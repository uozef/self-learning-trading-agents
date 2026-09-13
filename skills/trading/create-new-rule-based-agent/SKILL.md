---
name: create-new-rule-based-agent
description: "Build an agent with fixed rules and no supervisor."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Agents, Rules, Strategy]
    related_skills: [liveagents, create-new-trading-agent, backtest-agent, walk-forward]
---

# Create New Rule Based Agent Skill

Build an agent that does exactly what it says and keeps doing it. The defining feature is an
absence: a strategy that declares no tunables gets no supervisor, so nothing adjusts it between
deployments.

The code is written in the caller's Agent Terminal workspace from the brief assembled here.

## When to Use

When testing one idea, or when the rule encodes something the user already believes and does not
want tuned away from. Say the reason for choosing it early:

- The code can be read, and what it will do is knowable from reading it.
- A result is attributable to the rules, not to something that changed itself overnight.
- Nothing drifts. If it is wrong it stays wrong until somebody fixes it, which is better than
  wrong in a way nobody can reconstruct.

If they want it to improve on its own, that is `/create-new-self-learning-agent`.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`; the `liveagents` skill for the platform reference. Confirm through
`terminal` that the workspace can build:

```bash
parabolic liveagents whoami
```

## How to Run

Interview first, then one build call, then test it harder than you would test an adaptive agent —
because nothing will tune this later, the backtest carries more weight here.

## Quick Reference

| Stage | Command |
|---|---|
| Build | `parabolic liveagents build --kind rule-based --name … --market … --idea … --description …` |
| Replay | `/backtest-agent <name>` |
| Prove the settings hold | `/walk-forward <name>` |
| Deploy | `/deploy-agent-demo <name>` then `/deploy-agent-live <name>` |

## Procedure

1. **Market.** A fading rule needs a mean-reverting market and a trend rule needs a trending one.
   On the wrong one it will lose steadily and look like a bug. The research table that measures
   which way a market leans lives in the workspace; if they want it first, say so and offer to
   open Agent Terminal rather than guessing at a leaning here.

2. **Interview.** Fixed rules mean every number is decided now. Offer a default for each.

   1. **The rule**, in one sentence: what is true when it enters, and what is true when it leaves.
   2. **The measurement** behind it: an average and a distance from it, a level, a range, a
      crossing.
   3. **Entry and exit thresholds.** Keep the exit tighter than the entry, or a price sitting on
      the line opens and closes every pass, paying fees both ways.
   4. **Size**: one number.
   5. **The risk envelope**: largest position, unrealised loss that stops it, daily realised loss,
      drawdown percent.

3. **Read the answers back as one sentence** of the form "it goes long when X, closes when Y, and
   stops entirely if Z". If that sentence is hard to write, the rule is not yet a rule.

4. **Build it**, and say in the brief that it must declare no tunables:

   ```bash
   parabolic liveagents build --kind rule-based --name "<name>" --market <SYMBOL> \
     --interval <seconds> --idea "<the rule in one sentence>" \
     --description "<measurement, thresholds, size, risk envelope. No tunables: this agent takes no supervisor.>"
   ```

5. **Test it harder than usual.** `/backtest-agent` over a week, then `/walk-forward` over a
   longer stretch. Report honestly: negative net P&L first, no-trades as too-wide rather than
   safe, an absent Sharpe as too few samples, and the fees line against the gross.

6. **Deploy** with `/deploy-agent-demo`, then `/deploy-agent-live`.

## Pitfalls

- **Do not let it acquire tunables.** A declarations file would attach a supervisor and destroy
  the one property this type exists for.
- **An exit threshold at or wider than the entry** churns fees on a price sitting on the line.
- **Keep every number a named constant.** In six weeks the constants are the only documentation.
- **No supervisor means no rescue.** A rule-based agent that stops working keeps not working until
  somebody redeploys it, so `/monitor-agent` matters more here, not less.

## Verification

`parabolic liveagents agents` lists it with a status; `parabolic liveagents source <name>` shows the code
it is actually running, which is the check that the workspace built the rule that was agreed.
