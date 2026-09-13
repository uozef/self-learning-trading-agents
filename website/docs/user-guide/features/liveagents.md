---
sidebar_position: 18
sidebar_label: "LiveAgents Trading"
title: "LiveAgents Trading"
description: "Create, backtest, deploy and supervise trading agents on liveagents.org from Hermes, with one shared sign-in"
---

# LiveAgents Trading

Hermes can create trading agents, replay them over history, deploy them onto the LiveAgents
exchange and supervise them afterwards — using the same commands and the same sign-in as Agent
Terminal, so somebody moving between the two types the same thing in both.

It is a client, not a second implementation. Agent Terminal already runs Claude Code against the
trading harness, writes agents and deploys them with a sub-account of their own; that machinery
stays where it is. A builder here that wrote its own templates would be a second idea of what an
agent is, and the two would disagree the first time either changed.

## Which host answers what

| Host | Owns | Reached as |
|---|---|---|
| the console, `liveagents.org` | sign-in | the shared Privy session |
| Agent Terminal, `terminal.liveagents.org` | the workspace: agent source, builds, backtests | `hermes liveagents whoami / launch / kinds / build / publish / backtest` |
| the exchange, `dex.liveagents.org` | deployed agents: sub-accounts, scoped tokens, containers | `hermes liveagents agents / logs / source / start / stop / redeploy` |

Authoring and replaying need the harness and a Claude credential, which live in the workspace.
What is running and what it has traded are facts about the exchange, so they are asked of the
exchange rather than of a terminal that merely started it once.

## Setting it up

Addresses are behaviour and go in `config.yaml`; tokens are credentials and come from the
environment.

```yaml
plugins:
  entries:
    liveagents:
      enabled: true
      settings:
        terminal_url: https://terminal.liveagents.org
        exchange_url: https://dex.liveagents.org
        console_url: https://liveagents.org
```

```bash
# A workspace key, created at the console under Connect Claude Code -> Workspace keys:
export LIVEAGENTS_TERMINAL_TOKEN=lat_…
# The exchange session, from the console's own browser storage:
export LIVEAGENTS_API_TOKEN=…   # localStorage.la_dex_token
```

The two come from different places on purpose, and it is worth knowing why.

`la_dex_token` is a session the exchange minted and holds. It lasts days and copying it is fine.

`la_terminal_token` is **not** the matching value, though it sits beside it under a name that
suggests it is. It is the Privy access token the console signed in with: renewed while a tab is
open, and good for one hour on its own. Copied into a config file it works until roughly
lunchtime and then returns 401 permanently, and copying a fresh one has the same ending. That is
what workspace keys are for - a credential created deliberately, labelled, revocable, and not
tied to anybody's browser being open. Create one on the **Connect Claude Code** page.

There is no Privy *identity* token to look for on liveagents.org: that setting is off for the
app, which is also why the platform's shared-identity cookie is never written and the console
hands its session over in a URL fragment instead.

Check both before promising anything:

```bash
hermes liveagents whoami      # the workspace, and whether Claude is signed in for it
hermes liveagents agents      # the exchange, and what is deployed
```

`whoami` reporting Claude as not signed in means no build will work, whatever else looks healthy.

## The commands

Every Agent Terminal command exists here under the same name. They are skills, so they arrive as
slash commands in the CLI, the TUI, the dashboard and the gateway alike.

| Command | What it does |
|---|---|
| `/create-new-trading-agent` | build one end to end, from choosing a market to running it live |
| `/create-new-news-agent` | build one that reacts to events rather than the shape of the chart |
| `/create-new-rule-based-agent` | build one with fixed rules and no supervisor |
| `/create-new-self-learning-agent` | build one that retunes itself as it runs |
| `/backtest`, `/backtest-agent` | replay a strategy over history and read the result honestly |
| `/walk-forward` | choose settings on one period and judge them on the next |
| `/optimise-agent` | find what is actually wrong with an agent, then improve it |
| `/deploy-agent-demo` | deploy for real with every order refused by the exchange |
| `/deploy-agent-live` | deploy onto its own sub-account |
| `/redeploy-agent` | swap the code, keep the sub-account |
| `/start-agent`, `/stop-agent` | lifecycle |
| `/monitor-agent` | status, performance and recent output |
| `/diagnose-agent` | work out why one will not run, and propose a fix |
| `/liveagents` | the platform reference: how the pieces fit and what the numbers mean |

