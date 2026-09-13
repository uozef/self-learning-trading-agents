---
name: backtest
description: "Replay an agent over history: the short name."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Backtesting, Strategy]
    related_skills: [backtest-agent, liveagents, walk-forward]
---

# Backtest Skill

The same command as `/backtest-agent`, under the shorter name people reach for. It replays one of
the user's agents over history in their Agent Terminal workspace and reports the result.

There is one set of instructions and it lives in the other skill, because two copies of a
procedure drift apart and then the two names do different things.

## When to Use

Whenever `/backtest-agent` would be used. They are the same operation.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`.

## How to Run

Load the `backtest-agent` skill and follow it exactly, with whatever arguments were given here.
Do not improvise a shorter version: the parts most often skipped — the dataset handle, the bar
count, the order the numbers are read in — are the parts that keep a backtest honest.

## Quick Reference

| Intent | Command |
|---|---|
| The procedure | the `backtest-agent` skill |
| Replay | `parabolic liveagents backtest <agent> [window]` |

## Procedure

1. Load `backtest-agent`.
2. Follow it, passing through the arguments given to this command.

## Pitfalls

- **Do not answer from memory of what a backtest usually involves.** The market and period
  selection rules, and the way the result must be read, are specific and easy to soften.

## Verification

Whatever `backtest-agent` verifies. If that skill's five facts cannot be stated, the result is not
reportable.
