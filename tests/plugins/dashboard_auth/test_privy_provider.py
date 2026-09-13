"""Tests for the Privy dashboard-auth provider (the shared liveagents.org sign-in).

What matters here is what gets checked and what gets refused. A token signed by somebody else's
key, minted for another app, issued by another party or already expired must never become a
session; and the provider must never mint a session of its own, because one that outlives a
Privy logout is the failure the whole shape exists to prevent.

No live network: the JWKS client is replaced with the fixture's own key.
"""

from __future__ import annotations

import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from hermes_cli.dashboard_auth import (
    InvalidCodeError, ProviderError, RefreshExpiredError, assert_protocol_compliance)
from plugins.dashboard_auth import _shared
from plugins.dashboard_auth import privy as privy_plugin

APP_ID = "clzfakeprivyappid"


@pytest.fixture(scope="module")
def ec_keypair():
    """An ES256 keypair — the algorithm Privy signs with."""
    private = ec.generate_private_key(ec.SECP256R1())
    return {"private": private, "public": private.public_key()}


def _mint(ec_keypair, **overrides: Any) -> str:
    now = int(time.time())
    claims: Dict[str, Any] = {
        "iss": "privy.io",
        "aud": APP_ID,
        "sub": "did:privy:cm1234567890",
        "iat": now,
        "exp": now + 3600,
        "sid": "session-1",
    }
    claims.update(overrides)
    return jwt.encode(claims, ec_keypair["private"], algorithm="ES256")


def _with_keys(provider, ec_keypair):
    """Point the provider at the fixture's public key instead of Privy's endpoint."""
    key = MagicMock()
    key.key = ec_keypair["public"]
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = key
    provider._jwks_client = client
    return provider


@pytest.fixture
def provider(ec_keypair):
    return _with_keys(
        privy_plugin.PrivyDashboardAuthProvider(
            app_id=APP_ID, shared_cookie="la_privy_id", console_url="https://liveagents.org"),
        ec_keypair)


# ---------------------------------------------------------------------------
# Construction and protocol
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_protocol_compliant(self):
        assert assert_protocol_compliance(privy_plugin.PrivyDashboardAuthProvider) is None

    def test_empty_app_id_is_refused(self):
        with pytest.raises(ValueError):
            privy_plugin.PrivyDashboardAuthProvider(
                app_id="", shared_cookie="c", console_url="https://x.test")

    def test_capability_flags(self, provider):
        assert provider.supports_session is True
        assert provider.supports_sso_handoff is True
        assert provider.supports_token is True
        assert provider.supports_password is False

    def test_no_redirect_flow(self, provider):
        # The console signs people in; there is nothing to redirect to.
        with pytest.raises(NotImplementedError):
            provider.start_login(redirect_uri="https://hermes.liveagents.org/auth/callback")
        with pytest.raises(NotImplementedError):
            provider.complete_login(code="c", state="s", code_verifier="v", redirect_uri="r")

    def test_console_url_trailing_slash_is_normalised(self, ec_keypair):
        p = privy_plugin.PrivyDashboardAuthProvider(
            app_id=APP_ID, shared_cookie="c", console_url="https://liveagents.org/")
        assert p.sso_handoff_hint()["console_url"] == "https://liveagents.org"


# ---------------------------------------------------------------------------
# Verifying the shared token
# ---------------------------------------------------------------------------


