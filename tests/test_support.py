"""
Support keyword — synthetic-card framework tests (ash-set:01).

Support:

    "When you play this unit / deploy this leader, you may attack with another
     unit.  It gains this unit's other abilities for this attack."

Engine shape (no new decision kind):
  * ``keyword_triggers._support_enters_play_listener`` / ``_support_deploy_listener``
    push the existing ``granted_attack`` decision with ``optional=True`` (the "you
    may"), ``exclude_source=True`` (the "another unit") and the new
    ``borrow_abilities=True`` rider — and only when some other unit could actually
    attack (the "don't offer a no-op" rule).
  * ``AttackWithUnit`` lands ONE ``borrowed_abilities`` this-attack modifier on the
    chosen attacker naming the Support card as lender.
  * ``state.borrowed_ability_sources`` is the single read layer, consulted by the
    keyword layer (``has_keyword`` / ``keyword_value``) and by
    ``resolver._collect_triggers`` (the lender's triggers, resolving FROM the
    attacker).

These tests grant Support to plain units via a keyword_grant modifier and drive
everything through the public ``legal_actions`` / ``apply`` interface, so they are
independent of any specific ASH card; two closing tests pin the real cards.
"""
from __future__ import annotations

from tests.test_sor_cards import (  # noqa: F401
    repo, _get_card, _make_state, _place, _push_deck_top, _get_leader,
)

from swu.engine.actions import (
    legal_actions, apply, AttackWithUnit, DeclineGrantedAttack, compute_power,
)
from swu.engine.keywords import has_keyword, keyword_value, Keyword


VANILLA = ("SOR", "46")          # Consular Security Force 3/7, no text
ON_ATTACK_DRAW = ("LAW", "107")  # Swoop Bike Marauder — "On Attack: Draw a card."


def _grant_keyword(state, ci, keyword: str, value: int = 0):
    """Grant ``keyword`` to ``ci`` for this phase via a keyword_grant modifier."""
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=ci.instance_id,
        target_instance_id=ci.instance_id,
        kind="keyword_grant",
        value={"keyword": keyword, "value": value},
        duration="this_phase",
    ))


def _enters_play(state, ci):
    """Fire the Phase-2 enter-play keyword bus for ``ci`` (what ``_put_unit_in_play``
    does), so Shielded / Support / Ambush listeners see it."""
    from swu.engine.triggers import get_bus
    from swu.engine.events import UnitEntersPlay
    evt = UnitEntersPlay(
        player_id=ci.owner_id, instance_id=ci.instance_id,
        card_name=ci.card_def.display_name, arena=ci.arena() or "Ground",
    )
    state.event_log.append(evt)
    return get_bus().fire(state, evt)


def _deploys(state, leader_ci):
    """Fire the LeaderDeployed bus event for an already-deployed leader."""
    from swu.engine.triggers import get_bus
    from swu.engine.events import LeaderDeployed
    evt = LeaderDeployed(
        player_id=leader_ci.owner_id, instance_id=leader_ci.instance_id,
        leader_name=leader_ci.card_def.display_name,
        arena=leader_ci.arena() or "Ground",
    )
    state.event_log.append(evt)
    return get_bus().fire(state, evt)


def _granted(state):
    return [d for d in state.pending_decisions if d.kind == "granted_attack"]


def _attack_options(state):
    return [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]


def _support_unit(state, owner, card_def, arena="ground"):
    ci = _place(state, owner, card_def, arena)
    _grant_keyword(state, ci, "Support")
    return ci


# ── The decision itself ───────────────────────────────────────────────────────

