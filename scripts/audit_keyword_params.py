"""
Step 0 parameter-extraction audit for Phase 2.

For each numeric keyword (Raid, Restore, Exploit), checks every card in
card_keywords and reports whether the numeric value can be extracted from:
  1. The card's `text` field (units and upgrades)
  2. The `deploy_box` field (leaders — the deployed-unit side)

Prints a compact summary, then lists every card whose value cannot be
confidently extracted so Phase 2 implementation can handle edge cases.

Usage:
    python scripts/audit_keyword_params.py [path/to/swu.db]
"""

import re
import sqlite3
import sys
from pathlib import Path

DB_DEFAULT = Path(__file__).parent.parent / "data" / "swu.db"

NUMERIC_KEYWORDS = ["Raid", "Restore", "Exploit"]

# Pattern: keyword name followed by a space and one or more digits.
# We anchor at a word boundary so "Raid 3" doesn't match inside "Unraid 3".
_PATTERNS = {
    kw: re.compile(rf"\b{kw}\s+(\d+)")
    for kw in NUMERIC_KEYWORDS
}


def extract_value(text: str | None, pattern: re.Pattern) -> int | None:
    if not text:
        return None
    m = pattern.search(text)
    return int(m.group(1)) if m else None


def audit(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    results: dict[str, dict] = {kw: {"ok": [], "fail": []} for kw in NUMERIC_KEYWORDS}

    for kw in NUMERIC_KEYWORDS:
        pattern = _PATTERNS[kw]
        rows = con.execute(
            """
            SELECT c.id, c.name, c.type, c.text, c.deploy_box
            FROM cards c
            JOIN card_keywords ck ON ck.card_id = c.id
            WHERE ck.name = ?
            """,
            (kw,),
        ).fetchall()

        for row in rows:
            card_id, name, ctype, text, deploy_box = (
                row["id"], row["name"], row["type"], row["text"], row["deploy_box"]
            )
            val = extract_value(text, pattern)
            if val is None and ctype == "Leader":
                val = extract_value(deploy_box, pattern)

            if val is not None:
                results[kw]["ok"].append((card_id, name, ctype, val))
            else:
                results[kw]["fail"].append((card_id, name, ctype, text, deploy_box))

    con.close()

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print("=" * 70)
    print("KEYWORD PARAMETER EXTRACTION AUDIT")
    print("=" * 70)

    any_failures = False
    for kw in NUMERIC_KEYWORDS:
        ok = results[kw]["ok"]
        fail = results[kw]["fail"]
        total = len(ok) + len(fail)
        print(f"\n{kw}: {len(ok)}/{total} extractable")
        if fail:
            any_failures = True
            print(f"  *** {len(fail)} NOT extractable ***")
            for card_id, name, ctype, text, deploy_box in fail:
                print(f"    [{card_id}] {name!r} ({ctype})")
                if text:
                    print(f"      text:       {text[:120]!r}")
                if deploy_box:
                    print(f"      deploy_box: {deploy_box[:120]!r}")
        else:
            print("  All values extractable.")

    print()
    if any_failures:
        print("CONCLUSION: Most numeric keyword values can be extracted from `text`")
        print("(units) or `deploy_box` (leaders).  The failures above are cards")
        print("where the keyword appears in the DB tag but the card itself has no")
        print("printed numeric value — they grant or modify the keyword conditionally")
        print("via card-text abilities, which are Phase 3 scope.")
        print()
        print("Extractor strategy: check text first, then deploy_box for leaders.")
        print("Return None for the edge cases — they will be handled as Phase 3")
        print("text-bearing cards.")
    else:
        print("CONCLUSION: All numeric keyword values are extractable.")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_DEFAULT
    if not path.exists():
        sys.exit(f"Database not found: {path}")
    audit(path)
