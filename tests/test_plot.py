"""
Plot keyword — synthetic-card framework tests (jabba-the-hutt:01).

Plot ("When you deploy a leader, you may play this card from your resources,
paying its cost.  Replace it with the top card of your deck.") lets a card sitting
in your resource zone be played for its printed cost when you deploy a leader,
then replaced with the deck top (preserving your resource count, exactly like
Smuggle).  These tests build minimal synthetic cards and exercise the keyword
purely through the public ``legal_actions`` / ``apply`` interface (a real
DeployLeader pushing a ``"plot"`` decision), independent of any specific real
card.
"""
from __future__ import annotations

import uuid


from tests.test_sor_cards import repo, _get_card, _make_state  # noqa: F401
from tests.test_smuggle import _add_resource, _fill_resources, _add_deck_card

from swu.cards.models import AspectPip, Leader, Unit
from swu.engine.state import CardInstance, Zone
from swu.engine.actions import (
    legal_actions, apply, DeployLeader, PlotPlay, FinishPlot,
)


def _aspect(name, pos=0):
    return AspectPip(position=pos, name=name, color="x", is_duplicate=False)


_PLOT_REMINDER = ("Plot (When you deploy a leader, you may play this card from "
                  "your resources, paying its cost. Replace it with the top card "
                  "of your deck.)")


def _synthetic_plot_unit(name="Plotter", cost=2, aspects=(), power=2, hp=3,
                         keywords=("Plot",), arena="Ground"):
    return Unit(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="1", name=name, subtitle=None, type="Unit", rarity="Common",
        is_unique=False, artist=None, text=_PLOT_REMINDER, text_styled=None,
        rules=None, rules_styled=None,
        aspects=tuple(_aspect(a, i) for i, a in enumerate(aspects)),
        keywords=keywords, traits=("Underworld",), arenas=(arena,),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=cost, power=power, hp=hp,
    )


def _synthetic_leader(name="Test Leader", threshold=2):
    return Leader(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="2", name=name, subtitle=None, type="Leader", rarity="Common",
        is_unique=True, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None, aspects=(), keywords=(), traits=(), arenas=("Ground",),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        power=5, hp=8, deploy_box=None,
        epic_action=(f"Epic Action: Deploy this leader. (You control {threshold} "
                     "or more resources.)"),
    )


def _add_leader(state, owner_id, leader_def):
    ps = state.player_by_id(owner_id)
    ci = CardInstance(
        instance_id=f"{owner_id}_leader_{uuid.uuid4().hex[:4]}",
        card_def=leader_def, owner_id=owner_id, zone=Zone.BASE_ZONE,
    )
    ps.base_zone.append(ci)
    return ci


def _deploy(state, owner_id="P0"):
    """Deploy ``owner_id``'s leader through the public apply() path."""
    return apply(state, DeployLeader())


