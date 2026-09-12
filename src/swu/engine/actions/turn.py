"""Starting a game: deck setup, opening hands, and the seeded RNG.

``create_game`` builds the initial ``GameState`` from two decklists — shuffling with
a seeded RNG, dealing opening hands, and pushing the mulligan decisions that the
first ``legal_actions`` call will offer.

The seeding is the part worth protecting.  Every shuffle and random choice in a game
must come from ``state.make_rng()`` so that a seed fully determines the game: the
soak suite plays 400 seeded games and the determinism regression replays specific
seeds expecting identical results.  Two bugs in this area were real and are worth
remembering — a global ``random.shuffle`` that made the same seed diverge, and
``uuid4`` modifier ids that made a serialised end state differ run to run.  Both are
covered by ``tests/regressions/test_determinism_seeded_replay.py``.

The starting hand size is a value, not a constant, because a base can change it —
``_starting_hand_modifier`` is why ``STARTING_HAND_SIZE`` is only the default.
"""
from __future__ import annotations

from typing import Optional

from swu.cards.models import AnyCard, Base, Leader
from swu.engine.events import (
    AllCardsReadied, GameStarted, HandDrawn, PhaseChanged, RegroupDrawn, RoundStarted, UpgradeDetached,
)
from swu.engine.state import (
    CardInstance, GameState, Phase, PlayerState, Zone,
)
from swu.engine.triggers import get_bus

from swu.engine.actions.stats import (
    _expire_modifiers,
)
from swu.engine.actions.zones import (
    _apply_put_on_deck, _defeat_unit, _draw_cards, _find_in_arenas, _rescue_captured_card, change_control,
)
from swu.engine.actions.flow import (
    _check_game_over,
)
from swu.engine.actions.combat import (
    note_hand_or_deck_discard, record_hand_discard,
)
from swu.engine.actions.observers import (
    _fire_action_phase_start_triggers, _fire_defeat_own_resource, _fire_scheduled_action_phase_effects, note_unit_readied,
)

# ── Setup actions ─────────────────────────────────────────────────────────────

STARTING_HAND_SIZE = 6


def _starting_hand_modifier(ps: "PlayerState"):
    """The ``StartingHandModifier`` marker on ``ps``'s base, or None.

    Scans the player's ``base_zone`` (which also holds the undeployed leader — a
    leader carrying the marker would count too, but none prints it).  A no-op read
    for every base without the marker (the ``_extra_regroup_active`` shape)."""
    from swu.abilities.registry import get_abilities, StartingHandModifier
    for ci in ps.base_zone:
        sc = getattr(ci.card_def, "set_code", None) or ""
        cn = getattr(ci.card_def, "card_number", None) or ""
        if not sc or not cn:
            continue
        for spec in get_abilities(sc, cn):
            if isinstance(spec, StartingHandModifier):
                return spec
    return None


def _starting_hand_size(ps: "PlayerState") -> int:
    """How many cards ``ps`` draws for an opening hand (and redraws on a mulligan).

    The standard 6, shifted by their base's ``StartingHandModifier`` — "Draw 1 less
    card in your starting hand" (Colossus JTL_21) / "Draw 3 more" (Nabat Village
    JTL_28).  Floored at 0."""
    spec = _starting_hand_modifier(ps)
    return max(0, STARTING_HAND_SIZE + (int(spec.amount) if spec is not None else 0))


# ── Game creation ─────────────────────────────────────────────────────────────

