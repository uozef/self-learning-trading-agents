---
name: monitor-agent
description: "Report an agent's status, performance and output."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Monitoring, Metrics, Agents]
    related_skills: [liveagents, diagnose-agent, stop-agent, optimise-agent]
---

# Monitor Agent Skill

Report on a deployed agent: what it is doing, how it is doing, and what its container has been
saying.

Reading the numbers honestly rather than flatteringly is the point of this skill. Each of the
metrics below means something narrower than its name suggests.

## When to Use

Any time somebody asks how an agent is doing, and after every deploy.

## Prerequisites

`LIVEAGENTS_API_TOKEN`.

## How to Run

```bash
parabolic liveagents agents
parabolic liveagents logs <name>
```

The log is polled rather than streamed, because it lives in the agent's container and a socket
held open to it keeps that container from idling out.

## Quick Reference

| Intent | Command |
|---|---|
| The whole picture | `parabolic liveagents agents` |
| One agent's output | `parabolic liveagents logs <name>` |
| What code it runs | `parabolic liveagents source <name>` |

## Procedure

1. **Run the agent list** for the whole picture.
2. **If a name was given**, also read that agent's log.
3. **Summarise in a few lines**: mode, status, how long it has run, its sub-account, trades, net
   P&L and max drawdown, then anything notable in the log.

Read the numbers with these caveats attached, every time:

- **Net P&L is realised P&L, fees and funding only.** Money transferred into the sub-account is
  not performance and is not in it.
- **Max drawdown is the deepest peak-to-trough fall of realised P&L**, and it is realised: an
  agent sitting on a large open loss shows no drawdown from it until the position closes. Say so
  when there are open positions.
- **Sharpe is a plain reward-to-variability ratio over realised trade P&L**, not annualised. Under
  about twenty trades it says very little; say that instead of quoting it as though it meant
  something.
- **Net P&L includes fees and funding**, so it can be negative while the win rate looks good.
- **A stale heartbeat means the container stopped reporting.** The agent is not running, whatever
  its last status said.

## Pitfalls

- **Do not lead with the win rate.** It is the most flattering number available and the least
  informative.
- **A status of `running` with no recent log output is not running.** Trust the heartbeat over the
  status field.
- **An agent with no trades is not "doing fine".** It is either waiting correctly or never firing,
  and the log says which.

## Verification

The summary states mode, status, last-seen time, sub-account, trade count, net P&L and max
drawdown, each with the caveat that applies. If the agent looks stalled, `/diagnose-agent` is the
next step rather than a second look at the same list.
