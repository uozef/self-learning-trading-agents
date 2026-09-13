---
name: walk-forward
description: "Choose settings on one period, judge them on the next."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Backtesting, Validation, Overfitting]
    related_skills: [liveagents, backtest-agent, optimise-agent]
---

# Walk Forward Skill

Test whether an agent's settings survive data they were not chosen on. A sweep finds the setting
that suited a stretch of history; that is not the setting that will suit the next one, and the gap
between the two is where most backtested strategies die.

This measures the gap instead of hoping it is small.

## When to Use

Before deploying anything whose parameters came from a sweep, and whenever a backtest result looks
good enough to act on. It is the harder and more honest version of the question `/backtest-agent`
answers.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`, and **years of history**. The exchange feed holds days: rolling a
train and test window through a fortnight produces five numbers that all mean "that fortnight".
If only the feed is available, say so plainly and offer a split-window backtest instead, which is
the honest version of this question on a short history.

Check the asset actually has the range before naming dates. A window that starts before the first
bar is a shorter window than the one that was asked for.

## How to Run

Each run is one `parabolic liveagents backtest` call with an explicit window and, for the test leg,
an explicit setting.

## Quick Reference

| Leg | Command |
|---|---|
| Train | `parabolic liveagents backtest agents/<file>.mjs --from <train from> --to <train to> --param <name>=<candidate>` |
| Test | `parabolic liveagents backtest agents/<file>.mjs --from <test from> --to <test to> --param <name>=<winner>` |

## Procedure

1. **Cut the history into windows.** Sensible defaults for crypto at five-minute bars: train
   twelve months, test three months, step three months — four windows over two years, each test
   period immediately after its own training period.

   Say the dates out loud before running anything:

   ```
   window 1   train 2022-01-01 → 2023-01-01   test 2023-01-01 → 2023-04-01
   window 2   train 2022-04-01 → 2023-04-01   test 2023-04-01 → 2023-07-01
   ```

   Rolling, not expanding, unless the user asks otherwise. An expanding window weights the distant
   past more heavily every step, and a market from four years ago is not the market being traded.

2. **Name the metric before looking at any table.** Sharpe or net P&L, decided once, for every
   window. Choosing it afterwards is choosing the window's winner twice.

3. **Choose on the training window only.** Run each candidate over the train period and take the
   best by the metric named in step 2.

4. **Judge it on the window that follows.** Run the winner, once, over the test period.

   **Never sweep on the test window.** The moment a parameter is chosen there it stops being out of
   sample and the whole exercise measures nothing. If a test period has already been evaluated
   several times, read that out: a test set consulted repeatedly has quietly become a training set,
   and the only fix is a period nobody has touched.

5. **Report the efficiency, not the returns.** For each window the number that matters is
   out-of-sample return divided by in-sample return.

   | Efficiency | What it means |
   |---|---|
   | near 1.0 | the parameters generalise; the good outcome, and rarer than people expect |
   | around 0.5 | half the edge was fitting; survivable if what is left still beats costs |
   | near 0 or negative | the search found noise and following it actively hurt |

   For the last case, say plainly that the strategy has not been shown to work and a better sweep
   will not change that.

6. **Read out how the chosen setting moved between windows.** A parameter landing on a different
   value every time has no stable optimum, which is a stronger finding than any individual result:
   the number is being fitted to whatever just happened.

7. **Finish with one recommendation and the reason.** Efficiency near 1 across windows, stable
   parameters and more than thirty trades in each test window is a case for deploying — at a size
   that survives the worst drawdown seen in any test window. Anything else: say what would have to
   be true to change the answer, which is usually a simpler strategy with fewer things to fit
   rather than a wider sweep.

## Pitfalls

- **A sweep on the test window ends the experiment.** There is no partial credit here.
- **Reusing a test period silently turns it into training data.** Track how many times it has been
  used and say so.
- **Efficiency near 1 on two windows is not "it generalises."** Report every window, including the
  ones that disagree.
- **Naming the metric after seeing the results** is the most common way this procedure is quietly
  spoiled.

## Verification

The summary names the agent, every window's dates, the metric chosen in advance, each window's
efficiency, how the parameter moved, and the dataset handle. "Two years of BTC" does not identify
any particular two years, so without the handle nobody can run this again.
