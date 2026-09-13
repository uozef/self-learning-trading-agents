"""Server-rendered /login page (no React, no SPA bundle, no injected token).

Providers come from the registry; an OAuth provider renders an anchor to
``/auth/login?provider=<name>``, a ``supports_password`` provider renders a
credential form wired by :data:`_PASSWORD_FORM_SCRIPT`. Styling mirrors the
``@nous-research/ui`` design system; fonts load from the SPA's ``/fonts/``
mount, which the gate allowlists pre-auth.

The ``class="provider-btn"`` anchor is test-stable: the suite extracts its
href to walk the OAuth flow.
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote, urlencode

from hermes_cli.dashboard_auth import list_session_providers

# Single curly braces are ``str.format`` placeholders; CSS curlies are doubled.
_LOGIN_HTML_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — Parabolic Agents</title>
{head_script}<style>
  /* Brand fonts shipped by @nous-research/ui — same files the SPA loads. */
  @font-face {{
    font-family: 'Collapse';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('/fonts/Collapse-Regular.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'Collapse';
    font-style: normal;
    font-weight: 700;
    font-display: swap;
    src: url('/fonts/Collapse-Bold.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'Rules Compressed';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('/fonts/RulesCompressed-Regular.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'Rules Compressed';
    font-style: normal;
    font-weight: 600;
    font-display: swap;
    src: url('/fonts/RulesCompressed-Medium.woff2') format('woff2');
  }}

  :root {{
    --background-base: {bg};
    --background: {bg};
    --midground: {accent};
    --foreground: {fg};
    --hairline: color-mix(in srgb, {accent} 18%, transparent);
    --hairline-strong: color-mix(in srgb, {accent} 35%, transparent);
  }}

  *, *::before, *::after {{ box-sizing: border-box; }}

  /* A sign-in that is already happening shows nothing.
     The token arrives in the URL fragment, which a server cannot see, so this
     page has to load for its script to spend it. Without this the visitor gets
     a fully painted sign-in form for the half second before the redirect —
     asked to sign in, in another product's colours, while already signed in.
     `visibility` rather than `display`: the ground stays painted, so the frame
     does not flash white either. Cleared by the script when the handoff fails,
     which is the one case where the form is the right thing to show. */
  html[data-handoff] body {{
    visibility: hidden;
  }}

  html, body {{
    margin: 0;
    padding: 0;
    min-height: 100%;
    background: var(--background-base);
    color: var(--foreground);
    font-family: 'Collapse', system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    font-size: 16px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}

  /* Subtle dot-grid backdrop — DS idiom (see `.dither` in globals.css). */
  body {{
    background-image:
      radial-gradient(
        ellipse at top,
        color-mix(in srgb, var(--midground) 6%, transparent) 0%,
        transparent 55%
      ),
      repeating-conic-gradient(
        color-mix(in srgb, var(--midground) 4%, transparent) 0% 25%,
        transparent 0% 50%
      );
    background-size: auto, 3px 3px;
    background-attachment: fixed;
  }}

  /* Layout: vertically center on tall screens, top-anchor on short. */
  body {{
    display: grid;
    place-items: center;
    padding: clamp(1.5rem, 6vh, 6rem) 1.25rem;
  }}

  main {{
    width: 100%;
    max-width: 26rem;
    position: relative;
    animation: slide-up 0.6s ease-out both;
  }}

  @keyframes slide-up {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  @media (prefers-reduced-motion: reduce) {{
    main {{ animation: none; }}
  }}

  /* Brand wordmark above the card — same uppercase + wide-tracking
     idiom DS Buttons use. */
  .brand {{
    text-align: center;
    margin-bottom: 1.75rem;
    font-family: 'Rules Compressed', 'Collapse', sans-serif;
    font-weight: 600;
    font-size: 1.05rem;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    color: var(--midground);
  }}
  .brand .dot {{
    display: inline-block;
    width: 6px;
    height: 6px;
    background: var(--midground);
    margin: 0 0.55em 0.18em;
    vertical-align: middle;
    border-radius: 1px;
  }}

  .card {{
    position: relative;
    padding: 2.25rem 2rem 2rem;
    background: color-mix(in srgb, #ffffff 2%, var(--background-base));
    border: 1px solid var(--hairline);
    /* Hairline highlight + bevel shadow — matches DS Button SHADOW_DEFAULT
       (`inset -1px -1px 0 #00000080, inset 1px 1px 0 #ffffff80`) at panel scale. */
    box-shadow:
      inset 1px 1px 0 0 color-mix(in srgb, #ffffff 5%, transparent),
      inset -1px -1px 0 0 rgba(0, 0, 0, 0.4),
      0 24px 60px -20px rgba(0, 0, 0, 0.6);
  }}

  h1 {{
    margin: 0 0 0.4rem;
    font-family: 'Rules Compressed', 'Collapse', sans-serif;
    font-weight: 600;
    font-size: 1.85rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--foreground);
  }}

  .subtitle {{
    margin: 0 0 1.75rem;
    color: color-mix(in srgb, var(--foreground) 65%, transparent);
    font-size: 0.95rem;
  }}

  .provider-list {{
    display: grid;
    gap: 0.75rem;
  }}

  /* Provider button — mirrors DS Button (default variant):
     amber surface, dark text, uppercase + wide tracking, inset bevel. */
  .provider-btn {{
    display: block;
    width: 100%;
    box-sizing: border-box;
    padding: 0.95rem 1rem;
    text-align: center;
    background: var(--midground);
    color: var(--background-base);
    font-family: 'Collapse', sans-serif;
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    text-decoration: none;
    border: 0;
    border-radius: 0;  /* DS Button is squared — no rounded corners. */
    cursor: pointer;
    box-shadow:
      inset 1px 1px 0 0 rgba(255, 255, 255, 0.5),
      inset -1px -1px 0 0 rgba(0, 0, 0, 0.5);
    transition: filter 0.12s ease-out;
  }}
  .provider-btn:hover {{
    filter: brightness(1.08);
  }}
  .provider-btn:active {{
    /* DS Button uses `active:invert` on the default surface. */
    filter: invert(1);
  }}
  .provider-btn:focus-visible {{
    outline: 2px solid var(--midground);
    outline-offset: 3px;
  }}

  /* Password provider form — same visual language as the OAuth buttons:
     squared inputs, hairline borders, amber focus ring. */
  .provider-form {{
    display: grid;
    gap: 0.75rem;
    text-align: left;
  }}
  .form-title {{
    font-family: 'Rules Compressed', 'Collapse', sans-serif;
    font-weight: 600;
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--foreground) 70%, transparent);
  }}
  .field {{
    display: grid;
    gap: 0.3rem;
  }}
  .field-label {{
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--foreground) 55%, transparent);
  }}
  .field-input {{
    width: 100%;
    box-sizing: border-box;
    padding: 0.7rem 0.8rem;
    background: color-mix(in srgb, #000000 25%, var(--background-base));
    color: var(--foreground);
    border: 1px solid var(--hairline-strong);
    border-radius: 0;
    font-family: 'Collapse', sans-serif;
    font-size: 0.95rem;
  }}
  .field-input:focus-visible {{
    outline: none;
    border-color: var(--midground);
    box-shadow: 0 0 0 1px var(--midground);
  }}
  .form-error {{
    color: #ff6b6b;
    font-size: 0.82rem;
    letter-spacing: 0.02em;
  }}
  .provider-form .provider-btn {{
    margin-top: 0.25rem;
  }}

  footer {{
    margin-top: 1.75rem;
    text-align: center;
    color: color-mix(in srgb, var(--foreground) 45%, transparent);
    font-size: 0.75rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    line-height: 1.7;
  }}
  footer .sep {{
    display: inline-block;
    width: 1.5rem;
    height: 1px;
    background: var(--hairline-strong);
    vertical-align: middle;
    margin: 0 0.6em 0.2em;
  }}

  /* Selection — DS uses midground bg + background text. */
  ::selection {{
    background: var(--midground);
    color: var(--background-base);
  }}
</style>
</head>
<body>
<main>
  <div class="brand">Parabolic<span class="dot"></span>Agents</div>
  <div class="card">
    <h1>Sign in</h1>
    <p class="subtitle">Choose a sign-in method to continue to the Parabolic Agents dashboard.</p>
    <div class="provider-list">
{provider_buttons}
    </div>
  </div>
  <footer>
    <span class="sep"></span>Public bind &middot; Auth required<span class="sep"></span>
  </footer>
</main>
{password_script}
</body>
</html>
"""

