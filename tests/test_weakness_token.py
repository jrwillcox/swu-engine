"""The Weakness token (HMW) and the 0-HP floor it depends on.

Weakness is a TokenUpgrade row in the DB (HMW_2's token: −1/−1, no text), so
``tokens.attach_token(..., "Weakness")`` and ``GiveToken("Weakness", …)`` need no
new machinery — exactly like the Beast token UNIT.  What it did need:

* ``compute_hp`` floors at 0, not 1.  A unit reduced to 0 HP is defeated even with
  no damage on it; the old floor of 1 meant no HP debuff could ever kill an
  undamaged unit (a Weakness on a 1-HP unit, a −2/−2 on a 2-HP one).
* The heuristic bot's effect polarity: ``GiveToken`` was always "good", so it would
  have put Weakness tokens on its OWN units.
"""
from __future__ import annotations

from tests.test_sor_cards import repo, _make_state, _place  # noqa: F401
from tests.test_fortify import _unit_def


def _settle(state):
    """Any settled action runs the state-based defeat sweep."""
    from swu.engine.actions import apply, Pass
    state.active_player_index = 0
    return apply(state, Pass())


def _weakness(state, ci):
    from swu.engine import tokens
    return tokens.attach_token(state, state.player_by_id(ci.owner_id), ci, "Weakness")


def _in_arena(state, ci):
    return any(u.instance_id == ci.instance_id
               for p in state.players for u in p.ground_arena + p.space_arena)


def test_weakness_token_is_minus_1_minus_1(repo):
    from swu.engine.actions import compute_power, compute_hp
    state = _make_state()
    unit = _place(state, "P0", _unit_def(power=3, hp=4))
    _weakness(state, unit)
    _weakness(state, unit)
    assert (compute_power(state, unit), compute_hp(state, unit)) == (1, 2)


def test_weakness_on_a_1_hp_unit_defeats_it(repo):
    state = _make_state()
    frail = _place(state, "P0", _unit_def(power=2, hp=1))
    _weakness(state, frail)
    state = _settle(state)
    assert not _in_arena(state, frail)
    # A token ceases to exist with its host: it is in no discard pile.
    assert all(c.card_def.name != "Weakness" for p in state.players for c in p.discard)


def test_hp_debuff_can_defeat_an_undamaged_unit(repo):
    """The floor fix on its own: a −2/−2 on an undamaged 2-HP unit is lethal."""
    from swu.engine.actions import compute_hp
    from swu.engine.state import Modifier
    state = _make_state()
    unit = _place(state, "P0", _unit_def(power=2, hp=2))
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(), source_instance_id=unit.instance_id,
        target_instance_id=unit.instance_id, kind="stats",
        value={"power": -2, "hp": -2}, duration="this_phase"))
    assert compute_hp(state, unit) == 0
    state = _settle(state)
    assert not _in_arena(state, unit)


def test_give_token_effect_attaches_weakness(repo):
    """The ``GiveToken`` resolver arm reaches the Weakness row by name."""
    from swu.abilities.registry import GiveToken, TargetSpec, SELF
    from swu.abilities.resolver import execute_effect
    state = _make_state()
    unit = _place(state, "P0", _unit_def(power=2, hp=3))
    state = execute_effect(state, GiveToken("Weakness", TargetSpec(fixed=SELF)), unit,
                           unit.instance_id, {})
    assert [u.card_def.name for u in unit.attached_upgrades] == ["Weakness"]


def test_bot_reads_a_weakness_gift_as_harmful():
    from swu.abilities.registry import GiveToken, TargetSpec
    from swu.players.heuristic_bot import _effect_polarity
    assert _effect_polarity(GiveToken("Weakness", TargetSpec())) == "bad"
    assert _effect_polarity(GiveToken("Shield", TargetSpec())) == "good"
