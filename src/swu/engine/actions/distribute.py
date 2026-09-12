"""Damage whose targets are chosen by a player rather than fixed by the effect.

"Deal N damage divided as you choose" cannot be resolved in one step, because each
point's legal targets depend on where the previous points went -- a unit defeated
halfway through stops being a target. So the effect becomes a decision that is pushed,
added to, and re-validated, and this module is the three shapes that takes:

* ``distribute_damage`` — divide a pool among any number of targets, the controller
  choosing the split. ``_distribution_targets`` is re-derived per assignment rather than
  snapshotted, which is the whole reason this is not a simple loop.
* ``assign_indirect_damage`` — the *receiving* player chooses where it lands, so the
  deciding player is not the source's controller.
* ``select_damage`` — a fixed amount to each of up to N chosen units.

Note what is **not** here: dealing the damage. All three hand off to the ability
resolver (``_apply_deal_damage``, ``_apply_indirect_damage``) once a target is settled,
so shields, prevention, lethality and the defeat cascade behave identically however the
damage was directed. This module decides *where*, never *what happens*.

``_resolve_assign_indirect_damage`` carries the one piece of ordering that is behaviour
rather than style, and its own comment says so: it pops the decision off the stack
*before* the damage is dealt, so a ``WhenDefeated`` trigger -- or the
``WhenIndirectDamageDealtToUnit`` observer -- fires onto a clean stack rather than on top
of the decision that caused it. The active player is restored to the source's controller
only once nothing is pending. Reordering those two lines would change which triggers see
which state.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardResourced,
    DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState, PlayerState, Zone

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.stats import (
    compute_power,
)
from swu.engine.actions.damage import (
    _bases_cannot_heal, note_base_healed,
)
from swu.engine.actions.zones import (
    _draw_cards,
)
from swu.engine.actions.shared import (
    _find_in_arenas_any, _plot_eligible_resource_ids, _plot_play_actions,
)
from swu.engine.actions.combat import (
    _select_damage_targets, push_granted_attack,
)
from swu.engine.actions.observers import (
    note_unit_healed,
)


# ── Player-directed damage distribution (distribute_damage decision) ──────────

@dataclass
class AssignDamage(Action):
    """Assign one point of distributed damage to a target unit.

    Used by the pool-allocation flows (Palpatine, Overwhelming Barrage): the
    controller spends the damage pool one point at a time onto any legal target
    (piling several points onto a single unit is allowed).  Damage is only
    *dealt* once the whole pool is allocated — the division is announced first,
    then applied simultaneously via the resolver, so no target leaves play
    mid-allocation.
    """
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.target_id not in _distribution_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        alloc = ctx.setdefault("alloc", {})
        alloc[self.target_id] = alloc.get(self.target_id, 0) + 1
        ctx["pool"] = int(ctx.get("pool", 0)) - 1
        if ctx["pool"] <= 0:
            return _finish_distribution(s)
        return s

    def describe(self) -> str:
        return f"Assign 1 damage to {self.target_id}"


@dataclass
class FinishDamageDistribution(Action):
    """Stop an "up to N" damage distribution early (Boba Fett JTL_9).

    Offered only in ``pool`` mode when the decision was pushed with ``up_to=True``.
    Deals whatever has been allocated so far and pops the decision.
    """
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if ctx.get("mode") != "pool" or not ctx.get("up_to"):
            raise IllegalActionError("This distribution cannot be finished early")
        return _finish_distribution(s)

    def describe(self) -> str:
        return "Finish assigning damage"


@dataclass
class ChooseDamageTarget(Action):
    """Choose the single victim for a sequenced-damage effect (Maximum Firepower).

    Picked first; the sources then each deal their power to this same unit.
    """
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if ctx.get("mode") != "sequence" or ctx.get("stage") != "pick_target":
            raise IllegalActionError("Not awaiting a damage target")
        if self.target_id not in _distribution_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        ctx["target_id"] = self.target_id
        ctx["stage"] = "pick_source"
        if not _distribution_sources(s, ctx):
            return _finish_distribution(s)
        return s

    def describe(self) -> str:
        return f"Choose damage target {self.target_id}"


@dataclass
class ChooseDamageSource(Action):
    """Choose a source unit that deals its power as part of a distribution.

    * Overwhelming Barrage (``source_pool``): pick the friendly unit, apply its
      this-phase buff, then distribute its (buffed) power among other units.
    * Maximum Firepower (``sequence``): pick a friendly Imperial unit; it deals
      its power to the fixed target, then (if the target survives and another
      distinct source remains) the next source is chosen.
    """
    unit_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "distribute_damage"):
            raise IllegalActionError("No distribute_damage decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.unit_id not in _distribution_sources(s, ctx):
            raise IllegalActionError(f"{self.unit_id} is not a legal damage source")
        mode = ctx.get("mode")

        if mode == "source_pool":
            result = s.find_instance(self.unit_id)
            if result is None:
                return _finish_distribution(s)
            _, src = result
            bp = int(ctx.get("buff_power", 0) or 0)
            bh = int(ctx.get("buff_hp", 0) or 0)
            if bp or bh:
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id("dist"),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=self.unit_id,
                    kind="stats",
                    value={"power": bp, "hp": bh},
                    duration="this_phase",
                ))
            ctx["pool"] = compute_power(s, src)
            if ctx.get("exclude_source_from_targets"):
                ctx.setdefault("exclude_ids", []).append(self.unit_id)
            ctx["stage"] = "allocate"
            if ctx["pool"] <= 0 or not _distribution_targets(s, ctx):
                return _finish_distribution(s)
            return s

        if mode == "sequence":
            top = s.pending_decisions[-1]
            after_idx = top.after_resolve_player_index
            target_id = ctx.get("target_id")
            ctx.setdefault("sources_used", []).append(self.unit_id)
            # Pop the distribute_damage decision BEFORE dealing damage: defeating
            # the target fires WhenDefeated triggers that push their own decisions
            # onto the stack, and they must land on a clean stack (not on top of
            # this decision, which a blind pop would then mishandle).
            s.pending_decisions.pop()
            result = s.find_instance(self.unit_id)
            power = compute_power(s, result[1]) if result is not None else 0
            if power > 0 and target_id is not None:
                from swu.abilities.resolver import _apply_deal_damage
                _apply_deal_damage(s, target_id, power)
            target_alive = (
                target_id is not None and _find_in_arenas_any(s, target_id) is not None
            )
            remaining = int(ctx.get("num_sources", 0)) - len(ctx["sources_used"])
            if target_alive and remaining > 0 and _distribution_sources(s, ctx):
                # Target survived → no defeat triggers were pushed, so the stack
                # top is clean; re-push for the next distinct source.
                ctx["stage"] = "pick_source"
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=top.deciding_player_id,
                    kind="distribute_damage",
                    context=ctx,
                    after_resolve_player_index=after_idx,
                ))
                s.active_player_index = s.player_index(top.deciding_player_id)
                return s
            # Sequence finished (target defeated, no more sources, or num_sources
            # reached).  Leave the active player to any triggers still resolving.
            s.event_log.append(DecisionResolved(
                deciding_player_id=top.deciding_player_id,
                kind="distribute_damage",
                choice="distributed",
            ))
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = after_idx
            return s

        raise IllegalActionError(f"ChooseDamageSource invalid for mode {mode}")

    def describe(self) -> str:
        return f"Choose damage source {self.unit_id}"


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───

@dataclass
class SelectDamageTarget(Action):
    """Pick one unit to deal 1 damage to (IG-2000 JTL_140 select_damage decision).
    Chosen targets are recorded; damage is dealt after the decision pops."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_damage"):
            raise IllegalActionError("No select-damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _select_damage_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible damage target")
        ctx["chosen"].append(self.target_id)
        ctx["remaining"] = int(ctx["remaining"]) - 1
        if int(ctx["remaining"]) <= 0 or not _select_damage_targets(s, ctx):
            return _resolve_select_damage(s, top)
        return s

    def describe(self) -> str:
        return f"Deal 1 damage to {self.target_id}"


