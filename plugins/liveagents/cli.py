"""``hermes liveagents ...`` — the plumbing the trading skills drive.

This is the analogue of ``node scripts/deploy.mjs`` and ``node scripts/backtest.mjs`` inside an
Agent Terminal workspace: the deterministic half, callable from a skill, a script or a person's
shell. The judgement half — which market, which kind of agent, whether a backtest result is
worth deploying — lives in the skills, exactly as it lives in Agent Terminal's own commands.

Subcommands map onto whichever host owns the question:

    whoami      workspace   who the workspace thinks we are, and whether Claude is signed in
    launch      workspace   a URL that opens Agent Terminal already signed in
    kinds       workspace   the templates it will build from
    build       workspace   write a new agent (streams)
    publish     workspace   deploy an agent the workspace holds (streams)
    backtest    workspace   replay a strategy; runs, and one run
    agents      exchange    what is deployed, with status and metrics
    logs        exchange    an agent's stored error and its container's output
    start/stop  exchange    lifecycle
    fund-agent  platform    ask the owner to fund an agent; the console moves the money
    redeploy    exchange    swap the code, keep the sub-account
    source      exchange    the code an agent is actually running

Output is plain text by default and ``--json`` everywhere, because a skill reads JSON and a
person reads a table.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Iterator, List, Optional

from .config import EXCHANGE_TOKEN_ENV, TERMINAL_TOKEN_ENV, LiveAgentsConfig, MissingToken, load_config
from .exchange import ExchangeClient, ExchangeError
from .terminal import TerminalClient, TerminalError

_DEFAULT_INTERVAL_SECONDS = 60


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire up ``hermes liveagents ...``."""
    parser.add_argument(
        "--token", default=None,
        help="Bearer token for this call, instead of the environment "
             f"({TERMINAL_TOKEN_ENV} for the workspace, {EXCHANGE_TOKEN_ENV} for the exchange)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    subs = parser.add_subparsers(dest="liveagents_command", required=False)

    subs.add_parser("whoami", help="Who the workspace thinks you are")
    subs.add_parser("kinds", help="Agent templates the workspace will build from")

    p_launch = subs.add_parser(
        "launch", help="A URL that opens Agent Terminal already signed in as you")
    p_launch.add_argument(
        "--as", dest="as_tag", default="",
        help="Who this session is signed in as; a changed tag signs the previous person out")

    p_build = subs.add_parser("build", help="Write a new agent in your workspace")
    p_build.add_argument("--idea", required=True, help="What the agent should do, in one or two sentences")
    p_build.add_argument("--market", required=True, help="Symbol it trades, e.g. BTC-PERP")
    p_build.add_argument("--kind", required=True, help="Template id from `kinds`")
    p_build.add_argument("--name", required=True, help="Agent name; the file is slugged from it")
    p_build.add_argument("--description", default="", help="Longer brief, when one sentence is not enough")
    p_build.add_argument(
        "--interval", type=int, default=_DEFAULT_INTERVAL_SECONDS,
        help=f"Seconds between decisions (default {_DEFAULT_INTERVAL_SECONDS})")

    p_publish = subs.add_parser(
        "publish", help="Deploy an agent your workspace holds (demo refuses every order)")
    p_publish.add_argument("name", help="Agent name as the workspace knows it")
    p_publish.add_argument("--market", required=True, help="Symbol it trades")
    p_publish.add_argument(
        "--mode", choices=("demo", "live"), default="demo",
        help="demo: it runs for real and the exchange refuses its orders. live: it trades")
    p_publish.add_argument(
        "--exchange-token", default=None,
        help=f"Exchange session for this deploy only (default: {EXCHANGE_TOKEN_ENV})")

    p_backtest = subs.add_parser("backtest", help="Replay a strategy in your workspace")
    p_backtest.add_argument(
        "agent", help="Path to the strategy inside the workspace, e.g. agents/momentum.mjs")
    p_backtest.add_argument("--market", default="", help="Symbol to replay on")
    p_backtest.add_argument("--interval", default="", help="Bar size, e.g. 5m")
    p_backtest.add_argument("--days", type=int, default=0, help="Window as a number of days back")
    p_backtest.add_argument("--from", dest="date_from", default="", help="Window start, YYYY-MM-DD")
    p_backtest.add_argument("--to", dest="date_to", default="", help="Window end, YYYY-MM-DD")
    p_backtest.add_argument("--dataset", default="", help="A HistPrice dataset handle (hp_…)")
    p_backtest.add_argument(
        "--param", action="append", default=[], metavar="NAME=VALUE",
        help="Override one declared tunable; repeatable")
    # The cost assumptions. A replay that is cheaper than reality is the most flattering thing a
    # backtest can be, so they are adjustable rather than baked in.
    p_backtest.add_argument("--fee", default="", help="Fee assumption, overriding the market's")
    p_backtest.add_argument("--slippage", default="", help="Slippage assumption")
    p_backtest.add_argument("--equity", default="", help="Starting equity")

    subs.add_parser("backtests", help="Saved backtest runs in your workspace")
    p_read = subs.add_parser("backtest-read", help="One saved run")
    p_read.add_argument("file", help="Run file, as `backtests` lists it")

    subs.add_parser("agents", help="What is deployed on the exchange")

    p_logs = subs.add_parser("logs", help="An agent's stored error and its container's output")
    p_logs.add_argument("name", help="Agent name or id")

    p_source = subs.add_parser("source", help="The code an agent is actually running")
    p_source.add_argument("name", help="Agent name or id")

    p_start = subs.add_parser("start", help="Start a stopped agent")
    p_start.add_argument("name", help="Agent name or id")

    p_fund = subs.add_parser(
        "fund-agent", help="Ask the owner to fund an agent (the console does the transfer)")
    p_fund.add_argument(
        "name", nargs="?", default="",
        help="Agent name or id. Defaults to the one deployed most recently")
    p_fund.add_argument(
        "--amount", default="",
        help="A suggestion that prefills the console dialog. Leave it out and the owner decides")
    p_fund.add_argument("--note", default="", help="One line saying why, shown in the dialog")
    p_fund.add_argument(
        "--no-wait", dest="wait", action="store_false",
        help="Record the request and return, instead of watching for the transfer")
    p_fund.set_defaults(wait=True)

    p_stop = subs.add_parser("stop", help="Stop a running agent (its sub-account is untouched)")
    p_stop.add_argument("name", help="Agent name or id")

    p_redeploy = subs.add_parser("redeploy", help="Swap an agent's code and start it again")
    p_redeploy.add_argument("name", help="Agent name or id")
    p_redeploy.add_argument("file", help="Local file holding the new source")
    p_redeploy.add_argument(
        "--params", default="",
        help="Tunable declarations (JSON file). Default: the sibling <file>.params.json when it exists")
    p_redeploy.add_argument("--market", default="", help="Change the market too")
    p_redeploy.add_argument("--mode", choices=("demo", "live"), default="", help="Change the mode too")


def dispatch(args: argparse.Namespace) -> int:
    """Run one subcommand. Returns a process exit code."""
    sub = getattr(args, "liveagents_command", None)
    handler = _COMMANDS.get(sub or "agents")
    if handler is None:
        print(f"unknown subcommand: {sub}", file=sys.stderr)
        return 2
    try:
        return handler(args)
    except MissingToken as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (TerminalError, ExchangeError) as exc:
        print(str(exc), file=sys.stderr)
        if getattr(exc, "unauthorized", False):
            print(
                "Sign in again on the console and put the fresh token in the environment.",
                file=sys.stderr)
        return 1


# ---- shared helpers -------------------------------------------------------

def _config(args: argparse.Namespace) -> LiveAgentsConfig:
    cfg = load_config(_settings_reader())
    override = getattr(args, "token", None)
    if override:
        # One token on the command line serves whichever host this subcommand talks to.
        return LiveAgentsConfig(
            terminal_url=cfg.terminal_url, exchange_url=cfg.exchange_url,
            console_url=cfg.console_url, platform_url=cfg.platform_url,
            terminal_token=override, exchange_token=override)
    return cfg


def _settings_reader():
    """The settings reader ``register()`` captured, or None (defaults apply).

    The CLI is also reachable from a bare script and from tests, where no plugin manager has run;
    falling back to defaults keeps those paths working rather than requiring a config file.
    """
    from . import settings_reader

    return settings_reader()


def _terminal(args: argparse.Namespace) -> TerminalClient:
    cfg = _config(args)
    return TerminalClient(cfg.terminal_url, cfg.require_terminal_token())


def _exchange(args: argparse.Namespace) -> ExchangeClient:
    cfg = _config(args)
    return ExchangeClient(
        cfg.exchange_url, cfg.require_exchange_token(), platform_url=cfg.platform_url)


def _emit(args: argparse.Namespace, payload: Any, text: str) -> int:
    print(json.dumps(payload, indent=2, default=str) if getattr(args, "json", False) else text)
    return 0


def _money(value: Any) -> str:
    return str(value if value is not None else "0")


def _render_agents(agents) -> str:
    if not agents:
        return "No agents deployed yet."
    columns = (("name", 18), ("mode", 6), ("status", 10), ("market", 11),
               ("sub-account", 13), ("trades", 8), ("net pnl", 14))
    lines = ["".join(head.ljust(width) for head, width in columns) + "max dd"]
    for agent in agents:
        metrics = agent.get("metrics") or {}
        lines.append(
            str(agent.get("name", "")).ljust(18)
            + str(agent.get("mode") or "live").ljust(6)
            + str(agent.get("status", "")).ljust(10)
            + str(agent.get("market", "")).ljust(11)
            + f"#{agent.get('accountId', '')}".ljust(13)
            + str(metrics.get("trades", 0)).ljust(8)
            + _money(metrics.get("netPnl")).ljust(14)
            + _money(metrics.get("maxDrawdown")))
        if agent.get("lastError"):
            lines.append(f"  {agent['lastError']}")
    return "\n".join(lines)


def _stream_to_stdout(events: Iterator[Dict[str, Any]], *, as_json: bool) -> int:
    """Print a build/deploy stream as it arrives; return an exit code from its last line.

    The stream's own ``done``/``error`` line is what says finishing apart from being cut off
    halfway, so it decides the exit code rather than the HTTP status that opened it.
    """
    outcome = 1
    saw_terminal_line = False
    for event in events:
        if as_json:
            print(json.dumps(event, default=str), flush=True)
        else:
            rendered = _render_event(event)
            if rendered:
                print(rendered, flush=True)
        if event.get("error"):
            saw_terminal_line, outcome = True, 1
        elif event.get("done"):
            saw_terminal_line = True
            code = event.get("code")
            outcome = 0 if code in (0, None) else 1
    if not saw_terminal_line:
        print(
            "The stream ended without saying whether it finished. Check `hermes liveagents agents` "
            "before running it again — a repeated deploy is a second agent.", file=sys.stderr)
        return 1
    return outcome


def _render_event(event: Dict[str, Any]) -> str:
    """One line of a stream as text. Claude's own events are summarised, not replayed verbatim."""
    if event.get("error"):
        return f"error: {event['error']}"
    if event.get("done"):
        code = event.get("code")
        return "done." if code in (0, None) else f"failed (exit {code})."
    if event.get("type") == "claude":
        inner = event.get("event") or {}
        kind = inner.get("type") or inner.get("subtype") or "event"
        return f"claude: {kind}"
    text = str(event.get("text") or "").rstrip()
    return text


# ---- workspace ------------------------------------------------------------

def _cmd_whoami(args: argparse.Namespace) -> int:
    me = _terminal(args).whoami()
    ready = me.get("sharedCredentialReady")
    lines = [f"account: {me.get('wallet') or me.get('user_id') or 'unknown'}"]
    lines.append(f"admin: {'yes' if me.get('isAdmin') else 'no'}")
    lines.append(
        "claude: signed in" if ready else
        "claude: NOT signed in - nothing will build until an admin sets the shared credential")
    lines.extend(_credential_lines(me))
    return _emit(args, me, "\n".join(lines))


def _credential_lines(me: Dict[str, Any]) -> List[str]:
    """What kind of credential is calling, and how long it has left.

    A working setup and one that is about to break look identical from the outside, which is the
    whole problem this reports on. A browser session answers every call correctly right up to the
    minute it stops, and the failure then lands in the middle of a build rather than at the start
    of one. So the kind is printed always, and the remaining life whenever it is knowable.
    """
    kind = me.get("credential")
    if kind == "key":
        return [f"credential: workspace key {me.get('keyId') or ''}".rstrip()]
    if kind is None:
        # An older workspace that does not report this. Nothing useful to say, and a guess here
        # would be worse than silence.
        return []

    expires = me.get("expiresAt")
    left = ""
    if isinstance(expires, (int, float)) and expires > 0:
        minutes = int((expires / 1000 - time.time()) // 60)
        left = f", {minutes} minutes left" if minutes > 0 else ", expired"

    return [
        f"credential: browser session ({kind}){left}",
        "  This is a session, not a configured credential: it ends when you sign out and",
        "  within the hour regardless. For anything unattended create a workspace key at the",
        "  console under Connect Claude Code.",
    ]


def _cmd_launch(args: argparse.Namespace) -> int:
    """Print a URL that opens the workspace's own terminal already signed in.

    The token travels in the URL **fragment**, which never reaches a server and never appears in a
    Referer; that is the whole reason a credential may be passed this way at all. Agent Terminal
    reads it, verifies it and makes it that origin's cookie.

    ``--as`` carries a tag for whoever this session is signed in as. Agent Terminal remembers the
    last tag it saw, and a changed one means a different person at the same browser, so the old
    session goes with them. Without it, a shared browser can open the terminal on the previous
    person's workspace.
    """
    from urllib.parse import quote

    cfg = _config(args)
    token = cfg.require_terminal_token()
    fragment = f"sso={quote(token, safe='')}"
    if args.as_tag:
        fragment += f"&as={quote(args.as_tag, safe='')}"
    url = f"{cfg.terminal_url}/#{fragment}"
    # The URL carries a live credential, so it is the answer and never a log line.
    return _emit(args, {"url": url, "terminal_url": cfg.terminal_url}, url)


def _cmd_kinds(args: argparse.Namespace) -> int:
    payload = _terminal(args).kinds()
    kinds = payload.get("kinds") or []
    lines = [f"{k.get('id', ''):24}{k.get('label', '')}" for k in kinds] or ["(none offered)"]
    if payload.get("claudeReady") is False:
        lines.append("")
        lines.append("Claude is not signed in for this workspace, so a build would fail.")
    return _emit(args, payload, "\n".join(lines))


def _cmd_build(args: argparse.Namespace) -> int:
    client = _terminal(args)
    return _stream_to_stdout(
        client.build(
            idea=args.idea, market=args.market, kind=args.kind, name=args.name,
            description=args.description, interval_seconds=args.interval),
        as_json=args.json)


def _cmd_publish(args: argparse.Namespace) -> int:
    cfg = _config(args)
    client = TerminalClient(cfg.terminal_url, cfg.require_terminal_token())
    # A live deploy creates a sub-account in the holder's name, and the terminal holds no exchange
    # token for anybody, so ours travels with this one request.
    exchange_token = args.exchange_token or cfg.exchange_token
    if args.mode == "live" and not exchange_token:
        print(
            f"A live deploy creates a sub-account on the exchange, which needs your own session. "
            f"Set {EXCHANGE_TOKEN_ENV} or pass --exchange-token. Demo mode needs neither.",
            file=sys.stderr)
        return 2
    return _stream_to_stdout(
        client.deploy(
            name=args.name, market=args.market, mode=args.mode, exchange_token=exchange_token),
        as_json=args.json)


def _cmd_backtest(args: argparse.Namespace) -> int:
    """Replay a strategy and report the run the workspace saved.

    The workspace reads parameter overrides from ``set`` and returns the whole saved artifact under
    ``run``; its numbers live in ``run.summary``. Both were verified against the container's own
    handler, because a field it does not read is an override that is silently ignored.
    """
    request: Dict[str, Any] = {"agent": args.agent}
    for key, value in (
        ("market", args.market), ("interval", args.interval), ("dataset", args.dataset),
        ("from", args.date_from), ("to", args.date_to),
        ("fee", args.fee), ("slippage", args.slippage), ("equity", args.equity),
    ):
        if value:
            request[key] = value
    if args.days:
        request["days"] = args.days
    if args.param:
        overrides: Dict[str, str] = {}
        for raw in args.param:
            name, sep, value = raw.partition("=")
            if not sep:
                print(f"--param wants NAME=VALUE, got {raw!r}", file=sys.stderr)
                return 2
            overrides[name.strip()] = value.strip()
        request["set"] = overrides

    payload = _terminal(args).backtest(request)
    run = payload.get("run") or {}
    return _emit(args, payload, _render_run(run, args.agent))


def _render_run(run: Dict[str, Any], fallback_agent: str) -> str:
    """A finished run, read in the order that keeps a backtest honest.

    Net P&L first because it is the headline and the win rate is the most flattering number
    available; fees against gross next, because gross profit smaller than fees is a losing
    strategy whatever the win rate looks like; and the run id last, because a result nobody can
    identify cannot be checked by anyone, including its author.
    """
    summary = run.get("summary") or {}
    if not run:
        return "The workspace returned no run. --json shows everything it sent."

    period = run.get("days")
    window = f"{run.get('from')} → {run.get('to')}" if run.get("from") else (
        f"{period} days" if period else "the workspace's default window")
    lines = [
        f"{run.get('agent') or fallback_agent} on {run.get('market') or '(unstated)'} "
        f"at {run.get('interval') or '(unstated)'} over {window}"
    ]
    ordered = (
        ("net P&L", "netPnl"), ("fees paid", "feesPaid"), ("return %", "returnPct"),
        ("max drawdown", "maxDrawdown"), ("max drawdown %", "maxDrawdownPct"),
        ("trades", "trades"), ("win rate", "winRate"), ("profit factor", "profitFactor"),
        ("sharpe", "sharpe"), ("sortino", "sortino"),
    )
    for label, key in ordered:
        if key in summary:
            value = summary[key]
            # A null Sharpe means too few samples to compute one, not an unmeasured number.
            shown = "n/a (too few samples)" if value is None else value
            lines.append(f"  {label}: {shown}")

    trades = summary.get("trades")
    if isinstance(trades, (int, float)) and trades < 30:
        lines.append(
            f"  note: {trades} trades is too few to be significant; treat every ratio above as "
            "indicative at best.")
    if run.get("barCount") is not None:
        lines.append(f"  bars: {run['barCount']}")
    if run.get("dataset"):
        lines.append(f"  dataset: {run['dataset']}")
    if run.get("id"):
        lines.append(f"  saved as: {run['id']} — quote this when reporting the result")
    return "\n".join(lines)


def _cmd_backtests(args: argparse.Namespace) -> int:
    """The saved runs, newest first, as the workspace lists them."""
    payload = _terminal(args).backtests()
    runs = payload.get("runs") or []
    if not runs:
        return _emit(args, payload, "No saved runs yet.")
    lines = []
    for run in runs:
        summary = run.get("summary") or {}
        lines.append(
            f"{str(run.get('file') or run.get('id') or '?').ljust(40)}"
            f"{str(run.get('strategy') or '').ljust(16)}"
            f"{str(run.get('market') or '').ljust(11)}"
            f"{str(run.get('interval') or '').ljust(6)}"
            f"net {_money(summary.get('netPnl'))}")
    return _emit(args, payload, "\n".join(lines))


def _cmd_backtest_read(args: argparse.Namespace) -> int:
    """One saved run. Text mode summarises it; ``--json`` carries the artifact in full."""
    payload = _terminal(args).backtest_read(args.file)
    return _emit(args, payload, _render_run(payload.get("run") or {}, args.file))


# ---- exchange -------------------------------------------------------------

def _cmd_agents(args: argparse.Namespace) -> int:
    agents = _exchange(args).agents()
    return _emit(args, {"agents": agents}, _render_agents(agents))


def _cmd_logs(args: argparse.Namespace) -> int:
    client = _exchange(args)
    agent = client.find(args.name)
    payload = client.logs(str(agent.get("id")))
    header = (
        f"{agent.get('name')}: {payload.get('status') or agent.get('status')} "
        f"({agent.get('mode') or 'live'}), sub-account #{agent.get('accountId')}, "
        f"last seen {agent.get('lastSeenAt') or 'never'}")
    lines = [header]
    if agent.get("lastError"):
        lines.append(f"last error: {agent['lastError']}")
    lines.append("---")
    lines.extend(str(line) for line in (payload.get("logs") or []))
    if not payload.get("logs"):
        lines.append("(no output yet)")
        lines.append("")
        lines.append(
            "A deployed agent must keep running: a script that finishes its work and returns is "
            "treated as a crash. It needs a loop.")
    return _emit(args, {"agent": agent, **payload}, "\n".join(lines))


def _cmd_source(args: argparse.Namespace) -> int:
    client = _exchange(args)
    agent = client.find(args.name)
    payload = client.source(str(agent.get("id")))
    return _emit(args, payload, str(payload.get("source") or "(the exchange kept no source)"))


def _cmd_start(args: argparse.Namespace) -> int:
    client = _exchange(args)
    agent = client.find(args.name)
    if agent.get("status") in ("running", "starting"):
        return _emit(args, agent, f"{agent.get('name')} is already {agent.get('status')}.")
    fresh = client.start(str(agent.get("id"))) or agent
    return _emit(args, fresh, (
        f"{fresh.get('name')} is {fresh.get('status')} again on {fresh.get('market')} "
        f"({fresh.get('mode')}).\n"
        f"  sub-account #{fresh.get('accountId')}, equity {_money(fresh.get('equity'))}\n"
        "It runs the code it was deployed with. Redeploy the file to change that."))


def _cmd_stop(args: argparse.Namespace) -> int:
    client = _exchange(args)
    agent = client.find(args.name)
    result = client.stop(str(agent.get("id")))
    text = (
        f"Stopped {agent.get('name')}. Its sub-account #{agent.get('accountId')} and its funds "
        "are untouched.")
    if result.get("runnerStopped") is False:
        text += "\nThe container did not confirm; its token is revoked either way, so it cannot trade."
    return _emit(args, result, text)


# How long to watch for the money, and how often to look.
_FUND_WAIT_SECONDS = 150
_FUND_POLL_SECONDS = 5


def _cmd_fund_agent(args: argparse.Namespace) -> int:
    """Ask for an agent to be funded, then say whether the money arrived.

    Two facts, and only the second is what anybody wanted: that the request was recorded, and that
    the sub-account now holds something. The equity comes from the exchange, so what is reported
    is the transfer having landed rather than this command's opinion of how it went.
    """
    client = _exchange(args)
    agents = client.agents()
    if not agents:
        print("Nothing is deployed, so there is nothing to fund.", file=sys.stderr)
        return 2

    if args.name:
        agent = client.find(args.name)
    else:
        # "Fund the agent I just deployed", which is the moment this is for.
        agent = sorted(agents, key=lambda a: str(a.get("createdAt") or ""), reverse=True)[0]

    if args.amount:
        try:
            if float(args.amount) <= 0:
                raise ValueError
        except ValueError:
            print(f"--amount {args.amount} is not a positive number.", file=sys.stderr)
            return 2

    before = _as_float(agent.get("equity"))
    answer = client.request_funding(str(agent.get("id")), amount=args.amount, note=args.note)
    request = answer.get("request") or {}

    lines = [
        f"Asked the owner's console to fund {agent.get('name')}.",
        f"  sub-account  #{agent.get('accountId')}",
        f"  market       {agent.get('market')}",
        f"  holds        {_money(agent.get('equity'))}",
    ]
    if args.amount:
        lines.append(f"  suggested    {args.amount} {request.get('asset') or 'USDT'}")
    lines.append("")
    lines.append(
        "The funding dialog is opening in their console: it shows what this agent holds and what\n"
        "they have free, and the amount is theirs to type. Nothing moves until they press Deposit\n"
        "there - this process cannot and does not move it. With no console tab open the request\n"
        "waits, and lapses fifteen minutes after it was raised.")

    if not args.wait:
        return _emit(args, answer, "\n".join(lines))

    print("\n".join(lines))
    deadline = time.time() + _FUND_WAIT_SECONDS
    waiting = False
    while time.time() < deadline:
        time.sleep(_FUND_POLL_SECONDS)
        try:
            fresh = next(
                (a for a in client.agents() if str(a.get("id")) == str(agent.get("id"))), None)
        except ExchangeError:
            continue  # A blip while waiting is not an answer either way.
        now = _as_float((fresh or {}).get("equity"))
        if now > before:
            text = (
                f"{agent.get('name')} now holds {_money((fresh or {}).get('equity'))}, up from "
                f"{_money(before)}.\nIt can open a position on its next tick.")
            if waiting:
                print("")
            return _emit(args, {"agent": fresh, "request": request, "funded": True}, text)
        if not waiting:
            sys.stdout.write("Waiting for the transfer")
            waiting = True
        sys.stdout.write(".")
        sys.stdout.flush()

    if waiting:
        print("")
    return _emit(
        args,
        {"agent": agent, "request": request, "funded": False},
        "Nothing has arrived yet, which is not a failure - the dialog is waiting for them.\n"
        "Do not raise a second request; this one is still live.")


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cmd_redeploy(args: argparse.Namespace) -> int:
    try:
        source = _read_text(args.file)
    except OSError as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    params: Optional[Dict[str, Any]] = None
    params_path = args.params or _sibling_params(args.file)
    if params_path and os.path.exists(params_path):
        try:
            params = json.loads(_read_text(params_path))
        except (OSError, ValueError) as exc:
            print(f"Cannot read {params_path}: {exc}", file=sys.stderr)
            return 2
    elif args.params:
        print(f"No such params file: {args.params}", file=sys.stderr)
        return 2

    client = _exchange(args)
    agent = client.find(args.name)
    fresh = client.redeploy(
        str(agent.get("id")), source=source, params=params, market=args.market, mode=args.mode)
    text = (
        f"Redeployed {fresh.get('name') or agent.get('name')} from {args.file} "
        f"({len(source.encode('utf-8'))} bytes); it is {fresh.get('status') or 'starting'} on "
        f"{fresh.get('market') or agent.get('market')}.\n"
        f"  sub-account #{fresh.get('accountId') or agent.get('accountId')} kept, so no balance is stranded.")
    return _emit(args, fresh, text)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _sibling_params(file: str) -> str:
    """``agents/momentum.mjs`` -> ``agents/momentum.params.json``, the workspace's own convention."""
    stem, _, _ext = file.rpartition(".")
    return f"{stem}.params.json" if stem else ""


_COMMANDS = {
    "whoami": _cmd_whoami,
    "launch": _cmd_launch,
    "kinds": _cmd_kinds,
    "build": _cmd_build,
    "publish": _cmd_publish,
    "backtest": _cmd_backtest,
    "backtests": _cmd_backtests,
    "backtest-read": _cmd_backtest_read,
    "agents": _cmd_agents,
    "logs": _cmd_logs,
    "source": _cmd_source,
    "start": _cmd_start,
    "stop": _cmd_stop,
    "fund-agent": _cmd_fund_agent,
    "redeploy": _cmd_redeploy,
}
