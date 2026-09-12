"""The observer pipeline: what else happens because something happened.

Almost every triggered ability in the game is "when X happens, do Y", and this
module is the X half.  ``apply`` runs these nineteen ``_fire_*`` functions in a
**fixed order** after the action's own effect, each one asking the ability registry
whether any card in play cares about what just occurred — a unit entering play, a
card being drawn or discarded, damage dealt to a base, a token created, a Bounty
collected, a unit readied or healed.

**The order is behaviour, not style.** Several observers depend on running after
another, and ``_sweep_defeated_units`` is interleaved at a specific point so that
triggers see the board either before or after defeats as the rules require.  Moving
a ``_fire_*`` call, or reordering the block, changes which abilities see which
state.  They move together or not at all.

The ``note_*`` and ``record_*`` writers are the memory half: they record that
something happened this turn (a card discarded from hand, a base damaged, a token
unit attacking) so that abilities phrased "if you have ... this phase" have
something to read.  Two of them, ``_fire_bounty_observers`` and
``_fire_hand_discard_observers``, are reached from the card tests only by attribute
access on the package, so they are pinned individually in
``tests/test_actions_contract.py``.
"""
from __future__ import annotations


from swu.engine.decisions import PendingDecision
from swu.engine.events import (
    DecisionPushed, UnitDefeated,
)
from swu.engine.state import (
    CardInstance, GameState, Zone,
)

from swu.engine.actions.damage import (
    note_base_healed,
)
from swu.engine.actions.zones import (
    _sweep_defeated_units,
)


# ── Delayed action-phase-start scheduler + per-enemy pay-or-exhaust ────────────

def _fire_scheduled_action_phase_effects(s: GameState) -> None:
    """Drain the once-only scheduled effects at the start of an action phase.
    Clears the list first (so nothing re-fires next round), then dispatches each
    entry by kind — a no-op for every game with nothing scheduled."""
    scheduled = list(s.scheduled_action_phase_effects)
    if not scheduled:
        return
    s.scheduled_action_phase_effects.clear()
    for entry in scheduled:
        if entry.get("kind") == "eye_of_aldhani":
            _fire_eye_of_aldhani(s, entry["controller_id"])
        elif entry.get("kind") == "defeat_own_resource":
            _fire_defeat_own_resource(s, entry["controller_id"])


def _fire_eye_of_aldhani(s: GameState, controller_id: str) -> None:
    """Push a per-enemy pay-or-exhaust decision for the caster's opponent.  Snapshots
    the opponent's READY units (an already-exhausted unit's "or exhaust that unit"
    is a guaranteed no-op, so paying to protect it is never rational — skipping them
    is faithful in outcome and avoids pointless prompts).  No push if the opponent
    has no ready unit."""
    try:
        caster_idx = s.player_index(controller_id)
    except (KeyError, ValueError):
        return
    opp_ps = s.players[1 - caster_idx]
    pending_ids = [u.instance_id
                   for u in opp_ps.ground_arena + opp_ps.space_arena
                   if not u.exhausted]
    if not pending_ids:
        return
    decider_id = opp_ps.player_id
    dec = PendingDecision(
        deciding_player_id=decider_id,
        kind="pay_or_exhaust",
        context={
            "controller_id": decider_id,   # the deciding player (controls the units)
            "caster_id": controller_id,
            "pending_ids": pending_ids,
        },
        after_resolve_player_index=s.active_player_index,
    )
    s.pending_decisions.append(dec)
    s.active_player_index = s.player_index(decider_id)
    s.event_log.append(DecisionPushed(
        deciding_player_id=decider_id,
        kind="pay_or_exhaust",
    ))


# ── Delayed "defeat a resource you control at the next action phase" ──────────

def _fire_defeat_own_resource(s: GameState, controller_id: str) -> None:
    """Defeat one resource the given player controls (auto-selected — resources are
    fungible face-down cards; prefer a plain face-down resource).  No-op if the
    player controls no resource."""
    try:
        ps = s.player_by_id(controller_id)
    except (KeyError, ValueError):
        return
    if not ps.resources:
        return
    res = next((r for r in ps.resources if r.face_down), ps.resources[0])
    ps.resources.remove(res)
    res.zone = Zone.DISCARD
    res.face_down = False
    res.exhausted = False
    ps.discard.append(res)
    s.event_log.append(UnitDefeated(
        player_id=ps.player_id,
        instance_id=res.instance_id,
        card_name=res.card_def.display_name,
    ))


