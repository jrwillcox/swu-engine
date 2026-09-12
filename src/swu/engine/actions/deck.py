"""The deck treated as an addressable list rather than a stack you draw from.

Drawing needs no decision: the top card is the top card. This family is every effect that
looks *into* the deck or rearranges it, which always needs one — searching for a card
matching a predicate, looking at the top N and choosing what to keep, putting cards on top
or bottom in a player-chosen order, moving a card from hand to the deck or to the resource
row, and being asked for a number before any of that happens.

Two constraints shape all of it.

**What the searching player may see is not the same as what matches.** A search that
filters only by the predicate would reveal the presence of cards the player is not entitled
to know about, so the candidate list and the visible list are derived separately.
``invariants.py`` checks for exactly this class of leak by scanning the rendered
``view_for(p)``, which catches it when a card *name* escapes -- so the discipline here is
the first line of defence rather than the only one.

**Any reordering described as random must use the game's seeded RNG.** The pattern is
``s.make_rng()``, never the global ``random`` module: the engine's determinism guarantee is
that a seed and an action sequence reproduce a game exactly, and a single global
``random.shuffle`` anywhere in this file would break replay, saved games and the trace
oracle at once, while still passing every test that does not compare two runs.
``tests/regressions/test_determinism_seeded_replay.py`` is what pins it.

``_search_window_doubled`` is worth reading before adding a search effect, because how many
cards a search examines is not a property of the searching effect at all. It is a
``SearchWindowDoubler`` marker held by the searching *player*, and the check walks their
arena units **and every attached upgrade**, so the marker counts whether it is printed on a
unit or conferred onto a host by an upgrade -- and confers nothing from a host whose
abilities are suppressed.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Optional

from swu.cards.models import Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardPlayed, CardResourced,
    DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState, Zone, ability_suppressed
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _consume_play_discount, _consume_standing_discount, _effective_cost, _pay_play_cost, _play_cost, _usable_credits,
)
from swu.engine.actions.damage import (
    _bases_cannot_heal, note_base_healed,
)
from swu.engine.actions.zones import (
    _apply_put_on_deck, _attach_upgrade, _draw_cards, _eligible_upgrade_targets, _put_unit_in_play, _resolve_event_ability, _upgrade_target_spec,
)
from swu.engine.actions.shared import (
    _candidate_card_views, spend_force_token,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard, push_granted_attack, push_select_token,
)
from swu.engine.actions.hand import (
    push_play_from_hand,
)


# ── Put a chosen in-play unit on the top or bottom of its owner's deck

def _resolve_put_on_deck(state: GameState, instance_id: str, *, to_top: bool) -> GameState:
    if (not state.pending_decisions
            or state.pending_decisions[-1].kind != "put_on_deck"):
        raise IllegalActionError("No put_on_deck decision pending")
    ctx = state.pending_decisions[-1].context
    if instance_id != ctx.get("card_id"):
        raise IllegalActionError("Not the chosen unit")
    s = copy.deepcopy(state)
    top = s.pending_decisions.pop()
    # Pop BEFORE relocating so any state-based fallout (a buff source leaving play)
    # is swept by the top-level apply() on a clean stack (the "pop, then act" gotcha).
    s = _apply_put_on_deck(s, instance_id, to_top=to_top)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="put_on_deck",
        choice=("top" if to_top else "bottom"),
    ))
    # The buried resolve_effects decision (if the CustomEffect that pushed us was
    # mid-resolution) stays on the stack — only restore control when it is clear.
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


@dataclass
class PutOnDeckTop(Action):
    """Resolve a 'put_on_deck' decision by putting the unit on TOP of its owner's
    deck (Qui-Gon Jinn LOF_200)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        return _resolve_put_on_deck(state, self.instance_id, to_top=True)

    def describe(self) -> str:
        return f"Put {self.instance_id} on top of its owner's deck"


@dataclass
class PutOnDeckBottom(Action):
    """Resolve a 'put_on_deck' decision by putting the unit on the BOTTOM of its
    owner's deck (Qui-Gon Jinn LOF_200)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        return _resolve_put_on_deck(state, self.instance_id, to_top=False)

    def describe(self) -> str:
        return f"Put {self.instance_id} on the bottom of its owner's deck"


def push_put_on_deck(s: GameState, source_ci: CardInstance, target_id: str) -> None:
    """Push a 'put_on_deck' decision (Qui-Gon Jinn LOF_200): the OWNER of the chosen
    in-play unit puts it on the top or bottom of THEIR deck.  The decider is that
    owner (who may be the source's opponent — the owner_may_replay LOF_185
    deciding-player shift), since only they should order their own deck.  A clean
    no-op if the target is not an in-play arena unit."""
    result = s.find_instance(target_id)
    if result is None:
        return
    ps, ci = result
    if not any(ci in arena for arena in (ps.ground_arena, ps.space_arena)):
        return
    owner_idx = s.player_index(ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=ci.owner_id,
        kind="put_on_deck",
        context={
            "source_id": source_ci.instance_id,
            "card_id": target_id,
            "owner_id": ci.owner_id,
        },
        after_resolve_player_index=s.player_index(source_ci.owner_id),
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=ci.owner_id,
        kind="put_on_deck",
    ))


# ── Deck search-and-select (deck_search decision) ─────────────────────────────

@dataclass
class SelectSearchCard(Action):
    """Select one revealed candidate from the searched top cards to draw."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "deck_search"):
            raise IllegalActionError("No deck_search decision pending")
        s = copy.deepcopy(state)
        ctx = s.pending_decisions[-1].context
        if self.instance_id not in ctx["candidate_ids"]:
            raise IllegalActionError(f"{self.instance_id} is not a search candidate")
        if self.instance_id in ctx["selected_ids"]:
            raise IllegalActionError(f"{self.instance_id} already selected")
        budget = ctx.get("budget")
        if budget is not None:
            # Combined-cost budget (Darth Vader SOR_87): the picked units' printed
            # costs may not exceed the budget.  Guard defensively — legal_actions
            # already hides an over-budget candidate.
            deck_by_id = {ci.instance_id: ci
                          for ci in s.player_by_id(ctx["controller_id"]).deck}
            spent = sum((deck_by_id[cid].card_def.cost or 0)
                        for cid in ctx["selected_ids"] if cid in deck_by_id)
            this_cost = (deck_by_id[self.instance_id].card_def.cost or 0
                         ) if self.instance_id in deck_by_id else 0
            if spent + this_cost > int(budget):
                raise IllegalActionError(
                    f"{self.instance_id} exceeds the combined-cost budget")
        ctx["selected_ids"].append(self.instance_id)
        if len(ctx["selected_ids"]) >= int(ctx["max_select"]):
            return _finish_deck_search(s)
        return s

    def describe(self) -> str:
        return f"Take {self.instance_id} from the searched cards"


@dataclass
class FinishSearch(Action):
    """Stop selecting searched cards: draw the chosen ones and bottom the rest.

    Offered whenever the effect is "up to N" (a zero-pick finish is always legal)
    or no eligible candidate remains (a mandatory search with nothing left to take).
    """
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "deck_search"):
            raise IllegalActionError("No deck_search decision pending")
        return _finish_deck_search(copy.deepcopy(state))

    def describe(self) -> str:
        return "Finish searching"


