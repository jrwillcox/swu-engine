"""Decisions taken by someone other than the player whose effect it is.

Normally the controller of an effect chooses its targets, and the engine can enumerate
those choices from the acting player alone. This family is the set of effects where it
cannot, because the rules hand the choice to somebody else:

* **the opponent picks, from their own cards** — ``opponent_chooses_target`` and the
  split-bounce decisions, where the attacker names a number and the defender decides
  which of their units it falls on.
* **each player picks, simultaneously in turn order** — ``each_player_defeats``, which
  is two nested decisions rather than one, since the second player's legal set depends
  on what the first did.
* **the controller picks who is spared, not who is hit** — ``choose_units_sacrifice_rest``
  inverts the usual selection, so the decision's payload names the survivors.
* **the card's owner, not its current controller, may act** — ``owner_may_replay``,
  which is the same inversion applied to ownership rather than to selection.

The shape they share, and the reason they are one module, is that handing the choice to
another player makes a single decision insufficient: the effect has to be suspended
while somebody else acts, then resumed. So these handlers are **staged** — they branch
on ``top.context["stage"]`` and enumerate a different action set per stage (``choose``
then ``confirm``, or select-then-finish) rather than returning one flat list. That is
also why the family owns so many small Action classes for its size: a stage boundary
needs its own class to cross.

The registration block at the bottom claims these kinds from ``dispatch``. It is the
whole of this module's coupling to the rest of the package -- nothing here is called by
another family, which is why it could be extracted first.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Leader, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardPlayed, DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState
from swu.engine.tokens import attach_token
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.zones import (
    _apply_put_on_deck, _defeat_unit, _put_unit_in_play,
)
from swu.engine.actions.shared import (
    _take_from_hand,
)


# ── Owner-may-replay a just-returned unit for free (Baylan Skoll LOF_185,

@dataclass
class ReplayReturnedUnit(Action):
    """Resolve an 'owner_may_replay' decision by playing the returned unit from the
    deciding player's hand for FREE (Baylan Skoll LOF_185 / Rio Durant LAW_93)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "owner_may_replay"):
            raise IllegalActionError("No owner_may_replay decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id != ctx.get("card_id"):
            raise IllegalActionError("Not the returned unit")
        owner_ps = s.player_by_id(top.deciding_player_id)
        if not any(c.instance_id == self.instance_id for c in owner_ps.hand):
            raise IllegalActionError("Returned unit is not in the owner's hand")
        ci = _take_from_hand(owner_ps, self.instance_id)
        if not isinstance(ci.card_def, Unit):
            raise IllegalActionError("Returned card is not a unit")
        grant_keyword = ctx.get("grant_keyword")
        after_idx = top.after_resolve_player_index
        s.pending_decisions.pop()

        card_played_evt = CardPlayed(
            player_id=owner_ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=0,
        )
        s.event_log.append(card_played_evt)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="owner_may_replay",
            choice=f"replayed {ci.card_def.display_name}",
        ))
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(owner_ps.player_id)
        # The decision is popped above BEFORE the unit enters play so the replayed
        # unit's own When Played / enter-play keyword triggers land on a clean
        # stack (the push_distribute_damage "pop, then act" gotcha).  It is played
        # for free (cost 0); ``grant_keyword`` (Rio's Shielded) is applied before
        # the enter-play keyword bus so a granted Shielded winks on immediately.
        _put_unit_in_play(
            s, owner_ps, ci, grant_keyword=grant_keyword,
            play_source="hand", cost_paid=0)
        get_bus().fire(s, card_played_evt)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return f"Play returned unit {self.instance_id} for free"


