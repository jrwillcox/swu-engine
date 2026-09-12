"""
Encoding verifier & deck graduation (Phase 7, Parts B/C).

    python scripts/verify_encoding.py <deck_slug>            # progress + what's left
    python scripts/verify_encoding.py <deck_slug> --group 03 # also run that group's tests
    python scripts/verify_encoding.py <deck_slug> --graduate # run the full graduation gate

It re-runs the planner's (registry-aware, strong) audit, updates
`manifest.json` / `MANIFEST.md` progress in place (stable group ids preserved),
and prints what remains.  ``--group NN`` additionally runs a focused pytest for
that group's cards.  ``--graduate`` runs the automated graduation gate and, on a
full pass, marks the deck shippable in ``docs/decks_status.md`` **and registers
it on the web start screen** (``swu.web.decks.register_ui_deck`` → the catalog
the new-game screen lists), so a graduated deck is immediately selectable without
a code edit.

**Deck graduation criteria** (all must hold; the human still owns the last two):
  1. 100% of the deck's cards classify ``implemented`` (or better).
  2. Every per-card / keyword test green (checked via the fast suite here).
  3. The fast + medium suites pass.
  4. A clean Phase-4-style soak of N seeded games using that exact deck
     (no crashes, no invariant violations).
  5. [manual] A UI smoke pass.
This script checks 1–4 automatically and prints 5 as a checklist item.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_encoding as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DECKS_STATUS = ROOT / "docs" / "decks_status.md"
PY = sys.executable


def _run(cmd: list[str]) -> tuple[int, str]:
    print(f"\n$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out[-4000:])
    return proc.returncode, out


def _load_manifest(slug: str) -> dict:
    p = P.ENCODING_DIR / slug / "manifest.json"
    if not p.exists():
        sys.exit(f"No manifest for '{slug}'. Run: python scripts/plan_encoding.py "
                 f"--deck <path> first.")
    return json.loads(p.read_text(encoding="utf-8"))


def _replan(slug: str, manifest: dict) -> dict:
    """Re-run the planner from the recorded source to refresh progress in place."""
    src = manifest.get("source", {})
    deck, set_code = src.get("deck"), src.get("set_code")
    if not deck and not set_code:
        sys.exit("Manifest has no recorded source; re-run plan_encoding with --deck/--set.")
    _, groups, meta = P.plan(deck, set_code, str(P.DEFAULT_DB), slug_override=slug)
    P.emit(slug, groups, meta)
    return {"groups": groups, "meta": meta}


def _focused_test(slug: str, manifest: dict, group_seq: str) -> int:
    """Run pytest filtered to the named group's card numbers."""
    gid = f"{slug}:{int(group_seq):02d}"
    grp = next((g for g in manifest["groups"] if g["gid"] == gid), None)
    if grp is None:
        sys.exit(f"No group {gid} in manifest.")
    # Build a -k expression from card numbers (matches Test classes / names that
    # mention the number) and keyword name.
    terms = [cid.split("_", 1)[1] for cid in grp["cards"]]
    if grp.get("keyword"):
        terms.append(grp["keyword"])
    kexpr = " or ".join(terms)
    code, _ = _run([PY, "-m", "pytest", "tests/", "-q",
                    "--ignore=tests/test_engine_soak.py",
                    "--ignore=tests/test_hypothesis_engine.py",
                    "-k", kexpr])
    return code


def _print_progress(slug: str, info: dict) -> tuple[int, int]:
    groups = info["groups"]
    prog = info["meta"]["progress"]
    total = info["meta"]["total_deck"]
    playable = info["meta"]["playable_deck"]
    print(f"\nDeck '{slug}': {playable}/{total} cards playable.")
    print(f"{'group id':<22} {'kind':8} {'theme':36} progress")
    print("-" * 80)
    remaining = []
    for g in groups:
        p = prog[g.gid]
        mark = "done" if (p["total"] and p["done"] == p["total"]) else f"{p['done']}/{p['total']}"
        flag = " [NEW PRIMS]" if g.new_primitives else ""
        line = f"{g.gid:<22} {g.kind:8} {g.theme:36} {mark}{flag}"
        print(line.encode("ascii", "replace").decode("ascii"))
        if not (p["total"] and p["done"] == p["total"]):
            remaining.append(g)
    if remaining:
        nxt = _next_group(groups, prog)
        print(f"\n{len(remaining)} group(s) left. Next suggested: "
              f"{nxt.gid if nxt else '—'}")
    else:
        print("\nAll groups complete — eligible for --graduate.")
    return playable, total


