"""The discard pile, in both directions, because both use the same selection machinery.

*Out of it:* returning cards to hand, playing one as a resource, recurring a unit and
buffing it, returning one of several distinct-named picks at random, bottoming cards from
a pile. *Into it:* discarding down to a hand size, discarding as a cost, discarding for
Experience, and naming a card to discard it out of an opponent's hand.

Putting cards in and taking them out look like opposite concerns, but every one of them is
"choose some cards from a pile, subject to a predicate, possibly repeatedly" -- so they
share ``_distinct_discard_candidates``, ``_recur_buff_targets``, ``_name_discard_type_ok``
and the same accumulate-and-revalidate shape. Splitting them would duplicate that and
leave two modules importing each other.

**The trap here is about testing rather than playing, and it is a quiet one.**
``state.find_instance`` searches ``PlayerState.all_instances()``, which spans **ten** zones
including ``discard`` -- so a discarded card is still findable, and an assertion of the form
"the card is gone" written as ``find_instance(...) is None`` passes only by accident and
usually not at all. A test that a unit was defeated has to check the *arena* it left, not
the whole state.

The asymmetry that catches people out: a defeated **token** genuinely ceases to exist, since
it was never a deck card and has no pile to go to. So the same assertion is correct for a
token and wrong for a card, which is exactly the sort of difference that makes a test pass
for the wrong reason.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Optional

from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardResourced,
    DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState, Zone
from swu.engine.tokens import attach_token

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.damage import (
    base_damage_after_prevention,
)
from swu.engine.actions.zones import (
    _create_token_units, _draw_cards,
)
from swu.engine.actions.shared import (
    _candidate_card_views, _sacrifice_damage_targets,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard, record_base_damage, record_hand_discard,
)
from swu.engine.actions.hand import (
    push_play_from_hand,
)
from swu.engine.actions.deck import (
    push_deck_search,
)


# ── Return cards from the discard pile to hand (return_from_discard decision) ──

@dataclass
class SelectDiscardCard(Action):
    """Select one eligible card from the discard pile to return to hand."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "return_from_discard"):
            raise IllegalActionError("No return_from_discard decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard candidate")
        if self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} already selected")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _finish_return_from_discard(s)
        return s

    def describe(self) -> str:
        return f"Return {self.instance_id} from the discard pile to hand"


@dataclass
class FinishReturnFromDiscard(Action):
    """Stop selecting discard-pile cards: return the chosen ones to hand.

    Always offered (these effects are "you may" / "up to N", so a zero-pick
    finish is legal)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "return_from_discard"):
            raise IllegalActionError("No return_from_discard decision pending")
        return _finish_return_from_discard(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish returning cards from the discard pile"


def _finish_return_from_discard(s: GameState) -> GameState:
    """Pop the return_from_discard decision: move the selected cards from the
    controller's discard pile to their hand (preserving discard order)."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    selected_set = set(ctx["selected_ids"])

    returned = [ci for ci in ps.discard if ci.instance_id in selected_set]
    for ci in returned:
        ps.discard.remove(ci)
        ci.zone = Zone.HAND
        # A unit defeated while exhausted lands in discard still exhausted (discard
        # carries no exhaust meaning); a card returned to HAND must be a clean card,
        # else it trips the zone/exhaust-sanity invariant (the Sarlacc LAW_163
        # discard→deck graduation fix, mirrored for the discard→hand path).
        ci.exhausted = False
        ci.damage = 0
        ps.hand.append(ci)

    returned_names = ", ".join(ci.card_def.display_name for ci in returned) or "nothing"
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="return_from_discard",
        choice=f"returned {len(returned)} ({returned_names})",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── Put a chosen discard-pile card into play as a resource (resource_from_discard) ──

