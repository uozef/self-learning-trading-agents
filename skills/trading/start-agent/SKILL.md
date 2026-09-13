---
name: start-agent
description: "Start a stopped agent from its deployed code."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Lifecycle, Agents]
    related_skills: [liveagents, stop-agent, redeploy-agent, monitor-agent]
---

# Start Agent Skill

Start a stopped agent. It runs the code it was deployed with, not whatever a file says now, and it
is issued a fresh token so the one it held while stopped stays dead.

## When to Use

To resume an agent that was stopped deliberately, or one that stopped itself on a risk limit and
whose situation has changed.

## Prerequisites

`LIVEAGENTS_API_TOKEN`.

## How to Run

```bash
parabolic liveagents start <name>
```

`<name>` matches an agent's name or its id; an unknown one lists what does exist.

## Quick Reference

| Step | Command |
|---|---|
| Find the stopped ones | `parabolic liveagents agents` |
| Start it | `parabolic liveagents start <name>` |
| Confirm it is trading | `parabolic liveagents logs <name>` |

## Procedure

1. **If no name was given**, list the agents and ask which of the stopped ones to start.
2. **Start it.**
3. **Report its mode, market, sub-account and equity.** An agent already running or starting is
   said so rather than started twice.

## Pitfalls

- **Starting does not pick up edits.** It runs the deployed code. To ship a change use
  `/redeploy-agent`, which keeps the sub-account.
- **An agent that stopped on a risk limit will stop again** if nothing about the situation changed.
  Say what would have to be different before restarting it.
- **Zero equity means it cannot open anything.** Starting it is not the fix; funding is.

## Verification

`parabolic liveagents agents` shows it running, and its log shows the strategy talking within a few
minutes. Running with a silent log means it started and crashed: go to `/diagnose-agent`.
