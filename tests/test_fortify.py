"""Framework tests for the Fortify keyword (HMW, 2026-11).

Fortify: "Attach this to your base, not a unit."  An upgrade with Fortify has
exactly one legal host, its controller's own base.  It ignores unit-based
attach restrictions, so it is playable with no units in play.  Once attached it
behaves like any other upgrade: "defeat an upgrade" and "return an upgrade"
effects reach it, and the abilities it grants ("Attached base gains: '…'") or
prints for itself are live.

Synthetic cards only (set code ``FTST``), with abilities registered for the
duration of a test, so nothing here depends on how the real HMW cards end up
encoded.  One test at the end plays a real HMW card from the DB.
"""
from __future__ import annotations

import uuid

import pytest

import swu.abilities.registry as _registry
from tests.test_sor_cards import repo, _get_card, _make_state, _place  # noqa: F401


# ── synthetic card defs ───────────────────────────────────────────────────────

def _upgrade_def(name="Bunker", number="1", *, fortify=True, unique=False,
                 cost=1, text=None):
    from swu.cards.models import Upgrade
    return Upgrade(
        id=900000 + int(number), card_uid=None, set_code="FTST", set_name="T",
        card_number=number, name=name, subtitle="Test" if unique else None,
        type="Upgrade", rarity="Common", is_unique=unique, artist=None,
        text=text if text is not None else (
            "Fortify (Attach this to your base, not a unit.)" if fortify else None),
        text_styled=None, rules=None, rules_styled=None, aspects=(),
        keywords=("Fortify",) if fortify else (), traits=("Fortification",),
        arenas=(), image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None, cost=cost,
        upgrade_power=0, upgrade_hp=0,
    )


def _unit_def(name="Trooper", number="50", power=2, hp=3):
    from swu.cards.models import Unit
    return Unit(
        id=900000 + int(number), card_uid=None, set_code="FTST", set_name="T",
        card_number=number, name=name, subtitle=None, type="Unit",
        rarity="Common", is_unique=False, artist=None, text=None,
        text_styled=None, rules=None, rules_styled=None, aspects=(),
        keywords=(), traits=("Trooper",), arenas=("Ground",),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, cost=2, power=power, hp=hp,
    )


# ── state helpers ─────────────────────────────────────────────────────────────