@dataclass
class SelectResourceFromDiscard(Action):
    """Select one eligible discard-pile card to put into play as a resource."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_discard"):
            raise IllegalActionError("No resource_from_discard decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a resource candidate")
        return _finish_resource_from_discard(s, self.instance_id)

    def describe(self) -> str:
        return f"Put {self.instance_id} into play as a resource"


@dataclass
class DeclineResourceFromDiscard(Action):
    """Decline to resource a discard card (offered only for a 'you may' variant)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_discard"):
            raise IllegalActionError("No resource_from_discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="resource_from_discard", choice="declined"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to resource a discard card"


def _finish_resource_from_discard(s: GameState, instance_id: str) -> GameState:
    """Pop the resource_from_discard decision: move the chosen card from the
    controller's discard pile into their resource zone (facedown + exhausted)."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    ci = next((c for c in ps.discard if c.instance_id == instance_id), None)
    name = "nothing"
    if ci is not None:
        ps.discard.remove(ci)
        ci.zone = Zone.RESOURCES
        ci.face_down = True
        ci.exhausted = True   # CR default: facedown + exhausted (no "ready it")
        ci.damage = 0
        ps.resources.append(ci)
        name = ci.card_def.display_name
        s.event_log.append(CardResourced(
            player_id=ps.player_id, instance_id=ci.instance_id, card_name=name))
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="resource_from_discard", choice=f"resourced {name}"))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_resource_from_discard(
    s: GameState, source_ci: CardInstance, *,
    eligible: Callable[["CardInstance"], bool], up_to: bool = False,
) -> None:
    """Push a 'resource_from_discard' decision: choose one card in the controller's
    discard pile matching ``eligible`` (a CardInstance predicate) and put it into
    play as a resource (facedown + exhausted).  Candidates are pre-filtered to the
    qualifying cards; fizzles cleanly (no prompt) if none qualify.  ``up_to`` adds a
    DeclineResourceFromDiscard for a "you may" variant (SHD_102/105 are mandatory
    among the qualifiers, so both pass up_to=False)."""
    ps = s.player_by_id(source_ci.owner_id)
    candidate_ids = [ci.instance_id for ci in ps.discard if eligible(ci)]
    if not candidate_ids:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="resource_from_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "up_to": bool(up_to),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="resource_from_discard"))


def _resource_from_discard_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top resource_from_discard decision."""
    ctx = top.context
    acts: list[Action] = [SelectResourceFromDiscard(cid) for cid in ctx["candidate_ids"]]
    if ctx.get("up_to"):
        acts.append(DeclineResourceFromDiscard())
    return acts


# ── Discard a same-named hand card to give 2 Experience (discard_for_experience) ──

@dataclass
class SelectDiscardForExperience(Action):
    """Discard the chosen hand card and give 2 Experience to a same-named unit."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_experience"):
            raise IllegalActionError("No discard_for_experience decision pending")
        from swu.engine.state import Zone
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard candidate")
        ps = s.player_by_id(ctx["controller_id"])
        card = next(c for c in ps.hand if c.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(s, card)
        name = card.card_def.display_name
        target = None
        for arena in (ps.ground_arena, ps.space_arena):
            for u in arena:
                if u.card_def.display_name == name:
                    target = u
                    break
            if target is not None:
                break
        if target is not None:
            attach_token(s, ps, target, "Experience")
            attach_token(s, ps, target, "Experience")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_experience",
            choice=f"discarded {name}, gave 2 Experience"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Discard {self.instance_id} to give 2 Experience"


@dataclass
class DeclineDiscardForExperience(Action):
    """Decline Echo's optional discard ("You may discard a card")."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_experience"):
            raise IllegalActionError("No discard_for_experience decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_experience", choice="declined"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to discard for Experience"


def push_discard_for_experience(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'discard_for_experience' decision (Echo SHD_99): the candidates are the
    controller's hand cards whose name matches a friendly unit in play.  Fizzles
    cleanly if no hand card matches (nothing to gain from the optional discard)."""
    ps = s.player_by_id(source_ci.owner_id)
    unit_names = {u.card_def.display_name
                  for arena in (ps.ground_arena, ps.space_arena) for u in arena}
    candidate_ids = [c.instance_id for c in ps.hand
                     if c.card_def.display_name in unit_names]
    if not candidate_ids:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="discard_for_experience",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id, kind="discard_for_experience"))


def _discard_for_experience_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_for_experience decision (always includes a
    Decline for the "you may")."""
    ctx = top.context
    acts: list[Action] = [SelectDiscardForExperience(cid) for cid in ctx["candidate_ids"]]
    acts.append(DeclineDiscardForExperience())
    return acts


# ── Restock SOR_252: bottom up-to-N cards from a discard pile ─────────────────

@dataclass
class SelectBottomDiscardCard(Action):
    """Select one card from a discard pile to bottom (Restock SOR_252)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_discard"):
            raise IllegalActionError("No bottom_from_discard decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard candidate")
        if self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} already selected")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _finish_bottom_from_discard(s)
        return s

    def describe(self) -> str:
        return f"Bottom {self.instance_id} from a discard pile"


@dataclass
class FinishBottomFromDiscard(Action):
    """Stop selecting: bottom the chosen discard cards (always offered — "up to N")."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_discard"):
            raise IllegalActionError("No bottom_from_discard decision pending")
        return _finish_bottom_from_discard(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish bottoming cards from the discard pile"


def _finish_bottom_from_discard(s: GameState) -> GameState:
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    selected_set = set(ctx["selected_ids"])

    chosen: list[CardInstance] = []
    if ctx.get("disposition") == "choose_only":
        # "Choose another card in your discard pile" (Psychometry LOF_219) — the
        # decision is only a SELECTOR here; nothing moves.  The payoff reads the
        # chosen card's traits.
        for pl in s.players:
            for ci in pl.discard:
                if ci.instance_id in selected_set:
                    chosen.append(ci)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="bottom_from_discard",
            choice=("chose "
                    + (", ".join(c.card_def.display_name for c in chosen)
                       or "nothing")),
        ))
        window = ctx.get("then_deck_search_shared_trait")
        src_res = s.find_instance(ctx["source_id"])
        if window and chosen and src_res is not None:
            wanted = set()
            for c in chosen:
                wanted |= set(getattr(c.card_def, "traits", None) or ())
            push_deck_search(
                s, src_res[1], count=1, up_to=False, window=int(window),
                eligible=lambda cd: bool(
                    wanted & set(getattr(cd, "traits", None) or ())))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    for pl in s.players:
        for ci in list(pl.discard):
            if ci.instance_id in selected_set:
                pl.discard.remove(ci)
                chosen.append(ci)

    # Random bottom order (deck_search bottoming pattern).
    rng = s.make_rng()
    rng.shuffle(chosen)
    s.rng_state = rng.getstate()

    for ci in chosen:
        ci.zone = Zone.DECK
        ci.face_down = True
        ci.exhausted = False
        ci.damage = 0
        s.player_by_id(ci.owner_id).deck.append(ci)  # bottom

    names = ", ".join(ci.card_def.display_name for ci in chosen) or "nothing"
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="bottom_from_discard",
        choice=f"bottomed {len(chosen)} ({names})",
    ))
    # "…and create that many <token> tokens" (Reprocess TWI_88) — the payoff scales
    # with how many cards were actually bottomed, so it is settled here, after the
    # pop, and yields nothing when the controller chose none.
    token = ctx.get("then_create_token")
    if token and chosen:
        _create_token_units(s, s.player_by_id(ctx["controller_id"]),
                            token, len(chosen))
    # "…on the bottom of your deck.  If you do, draw a card" (Fives TWI_216) — the
    # same shape: the payoff is bound to an actual bottoming, so choosing none
    # draws nothing.
    draw = int(ctx.get("then_draw") or 0)
    if draw and chosen:
        _draw_cards(s, s.player_by_id(ctx["controller_id"]), draw)
    # "…on the bottom of your deck.  If you do, create a Credit token" (Scavenging
    # Sandcrawler LAW_238) — the Credit sibling of the two payoffs above, likewise
    # bound to an actual bottoming, so choosing none creates nothing.
    credits = int(ctx.get("then_create_credit") or 0)
    if credits and chosen:
        from swu.engine.tokens import create_credit_token
        beneficiary = s.player_by_id(ctx["controller_id"])
        for _ in range(credits):
            create_credit_token(s, beneficiary)
    # "…If you do, play a unit from your hand and give 2 Experience tokens to it"
    # (The Burden of Masters LOF_125) — the third payoff in the same settle-at-the-
    # finish family, so bottoming nothing plays nothing.  The play itself carries
    # the Experience through push_play_from_hand's own ``then_select_token`` rider.
    play_cfg = ctx.get("then_play_from_hand")
    if play_cfg and chosen:
        source_result = s.find_instance(ctx["source_id"])
        if source_result is not None:
            push_play_from_hand(s, source_result[1], **dict(play_cfg))
    # "…If you do, deal 1 damage to each enemy base" (0-0-0 LAW_174) — the same
    # settle-at-the-finish family; bottoming nothing deals nothing.  Routed through
    # ``base_damage_after_prevention`` like every other base-damage site.
    # "…put that card on the bottom of your deck and heal 3 damage from your base"
    # (Trask Walker ASH_133) — the heal flavour of the same settle-at-the-finish
    # family, routed through ``_apply_heal`` so the Wolffe SOR_160 base-heal lock and
    # the heal observers still see it.  Bottoming nothing heals nothing.
    heal_base = int(ctx.get("then_heal_base") or 0)
    if heal_base and chosen:
        src_res = s.find_instance(ctx["source_id"])
        beneficiary = s.player_by_id(ctx["controller_id"])
        if src_res is not None and beneficiary.base_instance is not None:
            from swu.abilities.resolver import _apply_heal
            _apply_heal(s, src_res[1], beneficiary.base_instance.instance_id,
                        heal_base)
    base_dmg = int(ctx.get("then_damage_enemy_base") or 0)
    if base_dmg and chosen:
        for p in s.players:
            if p.player_id == ctx["controller_id"] or p.base_instance is None:
                continue
            amt = base_damage_after_prevention(s, p.base_instance, base_dmg)
            if amt > 0:
                p.base_instance.damage += amt
                record_base_damage(s, p.player_id, amt)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_bottom_from_discard(
    s: GameState, source_ci: CardInstance, *, count: int,
    own_only: bool = False,
    eligible: Optional[Callable[[object], bool]] = None,
    then_create_token: Optional[str] = None,
    then_draw: int = 0,
    then_create_credit: int = 0,
    then_play_from_hand: Optional[dict] = None,
    then_damage_enemy_base: int = 0,
    then_heal_base: int = 0,
    exclude_ids: Optional[frozenset] = None,
    disposition: str = "bottom",
    then_deck_search_shared_trait: Optional[int] = None,
) -> None:
    """Push a 'bottom_from_discard' decision (Restock SOR_252): choose up to
    ``count`` cards across both players' discard piles; each goes to the bottom of
    its owner's deck in random order.  Fizzles cleanly if no discard card exists.

    ``own_only`` narrows the candidates to the CONTROLLER's own discard pile ("in
    YOUR discard pile") and ``eligible`` (a predicate on the card_def) narrows them
    by card type/trait ("choose up to 4 UNITS") — Reprocess TWI_88, whose
    ``then_create_token`` also creates one token unit of that name per card
    actually bottomed.  ``then_draw`` is the same shape for a draw payoff ("put a
    Clone unit from your discard pile on the bottom of your deck.  If you do, draw
    a card" — Fives TWI_216): it too is settled at the finish, so bottoming
    nothing draws nothing.  ``then_create_credit`` is the same shape again for the
    Credit economy ("If you do, create a Credit token" — Scavenging Sandcrawler
    LAW_238).

    ``then_damage_enemy_base`` is the same settle-at-the-finish shape for base
    damage — "You may put an Aggression card from your discard pile on the bottom of
    your deck.  If you do, deal 1 damage to each enemy base" (0-0-0 LAW_174) — and
    ``then_heal_base`` its heal mirror, "put that card on the bottom of your deck and
    heal 3 damage from your base" (Trask Walker ASH_133).

    ``then_play_from_hand`` is the same settle-at-the-finish shape for a whole
    ``push_play_from_hand`` (its kwargs as a dict) — "Put a Force unit from your
    discard pile on the bottom of your deck.  If you do, play a unit from your hand
    and give 2 Experience tokens to it" (The Burden of Masters LOF_125).

    ``disposition="choose_only"`` makes the decision a pure SELECTOR — nothing is
    moved — for "Choose another card in your discard pile.  Search the top N cards
    of your deck for a card that shares a trait with the chosen card, reveal it, and
    draw it" (Psychometry LOF_219), whose ``then_deck_search_shared_trait`` window
    runs an ordinary ``deck_search`` over the chosen card's traits.

    ``exclude_ids`` drops specific instances from the candidate set — an EVENT is
    already in its owner's discard by the time its own ability resolves, so "put
    ANOTHER card in a discard pile …" must exclude the event itself (Commence
    Patrol JTL_205) while still offering a second copy of the same card."""
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    piles = ([s.player_by_id(controller_id)] if own_only else list(s.players))
    skip = set(exclude_ids or ())
    candidate_ids = [ci.instance_id for pl in piles for ci in pl.discard
                     if ci.instance_id not in skip
                     and (eligible is None or eligible(ci.card_def))]
    if not candidate_ids or int(count) <= 0:
        return
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="bottom_from_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": int(count),
            "then_create_token": then_create_token,
            "then_draw": int(then_draw),
            "then_create_credit": int(then_create_credit),
            "then_play_from_hand": dict(then_play_from_hand or {}) or None,
            "then_damage_enemy_base": int(then_damage_enemy_base),
            "then_heal_base": int(then_heal_base),
            "disposition": str(disposition),
            "then_deck_search_shared_trait": then_deck_search_shared_trait,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="bottom_from_discard"))


