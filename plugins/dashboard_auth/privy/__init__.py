"""PrivyDashboardAuthProvider — the shared Privy session the whole of liveagents.org signs in to.

The console at liveagents.org, Agent Terminal at terminal.liveagents.org and this dashboard are
one Privy application, so a sign-in on any of them is a sign-in on all of them. What makes that
safe is what gets checked: the algorithm, the signature against the keys Privy publishes for this
app, the issuer, that the audience is this app rather than somebody else's, and that the token has
not expired.

**Nothing here mints a session.** ``verify_session`` verifies Privy's own token on every request
and the session ends exactly when that token does, so a Privy logout cannot leave a live dashboard
session behind. That is the failure this shape exists to prevent: trading a console sign-in for a
long-lived session of our own means Privy revokes an account and the dashboard never hears about
it. For the same reason ``refresh_session`` always rejects — there is nothing of ours to rotate,
and re-reading the shared cookie is the refresh.

There are two tokens and they are not the same thing. The identity token (``privy-id-token``)
carries the user; the access token (``privy-token``) carries a subject and a session id. Either
proves the session and both are the same signature over the same app id, so one verification
covers both.

Configuration (``dashboard.privy`` in config.yaml, canonical):

    dashboard:
      privy:
        app_id: "<the Privy app id>"        # same value as the console's NEXT_PUBLIC_PRIVY_APP_ID
        shared_cookie: la_privy_id          # optional; what the console publishes the token in
        console_url: https://liveagents.org # optional; where an unauthenticated visitor is sent

``HERMES_DASHBOARD_PRIVY_APP_ID`` overrides it, because the Cloudflare container has no
config.yaml an operator can edit and secrets arrive as environment variables.

**The app id must be byte-identical to the console's.** Two ids that merely look alike produce two
accounts for the same person and tokens each side rejects as minted for somebody else.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from hermes_cli.dashboard_auth import (
    DashboardAuthProvider, InvalidCodeError, ProviderError, RefreshExpiredError, Session,
    TokenPrincipal)
from plugins.dashboard_auth._shared import (
    JWKS_CACHE_SECONDS,
    NonInteractiveMixin,
    SkipRegistration,
    load_config_section,
    register_provider,
    resolve_env_or_cfg,
    session_from_claims,
    verify_jwt,
)

logger = logging.getLogger(__name__)
_TAG = "dashboard-auth-privy"

# Privy signs with ES256 and issues as `privy.io`. Both are fixed by Privy rather than by us, so
# they are constants: making them configurable would turn a forged-issuer check into a setting.
_ALGORITHMS = ["ES256"]
_ISSUER = "privy.io"
_JWKS_TEMPLATE = "https://auth.privy.io/api/v1/apps/{app_id}/jwks.json"

_DEFAULT_SHARED_COOKIE = "la_privy_id"
_DEFAULT_CONSOLE_URL = "https://liveagents.org"

LAST_SKIP_REASON: str = ""  # cleared on every register() so restarts don't leak stale reasons


class PrivyDashboardAuthProvider(NonInteractiveMixin, DashboardAuthProvider):
    """Verifies the Privy token the console hands over; never issues one."""

    name = "privy"
    display_name = "LiveAgents"
    supports_session = True
    # A Privy token is equally good as a service credential on the token-auth routes: same
    # signature, same app id, same expiry.
    supports_token = True
    # There is no login flow here. The token is minted by the console and handed over, so the
    # login page offers a handoff and a link out rather than a redirect into an IDP.
    supports_sso_handoff = True

    _NOT_INTERACTIVE = (
        "PrivyDashboardAuthProvider has no OAuth redirect flow: the console signs people in and "
        "hands the token over. See POST /auth/sso-session.")

    def __init__(self, *, app_id: str, shared_cookie: str, console_url: str) -> None:
        if not app_id:
            raise ValueError("app_id must be non-empty")
        self._app_id = app_id
        self._shared_cookie = shared_cookie
        self._console_url = console_url.rstrip("/")
        self._jwks_client: Any = None  # lazily built (crypto import cost)

    # ---- what the login page and the logout route need to know ------------

    def sso_handoff_hint(self) -> Dict[str, str]:
        """Where a handed-over token comes from, for the login page and the logout route.

        ``cookie`` is the name the console publishes the identity token under on the parent
        domain; ``console_url`` is where somebody with no session is sent to get one. Returned as
        data so the core login page stays free of anything Privy-specific.
        """
        return {
            "cookie": self._shared_cookie,
            "console_url": self._console_url,
            "label": self.display_name,
        }

    def sso_cookies_to_clear(self) -> tuple[str, ...]:
        """Every cookie a sign-out has to remove, not just ours.

        Leaving the refresh token behind lets the SDK mint a new access token on the next page
        load and undo the sign-out, so the whole set goes. Clearing a cookie that was never there
        costs nothing.
        """
        return (
            self._shared_cookie,
            "privy-token",
            "privy-id-token",
            "privy-refresh-token",
            "privy-session",
        )

    # ---- session verification ---------------------------------------------

    def _get_jwks_client(self) -> Any:
        """Privy's signing keys, cached.

        Built here rather than with ``_shared.make_jwks_client`` because Privy's JWKS endpoint
        wants the app id in a ``privy-app-id`` header as well as in the path, and the shared
        helper sends a fixed header set. Same cache lifespan as every other provider.
        """
        if self._jwks_client is None:
            from jwt import PyJWKClient

            self._jwks_client = PyJWKClient(
                _JWKS_TEMPLATE.format(app_id=self._app_id),
                cache_keys=True,
                lifespan=JWKS_CACHE_SECONDS,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HermesAgent/1.0",
                    "privy-app-id": self._app_id,
                },
            )
        return self._jwks_client

    def _claims_for(self, token: str) -> Dict[str, Any]:
        return verify_jwt(
            token, self._get_jwks_client(), algorithms=_ALGORITHMS,
            audience=self._app_id, issuer=_ISSUER, label="Privy token")

    def verify_session(self, *, access_token: str) -> Optional[Session]:
        """The Privy token, verified. ``None`` when it is expired or not one of ours.

        A Privy DID is the account. An address or a handle sent by a caller proves nothing and the
        token carries none to check it against, so ``sub`` is the only identity trusted here.
        """
        try:
            claims = self._claims_for(access_token)
        except InvalidCodeError:
            return None
        return session_from_claims(
            self.name, claims, access_token=access_token, refresh_token="",
            label="Privy token", display_name=str(claims.get("sub", "")))

    def refresh_session(self, *, refresh_token: str) -> Session:
        """Always rejects, and that is the design.

        Privy owns the session; there is no refresh token of ours and minting one would recreate
        exactly the thing this provider avoids — a dashboard session that outlives a Privy logout.
        The middleware treats this as "this provider does not recognise that token", tries the
        others, and falls back to the login page, where the shared cookie is read again.
        """
        raise RefreshExpiredError(
            "the Privy session is refreshed by re-reading the shared cookie, not by rotating a "
            "refresh token here")

    def revoke_session(self, *, refresh_token: str) -> None:
        # Nothing server-side to revoke: the token is Privy's and ends when Privy says so. The
        # logout route clears the cookies named by ``sso_cookies_to_clear``. Must not raise.
        return None

    # ---- non-interactive callers ------------------------------------------

    def verify_token(self, *, token: str) -> Optional[TokenPrincipal]:
        """A Privy token presented as a service credential. ``None`` when it is not one."""
        try:
            claims = self._claims_for(token)
        except (InvalidCodeError, ProviderError):
            return None
        subject = str(claims.get("sub", ""))
        return TokenPrincipal(principal=subject, provider=self.name) if subject else None


# ---- Plugin entry point ----

def _settings() -> dict:
    """Resolve provider kwargs from env/config; raises ``SkipRegistration`` when unconfigured."""
    section = load_config_section(logger, _TAG, "dashboard", "privy")

    def setting(env_name: str, cfg_key: str, default: str = "") -> str:
        return resolve_env_or_cfg(env_name, section.get(cfg_key, "")) or default

    app_id = setting("HERMES_DASHBOARD_PRIVY_APP_ID", "app_id")
    if not app_id:
        raise SkipRegistration(
            "dashboard.privy.app_id is not set (and HERMES_DASHBOARD_PRIVY_APP_ID is empty). Set "
            "it to the same Privy app id the console uses to share one sign-in across "
            "liveagents.org, or use another dashboard auth provider.")
    return {
        "app_id": app_id,
        "shared_cookie": setting(
            "HERMES_DASHBOARD_PRIVY_SHARED_COOKIE", "shared_cookie", _DEFAULT_SHARED_COOKIE),
        "console_url": setting(
            "HERMES_DASHBOARD_PRIVY_CONSOLE_URL", "console_url", _DEFAULT_CONSOLE_URL),
    }


def register(ctx) -> None:
    """Register ``PrivyDashboardAuthProvider`` when an app id is configured; a no-op otherwise."""
    global LAST_SKIP_REASON
    LAST_SKIP_REASON = ""
    kwargs, LAST_SKIP_REASON = register_provider(
        ctx, logger, _TAG, PrivyDashboardAuthProvider, _settings)
    if kwargs is not None:
        logger.info("dashboard-auth-privy: registered shared Privy session (app_id=%s)", kwargs["app_id"])
