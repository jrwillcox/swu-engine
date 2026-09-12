"""Revealing cards — to yourself, to an opponent, or to both.

Revealing is a rules action with consequences, not an information display. A revealed
identity becomes public knowledge, and the cards that were *not* revealed must stay hidden,
so this family is where a hidden-information bug would actually occur: it is the only place
that deliberately moves card identities from private state into something both players can
see.

That is why the engine checks it from the outside rather than trusting the code here.
``invariants.py``'s invariant 8 serialises ``state.view_for(pid)`` and scans the JSON for
opponent hand and deck identities, so a leak is caught by what the *view* renders rather
than by what this module intended -- which is the right way round, since a reveal
implemented correctly and rendered carelessly leaks just as badly.

The decisions themselves are the several shapes a reveal takes: reveal the top N and cull,
reveal until you choose to stop, reveal and reorder, reveal a deck top for *someone else* to
play, and the resource-reveal name-match effects.

**Disclose** is the odd member and the one worth reading before touching. It reveals aspect
icons from hand to unlock a payoff, and the requirement is an aspect **multiset** satisfied
*collectively*: ``_disclose_can_satisfy`` sums every card's aspects into one Counter and asks
whether the hand as a whole bears the required counts. So no single card need match, the
same card contributes all of its aspects at once, and "can I disclose?" is a question about
the hand rather than about any card in it. Getting that wrong would either refuse a legal
disclose or permit an illegal one, and neither shows up as an error -- only as the wrong
payoff.
"""
from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardPlayed, DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState, Zone
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.zones import (
    _apply_capture, _attach_upgrade, _create_token_units, _draw_cards, _eligible_upgrade_targets, _put_unit_in_play, _resolve_event_ability,
)
from swu.engine.actions.shared import (
    _candidate_card_views, _resource_top_of_deck,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard, push_granted_attack, push_select_token, record_hand_discard,
)
from swu.engine.actions.observers import (
    note_unit_healed,
)
from swu.engine.actions.distribute import (
    push_distribute_heal,
)
from swu.engine.actions.scheduling import (
    push_may_discard_else_damage,
)
from swu.engine.actions.discard import (
    push_name_and_discard,
)


# ── Reveal the top N; an opponent culls some; you draw one (reveal_cull_draw) ────

@dataclass
class CullRevealedCard(Action):
    """The OPPONENT discards one of the revealed cards."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cull_draw"):
            raise IllegalActionError("No reveal_cull_draw decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "cull":
            raise IllegalActionError("reveal_cull_draw is not in the cull stage")
        if self.instance_id not in ctx["remaining"]:
            raise IllegalActionError(f"{self.instance_id} is not a revealed card")
        ctx["remaining"].remove(self.instance_id)
        ctx["culled"].append(self.instance_id)
        if len(ctx["culled"]) >= int(ctx["cull_count"]) or not ctx["remaining"]:
            return _advance_reveal_cull_draw(s)
        return s

    def describe(self) -> str:
        return f"Discard revealed card {self.instance_id}"


@dataclass
class DrawRevealedCard(Action):
    """The CONTROLLER draws one survivor; the rest of the revealed cards are
    discarded."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cull_draw"):
            raise IllegalActionError("No reveal_cull_draw decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "draw":
            raise IllegalActionError("reveal_cull_draw is not in the draw stage")
        if self.instance_id not in ctx["remaining"]:
            raise IllegalActionError(f"{self.instance_id} is not a surviving card")
        return _finish_reveal_cull_draw(s, self.instance_id)

    def describe(self) -> str:
        return f"Draw revealed card {self.instance_id}"


def _advance_reveal_cull_draw(s: GameState) -> GameState:
    """The cull stage is done: discard the culled cards and hand the seat to the
    controller for the draw stage.  With nothing left to draw the decision resolves
    outright."""
    top = s.pending_decisions[-1]
    ctx = top.context
    _reveal_cull_discard(s, ctx, ctx["culled"])
    ctx["culled"] = []
    if not ctx["remaining"]:
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="reveal_cull_draw", choice="nothing left to draw"))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s
    ctx["stage"] = "draw"
    top.deciding_player_id = ctx["controller_id"]
    s.active_player_index = s.player_index(ctx["controller_id"])
    return s


def _reveal_cull_discard(s: GameState, ctx: dict, ids: list) -> None:
    """Move the named revealed cards out of the controller's deck into their discard
    pile (they are still in the deck — the decision never touched it)."""
    from swu.engine.state import Zone
    ps = s.player_by_id(ctx["controller_id"])
    for iid in list(ids):
        ci = next((c for c in ps.deck if c.instance_id == iid), None)
        if ci is None:
            continue
        ps.deck.remove(ci)
        ci.zone = Zone.DISCARD
        ps.discard.append(ci)
        note_hand_or_deck_discard(s, ci, from_deck=True)