def _to_hand(state, owner_id, card_def):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(instance_id=f"{owner_id}_h_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.HAND)
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _give_resources(state, owner_id, n=5):
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    for i in range(n):
        ps.resources.append(CardInstance(
            instance_id=f"{owner_id}_r{i}_{uuid.uuid4().hex[:4]}",
            card_def=_unit_def(name=f"Res {i}", number=str(60 + i)),
            owner_id=owner_id, zone=Zone.RESOURCES))


def _deck(state, owner_id, n=5):
    from swu.engine.state import CardInstance, Zone
    ps = state.player_by_id(owner_id)
    for i in range(n):
        ps.deck.append(CardInstance(
            instance_id=f"{owner_id}_d{i}_{uuid.uuid4().hex[:4]}",
            card_def=_unit_def(name=f"Deck {i}", number=str(70 + i)),
            owner_id=owner_id, zone=Zone.DECK))


def _attach_to_base(state, owner_id, card_def):
    """Put a Fortify upgrade straight onto ``owner_id``'s base (no triggers)."""
    from swu.engine.state import CardInstance, Zone
    base = state.player_by_id(owner_id).base_instance
    ci = CardInstance(instance_id=f"{owner_id}_f_{uuid.uuid4().hex[:6]}",
                      card_def=card_def, owner_id=owner_id, zone=Zone.BASE_ZONE)
    base.attached_upgrades.append(ci)
    return ci


def _drain(state):
    from swu.engine.actions import apply, legal_actions
    for _ in range(20):
        if not state.pending_decisions:
            return state
        state = apply(state, legal_actions(state)[0])
    raise AssertionError("decision stack did not drain")


def _check_invariants(state):
    from swu.engine import invariants
    invariants.check(state, invariants.CheckContext.from_state(state))


@pytest.fixture
def register():
    """Register synthetic abilities on FTST cards, restoring the registry after."""
    saved: dict = {}

    def _reg(number, specs):
        key = ("FTST", number)
        saved.setdefault(key, _registry._REGISTRY.get(key))
        _registry._REGISTRY[key] = list(specs)

    yield _reg
    for key, prev in saved.items():
        if prev is None:
            _registry._REGISTRY.pop(key, None)
        else:
            _registry._REGISTRY[key] = prev


# ── attaching ─────────────────────────────────────────────────────────────────

def _play_card_actions(state, ci):
    from swu.engine.actions import legal_actions, PlayCard
    return [a for a in legal_actions(state)
            if isinstance(a, PlayCard) and a.instance_id == ci.instance_id]


def test_fortify_upgrade_targets_only_own_base():
    state = _make_state()
    _give_resources(state, "P0")
    _place(state, "P0", _unit_def(name="Mine"))
    _place(state, "P1", _unit_def(name="Theirs", number="51"))
    upg = _to_hand(state, "P0", _upgrade_def())
    acts = _play_card_actions(state, upg)
    assert [a.upgrade_target_id for a in acts] == [
        state.player_by_id("P0").base_instance.instance_id]


def test_fortify_upgrade_playable_with_no_units_in_play():
    state = _make_state()
    _give_resources(state, "P0")
    upg = _to_hand(state, "P0", _upgrade_def())
    assert len(_play_card_actions(state, upg)) == 1


def test_non_fortify_upgrade_never_targets_a_base():
    state = _make_state()
    _give_resources(state, "P0")
    unit = _place(state, "P0", _unit_def())
    upg = _to_hand(state, "P0", _upgrade_def(fortify=False))
    assert [a.upgrade_target_id for a in _play_card_actions(state, upg)] == [
        unit.instance_id]


def test_playing_fortify_attaches_to_base_and_pays():
    from swu.engine.actions import apply, PlayCard
    state = _make_state()
    _give_resources(state, "P0")
    upg = _to_hand(state, "P0", _upgrade_def(cost=2))
    base_id = state.player_by_id("P0").base_instance.instance_id
    state = apply(state, PlayCard(upg.instance_id, base_id))
    ps = state.player_by_id("P0")
    base = ps.base_instance
    assert [u.instance_id for u in base.attached_upgrades] == [upg.instance_id]
    assert base.attached_upgrades[0].zone.name == "BASE_ZONE"
    assert not ps.hand
    assert ps.available_resources == 3
    _check_invariants(state)


@pytest.mark.parametrize("target", ["unit", "enemy_base"])
def test_fortify_rejects_any_host_but_own_base(target):
    from swu.engine.actions import apply, PlayCard, IllegalActionError
    state = _make_state()
    _give_resources(state, "P0")
    unit = _place(state, "P0", _unit_def())
    upg = _to_hand(state, "P0", _upgrade_def())
    bad = (unit.instance_id if target == "unit"
           else state.player_by_id("P1").base_instance.instance_id)
    with pytest.raises(IllegalActionError):
        apply(state, PlayCard(upg.instance_id, bad))


def test_fortify_ignores_a_unit_attach_restriction():
    """A Fortify card whose text also says "Attach to a Vehicle unit" still
    targets only the base, and is playable with no Vehicle in play."""
    state = _make_state()
    _give_resources(state, "P0")
    _place(state, "P0", _unit_def())
    upg = _to_hand(state, "P0", _upgrade_def(
        text="Fortify\nAttach to a Vehicle unit."))
    acts = _play_card_actions(state, upg)
    assert [a.upgrade_target_id for a in acts] == [
        state.player_by_id("P0").base_instance.instance_id]


@pytest.mark.parametrize("viewer", ["P0", "P1"])
def test_base_upgrade_is_public_in_both_views(viewer):
    """A Fortify upgrade is a face-up card in play: both players see it on the
    base in their view (which is what the web client renders)."""
    state = _make_state()
    upg = _attach_to_base(state, "P0", _upgrade_def())
    view = state.view_for(viewer).to_dict()
    zones = view["my"] if viewer == "P0" else view["opponent"]
    base_v = next(c for c in zones["base_zone"] if c["card_type"] == "Base")
    assert [u["instance_id"] for u in base_v["attached_upgrades"]] == [upg.instance_id]
    assert base_v["attached_upgrades"][0]["card_name"] == "Bunker"


# ── removal ───────────────────────────────────────────────────────────────────

def test_defeat_an_upgrade_reaches_a_base_upgrade():
    from swu.abilities.registry import TargetSpec
    from swu.abilities.resolver import _gather_legal_targets
    state = _make_state()
    source = _place(state, "P1", _unit_def())
    upg = _attach_to_base(state, "P0", _upgrade_def())
    assert _gather_legal_targets(
        state, TargetSpec(controller="any", kind="upgrade"), source, {}) == [
        upg.instance_id]


def test_on_unit_predicate_excludes_a_base_upgrade():
    from swu.abilities.registry import TargetSpec
    from swu.abilities.resolver import _gather_legal_targets
    from swu.engine.state import CardInstance
    state = _make_state()
    host = _place(state, "P0", _unit_def())
    on_unit = CardInstance(instance_id="P0_onunit", card_def=_upgrade_def(
        name="Rifle", number="2", fortify=False), owner_id="P0", zone=host.zone)
    host.attached_upgrades.append(on_unit)
    _attach_to_base(state, "P0", _upgrade_def())
    spec = TargetSpec(controller="any", kind="upgrade", predicates=("on_unit",))
    assert _gather_legal_targets(state, spec, host, {}) == ["P0_onunit"]


def test_defeating_a_base_upgrade_discards_it():
    from swu.abilities.resolver import _apply_defeat_unit
    state = _make_state()
    upg = _attach_to_base(state, "P0", _upgrade_def())
    ctx_state = state
    _apply_defeat_unit(state, upg.instance_id)
    ps = ctx_state.player_by_id("P0")
    assert not ps.base_instance.attached_upgrades
    assert [c.instance_id for c in ps.discard] == [upg.instance_id]
    assert ps.discard[0].zone.name == "DISCARD"
    assert ps.base_instance.zone.name == "BASE_ZONE"   # the base is untouched


def test_returning_a_base_upgrade_to_hand():
    from swu.abilities.resolver import _apply_return_to_hand
    state = _make_state()
    upg = _attach_to_base(state, "P0", _upgrade_def())
    _apply_return_to_hand(state, upg.instance_id)
    ps = state.player_by_id("P0")
    assert not ps.base_instance.attached_upgrades
    assert [c.instance_id for c in ps.hand] == [upg.instance_id]


def test_find_upgrade_host_returns_the_base():
    from swu.engine.actions import _find_upgrade_host
    state = _make_state()
    upg = _attach_to_base(state, "P0", _upgrade_def())
    host = _find_upgrade_host(state, upg.instance_id)
    assert host is state.player_by_id("P0").base_instance


def test_two_unique_fortify_copies_trigger_the_unique_rule():
    from swu.engine.actions import apply, PlayCard
    state = _make_state()
    _give_resources(state, "P0")
    doctrine = _upgrade_def(name="Doctrine", number="3", unique=True)
    _attach_to_base(state, "P0", doctrine)
    second = _to_hand(state, "P0", doctrine)
    base_id = state.player_by_id("P0").base_instance.instance_id
    state = apply(state, PlayCard(second.instance_id, base_id))
    assert state.pending_decisions
    assert state.pending_decisions[-1].kind == "resolve_unique"
    state = _drain(state)
    assert len(state.player_by_id("P0").base_instance.attached_upgrades) == 1


# ── abilities on a base-hosted upgrade ────────────────────────────────────────

def test_granted_action_on_base_is_offered_and_resolves(register):
    """"Attached base gains: 'Action [defeat this upgrade]: Draw a card.'" """
    from swu.abilities.registry import (
        ActivatedAbility, DefeatSelf, DrawCards, GrantedAbility)
    from swu.engine.actions import apply, legal_actions, UseAbility
    register("4", [GrantedAbility(ActivatedAbility(
        costs=[DefeatSelf()], effects=[DrawCards(1)]))])
    state = _make_state()
    _deck(state, "P0")
    upg = _attach_to_base(state, "P0", _upgrade_def(name="Cannon", number="4"))
    use = [a for a in legal_actions(state)
           if isinstance(a, UseAbility) and a.source_id == upg.instance_id]
    assert len(use) == 1
    state = _drain(apply(state, use[0]))
    ps = state.player_by_id("P0")
    assert len(ps.hand) == 1
    assert not ps.base_instance.attached_upgrades
    assert [c.instance_id for c in ps.discard] == [upg.instance_id]


def test_granted_trigger_on_base_fires_from_the_base(register):
    """"Attached base gains: 'When a friendly unit is defeated: …'"; the
    effect resolves with the BASE as its source."""
    from swu.abilities.registry import (
        CustomEffect, GrantedAbility, TargetSpec, TriggerAbility, WhenUnitDefeated)
    from swu.engine.actions import _defeat_unit
    seen: list = []

    def _record(state, source_ci, target_id, event_ctx):
        seen.append(source_ci.instance_id)
        return state

    register("5", [GrantedAbility(TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(controller="friendly", kind="unit")),
        effects=[CustomEffect(fn=_record)]))])
    state = _make_state()
    _attach_to_base(state, "P0", _upgrade_def(name="Memorial", number="5"))
    unit = _place(state, "P0", _unit_def())
    ps = state.player_by_id("P0")
    _defeat_unit(state, ps, unit)
    _drain(state)
    assert seen == [ps.base_instance.instance_id]