def _finish_deck_search(s: GameState) -> GameState:
    """Pop the deck_search decision: dispose of the selected top cards (draw them,
    the default, or PLAY them — Kelleran Beq LOF_100) and put the remaining
    searched cards on the bottom of the deck in a seeded-random order.

    The deck is untouched while the decision is open, so the searched window is
    simply ``deck[:window]`` again here.  Selected cards (preserving deck order)
    are revealed and either drawn to hand or played from the deck; the rest are
    shuffled with the game's seeded RNG (NOT the global ``random`` module) and
    appended below the un-searched remainder, and the advanced ``rng_state`` is
    persisted so two same-seed runs reorder identically.
    """
    from swu.engine.state import Zone
    top = s.pending_decisions.pop()
    ctx = top.context
    ps = s.player_by_id(ctx["controller_id"])
    window = int(ctx.get("window", 5))
    selected_set = set(ctx["selected_ids"])

    searched = ps.deck[:window]
    rest = ps.deck[window:]
    selected = [ci for ci in searched if ci.instance_id in selected_set]
    skipped = [ci for ci in searched if ci.instance_id not in selected_set]

    skipped_in_order = list(skipped)
    rng = s.make_rng()
    rng.shuffle(skipped)
    s.rng_state = rng.getstate()

    # The selected cards leave the deck (they are neither in ``rest`` nor
    # ``skipped``).  The un-taken searched cards go to the bottom in random order
    # by default, or to the discard pile when ``rest_disposition == "discard"``
    # (I've Found Them IBH_9 — "discard the other revealed cards").
    if ctx.get("rest_disposition") == "discard":
        for ci in skipped:
            ci.zone = Zone.DISCARD
            # A deck discard, so it feeds the shared ledger (and with it the
            # WhenThisIsDiscarded observer drain — That's a Rock LAW_206), exactly
            # as the SELECTED-card "discard" disposition below does.  The cards
            # NOT skipped never reach a discard pile at all, which is why
            # Shipbreaking Yard LAW_26's rescued card correctly does not fire it.
            note_hand_or_deck_discard(s, ci, from_deck=True)
        ps.discard.extend(skipped)
        ps.deck = rest
    elif ctx.get("rest_disposition") == "top":
        # "(Put the other back on top.)" — Sabé SEC_17.  The un-taken searched
        # cards keep their original order (they never left the top), so the
        # shuffled copy is discarded and the in-order one used.
        ps.deck = skipped_in_order + rest
    else:
        ps.deck = rest + skipped

    if ctx.get("disposition") == "play":
        # Kelleran Beq: "Search the top N … for a unit, reveal it, and play it.
        # It costs 3 resources less."  The decision is already popped, so the
        # played unit's own When Played triggers land on a clean stack (the
        # push_distribute_damage "pop, then act" gotcha).
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        free = bool(ctx.get("free"))
        enters_ready = bool(ctx.get("enters_ready"))
        return_at_regroup = bool(ctx.get("return_at_regroup"))
        bottom_at_regroup = bool(ctx.get("bottom_at_regroup"))
        played_names: list[str] = []
        for ci in selected:
            cost = 0 if free else max(0, _effective_cost(ci.card_def, ps, s) - cost_reduction)
            _pay_play_cost(s, ps, cost)
            evt = CardPlayed(
                player_id=ps.player_id,
                instance_id=ci.instance_id,
                card_name=ci.card_def.display_name,
                cost_paid=cost,
            )
            s.event_log.append(evt)
            card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
            if "Villainy" in card_aspects:
                s.game_memory.villainy_players_this_phase.add(ps.player_id)
            _put_unit_in_play(s, ps, ci, play_source="deck", cost_paid=cost,
                              enters_ready=enters_ready)
            if return_at_regroup:
                ci.return_to_owner_hand_at_regroup = True
            if bottom_at_regroup:
                ci.bottom_at_regroup = True
            get_bus().fire(s, evt)
            played_names.append(ci.card_def.display_name)
        choice = f"played {', '.join(played_names) or 'nothing'}"
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=choice,
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "play_upgrade":
        # Reforge ASH_90: the chosen upgrade is PLAYED onto a pre-chosen host at
        # ``cost_reduction`` off.  The decision is already popped, so the upgrade's
        # own When Played trigger lands on a clean stack.
        cost_reduction = int(ctx.get("cost_reduction", 0) or 0)
        host_id = ctx.get("upgrade_host_id")
        played_names: list[str] = []
        for ci in selected:
            if host_id is None or s.find_instance(host_id) is None:
                # The host left play while the decision was open — the revealed
                # upgrade has nowhere to go, so it is discarded rather than lost.
                ci.zone = Zone.DISCARD
                ps.discard.append(ci)
                continue
            cost = max(0, _effective_cost(ci.card_def, ps, s) - cost_reduction)
            _pay_play_cost(s, ps, cost)
            evt = CardPlayed(
                player_id=ps.player_id,
                instance_id=ci.instance_id,
                card_name=ci.card_def.display_name,
                cost_paid=cost,
            )
            s.event_log.append(evt)
            card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
            if "Villainy" in card_aspects:
                s.game_memory.villainy_players_this_phase.add(ps.player_id)
            _attach_upgrade(s, ps, ci, host_id)
            get_bus().fire(s, evt)
            played_names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"played {', '.join(played_names) or 'nothing'}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "discard_free_replay":
        # Cobb Vanth SHD_115: the selected unit is DISCARDED (not drawn) and flagged
        # for a free replay from the discard pile this phase (the Second Chance
        # SHD_53 free-discard-replay seam).  The un-taken searched cards were already
        # sent to the bottom (rest_disposition default) above.
        names: list[str] = []
        for ci in selected:
            ci.zone = Zone.DISCARD
            ci.exhausted = False
            ci.damage = 0
            ps.discard.append(ci)
            s.game_memory.free_discard_play_this_phase.add(ci.instance_id)
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"discarded for free replay ({', '.join(names) or 'nothing'})",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "discard_play_discount":
        # Aid from the Innocent TWI_201: the selected cards are DISCARDED and, for
        # the rest of this phase, may be played from the discard pile at
        # ``play_discount`` resources less (the discounted sibling of the free
        # permission above; any card type, since the cards searched for are
        # non-units).
        red = int(ctx.get("play_discount") or 0)
        names = []
        for ci in selected:
            ci.zone = Zone.DISCARD
            ci.exhausted = False
            ci.damage = 0
            ps.discard.append(ci)
            note_hand_or_deck_discard(s, ci, from_deck=True)
            s.game_memory.discard_play_discount_this_phase[ci.instance_id] = red
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=(f"discarded for a {red}-cheaper replay "
                    f"({', '.join(names) or 'nothing'})"),
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "discard":
        # The plain discard of the SELECTED cards (no replay permission attached) —
        # "look at the top 2 cards of the defending player's deck.  Discard 1 of
        # those cards" (Sabé SEC_17).  ``ps`` is the DECK OWNER, so the card lands
        # in their own discard pile.
        names = []
        for ci in selected:
            ci.zone = Zone.DISCARD
            ci.exhausted = False
            ci.damage = 0
            ps.discard.append(ci)
            note_hand_or_deck_discard(s, ci, from_deck=True)
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"discarded {', '.join(names) or 'nothing'}",
        ))
        # "Then, you may attack with this unit.  For this attack, this unit gains the
        # discarded unit's abilities" (Improvised Identity ASH_230) — the attack is
        # pushed AFTER the pop (the pop-then-act rule), with the card just discarded
        # as the BORROW lender; ``borrowed_ability_sources`` finds it through
        # ``find_instance``, which reaches the discard.
        attacker_id = ctx.get("then_borrowed_attack_by")
        if attacker_id and selected:
            att = s.find_instance(attacker_id)
            if att is not None:
                push_granted_attack(
                    s, att[1], optional=True, attacker_id=attacker_id,
                    allow_exhausted=False, borrow_abilities=True,
                    borrow_lender_id=selected[0].instance_id)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "resource":
        # Jendirian Valley TS26_18: "Search the top 8 cards of your deck for a card
        # and RESOURCE it."  The selected card goes straight into the searcher's
        # resource row rather than to hand — face down and EXHAUSTED, the CR default
        # for a resource put into play by an effect that does not say "and ready it"
        # (the same placement ``resource_from_discard`` uses, and the card's own
        # rules note: "Resources enter play exhausted").
        names = []
        for ci in selected:
            ci.zone = Zone.RESOURCES
            ci.face_down = True
            ci.exhausted = True
            ci.damage = 0
            ps.resources.append(ci)
            s.event_log.append(CardResourced(
                player_id=ps.player_id,
                instance_id=ci.instance_id,
                card_name=ci.card_def.display_name,
            ))
            names.append(ci.card_def.display_name)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=f"resourced {', '.join(names) or 'nothing'}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    if ctx.get("disposition") == "top":
        # Following the Path LOF_103: "…reveal them, and put them on top of your
        # deck in any order."  The selected cards go back on TOP rather than being
        # drawn; SELECTION order is the chosen top-down order (the reveal_top
        # SOR_152 click-order convention), so re-sort by ``selected_ids`` — the
        # ``selected`` list above is in deck order.
        order = {iid: i for i, iid in enumerate(ctx["selected_ids"])}
        ordered = sorted(selected, key=lambda c: order.get(c.instance_id, 0))
        for ci in ordered:
            ci.zone = Zone.DECK
        ps.deck = ordered + ps.deck
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="deck_search",
            choice=(f"put {len(ordered)} on top ("
                    f"{', '.join(c.card_def.display_name for c in ordered) or 'nothing'})"),
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    for ci in selected:
        ci.zone = Zone.HAND
        ps.hand.append(ci)

    # "…reveal it, and draw it.  If it costs 2 or less, you may play it for free"
    # (The Invisible Hand JTL_89).  Pushed AFTER the draw and after this decision is
    # popped, so the free play lands on a clean stack; the whitelist pins the play to
    # exactly the just-drawn card.  DEVIATION: play_from_hand has no decline, so the
    # "you may" collapses to mandatory — a free ≤N-cost unit entering play is never
    # a downside, and declining the search entirely is still available upstream.
    play_cap = ctx.get("then_play_free_cost_max")
    replay_ids = [ci.instance_id for ci in selected
                  if play_cap is not None
                  and int(getattr(ci.card_def, "cost", None) or 0) <= int(play_cap)]

    drawn_names = ", ".join(ci.card_def.display_name for ci in selected) or "nothing"
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="deck_search",
        choice=f"drew {len(selected)} ({drawn_names})",
    ))
    if replay_ids and not s.is_terminal():
        src = s.find_instance(ctx["source_id"])
        if src is not None:
            push_play_from_hand(s, src[1], free=True,
                                eligible_ids=frozenset(replay_ids))
    # "If its cost is the chosen number, you may give N <token> tokens to a <trait>
    # unit" (Sense Through the Force ASH_235) — the number came down from the
    # choose_number decision that pushed this search.  The "you may" is the
    # select_token loop's own always-legal finish.
    tok = ctx.get("then_tokens_if_cost")
    if tok and selected and not s.is_terminal():
        cost = getattr(selected[0].card_def, "cost", None)
        if cost is not None and int(cost) == int(tok.get("number", -1)):
            src = s.find_instance(ctx["source_id"])
            if src is not None:
                push_select_token(
                    s, src[1], token_type=str(tok.get("token") or "Advantage"),
                    max_targets=1, controller=str(tok.get("controller") or "any"),
                    traits=([tok["trait"]] if tok.get("trait") else None),
                    token_count=int(tok.get("count", 1)))
    # "Then, put a card from your hand on top of your deck" (Captain Vaughn TS26_39).
    # Settled HERE, after the pop and after the draw, so the card just drawn is in
    # hand and offered — pushing this decision up front would read an empty hand and
    # fizzle before the search had put anything there.
    if ctx.get("then_top_from_hand") and not s.is_terminal():
        src = s.find_instance(ctx["source_id"])
        if src is not None:
            push_bottom_from_hand(s, src[1], count=1, top_only=True)
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── Peek at the top card of the deck (peek_top / choose_number decisions) ─────

