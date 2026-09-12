"""LOF (Legends of the Force) card ability tests — deck ``qui-gon-jinn``.

The first LOF deck.  Group ``qui-gon-jinn:01`` — Direct damage & removal:
  * LOF_198 Stinger Mantis — When Played: you may deal 2 damage to an exhausted
    unit (an optional WhenPlayed DealDamage with the ``exhausted`` predicate).
  * SOR_219 Sneak Attack — Play a unit from hand for 3 less, ready, then defeat
    it at the start of the next regroup (the play-from-hand subsystem plus the
    new ``defeat_at_regroup`` flag).

Reuses the DB-backed game-state helpers from the SOR card tests.  Method names
embed the card number so the encoding verifier's ``-k`` gate selects them.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _fire_when_defeated,
    _fire_on_attack,
    _fire_upgrade_played, _find_instance, _give_resources, _play_event_from_hand,
    _experience_count, _shield_count, _place_leader, _push_deck_top,
    _accept_optional_and_run,
)
from tests.test_shd_cards import _put_in_hand, _attach_upgrade_directly


def _put_in_discard(state, owner, card_def):
    """Put a card into a player's discard pile.  Returns the CardInstance."""
    import uuid
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(f"{owner}_disc_{uuid.uuid4().hex[:6]}", card_def, owner, Zone.DISCARD)
    state.player_by_id(owner).discard.append(ci)
    return ci


# ── LOF_198 Stinger Mantis ────────────────────────────────────────────────────

class TestStingerMantis:
    """When Played: You may deal 2 damage to an exhausted unit."""

    def test_lof_198_deals_2_to_exhausted_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.exhausted = True
        state = _fire_when_played(state, mantis)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_lof_198_only_exhausted_units_targetable(self, repo):
        """A ready unit is not a legal target; an exhausted one is."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        ready_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        exhausted_enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        exhausted_enemy.exhausted = True
        state = _fire_when_played(state, mantis)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert exhausted_enemy.instance_id in offered
        assert ready_enemy.instance_id not in offered

    def test_lof_198_auto_declines_with_no_exhausted_unit(self, repo):
        """With no exhausted unit on the board the optional trigger is never
        offered (the resolver auto-declines a 'you may' with no legal target)."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # ready
        state = _fire_when_played(state, mantis)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


# ── SOR_219 Sneak Attack ──────────────────────────────────────────────────────

def _play_sneak_attack(state, repo, owner="P0"):
    """Put Sneak Attack in owner's hand, give resources, and play it (PlayCard).
    Returns the state with a pending play_from_hand decision."""
    from swu.engine.state import CardInstance, Zone
    from swu.engine.actions import apply, PlayCard
    ci = CardInstance(f"{owner}_sneak", _get_card(repo, "SOR", "219"), owner, Zone.HAND)
    state.player_by_id(owner).hand.append(ci)
    _give_resources(state, owner, 12)
    return apply(state, PlayCard(ci.instance_id))


class TestSneakAttack:
    """Play a unit from hand.  It costs 3 less and enters play ready.  At the
    start of the regroup phase, defeat it."""

    def test_sor_219_pushes_discounted_ready_play(self, repo):
        """Playing Sneak Attack pushes a play_from_hand decision carrying the
        3-resource discount, enters-ready, and the defeat-at-regroup flag."""
        from swu.engine.actions import legal_actions, PlayFromHand
        state = _make_state()
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state = _play_sneak_attack(state, repo)
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        assert top.context["cost_reduction"] == 3
        assert top.context["enters_ready"] is True
        assert top.context["defeat_at_regroup"] is True
        # The hand unit is an eligible play.
        assert any(isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id
                   for a in legal_actions(state))

    def test_sor_219_unit_enters_ready_and_flagged(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayFromHand
        state = _make_state()
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state = _play_sneak_attack(state, repo)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = apply(state, play)
        in_play = _find_instance(state, unit.instance_id)
        assert in_play is not None, "unit entered play"
        assert in_play.exhausted is False, "enters play ready"
        assert in_play.defeat_at_regroup is True

    def test_sor_219_unit_defeated_at_regroup(self, repo):
        """End to end: play the unit, then pass both players into regroup — the
        Sneak-Attacked unit is defeated, a normal unit survives."""
        from swu.engine.actions import legal_actions, apply, PlayFromHand, Pass
        state = _make_state()
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        bystander = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _play_sneak_attack(state, repo)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand) and a.instance_id == unit.instance_id)
        state = apply(state, play)
        # Both players pass -> ACTION ends -> _enter_regroup sweeps the flag.
        for _ in range(2):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, Pass)))
        assert _find_instance(state, unit.instance_id) is None
        assert unit.instance_id in {c.instance_id
                                    for c in state.player_by_id("P0").discard}
        assert _find_instance(state, bystander.instance_id) is not None


# ── LOF_104 Luminous Beings ───────────────────────────────────────────────────

class TestLuminousBeings:
    """Put up to 3 Force units from your discard pile on the bottom of your deck in
    a random order.  Give that many units +4/+4 for this phase."""

    def test_lof_104_only_force_units_recurrable(self, repo):
        from swu.engine.actions import legal_actions, SelectRecurUnit
        state = _make_state()
        force_a = _put_in_discard(state, "P0", _get_card(repo, "SOR", "45"))   # Yoda (Force)
        force_b = _put_in_discard(state, "P0", _get_card(repo, "SOR", "47"))   # Kanan (Force)
        non_force = _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))  # not Force
        state, _ = _play_event_from_hand(state, repo, "LOF", "104")
        top = state.pending_decisions[-1]
        assert top.kind == "recur_and_buff" and top.context["stage"] == "recur"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectRecurUnit)}
        assert force_a.instance_id in offered
        assert force_b.instance_id in offered
        assert non_force.instance_id not in offered

    def test_lof_104_no_force_units_is_noop(self, repo):
        """With no Force unit in the discard pile, the event does nothing."""
        state = _make_state()
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))  # non-Force
        state, _ = _play_event_from_hand(state, repo, "LOF", "104")
        assert not state.pending_decisions

    def test_lof_104_recurs_to_deck_bottom_and_buffs(self, repo):
        """Recur 2 Force units (→ deck bottom, out of discard), then buff 2 units
        +4/+4 for this phase."""
        from swu.engine.actions import (
            legal_actions, apply, compute_power,
            SelectRecurUnit, SelectBuffTarget,
        )
        state = _make_state()
        force_a = _put_in_discard(state, "P0", _get_card(repo, "SOR", "45"))
        force_b = _put_in_discard(state, "P0", _get_card(repo, "SOR", "47"))
        u1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        u2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        base_power = compute_power(state, u1)
        state, _ = _play_event_from_hand(state, repo, "LOF", "104")

        # Recur both Force units (cap 3, but only 2 candidates → auto-advance).
        for fid in (force_a.instance_id, force_b.instance_id):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, SelectRecurUnit) and a.instance_id == fid)
            state = apply(state, act)

        # Both Force units left the discard pile for the bottom of the deck.
        p0 = state.player_by_id("P0")
        disc_ids = {c.instance_id for c in p0.discard}
        deck_ids = {c.instance_id for c in p0.deck}
        assert force_a.instance_id not in disc_ids and force_a.instance_id in deck_ids
        assert force_b.instance_id not in disc_ids and force_b.instance_id in deck_ids

        # Now the buff stage: K == 2, so buff two units.
        top = state.pending_decisions[-1]
        assert top.kind == "recur_and_buff" and top.context["stage"] == "buff"
        for uid in (u1.instance_id, u2.instance_id):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, SelectBuffTarget) and a.instance_id == uid)
            state = apply(state, act)

        assert not state.pending_decisions  # auto-popped at K == 2
        assert compute_power(state, _find_instance(state, u1.instance_id)) == base_power + 4
        assert compute_power(state, _find_instance(state, u2.instance_id)) == base_power + 4

    def test_lof_104_buff_count_capped_at_recurred(self, repo):
        """Recurring only 1 unit lets you buff only 1 (the decision auto-pops)."""
        from swu.engine.actions import (
            legal_actions, apply, compute_power,
            FinishRecur, SelectRecurUnit, SelectBuffTarget,
        )
        state = _make_state()
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "45"))
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "47"))
        u1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        u2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        base_power = compute_power(state, u1)
        state, _ = _play_event_from_hand(state, repo, "LOF", "104")

        # Recur exactly one, then finish the recur stage early.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectRecurUnit)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishRecur)))

        top = state.pending_decisions[-1]
        assert top.context["stage"] == "buff" and top.context["buff_remaining"] == 1
        # Buff one unit → the decision auto-pops (only 1 allowed).
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectBuffTarget)
                                  and a.instance_id == u1.instance_id))
        assert not state.pending_decisions
        assert compute_power(state, _find_instance(state, u1.instance_id)) == base_power + 4
        # The other unit was never buffed (capped at the 1 recurred).
        assert compute_power(state, _find_instance(state, u2.instance_id)) == base_power


# ── LOF_194 J-Type Nubian Starship ────────────────────────────────────────────

class TestJTypeNubianStarship:
    """When Played: Draw a card.  When Defeated: Discard a card from your hand."""

    def test_lof_194_when_played_draws(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        # Seed the deck so there is a card to draw.
        deck_card = CardInstance("P0_deck1", _get_card(repo, "SOR", "46"), "P0", Zone.DECK)
        state.player_by_id("P0").deck.append(deck_card)
        starship = _place(state, "P0", _get_card(repo, "LOF", "194"), "space")
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, starship)
        assert len(state.player_by_id("P0").hand) == before + 1
        assert deck_card.instance_id in {c.instance_id
                                         for c in state.player_by_id("P0").hand}

    def test_lof_194_when_defeated_discards_a_card(self, repo):
        state = _make_state()
        starship = _place(state, "P0", _get_card(repo, "LOF", "194"), "space")
        held = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_defeated(state, starship)
        assert len(state.player_by_id("P0").hand) == before - 1
        assert held.instance_id in {c.instance_id
                                    for c in state.player_by_id("P0").discard}


# ── qui-gon-jinn:03 — Combat tricks, buffs & tempo ────────────────────────────
#
# SHD_96 (Maz Kanata) and JTL_201 (Ahsoka Tano) belong to the SHD / JTL sets but
# are part of the qui-gon-jinn deck; their tests live here with the rest of the
# group so the verifier's card-number ``-k`` gate finds them together.

def _fire_card_played(state, ci):
    """Fire a CardPlayed event for ci as if it was just played (the
    WhenYouPlayCard observer hook — Obi-Wan LOF_96 / Maz Kanata SHD_96)."""
    from swu.engine.events import CardPlayed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = CardPlayed(
        player_id=ci.owner_id, instance_id=ci.instance_id,
        card_name=ci.card_def.display_name, cost_paid=0,
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


class TestObiWanKenobi:
    """LOF_96 — When you play a Force unit (including this one): gains Sentinel for
    this phase."""

    def test_lof_96_no_innate_sentinel(self, repo):
        """The data mis-tags Obi-Wan with a printed Sentinel; the sanitiser strips
        it (the triggered self-grant owns it), so he is NOT a Sentinel by default —
        only after a Force unit is played."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")
        assert not has_keyword(state, obi, Keyword.SENTINEL)

    def test_lof_96_gains_sentinel_when_force_unit_played(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _fire_card_played(state, force_unit)
        assert has_keyword(state, _find_instance(state, obi.instance_id), Keyword.SENTINEL)

    def test_lof_96_including_this_one(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")
        state = _fire_card_played(state, obi)  # he is the played Force unit
        assert has_keyword(state, _find_instance(state, obi.instance_id), Keyword.SENTINEL)

    def test_lof_96_non_force_unit_no_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")
        non_force = _place(state, "P0", _get_card(repo, "SHD", "96"), "ground")  # Underworld
        state = _fire_card_played(state, non_force)
        assert not has_keyword(state, _find_instance(state, obi.instance_id), Keyword.SENTINEL)


class TestMazKanataSHD96:
    """SHD_96 — When you play another unit: Give an Experience token to this unit."""

    def test_shd_96_gains_experience_when_another_unit_played(self, repo):
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "SHD", "96"), "ground")
        other = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _fire_card_played(state, other)
        assert _experience_count(_find_instance(state, maz.instance_id)) == 1

    def test_shd_96_not_triggered_by_self(self, repo):
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "SHD", "96"), "ground")
        state = _fire_card_played(state, maz)
        assert _experience_count(_find_instance(state, maz.instance_id)) == 0


class TestPaladinTrainingCorvette:
    """LOF_99 — When Played: give an Experience token to each of up to 3 Force
    units."""

    def test_lof_99_tokens_up_to_3_force_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget, FinishSelectToken)
        state = _make_state()
        corvette = _place(state, "P0", _get_card(repo, "LOF", "99"), "space")
        f1 = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")  # Force
        f2 = _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")   # Force
        f3 = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")  # Force (3rd)
        non_force = _place(state, "P0", _get_card(repo, "SHD", "96"), "ground")

        state = _fire_when_played(state, corvette)
        assert state.pending_decisions[-1].kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert {f1.instance_id, f2.instance_id, f3.instance_id} <= offered
        assert non_force.instance_id not in offered

        state = apply(state, SelectTokenTarget(f1.instance_id))
        state = apply(state, SelectTokenTarget(f2.instance_id))
        # Stop early (the "up to") — f3 gets nothing.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishSelectToken)))
        assert _experience_count(state.find_instance(f1.instance_id)[1]) == 1
        assert _experience_count(state.find_instance(f2.instance_id)[1]) == 1
        assert _experience_count(state.find_instance(f3.instance_id)[1]) == 0


class TestMazKanataLOF111:
    """LOF_111 — When Played: you may attack with a Force unit, +2/+0."""

    def test_lof_111_force_unit_attacks_with_bonus(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "LOF", "111"), "ground")  # Underworld
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")  # Force 0/3
        base_before = state.players[1].base_instance.damage

        state = _fire_when_played(state, maz)
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert force_unit.instance_id in attackers
        assert maz.instance_id not in attackers

        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == force_unit.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == 2  # 0 power + 2

    def test_lof_111_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineGrantedAttack
        state = _make_state()
        maz = _place(state, "P0", _get_card(repo, "LOF", "111"), "ground")
        _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _fire_when_played(state, maz)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineGrantedAttack))
        state = apply(state, decline)
        assert not state.pending_decisions


class TestQuiGonJinnsLightsaber:
    """LOF_201 — When Played: if attached unit is Qui-Gon Jinn, you may exhaust any
    number of units with combined cost 6 or less."""

    def test_lof_201_exhausts_units_within_budget(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectUnitToExhaustCombined)
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")  # Qui-Gon Jinn
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "201"), "P0")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # cost 2
        e2 = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # cost 2

        state = _fire_upgrade_played(state, saber, host)
        assert state.pending_decisions[-1].kind == "exhaust_combined_cost"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectUnitToExhaustCombined)}
        assert {e1.instance_id, e2.instance_id} <= offered

        state = apply(state, SelectUnitToExhaustCombined(e1.instance_id))
        offered2 = {a.target_id for a in legal_actions(state)
                    if isinstance(a, SelectUnitToExhaustCombined)}
        assert e2.instance_id in offered2  # 4 budget left, e2 (cost 2) still fits
        state = apply(state, SelectUnitToExhaustCombined(e2.instance_id))
        assert state.find_instance(e1.instance_id)[1].exhausted
        assert state.find_instance(e2.instance_id)[1].exhausted

    def test_lof_201_budget_caps_combined_cost(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectUnitToExhaustCombined
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "201"), "P0")
        big = _place(state, "P1", _get_card(repo, "LOF", "99"), "space")     # cost 5
        cheap = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 3
        state = _fire_upgrade_played(state, saber, host)
        state = apply(state, SelectUnitToExhaustCombined(big.instance_id))   # spend 5
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectUnitToExhaustCombined)}
        assert cheap.instance_id not in offered  # only 1 budget left

    def test_lof_201_wrong_host_no_decision(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Qui-Gon
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "201"), "P0")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, saber, host)
        assert not state.pending_decisions

    def test_lof_201_may_take_zero(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishExhaustCombined
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "201"), "P0")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, saber, host)
        fin = next(a for a in legal_actions(state)
                   if isinstance(a, FinishExhaustCombined))
        state = apply(state, fin)
        assert not state.pending_decisions


class TestAhsokaTanoJTL201:
    """JTL_201 — When Played: an opponent discards a card; if it's a unit, you may
    exhaust a unit."""

    def test_jtl_201_unit_discarded_allows_exhaust(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectUnitToExhaustCombined
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "JTL", "201"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))  # a Unit on top
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        opp_discard_before = len(state.player_by_id("P1").discard)

        state = _fire_when_played(state, ahsoka)
        assert len(state.player_by_id("P1").discard) == opp_discard_before + 1
        assert state.pending_decisions[-1].kind == "exhaust_combined_cost"
        sel = next(a for a in legal_actions(state)
                   if isinstance(a, SelectUnitToExhaustCombined)
                   and a.target_id == enemy.instance_id)
        state = apply(state, sel)
        assert state.find_instance(enemy.instance_id)[1].exhausted

    def test_jtl_201_only_one_unit_may_be_exhausted(self, repo):
        from swu.engine.actions import apply, SelectUnitToExhaustCombined
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "JTL", "201"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, ahsoka)
        state = apply(state, SelectUnitToExhaustCombined(e1.instance_id))
        assert not state.pending_decisions  # max_units=1 → auto-resolved
        assert not state.find_instance(e2.instance_id)[1].exhausted

    def test_jtl_201_non_unit_discarded_no_exhaust(self, repo):
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "JTL", "201"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "219"))  # Sneak Attack (Event)
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        opp_discard_before = len(state.player_by_id("P1").discard)
        state = _fire_when_played(state, ahsoka)
        assert len(state.player_by_id("P1").discard) == opp_discard_before + 1
        assert not state.pending_decisions


# ── LOF_202 Mind Trick — the ability-suppression read-layer ───────────────────

class TestMindTrick:
    """LOF_202 — Event: "Exhaust any number of units with a combined power of 4 or
    less.  If you control a Force unit, those units lose all abilities and can't
    gain abilities for this phase."  Exercises the exhaust-combined-POWER variant
    of the exhaust_combined_cost seam and the new CardInstance.abilities_suppressed
    read-layer."""

    def test_lof_202_eligibility_capped_by_combined_power(self, repo):
        # Two power-3 enemies: after exhausting one (weight 3), only 1 budget is
        # left, so the other power-3 unit is no longer eligible.
        from swu.engine.actions import (
            legal_actions, apply, SelectUnitToExhaustCombined)
        state = _make_state()
        e1 = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # power 3
        e2 = _place(state, "P1", _get_card(repo, "SOR", "95"), "ground")  # power 3
        state, _ = _play_event_from_hand(state, repo, "LOF", "202")
        assert state.pending_decisions[-1].kind == "exhaust_combined_cost"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectUnitToExhaustCombined)}
        assert {e1.instance_id, e2.instance_id} <= offered
        state = apply(state, SelectUnitToExhaustCombined(e1.instance_id))
        offered2 = {a.target_id for a in legal_actions(state)
                    if isinstance(a, SelectUnitToExhaustCombined)}
        assert e2.instance_id not in offered2  # only 1 budget left, power-3 too big

    def test_lof_202_force_unit_suppresses_chosen_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectUnitToExhaustCombined, FinishExhaustCombined)
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")  # Qui-Gon (Force)
        guard = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")  # Sentinel, power 3
        assert has_keyword(state, guard, Keyword.SENTINEL)
        state, _ = _play_event_from_hand(state, repo, "LOF", "202")
        state = apply(state, SelectUnitToExhaustCombined(guard.instance_id))
        if state.pending_decisions:  # 1 budget left, may still be a decision
            fin = next(a for a in legal_actions(state)
                       if isinstance(a, FinishExhaustCombined))
            state = apply(state, fin)
        g = state.find_instance(guard.instance_id)[1]
        assert g.exhausted
        assert g.abilities_suppressed
        assert not has_keyword(state, g, Keyword.SENTINEL)  # lost all abilities

    def test_lof_202_no_force_unit_no_suppression(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectUnitToExhaustCombined, FinishExhaustCombined)
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        # No Force unit controlled by P0.
        guard = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")  # Sentinel, power 3
        state, _ = _play_event_from_hand(state, repo, "LOF", "202")
        state = apply(state, SelectUnitToExhaustCombined(guard.instance_id))
        if state.pending_decisions:
            fin = next(a for a in legal_actions(state)
                       if isinstance(a, FinishExhaustCombined))
            state = apply(state, fin)
        g = state.find_instance(guard.instance_id)[1]
        assert g.exhausted            # still exhausted (that half is unconditional)
        assert not g.abilities_suppressed
        assert has_keyword(state, g, Keyword.SENTINEL)  # abilities intact

    def test_lof_202_suppression_lifts_at_round_rollover(self, repo):
        from swu.engine.actions import _regroup_rollover
        state = _make_state()
        u = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        u.abilities_suppressed = True
        _regroup_rollover(state)
        assert not state.find_instance(u.instance_id)[1].abilities_suppressed

    def test_lof_202_suppressed_unit_loses_constant_buff(self, repo):
        # Scimitar LOF_233: 3/4, "While damaged, +3/+0" (self ConstantAbility).
        # Damaged → power 6; suppressed → the constant source is skipped → power 3.
        from swu.engine.actions import compute_power
        state = _make_state()
        scim = _place(state, "P0", _get_card(repo, "LOF", "233"), "ground")
        scim.damage = 1
        assert compute_power(state, scim) == 6
        scim.abilities_suppressed = True
        assert compute_power(state, scim) == 3

    def test_lof_202_suppressed_unit_activated_ability_not_offered(self, repo):
        # Grogu SHD_196: "Action [Exhaust]: Exhaust an enemy unit" (ActivatedAbility).
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        grogu = _place(state, "P0", _get_card(repo, "SHD", "196"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # a target exists
        offered = {a.source_id for a in legal_actions(state) if isinstance(a, UseAbility)}
        assert grogu.instance_id in offered
        grogu.abilities_suppressed = True
        offered2 = {a.source_id for a in legal_actions(state) if isinstance(a, UseAbility)}
        assert grogu.instance_id not in offered2

    def test_lof_202_reprint_lofp_17_alias(self, repo):
        from swu.abilities.registry import get_abilities
        assert get_abilities("LOFP", "17") == get_abilities("LOF", "202")
        assert get_abilities("LOF", "202")  # non-empty

    def test_lof_202_suppression_survives_serialisation(self, repo):
        from swu.engine.state import GameState
        state = _make_state()
        u = _place(state, "P1", _get_card(repo, "SOR", "229"), "ground")
        u.abilities_suppressed = True
        restored = GameState.from_json(state.to_json())
        assert restored.find_instance(u.instance_id)[1].abilities_suppressed

    def test_jtl_201_empty_opponent_hand_no_op(self, repo):
        state = _make_state()
        ahsoka = _place(state, "P0", _get_card(repo, "JTL", "201"), "ground")
        state.player_by_id("P1").hand.clear()
        state = _fire_when_played(state, ahsoka)
        assert not state.pending_decisions


# ── qui-gon-jinn:04 — Combat tricks, buffs & tempo ────────────────────────────

class TestCuriousFlock:
    """LOF_255 — When Played: Pay up to 6 resources; give an Experience token to
    this unit for each resource paid this way."""

    def test_lof_255_pay_some_then_finish(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PayResourceForToken, FinishPayResources)
        state = _make_state()
        flock = _place(state, "P0", _get_card(repo, "LOF", "255"), "ground")
        _give_resources(state, "P0", 3)

        state = _fire_when_played(state, flock)
        assert state.pending_decisions[-1].kind == "pay_resources_for_tokens"

        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PayResourceForToken)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PayResourceForToken)))
        # Stop early (the "up to") — third resource stays ready.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishPayResources)))
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, flock.instance_id)) == 2
        assert state.player_by_id("P0").available_resources == 1

    def test_lof_255_auto_resolves_when_resources_exhausted(self, repo):
        from swu.engine.actions import legal_actions, apply, PayResourceForToken
        state = _make_state()
        flock = _place(state, "P0", _get_card(repo, "LOF", "255"), "ground")
        _give_resources(state, "P0", 2)

        state = _fire_when_played(state, flock)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PayResourceForToken)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PayResourceForToken)))
        # No ready resource left → the decision auto-resolves.
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, flock.instance_id)) == 2
        assert state.player_by_id("P0").available_resources == 0

    def test_lof_255_caps_at_six(self, repo):
        from swu.engine.actions import legal_actions, apply, PayResourceForToken
        state = _make_state()
        flock = _place(state, "P0", _get_card(repo, "LOF", "255"), "ground")
        _give_resources(state, "P0", 8)

        state = _fire_when_played(state, flock)
        for _ in range(6):
            state = apply(state, next(a for a in legal_actions(state)
                                      if isinstance(a, PayResourceForToken)))
        # Cap of 6 reached → auto-resolved even though 2 resources remain ready.
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, flock.instance_id)) == 6
        assert state.player_by_id("P0").available_resources == 2

    def test_lof_255_may_pay_zero(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishPayResources
        state = _make_state()
        flock = _place(state, "P0", _get_card(repo, "LOF", "255"), "ground")
        _give_resources(state, "P0", 3)
        state = _fire_when_played(state, flock)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishPayResources)))
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, flock.instance_id)) == 0
        assert state.player_by_id("P0").available_resources == 3

    def test_lof_255_no_resources_no_decision(self, repo):
        state = _make_state()
        flock = _place(state, "P0", _get_card(repo, "LOF", "255"), "ground")
        state.player_by_id("P0").resources.clear()
        state = _fire_when_played(state, flock)
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, flock.instance_id)) == 0


class TestRefugeeOfThePath:
    """LOF_242 — When Played: you may give a Shield token to a unit with Sentinel."""

    def test_lof_242_gives_shield_to_sentinel_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        # Refugee itself does NOT have Sentinel (LOF_242's printed bar is empty; the
        # word "Sentinel" only appears in its ability text) — so it needs a separate
        # Sentinel unit to target. Cell Block Guard SOR_229 is a vanilla unit with an
        # unconditional printed Sentinel (Homestead Militia SOR_113's Sentinel is now
        # correctly encoded as conditional on 6+ resources, so it is no longer a
        # reliable always-Sentinel unit).
        refugee = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        sentinel = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")  # Sentinel
        non_sentinel = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, refugee)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert sentinel.instance_id in offered
        assert refugee.instance_id not in offered      # Refugee has no Sentinel
        assert non_sentinel.instance_id not in offered
        state = apply(state, ChooseTarget(sentinel.instance_id))
        assert _shield_count(state.find_instance(sentinel.instance_id)[1]) == 1

    def test_lof_242_no_sentinel_unit_auto_declines(self, repo):
        """With no Sentinel unit on the board the optional trigger is not offered.

        Refugee has no Sentinel itself, so a board of just Refugee has no valid
        target.
        """
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        refugee = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _fire_when_played(state, refugee)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── LOF_100 Kelleran Beq (qui-gon-jinn:05) ────────────────────────────────────

class TestKelleranBeq:
    """When Played: Search the top 7 cards of your deck for a unit, reveal it, and
    play it.  It costs 3 resources less.  (Put the rest on the bottom randomly.)"""

    def test_lof_100_plays_a_unit_from_top7_for_3_less(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectSearchCard, _effective_cost)
        from tests.test_sor_cards import _build_search_deck, _seed_rng
        state = _seed_rng(_make_state())
        kelleran = _place(state, "P0", _get_card(repo, "LOF", "100"), "ground")
        _give_resources(state, "P0", 10)
        unit = _get_card(repo, "SOR", "46")  # Consular Security Force, cost 4
        deck = _build_search_deck(state, "P0", [unit], [])
        target_iid = deck[0].instance_id
        expected_cost = max(0, _effective_cost(unit, state.player_by_id("P0")) - 3)
        avail_before = state.player_by_id("P0").available_resources

        state = _fire_when_played(state, kelleran)
        assert state.pending_decisions[-1].kind == "deck_search"
        cands = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)}
        assert target_iid in cands
        state = apply(state, SelectSearchCard(target_iid))

        # The chosen unit is now in play and paid for at 3 less.
        assert _find_instance(state, target_iid) is not None
        assert state.player_by_id("P0").available_resources == avail_before - expected_cost
        assert not state.pending_decisions

    def test_lof_100_bottoms_unsearched_cards(self, repo):
        from swu.engine.actions import apply, SelectSearchCard
        from tests.test_sor_cards import _build_search_deck, _seed_rng
        state = _seed_rng(_make_state())
        kelleran = _place(state, "P0", _get_card(repo, "LOF", "100"), "ground")
        _give_resources(state, "P0", 10)
        unit = _get_card(repo, "SOR", "46")
        other = _get_card(repo, "SOR", "85")  # Rukh (a second unit, not chosen)
        filler = _get_card(repo, "SOR", "74")  # Repair (fills the rest of the window)
        below = _get_card(repo, "SOR", "128")  # un-searched remainder (outside top 7)
        # Window of 7 = [unit, other, 5×filler]; `below` is the 8th card (remainder).
        deck = _build_search_deck(
            state, "P0", [unit, other] + [filler] * 5, [below])
        chosen, not_chosen, remainder = deck[0], deck[1], deck[7]

        state = _fire_when_played(state, kelleran)
        state = apply(state, SelectSearchCard(chosen.instance_id))

        ps = state.player_by_id("P0")
        # Chosen unit left the deck (it is in play); the un-searched remainder
        # stays on top, the not-chosen searched cards are bottomed below it.
        deck_ids = [c.instance_id for c in ps.deck]
        assert chosen.instance_id not in deck_ids
        assert deck_ids[0] == remainder.instance_id
        assert not_chosen.instance_id in deck_ids[1:]
        assert len(deck_ids) == 7  # 8 − 1 played

    def test_lof_100_only_affordable_units_offered(self, repo):
        """An event is never a candidate; a unit too expensive (after −3) is not
        offered when the controller cannot pay for it."""
        from swu.engine.actions import (
            legal_actions, SelectSearchCard, _effective_cost)
        from tests.test_sor_cards import _build_search_deck, _seed_rng
        state = _seed_rng(_make_state())
        kelleran = _place(state, "P0", _get_card(repo, "LOF", "100"), "ground")
        cheap = _get_card(repo, "SOR", "128")  # Death Star Stormtrooper, cost 1
        pricey = _get_card(repo, "SOR", "85")  # Rukh, cost 5
        event = _get_card(repo, "SOR", "74")   # Repair (event)
        deck = _build_search_deck(state, "P0", [cheap, pricey, event], [])
        cheap_ci, pricey_ci, event_ci = deck[0], deck[1], deck[2]

        # Give exactly enough to afford the cheap unit (−3) but not the pricey one.
        ps = state.player_by_id("P0")
        cheap_cost = max(0, _effective_cost(cheap, ps) - 3)
        pricey_cost = max(0, _effective_cost(pricey, ps) - 3)
        _give_resources(state, "P0", cheap_cost)  # < pricey_cost
        assert cheap_cost < pricey_cost

        state = _fire_when_played(state, kelleran)
        cands = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, SelectSearchCard)}
        assert cheap_ci.instance_id in cands
        assert pricey_ci.instance_id not in cands
        assert event_ci.instance_id not in cands

    def test_lof_100_played_unit_fires_its_own_when_played(self, repo):
        """The searched-and-played unit's own When Played ability fires (it is a
        real play, not a draw) — Patrolling V-Wing draws a card on entry."""
        from swu.engine.actions import apply, SelectSearchCard
        from tests.test_sor_cards import _build_search_deck, _seed_rng
        state = _seed_rng(_make_state())
        kelleran = _place(state, "P0", _get_card(repo, "LOF", "100"), "ground")
        _give_resources(state, "P0", 10)
        vwing = _get_card(repo, "TWI", "107")  # Patrolling V-Wing: WhenPlayed draw 1
        # Deck: V-Wing on top, then a card it will draw.
        below = _get_card(repo, "SOR", "74")
        deck = _build_search_deck(state, "P0", [vwing], [below])
        hand_before = len(state.player_by_id("P0").hand)

        state = _fire_when_played(state, kelleran)
        state = apply(state, SelectSearchCard(deck[0].instance_id))

        assert _find_instance(state, deck[0].instance_id) is not None
        assert len(state.player_by_id("P0").hand) == hand_before + 1


# ── qui-gon-jinn:06 — New primitive: force-token (the keystone) ────────────────

def _set_base(state, owner_id, base_def):
    """Replace ``owner_id``'s base with one built from ``base_def`` (e.g. Jedi
    Temple LOF_23).  Returns the new base CardInstance."""
    import uuid
    from swu.engine.state import CardInstance, Zone
    from swu.cards.models import Base
    ps = state.player_by_id(owner_id)
    ps.base_zone = [c for c in ps.base_zone if not isinstance(c.card_def, Base)]
    ci = CardInstance(f"{owner_id}_jbase_{uuid.uuid4().hex[:4]}", base_def,
                      owner_id, Zone.BASE_ZONE)
    ps.base_zone.append(ci)
    return ci


def _fire_attack_declared(state, attacker_ci, defender_ci=None):
    """Fire an AttackDeclared event (drives WhenUnitAttacks observers like Jedi
    Temple LOF_23) without running the full combat pipeline."""
    from swu.engine.events import AttackDeclared
    from swu.abilities.resolver import fire_triggered_abilities
    did = defender_ci.instance_id if defender_ci else None
    evt = AttackDeclared(
        attacker_player_id=attacker_ci.owner_id,
        attacker_instance_id=attacker_ci.instance_id,
        attacker_name=attacker_ci.card_def.display_name,
        defender_instance_id=did,
        defender_name=defender_ci.card_def.display_name if defender_ci else "Base",
    )
    state.event_log.append(evt)
    return fire_triggered_abilities(
        state, evt, after_all_player_idx=0,
        event_ctx={"attacker_id": attacker_ci.instance_id, "defender_id": did})


def _add_deck_card(state, repo, owner, set_code, num):
    """Put a card on top of ``owner``'s deck (so a draw has something to take)."""
    from swu.engine.state import CardInstance, Zone
    import uuid
    ci = CardInstance(f"{owner}_deck_{uuid.uuid4().hex[:5]}",
                      _get_card(repo, set_code, num), owner, Zone.DECK)
    state.player_by_id(owner).deck.insert(0, ci)
    return ci


