"""Where the LiveAgents platform lives, and what proves who is calling.

Two hosts, two jobs, and the split is the same one Agent Terminal makes:

* **The workspace** (``terminal.liveagents.org``) writes agents and replays them. Claude Code and
  the trading harness live there, so authoring and backtesting happen there and nowhere else. A
  builder here that wrote its own templates would be a second idea of what an agent is, and the
  two would disagree the first time either changed.
* **The exchange** (``dex.liveagents.org``) owns deployed agents: the sub-accounts, the scoped
  tokens, the containers and the lifecycle. It is the authority on what is running, so
  list/start/stop/redeploy/logs ask it rather than asking a terminal.

URLs are behaviour, so they are settings under ``plugins.entries.liveagents.settings``. Tokens are
credentials, so they come from the environment:

* ``LIVEAGENTS_TERMINAL_TOKEN`` — a bearer the workspace accepts.
* ``LIVEAGENTS_API_TOKEN`` — the exchange session. The same variable name the workspace's own
  client reads, so a machine already set up for one is set up for both.

**The console already holds both.** It signs Agent Terminal's challenge with the account's
embedded wallet and exchanges the same Privy identity for an exchange session, keeping the
results in its own storage as ``la_terminal_token`` and ``la_dex_token``. Those are the values to
copy; they are wallet-minted sessions and last days.

A Privy **access** token is also accepted by the workspace, and is what the dashboard itself signs
in with — but it expires in about an hour, so it is not what belongs in a configured credential.
Do not go looking for a Privy *identity* token: it exists only when that is switched on for the
app, and on liveagents.org it is not, which is why the platform's shared-identity cookie is never
written.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_TERMINAL_URL = "https://terminal.liveagents.org"
DEFAULT_EXCHANGE_URL = "https://dex.liveagents.org"
DEFAULT_CONSOLE_URL = "https://liveagents.org"

TERMINAL_TOKEN_ENV = "LIVEAGENTS_TERMINAL_TOKEN"
EXCHANGE_TOKEN_ENV = "LIVEAGENTS_API_TOKEN"


class MissingToken(Exception):
    """No credential for the host a command needs. Carries what to set, not a stack trace."""


@dataclass(frozen=True)
class LiveAgentsConfig:
    """Resolved addresses and credentials. Tokens may be empty; commands say so when they need one."""

    terminal_url: str = DEFAULT_TERMINAL_URL
    exchange_url: str = DEFAULT_EXCHANGE_URL
    console_url: str = DEFAULT_CONSOLE_URL
    terminal_token: str = ""
    exchange_token: str = ""

    def require_terminal_token(self) -> str:
        if not self.terminal_token:
            raise MissingToken(
                f"No Agent Terminal credential. Set {TERMINAL_TOKEN_ENV} to a token the workspace "
                f"accepts — the Privy identity token from a {self.console_url} sign-in is one — or "
                "pass --token.")
        return self.terminal_token

    def require_exchange_token(self) -> str:
        if not self.exchange_token:
            raise MissingToken(
                f"No exchange credential. Set {EXCHANGE_TOKEN_ENV} to your {self.exchange_url} API "
                "token, or pass --token. Market data needs no token; anything about an account "
                "does.")
        return self.exchange_token


def _clean_url(raw: object, default: str) -> str:
    """A non-empty string with no trailing slash, else *default*."""
    text = str(raw or "").strip().rstrip("/")
    return text or default


def load_config(
    get_setting: Optional[Callable[[str, object], object]] = None,
    *,
    env: Optional[dict] = None,
) -> LiveAgentsConfig:
    """Resolve the configuration.

    *get_setting* is ``ctx.get_config`` (plugin-relative settings); it is optional so the clients
    and their tests can run without a plugin manager. *env* defaults to the real environment.
    """
    environ = os.environ if env is None else env

    def setting(key: str, default: str) -> str:
        if get_setting is None:
            return default
        try:
            return _clean_url(get_setting(key, default), default)
        except Exception:
            # A malformed config file must not stop a command that has defaults to fall back on.
            return default

    return LiveAgentsConfig(
        terminal_url=setting("terminal_url", DEFAULT_TERMINAL_URL),
        exchange_url=setting("exchange_url", DEFAULT_EXCHANGE_URL),
        console_url=setting("console_url", DEFAULT_CONSOLE_URL),
        terminal_token=(environ.get(TERMINAL_TOKEN_ENV) or "").strip(),
        exchange_token=(environ.get(EXCHANGE_TOKEN_ENV) or "").strip(),
    )
