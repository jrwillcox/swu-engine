"""Upgrades that choose their host through a decision rather than at play time.

Attaching an upgrade is ordinarily part of playing a card: the cost is paid, a host is
named, and ``zones._attach_upgrade`` does the rest with no decision on the stack. This
family is the four cases where the host cannot be settled that way, so a decision has
to be pushed and resumed:

* **move an upgrade already in play** to a different host, which is two decisions --
  pick the upgrade, then pick where it goes.
* **pay to steal** an opposing upgrade, where the cost and the host are chosen together.
* **attach an in-play unit as a Pilot**, the one case where the thing being attached is
  itself a unit rather than an upgrade card.
* **play an upgrade from hand onto a chosen host**, used where an effect grants the play
  rather than the player paying for it.

What they have in common is that every one of them has to re-check the upgrade's own
"Attach to …" restriction against a host chosen *later* than the point where playing a
card would normally have checked it. That restriction is read by
``zones._upgrade_target_spec`` and applied by ``zones._eligible_upgrade_targets``, both
of which sit far enough down the layering for all four to reach them.

``_affordable_hand_upgrades`` belongs here for that same reason and no other. It looks
like a cost primitive and was tried in ``costs`` during the kernel pass, but it needs
``_upgrade_target_spec``, which is above ``costs`` -- affordability for an upgrade is
not a question about price alone, since an upgrade with no legal host is unplayable at
any cost.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional

from swu.cards.models import Upgrade
from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    DecisionPushed, DecisionResolved, UnitReadied, UpgradePlayed,
)
from swu.engine.state import CardInstance, GameState, Zone

from swu.engine.actions.base import (
    Action, IllegalActionError,
)
from swu.engine.actions.dispatch import (
    register_decisions,
)
from swu.engine.actions.costs import (
    _exhaust_resources, _pay_play_cost, _play_upgrade_affordable, _play_upgrade_cost, _vehicle_has_pilot,
)
from swu.engine.actions.zones import (
    _attach_upgrade, _eligible_upgrade_targets, _upgrade_target_spec, note_upgrade_attached,
)
from swu.engine.actions.shared import (
    _resource_top_of_deck,
)


# ── New primitive: move-an-upgrade (Survivors' Gauntlet SHD_64) ───────────────

def _upgrade_move_destinations(
    state: GameState, upgrade_ci: CardInstance, host_id: str, host_controller_id: str,
    dest_traits: "tuple[str, ...] | list[str]" = (),
    dest_controller_id: Optional[str] = None,
) -> list[str]:
    """Legal destination unit ids for relocating ``upgrade_ci``: units the upgrade
    may legally attach to (its "Attach to …" restriction), controlled by the same
    player as its current host, excluding the current host itself.

    ``dest_traits`` narrows the destinations to units carrying every named trait
    ("another eligible friendly **Vehicle** unit", U-Wing Lander JTL_70).

    ``dest_controller_id`` REPLACES the same-controller-as-the-current-host rule
    with a fixed controller — which is how "take control of an upgrade on a unit
    and attach it to a different eligible unit" is spelled (Hondo Ohnaka JTL_56):
    control follows the host, so landing the upgrade on one of the ability
    controller's units IS taking control of it, and the source may be an enemy
    unit's upgrade."""
    from swu.engine.traits import has_trait
    want_controller = dest_controller_id or host_controller_id
    out: list[str] = []
    for u in _eligible_upgrade_targets(state, upgrade_ci):
        if u.instance_id == host_id:
            continue
        located = state.find_instance(u.instance_id)
        if located is None:
            continue
        ps, _ = located
        if ps.player_id != want_controller:
            continue
        if any(not has_trait(state, u, t) for t in (dest_traits or ())):
            continue
        out.append(u.instance_id)
    return out


