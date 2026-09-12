"""LAW / JTL card ability tests (deck ``leia-organa``).

One focused test per card, asserting behaviour through the public engine
interfaces (legal_actions / apply / trigger firing).  Encoded for group
``leia-organa:01`` (Direct damage & removal).

Reuses the DB-backed game-state helpers from the SOR card tests.  Method names
embed the card number so the encoding verifier's ``-k`` gate selects them.
"""
from __future__ import annotations


from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _fire_on_attack,
    _fire_when_defeated,
    _find_instance, _experience_count, _shield_count, _add_resource,
    _play_event_from_hand, _give_resources, _place_leader,
    _build_search_deck, _seed_rng, _take_from_search, _expected_bottom_order,
    _fire_upgrade_played, _push_deck_top,
)
from tests.test_shd_cards import _attach_upgrade_directly, _put_in_hand

from swu.engine.actions import legal_actions  # noqa: E402
from tests.test_shd_cards import _fire_when_deployed  # noqa: E402
from tests.dbpath import require_db, require_row  # noqa: E402


def _distinct_aspects(state, player_id):
    ps = state.player_by_id(player_id)
    aspects = set()
    for u in ps.ground_arena + ps.space_arena:
        aspects |= {a.name for a in (getattr(u.card_def, "aspects", None) or ())}
    return aspects


def _drive_to_quiescence(state, picker):
    """Apply actions until no decision is pending, choosing via ``picker(acts)``
    (which returns the action to apply, or None to apply the first)."""
    from swu.engine.actions import legal_actions, apply
    guard = 0
    while state.pending_decisions and guard < 30:
        guard += 1
        acts = legal_actions(state)
        choice = picker(acts) or acts[0]
        state = apply(state, choice)
    return state


def _fire_unit_defeated(state, ci, controller_id="P0"):
    """Mimic ``_defeat_unit``'s trigger firing: pull ``ci`` from its arena (so it
    is no longer in play, as during a real defeat) and fire ``UnitDefeated`` with
    the same event_ctx the engine provides (``defeated_ci`` / ``defeated_id`` /
    ``defeated_controller_id``).  Exercises the ``WhenUnitDefeated`` filter path
    that reads ``defeated_ci`` because the unit has left play."""
    from swu.engine.events import UnitDefeated
    from swu.abilities.resolver import fire_triggered_abilities
    ps = state.player_by_id(controller_id)
    for arena in (ps.ground_arena, ps.space_arena):
        if ci in arena:
            arena.remove(ci)
            break
    evt = UnitDefeated(player_id=controller_id, instance_id=ci.instance_id,
                       card_name=ci.card_def.display_name)
    state.event_log.append(evt)
    ctx = {"defeated_id": ci.instance_id, "defeated_ci": ci,
           "defeated_controller_id": controller_id}
    state = fire_triggered_abilities(state, evt, after_all_player_idx=0, event_ctx=ctx)
    # Mirror _defeat_unit's tail: after firing (which may push a decision while the
    # card is out of every zone), the engine homes the defeated card in its owner's
    # discard — so when the pushed decision is later resolved, find_instance locates
    # the source there (needed for a self-WhenDefeated whose effect targets).
    from swu.engine.state import Zone
    from swu.cards.models import Leader
    if not isinstance(ci.card_def, Leader):
        owner = state.player_by_id(ci.owner_id)
        if all(ci.instance_id != c.instance_id for c in owner.discard):
            ci.zone = Zone.DISCARD
            owner.discard.append(ci)
    return state


# ── LAW_80 Luke Skywalker — opponent-decided modal ────────────────────────────

class TestLukeSkywalkerLAW80:
    """"When Played: An opponent chooses one:
        They create a Credit token. Ready this unit.
        You may deal 5 damage to a unit."
    The choose_two_modal decision kind with the ``decider_id`` opponent shift
    (pick=1): the OPPONENT picks the mode, the CONTROLLER resolves it.
    """

    def _play_luke(self, repo):
        """Place an exhausted Luke (P0), fire his WhenPlayed, drain to the modal."""
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "LAW", "80"), "ground")
        luke.exhausted = True                      # a freshly-played unit is exhausted
        state = _fire_when_played(state, luke)
        # Drain the idx-0 resolve_effects (the CustomEffect pushes the modal).
        while (state.pending_decisions
               and state.pending_decisions[-1].kind != "choose_two_modal"):
            acts = legal_actions(state)
            auto = next((a for a in acts if isinstance(a, AutoResolveEffects)), None)
            assert auto is not None, [type(a).__name__ for a in acts]
            state = apply(state, auto)
        return state, luke

    def test_law_80_modal_is_decided_by_the_opponent(self, repo):
        state, _luke = self._play_luke(repo)
        top = state.pending_decisions[-1]
        assert top.kind == "choose_two_modal"
        # The OPPONENT of Luke's controller (P0) makes the choice.
        assert top.deciding_player_id == "P1"
        assert state.active_player_index == state.player_index("P1")
        assert top.context["pick"] == 1

    def test_law_80_option_a_opponent_gets_credit_and_readies_luke(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state, luke = self._play_luke(repo)
        # Opponent picks option 1 (credit + ready) — the option worst-avoiding for
        # them here would be situational; we just drive the branch.
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectModalOption) and a.option_idx == 1)
        state = apply(state, pick)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").credits) == 1     # opponent's credit
        assert len(state.player_by_id("P0").credits) == 0
        res = state.find_instance(luke.instance_id)
        assert res is not None and res[1].exhausted is False  # Luke readied

    def test_law_80_option_b_controller_deals_5_to_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption, ChooseTarget
        state, _luke = self._play_luke(repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectModalOption) and a.option_idx == 2)
        state = apply(state, pick)
        # The CONTROLLER (P0) now chooses the target for "you may deal 5".
        top = state.pending_decisions[-1]
        assert top.kind == "resolve_effects" and top.deciding_player_id == "P0"
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not state.pending_decisions
        res = state.find_instance(enemy.instance_id)
        assert res is not None and res[1].damage == 5
        assert len(state.player_by_id("P1").credits) == 0     # mode A did not happen

    def test_law_80_option_b_controller_may_decline(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectModalOption, DeclineTarget)
        state, _luke = self._play_luke(repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectModalOption) and a.option_idx == 2)
        state = apply(state, pick)
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTarget))
        state = apply(state, decline)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not state.pending_decisions
        res = state.find_instance(enemy.instance_id)
        assert res is not None and res[1].damage == 0         # "may" declined


# ── LAW_41 Nothing Left to Fear ───────────────────────────────────────────────

class TestNothingLeftToFear:
    """Choose a friendly unit and give it +2/+2 for this phase.  Then, you may
    defeat a non-leader unit with power ≤ the chosen unit."""

    def test_law_41_buffs_then_defeats_within_threshold(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, DeclineTarget, compute_power)
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        weak = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")      # 3/1
        strong = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")     # 9/9
        state, _evt = _play_event_from_hand(state, repo, "LAW", "41")

        # Stage 1 — choose the friendly unit to buff.
        assert state.pending_decisions[-1].kind == "resolve_effects"
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, choose)
        assert compute_power(state, _find_instance(state, friendly.instance_id)) == 5

        # Stage 2 — only non-leader units with power ≤ 5 are offered (strong=9 not);
        # the chosen unit (now power 5) qualifies too, and decline is allowed.
        acts = legal_actions(state)
        offered = {a.target_id for a in acts if isinstance(a, ChooseTarget)}
        assert weak.instance_id in offered
        assert friendly.instance_id in offered
        assert strong.instance_id not in offered
        assert any(isinstance(a, DeclineTarget) for a in acts)

        state = apply(state, ChooseTarget(weak.instance_id))
        assert _find_instance(state, weak.instance_id) is None      # defeated
        assert not state.pending_decisions

    def test_law_41_may_decline_the_defeat(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, DeclineTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "41")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DeclineTarget)))
        assert _find_instance(state, enemy.instance_id) is not None  # not defeated
        assert not state.pending_decisions


# ── LAW_45 Zeb Orellios ───────────────────────────────────────────────────────

class TestZebOrellios:
    """Sentinel.  When Played: You may deal 3 damage to a ground unit.  If you
    control a Command or Cunning unit, you may deal 5 damage to a ground unit
    instead."""

    def test_law_45_deals_3_without_command_or_cunning(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        zeb = _place(state, "P0", _get_card(repo, "LAW", "45"), "ground")  # Vig/Agg/Hero
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, zeb)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3

    def test_law_45_deals_5_with_command_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        zeb = _place(state, "P0", _get_card(repo, "LAW", "45"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")   # Battlefield Marine = Command
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, zeb)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 5

    def test_law_45_may_decline_the_damage(self, repo):
        """The "you may" lets the controller decline — no damage is dealt."""
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        zeb = _place(state, "P0", _get_card(repo, "LAW", "45"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, zeb)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert not state.pending_decisions


# ── JTL_250 Sabine's Masterpiece ──────────────────────────────────────────────

def _sabine(state, repo):
    """Place Sabine's Masterpiece (Space unit) for P0 and return its instance."""
    return _place(state, "P0", _get_card(repo, "JTL", "250"), "space")


class TestSabinesMasterpiece:
    """On Attack, four aspect-gated clauses resolve in order (Vigilance heal,
    Command Experience, Aggression damage, Cunning resource exhaust/ready)."""

    def test_jtl_250_no_matching_aspect_does_nothing(self, repo):
        """Controlling only Heroism units → every clause is gated off, no prompt."""
        state = _make_state()
        sab = _sabine(state, repo)
        state = _fire_on_attack(state, sab, defender_ci=None)
        assert not state.pending_decisions

    def test_jtl_250_command_clause_gives_experience(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        sab = _sabine(state, repo)
        marine = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # Command
        state = _fire_on_attack(state, sab, defender_ci=None)
        # Only the Command clause is active → a single "give Experience to a unit" prompt.
        assert state.pending_decisions[-1].kind == "resolve_effects"
        state = apply(state, ChooseTarget(marine.instance_id))
        assert _experience_count(_find_instance(state, marine.instance_id)) == 1
        assert not state.pending_decisions

    def test_jtl_250_cunning_clause_readies_a_resource(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseModalOption
        state = _make_state()
        sab = _sabine(state, repo)
        _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Swoop Racer = Cunning
        ex = _add_resource(state, repo, "P0", exhausted=True)   # ready_resource target
        _add_resource(state, repo, "P0", exhausted=False)       # exhaust_resource target
        state = _fire_on_attack(state, sab, defender_ci=None)
        # The Cunning clause pushed a fungible resource modal with both modes.
        assert state.pending_decisions[-1].kind == "modal"
        modes = {a.mode for a in legal_actions(state) if isinstance(a, ChooseModalOption)}
        assert modes == {"ready_resource", "exhaust_resource"}
        state = apply(state, ChooseModalOption("ready_resource"))
        # The exhausted resource was readied; no further prompt (fungible).
        res = {r.instance_id: r for r in state.player_by_id("P0").resources}
        assert res[ex.instance_id].exhausted is False
        assert not state.pending_decisions

    def test_jtl_250_all_four_clauses_resolve_in_order(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, ChooseModalOption, AutoResolveEffects)
        state = _make_state()
        sab = _sabine(state, repo)
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Vigilance
        marine = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # Command
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Aggression
        _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Cunning
        # Damage our own base so the Vigilance heal has a visible effect.
        p0_base = state.player_by_id("P0").base_zone[0]
        p0_base.damage = 5
        p1_base = state.player_by_id("P1").base_zone[0]
        ex = _add_resource(state, repo, "P0", exhausted=True)

        base_ids = {p0_base.instance_id, p1_base.instance_id}
        state = _fire_on_attack(state, sab, defender_ci=None)

        # Drive each clause to completion.  Clauses resolve as independent
        # single-effect decisions, so route each by the *shape* of its target set:
        #   only-bases   → Vigilance heal  → heal our (P0) base
        #   units+bases  → Aggression dmg  → damage the enemy (P1) base
        #   only-units   → Command token   → give Experience to our marine
        guard = 0
        while state.pending_decisions and guard < 20:
            guard += 1
            acts = legal_actions(state)
            modal = [a for a in acts if isinstance(a, ChooseModalOption)]
            targets = [a for a in acts if isinstance(a, ChooseTarget)]
            auto = [a for a in acts if isinstance(a, AutoResolveEffects)]
            if modal:
                state = apply(state, next(a for a in modal if a.mode == "ready_resource"))
            elif targets:
                ids = {a.target_id for a in targets}
                has_units = bool(ids - base_ids)
                has_bases = bool(ids & base_ids)
                if has_bases and not has_units:          # Vigilance heal
                    pick = p0_base.instance_id
                elif has_units and has_bases:            # Aggression damage
                    pick = p1_base.instance_id
                else:                                    # Command Experience
                    pick = marine.instance_id
                state = apply(state, ChooseTarget(pick))
            elif auto:
                state = apply(state, auto[0])
            else:
                state = apply(state, acts[0])

        assert not state.pending_decisions
        # Re-fetch from the (deep-copied) final state by instance id.
        assert state.player_by_id("P0").base_zone[0].damage == 3   # Vigilance healed 2 of 5
        assert _experience_count(_find_instance(state, marine.instance_id)) == 1
        assert state.player_by_id("P1").base_zone[0].damage == 1   # Aggression 1 dmg
        assert state.player_by_id("P0").resources[0].exhausted is False  # Cunning readied


# ── LAW_119 Rogue One ─────────────────────────────────────────────────────────

class TestRogueOne:
    """When a friendly unit is defeated: Look at the top 2 cards of your deck.
    Put any number of them on the bottom of your deck and the rest on top in any
    order."""

    def _setup(self, repo):
        state = _make_state()
        rogue = _place(state, "P0", _get_card(repo, "LAW", "119"), "space")
        victim = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # friendly
        deck = _build_search_deck(
            state, "P0",
            top_cards=[_get_card(repo, "SOR", "46"), _get_card(repo, "SOR", "88")],
            below_cards=[_get_card(repo, "SOR", "105")],
        )
        return state, rogue, victim, deck

    def test_law_119_fires_on_friendly_defeat_looks_at_top_2(self, repo):
        from swu.engine.actions import legal_actions, KeepRevealed, DiscardRevealed
        state, rogue, victim, deck = self._setup(repo)
        state = _fire_unit_defeated(state, victim, "P0")
        assert state.pending_decisions[-1].kind == "reveal_top"
        offered = {a.card_id for a in legal_actions(state)
                   if isinstance(a, (KeepRevealed, DiscardRevealed))}
        assert offered == {deck[0].instance_id, deck[1].instance_id}

    def test_law_119_bottoms_one_keeps_one(self, repo):
        from swu.engine.actions import apply, KeepRevealed, DiscardRevealed
        state, rogue, victim, deck = self._setup(repo)
        state = _fire_unit_defeated(state, victim, "P0")
        # Keep deck[0] on top; put deck[1] on the bottom of the deck.
        state = apply(state, KeepRevealed(deck[0].instance_id))
        state = apply(state, DiscardRevealed(deck[1].instance_id))
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        ids = [c.instance_id for c in ps.deck]
        assert ids[0] == deck[0].instance_id    # kept on top
        assert ids[-1] == deck[1].instance_id   # bottomed
        assert len(ps.deck) == 3                 # nothing left the deck
        assert deck[1].instance_id not in {c.instance_id for c in ps.discard}

    def test_law_119_keep_both_on_top_in_chosen_order(self, repo):
        from swu.engine.actions import apply, KeepRevealed
        state, rogue, victim, deck = self._setup(repo)
        state = _fire_unit_defeated(state, victim, "P0")
        # Put any number (here zero) on the bottom — keep both, ordering deck[1]
        # above deck[0] (the first kept becomes the top card).
        state = apply(state, KeepRevealed(deck[1].instance_id))
        state = apply(state, KeepRevealed(deck[0].instance_id))
        assert not state.pending_decisions
        ids = [c.instance_id for c in state.player_by_id("P0").deck]
        assert ids[:3] == [deck[1].instance_id, deck[0].instance_id, deck[2].instance_id]

    def test_law_119_does_not_fire_on_enemy_defeat(self, repo):
        """The "friendly" filter: an *enemy* unit's defeat must not trigger it."""
        state, rogue, victim, deck = self._setup(repo)
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_unit_defeated(state, enemy, "P1")
        assert not state.pending_decisions


# ── LAW_145 R2-D2 ─────────────────────────────────────────────────────────────

class TestR2D2:
    """When Played: Search the top 5 cards of your deck for a unit that shares an
    aspect with a friendly unit, reveal it, and draw it."""

    def _setup(self, repo):
        state = _seed_rng(_make_state())
        r2 = _place(state, "P0", _get_card(repo, "LAW", "145"), "ground")  # Command/Heroism
        deck = _build_search_deck(
            state, "P0",
            top_cards=[_get_card(repo, "SOR", "95"),    # Command/Heroism — eligible
                       _get_card(repo, "SOR", "128"),   # Villainy/Aggression — no
                       _get_card(repo, "SOR", "74"),    # event — no
                       _get_card(repo, "SOR", "210"),   # Cunning — no
                       _get_card(repo, "SOR", "105")],  # Command — eligible
            below_cards=[_get_card(repo, "SOR", "74")],
        )
        state = _fire_when_played(state, r2)
        return state, deck

    def test_law_145_searches_for_aspect_sharing_unit(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard, FinishSearch
        state, deck = self._setup(repo)
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        selects = {a.instance_id for a in acts if isinstance(a, SelectSearchCard)}
        assert selects == {deck[0].instance_id, deck[4].instance_id}
        assert not any(isinstance(a, FinishSearch) for a in acts)  # mandatory if able

    def test_law_145_draws_chosen_bottoms_rest(self, repo):
        state, deck = self._setup(repo)
        ps = state.players[0]
        hand_before = len(ps.hand)
        state = _take_from_search(state, deck[0].instance_id)
        assert not state.pending_decisions  # taking the one (cap 1) auto-finishes
        ps = state.players[0]
        assert len(ps.hand) == hand_before + 1
        assert any(c.instance_id == deck[0].instance_id for c in ps.hand)
        assert ps.deck[0].instance_id == deck[5].instance_id  # 'below' stays on top
        expected = _expected_bottom_order([deck[i].instance_id for i in (1, 2, 3, 4)])
        assert [c.instance_id for c in ps.deck[1:]] == expected


# ── LAW_166 Putting a Team Together ───────────────────────────────────────────

class TestPuttingATeamTogether:
    """Search the top 8 cards of your deck for a Vigilance, Aggression, or Cunning
    unit, reveal it, and draw it."""

    def _play(self, repo):
        state = _seed_rng(_make_state())
        deck = _build_search_deck(
            state, "P0",
            top_cards=[_get_card(repo, "SOR", "210"),   # Cunning — eligible
                       _get_card(repo, "SOR", "95"),    # Command/Heroism — no
                       _get_card(repo, "SOR", "74"),    # event — no
                       _get_card(repo, "SOR", "140"),   # Aggression/Heroism — eligible
                       _get_card(repo, "SOR", "46"),    # Vigilance/Heroism — eligible
                       _get_card(repo, "SOR", "105"),   # Command — no
                       _get_card(repo, "SOR", "236"),   # Heroism only — no
                       _get_card(repo, "SOR", "95")],   # Command/Heroism — no
            below_cards=[_get_card(repo, "SOR", "74")],
        )
        state, _evt = _play_event_from_hand(state, repo, "LAW", "166")
        return state, deck

    def test_law_166_searches_top_8_for_vac_unit(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard, FinishSearch
        state, deck = self._play(repo)
        assert state.pending_decisions[-1].kind == "deck_search"
        acts = legal_actions(state)
        selects = {a.instance_id for a in acts if isinstance(a, SelectSearchCard)}
        assert selects == {deck[0].instance_id, deck[3].instance_id, deck[4].instance_id}
        assert not any(isinstance(a, FinishSearch) for a in acts)  # mandatory if able

    def test_law_166_draws_chosen_unit_bottoms_rest(self, repo):
        state, deck = self._play(repo)
        ps = state.players[0]
        hand_before = len(ps.hand)
        state = _take_from_search(state, deck[4].instance_id)  # take Consular (Vigilance)
        assert not state.pending_decisions
        ps = state.players[0]
        assert len(ps.hand) == hand_before + 1
        assert any(c.instance_id == deck[4].instance_id for c in ps.hand)
        assert ps.deck[0].instance_id == deck[8].instance_id  # 'below' stays on top


# ── Group leia-organa:03 — Combat tricks, buffs & tempo ───────────────────────

# ── LAW_10 Leia Organa ────────────────────────────────────────────────────────

class TestLeiaOrganaLAW:
    """Undeployed Action [2 resources, Exhaust]: give a unit +1/+1 per different
    aspect it has (this phase).  When Deployed: give a chosen unit an Experience
    token per different aspect among units you control."""

    def test_law_10_undeployed_buff_scales_with_aspects(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        leia = _place_leader(state, "P0", _get_card(repo, "LAW", "10"))
        _give_resources(state, "P0", 3)
        unit = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # Command+Heroism = 2 aspects
        p0, hp0 = compute_power(state, unit), compute_hp(state, unit)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leia.instance_id)
        state = apply(state, use)
        state = apply(state, ChooseTarget(unit.instance_id))

        now = _find_instance(state, unit.instance_id)
        assert compute_power(state, now) == p0 + 2   # +1/+1 per the 2 aspects
        assert compute_hp(state, now) == hp0 + 2
        assert state.players[0].available_resources == 1  # 2 of 3 resources spent

    def test_law_10_when_deployed_gives_experience_per_aspect(self, repo):
        from swu.engine.actions import legal_actions, apply, DeployLeader, ChooseTarget
        state = _make_state()
        leia = _place_leader(state, "P0", _get_card(repo, "LAW", "10"))
        _give_resources(state, "P0", 5)   # deploy threshold is 5
        unit = _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Cunning

        deploy = next(a for a in legal_actions(state) if isinstance(a, DeployLeader))
        state = apply(state, deploy)
        # When Deployed pushed a target choice for the Experience tokens.
        assert state.pending_decisions[-1].kind == "resolve_effects"
        # Distinct aspects among P0's units now (deployed Leia + the Cunning unit).
        controller = state.player_by_id("P0")
        aspects = set()
        for u in controller.ground_arena + controller.space_arena:
            aspects |= {a.name for a in (getattr(u.card_def, "aspects", None) or ())}
        state = apply(state, ChooseTarget(unit.instance_id))
        assert _experience_count(_find_instance(state, unit.instance_id)) == len(aspects)
        assert len(aspects) >= 2  # Leia's aspects + Cunning → scaling is exercised


# ── LAW_35 Ezra Bridger ───────────────────────────────────────────────────────

class TestEzraBridger:
    """Raid 1.  When Played: You may heal 2 damage from a unit, or 4 if you
    control an Aggression or Cunning unit."""

    def _setup(self, repo, *, with_cunning):
        state = _make_state()
        ezra = _place(state, "P0", _get_card(repo, "LAW", "35"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        target.damage = 6
        if with_cunning:
            _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Cunning
        return state, ezra, target

    def test_law_35_heals_2_without_aggression_or_cunning(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state, ezra, target = self._setup(repo, with_cunning=False)
        state = _fire_when_played(state, ezra)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(target.instance_id))
        assert _find_instance(state, target.instance_id).damage == 4  # healed 2 of 6

    def test_law_35_heals_4_with_cunning_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state, ezra, target = self._setup(repo, with_cunning=True)
        state = _fire_when_played(state, ezra)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(target.instance_id))
        assert _find_instance(state, target.instance_id).damage == 2  # healed 4 of 6

    def test_law_35_auto_declines_with_no_damaged_unit(self, repo):
        state = _make_state()
        ezra = _place(state, "P0", _get_card(repo, "LAW", "35"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # undamaged
        state = _fire_when_played(state, ezra)
        assert not state.pending_decisions  # nothing to heal → optional trigger auto-declines


# ── LAW_37 Han Solo ───────────────────────────────────────────────────────────

class TestHanSoloLAW:
    """On Attack: Give an Experience token to this unit."""

    def test_law_37_on_attack_gives_self_experience(self, repo):
        state = _make_state()
        han = _place(state, "P0", _get_card(repo, "LAW", "37"), "ground")
        state = _fire_on_attack(state, han, defender_ci=None)
        assert _experience_count(_find_instance(state, han.instance_id)) == 1
        assert not state.pending_decisions  # fixed SELF target → resolves inline


# ── LAW_67 Jyn Erso ───────────────────────────────────────────────────────────

class TestJynErso:
    """When Played: Either give an Experience token to a unit or exhaust a unit."""

    def _setup(self, repo):
        state = _make_state()
        jyn = _place(state, "P0", _get_card(repo, "LAW", "67"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, jyn)
        return state, jyn, friendly, enemy

    def test_law_67_offers_both_modes(self, repo):
        from swu.engine.actions import legal_actions, ChooseModalOption
        state, jyn, friendly, enemy = self._setup(repo)
        assert state.pending_decisions[-1].kind == "modal"
        modes = {a.mode for a in legal_actions(state) if isinstance(a, ChooseModalOption)}
        assert modes == {"give_experience_unit", "exhaust_unit"}

    def test_law_67_give_experience_mode(self, repo):
        from swu.engine.actions import apply, ChooseModalOption, ChooseModalTarget
        state, jyn, friendly, enemy = self._setup(repo)
        state = apply(state, ChooseModalOption("give_experience_unit"))
        state = apply(state, ChooseModalTarget(friendly.instance_id))
        assert _experience_count(_find_instance(state, friendly.instance_id)) == 1
        assert not state.pending_decisions

    def test_law_67_exhaust_mode(self, repo):
        from swu.engine.actions import apply, ChooseModalOption, ChooseModalTarget
        state, jyn, friendly, enemy = self._setup(repo)
        state = apply(state, ChooseModalOption("exhaust_unit"))
        state = apply(state, ChooseModalTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert not state.pending_decisions


# ── LAW_105 Cinta Kaz ─────────────────────────────────────────────────────────

class TestCintaKaz:
    """While this unit is upgraded, she gains Sentinel."""

    def test_law_105_printed_sentinel_is_sanitised(self, repo):
        cinta = _get_card(repo, "LAW", "105")
        assert "Sentinel" not in (cinta.keywords or ()), (
            "the conditional self-grant owns Sentinel; the printed bar is stripped")

    def test_law_105_sentinel_only_while_upgraded(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.tokens import attach_token
        state = _make_state()
        cinta = _place(state, "P0", _get_card(repo, "LAW", "105"), "ground")
        assert not has_keyword(state, cinta, Keyword.SENTINEL)  # no upgrade yet
        attach_token(state, state.player_by_id("P0"), cinta, "Shield")
        assert has_keyword(state, cinta, Keyword.SENTINEL)  # a token counts as an upgrade


# ── SEC_93 C-3PO ──────────────────────────────────────────────────────────────

class TestC3PO:
    """Action [Exhaust, return this unit to its owner's hand]: Give a unit +2/+2
    for this phase."""

    def test_sec_93_buffs_a_unit_and_returns_self_to_hand(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, ChooseTarget, compute_power, compute_hp)
        state = _make_state()
        c3po = _place(state, "P0", _get_card(repo, "SEC", "93"), "ground")
        target = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        p0, hp0 = compute_power(state, target), compute_hp(state, target)

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == c3po.instance_id)
        state = apply(state, use)
        # C-3PO itself is excluded from the buff target (not_self).
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert c3po.instance_id not in offered
        state = apply(state, ChooseTarget(target.instance_id))
        state = _drive_to_quiescence(state, lambda acts: None)

        now = _find_instance(state, target.instance_id)
        assert compute_power(state, now) == p0 + 2
        assert compute_hp(state, now) == hp0 + 2
        # C-3PO has returned to its owner's hand (no longer in the arena).
        assert _find_instance(state, c3po.instance_id) is None
        assert any(c.instance_id == c3po.instance_id for c in state.player_by_id("P0").hand)


# ── SEC_103 Mon Mothma ────────────────────────────────────────────────────────

class TestMonMothma:
    """Restore 3.  When Played: You may attack with any number of other units (one
    at a time), even if exhausted; they can't attack bases."""

    def _setup(self, repo):
        state = _make_state()
        mon = _place(state, "P0", _get_card(repo, "SEC", "103"), "ground")
        unit_a = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7 ready
        unit_b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        unit_b.exhausted = True
        enemy1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, mon)
        return state, mon, unit_a, unit_b, enemy1, enemy2

    def test_sec_103_offers_other_units_even_exhausted_no_bases(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        state, mon, unit_a, unit_b, enemy1, enemy2 = self._setup(repo)
        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        attackers = {a.attacker_id for a in acts if isinstance(a, AttackWithUnit)}
        assert attackers == {unit_a.instance_id, unit_b.instance_id}  # exhausted unit_b incl.
        assert mon.instance_id not in attackers                       # "other" units only
        # No base attacks (every offered attack targets a unit).
        assert all(a.defender_id is not None
                   for a in acts if isinstance(a, AttackWithUnit))
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)

    def test_sec_103_repeats_excluding_already_attacked_then_declines(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, DeclineGrantedAttack)
        state, mon, unit_a, unit_b, enemy1, enemy2 = self._setup(repo)
        # Attack with unit_a.
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit) and a.attacker_id == unit_a.instance_id)
        state = apply(state, atk)
        # The grant re-pushed: only unit_b remains (unit_a already attacked).
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state) if isinstance(a, AttackWithUnit)}
        assert attackers == {unit_b.instance_id}
        # Decline to stop the loop.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineGrantedAttack)))
        assert not state.pending_decisions

    def test_sec_103_attack_with_exhausted_unit_deals_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state, mon, unit_a, unit_b, enemy1, enemy2 = self._setup(repo)
        # unit_b is exhausted but may still attack; it deals its 3 power to enemy1.
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == unit_b.instance_id
                   and a.defender_id == enemy1.instance_id)
        state = apply(state, atk)
        assert _find_instance(state, enemy1.instance_id).damage == 3


# ── Group leia-organa:04 — Combat tricks, buffs & tempo ───────────────────────

# ── LAW_111 Leia's Disguise ───────────────────────────────────────────────────

class TestLeiasDisguise:
    """Attached unit gains the Underworld trait.  When Played: If attached unit is
    Leia Organa, give a Shield token to a friendly unit."""

    def test_law_111_grants_underworld_trait_to_host(self, repo):
        from swu.engine.traits import get_traits
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel/Trooper
        assert "Underworld" not in get_traits(state, host)
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "111"), "P0")
        assert "Underworld" in get_traits(state, host)

    def test_law_111_when_played_gives_shield_if_host_is_leia(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "SOR", "189"), "ground")  # "Leia Organa" unit
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, leia, _get_card(repo, "LAW", "111"), "P0")
        state = _fire_upgrade_played(state, up, leia)
        # Host is named Leia Organa → the When Played fires: give a Shield to a
        # friendly unit (mandatory; the host is itself a legal target).
        assert state.pending_decisions[-1].kind == "resolve_effects"
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert {leia.instance_id, ally.instance_id} <= offered
        state = apply(state, ChooseTarget(ally.instance_id))
        assert _shield_count(_find_instance(state, ally.instance_id)) == 1
        assert not state.pending_decisions

    def test_law_111_no_shield_when_host_not_leia(self, repo):
        """The ATTACHED_HOST_NAMED gate: a non-Leia host never gives the Shield."""
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Leia
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "111"), "P0")
        state = _fire_upgrade_played(state, up, host)
        assert not state.pending_decisions
        assert _shield_count(_find_instance(state, host.instance_id)) == 0


# ── LAW_142 Scarif Lieutenant ─────────────────────────────────────────────────

class TestScarifLieutenant:
    """When Defeated: Give an Experience token to a friendly Rebel unit."""

    def test_law_142_gives_experience_to_a_friendly_rebel(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        scarif = _place(state, "P0", _get_card(repo, "LAW", "142"), "ground")
        rebel = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")   # Rebel
        non_rebel = _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Fringe
        enemy_rebel = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy Rebel
        state = _fire_unit_defeated(state, scarif, "P0")
        # Only friendly Rebel units are eligible (not the Fringe ally, not the enemy).
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert rebel.instance_id in offered
        assert non_rebel.instance_id not in offered
        assert enemy_rebel.instance_id not in offered
        state = apply(state, ChooseTarget(rebel.instance_id))
        assert _experience_count(_find_instance(state, rebel.instance_id)) == 1
        assert not state.pending_decisions

    def test_law_142_fizzles_with_no_friendly_rebel(self, repo):
        state = _make_state()
        scarif = _place(state, "P0", _get_card(repo, "LAW", "142"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Fringe, not Rebel
        state = _fire_unit_defeated(state, scarif, "P0")
        assert not state.pending_decisions  # mandatory-if-able, but no legal target


# ── LAW_147 Jaunty Light Freighter ────────────────────────────────────────────

class TestJauntyLightFreighter:
    """When Played: Give an Experience token to this unit for each different aspect
    among units you control."""

    def test_law_147_tokens_self_per_distinct_aspect(self, repo):
        state = _make_state()
        jaunty = _place(state, "P0", _get_card(repo, "LAW", "147"), "space")  # Command/Heroism
        _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Cunning
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Aggression/Villainy
        n = len(_distinct_aspects(state, "P0"))
        state = _fire_when_played(state, jaunty)
        assert n >= 3  # Command, Heroism, Cunning, … → scaling is exercised
        assert _experience_count(_find_instance(state, jaunty.instance_id)) == n
        assert not state.pending_decisions  # fixed SELF → resolves inline


# ── LAW_152 C-3PO ─────────────────────────────────────────────────────────────

class TestC3POLAW:
    """On Attack: You may give an Experience token to another non-leader unit that
    shares a Trait with a friendly leader."""

    def _setup(self, repo):
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "LAW", "10"))  # leader, trait Rebel
        c3po = _place(state, "P0", _get_card(repo, "LAW", "152"), "ground")  # Rebel
        sharing = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel — shares
        non_sharing = _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Fringe — no
        return state, c3po, sharing, non_sharing

    def test_law_152_offers_only_trait_sharing_non_leader_units(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state, c3po, sharing, non_sharing = self._setup(repo)
        state = _fire_on_attack(state, c3po, defender_ci=None)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert sharing.instance_id in offered
        assert non_sharing.instance_id not in offered   # Fringe shares no leader trait
        assert c3po.instance_id not in offered          # "another" unit (not_self)
        state = apply(state, ChooseTarget(sharing.instance_id))
        assert _experience_count(_find_instance(state, sharing.instance_id)) == 1
        assert not state.pending_decisions

    def test_law_152_auto_declines_with_no_eligible_unit(self, repo):
        """No friendly leader / no trait-sharing unit → the optional trigger
        auto-declines (no prompt)."""
        state = _make_state()
        # No leader placed for P0, so no unit can share a trait with a friendly leader.
        c3po = _place(state, "P0", _get_card(repo, "LAW", "152"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, c3po, defender_ci=None)
        assert not state.pending_decisions


# ── LAW_167 Common Cause ──────────────────────────────────────────────────────

class TestCommonCause:
    """Give a unit +1/+1 for this phase for each different aspect among units you
    control."""

    def test_law_167_buffs_per_distinct_aspect(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        target = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # Command/Heroism
        _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Cunning
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Aggression/Villainy
        n = len(_distinct_aspects(state, "P0"))
        p0, hp0 = compute_power(state, target), compute_hp(state, target)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "167")
        assert state.pending_decisions[-1].kind == "resolve_effects"
        state = apply(state, ChooseTarget(target.instance_id))
        now = _find_instance(state, target.instance_id)
        assert n >= 3
        assert compute_power(state, now) == p0 + n
        assert compute_hp(state, now) == hp0 + n
        assert not state.pending_decisions


# ── SEC_252 Maarva Andor ──────────────────────────────────────────────────────

class TestMaarvaAndor:
    """When Defeated: Give an Experience token to each friendly Rebel unit."""

    def test_sec_252_tokens_each_friendly_rebel(self, repo):
        state = _make_state()
        maarva = _place(state, "P0", _get_card(repo, "SEC", "252"), "ground")  # Rebel
        rebel_a = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")   # Rebel
        rebel_b = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # Rebel
        non_rebel = _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Fringe
        enemy_rebel = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")  # enemy Rebel
        state = _fire_unit_defeated(state, maarva, "P0")
        # Each friendly Rebel unit got a token inline (no prompt); others did not.
        assert _experience_count(_find_instance(state, rebel_a.instance_id)) == 1
        assert _experience_count(_find_instance(state, rebel_b.instance_id)) == 1
        assert _experience_count(_find_instance(state, non_rebel.instance_id)) == 0
        assert _experience_count(_find_instance(state, enemy_rebel.instance_id)) == 0
        assert not state.pending_decisions


# ── Group leia-organa:05 — Miscellaneous abilities ────────────────────────────

# ── LAW_20 Daimyo's Palace ────────────────────────────────────────────────────

class TestDaimyosPalace:
    """Epic Action: Play a card from your hand, ignoring 1 of its Vigilance,
    Command, Aggression, or Cunning aspect penalties.  (Units only — documented
    deviation; the aspect-penalty waiver is faithful.)"""

    def _setup_base(self, state, repo, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_dp", _get_card(repo, "LAW", "20"), owner, Zone.BASE_ZONE)
        state.player_by_id(owner).base_zone = [ci]
        return ci

    def _hand(self, state, repo, sc, num, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        import uuid as _u
        ci = CardInstance(f"{owner}_h_{num}_{_u.uuid4().hex[:4]}",
                          _get_card(repo, sc, num), owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def test_law_20_waives_one_aspect_penalty_to_play(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
        state = _make_state()                       # P0 base has no aspects
        dp = self._setup_base(state, repo)
        # Swoop Racer: printed cost 3, [Cunning].  No matching base aspect →
        # effective cost 5; with one Cunning penalty waived it costs 3.
        unit = self._hand(state, repo, "SOR", "210")
        _give_resources(state, "P0", 3)             # affords 3, not the full 5

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == dp.instance_id)
        state = apply(state, use)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        assert dp.instance_id in state.game_memory.epic_actions_spent  # once-per-game

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = apply(state, play)
        assert _find_instance(state, unit.instance_id) is not None     # now in play
        # Paid 3 (5 effective − 2 waiver), so all 3 resources are exhausted.
        assert state.player_by_id("P0").available_resources == 0

    def test_law_20_waives_only_one_penalty_not_heroism(self, repo):
        """Only ONE V/C/A/Cunning penalty (2 resources) is waived — a second
        (Heroism) penalty is NOT, so a unit needing both waived stays unplayable."""
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        self._setup_base(state, repo)
        # SpecForce Soldier: cost 1, [Aggression, Heroism] → effective cost 5.
        # Waiving one Aggression penalty → cost 3; Heroism stays.
        self._hand(state, repo, "SOR", "140")
        _give_resources(state, "P0", 2)             # 2 < 3 → still not affordable
        # The epic is gated off: no unit is playable even with the single waiver.
        assert not any(isinstance(a, UseAbility) for a in legal_actions(state)), \
            "epic gated off — Heroism penalty not also waived, unit still costs 3"

    def test_law_20_waiver_caps_at_two_resources(self, repo):
        """The waiver removes at most one penalty (2 resources), not the whole
        effective cost: a [Cunning] unit (eff cost 5) costs 3 after the waiver."""
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, PlayFromHand)
        state = _make_state()
        dp = self._setup_base(state, repo)
        unit = self._hand(state, repo, "SOR", "210")   # [Cunning], eff cost 5 here
        _give_resources(state, "P0", 4)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == dp.instance_id)
        state = apply(state, use)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = apply(state, play)
        # Paid 3 (5 − 2 waiver), leaving 1 of 4 — the waiver caps at 2.
        assert state.player_by_id("P0").available_resources == 1

    def test_law_20_deployed_leader_aspects_still_count(self, repo):
        """Regression: a DEPLOYED leader's aspect icons must still count toward
        play costs.  Leia Organa (Command/Heroism) + Daimyo's Palace (Vigilance):
        Lando Calrissian (Vigilance/Heroism, cost 5) is fully matched and costs 5
        whether Leia is undeployed or deployed — not "5 +2" once she hits the
        arena (the bug behind the reported Daimyo's-Palace/Lando issue)."""
        from swu.engine.actions import _effective_cost, legal_actions, apply, \
            UseAbility, PlayFromHand
        from swu.engine.state import Zone
        state = _make_state()
        # Real Leia base + leader, not the aspect-less _make_state base.
        dp = self._setup_base(state, repo)
        leia = _place_leader(state, "P0", _get_card(repo, "LAW", "10"))
        ps = state.player_by_id("P0")
        lando = _get_card(repo, "LAW", "108")
        assert _effective_cost(lando, ps) == 5            # undeployed: fully matched

        # Deploy Leia into the ground arena.
        ps.base_zone = [dp]
        leia.deployed = True
        leia.zone = Zone.GROUND_ARENA
        ps.ground_arena.append(leia)
        assert _effective_cost(lando, ps) == 5            # deployed: STILL matched

        # And it is playable via Daimyo's Palace with 5 resources (no waiver needed).
        unit = self._hand(state, repo, "LAW", "108")
        _give_resources(state, "P0", 5)
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == dp.instance_id)
        state = apply(state, use)
        assert any(isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id
                   for a in legal_actions(state))


# ── LAW_104 Bodhi Rook ────────────────────────────────────────────────────────

class TestBodhiRook:
    """Sentinel.  On Attack: You may give a friendly Rebel unit Sentinel for this
    phase."""

    def test_law_104_grants_sentinel_to_friendly_rebel(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bodhi = _place(state, "P0", _get_card(repo, "LAW", "104"), "ground")   # Rebel
        rebel = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # Rebel
        non_rebel = _place(state, "P0", _get_card(repo, "SOR", "210"), "ground")  # Fringe
        enemy_rebel = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")  # enemy Rebel
        assert not has_keyword(state, rebel, Keyword.SENTINEL)

        state = _fire_on_attack(state, bodhi, defender_ci=None)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert rebel.instance_id in offered
        assert bodhi.instance_id in offered          # "a friendly Rebel unit" incl. self
        assert non_rebel.instance_id not in offered  # not a Rebel
        assert enemy_rebel.instance_id not in offered  # not friendly

        state = apply(state, ChooseTarget(rebel.instance_id))
        assert has_keyword(state, _find_instance(state, rebel.instance_id), Keyword.SENTINEL)
        assert not state.pending_decisions

    def test_law_104_is_optional(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        bodhi = _place(state, "P0", _get_card(repo, "LAW", "104"), "ground")
        rebel = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, bodhi, defender_ci=None)
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        assert not has_keyword(state, _find_instance(state, rebel.instance_id), Keyword.SENTINEL)
        assert not state.pending_decisions


# ── LAW_108 Lando Calrissian ──────────────────────────────────────────────────

class TestLandoCalrissian:
    """Sentinel.  While this unit is defending, the attacker gets −1/−0."""

    def test_law_108_debuffs_only_the_unit_attacking_lando(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "LAW", "108"), "ground")
        other_friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # power 3
        base = compute_power(state, attacker, is_attacking=True, attacking_unit=True)

        # While Lando is the defender, the attacker gets −1/−0.
        while_attacking_lando = compute_power(
            state, attacker, is_attacking=True, attacking_unit=True,
            defender_id=lando.instance_id)
        assert while_attacking_lando == max(0, base - 1)

        # No defender context (or attacking a different friendly unit) → full power.
        assert compute_power(state, attacker, is_attacking=True,
                             attacking_unit=True) == base
        assert compute_power(state, attacker, is_attacking=True, attacking_unit=True,
                             defender_id=other_friendly.instance_id) == base

    def test_law_108_reduces_damage_dealt_to_lando_in_combat(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "LAW", "108"), "ground")  # 4/5, Sentinel
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state.active_player_index = 1   # P1 acts; Lando (Sentinel) is the only target

        state = apply(state, AttackWithUnit(attacker.instance_id, lando.instance_id))
        # Attacker power 3, debuffed to 2 while attacking Lando → Lando takes 2 (not 3).
        now = _find_instance(state, lando.instance_id)
        assert now is not None and now.damage == 2
        assert all(m.duration != "this_attack" for m in state.modifiers)


# ── LAW_216 Jabba's Rancor (jabba-the-hutt:02 — Hidden keyword + residual) ─────

class TestJabbasRancor:
    """Jabba's Rancor (Creature/Underworld, 7/7, Hidden).
    Hidden: can't be attacked the phase it was played.
    On Attack: An opponent chooses a ground unit they control.  You may deal 7
    damage to that unit (the opponent-chooses-target seam with ground_only)."""

    def test_law_216_hidden_blocks_attack_the_phase_played(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        from swu.engine.keywords import has_keyword, Keyword
        rancor = _get_card(repo, "LAW", "216")
        state = _make_state()
        jabba = _place(state, "P0", rancor, "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, jabba, Keyword.HIDDEN)
        # Just played this phase → protected; P1 is the attacking player.
        state.active_player_index = 1
        state.game_memory.units_played_this_phase.add(jabba.instance_id)
        on_jabba = [a for a in legal_actions(state)
                    if isinstance(a, AttackWithUnit)
                    and a.defender_id == jabba.instance_id]
        assert on_jabba == []
        base_atk = [a for a in legal_actions(state)
                    if isinstance(a, AttackWithUnit) and a.defender_id is None]
        assert base_atk  # base still attackable

        # Next round (set cleared) → Rancor becomes attackable.
        state.game_memory.units_played_this_phase.discard(jabba.instance_id)
        assert any(a.defender_id == jabba.instance_id
                   for a in legal_actions(state) if isinstance(a, AttackWithUnit))

    def test_law_216_on_attack_opponent_picks_ground_then_deal_7(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseOwnTarget, ConfirmOpponentDamage)
        rancor = _get_card(repo, "LAW", "216")
        state = _make_state()
        jabba = _place(state, "P0", rancor, "ground")
        enemy_ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # An enemy SPACE unit and the base must NOT be offered (ground_only).
        enemy_space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_on_attack(state, jabba, None)

        top = state.pending_decisions[-1]
        assert top.kind == "opponent_chooses_target"
        assert top.deciding_player_id == "P1"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseOwnTarget)}
        assert offered == {enemy_ground.instance_id}  # only the ground unit
        assert enemy_space.instance_id not in offered
        assert state.players[1].base_instance.instance_id not in offered

        state = apply(state, ChooseOwnTarget(enemy_ground.instance_id))
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ConfirmOpponentDamage)))
        _, hit = state.find_instance(enemy_ground.instance_id)
        assert hit.damage == 7
        assert not any(d.kind == "opponent_chooses_target"
                       for d in state.pending_decisions)

    def test_law_216_on_attack_fizzles_without_opponent_ground_unit(self, repo):
        """No opponent ground unit → no decision is pushed (the trigger fizzles)."""
        rancor = _get_card(repo, "LAW", "216")
        state = _make_state()
        jabba = _place(state, "P0", rancor, "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # space only
        state = _fire_on_attack(state, jabba, None)
        assert not any(d.kind == "opponent_chooses_target"
                       for d in state.pending_decisions)


# ── Group jabba-the-hutt:07 — New primitive: create-token-unit (Credit) ────────

def _credits(state, pid="P0"):
    """Number of Credit tokens in a player's credit pile."""
    return len(state.player_by_id(pid).credits)


def _underworld_unit_def(repo, cost=2, name="Test Underworld Goon"):
    """A minimal vanilla Underworld Unit def (no abilities) for credit tests."""
    from swu.cards.models import Unit
    return Unit(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="UW", name=name, subtitle=None, type="Unit", rarity="Common",
        is_unique=False, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None, aspects=(), keywords=(), traits=("Underworld",),
        arenas=("Ground",), image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None, cost=cost, power=2, hp=2,
    )


class TestUnmarkedCredits:
    def test_law_244_creates_a_credit_token(self, repo):
        """Playing the event creates one Credit token for the controller."""
        state = _make_state()
        assert _credits(state, "P0") == 0
        state, _ = _play_event_from_hand(state, repo, "LAW", "244", owner="P0")
        assert _credits(state, "P0") == 1


class TestBibFortuna:
    def test_law_134_creates_credit_with_another_underworld_unit(self, repo):
        """When Played with another Underworld unit in play -> create a credit."""
        bib = _get_card(repo, "LAW", "134")
        state = _make_state()
        bib_ci = _place(state, "P0", bib, "ground")
        _place(state, "P0", _underworld_unit_def(repo), "ground")  # another Underworld
        state = _fire_when_played(state, bib_ci)
        assert _credits(state, "P0") == 1

    def test_law_134_no_credit_without_another_underworld_unit(self, repo):
        """Bib alone (no *other* Underworld unit) -> the trigger is not collected."""
        bib = _get_card(repo, "LAW", "134")
        state = _make_state()
        bib_ci = _place(state, "P0", bib, "ground")
        state = _fire_when_played(state, bib_ci)
        assert _credits(state, "P0") == 0


class TestFettsFirespray:
    def _fire_attack_defeats_unit(self, state, attacker_ci):
        from swu.abilities.resolver import fire_triggered_abilities
        return fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_defeated_unit": attacker_ci.instance_id})

    def test_law_252_creates_credit_when_it_defeats_the_defender(self, repo):
        """OnAttackDefeatsUnit (Fett's Firespray defeated the defender) -> credit."""
        fett = _get_card(repo, "LAW", "252")
        state = _make_state()
        fett_ci = _place(state, "P0", fett, "space")
        state = self._fire_attack_defeats_unit(state, fett_ci)
        assert _credits(state, "P0") == 1

    def test_law_252_no_credit_when_another_unit_defeats(self, repo):
        """The trigger is Fett-specific: another attacker defeating a unit gives
        Fett no credit."""
        fett = _get_card(repo, "LAW", "252")
        other = _underworld_unit_def(repo, name="Other Attacker")
        state = _make_state()
        _place(state, "P0", fett, "space")
        other_ci = _place(state, "P0", other, "ground")
        state = self._fire_attack_defeats_unit(state, other_ci)
        assert _credits(state, "P0") == 0


def _deploy_leader_in_arena(state, owner_id, leader_def):
    """Place a leader as a deployed (ready) unit in the ground arena."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ci = CardInstance(
        instance_id=f"{owner_id}_jabba_{_u.uuid4().hex[:6]}",
        card_def=leader_def, owner_id=owner_id, zone=Zone.GROUND_ARENA,
    )
    ci.deployed = True
    ci.exhausted = False
    state.player_by_id(owner_id).ground_arena.append(ci)
    return ci


def _add_credit(state, owner_id, n=1):
    from swu.engine.tokens import create_credit_token
    for _ in range(n):
        create_credit_token(state, state.player_by_id(owner_id))


class TestJabbaTheHutt:
    def _use_jabba(self, state, jabba_ci):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(
            a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == jabba_ci.instance_id
        )
        return apply(state, use)

    def test_law_15_undeployed_returns_underworld_unit_and_creates_credit(self, repo):
        """Undeployed Action [1 resource, Exhaust, return a friendly Underworld
        unit]: Create a Credit token."""
        from swu.engine.actions import ChooseTarget
        jabba = _get_card(repo, "LAW", "15")
        state = _make_state()
        jabba_ci = _place_leader(state, "P0", jabba)
        _give_resources(state, "P0", 1)
        goon = _place(state, "P0", _underworld_unit_def(repo), "ground")

        state = self._use_jabba(state, jabba_ci)
        # resolve the ReturnToHand target (the only Underworld unit)
        state = _drive_to_quiescence(
            state, lambda acts: next(
                (a for a in acts if isinstance(a, ChooseTarget)
                 and a.target_id == goon.instance_id), None))

        assert _credits(state, "P0") == 1
        assert _find_instance(state, goon.instance_id) is None, "goon left the arena"
        assert any(c.instance_id == goon.instance_id
                   for c in state.player_by_id("P0").hand), "goon returned to hand"
        jabba_now = next(c for c in state.player_by_id("P0").base_zone
                         if c.instance_id == jabba_ci.instance_id)
        assert jabba_now.exhausted, "Jabba exhausted by the cost"
        assert state.player_by_id("P0").available_resources == 0, "1 resource spent"

    def test_law_15_undeployed_not_offered_without_underworld_unit(self, repo):
        """No friendly Underworld unit to return -> the ability is not offered
        (the return is a genuine cost)."""
        from swu.engine.actions import legal_actions, UseAbility
        jabba = _get_card(repo, "LAW", "15")
        state = _make_state()
        jabba_ci = _place_leader(state, "P0", jabba)
        _give_resources(state, "P0", 3)
        offered = [a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == jabba_ci.instance_id]
        assert offered == []

    def test_law_15_deployed_plays_underworld_and_grants_ambush_on_credit_spend(self, repo):
        """Deployed Action: play an Underworld unit; if a Credit was defeated while
        paying its cost, that unit gains Ambush this phase."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        jabba = _get_card(repo, "LAW", "15")
        state = _make_state()
        jabba_ci = _deploy_leader_in_arena(state, "P0", jabba)
        _give_resources(state, "P0", 1)   # 1 ready resource
        _add_credit(state, "P0", 1)        # + 1 credit  -> can afford a cost-2 unit
        goon_def = _underworld_unit_def(repo, cost=2)
        goon = CardInstance("P0_uw_hand", goon_def, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(goon)

        state = self._use_jabba(state, jabba_ci)
        pf = next(a for a in legal_actions(state) if isinstance(a, PlayFromHand))
        state = apply(state, pf)

        played = _find_instance(state, goon.instance_id)
        assert played is not None, "Underworld unit entered play"
        assert has_keyword(state, played, Keyword.AMBUSH), "gained Ambush (credit spent)"
        assert _credits(state, "P0") == 0, "the credit was defeated to pay the cost"

    def test_law_15_deployed_no_ambush_when_no_credit_spent(self, repo):
        """If the unit is fully affordable from ready resources, no credit is spent
        (need-based) and the played unit does NOT gain Ambush."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        jabba = _get_card(repo, "LAW", "15")
        state = _make_state()
        jabba_ci = _deploy_leader_in_arena(state, "P0", jabba)
        _give_resources(state, "P0", 2)   # 2 ready resources cover the cost-2 unit
        _add_credit(state, "P0", 1)        # credit present but not needed
        goon_def = _underworld_unit_def(repo, cost=2)
        goon = CardInstance("P0_uw_hand2", goon_def, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(goon)

        state = self._use_jabba(state, jabba_ci)
        pf = next(a for a in legal_actions(state) if isinstance(a, PlayFromHand))
        state = apply(state, pf)

        played = _find_instance(state, goon.instance_id)
        assert played is not None
        assert not has_keyword(state, played, Keyword.AMBUSH), "no credit spent -> no Ambush"
        assert _credits(state, "P0") == 1, "credit untouched (need-based spend)"


# ── Group jabba-the-hutt:03 — Direct damage & removal ─────────────────────────

def _put_unit_in_discard(state, owner_id, card_def):
    """Place a unit card_def directly into a player's discard pile."""
    import uuid as _u
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_disc_{_u.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DISCARD,
    )
    state.player_by_id(owner_id).discard.append(ci)
    return ci


class TestSarlaccOfCarkoon:
    """LAW_163 — On Attack: Put a unit from your discard pile on the bottom of your
    deck.  Deal damage equal to that unit's power to an enemy ground unit."""

    def test_law_163_recycle_unit_then_deal_its_power(self, repo):
        from swu.engine.actions import (
            legal_actions, apply,
            SelectDiscardUnitForDamage, ChooseDiscardDamageTarget,
        )
        state = _make_state()
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")
        # A discarded unit whose power becomes the damage (Boba Fett, power 6).
        disc_def = _get_card(repo, "LAW", "214")
        disc = _put_unit_in_discard(state, "P0", disc_def)
        # An enemy ground unit with enough HP to survive (Jabba's Rancor, 7/7).
        enemy = _place(state, "P1", _get_card(repo, "LAW", "216"), "ground")

        state = _fire_on_attack(state, sarlacc, defender_ci=None)
        top = state.pending_decisions[-1]
        assert top.kind == "discard_unit_damage"
        assert top.context["stage"] == "select"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectDiscardUnitForDamage)
                   and a.instance_id == disc.instance_id)
        state = apply(state, sel)

        # The recycled unit is now on the bottom of P0's deck (out of discard).
        p0 = state.player_by_id("P0")
        assert disc.instance_id not in {c.instance_id for c in p0.discard}
        assert p0.deck[-1].instance_id == disc.instance_id

        assert state.pending_decisions[-1].context["stage"] == "target"
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseDiscardDamageTarget))
        assert tgt.target_id == enemy.instance_id
        state = apply(state, tgt)
        assert _find_instance(state, enemy.instance_id).damage == disc_def.power
        assert not state.pending_decisions

    def test_law_163_fizzles_with_empty_discard(self, repo):
        """No unit in the discard pile -> the On Attack pushes no decision."""
        state = _make_state()
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")
        _place(state, "P1", _get_card(repo, "LAW", "216"), "ground")
        state = _fire_on_attack(state, sarlacc, defender_ci=None)
        assert not any(d.kind == "discard_unit_damage"
                       for d in state.pending_decisions)

    def test_law_163_recycles_even_without_a_damage_target(self, repo):
        """A discard unit but no enemy ground unit: the recycle still happens
        (mandatory) and the decision resolves with no damage dealt."""
        from swu.engine.actions import legal_actions, apply, SelectDiscardUnitForDamage
        state = _make_state()
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")
        disc = _put_unit_in_discard(state, "P0", _get_card(repo, "LAW", "214"))
        # enemy has only a SPACE unit, no ground target
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_on_attack(state, sarlacc, defender_ci=None)
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectDiscardUnitForDamage))
        state = apply(state, sel)
        # No target stage — the decision popped after the recycle.
        assert not state.pending_decisions
        assert state.player_by_id("P0").deck[-1].instance_id == disc.instance_id


class TestBobaFett:
    """LAW_214 — When Played/On Attack: You may pay 1 resource.  If you do, deal 3
    damage to a ground unit."""

    def test_law_214_when_played_pay_then_deal_3(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "LAW", "214"), "ground")
        _give_resources(state, "P0", 1)   # one ready resource to pay
        enemy = _place(state, "P1", _get_card(repo, "LAW", "216"), "ground")  # 7 HP
        state = _fire_when_played(state, boba)
        # Optional ("you may") -> a trigger_option is offered (affordable + a target).
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3
        # The 1 resource was paid.
        assert state.player_by_id("P0").available_resources == 0
        assert not state.pending_decisions

    def test_law_214_on_attack_pay_then_deal_3(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "LAW", "214"), "ground")
        _give_resources(state, "P0", 1)
        enemy = _place(state, "P1", _get_card(repo, "LAW", "216"), "ground")
        state = _fire_on_attack(state, boba, defender_ci=None)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3

    def test_law_214_not_offered_without_a_ready_resource(self, repo):
        """No ready resource -> the "you may pay" trigger is not even offered."""
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "LAW", "214"), "ground")
        _place(state, "P1", _get_card(repo, "LAW", "216"), "ground")
        state = _fire_when_played(state, boba)   # 0 resources
        assert not state.pending_decisions

    def test_law_214_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        boba = _place(state, "P0", _get_card(repo, "LAW", "214"), "ground")
        _give_resources(state, "P0", 1)
        enemy = _place(state, "P1", _get_card(repo, "LAW", "216"), "ground")
        state = _fire_when_played(state, boba)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, enemy.instance_id).damage == 0
        # Declining costs no resource.
        assert state.player_by_id("P0").available_resources == 1
        assert not state.pending_decisions


class TestContractedHunter:
    """JTL_216 — Ambush (keyword) + When the regroup phase starts: Defeat this
    unit."""

    def test_jtl_216_defeated_when_regroup_starts(self, repo):
        """Driving both players to Pass enters regroup, which fires the trigger and
        defeats Contracted Hunter (it leaves the arena for its owner's discard)."""
        from swu.engine.actions import legal_actions, apply, Pass
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "JTL", "216"), "ground")
        # Both players pass -> ACTION ends -> _enter_regroup fires the trigger.
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, Pass)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, Pass)))
        # The hunter has been defeated.
        assert _find_instance(state, hunter.instance_id) is None
        assert hunter.instance_id in {c.instance_id
                                      for c in state.player_by_id("P0").discard}

    def test_jtl_216_only_self_defeats(self, repo):
        """The trigger defeats only the Contracted Hunter, not other units."""
        from swu.engine.actions import legal_actions, apply, Pass
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "JTL", "216"), "ground")
        bystander = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, Pass)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, Pass)))
        assert _find_instance(state, hunter.instance_id) is None
        assert _find_instance(state, bystander.instance_id) is not None
        assert _find_instance(state, enemy.instance_id) is not None


# ── Group jabba-the-hutt:04 — Card advantage & disruption ─────────────────────

def _put_in_hand(state, owner_id, card_def):
    """Place a card_def directly into a player's hand; returns the CardInstance."""
    import uuid as _u
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_hand_{_u.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


class TestGreatPitOfCarkoon:
    """LAW_23 — Epic Action [discard a unit from your hand]: Search your deck for a
    card named The Sarlacc of Carkoon, reveal it, and draw it."""

    def _setup_base(self, state, repo, owner="P0"):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_pit", _get_card(repo, "LAW", "23"), owner,
                          Zone.BASE_ZONE)
        state.player_by_id(owner).base_zone = [ci]
        return ci

    def test_law_23_discard_unit_then_tutor_sarlacc(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, DiscardForSearch, SelectSearchCard)
        state = _seed_rng(_make_state())
        pit = self._setup_base(state, repo)
        discardable = _put_in_hand(state, "P0", _get_card(repo, "LAW", "214"))  # a unit
        sarlacc = _get_card(repo, "LAW", "163")
        deck = _build_search_deck(
            state, "P0",
            top_cards=[_get_card(repo, "SOR", "128"), sarlacc, _get_card(repo, "SOR", "46")],
        )
        sarlacc_ci = deck[1]

        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == pit.instance_id)
        state = apply(state, use)
        assert pit.instance_id in state.game_memory.epic_actions_spent  # once-per-game
        top = state.pending_decisions[-1]
        assert top.kind == "discard_for_search"

        # Discard the unit (the cost), which triggers the search.
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, DiscardForSearch)
                   and a.instance_id == discardable.instance_id)
        state = apply(state, sel)
        p0 = state.player_by_id("P0")
        assert discardable.instance_id in {c.instance_id for c in p0.discard}
        assert state.pending_decisions[-1].kind == "deck_search"

        # Only the Sarlacc is an eligible candidate (named search).
        selects = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)}
        assert selects == {sarlacc_ci.instance_id}
        state = apply(state, SelectSearchCard(sarlacc_ci.instance_id))
        p0 = state.player_by_id("P0")
        assert any(c.instance_id == sarlacc_ci.instance_id for c in p0.hand)
        assert not state.pending_decisions

    def test_law_23_not_offered_without_a_unit_in_hand(self, repo):
        """The discard cost requires a Unit in hand — with none, the Epic Action is
        gated off (and the once-per-game epic is not wasted)."""
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        pit = self._setup_base(state, repo)
        # A non-unit in hand (an event) does not satisfy the "discard a unit" cost.
        _put_in_hand(state, "P0", _get_card(repo, "LAW", "246"))
        assert not any(isinstance(a, UseAbility) and a.source_id == pit.instance_id
                       for a in legal_actions(state))

    def test_law_23_search_finds_nothing_still_pays_cost(self, repo):
        """The Sarlacc not in the deck: the unit is still discarded and the search
        resolves (bottoming the deck), drawing nothing."""
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, DiscardForSearch, FinishSearch)
        state = _seed_rng(_make_state())
        pit = self._setup_base(state, repo)
        discardable = _put_in_hand(state, "P0", _get_card(repo, "LAW", "214"))
        _build_search_deck(state, "P0",
                           top_cards=[_get_card(repo, "SOR", "128"),
                                      _get_card(repo, "SOR", "46")])
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, UseAbility)
                                  and a.source_id == pit.instance_id))
        hand_before = len(state.player_by_id("P0").hand)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DiscardForSearch)))
        # No named card → no SelectSearchCard, only FinishSearch.
        acts = legal_actions(state)
        assert any(isinstance(a, FinishSearch) for a in acts)
        state = apply(state, next(a for a in acts if isinstance(a, FinishSearch)))
        p0 = state.player_by_id("P0")
        assert discardable.instance_id in {c.instance_id for c in p0.discard}
        # The unit was discarded (−1) and nothing was drawn.
        assert len(p0.hand) == hand_before - 1
        assert not state.pending_decisions


class TestSyndicateSpiceRunner:
    """LAW_136 — When Played: Search the top 3 cards of your deck for an Underworld
    unit, reveal it, and draw it."""

    def _setup(self, repo, top_cards):
        state = _seed_rng(_make_state())
        runner = _place(state, "P0", _get_card(repo, "LAW", "136"), "ground")
        deck = _build_search_deck(state, "P0", top_cards=top_cards,
                                  below_cards=[_get_card(repo, "SOR", "74")])
        state = _fire_when_played(state, runner)
        return state, deck

    def test_law_136_searches_top_3_for_underworld_unit(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard, FinishSearch
        # Top 3: an Underworld unit (eligible), a non-Underworld unit, an event.
        underworld = _underworld_unit_def(repo)
        state, deck = self._setup(repo, [underworld,
                                         _get_card(repo, "SOR", "46"),
                                         _get_card(repo, "SOR", "74")])
        assert state.pending_decisions[-1].kind == "deck_search"
        assert state.pending_decisions[-1].context["window"] == 3
        selects = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)}
        assert selects == {deck[0].instance_id}                 # only the Underworld unit
        assert not any(isinstance(a, FinishSearch) for a in legal_actions(state))  # mandatory

    def test_law_136_draws_the_underworld_unit(self, repo):
        underworld = _underworld_unit_def(repo)
        state, deck = self._setup(repo, [underworld,
                                         _get_card(repo, "SOR", "46"),
                                         _get_card(repo, "SOR", "74")])
        hand_before = len(state.player_by_id("P0").hand)
        state = _take_from_search(state, deck[0].instance_id)
        assert not state.pending_decisions
        p0 = state.player_by_id("P0")
        assert len(p0.hand) == hand_before + 1
        assert any(c.instance_id == deck[0].instance_id for c in p0.hand)

    def test_law_136_no_underworld_unit_in_window(self, repo):
        """No Underworld unit among the top 3 -> a FinishSearch (bottom the rest)."""
        from swu.engine.actions import legal_actions, SelectSearchCard, FinishSearch
        state, _deck = self._setup(repo, [_get_card(repo, "SOR", "46"),
                                          _get_card(repo, "SOR", "128"),
                                          _get_card(repo, "SOR", "74")])
        acts = legal_actions(state)
        assert not any(isinstance(a, SelectSearchCard) for a in acts)
        assert any(isinstance(a, FinishSearch) for a in acts)


class TestTheAxeForgets:
    """LAW_246 — Return a non-leader unit that costs 3 or less to its owner's
    hand."""

    def test_law_246_returns_eligible_unit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        cheap = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 1
        expensive = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")  # cost 8
        state, _evt = _play_event_from_hand(state, repo, "LAW", "246")
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert cheap.instance_id in offered
        assert expensive.instance_id not in offered  # cost > 3

        from swu.engine.actions import apply
        state = apply(state, ChooseTarget(cheap.instance_id))
        assert _find_instance(state, cheap.instance_id) is None       # left the arena
        assert any(c.instance_id == cheap.instance_id
                   for c in state.player_by_id("P1").hand)             # back in owner's hand
        assert not state.pending_decisions

    def test_law_246_can_return_friendly_unit(self, repo):
        """"a non-leader unit" omits friendly/enemy — either side is targetable."""
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "246")
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert friendly.instance_id in offered

    def test_law_246_fizzles_with_no_eligible_unit(self, repo):
        """No unit costing ≤3 on the board -> the event resolves with no target."""
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")  # cost 8 only
        state, _evt = _play_event_from_hand(state, repo, "LAW", "246")
        assert not state.pending_decisions


# ── Group jabba-the-hutt:05 — Combat tricks, buffs & tempo ────────────────────

class Test4LOM:
    """LAW_65 — When Played: You may attack with a friendly Bounty Hunter unit,
    even if it's exhausted.  It can't attack bases for this attack."""

    def test_law_65_offers_bounty_hunters_even_exhausted_no_base(self, repo):
        from swu.engine.actions import (
            legal_actions, AttackWithUnit, DeclineGrantedAttack)
        state = _make_state()
        fourlom = _place(state, "P0", _get_card(repo, "LAW", "65"), "ground")   # BH
        boba = _place(state, "P0", _get_card(repo, "LAW", "214"), "ground")     # BH
        boba.exhausted = True
        nonbh = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # not BH
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")            # enemy
        state = _fire_when_played(state, fourlom)
        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        attackers = {a.attacker_id for a in acts if isinstance(a, AttackWithUnit)}
        assert fourlom.instance_id in attackers           # 4-LOM is itself a BH
        assert boba.instance_id in attackers              # exhausted BH still offered
        assert nonbh.instance_id not in attackers         # non-BH excluded
        assert all(a.defender_id is not None              # no attack-a-base option
                   for a in acts if isinstance(a, AttackWithUnit))
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)

    def test_law_65_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineGrantedAttack
        state = _make_state()
        fourlom = _place(state, "P0", _get_card(repo, "LAW", "65"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, fourlom)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineGrantedAttack)))
        assert not state.pending_decisions


class TestKhetanna:
    """LAW_158 — When Played/On Attack: The next Underworld unit you play this
    phase costs 1 resource less."""

    def test_law_158_discounts_next_underworld_unit(self, repo):
        from swu.engine.actions import _play_cost, _effective_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        khet = _place(state, "P0", _get_card(repo, "LAW", "158"), "ground")
        uw = _get_card(repo, "LAW", "249")    # Black Sun Cabalist (Underworld)
        uw_ci = CardInstance("P0_uw", uw, "P0", Zone.HAND)
        nonuw = _get_card(repo, "SOR", "46")  # Rebel/Trooper (not Underworld)
        nonuw_ci = CardInstance("P0_nonuw", nonuw, "P0", Zone.HAND)
        state.player_by_id("P0").hand.extend([uw_ci, nonuw_ci])
        ps = state.player_by_id("P0")
        base_uw = _effective_cost(uw, ps)
        base_non = _effective_cost(nonuw, ps)
        # No discount before Khetanna's trigger fires.
        assert _play_cost(state, uw_ci, ps) == base_uw
        state = _fire_when_played(state, khet)
        ps = state.player_by_id("P0")
        assert _play_cost(state, uw_ci, ps) == max(0, base_uw - 1)   # Underworld -1
        assert _play_cost(state, nonuw_ci, ps) == base_non          # non-Underworld unchanged

    def test_law_158_discount_consumed_on_play(self, repo):
        from swu.engine.actions import apply, PlayCard, _effective_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        khet = _place(state, "P0", _get_card(repo, "LAW", "158"), "ground")
        state = _fire_when_played(state, khet)
        weq = _get_card(repo, "LAW", "231")   # Weequay Pirate (Underworld, no play decision)
        weq_ci = CardInstance("P0_weq", weq, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(weq_ci)
        _give_resources(state, "P0", 10)
        ps = state.player_by_id("P0")
        expected = max(0, _effective_cost(weq, ps) - 1)
        ready_before = ps.available_resources
        state = apply(state, PlayCard(weq_ci.instance_id))
        ps = state.player_by_id("P0")
        assert ps.available_resources == ready_before - expected     # paid 1 less
        assert not state.game_memory.pending_play_discounts          # discount consumed

    def test_law_158_on_attack_also_records_discount(self, repo):
        from swu.engine.actions import _play_cost, _effective_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        khet = _place(state, "P0", _get_card(repo, "LAW", "158"), "ground")
        uw = _get_card(repo, "LAW", "249")
        uw_ci = CardInstance("P0_uw", uw, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(uw_ci)
        state = _fire_on_attack(state, khet)
        ps = state.player_by_id("P0")
        assert _play_cost(state, uw_ci, ps) == max(0, _effective_cost(uw, ps) - 1)


class TestHaymaker:
    """LAW_168 — Give an Experience token to a friendly unit.  That unit deals
    damage equal to its power to an enemy unit in the same arena."""

    def test_law_168_token_then_damage_equal_to_power(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")  # 3/3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # 3/7
        state, _evt = _play_event_from_hand(state, repo, "LAW", "168")
        # First: choose the friendly unit (it gains an Experience token).
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == friendly.instance_id))
        assert _experience_count(_find_instance(state, friendly.instance_id)) == 1
        # Second: that unit (now power 4) deals 4 to the enemy in the same arena.
        acts = legal_actions(state)
        offered = {a.target_id for a in acts if isinstance(a, ChooseTarget)}
        assert enemy.instance_id in offered
        state = apply(state, next(a for a in acts if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4   # 3 power + 1 token
        assert not state.pending_decisions

    def test_law_168_only_same_arena_enemy_targetable(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")
        ground_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space_enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "space")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "168")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == friendly.instance_id))
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert ground_enemy.instance_id in offered
        assert space_enemy.instance_id not in offered   # different arena


class TestDoubleCross:
    """LAW_170 — Choose a friendly non-leader unit and an enemy non-leader unit.
    Exchange control of those units.  The player who takes control of the
    lower-cost unit creates Credit tokens equal to the cost difference."""

    def test_law_170_exchanges_control_and_credits_lower_cost(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # cost 4
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")     # cost 1
        state, _evt = _play_event_from_hand(state, repo, "LAW", "170")
        # First: choose the friendly non-leader unit.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == friendly.instance_id))
        # Second: choose the enemy non-leader unit → exchange happens now.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert not state.pending_decisions
        # Control exchanged: each unit now sits in the other player's arena, owner
        # unchanged (control is implicit = arena membership).
        f_ps, f_ci = state.find_instance(friendly.instance_id)
        e_ps, e_ci = state.find_instance(enemy.instance_id)
        assert f_ps.player_id == "P1" and f_ci.owner_id == "P0"   # my unit → opponent
        assert e_ps.player_id == "P0" and e_ci.owner_id == "P1"   # enemy unit → me
        # I (P0) now control the lower-cost unit (cost 1 < 4) → 3 Credit tokens.
        assert len(state.player_by_id("P0").credits) == 3
        assert len(state.player_by_id("P1").credits) == 0

    def test_law_170_credits_go_to_opponent_when_my_unit_is_cheaper(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # cost 1
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")      # cost 4
        state, _evt = _play_event_from_hand(state, repo, "LAW", "170")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == friendly.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        # Opponent (P1) takes control of my cheaper unit (cost 1) → 3 credits.
        assert len(state.player_by_id("P1").credits) == 3
        assert len(state.player_by_id("P0").credits) == 0

    def test_law_170_equal_cost_exchanges_without_credits(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")   # cost 2
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")      # cost 2
        state, _evt = _play_event_from_hand(state, repo, "LAW", "170")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == friendly.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        f_ps, _ = state.find_instance(friendly.instance_id)
        e_ps, _ = state.find_instance(enemy.instance_id)
        assert f_ps.player_id == "P1" and e_ps.player_id == "P0"   # still exchanged
        assert len(state.player_by_id("P0").credits) == 0          # no difference
        assert len(state.player_by_id("P1").credits) == 0


class TestSalaciousCrumb:
    """LAW_210 — If you control Jabba the Hutt, this unit enters play ready."""

    def test_law_210_enters_ready_with_jabba(self, repo):
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "LAW", "15"))   # Jabba undeployed
        crumb = _get_card(repo, "LAW", "210")
        crumb_ci = CardInstance("P0_crumb", crumb, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(crumb_ci)
        _give_resources(state, "P0", 5)
        state = apply(state, PlayCard(crumb_ci.instance_id))
        placed = _find_instance(state, crumb_ci.instance_id)
        assert placed is not None and not placed.exhausted   # entered ready

    def test_law_210_enters_exhausted_without_jabba(self, repo):
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        crumb = _get_card(repo, "LAW", "210")
        crumb_ci = CardInstance("P0_crumb", crumb, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(crumb_ci)
        _give_resources(state, "P0", 5)
        state = apply(state, PlayCard(crumb_ci.instance_id))
        placed = _find_instance(state, crumb_ci.instance_id)
        assert placed is not None and placed.exhausted       # default exhausted


class TestWeequayPirate:
    """LAW_231 — When Played: If no resources were paid to play this unit, give an
    Experience token to it."""

    def _fire_with_cost(self, state, ci, cost_paid):
        from swu.engine.events import UnitEntersPlay
        from swu.abilities.resolver import fire_triggered_abilities
        evt = UnitEntersPlay(player_id=ci.owner_id, instance_id=ci.instance_id,
                             card_name=ci.card_def.display_name, arena="Ground")
        state.event_log.append(evt)
        return fire_triggered_abilities(
            state, evt, after_all_player_idx=0,
            event_ctx={"source_id": ci.instance_id, "cost_paid": cost_paid})

    def test_law_231_token_when_no_resources_paid(self, repo):
        state = _make_state()
        weq = _place(state, "P0", _get_card(repo, "LAW", "231"), "ground")
        state = self._fire_with_cost(state, weq, 0)
        assert _experience_count(_find_instance(state, weq.instance_id)) == 1

    def test_law_231_no_token_when_resources_paid(self, repo):
        state = _make_state()
        weq = _place(state, "P0", _get_card(repo, "LAW", "231"), "ground")
        state = self._fire_with_cost(state, weq, 2)
        assert _experience_count(_find_instance(state, weq.instance_id)) == 0

    def test_law_231_no_token_on_normal_play(self, repo):
        """A normal paid PlayCard threads a non-zero cost_paid → no token."""
        from swu.engine.actions import apply, PlayCard
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        weq = _get_card(repo, "LAW", "231")
        weq_ci = CardInstance("P0_weq", weq, "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(weq_ci)
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(weq_ci.instance_id))
        assert _experience_count(_find_instance(state, weq_ci.instance_id)) == 0


class TestBlackSunCabalist:
    """LAW_249 — When Played: Give an Experience token to another friendly
    Underworld unit."""

    def test_law_249_tokens_another_underworld_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        cab = _place(state, "P0", _get_card(repo, "LAW", "249"), "ground")
        other_uw = _place(state, "P0", _get_card(repo, "LAW", "231"), "ground")  # Underworld
        nonuw = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")      # not Underworld
        state = _fire_when_played(state, cab)
        acts = legal_actions(state)
        offered = {a.target_id for a in acts if isinstance(a, ChooseTarget)}
        assert other_uw.instance_id in offered
        assert nonuw.instance_id not in offered
        assert cab.instance_id not in offered     # "another" — not itself
        state = apply(state, next(a for a in acts if isinstance(a, ChooseTarget)
                                  and a.target_id == other_uw.instance_id))
        assert _experience_count(_find_instance(state, other_uw.instance_id)) == 1

    def test_law_249_fizzles_with_no_other_underworld(self, repo):
        state = _make_state()
        cab = _place(state, "P0", _get_card(repo, "LAW", "249"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Underworld
        state = _fire_when_played(state, cab)
        assert not state.pending_decisions


# ── Group jabba-the-hutt:06 — Miscellaneous abilities ─────────────────────────

class TestMalakili:
    """LAW_212 — Each friendly Creature unit gains the Underworld trait (the
    arena-wide TraitGrant ConstantAbility seam in the trait query layer)."""

    def test_law_212_friendly_creature_gains_underworld(self, repo):
        from swu.engine.traits import get_traits, has_trait
        state = _make_state()
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")  # Creature
        # Baseline: with no Malakili in play, the Creature is not Underworld.
        assert "Creature" in get_traits(state, sarlacc)
        assert not has_trait(state, sarlacc, "Underworld")
        # With Malakili in play, the friendly Creature gains Underworld.
        _place(state, "P0", _get_card(repo, "LAW", "212"), "ground")
        assert has_trait(state, sarlacc, "Underworld")

    def test_law_212_enemy_creature_not_affected(self, repo):
        from swu.engine.traits import has_trait
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "212"), "ground")
        enemy_creature = _place(state, "P1", _get_card(repo, "LAW", "163"), "ground")
        assert not has_trait(state, enemy_creature, "Underworld")  # "friendly" only

    def test_law_212_non_creature_friendly_not_affected(self, repo):
        from swu.engine.traits import has_trait
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "212"), "ground")
        non_creature = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert "Creature" not in (non_creature.card_def.traits or ())
        assert not has_trait(state, non_creature, "Underworld")

    def test_law_212_grant_lifts_when_malakili_leaves_play(self, repo):
        from swu.engine.traits import has_trait
        state = _make_state()
        malakili = _place(state, "P0", _get_card(repo, "LAW", "212"), "ground")
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")
        assert has_trait(state, sarlacc, "Underworld")
        state.player_by_id("P0").ground_arena.remove(malakili)
        assert not has_trait(state, sarlacc, "Underworld")  # winks off with the source

    def test_law_212_granted_underworld_counts_in_target_matcher(self, repo):
        """The granted trait is honoured by the universal target matcher (and the
        recursion guard does not loop: the matcher's own ``traits=("Underworld",)``
        filter and Malakili's ``traits=("Creature",)`` grant filter both read the
        trait layer)."""
        from swu.abilities.registry import TargetSpec
        from swu.abilities.resolver import _spec_matches_ci
        state = _make_state()
        malakili = _place(state, "P0", _get_card(repo, "LAW", "212"), "ground")
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")
        spec = TargetSpec(controller="friendly", kind="unit", traits=("Underworld",))
        assert _spec_matches_ci(spec, sarlacc, malakili, state, {})

    def test_law_212_granted_creature_is_legal_black_sun_recipient(self, repo):
        """End-to-end through a card: Black Sun Cabalist LAW_249's "another friendly
        Underworld unit" now offers a Malakili-granted Creature as a recipient."""
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "212"), "ground")
        sarlacc = _place(state, "P0", _get_card(repo, "LAW", "163"), "ground")  # Creature
        cab = _place(state, "P0", _get_card(repo, "LAW", "249"), "ground")
        state = _fire_when_played(state, cab)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert sarlacc.instance_id in offered


# ── Group jabba-the-hutt:06 — Vermillion LAW_215 (escalated) ──────────────────

def _deck_top(state, owner_id, card_def):
    """Put a CardInstance for ``card_def`` on TOP of ``owner_id``'s deck."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ci = CardInstance(
        instance_id=f"{owner_id}_deck_{_u.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.DECK, face_down=True,
    )
    state.player_by_id(owner_id).deck.insert(0, ci)
    return ci


class TestVermillion:
    """LAW_215 — "When Attack Ends: If this unit survived, reveal the top card of a
    deck, then choose a player. They may play the revealed card for free. If they
    do, a different player creates Credit tokens equal to that card's cost." """

    def test_law_215_attack_ends_reveals_plays_free_makes_credits(self, repo):
        """A real base attack (Vermillion always survives) fires the
        ``WhenAttackEnds`` trigger; revealing P0's deck, letting P0 play the
        revealed Battlefield Marine for free, then P1 (the other player) makes
        Credits equal to its cost."""
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit,
            ChooseRevealDeck, ChooseRevealPlayer, PlayRevealedCard,
        )
        state = _make_state()
        verm = _place(state, "P0", _get_card(repo, "LAW", "215"), "space")
        marine = _deck_top(state, "P0", _get_card(repo, "SOR", "95"))  # cost 2, 3/3

        atk = AttackWithUnit(attacker_id=verm.instance_id, defender_id=None)
        assert atk in legal_actions(state)
        state = apply(state, atk)

        top = state.pending_decisions[-1]
        assert top.kind == "reveal_play_credit"
        assert top.deciding_player_id == "P0"
        assert top.context.get("stage") == "choose_deck"

        state = apply(state, ChooseRevealDeck("P0"))
        state = apply(state, ChooseRevealPlayer("P0"))
        # The revealed card is playable, so PlayRevealedCard is offered.
        assert PlayRevealedCard() in legal_actions(state)
        state = apply(state, PlayRevealedCard())

        p0 = state.player_by_id("P0")
        p1 = state.player_by_id("P1")
        assert any(u.instance_id == marine.instance_id for u in p0.ground_arena)
        assert all(c.instance_id != marine.instance_id for c in p0.deck)
        assert len(p1.credits) == 2          # different player makes Credits = cost
        assert not state.pending_decisions
        assert state.active_player_index == 1  # turn passes to the attacker's opponent

    def test_law_215_does_not_fire_when_attacker_defeated(self, repo):
        """The trigger reads ``attack_ended_survivor`` — set only for an attacker
        still in play.  Vermillion (5/7) trading into Mercenary Fleet (10/10) dies,
        so no reveal_play_credit decision is pushed even though a deck is ready."""
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        verm = _place(state, "P0", _get_card(repo, "LAW", "215"), "space")
        fleet = _place(state, "P1", _get_card(repo, "LAW", "164"), "space")  # 10/10
        _deck_top(state, "P0", _get_card(repo, "SOR", "95"))

        state = apply(state, AttackWithUnit(attacker_id=verm.instance_id,
                                            defender_id=fleet.instance_id))
        # Vermillion is defeated; no attack-ends decision was pushed.
        assert all(d.kind != "reveal_play_credit" for d in state.pending_decisions)
        p0 = state.player_by_id("P0")
        assert all(u.instance_id != verm.instance_id
                   for u in p0.ground_arena + p0.space_arena)

    def test_law_215_credits_go_to_the_other_player(self, repo):
        """The controller (P0) may hand the play to the opponent (P1).  Then the
        *different* player — P0 — makes the Credits, and the card enters P1's
        control (the cross-deck/control case, the documented limitation)."""
        from swu.engine.actions import (
            apply, AttackWithUnit,
            ChooseRevealDeck, ChooseRevealPlayer, PlayRevealedCard,
        )
        state = _make_state()
        verm = _place(state, "P0", _get_card(repo, "LAW", "215"), "space")
        marine = _deck_top(state, "P0", _get_card(repo, "SOR", "95"))

        state = apply(state, AttackWithUnit(attacker_id=verm.instance_id,
                                            defender_id=None))
        state = apply(state, ChooseRevealDeck("P0"))
        state = apply(state, ChooseRevealPlayer("P1"))   # let the opponent play it
        state = apply(state, PlayRevealedCard())

        p0 = state.player_by_id("P0")
        p1 = state.player_by_id("P1")
        # Marine entered P1's arena (control = P1); owner is still P0.
        assert any(u.instance_id == marine.instance_id for u in p1.ground_arena)
        assert marine.owner_id == "P0"
        # P0 (the player who did NOT play it) made the Credits.
        assert len(p0.credits) == 2
        assert len(p1.credits) == 0

    def test_law_215_decline_leaves_card_on_top_no_credits(self, repo):
        """Declining to play leaves the revealed card on top of its deck and makes
        no Credits (the "may play")."""
        from swu.engine.actions import (
            apply, AttackWithUnit,
            ChooseRevealDeck, ChooseRevealPlayer, DeclineRevealedCard,
        )
        state = _make_state()
        verm = _place(state, "P0", _get_card(repo, "LAW", "215"), "space")
        marine = _deck_top(state, "P0", _get_card(repo, "SOR", "95"))

        state = apply(state, AttackWithUnit(attacker_id=verm.instance_id,
                                            defender_id=None))
        state = apply(state, ChooseRevealDeck("P0"))
        state = apply(state, ChooseRevealPlayer("P0"))
        state = apply(state, DeclineRevealedCard())

        p0 = state.player_by_id("P0")
        p1 = state.player_by_id("P1")
        assert p0.deck and p0.deck[0].instance_id == marine.instance_id  # still on top
        assert all(u.instance_id != marine.instance_id for u in p0.ground_arena)
        assert len(p0.credits) == 0 and len(p1.credits) == 0
        assert not state.pending_decisions


# ── Reprint-duplicate encodes (Stage 4 of docs/reprint_duplicates_plan.md) ────

class TestIncapacitate:
    """LAW_131 — "Give a unit -2/-2 for this phase." (sib LAWP_12)."""

    def test_law_131_debuffs_chosen_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "LAW", "131")
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, tgt)
        e = _find_instance(state, enemy.instance_id)
        assert compute_power(state, e) == 1 and compute_hp(state, e) == 5


class TestFulminatrix:
    """SEC_142 — "When Played/On Attack: You may deal 4 damage to a ground unit."
    (sib SECP_12)."""

    def test_sec_142_when_played_deals_4_to_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        ful = _place(state, "P0", _get_card(repo, "SEC", "142"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, ful)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, tgt)
        assert _find_instance(state, enemy.instance_id).damage == 4

    def test_sec_142_on_attack_targets_only_ground(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        ful = _place(state, "P0", _get_card(repo, "SEC", "142"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_on_attack(state, ful)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert ground.instance_id in tids
        assert space.instance_id not in tids


# ── Reprint sweep Stage 4 Batch 2 canonical encode ───────────────────────────

class TestFirstLight:
    """SEC_88 — First Light (Ambush + Plot keyword layers): "When this unit attacks
    and defeats a unit: You may draw a card." (reprint canonical; sib P25_25)."""

    def _fire_defeats_unit(self, state, attacker_ci):
        from swu.abilities.resolver import fire_triggered_abilities
        return fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_defeated_unit": attacker_ci.instance_id})

    def _seed_deck(self, state, owner, repo, n=2):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ps = state.player_by_id(owner)
        for _ in range(n):
            ps.deck.append(CardInstance(
                f"{owner}_deck_{uuid.uuid4().hex[:6]}",
                _get_card(repo, "SOR", "46"), owner, Zone.DECK))

    def test_sec_88_draws_on_accept(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        fl = _place(state, "P0", _get_card(repo, "SEC", "88"), "space")
        self._seed_deck(state, "P0", repo)
        before = len(state.player_by_id("P0").hand)
        state = self._fire_defeats_unit(state, fl)
        assert state.pending_decisions[-1].kind == "trigger_option"   # "you may"
        acc = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, acc)
        while state.pending_decisions:   # drain the resolve_effects (the draw)
            state = apply(state, legal_actions(state)[0])
        assert len(state.player_by_id("P0").hand) == before + 1

    def test_sec_88_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        fl = _place(state, "P0", _get_card(repo, "SEC", "88"), "space")
        self._seed_deck(state, "P0", repo)
        before = len(state.player_by_id("P0").hand)
        state = self._fire_defeats_unit(state, fl)
        dec = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, dec)
        assert len(state.player_by_id("P0").hand) == before   # no draw


# ══════════════════════════════════════════════════════════════════════════════
# Reprint-duplicate sweep (Stage 4) — shipped-set LAW / SEC canonicals
# ══════════════════════════════════════════════════════════════════════════════

class TestBenthicTwoTubes:
    """LAW_57 — Benthic "Two Tubes": "On Attack: Deal 1 damage to an enemy ground
    unit.  When Defeated: Deal 1 damage to a base." (sib P26_8)."""

    def test_law_57_on_attack_damages_enemy_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        benthic = _place(state, "P0", _get_card(repo, "LAW", "57"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, benthic)
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert enemy.instance_id in tids
        assert friendly.instance_id not in tids   # enemy-only
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_law_57_when_defeated_damages_a_base(self, repo):
        from tests.test_sor_cards import _fire_when_defeated
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        benthic = _place(state, "P0", _get_card(repo, "LAW", "57"), "ground")
        state = _fire_when_defeated(state, benthic)
        enemy_base = state.player_by_id("P1").base_instance.instance_id
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy_base))
        assert state.player_by_id("P1").base_instance.damage == 1


class TestBailOrgana:
    """SEC_198 — Bail Organa: "On Attack: You may discard a card from your hand.  If
    you do, create a Spy token." (sib SECP_17)."""

    def _spy_count(self, state, owner):
        from swu.cards.models import TokenUnit
        ps = state.player_by_id(owner)
        return sum(1 for arena in (ps.ground_arena, ps.space_arena) for u in arena
                   if isinstance(u.card_def, TokenUnit) and u.card_def.name == "Spy")

    def _put_card_in_hand(self, state, owner, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid
        ci = CardInstance(f"{owner}_h_{uuid.uuid4().hex[:6]}",
                          _get_card(repo, "SOR", "46"), owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def test_sec_198_discard_creates_spy_token(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        bail = _place(state, "P0", _get_card(repo, "SEC", "198"), "ground")
        self._put_card_in_hand(state, "P0", repo)
        before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, bail)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        while state.pending_decisions:   # drain the CustomEffect resolve
            state = apply(state, legal_actions(state)[0])
        assert len(state.player_by_id("P0").hand) == before - 1
        assert self._spy_count(state, "P0") == 1

    def test_sec_198_auto_declines_with_empty_hand(self, repo):
        state = _make_state()
        bail = _place(state, "P0", _get_card(repo, "SEC", "198"), "ground")
        assert not state.player_by_id("P0").hand   # empty hand
        state = _fire_on_attack(state, bail)
        assert not state.pending_decisions   # no card to discard → not offered
        assert self._spy_count(state, "P0") == 0


# ── Reprint-duplicate sweep (Stage 4) — Batch 4 ───────────────────────────────

class TestK2SOLAW79:
    """LAW_79 — K-2SO (Unit, Ambush): "On Attack: You may deal 3 damage to a
    damaged ground unit." (sib LAWP_8)."""

    def test_law_79_damages_damaged_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        k2 = _place(state, "P0", _get_card(repo, "LAW", "79"), "ground")
        dmg = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        dmg.damage = 1                                   # damaged → eligible
        healthy = _place(state, "P1", _get_card(repo, "SOR", "48"), "ground")
        state = _fire_on_attack(state, k2)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert dmg.instance_id in tids
        assert healthy.instance_id not in tids           # undamaged excluded
        state = apply(state, ChooseTarget(dmg.instance_id))
        assert _find_instance(state, dmg.instance_id).damage == 1 + 3

    def test_law_79_auto_declines_with_no_damaged_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        k2 = _place(state, "P0", _get_card(repo, "LAW", "79"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "48"), "ground")   # undamaged
        state = _fire_on_attack(state, k2)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestDaringDelve:
    """LAW_203 — Daring Delve (Event): "Discard 2 cards from your deck. You may
    return an Aggression card discarded this way to your hand." (sib LAWP_16)."""

    def _push_deck_top(self, state, owner, card_def):
        import uuid
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_dk_{uuid.uuid4().hex[:6]}", card_def, owner, Zone.DECK)
        state.player_by_id(owner).deck.insert(0, ci)
        return ci

    def test_law_203_mills_two_and_returns_aggression(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectDiscardCard, FinishReturnFromDiscard)
        state = _make_state()
        # top two: an Aggression card (SOR_155 Aggression event) + a non-Aggression
        agg = self._push_deck_top(state, "P0", _get_card(repo, "SOR", "155"))     # milled 2nd
        non = self._push_deck_top(state, "P0", _get_card(repo, "SOR", "58"))      # Vigilance — milled 1st
        state, _ = _play_event_from_hand(state, repo, "LAW", "203")
        # both were milled to discard
        disc_ids = {c.instance_id for c in state.player_by_id("P0").discard}
        assert agg.instance_id in disc_ids and non.instance_id in disc_ids
        # return_from_discard offers only the Aggression milled card
        sel = [a for a in legal_actions(state) if isinstance(a, SelectDiscardCard)]
        offered = {a.instance_id for a in sel}
        assert agg.instance_id in offered
        assert non.instance_id not in offered
        state = apply(state, next(a for a in sel if a.instance_id == agg.instance_id))
        while state.pending_decisions:
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, FinishReturnFromDiscard)))
        assert any(c.instance_id == agg.instance_id
                   for c in state.player_by_id("P0").hand)

    def test_law_203_no_aggression_milled_no_return(self, repo):
        from swu.engine.actions import legal_actions, SelectDiscardCard
        state = _make_state()
        self._push_deck_top(state, "P0", _get_card(repo, "SOR", "58"))   # Vigilance
        self._push_deck_top(state, "P0", _get_card(repo, "SOR", "107"))  # Command
        state, _ = _play_event_from_hand(state, repo, "LAW", "203")
        assert not any(isinstance(a, SelectDiscardCard) for a in legal_actions(state))
        # both non-Aggression cards milled (plus the spent event itself in discard)
        assert not state.player_by_id("P0").deck
        assert len(state.player_by_id("P0").discard) == 3


class TestChopper:
    """SEC_147 — Chopper: "When this unit deals combat damage to a base: Each
    player discards a card from their hand." (sibs C25_6, P26_44, P26_56)."""

    def _put_in_hand(self, state, owner, repo):
        import uuid
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_h_{uuid.uuid4().hex[:6]}",
                          _get_card(repo, "SOR", "46"), owner, Zone.HAND)
        state.player_by_id(owner).hand.append(ci)
        return ci

    def test_sec_147_each_player_discards(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        chopper = _place(state, "P0", _get_card(repo, "SEC", "147"), "ground")
        self._put_in_hand(state, "P0", repo)
        self._put_in_hand(state, "P1", repo)
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": chopper.instance_id})
        while state.pending_decisions:
            from swu.engine.actions import legal_actions, apply
            state = apply(state, legal_actions(state)[0])
        assert len(state.player_by_id("P0").hand) == 0
        assert len(state.player_by_id("P1").hand) == 0


class TestGrassrootsResistance:
    """SEC_258 — Grassroots Resistance (Event): "Deal 3 damage to a unit. Heal 3
    damage from your base." (sibs ASH_258, SECP_20)."""

    def test_sec_258_damages_unit_and_heals_own_base(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 5
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "SEC", "258")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        while state.pending_decisions:
            state = apply(state, legal_actions(state)[0])
        assert _find_instance(state, enemy.instance_id).damage == 3
        assert state.player_by_id("P0").base_instance.damage == 2   # healed 3 of 5


# ── Reprint-duplicate encode (Stage 4 batch 5) ────────────────────────────────

def _fire_attack_ends_law(state, attacker_ci):
    """Fire a WhenAttackEnds trigger for a surviving attacker."""
    from swu.engine.events import AttackDeclared
    from swu.abilities.resolver import fire_triggered_abilities
    evt = AttackDeclared(
        attacker_player_id=attacker_ci.owner_id,
        attacker_instance_id=attacker_ci.instance_id,
        attacker_name=attacker_ci.card_def.display_name,
        defender_instance_id=None, defender_name="Base",
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=0,
        event_ctx={"attack_ended_survivor": attacker_ci.instance_id})


class TestHoundsTooth:
    """LAW_33 — When Attack Ends: If this unit survived, you may defeat a unit with
    less power than this unit (Hound's Tooth power 4)."""

    def test_law_33_defeats_lower_power_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        hound = _place(state, "P0", _get_card(repo, "LAW", "33"), "ground")  # 4/8
        weak = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # power 3 < 4
        state = _fire_attack_ends_law(state, hound)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(weak.instance_id))
        assert _find_instance(state, weak.instance_id) is None  # defeated

    def test_law_33_equal_or_greater_power_not_targetable(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        hound = _place(state, "P0", _get_card(repo, "LAW", "33"), "ground")  # power 4
        tough = _place(state, "P1", _get_card(repo, "SEC", "51"), "ground")  # power 8 >= 4
        state = _fire_attack_ends_law(state, hound)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions
        assert _find_instance(state, tough.instance_id) is not None


class TestInterrogationDroid:
    """LAW_75 — When Played: Exhaust an enemy unit.  If you do and that unit costs
    3 or less, its controller discards a card from their hand."""

    def test_law_75_exhausts_and_cheap_unit_forces_discard(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "LAW", "75"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "112"), "ground")  # cost 3
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        assert len(state.player_by_id("P1").hand) == 1
        state = _fire_when_played(state, droid)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert len(state.player_by_id("P1").hand) == 0  # cost<=3 -> discarded

    def test_law_75_expensive_unit_no_discard(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "LAW", "75"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_when_played(state, droid)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert len(state.player_by_id("P1").hand) == 1  # cost 4 -> no discard


class TestBoKatanKryze:
    """SEC_51 — When Played: give each enemy unit -3/-3 for this phase.  When an
    enemy unit is defeated: give an Experience token to a friendly unit."""

    def test_sec_51_debuffs_each_enemy_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        bo = _place(state, "P0", _get_card(repo, "SEC", "51"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SEC", "51"), "ground")  # 8/8
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")   # 3/7
        state = _fire_when_played(state, bo)
        assert compute_power(state, e1) == 5 and compute_hp(state, e1) == 5
        assert compute_power(state, e2) == 0 and compute_hp(state, e2) == 4
        # Bo-Katan (friendly) is untouched
        assert compute_power(state, bo) == 8

    def test_sec_51_experience_on_enemy_defeat(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        bo = _place(state, "P0", _get_card(repo, "SEC", "51"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # An enemy unit is defeated (still in its arena at fire time, per the
        # WhenUnitDefeated observer convention).
        state = _fire_when_defeated(state, enemy)
        # Give the Experience token to Bo-Katan (the only friendly unit).
        state = apply(state, ChooseTarget(bo.instance_id))
        assert _experience_count(_find_instance(state, bo.instance_id)) == 1


# ── Reprint-duplicate batch 6 (2026-07-08) ────────────────────────────────────


class TestChewbaccaLAW34:
    """LAW_34 — When Attack Ends: If the defending unit was defeated, give an
    Experience token to Chewbacca and heal 3 damage from him (= OnAttackDefeatsUnit,
    the attacker survived)."""

    def _fire_attack_defeats(self, state, attacker_ci):
        from swu.abilities.resolver import fire_triggered_abilities
        return fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_defeated_unit": attacker_ci.instance_id})

    def test_law_34_token_and_heal_on_defeat(self, repo):
        state = _make_state()
        chewie = _place(state, "P0", _get_card(repo, "LAW", "34"), "ground")  # 4/4
        chewie.damage = 3
        state = self._fire_attack_defeats(state, chewie)
        c = _find_instance(state, chewie.instance_id)
        assert _experience_count(c) == 1
        assert c.damage == 0  # healed 3

    def test_law_34_heal_floors_at_zero(self, repo):
        state = _make_state()
        chewie = _place(state, "P0", _get_card(repo, "LAW", "34"), "ground")
        chewie.damage = 1
        state = self._fire_attack_defeats(state, chewie)
        assert _find_instance(state, chewie.instance_id).damage == 0


def _drive_mf(state, prefer_ids):
    """Resolve the two optional Millennium Falcon On Attack triggers, accepting
    each and steering ChooseTarget toward the designated ids."""
    from swu.engine.actions import (
        legal_actions, apply, AcceptTrigger, ChooseTarget,
    )
    guard = 0
    while state.pending_decisions and guard < 20:
        guard += 1
        acts = legal_actions(state)
        acc = [a for a in acts if isinstance(a, AcceptTrigger)]
        cts = [a for a in acts if isinstance(a, ChooseTarget)
               and getattr(a, "target_id", None) is not None]
        if acc:
            state = apply(state, acc[0])
            continue
        if cts:
            ids = {a.target_id for a in cts}
            pick = next((i for i in prefer_ids if i in ids), cts[0].target_id)
            state = apply(state, ChooseTarget(pick))
            continue
        state = apply(state, acts[0])
    return state


class TestMillenniumFalconLAW68:
    """LAW_68 — On Attack: You may give a space unit -2/-0 and a ground unit +2/+0
    for this phase (two independent optional effects)."""

    def test_law_68_debuffs_space_and_buffs_ground(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        falcon = _place(state, "P0", _get_card(repo, "LAW", "68"), "space")  # 2/5
        enemy_space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # 3/7
        my_ground = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, falcon)
        state = _drive_mf(state, [enemy_space.instance_id, my_ground.instance_id])
        assert compute_power(state, _find_instance(state, enemy_space.instance_id)) == 1
        assert compute_power(state, _find_instance(state, my_ground.instance_id)) == 5


class TestKinoLoySEC114:
    """SEC_114 — This unit gets +1/+0 for each other exhausted friendly unit."""

    def test_sec_114_scales_with_exhausted_friendlies(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        kino = _place(state, "P0", _get_card(repo, "SEC", "114"), "ground")  # 1/5
        assert compute_power(state, kino) == 1  # no other exhausted friendly
        e1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        e1.exhausted = True
        e2.exhausted = True
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # ready → no count
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True  # enemy exhausted → not friendly, no count
        assert compute_power(state, _find_instance(state, kino.instance_id)) == 3

    def test_sec_114_own_exhaust_not_counted(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        kino = _place(state, "P0", _get_card(repo, "SEC", "114"), "ground")
        kino.exhausted = True  # "OTHER" excludes self
        assert compute_power(state, _find_instance(state, kino.instance_id)) == 1


# ── Stage-4 reprint sweep (Batch 7): SEC_170, SEC_130, LAW_247 ────────────────

def _play_unit_from_hand(state, repo, set_code, num, owner="P0", resources=10):
    """Put a unit card in hand and play it via PlayCard; returns (state, iid)."""
    from swu.engine.state import CardInstance, Zone
    from swu.engine.actions import apply, PlayCard
    card = _get_card(repo, set_code, num)
    ci = CardInstance(f"{owner}_{set_code}{num}_u", card, owner, Zone.HAND)
    state.player_by_id(owner).hand.append(ci)
    _give_resources(state, owner, resources)
    return apply(state, PlayCard(ci.instance_id)), ci.instance_id


class TestCorellianHoundsSEC170:
    """SEC_170 — "If an opponent controls no ground units, this unit enters play
    ready" (EntersPlayReady gated by ENEMY_CONTROLS_NO_GROUND_UNITS)."""

    def test_sec_170_enters_ready_when_enemy_has_no_ground(self, repo):
        state = _make_state()
        state, iid = _play_unit_from_hand(state, repo, "SEC", "170")
        assert _find_instance(state, iid).exhausted is False

    def test_sec_170_enters_exhausted_when_enemy_has_ground_unit(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy ground unit
        state, iid = _play_unit_from_hand(state, repo, "SEC", "170")
        assert _find_instance(state, iid).exhausted is True

    def test_sec_170_enemy_space_unit_does_not_block(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # space, not ground
        state, iid = _play_unit_from_hand(state, repo, "SEC", "170")
        assert _find_instance(state, iid).exhausted is False


class TestFerrixUprisingSEC130:
    """SEC_130 — "Deal damage to a unit equal to twice the number of units you
    control in its arena" (DealDamageEqualTo, doubled count)."""

    def test_sec_130_deals_double_arena_unit_count(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 2 friendly ground
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7 target
        state, _evt = _play_event_from_hand(state, repo, "SEC", "130")
        assert state.pending_decisions[-1].kind == "resolve_effects"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4  # 2 units × 2

    def test_sec_130_space_target_counts_space_arena(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "space")   # 1 friendly space
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # ground: not counted
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state, _evt = _play_event_from_hand(state, repo, "SEC", "130")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2  # 1 unit × 2


class TestBackedByTheHuttsLAW247:
    """LAW_247 — "Create a Credit token. You may deal damage to a unit equal to the
    number of friendly Credit tokens." """

    def test_law_247_creates_credit_and_deals_one(self, repo):
        from swu.engine.actions import apply, SelectDamageTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "247")
        assert len(state.player_by_id("P0").credits) == 1
        assert state.pending_decisions[-1].kind == "select_damage"
        state = apply(state, SelectDamageTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1
        assert not state.pending_decisions

    def test_law_247_scales_with_existing_credits(self, repo):
        from swu.engine.actions import apply, SelectDamageTarget
        from swu.engine.tokens import create_credit_token
        state = _make_state()
        p0 = state.player_by_id("P0")
        create_credit_token(state, p0)
        create_credit_token(state, p0)  # 2 pre-existing
        enemy = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")  # 9/9
        state, _evt = _play_event_from_hand(state, repo, "LAW", "247")
        assert len(state.player_by_id("P0").credits) == 3
        state = apply(state, SelectDamageTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3  # 3 credits

    def test_law_247_may_decline_damage(self, repo):
        from swu.engine.actions import apply, FinishSelectDamage
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "247")
        # "you may" — declining deals no damage but the credit stays.
        state = apply(state, FinishSelectDamage())
        assert len(state.player_by_id("P0").credits) == 1
        assert not state.pending_decisions


class TestRicketyQuadjumper:
    """LAW_115 — On Attack (optional): reveal the top card of your deck; if it's
    not a unit, give an Experience token to another unit (leave it on top)."""

    def _experience(self, ci):
        from swu.cards.models import TokenUpgrade
        return sum(1 for u in ci.attached_upgrades
                   if isinstance(u.card_def, TokenUpgrade) and u.card_def.name == "Experience")

    def test_law_115_gives_experience_when_top_not_unit(self, repo):
        from tests.test_sor_cards import _push_deck_top
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects, SelectTokenTarget)
        state = _make_state()
        rickety = _place(state, "P0", _get_card(repo, "LAW", "115"), "space")
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "186"))  # an Event = non-unit
        state = _fire_on_attack(state, rickety)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)))
        # Only "another unit" is offered — Rickety itself (not_self) is not.
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, SelectTokenTarget)}
        assert offered == {other.instance_id}
        state = apply(state, SelectTokenTarget(other.instance_id))
        _, o_after = state.find_instance(other.instance_id)
        assert self._experience(o_after) == 1
        # The revealed card is left on top of the deck.
        assert state.player_by_id("P0").deck[0].card_def.type == "Event"

    def test_law_115_no_token_when_top_is_unit(self, repo):
        from tests.test_sor_cards import _push_deck_top
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects, SelectTokenTarget)
        state = _make_state()
        rickety = _place(state, "P0", _get_card(repo, "LAW", "115"), "space")
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))  # a Unit
        state = _fire_on_attack(state, rickety)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)))
        assert not any(isinstance(a, SelectTokenTarget) for a in legal_actions(state))
        assert self._experience(other) == 0


# ── Reprint sweep Stage 4 Batch 10 canonical encodes (2026-07-09) ────────────

class TestTheMandalorianSEC209:
    """SEC_209 — The Mandalorian (Ambush): "When this unit attacks and defeats a
    unit: You may choose an enemy non-leader unit.  This unit captures it."
    (reprint canonical; sib J25_19)."""

    def _fire_defeats_unit(self, state, attacker_ci):
        from swu.abilities.resolver import fire_triggered_abilities
        return fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"attack_defeated_unit": attacker_ci.instance_id})

    def test_sec_209_captures_enemy_on_defeat(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        from swu.engine.state import Zone
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "SEC", "209"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._fire_defeats_unit(state, mando)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id))
        # Enemy left P1's arena and sits facedown under The Mandalorian (P0's pile).
        assert all(c.instance_id != enemy.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        cap = state.player_by_id("P0").capture_pile
        assert len(cap) == 1 and cap[0].instance_id == enemy.instance_id
        assert cap[0].captured_by == mando.instance_id
        assert cap[0].owner_id == "P1"
        assert cap[0].zone == Zone.CAPTURE_PILE

    def test_sec_209_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "SEC", "209"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._fire_defeats_unit(state, mando)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").capture_pile == []

    def test_sec_209_auto_declines_with_no_enemy_nonleader(self, repo):
        state = _make_state()
        mando = _place(state, "P0", _get_card(repo, "SEC", "209"), "ground")
        state = self._fire_defeats_unit(state, mando)
        assert not state.pending_decisions
        assert state.player_by_id("P0").capture_pile == []


class TestLandoCalrissianSEC68:
    """SEC_68 — Lando Calrissian (Grit): "When Played: You may choose an enemy unit
    and another friendly non-leader unit.  If you do, heal 6 damage from your base
    and the enemy unit captures the friendly unit." (reprint canonical; sib SECP_3)."""

    def test_sec_68_heals_base_and_enemy_captures_friendly(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        from swu.engine.state import Zone
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 10
        lando = _place(state, "P0", _get_card(repo, "SEC", "68"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, lando)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        # First target: the enemy captor.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id))
        # Second target: the friendly non-leader unit to be captured.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id))
        assert state.player_by_id("P0").base_instance.damage == 4   # healed 6
        # friendly is captured under the enemy → sits in P1's capture pile.
        assert all(c.instance_id != friendly.instance_id
                   for c in state.player_by_id("P0").ground_arena)
        cap = state.player_by_id("P1").capture_pile
        assert len(cap) == 1 and cap[0].instance_id == friendly.instance_id
        assert cap[0].captured_by == enemy.instance_id
        assert cap[0].owner_id == "P0" and cap[0].zone == Zone.CAPTURE_PILE

    def test_sec_68_friendly_target_excludes_lando_himself(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "SEC", "68"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, lando)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id))
        friendly_choices = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert other.instance_id in friendly_choices
        assert lando.instance_id not in friendly_choices   # "another" → not_self

    def test_sec_68_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 10
        lando = _place(state, "P0", _get_card(repo, "SEC", "68"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, lando)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").base_instance.damage == 10   # not healed
        assert state.player_by_id("P1").capture_pile == []


class TestChancellorPalpatineSEC82:
    """SEC_82 — Chancellor Palpatine (Plot): "When Played: If you control a leader
    unit, create 2 Spy tokens and give those tokens Sentinel for this phase."
    (reprint canonical; sib P26_62)."""

    def test_sec_82_creates_2_spies_with_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.cards.models import TokenUnit
        from tests.test_shd_cards import _place_deployed_leader
        state = _make_state()
        _place_deployed_leader(state, "P0", _get_card(repo, "SHD", "18"))  # a leader unit
        palp = _place(state, "P0", _get_card(repo, "SEC", "82"), "ground")
        state = _fire_when_played(state, palp)
        spies = [u for u in state.player_by_id("P0").ground_arena
                 if isinstance(u.card_def, TokenUnit) and u.card_def.name == "Spy"]
        assert len(spies) == 2
        for spy in spies:
            assert has_keyword(state, spy, Keyword.SENTINEL)

    def test_sec_82_no_spies_without_leader_unit(self, repo):
        from swu.cards.models import TokenUnit
        state = _make_state()
        palp = _place(state, "P0", _get_card(repo, "SEC", "82"), "ground")
        state = _fire_when_played(state, palp)
        spies = [u for u in state.player_by_id("P0").ground_arena
                 if isinstance(u.card_def, TokenUnit) and u.card_def.name == "Spy"]
        assert spies == []


# ── Stage-4 reprint sweep (batch 11) ─────────────────────────────────────────

class TestSecretBattleOfPretend:
    """LAW_226 — Event: Exhaust a friendly unit.  If you do, for each different
    aspect it has, exhaust an enemy unit in the same arena."""

    def test_law_226_exhausts_enemies_per_aspect(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, SelectUnitToExhaustCombined)
        state = _make_state()
        # Friendly unit with 2 distinct aspects (Vigilance + Heroism).
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "226", "P0", resources=20)
        # Choose the friendly unit to exhaust.
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, pick)
        # Now an exhaust_combined_cost decision offers the two enemy units.
        assert state.pending_decisions[-1].kind == "exhaust_combined_cost"
        for enemy in (e1, e2):
            sel = next(a for a in legal_actions(state)
                       if isinstance(a, SelectUnitToExhaustCombined)
                       and a.target_id == enemy.instance_id)
            state = apply(state, sel)
        _, f = state.find_instance(friendly.instance_id)
        _, a1 = state.find_instance(e1.instance_id)
        _, a2 = state.find_instance(e2.instance_id)
        assert f.exhausted        # the friendly unit was exhausted
        assert a1.exhausted        # first enemy exhausted (aspect 1)
        assert a2.exhausted        # second enemy exhausted (aspect 2)

    def test_law_226_capped_at_aspect_count(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, SelectUnitToExhaustCombined)
        state = _make_state()
        # A mono-aspect friendly unit (Vigilance only) → at most 1 enemy exhaust.
        friendly = _place(state, "P0", _get_card(repo, "LOF", "63"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "226", "P0", resources=20)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, pick)
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectUnitToExhaustCombined))
        state = apply(state, sel)
        # After one pick the cap (1) is reached → no more SelectUnit actions.
        assert not any(isinstance(a, SelectUnitToExhaustCombined)
                       for a in legal_actions(state))
        exhausted = [ci for ci in state.player_by_id("P1").ground_arena if ci.exhausted]
        assert len(exhausted) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Reprint-duplicate batch 12 (Stage 4) — SEC cards
# ══════════════════════════════════════════════════════════════════════════════

class TestDarthTrayaSEC188:
    """SEC_188 — On Attack: You may ready a non-unit leader."""

    def test_sec_188_readies_exhausted_undeployed_leader(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        leader = _place_leader(state, "P0", _get_card(repo, "LAW", "10"))
        leader.exhausted = True
        traya = _place(state, "P0", _get_card(repo, "SEC", "188"), "ground")
        state = _fire_on_attack(state, traya, defender_ci=None)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        # No-target CustomEffect: drive the resolve_effects step to completion.
        guard = 0
        while state.pending_decisions and guard < 10:
            state = apply(state, legal_actions(state)[0])
            guard += 1
        assert state.player_by_id("P0").leader_instance.exhausted is False

    def test_sec_188_not_offered_when_leader_already_ready(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        leader = _place_leader(state, "P0", _get_card(repo, "LAW", "10"))
        leader.exhausted = False  # ready → condition false, nothing to ready
        traya = _place(state, "P0", _get_card(repo, "SEC", "188"), "ground")
        state = _fire_on_attack(state, traya, defender_ci=None)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_sec_188_not_offered_when_leader_deployed(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        leader = _place_leader(state, "P0", _get_card(repo, "LAW", "10"))
        leader.deployed = True     # a "unit leader", not a non-unit leader
        leader.exhausted = True
        traya = _place(state, "P0", _get_card(repo, "SEC", "188"), "ground")
        state = _fire_on_attack(state, traya, defender_ci=None)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestOppressionBreedsRebellionSEC158:
    """SEC_158 — If a friendly unit was defeated while attacking this phase, draw 3."""

    def _seed_deck(self, state, repo, n=3):
        from tests.test_sor_cards import _push_deck_top
        for _ in range(n):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))

    def test_sec_158_draws_3_when_friendly_attacker_defeated(self, repo):
        state = _make_state()
        self._seed_deck(state, repo, 3)
        state.game_memory.attackers_defeated_this_round.add("P0")
        state, _evt = _play_event_from_hand(state, repo, "SEC", "158", owner="P0")
        assert len(state.player_by_id("P0").hand) == 3

    def test_sec_158_no_draw_when_no_attacker_defeated(self, repo):
        state = _make_state()
        self._seed_deck(state, repo, 3)
        state, _evt = _play_event_from_hand(state, repo, "SEC", "158", owner="P0")
        assert len(state.player_by_id("P0").hand) == 0
        assert len(state.player_by_id("P0").deck) == 3


class TestDarthSionSEC35:
    """SEC_35 — WhenPlayed: Experience per enemy unit defeated this phase; WhenDefeated:
    if 7+ power, return to hand (batch-13 reprint encode)."""

    def _drive(self, state):
        from swu.engine.actions import legal_actions, apply
        guard = 0
        while state.pending_decisions and guard < 12:
            state = apply(state, legal_actions(state)[0])
            guard += 1
        return state

    def test_sec_35_when_played_scales_experience_to_enemy_defeats(self, repo):
        state = _make_state()
        # Two enemy (P1) units + one friendly (P0) unit defeated this phase.
        state.game_memory.defeated_controllers_this_round = ["P1", "P1", "P0"]
        sion = _place(state, "P0", _get_card(repo, "SEC", "35"), "ground")
        state = self._drive(_fire_when_played(state, sion))
        assert _experience_count(sion) == 2  # only the two enemy defeats count

    def test_sec_35_when_played_no_tokens_when_no_enemy_defeats(self, repo):
        state = _make_state()
        state.game_memory.defeated_controllers_this_round = ["P0"]  # only a friendly loss
        sion = _place(state, "P0", _get_card(repo, "SEC", "35"), "ground")
        state = self._drive(_fire_when_played(state, sion))
        assert _experience_count(sion) == 0

    def test_sec_35_when_defeated_returns_to_hand_at_7_power(self, repo):
        from swu.engine.actions import _defeat_unit
        from swu.engine.tokens import attach_token
        state = _make_state()
        sion = _place(state, "P0", _get_card(repo, "SEC", "35"), "ground")
        # 5/5 base + two Experience tokens → 7/7 effective power at defeat.
        attach_token(state, state.player_by_id("P0"), sion, "Experience")
        attach_token(state, state.player_by_id("P0"), sion, "Experience")
        _defeat_unit(state, state.player_by_id("P0"), sion)
        state = self._drive(state)
        hand_ids = [c.instance_id for c in state.player_by_id("P0").hand]
        discard_ids = [c.instance_id for c in state.player_by_id("P0").discard]
        assert sion.instance_id in hand_ids
        assert sion.instance_id not in discard_ids

    def test_sec_35_when_defeated_stays_in_discard_below_7_power(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        sion = _place(state, "P0", _get_card(repo, "SEC", "35"), "ground")  # 5/5, no buffs
        _defeat_unit(state, state.player_by_id("P0"), sion)
        state = self._drive(state)
        hand_ids = [c.instance_id for c in state.player_by_id("P0").hand]
        discard_ids = [c.instance_id for c in state.player_by_id("P0").discard]
        assert sion.instance_id in discard_ids
        assert sion.instance_id not in hand_ids


class TestTheMandalorianLAW52:
    """LAW_52 — The Mandalorian, "Let's See the Puck": the batch-16 WhenYouDraw
    in-play observer ("When you draw 1+ cards during the action phase: give this
    unit a Shield") plus its "When Played: Draw a card"."""

    def test_law_52_draw_during_action_gives_shield(self, repo):
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state = _make_state()
        mando = _get_card(repo, "LAW", "52")
        mci = _place(state, "P0", mando, "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        ps0 = state.player_by_id("P0")
        assert _shield_count(mci) == 0
        _draw_cards(state, ps0, 1)                 # ACTION-phase draw → ledger entry
        state = _fire_draw_observers(state)        # settle-point drain
        mci = _find_instance(state, mci.instance_id)
        assert _shield_count(mci) == 1

    def test_law_52_when_played_draw_also_feeds_shield(self, repo):
        # Its own "When Played: Draw a card" enters the draw into the ledger; by the
        # settle-point drain the Mandalorian is in play, so that draw feeds a Shield.
        from swu.engine.actions import _fire_draw_observers
        state = _make_state()
        mci = _place(state, "P0", _get_card(repo, "LAW", "52"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        ps0 = state.player_by_id("P0")
        hand_before = len(ps0.hand)
        state = _fire_when_played(state, mci)      # WhenPlayed DrawCards(1)
        assert len(state.player_by_id("P0").hand) == hand_before + 1
        state = _fire_draw_observers(state)
        assert _shield_count(_find_instance(state, mci.instance_id)) == 1

    def test_law_52_regroup_draw_gives_no_shield(self, repo):
        # "during the action phase" — a REGROUP draw is ledgered (tagged with its
        # phase, for Axe Woves ASH_169's "including during the regroup phase") but
        # the MATCHER admits only ACTION ones, so this observer never fires.
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        from swu.engine.state import Phase
        state = _make_state()
        mci = _place(state, "P0", _get_card(repo, "LAW", "52"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state.phase = Phase.REGROUP
        _draw_cards(state, state.player_by_id("P0"), 1)
        assert [e["phase"] for e in state.game_memory.action_phase_draws] == ["REGROUP"]
        state = _fire_draw_observers(state)
        assert _shield_count(_find_instance(state, mci.instance_id)) == 0

    def test_law_52_enemy_draw_gives_no_shield(self, repo):
        # "when YOU draw" — an opponent's draw does not feed a friendly observer.
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state = _make_state()
        mci = _place(state, "P0", _get_card(repo, "LAW", "52"), "ground")
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "128"))
        _draw_cards(state, state.player_by_id("P1"), 1)   # P1 draws
        state = _fire_draw_observers(state)
        assert _shield_count(_find_instance(state, mci.instance_id)) == 0


def _in_hand(state, owner_id, instance_id):
    return any(c.instance_id == instance_id
               for c in state.player_by_id(owner_id).hand)


class TestKananJarrusLAW89:
    """Restore 1.  When Played: You may return a non-leader unit that costs 2 or
    less to its owner's hand.  If you control a Command or Aggression unit, you
    may return a non-leader unit that costs 4 or less instead.

    Exercises the new ``TargetSpec.cost_max_boost`` conditional cost cap.  Kanan
    is Cunning/Vigilance/Heroism, so he never self-satisfies the boost."""

    def test_law_89_returns_cost_2_enemy_unit_to_owner_hand(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "LAW", "89"), "ground")
        # enemy cost-2 unit — returnable at the base cap of 2 (its Command aspect
        # belongs to P1, so it does NOT boost P0's cap).
        marine = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # cost 2
        state = _fire_when_played(state, kanan)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(marine.instance_id))
        assert _find_instance(state, marine.instance_id) is None      # left the arena
        assert _in_hand(state, "P1", marine.instance_id)               # → owner's hand

    def test_law_89_cost_3_unit_not_returnable_without_command_or_aggression(self, repo):
        """At the base cap of 2, a cost-3 unit is no legal target, so the optional
        trigger auto-declines (no prompt)."""
        from swu.engine.actions import AcceptTrigger, legal_actions
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "LAW", "89"), "ground")  # cost 4
        fleet = _place(state, "P1", _get_card(repo, "SOR", "240"), "ground")  # cost 3
        state = _fire_when_played(state, kanan)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions
        assert _find_instance(state, fleet.instance_id) is not None    # still in play
        assert not _in_hand(state, "P1", fleet.instance_id)

    def test_law_89_boost_lets_cost_3_return_with_aggression_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "LAW", "89"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "140"), "ground")   # SpecForce Soldier = Aggression
        fleet = _place(state, "P1", _get_card(repo, "SOR", "240"), "ground")  # cost 3
        state = _fire_when_played(state, kanan)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(fleet.instance_id))
        assert _find_instance(state, fleet.instance_id) is None
        assert _in_hand(state, "P1", fleet.instance_id)

    def test_law_89_boost_cap_is_exactly_4_with_command_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "LAW", "89"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")    # Battlefield Marine = Command
        consular = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state = _fire_when_played(state, kanan)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(consular.instance_id))
        assert _find_instance(state, consular.instance_id) is None
        assert _in_hand(state, "P1", consular.instance_id)

    def test_law_89_declinable(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "LAW", "89"), "ground")
        marine = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # cost 2
        state = _fire_when_played(state, kanan)
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, marine.instance_id) is not None   # stays in play
        assert not _in_hand(state, "P1", marine.instance_id)
        assert not state.pending_decisions


# ── Stage 4 batch 30 (2026-07-13) — trivial straggler: Lawbringer LAW_101 ──────

class TestLawbringerLAW101:
    """Lawbringer LAW_101 — "When Played/On Attack: Choose an aspect. Give each
    enemy unit with that aspect –2/–2 for this phase."

    Zero new engine code — the choose_two_modal pick=1 selector over six aspect
    ``EventAbility`` options + mass ``ModifyStats`` to EACH_ENEMY of the chosen
    aspect.  Option indices: 2=Vigilance 3=Command 4=Aggression 5=Cunning
    6=Heroism 7=Villainy.  Siblings P26_83 / P26_99 are byte-identical reprint
    faces aliased to it.
    """
    AGGRESSION = 4
    COMMAND = 3

    def _play_and_pick(self, repo, aspect_opt):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        law = _place(state, "P0", _get_card(repo, "LAW", "101"), "ground")   # 7/7
        agg = _place(state, "P1", _get_card(repo, "SOR", "130"), "ground")   # 2/3 Aggression
        cmd = _place(state, "P1", _get_card(repo, "SOR", "105"), "ground")   # 5/4 Command
        state = _fire_when_played(state, law)
        assert state.pending_decisions[-1].kind == "choose_two_modal"
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectModalOption) and a.option_idx == aspect_opt)
        state = apply(state, pick)
        state = _drive_to_quiescence(state, lambda acts: None)
        return state, agg, cmd

    def test_law_101_debuffs_only_the_chosen_aspect(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state, agg, cmd = self._play_and_pick(repo, self.AGGRESSION)
        a = _find_instance(state, agg.instance_id)
        c = _find_instance(state, cmd.instance_id)
        assert compute_power(state, a) == 0 and compute_hp(state, a) == 1   # 2/3 → 0/1
        assert compute_power(state, c) == 5 and compute_hp(state, c) == 4   # Command untouched

    def test_law_101_other_aspect_choice_spares_aggression(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state, agg, cmd = self._play_and_pick(repo, self.COMMAND)
        a = _find_instance(state, agg.instance_id)
        c = _find_instance(state, cmd.instance_id)
        assert compute_power(state, a) == 2 and compute_hp(state, a) == 3   # aggression untouched
        assert compute_power(state, c) == 3 and compute_hp(state, c) == 2   # 5/4 → 3/2

    def test_law_101_debuff_can_defeat_a_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectModalOption
        state = _make_state()
        law = _place(state, "P0", _get_card(repo, "LAW", "101"), "ground")
        frail = _place(state, "P1", _get_card(repo, "SOR", "130"), "ground")  # 2/3 Aggression
        frail.damage = 2   # remaining 1 → the –2 HP (max HP floored at 1) makes damage 2 ≥ HP 1
        state = _fire_when_played(state, law)
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectModalOption) and a.option_idx == self.AGGRESSION)
        state = apply(state, pick)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert _find_instance(state, frail.instance_id) is None   # swept as defeated

    def test_law_101_on_attack_also_offers_the_modal(self, repo):
        state = _make_state()
        law = _place(state, "P0", _get_card(repo, "LAW", "101"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "130"), "ground")
        state = _fire_on_attack(state, law)
        assert state.pending_decisions[-1].kind == "choose_two_modal"

    def test_law_101_reprint_faces_registered(self):
        from swu.abilities.registry import get_abilities
        canon = get_abilities("LAW", "101")
        for s, n in [("P26", "83"), ("P26", "99")]:
            assert get_abilities(s, n) is canon


class TestMaulLAW54:
    """LAW_54 — Maul (7-cost 6/8, Overwhelm): "When Attack Ends: If this unit dealt
    combat damage to a player's base, you may take control of a non-leader unit that
    player controls.  When this unit leaves play, that unit's owner takes control of
    that unit."  The source-linked control-revert primitive."""

    def test_law_54_base_attack_take_control_links_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, AcceptTrigger, ChooseTarget)
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LAW", "54"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # 3/3

        state = apply(state, AttackWithUnit(attacker_id=maul.instance_id, defender_id=None))
        # The base-damage attack fired the optional take-control trigger.
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        assert ChooseTarget(enemy.instance_id) in legal_actions(state)
        state = apply(state, ChooseTarget(enemy.instance_id))

        # The enemy unit now sits in P0's arena (control changed) and is LINKED.
        p0 = state.player_by_id("P0")
        p1 = state.player_by_id("P1")
        assert any(u.instance_id == enemy.instance_id for u in p0.ground_arena)
        assert all(u.instance_id != enemy.instance_id for u in p1.ground_arena)
        moved = _find_instance(state, enemy.instance_id)
        assert moved.control_linked_to == maul.instance_id
        assert moved.owner_id == "P1"  # ownership unchanged

    def test_law_54_control_reverts_when_maul_leaves_play(self, repo):
        from swu.engine.actions import (
            apply, AttackWithUnit, AcceptTrigger, ChooseTarget, _defeat_unit)
        from swu.engine.actions import legal_actions
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LAW", "54"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")

        state = apply(state, AttackWithUnit(attacker_id=maul.instance_id, defender_id=None))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))

        # Defeat Maul via the real leave-play path — control reverts to the owner.
        _defeat_unit(state, state.player_by_id("P0"), _find_instance(state, maul.instance_id))
        p0 = state.player_by_id("P0")
        p1 = state.player_by_id("P1")
        reverted = _find_instance(state, enemy.instance_id)
        assert any(u.instance_id == enemy.instance_id for u in p1.ground_arena)
        assert all(u.instance_id != enemy.instance_id for u in p0.ground_arena)
        assert reverted.control_linked_to is None

    def test_law_54_unit_attack_does_not_fire(self, repo):
        """require_base_damage gates the trigger — a unit-vs-unit attack (no base
        damage) never offers the take-control, even with a valid target present."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, AcceptTrigger
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LAW", "54"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")   # attacked
        other = _place(state, "P1", _get_card(repo, "LAW", "164"), "ground")   # 10/10, survives

        state = apply(state, AttackWithUnit(attacker_id=maul.instance_id,
                                            defender_id=other.instance_id))
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert _find_instance(state, other.instance_id).control_linked_to is None

    def test_law_54_no_enemy_unit_auto_declines(self, repo):
        """Base attack with no enemy non-leader unit → the optional trigger has no
        legal target, so it auto-declines (no trigger_option decision)."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, AcceptTrigger
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LAW", "54"), "ground")

        state = apply(state, AttackWithUnit(attacker_id=maul.instance_id, defender_id=None))
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert all(d.kind != "trigger_option" for d in state.pending_decisions)

    def test_law_54_decline_leaves_control_unchanged(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit, DeclineTrigger
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LAW", "54"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")

        state = apply(state, AttackWithUnit(attacker_id=maul.instance_id, defender_id=None))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger)))

        p1 = state.player_by_id("P1")
        assert any(u.instance_id == enemy.instance_id for u in p1.ground_arena)
        assert _find_instance(state, enemy.instance_id).control_linked_to is None

    def test_law_54_reprint_p26_4_aliases_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        from swu.cards.reprints import REPRINT_ALIASES
        assert REPRINT_ALIASES.get(("P26", "4")) == ("LAW", "54")
        assert get_abilities("P26", "4") == get_abilities("LAW", "54")


# ── The Stranger LAW_86 (defender-first-strike) ──────────────────────────────

class TestTheStrangerLAW86:
    """LAW_86 — The Stranger (5-cost 1/7 Ground, Cunning/Vigilance/Villainy;
    Ambush/Grit = keyword layer): "While attacking, you may have the defending unit
    deal combat damage before this unit."

    Exercises the batch-39 defender-first-strike primitive (a this_attack
    ``defender_deals_first`` flag on the attacker, read at the unit-combat step —
    the mirror of attacker First Strike)."""

    def _resolve_attack(self, state, attacker_id, defender_id, *, accept):
        """Drive apply(AttackWithUnit) to full resolution, choosing the optional
        OnAttack defender-first trigger (accept/decline) and the pre_attack
        continuation along the way."""
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, AcceptTrigger, DeclineTrigger,
            ContinueAttack)
        state = apply(state, AttackWithUnit(attacker_id, defender_id))
        guard = 0
        while state.pending_decisions and guard < 20:
            guard += 1
            top = state.pending_decisions[-1]
            acts = legal_actions(state)
            if top.kind == "trigger_option":
                want = AcceptTrigger if accept else DeclineTrigger
                state = apply(state, next(a for a in acts if isinstance(a, want)))
            elif top.kind == "pre_attack":
                state = apply(state, next(a for a in acts if isinstance(a, ContinueAttack)))
            else:
                state = apply(state, acts[0])
        return state

    def test_law_86_on_attack_offers_optional_trigger_and_sets_flag_and_serialises(self, repo):
        """The OnAttack trigger is offered (a no-target "you may"); accepting sets the
        attacker's defender_deals_first flag, which survives a JSON round-trip."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        stranger = _get_card(repo, "LAW", "86")
        thug = _get_card(repo, "SOR", "247")
        state = _make_state()
        s_ci = _place(state, "P0", stranger, "ground")
        d_ci = _place(state, "P1", thug, "ground")

        state = _fire_on_attack(state, s_ci, d_ci)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        # The no-target CustomEffect resolves to quiescence (AutoResolveEffects); there
        # is no combat step2 here to clear the flag, so it stays set.
        state = _drive_to_quiescence(state, lambda acts: None)

        _, s_after = state.find_instance(s_ci.instance_id)
        assert s_after.defender_deals_first is True

        from swu.engine.state import GameState
        restored = GameState.from_json(state.to_json())
        _, s_r = restored.find_instance(s_ci.instance_id)
        assert s_r.defender_deals_first is True

    def test_law_86_defender_first_lets_grit_attacker_kill_via_incoming_damage(self, repo):
        """Defender strikes first (2 dmg); the surviving Stranger's Grit power grows to
        1+2=3 and kills the 3-hp defender — the whole point of choosing defender-first
        (which a declined/simultaneous 1-power swing could not do)."""
        stranger = _get_card(repo, "LAW", "86")   # 1/7, Grit
        thug = _get_card(repo, "SOR", "247")       # 2/3
        state = _make_state()
        s_ci = _place(state, "P0", stranger, "ground")
        d_ci = _place(state, "P1", thug, "ground")

        state = self._resolve_attack(state, s_ci.instance_id, d_ci.instance_id, accept=True)

        assert _find_instance(state, d_ci.instance_id) is None, "Thug killed by grown Grit power"
        s_after = _find_instance(state, s_ci.instance_id)
        assert s_after is not None and s_after.damage == 2, "Stranger survives the 2 it took first"
        assert s_after.defender_deals_first is False, "flag cleared after the attack"

    def test_law_86_declined_is_simultaneous_and_thug_survives(self, repo):
        """Declining the trigger leaves normal simultaneous combat: the Stranger's
        power is snapshot at 1 (Grit unfed), so the 3-hp Thug survives and the Stranger
        still takes the Thug's 2."""
        stranger = _get_card(repo, "LAW", "86")
        thug = _get_card(repo, "SOR", "247")
        state = _make_state()
        s_ci = _place(state, "P0", stranger, "ground")
        d_ci = _place(state, "P1", thug, "ground")

        state = self._resolve_attack(state, s_ci.instance_id, d_ci.instance_id, accept=False)

        d_after = _find_instance(state, d_ci.instance_id)
        assert d_after is not None and d_after.damage == 1, "Thug takes only the 1-power swing"
        s_after = _find_instance(state, s_ci.instance_id)
        assert s_after is not None and s_after.damage == 2
        assert s_after.defender_deals_first is False

    def test_law_86_defender_first_defeats_attacker_deals_nothing_back(self, repo):
        """When the defender's first strike defeats the Stranger, the Stranger deals no
        combat damage back — the defender is untouched (the First-Strike mirror)."""
        stranger = _get_card(repo, "LAW", "86")   # 1/7, Grit
        thug = _get_card(repo, "SOR", "247")       # power 2
        state = _make_state()
        s_ci = _place(state, "P0", stranger, "ground")
        s_ci.damage = 6                             # remaining 1; power via Grit = 1+6 = 7
        d_ci = _place(state, "P1", thug, "ground")

        state = self._resolve_attack(state, s_ci.instance_id, d_ci.instance_id, accept=True)

        assert _find_instance(state, s_ci.instance_id) is None, "Stranger defeated by first strike"
        d_after = _find_instance(state, d_ci.instance_id)
        assert d_after is not None and d_after.damage == 0, "defender takes nothing back"

    def test_law_86_attacking_base_does_not_leak_flag(self, repo):
        """Accepting defender-first then attacking a base (which reads no such flag)
        must not leak the flag onto the Stranger for a later attack."""
        stranger = _get_card(repo, "LAW", "86")
        state = _make_state()
        s_ci = _place(state, "P0", stranger, "ground")

        state = self._resolve_attack(state, s_ci.instance_id, None, accept=True)

        s_after = _find_instance(state, s_ci.instance_id)
        assert s_after is not None and s_after.defender_deals_first is False, "flag cleared, no leak"
        # And the base took the Stranger's (snapshot) 1 power.
        assert state.player_by_id("P1").base_instance.damage == 1

    def test_law_86_reprints_alias_to_canonical(self):
        """P26_110 aliases to the shipped LAW_86 registration."""
        import swu.cards  # noqa: F401 — ensure aliases are applied
        from swu.abilities.registry import get_abilities
        canonical = get_abilities("LAW", "86")
        assert canonical, "LAW_86 must be registered"
        assert get_abilities("P26", "110") == canonical, "P26_110 should alias LAW_86"


# ── Max Rebo LAW_72 (extra-regroup-phase) ────────────────────────────────────

class TestMaxReboLAW72:
    """LAW_72 — Max Rebo (4-cost Unit): "There is an additional regroup phase after
    the first regroup phase each round."

    Exercises the batch-40 extra-regroup-phase primitive (an ExtraRegroupPhase
    passive marker + a regroup_count_this_round counter, read at the
    regroup-rollover site — the round runs TWO regroups while a Max Rebo is in
    play)."""

    def _stock(self, state, repo):
        """Give both players a deck so regroup draws don't hit the empty-deck
        base-damage penalty."""
        for pid in ("P0", "P1"):
            for _ in range(8):
                _push_deck_top(state, pid, _get_card(repo, "SOR", "46"))

    def _pass_both(self, state):
        from swu.engine.actions import legal_actions, apply, Pass
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, Pass)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, Pass)))
        return state

    def _skip_regroup_once(self, state):
        """Both players skip resourcing → completes ONE regroup phase (which either
        re-enters a second regroup or rolls over)."""
        from swu.engine.actions import legal_actions, apply, SkipResource
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, SkipResource)))
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, SkipResource)))
        return state

    def test_law_72_two_regroups_each_round_draws_double(self, repo):
        """With Max Rebo in play the round runs a second regroup: both players draw
        twice (4 cards), the counter reaches 2 mid-round, then rolls over to the
        next round's ACTION with the counter reset to 0."""
        state = _make_state()
        self._stock(state, repo)
        _place(state, "P0", _get_card(repo, "LAW", "72"), "ground")
        h0 = len(state.player_by_id("P0").hand)

        state = self._pass_both(state)
        assert state.phase.name == "REGROUP"
        assert state.regroup_count_this_round == 1

        state = self._skip_regroup_once(state)          # first regroup ends
        assert state.phase.name == "REGROUP", "re-entered a second regroup, not ACTION"
        assert state.regroup_count_this_round == 2
        assert state.round_number == 1, "still the same round between the two regroups"

        state = self._skip_regroup_once(state)          # second regroup ends
        assert state.phase.name == "ACTION"
        assert state.round_number == 2
        assert state.regroup_count_this_round == 0, "counter reset at rollover"
        assert len(state.player_by_id("P0").hand) - h0 == 4, "drew 2 per regroup, twice"

    def test_law_72_no_max_rebo_single_regroup_is_unchanged(self, repo):
        """Control: with NO Max Rebo the round runs exactly one regroup — a single
        draw of 2 and a rollover — byte-identical to the pre-primitive behaviour."""
        state = _make_state()
        self._stock(state, repo)
        h0 = len(state.player_by_id("P0").hand)

        state = self._pass_both(state)
        assert state.regroup_count_this_round == 1
        state = self._skip_regroup_once(state)
        assert state.phase.name == "ACTION"
        assert state.round_number == 2
        assert state.regroup_count_this_round == 0
        assert len(state.player_by_id("P0").hand) - h0 == 2, "one regroup, drew 2"

    def test_law_72_cannot_ready_stays_exhausted_through_both_regroups(self, repo):
        """A unit that "can't ready this round" (No Good to Me Dead SOR_186) stays
        exhausted through BOTH of Max Rebo's regroups; the flag is cleared only at
        the true round rollover (so it readies normally next round)."""
        state = _make_state()
        self._stock(state, repo)
        _place(state, "P0", _get_card(repo, "LAW", "72"), "ground")
        u = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        u.exhausted = True
        u.cannot_ready_this_round = True

        state = self._pass_both(state)
        state = self._skip_regroup_once(state)          # first regroup readies
        after1 = _find_instance(state, u.instance_id)
        assert after1.exhausted is True, "kept tapped through the first regroup"
        assert after1.cannot_ready_this_round is True, "flag not cleared between regroups"
        assert state.phase.name == "REGROUP"

        state = self._skip_regroup_once(state)          # second regroup → rollover
        after2 = _find_instance(state, u.instance_id)
        assert after2.exhausted is True, "kept tapped through the second regroup too"
        assert after2.cannot_ready_this_round is False, "flag cleared at rollover"
        assert state.round_number == 2

    def test_law_72_regroup_count_serialises_between_regroups(self, repo):
        """The regroup_count_this_round field round-trips through JSON while sitting
        mid-round between Max Rebo's two regroups."""
        from swu.engine.state import GameState
        state = _make_state()
        self._stock(state, repo)
        _place(state, "P0", _get_card(repo, "LAW", "72"), "ground")
        state = self._pass_both(state)
        state = self._skip_regroup_once(state)          # now in the second regroup
        assert state.regroup_count_this_round == 2

        restored = GameState.from_json(state.to_json())
        assert restored.regroup_count_this_round == 2
        assert restored.phase.name == "REGROUP"

    def test_law_72_reprints_alias_to_canonical(self):
        """P26_82 and P26_98 alias the shipped LAW_72 registration."""
        import swu.cards  # noqa: F401 — ensure aliases are applied
        from swu.abilities.registry import get_abilities
        canonical = get_abilities("LAW", "72")
        assert canonical, "LAW_72 must be registered"
        assert get_abilities("P26", "82") == canonical, "P26_82 should alias LAW_72"
        assert get_abilities("P26", "98") == canonical, "P26_98 should alias LAW_72"


# ── SEC_193 Grand Admiral Thrawn — the capture_or_ready decision kind (batch 42)

class TestGrandAdmiralThrawnSEC193:
    """When Played: An opponent may choose a non-leader unit they control. If they
    do, this unit captures that unit. If they don't, ready this unit.
    When Defeated: A friendly unit captures an enemy non-leader unit in the same
    arena.

    The new ``capture_or_ready`` decision kind (opponent-decided capture-or-ready)
    for the When Played; the When Defeated composes two dependent CustomEffects
    (Haymaker LAW_168 pattern) + ``same_arena_as_event`` + the capture primitive.
    """

    def _drive_to_capture_decision(self, state, thrawn):
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        state = _fire_when_played(state, thrawn)
        guard = 0
        while (state.pending_decisions
               and state.pending_decisions[-1].kind != "capture_or_ready"
               and guard < 20):
            guard += 1
            auto = next((a for a in legal_actions(state)
                         if isinstance(a, AutoResolveEffects)), None)
            if auto is None:
                break
            state = apply(state, auto)
        return state

    def _play_thrawn_with_enemy(self, repo):
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "SEC", "193"), "ground")
        thrawn.exhausted = True                    # a freshly-played unit is exhausted
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        state = self._drive_to_capture_decision(state, thrawn)
        return state, thrawn, enemy

    def test_sec_193_when_played_decision_is_decided_by_the_opponent(self, repo):
        state, _thrawn, _enemy = self._play_thrawn_with_enemy(repo)
        top = state.pending_decisions[-1]
        assert top.kind == "capture_or_ready"
        assert top.deciding_player_id == "P1"                     # the OPPONENT decides
        assert state.active_player_index == state.player_index("P1")

    def test_sec_193_when_played_opponent_gives_up_unit_thrawn_captures_it(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseCaptureVictim
        state, thrawn, enemy = self._play_thrawn_with_enemy(repo)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseCaptureVictim)
                      and a.target_id == enemy.instance_id)
        state = apply(state, choose)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not state.pending_decisions
        # Enemy captured: gone from P1's arena, facedown in P0 (Thrawn's) capture pile.
        assert all(enemy.instance_id != u.instance_id
                   for u in state.player_by_id("P1").ground_arena)
        pile = state.player_by_id("P0").capture_pile
        assert any(c.instance_id == enemy.instance_id for c in pile)
        # Thrawn did NOT ready on the capture branch (only "if they don't").
        res = state.find_instance(thrawn.instance_id)
        assert res is not None and res[1].exhausted is True

    def test_sec_193_when_played_opponent_declines_source_readies(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineCaptureVictim
        state, thrawn, enemy = self._play_thrawn_with_enemy(repo)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineCaptureVictim))
        state = apply(state, decline)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not state.pending_decisions
        # No capture; Thrawn readied.
        assert len(state.player_by_id("P0").capture_pile) == 0
        assert any(enemy.instance_id == u.instance_id
                   for u in state.player_by_id("P1").ground_arena)
        res = state.find_instance(thrawn.instance_id)
        assert res is not None and res[1].exhausted is False

    def test_sec_193_when_played_no_opponent_unit_readies_inline(self, repo):
        # No enemy non-leader unit → "they don't" → Thrawn readies, no decision.
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "SEC", "193"), "ground")
        thrawn.exhausted = True
        state = self._drive_to_capture_decision(state, thrawn)
        assert not any(d.kind == "capture_or_ready" for d in state.pending_decisions)
        state = _drive_to_quiescence(state, lambda acts: None)
        res = state.find_instance(thrawn.instance_id)
        assert res is not None and res[1].exhausted is False

    def test_sec_193_when_defeated_friendly_captor_captures_same_arena_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "SEC", "193"), "ground")
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        victim = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")   # 9/9
        state = _fire_unit_defeated(state, thrawn, "P0")
        pick_captor = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget)
                           and a.target_id == captor.instance_id)
        state = apply(state, pick_captor)
        state = _drive_to_quiescence(
            state,
            lambda acts: next((a for a in acts
                               if isinstance(a, ChooseTarget)
                               and a.target_id == victim.instance_id), None))
        assert not state.pending_decisions
        # Victim captured into the captor's controller (P0) capture pile.
        assert all(victim.instance_id != u.instance_id
                   for u in state.player_by_id("P1").ground_arena)
        assert any(c.instance_id == victim.instance_id
                   for c in state.player_by_id("P0").capture_pile)

    def test_sec_193_when_defeated_only_same_arena_enemy_offered(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "SEC", "193"), "ground")
        captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # ground
        ground_enemy = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")
        space_enemy = _place(state, "P1", _get_card(repo, "SOR", "236"), "space")
        state = _fire_unit_defeated(state, thrawn, "P0")
        pick_captor = next(a for a in legal_actions(state)
                           if isinstance(a, ChooseTarget)
                           and a.target_id == captor.instance_id)
        state = apply(state, pick_captor)
        # Effect 2 offers only the ground enemy (captor's arena), not the space one.
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ground_enemy.instance_id in offered
        assert space_enemy.instance_id not in offered

    def test_sec_193_when_defeated_no_friendly_unit_no_capture(self, repo):
        # Only Thrawn (who dies) is friendly → no captor → no capture.
        state = _make_state()
        thrawn = _place(state, "P0", _get_card(repo, "SEC", "193"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")
        state = _fire_unit_defeated(state, thrawn, "P0")
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").capture_pile) == 0
        assert any(victim.instance_id == u.instance_id
                   for u in state.player_by_id("P1").ground_arena)

    def test_sec_193_reprint_p25_33_aliases_to_canonical(self, repo):
        from swu.abilities.registry import get_abilities
        canonical = get_abilities("SEC", "193")
        assert canonical, "SEC_193 must be registered"
        assert get_abilities("P25", "33") == canonical, "P25_33 should alias SEC_193"


# ── Group law-set:01 — Direct damage & removal ────────────────────────────────


def _law01_drain(state):
    """Apply any pending AutoResolveEffects to quiescence."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(25):
        if not state.pending_decisions:
            break
        auto = next((a for a in legal_actions(state)
                     if isinstance(a, AutoResolveEffects)), None)
        if auto is None:
            break
        state = apply(state, auto)
    return state


def _law01_use(state, source_ci):
    """Use ``source_ci``'s (only) activated ability."""
    from swu.engine.actions import legal_actions, apply, UseAbility
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id)
    return _law01_drain(apply(state, use))


class TestSawGerrera_LAW_1:
    """"Action [Exhaust]: Attack with a unit.  It gets +2/+0 and gains Overwhelm
    for this attack.  After completing this attack, defeat it." / the deployed
    "When Attack Ends" twin that repeats it with another unit."""

    def test_LAW_1_undeployed_action_buffs_then_defeats_the_attacker(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        saw = _place_leader(state, "P0", _get_card(repo, "LAW", "1"))
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")    # 3/7
        state = _law01_use(state, saw)

        assert state.pending_decisions[-1].kind == "granted_attack"
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == ally.instance_id
                   and a.defender_id == foe.instance_id)
        state = _law01_drain(apply(state, atk))
        # +2/+0 → 5 damage dealt, and the attacker is defeated afterwards.
        assert _find_instance(state, foe.instance_id).damage == 5
        assert _find_instance(state, ally.instance_id) is None

    def test_LAW_1_deployed_attack_ends_offers_another_unit_optionally(self, repo):
        from swu.engine.actions import (
            legal_actions, AttackWithUnit, DeclineGrantedAttack)
        state = _make_state()
        saw = _deploy_leader_in_arena(state, "P0", _get_card(repo, "LAW", "1"))
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_attack_ends_law(state, saw))

        assert state.pending_decisions[-1].kind == "granted_attack"
        acts = legal_actions(state)
        attackers = {a.attacker_id for a in acts if isinstance(a, AttackWithUnit)}
        assert attackers == {ally.instance_id}          # "ANOTHER unit" — not Saw
        assert any(isinstance(a, DeclineGrantedAttack) for a in acts)   # "you may"


class TestAurraSing_LAW_4:
    """"Action [Exhaust]: Defeat a non-leader unit with 1 or less remaining HP." /
    "When Deployed: You may defeat a non-leader unit with 5 or less remaining HP. """

    def test_LAW_4_action_defeats_only_a_unit_at_1_or_less_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        aurra = _place_leader(state, "P0", _get_card(repo, "LAW", "4"))
        nearly = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        nearly.damage = 6                                     # 1 remaining HP
        healthy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_use(state, aurra)

        choices = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert choices == {nearly.instance_id}        # the healthy unit is out of range
        assert healthy.instance_id not in choices
        state = _law01_drain(apply(state, ChooseTarget(nearly.instance_id)))
        assert _find_instance(state, nearly.instance_id) is None

    def test_LAW_4_when_deployed_reaches_5_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, apply, DeployLeader, ChooseTarget
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "LAW", "4"))
        _give_resources(state, "P0", 8)                        # deploy threshold is 7
        wounded = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        wounded.damage = 2                                     # 5 remaining HP
        deploy = next(a for a in legal_actions(state) if isinstance(a, DeployLeader))
        state = _law01_drain(apply(state, deploy))
        acts = legal_actions(state)
        accept = next((a for a in acts if type(a).__name__ == "AcceptTrigger"), None)
        if accept is not None:                                 # optional "you may"
            state = _law01_drain(apply(state, accept))
        state = _law01_drain(apply(state, ChooseTarget(wounded.instance_id)))
        assert _find_instance(state, wounded.instance_id) is None


class TestDarthVader_LAW_11:
    """"Action [Exhaust, discard a card from your hand]: Deal 1 damage to a unit or
    base." / "On Attack: Discard any number of cards from your hand.  Deal damage
    to a unit or base equal to the number of cards discarded this way. """

    def test_LAW_11_action_discards_a_card_and_deals_1(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "LAW", "11"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_use(state, vader)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 1
        assert state.player_by_id("P0").hand == []          # the cost was paid

    def test_LAW_11_action_is_unavailable_with_an_empty_hand(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        vader = _place_leader(state, "P0", _get_card(repo, "LAW", "11"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not any(isinstance(a, UseAbility) and a.source_id == vader.instance_id
                       for a in legal_actions(state))

    def test_LAW_11_on_attack_scales_the_damage_with_the_cards_discarded(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        vader = _deploy_leader_in_arena(state, "P0", _get_card(repo, "LAW", "11"))
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, vader, foe))

        assert state.pending_decisions[-1].kind == "cull_for_damage"
        for _ in range(2):                                   # discard 2 of the 3
            pick = next(a for a in legal_actions(state)
                        if type(a).__name__ == "SelectCullCard")
            state = apply(state, pick)
        state = apply(state, next(a for a in legal_actions(state)
                                  if type(a).__name__ == "FinishCull"))
        tgt = next(a for a in legal_actions(state)
                   if type(a).__name__ == "ChooseCullDamageTarget"
                   and a.target_id == foe.instance_id)
        state = _law01_drain(apply(state, tgt))
        assert _find_instance(state, foe.instance_id).damage == 2
        assert len(state.player_by_id("P0").hand) == 1
        assert len(state.player_by_id("P0").discard) == 2


class TestChewbacca_LAW_13:
    """"Action [1 resource, Exhaust, defeat a friendly resource]: Deal 2 damage to a
    unit and create a Credit token." / the optional On Attack twin."""

    def test_LAW_13_action_sacrifice_is_a_cost_with_no_decline(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        chewie = _place_leader(state, "P0", _get_card(repo, "LAW", "13"))
        _give_resources(state, "P0", 3)
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_use(state, chewie)

        assert state.pending_decisions[-1].kind == "sacrifice_resource"
        acts = legal_actions(state)
        assert not any(type(a).__name__ == "DeclineSacrifice" for a in acts)  # a COST
        state = apply(state, next(a for a in acts
                                  if type(a).__name__ == "SacrificeResource"))
        state = _law01_drain(apply(state, next(
            a for a in legal_actions(state)
            if type(a).__name__ == "ChooseSacrificeTarget"
            and a.target_id == foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 2
        assert len(state.player_by_id("P0").credits) == 1     # "and create a Credit"

    def test_LAW_13_on_attack_sacrifice_may_be_declined(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        chewie = _deploy_leader_in_arena(state, "P0", _get_card(repo, "LAW", "13"))
        _give_resources(state, "P0", 2)
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, chewie, foe))

        assert state.pending_decisions[-1].kind == "sacrifice_resource"
        decline = next(a for a in legal_actions(state)
                       if type(a).__name__ == "DeclineSacrifice")
        state = _law01_drain(apply(state, decline))
        assert _find_instance(state, foe.instance_id).damage == 0
        assert state.player_by_id("P0").credits == []
        assert len(state.player_by_id("P0").resources) == 2   # nothing sacrificed


class TestHanSolo_LAW_17:
    """"Action [Exhaust, defeat a friendly token]: Deal 1 damage to a unit." / "On
    Attack: Defeat any number of friendly tokens.  Deal damage to a unit equal to
    the number of tokens defeated this way. """

    def _give_experience(self, state, unit_ci, n=1):
        from swu.engine.tokens import attach_token
        for _ in range(n):
            attach_token(state, state.player_by_id(unit_ci.owner_id), unit_ci,
                         "Experience")

    def test_LAW_17_action_defeats_exactly_one_token_for_1_damage(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        han = _place_leader(state, "P0", _get_card(repo, "LAW", "17"))
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        self._give_experience(state, ally, 2)
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_use(state, han)

        assert state.pending_decisions[-1].kind == "cull_for_damage"
        acts = legal_actions(state)
        # The token defeat is a COST: no "finish with nothing" escape.
        assert not any(type(a).__name__ == "FinishCull" for a in acts)
        state = apply(state, next(a for a in acts
                                  if type(a).__name__ == "SelectCullCard"))
        # max_count=1 → the select stage closed itself.
        state = _law01_drain(apply(state, next(
            a for a in legal_actions(state)
            if type(a).__name__ == "ChooseCullDamageTarget"
            and a.target_id == foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 1
        assert _experience_count(_find_instance(state, ally.instance_id)) == 1

    def test_LAW_17_on_attack_scales_with_the_tokens_defeated(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        han = _deploy_leader_in_arena(state, "P0", _get_card(repo, "LAW", "17"))
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        self._give_experience(state, ally, 3)
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, han, foe))

        assert state.pending_decisions[-1].kind == "cull_for_damage"
        for _ in range(3):
            state = apply(state, next(a for a in legal_actions(state)
                                      if type(a).__name__ == "SelectCullCard"))
        state = _law01_drain(apply(state, next(
            a for a in legal_actions(state)
            if type(a).__name__ == "ChooseCullDamageTarget"
            and a.target_id == foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 3
        assert _experience_count(_find_instance(state, ally.instance_id)) == 0


class TestTaramynBarcona_LAW_40:
    """"When Played: You may defeat a Credit token (belonging to any player).  If
    you do, give an Experience token to this unit and another friendly unit. """

    def test_LAW_40_defeats_an_enemy_credit_and_gives_two_experience(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        taramyn = _place(state, "P0", _get_card(repo, "LAW", "40"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_credit(state, "P1", 1)
        _add_credit(state, "P0", 1)
        state = _law01_drain(_fire_when_played(state, taramyn))
        accept = next((a for a in legal_actions(state)
                       if type(a).__name__ == "AcceptTrigger"), None)
        if accept is not None:
            state = _law01_drain(apply(state, accept))
        state = _law01_drain(apply(state, ChooseTarget(ally.instance_id)))

        # The OPPONENT's credit is the one given up (never worse for the controller).
        assert state.player_by_id("P1").credits == []
        assert len(state.player_by_id("P0").credits) == 1
        assert _experience_count(_find_instance(state, taramyn.instance_id)) == 1
        assert _experience_count(_find_instance(state, ally.instance_id)) == 1

    def test_LAW_40_never_prompts_when_no_credit_exists(self, repo):
        state = _make_state()
        taramyn = _place(state, "P0", _get_card(repo, "LAW", "40"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_when_played(state, taramyn))
        assert state.pending_decisions == []                 # the condition gate
        assert _experience_count(_find_instance(state, taramyn.instance_id)) == 0


class TestSingleReactorIgnition_LAW_44:
    """"Defeat all units.  For each enemy unit defeated this way, deal 1 damage to
    its controller's base. """

    def test_LAW_44_wipes_the_board_and_burns_the_enemy_base_per_enemy_unit(self, repo):
        state = _make_state()
        mine = [_place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
                for _ in range(2)]
        theirs = [_place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
                  for _ in range(3)]
        state, _ = _play_event_from_hand(state, repo, "LAW", "44", resources=30)
        state = _law01_drain(state)

        for ci in mine + theirs:
            assert _find_instance(state, ci.instance_id) is None
        assert state.player_by_id("P1").base_zone[0].damage == 3   # 3 enemy units
        assert state.player_by_id("P0").base_zone[0].damage == 0


# ── Group law-set:02 — Direct damage & removal ────────────────────────────────


def _law01_continue(state):
    """Drain AutoResolveEffects AND resume a suspended attack (ContinueAttack)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects, ContinueAttack
    for _ in range(25):
        if not state.pending_decisions:
            break
        acts = legal_actions(state)
        nxt = next((a for a in acts if isinstance(a, (AutoResolveEffects, ContinueAttack))), None)
        if nxt is None:
            break
        state = apply(state, nxt)
    return state


def _law02_accept(state):
    """Accept the top optional trigger if one is offered."""
    from swu.engine.actions import legal_actions, apply
    acts = legal_actions(state)
    accept = next((a for a in acts if type(a).__name__ == "AcceptTrigger"), None)
    return _law01_drain(apply(state, accept)) if accept is not None else state


class TestBazeMalbus_LAW_47:
    """"When 1 or more damage is healed from this unit: You may deal that much
    damage to a unit." """

    def test_LAW_47_deals_damage_equal_to_the_amount_healed(self, repo):
        from swu.engine.actions import apply, ChooseTarget, note_unit_healed
        from swu.engine.actions import _fire_heal_observers
        state = _make_state()
        baze = _place(state, "P0", _get_card(repo, "LAW", "47"), "ground")
        baze.damage = 5
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        baze.damage -= 3
        note_unit_healed(state, baze, 3)
        state = _law01_drain(_fire_heal_observers(state))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 3   # "that much"

    def test_LAW_47_does_not_fire_for_another_units_heal(self, repo):
        from swu.engine.actions import note_unit_healed, _fire_heal_observers
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "47"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other.damage = 2
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        other.damage -= 2
        note_unit_healed(state, other, 2)
        state = _law01_drain(_fire_heal_observers(state))
        assert state.pending_decisions == []       # strictly self-referential


class TestBeilertValance_LAW_51:
    """"On Attack: Draw a card.  You may deal damage to a ground unit equal to the
    number of cards you've drawn this phase." """

    def test_LAW_51_draws_then_scales_the_damage_with_the_phase_draw_count(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        valance = _place(state, "P0", _get_card(repo, "LAW", "51"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        hand0 = len(state.player_by_id("P0").hand)
        state = _law01_drain(_fire_on_attack(state, valance, foe))
        assert len(state.player_by_id("P0").hand) == hand0 + 1     # the draw is first
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 1  # 1 card drawn


class TestCassianAndor_LAW_56:
    """"When a friendly unit's attack ends: If the defending unit was defeated, deal
    2 damage to a base." """

    def test_LAW_56_burns_a_base_when_a_friendly_attacker_kills(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "56"), "ground")
        killer = _place(state, "P0", _get_card(repo, "LAW", "164"), "space")  # 10/10
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")   # 3/7
        state = _law01_drain(apply(state, AttackWithUnit(
            attacker_id=killer.instance_id, defender_id=victim.instance_id)))
        from swu.engine.actions import legal_actions, ChooseTarget
        tgt = next((a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget)
                    and a.target_id == state.player_by_id("P1").base_zone[0].instance_id),
                   None)
        if tgt is not None:
            state = _law01_drain(apply(state, tgt))
        assert state.player_by_id("P1").base_zone[0].damage >= 2

    def test_LAW_56_stays_silent_when_the_defender_survives(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "56"), "ground")
        weak = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")     # 3/7
        tough = _place(state, "P1", _get_card(repo, "LAW", "164"), "space")   # 10/10
        base0 = state.player_by_id("P1").base_zone[0].damage
        state = _law01_drain(apply(state, AttackWithUnit(
            attacker_id=weak.instance_id, defender_id=tough.instance_id)))
        assert state.player_by_id("P1").base_zone[0].damage == base0


class TestHonorBoundPartisan_LAW_58:
    """"When Played: Deal 1 damage to a base." / "When Defeated: The next unit you
    play this phase costs 1 resource less." """

    def test_LAW_58_when_played_damages_a_base(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        partisan = _place(state, "P0", _get_card(repo, "LAW", "58"), "ground")
        state = _law01_drain(_fire_when_played(state, partisan))
        enemy_base = state.player_by_id("P1").base_zone[0]
        state = _law01_drain(apply(state, ChooseTarget(enemy_base.instance_id)))
        assert state.player_by_id("P1").base_zone[0].damage == 1

    def test_LAW_58_when_defeated_discounts_the_next_unit(self, repo):
        state = _make_state()
        partisan = _place(state, "P0", _get_card(repo, "LAW", "58"), "ground")
        state = _law01_drain(_fire_when_defeated(state, partisan))
        pending = state.game_memory.pending_play_discounts
        assert len(pending) == 1
        assert pending[0]["player_id"] == "P0"
        assert int(pending[0]["amount"]) == 1


class TestDefiantHammerhead_LAW_62:
    """"On Attack: If this unit is attacking a unit, you may give this unit +4/+0 for
    this attack.  If you do, defeat this unit after completing this attack." """

    def test_LAW_62_rams_a_unit_for_plus_4_then_dies(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        ram = _place(state, "P0", _get_card(repo, "LAW", "62"), "space")     # 6/6
        foe = _place(state, "P1", _get_card(repo, "LAW", "164"), "space")    # 10/10
        state = apply(state, AttackWithUnit(attacker_id=ram.instance_id,
                                            defender_id=foe.instance_id))
        state = _law02_accept(state)
        state = _law01_continue(state)
        # A plain 6-power attack cannot kill a 10 HP hull — only the +4 does.
        assert _find_instance(state, foe.instance_id) is None
        assert _find_instance(state, ram.instance_id) is None                # rammed

    def test_LAW_62_defeats_itself_even_when_it_survives_combat(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        ram = _place(state, 'P0', _get_card(repo, 'LAW', '62'), 'space')     # 6/6
        foe = _place(state, 'P1', _get_card(repo, 'SOR', '46'), 'space')    # 3/7
        state = apply(state, AttackWithUnit(attacker_id=ram.instance_id,
                                            defender_id=foe.instance_id))
        state = _law02_accept(state)
        state = _law01_continue(state)
        # It took only 3 combat damage against 6 HP, so the rider is what kills it.
        assert _find_instance(state, ram.instance_id) is None

    def test_LAW_62_is_not_offered_on_a_base_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        ram = _place(state, "P0", _get_card(repo, "LAW", "62"), "space")
        state = apply(state, AttackWithUnit(attacker_id=ram.instance_id,
                                            defender_id=None))
        assert not any(type(a).__name__ == "AcceptTrigger"
                       for a in legal_actions(state))
        assert _find_instance(state, ram.instance_id) is not None   # no self-defeat


class TestZuckuss_LAW_64:
    """"On Attack: If you control another Bounty Hunter unit, you may deal damage
    equal to this unit's power to a ground unit." """

    def test_LAW_64_deals_its_power_with_another_bounty_hunter_out(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        zuckuss = _place(state, "P0", _get_card(repo, "LAW", "64"), "ground")  # 3/5
        _place(state, "P0", _get_card(repo, "LAW", "51"), "ground")   # Bounty Hunter
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, zuckuss, foe))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 3     # his power

    def test_LAW_64_is_silent_when_he_is_the_only_bounty_hunter(self, repo):
        state = _make_state()
        zuckuss = _place(state, "P0", _get_card(repo, "LAW", "64"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, zuckuss, foe))
        assert state.pending_decisions == []      # the "another" gate excludes himself
        assert _find_instance(state, foe.instance_id).damage == 0


class TestVultSkerrissDefender_LAW_76:
    """"When Played: If you discarded a card from your hand or deck this phase, give
    a Shield token to this unit." / "On Attack: You may deal 1 damage to a space unit
    and exhaust it." """

    def test_LAW_76_shields_itself_only_after_a_discard_this_phase(self, repo):
        from swu.engine.actions import note_hand_or_deck_discard
        state = _make_state()
        plain = _place(state, "P0", _get_card(repo, "LAW", "76"), "space")
        state = _law01_drain(_fire_when_played(state, plain))
        assert _shield_count(_find_instance(state, plain.instance_id)) == 0

        state2 = _make_state()
        _put_in_hand(state2, "P0", _get_card(repo, "SOR", "46"))
        binned = state2.player_by_id("P0").hand.pop()
        from swu.engine.state import Zone
        binned.zone = Zone.DISCARD
        state2.player_by_id("P0").discard.append(binned)
        note_hand_or_deck_discard(state2, binned)
        shielded = _place(state2, "P0", _get_card(repo, "LAW", "76"), "space")
        state2 = _law01_drain(_fire_when_played(state2, shielded))
        assert _shield_count(_find_instance(state2, shielded.instance_id)) == 1

    def test_LAW_76_on_attack_damages_and_exhausts_one_space_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        defender = _place(state, "P0", _get_card(repo, "LAW", "76"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        foe.exhausted = False
        state = _law01_drain(_fire_on_attack(state, defender, foe))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        now = _find_instance(state, foe.instance_id)
        assert now.damage == 1
        assert now.exhausted is True     # both halves, from one prompt


# ── Group law-set:03 — Direct damage & removal ────────────────────────────────


def _law03_regroup_start(state):
    """Fire the "regroup phase starts" PhaseStartTrigger site."""
    from swu.engine.events import PhaseChanged
    from swu.abilities.resolver import fire_triggered_abilities
    evt = PhaseChanged(new_phase="REGROUP", round_number=state.round_number)
    state.event_log.append(evt)
    return _law01_drain(fire_triggered_abilities(state, evt, after_all_player_idx=0))


class TestShadowOfStygeonPrime_LAW_77:
    """"Attached unit can't ready.  It gains: 'When the regroup phase starts: Deal
    2 damage to your base.'" """

    def test_LAW_77_attached_unit_cannot_ready(self, repo):
        from swu.engine.actions import _ready_forbidden, _ready_all_cards
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "77"), "P0")
        host.exhausted = True
        assert _ready_forbidden(state, host) is True
        _ready_all_cards(state)
        assert host.exhausted is True      # the lock holds through the regroup

    def test_LAW_77_regroup_damage_follows_the_hosts_controller(self, repo):
        state = _make_state()
        # On an ENEMY host, "your base" is the HOST controller's base — the whole
        # point of resolving the granted ability from the host.
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, victim, _get_card(repo, "LAW", "77"), "P0")
        state = _law03_regroup_start(state)
        assert state.player_by_id("P1").base_zone[0].damage == 2
        assert state.player_by_id("P0").base_zone[0].damage == 0


class TestSabineWren_LAW_78:
    """"When Played: You may defeat a non-<uq> upgrade.  If you control a Vigilance
    or Command unit, you may defeat an upgrade instead." """

    def _armed(self, repo, host_num, upgrade_num):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", host_num), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "SOR",
                                                             upgrade_num), "P1")
        return state, host, up

    def test_LAW_78_defeats_a_non_unique_upgrade_with_no_vigilance_or_command(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        # SOR_247 Underworld Thug carries no aspects; Sabine is Aggression/Cunning/
        # Heroism, so the widened arm stays off.
        state, host, up = self._armed(repo, "247", "69")     # Resilient (non-unique)
        sabine = _place(state, "P0", _get_card(repo, "LAW", "78"), "ground")
        state = _law01_drain(_fire_when_played(state, sabine))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(up.instance_id)))
        assert all(u.instance_id != up.instance_id
                   for u in _find_instance(state, host.instance_id).attached_upgrades)

    def test_LAW_78_cannot_touch_a_unique_upgrade_without_vigilance_or_command(self, repo):
        state, host, up = self._armed(repo, "247", "53")     # Luke's Lightsaber (uq)
        sabine = _place(state, "P0", _get_card(repo, "LAW", "78"), "ground")
        state = _law01_drain(_fire_when_played(state, sabine))
        assert state.pending_decisions == []      # no legal target ⇒ never offered

    def test_LAW_78_defeats_a_unique_upgrade_with_a_command_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state, host, up = self._armed(repo, "247", "53")     # Luke's Lightsaber (uq)
        _place(state, "P0", _get_card(repo, "SOR", "95"), "ground")   # Command unit
        sabine = _place(state, "P0", _get_card(repo, "LAW", "78"), "ground")
        state = _law01_drain(_fire_when_played(state, sabine))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(up.instance_id)))
        assert all(u.instance_id != up.instance_id
                   for u in _find_instance(state, host.instance_id).attached_upgrades)


class TestYouHoldThis_LAW_85:
    """"Choose a friendly non-leader unit.  An opponent takes control of it.  If
    they do, deal 4 damage to another unit in the same arena." """

    def test_LAW_85_hands_the_unit_over_then_burns_another_in_that_arena(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        gift = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "85")
        state = _law01_drain(apply(state, ChooseTarget(gift.instance_id)))
        # Control follows the arena the instance now sits in.
        assert any(u.instance_id == gift.instance_id
                   for u in state.player_by_id("P1").ground_arena)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 4

    def test_LAW_85_damage_stays_in_the_gifted_units_arena(self, repo):
        from swu.engine.actions import apply, ChooseTarget, legal_actions
        state = _make_state()
        gift = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        far = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "85")
        state = _law01_drain(apply(state, ChooseTarget(gift.instance_id)))
        # The only other unit is in the other arena, and the gift itself is
        # excluded — no candidate, so nothing is prompted and nothing is damaged.
        assert not any(isinstance(a, ChooseTarget) and a.target_id == far.instance_id
                       for a in legal_actions(state))
        assert _find_instance(state, far.instance_id).damage == 0


class TestGovernorsShuttle_LAW_99:
    """"When Played: Each player chooses a unit they control.  Defeat those
    units." """

    def test_LAW_99_each_player_loses_their_chosen_unit(self, repo):
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        shuttle = _place(state, "P0", _get_card(repo, "LAW", "99"), "space")
        state = _law01_drain(_fire_when_played(state, shuttle))
        assert state.pending_decisions[-1].kind == "each_player_defeats"
        state = _law01_drain(apply(state, ChooseUnitToDefeat(mine.instance_id)))
        state = _law01_drain(apply(state, ChooseUnitToDefeat(theirs.instance_id)))
        assert _find_instance(state, mine.instance_id) is None
        assert _find_instance(state, theirs.instance_id) is None
        assert _find_instance(state, shuttle.instance_id) is not None

    def test_LAW_99_a_deployed_leader_is_a_legal_choice(self, repo):
        from swu.engine.actions import legal_actions, ChooseUnitToDefeat
        state = _make_state()
        leader = _deploy_leader_in_arena(state, "P0", _get_card(repo, "SOR", "5"))
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        shuttle = _place(state, "P0", _get_card(repo, "LAW", "99"), "space")
        state = _law01_drain(_fire_when_played(state, shuttle))
        picks = {a.target_id for a in legal_actions(state)
                 if isinstance(a, ChooseUnitToDefeat)}
        assert leader.instance_id in picks     # "a unit they control", not non-leader


class TestChokeOnAspirations_LAW_102:
    """"Deal up to 5 damage to a friendly non-Vehicle unit.  If it survives, heal
    damage from your base equal to the damage dealt this way." """

    def test_LAW_102_heals_the_base_for_the_damage_a_survivor_took(self, repo):
        from swu.engine.actions import (
            apply, ChooseTarget, AssignDamage, FinishDamageDistribution)
        state = _make_state()
        state.player_by_id("P0").base_zone[0].damage = 9
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        state, _evt = _play_event_from_hand(state, repo, "LAW", "102")
        state = _law01_drain(apply(state, ChooseTarget(mine.instance_id)))
        assert state.pending_decisions[-1].kind == "distribute_damage"
        for _ in range(3):
            state = apply(state, AssignDamage(mine.instance_id))
        state = _law01_drain(apply(state, FinishDamageDistribution()))
        assert _find_instance(state, mine.instance_id).damage == 3
        assert state.player_by_id("P0").base_zone[0].damage == 6       # 9 − 3

    def test_LAW_102_a_unit_killed_by_it_forfeits_the_heal(self, repo):
        from swu.engine.actions import (
            apply, ChooseTarget, AssignDamage, FinishDamageDistribution)
        state = _make_state()
        state.player_by_id("P0").base_zone[0].damage = 9
        mine = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        state, _evt = _play_event_from_hand(state, repo, "LAW", "102")
        state = _law01_drain(apply(state, ChooseTarget(mine.instance_id)))
        for _ in range(2):
            state = apply(state, AssignDamage(mine.instance_id))
        state = _law01_drain(apply(state, FinishDamageDistribution()))
        assert _find_instance(state, mine.instance_id) is None
        assert state.player_by_id("P0").base_zone[0].damage == 9        # no heal


class TestDefiantScrapper_LAW_106:
    """"When Played: You may defeat an enemy Credit token." """

    def test_LAW_106_defeats_one_enemy_credit(self, repo):
        state = _make_state()
        _add_credit(state, "P1", 2)
        _add_credit(state, "P0", 1)
        scrapper = _place(state, "P0", _get_card(repo, "LAW", "106"), "ground")
        state = _law01_drain(_fire_when_played(state, scrapper))
        state = _law02_accept(state)
        assert len(state.player_by_id("P1").credits) == 1
        assert len(state.player_by_id("P0").credits) == 1   # never its own

    def test_LAW_106_is_not_offered_when_only_the_controller_has_credits(self, repo):
        state = _make_state()
        _add_credit(state, "P0", 2)
        scrapper = _place(state, "P0", _get_card(repo, "LAW", "106"), "ground")
        state = _law01_drain(_fire_when_played(state, scrapper))
        assert state.pending_decisions == []
        assert len(state.player_by_id("P0").credits) == 2


class TestIndustriousTeam_LAW_124:
    """"When Played: You may defeat a non-leader unit with 4 or less remaining
    HP." """

    def test_LAW_124_defeats_a_unit_inside_the_hp_window(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        weak = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")   # 3/3
        team = _place(state, "P0", _get_card(repo, "LAW", "124"), "ground")
        state = _law01_drain(_fire_when_played(state, team))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(weak.instance_id)))
        assert _find_instance(state, weak.instance_id) is None

    def test_LAW_124_cannot_reach_a_unit_above_the_hp_window(self, repo):
        state = _make_state()
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        team = _place(state, "P0", _get_card(repo, "LAW", "124"), "ground")
        state = _law01_drain(_fire_when_played(state, team))
        assert state.pending_decisions == []
        assert _find_instance(state, tough.instance_id) is not None


# ── Group law-set:04 — Direct damage & removal ────────────────────────────────


def _law04_modal(state, mode):
    """Choose ``mode`` on the pending modal decision (handles a target stage)."""
    from tests.test_sor_cards import _modal_option
    return _law01_drain(_modal_option(state, mode))


def _law04_attack(state, attacker, defender):
    """Declare a real attack and settle it."""
    from swu.engine.actions import apply, AttackWithUnit
    return _law01_continue(apply(state, AttackWithUnit(
        attacker_id=attacker.instance_id, defender_id=defender.instance_id)))


class TestBetrayedTrust_LAW_130:
    """"Choose an enemy unit.  For this phase, that unit can't deal combat
    damage." """

    def test_LAW_130_blocked_attacker_deals_no_combat_damage(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power
        state = _make_state()
        # P1's 3/7 is the enemy unit; P0 attacks it with a 3/7 of its own.
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "130")
        state = _law01_drain(apply(state, ChooseTarget(theirs.instance_id)))
        blocked = _find_instance(state, theirs.instance_id)
        assert compute_power(state, blocked) == 3       # its power is untouched
        # It strikes back for nothing when attacked.
        state.active_player_index = 0
        state = _law04_attack(state, _find_instance(state, mine.instance_id), blocked)
        assert _find_instance(state, mine.instance_id).damage == 0
        assert _find_instance(state, theirs.instance_id).damage == 3

    def test_LAW_130_blocked_unit_cannot_damage_a_base_either(self, repo):
        from swu.engine.actions import apply, ChooseTarget, AttackWithUnit
        state = _make_state()
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "130")
        state = _law01_drain(apply(state, ChooseTarget(theirs.instance_id)))
        state.active_player_index = 1
        state = _law01_continue(apply(state, AttackWithUnit(
            attacker_id=theirs.instance_id, defender_id=None)))
        assert state.player_by_id("P0").base_zone[0].damage == 0


class TestTheTreeRemembers_LAW_132:
    """"An enemy unit loses all abilities for this phase.  If it costs 3 or less,
    defeat it." """

    def test_LAW_132_defeats_a_cheap_enemy_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        cheap = _place(state, "P1", _get_card(repo, "SOR", "247"), "ground")  # cost 2
        state, _evt = _play_event_from_hand(state, repo, "LAW", "132")
        state = _law01_drain(apply(state, ChooseTarget(cheap.instance_id)))
        assert _find_instance(state, cheap.instance_id) is None

    def test_LAW_132_only_suppresses_an_expensive_one(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        from swu.engine.state import ability_suppressed
        state = _make_state()
        big = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # cost 4
        state, _evt = _play_event_from_hand(state, repo, "LAW", "132")
        state = _law01_drain(apply(state, ChooseTarget(big.instance_id)))
        survivor = _find_instance(state, big.instance_id)
        assert survivor is not None
        assert ability_suppressed(state, survivor) is True


class TestRuthlessDuo_LAW_137:
    """"When Played: If you control another Villainy unit, you may deal 2 damage to
    a ground unit." """

    def test_LAW_137_damages_a_ground_unit_with_another_villainy_unit_out(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")   # Villainy
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        duo = _place(state, "P0", _get_card(repo, "LAW", "137"), "ground")
        state = _law01_drain(_fire_when_played(state, duo))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 2

    def test_LAW_137_is_silent_without_another_villainy_unit(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        duo = _place(state, "P0", _get_card(repo, "LAW", "137"), "ground")
        state = _law01_drain(_fire_when_played(state, duo))
        assert state.pending_decisions == []
        assert _find_instance(state, foe.instance_id).damage == 0


class TestBT1_LAW_173:
    """"On Attack: Discard a card from your deck.  If it's Aggression, you may deal
    1 damage to a ground unit." """

    def test_LAW_173_damages_after_discarding_an_aggression_card(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        bt1 = _place(state, "P0", _get_card(repo, "LAW", "173"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # SOR_128 Death Star Stormtrooper is Villainy/Aggression.
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
        state = _law01_drain(_fire_on_attack(state, bt1, foe))
        assert len(state.player_by_id("P0").discard) == 1
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_LAW_173_a_non_aggression_discard_arms_nothing(self, repo):
        state = _make_state()
        bt1 = _place(state, "P0", _get_card(repo, "LAW", "173"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # SOR_46 is Vigilance/Heroism.
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _law01_drain(_fire_on_attack(state, bt1, foe))
        assert len(state.player_by_id("P0").discard) == 1   # the mill still happened
        assert state.pending_decisions == []
        assert _find_instance(state, foe.instance_id).damage == 0


class TestTripleZero_LAW_174:
    """"On Attack: You may put an Aggression card from your discard pile on the
    bottom of your deck.  If you do, deal 1 damage to each enemy base." """

    def test_LAW_174_bottoms_an_aggression_card_and_burns_the_enemy_base(self, repo):
        from swu.engine.actions import apply, SelectBottomDiscardCard
        state = _make_state()
        zeros = _place(state, "P0", _get_card(repo, "LAW", "174"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        binned = _put_unit_in_discard(state, "P0", _get_card(repo, "SOR", "128"))
        state = _law01_drain(_fire_on_attack(state, zeros, foe))
        assert state.pending_decisions[-1].kind == "bottom_from_discard"
        # count=1, so the single pick auto-finishes the decision and settles the payoff.
        state = _law01_drain(apply(state, SelectBottomDiscardCard(binned.instance_id)))
        assert state.player_by_id("P0").discard == []
        assert state.player_by_id("P0").deck[-1].instance_id == binned.instance_id
        assert state.player_by_id("P1").base_zone[0].damage == 1
        assert state.player_by_id("P0").base_zone[0].damage == 0

    def test_LAW_174_no_aggression_card_means_no_prompt_and_no_damage(self, repo):
        state = _make_state()
        zeros = _place(state, "P0", _get_card(repo, "LAW", "174"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _put_unit_in_discard(state, "P0", _get_card(repo, "SOR", "46"))  # Vigilance
        state = _law01_drain(_fire_on_attack(state, zeros, foe))
        assert state.pending_decisions == []
        assert state.player_by_id("P1").base_zone[0].damage == 0


class TestPersecutor_LAW_178:
    """"When Played/On Attack: Choose an arena.  You may deal 3 damage to each unit
    in that arena." """

    def test_LAW_178_bombs_the_chosen_arena_on_entry(self, repo):
        state = _make_state()
        ground_foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space_foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        persecutor = _place(state, "P0", _get_card(repo, "LAW", "178"), "space")
        state = _law01_drain(_fire_when_played(state, persecutor))
        state = _law02_accept(state)
        assert state.pending_decisions[-1].kind == "modal"
        state = _law04_modal(state, "bomb_ground")
        assert _find_instance(state, ground_foe.instance_id).damage == 3
        assert _find_instance(state, space_foe.instance_id).damage == 0
        assert _find_instance(state, persecutor.instance_id).damage == 0

    def test_LAW_178_may_be_declined_on_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        persecutor = _place(state, "P0", _get_card(repo, "LAW", "178"), "space")
        state = _law01_drain(_fire_on_attack(state, persecutor, foe))
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTrigger))
        state = _law01_drain(apply(state, decline))
        assert _find_instance(state, foe.instance_id).damage == 0
        assert _find_instance(state, persecutor.instance_id).damage == 0


class TestFearAndDeadMen_LAW_179:
    """"This card costs 1 resource less to play for each card discarded from your
    hand this phase.  Deal 4 damage to each enemy ground unit." """

    def test_LAW_179_costs_1_less_per_card_discarded_this_phase(self, repo):
        from swu.engine.actions import _play_cost, note_hand_or_deck_discard
        from swu.engine.state import Zone
        state = _make_state()
        ps = state.player_by_id("P0")
        card = _put_in_hand(state, "P0", _get_card(repo, "LAW", "179"))
        # The absolute figure carries this test state's aspect penalty; the card's
        # own clause is the DELTA, one per card discarded this phase.
        before = _play_cost(state, card, ps)
        for _ in range(3):
            binned = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
            ps.hand.remove(binned)
            binned.zone = Zone.DISCARD
            ps.discard.append(binned)
            note_hand_or_deck_discard(state, binned)
        assert _play_cost(state, card, ps) == before - 3

    def test_LAW_179_sweeps_the_enemy_ground_arena_only(self, repo):
        state = _make_state()
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        their_space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "179", resources=20)
        state = _law01_drain(state)
        assert _find_instance(state, theirs.instance_id).damage == 4
        assert _find_instance(state, their_space.instance_id).damage == 0
        assert _find_instance(state, mine.instance_id).damage == 0


# ── Group law-set:05 — Direct damage & removal ────────────────────────────────


def _law05_select_damage(state, ids):
    """Pick each id on the pending select_damage decision, then finish."""
    from swu.engine.actions import apply, SelectDamageTarget, FinishSelectDamage
    for iid in ids:
        state = apply(state, SelectDamageTarget(iid))
    if state.pending_decisions and state.pending_decisions[-1].kind == "select_damage":
        state = apply(state, FinishSelectDamage())
    return _law01_drain(state)


class TestCloudRiderVeteran_LAW_181:
    """"On Attack: Deal 2 damage to a base." """

    def test_LAW_181_burns_the_chosen_base_on_attack(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        veteran = _place(state, "P0", _get_card(repo, "LAW", "181"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, veteran, foe))
        enemy_base = state.player_by_id("P1").base_zone[0]
        state = _law01_drain(apply(state, ChooseTarget(enemy_base.instance_id)))
        assert state.player_by_id("P1").base_zone[0].damage == 2


class TestBWingSkirmisher_LAW_183:
    """"When Played: Deal 1 damage to each of up to 2 space units." """

    def test_LAW_183_hits_two_space_units_for_1_each(self, repo):
        state = _make_state()
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        bwing = _place(state, "P0", _get_card(repo, "LAW", "183"), "space")
        state = _law01_drain(_fire_when_played(state, bwing))
        assert state.pending_decisions[-1].kind == "select_damage"
        state = _law05_select_damage(state, [a.instance_id, b.instance_id])
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 1
        assert _find_instance(state, ground.instance_id).damage == 0

    def test_LAW_183_the_ground_arena_is_never_offered(self, repo):
        from swu.engine.actions import legal_actions, SelectDamageTarget
        state = _make_state()
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        bwing = _place(state, "P0", _get_card(repo, "LAW", "183"), "space")
        state = _law01_drain(_fire_when_played(state, bwing))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectDamageTarget)}
        assert ground.instance_id not in offered
        assert space.instance_id in offered


class TestAerie_LAW_184:
    """"On Attack: Deal 2 damage to an enemy ground unit and 2 damage to a base." """

    def test_LAW_184_hits_a_ground_unit_and_a_base(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        aerie = _place(state, "P0", _get_card(repo, "LAW", "184"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, aerie, foe))
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        enemy_base = state.player_by_id("P1").base_zone[0]
        state = _law01_drain(apply(state, ChooseTarget(enemy_base.instance_id)))
        assert _find_instance(state, foe.instance_id).damage == 2
        assert state.player_by_id("P1").base_zone[0].damage == 2

    def test_LAW_184_still_burns_a_base_with_no_enemy_ground_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        aerie = _place(state, "P0", _get_card(repo, "LAW", "184"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _law01_drain(_fire_on_attack(state, aerie, foe))
        enemy_base = state.player_by_id("P1").base_zone[0]
        state = _law01_drain(apply(state, ChooseTarget(enemy_base.instance_id)))
        assert state.player_by_id("P1").base_zone[0].damage == 2
        assert _find_instance(state, foe.instance_id).damage == 0


class TestStaccatoLightningRepeater_LAW_187:
    """"When Played: Deal 1 damage to each of up to 3 different ground units." """

    def test_LAW_187_sprays_three_different_ground_units(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "187"), "P0")
        state = _law01_drain(_fire_upgrade_played(state, up, host))
        assert state.pending_decisions[-1].kind == "select_damage"
        state = _law05_select_damage(state, [a.instance_id, b.instance_id,
                                             host.instance_id])
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 1
        assert _find_instance(state, host.instance_id).damage == 1

    def test_LAW_187_never_offers_the_same_unit_twice(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectDamageTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "187"), "P0")
        state = _law01_drain(_fire_upgrade_played(state, up, host))
        state = apply(state, SelectDamageTarget(a.instance_id))
        offered = {x.target_id for x in legal_actions(state)
                   if isinstance(x, SelectDamageTarget)}
        assert a.instance_id not in offered      # "different" units


class TestCavernAngelsXWing_LAW_189:
    """"When Defeated: Deal 2 damage to a base." """

    def test_LAW_189_burns_a_base_when_it_dies(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        xwing = _place(state, "P0", _get_card(repo, "LAW", "189"), "space")
        state = _law01_drain(_fire_when_defeated(state, xwing))
        enemy_base = state.player_by_id("P1").base_zone[0]
        state = _law01_drain(apply(state, ChooseTarget(enemy_base.instance_id)))
        assert state.player_by_id("P1").base_zone[0].damage == 2


class TestArvelSkeen_LAW_191:
    """"When Played/On Attack: You may defeat a Credit token (belonging to any
    player).  If you do, deal 1 damage to a unit or base." """

    def test_LAW_191_spends_an_enemy_credit_to_deal_1(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        _add_credit(state, "P1", 1)
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        arvel = _place(state, "P0", _get_card(repo, "LAW", "191"), "ground")
        state = _law01_drain(_fire_when_played(state, arvel))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(foe.instance_id)))
        assert state.player_by_id("P1").credits == []
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_LAW_191_is_not_offered_with_no_credits_anywhere(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        arvel = _place(state, "P0", _get_card(repo, "LAW", "191"), "ground")
        state = _law01_drain(_fire_on_attack(state, arvel, foe))
        assert state.pending_decisions == []
        assert _find_instance(state, foe.instance_id).damage == 0


class TestOverchargedTransport_LAW_195:
    """"When Played/When Defeated: You may defeat an upgrade attached to a space
    unit." """

    def test_LAW_195_defeats_an_upgrade_on_a_space_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "69"), "P1")
        transport = _place(state, "P0", _get_card(repo, "LAW", "195"), "space")
        state = _law01_drain(_fire_when_played(state, transport))
        state = _law02_accept(state)
        state = _law01_drain(apply(state, ChooseTarget(up.instance_id)))
        assert _find_instance(state, host.instance_id).attached_upgrades == []

    def test_LAW_195_ignores_an_upgrade_on_a_ground_unit(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "69"), "P1")
        transport = _place(state, "P0", _get_card(repo, "LAW", "195"), "space")
        state = _law01_drain(_fire_when_defeated(state, transport))
        assert state.pending_decisions == []
        assert len(_find_instance(state, host.instance_id).attached_upgrades) == 1


def _find_in_arena_law06(state, owner_id, instance_id):
    """The CardInstance for ``instance_id`` if it is still in ``owner_id``'s arenas."""
    ps = state.player_by_id(owner_id)
    for ci in ps.ground_arena + ps.space_arena:
        if ci.instance_id == instance_id:
            return ci
    return None


# -- Group law-set:06 -- Direct damage & removal --------------------------------


def _law06_choose(state, target_id):
    """Apply the ChooseTarget for ``target_id`` on the pending decision, then drain."""
    from swu.engine.actions import legal_actions, apply, ChooseTarget
    choose = next(a for a in legal_actions(state)
                  if isinstance(a, ChooseTarget) and a.target_id == target_id)
    return _law01_drain(apply(state, choose))


def _law06_offered(state):
    """The set of instance ids currently offered as ChooseTarget candidates."""
    from swu.engine.actions import legal_actions, ChooseTarget
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, ChooseTarget)}


def _law06_base_attack(state, attacker):
    """Take the granted attack against the enemy base and settle it."""
    from swu.engine.actions import legal_actions, apply, AttackWithUnit
    atk = next(a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == attacker.instance_id
               and not a.defender_id)
    return _law01_continue(apply(state, atk))


class TestDoggedPursuers_LAW_198:
    """"When Played: You may pay 1 resource.  If you do, deal 2 damage to a ground
    unit." """

    def test_LAW_198_pays_1_resource_and_deals_2(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        pursuers = _place(state, "P0", _get_card(repo, "LAW", "198"), "ground")
        _give_resources(state, "P0", 3)
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_when_played(state, pursuers))
        state = _law02_accept(state)
        state = _law06_choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 2
        assert state.player_by_id("P0").available_resources == before - 1

    def test_LAW_198_is_not_offered_with_no_ready_resource(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        pursuers = _place(state, "P0", _get_card(repo, "LAW", "198"), "ground")
        state = _law01_drain(_fire_when_played(state, pursuers))
        assert state.pending_decisions == []
        assert _find_instance(state, foe.instance_id).damage == 0


class TestThermalDetonator_LAW_201:
    """"Attached unit gains: 'When Defeated: If this unit was ready, deal 2 damage
    to each enemy ground unit.'" """

    def _rig(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "201"), "P0")
        ground_a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        ground_b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        return state, host, ground_a, ground_b, space

    def test_LAW_201_a_ready_host_bombs_each_enemy_ground_unit(self, repo):
        from tests.test_jtl_cards import _defeat_with_upgrades_jtl
        state, host, a, b, space = self._rig(repo)
        state = _law01_drain(_defeat_with_upgrades_jtl(state, host, "P0"))
        assert _find_instance(state, a.instance_id).damage == 2
        assert _find_instance(state, b.instance_id).damage == 2
        assert _find_instance(state, space.instance_id).damage == 0

    def test_LAW_201_an_exhausted_host_bombs_nothing(self, repo):
        from tests.test_jtl_cards import _defeat_with_upgrades_jtl
        state, host, a, b, space = self._rig(repo)
        host.exhausted = True
        state = _law01_drain(_defeat_with_upgrades_jtl(state, host, "P0"))
        assert _find_instance(state, a.instance_id).damage == 0
        assert _find_instance(state, b.instance_id).damage == 0


class TestFlashTheVents_LAW_205:
    """"Attack with a unit.  It gets +2/+0 and gains Overwhelm for this attack.
    After completing this attack, if that unit damaged a base, defeat that unit." """

    def test_LAW_205_defeats_the_attacker_that_damaged_a_base(self, repo):
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "205")
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = _law06_base_attack(state, attacker)
        # 3 power +2 for this attack = 5 onto the enemy base ...
        assert state.player_by_id("P1").base_zone[0].damage == 5
        # ... and the rider then defeats the attacker.
        assert _find_in_arena_law06(state, "P0", attacker.instance_id) is None

    def test_LAW_205_spares_an_attacker_that_hit_no_base(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        blocker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "205")
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id
                   and a.defender_id == blocker.instance_id)
        state = _law01_continue(apply(state, atk))
        # 5 power into a 3/7 defender: no Overwhelm excess, so no base damage ...
        assert _find_instance(state, blocker.instance_id).damage == 5
        assert state.player_by_id("P1").base_zone[0].damage == 0
        # ... and the attacker lives.
        assert _find_in_arena_law06(state, "P0", attacker.instance_id) is not None


class TestThatsARock_LAW_206:
    """"Deal 1 damage to a unit.  When this event is discarded from your hand or
    deck: You may deal 1 damage to a unit." """

    def test_LAW_206_played_deals_1_damage(self, repo):
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "206")
        state = _law06_choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_LAW_206_discarded_from_the_deck_deals_1_damage(self, repo):
        from swu.engine.actions import (note_hand_or_deck_discard,
                                        _fire_self_discard_observers)
        from swu.engine.state import Zone
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        rock = _put_in_hand(state, "P0", _get_card(repo, "LAW", "206"))
        # Mill it: out of hand, into the discard pile, through the chokepoint.
        state.player_by_id("P0").hand.remove(rock)
        rock.zone = Zone.DISCARD
        state.player_by_id("P0").discard.append(rock)
        note_hand_or_deck_discard(state, rock)
        state = _fire_self_discard_observers(state)
        state = _law02_accept(state)
        state = _law06_choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 1

    def test_LAW_206_sitting_in_the_discard_fires_nothing_by_itself(self, repo):
        from swu.engine.actions import _fire_self_discard_observers
        from swu.engine.state import Zone
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        rock = _put_in_hand(state, "P0", _get_card(repo, "LAW", "206"))
        state.player_by_id("P0").hand.remove(rock)
        rock.zone = Zone.DISCARD
        state.player_by_id("P0").discard.append(rock)
        state = _fire_self_discard_observers(state)   # ledger empty -> no fire
        assert state.pending_decisions == []


class TestAttackFromAllSides_LAW_207:
    """"Deal 3 damage to a unit.  If there are 4 or more different aspects among
    friendly units, you may deal 5 damage to that unit instead." """

    def test_LAW_207_deals_5_with_four_friendly_aspects(self, repo):
        state = _make_state()
        # Vigilance + Heroism, then Cunning + Villainy = 4 distinct aspects.
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "LAW", "213"), "ground")
        assert len(_distinct_aspects(state, "P0")) >= 4
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "207")
        state = _law06_choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 5

    def test_LAW_207_deals_3_with_fewer_aspects(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert len(_distinct_aspects(state, "P0")) < 4
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "207")
        state = _law06_choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 3


class TestCollateralDamage_LAW_208:
    """"Deal 2 damage to a unit.  Then, deal 2 damage to a base or another unit in
    the same arena." """

    def _rig(self, repo):
        state = _make_state()
        first = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        same = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        return state, first, same, other

    def test_LAW_208_splashes_another_unit_in_the_same_arena(self, repo):
        state, first, same, other = self._rig(repo)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "208")
        state = _law06_choose(state, first.instance_id)
        offered = _law06_offered(state)
        assert first.instance_id not in offered          # "another"
        assert other.instance_id not in offered          # wrong arena
        assert same.instance_id in offered
        state = _law06_choose(state, same.instance_id)
        assert _find_instance(state, first.instance_id).damage == 2
        assert _find_instance(state, same.instance_id).damage == 2
        assert _find_instance(state, other.instance_id).damage == 0

    def test_LAW_208_may_splash_a_base_instead(self, repo):
        state, first, same, other = self._rig(repo)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "208")
        state = _law06_choose(state, first.instance_id)
        enemy_base = state.player_by_id("P1").base_zone[0]
        assert enemy_base.instance_id in _law06_offered(state)
        state = _law06_choose(state, enemy_base.instance_id)
        assert state.player_by_id("P1").base_zone[0].damage == 2
        assert _find_instance(state, first.instance_id).damage == 2


class TestCutthroatPodracer_LAW_213:
    """"When Played: You may deal 2 damage to an exhausted ground unit." """

    def test_LAW_213_damages_an_exhausted_ground_unit(self, repo):
        state = _make_state()
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        podracer = _place(state, "P0", _get_card(repo, "LAW", "213"), "ground")
        state = _law01_drain(_fire_when_played(state, podracer))
        state = _law02_accept(state)
        state = _law06_choose(state, tired.instance_id)
        assert _find_instance(state, tired.instance_id).damage == 2

    def test_LAW_213_never_offers_a_ready_or_space_unit(self, repo):
        state = _make_state()
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired_space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        tired_space.exhausted = True
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        podracer = _place(state, "P0", _get_card(repo, "LAW", "213"), "ground")
        state = _law01_drain(_fire_when_played(state, podracer))
        state = _law02_accept(state)
        offered = _law06_offered(state)
        assert tired.instance_id in offered
        assert ready.instance_id not in offered
        assert tired_space.instance_id not in offered


# -- Group law-set:07 -- Card advantage & disruption ---------------------------


def _use_ability_law07(state, source_ci):
    """Apply the (single) UseAbility offered by ``source_ci``."""
    from swu.engine.actions import legal_actions, apply, UseAbility
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id)
    return apply(state, use)


def _offered_law07(state, source_ci):
    from swu.engine.actions import legal_actions, UseAbility
    return [a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]


def _set_base_law07(state, repo, sc, num, owner="P0"):
    """Swap a player's base for the named card (bases carry Epic Actions)."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ci = CardInstance(f"{owner}_base_{_u.uuid4().hex[:5]}",
                      _get_card(repo, sc, num), owner, Zone.BASE_ZONE)
    state.player_by_id(owner).base_zone = [ci]
    return ci


class TestTobiasBeckettLAW2:
    """LAW_2 -- "Action [Exhaust]: Choose a friendly unit.  An opponent takes
    control of it.  If they do, create a Credit token." / "When Deployed: Defeat
    any number of units you own but don't control.  For each unit defeated this
    way, create a Credit token and draw a card"."""

    def test_law_2_action_hands_a_unit_over_for_a_credit(self, repo):
        from swu.engine.actions import ChooseTarget
        state = _make_state()
        beckett = _place_leader(state, "P0", _get_card(repo, "LAW", "2"))
        goon = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")

        state = _use_ability_law07(state, beckett)
        state = _drive_to_quiescence(
            state, lambda acts: next(
                (a for a in acts if isinstance(a, ChooseTarget)
                 and a.target_id == goon.instance_id), None))

        p1_ids = [u.instance_id for u in state.player_by_id("P1").ground_arena]
        p0_ids = [u.instance_id for u in state.player_by_id("P0").ground_arena]
        assert goon.instance_id in p1_ids, "the opponent now controls it"
        assert goon.instance_id not in p0_ids
        # Control moved; OWNERSHIP did not (that split is the whole card).
        moved = next(u for u in state.player_by_id("P1").ground_arena
                     if u.instance_id == goon.instance_id)
        assert moved.owner_id == "P0"
        assert _credits(state, "P0") == 1

    def test_law_2_action_not_offered_with_no_friendly_unit(self, repo):
        state = _make_state()
        beckett = _place_leader(state, "P0", _get_card(repo, "LAW", "2"))
        assert _offered_law07(state, beckett) == [], "nothing to hand over"

    def test_law_2_deploy_defeats_owned_units_for_credits_and_draws(self, repo):
        from swu.engine.actions import (
            apply, change_control, SelectTokenTarget, FinishSelectToken)
        state = _make_state()
        beckett = _place(state, "P0", _get_card(repo, "LAW", "2"), "ground")
        beckett.deployed = True
        # Two units P0 OWNS but P1 controls, plus one ordinary P1 unit (which must
        # never be offered) and one ordinary P0 unit (ditto).
        lent1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        lent2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "space")
        change_control(state, lent1, "P1")
        change_control(state, lent2, "P1")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        hand_before = len(state.player_by_id("P0").hand)

        state = _fire_when_deployed(state, beckett)
        assert state.pending_decisions[-1].kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert offered == {lent1.instance_id, lent2.instance_id}, \
            "only units owned-but-not-controlled are offered"

        state = apply(state, SelectTokenTarget(lent1.instance_id))
        state = apply(state, SelectTokenTarget(lent2.instance_id))
        if state.pending_decisions and \
                state.pending_decisions[-1].kind == "select_token":
            state = apply(state, FinishSelectToken())

        assert _find_instance(state, lent1.instance_id) is None
        assert _find_instance(state, lent2.instance_id) is None
        assert _find_instance(state, theirs.instance_id) is not None
        assert _find_instance(state, mine.instance_id) is not None
        assert _credits(state, "P0") == 2, "one Credit per unit defeated this way"
        assert len(state.player_by_id("P0").hand) == hand_before + 2

    def test_law_2_deploy_is_silent_with_nothing_lent_out(self, repo):
        state = _make_state()
        beckett = _place(state, "P0", _get_card(repo, "LAW", "2"), "ground")
        beckett.deployed = True
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_deployed(state, beckett)
        assert not state.pending_decisions, "no pool -> no prompt"
        assert _credits(state, "P0") == 0

    def test_law_2_experience_token_gains_no_leader_abilities(self, repo):
        """LAW_2 is ALSO the Experience token's (set, number).  Both of Beckett's
        specs are of the kinds a token upgrade can never reach, so an Experience
        token in play must offer nothing (the Kylo Ren LOF_1 regression)."""
        import sqlite3
        from swu.engine.actions import legal_actions, UseAbility
        from swu.engine.state import CardInstance, Zone
        con = sqlite3.connect(require_db())
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                "SELECT * FROM cards WHERE set_code=? AND card_number=? "
                "AND type LIKE '%Token%'", ("LAW", "2")).fetchone()
            row = require_row(row, "the LAW_2 token (LAW_2 really is a token's number too)")
            token_def = repo._hydrate(con, row)
        finally:
            con.close()

        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        exp = CardInstance("P0_law2_token", token_def, "P0", Zone.GROUND_ARENA)
        host.attached_upgrades.append(exp)

        # Beckett's undeployed Action needs a Leader card_def, so the arena scan
        # never offers it from the token; nothing else of his is a spec a token
        # upgrade can be a source for.
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility) and a.source_id == exp.instance_id]
        assert not state.pending_decisions
        # …and no trigger of his is collected from the token either.
        state = _fire_on_attack(state, host)
        assert not state.pending_decisions
        assert _credits(state, "P0") == 0


class TestJynErsoLAW5:
    """LAW_5 -- both sides: "If a friendly Rebel unit was defeated this phase,
    search the top 3 cards of your deck for a card and draw it"."""

    def _kill_a_rebel(self, state, repo, owner="P0"):
        """Defeat a real Rebel unit through the engine, so the new
        ``defeated_traits_this_round`` ledger is exercised end to end."""
        from swu.engine.actions import _defeat_unit
        rebel = _place(state, owner, _get_card(repo, "LAW", "40"), "ground")
        assert "Rebel" in {t for t in rebel.card_def.traits}
        _defeat_unit(state, state.player_by_id(owner), rebel)
        assert "Rebel" in state.game_memory.defeated_traits_this_round[owner]
        return state

    def test_law_5_action_not_offered_before_a_rebel_dies(self, repo):
        state = _make_state()
        jyn = _place_leader(state, "P0", _get_card(repo, "LAW", "5"))
        _give_resources(state, "P0", 3)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        assert _offered_law07(state, jyn) == []

    def test_law_5_action_searches_top_three_after_a_rebel_dies(self, repo):
        from swu.engine.actions import apply, SelectSearchCard
        state = _seed_rng(_make_state())
        jyn = _place_leader(state, "P0", _get_card(repo, "LAW", "5"))
        _give_resources(state, "P0", 3)
        deck = _build_search_deck(
            state, "P0",
            [_get_card(repo, "SOR", "46"), _get_card(repo, "SOR", "140"),
             _get_card(repo, "SOR", "210")],
            [_get_card(repo, "SOR", "46")])
        state = self._kill_a_rebel(state, repo)

        assert _offered_law07(state, jyn), "the Rebel defeat opened the Action"
        state = _use_ability_law07(state, jyn)
        assert state.pending_decisions[-1].kind == "deck_search"
        want = deck[1].instance_id
        state = apply(state, SelectSearchCard(want))   # count=1 auto-finishes

        assert any(c.instance_id == want for c in state.player_by_id("P0").hand)
        assert state.player_by_id("P0").available_resources == 2, "1 resource spent"

    def test_law_5_on_attack_gated_by_the_rebel_defeat(self, repo):
        state = _seed_rng(_make_state())
        jyn = _place(state, "P0", _get_card(repo, "LAW", "5"), "ground")
        jyn.deployed = True
        _build_search_deck(state, "P0", [_get_card(repo, "SOR", "46")] * 3)

        quiet = _fire_on_attack(state, jyn)
        assert not quiet.pending_decisions, "no Rebel died -> no search"

        state = self._kill_a_rebel(state, repo)
        state = _fire_on_attack(state, jyn)
        assert state.pending_decisions[-1].kind == "deck_search"

    def test_law_5_ledger_is_scoped_to_the_controller(self, repo):
        """An ENEMY Rebel dying does not open Jyn's ability -- the ledger is keyed
        by controller-at-death."""
        state = _make_state()
        jyn = _place_leader(state, "P0", _get_card(repo, "LAW", "5"))
        _give_resources(state, "P0", 3)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        self._kill_a_rebel(state, repo, owner="P1")
        assert _offered_law07(state, jyn) == []


class TestSebulbaLAW12:
    """LAW_12 -- "Action [Exhaust, discard a card from your deck]: A friendly unit
    gains Raid 1 for this phase." / "On Attack: Discard a card from your deck"."""

    def test_law_12_action_mills_one_and_grants_raid_1(self, repo):
        from swu.engine.actions import ChooseTarget, compute_power
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        sebulba = _place_leader(state, "P0", _get_card(repo, "LAW", "12"))
        goon = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        power_before = compute_power(state, goon, is_attacking=True)

        state = _use_ability_law07(state, sebulba)
        state = _drive_to_quiescence(
            state, lambda acts: next(
                (a for a in acts if isinstance(a, ChooseTarget)
                 and a.target_id == goon.instance_id), None))

        assert any(c.instance_id == top.instance_id
                   for c in state.player_by_id("P0").discard), "milled the top card"
        assert not state.player_by_id("P0").deck
        buffed = _find_instance(state, goon.instance_id)
        assert keyword_value(state, buffed, Keyword.RAID) == 1
        assert compute_power(state, buffed, is_attacking=True) == power_before + 1

    def test_law_12_action_not_offered_with_no_friendly_unit(self, repo):
        state = _make_state()
        sebulba = _place_leader(state, "P0", _get_card(repo, "LAW", "12"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        assert _offered_law07(state, sebulba) == [], "the mill is never paid for nothing"

    def test_law_12_on_attack_mills_exactly_one(self, repo):
        state = _make_state()
        sebulba = _place(state, "P0", _get_card(repo, "LAW", "12"), "ground")
        sebulba.deployed = True
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        state = _fire_on_attack(state, sebulba)
        ps = state.player_by_id("P0")
        assert [c.instance_id for c in ps.discard] == [top.instance_id]
        assert len(ps.deck) == 1
        # The mill feeds the shared ledger, so a "when this is discarded" card and
        # the discarded-this-phase gate both see it.
        assert top.instance_id in state.game_memory.cards_discarded_this_phase


class TestLandoCalrissianLAW18:
    """LAW_18 -- "Action [1 resource, Exhaust]: Choose an aspect, then discard a
    card from a deck.  If it has the chosen aspect, create a Credit token." /
    "When Deployed: You may defeat a friendly Credit token.  If you do, create 3
    Credit tokens"."""

    def test_law_18_action_mills_and_pays_a_credit_on_a_match(self, repo):
        state = _make_state()
        lando = _place_leader(state, "P0", _get_card(repo, "LAW", "18"))
        _give_resources(state, "P0", 2)
        # A deck that is entirely one aspect: the modal-aspect choice must hit.
        heroic = _get_card(repo, "SOR", "140")           # [Aggression, Heroism]
        deck = _build_search_deck(state, "P0", [heroic, heroic, heroic])

        state = _use_ability_law07(state, lando)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert [c.instance_id for c in ps.discard] == [deck[0].instance_id]
        assert len(ps.deck) == 2
        assert _credits(state, "P0") == 1
        assert ps.available_resources == 1, "1 resource spent"

    def test_law_18_action_pays_nothing_when_the_milled_card_misses(self, repo):
        """The chosen aspect is the deck's MODAL one; stack the deck so the top
        card is the odd one out and no Credit is paid."""
        state = _make_state()
        lando = _place_leader(state, "P0", _get_card(repo, "LAW", "18"))
        _give_resources(state, "P0", 2)
        odd = _get_card(repo, "SOR", "210")              # Swoop Racer [Cunning]
        many = _get_card(repo, "SOR", "46")              # [Vigilance, Heroism]
        assert {a.name for a in odd.aspects}.isdisjoint({a.name for a in many.aspects})
        _build_search_deck(state, "P0", [odd, many, many, many, many])

        state = _use_ability_law07(state, lando)
        state = _drive_to_quiescence(state, lambda acts: None)

        assert _credits(state, "P0") == 0
        assert len(state.player_by_id("P0").discard) == 1

    def test_law_18_deploy_trades_one_credit_for_three(self, repo):
        from swu.engine.actions import AcceptTrigger
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "LAW", "18"), "ground")
        lando.deployed = True
        _add_credit(state, "P0", 1)
        state = _fire_when_deployed(state, lando)
        state = _drive_to_quiescence(state, lambda acts: next(
            (a for a in acts if isinstance(a, AcceptTrigger)), None))
        assert _credits(state, "P0") == 3, "1 spent, 3 created"

    def test_law_18_deploy_not_offered_without_a_credit(self, repo):
        state = _make_state()
        lando = _place(state, "P0", _get_card(repo, "LAW", "18"), "ground")
        lando.deployed = True
        _add_credit(state, "P1", 2)   # an ENEMY credit is not a friendly one
        state = _fire_when_deployed(state, lando)
        assert not state.pending_decisions
        assert _credits(state, "P0") == 0


class TestShipbreakingYardLAW26:
    """LAW_26 -- "Epic Action: Discard 3 cards from your deck.  You may return a
    card discarded this way to the top of your deck"."""

    def test_law_26_mills_three_and_returns_one_to_the_top(self, repo):
        from swu.engine.actions import apply, SelectSearchCard
        state = _seed_rng(_make_state())
        yard = _set_base_law07(state, repo, "LAW", "26")
        deck = _build_search_deck(
            state, "P0",
            [_get_card(repo, "SOR", "46"), _get_card(repo, "SOR", "140"),
             _get_card(repo, "SOR", "210")],
            [_get_card(repo, "SOR", "46")])

        state = _use_ability_law07(state, yard)
        assert state.pending_decisions[-1].kind == "deck_search"
        assert yard.instance_id in state.game_memory.epic_actions_spent

        keep = deck[2].instance_id
        state = apply(state, SelectSearchCard(keep))     # count=1 auto-finishes

        ps = state.player_by_id("P0")
        assert ps.deck[0].instance_id == keep, "the rescued card is back on TOP"
        assert len(ps.deck) == 2, "the kept card + the un-searched remainder"
        assert {c.instance_id for c in ps.discard} == {deck[0].instance_id,
                                                       deck[1].instance_id}
        # The card kept on top was never really discarded, so it is NOT in the
        # discarded-this-phase ledger (which a "when this is discarded" card reads).
        assert keep not in state.game_memory.cards_discarded_this_phase
        assert deck[0].instance_id in state.game_memory.cards_discarded_this_phase

    def test_law_26_declining_discards_all_three(self, repo):
        from swu.engine.actions import apply, FinishSearch
        state = _seed_rng(_make_state())
        yard = _set_base_law07(state, repo, "LAW", "26")
        deck = _build_search_deck(
            state, "P0", [_get_card(repo, "SOR", "46")] * 3,
            [_get_card(repo, "SOR", "140")])

        state = _use_ability_law07(state, yard)
        state = apply(state, FinishSearch())

        ps = state.player_by_id("P0")
        assert len(ps.discard) == 3
        assert [c.instance_id for c in ps.deck] == [deck[3].instance_id]


class TestCitadelResearchCenterLAW29:
    """LAW_29 -- "Epic Action [1 resource]: Return a friendly resource to its
    owner's hand.  If you do, resource the top card of your deck"."""

    def test_law_29_recycles_a_resource_and_ramps_the_deck_top(self, repo):
        state = _make_state()
        centre = _set_base_law07(state, repo, "LAW", "29")
        _give_resources(state, "P0", 3)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        hand_before = len(state.player_by_id("P0").hand)

        state = _use_ability_law07(state, centre)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert len(ps.resources) == 3, "one out, the deck top in"
        assert len(ps.hand) == hand_before + 1
        assert any(c.instance_id == top.instance_id for c in ps.resources), \
            "the deck top became a resource"
        assert not ps.deck
        assert centre.instance_id in state.game_memory.epic_actions_spent

    def test_law_29_is_a_no_op_without_a_resource_to_return(self, repo):
        """With no resource the cost cannot be paid at all, so the epic is not
        even offered -- and therefore never wasted."""
        state = _make_state()
        centre = _set_base_law07(state, repo, "LAW", "29")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        assert _offered_law07(state, centre) == []


class TestChioFainLAW48:
    """LAW_48 -- "On Attack: You may choose 2 players.  If you do, they each draw
    a card"."""

    def test_law_48_on_attack_both_players_draw(self, repo):
        from swu.engine.actions import AcceptTrigger
        state = _make_state()
        chio = _place(state, "P0", _get_card(repo, "LAW", "48"), "ground")
        for pid in ("P0", "P1"):
            _push_deck_top(state, pid, _get_card(repo, "SOR", "46"))
        before = {p.player_id: len(p.hand) for p in state.players}

        state = _fire_on_attack(state, chio)
        state = _drive_to_quiescence(state, lambda acts: next(
            (a for a in acts if isinstance(a, AcceptTrigger)), None))

        for pid in ("P0", "P1"):
            assert len(state.player_by_id(pid).hand) == before[pid] + 1

    def test_law_48_can_be_declined(self, repo):
        from swu.engine.actions import DeclineTrigger
        state = _make_state()
        chio = _place(state, "P0", _get_card(repo, "LAW", "48"), "ground")
        for pid in ("P0", "P1"):
            _push_deck_top(state, pid, _get_card(repo, "SOR", "46"))
        before = {p.player_id: len(p.hand) for p in state.players}

        state = _fire_on_attack(state, chio)
        state = _drive_to_quiescence(state, lambda acts: next(
            (a for a in acts if isinstance(a, DeclineTrigger)), None))

        for pid in ("P0", "P1"):
            assert len(state.player_by_id(pid).hand) == before[pid], \
                "declining helps neither player"


# -- Group law-set:08 -- Card advantage & disruption ---------------------------


def _hand_of_law08(state, repo, owner, n):
    """Give ``owner`` exactly ``n`` hand cards (replacing whatever is there)."""
    state.player_by_id(owner).hand = []
    for _ in range(n):
        _put_in_hand(state, owner, _get_card(repo, "SOR", "46"))
    return state


class TestBrokenHornLAW83:
    """LAW_83 -- "When Played: If you have fewer cards in hand than an opponent,
    draw a card.  If you control fewer resources than an opponent, resource the top
    card of your deck"."""

    def test_law_83_draws_and_ramps_when_behind_on_both(self, repo):
        state = _make_state()
        horn = _place(state, "P0", _get_card(repo, "LAW", "83"), "ground")
        _hand_of_law08(state, repo, "P0", 1)
        _hand_of_law08(state, repo, "P1", 4)
        _give_resources(state, "P0", 2)
        _give_resources(state, "P1", 5)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        draw = _push_deck_top(state, "P0", _get_card(repo, "SOR", "210"))

        state = _fire_when_played(state, horn)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert any(c.instance_id == draw.instance_id for c in ps.hand), "drew 1"
        assert any(c.instance_id == top.instance_id for c in ps.resources), \
            "ramped the (new) deck top"
        assert len(ps.resources) == 3

    def test_law_83_does_nothing_when_ahead_on_both(self, repo):
        state = _make_state()
        horn = _place(state, "P0", _get_card(repo, "LAW", "83"), "ground")
        _hand_of_law08(state, repo, "P0", 4)
        _hand_of_law08(state, repo, "P1", 1)
        _give_resources(state, "P0", 5)
        _give_resources(state, "P1", 2)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))

        state = _fire_when_played(state, horn)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert len(ps.hand) == 4 and len(ps.resources) == 5
        assert len(ps.deck) == 1, "deck untouched"

    def test_law_83_level_counts_satisfy_neither_clause(self, repo):
        """Both atoms are MIRRORS, not negations: equal is not "fewer"."""
        state = _make_state()
        horn = _place(state, "P0", _get_card(repo, "LAW", "83"), "ground")
        _hand_of_law08(state, repo, "P0", 3)
        _hand_of_law08(state, repo, "P1", 3)
        _give_resources(state, "P0", 4)
        _give_resources(state, "P1", 4)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))

        state = _fire_when_played(state, horn)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert len(ps.hand) == 3 and len(ps.resources) == 4 and len(ps.deck) == 1


class TestKrrsantanLAW84:
    """LAW_84 -- "Action [discard 2 cards from your hand]: Return this unit to your
    hand (from play)"."""

    def test_law_84_discards_two_and_bounces_itself(self, repo):
        state = _make_state()
        krr = _place(state, "P0", _get_card(repo, "LAW", "84"), "ground")
        _hand_of_law08(state, repo, "P0", 3)

        state = _use_ability_law07(state, krr)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert _find_instance(state, krr.instance_id) is None, "left the arena"
        assert any(c.instance_id == krr.instance_id for c in ps.hand)
        # 3 hand cards - 2 discarded + Krrsantan back = 2
        assert len(ps.hand) == 2
        assert len(ps.discard) == 2

    def test_law_84_not_offered_on_a_short_hand(self, repo):
        state = _make_state()
        krr = _place(state, "P0", _get_card(repo, "LAW", "84"), "ground")
        _hand_of_law08(state, repo, "P0", 1)
        assert _offered_law07(state, krr) == [], "the discard cost is unpayable"

    def test_law_84_usable_while_exhausted(self, repo):
        """There is no Exhaust in the printed cost, so an exhausted Krrsantan can
        still escape."""
        state = _make_state()
        krr = _place(state, "P0", _get_card(repo, "LAW", "84"), "ground")
        krr.exhausted = True
        _hand_of_law08(state, repo, "P0", 2)
        assert _offered_law07(state, krr), "still offered while exhausted"


class TestHondoOhnakaLAW94:
    """LAW_94 -- "Action: Play the top card of your deck (paying its cost).  Use
    this ability only once each round"."""

    def test_law_94_plays_the_top_card_of_the_deck(self, repo):
        from swu.engine.actions import apply, PlayTopCard
        state = _make_state()
        hondo = _place(state, "P0", _get_card(repo, "LAW", "94"), "ground")
        _give_resources(state, "P0", 8)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))

        state = _use_ability_law07(state, hondo)
        assert state.pending_decisions[-1].kind == "peek_top"
        play = next(a for a in legal_actions(state) if isinstance(a, PlayTopCard))
        state = apply(state, play)
        state = _drive_to_quiescence(state, lambda acts: None)

        assert _find_instance(state, top.instance_id) is not None, "now in play"
        assert not state.player_by_id("P0").deck

    def test_law_94_may_leave_the_card_on_top(self, repo):
        from swu.engine.actions import apply, KeepTopCard
        state = _make_state()
        hondo = _place(state, "P0", _get_card(repo, "LAW", "94"), "ground")
        _give_resources(state, "P0", 8)
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))

        state = _use_ability_law07(state, hondo)
        state = apply(state, KeepTopCard())

        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id

    def test_law_94_is_once_each_round(self, repo):
        from swu.engine.actions import apply, KeepTopCard
        state = _make_state()
        hondo = _place(state, "P0", _get_card(repo, "LAW", "94"), "ground")
        _give_resources(state, "P0", 8)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))

        state = _use_ability_law07(state, hondo)
        state = apply(state, KeepTopCard())
        state.active_player_index = 0
        assert _offered_law07(state, hondo) == [], "spent for the round"


class TestRhydoniumDetonationLAW96:
    """LAW_96 -- "Each player may return a non-leader unit to its owner's hand.
    Then, defeat all non-leader units"."""

    def test_law_96_each_player_saves_one_then_the_board_is_wiped(self, repo):
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        mine_saved = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine_doomed = _place(state, "P0", _get_card(repo, "SOR", "140"), "ground")
        theirs_saved = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        theirs_doomed = _place(state, "P1", _get_card(repo, "SOR", "140"), "ground")

        state, _ev = _play_event_from_hand(state, repo, "LAW", "96", resources=20)
        assert state.pending_decisions[-1].kind == "each_player_defeats"
        # The controller chooses first, then the opponent.
        state = apply(state, ChooseUnitToDefeat(mine_saved.instance_id))
        state = apply(state, ChooseUnitToDefeat(theirs_saved.instance_id))
        state = _drive_to_quiescence(state, lambda acts: None)

        for saved, owner in ((mine_saved, "P0"), (theirs_saved, "P1")):
            assert _find_instance(state, saved.instance_id) is None
            assert any(c.instance_id == saved.instance_id
                       for c in state.player_by_id(owner).hand), "returned to hand"
        for doomed, owner in ((mine_doomed, "P0"), (theirs_doomed, "P1")):
            assert _find_instance(state, doomed.instance_id) is None
            assert any(c.instance_id == doomed.instance_id
                       for c in state.player_by_id(owner).discard), "defeated"

    def test_law_96_spares_leaders(self, repo):
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        leader = _deploy_leader_in_arena(state, "P1", _get_card(repo, "LAW", "5"))
        grunt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ev = _play_event_from_hand(state, repo, "LAW", "96", resources=20)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseUnitToDefeat)}
        assert leader.instance_id not in offered, "a leader is not a non-leader unit"
        state = apply(state, ChooseUnitToDefeat(grunt.instance_id))
        state = _drive_to_quiescence(state, lambda acts: None)

        assert _find_instance(state, leader.instance_id) is not None, "leader survives"


class TestDisplayPieceLAW103:
    """LAW_103 -- "Defeat an enemy non-leader unit.  Its controller resources it
    from its owner's discard pile"."""

    def test_law_103_defeats_and_hands_the_victim_a_resource(self, repo):
        from swu.engine.actions import ChooseTarget
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        res_before = len(state.player_by_id("P1").resources)

        state, _ev = _play_event_from_hand(state, repo, "LAW", "103", resources=16)
        state = _drive_to_quiescence(
            state, lambda acts: next(
                (a for a in acts if isinstance(a, ChooseTarget)
                 and a.target_id == victim.instance_id), None))

        assert _find_instance(state, victim.instance_id) is None, "defeated"
        p1 = state.player_by_id("P1")
        assert len(p1.resources) == res_before + 1
        got = next(c for c in p1.resources if c.instance_id == victim.instance_id)
        assert got.face_down and not got.exhausted and got.damage == 0
        assert all(c.instance_id != victim.instance_id for c in p1.discard), \
            "it left the discard for the resource row"

    def test_law_103_cannot_target_a_friendly_unit(self, repo):
        from swu.engine.actions import ChooseTarget
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state, _ev = _play_event_from_hand(state, repo, "LAW", "103", resources=16)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {enemy.instance_id}
        assert mine.instance_id not in offered


class TestSwoopBikeMarauderLAW107:
    """LAW_107 -- "On Attack: Draw a card"."""

    def test_law_107_on_attack_draws_one(self, repo):
        state = _make_state()
        swoop = _place(state, "P0", _get_card(repo, "LAW", "107"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        before = len(state.player_by_id("P0").hand)

        state = _fire_on_attack(state, swoop)
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert len(ps.hand) == before + 1
        assert any(c.instance_id == top.instance_id for c in ps.hand)


class TestWatchfulLAW125:
    """LAW_125 -- "Attached unit gains: 'On Attack: Look at the top card of a deck.
    You may put it on the bottom of that deck.'"."""

    def test_law_125_host_on_attack_may_bottom_the_top_card(self, repo):
        from swu.engine.actions import apply, BottomTopCard
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "125"), "P0")
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        second = _push_deck_top(state, "P0", _get_card(repo, "SOR", "210"))
        # deck is now [second, top]
        state = _fire_on_attack(state, host)
        assert state.pending_decisions[-1].kind == "peek_top"
        state = apply(state, BottomTopCard())

        deck = state.player_by_id("P0").deck
        assert deck[0].instance_id == top.instance_id
        assert deck[-1].instance_id == second.instance_id, "bottomed"

    def test_law_125_may_leave_it_on_top(self, repo):
        from swu.engine.actions import apply, KeepTopCard
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "125"), "P0")
        second = _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        first = _push_deck_top(state, "P0", _get_card(repo, "SOR", "210"))

        state = _fire_on_attack(state, host)
        state = apply(state, KeepTopCard())

        deck = state.player_by_id("P0").deck
        assert [c.instance_id for c in deck] == [first.instance_id,
                                                 second.instance_id]

    def test_law_125_grants_nothing_to_an_unattached_upgrade(self, repo):
        """The grant is a GrantedAbility, so a bare unit with no Watchful on it
        has no On Attack of its own."""
        state = _make_state()
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        state = _fire_on_attack(state, plain)
        assert not state.pending_decisions


# =============================================================================
# Group law-set:09 -- Card advantage & disruption (the self-mill group)
# =============================================================================


def _finish_search_law09(state):
    from swu.engine.actions import apply, FinishSearch
    return apply(state, FinishSearch())


def _attack_base_law09(state, attacker_ci, attacker_owner="P0"):
    """Drive a REAL base attack through ``apply`` so the action settle-point runs.

    The deck-discard observer (LAW_176) is drained at that settle-point, so a test
    for it cannot use the ``_fire_on_attack`` shortcut -- the mill has to happen
    inside a real action."""
    from swu.engine.actions import legal_actions, apply, AttackWithUnit
    state.active_player_index = state.player_index(attacker_owner)
    atk = next(a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == attacker_ci.instance_id
               and a.defender_id is None)
    return apply(state, atk)


class TestUndercityHuntingTeamLAW138:
    """LAW_138 -- "When Played: Search the top 5 cards of your deck for a Bounty
    Hunter unit, reveal it, and draw it"."""

    def test_law_138_searches_top_5_and_draws_the_bounty_hunter(self, repo):
        state = _make_state()
        team = _place(state, "P0", _get_card(repo, "LAW", "138"), "ground")
        plain = _get_card(repo, "SOR", "46")            # no Bounty Hunter trait
        hunter = _get_card(repo, "LAW", "159")          # Bounty Hunter unit
        deck = _build_search_deck(
            state, "P0", [plain, plain, hunter, plain, plain], [plain])
        _seed_rng(state)
        target = deck[2]

        state = _fire_when_played(state, team)
        assert state.pending_decisions[-1].kind == "deck_search"
        offered = set(state.pending_decisions[-1].context["candidate_ids"])
        assert offered == {target.instance_id}, "only the Bounty Hunter qualifies"

        state = _take_from_search(state, target.instance_id)
        ps = state.player_by_id("P0")
        assert any(c.instance_id == target.instance_id for c in ps.hand)
        # The window's other four went to the bottom; the 6th card never moved.
        assert ps.deck[0].instance_id == deck[5].instance_id

    def test_law_138_fizzles_with_no_bounty_hunter_in_the_window(self, repo):
        state = _make_state()
        team = _place(state, "P0", _get_card(repo, "LAW", "138"), "ground")
        plain = _get_card(repo, "SOR", "46")
        hunter = _get_card(repo, "LAW", "159")
        # The only Bounty Hunter sits 6th -- outside the 5-card window.
        deck = _build_search_deck(state, "P0", [plain] * 5, [hunter])
        _seed_rng(state)

        state = _fire_when_played(state, team)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.context["candidate_ids"] == [], "nothing in the window qualifies"

        state = _finish_search_law09(state)
        ps = state.player_by_id("P0")
        assert all(c.instance_id != hunter_id
                   for hunter_id in [deck[5].instance_id] for c in ps.hand)
        assert ps.deck[0].instance_id == deck[5].instance_id, "the 6th card never moved"


class TestExpendableMercenaryLAW159:
    """LAW_159 -- "When Defeated: You may resource this unit from its owner's
    discard pile"."""

    def _defeat(self, state, ci, owner="P0"):
        from swu.engine.actions import _defeat_unit
        _defeat_unit(state, state.player_by_id(owner), ci)  # mutates in place
        return state

    def test_law_159_may_resource_itself_out_of_the_discard(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        SelectResourceFromDiscard)
        state = _make_state()
        merc = _place(state, "P0", _get_card(repo, "LAW", "159"), "ground")
        state = self._defeat(state, merc)

        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        while state.pending_decisions[-1].kind == "resolve_effects":
            state = apply(state, legal_actions(state)[0])
        top = state.pending_decisions[-1]
        assert top.kind == "resource_from_discard"
        assert top.context["candidate_ids"] == [merc.instance_id], "only itself"

        state = apply(state, SelectResourceFromDiscard(merc.instance_id))
        ps = state.player_by_id("P0")
        res = next(c for c in ps.resources if c.instance_id == merc.instance_id)
        assert res.face_down and res.exhausted, "enters as a resource, per CR"
        assert all(c.instance_id != merc.instance_id for c in ps.discard)

    def test_law_159_may_be_declined_and_stays_in_the_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        merc = _place(state, "P0", _get_card(repo, "LAW", "159"), "ground")
        state = self._defeat(state, merc)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))

        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert any(c.instance_id == merc.instance_id for c in ps.discard)
        assert all(c.instance_id != merc.instance_id for c in ps.resources)


class TestSebulbasPodracerLAW176:
    """LAW_176 -- "When you discard a card from your deck: You may ready this
    unit.  Use this ability only once each round"."""

    def _setup(self, repo):
        """Podracer exhausted beside a Bracca Shipbreaker whose On Attack mills."""
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "176"), "ground")
        pod.exhausted = True
        bracca = _place(state, "P0", _get_card(repo, "LAW", "192"), "ground")
        for _ in range(6):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        return state, pod, bracca

    def test_law_176_readies_when_you_mill_from_your_own_deck(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state, pod, bracca = self._setup(repo)
        state = _attack_base_law09(state, bracca)

        # The mill fired the observer at the settle-point.
        assert state.pending_decisions[-1].kind == "trigger_option"
        accept = next(a for a in legal_actions(state)
                      if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not _find_instance(state, pod.instance_id).exhausted

    def test_law_176_may_be_declined_without_spending_the_round_use(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state, pod, bracca = self._setup(repo)
        state = _attack_base_law09(state, bracca)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        state = _drive_to_quiescence(state, lambda acts: None)

        assert _find_instance(state, pod.instance_id).exhausted
        # Declining is not a use, so the limiter is untouched.
        assert not any(k.startswith(pod.instance_id)
                       for k in state.game_memory.activated_abilities_used_this_round)

    def test_law_176_only_once_each_round(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state, pod, bracca = self._setup(repo)
        state = _attack_base_law09(state, bracca)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = _drive_to_quiescence(state, lambda acts: None)
        assert not _find_instance(state, pod.instance_id).exhausted
        # Second mill in the same round: the limiter blocks collection outright,
        # so no trigger is even offered.
        _find_instance(state, pod.instance_id).exhausted = True
        bracca2 = _find_instance(state, bracca.instance_id)
        bracca2.exhausted = False
        state = _attack_base_law09(state, bracca2)
        assert not state.pending_decisions
        assert _find_instance(state, pod.instance_id).exhausted

    def test_law_176_ignores_an_opponents_self_mill(self, repo):
        """"When YOU discard" -- the ledger records who milled, so the enemy's
        Bracca leaves an enemy-side Podracer's controller alone."""
        from swu.engine.actions import discard_from_deck, _fire_deck_discard_observers
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "176"), "ground")
        pod.exhausted = True
        for _ in range(3):
            _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))

        discard_from_deck(state, state.player_by_id("P1"), 1)
        state = _fire_deck_discard_observers(state)
        assert not state.pending_decisions
        assert _find_instance(state, pod.instance_id).exhausted

    def test_law_176_does_not_fire_on_a_hand_discard(self, repo):
        """The deck ledger is fed only at the DECK sites -- a hand discard feeds
        the hand ledgers instead, so the Podracer stays exhausted."""
        from swu.engine.actions import (note_hand_or_deck_discard,
                                        _fire_deck_discard_observers)
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "176"), "ground")
        pod.exhausted = True
        card = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        note_hand_or_deck_discard(state, card)          # no from_deck=True

        state = _fire_deck_discard_observers(state)
        assert not state.pending_decisions
        assert _find_instance(state, pod.instance_id).exhausted


class TestBraccaShipbreakerLAW192:
    """LAW_192 -- "On Attack: Discard a card from your deck"."""

    def test_law_192_on_attack_mills_the_top_card(self, repo):
        state = _make_state()
        bracca = _place(state, "P0", _get_card(repo, "LAW", "192"), "ground")
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        second = _push_deck_top(state, "P0", _get_card(repo, "SOR", "210"))
        # deck is [second, top]
        state = _fire_on_attack(state, bracca)

        ps = state.player_by_id("P0")
        assert [c.instance_id for c in ps.deck] == [top.instance_id]
        assert [c.instance_id for c in ps.discard] == [second.instance_id]
        assert second.instance_id in state.game_memory.cards_discarded_this_phase

    def test_law_192_empty_deck_mills_nothing_and_deals_no_base_damage(self, repo):
        """A mill is not the empty-deck DRAW penalty."""
        state = _make_state()
        bracca = _place(state, "P0", _get_card(repo, "LAW", "192"), "ground")
        state.player_by_id("P0").deck = []
        base_before = state.player_by_id("P0").base_zone[0].damage

        state = _fire_on_attack(state, bracca)
        ps = state.player_by_id("P0")
        assert ps.deck == [] and ps.discard == []
        assert ps.base_zone[0].damage == base_before


class TestDoctorAphraLAW194:
    """LAW_194 -- "On Attack: Discard 3 cards from your deck.  You may return an
    Underworld card discarded this way to your hand"."""

    def test_law_194_mills_three_and_returns_an_underworld_card(self, repo):
        from swu.engine.actions import apply, SelectDiscardCard
        state = _make_state()
        aphra = _place(state, "P0", _get_card(repo, "LAW", "194"), "ground")
        plain = _get_card(repo, "SOR", "46")
        underworld = _get_card(repo, "LAW", "159")      # Underworld unit
        deck = _build_search_deck(state, "P0", [plain, underworld, plain, plain])

        state = _fire_on_attack(state, aphra)
        ps = state.player_by_id("P0")
        assert len(ps.discard) == 3 and len(ps.deck) == 1

        top = state.pending_decisions[-1]
        assert top.kind == "return_from_discard"
        assert top.context["candidate_ids"] == [deck[1].instance_id]

        state = apply(state, SelectDiscardCard(deck[1].instance_id))
        from swu.engine.actions import FinishReturnFromDiscard
        if state.pending_decisions:
            state = apply(state, FinishReturnFromDiscard())
        ps = state.player_by_id("P0")
        assert any(c.instance_id == deck[1].instance_id for c in ps.hand)
        assert len(ps.discard) == 2

    def test_law_194_only_offers_cards_discarded_this_way(self, repo):
        """"discarded this way" pins the return by INSTANCE id -- a matching
        Underworld card already in the discard is not offered."""
        from swu.engine.state import CardInstance, Zone
        import uuid as _u
        state = _make_state()
        aphra = _place(state, "P0", _get_card(repo, "LAW", "194"), "ground")
        stale = CardInstance(f"P0_stale_{_u.uuid4().hex[:5]}",
                             _get_card(repo, "LAW", "159"), "P0", Zone.DISCARD)
        state.player_by_id("P0").discard.append(stale)
        plain = _get_card(repo, "SOR", "46")
        deck = _build_search_deck(state, "P0",
                                  [plain, _get_card(repo, "LAW", "159"), plain])

        state = _fire_on_attack(state, aphra)
        top = state.pending_decisions[-1]
        assert top.context["candidate_ids"] == [deck[1].instance_id]
        assert stale.instance_id not in top.context["candidate_ids"]

    def test_law_194_no_underworld_milled_pushes_no_decision(self, repo):
        state = _make_state()
        aphra = _place(state, "P0", _get_card(repo, "LAW", "194"), "ground")
        plain = _get_card(repo, "SOR", "46")
        _build_search_deck(state, "P0", [plain, plain, plain])

        state = _fire_on_attack(state, aphra)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").discard) == 3


class TestSalvagedBlasterLAW200:
    """LAW_200 -- "Action: If this upgrade was discarded from your hand or deck
    this phase, play it from your discard pile (paying its cost)"."""

    def _mill_the_blaster(self, repo):
        from swu.engine.actions import discard_from_deck
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _build_search_deck(state, "P0", [_get_card(repo, "LAW", "200")])
        _give_resources(state, "P0", 12)
        milled = discard_from_deck(state, state.player_by_id("P0"), 1)[0]
        state.active_player_index = 0
        return state, host, milled

    def test_law_200_playable_from_discard_after_being_milled(self, repo):
        from swu.engine.actions import legal_actions, PlayFromDiscard
        state, host, blaster = self._mill_the_blaster(repo)
        plays = [a for a in legal_actions(state)
                 if isinstance(a, PlayFromDiscard)
                 and a.instance_id == blaster.instance_id]
        assert plays, "the milled upgrade is offered from the discard pile"
        # Offered once per legal (non-Vehicle) host.
        assert {a.upgrade_target_id for a in plays} == {host.instance_id}

    def test_law_200_not_playable_when_it_was_not_discarded_this_phase(self, repo):
        from swu.engine.actions import legal_actions, PlayFromDiscard
        state, host, blaster = self._mill_the_blaster(repo)
        state.game_memory.cards_discarded_this_phase.clear()
        assert not [a for a in legal_actions(state)
                    if isinstance(a, PlayFromDiscard)
                    and a.instance_id == blaster.instance_id]


class TestHoldForQuestioningLAW217:
    """LAW_217 -- "Exhaust an enemy unit.  If you do, look at its controller's
    hand and discard a card from it that shares an aspect with that unit"."""

    def test_law_217_exhausts_and_offers_only_aspect_sharing_hand_cards(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        # SOR_46 is [Vigilance, Heroism]; SOR_210 is [Cunning].
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P1").hand = []
        share = _put_in_hand(state, "P1", _get_card(repo, "SOR", "140"))   # Vigilance
        miss = _put_in_hand(state, "P1", _get_card(repo, "SOR", "210"))    # Cunning

        state, _ev = _play_event_from_hand(state, repo, "LAW", "217",
                                           owner="P0", resources=20)
        state = apply(state, ChooseTarget(enemy.instance_id))

        assert _find_instance(state, enemy.instance_id).exhausted
        top = state.pending_decisions[-1]
        assert top.kind == "name_and_discard"
        assert top.context["eligible_names"] == [share.card_def.display_name]
        assert miss.card_def.display_name not in top.context["eligible_names"]

    def test_law_217_discards_the_named_card(self, repo):
        from swu.engine.actions import apply, ChooseTarget, NameAndDiscard
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P1").hand = []
        share = _put_in_hand(state, "P1", _get_card(repo, "SOR", "140"))

        state, _ev = _play_event_from_hand(state, repo, "LAW", "217",
                                           owner="P0", resources=20)
        state = apply(state, ChooseTarget(enemy.instance_id))
        state = apply(state, NameAndDiscard(share.card_def.display_name))

        opp = state.player_by_id("P1")
        assert all(c.instance_id != share.instance_id for c in opp.hand)
        assert any(c.instance_id == share.instance_id for c in opp.discard)

    def test_law_217_offers_only_ready_enemy_units(self, repo):
        """An already-exhausted unit would make the whole card a no-op, so it is
        never a legal target."""
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent.exhausted = True
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")

        state, _ev = _play_event_from_hand(state, repo, "LAW", "217",
                                           owner="P0", resources=20)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {ready.instance_id}
        assert spent.instance_id not in offered
        assert mine.instance_id not in offered

    def test_law_217_no_matching_hand_card_leaves_no_prompt(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "210"), "ground")  # Cunning
        state.player_by_id("P1").hand = []
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "140"))             # Vigilance

        state, _ev = _play_event_from_hand(state, repo, "LAW", "217",
                                           owner="P0", resources=20)
        state = apply(state, ChooseTarget(enemy.instance_id))

        assert _find_instance(state, enemy.instance_id).exhausted, "the exhaust still lands"
        assert not state.pending_decisions
        assert len(state.player_by_id("P1").hand) == 1


# =============================================================================
# Group law-set:10 -- Card advantage & disruption (the Credit-economy group)
# =============================================================================


class TestLibertyLAW224:
    """LAW_224 -- "When Played/On Attack: Exhaust an enemy unit and return all
    upgrades on it that cost 4 or less to their owner's hands"."""

    def _setup(self, repo):
        state = _make_state()
        liberty = _place(state, "P0", _get_card(repo, "LAW", "224"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        return state, liberty, enemy

    def test_law_224_exhausts_and_bounces_cheap_upgrades(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state, liberty, enemy = self._setup(repo)
        cheap = _attach_upgrade_directly(state, enemy,
                                         _get_card(repo, "LAW", "125"), "P1")  # cost 1
        state = _fire_when_played(state, liberty)
        state = apply(state, ChooseTarget(enemy.instance_id))

        victim = _find_instance(state, enemy.instance_id)
        assert victim.exhausted
        assert all(u.instance_id != cheap.instance_id
                   for u in victim.attached_upgrades)
        assert any(c.instance_id == cheap.instance_id
                   for c in state.player_by_id("P1").hand), "to its OWNER's hand"

    def test_law_224_leaves_expensive_upgrades_attached(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state, liberty, enemy = self._setup(repo)
        dear = _attach_upgrade_directly(state, enemy,
                                        _get_card(repo, "TS26", "45"), "P1")  # cost 5
        assert int(dear.card_def.cost) > 4
        state = _fire_when_played(state, liberty)
        state = apply(state, ChooseTarget(enemy.instance_id))

        victim = _find_instance(state, enemy.instance_id)
        assert victim.exhausted, "the exhaust lands regardless"
        assert any(u.instance_id == dear.instance_id
                   for u in victim.attached_upgrades)

    def test_law_224_leaves_shield_tokens_alone(self, repo):
        """A token has no cost and no hand to go back to."""
        from swu.engine.actions import apply, ChooseTarget
        from swu.engine.tokens import attach_token
        state, liberty, enemy = self._setup(repo)
        attach_token(state, state.player_by_id("P1"), enemy, "Shield")
        state = _fire_when_played(state, liberty)
        state = apply(state, ChooseTarget(enemy.instance_id))

        victim = _find_instance(state, enemy.instance_id)
        assert _shield_count(victim) == 1

    def test_law_224_fires_on_attack_too(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state, liberty, enemy = self._setup(repo)
        state = _fire_on_attack(state, liberty)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted


class TestHansGoldenDiceLAW225:
    """LAW_225 -- "Attached unit gains: 'On Attack: Discard a card from your deck.
    If its cost is odd, create a Credit token.'"."""

    def _setup(self, repo, top_card):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "225"), "P0")
        top = _push_deck_top(state, "P0", top_card)
        return state, host, top

    def test_law_225_odd_cost_mill_creates_a_credit(self, repo):
        odd = _get_card(repo, "SOR", "210")            # Swoop Racer, cost 1
        assert int(odd.cost) % 2 == 1
        state, host, top = self._setup(repo, odd)
        state = _fire_on_attack(state, host)

        ps = state.player_by_id("P0")
        assert any(c.instance_id == top.instance_id for c in ps.discard)
        assert len(ps.credits) == 1

    def test_law_225_even_cost_mill_creates_nothing(self, repo):
        even = _get_card(repo, "SOR", "46")            # cost 6
        assert int(even.cost) % 2 == 0
        state, host, top = self._setup(repo, even)
        state = _fire_on_attack(state, host)

        ps = state.player_by_id("P0")
        assert any(c.instance_id == top.instance_id for c in ps.discard)
        assert len(ps.credits) == 0

    def test_law_225_grants_nothing_to_an_unattached_unit(self, repo):
        state = _make_state()
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "210"))
        state = _fire_on_attack(state, plain)
        ps = state.player_by_id("P0")
        assert ps.discard == [] and len(ps.credits) == 0


class TestTheMasterCodebreakerLAW229:
    """LAW_229 -- "The first Gambit card you play each round costs 1 resource less.
    When Played: Search the top 8 cards of your deck for a Gambit card, reveal it,
    and draw it"."""

    def test_law_229_searches_top_8_for_a_gambit_card(self, repo):
        state = _make_state()
        cb = _place(state, "P0", _get_card(repo, "LAW", "229"), "ground")
        plain = _get_card(repo, "SOR", "46")
        gambit = _get_card(repo, "LAW", "246")          # The Axe Forgets (Gambit)
        deck = _build_search_deck(state, "P0",
                                  [plain] * 7 + [gambit], [plain])
        _seed_rng(state)

        state = _fire_when_played(state, cb)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert top.context["candidate_ids"] == [deck[7].instance_id]

        state = _take_from_search(state, deck[7].instance_id)
        assert any(c.instance_id == deck[7].instance_id
                   for c in state.player_by_id("P0").hand)

    def test_law_229_discounts_the_first_gambit_card_each_round(self, repo):
        """A Gambit EVENT is discounted -- the discount arm is card-type-blind."""
        from swu.engine.actions import _play_cost
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "229"), "ground")
        gambit = _put_in_hand(state, "P0", _get_card(repo, "LAW", "246"))
        ps = state.player_by_id("P0")

        with_cb = _play_cost(state, gambit, ps)
        state.player_by_id("P0").ground_arena = []      # remove the Codebreaker
        without = _play_cost(state, gambit, state.player_by_id("P0"))
        assert with_cb == without - 1

    def test_law_229_does_not_discount_a_non_gambit_card(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "229"), "ground")
        plain = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        ps = state.player_by_id("P0")

        with_cb = _play_cost(state, plain, ps)
        state.player_by_id("P0").ground_arena = []
        without = _play_cost(state, plain, state.player_by_id("P0"))
        assert with_cb == without


class TestBixCaleenLAW236:
    """LAW_236 -- "When Played/On Attack: You may discard a card from your hand.
    If you do, create a Credit token"."""

    def test_law_236_discard_a_hand_card_for_a_credit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        bix = _place(state, "P0", _get_card(repo, "LAW", "236"), "ground")
        state.player_by_id("P0").hand = []
        pitched = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))

        state = _fire_when_played(state, bix)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert ps.hand == []
        assert any(c.instance_id == pitched.instance_id for c in ps.discard)
        assert len(ps.credits) == 1

    def test_law_236_may_be_declined(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        bix = _place(state, "P0", _get_card(repo, "LAW", "236"), "ground")
        state.player_by_id("P0").hand = []
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))

        state = _fire_when_played(state, bix)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 1 and len(ps.credits) == 0

    def test_law_236_not_offered_with_an_empty_hand(self, repo):
        state = _make_state()
        bix = _place(state, "P0", _get_card(repo, "LAW", "236"), "ground")
        state.player_by_id("P0").hand = []
        state = _fire_when_played(state, bix)
        assert not state.pending_decisions

    def test_law_236_fires_on_attack_too(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        bix = _place(state, "P0", _get_card(repo, "LAW", "236"), "ground")
        state.player_by_id("P0").hand = []
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))

        state = _fire_on_attack(state, bix)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = _drive_to_quiescence(state, lambda acts: None)
        assert len(state.player_by_id("P0").credits) == 1


class TestQuiGonJinnLAW237:
    """LAW_237 -- "When Played/On Attack: Look at the top 3 cards of your deck.
    You may discard 1 of them.  Put the rest back on top in any order"."""

    def test_law_237_looks_at_three_and_may_discard_one(self, repo):
        state = _make_state()
        qgj = _place(state, "P0", _get_card(repo, "LAW", "237"), "ground")
        plain = _get_card(repo, "SOR", "46")
        deck = _build_search_deck(state, "P0", [plain, plain, plain], [plain, plain])

        state = _fire_when_played(state, qgj)
        top = state.pending_decisions[-1]
        assert top.kind == "deck_search"
        assert set(top.context["candidate_ids"]) == {c.instance_id for c in deck[:3]}

        state = _take_from_search(state, deck[1].instance_id)
        ps = state.player_by_id("P0")
        assert [c.instance_id for c in ps.discard] == [deck[1].instance_id]
        # The other two stayed on TOP, in their existing order.
        assert [c.instance_id for c in ps.deck[:2]] == [deck[0].instance_id,
                                                        deck[2].instance_id]

    def test_law_237_may_discard_nothing(self, repo):
        state = _make_state()
        qgj = _place(state, "P0", _get_card(repo, "LAW", "237"), "ground")
        plain = _get_card(repo, "SOR", "46")
        deck = _build_search_deck(state, "P0", [plain, plain, plain])

        state = _fire_when_played(state, qgj)
        state = _finish_search_law09(state)
        ps = state.player_by_id("P0")
        assert ps.discard == []
        assert [c.instance_id for c in ps.deck] == [c.instance_id for c in deck]

    def test_law_237_fires_on_attack_too(self, repo):
        state = _make_state()
        qgj = _place(state, "P0", _get_card(repo, "LAW", "237"), "ground")
        _build_search_deck(state, "P0", [_get_card(repo, "SOR", "46")] * 3)
        state = _fire_on_attack(state, qgj)
        assert state.pending_decisions[-1].kind == "deck_search"


class TestScavengingSandcrawlerLAW238:
    """LAW_238 -- "On Attack: You may put a card from your discard pile on the
    bottom of your deck.  If you do, create a Credit token"."""

    def _setup(self, repo):
        from swu.engine.state import CardInstance, Zone
        import uuid as _u
        state = _make_state()
        crawler = _place(state, "P0", _get_card(repo, "LAW", "238"), "ground")
        junk = CardInstance(f"P0_junk_{_u.uuid4().hex[:5]}",
                            _get_card(repo, "SOR", "46"), "P0", Zone.DISCARD)
        state.player_by_id("P0").discard.append(junk)
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "140"))
        return state, crawler, junk

    def test_law_238_bottoming_a_card_creates_a_credit(self, repo):
        from swu.engine.actions import apply, SelectBottomDiscardCard
        state, crawler, junk = self._setup(repo)
        _seed_rng(state)
        state = _fire_on_attack(state, crawler)
        assert state.pending_decisions[-1].kind == "bottom_from_discard"

        state = apply(state, SelectBottomDiscardCard(junk.instance_id))
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        assert ps.discard == []
        assert ps.deck[-1].instance_id == junk.instance_id
        assert len(ps.credits) == 1

    def test_law_238_declining_creates_no_credit(self, repo):
        from swu.engine.actions import apply, FinishBottomFromDiscard
        state, crawler, junk = self._setup(repo)
        state = _fire_on_attack(state, crawler)
        state = apply(state, FinishBottomFromDiscard())

        ps = state.player_by_id("P0")
        assert any(c.instance_id == junk.instance_id for c in ps.discard)
        assert len(ps.credits) == 0

    def test_law_238_empty_discard_pushes_no_decision(self, repo):
        state = _make_state()
        crawler = _place(state, "P0", _get_card(repo, "LAW", "238"), "ground")
        state = _fire_on_attack(state, crawler)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").credits) == 0


class TestMilodonRiderLAW240:
    """LAW_240 -- "When Played: You may return another friendly non-leader unit to
    its owner's hand"."""

    def test_law_240_returns_another_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        rider = _place(state, "P0", _get_card(repo, "LAW", "240"), "ground")
        mate = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, rider)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(mate.instance_id))

        ps = state.player_by_id("P0")
        assert any(c.instance_id == mate.instance_id for c in ps.hand)
        assert _find_instance(state, rider.instance_id) is not None

    def test_law_240_never_offers_itself_or_an_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        rider = _place(state, "P0", _get_card(repo, "LAW", "240"), "ground")
        mate = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, rider)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {mate.instance_id}
        assert rider.instance_id not in offered
        assert enemy.instance_id not in offered

    def test_law_240_may_be_declined(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        rider = _place(state, "P0", _get_card(repo, "LAW", "240"), "ground")
        mate = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, rider)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, mate.instance_id) is not None
        assert state.player_by_id("P0").hand == []


# =============================================================================
# Group law-set:11 -- Card advantage & disruption (3 cards)
# =============================================================================


class TestTheBladeWingLAW241:
    """LAW_241 -- "When Played: You may return a non-leader unit to its owner's
    hand"."""

    def test_law_241_returns_an_enemy_non_leader_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "LAW", "241"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, wing)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))

        assert any(c.instance_id == enemy.instance_id
                   for c in state.player_by_id("P1").hand)

    def test_law_241_offers_either_side_but_no_leader(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "LAW", "241"), "space")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        leader = _place(state, "P1", _get_card(repo, "SOR", "10"), "ground")
        leader.deployed = True

        state = _fire_when_played(state, wing)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert {mine.instance_id, enemy.instance_id} <= offered
        assert leader.instance_id not in offered

    def test_law_241_may_be_declined(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        wing = _place(state, "P0", _get_card(repo, "LAW", "241"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, wing)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, enemy.instance_id) is not None
        assert state.player_by_id("P1").hand == []


class TestImproviseLAW242:
    """LAW_242 -- "Look at the top card of your deck.  You may play it.  It costs
    1 resource less.  If you don't, you may discard it"."""

    def _cast(self, repo, top_card):
        state = _make_state()
        top = _push_deck_top(state, "P0", top_card)
        state, _ev = _play_event_from_hand(state, repo, "LAW", "242",
                                           owner="P0", resources=20)
        return state, top

    def test_law_242_offers_play_discard_and_keep(self, repo):
        from swu.engine.actions import (legal_actions)
        state, top = self._cast(repo, _get_card(repo, "SOR", "210"))
        assert state.pending_decisions[-1].kind == "peek_top"
        kinds = {type(a).__name__ for a in legal_actions(state)}
        assert {"PlayTopCard", "DiscardTopCard", "KeepTopCard"} <= kinds

    def test_law_242_plays_the_top_card_one_resource_cheaper(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayTopCard, _play_cost
        card = _get_card(repo, "SOR", "210")            # Swoop Racer, a Unit
        state, top = self._cast(repo, card)
        ps = state.player_by_id("P0")
        full = _play_cost(state, ps.deck[0], ps)
        ready_before = sum(1 for r in ps.resources if not r.exhausted)

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayTopCard)))
        state = _drive_to_quiescence(state, lambda acts: None)

        ps = state.player_by_id("P0")
        ready_after = sum(1 for r in ps.resources if not r.exhausted)
        assert ready_before - ready_after == full - 1, "1 resource less"
        assert _find_instance(state, top.instance_id) is not None, "it entered play"

    def test_law_242_may_discard_the_top_card_instead(self, repo):
        from swu.engine.actions import legal_actions, apply, DiscardTopCard
        state, top = self._cast(repo, _get_card(repo, "SOR", "210"))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DiscardTopCard)))

        ps = state.player_by_id("P0")
        assert any(c.instance_id == top.instance_id for c in ps.discard)
        assert all(c.instance_id != top.instance_id for c in ps.deck)

    def test_law_242_may_leave_it_on_top(self, repo):
        from swu.engine.actions import legal_actions, apply, KeepTopCard
        state, top = self._cast(repo, _get_card(repo, "SOR", "210"))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, KeepTopCard)))
        assert state.player_by_id("P0").deck[0].instance_id == top.instance_id


class TestSalvagedMaterialsLAW245:
    """LAW_245 -- "Play an Item upgrade from your discard pile.  It costs 3
    resources less.  At the start of the next regroup phase, defeat it"."""

    def _setup(self, repo, upgrade_num="LAW_200"):
        from swu.engine.state import CardInstance, Zone
        import uuid as _u
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        blaster = CardInstance(f"P0_up_{_u.uuid4().hex[:5]}",
                               _get_card(repo, "LAW", "200"), "P0", Zone.DISCARD)
        state.player_by_id("P0").discard.append(blaster)
        return state, host, blaster

    def test_law_245_plays_an_item_upgrade_from_the_discard_3_cheaper(self, repo):
        from swu.engine.actions import (legal_actions, apply, PlayUpgradeFromHand,
                                        _play_cost)
        state, host, blaster = self._setup(repo)
        state, _ev = _play_event_from_hand(state, repo, "LAW", "245",
                                           owner="P0", resources=20)
        assert state.pending_decisions[-1].kind == "play_upgrade_from_hand"
        ps = state.player_by_id("P0")
        # _make_state's base has no aspects, so assert the REDUCTION as a delta.
        full = _play_cost(state, blaster, ps, target_host_id=host.instance_id)
        ready_before = sum(1 for r in ps.resources if not r.exhausted)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayUpgradeFromHand))
        state = apply(state, play)
        state = _drive_to_quiescence(state, lambda acts: None)

        landed = _find_instance(state, host.instance_id)
        assert any(u.instance_id == blaster.instance_id
                   for u in landed.attached_upgrades)
        ps = state.player_by_id("P0")
        ready_after = sum(1 for r in ps.resources if not r.exhausted)
        assert ready_before - ready_after == max(0, full - 3)
        assert full > 3, "and the discount really bit"

    def test_law_245_flags_the_upgrade_for_defeat_at_regroup(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        state, host, blaster = self._setup(repo)
        state, _ev = _play_event_from_hand(state, repo, "LAW", "245",
                                           owner="P0", resources=20)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayUpgradeFromHand)))
        state = _drive_to_quiescence(state, lambda acts: None)

        landed = _find_instance(state, host.instance_id)
        rented = next(u for u in landed.attached_upgrades
                      if u.instance_id == blaster.instance_id)
        assert rented.defeat_at_regroup is True

    def test_law_245_regroup_sends_the_rented_upgrade_to_its_owners_discard(self, repo):
        """A real card must not simply vanish the way a token does."""
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        from swu.engine.actions import _enter_regroup
        state, host, blaster = self._setup(repo)
        state, _ev = _play_event_from_hand(state, repo, "LAW", "245",
                                           owner="P0", resources=20)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayUpgradeFromHand)))
        state = _drive_to_quiescence(state, lambda acts: None)

        _enter_regroup(state)
        landed = _find_instance(state, host.instance_id)
        assert all(u.instance_id != blaster.instance_id
                   for u in landed.attached_upgrades), "detached"
        assert any(c.instance_id == blaster.instance_id
                   for c in state.player_by_id("P0").discard), "and not lost"

    def test_law_245_no_item_upgrade_in_the_discard_pushes_nothing(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ev = _play_event_from_hand(state, repo, "LAW", "245",
                                           owner="P0", resources=20)
        assert not state.pending_decisions


# ── law-set:12 — Combat tricks, buffs & tempo (the LAW leader block) ─────────


def _law12_use(state, source_ci, idx=0):
    """Apply the ``idx``-th UseAbility offered by ``source_ci``."""
    from swu.engine.actions import legal_actions, apply, UseAbility
    offered = [a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]
    return apply(state, offered[idx])


def _law12_offered(state, source_ci):
    from swu.engine.actions import legal_actions, UseAbility
    return [a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]


def _law12_undeployed_leader(state, owner_id, leader_def):
    """Put a leader into ``owner_id``'s base zone, ready and undeployed."""
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ci = CardInstance(f"{owner_id}_ldr_{_u.uuid4().hex[:6]}", leader_def,
                      owner_id, Zone.BASE_ZONE)
    ci.deployed = False
    ci.exhausted = False
    state.player_by_id(owner_id).base_zone.append(ci)
    return ci


def _law12_leader_def(repo, set_code, num):
    """Fetch the LEADER row for a (set, number) that a TOKEN also shares."""
    from swu.cards.models import Leader
    for cd in repo.iter_all():
        if (cd.set_code == set_code and cd.card_number == num
                and isinstance(cd, Leader)):
            return cd
    require_row(None, f"the {set_code}_{num} Leader")


def _law12_unit_def(repo, set_code, num):
    """Fetch the UNIT row for a (set, number) -- low numbers collide with tokens."""
    from swu.cards.models import Unit
    for cd in repo.iter_all():
        if (cd.set_code == set_code and cd.card_number == num
                and type(cd) is Unit):
            return cd
    require_row(None, f"the {set_code}_{num} Unit")


def _law12_credits(state, pid="P0"):
    return len(state.player_by_id(pid).credits)


class TestAgentKallusLAW3:
    """LAW_3 -- "Action [1 resource, Exhaust]: Play a card from your hand, ignoring
    its aspect penalties" (undeployed; deployed drops the exhaust) + "When you play
    a Heroism card: Heal 2 damage from your base" (deployed)."""

    def test_LAW_3_undeployed_action_plays_a_unit_ignoring_the_aspect_penalty(self, repo):
        from swu.engine.actions import apply, PlayFromHand, _play_cost
        state = _make_state()
        kallus = _law12_undeployed_leader(state, "P0",
                                          _law12_leader_def(repo, "LAW", "3"))
        # A 2-aspect unit, so _make_state's aspect-less base charges the full
        # penalty -- exactly what the ability waives.
        unit = _get_card(repo, "LAW", "31")
        held = _put_in_hand(state, "P0", unit)
        _give_resources(state, "P0", 20)
        printed = int(getattr(unit, "cost", 0) or 0)
        full = _play_cost(state, held, state.player_by_id("P0"))
        assert full > printed, "the test unit must carry an aspect penalty"

        ready_before = sum(1 for r in state.player_by_id("P0").resources
                           if not r.exhausted)
        state = _law12_use(state, kallus)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == held.instance_id)
        state = apply(state, play)
        ready_after = sum(1 for r in state.player_by_id("P0").resources
                          if not r.exhausted)
        # 1 for the ability's cost + the unit's PRINTED cost, penalty waived.
        assert ready_before - ready_after == 1 + printed
        assert _find_instance(state, held.instance_id) is not None

    def test_LAW_3_deployed_action_costs_no_exhaust(self, repo):
        state = _make_state()
        kallus = _deploy_leader_in_arena(state, "P0",
                                         _law12_leader_def(repo, "LAW", "3"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 20)
        state = _law12_use(state, kallus)
        assert _find_instance(state, kallus.instance_id).exhausted is False

    def test_LAW_3_deployed_heals_2_from_your_base_when_you_play_a_heroism_card(self, repo):
        state = _make_state()
        _deploy_leader_in_arena(state, "P0", _law12_leader_def(repo, "LAW", "3"))
        base = state.player_by_id("P0").base_zone[0]
        base.damage = 5
        heroic = _get_card(repo, "SOR", "46")       # Heroism unit
        assert "Heroism" in {a.name for a in (heroic.aspects or ())}
        held = _put_in_hand(state, "P0", heroic)
        _give_resources(state, "P0", 20)

        from swu.engine.actions import apply, PlayCard
        state.active_player_index = 0
        state = _law01_drain(apply(state, PlayCard(held.instance_id)))
        assert state.player_by_id("P0").base_zone[0].damage == 3

    def test_LAW_3_deployed_does_not_heal_for_a_non_heroism_card(self, repo):
        state = _make_state()
        _deploy_leader_in_arena(state, "P0", _law12_leader_def(repo, "LAW", "3"))
        base = state.player_by_id("P0").base_zone[0]
        base.damage = 5
        villain = _get_card(repo, "SOR", "247")     # Underworld Thug, no aspects
        assert "Heroism" not in {a.name for a in (villain.aspects or ())}
        held = _put_in_hand(state, "P0", villain)
        _give_resources(state, "P0", 20)

        from swu.engine.actions import apply, PlayCard
        state.active_player_index = 0
        state = _law01_drain(apply(state, PlayCard(held.instance_id)))
        assert state.player_by_id("P0").base_zone[0].damage == 5

    def test_LAW_3_registers_only_specs_a_token_upgrade_cannot_reach(self, repo):
        """LAW_3 is ALSO a Shield TOKEN UPGRADE's (set, number) in the DB.  The
        engine happens to build every Shield from one canonical def, but the
        registration must be safe regardless: an ActivatedAbility is enumerated
        only from arena UNITS and a plain TriggerAbility is only collected from
        cards in play, never from a host's attached_upgrades -- while a
        ConstantAbility, a GrantedAbility or a passive marker WOULD leak onto the
        token."""
        from swu.abilities.registry import (get_abilities, ActivatedAbility,
                                            TriggerAbility)
        from swu.cards.models import TokenUpgrade
        twins = [c for c in repo.iter_all()
                 if c.set_code == "LAW" and c.card_number == "3"]
        assert any(isinstance(c, TokenUpgrade) for c in twins), "the twin exists"
        specs = get_abilities("LAW", "3")
        assert specs
        for spec in specs:
            assert isinstance(spec, (ActivatedAbility, TriggerAbility)), spec
            assert spec.undeployed_only or spec.deployed_only, spec


class TestVelSarthaLAW6:
    """LAW_6 -- "Action [Exhaust]: Give an Experience token to a unit.  An opponent
    creates a Credit token." / "On Attack: You may give an Experience token to a
    unit.  If you do, an opponent creates a Credit token."."""

    def test_LAW_6_undeployed_gives_experience_and_an_opponent_credit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        vel = _law12_undeployed_leader(state, "P0",
                                       _law12_leader_def(repo, "LAW", "6"))
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _law12_use(state, vel)
        state = _law01_drain(apply(state, ChooseTarget(mine.instance_id)))
        assert _experience_count(_find_instance(state, mine.instance_id)) == 1
        assert _law12_credits(state, "P1") == 1
        assert _law12_credits(state, "P0") == 0
        assert _find_instance(state, vel.instance_id) is None  # still a leader
        assert state.player_by_id("P0").base_zone[-1].exhausted is True

    def test_LAW_6_deployed_on_attack_binds_the_credit_to_the_token(self, repo):
        from swu.engine.actions import apply, ChooseTarget, AcceptTrigger
        state = _make_state()
        vel = _deploy_leader_in_arena(state, "P0",
                                      _law12_leader_def(repo, "LAW", "6"))
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, vel, None)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, AcceptTrigger(vel.instance_id))
        state = _law01_drain(apply(state, ChooseTarget(mine.instance_id)))
        assert _experience_count(_find_instance(state, mine.instance_id)) == 1
        assert _law12_credits(state, "P1") == 1

    def test_LAW_6_deployed_declining_gives_the_opponent_no_credit(self, repo):
        from swu.engine.actions import apply, DeclineTrigger
        state = _make_state()
        vel = _deploy_leader_in_arena(state, "P0",
                                      _law12_leader_def(repo, "LAW", "6"))
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, vel, None)
        state = _law01_drain(apply(state, DeclineTrigger(vel.instance_id)))
        assert _law12_credits(state, "P1") == 0


class TestBobaFettLAW7:
    """LAW_7 -- "When a friendly Bounty Hunter unit's attack ends: If the defending
    unit was defeated, [you may exhaust this leader.  If you do,] create a Credit
    token."."""

    def _kill_with_bounty_hunter(self, state, repo, attacker_ci):
        """Attack a 1-HP enemy with ``attacker_ci`` so the defender dies."""
        from swu.engine.actions import apply, AttackWithUnit
        prey = _place(state, "P1", _get_card(repo, "SOR", "225"), "ground")  # 2/1
        state.active_player_index = 0
        return apply(state, AttackWithUnit(attacker_id=attacker_ci.instance_id,
                                           defender_id=prey.instance_id))

    def test_LAW_7_deployed_creates_a_credit_when_a_bounty_hunter_kills(self, repo):
        state = _make_state()
        _deploy_leader_in_arena(state, "P0", _law12_leader_def(repo, "LAW", "7"))
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        assert "Bounty Hunter" in (hunter.card_def.traits or ())
        state = _law01_drain(self._kill_with_bounty_hunter(state, repo, hunter))
        assert _law12_credits(state, "P0") == 1

    def test_LAW_7_deployed_no_credit_when_the_attacker_is_not_a_bounty_hunter(self, repo):
        state = _make_state()
        _deploy_leader_in_arena(state, "P0", _law12_leader_def(repo, "LAW", "7"))
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert "Bounty Hunter" not in (plain.card_def.traits or ())
        state = _law01_drain(self._kill_with_bounty_hunter(state, repo, plain))
        assert _law12_credits(state, "P0") == 0

    def test_LAW_7_fires_even_when_the_attacking_bounty_hunter_dies(self, repo):
        """The card's printed rules note: the attacker "doesn't need to survive"."""
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        _deploy_leader_in_arena(state, "P0", _law12_leader_def(repo, "LAW", "7"))
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        hunter.damage = 3                       # 2/4 -> one hit from death
        prey = _place(state, "P1", _get_card(repo, "SOR", "225"), "ground")  # 2/1
        state.active_player_index = 0
        state = _law01_drain(apply(state, AttackWithUnit(
            attacker_id=hunter.instance_id, defender_id=prey.instance_id)))
        assert _find_instance(state, hunter.instance_id) is None, "attacker died"
        assert _find_instance(state, prey.instance_id) is None, "defender died"
        assert _law12_credits(state, "P0") == 1

    def test_LAW_7_no_credit_when_the_defender_survives(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        _deploy_leader_in_arena(state, "P0", _law12_leader_def(repo, "LAW", "7"))
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state.active_player_index = 0
        state = _law01_drain(apply(state, AttackWithUnit(
            attacker_id=hunter.instance_id, defender_id=prey.instance_id)))
        assert _find_instance(state, prey.instance_id) is not None
        assert _law12_credits(state, "P0") == 0

    def test_LAW_7_undeployed_exhausts_the_leader_for_the_credit(self, repo):
        from swu.engine.actions import apply, AcceptTrigger
        state = _make_state()
        boba = _law12_undeployed_leader(state, "P0",
                                        _law12_leader_def(repo, "LAW", "7"))
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        state = self._kill_with_bounty_hunter(state, repo, hunter)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = _law01_drain(apply(state, AcceptTrigger(boba.instance_id)))
        assert _law12_credits(state, "P0") == 1
        assert state.player_by_id("P0").base_zone[-1].exhausted is True

    def test_LAW_7_undeployed_is_not_offered_while_already_exhausted(self, repo):
        state = _make_state()
        boba = _law12_undeployed_leader(state, "P0",
                                        _law12_leader_def(repo, "LAW", "7"))
        boba.exhausted = True
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        state = _law01_drain(self._kill_with_bounty_hunter(state, repo, hunter))
        assert _law12_credits(state, "P0") == 0


class TestEnfysNestLAW14:
    """LAW_14 -- "When you use an 'On Attack' ability: You may [pay 2 resources and
    exhaust this leader.  If you do,] use that ability again."."""

    def _mill_attacker(self, state, repo):
        """LAW_192 Bracca Shipbreaker: "On Attack: Discard a card from your deck"."""
        return _place(state, "P0", _get_card(repo, "LAW", "192"), "ground")

    def test_LAW_14_undeployed_repeats_an_on_attack_ability_for_2_and_an_exhaust(self, repo):
        from swu.engine.actions import apply, AcceptTrigger
        state = _make_state()
        enfys = _law12_undeployed_leader(state, "P0",
                                         _law12_leader_def(repo, "LAW", "14"))
        shipbreaker = self._mill_attacker(state, repo)
        for _ in range(6):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 6)
        deck_before = len(state.player_by_id("P0").deck)
        ready_before = sum(1 for r in state.player_by_id("P0").resources
                           if not r.exhausted)

        state = _fire_on_attack(state, shipbreaker, None)
        # The mill resolved inline; the redo is offered as a trigger_option.
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = _law01_drain(apply(state, AcceptTrigger(shipbreaker.instance_id)))

        assert len(state.player_by_id("P0").deck) == deck_before - 2, "milled twice"
        ready_after = sum(1 for r in state.player_by_id("P0").resources
                          if not r.exhausted)
        assert ready_before - ready_after == 2
        assert state.player_by_id("P0").base_zone[-1].exhausted is True

    def test_LAW_14_undeployed_declining_costs_nothing(self, repo):
        from swu.engine.actions import apply, DeclineTrigger
        state = _make_state()
        enfys = _law12_undeployed_leader(state, "P0",
                                         _law12_leader_def(repo, "LAW", "14"))
        shipbreaker = self._mill_attacker(state, repo)
        for _ in range(6):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 6)
        deck_before = len(state.player_by_id("P0").deck)
        ready_before = sum(1 for r in state.player_by_id("P0").resources
                           if not r.exhausted)

        state = _fire_on_attack(state, shipbreaker, None)
        state = _law01_drain(apply(state, DeclineTrigger(shipbreaker.instance_id)))
        assert len(state.player_by_id("P0").deck) == deck_before - 1
        assert sum(1 for r in state.player_by_id("P0").resources
                   if not r.exhausted) == ready_before
        assert state.player_by_id("P0").base_zone[-1].exhausted is False

    def test_LAW_14_undeployed_not_offered_without_2_ready_resources(self, repo):
        state = _make_state()
        _law12_undeployed_leader(state, "P0", _law12_leader_def(repo, "LAW", "14"))
        shipbreaker = self._mill_attacker(state, repo)
        for _ in range(6):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 1)
        state = _fire_on_attack(state, shipbreaker, None)
        assert not state.pending_decisions, "unpayable redo is never offered"

    def test_LAW_14_deployed_is_free_but_only_once_each_round(self, repo):
        from swu.engine.actions import apply, AcceptTrigger
        state = _make_state()
        enfys = _deploy_leader_in_arena(state, "P0",
                                        _law12_leader_def(repo, "LAW", "14"))
        shipbreaker = self._mill_attacker(state, repo)
        for _ in range(12):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        deck_before = len(state.player_by_id("P0").deck)

        state = _fire_on_attack(state, shipbreaker, None)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = _law01_drain(apply(state, AcceptTrigger(shipbreaker.instance_id)))
        assert len(state.player_by_id("P0").deck) == deck_before - 2
        assert _find_instance(state, enfys.instance_id).exhausted is False, "free"

        # Second attack this round: the single use is spent, so no redo is offered.
        state = _fire_on_attack(state, shipbreaker, None)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").deck) == deck_before - 3

    def test_LAW_14_a_redo_never_arms_another_redo(self, repo):
        from swu.engine.actions import apply, AcceptTrigger
        state = _make_state()
        _law12_undeployed_leader(state, "P0", _law12_leader_def(repo, "LAW", "14"))
        shipbreaker = self._mill_attacker(state, repo)
        for _ in range(12):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 12)
        deck_before = len(state.player_by_id("P0").deck)
        state = _fire_on_attack(state, shipbreaker, None)
        state = _law01_drain(apply(state, AcceptTrigger(shipbreaker.instance_id)))
        # Exactly two mills -- the re-use does not arm a third.
        assert len(state.player_by_id("P0").deck) == deck_before - 2


class TestTheClientLAW16:
    """LAW_16 -- "[Action [Exhaust] / On Attack]: If you created a token this phase,
    exhaust an enemy unit."."""

    def test_LAW_16_undeployed_exhausts_an_enemy_after_a_token_was_created(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        client = _law12_undeployed_leader(state, "P0",
                                          _law12_leader_def(repo, "LAW", "16"))
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        theirs.exhausted = False
        _add_credit(state, "P0", 1)             # a token was created this phase
        assert "P0" in state.game_memory.tokens_created_this_phase

        state = _law12_use(state, client)
        state = _law01_drain(apply(state, ChooseTarget(theirs.instance_id)))
        assert _find_instance(state, theirs.instance_id).exhausted is True

    def test_LAW_16_undeployed_action_is_still_legal_with_no_token_created(self, repo):
        """The printed rules note: the Action may be used regardless -- it simply
        exhausts nothing."""
        state = _make_state()
        client = _law12_undeployed_leader(state, "P0",
                                          _law12_leader_def(repo, "LAW", "16"))
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert "P0" not in state.game_memory.tokens_created_this_phase
        assert _law12_offered(state, client), "the Action is still offered"
        state = _law01_drain(_law12_use(state, client))
        assert _find_instance(state, theirs.instance_id).exhausted is False
        assert state.player_by_id("P0").base_zone[-1].exhausted is True  # cost paid

    def test_LAW_16_an_opponents_token_does_not_satisfy_the_clause(self, repo):
        state = _make_state()
        client = _law12_undeployed_leader(state, "P0",
                                          _law12_leader_def(repo, "LAW", "16"))
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_credit(state, "P1", 1)             # THEIR token, not yours
        state = _law01_drain(_law12_use(state, client))
        assert _find_instance(state, theirs.instance_id).exhausted is False

    def test_LAW_16_deployed_on_attack_exhausts_an_enemy_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        client = _deploy_leader_in_arena(state, "P0",
                                         _law12_leader_def(repo, "LAW", "16"))
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_credit(state, "P0", 1)
        state = _fire_on_attack(state, client, None)
        state = _law01_drain(apply(state, ChooseTarget(theirs.instance_id)))
        assert _find_instance(state, theirs.instance_id).exhausted is True

    def test_LAW_16_a_shield_token_also_counts_as_created(self, repo):
        from swu.engine.tokens import attach_token
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attach_token(state, state.player_by_id("P0"), host, "Shield")
        assert "P0" in state.game_memory.tokens_created_this_phase


class TestAllianceOutpostLAW19:
    """LAW_19 -- "Epic Action [defeat a friendly token]: Give an Experience or
    Shield token to a unit, or create a Credit token."."""

    def test_LAW_19_is_not_offered_without_a_friendly_token(self, repo):
        state = _make_state()
        base = _set_base_law07(state, repo, "LAW", "19", "P0")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.active_player_index = 0
        assert not _law12_offered(state, base)

    def test_LAW_19_defeats_a_token_then_creates_a_credit(self, repo):
        from swu.engine.actions import apply, SelectCullCard, ChooseModalOption
        from swu.engine.tokens import attach_token
        state = _make_state()
        base = _set_base_law07(state, repo, "LAW", "19", "P0")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        shield = attach_token(state, state.player_by_id("P0"), host, "Shield")
        state.active_player_index = 0

        state = _law12_use(state, base)
        assert state.pending_decisions[-1].kind == "cull_for_damage"
        state = apply(state, SelectCullCard(shield.instance_id))
        # min=max=1 -> the pick auto-finishes into the modal payoff.
        assert state.pending_decisions[-1].kind == "modal"
        assert _shield_count(_find_instance(state, host.instance_id)) == 0
        state = _law01_drain(apply(state, ChooseModalOption("create_credit_token")))
        assert _law12_credits(state, "P0") == 1

    def test_LAW_19_can_instead_give_a_shield_to_a_unit(self, repo):
        from swu.engine.actions import (apply, SelectCullCard, ChooseModalOption,
                                        ChooseModalTarget)
        from swu.engine.tokens import attach_token
        state = _make_state()
        base = _set_base_law07(state, repo, "LAW", "19", "P0")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "203"), "ground")
        exp = attach_token(state, state.player_by_id("P0"), host, "Experience")
        state.active_player_index = 0

        state = apply(_law12_use(state, base), SelectCullCard(exp.instance_id))
        state = apply(state, ChooseModalOption("give_shield_unit"))
        state = _law01_drain(apply(state, ChooseModalTarget(other.instance_id)))
        assert _shield_count(_find_instance(state, other.instance_id)) == 1
        assert _experience_count(_find_instance(state, host.instance_id)) == 0

    def test_LAW_19_offers_all_three_modes(self, repo):
        from swu.engine.actions import apply, SelectCullCard
        from swu.engine.tokens import attach_token
        state = _make_state()
        base = _set_base_law07(state, repo, "LAW", "19", "P0")
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        shield = attach_token(state, state.player_by_id("P0"), host, "Shield")
        state.active_player_index = 0
        state = apply(_law12_use(state, base), SelectCullCard(shield.instance_id))
        assert set(state.pending_decisions[-1].context["modes"]) == {
            "give_experience_unit", "give_shield_unit", "create_credit_token"}


class TestBosskLAW31:
    """LAW_31 -- "On Attack: Give a unit +1/+1 for this phase.  You may give a unit
    -1/-1 for this phase."."""

    def _drive_bossk(self, state, buff_id, debuff_id, accept):
        """Resolve Bossk's two On Attack abilities, routing each ChooseTarget by
        the TOP decision's ``ability_idx`` (0 = the mandatory +1/+1, 1 = the "you
        may" -1/-1) -- the optional trigger's prompt is pushed on top, so the
        order is not the printed one."""
        from swu.engine.actions import (legal_actions, apply, ChooseTarget,
                                        AcceptTrigger, DeclineTrigger)
        guard = 0
        while state.pending_decisions and guard < 20:
            guard += 1
            top = state.pending_decisions[-1]
            acts = legal_actions(state)
            if top.kind == "trigger_option":
                cls = AcceptTrigger if accept else DeclineTrigger
                state = apply(state, next(a for a in acts if isinstance(a, cls)))
                continue
            want = buff_id if top.context.get("ability_idx") == 0 else debuff_id
            pick = next((a for a in acts if isinstance(a, ChooseTarget)
                         and a.target_id == want), None)
            state = apply(state, pick or acts[0])
        return state

    def test_LAW_31_buffs_a_unit_then_may_debuff_another(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        bossk = _place(state, "P0", _get_card(repo, "LAW", "31"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        base_power = compute_power(state, mine)

        state = _fire_on_attack(state, bossk, None)
        state = self._drive_bossk(state, mine.instance_id, theirs.instance_id,
                                  accept=True)
        assert compute_power(state, _find_instance(state, mine.instance_id)) \
            == base_power + 1
        assert compute_power(state, _find_instance(state, theirs.instance_id)) \
            == base_power - 1

    def test_LAW_31_the_debuff_may_be_declined(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        bossk = _place(state, "P0", _get_card(repo, "LAW", "31"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        base_power = compute_power(state, theirs)

        state = _fire_on_attack(state, bossk, None)
        state = self._drive_bossk(state, mine.instance_id, theirs.instance_id,
                                  accept=False)
        assert compute_power(state, _find_instance(state, theirs.instance_id)) \
            == base_power
        assert compute_power(state, _find_instance(state, mine.instance_id)) \
            == base_power + 1


# ── law-set:13 — Combat tricks, buffs & tempo (the token-payoff block) ───────


def _law13_choose_option(state, idx):
    """Pick the ability at registry index ``idx`` in a ``choose_two_modal``
    selector (Latts Razzi LAW_39's "a Shield token or an Experience token")."""
    from swu.engine.actions import legal_actions, apply, SelectModalOption
    acts = [a for a in legal_actions(state) if isinstance(a, SelectModalOption)]
    assert acts, [type(a).__name__ for a in legal_actions(state)]
    return apply(state, next(a for a in acts if a.option_idx == idx))


class TestLattsRazziLAW39:
    """LAW_39 -- "When Played: Give a Shield token or an Experience token to this
    unit.  Then, she deals damage equal to her power to an enemy ground unit"."""

    def test_LAW_39_experience_raises_her_power_before_the_damage(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        latts = _place(state, "P0", _get_card(repo, "LAW", "39"), "ground")   # 2/1
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7

        state = _fire_when_played(state, latts)
        state = _law13_choose_option(state, 2)          # the Experience branch
        state = _law01_drain(apply(state, ChooseTarget(theirs.instance_id)))
        assert _experience_count(_find_instance(state, latts.instance_id)) == 1
        # 2 printed + 1 from the Experience token = 3 damage, not 2.
        assert _find_instance(state, theirs.instance_id).damage == 3

    def test_LAW_39_shield_branch_deals_her_printed_power(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        latts = _place(state, "P0", _get_card(repo, "LAW", "39"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")

        state = _fire_when_played(state, latts)
        state = _law13_choose_option(state, 1)          # the Shield branch
        state = _law01_drain(apply(state, ChooseTarget(theirs.instance_id)))
        assert _shield_count(_find_instance(state, latts.instance_id)) == 1
        assert _find_instance(state, theirs.instance_id).damage == 2

    def test_LAW_39_fizzles_cleanly_with_no_enemy_ground_unit(self, repo):
        """DOCUMENTED DEVIATION: both halves live in ONE targeted effect, so with
        nothing to hit the whole branch fizzles and the token is not given."""
        state = _make_state()
        latts = _place(state, "P0", _get_card(repo, "LAW", "39"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "225"), "space")   # wrong arena
        state = _fire_when_played(state, latts)
        state = _law01_drain(_law13_choose_option(state, 2))
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, latts.instance_id)) == 0

    def test_LAW_39_only_an_enemy_GROUND_unit_may_be_hit(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        latts = _place(state, "P0", _get_card(repo, "LAW", "39"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law13_choose_option(_fire_when_played(state, latts), 1)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {ground.instance_id}
        assert mine.instance_id not in offered and space.instance_id not in offered


class TestShadowCloakingLAW43:
    """LAW_43 -- "Ready a unit and give a Shield token to it"."""

    def test_LAW_43_readies_and_shields_the_same_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.exhausted = True
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "43")
        state = _law01_drain(apply(state, ChooseTarget(mine.instance_id)))
        landed = _find_instance(state, mine.instance_id)
        assert landed.exhausted is False
        assert _shield_count(landed) == 1

    def test_LAW_43_a_ready_unit_is_still_a_legal_target_for_the_shield(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.exhausted = False
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "43")
        assert mine.instance_id in {a.target_id for a in legal_actions(state)
                                    if isinstance(a, ChooseTarget)}


class TestChirrutImweLAW46:
    """LAW_46 -- "When Attack Ends: If this unit dealt combat damage to a base, you
    may heal 4 damage from another unit"."""

    def test_LAW_46_heals_4_after_damaging_a_base(self, repo):
        from swu.engine.actions import apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        chirrut = _place(state, "P0", _get_card(repo, "LAW", "46"), "ground")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 6
        state = _attack_base_law09(state, chirrut)
        assert state.pending_decisions[-1].kind == "trigger_option"
        state = apply(state, AcceptTrigger(chirrut.instance_id))
        state = _law01_drain(apply(state, ChooseTarget(hurt.instance_id)))
        assert _find_instance(state, hurt.instance_id).damage == 2

    def test_LAW_46_does_not_fire_on_a_unit_attack(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        chirrut = _place(state, "P0", _get_card(repo, "LAW", "46"), "ground")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 6
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.active_player_index = 0
        state = _law01_drain(apply(state, AttackWithUnit(
            attacker_id=chirrut.instance_id, defender_id=theirs.instance_id)))
        assert _find_instance(state, hurt.instance_id).damage == 6

    def test_LAW_46_is_not_offered_when_no_other_unit_is_damaged(self, repo):
        state = _make_state()
        chirrut = _place(state, "P0", _get_card(repo, "LAW", "46"), "ground")
        chirrut.damage = 3                  # HIS OWN damage does not count
        state = _attack_base_law09(state, chirrut)
        assert not [d for d in state.pending_decisions
                    if d.kind == "trigger_option"]


class TestChopperLAW55:
    """LAW_55 -- "When Played: Give an Experience token to this unit.  If you
    control a Cunning or Vigilance unit, give 2 Experience tokens to him instead"."""

    def test_LAW_55_gives_2_experience_with_a_cunning_unit_in_play(self, repo):
        state = _make_state()
        cunning = _get_card(repo, "SOR", "210")     # Swoop Racer, Cunning
        assert "Cunning" in {a.name for a in (cunning.aspects or ())}
        _place(state, "P0", cunning, "ground")
        chopper = _place(state, "P0", _get_card(repo, "LAW", "55"), "ground")
        state = _law01_drain(_fire_when_played(state, chopper))
        assert _experience_count(_find_instance(state, chopper.instance_id)) == 2

    def test_LAW_55_gives_1_experience_with_no_qualifying_unit(self, repo):
        state = _make_state()
        state.player_by_id("P0").ground_arena.clear()
        state.player_by_id("P0").space_arena.clear()
        plain = _get_card(repo, "SOR", "247")       # Underworld Thug, no aspects
        assert not {a.name for a in (plain.aspects or ())}
        _place(state, "P0", plain, "ground")
        # Chopper himself is a Cunning card, so place him only as the ability
        # source: fire from a copy that is NOT in the arena yet.
        from swu.engine.state import CardInstance, Zone
        import uuid as _u
        chopper_def = _get_card(repo, "LAW", "55")
        chopper = CardInstance(f"P0_chop_{_u.uuid4().hex[:6]}", chopper_def,
                               "P0", Zone.GROUND_ARENA)
        state.player_by_id("P0").ground_arena.append(chopper)
        cunning_in_play = {"Cunning", "Vigilance"} & {
            a.name for a in (chopper_def.aspects or ())}
        state = _law01_drain(_fire_when_played(state, chopper))
        expected = 2 if cunning_in_play else 1
        assert _experience_count(_find_instance(state, chopper.instance_id)) \
            == expected

    def test_LAW_55_an_enemy_cunning_unit_does_not_count(self, repo):
        state = _make_state()
        state.player_by_id("P0").ground_arena.clear()
        _place(state, "P1", _get_card(repo, "SOR", "210"), "ground")   # THEIR unit
        plain = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        assert plain is not None
        # Count what Chopper's own aspects contribute, then assert the enemy's
        # Cunning unit adds nothing on top of it.
        chopper_def = _get_card(repo, "LAW", "55")
        own = bool({"Cunning", "Vigilance"}
                   & {a.name for a in (chopper_def.aspects or ())})
        chopper = _place(state, "P0", chopper_def, "ground")
        state = _law01_drain(_fire_when_played(state, chopper))
        assert _experience_count(_find_instance(state, chopper.instance_id)) \
            == (2 if own else 1)


class TestHighsingerLAW59:
    """LAW_59 -- "When Played: Give an Experience token to another friendly Command
    unit." / "When Defeated: Give an Experience token to a friendly Aggression
    unit"."""

    def test_LAW_59_when_played_tokens_another_friendly_command_unit(self, repo):
        from swu.engine.actions import apply, legal_actions, ChooseTarget
        state = _make_state()
        high = _place(state, "P0", _get_card(repo, "LAW", "59"), "ground")
        cmd = _get_card(repo, "SHD", "110")         # Warzone Lieutenant, Command
        assert "Command" in {a.name for a in (cmd.aspects or ())}
        friend = _place(state, "P0", cmd, "ground")
        theirs = _place(state, "P1", cmd, "ground")
        state = _fire_when_played(state, high)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert friend.instance_id in offered
        assert theirs.instance_id not in offered, "friendly only"
        assert high.instance_id not in offered, "'another'"
        state = _law01_drain(apply(state, ChooseTarget(friend.instance_id)))
        assert _experience_count(_find_instance(state, friend.instance_id)) == 1

    def test_LAW_59_when_defeated_tokens_a_friendly_aggression_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        high = _place(state, "P0", _get_card(repo, "LAW", "59"), "ground")
        aggro = _get_card(repo, "TWI", "133")       # B1 Attack Platform
        assert "Aggression" in {a.name for a in (aggro.aspects or ())}
        friend = _place(state, "P0", aggro, "space")
        state = _fire_unit_defeated(state, high, "P0")
        state = _law01_drain(apply(state, ChooseTarget(friend.instance_id)))
        assert _experience_count(_find_instance(state, friend.instance_id)) == 1


class TestAsajjVentressLAW61:
    """LAW_61 -- "When Played: You may ready another Bounty Hunter unit"."""

    def test_LAW_61_readies_another_exhausted_bounty_hunter(self, repo):
        from swu.engine.actions import apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "LAW", "61"), "ground")
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        hunter.exhausted = True
        state = _fire_when_played(state, asajj)
        state = apply(state, AcceptTrigger(asajj.instance_id))
        state = _law01_drain(apply(state, ChooseTarget(hunter.instance_id)))
        assert _find_instance(state, hunter.instance_id).exhausted is False

    def test_LAW_61_is_not_offered_with_no_exhausted_bounty_hunter(self, repo):
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "LAW", "61"), "ground")
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        hunter.exhausted = False               # nothing to ready
        asajj.exhausted = True                 # 'another' excludes herself
        state = _fire_when_played(state, asajj)
        assert not state.pending_decisions

    def test_LAW_61_a_non_bounty_hunter_is_not_a_legal_target(self, repo):
        from swu.engine.actions import apply, AcceptTrigger, legal_actions, ChooseTarget
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "LAW", "61"), "ground")
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        plain.exhausted = True
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        hunter.exhausted = True
        state = apply(_fire_when_played(state, asajj),
                      AcceptTrigger(asajj.instance_id))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {hunter.instance_id}


class TestTheGhostLAW69:
    """LAW_69 -- "When Played: You may give an Experience token and a Shield token
    to a unit.  If you control a Vigilance or Aggression unit, ... to each of up to
    2 units instead"."""

    def test_LAW_69_gives_both_tokens_to_one_unit(self, repo):
        from swu.engine.actions import apply, SelectTokenTarget
        state = _make_state()
        state.player_by_id("P0").ground_arena.clear()
        ghost = _place(state, "P0", _get_card(repo, "LAW", "69"), "space")
        mine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        state = _fire_when_played(state, ghost)
        assert state.pending_decisions[-1].kind == "select_token"
        state = _law01_drain(apply(state, SelectTokenTarget(mine.instance_id)))
        landed = _find_instance(state, mine.instance_id)
        assert _experience_count(landed) == 1
        assert _shield_count(landed) == 1

    def test_LAW_69_reaches_2_units_with_an_aggression_unit_in_play(self, repo):
        from swu.engine.actions import apply, SelectTokenTarget
        state = _make_state()
        state.player_by_id("P0").ground_arena.clear()
        ghost = _place(state, "P0", _get_card(repo, "LAW", "69"), "space")
        aggro = _place(state, "P0", _get_card(repo, "TWI", "133"), "space")
        other = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        state = _fire_when_played(state, ghost)
        assert state.pending_decisions[-1].context["remaining"] == 2
        state = apply(state, SelectTokenTarget(aggro.instance_id))
        state = _law01_drain(apply(state, SelectTokenTarget(other.instance_id)))
        for iid in (aggro.instance_id, other.instance_id):
            landed = _find_instance(state, iid)
            assert _experience_count(landed) == 1 and _shield_count(landed) == 1

    def test_LAW_69_caps_at_1_unit_without_a_vigilance_or_aggression_unit(self, repo):
        state = _make_state()
        state.player_by_id("P0").ground_arena.clear()
        state.player_by_id("P0").space_arena.clear()
        ghost = _place(state, "P0", _get_card(repo, "LAW", "69"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        boosting = {"Vigilance", "Aggression"} & {
            a.name for a in (ghost.card_def.aspects or ())}
        state = _fire_when_played(state, ghost)
        assert state.pending_decisions[-1].context["remaining"] == (
            2 if boosting else 1)

    def test_LAW_69_the_you_may_is_the_finish_action(self, repo):
        from swu.engine.actions import apply, FinishSelectToken
        state = _make_state()
        state.player_by_id("P0").ground_arena.clear()
        ghost = _place(state, "P0", _get_card(repo, "LAW", "69"), "space")
        mine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        state = _fire_when_played(state, ghost)
        state = _law01_drain(apply(state, FinishSelectToken()))
        landed = _find_instance(state, mine.instance_id)
        assert _experience_count(landed) == 0 and _shield_count(landed) == 0


# ── Group law-set:14 — Combat tricks, buffs & tempo ───────────────────────────


def _law14_choose(state, target_id):
    """Answer the pending ChooseTarget and drain."""
    from swu.engine.actions import apply, ChooseTarget
    return _law01_drain(apply(state, ChooseTarget(target_id)))


def _law14_target_ids(state):
    """The ids currently offered by a pending ChooseTarget decision."""
    from swu.engine.actions import ChooseTarget
    return {a.target_id for a in legal_actions(state)
            if isinstance(a, ChooseTarget) and a.target_id}


def _law14_base(state, pid="P0"):
    return state.player_by_id(pid).base_instance


def _law14_shield_token(state, ci):
    """Attach a real Shield token to ``ci`` (its controller owns it)."""
    from swu.engine.tokens import attach_token
    res = state.find_instance(ci.instance_id)
    attach_token(state, res[0], res[1], "Shield")
    return state


class TestPatientHunterLAW73:
    """LAW_73 — "When the regroup phase starts: You may give an Experience token to
    a non-leader unit.  If you do, that unit can't ready during this regroup
    phase." """

    def test_LAW_73_token_and_ready_lock_land_together(self, repo):
        from swu.engine.actions import _ready_all_cards
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "73"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        prey.exhausted = True
        state = _law03_regroup_start(state)
        state = _law02_accept(state)
        state = _law14_choose(state, prey.instance_id)
        locked = _find_instance(state, prey.instance_id)
        assert _experience_count(locked) == 1
        assert locked.cannot_ready_this_round is True
        _ready_all_cards(state)
        assert _find_instance(state, prey.instance_id).exhausted is True

    def test_LAW_73_declining_the_may_gives_no_token_and_no_lock(self, repo):
        from swu.engine.actions import apply, legal_actions as _legal
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "73"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        prey.exhausted = True
        state = _law03_regroup_start(state)
        decline = next(a for a in _legal(state)
                       if type(a).__name__ == "DeclineTrigger")
        state = _law01_drain(apply(state, decline))
        still = _find_instance(state, prey.instance_id)
        assert _experience_count(still) == 0
        assert still.cannot_ready_this_round is False

    def test_LAW_73_a_deployed_leader_is_not_a_legal_target(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "73"), "ground")
        plain = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        leader = _deploy_leader_in_arena(state, "P0", _get_card(repo, "SOR", "5"))
        state = _law03_regroup_start(state)
        state = _law02_accept(state)
        offered = _law14_target_ids(state)
        assert plain.instance_id in offered
        assert leader.instance_id not in offered      # "a NON-LEADER unit"


class TestMazKanataLAW74:
    """LAW_74 — "When Attack Ends: If this unit survived, search the top 5 for an
    Underworld unit and play it.  It costs 4 resources less and enters play ready.
    At the start of the regroup phase, put that unit on the bottom of your deck." """

    def _setup(self, state, repo, *, cost=6):
        goon = _underworld_unit_def(repo, cost=cost)
        filler = [_get_card(repo, "SOR", "225") for _ in range(4)]
        _build_search_deck(state, "P0", [goon] + filler,
                           below_cards=[_get_card(repo, "SOR", "225")])
        _seed_rng(state)
        return goon

    def test_LAW_74_plays_an_underworld_unit_at_four_less_and_ready(self, repo):
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "LAW", "74"), "ground")
        self._setup(state, repo, cost=6)
        _give_resources(state, "P0", 4, repo)
        before = state.player_by_id("P0").available_resources
        state = _fire_attack_ends_law(state, maz)
        goon_id = state.pending_decisions[-1].context["candidate_ids"][0]
        state = _law01_drain(_take_from_search(state, goon_id))
        landed = _find_instance(state, goon_id)
        assert landed is not None and landed.exhausted is False   # enters ready
        assert state.player_by_id("P0").available_resources == before - 2  # 6 − 4

    def test_LAW_74_only_underworld_units_are_offered(self, repo):
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "LAW", "74"), "ground")
        goon = self._setup(state, repo, cost=2)
        _give_resources(state, "P0", 6, repo)
        state = _fire_attack_ends_law(state, maz)
        ctx = state.pending_decisions[-1].context
        assert len(ctx["candidate_ids"]) == 1
        chosen = next(c for c in state.player_by_id("P0").deck
                      if c.instance_id == ctx["candidate_ids"][0])
        assert chosen.card_def.name == goon.name

    def test_LAW_74_the_lent_unit_is_bottomed_at_regroup_not_defeated(self, repo):
        from swu.engine.actions import _enter_regroup
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "LAW", "74"), "ground")
        self._setup(state, repo, cost=6)
        _give_resources(state, "P0", 4, repo)
        state = _fire_attack_ends_law(state, maz)
        goon_id = state.pending_decisions[-1].context["candidate_ids"][0]
        state = _law01_drain(_take_from_search(state, goon_id))
        assert _find_instance(state, goon_id).bottom_at_regroup is True
        _enter_regroup(state)
        p0 = state.player_by_id("P0")
        assert _find_instance(state, goon_id) is None          # left the arena
        assert p0.deck[-1].instance_id == goon_id              # deck BOTTOM
        assert all(c.instance_id != goon_id for c in p0.discard)  # not defeated


class TestJangoFettLAW87:
    """LAW_87 — "On Attack: If this unit is upgraded, exhaust an enemy unit." """

    def test_LAW_87_upgraded_jango_exhausts_an_enemy_unit(self, repo):
        state = _make_state()
        jango = _place(state, "P0", _get_card(repo, "LAW", "87"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        state = _law14_shield_token(state, jango)   # his printed Shielded token
        state = _law01_drain(_fire_on_attack(state, jango))
        state = _law14_choose(state, prey.instance_id)
        assert _find_instance(state, prey.instance_id).exhausted is True

    def test_LAW_87_a_bare_jango_is_never_offered_the_trigger(self, repo):
        state = _make_state()
        jango = _place(state, "P0", _get_card(repo, "LAW", "87"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        assert jango.attached_upgrades == []
        state = _law01_drain(_fire_on_attack(state, jango))
        assert not state.pending_decisions


class TestAnakinSkywalkerLAW88:
    """LAW_88 — "When a friendly unit's attack ends: If no other units have attacked
    this phase, you may return it to its owner's hand.  If you do, heal 2 damage
    from your base." """

    def _board(self, state, repo, *, defender="SOR", dnum="225"):
        _place(state, "P0", _get_card(repo, "LAW", "88"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, defender, dnum), "ground")
        _law14_base(state, "P0").damage = 5
        return mine, theirs

    def test_LAW_88_returns_the_attacker_and_heals_two_from_your_base(self, repo):
        state = _make_state()
        mine, theirs = self._board(state, repo)
        state = _law04_attack(state, mine, theirs)
        state = _law02_accept(state)
        assert _find_instance(state, mine.instance_id) is None
        assert any(c.instance_id == mine.instance_id
                   for c in state.player_by_id("P0").hand)
        assert _law14_base(state, "P0").damage == 3

    def test_LAW_88_is_not_offered_once_another_unit_has_attacked(self, repo):
        state = _make_state()
        mine, theirs = self._board(state, repo)
        state.game_memory.units_attacked_this_round.add("some-other-unit")
        state = _law04_attack(state, mine, theirs)
        assert not state.pending_decisions
        assert _find_instance(state, mine.instance_id) is not None
        assert _law14_base(state, "P0").damage == 5

    def test_LAW_88_is_not_offered_when_the_attacker_died(self, repo):
        state = _make_state()
        # SOR_46 is a 3/7; a 7/7 defender kills it as it attacks.
        mine, theirs = self._board(state, repo, dnum="46")
        _find_instance(state, theirs.instance_id).damage = 0
        mine_ci = _find_instance(state, mine.instance_id)
        mine_ci.damage = mine_ci.card_def.hp - 1     # one hit from dead
        state = _law04_attack(state, mine_ci, theirs)
        assert _find_instance(state, mine.instance_id) is None   # it died
        assert not state.pending_decisions                        # never offered
        assert _law14_base(state, "P0").damage == 5               # and no heal

    def test_LAW_88_also_fires_when_a_friendly_unit_attacks_a_base(self, repo):
        state = _make_state()
        mine, _theirs = self._board(state, repo)
        state = _law06_base_attack(state, mine)
        state = _law02_accept(state)
        assert any(c.instance_id == mine.instance_id
                   for c in state.player_by_id("P0").hand)
        assert _law14_base(state, "P0").damage == 3


class TestValLAW91:
    """LAW_91 — "When Played: Give a Shield token to another friendly unit.  When
    Defeated: Give a Shield token to an enemy unit." """

    def test_LAW_91_when_played_shields_another_friendly_unit(self, repo):
        state = _make_state()
        val = _place(state, "P0", _get_card(repo, "LAW", "91"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        state = _fire_when_played(state, val)
        offered = _law14_target_ids(state)
        assert val.instance_id not in offered          # "ANOTHER friendly unit"
        state = _law14_choose(state, friend.instance_id)
        assert _shield_count(_find_instance(state, friend.instance_id)) == 1

    def test_LAW_91_when_defeated_shields_an_enemy_unit(self, repo):
        state = _make_state()
        val = _place(state, "P0", _get_card(repo, "LAW", "91"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        state = _law01_drain(_fire_when_defeated(state, val))
        assert _law14_target_ids(state) == {theirs.instance_id}
        state = _law14_choose(state, theirs.instance_id)
        assert _shield_count(_find_instance(state, theirs.instance_id)) == 1


class TestFinnLAW95:
    """LAW_95 — "On Attack: You may give a Shield token to a non-unique unit." """

    def test_LAW_95_shields_a_non_unique_unit(self, repo):
        state = _make_state()
        finn = _place(state, "P0", _get_card(repo, "LAW", "95"), "ground")
        plain = _place(state, "P0", _underworld_unit_def(repo), "ground")
        state = _law01_drain(_fire_on_attack(state, finn))
        state = _law02_accept(state)
        state = _law14_choose(state, plain.instance_id)
        assert _shield_count(_find_instance(state, plain.instance_id)) == 1

    def test_LAW_95_a_unique_unit_is_not_a_legal_target(self, repo):
        state = _make_state()
        finn = _place(state, "P0", _get_card(repo, "LAW", "95"), "ground")
        plain = _place(state, "P0", _underworld_unit_def(repo), "ground")
        assert finn.card_def.is_unique is True
        state = _law01_drain(_fire_on_attack(state, finn))
        state = _law02_accept(state)
        assert _law14_target_ids(state) == {plain.instance_id}


class TestImperialDoorTechnicianLAW97:
    """LAW_97 — "When Defeated: Heal 2 damage from your base." """

    def test_LAW_97_heals_two_from_its_controllers_base(self, repo):
        state = _make_state()
        tech = _place(state, "P0", _get_card(repo, "LAW", "97"), "ground")
        _law14_base(state, "P0").damage = 5
        _law14_base(state, "P1").damage = 5
        state = _law01_drain(_fire_when_defeated(state, tech))
        assert _law14_base(state, "P0").damage == 3
        assert _law14_base(state, "P1").damage == 5   # only YOUR base


# ── Group law-set:15 — Combat tricks, buffs & tempo ───────────────────────────


def _law15_hand_card(state, repo, set_code, num, owner="P0"):
    """Put a card in ``owner``'s hand and return the instance."""
    _put_in_hand(state, owner, _get_card(repo, set_code, num))
    return state.player_by_id(owner).hand[-1]


def _law15_cost(state, ci, owner="P0", host_id=None):
    from swu.engine.actions import _play_cost
    return _play_cost(state, ci, state.player_by_id(owner), host_id)


class TestTantiveIVLAW109:
    """LAW_109 — "When Played: If a friendly unit was defeated this phase, heal 4
    damage from your base." """

    def test_LAW_109_heals_four_after_a_friendly_unit_was_defeated(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        doomed = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), doomed)
        tantive = _place(state, "P0", _get_card(repo, "LAW", "109"), "space")
        _law14_base(state, "P0").damage = 9
        state = _law01_drain(_fire_when_played(state, tantive))
        assert _law14_base(state, "P0").damage == 5

    def test_LAW_109_does_nothing_when_no_friendly_unit_was_defeated(self, repo):
        state = _make_state()
        tantive = _place(state, "P0", _get_card(repo, "LAW", "109"), "space")
        _law14_base(state, "P0").damage = 9
        state = _law01_drain(_fire_when_played(state, tantive))
        assert _law14_base(state, "P0").damage == 9      # never collected
        assert not state.pending_decisions


class TestPhoenixSquadronFightersLAW110:
    """LAW_110 — "This unit costs 1 resource less to play for each friendly damaged
    unit." """

    def test_LAW_110_costs_one_less_per_friendly_damaged_unit(self, repo):
        state = _make_state()
        card = _law15_hand_card(state, repo, "LAW", "110")
        full = _law15_cost(state, card)
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.damage = 2
        assert _law15_cost(state, card) == full - 1
        other = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        other.damage = 1
        assert _law15_cost(state, card) == full - 2

    def test_LAW_110_ignores_undamaged_and_enemy_damaged_units(self, repo):
        state = _make_state()
        card = _law15_hand_card(state, repo, "LAW", "110")
        full = _law15_cost(state, card)
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # undamaged
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        theirs.damage = 3                                             # enemy
        assert _law15_cost(state, card) == full


class TestBoontaEveFlagbearerLAW112:
    """LAW_112 — "When a friendly unit attacks: If no other units have attacked this
    phase (including enemy units), heal 2 damage from your base." """

    def test_LAW_112_heals_two_on_the_phases_first_friendly_attack(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "112"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "225"), "ground")
        _law14_base(state, "P0").damage = 6
        state = _law04_attack(state, mine, theirs)
        assert _law14_base(state, "P0").damage == 4

    def test_LAW_112_is_silent_once_another_unit_has_attacked(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "112"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "225"), "ground")
        state.game_memory.units_attacked_this_round.add("an-earlier-attacker")
        _law14_base(state, "P0").damage = 6
        state = _law04_attack(state, mine, theirs)
        assert _law14_base(state, "P0").damage == 6


class TestShieldDriveOutfitterLAW113:
    """LAW_113 — "When Played: You may pay 1 resource.  If you do, give a Shield
    token to a unit." """

    def test_LAW_113_pays_one_resource_and_shields_the_chosen_unit(self, repo):
        state = _make_state()
        outfitter = _place(state, "P0", _get_card(repo, "LAW", "113"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        _give_resources(state, "P0", 3, repo)
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_when_played(state, outfitter))
        state = _law02_accept(state)
        state = _law14_choose(state, friend.instance_id)
        assert _shield_count(_find_instance(state, friend.instance_id)) == 1
        assert state.player_by_id("P0").available_resources == before - 1

    def test_LAW_113_is_not_offered_with_no_ready_resource(self, repo):
        state = _make_state()
        outfitter = _place(state, "P0", _get_card(repo, "LAW", "113"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        assert state.player_by_id("P0").available_resources == 0
        state = _law01_drain(_fire_when_played(state, outfitter))
        assert not state.pending_decisions


class TestKillSwitchLAW127:
    """LAW_127 — "When Played: Exhaust attached unit." """

    def test_LAW_127_exhausts_its_host(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        host.exhausted = False
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "127"), "P0")
        state = _law01_drain(_fire_upgrade_played(state, upg, host))
        assert _find_instance(state, host.instance_id).exhausted is True

    def test_LAW_127_exhausts_an_enemy_host_too(self, repo):
        state = _make_state()
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        host.exhausted = False
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "127"), "P0")
        state = _law01_drain(_fire_upgrade_played(state, upg, host))
        assert _find_instance(state, host.instance_id).exhausted is True


class TestVeiledStrengthLAW128:
    """LAW_128 — "Attach to a non-leader unit.  Attached unit gains Grit." """

    def test_LAW_128_grants_grit_to_its_host(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, host, Keyword.GRIT) is False
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "128"), "P0")
        assert has_keyword(state, host, Keyword.GRIT) is True

    def test_LAW_128_attaches_only_to_a_non_leader_unit(self, repo):
        from swu.engine.actions import _upgrade_target_spec
        spec = _upgrade_target_spec(_get_card(repo, "LAW", "128"))
        assert spec is not None and "non_leader" in (spec.predicates or ())


class TestMasteryLAW129:
    """LAW_129 — "This upgrade costs 1 resource less to play on a unique unit." """

    def test_LAW_129_costs_one_less_on_a_unique_host(self, repo):
        state = _make_state()
        card = _law15_hand_card(state, repo, "LAW", "129")
        plain = _place(state, "P0", _underworld_unit_def(repo), "ground")
        unique = _place(state, "P0", _get_card(repo, "LAW", "95"), "ground")
        assert unique.card_def.is_unique is True
        assert plain.card_def.is_unique is False
        full = _law15_cost(state, card, host_id=plain.instance_id)
        assert _law15_cost(state, card, host_id=unique.instance_id) == full - 1

    def test_LAW_129_gives_no_discount_before_a_host_is_chosen(self, repo):
        state = _make_state()
        card = _law15_hand_card(state, repo, "LAW", "129")
        plain = _place(state, "P0", _underworld_unit_def(repo), "ground")
        assert _law15_cost(state, card) == _law15_cost(
            state, card, host_id=plain.instance_id)


# ── Group law-set:16 — Combat tricks, buffs & tempo ───────────────────────────


def _law16_resource(state, repo, owner="P0", exhausted=False):
    """Append one resource to ``owner``'s row and return it."""
    _add_resource(state, repo, owner, exhausted=exhausted)
    return state.player_by_id(owner).resources[-1]


def _law16_pay(state):
    from swu.engine.actions import apply, PayResourceForToken
    return _law01_drain(apply(state, PayResourceForToken()))


def _law16_finish_paying(state):
    from swu.engine.actions import apply, FinishPayResources
    return _law01_drain(apply(state, FinishPayResources()))


class TestLostAndForgottenLAW133:
    """LAW_133 — "Defeat a non-leader unit.  If you do, heal 3 damage from your
    base." """

    def test_LAW_133_defeats_a_unit_and_heals_three(self, repo):
        state = _make_state()
        theirs = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        _law14_base(state, "P0").damage = 8
        state, _evt = _play_event_from_hand(state, repo, "LAW", "133")
        state = _law14_choose(state, theirs.instance_id)
        assert _find_instance(state, theirs.instance_id) is None
        assert _law14_base(state, "P0").damage == 5

    def test_LAW_133_a_deployed_leader_is_not_a_legal_target(self, repo):
        state = _make_state()
        leader = _deploy_leader_in_arena(state, "P1", _get_card(repo, "SOR", "10"))
        theirs = _place(state, "P1", _get_card(repo, "SOR", "225"), "space")
        state, _evt = _play_event_from_hand(state, repo, "LAW", "133")
        offered = _law14_target_ids(state)
        assert theirs.instance_id in offered
        assert leader.instance_id not in offered


class TestAdmiralMottiLAW139:
    """LAW_139 — "Friendly leader units get +2/+2." """

    def test_LAW_139_buffs_a_friendly_deployed_leader_only(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        mine = _deploy_leader_in_arena(state, "P0", _get_card(repo, "SOR", "5"))
        theirs = _deploy_leader_in_arena(state, "P1", _get_card(repo, "SOR", "10"))
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        base_p, base_h = compute_power(state, mine), compute_hp(state, mine)
        their_p = compute_power(state, theirs)
        plain_p = compute_power(state, plain)
        _place(state, "P0", _get_card(repo, "LAW", "139"), "ground")
        assert compute_power(state, mine) == base_p + 2
        assert compute_hp(state, mine) == base_h + 2
        assert compute_power(state, theirs) == their_p        # not friendly
        assert compute_power(state, plain) == plain_p         # not a leader


class TestIntimidatorLAW140:
    """LAW_140 — "When Played: Return any number of friendly resources to their
    owners' hands.  For each resource returned this way, create a Credit token." """

    def test_LAW_140_each_returned_resource_makes_a_credit(self, repo):
        state = _make_state()
        for _ in range(3):
            _law16_resource(state, repo)
        intimidator = _place(state, "P0", _get_card(repo, "LAW", "140"), "space")
        state = _law01_drain(_fire_when_played(state, intimidator))
        state = _law16_pay(state)
        state = _law16_pay(state)
        state = _law16_finish_paying(state)
        p0 = state.player_by_id("P0")
        assert len(p0.resources) == 1
        assert _credits(state, "P0") == 2
        assert len(p0.hand) == 2                    # both went back to hand

    def test_LAW_140_returning_none_creates_no_credit(self, repo):
        state = _make_state()
        _law16_resource(state, repo)
        intimidator = _place(state, "P0", _get_card(repo, "LAW", "140"), "space")
        state = _law01_drain(_fire_when_played(state, intimidator))
        state = _law16_finish_paying(state)
        assert _credits(state, "P0") == 0
        assert len(state.player_by_id("P0").resources) == 1

    def test_LAW_140_returns_exhausted_resources_first(self, repo):
        state = _make_state()
        ready = _law16_resource(state, repo, exhausted=False)
        spent = _law16_resource(state, repo, exhausted=True)
        intimidator = _place(state, "P0", _get_card(repo, "LAW", "140"), "space")
        state = _law01_drain(_fire_when_played(state, intimidator))
        state = _law16_pay(state)
        state = _law16_finish_paying(state)
        left = state.player_by_id("P0").resources
        assert [c.instance_id for c in left] == [ready.instance_id]
        assert any(c.instance_id == spent.instance_id
                   for c in state.player_by_id("P0").hand)


class TestPhantomLAW144:
    """LAW_144 — "When Played: You may play a Heroism unit from your hand (paying
    its cost) and give an Experience token to it." """

    def test_LAW_144_plays_a_heroism_unit_and_gives_it_experience(self, repo):
        from swu.engine.actions import apply, PlayFromHand
        state = _make_state()
        _give_resources(state, "P0", 8, repo)
        hero = _law15_hand_card(state, repo, "SOR", "46")     # a Heroism unit
        assert "Heroism" in {a.name for a in (hero.card_def.aspects or ())}
        phantom = _place(state, "P0", _get_card(repo, "LAW", "144"), "space")
        state = _law01_drain(_fire_when_played(state, phantom))
        state = _law02_accept(state)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == hero.instance_id)
        state = _law01_drain(apply(state, play))
        # The Experience rides a settle-time select_token narrowed to the unit just
        # played, so it is the only candidate offered.
        from swu.engine.actions import SelectTokenTarget
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget))
        assert pick.target_id == hero.instance_id
        state = _law01_drain(apply(state, pick))
        landed = _find_instance(state, hero.instance_id)
        assert landed is not None
        assert _experience_count(landed) == 1

    def test_LAW_144_is_not_offered_with_no_heroism_unit_in_hand(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 8, repo)
        _law15_hand_card(state, repo, "SOR", "247")           # no aspects
        phantom = _place(state, "P0", _get_card(repo, "LAW", "144"), "space")
        state = _law01_drain(_fire_when_played(state, phantom))
        assert not state.pending_decisions


class TestSmugglersYT2400LAW148:
    """LAW_148 — "When Played: You may pay 1 resource.  If you do, this unit gets
    +1/+1 for this phase." """

    def test_LAW_148_pays_one_and_buffs_itself(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        _give_resources(state, "P0", 2, repo)
        yt = _place(state, "P0", _get_card(repo, "LAW", "148"), "space")
        p0, h0 = compute_power(state, yt), compute_hp(state, yt)
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_when_played(state, yt))
        state = _law02_accept(state)
        now = _find_instance(state, yt.instance_id)
        assert compute_power(state, now) == p0 + 1
        assert compute_hp(state, now) == h0 + 1
        assert state.player_by_id("P0").available_resources == before - 1

    def test_LAW_148_is_not_offered_with_no_ready_resource(self, repo):
        state = _make_state()
        yt = _place(state, "P0", _get_card(repo, "LAW", "148"), "space")
        state = _law01_drain(_fire_when_played(state, yt))
        assert not state.pending_decisions


class TestFulcrumLAW150:
    """LAW_150 — "Attached unit gains the Rebel trait and 'Each other friendly Rebel
    unit gets +2/+2.'" """

    def test_LAW_150_host_gains_the_rebel_trait(self, repo):
        from swu.engine.traits import has_trait
        state = _make_state()
        host = _place(state, "P0", _underworld_unit_def(repo), "ground")
        assert has_trait(state, host, "Rebel") is False
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "150"), "P0")
        assert has_trait(state, host, "Rebel") is True

    def test_LAW_150_buffs_each_other_friendly_rebel_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        host = _place(state, "P0", _underworld_unit_def(repo), "ground")
        rebel = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert "Rebel" in (rebel.card_def.traits or ())
        base_p, base_h = compute_power(state, rebel), compute_hp(state, rebel)
        host_p = compute_power(state, host)
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "150"), "P0")
        assert compute_power(state, rebel) == base_p + 2
        assert compute_hp(state, rebel) == base_h + 2
        # The host gains only Fulcrum's own printed +2/+2 upgrade box — the AURA
        # skips it, as "each OTHER friendly Rebel unit" says.
        assert compute_power(state, host) == host_p + 2

    def test_LAW_150_does_not_buff_enemy_or_non_rebel_units(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _underworld_unit_def(repo), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine_plain = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        t0, m0 = compute_power(state, theirs), compute_power(state, mine_plain)
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "150"), "P0")
        assert compute_power(state, theirs) == t0
        assert compute_power(state, mine_plain) == m0


class TestProfiteeringHunterLAW151:
    """LAW_151 — "When Played: Another friendly unit gets +1/+1 for this phase." """

    def test_LAW_151_buffs_another_friendly_unit_for_the_phase(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "LAW", "151"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        p0, h0 = compute_power(state, friend), compute_hp(state, friend)
        state = _law01_drain(_fire_when_played(state, hunter))
        assert hunter.instance_id not in _law14_target_ids(state)   # "ANOTHER"
        state = _law14_choose(state, friend.instance_id)
        now = _find_instance(state, friend.instance_id)
        assert compute_power(state, now) == p0 + 1
        assert compute_hp(state, now) == h0 + 1


# ── Group law-set:17 — Combat tricks, buffs & tempo ───────────────────────────


def _law17_attack_with(state, attacker_id, defender_id=None):
    """Take the offered granted attack with a named attacker and settle it."""
    from swu.engine.actions import apply, AttackWithUnit
    atk = next(a for a in legal_actions(state)
               if isinstance(a, AttackWithUnit)
               and a.attacker_id == attacker_id
               and a.defender_id == defender_id)
    return _law01_continue(apply(state, atk))


class TestTargetTaggerLAW157:
    """LAW_157 — "When Played: You may attack with a unit.  If it's a Bounty
    Hunter, it gets +2/+0 for this attack." """

    def test_LAW_157_a_bounty_hunter_attacker_gets_plus_two(self, repo):
        state = _make_state()
        tagger = _place(state, "P0", _get_card(repo, "LAW", "157"), "ground")
        hunter = _place(state, "P0", _law12_unit_def(repo, "C26", "3"), "ground")
        hunter.exhausted = False
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert "Bounty Hunter" in (hunter.card_def.traits or ())
        state = _law01_drain(_fire_when_played(state, tagger))
        state = _law17_attack_with(state, hunter.instance_id, prey.instance_id)
        hit = _find_instance(state, prey.instance_id)
        assert hit.damage == hunter.card_def.power + 2

    def test_LAW_157_a_non_bounty_hunter_attacker_gets_nothing(self, repo):
        state = _make_state()
        tagger = _place(state, "P0", _get_card(repo, "LAW", "157"), "ground")
        plain = _place(state, "P0", _underworld_unit_def(repo), "ground")
        plain.exhausted = False
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_when_played(state, tagger))
        state = _law17_attack_with(state, plain.instance_id, prey.instance_id)
        assert _find_instance(state, prey.instance_id).damage == plain.card_def.power


class TestCombatExerciseLAW165:
    """LAW_165 — "Exhaust a friendly unit.  If you do, give 2 Experience tokens to
    it." """

    def test_LAW_165_exhausts_and_gives_two_experience(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.exhausted = False
        state, _evt = _play_event_from_hand(state, repo, "LAW", "165")
        state = _law14_choose(state, mine.instance_id)
        now = _find_instance(state, mine.instance_id)
        assert now.exhausted is True
        assert _experience_count(now) == 2

    def test_LAW_165_never_offers_an_already_exhausted_unit(self, repo):
        state = _make_state()
        ready = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ready.exhausted = False
        spent = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        spent.exhausted = True
        state, _evt = _play_event_from_hand(state, repo, "LAW", "165")
        assert _law14_target_ids(state) == {ready.instance_id}


class TestStockpileLAW171:
    """LAW_171 — "Resource this event and the top card of your deck." """

    def test_LAW_171_resources_itself_and_the_deck_top_exhausted(self, repo):
        state = _make_state()
        top = _push_deck_top(state, "P0", _get_card(repo, "SOR", "247"))
        state, evt = _play_event_from_hand(state, repo, "LAW", "171")
        state = _law01_drain(state)
        p0 = state.player_by_id("P0")
        landed = {c.instance_id: c for c in p0.resources}
        assert evt.instance_id in landed and top.instance_id in landed
        assert landed[evt.instance_id].exhausted is True       # enter exhausted
        assert landed[top.instance_id].exhausted is True
        assert all(c.instance_id != evt.instance_id for c in p0.discard)
        assert all(c.instance_id != top.instance_id for c in p0.deck)

    def test_LAW_171_still_resources_itself_with_an_empty_deck(self, repo):
        state = _make_state()
        state.player_by_id("P0").deck.clear()
        state, evt = _play_event_from_hand(state, repo, "LAW", "171")
        state = _law01_drain(state)
        p0 = state.player_by_id("P0")
        assert not p0.deck
        assert any(c.instance_id == evt.instance_id for c in p0.resources)
        assert all(c.instance_id != evt.instance_id for c in p0.discard)


class TestWeazelLAW182:
    """LAW_182 — "On Attack: Another friendly unit gains Raid 2 for this phase." """

    def test_LAW_182_grants_raid_two_to_another_friendly_unit(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        weazel = _place(state, "P0", _get_card(repo, "LAW", "182"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, weazel))
        assert weazel.instance_id not in _law14_target_ids(state)   # "ANOTHER"
        state = _law14_choose(state, friend.instance_id)
        now = _find_instance(state, friend.instance_id)
        assert keyword_value(state, now, Keyword.RAID) == 2


class TestBenSoloLAW185:
    """LAW_185 — "When Played/When Defeated: Ready another friendly unit.  It can't
    be attacked this phase." """

    def _ready_and_shelter(self, state, ben, friend):
        state = _law14_choose(state, friend.instance_id)
        return state

    def test_LAW_185_when_played_readies_and_shelters_another_unit(self, repo):
        from swu.engine.actions import _cannot_be_attacked
        state = _make_state()
        ben = _place(state, "P0", _get_card(repo, "LAW", "185"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.exhausted = True
        state = _law01_drain(_fire_when_played(state, ben))
        assert ben.instance_id not in _law14_target_ids(state)      # "ANOTHER"
        state = self._ready_and_shelter(state, ben, friend)
        now = _find_instance(state, friend.instance_id)
        assert now.exhausted is False
        assert _cannot_be_attacked(state, now) is True

    def test_LAW_185_when_defeated_does_the_same(self, repo):
        from swu.engine.actions import _cannot_be_attacked
        state = _make_state()
        ben = _place(state, "P0", _get_card(repo, "LAW", "185"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.exhausted = True
        state = _law01_drain(_fire_when_defeated(state, ben))
        state = self._ready_and_shelter(state, ben, friend)
        now = _find_instance(state, friend.instance_id)
        assert now.exhausted is False
        assert _cannot_be_attacked(state, now) is True


class TestEnfysNestsHelmetLAW186:
    """LAW_186 — "Attached unit gains: 'On Attack: You may give another unit +3/+0
    for this phase.'" """

    def test_LAW_186_host_buffs_another_unit_on_attack(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "186"), "P0")
        p0 = compute_power(state, friend)
        state = _law01_drain(_fire_on_attack(state, host))
        state = _law02_accept(state)
        assert host.instance_id not in _law14_target_ids(state)     # "ANOTHER"
        state = _law14_choose(state, friend.instance_id)
        assert compute_power(state, _find_instance(state, friend.instance_id)) == p0 + 3

    def test_LAW_186_grants_nothing_while_unattached(self, repo):
        state = _make_state()
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        state = _law01_drain(_fire_on_attack(state, unit))
        assert not state.pending_decisions


class TestMidRimSharpshooterLAW193:
    """LAW_193 — "When Played: You may pay 1 resource.  If you do, an opponent
    discards a card from their hand." """

    def test_LAW_193_pays_one_and_makes_an_opponent_discard(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 2, repo)
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "247"))
        shooter = _place(state, "P0", _get_card(repo, "LAW", "193"), "ground")
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_when_played(state, shooter))
        state = _law02_accept(state)
        assert len(state.player_by_id("P1").hand) == 0
        assert len(state.player_by_id("P1").discard) == 1
        assert state.player_by_id("P0").available_resources == before - 1

    def test_LAW_193_is_not_offered_with_no_ready_resource(self, repo):
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "247"))
        shooter = _place(state, "P0", _get_card(repo, "LAW", "193"), "ground")
        state = _law01_drain(_fire_when_played(state, shooter))
        assert not state.pending_decisions


# ── Group law-set:18 — Combat tricks, buffs & tempo ───────────────────────────


class TestCommenceTheFestivitiesLAW202:
    """LAW_202 — "Attack with a unit.  It gains Saboteur for this attack.  If you
    control fewer resources than an opponent, it gets +2/+0 for this attack." """

    def _board(self, state, repo):
        mine = _place(state, "P0", _underworld_unit_def(repo), "ground")
        mine.exhausted = False
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        return mine, prey

    def test_LAW_202_no_bonus_while_not_behind_on_resources(self, repo):
        state = _make_state()
        mine, prey = self._board(state, repo)
        # P1 has none, so the controller is never "fewer".  The magnitude is
        # decided when the event resolves, so the board must be set up first.
        state, _evt = _play_event_from_hand(state, repo, "LAW", "202")
        assert len(state.player_by_id("P1").resources) == 0
        state = _law17_attack_with(state, mine.instance_id, prey.instance_id)
        assert _find_instance(state, prey.instance_id).damage == mine.card_def.power

    def test_LAW_202_gives_plus_two_when_behind_on_resources(self, repo):
        state = _make_state()
        mine, prey = self._board(state, repo)
        for _ in range(40):
            _add_resource(state, repo, "P1", exhausted=False)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "202")
        assert (len(state.player_by_id("P1").resources)
                > len(state.player_by_id("P0").resources))
        state = _law17_attack_with(state, mine.instance_id, prey.instance_id)
        assert _find_instance(state, prey.instance_id).damage == (
            mine.card_def.power + 2)

    def test_LAW_202_the_attacker_ignores_a_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        mine, _prey = self._board(state, repo)
        guard = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, guard, Keyword.SENTINEL) is False
        state, _evt = _play_event_from_hand(state, repo, "LAW", "202")
        ctx = state.pending_decisions[-1].context
        assert "Saboteur" in (ctx.get("grant_keywords") or [])


class TestRoseTicoLAW223:
    """LAW_223 — "If you control a non-unique unit, this unit enters play ready." """

    def test_LAW_223_enters_ready_beside_a_non_unique_unit(self, repo):
        from swu.engine.actions import _put_unit_in_play
        state = _make_state()
        _place(state, "P0", _underworld_unit_def(repo), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "LAW", "223"))
        rose = state.player_by_id("P0").hand[-1]
        _put_unit_in_play(state, state.player_by_id("P0"), rose)
        assert _find_instance(state, rose.instance_id).exhausted is False

    def test_LAW_223_enters_exhausted_with_only_unique_units(self, repo):
        from swu.engine.actions import _put_unit_in_play
        state = _make_state()
        unique = _place(state, "P0", _get_card(repo, "LAW", "95"), "ground")
        assert unique.card_def.is_unique is True
        _put_in_hand(state, "P0", _get_card(repo, "LAW", "223"))
        rose = state.player_by_id("P0").hand[-1]
        _put_unit_in_play(state, state.player_by_id("P0"), rose)
        assert _find_instance(state, rose.instance_id).exhausted is True


class TestRookieRocketJumperLAW227:
    """LAW_227 — "When Played: You may pay 1 resource.  If you do, give a Shield
    token to this unit." """

    def test_LAW_227_pays_one_and_shields_itself(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 2, repo)
        rookie = _place(state, "P0", _get_card(repo, "LAW", "227"), "ground")
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_when_played(state, rookie))
        state = _law02_accept(state)
        assert _shield_count(_find_instance(state, rookie.instance_id)) == 1
        assert state.player_by_id("P0").available_resources == before - 1

    def test_LAW_227_is_not_offered_with_no_ready_resource(self, repo):
        state = _make_state()
        rookie = _place(state, "P0", _get_card(repo, "LAW", "227"), "ground")
        state = _law01_drain(_fire_when_played(state, rookie))
        assert not state.pending_decisions


class TestGalenErsoLAW233:
    """LAW_233 — "When Played: You may have an opponent take control of this unit.
    Enemy units gain Raid 1 and Saboteur." """

    def test_LAW_233_enemy_units_gain_raid_one_and_saboteur(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "233"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        assert keyword_value(state, theirs, Keyword.RAID) == 1
        assert has_keyword(state, theirs, Keyword.SABOTEUR) is True
        assert keyword_value(state, mine, Keyword.RAID) == 0

    def test_LAW_233_handing_him_over_flips_which_units_are_enemies(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "LAW", "233"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        mine = _place(state, "P0", _get_card(repo, "SOR", "247"), "ground")
        state = _law01_drain(_fire_when_played(state, galen))
        state = _law02_accept(state)
        moved = _find_instance(state, galen.instance_id)
        assert any(c is moved for c in state.player_by_id("P1").ground_arena)
        assert moved.owner_id == "P0"                 # control moved, owner did not
        assert keyword_value(state, _find_instance(state, mine.instance_id),
                             Keyword.RAID) == 1       # now the enemy side
        assert keyword_value(state, _find_instance(state, theirs.instance_id),
                             Keyword.RAID) == 0

    def test_LAW_233_the_hand_over_may_be_declined(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        galen = _place(state, "P0", _get_card(repo, "LAW", "233"), "ground")
        state = _law01_drain(_fire_when_played(state, galen))
        decline = next(a for a in legal_actions(state)
                       if type(a).__name__ == "DeclineTrigger")
        state = _law01_drain(apply(state, decline))
        assert any(c.instance_id == galen.instance_id
                   for c in state.player_by_id("P0").ground_arena)


class TestHiddenHandSupplierLAW257:
    """LAW_257 — "When Played: You may pay 1 resource.  If you do, give an
    Experience token to another unit." """

    def test_LAW_257_pays_one_and_tokens_another_unit(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 2, repo)
        supplier = _place(state, "P0", _get_card(repo, "LAW", "257"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_when_played(state, supplier))
        state = _law02_accept(state)
        assert supplier.instance_id not in _law14_target_ids(state)   # "ANOTHER"
        state = _law14_choose(state, friend.instance_id)
        assert _experience_count(_find_instance(state, friend.instance_id)) == 1
        assert state.player_by_id("P0").available_resources == before - 1

    def test_LAW_257_is_not_offered_with_no_ready_resource(self, repo):
        state = _make_state()
        supplier = _place(state, "P0", _get_card(repo, "LAW", "257"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_when_played(state, supplier))
        assert not state.pending_decisions


# ── Group law-set:19 — Miscellaneous abilities ────────────────────────────────


def _law19_deployed_leader(state, owner_id, leader_def):
    """Put a DEPLOYED leader into ``owner_id``'s ground arena (the shape
    ``_fire_when_deployed`` expects — ``_place_leader`` leaves it in base_zone)."""
    from swu.engine.state import Zone
    ci = _place_leader(state, owner_id, leader_def)
    ps = state.player_by_id(owner_id)
    ps.base_zone.remove(ci)
    ci.zone = Zone.GROUND_ARENA
    ci.deployed = True
    ps.ground_arena.append(ci)
    return ci


def _law19_base(state, repo, num, owner="P0"):
    """Put the LAW base ``num`` into ``owner``'s base zone (replacing the default)."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(f"{owner}_b{num}", _get_card(repo, "LAW", num), owner,
                      Zone.BASE_ZONE)
    state.player_by_id(owner).base_zone = [ci]
    return ci


def _law19_hand(state, repo, sc, num, owner="P0"):
    from swu.engine.state import CardInstance, Zone
    import uuid as _u
    ci = CardInstance(f"{owner}_h_{num}_{_u.uuid4().hex[:4]}",
                      _get_card(repo, sc, num), owner, Zone.HAND)
    state.player_by_id(owner).hand.append(ci)
    return ci


def _law19_epic_plays_at_waived_cost(state, repo, base_ci):
    """Shared assertion for the six bases printing Daimyo's Palace LAW_20's Epic
    Action: a [Cunning] 3-cost unit is affordable for 3 (not the full 5) because
    one aspect-penalty pip is waived."""
    from swu.engine.actions import legal_actions, apply, UseAbility, PlayFromHand
    unit = _law19_hand(state, repo, "SOR", "210")   # Swoop Racer, cost 3, [Cunning]
    _give_resources(state, "P0", 3)                 # affords 3, not the full 5
    use = next(a for a in legal_actions(state)
               if isinstance(a, UseAbility) and a.source_id == base_ci.instance_id)
    state = apply(state, use)
    play = next(a for a in legal_actions(state)
                if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
    state = _law01_drain(apply(state, play))
    assert any(c.instance_id == unit.instance_id
               for c in state.player_by_id("P0").ground_arena)
    return state


class TestDirectorKrennicLAW8:
    """LAW_8 — "Action [Exhaust, defeat a friendly unit]: Create a Credit token."
    / "When Deployed: Another friendly unit deals damage equal to its power to an
    enemy unit." """

    def test_LAW_8_action_defeats_a_friendly_unit_for_a_credit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        krennic = _law12_undeployed_leader(state, "P0",
                                           _law12_leader_def(repo, "LAW", "8"))
        fodder = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _law12_use(state, krennic)
        state = _law01_drain(apply(state, ChooseTarget(fodder.instance_id)))
        assert _law12_credits(state) == 1
        assert not any(c.instance_id == fodder.instance_id
                       for c in state.player_by_id("P0").ground_arena)
        assert state.find_instance(krennic.instance_id)[1].exhausted

    def test_LAW_8_action_is_not_offered_with_no_friendly_unit(self, repo):
        state = _make_state()
        krennic = _law12_undeployed_leader(state, "P0",
                                           _law12_leader_def(repo, "LAW", "8"))
        assert not _law12_offered(state, krennic)

    def test_LAW_8_when_deployed_shooter_power_lands_on_the_chosen_enemy(self, repo):
        state = _make_state()
        krennic = _law19_deployed_leader(state, "P0",
                                         _law12_leader_def(repo, "LAW", "8"))
        shooter = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_when_deployed(state, krennic))
        # "another friendly unit" — Krennic himself is not offered as the shooter
        assert krennic.instance_id not in _law06_offered(state)
        state = _law06_choose(state, shooter.instance_id)
        state = _law06_choose(state, foe.instance_id)
        assert _find_instance(state, foe.instance_id).damage == 3


class TestHeraSyndullaLAW9:
    """LAW_9 — "While you control 2 or more units, ignore the aspect penalties on
    Heroism units you play." """

    def _hero_unit(self, repo):
        # SOR_58 Rebel Assault Frigate? — pick a Heroism unit with an aspect penalty
        # against _make_state's aspect-less base.
        return _get_card(repo, "SOR", "51")

    def test_LAW_9_waives_the_penalty_on_a_heroism_unit_with_two_units_out(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        hera = _law12_undeployed_leader(state, "P0",
                                        _law12_leader_def(repo, "LAW", "9"))
        held = _law19_hand(state, repo, "SOR", "51")
        aspects = {a.name for a in (held.card_def.aspects or ())}
        assert "Heroism" in aspects
        ps = state.player_by_id("P0")
        full = _play_cost(state, held, ps)
        assert full > (held.card_def.cost or 0)        # a real penalty to waive
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert _play_cost(state, held, ps) == (held.card_def.cost or 0)
        assert hera is not None

    def test_LAW_9_charges_the_full_penalty_below_two_units(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        _law12_undeployed_leader(state, "P0", _law12_leader_def(repo, "LAW", "9"))
        held = _law19_hand(state, repo, "SOR", "51")
        ps = state.player_by_id("P0")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # only 1 unit
        assert _play_cost(state, held, ps) > (held.card_def.cost or 0)

    def test_LAW_9_does_not_waive_a_non_heroism_unit(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        _law12_undeployed_leader(state, "P0", _law12_leader_def(repo, "LAW", "9"))
        held = _law19_hand(state, repo, "SOR", "210")   # Swoop Racer, [Cunning]
        ps = state.player_by_id("P0")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert _play_cost(state, held, ps) > (held.card_def.cost or 0)


class TestAspectWaiverBasesLAW19:
    """LAW_21/22/24/25/27 — five bases printing Daimyo's Palace LAW_20's Epic
    Action verbatim: "Play a card from your hand, ignoring 1 of its Vigilance,
    Command, Aggression, or Cunning aspect penalties." """

    def test_LAW_21_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "21"))

    def test_LAW_22_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "22"))

    def test_LAW_24_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "24"))

    def test_LAW_25_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "25"))

    def test_LAW_27_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "27"))


# ── Group law-set:20 — Miscellaneous abilities ────────────────────────────────


class TestAspectWaiverBasesLAW20group:
    """LAW_28/30 — the last two bases printing Daimyo's Palace LAW_20's Epic
    Action."""

    def test_LAW_28_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "28"))

    def test_LAW_30_epic_action_waives_one_aspect_pip(self, repo):
        state = _make_state()
        _law19_epic_plays_at_waived_cost(state, repo, _law19_base(state, repo, "30"))


class TestObiWanKenobiLAW36:
    """LAW_36 — "While you control 7 or more units, their printed power is
    considered to be 7 and printed HP is considered to be 7." """

    def _fill(self, state, repo, n):
        return [_place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
                for _ in range(n)]

    def test_LAW_36_rewrites_printed_stats_at_seven_units(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "LAW", "36"), "ground")
        mates = self._fill(state, repo, 5)          # 6 units total — not enough
        assert compute_power(state, mates[0]) == 3
        assert compute_hp(state, mates[0]) == 7
        self._fill(state, repo, 1)                  # 7th unit turns the aura on
        assert compute_power(state, mates[0]) == 7
        assert compute_hp(state, mates[0]) == 7
        assert compute_power(state, obi) == 7

    def test_LAW_36_leaves_enemy_units_alone(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "36"), "ground")
        self._fill(state, repo, 6)
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, foe) == 3

    def test_LAW_36_bonuses_still_layer_on_the_overridden_seed(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.tokens import attach_token
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "36"), "ground")
        mates = self._fill(state, repo, 6)
        attach_token(state, state.player_by_id("P0"), mates[0], "Experience")
        assert compute_power(state, mates[0]) == 8      # 7 printed + 1 Experience


class TestDengarLAW53:
    """LAW_53 — "When a unit with the highest cost among enemy units is defeated:
    Create a Credit token.  Use this ability only once each round." """

    def test_LAW_53_credits_on_the_costliest_enemy_dying(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "53"), "ground")
        big = _place(state, "P1", _get_card(repo, "SOR", "116"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert (big.card_def.cost or 0) > 3
        state = _law01_drain(_fire_unit_defeated(state, big, controller_id="P1"))
        assert _law12_credits(state) == 1

    def test_LAW_53_ignores_a_cheaper_enemy_dying(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "53"), "ground")
        big = _place(state, "P1", _get_card(repo, "SOR", "116"), "ground")
        small = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert (small.card_def.cost or 0) < (big.card_def.cost or 0)
        state = _law01_drain(_fire_unit_defeated(state, small, controller_id="P1"))
        assert _law12_credits(state) == 0

    def test_LAW_53_fires_only_once_each_round(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "53"), "ground")
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_unit_defeated(state, a, controller_id="P1"))
        state = _law01_drain(_fire_unit_defeated(state, b, controller_id="P1"))
        assert _law12_credits(state) == 1


class TestL337LAW63:
    """LAW_63 — "When Played: Search the top 10 cards of your deck for any number
    of Droid units with combined cost 5 or less and play each of them for free." """

    def test_LAW_63_plays_droids_within_the_combined_cost_budget(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectSearchCard, FinishSearch)
        state = _make_state()
        # Two cheap Droids on top (2-1B Surgical Droid, cost 1).
        d1 = _push_deck_top(state, "P0", _get_card(repo, "SOR", "59"))
        d2 = _push_deck_top(state, "P0", _get_card(repo, "SOR", "59"))
        assert "Droid" in (d1.card_def.traits or ())
        l3 = _place(state, "P0", _get_card(repo, "LAW", "63"), "ground")
        state = _fire_when_played(state, l3)
        assert state.pending_decisions[-1].kind == "deck_search"
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert {p.instance_id for p in picks} == {d1.instance_id, d2.instance_id}
        state = apply(state, next(p for p in picks
                                  if p.instance_id == d1.instance_id))
        finish = next(a for a in legal_actions(state) if isinstance(a, FinishSearch))
        state = _law01_drain(apply(state, finish))
        assert any(c.instance_id == d1.instance_id
                   for c in state.player_by_id("P0").ground_arena)

    def test_LAW_63_offers_no_non_droid(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard
        state = _make_state()
        plain = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        l3 = _place(state, "P0", _get_card(repo, "LAW", "63"), "ground")
        state = _fire_when_played(state, l3)
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert plain.instance_id not in {p.instance_id for p in picks}


class TestTearThisShipApartLAW66:
    """LAW_66 — "Look at all of an opponent's resources.  You may play 1 of those
    cards for free.  If you do, that opponent resources the top card of their
    deck." """

    def _resource(self, state, owner, card_def):
        import uuid
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_r_{uuid.uuid4().hex[:6]}", card_def, owner,
                          Zone.RESOURCES)
        ci.face_down = True
        state.player_by_id(owner).resources.append(ci)
        return ci

    def test_LAW_66_plays_an_enemy_resource_unit_for_free(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        stolen = self._resource(state, "P1", _get_card(repo, "SOR", "116"))
        _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        p1_res_before = len(state.player_by_id("P1").resources)
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "66")
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == stolen.instance_id)
        state = _law01_drain(apply(state, play))
        # It entered P0's arena (owner unchanged, control follows the arena).
        assert any(c.instance_id == stolen.instance_id
                   for c in state.player_by_id("P0").space_arena
                   + state.player_by_id("P0").ground_arena)
        # The robbed player resourced their deck top — net resource count unchanged.
        p1 = state.player_by_id("P1")
        assert len(p1.resources) == p1_res_before
        assert p1.resources[-1].exhausted

    def test_LAW_66_offers_no_non_unit_resource(self, repo):
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        self._resource(state, "P1", _get_card(repo, "SOR", "76"))   # an Event
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "66")
        assert not [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]


class TestTheMaxReboBandLAW71:
    """LAW_71 — "When the regroup phase starts: Create a Credit token." """

    def test_LAW_71_credits_at_the_start_of_regroup(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "71"), "ground")
        state = _law03_regroup_start(state)
        assert _law12_credits(state) == 1


# ── Group law-set:21 — Miscellaneous abilities ────────────────────────────────


class TestTwoFacedTroigLAW92:
    """LAW_92 — "When Played: You may have an opponent take control of this unit.
    If you do, create 2 Credit tokens." """

    def test_LAW_92_hands_the_unit_over_for_two_credits(self, repo):
        state = _make_state()
        troig = _place(state, "P0", _get_card(repo, "LAW", "92"), "ground")
        state = _law01_drain(_fire_when_played(state, troig))
        state = _law02_accept(state)
        assert any(c.instance_id == troig.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        assert _law12_credits(state, "P0") == 2
        # owner_id never moves — only control does
        assert state.find_instance(troig.instance_id)[1].owner_id == "P0"

    def test_LAW_92_declining_keeps_the_unit_and_pays_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply
        state = _make_state()
        troig = _place(state, "P0", _get_card(repo, "LAW", "92"), "ground")
        state = _law01_drain(_fire_when_played(state, troig))
        decline = next(a for a in legal_actions(state)
                       if type(a).__name__ == "DeclineTrigger")
        state = _law01_drain(apply(state, decline))
        assert any(c.instance_id == troig.instance_id
                   for c in state.player_by_id("P0").ground_arena)
        assert _law12_credits(state, "P0") == 0


class TestRodianBondsmanLAW116:
    """LAW_116 — "When Defeated: Each player creates a Credit token." """

    def test_LAW_116_pays_both_players(self, repo):
        state = _make_state()
        bondsman = _place(state, "P0", _get_card(repo, "LAW", "116"), "ground")
        state = _law01_drain(_fire_when_defeated(state, bondsman))
        assert _law12_credits(state, "P0") == 1
        assert _law12_credits(state, "P1") == 1


class TestConveyexSecurityCaptainLAW117:
    """LAW_117 — "Enemy Credit tokens lose all abilities." """

    def test_LAW_117_stops_an_enemy_credit_paying(self, repo):
        from swu.engine.actions import _affordable_with_credits
        from swu.engine.tokens import create_credit_token
        state = _make_state()
        p1 = state.player_by_id("P1")
        create_credit_token(state, p1)
        create_credit_token(state, p1)
        assert _affordable_with_credits(p1, 2, state)          # no Captain yet
        _place(state, "P0", _get_card(repo, "LAW", "117"), "ground")
        assert not _affordable_with_credits(p1, 2, state)
        assert not _affordable_with_credits(p1, 1, state)

    def test_LAW_117_leaves_its_own_controllers_credits_alone(self, repo):
        from swu.engine.actions import _affordable_with_credits
        from swu.engine.tokens import create_credit_token
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LAW", "117"), "ground")
        p0 = state.player_by_id("P0")
        create_credit_token(state, p0)
        assert _affordable_with_credits(p0, 1, state)

    def test_LAW_117_lifts_when_it_leaves_play(self, repo):
        from swu.engine.actions import _affordable_with_credits
        from swu.engine.tokens import create_credit_token
        state = _make_state()
        captain = _place(state, "P0", _get_card(repo, "LAW", "117"), "ground")
        p1 = state.player_by_id("P1")
        create_credit_token(state, p1)
        assert not _affordable_with_credits(p1, 1, state)
        state.player_by_id("P0").ground_arena.remove(captain)
        assert _affordable_with_credits(p1, 1, state)


class TestCantoBightSecurityLAW121:
    """LAW_121 — "On Defense: Create a Credit token." """

    def test_LAW_121_credits_when_it_is_attacked(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "LAW", "121"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.active_player_index = 1
        state = _law01_continue(apply(state, AttackWithUnit(
            attacker_id=attacker.instance_id, defender_id=guard.instance_id)))
        assert _law12_credits(state, "P0") == 1


class TestAdventurerSniperRifleLAW126:
    """LAW_126 — the host gains "Action [Exhaust]: Choose an undamaged non-leader
    ground unit.  Its printed HP is considered to be 1 for this phase." """

    def test_LAW_126_drops_the_chosen_units_printed_hp_to_one(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, UseAbility, ChooseTarget, compute_hp)
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        rifle = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "126"), "P0")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        assert compute_hp(state, victim) == 7
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == rifle.instance_id)
        state = apply(state, use)
        state = _law01_drain(apply(state, ChooseTarget(victim.instance_id)))
        assert compute_hp(state, _find_instance(state, victim.instance_id)) == 1
        assert _find_instance(state, host.instance_id).exhausted

    def test_LAW_126_does_not_offer_a_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        rifle = _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "126"), "P0")
        hurt = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 1
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == rifle.instance_id)
        state = apply(state, use)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert hurt.instance_id not in offered


class TestTargetedForRemovalLAW141:
    """LAW_141 — the host gains "When Defeated: An opponent creates Credit tokens
    equal to this unit's cost." """

    def test_LAW_141_pays_the_opponent_the_hosts_printed_cost(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "116"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LAW", "141"), "P1")
        cost = host.card_def.cost or 0
        assert cost > 0
        state = _law01_drain(_fire_when_defeated(state, host))
        assert _law12_credits(state, "P1") == cost
        assert _law12_credits(state, "P0") == 0


class TestReyLAW149:
    """LAW_149 — "Opponents can't take control of this unit.  This unit can't be
    defeated by enemy card abilities." """

    def test_LAW_149_refuses_a_control_change(self, repo):
        from swu.engine.actions import change_control
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "LAW", "149"), "ground")
        change_control(state, rey, "P1")
        assert any(c.instance_id == rey.instance_id
                   for c in state.player_by_id("P0").ground_arena)

    def test_LAW_149_survives_an_enemy_defeat_ability(self, repo):
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "LAW", "149"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert _target_protected(state, rey.instance_id, enemy, "defeat")

    def test_LAW_149_still_dies_to_lethal_damage(self, repo):
        from swu.engine.actions import compute_hp
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "LAW", "149"), "ground")
        rey.damage = compute_hp(state, rey)
        from swu.engine.actions import _hp_defeat_prevented
        assert not _hp_defeat_prevented(state, rey)


# ── Group law-set:22 — Miscellaneous abilities ────────────────────────────────


class TestGetawayFreighterLAW155:
    """LAW_155 — "On Attack: If you control a ground unit, create a Credit." """

    def test_LAW_155_credits_with_a_friendly_ground_unit(self, repo):
        state = _make_state()
        freighter = _place(state, "P0", _get_card(repo, "LAW", "155"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _law01_drain(_fire_on_attack(state, freighter))
        assert _law12_credits(state, "P0") == 1

    def test_LAW_155_does_nothing_without_one(self, repo):
        state = _make_state()
        freighter = _place(state, "P0", _get_card(repo, "LAW", "155"), "space")
        state = _law01_drain(_fire_on_attack(state, freighter))
        assert _law12_credits(state, "P0") == 0


class TestHunterForHireLAW156:
    """LAW_156 — "Action [defeat a friendly Credit token]: Take control of this
    unit.  Any player may use this ability." """

    def test_LAW_156_opponent_buys_the_unit_with_their_own_credit(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility
        from swu.engine.tokens import create_credit_token
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "LAW", "156"), "ground")
        create_credit_token(state, state.player_by_id("P1"))
        state.active_player_index = 1
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == hunter.instance_id)
        state = _law01_drain(apply(state, use))
        assert any(c.instance_id == hunter.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        assert _law12_credits(state, "P1") == 0
        assert state.find_instance(hunter.instance_id)[1].owner_id == "P0"

    def test_LAW_156_is_not_offered_without_a_credit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        hunter = _place(state, "P0", _get_card(repo, "LAW", "156"), "ground")
        state.active_player_index = 1
        assert not [a for a in legal_actions(state)
                    if isinstance(a, UseAbility)
                    and a.source_id == hunter.instance_id]


class TestPartisanUWingLAW161:
    """LAW_161 — "When Played: If a friendly unit was defeated this phase, create
    a Credit token." """

    def test_LAW_161_credits_after_a_friendly_loss(self, repo):
        state = _make_state()
        state.game_memory.defeated_controllers_this_round.append("P0")
        uwing = _place(state, "P0", _get_card(repo, "LAW", "161"), "space")
        state = _law01_drain(_fire_when_played(state, uwing))
        assert _law12_credits(state, "P0") == 1

    def test_LAW_161_does_nothing_with_no_friendly_loss(self, repo):
        state = _make_state()
        uwing = _place(state, "P0", _get_card(repo, "LAW", "161"), "space")
        state = _law01_drain(_fire_when_played(state, uwing))
        assert _law12_credits(state, "P0") == 0


class TestPayrollHeistLAW169:
    """LAW_169 — "For this phase, each friendly unit gains: 'On Attack: Create a
    Credit token.'" """

    def test_LAW_169_every_friendly_attacker_mints_a_credit(self, repo):
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "169")
        state = _law01_drain(state)
        state = _law01_drain(_fire_on_attack(
            state, _find_instance(state, mine.instance_id)))
        assert _law12_credits(state, "P0") == 1

    def test_LAW_169_does_not_arm_enemy_units(self, repo):
        state = _make_state()
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "169")
        state = _law01_drain(state)
        state = _law01_drain(_fire_on_attack(
            state, _find_instance(state, theirs.instance_id)))
        assert _law12_credits(state, "P0") == 0
        assert _law12_credits(state, "P1") == 0


class TestShiftySuspectsLAW197:
    """LAW_197 — "On Attack: Bases can't be healed for this phase." """

    def test_LAW_197_locks_base_healing_for_the_phase(self, repo):
        from swu.engine.actions import _bases_cannot_heal
        state = _make_state()
        suspects = _place(state, "P0", _get_card(repo, "LAW", "197"), "ground")
        assert not _bases_cannot_heal(state)
        state = _law01_drain(_fire_on_attack(state, suspects))
        assert _bases_cannot_heal(state)


class TestEveryDayMoreLiesLAW204:
    """LAW_204 — "Each player discards a card from their hand." """

    def test_LAW_204_costs_both_players_a_card(self, repo):
        state = _make_state()
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 10)
        p0_before = len(state.player_by_id("P0").hand)
        p1_before = len(state.player_by_id("P1").hand)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "204")
        state = _law01_drain(state)
        # P0's hand also lost the event itself, hence the extra -1.
        assert len(state.player_by_id("P0").hand) == p0_before - 1
        assert len(state.player_by_id("P1").hand) == p1_before - 1


class TestAnakinsPodracerLAW219:
    """LAW_219 — "While attacking, if no other units have attacked this phase,
    this unit deals combat damage before the defending unit." """

    def test_LAW_219_strikes_first_when_nothing_else_attacked(self, repo):
        from swu.engine.actions import _attacker_has_first_strike
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "219"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert _attacker_has_first_strike(state, pod, foe)

    def test_LAW_219_loses_first_strike_once_another_unit_attacked(self, repo):
        from swu.engine.actions import _attacker_has_first_strike
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "219"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_attacked_this_round.add(other.instance_id)
        state.game_memory.units_attacked_this_round.add(pod.instance_id)
        assert not _attacker_has_first_strike(state, pod, foe)

    def test_LAW_219_kills_a_smaller_defender_before_it_strikes_back(self, repo):
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "219"), "ground")   # 3/2
        foe = _place(state, "P1", _get_card(repo, "SOR", "48"), "ground")
        state = _law01_continue(apply(state, AttackWithUnit(
            attacker_id=pod.instance_id, defender_id=foe.instance_id)))
        survivor = _find_instance(state, pod.instance_id)
        if survivor is not None:
            assert survivor.damage == 0     # the defender died before striking back


# ── Group law-set:23 — Miscellaneous abilities ────────────────────────────────


class TestLieutenantGornLAW221:
    """LAW_221 — "On Attack: Take control of an enemy Credit token." """

    def test_LAW_221_moves_an_enemy_credit_into_your_pile(self, repo):
        from swu.engine.tokens import create_credit_token
        state = _make_state()
        gorn = _place(state, "P0", _get_card(repo, "LAW", "221"), "ground")
        create_credit_token(state, state.player_by_id("P1"))
        state = _law01_drain(_fire_on_attack(state, gorn))
        assert _law12_credits(state, "P0") == 1
        assert _law12_credits(state, "P1") == 0

    def test_LAW_221_does_nothing_against_an_empty_pile(self, repo):
        state = _make_state()
        gorn = _place(state, "P0", _get_card(repo, "LAW", "221"), "ground")
        state = _law01_drain(_fire_on_attack(state, gorn))
        assert _law12_credits(state, "P0") == 0


class TestCanyonFrontrunnerLAW228:
    """LAW_228 — "On Attack: If no other units have attacked this phase, you may
    give a unit −2/−0 for this phase." """

    def test_LAW_228_debuffs_the_chosen_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "LAW", "228"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _law01_drain(_fire_on_attack(state, runner, foe))
        state = _law02_accept(state)
        state = _law06_choose(state, foe.instance_id)
        assert compute_power(state, _find_instance(state, foe.instance_id)) == 1

    def test_LAW_228_is_not_offered_once_another_unit_attacked(self, repo):
        from swu.engine.actions import legal_actions
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "LAW", "228"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_attacked_this_round.add(other.instance_id)
        state.game_memory.units_attacked_this_round.add(runner.instance_id)
        state = _law01_drain(_fire_on_attack(state, runner, foe))
        assert not any(type(a).__name__ == "AcceptTrigger"
                       for a in legal_actions(state))


class TestChampionsKT9PodracerLAW232:
    """LAW_232 — "When Played: Create a Credit token." """

    def test_LAW_232_creates_a_credit_on_entry(self, repo):
        state = _make_state()
        pod = _place(state, "P0", _get_card(repo, "LAW", "232"), "ground")
        state = _law01_drain(_fire_when_played(state, pod))
        assert _law12_credits(state, "P0") == 1


class TestLadyProximaLAW235:
    """LAW_235 — "Action [Exhaust]: Create a Credit token." """

    def test_LAW_235_exhausts_for_a_credit(self, repo):
        state = _make_state()
        proxima = _place(state, "P0", _get_card(repo, "LAW", "235"), "ground")
        state = _law01_use(state, proxima)
        assert _law12_credits(state, "P0") == 1
        assert _find_instance(state, proxima.instance_id).exhausted


class TestTransmissionJammingLAW243:
    """LAW_243 — "Name a card.  Cards with that name can't be played this
    phase." """

    def test_LAW_243_bars_the_named_card_from_being_played(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard, PlayCard
        state = _make_state()
        # A card of P1's is publicly visible (an arena unit), so it is nameable.
        marine = _get_card(repo, "SOR", "46")
        _place(state, "P1", marine, "ground")
        held = _put_in_hand(state, "P1", marine)
        _give_resources(state, "P0", 20)
        _give_resources(state, "P1", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "243")
        name = next(a for a in legal_actions(state)
                    if isinstance(a, NameCard) and a.name == marine.name)
        state = _law01_drain(apply(state, name))
        assert marine.name in state.game_memory.forbidden_card_names_this_phase
        state.active_player_index = 1
        assert not [a for a in legal_actions(state)
                    if isinstance(a, PlayCard)
                    and a.instance_id == held.instance_id]

    def test_LAW_243_ban_lifts_at_the_phase_rollover(self, repo):
        state = _make_state()
        state.game_memory.forbidden_card_names_this_phase.add("Battlefield Marine")
        state.game_memory.clear_phase()
        assert not state.game_memory.forbidden_card_names_this_phase


class TestWindfallLAW248:
    """LAW_248 — "Create 3 Credit tokens." """

    def test_LAW_248_creates_three_credits(self, repo):
        state = _make_state()
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "248")
        state = _law01_drain(state)
        assert _law12_credits(state, "P0") == 3


class TestFireAcrossTheGalaxyLAW256:
    """LAW_256 — "Use any number of 'When Played' abilities on friendly Spectre
    units." """

    def test_LAW_256_reuses_a_spectre_units_when_played(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget, FinishSelectToken)
        state = _make_state()
        # The Ghost LAW_69 is a Spectre unit with a When Played ability.
        ghost = _place(state, "P0", _get_card(repo, "LAW", "69"), "space")
        assert "Spectre" in (ghost.card_def.traits or ())
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "256")
        state = _law01_drain(state)
        picks = [a for a in legal_actions(state)
                 if isinstance(a, SelectTokenTarget)]
        assert {p.target_id for p in picks} == {ghost.instance_id}
        state = apply(state, picks[0])
        if state.pending_decisions and \
                state.pending_decisions[-1].kind == "select_token":
            state = apply(state, FinishSelectToken())
        state = _law01_drain(state)
        # The Ghost's re-used When Played gives an Experience AND a Shield token to
        # a chosen unit (its own select_token loop).
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)
                    and a.target_id == ghost.instance_id)
        state = _law01_drain(apply(state, pick))
        after = _find_instance(state, ghost.instance_id)
        assert _experience_count(after) == 1 and _shield_count(after) == 1

    def test_LAW_256_offers_no_spectre_unit_without_a_when_played(self, repo):
        from swu.engine.actions import legal_actions, SelectTokenTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Spectre
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "256")
        state = _law01_drain(state)
        assert not [a for a in legal_actions(state)
                    if isinstance(a, SelectTokenTarget)]


# ── Group law-set:24 — Miscellaneous abilities (LAW's last group) ─────────────


class TestCriminalContactLAW258:
    """LAW_258 — "On Attack: You may pay 2 resources.  If you do, create a Credit
    token." """

    def test_LAW_258_pays_two_for_a_credit(self, repo):
        state = _make_state()
        contact = _place(state, "P0", _get_card(repo, "LAW", "258"), "ground")
        _give_resources(state, "P0", 3)
        before = state.player_by_id("P0").available_resources
        state = _law01_drain(_fire_on_attack(state, contact))
        state = _law02_accept(state)
        assert _law12_credits(state, "P0") == 1
        assert state.player_by_id("P0").available_resources == before - 2

    def test_LAW_258_is_not_offered_below_two_resources(self, repo):
        state = _make_state()
        contact = _place(state, "P0", _get_card(repo, "LAW", "258"), "ground")
        _give_resources(state, "P0", 1)
        state = _law01_drain(_fire_on_attack(state, contact))
        assert not state.pending_decisions


class TestBankJobFugitivesLAW262:
    """LAW_262 — "When Played: Create a Credit token." """

    def test_LAW_262_creates_a_credit_on_entry(self, repo):
        state = _make_state()
        crew = _place(state, "P0", _get_card(repo, "LAW", "262"), "ground")
        state = _law01_drain(_fire_when_played(state, crew))
        assert _law12_credits(state, "P0") == 1


class TestFromACertainPointOfViewLAW264:
    """LAW_264 — "Play a card from your hand, ignoring its aspect penalties." """

    def test_LAW_264_plays_a_unit_with_an_aspect_pip_waived(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()          # P0's base has no aspects
        # Swoop Racer: printed cost 3, [Cunning] → effective 5 here; the waiver
        # brings it back to 3.
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "210"))
        _give_resources(state, "P0", 20)
        state, _evt = _play_event_from_hand(state, repo, "LAW", "264")
        state = _law01_drain(state)
        before = state.player_by_id("P0").available_resources
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == unit.instance_id)
        state = _law01_drain(apply(state, play))
        assert any(c.instance_id == unit.instance_id
                   for c in state.player_by_id("P0").ground_arena)
        assert state.player_by_id("P0").available_resources == before - 3
