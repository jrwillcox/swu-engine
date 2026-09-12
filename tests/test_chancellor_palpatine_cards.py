"""Tests for the chancellor-palpatine deck's card encodings.

Group ``chancellor-palpatine:01`` — Direct damage & removal:
  * SEC_34  Cad Bane — optional WhenPlayed: defeat a unit with 2 or less remaining
    HP (the new ``remaining_hp_le_2`` predicate).  Plot is the keyword layer.
  * SEC_76  Charged with Murder — event: disclose Vigilance×2 → defeat a damaged
    non-leader unit (the new ``defeat`` disclose-payoff arm).
  * SEC_77  Retaliation — event: defeat a unit that dealt damage to a base this
    phase (the new ``dealt_damage_to_base_this_phase`` predicate, backed by
    game_memory.units_dealt_base_damage_this_round).
  * LOF_82  Vaneé — optional WhenPlayed/OnAttack: defeat an Experience token on a
    friendly unit, then give an Experience token to a friendly unit (the new
    ``has_experience_token`` predicate + ``CONTROLLER_HAS_UNIT_WITH_EXPERIENCE_TOKEN``
    gate; reuses defeat_experience + GiveToken with the requires_prior_target "If
    you do" gate).
  * SEC_241 Political Bully — optional WhenPlayed gated by "another Official unit"
    (CONTROLLER_HAS_OTHER_TRAIT_UNIT): deal 2 damage to a ground unit.

Method names embed the card number so the encoding verifier's ``-k`` gate selects
them.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _place_leader, _give_resources,
    _fire_on_attack, _fire_when_played, _defeat_and_fire,
    _experience_count, _find_instance, _play_event_from_hand,
    _build_search_deck, _seed_rng,
)
from tests.test_disclose import _add_hand, _settle, _neutral, _agg_vil, _her


# ── shared drivers ────────────────────────────────────────────────────────────

def _legal(state):
    from swu.engine.actions import legal_actions
    return legal_actions(state)


def _has_accept(state):
    from swu.engine.actions import AcceptTrigger
    return any(isinstance(a, AcceptTrigger) for a in _legal(state))


def _accept(state):
    from swu.engine.actions import apply, AcceptTrigger
    return apply(state, next(a for a in _legal(state) if isinstance(a, AcceptTrigger)))


def _choose_target(state, target_id):
    from swu.engine.actions import apply, ChooseTarget
    return apply(state, next(a for a in _legal(state)
                             if isinstance(a, ChooseTarget) and a.target_id == target_id))


def _resolve_all(state):
    """Drive AutoResolveEffects to quiescence (no player-facing choices left)."""
    from swu.engine.actions import apply, AutoResolveEffects
    for _ in range(40):
        if not state.pending_decisions:
            break
        a = next((x for x in _legal(state) if isinstance(x, AutoResolveEffects)), None)
        if a is None:
            break
        state = apply(state, a)
    return state


def _remaining_hp(state, ci):
    from swu.engine.actions import compute_hp
    return compute_hp(state, ci) - ci.damage


# ══ SEC_34 Cad Bane (optional WhenPlayed: defeat a unit ≤2 remaining HP) ════════

class TestCadBane:
    def test_sec_34_defeats_low_hp_unit(self, repo):
        state = _make_state()
        cad = _place(state, "P0", _get_card(repo, "SEC", "34"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        from swu.engine.actions import compute_hp
        victim.damage = compute_hp(state, victim) - 1   # remaining HP = 1 (≤ 2)
        state = _fire_when_played(state, cad)
        assert _has_accept(state)
        state = _accept(state)
        state = _choose_target(state, victim.instance_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        assert _find_instance(state, victim.instance_id) is None   # defeated

    def test_sec_34_not_offered_when_no_low_hp_unit(self, repo):
        state = _make_state()
        cad = _place(state, "P0", _get_card(repo, "SEC", "34"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "39"), "ground")   # 8/8, full HP
        state = _fire_when_played(state, cad)
        assert not _has_accept(state)   # nothing ≤2 remaining HP → auto-decline

    def test_sec_34_decline_leaves_unit(self, repo):
        from swu.engine.actions import apply, DeclineTrigger
        state = _make_state()
        cad = _place(state, "P0", _get_card(repo, "SEC", "34"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        from swu.engine.actions import compute_hp
        victim.damage = compute_hp(state, victim) - 1
        state = _fire_when_played(state, cad)
        state = apply(state, next(a for a in _legal(state)
                                  if isinstance(a, DeclineTrigger)))
        state = _resolve_all(state)
        assert _find_instance(state, victim.instance_id) is not None   # still alive


# ══ SEC_76 Charged with Murder (disclose Vigilance×2 → defeat damaged non-leader) ═

class TestChargedWithMurder:
    def _setup(self, repo, *, aspects=True, damaged=True):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        if damaged:
            victim.damage = 1
        if aspects:
            _add_hand(state, "P0", _neutral(repo))   # Vigilance #1
            _add_hand(state, "P0", _neutral(repo))   # Vigilance #2
        return state, victim

    def _play(self, state, repo):
        state, _ = _play_event_from_hand(state, repo, "SEC", "76")
        return state

    def test_sec_76_disclose_defeats_damaged_unit(self, repo):
        state, victim = self._setup(repo)
        state = self._play(state, repo)
        state = _choose_target(state, victim.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _settle(state)   # disclose Vigilance×2 → defeat payoff
        assert not state.pending_decisions
        assert _find_instance(state, victim.instance_id) is None

    def test_sec_76_decline_disclose_no_defeat(self, repo):
        state, victim = self._setup(repo)
        state = self._play(state, repo)
        state = _choose_target(state, victim.instance_id)
        state = _settle(state, decline_disclose=True)
        assert not state.pending_decisions
        assert _find_instance(state, victim.instance_id) is not None

    def test_sec_76_no_damaged_unit_no_disclose(self, repo):
        state, victim = self._setup(repo, damaged=False)
        state = self._play(state, repo)
        # No damaged non-leader unit → mandatory targeted effect fizzles, no disclose.
        assert not any(d.kind == "disclose" for d in state.pending_decisions)
        state = _resolve_all(state)
        assert _find_instance(state, victim.instance_id) is not None


# ══ SEC_77 Retaliation (defeat a unit that dealt damage to a base this phase) ════

class TestRetaliation:
    def _play(self, state, repo):
        state, _ = _play_event_from_hand(state, repo, "SEC", "77")
        return state

    def test_sec_77_base_attack_records_dealer(self, repo):
        # Integration: a real base attack records the attacker in game_memory.
        from tests.test_engine_combat import _make_unit_instance, _make_minimal_state
        from swu.engine.actions import apply, AttackWithUnit
        atk = _make_unit_instance("atk", "P0", 3, 5)
        state = _make_minimal_state(p0_units=[atk])
        state = apply(state, AttackWithUnit("atk", None))
        assert "atk" in state.game_memory.units_dealt_base_damage_this_round

    def test_sec_77_defeats_recorded_dealer(self, repo):
        state = _make_state()
        dealer = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        state.game_memory.units_dealt_base_damage_this_round.add(dealer.instance_id)
        state = self._play(state, repo)
        state = _choose_target(state, dealer.instance_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        assert _find_instance(state, dealer.instance_id) is None

    def test_sec_77_no_dealer_fizzles(self, repo):
        state = _make_state()
        bystander = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        # bystander is NOT in the dealt-base-damage set → no legal target.
        state = self._play(state, repo)
        state = _resolve_all(state)
        assert not state.pending_decisions
        assert _find_instance(state, bystander.instance_id) is not None


# ══ LOF_82 Vaneé (defeat an Experience token → give an Experience token) ════════

class TestVanee:
    def _setup(self, repo, *, seed_token=True):
        state = _make_state()
        vanee = _place(state, "P0", _get_card(repo, "LOF", "82"), "ground")
        holder = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        recipient = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        if seed_token:
            from swu.engine.tokens import attach_token
            attach_token(state, state.player_by_id("P0"), holder, "Experience")
        return state, vanee, holder, recipient

    def test_lof_82_moves_experience_token(self, repo):
        state, vanee, holder, recipient = self._setup(repo)
        assert _experience_count(holder) == 1
        state = _fire_when_played(state, vanee)
        assert _has_accept(state)
        state = _accept(state)
        state = _choose_target(state, holder.instance_id)      # defeat token here
        state = _choose_target(state, recipient.instance_id)   # give token here
        state = _resolve_all(state)
        assert not state.pending_decisions
        holder = _find_instance(state, holder.instance_id)
        recipient = _find_instance(state, recipient.instance_id)
        assert _experience_count(holder) == 0     # token defeated
        assert _experience_count(recipient) == 1  # token given ("If you do")

    def test_lof_82_not_offered_without_experience_token(self, repo):
        state, vanee, holder, recipient = self._setup(repo, seed_token=False)
        state = _fire_when_played(state, vanee)
        assert not _has_accept(state)   # no Experience token anywhere → not offered

    def test_lof_82_on_attack_also_fires(self, repo):
        state, vanee, holder, recipient = self._setup(repo)
        state = _fire_on_attack(state, vanee)
        assert _has_accept(state)


# ══ SEC_241 Political Bully (WhenPlayed, another Official → 2 dmg to a ground unit) ═

class TestPoliticalBully:
    def test_sec_241_deals_two_with_another_official(self, repo):
        state = _make_state()
        bully = _place(state, "P0", _get_card(repo, "SEC", "241"), "ground")
        _place(state, "P0", _get_card(repo, "SEC", "237"), "ground")   # another Official
        target = _place(state, "P1", _get_card(repo, "SOR", "39"), "ground")  # 8/8
        state = _fire_when_played(state, bully)
        assert _has_accept(state)
        state = _accept(state)
        state = _choose_target(state, target.instance_id)
        state = _resolve_all(state)
        target = _find_instance(state, target.instance_id)
        assert target.damage == 2

    def test_sec_241_not_offered_without_another_official(self, repo):
        state = _make_state()
        bully = _place(state, "P0", _get_card(repo, "SEC", "241"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "39"), "ground")
        # Political Bully is itself Official, but "another Official unit" is required.
        state = _fire_when_played(state, bully)
        assert not _has_accept(state)


# ══ SEC_1 Chancellor Palpatine (leader: Plot deck-search + When Deployed discount) ═
#
# chancellor-palpatine:02 — Card advantage & disruption.
#   * Action [1 resource, Exhaust] (deployed): deck_search top 5 for a card with
#     Plot, reveal + draw it (the ``_has_plot`` eligible predicate; count=1,
#     up_to=False — mandatory if a Plot card is present).
#   * When Deployed: the next card you play using Plot this phase costs 3 less
#     (NextPlayDiscount with the new ``plot_only`` flag; applies only on the
#     PlotPlay path, which passes ``via_plot=True`` to the play-cost seam).

def _use_ability(state, source_id):
    """Apply the (single) UseAbility offered for ``source_id``."""
    from swu.engine.actions import apply, UseAbility
    act = next(a for a in _legal(state)
               if isinstance(a, UseAbility) and a.source_id == source_id)
    return apply(state, act)


class TestChancellorPalpatine:
    def _deploy_palpatine(self, state):
        """Place Palpatine as an undeployed leader, then deploy it as an effect
        (free — fires the real LeaderDeployed + WhenDeployed machinery)."""
        from swu.engine.actions import deploy_leader_as_effect
        return deploy_leader_as_effect(state, state.player_by_id("P0")
                                       .leader_instance.instance_id)

    def test_sec_1_search_draws_plot_card(self, repo):
        from swu.engine.actions import SelectSearchCard, apply
        state = _seed_rng(_make_state())
        pal = _place(state, "P0", _get_card(repo, "SEC", "1"), "ground")
        pal.deployed = True
        _give_resources(state, "P0", 2)
        plot_card = _get_card(repo, "SEC", "34")     # Cad Bane — has Plot
        filler = _get_card(repo, "SOR", "46")        # no Plot
        deck = _build_search_deck(
            state, "P0",
            top_cards=[filler, plot_card, filler, filler, filler],
            below_cards=[filler, filler],
        )
        state = _use_ability(state, pal.instance_id)
        assert state.pending_decisions[-1].kind == "deck_search"
        state = apply(state, SelectSearchCard(deck[1].instance_id))   # the Plot card
        state = _resolve_all(state)
        assert not state.pending_decisions
        ps = state.player_by_id("P0")
        assert deck[1].instance_id in {c.instance_id for c in ps.hand}   # drawn
        assert _find_instance(state, pal.instance_id).exhausted           # paid Exhaust
        assert ps.available_resources == 1                                # paid 1 resource

    def test_sec_1_search_not_offered_when_undeployed(self, repo):
        from swu.engine.actions import UseAbility
        state = _make_state()
        pal = _place_leader(state, "P0", _get_card(repo, "SEC", "1"))   # base_zone, undeployed
        _give_resources(state, "P0", 3)
        assert not any(isinstance(a, UseAbility) and a.source_id == pal.instance_id
                       for a in _legal(state))   # deployed_only ability suppressed

    def test_sec_1_deploy_records_plot_discount(self, repo):
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SEC", "1"))
        state = self._deploy_palpatine(state)
        entries = [e for e in state.game_memory.pending_play_discounts
                   if e.get("player_id") == "P0"]
        assert len(entries) == 1
        e = entries[0]
        assert e["plot_only"] is True and e["amount"] == 3 and e["units_only"] is False

    def test_sec_1_discount_applies_only_to_plot_play(self, repo):
        from swu.engine.actions import _play_cost, _effective_cost
        from swu.engine.state import CardInstance, Zone
        state = _make_state()
        _place_leader(state, "P0", _get_card(repo, "SEC", "1"))
        state = self._deploy_palpatine(state)
        ps = state.player_by_id("P0")
        plot_def = _get_card(repo, "SEC", "34")   # Cad Bane — a Plot card
        ci = CardInstance(instance_id="P0_plot_probe", card_def=plot_def,
                          owner_id="P0", zone=Zone.HAND)
        base = _effective_cost(plot_def, ps)
        # A normal (non-Plot) play sees no discount; a Plot play gets 3 less.
        assert _play_cost(state, ci, ps, via_plot=False) == base
        assert _play_cost(state, ci, ps, via_plot=True) == max(0, base - 3)


# ══ chancellor-palpatine:03 — Combat tricks, buffs & tempo ══════════════════════

def _drive_all(state, *, pick_token_ids=None, decline_disclose=False):
    """Drive AutoResolveEffects / disclose / select_token to quiescence.  Disclose
    reveals a covering set (or declines); select_token picks ``pick_token_ids`` in
    order then finishes (the "up to")."""
    from swu.engine.actions import (
        legal_actions, apply, AutoResolveEffects,
        DiscloseSelectCard, DeclineDisclose, SelectTokenTarget, FinishSelectToken)
    picks = list(pick_token_ids or [])
    for _ in range(80):
        if not state.pending_decisions:
            break
        acts = legal_actions(state)
        auto = next((a for a in acts if isinstance(a, AutoResolveEffects)), None)
        if auto is not None:
            state = apply(state, auto)
            continue
        kind = state.pending_decisions[-1].kind
        if kind == "disclose":
            pick = None if decline_disclose else next(
                (a for a in acts if isinstance(a, DiscloseSelectCard)), None)
            if pick is not None:
                state = apply(state, pick)
            else:
                state = apply(state, next(a for a in acts
                                          if isinstance(a, DeclineDisclose)))
            continue
        if kind == "select_token":
            act = None
            if picks:
                tid = picks[0]
                act = next((a for a in acts if isinstance(a, SelectTokenTarget)
                            and a.target_id == tid), None)
            if act is not None:
                picks.pop(0)
                state = apply(state, act)
            else:
                state = apply(state, next(a for a in acts
                                          if isinstance(a, FinishSelectToken)))
            continue
        break
    return state


# ── SEC_27 The Chancellor's Shuttle (WhenDefeated, gated: give an Experience token) ─

class TestChancellorsShuttle:
    def test_sec_27_gives_experience_when_controls_palpatine(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "27"), "space")
        _place(state, "P0", _get_card(repo, "SEC", "82"), "ground")   # Chancellor Palpatine (unit)
        recipient = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        state = _defeat_and_fire(state, shuttle, "P0")
        assert _has_accept(state)
        state = _accept(state)
        state = _choose_target(state, recipient.instance_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, recipient.instance_id)) == 1

    def test_sec_27_not_offered_without_palpatine(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "27"), "space")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # a unit, but no Palpatine
        state = _defeat_and_fire(state, shuttle, "P0")
        assert not _has_accept(state)   # condition gates collection → no prompt


# ── SEC_37 Cantwell Arrestor Cruiser (WhenPlayed disclose → exhaust + can't ready) ─

class TestCantwellArrestorCruiser:
    def _setup(self, repo, *, aspects=True, enemy=True):
        state = _make_state()
        cantwell = _place(state, "P0", _get_card(repo, "SEC", "37"), "space")
        victim = None
        if enemy:
            victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        if aspects:
            _add_hand(state, "P0", _neutral(repo))   # Vigilance
            _add_hand(state, "P0", _neutral(repo))   # Vigilance
            _add_hand(state, "P0", _agg_vil(repo))   # Villainy
        return state, cantwell, victim

    def test_sec_37_disclose_exhausts_and_locks(self, repo):
        state, cantwell, victim = self._setup(repo)
        state = _fire_when_played(state, cantwell)
        state = _choose_target(state, victim.instance_id)
        assert state.pending_decisions[-1].kind == "disclose"
        state = _drive_all(state)
        assert not state.pending_decisions
        victim = _find_instance(state, victim.instance_id)
        assert victim.exhausted is True
        assert victim.cannot_ready_this_round is True   # "can't ready while in play"

    def test_sec_37_decline_disclose_no_exhaust(self, repo):
        state, cantwell, victim = self._setup(repo)
        state = _fire_when_played(state, cantwell)
        state = _choose_target(state, victim.instance_id)
        state = _drive_all(state, decline_disclose=True)
        victim = _find_instance(state, victim.instance_id)
        assert victim.exhausted is False

    def test_sec_37_no_enemy_unit_no_disclose(self, repo):
        state, cantwell, _ = self._setup(repo, enemy=False)
        state = _fire_when_played(state, cantwell)
        # mandatory targeted effect fizzles (no enemy unit) → no disclose pushed.
        assert not any(d.kind == "disclose" for d in state.pending_decisions)
        state = _resolve_all(state)
        assert not state.pending_decisions


# ── SEC_55 Dhani Pilgrim (WhenPlayed/WhenDefeated: heal 1 from your base) ──────────

class TestDhaniPilgrim:
    def test_sec_55_when_played_heals_base(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 3
        dhani = _place(state, "P0", _get_card(repo, "SEC", "55"), "ground")
        state = _fire_when_played(state, dhani)
        state = _resolve_all(state)
        assert state.player_by_id("P0").base_instance.damage == 2

    def test_sec_55_when_defeated_heals_base(self, repo):
        state = _make_state()
        state.player_by_id("P0").base_instance.damage = 3
        dhani = _place(state, "P0", _get_card(repo, "SEC", "55"), "ground")
        state = _defeat_and_fire(state, dhani, "P0")
        state = _resolve_all(state)
        assert state.player_by_id("P0").base_instance.damage == 2


# ── SEC_79 Corrupt Politician (conditional self-grant Sentinel) ───────────────────

class TestCorruptPolitician:
    def _sentinel(self, state, ci):
        from swu.engine.keywords import has_keyword, Keyword
        return has_keyword(state, ci, Keyword.SENTINEL)

    def test_sec_79_gains_sentinel_when_more_units(self, repo):
        state = _make_state()
        pol = _place(state, "P0", _get_card(repo, "SEC", "79"), "ground")
        # P0 has 1 unit, P1 has 0 → strictly more.
        assert self._sentinel(state, pol) is True

    def test_sec_79_no_sentinel_when_not_more(self, repo):
        state = _make_state()
        pol = _place(state, "P0", _get_card(repo, "SEC", "79"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")   # P1=2 > P0=1
        # Printed Sentinel is stripped by the sanitiser, so it's OFF when not more.
        assert self._sentinel(state, pol) is False


# ── SEC_81 Major Partagaz (When another friendly Official attacks: +2/+2 this phase) ─

class TestMajorPartagaz:
    def _stats(self, state, ci):
        from swu.engine.actions import compute_power, compute_hp
        return compute_power(state, ci), compute_hp(state, ci)

    def test_sec_81_buffs_when_official_attacks(self, repo):
        state = _make_state()
        partagaz = _place(state, "P0", _get_card(repo, "SEC", "81"), "ground")  # 0/6
        other = _place(state, "P0", _get_card(repo, "SEC", "82"), "ground")     # Official
        assert self._stats(state, partagaz) == (0, 6)
        state = _fire_on_attack(state, other)
        state = _resolve_all(state)
        assert self._stats(state, _find_instance(state, partagaz.instance_id)) == (2, 8)

    def test_sec_81_no_buff_when_non_official_attacks(self, repo):
        state = _make_state()
        partagaz = _place(state, "P0", _get_card(repo, "SEC", "81"), "ground")
        other = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # not Official
        state = _fire_on_attack(state, other)
        state = _resolve_all(state)
        assert self._stats(state, _find_instance(state, partagaz.instance_id)) == (0, 6)


# ── SEC_84 Mas Amedda (WhenPlayed: Experience to up to 2 other Official units) ─────

class TestMasAmedda:
    def test_sec_84_gives_experience_to_two_officials(self, repo):
        state = _make_state()
        mas = _place(state, "P0", _get_card(repo, "SEC", "84"), "ground")
        off1 = _place(state, "P0", _get_card(repo, "SEC", "82"), "ground")   # Official
        off2 = _place(state, "P0", _get_card(repo, "SEC", "241"), "ground")  # Official
        state = _fire_when_played(state, mas)
        assert state.pending_decisions[-1].kind == "select_token"
        state = _drive_all(state, pick_token_ids=[off1.instance_id, off2.instance_id])
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, off1.instance_id)) == 1
        assert _experience_count(_find_instance(state, off2.instance_id)) == 1
        # "other" — Mas Amedda himself never receives a token.
        assert _experience_count(_find_instance(state, mas.instance_id)) == 0

    def test_sec_84_not_offered_without_other_official(self, repo):
        state = _make_state()
        mas = _place(state, "P0", _get_card(repo, "SEC", "84"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Official
        state = _fire_when_played(state, mas)
        assert not any(d.kind == "select_token" for d in state.pending_decisions)


# ── SEC_85 Vice Admiral Rampart (On Attack disclose → Experience to up to 2 units) ─

class TestViceAdmiralRampart:
    def _setup(self, repo):
        state = _make_state()
        rampart = _place(state, "P0", _get_card(repo, "SEC", "85"), "space")
        u1 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        u2 = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _add_hand(state, "P0", _her(repo))       # Command
        _add_hand(state, "P0", _her(repo))       # Command
        _add_hand(state, "P0", _agg_vil(repo))   # Villainy
        return state, rampart, u1, u2

    def test_sec_85_disclose_gives_experience(self, repo):
        state, rampart, u1, u2 = self._setup(repo)
        state = _fire_on_attack(state, rampart)
        assert any(d.kind == "disclose" for d in state.pending_decisions)
        state = _drive_all(state, pick_token_ids=[u1.instance_id, u2.instance_id])
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, u1.instance_id)) == 1
        assert _experience_count(_find_instance(state, u2.instance_id)) == 1

    def test_sec_85_decline_disclose_no_tokens(self, repo):
        state, rampart, u1, u2 = self._setup(repo)
        state = _fire_on_attack(state, rampart)
        state = _drive_all(state, decline_disclose=True)
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, u1.instance_id)) == 0


# ══ Group chancellor-palpatine:04 — Combat tricks, buffs & tempo ═════════════════

# ── SEC_124 Budget Scheming (event: Experience to up to 3 Official units) ────────

class TestBudgetScheming:
    def test_sec_124_gives_experience_to_officials(self, repo):
        state = _make_state()
        off1 = _place(state, "P0", _get_card(repo, "SEC", "44"), "ground")   # Populist Champion (Official)
        off2 = _place(state, "P0", _get_card(repo, "SEC", "44"), "ground")
        nonoff = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # Rebel/Trooper (not Official)
        state, _ = _play_event_from_hand(state, repo, "SEC", "124")
        assert any(d.kind == "select_token" for d in state.pending_decisions)
        state = _drive_all(state, pick_token_ids=[off1.instance_id, off2.instance_id])
        assert not state.pending_decisions
        assert _experience_count(_find_instance(state, off1.instance_id)) == 1
        assert _experience_count(_find_instance(state, off2.instance_id)) == 1
        assert _experience_count(_find_instance(state, nonoff.instance_id)) == 0   # non-Official ineligible

    def test_sec_124_not_offered_without_official(self, repo):
        state = _make_state()
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # only a non-Official unit
        state, _ = _play_event_from_hand(state, repo, "SEC", "124")
        # no eligible Official unit → select_token no-op, no prompt
        assert all(d.kind != "select_token" for d in state.pending_decisions)


# ── SEC_245 When Has Become Now (play a Plot card from resources, then ramp) ─────

class TestWhenHasBecomeNow:
    def _add_deck(self, state, owner, repo, n=3):
        from swu.engine.state import CardInstance, Zone
        for i in range(n):
            ci = CardInstance(f"{owner}_deck_{i}", _get_card(repo, "SOR", "46"), owner, Zone.DECK)
            state.player_by_id(owner).deck.append(ci)

    def _add_plot_resource(self, state, owner, repo, num="36"):
        from swu.engine.state import CardInstance, Zone
        ci = CardInstance(f"{owner}_plotres", _get_card(repo, "SEC", num), owner, Zone.RESOURCES)
        ci.face_down = True
        ci.exhausted = False
        state.player_by_id(owner).resources.append(ci)
        return ci

    def test_sec_245_plays_plot_card_and_ramps(self, repo):
        from swu.engine.actions import legal_actions, apply, PlotPlay
        state = _make_state()
        self._add_deck(state, "P0", repo, n=3)
        plot_ci = self._add_plot_resource(state, "P0", repo, "36")   # Dogmatic Shock Squad (Plot, no WhenPlayed)
        _give_resources(state, "P0", 20)                             # cover its Plot cost
        state, _ = _play_event_from_hand(state, repo, "SEC", "245", resources=0)
        p0 = state.player_by_id("P0")
        res_before = len(p0.resources)
        deck_before = len(p0.deck)
        assert state.pending_decisions[-1].kind == "plot"
        pp = next(a for a in legal_actions(state)
                  if isinstance(a, PlotPlay) and a.instance_id == plot_ci.instance_id)
        state = apply(state, pp)
        assert not state.pending_decisions                           # single-shot resolved
        p0 = state.player_by_id("P0")
        assert any(u.instance_id == plot_ci.instance_id
                   for u in p0.ground_arena + p0.space_arena)        # Plot unit now in play
        assert len(p0.resources) == res_before + 1                  # net +1 resource (ramp on top of Plot's replace)
        assert len(p0.deck) == deck_before - 2                      # Plot's replace + the ramp each pull one

    def test_sec_245_decline_no_ramp(self, repo):
        from swu.engine.actions import legal_actions, apply, FinishPlot
        state = _make_state()
        self._add_deck(state, "P0", repo, n=3)
        plot_ci = self._add_plot_resource(state, "P0", repo, "36")
        _give_resources(state, "P0", 20)
        state, _ = _play_event_from_hand(state, repo, "SEC", "245", resources=0)
        p0 = state.player_by_id("P0")
        res_before = len(p0.resources)
        deck_before = len(p0.deck)
        assert state.pending_decisions[-1].kind == "plot"
        state = apply(state, next(a for a in legal_actions(state) if isinstance(a, FinishPlot)))
        assert not state.pending_decisions
        p0 = state.player_by_id("P0")
        assert len(p0.resources) == res_before                      # declined → no play
        assert len(p0.deck) == deck_before                          # declined → no ramp
        assert any(r.instance_id == plot_ci.instance_id for r in p0.resources)   # still a face-down resource

    def test_sec_245_no_plot_card_no_decision(self, repo):
        state = _make_state()
        self._add_deck(state, "P0", repo, n=3)
        _give_resources(state, "P0", 5)
        deck_before = len(state.player_by_id("P0").deck)
        state, _ = _play_event_from_hand(state, repo, "SEC", "245", resources=0)
        # no Plot card in resources → push_plot_ability no-op → no decision, no ramp ("if you do")
        assert not state.pending_decisions
        assert len(state.player_by_id("P0").deck) == deck_before


# ══ Group chancellor-palpatine:05 — Miscellaneous abilities ═════════════════════
#   * SEC_31  Nute Gunray — optional WhenPlayed/OnAttack: give another friendly
#     Official unit Sentinel for this phase (GrantKeyword reuse, Bodhi Rook LAW_104).
#   * SEC_33  Sly Moore — WhenPlayed: for this phase, each enemy unit gets -2/-0
#     while it's attacking a base (NEW small engine gate: `attacking_base` on
#     compute_power + a `while_attacking_base` stats-modifier flag, base-attack site).
#   * SEC_83  ISB Shuttle — WhenPlayed: if a friendly unit was defeated this phase,
#     create a Spy token (inline gate on defeated_controllers_this_round + tokens).
#   * SEC_87  Dedra Meero — OnAttack: create a Spy token (create-token-unit reuse).
#   * SEC_92  I Am the Senate — event: create 5 Spy tokens (create-token-unit reuse).

def _spy_tokens(state, owner_id="P0"):
    """Return the owner's in-play Spy token-unit instances."""
    from swu.cards.models import TokenUnit
    ps = state.player_by_id(owner_id)
    return [ci for ci in ps.ground_arena + ps.space_arena
            if isinstance(ci.card_def, TokenUnit) and ci.card_def.name == "Spy"]


