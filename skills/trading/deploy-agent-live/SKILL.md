---
name: deploy-agent-live
description: "Deploy an agent that trades on its own sub-account."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Deployment, Live, Agents]
    related_skills: [liveagents, deploy-agent-demo, fund-agent, monitor-agent, diagnose-agent, stop-agent]
---

# Deploy Agent Live Skill

Deploy a trading agent live. It gets a sub-account of its own, a token that can reach only that
account, and a container that keeps running after this session ends.

This one spends money, so it does not get rushed.

## When to Use

After a demo deploy the user is satisfied with, and after a backtest that was read honestly. Not
as the first deploy of a strategy nobody has watched run.

## Prerequisites

Both credentials. `LIVEAGENTS_TERMINAL_TOKEN` for the workspace, and `LIVEAGENTS_API_TOKEN` for
the exchange — creating a sub-account is an act on the exchange in the holder's name, and the
workspace holds no exchange token for anybody. The command refuses up front when it is missing
rather than failing mid-deploy.

## How to Run

```bash
parabolic liveagents publish <name> --market <SYMBOL> --mode live
```

It streams. The last line says whether it finished; **a stream that ends without one is not a
failure to retry** — check `parabolic liveagents agents` first, because a repeated live deploy is a
second funded agent.

## Quick Reference

| Step | Command |
|---|---|
| Read what it will do | `parabolic liveagents source <name>` |
| Deploy | `parabolic liveagents publish <name> --market <SYMBOL> --mode live` |
| Confirm | `parabolic liveagents agents` |
| Watch | `/monitor-agent <name>` |

## Procedure

1. **Choose the agent** as for a demo deployment: the one named, otherwise ask.

2. **Read the agent and say what it will do**, before deploying. What its signal is, how large a
   position it can take, and what stops it. **If it has no bound on position size or loss, say so
   and ask whether to continue.** Do not deploy an unbounded agent quietly.

3. **Deploy it** live.

4. **Report the sub-account number and its equity.** A new sub-account is empty, so if equity is
   zero say clearly that the agent cannot open a position until funds are moved to it. There is no
   faucet; funding is an operator action.

5. **Suggest `/monitor-agent <name>` as the next step**, and `/stop-agent` as the way out.

## Pitfalls

- **A new sub-account has no collateral and every order it sends is rejected.** Say this at deploy
  time rather than letting it surface as a rejected order.
- **Stopping does not close positions.** It revokes the token and shuts the container down; open
  positions stay exposed until something closes them.
- **Never retry a live deploy on silence.** Two agents on two funded sub-accounts is the worst
  outcome of this command.
- **A deployed agent must keep running.** A strategy that returns is treated as a crash.

## Verification

The agent appears in `parabolic liveagents agents` with mode `live`, a status and a sub-account
number, and its log shows the strategy talking within a few minutes. The agent trades its own
sub-account and never the master account, and it cannot move funds anywhere: transfers need a
wallet signature its container never sees.
