"""Every ``note_hand_or_deck_discard`` call says where the card came from.

The helper feeds two ledgers: one for any hand-or-deck discard (Kylo's TIE
Silencer SHD_135, That's a Rock LAW_206) and a hand-only one (Kylo's TIE Silencer
IC27_63, "When this unit is discarded from your hand").  A call that passes neither
``from_hand`` nor ``from_deck`` leaves the reader to guess, and a hand discard
that forgets ``from_hand=True`` silently stops IC27_63 working.  So every call
site must pass one of them explicitly (a deck mill that doesn't feed Sebulba's
Podracer LAW_176 passes ``from_hand=False``).
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "swu"


def _calls():
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
            if name == "note_hand_or_deck_discard":
                yield path.relative_to(SRC.parent), node


def test_every_call_says_hand_or_deck():
    calls = list(_calls())
    assert len(calls) > 20, "the call-site scan found too few calls; has the helper moved?"
    missing = [f"{p}:{n.lineno}" for p, n in calls
               if not {k.arg for k in n.keywords} & {"from_hand", "from_deck"}]
    assert not missing, "pass from_hand=True (hand) or from_deck / from_hand=False (deck): " \
        + ", ".join(missing)
