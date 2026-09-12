"""Primitives that two or more decision families need, and so no family may own.

Everything here was found by measurement rather than judgement, and the measurement is
worth stating because getting it wrong is what kept this file monolithic. Partition
every helper referenced across a family boundary by the *full* set of families that
reference it, the helper's own home family included:

* **exactly one foreign family and never its own home** — the helper is not shared at
  all, it is simply filed under the wrong banner. It travels to that one consumer.
  Fifty-seven of the hundred-odd cross-family helpers turned out to be this, which is
  the measured reason section banners cannot be used to assign code: a banner names the
  card that motivated a helper, not the mechanic that uses it.
* **two or more families, home counted** — genuinely shared. Moving it to a consumer
  would only reverse the arrow, leaving the coupling intact while appearing to fix it.
  It has to move *down* instead, below every family, which is this module.

Fourteen names came out of that second bucket. ``PlayFromDiscard`` and ``PlotPlay``
join them not because they are shared but because they are the Action classes
``_enumerate_discard_play_actions`` and ``_plot_play_actions`` emit — an Action class
belongs with the code that emits it, and leaving them behind would have forced this
module to reach upward for them.

The module sits directly above ``flow`` because two of these helpers use it, and below
``combat`` because nothing here needs the attack pipeline. That position is not a
preference: ``scripts/refactor_parity.py`` and ``tests/test_actions_layering.py`` both
fail if it drifts, and a helper that grows a dependency on a decision family belongs in
that family instead of here.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Event, Leader, Upgrade, Unit
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    CardPlayed, CardResourced,
    DecisionPushed, LeaderDeployed, UpgradePlayed,
)
from swu.engine.keywords import Keyword, has_keyword
from swu.engine.state import CardInstance, GameState, Phase, PlayerState, Zone
from swu.engine.triggers import get_bus

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.costs import (
    _affordable_with_credits, _consume_play_discount, _effective_cost, _exhaust_resources, _pay_play_cost, _play_cost,
)
from swu.engine.actions.zones import (
    _attach_upgrade, _eligible_upgrade_targets, _find_in_arenas, _put_unit_in_play, _resolve_event_ability, note_upgrade_attached,
)
from swu.engine.actions.flow import (
    _assert_phase, _switch_active_player,
)


# ── ACTION phase actions ──────────────────────────────────────────────────────

@dataclass
class PlayFromDiscard(Action):
    """Play a card from the active player's DISCARD pile, paying its printed
    cost, per a ``PlayFromDiscardAction`` ability (Brutal Traditions SHD_38:
    "Action: If an enemy unit was defeated this phase, play this upgrade from
    your discard pile (paying its cost)").

    The card leaves the discard pile, its cost is paid from ready resources, and
    it is played exactly like a hand play (upgrade → attach onto
    ``upgrade_target_id``; a unit enters play) — the ``CardPlayed`` / WhenPlayed /
    observer firing mirrors ``PlayCard`` so a discard-play is indistinguishable
    downstream.  ``free`` skips cost payment (Second Chance SHD_53's granted "play
    it from your discard pile for free" replay, whose one-shot per-phase
    permission is also consumed here).  Availability, affordability, the free
    permission and the legal host set are all re-validated against the live
    discard enumeration on apply, so a stale action cannot force an illegal or
    unearned free play.  ``discount`` is the DISCOUNTED sibling of ``free`` (Aid
    from the Innocent TWI_201's "for this phase, you may play the discarded cards,
    and they each cost 2 resources less"): the normal cost is paid minus that many
    resources (floored at 0) and the one-shot permission is likewise consumed."""
    instance_id: str
    upgrade_target_id: Optional[str] = None
    free: bool = False
    discount: int = 0

    def apply(self, state: GameState) -> GameState:
        _assert_phase(state, Phase.ACTION)
        s = copy.deepcopy(state)
        ps = s.active_player
        # Re-derive the legal discard plays and require this one to be among them
        # (guards the gate condition / free permission, affordability and host).
        if not any(
            isinstance(a, PlayFromDiscard)
            and a.instance_id == self.instance_id
            and a.upgrade_target_id == self.upgrade_target_id
            and a.free == self.free
            and a.discount == self.discount
            for a in _enumerate_discard_play_actions(s, ps)
        ):
            raise IllegalActionError(
                f"Cannot play {self.instance_id} from discard right now")
        # The card is normally in the active player's own discard, but a granted
        # CROSS-PILE free replay (Stolen AT-Hauler JTL_221) plays it out of its
        # OWNER's pile, so fall back to a scan of every discard.  The enumeration
        # guard above has already established that this play is legal.
        holder = ps
        ci = next((c for c in ps.discard if c.instance_id == self.instance_id), None)
        if ci is None:
            for other in s.players:
                found = next((c for c in other.discard
                              if c.instance_id == self.instance_id), None)
                if found is not None:
                    ci, holder = found, other
                    break
        holder.discard.remove(ci)

        if self.free:
            # Consume the one-shot per-phase free-replay permission (Second Chance
            # SHD_53, or the cross-pile JTL_221 grant) so it can't be spent twice.
            s.game_memory.free_discard_play_this_phase.discard(self.instance_id)
            foreign = s.game_memory.foreign_free_discard_play_this_phase
            if self.instance_id in (foreign.get(ps.player_id) or ()):
                foreign[ps.player_id] = [
                    i for i in foreign[ps.player_id] if i != self.instance_id]
            cost = 0
        else:
            cost = _play_cost(s, ci, ps, target_host_id=self.upgrade_target_id)
            if self.discount:
                # Consume the one-shot discounted permission (Aid from the Innocent
                # TWI_201) so the discount can't be spent twice.
                cost = max(0, cost - int(self.discount))
                s.game_memory.discard_play_discount_this_phase.pop(
                    self.instance_id, None)
            # Consume a cross-pile PAID permission (Obi-Wan Kenobi SEC_205), whose
            # waiver rides in ``discount`` and may legitimately be 0.
            foreign_paid = s.game_memory.foreign_discard_play_this_phase
            if self.instance_id in (foreign_paid.get(ps.player_id) or ()):
                foreign_paid[ps.player_id] = [
                    i for i in foreign_paid[ps.player_id] if i != self.instance_id]
            _pay_play_cost(s, ps, cost)

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

        after_idx = 1 - s.active_player_index

        if isinstance(ci.card_def, Upgrade):
            _attach_upgrade(s, ps, ci, self.upgrade_target_id)
        elif isinstance(ci.card_def, (Unit, Leader)):
            _put_unit_in_play(s, ps, ci, play_source="discard", cost_paid=cost)
        elif isinstance(ci.card_def, Event):
            # An EVENT played from the discard pile (Aid from the Innocent TWI_201's
            # discounted permission) goes straight back to the discard and resolves
            # through the same chokepoint as a hand play.
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)
            _resolve_event_ability(s, ps, ci, after_idx)
        else:  # defensive — no other card type can reach a discard play today
            ci.zone = Zone.DISCARD
            ps.discard.append(ci)

        get_bus().fire(s, card_played_evt)

        from swu.abilities.resolver import fire_triggered_abilities
        fire_triggered_abilities(s, card_played_evt, after_all_player_idx=after_idx,
                                 event_ctx={"played_card_id": ci.instance_id})

        if not s.is_terminal() and not s.pending_decisions:
            _switch_active_player(s)
        return s

    def describe(self) -> str:
        return f"Play {self.instance_id} from discard" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


@dataclass
class PlotPlay(Action):
    """Play a card from your resource zone using its Plot keyword.

    Plot ("When you deploy a leader, you may play this card from your resources,
    paying its cost. Replace it with the top card of your deck.") is offered as a
    ``"plot"`` decision pushed by DeployLeader.  Resolving a PlotPlay pays the
    card's *printed* effective cost (aspect-adjusted, minus any cost reductions)
    from the OTHER ready resources, replaces the played card with the deck top
    (face down, ready — so the resource count is preserved, exactly like
    Smuggle), then plays the card normally (unit → arena, upgrade → attach, event
    → resolve) so its own keyword / "When Played" triggers fire.

    Unlike Smuggle, PlotPlay does NOT pop its decision or hand the turn over: a
    single leader deploy may trigger every Plot card in your resources, so the
    "plot" decision stays on the stack and re-offers the remaining Plot cards
    until the player resolves it with FinishPlot.  Any decision a played card
    pushes (e.g. a When Played target choice) lands on top of the still-pending
    plot decision and resolves first (LIFO), after which the plot decision is top
    again.
    """
    instance_id: str
    upgrade_target_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "plot"):
            raise IllegalActionError("No pending Plot decision")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ps = s.player_by_id(top.deciding_player_id)

        if self.instance_id not in top.context.get("plot_ids", []):
            raise IllegalActionError(
                f"{self.instance_id} is not an eligible Plot card")

        ci = None
        for i, r in enumerate(ps.resources):
            if r.instance_id == self.instance_id:
                ci = ps.resources.pop(i)
                break
        if ci is None:
            raise IllegalActionError(
                f"Plot source {self.instance_id} not in resource zone")
        if not has_keyword(s, ci, Keyword.PLOT):
            raise IllegalActionError(
                f"{ci.card_def.display_name} does not have Plot")

        # Plot pays the card's PRINTED cost (not a special bracketed cost like
        # Smuggle), from the OTHER ready resources (ci has already left the zone).
        # ``via_plot`` applies a "next card you play using Plot costs N less"
        # discount (Chancellor Palpatine SEC_1); it is consumed once here.
        cost = _play_cost(s, ci, ps, via_plot=True)
        if ps.available_resources < cost:
            raise IllegalActionError(
                f"Insufficient resources: need {cost}, have {ps.available_resources}")
        _exhaust_resources(ps, cost)
        _consume_play_discount(s, ci, ps, via_plot=True)

        # Replace the played card with the top of the deck (deterministic), as
        # Smuggle does, so the resource count is preserved.
        if ps.deck:
            repl = ps.deck.pop(0)
            repl.zone = Zone.RESOURCES
            repl.face_down = True
            repl.exhausted = False
            ps.resources.append(repl)
            s.event_log.append(CardResourced(
                player_id=ps.player_id,
                instance_id=repl.instance_id,
                card_name=repl.card_def.display_name,
            ))

        ci.face_down = False
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
            _put_unit_in_play(s, ps, ci, play_source="plot")
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

        # SEC_245 "When Has Become Now": an ability (not a leader deploy) that
        # plays ONE Plot card and — "if you do" — ramps.  Do the ramp now (net +1
        # resource, on top of Plot's own replace-with-deck-top), then remove THIS
        # plot decision (single-shot: it may no longer be on top if the played
        # card pushed its own decision, so remove it by identity).
        if top.context.get("plot_ability"):
            if top.context.get("ramp_after"):
                _resource_top_of_deck(s, ps)
            for i, d in enumerate(s.pending_decisions):
                if d is top:
                    del s.pending_decisions[i]
                    break
            if not s.is_terminal() and not s.pending_decisions:
                s.active_player_index = after_idx
            return s

        # Do NOT pop the plot decision or switch the active player: more Plot
        # cards may still be playable off this same leader deploy.  Any decision a
        # played card pushed sits on top of the plot decision and resolves first.
        return s

    def describe(self) -> str:
        return f"Plot {self.instance_id}" + (
            f" on {self.upgrade_target_id}" if self.upgrade_target_id else ""
        )


# ── Restock SOR_252: bottom up-to-N cards from a discard pile ─────────────────

def _candidate_card_views(s: GameState, instance_ids) -> list[dict]:
    """``[{instance_id, card_id, card_name}]`` for the given instance ids, so a
    "select one of these cards" decision can carry the candidates' identities in
    its context for the UI to render (images + names).

    Used for decisions whose candidate cards are NOT laid out as clickable board
    subjects in the web client — cards in the **deck** (deck_search: redacted to
    the deciding player, so only the searcher sees them) or in the **discard /
    hand** (return_from_discard, the Sarlacc's discard recycle, a discard-played
    play_from_hand — all already public).  Without this the web UI had no way to
    pick the card (the deck is hidden; the discard pile is a non-clickable pile),
    leaving those decisions unresolvable on a touch device."""
    out: list[dict] = []
    for iid in instance_ids:
        res = s.find_instance(iid)
        if res is None:
            continue
        ci = res[1]
        out.append({
            "instance_id": iid,
            "card_id": ci.card_def.id,
            "card_name": ci.card_def.display_name,
        })
    return out


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───

def _deploy_leader_into_arena(s: GameState, ps: PlayerState,
                              leader_ci: CardInstance) -> GameState:
    """Flip an undeployed leader into its arena, ready, and fire the deploy bus.

    The shared body of ``DeployLeader.apply`` (minus the resource/threshold check
    and the end-of-action active-player switch), so a card ability can deploy a
    leader *as an effect* (free, off-threshold) — Grogu ASH_18 "When you play a
    unique unit that costs 4 or more: you may deploy him".  Fires ``LeaderDeployed``
    + its ``WhenDeployed`` triggers and the Plot check, exactly like a normal
    deploy; the caller owns any turn-flow switch.
    """
    ps.base_zone.remove(leader_ci)
    target_zone = leader_ci.zone_for_arena()
    leader_ci.zone = target_zone
    leader_ci.deployed = True
    leader_ci.epic_action_spent = True
    # CR: a deployed leader enters the arena READY ("Flip him, ready him, and
    # move him to the ground arena"), even if it was exhausted before —
    # unlike a non-leader unit, which enters exhausted. So a freshly deployed
    # leader can attack the same round.
    leader_ci.exhausted = False
    arena_list = ps.ground_arena if target_zone == Zone.GROUND_ARENA else ps.space_arena
    arena_list.append(leader_ci)
    # A deployed leader ENTERED PLAY this phase, exactly like a played unit — the
    # cards that count "friendly units that entered play this phase (including
    # tokens and leaders)" say so explicitly (Anakin Skywalker TS26_2, Padmé
    # Amidala TS26_4), and so does Hidden's own leader reminder ("can't be attacked
    # if she was deployed this phase" — Asajj Ventress TS26_7), which reads this
    # same set through ``_hidden_protected``.  Recorded before the deploy bus fires,
    # so a WhenDeployed ability already sees it.
    s.game_memory.units_played_this_phase.add(leader_ci.instance_id)
    deploy_evt = LeaderDeployed(
        player_id=ps.player_id,
        instance_id=leader_ci.instance_id,
        leader_name=leader_ci.card_def.display_name,
        arena=leader_ci.arena() or "Ground",
    )
    s.event_log.append(deploy_evt)
    get_bus().fire(s, deploy_evt)
    # Phase 3: "When Deployed" triggers (Leia Organa LAW_10).  The leader is
    # now in the arena (deployed), so _collect_triggers sees it as the
    # deployed-side source; fire_triggered_abilities may push a decision.
    from swu.abilities.resolver import fire_triggered_abilities
    after_idx = 1 - s.active_player_index
    s = fire_triggered_abilities(s, deploy_evt, after_all_player_idx=after_idx)
    # Plot: "When you deploy a leader, you may play this card from your
    # resources, paying its cost."  Snapshot the deploying player's Plot
    # resources and, if any can actually be played now, push a "plot"
    # decision.  (fire_triggered_abilities does not change active_player, so
    # s.active_player is still the deploying player.)
    ps = s.active_player
    plot_ids = [] if s.is_terminal() else _plot_eligible_resource_ids(s, ps)
    if plot_ids and _plot_play_actions(s, ps, set(plot_ids)):
        s.pending_decisions.append(PendingDecision(
            deciding_player_id=ps.player_id,
            kind="plot",
            context={"plot_ids": plot_ids},
            after_resolve_player_index=1 - s.active_player_index,
        ))
        s.event_log.append(DecisionPushed(
            deciding_player_id=ps.player_id,
            kind="plot",
        ))
    return s


# ── Sacrifice-a-resource push helper (Wrecker SHD_154) ────────────────────────

def _sacrifice_damage_targets(state: GameState, ctx: dict) -> list[str]:
    """Legal instance ids for the follow-up damage of a sacrifice_resource
    decision (recomputed from current state).  For Wrecker: any ground unit of
    either player (controller filter / arena come from the stored context)."""
    controller_id = ctx["controller_id"]
    target_controller = ctx.get("target_controller", "any")
    arena = ctx.get("target_arena")  # "ground" / "space" / None
    out: list[str] = []
    for p in state.players:
        if target_controller == "friendly" and p.player_id != controller_id:
            continue
        if target_controller == "enemy" and p.player_id == controller_id:
            continue
        units = []
        if arena in (None, "ground"):
            units += p.ground_arena
        if arena in (None, "space"):
            units += p.space_arena
        out.extend(u.instance_id for u in units)
    return out


# ── The DEFENDING player may rescue one of their own cards guarded by a unit;

def _apply_defeat_unit_by_id(s: GameState, instance_id: str) -> None:
    """Defeat an in-play unit by id via the resolver's shared defeat path."""
    from swu.abilities.resolver import _apply_defeat_unit
    _apply_defeat_unit(s, instance_id)


# ── Player-directed damage distribution push helpers ──────────────────────────

def spend_force_token(s: GameState, ps: PlayerState) -> bool:
    """Use the Force for ``ps`` — spend their Force token (the single per-player
    boolean).  The one chokepoint for "use the Force": the ``UseForce`` ability
    cost, the ``use_force`` decision, and every card's force-spending
    ``CustomEffect`` route through here, so the WhenYouUseForce observer (Yoda
    LOF_101) sees every spend.

    Records the spender's player id in ``GameMemory.force_uses`` (drained at the
    settle-point by ``_fire_force_observers``).  Returns True if a token was spent,
    False if the player had none — so a caller can keep its "if you do" early-return
    (a spend that never happened must not trigger the observer)."""
    if not getattr(ps, "has_force_token", False):
        return False
    ps.has_force_token = False
    s.game_memory.force_uses.append(ps.player_id)
    return True


def _take_from_hand(ps: PlayerState, instance_id: str) -> CardInstance:
    for i, ci in enumerate(ps.hand):
        if ci.instance_id == instance_id:
            ps.hand.pop(i)
            return ci
    raise IllegalActionError(f"Card {instance_id} not found in hand")


def _find_in_arenas_any(state: GameState, instance_id: str) -> Optional[CardInstance]:
    """Find a unit by id across both players' arenas (None once defeated)."""
    for ps in state.players:
        found = _find_in_arenas(ps, instance_id)
        if found is not None:
            return found
    return None


# ── distribute_damage decision helpers ───────────────────────────────────────

def _enumerate_discard_play_actions(
    state: GameState, ps: PlayerState
) -> list["Action"]:
    """Legal ``PlayFromDiscard`` actions for cards in ``ps``'s discard pile that
    carry a ``PlayFromDiscardAction`` spec (Brutal Traditions SHD_38).

    The discard pile is a new legal-action source, scanned here in the ACTION
    phase and mirroring the hand-play enumeration: the spec's ``condition`` must
    hold, and — for an Upgrade — the play is offered once per legal "Attach to …"
    host the controller can afford (cost can depend on the host).  Empty unless a
    discard card actually satisfies its gate and is playable, so the action never
    appears when it could do nothing."""
    from swu.abilities.registry import get_abilities, PlayFromDiscardAction
    out: list[Action] = []
    # (a) Cards carrying a printed play-from-discard Action (Brutal Traditions
    #     SHD_38): gated by ``condition``, played by paying the normal cost.
    for ci in ps.discard:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        for spec in get_abilities(sc, cn):
            if not isinstance(spec, PlayFromDiscardAction):
                continue
            if spec.condition is not None and not spec.condition.evaluate(state, ci):
                continue
            if isinstance(ci.card_def, Upgrade):
                for target in _eligible_upgrade_targets(state, ci):
                    cost = _play_cost(state, ci, ps, target_host_id=target.instance_id)
                    if _affordable_with_credits(ps, cost, state):
                        out.append(PlayFromDiscard(ci.instance_id, target.instance_id))
            else:
                cost = _play_cost(state, ci, ps)
                if _affordable_with_credits(ps, cost, state):
                    out.append(PlayFromDiscard(ci.instance_id))
    # (b) Units granted a FREE per-phase replay by Second Chance SHD_53 (a
    #     per-instance permission in game_memory).  A unit re-enters play with no
    #     host and no cost; leaders can never carry the grant (Attach to a
    #     non-leader unit), so this is Unit-only.
    free_ids = getattr(state.game_memory, "free_discard_play_this_phase", None) or set()
    for ci in ps.discard:
        if ci.instance_id in free_ids and isinstance(ci.card_def, Unit):
            out.append(PlayFromDiscard(ci.instance_id, free=True))
    # (b2) Units in ANOTHER player's discard pile that this player was granted a
    #      free replay of (Stolen AT-Hauler JTL_221 "Choose an opponent.  For this
    #      phase, they may play this unit from its owner's discard pile for free").
    #      The card never leaves its owner's pile until it is played, and it enters
    #      under the player who plays it (control follows the holder).
    foreign = (getattr(state.game_memory,
                       "foreign_free_discard_play_this_phase", None) or {})
    permitted = set(foreign.get(ps.player_id, ()))
    if permitted:
        for other in state.players:
            if other.player_id == ps.player_id:
                continue
            for ci in other.discard:
                if ci.instance_id in permitted and isinstance(ci.card_def, Unit):
                    out.append(PlayFromDiscard(ci.instance_id, free=True))
    # (b3) Cards in ANOTHER player's discard pile this player may play this phase by
    #      PAYING the cost, with the card's aspect penalties waived (Obi-Wan Kenobi
    #      SEC_205).  The waiver is expressed as a ``discount`` equal to the aspect
    #      penalty the payer would otherwise owe, so the cost path is the shared one.
    foreign_paid = (getattr(state.game_memory,
                            "foreign_discard_play_this_phase", None) or {})
    paid_ids = set(foreign_paid.get(ps.player_id, ()))
    if paid_ids:
        for other in state.players:
            if other.player_id == ps.player_id:
                continue
            for ci in other.discard:
                if ci.instance_id not in paid_ids:
                    continue
                penalty = max(0, _effective_cost(ci.card_def, ps, state)
                              - int(getattr(ci.card_def, "cost", None) or 0))
                if isinstance(ci.card_def, Upgrade):
                    for target in _eligible_upgrade_targets(state, ci):
                        cost = max(0, _play_cost(state, ci, ps,
                                                 target_host_id=target.instance_id)
                                   - penalty)
                        if _affordable_with_credits(ps, cost, state):
                            out.append(PlayFromDiscard(
                                ci.instance_id, target.instance_id,
                                discount=penalty))
                else:
                    cost = max(0, _play_cost(state, ci, ps) - penalty)
                    if _affordable_with_credits(ps, cost, state):
                        out.append(PlayFromDiscard(ci.instance_id, discount=penalty))
    # (c) Cards granted a DISCOUNTED per-phase play from the discard pile (Aid from
    #     the Innocent TWI_201).  Any card type — the granting card discards
    #     non-units — so an Upgrade is offered once per legal host, like (a).
    discounts = getattr(
        state.game_memory, "discard_play_discount_this_phase", None) or {}
    for ci in ps.discard:
        red = int(discounts.get(ci.instance_id, 0))
        if red <= 0:
            continue
        if isinstance(ci.card_def, Upgrade):
            for target in _eligible_upgrade_targets(state, ci):
                cost = max(0, _play_cost(state, ci, ps,
                                         target_host_id=target.instance_id) - red)
                if _affordable_with_credits(ps, cost, state):
                    out.append(PlayFromDiscard(ci.instance_id, target.instance_id,
                                               discount=red))
        else:
            cost = max(0, _play_cost(state, ci, ps) - red)
            if _affordable_with_credits(ps, cost, state):
                out.append(PlayFromDiscard(ci.instance_id, discount=red))
    return out


def _eligible_pilot_targets(state: GameState, ps: PlayerState) -> list[CardInstance]:
    """Friendly Vehicle units the active player may attach a Pilot upgrade to."""
    from swu.engine.traits import has_trait
    targets = []
    for ci in ps.ground_arena + ps.space_arena:
        if has_trait(state, ci, "Vehicle"):
            targets.append(ci)
    return targets


def _attach_pilot(
    s: GameState, ps: PlayerState, pilot_ci: CardInstance, vehicle_target_id: str,
) -> None:
    """Attach a Unit pilot to a friendly Vehicle unit, firing UpgradePlayed."""
    pilot_ci.face_down = False
    for owner_ps in s.players:
        for unit_ci in owner_ps.ground_arena + owner_ps.space_arena:
            if unit_ci.instance_id == vehicle_target_id:
                pilot_ci.zone = unit_ci.zone
                unit_ci.attached_upgrades.append(pilot_ci)
                note_upgrade_attached(s, unit_ci)      # Sabine Wren ASH_208
                evt = UpgradePlayed(
                    player_id=ps.player_id,
                    instance_id=pilot_ci.instance_id,
                    card_name=pilot_ci.card_def.display_name,
                    attached_to_instance_id=vehicle_target_id,
                )
                s.event_log.append(evt)
                get_bus().fire(s, evt)
                from swu.abilities.resolver import fire_triggered_abilities
                after_idx = 1 - s.player_index(ps.player_id)
                fire_triggered_abilities(s, evt, after_all_player_idx=after_idx,
                                         event_ctx={"attached_to_id": vehicle_target_id,
                                                    "via_pilot": True})
                return
    raise IllegalActionError(f"Pilot vehicle target {vehicle_target_id} not found in any arena")


def _plot_eligible_resource_ids(state: GameState, ps: PlayerState) -> list[str]:
    """Instance ids of resources carrying the Plot keyword (the snapshot taken
    when a leader deploys — see DeployLeader / PlotPlay)."""
    return [ci.instance_id for ci in ps.resources
            if has_keyword(state, ci, Keyword.PLOT)]


def _plot_play_actions(
    state: GameState, ps: PlayerState, allowed_ids: "set[str]"
) -> list[Action]:
    """PlotPlay actions for every Plot resource the player may play right now.

    A resource is offered iff it is in ``allowed_ids`` (the set snapshotted at
    leader-deploy time, so a card later drawn into the zone as a replacement is
    not retroactively plottable), still carries Plot, and its printed effective
    cost is payable from the OTHER ready resources.  An upgrade additionally
    needs a legal host.
    """
    acts: list[Action] = []
    for ci in ps.resources:
        if ci.instance_id not in allowed_ids:
            continue
        if not has_keyword(state, ci, Keyword.PLOT):
            continue
        cost = _play_cost(state, ci, ps, via_plot=True)
        other_ready = sum(
            1 for r in ps.resources
            if not r.exhausted and r.instance_id != ci.instance_id
        )
        if other_ready < cost:
            continue
        if isinstance(ci.card_def, Upgrade):
            for target in _eligible_upgrade_targets(state, ci):
                acts.append(PlotPlay(ci.instance_id, target.instance_id))
        else:
            acts.append(PlotPlay(ci.instance_id))
    return acts


def _resource_top_of_deck(s: GameState, ps: PlayerState) -> None:
    """Put the top card of ``ps``'s deck into play as a ready resource (face down).

    The shared ramp primitive behind "put the top card of your deck into play as a
    resource" (When Has Become Now SEC_245; mirrors the Price on Your Head SHD_125
    bounty).  No-op on an empty deck."""
    if not ps.deck:
        return
    ci = ps.deck.pop(0)
    ci.zone = Zone.RESOURCES
    ci.face_down = True
    ci.exhausted = False
    ps.resources.append(ci)
    s.event_log.append(CardResourced(
        player_id=ps.player_id,
        instance_id=ci.instance_id,
        card_name=ci.card_def.display_name,
    ))
