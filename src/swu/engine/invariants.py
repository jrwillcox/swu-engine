"""
Invariant checker for the SWU game engine.

Call ``check(state, ctx)`` after every ``apply()`` in soak/campaign mode.
The *ctx* object is a ``CheckContext`` instance created once per game.
Toggle off by setting ``INVARIANTS_ENABLED = False`` or by not calling this.

Checks performed
----------------
1. Card conservation — same set of instance_ids from game start (by identity,
   not count); no duplicates across zones.
2. Damage ≥ 0 on all cards; no unit in an arena with damage ≥ effective HP.
2b. Zone-tag consistency (each ci.zone matches the list it's in; covers resource
   placement) and exhaust sanity (no exhausted cards in DECK/HAND).
3. Tokens (TokenUpgrade) only exist as attached_upgrades on live hosts;
   never in any zone list directly.
4. Decision stack: only known kinds; deciding_player_id is a real player;
   stack is empty between top-level actions (after non-decision apply()).
5. Modifier durations are valid strings.
5b. Modifier expiry (semantic): no 'this_attack' modifier in a settled state,
   no 'this_round' modifier surviving a round rollover. Catches stale modifiers
   that silently corrupt compute_power/has_keyword.
5c. Phase-scoped GameMemory (units_played_this_phase, villainy_players_this_phase)
   empty immediately after a round rollover.
5d. Every attached upgrade carries the same zone tag as its host unit.
5e. Pass/initiative consistency: passed_players holds valid indices; no settled
   ACTION state with both players passed; active player has not already passed.
6. Initiative holder is a valid player index; phase fields are consistent.
7. legal_actions() is non-empty while the game is live.
7b. Terminal quiescence (semantic): a terminal state offers zero legal actions
   (the engine loop must stop on a win, not play past it).
8. Hidden-information leak: view_for(p) JSON must not expose opponent hand/deck
   card identities (string scan for "card_id": <real_id>).
9. Periodic (every N actions) JSON round-trip: from_json(to_json(state)) must
   re-serialise identically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swu.engine.state import GameState

# The oracle sits above the whole engine — nothing under ``swu.engine.actions``
# imports this module — so it may depend on both the bottom of that package
# (``stats``) and the top of it (``api.legal_actions``) at module scope.
from swu.engine.actions.stats import compute_hp
from swu.engine.actions.api import legal_actions

_KNOWN_DECISION_KINDS = frozenset({
    "ambush", "exploit", "test",
    "trigger_option", "resolve_effects", "use_ability", "pre_attack",
    "granted_attack", "play_from_hand", "play_event_from_hand", "play_via_smuggle",
    "play_via_piloting",
    "opponent_ready",
    "distribute_damage", "deck_search", "peek_top", "choose_number",
    "modal", "say_no", "repeated_modal", "sacrifice_resource",
    "opponent_chooses_target", "reveal_top", "select_token",
    "return_from_discard", "move_upgrade", "plot", "discard_unit_damage",
    "cull_for_damage",
    "discard_for_search", "reveal_play_credit", "look_hand",
    "each_player_defeats", "capture_or_ready", "bottom_from_hand",
    "resource_from_hand",
    "may_discard", "exhaust_for_base_damage", "recur_and_buff",
    "exhaust_combined_cost", "capture_combined_hp", "rescue_guarded",
    "pay_resources_for_tokens", "use_force",
    "per_exploit_damage",
    "assign_indirect_damage", "select_damage",
    "resolve_unique", "choose_two_modal", "owner_may_replay",
    "disclose", "put_on_deck", "regroup_upkeep", "pilot_self_attach",
    "choose_units_sacrifice_rest", "play_upgrade_from_hand",
    "name_a_card", "combat_damage_prevention", "ability_damage_prevention",
    "pay_or_exhaust", "reveal_cost_damage", "opponent_split_bounce",
    "bottom_from_discard", "discard_excess_from_hand", "name_and_discard",
    "pay_and_steal_upgrade", "multi_capture_pairing", "play_captured_card",
    "combined_power_play",
    "play_resource_units", "reveal_cull_draw",
})

_VALID_DURATIONS = frozenset({"permanent", "this_phase", "this_attack", "this_round"})

SERIALIZATION_CHECK_INTERVAL = 50  # check round-trip every N actions


@dataclass
class CheckContext:
    """Per-game context for invariant checks."""
    # player_id -> frozenset of instance_ids present at game start
    initial_card_ids: dict[str, frozenset]
    action_count: int = 0
    # Boundary-tracking state for the "this_round" modifier-expiry check.
    prev_round: int = 1
    prev_this_round_mod_ids: frozenset = frozenset()

    @staticmethod
    def from_state(state: "GameState") -> "CheckContext":
        ids: dict[str, frozenset] = {}
        for ps in state.players:
            pid = ps.player_id
            instances = state.all_instances_for_player(pid)
            ids[pid] = frozenset(ci.instance_id for ci in instances)
        return CheckContext(
            initial_card_ids=ids,
            prev_round=getattr(state, "round_number", 1),
        )


def check(state: "GameState", ctx: CheckContext) -> None:
    """Run all invariant checks.  Raises AssertionError on first violation."""
    ctx.action_count += 1
    _check_conservation(state, ctx)
    _check_damage(state, ctx)
    _check_zone_consistency(state, ctx)
    _check_tokens(state, ctx)
    _check_decision_stack(state, ctx)
    _check_modifiers(state, ctx)
    _check_phase_memory(state, ctx)     # reads ctx.prev_round (before update)
    _check_modifier_expiry(state, ctx)  # updates ctx.prev_round
    _check_upgrade_zone(state, ctx)
    _check_pass_consistency(state, ctx)
    _check_game_fields(state, ctx)
    _check_legal_actions(state, ctx)
    _check_terminal_quiescence(state, ctx)
    _check_hidden_info(state, ctx)
    if ctx.action_count % SERIALIZATION_CHECK_INTERVAL == 0:
        _check_serialization_roundtrip(state, ctx)


# ── individual checks ─────────────────────────────────────────────────────────

def _check_conservation(state: "GameState", ctx: CheckContext) -> None:

    for ps in state.players:
        pid = ps.player_id
        instances = state.all_instances_for_player(pid)
        current_ids = [ci.instance_id for ci in instances]

        # No duplicates
        seen: set[str] = set()
        for iid in current_ids:
            assert iid not in seen, (
                f"[invariant] Duplicate instance_id {iid!r} for {pid} "
                f"at action {ctx.action_count}"
            )
            seen.add(iid)

        # Same set as at game start
        current_set = frozenset(current_ids)
        expected = ctx.initial_card_ids[pid]
        lost = expected - current_set
        gained = current_set - expected
        assert not lost and not gained, (
            f"[invariant] Card conservation violated for {pid} "
            f"at action {ctx.action_count}: lost={lost}, gained={gained}"
        )


def _check_damage(state: "GameState", ctx: CheckContext) -> None:
    for ps in state.players:
        for zone_list in (
            ps.deck, ps.hand, ps.discard, ps.resources,
            ps.ground_arena, ps.space_arena, ps.base_zone,
            ps.capture_pile, ps.play_buffer,
        ):
            for ci in zone_list:
                assert ci.damage >= 0, (
                    f"[invariant] Negative damage on {ci.card_def.display_name} "
                    f"({ci.instance_id}) at action {ctx.action_count}"
                )
                for upg in ci.attached_upgrades:
                    assert upg.damage >= 0, (
                        f"[invariant] Negative damage on upgrade "
                        f"{upg.card_def.display_name} at action {ctx.action_count}"
                    )

    # No unit in an arena with damage ≥ effective HP (unless game just ended).
    # Use compute_hp() not ci.effective_hp() — the latter ignores ConstantAbility
    # HP bonuses and Modifier records, which can diverge from the engine's view.
    if not state.is_terminal():
        for ps in state.players:
            for ci in ps.ground_arena + ps.space_arena:
                if ci.damage >= compute_hp(state, ci):
                    # Only hard-fail on a settled state (no pending decisions).
                    if not state.pending_decisions:
                        raise AssertionError(
                            f"[invariant] Defeated unit {ci.card_def.display_name} "
                            f"({ci.instance_id}) still in arena at action "
                            f"{ctx.action_count} (damage={ci.damage}, "
                            f"compute_hp={compute_hp(state, ci)})"
                        )


def _check_zone_consistency(state: "GameState", ctx: CheckContext) -> None:
    """Structural sanity on card placement.

    1. Zone-tag consistency: every CardInstance's ``zone`` field matches the
       zone list it actually lives in.  A mismatch means a card was moved
       between lists without retagging — which would corrupt serialisation,
       view redaction (hidden-info), and target gathering.  This covers
       resource placement (cards in ``resources`` are tagged RESOURCES) as a
       special case of the general check.
    2. Exhaust sanity: cards in DECK and HAND are never exhausted.  Exhaustion
       only applies to cards in play and to resources; a stale exhausted flag
       in deck/hand signals a card that changed zones without its state being
       reset.
    """
    from swu.engine.state import Zone

    deck_hand = {Zone.DECK, Zone.HAND}
    for ps in state.players:
        for zone in (
            Zone.DECK, Zone.HAND, Zone.DISCARD, Zone.RESOURCES,
            Zone.GROUND_ARENA, Zone.SPACE_ARENA, Zone.BASE_ZONE,
            Zone.CAPTURE_PILE, Zone.PLAY_BUFFER, Zone.CREDITS,
        ):
            for ci in ps.zone_list(zone):
                assert ci.zone == zone, (
                    f"[invariant] Zone-tag mismatch for {ci.card_def.display_name} "
                    f"({ci.instance_id}): tagged {ci.zone.name} but found in "
                    f"{zone.name} for {ps.player_id} at action {ctx.action_count}"
                )
                if zone in deck_hand:
                    assert not ci.exhausted, (
                        f"[invariant] Exhausted card {ci.card_def.display_name} "
                        f"({ci.instance_id}) in {zone.name} for {ps.player_id} "
                        f"at action {ctx.action_count}"
                    )


def _check_tokens(state: "GameState", ctx: CheckContext) -> None:
    from swu.cards.models import TokenUpgrade

    for ps in state.players:
        for zone_list in (
            ps.deck, ps.hand, ps.discard, ps.resources,
            ps.ground_arena, ps.space_arena, ps.base_zone,
            ps.capture_pile, ps.play_buffer,
        ):
            for ci in zone_list:
                assert not isinstance(ci.card_def, TokenUpgrade), (
                    f"[invariant] Detached token {ci.card_def.name} found in "
                    f"{ci.zone} for {ps.player_id} at action {ctx.action_count}"
                )
                # Tokens should only appear as attached_upgrades on arena units
                for upg in ci.attached_upgrades:
                    if isinstance(upg.card_def, TokenUpgrade):
                        # The host must itself be in an arena zone
                        assert ci.zone.name in ("GROUND_ARENA", "SPACE_ARENA",
                                                "BASE_ZONE", "PLAY_BUFFER"), (
                            f"[invariant] Token {upg.card_def.name} attached to "
                            f"non-arena card {ci.card_def.display_name} "
                            f"(zone={ci.zone}) at action {ctx.action_count}"
                        )


def _check_decision_stack(state: "GameState", ctx: CheckContext) -> None:
    player_ids = {ps.player_id for ps in state.players}
    for dec in state.pending_decisions:
        assert dec.kind in _KNOWN_DECISION_KINDS, (
            f"[invariant] Unknown decision kind {dec.kind!r} at action {ctx.action_count}"
        )
        assert dec.deciding_player_id in player_ids, (
            f"[invariant] Decision deciding_player_id {dec.deciding_player_id!r} "
            f"is not a player at action {ctx.action_count}"
        )


def _check_modifiers(state: "GameState", ctx: CheckContext) -> None:
    for mod in state.modifiers:
        assert mod.duration in _VALID_DURATIONS, (
            f"[invariant] Modifier with invalid duration {mod.duration!r} "
            f"at action {ctx.action_count}"
        )


def _check_game_fields(state: "GameState", ctx: CheckContext) -> None:
    n = len(state.players)
    assert 0 <= state.initiative_holder < n, (
        f"[invariant] initiative_holder={state.initiative_holder} out of range "
        f"at action {ctx.action_count}"
    )
    assert 0 <= state.active_player_index < n, (
        f"[invariant] active_player_index={state.active_player_index} out of range "
        f"at action {ctx.action_count}"
    )
    assert state.round_number >= 1, (
        f"[invariant] round_number={state.round_number} < 1 at action {ctx.action_count}"
    )


def _check_legal_actions(state: "GameState", ctx: CheckContext) -> None:
    if state.is_terminal():
        return
    acts = legal_actions(state)
    assert acts, (
        f"[invariant] legal_actions() empty at action {ctx.action_count}, "
        f"phase={state.phase}"
    )


def _check_hidden_info(state: "GameState", ctx: CheckContext) -> None:
    """Verify view_for(p) doesn't leak opponent hand/deck card identities.

    We check by *instance_id*, not card_id, because multiple copies of the
    same non-unique card (same card_id) can legitimately co-exist — one in the
    arena (visible) and another in the hand/deck (hidden).  Scanning for the
    numeric card_id would produce false positives in that case.

    The correct signal: the instance_id of a hidden card (in opp.hand or
    opp.deck) must not appear anywhere in the view JSON.  The view omits
    opponent hand entirely (returns []) and represents deck as a count only;
    any instance_id leak would mean the view builder exposed something it
    should not have.

    EXEMPTION — *publicly revealed* cards.  A card a "Reveal the top card of a
    deck" effect has turned face-up (Vermillion LAW_215's ``reveal_play_credit``
    decision) is legitimately public info even while it still sits in its deck,
    so its instance_id appearing in the deciding player's view is correct, not a
    leak.  Such ids are recorded as ``revealed_id`` on the pending decision; we
    exclude them.  (The ``reveal_top`` decision is a *private* own-deck look,
    redacted from the opponent, so it never reaches here.)
    """
    revealed_public_ids = {
        dec.context.get("revealed_id")
        for dec in state.pending_decisions
        if dec.kind == "reveal_play_credit" and dec.context.get("revealed_id")
    }
    # EXEMPTION — a FOREIGN deck_search ("look at the top N cards of the DEFENDING
    # player's deck", Sabé SEC_17).  The decider is looking at someone else's deck
    # cards by the card's own text, so those candidate ids appearing in the
    # decider's private decision context is the effect working, not a leak.  Only a
    # search whose deck owner differs from the decider is exempted.
    for dec in state.pending_decisions:
        if (dec.kind == "deck_search"
                and dec.context.get("controller_id") != dec.deciding_player_id):
            revealed_public_ids |= set(dec.context.get("candidate_ids") or ())
    for ps in state.players:
        pid = ps.player_id
        opp = state.players[1 - state.player_index(pid)]
        view = state.view_for(pid)
        view_json = view.to_json()

        # Opponent hand and deck are fully hidden — their instance_ids must not
        # appear anywhere in the view JSON.
        hidden_cards = list(opp.hand) + list(opp.deck)
        for ci in hidden_cards:
            iid = ci.instance_id
            if iid in revealed_public_ids:
                continue  # publicly revealed (face-up) — not hidden info

            # Search for the quoted string value (e.g. '"P0_2"') so that shorter
            # ids like "P0_2" don't falsely match inside longer ids like "P0_27".
            quoted = f'"{iid}"'
            assert quoted not in view_json, (
                f"[invariant] Hidden-info leak: instance_id {iid!r} of opponent "
                f"hand/deck card {ci.card_def.display_name!r} visible in "
                f"view_for({pid!r}) at action {ctx.action_count}"
            )


def _check_modifier_expiry(state: "GameState", ctx: CheckContext) -> None:
    """Duration-scoped modifiers must be cleaned up at their scope boundary.

    These are *semantic* checks: a stale modifier silently corrupts
    ``compute_power``/``has_keyword`` without ever tripping a structural
    invariant.

    - ``this_attack``: an attack resolves entirely within one ``apply()`` call,
      so once control returns (no pending decisions) no ``this_attack`` modifier
      may remain.  While a ``pre_attack`` decision is open the attack is still in
      progress, so we skip the check then.
    - ``this_round``: expired at round rollover (``_expire_modifiers("this_round")``).
      Tracked across the round boundary: when ``round_number`` increases, none of
      the modifiers that carried ``this_round`` before the rollover may survive.

    - ``this_phase``: expired when the ACTION phase ends (the ACTION->REGROUP
      transition, ``_expire_modifiers("this_phase")`` in ``_enter_regroup``).
      A this_phase modifier legitimately persists across settled states *within*
      an action phase, so it cannot be asserted absent in every settled state
      (unlike this_attack); but it is expired before the round rollover, so —
      like this_round — none may survive into the next round.
    """
    if not state.pending_decisions:
        for mod in state.modifiers:
            assert mod.duration != "this_attack", (
                f"[invariant] Stale 'this_attack' modifier {mod.modifier_id!r} "
                f"persists in settled state at action {ctx.action_count}"
            )

    # this_round boundary tracking.  Read ctx.prev_round here; it is updated at
    # the END of this function so _check_phase_memory (which runs first) sees the
    # same pre-update value.
    cur_round = getattr(state, "round_number", 1)
    cur_this_round = frozenset(
        m.modifier_id for m in state.modifiers if m.duration == "this_round"
    )
    if cur_round > ctx.prev_round:
        survivors = ctx.prev_this_round_mod_ids & cur_this_round
        assert not survivors, (
            f"[invariant] 'this_round' modifier(s) {set(survivors)!r} survived the "
            f"round {ctx.prev_round}->{cur_round} rollover at action {ctx.action_count}"
        )
        # this_phase expires at the ACTION->REGROUP transition, so none may
        # survive into the next round (Tactical Advantage TWI_124 regression).
        phase_survivors = frozenset(
            m.modifier_id for m in state.modifiers if m.duration == "this_phase"
        )
        assert not phase_survivors, (
            f"[invariant] 'this_phase' modifier(s) {set(phase_survivors)!r} survived "
            f"the round {ctx.prev_round}->{cur_round} rollover at action "
            f"{ctx.action_count}"
        )
    ctx.prev_round = cur_round
    ctx.prev_this_round_mod_ids = cur_this_round


def _check_phase_memory(state: "GameState", ctx: CheckContext) -> None:
    """Phase-scoped GameMemory must be empty immediately after a round rollover.

    ``clear_phase()`` empties ``units_played_this_phase`` and clears
    ``villainy_players_this_phase`` at the REGROUP->ACTION rollover (the same
    ``apply()`` that increments ``round_number``).  That rollover plays no card,
    so the first state we observe in the new round must have both cleared.  We
    intentionally check at the round boundary rather than "outside ACTION":
    these fields legitimately persist through REGROUP (they are cleared at the
    start of the next round, not the end of the current one) and are only read
    during the ACTION phase, so a non-ACTION value is not a leak.

    Reads ctx.prev_round WITHOUT updating it (``_check_modifier_expiry`` owns the
    update and runs after this check).
    """
    cur_round = getattr(state, "round_number", 1)
    if cur_round <= ctx.prev_round:
        return
    gm = getattr(state, "game_memory", None)
    if gm is None:
        return
    assert not gm.units_played_this_phase, (
        f"[invariant] units_played_this_phase not cleared at round "
        f"{ctx.prev_round}->{cur_round} rollover at action {ctx.action_count}: "
        f"{sorted(gm.units_played_this_phase)}"
    )
    assert not gm.villainy_players_this_phase, (
        f"[invariant] villainy_players_this_phase not cleared at round "
        f"{ctx.prev_round}->{cur_round} rollover at action {ctx.action_count}: "
        f"{sorted(gm.villainy_players_this_phase)}"
    )


def _check_upgrade_zone(state: "GameState", ctx: CheckContext) -> None:
    """Every attached upgrade must carry the same zone tag as its host unit.

    ``_attach_upgrade`` sets ``upgrade_ci.zone = unit_ci.zone``; if a unit later
    changes arena (or the upgrade is moved) without retagging, target gathering
    and serialisation would see an inconsistent zone.  Tokens are upgrades too
    and are covered by the same rule.
    """
    for ps in state.players:
        for ci in ps.ground_arena + ps.space_arena + ps.base_zone:
            for upg in ci.attached_upgrades:
                assert upg.zone == ci.zone, (
                    f"[invariant] Upgrade {upg.card_def.display_name} "
                    f"({upg.instance_id}) tagged {upg.zone.name} but host "
                    f"{ci.card_def.display_name} is in {ci.zone.name} "
                    f"at action {ctx.action_count}"
                )


def _check_pass_consistency(state: "GameState", ctx: CheckContext) -> None:
    """Pass/initiative bookkeeping must stay consistent.

    - ``passed_players`` only ever holds valid player indices.
    - A settled ACTION-phase state (no pending decisions) never has *both*
      players passed: the phase-end transition runs inside the last passer's
      ``apply()``, so a both-passed ACTION state should never be observable.

    Note: we do NOT assert "the active player has not passed" — the engine may
    legitimately hold ``active_player_index`` on a player who has passed while
    the other player finishes the phase; ``legal_actions``/``apply`` resolve the
    turn correctly from there, so this is internal transient state, not a leak.
    """
    n = len(state.players)
    passed = getattr(state, "passed_players", set())
    for idx in passed:
        assert 0 <= idx < n, (
            f"[invariant] passed_players holds invalid index {idx} "
            f"at action {ctx.action_count}"
        )
    if getattr(state.phase, "name", "") == "ACTION" and not state.pending_decisions:
        assert len(passed) < 2, (
            f"[invariant] Both players passed but still in settled ACTION phase "
            f"at action {ctx.action_count}"
        )


def _check_terminal_quiescence(state: "GameState", ctx: CheckContext) -> None:
    """Once the game is terminal the engine must offer no further actions.

    ``winner`` is derived from base damage, so a terminal state is unambiguous;
    the real risk is the *engine loop* continuing to generate moves past a win.
    A non-empty ``legal_actions`` in a terminal state would let a soak/replay
    play on after the game was decided.
    """
    if not state.is_terminal():
        return
    acts = legal_actions(state)
    assert not acts, (
        f"[invariant] {len(acts)} legal action(s) offered in a terminal state "
        f"(winner={state.winner}) at action {ctx.action_count}"
    )


def _check_serialization_roundtrip(state: "GameState", ctx: CheckContext) -> None:
    """Verify to_json() / from_json() roundtrip produces identical JSON.

    The event_log is intentionally NOT restored by from_json() (CLAUDE.md:
    "not needed for replay; re-run actions instead"), so we exclude it from
    the comparison.
    """
    import json as _json
    from swu.engine.state import GameState

    json1 = state.to_json()
    try:
        state2 = GameState.from_json(json1)
    except Exception as exc:
        raise AssertionError(
            f"[invariant] from_json failed at action {ctx.action_count}: {exc}"
        ) from exc
    json2 = state2.to_json()

    if json1 == json2:
        return  # fast path

    # Parse and compare without the event_log field
    d1 = _json.loads(json1)
    d2 = _json.loads(json2)
    d1.pop("event_log", None)
    d2.pop("event_log", None)
    canon1 = _json.dumps(d1, sort_keys=True)
    canon2 = _json.dumps(d2, sort_keys=True)
    assert canon1 == canon2, (
        f"[invariant] JSON round-trip mismatch (excl. event_log) at action "
        f"{ctx.action_count}; first diff at pos {_first_diff_pos(canon1, canon2)}"
    )


def _first_diff_pos(a: str, b: str) -> int:
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            return i
    return min(len(a), len(b))