class TestNuteGunray:
    def test_sec_31_when_played_grants_sentinel_to_official(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        nute = _place(state, "P0", _get_card(repo, "SEC", "31"), "ground")
        official = _place(state, "P0", _get_card(repo, "SEC", "44"), "ground")  # Populist Champion (Official)
        assert not has_keyword(state, official, Keyword.SENTINEL)
        state = _fire_when_played(state, nute)
        assert _has_accept(state)
        state = _accept(state)
        state = _choose_target(state, official.instance_id)
        state = _resolve_all(state)
        official = _find_instance(state, official.instance_id)
        assert has_keyword(state, official, Keyword.SENTINEL)   # granted for this phase

    def test_sec_31_on_attack_grants_sentinel(self, repo):
        from swu.engine.keywords import has_keyword, Keyword
        state = _make_state()
        nute = _place(state, "P0", _get_card(repo, "SEC", "31"), "ground")
        official = _place(state, "P0", _get_card(repo, "SEC", "44"), "ground")
        state = _fire_on_attack(state, nute)
        assert _has_accept(state)
        state = _accept(state)
        state = _choose_target(state, official.instance_id)
        state = _resolve_all(state)
        official = _find_instance(state, official.instance_id)
        assert has_keyword(state, official, Keyword.SENTINEL)

    def test_sec_31_not_offered_without_another_official(self, repo):
        state = _make_state()
        nute = _place(state, "P0", _get_card(repo, "SEC", "31"), "ground")
        _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # not Official
        state = _fire_when_played(state, nute)
        # Nute is Official but "another" (not_self) excludes him → no legal target
        assert not _has_accept(state)


class TestSlyMoore:
    def test_sec_33_debuffs_enemy_attacking_base(self, repo):
        from swu.engine.actions import apply, legal_actions, AttackWithUnit
        state = _make_state()
        sly = _place(state, "P1", _get_card(repo, "SEC", "33"), "ground")
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # power 3
        state = _fire_when_played(state, sly)
        state = _resolve_all(state)
        base_before = state.players[1].base_instance.damage
        atk = next(a for a in legal_actions(state)
                   if isinstance(a, AttackWithUnit)
                   and a.attacker_id == attacker.instance_id and a.defender_id is None)
        state = apply(state, atk)
        assert state.players[1].base_instance.damage - base_before == 1   # 3 - 2

    def test_sec_33_no_debuff_when_attacking_unit(self, repo):
        from swu.engine.actions import compute_power, compute_hp
        state = _make_state()
        sly = _place(state, "P1", _get_card(repo, "SEC", "33"), "ground")
        attacker = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")  # 3/7
        state = _fire_when_played(state, sly)
        state = _resolve_all(state)
        attacker = _find_instance(state, attacker.instance_id)
        # attacking a unit (or any non-base context) → the debuff does NOT apply
        assert compute_power(state, attacker, is_attacking=True, attacking_unit=True) == 3
        # attacking a base → -2
        assert compute_power(state, attacker, is_attacking=True, attacking_base=True) == 1
        # HP (7) is never touched by the -2/-0 debuff
        assert compute_hp(state, attacker) == 7


class TestISBShuttle:
    def test_sec_83_creates_spy_if_friendly_defeated_this_phase(self, repo):
        from swu.engine.actions import _defeat_unit
        state = _make_state()
        victim = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        _defeat_unit(state, state.player_by_id("P0"), victim)   # a friendly unit dies this phase
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "83"), "ground")
        assert len(_spy_tokens(state)) == 0
        state = _fire_when_played(state, shuttle)
        state = _resolve_all(state)
        assert len(_spy_tokens(state)) == 1

    def test_sec_83_no_spy_without_friendly_defeat(self, repo):
        state = _make_state()
        shuttle = _place(state, "P0", _get_card(repo, "SEC", "83"), "ground")
        state = _fire_when_played(state, shuttle)
        state = _resolve_all(state)
        assert len(_spy_tokens(state)) == 0