def test_support_pushes_a_granted_attack_for_another_unit(repo):
    """Playing a Support unit offers an attack by ANOTHER friendly unit — never
    by the Support unit itself."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    _place(state, "P1", vanilla)                      # something to attack
    supporter = _support_unit(state, "P0", vanilla)

    state = _enters_play(state, supporter)
    assert len(_granted(state)) == 1

    attackers = {a.attacker_id for a in _attack_options(state)}
    assert ally.instance_id in attackers
    assert supporter.instance_id not in attackers      # "another unit"


def test_support_is_not_offered_when_no_other_unit_can_attack(repo):
    """Alone on the board, the Support unit has nobody to support — no prompt."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    supporter = _support_unit(state, "P0", vanilla)

    state = _enters_play(state, supporter)
    assert _granted(state) == []


def test_support_attack_may_be_declined(repo):
    """"You MAY attack" — a decline is always offered and fizzles cleanly."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    _place(state, "P0", vanilla)
    supporter = _support_unit(state, "P0", vanilla)

    state = _enters_play(state, supporter)
    decline = [a for a in legal_actions(state)
               if isinstance(a, DeclineGrantedAttack)]
    assert decline
    state = apply(state, decline[0])
    assert _granted(state) == []


def test_support_without_the_keyword_pushes_nothing(repo):
    """A plain unit entering play offers no Support attack."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    _place(state, "P0", vanilla)
    plain = _place(state, "P0", vanilla)

    state = _enters_play(state, plain)
    assert _granted(state) == []


# ── "It gains this unit's other abilities for this attack" — keywords ──────────

def test_support_lends_its_keywords_to_the_chosen_attacker(repo):
    """The attacker borrows the Support unit's keywords, numeric values included."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    enemy = _place(state, "P1", vanilla)
    supporter = _support_unit(state, "P0", vanilla)
    _grant_keyword(state, supporter, "Overwhelm")
    _grant_keyword(state, supporter, "Raid", 2)

    assert not has_keyword(state, ally, Keyword.OVERWHELM)
    assert keyword_value(state, ally, Keyword.RAID) == 0

    state = _enters_play(state, supporter)
    attack = next(a for a in _attack_options(state)
                  if a.attacker_id == ally.instance_id
                  and a.defender_id == enemy.instance_id)
    power_before = compute_power(state, ally, is_attacking=True)
    state = apply(state, attack)

    # The attack has settled, but the borrow was live while it resolved: the
    # enemy took the Raid-boosted power.
    assert power_before == 3
    enemy_now = next((u for u in state.player_by_id("P1").ground_arena
                      if u.instance_id == enemy.instance_id), None)
    assert enemy_now is not None
    assert enemy_now.damage == 5          # 3 printed + Raid 2, not 3


def test_support_borrowed_keywords_are_live_during_the_attack(repo):
    """Read the borrow directly off the modifier, before the attack resolves."""
    from swu.engine.state import borrowed_ability_sources
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    supporter = _support_unit(state, "P0", vanilla)
    _grant_keyword(state, supporter, "Overwhelm")

    state = _enters_play(state, supporter)
    # Mark the borrow the way AttackWithUnit does, then read it back.
    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=supporter.instance_id,
        target_instance_id=ally.instance_id,
        kind="borrowed_abilities",
        value={"lender_id": supporter.instance_id},
        duration="this_attack",
    ))
    assert [c.instance_id for c in borrowed_ability_sources(state, ally)] == [
        supporter.instance_id]
    assert has_keyword(state, ally, Keyword.OVERWHELM)


def test_support_does_not_lend_support_itself(repo):
    """"…this unit's OTHER abilities" — Support is never borrowed, so a borrowed
    attack can't chain into another Support prompt."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    supporter = _support_unit(state, "P0", vanilla)

    from swu.engine.state import Modifier
    state.modifiers.append(Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=supporter.instance_id,
        target_instance_id=ally.instance_id,
        kind="borrowed_abilities",
        value={"lender_id": supporter.instance_id},
        duration="this_attack",
    ))
    assert has_keyword(state, supporter, Keyword.SUPPORT)
    assert not has_keyword(state, ally, Keyword.SUPPORT)


