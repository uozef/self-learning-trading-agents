---
name: diagnose-agent
description: "Work out why an agent will not run, and fix it."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Debugging, Agents, Deployment]
    related_skills: [liveagents, redeploy-agent, monitor-agent, deploy-agent-demo]
---

# Diagnose Agent Skill

An agent is not running and the reason needs finding. This reads the exchange's own stored reason
and the container's output, lines them up against the code, and proposes the fix.

Most failures here are one of a small set of causes, listed below in roughly the order they
happen.

## When to Use

The moment an agent's status reads `failed`, or when it is listed as running and its log is
silent.

## Prerequisites

`LIVEAGENTS_API_TOKEN`.

## How to Run

```bash
parabolic liveagents agents
parabolic liveagents logs <name>
parabolic liveagents source <name>
```

The third is what the agent is actually running, which is not always what a local file says.

## Quick Reference

| Step | Command |
|---|---|
| Find the failing one | `parabolic liveagents agents` |
| The reason and the output | `parabolic liveagents logs <name>` |
| The code it runs | `parabolic liveagents source <name>` |
| Ship the fix | `/redeploy-agent <name> <file>` |

## Procedure

1. **List the agents** and find the failing one — the one named, or the one in error if only one
   is.
2. **Read its log.** That carries the exchange's own reason and the container's output.
3. **Read the source it is running** and line it up against what the log says.
4. **Say what went wrong in one or two sentences**, then fix it.

The usual causes:

- **Exited immediately.** A deployed agent must keep running. A script that finishes its work and
  returns is treated as a crash. It needs a loop, or a timer that never resolves. This is by far
  the most common cause.
- **An import that is not there.** A deployed agent has node's built-ins and the workspace library
  only. There is no package install in its container.
- **A crash on the first pass**, usually reading a field that does not exist on a response. The
  log shows the stack.
- **A demo agent's orders refused.** Not a fault: a demo agent's writes are meant to be refused.
  If it should trade, redeploy it live.
- **Orders rejected as too small or off-step.** Sizes must be multiples of the lot size and prices
  of the tick size; both go through the harness's rounding helper.
- **No collateral.** An unfunded sub-account cannot open a position. Say so rather than editing the
  strategy — the fix is funding, not code.

5. **When the cause is in the code**, edit the file with `patch`, say what changed and why, then
   `/redeploy-agent <name>`, which keeps the sub-account and its balance.

## Pitfalls

- **Do not edit the strategy for a funding problem.** An unfunded account produces order rejections
  that look like a code fault and are not.
- **Do not redeploy repeatedly hoping it catches.** Two failures in a row means reading the log.
- **Check the source the exchange holds, not only the local file.** They diverge whenever a
  redeploy was skipped, and diagnosing the wrong code wastes the whole pass.
- **A refused demo order is the design working.** Diagnosing it as a bug is the most common false
  positive here.

## Verification

After the fix, the agent's log shows the strategy talking within a few minutes and the status
leaves `failed`. If it fails identically, the diagnosis was wrong — go back to the log rather than
redeploying again.