class TestDedraMeero:
    def test_sec_87_on_attack_creates_spy_token(self, repo):
        state = _make_state()
        dedra = _place(state, "P0", _get_card(repo, "SEC", "87"), "ground")
        assert len(_spy_tokens(state)) == 0
        state = _fire_on_attack(state, dedra)
        state = _resolve_all(state)
        assert len(_spy_tokens(state)) == 1


class TestIAmTheSenate:
    def test_sec_92_creates_five_spy_tokens(self, repo):
        state = _make_state()
        state, _ = _play_event_from_hand(state, repo, "SEC", "92", resources=20)
        state = _resolve_all(state)
        assert len(_spy_tokens(state)) == 5


# ══ Group chancellor-palpatine:06 — New primitive: opponent-chooses-target ═══════
#   * LOF_43 The Tragedy of Plagueis — event: (1) choose a friendly unit, it can't
#     be defeated by having no remaining HP this phase (NEW `prevent_hp_defeat`
#     marker read by actions._hp_lethal at every HP-defeat gate — the Protection
#     marker's mirror, for HP defeat instead of ability defeat); (2) an opponent
#     chooses a unit they control, defeat it (the `disposition="defeat"` /
#     `units_only` extension of the existing opponent_chooses_target kind, SHD_246).

def _choose_own(state, target_id):
    from swu.engine.actions import apply, ChooseOwnTarget
    return apply(state, next(a for a in _legal(state)
                             if isinstance(a, ChooseOwnTarget) and a.target_id == target_id))


