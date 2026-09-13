# syntax=docker/dockerfile:1.7
#
# Recursive Self Learning Agents — Cloudflare Containers image.
#
# Cloudflare only schedules linux/amd64, so the runtime stage is pinned to it.
# The web bundle is architecture-independent JavaScript, so its stage builds on
# the native BUILDPLATFORM instead — on an Apple Silicon laptop that is the
# difference between a two-minute build and an hour of qemu.
#
# BASE_IMAGE is the published runtime (Python venv, Node, Playwright shell,
# s6 supervision tree). Point it at an image built from this repository's own
# top-level Dockerfile when you need the Python source to come from your fork:
#
#     docker buildx build --platform linux/amd64 -t rsla-base:local .
#     docker buildx build --platform linux/amd64 \
#       --build-arg BASE_IMAGE=rsla-base:local \
#       -f deploy/cloudflare/Dockerfile -t rsla:local .
# Pinned by digest to the multi-arch manifest published from the same upstream
# commit this fork is checked out at, so the image is reproducible.
ARG BASE_IMAGE=nousresearch/hermes-agent:latest@sha256:011d9e4a9e3f8c0f1b1b11a8c1606d2d26546180c20379dfaa7753d777cab8f9
ARG NODE_IMAGE=node:26-bookworm-slim
# Cloudflare only schedules amd64. Override to linux/arm64 for a native
# smoke test on an Apple Silicon machine; never for a real deploy.
ARG RUNTIME_PLATFORM=linux/amd64

# ---------- Rebranded dashboard bundle ----------
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS web_build
WORKDIR /build

# `file:` workspace deps must be symlinked, not copied — same rationale as the
# top-level Dockerfile.
ENV npm_config_install_links=false

COPY package.json package-lock.json ./
COPY web/package.json web/
COPY ui-tui/package.json ui-tui/
COPY ui-tui/packages/hermes-ink/ ui-tui/packages/hermes-ink/
COPY apps/shared/ apps/shared/
RUN npm install --prefer-offline --no-audit --fetch-retries=5

COPY web/ web/
# The TUI's own source. The banner's tagline and the vendor credit beside the
# model are rendered by the TUI, not by the Python banner, so the rebranding
# only lands if this bundle is rebuilt from this checkout.
COPY ui-tui/ ui-tui/

# vite writes to web/../hermes_cli/web_dist (see web/vite.config.ts); the TUI
# bundles to ui-tui/dist/entry.js.
RUN cd web && npm run build && cd ../ui-tui && npm run build

# ---------- Runtime ----------
FROM --platform=${RUNTIME_PLATFORM} ${BASE_IMAGE}

# Overlay the rebranded assets onto the published runtime. `a+rX,go-w` matches
# the permissions the base image bakes for /opt/hermes: readable and traversable
# by the unprivileged `hermes` user, writable only by root.
#
# The bundle is deleted before it is replaced. COPY merges into a directory, and
# vite hashes every chunk filename, so an overlay alone would leave the base
# image's entire bundle sitting next to the new one — unreferenced by
# index.html, still carrying the old brand, and still shipped in the image.
# ---------- Relocate the install ----------
#
# The product is Parabolic Agents, and the path it runs from is on screen: the
# banner prints the working directory and the status bar carries it. `/opt/hermes`
# under a Parabolic banner is the same mismatch as a Nous Research tagline.
#
# A real move, not a symlink: `os.getcwd()` resolves symlinks, so a symlinked
# alias would still print the real path in the one place anybody reads it.
#
# `parabolic` is the same entry point under the product's name, so the shipped
# skills can tell people to run the command the product is actually called. The
# check is `test -x` and not `parabolic --version`: this image has no `git`, and
# the version banner shells out to it, so running it here fails on a missing
# binary that has nothing to do with whether the command works.
#
# The venv is the catch. Its `bin/*` shebangs, `pyvenv.cfg` and the editable
# install's path file all carry the old absolute path, so they are rewritten
# here. The compatibility symlink left behind means anything baked into the base
# image that still says `/opt/hermes` keeps working rather than failing at boot
# somewhere nobody is watching.
RUN mv /opt/hermes /opt/parabolic \
 && grep -rIl --null /opt/hermes /opt/parabolic/.venv/bin /opt/parabolic/.venv/pyvenv.cfg 2>/dev/null \
      | xargs -0 -r sed -i 's|/opt/hermes|/opt/parabolic|g' \
 && find /opt/parabolic/.venv/lib -name '*.pth' -o -name '*.egg-link' \
      | xargs -r sed -i 's|/opt/hermes|/opt/parabolic|g' \
 && ln -s /opt/parabolic /opt/hermes \
 && /opt/parabolic/.venv/bin/python -c "import hermes_cli, sys; print('venv ok on', sys.prefix)" \
 && ln -sf hermes /opt/parabolic/.venv/bin/parabolic \
 && test -x /opt/parabolic/.venv/bin/parabolic

