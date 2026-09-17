"""Where the LiveAgents platform lives, and what proves who is calling.

Two hosts, two jobs, and the split is the same one Agent Terminal makes:

* **The workspace** (``terminal.liveagents.org``) writes agents and replays them. Claude Code and
  the trading harness live there, so authoring and backtesting happen there and nowhere else. A
  builder here that wrote its own templates would be a second idea of what an agent is, and the
  two would disagree the first time either changed.
* **The platform Worker** (``code.liveagents.org``) serves the console and, for now, the one
  route that belongs on the exchange and cannot be deployed there: the funding request an agent
  raises. It takes the exchange credential, so there is nothing extra to configure.
* **The exchange** (``dex.liveagents.org``) owns deployed agents: the sub-accounts, the scoped
  tokens, the containers and the lifecycle. It is the authority on what is running, so
  list/start/stop/redeploy/logs ask it rather than asking a terminal.

URLs are behaviour, so they are settings under ``plugins.entries.liveagents.settings``. Tokens are
credentials, so they come from the environment:

* ``LIVEAGENTS_TERMINAL_TOKEN`` — a workspace key (``lat_...``), or any bearer the workspace
  accepts.
* ``LIVEAGENTS_API_TOKEN`` — the exchange session. The same variable name the workspace's own
  client reads, so a machine already set up for one is set up for both.

**The two are not the same kind of thing, and that is the thing to know.**

``LIVEAGENTS_API_TOKEN`` is the console's ``la_dex_token``: a session the exchange minted and
holds, good for days, and fine to copy.

``LIVEAGENTS_TERMINAL_TOKEN`` wants a **workspace key** — a credential beginning ``lat_``, created
at the console under *Connect Claude Code → Workspace keys*. It is made on purpose, carries a
label, survives signing out, and is revoked by name.

What is *not* wanted is the console's ``la_terminal_token``. That looks like the matching value
and is not one: it is the Privy access token the browser signed in with, renewed while a tab is
open and dead within the hour on its own. Copying it produces a setup that works, then returns
401 for the rest of time, and copying it again produces the same setup. It was the only thing
there was to copy before workspace keys existed, which is why so many machines are configured
that way.

Do not go looking for a Privy *identity* token either: it exists only when that is switched on
for the app, and on liveagents.org it is not, which is why the platform's shared-identity cookie
is never written.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_TERMINAL_URL = "https://terminal.liveagents.org"
DEFAULT_EXCHANGE_URL = "https://dex.liveagents.org"
DEFAULT_CONSOLE_URL = "https://liveagents.org"
# The Worker that serves the console and its API. One route here matters to this
# plugin: the funding request an agent raises, which belongs beside the rest of
# `/api/agents` on the exchange and is served here instead because the
# exchange's container image cannot currently be built. It takes the exchange
# credential, not a console one, so nothing new has to be configured for it.
DEFAULT_PLATFORM_URL = "https://code.liveagents.org/api"

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
    platform_url: str = DEFAULT_PLATFORM_URL
    terminal_token: str = ""
    exchange_token: str = ""

    def require_terminal_token(self) -> str:
        if not self.terminal_token:
            raise MissingToken(
                f"No Agent Terminal credential. Set {TERMINAL_TOKEN_ENV} to a workspace key, or "
                f"pass --token. Create one at {self.console_url} under Connect Claude Code -> "
                "Workspace keys; it begins `lat_` and does not expire. Do not copy "
                "la_terminal_token out of browser storage: that is a browser session and lasts "
                "under an hour.")
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
        platform_url=setting("platform_url", DEFAULT_PLATFORM_URL),
        terminal_token=(environ.get(TERMINAL_TOKEN_ENV) or "").strip(),
        exchange_token=(environ.get(EXCHANGE_TOKEN_ENV) or "").strip(),
    )