@dataclass
class KeepTopCard(Action):
    """Resolve a 'peek_top' decision by leaving the top card on top (no change)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"):
            raise IllegalActionError("No peek_top decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="left on top",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Leave the top card on top"


@dataclass
class BottomTopCard(Action):
    """Resolve a 'peek_top' (may_bottom) decision by moving the top card to the
    bottom of the deck (R2-D2)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode") != "may_bottom"):
            raise IllegalActionError("No peek_top (may_bottom) decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        if ps.deck:
            ps.deck.append(ps.deck.pop(0))
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="put on bottom",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Put the top card on the bottom"


@dataclass
class DrawTopCard(Action):
    """Resolve a 'peek_top' (may_draw) decision by revealing and drawing the top
    card (C-3PO, when the peeked card's cost matched the chosen number)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode")
                not in ("may_draw", "may_draw_or_discard_heal")):
            raise IllegalActionError("No peek_top (may_draw) decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        _draw_cards(s, ps, 1)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="revealed and drew",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Reveal and draw the top card"


@dataclass
class ChooseNumber(Action):
    """Resolve a 'choose_number' decision (C-3PO): name a number, then peek the
    top card.  If its cost equals the chosen number, a 'peek_top' (may_draw)
    decision follows; otherwise the card is left on top and the effect ends."""
    number: int

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "choose_number"):
            raise IllegalActionError("No choose_number decision pending")
        ctx = state.pending_decisions[-1].context
        if not (int(ctx["lo"]) <= self.number <= int(ctx["hi"])):
            raise IllegalActionError(f"{self.number} is out of range")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ctx = top.context
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="choose_number",
            choice=f"chose {self.number}",
        ))
        ps = s.player_by_id(ctx["controller_id"])
        found = s.find_instance(ctx["source_id"])
        source_ci = found[1] if found else None
        then = ctx.get("then")
        if then and source_ci is not None:
            # Sense Through the Force ASH_235: the chosen number is carried into a
            # deck search, whose DRAW finish pays off only if the drawn card's cost
            # matches it.  The decision is already popped, so the search lands on a
            # clean stack.
            if then.get("kind") == "deck_search_tokens_if_cost":
                push_deck_search(
                    s, source_ci, count=1, eligible=lambda cd: True, up_to=False,
                    window=int(then.get("window", 5)),
                    then_tokens_if_cost={**then, "number": int(self.number)})
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
            return s
        if ps.deck and source_ci is not None:
            top_cost = getattr(ps.deck[0].card_def, "cost", None)
            matched = top_cost is not None and top_cost == self.number
            # Always reveal the top card to the controller so they can study it,
            # even on a miss (a "reveal_only" peek that just leaves it on top) —
            # on a match the "may_draw" peek additionally offers DrawTopCard.
            push_peek_top(s, source_ci, mode="may_draw" if matched else "reveal_only")
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Choose the number {self.number}"


@dataclass
class DiscardTopCard(Action):
    """Resolve a 'peek_top' decision by discarding the top card of the deck (Ezra
    Bridger SOR_192; Reanimated Night Trooper ASH_45's ``may_discard``)."""
    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode")
                not in ("may_play_discard", "may_draw_or_discard_heal",
                        "may_discard")):
            raise IllegalActionError("No peek_top (may_play_discard) decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        ps = s.player_by_id(top.context["controller_id"])
        if ps.deck:
            card = ps.deck.pop(0)
            card.face_down = False
            card.zone = Zone.DISCARD
            ps.discard.append(card)
        # Reinforcement Walker SOR_119: discarding the top card also heals the
        # controller's base by ``discard_heal`` damage.
        heal = int(top.context.get("discard_heal", 0) or 0)
        if heal and ps.base_instance is not None and not _bases_cannot_heal(s):
            before = int(ps.base_instance.damage)
            ps.base_instance.damage = max(0, ps.base_instance.damage - heal)
            note_base_healed(s, ps.base_instance, before - ps.base_instance.damage)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice="discarded",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Discard the top card"


@dataclass
class PlayTopCard(Action):
    """Resolve a 'peek_top' (may_play_discard) decision by playing the top card of
    the deck for its cost (Ezra Bridger SOR_192).  For an upgrade, ``upgrade_target_id``
    names the host.  The decision is popped FIRST so the played card's own keyword /
    When Played triggers land on a clean stack (the "pop, then act" gotcha)."""
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "peek_top"
                or state.pending_decisions[-1].context.get("mode")
                not in ("may_play_discard", "may_play")):
            raise IllegalActionError("No peek_top play decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ps = s.player_by_id(top.context["controller_id"])
        if not ps.deck:
            raise IllegalActionError("Deck is empty; nothing to play")
        ci = ps.deck[0]
        reduction = int(top.context.get("cost_reduction", 0) or 0)
        free = bool(top.context.get("free"))
        base = _play_cost(s, ci, ps, target_host_id=self.upgrade_target_id)
        cost = 0 if free else max(0, base - reduction)
        if not _affordable_with_credits(ps, cost, s):
            raise IllegalActionError("Cannot afford the top card")
        # "You may use the Force … If you do, play that card" (As I Have Foreseen
        # LOF_188): the Force token is the price of THIS option.  Spent through the
        # single chokepoint, so the WhenYouUseForce observers see it.
        if top.context.get("force_cost"):
            if not spend_force_token(s, ps):
                raise IllegalActionError("No Force token to spend")
        # Pop the decision before the card enters play (so its own triggers land on
        # a clean stack), then remove it from the deck and play it.
        s.pending_decisions.pop()
        ps.deck.pop(0)
        ci.face_down = False
        _pay_play_cost(s, ps, cost)
        _consume_play_discount(s, ci, ps)
        _consume_standing_discount(s, ci, ps)
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="peek_top",
            choice=f"played {ci.card_def.display_name}",
        ))
        card_played_evt = CardPlayed(
            player_id=ps.player_id,
            instance_id=ci.instance_id,
            card_name=ci.card_def.display_name,
            cost_paid=cost,
        )
        s.event_log.append(card_played_evt)
        card_aspects = {a.name for a in (getattr(ci.card_def, "aspects", None) or ())}
        if "Villainy" in card_aspects:
            s.game_memory.villainy_players_this_phase.add(ps.player_id)
        after_idx = top.after_resolve_player_index
        if isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, cost_paid=cost)
        elif isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id)
        elif isinstance(ci.card_def, Event):
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
            _resolve_event_ability(s, ps, ci, after_idx)
        else:
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
        get_bus().fire(s, card_played_evt)
        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx)
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = after_idx
        return s

    def describe(self) -> str:
        return "Play the top card" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


