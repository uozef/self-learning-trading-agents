---
name: redeploy-agent
description: "Replace a deployed agent's code and start it again."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Deployment, Lifecycle, Agents]
    related_skills: [liveagents, diagnose-agent, optimise-agent, monitor-agent]
---

# Redeploy Agent Skill

Replace the code of an agent that already exists, and start it. It keeps its sub-account, its
balance and its open positions, and swaps the code.

It is the right tool for fixing a broken agent. Deploying under a new name instead would strand
the funds in the old account.

## When to Use

After fixing a crash found by `/diagnose-agent`, or shipping a change proved by
`/optimise-agent`. Any time the code should change and the money should stay where it is.

## Prerequisites

`LIVEAGENTS_API_TOKEN`, and the new source in a local file.

## How to Run

```bash
parabolic liveagents redeploy <name> <file>
```

A sibling declarations file is picked up automatically: `agents/momentum.mjs` brings
`agents/momentum.params.json` with it. Pass `--params` to point somewhere else, and `--market` or
`--mode` only if those should change too — left out, they stay as they were.

## Quick Reference

| Step | Command |
|---|---|
| Find it | `parabolic liveagents agents` |
| See what it runs now | `parabolic liveagents source <name>` |
| Redeploy | `parabolic liveagents redeploy <name> <file>` |
| Watch it start | `parabolic liveagents logs <name>` |

## Procedure

1. **If no name was given**, list the agents and ask which one.
2. **Work out which file to send.** If the user named one, use it; otherwise the file the agent was
   made from, asking when that is not obvious. `parabolic liveagents source <name>` shows what it is
   running now, which is the honest comparison.
3. **Check the file the way a deployment would**, with `read_file`: imports limited to node's
   built-ins and the workspace library, and a loop that keeps it alive.
4. **Say what changed and why**, in one sentence, before running it. The next review has to have
   something to work from.
5. **Redeploy.**
6. **Watch it actually start.** If it fails again, say so plainly rather than redeploying
   repeatedly.

## Pitfalls

- **A redeploy overwrites the supervisor's parameters** with whatever the declarations file says.
  For an agent with tunables, read what the supervisor has been doing first, so an adjustment that
  was working is not undone by a redeploy meant to fix something else.
- **Repeated redeploys are not a diagnosis.** Two failures in a row means reading the log, not
  sending the file again.
- **Open positions survive a redeploy.** New code inherits whatever the old code was holding, so
  say what the position is before swapping the logic that manages it.

## Verification

`parabolic liveagents source <name>` returns the new code and `parabolic liveagents agents` shows the
agent starting or running on the same sub-account number as before. A changed sub-account number
means a new agent was created rather than this one replaced.
