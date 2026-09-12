"""Choosing who receives a token, and three small mechanics with nowhere better to live.

The token family proper is two decisions: choose up to N units and give each a token, and
pay resources one at a time to convert them into Experience. Note the division of labour --
making a token is ``zones._create_token_units`` and *Shield's* behaviour is engine-native in
``damage._deal_damage_with_shield``; this module only ever decides **who gets one**. That
separation is why the Shield token card carries no ability-registry entry and must not be
given one: its rule is implemented, just not as an encoded ability.

Also here, and honestly rather than by pretending a theme:

* ``plot`` — the Plot keyword's decision, playing a card set aside as a resource.
* ``deploy_leader_as_effect`` — deploying a leader because an ability said so (Grogu
  ASH_18) rather than because the deploy cost was paid, so no resource or threshold cost
  applies and it is a no-op if the leader is already out.
* ``arm_when_played_redo`` — arming one "you may use that When Played ability again this
  phase" charge (Qui-Gon Jinn's Aethersprite LOF_197).

Each of those is one to three definitions. A module per mechanic is worth having; a module
per definition is filing, so they sit with the nearest neighbour rather than fragmenting the
package further -- the same judgement that folded ambush, damage prevention and event
suppression into the kernel rather than giving each a file of its own.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    DecisionPushed, DecisionResolved,
)
from swu.engine.state import CardInstance, GameState, PlayerState, Zone

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.costs import (
    _defeat_credit, _exhaust_resources,
)
from swu.engine.actions.zones import (
    _create_token_units, _draw_cards,
)
from swu.engine.actions.shared import (
    _deploy_leader_into_arena, _plot_play_actions,
)
from swu.engine.actions.combat import (
    _select_token_targets,
)
from swu.engine.actions.deck import (
    push_deck_search,
)


# ── ACTION phase actions ──────────────────────────────────────────────────────

@dataclass
class FinishPlot(Action):
    """Decline to play any (more) Plot cards off a leader deploy."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "plot"):
            raise IllegalActionError("No pending Plot decision")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="plot",
            choice="finish",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Finish Plot (play no more cards)"


# ── Pay up to N resources, give that many Experience tokens to this unit

