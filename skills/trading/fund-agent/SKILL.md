---
name: fund-agent
description: "Ask the owner to fund a deployed agent, and wait to see whether the money arrived."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Trading, LiveAgents, Agents, Funding, Accounts]
    related_skills: [liveagents, deploy-agent-live, monitor-agent, diagnose-agent]
---

# Fund Agent Skill

Ask for a deployed agent to be given something to trade with.

A deployed agent gets a sub-account of its own and starts empty, so the first thing a new one
does is place orders the exchange refuses for want of a balance. This is how it gets a budget.

## When to Use

Straight after a live deploy, when the agent's equity is zero. Also when a running agent has run
out of margin and is being refused - `/monitor-agent` and `/diagnose-agent` both surface that, and
this is the answer to it.

Not for a demo agent. A demo agent's orders are refused by the exchange whatever its balance is,
so funding one changes nothing.

## How to Run

```bash
parabolic liveagents fund-agent [<name>] [--amount N] [--note "why"]
```

Run it through `terminal`. It prints what it asked for and then waits, watching the sub-account,
and says when the money lands.

- **`<name>` is optional.** With nothing named it takes the agent deployed most recently, which
  is what "fund the one I just deployed" means and is the moment this exists for. It prints which
  one either way. If the user is plainly talking about a different agent, or several are empty,
  run `parabolic liveagents agents` and ask which.
- **`--amount` is a suggestion, not an instruction.** It prefills the field in the owner's
  console dialog and is typed over freely. Pass it only if they named a figure or asked you to
  recommend one; the person at the console can see their own free balance and this command
  cannot, so a number invented here is a guess at the one thing the dialog answers better. If you
  do recommend one, base it on the position size the agent takes and the margin that needs, and
  say so in a sentence.
- **`--note` is worth passing when there is a real reason.** "It is out of margin after three
  losing trades" tells the owner something; "needs funds" does not. It is shown beside the amount.
- `--no-wait` records the request and returns, for a script that is not going to read the answer.

## What it does, exactly

It records a funding request. The owner's console notices it within a few seconds and opens its
own funding dialog - the same one the agent's page has, showing what the agent holds and what the
owner has free - and **the transfer happens there**, in their browser, under their own session,
after they have typed an amount. With no console tab open the request waits, and lapses fifteen
minutes after it was raised.

Then this command watches the exchange and reports the equity actually changing. Two different
facts, and only the second is what anybody wanted: that a request was recorded, and that the
agent can now trade.

## Reading the answer

- **The money arrived.** Say the new balance and move on to `/monitor-agent <name>`.
- **Nothing arrived.** This is not a failure and not something to retry. The dialog is waiting
  for a person. Say so plainly, and say where: their console tab. **Do not raise a second
  request** - a new one replaces the old, so all that achieves is moving the amount they were
  looking at.
- **`no agent of yours called X`.** The name is wrong or the agent belongs to another account.
  The error lists what is deployed; offer those.
- **A 401.** The exchange session has expired. Set `LIVEAGENTS_API_TOKEN` again from the console;
  see the `liveagents` skill for which token that is and which one looks like it and is not.

## What this cannot do, and why that is the design

**This process cannot move the owner's money, and does not try to.** Say that plainly if asked,
because it is the reason the command works this way rather than simply transferring the funds.

`LIVEAGENTS_API_TOKEN` is a full exchange session, so a transfer from here would be technically
possible. It is deliberately not done: it would mean an agent's own code, a dependency of it, or
a stray line in a prompt could move somebody's capital while they were not present. Asking cannot
be done quietly - it puts a dialog in front of the one party who should decide, naming the agent
and the amount, with nothing moved until they answer.

So never offer a different route for the money, never ask the user to paste a credential to
speed this up, and never treat a request you raised as funding that happened. If they would
rather do it by hand, the answer is the Funding button on the agent's page in the console: the
same transfer, by the same route.