The skills carry the judgement and call `hermes liveagents` for the work, which is the same split
Agent Terminal makes between its commands and `scripts/deploy.mjs`.

## One sign-in across the platform

The console, Agent Terminal and this dashboard are one Privy application, so a sign-in on any of
them is a sign-in on all of them. Enable it with the bundled `privy` dashboard auth provider:

```yaml
dashboard:
  privy:
    app_id: "<the Privy app id>"          # byte-identical to the console's
    shared_cookie: la_privy_id            # what the console publishes the identity token in
    console_url: https://liveagents.org   # where a visitor with no session is sent
```

The app id **must** match the console's exactly. Two ids that merely look alike produce two
accounts for the same person and tokens each side rejects as minted for somebody else.

### How the handoff works

The console publishes Privy's identity token in a cookie scoped to the parent domain, which every
application on it can read. This dashboard's own session is an HttpOnly cookie that the console
can neither read nor write, so the token is handed over instead:

- The login page reads the shared cookie, or an `#sso=<token>` fragment, and posts it to
  `POST /auth/sso-session`, which verifies it against the keys Privy publishes for the app and
  makes it this origin's cookie. It grants nothing that holding the token did not already grant:
  the same bearer is accepted by the gate directly.
- The fragment is used because it never reaches a server and never appears in a `Referer`.

**Nothing here mints a session.** The token is verified on every request and the session ends
exactly when the token does, so a Privy logout cannot leave a live dashboard session behind. That
is why signing out clears Privy's cookies as well as Hermes's own — a refresh token left behind
would let the SDK mint a new access token and undo the sign-out on the next page load.

### Being framed by the console

The console lists Hermes in its rail and frames it, the way it frames Agent Terminal. That only
works on a hostname under `liveagents.org`, and the reason is worth knowing because it is invisible
until it bites:

- A session cookie is `SameSite=Lax`. A browser sends those on a top-level navigation and on
  same-site requests, and **withholds them from a cross-site iframe**.
- Framed from a `workers.dev` host, the dashboard is a different registrable domain from the
  console. Every framed request therefore arrived with no session — including the one immediately
  after a successful handoff — so the frame bounced to the login form on every load and no amount
  of handing tokens over could fix it.
- On `agentterminal2.liveagents.org` it is same-site with the console, the cookie travels, and nothing has
  to be loosened to `SameSite=None`. That matters: `Lax` on a session cookie is CSRF
  defence-in-depth that every other Hermes deployment relies on, and giving it up to work around a
  hostname would be a poor trade.

Being on the parent domain also puts the shared `la_privy_id` cookie in reach, so the dashboard
reads the session itself and the fragment handoff becomes the fallback rather than the mechanism.

### Opening Agent Terminal already signed in

```bash
hermes liveagents launch --as "$(hermes liveagents whoami --json | jq -r .wallet)"
```

That prints a URL carrying the same handoff in reverse. `--as` is a tag for whoever this session
is signed in as: Agent Terminal remembers the last tag it saw, and a changed one signs the
previous person out, so a shared browser cannot open somebody else's workspace. The URL carries a
live credential — treat it as one.

## Things worth knowing before the first live deploy

- **A new sub-account has no collateral** and every order it sends is rejected until funds are
  moved to it. There is no faucet.
- **A deployed agent must keep running.** A strategy that finishes its work and returns is treated
  as a crash; it needs a loop. This is by far the most common reason an agent will not start.
- **Stopping is not flattening.** It revokes the agent's token and shuts the container down; open
  positions stay exposed until something closes them.
- **Demo is enforced by the exchange, not by the agent's code.** A demo agent's token is refused
  on every write, which makes demo safe to point at a strategy nobody has read closely.
- **Never retry a deploy on silence.** If the stream ends without saying it finished, check
  `hermes liveagents agents` first: a repeated live deploy is a second funded agent.
- **A supervisor may move declared parameters inside ranges a person set, never code and never the
  risk envelope.** An agent that can widen its own limits has no limits.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | it worked |
| 1 | the host refused, or a stream failed or was cut off |
| 2 | the call was wrong: a missing credential, a bad argument, an unreadable file |

A rejected credential says so and says what to do: sign in again on the console and put the fresh
token in the environment. The tokens are short-lived by design.