class TestYounglingPadawan:
    """LOF_193 — When Played: create your Force token."""

    def test_lof_193_creates_force_token(self, repo):
        state = _make_state()
        youngling = _place(state, "P0", _get_card(repo, "LOF", "193"), "ground")
        assert not state.player_by_id("P0").has_force_token
        state = _fire_when_played(state, youngling)
        assert state.player_by_id("P0").has_force_token

    def test_lof_193_second_play_is_idempotent(self, repo):
        """A player has at most one Force token — creating one already held is a
        no-op (still just a single boolean)."""
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        youngling = _place(state, "P0", _get_card(repo, "LOF", "193"), "ground")
        state = _fire_when_played(state, youngling)
        assert state.player_by_id("P0").has_force_token


class TestJediTemple:
    """LOF_23 (Base) — When a friendly Force unit attacks: create your Force token."""

    def test_lof_23_friendly_force_unit_attack_creates_token(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "23"))
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # Force
        assert not state.player_by_id("P0").has_force_token
        state = _fire_attack_declared(state, force_unit)
        assert state.player_by_id("P0").has_force_token

    def test_lof_23_non_force_unit_attack_no_token(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "23"))
        non_force = _place(state, "P0", _get_card(repo, "SHD", "96"), "ground")  # Underworld
        state = _fire_attack_declared(state, non_force)
        assert not state.player_by_id("P0").has_force_token

    def test_lof_23_enemy_force_unit_attack_no_token(self, repo):
        """The base belongs to P0; an enemy (P1) Force unit attacking is not a
        *friendly* Force unit, so P0 gets no token."""
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "23"))
        enemy_force = _place(state, "P1", _get_card(repo, "LOF", "196"), "ground")
        state = _fire_attack_declared(state, enemy_force)
        assert not state.player_by_id("P0").has_force_token


class TestJediSentinel:
    """LOF_196 — While the Force is with you, this unit gains Sentinel."""

    def test_lof_196_no_sentinel_without_force_token(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        js = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        assert not has_keyword(state, js, Keyword.SENTINEL)

    def test_lof_196_gains_sentinel_with_force_token(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        js = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        state.player_by_id("P0").has_force_token = True
        assert has_keyword(state, js, Keyword.SENTINEL)


class TestLukeSkywalker:
    """LOF_249 — When you play another unique unit: you may use the Force; if you
    do, give an Experience + Shield token to this unit."""

    def _setup(self, repo, force_token=True, unique=True):
        state = _make_state()
        luke = _place(state, "P0", _get_card(repo, "LOF", "249"), "ground")
        state.player_by_id("P0").has_force_token = force_token
        played_num = "96" if unique else "193"  # Obi-Wan (unique) / Youngling (not)
        other = _place(state, "P0", _get_card(repo, "LOF", played_num), "ground")
        return state, luke, other

    def test_lof_249_use_force_gives_tokens(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects)
        state, luke, other = self._setup(repo)
        state = _fire_card_played(state, other)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, AutoResolveEffects())  # the no-target CustomEffect
        luke = _find_instance(state, luke.instance_id)
        assert _experience_count(luke) == 1 and _shield_count(luke) == 1
        assert not state.player_by_id("P0").has_force_token

    def test_lof_249_decline_keeps_token_no_bonus(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state, luke, other = self._setup(repo)
        state = _fire_card_played(state, other)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        luke = _find_instance(state, luke.instance_id)
        assert _experience_count(luke) == 0 and _shield_count(luke) == 0
        assert state.player_by_id("P0").has_force_token

    def test_lof_249_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state, luke, other = self._setup(repo, force_token=False)
        state = _fire_card_played(state, other)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions

    def test_lof_249_not_triggered_by_non_unique_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state, luke, other = self._setup(repo, unique=False)
        state = _fire_card_played(state, other)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestImpossibleEscape:
    """LOF_218 — You may exhaust a friendly unit OR use the Force; if you do
    either, exhaust an enemy unit and draw a card."""

    def test_lof_218_use_force_exhausts_enemy_and_draws(self, repo):
        from swu.engine.actions import apply, UseForceOption, ChooseUseForcePayoffTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_deck_card(state, repo, "P0", "LOF", "193")
        hand_before = len(state.player_by_id("P0").hand)
        state, _ = _play_event_from_hand(state, repo, "LOF", "218")
        assert state.pending_decisions[-1].kind == "use_force"
        state = apply(state, UseForceOption("force"))
        # drew a card; now at payoff stage to exhaust the enemy
        assert len(state.player_by_id("P0").hand) == hand_before + 1
        assert not state.player_by_id("P0").has_force_token
        state = apply(state, ChooseUseForcePayoffTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted

    def test_lof_218_exhaust_friendly_alternative(self, repo):
        from swu.engine.actions import legal_actions, apply, UseForceOption
        state = _make_state()  # no force token
        friendly = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _add_deck_card(state, repo, "P0", "LOF", "193")
        state, _ = _play_event_from_hand(state, repo, "LOF", "218")
        # only the exhaust-friendly cost is available (no Force token)
        opts = [a for a in legal_actions(state) if isinstance(a, UseForceOption)]
        assert opts and all(a.option == "exhaust_friendly" for a in opts)
        state = apply(state, UseForceOption("exhaust_friendly", friendly.instance_id))
        assert _find_instance(state, friendly.instance_id).exhausted

    def test_lof_218_decline_does_nothing(self, repo):
        from swu.engine.actions import apply, DeclineUseForce
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "218")
        state = apply(state, DeclineUseForce())
        assert state.player_by_id("P0").has_force_token
        assert not _find_instance(state, enemy.instance_id).exhausted
        assert not state.pending_decisions

    def test_lof_218_no_cost_available_no_decision(self, repo):
        """No Force token and no ready friendly unit → nothing happens (no decision)."""
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "218")
        assert not any(d.kind == "use_force" for d in state.pending_decisions)


class TestTheWillOfTheForce:
    """LOF_227 — Return a non-leader unit to its owner's hand. You may use the
    Force; if you do, that player discards a random card."""

    def test_lof_227_return_then_use_force_discards(self, repo):
        from swu.engine.actions import apply, ChooseTarget, UseForceOption
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "LOF", "193"))
        state, _ = _play_event_from_hand(state, repo, "LOF", "227")
        # resolve_effects: choose the enemy unit to return
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert state.pending_decisions[-1].kind == "use_force"
        # returned unit is back in P1's hand
        assert any(c.instance_id == enemy.instance_id
                   for c in state.player_by_id("P1").hand)
        p1_hand_before = len(state.player_by_id("P1").hand)
        state = apply(state, UseForceOption("force"))
        assert not state.player_by_id("P0").has_force_token
        assert len(state.player_by_id("P1").hand) == p1_hand_before - 1

    def test_lof_227_decline_returns_without_discard(self, repo):
        from swu.engine.actions import apply, ChooseTarget, DeclineUseForce
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "LOF", "193"))
        state, _ = _play_event_from_hand(state, repo, "LOF", "227")
        state = apply(state, ChooseTarget(enemy.instance_id))
        p1_hand_before = len(state.player_by_id("P1").hand)
        state = apply(state, DeclineUseForce())
        assert state.player_by_id("P0").has_force_token
        assert len(state.player_by_id("P1").hand) == p1_hand_before


class TestQuiGonJinn:
    """LOF_16 — undeployed Action [Exhaust, use the Force]: return a friendly
    non-leader unit, play a cheaper non-Villainy unit free."""

    def _use_undeployed(self, state, qg):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == qg.instance_id)
        return apply(state, use)

    def _leader_ci(self, state):
        from swu.cards.models import Leader
        return next(c for c in state.player_by_id("P0").base_zone
                    if isinstance(c.card_def, Leader))

    def test_lof_16_undeployed_returns_and_plays_cheaper_free(self, repo):
        from swu.engine.actions import apply, ChooseTarget, PlayFromHand
        state = _make_state()
        qg = _place_leader(state, "P0", _get_card(repo, "LOF", "16"))
        state.player_by_id("P0").has_force_token = True
        returned = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # cost 4
        cheaper = _put_in_hand(state, "P0", _get_card(repo, "LOF", "193"))       # cost 2
        state = self._use_undeployed(state, qg)
        # cost paid: leader exhausted + Force token spent
        assert self._leader_ci(state).exhausted
        assert not state.player_by_id("P0").has_force_token
        # choose the friendly unit to return, then play the cheaper unit free
        state = apply(state, ChooseTarget(returned.instance_id))
        assert any(c.instance_id == returned.instance_id
                   for c in state.player_by_id("P0").hand)
        state = apply(state, PlayFromHand(cheaper.instance_id))
        assert _find_instance(state, cheaper.instance_id) is not None

    def test_lof_16_deployed_when_attack_ends_bounce_and_play(self, repo):
        """Deployed side: When this unit completes an attack (and survives), the
        optional same bounce-then-play-cheaper (no Force cost)."""
        from swu.engine.actions import apply, AcceptTrigger, ChooseTarget, PlayFromHand
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import legal_actions
        state = _make_state()
        qg = _place(state, "P0", _get_card(repo, "LOF", "16"), "ground")
        qg.deployed = True
        returned = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # cost 4
        cheaper = _put_in_hand(state, "P0", _get_card(repo, "LOF", "193"))       # cost 2
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=1,
            event_ctx={"attack_ended_survivor": qg.instance_id})
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(returned.instance_id))
        state = apply(state, PlayFromHand(cheaper.instance_id))
        assert any(c.instance_id == returned.instance_id
                   for c in state.player_by_id("P0").hand)
        assert _find_instance(state, cheaper.instance_id) is not None

    def test_lof_16_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        qg = _place_leader(state, "P0", _get_card(repo, "LOF", "16"))
        _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        assert not any(isinstance(a, UseAbility) and a.source_id == qg.instance_id
                       for a in legal_actions(state))

    def test_lof_16_not_offered_without_non_leader_unit(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        qg = _place_leader(state, "P0", _get_card(repo, "LOF", "16"))
        state.player_by_id("P0").has_force_token = True
        assert not any(isinstance(a, UseAbility) and a.source_id == qg.instance_id
                       for a in legal_actions(state))

    def test_lof_16_excludes_villainy_unit_from_replay(self, repo):
        """The replayed unit must be non-Villainy: a Villainy unit in hand cheaper
        than the returned unit is not offered."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayFromHand
        state = _make_state()
        qg = _place_leader(state, "P0", _get_card(repo, "LOF", "16"))
        state.player_by_id("P0").has_force_token = True
        returned = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # cost 4
        villainy = _put_in_hand(state, "P0", _get_card(repo, "SHD", "30"))  # Death Trooper (Villainy)
        state = self._use_undeployed(state, qg)
        state = apply(state, ChooseTarget(returned.instance_id))
        offered = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        assert all(a.instance_id != villainy.instance_id for a in offered)



# ── LOF_197 Qui-Gon Jinn's Aethersprite ───────────────────────────────────────

def _redo_charges(state, pid="P0"):
    """Armed 'use the next When Played ability again' charges for a player."""
    return state.game_memory.when_played_redo_charges.get(pid, 0)


def _accept_top_trigger(state):
    """Accept the top trigger_option decision (the most-recently surfaced 'you
    may' / redo prompt)."""
    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, AcceptTrigger)))


def _has_accept_trigger(state, source_id=None):
    from swu.engine.actions import legal_actions, AcceptTrigger
    return any(isinstance(a, AcceptTrigger)
               and (source_id is None or a.source_id == source_id)
               for a in legal_actions(state))