class TestPlotKeyword:
    def test_plot_offered_on_leader_deploy(self, repo):
        state = _make_state()
        unit = _synthetic_plot_unit(cost=2)
        plot = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))

        state = _deploy(state)
        assert state.pending_decisions
        assert state.pending_decisions[-1].kind == "plot"

        acts = legal_actions(state)
        plays = [a for a in acts if isinstance(a, PlotPlay)
                 and a.instance_id == plot.instance_id]
        assert len(plays) == 1
        assert any(isinstance(a, FinishPlot) for a in acts)

    def test_plot_not_offered_without_a_plot_card(self, repo):
        state = _make_state()
        _fill_resources(state, "P0", 4, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))

        state = _deploy(state)
        # No Plot card → no plot decision; the deploy passed the turn to P1.
        assert not any(d.kind == "plot" for d in state.pending_decisions)
        assert state.active_player_index == 1
        ps0 = state.player_by_id("P0")
        assert any(u.card_def.type == "Leader" for u in ps0.ground_arena)

    def test_plot_not_offered_when_unaffordable(self, repo):
        state = _make_state()
        unit = _synthetic_plot_unit(cost=5)
        _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 2, repo)  # only 2 OTHER ready < cost 5
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=1))

        state = _deploy(state)
        assert not any(d.kind == "plot" for d in state.pending_decisions)

    def test_plot_play_puts_unit_in_play_and_replaces_from_deck(self, repo):
        state = _make_state()
        unit = _synthetic_plot_unit(cost=2)
        plot = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        deck = _add_deck_card(state, "P0", repo)
        repl_id = deck[0].instance_id
        _add_leader(state, "P0", _synthetic_leader(threshold=2))

        state = _deploy(state)
        ps0 = state.player_by_id("P0")
        res_before = len(ps0.resources)
        deck_before = len(ps0.deck)

        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == plot.instance_id)
        state = apply(state, play)

        ps0 = state.player_by_id("P0")
        assert any(u.instance_id == plot.instance_id for u in ps0.ground_arena)
        assert not any(r.instance_id == plot.instance_id for r in ps0.resources)
        # Resource count preserved by the replacement; deck shrank by one.
        assert len(ps0.resources) == res_before
        assert len(ps0.deck) == deck_before - 1
        assert any(r.instance_id == repl_id and r.face_down for r in ps0.resources)
        # 2 resources exhausted to pay the printed cost.
        assert sum(1 for r in ps0.resources if r.exhausted) == 2
        # The plot decision is still pending (more Plot cards could exist), but
        # only FinishPlot remains now.
        assert state.pending_decisions[-1].kind == "plot"
        finish = next(a for a in legal_actions(state) if isinstance(a, FinishPlot))
        state = apply(state, finish)
        assert not state.pending_decisions
        assert state.active_player_index == 1  # turn handed over

    def test_plot_replacement_skipped_on_empty_deck(self, repo):
        state = _make_state()
        unit = _synthetic_plot_unit(cost=1)
        plot = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 2, repo)
        # No deck cards.
        _add_leader(state, "P0", _synthetic_leader(threshold=1))

        state = _deploy(state)
        ps0 = state.player_by_id("P0")
        res_before = len(ps0.resources)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == plot.instance_id)
        state = apply(state, play)
        ps0 = state.player_by_id("P0")
        assert len(ps0.resources) == res_before - 1  # no replacement
        assert any(u.instance_id == plot.instance_id for u in ps0.ground_arena)

    def test_two_plot_cards_both_playable_off_one_deploy(self, repo):
        state = _make_state()
        a = _add_resource(state, "P0", _synthetic_plot_unit(name="Plot A", cost=1))
        b = _add_resource(state, "P0", _synthetic_plot_unit(name="Plot B", cost=1))
        _fill_resources(state, "P0", 4, repo)
        _add_deck_card(state, "P0", repo, n=2)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))

        state = _deploy(state)
        assert state.pending_decisions[-1].kind == "plot"

        # Play A.
        play_a = next(p for p in legal_actions(state)
                      if isinstance(p, PlotPlay) and p.instance_id == a.instance_id)
        state = apply(state, play_a)
        # B is still offered while plot is pending.
        assert state.pending_decisions[-1].kind == "plot"
        play_b = next(p for p in legal_actions(state)
                      if isinstance(p, PlotPlay) and p.instance_id == b.instance_id)
        state = apply(state, play_b)
        # Finish.
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, FinishPlot)))
        ps0 = state.player_by_id("P0")
        ids = {u.instance_id for u in ps0.ground_arena}
        assert {a.instance_id, b.instance_id} <= ids

    def test_non_plot_resource_not_offered(self, repo):
        state = _make_state()
        unit = _synthetic_plot_unit(cost=2, keywords=())  # no Plot keyword
        _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))

        state = _deploy(state)
        assert not any(d.kind == "plot" for d in state.pending_decisions)

    def test_card_conservation_through_plot(self, repo):
        from swu.engine.invariants import CheckContext, check
        state = _make_state()
        unit = _synthetic_plot_unit(cost=2)
        plot = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))
        ctx = CheckContext.from_state(state)

        state = _deploy(state)
        check(state, ctx)
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == plot.instance_id)
        state = apply(state, play)
        check(state, ctx)  # raises on any invariant violation
        state = apply(state, next(x for x in legal_actions(state)
                                  if isinstance(x, FinishPlot)))
        check(state, ctx)
