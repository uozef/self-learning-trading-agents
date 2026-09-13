---
name: optimise-agent
description: "Find what is wrong with an agent, then improve it."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Optimisation, Backtesting, Strategy]
    related_skills: [liveagents, backtest-agent, walk-forward, redeploy-agent, monitor-agent]
---

# Optimise Agent Skill

Review an agent and improve it, in that order. Most agents that lose money do not have a tuning
problem, and tuning past a broken premise just finds a setting that was lucky.

Work through the checks below in order and stop at the first one that is true.

## When to Use

When an agent disappoints and somebody wants it better. Also when a sweep has been proposed:
often the right answer is that the agent is in the wrong market, which no sweep fixes.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`, and `LIVEAGENTS_API_TOKEN` if the agent is deployed.

## How to Run

Ask what has already been tried before running anything. Saved runs answer in one query what
re-running a sweep answers in minutes, and they cover sessions nobody here was present for:

```bash
parabolic liveagents backtests
```

Two results are only comparable when the dataset handle matches. A better Sharpe on a different
window is not an improvement, it is a different question.

## Quick Reference

| Check | Command |
|---|---|
| What has been tried | `parabolic liveagents backtests` |
| Is it doing anything | `parabolic liveagents backtest agents/<file>.mjs --days 7` |
| One parameter, one window | `parabolic liveagents backtest agents/<file>.mjs --param <name>=<value> --from … --to …` |
| What it learned while live | `parabolic liveagents logs <name>` |
| Ship the change | `/redeploy-agent <name> <file>` |

## Procedure

1. **Is it in the right market at all?** If a round trip costs more than the average bar moves,
   **nothing fixes that by tuning**; offer a slower interval or a different market. A momentum
   agent on a mean-reverting market is backwards, and so is a fading agent on a trending one —
   move it or invert it, do not tune it.

   If either is true, stop here and say it plainly. It is the most valuable thing you can tell
   them and the finding people most often tune straight past.

2. **Is it doing anything?** Replay a week.

   - **No trades**: thresholds are wider than anything that happens. Lower them until it fires,
     then judge it.
   - **Trading every bar**: it is paying the spread continuously. Widen the entry band, or make
     the exit threshold tighter than the entry.
   - **Fees near or above gross profit**: it trades too often for its edge. Fewer, larger
     positions — not different averages.

3. **Is the result real, or was it one good week?** Split the history and read out how many
   stretches were profitable. Two of five is a coin flip. One jump and a flat line is a single
   lucky day wearing a strategy's clothes.

   **If it fails here, do not proceed to tuning.** Tuning something that only worked once produces
   something that only works once, more convincingly.

4. **Only now, tune it.** One parameter at a time, searching on one window and checking on a
   different one. Doing both on one window is how a setting that fits noise becomes a deployment.

   Read the *shape* of the response, which matters more than the winner:

   | Shape | What to do |
   |---|---|
   | a broad hill | the parameter has a real effect; the peak is safe to take |
   | a single spike among losses | the peak is noise; take a value from the flat part, even though it backtests worse |
   | flat everywhere | the parameter does nothing; remove it from the declarations so the supervisor stops spending attention on it |

   If a run reports a combination was already tried, believe it. Identical code, bars, settings and
   costs produce identical numbers, and re-running proves nothing.

5. **Check the envelope, not just the returns.** If the backtest drew down close to the agent's own
   limit, live it will breach it and stop — and a stopped agent earns nothing. Either widen the
   limit deliberately or reduce the size, and say which you are doing and why.

6. **If it is deployed, read what it already learned.** For an agent with declared tunables the
   supervisor has been adjusting it and writing down why. A parameter pinned at the edge of its
   range for days means the range is wrong, not the value; one it never moves is doing nothing.

   **Do not overwrite the supervisor's work without reading it.** A redeploy replaces the
   parameters with whatever is in the file, so an adjustment that was working can be undone by a
   redeploy meant to fix something else.

7. **Redeploy** with `/redeploy-agent`. It keeps the sub-account, its balance and any open
   positions, and replaces the code. Say what changed and why in one sentence, so the next review
   has something to work from.

## Pitfalls

- **A good sweep result is not a deploy decision.** The next question is `/walk-forward`: would
  these settings have held on data they were not chosen on? A parameter set picked on the same
  history it is judged on has not been tested, it has been fitted.
- **Comparing across datasets.** Without a matching handle the comparison is meaningless.
- **Be willing to conclude an agent should be archived rather than improved.** An idea that does
  not fit its market is not a tuning problem, and saying so is a better answer than a tenth sweep.

## Verification

State which numbered check the agent failed, what changed as a result, and on which window the
change was verified. If the answer is "it was tuned", the review was skipped.