# ── Peek at top of deck (R2-D2 SOR_236, C-3PO SOR_238) ────────────────

def _peek_top_actions(state: GameState, top: PendingDecision) -> list[Action]:
    mode = top.context.get("mode")
    if mode == "may_draw_or_discard_heal":
        # Reinforcement Walker SOR_119: a mandatory binary — no KeepTopCard.
        return [DrawTopCard(), DiscardTopCard()]
    acts = [KeepTopCard()]
    if mode == "may_bottom":
        acts.append(BottomTopCard())
    elif mode == "may_discard":
        # "Look at the top card of a deck.  You may discard it" (Reanimated
        # Night Trooper ASH_45) — the discard sibling of ``may_bottom``.
        acts.append(DiscardTopCard())
    elif mode == "may_draw":
        acts.append(DrawTopCard())
    elif mode in ("may_play_discard", "may_play"):
        if mode == "may_play_discard":
            acts.append(DiscardTopCard())
        # The play cost may be reduced (or free) — apply the same reduction the
        # PlayTopCard resolution will, so affordability and the offer agree.
        reduction = int(top.context.get("cost_reduction", 0) or 0)
        free = bool(top.context.get("free"))
        ps = state.player_by_id(top.context["controller_id"])
        if ps.deck:
            ci = ps.deck[0]
            cd = ci.card_def
            if isinstance(cd, Upgrade):
                for host in _eligible_upgrade_targets(state, ci):
                    base = _play_cost(state, ci, ps, target_host_id=host.instance_id)
                    cost = 0 if free else max(0, base - reduction)
                    if _affordable_with_credits(ps, cost, state):
                        acts.append(PlayTopCard(host.instance_id))
            elif isinstance(cd, (Unit, Event)):
                base = _play_cost(state, ci, ps)
                cost = 0 if free else max(0, base - reduction)
                if _affordable_with_credits(ps, cost, state):
                    acts.append(PlayTopCard())
    return acts


# ── Choose a number (C-3PO SOR_238) ───────────────────────────────────

def _choose_number_actions(state: GameState, top: PendingDecision) -> list[Action]:
    ctx = top.context
    return [ChooseNumber(n)
            for n in range(int(ctx["lo"]), int(ctx["hi"]) + 1)]


# ── Owner of a chosen in-play unit puts it on top or bottom of their deck

#    (Qui-Gon Jinn LOF_200) ─────────────────────────────────────────────────
def _put_on_deck_actions(state: GameState, top: PendingDecision) -> list[Action]:
    card_id = top.context.get("card_id")
    return [PutOnDeckTop(card_id), PutOnDeckBottom(card_id)]


# ── Deck search-and-select push helper (Tarkin SOR_84, Recruit SOR_123) ───────

def _search_window_doubled(s: GameState, searcher_id: str) -> bool:
    """Whether ``searcher_id`` has a ``SearchWindowDoubler`` in play (Arcana Star
    Map ASH_84).  Walks their arena units AND each unit's attached upgrades, so the
    marker works printed on a unit or conferred by an upgrade onto its host; a
    suppressed host (Mind Trick LOF_202 / Imprisoned SHD_72) confers nothing."""
    from swu.abilities.registry import get_abilities, SearchWindowDoubler
    ps = s.player_by_id(searcher_id)
    for host in ps.ground_arena + ps.space_arena:
        if ability_suppressed(s, host):
            continue
        for ci in (host, *host.attached_upgrades):
            if not hasattr(ci.card_def, "set_code"):
                continue
            if any(isinstance(spec, SearchWindowDoubler)
                   for spec in get_abilities(ci.card_def.set_code or "",
                                             ci.card_def.card_number or "")):
                return True
    return False