def test_support_borrow_lapses_once_the_attack_ends(repo):
    """The borrow is a this_attack modifier — it is swept with the rest."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    _place(state, "P1", vanilla)
    supporter = _support_unit(state, "P0", vanilla)
    _grant_keyword(state, supporter, "Overwhelm")

    state = _enters_play(state, supporter)
    attack = next(a for a in _attack_options(state)
                  if a.attacker_id == ally.instance_id)
    state = apply(state, attack)

    assert not any(m.kind == "borrowed_abilities" for m in state.modifiers)
    ally_now = next(u for u in state.player_by_id("P0").ground_arena
                    if u.instance_id == ally.instance_id)
    assert not has_keyword(state, ally_now, Keyword.OVERWHELM)


# ── "…other abilities" — triggered abilities ──────────────────────────────────

def test_support_lends_a_triggered_ability_to_the_attacker(repo):
    """Swoop Bike Marauder LAW_107 ("On Attack: Draw a card") lends its trigger:
    the CHOSEN attacker draws, resolving the ability from itself."""
    vanilla = _get_card(repo, *VANILLA)
    marauder = _get_card(repo, *ON_ATTACK_DRAW)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    _place(state, "P1", vanilla)
    supporter = _place(state, "P0", marauder)
    _grant_keyword(state, supporter, "Support")
    _push_deck_top(state, "P0", vanilla)
    hand_before = len(state.player_by_id("P0").hand)

    state = _enters_play(state, supporter)
    attack = next(a for a in _attack_options(state)
                  if a.attacker_id == ally.instance_id)
    state = apply(state, attack)
    assert len(state.player_by_id("P0").hand) == hand_before + 1


def test_support_lender_keeps_its_own_trigger_for_its_own_attacks(repo):
    """Lending is additive: the borrower fires the trigger, the lender is not
    stripped of it (nor does it fire twice for one attack)."""
    vanilla = _get_card(repo, *VANILLA)
    marauder = _get_card(repo, *ON_ATTACK_DRAW)
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    _place(state, "P1", vanilla)
    supporter = _place(state, "P0", marauder)
    _grant_keyword(state, supporter, "Support")
    for _ in range(4):
        _push_deck_top(state, "P0", vanilla)
    hand_before = len(state.player_by_id("P0").hand)

    state = _enters_play(state, supporter)
    attack = next(a for a in _attack_options(state)
                  if a.attacker_id == ally.instance_id)
    state = apply(state, attack)
    assert len(state.player_by_id("P0").hand) == hand_before + 1  # exactly one draw


# ── The leader half, and the real ASH cards ───────────────────────────────────

def test_support_fires_when_a_leader_is_deployed(repo):
    """"When you deploy this leader, you may attack with another unit."""
    vanilla = _get_card(repo, *VANILLA)
    state = _make_state()
    _place(state, "P0", vanilla)
    leader = _place(state, "P0", vanilla)   # stand-in permanent for the deploy event
    _grant_keyword(state, leader, "Support")

    state = _deploys(state, leader)
    assert len(_granted(state)) == 1
    assert leader.instance_id not in {a.attacker_id for a in _attack_options(state)}


def test_ASH_130_fang_fighter_squadron_supports_on_entry(repo):
    """A real Support-only card: Fang Fighter Squadron ASH_130 offers the attack
    with no ability registration of its own."""
    fang = _get_card(repo, "ASH", "130")
    vanilla = _get_card(repo, *VANILLA)
    assert "Support" in fang.keywords
    state = _make_state()
    ally = _place(state, "P0", vanilla)
    supporter = _place(state, "P0", fang, "space")
    assert has_keyword(state, supporter, Keyword.SUPPORT)

    state = _enters_play(state, supporter)
    assert len(_granted(state)) == 1
    assert ally.instance_id in {a.attacker_id for a in _attack_options(state)}


def test_ASH_9_ahsoka_tano_leader_has_support(repo):
    """The leader side carries the keyword too (Ahsoka Tano ASH_9)."""
    ahsoka = _get_leader(repo, "ASH", "9")
    assert "Support" in ahsoka.keywords
