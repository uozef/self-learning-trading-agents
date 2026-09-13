"""LiveAgents — create, backtest, deploy and supervise trading agents on liveagents.org.

Hermes becomes another console for the platform, not a second implementation of it. Agent
Terminal already runs Claude Code against the trading harness, writes agents, replays them and
deploys them onto the exchange with a sub-account of their own; that machinery stays where it is.
A builder here that wrote its own templates would be a second idea of what an agent is, and the
two would disagree the first time either changed. So this plugin is a client:

* **Authoring and backtesting** go to the caller's Agent Terminal workspace
  (``terminal.liveagents.org``), the same endpoints the browser console drives.
* **The agent lifecycle** goes to the exchange (``dex.liveagents.org``), which owns the
  sub-accounts, the scoped tokens and the containers, and is therefore the authority on what is
  running.

The command *names* are Agent Terminal's, deliberately: ``/create-new-trading-agent``,
``/backtest``, ``/deploy-agent-live`` and the rest arrive as skills under ``skills/trading/``, so
somebody moving between the terminal and this dashboard types the same thing in both. Those
skills carry the judgement; this plugin registers the plumbing they call,
``hermes liveagents ...``, which is the analogue of ``node scripts/deploy.mjs`` in a workspace.

Configuration lives in two places for the usual reason. URLs are behaviour, so they are settings
under ``plugins.entries.liveagents.settings`` (``terminal_url``, ``exchange_url``,
``console_url``). Tokens are credentials, so they come from the environment:
``LIVEAGENTS_TERMINAL_TOKEN`` for the workspace and ``LIVEAGENTS_API_TOKEN`` for the exchange.
The shared Privy identity token is a valid workspace credential, which is the point of the shared
sign-in: one account across the console, the terminal and this dashboard.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_settings_getter: Optional[Callable[[str, Any], Any]] = None


def settings_reader() -> Optional[Callable[[str, Any], Any]]:
    """The plugin-relative settings reader, once ``register`` has run.

    Captured rather than looked up because the CLI also runs with no plugin manager behind it (a
    script, a test), where defaults are the right answer instead of an error.
    """
    return _settings_getter


def register(ctx) -> None:
    """Register ``hermes liveagents ...``."""
    global _settings_getter
    _settings_getter = getattr(ctx, "get_config", None)

    from . import cli

    ctx.register_cli_command(
        name="liveagents",
        help="Create, backtest, deploy and supervise trading agents on liveagents.org",
        setup_fn=cli.register_cli,
        handler_fn=cli.dispatch,
        description=(
            "Drives the caller's Agent Terminal workspace for authoring and backtests, and the "
            "exchange for the agent lifecycle. The trading skills call these subcommands."),
    )
    logger.info("liveagents: registered `hermes liveagents` (workspace + exchange client)")