@dataclass
class PayResourceForToken(Action):
    """Pay one ready resource toward Curious Flock LOF_255 — exhausts a resource and
    gives one Experience token to the source unit."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_resources_for_tokens"):
            raise IllegalActionError("No pay_resources_for_tokens decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if not _pay_resources_for_tokens_can_pay(s, ctx):
            raise IllegalActionError("Cannot spend another cost item")
        ps = s.player_by_id(ctx["controller_id"])
        if ctx.get("cost_source") == "credit":
            _defeat_credit(s, ps)          # defeat a friendly Credit token (Cad Bane)
        elif ctx.get("cost_source") == "return_resource":
            _return_one_resource_to_owner(s, ps)   # Intimidator LAW_140
        else:
            _exhaust_resources(ps, 1)
        ctx["paid"] = int(ctx.get("paid", 0)) + 1
        if ctx.get("payoff") == "credit":
            # "For each resource returned this way, create a Credit token"
            # (Intimidator LAW_140).  A Credit is a pile entry, not a card entering
            # play, so it needs no pop-then-act care and is granted inline.
            from swu.engine.tokens import create_credit_token
            create_credit_token(s, ps)
        # The token-upgrade payoff is granted inline; the damage (SOR_138) and
        # token-unit (TWI_125) payoffs are tallied via ``paid`` and settled once at
        # resolve (pop-then-act), so nothing is granted here for those.
        if ctx.get("payoff", "token") == "token":
            # ``token_target_id`` puts the tokens on a CHOSEN unit rather than the
            # source ("Choose a non-leader unit and pay any number of resources.
            # For each resource paid this way, give an Experience token to the
            # chosen unit" — Emergency Powers SEC_40).  A target that has left play
            # simply receives nothing.
            result = s.find_instance(ctx.get("token_target_id") or ctx["source_id"])
            if result is not None:
                owner_ps, token_host = result
                from swu.engine.tokens import attach_token
                attach_token(s, owner_ps, token_host, ctx.get("token_type", "Experience"))
        # Auto-resolve once the cap is hit or no ready resource remains.
        if not _pay_resources_for_tokens_can_pay(s, ctx):
            return _resolve_pay_resources_for_tokens(s, top)
        return s

    def describe(self) -> str:
        return "Pay a resource for an Experience token"


@dataclass
class FinishPayResources(Action):
    """Stop paying resources ("up to N") — tokens were given inline as each resource
    was paid, so this just pops the decision (Curious Flock LOF_255)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_resources_for_tokens"):
            raise IllegalActionError("No pay_resources_for_tokens decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_pay_resources_for_tokens(s, top)

    def describe(self) -> str:
        return "Finish paying resources"


# ── New primitive: select-up-to-N units, give each a token (Medal Ceremony) ───

@dataclass
class SelectTokenTarget(Action):
    """Give a token to one eligible unit and (if more remain) keep selecting
    (Medal Ceremony SOR_245)."""
    target_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_token"):
            raise IllegalActionError("No select-token decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if self.target_id not in _select_token_targets(s, ctx):
            raise IllegalActionError(f"{self.target_id} is not an eligible token target")
        result = s.find_instance(self.target_id)
        if result is not None:
            ps, ci = result
            if ctx.get("token_type"):
                from swu.engine import tokens
                # ``token_count`` gives MORE THAN ONE token per chosen unit —
                # "give 2 Experience tokens to it" (The Burden of Masters LOF_125);
                # 1 (the default) is every prior caller.
                for _ in range(max(1, int(ctx.get("token_count", 1) or 1))):
                    tokens.attach_token(s, ps, ci, ctx["token_type"])
            # A SECOND token of a DIFFERENT kind on each chosen unit — "give an
            # Experience token AND a Shield token to a unit" (The Ghost LAW_69);
            # ``token_count`` only repeats the one kind.
            if ctx.get("extra_token_type"):
                from swu.engine import tokens as _tk
                _tk.attach_token(s, ps, ci, ctx["extra_token_type"])
            # BUFF mode: instead of (or as well as) a token, each chosen unit takes
            # a stat modifier — "Give each chosen unit +2/+2 for this phase"
            # (Kalani TWI_85).  Same select-up-to-N flow; only the payoff differs.
            if ctx.get("power_bonus") or ctx.get("hp_bonus"):
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=self.target_id,
                    kind="stats",
                    value={"power": int(ctx.get("power_bonus", 0) or 0),
                           "hp": int(ctx.get("hp_bonus", 0) or 0)},
                    duration=ctx.get("duration", "this_phase"),
                ))
            # READY mode: "Ready up to 3 units.  Each of those units gets +1/+0
            # and gains Overwhelm for this phase" (Planetary Invasion TWI_178) —
            # the same select-up-to-N flow with two more payoffs stacked on the
            # buff.  A keyword grant rides the same ``duration`` as the stats.
            if ctx.get("ready"):
                ci.exhausted = False
            # EXHAUST mode (No One Ever Knew SEC_196), honouring Protection exactly
            # as the declarative ExhaustCard arm does.
            if ctx.get("exhaust"):
                from swu.abilities.resolver import _target_protected
                src = s.find_instance(ctx["source_id"])
                src_ci = src[1] if src is not None else None
                if src_ci is None or not _target_protected(
                        s, self.target_id, src_ci, "exhaust"):
                    ci.exhausted = True
            # SUPPRESS mode: "Choose any number of friendly units.  They lose all
            # abilities for this round" (Kazuda Xiono JTL_18) — the same
            # select-up-to-N flow whose payoff is the unified ability-suppression
            # read-layer flag (Mind Trick LOF_202), lifted at the round rollover.
            if ctx.get("suppress_abilities"):
                ci.abilities_suppressed = True
            for kw in ctx.get("grant_keywords") or []:
                from swu.engine.state import Modifier
                s.modifiers.append(Modifier(
                    modifier_id=s.alloc_modifier_id(),
                    source_instance_id=ctx["source_id"],
                    target_instance_id=self.target_id,
                    kind="keyword_grant",
                    value={"keyword": kw, "value": 0},
                    duration=ctx.get("duration", "this_phase"),
                ))
        ctx["chosen"].append(self.target_id)
        ctx["remaining"] = int(ctx["remaining"]) - 1
        # Stop when the cap is reached or no further eligible unit remains.
        if int(ctx["remaining"]) <= 0 or not _select_token_targets(s, ctx):
            return _resolve_select_token(s, top)
        return s

    def describe(self) -> str:
        return f"Choose {self.target_id}"


