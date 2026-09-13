---
name: stop-agent
description: "Stop a running agent and revoke its trading token."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Lifecycle, Agents, Risk]
    related_skills: [liveagents, start-agent, monitor-agent, diagnose-agent]
---

# Stop Agent Skill

Stop a running agent. This revokes its token and shuts its container down, so it places no further
orders.

What it does **not** do is worth being exact about, because it is easy to assume otherwise.

## When to Use

To halt an agent's trading. If the point is to get out of the market, stopping alone does not do
that — see Pitfalls.

## Prerequisites

`LIVEAGENTS_API_TOKEN`.

## How to Run

```bash
parabolic liveagents stop <name>
```

## Quick Reference

| Step | Command |
|---|---|
| Find it | `parabolic liveagents agents` |
| Stop it | `parabolic liveagents stop <name>` |

## Procedure

1. **If no name was given**, list the agents and ask which one.
2. **Stop it.**
3. **Say what stopping did and did not do**, in plain terms:
   - It revoked the agent's token and shut the container down, so no further orders.
   - It did **not** close open positions and did **not** move money.
   - The sub-account keeps its balance and its positions, which stay exposed to the market until
     something closes them.

## Pitfalls

- **Stopping is not flattening.** An agent holding a position when it stops leaves that position
  open and exposed. If getting out of the market was the point, say so and offer to close the
  positions.
- **A container that misses its shutdown still cannot trade.** Revoking the token is what stops
  the trading; stopping the container is tidying up afterwards. So a stop that reports the
  container did not confirm has still stopped the trading.

## Verification

`parabolic liveagents agents` shows it stopped. If it still holds a position, say so in the same
breath: a stopped agent with an open position is the state people most often misread as safe.
