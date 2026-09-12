"""The attack pipeline: declaring an attack and resolving it to damage.

An attack is the most rule-dense action in the game, and CR order matters at every
step.  ``AttackWithUnit`` and the ``_resolve_*`` helpers run it as a fixed sequence:

1. Declare and exhaust the attacker.
2. On-attack triggers — Restore healing, Saboteur stripping the defender's shields.
3. Compute effective power (``stats``), including Raid and Grit.
4. Deal damage simultaneously, intercepted by Shield (``damage``).
5. Overwhelm spills excess damage to the defending base.
6. Process defeats, then settle anything that keyed off "after combat".

The steps are split into ``_resolve_*`` / ``_resolve_*_step2`` pairs because an
interactive prevention effect can interrupt the middle of an attack: the engine
pushes a decision, waits for a player, and resumes at step 2.  That is also why
first strike (``_defender_deals_first``) is a branch in the sequence rather than a
flag applied at the end — with first strike, a defeated defender never deals its
damage at all.

What legality means here is genuinely complicated, and ``_enumerate_attacks`` is the
one place that knows all of it: Sentinel forcing a ground attacker to take the
Sentinel first, units that cannot attack bases, arena restrictions, units hidden
from attack, and granted attacks filtered by their own predicates.

One trap, recorded because it has bitten before:
``_attacker_matches_predicates`` **ignores a predicate it does not recognise rather
than failing it.** A granted attack with a misspelled or newly-added predicate is
therefore silently legal. Any new predicate has to be added both here and in the
ability resolver.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    AttackDeclared, DamageDealt, DecisionPushed, DecisionResolved, OverwhelmDamage,
    RestoreHealing,
)
from swu.engine.keywords import Keyword, has_keyword, keyword_value, shields_on
from swu.engine.state import (
    CardInstance, GameState, Phase, PlayerState, Zone, ability_suppressed,
)
from swu.engine.tokens import defeat_shield
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.stats import (
    _expire_modifiers, compute_hp, compute_power,
)
from swu.engine.actions.damage import (
    _bases_cannot_heal, _deal_damage_with_shield, _hp_lethal, base_damage_after_prevention, note_base_healed,
)
from swu.engine.actions.zones import (
    _defeat_unit, _draw_cards, _find_in_arenas,
)
from swu.engine.actions.flow import (
    _assert_phase, _check_game_over, _switch_active_player,
)

# ── ACTION phase actions ──────────────────────────────────────────────────────

@dataclass
class AttackWithUnit(Action):
    attacker_id: str
    defender_id: Optional[str] = None  # None = attack base

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)

        # An effect-granted attack (e.g. Surprise Strike) presents itself as a
        # "granted_attack" decision on top of the stack.  Resolving it consumes
        # the decision and applies the granted this-attack stat bonus to the
        # chosen attacker before the normal combat pipeline runs.
        granted = None
        if s.pending_decisions and s.pending_decisions[-1].kind == "granted_attack":
            granted = s.pending_decisions.pop()

        active_ps = s.active_player
        inactive_ps = s.inactive_player

        attacker = _find_in_arenas(active_ps, self.attacker_id)
        if attacker is None:
            raise IllegalActionError(f"Attacker {self.attacker_id} not found")
        # Mon Mothma SEC_103 grants attacks "even if those units are exhausted",
        # so a granted attack carrying allow_exhausted bypasses the normal guard.
        allow_exhausted = granted is not None and granted.context.get("allow_exhausted")
        if attacker.exhausted and not allow_exhausted:
            raise IllegalActionError("Attacker is exhausted")

        # Stay on Target JTL_177: "gains 'When this unit deals damage to a base:
        # Draw a card.'"  Snapshot every base's damage before combat so the rider
        # below can tell whether the attack put anything on one (an Overwhelm spill
        # counts exactly like a direct base attack).
        # Flash the Vents LAW_205 ("if that unit damaged a base, defeat that unit")
        # reads the very same snapshot, so either rider arms it.
        base_damage_before = None
        if granted is not None and (granted.context.get("draw_if_base_damaged")
                                    or granted.context.get(
                                        "defeat_attacker_if_base_damaged")
                                    or granted.context.get(
                                        "opponent_discard_if_base_damaged")):
            base_damage_before = {
                ps.player_id: (ps.base_instance.damage
                               if ps.base_instance is not None else 0)
                for ps in s.players}

        if granted is not None:
            from swu.engine.state import Modifier
            gctx = granted.context
            source_id = gctx.get("source_id") or attacker.instance_id
            p_bonus = int(gctx.get("power_bonus", 0) or 0)
            h_bonus = int(gctx.get("hp_bonus", 0) or 0)
            # A trait-gated bonus (e.g. Fleet Lieutenant: +2/+0 only if Rebel)
            # applies only when the chosen attacker has the named trait.
            bonus_trait = gctx.get("bonus_trait")
            if bonus_trait is not None:
                traits = getattr(attacker.card_def, "traits", ()) or ()
                if bonus_trait not in traits:
                    p_bonus = h_bonus = 0
            # A defender-gated bonus (Moff Gideon SHD_7: "If it's attacking a
            # unit, it gets +1/+0") applies only when attacking a unit, not a base.
            if gctx.get("bonus_if_defender_unit") and self.defender_id is None:
                p_bonus = h_bonus = 0
            # An odd-cost-comparison bonus (Han Solo JTL_17: "If the revealed card
            # and that unit have different odd costs, +1/+0") — the revealed card's
            # cost is stashed in the context; the bonus applies only when BOTH the
            # revealed cost and the chosen attacker's cost are odd AND differ.
            odd_cmp = gctx.get("bonus_if_odd_cost_diff_from")
            if odd_cmp is not None:
                a_cost = getattr(attacker.card_def, "cost", None)
                if not (a_cost is not None and a_cost % 2 == 1
                        and odd_cmp % 2 == 1 and a_cost != odd_cmp):
                    p_bonus = h_bonus = 0
            # An arena-gated bonus (Swoop Down SHD_230: "If it attacks a GROUND
            # unit, it gets +2/+0") applies only when the chosen defender is a unit
            # in the ground arena (the cross-arena attacker may still hit space).
            if gctx.get("bonus_if_defender_ground"):
                dfd = (_find_in_arenas(inactive_ps, self.defender_id)
                       if self.defender_id is not None else None)
                if dfd is None or dfd.zone != Zone.GROUND_ARENA:
                    p_bonus = h_bonus = 0
            # A defender-damage-scaled bonus (Corner the Prey TWI_139: "+1/+0 for
            # each damage on the defender AT THE START OF THIS ATTACK").  Read
            # here, before the combat pipeline deals anything, so the snapshot is
            # the pre-attack damage — the card's whole point.  "The defender" is
            # whatever the attack is aimed at, so a BASE defender counts its own
            # damage.  Added after the gates above so it is a bonus in its own
            # right, not something a trait/arena gate could zero.
            per_dmg = int(gctx.get("bonus_per_defender_damage", 0) or 0)
            if per_dmg:
                dfd = (inactive_ps.base_instance if self.defender_id is None
                       else _find_in_arenas(inactive_ps, self.defender_id))
                p_bonus += per_dmg * int(getattr(dfd, "damage", 0) or 0)
            # "+1/+0 for this attack for each unit the defending player controls in
            # ITS arena" (Masterstroke ASH_234) — the sibling of the count above,
            # scaled by a defender-side POPULATION rather than a defender's damage,
            # and measured in the ATTACKER's arena (which is "its arena", and is the
            # only arena an ordinary attack can reach).
            per_arena = int(gctx.get("bonus_per_defending_arena_unit", 0) or 0)
            if per_arena:
                arena = (inactive_ps.ground_arena
                         if attacker.zone == Zone.GROUND_ARENA
                         else inactive_ps.space_arena)
                p_bonus += per_arena * len(arena)
            # "+1/+0 for this attack for each unit controlled by the DEFENDING
            # PLAYER" (Fearless Attack TS26_84) — the arena-blind sibling of the
            # count above.  A base attack has no unit defender but still has a
            # defending player, so it scales there too, exactly as printed.
            per_player = int(gctx.get("bonus_per_defending_player_unit", 0) or 0)
            if per_player:
                p_bonus += per_player * (len(inactive_ps.ground_arena)
                                         + len(inactive_ps.space_arena))
            if p_bonus or h_bonus:
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=source_id,
                    target_instance_id=attacker.instance_id,
                    kind="stats",
                    value={"power": p_bonus, "hp": h_bonus},
                    duration="this_attack",
                ))
            # Keywords granted for this attack (e.g. Shoot First -> First Strike).
            # An entry may be a bare name (value 0) or a (name, value) pair for a
            # numeric keyword (Leia Organa JTL_97: "gains Restore 1 for this
            # attack") — a JSON round-trip turns the tuple into a list.
            for kw in gctx.get("grant_keywords") or []:
                if isinstance(kw, (list, tuple)):
                    kw_name, kw_val = kw[0], int(kw[1])
                else:
                    kw_name, kw_val = kw, 0
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=source_id,
                    target_instance_id=attacker.instance_id,
                    kind="keyword_grant",
                    value={"keyword": kw_name, "value": kw_val},
                    duration="this_attack",
                ))
            # "Prevent all damage that would be dealt to it during this attack" (I
            # Have You Now JTL_193) — a ``damage_prevention`` modifier with ``all``
            # and NO ``combat_only``, so an ability that damages the attacker
            # mid-attack is prevented too, expiring with the this_attack sweep.
            if gctx.get("attacker_damage_prevention"):
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=source_id,
                    target_instance_id=attacker.instance_id,
                    kind="damage_prevention",
                    value=({"all": True, "combat_only": True}
                           if gctx.get("attacker_prevention_combat_only")
                           else {"all": True}),
                    duration="this_attack",
                ))
            # "For this attack, it deals damage equal to its remaining HP instead of
            # its power" (Babu Frik LOF_206) — expressed as a this_attack stats
            # modifier that shifts effective power onto remaining HP, so every
            # damage site (combat, Overwhelm spill) agrees without a second notion
            # of "attack damage".  Sized AFTER the bonuses above, from the values
            # they produced.
            if gctx.get("power_equals_remaining_hp"):
                remaining_hp = max(0, compute_hp(s, attacker) - attacker.damage)
                delta = remaining_hp - compute_power(s, attacker)
                if delta:
                    s.modifiers.append(Modifier(
                        modifier_id=s.alloc_modifier_id(),
                        source_instance_id=source_id,
                        target_instance_id=attacker.instance_id,
                        kind="stats",
                        value={"power": delta, "hp": 0},
                        duration="this_attack",
                    ))
            # "For this attack, it gains: 'On Attack: Return any number of
            # non-unique upgrades attached to the defender to their owners' hands'"
            # (Force Speed LOF_205).  Marked on the attacker here and read inside the
            # OnAttack window of ``_resolve_unit_combat``, so the choice lands in the
            # existing pre_attack continuation — before combat damage, which is what
            # "On Attack" means.
            if gctx.get("return_defender_upgrades"):
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=source_id,
                    target_instance_id=attacker.instance_id,
                    kind="return_defender_upgrades",
                    value={},
                    duration="this_attack",
                ))
            # "For this attack, you may deal its excess damage to another unit in the
            # same arena" (Wipe Them Out ASH_137) — Overwhelm's computation aimed at a
            # UNIT instead of the base, read at the tail of the combat pipeline.
            if gctx.get("excess_damage_to_unit"):
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=source_id,
                    target_instance_id=attacker.instance_id,
                    kind="excess_damage_to_unit",
                    value={},
                    duration="this_attack",
                ))
            # Support (ASH): "It gains this unit's other abilities for this attack."
            # ONE modifier naming the lender; the keyword layer and the trigger
            # collector read it through ``state.borrowed_ability_sources``, and it
            # lapses with the ordinary this_attack sweep.  Landed BEFORE the combat
            # pipeline runs, so a borrowed Raid/Overwhelm/Saboteur and a borrowed
            # "On Attack" trigger are all live from the declare step.
            lender_id = gctx.get("borrow_lender_id") or source_id
            if gctx.get("borrow_abilities") and lender_id != attacker.instance_id:
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=source_id,
                    target_instance_id=attacker.instance_id,
                    kind="borrowed_abilities",
                    value={"lender_id": lender_id},
                    duration="this_attack",
                ))

        needs_continuation: bool
        if self.defender_id is None:
            # Entrenched SOR_72: a unit barred from bases can't declare a base
            # attack (defensive guard; enumeration already omits the option).
            if granted is None and _cannot_attack_bases(s, attacker):
                raise IllegalActionError("This unit can't attack bases")
            needs_continuation = _resolve_base_attack(s, active_ps, inactive_ps, attacker)
        else:
            defender = _find_in_arenas(inactive_ps, self.defender_id)
            if defender is None:
                raise IllegalActionError(f"Defender {self.defender_id} not found")
            granted_cross = (granted is not None
                             and granted.context.get("cross_arena"))
            if (attacker.zone != defender.zone
                    and not _can_attack_other_arena(s, attacker)
                    and not granted_cross):
                raise IllegalActionError("Attacker and defender are in different arenas")
            # A defender debuff granted for this attack (Jyn Erso SOR_18: "Attack
            # with a unit.  The defender gets −1/−0 for this attack.") — applied
            # as a this_attack stats modifier on the chosen defender before the
            # combat pipeline computes its power.  Only for a unit defender.
            if granted is not None:
                from swu.engine.state import Modifier
                dp = int(granted.context.get("defender_power_bonus", 0) or 0)
                dh = int(granted.context.get("defender_hp_bonus", 0) or 0)
                # Swoop Down SHD_230: the defender debuff, like the attacker bonus,
                # applies only when attacking a GROUND unit.
                if (granted.context.get("bonus_if_defender_ground")
                        and defender.zone != Zone.GROUND_ARENA):
                    dp = dh = 0
                if dp or dh:
                    s.modifiers.append(Modifier(
                        modifier_id=s.alloc_modifier_id(),
                        source_instance_id=granted.context.get("source_id")
                        or attacker.instance_id,
                        target_instance_id=defender.instance_id,
                        kind="stats",
                        value={"power": dp, "hp": dh},
                        duration="this_attack",
                    ))
                # "If it attacks a unit, the defender loses all abilities for this
                # attack" (One Way Out SEC_157) — the modifier-backed arm of the
                # unified ``ability_suppressed`` read, scoped to this attack and
                # applied here, before the combat pipeline consults the defender's
                # keywords and triggers.  Only for a unit defender (a base has no
                # abilities to lose).
                if granted.context.get("defender_suppress_abilities"):
                    s.modifiers.append(Modifier(
                        modifier_id=s.alloc_modifier_id(),
                        source_instance_id=granted.context.get("source_id")
                        or attacker.instance_id,
                        target_instance_id=defender.instance_id,
                        kind="abilities_suppressed",
                        value={},
                        duration="this_attack",
                    ))
            needs_continuation = _resolve_unit_combat(s, active_ps, inactive_ps, attacker, defender)

        # Mon Mothma SEC_103: "attack with any number of other units (one at a
        # time)" — re-push the granted_attack so the controller may attack again
        # with a not-yet-attacked unit, until they decline or none remain.  Only
        # when the attack fully settled (no pre_attack continuation pending).
        if (granted is not None and granted.context.get("repeat")
                and not needs_continuation and not s.is_terminal()
                and not s.pending_decisions):
            new_ctx = dict(granted.context)
            new_ctx["already_attacked"] = (
                list(new_ctx.get("already_attacked") or []) + [self.attacker_id])
            # "up to N units": once N attacks have resolved, stop re-pushing
            # (Headhunting SHD_145).  ``repeat`` alone (Mon Mothma SEC_103) is an
            # unbounded "any number" and leaves repeat_max None.
            _rmax = new_ctx.get("repeat_max")
            capped = _rmax is not None and len(new_ctx["already_attacked"]) >= _rmax
            deciding_ps2 = s.active_player
            enemy_ps2 = s.inactive_player
            if not capped and _filter_granted_attacks(s, new_ctx, deciding_ps2, enemy_ps2):
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=granted.deciding_player_id,
                    kind="granted_attack",
                    context=new_ctx,
                    after_resolve_player_index=granted.after_resolve_player_index,
                ))
                s.active_player_index = s.player_index(granted.deciding_player_id)
                s.event_log.append(DecisionPushed(
                    deciding_player_id=granted.deciding_player_id,
                    kind="granted_attack",
                ))

        # Colonel Yularen SEC_6: "Attack with a unit.  Then, you may attack with
        # another unit that COSTS LESS THAN IT" — a one-shot follow-up whose cap is
        # read off the unit that just attacked (unlike ``repeat``, which re-pushes
        # the same context).  Optional, and the first attacker is excluded.
        if (granted is not None and granted.context.get("then_attack_cheaper")
                and not needs_continuation and not s.is_terminal()
                and not s.pending_decisions):
            first_cost = int(getattr(attacker.card_def, "cost", None) or 0)
            new_ctx = dict(granted.context)
            new_ctx.pop("then_attack_cheaper", None)
            new_ctx["optional"] = True
            new_ctx["attacker_cost_max"] = first_cost - 1
            new_ctx["already_attacked"] = (
                list(new_ctx.get("already_attacked") or []) + [self.attacker_id])
            if (first_cost > 0
                    and _filter_granted_attacks(s, new_ctx, s.active_player,
                                                s.inactive_player)):
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=granted.deciding_player_id,
                    kind="granted_attack",
                    context=new_ctx,
                    after_resolve_player_index=granted.after_resolve_player_index,
                ))
                s.active_player_index = s.player_index(granted.deciding_player_id)
                s.event_log.append(DecisionPushed(
                    deciding_player_id=granted.deciding_player_id,
                    kind="granted_attack",
                ))

        # Heroic Sacrifice SOR_150: the granted attacker "gains: 'When this unit
        # deals combat damage: Defeat it.'"  A +2/+0 attacker always deals combat
        # damage, so once the attack settles we defeat it (if it survived combat).
        if (base_damage_before is not None and not needs_continuation
                and not s.is_terminal()):
            hit_a_base = any(
                (ps.base_instance.damage if ps.base_instance is not None else 0)
                > base_damage_before.get(ps.player_id, 0)
                for ps in s.players)
            if hit_a_base and granted.context.get("draw_if_base_damaged"):
                _draw_cards(s, s.player_by_id(active_ps.player_id), 1)
            # "…if that unit damaged a base, defeat that unit" (LAW_205) — the
            # conditional twin of then_defeat_attacker below, sharing this snapshot.
            if hit_a_base and granted.context.get("defeat_attacker_if_base_damaged"):
                from swu.abilities.resolver import _apply_defeat_unit
                if _find_in_arenas(s.active_player, self.attacker_id) is not None:
                    _apply_defeat_unit(s, self.attacker_id)
            # "…gains: 'When Attack Ends: If this unit dealt combat damage to an
            # opponent's base, that opponent discards a card'" (Rash Action ASH_162).
            # An OPPONENT's base specifically, so it re-reads the same snapshot
            # rather than the any-base ``hit_a_base`` above; the discard is the
            # standing first-card simplification (K-2SO SOR_145).
            if granted.context.get("opponent_discard_if_base_damaged"):
                from swu.engine.state import Zone as _Zone
                for ps in s.players:
                    if ps.player_id == active_ps.player_id or ps.base_instance is None:
                        continue
                    if ps.base_instance.damage <= base_damage_before.get(
                            ps.player_id, 0):
                        continue
                    if not ps.hand:
                        continue
                    dropped = ps.hand.pop(0)
                    dropped.zone = _Zone.DISCARD
                    ps.discard.append(dropped)
                    note_hand_or_deck_discard(s, dropped)
                    record_hand_discard(s, ps.player_id)

        if (granted is not None and granted.context.get("then_defeat_attacker")
                and not needs_continuation):
            from swu.abilities.resolver import _apply_defeat_unit
            if _find_in_arenas(s.active_player, self.attacker_id) is not None:
                _apply_defeat_unit(s, self.attacker_id)

        if not needs_continuation and not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        if self.defender_id:
            return f"Attack unit {self.defender_id} with {self.attacker_id}"
        return f"Attack base with {self.attacker_id}"


# ── apply convenience wrapper ─────────────────────────────────────────────────

def record_hand_discard(s: GameState, player_id: str, kind: str = "discard") -> None:
    """Record that ``player_id`` revealed OR discarded 1+ cards from their hand in one
    instruction (the WhenYouRevealOrDiscard ledger; Padmé Amidala SEC_16).

    Call ONCE per reveal/discard instruction after the card(s) have moved, regardless
    of how many cards ("1 or more").  The declarative ``DiscardFromHand`` effect arm
    and the bespoke first-card hand-discard CustomEffects (Bail Organa SEC_198) route
    through here with the default ``kind="discard"``; the Disclose reveal path passes
    ``kind="reveal"``.  Both feed the reveal/discard ledger drained by
    ``_fire_reveal_discard_observers``; a true *discard* (kind="discard") ALSO feeds
    the discard-only ledger drained by ``_fire_hand_discard_observers`` (Migs Mayfeld
    SHD_163 — "when a player discards a card from their hand").  Purely additive: with
    neither observer card in play both drained ledgers fire nothing."""
    s.game_memory.hand_reveal_discards.append(player_id)
    if kind == "discard":
        s.game_memory.hand_discards.append(player_id)


def note_hand_or_deck_discard(s: GameState, ci: "CardInstance", *,
                              from_deck: bool = False) -> None:
    """Record that ``ci`` was discarded from a hand or deck this phase, feeding the
    phase-scoped ``cards_discarded_this_phase`` ledger read by Kylo's TIE Silencer
    SHD_135 ("If this unit was discarded from your hand or deck this phase, play it
    from your discard pile").

    Purely additive bookkeeping (only that one gate reads the set).  Call it at the
    self-discard / mill sites — the ``DiscardFromHand`` effect arm and the
    player-choice discard decisions (repeated_modal, discard_excess, the discard-a-
    hand-card decisions, Echo's discard-for-experience) plus the deck-search
    ``discard`` disposition.  Bespoke one-off discards that neither route through
    ``DiscardFromHand`` nor a discard decision are not marked (a documented
    simplification — the common enablers are covered).

    ``from_deck`` additionally queues the DECK-discard ledger read by the
    WhenYouDiscardFromDeck observer (Sebulba's Podracer LAW_176, "When you discard a
    card from your deck").  Pass it at the deck (mill / deck-search-discard) sites
    only; it defaults False, so a hand discard — which is most of the ~20 call sites —
    is unaffected.  The same documented simplification applies one level down: a
    bespoke card-module mill that does not route through ``discard_from_deck`` or a
    deck_search leaves the deck ledger alone, and simply does not fire the observer."""
    s.game_memory.cards_discarded_this_phase.add(ci.instance_id)
    # Beside the phase-scoped ledger, queue the card for the settle-drain that fires
    # its OWN "When this card is discarded from your hand or deck" observer (That's a
    # Rock LAW_206) — the note_unit_healed shape.  One entry per discarded card, so a
    # two-card mill fires the observer once per card that carries it.
    s.game_memory.self_discards.append(ci.instance_id)
    if from_deck:
        # The deck-only sibling, keyed by WHOSE deck was milled: the card came off the
        # top of its owner's deck, so the owner is the player who "discarded a card
        # from their deck" (a foreign deck_search mills the DECK OWNER's card into the
        # DECK OWNER's discard — Sabé SEC_17 — so this stays right there too).
        s.game_memory.deck_discards.append(ci.owner_id)


def note_token_unit_attacked(s: GameState, attacker: "CardInstance") -> None:
    """Record that ``attacker``'s controller declared an attack with a TOKEN unit
    this round, feeding ``game_memory.token_unit_attackers_this_round``.

    Called from the three attack-DECLARE steps beside the
    ``units_attacked_this_round`` write.  It records the CONTROLLER rather than the
    unit because the unit is the one thing that may not survive to be looked up: a
    defeated token ceases to exist (it is not discarded), so the usual
    ``find_instance`` re-read every other "attacked this phase" atom performs would
    silently lose it.  Gates Asajj Ventress TS26_7's "While you've attacked with a
    token unit this phase, this unit gets +2/+0"."""
    from swu.cards.models import TokenUnit
    if attacker is None or not isinstance(attacker.card_def, TokenUnit):
        return
    holder = s.find_instance(attacker.instance_id)
    pid = holder[0].player_id if holder is not None else attacker.owner_id
    s.game_memory.token_unit_attackers_this_round.add(pid)


def record_base_damage(s: GameState, base_owner_id: str, amount: int) -> None:
    """Record that ``base_owner_id``'s base was dealt ``amount`` damage, for the
    settle-point WhenDamageDealtToYourBase observer (The Daughter LOF_252).

    Called from the base-damage sinks (the base-attack pipeline and the ability
    damage sink); indirect damage a player assigns to their own base routes through
    the latter, so both paths are covered.  Zero-damage instances are not recorded —
    "when damage is dealt" needs damage."""
    if amount > 0:
        s.game_memory.base_damage_events.append(base_owner_id)
        # The standing, board-readable sibling of that drained queue: "If an enemy
        # base was damaged this phase" (Baylan Skoll ASH_39).
        s.game_memory.bases_damaged_this_phase.add(base_owner_id)


# ── Attack pipeline helpers ───────────────────────────────────────────────────

def _apply_restore(
    s: GameState, active_ps: PlayerState, n: int, source_name: str | None = None
) -> None:
    """Heal n damage from the attacking player's base (Restore N).

    ``source_name`` attributes the healing to the unit whose Restore keyword
    triggered it, so the log can read "… restores N (Restored ARC-170)."
    """
    base_ci = active_ps.base_instance
    if base_ci is None or _bases_cannot_heal(s):
        return
    healed = min(n, base_ci.damage)
    if healed > 0:
        base_ci.damage -= healed
        note_base_healed(s, base_ci, healed)
        s.event_log.append(RestoreHealing(
            player_id=active_ps.player_id, amount=healed, source_name=source_name,
        ))


def _combat_redirect_unit(
    s: GameState, active_ps: PlayerState, attacker: CardInstance
) -> Optional[CardInstance]:
    """The unit the attacker's incoming combat damage is redirected onto this attack
    (Maul SHD_90), or None.  The chosen unit is always friendly to the attacker
    ("another friendly Underworld unit"), so it is looked up in the attacker's
    controller's arenas; None if the flag is unset or the chosen unit has left play."""
    tid = getattr(attacker, "combat_damage_redirect_to", None)
    if not tid:
        return None
    return _find_in_arenas(active_ps, tid)


def _apply_attacker_combat_damage(
    s: GameState,
    active_ps: PlayerState,
    attacker: CardInstance,
    def_power: int,
    redirect: Optional[CardInstance],
    dealer_source_id: str | None = None,
) -> int:
    """Deal the defender's ``def_power`` combat damage to the attacker, unless an On
    Attack effect redirected it (Maul SHD_90): then it lands on the chosen unit
    (whose own Shield may intercept it) and the attacker takes none.  Returns the
    damage actually dealt to the ATTACKER (0 when redirected), so the attacker's
    "when combat damage is dealt to this unit" trigger correctly does not fire.  A
    redirect unit defeated by this damage is homed by the post-action defeat sweep."""
    if redirect is not None:
        _deal_damage_with_shield(s, active_ps, redirect, def_power, is_combat=True,
                                 dealer_source_id=dealer_source_id)
        return 0
    return _deal_damage_with_shield(s, active_ps, attacker, def_power, is_combat=True,
                                    dealer_source_id=dealer_source_id)


def _defender_deals_first(attacker: CardInstance) -> bool:
    """True if the attacker chose to let the defending unit deal combat damage before
    it does (The Stranger LAW_86: "While attacking, you may have the defending unit
    deal combat damage before this unit").  A this_attack flag set by the optional
    OnAttack CustomEffect and read only at the unit-combat damage step — the mirror
    of _attacker_has_first_strike's ordering."""
    return bool(getattr(attacker, "defender_deals_first", False))


def _snapshot_advantage_tokens(*combatants) -> frozenset:
    """The Advantage tokens on these combatants BEFORE the attack-end triggers run.

    Every pipeline fires its attack-end triggers and only then sweeps the Advantage
    tokens, so an ability that hands out a token AT that moment ("When Attack Ends:
    Give an Advantage token to this unit" — Bokken Saber ASH_180, Vane's Snub Fighter
    ASH_144) would have it taken straight back by the attack it was granted for.
    Snapshot first; ``_defeat_advantage_tokens_after_combat`` then sweeps only what
    the attack actually rode with, leaving anything created afterwards alone."""
    from swu.cards.models import TokenUpgrade
    ids = set()
    for ci in combatants:
        if ci is None:
            continue
        for u in ci.attached_upgrades:
            if (isinstance(u.card_def, TokenUpgrade)
                    and u.card_def.name == "Advantage"):
                ids.add(u.instance_id)
    return frozenset(ids)


def _defeat_advantage_tokens_after_combat(s: GameState, *combatants,
                                          only_ids: frozenset | None = None) -> None:
    """Shed every Advantage token from each combatant once the attack is over.

    "When attached unit's attack or defense ends: Defeat this upgrade" is printed on
    the Advantage token itself (ASH_2, the ASH set mechanic).  Enforced here — at the
    tail of all three combat pipelines, after damage and defeat processing so the
    +1/+0 still counted — rather than as a registered ability, the way Shield's
    damage-prevention rule already lives in the pipeline.

    ``only_ids`` is the pre-attack-end snapshot (see
    ``_snapshot_advantage_tokens``)."""
    from swu.engine.tokens import defeat_advantage_tokens
    for ci in combatants:
        if ci is None:
            continue
        defeat_advantage_tokens(s, ci, only_ids)


def _settle_defeat_after_attack(s: GameState, attacker: CardInstance) -> None:
    """""Defeat this unit after completing this attack" (Defiant Hammerhead LAW_62).

    A one-shot ``defeat_after_attack`` flag the attacker's own On Attack sets on
    itself, read here at the very end of each combat pipeline — just before the
    this-attack cleanup, and after the WhenAttackEnds fire, so "after completing
    this attack" is exact.  Cleared whether or not the defeat happens; if combat
    already defeated the attacker this is a clean no-op."""
    if not getattr(attacker, "defeat_after_attack", False):
        return
    attacker.defeat_after_attack = False
    if s.is_terminal() or s.find_instance(attacker.instance_id) is None:
        return
    from swu.abilities.resolver import _apply_defeat_unit
    _apply_defeat_unit(s, attacker.instance_id)


def _clear_this_attack_combat_flags(
    attacker: CardInstance, defender: Optional[CardInstance] = None
) -> None:
    """Reset the this_attack-scoped combat flags on an attacker at the end of its
    attack so neither leaks into a later attack: the Maul SHD_90 combat-damage
    redirect and the Stranger LAW_86 defender-deals-first choice.  Called at every
    attacker-in-scope this_attack cleanup site (both unit-combat step2 exits, the
    base-attack step2 end, and the defender-gone pre_attack fizzle) — closing the
    gap where a base attack or a fizzle previously left the redirect flag set.

    ``defender`` (unit-vs-unit sites only) additionally disarms the defender's
    combat-damage prevention flag — the protected unit may be the DEFENDER, whose
    flag would otherwise leak if the attacker left play before combat damage."""
    attacker.combat_damage_redirect_to = None
    attacker.defender_deals_first = False
    # Disarm any combat-damage prevention that was armed but never consumed (the
    # protected unit ended up taking no combat damage this attack — e.g. First Strike
    # defeated the striker first) so a stale flag cannot leak into a later attack.
    attacker.prevent_next_combat_damage = False
    if defender is not None:
        defender.prevent_next_combat_damage = False


# ── Internal helpers ──────────────────────────────────────────────────────────

def _attack_forbidden(state: GameState, attacker: CardInstance) -> bool:
    """True if ``attacker`` declares an ``AttackRestriction`` whose condition is
    currently False — i.e. it may not attack right now (Oggdo Bogdo LOF_63: "This
    unit can't attack unless it's damaged").  Read at the attack-enumeration seam;
    a no-op for the overwhelming majority of units (no such spec).

    An APPLIED restriction is honoured at the same seam: a ``cannot_attack``
    Modifier on the unit forbids attacking for its duration ("It can't attack for
    this phase" — Malevolence TWI_39).  Where ``AttackRestriction`` is a printed,
    condition-gated property of a card, this is a duration-scoped effect landed on
    a unit by someone else, and it expires with the ordinary modifier sweep."""
    for mod in state.modifiers:
        if (mod.kind == "cannot_attack"
                and mod.target_instance_id == attacker.instance_id):
            return True
    from swu.abilities.registry import get_abilities, AttackRestriction
    sc = getattr(attacker.card_def, "set_code", None) or ""
    cn = getattr(attacker.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    for spec in get_abilities(sc, cn):
        if isinstance(spec, AttackRestriction):
            # ``condition is None`` = the unconditional bar ("This unit can't
            # attack" — Corporate Defense Shuttle JTL_59).
            if spec.condition is None or not spec.condition.evaluate(state, attacker):
                return True
    return False


def _overwhelm_denied_by(state: GameState, defenders: list) -> bool:
    """Whether any unit DEFENDING this attack carries an upgrade with the
    ``AttackerLosesOverwhelm`` marker — "While attached unit is defending, the
    attacker loses Overwhelm" (Deadly Vulnerability ASH_150).

    Read at the two Overwhelm excess-spill steps, the only places the keyword does
    anything, because the keyword layer itself has no combat context and could not
    tell "while defending" from any other moment.  A no-op scan for a defender with
    no upgrades at all, which is most of them."""
    from swu.abilities.registry import get_abilities, AttackerLosesOverwhelm
    for d in defenders:
        if d is None:
            continue
        for up in getattr(d, "attached_upgrades", None) or ():
            sc = getattr(up.card_def, "set_code", None) or ""
            cn = getattr(up.card_def, "card_number", None) or ""
            if not sc or not cn:
                continue
            if any(isinstance(spec, AttackerLosesOverwhelm)
                   for spec in get_abilities(sc, cn)):
                return True
    return False


def _cannot_attack_bases(state: GameState, attacker: CardInstance) -> bool:
    """True if ``attacker`` carries a ``CannotAttackBases`` marker on its own card
    OR on any attached upgrade (Entrenched SOR_72: "Attached unit can't attack
    bases").  Read at the attack-enumeration seam to drop the base-attack option
    while leaving unit attacks intact; a no-op for the overwhelming majority of
    units (no such spec).

    Also honours the phase-scoped per-instance ledger
    ``game_memory.cannot_attack_bases_this_phase`` — the same bar granted by an
    effect rather than printed on a card ("They can't attack bases for this phase"
    — Scramble Fighters JTL_92).  Empty by default."""
    if attacker.instance_id in getattr(
            state.game_memory, "cannot_attack_bases_this_phase", ()):
        return True
    from swu.abilities.registry import get_abilities, CannotAttackBases
    for card_def in ([attacker.card_def]
                     + [u.card_def for u in attacker.attached_upgrades]):
        sc = getattr(card_def, "set_code", None) or ""
        cn = getattr(card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, CannotAttackBases):
                return True
    return False


def _can_attack_other_arena(state: GameState, attacker: CardInstance) -> bool:
    """True if ``attacker`` carries a ``CrossArenaAttack`` marker — it may attack
    enemy units in the OTHER arena, not only its own (Strafing Gunship SOR_212: "This
    unit can attack units in the ground arena").  Read at the attack-enumeration seam
    and the AttackWithUnit cross-arena apply-guard; a no-op for the overwhelming
    majority of units (no such spec).  Mirrors the ``_cannot_attack_bases`` scan."""
    from swu.abilities.registry import get_abilities, CrossArenaAttack
    sc = getattr(attacker.card_def, "set_code", None) or ""
    cn = getattr(attacker.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    for spec in get_abilities(sc, cn):
        if isinstance(spec, CrossArenaAttack):
            return True
    return False


def _attacker_has_first_strike(
    state: GameState, attacker: CardInstance, defender: CardInstance,
) -> bool:
    """True if ``attacker`` deals combat damage before ``defender`` this attack —
    either the innate First Strike keyword (Incinerator Trooper SHD_234) OR a
    registered ``ConditionalFirstStrike`` marker whose ``defender_spec`` the
    current defender satisfies (Hound's Tooth JTL_185: "While attacking an
    exhausted unit that didn't enter play this phase, …").  Read only at the
    unit-combat step; a plain ``has_keyword`` check for the overwhelming majority
    of attackers (no such marker)."""
    if has_keyword(state, attacker, Keyword.FIRST_STRIKE):
        return True
    from swu.abilities.registry import get_abilities, ConditionalFirstStrike
    sc = getattr(attacker.card_def, "set_code", None) or ""
    cn = getattr(attacker.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    from swu.abilities.resolver import _spec_matches_ci
    for spec in get_abilities(sc, cn):
        if isinstance(spec, ConditionalFirstStrike):
            cond = getattr(spec, "condition", None)
            if cond is not None and not cond.evaluate(state, attacker):
                continue  # "if no other units have attacked this phase" (LAW_219)
            if _spec_matches_ci(spec.defender_spec, defender, attacker, state, {}):
                return True
    return False


def _enumerate_attacks(
    state: GameState, ps: PlayerState, inactive_ps: PlayerState,
    *, include_exhausted: bool = False, cross_arena: bool = False,
) -> list["AttackWithUnit"]:
    """All legal AttackWithUnit actions for ps's ready units (Sentinel-aware).

    Shared by normal ACTION-phase legal_actions and by effect-granted attacks
    (e.g. Surprise Strike), so both honour the same targeting rules.

    ``include_exhausted`` also enumerates attacks for exhausted units (Mon Mothma
    SEC_103: "attack with any number of other units … even if those units are
    exhausted").
    """
    acts: list[AttackWithUnit] = []
    for attacker in ps.ground_arena + ps.space_arena:
        if attacker.exhausted and not include_exhausted:
            continue
        if _attack_forbidden(state, attacker):
            continue
        enemy_arena = list(
            inactive_ps.ground_arena
            if attacker.zone == Zone.GROUND_ARENA
            else inactive_ps.space_arena
        )
        # A cross-arena attacker (Strafing Gunship SOR_212) also reaches the OTHER
        # enemy arena's units — either by a printed marker or a decision-scoped
        # ``cross_arena`` grant (Swoop Down SHD_230).
        if cross_arena or _can_attack_other_arena(state, attacker):
            other = (inactive_ps.space_arena
                     if attacker.zone == Zone.GROUND_ARENA
                     else inactive_ps.ground_arena)
            enemy_arena = enemy_arena + list(other)
        saboteur = has_keyword(state, attacker, Keyword.SABOTEUR)
        # Hidden: a unit can't be attacked the phase it was played, so it is
        # removed from the eligible defenders entirely (Saboteur does not bypass
        # Hidden — only Sentinel).  Computing Sentinel over the attackable set
        # means a freshly-played Hidden Sentinel unit neither blocks nor forces.
        attackable = [u for u in enemy_arena
                      if not _is_hidden_from_attack(state, u)
                      and not _cannot_be_attacked(state, u)]
        sentinels = [u for u in attackable if has_keyword(state, u, Keyword.SENTINEL)]
        sentinel_required = bool(sentinels) and not saboteur

        for defender in attackable:
            if sentinel_required and not has_keyword(state, defender, Keyword.SENTINEL):
                continue  # must target Sentinel
            acts.append(AttackWithUnit(attacker.instance_id, defender.instance_id))

        # Can attack base only when Sentinel does not force a unit target and the
        # attacker isn't barred from bases (Entrenched SOR_72).
        if not sentinel_required and not _cannot_attack_bases(state, attacker):
            acts.append(AttackWithUnit(attacker.instance_id, None))
    return acts


def _is_hidden_from_attack(state: GameState, unit: CardInstance) -> bool:
    """Whether ``unit`` is currently protected by the Hidden keyword.

    Hidden ("This unit can't be attacked if it was played this phase") removes a
    unit from the legal defenders for the action phase in which it entered play.
    "Played this phase" is exactly ``game_memory.units_played_this_phase`` (the
    set every play path adds to in ``_put_unit_in_play``, cleared at the
    REGROUP→ACTION round rollover), so the protection lasts through that action
    phase and lifts on the next round.  Saboteur does not bypass Hidden.
    """
    if not has_keyword(state, unit, Keyword.HIDDEN):
        return False
    played = getattr(getattr(state, "game_memory", None),
                     "units_played_this_phase", set())
    return unit.instance_id in played


def _base_damager_aura(state: GameState, unit: CardInstance) -> bool:
    """True if ``unit``'s controller has an UNDEPLOYED card carrying
    ``CannotBeAttackedAfterDamagingBase`` (Cassian Andor SEC_12's undeployed side).

    Only the controller's ``base_zone`` is walked, which is what makes the aura
    undeployed-only for free — the mirror of the arena-scan convention that makes a
    leader's ``ConstantAbility`` deployed-only.  Called only after the cheap
    "damaged a base this phase" ledger test in ``_cannot_be_attacked``."""
    from swu.abilities.registry import (
        get_abilities, CannotBeAttackedAfterDamagingBase)
    found = state.find_instance(unit.instance_id)
    if found is None:
        return False
    for ci in found[0].base_zone:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        if any(isinstance(spec, CannotBeAttackedAfterDamagingBase)
               for spec in get_abilities(sc, cn)):
            return True
    return False


def _combat_power_after_block(state: GameState, unit: CardInstance, power: int) -> int:
    """``power``, or 0 while ``unit`` carries a ``cannot_deal_combat_damage``
    Modifier — "For this phase, that unit can't deal combat damage" (Betrayed Trust
    LAW_130).

    The dealer-side mirror of the ``damage_prevention`` modifier (which protects a
    RECEIVER): applied at the five points a combat pipeline turns a unit's effective
    power into an amount to deal, so it covers attacking a unit, attacking a base,
    striking back as the defender, and the multi-defender split alike, while leaving
    the unit's power itself — and therefore every "equal to its power" ability —
    untouched.  Expires with the ordinary duration sweep."""
    for mod in state.modifiers:
        if (mod.kind == "cannot_deal_combat_damage"
                and mod.target_instance_id == unit.instance_id):
            return 0
    return power


def _cannot_be_attacked(state: GameState, unit: CardInstance) -> bool:
    """True if ``unit`` currently can't be attacked — from either source, both of
    which yield to Sentinel:

      * an APPLIED ``cannot_be_attacked`` modifier ("Attached unit can't be attacked
        this phase (unless it has Sentinel)", On Top of Things TWI_219), which
        expires with the ordinary duration sweep; or
      * a printed ``CannotBeAttackedWhileExhausted`` marker while the unit is
        exhausted (Sabine Wren TWI_195); or
      * a ``CannotBeAttackedAfterDamagingBase`` aura its controller has undeployed,
        while the unit has damaged a base this phase (Cassian Andor SEC_12).

    The defender-side sibling of ``_is_hidden_from_attack``, applied at the same
    three attack-enumeration filters: such a unit drops out of the eligible-defender
    set, so it is neither attackable nor able to force/block as a Sentinel.  The
    Sentinel escape is printed on the card — "unless she gains Sentinel" — and it
    matters mechanically: a Sentinel that could not be attacked would make its whole
    arena unattackable.  A no-op for the overwhelming majority of units (no such
    spec); mirrors the ``_cannot_attack_bases`` scan."""
    for mod in state.modifiers:
        if (mod.kind == "cannot_be_attacked"
                and mod.target_instance_id == unit.instance_id):
            return not has_keyword(state, unit, Keyword.SENTINEL)
    # Cassian Andor SEC_12 (undeployed): the cheap ledger test comes FIRST, so the
    # aura scan never runs for a unit that has not damaged a base this phase.
    if (unit.instance_id in state.game_memory.units_dealt_base_damage_this_round
            and _base_damager_aura(state, unit)):
        return not has_keyword(state, unit, Keyword.SENTINEL)
    sc = getattr(unit.card_def, "set_code", None) or ""
    cn = getattr(unit.card_def, "card_number", None) or ""
    if not sc or not cn:
        return False
    from swu.abilities.registry import (
        get_abilities, CannotBeAttackedWhileExhausted, CannotBeAttacked)
    # ``while_ready`` flips the readiness test — "While this unit is READY, it can't
    # be attacked" (Muckraker Crab Droid SEC_135), the mirror of Sabine Wren TWI_195.
    specs = get_abilities(sc, cn)
    if any(isinstance(spec, CannotBeAttackedWhileExhausted)
           and bool(spec.while_ready) != bool(unit.exhausted)
           for spec in specs):
        return not has_keyword(state, unit, Keyword.SENTINEL)
    # The BOARD-gated sibling: "This unit can't be attacked while you control 2 or
    # more exhausted units" (Tatooine Repulsor Train ASH_35).  The condition is
    # evaluated against the unit itself, so "you" is its controller.
    for spec in specs:
        if isinstance(spec, CannotBeAttacked) and (
                spec.condition is None or spec.condition.evaluate(state, unit)):
            return not has_keyword(state, unit, Keyword.SENTINEL)
    return False


def _attacker_matches_predicates(
    attacker: Optional[CardInstance], predicates: list[str],
    state: Optional[GameState] = None,
) -> bool:
    """Whether ``attacker`` satisfies every TargetSpec predicate name in
    ``predicates`` (used to restrict a granted attack's eligible attacker, e.g.
    Desperate Attack: "damaged").  Mirrors the predicate checks in
    ``resolver._spec_matches_ci`` for the subset that makes sense for an attacker.

    ⚠️ An unknown predicate is IGNORED, not failed, so a filter this function does
    not implement silently offers every attacker — add the arm here as well as in
    the resolver whenever a card restricts a granted attack by a new predicate.
    ``state`` is needed only by the ledger-backed ones and may be omitted.
    """
    if attacker is None:
        return False
    for pred in predicates:
        if pred == "damaged" and attacker.damage == 0:
            return False
        if pred == "undamaged" and attacker.damage > 0:
            return False
        if pred == "exhausted" and not attacker.exhausted:
            return False
        if pred == "non_leader":
            from swu.cards.models import Leader
            if isinstance(attacker.card_def, Leader):
                return False
        if pred in ("token_unit", "non_token"):
            # "Attack with a TOKEN unit" (Asajj Ventress TS26_7).
            from swu.cards.models import TokenUnit
            is_token = isinstance(attacker.card_def, TokenUnit)
            if (pred == "token_unit") != is_token:
                return False
        if pred in ("unique", "non_unique"):
            # "Attack with up to 2 <uq> units" (Brothers TS26_59).
            is_uq = bool(getattr(attacker.card_def, "is_unique", False))
            if (pred == "unique") != is_uq:
                return False
        if pred == "played_this_phase":
            # "attack with 1 of them [the units that entered play this phase]"
            # (Padmé Amidala TS26_4) — the same ``units_played_this_phase`` set the
            # target-layer predicate of this name reads.
            played = getattr(getattr(state, "game_memory", None),
                             "units_played_this_phase", set()) or set()
            if attacker.instance_id not in played:
                return False
    return True


def _is_pilot_related(state: GameState, unit: Optional[CardInstance]) -> bool:
    """Whether ``unit`` is "a Pilot unit or a unit with a Pilot on it" (Leia
    Organa JTL_97) — it has the Pilot trait, or carries an attached upgrade that
    does (a pilot Unit, or a leader deployed as a Pilot upgrade)."""
    if unit is None:
        return False
    from swu.engine.traits import has_trait
    if has_trait(state, unit, "Pilot"):
        return True
    for up in getattr(unit, "attached_upgrades", None) or ():
        if "Pilot" in (getattr(up.card_def, "traits", ()) or ()):
            return True
    return False


def _filter_granted_attacks(
    state: GameState, ctx: dict, deciding_ps: PlayerState, enemy_ps: PlayerState
) -> list["AttackWithUnit"]:
    """The AttackWithUnit options a granted_attack decision offers, after applying
    every restriction recorded in its context.  Shared by the legal_actions
    granted_attack branch and the Mon Mothma SEC_103 repeat re-push, so both agree
    on eligibility.
    """
    attacks = list(_enumerate_attacks(
        state, deciding_ps, enemy_ps,
        include_exhausted=bool(ctx.get("allow_exhausted")),
        cross_arena=bool(ctx.get("cross_arena"))))
    # A restricted attacker (e.g. Desperate Attack: "Attack with a damaged unit").
    preds = ctx.get("attacker_predicates") or []
    if preds:
        attacks = [
            a for a in attacks
            if _attacker_matches_predicates(
                _find_in_arenas(deciding_ps, a.attacker_id), preds, state)
        ]
    # A trait-restricted attacker (Rebel Assault: "Attack with a REBEL unit").
    trait = ctx.get("attacker_trait")
    if trait:
        attacks = [
            a for a in attacks
            if trait in (getattr(
                getattr(_find_in_arenas(deciding_ps, a.attacker_id),
                        "card_def", None), "traits", ()) or ())
        ]
    # An aspect-restricted attacker (General Rieekan IBH_23: "another Heroism
    # unit" — Heroism is an aspect, not a trait).
    aspect = ctx.get("attacker_aspect")
    if aspect:
        attacks = [
            a for a in attacks
            if aspect in {
                asp.name for asp in (getattr(
                    getattr(_find_in_arenas(deciding_ps, a.attacker_id),
                            "card_def", None), "aspects", None) or ())
            }
        ]
    # A pinned attacker (Hotshot DL-44: "Attack with attached unit").
    pinned = ctx.get("attacker_id")
    if pinned:
        attacks = [a for a in attacks if a.attacker_id == pinned]
    # A cost-restricted attacker (Moff Gideon SHD_7: "a unit that costs 3 or less").
    cost_max = ctx.get("attacker_cost_max")
    if cost_max is not None:
        attacks = [
            a for a in attacks
            if (getattr(getattr(_find_in_arenas(deciding_ps, a.attacker_id),
                                "card_def", None), "cost", 0) or 0) <= cost_max
        ]
    # An arena-restricted attacker (Tandem Assault JTL_124: "Attack with a space
    # unit … attack with a ground unit").
    arena = ctx.get("attacker_arena")
    if arena:
        want = Zone.GROUND_ARENA if arena == "ground" else Zone.SPACE_ARENA
        attacks = [
            a for a in attacks
            if getattr(_find_in_arenas(deciding_ps, a.attacker_id), "zone", None) == want
        ]
    # A pilot-related attacker (Leia Organa JTL_97: "a Pilot unit or a unit with a
    # Pilot on it") — the attacker must have the Pilot trait or carry a Pilot
    # upgrade.
    if ctx.get("attacker_pilot_related"):
        attacks = [
            a for a in attacks
            if _is_pilot_related(state, _find_in_arenas(deciding_ps, a.attacker_id))
        ]
    # Mon Mothma SEC_103: "They can't attack bases for these attacks."
    if ctx.get("no_base"):
        attacks = [a for a in attacks if a.defender_id is not None]
    # Mon Mothma SEC_103: "attack with any number of *other* units" — exclude the
    # source itself.
    if ctx.get("exclude_source"):
        sid = ctx.get("source_id")
        attacks = [a for a in attacks if a.attacker_id != sid]
    # Mon Mothma SEC_103 repeat: a unit that has already attacked this grant is
    # not offered again (each of the "any number" units attacks at most once,
    # which also guarantees the loop terminates).
    already = ctx.get("already_attacked") or []
    if already:
        attacks = [a for a in attacks if a.attacker_id not in already]
    return attacks


# ── Interactive combat-damage prevention (Queen Amidala SEC_101) ────────────────

def _has_interactive_damage_prevention(state: GameState, ci: CardInstance) -> bool:
    """True if ``ci`` carries the InteractiveDamagePrevention marker (Amidala
    SEC_101).  A passive read, like ``_damage_prevented`` / ``_attack_forbidden``."""
    from swu.abilities.registry import get_abilities, InteractiveDamagePrevention
    sc = getattr(ci.card_def, "set_code", None) or ""
    cn = getattr(ci.card_def, "card_number", None) or ""
    return any(isinstance(sp, InteractiveDamagePrevention)
               for sp in get_abilities(sc, cn))


def _prevention_sacrifice_targets(state: GameState, protect_ci: CardInstance) -> list[str]:
    """Instance ids of the friendly units that could be defeated to prevent damage
    to ``protect_ci`` — "another friendly unit that shares a trait with this unit"
    (Amidala SEC_101).  Friendly = the same player who controls ``protect_ci``
    (its holding arena); effective traits (``get_traits``) so a granted trait counts.
    Recomputed from current state each time it is read (the decision may be resolved
    after the board changed)."""
    from swu.engine.traits import get_traits
    res = state.find_instance(protect_ci.instance_id)
    if res is None:
        return []
    ps, _ = res
    ptraits = set(get_traits(state, protect_ci))
    out: list[str] = []
    for u in ps.ground_arena + ps.space_arena:
        if u.instance_id == protect_ci.instance_id:
            continue
        if ptraits & set(get_traits(state, u)):
            out.append(u.instance_id)
    return out


def _armed_combat_preventions(
    s: GameState, active_ps: PlayerState, inactive_ps: PlayerState,
    attacker: CardInstance, defender: CardInstance,
) -> list[dict]:
    """Combatants (attacker and/or defender) that can invoke an interactive
    combat-damage prevention this attack: each carries the marker, would take >0
    unshielded combat damage, and has ≥1 eligible trait-sharing friendly to
    sacrifice.  Powers use the same combat calls as step2, so "would damage be
    dealt" matches what step2 will deal (a shield would absorb it, so a shielded
    unit is skipped — the prevention would be wasted)."""
    checks = [
        (defender, inactive_ps, compute_power(
            s, attacker, is_attacking=True, attacking_unit=True,
            defender_id=defender.instance_id)),
        (attacker, active_ps, compute_power(s, defender, is_attacking=False)),
    ]
    entries: list[dict] = []
    for protect_ci, protect_ps, incoming in checks:
        if incoming <= 0 or shields_on(protect_ci) > 0:
            continue
        if not _has_interactive_damage_prevention(s, protect_ci):
            continue
        if not _prevention_sacrifice_targets(s, protect_ci):
            continue
        entries.append({
            "protect_id": protect_ci.instance_id,
            "controller_id": protect_ps.player_id,
        })
    return entries


# ── Select-up-to-N units, give each a token push helper (Medal Ceremony) ──────

def _select_token_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible instance ids for the 'select_token' decision: units matching the
    stored spec criteria, minus those already chosen (recomputed from state).

    The source may have left play — e.g. a bounty (Public Enemy SHD_68 / Rich
    Reward SHD_261) whose host is defeated, so its instance is in limbo (mid
    ``_defeat_unit``) or in discard when this is called.  Since these bounty
    selects use ``controller="any"`` (no friendly/enemy or not_self filtering that
    needs the source's perspective), we gather directly from the arenas when the
    source can't be located.
    """
    from swu.abilities.resolver import _gather_legal_targets, _spec_matches_ci
    from swu.abilities.registry import TargetSpec
    spec = TargetSpec(
        controller=ctx.get("controller", "any"),
        kind=ctx.get("kind", "unit"),
        traits=tuple(ctx.get("traits", []) or ()),
        predicates=tuple(ctx.get("predicates", []) or ()),
        arena=ctx.get("arena"),
    )
    # ``allow_repeats`` turns the select-up-to-N loop into a DISTRIBUTION of a pool:
    # the same unit may be picked again, so "distribute up to 5 Advantage tokens
    # among other friendly units" (Elzar Mann ASH_224) can stack several on one unit.
    # ``exclude_ids`` is a caller-side filter and still applies.
    chosen = set(ctx.get("exclude_ids", []) or [])
    if not ctx.get("allow_repeats"):
        chosen |= set(ctx.get("chosen", []))
    source_result = state.find_instance(ctx["source_id"])
    if source_result is not None:
        _, source_ci = source_result
        ids = _gather_legal_targets(state, spec, source_ci, {})
    else:
        # Source gone (controller="any" only): each candidate is its own source.
        ids = [ci.instance_id
               for ps in state.players
               for ci in ps.ground_arena + ps.space_arena
               if _spec_matches_ci(spec, ci, ci, state, {})]
    ids = [tid for tid in ids if tid not in chosen]
    restrict = ctx.get("restrict_ids")
    if restrict:
        # Caller-computed whitelist, intersected AFTER the spec filter — "any number
        # of upgrades ON A UNIT" (Kit Fisto's Aethersprite LOF_147), where the host
        # unit is chosen first and only ITS upgrades may then be picked.  The
        # complement of ``exclude_ids``; absent = the original unrestricted pool.
        allow = set(restrict)
        ids = [tid for tid in ids if tid in allow]
    if ctx.get("shared_trait") and chosen:
        # "Choose up to 3 units that SHARE THE SAME TRAIT" (Bold Resistance
        # TWI_153): every pick after the first must keep a trait common to all
        # picks so far, so carry the running INTERSECTION of the chosen units'
        # effective traits (a TraitGrant counts) and admit only candidates that
        # still meet it.  The first pick is unconstrained — the "up to" lets a
        # single unit be the whole selection.
        from swu.engine.traits import get_traits
        common: Optional[set] = None
        for cid in chosen:
            res = state.find_instance(cid)
            if res is None:
                continue
            traits = set(get_traits(state, res[1]))
            common = traits if common is None else (common & traits)
        if common is not None:
            keep = []
            for tid in ids:
                res = state.find_instance(tid)
                if res is not None and (set(get_traits(state, res[1])) & common):
                    keep.append(tid)
            ids = keep
    return ids


def push_select_token(
    s: GameState, source_ci: CardInstance, *,
    token_type: Optional[str], max_targets: int,
    controller: str = "any", kind: str = "unit",
    traits: Optional[list[str]] = None,
    predicates: Optional[list[str]] = None,
    arena: Optional[str] = None,
    exclude_ids: Optional[list[str]] = None,
    decider_id: Optional[str] = None,
    after_resolve_idx: Optional[int] = None,
    power_bonus: int = 0, hp_bonus: int = 0,
    duration: str = "this_phase",
    shared_trait: bool = False,
    ready: bool = False,
    exhaust: bool = False,
    grant_keywords: Optional[list[str]] = None,
    suppress_abilities: bool = False,
    restrict_ids: Optional[list[str]] = None,
    defeat: bool = False,
    return_to_hand: bool = False,
    token_count: int = 1,
    then_credit_and_draw: bool = False,
    extra_token_type: Optional[str] = None,
    then_use_when_played: bool = False,
    mandatory: bool = False,
    then_pending_keyword: Optional[dict] = None,
    allow_repeats: bool = False,
    then_opponent_event_search: bool = False,
    then_draw_if_enemy_chosen: bool = False,
) -> None:
    """Push a 'select_token' decision: "Give a <token> to each of up to
    ``max_targets`` <filtered> units" (Medal Ceremony SOR_245).

    The controller's units are filtered by the spec criteria (controller / kind /
    traits / predicates — e.g. Rebel units with the ``attacked_this_phase``
    predicate); the controller then picks distinct units one at a time, each
    receiving a token, up to the cap (or stops early — the "up to").  Pushed only
    when at least one eligible unit exists, so the effect fizzles cleanly with no
    prompt otherwise.

    ``decider_id`` overrides who makes the choice (default: the source's
    controller).  This is needed for a bounty, where the OPPONENT of the dying
    unit's controller "collects" — the collector picks which units receive the
    tokens (Public Enemy SHD_68 Shield ×1, Rich Reward SHD_261 Experience ×2).
    ``after_resolve_idx`` overrides which player is active once the decision pops
    (default: the other player); a bounty firing mid-combat passes the active
    player so the attacker's turn resumes.

    ``power_bonus``/``hp_bonus``/``duration`` switch on BUFF mode: each chosen unit
    takes that stat modifier instead of (or as well as) a token, so the same
    select-up-to-N flow also models "Give each chosen unit +2/+2 for this phase"
    (Kalani TWI_85).  ``token_type=None`` = buff only.

    ``shared_trait`` narrows the candidates after each pick to units still sharing
    a trait with every unit chosen so far — "Choose up to 3 units that share the
    same Trait" (Bold Resistance TWI_153).

    ``ready`` readies each chosen unit and ``grant_keywords`` gives each one those
    keywords for ``duration`` — "Ready up to 3 units.  Each of those units gets
    +1/+0 and gains Overwhelm for this phase" (Planetary Invasion TWI_178).

    ``suppress_abilities`` makes each chosen unit lose all abilities for the round
    (the ``abilities_suppressed`` read-layer flag, lifted at the round rollover) —
    "Choose any number of friendly units.  They lose all abilities for this round"
    (Kazuda Xiono JTL_18), where "any number" is just ``max_targets`` set to the
    count of eligible units by the caller.

    ``restrict_ids`` whitelists the pool (intersected after the spec filter) and
    ``defeat`` switches on DEFEAT mode — together they give "You may defeat any
    number of upgrades on a unit" (Kit Fisto's Aethersprite LOF_147): the caller
    picks the host unit first, passes its non-token upgrades as the whitelist with
    ``kind="upgrade"``, and "any number" is again ``max_targets`` = that count.
    Unlike every other payoff here, the defeats are applied in
    ``_resolve_select_token`` — i.e. AFTER the decision is popped — because a defeat
    pushes its own triggers synchronously and must not run under this decision.

    ``mandatory`` withholds the early ``FinishSelectToken`` while a legal pick
    remains, for a clause with no "up to" — "An opponent gives 2 Advantage tokens to
    a unit they control" (Sabine Wren ASH_6), which the opponent must do if able.
    (The finish is still offered once nothing is eligible, so legal_actions is never
    empty.)  ``then_pending_keyword`` is that card's "If they do" payoff: a
    ``pending_keyword_grants`` entry (the Deceptive Shade LOF_180 ledger) armed for
    the SOURCE's controller — never the decider — and only when at least one unit was
    really chosen.
    """
    decider = decider_id or source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": decider,
        "token_type": token_type,
        "power_bonus": int(power_bonus),
        "hp_bonus": int(hp_bonus),
        "duration": duration,
        "remaining": int(max_targets),
        "controller": controller,
        "kind": kind,
        "traits": list(traits or []),
        "predicates": list(predicates or []),
        # "a unit in a DIFFERENT arena" (Lando Calrissian JTL_3 deployed as an
        # upgrade) — the caller computes the arena from the source's host and
        # passes it through, exactly like the TargetSpec field of the same name.
        "arena": arena,
        # Instances barred from the choice — "give ANOTHER unit +1/+0" relative to
        # a unit the caller just played (Major Vonreg JTL_11).
        "exclude_ids": list(exclude_ids or []),
        "shared_trait": bool(shared_trait),
        "ready": bool(ready),
        # EXHAUST mode: the mirror of ``ready`` — "For each friendly Official unit,
        # exhaust an enemy unit" (No One Ever Knew SEC_196).
        "exhaust": bool(exhaust),
        "grant_keywords": list(grant_keywords or []),
        "suppress_abilities": bool(suppress_abilities),
        "restrict_ids": list(restrict_ids) if restrict_ids is not None else None,
        "defeat": bool(defeat),
        # RETURN mode — the ``defeat`` sibling: each chosen card goes to its owner's
        # hand instead (Force Speed LOF_205), applied after the pop for the same
        # reason.
        "return_to_hand": bool(return_to_hand),
        # A PER-DEFEAT payoff on DEFEAT mode: "For each unit defeated this way,
        # create a Credit token and draw a card" (Tobias Beckett LAW_2).  Counted
        # from the defeats that actually happened at the resolve point (a pick that
        # a chained defeat already took does not pay), the TWI_239 "read off what is
        # really gone" rule.
        "then_credit_and_draw": bool(then_credit_and_draw),
        "token_count": int(token_count),
        # A second token of a DIFFERENT kind per chosen unit (The Ghost LAW_69).
        "extra_token_type": extra_token_type,
        # "Use any number of 'When Played' abilities on friendly Spectre units"
        # (Fire Across the Galaxy LAW_256) — a payoff settled AFTER the pop, like
        # ``defeat``/``return_to_hand``: each chosen unit's registered When Played
        # abilities are pushed as fresh ``resolve_effects`` decisions.
        "then_use_when_played": bool(then_use_when_played),
        # "An opponent GIVES 2 Advantage tokens to a unit they control" (Sabine Wren
        # ASH_6) — no "up to", so no early finish while a pick is available; and its
        # "If they do" payoff, armed for the SOURCE's controller at the resolve.
        "mandatory": bool(mandatory),
        "then_pending_keyword": dict(then_pending_keyword or {}) or None,
        # DISTRIBUTION mode: a picked unit stays pickable, so ``max_targets`` is a
        # POOL rather than a headcount — "Distribute up to 5 Advantage tokens among
        # other friendly units" (Elzar Mann ASH_224).
        "allow_repeats": bool(allow_repeats),
        # ASH_224's rider, settled at the resolve: an opponent searches TWICE the
        # number of tokens actually distributed for an event and draws it.
        "then_opponent_event_search": bool(then_opponent_event_search),
        # Secret Marriage TS26_46's rider: draw a card if any chosen unit was an
        # ENEMY one, settled at the resolve when the picks are known.
        "then_draw_if_enemy_chosen": bool(then_draw_if_enemy_chosen),
        "source_controller_id": source_ci.owner_id,
        "chosen": [],
    }
    if int(max_targets) <= 0 or not _select_token_targets(s, ctx):
        return
    decider_idx = s.player_index(decider)
    after_idx = after_resolve_idx if after_resolve_idx is not None else 1 - decider_idx
    dec = PendingDecision(
        deciding_player_id=decider,
        kind="select_token",
        context=ctx,
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = decider_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider,
        kind="select_token",
    ))


# ── select_damage: deal 1 damage to each of up to N units (IG-2000 JTL_140) ─

def _select_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible instance ids for the 'select_damage' decision: any arena unit,
    minus those already chosen.

    Two optional ctx narrowings (both absent = the original any-unit behaviour):
    ``arena`` restricts to one arena ("up to 2 units in this arena" — Twin Laser
    Turret JTL_172) and ``enemy_of`` restricts to units controlled by the OTHER
    player ("a different enemy unit" — Hotshot Maneuver JTL_174)."""
    chosen = set(ctx.get("chosen", []))
    arena = ctx.get("arena")
    enemy_of = ctx.get("enemy_of")
    # "each of up to N OTHER units" (AAT Incinerator SEC_169) — the source itself is
    # never an eligible target.
    if ctx.get("exclude_source"):
        chosen.add(ctx["source_id"])
    targets: list[str] = []
    for ps in state.players:
        if enemy_of is not None and ps.player_id == enemy_of:
            continue
        arenas = []
        if arena != "space":
            arenas.append(ps.ground_arena)
        if arena != "ground":
            arenas.append(ps.space_arena)
        for lst in arenas:
            for u in lst:
                if u.instance_id not in chosen:
                    targets.append(u.instance_id)
    return targets


def push_select_damage(
    s: GameState, source_ci: CardInstance, *,
    amount_each: int = 1, max_targets: int,
    decider_id: Optional[str] = None,
    after_resolve_idx: Optional[int] = None,
    arena: Optional[str] = None,
    enemy_only: bool = False,
    then_attack_with: Optional[str] = None,
    exclude_source: bool = False,
    then_self_base_damage_if_no_friendly_hit: int = 0,
) -> None:
    """Push a 'select_damage' decision: "Deal ``amount_each`` damage to each of
    up to ``max_targets`` units" (IG-2000 JTL_140).

    The deciding player picks distinct units one at a time; each is recorded.
    After finishing (or reaching the cap), the decision is popped and damage is
    dealt to all chosen targets ("pop, then deal" — so a defeat trigger lands on a
    clean stack).  Pushed only when at least one unit is in play.

    ``decider_id`` overrides who makes the choice (default: the source's
    controller) — needed for a bounty "Deal N damage to a unit", where the
    COLLECTOR (the opponent of the dying unit's controller) picks the target
    (Val SHD_58, Wanted Insurgents SHD_167).  ``after_resolve_idx`` overrides
    which player is active once the decision pops (default: the other player); a
    bounty firing mid-combat passes the active player so the turn resumes.

    ``arena`` narrows the eligible units to one arena ("each of up to 2 units in
    this arena" — Twin Laser Turret JTL_172); ``enemy_only`` narrows them to the
    decider's opponent ("a different enemy unit" — Hotshot Maneuver JTL_174).
    ``then_attack_with`` is the "Then, attack with the chosen unit" rider (JTL_174):
    the named unit's ``granted_attack`` is pushed at RESOLVE, so the damage lands
    first and the attack decision arrives on a clean stack (pushing both up front
    would resolve them in the wrong, LIFO, order).
    """
    ctx: dict = {
        "source_id": source_ci.instance_id,
        "amount_each": int(amount_each),
        "remaining": int(max_targets),
        "chosen": [],
    }
    if arena is not None:
        ctx["arena"] = arena
    if enemy_only:
        ctx["enemy_of"] = decider_id or source_ci.owner_id
    if then_attack_with is not None:
        ctx["then_attack_with"] = then_attack_with
    if exclude_source:
        ctx["exclude_source"] = True
    if then_self_base_damage_if_no_friendly_hit:
        ctx["self_base_damage_if_no_friendly_hit"] = int(
            then_self_base_damage_if_no_friendly_hit)
    if int(max_targets) <= 0 or not _select_damage_targets(s, ctx):
        return
    decider = decider_id or source_ci.owner_id
    decider_idx = s.player_index(decider)
    after_idx = after_resolve_idx if after_resolve_idx is not None else 1 - decider_idx
    dec = PendingDecision(
        deciding_player_id=decider,
        kind="select_damage",
        context=ctx,
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = decider_idx
    s.event_log.append(DecisionPushed(deciding_player_id=decider, kind="select_damage"))


# ── Credit-token economy (jabba-the-hutt:07) ───────────────────────────────────

def _resolve_base_attack(
    s: GameState,
    active_ps: PlayerState,
    inactive_ps: PlayerState,
    attacker: CardInstance,
) -> bool:
    """CR attack steps for unit-vs-base.

    Returns True if a pre_attack decision was pushed (callers must not
    call _switch_active_player in that case).
    """
    base_ci = inactive_ps.base_instance
    if base_ci is None:
        return False

    # Step 1: Declare
    attacker.exhausted = True
    evt = AttackDeclared(
        attacker_player_id=active_ps.player_id,
        attacker_instance_id=attacker.instance_id,
        attacker_name=attacker.card_def.display_name,
        defender_instance_id=None,
        defender_name=base_ci.card_def.display_name,
    )
    s.event_log.append(evt)
    get_bus().fire(s, evt)
    s.game_memory.units_attacked_this_round.add(attacker.instance_id)
    note_token_unit_attacked(s, attacker)
    s.game_memory.base_attackers_this_round.setdefault(
        inactive_ps.player_id, []).append(attacker.instance_id)

    # Phase 3: collect OnAttack ability triggers
    decisions_before = len(s.pending_decisions)
    from swu.abilities.resolver import fire_triggered_abilities
    event_ctx = {
        "attacker_id": attacker.instance_id,
        "defender_id": None,
    }
    s = fire_triggered_abilities(s, evt, after_all_player_idx=s.active_player_index, event_ctx=event_ctx)
    if len(s.pending_decisions) > decisions_before:
        # OnAttack triggers need choices — push pre_attack continuation below them
        pre_attack = PendingDecision(
            deciding_player_id=active_ps.player_id,
            kind="pre_attack",
            context={
                "attacker_id": attacker.instance_id,
                "defender_id": None,
                "active_player_id": active_ps.player_id,
            },
            after_resolve_player_index=1 - s.player_index(active_ps.player_id),
        )
        s.pending_decisions.insert(decisions_before, pre_attack)
        return True

    _resolve_base_attack_step2(s, active_ps, inactive_ps, attacker)
    return False


def _resolve_base_attack_step2(
    s: GameState,
    active_ps: PlayerState,
    inactive_ps: PlayerState,
    attacker: CardInstance,
) -> None:
    """Steps 2–5 of the base attack pipeline (Restore, power, damage, win check)."""
    base_ci = inactive_ps.base_instance
    if base_ci is None:
        return

    # Step 2: On-attack triggers
    if has_keyword(s, attacker, Keyword.RESTORE):
        n = keyword_value(s, attacker, Keyword.RESTORE)
        if n > 0:
            _apply_restore(s, active_ps, n, attacker.card_def.display_name)

    # Step 3: Effective power.  ``attacking_base=True`` enables a "while attacking a
    # base" debuff (Sly Moore SEC_33) to contribute here and only here.
    power = compute_power(s, attacker, is_attacking=True, attacking_base=True)
    power = _combat_power_after_block(s, attacker, power)   # LAW_130

    # Step 4: Damage to base
    power = base_damage_after_prevention(s, base_ci, power)
    base_ci.damage += power
    if power > 0:
        # Record that this attacker dealt damage to a base this round (gates
        # Retaliation SEC_77 "Defeat a unit that dealt damage to a base this
        # phase").  Only the direct base-attack site is tracked (the common case);
        # Overwhelm spillover to a base is a documented uncovered edge.
        s.game_memory.units_dealt_base_damage_this_round.add(attacker.instance_id)
        # Accumulate this player's total base damage this phase (Cassian Andor
        # SOR_13's undeployed "3 or more damage to an enemy base this phase"); the
        # defending base is always an enemy base at this direct-attack site.
        gm = s.game_memory
        gm.base_damage_dealt_this_phase[active_ps.player_id] = (
            gm.base_damage_dealt_this_phase.get(active_ps.player_id, 0) + power)
    s.event_log.append(DamageDealt(
        target_instance_id=base_ci.instance_id,
        target_name=base_ci.card_def.display_name,
        owner_id=inactive_ps.player_id,
        amount=power,
        is_base=True,
    ))
    record_base_damage(s, inactive_ps.player_id, power)

    # Step 5: Win check
    _check_game_over(s)

    # The Advantage tokens this attack actually rode with — snapshotted before any
    # attack-end trigger can hand out another one (ASH_180 / ASH_144).
    adv_snapshot = _snapshot_advantage_tokens(attacker)

    # "When this unit deals combat damage to a base" triggers (Ketsu Onyo
    # SHD_147).  Flagged in event_ctx (mirroring OnAttackDefeatsUnit); the attack
    # survives a base attack, so the attacker is still in play.  after_all_player
    # is the opponent so the turn passes once the (optional) trigger resolves —
    # the attacking action otherwise switches at AttackWithUnit/ContinueAttack,
    # but that switch is suspended while a decision is pending.
    if not s.is_terminal() and power > 0:
        from swu.abilities.resolver import fire_triggered_abilities
        opp_idx = s.player_index(inactive_ps.player_id)
        fire_triggered_abilities(
            s, None,
            after_all_player_idx=opp_idx,
            event_ctx={"dealt_combat_damage_to_base": attacker.instance_id,
                       # How much was dealt, so an observer can gate on a threshold
                       # (Temple of Destruction LOF_25, min_amount=3).
                       "base_combat_damage_amount": power},
        )

    # "When Attack Ends: If this unit survived" (Vermillion LAW_215).  A base
    # attack never damages the attacker, so it always survives; fire if still in
    # play and the game is not already over.  after_all is the opponent so the
    # turn passes once the resulting decision resolves.
    if not s.is_terminal() and _find_in_arenas(active_ps, attacker.instance_id) is not None:
        from swu.abilities.resolver import fire_triggered_abilities as _fire_end
        # ``attack_ended_attacker`` rides along so the WhenFriendlyUnitAttackEnds
        # observer (Anakin Skywalker LAW_88) also sees a BASE attack end — "when a
        # friendly unit's attack ends" draws no unit/base distinction.  A base attack
        # never damages the attacker, so this guarded site is the whole story here;
        # no defeated-defender key, so LAW_7's "If the defending unit was defeated"
        # reading correctly never fires on a base attack.
        end_ctx = {"attack_ended_survivor": attacker.instance_id,
                   "attack_ended_attacker": attacker.instance_id}
        if power > 0:
            # Also mark that this attack dealt combat damage to a base, so a
            # WhenAttackEnds(require_base_damage=True) trigger fires here (Maul
            # LAW_54); a unit-vs-unit attack never sets this key.  A DISTINCT key
            # (not dealt_combat_damage_to_base) so this fire does not re-match a
            # WhenDealsCombatDamageToBase trigger (Ketsu Onyo SHD_147), which the
            # earlier dedicated fire already handled.
            end_ctx["attack_ended_base_damage"] = attacker.instance_id
            # HOW MUCH, so an observer can gate on a threshold ("If it dealt 3 or
            # more combat damage to a base" — Ezra Bridger ASH_13) or scale off it
            # (Hera Syndulla ASH_31, Shin Hati ASH_16).
            end_ctx["attack_ended_base_damage_amount"] = power
        _fire_end(
            s, None,
            after_all_player_idx=s.player_index(inactive_ps.player_id),
            event_ctx=end_ctx,
        )

    _settle_defeat_after_attack(s, attacker)   # "… defeat this unit" (LAW_62)
    # "When attached unit's attack … ends: Defeat this upgrade" — the Advantage token
    # (ASH_2).  A base attack has no defender, so only the attacker sheds them.
    _defeat_advantage_tokens_after_combat(s, attacker, only_ids=adv_snapshot)
    # Clean up this-attack modifiers + the this-attack combat flags (a base attack
    # never reads them, but the attacker may have set one before choosing a base —
    # clear so it doesn't leak into a later attack).
    _clear_this_attack_combat_flags(attacker)
    _expire_modifiers(s, "this_attack")


def _push_granted_attack_on_attack(s: GameState, attacker: CardInstance,
                                   defender: CardInstance) -> None:
    """Resolve any attack-scoped granted "On Attack" ability marked on ``attacker``.

    Today the only one is Force Speed LOF_205's ``return_defender_upgrades``: "Return
    any number of non-unique upgrades attached to the defender to their owners'
    hands."  The choice is the ``select_token`` decision in RETURN mode, whitelisted
    to exactly those upgrades — "any number" being ``max_targets`` = that count plus
    the always-available finish (the Kit Fisto's Aethersprite LOF_147 shape)."""
    from swu.cards.models import TokenUpgrade
    if not any(m.target_instance_id == attacker.instance_id
               and m.kind == "return_defender_upgrades"
               for m in getattr(s, "modifiers", [])):
        return
    ids = [u.instance_id for u in defender.attached_upgrades
           if not isinstance(u.card_def, TokenUpgrade)
           and not getattr(u.card_def, "is_unique", False)]
    if not ids:
        return
    push_select_token(
        s, attacker, token_type=None, max_targets=len(ids),
        controller="any", kind="upgrade", restrict_ids=ids,
        return_to_hand=True, decider_id=attacker.owner_id,
    )


def _resolve_unit_combat(
    s: GameState,
    active_ps: PlayerState,
    inactive_ps: PlayerState,
    attacker: CardInstance,
    defender: CardInstance,
) -> bool:
    """Full CR attack pipeline for unit-vs-unit combat.

    Returns True if a pre_attack decision was pushed (callers must not
    call _switch_active_player in that case).
    """
    # Step 1: Declare
    attacker.exhausted = True
    # Sentinel forces the target: if the defender has Sentinel (and the attacker
    # is not a Saboteur, which ignores it), the base and any non-Sentinel enemy
    # units were not legal targets — flag it so the UI can explain the forced pick.
    forced_by_sentinel = (
        has_keyword(s, defender, Keyword.SENTINEL)
        and not has_keyword(s, attacker, Keyword.SABOTEUR)
    )
    evt = AttackDeclared(
        attacker_player_id=active_ps.player_id,
        attacker_instance_id=attacker.instance_id,
        attacker_name=attacker.card_def.display_name,
        defender_instance_id=defender.instance_id,
        defender_name=defender.card_def.display_name,
        forced_by_sentinel=forced_by_sentinel,
    )
    s.event_log.append(evt)
    get_bus().fire(s, evt)
    s.game_memory.units_attacked_this_round.add(attacker.instance_id)
    note_token_unit_attacked(s, attacker)

    # Phase 3: collect OnAttack ability triggers
    decisions_before = len(s.pending_decisions)
    from swu.abilities.resolver import fire_triggered_abilities
    event_ctx = {
        "attacker_id": attacker.instance_id,
        "defender_id": defender.instance_id,
    }
    s = fire_triggered_abilities(s, evt, after_all_player_idx=s.active_player_index, event_ctx=event_ctx)
    # An attack-scoped granted "On Attack" ability, marked on the attacker by the
    # granted_attack rider (Force Speed LOF_205).  Pushed inside this window so it
    # rides the same pre_attack continuation as a printed OnAttack trigger — i.e. it
    # resolves before combat damage.
    _push_granted_attack_on_attack(s, attacker, defender)
    trigger_pushed = len(s.pending_decisions) > decisions_before
    # Interactive combat-damage prevention checkpoint (Queen Amidala SEC_101): may
    # arm a combat_damage_prevention decision for a marked combatant that would take
    # combat damage this attack (see _armed_combat_preventions).
    armed = _armed_combat_preventions(s, active_ps, inactive_ps, attacker, defender)
    if trigger_pushed or armed:
        # Push the pre_attack continuation below any OnAttack-trigger decisions.  Any
        # prevention decisions sit just ABOVE it (decisions_before+1) so they resolve
        # after the trigger decisions and immediately before ContinueAttack resumes
        # step2 with the prevention flag already armed.
        pre_attack = PendingDecision(
            deciding_player_id=active_ps.player_id,
            kind="pre_attack",
            context={
                "attacker_id": attacker.instance_id,
                "defender_id": defender.instance_id,
                "active_player_id": active_ps.player_id,
            },
            after_resolve_player_index=1 - s.player_index(active_ps.player_id),
        )
        s.pending_decisions.insert(decisions_before, pre_attack)
        for entry in armed:
            s.pending_decisions.insert(decisions_before + 1, PendingDecision(
                deciding_player_id=entry["controller_id"],
                kind="combat_damage_prevention",
                context={"protect_id": entry["protect_id"],
                         "controller_id": entry["controller_id"]},
                after_resolve_player_index=1 - s.player_index(active_ps.player_id),
            ))
            s.event_log.append(DecisionPushed(
                deciding_player_id=entry["controller_id"],
                kind="combat_damage_prevention"))
        if not trigger_pushed and armed:
            # No OnAttack-trigger decision on top — hand the turn to the prevention
            # decision's decider (the protected unit's controller).
            top = s.pending_decisions[-1]
            s.active_player_index = s.player_index(top.deciding_player_id)
        return True

    _resolve_unit_combat_step2(s, active_ps, inactive_ps, attacker, defender)
    return False


def _resolve_unit_combat_step2(
    s: GameState,
    active_ps: PlayerState,
    inactive_ps: PlayerState,
    attacker: CardInstance,
    defender: CardInstance,
) -> None:
    """Steps 2–6 of unit-vs-unit combat (on-attack keywords through defeat)."""
    # Step 2: On-attack keyword triggers
    if has_keyword(s, attacker, Keyword.RESTORE):
        n = keyword_value(s, attacker, Keyword.RESTORE)
        if n > 0:
            _apply_restore(s, active_ps, n, attacker.card_def.display_name)

    if has_keyword(s, attacker, Keyword.SABOTEUR):
        while shields_on(defender) > 0:
            defeat_shield(s, defender)

    # Combat damage is exchanged only between units that are both still in play.
    # An OnAttack ability resolved before this step may have already removed the
    # defender (e.g. Fennec Shand SHD_220 deals lethal damage to the defender on
    # attack) or the attacker; in that case the resolved defeat stands and we
    # must NOT deal damage to / re-defeat a dangling reference, which would
    # double-home the same instance into discard (a card-conservation break).
    if (_find_in_arenas(active_ps, attacker.instance_id) is None
            or _find_in_arenas(inactive_ps, defender.instance_id) is None):
        _clear_this_attack_combat_flags(attacker, defender)
        _expire_modifiers(s, "this_attack")
        return

    # Step 3: Effective power (computed AFTER on-attack trigger resolution).
    # ``attacking_unit=True`` enables "while attacking an enemy unit" buffs
    # (Moff Gideon SHD_7) for the attacker — this path is always a unit attack.
    # ``defender_id`` enables the defender's "while defending, the attacker gets
    # −1/−0" debuff (Lando Calrissian LAW_108) to land on this attacker only.
    atk_power = compute_power(s, attacker, is_attacking=True, attacking_unit=True,
                              defender_id=defender.instance_id)
    atk_power = _combat_power_after_block(s, attacker, atk_power)   # LAW_130
    # ``attacker_id`` enables an attacker's "while THIS unit is attacking, the
    # defender gets −N/−0" debuff (Strafing Gunship SOR_212) to land on this
    # defender only.
    def_power = compute_power(s, defender, is_attacking=False, is_defending=True,
                              attacker_id=attacker.instance_id)
    def_power = _combat_power_after_block(s, defender, def_power)   # LAW_130

    # Step 4: damage with Shield interception.  An On Attack effect may have
    # redirected the attacker's incoming combat damage onto a chosen friendly unit
    # (Maul SHD_90) — resolved via _apply_attacker_combat_damage.
    defender_hp_before = compute_hp(s, defender) - defender.damage
    # The arena this attack happens in, snapshotted BEFORE any defeat moves a
    # combatant out of it (Wipe Them Out ASH_137's "in the same arena").
    combat_arena = "ground" if defender.zone == Zone.GROUND_ARENA else "space"
    redirect = _combat_redirect_unit(s, active_ps, attacker)

    if _attacker_has_first_strike(s, attacker, defender):
        # First Strike: the attacker deals its damage first; if that defeats the
        # defender, the defender deals no combat damage back.
        dealt_to_defender = _deal_damage_with_shield(s, inactive_ps, defender, atk_power,
                                                     is_combat=True,
                                                     dealer_source_id=attacker.instance_id)
        if _hp_lethal(s, defender):
            dealt_to_attacker = 0
        else:
            dealt_to_attacker = _apply_attacker_combat_damage(
                s, active_ps, attacker, def_power, redirect, defender.instance_id)
    elif _defender_deals_first(attacker):
        # The Stranger LAW_86: the attacker chose to let the defender strike first —
        # the mirror of First Strike.  The defender deals its combat damage to the
        # attacker first (a redirect still applies via _apply_attacker_combat_damage);
        # if that defeats the attacker, the attacker deals no combat damage back.
        dealt_to_attacker = _apply_attacker_combat_damage(
            s, active_ps, attacker, def_power, redirect, defender.instance_id)
        if _hp_lethal(s, attacker):
            dealt_to_defender = 0
        else:
            # Recompute the attacker's power AFTER it takes the defender's hit, so a
            # Grit attacker's combat damage grows from that damage before it swings
            # back (The Stranger's Grit is the reason to choose defender-first).
            atk_power = compute_power(s, attacker, is_attacking=True, attacking_unit=True,
                                      defender_id=defender.instance_id)
            atk_power = _combat_power_after_block(s, attacker, atk_power)   # LAW_130
            dealt_to_defender = _deal_damage_with_shield(s, inactive_ps, defender, atk_power,
                                                     is_combat=True,
                                                     dealer_source_id=attacker.instance_id)
    else:
        # Normal: simultaneous damage.
        dealt_to_defender = _deal_damage_with_shield(s, inactive_ps, defender, atk_power,
                                                     is_combat=True,
                                                     dealer_source_id=attacker.instance_id)
        dealt_to_attacker = _apply_attacker_combat_damage(
            s, active_ps, attacker, def_power, redirect, defender.instance_id)

    # Step 5: Overwhelm.  ``spill_to_base`` is the combat damage this attack put on
    # the defending BASE — carried on the attack-end fires below, exactly like the
    # direct base-attack pipeline's, because Overwhelm excess IS combat damage dealt
    # to a base (Ezra Bridger ASH_13, Hera Syndulla ASH_31).
    spill_to_base = 0
    if (has_keyword(s, attacker, Keyword.OVERWHELM) and dealt_to_defender > 0
            and not _overwhelm_denied_by(s, [defender])):
        excess = max(0, dealt_to_defender - defender_hp_before)
        if excess > 0:
            def_base = inactive_ps.base_instance
            if def_base is not None:
                excess = base_damage_after_prevention(s, def_base, excess)
            if def_base is not None and excess > 0:
                def_base.damage += excess
                spill_to_base = excess
                record_base_damage(s, inactive_ps.player_id, excess)
                s.event_log.append(OverwhelmDamage(
                    defending_player_id=inactive_ps.player_id,
                    amount=excess,
                ))
                s.event_log.append(DamageDealt(
                    target_instance_id=def_base.instance_id,
                    target_name=def_base.card_def.display_name,
                    owner_id=inactive_ps.player_id,
                    amount=excess,
                    is_base=True,
                ))
                _check_game_over(s)

    # Step 6: Defeat processing
    attacker_dead = _hp_lethal(s, attacker)
    defender_dead = _hp_lethal(s, defender)
    attacker_id = attacker.instance_id   # capture before possible defeat removes from play
    # Defeating one combatant can fire a WhenDefeated trigger (e.g. Hevy TWI_164's
    # "deal 1 to each enemy ground unit") that ALREADY defeats the other combatant
    # inline.  Re-check each is still in its arena before defeating it, so the
    # combat step does not home an already-removed unit a second time (which would
    # duplicate a leader in base_zone / a unit in discard).
    if attacker_dead:
        # Record that the attacking player lost a unit *while attacking* this round
        # (Oppression Breeds Rebellion SEC_158), whether the WhenDefeated AoE above
        # or this step does the actual defeat.
        s.game_memory.attackers_defeated_this_round.add(active_ps.player_id)
    if attacker_dead and _find_in_arenas(active_ps, attacker.instance_id) is not None:
        _defeat_unit(s, active_ps, attacker, while_attacking=True,
                     by_combat_damage=True)
    if defender_dead and _find_in_arenas(inactive_ps, defender.instance_id) is not None:
        _defeat_unit(s, inactive_ps, defender, by_combat_damage=True)

    # The Advantage tokens this attack actually rode with — snapshotted before any
    # attack-end trigger can hand out another one (ASH_180 / ASH_144).
    adv_snapshot = _snapshot_advantage_tokens(attacker, defender)

    # Fire OnAttackDefeatsUnit triggers when attacker survives and kills the defender
    if defender_dead and not attacker_dead:
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(
            s, None,  # no specific event type — only OnAttackDefeatsUnit triggers match
            after_all_player_idx=s.active_player_index,
            event_ctx={"attack_defeated_unit": attacker_id,
                       "attack_defeated_defender": defender.instance_id},
        )

    # "When a friendly unit's attack ends: …" (Boba Fett LAW_7, Anakin Skywalker
    # LAW_88) — its own fire, because it can ride neither neighbour: the
    # OnAttackDefeatsUnit fire just above is guarded on ``not attacker_dead`` and the
    # attack-ends fire further down on the attacker still being in play, while LAW_7's
    # printed rules note says the attacking unit "doesn't need to survive the attack".
    # Distinct keys, so this fire cannot re-match either of those trigger families.
    # EXACTLY ONE fire per attack, whatever happened: an observer's optional "If the
    # defending unit was defeated" clause reads ``attack_ended_defender_defeated``
    # (absent when the defender lived), so the two readings share one firing and
    # neither can fire twice for one attack.
    if not s.is_terminal():
        from swu.abilities.resolver import fire_triggered_abilities as _fire_end_obs
        end_obs_ctx = {"attack_ended_attacker": attacker_id}
        if defender_dead:
            end_obs_ctx["attack_ended_defender_defeated"] = defender.instance_id
        if spill_to_base > 0:
            end_obs_ctx["attack_ended_base_damage"] = attacker_id
            end_obs_ctx["attack_ended_base_damage_amount"] = spill_to_base
        _fire_end_obs(
            s, None,
            after_all_player_idx=s.player_index(inactive_ps.player_id),
            event_ctx=end_obs_ctx,
        )

    # Fire "When combat damage is dealt to this unit" triggers (Phase-III Dark
    # Trooper SHD_84) for each unit that took combat damage and survived — the
    # "(if it survives the damage)" clause falls out of only firing for a unit
    # still in play.  Flagged in event_ctx (mirroring dealt_combat_damage_to_base).
    # ``combat_damage_amount`` carries how much was dealt, so an observer can deal
    # "that much damage" (Tarfful SHD_250, DealDamageEqualTo "event_combat_damage").
    from swu.abilities.resolver import fire_triggered_abilities as _fire_dmg
    for hit_ci, hit_ps, dealt in (
        (defender, inactive_ps, dealt_to_defender),
        (attacker, active_ps, dealt_to_attacker),
    ):
        if (dealt > 0 and not s.is_terminal()
                and _find_in_arenas(hit_ps, hit_ci.instance_id) is not None):
            s = _fire_dmg(
                s, None,
                after_all_player_idx=s.active_player_index,
                event_ctx={"dealt_combat_damage_to": hit_ci.instance_id,
                           "combat_damage_amount": dealt},
            )

    # "When this unit deals combat damage to a (non-leader) unit while attacking"
    # (Rukh SOR_85) — fires for the ATTACKER (the mirror of the defender-side
    # WhenDealtCombatDamage above).  Only when the attacker dealt combat damage to
    # the defender and BOTH are still in play (so "that unit" — the surviving
    # defender in event_ctx["defender_id"] — is a live DEFENDER target).
    if (dealt_to_defender > 0 and not s.is_terminal()
            and _find_in_arenas(active_ps, attacker_id) is not None
            and _find_in_arenas(inactive_ps, defender.instance_id) is not None):
        s = _fire_dmg(
            s, None,
            after_all_player_idx=s.active_player_index,
            event_ctx={"attacker_dealt_combat_damage_to_unit": attacker_id,
                       "defender_id": defender.instance_id},
        )

    # "When Attack Ends: If this unit survived" (Vermillion LAW_215).  Fired last
    # (the attack is over) for the attacker, only if it is still in play after
    # defeat processing — the "survived" clause is intrinsic.  after_all is the
    # opponent so the turn passes once the resulting decision resolves (the
    # attacking action's switch is suspended while a decision is pending).
    if not s.is_terminal() and _find_in_arenas(active_ps, attacker_id) is not None:
        # ``attack_ended_defender_defeated`` rides along for
        # WhenAttackEnds(require_defender_defeated=True) — "If the defending unit was
        # defeated, ready this unit" (Thrawn ASH_33, Halo ASH_223).  It cannot
        # re-match the WhenFriendlyUnitAttackEnds observer, which additionally
        # requires ``attack_ended_attacker`` (never set on this fire).
        # ``attack_ended_combat_damaged`` lists the units this attacker actually dealt
        # combat damage to (The Great Mothers ASH_101).
        end_ctx = {"attack_ended_survivor": attacker_id}
        if defender_dead:
            end_ctx["attack_ended_defender_defeated"] = defender.instance_id
        if dealt_to_defender > 0:
            end_ctx["attack_ended_combat_damaged"] = [defender.instance_id]
        if spill_to_base > 0:
            end_ctx["attack_ended_base_damage"] = attacker_id
            end_ctx["attack_ended_base_damage_amount"] = spill_to_base
        s = _fire_dmg(
            s, None,
            after_all_player_idx=s.player_index(inactive_ps.player_id),
            event_ctx=end_ctx,
        )

    _settle_defeat_after_attack(s, attacker)   # "… defeat this unit" (LAW_62)
    # Advantage tokens expire when the attack (attacker) or the defense (defender)
    # ends — ASH_2, the ASH set mechanic.
    _defeat_advantage_tokens_after_combat(s, attacker, defender,
                                          only_ids=adv_snapshot)
    # "…you may deal its excess damage to another unit in the same arena" (Wipe Them
    # Out ASH_137).  Read BEFORE the this-attack sweep below, which drops the marker.
    _push_excess_damage_to_unit(s, attacker, combat_arena,
                                dealt_to_defender, defender_hp_before)
    # Clean up this-attack modifiers and the this-attack combat flags (Maul SHD_90
    # redirect, Stranger LAW_86 defender-deals-first) so neither leaks into a later
    # attack.
    _clear_this_attack_combat_flags(attacker, defender)
    _expire_modifiers(s, "this_attack")


def _push_excess_damage_to_unit(s: GameState, attacker: CardInstance,
                                arena: str, dealt: int, hp_before: int) -> None:
    """"For this attack, you may deal its excess damage to another unit in the same
    arena" (Wipe Them Out ASH_137) — Overwhelm's own excess computation aimed at a
    UNIT rather than at the defending base.

    Read at the tail of the single-defender pipeline, where ``dealt`` and the
    defender's pre-combat remaining HP are both known, from the ``this_attack``
    marker ``push_granted_attack(excess_damage_to_unit=True)`` landed on the chosen
    attacker.  The excess is delivered by ``push_select_damage`` at ``max_targets=1``
    — one chosen unit takes the whole amount, which IS "another unit" — with the
    always-offered finish carrying the printed "you may".  ``another`` needs no
    exclusion beyond the attacker: excess exists only when the damage was lethal, so
    the defender has already left the arena — which is also why ``arena`` is
    snapshotted before combat instead of read off the (by then discarded) defender."""
    if dealt <= 0:
        return
    excess = max(0, dealt - hp_before)
    if excess <= 0:
        return
    if not any(m.kind == "excess_damage_to_unit"
               and m.target_instance_id == attacker.instance_id
               for m in getattr(s, "modifiers", [])):
        return
    push_select_damage(s, attacker, amount_each=excess, max_targets=1,
                       arena=arena, exclude_source=True)


# ── ACTION phase actions ──────────────────────────────────────────────────────

@dataclass
class AttackTwoUnits(Action):
    """Attack two enemy units at once as a single attack (Darth Maul C24_6: "This
    unit can attack 2 units instead of 1").

    Both units are co-defenders of ONE attack: the attacker deals its power to each,
    and takes the SUM of both defenders' power, all simultaneously; Overwhelm spills
    the COMBINED excess to the defending base.  A base cannot be a co-defender ("may
    not attack a base and a unit simultaneously"), so both fields are real unit ids.
    """
    attacker_id: str
    defender1_id: str
    defender2_id: str

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        active_ps = s.active_player
        inactive_ps = s.inactive_player

        attacker = _find_in_arenas(active_ps, self.attacker_id)
        if attacker is None:
            raise IllegalActionError(f"Attacker {self.attacker_id} not found")
        if attacker.exhausted:
            raise IllegalActionError("Attacker is exhausted")
        if _multi_defender_count(s, attacker) < 2:
            raise IllegalActionError("Attacker cannot attack two units")
        if self.defender1_id == self.defender2_id:
            raise IllegalActionError("Must choose two distinct defenders")
        def1 = _find_in_arenas(inactive_ps, self.defender1_id)
        def2 = _find_in_arenas(inactive_ps, self.defender2_id)
        if def1 is None or def2 is None:
            raise IllegalActionError("Defender not found")
        if attacker.zone != def1.zone or attacker.zone != def2.zone:
            raise IllegalActionError("Attacker and defenders must share an arena")

        needs_continuation = _resolve_two_unit_combat(
            s, active_ps, inactive_ps, attacker, def1, def2)

        if not needs_continuation and not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return (f"Attack units {self.defender1_id} & {self.defender2_id} "
                f"with {self.attacker_id}")


# ── Phase 3 decision-resolving actions ───────────────────────────────────────

@dataclass
class ContinueAttack(Action):
    """Resume the attack pipeline after OnAttack trigger decisions have resolved.

    Resolves the top 'pre_attack' pending decision, then runs steps 2–6
    (Restore/Saboteur, power computation, damage, Overwhelm, defeat).
    """
    attacker_id: str
    defender_id: Optional[str]

    def apply(self, state: GameState) -> GameState:
        if not state.pending_decisions or state.pending_decisions[-1].kind != "pre_attack":
            raise IllegalActionError("No pending pre_attack decision")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pre_attack",
            choice="continue",
        ))

        active_ps = s.player_by_id(top.context["active_player_id"])
        inactive_ps = s.players[1 - s.player_index(top.context["active_player_id"])]
        attacker = _find_in_arenas(active_ps, self.attacker_id)
        if attacker is None:
            # The attack fizzles (a pre-attack trigger removed the attacker from
            # play), but it still ended — clean up its this-attack modifiers so
            # none leak into the settled state (would otherwise persist on the
            # would-be attacker or another unit a granted bonus targeted).
            _expire_modifiers(s, "this_attack")
            if not s.is_terminal():
                _switch_active_player(s)
            return s

        # A two-unit attack (Darth Maul C24_6) resumes into the multi-defender step2.
        defender_ids = top.context.get("defender_ids")
        if defender_ids is not None:
            defenders = [d for d in (
                _find_in_arenas(inactive_ps, defender_ids[0]),
                _find_in_arenas(inactive_ps, defender_ids[1]),
            ) if d is not None]
            if not defenders:
                # Both co-defenders left play during pre-attack triggers — cleanup.
                _clear_this_attack_combat_flags(attacker)
                _expire_modifiers(s, "this_attack")
                if not s.is_terminal():
                    _switch_active_player(s)
                return s
            _resolve_two_unit_combat_step2(s, active_ps, inactive_ps, attacker, defenders)
        elif self.defender_id is None:
            _resolve_base_attack_step2(s, active_ps, inactive_ps, attacker)
        else:
            defender = _find_in_arenas(inactive_ps, self.defender_id)
            if defender is None:
                # Defender left play during pre-attack triggers — same cleanup.
                _clear_this_attack_combat_flags(attacker)
                _expire_modifiers(s, "this_attack")
                if not s.is_terminal():
                    _switch_active_player(s)
                return s
            _resolve_unit_combat_step2(s, active_ps, inactive_ps, attacker, defender)

        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        if self.defender_id:
            return f"Continue attack vs {self.defender_id}"
        return "Continue base attack"


# ── Phase 3: pre_attack continuation ──────────────────────────────────

def _pre_attack_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    return [ContinueAttack(
        attacker_id=ctx["attacker_id"],
        defender_id=ctx.get("defender_id"),
    )]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _apply_ambush_defender_debuff(
    s: GameState, attacking_ps: PlayerState,
    attacker: CardInstance, defender: CardInstance,
) -> None:
    """Apply every ``AmbushDefenderDebuff`` the attacking player has in play as a
    ``this_attack`` stats modifier on ``defender`` (Enfys Nest SHD_219).

    Called only from ``UseAmbush.apply`` — the sole seam an Ambush attack is
    declared — so an ordinary attack by the same unit is unaffected, which is the
    distinction the card draws.  "Including this one" needs no special case: the
    Ambush attacker is in play at this point and so is found by the same scan.
    Multiple copies stack; a no-op (no modifier) when no such marker is in play."""
    from swu.abilities.registry import get_abilities, AmbushDefenderDebuff
    dp = dh = 0
    for ci in attacking_ps.ground_arena + attacking_ps.space_arena:
        if ability_suppressed(s, ci):
            continue
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, AmbushDefenderDebuff):
                dp += spec.power
                dh += spec.hp
    if not (dp or dh):
        return
    from swu.engine.state import Modifier
    s.modifiers.append(Modifier(
        modifier_id=s.alloc_modifier_id(),
        source_instance_id=attacker.instance_id,
        target_instance_id=defender.instance_id,
        kind="stats",
        value={"power": dp, "hp": dh},
        duration="this_attack",
    ))


def _apply_ambush_attacker_bonus(s: GameState, attacker: CardInstance) -> None:
    """Apply the attacker's own ``AmbushAttackerBonus`` markers as a ``this_attack``
    stats modifier (Heroic Purrgil ASH_207).

    The mirror of ``_apply_ambush_defender_debuff``, and called from the same single
    seam, so an ordinary attack by the same unit is unaffected — which is precisely
    what "while attacking using Ambush" says."""
    from swu.abilities.registry import get_abilities, AmbushAttackerBonus
    if ability_suppressed(s, attacker):
        return
    sc = getattr(attacker.card_def, "set_code", None) or ""
    cn = getattr(attacker.card_def, "card_number", None) or ""
    if not sc or not cn:
        return
    bp = bh = 0
    for spec in get_abilities(sc, cn):
        if isinstance(spec, AmbushAttackerBonus):
            bp += spec.power
            bh += spec.hp
    if not (bp or bh):
        return
    from swu.engine.state import Modifier
    s.modifiers.append(Modifier(
        modifier_id=s.alloc_modifier_id(),
        source_instance_id=attacker.instance_id,
        target_instance_id=attacker.instance_id,
        kind="stats",
        value={"power": bp, "hp": bh},
        duration="this_attack",
    ))


def _multi_defender_count(state: GameState, attacker: CardInstance) -> int:
    """The number of enemy units ``attacker`` may attack at once as a single attack
    (Darth Maul C24_6: "This unit can attack 2 units instead of 1" =
    ``MultiDefenderAttack(count=2)``), or 0 if it has no such marker.  Read at the
    two-unit attack-enumeration seam (``_enumerate_two_unit_attacks``) and by the
    ``AttackTwoUnits`` apply-guard; a no-op for the overwhelming majority of units
    (no such spec).  Mirrors the ``_attack_forbidden`` scan shape."""
    from swu.abilities.registry import get_abilities, MultiDefenderAttack
    sc = getattr(attacker.card_def, "set_code", None) or ""
    cn = getattr(attacker.card_def, "card_number", None) or ""
    if not sc or not cn:
        return 0
    for spec in get_abilities(sc, cn):
        if isinstance(spec, MultiDefenderAttack):
            return int(spec.count)
    return 0


def _forced_attack_actions(state: GameState) -> "list[AttackWithUnit] | None":
    """The constrained attack set for a Give-In-to-Your-Anger compulsion
    (SHD_144), or ``None`` when no compulsion applies to the active player.

    "Its controller's next action this phase must be an attack action with that
    unit, if able. It must attack a unit, if able."  So while the flag names the
    active player's unit and that unit is able to attack, ``legal_actions`` is
    restricted to that unit's attacks — the unit-target attacks if any exist
    ("must attack a unit, if able"), otherwise the base attack.  ``None`` means the
    compulsion is vacuous (the unit is gone / exhausted / unable to attack, or the
    flag isn't the active player's), so normal actions are offered and the flag is
    consumed by whatever action they take (actions.apply).

    A single-unit attack is the always-available attack form; the rare case where
    the compelled unit is a multi-defender attacker (Darth Maul C24_6) still offers
    its single attacks here — a documented simplification."""
    fa = state.game_memory.forced_attack
    if not fa:
        return None
    ps = state.active_player
    if ps.player_id != fa.get("player_id"):
        return None
    unit_id = fa.get("unit_id")
    attacker = next((u for u in ps.ground_arena + ps.space_arena
                     if u.instance_id == unit_id), None)
    if attacker is None or attacker.exhausted:
        return None
    attacks = [a for a in _enumerate_attacks(state, ps, state.inactive_player)
               if a.attacker_id == unit_id]
    if not attacks:
        return None
    unit_targets = [a for a in attacks if a.defender_id is not None]
    return unit_targets if unit_targets else attacks


def _enumerate_two_unit_attacks(
    state: GameState, ps: PlayerState, inactive_ps: PlayerState,
) -> list["AttackTwoUnits"]:
    """All legal AttackTwoUnits actions for ps's ready multi-defender attackers
    (Darth Maul C24_6).

    An attacker carrying a ``MultiDefenderAttack`` marker may attack any unordered
    pair of distinct enemy units in its OWN arena (a base can't be a co-defender —
    "may not attack a base and a unit simultaneously").  Sentinel and Hidden are
    honoured across the pair exactly as in ``_enumerate_attacks``: Hidden units are
    dropped from the eligible defenders, and if the defending player controls a
    Sentinel (and the attacker isn't a Saboteur), BOTH chosen units must be
    Sentinels.  Requires ≥2 eligible defenders in the arena.
    """
    acts: list[AttackTwoUnits] = []
    for attacker in ps.ground_arena + ps.space_arena:
        if attacker.exhausted:
            continue
        if _multi_defender_count(state, attacker) < 2:
            continue
        if _attack_forbidden(state, attacker):
            continue
        enemy_arena = (
            inactive_ps.ground_arena
            if attacker.zone == Zone.GROUND_ARENA
            else inactive_ps.space_arena
        )
        saboteur = has_keyword(state, attacker, Keyword.SABOTEUR)
        attackable = [u for u in enemy_arena
                      if not _is_hidden_from_attack(state, u)
                      and not _cannot_be_attacked(state, u)]
        sentinels = [u for u in attackable if has_keyword(state, u, Keyword.SENTINEL)]
        sentinel_required = bool(sentinels) and not saboteur
        eligible = sentinels if sentinel_required else attackable
        for i in range(len(eligible)):
            for j in range(i + 1, len(eligible)):
                acts.append(AttackTwoUnits(
                    attacker.instance_id,
                    eligible[i].instance_id,
                    eligible[j].instance_id))
    return acts


def push_granted_attack(
    s: GameState, source_ci: CardInstance,
    power_bonus: int = 0, hp_bonus: int = 0,
    *,
    optional: bool = False,
    bonus_trait: Optional[str] = None,
    grant_keywords: Optional[list[str]] = None,
    attacker_predicates: Optional[list[str]] = None,
    attacker_trait: Optional[str] = None,
    attacker_aspect: Optional[str] = None,
    attacker_id: Optional[str] = None,
    attacker_cost_max: Optional[int] = None,
    attacker_arena: Optional[str] = None,
    attacker_pilot_related: bool = False,
    bonus_if_defender_unit: bool = False,
    bonus_if_odd_cost_diff_from: Optional[int] = None,
    repeat: bool = False,
    allow_exhausted: bool = False,
    no_base: bool = False,
    exclude_source: bool = False,
    then_defeat_attacker: bool = False,
    defender_power_bonus: int = 0,
    defender_hp_bonus: int = 0,
    repeat_max: Optional[int] = None,
    cross_arena: bool = False,
    bonus_if_defender_ground: bool = False,
    bonus_per_defender_damage: int = 0,
    bonus_per_defending_arena_unit: int = 0,
    bonus_per_defending_player_unit: int = 0,
    draw_if_base_damaged: bool = False,
    opponent_discard_if_base_damaged: bool = False,
    defeat_attacker_if_base_damaged: bool = False,
    attacker_damage_prevention: bool = False,
    attacker_prevention_combat_only: bool = False,
    power_equals_remaining_hp: bool = False,
    return_defender_upgrades: bool = False,
    excess_damage_to_unit: bool = False,
    then_attack_cheaper: bool = False,
    defender_suppress_abilities: bool = False,
    borrow_abilities: bool = False,
    borrow_lender_id: Optional[str] = None,
) -> None:
    """Push a 'granted_attack' decision: the source's controller attacks with a
    unit that gets a bonus for that attack (e.g. Surprise Strike, Shoot First,
    Fleet Lieutenant).

    Parameters
    ----------
    power_bonus / hp_bonus
        Flat stat bonus applied to the chosen attacker for this attack.
    optional
        True for "You **may** attack with a unit" (a decline is always offered).
    bonus_trait
        If set, the stat bonus applies ONLY when the chosen attacker has this
        trait (e.g. Fleet Lieutenant: +2/+0 only if the unit is Rebel).
    grant_keywords
        Keyword names granted to the chosen attacker for this attack (e.g. Shoot
        First grants "First Strike").
    attacker_predicates
        Restricts which of the controller's units may be the attacker (e.g.
        Desperate Attack: "Attack with a *damaged* unit").  Each entry is one of
        the TargetSpec predicate names checked against a candidate attacker
        (``"damaged"``/``"undamaged"``/``"exhausted"``/``"non_leader"``); an
        attacker must satisfy ALL of them to be offered.  When the restriction
        leaves no eligible attacker the (mandatory) attack fizzles via
        DeclineGrantedAttack, exactly like having no ready unit at all.
    attacker_trait
        Restricts the attacker to units that have this trait (e.g. Rebel Assault:
        "Attack with a REBEL unit").  Like ``attacker_predicates``, it merely
        filters the offered AttackWithUnit options; no eligible attacker → the
        (mandatory) attack fizzles via DeclineGrantedAttack.
    attacker_id
        Pins the attacker to one specific unit (e.g. Hotshot DL-44 Blaster:
        "Attack with attached unit" — the upgrade's host).  Only attacks by that
        unit are offered; if it cannot attack (exhausted / left play) the attack
        fizzles via DeclineGrantedAttack.
    attacker_cost_max
        Restricts the attacker to units whose PRINTED cost is ≤ this (Moff Gideon
        SHD_7: "Attack with a unit that costs 3 or less").  Like ``attacker_trait``,
        it merely filters the offered AttackWithUnit options; no eligible attacker
        → the (mandatory) attack fizzles via DeclineGrantedAttack.
    attacker_arena
        Restricts the attacker to units in this arena ("ground"/"space") — Tandem
        Assault JTL_124: "Attack with a space unit … attack with a ground unit".
        Like the other attacker filters, no eligible attacker → the (mandatory)
        attack fizzles via DeclineGrantedAttack.
    attacker_pilot_related
        Restricts the attacker to "a Pilot unit or a unit with a Pilot on it"
        (Leia Organa JTL_97).
    bonus_if_defender_unit
        When True, the stat bonus applies ONLY when the chosen attack targets a
        unit, not a base (Moff Gideon SHD_7: "If it's attacking a unit, it gets
        +1/+0 for this attack").
    bonus_if_odd_cost_diff_from
        The revealed card's cost for Han Solo JTL_17 ("If the revealed card and
        that unit have different odd costs, +1/+0"): the stat bonus applies only
        when BOTH this value and the chosen attacker's printed cost are odd and
        the two costs differ.  ``grant_keywords`` entries may also be
        ``(name, value)`` pairs to grant a numeric keyword (Leia's Restore 1).
    repeat
        "Attack with any number of … units (one at a time)" (Mon Mothma SEC_103).
        After each granted attack resolves, the decision is re-pushed so the
        controller may attack with another (not-yet-attacked) unit, until they
        decline or no eligible unit remains.  Combine with ``optional`` so a
        decline is always available to stop the loop.  LIMITATION: the re-push
        happens at the end of AttackWithUnit; if a single attack itself requires a
        mid-attack decision (a ``pre_attack`` continuation from an OnAttack trigger
        that needs a choice), control returns through ContinueAttack instead and
        the loop ends early.  No shipped repeat-grant card has a choice-requiring
        OnAttack trigger on its other units, so this edge is not exercised.
    repeat_max
        Caps ``repeat`` at N attacks — "Attack with up to N units (one at a time)"
        (Headhunting SHD_145).  None (the default) is the unbounded "any number"
        (Mon Mothma SEC_103).
    allow_exhausted
        Offer attacks by EXHAUSTED units too (Mon Mothma SEC_103: "even if those
        units are exhausted").  The normal "attacker is exhausted" guard in
        AttackWithUnit is bypassed for a granted attack carrying this flag.
    no_base
        Drop the attack-a-base option, restricting granted attacks to enemy units
        (Mon Mothma SEC_103: "They can't attack bases for these attacks").
    exclude_source
        Drop the source unit from the eligible attackers ("any number of *other*
        units").
    then_defeat_attacker
        After the granted attack's combat fully settles, defeat the attacker
        (Heroic Sacrifice SOR_150: the attacker "gains: 'When this unit deals
        combat damage: Defeat it.'").  A +2/+0 attacker always has power ≥ 2 so it
        always deals combat damage to its target — the "when it deals combat
        damage" clause is therefore treated as unconditional.  If combat already
        defeated the attacker, this is a clean no-op.  LIMITATION: like ``repeat``,
        this fires only on the no-continuation settle path; an attacker whose own
        OnAttack trigger needs a mid-attack choice (a ``pre_attack`` continuation)
        is not self-defeated — no shipped card grants this rider to such a unit.

    cross_arena
        For THIS granted attack, let the chosen attacker reach enemy units in the
        OTHER arena too — a temporary, decision-scoped version of the printed
        CrossArenaAttack marker (Swoop Down SHD_230: a space unit "can attack ground
        units for this attack").  Threaded into ``_enumerate_attacks`` (defender
        enumeration) and the AttackWithUnit cross-arena apply-guard via the decision
        context, so no printed marker is needed.
    bonus_if_defender_ground
        The ``power_bonus``/``hp_bonus`` (attacker) AND ``defender_power_bonus``/
        ``defender_hp_bonus`` (defender debuff) apply ONLY when the chosen defender
        is a unit in the ground arena (Swoop Down SHD_230: "If it attacks a ground
        unit, it gets +2/+0 and the defender gets −2/−0").
    bonus_per_defender_damage
        The attacker gets +N/+0 for EACH damage already on the chosen defender when
        the attack starts (Corner the Prey TWI_139, N=1) — a bonus scaled by the
        defender rather than the attacker, snapshotted before combat deals anything.
        A base defender counts its own damage.
    bonus_per_defending_arena_unit
        The attacker gets +N/+0 for EACH unit the DEFENDING player controls in the
        attacker's own arena ("It gets +1/+0 for this attack for each unit the
        defending player controls in its arena" — Masterstroke ASH_234).  A
        population count rather than the damage count above, likewise snapshotted
        before combat, and it applies to a base attack too (the defender's arena
        population is still what it counts).
    draw_if_base_damaged
        The attacker's controller draws a card if this attack put damage on a base
        — "For this attack, it … gains: 'When this unit deals damage to a base:
        Draw a card.'" (Stay on Target JTL_177).  Settled in ``AttackWithUnit`` at
        the ``then_defeat_attacker`` rider point, by comparing every base's damage
        against a snapshot taken before combat, so an Overwhelm spill onto the base
        counts exactly like a direct base attack.
    opponent_discard_if_base_damaged
        Each opponent whose BASE this attack damaged discards a card — "gains: 'When
        Attack Ends: If this unit dealt combat damage to an opponent's base, that
        opponent discards a card.'" (Rash Action ASH_162).  Shares
        ``draw_if_base_damaged``'s snapshot and settle point, but re-reads it per
        player so only a damaged OPPONENT's base counts; the discard is the standing
        first-card simplification.
    defeat_attacker_if_base_damaged
        Defeat the attacker after the attack settles, but ONLY if it put damage on a
        base — "After completing this attack, if that unit damaged a base, defeat that
        unit" (Flash the Vents LAW_205).  The conditional sibling of the unconditional
        ``then_defeat_attacker``: it shares ``draw_if_base_damaged``'s before/after base
        snapshot (so an Overwhelm spill counts exactly like a direct base attack) and
        ``then_defeat_attacker``'s settle point, so a defender that killed the attacker
        first makes it a clean no-op.
    borrow_abilities
        The chosen attacker gains the SOURCE's other abilities for this attack — the
        Support keyword (ASH).  Landed as a single ``borrowed_abilities`` this-attack
        modifier naming the source as lender; ``state.borrowed_ability_sources`` is
        the read layer, consulted by the keyword layer (``has_keyword`` /
        ``keyword_value``, the Ghost JTL_53 copy block) and by
        ``resolver._collect_triggers`` (the lender's triggers, resolving FROM the
        attacker).  DOCUMENTED NARROWING: constant and activated abilities are not
        borrowed — they are read by scans keyed on the card in the arena, and only
        the keyword and trigger layers have a per-instance seam a duration can ride.

    The decision is presented to the controller as AttackWithUnit options;
    resolving one applies the bonus (this-attack) and runs combat.  If the
    controller has no unit able to attack (or declines an optional attack), a
    DeclineGrantedAttack lets the effect fizzle cleanly.
    """
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="granted_attack",
        context={
            "source_id": source_ci.instance_id,
            "power_bonus": power_bonus,
            "hp_bonus": hp_bonus,
            "optional": optional,
            "bonus_trait": bonus_trait,
            "grant_keywords": list(grant_keywords or []),
            "attacker_predicates": list(attacker_predicates or []),
            "attacker_trait": attacker_trait,
            "attacker_aspect": attacker_aspect,
            "attacker_id": attacker_id,
            "attacker_cost_max": attacker_cost_max,
            "attacker_arena": attacker_arena,
            "attacker_pilot_related": attacker_pilot_related,
            "bonus_if_defender_unit": bonus_if_defender_unit,
            "bonus_if_odd_cost_diff_from": bonus_if_odd_cost_diff_from,
            "repeat": repeat,
            # "Then, you may attack with another unit that costs less than it"
            # (Colonel Yularen SEC_6) — a one-shot follow-up whose cost cap is read
            # off the unit that just attacked, resolved at the AttackWithUnit site.
            "then_attack_cheaper": then_attack_cheaper,
            "allow_exhausted": allow_exhausted,
            "no_base": no_base,
            "exclude_source": exclude_source,
            "then_defeat_attacker": then_defeat_attacker,
            "defender_power_bonus": defender_power_bonus,
            "defender_hp_bonus": defender_hp_bonus,
            "repeat_max": repeat_max,
            "cross_arena": cross_arena,
            "bonus_if_defender_ground": bonus_if_defender_ground,
            "bonus_per_defender_damage": int(bonus_per_defender_damage),
            "bonus_per_defending_arena_unit": int(bonus_per_defending_arena_unit),
            "bonus_per_defending_player_unit": int(bonus_per_defending_player_unit),
            "draw_if_base_damaged": bool(draw_if_base_damaged),
            "opponent_discard_if_base_damaged": bool(
                opponent_discard_if_base_damaged),
            "defeat_attacker_if_base_damaged": bool(defeat_attacker_if_base_damaged),
            "attacker_damage_prevention": bool(attacker_damage_prevention),
            # "Prevent all COMBAT damage that would be dealt to each of them for
            # these attacks" (Brothers TS26_59) — the combat-only narrowing of the
            # JTL_193 blanket prevention.
            "attacker_prevention_combat_only": bool(attacker_prevention_combat_only),
            "power_equals_remaining_hp": bool(power_equals_remaining_hp),
            "return_defender_upgrades": bool(return_defender_upgrades),
            # "For this attack, you may deal its excess damage to another unit in
            # the same arena" (Wipe Them Out ASH_137) — landed as a this_attack
            # marker on the chosen attacker and settled at the pipeline's tail.
            "excess_damage_to_unit": bool(excess_damage_to_unit),
            # "the defender loses all abilities for this attack" (One Way Out
            # SEC_157) — applied to the chosen unit defender at the AttackWithUnit
            # site, alongside the defender stat debuff.
            "defender_suppress_abilities": bool(defender_suppress_abilities),
            # Support (ASH): "It gains this unit's OTHER abilities for this attack"
            # — the chosen attacker borrows the source's keywords and triggered
            # abilities for the duration of the attack (see the modifier landed at
            # the AttackWithUnit site).
            "borrow_abilities": bool(borrow_abilities),
            # The lender, when it is NOT the source — "this unit gains the
            # DISCARDED unit's abilities for this attack" (Improvised Identity
            # ASH_230), a lender sitting in the discard pile.  Default: the source
            # itself (Support).
            "borrow_lender_id": borrow_lender_id,
            "already_attacked": [],
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="granted_attack",
    ))


# ── Credit-token economy (jabba-the-hutt:07) ───────────────────────────────────

def _resolve_two_unit_combat(
    s: GameState,
    active_ps: PlayerState,
    inactive_ps: PlayerState,
    attacker: CardInstance,
    def1: CardInstance,
    def2: CardInstance,
) -> bool:
    """Declare a two-unit attack (Darth Maul C24_6) and fire its OnAttack triggers,
    then run steps 2–6 via ``_resolve_two_unit_combat_step2``.

    Returns True if a pre_attack continuation was pushed (an OnAttack trigger needed
    a choice) — callers must not switch the active player in that case.
    """
    # Step 1: Declare + exhaust.
    attacker.exhausted = True
    forced_by_sentinel = (
        (has_keyword(s, def1, Keyword.SENTINEL) or has_keyword(s, def2, Keyword.SENTINEL))
        and not has_keyword(s, attacker, Keyword.SABOTEUR)
    )
    s.game_memory.units_attacked_this_round.add(attacker.instance_id)
    note_token_unit_attacked(s, attacker)
    # Log an AttackDeclared for each co-defender (both are attacked) so the event
    # stream names both.  The bus fire is a no-op for WhenAttacked (an ability, not a
    # bus listener) but keeps parity with the single-defender declare.
    first_evt = None
    for defn in (def1, def2):
        evt = AttackDeclared(
            attacker_player_id=active_ps.player_id,
            attacker_instance_id=attacker.instance_id,
            attacker_name=attacker.card_def.display_name,
            defender_instance_id=defn.instance_id,
            defender_name=defn.card_def.display_name,
            forced_by_sentinel=forced_by_sentinel,
        )
        s.event_log.append(evt)
        get_bus().fire(s, evt)
        if first_evt is None:
            first_evt = evt

    # Phase 3: collect OnAttack / WhenAttacked ability triggers ONCE.  The attacker's
    # own OnAttack fires exactly once (the rules: "any triggered abilities only occur
    # once").  SIMPLIFICATION (documented; no shipped card exercises it): only the
    # first co-defender's WhenAttacked is fired — no shipped card has a WhenAttacked
    # defender under a two-unit attack.  Both defender ids ride in the event context.
    decisions_before = len(s.pending_decisions)
    from swu.abilities.resolver import fire_triggered_abilities
    event_ctx = {
        "attacker_id": attacker.instance_id,
        "defender_id": def1.instance_id,
        "defender_ids": [def1.instance_id, def2.instance_id],
    }
    s = fire_triggered_abilities(
        s, first_evt, after_all_player_idx=s.active_player_index, event_ctx=event_ctx)
    if len(s.pending_decisions) > decisions_before:
        pre_attack = PendingDecision(
            deciding_player_id=active_ps.player_id,
            kind="pre_attack",
            context={
                "attacker_id": attacker.instance_id,
                "defender_id": def1.instance_id,
                "defender_ids": [def1.instance_id, def2.instance_id],
                "active_player_id": active_ps.player_id,
            },
            after_resolve_player_index=1 - s.player_index(active_ps.player_id),
        )
        s.pending_decisions.insert(decisions_before, pre_attack)
        return True

    _resolve_two_unit_combat_step2(s, active_ps, inactive_ps, attacker, [def1, def2])
    return False


def _resolve_two_unit_combat_step2(
    s: GameState,
    active_ps: PlayerState,
    inactive_ps: PlayerState,
    attacker: CardInstance,
    defenders: list[CardInstance],
) -> None:
    """Steps 2–6 of a two-unit attack (Darth Maul C24_6).  Both co-defenders are hit
    simultaneously for the attacker's power; the attacker takes the SUM of both
    defenders' power; Overwhelm spills the COMBINED excess to the defending base.

    SIMPLIFICATIONS (documented; none exercised by a shipped card co-occurring with a
    two-unit attacker): First Strike, defender-deals-first (The Stranger LAW_86) and
    combat-damage redirect (Maul SHD_90) are not modelled here — a two-unit attack is
    always simultaneous; the "while defending" attacker debuff (Lando LAW_108) is not
    applied (``defender_id`` is left None for the attacker's power).
    """
    # Step 2: On-attack keyword triggers.
    if has_keyword(s, attacker, Keyword.RESTORE):
        n = keyword_value(s, attacker, Keyword.RESTORE)
        if n > 0:
            _apply_restore(s, active_ps, n, attacker.card_def.display_name)
    if has_keyword(s, attacker, Keyword.SABOTEUR):
        for defn in defenders:
            while shields_on(defn) > 0:
                defeat_shield(s, defn)

    # Combat damage is exchanged only among units still in play (an OnAttack ability
    # may have removed the attacker or a defender already — the same guard as the
    # single-defender step2, extended to two co-defenders).
    if _find_in_arenas(active_ps, attacker.instance_id) is None:
        _clear_this_attack_combat_flags(attacker)
        _expire_modifiers(s, "this_attack")
        return
    live_defs = [d for d in defenders
                 if _find_in_arenas(inactive_ps, d.instance_id) is not None]
    if not live_defs:
        _clear_this_attack_combat_flags(attacker)
        _expire_modifiers(s, "this_attack")
        return

    # Step 3: Effective powers (snapshot before any damage lands).
    atk_power = compute_power(s, attacker, is_attacking=True, attacking_unit=True)
    atk_power = _combat_power_after_block(s, attacker, atk_power)   # LAW_130
    hp_before = {d.instance_id: compute_hp(s, d) - d.damage for d in live_defs}
    def_powers = {d.instance_id: _combat_power_after_block(
                      s, d, compute_power(s, d, is_attacking=False))
                  for d in live_defs}

    # Step 4: simultaneous damage — each defender takes the attacker's power (its own
    # Shield may intercept); the attacker takes the SUM of the defenders' power.
    dealt = {}
    for d in live_defs:
        dealt[d.instance_id] = _deal_damage_with_shield(s, inactive_ps, d, atk_power,
                                                        is_combat=True,
                                                        dealer_source_id=attacker.instance_id)
    total_to_attacker = sum(def_powers[d.instance_id] for d in live_defs)
    # The co-defenders deal one pooled instance, so no single dealing card can be
    # named — the conservative reading (it keeps every prevention it would have).
    dealt_to_attacker = _deal_damage_with_shield(
        s, active_ps, attacker, total_to_attacker, is_combat=True)

    # Step 5: Overwhelm — the COMBINED excess spills to the defending base.
    spill_to_base = 0
    if (has_keyword(s, attacker, Keyword.OVERWHELM)
            and not _overwhelm_denied_by(s, live_defs)):
        excess = sum(max(0, dealt[d.instance_id] - hp_before[d.instance_id])
                     for d in live_defs)
        if excess > 0:
            def_base = inactive_ps.base_instance
            if def_base is not None:
                excess = base_damage_after_prevention(s, def_base, excess)
            if def_base is not None and excess > 0:
                def_base.damage += excess
                spill_to_base = excess
                record_base_damage(s, inactive_ps.player_id, excess)
                s.event_log.append(OverwhelmDamage(
                    defending_player_id=inactive_ps.player_id,
                    amount=excess,
                ))
                s.event_log.append(DamageDealt(
                    target_instance_id=def_base.instance_id,
                    target_name=def_base.card_def.display_name,
                    owner_id=inactive_ps.player_id,
                    amount=excess,
                    is_base=True,
                ))
                _check_game_over(s)

    # Step 6: Defeat processing (attacker + both co-defenders).  Re-check each is
    # still in its arena before defeating it (a WhenDefeated AoE from the first defeat
    # can already remove another combatant — the single-defender double-defeat guard).
    attacker_id = attacker.instance_id
    attacker_dead = _hp_lethal(s, attacker)
    if attacker_dead:
        s.game_memory.attackers_defeated_this_round.add(active_ps.player_id)
    defeated_def_ids: list[str] = []
    for d in live_defs:
        if (_hp_lethal(s, d)
                and _find_in_arenas(inactive_ps, d.instance_id) is not None):
            defeated_def_ids.append(d.instance_id)
            _defeat_unit(s, inactive_ps, d, by_combat_damage=True)
    if attacker_dead and _find_in_arenas(active_ps, attacker_id) is not None:
        _defeat_unit(s, active_ps, attacker, while_attacking=True,
                     by_combat_damage=True)

    # The Advantage tokens this attack actually rode with — snapshotted before any
    # attack-end trigger can hand out another one (ASH_180 / ASH_144).
    adv_snapshot = _snapshot_advantage_tokens(attacker, *live_defs)

    from swu.abilities.resolver import fire_triggered_abilities as _fire
    # OnAttackDefeatsUnit fires (once per defeated co-defender) when the attacker
    # survives and defeats a defender.
    if defeated_def_ids and not attacker_dead:
        for _did in defeated_def_ids:
            if s.is_terminal():
                break
            s = _fire(
                s, None,
                after_all_player_idx=s.active_player_index,
                event_ctx={"attack_defeated_unit": attacker_id,
                           "attack_defeated_defender": _did},
            )

    # The WhenFriendlyUnitAttackEnds observer (Boba Fett LAW_7, Anakin LAW_88) — as in
    # the single-defender pipeline, its own fire so a dead attacker still counts, and
    # EXACTLY ONCE: the attack ends once however many co-defenders it killed, so the
    # defeated key carries the first of them rather than the fire repeating.
    if not s.is_terminal():
        end_obs_ctx = {"attack_ended_attacker": attacker_id}
        if defeated_def_ids:
            end_obs_ctx["attack_ended_defender_defeated"] = defeated_def_ids[0]
        if spill_to_base > 0:
            end_obs_ctx["attack_ended_base_damage"] = attacker_id
            end_obs_ctx["attack_ended_base_damage_amount"] = spill_to_base
        s = _fire(
            s, None,
            after_all_player_idx=s.player_index(inactive_ps.player_id),
            event_ctx=end_obs_ctx,
        )

    # "When combat damage is dealt to this unit" (Phase-III Dark Trooper SHD_84) for
    # each combatant that took >0 combat damage and survived.
    hit_list = [(d, inactive_ps, dealt[d.instance_id]) for d in live_defs]
    hit_list.append((attacker, active_ps, dealt_to_attacker))
    for hit_ci, hit_ps, d_amt in hit_list:
        if (d_amt > 0 and not s.is_terminal()
                and _find_in_arenas(hit_ps, hit_ci.instance_id) is not None):
            s = _fire(
                s, None,
                after_all_player_idx=s.active_player_index,
                event_ctx={"dealt_combat_damage_to": hit_ci.instance_id,
                           "combat_damage_amount": d_amt},
            )

    # "When Attack Ends: If this unit survived" (Vermillion LAW_215) for the attacker.
    # Same two extra keys as the single-defender pipeline (ASH_33/223, ASH_101).
    if not s.is_terminal() and _find_in_arenas(active_ps, attacker_id) is not None:
        end_ctx = {"attack_ended_survivor": attacker_id}
        if defeated_def_ids:
            end_ctx["attack_ended_defender_defeated"] = defeated_def_ids[0]
        damaged_ids = [d.instance_id for d in live_defs if dealt[d.instance_id] > 0]
        if damaged_ids:
            end_ctx["attack_ended_combat_damaged"] = damaged_ids
        if spill_to_base > 0:
            end_ctx["attack_ended_base_damage"] = attacker_id
            end_ctx["attack_ended_base_damage_amount"] = spill_to_base
        s = _fire(
            s, None,
            after_all_player_idx=s.player_index(inactive_ps.player_id),
            event_ctx=end_ctx,
        )

    _settle_defeat_after_attack(s, attacker)   # "… defeat this unit" (LAW_62)
    _defeat_advantage_tokens_after_combat(s, attacker, *live_defs,
                                          only_ids=adv_snapshot)   # ASH_2
    _clear_this_attack_combat_flags(attacker)
    _expire_modifiers(s, "this_attack")