@dataclass
class DeclineReplay(Action):
    """Decline the optional 'owner_may_replay' replay ("may play it for free")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "owner_may_replay"):
            raise IllegalActionError("No owner_may_replay decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="owner_may_replay",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to replay the returned unit"


# ── New primitive: opponent-chooses-target (Grey Squadron Y-Wing SHD_246) ─────

@dataclass
class ChooseOwnTarget(Action):
    """The opponent chooses one of their own units or base to be the potential
    damage target (Grey Squadron Y-Wing SHD_246).  Advances the
    'opponent_chooses_target' decision to its confirm stage."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_chooses_target"):
            raise IllegalActionError("No opponent-chooses-target decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose":
            raise IllegalActionError("Opponent-chooses-target decision is past the choose stage")
        if self.target_id not in _opponent_chosen_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not a legal target to choose")
        ctx["chosen_id"] = self.target_id
        if ctx.get("disposition") in ("defeat", "exhaust"):
            # Single mandatory stage (LOF_43 "Defeat that unit" / LOF_15 "Exhaust
            # that unit"): resolve the instant the opponent chooses — no
            # controller confirm/decline.
            return _resolve_opponent_chooses_target(s, top, deal=True)
        ctx["stage"] = "confirm"
        controller_idx = s.player_index(ctx["controller_id"])
        top.deciding_player_id = ctx["controller_id"]
        s.active_player_index = controller_idx
        s.event_log.append(DecisionResolved(
            deciding_player_id=ctx["opponent_id"],
            kind="opponent_chooses_target",
            choice=f"chose {self.target_id}",
        ))
        return s

    def describe(self) -> str:
        return f"Choose own target {self.target_id}"


@dataclass
class ConfirmOpponentDamage(Action):
    """Deal the stored damage to the opponent's chosen target (Grey Squadron
    Y-Wing SHD_246 "you may deal 2 damage to it")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_chooses_target"):
            raise IllegalActionError("No opponent-chooses-target decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "confirm":
            raise IllegalActionError("Opponent-chooses-target decision is not at the confirm stage")
        return _resolve_opponent_chooses_target(s, top, deal=True)

    def describe(self) -> str:
        return "Deal damage to the chosen target"


@dataclass
class DeclineOpponentDamage(Action):
    """Decline the optional damage — the ability does nothing (Grey Squadron
    Y-Wing SHD_246 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_chooses_target"):
            raise IllegalActionError("No opponent-chooses-target decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "confirm":
            raise IllegalActionError("Opponent-chooses-target decision is not at the confirm stage")
        return _resolve_opponent_chooses_target(s, top, deal=False)

    def describe(self) -> str:
        return "Decline dealing the damage"


# ── New primitive: each-player-defeats-a-unit (Merciless Contest TWI_238) ─────

@dataclass
class ChooseUnitToDefeat(Action):
    """The current player chooses one of their own matching units to be defeated
    (Merciless Contest TWI_238).  Advances the 'each_player_defeats' decision to
    the next player, or resolves it (defeats all chosen units) once everyone has
    chosen."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "each_player_defeats"):
            raise IllegalActionError("No each-player-defeats decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        current_player = ctx["order"][ctx["idx"]]
        if self.target_id not in _each_player_defeat_targets(s, ctx, current_player):
            raise IllegalActionError(f"{self.target_id} is not a legal unit to defeat")
        ctx["chosen_ids"].append(self.target_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=current_player,
            kind="each_player_defeats",
            choice=f"chose {self.target_id}",
        ))
        # Advance to the next player who has an eligible unit.
        ctx["idx"] += 1
        while (ctx["idx"] < len(ctx["order"])
               and not _each_player_defeat_targets(s, ctx, ctx["order"][ctx["idx"]])):
            ctx["idx"] += 1
        if ctx["idx"] < len(ctx["order"]):
            next_player = ctx["order"][ctx["idx"]]
            top.deciding_player_id = next_player
            s.active_player_index = s.player_index(next_player)
            return s
        return _resolve_each_player_defeats(s, top)

    def describe(self) -> str:
        return f"Choose unit to defeat {self.target_id}"


# ── Opponent chooses one of their cards, you may damage it (Grey

#    Squadron Y-Wing SHD_246) ────────────────────────────────────────────
def _opponent_chooses_target_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "choose":
        return [ChooseOwnTarget(t) for t in _opponent_chosen_targets(state, ctx)]
    # stage "confirm"
    return [ConfirmOpponentDamage(), DeclineOpponentDamage()]


# ── Controller picks up to 2 non-leader units; the opponent chooses which

#    returns to hand, the other is bottomed (I Had No Choice SOR_187) ──────
def _opponent_split_bounce_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    if ctx.get("stage") == "choose":
        acts: list[Action] = [SelectSplitBounceUnit(t)
                              for t in _split_bounce_candidates(state, ctx)]
        acts.append(FinishSplitBounce())
        return acts
    # stage "split" — opponent picks which of the two returns to hand
    return [ChooseSplitReturn(cid) for cid in ctx["selected_ids"]]


# ── Owner of a returned unit may replay it for free (Baylan Skoll

#    LOF_185, Rio Durant LAW_93) ────────────────────────────────────────
def _owner_may_replay_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    card_id = top.context.get("card_id")
    acts: list[Action] = []
    if any(c.instance_id == card_id for c in deciding_ps.hand):
        acts.append(ReplayReturnedUnit(card_id))
    acts.append(DeclineReplay())  # "may play it for free"
    return acts


# ── Each player chooses one of their own non-leader units; defeat them

#    (Merciless Contest TWI_238) ────────────────────────────────────────────
def _each_player_defeats_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    current_player = ctx["order"][ctx["idx"]]
    return [ChooseUnitToDefeat(t)
            for t in _each_player_defeat_targets(state, ctx, current_player)]


# ── Choose N friendly units to spare, defeat all other friendly units

#    (Always Two LOF_42) ─────────────────────────────────────────────────────
def _choose_units_sacrifice_rest_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [ChooseUnitToSpare(t)
            for t in _choose_units_sacrifice_rest_targets(state, top.context)]


# ── Opponent-chooses-target push helper (Grey Squadron Y-Wing SHD_246) ────────

def _opponent_chosen_targets(state: GameState, ctx: dict) -> list[str]:
    """Legal instance ids the opponent may choose (recomputed from current state).

    By default any unit or base they control.  When ``ctx["ground_only"]`` is set
    (Jabba's Rancor LAW_216: "An opponent chooses a ground unit they control") the
    choice is restricted to the opponent's ground-arena units — no base, no space.
    When ``ctx["units_only"]`` is set (The Tragedy of Plagueis LOF_43: "An opponent
    chooses a unit they control") it is any unit in either arena — but no base.
    ``ctx["ready_only"]`` narrows any of those to READY units (Cal Kestis LOF_15:
    "An opponent chooses a READY unit they control").
    """
    opp = state.player_by_id(ctx["opponent_id"])
    ready_only = bool(ctx.get("ready_only"))

    def _ok(u) -> bool:
        return (not ready_only) or (not u.exhausted)

    if ctx.get("ground_only"):
        return [u.instance_id for u in opp.ground_arena if _ok(u)]
    if ctx.get("units_only"):
        return [u.instance_id
                for u in opp.ground_arena + opp.space_arena if _ok(u)]
    out = [u.instance_id for u in opp.ground_arena + opp.space_arena]
    base = opp.base_instance
    if base is not None:
        out.append(base.instance_id)
    return out


def push_opponent_chooses_target(
    s: GameState, source_ci: CardInstance, *, amount: int = 0,
    ground_only: bool = False, units_only: bool = False,
    disposition: str = "damage", ready_only: bool = False,
) -> None:
    """Push an 'opponent_chooses_target' decision: "An opponent chooses a unit or
    base they control. You may deal ``amount`` damage to it" (Grey Squadron
    Y-Wing SHD_246).

    Two stages with *different* deciding players (the say_no SOR_233 precedent):
    the opponent first picks one of their own cards (ChooseOwnTarget — mandatory,
    a base is always available), then control returns to the source's controller,
    who may ConfirmOpponentDamage / DeclineOpponentDamage.  The damage is dealt
    after the decision pops (the push_distribute_damage "pop, then deal" gotcha).
    Only pushed when the opponent has at least one card to choose.

    ``ground_only`` restricts the opponent's choice to their ground-arena units
    (Jabba's Rancor LAW_216: "An opponent chooses a ground unit they control") —
    no base, so the decision is skipped (the On Attack fizzles) when the opponent
    controls no ground units.

    ``disposition`` selects what happens to the chosen card:
      * ``"damage"`` (default) — the two-stage "you may deal ``amount``" flow above.
      * ``"defeat"`` — "Defeat that unit" (The Tragedy of Plagueis LOF_43): a
        *single* mandatory stage.  The opponent picks a unit (paired with
        ``units_only=True`` — no base is a legal choice) and it is defeated the
        instant they choose, with no controller confirm/decline stage.  Skipped
        (the event fizzles) when the opponent controls no eligible unit.
      * ``"exhaust"`` — "Exhaust that unit" (Cal Kestis LOF_15): the same single
        mandatory stage as ``"defeat"``, paired with ``units_only=True`` and
        ``ready_only=True`` so only a ready unit of theirs can be picked (an
        already-exhausted unit would be a no-op) — with none, nothing is pushed."""
    controller_id = source_ci.owner_id
    opponent_id = next(
        p.player_id for p in s.players if p.player_id != controller_id)
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
        "stage": "choose",
        "amount": int(amount),
        "ground_only": bool(ground_only),
        "units_only": bool(units_only),
        "ready_only": bool(ready_only),
        "disposition": disposition,
    }
    if not _opponent_chosen_targets(s, ctx):
        return
    opp_idx = s.player_index(opponent_id)
    dec = PendingDecision(
        deciding_player_id=opponent_id,
        kind="opponent_chooses_target",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = opp_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=opponent_id,
        kind="opponent_chooses_target",
    ))


def _resolve_opponent_chooses_target(
    s: GameState, top, *, deal: bool
) -> GameState:
    """Pop the decision, then act on the opponent-chosen target.  For the
    ``"damage"`` disposition, (if ``deal``) deal the stored damage; for the
    ``"defeat"`` disposition (LOF_43), defeat the chosen unit outright.  The action
    happens AFTER popping (like push_sacrifice_resource_for_damage) so a resulting
    WhenDefeated trigger lands on a clean stack."""
    ctx = top.context
    chosen_id = ctx.get("chosen_id")
    disposition = ctx.get("disposition", "damage")
    s.pending_decisions.pop()
    if disposition == "defeat":
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_chooses_target",
            choice=(f"defeated {chosen_id}" if chosen_id is not None else "no target"),
        ))
        if chosen_id is not None:
            result = s.find_instance(chosen_id)
            if result is not None:
                ps, ci = result
                _defeat_unit(s, ps, ci)  # "Defeat that unit" — mandatory, ignores HP
    elif disposition == "exhaust":
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_chooses_target",
            choice=(f"exhausted {chosen_id}" if chosen_id is not None else "no target"),
        ))
        if chosen_id is not None:
            result = s.find_instance(chosen_id)
            if result is not None:
                result[1].exhausted = True  # "Exhaust that unit" (Cal Kestis LOF_15)
    else:
        amount = int(ctx["amount"])
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_chooses_target",
            choice=(f"dealt {amount} to {chosen_id}" if deal else "declined"),
        ))
        if deal and chosen_id is not None:
            from swu.abilities.resolver import _apply_deal_damage
            source_result = s.find_instance(ctx["source_id"])
            source_name = (source_result[1].card_def.display_name
                           if source_result else None)
            _apply_deal_damage(s, chosen_id, amount, source_name=source_name)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── I Had No Choice SOR_187 — controller picks up to 2 non-leader units, the

def _split_bounce_candidates(state: GameState, ctx: dict) -> list[str]:
    """Still-selectable candidates for the 'choose' stage: pushed non-leader unit
    ids that remain in-play arena units and are not already selected."""
    selected = set(ctx["selected_ids"])
    out: list[str] = []
    for cid in ctx["candidate_ids"]:
        if cid in selected:
            continue
        result = state.find_instance(cid)
        if result is None:
            continue
        ps, ci = result
        if any(ci in arena for arena in (ps.ground_arena, ps.space_arena)):
            out.append(cid)
    return out


def _resolve_split_bounce_choose(s: GameState) -> GameState:
    """Finish the 'choose' stage: 0 picked → clean fizzle; 1 picked → return it to
    its owner's hand; 2 picked → advance to the opponent's 'split' stage."""
    top = s.pending_decisions[-1]
    ctx = top.context
    selected = list(ctx["selected_ids"])
    if len(selected) >= 2:
        ctx["stage"] = "split"
        top.deciding_player_id = ctx["opponent_id"]
        s.active_player_index = s.player_index(ctx["opponent_id"])
        s.event_log.append(DecisionPushed(
            deciding_player_id=ctx["opponent_id"],
            kind="opponent_split_bounce",
        ))
        return s
    s.pending_decisions.pop()  # pop, then act
    if len(selected) == 1:
        from swu.abilities.resolver import _apply_return_to_hand
        _apply_return_to_hand(s, selected[0])
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="opponent_split_bounce",
        choice=(f"returned {selected[0]}" if len(selected) == 1 else "no units"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


@dataclass
class SelectSplitBounceUnit(Action):
    """Stage 'choose' of opponent_split_bounce (I Had No Choice SOR_187): the
    source's controller adds a non-leader unit to the (up to 2) bounce pool.
    Reaching the max advances to the opponent's split stage."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_split_bounce"):
            raise IllegalActionError("No opponent_split_bounce decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose":
            raise IllegalActionError("opponent_split_bounce is past the choose stage")
        if self.instance_id not in _split_bounce_candidates(s, ctx):
            raise IllegalActionError(f"{self.instance_id} is not an eligible unit")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _resolve_split_bounce_choose(s)
        return s

    def describe(self) -> str:
        return f"Add {self.instance_id} to the bounce pool"


@dataclass
class FinishSplitBounce(Action):
    """Stop selecting units for opponent_split_bounce (I Had No Choice SOR_187).
    Always offered (the choice is "up to 2"), so a 0- or 1-pick finish is legal."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_split_bounce"):
            raise IllegalActionError("No opponent_split_bounce decision pending")
        return _resolve_split_bounce_choose(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish choosing units to bounce"


@dataclass
class ChooseSplitReturn(Action):
    """Stage 'split' of opponent_split_bounce (I Had No Choice SOR_187): the
    opponent picks which of the two chosen units returns to its owner's hand; the
    other is put on the bottom of its owner's deck."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "opponent_split_bounce"):
            raise IllegalActionError("No opponent_split_bounce decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "split":
            raise IllegalActionError("opponent_split_bounce is not at the split stage")
        selected = list(ctx["selected_ids"])
        if self.instance_id not in selected:
            raise IllegalActionError("Not one of the chosen units")
        other = next(cid for cid in selected if cid != self.instance_id)
        s.pending_decisions.pop()  # pop, then act
        from swu.abilities.resolver import _apply_return_to_hand
        _apply_return_to_hand(s, self.instance_id)      # to its owner's hand
        _apply_put_on_deck(s, other, to_top=False)      # the other → owner's deck bottom
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="opponent_split_bounce",
            choice=f"returned {self.instance_id}, bottomed {other}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Return {self.instance_id} to hand (bottom the other)"


def push_opponent_split_bounce(s: GameState, source_ci: CardInstance) -> None:
    """Push an 'opponent_split_bounce' decision (I Had No Choice SOR_187).  The
    source's controller chooses (stage "choose"); a two-pick pool later shifts to
    the opponent (stage "split").  Only pushed when at least one non-leader unit is
    in play (else the event fizzles cleanly)."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    candidate_ids: list[str] = []
    for p in s.players:
        for ci in p.ground_arena + p.space_arena:
            if isinstance(ci.card_def, Leader):
                continue  # "non-leader units"
            candidate_ids.append(ci.instance_id)
    if not candidate_ids:
        return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="opponent_split_bounce",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "opponent_id": opponent_id,
            "stage": "choose",
            "candidate_ids": candidate_ids,
            "selected_ids": [],
            "max_select": 2,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="opponent_split_bounce",
    ))


def push_owner_may_replay(
    s: GameState, source_ci: CardInstance, returned_instance_id: str,
    *, grant_keyword: Optional[str] = None,
) -> None:
    """Push an 'owner_may_replay' decision (Baylan Skoll LOF_185 / Rio Durant
    LAW_93): the OWNER of a just-returned unit may play it from their hand for
    FREE ("return a non-leader unit to its owner's hand.  Then, its owner may play
    it for free").

    The unit must already have been returned to its owner's hand (via
    ``_apply_return_to_hand``) before calling this.  The decider is that owner,
    who may be the source's OPPONENT — the say_no SOR_233 / opponent_chooses_target
    SHD_246 deciding-player shift — so this cannot be expressed as an ordinary
    ``play_from_hand`` decision (which is always decided by the source's
    controller).  ``grant_keyword`` (e.g. "Shielded") is granted to the replayed
    unit for this phase, applied before its enter-play keyword bus fires (Rio's
    "It gains Shielded for this phase"; Baylan grants nothing).

    Only pushed when the returned card is actually in its owner's hand (a clean
    no-op otherwise — e.g. the target fizzled)."""
    result = s.find_instance(returned_instance_id)
    if result is None:
        return
    owner_ps, ci = result
    if ci not in owner_ps.hand or ci.owner_id != owner_ps.player_id:
        return
    owner_idx = s.player_index(ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=ci.owner_id,
        kind="owner_may_replay",
        context={
            "source_id": source_ci.instance_id,
            "card_id": returned_instance_id,
            "owner_id": ci.owner_id,
            "grant_keyword": grant_keyword,
        },
        after_resolve_player_index=s.player_index(source_ci.owner_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=ci.owner_id,
        kind="owner_may_replay",
    ))


# ── Each player chooses one of their own non-leader units; defeat them all

def _each_player_defeat_targets(state: GameState, ctx: dict, player_id: str) -> list[str]:
    """Legal instance ids ``player_id`` may choose (recomputed from current state):
    the player's own non-leader arena units (a deployed leader is a Leader card_def
    and so excluded, mirroring the ``non_leader`` predicate).

    Under the ``"spare_then_damage"`` disposition — or with ``include_leaders``,
    for a card that simply says "a unit they control" (Governor's Shuttle LAW_99) —
    the choice carries no such narrowing (Time of Crisis LOF_177), so a deployed
    leader is a legal — and often the obvious — pick."""
    from swu.cards.models import Leader
    ps = state.player_by_id(player_id)
    if ctx.get("disposition") == "spare_then_damage" or ctx.get("include_leaders"):
        return [u.instance_id for u in ps.ground_arena + ps.space_arena]
    return [u.instance_id for u in ps.ground_arena + ps.space_arena
            if not isinstance(u.card_def, Leader)]


def push_each_player_defeats(
    s: GameState, source_ci: CardInstance, *, only_opponent: bool = False,
    disposition: str = "defeat", damage_amount: int = 0,
    include_leaders: bool = False,
) -> None:
    """Push an 'each_player_defeats' decision (Merciless Contest TWI_238): each
    player chooses one of their own non-leader units, then those units are
    defeated.  The source's controller chooses first, then the opponent; a player
    with no eligible unit is skipped, and if neither has one the decision is not
    pushed (the event fizzles).

    ``only_opponent`` restricts the choice to the OPPONENT of the source's
    controller ("An opponent chooses a non-leader unit they control.  Defeat that
    unit." — Avenger SOR_40); the controller never picks its own unit.

    ``disposition`` selects the payoff:
      * ``"defeat"`` (default) — defeat every chosen unit.
      * ``"spare_then_damage"`` — the INVERSE: the chosen units are the survivors,
        and ``damage_amount`` is dealt to every OTHER unit in play ("Each player
        chooses a unit they control.  Deal 3 damage to each unit not chosen this
        way" — Time of Crisis LOF_177).  The choice widens to any unit they
        control (a deployed leader included), and a player with no unit is simply
        skipped — all of their (zero) units are unchosen.

      * ``"return_then_defeat_all"`` — each player's chosen unit is RETURNED to its
        owner's hand, and then every non-leader unit still in play is defeated
        ("Each player may return a non-leader unit to its owner's hand.  Then,
        defeat all non-leader units." — Rhydonium Detonation LAW_96).
        OPTIMAL-PLAY COLLAPSE: the printed "may" is dropped, because the board is
        wiped immediately after — returning a unit that is about to be defeated is
        never worse than leaving it (the same card leaves play either way, but to
        hand rather than to the discard).  If NEITHER player has an eligible unit
        the decision is not pushed, which is also correct: the only units the wipe
        could defeat are exactly the ones that were eligible to be chosen.

    ``include_leaders`` widens the ``"defeat"`` choice the same way, for a card
    printed as plain "a unit they control" with no non-leader clause (Governor's
    Shuttle LAW_99)."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    order = [opponent_id] if only_opponent else [controller_id, opponent_id]
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
        "order": order,
        "idx": 0,
        "chosen_ids": [],
        "disposition": disposition,
        "damage_amount": int(damage_amount),
        "include_leaders": bool(include_leaders),
    }
    while ctx["idx"] < len(order) and not _each_player_defeat_targets(s, ctx, order[ctx["idx"]]):
        ctx["idx"] += 1
    if ctx["idx"] >= len(order):
        return  # neither player has an eligible unit → fizzle
    deciding = order[ctx["idx"]]
    dec = PendingDecision(
        deciding_player_id=deciding,
        kind="each_player_defeats",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(deciding)
    s.event_log.append(DecisionPushed(
        deciding_player_id=deciding,
        kind="each_player_defeats",
    ))


def _resolve_each_player_defeats(s: GameState, top) -> GameState:
    """Pop the decision, then act on the chosen units (the "pop, then act" gotcha —
    a defeat fires WhenDefeated triggers onto a clean stack)."""
    ctx = top.context
    chosen = list(ctx.get("chosen_ids", []))
    s.pending_decisions.pop()
    if ctx.get("disposition") == "spare_then_damage":
        amount = int(ctx.get("damage_amount", 0))
        spared = set(chosen)
        victims = [u.instance_id for p in s.players
                   for u in p.ground_arena + p.space_arena
                   if u.instance_id not in spared]
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="each_player_defeats",
            choice=f"spared {chosen}, dealt {amount} to {len(victims)} unit(s)",
        ))
        from swu.abilities.resolver import _apply_deal_damage
        source_result = s.find_instance(ctx["source_id"])
        source_name = (source_result[1].card_def.display_name
                       if source_result else None)
        for tid in victims:
            _apply_deal_damage(s, tid, amount, source_name=source_name)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    if ctx.get("disposition") == "return_then_defeat_all":
        # Rhydonium Detonation LAW_96: the picks are RESCUED to their owners' hands,
        # then everything else non-leader is wiped.  Both halves run after the pop
        # (the "pop, then act" rule) — the returns first, so a rescued unit is out of
        # the arena before the wipe reads it, which is the printed order.
        from swu.abilities.resolver import _apply_return_to_hand, _apply_defeat_unit
        from swu.cards.models import Leader
        for tid in chosen:
            if s.find_instance(tid) is not None:
                _apply_return_to_hand(s, tid)
        victims = [u.instance_id for p in s.players
                   for u in p.ground_arena + p.space_arena
                   if not isinstance(u.card_def, Leader)]
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="each_player_defeats",
            choice=f"returned {chosen}, defeated {len(victims)} unit(s)",
        ))
        for tid in victims:
            if s.find_instance(tid) is not None:
                _apply_defeat_unit(s, tid)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="each_player_defeats",
        choice=f"defeat {chosen}",
    ))
    from swu.abilities.resolver import _apply_defeat_unit
    for tid in chosen:
        _apply_defeat_unit(s, tid)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── Choose N friendly units, buff each, then defeat all OTHER friendly units

def _choose_units_sacrifice_rest_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible instance ids to spare: the controller's arena units matching the
    stored trait/predicate filter, minus those already chosen.  Scans only the
    controller's own arenas (so "friendly" is intrinsic and a source event sitting
    in discard is a non-issue — the select_token fallback pattern)."""
    from swu.abilities.resolver import _spec_matches_ci
    from swu.abilities.registry import TargetSpec
    spec = TargetSpec(
        controller="any", kind="unit",
        traits=tuple(ctx.get("traits", []) or ()),
        predicates=tuple(ctx.get("predicates", []) or ()),
    )
    ps = state.player_by_id(ctx["controller_id"])
    chosen = set(ctx.get("chosen", []))
    return [ci.instance_id
            for ci in ps.ground_arena + ps.space_arena
            if ci.instance_id not in chosen
            and _spec_matches_ci(spec, ci, ci, state, {})]


def push_choose_units_sacrifice_rest(
    s: GameState, source_ci: CardInstance, *,
    required_count: int,
    traits: Optional[list[str]] = None,
    predicates: Optional[list[str]] = None,
    tokens: Optional[list] = None,
) -> None:
    """Push a 'choose_units_sacrifice_rest' decision (Always Two LOF_42): the
    controller chooses exactly ``required_count`` of their own units matching the
    trait/predicate filter; on completion each chosen unit receives ``tokens``
    (a list of ``[token_name, count]``) and every OTHER friendly arena unit is
    defeated.  Pushed only when ≥ ``required_count`` units are eligible (else the
    "If you do" fails and nothing happens)."""
    controller_id = source_ci.owner_id
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "required_count": int(required_count),
        "traits": list(traits or []),
        "predicates": list(predicates or []),
        "tokens": [list(t) for t in (tokens or [])],
        "chosen": [],
    }
    if len(_choose_units_sacrifice_rest_targets(s, ctx)) < int(required_count):
        return  # too few eligible units → fizzle (no defeats)
    controller_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="choose_units_sacrifice_rest",
        context=ctx,
        after_resolve_player_index=1 - controller_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = controller_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="choose_units_sacrifice_rest",
    ))


@dataclass
class ChooseUnitToSpare(Action):
    """Choose one eligible friendly unit to spare (Always Two LOF_42).  Keeps
    selecting until ``required_count`` are chosen, then resolves (buff the chosen,
    defeat all other friendly units)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "choose_units_sacrifice_rest"):
            raise IllegalActionError("No choose-units-sacrifice-rest decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _choose_units_sacrifice_rest_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible unit to spare")
        ctx["chosen"].append(self.target_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="choose_units_sacrifice_rest",
            choice=f"spare {self.target_id}",
        ))
        if len(ctx["chosen"]) >= int(ctx["required_count"]):
            return _resolve_choose_units_sacrifice_rest(s, top)
        return s

    def describe(self) -> str:
        return f"Spare {self.target_id}"