def push_return_from_discard(
    s: GameState, source_ci: CardInstance,
    *,
    count: int,
    eligible: Callable[[object], bool],
    up_to: bool = True,
    eligible_instance: Callable[["CardInstance"], bool] | None = None,
) -> None:
    """Push a 'return_from_discard' decision: "Return up to ``count`` <eligible>
    cards from your discard pile to your hand."

    Parameters
    ----------
    count
        Maximum number of cards the controller may return.
    eligible
        Predicate on a card_def — only matching cards in the controller's discard
        pile are offered as candidates.  Evaluated once, at push time; the
        resulting ids are stored, so the decision context stays JSON-serialisable.
    up_to
        True (the only mode today) means a FinishReturnFromDiscard is always
        offered, so returning 0 is legal ("You may return …").
    eligible_instance
        Optional extra predicate on the *CardInstance* (not just its card_def), so
        an instance-level restriction can be applied alongside ``eligible`` — e.g.
        "units that were **defeated this phase**" (Admiral Trench TWI_86), which is
        a property of the instance (its id in ``game_memory.units_defeated_this_round``),
        not of the printed card.  Like ``eligible`` it is evaluated once at push
        time and only the resulting ids are stored.

    Pushed only when at least one eligible card is present; otherwise the effect
    fizzles cleanly with no prompt and the caller hands the turn over.
    """
    ps = s.player_by_id(source_ci.owner_id)
    candidate_ids = [ci.instance_id for ci in ps.discard
                     if eligible(ci.card_def)
                     and (eligible_instance is None or eligible_instance(ci))]
    if not candidate_ids or int(count) <= 0:
        return  # nothing eligible — fizzle cleanly
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="return_from_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": int(count),
            "up_to": bool(up_to),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="return_from_discard",
    ))