class TestQuiGonJinnsAethersprite:
    """LOF_197 — On Attack: "The next time you use a 'When Played' ability this
    phase, you may use that ability again." (the duplicate-the-next-WhenPlayed
    meta-mechanic)."""

    def test_lof_197_on_attack_arms_a_redo_charge(self, repo):
        """The OnAttack arms exactly one phase-scoped charge for its controller."""
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        assert _redo_charges(state) == 0
        state = _fire_on_attack(state, sprite)
        assert _redo_charges(state) == 1
        # No decision is created by the arming itself.
        assert not state.pending_decisions

    def test_lof_197_redoes_an_optional_when_played(self, repo):
        """With a charge armed, an accepted optional WhenPlayed (Stinger Mantis,
        deal 2 to an exhausted unit) may be used a second time — 2 + 2 = 4."""
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        state = _fire_on_attack(state, sprite)            # arm the charge
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.exhausted = True
        state = _fire_when_played(state, mantis)
        # First use: accept + target.
        state = _accept_top_trigger(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2
        # The charge is now spent and a redo of Stinger is offered.
        assert _redo_charges(state) == 0
        assert _has_accept_trigger(state, mantis.instance_id)
        # Second use (the redo): accept + target the same exhausted unit again.
        state = _accept_top_trigger(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4
        # The redo does not chain — no third prompt, stack empty.
        assert not _has_accept_trigger(state, mantis.instance_id)
        assert not state.pending_decisions

    def test_lof_197_charge_is_one_shot(self, repo):
        """One charge powers exactly one When Played ability; a later WhenPlayed
        this phase is not redone."""
        from swu.engine.actions import apply, ChooseTarget, legal_actions, DeclineTrigger
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        state = _fire_on_attack(state, sprite)
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        state = _fire_when_played(state, mantis)
        state = _accept_top_trigger(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        # Decline the redo to clear the stack.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _redo_charges(state) == 0
        # A second, fresh WhenPlayed (another Stinger) is NOT redone.  Stinger
        # Mantis is unique, so remove the first before placing the second to avoid
        # the (unrelated) Unique Rule duplicate resolution.
        p0 = state.player_by_id("P0")
        p0.ground_arena = [u for u in p0.ground_arena
                           if u.instance_id != mantis.instance_id]
        mantis2 = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        state = _fire_when_played(state, mantis2)
        state = _accept_top_trigger(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert not _has_accept_trigger(state, mantis2.instance_id)
        assert not state.pending_decisions

    def test_lof_197_declining_original_does_not_consume_charge(self, repo):
        """Declining an optional WhenPlayed is not a 'use' — the charge survives
        for the next When Played ability."""
        from swu.engine.actions import apply, legal_actions, DeclineTrigger, ChooseTarget
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        state = _fire_on_attack(state, sprite)
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        state = _fire_when_played(state, mantis)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        # Declined → no use → charge intact, no redo prompt.
        assert _redo_charges(state) == 1
        assert not state.pending_decisions
        # The next WhenPlayed this phase still gets the redo.
        mantis2 = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        state = _fire_when_played(state, mantis2)
        state = _accept_top_trigger(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _redo_charges(state) == 0
        assert _has_accept_trigger(state, mantis2.instance_id)

    def test_lof_197_no_charge_means_no_redo(self, repo):
        """Without a charge, an optional WhenPlayed resolves once with no redo."""
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        mantis = _place(state, "P0", _get_card(repo, "LOF", "198"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy.exhausted = True
        state = _fire_when_played(state, mantis)
        state = _accept_top_trigger(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2
        assert not state.pending_decisions

    def test_lof_197_redoes_an_inline_when_played(self, repo):
        """The redo also works for a mandatory inline WhenPlayed that spawns no
        sub-decision: J-Type Nubian Starship "When Played: Draw a card" draws twice
        (once for the play, once for the redo)."""
        from swu.engine.state import CardInstance, Zone
        import uuid
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        state = _fire_on_attack(state, sprite)
        # Stock P0's deck so there is something to draw.
        for _ in range(4):
            state.player_by_id("P0").deck.append(CardInstance(
                f"P0_deck_{uuid.uuid4().hex[:6]}", _get_card(repo, "SOR", "46"),
                "P0", Zone.DECK))
        jtype = _place(state, "P0", _get_card(repo, "LOF", "194"), "space")
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_when_played(state, jtype)           # inline draw 1, redo armed
        assert len(state.player_by_id("P0").hand) == hand_before + 1
        assert _redo_charges(state) == 0
        assert _has_accept_trigger(state, jtype.instance_id)
        # Accept the redo, then resolve its (untargeted) draw to completion.
        from swu.engine.actions import apply, AutoResolveEffects
        state = _accept_top_trigger(state)                # redo → draw 1 more
        state = apply(state, AutoResolveEffects())
        assert len(state.player_by_id("P0").hand) == hand_before + 2
        assert not state.pending_decisions

    def test_lof_197_charge_round_trips_through_serialisation(self, repo):
        """The armed charge survives a GameMemory to_dict/from_dict round-trip
        (so a mid-decision save/replay does not drop it)."""
        from swu.engine.state import GameMemory
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        state = _fire_on_attack(state, sprite)
        restored = GameMemory.from_dict(state.game_memory.to_dict())
        assert restored.when_played_redo_charges.get("P0") == 1

    def test_lof_197_charge_cleared_at_round_rollover(self, repo):
        """'This phase' — the charge is cleared when the action phase ends."""
        state = _make_state()
        sprite = _place(state, "P0", _get_card(repo, "LOF", "197"), "space")
        state = _fire_on_attack(state, sprite)
        assert _redo_charges(state) == 1
        state.game_memory.clear_phase()
        assert _redo_charges(state) == 0


# ── darth-maul:01 — Direct damage & removal ───────────────────────────────────


def _fire_attack_ends(state, attacker_ci):
    """Fire a WhenAttackEnds trigger for a surviving attacker (Pong Krell LOF_38)."""
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


class TestPongKrell:
    """LOF_38 — When this unit completes an attack (and survives): You may defeat
    a unit with less remaining HP than this unit's power (2)."""

    def test_lof_38_defeats_low_hp_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        krell = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")  # 2/9
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.damage = 6  # remaining HP 1 < Krell power 2 -> defeatable
        state = _fire_attack_ends(state, krell)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id) is None  # defeated

    def test_lof_38_unit_with_hp_ge_power_not_targetable(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        krell = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")  # power 2
        tough = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # remaining 7
        state = _fire_attack_ends(state, krell)
        # remaining HP 7 >= power 2 -> no eligible target -> optional trigger not offered
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions
        assert _find_instance(state, tough.instance_id) is not None


class TestFallenLightsaber:
    """SOR_137 — If attached unit is a Force unit, it gains: On Attack: deal 1 to
    each ground unit the defending player controls."""

    def test_sor_137_force_host_damages_each_enemy_ground_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")  # Pong Krell — Force
        _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "137"), "P0")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        e2 = _place(state, "P1", _get_card(repo, "SOR", "48"), "ground")
        e_space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # space — unaffected
        state = _fire_on_attack(state, host)
        # mandatory effect resolves inline (EACH_ENEMY ground)
        assert _find_instance(state, e1.instance_id).damage == 1
        assert _find_instance(state, e2.instance_id).damage == 1
        assert _find_instance(state, e_space.instance_id).damage == 0

    def test_sor_137_non_force_host_grants_nothing(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel/Trooper — not Force
        _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "137"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, host)
        assert _find_instance(state, enemy.instance_id).damage == 0
        assert not state.pending_decisions


class TestSithHolocron:
    """LOF_138 — Attached unit gains: On Attack: you may deal 2 damage to a
    friendly unit. If you do, this unit gets +2/+0 for this attack."""

    def test_lof_138_damage_friendly_and_buff_host(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power)
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")  # Pong Krell — Force, power 2
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "138"), "P0")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7 — the friendly target
        base_power = compute_power(state, host)
        state = _fire_on_attack(state, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(friend.instance_id))
        assert _find_instance(state, friend.instance_id).damage == 2
        # host gained +2/+0 for this attack
        host2 = _find_instance(state, host.instance_id)
        assert compute_power(state, host2) == base_power + 2

    def test_lof_138_decline_does_neither(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, DeclineTrigger, compute_power)
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "138"), "P0")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        base_power = compute_power(state, host)
        state = _fire_on_attack(state, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert _find_instance(state, friend.instance_id).damage == 0
        assert compute_power(state, _find_instance(state, host.instance_id)) == base_power


class TestMerrin:
    """LOF_160 — On Attack: You may discard a card from your hand. If you do, deal
    2 damage to a unit."""

    def test_lof_160_discard_then_deal_2(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        merrin = _place(state, "P0", _get_card(repo, "LOF", "160"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_on_attack(state, merrin)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2
        assert len(state.player_by_id("P0").hand) == hand_before - 1
        assert len(state.player_by_id("P0").discard) >= 1

    def test_lof_160_empty_hand_not_offered(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        merrin = _place(state, "P0", _get_card(repo, "LOF", "160"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not state.player_by_id("P0").hand
        state = _fire_on_attack(state, merrin)
        # CONTROLLER_HAS_CARD_IN_HAND gates collection -> trigger not offered
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestCountDooku:
    """TWI_138 — Exploit 2, Overwhelm. When Played: for each unit you exploited,
    you may deal damage to an enemy unit equal to its power."""

    def test_twi_138_per_exploit_damage_synthetic(self, repo):
        from swu.engine.actions import (
            push_per_exploit_damage, apply, DealExploitDamage)
        state = _make_state()
        dooku = _place(state, "P0", _get_card(repo, "TWI", "138"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        e2 = _place(state, "P1", _get_card(repo, "SOR", "48"), "ground")  # 4/6
        push_per_exploit_damage(state, dooku, [3, 5])
        assert state.pending_decisions[-1].kind == "per_exploit_damage"
        state = apply(state, DealExploitDamage(e1.instance_id))   # 3 to e1
        state = apply(state, DealExploitDamage(e2.instance_id))   # 5 to e2
        assert _find_instance(state, e1.instance_id).damage == 3
        assert _find_instance(state, e2.instance_id).damage == 5

    def test_twi_138_decline_a_chunk(self, repo):
        from swu.engine.actions import (
            push_per_exploit_damage, apply, DealExploitDamage, DeclineExploitDamage)
        state = _make_state()
        dooku = _place(state, "P0", _get_card(repo, "TWI", "138"), "ground")
        e1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        push_per_exploit_damage(state, dooku, [3, 5])
        state = apply(state, DeclineExploitDamage())             # skip the first (3)
        state = apply(state, DealExploitDamage(e1.instance_id))  # 5 to e1
        assert _find_instance(state, e1.instance_id).damage == 5
        assert not state.pending_decisions

    def test_twi_138_no_enemy_unit_fizzles(self, repo):
        from swu.engine.actions import push_per_exploit_damage
        state = _make_state()
        dooku = _place(state, "P0", _get_card(repo, "TWI", "138"), "ground")
        push_per_exploit_damage(state, dooku, [4])
        assert not state.pending_decisions  # no enemy unit -> nothing pushed

    def test_twi_138_full_exploit_flow(self, repo):
        """Play Count Dooku via Exploit, sacrifice a power-4 unit, then deal 4 to
        an enemy unit through the When Played per_exploit_damage decision."""
        from swu.engine.state import CardInstance, Zone
        from swu.engine.actions import (
            apply, PlayCard, ExploitSacrifice, ExploitCommit,
            DealExploitDamage)
        state = _make_state()
        dooku_ci = CardInstance("P0_dooku", _get_card(repo, "TWI", "138"), "P0", Zone.HAND)
        state.player_by_id("P0").hand.append(dooku_ci)
        fodder = _place(state, "P0", _get_card(repo, "SOR", "48"), "ground")  # 4/6, power 4
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        _give_resources(state, "P0", 20)
        state = apply(state, PlayCard(dooku_ci.instance_id))
        assert state.pending_decisions[-1].kind == "exploit"
        state = apply(state, ExploitSacrifice(fodder.instance_id))
        state = apply(state, ExploitCommit())
        # WhenPlayed pushed the per_exploit_damage decision (one chunk = power 4)
        assert state.pending_decisions[-1].kind == "per_exploit_damage"
        state = apply(state, DealExploitDamage(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4


# ── darth-maul:02 — Card advantage & disruption ───────────────────────────────

class TestNightsisterWarrior:
    """LOF_59 — Nightsister Warrior (2/2): "When Defeated: Draw a card." """

    def test_lof_59_when_defeated_draws(self, repo):
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        # Seed the deck so there is a card to draw.
        deck_card = CardInstance("P0_deck1", _get_card(repo, "SOR", "46"), "P0", Zone.DECK)
        state.player_by_id("P0").deck.append(deck_card)
        warrior = _place(state, "P0", _get_card(repo, "LOF", "59"), "ground")
        before = len(state.player_by_id("P0").hand)
        state = _fire_when_defeated(state, warrior)
        assert len(state.player_by_id("P0").hand) == before + 1
        assert deck_card.instance_id in {c.instance_id
                                         for c in state.player_by_id("P0").hand}


# ── darth-maul:03 — Combat tricks, buffs & tempo ──────────────────────────────


def _fire_attack_defeats_unit(state, attacker_ci):
    """Fire an OnAttackDefeatsUnit trigger for ``attacker_ci`` (Oggdo Bogdo LOF_63:
    'When this unit attacks and defeats a unit')."""
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(
        state, None, after_all_player_idx=0,
        event_ctx={"attack_defeated_unit": attacker_ci.instance_id})


class TestOggdoBogdo:
    """LOF_63 — Oggdo Bogdo (5/5): "This unit can't attack unless it's damaged.
    When this unit attacks and defeats a unit: Heal 2 damage from this unit." """

    def test_lof_63_undamaged_cannot_attack(self, repo):
        """Undamaged Oggdo is dropped from the legal attackers."""
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        oggdo = _place(state, "P0", _get_card(repo, "LOF", "63"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # an enemy
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert oggdo.instance_id not in attackers

    def test_lof_63_damaged_can_attack(self, repo):
        """A damaged Oggdo may attack normally (the restriction lifts)."""
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        oggdo = _place(state, "P0", _get_card(repo, "LOF", "63"), "ground")
        oggdo.damage = 1
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert oggdo.instance_id in attackers

    def test_lof_63_heals_2_when_attack_defeats_a_unit(self, repo):
        """On defeating a unit by attacking, Oggdo heals 2 from itself."""
        state = _make_state()
        oggdo = _place(state, "P0", _get_card(repo, "LOF", "63"), "ground")
        oggdo.damage = 3
        state = _fire_attack_defeats_unit(state, oggdo)
        assert _find_instance(state, oggdo.instance_id).damage == 1


class TestDarthMaulsLightsaber:
    """LOF_140 — Darth Maul's Lightsaber (Upgrade, Overwhelm): "When Played: If
    attached unit is Darth Maul, you may attack with him.  For this attack, he
    gains Overwhelm and can't attack bases." """

    def test_lof_140_grants_maul_an_attack_no_base(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit, DeclineGrantedAttack
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LOF", "9"), "ground")  # Darth Maul
        saber = _attach_upgrade_directly(state, maul, _get_card(repo, "LOF", "140"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, saber, maul)
        atks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        # Only Maul (the host) is offered as the attacker …
        assert atks and all(a.attacker_id == maul.instance_id for a in atks)
        # … and only against the enemy unit, never a base (no_base).
        assert all(a.defender_id == enemy.instance_id for a in atks)
        # "you may attack" -> a decline is offered.
        assert any(isinstance(a, DeclineGrantedAttack) for a in legal_actions(state))

    def test_lof_140_maul_gains_overwhelm_for_the_attack(self, repo):
        """Resolving the granted attack grants Maul Overwhelm (this attack)."""
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LOF", "9"), "ground")
        saber = _attach_upgrade_directly(state, maul, _get_card(repo, "LOF", "140"), "P0")
        # A small enemy unit so spillover/Overwhelm matters; Maul is 5/6.
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy.damage = 6  # remaining HP 1 -> Maul (power 5) overkills it
        base_dmg_before = state.player_by_id("P1").base_zone[0].damage
        state = _fire_upgrade_played(state, saber, maul)
        atk = next(a for a in legal_actions(state) if isinstance(a, AttackWithUnit))
        state = apply(state, atk)
        # Overwhelm spillover went to the enemy base (defeated unit had 1 HP left,
        # Maul dealt 5 -> 4 spill onto base).
        assert state.player_by_id("P1").base_zone[0].damage > base_dmg_before

    def test_lof_140_non_maul_host_no_attack(self, repo):
        """On a non-Darth-Maul host the trigger is not collected (no attack)."""
        from swu.engine.actions import legal_actions, DeclineGrantedAttack
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Maul
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "140"), "P0")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, saber, host)
        assert not state.pending_decisions
        assert not any(isinstance(a, DeclineGrantedAttack) for a in legal_actions(state))


class TestScimitar:
    """LOF_233 — Scimitar (3/4): "While this unit is damaged, it gets +3/+0." """

    def test_lof_233_buff_only_while_damaged(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        scimitar = _place(state, "P0", _get_card(repo, "LOF", "233"), "space")
        assert compute_power(state, scimitar) == 3  # undamaged
        scimitar.damage = 1
        assert compute_power(state, scimitar) == 6  # +3/+0 while damaged
        scimitar.damage = 0
        assert compute_power(state, scimitar) == 3  # winks off when healed


# ── darth-maul:04 — New primitive: force-token (reuses qui-gon-jinn:06) ────────


class TestDarthMaul:
    """LOF_9 (Leader) — undeployed Action [Exhaust, use the Force]: deal 1 to a unit
    and 1 to a different unit; deployed On Attack: the same."""

    def _use_undeployed(self, state, maul):
        from swu.engine.actions import legal_actions, apply, UseAbility
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == maul.instance_id)
        return apply(state, use)

    def test_lof_9_undeployed_deals_1_to_two_units(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        maul = _place_leader(state, "P0", _get_card(repo, "LOF", "9"))
        state.player_by_id("P0").has_force_token = True
        u1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        u2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._use_undeployed(state, maul)
        # cost paid: Force token spent
        assert not state.player_by_id("P0").has_force_token
        state = apply(state, ChooseTarget(u1.instance_id))   # first damage
        state = apply(state, ChooseTarget(u2.instance_id))   # different unit
        assert _find_instance(state, u1.instance_id).damage == 1
        assert _find_instance(state, u2.instance_id).damage == 1

    def test_lof_9_on_attack_deals_1_to_two_units(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        maul = _place(state, "P0", _get_card(repo, "LOF", "9"), "ground")
        maul.deployed = True
        u1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        u2 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, maul, u1)
        state = apply(state, ChooseTarget(u1.instance_id))
        state = apply(state, ChooseTarget(u2.instance_id))
        assert _find_instance(state, u1.instance_id).damage == 1
        assert _find_instance(state, u2.instance_id).damage == 1

    def test_lof_9_single_unit_takes_only_one_damage(self, repo):
        """With only one unit in play the second damage has no *different* unit and
        fizzles — the unit takes 1, not 2."""
        from swu.engine.actions import apply, ChooseTarget, legal_actions, AutoResolveEffects
        state = _make_state()
        maul = _place_leader(state, "P0", _get_card(repo, "LOF", "9"))
        state.player_by_id("P0").has_force_token = True
        only = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._use_undeployed(state, maul)
        state = apply(state, ChooseTarget(only.instance_id))
        # the second effect fizzles (no other unit); drain any auto-resolve
        while any(isinstance(a, AutoResolveEffects) for a in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert _find_instance(state, only.instance_id).damage == 1

    def test_lof_9_undeployed_requires_force_token(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        maul = _place_leader(state, "P0", _get_card(repo, "LOF", "9"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # no Force token → the undeployed Action (UseForce cost) is not affordable
        assert not any(isinstance(a, UseAbility) and a.source_id == maul.instance_id
                       for a in legal_actions(state))


class TestShadowedUndercity:
    """LOF_21 (Base) — When a friendly Force unit attacks: create your Force token."""

    def test_lof_21_friendly_force_attack_creates_token(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "21"))
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # Force
        assert not state.player_by_id("P0").has_force_token
        state = _fire_attack_declared(state, force_unit)
        assert state.player_by_id("P0").has_force_token

    def test_lof_21_non_force_attack_no_token(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "21"))
        non_force = _place(state, "P0", _get_card(repo, "SHD", "96"), "ground")  # Underworld
        state = _fire_attack_declared(state, non_force)
        assert not state.player_by_id("P0").has_force_token


class TestKaris:
    """LOF_31 — When Defeated: You may use the Force. If you do, give a unit –2/–2
    for this phase."""

    def test_lof_31_use_force_debuffs_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget,
            compute_power, compute_hp)
        state = _make_state()
        karis = _place(state, "P0", _get_card(repo, "LOF", "31"), "ground")
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_defeated(state, karis)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        enemy = _find_instance(state, enemy.instance_id)
        assert compute_power(state, enemy) == 1 and compute_hp(state, enemy) == 5
        assert not state.player_by_id("P0").has_force_token

    def test_lof_31_decline_keeps_token(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger, compute_power
        state = _make_state()
        karis = _place(state, "P0", _get_card(repo, "LOF", "31"), "ground")
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, karis)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").has_force_token
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 3

    def test_lof_31_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        karis = _place(state, "P0", _get_card(repo, "LOF", "31"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, karis)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestTalzinsAssassin:
    """LOF_35 — When Played: You may use the Force. If you do, give a unit –3/–3 for
    this phase."""

    def test_lof_35_use_force_debuffs_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget,
            compute_power, compute_hp)
        state = _make_state()
        assassin = _place(state, "P0", _get_card(repo, "LOF", "35"), "ground")
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, assassin)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        enemy = _find_instance(state, enemy.instance_id)
        assert compute_power(state, enemy) == 0 and compute_hp(state, enemy) == 4
        assert not state.player_by_id("P0").has_force_token

    def test_lof_35_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        assassin = _place(state, "P0", _get_card(repo, "LOF", "35"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, assassin)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestDarthSidious:
    """LOF_39 — When Played: You may use the Force. If you do, defeat each non-Sith
    unit with 3 or less remaining HP."""

    def test_lof_39_wipes_low_hp_non_sith_only(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, AutoResolveEffects
        state = _make_state()
        sidious = _place(state, "P0", _get_card(repo, "LOF", "39"), "ground")  # 6/8 Sith
        sidious.damage = 6  # remaining 2 — but Sith, so survives the wipe
        state.player_by_id("P0").has_force_token = True
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        victim.damage = 4  # remaining 3 → defeated
        survivor = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # remaining 7
        state = _fire_when_played(state, sidious)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        while any(isinstance(a, AutoResolveEffects) for a in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert _find_instance(state, victim.instance_id) is None      # defeated
        assert _find_instance(state, survivor.instance_id) is not None  # high HP
        assert _find_instance(state, sidious.instance_id) is not None  # Sith, excluded
        assert not state.player_by_id("P0").has_force_token

    def test_lof_39_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        sidious = _place(state, "P0", _get_card(repo, "LOF", "39"), "ground")
        v = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        v.damage = 4
        state = _fire_when_played(state, sidious)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestDrainEssence:
    """LOF_41 (Event) — Deal 2 damage to a unit. Create your Force token."""

    def test_lof_41_damages_and_creates_token(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _ = _play_event_from_hand(state, repo, "LOF", "41")
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2
        assert state.player_by_id("P0").has_force_token

    def test_lof_41_creates_token_even_with_no_unit(self, repo):
        """The "create your Force token" half lands even when there is no unit to
        damage (the targeted damage fizzles, the token is created)."""
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "LOF", "41")
        assert state.player_by_id("P0").has_force_token
        assert not state.pending_decisions


class TestChirrutImwe:
    """LOF_67 — When this unit is attacked: You may use the Force. If you do, the
    attacker gets –2/–0 for this attack."""

    def test_lof_67_use_force_debuffs_attacker(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, AutoResolveEffects, compute_power)
        state = _make_state()
        chirrut = _place(state, "P0", _get_card(repo, "LOF", "67"), "ground")
        state.player_by_id("P0").has_force_token = True
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, attacker, chirrut)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        while any(isinstance(a, AutoResolveEffects) for a in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert compute_power(state, _find_instance(state, attacker.instance_id)) == 1
        assert not state.player_by_id("P0").has_force_token

    def test_lof_67_decline_keeps_token(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger, compute_power
        state = _make_state()
        chirrut = _place(state, "P0", _get_card(repo, "LOF", "67"), "ground")
        state.player_by_id("P0").has_force_token = True
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, attacker, chirrut)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").has_force_token
        assert compute_power(state, _find_instance(state, attacker.instance_id)) == 3

    def test_lof_67_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        chirrut = _place(state, "P0", _get_card(repo, "LOF", "67"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, attacker, chirrut)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ── darth-maul:05 — New primitive: force-token (reuses qui-gon-jinn:06) ────────


class TestAcolyteOfTheBeyond:
    """LOF_129 — On Attack/When Defeated: create your Force token."""

    def test_lof_129_on_attack_creates_token(self, repo):
        state = _make_state()
        acolyte = _place(state, "P0", _get_card(repo, "LOF", "129"), "ground")
        assert not state.player_by_id("P0").has_force_token
        state = _fire_on_attack(state, acolyte)
        assert state.player_by_id("P0").has_force_token

    def test_lof_129_when_defeated_creates_token(self, repo):
        state = _make_state()
        acolyte = _place(state, "P0", _get_card(repo, "LOF", "129"), "ground")
        state = _fire_when_defeated(state, acolyte)
        assert state.player_by_id("P0").has_force_token


class TestSavageOpress:
    """LOF_137 — When Played/When Defeated: You may use the Force. If you don't,
    deal 9 damage to your base."""

    def test_lof_137_use_force_avoids_base_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, UseForceOption
        state = _make_state()
        opress = _place(state, "P0", _get_card(repo, "LOF", "137"), "ground")
        state.player_by_id("P0").has_force_token = True
        state = _fire_when_played(state, opress)
        assert state.pending_decisions[-1].kind == "use_force"
        force = next(a for a in legal_actions(state)
                     if isinstance(a, UseForceOption) and a.option == "force")
        state = apply(state, force)
        assert not state.player_by_id("P0").has_force_token  # spent
        assert state.player_by_id("P0").base_instance.damage == 0  # penalty avoided

    def test_lof_137_decline_deals_9_to_own_base(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineUseForce
        state = _make_state()
        opress = _place(state, "P0", _get_card(repo, "LOF", "137"), "ground")
        state.player_by_id("P0").has_force_token = True
        state = _fire_when_played(state, opress)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineUseForce))
        state = apply(state, decline)
        assert state.player_by_id("P0").has_force_token  # token kept
        assert state.player_by_id("P0").base_instance.damage == 9

    def test_lof_137_no_token_deals_9_inline(self, repo):
        """With no Force token the player cannot use the Force ("you don't"), so the
        9 damage lands inline with no decision pushed."""
        state = _make_state()
        opress = _place(state, "P0", _get_card(repo, "LOF", "137"), "ground")
        state = _fire_when_played(state, opress)
        assert not state.pending_decisions
        assert state.player_by_id("P0").base_instance.damage == 9

    def test_lof_137_when_defeated_also_triggers(self, repo):
        state = _make_state()
        opress = _place(state, "P0", _get_card(repo, "LOF", "137"), "ground")
        state = _fire_when_defeated(state, opress)
        assert state.player_by_id("P0").base_instance.damage == 9


class TestInfusedBrawler:
    """LOF_156 — When Played: you may use the Force for 2 Experience on this unit.
    When this unit completes an attack: defeat an Experience token on it."""

    def test_lof_156_use_force_gives_2_experience(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, AutoResolveEffects
        state = _make_state()
        brawler = _place(state, "P0", _get_card(repo, "LOF", "156"), "ground")
        state.player_by_id("P0").has_force_token = True
        state = _fire_when_played(state, brawler)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        while any(isinstance(a, AutoResolveEffects) for a in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert not state.player_by_id("P0").has_force_token
        assert _experience_count(_find_instance(state, brawler.instance_id)) == 2

    def test_lof_156_decline_keeps_token_no_experience(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        brawler = _place(state, "P0", _get_card(repo, "LOF", "156"), "ground")
        state.player_by_id("P0").has_force_token = True
        state = _fire_when_played(state, brawler)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        assert state.player_by_id("P0").has_force_token
        assert _experience_count(_find_instance(state, brawler.instance_id)) == 0

    def test_lof_156_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        brawler = _place(state, "P0", _get_card(repo, "LOF", "156"), "ground")
        state = _fire_when_played(state, brawler)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions

    def test_lof_156_completes_attack_defeats_one_experience(self, repo):
        from swu.engine.tokens import attach_token
        state = _make_state()
        brawler = _place(state, "P0", _get_card(repo, "LOF", "156"), "ground")
        ps = state.player_by_id("P0")
        attach_token(state, ps, brawler, "Experience")
        attach_token(state, ps, brawler, "Experience")
        assert _experience_count(_find_instance(state, brawler.instance_id)) == 2
        state = _fire_attack_ends(state, brawler)
        assert _experience_count(_find_instance(state, brawler.instance_id)) == 1


class TestKyloRen:
    """LOF_229 — When you play an upgrade on this unit: you may use the Force; if
    you do, draw a card."""

    def _stock_deck(self, state, repo, owner="P0", n=3):
        from swu.engine.state import CardInstance, Zone
        import uuid
        for _ in range(n):
            state.player_by_id(owner).deck.append(CardInstance(
                f"{owner}_deck_{uuid.uuid4().hex[:6]}", _get_card(repo, "SOR", "46"),
                owner, Zone.DECK))

    def test_lof_229_use_force_draws_a_card(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "LOF", "229"), "ground")
        state.player_by_id("P0").has_force_token = True
        self._stock_deck(state, repo)
        up = _attach_upgrade_directly(state, kylo, _get_card(repo, "SOR", "53"), "P0")
        hand_before = len(state.player_by_id("P0").hand)
        state = _fire_card_played(state, up)
        from swu.engine.actions import AutoResolveEffects
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        while any(isinstance(a, AutoResolveEffects) for a in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert not state.player_by_id("P0").has_force_token
        assert len(state.player_by_id("P0").hand) == hand_before + 1

    def test_lof_229_upgrade_on_other_unit_not_offered(self, repo):
        """An upgrade played on a DIFFERENT friendly unit does not trigger Kylo
        (the on_self filter)."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "LOF", "229"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = True
        up = _attach_upgrade_directly(state, other, _get_card(repo, "SOR", "53"), "P0")
        state = _fire_card_played(state, up)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions

    def test_lof_229_not_offered_without_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "LOF", "229"), "ground")
        up = _attach_upgrade_directly(state, kylo, _get_card(repo, "SOR", "53"), "P0")
        state = _fire_card_played(state, up)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestDarthTyranus:
    """LOF_231 — While the Force is with you, this unit gains Ambush (Shielded is
    genuinely possessed)."""

    def test_lof_231_ambush_conditional_on_force_token(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tyranus = _place(state, "P0", _get_card(repo, "LOF", "231"), "ground")
        assert not has_keyword(state, tyranus, Keyword.AMBUSH)
        state.player_by_id("P0").has_force_token = True
        assert has_keyword(state, tyranus, Keyword.AMBUSH)

    def test_lof_231_printed_ambush_stripped_shielded_kept(self, repo):
        """The data mis-tags a printed Ambush (owned by the conditional ability);
        the sanitiser strips it but keeps the genuinely-possessed Shielded."""
        card = _get_card(repo, "LOF", "231")
        names = {getattr(k, "name", k) for k in card.keywords}
        assert "Ambush" not in names
        assert "Shielded" in names


# ── Reprint-duplicate encode (Stage 4 of docs/reprint_duplicates_plan.md) ─────

class TestAsajjVentress:
    """LOF_165 — "When Played/On Attack: Give another friendly Force unit +2/+0
    for this phase." (sib P25_84)."""

    def test_lof_165_when_played_buffs_another_force_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "LOF", "165"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "49"), "ground")  # Obi-Wan, Force 4/6
        state = _fire_when_played(state, asajj)
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, tgt)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == 6  # 4 + 2

    def test_lof_165_only_other_force_units_targetable(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "LOF", "165"), "ground")
        force_ally = _place(state, "P0", _get_card(repo, "SOR", "49"), "ground")  # Force
        non_force = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Force
        state = _fire_when_played(state, asajj)
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert force_ally.instance_id in tids
        assert non_force.instance_id not in tids
        assert asajj.instance_id not in tids  # "another" — not_self

    def test_lof_165_on_attack_buffs_force_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        asajj = _place(state, "P0", _get_card(repo, "LOF", "165"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "49"), "ground")
        state = _fire_on_attack(state, asajj)
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == ally.instance_id)
        state = apply(state, tgt)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == 6


# ── Reprint sweep Stage 4 Batch 2 canonical encodes ──────────────────────────

class TestYaddle:
    """LOF_45 — Yaddle (Restore 1): "On Attack: Each other friendly Jedi unit gains
    Restore 1 for this phase." (reprint canonical; sib P25_143)."""

    def test_lof_45_grants_restore_to_other_jedi(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        yaddle = _place(state, "P0", _get_card(repo, "LOF", "45"), "ground")
        jedi = _place(state, "P0", _get_card(repo, "LOF", "145"), "ground")   # Jedi, no innate Restore
        non_jedi = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Jedi
        assert keyword_value(state, jedi, Keyword.RESTORE) == 0
        _fire_on_attack(state, yaddle)
        assert keyword_value(state, jedi, Keyword.RESTORE) == 1       # granted
        assert keyword_value(state, non_jedi, Keyword.RESTORE) == 0   # trait filter

    def test_lof_45_keeps_own_printed_restore(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        yaddle = _place(state, "P0", _get_card(repo, "LOF", "45"), "ground")
        # Yaddle's own printed Restore 1 is untouched (not_self on the grant).
        assert keyword_value(state, yaddle, Keyword.RESTORE) == 1


class TestCrushingBlow:
    """LOF_77 — Event: "Defeat a non-leader unit that costs 2 or less." (reprint
    canonical; sib LOFP_3)."""

    def test_lof_77_defeats_only_cheap_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard, ChooseTarget
        cheap = _place(state := _make_state(), "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 1
        pricey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        blow_ci = _put_in_hand(state, "P0", _get_card(repo, "LOF", "77"))
        _give_resources(state, "P0", 10)

        state = apply(state, PlayCard(blow_ci.instance_id))
        choices = [a for a in legal_actions(state) if isinstance(a, ChooseTarget) and a.target_id]
        tids = {a.target_id for a in choices}
        assert cheap.instance_id in tids
        assert pricey.instance_id not in tids   # cost_max=2 excludes the 4-cost unit
        state = apply(state, next(a for a in choices if a.target_id == cheap.instance_id))
        assert _find_instance(state, cheap.instance_id) is None
        assert _find_instance(state, pricey.instance_id) is not None

    def test_lof_77_fizzles_with_no_eligible_unit(self, repo):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4 only
        blow_ci = _put_in_hand(state, "P0", _get_card(repo, "LOF", "77"))
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(blow_ci.instance_id))
        assert not state.pending_decisions   # nothing ≤2 → clean fizzle


# ══════════════════════════════════════════════════════════════════════════════
# Reprint-duplicate sweep (Stage 4) — shipped-set LOF canonicals
# ══════════════════════════════════════════════════════════════════════════════

from tests.test_sor_cards import _defeat_and_fire  # noqa: E402


class TestHK47:
    """LOF_130 — HK-47: "When an enemy unit is defeated: Deal 1 damage to its
    controller's base." (sibs J25_12, P25_123, P25_135, P26_41, P26_53)."""

    def test_lof_130_damages_enemy_base_on_enemy_defeat(self, repo):
        # Real _defeat_unit removes the unit from its arena LIST but keeps ci.zone
        # = the arena zone while UnitDefeated fires, so the kind="unit" observer
        # filter still matches.  _fire_when_defeated leaves the unit in-arena,
        # faithfully reproducing that fire-time zone (the Hevy TWI_164 pattern).
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "130"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, enemy)
        assert not state.pending_decisions          # resolves inline
        assert state.player_by_id("P1").base_instance.damage == 1
        assert state.player_by_id("P0").base_instance.damage == 0

    def test_lof_130_ignores_friendly_defeat(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "130"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, friendly)
        # A friendly defeat must NOT fire the enemy-filtered observer.
        assert state.player_by_id("P1").base_instance.damage == 0
        assert state.player_by_id("P0").base_instance.damage == 0


class TestLothCat:
    """LOF_207 — Loth-Cat: "When Played/When Defeated: You may exhaust a ground
    unit." (sib LOFP_18)."""

    def test_lof_207_when_played_exhausts_ground_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        cat = _place(state, "P0", _get_card(repo, "LOF", "207"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, cat)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        tgt = next(a for a in legal_actions(state)
                   if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, tgt)
        assert _find_instance(state, enemy.instance_id).exhausted is True

    def test_lof_207_when_defeated_only_ground_targetable(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        cat = _place(state, "P0", _get_card(repo, "LOF", "207"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _defeat_and_fire(state, cat, "P0")
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert ground.instance_id in tids
        assert space.instance_id not in tids

    def test_lof_207_auto_declines_when_defeated_with_no_ground_unit(self, repo):
        # On the WhenDefeated firing Loth-Cat has left play, so with only a space
        # unit on the board there is no legal ground target → the optional trigger
        # auto-declines (no prompt).  (On the WhenPlayed firing Loth-Cat is itself
        # a ground unit, so the trigger is always offered.)
        state = _make_state()
        cat = _place(state, "P0", _get_card(repo, "LOF", "207"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "space")  # only a space unit
        state = _defeat_and_fire(state, cat, "P0")
        assert not state.pending_decisions   # no legal ground target → no prompt


class TestHK87AssassinDroid:
    """LOF_235 — HK-87 Assassin Droid: "When Defeated: Deal 2 damage to each ground
    unit." (sib LOFP_19)."""

    def test_lof_235_damages_all_ground_units_both_sides(self, repo):
        state = _make_state()
        hk = _place(state, "P0", _get_card(repo, "LOF", "235"), "ground")
        friendly_g = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_g = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _defeat_and_fire(state, hk, "P0")   # HK-87 leaves play first
        assert not state.pending_decisions          # EACH_IN_PLAY resolves inline
        assert _find_instance(state, friendly_g.instance_id).damage == 2
        assert _find_instance(state, enemy_g.instance_id).damage == 2
        assert _find_instance(state, space.instance_id).damage == 0


# ── Reprint-duplicate sweep (Stage 4) — Batch 4 ───────────────────────────────

class TestJediHolocron:
    """LOF_51 — Jedi Holocron (Upgrade): "Attached unit gains: 'On Attack: You may
    heal 3 damage from another unit.'" (sib P25_13)."""

    def test_lof_51_heals_another_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")  # Force host
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "51"), "P0")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 3
        state = _fire_on_attack(state, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        tids = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert host.instance_id not in tids       # "another" — not_self
        state = apply(state, ChooseTarget(hurt.instance_id))
        assert _find_instance(state, hurt.instance_id).damage == 0

    def test_lof_51_may_decline(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "51"), "P0")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 2
        state = _fire_on_attack(state, host)
        dec = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, dec)
        assert _find_instance(state, hurt.instance_id).damage == 2   # unhealed


class TestCorruptedSaber:
    """LOF_187 — Corrupted Saber (Upgrade): "If attached unit is a Force unit, it
    gains: 'On Attack: The defender gets -2/-0 for this attack.'" (sib P25_110)."""

    def test_lof_187_force_host_debuffs_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "38"), "ground")  # Force
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "187"), "P0")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = compute_power(state, defender)
        state = _fire_on_attack(state, host, defender)
        assert not state.pending_decisions   # mandatory fixed=DEFENDER resolves inline
        assert compute_power(state, _find_instance(state, defender.instance_id)) == before - 2

    def test_lof_187_non_force_host_grants_nothing(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Force
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "187"), "P0")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        before = compute_power(state, defender)
        state = _fire_on_attack(state, host, defender)
        assert not state.pending_decisions
        assert compute_power(state, _find_instance(state, defender.instance_id)) == before


class TestDarthRevansLightsabers:
    """LOF_238 — Darth Revan's Lightsabers (Upgrade): "If attached unit is a Sith,
    it gains Grit." (sib P25_19)."""

    def test_lof_238_sith_host_gains_grit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        sith = _place(state, "P0", _get_card(repo, "LOF", "129"), "ground")  # Sith
        _attach_upgrade_directly(state, sith, _get_card(repo, "LOF", "238"), "P0")
        assert has_keyword(state, sith, Keyword.GRIT)

    def test_lof_238_non_sith_host_no_grit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Sith, no native Grit
        assert not has_keyword(state, host, Keyword.GRIT)   # sanity: no printed Grit
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "238"), "P0")
        assert not has_keyword(state, host, Keyword.GRIT)   # not conferred (host not Sith)


class TestFlightOfTheInquisitor:
    """LOF_240 — Flight of the Inquisitor (Event): "You may return a Force unit and
    a Lightsaber upgrade from your discard pile to your hand." (sib LOFP_20)."""

    def test_lof_240_returns_force_unit_and_lightsaber(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectDiscardCard, FinishReturnFromDiscard)
        state = _make_state()
        # seed the discard BEFORE playing (the CustomEffect snapshots candidates)
        force_id = _put_in_discard(state, "P0", _get_card(repo, "LOF", "38")).instance_id
        saber_id = _put_in_discard(state, "P0", _get_card(repo, "LOF", "187")).instance_id
        state, _ = _play_event_from_hand(state, repo, "LOF", "240")
        # drain: pick each SelectDiscardCard offered (return them), then Finish
        guard = 0
        while state.pending_decisions and guard < 20:
            guard += 1
            acts = legal_actions(state)
            sel = [a for a in acts if isinstance(a, SelectDiscardCard)]
            if sel:
                state = apply(state, sel[0])
            else:
                state = apply(state, next(a for a in acts
                                          if isinstance(a, FinishReturnFromDiscard)))
        hand_ids = {c.instance_id for c in state.player_by_id("P0").hand}
        assert force_id in hand_ids
        assert saber_id in hand_ids

    def test_lof_240_fizzles_with_empty_discard(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "LOF", "240")
        assert not state.pending_decisions   # nothing eligible → no prompt


# ── Reprint-duplicate batch 6 (2026-07-08) ────────────────────────────────────


class TestEzraBridgerLOF46:
    """LOF_46 — On Attack: You may give an Experience token to another Creature or
    Spectre unit (the ``creature_or_spectre`` predicate; Ezra himself is Spectre)."""

    def test_lof_46_gives_experience_to_spectre_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        ezra = _place(state, "P0", _get_card(repo, "LOF", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "LOF", "46"), "ground")  # Spectre
        state = _fire_on_attack(state, ezra)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(other.instance_id))
        assert _experience_count(_find_instance(state, other.instance_id)) == 1

    def test_lof_46_auto_declines_with_no_other_creature_or_spectre(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        ezra = _place(state, "P0", _get_card(repo, "LOF", "46"), "ground")
        # A non-Creature/Spectre friendly (SOR_46) is not a legal target, and "another"
        # excludes Ezra himself → optional trigger auto-declines.
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, ezra)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestQuinlanVosLOF163:
    """LOF_163 — On Attack: If this unit has 6 or more power, you may deal 2 damage
    to an enemy base (the ``SOURCE_POWER_MIN(6)`` trigger gate)."""

    def _give_experience(self, state, ci, n):
        from swu.engine.tokens import attach_token
        ps = state.player_by_id(ci.owner_id)
        for _ in range(n):
            attach_token(state, ps, ci, "Experience")

    def test_lof_163_deals_2_to_base_at_power_6(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        quin = _place(state, "P0", _get_card(repo, "LOF", "163"), "ground")  # 4/5
        self._give_experience(state, quin, 2)  # +2/+2 → power 6
        base_id = state.player_by_id("P1").base_instance.instance_id
        state = _fire_on_attack(state, quin)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(base_id))
        assert state.player_by_id("P1").base_instance.damage == 2

    def test_lof_163_not_offered_below_power_6(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        quin = _place(state, "P0", _get_card(repo, "LOF", "163"), "ground")  # 4/5, power 4
        state = _fire_on_attack(state, quin)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions
        assert state.player_by_id("P1").base_instance.damage == 0


# ── Stage-4 reprint sweep (Batch 7) ───────────────────────────────────────────

def _zero_upgrade(name="Filler Upgrade"):
    """A minimal 0/0 Upgrade def (no stat bonus), so an attach changes only the
    upgrade *count* (for Axe Woves LOF_62's per-upgrade scaling)."""
    from swu.cards.models import Upgrade
    return Upgrade(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="UP", name=name, subtitle=None, type="Upgrade", rarity="Common",
        is_unique=False, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None, aspects=(), keywords=(), traits=(), arenas=(),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=1, upgrade_power=0, upgrade_hp=0,
    )


class TestAxeWovesLOF62:
    """LOF_62 — Shielded + "This unit gets +1/+1 for each upgrade on him"
    (self-scaling StatBonus, count=``upgrades_on_self``)."""

    def test_lof_62_no_upgrades_base_stats(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        axe = _place(state, "P0", _get_card(repo, "LOF", "62"), "ground")  # 2/2
        assert compute_power(state, axe) == 2
        assert compute_hp(state, axe) == 2

    def test_lof_62_scales_with_upgrade_count(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        axe = _place(state, "P0", _get_card(repo, "LOF", "62"), "ground")  # 2/2
        _attach_upgrade_directly(state, axe, _zero_upgrade("A"), "P0")
        assert compute_power(state, axe) == 3  # 2 + 1×1
        assert compute_hp(state, axe) == 3
        _attach_upgrade_directly(state, axe, _zero_upgrade("B"), "P0")
        assert compute_power(state, axe) == 4  # 2 + 1×2
        assert compute_hp(state, axe) == 4


class TestGrandInquisitorLOF132:
    """LOF_132 — Hidden + Raid 1 (kept) + "Other friendly Inquisitor units gain
    Hidden" (a ConstantAbility grant read by ``has_keyword``)."""

    def test_lof_132_grants_hidden_to_other_inquisitor(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        gi = _place(state, "P0", _get_card(repo, "LOF", "132"), "ground")
        # A second Inquisitor is a legal grantee (it also has its own printed
        # Hidden, so the positive assertion just confirms the grant reaches it).
        other = _place(state, "P0", _get_card(repo, "LOF", "132"), "ground")
        assert has_keyword(state, other, Keyword.HIDDEN)
        # A friendly NON-Inquisitor (SOR_46, no Hidden) must NOT be granted it —
        # proving the trait filter on the grant.
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert not has_keyword(state, plain, Keyword.HIDDEN)

    def test_lof_132_keeps_own_printed_keywords(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        gi = _place(state, "P0", _get_card(repo, "LOF", "132"), "ground")
        assert has_keyword(state, gi, Keyword.HIDDEN)   # printed, kept by sanitiser
        assert keyword_value(state, gi, Keyword.RAID) == 1


# ── Stage-4 reprint sweep (Batch 8) ───────────────────────────────────────────
# LOF_70 Anakin Skywalker, LOF_234 Darth Malak, LOF_40 Kylo Ren's Lightsaber.


class TestAnakinSkywalkerLOF70:
    """When Played: If there is a Heroism/Villainy card in your discard pile, you
    may give a unit -3/-3 for this phase (two aspect-gated optional triggers)."""

    def test_lof_70_heroism_discard_debuffs_unit(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                         ChooseTarget, compute_power, compute_hp)
        state = _make_state()
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "45"))  # Heroism card
        anakin = _place(state, "P0", _get_card(repo, "LOF", "70"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")  # 9/9
        state = _fire_when_played(state, anakin)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(target.instance_id))
        _, t = state.find_instance(target.instance_id)
        assert compute_power(state, t) == 6   # 9 - 3
        assert compute_hp(state, t) == 6       # 9 - 3

    def test_lof_70_not_offered_with_empty_discard(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        anakin = _place(state, "P0", _get_card(repo, "LOF", "70"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "88"), "ground")
        state = _fire_when_played(state, anakin)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestDarthMalakLOF234:
    """When Played: If you control a Sith leader unit, you may ready this unit."""

    def test_lof_234_readies_with_sith_leader_unit(self, repo):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        AutoResolveEffects)
        state = _make_state()
        sith_leader = _place(state, "P0", _get_card(repo, "SOR", "10"), "ground")  # Darth Vader
        sith_leader.deployed = True
        malak = _place(state, "P0", _get_card(repo, "LOF", "234"), "ground")
        malak.exhausted = True  # enters exhausted as a non-leader unit
        state = _fire_when_played(state, malak)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, AutoResolveEffects())  # ReadyCard(fixed=SELF) resolves inline
        _, m = state.find_instance(malak.instance_id)
        assert m.exhausted is False

    def test_lof_234_not_offered_without_sith_leader(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        malak = _place(state, "P0", _get_card(repo, "LOF", "234"), "ground")
        malak.exhausted = True
        state = _fire_when_played(state, malak)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestKyloRensLightsaberLOF40:
    """Upgrade: If attached unit is a Force unit, it can't be exhausted by enemy
    card abilities."""

    def _exhaust(self, state, source_ci, target_id):
        from swu.abilities.resolver import execute_effect
        from swu.abilities.registry import ExhaustCard, TargetSpec
        return execute_effect(
            state, ExhaustCard(TargetSpec(controller="any", kind="unit")),
            source_ci, target_id, {})

    def test_lof_40_force_host_immune_to_enemy_exhaust(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "45"), "ground")  # Yoda, Force
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "40"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._exhaust(state, enemy, host.instance_id)
        _, h = state.find_instance(host.instance_id)
        assert h.exhausted is False   # enemy ability can't exhaust a Force host

    def test_lof_40_non_force_host_can_be_exhausted(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "229"), "ground")  # not Force
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "40"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = self._exhaust(state, enemy, host.instance_id)
        _, h = state.find_instance(host.instance_id)
        assert h.exhausted is True    # protection gated on the Force trait only

    def test_lof_40_friendly_exhaust_not_blocked(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "45"), "ground")  # Force host
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "40"), "P0")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = self._exhaust(state, friendly, host.instance_id)
        _, h = state.find_instance(host.instance_id)
        assert h.exhausted is True    # only *enemy* abilities are blocked


class TestDarthVaderLOF37:
    """LOF_37 — Darth Vader (5/6): "When Played: Give a Shield token to a friendly
    unit and to an enemy unit.  On Attack: Defeat an enemy unit with a Shield token
    on it.\""""

    def test_lof_37_when_played_shields_friendly_and_enemy(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        vader = _place(state, "P0", _get_card(repo, "LOF", "37"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_when_played(state, vader)
        # First effect: friendly Shield (Vader himself is a legal friendly target).
        state = apply(state, ChooseTarget(vader.instance_id))
        # Second effect: enemy Shield.
        state = apply(state, ChooseTarget(enemy.instance_id))
        _, v_after = state.find_instance(vader.instance_id)
        _, e_after = state.find_instance(enemy.instance_id)
        assert _shield_count(v_after) == 1
        assert _shield_count(e_after) == 1

    def test_lof_37_on_attack_defeats_only_shielded_enemy(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine import tokens
        state = _make_state()
        vader = _place(state, "P0", _get_card(repo, "LOF", "37"), "ground")
        shielded = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tokens.attach_token(state, state.player_by_id("P1"), shielded, "Shield")
        state = _fire_on_attack(state, vader)
        offered = {a.target_id for a in legal_actions(state) if isinstance(a, ChooseTarget)}
        assert offered == {shielded.instance_id}
        assert plain.instance_id not in offered
        state = apply(state, ChooseTarget(shielded.instance_id))
        assert all(u.instance_id != shielded.instance_id
                   for u in state.player_by_id("P1").ground_arena)

    def test_lof_37_on_attack_fizzles_without_shielded_enemy(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        vader = _place(state, "P0", _get_card(repo, "LOF", "37"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # no shield
        state = _fire_on_attack(state, vader)
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


# ── Stage-4 reprint sweep (batch 11) ─────────────────────────────────────────

class TestInquisitorsLightsaber:
    """LOF_90 — Upgrade: attached unit gains "While attacking a Force unit,
    this unit gets +2/+0." (GrantedAbility OnAttack this-attack buff.)"""

    def test_lof_90_buffs_host_attacking_force_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "90"), "P0")
        force_def = _place(state, "P1", _get_card(repo, "LOF", "196"), "ground")  # Force
        base = compute_power(state, host, is_attacking=True)
        state = _fire_on_attack(state, host, force_def)
        _, h = state.find_instance(host.instance_id)
        assert compute_power(state, h, is_attacking=True) == base + 2

    def test_lof_90_no_buff_vs_non_force_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "90"), "P0")
        plain_def = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # Rebel
        base = compute_power(state, host, is_attacking=True)
        state = _fire_on_attack(state, host, plain_def)
        _, h = state.find_instance(host.instance_id)
        assert compute_power(state, h, is_attacking=True) == base

    def test_lof_90_base_attack_is_noop(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "90"), "P0")
        base = compute_power(state, host, is_attacking=True)
        state = _fire_on_attack(state, host, None)  # attacking a base
        _, h = state.find_instance(host.instance_id)
        assert compute_power(state, h, is_attacking=True) == base


class TestGroguLOF:
    """LOF_246 — Action [Exhaust]: Heal up to 2 from a unit; deal that much to a
    unit."""

    def test_lof_246_heal_then_deal_that_much(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        grogu = _place(state, "P0", _get_card(repo, "LOF", "246"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friendly.damage = 2
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == grogu.instance_id)
        state = apply(state, use)
        heal = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, heal)
        deal = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, deal)
        _, f = state.find_instance(friendly.instance_id)
        _, e = state.find_instance(enemy.instance_id)
        _, g = state.find_instance(grogu.instance_id)
        assert f.damage == 0     # healed the 2 damage
        assert e.damage == 2     # dealt that much
        assert g.exhausted       # paid its own exhaustion

    def test_lof_246_heal_undamaged_deals_zero(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, ChooseTarget
        state = _make_state()
        grogu = _place(state, "P0", _get_card(repo, "LOF", "246"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # undamaged
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == grogu.instance_id)
        state = apply(state, use)
        heal = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == friendly.instance_id)
        state = apply(state, heal)
        deal = next(a for a in legal_actions(state)
                    if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, deal)
        _, e = state.find_instance(enemy.instance_id)
        assert e.damage == 0     # nothing healed → nothing dealt


class TestConstructedLightsaber:
    """LOF_261 — Upgrade: Heroism→Restore 2, Villainy→Raid 2, neither→Sentinel."""

    def test_lof_261_heroism_host_gains_restore_2(self, repo):
        from swu.engine.keywords import keyword_value, has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Vigilance+Heroism
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "261"), "P0")
        _, h = state.find_instance(host.instance_id)
        assert keyword_value(state, h, Keyword.RESTORE) == 2
        assert keyword_value(state, h, Keyword.RAID) == 0
        assert not has_keyword(state, h, Keyword.SENTINEL)

    def test_lof_261_villainy_host_gains_raid_2(self, repo):
        from swu.engine.keywords import keyword_value, has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "233"), "ground")  # Villainy
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "261"), "P0")
        _, h = state.find_instance(host.instance_id)
        assert keyword_value(state, h, Keyword.RAID) == 2
        assert keyword_value(state, h, Keyword.RESTORE) == 0
        assert not has_keyword(state, h, Keyword.SENTINEL)

    def test_lof_261_neutral_host_gains_sentinel(self, repo):
        from swu.engine.keywords import keyword_value, has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "63"), "ground")  # Vigilance only
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "261"), "P0")
        _, h = state.find_instance(host.instance_id)
        assert has_keyword(state, h, Keyword.SENTINEL)
        assert keyword_value(state, h, Keyword.RESTORE) == 0
        assert keyword_value(state, h, Keyword.RAID) == 0


def _set_base(state, owner, card_def):
    """Replace ``owner``'s base with a specific Base card_def (returns the CI)."""
    import uuid
    from swu.engine.state import CardInstance, Zone
    from swu.cards.models import Base
    ps = state.player_by_id(owner)
    ps.base_zone = [c for c in ps.base_zone if not isinstance(c.card_def, Base)]
    ci = CardInstance(f"{owner}_base_{uuid.uuid4().hex[:4]}", card_def, owner, Zone.BASE_ZONE)
    ps.base_zone.append(ci)
    return ci


class TestReyLOF148:
    """LOF_148 — Rey, "With Palpatine's Power": the batch-16 WhenYouDraw drawn-card
    observer.  "When you draw this card during the action phase: If you control an
    Aggression leader or base, you may reveal it; if you do, deal 2 to a unit and 2
    to a base."  Fires while Rey sits in the drawer's hand."""

    def _draw_rey(self, repo, state):
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        rey_ci = _push_deck_top(state, "P0", _get_card(repo, "LOF", "148"))
        _draw_cards(state, state.player_by_id("P0"), 1)   # Rey → hand + ledger
        return _fire_draw_observers(state), rey_ci

    def test_lof_148_draw_reveals_and_deals_2_and_2(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "SOR", "25"))   # Tarkintown = Aggression
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7, survives 2
        enemy_base = state.player_by_id("P1").base_instance
        state, rey_ci = self._draw_rey(repo, state)
        # optional trigger offered while Rey is in hand
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc, "Rey's WhenYouDraw trigger should be offered"
        state = apply(state, acc[0])
        # deal 2 to the enemy unit, then 2 to the enemy base
        state = apply(state, ChooseTarget(enemy.instance_id))
        state = apply(state, ChooseTarget(enemy_base.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2
        assert state.player_by_id("P1").base_instance.damage == 2
        # Rey stays in hand (the "reveal" is a no-op)
        assert any(c.instance_id == rey_ci.instance_id
                   for c in state.player_by_id("P0").hand)

    def test_lof_148_no_aggression_leader_or_base_not_offered(self, repo):
        # The synthetic base has no aspects → the gate fails → no trigger, no damage.
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state, _rey = self._draw_rey(repo, state)
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 0

    def test_lof_148_decline_deals_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "SOR", "25"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state, _rey = self._draw_rey(repo, state)
        dec = [a for a in legal_actions(state) if isinstance(a, DeclineTrigger)]
        assert dec
        state = apply(state, dec[0])
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 0

    def test_lof_148_regroup_draw_not_offered(self, repo):
        # "during the action phase" — a REGROUP draw is ledgered (tagged with its
        # phase, for Axe Woves ASH_169) but the MATCHER admits only ACTION ones, so
        # drawing Rey in REGROUP still offers nothing.
        from swu.engine.state import Phase
        from swu.engine.actions import _draw_cards, _fire_draw_observers
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "SOR", "25"))
        _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "LOF", "148"))
        state.phase = Phase.REGROUP
        _draw_cards(state, state.player_by_id("P0"), 1)
        assert [e["phase"] for e in state.game_memory.action_phase_draws] == ["REGROUP"]
        state = _fire_draw_observers(state)
        assert not state.pending_decisions