# ── apply convenience wrapper ─────────────────────────────────────────────────

def _fire_noncombat_damage_observers(s: GameState) -> GameState:
    """Drain the non-combat damage ledger, firing the WhenDealNonCombatDamage
    observer (Boba Fett JTL_9) once per dealer.

    Runs at the action settle-point (after the defeat sweep).  A settle only fires
    while the stack is clear — a WhenDealNonCombatDamage trigger resolves after the
    current ability finishes; if a decision is still pending we leave the ledger for
    the next apply() (which resolves that decision, then re-settles).  Purely
    additive for every existing deck: with no WhenDealNonCombatDamage card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.
    """
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.noncombat_damage_dealers
    while queue and not s.pending_decisions and not s.is_terminal():
        dealer_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"noncombat_damage_dealer_id": dealer_id})
        _sweep_defeated_units(s)
    return s


def _fire_draw_observers(s: GameState) -> GameState:
    """Drain the ACTION-phase draw ledger, firing the WhenYouDraw observer once per
    draw event (The Mandalorian LAW_52 in-play observer; Rey LOF_148 drawn-card).

    Runs at the action settle-point (mirroring _fire_noncombat_damage_observers).  A
    settle only fires while the stack is clear — if a decision is pending we leave the
    ledger for the next apply() (which resolves that decision, then re-settles).
    Purely additive for every existing deck: with no WhenYouDraw card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.  Each entry carries the drawer id (for the
    in-play observer) and the drawn card ids (for a drawn-card's own trigger).
    """
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.action_phase_draws
    while queue and not s.pending_decisions and not s.is_terminal():
        entry = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"drew_player_id": entry["player_id"],
                       "drawn_card_ids": list(entry["card_ids"]),
                       "draw_phase": entry.get("phase", "ACTION")})
        _sweep_defeated_units(s)
    return s


def _fire_force_observers(s: GameState) -> GameState:
    """Drain the Force-use ledger, firing the WhenYouUseForce observer once per use
    (Yoda LOF_101 in-play observer).

    Runs at the action settle-point (mirroring _fire_draw_observers).  A settle only
    fires while the stack is clear — if a decision is pending we leave the ledger for
    the next apply() (which resolves that decision, then re-settles).  Purely additive
    for every existing deck: with no WhenYouUseForce card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.  Each entry is the id of the player who used the
    Force (matched only when it equals the observer's controller — "when YOU use").
    """
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.force_uses
    while queue and not s.pending_decisions and not s.is_terminal():
        player_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"force_used_player_id": player_id})
        _sweep_defeated_units(s)
    return s


def note_unit_healed(s: GameState, ci: "CardInstance", healed: int) -> None:
    """Record that ``healed`` damage was actually removed from the UNIT ``ci`` this
    phase, feeding the phase-scoped ``units_healed_this_phase`` ledger read by the
    ``healed_this_phase`` target predicate ("Each friendly unit that was healed this
    phase gets +1/+0" — Barriss Offee TWI_42).

    ``healed <= 0`` records nothing: an undamaged unit "healed" for 2 has no damage
    removed, so it was not healed.  Bases are ignored (the card asks about units).
    Purely additive bookkeeping — called from the heal chokepoints
    (``resolver._apply_heal`` and the heal flavour of the damage-distribution
    decision); a bespoke card-module heal that touches ``ci.damage`` directly is not
    marked (a documented simplification, the same shape as
    ``note_hand_or_deck_discard``)."""
    if healed <= 0:
        return
    from swu.cards.models import Base
    if isinstance(ci.card_def, Base):
        # A BASE keeps its own phase ledger instead (Dooku's Solar Sailer TS26_38's
        # "If a base was healed this phase"); the unit ledger and the WhenUnitHealed
        # drain below are deliberately units-only.
        note_base_healed(s, ci, healed)
        return
    s.game_memory.units_healed_this_phase.add(ci.instance_id)
    # Beside the phase-scoped ledger, queue the heal for the settle-drain that fires
    # the WhenUnitHealed observer ("When 1 or more damage is healed from this unit",
    # Silver Angel JTL_62).  The ``healed <= 0`` guard above IS the "1 or more", and
    # one entry per heal instruction means two separate heals fire twice.
    # The entry carries the AMOUNT beside the id so an observer can say "deal THAT
    # MUCH damage" (Baze Malbus LAW_47); a bare id (a legacy/serialised entry) is
    # still accepted by the drain and reads as an unknown amount.
    s.game_memory.heal_events.append([ci.instance_id, int(healed)])


