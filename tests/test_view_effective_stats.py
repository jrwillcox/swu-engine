"""In-play cards report their EFFECTIVE stats and keywords in the redacted view.

``CardInstance.effective_power`` / ``effective_hp`` only fold in attached
upgrades, and ``card_def.keywords`` is the printed bar — so an anthem, a duration
modifier, Grit, or a granted Sentinel used to be invisible to everything reading
a ``PlayerView``: the web UI's stat line, the heuristic bot's trade maths and the
LLM prompt alike.  Measured over real games before the fix, 4.5% of arena cards
showed the wrong power, 2.2% the wrong HP and 6.6% were missing a keyword they
actually had.

``views._effective_stats_and_keywords`` closes that for cards in an arena.  It
narrows which keywords it asks about (``views._grantable_keywords``) purely for
speed, so the load-bearing test here is the AGREEMENT one: over a real game, the
keyword list in the view must equal the engine's own per-keyword ``has_keyword``
answer, card for card.
"""
from __future__ import annotations

import uuid


from tests.test_sor_cards import _get_card, _make_state
from swu.engine.actions import compute_hp, compute_power, legal_actions, apply
from swu.engine.keywords import Keyword, has_keyword
from swu.engine.state import CardInstance, Zone
from swu.engine.views import build_view


def _arena(state, repo, sc, num, owner="P0", zone=Zone.GROUND_ARENA):
    ci = CardInstance(f"{owner}_a_{num}_{uuid.uuid4().hex[:4]}",
                      _get_card(repo, sc, num), owner, zone)
    ps = state.player_by_id(owner)
    (ps.ground_arena if zone is Zone.GROUND_ARENA else ps.space_arena).append(ci)
    return ci


def _find(view, iid):
    for zone in (view.my, view.opponent):
        for cv in zone.ground_arena + zone.space_arena:
            if cv.instance_id == iid:
                return cv
    return None


def test_modifier_buff_shows_in_view(repo):
    """A stats modifier (the +N/+N a card effect applies) reaches the view."""
    state = _make_state(repo)
    unit = _arena(state, repo, "SOR", "247")  # Underworld Thug, a vanilla 2/3
    printed_power = unit.card_def.power
    printed_hp = unit.card_def.hp

    before = _find(build_view(state, "P0"), unit.instance_id)
    assert (before.effective_power, before.effective_hp) == (printed_power, printed_hp)

    state.modifiers.append(_stats_modifier(state, unit, power=3, hp=2))

    after = _find(build_view(state, "P0"), unit.instance_id)
    assert after.effective_power == compute_power(state, unit) == printed_power + 3
    assert after.effective_hp == compute_hp(state, unit) == printed_hp + 2


def test_granted_keyword_shows_in_view(repo):
    """A keyword granted by a modifier is listed, though it is not printed."""
    state = _make_state(repo)
    unit = _arena(state, repo, "SOR", "247")  # no printed keywords
    assert "Sentinel" not in (unit.card_def.keywords or ())

    state.modifiers.append(_keyword_modifier(state, unit, "Sentinel"))

    cv = _find(build_view(state, "P0"), unit.instance_id)
    assert has_keyword(state, unit, Keyword.SENTINEL)
    assert "Sentinel" in cv.keywords


def test_revoked_keyword_drops_out_of_view(repo):
    """…and a revoked keyword stops being listed, though it IS printed."""
    state = _make_state(repo)
    # Wampa SOR_223-adjacent vanilla with a printed keyword: use any card the
    # repository reports as carrying Sentinel.
    unit = _arena(state, repo, "SOR", "247")
    state.modifiers.append(_keyword_modifier(state, unit, "Sentinel"))
    assert "Sentinel" in _find(build_view(state, "P0"), unit.instance_id).keywords

    state.modifiers.append(
        _keyword_modifier(state, unit, "Sentinel", kind="keyword_revoke"))
    assert "Sentinel" not in _find(build_view(state, "P0"), unit.instance_id).keywords


def _stats_modifier(state, ci, *, power, hp):
    from swu.engine.state import Modifier
    return Modifier(
        modifier_id=state.alloc_modifier_id("test"),
        source_instance_id=ci.instance_id,
        target_instance_id=ci.instance_id,
        kind="stats",
        value={"power": power, "hp": hp},
        duration="this_phase",
    )


def _keyword_modifier(state, ci, keyword, *, kind="keyword_grant"):
    from swu.engine.state import Modifier
    return Modifier(
        modifier_id=state.alloc_modifier_id("test"),
        source_instance_id=ci.instance_id,
        target_instance_id=ci.instance_id,
        kind=kind,
        value={"keyword": keyword},
        duration="this_phase",
    )


def test_view_keywords_match_engine_over_a_real_game(repo):
    """The load-bearing check on the ``_grantable_keywords`` narrowing.

    Plays a real, fully-encoded matchup and asserts that for every arena card in
    every view, the keyword list equals the engine's own answer for all 16
    keywords — so the narrowing can never hide one — and that power/HP match
    ``compute_power`` / ``compute_hp`` exactly.
    """
    from pathlib import Path
    from swu.cards.decklist import load_decklist
    from swu.engine.actions import create_game
    from swu.players.heuristic_bot import HeuristicBot

    fx = Path(__file__).resolve().parent / "fixtures"
    d0 = load_decklist(fx / "general_grievous.json", repo)
    d1 = load_decklist(fx / "leia_organa.json", repo)
    state = create_game("P0", d0, "P1", d1, seed=4242)
    bots = {"P0": HeuristicBot("P0", seed=1), "P1": HeuristicBot("P1", seed=2)}

    checked = 0
    n = 0
    while not state.is_terminal() and n < 1500:
        pid = (state.pending_decisions[-1].deciding_player_id
               if state.pending_decisions else state.active_player.player_id)
        view = state.view_for(pid)
        for zone, ps in ((view.my, state.player_by_id(pid)),
                         (view.opponent,
                          state.players[1 - state.player_index(pid)])):
            by_id = {ci.instance_id: ci for ci in ps.ground_arena + ps.space_arena}
            for cv in zone.ground_arena + zone.space_arena:
                ci = by_id.get(cv.instance_id)
                if ci is None:
                    continue
                checked += 1
                truth = {kw.value for kw in Keyword if has_keyword(state, ci, kw)}
                assert set(cv.keywords or ()) == truth, (
                    f"{cv.card_name}: view {sorted(cv.keywords or ())} "
                    f"!= engine {sorted(truth)}")
                assert cv.effective_power == compute_power(state, ci)
                assert cv.effective_hp == compute_hp(state, ci)
        state = apply(state, bots[pid].choose_action(view, legal_actions(state)))
        n += 1

    assert checked > 100, "expected plenty of in-play cards to check"