_EMPTY_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign-in unavailable — Parabolic Agents</title>
<style>
  @font-face {
    font-family: 'Collapse';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('/fonts/Collapse-Regular.woff2') format('woff2');
  }
  @font-face {
    font-family: 'Rules Compressed';
    font-style: normal;
    font-weight: 600;
    font-display: swap;
    src: url('/fonts/RulesCompressed-Medium.woff2') format('woff2');
  }
  :root {
    --background-base: #170d02;
    --midground: #ffac02;
    --foreground: #ffffff;
    --hairline: color-mix(in srgb, #ffac02 18%, transparent);
  }
  *, *::before, *::after { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; min-height: 100%;
    background: var(--background-base);
    color: var(--foreground);
    font-family: 'Collapse', system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    font-size: 16px; line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }
  body {
    display: grid; place-items: center;
    padding: clamp(1.5rem, 6vh, 6rem) 1.25rem;
  }
  main {
    width: 100%; max-width: 32rem;
    padding: 2.25rem 2rem;
    background: color-mix(in srgb, #ffffff 2%, var(--background-base));
    border: 1px solid var(--hairline);
    box-shadow:
      inset 1px 1px 0 0 color-mix(in srgb, #ffffff 5%, transparent),
      inset -1px -1px 0 0 rgba(0, 0, 0, 0.4),
      0 24px 60px -20px rgba(0, 0, 0, 0.6);
  }
  h1 {
    margin: 0 0 1rem;
    font-family: 'Rules Compressed', 'Collapse', sans-serif;
    font-weight: 600; font-size: 1.5rem;
    letter-spacing: 0.05em; text-transform: uppercase;
    color: var(--midground);
  }
  p { margin: 0 0 1rem; }
  code {
    background: var(--midground);
    color: var(--background-base);
    padding: 0.1em 0.35em;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
  }
  a { color: var(--midground); }
</style>
</head>
<body>
<main>
<h1>Sign-in unavailable</h1>
<p>This dashboard is bound to a non-loopback host but no authentication
providers are available.</p>
<p>Configure the bundled username/password provider or an OAuth provider.
See the <a href="https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard#authentication-gated-mode">dashboard
authentication documentation</a> for setup instructions.</p>
<p>For auth-free local use, bind to <code>127.0.0.1</code> and connect through
an SSH tunnel or Tailscale.</p>
</main>
</body>
</html>
"""


# Emitted ONLY when a ``supports_password`` provider is listed, so OAuth-only
# login pages stay script-free. Plain string (not ``str.format``): braces are
# literal. One delegated submit handler covers every form; the provider name
# comes from the form's ``data-provider`` attribute.
_PASSWORD_FORM_SCRIPT = """\
<script>
(function () {
  function handle(form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var err = form.querySelector('.form-error');
      var btn = form.querySelector('button[type=submit]');
      if (err) { err.hidden = true; err.textContent = ''; }
      if (btn) { btn.disabled = true; }
      var body = {
        provider: form.getAttribute('data-provider') || '',
        username: (form.querySelector('input[name=username]') || {}).value || '',
        password: (form.querySelector('input[name=password]') || {}).value || '',
        next: (form.querySelector('input[name=next]') || {}).value || ''
      };
      fetch('/auth/password-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
      }).then(function (resp) {
        if (resp.ok) {
          return resp.json().then(function (data) {
            window.location.assign((data && data.next) || '/');
          });
        }
        var msg = resp.status === 429
          ? 'Too many attempts. Please wait and try again.'
          : (resp.status === 401 ? 'Invalid username or password.'
                                 : 'Sign-in failed. Please try again.');
        if (err) { err.textContent = msg; err.hidden = false; }
        if (btn) { btn.disabled = false; }
      }).catch(function () {
        if (err) { err.textContent = 'Network error. Please try again.'; err.hidden = false; }
        if (btn) { btn.disabled = false; }
      });
    });
  }
  var forms = document.querySelectorAll('form.provider-form');
  for (var i = 0; i < forms.length; i++) { handle(forms[i]); }
})();
</script>
"""


# Emitted ONLY when a ``supports_sso_handoff`` provider is listed. Plain string (not
# ``str.format``): braces are literal. The token is read from the URL fragment the sibling
# application opened us with, or from the cookie it published on the shared parent domain, and
# handed to ``/auth/sso-session`` — which verifies it before it becomes a session here.
_SSO_HANDOFF_SCRIPT = """\
<script>
(function () {
  var el = document.querySelector('.provider-handoff');
  if (!el) { return; }
  var status = el.querySelector('.handoff-status');
  function say(text) { if (status) { status.textContent = text; status.hidden = false; } }
  // Whatever happens from here, the page has to become visible again: the
  // marker set in <head> hides it on the assumption the redirect is coming.
  function reveal() { document.documentElement.removeAttribute('data-handoff'); }

  // The fragment never reaches a server and never appears in a Referer, which is why the
  // sibling application is allowed to pass a credential in it.
  function fromFragment() {
    var match = /(?:^|[#&])sso=([^&]+)/.exec(window.location.hash || '');
    return match ? decodeURIComponent(match[1]) : '';
  }
  function fromCookie(name) {
    if (!name) { return ''; }
    var prefix = name + '=';
    var parts = (document.cookie || '').split(';');
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      if (part.indexOf(prefix) === 0) {
        try { return decodeURIComponent(part.slice(prefix.length)); } catch (e) { return ''; }
      }
    }
    return '';
  }

  var token = fromFragment() || fromCookie(el.getAttribute('data-cookie') || '');
  if (!token) { reveal(); return; }
  // Take it out of the address bar before anything else: a token left in the fragment stays in
  // history and in anything the user copies out of the URL bar.
  if (window.location.hash) {
    try {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    } catch (e) { /* a browser that refuses is no reason to stop signing in */ }
  }
  say('Signing you in\\u2026');

  fetch('/auth/sso-session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: token, next: el.getAttribute('data-next') || '' }),
    credentials: 'same-origin'
  }).then(function (resp) {
    if (resp.ok) {
      return resp.json().then(function (data) {
        window.location.assign((data && data.next) || '/');
      });
    }
    reveal();
    say(resp.status === 503
      ? 'The sign-in service is unreachable. Try again shortly.'
      : 'That sign-in has expired. Sign in again on the console.');
  }).catch(function () {
    reveal();
    say('Network error. Please try again.');
  });
})();
</script>
"""


# Emitted in <head>, before any of the page renders, ONLY when a handoff
# provider is listed. Plain string (not ``str.format``): braces are literal.
#
# It runs at parse time and sets a marker the stylesheet keys off, so the
# sign-in form never paints for somebody who is already signed in and is about
# to be redirected. The check is deliberately the same one the handoff script
# makes later; doing it here costs a few microseconds and saves the flash.
_SSO_HANDOFF_HEAD = """\
<script>
(function () {
  try {
    if (/(?:^|[#&])sso=/.test(window.location.hash || '')) {
      document.documentElement.setAttribute('data-handoff', '1');
    }
  } catch (e) { /* a page that cannot read its own hash simply renders */ }
})();
</script>
"""


# The sign-in page's palette, taken from the active skin.
#
# It used to be three hardcoded browns, which is right for the stock build and
# wrong for any deployment that has rebranded: the one page a visitor sees
# before they are signed in was the one page still wearing the old colours.
# Falls back to those browns when there is no skin to ask, so an unskinned
# install looks exactly as it did.
_LOGIN_PALETTE_FALLBACK = {"bg": "#170d02", "accent": "#ffac02", "fg": "#ffffff"}


def _login_palette() -> dict:
    """``{bg, accent, fg}`` for the sign-in page, from the active skin."""
    palette = dict(_LOGIN_PALETTE_FALLBACK)
    try:
        from hermes_cli.skin_engine import get_active_skin

        skin = get_active_skin()
        for key, token in (("bg", "status_bar_bg"), ("accent", "ui_accent"), ("fg", "banner_text")):
            value = (skin.get_color(token, "") or "").strip()
            # Only a hex colour: these land in a stylesheet, and anything else
            # would either break the rule or be a way to inject one.
            if re.fullmatch(r"#[0-9a-fA-F]{3,8}", value):
                palette[key] = value
    except Exception:  # noqa: BLE001 - a sign-in page must render without a skin
        pass
    return palette


def _render_sso_handoff(provider, next_path: str) -> str:
    """The panel for a provider whose session is minted elsewhere.

    There is no local login flow to offer, so this says where sign-in happens and carries the
    values the bootstrap script needs. Everything displayed comes from the provider's own
    ``sso_handoff_hint`` — core knows nothing about which identity product is behind it.
    """
    try:
        hint = provider.sso_handoff_hint() or {}
    except Exception:  # noqa: BLE001 - a broken provider must still render a login page
        hint = {}
    label = html.escape(str(hint.get("label") or provider.display_name))
    cookie = html.escape(str(hint.get("cookie") or ""), quote=True)
    console = str(hint.get("console_url") or "")
    safe_next = html.escape(next_path, quote=True) if next_path else ""
    link = (
        f'        <a class="provider-btn" href="{html.escape(console, quote=True)}">'
        f'Sign in on {label}</a>\n' if console.startswith(("https://", "http://")) else "")
    return (
        f'      <div class="provider-handoff" data-provider="{html.escape(provider.name, quote=True)}" '
        f'data-cookie="{cookie}" data-next="{safe_next}">\n'
        f'        <div class="form-title">{label}</div>\n'
        f'        <div class="handoff-status" role="status" hidden></div>\n'
        f'{link}'
        f'      </div>'
    )


def render_login_html(*, next_path: str = "") -> str:
    """Return the full HTML for ``GET /login``.

    ``next_path`` is threaded into each provider button/form so the OAuth round
    trip carries it end-to-end. The caller validates it same-origin; it is
    HTML-escaped here as defence in depth.
    """
    providers = list_session_providers()
    if not providers:
        return _EMPTY_HTML
    # URL-encode then HTML-escape, matching the gate's ``_safe_next_target``
    # shape so a round-tripped value is byte-identical.
    next_qs = f"&next={html.escape(quote(next_path, safe=''), quote=True)}" if next_path else ""
    def _render(p) -> str:
        if getattr(p, "supports_password", False):
            return _render_password_form(p, next_path)
        if getattr(p, "supports_sso_handoff", False):
            return _render_sso_handoff(p, next_path)
        return (
            f'      <a class="provider-btn" '
            f'href="/auth/login?provider={html.escape(p.name, quote=True)}{next_qs}">'
            f'Sign in with {html.escape(p.display_name)}</a>')

    buttons = [_render(p) for p in providers]
    scripts = ""
    if any(getattr(p, "supports_password", False) for p in providers):
        scripts += _PASSWORD_FORM_SCRIPT
    if any(getattr(p, "supports_sso_handoff", False) for p in providers):
        scripts += _SSO_HANDOFF_SCRIPT
    handoff = any(getattr(p, "supports_sso_handoff", False) for p in providers)
    return _LOGIN_HTML_TEMPLATE.format(
        provider_buttons="\n".join(buttons),
        password_script=scripts,
        head_script=_SSO_HANDOFF_HEAD if handoff else "",
        **_login_palette(),
    )


def render_native_provider_choice_html(
        *, providers, authorize_path: str, code_challenge: str,
        code_challenge_method: str, redirect_uri: str, state: str) -> str:
    """Provider picker for a native authorize request with more than one interactive provider.

    Every link re-enters ``/auth/native/authorize`` with the SAME desktop PKCE inputs plus an
    explicit ``provider``, so the choice never leaves the validated native flow.
    """
    common = {"code_challenge": code_challenge, "code_challenge_method": code_challenge_method,
              "redirect_uri": redirect_uri, "state": state}
    buttons = []
    for p in providers:
        href = html.escape(f"{authorize_path}?{urlencode({**common, 'provider': p.name})}",
                           quote=True)
        buttons.append(f'      <a class="provider-btn" href="{href}">'
                       f'Sign in with {html.escape(p.display_name)}</a>')
    if not buttons:
        return _EMPTY_HTML
    return _LOGIN_HTML_TEMPLATE.format(
        provider_buttons="\n".join(buttons), password_script="", head_script="",
        **_login_palette())


def _render_password_form(provider, next_path: str) -> str:
    """Username/password form for a ``supports_password`` provider.

    ``next_path`` rides in a hidden field (already validated by the caller,
    HTML-escaped here). The provider name is a ``data-`` attribute so the
    script does not depend on field ordering.
    """
    pname = html.escape(provider.name, quote=True)
    plabel = html.escape(provider.display_name)
    safe_next = html.escape(next_path, quote=True) if next_path else ""
    return (
        f'      <form class="provider-form" data-provider="{pname}" '
        f'autocomplete="on">\n'
        f'        <div class="form-title">Sign in with {plabel}</div>\n'
        f'        <input type="hidden" name="next" value="{safe_next}">\n'
        f'        <label class="field">\n'
        f'          <span class="field-label">Username</span>\n'
        f'          <input class="field-input" type="text" name="username" '
        f'autocomplete="username" autocapitalize="none" '
        f'autocorrect="off" spellcheck="false" required>\n'
        f'        </label>\n'
        f'        <label class="field">\n'
        f'          <span class="field-label">Password</span>\n'
        f'          <input class="field-input" type="password" name="password" '
        f'autocomplete="current-password" required>\n'
        f'        </label>\n'
        f'        <div class="form-error" role="alert" hidden></div>\n'
        f'        <button class="provider-btn" type="submit">Sign in</button>\n'
        f'      </form>'
    )