def note_unit_readied(s: GameState, ci: "CardInstance") -> None:
    """Queue the readying of the UNIT ``ci`` for the settle-drain that fires the
    WhenUnitReadies observer ("When attached unit readies" — In Debt to Crimson Dawn
    JTL_192).  The ``note_unit_healed`` shape.

    Call this BEFORE clearing ``exhausted``: a card that was already ready did not
    *ready*, so it records nothing.  Only arena units are queued (the trigger is a
    unit trigger; resources and the base zone ready too).  Fed from the ready
    chokepoints — the regroup mass-ready ``_ready_all_cards`` and the ``ReadyCard``
    effect arm — so a bespoke card-module ready that pokes ``ci.exhausted`` directly
    is unmarked (a documented simplification)."""
    if not getattr(ci, "exhausted", False):
        return
    if ci.zone not in (Zone.GROUND_ARENA, Zone.SPACE_ARENA):
        return
    # ``[instance_id, phase]`` (the ``heal_events`` widening) — the phase at READY
    # time, which the drain cannot re-derive: the regroup mass-ready is drained after
    # the rollover into ACTION (Rex's DC-17s TS26_63 "during the action phase").
    s.game_memory.ready_events.append(
        [ci.instance_id, getattr(s.phase, "name", str(s.phase))])


def _fire_base_damage_observers(s: GameState) -> GameState:
    """Drain the base-damage ledger, firing the WhenDamageDealtToYourBase observer
    once per damage instance (The Daughter LOF_252).

    The ``_fire_heal_observers`` shape exactly: runs at the action settle-point with
    a clear stack, and is purely additive — with no such card in play
    ``fire_triggered_abilities`` finds nothing and the ledger is still drained."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.base_damage_events
    while queue and not s.pending_decisions and not s.is_terminal():
        owner_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"base_damaged_player_id": owner_id})
        _sweep_defeated_units(s)
    return s


def _fire_upgrade_defeat_observers(s: GameState) -> GameState:
    """Drain the upgrade-defeat queue, firing WhenFriendlyUpgradeDefeated once per
    defeated upgrade (Zeb Orrelios ASH_161).

    The ``_fire_heal_observers`` shape verbatim: runs at the action settle-point with
    a clear stack, so a decision the observer pushes lands cleanly and the rest of the
    queue waits for the next apply()."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.upgrade_defeats
    while queue and not s.pending_decisions and not s.is_terminal():
        controller_id = queue.pop(0)
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=s.active_player_index,
            event_ctx={"upgrade_defeat_controller": controller_id})
        _sweep_defeated_units(s)
    return s


_UNIT_ENTRY_OBSERVER_KEYS: list = []


def _unit_entry_observer_keys() -> frozenset:
    """Cached (set_code, card_number) index of the cards carrying a
    ``WhenYouPlayOrCreateUnit`` trigger — the ``_token_doubler_keys`` /
    ``_suppress_leader_keys`` trick.  A unit entering play is one of the commonest
    things that happens, so the drain below must not walk the arenas at all for a
    board with no such card in it."""
    if not _UNIT_ENTRY_OBSERVER_KEYS:
        from swu.abilities.registry import (
            _REGISTRY, TriggerAbility, WhenYouPlayOrCreateUnit,
        )
        keys: set = set()
        for key, specs in _REGISTRY.items():
            for spec in specs:
                if (isinstance(spec, TriggerAbility)
                        and isinstance(spec.trigger, WhenYouPlayOrCreateUnit)):
                    keys.add(key)
                    break
        _UNIT_ENTRY_OBSERVER_KEYS.append(frozenset(keys))
    return _UNIT_ENTRY_OBSERVER_KEYS[0]


def _fire_unit_entry_observers(s: GameState) -> GameState:
    """Drain the unit-entry queue, firing WhenYouPlayOrCreateUnit once per unit that
    entered play ("When you play or create a unit" Greef Karga ASH_17; "When a
    friendly unit enters play (including this one)" Outcast ASH_41).

    The ``_fire_upgrade_defeat_observers`` shape verbatim: runs at the action
    settle-point with a clear stack, so a decision an observer pushes lands cleanly
    and the rest of the queue waits for the next apply().  ``entered_unit_id`` is how
    "that unit" is located; a unit that has already left play again by the time the
    drain runs simply finds nothing."""
    queue = s.game_memory.unit_entries
    if not queue:
        return s
    if not _unit_entry_observer_keys():
        queue.clear()
        return s
    from swu.abilities.resolver import fire_triggered_abilities
    while queue and not s.pending_decisions and not s.is_terminal():
        rec = queue.pop(0)
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=s.active_player_index,
            event_ctx={"entered_unit_id": rec.get("instance_id"),
                       "entered_unit_player": rec.get("player_id")})
        _sweep_defeated_units(s)
    return s


