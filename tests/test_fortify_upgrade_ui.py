"""Two Fortify upgrades the web game couldn't use (player reports, 2026-11-27).

* Intelligence Agency HMW_205 — "Attached base gains: 'You may look at the top
  card of your deck at any time.'"  The view never showed the top card.
* Bacta Tank HMW_37 — its "Action [defeat this upgrade]" was legal, but it is
  addressed to the upgrade, which the board draws only as a chip on the base; the
  client now offers it on the host (web/tests/interaction.test.ts), and the button
  names the card.
"""
from __future__ import annotations

from swu.cards.repository import CardRepository
from tests.dbpath import require_db
from tests.test_hmw_cards import _attach_to_base, _deck, _discard, _unit_def
from tests.test_sor_cards import _get_card, _make_state


def _repo():
    return CardRepository(require_db())


class _NoopBot:
    def choose_action(self, view, legal):  # pragma: no cover - never asked
        return legal[0]


def _views(state):
    from swu.engine.views import build_view
    return build_view(state, "P0"), build_view(state, "P1")


def test_HMW_205_shows_the_top_card_to_its_controller_only():
    from swu.web.serializers import view_to_model
    state = _make_state()
    _deck(state, "P0", 3)
    _deck(state, "P1", 3)
    top = state.player_by_id("P0").deck[0]
    mine, theirs = _views(state)
    assert mine.my.deck_top is None                     # nothing grants it yet

    _attach_to_base(state, "P0", _get_card(_repo(), "HMW", "205"))
    mine, theirs = _views(state)
    assert mine.my.deck_top is not None
    assert mine.my.deck_top.instance_id == top.instance_id
    assert mine.opponent.deck_top is None               # never the other deck
    assert theirs.opponent.deck_top is None             # the opponent never sees it
    assert theirs.my.deck_top is None
    # It survives the trip to the browser (a field the API drops is invisible).
    assert view_to_model(mine).my.deck_top.instance_id == top.instance_id
    assert view_to_model(theirs).opponent.deck_top is None


def test_HMW_205_top_card_follows_the_deck():
    state = _make_state()
    _deck(state, "P0", 2)
    _attach_to_base(state, "P0", _get_card(_repo(), "HMW", "205"))
    ps = state.player_by_id("P0")
    ps.deck.pop(0)
    mine, _ = _views(state)
    assert mine.my.deck_top.instance_id == ps.deck[0].instance_id
    ps.deck.clear()
    mine, _ = _views(state)
    assert mine.my.deck_top is None


def test_HMW_37_action_is_offered_and_labelled_by_card_name():
    from swu.engine.actions import UseAbility, legal_actions
    from swu.web.session import GameSession
    repo = _repo()
    state = _make_state()
    _deck(state, "P0", 3)
    _attach_to_base(state, "P0", _get_card(repo, "P26", "267"))   # Verdant Fortress
    tank = _attach_to_base(state, "P0", _get_card(repo, "HMW", "37"))
    _discard(state, "P0", _unit_def(name="Fallen"))
    state.active_player_index = 0
    use = [a for a in legal_actions(state)
           if isinstance(a, UseAbility) and a.source_id == tank.instance_id]
    assert len(use) == 1
    # The client finds the host through the base's attached upgrades in the view.
    from swu.engine.views import build_view
    base_view = next(c for c in build_view(state, "P0").my.base_zone
                     if any(u.instance_id == tank.instance_id for u in c.attached_upgrades))
    assert base_view.card_type == "Base"
    sess = GameSession(game_id="t", state=state, bot=_NoopBot(),
                       human_id="P0", bot_id="P1")
    assert sess.label_for(use[0]) == f"Use {tank.card_def.display_name}"
