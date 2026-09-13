---
name: create-new-trading-agent
description: "Build a trading agent end to end, market to live."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Agents, Strategy, Deployment]
    related_skills: [liveagents, backtest-agent, deploy-agent-demo, deploy-agent-live, monitor-agent]
---

# Create New Trading Agent Skill

Build a new trading agent with the user, from choosing a market to watching it run. This is the
general path; it interviews the user here, hands a finished brief to their Agent Terminal
workspace, then replays and deploys what comes back.

It does not write the strategy in this session. The workspace owns what an agent is, so the code
is written there against the harness that will run it.

## When to Use

When somebody wants an agent and does not yet know which kind. If they already know, go straight
to the one that fits and skip this:

| They want | Command |
|---|---|
| Fixed rules that never change themselves | `/create-new-rule-based-agent` |
| Something that retunes itself as it runs | `/create-new-self-learning-agent` |
| Something reacting to events rather than the chart | `/create-new-news-agent` |

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`, and `LIVEAGENTS_API_TOKEN` for a live deploy. Load the `liveagents`
skill for the platform reference. Check the account first, through `terminal`:

```bash
parabolic liveagents whoami
parabolic liveagents kinds
```

If `whoami` reports Claude as not signed in for that workspace, stop and say so. Nothing will
build, and finding out after a two-minute wait is worse than being told now.

## How to Run

Work through the stages in order. Do not skip the measurement steps: an agent built without them
is a guess that costs money.

## Quick Reference

| Stage | Command |
|---|---|
| Templates available | `parabolic liveagents kinds` |
| Write the agent | `parabolic liveagents build --idea … --market … --kind … --name …` |
| Replay it | `/backtest-agent <name>` |
| Deploy, no risk | `/deploy-agent-demo <name>` |
| Deploy for real | `/deploy-agent-live <name>` |

## Procedure

1. **Choose the market.** Ask, and say what each is: a perpetual can go short and take leverage, a
   spot market cannot. The research table that ranks markets by round-trip cost against average
   bar movement lives in the workspace, not here — if they want it before choosing, say so and
   offer to open Agent Terminal. Do not invent numbers in its place.

2. **Interview, in small batches**, offering a sensible default each time so they can agree and
   move on.

   1. **The idea**, in one sentence. If they cannot say it in a sentence, help them find it before
      anything is built.
   2. **Direction**: long only, short only, or both. Long only is the only option on spot.
   3. **Entry**: what has to be true to open. Push for something checkable against candles — a
      crossing, a threshold, a level, a range break.
   4. **Exit**: what closes it. Ask about the target and the stop separately. An agent with an
      entry and no exit holds whatever it opened forever.
   5. **Sizing**: fixed, a fraction of equity, or scaled by conviction.
   6. **The risk envelope**: largest position, unrealised loss that stops it, daily realised loss,
      drawdown percent. Say plainly that these become constants no supervisor can touch, which is
      the point of them.
   7. **Whether anything should adapt.** If yes this is really
      `/create-new-self-learning-agent`; offer to switch.

3. **Summarise the answers back and get agreement** before building. The brief is what the
   workspace builds from, so a vague brief is a vague agent.

4. **Build it.** One call, and it streams for a minute or two:

   ```bash
   parabolic liveagents build --kind <kind> --name "<name>" --market <SYMBOL> \
     --interval <seconds> --idea "<the one-sentence idea>" --description "<entry, exit, sizing, risk envelope>"
   ```

   Put the whole interview in `--description`. The workspace's builder reads it; anything left out
   is something it has to guess.

5. **Replay it** with `/backtest-agent`, and report the result honestly. Negative net P&L is the
   headline — never lead with the win rate. No trades means the thresholds are too wide, which is
   not safety. Then `/walk-forward` before believing any setting.

6. **Deploy demo first**, always, unless they refuse: `/deploy-agent-demo`. Then `/deploy-agent-live`
   once they are satisfied with what the demo did.

7. **Monitor** with `/monitor-agent`, and `/diagnose-agent` the moment a status reads `failed`.

## Pitfalls

- **Never talk the user past a market with no tendency.** "Neither momentum nor mean-reverting" is
  the most common honest answer; both ideas are then coin flips paying fees. A different market, a
  slower interval, or an event-driven agent are the real options.
- **Gross profit smaller than fees is a losing strategy**, however good the win rate looks.
- **The best of ten settings on one stretch of history is not evidence.** Say so out loud.
- **A deployed agent must keep running.** A strategy that returns is treated as a crash.
- **A new sub-account is empty.** Nothing can open until funds are moved to it.

## Verification

`parabolic liveagents agents` shows the agent with a status and a sub-account number, and
`parabolic liveagents logs <name>` shows its container talking. Listed but silent means it never
started: go to `/diagnose-agent`.