def push_deck_search(
    s: GameState, source_ci: CardInstance,
    *,
    count: int,
    eligible: Callable[[object], bool],
    up_to: bool,
    window: int = 5,
    rest_disposition: str = "bottom",
    disposition: Optional[str] = None,
    decider_id: Optional[str] = None,
    deck_owner_id: Optional[str] = None,
    play_discount: int = 0,
    then_play_free_cost_max: Optional[int] = None,
    budget: Optional[int] = None,
    then_borrowed_attack_by: Optional[str] = None,
    then_tokens_if_cost: Optional[dict] = None,
    then_top_from_hand: bool = False,
) -> None:
    """Push a 'deck_search' decision: "Search the top ``window`` cards of your deck
    for <eligible> cards, reveal and draw up to ``count`` of them, then put the
    rest on the bottom of your deck in a random order."

    ``disposition`` controls what happens to the SELECTED cards (default ``None`` —
    draw them to hand).  ``"discard_free_replay"`` (Cobb Vanth SHD_115: "search … for
    a unit that costs 2 or less and discard it.  For this phase, you may play that
    card from your discard pile for free") instead sends each selected card to the
    discard pile and flags it in ``game_memory.free_discard_play_this_phase`` (the
    Second Chance SHD_53 free-discard-replay seam).  ``"discard_play_discount"`` is
    its DISCOUNTED sibling (Aid from the Innocent TWI_201: "search the top 10 …
    for 2 Heroism non-unit cards and discard them.  For this phase, you may play
    the discarded cards, and they each cost 2 resources less") — each selected card
    is discarded and recorded in ``game_memory.discard_play_discount_this_phase``
    at ``play_discount`` resources off.

    ``rest_disposition`` controls where the un-taken searched cards go on finish:
    ``"bottom"`` (default — the Tarkin/Recruit convention: bottom in a seeded-random
    order) or ``"discard"`` (I've Found Them IBH_9: "discard the other revealed
    cards").  (The unrelated ``"play"`` disposition is set only by
    ``push_search_and_play`` and keys off ``ctx["disposition"]``.)

    Parameters
    ----------
    count
        Maximum number of cards the controller may take.
    eligible
        Predicate on a card_def — only matching cards among the searched window are
        offered as candidates.  Evaluated once, at push time; the resulting ids are
        stored, so the decision context stays JSON-serialisable.
    up_to
        True for "up to N" (Tarkin): a FinishSearch is always offered, so taking 0
        is legal.  False for "search for a <thing>" (Recruit): the take is mandatory
        if able — a pick is forced while an eligible candidate remains.
    window
        How many top cards to search (default 5).

    The decision is pushed whenever the deck has at least one card in the window
    (even with no eligible candidate — the un-taken searched cards must still be
    bottomed in a random order, which FinishSearch handles).  With an empty deck the
    effect fizzles cleanly and the caller hands the turn over.
    """
    # ``decider_id`` (default: the source's owner) is the player whose deck is
    # searched and who makes the selection — a collector-decided search (a bounty
    # whose "search YOUR deck" resolves for the OPPONENT of the dying host, the
    # push_select_token decider_id convention).  When overridden the turn resumes
    # with whoever is currently active (the attacker mid-combat), not the source's
    # opponent.
    #
    # ``deck_owner_id`` (default: the decider) separates WHOSE DECK is searched from
    # WHO decides — "look at the top 2 cards of the DEFENDING player's deck.  Discard
    # 1 of those cards" (Sabé SEC_17), where the searcher never owns the cards.  The
    # decision context's ``controller_id`` is the deck owner throughout (the window,
    # the finish, and any discard/draw land on their side); ``deciding_player_id``
    # is the searcher.
    searcher_id = decider_id or source_ci.owner_id
    deck_id = deck_owner_id or searcher_id
    ps = s.player_by_id(deck_id)
    # "If you would search a number of cards from your deck, search twice that
    # number of cards instead" (Arcana Star Map ASH_84).  Read HERE — the single
    # entry point where the window is still just a number — so every search route
    # (plain, search-and-play, search-and-play-an-upgrade, a foreign search) is
    # covered at once.  Only the window doubles; ``count`` is untouched.
    if _search_window_doubled(s, searcher_id):
        window = int(window) * 2
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    candidate_ids = [ci.instance_id for ci in searched if eligible(ci.card_def)]
    owner_idx = s.player_index(searcher_id)
    after_idx = (1 - owner_idx) if decider_id is None else s.active_player_index
    dec = PendingDecision(
        deciding_player_id=searcher_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": deck_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": int(count),
            "up_to": bool(up_to),
            "window": int(window),
            "rest_disposition": str(rest_disposition),
            "play_discount": int(play_discount),
            # Combined-COST budget over the picks ("any number of Clone units with
            # combined cost 4 or less" — Sifo-Dyas LOF_117).  The ctx key and both
            # its guards (the enumeration filter and SelectSearchCard's defensive
            # re-check) were built for Darth Vader SOR_87's search-and-play; the
            # plain deck_search push simply had no way to set it before.
            **({"budget": int(budget)} if budget is not None else {}),
            # "…and draw it.  If it costs N or less, you may play it for free"
            # (The Invisible Hand JTL_89) — settled at the draw branch of
            # _finish_deck_search, which whitelists the drawn card into a free
            # push_play_from_hand.  None (the default) leaves the draw alone.
            "then_play_free_cost_max": (int(then_play_free_cost_max)
                                        if then_play_free_cost_max is not None
                                        else None),
            # "…and discard it.  Then, you may attack with this unit.  For this
            # attack, this unit gains the discarded unit's abilities" (Improvised
            # Identity ASH_230) — the named unit's granted attack is pushed at the
            # ``discard`` disposition's finish, borrowing from the discarded card.
            "then_borrowed_attack_by": then_borrowed_attack_by,
            # "If its cost is the chosen number, you may give 3 Advantage tokens to
            # a Force unit" (Sense Through the Force ASH_235) — settled at the DRAW
            # branch, which is the only place the drawn card's cost is known.
            "then_tokens_if_cost": (dict(then_tokens_if_cost)
                                    if then_tokens_if_cost else None),
            # "Then, put a card from your hand on top of your deck" (Captain Vaughn
            # TS26_39) — settled AFTER the search, because the card it just drew is
            # part of what may be put back and the hand may be empty until then.
            "then_top_from_hand": bool(then_top_from_hand),
            **({"disposition": str(disposition)} if disposition else {}),
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=searcher_id,
        kind="deck_search",
    ))