def _fire_upgrade_attach_observers(s: GameState) -> GameState:
    """Drain the upgrade-attach queue, firing WhenUpgradeAttached ONCE per host
    (Sabine Wren ASH_208).

    The ``_fire_upgrade_defeat_observers`` shape, plus the coalescing
    ``_fire_token_creation_observers`` needs: the card reads "when **1 or more**
    upgrades attach", so several attachments landing on one host before the settle
    point are one event.  Because the queue is only fed for hosts that actually carry
    such a trigger (see ``note_upgrade_attached``) the dedupe is cheap."""
    queue = s.game_memory.upgrade_attachments
    if not queue:
        return s
    from swu.abilities.resolver import fire_triggered_abilities
    seen: set = set()
    batch = [h for h in queue if not (h in seen or seen.add(h))]
    queue.clear()
    for host_id in batch:
        if s.pending_decisions or s.is_terminal():
            # Re-queue what is left; the next settle point drains it.
            queue.append(host_id)
            continue
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=s.active_player_index,
            event_ctx={"upgrade_attached_host": host_id})
        _sweep_defeated_units(s)
    return s


_TOKEN_DOUBLER_KEYS: list = []


def _token_doubler_keys() -> frozenset:
    """Cached (set_code, card_number) index of the cards carrying a
    WhenYouWouldCreateTokens trigger — the ``_shield_aura_prevention_keys`` /
    ``_suppress_leader_keys`` trick.  Token creation is very frequent on an ASH board
    (every Shield, Experience and Advantage token), so the drain must not walk the
    arenas for a board with no such card in it."""
    if not _TOKEN_DOUBLER_KEYS:
        from swu.abilities.registry import (
            _REGISTRY, TriggerAbility, WhenYouWouldCreateTokens,
        )
        keys = {key for key, specs in _REGISTRY.items()
                if any(isinstance(sp, TriggerAbility)
                       and isinstance(sp.trigger, WhenYouWouldCreateTokens)
                       for sp in specs)}
        _TOKEN_DOUBLER_KEYS.append(frozenset(keys))
    return _TOKEN_DOUBLER_KEYS[0]


def _player_has_token_doubler(s: GameState, player_id: str) -> bool:
    """True while ``player_id`` controls an arena unit carrying the trigger."""
    keys = _token_doubler_keys()
    if not keys:
        return False
    ps = s.player_by_id(player_id)
    if ps is None:
        return False
    for ci in ps.ground_arena + ps.space_arena:
        key = (getattr(ci.card_def, "set_code", None) or "",
               getattr(ci.card_def, "card_number", None) or "")
        if key in keys:
            return True
    return False