def _return_from_discard_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top return_from_discard decision (never empty: a
    FinishReturnFromDiscard is always offered for the "up to" / "you may")."""
    ctx = top.context
    selected = set(ctx["selected_ids"])
    remaining = [cid for cid in ctx["candidate_ids"] if cid not in selected]
    acts: list[Action] = [SelectDiscardCard(cid) for cid in remaining]
    acts.append(FinishReturnFromDiscard())
    return acts


# ── Choose N different-named discard cards, return 1 of them at random ─────────

@dataclass
class SelectDistinctDiscardCard(Action):
    """Select one differently-named card for Doctor Aphra SHD_15's deploy pick."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_distinct_return_random"):
            raise IllegalActionError("No select_distinct_return_random decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in _distinct_discard_candidates(s, ctx):
            raise IllegalActionError(f"{self.instance_id} is not a legal distinct-name pick")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["count"]):
            return _finish_distinct_return_random(s)
        return s

    def describe(self) -> str:
        return f"Choose {self.instance_id} (different name) from the discard pile"


def _distinct_discard_candidates(s: GameState, ctx: dict) -> list[str]:
    """Instance ids in the controller's discard that are still legal to pick: not
    already selected and bearing a name not shared by any already-selected card."""
    ps = s.player_by_id(ctx["controller_id"])
    selected = set(ctx["selected_ids"])
    chosen_names = {ci.card_def.display_name for ci in ps.discard
                    if ci.instance_id in selected}
    return [ci.instance_id for ci in ps.discard
            if ci.instance_id not in selected
            and ci.card_def.display_name not in chosen_names]


def _finish_distinct_return_random(s: GameState) -> GameState:
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    selected = list(ctx["selected_ids"])
    chosen = [ci for ci in ps.discard if ci.instance_id in set(selected)]
    returned = None
    if chosen:
        rng = s.make_rng()
        returned = rng.choice(chosen)
        s.rng_state = rng.getstate()
        ps.discard.remove(returned)
        returned.zone = Zone.HAND
        returned.face_down = False
        ps.hand.append(returned)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="select_distinct_return_random",
        choice=(f"returned {returned.card_def.display_name} at random"
                if returned is not None else "returned nothing"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_select_distinct_return_random(
    s: GameState, source_ci: CardInstance, *, count: int) -> None:
    """Push Doctor Aphra SHD_15's deploy decision.  Pushed only when the controller
    has ≥ ``count`` distinct card names in their discard pile; otherwise "Choose N
    cards … with different names" cannot be satisfied, so the effect does nothing."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    distinct_names = {ci.card_def.display_name for ci in ps.discard}
    if int(count) <= 0 or len(distinct_names) < int(count):
        return
    owner_idx = s.player_index(controller_id)
    candidate_ids = [ci.instance_id for ci in ps.discard]
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="select_distinct_return_random",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "count": int(count),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id, kind="select_distinct_return_random"))


# ── Choose N different-named discard cards, return 1 at random (Aphra SHD_15) ─

def _select_distinct_return_random_actions(state: GameState, top: PendingDecision) -> list[Action]:
    return [SelectDistinctDiscardCard(cid)
            for cid in _distinct_discard_candidates(state, top.context)]


# ── Bottom up-to-N cards from a discard pile (Restock SOR_252) ─────────

def _bottom_from_discard_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    selected = set(ctx["selected_ids"])
    acts = [SelectBottomDiscardCard(cid) for cid in ctx["candidate_ids"]
            if cid not in selected]
    acts.append(FinishBottomFromDiscard())
    return acts


# ── Name a card in an opponent's hand; one copy is discarded (Chimaera

#    SOR_185 On Attack) ─────────────────────────────────────────────────────
def _name_and_discard_actions(state: GameState, top: PendingDecision) -> list[Action]:
    names = sorted(top.context.get("eligible_names")
                   or {c["card_name"] for c in top.context["revealed_hand"]})
    acts: list[Action] = [NameAndDiscard(n) for n in names]
    if top.context.get("optional"):
        acts.append(DeclineNameAndDiscard())
    return acts


# ── Recycle-a-discarded-unit-for-scaling-damage (The Sarlacc of Carkoon LAW_163)

@dataclass
class SelectDiscardUnitForDamage(Action):
    """Pick a unit from your discard pile to put on the bottom of your deck; its
    power becomes the damage magnitude (The Sarlacc of Carkoon LAW_163)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_unit_damage"
                or state.pending_decisions[-1].context.get("stage") != "select"):
            raise IllegalActionError("No discard_unit_damage (select) decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discard-unit candidate")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        # Bottom the chosen unit (discard pile → bottom of deck, face-down).  A
        # unit defeated while exhausted lands in discard still exhausted; a card
        # in the deck must be reset (no exhaust/damage out of play), so clear both.
        unit = next(ci for ci in ps.discard if ci.instance_id == self.instance_id)
        ps.discard.remove(unit)
        unit.zone = Zone.DECK
        unit.face_down = True
        unit.exhausted = False
        unit.damage = 0
        ps.deck.append(unit)
        ctx["amount"] = int(getattr(unit.card_def, "power", 0) or 0)
        ctx["recycled_name"] = unit.card_def.display_name
        # Advance to the damage step only if there is a legal target.
        if _sacrifice_damage_targets(s, ctx):
            ctx["stage"] = "target"
            return s
        return _resolve_discard_unit_damage(s, top, None)

    def describe(self) -> str:
        return f"Recycle {self.instance_id} from discard (deal its power)"