def _finish_reveal_cull_draw(s: GameState, instance_id: str) -> GameState:
    """Pop the decision: the chosen survivor is drawn, every other survivor is
    discarded."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    rest = [iid for iid in ctx["remaining"] if iid != instance_id]
    drawn = next((c for c in ps.deck if c.instance_id == instance_id), None)
    if drawn is not None:
        ps.deck.remove(drawn)
        drawn.zone = Zone.HAND
        ps.hand.append(drawn)
    _reveal_cull_discard(s, ctx, rest)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_cull_draw",
        choice=(f"drew {drawn.card_def.display_name}" if drawn is not None
                else "drew nothing"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def push_reveal_cull_draw(
    s: GameState, source_ci: CardInstance, *, count: int = 4, cull: int = 2,
) -> None:
    """Push a 'reveal_cull_draw' decision (Admiral Trench JTL_14): reveal the top
    ``count`` cards of the controller's deck; an opponent discards ``cull`` of them;
    the controller then draws 1 of the survivors and discards the rest.

    ``cull`` is capped so at least one card survives for the draw (a short deck
    still yields a legal, meaningful decision), and the whole effect fizzles cleanly
    with no prompt on an empty deck."""
    ps = s.player_by_id(source_ci.owner_id)
    revealed = ps.deck[:int(count)]
    if not revealed:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    opponent_id = s.players[1 - owner_idx].player_id
    cull_n = max(0, min(int(cull), len(revealed) - 1))
    ids = [c.instance_id for c in revealed]
    dec = PendingDecision(
        deciding_player_id=opponent_id if cull_n else source_ci.owner_id,
        kind="reveal_cull_draw",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "opponent_id": opponent_id,
            "stage": "cull" if cull_n else "draw",
            "cull_count": cull_n,
            "culled": [],
            "remaining": ids,
            # The card says "Reveal", so both players may see these identities.
            "revealed": _candidate_card_views(s, ids),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(dec.deciding_player_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=dec.deciding_player_id, kind="reveal_cull_draw"))


def _reveal_cull_draw_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top reveal_cull_draw decision — one per still-revealed
    card, in whichever stage is current.  Both stages are mandatory-if-able (the
    card gives neither player an opt-out)."""
    ctx = top.context
    if ctx.get("stage") == "cull":
        return [CullRevealedCard(cid) for cid in ctx["remaining"]]
    return [DrawRevealedCard(cid) for cid in ctx["remaining"]]


# ── Reveal-top "discard any, reorder the rest on top" (For a Cause I Believe In,

