"""The contract ``swu.engine.actions`` owes the rest of the tree.

``engine/actions.py`` grew to 24,788 lines with no ``__all__``, so all 638 of its
top-level names became de facto public — and 3,532 ``from swu.engine.actions
import …`` sites across 89 files now depend on them.  Splitting it into a package
is safe only if that surface is preserved exactly, which is what these tests
assert.  They are cheap (no database, no game played) and they turn "did we break
one of 3,532 imports?" into a millisecond check.

Two failure modes are specifically guarded:

*Attribute access.*  ``_fire_bounty_observers`` and ``_fire_hand_discard_observers``
are reached **only** as ``A._fire_…`` via ``from swu.engine import actions as A``
(``tests/test_shd_cards.py``).  A facade whose ``__all__`` was built by grepping
``from … import`` lines would silently omit them, and nothing but those card tests
would notice.  The surface file is built from the module's *definitions*, not its
import sites, so they are covered.

*The wire protocol.*  ``web/serializers.py`` sends ``type(action).__name__`` as an
action's ``kind`` and ``asdict(action)`` as its ``params``, so every Action class
name and dataclass field name below is part of the HTTP API the React frontend is
written against.  Moving a class between modules is invisible to it; renaming a
class or a field is a breaking change.

Both golden files are regenerated only deliberately.  If a test here fails, the
question to answer first is "which caller did I just break?", not "how do I update
the fixture?".
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SURFACE_FILE = FIXTURES / "actions_public_surface.json"
WIRE_FILE = FIXTURES / "actions_wire_contract.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def actions_module():
    import swu.engine.actions as module
    return module


def test_every_public_name_still_resolves(actions_module):
    """All 638 measured names are still reachable on ``swu.engine.actions``.

    This is the single assertion that makes the package split safe: whether a name
    lives in the facade or in a submodule, importing it from the historical path
    must keep working.
    """
    expected = _load(SURFACE_FILE)["names"]
    missing = [name for name in expected if not hasattr(actions_module, name)]
    assert not missing, (
        f"{len(missing)} name(s) no longer resolve on swu.engine.actions: "
        f"{missing[:20]}{' …' if len(missing) > 20 else ''}\n"
        "Every one is imported elsewhere in the tree. Re-export it from the "
        "package __init__ rather than deleting it from the surface file."
    )


def test_attribute_only_observers_are_bound(actions_module):
    """The two observers no ``from … import`` line mentions.

    Called as ``A._fire_bounty_observers(...)`` after ``from swu.engine import
    actions as A``.  Pinned separately from the bulk surface check because this is
    the case a mechanical facade generator gets wrong.
    """
    for name in ("_fire_bounty_observers", "_fire_hand_discard_observers"):
        assert callable(getattr(actions_module, name, None)), (
            f"{name} must be bound on the package: tests/test_shd_cards.py reaches "
            "it by attribute access, which no import grep would reveal."
        )


def test_action_class_names_and_fields_match_the_wire_contract(actions_module):
    """The frontend's view of the action API is unchanged.

    ``kind`` is the class name and ``params`` the dataclass fields, so this is a
    golden test over the serialised shape of every action the engine can offer.
    """
    golden = _load(WIRE_FILE)["actions"]

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    live = {}
    for cls in set(subclasses(actions_module.Action)):
        live[cls.__name__] = (
            [f.name for f in dataclasses.fields(cls)]
            if dataclasses.is_dataclass(cls) else []
        )

    assert sorted(live) == sorted(golden), (
        "the set of Action class names changed — this is the frontend's `kind` "
        f"vocabulary.\n  added:   {sorted(set(live) - set(golden))}\n"
        f"  removed: {sorted(set(golden) - set(live))}"
    )

    drifted = {k: {"was": golden[k], "now": live[k]} for k in golden if golden[k] != live[k]}
    assert not drifted, (
        f"dataclass fields changed on {len(drifted)} action(s) — these are the "
        f"`params` keys the frontend reads:\n{json.dumps(drifted, indent=2)}"
    )


def test_action_class_names_are_unique(actions_module):
    """No two Action classes may share a name.

    ``kind`` is only a class name, so two classes called the same thing would be
    indistinguishable on the wire.  Splitting one module into fourteen makes an
    accidental duplicate possible for the first time.
    """
    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    names = [cls.__name__ for cls in subclasses(actions_module.Action)]
    seen, dupes = set(), set()
    for name in names:
        if name in seen:
            dupes.add(name)
        seen.add(name)
    assert not dupes, f"duplicate Action class name(s): {sorted(dupes)}"
