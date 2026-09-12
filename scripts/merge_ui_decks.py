#!/usr/bin/env python3
"""Union two ui_decks.json registries by deck ``key``.

Usage:  merge_ui_decks.py DEV LIVE

Writes the merged list back to LIVE. DEV rows win on a key clash (they carry the
freshly-graduated decks); LIVE-only rows are preserved. Order: DEV rows first
(first-seen key wins), then any LIVE-only rows.

This is the server-side analogue of deploy.ps1's Step 4b registry sync: a deck
graduated in DEV records itself in DEV's data/ui_decks.json, but deploys mirror
code only (never data/), so the family server's registry would otherwise never
learn about it. Run in the server's WSL after a code sync. Stdlib only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: merge_ui_decks.py DEV LIVE")
    dev, live = load(sys.argv[1]), load(sys.argv[2])

    merged: list[dict] = []
    seen: set[str] = set()
    for row in list(dev) + list(live):
        key = row.get("key")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(row)

    # Write UTF-8, no BOM, trailing newline — matches what register_ui_deck emits
    # and what Python's json.loads(read_text(encoding="utf-8")) expects.
    Path(sys.argv[2]).write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    live_keys = {r.get("key") for r in live}
    added = [r.get("key") for r in dev if r.get("key") and r.get("key") not in live_keys]
    print(f"merged {len(merged)} decks; added: {', '.join(added) if added else '(none)'}")


if __name__ == "__main__":
    main()