@dataclass
class DiscardRevealed(Action):
    """Set aside one of the revealed top cards — to the discard pile (For a Cause
    I Believe In, SOR_152) or the bottom of the deck (Rogue One, LAW_119),
    according to the decision's ``disposition`` (default ``"discard"``)."""
    card_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_top"):
            raise IllegalActionError("No reveal_top decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.card_id not in ctx["pending"]:
            raise IllegalActionError(f"{self.card_id} is not a revealed card")
        ctx["pending"].remove(self.card_id)
        ps = s.player_by_id(ctx["controller_id"])
        disposition = ctx.get("disposition", "discard")
        for i, c in enumerate(ps.deck):
            if c.instance_id == self.card_id:
                card = ps.deck.pop(i)
                if disposition == "bottom":
                    card.zone = Zone.DECK
                    ps.deck.append(card)            # to the bottom of the deck
                else:
                    card.zone = Zone.DISCARD
                    ps.discard.append(card)
                    note_hand_or_deck_discard(s, card)
                break
        _maybe_finish_reveal_top(s, top)
        return s

    def describe(self) -> str:
        return f"Set aside revealed {self.card_id}"


@dataclass
class KeepRevealed(Action):
    """Keep one of the revealed top cards, placing it next on top of the deck
    (For a Cause I Believe In, SOR_152)."""
    card_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_top"):
            raise IllegalActionError("No reveal_top decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.card_id not in ctx["pending"]:
            raise IllegalActionError(f"{self.card_id} is not a revealed card")
        ctx["pending"].remove(self.card_id)
        ctx["kept_order"].append(self.card_id)
        _maybe_finish_reveal_top(s, top)
        return s

    def describe(self) -> str:
        return f"Keep revealed {self.card_id} on top"


def _maybe_finish_reveal_top(s: GameState, top: "PendingDecision") -> None:
    """When every revealed card is resolved, reorder the kept cards to the top of
    the deck (in the chosen order) and pop the decision."""
    ctx = top.context
    if ctx["pending"]:
        return
    ps = s.player_by_id(ctx["controller_id"])
    kept_set = set(ctx["kept_order"])
    by_id = {c.instance_id: c for c in ps.deck if c.instance_id in kept_set}
    below = [c for c in ps.deck if c.instance_id not in kept_set]
    new_top = [by_id[k] for k in ctx["kept_order"] if k in by_id]
    ps.deck = new_top + below
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_top",
        choice=f"kept {len(new_top)} on top",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index


# ── Reveal-until-stop, damage equal to the combined cost (Don't Get Cocky,

def push_reveal_cost_damage(
    s: GameState, source_ci: CardInstance, target_id: Optional[str],
    *, max_reveals: int = 7, threshold: int = 7,
) -> None:
    """Push a 'reveal_cost_damage' decision (Don't Get Cocky SOR_223).

    ``target_id`` is the pre-chosen unit (via the CustomEffect.target seam).  The
    decision fizzles cleanly (no push) when the target is gone or the deck is
    empty — nothing to reveal, no damage.
    """
    if target_id is None or s.find_instance(target_id) is None:
        return
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return  # empty deck — nothing to reveal
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_cost_damage",
        context={
            "source_id": source_ci.instance_id,
            "source_name": source_ci.card_def.display_name,
            "controller_id": source_ci.owner_id,
            "target_id": target_id,
            "revealed_ids": [],
            "revealed": [],
            "tally": 0,
            "max_reveals": int(max_reveals),
            "threshold": int(threshold),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_cost_damage",
    ))


@dataclass
class RevealNextCard(Action):
    """Reveal the next top card of the deck for a reveal_cost_damage decision,
    adding its cost to the running tally (Don't Get Cocky SOR_223)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cost_damage"):
            raise IllegalActionError("No reveal_cost_damage decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        idx = len(ctx["revealed_ids"])
        if idx >= len(ps.deck) or idx >= int(ctx["max_reveals"]):
            raise IllegalActionError("No more cards may be revealed")
        card = ps.deck[idx]
        ctx["revealed_ids"].append(card.instance_id)
        ctx["revealed"].append({
            "instance_id": card.instance_id,
            "card_id": card.card_def.id,
            "card_name": card.card_def.display_name,
            "cost": getattr(card.card_def, "cost", 0) or 0,
        })
        ctx["tally"] = int(ctx["tally"]) + (getattr(card.card_def, "cost", 0) or 0)
        # Auto-finish when the cap is hit or the deck is now exhausted.
        if (len(ctx["revealed_ids"]) >= int(ctx["max_reveals"])
                or len(ctx["revealed_ids"]) >= len(ps.deck)):
            return _finish_reveal_cost_damage(s)
        return s

    def describe(self) -> str:
        return "Reveal the next card"


@dataclass
class StopRevealing(Action):
    """Stop the reveal_cost_damage loop and resolve (Don't Get Cocky SOR_223)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_cost_damage"):
            raise IllegalActionError("No reveal_cost_damage decision pending")
        return _finish_reveal_cost_damage(copy.deepcopy(state))

    def describe(self) -> str:
        return "Stop revealing"


def _finish_reveal_cost_damage(s: GameState) -> GameState:
    """Pop the reveal_cost_damage decision: deal the tallied damage (if within the
    threshold) to the chosen unit, then bottom every revealed card in a
    seeded-random order."""
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    n = len(ctx["revealed_ids"])
    tally = int(ctx["tally"])
    threshold = int(ctx["threshold"])

    # Pop-then-deal: the decision is already off the stack, so a defeat trigger
    # from this damage lands on a clean stack.
    if 0 < tally <= threshold:
        tid = ctx["target_id"]
        if tid and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _apply_deal_damage
            _apply_deal_damage(s, tid, tally, source_name=ctx.get("source_name"))

    # Bottom the revealed cards (the top ``n`` of the deck) in a seeded-random order.
    revealed = ps.deck[:n]
    rest = ps.deck[n:]
    rng = s.make_rng()
    rng.shuffle(revealed)
    s.rng_state = rng.getstate()
    for c in revealed:
        c.zone = Zone.DECK
    ps.deck = rest + revealed

    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_cost_damage",
        choice=(f"revealed {n} (cost {tally}); dealt {tally}"
                if 0 < tally <= threshold
                else f"revealed {n} (cost {tally}); dealt 0"),
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── New primitive: reveal-a-deck-top, a chosen player plays it free, a different

@dataclass
class ChooseRevealDeck(Action):
    """Choose which player's deck top to reveal (Vermillion LAW_215, choose_deck
    stage)."""
    deck_owner_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_deck":
            raise IllegalActionError("reveal_play_credit decision is past the choose_deck stage")
        if self.deck_owner_id not in ctx.get("deck_player_ids", []):
            raise IllegalActionError(f"{self.deck_owner_id}'s deck cannot be revealed")
        deck = s.player_by_id(self.deck_owner_id).deck
        if not deck:
            raise IllegalActionError(f"{self.deck_owner_id}'s deck is empty")
        top_card = deck[0]
        ctx["deck_owner_id"] = self.deck_owner_id
        ctx["revealed_id"] = top_card.instance_id
        ctx["revealed_card_name"] = top_card.card_def.display_name
        ctx["revealed_card_def_id"] = top_card.card_def.id
        ctx["revealed_cost"] = int(getattr(top_card.card_def, "cost", 0) or 0)
        ctx["stage"] = "choose_player"
        s.event_log.append(DecisionResolved(
            deciding_player_id=ctx["controller_id"],
            kind="reveal_play_credit",
            choice=f"revealed {top_card.card_def.display_name}",
        ))
        return s

    def describe(self) -> str:
        return f"Reveal the top of {self.deck_owner_id}'s deck"


@dataclass
class ChooseRevealPlayer(Action):
    """Choose the player who may play the revealed card (Vermillion LAW_215,
    choose_player stage)."""
    player_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_player":
            raise IllegalActionError("reveal_play_credit decision is not at the choose_player stage")
        if self.player_id not in (ctx["controller_id"], ctx["opponent_id"]):
            raise IllegalActionError(f"{self.player_id} is not a valid player to choose")
        ctx["play_player_id"] = self.player_id
        ctx["stage"] = "may_play"
        top.deciding_player_id = self.player_id
        s.active_player_index = s.player_index(self.player_id)
        s.event_log.append(DecisionResolved(
            deciding_player_id=ctx["controller_id"],
            kind="reveal_play_credit",
            choice=f"chose {self.player_id} to play",
        ))
        return s

    def describe(self) -> str:
        return f"Let {self.player_id} play the revealed card"


@dataclass
class PlayRevealedCard(Action):
    """Play the revealed card for free (Vermillion LAW_215, may_play stage).

    A unit/event resolves immediately (then the other player makes Credits); an
    upgrade advances to the choose_host stage so the playing player picks a host
    before the upgrade is attached."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "may_play":
            raise IllegalActionError("reveal_play_credit decision is not at the may_play stage")
        if not _revealed_is_playable(s, ctx):
            raise IllegalActionError("The revealed card cannot be played")
        ci = _find_revealed(s, ctx)
        if isinstance(ci.card_def, Upgrade):
            ctx["stage"] = "choose_host"
            return s   # the playing player picks a host next (decision stays)
        return _resolve_play_revealed(s, top, host_id=None)

    def describe(self) -> str:
        return "Play the revealed card for free"


@dataclass
class DeclineRevealedCard(Action):
    """Decline to play the revealed card — it stays on top of its deck (Vermillion
    LAW_215, the "may play")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") not in ("may_play", "choose_host"):
            raise IllegalActionError("reveal_play_credit decision is not at a play stage")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="reveal_play_credit",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = int(ctx["final_active_idx"])
        return s

    def describe(self) -> str:
        return "Decline to play the revealed card"


@dataclass
class ChooseRevealHost(Action):
    """Pick the host for a revealed upgrade being played for free (Vermillion
    LAW_215, choose_host stage)."""
    host_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "reveal_play_credit"):
            raise IllegalActionError("No reveal_play_credit decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "choose_host":
            raise IllegalActionError("reveal_play_credit decision is not at the choose_host stage")
        if self.host_id not in _revealed_upgrade_hosts(s, ctx):
            raise IllegalActionError(f"{self.host_id} is not a legal host")
        return _resolve_play_revealed(s, top, host_id=self.host_id)

    def describe(self) -> str:
        return f"Attach the revealed upgrade to {self.host_id}"


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───

@dataclass
class DiscloseSelectCard(Action):
    """Reveal one hand card toward a 'disclose' requirement (Karis Nemik SEC_148,
    Syril Karn SEC_133).  Each revealed card contributes its aspect icons; once the
    required aspect multiset is covered the payoff auto-resolves.  Revealing does
    not move the card — it is public info only."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "disclose"):
            raise IllegalActionError("No disclose decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.instance_id not in _disclose_selectable(s, ctx):
            raise IllegalActionError(
                f"{self.instance_id} cannot be disclosed here")
        result = s.find_instance(self.instance_id)
        _, ci = result
        ctx["revealed"].append(self.instance_id)
        needed = ctx["required"]
        if ctx.get("any_of"):
            # "Disclose Vigilance, Command, Aggression, Cunning, OR Heroism (reveal a
            # card from your hand with this aspect icon)" — Leia Organa SEC_4.  One
            # card bearing ANY listed icon satisfies the whole requirement, so the
            # remaining multiset is cleared outright.
            for a in list(needed):
                needed[a] = 0
        else:
            for a in ci.card_def.aspect_names:
                if int(needed.get(a, 0)) > 0:
                    needed[a] = int(needed[a]) - 1
        if not _disclose_needed(ctx):
            return _resolve_disclose(s, top, success=True)
        return s

    def describe(self) -> str:
        return f"Disclose {self.instance_id}"


@dataclass
class DeclineDisclose(Action):
    """Decline to disclose (the "you may") — no payoff."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "disclose"):
            raise IllegalActionError("No disclose decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_disclose(s, top, success=False)

    def describe(self) -> str:
        return "Don't disclose"


# ── Disclose: reveal hand cards bearing aspect icons (Karis/Syril) ────

def _disclose_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [DiscloseSelectCard(tid)
            for tid in _disclose_selectable(state, top.context)]
    acts.append(DeclineDisclose())  # the "you may" — declining is always legal
    return acts


# ── Reveal top, discard any, reorder the rest on top (For a Cause I

#    Believe In, SOR_152) ─────────────────────────────────────────────────
def _reveal_top_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = []
    for cid in top.context["pending"]:
        acts.append(KeepRevealed(cid))
        acts.append(DiscardRevealed(cid))
    return acts


# ── Reveal-until-stop, damage = combined cost (Don't Get Cocky SOR_223) ─

def _reveal_cost_damage_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    ps = state.player_by_id(ctx["controller_id"])
    n = len(ctx["revealed_ids"])
    acts2: list[Action] = []
    if n < int(ctx["max_reveals"]) and n < len(ps.deck):
        acts2.append(RevealNextCard())
    acts2.append(StopRevealing())
    return acts2


# ── Reveal a deck top, a chosen player plays it free, a different player

#    makes Credits = its cost (Vermillion LAW_215) ──────────────────────────
def _reveal_play_credit_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    stage = ctx.get("stage")
    if stage == "choose_deck":
        return [ChooseRevealDeck(pid)
                for pid in ctx.get("deck_player_ids", [])
                if state.player_by_id(pid).deck]
    if stage == "choose_player":
        return [ChooseRevealPlayer(ctx["controller_id"]),
                ChooseRevealPlayer(ctx["opponent_id"])]
    if stage == "may_play":
        acts: list[Action] = []
        if _revealed_is_playable(state, ctx):
            acts.append(PlayRevealedCard())
        acts.append(DeclineRevealedCard())
        return acts
    if stage == "choose_host":
        acts = [ChooseRevealHost(h) for h in _revealed_upgrade_hosts(state, ctx)]
        acts.append(DeclineRevealedCard())  # no legal host left → may still decline
        return acts
    return [DeclineRevealedCard()]


# ── Reveal-top push helper (For a Cause I Believe In, SOR_152) ────────────────

def push_reveal_top_discard_reorder(
    s: GameState, source_ci: CardInstance, *, count: int = 4, aspect: str = "Heroism",
    deal_aspect_damage: bool = True, disposition: str = "discard",
) -> None:
    """Reveal/look at the top ``count`` cards of the controller's deck, then push a
    'reveal_top' decision letting the controller set aside any of them and put the
    rest back on top in any order.

    ``deal_aspect_damage`` (default True) — before the decision, deal 1 damage to
    the enemy base for each revealed card carrying ``aspect`` (For a Cause I
    Believe In SOR_152).  Set False for a plain "look at the top N and reorder"
    (Rogue One LAW_119), which deals no damage.

    ``disposition`` (default ``"discard"``) — where a *not-kept* revealed card
    goes: ``"discard"`` to the discard pile (SOR_152, a literal "discard"), or
    ``"bottom"`` to the bottom of the deck (Rogue One LAW_119, "put any number on
    the bottom").  ``DiscardRevealed`` reads this from the decision context;
    ``KeepRevealed`` always puts a card back on top regardless.

    The damage is dealt immediately (deterministic, no choice) before the
    decision is pushed.  When the deck has no cards there is nothing to reveal —
    no damage, no decision.  When the damage ends the game, no decision is pushed.
    """
    ps = s.player_by_id(source_ci.owner_id)
    revealed = ps.deck[:count]
    if revealed and deal_aspect_damage:
        n_aspect = sum(
            1 for c in revealed
            if aspect in {a.name for a in (getattr(c.card_def, "aspects", None) or ())}
        )
        if n_aspect > 0:
            opp = s.players[1 - s.player_index(source_ci.owner_id)]
            if opp.base_instance is not None:
                from swu.abilities.resolver import _apply_deal_damage
                _apply_deal_damage(s, opp.base_instance.instance_id, n_aspect,
                                   source_ci.card_def.display_name)
    if not revealed or s.is_terminal():
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_top",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "disposition": disposition,
            "pending": [c.instance_id for c in revealed],
            "kept_order": [],
            # The revealed cards' true identities, in their revealed (top→down)
            # order.  Safe to surface: the decision context is sent only to the
            # deciding player (its own deck), so the opponent never sees it.  The
            # UI renders these so the player can study each card before choosing
            # to discard it or keep it on top (the kept order = the new top order).
            "revealed": [
                {
                    "instance_id": c.instance_id,
                    "card_id": c.card_def.id,
                    "card_name": c.card_def.display_name,
                }
                for c in revealed
            ],
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="reveal_top",
    ))


# ── Disclose (reveal cards from hand bearing aspect icons; if you do, a payoff) ─

def _disclose_needed(ctx: dict) -> dict:
    """The still-uncovered required aspect multiset (name -> remaining count > 0)."""
    return {a: int(c) for a, c in ctx.get("required", {}).items() if int(c) > 0}


def _disclose_selectable(state: GameState, ctx: dict) -> list[str]:
    """Hand cards of the discloser, not yet revealed, that carry ≥1 still-needed
    aspect icon (so every pick makes progress toward covering the requirement)."""
    needed = _disclose_needed(ctx)
    if not needed:
        return []
    ps = state.player_by_id(ctx["discloser_id"])
    revealed = set(ctx.get("revealed", []))
    out: list[str] = []
    for ci in ps.hand:
        if ci.instance_id in revealed:
            continue
        if any(a in needed for a in ci.card_def.aspect_names):
            out.append(ci.instance_id)
    return out


def _disclose_can_satisfy(state: GameState, discloser_id: str,
                          required: dict) -> bool:
    """Whether the discloser's hand collectively bears the required aspect multiset."""
    from collections import Counter
    pool: Counter = Counter()
    for ci in state.player_by_id(discloser_id).hand:
        pool += Counter(ci.card_def.aspect_names)
    return all(pool.get(a, 0) >= int(c) for a, c in required.items())


def push_disclose(
    s: GameState, source_ci: CardInstance, required_aspects: list[str], *,
    payoff: str, payoff_args: Optional[dict] = None,
    discloser_id: Optional[str] = None,
    decline_payoff: Optional[str] = None,
    decline_payoff_args: Optional[dict] = None,
    always_offer: bool = False,
    any_of: bool = False,
) -> None:
    """Push a 'disclose' decision (the disclose primitive).  ``required_aspects`` is
    the multiset of aspect-icon names to cover (e.g. ["Aggression","Heroism"]);
    ``payoff``/``payoff_args`` name the "if you do" effect (see
    ``_apply_disclose_payoff``).  Only pushed when the discloser CAN cover the
    requirement (else the "you may disclose" simply does nothing — no prompt).

    ``decline_payoff``/``decline_payoff_args`` are the mirror: an "If you DON'T, …"
    penalty run when the disclose is declined (Warrior of Clan Ordo SEC_164: "You may
    disclose [Aggression].  If you don't, deal 2 damage to your base").  Such a card
    also passes ``always_offer=True`` so the decision is pushed even when the hand
    cannot cover the requirement — the penalty must still land, and the discloser is
    simply left with only the Decline."""
    from collections import Counter
    discloser = discloser_id or source_ci.owner_id
    required = {a: int(c) for a, c in Counter(required_aspects).items()}
    if any_of:
        # DISJUNCTIVE requirement (Leia Organa SEC_4): one card bearing ANY of the
        # listed icons satisfies it, so "can satisfy" is an ANY test, not the
        # multiset one, and every listed aspect is needed=1 for candidate offering.
        required = dict.fromkeys(dict.fromkeys(required_aspects), 1)
        satisfiable = any(
            any(a in required for a in ci.card_def.aspect_names)
            for ci in s.player_by_id(discloser).hand)
        if not satisfiable and not always_offer:
            return
    elif not _disclose_can_satisfy(s, discloser, required) and not always_offer:
        return
    discloser_idx = s.player_index(discloser)
    dec = PendingDecision(
        deciding_player_id=discloser,
        kind="disclose",
        context={
            "source_id": source_ci.instance_id,
            "discloser_id": discloser,
            "required": required,
            "any_of": bool(any_of),
            "revealed": [],
            "payoff": payoff,
            "payoff_args": dict(payoff_args or {}),
            "decline_payoff": decline_payoff,
            "decline_payoff_args": dict(decline_payoff_args or {}),
        },
        # If disclose is the top decision when it resolves the discloser continues
        # (e.g. mid-attack); if a payoff pushes a further decision this is unused.
        after_resolve_player_index=discloser_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = discloser_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=discloser,
        kind="disclose",
    ))