def test_own_trigger_on_base_upgrade_fires_from_the_upgrade(register):
    """A trigger printed on the Fortify upgrade itself ("When a ground unit
    enters play: …", Trap Field HMW_171) resolves with the UPGRADE as source."""
    from swu.abilities.registry import (
        CustomEffect, TargetSpec, TriggerAbility, WhenUnitEntersPlay)
    from tests.test_sor_cards import _fire_when_played
    seen: list = []

    def _record(state, source_ci, target_id, event_ctx):
        seen.append(source_ci.instance_id)
        return state

    register("6", [TriggerAbility(
        trigger=WhenUnitEntersPlay(filter=TargetSpec(controller="any", kind="unit")),
        effects=[CustomEffect(fn=_record)])])
    state = _make_state()
    upg = _attach_to_base(state, "P0", _upgrade_def(name="Trap", number="6"))
    unit = _place(state, "P1", _unit_def())
    state = _fire_when_played(state, unit)
    _drain(state)
    assert seen == [upg.instance_id]


def test_when_played_on_fortify_upgrade_fires_exactly_once(register):
    from swu.abilities.registry import CustomEffect, TriggerAbility, WhenPlayed
    from swu.engine.actions import apply, PlayCard
    seen: list = []

    def _record(state, source_ci, target_id, event_ctx):
        seen.append(source_ci.instance_id)
        return state

    register("7", [TriggerAbility(trigger=WhenPlayed(),
                                  effects=[CustomEffect(fn=_record)])])
    state = _make_state()
    _give_resources(state, "P0")
    upg = _to_hand(state, "P0", _upgrade_def(name="Agency", number="7"))
    base_id = state.player_by_id("P0").base_instance.instance_id
    _drain(apply(state, PlayCard(upg.instance_id, base_id)))
    assert seen == [upg.instance_id]


