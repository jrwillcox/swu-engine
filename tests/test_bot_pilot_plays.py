"""The heuristic bot plays Pilots.

A player reported that the bot never played a Piloting unit as an upgrade.  It
could see the move — the engine offered ``PilotPlay`` — but the bot scored it a
flat 0.0, level with Pass, so playing the card as a unit always won.  It also
declined every "attach this unit as a Pilot" offer outright.

These tests pin the replacement: the view reports what a Pilot play costs, the
bot scores ``PilotPlay`` on the unit-play scale, and the two Pilot decisions
(``pilot_self_attach``, ``play_via_piloting``) are judged rather than declined.
Synthetic cards only, so no card database is needed.
"""
from __future__ import annotations

import uuid

from swu.engine.views import CardView, PendingDecisionView, PlayerView, PlayerZoneView
from swu.players.heuristic_bot import HeuristicBot, W_PASS


# ── CardView-level helpers ────────────────────────────────────────────────────

def _cv(iid, ctype="Unit", *, power=2, hp=2, up=0, uhp=0, cost=2, owner="P0",
        exhausted=False, damage=0, piloting_cost=None):
    return CardView(
        instance_id=iid, card_id=1, card_name=iid, card_type=ctype,
        owner_id=owner, zone="SPACE_ARENA", exhausted=exhausted, damage=damage,
        face_down=False, deployed=False, epic_action_spent=False,
        effective_power=power, effective_hp=hp, attached_upgrades=[],
        cost=cost, keywords=[], upgrade_power=up, upgrade_hp=uhp,
        piloting_cost=piloting_cost,
    )


def _zone(pid, **over):
    base = dict(player_id=pid, deck_count=0, hand=[], hand_count=0, discard=[],
                resources=[], resource_count=0, available_resources=3, credits=0,
                ground_arena=[], space_arena=[], base_zone=[], is_eliminated=False)
    base.update(over)
    return PlayerZoneView(**base)


def _view(my, opp, decision=None):
    pending = [] if decision is None else [decision]
    return PlayerView(
        viewer_id="P0", phase="ACTION", round_number=3, active_player_id="P0",
        initiative_holder_id="P0", my=my, opponent=opp,
        event_log_tail=[], pending_decisions=pending,
    )


def _pilot_in_hand():
    """A Mandalorian JTL_210-shaped pilot: 5-cost 5/6 unit, or +3/+1 for 2."""
    return _cv("pilot", power=5, hp=6, up=3, uhp=1, cost=5, piloting_cost=2)


# ── PilotPlay scoring ─────────────────────────────────────────────────────────

def test_pilot_play_scores_above_pass():
    """The bug: PilotPlay used to score 0.0, level with Pass."""
    from swu.engine.actions import PilotPlay
    bot = HeuristicBot("P0", seed=1)
    idx = {"pilot": (_pilot_in_hand(), "my"), "ship": (_cv("ship"), "my")}
    assert bot._score_pilot_play(PilotPlay("pilot", "ship"), idx) > W_PASS + 30


def test_ready_host_is_worth_more_than_exhausted_host():
    """A ready Vehicle swings with the boost this round; an exhausted one can't."""
    bot = HeuristicBot("P0", seed=1)
    pilot = _pilot_in_hand()
    assert (bot._pilot_value(pilot, _cv("a", exhausted=False))
            > bot._pilot_value(pilot, _cv("b", exhausted=True)))


def test_pilot_play_onto_unreadable_or_enemy_host_is_refused():
    from swu.engine.actions import PilotPlay
    bot = HeuristicBot("P0", seed=1)
    idx = {"pilot": (_pilot_in_hand(), "my"), "theirs": (_cv("theirs"), "opp")}
    assert bot._score_pilot_play(PilotPlay("pilot", "theirs"), idx) < W_PASS
    assert bot._score_pilot_play(PilotPlay("pilot", "missing"), idx) < W_PASS