@dataclass
class FinishSelectDamage(Action):
    """Stop selecting damage targets ("up to N") — deal recorded damage and pop."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_damage"):
            raise IllegalActionError("No select-damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_select_damage(s, top)

    def describe(self) -> str:
        return "Finish dealing damage"


@dataclass
class AssignIndirectDamage(Action):
    """Receiving player assigns all indirect damage to one of their targets
    (assign_indirect_damage decision — First Order Stormtrooper JTL_132, Dengar
    JTL_139, etc.)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "assign_indirect_damage"):
            raise IllegalActionError("No assign-indirect-damage decision pending")
        if self.target_id not in _assign_indirect_damage_targets(state, state.pending_decisions[-1].context):
            raise IllegalActionError(f"{self.target_id} is not a valid indirect-damage target")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ctx["chosen_id"] = self.target_id
        return _resolve_assign_indirect_damage(s, top)

    def describe(self) -> str:
        return f"Assign indirect damage to {self.target_id}"


# ── Deal 1 damage to each of up to N units (IG-2000 JTL_140) ──────────

def _select_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectDamageTarget(tid) for tid in _select_damage_targets(state, top.context)]
    acts.append(FinishSelectDamage())  # "up to" — stopping early is always legal
    return acts


# ── Receiving player assigns all indirect damage to one target ──────────

