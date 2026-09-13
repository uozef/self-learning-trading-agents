---
name: deploy-agent-demo
description: "Deploy an agent whose orders the exchange refuses."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Deployment, Demo, Agents]
    related_skills: [liveagents, deploy-agent-live, monitor-agent, diagnose-agent]
---

# Deploy Agent Demo Skill

Deploy a trading agent in demo mode. It runs for real, in its own container, against live market
data, and the exchange refuses every order it sends.

Demo is enforced by the exchange rather than by the agent's own code: a demo agent's token is
refused on every write. That makes it safe to point at a strategy nobody has read closely yet.

## When to Use

Before every live deploy, unless the user refuses. It is the only way to exercise the real deploy,
the real loop and the real data path without risk.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`. An exchange session is not needed: demo creates no sub-account of
consequence and places nothing.

## How to Run

```bash
parabolic liveagents publish <name> --market <SYMBOL> --mode demo
```

It streams for a minute or two. The last line says whether it finished. **If the stream ends
without one, do not run it again** — check `parabolic liveagents agents` first, because a repeated
deploy is a second agent.

## Quick Reference

| Step | Command |
|---|---|
| See what the workspace holds | `parabolic liveagents agents` |
| Read the code first | `parabolic liveagents source <name>` |
| Deploy | `parabolic liveagents publish <name> --market <SYMBOL> --mode demo` |
| Watch it start | `parabolic liveagents logs <name>` |

## Procedure

1. **Work out which agent to deploy.** If the user named one, use it. Otherwise list what exists
   and ask; if exactly one is there, use it.

2. **Check the two things that stop a deployment**, before spending two minutes finding out:

   - It must import only node's built-ins and the workspace's own library. There is no package
     install in a deployed agent's container.
   - It must have a loop. A script that finishes its work and returns is treated as a crash, and
     this is the most common reason an agent will not start.

3. **Deploy it** in demo mode.

4. **Report the sub-account it was given**, and say plainly that nothing it decides will reach the
   book until it is redeployed with `/deploy-agent-live`.

5. **Watch it start** with `parabolic liveagents logs <name>`. A demo agent's orders being refused is
   the design working, not a fault.

## Pitfalls

- **Refused orders in a demo log are expected.** Do not diagnose them as a bug or "fix" them by
  going live.
- **Demo proves the deploy, the loop and the data path. It proves nothing about fills.** A demo
  that ran cleanly says nothing about slippage or whether the size was achievable.
- **A silent stream is not a failed deploy.** Check the agent list before retrying.

## Verification

`parabolic liveagents agents` shows the agent with mode `demo` and a status, and
`parabolic liveagents logs <name>` shows its container talking within a few minutes. Listed but
silent means it never started: go to `/diagnose-agent`.