@dataclass
class ChooseDiscardDamageTarget(Action):
    """Deal the recycled unit's power to the chosen enemy ground unit and pop the
    discard_unit_damage decision (The Sarlacc of Carkoon LAW_163)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_unit_damage"
                or state.pending_decisions[-1].context.get("stage") != "target"):
            raise IllegalActionError("No discard_unit_damage (target) decision pending")
        if self.target_id not in _sacrifice_damage_targets(
                state, state.pending_decisions[-1].context):
            raise IllegalActionError(f"{self.target_id} is not a legal damage target")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_discard_unit_damage(s, top, self.target_id)

    def describe(self) -> str:
        return f"Deal recycled-unit damage to {self.target_id}"


def _resolve_discard_unit_damage(
    s: GameState, top, target_id: Optional[str]
) -> GameState:
    """Pop the discard_unit_damage decision, then deal the stored damage (if any).

    Damage is dealt AFTER popping (like push_sacrifice_resource_for_damage) so a
    defeat trigger from the damage lands on a clean stack."""
    ctx = top.context
    amount = int(ctx.get("amount", 0))
    recycled = ctx.get("recycled_name", "a unit")
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="discard_unit_damage",
        choice=(f"recycled {recycled}, dealt {amount} to {target_id}"
                if target_id else f"recycled {recycled} (no target)"),
    ))
    if target_id is not None and amount > 0:
        from swu.abilities.resolver import _apply_deal_damage
        source_result = s.find_instance(ctx["source_id"])
        source_name = (source_result[1].card_def.display_name
                       if source_result else None)
        _apply_deal_damage(s, target_id, amount, source_name=source_name)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_discard_unit_then_damage(
    s: GameState, source_ci: CardInstance, *,
    target_controller: str = "enemy",
    target_arena: Optional[str] = "ground",
) -> None:
    """Push a 'discard_unit_damage' decision (The Sarlacc of Carkoon LAW_163):
    "Put a unit from your discard pile on the bottom of your deck.  Deal damage
    equal to that unit's power to a <target_controller> <target_arena> unit."

    Pushed only when the controller's discard pile holds at least one unit (the
    recycle is mandatory-if-able); the damage step is conditional on a legal target
    existing at select time."""
    from swu.cards.models import Unit
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    candidate_ids = [ci.instance_id for ci in ps.discard if isinstance(ci.card_def, Unit)]
    if not candidate_ids:
        return  # no unit in the discard pile — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="discard_unit_damage",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "select",
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "amount": 0,
            "target_controller": target_controller,
            "target_arena": target_arena,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="discard_unit_damage",
    ))


def _discard_unit_damage_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_unit_damage decision (never empty)."""
    ctx = top.context
    if ctx.get("stage") == "select":
        return [SelectDiscardUnitForDamage(cid) for cid in ctx["candidate_ids"]]
    # stage "target"
    return [ChooseDiscardDamageTarget(t) for t in _sacrifice_damage_targets(state, ctx)]


# ── Discard-a-unit-as-a-cost, then search the deck (Great Pit of Carkoon LAW_23)

@dataclass
class DiscardForSearch(Action):
    """Discard the chosen card from your hand (the cost), then search your deck and
    draw the matching card (Great Pit of Carkoon LAW_23, R2-D2 TWI_193)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_search"):
            raise IllegalActionError("No discard_for_search decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a discardable card")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        unit = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(unit)
        unit.zone = Zone.DISCARD
        ps.discard.append(unit)
        note_hand_or_deck_discard(s, unit)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_search",
            choice=f"discarded {unit.card_def.display_name}",
        ))
        # Run the search (push a deck_search decision).  ``search_name`` None means
        # "any card" (R2-D2 "search for a card"); a string means name-match (Great
        # Pit's tutor); the window/count/up_to params are carried in the context.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is not None:
            search_name = ctx.get("search_name")
            ps_now = s.player_by_id(ctx["controller_id"])
            window = int(ctx.get("search_window", len(ps_now.deck)))
            count = int(ctx.get("search_count", 1))
            up_to = bool(ctx.get("search_up_to", False))

            def _eligible(cd, _name=search_name):
                if _name is None:
                    return True
                return (getattr(cd, "name", None) or "") == _name

            push_deck_search(s, source_result[1], count=count, eligible=_eligible,
                             up_to=up_to, window=window)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Discard {self.instance_id} to search the deck"


@dataclass
class FinishDiscardForSearch(Action):
    """Decline the optional "you may discard a card" of a discard_for_search
    decision (R2-D2 TWI_193) — pop with no discard, no search."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_for_search"):
            raise IllegalActionError("No discard_for_search decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="discard_for_search",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to discard"


def push_discard_for_search(
    s: GameState, source_ci: CardInstance, *,
    search_window: int,
    search_count: int = 1,
    search_up_to: bool = False,
    search_name: str | None = None,
    discard_units_only: bool = True,
    optional: bool = False,
) -> None:
    """Push a 'discard_for_search' decision: "Discard a card from your hand, then
    search the top ``search_window`` cards of your deck and draw the matching
    card(s)."

    Parameters
    ----------
    search_window / search_count / search_up_to
        Forwarded to the follow-up ``push_deck_search`` (how deep to search, how
        many to take, and whether taking 0 is legal).
    search_name
        ``None`` (R2-D2 TWI_193 "search for a card") — any card is eligible.
        A string (Great Pit of Carkoon LAW_23) — only a card with that exact name.
    discard_units_only
        True (Great Pit) — only Units may be discarded as the cost.  False (R2-D2)
        — any card.
    optional
        False (Great Pit) — the discard is a mandatory cost (no decline).  True
        (R2-D2 "You may discard a card from your hand") — a FinishDiscardForSearch
        decline is offered.

    Pushed only when ≥1 eligible discard candidate is in hand; otherwise the effect
    fizzles cleanly with no prompt (so R2-D2's mandatory trigger no-ops on an empty
    hand without needing a hand-size condition)."""
    from swu.cards.models import Unit
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    if discard_units_only:
        candidate_ids = [ci.instance_id for ci in ps.hand if isinstance(ci.card_def, Unit)]
    else:
        candidate_ids = [ci.instance_id for ci in ps.hand]
    if not candidate_ids:
        return  # nothing to discard — fizzle cleanly (gated upstream)
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="discard_for_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "candidate_ids": candidate_ids,
            "search_name": search_name,
            "search_window": int(search_window),
            "search_count": int(search_count),
            "search_up_to": bool(search_up_to),
            "optional": bool(optional),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="discard_for_search",
    ))


def push_discard_unit_for_search(
    s: GameState, source_ci: CardInstance, *, search_name: str,
) -> None:
    """Push a 'discard_for_search' decision (Great Pit of Carkoon LAW_23): discard a
    chosen unit from your hand, then search your deck for a card named
    ``search_name``, reveal it, and draw it.

    Pushed only when the controller holds ≥1 Unit in hand (the discard cost is
    mandatory-if-able and the only way out is to pick a unit); the epic action is
    additionally gated by CONTROLLER_HAS_UNIT_IN_HAND so it is not offered (and the
    once-per-game epic not wasted) when there is nothing to discard.

    A thin wrapper over the generalised ``push_discard_for_search`` (whole-deck
    window, name-match, units-only, mandatory)."""
    push_discard_for_search(
        s, source_ci,
        search_window=len(s.player_by_id(source_ci.owner_id).deck),
        search_count=1, search_up_to=False,
        search_name=search_name, discard_units_only=True, optional=False,
    )


