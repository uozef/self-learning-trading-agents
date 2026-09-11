#!/usr/bin/env python3
"""Rebrand the user-visible product name to "Recursive Self Learning Agents".

Deliberately narrow: it rewrites display copy only. Python/TypeScript
identifiers, i18n keys, env vars (``HERMES_*``), HTTP headers
(``X-Hermes-Session-Token``), API routes (``/api/hermes/...``), package
names and import paths keep the ``hermes`` spelling, because the runtime
resolves configuration and modules through them.

Run from the repository root::

    python3 scripts/rebrand_rsla.py [--check]
"""

from __future__ import annotations

import argparse
import re
import sys

from pathlib import Path

FULL_NAME = "Recursive Self Learning Agents"
SHORT_NAME = "RSLA"

# Files whose *string literals* carry the product name in front of a user.
TARGETS = (
    "web/index.html",
    "web/src/**/*.ts",
    "web/src/**/*.tsx",
    # Shared with the desktop app and bundled into the dashboard's chat chunk.
    "apps/shared/src/**/*.ts",
    "locales/*.yaml",
    "hermes_cli/dashboard_auth/login_page.py",
    # The one banner line an operator sees in the container log.
    "hermes_cli/web_server.py",
)

# ``Hermes Agent`` is the full product name; a bare ``Hermes`` inside a
# sentence reads better as the short form.
# The hyphen lookarounds keep ``X-Hermes-Session-Token`` intact: it is a wire
# header the dashboard and the bundle must still agree on.
PRODUCT = re.compile(r"(?<![A-Za-z-])Hermes Agent(?![A-Za-z-])")
BARE = re.compile(r"(?<![A-Za-z-])Hermes(?![A-Za-z-])")

# i18n keys are camelCase (``updateHermes``) so the lookarounds above already
# skip them. These are the remaining spellings that must survive verbatim.
PRESERVE = (
    "HERMES_",
    "X-Hermes",
    "__HERMES",
    "/api/hermes",
    "hermes_cli",
    "@hermes/",
)


def rewrite(text: str) -> str:
    out = PRODUCT.sub(FULL_NAME, text)
    return BARE.sub(SHORT_NAME, out)


def iter_targets(root: Path):
    for pattern in TARGETS:
        if "*" in pattern:
            yield from sorted(root.glob(pattern))
        else:
            candidate = root / pattern
            if candidate.exists():
                yield candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if any file still needs rewriting")
    parser.add_argument("--root", default=".", type=Path)
    args = parser.parse_args()

    changed: list[Path] = []
    for path in iter_targets(args.root):
        original = path.read_text(encoding="utf-8")
        updated = rewrite(original)
        if updated == original:
            continue
        for token in PRESERVE:
            if original.count(token) != updated.count(token):
                print(f"refusing to rewrite {path}: would damage {token!r}", file=sys.stderr)
                return 2
        changed.append(path)
        if not args.check:
            path.write_text(updated, encoding="utf-8")

    if args.check:
        for path in changed:
            print(f"needs rebrand: {path}")
        return 1 if changed else 0

    for path in changed:
        print(f"rebranded {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
