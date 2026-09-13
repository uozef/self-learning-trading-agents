---
name: create-new-self-learning-agent
description: "Build an agent that retunes itself as it runs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Agents, Adaptive, Supervisor]
    related_skills: [liveagents, create-new-trading-agent, optimise-agent, monitor-agent]
---

# Create New Self Learning Agent Skill

Build an agent that measures what the market is doing and adapts to it. Two different things adapt
here, on different timescales, and confusing them leads to bad expectations.

The code is written in the caller's Agent Terminal workspace from the brief assembled here.

## When to Use

When a market has no stable tendency, where a fixed rule has no edge to fix on: this kind measures
whether moves are continuing or reversing and reads the same signal forwards or backwards
accordingly.

It is not an answer to an expensive market. Nothing tunes its way out of one where a round trip
costs more than the average bar moves.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`; the `liveagents` skill for the platform reference, which has the
supervisor's limits in full.

## How to Run

Say what "learning" means here before starting, interview for the ranges, then build.

**The strategy adapts every pass, by itself.** It measures the market and changes what it does.
That needs no supervisor, happens in a backtest too, and is just code.

**Its parameters adapt slowly, through a supervisor.** Once deployed, a Claude Code process in the
same container reads the fills, position, equity and the agent's own output every fifteen minutes,
moves the declared values and writes its reasoning to a journal.

Be equally clear about what the supervisor cannot do, because it is what makes this safe to run:

- It cannot change anything not declared. An undeclared name is refused, not created.
- It cannot move a value outside its range. Out of range is refused rather than clamped, because
  asking for it means it has misunderstood something.
- It cannot touch the risk envelope. Those are constants in the strategy.
- It cannot rewrite the code. Adaptation is parameters only.

This is not a model that learns. It is a careful reader making bounded adjustments and writing
down why.

## Quick Reference

| Stage | Command |
|---|---|
| Build | `parabolic liveagents build --kind self-learning --name … --market … --idea … --description …` |
| Replay | `/backtest-agent <name>` |
| Read what the supervisor did | `/monitor-agent <name>` |
| Deploy | `/deploy-agent-demo <name>` then `/deploy-agent-live <name>` |

## Procedure

1. **Market.** This kind suits a market with no clear leaning. Say that plainly, because it is the
   case for choosing it over a rule-based agent.

2. **Interview.**

   1. **The idea**, in one sentence.
   2. **What it should measure** to know which way to lean.
   3. **What should adapt, and between what limits.** This is the important question and deserves
      time. For each value: what it does, the smallest sane setting, the largest.
   4. **The risk envelope.** Constants, never tunable.

3. **Get the ranges right.** A range too wide lets the supervisor find a setting fitted to noise;
   too narrow and it cannot help. Both failures look like bad luck rather than a bad range, so
   decide them deliberately with the user rather than defaulting them.

4. **Build it**, with the tunables and their ranges spelled out in the brief:

   ```bash
   parabolic liveagents build --kind self-learning --name "<name>" --market <SYMBOL> \
     --interval <seconds> --idea "<the one-sentence idea>" \
     --description "<what it measures; tunables with min and max for each; the risk envelope as constants>"
   ```

5. **Replay it** with `/backtest-agent`. The strategy's own per-pass adaptation shows up in a
   backtest; the supervisor's does not, so a backtest result is the floor rather than the estimate.

6. **Deploy** demo first, then live. Afterwards `/monitor-agent` reads the journal, which is where
   the supervisor's reasoning is.

## Pitfalls

- **Do not let the user hear "it will learn to be profitable."** It makes bounded adjustments to
  declared parameters. A losing strategy with well-chosen ranges is still a losing strategy.
- **Ranges that include the current value at an extreme** give the supervisor one direction to
  move, which is not tuning.
- **Read the journal before overriding a parameter by hand**, so a working adjustment is not
  undone for looking unfamiliar.
- **The risk envelope stays a constant.** An agent that can widen its own limits has no limits.

## Verification

After a deploy, `parabolic liveagents logs <name>` should show the strategy talking within a few
minutes and the supervisor within the first fifteen. Silence from both means it never started; go
to `/diagnose-agent`.