def _assign_indirect_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [AssignIndirectDamage(tid)
            for tid in _assign_indirect_damage_targets(state, top.context)]


# ── select_damage: deal 1 damage to each of up to N units (IG-2000 JTL_140) ─

def _resolve_select_damage(s: GameState, top) -> GameState:
    """Pop 'select_damage', then deal amount_each damage to every chosen target."""
    ctx = top.context
    chosen = list(ctx.get("chosen", []))
    amount_each = int(ctx.get("amount_each", 1))
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="select_damage",
        choice=f"dealt {amount_each} to {len(chosen)} unit(s)",
    ))
    # Deal damage AFTER pop so any defeat trigger lands on a clean stack.
    from swu.abilities.resolver import _apply_deal_damage
    source_result = s.find_instance(ctx["source_id"])
    source_name = source_result[1].card_def.display_name if source_result else None
    friendly_ids: set = set()
    if source_result is not None:
        _own = s.player_by_id(source_result[1].owner_id)
        friendly_ids = {u.instance_id
                        for u in _own.ground_arena + _own.space_arena}
    for tid in chosen:
        _apply_deal_damage(s, tid, amount_each, source_name=source_name,
                           dealer_id=top.deciding_player_id)
    # "Then, attack with the chosen unit" (Hotshot Maneuver JTL_174) — pushed
    # after the damage so the attack decision lands on a clean stack.  A unit that
    # died to its own card's damage (or has otherwise left play) simply cannot
    # attack: push_granted_attack finds no eligible attacker and fizzles.
    # "If no friendly units were damaged by this ability, deal N damage to your base"
    # (AAT Incinerator SEC_169).  Read from the chosen list against the SOURCE
    # controller's board, checked before the damage could remove anyone — a unit the
    # controller chose and killed still counts as damaged by this ability.
    self_burn = int(ctx.get("self_base_damage_if_no_friendly_hit", 0) or 0)
    if self_burn and source_result is not None:
        owner_id = source_result[1].owner_id
        own = s.player_by_id(owner_id)
        hit_friendly = any(tid in friendly_ids for tid in chosen)
        if not hit_friendly and own.base_instance is not None:
            _apply_deal_damage(s, own.base_instance.instance_id, self_burn,
                               source_name=source_name)
    attacker_id = ctx.get("then_attack_with")
    if attacker_id and source_result is not None and not s.is_terminal():
        push_granted_attack(s, source_result[1], attacker_id=attacker_id)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── assign_indirect_damage: receiving player assigns unpreventable damage ─────

