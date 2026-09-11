/**
 * Recursive Self Learning Agents — Cloudflare Worker front door.
 *
 * The container has no public ingress of its own. Every byte reaches it
 * through this Worker, which does three things:
 *
 *   1. Optionally holds a pre-gate, so containers cannot be spawned by
 *      anonymous traffic (required for per-user isolation).
 *   2. Picks which container instance serves the request. In `shared` mode
 *      that is one instance for everyone; in `per-user` mode each browser
 *      gets its own instance, and therefore its own filesystem, processes
 *      and agent state.
 *   3. Forwards HTTP and WebSocket traffic verbatim, including the upgrade
 *      handshake the dashboard's chat and terminal panes depend on.
 *
 * The dashboard's own sign-in still runs inside the container. That gate is
 * an upstream security control and this deployment does not disable it.
 */
import { Container, getContainer } from "@cloudflare/containers";

export interface Env {
  AGENT: DurableObjectNamespace<AgentContainer>;
  /** `shared` (default) or `per-user`. */
  RSLA_ISOLATION?: string;
  /** Public origin the dashboard should believe it is served from. */
  RSLA_PUBLIC_URL?: string;
  /** Dashboard sign-in, read by the container's bundled `basic` auth plugin. */
  RSLA_DASHBOARD_USERNAME?: string;
  RSLA_DASHBOARD_PASSWORD?: string;
  /** Signs dashboard sessions so they survive a container restart. */
  RSLA_DASHBOARD_SECRET?: string;
  /** When set, the Worker pre-gate is enforced before any container starts. */
  RSLA_GATE_PASSWORD?: string;
}

const GATE_COOKIE = "rsla_gate";
const SESSION_COOKIE = "rsla_session";
/** Long enough that a working session is never interrupted by a cold start. */
const SLEEP_AFTER = "45m";

export class AgentContainer extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = SLEEP_AFTER;

  // The dashboard boots a Python process, a venv and an s6 supervision tree,
  // so the first request after a cold start waits a while.
  override envVars = {
    HERMES_DASHBOARD_HOST: "0.0.0.0",
    HERMES_DASHBOARD_PORT: "8080",
    HERMES_DASHBOARD_BASIC_AUTH_USERNAME: this.env.RSLA_DASHBOARD_USERNAME ?? "",
    HERMES_DASHBOARD_BASIC_AUTH_PASSWORD: this.env.RSLA_DASHBOARD_PASSWORD ?? "",
    HERMES_DASHBOARD_BASIC_AUTH_SECRET: this.env.RSLA_DASHBOARD_SECRET ?? "",
    HERMES_DASHBOARD_PUBLIC_URL: this.env.RSLA_PUBLIC_URL ?? "",
  };

  override onStart() {
    console.log("agent container started");
  }

  override onStop({ exitCode, reason }: { exitCode: number; reason: string }) {
    console.log(`agent container stopped: exit=${exitCode} reason=${reason}`);
  }

  override onError(error: unknown) {
    console.error("agent container error:", error);
    return new Response(
      "The agent container failed to start. Check `wrangler tail` for the container log.",
      { status: 502, headers: { "content-type": "text/plain; charset=utf-8" } },
    );
  }
}

function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get("cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    if (part.slice(0, eq).trim() === name) return part.slice(eq + 1).trim();
  }
  return null;
}

const encoder = new TextEncoder();

async function hmac(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return [...new Uint8Array(signature)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

/** Constant-time compare so a wrong password leaks no timing signal. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function gatePage(message: string | null, status: number): Response {
  const notice = message
    ? `<p class="err">${message.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!)}</p>`
    : "";
  return new Response(
    `<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recursive Self Learning Agents</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:#07100f; color:#d7e6e3;
         font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif; padding:24px; }
  form { width:100%; max-width:22rem; }
  h1 { font-size:1.05rem; letter-spacing:.06em; text-transform:uppercase;
       margin:0 0 .4rem; color:#5fe3c8; }
  p { margin:0 0 1.4rem; color:#7e918e; font-size:.85rem; }
  .err { color:#ff9d8a; }
  input, button { width:100%; box-sizing:border-box; padding:.7rem .8rem;
                  border-radius:.4rem; font:inherit; }
  input { background:#0d1a18; border:1px solid #1d3330; color:inherit; }
  button { margin-top:.7rem; background:#5fe3c8; border:0; color:#04120f;
           font-weight:600; cursor:pointer; }
</style>
<form method="post" action="/__rsla/gate">
  <h1>Recursive Self Learning Agents</h1>
  <p>This deployment is private. Enter the access password to continue.</p>
  ${notice}
  <input type="password" name="password" placeholder="Access password" autofocus required>
  <button type="submit">Continue</button>
</form>`,
    { status, headers: { "content-type": "text/html; charset=utf-8" } },
  );
}

async function gateCookieValue(secret: string): Promise<string> {
  return hmac(secret, "rsla-gate-v1");
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const isolation = (env.RSLA_ISOLATION ?? "shared").toLowerCase();
    const gatePassword = env.RSLA_GATE_PASSWORD ?? "";

    if (isolation === "per-user" && !gatePassword) {
      return new Response(
        "RSLA_ISOLATION=per-user requires the RSLA_GATE_PASSWORD secret, " +
          "otherwise anonymous traffic can spawn unlimited containers.\n" +
          "Set it with: wrangler secret put RSLA_GATE_PASSWORD\n",
        { status: 500, headers: { "content-type": "text/plain; charset=utf-8" } },
      );
    }

    const setCookies: string[] = [];

    if (gatePassword) {
      const expected = await gateCookieValue(gatePassword);

      if (url.pathname === "/__rsla/gate" && request.method === "POST") {
        const form = await request.formData();
        const supplied = String(form.get("password") ?? "");
        if (!timingSafeEqual(supplied, gatePassword)) {
          return gatePage("That password was not accepted.", 401);
        }
        return new Response(null, {
          status: 303,
          headers: {
            location: "/",
            "set-cookie":
              `${GATE_COOKIE}=${expected}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800`,
          },
        });
      }

      const presented = readCookie(request, GATE_COOKIE);
      if (!presented || !timingSafeEqual(presented, expected)) {
        return gatePage(null, 401);
      }
    }

    // Which container answers. `shared` keeps one agent for the deployment;
    // `per-user` gives every browser its own, keyed by an opaque cookie that
    // never leaves this Worker's control.
    let instanceName = "rsla-default";
    if (isolation === "per-user") {
      let session = readCookie(request, SESSION_COOKIE);
      if (!session || !/^[0-9a-f]{32}$/.test(session)) {
        session = crypto.randomUUID().replace(/-/g, "");
        setCookies.push(
          `${SESSION_COOKIE}=${session}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800`,
        );
      }
      instanceName = `rsla-${session}`;
    }

    const container = getContainer(env.AGENT, instanceName);
    const response = await container.fetch(request);

    if (setCookies.length === 0) return response;

    // A 101 response is immutable and carries the WebSocket, so cookies are
    // only ever attached to the ordinary HTTP response that precedes it.
    if (response.status === 101) return response;
    const withCookies = new Response(response.body, response);
    for (const cookie of setCookies) withCookies.headers.append("set-cookie", cookie);
    return withCookies;
  },
} satisfies ExportedHandler<Env>;