def create_game(
    player0_id: str,
    deck0: list[AnyCard],
    player1_id: str,
    deck1: list[AnyCard],
    seed: Optional[int] = None,
) -> GameState:
    """Build the initial GameState: shuffle decks, flip coin, draw opening hands."""
    rng = _new_rng(seed)
    counter = 0

    def make_player(pid: str, deck: list[AnyCard]) -> PlayerState:
        nonlocal counter
        ps = PlayerState(player_id=pid)
        for card in deck:
            if isinstance(card, Leader):
                ci = CardInstance(
                    instance_id=f"{pid}_{counter}", card_def=card,
                    owner_id=pid, zone=Zone.BASE_ZONE,
                )
                counter += 1
                ps.base_zone.append(ci)
            elif isinstance(card, Base):
                ci = CardInstance(
                    instance_id=f"{pid}_{counter}", card_def=card,
                    owner_id=pid, zone=Zone.BASE_ZONE,
                )
                counter += 1
                ps.base_zone.append(ci)
            else:
                ci = CardInstance(
                    instance_id=f"{pid}_{counter}", card_def=card,
                    owner_id=pid, zone=Zone.DECK,
                )
                counter += 1
                ps.deck.append(ci)
        return ps

    ps0 = make_player(player0_id, deck0)
    ps1 = make_player(player1_id, deck1)

    rng.shuffle(ps0.deck)
    rng.shuffle(ps1.deck)
    initiative_holder = rng.randint(0, 1)

    state = GameState(
        players=[ps0, ps1],
        phase=Phase.SETUP_MULLIGAN,
        active_player_index=0,
        initiative_holder=initiative_holder,
        rng_state=rng.getstate(),
        _next_id=counter,
    )
    state.event_log.append(GameStarted(
        player_ids=(player0_id, player1_id),
        initiative_holder_id=state.players[initiative_holder].player_id,
    ))

    # The opening hand is 6, shifted by each player's base (Colossus JTL_21 draws
    # 1 less, Nabat Village JTL_28 draws 3 more) — see _starting_hand_size.
    n0 = _starting_hand_size(ps0)
    _draw_cards(state, ps0, n0)
    state.event_log.append(HandDrawn(player_id=player0_id, card_count=n0))
    n1 = _starting_hand_size(ps1)
    _draw_cards(state, ps1, n1)
    state.event_log.append(HandDrawn(player_id=player1_id, card_count=n1))

    return state


# ── Internal helpers ──────────────────────────────────────────────────────────

def _new_rng(seed: Optional[int]) -> "random.Random":  # noqa: F821 (imported in body)
    import random
    return random.Random(seed)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _advance_mulligan(s: GameState) -> None:
    if all(s.mulligan_done):
        s.event_log.append(PhaseChanged(new_phase="SETUP_RESOURCES", round_number=0))
        s.phase = Phase.SETUP_RESOURCES
        s.active_player_index = 0
    else:
        s.active_player_index = 1 - s.active_player_index


def _advance_setup_resources(s: GameState) -> None:
    idx = s.active_player_index
    if all(rc >= 2 for rc in s.resources_chosen):
        _start_action_phase(s)
    else:
        s.active_player_index = 1 - idx


def _start_action_phase(s: GameState) -> None:
    s.phase = Phase.ACTION
    s.active_player_index = s.initiative_holder
    s.passed_players = set()
    s.initiative_claimed_this_round = False
    s.round_number = 1
    action_evt = PhaseChanged(new_phase="ACTION", round_number=s.round_number)
    s.event_log.append(action_evt)
    s.event_log.append(RoundStarted(
        round_number=s.round_number,
        initiative_holder_id=s.players[s.initiative_holder].player_id,
    ))
    get_bus().fire(s, s.event_log[-1])
    _fire_scheduled_action_phase_effects(s)
    _fire_action_phase_start_triggers(s, action_evt)


def _ready_forbidden(state: GameState, ci: CardInstance) -> bool:
    """True if ``ci`` can't ready right now, because either it OR one of its
    attached upgrades declares a ``ReadyRestriction`` whose condition currently
    holds — evaluated against ``ci`` (the host) in both cases.  Own restriction:
    Leia Organa LOF_98 ("While this unit is in the space arena, she can't ready").
    Upgrade-granted restriction: Frozen in Carbonite SHD_193 ("Attached unit can't
    ready" — an unconditional ``ReadyRestriction`` carried by the upgrade, whose
    ``condition`` is ``None`` = always).  The ready-site mirror of
    ``_attack_forbidden`` (note the inverted polarity — ``ReadyRestriction`` forbids
    WHILE its condition is True).  Read at the two ready sites that already honour
    ``cannot_ready_this_round`` (``_ready_all_cards`` + the ``ReadyCard`` effect
    arm); a no-op for the overwhelming majority of units (no such spec)."""
    from swu.abilities.registry import get_abilities, ReadyRestriction

    def _blocks(card_def) -> bool:
        sc = getattr(card_def, "set_code", None) or ""
        cn = getattr(card_def, "card_number", None) or ""
        if not sc or not cn:
            return False
        for spec in get_abilities(sc, cn):
            if isinstance(spec, ReadyRestriction):
                # Rampart JTL_182: "doesn't ready DURING THE REGROUP PHASE" — an
                # effect may still ready it mid-action.
                if getattr(spec, "regroup_only", False) and state.phase != Phase.REGROUP:
                    continue
                if spec.condition is None or spec.condition.evaluate(state, ci):
                    return True
        return False

    if _blocks(ci.card_def):
        return True
    for upg in ci.attached_upgrades:
        if _blocks(upg.card_def):
            return True
    return False


