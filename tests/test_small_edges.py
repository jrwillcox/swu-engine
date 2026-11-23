"""Known-deviation fixes 5 (2026-11-23): the smaller rules edges.

* Exploit applies to a card played by an ability (Admiral Ozzel's play-from-hand,
  Ezra Bridger SOR_192's play-the-top-card), not only to a ``PlayCard``.
* An undeployed leader is a legal "leader or unit" target.
* ``has_any_keyword`` sees aura-granted keywords.
* Granted-attack riders survive a mid-attack decision.
"""
from __future__ import annotations

import dataclasses

from tests.test_sor_cards import repo, _make_state, _place, _give_resources  # noqa: F401
from tests.test_fortify import _unit_def, _to_hand


def _exploiter(cost=5):
    return dataclasses.replace(_unit_def("Exploiter", "73"), cost=cost,
                               text="Exploit 1", keywords=("Exploit",))


# ── Exploit on ability-driven plays ──────────────────────────────────────────

def test_play_from_hand_offers_exploit_and_applies_its_discount(repo):
    from swu.engine.actions import (apply, legal_actions, push_play_from_hand,
                                    PlayFromHand, ExploitSacrifice)
    state = _make_state()
    source = _place(state, "P0", _unit_def("Source", "72"))
    fodder = _place(state, "P0", _unit_def("Fodder", "74"))
    _give_resources(state, "P0", 3)                     # 5 − 2 (Exploit) = 3
    ci = _to_hand(state, "P0", _exploiter(cost=5))
    state.active_player_index = 0
    push_play_from_hand(state, source)
    assert any(isinstance(a, PlayFromHand) and a.instance_id == ci.instance_id
               for a in legal_actions(state)), "affordable only by exploiting"
    state = apply(state, PlayFromHand(ci.instance_id))
    assert state.pending_decisions[-1].kind == "exploit"
    state = apply(state, ExploitSacrifice(fodder.instance_id))   # Exploit 1 → commits
    p0 = state.player_by_id("P0")
    assert ci.instance_id in {u.instance_id for u in p0.ground_arena}
    assert fodder.instance_id not in {u.instance_id for u in p0.ground_arena}
    assert all(r.exhausted for r in p0.resources)       # paid exactly 3
    assert source.instance_id in {u.instance_id for u in p0.ground_arena}


def test_TWI_179_offers_the_undeployed_grievous_leader(repo):
    """Soulless One: "exhaust a friendly Droid unit or General Grievous (leader or
    unit)" — the undeployed leader in the base zone is a legal choice."""
    from swu.abilities.resolver import _gather_legal_targets
    from swu.abilities.registry import get_abilities
    from tests.test_sor_cards import _get_card, _get_leader, _place_leader
    state = _make_state()
    soulless = _place(state, "P0", _get_card(repo, "TWI", "179"), "space")
    grievous = _place_leader(state, "P0", dataclasses.replace(
        _get_leader(repo, "SOR", "5"), name="General Grievous"))
    spec = get_abilities("TWI", "179")[0].effects[0].target
    assert grievous.instance_id in _gather_legal_targets(state, spec, soulless, {})
    grievous.exhausted = True                           # "ready" still applies
    assert grievous.instance_id not in _gather_legal_targets(state, spec, soulless, {})


# ── Aura-granted keywords count as "has a keyword" ───────────────────────────

def test_has_any_keyword_sees_an_aura_only_keyword(repo):
    """First Light SHD_36: "Each other friendly non-leader unit gains Grit" — a
    vanilla unit beside it HAS a keyword (Boba Fett SHD_8, Rex HMW_141)."""
    from swu.engine.keywords import has_any_keyword, distinct_keyword_names
    from tests.test_sor_cards import _get_card
    state = _make_state()
    vanilla = _place(state, "P0", _unit_def("Vanilla", "75"))
    assert not has_any_keyword(state, vanilla)
    _place(state, "P0", _get_card(repo, "SHD", "36"), "space")
    assert has_any_keyword(state, vanilla)
    assert "Grit" in distinct_keyword_names(state, vanilla)


# ── Granted-attack riders survive a paused attack ────────────────────────────

def _drive_to(state, kind, limit=12):
    """Resolve decisions (declining/continuing) until ``kind`` is on top."""
    from swu.engine.actions import apply, legal_actions
    for _ in range(limit):
        if not state.pending_decisions or state.pending_decisions[-1].kind == kind:
            return state
        acts = legal_actions(state)
        pick = next((a for a in acts if type(a).__name__ in (
            "DeclineTrigger", "ContinueAttack")), acts[0])
        state = apply(state, pick)
    return state


def test_repeat_granted_attack_survives_an_on_attack_pause(repo):
    """Mon Mothma SEC_103 "attack with any number of units, one at a time": the
    first attacker's optional On Attack (Furtive Handmaiden SEC_197) pauses the
    attack; the next attack is still offered once it settles."""
    from swu.engine.actions import apply, AttackWithUnit, push_granted_attack
    from tests.test_sor_cards import _get_card
    state = _make_state()
    source = _place(state, "P0", _unit_def("Source", "72"))
    maiden = _place(state, "P0", _get_card(repo, "SEC", "197"))
    other = _place(state, "P0", _unit_def("Other", "76"))
    _to_hand(state, "P0", _unit_def("Card", "77"))      # arms the optional trigger
    for u in (source, maiden, other):
        u.exhausted = False
    state.active_player_index = 0
    push_granted_attack(state, source, repeat=True, optional=True)
    state = apply(state, AttackWithUnit(maiden.instance_id, None))
    assert any(d.kind == "pre_attack" for d in state.pending_decisions), "paused"
    state = _drive_to(state, "granted_attack")
    top = state.pending_decisions[-1]
    assert top.kind == "granted_attack"
    assert maiden.instance_id in top.context.get("already_attacked", [])


def test_then_defeat_attacker_survives_an_on_attack_pause(repo):
    """Heroic Sacrifice SOR_150-style "then defeat it" on an attacker whose On
    Attack paused the attack."""
    from swu.engine.actions import apply, AttackWithUnit, push_granted_attack
    from tests.test_sor_cards import _get_card
    state = _make_state()
    source = _place(state, "P0", _unit_def("Source", "72"))
    maiden = _place(state, "P0", _get_card(repo, "SEC", "197"))
    _to_hand(state, "P0", _unit_def("Card", "77"))
    maiden.exhausted = False
    state.active_player_index = 0
    push_granted_attack(state, source, then_defeat_attacker=True)
    state = apply(state, AttackWithUnit(maiden.instance_id, None))
    state = _drive_to(state, "__none__")
    assert maiden.instance_id not in {
        u.instance_id for u in state.player_by_id("P0").ground_arena}


def test_free_ability_play_skips_exploit(repo):
    from swu.engine.actions import apply, push_play_from_hand, PlayFromHand
    state = _make_state()
    source = _place(state, "P0", _unit_def("Source", "72"))
    _place(state, "P0", _unit_def("Fodder", "74"))
    ci = _to_hand(state, "P0", _exploiter())
    push_play_from_hand(state, source, free=True)
    state = apply(state, PlayFromHand(ci.instance_id))
    assert not any(d.kind == "exploit" for d in state.pending_decisions)
    assert ci.instance_id in {u.instance_id for u in state.player_by_id("P0").ground_arena}
