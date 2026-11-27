"""No ability creates a token unit and then chooses a unit the new token could be.

An ability's targets are gathered before its earlier automatic effects run, so in
``[CreateTokenUnit(...), GiveToken(..., TargetSpec(controller="friendly"))]`` the
new token can't be picked (docs/known_deviations.md).  Cards that need it create
the token inside a ``CustomEffect`` and push the choice afterwards (Run Amok
HMW_194, Howl HMW_241, Geonosian Picador HMW_199, Covering the Wing JTL_76).

The audit on 2026-11-27 found no other card affected.  This test keeps it that
way: it fails when a declarative effect list puts a targeted effect that could
match the token after a ``CreateTokenUnit``.
"""
from __future__ import annotations

import dataclasses

import pytest

import swu.cards  # noqa: F401 — populates the registry
from swu.abilities.registry import (
    _REGISTRY, CreateTokenUnit, GiveToken, TargetSpec, TriggerAbility, WhenPlayed,
)
from swu.engine.tokens import _token_unit_def

@pytest.fixture(autouse=True)
def _needs_db():
    """Token definitions come from the card DB (the fixture DB is enough)."""
    from tests.dbpath import require_db
    require_db()


_UNIT_KINDS = {"unit", "unit_or_base", "unit_or_leader", "unit_or_unit_upgrade"}
_SIDE = {"controller": "friendly", "opponent": "enemy", "each": "any"}


def _target_specs(obj, depth=0):
    if depth > 6:
        return []
    if isinstance(obj, TargetSpec):
        return [obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return [t for f in dataclasses.fields(obj)
                for t in _target_specs(getattr(obj, f.name), depth + 1)]
    if isinstance(obj, (list, tuple)):
        return [t for x in obj for t in _target_specs(x, depth + 1)]
    return []


def _effect_lists(obj, depth=0):
    if depth > 6:
        return
    if isinstance(obj, (list, tuple)):
        if obj and all(dataclasses.is_dataclass(x) and not isinstance(x, type) for x in obj):
            yield list(obj)
        for x in obj:
            yield from _effect_lists(x, depth + 1)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _effect_lists(getattr(obj, f.name), depth + 1)


def _could_pick_token(spec: TargetSpec, tok: CreateTokenUnit) -> bool:
    if spec.kind not in _UNIT_KINDS or spec.fixed is not None or spec.names:
        return False
    side = _SIDE.get(tok.player, "any")
    if side != "any" and spec.controller not in ("any", side):
        return False
    tdef = _token_unit_def(tok.token_name)
    arenas = {a.lower() for a in (getattr(tdef, "arenas", ()) or ())}
    if spec.arena and arenas and spec.arena not in arenas:
        return False
    traits = set(getattr(tdef, "traits", ()) or ())
    if spec.traits and not set(spec.traits) <= traits:
        return False
    if spec.traits_any and not set(spec.traits_any) & traits:
        return False
    # A new token is undamaged, unupgraded and not a leader.
    return not set(spec.predicates) & {"damaged", "leader_unit", "upgraded"}


def _offenders(registry):
    out = []
    for (sc, cn), specs in sorted(registry.items()):
        for effs in _effect_lists(specs if isinstance(specs, (list, tuple)) else [specs]):
            for i, e in enumerate(effs):
                if not isinstance(e, CreateTokenUnit):
                    continue
                if any(_could_pick_token(t, e)
                       for later in effs[i + 1:] for t in _target_specs(later)):
                    out.append(f"{sc}_{cn}")
    return sorted(set(out))


def test_the_audit_spots_the_pattern():
    """The check isn't vacuous: it flags a made-up offender."""
    fake = {("ZZT", "2"): [TriggerAbility(trigger=WhenPlayed(), effects=[
        CreateTokenUnit(token_name="Clone Trooper"),
        GiveToken(token_type="Experience", target=TargetSpec(controller="friendly")),
    ])]}
    assert _offenders(fake) == ["ZZT_2"]


def test_no_registered_ability_targets_after_creating_a_token_it_could_pick():
    assert _offenders(_REGISTRY) == [], (
        "these abilities create a token unit, then choose a unit the token could be, "
        "but the choice is offered before the token exists. Create the token in a "
        "CustomEffect and push the choice after it (hmw._then_resolve_option).")
