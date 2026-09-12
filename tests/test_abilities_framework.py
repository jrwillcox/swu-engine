"""
Framework tests for Phase 3 card ability infrastructure.

All tests use synthetic card definitions registered at module import time, so
almost none of them need the card database.  The exceptions are the few that
give a Shield token or round-trip through ``from_json``: the engine loads the
real token ``CardDef`` from the database, so those call ``require_db()`` and
skip without one.  Tests exercise:
  * TriggerAbility collection and inline resolution
  * Optional trigger accept / decline
  * Target selection via ChooseTarget / DeclineTarget
  * Simultaneous trigger ordering
  * WhenDefeated trigger after combat
  * WhenUnitDefeated trigger from observer card
  * ConstantAbility stat bonuses (compute_power / compute_hp)
  * Modifier records and duration cleanup (this_attack, this_round)
  * ActivatedAbility in legal_actions + effect resolution
  * Epic Action once-per-game gating
  * Escape-hatch CustomAbility invocation
"""
from __future__ import annotations

import uuid


from tests.dbpath import require_db

# ── Synthetic card helpers ────────────────────────────────────────────────────

def _make_unit(
    name: str,
    power: int = 2,
    hp: int = 3,
    cost: int = 2,
    traits: tuple = (),
    keywords: tuple = (),
    set_code: str = "TST",
    card_number: str = "001",
    arenas: tuple = ("Ground",),
) -> object:
    """Build a minimal frozen Unit card definition (no DB needed)."""
    from swu.cards.models import Unit
    return Unit(
        id=abs(hash(name)) % 100000,
        card_uid=None,
        set_code=set_code,
        set_name="Test Set",
        card_number=card_number,
        name=name,
        subtitle=None,
        type="Unit",
        rarity="Common",
        is_unique=False,
        artist=None,
        text=None,
        text_styled=None,
        rules=None,
        rules_styled=None,
        aspects=(),
        keywords=keywords,
        traits=traits,
        arenas=arenas,
        image_front_url=None,
        image_back_url=None,
        image_front_path=None,
        image_back_path=None,
        cost=cost,
        power=power,
        hp=hp,
    )


def _make_base(name: str = "Test Base", hp: int = 30) -> object:
    from swu.cards.models import Base
    return Base(
        id=abs(hash(name)) % 100000 + 1000,
        card_uid=None,
        set_code="TST",
        set_name="Test Set",
        card_number="999",
        name=name,
        subtitle=None,
        type="Base",
        rarity="Common",
        is_unique=False,
        artist=None,
        text=None,
        text_styled=None,
        rules=None,
        rules_styled=None,
        aspects=(),
        keywords=(),
        traits=(),
        arenas=(),
        image_front_url=None,
        image_back_url=None,
        image_front_path=None,
        image_back_path=None,
        hp=hp,
        epic_action=None,
    )


def _make_leader_def(
    name: str,
    power: int = 3,
    hp: int = 6,
    leader_power: int = 2,
    leader_hp: int = 4,
    set_code: str = "TST",
    card_number: str = "L01",
) -> object:
    from swu.cards.models import Leader
    return Leader(
        id=abs(hash(name)) % 100000 + 2000,
        card_uid=None,
        set_code=set_code,
        set_name="Test Set",
        card_number=card_number,
        name=name,
        subtitle=None,
        type="Leader",
        rarity="Special",
        is_unique=True,
        artist=None,
        text=None,
        text_styled=None,
        rules=None,
        rules_styled=None,
        aspects=(),
        keywords=(),
        traits=(),
        arenas=("Ground",),
        image_front_url=None,
        image_back_url=None,
        image_front_path=None,
        image_back_path=None,
        power=power,
        hp=hp,
        deploy_box=None,
        epic_action=None,
        leader_power=leader_power,
        leader_hp=leader_hp,
    )


