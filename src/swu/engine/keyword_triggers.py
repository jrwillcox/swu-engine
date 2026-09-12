"""
Keyword trigger registrations.

Loaded at startup by engine/__init__.py.  Registers listeners on the
TriggerBus for keywords whose effects fire in response to game events
(enter-play, round-start, etc.).

On-attack and stat-modifying keywords (Grit, Raid, Restore, Overwhelm,
Saboteur, Shield interception) are handled inline in the attack pipeline
in actions.py — they don't need the trigger bus because they're
deterministic pipeline steps, not conditional callbacks.

Phase 2 triggers registered here:
  * Shielded — UnitEntersPlay → attach Shield token
  * Ambush   — UnitEntersPlay → push AmbushDecision (if legal targets exist)
  * Support  — UnitEntersPlay / LeaderDeployed → push a granted_attack by ANOTHER
               unit, which borrows this card's other abilities for that attack

Ordering matters: Shielded is registered first so the Shield token is
attached before the Ambush decision is presented.  A unit with both
keywords therefore starts with its shield up during the Ambush trade.
Support is registered BEFORE Ambush so that on a unit carrying both
(Domesticated Loth-Cat ASH_68) the Support attack sits BELOW the Ambush
decision on the LIFO stack: the unit resolves its own attack first, then
the other unit's.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.state import GameState
    from swu.engine.events import GameEvent

from swu.engine.triggers import get_bus
from swu.engine.keywords import Keyword, has_keyword


# ── Shielded ──────────────────────────────────────────────────────────────────

def _shielded_listener(state: "GameState", event: "GameEvent") -> "GameState":
    from swu.engine.events import UnitEntersPlay
    from swu.engine.tokens import attach_token
    if not isinstance(event, UnitEntersPlay):
        return state
    result = state.find_instance(event.instance_id)
    if result is None:
        return state
    owner_ps, ci = result
    if not has_keyword(state, ci, Keyword.SHIELDED):
        return state
    attach_token(state, owner_ps, ci, "Shield")
    return state


# ── Ambush ────────────────────────────────────────────────────────────────────

def _ambush_listener(state: "GameState", event: "GameEvent") -> "GameState":
    """
    When a unit with Ambush enters play, push an AmbushDecision if there
    are legal unit targets in the same arena (respecting Sentinel rules).
    If no legal targets exist, Ambush cannot be used and no decision is pushed.
    """
    from swu.engine.events import UnitEntersPlay
    from swu.engine.decisions import PendingDecision
    from swu.engine.events import DecisionPushed
    if not isinstance(event, UnitEntersPlay):
        return state
    result = state.find_instance(event.instance_id)
    if result is None:
        return state
    owner_ps, unit_ci = result
    if not has_keyword(state, unit_ci, Keyword.AMBUSH):
        return state

    # Determine legal Ambush targets: enemy units in the same arena,
    # with Sentinel filtering applied.
    owner_idx = state.player_index(owner_ps.player_id)
    enemy_ps = state.players[1 - owner_idx]
    enemy_arena = (
        enemy_ps.ground_arena
        if unit_ci.zone.name == "GROUND_ARENA"
        else enemy_ps.space_arena
    )

    # Apply Sentinel constraint (Saboteur bypasses it)
    from swu.engine.keywords import Keyword as KW
    if has_keyword(state, unit_ci, KW.SABOTEUR):
        targets = list(enemy_arena)
    else:
        sentinels = [u for u in enemy_arena if has_keyword(state, u, KW.SENTINEL)]
        targets = sentinels if sentinels else list(enemy_arena)

    # Only push decision if there's at least one legal unit target
    if not targets:
        return state

    opponent_idx = 1 - owner_idx
    decision = PendingDecision(
        deciding_player_id=owner_ps.player_id,
        kind="ambush",
        context={"unit_id": unit_ci.instance_id},
        after_resolve_player_index=opponent_idx,
    )
    state.pending_decisions.append(decision)
    state.event_log.append(DecisionPushed(
        deciding_player_id=owner_ps.player_id,
        kind="ambush",
    ))
    return state


# ── Support ───────────────────────────────────────────────────────────────────

def _push_support_attack(state: "GameState", source_ci) -> "GameState":
    """Push the Support granted attack for ``source_ci``, if it can do anything.

    Support (ASH): "When you play this unit / deploy this leader, you may attack
    with ANOTHER unit.  It gains this unit's other abilities for this attack."

    Modelled entirely on the existing ``granted_attack`` decision:
      * ``optional``        — "you MAY attack" (a decline is always offered);
      * ``exclude_source``  — "with ANOTHER unit" (Mon Mothma SEC_103's field);
      * ``borrow_abilities`` — the "it gains this unit's other abilities" rider,
        landed on the chosen attacker as a this-attack ``borrowed_abilities``
        modifier at the AttackWithUnit site.

    The decision is pushed ONLY when some other unit could actually attack (the
    "don't offer a no-op" rule), probed with ``_filter_granted_attacks`` — the very
    function ``legal_actions`` will use to enumerate the options.
    """
    from swu.engine.state import Phase
    from swu.engine.actions import _filter_granted_attacks, push_granted_attack
    # An attack can only be declared in the action phase; a Support unit that
    # entered play in any other phase (a regroup-time effect) simply does nothing.
    if state.phase != Phase.ACTION or state.is_terminal():
        return state
    owner_idx = state.player_index(source_ci.owner_id)
    owner_ps = state.players[owner_idx]
    enemy_ps = state.players[1 - owner_idx]
    probe = {"source_id": source_ci.instance_id, "exclude_source": True}
    if not _filter_granted_attacks(state, probe, owner_ps, enemy_ps):
        return state
    push_granted_attack(
        state, source_ci,
        optional=True,
        exclude_source=True,
        borrow_abilities=True,
    )
    return state


def _support_enters_play_listener(state: "GameState", event: "GameEvent") -> "GameState":
    """"When you play this unit, you may attack with another unit."

    Fires off ``UnitEntersPlay`` — the Ambush convention: Ambush's reminder text
    also says "when you PLAY this unit" and the engine has always read that as
    entering play, so both keywords treat a Smuggle/discard/token entry alike.
    """
    from swu.engine.events import UnitEntersPlay
    if not isinstance(event, UnitEntersPlay):
        return state
    result = state.find_instance(event.instance_id)
    if result is None:
        return state
    _owner_ps, unit_ci = result
    if not has_keyword(state, unit_ci, Keyword.SUPPORT):
        return state
    return _push_support_attack(state, unit_ci)


def _support_deploy_listener(state: "GameState", event: "GameEvent") -> "GameState":
    """The leader half — "When you deploy this leader, you may attack with another
    unit" (Moff Gideon ASH_8, Ahsoka Tano ASH_9, The Mandalorian ASH_14)."""
    from swu.engine.events import LeaderDeployed
    if not isinstance(event, LeaderDeployed):
        return state
    result = state.find_instance(event.instance_id)
    if result is None:
        return state
    _owner_ps, leader_ci = result
    if not has_keyword(state, leader_ci, Keyword.SUPPORT):
        return state
    return _push_support_attack(state, leader_ci)


# ── Registration ──────────────────────────────────────────────────────────────

get_bus().register("UnitEntersPlay", _shielded_listener)
get_bus().register("UnitEntersPlay", _support_enters_play_listener)
get_bus().register("UnitEntersPlay", _ambush_listener)
get_bus().register("LeaderDeployed", _support_deploy_listener)