RUN rm -rf /opt/parabolic/hermes_cli/web_dist

COPY --chmod=a+rX,go-w --from=web_build /build/hermes_cli/web_dist/ /opt/parabolic/hermes_cli/web_dist/
COPY --chmod=a+rX,go-w locales/ /opt/parabolic/locales/
# The rebuilt TUI bundle. One self-contained file, so replacing it is the whole
# update; the base image's copy predates the rebrand.
COPY --chmod=a+rX,go-w --from=web_build /build/ui-tui/dist/entry.js /opt/parabolic/ui-tui/dist/entry.js

# The Python modules this fork changes. Only these, not the whole hermes_cli
# tree: the base image's venv is an editable install of its own source, and
# wholesale replacement would silently mix this checkout against dependencies
# resolved for a different commit.
#
# login_page.py and web_server.py carry the rebrand. auth.py and the anthropic
# provider plugin carry the credential-precedence fix that makes the Claude
# connector authenticate with the Claude auth token instead of a Console API key.
COPY --chmod=a+rX,go-w hermes_cli/web_server.py /opt/parabolic/hermes_cli/web_server.py
# Its sibling, for the theme list the dashboard's picker reads. The palettes
# themselves live in the bundle; this is the labels beside them.
COPY --chmod=a+rX,go-w hermes_cli/web_server_dashboard.py /opt/parabolic/hermes_cli/web_server_dashboard.py
# The TUI gateway, for the one line that decides which version the banner shows:
# a rebranding skin carries its own, and the build's version describes the
# engine rather than the product on screen.
COPY --chmod=a+rX,go-w tui_gateway/server.py /opt/parabolic/tui_gateway/server.py
COPY --chmod=a+rX,go-w hermes_cli/auth.py /opt/parabolic/hermes_cli/auth.py
COPY --chmod=a+rX,go-w plugins/model-providers/anthropic/__init__.py /opt/parabolic/plugins/model-providers/anthropic/__init__.py

# The dashboard-auth package, whole rather than file by file.
#
# It carries the shared Privy sign-in: the handoff capability on the provider
# protocol, the registry lookup for it, `POST /auth/sso-session`, the gate that
# adopts a sibling application's cookie before it ever redirects to a login
# page, the sign-out that clears that sibling's cookies too, and the login page
# (which also carries the rebrand).
#
# One self-contained subpackage, so copying all of it keeps it internally
# consistent - half of it at this checkout and half at the base image's commit
# is how a protocol change becomes an AttributeError on somebody's sign-in. The
# caution in the comment above is about replacing the whole `hermes_cli` tree
# against a venv resolved for another commit; a single subpackage whose own
# imports all resolve within it is a different proposition.
COPY --chmod=a+rX,go-w hermes_cli/dashboard_auth/ /opt/parabolic/hermes_cli/dashboard_auth/

# The Privy provider itself. Registers only when RSLA_PRIVY_APP_ID is set, so
# its presence changes nothing on a deployment that has not configured it.
COPY --chmod=a+rX,go-w plugins/dashboard_auth/privy/ /opt/parabolic/plugins/dashboard_auth/privy/