def push_search_and_play(
    s: GameState, source_ci: CardInstance,
    *,
    window: int,
    cost_reduction: int = 0,
    eligible: Optional[Callable[[object], bool]] = None,
    enters_ready: bool = False,
    return_at_regroup: bool = False,
    bottom_at_regroup: bool = False,
    free: bool = False,
    decider_id: Optional[str] = None,
) -> None:
    """Push a 'deck_search' decision that PLAYS the chosen unit (Kelleran Beq
    LOF_100: "Search the top N cards of your deck for a unit, reveal it, and play
    it.  It costs ``cost_reduction`` resources less.").

    The search-and-play variant of ``push_deck_search`` (``disposition="play"``):
    candidates are the units in the top ``window`` cards that the controller can
    afford to play at their effective cost less ``cost_reduction`` (credits cover a
    shortfall, like every other play path).  Exactly one is chosen (``max_select``
    1, ``up_to`` False — mandatory if able, so the play is forced while an
    affordable unit remains); ``_finish_deck_search``'s play branch pays the
    reduced cost, puts the unit into play (firing its own keyword / When Played
    triggers), and bottoms the un-taken searched cards in a seeded-random order.
    With no affordable unit in the window the decision still resolves cleanly via
    FinishSearch (nothing played, the rest bottomed).  An empty deck is a no-op.

    ``eligible`` optionally narrows the searched-for units beyond "any Unit" (Triple
    Dark Raid SHD_194: "search … for a Vehicle").  ``enters_ready`` puts the played
    unit into play ready, and ``return_at_regroup`` flags it to bounce to its owner's
    hand at the start of the next regroup phase ("enters play ready.  Return it to
    its owner's hand at the end of the phase" — reusing the Commandeer JTL_235
    delayed-return flag, the action→regroup boundary).  ``bottom_at_regroup`` is that
    flag's DECK-bound sibling — "At the start of the regroup phase, put that unit on
    the bottom of your deck (if it is still in play)" (Maz Kanata LAW_74), a
    relocation rather than a defeat, so the lent unit's When Defeated never fires.
    """
    # ``decider_id`` (default: the source's owner) is the player whose deck is
    # searched and who plays the found unit under their control — a collector-decided
    # search-and-play (a bounty whose "search YOUR deck … and play it" resolves for
    # the OPPONENT of the dying host; Bounty Hunter's Quarry SHD_123, the
    # push_deck_search decider_id convention).  ``free`` plays the found unit at cost
    # 0 (candidates then need not be affordability-filtered).
    actor_id = decider_id or source_ci.owner_id
    ps = s.player_by_id(actor_id)
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    candidate_ids: list[str] = []
    for ci in searched:
        cd = ci.card_def
        if not isinstance(cd, Unit):
            continue
        if eligible is not None and not eligible(cd):
            continue
        if free:
            candidate_ids.append(ci.instance_id)
            continue
        cost = max(0, _effective_cost(cd, ps, s) - cost_reduction)
        if cost <= ps.available_resources + _usable_credits(s, ps):
            candidate_ids.append(ci.instance_id)
    owner_idx = s.player_index(actor_id)
    after_idx = (1 - owner_idx) if decider_id is None else s.active_player_index
    dec = PendingDecision(
        deciding_player_id=actor_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": actor_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": 1,
            "up_to": False,
            "window": int(window),
            "disposition": "play",
            "cost_reduction": int(cost_reduction),
            "free": bool(free),
            "enters_ready": bool(enters_ready),
            "return_at_regroup": bool(return_at_regroup),
            "bottom_at_regroup": bool(bottom_at_regroup),
        },
        after_resolve_player_index=after_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=actor_id,
        kind="deck_search",
    ))


def push_search_and_play_upgrade(
    s: GameState, source_ci: CardInstance,
    *, window: int, host_id: str, cost_reduction: int = 0,
) -> None:
    """Push a 'deck_search' decision that plays the chosen UPGRADE onto one
    pre-chosen host — "search the top ``window`` cards of your deck for an upgrade
    that can attach to that unit, reveal it, and play it on that unit.  It costs
    ``cost_reduction`` resources less" (Reforge ASH_90).

    The upgrade sibling of ``push_search_and_play``: candidates are the Upgrades in
    the window whose "Attach to …" restriction admits ``host_id`` (the same
    ``_upgrade_target_spec`` gate every other attachment site uses) and which the
    controller can afford at the reduced price.  ``_finish_deck_search``'s
    ``play_upgrade`` branch pays that price, emits CardPlayed and attaches — so the
    upgrade's own When Played trigger fires exactly as a hand play's would.  With no
    eligible upgrade the decision still resolves cleanly (nothing played, the window
    bottomed in a seeded-random order)."""
    from swu.abilities.resolver import _spec_matches_ci
    actor_id = source_ci.owner_id
    ps = s.player_by_id(actor_id)
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    host_res = s.find_instance(host_id)
    if host_res is None:
        return
    _, host = host_res
    candidate_ids: list[str] = []
    for ci in searched:
        cd = ci.card_def
        if not isinstance(cd, Upgrade):
            continue
        spec = _upgrade_target_spec(cd)
        if spec is not None and not _spec_matches_ci(spec, host, ci, s, {}):
            continue
        cost = max(0, _effective_cost(cd, ps, s) - cost_reduction)
        if cost <= ps.available_resources + _usable_credits(s, ps):
            candidate_ids.append(ci.instance_id)
    owner_idx = s.player_index(actor_id)
    dec = PendingDecision(
        deciding_player_id=actor_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": actor_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": 1,
            "up_to": False,
            "window": int(window),
            "disposition": "play_upgrade",
            "upgrade_host_id": host_id,
            "cost_reduction": int(cost_reduction),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=actor_id,
        kind="deck_search",
    ))


def push_search_and_play_multiple(
    s: GameState, source_ci: CardInstance,
    *,
    window: int,
    budget: int,
    eligible: Callable[[object], bool],
    max_units: Optional[int] = None,
) -> None:
    """Push a 'deck_search' decision that PLAYS ANY NUMBER of chosen units FOR FREE
    under a combined-cost budget (Darth Vader SOR_87: "Search the top ``window``
    cards of your deck for any number of [Villainy] units with combined cost
    ``budget`` or less and play each of them for free").

    The multi-select, budgeted, free-play sibling of ``push_search_and_play``:
    ``disposition="play"`` + ``free=True`` (each chosen unit is played at cost 0)
    + ``budget`` (the picked units' combined *printed* cost may not exceed it; the
    ``deck_search`` legal-actions builder shrinks the offered candidates as units
    are taken).  ``up_to=True`` so a FinishSearch is always offered ("any number"
    includes 0).  Candidates are every card in the top ``window`` matching
    ``eligible`` regardless of individual cost — an unaffordable-within-budget one
    simply never becomes selectable.  ``max_select`` is the candidate count (or
    ``max_units`` when a "up to N units" cap applies — U-Wing Reinforcement SOR_104:
    "up to 3 units with combined cost 7 or less"), so the existing per-pick
    auto-finish fires once the cap (or everything) has been taken.
    ``_finish_deck_search``'s play branch pays 0 for each, puts it into play (firing
    its own keyword / When Played triggers), and bottoms the un-taken searched cards
    in a seeded-random order.  An empty deck is a no-op.
    """
    ps = s.player_by_id(source_ci.owner_id)
    searched = ps.deck[:window]
    if not searched:
        return  # empty deck — nothing to search or bottom
    candidate_ids = [ci.instance_id for ci in searched if eligible(ci.card_def)]
    max_select = (len(candidate_ids) if max_units is None
                  else min(len(candidate_ids), int(max_units)))
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="deck_search",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "candidate_ids": candidate_ids,
            "candidates": _candidate_card_views(s, candidate_ids),
            "selected_ids": [],
            "max_select": max_select,
            "up_to": True,
            "window": int(window),
            "disposition": "play",
            "free": True,
            "budget": int(budget),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="deck_search",
    ))


