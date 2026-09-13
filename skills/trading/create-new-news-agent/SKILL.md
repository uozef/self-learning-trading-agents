---
name: create-new-news-agent
description: "Build an agent that trades on events, not chart shape."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Agents, News, Events, Feeds]
    related_skills: [liveagents, create-new-trading-agent, backtest-agent, deploy-agent-demo]
---

# Create New News Agent Skill

Build an agent that reacts to something happening rather than to the shape of the chart. The first
question is not the strategy, it is what the agent can actually read, because that decides what
kind of agent this is.

The code is written in the caller's Agent Terminal workspace from the brief assembled here.

## When to Use

When the user wants to trade events, or when a market has no usable tendency and a chart-reading
agent would be a coin flip paying fees. An event agent does not depend on the chart having a
leaning, which is what makes it a reasonable answer there.

## Prerequisites

`LIVEAGENTS_TERMINAL_TOKEN`; the `liveagents` skill for the platform reference. What feeds the
deployment reads is published by the platform and registered once by an admin, so settle it
before the interview rather than after.

## How to Run

Establish the data source first, interview second, build third. Getting that order wrong produces
an agent designed around a feed that turns out to be silent.

## Quick Reference

| Stage | Command |
|---|---|
| Build | `parabolic liveagents build --kind news --name … --market … --idea … --description …` |
| Replay | `/backtest-agent <name>` |
| Deploy | `/deploy-agent-demo <name>` then `/deploy-agent-live <name>` |

## Procedure

1. **Find out what it can read.** Ask the user which of these they have, and put the answer in the
   agent's own brief so it survives into the comments:

   - **A registered feed, on.** Real headlines tagged with the assets they concern, with no key to
     paste. Read what it actually publishes about the market under consideration before designing
     anything around it: a feed that publishes twice a day cannot support an agent that reacts
     within minutes, and only reading it tells you that.
   - **A source of their own.** A URL returning JSON that they own or subscribe to. It takes
     precedence over the registered feeds.
   - **Nothing.** Say so plainly rather than building against a feed that will be silent.

2. **Be honest about the fallback.** With no feed, this kind detects events in the market itself:
   turnover far above its own recent baseline, which is often what news looks like from inside the
   order book. That is a real strategy and a useful one, but it is **not news** — it reacts to the
   market having already moved. Do not let the user believe they are trading headlines when they
   are trading volume. Ask which they want.

3. **Market.** Cost matters more than usual here: an event agent is flat most of the time, so it
   has few trades to spread its costs across. If a round trip costs more than the average bar
   moves, it will not work on that interval. The research table lives in the workspace; offer to
   open Agent Terminal rather than estimating it here.

4. **Interview.**

   1. **What counts as an event.** A keyword, an asset tag, a sentiment threshold, a turnover
      multiple of the recent baseline.
   2. **What it does when one fires**: direction, size, and for how long.
   3. **How long the reaction lasts.** An event agent that never exits is holding a position for a
      reason that stopped being true hours ago.
   4. **The risk envelope**: largest position, unrealised loss that stops it, daily realised loss,
      drawdown percent.

5. **Build it:**

   ```bash
   parabolic liveagents build --kind news --name "<name>" --market <SYMBOL> \
     --interval <seconds> --idea "<what event it trades>" \
     --description "<the feed or the turnover fallback; what counts as an event; the reaction and how long it lasts; the risk envelope>"
   ```

6. **Replay it** with `/backtest-agent`, knowing a replay judges the fallback better than the feed:
   history of headlines is not the same as history of candles. Say which of the two the result
   actually tested.

7. **Deploy** demo first, then live.

## Pitfalls

- **A silent feed looks exactly like a working agent with nothing to do.** Check the feed publishes
  before blaming the strategy.
- **The turnover fallback is not news.** Name it correctly in front of the user, every time.
- **Few trades means costs bite harder**, not less: there is less profit to spread them over.
- **An event with no expiry becomes a position with no thesis.** Insist on a duration.

## Verification

`parabolic liveagents logs <name>` shows what the agent saw each pass. An event agent that never
mentions an event is either reading nothing or has thresholds nothing reaches; both are worth
knowing before it is left running.