class TestYodaLOF101:
    """LOF_101 — Yoda, "My Ally is the Force": the batch-17 WhenYouUseForce observer.
    "When Played: You may use the Force. If you do, heal 5 damage from a base.  When
    you use the Force: You may deal damage to a unit equal to twice the number of
    units you control." """

    def _drain_auto(self, state):
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        while any(isinstance(a, AutoResolveEffects) for a in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        return state

    def test_lof_101_when_played_use_force_heals_and_triggers_second(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        yoda = _place(state, "P0", _get_card(repo, "LOF", "101"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 2nd unit → 2 units
        state.player_by_id("P0").has_force_token = True
        base = state.player_by_id("P0").base_instance
        base.damage = 6
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        # Fire Yoda's WhenPlayed and accept "use the Force"
        state = _fire_when_played(state, yoda)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = self._drain_auto(state)   # runs the CustomEffect → spends token, heals
        assert not state.player_by_id("P0").has_force_token
        assert state.player_by_id("P0").base_instance.damage == 1   # 6 − 5
        # The spend drained at settle → the WhenYouUseForce observer is now offered
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc, "second ability (WhenYouUseForce) should be offered after using the Force"
        state = apply(state, acc[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        # twice the number of units P0 controls (Yoda + the 2nd unit = 2) → 4
        assert _find_instance(state, enemy.instance_id).damage == 4

    def test_lof_101_decline_when_played_no_force_used(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        yoda = _place(state, "P0", _get_card(repo, "LOF", "101"), "ground")
        state.player_by_id("P0").has_force_token = True
        base = state.player_by_id("P0").base_instance
        base.damage = 6
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, yoda)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineTrigger)))
        # token kept, base not healed, second ability never fires
        assert state.player_by_id("P0").has_force_token
        assert state.player_by_id("P0").base_instance.damage == 6
        assert state.game_memory.force_uses == []
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 0

    def test_lof_101_use_force_by_any_route_fires_observer(self, repo):
        # Spending the Force by any route (here the spend_force_token chokepoint,
        # standing in for an ability cost / the use_force decision) triggers the
        # observer — and the magnitude is 2× the units the controller has.
        from swu.engine.actions import (
            spend_force_token, _fire_force_observers,
            legal_actions, apply, AcceptTrigger, ChooseTarget)
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "101"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3 units total
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        assert spend_force_token(state, state.player_by_id("P0")) is True
        assert state.game_memory.force_uses == ["P0"]
        state = _fire_force_observers(state)
        acc = [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]
        assert acc
        state = apply(state, acc[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 6   # 2 × 3 units

    def test_lof_101_second_ability_decline_deals_nothing(self, repo):
        from swu.engine.actions import (
            spend_force_token, _fire_force_observers,
            legal_actions, apply, DeclineTrigger)
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "101"), "ground")
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spend_force_token(state, state.player_by_id("P0"))
        state = _fire_force_observers(state)
        dec = [a for a in legal_actions(state) if isinstance(a, DeclineTrigger)]
        assert dec
        state = apply(state, dec[0])
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 0


class TestQuiGonJinnLOF200:
    """LOF_200 — Ambush. "When Defeated: You may choose a non-leader ground unit.
    Its owner puts it on the top or bottom of their deck." The new put_on_deck
    multi-decider decision kind (the chosen unit's OWNER orders their own deck)."""

    def _defeat_and_choose(self, state, qg, target):
        from swu.engine.actions import (legal_actions, apply, AcceptTrigger,
                                        ChooseTarget)
        state = _defeat_and_fire(state, qg, "P0")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(target.instance_id))
        return state

    def _drain(self, state):
        """Drain the buried (now-empty) resolve_effects decision the push helper
        left behind — real apply() runs this to quiescence automatically."""
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        while state.pending_decisions:
            auto = [a for a in legal_actions(state)
                    if isinstance(a, AutoResolveEffects)]
            if not auto:
                break
            state = apply(state, auto[0])
        return state

    def test_lof_200_puts_enemy_ground_unit_on_top(self, repo):
        from swu.engine.actions import legal_actions, apply, PutOnDeckTop
        state = _make_state()
        qg = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "LOF", "193"), "ground")
        enemy.damage = 2
        enemy.exhausted = True
        deck_before = len(state.player_by_id("P1").deck)
        state = self._defeat_and_choose(state, qg, enemy)
        # the OWNER (P1) now decides top vs bottom
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PutOnDeckTop)))
        state = self._drain(state)
        p1 = state.player_by_id("P1")
        assert _find_instance(state, enemy.instance_id) is None      # left play
        assert p1.deck[0].instance_id == enemy.instance_id           # on TOP (deck[0])
        assert len(p1.deck) == deck_before + 1
        # a card out of play is a clean, face-down card
        assert p1.deck[0].damage == 0
        assert p1.deck[0].exhausted is False
        assert p1.deck[0].face_down is True
        assert not state.pending_decisions

    def test_lof_200_puts_enemy_ground_unit_on_bottom(self, repo):
        from swu.engine.actions import legal_actions, apply, PutOnDeckBottom
        state = _make_state()
        qg = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "LOF", "193"), "ground")
        state = self._defeat_and_choose(state, qg, enemy)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PutOnDeckBottom)))
        state = self._drain(state)
        p1 = state.player_by_id("P1")
        assert _find_instance(state, enemy.instance_id) is None
        assert p1.deck[-1].instance_id == enemy.instance_id          # on BOTTOM
        assert not state.pending_decisions

    def test_lof_200_friendly_unit_goes_to_owner_deck_and_strips_upgrades(self, repo):
        """Target may be friendly (any controller); its OWNER (= P0 here) decides,
        and its non-token upgrades are stripped to their owner's discard."""
        from swu.engine.actions import legal_actions, apply, PutOnDeckTop
        state = _make_state()
        qg = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "LOF", "193"), "ground")
        upg = _attach_upgrade_directly(state, friendly,
                                       _get_card(repo, "LOF", "201"), "P0")
        state = self._defeat_and_choose(state, qg, friendly)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PutOnDeckTop)))
        p0 = state.player_by_id("P0")
        assert _find_instance(state, friendly.instance_id) is None
        assert p0.deck[0].instance_id == friendly.instance_id
        assert not p0.deck[0].attached_upgrades
        assert any(c.instance_id == upg.instance_id for c in p0.discard)

    def test_lof_200_no_ground_unit_auto_declines(self, repo):
        """Only a SPACE enemy unit on the board — no legal ground target, so the
        optional WhenDefeated trigger is not offered."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        qg = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        _place(state, "P1", _get_card(repo, "LOF", "193"), "space")
        state = _defeat_and_fire(state, qg, "P0")
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_lof_200_declinable(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineTrigger
        state = _make_state()
        qg = _place(state, "P0", _get_card(repo, "LOF", "200"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "LOF", "193"), "ground")
        state = _defeat_and_fire(state, qg, "P0")
        dec = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, dec)
        assert _find_instance(state, enemy.instance_id) is not None   # still in play
        assert not state.pending_decisions


# ── LOF_42 Always Two (choose_units_sacrifice_rest) ───────────────────────────

class TestAlwaysTwoLOF42:
    """Choose 2 friendly unique Sith units. If you do, give 2 Shield + 2 Experience
    tokens to each chosen unit. Defeat all other friendly units."""

    def _board(self, repo):
        """P0 with two unique Sith units, a non-Sith unique unit, a non-unique unit;
        P1 with an enemy unit.  Returns (state, dict of instance_ids)."""
        state = _make_state()
        sith_a = _place(state, "P0", _get_card(repo, "LOF", "82"), "ground")   # Vaneé 2/4 unique Sith
        sith_b = _place(state, "P0", _get_card(repo, "LOF", "130"), "ground")  # HK-47 2/4 unique Sith
        sith_c = _place(state, "P0", _get_card(repo, "TWI", "134"), "ground")  # Asajj 2/4 unique Sith
        nonsith = _place(state, "P0", _get_card(repo, "SOR", "189"), "ground")  # Leia — unique non-Sith
        nonuniq = _place(state, "P0", _get_card(repo, "SOR", "225"), "space")   # TIE — non-unique
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")     # 3/7 enemy
        return state, {
            "a": sith_a.instance_id, "b": sith_b.instance_id, "c": sith_c.instance_id,
            "nonsith": nonsith.instance_id, "nonuniq": nonuniq.instance_id,
            "enemy": enemy.instance_id,
        }

    def test_lof_42_pushes_choose_units_sacrifice_rest(self, repo):
        from swu.engine.actions import legal_actions, ChooseUnitToSpare
        state, ids = self._board(repo)
        state, _ = _play_event_from_hand(state, repo, "LOF", "42")
        top = state.pending_decisions[-1]
        assert top.kind == "choose_units_sacrifice_rest"
        assert top.deciding_player_id == "P0"
        # Only the three unique Sith units are eligible to spare.
        spare_ids = {a.target_id for a in legal_actions(state)
                     if isinstance(a, ChooseUnitToSpare)}
        assert spare_ids == {ids["a"], ids["b"], ids["c"]}

    def test_lof_42_buffs_chosen_and_defeats_the_rest(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseUnitToSpare
        state, ids = self._board(repo)
        state, _ = _play_event_from_hand(state, repo, "LOF", "42")
        for keep in (ids["a"], ids["b"]):
            act = next(a for a in legal_actions(state)
                       if isinstance(a, ChooseUnitToSpare) and a.target_id == keep)
            state = apply(state, act)
        assert not state.pending_decisions
        # The two chosen units survive with 2 Shield + 2 Experience each.
        for keep in (ids["a"], ids["b"]):
            ci = _find_instance(state, keep)
            assert ci is not None
            assert _shield_count(ci) == 2
            assert _experience_count(ci) == 2
        # Every OTHER friendly unit is defeated (incl. the third Sith, the non-Sith
        # unique, and the non-unique space unit).
        for gone in (ids["c"], ids["nonsith"], ids["nonuniq"]):
            assert _find_instance(state, gone) is None
        # The enemy unit is untouched.
        assert _find_instance(state, ids["enemy"]) is not None

    def test_lof_42_fizzles_with_fewer_than_two_unique_sith(self, repo):
        # Only ONE unique Sith unit on the board → "If you do" fails; nothing dies.
        state = _make_state()
        sith = _place(state, "P0", _get_card(repo, "LOF", "82"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "225"), "space")  # non-unique
        state, _ = _play_event_from_hand(state, repo, "LOF", "42")
        assert not state.pending_decisions  # not pushed
        assert _find_instance(state, sith.instance_id) is not None
        assert _find_instance(state, other.instance_id) is not None

    def test_lof_42_reprints_p26_73_and_89_alias_to_lof_42(self, repo):
        from swu.cards.reprints import REPRINT_ALIASES
        from swu.abilities.registry import get_abilities
        assert REPRINT_ALIASES.get(("P26", "73")) == ("LOF", "42")
        assert REPRINT_ALIASES.get(("P26", "89")) == ("LOF", "42")
        canonical = get_abilities("LOF", "42")
        assert canonical
        assert get_abilities("P26", "73") == canonical
        assert get_abilities("P26", "89") == canonical


# ── LOF_98 Leia Organa — the location-gated ready restriction (batch 37) ────────

class TestLeiaOrganaLOF98:
    """LOF_98 — Leia (Space unit): "While this unit is in the space arena, she can't
    ready and gains: 'Action [use the Force]: Move to the ground arena and give each
    friendly Heroism unit +2/+2 for this phase.'\""""

    def test_lof_98_cannot_ready_at_regroup_while_in_space(self, repo):
        from swu.engine.actions import _end_regroup
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "LOF", "98"), "space")
        plain = _place(state, "P0", _get_card(repo, "SOR", "97"), "space")  # Admiral Ackbar (space, no restriction)
        leia.exhausted = True
        plain.exhausted = True
        _end_regroup(state)
        assert leia.exhausted is True   # ReadyRestriction: stuck exhausted in space
        assert plain.exhausted is False  # a normal space unit readies

    def test_lof_98_action_offered_only_in_space_with_force_token(self, repo):
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "LOF", "98"), "space")

        def _has_leia_action(st):
            return any(isinstance(a, UseAbility) and a.source_id == leia.instance_id
                       for a in legal_actions(st))

        # No Force token → the UseForce cost is unaffordable → not offered.
        state.player_by_id("P0").has_force_token = False
        assert not _has_leia_action(state)
        # In space + Force token → offered.
        state.player_by_id("P0").has_force_token = True
        assert _has_leia_action(state)

    def test_lof_98_action_moves_to_ground_buffs_heroism_and_lifts(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, compute_power, compute_hp
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "LOF", "98"), "space")
        ally_hero = _place(state, "P0", _get_card(repo, "SOR", "192"), "ground")  # Ezra (Heroism)
        ally_non = _place(state, "P0", _get_card(repo, "SOR", "225"), "space")    # TIE/ln (Villainy, no Heroism)
        enemy_hero = _place(state, "P1", _get_card(repo, "SOR", "192"), "ground")
        state.player_by_id("P0").has_force_token = True
        hp_ally_before = compute_hp(state, ally_hero)
        pow_non_before = compute_power(state, ally_non)
        pow_enemy_before = compute_power(state, enemy_hero)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leia.instance_id)
        state = apply(state, act)

        ps = state.player_by_id("P0")
        leia2 = _find_instance(state, leia.instance_id)
        assert leia2 in ps.ground_arena and leia2 not in ps.space_arena  # moved to ground
        assert ps.has_force_token is False  # Force token spent
        # Each friendly Heroism unit +2/+2 (Leia herself too); non-Heroism + enemy untouched.
        assert compute_power(state, leia2) == 5 + 2
        assert compute_hp(state, _find_instance(state, ally_hero.instance_id)) == hp_ally_before + 2
        assert compute_power(state, _find_instance(state, ally_non.instance_id)) == pow_non_before
        assert compute_power(state, _find_instance(state, enemy_hero.instance_id)) == pow_enemy_before
        # On the ground the restriction + Action are both gone.
        assert not any(isinstance(a, UseAbility) and a.source_id == leia.instance_id
                       for a in legal_actions(state))

    def test_lof_98_readies_normally_after_moving_to_ground(self, repo):
        from swu.engine.actions import legal_actions, apply, UseAbility, _end_regroup
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "LOF", "98"), "space")
        state.player_by_id("P0").has_force_token = True
        act = next(a for a in legal_actions(state)
                   if isinstance(a, UseAbility) and a.source_id == leia.instance_id)
        state = apply(state, act)  # now on the ground
        leia2 = _find_instance(state, leia.instance_id)
        leia2.exhausted = True
        _end_regroup(state)
        assert _find_instance(state, leia.instance_id).exhausted is False  # restriction lifted

    def test_lof_98_ready_forbidden_helper_and_readycard_effect(self, repo):
        from swu.engine.actions import _ready_forbidden
        from swu.abilities.registry import ReadyCard, TargetSpec
        from swu.abilities.resolver import execute_effect
        from swu.engine.state import Zone
        state = _make_state()
        leia = _place(state, "P0", _get_card(repo, "LOF", "98"), "space")
        assert _ready_forbidden(state, leia) is True   # in space
        leia.exhausted = True
        # A ReadyCard effect can't ready her while she is in space.
        execute_effect(state, ReadyCard(TargetSpec(controller="friendly", kind="unit")),
                       leia, leia.instance_id, {})
        assert leia.exhausted is True
        # Move her to ground → restriction no longer applies.
        state.player_by_id("P0").space_arena.remove(leia)
        leia.zone = Zone.GROUND_ARENA
        state.player_by_id("P0").ground_arena.append(leia)
        assert _ready_forbidden(state, leia) is False

    def test_lof_98_reprints_p25_80_and_p26_102_alias_to_lof_98(self, repo):
        from swu.cards.reprints import REPRINT_ALIASES
        from swu.abilities.registry import get_abilities
        assert REPRINT_ALIASES[("P25", "80")] == ("LOF", "98")
        assert REPRINT_ALIASES[("P26", "102")] == ("LOF", "98")
        canon = get_abilities("LOF", "98")
        assert get_abilities("P25", "80") == canon
        assert get_abilities("P26", "102") == canon


# ── LOF_108 Malakili — ability-damage prevention (Stage 4 batch 41) ────────────

class TestMalakiliLOF108:
    """LOF_108 Malakili — 'If a friendly Creature unit would deal damage to a
    friendly unit, prevent that damage' (the PreventDamage primitive) + 'The first
    Creature unit you play each phase costs 1 less' (StandingPlayDiscount reuse)."""

    def test_lof_108_friendly_creature_damage_to_friendly_unit_prevented(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "108"), "ground")     # Malakili
        wampa = _place(state, "P0", _get_card(repo, "SOR", "164"), "ground")  # Creature
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # friendly
        _apply_deal_damage(state, target.instance_id, 3, source_id=wampa.instance_id)
        assert _find_instance(state, target.instance_id).damage == 0

    def test_lof_108_no_malakili_creature_damage_lands(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        wampa = _place(state, "P0", _get_card(repo, "SOR", "164"), "ground")
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _apply_deal_damage(state, target.instance_id, 3, source_id=wampa.instance_id)
        assert _find_instance(state, target.instance_id).damage == 3

    def test_lof_108_non_creature_source_not_prevented(self, repo):
        """A non-Creature friendly source is not covered by Malakili's prevention."""
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "108"), "ground")
        src = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Creature
        target = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7, survives
        _apply_deal_damage(state, target.instance_id, 2, source_id=src.instance_id)
        assert _find_instance(state, target.instance_id).damage == 2

    def test_lof_108_creature_damage_to_enemy_unit_lands(self, repo):
        """Prevention is friendly-fire only — a Creature hitting an ENEMY unit is
        unaffected even with Malakili in play."""
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "108"), "ground")
        wampa = _place(state, "P0", _get_card(repo, "SOR", "164"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _apply_deal_damage(state, enemy.instance_id, 3, source_id=wampa.instance_id)
        assert _find_instance(state, enemy.instance_id).damage == 3

    def test_lof_108_creature_damage_to_base_lands(self, repo):
        """Only friendly UNIT targets are guarded — a base is never prevented."""
        from swu.abilities.resolver import _apply_deal_damage
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "108"), "ground")
        wampa = _place(state, "P0", _get_card(repo, "SOR", "164"), "ground")
        base = state.player_by_id("P0").base_zone[0]
        _apply_deal_damage(state, base.instance_id, 3, source_id=wampa.instance_id)
        assert base.damage == 3

    def test_lof_108_first_creature_costs_1_less(self, repo):
        from swu.engine.actions import _standing_play_discount
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "108"), "ground")   # Malakili
        ps0 = state.player_by_id("P0")
        creature = _put_in_hand(state, "P0", _get_card(repo, "SOR", "164"))  # Creature
        non_creature = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        assert _standing_play_discount(state, creature, ps0) == 1
        assert _standing_play_discount(state, non_creature, ps0) == 0

    def test_lof_108_reprints_alias_to_canonical(self):
        from swu.abilities.registry import get_abilities
        assert get_abilities("LOFP", "7") is get_abilities("LOF", "108")


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:01`` / ``lof-set:02`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

def _use_actions_lof(state, source_ci):
    """Every UseAbility currently offered for ``source_ci``."""
    from swu.engine.actions import legal_actions, UseAbility
    return [a for a in legal_actions(state)
            if isinstance(a, UseAbility) and a.source_id == source_ci.instance_id]


def _fire_leader_deployed_lof(state, leader_ci):
    """Fire the LeaderDeployed event for a leader deployed into an arena."""
    from swu.engine.events import LeaderDeployed
    from swu.abilities.resolver import fire_triggered_abilities
    evt = LeaderDeployed(player_id=leader_ci.owner_id,
                         instance_id=leader_ci.instance_id,
                         leader_name=leader_ci.card_def.display_name,
                         arena="Ground")
    return fire_triggered_abilities(
        state, evt,
        after_all_player_idx=1 - state.player_index(leader_ci.owner_id))


# ── LOF_11 Kit Fisto ──────────────────────────────────────────────────────────

class TestKitFistoLOF11:
    """Undeployed Action [1 resource, Exhaust]: if you attacked with a Jedi unit
    this phase, deal 2 damage to a unit.  Deployed: +1/+0 per OTHER friendly Jedi."""

    def test_lof_11_action_needs_a_jedi_attack_this_phase(self, repo):
        """Not offered before any attack, offered after a Jedi unit attacks."""
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        kit = _place_leader(state, "P0", _get_card(repo, "LOF", "11"))
        jedi = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # Force/Jedi
        _give_resources(state, "P0", 4)
        assert not _use_actions_lof(state, kit)
        state = apply(state, AttackWithUnit(attacker_id=jedi.instance_id))
        state.active_player_index = state.player_index("P0")
        assert _use_actions_lof(state, kit)

    def test_lof_11_non_jedi_attack_does_not_arm_the_action(self, repo):
        """A Rebel/Trooper attacker leaves the Jedi gate closed."""
        from swu.engine.actions import apply, AttackWithUnit
        state = _make_state()
        kit = _place_leader(state, "P0", _get_card(repo, "LOF", "11"))
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 4)
        state = apply(state, AttackWithUnit(attacker_id=trooper.instance_id))
        state.active_player_index = state.player_index("P0")
        assert not _use_actions_lof(state, kit)

    def test_lof_11_action_deals_2_damage_to_a_unit(self, repo):
        from swu.engine.actions import apply, AttackWithUnit, ChooseTarget
        state = _make_state()
        kit = _place_leader(state, "P0", _get_card(repo, "LOF", "11"))
        jedi = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        _give_resources(state, "P0", 4)
        state = apply(state, AttackWithUnit(attacker_id=jedi.instance_id))
        state.active_player_index = state.player_index("P0")
        state = apply(state, _use_actions_lof(state, kit)[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_lof_11_deployed_gets_plus_1_per_other_friendly_jedi(self, repo):
        """+1/+0 for each OTHER friendly Jedi — he never counts himself."""
        from swu.engine.actions import compute_power
        state = _make_state()
        kit = _place(state, "P0", _get_card(repo, "LOF", "11"), "ground")
        kit.deployed = True
        assert compute_power(state, kit) == 1          # printed power, no other Jedi
        _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")   # Jedi
        _place(state, "P0", _get_card(repo, "LOF", "145"), "ground")   # Jedi
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # not a Jedi
        _place(state, "P1", _get_card(repo, "LOF", "196"), "ground")   # enemy Jedi
        assert compute_power(state, _find_instance(state, kit.instance_id)) == 3


# ── LOF_12 Rey ────────────────────────────────────────────────────────────────

class TestReyLOF12:
    """Undeployed Action [Exhaust]: if you played a non-unit Force card this phase,
    deal 1 damage to a unit.  When Deployed: you may discard your hand, draw 2."""

    def test_lof_12_action_armed_by_a_non_unit_force_card(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        rey = _place_leader(state, "P0", _get_card(repo, "LOF", "12"))
        assert not _use_actions_lof(state, rey)
        # Mind Trick (Force/Trick EVENT) — fizzles with no units in play.
        state, _ = _play_event_from_hand(state, repo, "LOF", "202")
        state.active_player_index = state.player_index("P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = apply(state, _use_actions_lof(state, rey)[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 1

    def test_lof_12_a_force_unit_does_not_arm_the_action(self, repo):
        """The ledger is the NON-UNIT slice: playing a Force *unit* leaves it shut."""
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        rey = _place_leader(state, "P0", _get_card(repo, "LOF", "12"))
        unit = _put_in_hand(state, "P0", _get_card(repo, "LOF", "196"))  # Force/Jedi
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(unit.instance_id))
        state.active_player_index = state.player_index("P0")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not _use_actions_lof(state, rey)

    def test_lof_12_when_deployed_discards_hand_and_draws_2(self, repo):
        state = _make_state()
        rey = _place(state, "P0", _get_card(repo, "LOF", "12"), "ground")
        rey.deployed = True
        for _ in range(3):
            _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        for _ in range(4):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_leader_deployed_lof(state, rey)
        state = _accept_optional_and_run(state)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 2          # 3 discarded, 2 drawn
        assert len(ps.discard) == 3


# ── LOF_71 Grappling Guardian ─────────────────────────────────────────────────

class TestGrapplingGuardianLOF71:
    """When Played: You may defeat a space unit with 6 or less remaining HP."""

    def test_lof_71_defeats_a_low_hp_space_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        guardian = _place(state, "P0", _get_card(repo, "LOF", "71"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")  # 2/3
        state = _fire_when_played(state, guardian)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(prey.instance_id))
        assert _find_instance(state, prey.instance_id) is None

    def test_lof_71_only_space_units_with_6_or_less_remaining_hp(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        guardian = _place(state, "P0", _get_card(repo, "LOF", "71"), "ground")
        small = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")   # 2/3
        big = _place(state, "P1", _get_card(repo, "LOF", "119"), "space")     # 4/10
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, guardian)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert small.instance_id in offered
        assert big.instance_id not in offered
        assert ground.instance_id not in offered


# ── LOF_91 Craving Power ──────────────────────────────────────────────────────

class TestCravingPowerLOF91:
    """When Played: Deal damage to an enemy unit equal to attached unit's power."""

    def test_lof_91_deals_damage_equal_to_host_power(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # 5/4
        enemy = _place(state, "P1", _get_card(repo, "LOF", "119"), "space")  # 4/10
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "91"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        state = apply(state, ChooseTarget(enemy.instance_id))
        # 5 printed + the upgrade's own +2/+2 = the host's power when this resolves
        assert _find_instance(state, enemy.instance_id).damage == 7

    def test_lof_91_magnitude_tracks_the_hosts_effective_power(self, repo):
        """An Experience token on the host raises the damage — effective power."""
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")  # 5/4
        from swu.engine import tokens
        tokens.attach_token(state, state.player_by_id("P0"), host, "Experience")
        enemy = _place(state, "P1", _get_card(repo, "LOF", "119"), "space")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "91"), "P0")
        state = _fire_upgrade_played(state, upg, host)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 8   # 5 + 2 + 1


# ── LOF_133 Purge Trooper ─────────────────────────────────────────────────────

class TestPurgeTrooperLOF133:
    """When Played: You may deal 2 damage to a Force unit."""

    def test_lof_133_deals_2_to_a_force_unit_only(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        trooper = _place(state, "P0", _get_card(repo, "LOF", "133"), "ground")
        force_unit = _place(state, "P1", _get_card(repo, "LOF", "196"), "ground")
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, trooper)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert force_unit.instance_id in offered
        assert plain.instance_id not in offered
        state = apply(state, ChooseTarget(force_unit.instance_id))
        assert _find_instance(state, force_unit.instance_id).damage == 2


# ── LOF_134 Heavy Missile Gunship ─────────────────────────────────────────────

class TestHeavyMissileGunshipLOF134:
    """Action [Exhaust]: Deal 2 damage to a ground unit."""

    def test_lof_134_action_deals_2_to_a_ground_unit_only(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        gunship = _place(state, "P0", _get_card(repo, "LOF", "134"), "ground")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")
        state = apply(state, _use_actions_lof(state, gunship)[0])
        from swu.engine.actions import legal_actions
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ground.instance_id in offered
        assert space.instance_id not in offered
        state = apply(state, ChooseTarget(ground.instance_id))
        assert _find_instance(state, ground.instance_id).damage == 2
        assert _find_instance(state, gunship.instance_id).exhausted


# ── LOF_141 Death Field ───────────────────────────────────────────────────────

class TestDeathFieldLOF141:
    """Deal 2 damage to each non-Vehicle enemy unit.  If you control a Force unit,
    draw a card."""

    def test_lof_141_damages_each_non_vehicle_enemy_unit_only(self, repo):
        state = _make_state()
        enemy_troop = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        enemy_ship = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")  # Vehicle
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "141")
        assert _find_instance(state, enemy_troop.instance_id).damage == 2
        assert _find_instance(state, enemy_ship.instance_id).damage == 0
        assert _find_instance(state, friendly.instance_id).damage == 0

    def test_lof_141_draws_only_while_you_control_a_force_unit(self, repo):
        state = _make_state()
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        for _ in range(4):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        before = len(state.player_by_id("P0").hand)
        state, _ = _play_event_from_hand(state, repo, "LOF", "141")
        assert len(state.player_by_id("P0").hand) == before   # the event left the hand

        state2 = _make_state()
        _place(state2, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state2, "P0", _get_card(repo, "LOF", "196"), "ground")   # Force unit
        for _ in range(4):
            _push_deck_top(state2, "P0", _get_card(repo, "SOR", "46"))
        before2 = len(state2.player_by_id("P0").hand)
        state2, _ = _play_event_from_hand(state2, repo, "LOF", "141")
        assert len(state2.player_by_id("P0").hand) == before2 + 1


# ── LOF_142 Adi Gallia ────────────────────────────────────────────────────────

class TestAdiGalliaLOF142:
    """When an opponent plays an event: Deal 1 damage to that player's base."""

    def test_lof_142_damages_the_event_players_base(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "142"), "ground")
        state.active_player_index = state.player_index("P1")
        state, _ = _play_event_from_hand(state, repo, "LOF", "127", owner="P1")
        # the only legal target is the event player's own base
        choices = [a for a in legal_actions(state) if isinstance(a, ChooseTarget)]
        assert [a.target_id for a in choices] == [
            state.player_by_id("P1").base_instance.instance_id]
        state = apply(state, choices[0])
        assert state.player_by_id("P1").base_instance.damage == 1
        assert state.player_by_id("P0").base_instance.damage == 0

    def test_lof_142_ignores_the_controllers_own_events(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "142"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "127", owner="P0")
        assert not state.pending_decisions
        assert state.player_by_id("P1").base_instance.damage == 0
        assert state.player_by_id("P0").base_instance.damage == 0


# ── LOF_144 Jedi Starfighter ──────────────────────────────────────────────────

class TestJediStarfighterLOF144:
    """On Attack: You may deal 1 damage to a space unit."""

    def test_lof_144_on_attack_deals_1_to_a_space_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "LOF", "144"), "space")
        target = _place(state, "P1", _get_card(repo, "SOR", "237"), "space")
        ground = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, fighter, target)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ground.instance_id not in offered
        state = apply(state, ChooseTarget(target.instance_id))
        assert _find_instance(state, target.instance_id).damage == 1


# ── LOF_145 Jedi Knight ───────────────────────────────────────────────────────

class TestJediKnightLOF145:
    """When Played: If you have the initiative, deal 2 damage to an enemy ground
    unit."""

    def test_lof_145_deals_2_with_the_initiative(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        state.initiative_holder = state.player_index("P0")
        knight = _place(state, "P0", _get_card(repo, "LOF", "145"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, knight)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_lof_145_no_trigger_without_the_initiative(self, repo):
        """The 'If …' clause gates COLLECTION — no prompt at all, no decision."""
        state = _make_state()
        state.initiative_holder = state.player_index("P1")
        knight = _place(state, "P0", _get_card(repo, "LOF", "145"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, knight)
        assert not state.pending_decisions
        assert _find_instance(state, enemy.instance_id).damage == 0


# ── LOF_147 Kit Fisto's Aethersprite ──────────────────────────────────────────

class TestKitFistosAetherspriteLOF147:
    """When Played: You may defeat any number of upgrades on a unit."""

    def test_lof_147_defeats_every_chosen_upgrade_on_one_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, SelectTokenTarget)
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "LOF", "147"), "space")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        up1 = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "120"), "P1")
        up2 = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "69"), "P1")
        state = _fire_when_played(state, ship)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(host.instance_id))
        assert state.pending_decisions[-1].kind == "select_token"
        state = apply(state, SelectTokenTarget(up1.instance_id))
        state = apply(state, SelectTokenTarget(up2.instance_id))
        assert not _find_instance(state, host.instance_id).attached_upgrades
        assert len(state.player_by_id("P1").discard) == 2

    def test_lof_147_any_number_may_be_none_and_stops_early(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, FinishSelectToken)
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "LOF", "147"), "space")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "120"), "P1")
        _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "69"), "P1")
        state = _fire_when_played(state, ship)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(host.instance_id))
        state = apply(state, FinishSelectToken())
        assert len(_find_instance(state, host.instance_id).attached_upgrades) == 2

    def test_lof_147_only_units_carrying_a_real_upgrade_are_offered(self, repo):
        """A bare unit — or one holding only a Shield token — is not a legal choice,
        so with no upgraded unit anywhere the optional trigger never prompts."""
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "LOF", "147"), "space")
        bare = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        shielded = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        from swu.engine import tokens
        tokens.attach_token(state, state.player_by_id("P1"), shielded, "Shield")
        upgraded = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, upgraded, _get_card(repo, "SOR", "120"), "P1")
        state = _fire_when_played(state, ship)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {upgraded.instance_id}
        assert bare.instance_id not in offered
        assert shielded.instance_id not in offered

    def test_lof_147_no_prompt_when_nothing_is_upgraded(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "LOF", "147"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, ship)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


# ── LOF_155 DRK-1 Probe Droid ─────────────────────────────────────────────────

class TestDRK1ProbeDroidLOF155:
    """When Played: You may defeat a non-unique upgrade."""

    def test_lof_155_defeats_a_non_unique_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "LOF", "155"), "ground")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        up = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "120"), "P1")
        state = _fire_when_played(state, droid)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(up.instance_id))
        assert not _find_instance(state, host.instance_id).attached_upgrades

    def test_lof_155_skips_unique_upgrades_and_tokens(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        droid = _place(state, "P0", _get_card(repo, "LOF", "155"), "ground")
        host = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        plain = _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "120"), "P1")
        unique = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "201"), "P1")
        from swu.engine import tokens
        tokens.attach_token(state, state.player_by_id("P1"), host, "Shield")
        state = _fire_when_played(state, droid)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {plain.instance_id}
        assert unique.instance_id not in offered


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:03`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

