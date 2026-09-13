---
name: backtest-agent
description: "Replay an agent over history, with metrics read honestly."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Backtesting, Metrics, Strategy]
    related_skills: [liveagents, backtest, walk-forward, optimise-agent]
---

# Backtest Agent Skill

Replay one of the user's agents over history and say what actually happened. The replay runs in
their Agent Terminal workspace, against the same `decide` function that will trade live, so a
result here is about the code that would be deployed.

Reading the result honestly is most of this skill. A backtest is very easy to report
flatteringly.

## When to Use

Before any deploy, and after any change to a strategy. Also whenever somebody quotes a number
from a previous run without a dataset behind it.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`; the `liveagents` skill for the platform reference.

## How to Run

```bash
parabolic liveagents backtest agents/<file>.mjs --market <SYMBOL> --interval 5m \
  --from <date> --to <date>
```

The first argument is the strategy's **path inside the workspace**, not a deployed agent's
name. This replays a file; the exchange's agents are a different thing with different names.

Windows can be given three ways and they are not equivalent: `--days N` walks back from now,
`--from`/`--to` name real dates, and `--dataset hp_…` names an exact set of bars that will never
change. Use the third when one exists, because it is what makes a result comparable with the next
one.

## Quick Reference

| Intent | Command |
|---|---|
| Replay | `parabolic liveagents backtest agents/<file>.mjs [window]` |
| Override one tunable | `parabolic liveagents backtest agents/<file>.mjs --param name=value` |
| Change the cost assumptions | `… --fee <pct> --slippage <pct> --equity <amount>` |
| What has been run before | `parabolic liveagents backtests` |
| One saved run in full | `parabolic liveagents backtest-read <file>` |

## Procedure

1. **Find the agent.** If the user named one, use it. Otherwise `parabolic liveagents agents` and the
   workspace's own list, and ask which — do not guess, and do not make them remember a filename.

2. **Choose the market deliberately.** The agent's own market is the default. Two things decide
   whether another is better, and both matter: what a round trip costs against what the average
   bar moves, and how much checked history exists. A market with two days behind it cannot be
   judged however good it looks. Say which you picked and why, in one sentence, using numbers
   rather than adjectives.

3. **Choose a period the data can support.**

   - **Days** is a first look: is it alive, does it trade at all.
   - **A year** is the first length with more than one mood in it.
   - **Two to four years** is what makes a result worth something, because it contains at least
     one period that was nothing like the others.
   - Ask for a timeframe the window can carry. Three years of one-minute bars is over a million
     and the replay runs bar by bar. Coarser bars over a longer window beat fine bars over a
     fortnight.

4. **Run it**, then read back the dataset handle if the result carries one. The handle names those
   exact bars for ever, so it is what makes the number checkable. A Sharpe with no dataset behind
   it cannot be verified by anyone, including you.

   If the run reports the experiment was already recorded, that is not a failure: this exact code,
   on these exact bars, with these settings, has been run before and produced this. Say so and move
   to the question that has not been answered.

5. **Check what you actually got.** The run says how many bars it used. Fewer than asked for means
   a shorter result than the one requested; report the real period, never the intended one.

6. **Read the numbers in this order.**

   1. **Net P&L.** Negative goes first, always. Never open with the win rate.
   2. **Fees against gross.** Gross profit smaller than fees is a losing strategy however good the
      win rate looks.
   3. **Max drawdown**, as money and as percent.
   4. **Trades.** Under about thirty, say plainly that nothing here is significant.
   5. **Sharpe.** If it is absent, that means too few samples to compute one — not that it was not
      measured.

7. **Say what the shape of the result was, not only its total.** One jump and a flat line is a
   strategy whose whole result came from a single day, and it has not been shown to work. A curve
   that ends well after months below its peak is one nobody would have held, which is a real
   objection to deploying it rather than a detail. Many small wins and one catastrophe is a
   different strategy from a few large wins paying for many small losses, and the first is the one
   that eventually finds a loss it cannot pay for.

8. **Then test it against being wrong.** One result on one stretch is not evidence. Split the
   history and report how many stretches were profitable: two of five is a coin flip, and saying so
   is the whole point of running it. For settings specifically, `/walk-forward` asks the harder and
   more honest question; to improve the agent, `/optimise-agent`.

## Pitfalls

- **Never execute an agent file to inspect it.** An agent is code that places orders. Use
  `read_file`.
- **Do not pull a saved run's full JSON into the conversation.** It carries every bar the run was
  measured against and says nothing the report has not already said. `parabolic liveagents backtest-read`
  is for when a specific field is needed.
- **Incomplete coverage invalidates the period.** A strategy tuned on a window with gaps is tuned
  on the gaps.
- **Without a history service the only source is the exchange feed, which holds days.** A result
  from it is a smoke test, not evidence. Say which one you have.

## Verification

The report names the agent, the market, the real period, the bar count and the dataset handle when
there is one. If you cannot state all five, the result is not yet reportable.
