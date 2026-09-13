# How the LiveAgents platform is put together

Three hosts, and knowing which one owns a question saves asking the wrong one.

| Host | Owns | Parabolic reaches it as |
|---|---|---|
| the console, `liveagents.org` | sign-in, the browser wizard | the shared Privy session |
| Agent Terminal, `terminal.liveagents.org` | the workspace: Claude Code, the trading harness, agent source, backtests | `parabolic liveagents whoami/kinds/build/publish/backtest` |
| the exchange, `dex.liveagents.org` | deployed agents: sub-accounts, scoped tokens, containers, fills | `parabolic liveagents agents/logs/source/start/stop/redeploy` |

The split is deliberate. Authoring and replaying need the harness and a Claude credential, which
live in the workspace. What is running, what it has traded and whether it may continue are facts
about the exchange. Asking a terminal what is deployed would be asking something that merely
started it once.

## One sign-in

The console, the terminal and this dashboard are one Privy application, so a sign-in on any of
them is a sign-in on all of them. The identity token is published in a cookie scoped to the parent
domain, and each application verifies it against the keys Privy publishes for the app.

Nothing mints a session of its own from it. A session that outlived a Privy logout is exactly the
failure that shape avoids, which is why `LIVEAGENTS_TERMINAL_TOKEN` holding a Privy token is
normal rather than a workaround: the workspace verifies it on every request.

## What a deployed agent is

A deploy does three things, and the middle one is the whole design:

1. creates a **sub-account** for the agent,
2. mints a token that resolves to **that account alone**,
3. starts a container that runs the strategy with that token in its environment.

What follows from it:

- **Attribution is free.** Agent fills are separable from the holder's own because they are on a
  different account, not because something remembered to set a flag.
- **A faulty agent cannot reach the master account.** Its token resolves to one fixed account and
  the account-selection header is refused for it.
- **An agent cannot move money.** Transfers need a wallet signature the container never sees.
- **Stopping actually stops.** Revoking the token halts trading; stopping the container is tidying
  up afterwards. A container that misses its shutdown still cannot trade.

A freshly created sub-account has **no collateral**, and every order it sends is rejected until
funds are moved to it. There is no faucet. Say this plainly after a live deploy rather than
letting it surface as a rejected order.

## Demo and live

| Mode | Runs | Market data | Orders |
|---|---|---|---|
| `demo` | for real, in its own container | live | the exchange refuses every one |
| `live` | for real, in its own container | live | filled against the book |

Demo is not a simulation and not a backtest. It exercises the deploy, the loop, the data path and
the error handling; it says nothing about fills or slippage.

## Supervision, and what may change

Each deployed agent's container runs the strategy **and** a supervisor. Every fifteen minutes the
supervisor reads what happened — fills, position, equity, market move, realised volatility, the
strategy's own output — decides, applies the answer and writes its reasoning to a journal.

It may change **parameters, not code**. Tunables are declared with ranges in a sibling
`params.json`; an undeclared name is refused and an out-of-range value is refused rather than
clamped. The risk envelope is a constant in the strategy and is never tunable.

An agent that ships no declarations gets **no supervisor**. That is a legitimate choice and the
defining feature of a rule-based agent, not an omission.

## Reading the numbers honestly

- **Net P&L** is realised P&L, fees and funding. Money transferred in is not performance.
- **Max drawdown** is the deepest peak-to-trough fall of *realised* P&L. An agent holding a large
  open loss shows no drawdown from it until the position closes.
- **Sharpe** is a plain reward-to-variability ratio over realised trade P&L, not annualised. Under
  about twenty trades it says very little.
- **Win rate** can look good while net P&L is negative, because fees and funding are in the second
  and not the first.
- **A stale heartbeat** means the container stopped reporting. The agent is not running.

## Two endpoints that are easy to confuse

The account view carries balances, positions and margin. The portfolio view is the equity curve,
Sharpe and drawdown, and contains no positions at all. An agent wants the first one every pass.