def _assign_indirect_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible targets for 'assign_indirect_damage': the receiving player's base
    and all their arena units (a base is always present, so the list is never
    empty while the game is live)."""
    receiving_id: str = ctx["receiving_player_id"]
    ps = state.player_by_id(receiving_id)
    targets = []
    if ps.base_instance is not None:
        targets.append(ps.base_instance.instance_id)
    targets.extend(u.instance_id for u in ps.ground_arena + ps.space_arena)
    return targets


def _indirect_damage_bonus(s: GameState, controller_id: str) -> int:
    """Sum of every in-play ``IndirectDamageBonus`` marker controlled by
    ``controller_id`` (Hunting Aggressor JTL_165: "Indirect damage you deal to
    opponents is increased by 1"; multiple copies stack).  Read only at the
    indirect-damage chokepoint; 0 for the overwhelming majority of boards."""
    from swu.abilities.registry import get_abilities, IndirectDamageBonus
    ps = s.player_by_id(controller_id)
    total = 0
    for u in ps.ground_arena + ps.space_arena:
        sc = getattr(u.card_def, "set_code", None) or ""
        cn = getattr(u.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, IndirectDamageBonus):
                total += spec.amount
    return total


def _controller_self_assigns_indirect(s: GameState, controller_id: str) -> bool:
    """True when ``controller_id`` controls any ``IndirectDamageSelfAssign`` marker
    (Devastator JTL_143: "You assign all indirect damage you deal to opponents").
    Read only at the indirect-damage chokepoint; False for the overwhelming
    majority of boards, so the receiving player assigns as before."""
    from swu.abilities.registry import get_abilities, IndirectDamageSelfAssign
    ps = s.player_by_id(controller_id)
    for u in ps.ground_arena + ps.space_arena:
        # The marker may sit on the unit itself (Devastator JTL_143) or on an
        # attached UPGRADE conferring it ("Attached unit gains: 'You assign all
        # indirect damage dealt by this unit'" — Targeting Computer JTL_171).
        # DOCUMENTED SIMPLIFICATION: the read is controller-scoped, as the
        # decision seam has always been, so an upgrade-borne marker flips the
        # decider for that controller's indirect damage generally rather than only
        # for damage dealt by its own host.
        for card in (u, *u.attached_upgrades):
            sc = getattr(card.card_def, "set_code", None) or ""
            cn = getattr(card.card_def, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                if isinstance(spec, IndirectDamageSelfAssign):
                    return True
    return False


def push_assign_indirect_damage(
    s: GameState, source_ci: CardInstance, *, amount: int,
    then_draw_if_base: bool = False,
    then_ready_source_if_base: bool = False,
    then_exhaust_damaged: bool = False,
) -> None:
    """Push an 'assign_indirect_damage' decision: the OPPONENT of the source's
    controller must assign ``amount`` unpreventable damage among their base and
    units (First Order Stormtrooper JTL_132, Dengar JTL_139, etc.).

    Unlike normal damage this bypasses shields (indirect damage) and cannot be
    split — the receiving player picks ONE target that absorbs all ``amount``
    points.  Because the base is always a valid target the decision always has a
    legal action (no confirm step needed).  Damage is applied AFTER popping the
    decision ("pop, then deal").

    Three optional RIDERS settle at the same resolve point, once it is known what
    the receiving player actually hit (the "then_*" convention the other decisions
    already use).  They read off the single chosen target, which is exactly the
    granularity this decision models:

    ``then_draw_if_base``
        "If a base is damaged this way, draw a card" (Tactical Heavy Bomber
        JTL_152) — the SOURCE's controller draws.
    ``then_ready_source_if_base``
        "If a base is damaged this way, ready this unit" (Guerilla Soldier
        JTL_218) — a no-op if the source has since left play.
    ``then_exhaust_damaged``
        "Exhaust each unit damaged this way" (Kimogila Heavy Fighter JTL_222) —
        "each" is at most one unit here, and a unit defeated by the damage is no
        longer in an arena so nothing is exhausted.

    All three are inert by default, so every existing caller is unchanged.
    """
    controller_id = source_ci.owner_id
    receiving_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    amount = int(amount)
    # Static "indirect damage you deal is increased by N" markers (Hunting
    # Aggressor JTL_165) raise the amount — but only when there is damage to raise
    # (a 0-point deal stays 0, so a marker can never conjure damage from nothing).
    if amount > 0:
        amount += _indirect_damage_bonus(s, controller_id)
    ctx: dict = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "receiving_player_id": receiving_id,
        "amount": amount,
        "chosen_id": None,
    }
    if then_draw_if_base:
        ctx["then_draw_if_base"] = True
    if then_ready_source_if_base:
        ctx["then_ready_source_if_base"] = True
    if then_exhaust_damaged:
        ctx["then_exhaust_damaged"] = True
    if not _assign_indirect_damage_targets(s, ctx):
        return
    # "You assign all indirect damage you deal to opponents" (Devastator JTL_143):
    # the source's controller picks the target instead of the receiving player.
    # The eligible targets are unchanged (the receiving player's base/units); only
    # the decider flips.
    if _controller_self_assigns_indirect(s, controller_id):
        decider_id = controller_id
    else:
        decider_id = receiving_id
    decider_idx = s.player_index(decider_id)
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="assign_indirect_damage",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = decider_idx
    s.event_log.append(DecisionPushed(deciding_player_id=decider_id, kind="assign_indirect_damage"))


def _resolve_assign_indirect_damage(s: GameState, top) -> GameState:
    """Pop 'assign_indirect_damage', apply the indirect damage to the chosen
    target, then fire WhenIndirectDamageDealtToUnit if the target was a unit.

    Damage is dealt AFTER popping (the push_distribute_damage "pop, then deal"
    gotcha) so any WhenDefeated trigger — and the WhenIndirectDamageDealtToUnit
    observer (Allegiant General Pryde JTL_133) — lands on a clean stack.  The
    active player is set to the source controller only once nothing is pending."""
    from swu.abilities.resolver import _apply_indirect_damage, fire_triggered_abilities
    from swu.cards.models import Base
    ctx = top.context
    chosen_id: Optional[str] = ctx.get("chosen_id")
    amount = int(ctx["amount"])
    after_idx = top.after_resolve_player_index
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="assign_indirect_damage",
        choice=f"assigned {amount} indirect to {chosen_id}",
    ))
    if chosen_id is not None:
        source_result = s.find_instance(ctx["source_id"])
        source_name = source_result[1].card_def.display_name if source_result else None
        was_unit = False
        target_result = s.find_instance(chosen_id)
        if target_result is not None:
            was_unit = not isinstance(target_result[1].card_def, Base)
        _apply_indirect_damage(s, chosen_id, amount, source_name=source_name,
                               dealer_id=ctx.get("controller_id"))
        # Ledger for "If you dealt indirect damage this phase, …" (Decimator of
        # Dissidents JTL_138).  Only a real (non-zero) deal counts.
        if amount > 0 and ctx.get("controller_id"):
            s.game_memory.indirect_dealers_this_phase.add(ctx["controller_id"])
        # ── "then_*" riders (JTL_152 / JTL_218 / JTL_222) ──────────────────
        # Settled here, where it is known what the receiving player actually hit.
        # Only real damage counts as "damaged this way" (a 0-point deal does not).
        if amount > 0:
            if not was_unit and (ctx.get("then_draw_if_base")
                                 or ctx.get("then_ready_source_if_base")):
                if ctx.get("then_draw_if_base"):
                    _draw_cards(s, s.player_by_id(ctx["controller_id"]), 1)
                if ctx.get("then_ready_source_if_base") and source_result is not None:
                    source_result[1].exhausted = False
            if was_unit and ctx.get("then_exhaust_damaged"):
                # The unit may have been defeated by the damage — exhaust it only
                # while it is still in an arena.
                hit = s.find_instance(chosen_id)
                if hit is not None and hit[1].zone in (Zone.GROUND_ARENA,
                                                       Zone.SPACE_ARENA):
                    hit[1].exhausted = True
        # Fire WhenIndirectDamageDealtToUnit for any observer in play (Allegiant
        # General Pryde JTL_133) — fires whether or not the unit survived the
        # damage (indirect damage WAS dealt to a unit).
        if was_unit and not s.is_terminal():
            fire_triggered_abilities(
                s, None,
                after_all_player_idx=after_idx,
                event_ctx={"indirect_damage_unit_id": chosen_id},
            )
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = after_idx
    return s


# ── Player-directed damage distribution push helpers ──────────────────────────

def _push_distribute_decision(s: GameState, source_ci: CardInstance, ctx: dict) -> None:
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="distribute_damage",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="distribute_damage",
    ))


def push_distribute_damage(
    s: GameState, source_ci: CardInstance, amount: int,
    *,
    target_controller: str = "enemy",
    target_arena: Optional[str] = None,
    target_traits: Optional[list[str]] = None,
    exclude_ids: Optional[list[str]] = None,
    restrict_ids: Optional[list[str]] = None,
    up_to: bool = False,
    then_heal_base_if_survives: bool = False,
) -> None:
    """Push a 'distribute_damage' decision: "Deal ``amount`` damage divided as
    you choose among <filter> units" (Emperor Palpatine, SOR_135).

    The controller allocates the fixed pool one point at a time onto any legal
    target via ``AssignDamage`` (piling several points onto one unit is allowed);
    the damage is dealt simultaneously once the pool is spent.  If ``amount`` is
    non-positive or there are no legal targets, nothing is pushed and the effect
    fizzles cleanly (the caller hands the turn over normally).

    ``up_to=True`` makes it "deal UP TO ``amount`` damage" (Boba Fett JTL_9's
    "deal up to 4 damage divided … among any number of units"): a
    ``FinishDamageDistribution`` action is offered alongside the per-target
    ``AssignDamage`` options so the controller may stop before spending the whole
    pool (assigning 0 is allowed).

    ``restrict_ids`` is the WHITELIST complement of ``exclude_ids`` (the
    ``push_select_token`` LOF_147 field): only those instance ids may absorb the
    pool.  Pinned to ONE id it turns the pool into "deal up to N damage to <that
    unit>" — the way a card whose target is a single chosen unit still lets the
    controller pick the magnitude, since no choose-a-number decision exists (Choke
    on Aspirations LAW_102, whose target is chosen first by an ordinary
    ``CustomEffect.target``).

    ``then_heal_base_if_survives`` heals the controller's base for the damage
    actually dealt, but only while every damaged target is still in an arena —
    "If it survives, heal damage from your base equal to the damage dealt this
    way" (LAW_102).  Settled in ``_finish_distribution`` after the pop, so a
    defeat triggered by the damage lands on a clean stack first.
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "pool",
        "pool": int(amount),
        "up_to": bool(up_to),
        "alloc": {},
        "target_controller": target_controller,
        "target_arena": target_arena,
        "target_traits": list(target_traits or []),
        "exclude_ids": list(exclude_ids or []),
        "restrict_ids": list(restrict_ids) if restrict_ids is not None else None,
        "heal_base_if_survives": bool(then_heal_base_if_survives),
    }
    if int(amount) <= 0 or not _distribution_targets(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def push_distribute_heal(
    s: GameState, source_ci: CardInstance, amount: int,
    *,
    include_bases: bool = True,
    then_damage_self: bool = True,
    target_controller: str = "friendly",
    exclude_ids: Optional[list] = None,
) -> None:
    """Push an "up to ``amount``" heal distribution: "Heal up to N total damage from
    any number of units and/or bases" (Redemption SOR_52), reusing the
    ``distribute_damage`` pool machinery with a ``heal`` flag.

    The controller allocates the pool one point at a time onto its own damaged
    units/bases via ``AssignDamage`` (a target drops out once fully healed) and may
    stop early via ``FinishDamageDistribution`` (the pool is always "up to").  On
    finish, each allocation heals that much damage and — when ``then_damage_self`` —
    the total actually healed is dealt back to ``source_ci`` ("Deal that much damage
    to this unit").  Nothing is pushed when the pool is non-positive or the
    controller has nothing damaged to heal (the effect fizzles: 0 healed ⇒ 0 self
    damage).
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "pool",
        "heal": True,
        "include_bases": bool(include_bases),
        "heal_controller": str(target_controller),
        "exclude_ids": list(exclude_ids or []),
        "self_damage_source_id": source_ci.instance_id if then_damage_self else None,
        "pool": int(amount),
        "up_to": True,
        "alloc": {},
    }
    if int(amount) <= 0 or not _distribution_targets(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def push_distribute_source_power(
    s: GameState, source_ci: CardInstance,
    *,
    source_controller: str = "friendly",
    source_arena: Optional[str] = None,
    source_traits: Optional[list[str]] = None,
    buff_power: int = 0,
    buff_hp: int = 0,
    target_controller: str = "any",
    target_arena: Optional[str] = None,
    target_traits: Optional[list[str]] = None,
    exclude_source_from_targets: bool = True,
) -> None:
    """Push a 'distribute_damage' decision: the controller picks a source unit
    (which may receive a this-phase stat buff), then that unit deals damage equal
    to its (buffed) power divided as the controller chooses among any number of
    OTHER units (Overwhelming Barrage, SOR_92).

    Pushes only when at least one source unit exists.  After the source is
    chosen, the distribution fizzles cleanly if its power is 0 or no other unit
    can be targeted.
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "source_pool",
        "stage": "pick_source",
        "source_controller": source_controller,
        "source_arena": source_arena,
        "source_traits": list(source_traits or []),
        "buff_power": int(buff_power),
        "buff_hp": int(buff_hp),
        "exclude_source_from_targets": exclude_source_from_targets,
        "pool": 0,
        "alloc": {},
        "target_controller": target_controller,
        "target_arena": target_arena,
        "target_traits": list(target_traits or []),
        "exclude_ids": [],
    }
    if not _distribution_sources(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


def push_sequence_damage(
    s: GameState, source_ci: CardInstance,
    *,
    num_sources: int = 2,
    source_controller: str = "friendly",
    source_arena: Optional[str] = None,
    source_traits: Optional[list[str]] = None,
    target_controller: str = "any",
    target_arena: Optional[str] = None,
    target_traits: Optional[list[str]] = None,
) -> None:
    """Push a 'distribute_damage' decision: the controller picks a single target
    unit, then up to ``num_sources`` distinct source units (filtered by trait)
    each deal damage equal to their power to that same target, in sequence
    (stopping early if the target is defeated) — Maximum Firepower, SOR_234.

    Pushes only when at least one source AND one legal target exist; otherwise
    the effect fizzles cleanly.
    """
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": source_ci.owner_id,
        "mode": "sequence",
        "stage": "pick_target",
        "source_controller": source_controller,
        "source_arena": source_arena,
        "source_traits": list(source_traits or []),
        "num_sources": int(num_sources),
        "sources_used": [],
        "target_id": None,
        "target_controller": target_controller,
        "target_arena": target_arena,
        "target_traits": list(target_traits or []),
        "exclude_ids": [],
        "alloc": {},
    }
    if not _distribution_sources(s, ctx) or not _distribution_targets(s, ctx):
        return
    _push_distribute_decision(s, source_ci, ctx)


