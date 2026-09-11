# Recursive Self Learning Agents on Cloudflare Containers

Runs the agent's browser dashboard as a Cloudflare Container, fronted by a
Worker. The container has no public ingress; the Worker is the only way in.

```
browser ──► Worker (auth gate, instance routing, WebSocket passthrough)
                │
                └──► Container: dashboard on :8080, isolated VM, ephemeral disk
```

## What you need

- A Cloudflare account on the **Workers Paid** plan. Containers are not
  available on the free plan.
- Docker running locally. Wrangler builds the image and pushes it to
  Cloudflare's registry.
- Node 20 or newer.

## Deploy

```bash
cd deploy/cloudflare
npm install

# Dashboard sign-in, enforced inside the container.
npx wrangler secret put RSLA_DASHBOARD_USERNAME
npx wrangler secret put RSLA_DASHBOARD_PASSWORD
# Signs dashboard sessions so they survive a container restart.
npx wrangler secret put RSLA_DASHBOARD_SECRET

npx wrangler deploy
```

Wrangler prints the `*.workers.dev` URL. Open it, sign in, and the dashboard
runs in the browser.

Set the public origin so the dashboard builds correct absolute URLs:

```bash
npx wrangler secret put RSLA_PUBLIC_URL   # e.g. https://recursive-self-learning-agents.<subdomain>.workers.dev
```

## Isolation

`RSLA_ISOLATION` in `wrangler.jsonc` chooses the model.

| Value | Behaviour |
| --- | --- |
| `shared` (default) | One container instance serves the deployment. |
| `per-user` | Every browser gets its own container instance, keyed by an opaque cookie the Worker issues. Separate filesystem, processes and agent state. |

`per-user` requires a Worker pre-gate, otherwise anonymous traffic could spawn
containers without limit:

```bash
npx wrangler secret put RSLA_GATE_PASSWORD
```

The Worker refuses to serve `per-user` without it. Raise `max_instances` in
`wrangler.jsonc` to the number of concurrent users you expect.

## Building the runtime from this fork's source

The image layers the rebranded dashboard bundle onto the published upstream
runtime, pinned by digest. To build the Python runtime from this checkout
instead:

```bash
docker buildx build --platform linux/amd64 -t rsla-base:local .
cd deploy/cloudflare
npx wrangler deploy --var BASE_IMAGE:rsla-base:local
```

That build compiles SQLite, installs a Playwright Chromium shell and resolves
the full Python dependency set, so budget 30–60 minutes on a cold cache.

## Operating notes

- **Container disk is ephemeral.** `/opt/data` is wiped when an instance
  stops. Anything the agent should keep across restarts has to live in an
  external store. An instance sleeps after 45 minutes of no requests.
- **First request after a cold start is slow.** The dashboard boots a Python
  venv and an s6 supervision tree before it accepts connections.
- **WebSockets pass through unchanged**, which is what the chat and terminal
  panes need.
- `npx wrangler tail` streams Worker and container logs.

## Local smoke test

Build and run the same image natively, without Cloudflare in the loop:

```bash
docker buildx build --platform linux/arm64 --build-arg RUNTIME_PLATFORM=linux/arm64 \
  -f deploy/cloudflare/Dockerfile -t rsla:localtest --load .

docker run --rm -p 8080:8080 \
  -e HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin \
  -e HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=changeme \
  -e HERMES_DASHBOARD_BASIC_AUTH_SECRET=local-dev-secret \
  rsla:localtest
```

Then open <http://localhost:8080>. Drop `RUNTIME_PLATFORM` on an x86 machine.