def _resolve_disclose(s: GameState, top, *, success: bool) -> GameState:
    """Pop the 'disclose' decision; run the payoff if the discloser disclosed."""
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="disclose",
        choice=("disclosed" if success else "declined"),
    ))
    if success:
        # A successful Disclose reveals 1+ cards from the discloser's hand — record
        # it for the WhenYouRevealOrDiscard observer (Padmé Amidala SEC_16) before
        # the payoff runs (the ledger is drained at the settle-point either way).  A
        # reveal is NOT a discard, so kind="reveal" keeps it out of the discard-only
        # ledger (Migs Mayfeld SHD_163 must not fire on a Disclose).
        if ctx.get("revealed"):
            record_hand_discard(s, ctx["discloser_id"], kind="reveal")
        _apply_disclose_payoff(s, ctx)
    elif ctx.get("decline_payoff"):
        # "If you DON'T, …" (Warrior of Clan Ordo SEC_164) — the same payoff
        # dispatcher, keyed off the decline arm.
        _apply_disclose_payoff(s, {**ctx,
                                   "payoff": ctx["decline_payoff"],
                                   "payoff_args": ctx.get("decline_payoff_args", {})})
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


def _apply_disclose_payoff(s: GameState, ctx: dict) -> None:
    """Dispatch a disclosed card's "if you do" payoff (string key + serialisable
    args).  Each payoff reuses an existing seam; new disclose cards add an arm."""
    payoff = ctx.get("payoff")
    args = ctx.get("payoff_args", {})
    discloser_id = ctx["discloser_id"]
    if payoff == "create_ready_token":
        # Karis Nemik SEC_148: create a Spy token and ready it.
        ps = s.player_by_id(discloser_id)
        created = _create_token_units(
            s, ps, args["token_name"], int(args.get("count", 1)))
        for ci in created:
            ci.exhausted = False
        return
    if payoff == "experience_off_aspect_unit":
        # Leia Organa SEC_4: "give an Experience token to a unit that doesn't share
        # an aspect with the disclosed card."  The disclosed card's aspects come off
        # ctx["revealed"]; every in-play unit sharing none of them is whitelisted
        # into a select_token.  DOCUMENTED DEVIATION: select_token is an "up to",
        # so the printed mandatory gift can be declined.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None or not ctx.get("revealed"):
            return
        disclosed = s.find_instance(ctx["revealed"][-1])
        if disclosed is None:
            return
        shown = set(disclosed[1].card_def.aspect_names)
        eligible = [
            u.instance_id
            for p in s.players
            for arena in (p.ground_arena, p.space_arena)
            for u in arena
            if not (shown & set(u.card_def.aspect_names))
        ]
        if not eligible:
            return
        push_select_token(s, source_result[1], token_type="Experience",
                          max_targets=1, restrict_ids=eligible,
                          decider_id=discloser_id)
        return
    if payoff == "name_and_discard":
        # Charged with Espionage SEC_230: "look at an opponent's hand and discard a
        # unit from it" — the Chimaera SOR_185 decision, which already carries the
        # whole hand to the discloser and offers only names present (that IS the
        # look), narrowed by ``card_type``.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is not None:
            push_name_and_discard(s, source_result[1],
                                  card_type=args.get("card_type"))
        return
    if payoff == "opponents_discard_random":
        # Duchess's Investigators SEC_223: "each opponent discards a RANDOM card
        # from their hand" — drawn from the seeded RNG, so replays reproduce.
        rng = s.make_rng()
        for opp in s.players:
            if opp.player_id == discloser_id or not opp.hand:
                continue
            card = opp.hand.pop(rng.randrange(len(opp.hand)))
            card.zone = Zone.DISCARD
            opp.discard.append(card)
            note_hand_or_deck_discard(s, card)
            record_hand_discard(s, opp.player_id, kind="discard")
        s.rng_state = rng.getstate()
        return
    if payoff == "opponent_discard":
        # Luthen's Haulcraft SEC_153: "that opponent discards N cards from their
        # hand" — the first-card discard convention (K-2SO SOR_145).
        opp = next((p for p in s.players if p.player_id != discloser_id), None)
        if opp is None:
            return
        moved = 0
        for _ in range(int(args.get("count", 1))):
            if not opp.hand:
                break
            card = opp.hand.pop(0)
            card.zone = Zone.DISCARD
            opp.discard.append(card)
            note_hand_or_deck_discard(s, card)
            moved += 1
        if moved:
            # ONE record per discard instruction, however many cards moved.
            record_hand_discard(s, opp.player_id, kind="discard")
        return
    if payoff == "create_token":
        # Faith in Your Friends SEC_211: create N token units (the plain sibling of
        # ``create_ready_token`` — these enter exhausted, the CR default).
        ps = s.player_by_id(discloser_id)
        _create_token_units(s, ps, args["token_name"], int(args.get("count", 1)))
        return
    if payoff == "damage_unless_discard":
        # Syril Karn SEC_133: deal N to the chosen unit unless its controller
        # discards a card (reuses the may_discard else-damage seam).
        source_result = s.find_instance(ctx["source_id"])
        source_ci = source_result[1] if source_result is not None else None
        push_may_discard_else_damage(
            s, source_ci, args.get("target_id"), int(args.get("amount", 0)))
        return
    if payoff == "self_base_damage":
        # Warrior of Clan Ordo SEC_164's DECLINE arm: "If you don't, deal N damage to
        # your base."  Also usable as a normal payoff; the discloser's own base.
        ps = s.player_by_id(discloser_id)
        if ps.base_instance is not None:
            from swu.abilities.resolver import _apply_deal_damage
            source_result = s.find_instance(ctx["source_id"])
            name = (source_result[1].card_def.display_name
                    if source_result is not None else None)
            _apply_deal_damage(s, ps.base_instance.instance_id,
                               int(args.get("amount", 1)), name)
        return
    if payoff == "damage_unit":
        # Charged with Treason SEC_182: "If you do, deal N damage to a unit" — the
        # target was chosen up front (the Syril Karn SEC_133 convention).
        target_id = args.get("target_id")
        if target_id:
            from swu.abilities.resolver import _apply_deal_damage
            source_result = s.find_instance(ctx["source_id"])
            name = (source_result[1].card_def.display_name
                    if source_result is not None else None)
            _apply_deal_damage(s, target_id, int(args.get("amount", 1)), name)
        return
    if payoff == "draw":
        # Mina Bonteri SEC_94: draw N cards (reuses the _draw_cards seam).
        ps = s.player_by_id(discloser_id)
        _draw_cards(s, ps, int(args.get("count", 1)))
        return
    if payoff == "heal_base":
        # Captain Typho SEC_98: heal N damage from the discloser's own base.
        ps = s.player_by_id(discloser_id)
        if ps.base_instance is not None:
            ps.base_instance.damage = max(
                0, ps.base_instance.damage - int(args.get("amount", 0)))
        return
    if payoff == "granted_attack":
        # Ahsoka Tano SEC_96: attack with another unit (reuses push_granted_attack).
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None:
            return
        push_granted_attack(
            s, source_result[1],
            exclude_source=bool(args.get("exclude_source", True)),
            no_base=bool(args.get("no_base", False)),
            allow_exhausted=bool(args.get("allow_exhausted", False)),
            optional=bool(args.get("optional", False)),
        )
        return
    if payoff == "buff_unit":
        # With Thunderous Applause SEC_129: give the pre-chosen "another" unit a
        # +power/+hp modifier for this phase (reuses the stat-modifier seam).  The
        # target was chosen up front (a cosmetic reorder, the Syril Karn SEC_133
        # convention); no-op if it has since left play.
        tid = args.get("target_id")
        if tid is not None and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _make_modifier
            from swu.abilities.registry import Duration
            # ``duration`` widens the arm to "for this ATTACK" (Ebon Hawk SEC_219,
            # which buffs itself and debuffs the defender mid-combat); the default
            # stays SEC_129's this-phase reading.
            dur = (Duration.THIS_ATTACK if args.get("duration") == "this_attack"
                   else Duration.THIS_PHASE)
            s.modifiers.append(_make_modifier(
                s, ctx.get("source_id", ""), tid,
                power=int(args.get("power", 0)), hp=int(args.get("hp", 0)),
                duration=dur))
        return
    if payoff == "exhaust_unit":
        # Bog Down in Procedure SEC_234: exhaust the pre-chosen "another" unit
        # (honours Protection, mirroring the declarative ExhaustCard arm).
        # ``lock_round`` also flags the unit ``cannot_ready_this_round`` — Cantwell
        # Arrestor Cruiser SEC_37 ("That unit can't ready while this unit is in
        # play"): a documented simplification to "this round" using the existing
        # No-Good-to-Me-Dead SOR_186 keep-tapped flag (the persistent while-in-play
        # lock would need a new ready-lock modifier kind, out of scope here).
        tid = args.get("target_id")
        res = s.find_instance(tid) if tid is not None else None
        if res is not None:
            src = s.find_instance(ctx.get("source_id", ""))
            src_ci = src[1] if src is not None else None
            from swu.abilities.resolver import _target_protected
            if src_ci is None or not _target_protected(s, tid, src_ci, "exhaust"):
                res[1].exhausted = True
                if args.get("lock_round"):
                    res[1].cannot_ready_this_round = True
        return
    if payoff == "select_token":
        # Vice Admiral Rampart SEC_85: "give an Experience token to each of up to
        # N other units" — the Medal Ceremony SOR_245 select_token decision, pushed
        # from the disclose payoff (the source's controller decides).
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None:
            return
        push_select_token(
            s, source_result[1],
            token_type=str(args.get("token_type", "Experience")),
            max_targets=int(args.get("max_targets", 1)),
            controller=str(args.get("controller", "any")),
            kind=str(args.get("kind", "unit")),
            traits=list(args.get("traits", []) or []),
            predicates=list(args.get("predicates", []) or []),
        )
        return
    if payoff == "grant_keyword":
        # Naboo Security Force SEC_120 / B2EMO SEC_248: give the pre-chosen unit a
        # keyword for this phase (reuses the keyword-grant modifier seam).  The
        # target was chosen up front (the SEC_129 pre-chosen convention); no-op if
        # it has since left play.
        tid = args.get("target_id")
        if tid is not None and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _make_kw_modifier
            from swu.abilities.registry import Duration
            s.modifiers.append(_make_kw_modifier(
                s, ctx.get("source_id", ""), tid,
                keyword=str(args.get("keyword", "Sentinel")),
                value=int(args.get("value", 0)),
                duration=Duration.THIS_PHASE, kind="keyword_grant"))
        return
    if payoff == "ready_resources":
        # Soulless One SEC_190: "ready N resources" — the resource-ramp mirror of
        # the ``heal_base`` arm (readying fewer than N when only fewer are spent).
        ps = s.player_by_id(discloser_id)
        remaining = int(args.get("count", 1))
        for r in ps.resources:
            if remaining <= 0:
                break
            if r.exhausted:
                r.exhausted = False
                remaining -= 1
        return
    if payoff == "pending_keyword_grant":
        # Diplomatic Envoy SEC_109: "the next unit you play this phase gains K for
        # this phase" — one entry on the ``pending_keyword_grants`` ledger (Deceptive
        # Shade LOF_180), consumed by that player's next unit play.
        s.game_memory.pending_keyword_grants.append({
            "player_id": discloser_id,
            "trait": str(args.get("trait", "") or ""),
            "keyword": str(args.get("keyword", "Ambush")),
        })
        return
    if payoff == "resource_top_of_deck":
        # Chancellor Valorum SEC_107: "put the top card of your deck into play as a
        # resource" (the ``_resource_top_of_deck`` ramp seam, which enters ready).
        _resource_top_of_deck(s, s.player_by_id(discloser_id))
        return
    if payoff == "heal_unit":
        # Relief Request SEC_74: heal N damage from the pre-chosen "another" unit
        # (the SEC_129 pre-chosen convention); no-op if it has since left play.
        tid = args.get("target_id")
        res = s.find_instance(tid) if tid is not None else None
        if res is not None:
            healed = min(int(args.get("amount", 0)), int(res[1].damage))
            if healed > 0:
                res[1].damage -= healed
                note_unit_healed(s, res[1], healed)
        return
    if payoff == "distribute_heal":
        # Nala Se SEC_65: "heal up to 4 damage from among other units" — the
        # Redemption SOR_52 heal-pool decision, widened to either player's units
        # and excluding the source ("other"), with no self-damage kicker.
        source_result = s.find_instance(ctx["source_id"])
        if source_result is None:
            return
        push_distribute_heal(
            s, source_result[1], int(args.get("amount", 0)),
            include_bases=False, then_damage_self=False,
            target_controller="any",
            exclude_ids=[ctx["source_id"]],
        )
        return
    if payoff == "capture":
        # Charged with Corruption SEC_127: the pre-chosen friendly captor captures
        # the pre-chosen enemy non-leader unit (reuses _apply_capture).  Both ids
        # were chosen up front (the SEC_129 pre-chosen convention); no-op if either
        # has since left play.
        captor_id = args.get("captor_id")
        victim_id = args.get("victim_id")
        if (captor_id and victim_id
                and s.find_instance(captor_id) is not None
                and s.find_instance(victim_id) is not None):
            _apply_capture(s, captor_id, victim_id)
        return
    if payoff == "defeat":
        # Charged with Murder SEC_76: defeat the pre-chosen unit (reuses
        # _apply_defeat_unit).  The target (a damaged non-leader unit) was chosen up
        # front (the SEC_129 pre-chosen convention); no-op if it has since left play.
        tid = args.get("target_id")
        if tid is not None and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _apply_defeat_unit
            _apply_defeat_unit(s, tid)
        return


