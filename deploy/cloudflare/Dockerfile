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
# vite writes to web/../hermes_cli/web_dist (see web/vite.config.ts).
RUN cd web && npm run build

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
RUN rm -rf /opt/hermes/hermes_cli/web_dist
COPY --chmod=a+rX,go-w --from=web_build /build/hermes_cli/web_dist/ /opt/hermes/hermes_cli/web_dist/
COPY --chmod=a+rX,go-w locales/ /opt/hermes/locales/

# The two Python modules the rebrand touches. Only these, not the whole
# hermes_cli tree: the base image's venv is an editable install of its own
# source, and wholesale replacement would silently mix this checkout against
# dependencies resolved for a different commit.
COPY --chmod=a+rX,go-w hermes_cli/dashboard_auth/login_page.py /opt/hermes/hermes_cli/dashboard_auth/login_page.py
COPY --chmod=a+rX,go-w hermes_cli/web_server.py /opt/hermes/hermes_cli/web_server.py

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