# ── Player-directed damage distribution push helpers ──────────────────────────

def _enter_regroup(s: GameState) -> None:
    s.event_log.append(PhaseChanged(new_phase="REGROUP", round_number=s.round_number))
    s.phase = Phase.REGROUP
    # "At the start of the regroup phase, you lose the game" (Final Showdown
    # SHD_208).  Each scheduled player is forced to lose by marking its base
    # defeated (lethal damage), which is_eliminated / _check_game_over pick up.  Done
    # first, before the regroup draws and the delayed-sweep block below, so a
    # scheduled loss short-circuits the rest of regroup.  The schedule is then
    # cleared (it is a one-shot).
    if s.game_memory.lose_at_regroup:
        for pid in list(s.game_memory.lose_at_regroup):
            ps = s.player_by_id(pid)
            if ps is not None and ps.base_instance is not None:
                ps.base_instance.damage = ps.base_instance.card_def.hp
        s.game_memory.lose_at_regroup.clear()
        _check_game_over(s)
        if s.is_terminal():
            return
    # "At the start of the regroup phase, if you are the only player who controls
    # units in that arena, you win the game" (Confidence in Victory SEC_145) — the
    # mirror of the schedule above, delivered by marking every OTHER player's base
    # defeated.  Also a one-shot: the schedule is cleared whether or not it paid off.
    if s.game_memory.win_at_regroup_sole_arena:
        for entry in list(s.game_memory.win_at_regroup_sole_arena):
            winner_id = entry.get("player_id")
            arena = entry.get("arena")
            counts = {
                p.player_id: len(p.ground_arena if arena == "ground" else p.space_arena)
                for p in s.players}
            if counts.get(winner_id, 0) <= 0:
                continue
            if any(n > 0 for pid, n in counts.items() if pid != winner_id):
                continue
            for ps in s.players:
                if ps.player_id != winner_id and ps.base_instance is not None:
                    ps.base_instance.damage = ps.base_instance.card_def.hp
        s.game_memory.win_at_regroup_sole_arena.clear()
        _check_game_over(s)
        if s.is_terminal():
            return
    # "At the start of the regroup phase, its owner rescues it" (Arrest SEC_195) —
    # scheduled captives leave the capture pile for their owner's hand through the
    # shared CR rescue seam.  A one-shot; a captive already gone is skipped.
    if s.game_memory.rescue_at_regroup:
        for iid in list(s.game_memory.rescue_at_regroup):
            res = s.find_instance(iid)
            if res is not None:
                _rescue_captured_card(s, res[1])
        s.game_memory.rescue_at_regroup.clear()
    # "If you do, defeat that many friendly resources at the start of the regroup
    # phase" (Sundari Palace TS26_12) — the numeric sibling of the sweep above.
    # Resources are fungible face-down cards, so each defeat is auto-picked through
    # the shared ``_fire_defeat_own_resource`` seam (which is itself a clean no-op on
    # an empty row).  A one-shot: the schedule is cleared whether or not it was paid.
    if s.game_memory.defeat_resources_at_regroup:
        for pid, n in list(s.game_memory.defeat_resources_at_regroup.items()):
            for _ in range(int(n)):
                _fire_defeat_own_resource(s, pid)
        s.game_memory.defeat_resources_at_regroup.clear()
    # Count this regroup phase (reset to 0 at the round rollover).  Normally reaches
    # 1; a second entry (Max Rebo LAW_72's additional regroup) reaches 2 — the cap
    # _end_regroup checks so the extra regroup happens exactly once per round.
    s.regroup_count_this_round += 1
    # "For this phase" effects (Tactical Advantage TWI_124's +2/+2, Moment of
    # Glory SHD_130, granted keywords, etc.) last through the ACTION phase in
    # which they were played and wear off when it ends.  The action phase is
    # ending now (ACTION->REGROUP), so expire every this_phase modifier here.
    # A unit whose effective HP now drops to lethal is caught by the settle-time
    # _sweep_defeated_units in apply().
    _expire_modifiers(s, "this_phase")
    for ps in s.players:
        drawn = _draw_cards(s, ps, 2)
        s.event_log.append(RegroupDrawn(player_id=ps.player_id, count=drawn))
        get_bus().fire(s, s.event_log[-1])
    for ps in s.players:
        ps.regroup_done = False
    s.active_player_index = s.initiative_holder
    # "At the start of the regroup phase, defeat it" — units played by Sneak
    # Attack SOR_219 (and any future effect threading defeat_at_regroup).  Swept
    # before the "regroup starts" triggers below; the active player is already the
    # initiative holder so any WhenDefeated trigger's after_all lands there.
    if not s.is_terminal():
        for ps in s.players:
            for ci in list(ps.ground_arena) + list(ps.space_arena):
                if ci.defeat_at_regroup and _find_in_arenas(ps, ci.instance_id) is not None:
                    _defeat_unit(s, ps, ci)
    # "At the start of the regroup phase, defeat that upgrade" — a Shield token
    # granted by Jetpack SHD_225, or a real Item upgrade rented out of the discard by
    # Salvaged Materials LAW_245 (both flagged ``defeat_at_regroup`` on the attached
    # instance).  ⚠️ The two dispose differently: a TOKEN ceases to exist and is
    # simply detached, but a real card MUST go to its owner's discard pile or it
    # would leave the game and break card conservation.  Runs after the unit sweep;
    # an upgrade whose host already left play went with its host.
    if not s.is_terminal():
        from swu.cards.models import TokenUpgrade
        for ps in s.players:
            for host in list(ps.ground_arena) + list(ps.space_arena):
                doomed = [up for up in host.attached_upgrades
                          if getattr(up, "defeat_at_regroup", False)]
                if not doomed:
                    continue
                host.attached_upgrades = [
                    up for up in host.attached_upgrades if up not in doomed]
                for up in doomed:
                    if isinstance(up.card_def, TokenUpgrade):
                        continue
                    s.event_log.append(UpgradeDetached(
                        upgrade_instance_id=up.instance_id,
                        upgrade_name=up.card_def.display_name,
                        former_host_name=host.card_def.display_name,
                        owner_id=up.owner_id,
                    ))
                    up.defeat_at_regroup = False
                    up.zone = Zone.DISCARD
                    s.player_by_id(up.owner_id).discard.append(up)
    # "At the start of the next regroup phase, return that unit to its owner's
    # hand" — units taken with Commandeer JTL_235 (and any future effect threading
    # return_to_owner_hand_at_regroup).  _apply_return_to_hand sends the card to
    # its OWNER's hand regardless of who currently controls it, so a commandeered
    # unit goes home.  Swept alongside the defeat sweep; the flag is cleared by the
    # relocation (a card out of an arena no longer carries it).
    if not s.is_terminal():
        from swu.abilities.resolver import _apply_return_to_hand
        for ps in s.players:
            for ci in list(ps.ground_arena) + list(ps.space_arena):
                if ci.return_to_owner_hand_at_regroup and _find_in_arenas(ps, ci.instance_id) is not None:
                    ci.return_to_owner_hand_at_regroup = False
                    _apply_return_to_hand(s, ci.instance_id)
    # "At the start of the regroup phase, put that unit on the bottom of your deck (if
    # it is still in play)" — a unit lent by Maz Kanata LAW_74's search-and-play.  The
    # deck-bound sibling of the hand-return sweep just above; ``_apply_put_on_deck`` is
    # a RELOCATION, so — as LAW_74's printed rules note requires — the unit's "When
    # Defeated" abilities do not fire.  It also clears the flag as it goes.
    if not s.is_terminal():
        for ps in list(s.players):
            for ci in list(ps.ground_arena) + list(ps.space_arena):
                if ci.bottom_at_regroup and _find_in_arenas(ps, ci.instance_id) is not None:
                    _apply_put_on_deck(s, ci.instance_id, to_top=False)
    # "At the start of the regroup phase, its owner takes control of it" — units taken
    # with Change of Heart SOR_224 (return_control_to_owner_at_regroup).  Unlike the
    # hand-return above, control simply reverts: change_control relocates the unit to
    # its OWNER's arena (control is implicit arena occupancy).  Cleared by the move
    # (change_control re-homes the instance; the old carrier no longer holds it).
    if not s.is_terminal():
        for ps in list(s.players):
            for ci in list(ps.ground_arena) + list(ps.space_arena):
                if ci.return_control_to_owner_at_regroup and _find_in_arenas(ps, ci.instance_id) is not None:
                    ci.return_control_to_owner_at_regroup = False
                    if ci.owner_id != ps.player_id:
                        change_control(s, ci, ci.owner_id)
    # "At the start of the regroup phase, discard a card from your hand" — scheduled
    # per-attack by Zorii Bliss SHD_203 (``discard_from_hand_at_regroup`` counter).
    # The unit's CONTROLLER discards that many cards (first-card simplification, the
    # DiscardFromHand convention); the counter is then cleared.  Skipped for a unit
    # that has left play by regroup (the per-instance delayed-flag convention).
    if not s.is_terminal():
        for ps in list(s.players):
            for ci in list(ps.ground_arena) + list(ps.space_arena):
                n = getattr(ci, "discard_from_hand_at_regroup", 0)
                if n and _find_in_arenas(ps, ci.instance_id) is not None:
                    ci.discard_from_hand_at_regroup = 0
                    for _ in range(n):
                        if not ps.hand:
                            break
                        card = ps.hand.pop(0)
                        card.zone = Zone.DISCARD
                        card.face_down = False
                        ps.discard.append(card)
                        note_hand_or_deck_discard(s, card)
                        record_hand_discard(s, ps.player_id)
    # "When the regroup phase starts" triggers (Contracted Hunter JTL_216:
    # "Defeat this unit").  Fire after the regroup draws and after the active
    # player is set to the initiative holder, so any inline self-defeat lands on a
    # settled regroup state; after_all_player_idx returns control to the
    # initiative holder for the resource step.  Skipped on a terminal state (an
    # empty-deck regroup draw could have ended the game).
    if not s.is_terminal():
        from swu.abilities.resolver import fire_triggered_abilities
        regroup_evt = PhaseChanged(new_phase="REGROUP", round_number=s.round_number)
        fire_triggered_abilities(s, regroup_evt, after_all_player_idx=s.initiative_holder)