# ── distribute_damage decision helpers ───────────────────────────────────────

def _distribution_units(
    state: GameState, controller_id: str, controller_filter: str,
    arena: Optional[str], traits: list[str], exclude_ids: list[str],
) -> list[str]:
    """Instance ids of arena units matching a distribution filter.

    ``controller_filter`` is "friendly" / "enemy" / "any" relative to
    ``controller_id``; ``arena`` is "ground" / "space" / None (both); ``traits``
    must all be present; ids in ``exclude_ids`` are skipped (e.g. the source unit
    when distributing among "other units").
    """
    owner_idx = state.player_index(controller_id)
    out: list[str] = []
    for i, ps in enumerate(state.players):
        is_friendly = (i == owner_idx)
        if controller_filter == "friendly" and not is_friendly:
            continue
        if controller_filter == "enemy" and is_friendly:
            continue
        arena_lists = []
        if arena in (None, "ground"):
            arena_lists.append(ps.ground_arena)
        if arena in (None, "space"):
            arena_lists.append(ps.space_arena)
        for arena_list in arena_lists:
            for ci in arena_list:
                if ci.instance_id in exclude_ids:
                    continue
                if traits:
                    from swu.engine.traits import get_traits
                    ctraits = get_traits(state, ci)
                    if any(t not in ctraits for t in traits):
                        continue
                out.append(ci.instance_id)
    return out


