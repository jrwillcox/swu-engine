"""Tests for the interactive ABILITY-damage prevention primitive — the replacement-
effect framework's DAMAGE half, ability sink (Queen Amidala SEC_101).

Amidala is now FULLY registered: her combat half (B48 — the one-shot
``prevent_next_combat_damage`` flag + the pre-step2 ``_armed_combat_preventions``
checkpoint) plus this batch's ability half (a deferred ``ability_damage_prevention``
decision pushed from the synchronous sink ``resolver._apply_deal_damage``) together
cover her whole "If damage would be dealt to this unit, you may defeat another friendly
unit that shares a trait with this unit.  If you do, prevent that damage."  Indirect
damage needs no coverage — its receiving player assigns the sink and so never lands it
on a unit they would rather protect.

Scenario cards (all real):
  * SEC_101 Queen Amidala — 5/3, traits Naboo/Official (the marked, protected unit).
  * SEC_103 Mon Mothma — 5/4, traits Official/Rebel — shares Official with Amidala, so
    a legal sacrifice; her only ability is a WhenPlayed (never fired by ``_place``, and
    no WhenDefeated), so defeating her as a sacrifice is clean.
  * SOR_46 Consular Security Force — 3/7, Rebel/Trooper (a plain enemy source; its
    traits do NOT overlap Amidala, so it is never a sacrifice candidate).
  * TWI_174 Open Fire — "Deal 4 damage to a unit" (the end-to-end ability source).
"""
from __future__ import annotations


from tests.test_sor_cards import (  # noqa: F401
    repo, _get_card, _make_state, _place, _play_event_from_hand,
)


def _amidala_setup(repo, *, with_sacrifice=True):
    """P1 fields Amidala (SEC_101, marked) + optionally an Official-sharing sacrifice
    (Mon Mothma SEC_103); P0 fields a plain enemy source (SOR_46)."""
    state = _make_state()
    amidala = _place(state, "P1", _get_card(repo, "SEC", "101"), "ground")
    sac = None
    if with_sacrifice:
        sac = _place(state, "P1", _get_card(repo, "SEC", "103"), "ground")
    src = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
    return state, amidala, sac, src


def _deal_ability_damage(state, target_ci, amount, src_ci):
    """Drive the ability-damage sink directly (mutates state in place)."""
    from swu.abilities.resolver import _apply_deal_damage
    return _apply_deal_damage(
        state, target_ci.instance_id, amount,
        source_name=src_ci.card_def.display_name,
        dealer_id=src_ci.owner_id, source_id=src_ci.instance_id)