def _check_regroup_complete(s: GameState) -> None:
    if all(ps.regroup_done for ps in s.players):
        _end_regroup(s)
    else:
        other = 1 - s.active_player_index
        if not s.players[other].regroup_done:
            s.active_player_index = other


def _extra_regroup_active(s: GameState) -> bool:
    """True if any in-play unit carries the ``ExtraRegroupPhase`` marker (Max Rebo
    LAW_72: "There is an additional regroup phase after the first regroup phase each
    round").  Read only at the regroup-rollover site; a no-op for the overwhelming
    majority of boards (no such marker).  It is a static condition, not additive —
    any number of Max Rebos still yields exactly one extra regroup (the caller's
    ``regroup_count_this_round < 2`` cap)."""
    from swu.abilities.registry import get_abilities, ExtraRegroupPhase
    for ps in s.players:
        for ci in ps.ground_arena + ps.space_arena:
            sc = getattr(ci.card_def, "set_code", None) or ""
            cn = getattr(ci.card_def, "card_number", None) or ""
            if not sc or not cn:
                continue
            for spec in get_abilities(sc, cn):
                if isinstance(spec, ExtraRegroupPhase):
                    return True
    return False


def _ready_all_cards(s: GameState) -> None:
    """The regroup ready step: ready every card (and attached upgrade) that is not
    kept exhausted by a restriction.  Runs once per regroup phase — so with Max
    Rebo's extra regroup it runs twice, which is why ``cannot_ready_this_round`` is
    SKIPPED but NOT cleared here (a unit kept tapped "this round" must stay tapped
    through BOTH regroups); that flag and phase-granted bounties are cleared at the
    round rollover (``_regroup_rollover``)."""
    for ps in s.players:
        for zone_list in (ps.resources, ps.ground_arena, ps.space_arena, ps.base_zone):
            for ci in zone_list:
                # No Good to Me Dead SOR_186: a unit that "can't ready this round
                # (including during the regroup phase)" stays exhausted through every
                # regroup this round.  Skip it here (the flag is cleared at rollover
                # so it readies normally next round).
                if ci.cannot_ready_this_round:
                    continue
                # Leia Organa LOF_98: "While this unit is in the space arena, she
                # can't ready" — a persistent ReadyRestriction, re-evaluated every
                # regroup (leaving the space arena lifts it), so DON'T clear it.
                if _ready_forbidden(s, ci):
                    continue
                note_unit_readied(s, ci)
                ci.exhausted = False
        # Ready attached upgrades too — a leader deployed as an upgrade (Boba Fett
        # JTL_9) carries a meaningful exhaust state (its "you may exhaust this
        # leader" ability) and must re-ready each round like any other card.
        for ci in ps.ground_arena + ps.space_arena:
            for upg in ci.attached_upgrades:
                upg.exhausted = False
    s.event_log.append(AllCardsReadied(round_number=s.round_number))