def _movable_upgrades(state: GameState,
                      filters: Optional[dict] = None) -> dict[str, dict]:
    """Map each movable in-play upgrade id → {host_id, controller_id, dests}.

    An upgrade is movable when it is a non-token upgrade attached to a unit that
    has at least one *other* legal host controlled by the same player.

    ``filters`` (carried in the decision's context so every re-derivation agrees)
    narrows the board-wide default for a card that only moves its OWN load
    (U-Wing Lander JTL_70, "an upgrade on **this** unit … to another eligible
    friendly **Vehicle** unit"):
      * ``from_host_id`` — only upgrades attached to that one host;
      * ``dest_traits``  — destinations must carry these traits;
      * ``include_tokens`` — admit Shield/Experience TOKEN upgrades, which the
        engine-wide ``kind="upgrade"`` convention otherwise excludes (JTL_70
        loads itself with 3 Experience tokens precisely to ferry them onward);
      * ``dest_controller_id`` — every destination must be controlled by this
        player rather than by the upgrade's current host's controller, i.e. the
        relocation TAKES CONTROL of the upgrade (Hondo Ohnaka JTL_56);
      * ``exclude_upgrade_traits`` — skip upgrades carrying any of these traits
        ("a **non-Pilot** upgrade", JTL_56).
      * ``tokens_only`` — admit ONLY Shield/Experience token upgrades ("a **token**
        upgrade on a unit", Shuttle ST-149 JTL_242).  Implies ``include_tokens``;
        the complement of the engine-wide non-token default.
      * ``only_upgrade_id`` — only this one upgrade may move ("The attacking player
        takes control of **this upgrade**", Death Star Plans JTL_260), which
        ``from_host_id`` cannot express when the host carries several upgrades.
      * ``host_controller_id`` — the upgrade's CURRENT host must be controlled by
        this player ("a friendly upgrade on a friendly unit", Jocasta Nu LOF_248).
        The board-wide default admits enemy hosts too; destinations are already
        pinned to the host's own controller, so this makes both ends friendly.
    """
    from swu.cards.models import TokenUpgrade
    f = filters or {}
    from_host_id = f.get("from_host_id")
    host_controller_id = f.get("host_controller_id")
    dest_traits = tuple(f.get("dest_traits") or ())
    tokens_only = bool(f.get("tokens_only"))
    include_tokens = bool(f.get("include_tokens")) or tokens_only
    dest_controller_id = f.get("dest_controller_id")
    exclude_upgrade_traits = tuple(f.get("exclude_upgrade_traits") or ())
    only_upgrade_id = f.get("only_upgrade_id")
    out: dict[str, dict] = {}
    for ps in state.players:
        if host_controller_id is not None and ps.player_id != host_controller_id:
            continue
        for host in ps.ground_arena + ps.space_arena:
            if from_host_id is not None and host.instance_id != from_host_id:
                continue
            for upg in host.attached_upgrades:
                if only_upgrade_id is not None and upg.instance_id != only_upgrade_id:
                    continue
                is_token = isinstance(upg.card_def, TokenUpgrade)
                if is_token and not include_tokens:
                    continue
                if tokens_only and not is_token:
                    continue
                if any(t in (getattr(upg.card_def, "traits", None) or ())
                       for t in exclude_upgrade_traits):
                    continue
                dests = _upgrade_move_destinations(
                    state, upg, host.instance_id, ps.player_id, dest_traits,
                    dest_controller_id)
                if dests:
                    out[upg.instance_id] = {
                        "host_id": host.instance_id,
                        "controller_id": ps.player_id,
                        "dests": dests,
                    }
    return out


@dataclass
class MoveUpgradeSelect(Action):
    """Choose an in-play upgrade to relocate (Survivors' Gauntlet SHD_64).
    Advances the 'move_upgrade' decision to its destination stage."""
    upgrade_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "move_upgrade"):
            raise IllegalActionError("No move-upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "pick_upgrade":
            raise IllegalActionError("Move-upgrade decision is past the pick stage")
        movable = _movable_upgrades(s, ctx.get("filters"))
        if self.upgrade_id not in movable:
            raise IllegalActionError(f"{self.upgrade_id} is not a movable upgrade")
        ctx["stage"] = "pick_dest"
        ctx["chosen_upgrade"] = self.upgrade_id
        return s

    def describe(self) -> str:
        return f"Move upgrade {self.upgrade_id}"


@dataclass
class DeclineMoveUpgrade(Action):
    """Decline to move an upgrade — the ability does nothing (Survivors' Gauntlet
    SHD_64 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "move_upgrade"):
            raise IllegalActionError("No move-upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        if top.context.get("stage") != "pick_upgrade":
            raise IllegalActionError("Move-upgrade decision is past the pick stage")
        if top.context.get("mandatory"):
            raise IllegalActionError("This move-upgrade decision cannot be declined")
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="move_upgrade",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to move an upgrade"


@dataclass
class MoveUpgradeTo(Action):
    """Choose the destination unit and relocate the chosen upgrade, resolving the
    'move_upgrade' decision (Survivors' Gauntlet SHD_64)."""
    dest_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "move_upgrade"):
            raise IllegalActionError("No move-upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        if ctx.get("stage") != "pick_dest":
            raise IllegalActionError("Move-upgrade decision is not at the destination stage")
        upgrade_id = ctx["chosen_upgrade"]
        movable = _movable_upgrades(s, ctx.get("filters"))
        info = movable.get(upgrade_id)
        if info is None or self.dest_id not in info["dests"]:
            raise IllegalActionError(f"{self.dest_id} is not a legal destination")
        _relocate_upgrade(s, upgrade_id, info["host_id"], self.dest_id)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="move_upgrade",
            choice=f"moved {upgrade_id} to {self.dest_id}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Attach the upgrade to {self.dest_id}"


def _relocate_upgrade(s: GameState, upgrade_id: str, host_id: str, dest_id: str) -> None:
    """Detach ``upgrade_id`` from ``host_id`` and attach it to ``dest_id``.

    A pure relocation: no WhenPlayed re-fire (the upgrade was already played).
    The upgrade's zone tag is updated to the destination's arena so upgrade-zone
    invariants hold."""
    host = s.find_instance(host_id)
    dest = s.find_instance(dest_id)
    if host is None or dest is None:
        raise IllegalActionError("Move-upgrade host or destination not found")
    _, host_ci = host
    _, dest_ci = dest
    upg = next((u for u in host_ci.attached_upgrades
                if u.instance_id == upgrade_id), None)
    if upg is None:
        raise IllegalActionError(f"{upgrade_id} no longer attached to {host_id}")
    host_ci.attached_upgrades.remove(upg)
    upg.zone = dest_ci.zone
    upg.face_down = False
    dest_ci.attached_upgrades.append(upg)
    note_upgrade_attached(s, dest_ci)      # Sabine Wren ASH_208


def push_move_upgrade(s: GameState, source_ci: CardInstance, *,
                      from_host_id: Optional[str] = None,
                      dest_traits: Optional[list[str]] = None,
                      include_tokens: bool = False,
                      dest_controller_id: Optional[str] = None,
                      exclude_upgrade_traits: Optional[list[str]] = None,
                      tokens_only: bool = False,
                      only_upgrade_id: Optional[str] = None,
                      host_controller_id: Optional[str] = None,
                      decider_id: Optional[str] = None,
                      mandatory: bool = False) -> None:
    """Push a 'move_upgrade' decision: "You may attach an upgrade on a unit to
    another eligible unit controlled by the same player" (Survivors' Gauntlet
    SHD_64).

    Only pushed when at least one in-play upgrade can actually be relocated to a
    different same-controller legal host — so the optional ability is never
    offered when it could do nothing.

    The optional narrowings (``from_host_id`` / ``dest_traits`` /
    ``include_tokens`` / ``dest_controller_id`` / ``exclude_upgrade_traits``, all
    documented on ``_movable_upgrades``) are stored in the decision context so the
    action enumeration and both apply-guards re-derive exactly the same candidate
    set (U-Wing Lander JTL_70, Hondo Ohnaka JTL_56).

    ``decider_id`` hands the choice to a player other than the source's controller
    ("The ATTACKING PLAYER takes control of this upgrade …", Death Star Plans
    JTL_260); ``mandatory`` drops the decline, for a relocation that is not a
    "you may"."""
    filters = {
        "from_host_id": from_host_id,
        "dest_traits": list(dest_traits or []),
        "include_tokens": bool(include_tokens),
        "dest_controller_id": dest_controller_id,
        "exclude_upgrade_traits": list(exclude_upgrade_traits or []),
        "tokens_only": bool(tokens_only),
        "only_upgrade_id": only_upgrade_id,
        "host_controller_id": host_controller_id,
    }
    if not _movable_upgrades(s, filters):
        return
    controller_id = decider_id or source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="move_upgrade",
        context={
            "source_id": source_ci.instance_id,
            "controller_id": controller_id,
            "stage": "pick_upgrade",
            "chosen_upgrade": None,
            "mandatory": bool(mandatory),
            "filters": filters,
        },
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="move_upgrade",
    ))


