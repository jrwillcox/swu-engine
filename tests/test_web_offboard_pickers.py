"""Every decision that asks the player to pick a card they can't click on the
board must have an on-screen picker.

A decision whose context carries ``"candidates"`` (card identities for the UI)
is choosing among cards in the deck, the discard pile or under a captor — none
of which the board renders as clickable.  The frontend's generic chooser
(``Table.tsx``'s ``chooser`` switch → ``ChooseCardsViewer``) must handle each
such kind, or the game soft-locks: the engine waits on a Select action the
player has no way to press.

Regression: bug report 2026-10-14 "I can't resource my expendable mercenary
from the discard pile" — ``resource_from_discard`` (Expendable Mercenary
LAW_159) had no chooser case and no prompt.
"""
import re
from pathlib import Path

from swu.web.session import _PROMPTS

ROOT = Path(__file__).resolve().parents[1]
ACTIONS_DIR = ROOT / "src" / "swu" / "engine" / "actions"
TABLE_TSX = ROOT / "web" / "src" / "components" / "Table.tsx"

# Kinds whose candidates ARE clickable board subjects, so need no chooser.
BOARD_CLICKABLE = {
    "discard_for_experience",  # hand cards
    "play_resource_units",     # resource-row cards
}

_PUSH = re.compile(r'kind="(\w+)",\s*context=\{(.*?)\n\s*\},', re.S)


def _offboard_kinds() -> set[str]:
    kinds: set[str] = set()
    for path in ACTIONS_DIR.glob("*.py"):
        for kind, body in _PUSH.findall(path.read_text(encoding="utf-8")):
            if '"candidates":' in body:
                kinds.add(kind)
    return kinds


def _chooser_cases() -> set[str]:
    src = TABLE_TSX.read_text(encoding="utf-8")
    start = src.index("const chooser = (() => {")
    end = src.index("})();", start)
    return set(re.findall(r'case "(\w+)":', src[start:end]))


def test_scan_finds_the_known_offboard_kinds():
    kinds = _offboard_kinds()
    # Guard the regex itself — an empty scan would pass every check below.
    assert {"resource_from_discard", "deck_search", "return_from_discard"} <= kinds


def test_every_offboard_decision_has_a_chooser():
    missing = _offboard_kinds() - BOARD_CLICKABLE - _chooser_cases()
    assert not missing, (
        f"decision kinds with off-board candidates but no Table.tsx chooser case "
        f"(the player can't answer them): {sorted(missing)}")


def test_every_offboard_decision_has_a_prompt():
    missing = _offboard_kinds() - set(_PROMPTS)
    assert not missing, f"no session._PROMPTS entry for: {sorted(missing)}"
