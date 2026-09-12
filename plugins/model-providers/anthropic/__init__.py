"""Native Anthropic provider profile."""

import json
import logging
import urllib.request

from hermes_cli.urllib_security import open_credentialed_url
from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)


class AnthropicProfile(ProviderProfile):
    """Native Anthropic — Claude auth token on Bearer, Console API key on x-api-key."""

    def fetch_models(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ) -> list[str] | None:
        """Model ids from /v1/models, authenticating by credential shape.

        A Claude auth token (``claude setup-token`` / ``CLAUDE_CODE_OAUTH_TOKEN``, an
        ``sk-ant-oat01…`` value) is an OAuth credential, not an API key: sent as ``x-api-key`` it
        401s. It needs ``Authorization: Bearer`` plus the OAuth beta header, and a subscription that
        rejects the 1M-context beta needs a retry without it. ``models._fetch_anthropic_models``
        already implements all of that, so delegate rather than keep a second, weaker copy here —
        this method used to hardcode ``x-api-key`` and broke every token-authenticated catalog fetch.
        """
        try:
            from hermes_cli.models import _fetch_anthropic_models
        except ImportError:  # pragma: no cover — models layer unavailable (trimmed install)
            return self._fetch_models_with_api_key(api_key, timeout=timeout)
        return _fetch_anthropic_models(timeout=timeout, base_url=base_url, api_key=api_key)

    @staticmethod
    def _fetch_models_with_api_key(api_key: str | None, *, timeout: float) -> list[str] | None:
        """Console-API-key-only fallback for installs without the models layer."""
        if not api_key:
            return None
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/models")
            for k, v in (("x-api-key", api_key), ("anthropic-version", "2023-06-01"), ("Accept", "application/json")):
                req.add_header(k, v)
            with open_credentialed_url(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
        except Exception as exc:
            logger.debug("fetch_models(anthropic): %s", exc)
            return None


# env_vars order mirrors hermes_cli.auth's registry row and resolve_anthropic_token(): the Claude
# auth token wins over a Console API key when both are present.
#
# auth_type stays "api_key" even though the preferred credential is an OAuth token. It is not a
# statement about the wire format — it is the flag that keeps this provider in the env-var-backed
# discovery and health-check paths (hermes_cli/auth.py registry sync, doctor_connectivity's /models
# probe), which skip anything declaring an interactive OAuth flow. The wire format is chosen per
# request from the credential's shape by anthropic_adapter._auth_style().
anthropic = AnthropicProfile(
    name="anthropic", aliases=("claude", "claude-oauth", "claude-code"), api_mode="anthropic_messages",
    env_vars=("ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"),
    base_url="https://api.anthropic.com", auth_type="api_key", default_aux_model="claude-haiku-4-5-20251001",
)

register_provider(anthropic)