def _discard_for_search_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_for_search decision.  Never empty — the
    decision is only pushed with ≥1 discardable card; a FinishDiscardForSearch
    decline is added when the discard is "you may" (R2-D2 TWI_193)."""
    acts: list[Action] = [DiscardForSearch(cid) for cid in top.context["candidate_ids"]]
    if top.context.get("optional"):
        acts.append(FinishDiscardForSearch())
    return acts


# ── Recur-from-discard then buff (Luminous Beings LOF_104) ────────────────────

@dataclass
class SelectRecurUnit(Action):
    """Recur a matching unit from your discard pile (recur_and_buff stage 'recur',
    Luminous Beings LOF_104).  Auto-advances to the buff stage at the cap."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "recur"):
            raise IllegalActionError("No recur_and_buff (recur) decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"] or self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a recurrable unit")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ctx["selected_ids"].append(self.instance_id)
        remaining = [cid for cid in ctx["candidate_ids"] if cid not in ctx["selected_ids"]]
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]) or not remaining:
            return _finish_recur(s, top)
        return s

    def describe(self) -> str:
        return f"Put {self.instance_id} on the bottom of your deck"


@dataclass
class FinishRecur(Action):
    """Stop recurring units ("up to N") and move to the buff stage (Luminous
    Beings LOF_104)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "recur"):
            raise IllegalActionError("No recur_and_buff (recur) decision pending")
        s = copy.deepcopy(state)
        return _finish_recur(s, s.pending_decisions[-1])

    def describe(self) -> str:
        return "Finish putting units on the bottom of the deck"


def _finish_recur(s: GameState, top) -> GameState:
    """Move the selected discard units to the bottom of the deck in a random order,
    then either advance to the buff stage (if any were recurred and there is a unit
    to buff) or pop the decision."""
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    selected_set = set(ctx["selected_ids"])
    recurred = [ci for ci in ps.discard if ci.instance_id in selected_set]
    # Random order onto the bottom of the deck (deterministic via the seeded rng).
    rng = s.make_rng()
    rng.shuffle(recurred)
    s.rng_state = rng.getstate()
    for ci in recurred:
        ps.discard.remove(ci)
        ci.zone = Zone.DECK
        ci.face_down = True
        ci.exhausted = False
        ci.damage = 0
        ps.deck.append(ci)
    k = len(recurred)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="recur_and_buff",
        choice=f"bottomed {k} unit(s)",
    ))
    ctx["stage"] = "buff"
    ctx["buff_remaining"] = k
    ctx["buffed_ids"] = []
    # Advance to the buff stage only if we recurred ≥1 unit AND there is an
    # eligible unit to buff; otherwise the effect is done.
    if k > 0 and _recur_buff_targets(s, ctx):
        return s
    s.pending_decisions.pop()
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _recur_buff_targets(state: GameState, ctx: dict) -> list[str]:
    """Eligible buff targets for the recur_and_buff 'buff' stage (any in-play unit
    not already buffed this resolution)."""
    from swu.abilities.resolver import _gather_legal_targets, _spec_matches_ci
    from swu.abilities.registry import TargetSpec
    spec = TargetSpec(controller=ctx.get("buff_controller", "any"), kind="unit")
    buffed = set(ctx.get("buffed_ids", []))
    source_result = state.find_instance(ctx["source_id"])
    if source_result is not None:
        _, source_ci = source_result
        ids = _gather_legal_targets(state, spec, source_ci, {})
    else:
        ids = [ci.instance_id
               for ps in state.players
               for ci in ps.ground_arena + ps.space_arena
               if _spec_matches_ci(spec, ci, ci, state, {})]
    return [tid for tid in ids if tid not in buffed]


@dataclass
class SelectBuffTarget(Action):
    """Give the chosen unit +P/+H for this phase (recur_and_buff stage 'buff',
    Luminous Beings LOF_104).  Auto-pops once K units are buffed / none remain."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "buff"):
            raise IllegalActionError("No recur_and_buff (buff) decision pending")
        ctx = state.pending_decisions[-1].context
        if self.instance_id not in _recur_buff_targets(state, ctx):
            raise IllegalActionError(f"{self.instance_id} is not an eligible buff target")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        from swu.abilities.resolver import _make_modifier
        from swu.abilities.registry import Duration
        mod = _make_modifier(
            s, ctx["source_id"], self.instance_id,
            power=int(ctx["power"]), hp=int(ctx["hp"]),
            duration=Duration.THIS_PHASE,
        )
        s.modifiers.append(mod)
        ctx["buffed_ids"].append(self.instance_id)
        ctx["buff_remaining"] = int(ctx["buff_remaining"]) - 1
        if int(ctx["buff_remaining"]) <= 0 or not _recur_buff_targets(s, ctx):
            return _finish_recur_buff(s, top)
        return s

    def describe(self) -> str:
        return f"Give {self.instance_id} a stat bonus for this phase"


@dataclass
class FinishRecurBuff(Action):
    """Stop buffing units ("that many", capped by available) — resolve (Luminous
    Beings LOF_104)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "recur_and_buff"
                or state.pending_decisions[-1].context.get("stage") != "buff"):
            raise IllegalActionError("No recur_and_buff (buff) decision pending")
        s = copy.deepcopy(state)
        return _finish_recur_buff(s, s.pending_decisions[-1])

    def describe(self) -> str:
        return "Finish buffing units"


def _finish_recur_buff(s: GameState, top) -> GameState:
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="recur_and_buff",
        choice=f"buffed {len(ctx.get('buffed_ids', []))} unit(s)",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_recur_and_buff(
    s: GameState, source_ci: CardInstance, *,
    max_select: int, trait: str, power: int, hp: int,
    buff_controller: str = "any",
) -> None:
    """Push a 'recur_and_buff' decision (Luminous Beings LOF_104): "Put up to
    ``max_select`` ``trait`` units from your discard pile on the bottom of your
    deck in a random order.  Give that many units +``power``/+``hp`` for this
    phase."

    Candidates are the controller's discard-pile Units carrying ``trait``.  Pushed
    only when ≥1 such unit exists (with none, "put 0, buff 0" is a clean no-op so
    the caller hands the turn over).  The buff targets (``buff_controller="any"``
    by default, mirroring the literal "units") are recomputed live so the cap of K
    = the number recurred is honoured even as units leave play."""
    from swu.cards.models import Unit
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    candidate_ids = [ci.instance_id for ci in ps.discard
                     if isinstance(ci.card_def, Unit) and trait in ci.card_def.traits]
    if not candidate_ids or int(max_select) <= 0:
        return  # no recurrable unit — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="recur_and_buff",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "recur",
            "candidate_ids": candidate_ids,
            "selected_ids": [],
            "max_select": int(max_select),
            "power": int(power),
            "hp": int(hp),
            "buff_controller": buff_controller,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="recur_and_buff",
    ))


def _recur_and_buff_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top recur_and_buff decision (never empty — a Finish is
    always offered for the 'up to' / 'that many' of each stage)."""
    ctx = top.context
    if ctx.get("stage") == "recur":
        selected = set(ctx["selected_ids"])
        remaining = [cid for cid in ctx["candidate_ids"] if cid not in selected]
        acts: list[Action] = [SelectRecurUnit(cid) for cid in remaining]
        acts.append(FinishRecur())
        return acts
    acts = [SelectBuffTarget(tid) for tid in _recur_buff_targets(state, ctx)]
    acts.append(FinishRecurBuff())
    return acts