# ── Reveal-a-deck-top / a chosen player plays it free / a different player makes

def push_reveal_play_credit(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'reveal_play_credit' decision (Vermillion LAW_215).

    The source's controller first chooses which deck's top card to reveal, then a
    player who may play it for free; if it is played, the OTHER player makes Credit
    tokens equal to the played card's printed cost.  Only pushed when at least one
    player's deck is non-empty (else the whole ability fizzles).  After the whole
    sequence the turn passes to the source controller's opponent (the attack is
    over), stored in ``final_active_idx``.
    """
    controller_id = source_ci.owner_id
    opponent_id = next(p.player_id for p in s.players if p.player_id != controller_id)
    deck_player_ids = [p.player_id for p in s.players if p.deck]
    if not deck_player_ids:
        return  # nothing to reveal
    controller_idx = s.player_index(controller_id)
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "opponent_id": opponent_id,
        "stage": "choose_deck",
        "deck_player_ids": deck_player_ids,
        "final_active_idx": s.player_index(opponent_id),
    }
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="reveal_play_credit",
        context=ctx,
        after_resolve_player_index=s.player_index(opponent_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = controller_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="reveal_play_credit",
    ))


def _find_revealed(s: GameState, ctx: dict) -> Optional[CardInstance]:
    """The revealed card (still on top of / in its deck), or None if it has gone."""
    rid = ctx.get("revealed_id")
    if rid is None:
        return None
    for c in s.player_by_id(ctx["deck_owner_id"]).deck:
        if c.instance_id == rid:
            return c
    return None


def _revealed_upgrade_hosts(s: GameState, ctx: dict) -> list[str]:
    """Legal host ids for the revealed upgrade (empty if not an upgrade / no host)."""
    ci = _find_revealed(s, ctx)
    if ci is None or not isinstance(ci.card_def, Upgrade):
        return []
    return [u.instance_id for u in _eligible_upgrade_targets(s, ci)]


def _revealed_is_playable(s: GameState, ctx: dict) -> bool:
    """Whether the chosen player can play the revealed card: a unit or event is
    always playable; an upgrade needs at least one legal host on the board."""
    ci = _find_revealed(s, ctx)
    if ci is None:
        return False
    if isinstance(ci.card_def, Upgrade):
        return bool(_eligible_upgrade_targets(s, ci))
    return isinstance(ci.card_def, (Unit, Leader, Event))


def _play_revealed_card(s: GameState, ctx: dict, host_id: Optional[str]) -> None:
    """Play the revealed card for free under the chosen player's control.

    The card is removed from the revealed deck and played via the normal play
    paths (unit → arena, upgrade → attach, event → resolve) so its own keyword /
    When Played abilities fire.  ``owner_id`` is left unchanged (control is
    implicit — the Stolen Landspeeder SHD_161 convention), so when the chosen
    player does not own the card, its own abilities resolve from the OWNER's
    perspective (the documented control-change limitation); the common case (a
    player plays their own deck's card) is exact."""
    deck_owner = s.player_by_id(ctx["deck_owner_id"])
    play_ps = s.player_by_id(ctx["play_player_id"])
    rid = ctx.get("revealed_id")
    ci = None
    for i, c in enumerate(deck_owner.deck):
        if c.instance_id == rid:
            ci = deck_owner.deck.pop(i)
            break
    if ci is None:
        return  # gone (shouldn't happen)
    ci.face_down = False
    after_idx = int(ctx["final_active_idx"])

    card_played_evt = CardPlayed(
        player_id=play_ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
        cost_paid=0,
    )
    s.event_log.append(card_played_evt)
    card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
    if "Villainy" in card_aspects:
        s.game_memory.villainy_players_this_phase.add(play_ps.player_id)

    if isinstance(ci.card_def, (Unit, Leader)):
        _put_unit_in_play(s, play_ps, ci, cost_paid=0)
    elif isinstance(ci.card_def, Upgrade):
        _attach_upgrade(s, play_ps, ci, host_id)
    elif isinstance(ci.card_def, Event):
        ci.zone = Zone.DISCARD
        play_ps.discard.append(ci)
        _resolve_event_ability(s, play_ps, ci, after_idx)
    else:
        ci.zone = Zone.DISCARD
        play_ps.discard.append(ci)

    get_bus().fire(s, card_played_evt)
    from swu.abilities.resolver import fire_triggered_abilities
    fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)