def _distribution_targets(state: GameState, ctx: dict) -> list[str]:
    if ctx.get("heal"):
        return _heal_distribution_targets(state, ctx)
    out = _distribution_units(
        state, ctx["controller_id"],
        ctx.get("target_controller", "any"), ctx.get("target_arena"),
        ctx.get("target_traits", []), ctx.get("exclude_ids", []),
    )
    allowed = ctx.get("restrict_ids")
    if allowed is not None:
        out = [t for t in out if t in allowed]
    return out


def _heal_distribution_targets(state: GameState, ctx: dict) -> list[str]:
    """Instance ids of the controller's own damaged units (and, when
    ``include_bases``, its damaged base) that can still absorb more of the heal
    pool — a target drops out once its allocation reaches its current damage, so a
    heal point is never wasted on an undamaged / already-fully-healed target.

    Backs the heal flavour of the ``distribute_damage`` decision (Redemption
    SOR_52: "Heal up to 8 total damage from any number of units and/or bases").
    Restricted to the controller's own cards — healing an enemy card while dealing
    the healed total back to Redemption is never useful, a documented simplification
    of the printed "any number of units and/or bases".
    """
    ps = state.player_by_id(ctx["controller_id"])
    alloc = ctx.get("alloc", {})
    # ``heal_controller`` widens the pool beyond the controller's own cards —
    # "heal up to 4 damage from among OTHER units" (Nala Se SEC_65) is unqualified,
    # so either player's units may absorb it; ``exclude_ids`` carries the "other"
    # (the source itself).  Defaults keep the Redemption SOR_52 reading.
    owners = ([ps] if ctx.get("heal_controller", "friendly") != "any"
              else list(state.players))
    cands = [ci for owner in owners
             for ci in list(owner.ground_arena) + list(owner.space_arena)]
    if ctx.get("include_bases") and not _bases_cannot_heal(state):
        for owner in owners:
            if owner.base_instance is not None:
                cands.append(owner.base_instance)
    excluded = set(ctx.get("exclude_ids") or ())
    out: list[str] = []
    for ci in cands:
        if ci.instance_id in excluded:
            continue
        if int(ci.damage) - int(alloc.get(ci.instance_id, 0)) > 0:
            out.append(ci.instance_id)
    return out