def _fire_token_creation_observers(s: GameState) -> GameState:
    """Drain the token-creation ledger, firing the WhenYouWouldCreateTokens observer
    once per creation (Moff Jerjerrod ASH_94).

    The ``_fire_upgrade_defeat_observers`` shape, plus two things that family did not
    need.  (1) COALESCING: equal-keyed records (same creator, kind, token name, host
    and ready-ness) are merged into one event, so "give 2 Experience tokens" — which
    the engine performs as two ``attach_token`` calls — reads as a single creation of
    2 and doubles to 4, not 3.  (2) A cheap registry-index gate before any firing,
    because this ledger is fed constantly on an ASH board.

    DOCUMENTED DEVIATION (the reason this is an observer rather than a true
    replacement effect): the printed card replaces the creation, creating 2N tokens at
    once; here the original N are created as normal and the player is offered the
    top-up of another N at the settle-point, which reaches the same board state
    without a decision pushed from inside a creation."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.token_creations
    if not queue:
        return s
    if not _token_doubler_keys():
        queue.clear()  # nothing in the game can observe these
        return s
    while queue and not s.pending_decisions and not s.is_terminal():
        head = queue.pop(0)

        def _key(rec):
            return (rec.get("creator"), rec.get("kind"), rec.get("name"),
                    rec.get("host"), bool(rec.get("ready")))

        key = _key(head)
        count = int(head.get("count") or 0)
        rest = []
        for rec in queue:
            if _key(rec) == key:
                count += int(rec.get("count") or 0)
            else:
                rest.append(rec)
        queue[:] = rest
        if count <= 0 or not _player_has_token_doubler(s, head.get("creator")):
            continue
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=s.active_player_index,
            event_ctx={
                "token_creation_creator": head.get("creator"),
                "token_creation_kind": head.get("kind"),
                "token_creation_name": head.get("name"),
                "token_creation_count": count,
                "token_creation_host": head.get("host"),
                "token_creation_ready": bool(head.get("ready")),
            })
        _sweep_defeated_units(s)
    return s


def _fire_ready_observers(s: GameState) -> GameState:
    """Drain the ready ledger, firing the WhenUnitReadies observer once per unit that
    readied (In Debt to Crimson Dawn JTL_192).

    Runs at the action settle-point (mirroring ``_fire_heal_observers``) — a settle
    only fires while the stack is clear, so a decision the observer pushes (the
    pay-or-exhaust) lands cleanly and the rest of the ledger waits for the next
    apply().  Purely additive: with no WhenUnitReadies card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.ready_events
    while queue and not s.pending_decisions and not s.is_terminal():
        entry = queue.pop(0)
        # An entry is [instance_id, phase]; a bare string is a legacy/serialised
        # one and reads as an ACTION-phase ready.
        if isinstance(entry, (list, tuple)):
            readied_id = entry[0]
            readied_phase = entry[1] if len(entry) > 1 else "ACTION"
        else:
            readied_id, readied_phase = entry, "ACTION"
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"readied_unit_id": readied_id,
                       "readied_phase": readied_phase})
        _sweep_defeated_units(s)
    return s


def _fire_heal_observers(s: GameState) -> GameState:
    """Drain the heal ledger, firing the WhenUnitHealed observer once per heal
    instruction (Silver Angel JTL_62: "When 1 or more damage is healed from this
    unit: …").

    Runs at the action settle-point (mirroring _fire_hand_discard_observers).  A
    settle only fires while the stack is clear — if a decision is pending we leave the
    ledger for the next apply() (which resolves that decision, then re-settles).
    Purely additive for every existing deck: with no WhenUnitHealed card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.  Each entry is the healed UNIT's instance id,
    matched against the observer's own id — the trigger is self-referential ("from
    THIS unit"), so a unit healed after leaving play simply matches nothing."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.heal_events
    while queue and not s.pending_decisions and not s.is_terminal():
        entry = queue.pop(0)
        # An entry is [instance_id, amount]; a bare id (legacy/serialised) reads as
        # amount 0 — "that much damage" then simply deals nothing.
        if isinstance(entry, str):
            healed_id, healed_amount = entry, 0
        else:
            healed_id, healed_amount = entry[0], int(entry[1])
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"healed_unit_id": healed_id,
                       "healed_amount": healed_amount})
        _sweep_defeated_units(s)
    return s


def _fire_reveal_discard_observers(s: GameState) -> GameState:
    """Drain the reveal/discard-from-hand ledger, firing the WhenYouRevealOrDiscard
    observer once per reveal/discard instruction (Padmé Amidala SEC_16).

    Runs at the action settle-point (mirroring _fire_force_observers).  A settle only
    fires while the stack is clear — if a decision is pending we leave the ledger for
    the next apply() (which resolves that decision, then re-settles).  Purely additive
    for every existing deck: with no WhenYouRevealOrDiscard card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.  Each entry is the id of the player who revealed
    or discarded (matched only when it equals the observer's controller — "when YOU
    reveal or discard")."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.hand_reveal_discards
    while queue and not s.pending_decisions and not s.is_terminal():
        player_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"hand_reveal_discard_player_id": player_id})
        _sweep_defeated_units(s)
    return s