def test_disabling_the_weight_restores_the_old_behaviour():
    """``W_PLAY_PILOT`` is tunable, and a very low value switches piloting off —
    the arena comparison against the pre-fix bot relies on that."""
    from swu.engine.actions import PilotPlay
    bot = HeuristicBot("P0", seed=1, weights={"W_PLAY_PILOT": -1000})
    idx = {"pilot": (_pilot_in_hand(), "my"), "ship": (_cv("ship"), "my")}
    assert bot._score_pilot_play(PilotPlay("pilot", "ship"), idx) < W_PASS


# ── pilot_self_attach (Poe Dameron JTLP_6, Sidon Ithano JTL_213) ──────────────

def _self_attach_view(source, my_units=(), opp_units=()):
    decision = PendingDecisionView(
        deciding_player_id="P0", kind="pilot_self_attach",
        context={"source_id": source.instance_id, "controller_id": "P0"},
        is_mine=True)
    my = _zone("P0", space_arena=[source, *my_units])
    opp = _zone("P1", space_arena=list(opp_units))
    return _view(my, opp, decision)


def _self_attach_legal(*vehicle_ids):
    from swu.engine.actions import AttachSelfAsPilot, DeclineAttachSelfAsPilot
    return [AttachSelfAsPilot(v) for v in vehicle_ids] + [DeclineAttachSelfAsPilot()]


def test_sidon_rides_an_enemy_ship_it_would_destroy():
    """Sidon Ithano is -2/-2 as a Pilot: on a 2-HP enemy ship that is removal."""
    bot = HeuristicBot("P0", seed=1)
    sidon = _cv("sidon", power=2, hp=2, up=-2, uhp=-2)
    frail = _cv("frail", power=3, hp=2, owner="P1")
    sturdy = _cv("sturdy", power=1, hp=8, owner="P1")
    view = _self_attach_view(sidon, opp_units=[frail, sturdy])
    chosen = bot.choose_action(view, _self_attach_legal("frail", "sturdy"))
    assert type(chosen).__name__ == "AttachSelfAsPilot"
    assert chosen.vehicle_id == "frail"


def test_a_pilot_that_buffs_is_never_put_on_an_enemy_ship():
    bot = HeuristicBot("P0", seed=1)
    friendly_pilot = _cv("poe", power=1, hp=1, up=2, uhp=3)
    enemy = _cv("enemy", power=3, hp=3, owner="P1")
    view = _self_attach_view(friendly_pilot, opp_units=[enemy])
    chosen = bot.choose_action(view, _self_attach_legal("enemy"))
    assert type(chosen).__name__ == "DeclineAttachSelfAsPilot"


def test_keeps_the_unit_when_its_body_beats_the_boost():
    """Poe JTLP_6 is a 3/3 unit or +2/+3 on an exhausted ship: keep the body."""
    bot = HeuristicBot("P0", seed=1)
    poe = _cv("poe", power=3, hp=3, up=2, uhp=3)
    ship = _cv("xwing", exhausted=True)
    view = _self_attach_view(poe, my_units=[ship])
    chosen = bot.choose_action(view, _self_attach_legal("xwing"))
    assert type(chosen).__name__ == "DeclineAttachSelfAsPilot"


def test_attaches_when_the_boost_beats_the_body():
    """A 1/1 that adds +3/+3 to a ready ship is worth more as a Pilot."""
    bot = HeuristicBot("P0", seed=1)
    pilot = _cv("ace", power=1, hp=1, up=3, uhp=3)
    ship = _cv("ship", exhausted=False)
    view = _self_attach_view(pilot, my_units=[ship])
    chosen = bot.choose_action(view, _self_attach_legal("ship"))
    assert type(chosen).__name__ == "AttachSelfAsPilot"


# ── play_via_piloting (Wedge Antilles JTL_8) ──────────────────────────────────