class TestVerifySession:
    def test_valid_token_becomes_a_session_keyed_on_the_did(self, provider, ec_keypair):
        session = provider.verify_session(access_token=_mint(ec_keypair))
        assert session is not None
        assert session.user_id == "did:privy:cm1234567890"
        assert session.provider == "privy"

    def test_the_session_ends_when_the_token_does(self, provider, ec_keypair):
        exp = int(time.time()) + 120
        session = provider.verify_session(access_token=_mint(ec_keypair, exp=exp))
        # Not a TTL of our choosing: a session that outlives the token it came from is a session
        # a Privy logout cannot end.
        assert session.expires_at == exp

    def test_no_refresh_token_is_issued(self, provider, ec_keypair):
        assert provider.verify_session(access_token=_mint(ec_keypair)).refresh_token == ""

    def test_expired_token_is_not_a_session(self, provider, ec_keypair):
        assert provider.verify_session(access_token=_mint(ec_keypair, exp=int(time.time()) - 5)) is None

    def test_token_for_another_app_is_refused(self, provider, ec_keypair):
        # Two Privy apps that merely look alike produce tokens each side must reject.
        with pytest.raises(ProviderError):
            provider.verify_session(access_token=_mint(ec_keypair, aud="somebody-elses-app"))

    def test_token_from_another_issuer_is_refused(self, provider, ec_keypair):
        with pytest.raises(ProviderError):
            provider.verify_session(access_token=_mint(ec_keypair, iss="https://evil.example"))

    def test_token_signed_by_another_key_is_refused(self, provider):
        other = ec.generate_private_key(ec.SECP256R1())
        now = int(time.time())
        forged = jwt.encode(
            {"iss": "privy.io", "aud": APP_ID, "sub": "did:privy:attacker",
             "iat": now, "exp": now + 3600},
            other, algorithm="ES256")
        with pytest.raises(ProviderError):
            provider.verify_session(access_token=forged)

    def test_a_non_jwt_bearer_is_simply_not_ours(self, provider):
        # Another provider's opaque token must fall through, not 503 the dashboard.
        provider._jwks_client.get_signing_key_from_jwt.side_effect = jwt.DecodeError("not a jwt")
        assert provider.verify_session(access_token="an-opaque-peer-key") is None

    def test_unreachable_keys_are_an_outage_not_a_rejection(self, provider, ec_keypair):
        provider._jwks_client.get_signing_key_from_jwt.side_effect = (
            jwt.PyJWKClientConnectionError("auth.privy.io unreachable"))
        with pytest.raises(ProviderError):
            provider.verify_session(access_token=_mint(ec_keypair))


class TestSessionLifecycle:
    def test_refresh_always_rejects(self, provider):
        # There is nothing of ours to rotate, and minting something would recreate a session
        # Privy cannot end. The middleware reads this as "not my token" and falls back to login.
        with pytest.raises(RefreshExpiredError):
            provider.refresh_session(refresh_token="anything")

    def test_revoke_never_raises(self, provider):
        assert provider.revoke_session(refresh_token="anything") is None


class TestTokenAuth:
    def test_a_privy_token_works_as_a_service_credential(self, provider, ec_keypair):
        principal = provider.verify_token(token=_mint(ec_keypair))
        assert principal.principal == "did:privy:cm1234567890"
        assert principal.provider == "privy"

    def test_an_unrecognised_token_returns_none_rather_than_raising(self, provider, ec_keypair):
        # The token seam falls through to the next provider; it must never see an exception.
        assert provider.verify_token(token=_mint(ec_keypair, aud="another-app")) is None
        provider._jwks_client.get_signing_key_from_jwt.side_effect = jwt.DecodeError("nope")
        assert provider.verify_token(token="opaque") is None


# ---------------------------------------------------------------------------
# What the login page and the logout route read off the provider
# ---------------------------------------------------------------------------


class TestHandoffSurface:
    def test_hint_names_the_shared_cookie_and_where_to_sign_in(self, provider):
        hint = provider.sso_handoff_hint()
        assert hint["cookie"] == "la_privy_id"
        assert hint["console_url"] == "https://liveagents.org"
        assert hint["label"]

    def test_sign_out_clears_the_refresh_token_too(self, provider):
        names = provider.sso_cookies_to_clear()
        assert "la_privy_id" in names
        # Leaving this behind lets the SDK mint a new access token and undo the sign-out.
        assert "privy-refresh-token" in names

    def test_a_renamed_shared_cookie_is_the_one_cleared(self, ec_keypair):
        p = privy_plugin.PrivyDashboardAuthProvider(
            app_id=APP_ID, shared_cookie="custom_name", console_url="https://x.test")
        assert "custom_name" in p.sso_cookies_to_clear()
        assert p.sso_handoff_hint()["cookie"] == "custom_name"


