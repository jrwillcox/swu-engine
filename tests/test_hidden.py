"""
Hidden keyword — synthetic-card framework tests (jabba-the-hutt:02).

Hidden ("This unit can't be attacked if it was played this phase") removes a unit
from the legal defenders for the action phase it entered play, then lifts on the
next round (the protection is keyed off ``game_memory.units_played_this_phase``,
which is cleared at the REGROUP→ACTION rollover).  These tests grant Hidden to a
plain unit via a keyword_grant modifier and exercise the keyword purely through
the public ``legal_actions`` interface, independent of any specific real card.
"""
from __future__ import annotations

from tests.test_sor_cards import repo, _get_card, _make_state, _place  # noqa: F401

from swu.engine.actions import legal_actions, AttackWithUnit
from swu.engine.keywords import has_keyword, Keyword


def _grant_hidden(state, ci):
    """Grant the Hidden keyword to ``ci`` via a keyword_grant modifier."""
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=ci.instance_id,
        target_instance_id=ci.instance_id,
        kind="keyword_grant",
        value={"keyword": "Hidden", "value": 0},
        duration="this_phase",
    ))


def _attacks_on(state, attacker, target):
    return [a for a in legal_actions(state)
            if isinstance(a, AttackWithUnit)
            and a.attacker_id == attacker.instance_id
            and a.defender_id == target.instance_id]


def _base_attacks(state, attacker):
    return [a for a in legal_actions(state)
            if isinstance(a, AttackWithUnit)
            and a.attacker_id == attacker.instance_id
            and a.defender_id is None]


def test_hidden_unit_played_this_phase_cannot_be_attacked(repo):
    """A Hidden unit whose instance is in units_played_this_phase is not a legal
    defender, but the base is still attackable."""
    vanilla = _get_card(repo, "SOR", "46")
    state = _make_state()
    attacker = _place(state, "P0", vanilla, "ground")     # P0 active, ready
    defender = _place(state, "P1", vanilla, "ground")
    _grant_hidden(state, defender)
    assert has_keyword(state, defender, Keyword.HIDDEN)
    state.game_memory.units_played_this_phase.add(defender.instance_id)

    assert _attacks_on(state, attacker, defender) == []   # protected
    assert _base_attacks(state, attacker)                 # base still attackable


def test_hidden_unit_attackable_after_phase_clears(repo):
    """Once the unit is no longer 'played this phase' (round rolled over), the
    Hidden protection lifts and it can be attacked."""
    vanilla = _get_card(repo, "SOR", "46")
    state = _make_state()
    attacker = _place(state, "P0", vanilla, "ground")
    defender = _place(state, "P1", vanilla, "ground")
    _grant_hidden(state, defender)
    # NOT added to units_played_this_phase → not protected.
    assert _attacks_on(state, attacker, defender)


def test_non_hidden_unit_played_this_phase_is_attackable(repo):
    """Being played this phase only matters for a unit that actually has Hidden."""
    vanilla = _get_card(repo, "SOR", "46")
    state = _make_state()
    attacker = _place(state, "P0", vanilla, "ground")
    defender = _place(state, "P1", vanilla, "ground")
    state.game_memory.units_played_this_phase.add(defender.instance_id)
    assert _attacks_on(state, attacker, defender)


def test_hidden_sentinel_just_played_does_not_force_attack(repo):
    """A freshly-played Hidden + Sentinel unit neither can be attacked nor forces
    enemy units to attack it — the base and other units stay open."""
    vanilla = _get_card(repo, "SOR", "46")
    state = _make_state()
    attacker = _place(state, "P0", vanilla, "ground")
    hidden_sentinel = _place(state, "P1", vanilla, "ground")
    other = _place(state, "P1", vanilla, "ground")
    # Grant both Hidden and Sentinel to the freshly-played unit.
    _grant_hidden(state, hidden_sentinel)
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=hidden_sentinel.instance_id,
        target_instance_id=hidden_sentinel.instance_id,
        kind="keyword_grant",
        value={"keyword": "Sentinel", "value": 0},
        duration="this_phase",
    ))
    state.game_memory.units_played_this_phase.add(hidden_sentinel.instance_id)

    assert _attacks_on(state, attacker, hidden_sentinel) == []  # can't attack it
    assert _attacks_on(state, attacker, other)                  # other unit open
    assert _base_attacks(state, attacker)                       # base open too