def _next_group(groups, prog):
    """Lowest-seq incomplete group whose dependencies are all complete."""
    done_ids = {g.gid for g in groups
                if prog[g.gid]["total"] and prog[g.gid]["done"] == prog[g.gid]["total"]}
    for g in sorted(groups, key=lambda x: x.seq):
        if g.gid in done_ids:
            continue
        if all(d in done_ids for d in g.depends_on):
            return g
    return None


def _graduate(slug: str, info: dict, soak_games: int) -> bool:
    total = info["meta"]["total_deck"]
    playable = info["meta"]["playable_deck"]
    src = info["meta"]["source"]
    deck_path = src.get("deck")

    checklist: list[tuple[str, bool | None, str]] = []

    # 1. 100% playable
    full = (playable == total)
    checklist.append(("100% of deck cards implemented-or-better",
                      full, f"{playable}/{total}"))

    fast_ok = medium_ok = soak_ok = None
    if full:
        # 2/3. fast + medium suites
        code, _ = _run([PY, "-m", "pytest", "tests/",
                        "--ignore=tests/test_engine_soak.py",
                        "--ignore=tests/test_hypothesis_engine.py", "-q"])
        fast_ok = (code == 0)
        checklist.append(("fast suite green", fast_ok, ""))
        code, _ = _run([PY, "-m", "pytest", "tests/test_engine_soak.py", "-q"])
        medium_ok = (code == 0)
        checklist.append(("medium suite green", medium_ok, ""))

        # 4. deck-specific soak (mirror match), invariants on
        if deck_path:
            code, out = _run([PY, "scripts/soak.py", "--games", str(soak_games),
                              "--jobs", "4", "--bots", "heuristic",
                              "--decks", f"{deck_path}:{deck_path}",
                              "--check-invariants", "--quiet"])
            soak_ok = (code == 0) and ("0 failures" in out or "failures: 0" in out.lower()
                                       or "0 invariant" in out.lower() or code == 0)
            checklist.append((f"clean {soak_games}-game soak (this deck)", soak_ok, ""))
        else:
            checklist.append(("deck-specific soak", None, "no deck path (set deck)"))
    else:
        checklist.append(("fast/medium/soak", None, "skipped — deck not 100% yet"))

    checklist.append(("[manual] UI smoke pass", None, "verify in the web UI"))

    print("\n=== Graduation checklist ===")
    for name, ok, note in checklist:
        sym = "[x]" if ok else ("[ ]" if ok is False else "[~]")
        print(f"  {sym} {name}" + (f"  ({note})" if note else ""))

    auto_pass = full and fast_ok and medium_ok and (soak_ok is not False)
    if auto_pass and soak_ok:
        _mark_shippable(slug, total)
        _register_for_ui(slug, info)
        print(f"\nDeck '{slug}' passes the automated gate and is marked shippable "
              f"(complete the manual UI smoke pass). See {DECKS_STATUS}.")
    else:
        print(f"\nDeck '{slug}' is NOT yet shippable — resolve the unchecked items.")
    return bool(auto_pass and soak_ok)


def _mark_shippable(slug: str, total: int) -> None:
    DECKS_STATUS.parent.mkdir(parents=True, exist_ok=True)
    header = "# Deck status registry\n\nDecks marked **shippable** pass the automated graduation gate (100% implemented, fast+medium suites green, clean deck soak). The manual UI smoke pass is the human's final sign-off.\n\n| Deck | Cards | Status |\n|------|------:|--------|\n"
    rows: dict[str, str] = {}
    if DECKS_STATUS.exists():
        for line in DECKS_STATUS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("|") and "Deck" not in line and "---" not in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0]:
                    rows[cells[0]] = line
    rows[slug] = f"| {slug} | {total} | ✅ shippable |"
    body = header + "\n".join(rows[k] for k in sorted(rows)) + "\n"
    DECKS_STATUS.write_text(body, encoding="utf-8")