# ── Each player discards down to a chosen hand size (Smoke and Cinders SOR_174) ─

@dataclass
class SelectExcessHandCardToDiscard(Action):
    """The current player discards a chosen card from their hand toward the target
    hand size (Smoke and Cinders SOR_174).  Advances to the next player once the
    current player is down to ``keep`` cards, or resolves the decision."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "discard_excess_from_hand"):
            raise IllegalActionError("No discard-excess decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        current = ctx["order"][ctx["idx"]]
        ps = s.player_by_id(current)
        card = next((ci for ci in ps.hand
                     if ci.instance_id == self.instance_id), None)
        if card is None or len(ps.hand) <= _discard_excess_keep(ctx, current):
            raise IllegalActionError(
                f"{self.instance_id} is not a discardable excess card")
        ps.hand.remove(card)
        card.zone = Zone.DISCARD
        ps.discard.append(card)
        note_hand_or_deck_discard(s, card)
        tally = dict(ctx.get("discarded", {}))
        tally[current] = tally.get(current, 0) + 1
        ctx["discarded"] = tally
        s.event_log.append(DecisionResolved(
            deciding_player_id=current,
            kind="discard_excess_from_hand",
            choice=f"discarded {card.card_def.display_name}",
        ))
        # Advance past any players already down to (or below) the target size.
        while (ctx["idx"] < len(ctx["order"])
               and len(s.player_by_id(ctx["order"][ctx["idx"]]).hand)
               <= _discard_excess_keep(ctx, ctx["order"][ctx["idx"]])):
            ctx["idx"] += 1
        if ctx["idx"] < len(ctx["order"]):
            top.deciding_player_id = ctx["order"][ctx["idx"]]
            s.active_player_index = s.player_index(top.deciding_player_id)
            return s
        # Everyone is down to size — record the discard observers and pop.
        s.pending_decisions.pop()
        for pid, n in ctx["discarded"].items():
            if n:
                record_hand_discard(s, pid)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Discard {self.instance_id} (down to hand size)"


def _discard_excess_keep(ctx: dict, player_id: str) -> int:
    """The target hand size for ``player_id`` in a discard_excess_from_hand decision.

    Two shapes share the walk: the printed "discard down to N" (a single ``keep``
    for everyone — Smoke and Cinders SOR_174) and "each player discards N cards"
    (Guerilla Insurgency TWI_177), which is per-player and so is pre-computed into
    a ``keeps`` map at push time from each hand's size.  Hand sizes only change
    through this decision itself, so pinning the targets up front is exact."""
    keeps = ctx.get("keeps")
    if keeps is not None:
        return int(keeps.get(player_id, 0))
    return int(ctx["keep"])


def push_discard_excess_from_hand(
    s: GameState, source_ci: CardInstance, *, keep: int = 2,
    count: Optional[int] = None,
) -> None:
    """Push a 'discard_excess_from_hand' decision (Smoke and Cinders SOR_174): each
    player discards down to ``keep`` cards of their choice, the source's controller
    first.  Pushed only when ≥1 player holds more than ``keep`` cards; otherwise it
    fizzles cleanly with no prompt.

    ``count`` switches to the sibling shape "each player discards ``count`` cards of
    their choice" (Guerilla Insurgency TWI_177) — each player's target hand size is
    their current size minus ``count``, floored at 0, so a short hand just discards
    all of it."""
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    order = [controller_id, opponent_id]
    keeps = None
    if count is not None:
        keeps = {pid: max(0, len(s.player_by_id(pid).hand) - int(count))
                 for pid in order}
    ctx = {
        "source_id": source_ci.instance_id,
        "order": order,
        "idx": 0,
        "keep": int(keep),
        "discarded": {},
    }
    if keeps is not None:
        ctx["keeps"] = keeps
    idx = 0
    while (idx < len(order)
           and len(s.player_by_id(order[idx]).hand)
           <= _discard_excess_keep(ctx, order[idx])):
        idx += 1
    if idx >= len(order):
        return  # nobody has excess — fizzle
    ctx["idx"] = idx
    dec = PendingDecision(
        deciding_player_id=order[idx],
        kind="discard_excess_from_hand",
        context=ctx,
        after_resolve_player_index=s.player_index(controller_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(order[idx])
    s.event_log.append(DecisionPushed(
        deciding_player_id=order[idx],
        kind="discard_excess_from_hand",
    ))


def _discard_excess_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top discard_excess_from_hand decision: the current
    player discards any one of their hand cards (never empty — the idx always points
    at a player still holding more than ``keep`` cards)."""
    ctx = top.context
    ps = state.player_by_id(ctx["order"][ctx["idx"]])
    if len(ps.hand) <= _discard_excess_keep(ctx, ps.player_id):
        return []
    return [SelectExcessHandCardToDiscard(ci.instance_id) for ci in ps.hand]


# ── Name a card; an opponent reveals their hand and discards a card of that name

