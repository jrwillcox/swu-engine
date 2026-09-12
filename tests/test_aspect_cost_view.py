"""The aspect-adjusted cost surcharge surfaced on the player's own hand cards.

`CardView.aspect_penalty` is the +2-per-unmatched-pip surcharge a hand card would
incur if played now, computed against the owner's base/leader aspects.  The web
UI renders it as a "+N" pill beside the printed cost.  It must be shown ONLY for
the viewer's own hand (the "what will it cost me" cards) — never for in-play
cards, never leaking the opponent's hand.
"""
from __future__ import annotations

import uuid

from tests.test_sor_cards import _get_card, _make_state
from swu.engine.state import CardInstance, Zone
from swu.engine.views import build_view


def _hand(state, repo, sc, num, owner="P0"):
    ci = CardInstance(f"{owner}_h_{num}_{uuid.uuid4().hex[:4]}",
                      _get_card(repo, sc, num), owner, Zone.HAND)
    state.player_by_id(owner).hand.append(ci)
    return ci


def _leia_base_zone(state, repo, owner="P0"):
    """Leia Organa (Command/Heroism) + Daimyo's Palace (Vigilance)."""
    ps = state.player_by_id(owner)
    ps.base_zone = [
        CardInstance(f"{owner}_leia", _get_card(repo, "LAW", "10"), owner, Zone.BASE_ZONE),
        CardInstance(f"{owner}_dp", _get_card(repo, "LAW", "20"), owner, Zone.BASE_ZONE),
    ]


class TestAspectPenaltyView:
    def test_off_aspect_hand_card_shows_surcharge(self, repo):
        """Jyn Erso (Command/Cunning/Heroism) in a Command/Heroism deck has one
        unmatched Cunning pip → +2 surcharge (effective cost 2 + 2 = 4)."""
        state = _make_state()
        _leia_base_zone(state, repo)
        jyn = _hand(state, repo, "LAW", "67")

        view = build_view(state, "P0")
        cards = {c.instance_id: c for c in view.my.hand}
        assert cards[jyn.instance_id].cost == 2          # printed cost unchanged
        assert cards[jyn.instance_id].aspect_penalty == 2  # the +2 pill value

    def test_on_aspect_hand_card_has_no_surcharge(self, repo):
        """Han Solo LAW_37 (Command/Heroism) is fully on-aspect → no penalty, so
        no pill is shown."""
        state = _make_state()
        _leia_base_zone(state, repo)
        han = _hand(state, repo, "LAW", "37")

        view = build_view(state, "P0")
        cards = {c.instance_id: c for c in view.my.hand}
        assert cards[han.instance_id].aspect_penalty == 0

    def test_penalty_not_leaked_through_opponent_view(self, repo):
        """The opponent never sees P0's hand (and so never its penalties)."""
        state = _make_state()
        _leia_base_zone(state, repo)
        _hand(state, repo, "LAW", "67")

        opp_view = build_view(state, "P1")
        assert opp_view.opponent.hand == []   # P0's hand is redacted entirely

    def test_in_play_unit_carries_no_surcharge(self, repo):
        """The surcharge is a hand-only affordability hint; an in-play (already
        paid-for) off-aspect unit reports penalty 0."""
        from tests.test_sor_cards import _place
        state = _make_state()
        _leia_base_zone(state, repo)
        jyn = _place(state, "P0", _get_card(repo, "LAW", "67"), "ground")

        view = build_view(state, "P0")
        ground = {c.instance_id: c for c in view.my.ground_arena}
        assert ground[jyn.instance_id].aspect_penalty == 0


def _resource(state, repo, sc, num, owner="P0"):
    ci = CardInstance(f"{owner}_r_{num}_{uuid.uuid4().hex[:4]}",
                      _get_card(repo, sc, num), owner, Zone.RESOURCES)
    state.player_by_id(owner).resources.append(ci)
    return ci


class TestSmuggleCostView:
    """`CardView.smuggle_base` / `smuggle_penalty` surface the per-resource Smuggle
    cost (bracket cost + aspect penalty) for the viewer's OWN resources only."""

    def test_on_aspect_smuggle_resource(self, repo):
        """Privateer Crew SHD_113 — Smuggle [6, Command] in a Command/Heroism deck
        → base 6, no penalty."""
        state = _make_state()
        _leia_base_zone(state, repo)
        pc = _resource(state, repo, "SHD", "113")

        view = build_view(state, "P0")
        cards = {c.instance_id: c for c in view.my.resources}
        assert cards[pc.instance_id].smuggle_base == 6
        assert cards[pc.instance_id].smuggle_penalty == 0

    def test_off_aspect_smuggle_resource(self, repo):
        """Hotshot DL-44 SHD_174 — Smuggle [3, Cunning] in a Command/Heroism deck
        → base 3 + 2 Cunning penalty (total 5)."""
        state = _make_state()
        _leia_base_zone(state, repo)
        hot = _resource(state, repo, "SHD", "174")

        view = build_view(state, "P0")
        cards = {c.instance_id: c for c in view.my.resources}
        assert cards[hot.instance_id].smuggle_base == 3
        assert cards[hot.instance_id].smuggle_penalty == 2

    def test_non_smuggle_resource_has_no_smuggle_fields(self, repo):
        state = _make_state()
        _leia_base_zone(state, repo)
        han = _resource(state, repo, "LAW", "37")   # no Smuggle

        view = build_view(state, "P0")
        cards = {c.instance_id: c for c in view.my.resources}
        assert cards[han.instance_id].smuggle_base is None
        assert cards[han.instance_id].smuggle_penalty == 0

    def test_smuggle_cost_not_leaked_through_opponent_view(self, repo):
        """The opponent's view of my resources is hidden stubs — no smuggle cost."""
        state = _make_state()
        _leia_base_zone(state, repo)
        _resource(state, repo, "SHD", "174")

        opp_view = build_view(state, "P1")
        for c in opp_view.opponent.resources:
            assert c.smuggle_base is None
            assert c.smuggle_penalty == 0
