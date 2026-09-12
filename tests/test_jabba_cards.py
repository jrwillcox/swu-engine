"""
jabba-the-hutt deck card ability tests (LAW / SEC / JTL sets).

Group jabba-the-hutt:01 — Plot keyword + residuals:
  * SEC_186 Garindan — "When Played: Name a card. Look at an opponent's hand and
    discard a card with that name from it." (residual; the DiscardFromHand
    first-card simplification, documented in sec/abilities.py).
  * SEC_189 Lurking Snub Fighter — "When Played: You may exhaust a unit."
Both are unblocked by the Plot keyword (see tests/test_plot.py for the keyword
framework tests); these tests drive each card from its resource zone through a
real leader deploy → PlotPlay, then assert the residual ability.
"""
from __future__ import annotations

import uuid


from tests.test_sor_cards import repo, _get_card, _make_state, _place  # noqa: F401
from tests.test_smuggle import _add_resource, _fill_resources, _add_deck_card
from tests.test_plot import _synthetic_leader, _add_leader

from swu.engine.state import CardInstance, Zone
from swu.engine.actions import (
    legal_actions, apply, DeployLeader, PlotPlay, AcceptTrigger, ChooseTarget,
)


def _add_hand_card(state, owner_id, repo, set_code="SOR", num="46"):
    card = _get_card(repo, set_code, num)
    ci = CardInstance(
        instance_id=f"{owner_id}_hand_{uuid.uuid4().hex[:6]}",
        card_def=card, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


class TestGarindan:
    def test_sec_186_plot_play_discards_from_opponent_hand(self, repo):
        state = _make_state()
        garindan = _add_resource(state, "P0", _get_card(repo, "SEC", "186"))
        _fill_resources(state, "P0", 6, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))
        # Opponent hand to strip.
        _add_hand_card(state, "P1", repo)
        _add_hand_card(state, "P1", repo)
        hand_before = len(state.player_by_id("P1").hand)

        state = apply(state, DeployLeader())
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == garindan.instance_id)
        state = apply(state, play)

        ps0 = state.player_by_id("P0")
        ps1 = state.player_by_id("P1")
        # Garindan entered play via Plot.
        assert any(u.instance_id == garindan.instance_id for u in ps0.ground_arena)
        # Its When Played stripped one card from the opponent's hand (inline).
        assert len(ps1.hand) == hand_before - 1
        assert len(ps1.discard) == 1

    def test_sec_186_noop_when_opponent_hand_empty(self, repo):
        state = _make_state()
        garindan = _add_resource(state, "P0", _get_card(repo, "SEC", "186"))
        _fill_resources(state, "P0", 6, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))
        # P1 hand empty.

        state = apply(state, DeployLeader())
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == garindan.instance_id)
        state = apply(state, play)  # must not raise
        assert state.player_by_id("P1").discard == []


class TestLurkingSnubFighter:
    def test_sec_189_plot_play_may_exhaust_a_unit(self, repo):
        state = _make_state()
        lurking = _add_resource(state, "P0", _get_card(repo, "SEC", "189"))
        _fill_resources(state, "P0", 7, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))
        enemy = _place(state, "P1", _get_card(repo, "SOR", "46"))  # vanilla unit
        assert not enemy.exhausted

        state = apply(state, DeployLeader())
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == lurking.instance_id)
        state = apply(state, play)

        # Lurking Snub Fighter is a Space unit; it entered the space arena and its
        # optional "may exhaust a unit" trigger is now offered.
        ps0 = state.player_by_id("P0")
        assert any(u.instance_id == lurking.instance_id for u in ps0.space_arena)
        accept = next(a for a in legal_actions(state) if isinstance(a, AcceptTrigger))
        state = apply(state, accept)
        choose = next(a for a in legal_actions(state)
                      if isinstance(a, ChooseTarget) and a.target_id == enemy.instance_id)
        state = apply(state, choose)

        found = state.find_instance(enemy.instance_id)
        assert found is not None and found[1].exhausted

    def test_sec_189_optional_trigger_can_be_declined(self, repo):
        from swu.engine.actions import DeclineTrigger
        state = _make_state()
        lurking = _add_resource(state, "P0", _get_card(repo, "SEC", "189"))
        _fill_resources(state, "P0", 7, repo)
        _add_deck_card(state, "P0", repo)
        _add_leader(state, "P0", _synthetic_leader(threshold=2))

        state = apply(state, DeployLeader())
        play = next(a for a in legal_actions(state)
                    if isinstance(a, PlotPlay) and a.instance_id == lurking.instance_id)
        state = apply(state, play)
        # No enemy unit, but Lurking itself is a legal (friendly) target so the
        # optional trigger is offered; decline it.
        decline = next(a for a in legal_actions(state) if isinstance(a, DeclineTrigger))
        state = apply(state, decline)
        # Back to the plot decision (or, after finishing, the turn passes).
        assert state.pending_decisions[-1].kind == "plot"
