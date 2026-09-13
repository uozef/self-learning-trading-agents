// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  embedThemeName,
  isChatOnlyEmbed,
  resetChatOnlyEmbedForTests,
} from "./embed";

/**
 * Chat-only mode is a contract with another product's console, so what is
 * pinned is the contract: which URL turns it on, that it survives the auth
 * gate's redirect, that it is never inferred from being framed, and that a
 * theme it carries cannot leak into an ordinary load.
 */

function visit(search: string): void {
  resetChatOnlyEmbedForTests();
  window.history.replaceState({}, "", `/${search}`);
}

describe("chat-only embed mode", () => {
  beforeEach(() => {
    resetChatOnlyEmbedForTests();
  });

  afterEach(() => {
    resetChatOnlyEmbedForTests();
    window.history.replaceState({}, "", "/");
  });

  it("is off for an ordinary load", () => {
    visit("");
    expect(isChatOnlyEmbed()).toBe(false);
  });

  it("is on when the embedder asks", () => {
    visit("?embed=chat");
    expect(isChatOnlyEmbed()).toBe(true);
  });

  it("survives the URL the app navigates to next", () => {
    // The auth gate redirects an unauthenticated load to /login and back, and
    // the SPA rewrites its own query; without the latch the chrome would
    // reappear the moment either happened.
    visit("?embed=chat");
    expect(isChatOnlyEmbed()).toBe(true);
    window.history.replaceState({}, "", "/chat");
    resetResolvedOnly();
    expect(isChatOnlyEmbed()).toBe(true);
  });

  it("ignores a value that is not the one we publish", () => {
    visit("?embed=1");
    expect(isChatOnlyEmbed()).toBe(false);
    visit("?embed=full");
    expect(isChatOnlyEmbed()).toBe(false);
  });

  it("is never inferred from anything but the URL", () => {
    // Sniffing `window !== window.top` would strip the chrome from any framed
    // page, including an operator's own preview, and do it invisibly.
    visit("");
    expect(isChatOnlyEmbed()).toBe(false);
  });
});

describe("the theme an embedder asks for", () => {
  beforeEach(() => {
    resetChatOnlyEmbedForTests();
  });

  afterEach(() => {
    resetChatOnlyEmbedForTests();
    window.history.replaceState({}, "", "/");
  });

  it("is carried alongside the mode", () => {
    visit("?embed=chat&theme=liveagents");
    expect(embedThemeName()).toBe("liveagents");
  });

  it("is null when none was asked for", () => {
    visit("?embed=chat");
    expect(embedThemeName()).toBeNull();
  });

  it("is refused outside chat-only mode", () => {
    // Otherwise any link could restyle somebody's dashboard.
    visit("?theme=liveagents");
    expect(embedThemeName()).toBeNull();
  });

  it("refuses a name that is not name-shaped", () => {
    visit("?embed=chat&theme=../../etc/passwd");
    expect(embedThemeName()).toBeNull();
    visit("?embed=chat&theme=<script>");
    expect(embedThemeName()).toBeNull();
  });

  it("survives a later navigation like the mode does", () => {
    visit("?embed=chat&theme=liveagents-light");
    expect(embedThemeName()).toBe("liveagents-light");
    window.history.replaceState({}, "", "/chat");
    resetResolvedOnly();
    expect(embedThemeName()).toBe("liveagents-light");
  });
});

/**
 * Forget the per-load memo without clearing the session latch.
 *
 * A reload is exactly this: module state goes, `sessionStorage` stays. The
 * exported reset clears both, which is right for isolating a test and wrong for
 * proving that the latch is what carries the flag across a redirect.
 */
function resetResolvedOnly(): void {
  const mode = sessionStorage.getItem("hermes-embed-mode");
  const theme = sessionStorage.getItem("hermes-embed-theme");
  resetChatOnlyEmbedForTests();
  if (mode) sessionStorage.setItem("hermes-embed-mode", mode);
  if (theme) sessionStorage.setItem("hermes-embed-theme", theme);
}