class TestTragedyOfPlagueis:
    def test_lof_43_protects_friendly_and_opponent_defeats_own_unit(self, repo):
        state = _make_state()
        prot = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        prot_id, victim_id = prot.instance_id, victim.instance_id
        state, _ = _play_event_from_hand(state, repo, "LOF", "43")
        # Clause 1: choose the friendly unit to protect.
        state = _choose_target(state, prot_id)
        # Clause 2: the opponent (P1) must pick one of their units to be defeated.
        top = state.pending_decisions[-1]
        assert top.kind == "opponent_chooses_target"
        assert top.context["disposition"] == "defeat"
        assert top.deciding_player_id == "P1"
        state = _choose_own(state, victim_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        assert _find_instance(state, victim_id) is None            # opponent's unit defeated
        assert _find_instance(state, prot_id) is not None          # protected unit untouched
        assert any(m.kind == "prevent_hp_defeat" and m.target_instance_id == prot_id
                   for m in state.modifiers)                        # protection marker applied

    def test_lof_43_protected_unit_survives_lethal_damage(self, repo):
        from swu.abilities.resolver import _apply_deal_damage
        from swu.engine.actions import compute_hp, _sweep_defeated_units
        state = _make_state()
        prot = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")     # 3/7
        doomed = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")   # 3/7, unmarked
        prot_id, doomed_id = prot.instance_id, doomed.instance_id
        # No enemy unit → clause 2 fizzles; only clause 1 protects `prot`.
        state, _ = _play_event_from_hand(state, repo, "LOF", "43")
        state = _choose_target(state, prot_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        prot = _find_instance(state, prot_id)
        _apply_deal_damage(state, prot_id, compute_hp(state, prot))            # exactly lethal
        doomed = _find_instance(state, doomed_id)
        _apply_deal_damage(state, doomed_id, compute_hp(state, doomed))
        _sweep_defeated_units(state)
        assert _find_instance(state, prot_id) is not None    # protected: survives 0 remaining HP
        assert _find_instance(state, doomed_id) is None      # unmarked: defeated normally

    def test_lof_43_no_friendly_unit_still_defeats_opponent(self, repo):
        state = _make_state()
        victim = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")
        victim_id = victim.instance_id
        # P0 controls no unit → clause 1 fizzles; clause 2 still forces the opponent
        # to defeat one of their own units.
        state, _ = _play_event_from_hand(state, repo, "LOF", "43")
        assert state.pending_decisions[-1].kind == "opponent_chooses_target"
        state = _choose_own(state, victim_id)
        state = _resolve_all(state)
        assert not state.pending_decisions
        assert _find_instance(state, victim_id) is None

    def test_lof_43_marker_does_not_block_ability_defeat(self, repo):
        from swu.abilities.resolver import _apply_defeat_unit
        state = _make_state()
        prot = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")
        prot_id = prot.instance_id
        state, _ = _play_event_from_hand(state, repo, "LOF", "43")   # no enemy → clause 2 fizzles
        state = _choose_target(state, prot_id)
        state = _resolve_all(state)
        # The marker prevents ONLY no-remaining-HP defeat, never a "Defeat that unit"
        # ability (the Protection-marker mirror).
        _apply_defeat_unit(state, prot_id)
        assert _find_instance(state, prot_id) is None