def _drain(state):
    """Apply any pending AutoResolveEffects to quiescence (resume a buried
    resolve_effects decision once a nested decision has been resolved)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(25):
        if not state.pending_decisions:
            break
        auto = next((a for a in legal_actions(state)
                     if isinstance(a, AutoResolveEffects)), None)
        if auto is None:
            break
        state = apply(state, auto)
    return state


# ── Registration ────────────────────────────────────────────────────────────────

class TestQueenAmidalaRegistration:
    def test_sec_101_registered_with_marker_and_spy_tokens(self, repo):
        from swu.abilities.registry import (
            get_abilities, InteractiveDamagePrevention, TriggerAbility, CreateTokenUnit)
        specs = get_abilities("SEC", "101")
        assert any(isinstance(s, InteractiveDamagePrevention) for s in specs)
        spy = next((s for s in specs if isinstance(s, TriggerAbility)), None)
        assert spy is not None
        assert any(isinstance(e, CreateTokenUnit) and e.token_name == "Spy" and e.count == 2
                   for e in spy.effects)

    def test_sec_101_reprints_alias_to_canonical(self, repo):
        from tests.dbpath import skip_on_fixture
        skip_on_fixture("reprint aliasing needs every printing in the DB")
        from swu.abilities.registry import get_abilities
        assert get_abilities("J25", "16") is get_abilities("SEC", "101")
        assert get_abilities("P25", "27") is get_abilities("SEC", "101")


# ── The deferred ability-damage prevention decision ─────────────────────────────

class TestAbilityDamagePreventionDecision:
    def test_sec_101_ability_damage_deferred_and_offered_to_controller(self, repo):
        from swu.engine.actions import (
            legal_actions, ChoosePreventionSacrifice, DeclineCombatPrevention)
        state, amidala, sac, src = _amidala_setup(repo)
        state = _deal_ability_damage(state, amidala, 2, src)

        top = state.pending_decisions[-1]
        assert top.kind == "ability_damage_prevention"
        assert top.deciding_player_id == "P1"       # the protected unit's controller
        assert amidala.damage == 0                   # deferred, not yet dealt
        acts = legal_actions(state)
        assert any(isinstance(a, ChoosePreventionSacrifice)
                   and a.target_id == sac.instance_id for a in acts)
        assert any(isinstance(a, DeclineCombatPrevention) for a in acts)

    def test_sec_101_accept_defeats_friendly_and_prevents_ability_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, ChoosePreventionSacrifice
        from swu.engine.events import DamagePrevented
        state, amidala, sac, src = _amidala_setup(repo)
        state = _deal_ability_damage(state, amidala, 2, src)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, ChoosePreventionSacrifice)
                   and a.target_id == sac.instance_id)
        state = apply(state, act)

        # The sacrifice was defeated to its owner's discard; Amidala took no damage.
        assert any(c.instance_id == sac.instance_id
                   for c in state.player_by_id("P1").discard)
        _, am = state.find_instance(amidala.instance_id)
        assert am.damage == 0
        assert not state.pending_decisions
        assert any(isinstance(e, DamagePrevented) for e in state.event_log)

    def test_sec_101_decline_lets_ability_damage_land(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineCombatPrevention
        state, amidala, sac, src = _amidala_setup(repo)
        state = _deal_ability_damage(state, amidala, 2, src)

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineCombatPrevention)))
        _, am = state.find_instance(amidala.instance_id)
        assert am.damage == 2                        # full damage landed
        # The sacrifice survives (not defeated).
        assert any(c.instance_id == sac.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        assert not state.pending_decisions

    def test_sec_101_lethal_ability_damage_declined_defeats_amidala(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineCombatPrevention
        state, amidala, sac, src = _amidala_setup(repo)
        state = _deal_ability_damage(state, amidala, 3, src)   # == her 3 hp

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineCombatPrevention)))
        # Amidala is defeated: gone from the arena, in P1's discard.
        assert all(c.instance_id != amidala.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        assert any(c.instance_id == amidala.instance_id
                   for c in state.player_by_id("P1").discard)

    def test_sec_101_not_offered_without_trait_sharing_friendly(self, repo):
        state, amidala, _, src = _amidala_setup(repo, with_sacrifice=False)
        state = _deal_ability_damage(state, amidala, 2, src)
        # No eligible sacrifice → the sink deals the damage straight through.
        assert not any(d.kind == "ability_damage_prevention"
                       for d in state.pending_decisions)
        assert amidala.damage == 2

    def test_sec_101_not_offered_when_shielded(self, repo):
        from swu.engine.tokens import attach_token
        state, amidala, sac, src = _amidala_setup(repo)
        attach_token(state, state.player_by_id("P1"), amidala, "Shield")
        state = _deal_ability_damage(state, amidala, 2, src)
        # A shield would absorb the hit — no prevention decision, sacrifice untouched.
        assert not any(d.kind == "ability_damage_prevention"
                       for d in state.pending_decisions)
        assert any(c.instance_id == sac.instance_id
                   for c in state.player_by_id("P1").ground_arena)

    def test_sec_101_zero_amount_deals_and_offers_nothing(self, repo):
        state, amidala, sac, src = _amidala_setup(repo)
        state = _deal_ability_damage(state, amidala, 0, src)
        assert not state.pending_decisions
        assert amidala.damage == 0


# ── End-to-end through a real ability (Open Fire TWI_174) — nested-decision resume ──

class TestAbilityDamagePreventionEndToEnd:
    def test_sec_101_open_fire_decline_via_apply(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, DeclineCombatPrevention
        state = _make_state()
        amidala = _place(state, "P1", _get_card(repo, "SEC", "101"), "ground")
        _place(state, "P1", _get_card(repo, "SEC", "103"), "ground")   # sacrifice
        # P0 plays Open Fire (deal 4 to a unit) and targets Amidala.
        state, _ = _play_event_from_hand(state, repo, "TWI", "174", owner="P0")
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == amidala.instance_id)
        state = apply(state, tgt)

        top = state.pending_decisions[-1]
        assert top.kind == "ability_damage_prevention"
        assert top.deciding_player_id == "P1"
        # P1 declines → the deferred 4 lands (lethal on a 5/3 → Amidala defeated).
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineCombatPrevention)))
        state = _drain(state)
        assert any(c.instance_id == amidala.instance_id
                   for c in state.player_by_id("P1").discard)
        assert not state.pending_decisions

    def test_sec_101_open_fire_accept_via_apply(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, ChoosePreventionSacrifice
        state = _make_state()
        amidala = _place(state, "P1", _get_card(repo, "SEC", "101"), "ground")
        sac = _place(state, "P1", _get_card(repo, "SEC", "103"), "ground")
        state, _ = _play_event_from_hand(state, repo, "TWI", "174", owner="P0")
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == amidala.instance_id)
        state = apply(state, tgt)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, ChoosePreventionSacrifice)
                   and a.target_id == sac.instance_id)
        state = apply(state, act)
        state = _drain(state)
        # Sacrifice defeated, Amidala survives undamaged, the buried event resolved.
        assert any(c.instance_id == sac.instance_id
                   for c in state.player_by_id("P1").discard)
        _, am = state.find_instance(amidala.instance_id)
        assert am.damage == 0
        assert not state.pending_decisions


# ── Serialisation + invariants ───────────────────────────────────────────────────

class TestAbilityDamagePreventionRobustness:
    def test_sec_101_serialises_across_pending_decision(self, repo):
        from swu.engine.state import GameState
        state, amidala, sac, src = _amidala_setup(repo)
        state = _deal_ability_damage(state, amidala, 2, src)
        assert state.pending_decisions[-1].kind == "ability_damage_prevention"
        restored = GameState.from_json(state.to_json())
        assert restored.pending_decisions[-1].kind == "ability_damage_prevention"
        assert restored.pending_decisions[-1].context["amount"] == 2

    def test_sec_101_invariants_hold_across_prevention(self, repo):
        from swu.engine.actions import legal_actions, apply, ChoosePreventionSacrifice
        from swu.engine.invariants import CheckContext, check
        state, amidala, sac, src = _amidala_setup(repo)
        ctx = CheckContext.from_state(state)
        state = _deal_ability_damage(state, amidala, 2, src)
        check(state, ctx)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChoosePreventionSacrifice)))
        check(state, ctx)