class TestHyenaBomber_LOF_158:
    """When Played: If you control another Aggression unit, you may deal 2 damage
    to a ground unit."""

    def test_LOF_158_deals_2_with_another_aggression_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "158"), "space")  # another Aggression unit
        bomber = _place(state, "P0", _get_card(repo, "LOF", "158"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, bomber)
        state = _accept_optional_and_run(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2

    def test_LOF_158_no_trigger_without_another_aggression_unit(self, repo):
        """The bomber cannot satisfy its own 'another Aggression unit' clause, so
        with no other Aggression unit the trigger is never collected."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        bomber = _place(state, "P0", _get_card(repo, "LOF", "158"), "space")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, bomber)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert not state.pending_decisions


class TestSaeseeTiin_LOF_167:
    """When Played: If you have the initiative, deal 1 damage to each of up to 3
    units."""

    def test_LOF_167_damages_up_to_three_units_with_initiative(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AutoResolveEffects, SelectDamageTarget,
            FinishSelectDamage)
        state = _make_state()
        state.initiative_holder = state.player_index("P0")
        tiin = _place(state, "P0", _get_card(repo, "LOF", "167"), "ground")
        a = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        b = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, tiin)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert state.pending_decisions[-1].kind == "select_damage"
        state = apply(state, SelectDamageTarget(a.instance_id))
        state = apply(state, SelectDamageTarget(b.instance_id))
        state = apply(state, FinishSelectDamage())
        assert _find_instance(state, a.instance_id).damage == 1
        assert _find_instance(state, b.instance_id).damage == 1

    def test_LOF_167_no_trigger_without_initiative(self, repo):
        from swu.engine.actions import legal_actions, AutoResolveEffects
        state = _make_state()
        state.initiative_holder = state.player_index("P1")
        tiin = _place(state, "P0", _get_card(repo, "LOF", "167"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, tiin)
        assert not any(isinstance(x, AutoResolveEffects) for x in legal_actions(state))
        assert not state.pending_decisions


class TestBendu_LOF_170:
    """On Attack: Deal 3 damage to each other unit."""

    def test_LOF_170_damages_every_other_unit_but_not_itself(self, repo):
        from swu.engine.actions import legal_actions, apply, AutoResolveEffects
        state = _make_state()
        bendu = _place(state, "P0", _get_card(repo, "LOF", "170"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_on_attack(state, bendu)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert _find_instance(state, friend.instance_id).damage == 3
        assert _find_instance(state, foe.instance_id).damage == 3
        assert _find_instance(state, bendu.instance_id).damage == 0


class TestHeavyBlasterCannon_LOF_171:
    """When Played: You may deal 1 damage to a ground unit, three times over."""

    def test_LOF_171_deals_three_separate_instances(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        cannon = _attach_upgrade_directly(
            state, host, _get_card(repo, "LOF", "171"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_upgrade_played(state, cannon, host)
        state = _accept_optional_and_run(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3

    def test_LOF_171_shield_only_stops_the_first_instance(self, repo):
        """The printed rules note: three separate instances, so a Shield eats one."""
        from swu.engine.actions import apply, ChooseTarget
        from swu.engine.tokens import attach_token
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        cannon = _attach_upgrade_directly(
            state, host, _get_card(repo, "LOF", "171"), "P0")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        attach_token(state, state.player_by_id("P1"), enemy, "Shield")
        state = _fire_upgrade_played(state, cannon, host)
        state = _accept_optional_and_run(state)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 2


class TestSorcerousBlast_LOF_172:
    """Use the Force. If you do, deal 3 damage to a unit."""

    def test_LOF_172_spends_force_and_deals_3(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "172")
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 3
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_172_fizzles_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = False
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "172")
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert _find_instance(state, enemy.instance_id).damage == 0


class TestLightsaberThrow_LOF_176:
    """Discard a Lightsaber card from your hand. If you do, deal 4 damage to a
    ground unit and draw a card."""

    def test_LOF_176_discards_lightsaber_deals_4_and_draws(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        saber = _put_in_hand(state, "P0", _get_card(repo, "SOR", "53"))  # Luke's Lightsaber
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "176")
        hand_before = len(state.player_by_id("P0").hand)
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).damage == 4
        ps = state.player_by_id("P0")
        assert saber.instance_id in {c.instance_id for c in ps.discard}
        # -1 for the pitched Lightsaber, +1 for the draw
        assert len(ps.hand) == hand_before

    def test_LOF_176_fizzles_without_a_lightsaber_in_hand(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "176")
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert _find_instance(state, enemy.instance_id).damage == 0


class TestTimeOfCrisis_LOF_177:
    """Each player chooses a unit they control. Deal 3 damage to each unit not
    chosen this way."""

    def test_LOF_177_spares_one_unit_each_and_damages_the_rest(self, repo):
        from swu.engine.actions import apply, ChooseUnitToDefeat
        state = _make_state()
        keep0 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        burn0 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        keep1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        burn1 = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "177")
        assert state.pending_decisions[-1].kind == "each_player_defeats"
        assert state.pending_decisions[-1].deciding_player_id == "P0"
        state = apply(state, ChooseUnitToDefeat(keep0.instance_id))
        assert state.pending_decisions[-1].deciding_player_id == "P1"
        state = apply(state, ChooseUnitToDefeat(keep1.instance_id))
        assert _find_instance(state, keep0.instance_id).damage == 0
        assert _find_instance(state, keep1.instance_id).damage == 0
        assert _find_instance(state, burn0.instance_id).damage == 3
        assert _find_instance(state, burn1.instance_id).damage == 3


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:04`` — Direct damage & removal
# ══════════════════════════════════════════════════════════════════════════════

class TestTheLegacyRun_LOF_213:
    """When Defeated: Deal 6 damage divided as you choose among enemy units."""

    def test_LOF_213_distributes_6_among_enemy_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AutoResolveEffects, AssignDamage)
        state = _make_state()
        run = _place(state, "P0", _get_card(repo, "LOF", "213"), "space")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_defeated(state, run)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        top = state.pending_decisions[-1]
        assert top.kind == "distribute_damage"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, AssignDamage)}
        assert foe.instance_id in offered
        assert friend.instance_id not in offered  # enemy units only
        for _ in range(6):
            state = apply(state, AssignDamage(foe.instance_id))
        assert not state.pending_decisions
        assert _find_instance(state, foe.instance_id).damage == 6
        assert _find_instance(state, friend.instance_id).damage == 0


class TestConsumedByTheDarkSide_LOF_239:
    """Give 2 Experience tokens to a unit, then deal 2 damage to it."""

    def test_LOF_239_gives_two_experience_then_deals_2(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        target = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "239")
        state = apply(state, ChooseTarget(target.instance_id))
        after = _find_instance(state, target.instance_id)
        assert _experience_count(after) == 2
        assert after.damage == 2


class TestRaveningGundark_LOF_259:
    """When Played: Deal 1 damage to a ground unit."""

    def test_LOF_259_deals_1_to_a_ground_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget, legal_actions
        state = _make_state()
        gundark = _place(state, "P0", _get_card(repo, "LOF", "259"), "ground")
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        space_foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "space")
        state = _fire_when_played(state, gundark)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert space_foe.instance_id not in offered
        state = apply(state, ChooseTarget(foe.instance_id))
        assert _find_instance(state, foe.instance_id).damage == 1


class TestTheFather_LOF_260:
    """When you use the Force: You may deal 1 damage to this unit. If you do, the
    Force is with you."""

    def test_LOF_260_self_damage_recreates_the_force_token(self, repo):
        from swu.engine.actions import apply, spend_force_token, Pass
        state = _make_state()
        father = _place(state, "P0", _get_card(repo, "LOF", "260"), "ground")
        ps = state.player_by_id("P0")
        ps.has_force_token = True
        spend_force_token(state, ps)
        assert state.player_by_id("P0").has_force_token is False
        # The observer drains at the action settle-point.
        state = apply(state, Pass())
        state = _accept_optional_and_run(state)
        assert _find_instance(state, father.instance_id).damage == 1
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_260_declining_leaves_him_undamaged_and_tokenless(self, repo):
        from swu.engine.actions import (
            apply, spend_force_token, Pass, legal_actions, DeclineTrigger)
        state = _make_state()
        father = _place(state, "P0", _get_card(repo, "LOF", "260"), "ground")
        ps = state.player_by_id("P0")
        ps.has_force_token = True
        spend_force_token(state, ps)
        state = apply(state, Pass())
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        assert _find_instance(state, father.instance_id).damage == 0
        assert state.player_by_id("P0").has_force_token is False


class TestItsWorse_LOF_264:
    """Defeat a non-leader unit."""

    def test_LOF_264_defeats_a_non_leader_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget, legal_actions
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        leader = _place(state, "P1", _get_card(repo, "SOR", "10"), "ground")
        leader.deployed = True
        state, _evt = _play_event_from_hand(state, repo, "LOF", "264")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert leader.instance_id not in offered
        state = apply(state, ChooseTarget(foe.instance_id))
        assert _find_instance(state, foe.instance_id) is None


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:05`` — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

def _token_def_lof(repo, number, type_name):
    """Fetch the TOKEN card_def sharing a (set, number) with a real LOF card."""
    with repo._con() as con:
        row = con.execute(
            "SELECT * FROM cards WHERE set_code=? AND card_number=? AND type=?",
            ("LOF", str(int(number)), type_name)).fetchone()
        from tests.dbpath import require_row
        row = require_row(row, f"LOF_{number} ({type_name})")
        return repo._hydrate(con, row)


class TestKyloRen_LOF_1:
    """Undeployed Action [Exhaust]: discard a card; draw if it was an upgrade.
    When Deployed: play any number of upgrades from your discard onto him."""

    def test_LOF_1_action_discards_and_draws_only_for_an_upgrade(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        kylo = _place_leader(state, "P0", _get_card(repo, "LOF", "1"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "53"))  # Luke's Lightsaber
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = apply(state, _use_actions_lof(state, kylo)[0])
        ps = state.player_by_id("P0")
        assert len(ps.discard) == 1
        assert len(ps.hand) == 1  # pitched the upgrade, drew a replacement

    def test_LOF_1_action_no_draw_when_a_unit_is_pitched(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        kylo = _place_leader(state, "P0", _get_card(repo, "LOF", "1"))
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))  # a Unit
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = apply(state, _use_actions_lof(state, kylo)[0])
        ps = state.player_by_id("P0")
        assert len(ps.discard) == 1
        assert len(ps.hand) == 0

    def test_LOF_1_action_not_offered_with_an_empty_hand(self, repo):
        state = _make_state()
        kylo = _place_leader(state, "P0", _get_card(repo, "LOF", "1"))
        assert not _use_actions_lof(state, kylo)

    def test_LOF_1_when_deployed_replays_discard_upgrades_onto_him(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayUpgradeFromHand)
        state = _make_state()
        kylo = _place(state, "P0", _get_card(repo, "LOF", "1"), "ground")
        kylo.deployed = True
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        saber = _put_in_discard(state, "P0", _get_card(repo, "SOR", "53"))
        _give_resources(state, "P0", 10)
        state = _fire_leader_deployed_lof(state, kylo)
        while any(isinstance(a, __import__("swu.engine.actions", fromlist=["x"])
                             .AutoResolveEffects) for a in legal_actions(state)):
            from swu.engine.actions import AutoResolveEffects
            state = apply(state, AutoResolveEffects())
        top = state.pending_decisions[-1]
        assert top.kind == "play_upgrade_from_hand"
        plays = [a for a in legal_actions(state) if isinstance(a, PlayUpgradeFromHand)]
        # "on this unit" — Kylo is the only legal host offered.
        assert plays and all(a.host_id == kylo.instance_id for a in plays)
        assert all(a.host_id != other.instance_id for a in plays)
        state = apply(state, plays[0])
        host = _find_instance(state, kylo.instance_id)
        assert saber.instance_id in {u.instance_id for u in host.attached_upgrades}
        # "Any number" — the loop re-pushes; nothing is left, so it is gone.
        assert not any(d.kind == "play_upgrade_from_hand"
                       for d in state.pending_decisions)

    def test_LOF_1_experience_token_gains_no_kylo_abilities(self, repo):
        """LOF_1 is also the Experience token's (set, number)."""
        from swu.engine.actions import legal_actions, UseAbility
        state = _make_state()
        token_def = _token_def_lof(repo, "1", "Token Upgrade")
        assert token_def.name == "Experience"
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        from swu.engine.tokens import attach_token
        attach_token(state, state.player_by_id("P0"), host, "Experience")
        assert not any(isinstance(a, UseAbility) for a in legal_actions(state))


class TestOldDaka_LOF_36:
    """When Played: You may defeat a friendly Night unit not named Old Daka. Then,
    you may play that unit from your discard pile for free."""

    def test_LOF_36_defeats_a_night_unit_and_replays_it_free(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayFromHand
        state = _make_state()
        daka = _place(state, "P0", _get_card(repo, "LOF", "36"), "ground")
        night = _place(state, "P0", _get_card(repo, "LOF", "59"), "ground")  # Nightsister Warrior
        state = _fire_when_played(state, daka)
        state = _accept_optional_and_run(state)
        state = apply(state, ChooseTarget(night.instance_id))
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        plays = [a for a in legal_actions(state) if isinstance(a, PlayFromHand)]
        assert {a.instance_id for a in plays} == {night.instance_id}
        state = apply(state, plays[0])
        assert _find_instance(state, night.instance_id) is not None

    def test_LOF_36_cannot_target_itself(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        daka = _place(state, "P0", _get_card(repo, "LOF", "36"), "ground")
        state = _fire_when_played(state, daka)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestOwenLars_LOF_57:
    """When Defeated: Search the top 5 of your deck for a Force unit and draw it."""

    def test_LOF_57_searches_and_draws_a_force_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AutoResolveEffects, SelectSearchCard)
        state = _make_state()
        owen = _place(state, "P0", _get_card(repo, "LOF", "57"), "ground")
        force_unit = _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))
        state = _fire_when_defeated(state, owen)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        assert state.pending_decisions[-1].kind == "deck_search"
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert {a.instance_id for a in picks} == {force_unit.instance_id}
        state = apply(state, picks[0])
        assert force_unit.instance_id in {
            c.instance_id for c in state.player_by_id("P0").hand}


class TestWatto_LOF_65:
    """On Attack: An opponent chooses one: you give an Experience token to a
    friendly unit / you draw a card."""

    def test_LOF_65_opponent_picks_the_mode_controller_picks_the_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AutoResolveEffects, ChooseModalOption,
            ChooseModalTarget)
        state = _make_state()
        watto = _place(state, "P0", _get_card(repo, "LOF", "65"), "ground")
        state = _fire_on_attack(state, watto)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        top = state.pending_decisions[-1]
        assert top.kind == "modal"
        assert top.deciding_player_id == "P1"      # the opponent chooses the mode
        state = apply(state, ChooseModalOption("give_experience_friendly_unit"))
        top = state.pending_decisions[-1]
        assert top.deciding_player_id == "P0"      # the controller picks the unit
        targets = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseModalTarget)}
        assert targets == {watto.instance_id}
        state = apply(state, ChooseModalTarget(watto.instance_id))
        assert _experience_count(_find_instance(state, watto.instance_id)) == 1

    def test_LOF_65_draw_mode_is_fungible_and_draws_for_the_controller(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AutoResolveEffects, ChooseModalOption)
        state = _make_state()
        watto = _place(state, "P0", _get_card(repo, "LOF", "65"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_on_attack(state, watto)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        state = apply(state, ChooseModalOption("draw_card"))
        assert len(state.player_by_id("P0").hand) == 1
        assert not any(d.kind == "modal" for d in state.pending_decisions)


class TestLuthenRael_LOF_68:
    """On Attack: Search the top 5 of your deck for an Item upgrade and draw it."""

    def test_LOF_68_offers_only_item_upgrades(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AutoResolveEffects, SelectSearchCard)
        state = _make_state()
        luthen = _place(state, "P0", _get_card(repo, "LOF", "68"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))      # a Unit
        item = _push_deck_top(state, "P0", _get_card(repo, "LOF", "171"))  # Item upgrade
        state = _fire_on_attack(state, luthen)
        while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
            state = apply(state, AutoResolveEffects())
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        assert {a.instance_id for a in picks} == {item.instance_id}
        state = apply(state, picks[0])
        assert item.instance_id in {
            c.instance_id for c in state.player_by_id("P0").hand}


class TestCaptainEnoch_LOF_83:
    """This unit gets +1/+0 for each Trooper unit in your discard pile."""

    def test_LOF_83_scales_with_troopers_in_the_discard(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        enoch = _place(state, "P0", _get_card(repo, "LOF", "83"), "ground")
        assert compute_power(state, enoch) == 1
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))   # Rebel/Trooper
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))
        assert compute_power(state, _find_instance(state, enoch.instance_id)) == 3

    def test_LOF_83_ignores_non_troopers_and_the_enemy_discard(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        enoch = _place(state, "P0", _get_card(repo, "LOF", "83"), "ground")
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "53"))   # an upgrade
        _put_in_discard(state, "P1", _get_card(repo, "SOR", "46"))   # enemy Trooper
        assert compute_power(state, _find_instance(state, enoch.instance_id)) == 1


class TestDagoyanMaster_LOF_115:
    """When Played/When Defeated: You may use the Force. If you do, search the top 5
    for a Force unit and draw it."""

    def test_LOF_115_when_played_spends_force_and_searches(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectSearchCard)
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        master = _place(state, "P0", _get_card(repo, "LOF", "115"), "ground")
        force_unit = _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))
        state = _fire_when_played(state, master)
        state = _accept_optional_and_run(state)
        assert state.pending_decisions[-1].kind == "deck_search"
        picks = [a for a in legal_actions(state) if isinstance(a, SelectSearchCard)]
        state = apply(state, picks[0])
        assert state.player_by_id("P0").has_force_token is False
        assert force_unit.instance_id in {
            c.instance_id for c in state.player_by_id("P0").hand}

    def test_LOF_115_not_offered_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        state.player_by_id("P0").has_force_token = False
        master = _place(state, "P0", _get_card(repo, "LOF", "115"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))
        state = _fire_when_played(state, master)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_LOF_115_when_defeated_also_offers_the_search(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        master = _place(state, "P0", _get_card(repo, "LOF", "115"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))
        state = _fire_when_defeated(state, master)
        assert any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:06`` — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

def _drain_lof(state):
    """Run every pending AutoResolveEffects."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    while any(isinstance(x, AutoResolveEffects) for x in legal_actions(state)):
        state = apply(state, AutoResolveEffects())
    return state


class TestSifoDyas_LOF_117:
    """When Defeated: search the top 8 for any number of Clone units with combined
    cost 4 or less, discard them, and play them free from the discard this phase."""

    def test_LOF_117_budget_caps_the_combined_cost(self, repo):
        from swu.engine.actions import legal_actions, SelectSearchCard
        state = _make_state()
        sifo = _place(state, "P0", _get_card(repo, "LOF", "117"), "ground")
        cheap = _push_deck_top(state, "P0", _get_card(repo, "TWI", "141"))   # Clone, cost 1
        pricey = _push_deck_top(state, "P0", _get_card(repo, "TWI", "97"))   # Clone, cost 6
        state = _fire_when_defeated(state, sifo)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "deck_search"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)}
        # Only Clone units within the 4-cost budget are offered.
        for iid in offered:
            ci = state.find_instance(iid)[1]
            assert "Clone" in (ci.card_def.traits or ())
            assert (ci.card_def.cost or 0) <= 4
        assert cheap.instance_id in offered or pricey.instance_id in offered

    def test_LOF_117_discards_the_picks_and_flags_a_free_replay(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard, FinishSearch
        state = _make_state()
        sifo = _place(state, "P0", _get_card(repo, "LOF", "117"), "ground")
        clone = _push_deck_top(state, "P0", _get_card(repo, "TWI", "141"))
        state = _fire_when_defeated(state, sifo)
        state = _drain_lof(state)
        pick = next((a for a in legal_actions(state)
                     if isinstance(a, SelectSearchCard)
                     and a.instance_id == clone.instance_id), None)
        assert pick is not None
        state = apply(state, pick)
        if any(isinstance(a, FinishSearch) for a in legal_actions(state)):
            state = apply(state, FinishSearch())
        ps = state.player_by_id("P0")
        assert clone.instance_id in {c.instance_id for c in ps.discard}
        assert clone.instance_id in state.game_memory.free_discard_play_this_phase


class TestThePurrgilKing_LOF_121:
    """When Played: Draw a card for each friendly unit with 7 or more remaining HP."""

    def test_LOF_121_draws_one_per_beefy_friendly_unit(self, repo):
        state = _make_state()
        king = _place(state, "P0", _get_card(repo, "LOF", "121"), "space")  # 4/12
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7 → counts
        _place(state, "P0", _get_card(repo, "SOR", "237"), "space")   # 2/3 → no
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # enemy → no
        for _ in range(5):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_when_played(state, king)
        state = _drain_lof(state)
        assert len(state.player_by_id("P0").hand) == 2  # the King + the 3/7

    def test_LOF_121_damage_lowers_remaining_hp_below_the_bar(self, repo):
        state = _make_state()
        king = _place(state, "P0", _get_card(repo, "LOF", "121"), "space")
        king.damage = 6  # 12 − 6 = 6 remaining → no longer counts
        for _ in range(5):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_when_played(state, king)
        state = _drain_lof(state)
        assert len(state.player_by_id("P0").hand) == 0


class TestPillioStarCompass_LOF_122:
    """When Played: search the top 3 for a unit and draw it."""

    def test_LOF_122_searches_the_top_three_for_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        compass = _attach_upgrade_directly(
            state, host, _get_card(repo, "LOF", "122"), "P0")
        unit = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_upgrade_played(state, compass, host)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "deck_search"
        assert state.pending_decisions[-1].context["window"] == 3
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, SelectSearchCard))
        state = apply(state, pick)
        assert unit.instance_id in {
            c.instance_id for c in state.player_by_id("P0").hand}


class TestTheBurdenOfMasters_LOF_125:
    """Put a Force unit from your discard on the bottom of your deck. If you do,
    play a unit from your hand and give 2 Experience tokens to it."""

    def test_LOF_125_bottoms_then_plays_and_tokens_the_played_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectBottomDiscardCard, FinishBottomFromDiscard,
            PlayFromHand, SelectTokenTarget)
        state = _make_state()
        forced = _put_in_discard(state, "P0", _get_card(repo, "LOF", "196"))  # Force
        hand_unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "125", resources=20)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "bottom_from_discard"
        state = apply(state, SelectBottomDiscardCard(forced.instance_id))
        if any(isinstance(a, FinishBottomFromDiscard) for a in legal_actions(state)):
            state = apply(state, FinishBottomFromDiscard())
        assert forced.instance_id in {
            c.instance_id for c in state.player_by_id("P0").deck}
        assert state.pending_decisions[-1].kind == "play_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayFromHand)
                    and a.instance_id == hand_unit.instance_id)
        state = apply(state, play)
        # The Experience payoff lands only on the just-played unit.
        top = state.pending_decisions[-1]
        assert top.kind == "select_token"
        picks = {a.target_id for a in legal_actions(state)
                 if isinstance(a, SelectTokenTarget)}
        assert picks == {hand_unit.instance_id}
        state = apply(state, SelectTokenTarget(hand_unit.instance_id))
        assert _experience_count(_find_instance(state, hand_unit.instance_id)) == 2

    def test_LOF_125_fizzles_with_no_force_unit_in_the_discard(self, repo):
        state = _make_state()
        _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))  # no Force trait
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "125", resources=20)
        state = _drain_lof(state)
        assert not state.pending_decisions


class TestBattleFury_LOF_139:
    """Attached unit gains: 'On Attack: Discard a card from your hand.'"""

    def test_LOF_139_host_discards_on_attack(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "139"), "P0")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_on_attack(state, _find_instance(state, host.instance_id))
        state = _drain_lof(state)
        ps = state.player_by_id("P0")
        assert len(ps.hand) == 0
        assert len(ps.discard) == 1

    def test_LOF_139_unattached_unit_does_not_discard(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_on_attack(state, host)
        state = _drain_lof(state)
        assert len(state.player_by_id("P0").hand) == 1


class TestKiAdiMundi_LOF_146:
    """When Played: You may use the Force. If you do, draw 2 cards."""

    def test_LOF_146_spends_the_force_and_draws_2(self, repo):
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        mundi = _place(state, "P0", _get_card(repo, "LOF", "146"), "ground")
        for _ in range(3):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_when_played(state, mundi)
        state = _accept_optional_and_run(state)
        assert len(state.player_by_id("P0").hand) == 2
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_146_not_offered_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        mundi = _place(state, "P0", _get_card(repo, "LOF", "146"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state = _fire_when_played(state, mundi)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestDoOrDoNot_LOF_175:
    """You may use the Force. If you do, draw 2. If you do not, draw a card."""

    def test_LOF_175_using_the_force_draws_2(self, repo):
        from swu.engine.actions import legal_actions, apply, UseForceOption
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        for _ in range(4):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "175")
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "use_force"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, UseForceOption)))
        assert len(state.player_by_id("P0").hand) == 2
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_175_declining_draws_1(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineUseForce
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        for _ in range(4):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "175")
        state = _drain_lof(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineUseForce)))
        assert len(state.player_by_id("P0").hand) == 1
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_175_no_token_draws_1_with_no_prompt(self, repo):
        state = _make_state()
        state.player_by_id("P0").has_force_token = False
        for _ in range(4):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "175")
        state = _drain_lof(state)
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").hand) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:07`` — Card advantage & disruption
# ══════════════════════════════════════════════════════════════════════════════

class TestSecondSister_LOF_184:
    """On Attack: You may discard 2 from your deck; ready a resource per Force card
    discarded this way."""

    def test_LOF_184_readies_one_resource_per_force_card_milled(self, repo):
        state = _make_state()
        sister = _place(state, "P0", _get_card(repo, "LOF", "184"), "ground")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))       # not Force
        _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))      # Force
        _give_resources(state, "P0", 3)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        state = _fire_on_attack(state, sister)
        state = _accept_optional_and_run(state)
        ps = state.player_by_id("P0")
        assert len(ps.discard) == 2
        assert sum(1 for r in ps.resources if not r.exhausted) == 1

    def test_LOF_184_no_force_card_readies_nothing(self, repo):
        state = _make_state()
        sister = _place(state, "P0", _get_card(repo, "LOF", "184"), "ground")
        for _ in range(2):
            _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 3)
        for r in state.player_by_id("P0").resources:
            r.exhausted = True
        state = _fire_on_attack(state, sister)
        state = _accept_optional_and_run(state)
        ps = state.player_by_id("P0")
        assert len(ps.discard) == 2
        assert all(r.exhausted for r in ps.resources)


class TestAsIHaveForeseen_LOF_188:
    """Look at the top card. You may use the Force; if you do, play it for 4 less."""

    def test_LOF_188_playing_the_top_card_spends_the_force(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayTopCard
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        top_card = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "188", resources=20)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "peek_top"
        play = next(a for a in legal_actions(state) if isinstance(a, PlayTopCard))
        state = apply(state, play)
        assert state.player_by_id("P0").has_force_token is False
        assert _find_instance(state, top_card.instance_id) is not None

    def test_LOF_188_no_decision_without_a_force_token(self, repo):
        state = _make_state()
        state.player_by_id("P0").has_force_token = False
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "188", resources=20)
        state = _drain_lof(state)
        assert not state.pending_decisions

    def test_LOF_188_keeping_the_card_costs_no_force(self, repo):
        from swu.engine.actions import legal_actions, apply, KeepTopCard
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "188", resources=20)
        state = _drain_lof(state)
        keep = next(a for a in legal_actions(state) if isinstance(a, KeepTopCard))
        state = apply(state, keep)
        assert state.player_by_id("P0").has_force_token is True


class TestZuckuss_LOF_204:
    """On Attack: name a card, mill the defending player's top card; +4/+0 on a
    match."""

    def test_LOF_204_matching_mill_buffs_him_for_this_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard, compute_power
        state = _make_state()
        zuck = _place(state, "P0", _get_card(repo, "LOF", "204"), "ground")
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        top_card = _push_deck_top(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_on_attack(state, zuck)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "name_a_card"
        name = prey.card_def.name
        pick = next(a for a in legal_actions(state)
                    if isinstance(a, NameCard) and a.name == name)
        state = apply(state, pick)
        ps1 = state.player_by_id("P1")
        assert top_card.instance_id in {c.instance_id for c in ps1.discard}
        assert compute_power(state, _find_instance(state, zuck.instance_id)) == 8

    def test_LOF_204_a_miss_leaves_his_power_alone(self, repo):
        from swu.engine.actions import legal_actions, apply, NameCard, compute_power
        state = _make_state()
        zuck = _place(state, "P0", _get_card(repo, "LOF", "204"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        top_card = _push_deck_top(state, "P1", _get_card(repo, "SOR", "237"))
        state = _fire_on_attack(state, zuck)
        state = _drain_lof(state)
        pick = next(a for a in legal_actions(state) if isinstance(a, NameCard))
        state = apply(state, pick)
        assert top_card.instance_id in {
            c.instance_id for c in state.player_by_id("P1").discard}
        assert compute_power(state, _find_instance(state, zuck.instance_id)) == 4


class TestPsychometry_LOF_219:
    """Choose another card in your discard; search the top 5 for a card sharing a
    trait with it and draw it."""

    def test_LOF_219_searches_for_a_trait_sharing_card(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectBottomDiscardCard,
            FinishBottomFromDiscard, SelectSearchCard)
        state = _make_state()
        seed = _put_in_discard(state, "P0", _get_card(repo, "SOR", "46"))  # Rebel/Trooper
        match = _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        state, evt = _play_event_from_hand(state, repo, "LOF", "219")
        state = _drain_lof(state)
        top = state.pending_decisions[-1]
        assert top.kind == "bottom_from_discard"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectBottomDiscardCard)}
        assert evt.instance_id not in offered           # "another card"
        assert seed.instance_id in offered
        state = apply(state, SelectBottomDiscardCard(seed.instance_id))
        if any(isinstance(a, FinishBottomFromDiscard) for a in legal_actions(state)):
            state = apply(state, FinishBottomFromDiscard())
        # The chosen card stays in the discard — the decision is only a selector.
        assert seed.instance_id in {
            c.instance_id for c in state.player_by_id("P0").discard}
        assert state.pending_decisions[-1].kind == "deck_search"
        pick = next(a for a in legal_actions(state) if isinstance(a, SelectSearchCard))
        state = apply(state, pick)
        assert match.instance_id in {
            c.instance_id for c in state.player_by_id("P0").hand}


class TestAPrecariousPredicament_LOF_222:
    """Return an enemy non-leader unit unless its controller says 'It could be
    worse'; if they do, you may play It's Worse free."""

    def test_LOF_222_allowing_returns_the_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, AllowEffect
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "222")
        state = apply(state, ChooseTarget(foe.instance_id))
        assert state.pending_decisions[-1].kind == "say_no"
        assert state.pending_decisions[-1].deciding_player_id == "P1"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AllowEffect)))
        assert _find_instance(state, foe.instance_id) is None
        assert foe.instance_id in {
            c.instance_id for c in state.player_by_id("P1").hand}

    def test_LOF_222_refusing_lets_the_controller_play_its_worse_free(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, SayNo, PlayEventFromHand)
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        worse = _put_in_hand(state, "P0", _get_card(repo, "LOF", "264"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "222", resources=10)
        state = apply(state, ChooseTarget(foe.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SayNo)))
        assert _find_instance(state, foe.instance_id) is not None  # not returned
        top = state.pending_decisions[-1]
        assert top.kind == "play_event_from_hand"
        plays = [a for a in legal_actions(state) if isinstance(a, PlayEventFromHand)]
        assert {a.instance_id for a in plays} == {worse.instance_id}
        # It's Worse (cost 7) is played for FREE — no resources are spent.
        spent_before = sum(1 for r in state.player_by_id("P0").resources if r.exhausted)
        state = apply(state, plays[0])
        assert sum(1 for r in state.player_by_id("P0").resources
                   if r.exhausted) == spent_before

    def test_LOF_222_refusing_with_no_copy_does_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, SayNo
        state = _make_state()
        foe = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "222")
        state = apply(state, ChooseTarget(foe.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SayNo)))
        assert _find_instance(state, foe.instance_id) is not None
        assert not any(d.kind == "play_event_from_hand"
                       for d in state.pending_decisions)


class TestTipTheScale_LOF_226:
    """Look at an opponent's hand and discard a non-unit card from it."""

    def test_LOF_226_only_non_unit_names_are_offered(self, repo):
        from swu.engine.actions import legal_actions, apply, NameAndDiscard
        state = _make_state()
        unit = _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        upgrade = _put_in_hand(state, "P1", _get_card(repo, "SOR", "53"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "226")
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "name_and_discard"
        offered = {a.card_name for a in legal_actions(state)
                   if isinstance(a, NameAndDiscard)}
        assert upgrade.card_def.display_name in offered
        assert unit.card_def.display_name not in offered
        state = apply(state, NameAndDiscard(upgrade.card_def.display_name))
        assert upgrade.instance_id in {
            c.instance_id for c in state.player_by_id("P1").discard}

    def test_LOF_226_fizzles_when_the_hand_is_all_units(self, repo):
        state = _make_state()
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state, _evt = _play_event_from_hand(state, repo, "LOF", "226")
        state = _drain_lof(state)
        assert not state.pending_decisions


class TestCaretakerMatron_LOF_243:
    """Action [Exhaust]: If you played a Force card this phase, draw a card."""

    def test_LOF_243_action_armed_by_a_force_card(self, repo):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        matron = _place(state, "P0", _get_card(repo, "LOF", "243"), "ground")
        assert not _use_actions_lof(state, matron)
        force_unit = _put_in_hand(state, "P0", _get_card(repo, "LOF", "196"))
        _give_resources(state, "P0", 10)
        state = apply(state, PlayCard(force_unit.instance_id))
        state.active_player_index = state.player_index("P0")
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))
        matron_now = _find_instance(state, matron.instance_id)
        state = apply(state, _use_actions_lof(state, matron_now)[0])
        assert len(state.player_by_id("P0").hand) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Group ``lof-set:08`` — Combat tricks, buffs & tempo (the LOF leaders)