class TestJwksClient:
    def test_the_app_id_travels_in_the_path_and_the_header(self, ec_keypair):
        # Privy's JWKS endpoint wants both; the shared helper sends a fixed header set, which is
        # why this provider builds its own client.
        p = privy_plugin.PrivyDashboardAuthProvider(
            app_id=APP_ID, shared_cookie="c", console_url="https://x.test")
        with patch("jwt.PyJWKClient") as client_cls:
            p._get_jwks_client()
        client_cls.assert_called_once_with(
            f"https://auth.privy.io/api/v1/apps/{APP_ID}/jwks.json",
            cache_keys=True,
            lifespan=_shared.JWKS_CACHE_SECONDS,
            headers={
                "Accept": "application/json",
                "User-Agent": "HermesAgent/1.0",
                "privy-app-id": APP_ID,
            },
        )

    def test_the_client_is_built_once_and_reused(self, ec_keypair):
        p = privy_plugin.PrivyDashboardAuthProvider(
            app_id=APP_ID, shared_cookie="c", console_url="https://x.test")
        with patch("jwt.PyJWKClient") as client_cls:
            assert p._get_jwks_client() is p._get_jwks_client()
        assert client_cls.call_count == 1


# ---------------------------------------------------------------------------
# Registration: config.yaml is canonical, env overrides
# ---------------------------------------------------------------------------


class TestRegistration:
    @pytest.fixture
    def patch_config(self, monkeypatch):
        def _set(privy_block: Dict[str, Any] | None) -> None:
            cfg = {"dashboard": {"privy": privy_block}} if privy_block is not None else {}
            monkeypatch.setattr("hermes_cli.config.load_config", lambda: cfg)

        return _set

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for name in (
            "HERMES_DASHBOARD_PRIVY_APP_ID",
            "HERMES_DASHBOARD_PRIVY_SHARED_COOKIE",
            "HERMES_DASHBOARD_PRIVY_CONSOLE_URL",
        ):
            monkeypatch.delenv(name, raising=False)

    def test_unconfigured_deployments_register_nothing(self, patch_config):
        patch_config(None)
        ctx = MagicMock()
        privy_plugin.register(ctx)
        ctx.register_dashboard_auth_provider.assert_not_called()
        assert "app_id" in privy_plugin.LAST_SKIP_REASON

    def test_config_yaml_alone_registers(self, patch_config):
        patch_config({"app_id": "from-config"})
        ctx = MagicMock()
        privy_plugin.register(ctx)
        registered = ctx.register_dashboard_auth_provider.call_args.args[0]
        assert registered._app_id == "from-config"
        # Defaults that match what the console publishes.
        assert registered.sso_handoff_hint()["cookie"] == "la_privy_id"
        assert registered.sso_handoff_hint()["console_url"] == "https://liveagents.org"

    def test_env_overrides_config(self, patch_config, monkeypatch):
        patch_config({"app_id": "from-config"})
        monkeypatch.setenv("HERMES_DASHBOARD_PRIVY_APP_ID", "from-env")
        ctx = MagicMock()
        privy_plugin.register(ctx)
        assert ctx.register_dashboard_auth_provider.call_args.args[0]._app_id == "from-env"

    def test_a_blank_env_var_does_not_shadow_config(self, patch_config, monkeypatch):
        patch_config({"app_id": "from-config"})
        monkeypatch.setenv("HERMES_DASHBOARD_PRIVY_APP_ID", "   ")
        ctx = MagicMock()
        privy_plugin.register(ctx)
        assert ctx.register_dashboard_auth_provider.call_args.args[0]._app_id == "from-config"

    def test_cookie_and_console_are_configurable(self, patch_config):
        patch_config({
            "app_id": "a", "shared_cookie": "other_cookie",
            "console_url": "https://staging.liveagents.org"})
        ctx = MagicMock()
        privy_plugin.register(ctx)
        hint = ctx.register_dashboard_auth_provider.call_args.args[0].sso_handoff_hint()
        assert hint["cookie"] == "other_cookie"
        assert hint["console_url"] == "https://staging.liveagents.org"

    def test_a_previous_skip_reason_does_not_survive_a_successful_register(self, patch_config):
        patch_config(None)
        privy_plugin.register(MagicMock())
        assert privy_plugin.LAST_SKIP_REASON
        patch_config({"app_id": "a"})
        privy_plugin.register(MagicMock())
        assert privy_plugin.LAST_SKIP_REASON == ""
