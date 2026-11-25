"""Known-deviation fixes (2026-11-24), the "medium" items:

1. "If a unit left play this phase" counts every route out of play — defeat,
   return to hand, put on a deck, capture — not only defeat.
2. "When this unit is dealt damage" observers and the base-damage ledgers see
   ability and indirect damage, not only combat damage.
"""
from __future__ import annotations

from tests.test_sor_cards import (  # noqa: F401
    repo, _make_state, _place, _get_card, _push_deck_top,
)
from tests.test_shd_cards import _put_in_hand
from tests.test_twi_cards import _place_leader


# ── 1. "left play" ────────────────────────────────────────────────────────────

def _bounce(state, ci):
    from swu.abilities.resolver import _apply_return_to_hand
    return _apply_return_to_hand(state, ci.instance_id)


def _capture(state, captor, target):
    from swu.engine.actions.zones import _apply_capture
    return _apply_capture(state, captor.instance_id, target.instance_id)


def _cond(state, source, name):
    from swu.abilities.registry import Condition, ConditionCheck
    return ConditionCheck(getattr(Condition, name)).evaluate(state, source)


def test_a_bounced_enemy_unit_counts_as_left_play(repo):
    state = _make_state()
    me = _place(state, "P0", _get_card(repo, "SOR", "46"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    assert not _cond(state, me, "ANY_UNIT_LEFT_PLAY_THIS_PHASE")
    state = _bounce(state, enemy)
    assert _cond(state, me, "ANY_UNIT_LEFT_PLAY_THIS_PHASE")
    assert _cond(state, me, "ENEMY_UNIT_LEFT_PLAY_THIS_PHASE")
    assert not _cond(state, me, "CONTROLLER_UNIT_LEFT_PLAY_THIS_PHASE")
    # A bounce is not a defeat: the "defeated" atoms stay false.
    assert not _cond(state, me, "ENEMY_UNIT_DEFEATED_THIS_PHASE")


def test_a_captured_friendly_unit_counts_for_its_controller(repo):
    state = _make_state()
    mine = _place(state, "P0", _get_card(repo, "SOR", "46"))
    watcher = _place(state, "P0", _get_card(repo, "SOR", "46"))
    captor = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state = _capture(state, captor, mine)
    assert _cond(state, watcher, "CONTROLLER_UNIT_LEFT_PLAY_THIS_PHASE")


def test_TWI_4_yoda_action_after_a_bounce(repo):
    from swu.engine.actions import legal_actions, UseAbility
    state = _make_state()
    yoda = _place_leader(state, "P0", _get_card(repo, "TWI", "4"))
    for _ in range(2):
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))

    def offered(s):
        return any(isinstance(a, UseAbility) and a.source_id == yoda.instance_id
                   for a in legal_actions(s))

    assert not offered(state)
    state = _bounce(state, enemy)
    assert offered(state)


def test_LOF_216_after_a_friendly_unit_is_captured(repo):
    from tests.test_lof_cards import _play_event_from_hand
    state = _make_state()
    mine = _place(state, "P0", _get_card(repo, "SOR", "46"))
    captor = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state = _capture(state, captor, mine)
    state, _evt = _play_event_from_hand(state, repo, "LOF", "216")
    assert state.player_by_id("P0").has_force_token is True