def _move_upgrade_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top move_upgrade decision (never empty)."""
    ctx = top.context
    if ctx.get("stage") == "pick_upgrade":
        acts: list[Action] = [
            MoveUpgradeSelect(uid)
            for uid in sorted(_movable_upgrades(state, ctx.get("filters")))
        ]
        if not ctx.get("mandatory"):
            acts.append(DeclineMoveUpgrade())  # the "you may" (SHD_64)
        return acts
    # stage "pick_dest"
    upgrade_id = ctx["chosen_upgrade"]
    info = _movable_upgrades(state, ctx.get("filters")).get(upgrade_id)
    dests = info["dests"] if info else []
    return [MoveUpgradeTo(d) for d in dests]


# ── New primitive: pay-and-steal-an-upgrade (Pre Vizsla SHD_142) ──────────────

def _stealable_upgrades(state: GameState, source_ci: CardInstance) -> dict[str, dict]:
    """Map each steal-eligible upgrade id → {host_id, cost}.

    An upgrade is steal-eligible for Pre Vizsla when it is a real (non-token)
    Upgrade attached to a NON-Vehicle unit OTHER than the source, and the source's
    controller can pay its printed cost from ready resources."""
    from swu.cards.models import Upgrade, TokenUpgrade
    from swu.engine.traits import has_trait
    located = state.find_instance(source_ci.instance_id)
    if located is None:
        return {}
    controller_ps, _ = located
    out: dict[str, dict] = {}
    for ps in state.players:
        for host in ps.ground_arena + ps.space_arena:
            if host.instance_id == source_ci.instance_id:
                continue  # "another" unit
            if has_trait(state, host, "Vehicle"):
                continue  # "non-Vehicle unit"
            for upg in host.attached_upgrades:
                if not isinstance(upg.card_def, Upgrade) or isinstance(
                        upg.card_def, TokenUpgrade):
                    continue
                cost = int(getattr(upg.card_def, "cost", 0) or 0)
                if controller_ps.available_resources < cost:
                    continue
                out[upg.instance_id] = {"host_id": host.instance_id, "cost": cost}
    return out


@dataclass
class StealUpgrade(Action):
    """Pay an upgrade's cost and take control of it, attaching it to the source
    (Pre Vizsla SHD_142) — or defeating it if it can't attach."""
    upgrade_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_and_steal_upgrade"):
            raise IllegalActionError("No pay_and_steal_upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        source_id = top.context["source_id"]
        located = s.find_instance(source_id)
        stealable = _stealable_upgrades(s, located[1]) if located is not None else {}
        info = stealable.get(self.upgrade_id)
        if info is None:
            raise IllegalActionError(f"{self.upgrade_id} is not a stealable upgrade")
        source_ci = located[1]
        controller_ps, _ = located
        # Pay the printed cost (ready resources — the Pre Vizsla payment is
        # resource-only, matching the credit-spend SCOPE exclusions).
        _exhaust_resources(controller_ps, info["cost"])
        upg = next((u for u in s.find_instance(info["host_id"])[1].attached_upgrades
                    if u.instance_id == self.upgrade_id), None)
        spec = _upgrade_target_spec(upg.card_def) if upg is not None else None
        can_attach = False
        if upg is not None:
            if spec is None:
                can_attach = True
            else:
                from swu.abilities.resolver import _spec_matches_ci
                can_attach = _spec_matches_ci(spec, source_ci, upg, s, {})
        if can_attach:
            _relocate_upgrade(s, self.upgrade_id, info["host_id"], source_id)
            choice = f"took control of {self.upgrade_id}"
        else:
            from swu.abilities.resolver import _apply_defeat_unit
            _apply_defeat_unit(s, self.upgrade_id)
            choice = f"defeated {self.upgrade_id} (can't attach)"
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pay_and_steal_upgrade",
            choice=choice,
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Pay for and take control of upgrade {self.upgrade_id}"


@dataclass
class DeclineStealUpgrade(Action):
    """Decline the optional pay-and-steal-an-upgrade (Pre Vizsla SHD_142 "you may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pay_and_steal_upgrade"):
            raise IllegalActionError("No pay_and_steal_upgrade decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pay_and_steal_upgrade",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to steal an upgrade"


def push_pay_and_steal_upgrade(s: GameState, source_ci: CardInstance) -> None:
    """Push a 'pay_and_steal_upgrade' decision (Pre Vizsla SHD_142).

    Only pushed when at least one affordable steal-eligible upgrade exists, so the
    optional ability is never offered when it could do nothing."""
    if not _stealable_upgrades(s, source_ci):
        return
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    s.pending_decisions.append(PendingDecision(
        deciding_player_id=controller_id,
        kind="pay_and_steal_upgrade",
        context={"source_id": source_ci.instance_id},
        after_resolve_player_index=1 - owner_idx,
    ))
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="pay_and_steal_upgrade",
    ))


def _pay_and_steal_upgrade_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top pay_and_steal_upgrade decision (never empty)."""
    located = state.find_instance(top.context["source_id"])
    stealable = _stealable_upgrades(state, located[1]) if located is not None else {}
    acts: list[Action] = [StealUpgrade(uid) for uid in sorted(stealable)]
    acts.append(DeclineStealUpgrade())
    return acts


# ── Attach an in-play unit as a Pilot upgrade (Poe Dameron JTLP_6) ────────────

def _pilot_self_attach_hosts(s: GameState, source_ci: CardInstance,
                             hosts: str = "friendly") -> list[str]:
    """Instance ids of the Vehicle units that ``source_ci`` may attach itself onto
    as a Pilot: Vehicles with no Pilot on them (Poe JTLP_6 "a friendly Vehicle unit
    without a Pilot on it"), excluding the source itself.

    ``hosts="enemy"`` looks at the OPPONENT's arenas instead — "attach this unit as
    an upgrade to an ENEMY Vehicle unit without a Pilot on it" (Sidon Ithano
    JTL_213), where the pilot ends up buffing a ship it does not control."""
    from swu.engine.traits import has_trait
    idx = s.player_index(source_ci.owner_id)
    ps = s.players[1 - idx] if hosts == "enemy" else s.players[idx]
    return [ci.instance_id for ci in ps.ground_arena + ps.space_arena
            if ci.instance_id != source_ci.instance_id
            and has_trait(s, ci, "Vehicle")
            and not _vehicle_has_pilot(ci)]


def _attach_unit_as_pilot(s: GameState, unit_id: str, vehicle_id: str) -> None:
    """Relocate the in-play unit ``unit_id`` into ``vehicle_id``'s attached
    upgrades as a Pilot.  A pure relocation (no WhenPlayed re-fire) mirroring
    `_relocate_upgrade`; the unit's `upgrade_power`/`upgrade_hp` then buff the
    host via the existing compute_power/hp reads, and on the host's defeat
    `_defeat_unit` detaches the unit (a non-token Unit) to its owner's discard
    like any pilot."""
    from swu.cards.models import TokenUpgrade
    ures = s.find_instance(unit_id)
    vres = s.find_instance(vehicle_id)
    if ures is None or vres is None:
        return
    unit_ps, unit_ci = ures
    _, vehicle_ci = vres
    # Remove the unit from whichever arena holds it (no-op if it already left).
    removed = False
    for arena in (unit_ps.ground_arena, unit_ps.space_arena):
        if unit_ci in arena:
            arena.remove(unit_ci)
            removed = True
            break
    if not removed:
        return
    # A unit becoming an upgrade sheds its own attachments (tokens vanish, real
    # upgrades → owner's discard), mirroring _apply_capture / _defeat_unit.  A
    # freshly-played Poe has none, but this keeps the relocation clean in general.
    for upgrade in list(unit_ci.attached_upgrades):
        if isinstance(upgrade.card_def, TokenUpgrade):
            continue
        upgrade_owner = s.player_by_id(upgrade.owner_id)
        upgrade.zone = Zone.DISCARD
        upgrade_owner.discard.append(upgrade)
    unit_ci.attached_upgrades.clear()
    # Modifiers that targeted it as a unit no longer apply.
    s.modifiers = [m for m in s.modifiers if m.target_instance_id != unit_ci.instance_id]
    unit_ci.damage = 0
    unit_ci.exhausted = False
    unit_ci.face_down = False
    unit_ci.deployed = False
    unit_ci.zone = vehicle_ci.zone
    vehicle_ci.attached_upgrades.append(unit_ci)
    note_upgrade_attached(s, vehicle_ci)      # Sabine Wren ASH_208
    s.event_log.append(UpgradePlayed(
        player_id=unit_ci.owner_id,
        instance_id=unit_ci.instance_id,
        card_name=unit_ci.card_def.display_name,
        attached_to_instance_id=vehicle_id,
    ))


def push_attach_unit_as_pilot(s: GameState, source_ci: CardInstance, *,
                              hosts: str = "friendly") -> None:
    """Push a 'pilot_self_attach' decision: "You may attach this unit as an
    upgrade to a friendly Vehicle unit without a Pilot on it" (Poe JTLP_6).

    ``hosts="enemy"`` offers the OPPONENT's pilotless Vehicles instead (Sidon
    Ithano JTL_213); the choice is carried in the decision context so the
    enumeration and the apply-guard re-derive the same host set.

    Only pushed when at least one eligible Vehicle host exists — so the optional
    ability auto-skips (does nothing) when it could not attach anywhere."""
    if not _pilot_self_attach_hosts(s, source_ci, hosts):
        return
    controller_id = source_ci.owner_id
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="pilot_self_attach",
        context={"source_id": source_ci.instance_id, "controller_id": controller_id,
                 "hosts": hosts},
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="pilot_self_attach",
    ))