@dataclass
class FinishSelectToken(Action):
    """Stop selecting token targets ("up to N") — resolve the decision (Medal
    Ceremony SOR_245)."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "select_token"):
            raise IllegalActionError("No select-token decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        return _resolve_select_token(s, top)

    def describe(self) -> str:
        return "Finish giving tokens"


def deploy_leader_as_effect(s: GameState, leader_id: str) -> GameState:
    """Deploy a specific undeployed leader as the *result of a card ability*.

    Grogu ASH_18 "you may deploy him".  No resource / threshold cost is paid; a
    no-op if the leader is already deployed or not in its base zone.  The turn-flow
    switch is the resolver's job (this runs inside trigger resolution), so this
    only flips the leader in and fires the deploy bus via ``_deploy_leader_into_arena``.
    """
    for ps in s.players:
        leader_ci = ps.leader_instance
        if (leader_ci is not None and leader_ci.instance_id == leader_id
                and not leader_ci.deployed and leader_ci in ps.base_zone):
            return _deploy_leader_into_arena(s, ps, leader_ci)
    return s


# ── Select up to N units, give each a token (Medal Ceremony SOR_245) ──

def _select_token_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts = [SelectTokenTarget(tid) for tid in _select_token_targets(state, top.context)]
    # "up to" — stopping early is always legal, EXCEPT for a mandatory clause
    # with a pick still available ("An opponent gives 2 Advantage tokens to a
    # unit they control", Sabine Wren ASH_6).  Still offered when nothing is
    # eligible, so legal_actions can never come back empty.
    if not (top.context.get("mandatory") and acts):
        acts.append(FinishSelectToken())
    return acts


# ── Pay up to N resources, give that many Experience tokens to this unit

#    (Curious Flock LOF_255) ─────────────────────────────────────────────────
def _pay_resources_for_tokens_actions(state: GameState, top: PendingDecision) -> list[Action]:
    acts: list[Action] = []
    if _pay_resources_for_tokens_can_pay(state, top.context):
        acts.append(PayResourceForToken())
    acts.append(FinishPayResources())  # "up to" — paying 0 is legal
    return acts


# ── Plot — play Plot cards from resources on a leader deploy (Garindan

#    SEC_186, Lurking Snub Fighter SEC_189) ────────────────────────────────
def _plot_actions(state: GameState, top: PendingDecision) -> list[Action]:
    deciding_ps = state.player_by_id(top.deciding_player_id)
    allowed = set(top.context.get("plot_ids", []))
    acts = _plot_play_actions(state, deciding_ps, allowed)
    acts.append(FinishPlot())  # "you may" — declining the rest is always legal
    return acts


# ── The DEFENDING player may rescue one of their own cards guarded by a unit;

def _return_one_resource_to_owner(s: GameState, ps: PlayerState) -> None:
    """Return one of ``ps``'s resources to its OWNER's hand (Intimidator LAW_140).

    Resources are fungible and are not targetable cards, so the pick is automatic
    (the K-2SO SOR_145 convention): the EXHAUSTED ones go first, since a returned
    resource is equally a card in hand either way while a ready one left behind is
    still worth a resource this phase.  Ties break on the highest printed cost, the
    card most worth recovering (Citadel Research Center LAW_29).  The owner is not
    always the controller — a resource can change hands (DJ SHD_213)."""
    if not ps.resources:
        return
    res = max(ps.resources,
              key=lambda c: (1 if c.exhausted else 0,
                             getattr(c.card_def, "cost", 0) or 0))
    ps.resources.remove(res)
    res.zone = Zone.HAND
    res.face_down = False
    res.exhausted = False
    s.player_by_id(res.owner_id).hand.append(res)


def _pay_resources_for_tokens_can_pay(state: GameState, ctx: dict) -> bool:
    """Whether another cost item may be spent: below the cap (``None`` = unbounded)
    AND an item of the configured ``cost_source`` remains — a ready resource, a
    Credit token when ``cost_source == "credit"`` (Cad Bane LAW_32), or ANY resource
    (ready or not) when it is ``"return_resource"`` (Intimidator LAW_140, whose
    "return any number of friendly resources" does not ask them to be ready)."""
    cap = ctx.get("max_resources")
    if cap is not None and int(ctx.get("paid", 0)) >= int(cap):
        return False
    ps = state.player_by_id(ctx["controller_id"])
    if ctx.get("cost_source") == "credit":
        return len(ps.credits) > 0
    if ctx.get("cost_source") == "return_resource":
        return len(ps.resources) > 0
    return ps.available_resources > 0


def push_pay_resources_for_tokens(
    s: GameState, source_ci: CardInstance, *,
    max_resources: Optional[int] = 6, token_type: str = "Experience",
    cost_source: str = "resource",
    payoff: str = "token", damage_per: int = 0,
    damage_target_id: Optional[str] = None,
    token_unit_name: Optional[str] = None,
    opponent_token_unit_name: Optional[str] = None,
    token_target_id: Optional[str] = None,
) -> None:
    """Push a 'pay_resources_for_tokens' decision (Curious Flock LOF_255): "Pay up
    to ``max_resources`` resources.  For each resource paid this way, give a
    ``token_type`` token to this unit."

    ``payoff`` selects what each paid resource buys:
      * ``"token"`` (default) — one ``token_type`` token on the source, granted
        inline as each resource is paid (Curious Flock LOF_255).
      * ``"damage"`` — ``damage_per`` damage to ``damage_target_id``, tallied and
        dealt once at resolve (Force Lightning SOR_138 "pay any number of resources
        and deal 2 damage to the chosen unit for each resource paid").  Dealing at
        resolve keeps the "pop then deal" discipline so a resulting defeat lands on a
        clean stack; nothing is granted inline in this mode.  Pushed only when the
        target is still in play.
      * ``"token_units"`` — ``token_unit_name`` TOKEN UNITS for the controller and
        ``opponent_token_unit_name`` (if given) for each opponent, one each per
        resource paid (The Clone Wars TWI_125: "Pay any number of resources.
        Create that many Clone Trooper tokens.  Each opponent creates that many
        Battle Droid tokens").  Like the damage payoff these are tallied via
        ``paid`` and created once at resolve — after the pop — because a token
        entering play fires its own enter-play bus, which must land on a clean
        stack.

    The decider is the source's controller; cost items are fungible, so each payment
    just spends the next item and grants one token to the source inline.  Pushed only
    when the controller has at least one spendable item (spending 0 grants 0 tokens —
    a clean no-op); "up to" includes 0, so FinishPayResources is always offered while
    the decision is up.

    ``cost_source`` selects what is spent per token:
      * ``"resource"`` (default) — exhaust a ready resource (Curious Flock LOF_255).
      * ``"credit"`` — defeat a friendly Credit token (Cad Bane LAW_32 "Defeat any
        number of friendly Credit tokens").
      * ``"return_resource"`` — RETURN a resource to its owner's hand rather than
        spending it in place ("Return any number of friendly resources to their
        owners' hands.  For each resource returned this way, create a Credit token"
        — Intimidator LAW_140, paired with ``payoff="credit"``).  Readiness is not
        required, and the auto-pick prefers the exhausted ones.
    A fourth ``payoff``, ``"credit"``, creates one Credit token per item spent —
    granted inline, since a Credit is a pile entry and fires no enter-play bus.
    ``max_resources`` may be ``None`` for an unbounded "any number" (bounded only by
    the available cost items — Cad Bane)."""
    controller_id = source_ci.owner_id
    ps = s.player_by_id(controller_id)
    if cost_source == "credit":
        if len(ps.credits) <= 0:
            return
    elif cost_source == "return_resource":
        if len(ps.resources) <= 0:
            return
    elif ps.available_resources <= 0:
        return
    if payoff == "damage" and s.find_instance(damage_target_id or "") is None:
        return  # no live target to damage — don't offer the pay decision
    ctx = {
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "max_resources": None if max_resources is None else int(max_resources),
        "token_type": token_type,
        "cost_source": cost_source,
        "paid": 0,
        "payoff": payoff,
        "damage_per": int(damage_per),
        "damage_target_id": damage_target_id,
        "token_unit_name": token_unit_name,
        "opponent_token_unit_name": opponent_token_unit_name,
        "token_target_id": token_target_id,
    }
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="pay_resources_for_tokens",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="pay_resources_for_tokens",
    ))


def _resolve_pay_resources_for_tokens(s: GameState, top) -> GameState:
    """Pop the 'pay_resources_for_tokens' decision and hand the turn over.  Token
    payoffs were granted inline as each resource was paid; a ``payoff == "damage"``
    payoff is dealt here — after the pop — so a resulting defeat lands on a clean
    stack (Force Lightning SOR_138)."""
    ctx = top.context
    s.pending_decisions.pop()
    unit = "credit" if ctx.get("cost_source") == "credit" else "resource"
    if ctx.get("cost_source") == "return_resource":
        unit = "returned resource"
    if ctx.get("payoff") == "damage":
        paid = int(ctx.get("paid", 0))
        amount = paid * int(ctx.get("damage_per", 0))
        tid = ctx.get("damage_target_id")
        if amount > 0 and tid and s.find_instance(tid) is not None:
            from swu.abilities.resolver import _apply_deal_damage
            src = s.find_instance(ctx.get("source_id", ""))
            name = src[1].card_def.display_name if src is not None else None
            _apply_deal_damage(s, tid, amount, source_name=name)
    if ctx.get("payoff") == "token_units":
        # "Create that many <token> tokens.  Each opponent creates that many
        # <other token> tokens" (The Clone Wars TWI_125) — created after the pop so
        # each token's enter-play bus lands on a clean stack.
        paid = int(ctx.get("paid", 0))
        controller_id = ctx["controller_id"]
        if paid > 0:
            if ctx.get("token_unit_name"):
                _create_token_units(s, s.player_by_id(controller_id),
                                    ctx["token_unit_name"], paid)
            if ctx.get("opponent_token_unit_name"):
                for pl in s.players:
                    if pl.player_id != controller_id:
                        _create_token_units(s, pl,
                                            ctx["opponent_token_unit_name"], paid)
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="pay_resources_for_tokens",
        choice=f"spent {ctx.get('paid', 0)} {unit}(s)",
    ))
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s


# ── Select-up-to-N units, give each a token push helper (Medal Ceremony) ──────

def arm_when_played_redo(s: GameState, source_ci: CardInstance) -> None:
    """Arm one "the next time you use a When Played ability this phase, you may use
    that ability again" charge for the source's controller (Qui-Gon Jinn's
    Aethersprite LOF_197, On Attack).

    The charge is a phase-scoped per-player counter on ``game_memory``; the next
    qualifying WhenPlayed ability the controller uses consumes one charge and
    offers an optional re-use of that same ability (see
    ``resolver._schedule_when_played_redo``).  Multiple Aethersprites attacking
    arm multiple charges, each spent by a successive WhenPlayed ability — a faithful
    simplification of the rules' simultaneous delayed effects (vanishingly rare,
    needing two attacks before a When Played card in the same phase)."""
    charges = s.game_memory.when_played_redo_charges
    pid = source_ci.owner_id
    charges[pid] = charges.get(pid, 0) + 1


def _resolve_select_token(s: GameState, top) -> GameState:
    """Pop the 'select_token' decision and hand the turn over."""
    ctx = top.context
    s.pending_decisions.pop()
    s.event_log.append(DecisionResolved(
        deciding_player_id=top.deciding_player_id,
        kind="select_token",
        choice=(f"defeated {len(ctx.get('chosen', []))} upgrade(s)"
                if ctx.get("defeat") else
                f"returned {len(ctx.get('chosen', []))} card(s) to hand"
                if ctx.get("return_to_hand") else
                f"gave {ctx['token_type'] or 'a bonus'} to "
                f"{len(ctx.get('chosen', []))} unit(s)"),
    ))
    # RETURN mode (Force Speed LOF_205: "return any number of non-unique upgrades
    # attached to the defender to their owners' hands") — resolved after the pop for
    # the same reason DEFEAT mode is: the return detaches cards and may fire
    # follow-on effects that would otherwise stack under this decision.
    if ctx.get("return_to_hand"):
        from swu.abilities.resolver import _apply_return_to_hand
        for tid in ctx.get("chosen", []):
            if s.find_instance(tid) is None:
                continue
            _apply_return_to_hand(s, tid)
    # DEFEAT mode (Kit Fisto's Aethersprite LOF_147) resolves HERE, after the pop:
    # defeating an upgrade fires its When Defeated triggers synchronously, which
    # would otherwise stack decisions underneath this one.
    if ctx.get("defeat"):
        from swu.abilities.resolver import _apply_defeat_unit
        defeated_here = 0
        for tid in ctx.get("chosen", []):
            if s.find_instance(tid) is None:
                continue  # already gone (a chained defeat took it)
            _apply_defeat_unit(s, tid)
            defeated_here += 1
        # "For each unit defeated this way, create a Credit token and draw a card"
        # (Tobias Beckett LAW_2) — paid after the defeats, so a unit that was
        # already gone when its turn came round pays nothing.
        if ctx.get("then_credit_and_draw") and defeated_here:
            from swu.engine.tokens import create_credit_token
            beneficiary = s.player_by_id(ctx.get("controller_id")
                                         or top.deciding_player_id)
            for _ in range(defeated_here):
                create_credit_token(s, beneficiary)
            _draw_cards(s, beneficiary, defeated_here)
    # "If they do, the next unit you play this phase gains Shielded for this phase"
    # (Sabine Wren ASH_6) — the "if they do" is literal: the entry is armed only when
    # the decider really gave a token, and it is armed for the SOURCE's controller
    # (the opponent made the choice, but the payoff is the source player's).
    # "Then, an opponent searches TWICE that many cards from the top of their deck
    # for an event, reveals it, and draws it" (Elzar Mann ASH_224) — the drawback
    # rider, scaled by how many tokens were really distributed, so giving none
    # searches nothing.  A FOREIGN deck_search (Sabé SEC_17): the opponent both owns
    # the deck and decides.
    if ctx.get("then_opponent_event_search") and ctx.get("chosen"):
        src_res = s.find_instance(ctx["source_id"])
        controller_id = ctx.get("controller_id") or top.deciding_player_id
        opp = next((p for p in s.players if p.player_id != controller_id), None)
        if src_res is not None and opp is not None:
            from swu.cards.models import Event as _EventDef
            push_deck_search(
                s, src_res[1], count=1, up_to=False,
                window=2 * len(ctx["chosen"]),
                deck_owner_id=opp.player_id, decider_id=opp.player_id,
                eligible=lambda cd: isinstance(cd, _EventDef))
    # "If you give a Shield to an ENEMY unit this way, draw a card" (Secret Marriage
    # TS26_46) — settled after the pop, once it is known which units really took a
    # token.  ONE draw however many enemy units were chosen (the card says "a card"),
    # and none when every pick was friendly, which is the whole tension of the card.
    if ctx.get("then_draw_if_enemy_chosen") and ctx.get("chosen"):
        controller_id = ctx.get("controller_id") or top.deciding_player_id
        hit_enemy = False
        for tid in ctx.get("chosen", []):
            res = s.find_instance(tid)
            if res is not None and res[0].player_id != controller_id:
                hit_enemy = True
                break
        if hit_enemy:
            _draw_cards(s, s.player_by_id(controller_id), 1)
    _pkw = ctx.get("then_pending_keyword")
    if _pkw and ctx.get("chosen"):
        s.game_memory.pending_keyword_grants.append({
            "player_id": ctx.get("source_controller_id") or top.deciding_player_id,
            "trait": str(_pkw.get("trait", "") or ""),
            "keyword": str(_pkw.get("keyword", "Shielded")),
        })
    # "Use any number of 'When Played' abilities on friendly Spectre units" (Fire
    # Across the Galaxy LAW_256).  Also resolved AFTER the pop — each re-use is a
    # fresh ``resolve_effects`` decision (the Chimaera JTL_39 / Shadow Caster
    # JTL_169 shape) and must not stack underneath this one.  Pushed in REVERSE, per
    # unit and per ability, so the first-chosen unit's first-registered ability
    # resolves first on the LIFO stack.
    if ctx.get("then_use_when_played") and ctx.get("chosen"):
        from swu.abilities.resolver import _when_played_ability_indices
        from swu.engine.decisions import PendingDecision
        controller_id = ctx.get("controller_id") or top.deciding_player_id
        owner_idx = s.player_index(controller_id)
        pushed = False
        for tid in reversed(list(ctx.get("chosen", []))):
            res = s.find_instance(tid)
            if res is None:
                continue
            unit = res[1]
            for ability_idx in reversed(_when_played_ability_indices(s, unit)):
                s.pending_decisions.append(PendingDecision(
                    deciding_player_id=controller_id,
                    kind="resolve_effects",
                    context={
                        "set_code": unit.card_def.set_code,
                        "card_number": unit.card_def.card_number,
                        "ability_idx": ability_idx,
                        "source_id": unit.instance_id,
                        "effect_idx": 0,
                        "resolved_targets": {},
                        "event_ctx": {"ability_redo": True},
                        "after_all_player_idx": top.after_resolve_player_index,
                    },
                    after_resolve_player_index=top.after_resolve_player_index,
                ))
                s.event_log.append(DecisionPushed(
                    deciding_player_id=controller_id, kind="resolve_effects"))
                pushed = True
        if pushed:
            s.active_player_index = owner_idx
            return s
    if not s.is_terminal() and not s.pending_decisions:
        s.active_player_index = top.after_resolve_player_index
    return s

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "select_token":                  _select_token_actions,
    "pay_resources_for_tokens":      _pay_resources_for_tokens_actions,
    "plot":                          _plot_actions,
})
