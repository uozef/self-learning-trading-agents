# `parabolic liveagents` reference

Every subcommand takes `--json` for machine-readable output and `--token` to override the
environment for one call. Run them through `terminal`.

## The workspace

| Command | What it does |
|---|---|
| `whoami` | the account the workspace sees, and whether Claude is signed in for it |
| `launch [--as <tag>]` | a URL that opens Agent Terminal already signed in |
| `kinds` | the templates it will build from, and whether a build could run now |
| `build --idea … --market … --kind … --name … [--description …] [--interval N]` | writes a new agent; streams progress |
| `publish <name> --market … [--mode demo\|live] [--exchange-token …]` | deploys an agent the workspace holds; streams progress |
| `backtest <path> [--market …] [--interval 5m] [--days N \| --from … --to … \| --dataset hp_…] [--param name=value] [--fee …] [--slippage …] [--equity …]` | replays a strategy |
| `backtests` | saved runs |
| `backtest-read <file>` | one saved run in full |

`build` and `publish` stream newline-delimited JSON and take minutes. The last line says `done` or
`error`; a stream that ends without one was cut off, and the command says so and exits non-zero.
**Never re-run a deploy on silence** — check `agents` first, because a repeated deploy is a second
agent.

`backtest` takes the strategy's **path inside the workspace** (`agents/momentum.mjs`), not an
agent's deployed name — it replays a file, and the two are different things. `--param` sets a
declared tunable for that run only. `--fee`, `--slippage` and `--equity` override the cost
assumptions; a replay cheaper than reality is the most flattering thing a backtest can be.

The answer is the saved run artifact: its numbers are under `summary`, and its `id` is what
makes the result checkable later. Quote it.

`launch` puts the token in the URL **fragment**, which never reaches a server and never appears in a Referer. Pass `--as` with whoever this session is signed in as: Agent Terminal remembers the last tag it saw, and a changed one signs the previous person out, so a shared browser cannot open somebody else's workspace. Treat the URL as a live credential.

`--mode live` needs an exchange session as well as a workspace one, because creating a sub-account
is an act on the exchange in the holder's name. The command refuses up front rather than failing
mid-deploy.

## The exchange

| Command | What it does |
|---|---|
| `agents` | every deployed agent with status, sub-account, trades, net P&L, max drawdown |
| `logs <name>` | the stored status and error plus the container's own output |
| `source <name>` | the code the agent is actually running |
| `start <name>` | starts a stopped agent from the code it was deployed with |
| `stop <name>` | stops it; the sub-account and its funds are untouched |
| `redeploy <name> <file> [--params …] [--market …] [--mode …]` | swaps the code, keeps the sub-account |
| `fund-agent [<name>] [--amount N] [--note "why"] [--no-wait]` | asks the owner to fund an agent, then waits for the money |

`<name>` matches an agent's name or its id, and an unknown one lists what does exist rather than
failing blankly.

`redeploy` picks up a sibling `<file>.params.json` automatically, the same convention the
workspace uses. Keeping the sub-account is the point: a new agent for new code would strand the
balance in the abandoned one.

`fund-agent` is the one subcommand that is not answered by the exchange or the workspace. It
records a request on the platform Worker that serves the console, which opens its own funding
dialog - what the agent holds, what the owner has free, an amount, a button - and **the transfer
happens there**, in their browser, under their session. The credential is the same exchange
session everything else here uses, so there is nothing extra to configure.

It moves no money and cannot be made to. `LIVEAGENTS_API_TOKEN` would allow a transfer outright,
and that is exactly why funding is a request: otherwise an agent's code, a dependency of it or a
line in a prompt could spend somebody's capital while they were not there. The command then
watches the sub-account and reports the equity changing, so "asked" and "funded" are never
reported as the same thing. Nothing arriving is not a failure and not something to retry - a
second request replaces the first, which only moves the figure the owner was looking at.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | it worked |
| 1 | the host refused, or a stream failed or was cut off |
| 2 | the call was wrong: a missing credential, a bad argument, an unreadable file |

A rejected credential prints what to do about it. Sign in again on the console and put the fresh
token in the environment; the tokens are short-lived by design.