def _create_credits_for_other(s: GameState, ctx: dict) -> None:
    """The player who did NOT play the revealed card makes Credit tokens equal to
    its printed cost ("a different player creates Credit tokens equal to that
    card's cost").  In a 2-player game the "different player" is unambiguous."""
    cost = int(ctx.get("revealed_cost", 0) or 0)
    if cost <= 0:
        return
    other_id = next(p.player_id for p in s.players
                    if p.player_id != ctx["play_player_id"])
    from swu.engine.tokens import create_credit_token
    other_ps = s.player_by_id(other_id)
    for _ in range(cost):
        create_credit_token(s, other_ps)


def _resolve_play_revealed(s: GameState, top, host_id: Optional[str]) -> GameState:
    """Pop the decision, play the revealed card for free, then the other player
    makes Credits = its cost.  The decision is popped FIRST so the played card's
    own triggers land on a clean stack (the push_distribute_damage "pop, then act"
    gotcha)."""
    ctx = top.context
    final_idx = int(ctx["final_active_idx"])
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="reveal_play_credit",
        choice=f"played {ctx.get('revealed_card_name')}",
    ))
    _play_revealed_card(s, ctx, host_id=host_id)
    _create_credits_for_other(s, ctx)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = final_idx
    return s

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "reveal_cull_draw":              _reveal_cull_draw_actions,
    "disclose":                      _disclose_actions,
    "reveal_top":                    _reveal_top_actions,
    "reveal_cost_damage":            _reveal_cost_damage_actions,
    "reveal_play_credit":            _reveal_play_credit_actions,
})