# The LiveAgents client, which gives the container `hermes liveagents ...` - the
# plumbing the trading skills call. Gated on a token, so it is inert until one
# is configured.
COPY --chmod=a+rX,go-w plugins/liveagents/ /opt/parabolic/plugins/liveagents/

# The terminal's own palette and identity. `skin_engine` holds the `liveagents`
# skin: the console's CSS tokens, so the framed terminal is not a second
# product's colours inside the page, plus the Kharazmi branding and artwork it
# presents itself with. `banner.py` reads the agent name and version off that
# skin instead of hardcoding Hermes's, which is what lets a skin rebrand the
# banner it draws under.
COPY --chmod=a+rX,go-w hermes_cli/skin_engine.py /opt/parabolic/hermes_cli/skin_engine.py
COPY --chmod=a+rX,go-w hermes_cli/banner.py /opt/parabolic/hermes_cli/banner.py

# The trading commands, as bundled skills.
COPY --chmod=a+rX,go-w skills/trading/ /opt/parabolic/skills/trading/

# Seed them into the profile the dashboard reads.
#
# A skill becomes a slash command by being in HERMES_HOME, not by being bundled:
# `sync_skills` is what copies one to the other and it runs on `hermes update`
# and on first-run setup, neither of which happens in this image. So the sync
# runs here, at build time, into the home the container starts with.
#
# That home is `/opt/data` and NOT `/opt/data/.hermes`: this image sets
# `HERMES_HOME` to the directory itself, the way the project's own Dockerfile
# does. Seeding the `.hermes` child instead puts every file one level below
# anything that reads it, which looks exactly like a sync that did nothing.
#
# `|| true` because a failure to seed a skill must not fail the build: the
# dashboard is the product and it works without them, and the alternative is an
# image that cannot be deployed at all over a slash command.
RUN cd /opt/parabolic && HERMES_HOME=/opt/data /opt/parabolic/.venv/bin/python -c \
      "from tools.skills_sync import sync_skills; r = sync_skills(quiet=True); print('seeded', len(r.get('copied', [])), 'skills')" \
    || true
# Select the skin, the matching dashboard theme, and the model.
#
# Written as a PARTIAL merge, never by round-tripping `load_config()`.
# `load_config()` returns the schema defaults and the environment merged over
# the file; saving that back writes resolved values into config.yaml as if a
# person had chosen them. That is how this deployment ended up asking
# api.anthropic.com for `z-ai/glm-5.2` — an aggregator-style model id, resolved
# from somewhere it was only ever a default, then persisted against a provider
# that has never heard of it. `merge_existing=True` with just these keys cannot
# do that: nothing it does not name is touched.
#
# The model is named rather than left blank because blank means "whatever the
# resolver picks today", and this deployment carries a Claude subscription
# token (RSLA_CLAUDE_CODE_OAUTH_TOKEN) — so the answer should be a Claude model
# every time, not whatever a guest tier happens to be serving.
RUN cd /opt/parabolic && HERMES_HOME=/opt/data /opt/parabolic/.venv/bin/python -c "\
from hermes_cli import config as c; \
c.save_config({ \
    'display': {'skin': 'liveagents'}, \
    'dashboard': {'theme': 'liveagents'}, \
    'model': {'provider': 'anthropic', 'default': 'claude-opus-5'}, \
}, merge_existing=True); \
print('styled for the console, on Claude')" || true

RUN chown -R hermes:hermes /opt/data 2>/dev/null || true

# The Worker forwards to this port; Cloudflare gives the container no public
# ingress of its own.
ENV HERMES_DASHBOARD_HOST=0.0.0.0
ENV HERMES_DASHBOARD_PORT=8080

# Supervise the gateway too? No: the browser dashboard is the whole product
# here, and the gateway's messaging adapters need credentials this deployment
# does not carry. Leave the s6 dashboard slot down and run the dashboard as the
# container's main program so its exit is the container's exit.
ENV HERMES_DASHBOARD=0

EXPOSE 8080

CMD ["dashboard", "--host", "0.0.0.0", "--port", "8080", "--no-open"]