def _regroup_rollover(s: GameState) -> None:
    """The true round boundary: end the final regroup, roll into the next round's
    ACTION phase.  Expires round-scoped state (this_round modifiers, round/phase
    GameMemory), clears the ``cannot_ready_this_round`` flags and phase-granted
    bounties that ``_ready_all_cards`` deliberately left alone, resets the
    regroup counter, and advances the round.  With no Max Rebo in play this runs
    immediately after the single ready step, so the net behaviour is identical to
    the old monolithic ``_end_regroup``."""
    for ps in s.players:
        for zone_list in (ps.resources, ps.ground_arena, ps.space_arena, ps.base_zone):
            for ci in zone_list:
                ci.cannot_ready_this_round = False
        # Phase-granted bounties (The Client SHD_31) last only "for this phase";
        # clear them at the round rollover (bounding any lingering grant to the
        # round in which it was given, no combat happens in REGROUP).
        for ci in ps.ground_arena + ps.space_arena:
            if ci.granted_bounties:
                ci.granted_bounties.clear()
            # Ability suppression (Mind Trick LOF_202) lasts only "for this phase";
            # lift it at the round rollover (the granted_bounties shape).
            ci.abilities_suppressed = False
    # Phase 3: expire round-scoped modifiers and clear round memory
    _expire_modifiers(s, "this_round")
    s.game_memory.clear_round()
    s.game_memory.clear_phase()
    s.regroup_count_this_round = 0
    s.round_number += 1
    s.phase = Phase.ACTION
    s.active_player_index = s.initiative_holder
    s.passed_players = set()
    s.initiative_claimed_this_round = False
    action_evt = PhaseChanged(new_phase="ACTION", round_number=s.round_number)
    s.event_log.append(action_evt)
    s.event_log.append(RoundStarted(
        round_number=s.round_number,
        initiative_holder_id=s.players[s.initiative_holder].player_id,
    ))
    get_bus().fire(s, s.event_log[-1])
    _fire_scheduled_action_phase_effects(s)
    _fire_action_phase_start_triggers(s, action_evt)


def _end_regroup(s: GameState) -> None:
    _ready_all_cards(s)
    # Max Rebo LAW_72: "There is an additional regroup phase after the first regroup
    # phase each round."  After the FIRST regroup's ready step, re-enter a second
    # regroup (a fresh draw-2 + resource + ready) instead of rolling over; the
    # second regroup then rolls over normally.  The static marker is not additive,
    # so the < 2 cap yields exactly one extra regroup.  Skipped when the deck-out
    # draws already ended the game.
    if (not s.is_terminal()
            and s.regroup_count_this_round < 2
            and _extra_regroup_active(s)):
        _enter_regroup(s)
        return
    _regroup_rollover(s)