def _fire_hand_discard_observers(s: GameState) -> GameState:
    """Drain the discard-only ledger, firing the WhenPlayerDiscardsFromHand observer
    once per discard instruction (Migs Mayfeld SHD_163: "When a player discards a card
    from their hand: …", ANY player).

    Runs at the action settle-point (mirroring _fire_reveal_discard_observers).  A
    settle only fires while the stack is clear — if a decision is pending we leave the
    ledger for the next apply() (which resolves that decision, then re-settles).
    Purely additive for every existing deck: with no WhenPlayerDiscardsFromHand card in
    play ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so
    the behaviour and RNG are unchanged.  Each entry is the id of the player who
    discarded — matched with NO owner guard ("a player" = anyone)."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.hand_discards
    while queue and not s.pending_decisions and not s.is_terminal():
        player_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"hand_discard_player_id": player_id})
        _sweep_defeated_units(s)
    return s


def _fire_self_discard_observers(s: GameState) -> GameState:
    """Drain the hand/deck-discard ledger, firing the WhenThisIsDiscarded observer once
    per discarded CARD (That's a Rock LAW_206: "When this event is discarded from your
    hand or deck: You may deal 1 damage to a unit.").

    Runs at the action settle-point (mirroring _fire_hand_discard_observers).  A settle
    only fires while the stack is clear — if a decision is pending we leave the ledger
    for the next apply() (which resolves that decision, then re-settles).  Purely
    additive for every existing deck: with no WhenThisIsDiscarded card discarded
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.  Each entry is the DISCARDED card's own instance
    id, matched against the observer's own id — the trigger is self-referential, and
    the source is located in its owner's discard pile by _collect_triggers."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.self_discards
    while queue and not s.pending_decisions and not s.is_terminal():
        discarded_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"self_discard_id": discarded_id})
        _sweep_defeated_units(s)
    return s


def _fire_deck_discard_observers(s: GameState) -> GameState:
    """Drain the DECK-discard ledger, firing the WhenYouDiscardFromDeck observer once
    per card milled (Sebulba's Podracer LAW_176: "When you discard a card from your
    deck: You may ready this unit").

    The `_fire_self_discard_observers` shape one step over: that one is keyed by the
    discarded CARD and finds its source in the discard pile, this one is keyed by the
    milling PLAYER and its source is an ordinary card in play, so the standard
    `_collect_triggers` in-play scan finds it with no dedicated scan.  Runs at the
    action settle-point, so a three-card mill fires it three times on a clean stack
    rather than mid-loop.  Purely additive: with no such observer in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.deck_discards
    while queue and not s.pending_decisions and not s.is_terminal():
        player_id = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"deck_discard_player_id": player_id})
        _sweep_defeated_units(s)
    return s


def _fire_bounty_observers(s: GameState) -> GameState:
    """Drain the bounties-collected ledger, firing the WhenBountyCollected observer
    once per bounty collected (Bossk SHD_10: "When you collect a bounty: …").

    Runs at the action settle-point (mirroring _fire_force_observers).  A settle only
    fires while the stack is clear — if a decision is pending we leave the ledger for
    the next apply() (which resolves that decision, then re-settles).  Purely additive
    for every existing deck: with no WhenBountyCollected card in play
    ``fire_triggered_abilities`` finds nothing (the ledger is still cleared), so the
    behaviour and RNG are unchanged.  Each entry carries the collector id (matched only
    when it equals the observer's controller — "when YOU collect a bounty") plus the
    collected bounty's registry coordinates, which the re-collection payoff
    (push_bounty_recollect) reads to re-run that exact bounty."""
    from swu.abilities.resolver import fire_triggered_abilities
    queue = s.game_memory.bounties_collected
    while queue and not s.pending_decisions and not s.is_terminal():
        entry = queue.pop(0)
        after_idx = s.active_player_index
        s = fire_triggered_abilities(
            s, None, after_all_player_idx=after_idx,
            event_ctx={"bounty_collector_id": entry["collector_id"],
                       "recollect_bounty": dict(entry)})
        _sweep_defeated_units(s)
    return s


# ── Player-directed damage distribution push helpers ──────────────────────────

def _fire_action_phase_start_triggers(s: GameState, evt) -> None:
    """Fire ``PhaseStartTrigger(phase="action")`` abilities at an ACTION-phase entry.

    The regroup mirror of the long-standing ``_enter_regroup`` fire site (Contracted
    Hunter JTL_216).  Called from BOTH action-phase entries — the first one
    (``_start_action_phase``) and every round rollover — with the same
    ``PhaseChanged`` event the log already carries, so a trigger narrowed by
    ``first_only`` (Nabat Village JTL_28, "When the first action phase starts")
    picks the round out of the event itself.  ``after_all_player_idx`` returns
    control to the initiative holder, who acts first in an action phase."""
    if s.is_terminal():
        return
    from swu.abilities.resolver import fire_triggered_abilities
    fire_triggered_abilities(s, evt, after_all_player_idx=s.initiative_holder)