def _lookup_card(con: sqlite3.Connection, card_id: str, card_type: str) -> sqlite3.Row | None:
    """Resolve a fixture ``"SHD_7"`` id to its DB row, pinned to the card type
    (so a Leader never mis-resolves to its same-numbered Token)."""
    if "_" not in (card_id or ""):
        return None
    set_code, _, num = card_id.partition("_")
    return con.execute(
        "SELECT name, set_code, set_name, raw_json FROM cards "
        "WHERE set_code=? AND card_number=? AND type=?",
        (set_code, num, card_type),
    ).fetchone()


def _aspect_names(raw_json: str | None) -> list[str]:
    """Ordered, de-duplicated aspect names from a card's raw Strapi blob."""
    try:
        data = json.loads(raw_json or "")
        items = (data.get("aspects") or {}).get("data") or []
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []
    names: list[str] = []
    for it in items:
        n = (it.get("attributes") or {}).get("name")
        if n and n not in names:
            names.append(n)
    return names


def _register_for_ui(slug: str, info: dict) -> None:
    """Add a freshly graduated deck to the web start-screen catalog so it is
    selectable without a code edit.  Derives the leader/base names + aspect
    label from the recorded fixture and the card DB.  Best-effort: a failure
    here never fails graduation (the deck is already marked shippable)."""
    deck_path = info["meta"]["source"].get("deck")
    if not deck_path:
        print("UI registration skipped: manifest records no deck path.")
        return
    p = Path(deck_path)
    if not p.is_absolute():
        p = ROOT / deck_path
    try:
        fixture = json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"UI registration skipped: cannot read fixture {p} ({e}).")
        return

    leader_id = (fixture.get("leader") or {}).get("id", "")
    base_id = (fixture.get("base") or {}).get("id", "")
    con = sqlite3.connect(str(P.DEFAULT_DB))
    con.row_factory = sqlite3.Row
    try:
        leader = _lookup_card(con, leader_id, "Leader")
        base = _lookup_card(con, base_id, "Base")
    finally:
        con.close()
    if leader is None:
        print(f"UI registration skipped: leader {leader_id!r} not found in DB.")
        return

    aspects = "/".join(_aspect_names(leader["raw_json"]))
    set_name = leader["set_name"] or leader["set_code"]
    label = f"{leader['name']} — {aspects + ' ' if aspects else ''}({set_name})"
    try:
        from swu.web.decks import register_ui_deck
        register_ui_deck(
            key=slug, label=label,
            leader_name=leader["name"],
            base_name=base["name"] if base else "",
            filename=p.name,
        )
    except Exception as e:  # never fail graduation on a UI-catalog hiccup
        print(f"UI registration skipped: {e!r}.")
        return
    print(f"Registered '{slug}' on the start screen as: {label}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 7 encoding verifier / graduation")
    ap.add_argument("slug")
    ap.add_argument("--group", default=None, help="group seq NN to run focused tests for")
    ap.add_argument("--graduate", action="store_true", help="run the full graduation gate")
    ap.add_argument("--soak-games", type=int, default=200)
    args = ap.parse_args()

    manifest = _load_manifest(args.slug)
    info = _replan(args.slug, manifest)
    manifest = _load_manifest(args.slug)  # reload refreshed file

    _print_progress(args.slug, info)

    if args.group:
        code = _focused_test(args.slug, manifest, args.group)
        print(f"\nFocused tests for group {args.slug}:{int(args.group):02d}: "
              f"{'PASS' if code == 0 else 'FAIL'}")

    if args.graduate:
        _graduate(args.slug, info, args.soak_games)


if __name__ == "__main__":
    main()