def test_opponent_discard_fortify_upgrade_is_not_offered():
    """A Fortify upgrade in an OPPONENT's discard is not offered to a
    play-from-any-discard effect (A Fine Addition TWI_40); its host would be
    read from the wrong player."""
    from swu.engine.actions.upgrades import _affordable_hand_upgrades
    from swu.engine.state import CardInstance, Zone
    state = _make_state()
    theirs = CardInstance(instance_id="P1_disc_f", card_def=_upgrade_def(),
                          owner_id="P1", zone=Zone.DISCARD)
    state.player_by_id("P1").discard.append(theirs)
    mine = CardInstance(instance_id="P0_disc_f", card_def=_upgrade_def(number="8"),
                        owner_id="P0", zone=Zone.DISCARD)
    state.player_by_id("P0").discard.append(mine)
    ctx = {"controller_id": "P0", "include_discards": True, "free": True}
    assert _affordable_hand_upgrades(state, ctx) == ["P0_disc_f"]


# ── a real HMW card ───────────────────────────────────────────────────────────

def test_real_fortify_card_plays_onto_base(repo):  # noqa: F811
    """Carbonite Chamber HMW_95 is a cost-1 Fortify upgrade."""
    from swu.engine.actions import apply, PlayCard
    chamber = _get_card(repo, "HMW", "95")
    state = _make_state()
    _give_resources(state, "P0")
    _place(state, "P0", _unit_def())
    ci = _to_hand(state, "P0", chamber)
    acts = _play_card_actions(state, ci)
    base_id = state.player_by_id("P0").base_instance.instance_id
    assert [a.upgrade_target_id for a in acts] == [base_id]
    state = apply(state, acts[0])
    assert [u.instance_id for u in state.player_by_id("P0").base_instance
            .attached_upgrades] == [ci.instance_id]
    _check_invariants(state)
    assert isinstance(acts[0], PlayCard)
