"""
Smuggle keyword — synthetic-card framework tests (shd-han-solo:01).

Smuggle lets a card sitting in your resource zone be played for its bracketed
smuggle cost, then replaced with the top card of your deck.  These tests build
minimal synthetic cards and exercise the keyword purely through the public
``legal_actions`` / ``apply`` interface, independent of any specific real card.
"""
from __future__ import annotations

import uuid


from tests.test_sor_cards import repo, _get_card, _make_state  # noqa: F401

from swu.cards.models import AspectPip, Unit
from swu.engine.state import CardInstance, Zone
from swu.engine.actions import legal_actions, apply, SmugglePlay


def _aspect(name, pos=0):
    return AspectPip(position=pos, name=name, color="x", is_duplicate=False)


def _synthetic_unit(name="Smuggled Trooper", cost=2, smuggle_text="Smuggle [2 resources]",
                    aspects=(), power=3, hp=3):
    return Unit(
        id=abs(hash(name)) % 99999, card_uid=None, set_code="TST", set_name="T",
        card_number="1", name=name, subtitle=None, type="Unit", rarity="Common",
        is_unique=False, artist=None, text=smuggle_text, text_styled=None,
        rules=None, rules_styled=None,
        aspects=tuple(_aspect(a, i) for i, a in enumerate(aspects)),
        keywords=("Smuggle",), traits=("Smuggler",), arenas=("Ground",),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=cost, power=power, hp=hp,
    )


def _add_resource(state, owner_id, card_def, *, exhausted=False, face_down=True):
    ps = state.player_by_id(owner_id)
    ci = CardInstance(
        instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.RESOURCES,
        face_down=face_down, exhausted=exhausted,
    )
    ps.resources.append(ci)
    return ci


def _fill_resources(state, owner_id, n, repo):
    filler = _get_card(repo, "SOR", "46")  # Consular Security Force (vanilla)
    return [_add_resource(state, owner_id, filler) for _ in range(n)]


def _add_deck_card(state, owner_id, repo, n=1):
    filler = _get_card(repo, "SOR", "46")
    ps = state.player_by_id(owner_id)
    out = []
    for _ in range(n):
        ci = CardInstance(
            instance_id=f"{owner_id}_deck_{uuid.uuid4().hex[:6]}",
            card_def=filler, owner_id=owner_id, zone=Zone.DECK,
        )
        ps.deck.append(ci)
        out.append(ci)
    return out


class TestSmuggleKeyword:
    def test_smuggle_play_offered_when_affordable(self, repo):
        state = _make_state()
        unit = _synthetic_unit(cost=2, smuggle_text="Smuggle [2 resources]")
        smug = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        _add_deck_card(state, "P0", repo)

        acts = legal_actions(state)
        smuggle_acts = [a for a in acts if isinstance(a, SmugglePlay)
                        and a.instance_id == smug.instance_id]
        assert len(smuggle_acts) == 1

    def test_smuggle_not_offered_without_enough_other_resources(self, repo):
        # Smuggle cost 3, but only the smuggled card itself + 2 others are ready.
        state = _make_state()
        unit = _synthetic_unit(cost=3, smuggle_text="Smuggle [3 resources]")
        smug = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 2, repo)  # only 2 OTHER ready resources
        _add_deck_card(state, "P0", repo)

        smuggle_acts = [a for a in legal_actions(state) if isinstance(a, SmugglePlay)]
        assert smuggle_acts == []

    def test_smuggle_plays_unit_and_replaces_from_deck(self, repo):
        state = _make_state()
        unit = _synthetic_unit(cost=2, smuggle_text="Smuggle [2 resources]")
        smug = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        deck = _add_deck_card(state, "P0", repo)
        repl_id = deck[0].instance_id

        ps0 = state.player_by_id("P0")
        res_before = len(ps0.resources)
        deck_before = len(ps0.deck)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)

        ps0 = state.player_by_id("P0")
        # The smuggled unit is now in play, not a resource.
        assert any(u.instance_id == smug.instance_id for u in ps0.ground_arena)
        assert not any(r.instance_id == smug.instance_id for r in ps0.resources)
        # Resource count preserved by the replacement from the deck.
        assert len(ps0.resources) == res_before
        assert len(ps0.deck) == deck_before - 1
        assert any(r.instance_id == repl_id and r.face_down for r in ps0.resources)
        # 2 resources were exhausted to pay the cost.
        assert sum(1 for r in ps0.resources if r.exhausted) == 2

    def test_aspect_penalty_raises_smuggle_cost(self, repo):
        # Smuggle [2 resources Aggression] with no Aggression base => +2 penalty
        # => effective cost 4.  3 other ready resources is not enough.
        state = _make_state()
        unit = _synthetic_unit(cost=2, smuggle_text="Smuggle [2 resources Aggression]",
                               aspects=("Aggression",))
        _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        _add_deck_card(state, "P0", repo)
        assert [a for a in legal_actions(state) if isinstance(a, SmugglePlay)] == []

        # Give a 4th other ready resource → now affordable at cost 4.
        _fill_resources(state, "P0", 1, repo)
        assert [a for a in legal_actions(state) if isinstance(a, SmugglePlay)]

    def test_smuggle_replacement_skipped_on_empty_deck(self, repo):
        state = _make_state()
        unit = _synthetic_unit(cost=1, smuggle_text="Smuggle [1 resources]")
        smug = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 2, repo)
        # No deck cards.
        ps0 = state.player_by_id("P0")
        res_before = len(ps0.resources)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)
        ps0 = state.player_by_id("P0")
        # No deck → no replacement → resource count drops by one.
        assert len(ps0.resources) == res_before - 1
        assert any(u.instance_id == smug.instance_id for u in ps0.ground_arena)

    def test_non_smuggle_resource_not_offered(self, repo):
        state = _make_state()
        # A vanilla resource with no Smuggle keyword.
        _fill_resources(state, "P0", 4, repo)
        _add_deck_card(state, "P0", repo)
        assert [a for a in legal_actions(state) if isinstance(a, SmugglePlay)] == []

    def test_card_conservation_through_smuggle(self, repo):
        from swu.engine.invariants import CheckContext, check
        state = _make_state()
        unit = _synthetic_unit(cost=2, smuggle_text="Smuggle [2 resources]")
        smug = _add_resource(state, "P0", unit)
        _fill_resources(state, "P0", 3, repo)
        _add_deck_card(state, "P0", repo)
        ctx = CheckContext.from_state(state)

        act = next(a for a in legal_actions(state)
                   if isinstance(a, SmugglePlay) and a.instance_id == smug.instance_id)
        state = apply(state, act)
        check(state, ctx)  # raises on any invariant violation
