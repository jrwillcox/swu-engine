"""
Ability resolver — trigger collection and effect execution.

Called from actions.py after every event that may fire triggers.  Keeps
circular-import risk low by using late imports (inside functions) for
anything from actions.py.

Public API
----------
fire_triggered_abilities(state, event, after_all_player_idx) -> GameState
    Collect triggered abilities matching event, resolve inline ones
    immediately, push decisions for optional or choice-requiring ones.

resolve_effects_actions(state, decision) -> list[Action]
    Return the ChooseTarget / DeclineTarget options for the top
    "resolve_effects" pending decision.  Called from
    _decision_legal_actions() in actions.py.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from swu.abilities.registry import (
    get_abilities,
    TriggerAbility, ConstantAbility, GrantedAbility, AuraGrantedAbility, unwrap_granted,
    WhenPlayed, WhenPlayedViaSmuggle, WhenDeployed, WhenYouDeployLeader, WhenDefeated, WhenDefeatedAsUpgrade, OnAttack, WhenAttacked,
    WhenEnemyAttacksYourBase,
    WhenUnitDefeated, WhenUnitEntersPlay, WhenIndirectDamageDealtToUnit, OnAttackDefeatsUnit,
    WhenYouTakeInitiative,
    WhenFriendlyUnitAttacksAndDefeatsUnit,
    RevokeTrait,
    WhenYouPlayCard, WhenOpponentPlaysNthCard, WhenOpponentPlaysCard, WhenUnitAttacks, WhenDealsCombatDamageToBase, WhenDealtCombatDamage,
    WhenDealsCombatDamageToUnit, WhenFriendlyUnitDealtCombatDamage,
    WhenFriendlyUnitDealsCombatDamageToEnemyUnit,
    WhenDealNonCombatDamage, WhenYouDraw, WhenYouUseForce, WhenYouRevealOrDiscard, WhenPlayerDiscardsFromHand, WhenThisIsDiscarded, WhenYouDiscardFromDeck, WhenUnitHealed, WhenUnitReadies, WhenFriendlyUpgradeDefeated, WhenUpgradeAttached, WhenYouWouldCreateTokens, WhenBountyCollected, WhenAttackEnds, WhenFriendlyUnitAttackEnds, WhenYouPlayOrCreateUnit, WhenDamageDealtToYourBase, RoundStartTrigger, PhaseStartTrigger,
    DealDamage, DealDamageEqualTo, Heal, DefeatUnit, DefeatAllUnits, GiveToken,
    CreateCreditToken, CreateForceToken, CreateTokenUnit, NextPlayDiscount,
    DrawCards, DiscardFromHand, ReturnToHand, ExhaustCard, ReadyCard,
    ModifyStats, GrantKeyword, RevokeKeyword, ConditionalEffect, CustomEffect,
    CaptureUnit, Protection,
    TargetSpec, SELF, ATTACKER, DEFENDER, EACH_FRIENDLY, EACH_ENEMY, EACH_IN_PLAY,
    Duration,
)

if TYPE_CHECKING:
    # All imported inside the functions that use them at runtime, to break the
    # state/actions import cycle; declared here so the annotations resolve.
    from swu.engine.state import GameState, CardInstance, PlayerState, Modifier
    from swu.engine.events import GameEvent
    from swu.engine.actions import Action
    from swu.engine.decisions import PendingDecision


# ── Coverage observer (opt-in, for soak instrumentation) ──────────────────────
# Default None → the resolver stays a pure, deterministic function (the observer
# only reads card identity, never touches state).  soak.py installs a callback
# to record which registered abilities actually resolve.  Every non-constant
# ability (TriggerAbility, ActivatedAbility, EventAbility) funnels its effects
# through execute_effect(), so this is the single chokepoint for fire-tracking.
_ability_observer = None  # callable(set_code: str, card_number: str) | None

# Reentrancy guard for the ``most_power_among_friendly`` predicate, which reads
# ``compute_power`` from inside a ConstantAbility aura target — the
# ``registry._POWER_MIN_EVALUATING`` shape.  See the predicate for why re-entry
# reporting False is also the correct answer.
_MOST_POWER_EVALUATING: set = set()


def set_ability_observer(fn) -> None:
    """Install (or clear, with None) the ability-resolution observer."""
    global _ability_observer
    _ability_observer = fn


def _note_ability_resolved(source_ci: "CardInstance") -> None:
    if _ability_observer is None or source_ci is None:
        return
    cd = getattr(source_ci, "card_def", None)
    sc = getattr(cd, "set_code", None)
    cn = getattr(cd, "card_number", None)
    if sc and cn:
        _ability_observer(sc, cn)


# Effect-efficacy observer: distinguishes an ability that *fired* from one that
# actually had something to act on.  soak.py installs a callback to record, per
# ability, the effect kinds it resolved, their nominal magnitude, and how many
# targets were resolved — so an ability that "fires" 900x but always resolves 0
# targets (a wiring/targeting bug) is visible, not hidden behind the fire count.
# Default None → resolver stays pure.
_effect_observer = None  # callable(sc, cn, effect_kind, amount, n_targets) | None


def set_effect_observer(fn) -> None:
    """Install (or clear, with None) the per-effect efficacy observer."""
    global _effect_observer
    _effect_observer = fn


def _note_effect_efficacy(source_ci: "CardInstance", effect: object, n_targets: int) -> None:
    if _effect_observer is None or source_ci is None:
        return
    cd = getattr(source_ci, "card_def", None)
    sc = getattr(cd, "set_code", None)
    cn = getattr(cd, "card_number", None)
    if not (sc and cn):
        return
    # Nominal magnitude: amount for damage/heal/stat effects, count for draw/token.
    amount = getattr(effect, "amount", None)
    if amount is None:
        amount = getattr(effect, "count", 0) or 0
    # Some effects carry a non-numeric magnitude — e.g. DealDamageEqualTo's
    # ``count`` is the *name* of a scaling source ("source_controller_discard_
    # distinct_costs"), not an integer.  The efficacy counter only wants a
    # nominal number, and must never crash the game on instrumentation, so a
    # non-numeric magnitude records as 0 (magnitude unknown).
    try:
        amount_i = int(amount)
    except (TypeError, ValueError):
        amount_i = 0
    _effect_observer(sc, cn, type(effect).__name__, amount_i, int(n_targets))


# ── Non-combat damage attribution (Boba Fett JTL_9 observer) ──────────────────
#
# The two non-combat damage sinks below (_apply_deal_damage / _apply_indirect_
# damage) record the *dealer's* player id into GameMemory.noncombat_damage_dealers
# so the WhenDealNonCombatDamage observer can fire at the settle point.  Most
# damage is dealt from within execute_effect, which knows the source's controller;
# it pushes the dealer onto this stack for the duration of the effect (covering
# CustomEffect fns that call _apply_deal_damage synchronously).  The "pop, then
# deal" decision resolvers in actions.py (indirect / distribute / select_damage)
# run outside execute_effect and instead pass ``dealer_id=`` explicitly.
_noncombat_dealer_stack: list = []


class _noncombat_dealer:
    """Context manager: mark the dealer of any non-combat damage dealt while active."""
    def __init__(self, dealer_id):
        self._dealer_id = dealer_id

    def __enter__(self):
        _noncombat_dealer_stack.append(self._dealer_id)
        return self

    def __exit__(self, *exc):
        if _noncombat_dealer_stack:
            _noncombat_dealer_stack.pop()
        return False


def _record_noncombat_damage(state: "GameState", dealer_id=None) -> None:
    """Record that ``dealer_id`` (or the current stack dealer) dealt non-combat
    damage, deduped, for the settle-point observer drain."""
    if dealer_id is None:
        dealer_id = _noncombat_dealer_stack[-1] if _noncombat_dealer_stack else None
    if dealer_id is None:
        return
    queue = state.game_memory.noncombat_damage_dealers
    if dealer_id not in queue:
        queue.append(dealer_id)


# ── Trigger collection ────────────────────────────────────────────────────────

def _cards_in_play(state: "GameState"):
    """Yield all CardInstances currently in any arena."""
    for ps in state.players:
        yield from ps.ground_arena
        yield from ps.space_arena


def _trigger_matches(
    trigger: object,
    event: "GameEvent",
    source_ci: "CardInstance",
    state: "GameState",
    event_ctx: dict,
) -> bool:
    """Return True if this trigger condition fires for the given event."""
    from swu.engine.events import (
        UnitEntersPlay, UnitDefeated, AttackDeclared, RoundStarted,
    )

    if isinstance(trigger, WhenPlayed):
        from swu.engine.events import UpgradePlayed
        if getattr(trigger, "as_upgrade", False):
            # "When played as an upgrade": fire ONLY on the upgrade/pilot play
            # path, never when the same Piloting unit is played as a normal unit
            # (Boba Fett JTL_189).
            return (isinstance(event, UpgradePlayed)
                    and event.instance_id == source_ci.instance_id)
        if getattr(trigger, "as_unit", False):
            # "When played as a unit": fire ONLY on the normal unit play path,
            # never when the same Piloting unit is played as a Pilot upgrade
            # (The Mandalorian JTL_210).
            return (isinstance(event, UnitEntersPlay)
                    and event.instance_id == source_ci.instance_id)
        if isinstance(event, UnitEntersPlay) and event.instance_id == source_ci.instance_id:
            return True
        if isinstance(event, UpgradePlayed) and event.instance_id == source_ci.instance_id:
            return True
        return False

    if isinstance(trigger, WhenPlayedViaSmuggle):
        # Only fires when the play used the Smuggle keyword (flagged in event_ctx).
        if not event_ctx.get("via_smuggle"):
            return False
        if isinstance(event, UnitEntersPlay) and event.instance_id == source_ci.instance_id:
            return True
        from swu.engine.events import UpgradePlayed
        if isinstance(event, UpgradePlayed) and event.instance_id == source_ci.instance_id:
            return True
        return False

    if isinstance(trigger, WhenDeployed):
        from swu.engine.events import LeaderDeployed
        if not (isinstance(event, LeaderDeployed)
                and event.instance_id == source_ci.instance_id):
            return False
        # via_pilot_leader=True → only fire on the pilot-deploy path (Boba Fett
        # JTL_9 "When deployed as an upgrade: …"); False → any deploy (default).
        if trigger.via_pilot_leader and not event_ctx.get("via_pilot_leader"):
            return False
        return True

    if isinstance(trigger, WhenYouDeployLeader):
        # "When you deploy a leader" (Shadow Collective Camp TWI_25): an observer on
        # another permanent, so — unlike WhenDeployed — the instance ids are NOT
        # compared; the gate is that the deploying player is the source's controller.
        from swu.engine.events import LeaderDeployed
        return (isinstance(event, LeaderDeployed)
                and event.player_id == source_ci.owner_id)

    if isinstance(trigger, WhenDefeated):
        return (
            isinstance(event, UnitDefeated)
            and event.instance_id == source_ci.instance_id
        )

    if isinstance(trigger, WhenDefeatedAsUpgrade):
        # The UnitDefeated event here is the HOST's (the pilot was detached when its
        # host died), so we do NOT compare instance ids — the "this card was defeated
        # as an upgrade" gating is structural: this trigger is collected ONLY from the
        # ``defeated_upgrades`` scan (see _collect_triggers), where the source is the
        # detached upgrade itself (Luke Skywalker J25_4).
        return isinstance(event, UnitDefeated)

    if isinstance(trigger, OnAttack):
        if not (isinstance(event, AttackDeclared)
                and event.attacker_instance_id == source_ci.instance_id):
            return False
        # "If this unit is attacking a unit" (LAW_62) — a base attack has no defender.
        if getattr(trigger, "vs_unit", False) and event.defender_instance_id is None:
            return False
        return True

    if isinstance(trigger, WhenUnitAttacks):
        # An observer (e.g. a Base) fires when a unit matching its filter attacks
        # (Jedi Temple LOF_23: "When a friendly Force unit attacks").  The attacker
        # is never the source itself.
        if not isinstance(event, AttackDeclared):
            return False
        if event.attacker_instance_id == source_ci.instance_id:
            return False
        att = state.find_instance(event.attacker_instance_id)
        if att is None:
            return False
        _, attacker_ci = att
        return _spec_matches_ci(trigger.filter, attacker_ci, source_ci, state, event_ctx)

    if isinstance(trigger, WhenAttacked):
        return (
            isinstance(event, AttackDeclared)
            and event.defender_instance_id == source_ci.instance_id
        )

    if isinstance(trigger, WhenEnemyAttacksYourBase):
        # Observer: fires when an OPPONENT of the source's controller declares an
        # attack against a base (defender is None).  A base attack always targets
        # the non-active player's base, so an enemy attacker means the source
        # controller's own base is under attack (two-player).  Records the
        # attacker's arena for a "friendly unit in the same arena" target
        # (Kragan Gorr SHD_241).
        if not isinstance(event, AttackDeclared):
            return False
        if event.defender_instance_id is not None:
            return False
        att = state.find_instance(event.attacker_instance_id)
        if att is None:
            return False
        att_ps, attacker_ci = att
        if att_ps.player_id == source_ci.owner_id:
            return False
        from swu.engine.state import Zone
        arena = "space" if attacker_ci.zone == Zone.SPACE_ARENA else "ground"
        # "When an enemy GROUND unit attacks your base" (Aurra Sing TWI_166) —
        # the optional arena narrowing; None (SHD_241) matches either arena.
        if trigger.arena is not None and trigger.arena != arena:
            return False
        event_ctx["same_arena"] = arena
        return True

    if isinstance(trigger, WhenUnitDefeated):
        if not isinstance(event, UnitDefeated):
            return False
        # The defeated unit must match the filter FROM the source card's perspective
        defeated_ps_result = state.find_instance(event.instance_id)
        if defeated_ps_result is None:
            # By the time UnitDefeated fires, _defeat_unit has already pulled the
            # unit out of its arena, so find_instance can't see it.  Apply the
            # filter against the defeated CardInstance handed to us in event_ctx
            # (its owner_id is unchanged and its arena zone is not cleared until
            # after the triggers fire) so a *filtered* observer — e.g. Rogue One
            # LAW_119's "a friendly unit" — is not fired for the wrong controller.
            dci = event_ctx.get("defeated_ci")
            if dci is not None and dci.instance_id == event.instance_id:
                return _spec_matches_ci(trigger.filter, dci, source_ci, state, event_ctx)
            return event_ctx.get("defeated_id") == event.instance_id
        _, defeated_ci = defeated_ps_result
        return _spec_matches_ci(trigger.filter, defeated_ci, source_ci, state, event_ctx)

    if isinstance(trigger, WhenYouTakeInitiative):
        # Ziton Moj SEC_168 — fires only for cards controlled by the player who just
        # claimed the initiative.
        from swu.engine.events import InitiativeTaken
        if not isinstance(event, InitiativeTaken):
            return False
        return event.player_id == source_ci.owner_id

    if isinstance(trigger, WhenUnitEntersPlay):
        if not isinstance(event, UnitEntersPlay):
            return False
        result = state.find_instance(event.instance_id)
        if result is None:
            return False
        _, entered_ci = result
        return _spec_matches_ci(trigger.filter, entered_ci, source_ci, state, event_ctx)

    if isinstance(trigger, OnAttackDefeatsUnit):
        # Fires after combat when the attacker survived and the defender died.
        # Captured via a dedicated "attacker_defeats_unit" event context key.
        return event_ctx.get("attack_defeated_unit") == source_ci.instance_id

    if isinstance(trigger, WhenFriendlyUnitAttacksAndDefeatsUnit):
        # The group analogue (Darth Revan LOF_17): same firing site / event_ctx key
        # as OnAttackDefeatsUnit, but for an observer whose controller controls the
        # attacker.  The source itself qualifies ("a friendly unit").
        aid = event_ctx.get("attack_defeated_unit")
        if not aid:
            return False
        res = state.find_instance(aid)
        if res is None:
            return False
        att_ps, _ = res
        return att_ps.player_id == source_ci.owner_id

    if isinstance(trigger, WhenDealsCombatDamageToBase):
        # Fires after a base attack's combat damage, flagged in event_ctx.
        dealer_id = event_ctx.get("dealt_combat_damage_to_base")
        if not dealer_id:
            return False
        if (trigger.min_amount
                and event_ctx.get("base_combat_damage_amount", 0) < trigger.min_amount):
            return False
        if trigger.filter is None:
            return dealer_id == source_ci.instance_id
        # Observer form (Temple of Destruction LOF_25): a Base watches for any unit
        # matching the filter from its own perspective having dealt the damage.
        res = state.find_instance(dealer_id)
        if res is None:
            return False
        _, dealer_ci = res
        return _spec_matches_ci(trigger.filter, dealer_ci, source_ci, state, event_ctx)

    if isinstance(trigger, WhenDealtCombatDamage):
        # Fires after unit combat for a surviving unit that took combat damage,
        # flagged in event_ctx (the firing site only fires for a still-in-play unit).
        return event_ctx.get("dealt_combat_damage_to") == source_ci.instance_id

    if isinstance(trigger, WhenFriendlyUnitDealtCombatDamage):
        # The group analogue of WhenDealtCombatDamage: fires for an OBSERVER when a
        # friendly unit (optionally trait-filtered) took combat damage and survived
        # (Tarfful SHD_250).  Same event_ctx key and firing site, so "isn't
        # defeated" is equally intrinsic; the source itself qualifies when it
        # matches the filter ("a friendly Wookiee unit" includes Tarfful).
        hit_id = event_ctx.get("dealt_combat_damage_to")
        if not hit_id:
            return False
        res = state.find_instance(hit_id)
        if res is None:
            return False
        hit_ps, hit_ci = res
        if hit_ps.player_id != source_ci.owner_id:
            return False
        if trigger.traits:
            from swu.engine.traits import has_trait
            if not all(has_trait(state, hit_ci, t) for t in trigger.traits):
                return False
        return True

    if isinstance(trigger, WhenDealsCombatDamageToUnit):
        # Fires for the ATTACKER after it dealt combat damage to a still-in-play
        # defender unit (Rukh SOR_85), flagged in event_ctx.  ``non_leader_only``
        # suppresses it when the defender is a leader unit.
        if event_ctx.get("attacker_dealt_combat_damage_to_unit") != source_ci.instance_id:
            return False
        if getattr(trigger, "non_leader_only", False):
            from swu.cards.models import Leader
            did = event_ctx.get("defender_id")
            dres = state.find_instance(did) if did else None
            if dres is None or isinstance(dres[1].card_def, Leader):
                return False
        return True

    if isinstance(trigger, WhenFriendlyUnitDealsCombatDamageToEnemyUnit):
        # The group analogue of the trigger above (Jango Fett TWI_16): fires for an
        # observer when ANOTHER unit its controller controls dealt combat damage to a
        # still-in-play enemy defender.  Same keys, same firing site.
        dealer_id = event_ctx.get("attacker_dealt_combat_damage_to_unit")
        if not dealer_id or dealer_id == source_ci.instance_id:
            return False
        dres = state.find_instance(dealer_id)
        if dres is None or dres[0].player_id != source_ci.owner_id:
            return False
        return True

    if isinstance(trigger, WhenFriendlyUnitAttackEnds):
        # "When a friendly <Trait> unit's attack ends: If the defending unit was
        # defeated, …" (Boba Fett LAW_7).  Its own key pair, set at a dedicated
        # fire that runs whether or not the attacker survived — the card's printed
        # rules note says it need not (see the trigger's docstring).
        att_id = event_ctx.get("attack_ended_attacker")
        if att_id is None:
            return False
        if (getattr(trigger, "require_defender_defeated", False)
                and not event_ctx.get("attack_ended_defender_defeated")):
            return False
        _min_base = int(getattr(trigger, "require_base_damage_min", 0) or 0)
        if _min_base:
            # "If it dealt N or more combat damage to a base" (Ezra Bridger ASH_13).
            # Both a direct base attack and an Overwhelm spill carry the amount.
            if int(event_ctx.get("attack_ended_base_damage_amount", 0) or 0) < _min_base:
                return False
        # The attacker may be DEAD, so resolve it wherever it now sits
        # (``find_instance`` reaches the discard) to read its controller + traits.
        att = state.find_instance(att_id)
        if att is None:
            return False
        res = state.find_instance(source_ci.instance_id)
        controller = res[0].player_id if res is not None else source_ci.owner_id
        if att[0].player_id != controller:
            return False
        if trigger.traits:
            from swu.engine.traits import has_trait
            if not all(has_trait(state, att[1], t) for t in trigger.traits):
                return False
        return True

    if isinstance(trigger, WhenYouPlayOrCreateUnit):
        # Settle-drain observer: a unit entered play under the observer's
        # controller ("When you play or create a unit" Greef Karga ASH_17; "When a
        # friendly unit enters play (including this one)" Outcast ASH_41).
        entered_id = event_ctx.get("entered_unit_id")
        if entered_id is None:
            return False
        if not trigger.include_self and entered_id == source_ci.instance_id:
            return False
        res = state.find_instance(source_ci.instance_id)
        controller = res[0].player_id if res is not None else source_ci.owner_id
        return event_ctx.get("entered_unit_player") == controller

    if isinstance(trigger, WhenAttackEnds):
        # Fires for the attacker at the end of its attack, flagged in event_ctx;
        # the firing site only sets the key for an attacker still in play, so the
        # "if this unit survived" clause is intrinsic (Vermillion LAW_215).
        if event_ctx.get("attack_ended_survivor") != source_ci.instance_id:
            return False
        if getattr(trigger, "require_base_damage", False):
            # Maul LAW_54: only when this attack dealt combat damage to a base (the
            # base-attack fire carries this distinct key alongside
            # attack_ended_survivor — NOT dealt_combat_damage_to_base, which would
            # re-match Ketsu Onyo SHD_147's separate trigger).
            return event_ctx.get("attack_ended_base_damage") == source_ci.instance_id
        if getattr(trigger, "require_defender_defeated", False):
            # "If the defending unit was defeated" (Thrawn ASH_33, Halo ASH_223) —
            # both unit-combat pipelines carry the defeated defender's id on this
            # fire; a base attack never sets it.
            return bool(event_ctx.get("attack_ended_defender_defeated"))
        return True

    if isinstance(trigger, WhenIndirectDamageDealtToUnit):
        # Observer trigger: fires for any card in play when indirect damage was
        # dealt to a unit (Allegiant General Pryde JTL_133).  The key is set by
        # _resolve_assign_indirect_damage when the chosen target is a unit; no
        # source-card filter (unlike WhenDealtCombatDamage which is source-specific).
        return bool(event_ctx.get("indirect_damage_unit_id"))

    if isinstance(trigger, WhenDealNonCombatDamage):
        # Observer trigger: fires when the source's controller dealt non-combat
        # damage (Boba Fett JTL_9).  The dealer's player id is drained from the
        # ledger into event_ctx by actions._fire_noncombat_damage_observers; "when
        # YOU deal" means it must equal the source's controller.
        return event_ctx.get("noncombat_damage_dealer_id") == source_ci.owner_id

    if isinstance(trigger, WhenYouDraw):
        # Observer trigger fired at the settle-point from the ACTION-phase draw
        # ledger (event is None).  ``on_self`` fires for the drawn card itself
        # (Rey LOF_148 — matched by its id being among the drawn cards); otherwise
        # an in-play observer fires when its controller drew (The Mandalorian
        # LAW_52 — "when YOU draw").
        # Draws outside the ACTION phase are ledgered too, but only a trigger that
        # PRINTS "(including during the regroup phase)" reads them (Axe Woves
        # ASH_169); every other WhenYouDraw keeps its action-phase-only wording.
        if (not getattr(trigger, "any_phase", False)
                and event_ctx.get("draw_phase", "ACTION") != "ACTION"):
            return False
        if trigger.on_self:
            return source_ci.instance_id in event_ctx.get("drawn_card_ids", [])
        drew_id = event_ctx.get("drew_player_id")
        if getattr(trigger, "any_player", False):
            # "When a player draws …" (Chairman Papanoida SEC_159) — either seat.
            return drew_id is not None
        if getattr(trigger, "opponent", False):
            # "When an opponent draws" (Seasoned Fleet Admiral JTL_111).
            return drew_id is not None and drew_id != source_ci.owner_id
        return drew_id == source_ci.owner_id

    if isinstance(trigger, WhenYouUseForce):
        # Observer trigger fired at the settle-point from the Force-use ledger
        # (event is None; Yoda LOF_101).  The spender's player id is drained into
        # event_ctx by actions._fire_force_observers; "when YOU use the Force"
        # means it must equal the source's controller.
        return event_ctx.get("force_used_player_id") == source_ci.owner_id

    if isinstance(trigger, WhenYouRevealOrDiscard):
        # Observer trigger fired at the settle-point from the reveal/discard-from-hand
        # ledger (event is None; Padmé Amidala SEC_16).  The acting player's id is
        # drained into event_ctx by actions._fire_reveal_discard_observers; "when YOU
        # reveal or discard" means it must equal the source's controller.
        return event_ctx.get("hand_reveal_discard_player_id") == source_ci.owner_id

    if isinstance(trigger, WhenPlayerDiscardsFromHand):
        # Observer trigger fired at the settle-point from the discard-only ledger
        # (event is None; Migs Mayfeld SHD_163).  "When A PLAYER discards" — matches on
        # ANY player's discard, so there is NO owner_id guard (mirroring the
        # WhenIndirectDamageDealtToUnit any-card observer).  A Disclose reveal never
        # records into this ledger, so it cannot match here.
        return event_ctx.get("hand_discard_player_id") is not None

    if isinstance(trigger, WhenThisIsDiscarded):
        # Observer trigger fired at the settle-point from the hand/deck-discard ledger
        # (event is None; That's a Rock LAW_206).  "When THIS card is discarded" —
        # strictly self-referential, so the discarded instance id must be the source's
        # own.  The source is the discarded card itself, found in its owner's discard
        # pile by the dedicated scan in _collect_triggers.
        return event_ctx.get("self_discard_id") == source_ci.instance_id

    if isinstance(trigger, WhenYouDiscardFromDeck):
        # Observer trigger fired at the settle-point from the DECK-discard ledger
        # (event is None; Sebulba's Podracer LAW_176).  "When YOU discard a card from
        # your deck" — the miller must be the source's own controller, so an
        # opponent's self-mill (or a foreign deck_search milling THEIR deck) does not
        # fire it.  The source is an ordinary card in play, found by the standard scan.
        miller = event_ctx.get("deck_discard_player_id")
        if miller is None:
            return False
        res = state.find_instance(source_ci.instance_id)
        controller = res[0].player_id if res is not None else source_ci.owner_id
        return miller == controller

    if isinstance(trigger, WhenUnitHealed):
        # Observer trigger fired at the settle-point from the heal ledger (event is
        # None; Silver Angel JTL_62).  "…healed from THIS unit" — strictly
        # self-referential, so the healed instance id must be the source's own.
        return event_ctx.get("healed_unit_id") == source_ci.instance_id

    if isinstance(trigger, WhenDamageDealtToYourBase):
        # Observer trigger fired at the settle-point from the base-damage ledger
        # (event is None; The Daughter LOF_252).  "YOUR base" — the damaged base's
        # owner must be the source's controller.
        return event_ctx.get("base_damaged_player_id") == source_ci.owner_id

    if isinstance(trigger, WhenUnitReadies):
        # Observer trigger fired at the settle-point from the ready ledger (event is
        # None; In Debt to Crimson Dawn JTL_192).  "When ATTACHED UNIT readies" — the
        # spec rides in a GrantedAbility, so the source here is already the HOST.
        readied_id = event_ctx.get("readied_unit_id")
        if getattr(trigger, "action_phase", False):
            if str(event_ctx.get("readied_phase") or "ACTION") != "ACTION":
                return False
        if getattr(trigger, "controller", None) == "enemy":
            # "When an ENEMY unit readies" (Rex's DC-17s TS26_63) — resolved through
            # find_instance so the readied unit's current HOLDER decides, and never
            # matching the source itself.
            if not readied_id or readied_id == source_ci.instance_id:
                return False
            res = state.find_instance(readied_id) if state is not None else None
            return res is not None and res[0].player_id != source_ci.owner_id
        return readied_id == source_ci.instance_id

    if isinstance(trigger, WhenFriendlyUpgradeDefeated):
        # Observer trigger fired at the settle-point from the upgrade-defeat ledger
        # (event is None; Zeb Orrelios ASH_161).  "FRIENDLY" = the defeated upgrade's
        # controller (the host's controller) is the source's controller.
        return event_ctx.get("upgrade_defeat_controller") == source_ci.owner_id

    if isinstance(trigger, WhenUpgradeAttached):
        # Observer trigger fired at the settle-point from the upgrade-attach ledger
        # (event is None; Sabine Wren ASH_208).  Self-referential: the ledger names
        # the HOST, coalesced per host, so "1 or more upgrades attach to THIS unit"
        # is exactly this identity test.
        return event_ctx.get("upgrade_attached_host") == source_ci.instance_id

    if isinstance(trigger, WhenYouWouldCreateTokens):
        # Observer trigger fired at the settle-point from the token-creation ledger
        # (event is None; Moff Jerjerrod ASH_94).  "If YOU would create" — the
        # creating player must be the source's controller.
        return event_ctx.get("token_creation_creator") == source_ci.owner_id

    if isinstance(trigger, WhenBountyCollected):
        # Observer trigger fired at the settle-point from the bounties-collected
        # ledger (event is None; Bossk SHD_10).  The collector's player id is drained
        # into event_ctx by actions._fire_bounty_observers; "when YOU collect a
        # bounty" means it must equal the source's controller.
        return event_ctx.get("bounty_collector_id") == source_ci.owner_id

    if isinstance(trigger, WhenYouPlayCard):
        from swu.engine.events import CardPlayed
        if not isinstance(event, CardPlayed):
            return False
        if event.player_id != source_ci.owner_id:
            return False
        if trigger.exclude_self and event.instance_id == source_ci.instance_id:
            return False
        if getattr(trigger, "via_smuggle", False) and not event_ctx.get("via_smuggle"):
            # "When you play a card using Smuggle" (Hondo Ohnaka SHD_5) — only a
            # smuggle play (the via_smuggle event_ctx flag) qualifies.
            return False
        if getattr(trigger, "has_any_keyword", False):
            # "a unit/card that has 1 or more keywords" (Boba Fett SHD_8): read the
            # played card's effective keywords via the keyword layer.
            from swu.engine.keywords import has_any_keyword
            result = state.find_instance(event.instance_id)
            if result is None:
                return False
            if not has_any_keyword(state, result[1]):
                return False
        if trigger.on_self:
            # "an upgrade on this unit" (Kylo Ren LOF_229): the played card must be
            # attached to the source unit.  By the time CardPlayed fires the upgrade
            # is already in its host's attached_upgrades (PlayCard attaches first),
            # so locate the host by scanning in-play units.
            host = next(
                (u for u in _cards_in_play(state)
                 if any(up.instance_id == event.instance_id
                        for up in u.attached_upgrades)),
                None,
            )
            if host is None or host.instance_id != source_ci.instance_id:
                return False
        if (trigger.aspect or trigger.card_type or trigger.trait or trigger.unique
                or trigger.cost_min is not None or getattr(trigger, "non_unit", False)):
            result = state.find_instance(event.instance_id)
            if result is None:
                return False
            _, played_ci = result
            if getattr(trigger, "non_unit", False):
                # "When you play a non-unit card" (Tobias Beckett SHD_217): the
                # played card must NOT be a Unit (events + upgrades qualify).
                from swu.cards.models import Unit
                if isinstance(played_ci.card_def, Unit):
                    return False
            if trigger.cost_min is not None:
                pc = getattr(played_ci.card_def, "cost", None)
                if pc is None or pc < trigger.cost_min:
                    return False
            if trigger.aspect:
                names = {a.name for a in (getattr(played_ci.card_def, "aspects", None) or ())}
                if trigger.aspect not in names:
                    return False
            if trigger.card_type == "upgrade":
                from swu.cards.models import Upgrade
                if not isinstance(played_ci.card_def, Upgrade):
                    return False
            if trigger.card_type == "unit":
                from swu.cards.models import Unit
                if not isinstance(played_ci.card_def, Unit):
                    return False
            if trigger.card_type == "event":
                from swu.cards.models import Event
                if not isinstance(played_ci.card_def, Event):
                    return False
            if trigger.trait:
                from swu.engine.traits import has_trait
                if not has_trait(state, played_ci, trigger.trait):
                    return False
            if trigger.unique and not getattr(played_ci.card_def, "is_unique", False):
                return False
            # Record the played card's printed cost so an effect can target
            # "a unit that costs the same as or less than the played unit"
            # (cost_le_event_threshold predicate, Tactical Droid Commander TWI_184).
            event_ctx["cost_le_threshold"] = getattr(played_ci.card_def, "cost", None)
        return True

    if isinstance(trigger, WhenOpponentPlaysNthCard):
        # Observer: fires when an OPPONENT plays their ``count``-th card this phase.
        # The per-phase per-player counter is incremented at the CardPlayed firing
        # chokepoint (fire_triggered_abilities) BEFORE trigger collection, so the
        # count here already includes this play; ``== count`` fires exactly once
        # (their second card), not on every subsequent play.  Ki-Adi-Mundi TWI_64.
        from swu.engine.events import CardPlayed
        if not isinstance(event, CardPlayed):
            return False
        if event.player_id == source_ci.owner_id:
            return False  # a friendly play, not an opponent's
        count = state.game_memory.cards_played_this_phase.get(event.player_id, 0)
        return count == trigger.count

    if isinstance(trigger, WhenOpponentPlaysCard):
        # Observer: fires when an OPPONENT plays a card matching ``card_type``
        # (Saw Gerrera SOR_153 — additional-cost-as-observer simplification).  The
        # event player's id is recorded so the DealDamage lands on THEIR base; in
        # 2-player, controller="enemy" already resolves to that base.
        from swu.engine.events import CardPlayed
        if not isinstance(event, CardPlayed):
            return False
        if event.player_id == source_ci.owner_id:
            return False  # a friendly play, not an opponent's
        result = state.find_instance(event.instance_id)
        if trigger.card_type:
            if result is None:
                return False
            _, played_ci = result
            if trigger.card_type == "event":
                from swu.cards.models import Event
                if not isinstance(played_ci.card_def, Event):
                    return False
        # Record the played card's printed cost so an effect can deal "damage equal
        # to that card's cost" (DealDamageEqualTo count "event_played_card_cost",
        # Krayt Dragon SHD_172).  Public info (a played card's cost); no hidden-info
        # leak, so it needs no _TRANSIENT strip.
        if result is not None:
            event_ctx["event_played_card_cost"] = getattr(result[1].card_def, "cost", None)
        # "If that opponent paid less than the card's cost to play it" (Lux Bonteri
        # TWI_210) — every play path stamps what was actually paid on the event, so
        # the discount is just paid < printed.  A card with no printed cost (or an
        # unlocatable one) can't be shown to have been discounted, so it doesn't
        # match.  Default False = the SOR_153 behaviour, unchanged.
        if trigger.paid_less_than_cost:
            printed = (getattr(result[1].card_def, "cost", None)
                       if result is not None else None)
            if printed is None or event.cost_paid >= printed:
                return False
        return True

    if isinstance(trigger, RoundStartTrigger):
        from swu.engine.events import RoundStarted
        return isinstance(event, RoundStarted)

    if isinstance(trigger, PhaseStartTrigger):
        # "When the <phase> phase starts" — matches the PhaseChanged event the
        # engine emits at a phase transition (fired through fire_triggered_abilities
        # only at the regroup transition today; Contracted Hunter JTL_216).
        from swu.engine.events import PhaseChanged
        if not isinstance(event, PhaseChanged):
            return False
        if (event.new_phase or "").lower() != (trigger.phase or "").lower():
            return False
        # "the FIRST action phase" (Nabat Village JTL_28) — round 1 only.
        if getattr(trigger, "first_only", False):
            return int(getattr(event, "round_number", 0) or 0) <= 1
        return True

    return False


def _collect_triggers(
    state: "GameState",
    event: "GameEvent",
    event_ctx: dict,
) -> list[tuple["CardInstance", "CardInstance", int, TriggerAbility]]:
    """Return (source_ci, spec_ci, ability_idx, ability) for every trigger.

    ``source_ci`` is the unit the trigger fires for and whose perspective the
    effects resolve from; ``spec_ci`` is the card whose registry holds the spec
    addressed by ``ability_idx``.  These coincide for an ordinary unit/leader
    trigger, but differ for an upgrade's *granted* ability (``GrantedAbility``,
    e.g. Armed to the Teeth SHD_175): there ``source_ci`` is the host unit while
    ``spec_ci`` is the upgrade, so the pushed decision is addressed to the
    upgrade's registry entry but resolves from the host.
    """
    from swu.cards.models import Leader
    from swu.engine.events import UnitDefeated
    from swu.engine.state import borrowed_ability_sources
    results = []
    candidates = list(_cards_in_play(state))
    for ci in candidates:
        if not hasattr(ci.card_def, "set_code") or not hasattr(ci.card_def, "card_number"):
            continue
        # A unit whose abilities are suppressed this phase (Mind Trick LOF_202) or
        # named by an enemy Galen Erso (P25_31) is no trigger source — skip its own,
        # upgrade-granted, and leader-as-upgrade triggers.
        from swu.engine.state import ability_suppressed
        if ability_suppressed(state, ci):
            continue
        set_code = ci.card_def.set_code or ""
        card_number = ci.card_def.card_number or ""
        is_leader_card = isinstance(ci.card_def, Leader)
        is_deployed_leader = is_leader_card and ci.deployed
        for idx, spec in enumerate(get_abilities(set_code, card_number)):
            if not isinstance(spec, TriggerAbility):
                continue
            # Gate leader abilities by deployment state.  ``undeployed_only`` says
            # something only about a LEADER — and a token unit shares its (set,
            # number) with a real card (the Clone Trooper token is TWI_2, the same
            # registry key as the leader Nute Gunray), so a non-leader instance must
            # never collect an undeployed-side trigger through that collision.
            if spec.deployed_only and not is_deployed_leader:
                continue
            if spec.undeployed_only and (is_deployed_leader or not is_leader_card):
                continue
            if _trigger_matches(spec.trigger, event, ci, state, event_ctx):
                if spec.condition is None or spec.condition.evaluate(state, ci):
                    results.append((ci, ci, idx, spec))

        # Upgrade-granted abilities: an upgrade attached to this unit may confer a
        # triggered ability on it ("Attached unit gains: '<ability>'", Armed to
        # the Teeth SHD_175).  The granted ability behaves as if registered on the
        # host (ci) — trigger matching and effect resolution both use ci as the
        # source — but the spec lives in the upgrade's registry, so the trigger is
        # addressed to the upgrade (spec_ci) at the granted ability's index.
        for upg in ci.attached_upgrades:
            ucd = getattr(upg, "card_def", None)
            if ucd is None or not hasattr(ucd, "set_code") or not hasattr(
                    ucd, "card_number"):
                continue
            for idx, spec in enumerate(get_abilities(ucd.set_code or "", ucd.card_number or "")):
                if not isinstance(spec, GrantedAbility):
                    continue
                inner = spec.ability
                if not isinstance(inner, TriggerAbility):
                    continue
                if _trigger_matches(inner.trigger, event, ci, state, event_ctx):
                    if inner.condition is None or inner.condition.evaluate(state, ci):
                        results.append((ci, upg, idx, inner))

        # A LEADER deployed as an upgrade (Boba Fett JTL_9) lives in a host unit's
        # attached_upgrades, so the arena scan above never yields it — yet it
        # carries its own triggered abilities (the "When deployed as an upgrade"
        # deal-up-to-4, and the ongoing "when you deal non-combat damage" observer),
        # which resolve from the leader-upgrade instance itself as source.  Scan for
        # a deployed Leader upgrade and collect its plain (non-granted) triggers,
        # mirroring the arena leader scan (undeployed_only is skipped — a
        # deployed-as-upgrade leader is deployed).  Purely additive: no leader was
        # ever an upgrade before this session.
        for upg in ci.attached_upgrades:
            ucd = getattr(upg, "card_def", None)
            if not isinstance(ucd, Leader) or not upg.deployed:
                continue
            for idx, spec in enumerate(get_abilities(ucd.set_code or "", ucd.card_number or "")):
                if not isinstance(spec, TriggerAbility):
                    continue
                if spec.undeployed_only:
                    continue
                if _trigger_matches(spec.trigger, event, upg, state, event_ctx):
                    if spec.condition is None or spec.condition.evaluate(state, upg):
                        results.append((upg, upg, idx, spec))

        # BORROWED abilities — the Support keyword's "It gains this unit's other
        # abilities for this attack" (ASH).  A ``borrowed_abilities`` this-attack
        # modifier on ``ci`` names a LENDER whose registered triggers are collected
        # here as if printed on ci: ``source_ci`` is the borrower (the ability
        # resolves from it — "this unit" is the attacker), while ``spec_ci`` is the
        # lender, whose registry holds the spec.  Exactly the GrantedAbility
        # source/spec split above, one card further away.
        for lender in borrowed_ability_sources(state, ci):
            lcd = getattr(lender, "card_def", None)
            lsc = getattr(lcd, "set_code", None) or ""
            lcn = getattr(lcd, "card_number", None) or ""
            if not lsc or not lcn:
                continue
            # A leader's two sides are gated by the LENDER's own deployment state:
            # the borrower is lent whichever side the lender is currently showing.
            l_is_leader = isinstance(lcd, Leader)
            l_deployed = l_is_leader and lender.deployed
            for idx, spec in enumerate(get_abilities(lsc, lcn)):
                if not isinstance(spec, TriggerAbility):
                    continue
                if spec.deployed_only and not l_deployed:
                    continue
                if spec.undeployed_only and (l_deployed or not l_is_leader):
                    continue
                if _trigger_matches(spec.trigger, event, ci, state, event_ctx):
                    if spec.condition is None or spec.condition.evaluate(state, ci):
                        results.append((ci, lender, idx, spec))

    # An ONGOING triggered ability a SOURCE confers as an AURA on every unit matching
    # its target ("… gains: '<triggered ability>'") — the in-play half of the
    # ``AuraGrantedAbility`` seam, and the mirror of the upgrade-borne GrantedAbility
    # scan above.  Implicate SEC_231: "Choose a unit.  For this phase, it gains
    # Sentinel and: 'When this unit is attacked: Create a Spy token.'"
    #
    # A ``WhenDefeated`` inner trigger is deliberately EXCLUDED here and collected at
    # the UnitDefeated path below instead (Gar Saxon SHD_1): by then the dying unit is
    # already out of its arena and so is absent from ``candidates``, which is exactly
    # why that path exists.  Every other trigger kind fires for a unit that is still in
    # play, so it belongs in this scan.  Purely additive — until Implicate, every
    # registered aura grant wrapped either a WhenDefeated trigger or an ActivatedAbility
    # (Satine Kryze TWI_47, surfaced by the aura scan in ``actions.legal_actions``).
    #
    # Phase-scoped sources (``game_memory.phase_aura_sources``) are scanned alongside
    # the in-play ones, so a spent EVENT keeps granting from the discard for the rest of
    # the phase — find_instance reaches the discard and the recovered instance still
    # carries its real owner_id (Pyrrhic Assault TWI_103).
    aura_sources = list(candidates)
    _gm = getattr(state, "game_memory", None)
    for _aid in (getattr(_gm, "phase_aura_sources", None) or ()):
        _ares = state.find_instance(_aid)
        if _ares is not None and _ares[1] not in aura_sources:
            aura_sources.append(_ares[1])
    for src in aura_sources:
        scd = getattr(src, "card_def", None)
        if scd is None or not hasattr(scd, "set_code") or not hasattr(
                scd, "card_number"):
            continue
        from swu.engine.state import ability_suppressed as _aura_suppressed
        if _aura_suppressed(state, src):
            continue
        aura_specs = [
            (i, sp) for i, sp in enumerate(get_abilities(scd.set_code or "",
                                                        scd.card_number or ""))
            if isinstance(sp, AuraGrantedAbility)
            and isinstance(sp.ability, TriggerAbility)
            and not isinstance(sp.ability.trigger, WhenDefeated)
        ]
        if not aura_specs:
            continue
        for ci in candidates:
            if not hasattr(ci.card_def, "set_code") or not hasattr(ci.card_def, "card_number"):
                continue
            # A unit whose abilities are suppressed can't gain one either.
            if _aura_suppressed(state, ci):
                continue
            for idx, spec in aura_specs:
                inner = spec.ability
                if not isinstance(inner, TriggerAbility):
                    continue  # already filtered when aura_specs was built
                if not _spec_matches_ci(spec.target, ci, src, state, event_ctx):
                    continue
                if _trigger_matches(inner.trigger, event, ci, state, event_ctx):
                    if inner.condition is None or inner.condition.evaluate(state, ci):
                        results.append((ci, src, idx, inner))

    # Undeployed leaders live in base_zone (not an arena), so _cards_in_play
    # above never yields them — yet an undeployed leader may carry a triggered
    # ability (The Mandalorian SHD_18 undeployed: "When you play an upgrade: …").
    # Scan each player's base_zone leader for its undeployed triggers, mirroring
    # the arena loop's deployment gating (an undeployed leader is never a
    # deployed-leader, so deployed_only triggers are skipped and undeployed_only/
    # unflagged ones are eligible).  Purely additive: no card relied on
    # undeployed-leader triggers staying silent.
    from swu.cards.models import Base
    for ps in state.players:
        for ci in ps.base_zone:
            # A Base may carry an observer trigger (Jedi Temple LOF_23: "When a
            # friendly Force unit attacks: …").  Bases live in base_zone, never an
            # arena, so _cards_in_play above never yields them — scan them here.
            # Purely additive: no Base had a trigger ability before.
            if isinstance(ci.card_def, Base):
                if not hasattr(ci.card_def, "set_code") or not hasattr(ci.card_def, "card_number"):
                    continue
                for idx, spec in enumerate(get_abilities(ci.card_def.set_code or "",
                                                         ci.card_def.card_number or "")):
                    if not isinstance(spec, TriggerAbility):
                        continue
                    if _trigger_matches(spec.trigger, event, ci, state, event_ctx):
                        if spec.condition is None or spec.condition.evaluate(state, ci):
                            results.append((ci, ci, idx, spec))
                continue
            if not isinstance(ci.card_def, Leader) or ci.deployed:
                continue
            if not hasattr(ci.card_def, "set_code") or not hasattr(ci.card_def, "card_number"):
                continue
            for idx, spec in enumerate(get_abilities(ci.card_def.set_code or "",
                                                     ci.card_def.card_number or "")):
                if not isinstance(spec, TriggerAbility):
                    continue
                if spec.deployed_only:  # the deployed side lives in the arena scan
                    continue
                if _trigger_matches(spec.trigger, event, ci, state, event_ctx):
                    if spec.condition is None or spec.condition.evaluate(state, ci):
                        results.append((ci, ci, idx, spec))

    # A freshly-drawn card's own "When you draw this card" trigger (Rey LOF_148):
    # the card sits in the drawer's HAND, which _cards_in_play never yields, so the
    # arena scan above cannot see it.  For a draw-observer fire (drawn_card_ids in
    # event_ctx) locate each drawn card in the drawer's hand and collect its
    # WhenYouDraw(on_self=True) triggers — scoped to that trigger kind so a hand card
    # never spuriously matches another trigger.  (The in-play observer LAW_52 is
    # already collected by the arena scan above.)
    drawn_ids = event_ctx.get("drawn_card_ids")
    if drawn_ids:
        drawer_id = event_ctx.get("drew_player_id")
        for ps in state.players:
            if drawer_id is not None and ps.player_id != drawer_id:
                continue
            for ci in ps.hand:
                if ci.instance_id not in drawn_ids:
                    continue
                if not hasattr(ci.card_def, "set_code") or not hasattr(ci.card_def, "card_number"):
                    continue
                for idx, spec in enumerate(get_abilities(ci.card_def.set_code or "",
                                                         ci.card_def.card_number or "")):
                    if not isinstance(spec, TriggerAbility):
                        continue
                    if not (isinstance(spec.trigger, WhenYouDraw) and spec.trigger.on_self):
                        continue
                    if _trigger_matches(spec.trigger, event, ci, state, event_ctx):
                        if spec.condition is None or spec.condition.evaluate(state, ci):
                            results.append((ci, ci, idx, spec))

    # A just-discarded card's own "When this card is discarded from your hand or deck"
    # trigger (That's a Rock LAW_206): the card sits in its owner's DISCARD pile, which
    # _cards_in_play never yields, so the arena scan above cannot see it.  For a
    # self-discard observer fire (self_discard_id in event_ctx) locate that one card by
    # id — find_instance reaches the discard — and collect its WhenThisIsDiscarded
    # triggers, scoped to that trigger kind so a discard-pile card never spuriously
    # matches another trigger.  (The Rey LOF_148 hand scan above, mirrored for the
    # discard pile.)
    self_discard_id = event_ctx.get("self_discard_id")
    if self_discard_id:
        res = state.find_instance(self_discard_id)
        if res is not None:
            disc_ci = res[1]
            if (hasattr(disc_ci.card_def, "set_code")
                    and hasattr(disc_ci.card_def, "card_number")):
                for idx, spec in enumerate(get_abilities(disc_ci.card_def.set_code or "",
                                                         disc_ci.card_def.card_number or "")):
                    if not isinstance(spec, TriggerAbility):
                        continue
                    if not isinstance(spec.trigger, WhenThisIsDiscarded):
                        continue
                    if _trigger_matches(spec.trigger, event, disc_ci, state, event_ctx):
                        if spec.condition is None or spec.condition.evaluate(state, disc_ci):
                            results.append((disc_ci, disc_ci, idx, spec))

    # A unit's own "When Defeated" trigger: by the time the UnitDefeated event
    # fires, _defeat_unit() has already pulled the unit out of its arena (and not
    # yet placed it in discard), so it is absent from _cards_in_play above.  The
    # defeated CardInstance is handed to us via event_ctx so its WhenDefeated
    # ability still resolves.  Scoped to WhenDefeated only to avoid the unit
    # spuriously matching other trigger kinds for its own defeat.
    if isinstance(event, UnitDefeated):
        dci = event_ctx.get("defeated_ci")
        from swu.engine.state import ability_suppressed as _abil_suppressed
        if (dci is not None and dci not in candidates
                and hasattr(dci.card_def, "set_code")
                # A unit whose abilities are suppressed is no trigger source, even
                # on its way out — the in-play scan above applies the same guard, but
                # the dying unit has already left its arena so it never reaches it
                # ("the defender loses all abilities for this attack", One Way Out
                # SEC_157, then dies to that very attack).
                and not _abil_suppressed(state, dci)):
            sc = dci.card_def.set_code or ""
            cn = dci.card_def.card_number or ""
            is_dep_leader = isinstance(dci.card_def, Leader) and dci.deployed
            for idx, spec in enumerate(get_abilities(sc, cn)):
                if not isinstance(spec, TriggerAbility):
                    continue
                if not isinstance(spec.trigger, WhenDefeated):
                    continue
                if spec.deployed_only and not is_dep_leader:
                    continue
                if spec.undeployed_only and is_dep_leader:
                    continue
                if _trigger_matches(spec.trigger, event, dci, state, event_ctx):
                    if spec.condition is None or spec.condition.evaluate(state, dci):
                        results.append((dci, dci, idx, spec))

        # Bounty (and any "Attached unit gains: When Defeated …") granted by an
        # upgrade on the defeated unit.  By the time UnitDefeated fires, the host
        # is out of its arena AND its upgrades have already been detached (cleared
        # from ``attached_upgrades`` and sent to discard) — so neither the in-play
        # granted-ability scan above nor ``ci.attached_upgrades`` can see them.
        # ``_defeat_unit`` therefore stashes the detached upgrades in
        # ``event_ctx["defeated_upgrades"]`` so a GrantedAbility(WhenDefeated) (the
        # bounty-granting upgrades Public Enemy SHD_68 / Wanted SHD_221 / Rich
        # Reward SHD_261) still resolves — from the HOST (dci) as source, with the
        # upgrade as the spec card.
        if dci is not None:
            for upg in event_ctx.get("defeated_upgrades", []):
                ucd = getattr(upg, "card_def", None)
                if ucd is None or not hasattr(ucd, "set_code") or not hasattr(
                        ucd, "card_number"):
                    continue
                for idx, spec in enumerate(get_abilities(ucd.set_code or "", ucd.card_number or "")):
                    # (a) A "When Defeated" the upgrade GRANTS to its host (Bounty:
                    #     Public Enemy SHD_68 etc.) — resolves from the HOST (dci).
                    if isinstance(spec, GrantedAbility):
                        inner = spec.ability
                        if not isinstance(inner, TriggerAbility):
                            continue
                        if not isinstance(inner.trigger, WhenDefeated):
                            continue
                        if _trigger_matches(inner.trigger, event, dci, state, event_ctx):
                            if inner.condition is None or inner.condition.evaluate(state, dci):
                                results.append((dci, upg, idx, inner))
                        continue
                    # (b) The upgrade's OWN "When defeated as an upgrade" replacement
                    #     (Luke Skywalker J25_4 pilot) — resolves from the UPGRADE
                    #     itself (the pilot), which is in its owner's discard by now.
                    if isinstance(spec, TriggerAbility) and isinstance(
                        spec.trigger, WhenDefeatedAsUpgrade
                    ):
                        if _trigger_matches(spec.trigger, event, upg, state, event_ctx):
                            if spec.condition is None or spec.condition.evaluate(state, upg):
                                results.append((upg, upg, idx, spec))

        # A When-Defeated ability an in-play SOURCE grants as an AURA to every unit
        # matching its target (Gar Saxon SHD_1: "Each friendly upgraded unit ... gains:
        # 'When Defeated: …'").  The dying unit (dci) is already out of its arena, so
        # only the aura source is still in play; match dci against the aura's target
        # from the source's perspective and, if the inner WhenDefeated fires, collect
        # it with dci as source and the SOURCE card as the spec card (so the decision
        # addresses the source's registry entry and unwrap_granted yields the inner
        # ability).  Scanning only in-play sources makes a leader-side aura deployed-
        # only for free.
        if dci is not None:
            from swu.engine.state import ability_suppressed
            # Phase-scoped aura sources (game_memory.phase_aura_sources) grant from
            # OUTSIDE play — Pyrrhic Assault TWI_103's spent event grants from the
            # discard for the rest of the phase.  find_instance reaches the discard,
            # and the recovered instance carries the real owner_id, so "friendly" in
            # the aura's target still resolves against its controller.  Empty list ⇒
            # this adds nothing and the scan below is unchanged.
            aura_sources = list(candidates)
            gm = getattr(state, "game_memory", None)
            for _aid in (getattr(gm, "phase_aura_sources", None) or ()):
                _ares = state.find_instance(_aid)
                if _ares is not None and _ares[1] not in aura_sources:
                    aura_sources.append(_ares[1])
            for src in aura_sources:
                scd = getattr(src, "card_def", None)
                if scd is None or not hasattr(scd, "set_code") or not hasattr(
                        scd, "card_number"):
                    continue
                if ability_suppressed(state, src):
                    continue
                for idx, spec in enumerate(get_abilities(scd.set_code or "", scd.card_number or "")):
                    if not isinstance(spec, AuraGrantedAbility):
                        continue
                    inner = spec.ability
                    if not isinstance(inner, TriggerAbility) or not isinstance(
                        inner.trigger, WhenDefeated
                    ):
                        continue
                    if not _spec_matches_ci(spec.target, dci, src, state, event_ctx):
                        continue
                    if _trigger_matches(inner.trigger, event, dci, state, event_ctx):
                        if inner.condition is None or inner.condition.evaluate(state, dci):
                            results.append((dci, src, idx, inner))

    # An upgrade's own "When Played" trigger: a freshly-played upgrade lives in
    # its host unit's attached_upgrades list, not directly in an arena, so
    # _cards_in_play above never yields it.  Locate it by the event's instance_id
    # and collect its play triggers — WhenPlayed and WhenPlayedViaSmuggle (e.g.
    # Hotshot DL-44 Blaster SHD_174 "When played using Smuggle: Attack with
    # attached unit"), scoped to those two kinds to avoid the upgrade spuriously
    # matching other trigger kinds.
    from swu.engine.events import UpgradePlayed
    if isinstance(event, UpgradePlayed):
        upg_result = state.find_instance(event.instance_id)
        if upg_result is not None:
            _, uci = upg_result
            if (uci not in candidates
                    and hasattr(uci.card_def, "set_code")
                    and hasattr(uci.card_def, "card_number")):
                sc = uci.card_def.set_code or ""
                cn = uci.card_def.card_number or ""
                for idx, spec in enumerate(get_abilities(sc, cn)):
                    if not isinstance(spec, TriggerAbility):
                        continue
                    if not isinstance(spec.trigger, (WhenPlayed, WhenPlayedViaSmuggle)):
                        continue
                    if _trigger_matches(spec.trigger, event, uci, state, event_ctx):
                        if spec.condition is None or spec.condition.evaluate(state, uci):
                            results.append((uci, uci, idx, spec))
    return results


# ── Target spec evaluation ────────────────────────────────────────────────────

def _unit_has_bounty(state: "GameState", ci: "CardInstance") -> bool:
    """True if ``ci`` currently has a Bounty ability (Bossk SHD_10's "a unit with a
    Bounty" target): a phase-granted bounty, its own printed ``is_bounty`` ability
    whose gating condition holds right now (Synara San SHD_33's "while exhausted"),
    or an attached bounty upgrade (Public Enemy SHD_68 etc.)."""
    if getattr(ci, "granted_bounties", None):
        return True
    cd = ci.card_def
    if hasattr(cd, "set_code") and hasattr(cd, "card_number"):
        for spec in get_abilities(cd.set_code or "", cd.card_number or ""):
            ab = unwrap_granted(spec)
            if isinstance(ab, TriggerAbility) and getattr(ab, "is_bounty", False):
                if ab.condition is None or ab.condition.evaluate(state, ci):
                    return True
    for upg in ci.attached_upgrades:
        ucd = getattr(upg, "card_def", None)
        if ucd is None or not hasattr(ucd, "set_code") or not hasattr(
                ucd, "card_number"):
            continue
        for spec in get_abilities(ucd.set_code or "", ucd.card_number or ""):
            inner = unwrap_granted(spec)
            if isinstance(inner, TriggerAbility) and getattr(inner, "is_bounty", False):
                return True
    return False


def _is_leader_unit(ci) -> bool:
    """Whether ``ci`` counts as a LEADER UNIT — the shared basis of the mutually
    exclusive ``leader_unit`` / ``non_leader`` predicates.

    True for a Leader card in an arena, and ALSO for an ordinary unit carrying a
    Leader attached as a Pilot upgrade: every leader with a deploy-as-an-upgrade
    Epic Action prints "Attached unit is a leader unit" (Boba Fett JTL_9, Asajj
    Ventress JTL_1, Luke Skywalker JTL_12).  So a Vehicle piloted by a deployed
    leader is shielded from "Defeat a non-leader unit" removal and picked up by a
    "each leader unit you control" aura, exactly as printed."""
    from swu.cards.models import Leader
    if isinstance(ci.card_def, Leader):
        return True
    upgrades = getattr(ci, "attached_upgrades", None) or ()
    if any(isinstance(u.card_def, Leader) for u in upgrades):
        return True
    # "Attached unit is a leader unit" printed on an ORDINARY upgrade (The Darksaber
    # ASH_135) — the ``LeaderUnitGrant`` marker, the second reason this predicate can
    # say yes.  Scanned only over a unit's own attachments, so it costs nothing for
    # the (vast majority of) units carrying no upgrades at all.
    if upgrades:
        for u in upgrades:
            sc = getattr(u.card_def, "set_code", None) or ""
            cn = getattr(u.card_def, "card_number", None) or ""
            if (sc, cn) in _leader_unit_grant_keys():
                return True
    return False


_LEADER_UNIT_GRANT_KEYS: "set | None" = None


def _leader_unit_grant_keys() -> set:
    """(set_code, card_number) keys of every card carrying a ``LeaderUnitGrant``
    marker (The Darksaber ASH_135 — one card today).  ``_is_leader_unit`` backs the
    mutually exclusive ``leader_unit`` / ``non_leader`` predicates and so runs inside
    target matching, hence the cached index rather than a per-upgrade spec walk."""
    global _LEADER_UNIT_GRANT_KEYS
    if _LEADER_UNIT_GRANT_KEYS is None:
        from swu.abilities.registry import get_all_registered, LeaderUnitGrant
        _LEADER_UNIT_GRANT_KEYS = {
            key for key, specs in get_all_registered().items()
            if any(isinstance(sp, LeaderUnitGrant) for sp in specs)
        }
    return _LEADER_UNIT_GRANT_KEYS


def _spec_matches_ci(
    spec: TargetSpec,
    candidate: "CardInstance",
    source_ci: "CardInstance",
    state: "GameState",
    event_ctx: dict,
) -> bool:
    """Return True if candidate satisfies spec, from source_ci's perspective."""
    from swu.engine.state import Zone

    # Board-precondition gate ("If you control a <Aspect> unit, …"): NO candidate
    # matches unless the source controller controls a unit with the named aspect
    # (the source itself counts).  Gates the whole effect via the empty-target
    # fizzle so an inactive conditional branch is skipped silently — Sabine's
    # Masterpiece JTL_250.
    if spec.require_controller_aspect is not None:
        ctrl = state.player_by_id(source_ci.owner_id)
        aspect = spec.require_controller_aspect
        if not any(
            aspect in {a.name for a in (getattr(u.card_def, "aspects", None) or ())}
            for arena in (ctrl.ground_arena, ctrl.space_arena) for u in arena
        ):
            return False

    # Fixed-target: when spec.fixed == SELF, only the source card itself matches
    if spec.fixed == SELF:
        return candidate.instance_id == source_ci.instance_id

    # Controller filter
    if spec.controller == "friendly":
        if candidate.owner_id != source_ci.owner_id:
            return False
    elif spec.controller == "enemy":
        if candidate.owner_id == source_ci.owner_id:
            return False

    # Kind filter
    if spec.kind == "unit":
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return False
    elif spec.kind == "base":
        from swu.cards.models import Base
        if not isinstance(candidate.card_def, Base):
            return False
    elif spec.kind == "unit_or_base":
        from swu.cards.models import Base
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA) and not isinstance(candidate.card_def, Base):
            return False
    elif spec.kind == "upgrade":
        from swu.cards.models import Upgrade, TokenUpgrade
        # "an upgrade" means a real (non-token) upgrade attached to a unit.
        if not isinstance(candidate.card_def, Upgrade) or isinstance(candidate.card_def, TokenUpgrade):
            return False
    elif spec.kind == "unit_upgrade":
        # A UNIT card currently riding as an upgrade — i.e. a Piloting unit played
        # as a Pilot upgrade, which is the only attached card that still has stats
        # to stand up with ("Detach a Pilot upgrade, move it to the ground arena as
        # a unit", Eject JTL_126).  Enumerated from the same attached_upgrades scan
        # as ``kind="upgrade"``; a printed Upgrade card and a token both fail the
        # isinstance, and so does a LEADER deployed as a Pilot (a documented
        # narrowing — a leader re-entering an arena is its own deploy path).
        from swu.cards.models import Unit as _UnitCard, Leader as _LeaderCard
        if (not isinstance(candidate.card_def, _UnitCard)
                or isinstance(candidate.card_def, _LeaderCard)):
            return False
    elif spec.kind == "leader":
        # "Friendly leaders …" (Mythosaur LOF_73) — a leader card IN PLAY, whether
        # deployed into an arena or still undeployed in base_zone (a leader in hand
        # or deck is not in play and grants nothing).  ``_is_leader_unit`` also
        # accepts a unit carrying a leader as a Pilot ("attached unit is a leader
        # unit"), matching the ``leader_unit`` predicate's reading.
        if candidate.zone not in (Zone.BASE_ZONE, Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return False
        if not _is_leader_unit(candidate):
            return False
    elif spec.kind == "unit_or_unit_upgrade":
        # "a friendly Pilot unit **or upgrade**" (Corvus JTL_38) — the union of
        # ``unit`` (a card standing in an arena) and ``unit_upgrade`` (a Piloting
        # unit card currently riding another unit as a Pilot).  One choice over
        # both pools, which no single existing kind expresses; a printed Upgrade
        # card and a token both fail the isinstance, as does a LEADER riding as a
        # Pilot (the ``unit_upgrade`` narrowing — a leader is its own deploy path).
        from swu.cards.models import Unit as _UnitCard, Leader as _LeaderCard
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            if (not isinstance(candidate.card_def, _UnitCard)
                    or isinstance(candidate.card_def, _LeaderCard)):
                return False

    # Arena filter
    if spec.arena == "ground" and candidate.zone != Zone.GROUND_ARENA:
        return False
    if spec.arena == "space" and candidate.zone != Zone.SPACE_ARENA:
        return False

    # Trait filter — effective traits (printed + granted, e.g. Foundling SHD_69,
    # Malakili LAW_212).  Uses per-trait ``has_trait`` (not ``get_traits``) so the
    # hot path short-circuits in O(1) for the common never-granted trait.
    if spec.traits:
        from swu.engine.traits import has_trait
        for t in spec.traits:
            if not has_trait(state, candidate, t):
                return False

    # "a friendly Vehicle OR Droid unit" (Peli Motto LOF_258) — the ANY-of sibling
    # of the ALL-of ``traits`` filter above, on the same effective-trait reading.
    if getattr(spec, "traits_any", ()):
        from swu.engine.traits import has_trait
        if not any(has_trait(state, candidate, t) for t in spec.traits_any):
            return False

    # Disjunctive trait filter — "a <Trait> unit OR a unit with a <Trait> upgrade
    # on it" (Admiral Holdo JTL_7).  The unit's own effective traits first (so a
    # granted trait counts), then the PRINTED traits of every attached upgrade — a
    # Pilot riding a Vehicle, a Resistance upgrade, a Leader deployed as an
    # upgrade.  Tokens carry their own traits (Shield = Armor) and simply never
    # match a real card's trait.
    if getattr(spec, "trait_or_upgrade_trait", None):
        from swu.engine.traits import has_trait
        # Own name, not the `want` reused by the arena predicates below: this one
        # is a trait string and must be non-None for has_trait().
        want_trait = spec.trait_or_upgrade_trait or ""
        if not has_trait(state, candidate, want_trait):
            if not any(
                want_trait in (getattr(up.card_def, "traits", None) or ())
                for up in (candidate.attached_upgrades or ())
            ):
                return False

    # Name filter — "a unit named X" (name-anthem auras, e.g. 4-LOM SHD_188:
    # "Each friendly unit named Zuckuss …").  Matches the printed title only
    # (``name``, not ``display_name`` — subtitle is ignored, per the CR "named").
    if spec.names:
        if getattr(candidate.card_def, "name", None) not in spec.names:
            return False

    # Predicate filter
    for pred in spec.predicates:
        if pred == "damaged" and candidate.damage == 0:
            return False
        if pred == "undamaged" and candidate.damage > 0:
            return False
        if pred == "exhausted" and not candidate.exhausted:
            return False
        if pred == "ready" and candidate.exhausted:
            return False
        if pred == "non_leader":
            if _is_leader_unit(candidate):
                return False
        if pred == "not_self" and candidate.instance_id == source_ci.instance_id:
            return False
        if pred == "non_unique":
            # "a non-unique unit" (Fett's Firespray SOR_184 Action).
            if getattr(candidate.card_def, "is_unique", False):
                return False
        if pred == "unique":
            # "a unique unit" — the <uq> symbol (Always Two LOF_42).
            if not getattr(candidate.card_def, "is_unique", False):
                return False
        if pred == "highest_cost_among_enemy_units":
            # "a unit with the highest cost among enemy units" (Dengar LAW_53),
            # measured against the SOURCE's opponent by PRINTED cost (the card's
            # own rules note: "abilities that refer to a card's cost always refer
            # to its printed cost").  Ties all qualify, as the note also says.
            #
            # This is read from a ``WhenUnitDefeated`` filter, i.e. after the dying
            # unit has already left its arena — so the remaining enemy units are
            # exactly the OTHER ones, and "cost ≥ the highest of those" is the
            # exact test (a still-standing unit compares against itself and is
            # trivially ≥ its own cost).
            opp_id = None
            for p in state.players:
                if p.player_id != source_ci.owner_id:
                    opp_id = p.player_id
                    break
            if opp_id is None or candidate.owner_id != opp_id:
                return False
            opp = state.player_by_id(opp_id)
            best = 0
            for u in opp.ground_arena + opp.space_arena:
                best = max(best, int(getattr(u.card_def, "cost", None) or 0))
            if int(getattr(candidate.card_def, "cost", None) or 0) < best:
                return False
        if pred == "enemy_of_source_controller":
            # "Enemy units gain …" measured against whoever CONTROLS the source
            # right now, not its owner (Galen Erso LAW_233, whose own When Played
            # hands him to an opponent — which is exactly when the two differ).
            # The ordinary ``controller="enemy"`` filter compares ``owner_id``,
            # since control is implicit arena occupancy and the owner never
            # changes; this predicate resolves both cards through
            # ``find_instance`` and compares the HOLDERS instead.
            src = state.find_instance(source_ci.instance_id)
            cand = state.find_instance(candidate.instance_id)
            if src is None or cand is None:
                return False
            if cand[0].player_id == src[0].player_id:
                return False
        if pred == "non_vehicle":
            if "Vehicle" in (getattr(candidate.card_def, "traits", None) or ()):
                return False
        if pred == "no_pilot":
            # "a … unit … without a Pilot on it" (Commandeer JTL_235).  A Pilot is
            # an attached upgrade carrying the Pilot trait (a Pilot upgrade or a
            # leader deployed as an upgrade), mirroring actions._pilot_count.
            if any("Pilot" in (getattr(upg.card_def, "traits", ()) or ())
                   for upg in candidate.attached_upgrades):
                return False
        if pred == "has_when_defeated_ability":
            # "another friendly unit [with] a 'When Defeated' ability" (Chimaera
            # JTL_39).  Per JTL_39's own printed rules note, a "When Defeated"
            # ability is any ability whose trigger reads "When Defeated" — so a
            # Bounty (its own keyword, collected by the OPPONENT) and
            # ``WhenDefeatedAsUpgrade`` (a defeat *replacement*) do not count,
            # exactly as at the ability-redo chokepoint.
            if not _when_defeated_ability_indices(state, candidate):
                return False
        if pred == "has_when_played_ability":
            # "Use any number of 'When Played' abilities on friendly Spectre
            # units" (Fire Across the Galaxy LAW_256) — only a unit that actually
            # has one is offered, so the "any number" never includes a dud pick.
            if not _when_played_ability_indices(state, candidate):
                return False
        if pred.startswith("has_keyword_"):
            # "a unit WITH <keyword>" — the per-candidate keyword filter, read
            # through the keyword layer so granted keywords count ("Each friendly
            # ground unit with Sentinel gets +0/+2" — Kylo Ren's Command Shuttle
            # SEC_32).  The keyword name rides in the predicate string, lowercased
            # with spaces as underscores (e.g. "has_keyword_sentinel").
            from swu.engine.keywords import has_keyword, Keyword
            want = pred[len("has_keyword_"):]
            kw = next((k for k in Keyword
                       if k.value.lower().replace(" ", "_") == want), None)
            if kw is None or not has_keyword(state, candidate, kw):
                return False
        if pred == "token_unit":
            # "a token unit" (Shaak Ti TWI_94 "Each friendly token unit gets +1/+0").
            from swu.cards.models import TokenUnit
            if not isinstance(candidate.card_def, TokenUnit):
                return False
        if pred == "non_token":
            # "a non-token unit" — the exact negation of ``token_unit``
            # (Bo-Katan's Gauntlet ASH_63: "Each other friendly NON-TOKEN unit
            # gains: 'When Defeated: Create a Mandalorian token'", whose whole
            # point is that the tokens it mints do not mint more themselves).
            from swu.cards.models import TokenUnit
            if isinstance(candidate.card_def, TokenUnit):
                return False
        if pred == "upgraded":
            # "an upgraded unit" — a unit with ≥1 attached upgrade (Gar Saxon SHD_1:
            # "Each friendly upgraded unit gets +1/+0").  In SWU a token upgrade
            # (Shield/Experience) counts as an upgrade, so any non-empty
            # ``attached_upgrades`` qualifies.
            if not candidate.attached_upgrades:
                return False
        if pred == "has_non_token_upgrade":
            # "defeat any number of UPGRADES on a unit" (Kit Fisto's Aethersprite
            # LOF_147) — the choosable unit must carry ≥1 upgrade the effect can
            # actually reach.  Narrower than ``upgraded``: the engine-wide
            # ``kind="upgrade"`` convention excludes Shield/Experience token
            # upgrades, so a unit holding only a Shield is not a legal choice here.
            from swu.cards.models import Upgrade as _Upg, TokenUpgrade as _TokUpg
            if not any(isinstance(u.card_def, _Upg)
                       and not isinstance(u.card_def, _TokUpg)
                       for u in (candidate.attached_upgrades or ())):
                return False
        if pred == "not_upgraded":
            # The complement of ``upgraded`` — no attached upgrades at all, tokens
            # included (a Shield or Experience token IS an upgrade, so a unit holding
            # one is upgraded).  "Defeat each unit that isn't upgraded" (Nebula
            # Ignition JTL_80).
            if getattr(candidate, "attached_upgrades", None):
                return False
        if pred == "opponent_no_space_units":
            # BOARD gate on the follow-up half of a two-target effect: the source
            # controller's opponent must control no space units at all — "If you do
            # and an opponent controls no space units, you may give an Experience
            # token to a unit" (You're All Clear, Kid JTL_55).  Failing the gate
            # yields NO candidates, so the follow-up fizzles without prompting (the
            # ``fewer_units_than_prior_target_controller`` shape).  Evaluated AFTER
            # the defeat, which is what makes the card's own kill able to satisfy it.
            opp = state.players[1 - state.player_index(source_ci.owner_id)]
            if opp.space_arena:
                return False
        if pred == "controller_more_space_units_than_target_controller":
            # BOARD gate: the source's controller must control strictly more space
            # units than the CANDIDATE's controller — "If you control more space units
            # than an opponent, deal 4 damage to a ground unit that opponent controls"
            # (Air Superiority JTL_125).  Reading it per-candidate is what ties "that
            # opponent" to the same player in both halves of the sentence; failing it
            # leaves no candidates, so the event fizzles without prompting.
            held = state.find_instance(candidate.instance_id)
            if held is None:
                return False
            held_by = held[0]       # the HOLDING player = the true controller
            mine = state.players[state.player_index(source_ci.owner_id)]
            if len(mine.space_arena) <= len(held_by.space_arena):
                return False
        if pred == "defeated_upgraded":
            # "an upgraded unit is defeated" (Punishing One SHD_137).  By the time
            # UnitDefeated fires, _defeat_unit has already cleared the unit's
            # attached_upgrades, so the plain ``upgraded`` predicate would read
            # empty — the snapshot taken before detaching lives in
            # event_ctx["defeated_upgrades"]; a non-empty snapshot means the unit
            # was upgraded at the moment of defeat.
            if not (event_ctx or {}).get("defeated_upgrades"):
                return False
        if pred == "has_sentinel":
            # "a unit with Sentinel" (Refugee of The Path LOF_242).  Reads the
            # effective keyword via the keyword query layer, so a conditionally /
            # granted Sentinel counts too.
            from swu.engine.keywords import has_keyword, Keyword
            if not has_keyword(state, candidate, Keyword.SENTINEL):
                return False
        if pred == "has_hidden":
            # "a friendly unit with Hidden" (In the Shadows LOF_241) — the
            # ``has_sentinel`` sibling, read through the effective keyword layer.
            from swu.engine.keywords import has_keyword, Keyword
            if not has_keyword(state, candidate, Keyword.HIDDEN):
                return False
        if pred == "has_bounty":
            # "a unit with a Bounty" (Bossk SHD_10): the unit currently has a Bounty
            # ability (a bounty upgrade, a phase-granted bounty, or an own printed
            # is_bounty ability whose while-condition holds now).
            if not _unit_has_bounty(state, candidate):
                return False
        if pred == "has_any_keyword":
            # "a unit that has 1 or more keywords" (Boba Fett SHD_8 deployed aura) —
            # effective keywords from any source (keywords.has_any_keyword).
            from swu.engine.keywords import has_any_keyword
            if not has_any_keyword(state, candidate):
                return False
        if pred.startswith("n_plus_keywords_"):
            # "units with N or more DIFFERENT keywords" (Gallius Rax ASH_100).  The
            # LIGHTWEIGHT count (keywords.distinct_keyword_count), for exactly the
            # reason ``has_any_keyword`` is lightweight: this predicate is consulted
            # from inside a ConstantAbility aura target, and a full ``has_keyword``
            # sweep would call back into the constant scans that evaluate that same
            # aura.
            from swu.engine.keywords import distinct_keyword_count
            try:
                need = int(pred.rsplit("_", 1)[1])
            except ValueError:
                return False
            if distinct_keyword_count(state, candidate) < need:
                return False
        if pred == "has_shield_token":
            # "a unit with a Shield token on it" (Darth Vader LOF_37 On Attack).
            from swu.cards.models import TokenUpgrade
            if not any(isinstance(u.card_def, TokenUpgrade)
                       and u.card_def.name == "Shield"
                       for u in candidate.attached_upgrades):
                return False
        if pred == "defender_or_base":
            # "the defender or a base" (Sabine Wren SOR_142 On Attack).  Used with
            # kind="unit_or_base": a base always qualifies; a unit qualifies only
            # if it is the current attack's defender (from event_ctx).  When the
            # attack is against a base there is no defender, so only bases qualify.
            from swu.cards.models import Base
            if isinstance(candidate.card_def, Base):
                pass
            elif candidate.instance_id == event_ctx.get("defender_id"):
                pass
            else:
                return False
        if pred == "ground_or_base":
            # "a ground unit or a base" (Jedha Agitator SOR_158).  Used with
            # kind="unit_or_base" (so a base is among the candidates): a base always
            # qualifies; a unit qualifies only if it is in the ground arena.  A plain
            # arena="ground" filter can't express this because it would exclude the
            # base (which lives in base_zone).
            from swu.cards.models import Base
            if isinstance(candidate.card_def, Base):
                pass
            elif candidate.zone == Zone.GROUND_ARENA:
                pass
            else:
                return False
        if pred == "leader_unit":
            if not _is_leader_unit(candidate):
                return False
        if pred == "played_this_phase":
            played: set[str] = getattr(getattr(state, "game_memory", None),
                                       "units_played_this_phase", set())
            if candidate.instance_id not in played:
                return False
        if pred == "not_played_this_phase":
            # "a unit that didn't enter play this phase" (Hound's Tooth JTL_185).
            # The inverse of "played_this_phase"; backed by the same
            # game_memory.units_played_this_phase set (every play path adds to it,
            # cleared at the round rollover).
            played = getattr(getattr(state, "game_memory", None), "units_played_this_phase", set())
            if candidate.instance_id in played:
                return False
        if pred in ("sole_friendly_unit_in_arena",
                    "sole_friendly_non_leader_unit_in_arena"):
            # "…if it's the only unit you control in its arena" / "…the only
            # NON-LEADER unit you control in its arena" (Baylan Skoll ASH_3, whose
            # deployed side attacks from the ground arena and so must not count
            # itself).  "You" is the candidate's own controller, which for a
            # ``controller="friendly"`` target is the source's controller.
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            # Annotated at this first `holder` binding; a later predicate branch
            # in the same scope reuses the name the same way.
            holder: Optional["PlayerState"] = None
            for ps in state.players:
                if candidate in ps.ground_arena or candidate in ps.space_arena:
                    holder = ps
                    break
            if holder is None:
                return False
            arena = (holder.ground_arena if candidate.zone == Zone.GROUND_ARENA
                     else holder.space_arena)
            non_leader_only = pred.endswith("non_leader_unit_in_arena")
            if non_leader_only and _is_leader_unit(candidate):
                return False
            others = [u for u in arena if u.instance_id != candidate.instance_id
                      and not (non_leader_only and _is_leader_unit(u))]
            if others:
                return False
        if pred == "attack_ended_attacker_or_own_base":
            # "Heal 2 damage from THAT UNIT or from YOUR BASE" (Luke Skywalker
            # ASH_5, on the ``WhenFriendlyUnitAttackEnds`` fire, which always
            # carries ``attack_ended_attacker``).  A base always qualifies; the
            # ``controller="friendly"`` filter is what makes it "your" base, and
            # the attacker was friendly by the trigger's own definition.
            from swu.cards.models import Base
            if isinstance(candidate.card_def, Base):
                pass
            elif candidate.instance_id != event_ctx.get("attack_ended_attacker"):
                return False
        if pred == "healed_this_phase":
            # "each friendly unit that was healed this phase" (Barriss Offee
            # TWI_42).  Backed by game_memory.units_healed_this_phase, fed at the
            # heal chokepoints by ``actions.note_unit_healed`` and only when damage
            # was really removed.  Phase-scoped, like "played_this_phase".
            healed: set[str] = getattr(getattr(state, "game_memory", None),
                                       "units_healed_this_phase", set()) or set()
            if candidate.instance_id not in healed:
                return False
        if pred == "damaged_this_phase":
            # "Ready a unit that was damaged this phase" (Galvanized Leap ASH_188) —
            # the mirror of ``healed_this_phase`` over
            # game_memory.units_damaged_this_phase, fed at the single unit-damage
            # chokepoint.  NOT the ``damaged`` predicate, which reads current damage:
            # a unit healed since still qualifies here.
            hurt: set[str] = getattr(getattr(state, "game_memory", None),
                                     "units_damaged_this_phase", set()) or set()
            if candidate.instance_id not in hurt:
                return False
        if pred == "attacked_this_phase":
            # Units that attacked this phase (Medal Ceremony SOR_245).  Backed by
            # game_memory.units_attacked_this_round — attacks only happen in the
            # ACTION phase and the set is cleared at the round rollover, so "this
            # round" and "this phase" coincide for attacks (mirrors
            # "played_this_phase" / units_played_this_phase).
            attacked: set[str] = getattr(getattr(state, "game_memory", None),
                                         "units_attacked_this_round", set())
            if candidate.instance_id not in attacked:
                return False
        if pred == "not_attacked_this_phase":
            # "a unit that didn't attack … this phase" (It's Not Over Yet SEC_177).
            # The inverse of "attacked_this_phase", over the same
            # game_memory.units_attacked_this_round set.
            attacked = getattr(getattr(state, "game_memory", None),
                               "units_attacked_this_round", set())
            if candidate.instance_id in attacked:
                return False
        if pred == "shares_trait_with_friendly_leader":
            # "a unit that shares a Trait with a friendly leader" (C-3PO LAW_152).
            # The friendly leader is the source controller's leader (deployed in an
            # arena or undeployed in base_zone); effective traits on both sides
            # (printed + granted) are compared.  No friendly leader, or no shared
            # trait ⇒ no match.
            from swu.engine.traits import get_traits
            ctrl = state.player_by_id(source_ci.owner_id)
            leader = ctrl.leader_instance
            if leader is None:
                return False
            if not (set(get_traits(state, candidate)) & set(get_traits(state, leader))):
                return False
        if pred == "same_arena_as_event":
            # Candidate must be in the arena an earlier effect recorded in
            # ``event_ctx["same_arena"]`` ("ground"/"space") — "an enemy unit in
            # the same arena" as a previously-chosen unit (Haymaker LAW_168).  No
            # recorded arena ⇒ no match.
            want = event_ctx.get("same_arena")
            if want == "ground" and candidate.zone != Zone.GROUND_ARENA:
                return False
            if want == "space" and candidate.zone != Zone.SPACE_ARENA:
                return False
            if want is None:
                return False
        if pred == "cost_eq_a_hand_unit":
            # "You may reveal a unit from your hand.  If you do, deal 3 damage to a
            # unit with the same cost as the revealed unit" (Queen Soruna ASH_132) —
            # the candidate's printed cost must match SOME unit in the source
            # controller's hand.  Which equal-cost hand unit is revealed is then
            # determined (they are interchangeable for this card), so the whole
            # ability is ONE prompt: pick the victim, and the reveal follows.
            from swu.cards.models import Unit as _Unit
            cost = getattr(candidate.card_def, "cost", None)
            if cost is None:
                return False
            hand = state.player_by_id(source_ci.owner_id).hand
            if not any(isinstance(c.card_def, _Unit)
                       and getattr(c.card_def, "cost", None) == cost for c in hand):
                return False
        if pred == "on_friendly_host":
            # An UPGRADE candidate whose HOST is controlled by the source's
            # controller — "Defeat an upgrade on a friendly unit" (Reforge ASH_90).
            # The plain ``controller="friendly"`` filter reads the UPGRADE's owner,
            # which is a different question (an upgrade you own may sit on an enemy
            # unit, and an enemy's upgrade may sit on yours).
            holder = None
            for _ps in state.players:
                for _u in _ps.ground_arena + _ps.space_arena:
                    if any(x.instance_id == candidate.instance_id
                           for x in _u.attached_upgrades):
                        holder = _ps
                        break
                if holder is not None:
                    break
            if holder is None or holder.player_id != source_ci.owner_id:
                return False
        if pred == "same_arena_as_played_card":
            # Candidate must stand in the same arena as the card whose play fired
            # this observer (``event_ctx["played_card_id"]``, threaded at the
            # CardPlayed fire) — "When you play a unit: you may have it deal damage
            # … to a unit in the same arena" (Ravager ASH_102).  The
            # ``same_arena_as_event`` sibling for an arena that is already pinned by
            # the event rather than by an earlier target choice, so no stamp is
            # needed and the ability prompts exactly once.  Unknown / off-board
            # played card ⇒ no match.
            played_id = event_ctx.get("played_card_id")
            if not played_id:
                return False
            res = state.find_instance(played_id)
            if res is None:
                return False
            _, played_ci = res
            if played_ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            if candidate.zone != played_ci.zone:
                return False
        if pred == "same_arena_as_event_or_base":
            # "a base or another unit in the same arena" (Collateral Damage LAW_208).
            # Used with kind="unit_or_base": a base ALWAYS qualifies (it lives in
            # base_zone and so could never satisfy a bare arena test); a unit
            # qualifies only if it is in the arena an earlier effect recorded in
            # ``event_ctx["same_arena"]`` — the ``ground_or_base`` widening applied to
            # ``same_arena_as_event``.  No recorded arena ⇒ only bases qualify.
            from swu.cards.models import Base as _BaseCard
            if isinstance(candidate.card_def, _BaseCard):
                pass
            else:
                want = event_ctx.get("same_arena")
                if want == "ground" and candidate.zone != Zone.GROUND_ARENA:
                    return False
                if want == "space" and candidate.zone != Zone.SPACE_ARENA:
                    return False
                if want is None:
                    return False
        if pred == "same_arena_as_host":
            # Candidate must be in the same arena as the upgrade's attached host
            # (``event_ctx["attached_to_id"]``, threaded by the upgrade/pilot play
            # path) — "an enemy unit in this arena" for a pilot upgrade (The
            # Mandalorian JTL_210 "When played as an upgrade: Exhaust an enemy unit
            # in this arena").  No host id / host not found ⇒ no match.
            host_id = event_ctx.get("attached_to_id")
            if not host_id:
                return False
            host_res = state.find_instance(host_id)
            if host_res is None:
                return False
            if candidate.zone != host_res[1].zone:
                return False
        if pred == "not_attached_host":
            # Candidate must not be the upgrade's own attached host
            # (``event_ctx["attached_to_id"]``) — "**another** friendly unit" said by
            # an UPGRADE's When Played, where the plain ``not_self`` excludes the
            # upgrade itself rather than the unit it is riding (Fiery Alliance
            # TS26_25).  No host id ⇒ nothing is excluded, so a non-upgrade source
            # reading this predicate is simply unfiltered.
            host_id = event_ctx.get("attached_to_id")
            if host_id and candidate.instance_id == host_id:
                return False
        if pred == "same_arena_as_source":
            # Candidate must be in the same arena as the SOURCE unit — "another
            # unit in this arena" (Major Vonreg JTL_11's granted On Attack).  The
            # source-anchored sibling of ``same_arena_as_host``, for an ability
            # that resolves FROM a unit rather than from an upgrade's host.  A
            # source that is not in an arena (an undeployed leader, a base) ⇒
            # nothing matches, so such an ability fizzles with no prompt.
            if source_ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            if candidate.zone != source_ci.zone:
                return False
        if pred == "in_source_chosen_arena":
            # Candidate must stand in the arena the SOURCE's controller chose for
            # it (``game_memory.chosen_arenas``) — "Choose an arena.  For this
            # phase, each unit in that arena gains: …" (Treacherous Minefield
            # ASH_186).  One aura spec serves both arenas: with no choice
            # recorded nothing matches, so the aura is simply inert.
            chosen = state.game_memory.chosen_arenas.get(
                getattr(source_ci, "instance_id", None))
            if chosen == "ground":
                if candidate.zone != Zone.GROUND_ARENA:
                    return False
            elif chosen == "space":
                if candidate.zone != Zone.SPACE_ARENA:
                    return False
            else:
                return False
        if pred == "same_arena_as_defender_unit":
            # Candidate must be a unit in the same arena as the current combat's
            # DEFENDER, and only when that defender is a unit (not a base) — "a unit
            # in the defender's arena" that also encodes "if this unit isn't attacking
            # a base" (Hardpoint Heavy Blaster SOR_121's granted On Attack).  A base
            # defender (or no defender) ⇒ nothing matches, so the ability fizzles on a
            # base attack with no prompt.
            did = event_ctx.get("defender_id")
            dres = state.find_instance(did) if did else None
            if dres is None:
                return False
            def_ci = dres[1]
            if def_ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            if candidate.zone != def_ci.zone:
                return False
        if pred == "excludes_event_target":
            # Candidate must not be the unit a previous effect recorded under
            # ``event_ctx["excluded_target_id"]`` — "another unit" relative to an
            # earlier chosen target (Grenade Strike TWI_171, combined with
            # ``same_arena_as_event``).  No recorded id ⇒ nothing is excluded.
            if candidate.instance_id == event_ctx.get("excluded_target_id"):
                return False
        if pred == "excludes_event_targets":
            # Candidate must not be any unit a previous effect recorded in the
            # set ``event_ctx["excluded_target_ids"]`` — the multi-target "another
            # … a third …" chain (Attack Pattern Delta SOR_106, three sequential
            # buffs to distinct units).  Generalises ``excludes_event_target`` (a
            # single id) to an accumulating set; no recorded ids ⇒ nothing excluded.
            if candidate.instance_id in (event_ctx.get("excluded_target_ids") or ()):
                return False
        if pred == "fewer_units_than_prior_target_controller":
            # Board gate on the FOLLOW-UP half of a two-target effect: the source's
            # controller must control fewer units than the controller of the unit an
            # earlier effect chose (recorded under
            # ``event_ctx["prior_target_controller"]``) — "Then, if you control fewer
            # units than that unit's controller, give another unit -2/-2" (Equalize
            # TWI_55).  Failing the gate yields NO candidates, so the second half
            # fizzles without prompting, the requires_prior_target shape.  Counts
            # both arenas, the CONTROLLER_N_PLUS_UNITS basis.
            other_id = event_ctx.get("prior_target_controller")
            if not other_id:
                return False
            mine = state.players[state.player_index(source_ci.owner_id)]
            theirs = state.players[state.player_index(other_id)]
            if (len(mine.ground_arena) + len(mine.space_arena)
                    >= len(theirs.ground_arena) + len(theirs.space_arena)):
                return False
        if pred == "requires_prior_target":
            # Candidate matches only if an earlier effect actually chose a target
            # (recorded under ``event_ctx["prior_target_id"]``) — the "If you do"
            # gate for a follow-up effect that must happen only when the prior one
            # did (In Pursuit TWI_221: "Exhaust a friendly unit. If you do, exhaust
            # an enemy unit").  No recorded prior target ⇒ no candidates ⇒ the
            # follow-up fizzles without a prompt.
            if not event_ctx.get("prior_target_id"):
                return False
        if pred == "requires_prior_defeat":
            # Candidate matches only if an earlier effect's target was defeated by
            # it (recorded under ``event_ctx["prior_target_defeated"]``) — the "If
            # that unit is defeated this way, you may …" gate (Shoot Down JTL_176:
            # "Deal 3 to a space unit. If defeated, you may deal 2 to a base").
            # Reads event_ctx only, so it works for base candidates too.
            if not event_ctx.get("prior_target_defeated"):
                return False
        if pred == "cost_le_event_threshold":
            # Printed cost must be ≤ a threshold an earlier step stashed in
            # ``event_ctx["cost_le_threshold"]`` — "a unit that costs the same as
            # or less than the played unit" (Tactical Droid Commander TWI_184,
            # the played unit's cost recorded by the WhenYouPlayCard matcher).  No
            # threshold (or an unknown candidate/played cost) ⇒ no match.
            threshold = event_ctx.get("cost_le_threshold")
            if threshold is None:
                return False
            cost = getattr(candidate.card_def, "cost", None)
            if cost is None or cost > threshold:
                return False
        if pred == "cost_gt_event_threshold":
            # Printed cost must be STRICTLY GREATER than the threshold an earlier
            # step stashed in ``event_ctx["cost_gt_threshold"]`` — "a unit that costs
            # more than the discarded card" (Reckless Sacrifice ASH_163).  The
            # ``cost_le_event_threshold`` mirror; no threshold ⇒ no match, so the
            # effect fizzles unprompted when the discard did not happen.
            threshold = event_ctx.get("cost_gt_threshold")
            if threshold is None:
                return False
            cost = getattr(candidate.card_def, "cost", None)
            if cost is None or cost <= threshold:
                return False
        if pred == "cost_eq_event_threshold":
            # Printed cost must EQUAL the threshold an earlier step stashed in
            # ``event_ctx["cost_le_threshold"]`` — "an enemy unit that costs the same
            # as the played unit" (Quinlan Vos TWI_18's undeployed side; his deployed
            # side says "the same as or less than" and uses cost_le_event_threshold
            # instead).  Same threshold key, tighter comparison.
            threshold = event_ctx.get("cost_le_threshold")
            if threshold is None:
                return False
            cost = getattr(candidate.card_def, "cost", None)
            if cost is None or cost != threshold:
                return False
        if pred == "attacked_your_base_this_phase":
            # Candidate declared an attack against the SOURCE controller's base this
            # phase — recorded in ``game_memory.base_attackers_this_round`` keyed by
            # the base owner ("an enemy unit that attacked your base this phase",
            # Ephant Mon SHD_88).  ("this round" == "this phase" — base attacks
            # happen only in ACTION.)
            attackers = state.game_memory.base_attackers_this_round.get(
                source_ci.owner_id, [])
            if candidate.instance_id not in attackers:
                return False
        if pred == "eligible_host_for_event_upgrade":
            # Candidate must be a legal "Attach to …" host for the upgrade an
            # earlier effect recorded under ``event_ctx["evidence_upgrade_id"]`` —
            # "attach it to an eligible unit of your choice" for a chosen upgrade
            # (Evidence of the Crime SHD_77).  No recorded upgrade ⇒ no match.
            uid = event_ctx.get("evidence_upgrade_id")
            if not uid:
                return False
            ures = state.find_instance(uid)
            if ures is None:
                return False
            from swu.engine.actions import _eligible_upgrade_targets
            if candidate.instance_id not in {
                u.instance_id for u in _eligible_upgrade_targets(state, ures[1])
            }:
                return False
        if pred == "droid_or_general_grievous":
            # "a friendly Droid unit or General Grievous" (Soulless One TWI_179):
            # the candidate must either carry the Droid trait or be named General
            # Grievous (his deployed leader-unit form, since the leader is not a
            # Droid).  Combined with controller="friendly"/kind="unit", so only
            # arena units qualify.  LIMITATION: the undeployed leader (in base_zone)
            # is not an arena unit and so is not offered — exhausting the undeployed
            # leader form is the unexercised edge of "(leader or unit)".
            from swu.engine.traits import has_trait
            name = getattr(candidate.card_def, "name", None) or ""
            if not (has_trait(state, candidate, "Droid")
                    or "General Grievous" in name):
                return False
        if pred == "creature_or_spectre":
            # "a Creature or Spectre unit" (Ezra Bridger LOF_46): the candidate
            # must carry the Creature OR the Spectre trait (an OR a single
            # TargetSpec.traits tuple — which requires ALL — cannot express).
            # Effective traits (granted count) via the trait query layer.
            from swu.engine.traits import has_trait
            if not (has_trait(state, candidate, "Creature")
                    or has_trait(state, candidate, "Spectre")):
                return False
        if pred == "droid_or_vehicle":
            # "a Droid or Vehicle unit" (Electromagnetic Pulse JTL_230): the
            # candidate must carry the Droid OR the Vehicle trait (an OR a single
            # TargetSpec.traits tuple — which requires ALL — cannot express).
            # Effective traits (granted count) via the trait query layer.
            from swu.engine.traits import has_trait
            if not (has_trait(state, candidate, "Droid")
                    or has_trait(state, candidate, "Vehicle")):
                return False
        if pred == "controller_created_token_this_phase":
            # BOARD gate (the ``no_initiative_claimed`` shape): "If you created a
            # token this phase, exhaust an enemy unit" (The Client LAW_16).  It has
            # to be a candidate gate rather than the ability's ``condition`` because
            # the card's printed rules note says the Action may still be USED when
            # the clause is unmet — it simply exhausts nothing, which is exactly
            # what an empty candidate set gives.
            if (source_ci.owner_id
                    not in state.game_memory.tokens_created_this_phase):
                return False
        if pred == "no_initiative_claimed":
            # BOARD gate, not a property of the candidate: "If no player has taken
            # the initiative this phase, …" (Face Off JTL_178).  Failing it yields NO
            # candidates, so the effect fizzles with no prompt — the
            # ``fewer_units_than_prior_target_controller`` TWI_55 shape.
            if getattr(state, "initiative_claimed_this_round", False):
                return False
        if pred == "fighter_or_transport":
            # "a Fighter or Transport unit" (Koiogran Turn JTL_179) — the
            # ``droid_or_vehicle`` disjunction for the other common JTL trait pair.
            from swu.engine.traits import has_trait
            if not (has_trait(state, candidate, "Fighter")
                    or has_trait(state, candidate, "Transport")):
                return False
        if pred == "no_experience_token":
            # "a unit without an Experience token on it" (Obi-Wan Kenobi LOF_8) —
            # the negation of the long-standing ``has_experience_token``.
            if any(getattr(u.card_def, "name", None) == "Experience"
                   for u in (candidate.attached_upgrades or ())):
                return False
        if pred == "most_power_among_friendly":
            # "Each friendly unit with the most power among friendly units" (Savage
            # Opress TS26_5's undeployed aura) — the aspect-blind sibling of
            # ``most_power_among_friendly_villainy``, and unlike it an "EACH", so a
            # tie grants the keyword to every tied unit (the card's own rules note).
            #
            # ⚠ Read from inside a ConstantAbility aura target, so it calls
            # ``compute_power``, which re-enters the very keyword/stat scans that
            # evaluate the aura.  Today that is safe — the aura grants Overwhelm,
            # which ``compute_power`` never asks about, and the keyword filter runs
            # BEFORE the target match — but the guard makes it safe by construction
            # (the ``SOURCE_POWER_MIN`` lesson); re-entry reporting False is also the
            # right answer, since a grant cannot bootstrap its own power comparison.
            from swu.engine.actions import compute_power
            guard = (id(state), source_ci.instance_id)
            if guard in _MOST_POWER_EVALUATING:
                return False
            _MOST_POWER_EVALUATING.add(guard)
            try:
                ps = state.player_by_id(source_ci.owner_id)
                pool = list(ps.ground_arena) + list(ps.space_arena)
                if not pool:
                    return False
                if candidate.instance_id not in {u.instance_id for u in pool}:
                    return False
                best = max(compute_power(state, u) for u in pool)
                if compute_power(state, candidate) != best:
                    return False
            finally:
                _MOST_POWER_EVALUATING.discard(guard)
        if pred == "most_power_among_friendly_villainy":
            # "the unit with the most power among friendly Villainy units.  (If
            # multiple units are tied, choose one.)" (Supreme Leader Snoke LOF_6).
            # A per-candidate BOARD read (the ``fewer_units_than_prior_target_
            # controller`` TWI_55 shape): admit only the units at the maximum, so a
            # tie is still a real choice and a clear winner auto-resolves.
            from swu.engine.actions import compute_power
            ps = state.player_by_id(source_ci.owner_id)
            pool = [u for u in ps.ground_arena + ps.space_arena
                    if "Villainy" in {a.name for a in
                                      (getattr(u.card_def, "aspects", None) or ())}]
            if not pool:
                return False
            best = max(compute_power(state, u) for u in pool)
            if candidate.instance_id not in {u.instance_id for u in pool}:
                return False
            if compute_power(state, candidate) != best:
                return False
        if pred == "controller_has_force_token":
            # BOARD gate (the ``no_initiative_claimed`` shape): "Use the Force (lose
            # your Force token).  If you do, <targeted effect>" (Sorcerous Blast
            # LOF_172).  An EventAbility has no ``condition`` field and a
            # ConditionalEffect cannot carry a targeted sub-effect, so the "if you
            # do" is expressed as a gate that yields NO candidates — the event
            # fizzles unprompted when the controller has no Force token.
            if not getattr(state.player_by_id(source_ci.owner_id),
                           "has_force_token", False):
                return False
        if pred.startswith("controller_has_trait_card_in_hand:"):
            # BOARD gate: "Discard a <Trait> card from your hand.  If you do,
            # <targeted effect>" (Lightsaber Throw LOF_176).  The trait rides in the
            # predicate string after the colon, so one arm serves any trait; PRINTED
            # traits, since a card in hand is not in play for the trait-grant layer.
            want = pred.split(":", 1)[1]
            ps = state.player_by_id(source_ci.owner_id)
            if not any(want in (getattr(h.card_def, "traits", None) or ())
                       for h in ps.hand):
                return False
        if pred == "power_le_event_threshold":
            # Effective power must be ≤ a numeric threshold stashed in event_ctx by
            # an earlier effect ("a unit with power ≤ the chosen unit" — Nothing
            # Left to Fear LAW_41 records the buffed chosen unit's power under
            # ``event_ctx["power_le_threshold"]``).  No threshold set (the
            # recording effect has not run) ⇒ no match.
            from swu.engine.actions import compute_power
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            threshold = event_ctx.get("power_le_threshold")
            if threshold is None or compute_power(state, candidate) > threshold:
                return False
        if pred == "hp_remaining_lt_source_power":
            # Candidate's *remaining* HP must be strictly less than the SOURCE
            # unit's effective power — "a unit with less remaining HP than this
            # unit's power" (Pong Krell LOF_38, evaluated relative to the attacker
            # whose power may be boosted by Grit at trigger time).  Only arena
            # units have HP/power.
            from swu.engine.actions import compute_power, compute_hp
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            src_power = compute_power(state, source_ci)
            hp_left = compute_hp(state, candidate) - candidate.damage
            if hp_left >= src_power:
                return False
        if pred == "less_remaining_hp_than_host":
            # Candidate's *remaining* HP must be strictly less than the attached
            # host's remaining HP — "an enemy non-leader unit with less remaining HP
            # than it" for an upgrade's WhenPlayed capture (Moral Authority SEC_256,
            # host read from ``event_ctx["attached_to_id"]``).  Only arena units
            # have HP; no host id / host not found ⇒ no match.
            from swu.engine.actions import compute_hp
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            host_id = event_ctx.get("attached_to_id")
            if not host_id:
                return False
            host_res = state.find_instance(host_id)
            if host_res is None:
                return False
            host = host_res[1]
            host_hp_left = compute_hp(state, host) - host.damage
            cand_hp_left = compute_hp(state, candidate) - candidate.damage
            if cand_hp_left >= host_hp_left:
                return False
        if pred == "power_lt_source":
            # "a unit with less power than this unit" (Ahsoka Tano ASH_9 deployed).
            # Effective power both sides, read at prompt time.
            from swu.engine.actions import compute_power
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            if compute_power(state, candidate) >= compute_power(state, source_ci):
                return False
        if pred == "power_lt_a_friendly_unit":
            # "a unit with less power than a friendly unit" (Ahsoka Tano ASH_9
            # undeployed) — i.e. strictly below the MAXIMUM power among the source
            # controller's arena units.  "Friendly" is relative to the source, and a
            # friendly unit can itself qualify (it need only be weaker than another).
            from swu.engine.actions import compute_power
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            own = state.player_by_id(source_ci.owner_id)
            best_power = max((compute_power(state, ci)
                              for arena in (own.ground_arena, own.space_arena)
                              for ci in arena), default=None)
            if best_power is None or compute_power(state, candidate) >= best_power:
                return False
        if pred.startswith("remaining_hp_ge_"):
            # "a unit with N or more remaining HP" — the ceiling mirror of
            # ``remaining_hp_le_<N>``, threshold in the suffix (Cad Bane ASH_11).
            from swu.engine.actions import compute_hp
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            if compute_hp(state, candidate) - candidate.damage < int(pred.rsplit("_", 1)[1]):
                return False
        if pred.startswith("remaining_hp_le_"):
            # "a unit with N or less remaining HP" — the threshold is the suffix
            # (Cad Bane SEC_34 When Played uses ``remaining_hp_le_2``; Aurra Sing
            # LAW_4 uses ``_1`` for her Action and ``_5`` for her When Deployed).
            # Only arena units have HP; remaining HP = effective HP − damage marked.
            from swu.engine.actions import compute_hp
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            if compute_hp(state, candidate) - candidate.damage > int(pred.rsplit("_", 1)[1]):
                return False
        if pred == "power_and_hp_equal_source_ready_resources":
            # "a unit with power and remaining HP BOTH equal to the number of ready
            # resources you control" (One in a Million SEC_53).  Effective power and
            # remaining HP, read per candidate; "you" is the SOURCE's controller, and
            # by the time an event resolves its own cost is already paid — which is
            # what the card's rules insert requires.
            from swu.engine.actions import compute_power, compute_hp
            if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
                return False
            ps = state.player_by_id(source_ci.owner_id)
            ready = sum(1 for r in ps.resources if not r.exhausted)
            if compute_power(state, candidate) != ready:
                return False
            if compute_hp(state, candidate) - candidate.damage != ready:
                return False
        if pred == "defeated_while_attacking":
            # The defeat being observed happened to a unit that was ATTACKING
            # ("When a friendly unit is defeated while attacking" — Luthen Rael
            # SEC_13, both sides).  Stamped into the defeat's event_ctx by
            # ``actions._defeat_unit(while_attacking=True)``, which the two
            # attacker-death sites in the combat pipeline pass.  A plain read of
            # the flag: the candidate here IS the defeated unit (WhenUnitDefeated
            # matches its filter against it), so no id comparison is needed.
            if not event_ctx.get("defeated_while_attacking"):
                return False
        if pred == "has_experience_token":
            # "a unit with an Experience token on it" (Vaneé LOF_82) — mirrors
            # has_shield_token.
            from swu.cards.models import TokenUpgrade
            if not any(isinstance(u.card_def, TokenUpgrade)
                       and u.card_def.name == "Experience"
                       for u in candidate.attached_upgrades):
                return False
        if pred == "dealt_damage_to_base_this_phase":
            # "a unit that dealt damage to a base this phase" (Retaliation SEC_77).
            # Backed by game_memory.units_dealt_base_damage_this_round (combat damage
            # dealt by attacking a base; "this round" == "this phase" — attacks
            # happen only in ACTION and the set is cleared at the round rollover, the
            # units_attacked_this_round precedent).
            dealt: set[str] = getattr(getattr(state, "game_memory", None),
                                      "units_dealt_base_damage_this_round", set())
            if candidate.instance_id not in dealt:
                return False
        if pred == "sole_friendly_upgrade_on_source":
            # "While this unit has exactly 1 friendly upgrade on it, THAT upgrade
            # …" (Willrow Hood SEC_61).  The candidate must be the source's one and
            # only owner-controlled attached card — Shield/Experience tokens are
            # upgrades too, so they count toward the "exactly 1" even though
            # ``kind="upgrade"`` never offers them as the candidate.
            if source_ci is None:
                return False
            own_upgrades = [u for u in (getattr(source_ci, "attached_upgrades", None) or ())
                            if u.owner_id == source_ci.owner_id]
            if (len(own_upgrades) != 1
                    or own_upgrades[0].instance_id != candidate.instance_id):
                return False
        if pred == "granted_keyword_by_source":
            # "the unit THIS card chose" — the candidate carries a ``keyword_grant``
            # modifier whose source is this aura's source (Implicate SEC_231: "Choose
            # a unit.  For this phase, it gains Sentinel and: '…'").  An aura is a
            # board-wide scan with no memory of a choice; the keyword half of the very
            # same effect already stamps exactly one modifier onto exactly the chosen
            # unit, so reading it back pins the aura to that unit with no new state.
            # The modifier and the aura registration share the phase scope, so both
            # halves lapse together at the phase rollover.
            if source_ci is None:
                return False
            if not any(m.kind == "keyword_grant"
                       and m.source_instance_id == source_ci.instance_id
                       and m.target_instance_id == candidate.instance_id
                       for m in state.modifiers):
                return False

    # Aspect filter (card must have ALL listed aspects)
    if spec.aspects:
        card_aspect_names = {a.name for a in (getattr(candidate.card_def, "aspects", None) or ())}
        for a in spec.aspects:
            if a not in card_aspect_names:
                return False

    # Cost filters
    cost = getattr(candidate.card_def, "cost", None)
    # Conditional cost cap ("… costs 4 or less instead if you control a Command or
    # Aggression unit" — Kanan Jarrus LAW_89): raise cost_max to the boosted cap
    # when the source controller controls a unit with any of the listed aspects
    # (the source counts).
    effective_cost_max = spec.cost_max
    if spec.cost_max_boost is not None:
        boost_aspects, boosted_cap = spec.cost_max_boost
        ctrl = state.player_by_id(source_ci.owner_id)
        boost_set = set(boost_aspects)
        if any(
            boost_set & {a.name for a in (getattr(u.card_def, "aspects", None) or ())}
            for arena in (ctrl.ground_arena, ctrl.space_arena) for u in arena
        ):
            effective_cost_max = boosted_cap
    # Per-candidate conditional cost cap ("… or an EXHAUSTED non-leader unit that
    # costs 4 or less" — Razor Crest JTL_223): an exhausted candidate is measured
    # against the (higher) exhausted cap instead.  Unlike cost_max_boost this reads
    # the candidate's own state, so the two halves of the printed "X or Y" sentence
    # collapse into one spec.
    if getattr(spec, "cost_max_if_exhausted", None) is not None and candidate.exhausted:
        effective_cost_max = spec.cost_max_if_exhausted
    if effective_cost_max is not None and (cost is None or cost > effective_cost_max):
        return False
    if spec.cost_min is not None and (cost is None or cost < spec.cost_min):
        return False
    # Dynamic cost cap: printed cost <= a count computed from board state (the
    # power_max_count sibling).  Evil is Everywhere SEC_247: "a unit with cost equal
    # to or less than the number of Villainy aspect icons among friendly units" — a
    # double-Villainy unit contributes 2 icons, so duplicates count.
    if getattr(spec, "cost_max_count", None) is not None:
        if spec.cost_max_count == "controller_villainy_aspect_icons":
            ctrl = state.player_by_id(source_ci.owner_id)
            threshold = sum(
                1
                for arena in (ctrl.ground_arena, ctrl.space_arena)
                for u in arena
                for a in (getattr(u.card_def, "aspects", None) or ())
                if a.name == "Villainy"
            )
        else:
            threshold = 0
        if cost is None or cost > threshold:
            return False

    # Power filter (effective power, e.g. "a unit with 5 or more power")
    if spec.power_min is not None:
        from swu.engine.actions import compute_power
        from swu.engine.state import Zone
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return False  # only units have power
        if compute_power(state, candidate) < spec.power_min:
            return False

    # Power filter (effective power, e.g. "a unit with 4 or less power" —
    # Independent Senator TWI_206)
    if spec.power_max is not None:
        from swu.engine.actions import compute_power
        from swu.engine.state import Zone
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return False  # only units have power
        if compute_power(state, candidate) > spec.power_max:
            return False

    # Dynamic power cap: effective power must be <= a count computed from board
    # state (Slaver's Freighter SHD_189: "power ≤ the number of upgrades on enemy
    # units").  In SWU a Shield/Experience token IS an upgrade, so every attached
    # upgrade on an enemy unit counts.
    if spec.power_max_count is not None:
        from swu.engine.actions import compute_power
        from swu.engine.state import Zone
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return False  # only units have power
        if spec.power_max_count == "enemy_units_upgrade_count":
            opp = state.players[1 - state.player_index(source_ci.owner_id)]
            threshold = sum(len(u.attached_upgrades)
                            for u in (*opp.ground_arena, *opp.space_arena))
        else:
            threshold = 0
        if compute_power(state, candidate) > threshold:
            return False

    # Relative-power filter: candidate's effective power must be strictly less
    # than the *capturing* unit's effective power (Legal Authority SHD_124,
    # "an enemy non-leader unit with less power than it").  The captor is the
    # upgrade's attached host (event_ctx["attached_to_id"], available during
    # enumeration as it is persisted in the decision's event_ctx), falling back
    # to the ability's source unit for a unit that captures via its own ability.
    if spec.power_less_than_captor:
        from swu.engine.actions import compute_power
        from swu.engine.state import Zone
        if candidate.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return False  # only units have power
        captor_id = event_ctx.get("attached_to_id") or source_ci.instance_id
        captor_res = state.find_instance(captor_id)
        if captor_res is None:
            return False
        _, captor_ci = captor_res
        if compute_power(state, candidate) >= compute_power(state, captor_ci):
            return False

    # HP-remaining filter
    if spec.hp_remaining_max is not None:
        from swu.engine.actions import compute_hp
        hp_left = compute_hp(state, candidate) - candidate.damage
        if hp_left > spec.hp_remaining_max:
            return False

    return True


def _gather_legal_targets(
    state: "GameState",
    spec: TargetSpec,
    source_ci: "CardInstance",
    event_ctx: dict,
) -> list[str]:
    """Return instance_ids of all cards that legally satisfy spec."""
    if spec.fixed is not None:
        return _resolve_fixed_target_ids(state, spec, source_ci, event_ctx)

    results = []
    # Gather candidates based on kind
    candidates: list["CardInstance"] = []
    for ps in state.players:
        if spec.kind in ("unit", "unit_or_base", "unit_or_unit_upgrade"):
            candidates.extend(ps.ground_arena)
            candidates.extend(ps.space_arena)
        if spec.kind in ("base", "unit_or_base"):
            if ps.base_instance is not None:
                candidates.append(ps.base_instance)
        if spec.kind in ("upgrade", "unit_upgrade", "unit_or_unit_upgrade"):
            # Real upgrades live in their host unit's attached_upgrades list.
            for host in ps.ground_arena + ps.space_arena:
                candidates.extend(host.attached_upgrades)

    for ci in candidates:
        if _spec_matches_ci(spec, ci, source_ci, state, event_ctx):
            results.append(ci.instance_id)

    # Set-relative "extreme" selector ("the unit with the least remaining HP among
    # other units" — Darth Nihilus P26_79): applied AFTER the per-candidate filters,
    # since it depends on the whole matched set.  Ties keep every minimum, so the
    # controller chooses among them (or the choice auto-resolves when only one).
    if spec.select_extreme is not None and results:
        results = _apply_select_extreme(state, spec.select_extreme, results)
    return results


def _apply_select_extreme(
    state: "GameState", selector: str, ids: list[str]
) -> list[str]:
    """Narrow ids to the candidates at the extreme named by selector."""
    from swu.engine.actions import compute_hp
    if selector == "least_remaining_hp":
        remaining = {}
        for tid in ids:
            result = state.find_instance(tid)
            if result is None:
                continue
            _ps, ci = result
            remaining[tid] = compute_hp(state, ci) - ci.damage
        if not remaining:
            return []
        least = min(remaining.values())
        return [tid for tid in ids if remaining.get(tid) == least]
    return ids


def _resolve_fixed_target_ids(
    state: "GameState",
    spec: TargetSpec,
    source_ci: "CardInstance",
    event_ctx: dict,
) -> list[str]:
    """Resolve a fixed-reference target to zero or more instance_ids."""
    fixed = spec.fixed
    if fixed == SELF:
        result = state.find_instance(source_ci.instance_id)
        return [source_ci.instance_id] if result is not None else []
    if fixed == ATTACKER:
        aid = event_ctx.get("attacker_id")
        if aid and state.find_instance(aid):
            return [aid]
        return []
    if fixed == DEFENDER:
        did = event_ctx.get("defender_id")
        if did and state.find_instance(did):
            return [did]
        return []
    if fixed in (EACH_FRIENDLY, EACH_ENEMY, EACH_IN_PLAY):
        sub_spec = TargetSpec(
            controller=("friendly" if fixed == EACH_FRIENDLY
                        else "enemy" if fixed == EACH_ENEMY else "any"),
            kind=spec.kind,
            arena=spec.arena,
            traits=spec.traits,
            names=spec.names,
            predicates=spec.predicates,
            cost_max=spec.cost_max,
            cost_min=spec.cost_min,
            cost_max_if_exhausted=spec.cost_max_if_exhausted,
            cost_max_count=spec.cost_max_count,
            # Per-candidate "card must match" filters must survive the EACH_*
            # expansion too, else a mass effect ignores them (Lawbringer LAW_101's
            # "each enemy unit with that aspect" would hit every enemy unit).  No
            # pre-existing card combined an EACH_* target with these fields, so this
            # only tightens matching where a card actually asked for it.
            aspects=spec.aspects,
            power_min=spec.power_min,
            power_max=spec.power_max,
            power_max_count=spec.power_max_count,
            hp_remaining_max=spec.hp_remaining_max,
        )
        return _gather_legal_targets(state, sub_spec, source_ci, event_ctx)
    return []


# ── Effect execution ──────────────────────────────────────────────────────────

def _needs_choice(effect: object, state: "GameState", source_ci: "CardInstance", event_ctx: dict) -> bool:
    """Return True if this effect requires a player choice (non-fixed target)."""
    spec = _get_effect_target_spec(effect)
    if spec is None:
        return False
    if spec.fixed is not None:
        return False
    targets = _gather_legal_targets(state, spec, source_ci, event_ctx)
    if not targets:
        return False   # No valid targets — will fizzle silently
    return True


def _get_effect_target_spec(effect: object) -> Optional[TargetSpec]:
    """Return the TargetSpec of an effect, or None if it has no player-chosen target."""
    if isinstance(effect, (DealDamage, DealDamageEqualTo, Heal, DefeatUnit, GiveToken,
                           ReturnToHand, ExhaustCard, ReadyCard, ModifyStats,
                           GrantKeyword, RevokeKeyword, RevokeTrait, CaptureUnit)):
        return effect.target
    if isinstance(effect, CustomEffect):
        # A CustomEffect opts into the standard target-choice machinery by
        # carrying a TargetSpec; without one it stays a no-target inline effect.
        return effect.target
    if isinstance(effect, (DrawCards, DiscardFromHand, DefeatAllUnits,
                           CreateCreditToken, CreateForceToken, CreateTokenUnit,
                           NextPlayDiscount)):
        return None   # no single player-chosen target
    return None


def execute_effect(
    state: "GameState",
    effect: object,
    source_ci: "CardInstance",
    target_id: Optional[str],
    event_ctx: dict,
) -> "GameState":
    """Apply one effect to the game state.

    target_id is only used for effects where the player chose a target.
    For fixed/auto/EACH targets, target_id is ignored and resolved inline.
    """
    _note_ability_resolved(source_ci)
    spec = _get_effect_target_spec(effect)
    if spec is not None and spec.fixed is not None:
        # Fixed target — resolve automatically
        target_ids = _resolve_fixed_target_ids(state, spec, source_ci, event_ctx)
    elif target_id is not None:
        target_ids = [target_id]
    else:
        # No target — effects like DrawCards, DefeatAllUnits
        target_ids = []

    _note_effect_efficacy(source_ci, effect, len(target_ids))

    owner_ps = state.player_by_id(source_ci.owner_id)

    if isinstance(effect, DealDamage):
        source_name = source_ci.card_def.display_name
        for tid in target_ids:
            if _target_protected(state, tid, source_ci, "damage"):
                continue  # can't be damaged by enemy card abilities (SHD_187)
            state = _apply_deal_damage(state, tid, effect.amount, source_name,
                                       dealer_id=source_ci.owner_id,
                                       source_id=source_ci.instance_id)
        return state

    if isinstance(effect, DealDamageEqualTo):
        # Scaling magnitude: each target's damage is computed from game state at
        # resolution.  Magnitudes are read up front (a snapshot) so that dealing
        # damage to one target cannot influence another's amount.
        source_name = source_ci.card_def.display_name
        amounts = [(tid, _scaling_magnitude(state, effect.count, tid, source_ci, event_ctx))
                   for tid in target_ids]
        for tid, amount in amounts:
            if amount > 0 and not _target_protected(state, tid, source_ci, "damage"):
                state = _apply_deal_damage(state, tid, amount, source_name,
                                           dealer_id=source_ci.owner_id,
                                           source_id=source_ci.instance_id)
        return state

    if isinstance(effect, Heal):
        for tid in target_ids:
            state = _apply_heal(state, source_ci, tid, effect.amount)
        return state

    if isinstance(effect, DefeatUnit):
        for tid in target_ids:
            if _target_protected(state, tid, source_ci, "defeat"):
                continue
            state = _apply_defeat_unit(state, tid)
        return state

    if isinstance(effect, CaptureUnit):
        # The captor is the upgrade's attached host (an upgrade WhenPlayed threads
        # ``attached_to_id``); a unit capturing via its own ability would have no
        # host and capture under itself.
        from swu.engine.actions import _apply_capture
        captor_id = event_ctx.get("attached_to_id") or source_ci.instance_id
        for tid in target_ids:
            state = _apply_capture(state, captor_id, tid)
        return state

    if isinstance(effect, DefeatAllUnits):
        all_ids = _gather_legal_targets(state, effect.filter, source_ci, event_ctx)
        for tid in all_ids:
            if state.find_instance(tid) is None:
                continue
            if _target_protected(state, tid, source_ci, "defeat"):
                continue
            state = _apply_defeat_unit(state, tid)
        return state

    if isinstance(effect, GiveToken):
        for tid in target_ids:
            result = state.find_instance(tid)
            if result is not None:
                ps, ci = result
                from swu.engine.tokens import attach_token
                for _ in range(max(1, effect.count)):
                    attach_token(state, ps, ci, effect.token_type)
        return state

    if isinstance(effect, CreateCreditToken):
        from swu.engine.tokens import create_credit_token
        # "An opponent creates a Credit token" (Vel Sartha LAW_6) — the DrawCards /
        # CreateTokenUnit ``player`` convention.  Two players, so "an opponent" is
        # the one opponent and needs no choice.
        who = getattr(effect, "player", "controller")
        if who == "opponent":
            beneficiaries = [p for p in state.players
                             if p.player_id != owner_ps.player_id] or [owner_ps]
        elif who == "each":
            # "Each player creates a Credit token" (Rodian Bondsman LAW_116).
            beneficiaries = list(state.players)
        else:
            beneficiaries = [owner_ps]
        for beneficiary in beneficiaries:
            for _ in range(max(1, effect.count)):
                create_credit_token(state, beneficiary)
        return state

    if isinstance(effect, CreateForceToken):
        # "The Force is with you (create your Force token)" — a per-player boolean
        # (at most one Force token); creating one already held is a no-op.
        owner_ps.has_force_token = True
        return state

    if isinstance(effect, CreateTokenUnit):
        from swu.engine.actions import _create_token_units
        # ``player`` follows the DrawCards convention — an opponent may be made to
        # create them ("An opponent creates 2 Battle Droid tokens", Jesse TWI_145).
        who = getattr(effect, "player", "controller")
        if who == "opponent":
            makers = [p for p in state.players if p.player_id != owner_ps.player_id]
        elif who == "each":
            makers = list(state.players)
        else:
            makers = [owner_ps]
        for maker_ps in makers:
            _create_token_units(state, maker_ps, effect.token_name,
                                max(1, effect.count),
                                enters_ready=effect.enters_ready)
        return state

    if isinstance(effect, NextPlayDiscount):
        # Record a pending "next <trait> unit you play this phase costs N less"
        # discount for the source's controller (Khetanna LAW_158).  The play-cost
        # path reads/consumes it (actions._pending_play_discount / _consume_play_discount).
        # ``count`` records N entries at once ("each of the next N cards" —
        # Tranquility TWI_246); ``units_only`` restricts to Unit plays (Khetanna).
        for _ in range(max(1, effect.count)):
            state.game_memory.pending_play_discounts.append({
                "player_id": owner_ps.player_id,
                "trait": effect.trait,
                "amount": effect.amount,
                "units_only": bool(effect.units_only),
                "plot_only": bool(getattr(effect, "plot_only", False)),
                "exclude_aspects": list(getattr(effect, "exclude_aspects", ()) or ()),
                "applies_to_piloting": bool(
                    getattr(effect, "applies_to_piloting", False)),
                "shares_keyword_with_friendly": bool(
                    getattr(effect, "shares_keyword_with_friendly", False)),
                "card_type": getattr(effect, "card_type", None),
            })
        return state

    if isinstance(effect, DrawCards):
        from swu.engine.actions import _draw_cards
        if effect.player in ("controller", "each"):
            _draw_cards(state, owner_ps, effect.count)
        if effect.player in ("opponent", "each"):
            opp_ps = state.players[1 - state.player_index(source_ci.owner_id)]
            _draw_cards(state, opp_ps, effect.count)
        return state

    if isinstance(effect, DiscardFromHand):
        # Simple auto-discard: discard the first N cards from the choosing player's hand
        from swu.engine.state import Zone
        choosing_ps = owner_ps if effect.chooser == "controller" else state.players[1 - state.player_index(source_ci.owner_id)]
        discarded = 0
        for _ in range(min(effect.count, len(choosing_ps.hand))):
            if choosing_ps.hand:
                ci = choosing_ps.hand.pop(0)
                ci.zone = Zone.DISCARD
                choosing_ps.discard.append(ci)
                from swu.engine.actions import note_hand_or_deck_discard
                note_hand_or_deck_discard(state, ci)
                discarded += 1
        if discarded:
            # Record the "discard 1+ cards from your hand" observer instruction
            # (Padmé Amidala SEC_16) — once per effect, for the player who discarded.
            from swu.engine.actions import record_hand_discard
            record_hand_discard(state, choosing_ps.player_id)
        return state

    if isinstance(effect, ReturnToHand):
        for tid in target_ids:
            if _target_protected(state, tid, source_ci, "return"):
                continue
            state = _apply_return_to_hand(state, tid)
        return state

    if isinstance(effect, ExhaustCard):
        for tid in target_ids:
            if _target_protected(state, tid, source_ci, "exhaust"):
                continue  # "can't be exhausted by enemy card abilities" (LOF_40)
            result = state.find_instance(tid)
            if result is not None:
                _, ci = result
                ci.exhausted = True
        return state

    if isinstance(effect, ReadyCard):
        for tid in target_ids:
            result = state.find_instance(tid)
            if result is not None:
                _, ci = result
                # A unit that "can't ready this round" (No Good to Me Dead SOR_186)
                # cannot be readied by an effect either.
                if getattr(ci, "cannot_ready_this_round", False):
                    continue
                # Nor one under a ReadyRestriction whose condition holds
                # (Leia Organa LOF_98: can't ready while in the space arena).
                from swu.engine.actions import _ready_forbidden, note_unit_readied
                if _ready_forbidden(state, ci):
                    continue
                note_unit_readied(state, ci)
                ci.exhausted = False
        return state

    if isinstance(effect, ModifyStats):
        for tid in target_ids:
            result = state.find_instance(tid)
            if result is not None:
                _, ci = result
                mod = _make_modifier(
                    state, source_ci.instance_id, tid,
                    power=effect.power, hp=effect.hp,
                    duration=effect.duration,
                )
                state.modifiers.append(mod)
        return state

    if isinstance(effect, GrantKeyword):
        for tid in target_ids:
            result = state.find_instance(tid)
            if result is not None:
                mod = _make_kw_modifier(
                    state, source_ci.instance_id, tid,
                    keyword=effect.keyword, value=effect.value,
                    duration=effect.duration, kind="keyword_grant",
                )
                state.modifiers.append(mod)
        return state

    if isinstance(effect, RevokeTrait):
        # "Each enemy unit loses the <T> trait for this phase" (Nameless Terror
        # LOF_33) — a ``trait_revoke`` Modifier the trait query layer reads FIRST,
        # the sibling of ``keyword_revoke``.
        from swu.engine.state import Modifier
        for tid in target_ids:
            if state.find_instance(tid) is None:
                continue
            state.modifiers.append(Modifier(
                modifier_id=state.alloc_modifier_id(),
                source_instance_id=source_ci.instance_id,
                target_instance_id=tid,
                kind="trait_revoke",
                value={"trait": effect.trait},
                duration=effect.duration.value,
            ))
        return state

    if isinstance(effect, RevokeKeyword):
        for tid in target_ids:
            result = state.find_instance(tid)
            if result is not None:
                mod = _make_kw_modifier(
                    state, source_ci.instance_id, tid,
                    keyword=effect.keyword, value=0,
                    duration=effect.duration, kind="keyword_revoke",
                )
                state.modifiers.append(mod)
        return state

    if isinstance(effect, ConditionalEffect):
        branch = effect.if_true if effect.condition.evaluate(state, source_ci) else effect.if_false
        for sub in branch:
            state = execute_effect(state, sub, source_ci, None, event_ctx)
        return state

    if isinstance(effect, CustomEffect):
        # A CustomEffect fn may deal non-combat damage (directly via _apply_deal_
        # damage, or by pushing an indirect/select/distribute decision).  Mark the
        # source's controller as the dealer for any damage dealt synchronously here
        # (a pushed decision resolves later, outside this scope, and passes dealer_id
        # explicitly in its resolver) — Boba Fett JTL_9's WhenDealNonCombatDamage.
        with _noncombat_dealer(source_ci.owner_id):
            return effect.fn(state, source_ci, target_id, event_ctx)

    return state


# ── Effect helper implementations ─────────────────────────────────────────────

def _scaling_magnitude(
    state: "GameState", count: str, target_id: str,
    source_ci: "CardInstance | None" = None,
    event_ctx: "dict | None" = None,
) -> int:
    """Compute a per-target scaling magnitude for ``DealDamageEqualTo``.

    ``"target_controller_hand"`` → the number of cards in the hand of the player
    who controls the target.  ``find_instance`` returns the containing player,
    which is the controller (and, for a base, the owner).

    ``"source_controller_discard_distinct_costs"`` → the number of *distinct*
    printed costs among cards in the SOURCE controller's discard pile (Fennec
    Shand SHD_220 — "for each different cost among cards in your discard pile").
    This count depends on the source, not the target, so it ignores ``target_id``.

    ``"source_controller_units_in_target_arena"`` → the number of units the SOURCE
    controller has in the same arena (ground/space) as the target (Synchronized
    Strike TWI_99 — "equal to the number of units you control in its arena").
    Depends on both the source (whose controller is counted) and the target
    (whose arena selects which of the source controller's arena lists to count).

    Unknown count specs and missing targets yield 0 (no damage).
    """
    if count == "source_controller_discard_distinct_costs":
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        # Read through getattr once: AnyCard is a union and Leader/Base/tokens
        # have no cost at all.
        costs = {cost for cost in (getattr(ci.card_def, "cost", None)
                                   for ci in ps.discard) if cost is not None}
        return len(costs)

    if count == "source_controller_units":
        # "Deal 1 damage to it for each friendly unit" (Turning the Tide ASH_138) —
        # the arena-blind sibling of ``source_controller_units_in_target_arena``,
        # counting BOTH of the source controller's arenas and ignoring the target.
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        return len(ps.ground_arena) + len(ps.space_arena)

    if count == "source_controller_units_damage":
        # "Deal damage to a unit equal to the total amount of damage on all units
        # you control" (Reckoning ASH_187) — the DAMAGE-summing sibling of
        # ``source_controller_units``, over both of the source controller's
        # arenas and independent of the target (which may itself be one of them,
        # and correctly contributes its own damage when it is friendly).
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        return sum(int(ci.damage or 0) for ci in ps.ground_arena + ps.space_arena)

    if count == "source_controller_experience_tokens":
        # "Deal damage to a unit equal to the number of Experience tokens on friendly
        # units" (Backed by the Pykes TS26_58).  Counted off the SOURCE controller's
        # arena units' attached upgrades, so it is independent of the target — and
        # read at resolution, i.e. AFTER the card's own leading GiveToken has landed,
        # which is what makes the token it just handed out count.
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        return sum(
            1
            for u in ps.ground_arena + ps.space_arena
            for up in (u.attached_upgrades or ())
            if up.card_def.display_name == "Experience"
        )

    if count == "enemy_damaged_units":
        # "Deal damage to a unit equal to the number of damaged enemy units" (Backed
        # by Black Sun TS26_70) — enemy of the SOURCE's controller, both arenas, and
        # independent of the target (which may itself be one of them and correctly
        # counts its own freshly-dealt damage, since the card's leading 1 damage has
        # already resolved).
        if source_ci is None:
            return 0
        return sum(
            1
            for p in state.players if p.player_id != source_ci.owner_id
            for u in p.ground_arena + p.space_arena
            if int(getattr(u, "damage", 0) or 0) > 0
        )

    if count == "attached_host_power":
        # "Deal damage to an enemy unit equal to ATTACHED UNIT's power" (Craving
        # Power LOF_91, an upgrade's own When Played).  The host is the standard
        # ``event_ctx["attached_to_id"]`` threaded by the upgrade-play site; the
        # magnitude depends on the source's host, not the target.  Effective power
        # (every StatBonus / token counted), via compute_power.
        host_id = (event_ctx or {}).get("attached_to_id")
        if host_id is None:
            return 0
        res = state.find_instance(host_id)
        if res is None:
            return 0
        from swu.engine.actions import compute_power
        return max(0, compute_power(state, res[1]))

    if count == "source_controller_resources":
        # "damage equal to the number of resources you control" (Devastator SOR_90).
        # Independent of target; counts every resource in the source controller's
        # resource row (available + spent).
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        return len(ps.resources)

    if count == "source_controller_space_units":
        # "damage equal to the number of friendly space units" (Resistance Blue
        # Squadron JTL_102).  Independent of target; the source itself counts when it
        # is in the space arena, exactly as printed ("units you control", not
        # "other").
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        return len(ps.space_arena)

    if count == "source_controller_hand":
        # "damage equal to the number of cards in your hand" (Rebellious Hammerhead
        # JTL_153) — the SOURCE controller's hand, the mirror of the existing
        # target-side ``target_controller_hand``.  Independent of target.
        if source_ci is None:
            return 0
        return len(state.player_by_id(source_ci.owner_id).hand)

    if count == "source_controller_units_x2":
        # "Twice the number of units you control" (Yoda LOF_101) — total units in
        # both of the source controller's arenas, doubled.  Independent of target.
        if source_ci is None:
            return 0
        ps = state.player_by_id(source_ci.owner_id)
        return 2 * (len(ps.ground_arena) + len(ps.space_arena))

    if count == "source_damage":
        # "for each damage on this unit" (Krrsantan SHD_139 On Attack).  Independent
        # of target; reads the damage currently marked on the source unit.
        if source_ci is None:
            return 0
        return int(getattr(source_ci, "damage", 0) or 0)

    if count == "source_power":
        # "damage equal to his power" (Crosshair SHD_87 Action).  Independent of
        # target; reads the source unit's *effective* power (modifiers included).
        if source_ci is None:
            return 0
        from swu.engine.actions import compute_power
        return max(0, compute_power(state, source_ci))

    if count == "event_healed_amount":
        # "When 1 or more damage is healed from this unit: You may deal THAT MUCH
        # damage to a unit" (Baze Malbus LAW_47).  The amount rides in the heal
        # observer's event_ctx, stamped by ``actions._fire_heal_observers`` from the
        # ledger entry ``note_unit_healed`` wrote; target-independent.
        return max(0, int((event_ctx or {}).get("healed_amount", 0) or 0))

    if count == "controller_cards_drawn_this_phase":
        # "equal to the number of cards you've drawn this phase" (Pre Vizsla TWI_10's
        # undeployed Action).  Reads the per-phase draw tally
        # (game_memory.cards_drawn_this_phase, ACTION-phase draws only — the card's
        # "this doesn't include cards drawn in the regroup phase"); target-independent.
        if source_ci is None:
            return 0
        gm = getattr(state, "game_memory", None)
        tally = getattr(gm, "cards_drawn_this_phase", None) or {}
        return int(tally.get(source_ci.owner_id, 0))

    if count.startswith("source_controller_units_with_trait:"):
        # "1 damage to it for each friendly <Trait> unit" (Low Altitude Gunship
        # TWI_149 — Republic).  The trait rides in the count string after the colon
        # so one arm serves every trait; counts both of the source controller's
        # arenas, including the source itself when it carries the trait.
        if source_ci is None:
            return 0
        trait = count.split(":", 1)[1]
        from swu.engine.traits import has_trait
        ps = state.player_by_id(source_ci.owner_id)
        return sum(1 for u in (ps.ground_arena + ps.space_arena)
                   if has_trait(state, u, trait))

    if count == "event_combat_damage":
        # "that much damage" — the amount of combat damage just dealt to the unit
        # that triggered this ability (Tarfful SHD_250).  Recorded into event_ctx at
        # the unit-combat damage firing site alongside ``dealt_combat_damage_to``;
        # independent of target.
        if not event_ctx:
            return 0
        return int(event_ctx.get("combat_damage_amount") or 0)

    if count == "event_played_card_cost":
        # "damage equal to that card's cost" (Krayt Dragon SHD_172 — the opponent's
        # just-played card).  Recorded into event_ctx by the WhenOpponentPlaysCard
        # matcher; independent of target.
        if not event_ctx:
            return 0
        return int(event_ctx.get("event_played_card_cost") or 0)

    result = state.find_instance(target_id)
    if result is None:
        return 0
    ps, _ci = result
    if count == "target_controller_hand":
        return len(ps.hand)
    if count in ("source_controller_units_in_target_arena",
                 "source_controller_units_in_target_arena_x2"):
        if source_ci is None:
            return 0
        from swu.engine.state import Zone
        src_ps = state.player_by_id(source_ci.owner_id)
        mult = 2 if count.endswith("_x2") else 1
        # Ferrix Uprising SEC_130 uses the doubled variant ("twice the number of
        # units you control in its arena"); Synchronized Strike TWI_99 the plain one.
        if _ci.zone == Zone.SPACE_ARENA:
            return mult * len(src_ps.space_arena)
        if _ci.zone == Zone.GROUND_ARENA:
            return mult * len(src_ps.ground_arena)
        return 0
    if count == "target_remaining_hp_minus_1":
        # "Deal damage equal to 1 less than its remaining HP" — max 0 so we
        # never deal negative damage (No Disintegrations JTL_144).
        from swu.engine.actions import compute_hp
        remaining = compute_hp(state, _ci) - _ci.damage
        return max(0, remaining - 1)
    return 0


def _damage_prevented(
    state: "GameState", source_id: str | None, target_ps, target_ci
) -> bool:
    """True if a ``PreventDamage`` marker blocks this ability damage (Malakili
    LOF_108).  Prevent when the damage SOURCE is a unit its controller controls
    matching a ``PreventDamage`` marker's ``source_traits`` AND the TARGET is a unit
    the SAME player controls (friendly-fire) — the marker is held by that player.

    ``source_id`` None (an unthreaded caller — the damage-decision resolvers in
    actions.py never pass it) → not prevented (conservative; no shipped Creature
    routes friendly-fire through those paths)."""
    if not source_id:
        return False
    sres = state.find_instance(source_id)
    if sres is None:
        return False
    sps, _sci = sres
    if sps.player_id != target_ps.player_id:
        return False  # source and target are not the same player's units → no friendly-fire
    from swu.abilities.registry import get_abilities, PreventDamage
    from swu.engine.traits import get_traits
    src_traits = get_traits(state, _sci)
    for marker_ci in sps.ground_arena + sps.space_arena:
        msc = getattr(marker_ci.card_def, "set_code", None) or ""
        mcn = getattr(marker_ci.card_def, "card_number", None) or ""
        for spec in get_abilities(msc, mcn):
            if isinstance(spec, PreventDamage) and all(
                t in src_traits for t in spec.source_traits
            ):
                return True
    return False


def _apply_deal_damage(
    state: "GameState", target_id: str, amount: int, source_name: str | None = None,
    dealer_id: str | None = None, source_id: str | None = None,
    _skip_prevention: bool = False,
) -> "GameState":
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, ci = result
    from swu.cards.models import Base
    # Malakili LOF_108 friendly-fire prevention — a friendly Creature's ability
    # damage to another friendly UNIT is dropped entirely (no record, no event, no
    # defeat).  Checked BEFORE _record_noncombat_damage so a prevented hit does not
    # fire WhenDealNonCombatDamage.  Bases are never guarded (Malakili says "unit").
    if not isinstance(ci.card_def, Base) and _damage_prevented(state, source_id, ps, ci):
        return state
    # Queen Amidala SEC_101 — interactive ABILITY-damage prevention (the DAMAGE half's
    # ability sink; combat is handled at _deal_damage_with_shield's one-shot flag).  If
    # the target carries the InteractiveDamagePrevention marker and can prevent, DEFER
    # this damage: push an ``ability_damage_prevention`` decision and return WITHOUT
    # dealing.  On resolve the decision either drops the damage (a friendly trait-
    # sharing unit was sacrificed) or re-applies it here with ``_skip_prevention=True``.
    # (Indirect damage needs no equivalent: its receiving player assigns the sink, so
    # they never place it on a unit they could instead protect.)
    if not _skip_prevention and amount > 0 and not isinstance(ci.card_def, Base):
        from swu.engine.actions import _try_defer_ability_damage_prevention
        if _try_defer_ability_damage_prevention(
                state, ci, ps, amount, source_name, dealer_id, source_id):
            return state
    if amount > 0:
        _record_noncombat_damage(state, dealer_id)
    from swu.engine.events import DamageDealt
    if isinstance(ci.card_def, Base):
        # A one-shot "prevent the next damage to this base this phase" (Close the
        # Shield Gate JTL_74) eats the whole instance.
        from swu.engine.actions import base_damage_after_prevention
        amount = base_damage_after_prevention(state, ci, amount)
        ci.damage += amount
        state.event_log.append(DamageDealt(
            target_instance_id=ci.instance_id,
            target_name=ci.card_def.display_name,
            owner_id=ps.player_id,
            amount=amount,
            is_base=True,
            source_name=source_name,
        ))
        from swu.engine.actions import _check_game_over, record_base_damage
        record_base_damage(state, ps.player_id, amount)
        _check_game_over(state)
    else:
        from swu.engine.state import Zone
        # A unit that has already left play (e.g. defeated by an earlier chunk of
        # the same multi-target damage plan — Count Dooku TWI_138's per-exploit
        # damage can assign two chunks to one unit) cannot take further damage.
        # Without this guard the second hit would re-run _defeat_unit on a card
        # already in discard, appending a duplicate instance to the pile.
        if ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            return state
        from swu.engine.actions import _deal_damage_with_shield
        _deal_damage_with_shield(state, ps, ci, amount, source_name=source_name,
                                 dealer_id=dealer_id, dealer_source_id=source_id)
        # Check if unit is now defeated (unless protected from no-remaining-HP
        # defeat this phase — The Tragedy of Plagueis LOF_43).
        from swu.engine.actions import _hp_lethal
        if _hp_lethal(state, ci):
            from swu.engine.actions import _defeat_unit
            _defeat_unit(state, ps, ci)
    return state


def _apply_indirect_damage(
    state: "GameState", target_id: str, amount: int, source_name: str | None = None,
    dealer_id: str | None = None,
) -> "GameState":
    """Deal ``amount`` indirect (unpreventable) damage to a base or unit target.

    Indirect damage bypasses shields — it is applied directly to the target's
    ``damage`` counter without routing through ``_deal_damage_with_shield``.  A
    defeated unit is cleaned up via ``_defeat_unit`` as normal.  If the target
    was a unit, the caller should set ``event_ctx["indirect_damage_unit_id"]``
    before firing ``WhenIndirectDamageDealtToUnit`` triggers (done by
    ``_resolve_assign_indirect_damage`` in actions.py).
    """
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, ci = result
    if amount > 0:
        _record_noncombat_damage(state, dealer_id)
    from swu.cards.models import Base
    from swu.engine.events import DamageDealt
    is_base = isinstance(ci.card_def, Base)
    if is_base:
        from swu.engine.actions import base_damage_after_prevention
        amount = base_damage_after_prevention(state, ci, amount)
    ci.damage += amount
    state.event_log.append(DamageDealt(
        target_instance_id=ci.instance_id,
        target_name=ci.card_def.display_name,
        owner_id=ps.player_id,
        amount=amount,
        is_base=is_base,
        source_name=source_name,
    ))
    if is_base:
        from swu.engine.actions import _check_game_over
        _check_game_over(state)
    else:
        from swu.engine.state import Zone
        from swu.engine.actions import _hp_lethal, _defeat_unit
        if ci.zone in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
            if _hp_lethal(state, ci):
                _defeat_unit(state, ps, ci)
    return state


def _apply_heal(state: "GameState", source_ci: "CardInstance", target_id: str, amount: int) -> "GameState":
    result = state.find_instance(target_id)
    if result is None:
        return state
    _, ci = result
    # "Bases can't be healed for this phase" (Wolffe SOR_160) — a base target
    # absorbs no healing while the lock is in force.
    from swu.cards.models import Base
    from swu.engine.actions import _bases_cannot_heal
    if isinstance(ci.card_def, Base) and _bases_cannot_heal(state):
        return state
    before = int(ci.damage)
    ci.damage = max(0, ci.damage - amount)
    from swu.engine.actions import note_unit_healed
    note_unit_healed(state, ci, before - ci.damage)
    return state


def _card_grants_self_protection(card_def, kind: str, state=None, host_ci=None,
                                 is_attached=None) -> bool:
    """True if ``card_def`` carries a self-targeted ``Protection`` ConstantAbility
    covering ``kind`` ("defeat" | "return" | "exhaust").  Read for the card as a
    unit and, when it is an upgrade, for the host it protects (Chewbacca JTL_103's
    "Attached unit gains …").  When the ConstantAbility carries a ``condition`` it
    is evaluated against ``host_ci`` (the protected unit) — Kylo Ren's Lightsaber
    LOF_40 protects only "if attached unit is a Force unit".

    ``is_attached`` distinguishes the readings an ``upgrade_only`` Protection cares
    about: ``None`` means "we are asking on behalf of the HOST" (the attached-upgrade
    branch), and a CALLABLE means "we are asking about the card itself", returning
    whether it is currently attached to a host.  An ``upgrade_only`` Protection
    answers only the card-itself-while-attached case — "THIS UPGRADE can't be
    defeated" (Luke Skywalker JTL_12) protects neither Luke-as-a-deployed-unit nor
    the Vehicle he is riding.  The callable is only invoked once such a Protection is
    actually found, keeping the board walk off the hot damage/defeat path."""
    sc = getattr(card_def, "set_code", None) or ""
    cn = getattr(card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    for spec in get_abilities(sc, cn):
        if not isinstance(spec, ConstantAbility) or spec.target.fixed != SELF:
            continue
        if spec.condition is not None and state is not None and host_ci is not None:
            if not spec.condition.evaluate(state, host_ci):
                continue
        for eff in spec.effects:
            if isinstance(eff, Protection):
                if getattr(eff, "upgrade_only", False):
                    if is_attached is None or not is_attached():
                        continue
                if kind == "defeat" and eff.from_defeat:
                    return True
                if kind == "return" and eff.from_return:
                    return True
                if kind == "exhaust" and getattr(eff, "from_exhaust", False):
                    return True
                if kind == "hp_defeat" and getattr(eff, "from_hp_defeat", False):
                    return True
                if (kind == "hp_defeat_any_phase"
                        and getattr(eff, "from_hp_defeat", False)
                        and getattr(eff, "hp_defeat_any_phase", False)):
                    return True
                if kind == "capture" and getattr(eff, "from_capture", False):
                    return True
                if kind == "damage" and getattr(eff, "from_damage", False):
                    return True
    return False


# Cache: does a card type carry an arena-wide (non-SELF) ConstantAbility Protection?
# Almost no card does, so the protection read skips the full spec scan for the rest
# with a single dict lookup (the ``traits._arena_granter_cache`` pattern).  Card defs
# are immutable, so this is safe across states and games.
_aura_protector_cache: dict = {}


def _is_aura_protector(sc: str, cn: str) -> bool:
    key = (sc, cn)
    cached = _aura_protector_cache.get(key)
    if cached is None:
        cached = any(
            isinstance(spec, ConstantAbility)
            and spec.target.fixed != SELF
            and any(isinstance(e, Protection) for e in spec.effects)
            for spec in get_abilities(sc, cn))
        _aura_protector_cache[key] = cached
    return cached


def _aura_protection(state, ci, kind: str) -> bool:
    """True if some OTHER in-play unit protects ``ci`` from ``kind`` via an
    arena-wide (non-SELF) ``ConstantAbility`` carrying a ``Protection``.

    The third protection source, beside the card's own self-targeted Protection and
    one on an attached upgrade (both ``_card_grants_self_protection``'s job):
    Mythosaur LOF_73, "Friendly upgraded units can't be exhausted or returned to
    hand by enemy card abilities".  Gated by ``_is_aura_protector`` so the board
    walk only ever runs for the handful of cards that grant such an aura."""
    from swu.engine.state import ability_suppressed
    for ps in state.players:
        for source in (*ps.ground_arena, *ps.space_arena):
            if source.instance_id == ci.instance_id:
                continue
            if ability_suppressed(state, source):
                continue
            cd = source.card_def
            sc = getattr(cd, "set_code", None) or ""
            cn = getattr(cd, "card_number", None) or ""
            if not sc or not cn or not _is_aura_protector(sc, cn):
                continue
            for spec in get_abilities(sc, cn):
                if not isinstance(spec, ConstantAbility) or spec.target.fixed == SELF:
                    continue
                if not any(_protection_covers(e, kind) for e in spec.effects
                           if isinstance(e, Protection)):
                    continue
                if spec.condition is not None and not spec.condition.evaluate(state, source):
                    continue
                if _spec_matches_ci(spec.target, ci, source, state, {}):
                    return True
    return False


def _protection_covers(eff, kind: str) -> bool:
    """Whether a ``Protection`` effect covers ``kind`` ("defeat" | "return" |
    "exhaust" | "hp_defeat" | "capture" | "damage")."""
    return bool(getattr(eff, f"from_{kind}", False))


def _target_protected(state, target_id: str, source_ci, kind: str) -> bool:
    """True if ``target_id`` can't be defeated/returned (``kind``) by this *enemy*
    card ability (Chewbacca JTL_103).  Only enemy abilities are blocked — a source
    controlled by the target's own controller is unaffected — and the protection
    also flows from a protective Pilot upgrade (Chewbacca-as-upgrade) attached to
    the target ("Attached unit gains …")."""
    result = state.find_instance(target_id)
    if result is None:
        return False
    ps, ci = result
    if source_ci is not None and source_ci.owner_id == ps.player_id:
        return False  # friendly ability — not an "enemy card ability"
    # Is the target itself currently attached to a host?  Distinguishes an
    # ``upgrade_only`` protection's one valid reading (Luke JTL_12) from the card
    # sitting in an arena as a unit; ordinary protections ignore the distinction.
    # ⚡ Passed as a LAZY callable because this predicate sits on the hot damage /
    # defeat path: the board walk only runs for the handful of cards that actually
    # carry an ``upgrade_only`` Protection, never for the overwhelming majority that
    # carry none at all.
    def _attached() -> bool:
        return any(
            any(u.instance_id == target_id for u in host.attached_upgrades)
            for hps in state.players
            for host in hps.ground_arena + hps.space_arena)

    if _card_grants_self_protection(ci.card_def, kind, state, ci,
                                    is_attached=_attached):
        return True
    for upg in getattr(ci, "attached_upgrades", None) or ():
        if _card_grants_self_protection(upg.card_def, kind, state, ci):
            return True
    # Third source: an aura from a different in-play unit (Mythosaur LOF_73).
    return _aura_protection(state, ci, kind)


def _apply_defeat_unit(state: "GameState", target_id: str) -> "GameState":
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, ci = result
    from swu.cards.models import Upgrade, TokenUpgrade
    from swu.engine.state import Zone
    # Defeating something attached as an upgrade: detach it from its host and
    # discard it (tokens are stripped silently, real upgrades go to the owner's
    # discard).  We key on ATTACHMENT, not on ``isinstance(card_def, Upgrade)``,
    # because a Pilot unit played via Piloting lives in a host's
    # ``attached_upgrades`` while its ``card_def`` is still a Unit.  Routing such a
    # pilot through the unit-defeat path below would fail to remove it from its
    # host (that path only scans the arenas) and then append it to discard,
    # double-homing the instance and tripping the "Duplicate instance_id"
    # invariant.
    for host_ps in state.players:
        for host in host_ps.ground_arena + host_ps.space_arena:
            if any(u.instance_id == target_id for u in host.attached_upgrades):
                host.attached_upgrades = [
                    u for u in host.attached_upgrades if u.instance_id != target_id]
                # "When a friendly upgrade is defeated" (Zeb Orrelios ASH_161) —
                # "friendly" is the HOST's controller, control following the host.
                from swu.engine.actions import note_upgrade_defeated
                note_upgrade_defeated(state, ci, host_ps.player_id)
                if not isinstance(ci.card_def, TokenUpgrade):
                    ci.zone = Zone.DISCARD
                    state.player_by_id(ci.owner_id).discard.append(ci)
                # A control-linking upgrade (Traitorous SOR_122) leaving its host
                # reverts any control it took — the host's owner reclaims it. Keyed
                # on ``control_linked_to`` (Maul LAW_54's seam, here fired from the
                # upgrade-removal chokepoint rather than the unit-leaves-play one).
                from swu.engine.actions import _revert_linked_control
                _revert_linked_control(state, ci)
                return state
    # A real (non-attached) Upgrade card not on any host: nothing to defeat.
    if isinstance(ci.card_def, Upgrade):
        return state
    from swu.engine.actions import _defeat_unit
    _defeat_unit(state, ps, ci)
    return state


def _apply_return_to_hand(state: "GameState", target_id: str) -> "GameState":
    result = state.find_instance(target_id)
    if result is None:
        return state
    ps, ci = result
    from swu.engine.state import Zone
    from swu.cards.models import TokenUpgrade

    # The target may itself be an *upgrade* attached to a host (Jabba the Hutt
    # ASH_42 "return an upgrade to its owner's hand").  An upgrade lives in its
    # host's ``attached_upgrades``, not an arena, so the unit-return arena-removal
    # loop below would silently fail and double-home it.  Detach it from whatever
    # host holds it and route it to its OWNER's hand as a clean card.  A token
    # upgrade ceases to exist rather than going to a hand.
    for holder_ps in state.players:
        for host_ci in holder_ps.ground_arena + holder_ps.space_arena:
            if ci in host_ci.attached_upgrades:
                host_ci.attached_upgrades.remove(ci)
                ci.attached_upgrades.clear()  # an upgrade holds no sub-upgrades, defensive
                # Returning a control-linking upgrade (Traitorous SOR_122) to hand
                # likewise reverts the control it took (host reclaimed by its owner).
                from swu.engine.actions import _revert_linked_control
                _revert_linked_control(state, ci)
                ci.damage = 0
                ci.exhausted = False
                ci.face_down = False
                ci.cannot_ready_this_round = False
                if isinstance(ci.card_def, TokenUpgrade):
                    ci.zone = Zone.DISCARD  # tokens are created on demand; they vanish
                    return state
                ci.zone = Zone.HAND
                state.player_by_id(ci.owner_id).hand.append(ci)
                return state

    # Strip upgrades
    for upg in list(ci.attached_upgrades):
        if not isinstance(upg.card_def, TokenUpgrade):
            upg_owner = state.player_by_id(upg.owner_id)
            upg.zone = Zone.DISCARD
            upg_owner.discard.append(upg)
    ci.attached_upgrades.clear()
    ci.damage = 0
    ci.exhausted = False
    ci.cannot_ready_this_round = False  # a card out of play is a clean card
    ci.abilities_suppressed = False  # a card out of play is a clean card (Mind Trick LOF_202)
    ci.control_linked_to = None  # a bounced unit is no longer linked to a source (Maul LAW_54)
    # Remove from arena
    for arena in (ps.ground_arena, ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break
    ci.zone = Zone.HAND
    owner_ps = state.player_by_id(ci.owner_id)
    owner_ps.hand.append(ci)
    # A returned card no longer sources any "while this unit is in play" permanent
    # modifier it may have granted (Huyang TWI_110) — drop them for hygiene (the
    # compute-time source-in-play guard already makes them inert).
    state.modifiers = [
        m for m in state.modifiers
        if not (m.duration == "permanent" and m.source_instance_id == ci.instance_id)
    ]
    return state


def _make_modifier(
    state: "GameState", source_id: str, target_id: str,
    power: int, hp: int, duration: Duration,
) -> "Modifier":
    from swu.engine.state import Modifier
    return Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_id,
        target_instance_id=target_id,
        kind="stats",
        value={"power": power, "hp": hp},
        duration=duration.value,
    )


def _make_kw_modifier(
    state: "GameState", source_id: str, target_id: str,
    keyword: str, value: int, duration: Duration, kind: str,
) -> "Modifier":
    from swu.engine.state import Modifier
    return Modifier(
        modifier_id=state.alloc_modifier_id(),
        source_instance_id=source_id,
        target_instance_id=target_id,
        kind=kind,
        value={"keyword": keyword, "value": value},
        duration=duration.value,
    )


# ── Inline vs choice detection ────────────────────────────────────────────────

def _ability_can_inline(ability: TriggerAbility, state: "GameState", source_ci: "CardInstance", event_ctx: dict) -> bool:
    """True if every effect in the ability can be executed without player choice."""
    if ability.optional:
        return False  # optional triggers always need the accept/decline decision
    # A no-target CustomEffect can arm a *later* effect's target via a side effect on
    # event_ctx (e.g. Force Throw SOR_167 discards a card, then arms a
    # ``requires_prior_target`` gate).  The inline check runs before that side effect,
    # so a later targeted effect would look target-less and be wrongly inlined (its
    # prompt skipped).  Once we have seen such an effect, defer any subsequent
    # currently-targetless targeted effect to the decision path (always correct — it
    # runs the effects in order, re-evaluating targets after each).
    saw_arming_custom = False
    for effect in ability.effects:
        if isinstance(effect, ConditionalEffect):
            # Check both branches conservatively — if either needs a choice, not inline
            branch = effect.if_true if effect.condition.evaluate(state, source_ci) else effect.if_false
            sub_ability = TriggerAbility(trigger=None, effects=list(branch))
            if not _ability_can_inline(sub_ability, state, source_ci, event_ctx):
                return False
            continue
        spec = _get_effect_target_spec(effect)
        if spec is None:
            if isinstance(effect, CustomEffect):
                saw_arming_custom = True  # may arm a later target via event_ctx
            continue  # DrawCards, DefeatAllUnits etc. — no player choice
        if spec.fixed is not None:
            continue  # fixed target — no player choice
        # player-chosen target: check if there are legal targets
        targets = _gather_legal_targets(state, spec, source_ci, event_ctx)
        if targets:
            return False  # has valid targets → needs choice
        if saw_arming_custom:
            return False  # a prior CustomEffect may arm this target — use the
                          # decision path, which re-checks targets after it runs
        # no legal targets → fizzles silently; still inline
    return True


def _optional_trigger_has_legal_effect(
    ability: TriggerAbility, state: "GameState", source_ci: "CardInstance", event_ctx: dict
) -> bool:
    """True if an optional 'may' trigger could produce at least one outcome.

    Used to auto-decline (silently skip) an optional trigger whose every effect
    has no legal target — e.g. 2-1B Surgical Droid's "you may heal 2 damage from
    another unit" when no other unit is damaged.  Otherwise the player would be
    shown a pointless accept/decline prompt for an ability that can do nothing.

    Conservative: returns True the moment any effect *could* do something, so we
    only drop the trigger when we are certain nothing can happen.
    """
    for effect in ability.effects:
        if isinstance(effect, ConditionalEffect):
            branch = effect.if_true if effect.condition.evaluate(state, source_ci) else effect.if_false
            sub = TriggerAbility(trigger=None, effects=list(branch))
            if _optional_trigger_has_legal_effect(sub, state, source_ci, event_ctx):
                return True
            continue
        avail = getattr(effect, "available_fn", None)
        if avail is not None and not avail(state, source_ci, event_ctx):
            continue  # the card says this effect can do nothing right now
                      # (CustomEffect.available_fn — Shadow Caster JTL_169)
        spec = _get_effect_target_spec(effect)
        if spec is None:
            return True  # non-targeted effect (DrawCards, etc.) always does something
        if spec.fixed is not None:
            if _resolve_fixed_target_ids(state, spec, source_ci, event_ctx):
                return True
            continue
        if _gather_legal_targets(state, spec, source_ci, event_ctx):
            return True
    return False


def _resolve_inline(
    state: "GameState",
    ability: TriggerAbility,
    source_ci: "CardInstance",
    event_ctx: dict,
) -> "GameState":
    """Execute all effects of a mandatory inline ability."""
    for effect in ability.effects:
        state = execute_effect(state, effect, source_ci, None, event_ctx)
    return state


# ── "Use that ability again" meta-mechanic (Aethersprite LOF_197, Thrawn JTL_2) ─

def _find_ability_redo(state: "GameState", controller_id: str, marker_cls):
    """Locate a redo marker of type ``marker_cls`` that ``controller_id`` has in play
    and whose cost is payable right now, as ``(source_ci, marker)`` — or ``None``.

    Shared by both marker kinds: ``WhenDefeatedRedo`` (Grand Admiral Thrawn JTL_2)
    and ``OnAttackRedo`` (Enfys Nest LAW_14), which differ only in the trigger class
    they answer for and in ``OnAttackRedo``'s extra ``cost_resources``.

    Scans the controller's arenas (a deployed leader) and their base_zone leader (an
    undeployed one), honouring each marker's ``deployed_only`` / ``undeployed_only``
    gate the way ``_collect_triggers`` gates a leader's triggers.  A marker whose
    cost cannot be paid — an already-exhausted ``cost_exhaust_source`` leader, too
    few ready resources for ``cost_resources``, or a ``once_per_round`` marker
    already used this round — is skipped, so an unusable redo is never offered."""
    from swu.cards.models import Leader
    ps = state.player_by_id(controller_id)
    used = state.game_memory.when_defeated_redo_used_this_round
    ready_resources = sum(1 for r in ps.resources if not r.exhausted)
    candidates = [(ci, False) for ci in (*ps.ground_arena, *ps.space_arena)]
    candidates += [(ci, True) for ci in ps.base_zone
                   if isinstance(getattr(ci, "card_def", None), Leader)
                   and not ci.deployed]
    for ci, undeployed in candidates:
        cd = ci.card_def
        if not hasattr(cd, "set_code") or not hasattr(cd, "card_number"):
            continue
        for spec in get_abilities(cd.set_code or "", cd.card_number or ""):
            if not isinstance(spec, marker_cls):
                continue
            if spec.undeployed_only and not undeployed:
                continue
            if spec.deployed_only and undeployed:
                continue
            if spec.cost_exhaust_source and ci.exhausted:
                continue
            if getattr(spec, "cost_resources", 0) > ready_resources:
                continue
            if spec.once_per_round and ci.instance_id in used:
                continue
            return ci, spec
    return None


def _find_when_defeated_redo(state: "GameState", controller_id: str):
    """``_find_ability_redo`` narrowed to ``WhenDefeatedRedo`` (Thrawn JTL_2)."""
    from swu.abilities.registry import WhenDefeatedRedo
    return _find_ability_redo(state, controller_id, WhenDefeatedRedo)


def _when_defeated_ability_indices(state: "GameState",
                                   ci: "CardInstance") -> list[int]:
    """Registry indices of ``ci``'s "When Defeated" abilities, in registration order.

    "Any ability whose trigger starts with 'When Defeated…' is considered a 'When
    Defeated' ability" (Chimaera JTL_39's printed rules note).  A Bounty
    (``is_bounty``) is its own keyword ability collected by the OPPONENT, and
    ``WhenDefeatedAsUpgrade`` is a defeat *replacement* — neither counts, the same
    two carve-outs ``_schedule_ability_redo`` makes.  A suppressed unit (Mind Trick
    LOF_202 / Imprisoned SHD_72 / …) has no abilities at all."""
    from swu.engine.state import ability_suppressed
    if ability_suppressed(state, ci):
        return []
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    if not sc or not cn:
        return []
    out: list[int] = []
    for idx, spec in enumerate(get_abilities(sc, cn)):
        ability = unwrap_granted(spec)
        if not isinstance(ability, TriggerAbility):
            continue
        if not isinstance(ability.trigger, WhenDefeated):
            continue
        if getattr(ability, "is_bounty", False):
            continue
        out.append(idx)
    return out


def _when_played_ability_indices(state: "GameState",
                                 ci: "CardInstance") -> list[int]:
    """Registry indices of ``ci``'s "When Played" abilities, in registration order —
    the WhenPlayed sibling of ``_when_defeated_ability_indices``.

    "Any ability whose trigger starts with 'When played…' is considered a 'When
    Played' ability" (Fire Across the Galaxy LAW_256's printed rules note).  A
    ``GrantedAbility`` wrapper is unwrapped like everywhere else, and a suppressed
    unit has no abilities at all."""
    from swu.engine.state import ability_suppressed
    if ability_suppressed(state, ci):
        return []
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    if not sc or not cn:
        return []
    out: list[int] = []
    for idx, spec in enumerate(get_abilities(sc, cn)):
        ability = unwrap_granted(spec)
        if not isinstance(ability, TriggerAbility):
            continue
        if isinstance(ability.trigger, WhenPlayed):
            out.append(idx)
    return out


def _schedule_ability_redo(
    state: "GameState",
    source_ci: "CardInstance",
    set_code: str,
    card_number: str,
    ability_idx: int,
    event_ctx: dict,
    after_idx: int,
    insert_at: int,
) -> "GameState":
    """Offer an optional re-use of the ability that was just *used*, when something
    on the board grants one — the shared "use that ability again" chokepoint.

    Two shapes feed it:

    * **When Played** — Qui-Gon Jinn's Aethersprite LOF_197 arms a phase-scoped
      per-player charge (``game_memory.when_played_redo_charges``).  The charge is
      spent the moment a qualifying WhenPlayed ability is used, whether or not
      re-using it can accomplish anything: its delayed trigger's condition ("the
      next time you use a When Played ability this phase") has been met.
    * **When Defeated** — a ``WhenDefeatedRedo`` marker the ability's controller has
      in play (Grand Admiral Thrawn JTL_2).  Standing rather than a charge, and its
      cost (exhaust the leader / the once-per-round limit) is charged on ACCEPT in
      ``actions.AcceptTrigger``, because declining a "you may" is not a use.
    * **On Attack** — an ``OnAttackRedo`` marker, the exact sibling of the above
      (Enfys Nest LAW_14), whose extra ``cost_resources`` is charged at the same
      accept-time site.

    Called wherever an ability is used — right after an inline one resolves, when a
    mandatory one's target decision is pushed, and when an optional one is accepted.
    The "use it again" is modelled by inserting a fresh ``trigger_option`` decision
    for the SAME ability (same registry entry / source / event context) at
    ``insert_at`` — just *below* the original's resolution on the stack — so it
    resolves only after the original ability (and any sub-decisions it spawned)
    fully completes.  On accept it re-runs the ability with fresh target choices via
    the normal trigger_option → resolve_effects path; the ``ability_redo``
    event-context flag prevents a re-use from itself arming another redo."""
    if event_ctx.get("ability_redo") or event_ctx.get("aethersprite_redo"):
        return state  # a redo resolution never arms another redo
    specs = get_abilities(set_code, card_number)
    if ability_idx >= len(specs):
        return state
    ability = unwrap_granted(specs[ability_idx])
    if not isinstance(ability, TriggerAbility):
        return state
    owner_id = source_ci.owner_id
    redo_ctx_extra: dict = {}

    if isinstance(ability.trigger, WhenPlayed):
        charges = state.game_memory.when_played_redo_charges
        if charges.get(owner_id, 0) <= 0:
            return state
        charges[owner_id] -= 1
        if charges[owner_id] <= 0:
            del charges[owner_id]
    elif isinstance(ability.trigger, WhenDefeated):
        # A Bounty is collected by the OPPONENT of the defeated unit's controller,
        # never by ``owner_id`` — and Bounty is its own keyword ability, not one
        # whose trigger reads "When Defeated" (JTL_2's own printed rules note:
        # "Any ability whose trigger starts with 'When Defeated' is considered a
        # 'When Defeated' ability").  ``WhenDefeatedAsUpgrade`` is likewise not one
        # — it is a defeat *replacement* ("If this upgrade would be defeated…"), and
        # is a distinct trigger class, so this isinstance never matches it.
        if getattr(ability, "is_bounty", False):
            return state
        found = _find_when_defeated_redo(state, owner_id)
        if found is None:
            return state
        redo_ci, marker = found
        redo_ctx_extra = {
            "redo_source_id": redo_ci.instance_id,
            "redo_cost_exhaust": bool(marker.cost_exhaust_source),
            "redo_once_per_round": bool(marker.once_per_round),
        }
    elif isinstance(ability.trigger, OnAttack):
        # "When you use an 'On Attack' ability: … use that ability again" (Enfys
        # Nest LAW_14).  The exact sibling of the When Defeated arm above, over an
        # ``OnAttackRedo`` marker — standing, and priced on ACCEPT only, since
        # declining a "you may" is not a use.  Unlike a When Defeated ability there
        # is no Bounty carve-out to make: a Bounty is a When Defeated ability by
        # construction, so nothing an OnAttack trigger can be belongs to the
        # opponent.
        from swu.abilities.registry import OnAttackRedo
        found = _find_ability_redo(state, owner_id, OnAttackRedo)
        if found is None:
            return state
        redo_ci, marker = found
        redo_ctx_extra = {
            "redo_source_id": redo_ci.instance_id,
            "redo_cost_exhaust": bool(marker.cost_exhaust_source),
            "redo_once_per_round": bool(marker.once_per_round),
            "redo_cost_resources": int(getattr(marker, "cost_resources", 0)),
        }
    else:
        return state

    # Offer the optional re-use only when the ability could actually do something
    # now (mirrors the engine's auto-decline-of-pointless-optionals); otherwise a
    # WhenPlayed charge is simply spent with no prompt (and a Thrawn redo, whose
    # cost is charged on accept, costs nothing at all).
    if not _optional_trigger_has_legal_effect(ability, state, source_ci, event_ctx):
        return state

    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    redo_ctx = dict(event_ctx)
    redo_ctx["ability_redo"] = True
    dec = PendingDecision(
        deciding_player_id=owner_id,
        kind="trigger_option",
        context={
            "set_code": set_code,
            "card_number": card_number,
            "ability_idx": ability_idx,
            "source_id": source_ci.instance_id,
            "event_ctx": redo_ctx,
            "after_all_player_idx": after_idx,
            **redo_ctx_extra,
        },
        after_resolve_player_index=after_idx,
    )
    insert_at = max(0, min(insert_at, len(state.pending_decisions)))
    state.pending_decisions.insert(insert_at, dec)
    state.event_log.append(DecisionPushed(
        deciding_player_id=owner_id, kind="trigger_option"))
    # If the redo landed on top of the stack (the original spawned no sub-decision),
    # the controller must act on it next, so hand them the active seat.  When it was
    # inserted *below* a still-pending sub-decision, that sub-decision stays on top
    # and the actor is driven by the top decision's deciding player, not this index.
    if insert_at == len(state.pending_decisions) - 1:
        state.active_player_index = state.player_index(owner_id)
    return state


# ── Trigger firing (public) ───────────────────────────────────────────────────

def fire_triggered_abilities(
    state: "GameState",
    event: "GameEvent",
    after_all_player_idx: int,
    event_ctx: Optional[dict] = None,
) -> "GameState":
    """Collect and begin resolution of all triggered abilities matching event.

    Mandatory triggers with only fixed/auto targets are resolved inline
    immediately.  Optional triggers and triggers requiring player target
    choices push PendingDecision objects onto the stack.

    after_all_player_idx: the player index that should be active after ALL
    resulting decisions have been resolved.  Stored in the bottommost
    pushed decision's after_resolve_player_index.
    """
    if event_ctx is None:
        event_ctx = {}

    # Per-phase per-player card-play counter (Ki-Adi-Mundi TWI_64 "an opponent plays
    # their second card each phase").  CardPlayed is the one event every play path
    # emits and every site fires it through here exactly once, so this is the single
    # chokepoint; increment BEFORE collection so the WhenOpponentPlaysNthCard matcher
    # sees the post-increment count.  Tokens (CreateTokenUnit) fire UnitEntersPlay,
    # not CardPlayed, so they correctly do not count as "a card played".
    from swu.engine.events import CardPlayed as _CardPlayed
    if isinstance(event, _CardPlayed):
        counter = state.game_memory.cards_played_this_phase
        counter[event.player_id] = counter.get(event.player_id, 0) + 1
        # Alongside the count, record the played card's effective TRAITS — "If you
        # played a First Order card this phase" (Captain Phasma JTL_10).  Recorded
        # here, at play time, because an event card is already in the discard by the
        # time the condition is read.  Purely additive: nothing else consults the
        # ledger, so a card with no traits simply records an empty set.
        played = state.find_instance(event.instance_id)
        if played is not None:
            from swu.engine.traits import get_traits
            seen = state.game_memory.traits_played_this_phase.setdefault(
                event.player_id, set())
            traits_now = get_traits(state, played[1])
            seen.update(traits_now)
            # The NON-UNIT slice of the same record — "If you played a non-unit
            # Force card this phase" (Rey LOF_12).  Only the card type differs, and
            # it is knowable only here (an event is in the discard by the time the
            # condition is read), so it is split at record time, not read time.
            from swu.cards.models import Unit as _UnitCard
            if not isinstance(played[1].card_def, _UnitCard):
                nu = state.game_memory.non_unit_traits_played_this_phase.setdefault(
                    event.player_id, set())
                nu.update(traits_now)
        # A traitless non-unit card records nothing above, so "the FIRST non-unit
        # card you play each phase" (Peli Motto ASH_212) needs its own COUNT.
        if played is not None:
            from swu.cards.models import Unit as _UnitCard2
            if not isinstance(played[1].card_def, _UnitCard2):
                counts = state.game_memory.non_units_played_this_phase
                counts[event.player_id] = counts.get(event.player_id, 0) + 1

    triggers = _collect_triggers(state, event, event_ctx)

    # Record every *bounty* collection into the bounties-collected ledger (drained at
    # the action settle-point to fire the WhenBountyCollected observer, Bossk SHD_10).
    # A bounty is an ``is_bounty`` WhenDefeated ability; it resolves for the COLLECTOR
    # = the opponent of the dying unit's controller (event_ctx["defeated_controller_id"],
    # set only by _defeat_unit).  One entry per collected bounty, carrying the bounty's
    # registry coordinates so the re-collection (push_bounty_recollect) can re-run it.
    # This is the sole record chokepoint — no bounty card fn changes.  The re-run
    # bypasses this collection scan, so it never re-records (no chain).
    dc_id = event_ctx.get("defeated_controller_id")
    if dc_id is not None:
        for ci, sci, idx, ab in triggers:
            if not getattr(ab, "is_bounty", False):
                continue
            collector_id = state.players[1 - state.player_index(dc_id)].player_id
            state.game_memory.bounties_collected.append({
                "collector_id": collector_id,
                "set_code": sci.card_def.set_code or "",
                "card_number": sci.card_def.card_number or "",
                "ability_idx": idx,
                "source_id": ci.instance_id,
                "defeated_controller_id": dc_id,
            })

    if not triggers:
        return state

    # Auto-decline optional "may" triggers that can't do anything (no legal
    # target for any effect) — they would only show a pointless accept/decline
    # prompt.  Mandatory triggers with no target already fizzle inline below.
    triggers = [
        (ci, sci, idx, ab) for ci, sci, idx, ab in triggers
        if not ab.optional or _optional_trigger_has_legal_effect(ab, state, ci, event_ctx)
    ]
    if not triggers:
        return state

    # Separate inline-resolvable from decision-requiring
    inline = [(ci, sci, idx, ab) for ci, sci, idx, ab in triggers if _ability_can_inline(ab, state, ci, event_ctx)]
    needs_decision = [(ci, sci, idx, ab) for ci, sci, idx, ab in triggers if not _ability_can_inline(ab, state, ci, event_ctx)]

    # Execute inline triggers immediately.  An inline ability may itself push a
    # sub-decision (a CustomEffect adapter onto push_select_token etc.); a redo is
    # inserted just below whatever this ability spawned, so it resolves only after
    # the original ability fully completes.
    for ci, sci, idx, ab in inline:
        depth_before = len(state.pending_decisions)
        state = _resolve_inline(state, ab, ci, event_ctx)
        state = _schedule_ability_redo(
            state, ci, sci.card_def.set_code or "", sci.card_def.card_number or "",
            idx, event_ctx, after_all_player_idx, depth_before)

    if not needs_decision:
        return state

    # Group decision-requiring triggers by owner for ordering purposes
    # Initiative holder's triggers resolve first (pushed last → on top of stack)
    ih_triggers = [(ci, sci, idx, ab) for ci, sci, idx, ab in needs_decision
                   if state.player_index(ci.owner_id) == state.initiative_holder]
    other_triggers = [(ci, sci, idx, ab) for ci, sci, idx, ab in needs_decision
                      if state.player_index(ci.owner_id) != state.initiative_holder]

    # Build the final ordered list: other player's triggers resolve first (before initiative holder)
    # LIFO: push in reverse — push IH triggers first (bottom), then other triggers (top)
    ordered = ih_triggers + other_triggers  # IH pushed first → bottom of new decisions; other on top

    # Push decisions; bottommost gets after_all_player_idx, others get deciding player's index
    from swu.engine.events import DecisionPushed

    decisions_to_push = []
    for i, (ci, spec_ci, ability_idx, ab) in enumerate(ordered):
        owner_idx = state.player_index(ci.owner_id)
        is_last_pushed = (i == len(ordered) - 1)
        after_idx = after_all_player_idx if is_last_pushed else owner_idx
        dec = _build_ability_decision(state, ci, spec_ci, ability_idx, ab, after_idx, event_ctx)
        decisions_to_push.append((dec, ci.owner_id))

    for dec, owner_id in decisions_to_push:
        state.pending_decisions.append(dec)
        state.event_log.append(DecisionPushed(
            deciding_player_id=owner_id,
            kind=dec.kind,
        ))
        state.active_player_index = state.player_index(owner_id)

    # A *mandatory* ability that needs a target decision will certainly be used, so
    # arm any redo now, inserting it just below that decision (an optional ability
    # is handled at accept-time in AcceptTrigger — declining it is not a "use").
    # Mandatory-targeted WhenPlayed abilities are rare (the common shapes resolve
    # inline above or are optional), but mandatory-targeted WhenDefeated ones are
    # ordinary ("When Defeated: deal 2 damage to a unit" — Thrawn JTL_2's bread
    # and butter).
    for (ci, spec_ci, ability_idx, ab) in ordered:
        if ab.optional:
            continue
        dec = _build_ability_decision(state, ci, spec_ci, ability_idx, ab,
                                      after_all_player_idx, event_ctx)
        # Locate this just-pushed decision and insert the redo immediately below it.
        for pos in range(len(state.pending_decisions) - 1, -1, -1):
            d = state.pending_decisions[pos]
            if (d.kind == dec.kind
                    and d.context.get("source_id") == ci.instance_id
                    and d.context.get("ability_idx") == ability_idx):
                state = _schedule_ability_redo(
                    state, ci, spec_ci.card_def.set_code or "",
                    spec_ci.card_def.card_number or "", ability_idx,
                    event_ctx, after_all_player_idx, pos)
                break

    return state


def _build_ability_decision(
    state: "GameState",
    source_ci: "CardInstance",
    spec_ci: "CardInstance",
    ability_idx: int,
    ability: TriggerAbility,
    after_resolve_player_index: int,
    event_ctx: dict,
) -> "PendingDecision":
    from swu.engine.decisions import PendingDecision

    # The spec is addressed by the card whose registry holds it (``spec_ci`` —
    # the upgrade for a granted ability), while ``source_id`` is the unit the
    # ability resolves from (``source_ci`` — the host for a granted ability).
    set_code = spec_ci.card_def.set_code or ""
    card_number = spec_ci.card_def.card_number or ""

    # The decision is persisted on the stack (and serialised every action), so
    # its stored event_ctx must contain only JSON-serialisable values AND no
    # hidden info (the whole context is shown to the deciding player).  Drop
    # collection-only keys:
    #   - ``defeated_ci`` / ``defeated_upgrades`` — raw CardInstances (not
    #     JSON-serialisable), needed only during synchronous trigger collection
    #     (the granted-bounty-from-a-defeated-upgrade scan); resolution re-locates
    #     the source by source_id (by then the defeated unit is in its
    #     discard/base zone and findable).
    #   - ``drawn_card_ids`` — the just-drawn card instance ids, needed only to
    #     collect a drawn card's own WhenYouDraw(on_self) trigger and to match the
    #     in-play draw observer during collection.  For an OPPONENT-draw observer
    #     (Seasoned Fleet Admiral JTL_111) the deciding player is NOT the drawer,
    #     so leaving these ids in the persisted context would leak the opponent's
    #     freshly-drawn hand card into the deciding player's view (a hidden-info
    #     leak).  Resolution never reads them.
    _TRANSIENT = ("defeated_ci", "defeated_upgrades", "drawn_card_ids")
    event_ctx = {k: v for k, v in event_ctx.items() if k not in _TRANSIENT}

    if ability.optional:
        return PendingDecision(
            deciding_player_id=source_ci.owner_id,
            kind="trigger_option",
            context={
                "set_code": set_code,
                "card_number": card_number,
                "ability_idx": ability_idx,
                "source_id": source_ci.instance_id,
                "event_ctx": event_ctx,
                "after_all_player_idx": after_resolve_player_index,
            },
            after_resolve_player_index=after_resolve_player_index,
        )
    else:
        return PendingDecision(
            deciding_player_id=source_ci.owner_id,
            kind="resolve_effects",
            context={
                "set_code": set_code,
                "card_number": card_number,
                "ability_idx": ability_idx,
                "source_id": source_ci.instance_id,
                "effect_idx": 0,
                "resolved_targets": {},
                "event_ctx": event_ctx,
                "after_all_player_idx": after_resolve_player_index,
            },
            after_resolve_player_index=after_resolve_player_index,
        )


# ── Decision resolution helpers (called from actions.py) ─────────────────────

def resolve_effects_actions(state: "GameState", decision: object) -> "list[Action]":
    """Return legal actions for the top 'resolve_effects' pending decision.

    Skips effects that can be auto-resolved and returns target choices for
    the first effect that requires player input.  If all remaining effects
    can be auto-resolved, returns a single AutoResolveEffects action.
    """
    from swu.engine.actions import ChooseTarget, DeclineTarget, AutoResolveEffects

    ctx = decision.context  # type: ignore[attr-defined]
    set_code = ctx["set_code"]
    card_number = ctx["card_number"]
    ability_idx = ctx["ability_idx"]
    source_id = ctx["source_id"]
    effect_idx = ctx["effect_idx"]
    event_ctx = ctx.get("event_ctx", {})

    from swu.abilities.registry import get_abilities
    specs = get_abilities(set_code, card_number)
    if ability_idx >= len(specs):
        return [AutoResolveEffects()]

    ability = unwrap_granted(specs[ability_idx])
    effects = ability.effects

    # Advance past effects that can be auto-resolved
    source_result = state.find_instance(source_id)
    if source_result is None:
        return [AutoResolveEffects()]
    _, source_ci = source_result

    while effect_idx < len(effects):
        eff = effects[effect_idx]
        spec = _get_effect_target_spec(eff)
        if spec is None or spec.fixed is not None:
            effect_idx += 1
            continue
        targets = _gather_legal_targets(state, spec, source_ci, event_ctx)
        if not targets:
            effect_idx += 1
            continue
        # This effect needs a choice
        acts: list["Action"] = [ChooseTarget(t) for t in targets]
        if spec.optional:
            acts.append(DeclineTarget())
        return acts

    # All effects are auto-resolvable
    return [AutoResolveEffects()]


def apply_resolve_effects(state: "GameState", chosen_target_id: Optional[str]) -> "GameState":
    """Execute effects for the top 'resolve_effects' decision.

    called from ChooseTarget.apply() and AutoResolveEffects.apply().
    chosen_target_id is None when auto-resolving or when the player declined.
    """
    import copy
    s = copy.deepcopy(state)
    top = s.pending_decisions[-1]
    ctx = top.context
    set_code = ctx["set_code"]
    card_number = ctx["card_number"]
    ability_idx = ctx["ability_idx"]
    source_id = ctx["source_id"]
    event_ctx = ctx.get("event_ctx", {})

    specs = get_abilities(set_code, card_number)
    if ability_idx >= len(specs):
        s.pending_decisions.pop()
        s.active_player_index = top.after_resolve_player_index
        return s

    ability = unwrap_granted(specs[ability_idx])
    effects = ability.effects

    source_result = s.find_instance(source_id)
    if source_result is None:
        s.pending_decisions.pop()
        s.active_player_index = top.after_resolve_player_index
        return s
    _, source_ci = source_result

    effect_idx = ctx["effect_idx"]

    # If a choice was made, execute the effect at current effect_idx with the chosen target
    if chosen_target_id is not None and effect_idx < len(effects):
        eff = effects[effect_idx]
        spec = _get_effect_target_spec(eff)
        if spec is not None and spec.fixed is None:
            s = execute_effect(s, eff, source_ci, chosen_target_id, event_ctx)
            effect_idx += 1
            ctx["effect_idx"] = effect_idx
            # Re-acquire source_ci after possible state changes
            source_result2 = s.find_instance(source_id)
            if source_result2 is not None:
                _, source_ci = source_result2

    # Auto-resolve remaining auto-resolvable effects
    while effect_idx < len(effects):
        eff = effects[effect_idx]
        spec = _get_effect_target_spec(eff)
        if spec is None or spec.fixed is not None:
            s = execute_effect(s, eff, source_ci, None, event_ctx)
            effect_idx += 1
            ctx["effect_idx"] = effect_idx
            source_result3 = s.find_instance(source_id)
            if source_result3 is not None:
                _, source_ci = source_result3
            continue
        targets = _gather_legal_targets(s, spec, source_ci, event_ctx)
        if not targets:
            # Fizzle — no legal targets, skip this effect
            effect_idx += 1
            ctx["effect_idx"] = effect_idx
            continue
        # Stop — this effect needs a player choice
        break

    if effect_idx >= len(effects):
        # All effects resolved.  Normally pop our decision and hand control to
        # after_resolve_player_index.  But an effect may have pushed a *nested*
        # decision (e.g. SOR_233 I Am Your Father's opponent "say no" choice); in
        # that case our resolve_effects decision is now buried beneath it.  Leave
        # it in place — once the nested decision resolves and returns control,
        # this decision is back on top with effect_idx past the end, so
        # legal_actions offers an AutoResolveEffects that pops it cleanly.
        if s.pending_decisions and s.pending_decisions[-1] is top:
            s.pending_decisions.pop()
            s.active_player_index = top.after_resolve_player_index

    return s
