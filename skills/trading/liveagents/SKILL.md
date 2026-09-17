---
name: liveagents
description: "Trade on liveagents.org: agents, deploys, runs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Agents, Exchange, Backtesting, Deployment]
    related_skills:
      - create-new-trading-agent
      - deploy-agent-live
      - fund-agent
      - monitor-agent
      - backtest-agent
---

# LiveAgents Skill

Create, backtest, deploy and supervise trading agents on the LiveAgents platform without leaving
Parabolic. This is the hub: it explains how the platform is put together, what each command does, and
how to read the numbers it gives back. The individual commands do the work.

It does not implement anything itself. Agents are written and replayed in the caller's Agent
Terminal workspace and run on the exchange, so there is one idea of what an agent is rather than
one per console.

## When to Use

Load this when you need the whole picture: which host answers which question, what a mode or a
sub-account means, or why a metric says less than it appears to. For a single operation, invoke
the command for it instead — `/create-new-trading-agent`, `/backtest-agent`, `/deploy-agent-live`,
`/monitor-agent`, `/diagnose-agent` and the rest, which are the same names Agent Terminal uses.

## Prerequisites

The `liveagents` plugin supplies `parabolic liveagents`, which every command here calls through
`terminal`. Two credentials, both from the environment:

| Variable | Reaches | Where it comes from |
|---|---|---|
| `LIVEAGENTS_TERMINAL_TOKEN` | the Agent Terminal workspace | a **workspace key**, created at the console under *Connect Claude Code -> Workspace keys*. Begins `lat_` |
| `LIVEAGENTS_API_TOKEN` | the exchange | the console's `la_dex_token`, a session the exchange minted. Lasts days |

**Never tell somebody to copy `la_terminal_token` out of browser storage.** It looks like the
value that belongs in the first row and is not one: it is the Privy access token the console
signed in with, renewed while a tab is open and good for an hour by itself. A machine configured
from it works until roughly lunchtime and then answers 401 forever, and re-copying it produces
the same result. A workspace key is the credential for anything that is not a browser - it is
created deliberately, survives signing out, and is revoked by name from the same panel.

Never go looking for a Privy identity token either: it is issued only when that setting is on for
the app, and on liveagents.org it is not.

Addresses are settings, not credentials: `plugins.entries.liveagents.settings.terminal_url`,
`.exchange_url` and `.console_url` in `config.yaml`.

Check both before promising anything:

```bash
parabolic liveagents whoami      # the workspace, and whether Claude is signed in for it
parabolic liveagents agents      # the exchange, and what is deployed
```

`whoami` reporting Claude as not signed in means no build will work, whatever else looks healthy.
Say that immediately rather than after a two-minute wait.

## How to Run

Read `references/platform.md` for how the pieces fit together and what the words mean, and
`references/cli.md` for every subcommand with its arguments. Both are short and worth reading
fully before a first deploy.

## Quick Reference

| Intent | Command |
|---|---|
| Open the workspace's own terminal, signed in | `parabolic liveagents launch` |
| Build one, end to end | `/create-new-trading-agent` |
| Build a specific kind | `/create-new-news-agent`, `/create-new-rule-based-agent`, `/create-new-self-learning-agent` |
| Replay over history | `/backtest-agent` (or `/backtest`) |
| Test whether settings survive | `/walk-forward` |
| Improve one that disappoints | `/optimise-agent` |
| Deploy without risk | `/deploy-agent-demo` |
| Deploy for real | `/deploy-agent-live` |
| Change the code of a live one | `/redeploy-agent` |
| Lifecycle | `/start-agent`, `/stop-agent` |
| See how it is doing | `/monitor-agent` |
| Find out why it will not run | `/diagnose-agent` |

## Procedure

The path that works, in order. Skipping a step does not save time; it moves the discovery later.

1. **Check the account.** `parabolic liveagents whoami` and `parabolic liveagents agents`. A workspace
   without a Claude credential cannot build; an exchange account without collateral cannot trade.
2. **Build in the workspace.** One of the `create-new-*` commands. The agent's code lands in the
   caller's workspace, not here.
3. **Replay it.** `/backtest-agent`, then `/walk-forward` before believing any tuning. A backtest
   over days can find a broken strategy and cannot judge a working one.
4. **Deploy demo first.** `/deploy-agent-demo` runs it for real against live data while the
   exchange refuses every order. It is the only way to see the live path without risk.
5. **Deploy live.** `/deploy-agent-live`. A new sub-account is empty, so funds have to be moved to
   it before the agent can open anything.
6. **Watch it.** `/monitor-agent`, and `/diagnose-agent` the moment a status reads `failed`.

## Pitfalls

- **A deployed agent must keep running.** A strategy that finishes its work and returns is treated
  as a crash. This is the most common reason an agent will not start, by a wide margin.
- **Net P&L is realised only.** Money moved into a sub-account is not performance, and an agent
  sitting on a large open loss shows no drawdown from it until the position closes.
- **Sharpe under about twenty trades says very little.** Quote it with that caveat or not at all.
- **A stale heartbeat means it stopped reporting.** The agent is not running, whatever its last
  status said.
- **Demo is not a simulation.** It is the real path with the orders refused, so a demo agent still
  proves the deploy, the loop and the data; it proves nothing about fills.
- **The risk envelope is never tunable.** A supervisor may move declared parameters inside ranges
  a person set. An agent that can widen its own limits has no limits.

## Verification

After a deploy, `parabolic liveagents agents` shows the new agent with a status and a sub-account
number, and `parabolic liveagents logs <name>` shows its container talking. An agent that appears in
the list but logs nothing has not started; go to `/diagnose-agent` rather than waiting.