@dataclass
class NameAndDiscard(Action):
    """The controller names a card present in the opponent's revealed hand; one
    opponent card of that name is discarded (Chimaera SOR_185 On Attack)."""
    card_name: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "name_and_discard"):
            raise IllegalActionError("No name-and-discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        opp = s.player_by_id(ctx["opponent_id"])
        names = set(ctx.get("eligible_names")
                    or {c["card_name"] for c in ctx["revealed_hand"]})
        if self.card_name not in names:
            raise IllegalActionError(
                f"{self.card_name!r} is not a nameable card in the revealed hand")
        s.pending_decisions.pop()
        want_type = ctx.get("card_type")
        victim = next((ci for ci in opp.hand
                       if ci.card_def.display_name == self.card_name
                       and _name_discard_type_ok(ci.card_def, want_type)), None)
        if victim is not None:
            opp.hand.remove(victim)
            victim.zone = Zone.DISCARD
            opp.discard.append(victim)
            note_hand_or_deck_discard(s, victim)
            record_hand_discard(s, opp.player_id)
            # "If you do, that player draws a card" (Bazine Netal SHD_184).
            if ctx.get("discarder_draws"):
                _draw_cards(s, opp, 1)
            # "If the discarded card is a UNIT, for this phase you may play it from
            # their discard pile, ignoring its aspect penalties" (Mother Talzin
            # TS26_26) — the PAID cross-pile permission (Obi-Wan Kenobi SEC_205),
            # keyed to the naming player and pinned to this one instance.
            if ctx.get("then_foreign_discard_play"):
                from swu.cards.models import Unit
                if isinstance(victim.card_def, Unit):
                    led = s.game_memory.foreign_discard_play_this_phase
                    led.setdefault(ctx["controller_id"], []).append(
                        victim.instance_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="name_and_discard",
            choice=f"named {self.card_name}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Name {self.card_name}"


@dataclass
class DeclineNameAndDiscard(Action):
    """Decline an OPTIONAL name-and-discard (Bazine Netal SHD_184's "You may
    discard 1 of those cards")."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "name_and_discard"):
            raise IllegalActionError("No name-and-discard decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="name_and_discard",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Discard nothing from the opponent's hand"


def _name_discard_type_ok(card_def, card_type: Optional[str]) -> bool:
    """Does ``card_def`` match a name_and_discard ``card_type`` filter?"""
    if not card_type:
        return True
    from swu.cards.models import Unit, Upgrade, Event
    if card_type == "non_unit":
        # "Discard a NON-UNIT card from it" (Tip the Scale LOF_226) — the
        # complement of the "unit" filter (an Upgrade or an Event).
        return not isinstance(card_def, Unit)
    cls = {"unit": Unit, "upgrade": Upgrade, "event": Event}.get(card_type)
    return cls is not None and isinstance(card_def, cls)


def push_name_and_discard(
    s: GameState, source_ci: CardInstance, *,
    optional: bool = False, discarder_draws: bool = False,
    card_type: Optional[str] = None, aspects_any: Optional[tuple] = None,
    then_foreign_discard_play: bool = False,
    namer_id: Optional[str] = None,
) -> None:
    """Push a 'name_and_discard' decision (Chimaera SOR_185 On Attack): the source's
    controller names a card in an opponent's hand and one copy is discarded.  Carries
    the opponent's hand identities (card_id + name only — never their hidden
    instance_ids, the look_hand precedent) in the controller's private context.
    Pushed only when the opponent holds ≥1 card; an empty hand fizzles with no
    prompt.

    ``optional`` adds a DeclineNameAndDiscard action ("You may discard 1 …");
    ``discarder_draws`` makes the discarding opponent draw a card after a discard
    ("If you do, that player draws a card") — Bazine Netal SHD_184, where the
    controller looks at the opponent's hand and may strip one card (the optimal-play
    collapse of a look-then-discard: the controller already sees the hand).

    ``card_type`` ("event" | "unit" | "upgrade") narrows what may be *named* while
    the whole hand is still revealed — "Look at an opponent's hand and discard an
    EVENT from it" (Jam Communications JTL_207).  With no card of that type in the
    hand the decision fizzles with no prompt, exactly as an empty hand does.

    ``aspects_any`` narrows it the other way: only a card sharing AT LEAST ONE of the
    listed aspects may be named — "discard a card from it that shares an aspect with
    that unit" (Hold For Questioning LAW_217, which passes the exhausted unit's own
    aspects).  Like ``card_type`` it filters what is NAMEABLE while the whole hand
    stays revealed, and an empty eligible set fizzles with no prompt (so the printed
    "If you do" costs nothing when their hand cannot match).

    ``then_foreign_discard_play`` is the settle-at-the-discard rider "If the discarded
    card is a unit, for this phase you may play it from their discard pile, ignoring
    its aspect penalties" (Mother Talzin TS26_26): the discarded instance is recorded
    in ``game_memory.foreign_discard_play_this_phase`` against the NAMING player — the
    PAID cross-pile permission built for Obi-Wan Kenobi SEC_205, whose branch of
    ``_enumerate_discard_play_actions`` already expresses the aspect waiver as a
    discount.  Pinned to that one instance, so a second copy already in the pile is
    not unlocked, and a non-unit discard unlocks nothing."""
    from swu.engine.events import HandInspected
    # ``namer_id`` shifts WHO names (and therefore whose hand is stripped) away from
    # the source's controller — the say_no SOR_233 decider shift.  "In player order,
    # each player discards a card from the hand of the player to their right"
    # (Reveal Intentions TS26_80) is two pushes of this decision, one per seat.
    controller_id = namer_id or source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    opp = s.players[1 - owner_idx]
    if not opp.hand:
        return
    want = {str(a) for a in (aspects_any or ())}
    eligible_names = sorted({
        ci.card_def.display_name for ci in opp.hand
        if _name_discard_type_ok(ci.card_def, card_type)
        and (not want or want & {getattr(a, "name", str(a))
                                 for a in (getattr(ci.card_def, "aspects", None) or ())})
    })
    if not eligible_names:
        return
    revealed = [
        {"card_id": ci.card_def.id, "card_name": ci.card_def.display_name}
        for ci in opp.hand
    ]
    s.event_log.append(HandInspected(
        inspecting_player_id=controller_id,
        revealed_player_id=opp.player_id,
        card_count=len(opp.hand),
    ))
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="name_and_discard",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "opponent_id": opp.player_id,
            "revealed_hand": revealed,
            "eligible_names": eligible_names,
            "card_type": card_type,
            "optional": bool(optional),
            "discarder_draws": bool(discarder_draws),
            "then_foreign_discard_play": bool(then_foreign_discard_play),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="name_and_discard",
    ))

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "return_from_discard":           _return_from_discard_actions,
    "resource_from_discard":         _resource_from_discard_actions,
    "discard_for_experience":        _discard_for_experience_actions,
    "select_distinct_return_random": _select_distinct_return_random_actions,
    "bottom_from_discard":           _bottom_from_discard_actions,
    "discard_unit_damage":           _discard_unit_damage_actions,
    "discard_for_search":            _discard_for_search_actions,
    "recur_and_buff":                _recur_and_buff_actions,
    "discard_excess_from_hand":      _discard_excess_from_hand_actions,
    "name_and_discard":              _name_and_discard_actions,
})