def _deck_search_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top deck_search decision (never empty: a forced
    FinishSearch is offered once no eligible candidate remains)."""
    ctx = top.context
    selected = set(ctx["selected_ids"])
    remaining = [cid for cid in ctx["candidate_ids"] if cid not in selected]
    budget = ctx.get("budget")
    if budget is not None:
        # Combined-cost budget (Darth Vader SOR_87): only offer a candidate whose
        # printed cost fits within the budget left after the already-picked units.
        deck_by_id = {ci.instance_id: ci
                      for ci in state.player_by_id(ctx["controller_id"]).deck}
        spent = sum((deck_by_id[cid].card_def.cost or 0)
                    for cid in selected if cid in deck_by_id)
        left = int(budget) - spent
        remaining = [cid for cid in remaining
                     if cid in deck_by_id
                     and (deck_by_id[cid].card_def.cost or 0) <= left]
    acts: list[Action] = [SelectSearchCard(cid) for cid in remaining]
    if ctx.get("up_to") or not remaining:
        acts.append(FinishSearch())
    return acts


# ── Peek-at-top-of-deck push helpers (R2-D2 SOR_236, C-3PO SOR_238) ───────────

def push_peek_top(s: GameState, source_ci: CardInstance, *, mode: str,
                  cost_reduction: int = 0, free: bool = False,
                  discard_heal: int = 0, force_cost: bool = False) -> None:
    """Push a 'peek_top' decision: the controller looks at the top card of their
    deck and decides what to do with it.

    mode
        ``"may_bottom"`` — R2-D2: KeepTopCard (leave on top) vs BottomTopCard
        (put it on the bottom).
        ``"may_discard"`` — Reanimated Night Trooper ASH_45: KeepTopCard vs
        DiscardTopCard, the discard sibling of ``may_bottom``.
        ``"may_draw"`` — C-3PO, after a cost match: KeepTopCard (leave on top)
        vs DrawTopCard (reveal and draw it).
        ``"reveal_only"`` — C-3PO, after a cost miss: the card is just shown to
        the controller and stays on top (KeepTopCard is the only option, an
        acknowledgement) so the reveal is never invisible.
        ``"may_play_discard"`` — Ezra: KeepTopCard vs DiscardTopCard vs PlayTopCard.
        ``"may_play"`` — You're My Only Hope SOR_246: KeepTopCard vs PlayTopCard
        (no discard option); the play may carry a ``cost_reduction`` / ``free``.
        ``"may_draw_or_discard_heal"`` — Reinforcement Walker SOR_119: a *mandatory*
        binary DrawTopCard vs DiscardTopCard (no KeepTopCard) where discarding also
        heals ``discard_heal`` damage from the controller's base.

    ``cost_reduction`` / ``free`` apply to the play options in the may_play(_discard)
    modes (the top card costs that much less, or is free).  The deck is left
    untouched while the decision is open (the chosen action moves the card), so
    ``card_id`` (the top card's instance id) in the context is purely informational
    (for prompts/logging).  ``peeked_card_id`` / ``peeked_card_name`` carry the
    revealed card's identity so the UI can show it to the deciding player.  An empty
    deck is a clean no-op — no decision is pushed and the caller proceeds (the effect
    simply has nothing to look at)."""
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    top_ci = ps.deck[0]
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="peek_top",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "mode": mode,
            "cost_reduction": int(cost_reduction),
            "free": bool(free),
            "discard_heal": int(discard_heal),
            # "You may use the Force (lose your Force token).  If you do, play that
            # card" (As I Have Foreseen LOF_188) — the Force token is the PRICE of
            # the play option, spent by PlayTopCard and by nothing else, so keeping
            # the card on top costs nothing.
            "force_cost": bool(force_cost),
            "card_id": top_ci.instance_id,
            # The peeked card's true identity. Safe to surface: the decision
            # context is sent only to the deciding player (its own deck), so the
            # opponent never sees it. The UI renders this so the player can study
            # the card before choosing (KeepTopCard / BottomTopCard / DrawTopCard).
            "peeked_card_id": top_ci.card_def.id,
            "peeked_card_name": top_ci.card_def.display_name,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="peek_top",
    ))


def push_choose_number(
    s: GameState, source_ci: CardInstance, *, lo: int = 0, hi: int = 10,
    then: Optional[dict] = None,
) -> None:
    """Push a 'choose_number' decision (C-3PO): the controller names a number in
    ``lo..hi`` (inclusive).  On resolution (see ``ChooseNumber``) the top card is
    peeked; if its cost equals the chosen number a 'peek_top' (may_draw) decision
    follows, otherwise the card is left on top.

    The default range ``0..10`` covers every printed SOR card cost.  An empty
    deck is a clean no-op — there is nothing to peek, so no decision is pushed.

    ``then`` replaces that C-3PO tail with another continuation, dispatched in
    ``ChooseNumber.apply``.  Today the one arm is
    ``{"kind": "deck_search_tokens_if_cost", …}`` — "Choose a number, then search
    the top 5 … and draw it.  If its cost is the chosen number, you may give 3
    Advantage tokens to a Force unit" (Sense Through the Force ASH_235)."""
    ps = s.player_by_id(source_ci.owner_id)
    if not ps.deck:
        return
    owner_idx = s.player_index(source_ci.owner_id)
    dec = PendingDecision(
        deciding_player_id=source_ci.owner_id,
        kind="choose_number",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": source_ci.owner_id,
            "lo": int(lo),
            "hi": int(hi),
            "then": dict(then) if then else None,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=source_ci.owner_id,
        kind="choose_number",
    ))


# ── Put N cards from your hand on the bottom of your deck in any order

@dataclass
class SelectHandCardToBottom(Action):
    """Put the chosen hand card on the bottom of your deck (Private Manufacturing
    TWI_257).  Auto-pops the decision once the required number have been placed."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_hand"):
            raise IllegalActionError("No bottom_from_hand decision pending")
        ctx = state.pending_decisions[-1].context
        ps0 = state.player_by_id(ctx["controller_id"])
        if self.instance_id not in {ci.instance_id for ci in ps0.hand}:
            raise IllegalActionError(f"{self.instance_id} is not in hand")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        card = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.DECK
        card.face_down = True
        ps.deck.append(card)  # the bottom of the deck
        ctx["placed"] = int(ctx.get("placed", 0)) + 1
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="bottom_from_hand",
            choice=f"bottomed {card.card_def.display_name}",
        ))
        # Done once we've placed the required number (or the hand is empty).
        if ctx["placed"] >= int(ctx["count"]) or not ps.hand:
            s.pending_decisions.pop()
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Put {self.instance_id} on the bottom of your deck"


@dataclass
class SelectHandCardToTop(Action):
    """Put the chosen hand card on the TOP of your deck — the other half of the
    "on the top or bottom of your deck" choice (Yoda TWI_4).  Offered only when the
    decision was pushed with ``allow_top=True``; otherwise identical to
    ``SelectHandCardToBottom`` (same decision kind, same placement accounting)."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "bottom_from_hand"):
            raise IllegalActionError("No bottom_from_hand decision pending")
        ctx0 = state.pending_decisions[-1].context
        if not ctx0.get("allow_top"):
            raise IllegalActionError("This decision cannot place cards on top")
        ps0 = state.player_by_id(ctx0["controller_id"])
        if self.instance_id not in {ci.instance_id for ci in ps0.hand}:
            raise IllegalActionError(f"{self.instance_id} is not in hand")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        card = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.DECK
        card.face_down = True
        ps.deck.insert(0, card)  # the top of the deck
        ctx["placed"] = int(ctx.get("placed", 0)) + 1
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="bottom_from_hand",
            choice=f"put {card.card_def.display_name} on top",
        ))
        if ctx["placed"] >= int(ctx["count"]) or not ps.hand:
            s.pending_decisions.pop()
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Put {self.instance_id} on the top of your deck"


