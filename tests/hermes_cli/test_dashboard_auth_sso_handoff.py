"""Tests for the SSO-handoff seam: adopting a session token minted by a sibling application.

Covers the protocol extension (``supports_sso_handoff`` + ``sso_handoff_hint`` +
``sso_cookies_to_clear``), ``POST /auth/sso-session`` end-to-end through the REAL
``gated_auth_middleware``, the login page's handoff panel, and the sign-out that has to reach
cookies this origin never set.

The E2E harness mirrors ``test_dashboard_auth_password_login.py``: register a provider, flip
``app.state.auth_required = True``, drive a ``TestClient``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from hermes_cli import web_server
from hermes_cli.dashboard_auth import (
    DashboardAuthProvider,
    ProviderError,
    Session,
    assert_protocol_compliance,
    clear_providers,
    list_session_providers,
    list_sso_handoff_providers,
    register_provider,
)
from hermes_cli.dashboard_auth.cookies import (
    SESSION_AT_COOKIE, parent_cookie_domain)
from hermes_cli.dashboard_auth.login_page import render_login_html
from tests.hermes_cli.conftest_dashboard_auth import StubAuthProvider

_SECRET = b"sso-handoff-test-secret"
_SHARED_COOKIE = "sibling_identity"
_CONSOLE = "https://console.example.org"


def _mint(sub: str = "did:example:abc", ttl: int = 3600) -> str:
    """A token 'minted by the sibling application' — signed JSON, not a real JWT."""
    raw = json.dumps({"sub": sub, "exp": int(time.time()) + ttl}, separators=(",", ":")).encode()
    sig = hmac.new(_SECRET, raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + sig).decode()


class HandoffProvider(DashboardAuthProvider):
    """A provider whose session token comes from elsewhere and is only ever verified here."""

    name = "sibling"
    display_name = "Sibling Console"
    supports_sso_handoff = True

    def __init__(self, *, unreachable: bool = False) -> None:
        self.unreachable = unreachable
        self.revoked: list[str] = []

    def sso_handoff_hint(self):
        return {"cookie": _SHARED_COOKIE, "console_url": _CONSOLE, "label": self.display_name}

    def sso_cookies_to_clear(self):
        return (_SHARED_COOKIE, "sibling-refresh-token")

    def start_login(self, *, redirect_uri: str):
        raise NotImplementedError("no redirect flow; the console signs people in")

    def complete_login(self, *, code: str, state: str, code_verifier: str, redirect_uri: str):
        raise NotImplementedError("no redirect flow; the console signs people in")

    def verify_session(self, *, access_token: str):
        if self.unreachable:
            raise ProviderError("sibling keys unreachable")
        try:
            blob = base64.urlsafe_b64decode(access_token.encode())
            raw, sig = blob[:-32], blob[-32:]
            if not hmac.compare_digest(sig, hmac.new(_SECRET, raw, hashlib.sha256).digest()):
                return None
            payload = json.loads(raw)
        except Exception:
            return None
        if payload.get("exp", 0) <= int(time.time()):
            return None
        return Session(
            user_id=payload["sub"], email="", display_name=payload["sub"], org_id="",
            provider=self.name, expires_at=payload["exp"], access_token=access_token,
            refresh_token="")

    def refresh_session(self, *, refresh_token: str):
        from hermes_cli.dashboard_auth import RefreshExpiredError

        raise RefreshExpiredError("the sibling owns the session; re-read the shared cookie")

    def revoke_session(self, *, refresh_token: str) -> None:
        self.revoked.append(refresh_token)


def _gate(client_provider):
    """Register *client_provider* and return a gated TestClient over an https origin."""
    clear_providers()
    register_provider(client_provider)
    prev = (
        getattr(web_server.app.state, "bound_host", None),
        getattr(web_server.app.state, "bound_port", None),
        getattr(web_server.app.state, "auth_required", None),
    )
    web_server.app.state.bound_host = "hermes.example.org"
    web_server.app.state.bound_port = 443
    web_server.app.state.auth_required = True
    client = TestClient(web_server.app, base_url="https://hermes.example.org")
    return client, prev


def _restore(prev):
    clear_providers()
    web_server.app.state.bound_host = prev[0]
    web_server.app.state.bound_port = prev[1]
    web_server.app.state.auth_required = prev[2]


@pytest.fixture
def handoff_provider():
    return HandoffProvider()


@pytest.fixture
def gated_app(handoff_provider):
    client, prev = _gate(handoff_provider)
    yield client
    _restore(prev)


# ---------------------------------------------------------------------------
# Protocol extension
# ---------------------------------------------------------------------------


class TestProtocolExtension:
    def test_handoff_provider_is_protocol_compliant(self):
        assert assert_protocol_compliance(HandoffProvider) is None

    def test_providers_without_the_capability_default_to_false(self):
        # An OAuth provider (the Stub) must not be drivable by a token a page supplies.
        assert StubAuthProvider.supports_sso_handoff is False
        assert StubAuthProvider().sso_handoff_hint() == {}
        assert StubAuthProvider().sso_cookies_to_clear() == ()

    def test_registry_lists_only_handoff_providers(self, handoff_provider):
        clear_providers()
        try:
            register_provider(StubAuthProvider())
            register_provider(handoff_provider)
            assert [p.name for p in list_sso_handoff_providers()] == [handoff_provider.name]
            # Still an ordinary interactive provider as far as everything else is concerned.
            assert handoff_provider.name in [p.name for p in list_session_providers()]
        finally:
            clear_providers()


# ---------------------------------------------------------------------------
# POST /auth/sso-session
# ---------------------------------------------------------------------------


class TestSsoSessionRoute:
    def test_valid_token_becomes_this_origins_session(self, gated_app):
        resp = gated_app.post("/auth/sso-session", json={"token": _mint()})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert any(SESSION_AT_COOKIE in name for name in gated_app.cookies)
        # The cookie alone now authenticates an ordinary request.
        me = gated_app.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["user_id"] == "did:example:abc"

    def test_next_is_returned_when_safe(self, gated_app):
        resp = gated_app.post("/auth/sso-session", json={"token": _mint(), "next": "/agents"})
        assert resp.status_code == 200
        assert resp.json()["next"] == "/agents"

    def test_offsite_next_is_refused_and_falls_back_to_root(self, gated_app):
        resp = gated_app.post(
            "/auth/sso-session", json={"token": _mint(), "next": "https://evil.example/steal"})
        assert resp.status_code == 200
        assert resp.json()["next"] == "/"

    def test_expired_token_is_rejected_without_a_session(self, gated_app):
        resp = gated_app.post("/auth/sso-session", json={"token": _mint(ttl=-10)})
        assert resp.status_code == 401
        assert not any(SESSION_AT_COOKIE in name for name in gated_app.cookies)

    def test_tampered_token_is_rejected(self, gated_app):
        resp = gated_app.post("/auth/sso-session", json={"token": _mint()[:-4] + "AAAA"})
        assert resp.status_code == 401

    def test_empty_token_is_rejected(self, gated_app):
        assert gated_app.post("/auth/sso-session", json={"token": "   "}).status_code == 401

    def test_unreachable_provider_is_503_not_401(self):
        # Uncertain, not rejected: a page that was told 401 would clear a working credential.
        client, prev = _gate(HandoffProvider(unreachable=True))
        try:
            assert client.post("/auth/sso-session", json={"token": _mint()}).status_code == 503
        finally:
            _restore(prev)

    def test_route_is_absent_when_no_provider_accepts_handoffs(self):
        client, prev = _gate(StubAuthProvider())
        try:
            resp = client.post("/auth/sso-session", json={"token": _mint()})
            assert resp.status_code == 404
        finally:
            _restore(prev)


# ---------------------------------------------------------------------------
# The gate adopting the shared cookie, with no login page in between
# ---------------------------------------------------------------------------


class TestGateAdoptsTheSharedCookie:
    """An already-signed-in visitor must never see a login page.

    Bouncing them to ``/login`` so a script there can read the same cookie the server could have
    read paints a password form in front of somebody who has already signed in somewhere else.
    That is the complaint this closes, not a cosmetic one.
    """

    def test_a_shared_cookie_is_a_session_without_a_redirect(self, gated_app):
        gated_app.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
        resp = gated_app.get("/api/auth/me", follow_redirects=False)
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "did:example:abc"

    def test_the_adopted_session_is_written_back_as_our_own_cookie(self, gated_app):
        gated_app.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
        resp = gated_app.get("/api/auth/me", follow_redirects=False)
        # Written back so the next request does not have to verify the shared token again.
        assert any(SESSION_AT_COOKIE in c for c in resp.headers.get_list("set-cookie"))

    def test_an_html_load_is_served_rather_than_redirected(self, gated_app):
        gated_app.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
        resp = gated_app.get("/", follow_redirects=False)
        assert resp.status_code != 302, "a signed-in visitor was sent to the login page"

    def test_a_stale_shared_cookie_still_reaches_the_login_page(self, gated_app):
        gated_app.cookies.set(_SHARED_COOKIE, _mint(ttl=-10), domain="hermes.example.org")
        resp = gated_app.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]

    def test_a_rotated_token_renews_without_a_re_login(self, gated_app):
        # The provider refuses refresh_session on purpose: re-reading the cookie IS the renewal.
        gated_app.cookies.set(SESSION_AT_COOKIE, _mint(ttl=-10))
        gated_app.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
        resp = gated_app.get("/api/auth/me", follow_redirects=False)
        assert resp.status_code == 200

    def test_a_provider_with_no_cookie_declared_is_not_consulted(self):
        class NoCookie(HandoffProvider):
            def sso_handoff_hint(self):
                return {"console_url": _CONSOLE}

        client, prev = _gate(NoCookie())
        try:
            client.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
            assert client.get("/", follow_redirects=False).status_code == 302
        finally:
            _restore(prev)

    def test_a_broken_provider_does_not_break_the_gate(self):
        class Broken(HandoffProvider):
            def sso_handoff_hint(self):
                raise RuntimeError("provider is broken")

        client, prev = _gate(Broken())
        try:
            # Still the login page, rather than a 500 for every visitor.
            assert client.get("/", follow_redirects=False).status_code == 302
        finally:
            _restore(prev)

    def test_an_unreachable_provider_falls_through_rather_than_503(self):
        client, prev = _gate(HandoffProvider(unreachable=True))
        try:
            client.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
            resp = client.get("/", follow_redirects=False)
            # Uncertain, not rejected, and not an outage we can confirm: offer the way in.
            assert resp.status_code == 302
        finally:
            _restore(prev)

    def test_an_ordinary_provider_never_has_a_cookie_read_for_it(self):
        client, prev = _gate(StubAuthProvider())
        try:
            client.cookies.set(_SHARED_COOKIE, _mint(), domain="hermes.example.org")
            # An OAuth provider must not be drivable by a cookie any page on the domain can write.
            assert client.get("/", follow_redirects=False).status_code == 302
        finally:
            _restore(prev)


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------


class TestLoginPage:
    def test_handoff_panel_carries_the_cookie_name_and_console_link(self, handoff_provider):
        clear_providers()
        try:
            register_provider(handoff_provider)
            html = render_login_html(next_path="/agents")
            assert f'data-cookie="{_SHARED_COOKIE}"' in html
            assert f'href="{_CONSOLE}"' in html
            assert 'data-next="/agents"' in html
            # The bootstrap has to be present, and it must post to the route that verifies.
            assert "/auth/sso-session" in html
        finally:
            clear_providers()

    def test_a_handoff_in_flight_paints_nothing(self, handoff_provider):
        """The flash this closes: a fully painted sign-in form, in the seconds
        before the redirect, shown to somebody who is already signed in."""
        clear_providers()
        try:
            register_provider(handoff_provider)
            html = render_login_html()
            # Set before first paint, which means in <head> and before the stylesheet.
            assert "setAttribute('data-handoff'" in html
            assert html.index("setAttribute('data-handoff'") < html.index("<style>")
            # And something for it to key off.
            assert "html[data-handoff] body" in html
            assert "visibility: hidden" in html
            # Failure has to undo it, or a stale token leaves a blank page.
            assert "removeAttribute('data-handoff')" in html
        finally:
            clear_providers()

    def test_no_handoff_provider_means_no_handoff_script(self):
        clear_providers()
        try:
            register_provider(StubAuthProvider())
            html = render_login_html()
            assert "/auth/sso-session" not in html
            assert "provider-handoff" not in html
            # Nor the pre-paint hook, which would hide a page nothing will reveal.
            # The stylesheet's rule is static and stays; with no script to set
            # the attribute it never matches, which costs nothing.
            assert "setAttribute('data-handoff'" not in html
        finally:
            clear_providers()

    def test_auth_login_sends_a_handoff_provider_to_the_login_page(self, gated_app):
        # There is no IDP to redirect to; without this branch start_login raises and it 500s.
        resp = gated_app.get("/auth/login?provider=sibling", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"].endswith("/login")

    def test_providers_endpoint_advertises_the_capability(self, gated_app):
        entry = gated_app.get("/api/auth/providers").json()["providers"][0]
        assert entry["supports_sso_handoff"] is True
        assert entry["supports_password"] is False


# ---------------------------------------------------------------------------
# Signing out of a shared session
# ---------------------------------------------------------------------------


class TestLogoutReachesTheSharedSession:
    def test_logout_expires_the_siblings_cookies_host_only_and_on_the_parent(self, gated_app):
        gated_app.post("/auth/sso-session", json={"token": _mint()})
        resp = gated_app.post("/auth/logout", follow_redirects=False)
        assert resp.status_code == 302
        set_cookies = resp.headers.get_list("set-cookie")
        for name in (_SHARED_COOKIE, "sibling-refresh-token"):
            deletions = [c for c in set_cookies if c.startswith(f"{name}=")]
            # One host-only and one for the parent domain: a cookie is identified by name,
            # domain and path together, so the host-only deletion cannot touch the shared copy.
            assert any("Domain=.example.org" in c for c in deletions), name
            assert any("Domain=" not in c for c in deletions), name
            assert all("Max-Age=0" in c for c in deletions), name

    def test_logout_still_works_when_the_provider_misbehaves(self):
        class Broken(HandoffProvider):
            def sso_cookies_to_clear(self):
                raise RuntimeError("provider is broken")

        client, prev = _gate(Broken())
        try:
            # Signing out is the one operation that has to work when everything else is wrong.
            assert client.post("/auth/logout", follow_redirects=False).status_code == 302
        finally:
            _restore(prev)


class TestParentCookieDomain:
    @pytest.mark.parametrize(
        "host,expected",
        [
            ("hermes.example.org", ".example.org"),
            ("deep.hermes.example.org", ".hermes.example.org"),
            ("hermes.example.org:8443", ".example.org"),
            ("HERMES.EXAMPLE.ORG", ".example.org"),
            # Nothing worth sharing: no parent, an IP literal, or loopback.
            ("example.org", None),
            ("localhost", None),
            ("127.0.0.1", None),
            ("", None),
        ],
    )
    def test_parent_domain_of(self, host, expected):
        assert parent_cookie_domain(host) == expected
