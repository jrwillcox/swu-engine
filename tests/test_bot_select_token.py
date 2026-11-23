"""The heuristic bot on the ``select_token`` "choose up to N units" decision.

That one decision gives tokens and buffs, but also exhausts, strips abilities,
bounces upgrades and (HMW) hands out Weakness tokens.  The bot used to assume
every pick helps and always chose its OWN units — exhausting itself with Evade
Arrest TS26_82, wasting No One Ever Knew SEC_196, stripping every friendly unit
with Kazuda Xiono JTL_18.  It now reads the payoff off the decision context.
"""
from __future__ import annotations

from tests.test_sor_cards import repo, _make_state, _place  # noqa: F401
from tests.test_fortify import _unit_def


def _pick(state, **select_token_kwargs):
    """Push a select_token decision for P0 and return the bot's choice."""
    from swu.engine.actions import legal_actions, push_select_token
    from swu.players.heuristic_bot import HeuristicBot
    src = state.player_by_id("P0").ground_arena[0]
    kw = {"token_type": None, "max_targets": 1, **select_token_kwargs}
    push_select_token(state, src, **kw)
    assert state.pending_decisions[-1].kind == "select_token"
    return HeuristicBot("P0", seed=0).choose_action(state.view_for("P0"),
                                                     legal_actions(state))


def _board():
    state = _make_state()
    mine = _place(state, "P0", _unit_def("Mine", "50", power=3, hp=4))
    foe = _place(state, "P1", _unit_def("Foe", "51", power=3, hp=4))
    mine.exhausted = foe.exhausted = False
    return state, mine, foe


def test_bot_exhaust_any_unit_targets_the_enemy(repo):        # Evade Arrest TS26_82
    state, _, foe = _board()
    a = _pick(state, controller="any", exhaust=True, max_targets=2)
    assert type(a).__name__ == "SelectTokenTarget" and a.target_id == foe.instance_id


def test_bot_exhaust_enemy_only_is_not_wasted(repo):          # No One Ever Knew SEC_196
    state, _, foe = _board()
    a = _pick(state, controller="enemy", exhaust=True)
    assert type(a).__name__ == "SelectTokenTarget" and a.target_id == foe.instance_id


def test_bot_exhaust_skips_an_already_exhausted_enemy(repo):
    state, _, foe = _board()
    foe.exhausted = True
    fresh = _place(state, "P1", _unit_def("Fresh", "52", power=1, hp=1))
    fresh.exhausted = False
    a = _pick(state, controller="any", exhaust=True)
    assert a.target_id == fresh.instance_id


def test_bot_declines_to_strip_its_own_abilities(repo):       # Kazuda Xiono JTL_18
    state, _, _ = _board()
    a = _pick(state, controller="friendly", suppress_abilities=True, max_targets=1)
    assert type(a).__name__ == "FinishSelectToken"


def test_bot_gives_weakness_to_an_enemy_preferring_a_kill(repo):   # HMW
    state, _, _ = _board()
    frail = _place(state, "P1", _unit_def("Frail", "53", power=1, hp=1))
    a = _pick(state, controller="any", token_type="Weakness", max_targets=3,
              allow_repeats=True)
    assert a.target_id == frail.instance_id


def test_bot_mandatory_harm_with_only_own_targets_picks_the_cheapest(repo):  # Shin Hati
    state, mine, _ = _board()
    tiny = _place(state, "P0", _unit_def("Tiny", "54", power=1, hp=1))
    a = _pick(state, controller="friendly", exhaust=True, mandatory=True,
              restrict_ids=[mine.instance_id, tiny.instance_id])
    assert a.target_id == tiny.instance_id


def test_bot_returns_only_opponent_owned_upgrades(repo):      # There Is No Conflict ASH_199
    from swu.engine.state import CardInstance
    from tests.test_sor_cards import _get_card
    state, mine, _ = _board()
    gear = _get_card(repo, "HMW", "190")   # a real Upgrade card (Enraged)
    own = CardInstance("P0_up", gear, "P0", mine.zone)
    theirs = CardInstance("P1_up", gear, "P1", mine.zone)
    mine.attached_upgrades += [own, theirs]
    a = _pick(state, kind="upgrade", controller="any", return_to_hand=True,
              max_targets=2, restrict_ids=[own.instance_id, theirs.instance_id])
    assert a.target_id == theirs.instance_id


def test_bot_still_gives_helpful_tokens_to_its_own_units(repo):   # Medal Ceremony SOR_245
    state, mine, _ = _board()
    a = _pick(state, controller="any", token_type="Experience", max_targets=3)
    assert a.target_id == mine.instance_id