def _resolve_choose_units_sacrifice_rest(s: GameState, top) -> GameState:
    """Pop, give each chosen unit its tokens, then defeat every OTHER friendly
    arena unit (the "pop, then defeat" gotcha — WhenDefeated lands on a clean
    stack)."""
    from swu.abilities.resolver import _apply_defeat_unit
    ctx = top.context
    chosen = list(ctx.get("chosen", []))
    chosen_set = set(chosen)
    tokens = ctx.get("tokens", [])
    controller_id = ctx["controller_id"]
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="choose_units_sacrifice_rest",
        choice=f"spared {chosen}",
    ))
    # Buff the chosen units.
    for tid in chosen:
        result = s.find_instance(tid)
        if result is None:
            continue
        owner_ps, ci = result
        for token_name, count in tokens:
            for _ in range(int(count)):
                attach_token(s, owner_ps, ci, token_name)
    # Defeat all OTHER friendly units (snapshot first — defeats mutate arenas).
    ctrl = s.player_by_id(controller_id)
    victims = [u.instance_id for u in ctrl.ground_arena + ctrl.space_arena
               if u.instance_id not in chosen_set]
    for tid in victims:
        _apply_defeat_unit(s, tid)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "opponent_chooses_target":       _opponent_chooses_target_actions,
    "opponent_split_bounce":         _opponent_split_bounce_actions,
    "owner_may_replay":              _owner_may_replay_actions,
    "each_player_defeats":           _each_player_defeats_actions,
    "choose_units_sacrifice_rest":   _choose_units_sacrifice_rest_actions,
})