def test_SOR_15_boba_fires_when_an_enemy_unit_is_bounced(repo):
    state = _make_state()
    _place_leader(state, "P0", _get_card(repo, "SOR", "15"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    mine = _place(state, "P0", _get_card(repo, "SOR", "46"))
    state = _bounce(state, mine)                    # a friendly unit: no trigger
    assert not state.pending_decisions
    state = _bounce(state, enemy)
    assert state.pending_decisions, "the optional 'exhaust this leader' prompt"


def test_put_on_deck_counts_as_left_play(repo):
    from swu.engine.actions.zones import _apply_put_on_deck
    state = _make_state()
    me = _place(state, "P0", _get_card(repo, "SOR", "46"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state = _apply_put_on_deck(state, enemy.instance_id, to_top=False)
    assert _cond(state, me, "ENEMY_UNIT_LEFT_PLAY_THIS_PHASE")


def test_phase_rollover_clears_the_left_play_ledger(repo):
    state = _make_state()
    me = _place(state, "P0", _get_card(repo, "SOR", "46"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state = _bounce(state, enemy)
    state.game_memory.clear_phase()
    assert not _cond(state, me, "ANY_UNIT_LEFT_PLAY_THIS_PHASE")


# ── 2. non-combat damage ──────────────────────────────────────────────────────

def _ping(state, target, amount, dealer=None):
    """Ability damage to ``target`` (a unit or a base), then the settle-point drain."""
    from swu.abilities.resolver import _apply_deal_damage
    from swu.engine.actions.observers import _fire_damage_observers
    state = _apply_deal_damage(state, target.instance_id, amount, "test",
                               dealer_id=dealer.instance_id if dealer else None)
    return _fire_damage_observers(state)


def _offered_trigger(state, source):
    from swu.engine.actions import legal_actions, AcceptTrigger
    return any(isinstance(a, AcceptTrigger) and a.source_id == source.instance_id
               for a in legal_actions(state))


def test_SEC_143_elite_squad_triggers_on_ability_damage(repo):
    state = _make_state()
    squad = _place(state, "P0", _get_card(repo, "SEC", "143"))
    _place(state, "P1", _get_card(repo, "SOR", "51"))           # a unique target
    pinger = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state = _ping(state, squad, 1, dealer=pinger)
    assert _offered_trigger(state, squad)


def test_SEC_2_jabba_retaliates_for_ability_damage(repo):
    from tests.test_sec_cards import _deploy, _accept_optional_and_run, _choose
    state = _make_state()
    jabba = _deploy(state, "P0", _get_card(repo, "SEC", "2"))
    hurt = _place(state, "P0", _get_card(repo, "SOR", "46"))
    enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))
    state = _ping(state, hurt, 2, dealer=enemy)
    assert _offered_trigger(state, jabba)
    state = _accept_optional_and_run(state)
    state = _choose(state, enemy.instance_id)
    assert state.find_instance(enemy.instance_id)[1].damage == 2


def test_ability_damage_to_an_enemy_base_feeds_both_ledgers(repo):
    state = _make_state()
    me = _place(state, "P0", _get_card(repo, "SOR", "46"))
    state = _ping(state, state.player_by_id("P1").base_instance, 3, dealer=me)
    gm = state.game_memory
    assert gm.base_damage_dealt_this_phase.get("P0") == 3
    assert me.instance_id in gm.units_dealt_base_damage_this_round
    from swu.abilities.registry import Condition, ConditionCheck
    assert ConditionCheck(Condition.CONTROLLER_DEALT_N_BASE_DAMAGE_THIS_PHASE,
                          param=3).evaluate(state, me)


def test_damage_to_your_own_base_is_not_enemy_base_damage(repo):
    state = _make_state()
    me = _place(state, "P0", _get_card(repo, "SOR", "46"))
    state = _ping(state, state.player_by_id("P0").base_instance, 2, dealer=me)
    assert state.game_memory.base_damage_dealt_this_phase.get("P0", 0) == 0


def test_SOR_13_deployed_cassian_draws_on_ability_base_damage(repo):
    from tests.test_sec_cards import _deploy
    state = _make_state()
    cassian = _deploy(state, "P0", _get_card(repo, "SOR", "13"))
    me = _place(state, "P0", _get_card(repo, "SOR", "46"))
    state = _ping(state, state.player_by_id("P1").base_instance, 1, dealer=me)
    assert _offered_trigger(state, cassian)


# ── 3. "Play a card" offers events and upgrades ──────────────────────────────

def _palace(state, repo, owner="P0"):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(f"{owner}_dp", _get_card(repo, "LAW", "20"), owner, Zone.BASE_ZONE)
    state.player_by_id(owner).base_zone = [ci]
    return ci


def _use(state, source):
    from swu.engine.actions import legal_actions, apply, UseAbility
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, UseAbility)
                             and a.source_id == source.instance_id))


def _play_offered(state, card):
    from swu.engine.actions import legal_actions, PlayFromHand
    return next((a for a in legal_actions(state)
                 if isinstance(a, PlayFromHand) and a.instance_id == card.instance_id),
                None)


def test_LAW_20_palace_plays_an_event(repo):
    from tests.test_sor_cards import _give_resources
    from swu.engine.actions import apply
    state = _make_state()
    dp = _palace(state, repo)
    briefing = _put_in_hand(state, "P0", _get_card(repo, "SOR", "171"))   # draw 2
    for _ in range(3):
        _push_deck_top(state, "P0", _get_card(repo, "SOR", "128"))
    _give_resources(state, "P0", 10)
    state = _use(state, dp)
    play = _play_offered(state, briefing)
    assert play is not None, "the event is offered"
    state = apply(state, play)
    while state.pending_decisions:                  # "choose a player" etc.
        from swu.engine.actions import legal_actions
        state = apply(state, legal_actions(state)[0])
    ps = state.player_by_id("P0")
    assert any(c.instance_id == briefing.instance_id for c in ps.discard)
    # The event resolved: one player drew 2 (both hands started empty).
    assert len(ps.hand) + len(state.player_by_id("P1").hand) == 2


def test_LAW_20_palace_plays_an_upgrade_onto_a_chosen_host(repo):
    from tests.test_sor_cards import _give_resources
    from swu.engine.actions import apply, legal_actions, PlayUpgradeFromHand
    state = _make_state()
    dp = _palace(state, repo)
    host = _place(state, "P0", _get_card(repo, "SOR", "46"))
    training = _put_in_hand(state, "P0", _get_card(repo, "SOR", "120"))
    _give_resources(state, "P0", 10)
    state = _use(state, dp)
    state = apply(state, _play_offered(state, training))
    assert state.pending_decisions[-1].kind == "play_upgrade_from_hand"
    attach = next(a for a in legal_actions(state)
                  if isinstance(a, PlayUpgradeFromHand) and a.host_id == host.instance_id)
    state = apply(state, attach)
    host_now = state.find_instance(host.instance_id)[1]
    assert any(u.instance_id == training.instance_id for u in host_now.attached_upgrades)


def test_LAW_20_gate_opens_for_an_event_only_hand(repo):
    from tests.test_sor_cards import _give_resources
    from swu.engine.actions import legal_actions, UseAbility
    state = _make_state()
    dp = _palace(state, repo)
    _put_in_hand(state, "P0", _get_card(repo, "SOR", "171"))
    _give_resources(state, "P0", 10)
    assert any(isinstance(a, UseAbility) and a.source_id == dp.instance_id
               for a in legal_actions(state))


def test_LAW_3_kallus_waives_the_whole_aspect_penalty_on_an_event(repo):
    """Agent Kallus: "ignoring its aspect penalties" — all of them, not one pip."""
    from tests.test_sor_cards import _give_resources
    from tests.test_law_cards import _law12_leader_def, _law12_undeployed_leader
    from swu.engine.actions import apply, _play_cost
    state = _make_state()
    kallus = _law12_undeployed_leader(state, "P0", _law12_leader_def(repo, "LAW", "3"))
    briefing = _put_in_hand(state, "P0", _get_card(repo, "SOR", "171"))
    _give_resources(state, "P0", 10)
    printed = int(briefing.card_def.cost)
    assert _play_cost(state, briefing, state.player_by_id("P0")) > printed
    before = state.player_by_id("P0").available_resources
    state = _use(state, kallus)
    state = apply(state, _play_offered(state, briefing))
    # 1 for the ability + the event's printed cost.
    assert before - state.player_by_id("P0").available_resources == 1 + printed


def _separatist_event(repo):
    from swu.cards.models import Event
    from swu.abilities.registry import get_abilities
    for cd in repo.iter_all():
        if (isinstance(cd, Event) and "Separatist" in (cd.traits or ())
                and (cd.cost or 0) <= 3 and get_abilities(cd.set_code, cd.card_number)):
            return cd
    import pytest
    pytest.skip("no cheap Separatist event in the DB")


def test_TWI_5_dooku_offers_a_separatist_event_but_not_another(repo):
    from tests.test_sor_cards import _give_resources
    state = _make_state()
    dooku = _place_leader(state, "P0", _get_card(repo, "TWI", "5"))
    sep = _put_in_hand(state, "P0", _separatist_event(repo))
    other = _put_in_hand(state, "P0", _get_card(repo, "SOR", "171"))
    _give_resources(state, "P0", 10)
    state = _use(state, dooku)
    assert _play_offered(state, sep) is not None
    assert _play_offered(state, other) is None


# ── 4. "While attacking a … unit" keyword grants ─────────────────────────────

def _attack_unit(state, attacker, defender):
    from swu.engine.actions import apply, AttackWithUnit
    state.active_player_index = 0
    state.find_instance(attacker.instance_id)[1].exhausted = False
    return apply(state, AttackWithUnit(attacker.instance_id, defender.instance_id))


def _base_damage(state, pid="P1"):
    return state.player_by_id(pid).base_instance.damage


def _weaken(state, unit, hp):
    """-0/-hp for this phase, leaving ``unit`` undamaged."""
    from swu.abilities.registry import Duration
    from swu.abilities.resolver import _make_modifier
    state.modifiers.append(_make_modifier(state, unit.instance_id, unit.instance_id,
                                          0, -hp, Duration.THIS_PHASE))


def test_SEC_139_overwhelm_only_against_a_damaged_defender(repo):
    from swu.engine.keywords import has_keyword, Keyword
    # Damaged defender (3/7 with 5 damage): the 3-power attacker spills 1.
    state = _make_state()
    _place(state, "P0", _get_card(repo, "SEC", "139"))
    atk = _place(state, "P0", _get_card(repo, "SOR", "46"))
    dfd = _place(state, "P1", _get_card(repo, "SOR", "46"))
    dfd.damage = 5
    assert not has_keyword(state, atk, Keyword.OVERWHELM), "not shown out of combat"
    state = _attack_unit(state, atk, dfd)
    assert _base_damage(state) == 1
    # Undamaged defender with the same 2 HP left: no Overwhelm, no spill.
    state = _make_state()
    _place(state, "P0", _get_card(repo, "SEC", "139"))
    atk = _place(state, "P0", _get_card(repo, "SOR", "46"))
    dfd = _place(state, "P1", _get_card(repo, "SOR", "46"))
    _weaken(state, dfd, 5)
    state = _attack_unit(state, atk, dfd)
    assert _base_damage(state) == 0


def test_SHD_7_gideon_overwhelm_only_while_attacking_a_unit(repo):
    from tests.test_sec_cards import _deploy
    from swu.engine.keywords import has_keyword, Keyword
    state = _make_state()
    _deploy(state, "P0", _get_card(repo, "SHD", "7"))
    trooper = _place(state, "P0", _get_card(repo, "SOR", "128"))     # 3/1, cost 1
    dfd = _place(state, "P1", _get_card(repo, "SOR", "46"))
    dfd.damage = 6                                                   # 1 HP left
    assert not has_keyword(state, trooper, Keyword.OVERWHELM)
    state = _attack_unit(state, trooper, dfd)
    assert _base_damage(state) == 3          # (3 + 1) power, 1 HP: 3 spills over