@dataclass
class AttachSelfAsPilot(Action):
    """Attach the source unit to a chosen friendly Vehicle as a Pilot, resolving
    the 'pilot_self_attach' decision (Poe JTLP_6)."""
    vehicle_id: str

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pilot_self_attach"):
            raise IllegalActionError("No pilot-self-attach decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        source_id = top.context["source_id"]
        source = s.find_instance(source_id)
        if source is None or self.vehicle_id not in _pilot_self_attach_hosts(
                s, source[1], top.context.get("hosts", "friendly")):
            raise IllegalActionError(f"{self.vehicle_id} is not a legal pilot host")
        _attach_unit_as_pilot(s, source_id, self.vehicle_id)
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pilot_self_attach",
            choice=f"attached {source_id} to {self.vehicle_id}",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Attach as a Pilot onto {self.vehicle_id}"


@dataclass
class DeclineAttachSelfAsPilot(Action):
    """Decline to attach the unit as a Pilot — it stays a unit (Poe JTLP_6 "you
    may")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "pilot_self_attach"):
            raise IllegalActionError("No pilot-self-attach decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="pilot_self_attach",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to attach as a Pilot"


def _pilot_self_attach_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top pilot_self_attach decision (never empty — a
    decline is always offered)."""
    source = state.find_instance(top.context["source_id"])
    hosts = (_pilot_self_attach_hosts(state, source[1],
                                      top.context.get("hosts", "friendly"))
             if source else [])
    acts: list[Action] = [AttachSelfAsPilot(v) for v in sorted(hosts)]
    acts.append(DeclineAttachSelfAsPilot())
    return acts


# ── Play an upgrade from hand for free, choosing a host (Jabba the Hutt ASH_42) ─

def _play_upgrade_source_zones(state: GameState, ctx: dict) -> list[list[CardInstance]]:
    """The zones a ``play_upgrade_from_hand`` decision may play an upgrade out of:
    the controller's hand, plus — with ``ctx['include_discards']`` — EVERY player's
    discard pile ("play an upgrade from your hand or from any player's discard
    pile", A Fine Addition TWI_40).  An upgrade played out of an opponent's discard
    keeps its owner (it returns there when defeated); control follows the host, the
    ``change_control`` convention.

    ``from_discard_only`` narrows the source to the controller's OWN discard pile,
    with the hand dropped entirely — "Play any number of upgrades from your discard
    pile on this unit" (Kylo Ren LOF_1).

    ``from_resources`` narrows it to the controller's own RESOURCE row — "Play an
    upgrade from your resources … (paying its cost)" (The Armorer ASH_1).  The card
    leaves the row when it is played (it is not replaced from the deck, unlike
    Smuggle), which is why the Armorer's own "If you do, resource the top card of
    your deck" rider exists."""
    ps = state.player_by_id(ctx["controller_id"])
    if ctx.get("from_resources"):
        return [ps.resources]
    if ctx.get("from_discard_only"):
        return [ps.discard]
    zones = [ps.hand]
    if ctx.get("include_discards"):
        zones += [p.discard for p in state.players]
    return zones


def _find_playable_upgrade(state: GameState, ctx: dict,
                           upgrade_id: str) -> Optional[CardInstance]:
    """Locate ``upgrade_id`` in any of the decision's legal source zones."""
    for zone in _play_upgrade_source_zones(state, ctx):
        for c in zone:
            if c.instance_id == upgrade_id:
                return c
    return None


def _play_upgrade_hosts_for(state: GameState, ctx: dict,
                            upgrade_ci: CardInstance) -> list[str]:
    """Legal host instance ids for ``upgrade_ci``, per its own "Attach to …"
    restriction, narrowed by ``ctx['host_id']`` when the card pins the host ("…on
    this unit" — Kylo Ren LOF_1).

    ``ctx['host_controller']`` / ``ctx['host_predicates']`` narrow the hosts by the
    ordinary TargetSpec matcher, evaluated with the UPGRADE as the source (so
    "friendly" reads from its owner — the player making the play): "on a unit that
    entered play this phase" / "on a friendly unit" (The Armorer ASH_1)."""
    hosts = [u.instance_id for u in _eligible_upgrade_targets(state, upgrade_ci)]
    pinned = ctx.get("host_id")
    if pinned is not None:
        hosts = [h for h in hosts if h == pinned]
    preds = tuple(ctx.get("host_predicates") or ())
    host_controller = ctx.get("host_controller")
    if preds or host_controller:
        from swu.abilities.registry import TargetSpec
        from swu.abilities.resolver import _spec_matches_ci
        spec = TargetSpec(controller=host_controller or "any", kind="unit",
                          predicates=preds)
        keep = []
        for hid in hosts:
            res = state.find_instance(hid)
            if res is None:
                continue
            if _spec_matches_ci(spec, res[1], upgrade_ci, state, {}):
                keep.append(hid)
        hosts = keep
    return hosts


def _play_upgrade_from_hand_hosts(state: GameState, ctx: dict) -> list[str]:
    """Legal host instance ids for the pending upgrade ``ctx['upgrade_id']`` — the
    units it may be attached to, per its own "Attach to …" restriction.  Empty
    if the upgrade has left its source zone (defensive)."""
    upgrade_ci = _find_playable_upgrade(state, ctx, ctx["upgrade_id"])
    if upgrade_ci is None:
        return []
    return _play_upgrade_hosts_for(state, ctx, upgrade_ci)


def _affordable_hand_upgrades(state: GameState, ctx: dict) -> list[str]:
    """Instance ids of Upgrade cards in the decision's source zones (the
    controller's hand, plus every discard pile when ``include_discards``) that are
    BOTH affordable (given ``ctx['free']`` / ``cost_reduction`` /
    ``ignore_aspect_penalty``) AND have ≥1 legal host — the candidate set for a
    "choose an upgrade to play" decision (Fenn Rau SHD_67, A Fine Addition TWI_40).
    Empty ⇒ the play can do nothing."""
    free = bool(ctx.get("free", True))
    out: list[str] = []
    trait = ctx.get("trait")
    for zone in _play_upgrade_source_zones(state, ctx):
        for c in zone:
            if not isinstance(c.card_def, Upgrade):
                continue
            # "…a Lightsaber upgrade from your hand" (Cin Drallig LOF_150) — the
            # printed-trait narrowing of the candidate set.
            if trait is not None and trait not in (
                    getattr(c.card_def, "traits", None) or ()):
                continue
            # An upgrade taken from an OPPONENT's discard keeps its owner, and the
            # "Attach to a friendly/enemy unit" restriction is evaluated from the
            # owner's perspective — which would invert for the player now playing
            # it.  Rather than mis-attach, such a card is simply not offered from a
            # foreign discard (a documented narrowing; controller-agnostic
            # restrictions — the overwhelming majority — are unaffected).
            if c.owner_id != ctx["controller_id"]:
                spec = _upgrade_target_spec(c.card_def)
                if spec is not None and getattr(spec, "controller", "any") != "any":
                    continue
            if not _play_upgrade_hosts_for(state, ctx, c):
                continue
            if not free and not _play_upgrade_affordable(
                    state, ctx, c, _play_upgrade_cost(state, ctx, c)):
                continue
            out.append(c.instance_id)
    return out


def push_play_upgrade_from_hand(
    s: GameState, source_ci: CardInstance, *, upgrade_id: Optional[str] = None,
    free: bool = True, cost_reduction: int = 0,
    include_discards: bool = False, ignore_aspect_penalty: bool = False,
    from_discard_only: bool = False, host_id: Optional[str] = None,
    repeat: bool = False, trait: Optional[str] = None,
    then_ready_source: bool = False, then_damage_host: int = 0,
    then_defeat_at_regroup: bool = False,
    from_resources: bool = False,
    host_controller: Optional[str] = None,
    host_predicates: Optional[tuple] = None,
    then_resource_top_of_deck: bool = False,
) -> None:
    """Push a 'play_upgrade_from_hand' decision: "You may play [the upgrade
    ``upgrade_id`` / an upgrade of your choice] from your hand [for free / at
    ``cost_reduction`` off], choosing a legal host".

    Two callers: Jabba the Hutt ASH_42 passes a specific ``upgrade_id`` (the
    just-returned upgrade, played for free); Fenn Rau SHD_67 passes
    ``upgrade_id=None`` (the controller CHOOSES an affordable hand upgrade) with
    ``free=False, cost_reduction=2``.

    ``include_discards`` widens the source zones to every player's discard pile and
    ``ignore_aspect_penalty`` waives the played upgrade's whole aspect penalty — "If
    an enemy unit was defeated this phase, play an upgrade from your hand or from any
    player's discard pile, ignoring its aspect penalty" (A Fine Addition TWI_40,
    which pays the cost in full otherwise: ``free=False, cost_reduction=0``).

    Three further knobs serve "Play any number of upgrades from your discard pile on
    this unit (one at a time, paying their costs)" (Kylo Ren LOF_1):
    ``from_discard_only`` drops the hand and reads only the controller's OWN discard;
    ``host_id`` pins every candidate's host to one unit ("on this unit"); and
    ``repeat`` makes each successful play RE-PUSH the loop — re-pushed BEFORE the
    upgrade attaches, so the just-played upgrade's own When Played triggers (pushed
    on top) resolve before the next pick, the faithful "one at a time" LIFO (the
    Endless Legions SHD_109 shape).  The always-offered decline is the "any number",
    including zero.

    Two more serve "When Played: You may play a Lightsaber upgrade from your hand for
    free on this unit.  If you do, ready him" (Cin Drallig LOF_150): ``trait`` narrows
    the candidate upgrades to a printed trait, and ``then_ready_source`` readies the
    SOURCE unit after a successful play ("if you do" — never on a decline).

    ``then_damage_host`` is the same-family "if you do" hook on the other side of the
    attachment: N damage dealt to the HOST the upgrade landed on ("Play an upgrade
    from your hand on a friendly non-Vehicle unit.  It costs 1 resource less.  If you
    do, deal 1 damage to that unit" — Lama Su SEC_3).  Like then_ready_source it runs
    only on a real play, never on the decline.

    ``then_defeat_at_regroup`` stamps the played upgrade with the long-standing
    per-instance ``defeat_at_regroup`` flag, swept in ``_enter_regroup`` — "Play an
    Item upgrade from your discard pile.  It costs 3 resources less.  At the start of
    the next regroup phase, defeat it" (Salvaged Materials LAW_245).  The flag is the
    same delayed-defeat family as the unit version, so a rental upgrade needs no new
    bookkeeping.

    Four knobs serve "Play an upgrade from your resources on a unit that entered play
    this phase (paying its cost).  If you do, resource the top card of your deck"
    (The Armorer ASH_1): ``from_resources`` swaps the source zone for the
    controller's RESOURCE row (the card leaves the row and is NOT replaced — unlike
    Smuggle — and cannot pay for itself, the ``_play_upgrade_affordable`` rule);
    ``host_controller`` / ``host_predicates`` narrow the legal hosts through the
    ordinary TargetSpec matcher; and ``then_resource_top_of_deck`` is the "if you do"
    ramp, run only on a real play (never on the decline).

    Only pushed when there is at least one affordable candidate upgrade with ≥1 legal
    host — so the optional play is never offered when it could do nothing.  The
    decider is the source's controller."""
    controller_id = source_ci.owner_id
    ctx = {
        "trait": trait,
        "from_resources": bool(from_resources),
        "host_controller": host_controller,
        "host_predicates": list(host_predicates or ()),
        "then_resource_top_of_deck": bool(then_resource_top_of_deck),
        "then_ready_source": bool(then_ready_source),
        "then_damage_host": int(then_damage_host),
        "then_defeat_at_regroup": bool(then_defeat_at_regroup),
        "source_id": source_ci.instance_id,
        "controller_id": controller_id,
        "upgrade_id": upgrade_id,
        "free": bool(free),
        "cost_reduction": int(cost_reduction),
        "include_discards": bool(include_discards),
        "ignore_aspect_penalty": bool(ignore_aspect_penalty),
        "from_discard_only": bool(from_discard_only),
        "host_id": host_id,
        "repeat": bool(repeat),
    }
    if upgrade_id is None:
        if not _affordable_hand_upgrades(s, ctx):
            return
    else:
        if not _play_upgrade_from_hand_hosts(s, ctx):
            return
        # A specific-upgrade paid play must also be affordable.
        if not bool(free):
            upg = _find_playable_upgrade(s, ctx, upgrade_id)
            if upg is None:
                return
            if not _play_upgrade_affordable(s, ctx, upg,
                                            _play_upgrade_cost(s, ctx, upg)):
                return
    owner_idx = s.player_index(controller_id)
    dec = PendingDecision(
        deciding_player_id=controller_id,
        kind="play_upgrade_from_hand",
        context=ctx,
        after_resolve_player_index=1 - owner_idx,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = owner_idx
    s.event_log.append(DecisionPushed(
        deciding_player_id=controller_id,
        kind="play_upgrade_from_hand",
    ))


@dataclass
class PlayUpgradeFromHand(Action):
    """Play a pending hand upgrade onto a chosen host, resolving the
    'play_upgrade_from_hand' decision.  ``upgrade_id`` is carried on the action
    only in "choose an upgrade" mode (Fenn Rau SHD_67); it is ``None`` for the
    fixed-upgrade caller (Jabba the Hutt ASH_42), which reads the id from the
    decision context."""
    host_id: str
    upgrade_id: Optional[str] = None

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_upgrade_from_hand"):
            raise IllegalActionError("No play-upgrade-from-hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions[-1]
        ctx = top.context
        upg_id = self.upgrade_id or ctx.get("upgrade_id")
        if upg_id is None:
            raise IllegalActionError("No upgrade chosen")
        ps = s.player_by_id(ctx["controller_id"])
        upgrade_ci = _find_playable_upgrade(s, ctx, upg_id)
        if upgrade_ci is None:
            raise IllegalActionError("Upgrade no longer available to play")
        if self.host_id not in _play_upgrade_hosts_for(s, ctx, upgrade_ci):
            raise IllegalActionError(f"{self.host_id} is not a legal host")
        free = bool(ctx.get("free", True))
        cost = 0 if free else _play_upgrade_cost(s, ctx, upgrade_ci, self.host_id)
        if not free and not _play_upgrade_affordable(s, ctx, upgrade_ci, cost):
            raise IllegalActionError("Cannot afford the upgrade")
        # The upgrade may live in the controller's hand or (include_discards) in
        # ANY player's discard pile — remove it from whichever zone holds it.
        for zone in _play_upgrade_source_zones(s, ctx):
            if upgrade_ci in zone:
                zone.remove(upgrade_ci)
                break
        if cost:
            _pay_play_cost(s, ps, cost)
        # Pop the decision BEFORE attaching, so the upgrade's own WhenPlayed
        # triggers land on a clean stack (the "pop, then act" gotcha).
        s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_upgrade_from_hand",
            choice=f"played {upg_id} onto {self.host_id}",
        ))
        # "Any number … one at a time" (Kylo Ren LOF_1): re-push the loop BEFORE the
        # attach, so this upgrade's own When Played triggers land on top of it and
        # resolve first (the Endless Legions SHD_109 ordering).
        if ctx.get("repeat"):
            source_result = s.find_instance(ctx["source_id"])
            if source_result is not None:
                push_play_upgrade_from_hand(
                    s, source_result[1],
                    free=bool(ctx.get("free", True)),
                    cost_reduction=int(ctx.get("cost_reduction", 0) or 0),
                    include_discards=bool(ctx.get("include_discards")),
                    ignore_aspect_penalty=bool(ctx.get("ignore_aspect_penalty")),
                    from_discard_only=bool(ctx.get("from_discard_only")),
                    host_id=ctx.get("host_id"),
                    repeat=True,
                    trait=ctx.get("trait"),
                    then_ready_source=bool(ctx.get("then_ready_source")),
                    then_damage_host=int(ctx.get("then_damage_host", 0) or 0),
                    then_defeat_at_regroup=bool(ctx.get("then_defeat_at_regroup")),
                    from_resources=bool(ctx.get("from_resources")),
                    host_controller=ctx.get("host_controller"),
                    host_predicates=tuple(ctx.get("host_predicates") or ()),
                    then_resource_top_of_deck=bool(
                        ctx.get("then_resource_top_of_deck")),
                )
        # "At the start of the next regroup phase, defeat it" (Salvaged Materials
        # LAW_245) — stamped BEFORE the attach so the flag is already on the card
        # when its own When Played resolves.
        if ctx.get("then_defeat_at_regroup"):
            upgrade_ci.defeat_at_regroup = True
        # A card played out of the RESOURCE row (The Armorer ASH_1) may be exhausted
        # there; it is not an exhaustible card once attached, and leaving the flag on
        # would put an exhausted card in a hand if it is ever returned.
        if ctx.get("from_resources"):
            upgrade_ci.exhausted = False
        # _attach_upgrade fires UpgradePlayed + WhenPlayed
        _attach_upgrade(s, ps, upgrade_ci, self.host_id)
        # "If you do, resource the top card of your deck" (The Armorer ASH_1) — the
        # ramp that repays the resource row the play just spent, on a real play only.
        if ctx.get("then_resource_top_of_deck"):
            _resource_top_of_deck(s, ps)
        # "If you do, ready him" (Cin Drallig LOF_150) — only on a play, never on the
        # decline, and after the upgrade has landed.
        # "If you do, deal N damage to that unit" (Lama Su SEC_3) — the host-side
        # "if you do" hook, after the upgrade has landed (so the host's HP already
        # includes it, matching the printed ordering) and only on a real play.
        _thd = int(ctx.get("then_damage_host", 0) or 0)
        if _thd > 0:
            from swu.abilities.resolver import _apply_deal_damage
            src_res = s.find_instance(ctx["source_id"])
            _name = (src_res[1].card_def.display_name
                     if src_res is not None else upgrade_ci.card_def.display_name)
            _apply_deal_damage(s, self.host_id, _thd, _name)
        if ctx.get("then_ready_source"):
            src_res = s.find_instance(ctx["source_id"])
            if src_res is not None and src_res[1].exhausted:
                src_res[1].exhausted = False
                s.event_log.append(UnitReadied(
                    player_id=ps.player_id,
                    instance_id=src_res[1].instance_id,
                    card_name=src_res[1].card_def.display_name,
                ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return f"Play the upgrade onto {self.host_id}"


@dataclass
class DeclinePlayUpgradeFromHand(Action):
    """Decline to play the returned upgrade — it stays in hand (Jabba the Hutt
    ASH_42 "you may play it for free")."""

    def apply(self, state: GameState) -> GameState:
        if (not state.pending_decisions
                or state.pending_decisions[-1].kind != "play_upgrade_from_hand"):
            raise IllegalActionError("No play-upgrade-from-hand decision pending")
        s = copy.deepcopy(state)
        top = s.pending_decisions.pop()
        s.event_log.append(DecisionResolved(
            deciding_player_id=top.deciding_player_id,
            kind="play_upgrade_from_hand",
            choice="declined",
        ))
        if not s.is_terminal() and not s.pending_decisions:
            s.active_player_index = top.after_resolve_player_index
        return s

    def describe(self) -> str:
        return "Decline to play the upgrade"


def _play_upgrade_from_hand_actions(state: GameState, top) -> list["Action"]:
    """Legal actions for the top play_upgrade_from_hand decision (never empty — a
    decline is always offered, as the play is a "you may").

    Fixed-upgrade mode (``ctx['upgrade_id']`` set, Jabba ASH_42): one action per
    legal host.  Choose-upgrade mode (``upgrade_id`` None, Fenn Rau SHD_67): one
    action per (affordable hand upgrade × its legal host) pair, each carrying the
    chosen upgrade id."""
    ctx = top.context
    acts: list[Action] = []
    if ctx.get("upgrade_id") is not None:
        acts += [PlayUpgradeFromHand(h)
                 for h in sorted(_play_upgrade_from_hand_hosts(state, ctx))]
    else:
        for uid in _affordable_hand_upgrades(state, ctx):
            upg = _find_playable_upgrade(state, ctx, uid)
            if upg is None:
                continue
            for host in sorted(_play_upgrade_hosts_for(state, ctx, upg)):
                acts.append(PlayUpgradeFromHand(host, upgrade_id=uid))
    acts.append(DeclinePlayUpgradeFromHand())
    return acts

# ── Decision-kind registration ─────────────────────────────────────────────
register_decisions({
    "move_upgrade":                  _move_upgrade_actions,
    "pay_and_steal_upgrade":         _pay_and_steal_upgrade_actions,
    "pilot_self_attach":             _pilot_self_attach_actions,
    "play_upgrade_from_hand":        _play_upgrade_from_hand_actions,
})