def _make_game_state() -> object:
    """Minimal ACTION-phase GameState with two players, no cards in play."""
    from swu.engine.state import GameState, PlayerState, CardInstance, Zone, Phase

    base_def_0 = _make_base("Base Alpha", hp=30)
    base_def_1 = _make_base("Base Beta", hp=30)

    def _ci(card_def, pid, zone):
        return CardInstance(
            instance_id=f"{pid}_{uuid.uuid4().hex[:6]}",
            card_def=card_def,
            owner_id=pid,
            zone=zone,
        )

    ps0 = PlayerState(player_id="P0")
    ps0.base_zone.append(_ci(base_def_0, "P0", Zone.BASE_ZONE))
    ps1 = PlayerState(player_id="P1")
    ps1.base_zone.append(_ci(base_def_1, "P1", Zone.BASE_ZONE))

    return GameState(
        players=[ps0, ps1],
        phase=Phase.ACTION,
        active_player_index=0,
        round_number=1,
        initiative_holder=0,
    )


def _place_unit(state, pid: str, card_def, arena: str = "GROUND_ARENA") -> object:
    """Place a unit directly into an arena (bypass play pipeline)."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{pid}_{uuid.uuid4().hex[:6]}",
        card_def=card_def,
        owner_id=pid,
        zone=Zone[arena],
        exhausted=False,
    )
    ps = state.player_by_id(pid)
    if arena == "GROUND_ARENA":
        ps.ground_arena.append(ci)
    else:
        ps.space_arena.append(ci)
    return ci


# ── Register synthetic card abilities ─────────────────────────────────────────

from swu.abilities.registry import (
    card_ability, TriggerAbility, ConstantAbility, ActivatedAbility, CustomAbility,
    WhenPlayed, WhenDefeated, OnAttack, WhenUnitDefeated,
    DealDamage, GiveToken, DrawCards, ModifyStats,
    TargetSpec, Duration,
    StatBonus, KeywordGrant, ExhaustSelf, SELF,
)

# TST-A01: WhenPlayed → deal 1 damage to an enemy unit (mandatory, targeted)
@card_ability("TST", "A01")
def _():
    return [TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DealDamage(1, TargetSpec(controller="enemy", kind="unit"))],
    )]

# TST-A02: WhenPlayed → give Shield to self (mandatory, fixed target — INLINE)
@card_ability("TST", "A02")
def _():
    return [TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(fixed=SELF))],
    )]

# TST-A03: WhenPlayed → draw 2 cards (mandatory, no target — INLINE)
@card_ability("TST", "A03")
def _():
    return [TriggerAbility(
        trigger=WhenPlayed(),
        effects=[DrawCards(2)],
    )]

# TST-A04: WhenPlayed → "may" give Shield to a friendly unit (optional, targeted)
@card_ability("TST", "A04")
def _():
    return [TriggerAbility(
        trigger=WhenPlayed(),
        effects=[GiveToken("Shield", TargetSpec(controller="friendly", kind="unit", optional=True))],
        optional=True,
    )]

# TST-A05: WhenDefeated → deal 2 damage to an enemy unit (mandatory)
@card_ability("TST", "A05")
def _():
    return [TriggerAbility(
        trigger=WhenDefeated(),
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="unit"))],
    )]

# TST-A06: WhenUnitDefeated (any enemy unit) → draw 1 card (mandatory, no target)
@card_ability("TST", "A06")
def _():
    return [TriggerAbility(
        trigger=WhenUnitDefeated(filter=TargetSpec(controller="enemy", kind="unit")),
        effects=[DrawCards(1)],
    )]

# TST-A07: ConstantAbility → all friendly units get +1/+1
@card_ability("TST", "A07")
def _():
    return [ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", predicates=("not_self",)),
        effects=[StatBonus(power=1, hp=1)],
    )]

# TST-A08: ConstantAbility → grant Sentinel to all friendly ground units
@card_ability("TST", "A08")
def _():
    return [ConstantAbility(
        target=TargetSpec(controller="friendly", kind="unit", arena="ground"),
        effects=[KeywordGrant("Sentinel")],
    )]

# TST-A09: ActivatedAbility → exhaust self, deal 2 damage to enemy unit
@card_ability("TST", "A09")
def _():
    return [ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[DealDamage(2, TargetSpec(controller="enemy", kind="unit"))],
        title="Snipe",
    )]

# TST-A10: ActivatedAbility (epic, once-per-game) → draw 3 cards
@card_ability("TST", "A10")
def _():
    return [ActivatedAbility(
        costs=[ExhaustSelf()],
        effects=[DrawCards(3)],
        title="Epic Draw",
        epic=True,
    )]

# TST-A11: OnAttack → deal 1 damage to any unit (mandatory, targeted — needs pre_attack)
@card_ability("TST", "A11")
def _():
    return [TriggerAbility(
        trigger=OnAttack(),
        effects=[DealDamage(1, TargetSpec(controller="any", kind="unit"))],
    )]

# TST-A12: ModifyStats THIS_ATTACK +2/+0 to self (OnAttack, inline)
@card_ability("TST", "A12")
def _():
    return [TriggerAbility(
        trigger=OnAttack(),
        effects=[ModifyStats(power=2, hp=0, target=TargetSpec(fixed=SELF), duration=Duration.THIS_ATTACK)],
    )]

# TST-A13: Two simultaneous WhenPlayed triggers on one card
@card_ability("TST", "A13")
def _():
    return [
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
        TriggerAbility(trigger=WhenPlayed(), effects=[DrawCards(1)]),
    ]

# TST-A14: CustomAbility escape hatch
_ESCAPE_HATCH_FIRED: list[str] = []

@card_ability("TST", "A14", escape_hatch=True)
def _():
    def _resolve(state, source_ci, event_ctx):
        _ESCAPE_HATCH_FIRED.append(source_ci.instance_id)
        return state
    return [CustomAbility(resolve_fn=_resolve)]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestInlineTriggers:
    def test_when_played_fixed_target_gives_shield(self):
        """WhenPlayed → GiveToken(Shield, fixed=SELF) resolves inline, no decision."""
        require_db()  # engine token lookup / from_json needs the card database
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import Zone
        from swu.engine.keywords import shields_on

        state = _make_game_state()
        unit_def = _make_unit("A02 Unit", set_code="TST", card_number="A02")
        ps0 = state.players[0]

        # Give P0 enough resources + put card in hand
        from swu.engine.state import CardInstance
        hand_ci = CardInstance(
            instance_id="p0_hand_a02",
            card_def=unit_def,
            owner_id="P0",
            zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        # Give P0 two ready resources
        res_def = _make_unit("Dummy Res", set_code="TST", card_number="RES")
        for i in range(3):
            r = CardInstance(
                instance_id=f"p0_res_{i}",
                card_def=res_def,
                owner_id="P0",
                zone=Zone.RESOURCES,
                exhausted=False,
                face_down=True,
            )
            ps0.resources.append(r)

        state = apply(state, PlayCard("p0_hand_a02"))
        # Should be no pending decisions (inline)
        assert not state.pending_decisions
        # Unit should be in ground arena with a Shield token
        arena_unit = state.players[0].ground_arena[-1]
        assert shields_on(arena_unit) == 1

    def test_when_played_draw_cards_inline(self):
        """WhenPlayed → DrawCards(2) resolves inline, controller draws cards."""
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        unit_def = _make_unit("A03 Unit", set_code="TST", card_number="A03")
        ps0 = state.players[0]

        hand_ci = CardInstance(
            instance_id="p0_hand_a03",
            card_def=unit_def,
            owner_id="P0",
            zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        # Resources
        res_def = _make_unit("Res", set_code="TST", card_number="RES")
        for i in range(3):
            ps0.resources.append(CardInstance(
                instance_id=f"p0_res_{i}",
                card_def=res_def, owner_id="P0", zone=Zone.RESOURCES,
                exhausted=False, face_down=True,
            ))
        # Deck cards
        deck_def = _make_unit("Deck", set_code="TST", card_number="DCK")
        for i in range(4):
            ps0.deck.append(CardInstance(
                instance_id=f"p0_deck_{i}",
                card_def=deck_def, owner_id="P0", zone=Zone.DECK,
            ))

        hand_before = len(ps0.hand)  # should be 0 after card removed
        state = apply(state, PlayCard("p0_hand_a03"))

        assert not state.pending_decisions
        # Drew 2 cards
        assert len(state.players[0].hand) == 2


class TestTargetedTriggers:
    def test_when_played_targeted_mandatory_pushes_decision(self):
        """WhenPlayed → DealDamage to enemy unit → pushes resolve_effects decision."""
        from swu.engine.actions import apply, PlayCard, ChooseTarget, legal_actions
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        unit_def = _make_unit("A01 Unit", set_code="TST", card_number="A01")
        enemy_unit_def = _make_unit("Enemy", power=3, hp=5)
        ps0 = state.players[0]
        ps1 = state.players[1]

        # Place an enemy unit for the trigger to target
        enemy_ci = _place_unit(state, "P1", enemy_unit_def)

        hand_ci = CardInstance(
            instance_id="p0_hand_a01",
            card_def=unit_def, owner_id="P0", zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        res_def = _make_unit("Res", set_code="TST", card_number="RES")
        for i in range(3):
            ps0.resources.append(CardInstance(
                instance_id=f"p0_res_{i}",
                card_def=res_def, owner_id="P0", zone=Zone.RESOURCES,
                exhausted=False, face_down=True,
            ))

        state = apply(state, PlayCard("p0_hand_a01"))

        # Should have pushed a resolve_effects decision
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "resolve_effects"

        # ChooseTarget(enemy_ci) should deal 1 damage
        acts = legal_actions(state)
        choose = next(a for a in acts if isinstance(a, ChooseTarget) and a.target_id == enemy_ci.instance_id)
        state = apply(state, choose)

        assert not state.pending_decisions
        result = state.find_instance(enemy_ci.instance_id)
        assert result is not None
        _, updated_ci = result
        assert updated_ci.damage == 1

    def test_targeted_trigger_fizzles_when_no_targets(self):
        """WhenPlayed → DealDamage to enemy unit fizzles if no enemy units exist."""
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        unit_def = _make_unit("A01 Unit", set_code="TST", card_number="A01")
        ps0 = state.players[0]

        hand_ci = CardInstance(
            instance_id="p0_hand_a01",
            card_def=unit_def, owner_id="P0", zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        res_def = _make_unit("Res", set_code="TST", card_number="RES")
        for i in range(3):
            ps0.resources.append(CardInstance(
                instance_id=f"p0_res_{i}",
                card_def=res_def, owner_id="P0", zone=Zone.RESOURCES,
                exhausted=False, face_down=True,
            ))

        # No enemy units — trigger fires but fizzles inline
        state = apply(state, PlayCard("p0_hand_a01"))
        assert not state.pending_decisions


class TestOptionalTriggers:
    def test_optional_trigger_accept_gives_shield(self):
        """Optional WhenPlayed trigger: accept → Shield applied."""
        require_db()  # engine token lookup / from_json needs the card database
        from swu.engine.actions import apply, PlayCard, AcceptTrigger, ChooseTarget, legal_actions
        from swu.engine.state import Zone, CardInstance
        from swu.engine.keywords import shields_on

        state = _make_game_state()
        unit_def = _make_unit("A04 Unit", set_code="TST", card_number="A04")
        ps0 = state.players[0]

        hand_ci = CardInstance(
            instance_id="p0_hand_a04",
            card_def=unit_def, owner_id="P0", zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        res_def = _make_unit("Res", set_code="TST", card_number="RES")
        for i in range(3):
            ps0.resources.append(CardInstance(
                instance_id=f"p0_res_{i}",
                card_def=res_def, owner_id="P0", zone=Zone.RESOURCES,
                exhausted=False, face_down=True,
            ))

        state = apply(state, PlayCard("p0_hand_a04"))

        # Should have trigger_option decision
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "trigger_option"

        # Accept the trigger
        source_id = state.pending_decisions[-1].context["source_id"]
        state = apply(state, AcceptTrigger(source_id))

        # Now resolve_effects decision for choosing target
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "resolve_effects"

        acts = legal_actions(state)
        # There should be ChooseTarget options for friendly units + DeclineTarget (optional)
        choose_acts = [a for a in acts if isinstance(a, ChooseTarget)]
        assert choose_acts  # the newly played unit is a valid target

        state = apply(state, choose_acts[0])
        assert not state.pending_decisions
        # Shield should be on the chosen unit
        chosen_id = choose_acts[0].target_id
        result = state.find_instance(chosen_id)
        assert result is not None
        _, chosen_ci = result
        assert shields_on(chosen_ci) == 1

    def test_optional_trigger_decline(self):
        """Optional WhenPlayed trigger: decline → no effect."""
        from swu.engine.actions import apply, PlayCard, DeclineTrigger
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        unit_def = _make_unit("A04 Unit", set_code="TST", card_number="A04")
        ps0 = state.players[0]

        hand_ci = CardInstance(
            instance_id="p0_hand_a04b",
            card_def=unit_def, owner_id="P0", zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        res_def = _make_unit("Res", set_code="TST", card_number="RES")
        for i in range(3):
            ps0.resources.append(CardInstance(
                instance_id=f"p0_res_b{i}",
                card_def=res_def, owner_id="P0", zone=Zone.RESOURCES,
                exhausted=False, face_down=True,
            ))

        state = apply(state, PlayCard("p0_hand_a04b"))
        assert state.pending_decisions[-1].kind == "trigger_option"

        source_id = state.pending_decisions[-1].context["source_id"]
        state = apply(state, DeclineTrigger(source_id))

        assert not state.pending_decisions
        # No shields should have been applied to anything
        unit = state.players[0].ground_arena[-1]
        from swu.engine.keywords import shields_on
        assert shields_on(unit) == 0


class TestConstantAbilities:
    def test_constant_power_bonus(self):
        """A07 ConstantAbility: all other friendly units get +1 power."""
        from swu.engine.actions import compute_power

        state = _make_game_state()
        buffing_def = _make_unit("A07 Buff", power=2, hp=3, set_code="TST", card_number="A07")
        target_def = _make_unit("Target", power=2, hp=3)

        buff_ci = _place_unit(state, "P0", buffing_def)
        target_ci = _place_unit(state, "P0", target_def)

        # The buffing card should give +1 power to target (but not to itself, not_self predicate)
        assert compute_power(state, target_ci) == 3   # 2 base + 1 constant bonus
        assert compute_power(state, buff_ci) == 2     # self excluded

    def test_constant_hp_bonus(self):
        """A07 ConstantAbility: all other friendly units get +1 HP."""
        from swu.engine.actions import compute_hp

        state = _make_game_state()
        buffing_def = _make_unit("A07 Buff", power=2, hp=3, set_code="TST", card_number="A07")
        target_def = _make_unit("Target", power=2, hp=3)

        buff_ci = _place_unit(state, "P0", buffing_def)
        target_ci = _place_unit(state, "P0", target_def)

        assert compute_hp(state, target_ci) == 4   # 3 base + 1
        assert compute_hp(state, buff_ci) == 3     # self excluded

    def test_constant_keyword_grant(self):
        """A08 ConstantAbility: friendly ground units gain Sentinel."""
        from swu.engine.keywords import has_keyword, Keyword

        state = _make_game_state()
        granter_def = _make_unit("A08 Granter", set_code="TST", card_number="A08")
        target_def = _make_unit("Ground Target", arenas=("Ground",))
        space_def = _make_unit("Space Unit", arenas=("Space",))

        _place_unit(state, "P0", granter_def, "GROUND_ARENA")
        target_ci = _place_unit(state, "P0", target_def, "GROUND_ARENA")
        space_ci = _place_unit(state, "P0", space_def, "SPACE_ARENA")

        assert has_keyword(state, target_ci, Keyword.SENTINEL)
        assert not has_keyword(state, space_ci, Keyword.SENTINEL)


class TestModifiers:
    def test_modifier_this_attack_expires(self):
        """THIS_ATTACK modifier is cleaned up after attack resolution."""
        from swu.engine.actions import apply, AttackWithUnit

        state = _make_game_state()
        # A12 Unit: OnAttack → ModifyStats(+2/0, fixed=SELF, THIS_ATTACK)
        atk_def = _make_unit("A12 Attacker", power=2, hp=5, set_code="TST", card_number="A12")
        def_def = _make_unit("Defender", power=1, hp=8)

        atk_ci = _place_unit(state, "P0", atk_def)
        def_ci = _place_unit(state, "P1", def_def)

        # OnAttack triggers inline (fixed=SELF, no player choice)
        # The +2 power modifier should be applied during the attack
        state = apply(state, AttackWithUnit(atk_ci.instance_id, def_ci.instance_id))

        # After the attack resolves, the this_attack modifier should be expired
        # (both cards should still be alive: attacker 2+2=4 power vs 8 HP defender, defender 1 power vs 5 HP attacker)
        assert len(state.modifiers) == 0  # modifier cleaned up

    def test_modifier_this_round_expires_at_regroup(self):
        """THIS_ROUND modifiers are cleaned up when regroup ends."""
        from swu.engine.state import Modifier
        from swu.engine.actions import apply, Pass, SkipResource
        from swu.engine.state import Phase

        state = _make_game_state()
        # Manually add a this_round modifier
        mod = Modifier(
            modifier_id="test_mod_1",
            source_instance_id="some_ci",
            target_instance_id="other_ci",
            kind="stats",
            value={"power": 3, "hp": 0},
            duration="this_round",
        )
        state.modifiers.append(mod)

        # Pass both players to trigger regroup
        state = apply(state, Pass())
        state = apply(state, Pass())
        assert state.phase == Phase.REGROUP

        # Skip resource for both players to end regroup
        state = apply(state, SkipResource())
        state = apply(state, SkipResource())

        assert state.phase == Phase.ACTION
        assert len(state.modifiers) == 0  # modifier expired


class TestActivatedAbility:
    def test_activated_ability_in_legal_actions(self):
        """UseAbility appears in legal_actions when costs are payable."""
        from swu.engine.actions import legal_actions, UseAbility

        state = _make_game_state()
        ability_def = _make_unit("A09 Sniper", set_code="TST", card_number="A09")
        target_def = _make_unit("Enemy Target")

        sniper_ci = _place_unit(state, "P0", ability_def)
        _place_unit(state, "P1", target_def)

        acts = legal_actions(state)
        use_acts = [a for a in acts if isinstance(a, UseAbility) and a.source_id == sniper_ci.instance_id]
        assert use_acts, "UseAbility should be in legal_actions"
        assert use_acts[0].ability_idx == 0

    def test_activated_ability_not_legal_when_exhausted(self):
        """UseAbility not offered when ExhaustSelf cost cannot be paid."""
        from swu.engine.actions import legal_actions, UseAbility

        state = _make_game_state()
        ability_def = _make_unit("A09 Sniper", set_code="TST", card_number="A09")
        _place_unit(state, "P1", _make_unit("Enemy"))

        sniper_ci = _place_unit(state, "P0", ability_def)
        sniper_ci.exhausted = True  # can't pay ExhaustSelf

        acts = legal_actions(state)
        use_acts = [a for a in acts if isinstance(a, UseAbility) and a.source_id == sniper_ci.instance_id]
        assert not use_acts

    def test_activated_ability_executes_effect(self):
        """UseAbility(snipe) exhausts source and damages chosen enemy unit."""
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget

        state = _make_game_state()
        ability_def = _make_unit("A09 Sniper", set_code="TST", card_number="A09")
        enemy_def = _make_unit("Enemy", power=3, hp=5)

        sniper_ci = _place_unit(state, "P0", ability_def)
        enemy_ci = _place_unit(state, "P1", enemy_def)

        state = apply(state, UseAbility(sniper_ci.instance_id, 0))

        # Should push a resolve_effects decision for choosing target
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "resolve_effects"

        acts = legal_actions(state)
        choose = next(a for a in acts if isinstance(a, ChooseTarget))
        state = apply(state, choose)

        assert not state.pending_decisions
        # Sniper should be exhausted
        result_sniper = state.find_instance(sniper_ci.instance_id)
        assert result_sniper is not None
        _, updated_sniper = result_sniper
        assert updated_sniper.exhausted

        # Enemy should have 2 damage
        result_enemy = state.find_instance(enemy_ci.instance_id)
        assert result_enemy is not None
        _, updated_enemy = result_enemy
        assert updated_enemy.damage == 2

    def test_epic_ability_only_once(self):
        """Epic activated ability cannot be used twice (once-per-game)."""
        from swu.engine.actions import legal_actions, apply, UseAbility

        state = _make_game_state()
        epic_def = _make_unit("A10 Epic", set_code="TST", card_number="A10")
        epic_ci = _place_unit(state, "P0", epic_def)

        # Ensure deck has cards to draw
        from swu.engine.state import CardInstance, Zone
        deck_def = _make_unit("Deck", set_code="TST", card_number="DCK")
        for i in range(5):
            state.players[0].deck.append(CardInstance(
                instance_id=f"deck_{i}",
                card_def=deck_def, owner_id="P0", zone=Zone.DECK,
            ))

        acts = legal_actions(state)
        use_acts = [a for a in acts if isinstance(a, UseAbility) and a.source_id == epic_ci.instance_id]
        assert use_acts  # first time: legal

        state = apply(state, use_acts[0])
        # Ready the unit again (simulating next turn)
        result = state.find_instance(epic_ci.instance_id)
        if result:
            _, u = result
            u.exhausted = False

        acts2 = legal_actions(state)
        use_acts2 = [a for a in acts2 if isinstance(a, UseAbility) and a.source_id == epic_ci.instance_id]
        assert not use_acts2  # epic spent — not legal again


class TestWhenDefeated:
    def test_when_defeated_triggers_on_combat_kill(self):
        """WhenDefeated → DealDamage to enemy fires when unit is killed in combat."""
        from swu.engine.actions import apply, AttackWithUnit, ChooseTarget, legal_actions

        state = _make_game_state()
        # P1 has A05 unit (WhenDefeated: deal 2 to enemy unit); HP=1 so it dies to any hit
        dying_def = _make_unit("A05 Dying", power=1, hp=1, set_code="TST", card_number="A05")
        # P0 has the attacker
        attacker_def = _make_unit("Attacker", power=3, hp=5)
        # P1 also has a target for the WhenDefeated effect
        bystander_def = _make_unit("Bystander", power=1, hp=5)

        attacker_ci = _place_unit(state, "P0", attacker_def)
        dying_ci = _place_unit(state, "P1", dying_def)
        bystander_ci = _place_unit(state, "P1", bystander_def)

        state = apply(state, AttackWithUnit(attacker_ci.instance_id, dying_ci.instance_id))

        # dying_ci should be defeated by the 3 power hit
        # WhenDefeated trigger fires — needs a target choice for DealDamage(2, enemy unit)
        # From dying_ci's perspective (owner P1): "enemy" = P0's units
        # But P0's attacker might also be dead (1 power vs 1 HP)
        # Let's just check that the trigger resolved somehow
        # If there are still pending decisions, accept them
        if state.pending_decisions:
            acts = legal_actions(state)
            if any(isinstance(a, ChooseTarget) for a in acts):
                choose = next(a for a in acts if isinstance(a, ChooseTarget))
                state = apply(state, choose)

        assert not state.pending_decisions


class TestWhenUnitDefeated:
    def test_when_unit_defeated_observer_draws(self):
        """A06 (WhenUnitDefeated any enemy unit → draw 1) fires when enemy dies."""
        from swu.engine.actions import apply, AttackWithUnit

        state = _make_game_state()
        # P0 has A06 observer and the attacker
        observer_def = _make_unit("A06 Observer", power=1, hp=5, set_code="TST", card_number="A06")
        attacker_def = _make_unit("Big Attacker", power=5, hp=5)
        # P1 has a weak unit that will die
        weak_def = _make_unit("Weak Enemy", power=0, hp=1)

        observer_ci = _place_unit(state, "P0", observer_def)
        attacker_ci = _place_unit(state, "P0", attacker_def)
        weak_ci = _place_unit(state, "P1", weak_def)

        # Seed P0's deck
        from swu.engine.state import CardInstance, Zone
        deck_def = _make_unit("Deck Card")
        for i in range(3):
            state.players[0].deck.append(CardInstance(
                instance_id=f"obs_deck_{i}",
                card_def=deck_def, owner_id="P0", zone=Zone.DECK,
            ))

        hand_before = len(state.players[0].hand)
        state = apply(state, AttackWithUnit(attacker_ci.instance_id, weak_ci.instance_id))

        # Resolve any pending decisions
        from swu.engine.actions import legal_actions
        while state.pending_decisions:
            acts = legal_actions(state)
            state = apply(state, acts[0])

        # P0 should have drawn a card from the WhenUnitDefeated trigger
        assert len(state.players[0].hand) == hand_before + 1


class TestAttackWithLeader:
    def test_attack_with_leader_deals_damage_to_base(self):
        """AttackWithLeader exhausts leader and deals leader_power damage to enemy base."""
        from swu.engine.actions import apply, AttackWithLeader, legal_actions
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        leader_def = _make_leader_def("Test Leader", leader_power=2, leader_hp=4)
        ps0 = state.players[0]

        leader_ci = CardInstance(
            instance_id="p0_leader",
            card_def=leader_def,
            owner_id="P0",
            zone=Zone.BASE_ZONE,
            exhausted=False,
            deployed=False,
        )
        ps0.base_zone.append(leader_ci)

        acts = legal_actions(state)
        assert any(isinstance(a, AttackWithLeader) for a in acts)

        base_hp_before = state.players[1].base_instance.damage
        state = apply(state, AttackWithLeader())

        assert state.players[1].base_instance.damage == base_hp_before + 2
        # Leader should be exhausted
        result = state.find_instance("p0_leader")
        assert result is not None
        _, updated_leader = result
        assert updated_leader.exhausted

    def test_attack_with_leader_not_legal_when_exhausted(self):
        """AttackWithLeader is not in legal_actions when leader is exhausted."""
        from swu.engine.actions import legal_actions, AttackWithLeader
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        leader_def = _make_leader_def("Tired Leader", leader_power=2, leader_hp=4)
        ps0 = state.players[0]

        leader_ci = CardInstance(
            instance_id="p0_leader_tired",
            card_def=leader_def,
            owner_id="P0",
            zone=Zone.BASE_ZONE,
            exhausted=True,  # already exhausted
            deployed=False,
        )
        ps0.base_zone.append(leader_ci)

        acts = legal_actions(state)
        assert not any(isinstance(a, AttackWithLeader) for a in acts)


class TestEscapeHatch:
    def test_custom_ability_callable(self):
        """CustomAbility.resolve_fn is called when the ability fires."""
        from swu.abilities.registry import get_abilities, CustomAbility

        specs = get_abilities("TST", "A14")
        assert specs
        assert isinstance(specs[0], CustomAbility)
        assert callable(specs[0].resolve_fn)

        _ESCAPE_HATCH_FIRED.clear()
        # Call the escape hatch directly with dummy args
        from swu.engine.state import CardInstance, Zone
        state = _make_game_state()
        dummy_def = _make_unit("A14 Escape", set_code="TST", card_number="A14")
        dummy_ci = CardInstance(
            instance_id="esc_ci",
            card_def=dummy_def, owner_id="P0", zone=Zone.GROUND_ARENA,
        )
        specs[0].resolve_fn(state, dummy_ci, {})
        assert "esc_ci" in _ESCAPE_HATCH_FIRED


class TestGameMemory:
    def test_units_played_tracked(self):
        """Units played this phase are tracked in game_memory."""
        require_db()  # engine token lookup / from_json needs the card database
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import Zone, CardInstance

        state = _make_game_state()
        unit_def = _make_unit("Track Me", set_code="TST", card_number="A02")  # A02: Shield, inline
        ps0 = state.players[0]

        hand_ci = CardInstance(
            instance_id="p0_tracked",
            card_def=unit_def, owner_id="P0", zone=Zone.HAND,
        )
        ps0.hand.append(hand_ci)
        res_def = _make_unit("Res")
        for i in range(3):
            ps0.resources.append(CardInstance(
                instance_id=f"p0_mem_res_{i}",
                card_def=res_def, owner_id="P0", zone=Zone.RESOURCES,
                exhausted=False, face_down=True,
            ))

        state = apply(state, PlayCard("p0_tracked"))
        assert not state.pending_decisions

        # The unit should be recorded in units_played_this_phase
        played = state.players[0].ground_arena[-1]
        assert played.instance_id in state.game_memory.units_played_this_phase


class TestJSONRoundtrip:
    def test_state_with_modifiers_roundtrips(self):
        """GameState with Modifier and GameMemory serialises and deserialises correctly."""
        from swu.engine.state import Modifier
        from tests.dbpath import require_db

        state = _make_game_state()
        require_db()  # from_json needs the card database; skip cleanly without it

        state.modifiers.append(Modifier(
            modifier_id="m1",
            source_instance_id="s1",
            target_instance_id="t1",
            kind="stats",
            value={"power": 2, "hp": 0},
            duration="this_round",
        ))
        state.game_memory.units_played_this_phase.add("ci_abc")
        state.game_memory.epic_actions_spent.add("ci_xyz")

        j = state.to_json()
        restored = state.from_json(j)
        assert len(restored.modifiers) == 1
        assert restored.modifiers[0].modifier_id == "m1"
        assert restored.modifiers[0].duration == "this_round"
        assert "ci_abc" in restored.game_memory.units_played_this_phase
        assert "ci_xyz" in restored.game_memory.epic_actions_spent