def test_play_via_piloting_prefers_the_ready_host():
    from swu.engine.actions import PlayViaPiloting
    bot = HeuristicBot("P0", seed=1)
    pilot = _pilot_in_hand()
    tired = _cv("tired", exhausted=True)
    ready = _cv("ready", exhausted=False)
    decision = PendingDecisionView(
        deciding_player_id="P0", kind="play_via_piloting",
        context={"source_id": "wedge", "cost_reduction": 1}, is_mine=True)
    view = _view(_zone("P0", hand=[pilot], space_arena=[tired, ready]),
                 _zone("P1"), decision)
    legal = [PlayViaPiloting("pilot", "tired"), PlayViaPiloting("pilot", "ready")]
    assert bot.choose_action(view, legal).vehicle_target_id == "ready"


# ── Engine level: the view and a real legal-action list ───────────────────────

def _synthetic_pilot(owner_id, *, cost=5, piloting="Piloting [2 resources]"):
    from swu.cards.models import Unit
    from swu.engine.state import CardInstance, Zone
    card = Unit(
        id=77711, card_uid=None, set_code="TST", set_name="T",
        card_number="BP", name="Bot Test Pilot", subtitle=None, type="Unit",
        rarity="Common", is_unique=False, artist=None, text=None,
        text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=("Piloting",), traits=("Pilot",), arenas=("Ground",),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=cost, power=5, hp=6, upgrade_power=3, upgrade_hp=1,
        epic_action=piloting,
    )
    return CardInstance(
        instance_id=f"{owner_id}_pilot_{uuid.uuid4().hex[:6]}",
        card_def=card, owner_id=owner_id, zone=Zone.HAND,
    )


def _pilot_board():
    """P0: a ready Vehicle, the synthetic pilot in hand, 3 ready resources —
    enough for the Pilot mode (2) but not the unit (5)."""
    from tests.test_sor_cards import _make_state
    from tests.test_piloting import _give_resources, _place_vehicle
    state = _make_state()
    pilot = _synthetic_pilot("P0")
    state.player_by_id("P0").hand.append(pilot)
    vehicle = _place_vehicle(state, "P0", arena="space")
    vehicle.exhausted = False
    _give_resources(state, "P0", 3)
    return state, pilot, vehicle


def test_view_reports_piloting_cost_for_own_hand_only():
    from swu.engine.actions.costs import _piloting_cost
    state, pilot, vehicle = _pilot_board()
    ps = state.player_by_id("P0")
    mine = state.view_for("P0").my
    hand_cv = next(c for c in mine.hand if c.instance_id == pilot.instance_id)
    assert hand_cv.piloting_cost == _piloting_cost(state, pilot, ps) == 2
    assert hand_cv.to_dict()["piloting_cost"] == 2
    # Arena cards, and anything the opponent sees, carry no Piloting cost.
    assert all(c.piloting_cost is None for c in mine.space_arena)
    assert state.view_for("P1").opponent.hand == []


def test_bot_pilots_when_it_cannot_afford_the_unit():
    """End to end: with only the Pilot mode affordable and a ready Vehicle, the
    bot plays the Pilot instead of passing (which it used to do half the time)."""
    from swu.engine.actions import legal_actions
    state, pilot, vehicle = _pilot_board()
    legal = legal_actions(state)
    kinds = {type(a).__name__ for a in legal}
    assert "PilotPlay" in kinds and "PlayCard" not in kinds
    chosen = HeuristicBot("P0", seed=1).choose_action(state.view_for("P0"), legal)
    assert type(chosen).__name__ == "PilotPlay"
    assert chosen.vehicle_target_id == vehicle.instance_id


# ── The LLM opponent is told about Pilots ─────────────────────────────────────

def test_llm_prompt_shows_the_pilot_mode():
    """Normal/Hard: the model sees each hand pilot's cost and boost, and the
    rules brief explains what PilotPlay does."""
    from swu.players.llm_player import Style, _card_brief, _system_prompt
    brief = _card_brief(_pilot_in_hand().to_dict())
    assert brief["piloting_cost"] == 2
    assert brief["pilot_bonus"] == "+3/+1"
    assert "piloting_cost" not in _card_brief(_cv("plain").to_dict())
    for style in Style:
        assert "PilotPlay" in _system_prompt(style)
