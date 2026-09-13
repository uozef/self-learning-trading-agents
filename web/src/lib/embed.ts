/**
 * Chat-only mode, for a dashboard framed inside somebody else's console.
 *
 * The LiveAgents console lists Hermes in its own rail and frames it. Two rails,
 * two brand blocks and two page headers then sit inside one window, and the
 * navigation the reader is actually using is the outer one — so the inner
 * chrome is duplication that costs the chat the space it needs.
 *
 * On, the shell drops its sidebar, its mobile header and its page header, and
 * the chat side panel starts collapsed. Nothing is removed from the build and
 * nothing is unreachable: the panel's own toggle still opens it, and every other
 * page is still there on its URL for anyone who navigates to it.
 *
 * **Asked for explicitly, never sniffed.** Detecting `window !== window.top`
 * would strip the chrome from any page that happened to be framed, including an
 * operator's own preview, and would do it invisibly. The embedder asks by
 * loading `?embed=chat`, which is a decision recorded in the URL where somebody
 * can see it and remove it.
 *
 * Latched in `sessionStorage` because the flag has to survive what the app does
 * to its own URL: the auth gate redirects an unauthenticated load to `/login`
 * and back, and the SPA rewrites the query as it navigates. Session scope, so a
 * new tab opened by hand is an ordinary dashboard again.
 */

const PARAM = "embed";
const THEME_PARAM = "theme";
const VALUE = "chat";
const STORE_KEY = "hermes-embed-mode";
const THEME_STORE_KEY = "hermes-embed-theme";

/** Read once per page load: neither can change under a running app. */
let resolved: boolean | null = null;
let resolvedTheme: string | null | undefined;

function readStore(): boolean {
  try {
    return sessionStorage.getItem(STORE_KEY) === VALUE;
  } catch {
    // Private browsing, or storage disabled. The query param still works for
    // the life of the URL; it simply stops surviving a redirect.
    return false;
  }
}

function writeStore(): void {
  try {
    sessionStorage.setItem(STORE_KEY, VALUE);
  } catch {
    /* nothing to latch to, and not worth failing a page load over */
  }
}

/**
 * Whether this page should render as chat and nothing else.
 *
 * Reads the query param and, having seen it once, remembers it for the tab.
 */
export function isChatOnlyEmbed(): boolean {
  if (resolved !== null) return resolved;
  let fromUrl = false;
  try {
    fromUrl = new URLSearchParams(window.location.search).get(PARAM) === VALUE;
  } catch {
    fromUrl = false;
  }
  if (fromUrl) writeStore();
  resolved = fromUrl || readStore();
  return resolved;
}

/** Test seam: forget what was resolved so a case can set up its own URL. */
export function resetChatOnlyEmbedForTests(): void {
  resolved = null;
  resolvedTheme = undefined;
  try {
    sessionStorage.removeItem(STORE_KEY);
    sessionStorage.removeItem(THEME_STORE_KEY);
  } catch {
    /* nothing stored */
  }
}

/**
 * The theme the embedder asked for, or null.
 *
 * A framed dashboard in its own colours is a second colour scheme inside
 * somebody else's page, so the embedder names one it matches. Requested rather
 * than stored: it applies for this framed session only and never becomes the
 * account's saved preference, so opening the dashboard in its own tab still
 * gives back whatever theme the person chose for themselves.
 *
 * Only honoured in chat-only mode. A `theme=` on an ordinary load would let any
 * link restyle somebody's dashboard, which is a different feature and not one
 * anybody asked for.
 */
export function embedThemeName(): string | null {
  if (resolvedTheme !== undefined) return resolvedTheme;
  if (!isChatOnlyEmbed()) {
    resolvedTheme = null;
    return resolvedTheme;
  }
  let fromUrl: string | null = null;
  try {
    fromUrl = new URLSearchParams(window.location.search).get(THEME_PARAM);
  } catch {
    fromUrl = null;
  }
  // Names are ours and short; anything else is ignored rather than applied, so
  // a malformed value cannot reach the theme resolver.
  if (fromUrl && !/^[a-z0-9-]{1,40}$/.test(fromUrl)) fromUrl = null;
  if (fromUrl) {
    try {
      sessionStorage.setItem(THEME_STORE_KEY, fromUrl);
    } catch {
      /* nothing to latch to */
    }
  }
  let stored: string | null = null;
  try {
    stored = sessionStorage.getItem(THEME_STORE_KEY);
  } catch {
    stored = null;
  }
  resolvedTheme = fromUrl ?? stored;
  return resolvedTheme;
}