# ══════════════════════════════════════════════════════════════════════════════

class TestKananJarrus_LOF_4:
    """Action [1 resource, Exhaust]: Shield a Creature or Spectre unit.
    Deployed: +2/+2 while you control another Creature or Spectre unit."""

    def test_LOF_4_action_only_targets_creature_or_spectre(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        kanan = _place_leader(state, "P0", _get_card(repo, "LOF", "4"))
        creature = _place(state, "P0", _get_card(repo, "LOF", "121"), "space")  # Creature
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _give_resources(state, "P0", 5)
        state = apply(state, _use_actions_lof(state, kanan)[0])
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert creature.instance_id in offered
        assert plain.instance_id not in offered
        state = apply(state, ChooseTarget(creature.instance_id))
        assert _shield_count(_find_instance(state, creature.instance_id)) == 1

    def test_LOF_4_deployed_buff_needs_another_creature_or_spectre(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        kanan = _place(state, "P0", _get_card(repo, "LOF", "4"), "ground")
        kanan.deployed = True
        assert compute_power(state, kanan) == 3
        _place(state, "P0", _get_card(repo, "LOF", "121"), "space")  # Creature
        kanan_now = _find_instance(state, kanan.instance_id)
        assert compute_power(state, kanan_now) == 5
        assert compute_hp(state, kanan_now) == 8


class TestMorganElsbeth_LOF_5:
    """Undeployed: play a unit sharing a keyword with one that attacked this phase,
    1 less. Deployed On Attack: the next such unit costs 1 less."""

    def test_LOF_5_action_offers_only_keyword_sharing_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, PlayFromHand
        state = _make_state()
        morgan = _place_leader(state, "P0", _get_card(repo, "LOF", "5"))
        # SOR_101 Rogue Squadron Skirmisher has Ambush — so does SOR_115 Agent Kallus.
        attacker = _place(state, "P0", _get_card(repo, "SOR", "101"), "ground")
        state.game_memory.units_attacked_this_round.add(attacker.instance_id)
        match = _put_in_hand(state, "P0", _get_card(repo, "SOR", "115"))
        miss = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 20)
        state = apply(state, _use_actions_lof(state, morgan)[0])
        state = apply(state, ChooseTarget(attacker.instance_id))
        assert state.pending_decisions[-1].kind == "play_from_hand"
        plays = {a.instance_id for a in legal_actions(state)
                 if isinstance(a, PlayFromHand)}
        assert match.instance_id in plays
        assert miss.instance_id not in plays

    def test_LOF_5_deployed_discount_needs_a_shared_keyword(self, repo):
        from swu.engine.actions import _play_cost
        state = _make_state()
        morgan = _place(state, "P0", _get_card(repo, "LOF", "5"), "ground")
        morgan.deployed = True
        friendly = _place(state, "P0", _get_card(repo, "SOR", "101"), "ground")  # Ambush
        match = _put_in_hand(state, "P0", _get_card(repo, "SOR", "115"))   # Ambush
        miss = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))     # no keyword
        ps = state.player_by_id("P0")
        base_match = _play_cost(state, match, ps)
        base_miss = _play_cost(state, miss, ps)
        state = _fire_on_attack(state, morgan)
        state = _drain_lof(state)
        ps = state.player_by_id("P0")
        assert _play_cost(state, match, ps) == base_match - 1
        assert _play_cost(state, miss, ps) == base_miss


class TestSupremeLeaderSnoke_LOF_6:
    """Give an Experience token to the strongest friendly Villainy unit."""

    def test_LOF_6_action_auto_resolves_onto_the_clear_leader(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        snoke = _place_leader(state, "P0", _get_card(repo, "LOF", "6"))
        big = _place(state, "P0", _get_card(repo, "SOR", "89"), "space")   # Villainy 6/7
        small = _place(state, "P0", _get_card(repo, "SOR", "226"), "ground")  # Villainy 1/5
        _give_resources(state, "P0", 5)
        state = apply(state, _use_actions_lof(state, snoke)[0])
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        if offered:
            assert offered == {big.instance_id}
            state = apply(state, ChooseTarget(big.instance_id))
        assert _experience_count(_find_instance(state, big.instance_id)) == 1
        assert _experience_count(_find_instance(state, small.instance_id)) == 0

    def test_LOF_6_ignores_non_villainy_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        snoke = _place_leader(state, "P0", _get_card(repo, "LOF", "6"))
        heroic = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Heroism
        villain = _place(state, "P0", _get_card(repo, "SOR", "226"), "ground")
        _give_resources(state, "P0", 5)
        state = apply(state, _use_actions_lof(state, snoke)[0])
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        if offered:
            state = apply(state, ChooseTarget(next(iter(offered))))
        assert _experience_count(_find_instance(state, villain.instance_id)) == 1
        assert _experience_count(_find_instance(state, heroic.instance_id)) == 0


class TestAvarKriss_LOF_7:
    """Action [Exhaust]: create your Force token. Deployed: +4/+0 and Overwhelm
    while the Force is with you."""

    def test_LOF_7_action_creates_the_force_token(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        avar = _place_leader(state, "P0", _get_card(repo, "LOF", "7"))
        assert state.player_by_id("P0").has_force_token is False
        state = apply(state, _use_actions_lof(state, avar)[0])
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_7_deployed_buff_tracks_the_force_token(self, repo):
        from swu.engine.actions import compute_power
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        avar = _place(state, "P0", _get_card(repo, "LOF", "7"), "ground")
        avar.deployed = True
        assert compute_power(state, avar) == 4
        assert not has_keyword(state, avar, Keyword.OVERWHELM)
        state.player_by_id("P0").has_force_token = True
        avar_now = _find_instance(state, avar.instance_id)
        assert compute_power(state, avar_now) == 8
        assert has_keyword(state, avar_now, Keyword.OVERWHELM)


class TestObiWanKenobi_LOF_8:
    """Action [Exhaust, use the Force]: Experience onto a unit without one.
    Deployed On Attack: the same, on ANOTHER unit, optionally."""

    def test_LOF_8_action_needs_the_force_and_skips_tokened_units(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.tokens import attach_token
        state = _make_state()
        obi = _place_leader(state, "P0", _get_card(repo, "LOF", "8"))
        assert not _use_actions_lof(state, obi)          # no Force token → no action
        state.player_by_id("P0").has_force_token = True
        bare = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        tokened = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attach_token(state, state.player_by_id("P0"), tokened, "Experience")
        state = apply(state, _use_actions_lof(state, obi)[0])
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert bare.instance_id in offered
        assert tokened.instance_id not in offered
        state = apply(state, ChooseTarget(bare.instance_id))
        assert _experience_count(_find_instance(state, bare.instance_id)) == 1
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_8_deployed_on_attack_excludes_himself(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        obi = _place(state, "P0", _get_card(repo, "LOF", "8"), "ground")
        obi.deployed = True
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, obi)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert obi.instance_id not in offered
        assert other.instance_id in offered


class TestBarrissOffee_LOF_13:
    """Both sides: [use the Force] play an event from hand for 1 less."""

    def test_LOF_13_undeployed_plays_a_discounted_event(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayEventFromHand
        state = _make_state()
        barriss = _place_leader(state, "P0", _get_card(repo, "LOF", "13"))
        assert not _use_actions_lof(state, barriss)      # no Force token
        state.player_by_id("P0").has_force_token = True
        evt = _put_in_hand(state, "P0", _get_card(repo, "LOF", "264"))  # cost 7
        _give_resources(state, "P0", 20)
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent_before = sum(1 for r in state.player_by_id("P0").resources if r.exhausted)
        state = apply(state, _use_actions_lof(state, barriss)[0])
        assert state.pending_decisions[-1].kind == "play_event_from_hand"
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlayEventFromHand)
                    and a.instance_id == evt.instance_id)
        state = apply(state, play)
        spent = sum(1 for r in state.player_by_id("P0").resources
                    if r.exhausted) - spent_before
        assert spent == 6                                 # 7 − 1
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_13_deployed_side_costs_no_exhaust(self, repo):
        state = _make_state()
        barriss = _place(state, "P0", _get_card(repo, "LOF", "13"), "ground")
        barriss.deployed = True
        barriss.exhausted = True                          # no Exhaust cost on this side
        state.player_by_id("P0").has_force_token = True
        _put_in_hand(state, "P0", _get_card(repo, "LOF", "175"))
        _give_resources(state, "P0", 20)
        assert _use_actions_lof(state, barriss)


class TestGrandInquisitor_LOF_14:
    """Action [Exhaust, use the Force]: attack with a friendly unit, defender −2/−0.
    Deployed On Attack: the defender gets −2/−0."""

    def test_LOF_14_action_grants_an_attack_with_a_debuffed_defender(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        gi = _place_leader(state, "P0", _get_card(repo, "LOF", "14"))
        assert not _use_actions_lof(state, gi)            # no Force token
        state.player_by_id("P0").has_force_token = True
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = apply(state, _use_actions_lof(state, gi)[0])
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context.get("defender_power_bonus") == -2
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_14_deployed_on_attack_debuffs_the_defender(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        gi = _place(state, "P0", _get_card(repo, "LOF", "14"), "ground")
        gi.deployed = True
        prey = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_on_attack(state, gi, prey)
        state = _drain_lof(state)
        assert compute_power(state, _find_instance(state, prey.instance_id)) == 1


# ── lof-set:09 — Combat tricks, buffs & tempo ─────────────────────────────────

def _fire_attack_and_defeat(state, attacker_ci, defeated_ci):
    """Mimic the engine's post-combat fire site for OnAttackDefeatsUnit and its
    new group analogue WhenFriendlyUnitAttacksAndDefeatsUnit (actions.py)."""
    from swu.abilities.resolver import fire_triggered_abilities
    return fire_triggered_abilities(
        state, None, after_all_player_idx=0,
        event_ctx={"attack_defeated_unit": attacker_ci.instance_id,
                   "attack_defeated_defender": defeated_ci.instance_id},
    )


class TestCalKestis_LOF_15:
    """An opponent chooses a ready unit they control.  Exhaust that unit."""

    def test_LOF_15_opponent_exhausts_a_ready_unit_they_choose(self, repo):
        from swu.engine.actions import apply, ChooseOwnTarget
        state = _make_state()
        cal = _place(state, "P0", _get_card(repo, "LOF", "15"), "ground")
        cal.deployed = True
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, cal)
        top = state.pending_decisions[-1]
        assert top.kind == "opponent_chooses_target"
        assert top.deciding_player_id == "P1"
        state = apply(state, ChooseOwnTarget(ready.instance_id))
        assert _find_instance(state, ready.instance_id).exhausted is True
        assert not state.pending_decisions

    def test_LOF_15_only_ready_units_are_offered(self, repo):
        from swu.engine.actions import legal_actions, ChooseOwnTarget
        state = _make_state()
        cal = _place(state, "P0", _get_card(repo, "LOF", "15"), "ground")
        cal.deployed = True
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent.exhausted = True
        state = _fire_on_attack(state, cal)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseOwnTarget)}
        assert offered == {ready.instance_id}

    def test_LOF_15_no_ready_enemy_unit_fizzles_without_a_prompt(self, repo):
        state = _make_state()
        cal = _place(state, "P0", _get_card(repo, "LOF", "15"), "ground")
        cal.deployed = True
        spent = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        spent.exhausted = True
        state = _fire_on_attack(state, cal)
        assert not state.pending_decisions


class TestDarthRevan_LOF_17:
    """When a friendly unit attacks and defeats a unit: Experience to it."""

    def test_LOF_17_deployed_gives_experience_to_the_attacker(self, repo):
        state = _make_state()
        revan = _place(state, "P0", _get_card(repo, "LOF", "17"), "ground")
        revan.deployed = True
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_attack_and_defeat(state, attacker, victim)
        state = _accept_optional_and_run(state)
        assert _experience_count(_find_instance(state, attacker.instance_id)) == 1

    def test_LOF_17_undeployed_exhausts_the_leader_to_pay(self, repo):
        state = _make_state()
        revan = _place_leader(state, "P0", _get_card(repo, "LOF", "17"))
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_attack_and_defeat(state, attacker, victim)
        state = _accept_optional_and_run(state)
        assert state.find_instance(revan.instance_id)[1].exhausted is True
        assert _experience_count(_find_instance(state, attacker.instance_id)) == 1

    def test_LOF_17_undeployed_not_offered_while_exhausted(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        revan = _place_leader(state, "P0", _get_card(repo, "LOF", "17"))
        revan.exhausted = True
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_attack_and_defeat(state, attacker, victim)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_LOF_17_does_not_fire_for_an_enemy_attacker(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        revan = _place(state, "P0", _get_card(repo, "LOF", "17"), "ground")
        revan.deployed = True
        enemy_attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_attack_and_defeat(state, enemy_attacker, victim)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestNamelessTerror_LOF_33:
    """When Played: may exhaust a Force unit.  On Attack: enemy units lose Force."""

    def test_LOF_33_when_played_exhausts_a_force_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        terror = _place(state, "P0", _get_card(repo, "LOF", "33"), "ground")
        mystic = _place(state, "P1", _get_card(repo, "LOF", "112"), "ground")  # Force
        plain = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, terror)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert mystic.instance_id in offered
        assert plain.instance_id not in offered
        state = apply(state, ChooseTarget(mystic.instance_id))
        assert _find_instance(state, mystic.instance_id).exhausted is True

    def test_LOF_33_on_attack_strips_the_force_trait_from_enemy_units(self, repo):
        from swu.engine.traits import has_trait
        state = _make_state()
        terror = _place(state, "P0", _get_card(repo, "LOF", "33"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "LOF", "112"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "LOF", "112"), "ground")
        assert has_trait(state, enemy, "Force")
        state = _fire_on_attack(state, terror)
        assert has_trait(state, _find_instance(state, enemy.instance_id), "Force") is False
        # A friendly Force unit is untouched, and the enemy keeps its other traits.
        assert has_trait(state, _find_instance(state, friendly.instance_id), "Force")
        assert has_trait(state, _find_instance(state, enemy.instance_id), "Fringe")


class TestT6Shuttle_LOF_47:
    """When this unit is attacked: you may give an Experience token to it."""

    def test_LOF_47_gives_itself_experience_when_attacked(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "LOF", "47"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, attacker, shuttle)
        state = _accept_optional_and_run(state)
        assert _experience_count(_find_instance(state, shuttle.instance_id)) == 1


class TestItinerantWarrior_LOF_48:
    """When Played: may use the Force; if you do, heal 3 from a base."""

    def test_LOF_48_spends_the_force_token_to_heal_a_base(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        base = state.player_by_id("P0").base_instance
        base.damage = 7
        warrior = _place(state, "P0", _get_card(repo, "LOF", "48"), "ground")
        state = _fire_when_played(state, warrior)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(base.instance_id))
        assert state.find_instance(base.instance_id)[1].damage == 4
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_48_not_offered_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        state.player_by_id("P0").has_force_token = False
        state.player_by_id("P0").base_instance.damage = 7
        warrior = _place(state, "P0", _get_card(repo, "LOF", "48"), "ground")
        state = _fire_when_played(state, warrior)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestJediGuardian_LOF_49:
    """While this unit is defending, it gets +2/+0."""

    def test_LOF_49_gets_plus_2_power_only_while_defending(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "LOF", "49"), "ground")
        assert compute_power(state, guard) == 4
        assert compute_power(state, guard, is_defending=True) == 6


class TestPloKoon_LOF_50:
    """While the Force is with you, this unit gains Grit."""

    def test_LOF_50_gains_grit_only_while_the_force_is_with_you(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.actions import compute_power
        state = _make_state()
        plo = _place(state, "P0", _get_card(repo, "LOF", "50"), "ground")
        plo.damage = 3
        assert has_keyword(state, plo, Keyword.GRIT) is False
        assert compute_power(state, plo) == 6
        state.player_by_id("P0").has_force_token = True
        assert has_keyword(state, plo, Keyword.GRIT) is True
        assert compute_power(state, plo) == 9


# ── lof-set:10 — Combat tricks, buffs & tempo ─────────────────────────────────

def _fire_regroup_start_lof(state):
    """Fire the "regroup phase starts" PhaseStartTrigger site."""
    from swu.engine.events import PhaseChanged
    from swu.abilities.resolver import fire_triggered_abilities
    evt = PhaseChanged(new_phase="REGROUP", round_number=state.round_number)
    state.event_log.append(evt)
    return fire_triggered_abilities(state, evt, after_all_player_idx=0)


class TestJediTrials_LOF_52:
    """Granted On Attack Experience + the 4-upgrade Jedi trait grant."""

    def test_LOF_52_granted_on_attack_gives_the_host_experience(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "112"), "ground")  # Force
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "52"), "P0")
        state = _fire_on_attack(state, host)
        assert _experience_count(_find_instance(state, host.instance_id)) == 1

    def test_LOF_52_grants_jedi_only_at_4_plus_upgrades(self, repo):
        from swu.engine.traits import has_trait
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "LOF", "112"), "ground")  # Force/Fringe
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "52"), "P0")
        assert has_trait(state, host, "Jedi") is False
        for _ in range(3):
            _attach_upgrade_directly(state, host, _get_card(repo, "SOR", "71"), "P0")
        assert len(host.attached_upgrades) == 4
        assert has_trait(state, host, "Jedi") is True


class TestHeirloomLightsaber_LOF_53:
    """If attached unit is a Force unit, it gains Restore 1."""

    def test_LOF_53_grants_restore_only_to_a_force_host(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        force_host = _place(state, "P0", _get_card(repo, "LOF", "112"), "ground")
        plain_host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, force_host, _get_card(repo, "LOF", "53"), "P0")
        _attach_upgrade_directly(state, plain_host, _get_card(repo, "LOF", "53"), "P0")
        assert has_keyword(state, force_host, Keyword.RESTORE) is True
        assert keyword_value(state, force_host, Keyword.RESTORE) == 1
        assert has_keyword(state, plain_host, Keyword.RESTORE) is False


class TestCalmInTheStorm_LOF_54:
    """Exhaust a friendly unit; if you do, Shield + 2 Experience to it."""

    def test_LOF_54_exhausts_and_loads_the_chosen_unit(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        friendly = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "54")
        state = apply(state, ChooseTarget(friendly.instance_id))
        after = _find_instance(state, friendly.instance_id)
        assert after.exhausted is True
        assert _shield_count(after) == 1
        assert _experience_count(after) == 2

    def test_LOF_54_only_ready_friendly_units_are_targetable(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        ready = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        spent = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        spent.exhausted = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "54")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {ready.instance_id}


class TestDume_LOF_55:
    """When the regroup phase starts: Experience to each other friendly
    non-Vehicle unit."""

    def test_LOF_55_tokens_other_friendly_non_vehicles_only(self, repo):
        state = _make_state()
        dume = _place(state, "P0", _get_card(repo, "LOF", "55"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        vehicle = _place(state, "P0", _get_card(repo, "LOF", "60"), "space")  # Vehicle
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_regroup_start_lof(state)
        assert _experience_count(_find_instance(state, ally.instance_id)) == 1
        assert _experience_count(_find_instance(state, dume.instance_id)) == 0
        assert _experience_count(_find_instance(state, vehicle.instance_id)) == 0
        assert _experience_count(_find_instance(state, enemy.instance_id)) == 0


class TestSizeMattersNot_LOF_56:
    """Printed power/HP are considered 5/5; costs 1 less with a Force unit."""

    def test_LOF_56_overrides_the_hosts_printed_stats(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # 3/1
        assert (compute_power(state, host), compute_hp(state, host)) == (3, 1)
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "56"), "P0")
        assert (compute_power(state, host), compute_hp(state, host)) == (5, 5)

    def test_LOF_56_stat_bonuses_still_layer_on_top_of_the_override(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        from swu.engine.tokens import attach_token
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "56"), "P0")
        attach_token(state, state.player_by_id("P0"), host, "Experience")
        assert (compute_power(state, host), compute_hp(state, host)) == (6, 6)

    def test_LOF_56_costs_1_less_while_you_control_a_force_unit(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")
        upg = CardInstance("p0_smn", _get_card(repo, "LOF", "56"), "P0", Zone.HAND)
        state.players[0].hand.append(upg)
        full = _play_cost(state, upg, state.players[0],
                          target_host_id=host.instance_id)
        _place(state, "P0", _get_card(repo, "LOF", "112"), "ground")  # a Force unit
        discounted = _play_cost(state, upg, state.players[0],
                                target_host_id=host.instance_id)
        assert full - discounted == 1


class TestGuardianOfTheWhills_LOF_58:
    """The first upgrade you play on this unit each round costs 1 less."""

    def test_LOF_58_first_upgrade_on_self_costs_less(self, repo):
        from swu.engine.actions import _play_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        guardian = _place(state, "P0", _get_card(repo, "LOF", "58"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = CardInstance("p0_up58", _get_card(repo, "SOR", "71"), "P0", Zone.HAND)
        state.players[0].hand.append(upg)
        on_guardian = _play_cost(state, upg, state.players[0],
                                 target_host_id=guardian.instance_id)
        on_other = _play_cost(state, upg, state.players[0],
                              target_host_id=other.instance_id)
        assert on_other - on_guardian == 1
        state.game_memory.standing_play_discounts_used_this_round.add(
            guardian.instance_id)
        assert _play_cost(state, upg, state.players[0],
                          target_host_id=guardian.instance_id) == on_other


class TestPadawanStarfighter_LOF_60:
    """While you control a Force unit or upgrade, this unit gets +1/+1."""

    def test_LOF_60_buffed_by_a_force_unit_or_a_force_upgrade(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        fighter = _place(state, "P0", _get_card(repo, "LOF", "60"), "space")
        assert (compute_power(state, fighter), compute_hp(state, fighter)) == (1, 3)
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "56"), "P0")  # Force upgrade
        assert (compute_power(state, fighter), compute_hp(state, fighter)) == (2, 4)


# ── lof-set:11 — Combat tricks, buffs & tempo ─────────────────────────────────

class TestTauntaun_LOF_64:
    """When Defeated: you may give a Shield to a damaged non-Vehicle unit."""

    def test_LOF_64_shields_a_damaged_non_vehicle_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        tauntaun = _place(state, "P0", _get_card(repo, "LOF", "64"), "ground")
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 2
        vehicle = _place(state, "P0", _get_card(repo, "LOF", "60"), "space")
        vehicle.damage = 1
        state = _fire_when_defeated(state, tauntaun)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {hurt.instance_id}   # the damaged Vehicle is excluded
        state = apply(state, ChooseTarget(hurt.instance_id))
        assert _shield_count(_find_instance(state, hurt.instance_id)) == 1

    def test_LOF_64_auto_declines_with_no_damaged_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        tauntaun = _place(state, "P0", _get_card(repo, "LOF", "64"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # undamaged
        state = _fire_when_defeated(state, tauntaun)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestPriestessesOfTheForce_LOF_72:
    """When Played: may use the Force; if you do, Shield up to 5 units."""

    def test_LOF_72_spends_the_force_and_shields_chosen_units(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, SelectTokenTarget,
            FinishSelectToken,
        )
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        priest = _place(state, "P0", _get_card(repo, "LOF", "72"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, priest)
        state = _accept_optional_and_run(state)
        assert state.player_by_id("P0").has_force_token is False
        assert state.pending_decisions[-1].kind == "select_token"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == ally.instance_id))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, FinishSelectToken)))
        assert _shield_count(_find_instance(state, ally.instance_id)) == 1

    def test_LOF_72_not_offered_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        priest = _place(state, "P0", _get_card(repo, "LOF", "72"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, priest)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestCureWounds_LOF_75:
    """Use the Force; if you do, heal 6 from a unit."""

    def test_LOF_75_spends_the_force_and_heals_6(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 6
        state, _ = _play_event_from_hand(state, repo, "LOF", "75")
        state = apply(state, ChooseTarget(hurt.instance_id))
        assert _find_instance(state, hurt.instance_id).damage == 0
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_75_no_force_token_means_no_target_and_no_heal(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 6
        state, _ = _play_event_from_hand(state, repo, "LOF", "75")
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))
        assert _find_instance(state, hurt.instance_id).damage == 6


class TestSoresuStance_LOF_76:
    """Play a Force unit from hand (paying its cost) and Shield it."""

    def test_LOF_76_plays_a_force_unit_and_shields_it(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayFromHand, SelectTokenTarget,
        )
        state = _make_state()
        mystic = _put_in_hand(state, "P0", _get_card(repo, "LOF", "112"))  # Force
        plain = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))    # no Force
        state, _ = _play_event_from_hand(state, repo, "LOF", "76", resources=20)
        assert state.pending_decisions[-1].kind == "play_from_hand"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert mystic.instance_id in offered
        assert plain.instance_id not in offered
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, PlayFromHand)
                                  and a.instance_id == mystic.instance_id))
        played = _find_instance(state, mystic.instance_id)
        assert played is not None
        # The Shield rider is a settle payoff restricted to the unit just played.
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)))
        assert _shield_count(_find_instance(state, mystic.instance_id)) == 1


class TestSithLegionnaire_LOF_81:
    """While you control another Villainy unit, this unit gets +2/+0."""

    def test_LOF_81_buffed_only_by_another_villainy_unit(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        legionnaire = _place(state, "P0", _get_card(repo, "LOF", "81"), "ground")
        assert compute_power(state, legionnaire) == 2
        _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # Villainy
        assert compute_power(state, legionnaire) == 4


class TestPraetorianGuard_LOF_85:
    """While you control a unit with 4 or more power, this unit gains Sentinel."""

    def test_LOF_85_gains_sentinel_only_beside_a_4_power_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "LOF", "85"), "ground")
        weak = _place(state, "P0", _get_card(repo, "SOR", "128"), "ground")  # 3 power
        assert has_keyword(state, guard, Keyword.SENTINEL) is False
        big = _place(state, "P0", _get_card(repo, "LOF", "50"), "ground")    # 6 power
        assert has_keyword(state, big, Keyword.SENTINEL) is False
        assert has_keyword(state, guard, Keyword.SENTINEL) is True

    def test_LOF_85_ignores_an_enemy_big_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        guard = _place(state, "P0", _get_card(repo, "LOF", "85"), "ground")
        _place(state, "P1", _get_card(repo, "LOF", "50"), "ground")  # enemy 6 power
        assert has_keyword(state, guard, Keyword.SENTINEL) is False


class TestDrengirSpawn_LOF_86:
    """Experience tokens equal to the defeated unit's cost."""

    def test_LOF_86_experience_equals_the_defeated_units_cost(self, repo):
        state = _make_state()
        spawn = _place(state, "P0", _get_card(repo, "LOF", "86"), "ground")
        victim = _put_in_discard(state, "P1", _get_card(repo, "SOR", "46"))  # cost 4
        state = _fire_attack_and_defeat(state, spawn, victim)
        assert _experience_count(_find_instance(state, spawn.instance_id)) == 4


# ══ lof-set:12 — Combat tricks, buffs & tempo ═════════════════════════════════

