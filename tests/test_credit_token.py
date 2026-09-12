"""Credit-token economy — synthetic framework tests (jabba-the-hutt:07).

Exercises the create-token-unit primitive independently of any specific card:
credit creation, need-based credit-spend during a card play (PlayCard), the
affordability gate counting credits, serialisation round-trip, and the invariant
checker tolerating the new CREDITS zone.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _make_state, _give_resources,
)


def _credits(state, pid="P0"):
    return len(state.player_by_id(pid).credits)


def _unit_def(cost=1, name="Synth Unit"):
    from swu.cards.models import Unit
    return Unit(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="SY", name=name, subtitle=None, type="Unit", rarity="Common",
        is_unique=False, artist=None, text=None, text_styled=None, rules=None,
        rules_styled=None, aspects=(), keywords=(), traits=(), arenas=("Ground",),
        image_front_url=None, image_back_url=None, image_front_path=None,
        image_back_path=None, cost=cost, power=1, hp=1,
    )


def _add_credit(state, pid, n=1):
    from swu.engine.tokens import create_credit_token
    for _ in range(n):
        create_credit_token(state, state.player_by_id(pid))


def _hand_unit(state, pid, cost=1):
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(f"{pid}_synth_{cost}", _unit_def(cost), pid, Zone.HAND)
    state.player_by_id(pid).hand.append(ci)
    return ci


class TestCreditCreation:
    def test_create_credit_token_adds_to_credit_pile(self, repo):
        from swu.engine.state import Zone
        state = _make_state()
        _add_credit(state, "P0", 2)
        ps = state.player_by_id("P0")
        assert _credits(state, "P0") == 2
        assert all(c.zone == Zone.CREDITS for c in ps.credits)
        # Credits are NOT normal resources.
        assert ps.available_resources == 0
        assert ps.total_resources == 0

    def test_credits_excluded_from_card_conservation(self, repo):
        """A credit is an unlimited-supply token: it must not count toward the
        owner's conserved card set."""
        state = _make_state()
        before = len(state.all_instances_for_player("P0"))
        _add_credit(state, "P0", 3)
        after = len(state.all_instances_for_player("P0"))
        assert before == after


class TestCreditSpend:
    def test_credit_covers_a_shortfall_when_playing_a_card(self, repo):
        from swu.engine.actions import legal_actions, apply, PlayCard
        from swu.engine.state import Zone
        state = _make_state()
        unit = _hand_unit(state, "P0", cost=1)
        _add_credit(state, "P0", 1)   # 0 ready resources + 1 credit affords cost 1
        # The play is offered (affordability counts credits).
        acts = legal_actions(state)
        assert any(isinstance(a, PlayCard) and a.instance_id == unit.instance_id
                   for a in acts)
        state = apply(state, PlayCard(unit.instance_id))
        played = next(c for c in state.player_by_id("P0").ground_arena
                      if c.instance_id == unit.instance_id)
        assert played.zone == Zone.GROUND_ARENA
        assert _credits(state, "P0") == 0, "credit defeated to cover the shortfall"

    def test_credit_not_spent_when_resources_suffice(self, repo):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        unit = _hand_unit(state, "P0", cost=1)
        _give_resources(state, "P0", 1)   # 1 ready resource covers it
        _add_credit(state, "P0", 1)        # credit present but not needed
        state = apply(state, PlayCard(unit.instance_id))
        assert _credits(state, "P0") == 1, "need-based: credit untouched"
        assert state.player_by_id("P0").available_resources == 0, "resource spent instead"

    def test_partial_shortfall_spends_only_the_needed_credits(self, repo):
        from swu.engine.actions import apply, PlayCard
        state = _make_state()
        unit = _hand_unit(state, "P0", cost=3)
        _give_resources(state, "P0", 2)   # 2 ready resources
        _add_credit(state, "P0", 3)        # only 1 of 3 credits is needed
        state = apply(state, PlayCard(unit.instance_id))
        assert state.player_by_id("P0").available_resources == 0
        assert _credits(state, "P0") == 2, "only 1 credit defeated for the shortfall"

    def test_unaffordable_even_with_credits_is_not_offered(self, repo):
        from swu.engine.actions import legal_actions, PlayCard
        state = _make_state()
        unit = _hand_unit(state, "P0", cost=4)
        _give_resources(state, "P0", 1)
        _add_credit(state, "P0", 1)        # 1 + 1 < 4
        acts = legal_actions(state)
        assert not any(isinstance(a, PlayCard) and a.instance_id == unit.instance_id
                       for a in acts)


class TestCreditSerialisationAndInvariants:
    def test_state_round_trips_with_credits(self, repo):
        state = _make_state()
        _add_credit(state, "P0", 2)
        data = state.to_json()
        restored = type(state).from_json(data)
        assert _credits(restored, "P0") == 2

    def test_invariants_hold_with_credits(self, repo):
        from swu.engine.invariants import CheckContext, check
        state = _make_state()
        ctx = CheckContext.from_state(state)
        _add_credit(state, "P0", 2)
        # Creating credits must not break card conservation or zone-tag checks.
        check(state, ctx)
