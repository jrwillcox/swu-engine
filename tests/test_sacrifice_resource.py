"""Framework tests for the 'sacrifice_resource' decision kind (the
sacrifice-resource-cost primitive, group ``shd-han-solo:07``).

Exercise the primitive via the public ``legal_actions`` / ``apply`` interface and
the ``push_sacrifice_resource_for_damage`` seam, independent of any specific card
(Wrecker SHD_154 is covered separately in ``test_shd_cards.py``)."""
from __future__ import annotations

from tests.test_sor_cards import repo, _get_card, _make_state, _place  # noqa: F401
from tests.test_shd_cards import _give_resources


def _setup(repo, *, resources=2, with_enemy=True):
    """A minimal ACTION-phase state: P0 has a source ground unit + ``resources``
    ready resources; optionally a P1 enemy ground unit to be hit."""
    state = _make_state()
    source_ci = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
    enemy_ci = None
    if with_enemy:
        enemy_ci = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
    _give_resources(state, "P0", resources, repo)
    return state, source_ci, enemy_ci


def test_sacrifice_then_deal_damage(repo):
    """Pay the optional cost (defeat a resource), then deal 5 to a ground unit."""
    from swu.engine.actions import (
        legal_actions, apply, push_sacrifice_resource_for_damage,
        SacrificeResource, DeclineSacrifice, ChooseSacrificeTarget,
    )
    state, source_ci, enemy_ci = _setup(repo, resources=3)
    res_before = len(state.player_by_id("P0").resources)

    push_sacrifice_resource_for_damage(
        state, source_ci, amount=5, target_controller="any", target_arena="ground")
    top = state.pending_decisions[-1]
    assert top.kind == "sacrifice_resource"
    assert top.deciding_player_id == "P0"

    # Decide stage: one SacrificeResource per resource + a decline option.
    acts = legal_actions(state)
    assert sum(isinstance(a, SacrificeResource) for a in acts) == res_before
    assert any(isinstance(a, DeclineSacrifice) for a in acts)

    state = apply(state, next(a for a in acts if isinstance(a, SacrificeResource)))
    # One resource was defeated (moved to discard).
    ps = state.player_by_id("P0")
    assert len(ps.resources) == res_before - 1
    assert len(ps.discard) == 1

    # Target stage: deal 5 to the enemy ground unit.
    tgt = next(a for a in legal_actions(state)
               if isinstance(a, ChooseSacrificeTarget)
               and a.target_id == enemy_ci.instance_id)
    state = apply(state, tgt)
    _, hit = state.find_instance(enemy_ci.instance_id)
    assert hit.damage == 5
    assert not state.pending_decisions


def test_decline_does_nothing(repo):
    """Declining the optional sacrifice leaves resources and the board untouched."""
    from swu.engine.actions import (
        legal_actions, apply, push_sacrifice_resource_for_damage, DeclineSacrifice,
    )
    state, source_ci, enemy_ci = _setup(repo, resources=2)
    res_before = len(state.player_by_id("P0").resources)

    push_sacrifice_resource_for_damage(
        state, source_ci, amount=5, target_arena="ground")
    state = apply(state, next(a for a in legal_actions(state)
                              if isinstance(a, DeclineSacrifice)))

    assert len(state.player_by_id("P0").resources) == res_before
    assert not state.player_by_id("P0").discard
    _, enemy = state.find_instance(enemy_ci.instance_id)
    assert enemy.damage == 0
    assert not any(d.kind == "sacrifice_resource" for d in state.pending_decisions)


def test_no_resource_no_decision(repo):
    """With no resource to spend, the optional cost can't be paid — nothing is
    pushed (the ability simply does nothing)."""
    from swu.engine.actions import push_sacrifice_resource_for_damage
    state, source_ci, _ = _setup(repo, resources=0)
    push_sacrifice_resource_for_damage(
        state, source_ci, amount=5, target_arena="ground")
    assert not state.pending_decisions


def test_target_filter_enemy_only(repo):
    """``target_controller='enemy'`` restricts the damage targets to enemy units
    (the source's own ground unit is excluded)."""
    from swu.engine.actions import (
        legal_actions, apply, push_sacrifice_resource_for_damage,
        SacrificeResource, ChooseSacrificeTarget,
    )
    state, source_ci, enemy_ci = _setup(repo, resources=1)
    push_sacrifice_resource_for_damage(
        state, source_ci, amount=5, target_controller="enemy", target_arena="ground")
    state = apply(state, next(a for a in legal_actions(state)
                              if isinstance(a, SacrificeResource)))
    targets = {a.target_id for a in legal_actions(state)
               if isinstance(a, ChooseSacrificeTarget)}
    assert targets == {enemy_ci.instance_id}
    assert source_ci.instance_id not in targets