class TestEighthBrother_LOF_87:
    """When you play another unit: You may use the Force.  If you do, give a unit
    +2/+2 for this phase."""

    def test_LOF_87_spends_force_and_buffs_the_chosen_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power,
            compute_hp,
        )
        state = _make_state()
        eighth = _place(state, "P0", _get_card(repo, "LOF", "87"), "ground")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state.player_by_id("P0").has_force_token = True
        played = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _fire_card_played(state, played)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == ally.instance_id))
        buffed = _find_instance(state, ally.instance_id)
        assert (compute_power(state, buffed), compute_hp(state, buffed)) == (5, 9)
        assert not state.player_by_id("P0").has_force_token
        assert eighth is not None

    def test_LOF_87_not_offered_without_a_force_token(self, repo):
        """The trigger is gated on the Force token, so with none it never prompts."""
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "87"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = False
        played = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _fire_card_played(state, played)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestSupremacy_LOF_89:
    """Other friendly Vehicle units get +6/+6."""

    def test_LOF_89_buffs_other_friendly_vehicles_only(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        supremacy = _place(state, "P0", _get_card(repo, "LOF", "89"), "space")
        vehicle = _place(state, "P0", _get_card(repo, "LOF", "194"), "space")  # 2/4
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy_vehicle = _place(state, "P1", _get_card(repo, "LOF", "194"), "space")
        assert (compute_power(state, vehicle), compute_hp(state, vehicle)) == (8, 10)
        assert (compute_power(state, trooper), compute_hp(state, trooper)) == (3, 7)
        assert compute_power(state, enemy_vehicle) == 2, "enemy Vehicles unaffected"
        # "Other" — Supremacy does not buff itself.
        assert (compute_power(state, supremacy), compute_hp(state, supremacy)) == (12, 12)


class TestPointRainReclaimer_LOF_92:
    """When Played: If you control a Jedi unit, you may give an Experience token to
    this unit."""

    def test_LOF_92_gives_experience_beside_a_jedi(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "48"), "ground")  # Force/Jedi
        clone = _place(state, "P0", _get_card(repo, "LOF", "92"), "ground")
        state = _fire_when_played(state, clone)
        state = _accept_optional_and_run(state)
        assert _experience_count(_find_instance(state, clone.instance_id)) == 1

    def test_LOF_92_not_offered_without_a_jedi(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel Trooper
        clone = _place(state, "P0", _get_card(repo, "LOF", "92"), "ground")
        state = _fire_when_played(state, clone)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert _experience_count(_find_instance(state, clone.instance_id)) == 0


class TestLorSanTekka_LOF_95:
    """When Defeated: You may give an Experience token to a unique unit."""

    def test_LOF_95_only_unique_units_are_targetable(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        tekka = _place(state, "P0", _get_card(repo, "LOF", "95"), "ground")
        uniq = _place(state, "P0", _get_card(repo, "LOF", "96"), "ground")   # unique
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not
        state = _fire_when_defeated(state, tekka)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert uniq.instance_id in offered
        assert plain.instance_id not in offered
        state = apply(state, ChooseTarget(uniq.instance_id))
        assert _experience_count(_find_instance(state, uniq.instance_id)) == 1


class TestEethKoth_LOF_97:
    """When Defeated: You may use the Force.  If you do, put this card into play as
    a resource."""

    def test_LOF_97_spends_force_to_resource_itself_exhausted(self, repo):
        from tests.test_sor_cards import _defeat_and_fire
        from swu.engine.state import Zone
        state = _make_state()
        koth = _place(state, "P0", _get_card(repo, "LOF", "97"), "ground")
        state.player_by_id("P0").has_force_token = True
        before = len(state.player_by_id("P0").resources)
        state = _defeat_and_fire(state, koth, "P0")
        state = _accept_optional_and_run(state)
        ps = state.player_by_id("P0")
        assert len(ps.resources) == before + 1
        res = ps.resources[-1]
        assert res.instance_id == koth.instance_id
        assert res.zone == Zone.RESOURCES and res.face_down and res.exhausted
        assert all(c.instance_id != koth.instance_id for c in ps.discard)
        assert not ps.has_force_token

    def test_LOF_97_not_offered_without_a_force_token(self, repo):
        from tests.test_sor_cards import _defeat_and_fire
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        koth = _place(state, "P0", _get_card(repo, "LOF", "97"), "ground")
        state.player_by_id("P0").has_force_token = False
        state = _defeat_and_fire(state, koth, "P0")
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert any(c.instance_id == koth.instance_id
                   for c in state.player_by_id("P0").discard)


class TestYodasLightsaber_LOF_102:
    """When Played: You may use the Force.  If you do, heal 3 damage from a base."""

    def test_LOF_102_spends_force_to_heal_a_base(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "102"), "P0")
        base = state.player_by_id("P0").base_zone[0]
        base.damage = 5
        state.player_by_id("P0").has_force_token = True
        state = _fire_upgrade_played(state, saber, host)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(base.instance_id))
        assert state.find_instance(base.instance_id)[1].damage == 2
        assert not state.player_by_id("P0").has_force_token

    def test_LOF_102_not_offered_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        saber = _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "102"), "P0")
        state.player_by_id("P0").base_zone[0].damage = 5
        state.player_by_id("P0").has_force_token = False
        state = _fire_upgrade_played(state, saber, host)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestOppoRancisis_LOF_105:
    """This unit gains Ambush/Grit/Hidden/Overwhelm/Saboteur/Sentinel/Shielded — and
    Raid 2 / Restore 2 — while another friendly unit has that keyword."""

    def test_LOF_105_mirrors_a_keyword_from_another_friendly_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        oppo = _place(state, "P0", _get_card(repo, "LOF", "105"), "ground")
        assert has_keyword(state, oppo, Keyword.AMBUSH) is False, "alone → nothing"
        # Eighth Brother LOF_87 has a printed Ambush.
        _place(state, "P0", _get_card(repo, "LOF", "87"), "ground")
        assert has_keyword(state, oppo, Keyword.AMBUSH) is True
        assert has_keyword(state, oppo, Keyword.SENTINEL) is False, "only what is there"

    def test_LOF_105_ignores_an_enemy_units_keyword(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        oppo = _place(state, "P0", _get_card(repo, "LOF", "105"), "ground")
        _place(state, "P1", _get_card(repo, "LOF", "87"), "ground")  # enemy Ambush
        assert has_keyword(state, oppo, Keyword.AMBUSH) is False

    def test_LOF_105_two_of_them_terminate_and_mirror_nothing(self, repo):
        """Two Oppos ask each other about the same keyword; the reentrancy guard
        makes that terminate, and neither invents a keyword out of nothing."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        a = _place(state, "P0", _get_card(repo, "LOF", "105"), "ground")
        b = _place(state, "P0", _get_card(repo, "LOF", "105"), "ground")
        assert has_keyword(state, a, Keyword.GRIT) is False
        assert has_keyword(state, b, Keyword.GRIT) is False


# ══ lof-set:13 — Combat tricks, buffs & tempo ═════════════════════════════════

class TestAcclamatorAssaultShip_LOF_106:
    """On Attack: You may give another unit +5/+5 for this phase."""

    def test_LOF_106_buffs_another_unit_and_never_itself(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power,
            compute_hp,
        )
        state = _make_state()
        ship = _place(state, "P0", _get_card(repo, "LOF", "106"), "space")
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, ship, enemy)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ship.instance_id not in offered, "'another' excludes itself"
        assert {ally.instance_id, enemy.instance_id} <= offered
        state = apply(state, ChooseTarget(ally.instance_id))
        buffed = _find_instance(state, ally.instance_id)
        assert (compute_power(state, buffed), compute_hp(state, buffed)) == (8, 12)


class TestTerentatek_LOF_118:
    """While an opponent controls a Force unit, this unit gains Ambush."""

    def test_LOF_118_gains_ambush_only_against_a_force_unit(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        tere = _place(state, "P0", _get_card(repo, "LOF", "118"), "ground")
        assert has_keyword(state, tere, Keyword.AMBUSH) is False, "printed bar stripped"
        _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")  # friendly Force
        assert has_keyword(state, tere, Keyword.AMBUSH) is False, "must be an opponent's"
        _place(state, "P1", _get_card(repo, "LOF", "242"), "ground")  # enemy Force
        assert has_keyword(state, tere, Keyword.AMBUSH) is True


class TestNimanStrike_LOF_124:
    """Attack with a Force unit, even if it's exhausted.  +1/+0, no bases."""

    def test_LOF_124_grants_an_exhausted_force_unit_a_baseless_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")  # 0/3
        force_unit.exhausted = True
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # not Force
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "LOF", "124")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["allow_exhausted"] is True
        assert top.context["no_base"] is True
        attacks = [a for a in legal_actions(state) if isinstance(a, AttackWithUnit)]
        assert {a.attacker_id for a in attacks} == {force_unit.instance_id}
        assert all(a.defender_id is not None for a in attacks), "bases are off limits"
        assert plain is not None
        state = apply(state, next(a for a in attacks
                                  if a.defender_id == enemy.instance_id))
        # 0 power + 1 from the event.
        assert _find_instance(state, enemy.instance_id).damage == 1


class TestOverpower_LOF_126:
    """Give a unit +3/+3 and Overwhelm for this phase."""

    def test_LOF_126_buffs_and_grants_overwhelm_to_one_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, compute_power, compute_hp,
        )
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "126")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ChooseTarget)
                                  and a.target_id == ally.instance_id))
        buffed = _find_instance(state, ally.instance_id)
        assert (compute_power(state, buffed), compute_hp(state, buffed)) == (6, 10)
        assert has_keyword(state, buffed, Keyword.OVERWHELM) is True
        # Both landed on the SAME unit — the other one got neither.
        untouched = _find_instance(state, other.instance_id)
        assert compute_power(state, untouched) == 3
        assert has_keyword(state, untouched, Keyword.OVERWHELM) is False


class TestRampage_LOF_127:
    """Each friendly Creature unit gets +2/+2 for this phase."""

    def test_LOF_127_buffs_every_friendly_creature_only(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        creature = _place(state, "P0", _get_card(repo, "LOF", "118"), "ground")  # 5/5
        trooper = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")    # 3/7
        enemy_creature = _place(state, "P1", _get_card(repo, "LOF", "118"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "127")
        buffed = _find_instance(state, creature.instance_id)
        assert (compute_power(state, buffed), compute_hp(state, buffed)) == (7, 7)
        assert compute_power(state, _find_instance(state, trooper.instance_id)) == 3
        assert compute_power(state, _find_instance(state, enemy_creature.instance_id)) == 5


class TestScythe_LOF_135:
    """On Attack: You may give another friendly Inquisitor unit +2/+0."""

    def test_LOF_135_buffs_another_friendly_inquisitor(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_power,
        )
        state = _make_state()
        scythe = _place(state, "P0", _get_card(repo, "LOF", "135"), "space")
        inq = _place(state, "P0", _get_card(repo, "LOF", "87"), "ground")  # Inquisitor 5/7
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, scythe, enemy)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {inq.instance_id}, "another FRIENDLY Inquisitor only"
        state = apply(state, ChooseTarget(inq.instance_id))
        assert compute_power(state, _find_instance(state, inq.instance_id)) == 7

    def test_LOF_135_auto_declines_with_no_other_inquisitor(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        scythe = _place(state, "P0", _get_card(repo, "LOF", "135"), "space")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, scythe, enemy)
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestCinDrallig_LOF_150:
    """When Played: You may play a Lightsaber upgrade from your hand for free on
    this unit.  If you do, ready him."""

    def test_LOF_150_plays_a_free_lightsaber_on_himself_and_readies(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayUpgradeFromHand
        state = _make_state()
        cin = _place(state, "P0", _get_card(repo, "LOF", "150"), "ground")
        cin.exhausted = True  # units enter play exhausted
        saber = _put_in_hand(state, "P0", _get_card(repo, "LOF", "102"))  # Lightsaber
        resources_before = len(state.player_by_id("P0").resources)
        state = _fire_when_played(state, cin)
        top = state.pending_decisions[-1]
        assert top.kind == "play_upgrade_from_hand"
        plays = [a for a in legal_actions(state) if isinstance(a, PlayUpgradeFromHand)]
        assert {a.host_id for a in plays} == {cin.instance_id}, "pinned to this unit"
        state = apply(state, next(a for a in plays
                                  if a.upgrade_id == saber.instance_id))
        host = _find_instance(state, cin.instance_id)
        assert [u.instance_id for u in host.attached_upgrades] == [saber.instance_id]
        assert host.exhausted is False, "'if you do, ready him'"
        assert len(state.player_by_id("P0").resources) == resources_before, "free"

    def test_LOF_150_only_lightsabers_are_offered(self, repo):
        from swu.engine.actions import legal_actions, PlayUpgradeFromHand
        state = _make_state()
        cin = _place(state, "P0", _get_card(repo, "LOF", "150"), "ground")
        saber = _put_in_hand(state, "P0", _get_card(repo, "LOF", "102"))
        other = _put_in_hand(state, "P0", _get_card(repo, "LOF", "52"))  # Jedi Trials
        state = _fire_when_played(state, cin)
        offered = {a.upgrade_id for a in legal_actions(state)
                   if isinstance(a, PlayUpgradeFromHand)}
        assert offered == {saber.instance_id}
        assert other is not None

    def test_LOF_150_declining_leaves_him_exhausted(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, DeclinePlayUpgradeFromHand,
        )
        state = _make_state()
        cin = _place(state, "P0", _get_card(repo, "LOF", "150"), "ground")
        cin.exhausted = True
        _put_in_hand(state, "P0", _get_card(repo, "LOF", "102"))
        state = _fire_when_played(state, cin)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclinePlayUpgradeFromHand)))
        assert _find_instance(state, cin.instance_id).exhausted is True
        assert len(state.player_by_id("P0").hand) == 1, "the saber stays in hand"


# ══ lof-set:14 — Combat tricks, buffs & tempo ═════════════════════════════════

class TestFocusDeterminesReality_LOF_152:
    """Each friendly Force unit gains Raid 1 and Saboteur for this phase."""

    def test_LOF_152_grants_raid_1_and_saboteur_to_friendly_force_units(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_force = _place(state, "P1", _get_card(repo, "LOF", "242"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "152")
        buffed = _find_instance(state, force_unit.instance_id)
        assert keyword_value(state, buffed, Keyword.RAID) == 1
        assert has_keyword(state, buffed, Keyword.SABOTEUR) is True
        assert not has_keyword(state, _find_instance(state, plain.instance_id),
                               Keyword.SABOTEUR)
        assert not has_keyword(state, _find_instance(state, enemy_force.instance_id),
                               Keyword.SABOTEUR)


class TestPazVizsla_LOF_153:
    """This unit gets +2/+0 for each damage on him."""

    def test_LOF_153_gains_2_power_per_damage_on_himself(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        paz = _place(state, "P0", _get_card(repo, "LOF", "153"), "ground")  # 3/6
        assert (compute_power(state, paz), compute_hp(state, paz)) == (3, 6)
        paz.damage = 2
        assert compute_power(state, paz) == 7
        assert compute_hp(state, paz) == 6, "HP is untouched — the buff is +2/+0"
        # Another damaged unit does not feed him: the count is read off HIM.
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other.damage = 3
        assert compute_power(state, paz) == 7


class TestBlockadeRunner_LOF_166:
    """When this unit deals combat damage to a base: You may give an Experience
    token to this unit."""

    def test_LOF_166_gives_itself_experience_after_hitting_a_base(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "LOF", "166"), "space")
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": runner.instance_id})
        state = _accept_optional_and_run(state)
        assert _experience_count(_find_instance(state, runner.instance_id)) == 1

    def test_LOF_166_does_not_fire_for_another_units_base_hit(self, repo):
        from swu.abilities.resolver import fire_triggered_abilities
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        runner = _place(state, "P0", _get_card(repo, "LOF", "166"), "space")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"dealt_combat_damage_to_base": other.instance_id})
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))
        assert _experience_count(_find_instance(state, runner.instance_id)) == 0


class TestInvasionControlShip_LOF_169:
    """Friendly Droid units gain Raid 2."""

    def test_LOF_169_grants_raid_2_to_friendly_droids_only(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "169"), "space")
        droid = _place(state, "P0", _get_card(repo, "SOR", "59"), "ground")   # Droid
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_droid = _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        assert keyword_value(state, droid, Keyword.RAID) == 2
        assert keyword_value(state, plain, Keyword.RAID) == 0
        assert keyword_value(state, enemy_droid, Keyword.RAID) == 0


class TestUnleashRage_LOF_173:
    """Use the Force.  If you do, give a friendly unit +3/+0 for this phase."""

    def test_LOF_173_spends_the_force_to_buff_a_friendly_unit(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, ChooseTarget, compute_power, compute_hp,
        )
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = True
        state, _evt = _play_event_from_hand(state, repo, "LOF", "173")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert enemy.instance_id not in offered, "friendly only"
        state = apply(state, ChooseTarget(ally.instance_id))
        buffed = _find_instance(state, ally.instance_id)
        assert (compute_power(state, buffed), compute_hp(state, buffed)) == (6, 7)
        assert not state.player_by_id("P0").has_force_token

    def test_LOF_173_no_force_token_means_no_buff(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = False
        state, _evt = _play_event_from_hand(state, repo, "LOF", "173")
        choose = next((a for a in legal_actions(state) if isinstance(a, ChooseTarget)
                       and a.target_id == ally.instance_id), None)
        if choose is not None:
            state = apply(state, choose)
        assert compute_power(state, _find_instance(state, ally.instance_id)) == 3


class TestAtaruOnslaught_LOF_174:
    """Ready a Force unit with 4 or less power."""

    def test_LOF_174_readies_only_a_small_force_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        small = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")  # Force 0/3
        small.exhausted = True
        big = _place(state, "P0", _get_card(repo, "LOF", "50"), "ground")     # Force 6 power
        big.exhausted = True
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Force
        plain.exhausted = True
        state, _evt = _play_event_from_hand(state, repo, "LOF", "174")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert small.instance_id in offered
        assert big.instance_id not in offered, "6 power is over the cap"
        assert plain.instance_id not in offered, "not a Force unit"
        state = apply(state, ChooseTarget(small.instance_id))
        assert _find_instance(state, small.instance_id).exhausted is False


class TestAdeptOfAnger_LOF_178:
    """Action [Exhaust, use the Force]: Exhaust a unit."""

    def test_LOF_178_costs_the_force_token_and_exhausts_a_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        adept = _place(state, "P0", _get_card(repo, "LOF", "178"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert not _use_actions_lof(state, adept), "no Force token → no action"
        state.player_by_id("P0").has_force_token = True
        state = apply(state, _use_actions_lof(state, adept)[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert _find_instance(state, adept.instance_id).exhausted is True, "cost"
        assert not state.player_by_id("P0").has_force_token
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))


# ══ lof-set:15 — Combat tricks, buffs & tempo ═════════════════════════════════

class TestDeceptiveShade_LOF_180:
    """When Defeated: The next unit you play this phase gains Ambush."""

    def test_LOF_180_arms_ambush_for_the_next_unit_played(self, repo):
        from tests.test_sor_cards import _defeat_and_fire
        from swu.engine.actions import _put_unit_in_play
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        shade = _place(state, "P0", _get_card(repo, "LOF", "180"), "ground")
        state = _defeat_and_fire(state, shade, "P0")
        state = _drain_lof(state)
        assert len(state.game_memory.pending_keyword_grants) == 1
        nxt = CardInstance("P0_next", _get_card(repo, "SOR", "46"), "P0", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P0"), nxt)
        assert has_keyword(state, nxt, Keyword.AMBUSH) is True
        assert not state.game_memory.pending_keyword_grants, "one unit only"
        # The unit AFTER it gets nothing.
        later = CardInstance("P0_later", _get_card(repo, "SOR", "46"), "P0", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P0"), later)
        assert has_keyword(state, later, Keyword.AMBUSH) is False

    def test_LOF_180_does_not_arm_the_opponents_plays(self, repo):
        from tests.test_sor_cards import _defeat_and_fire
        from swu.engine.actions import _put_unit_in_play
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        shade = _place(state, "P0", _get_card(repo, "LOF", "180"), "ground")
        state = _defeat_and_fire(state, shade, "P0")
        state = _drain_lof(state)
        theirs = CardInstance("P1_next", _get_card(repo, "SOR", "46"), "P1", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P1"), theirs)
        assert has_keyword(state, theirs, Keyword.AMBUSH) is False
        assert len(state.game_memory.pending_keyword_grants) == 1, "still armed"


class TestPremonitionOfDoom_LOF_203:
    """The next time you take the initiative this phase, exhaust all units."""

    def test_LOF_203_exhausts_all_units_when_you_claim_initiative(self, repo):
        from swu.engine.actions import apply, ClaimInitiative
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "203")
        assert len(state.game_memory.pending_initiative_effects) == 1
        assert not _find_instance(state, mine.instance_id).exhausted
        state.active_player_index = state.player_index("P0")
        state = apply(state, ClaimInitiative())
        assert _find_instance(state, mine.instance_id).exhausted is True
        assert _find_instance(state, theirs.instance_id).exhausted is True
        assert not state.game_memory.pending_initiative_effects, "one shot"

    def test_LOF_203_does_not_fire_for_the_opponents_claim(self, repo):
        from swu.engine.actions import apply, ClaimInitiative
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "203")
        state.active_player_index = state.player_index("P1")
        state = apply(state, ClaimInitiative())
        assert _find_instance(state, mine.instance_id).exhausted is False
        assert len(state.game_memory.pending_initiative_effects) == 1


class TestForceSpeed_LOF_205:
    """Attack with a unit.  For this attack it gains: 'On Attack: Return any number
    of non-unique upgrades attached to the defender to their owners' hands.'"""

    def test_LOF_205_returns_the_defenders_non_unique_upgrades_before_damage(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, SelectTokenTarget,
            FinishSelectToken,
        )
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        plain = _attach_upgrade_directly(state, defender,
                                         _get_card(repo, "LOF", "52"), "P1")  # non-uq
        unique = _attach_upgrade_directly(state, defender,
                                          _get_card(repo, "LOF", "102"), "P1")  # uq
        state, _evt = _play_event_from_hand(state, repo, "LOF", "205")
        assert state.pending_decisions[-1].kind == "granted_attack"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.defender_id == defender.instance_id))
        top = state.pending_decisions[-1]
        assert top.kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert offered == {plain.instance_id}, "non-unique upgrades only"
        state = apply(state, SelectTokenTarget(plain.instance_id))
        # The lone candidate exhausts ``max_targets``, so the decision settles itself.
        finish = next((a for a in legal_actions(state)
                       if isinstance(a, FinishSelectToken)), None)
        if finish is not None:
            state = apply(state, finish)
        hand_ids = {c.instance_id for c in state.player_by_id("P1").hand}
        assert plain.instance_id in hand_ids
        host = _find_instance(state, defender.instance_id)
        assert [u.instance_id for u in host.attached_upgrades] == [unique.instance_id]

    def test_LOF_205_no_prompt_when_the_defender_has_no_such_upgrade(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "205")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.defender_id == defender.instance_id))
        assert not any(d.kind == "select_token" for d in state.pending_decisions)
        assert _find_instance(state, defender.instance_id).damage == 3


class TestBabuFrik_LOF_206:
    """Action [Exhaust]: attack with a friendly Droid unit; it deals damage equal to
    its remaining HP instead of its power."""

    def test_LOF_206_droid_deals_its_remaining_hp_as_damage(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        babu = _place(state, "P0", _get_card(repo, "LOF", "206"), "ground")
        droid = _place(state, "P0", _get_card(repo, "SOR", "59"), "ground")  # 1/3
        droid.damage = 1  # remaining HP 2
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = apply(state, _use_actions_lof(state, babu)[0])
        assert state.pending_decisions[-1].kind == "granted_attack"
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {droid.instance_id}, "friendly Droid units only"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.defender_id == defender.instance_id))
        # 2 remaining HP, not its printed power of 1.
        assert _find_instance(state, defender.instance_id).damage == 2
        assert _find_instance(state, babu.instance_id).exhausted is True


class TestLifeWindSage_LOF_212:
    """While an enemy unit is exhausted, this unit gains Raid 2."""

    def test_LOF_212_gains_raid_2_only_beside_an_exhausted_enemy(self, repo):
        from swu.engine.keywords import has_keyword, keyword_value, Keyword
        state = _make_state()
        sage = _place(state, "P0", _get_card(repo, "LOF", "212"), "ground")
        friend = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        friend.exhausted = True
        assert has_keyword(state, sage, Keyword.RAID) is False, "friendlies don't count"
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, sage, Keyword.RAID) is False, "a ready enemy is not it"
        enemy.exhausted = True
        assert keyword_value(state, sage, Keyword.RAID) == 2


# ══ lof-set:16 — Combat tricks, buffs & tempo ═════════════════════════════════

class TestAscensionCable_LOF_215:
    """Attached unit gains Saboteur."""

    def test_LOF_215_gives_its_host_saboteur(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert has_keyword(state, host, Keyword.SABOTEUR) is False
        _attach_upgrade_directly(state, host, _get_card(repo, "LOF", "215"), "P0")
        assert has_keyword(state, host, Keyword.SABOTEUR) is True
        assert has_keyword(state, other, Keyword.SABOTEUR) is False


class TestDisturbanceInTheForce_LOF_216:
    """If a friendly unit left play this phase: create your Force token and you may
    give a Shield to a unit."""

    def test_LOF_216_creates_the_force_token_and_offers_a_shield(self, repo):
        from tests.test_sor_cards import _defeat_and_fire
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        doomed = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        ally = _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state = _defeat_and_fire(state, doomed, "P0")
        state = _drain_lof(state)
        # ``_defeat_and_fire`` mimics the trigger fire, not _defeat_unit's ledger.
        state.game_memory.defeated_controllers_this_round.append("P0")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "216")
        assert state.player_by_id("P0").has_force_token is True
        assert state.pending_decisions[-1].kind == "select_token"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == ally.instance_id))
        assert _shield_count(_find_instance(state, ally.instance_id)) == 1

    def test_LOF_216_does_nothing_with_no_unit_lost(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "242"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "216")
        assert state.player_by_id("P0").has_force_token is False
        assert not state.pending_decisions, "no gate, no prompt"


class TestShienFlurry_LOF_220:
    """Play a Force unit from hand.  It gains Ambush, and the next damage it would
    take this phase is reduced by 2."""

    def test_LOF_220_plays_a_force_unit_with_ambush_and_a_one_shot_shield(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, PlayFromHand, _deal_damage_with_shield,
        )
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        force_unit = _put_in_hand(state, "P0", _get_card(repo, "LOF", "48"))  # Force
        plain = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 12)
        state, _evt = _play_event_from_hand(state, repo, "LOF", "220")
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayFromHand)}
        assert offered == {force_unit.instance_id}, "Force units only"
        assert plain is not None
        state = apply(state, PlayFromHand(force_unit.instance_id))
        state = _drain_lof(state)
        played = _find_instance(state, force_unit.instance_id)
        assert has_keyword(state, played, Keyword.AMBUSH) is True
        # Itinerant Warrior is Shielded, so strip the shield first to see the
        # prevention itself.
        from swu.engine.tokens import defeat_shield
        while _shield_count(played) > 0:
            defeat_shield(state, played)
        _deal_damage_with_shield(state, state.player_by_id("P0"), played, 3)
        assert played.damage == 1, "2 of the 3 prevented"
        _deal_damage_with_shield(state, state.player_by_id("P0"), played, 3)
        assert played.damage == 4, "one shot only"


class TestTrustYourInstincts_LOF_221:
    """Use the Force.  If you do, attack with a unit: +2/+0 and First Strike."""

    def test_LOF_221_spends_the_force_for_a_first_strike_attack(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = True
        state, _evt = _play_event_from_hand(state, repo, "LOF", "221")
        top = state.pending_decisions[-1]
        assert top.kind == "granted_attack"
        assert top.context["power_bonus"] == 2
        assert "First Strike" in top.context["grant_keywords"]
        assert not state.player_by_id("P0").has_force_token
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id == defender.instance_id))
        assert _find_instance(state, defender.instance_id).damage == 5

    def test_LOF_221_no_force_token_no_attack(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = False
        state, _evt = _play_event_from_hand(state, repo, "LOF", "221")
        assert not any(d.kind == "granted_attack" for d in state.pending_decisions)


class TestForceIllusion_LOF_223:
    """Exhaust an enemy unit.  A friendly unit gains Sentinel for this phase."""

    def test_LOF_223_exhausts_an_enemy_and_shields_a_friendly_with_sentinel(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "223")
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {enemy.instance_id}, "the exhaust is enemy-only"
        state = apply(state, ChooseTarget(enemy.instance_id))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {ally.instance_id}, "the Sentinel grant is friendly-only"
        state = apply(state, ChooseTarget(ally.instance_id))
        assert _find_instance(state, enemy.instance_id).exhausted is True
        assert has_keyword(state, _find_instance(state, ally.instance_id),
                           Keyword.SENTINEL) is True


class TestPounce_LOF_224:
    """Attack with a Creature unit.  It gets +4/+0 for this attack."""

    def test_LOF_224_only_a_creature_attacks_and_it_hits_for_four_more(self, repo):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        state = _make_state()
        creature = _place(state, "P0", _get_card(repo, "LOF", "118"), "ground")  # 5/5
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state, _evt = _play_event_from_hand(state, repo, "LOF", "224")
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert attackers == {creature.instance_id}
        assert plain is not None
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.defender_id == defender.instance_id))
        # 5 power + 4 = 9, well past the defender's 7 HP.
        assert _find_instance(state, defender.instance_id) is None
        assert any(c.instance_id == defender.instance_id
                   for c in state.player_by_id("P1").discard)


class TestThreeLessons_LOF_225:
    """Play a unit from hand.  It gains Hidden, plus an Experience and a Shield."""

    def test_LOF_225_played_unit_gets_hidden_and_both_tokens(self, repo):
        from swu.engine.actions import apply, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 12)
        state, _evt = _play_event_from_hand(state, repo, "LOF", "225")
        assert state.pending_decisions[-1].kind == "play_from_hand"
        state = apply(state, PlayFromHand(unit.instance_id))
        state = _drain_lof(state)
        played = _find_instance(state, unit.instance_id)
        assert has_keyword(state, played, Keyword.HIDDEN) is True
        assert _experience_count(played) == 1
        assert _shield_count(played) == 1


# ══ lof-set:17 — Combat tricks, buffs & tempo ═════════════════════════════════

class TestTheSon_LOF_237:
    """While the Force is with you, each friendly unit gets +2/+0."""

    def test_LOF_237_buffs_every_friendly_unit_only_with_the_force(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        son = _place(state, "P0", _get_card(repo, "LOF", "237"), "ground")   # 6/8
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        assert compute_power(state, ally) == 3
        state.player_by_id("P0").has_force_token = True
        assert (compute_power(state, ally), compute_hp(state, ally)) == (5, 7)
        assert compute_power(state, son) == 8, "'each friendly' includes himself"
        assert compute_power(state, enemy) == 3, "enemies unaffected"


class TestInTheShadows_LOF_241:
    """Give an Experience token to each of up to 3 friendly units with Hidden."""

    def test_LOF_241_only_friendly_hidden_units_are_offered(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        hidden = _place(state, "P0", _get_card(repo, "LOF", "191"), "ground")  # Hidden
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_hidden = _place(state, "P1", _get_card(repo, "LOF", "191"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "241")
        assert state.pending_decisions[-1].kind == "select_token"
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, SelectTokenTarget)}
        assert offered == {hidden.instance_id}
        assert plain is not None and enemy_hidden is not None
        state = apply(state, SelectTokenTarget(hidden.instance_id))
        assert _experience_count(_find_instance(state, hidden.instance_id)) == 1


class TestJediVector_LOF_244:
    """+1/+0 for another Jedi unit, +1/+0 for a Lightsaber upgrade — they stack."""

    def test_LOF_244_each_clause_adds_one_power(self, repo):
        from swu.engine.actions import compute_power
        state = _make_state()
        vector = _place(state, "P0", _get_card(repo, "LOF", "244"), "space")  # 1/3
        assert compute_power(state, vector) == 1, "alone — neither clause"
        jedi = _place(state, "P0", _get_card(repo, "LOF", "48"), "ground")  # Force/Jedi
        assert compute_power(state, vector) == 2, "another Jedi unit"
        _attach_upgrade_directly(state, jedi, _get_card(repo, "LOF", "102"), "P0")
        assert compute_power(state, vector) == 3, "…and a Lightsaber upgrade"


class TestMedicalFrigate_LOF_250:
    """On Attack: You may heal 2 damage from another unit."""

    def test_LOF_250_heals_another_unit_but_never_itself(self, repo):
        from swu.engine.actions import legal_actions, apply, AcceptTrigger, ChooseTarget
        state = _make_state()
        frigate = _place(state, "P0", _get_card(repo, "LOF", "250"), "space")
        frigate.damage = 3
        hurt = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        hurt.damage = 3
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, frigate, enemy)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert frigate.instance_id not in offered, "'another' excludes itself"
        state = apply(state, ChooseTarget(hurt.instance_id))
        assert _find_instance(state, hurt.instance_id).damage == 1


class TestTheDaughter_LOF_252:
    """When damage is dealt to your base: you may spend the Force to heal 2."""

    def test_LOF_252_heals_your_base_after_it_takes_damage(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AttackWithUnit, _fire_base_damage_observers,
        )
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "252"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3
        state.player_by_id("P0").has_force_token = True
        state.active_player_index = state.player_index("P1")
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AttackWithUnit)
                                  and a.attacker_id == attacker.instance_id
                                  and a.defender_id is None))
        state = _fire_base_damage_observers(state)
        state = _accept_optional_and_run(state)
        assert state.player_by_id("P0").base_instance.damage == 1, "3 dealt, 2 healed"
        assert not state.player_by_id("P0").has_force_token

    def test_LOF_252_not_offered_without_a_force_token(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "252"), "ground")
        state.player_by_id("P0").has_force_token = False
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"base_damaged_player_id": "P0"})
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))

    def test_LOF_252_ignores_damage_to_the_enemy_base(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        from swu.abilities.resolver import fire_triggered_abilities
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "252"), "ground")
        state.player_by_id("P0").has_force_token = True
        state = fire_triggered_abilities(
            state, None, after_all_player_idx=0,
            event_ctx={"base_damaged_player_id": "P1"})
        assert not any(isinstance(a, AcceptTrigger) for a in legal_actions(state))


class TestPeliMotto_LOF_258:
    """On Attack: Give an Experience token to a friendly Vehicle or Droid unit."""

    def test_LOF_258_offers_vehicles_and_droids_but_nothing_else(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        peli = _place(state, "P0", _get_card(repo, "LOF", "258"), "ground")
        vehicle = _place(state, "P0", _get_card(repo, "LOF", "194"), "space")  # Vehicle
        droid = _place(state, "P0", _get_card(repo, "SOR", "59"), "ground")    # Droid
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy_droid = _place(state, "P1", _get_card(repo, "SOR", "59"), "ground")
        defender = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, peli, defender)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {vehicle.instance_id, droid.instance_id}
        assert plain is not None and enemy_droid is not None
        state = apply(state, ChooseTarget(droid.instance_id))
        assert _experience_count(_find_instance(state, droid.instance_id)) == 1