def push_bottom_from_hand(s: GameState, source_ci: CardInstance, *, count: int,
                          allow_top: bool = False,
                          top_only: bool = False) -> None:
    """Push a 'bottom_from_hand' decision (Private Manufacturing TWI_257): "Put
    ``count`` cards from your hand on the bottom of your deck in any order."

    Mandatory-if-able: the controller must bottom exactly ``min(count, hand size)``
    cards, picked one at a time (the pick order == bottom-placement order).  Pushed
    only when the controller holds ≥1 card and ``count`` ≥ 1; otherwise it fizzles
    cleanly with no prompt.

    ``allow_top`` additionally offers a ``SelectHandCardToTop`` per hand card, for
    "put a card from your hand on the top **or bottom** of your deck" (Yoda TWI_4) —
    the same decision, one more placement option per card.  ``top_only`` is its
    exclusive form: ONLY the top placement is offered, so "put a card from your hand
    on the top of your deck **and another card on the bottom**" (Kreia's Whispers
    SEC_232) is two pushes of this one decision rather than a new kind."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    cap = min(int(count), len(ps.hand))
    if cap <= 0:
        return  # nothing to bottom — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="bottom_from_hand",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "count": cap,
            "placed": 0,
            "allow_top": bool(allow_top or top_only),
            "top_only": bool(top_only),
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="bottom_from_hand",
    ))


@dataclass
class SelectHandCardToResource(Action):
    """Resource the chosen hand card, READY (Sundari Palace TS26_12: "you may
    resource a card from your hand and ready it").

    The ordinary ``ResourceCard`` action enters a resource face-down and ready, but
    it is the *once-per-turn* regroup/setup move; this is the same placement reached
    from inside an ability, and — unlike Smuggle — the card is NOT replaced from the
    deck, so the row really grows.  Auto-pops the decision once ``count`` cards have
    been resourced or the hand runs out."""
    instance_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_hand"):
            raise IllegalActionError("No resource_from_hand decision pending")
        ctx0 = state.pending_decisions[-1].context
        ps0 = state.player_by_id(ctx0["controller_id"])
        if self.instance_id not in {ci.instance_id for ci in ps0.hand}:
            raise IllegalActionError(f"{self.instance_id} is not in hand")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        ps = s.player_by_id(ctx["controller_id"])
        card = next(ci for ci in ps.hand if ci.instance_id == self.instance_id)
        ps.hand.remove(card)
        card.zone = Zone.RESOURCES
        card.face_down = True
        card.exhausted = False
        ps.resources.append(card)
        s.event_log.append(CardResourced(
            player_id=ps.player_id,
            instance_id=card.instance_id,
            card_name=card.card_def.display_name,
        ))
        ctx["placed"] = int(ctx.get("placed", 0)) + 1
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="resource_from_hand",
            choice=f"resourced {card.card_def.display_name}",
        ))
        if ctx["placed"] >= int(ctx["count"]) or not ps.hand:
            _resolve_resource_from_hand(s)
        return s

    def describe(self) -> str:
        return f"Resource {self.instance_id} from your hand (it enters ready)"


@dataclass
class FinishResourceFromHand(Action):
    """Stop resourcing — the "up to"/"you may" half of the resource_from_hand
    decision.  Always legal while the decision is open (including at zero, which is
    the printed "you MAY resource a card ... for each friendly leader unit")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "resource_from_hand"):
            raise IllegalActionError("No resource_from_hand decision pending")
        s = copy.deepcopy(state)
        _resolve_resource_from_hand(s)
        return s

    def describe(self) -> str:
        return "Stop resourcing cards from your hand"


def _resolve_resource_from_hand(s: GameState) -> None:
    """Pop the decision and settle its rider.  ``then_defeat_resources_at_regroup``
    schedules ONE resource defeat per card actually resourced ("If you do, defeat
    that many friendly resources at the start of the regroup phase" — TS26_12), so
    resourcing nothing schedules nothing."""
    top = s.pending_decisions.pop()
    ctx = top.context
    placed = int(ctx.get("placed", 0))
    if placed and ctx.get("then_defeat_resources_at_regroup"):
        pid = ctx["controller_id"]
        led = s.game_memory.defeat_resources_at_regroup
        led[pid] = int(led.get(pid, 0)) + placed
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index


def push_resource_from_hand(
    s: GameState, source_ci: CardInstance, *, count: int,
    then_defeat_resources_at_regroup: bool = False,
) -> None:
    """Push a 'resource_from_hand' decision: "You may resource up to ``count`` cards
    from your hand, each entering READY" (Sundari Palace TS26_12, whose count is the
    controller's friendly leader units).

    Always "up to" — ``FinishResourceFromHand`` is offered from the start, since the
    printed clause is a per-leader "you may" and ramping is a real cost (the card you
    give up, plus the scheduled resource defeat).  Fizzles cleanly with an empty hand
    or a non-positive count."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    cap = min(int(count), len(ps.hand))
    if cap <= 0:
        return  # nothing to resource — fizzle cleanly
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="resource_from_hand",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "count": cap,
            "placed": 0,
            "then_defeat_resources_at_regroup": bool(
                then_defeat_resources_at_regroup),
        },
        # Using the ability is an action, so the seat passes once it settles (the
        # bottom_from_hand convention).
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="resource_from_hand",
    ))


def _resource_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top resource_from_hand decision — one per hand card,
    plus the always-offered finish (never empty)."""
    ps = state.player_by_id(top.context["controller_id"])
    return ([SelectHandCardToResource(ci.instance_id) for ci in ps.hand]
            + [FinishResourceFromHand()])


def _bottom_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top bottom_from_hand decision (never empty — the
    decision is only pushed with ≥1 hand card and the cost is mandatory, so a
    card is always available to place).  With ``allow_top`` each card is offered
    twice: bottom or top (Yoda TWI_4)."""
    ps = state.player_by_id(top.context["controller_id"])
    if top.context.get("top_only"):
        # The exclusive top placement (Kreia's Whispers SEC_232) — no bottom option.
        return [SelectHandCardToTop(ci.instance_id) for ci in ps.hand]
    acts: list["Action"] = [SelectHandCardToBottom(ci.instance_id) for ci in ps.hand]
    if top.context.get("allow_top"):
        acts += [SelectHandCardToTop(ci.instance_id) for ci in ps.hand]
    return acts

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "deck_search":                   _deck_search_actions,
    "peek_top":                      _peek_top_actions,
    "choose_number":                 _choose_number_actions,
    "put_on_deck":                   _put_on_deck_actions,
    "bottom_from_hand":              _bottom_from_hand_actions,
    "resource_from_hand":            _resource_from_hand_actions,
})