def _distribution_sources(state: GameState, ctx: dict) -> list[str]:
    return _distribution_units(
        state, ctx["controller_id"],
        ctx.get("source_controller", "friendly"), ctx.get("source_arena"),
        ctx.get("source_traits", []), ctx.get("sources_used", []),
    )


def _finish_distribution(s: GameState) -> GameState:
    """Pop the distribute_damage decision, applying any pooled allocation.

    Pool-allocation flows accumulate per-target amounts in ``alloc`` and deal
    them here (announce-then-deal); sequence flows deal damage as each source is
    chosen and reach here with an empty ``alloc``.
    """
    top = s.pending_decisions.pop()
    ctx = top.context
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="distribute_damage",
        choice="distributed",
    ))
    # Deal the announced division simultaneously, now that the decision is off
    # the stack — any WhenDefeated triggers stack cleanly on top.
    alloc = ctx.get("alloc", {})
    if ctx.get("heal"):
        # Heal flavour (Redemption SOR_52): reduce each target's damage by its
        # allocation, sum the damage actually removed, then deal that total to the
        # source unit ("Deal that much damage to this unit").
        total_healed = 0
        for tid in sorted(alloc):
            amt = int(alloc[tid])
            res = s.find_instance(tid)
            if res is None or amt <= 0:
                continue
            _, ci = res
            healed = min(amt, int(ci.damage))
            ci.damage -= healed
            note_unit_healed(s, ci, healed)
            total_healed += healed
        self_id = ctx.get("self_damage_source_id")
        if self_id and total_healed > 0 and s.find_instance(self_id) is not None:
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(s, self_id, total_healed,
                               dealer_id=ctx.get("controller_id"))
    elif alloc:
        from swu.abilities.resolver import _apply_deal_damage
        dealer_id = ctx.get("controller_id")
        dealt = 0
        for tid in sorted(alloc):
            amt = int(alloc[tid])
            if amt > 0:
                _apply_deal_damage(s, tid, amt, dealer_id=dealer_id)
                dealt += amt
        if ctx.get("heal_base_if_survives") and dealt > 0:
            # "If it survives, heal damage from your base equal to the damage dealt
            # this way" (Choke on Aspirations LAW_102) — a target the damage
            # defeated has left its arena, and forfeits the heal.
            # ``find_instance`` reaches the discard, so survival is an ARENA test.
            in_arena = {ci.instance_id
                        for p in s.players
                        for ci in list(p.ground_arena) + list(p.space_arena)}
            survived = all(tid in in_arena
                           for tid in alloc if int(alloc[tid]) > 0)
            base = s.player_by_id(ctx["controller_id"]).base_instance
            if survived and base is not None and not _bases_cannot_heal(s):
                before_base = int(base.damage)
                base.damage = max(0, int(base.damage) - dealt)
                note_base_healed(s, base, before_base - base.damage)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _distribute_damage_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top distribute_damage decision (never empty: the
    push helpers only push when ≥1 option exists, and every stage transition
    auto-finishes when the next stage would be empty)."""
    ctx = top.context
    mode = ctx.get("mode")
    if mode == "pool":
        acts: list[Action] = [AssignDamage(t) for t in _distribution_targets(state, ctx)]
        if ctx.get("up_to"):
            acts.append(FinishDamageDistribution())
        return acts
    if mode == "source_pool":
        if ctx.get("stage") == "pick_source":
            return [ChooseDamageSource(u) for u in _distribution_sources(state, ctx)]
        return [AssignDamage(t) for t in _distribution_targets(state, ctx)]
    if mode == "sequence":
        if ctx.get("stage") == "pick_target":
            return [ChooseDamageTarget(t) for t in _distribution_targets(state, ctx)]
        return [ChooseDamageSource(u) for u in _distribution_sources(state, ctx)]
    return []


def _resource_card_from_hand(s: GameState, ps: PlayerState) -> None:
    """Put a card from ``ps``'s hand into play as a READY resource (face down).

    The from-hand sibling of ``_resource_top_of_deck``, behind "put a card from
    your hand into play as a resource and ready it" (Han Solo SOR_17's undeployed
    Action).  Faithful simplification (K-2SO SOR_145 auto-select precedent): the
    highest-cost hand card is chosen — the one least likely to be immediately
    playable, i.e. the natural card to resource — instead of prompting.  No-op on
    an empty hand."""
    if not ps.hand:
        return
    ci = max(ps.hand, key=lambda c: getattr(c.card_def, "cost", 0) or 0)
    ps.hand.remove(ci)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ps.resources.append(ci)
    s.event_log.append(CardResourced(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))


def push_plot_ability(s: GameState, source_ci: CardInstance, *,
                      ramp: bool = True) -> None:
    """Push a single-shot 'plot' decision: "Play a card with Plot from your
    resources (paying its cost)" (When Has Become Now SEC_245).

    Reuses the Plot decision / PlotPlay path (the chosen card is played via its
    Plot keyword — pay its printed cost, replace it with the deck top), but the
    context is marked ``plot_ability`` so PlotPlay resolves the decision after ONE
    play instead of re-offering the rest, and — when ``ramp`` — performs the
    errata's "if you do, put the top card of your deck into play as a resource".
    Pushed only when the controller has a Plot card in their resources they can
    actually afford right now; otherwise a no-op (you did not play a card, so no
    ramp)."""
    ps = s.player_by_id(source_ci.owner_id)
    plot_ids = [] if s.is_terminal() else _plot_eligible_resource_ids(s, ps)
    if not (plot_ids and _plot_play_actions(s, ps, set(plot_ids))):
        return
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=ps.player_id,
        kind="plot",
        context={"plot_ids": plot_ids, "plot_ability": True,
                 "ramp_after": bool(ramp)},
        after_resolve_player_index=1 - s.active_player_index,
    ))
    s.event_log.append(DecisionPushed(
        deciding_player_id=ps.player_id,
        kind="plot",
    ))

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "distribute_damage":             _distribute_damage_actions,
    "select_damage":                 _select_damage_actions,
    "assign_indirect_damage":        _assign_indirect_damage_actions,
})