class TestLastWords_LOF_263:
    """If a friendly unit was defeated this phase, give 2 Experience to a unit."""

    def test_LOF_263_gives_two_experience_after_a_friendly_loss(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectTokenTarget
        state = _make_state()
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.defeated_controllers_this_round.append("P0")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "263")
        assert state.pending_decisions[-1].kind == "select_token"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, SelectTokenTarget)
                                  and a.target_id == ally.instance_id))
        assert _experience_count(_find_instance(state, ally.instance_id)) == 2

    def test_LOF_263_does_nothing_with_no_friendly_loss(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state, _evt = _play_event_from_hand(state, repo, "LOF", "263")
        assert not state.pending_decisions, "no gate, no prompt"


# ══ lof-set:18 — Miscellaneous abilities ══════════════════════════════════════

class TestMotherTalzin_LOF_2:
    """Undeployed Action [Exhaust, use the Force]: give a unit −1/−1.  Deployed On
    Attack: you may do the same."""

    def test_LOF_2_undeployed_action_costs_the_force_and_debuffs(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, compute_power
        state = _make_state()
        talzin = _place_leader(state, "P0", _get_card(repo, "LOF", "2"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        assert not _use_actions_lof(state, talzin), "no Force token → no action"
        state.player_by_id("P0").has_force_token = True
        state = apply(state, _use_actions_lof(state, talzin)[0])
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert compute_power(state, _find_instance(state, enemy.instance_id)) == 2
        assert not state.player_by_id("P0").has_force_token
        assert not any(isinstance(a, ChooseTarget) for a in legal_actions(state))

    def test_LOF_2_deployed_on_attack_needs_no_force(self, repo):
        from swu.engine.actions import (
            legal_actions, apply, AcceptTrigger, ChooseTarget, compute_hp,
        )
        state = _make_state()
        talzin = _place(state, "P0", _get_card(repo, "LOF", "2"), "ground")
        talzin.deployed = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = False
        state = _fire_on_attack(state, talzin, enemy)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, AcceptTrigger)))
        state = apply(state, ChooseTarget(enemy.instance_id))
        assert compute_hp(state, _find_instance(state, enemy.instance_id)) == 6


class TestAhsokaTano_LOF_3:
    """Undeployed Action [Exhaust, use the Force] / deployed On Attack: give a
    friendly unit Sentinel for this phase."""

    def test_LOF_3_undeployed_action_grants_a_friendly_sentinel(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        ahsoka = _place_leader(state, "P0", _get_card(repo, "LOF", "3"))
        ally = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.player_by_id("P0").has_force_token = True
        state = apply(state, _use_actions_lof(state, ahsoka)[0])
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert enemy.instance_id not in offered, "friendly only"
        state = apply(state, ChooseTarget(ally.instance_id))
        assert has_keyword(state, _find_instance(state, ally.instance_id),
                           Keyword.SENTINEL) is True
        assert not state.player_by_id("P0").has_force_token


class TestThirdSister_LOF_10:
    """Undeployed Action [Exhaust]: play a unit from hand, it gains Hidden.
    Deployed On Attack: the next unit you play this phase gains Hidden."""

    def test_LOF_10_undeployed_plays_a_unit_that_gains_hidden(self, repo):
        from swu.engine.actions import apply, PlayFromHand
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        sister = _place_leader(state, "P0", _get_card(repo, "LOF", "10"))
        unit = _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 12)
        state = apply(state, _use_actions_lof(state, sister)[0])
        assert state.pending_decisions[-1].kind == "play_from_hand"
        state = apply(state, PlayFromHand(unit.instance_id))
        state = _drain_lof(state)
        assert has_keyword(state, _find_instance(state, unit.instance_id),
                           Keyword.HIDDEN) is True

    def test_LOF_10_deployed_on_attack_arms_the_next_play(self, repo):
        from swu.engine.actions import _put_unit_in_play
        from swu.engine.keywords import has_keyword, Keyword
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        sister = _place(state, "P0", _get_card(repo, "LOF", "10"), "ground")
        sister.deployed = True
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_on_attack(state, sister, enemy)
        state = _drain_lof(state)
        assert len(state.game_memory.pending_keyword_grants) == 1
        nxt = CardInstance("P0_next", _get_card(repo, "SOR", "46"), "P0", Zone.HAND)
        _put_unit_in_play(state, state.player_by_id("P0"), nxt)
        assert has_keyword(state, nxt, Keyword.HIDDEN) is True


class TestAnakinSkywalker_LOF_18:
    """Action [Exhaust, use the Force]: play a Villainy non-unit card from hand,
    ignoring its aspect penalties."""

    def _villainy_event(self, state, repo):
        # I Am Your Father SOR_233 is a Villainy event.
        return _put_in_hand(state, "P0", _get_card(repo, "SOR", "233"))

    def test_LOF_18_undeployed_plays_a_villainy_event_for_the_force(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayEventFromHand
        state = _make_state()
        anakin = _place_leader(state, "P0", _get_card(repo, "LOF", "18"))
        villainy = self._villainy_event(state, repo)
        heroic = _put_in_hand(state, "P0", _get_card(repo, "SOR", "152"))
        _give_resources(state, "P0", 12)
        assert not _use_actions_lof(state, anakin), "no Force token → no action"
        state.player_by_id("P0").has_force_token = True
        state = apply(state, _use_actions_lof(state, anakin)[0])
        top = state.pending_decisions[-1]
        assert top.kind == "play_event_from_hand"
        assert top.context["ignore_aspect_penalty"] is True
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, PlayEventFromHand)}
        assert offered == {villainy.instance_id}, "Villainy events only"
        assert heroic is not None
        assert not state.player_by_id("P0").has_force_token

    def test_LOF_18_ignores_the_aspect_penalty_when_paying(self, repo):
        from swu.engine.actions import apply, PlayEventFromHand, _play_cost
        state = _make_state()
        anakin = _place_leader(state, "P0", _get_card(repo, "LOF", "18"))
        villainy = self._villainy_event(state, repo)
        _give_resources(state, "P0", 12)
        state.player_by_id("P0").has_force_token = True
        ps = state.player_by_id("P0")
        full_cost = _play_cost(state, villainy, ps)
        printed = villainy.card_def.cost
        assert full_cost > printed, "the synthetic base pays an aspect penalty"
        before = ps.available_resources
        state = apply(state, _use_actions_lof(state, anakin)[0])
        state = apply(state, PlayEventFromHand(villainy.instance_id))
        spent = before - state.player_by_id("P0").available_resources
        assert spent == printed, "the whole aspect penalty was waived"


class TestVergenceTemple_LOF_19:
    """When the regroup phase starts: if you control a unit with 4+ remaining HP,
    create your Force token."""

    def test_LOF_19_needs_a_unit_with_four_remaining_hp(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "19"))
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        unit.damage = 5  # 2 remaining
        state = _fire_regroup_start_lof(state)
        assert state.player_by_id("P0").has_force_token is False
        unit.damage = 3  # 4 remaining
        state = _fire_regroup_start_lof(state)
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_19_ignores_the_opponents_healthy_units(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "19"))
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy 3/7
        state = _fire_regroup_start_lof(state)
        assert state.player_by_id("P0").has_force_token is False


class TestNightsisterLair_LOF_20:
    """When a friendly Force unit attacks: create your Force token."""

    def test_LOF_20_friendly_force_attack_creates_the_token(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "20"))
        force_unit = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        state = _fire_attack_declared(state, force_unit)
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_20_a_non_force_attacker_does_nothing(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "20"))
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_attack_declared(state, plain)
        assert state.player_by_id("P0").has_force_token is False


class TestMysticMonastery_LOF_22:
    """Action: create your Force token — no more than 3 times each game."""

    def test_LOF_22_runs_out_after_three_uses_in_a_game(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "22"))
        base = state.player_by_id("P0").base_zone[0]
        for i in range(3):
            acts = _use_actions_lof(state, base)
            assert acts, f"use {i + 1} should still be offered"
            state = apply(state, acts[0])
            state = _drain_lof(state)
            assert state.player_by_id("P0").has_force_token is True
            state.player_by_id("P0").has_force_token = False  # spend it
            state.active_player_index = state.player_index("P0")
        assert not _use_actions_lof(state, base), "the 4th use is gone for the game"


# ── lof-set:19 — Force-token Bases ────────────────────────────────────────────


class TestForceTokenBases_LOF_24_26_27_29_30:
    """LOF_24 / 26 / 27 / 29 / 30 — five Bases whose text is Jedi Temple LOF_23
    verbatim: "When a friendly Force unit attacks: create your Force token"."""

    def _attacks(self, repo, base_num, attacker_num):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", base_num))
        attacker = _place(state, "P0", _get_card(repo, "LOF", attacker_num), "ground")
        state = _fire_attack_declared(state, attacker)
        return state

    def test_LOF_24_starlight_temple_creates_the_token(self, repo):
        state = self._attacks(repo, "24", "196")  # LOF_196 Jedi Sentinel = Force
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_26_fortress_vader_creates_the_token(self, repo):
        state = self._attacks(repo, "26", "196")
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_27_strangled_cliffs_creates_the_token(self, repo):
        state = self._attacks(repo, "27", "196")
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_29_crystal_caves_creates_the_token(self, repo):
        state = self._attacks(repo, "29", "196")
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_30_the_holy_city_creates_the_token(self, repo):
        state = self._attacks(repo, "30", "196")
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_24_a_non_force_attacker_does_nothing(self, repo):
        """The Force-trait filter really bites (guards all five registrations)."""
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "24"))
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_attack_declared(state, plain)
        assert state.player_by_id("P0").has_force_token is False


class TestTempleOfDestruction_LOF_25:
    """When a friendly unit deals 3 or more combat damage to an enemy base:
    create your Force token."""

    def _attack_enemy_base(self, state, attacker):
        from swu.engine.actions import legal_actions, apply, AttackWithUnit
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id and a.defender_id is None)
        return apply(state, atk)

    def test_LOF_25_three_damage_to_the_enemy_base_creates_the_token(self, repo):
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "25"))
        hitter = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3 power
        state = self._attack_enemy_base(state, hitter)
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_25_below_the_threshold_does_nothing(self, repo):
        """A 2-power attacker clears the base-damage step but misses min_amount=3."""
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "25"))
        weak = _place(state, "P0", _get_card(repo, "LOF", "112"), "ground")
        from swu.engine.actions import compute_power
        assert compute_power(state, weak) < 3
        state = self._attack_enemy_base(state, weak)
        assert state.player_by_id("P0").has_force_token is False

    def test_LOF_25_an_enemy_unit_hitting_your_base_does_nothing(self, repo):
        """The observer filter is controller="friendly" — P1 smashing P0's base is
        not "a friendly unit … an enemy base"."""
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "25"))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.active_player_index = state.player_index("P1")
        state = self._attack_enemy_base(state, enemy)
        assert state.player_by_id("P0").has_force_token is False


class TestTombOfEilram_LOF_28:
    """Action [exhaust a friendly unit]: create your Force token."""

    def test_LOF_28_exhausts_the_chosen_unit_and_creates_the_token(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "28"))
        base = state.player_by_id("P0").base_zone[0]
        unit = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        acts = _use_actions_lof(state, base)
        assert acts, "the Action is offered while a ready friendly unit exists"
        state = apply(state, acts[0])
        state = _drain_lof(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {unit.instance_id}
        state = apply(state, ChooseTarget(unit.instance_id))
        state = _drain_lof(state)
        assert _find_instance(state, unit.instance_id).exhausted is True
        assert state.player_by_id("P0").has_force_token is True

    def test_LOF_28_not_offered_without_a_ready_friendly_unit(self, repo):
        """The payability gate: an exhausted friendly unit (or an enemy one) can't
        pay the cost, so the Action is never offered."""
        state = _make_state()
        _set_base(state, "P0", _get_card(repo, "LOF", "28"))
        base = state.player_by_id("P0").base_zone[0]
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        mine.exhausted = True
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy, ready
        assert not _use_actions_lof(state, base)


# ── lof-set:20 — Miscellaneous abilities ──────────────────────────────────────


class TestLothWolf_LOF_44:
    """Sentinel; this unit can't attack."""

    def test_LOF_44_is_never_offered_as_an_attacker(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        wolf = _place(state, "P0", _get_card(repo, "LOF", "44"), "ground")
        ordinary = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attackers = {a.attacker_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)}
        assert ordinary.instance_id in attackers
        assert wolf.instance_id not in attackers

    def test_LOF_44_keeps_its_printed_sentinel(self, repo):
        """The restriction is a separate marker — the Sentinel wall still works."""
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        wolf = _place(state, "P0", _get_card(repo, "LOF", "44"), "ground")
        assert has_keyword(state, wolf, Keyword.SENTINEL)


class TestMythosaur_LOF_73:
    """Friendly upgraded units can't be exhausted or returned to hand by enemy
    card abilities.  Friendly leaders gain the Mandalorian trait."""

    def _grogu_exhausts(self, state, grogu, victim):
        """P1's Grogu (SHD_196) "Action [Exhaust]: Exhaust an enemy unit"."""
        from swu.engine.actions import apply, ChooseTarget
        state.active_player_index = state.player_index("P1")
        acts = _use_actions_lof(state, grogu)
        assert acts, "Grogu's Action should be available"
        state = apply(state, acts[0])
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(victim.instance_id))
        return _drain_lof(state)

    def test_LOF_73_aura_blocks_an_enemy_exhaust_of_an_upgraded_unit(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "73"), "ground")
        upgraded = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, upgraded, _get_card(repo, "SOR", "53"), "P0")
        grogu = _place(state, "P1", _get_card(repo, "SHD", "196"), "ground")
        state = self._grogu_exhausts(state, grogu, upgraded)
        assert _find_instance(state, upgraded.instance_id).exhausted is False

    def test_LOF_73_a_bare_friendly_unit_is_still_exhaustable(self, repo):
        """The aura's ``upgraded`` predicate really bites."""
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "73"), "ground")
        bare = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        grogu = _place(state, "P1", _get_card(repo, "SHD", "196"), "ground")
        state = self._grogu_exhausts(state, grogu, bare)
        assert _find_instance(state, bare.instance_id).exhausted is True

    def test_LOF_73_does_not_protect_the_enemys_upgraded_units(self, repo):
        """"Friendly" is from the Mythosaur's perspective — P1's own upgraded unit
        gets no protection from P0's Mythosaur."""
        from swu.abilities.resolver import _target_protected
        state = _make_state()
        mytho = _place(state, "P0", _get_card(repo, "LOF", "73"), "ground")
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _attach_upgrade_directly(state, theirs, _get_card(repo, "SOR", "53"), "P1")
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        assert _target_protected(state, theirs.instance_id, attacker, "exhaust") is False
        assert mytho.instance_id  # the aura source is in play

    def test_LOF_73_friendly_leaders_gain_mandalorian(self, repo):
        """Both an undeployed leader (base_zone) and the enemy's non-exclusion."""
        from swu.engine.traits import has_trait
        state = _make_state()
        _place(state, "P0", _get_card(repo, "LOF", "73"), "ground")
        mine = _place_leader(state, "P0", _get_card(repo, "SOR", "5"))    # Luke
        theirs = _place_leader(state, "P1", _get_card(repo, "SOR", "10"))  # Vader
        assert has_trait(state, mine, "Mandalorian") is True
        assert has_trait(state, theirs, "Mandalorian") is False


class TestWhirlwindOfPower_LOF_78:
    """Give a unit -2/-2 for this phase; -3/-3 instead if you control a Force unit."""

    def _cast_at(self, repo, extra_friendly=None):
        from swu.engine.actions import apply, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        if extra_friendly:
            _place(state, "P0", _get_card(repo, "LOF", extra_friendly), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "78")
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(victim.instance_id))
        state = _drain_lof(state)
        hit = _find_instance(state, victim.instance_id)
        return compute_power(state, hit), compute_hp(state, hit)

    def test_LOF_78_gives_minus_two_without_a_force_unit(self, repo):
        assert self._cast_at(repo) == (1, 5)

    def test_LOF_78_gives_minus_three_with_a_force_unit(self, repo):
        # LOF_196 Jedi Sentinel carries the Force trait.
        assert self._cast_at(repo, extra_friendly="196") == (0, 4)


class TestJediConsular_LOF_94:
    """Action [Exhaust, use the Force]: play a unit from hand for 2 less."""

    def test_LOF_94_needs_a_force_token(self, repo):
        state = _make_state()
        consular = _place(state, "P0", _get_card(repo, "LOF", "94"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 10)
        assert not _use_actions_lof(state, consular)
        state.player_by_id("P0").has_force_token = True
        assert _use_actions_lof(state, consular)

    def test_LOF_94_spends_the_token_and_discounts_the_play(self, repo):
        from swu.engine.actions import apply
        state = _make_state()
        consular = _place(state, "P0", _get_card(repo, "LOF", "94"), "ground")
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        _give_resources(state, "P0", 10)
        state.player_by_id("P0").has_force_token = True
        state = apply(state, _use_actions_lof(state, consular)[0])
        state = _drain_lof(state)
        assert state.player_by_id("P0").has_force_token is False
        assert _find_instance(state, consular.instance_id).exhausted is True
        top = state.pending_decisions[-1]
        assert top.kind == "play_from_hand"
        assert int(top.context.get("cost_reduction") or 0) == 2


class TestFollowingThePath_LOF_103:
    """Search the top 8 for up to 2 Force units and put them back on top."""

    def test_LOF_103_puts_the_chosen_force_units_on_top_in_pick_order(self, repo):
        from swu.engine.actions import legal_actions, apply, SelectSearchCard
        state = _make_state()
        # Deck top-down: filler, Force A, filler, Force B.
        force_b = _push_deck_top(state, "P0", _get_card(repo, "LOF", "112"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))    # filler
        force_a = _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "46"))    # filler
        deck_before = len(state.player_by_id("P0").deck)
        hand_before = len(state.player_by_id("P0").hand)
        state, _ = _play_event_from_hand(state, repo, "LOF", "103")
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "deck_search"
        offered = {a.instance_id for a in legal_actions(state)
                   if isinstance(a, SelectSearchCard)}
        # Only the two Force units are eligible out of the top 8.
        assert offered == {force_a.instance_id, force_b.instance_id}
        # Pick B FIRST, then A — selection order, not deck order, decides the top.
        state = apply(state, SelectSearchCard(force_b.instance_id))
        state = apply(state, SelectSearchCard(force_a.instance_id))
        state = _drain_lof(state)
        deck = state.player_by_id("P0").deck
        # Nothing was drawn; both picks are the top two, in selection order.
        assert len(state.player_by_id("P0").hand) == hand_before
        assert len(deck) == deck_before
        assert [c.instance_id for c in deck[:2]] == [force_b.instance_id,
                                                     force_a.instance_id]

    def test_LOF_103_taking_none_is_legal_and_bottoms_the_rest(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishSearch
        state = _make_state()
        top_card = _push_deck_top(state, "P0", _get_card(repo, "LOF", "196"))
        state, _ = _play_event_from_hand(state, repo, "LOF", "103")
        state = _drain_lof(state)
        finish = next(a for a in legal_actions(state) if isinstance(a, FinishSearch))
        state = apply(state, finish)
        state = _drain_lof(state)
        deck = state.player_by_id("P0").deck
        assert top_card.instance_id in {c.instance_id for c in deck}
        assert len(state.player_by_id("P0").hand) == 0


class TestKaadu_LOF_114:
    """When Played: you may give ANOTHER friendly unit Overwhelm for this phase."""

    def test_LOF_114_grants_overwhelm_to_another_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        kaadu = _place(state, "P0", _get_card(repo, "LOF", "114"), "ground")
        buddy = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, kaadu)
        state = _accept_optional_and_run(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {buddy.instance_id}, "'another' excludes Kaadu itself"
        state = apply(state, ChooseTarget(buddy.instance_id))
        state = _drain_lof(state)
        assert has_keyword(state, _find_instance(state, buddy.instance_id),
                           Keyword.OVERWHELM)

    def test_LOF_114_auto_declines_with_no_other_friendly_unit(self, repo):
        from swu.engine.actions import legal_actions, AcceptTrigger
        state = _make_state()
        kaadu = _place(state, "P0", _get_card(repo, "LOF", "114"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # enemy only
        state = _fire_when_played(state, kaadu)
        assert not [a for a in legal_actions(state) if isinstance(a, AcceptTrigger)]


class TestDirectedByTheForce_LOF_123:
    """Create your Force token; you may play a unit from your hand."""

    def test_LOF_123_creates_the_token_and_offers_a_unit_play(self, repo):
        state = _make_state()
        _put_in_hand(state, "P0", _get_card(repo, "SOR", "46"))
        # Generous, so the off-aspect penalty can't make the hand unit unaffordable.
        state, _ = _play_event_from_hand(state, repo, "LOF", "123", resources=20)
        state = _drain_lof(state)
        assert state.player_by_id("P0").has_force_token is True
        assert state.pending_decisions[-1].kind == "play_from_hand"

    def test_LOF_123_still_creates_the_token_with_an_empty_hand(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "LOF", "123")
        state = _drain_lof(state)
        assert state.player_by_id("P0").has_force_token is True
        assert not [d for d in state.pending_decisions
                    if d.kind == "play_from_hand"]


# ── lof-set:21 — Miscellaneous abilities ──────────────────────────────────────


class TestProtectThePod_LOF_128:
    """A friendly non-Vehicle unit deals damage equal to its remaining HP to an
    enemy unit."""

    def test_LOF_128_deals_the_dealers_remaining_hp(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        dealer = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        dealer.damage = 2                                                    # 5 left
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "128", resources=20)
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(dealer.instance_id))
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(victim.instance_id))
        state = _drain_lof(state)
        assert _find_instance(state, victim.instance_id).damage == 5

    def test_LOF_128_a_vehicle_is_not_offered_as_the_dealer(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        # LOF_233 Scimitar is a Vehicle; LOF_196 Jedi Sentinel is not.
        vehicle = _place(state, "P0", _get_card(repo, "LOF", "233"), "space")
        ok = _place(state, "P0", _get_card(repo, "LOF", "196"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "128", resources=20)
        state = _drain_lof(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert ok.instance_id in offered
        assert vehicle.instance_id not in offered


class TestJediInHiding_LOF_159:
    """When Defeated: you may use the Force; if you do, each opponent discards."""

    def test_LOF_159_spending_the_token_makes_the_opponent_discard(self, repo):
        from swu.engine.actions import legal_actions, apply, UseForceOption
        state = _make_state()
        jedi = _place(state, "P0", _get_card(repo, "LOF", "159"), "ground")
        state.player_by_id("P0").has_force_token = True
        held = _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_when_defeated(state, jedi)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "use_force"
        use = next(a for a in legal_actions(state)
                   if isinstance(a, UseForceOption) and a.option == "force")
        state = apply(state, use)
        state = _drain_lof(state)
        assert state.player_by_id("P0").has_force_token is False
        assert held.instance_id in {c.instance_id
                                    for c in state.player_by_id("P1").discard}

    def test_LOF_159_declining_costs_nothing(self, repo):
        from swu.engine.actions import legal_actions, apply, DeclineUseForce
        state = _make_state()
        jedi = _place(state, "P0", _get_card(repo, "LOF", "159"), "ground")
        state.player_by_id("P0").has_force_token = True
        held = _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_when_defeated(state, jedi)
        state = _drain_lof(state)
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, DeclineUseForce)))
        state = _drain_lof(state)
        assert state.player_by_id("P0").has_force_token is True
        assert held.instance_id in {c.instance_id
                                    for c in state.player_by_id("P1").hand}

    def test_LOF_159_no_token_means_no_prompt(self, repo):
        state = _make_state()
        jedi = _place(state, "P0", _get_card(repo, "LOF", "159"), "ground")
        _put_in_hand(state, "P1", _get_card(repo, "SOR", "46"))
        state = _fire_when_defeated(state, jedi)
        state = _drain_lof(state)
        assert not [d for d in state.pending_decisions if d.kind == "use_force"]


class TestMarchionRo_LOF_186:
    """Each friendly unit's Raid is doubled."""

    def test_LOF_186_doubles_a_friendly_units_raid(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        # LOF_209 Tusken Tracker prints Raid 2.
        tusken = _place(state, "P0", _get_card(repo, "LOF", "209"), "ground")
        assert keyword_value(state, tusken, Keyword.RAID) == 2
        _place(state, "P0", _get_card(repo, "LOF", "186"), "ground")
        assert keyword_value(state, tusken, Keyword.RAID) == 4

    def test_LOF_186_leaves_enemy_raid_alone(self, repo):
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        enemy = _place(state, "P1", _get_card(repo, "LOF", "209"), "ground")
        _place(state, "P0", _get_card(repo, "LOF", "186"), "ground")
        assert keyword_value(state, enemy, Keyword.RAID) == 2

    def test_LOF_186_two_doublers_multiply_twice(self, repo):
        """The CR's independent-application reading (and the guard that the marker
        scan does not stop at the first match)."""
        from swu.engine.keywords import keyword_value, Keyword
        state = _make_state()
        tusken = _place(state, "P0", _get_card(repo, "LOF", "209"), "ground")
        _place(state, "P0", _get_card(repo, "LOF", "186"), "ground")
        _place(state, "P0", _get_card(repo, "LOF", "186"), "ground")
        assert keyword_value(state, tusken, Keyword.RAID) == 8


class TestLiberatedByDarkness_LOF_189:
    """Use the Force; if you do, take control of a non-leader unit until regroup."""

    def test_LOF_189_takes_control_and_reverts_at_regroup(self, repo):
        from swu.engine.actions import apply, ChooseTarget
        state = _make_state()
        state.player_by_id("P0").has_force_token = True
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "189", resources=20)
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(victim.instance_id))
        state = _drain_lof(state)
        assert state.player_by_id("P0").has_force_token is False
        mine = {c.instance_id for c in state.player_by_id("P0").ground_arena}
        assert victim.instance_id in mine
        stolen = _find_instance(state, victim.instance_id)
        assert stolen.return_control_to_owner_at_regroup is True

    def test_LOF_189_no_token_means_no_prompt(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "189", resources=20)
        state = _drain_lof(state)
        assert not state.pending_decisions
        assert victim.instance_id in {c.instance_id
                                      for c in state.player_by_id("P1").ground_arena}


class TestTuskenTracker_LOF_209:
    """When Played: each enemy unit loses Hidden for this phase."""

    def test_LOF_209_strips_hidden_from_enemy_units(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        hider = _place(state, "P1", _get_card(repo, "LOF", "159"), "ground")  # Hidden
        assert has_keyword(state, hider, Keyword.HIDDEN)
        tracker = _place(state, "P0", _get_card(repo, "LOF", "209"), "ground")
        state = _fire_when_played(state, tracker)
        state = _drain_lof(state)
        assert not has_keyword(state, _find_instance(state, hider.instance_id),
                               Keyword.HIDDEN)

    def test_LOF_209_leaves_friendly_hidden_alone(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        friend = _place(state, "P0", _get_card(repo, "LOF", "159"), "ground")
        tracker = _place(state, "P0", _get_card(repo, "LOF", "209"), "ground")
        state = _fire_when_played(state, tracker)
        state = _drain_lof(state)
        assert has_keyword(state, _find_instance(state, friend.instance_id),
                           Keyword.HIDDEN)


class TestDooku_LOF_211:
    """When Played: each friendly unit with Hidden can't be attacked this phase."""

    def test_LOF_211_hidden_friends_drop_out_of_the_defender_pool(self, repo):
        from swu.engine.actions import legal_actions, AttackWithUnit
        state = _make_state()
        hider = _place(state, "P0", _get_card(repo, "LOF", "159"), "ground")  # Hidden
        plain = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        dooku = _place(state, "P0", _get_card(repo, "LOF", "211"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state = _fire_when_played(state, dooku)
        state = _drain_lof(state)
        state.active_player_index = state.player_index("P1")
        defenders = {a.defender_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)
                     and a.attacker_id == attacker.instance_id}
        assert plain.instance_id in defenders
        assert hider.instance_id not in defenders
        assert dooku.instance_id not in defenders  # Dooku has Hidden himself


class TestForceSlow_LOF_217:
    """Give an exhausted unit -8/-0 for this phase."""

    def test_LOF_217_only_exhausted_units_are_targetable(self, repo):
        from swu.engine.actions import legal_actions, ChooseTarget
        state = _make_state()
        ready = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        tired.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "LOF", "217", resources=20)
        state = _drain_lof(state)
        offered = {a.target_id for a in legal_actions(state)
                   if isinstance(a, ChooseTarget)}
        assert offered == {tired.instance_id}
        assert ready.instance_id not in offered

    def test_LOF_217_floors_the_power_at_zero(self, repo):
        from swu.engine.actions import apply, ChooseTarget, compute_power, compute_hp
        state = _make_state()
        tired = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        tired.exhausted = True
        state, _ = _play_event_from_hand(state, repo, "LOF", "217", resources=20)
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(tired.instance_id))
        state = _drain_lof(state)
        hit = _find_instance(state, tired.instance_id)
        assert compute_power(state, hit) == 0
        assert compute_hp(state, hit) == 7  # -0 HP


# ── lof-set:22 — Miscellaneous abilities (completes the LOF set) ──────────────


def _move_select_lof(state, upgrade_id):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "MoveUpgradeSelect"
               and a.upgrade_id == upgrade_id)
    return apply(state, act)


def _move_upgrade_ids_lof(state):
    from swu.engine.actions import legal_actions
    return {a.upgrade_id for a in legal_actions(state)
            if type(a).__name__ == "MoveUpgradeSelect"}


def _move_to_lof(state, dest_id):
    from swu.engine.actions import legal_actions, apply
    act = next(a for a in legal_actions(state)
               if type(a).__name__ == "MoveUpgradeTo" and a.dest_id == dest_id)
    return apply(state, act)


class TestJocastaNu_LOF_248:
    """When Played: you may attach a friendly upgrade on a friendly unit to a
    different eligible unit."""

    def test_LOF_248_moves_a_friendly_upgrade_to_another_friendly_unit(self, repo):
        state = _make_state()
        host = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        dest = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        upg = _attach_upgrade_directly(state, host, _get_card(repo, "SHD", "69"), "P0")
        jocasta = _place(state, "P0", _get_card(repo, "LOF", "248"), "ground")
        state = _fire_when_played(state, jocasta)
        state = _drain_lof(state)
        assert state.pending_decisions[-1].kind == "move_upgrade"
        state = _move_select_lof(state, upg.instance_id)
        state = _move_to_lof(state, dest.instance_id)
        state = _drain_lof(state)
        assert not _find_instance(state, host.instance_id).attached_upgrades
        assert [u.instance_id for u in
                _find_instance(state, dest.instance_id).attached_upgrades] \
            == [upg.instance_id]

    def test_LOF_248_ignores_upgrades_on_enemy_units(self, repo):
        """The new ``host_controller_id`` filter: an enemy-hosted upgrade is not
        "a friendly upgrade on a friendly unit"."""
        state = _make_state()
        mine = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # a destination
        theirs = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # their dest
        friendly_upg = _attach_upgrade_directly(
            state, mine, _get_card(repo, "SHD", "69"), "P0")
        enemy_upg = _attach_upgrade_directly(
            state, theirs, _get_card(repo, "SHD", "69"), "P1")
        jocasta = _place(state, "P0", _get_card(repo, "LOF", "248"), "ground")
        state = _fire_when_played(state, jocasta)
        state = _drain_lof(state)
        offered = _move_upgrade_ids_lof(state)
        assert friendly_upg.instance_id in offered
        assert enemy_upg.instance_id not in offered

    def test_LOF_248_not_offered_when_nothing_can_move(self, repo):
        state = _make_state()
        jocasta = _place(state, "P0", _get_card(repo, "LOF", "248"), "ground")
        state = _fire_when_played(state, jocasta)
        state = _drain_lof(state)
        assert not any(d.kind == "move_upgrade" for d in state.pending_decisions)


class TestGoIntoHiding_LOF_262:
    """Choose a unit.  It can't be attacked this phase (unless it has Sentinel)."""

    def test_LOF_262_the_chosen_unit_leaves_the_defender_pool(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, AttackWithUnit
        state = _make_state()
        hidden = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "262", resources=20)
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(hidden.instance_id))
        state = _drain_lof(state)
        state.active_player_index = state.player_index("P1")
        defenders = {a.defender_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)
                     and a.attacker_id == attacker.instance_id}
        assert other.instance_id in defenders
        assert hidden.instance_id not in defenders

    def test_LOF_262_a_sentinel_is_still_attackable(self, repo):
        """The printed "(unless it has Sentinel)" escape, shared with TWI_219."""
        from swu.engine.actions import legal_actions, apply, ChooseTarget, AttackWithUnit
        state = _make_state()
        # LOF_44 Loth-Wolf prints Sentinel.
        wall = _place(state, "P0", _get_card(repo, "LOF", "44"), "ground")
        attacker = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state, _ = _play_event_from_hand(state, repo, "LOF", "262", resources=20)
        state = _drain_lof(state)
        state = apply(state, ChooseTarget(wall.instance_id))
        state = _drain_lof(state)
        state.active_player_index = state.player_index("P1")
        defenders = {a.defender_id for a in legal_actions(state)
                     if isinstance(a, AttackWithUnit)
                     and a.attacker_id == attacker.instance_id}
        assert wall.instance_id in defenders
