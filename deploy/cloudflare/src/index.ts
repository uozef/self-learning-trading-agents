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
  /**
   * Claude subscription auth token from `claude setup-token` (an `sk-ant-oat01…`
   * value). This is the agent's Claude credential and is preferred over a Console
   * API key. Set `RSLA_ANTHROPIC_API_KEY` only to authenticate with a Console key
   * instead; if both are set the Claude token wins, matching the connector.
   */
  RSLA_CLAUDE_CODE_OAUTH_TOKEN?: string;
  RSLA_ANTHROPIC_API_KEY?: string;
  /**
   * The Privy app the whole of liveagents.org signs in to. Setting it turns on
   * the dashboard's Privy auth provider, so a console sign-in is a sign-in
   * here and nothing asks for a password.
   *
   * It MUST be byte-identical to the console's `VITE_PRIVY_APP_ID` and Agent
   * Terminal's `PRIVY_APP_ID`. Two ids that merely look alike produce two
   * accounts for the same person and tokens each side rejects as minted for
   * somebody else.
   */
  RSLA_PRIVY_APP_ID?: string;
  /**
   * The LiveAgents platform credentials the trading commands need.
   *
   * Two hosts, two tokens, because they answer different questions. The
   * workspace at terminal.liveagents.org writes agents and replays them; the
   * exchange at dex.liveagents.org owns the deployed ones.
   *
   * Both are minted by the console, which already holds them: it signs the
   * Agent Terminal challenge with the account's embedded wallet and exchanges
   * the same Privy identity for an exchange session. They live in the console's
   * own storage as `la_terminal_token` and `la_dex_token`.
   *
   * They are wallet-minted sessions rather than Privy access tokens, which is
   * what makes a secret the right home for them: a Privy access token lasts
   * about an hour, so baking one in would stop working before the day was out.
   */
  RSLA_LIVEAGENTS_TERMINAL_TOKEN?: string;
  RSLA_LIVEAGENTS_API_TOKEN?: string;
  /**
   * Enables POST /__rsla/restart. Unset (the default) and that route 404s, so it
   * adds no reachable surface until an operator opts in.
   */
  RSLA_ADMIN_TOKEN?: string;
}

const GATE_COOKIE = "rsla_gate";
const SESSION_COOKIE = "rsla_session";
/** Long enough that a working session is never interrupted by a cold start. */
const SLEEP_AFTER = "45m";

export class AgentContainer extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = SLEEP_AFTER;

  /**
   * Only the variables that actually carry a value.
   *
   * An unset secret used to arrive as an empty string, which is not the same
   * thing as absent: the agent reported both LiveAgents tokens as "present but
   * 0 chars" and told its user they were configured-but-blank, when nobody had
   * configured them at all. Absent says what is true, and it lets a value
   * written to the container's own `.env` win rather than sit behind an empty
   * variable of the same name.
   */
  private static present(vars: Record<string, string | undefined>): Record<string, string> {
    return Object.fromEntries(
      Object.entries(vars).filter(([, v]) => typeof v === "string" && v.length > 0),
    ) as Record<string, string>;
  }

  // The dashboard boots a Python process, a venv and an s6 supervision tree,
  // so the first request after a cold start waits a while.
  override envVars = AgentContainer.present({
    HERMES_DASHBOARD_HOST: "0.0.0.0",
    HERMES_DASHBOARD_PORT: "8080",
    HERMES_DASHBOARD_BASIC_AUTH_USERNAME: this.env.RSLA_DASHBOARD_USERNAME ?? "",
    HERMES_DASHBOARD_BASIC_AUTH_PASSWORD: this.env.RSLA_DASHBOARD_PASSWORD ?? "",
    HERMES_DASHBOARD_BASIC_AUTH_SECRET: this.env.RSLA_DASHBOARD_SECRET ?? "",
    HERMES_DASHBOARD_PUBLIC_URL: this.env.RSLA_PUBLIC_URL ?? "",
    // Unset means the provider does not register and the dashboard falls back
    // to the password it already has.
    HERMES_DASHBOARD_PRIVY_APP_ID: this.env.RSLA_PRIVY_APP_ID ?? "",
    // The names the `liveagents` plugin reads. Unset means the trading commands
    // name the missing token, and a value in the container's `.env` still wins.
    LIVEAGENTS_TERMINAL_TOKEN: this.env.RSLA_LIVEAGENTS_TERMINAL_TOKEN ?? "",
    LIVEAGENTS_API_TOKEN: this.env.RSLA_LIVEAGENTS_API_TOKEN ?? "",
    // The agent's Claude credential. The connector reads the Claude auth token
    // ahead of the Console API key, so passing both leaves the subscription in
    // charge. Empty values are fine: the agent treats a blank env var as absent.
    CLAUDE_CODE_OAUTH_TOKEN: this.env.RSLA_CLAUDE_CODE_OAUTH_TOKEN ?? "",
    ANTHROPIC_API_KEY: this.env.RSLA_ANTHROPIC_API_KEY ?? "",
  });

  override onStart() {
    console.log("agent container started");
  }

  override onStop({ exitCode, reason }: { exitCode: number; reason: string }) {
    console.log(`agent container stopped: exit=${exitCode} reason=${reason}`);
  }

  /**
   * Stop the container so the next request starts it again.
   *
   * `envVars` is read when the container starts, not per request, so a secret
   * added after an instance is already up never reaches the agent — and a deploy
   * that changes no container config performs no rollout, so the stale instance
   * simply keeps running until it idles out. This is the supported way to apply
   * a credential change now instead of waiting for `sleepAfter`.
   */
  async restartForConfigChange(): Promise<string> {
    const before = await this.getState();
    await this.destroy();
    return before?.status ?? "unknown";
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

    // Applies a credential change without waiting for the idle timeout. Carries
    // its own auth and is absent unless RSLA_ADMIN_TOKEN is set, so it sits
    // ahead of the visitor gate without widening what an anonymous caller can do.
    if (url.pathname === "/__rsla/restart") {
      const adminToken = env.RSLA_ADMIN_TOKEN ?? "";
      if (!adminToken || request.method !== "POST") {
        return new Response("Not found", { status: 404 });
      }
      if (!timingSafeEqual(request.headers.get("x-rsla-admin") ?? "", adminToken)) {
        return new Response("Forbidden", { status: 403 });
      }
      const target = url.searchParams.get("instance") || "rsla-default";
      const previous = await getContainer(env.AGENT, target).restartForConfigChange();
      return new Response(
        `stopped ${target} (was ${previous}); it restarts on the next request\n`,
        { headers: { "content-type": "text/plain; charset=utf-8" } },
      );
    }

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
