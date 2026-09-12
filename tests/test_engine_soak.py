"""
Soak test: seeded games, two random bots.

100 games use vanilla decks (no keyword cards) to validate the base engine.
100 games use keyword-rich decks so that Tier 1/2 keywords (Grit, Raid,
Sentinel, Overwhelm, Restore, Saboteur, Shielded, Ambush, Exploit) are
exercised throughout.
200 games use real Luke vs Vader starter decks (full ability coverage).

Invariant checking is delegated to ``swu.engine.invariants``.
"""
from __future__ import annotations

import pytest

from tests.dbpath import db_path

pytestmark = pytest.mark.slow


_DB = db_path()

PHASE2_KEYWORDS = frozenset({
    "Sentinel", "Overwhelm", "Raid", "Ambush",
    "Restore", "Saboteur", "Shielded", "Grit", "Exploit",
})


def _play_game(deck_a, deck_b, seed: int, action_cap: int = 3000):
    from swu.engine.actions import create_game, legal_actions, apply
    from swu.engine.invariants import CheckContext, check
    from swu.players.random_bot import RandomBot

    state = create_game("P0", deck_a, "P1", deck_b, seed=seed)
    ctx = CheckContext.from_state(state)
    bot0 = RandomBot("P0", seed=seed)
    bot1 = RandomBot("P1", seed=seed + 1)
    bots = {"P0": bot0, "P1": bot1}

    actions_taken = 0

    while not state.is_terminal() and actions_taken < action_cap:
        acts = legal_actions(state)
        active_id = state.active_player.player_id
        view = state.view_for(active_id)
        chosen = bots[active_id].choose_action(view, acts)
        state = apply(state, chosen)
        actions_taken += 1
        check(state, ctx)

    return state, actions_taken


def _build_keyword_deck(repo, leader_name: str, base_name: str) -> list:
    """
    Build a 50-card deck that intentionally includes Phase 2 keyword units.
    Falls back to vanilla if not enough keyword cards are available.
    """
    from swu.cards.models import Leader, Base, Unit
    from swu.cards.decklist import DecklistError

    leaders = repo.by_name(leader_name)
    leader = next((c for c in leaders if isinstance(c, Leader)), None)
    if leader is None:
        raise DecklistError(f"No Leader card named {leader_name!r}")

    bases = repo.by_name(base_name)
    base = next((c for c in bases if isinstance(c, Base)), None)
    if base is None:
        raise DecklistError(f"No Base card named {base_name!r}")

    available_aspects = {a.name for a in leader.aspects} | {a.name for a in base.aspects}

    # Prefer keyword units; fall back to any aspect-compatible unit
    keyword_units: list = []
    other_units: list = []
    for card in repo.all_of_type("Unit"):
        if not isinstance(card, Unit):
            continue
        card_aspects = {a.name for a in card.aspects}
        if card_aspects and not (card_aspects & available_aspects):
            continue  # aspect mismatch
        kws = set(getattr(card, "keywords", ()))
        if kws & PHASE2_KEYWORDS:
            keyword_units.append(card)
        else:
            other_units.append(card)

    # Deduplicate by name
    seen: set[str] = set()
    pool: list = []
    for c in keyword_units + other_units:
        if c.name not in seen:
            seen.add(c.name)
            pool.append(c)

    deck_cards: list = []
    for c in pool:
        limit = 1 if c.is_unique else 3
        for _ in range(limit):
            if len(deck_cards) >= 50:
                break
            deck_cards.append(c)
        if len(deck_cards) >= 50:
            break

    if len(deck_cards) < 50:
        for c in repo.all_of_type("Unit"):
            if c.name not in seen:
                seen.add(c.name)
                deck_cards.append(c)
            if len(deck_cards) >= 50:
                break

    return [leader, base] + deck_cards[:50]


@pytest.fixture(scope="module")
def vanilla_decks():
    if not _DB.exists():
        pytest.skip("swu.db not found")
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import build_vanilla_deck
    repo = CardRepository(_DB)
    da = build_vanilla_deck(repo, "Darth Vader", "Security Complex")
    db = build_vanilla_deck(repo, "Luke Skywalker", "Administrator's Tower")
    return da, db


@pytest.fixture(scope="module")
def keyword_decks():
    if not _DB.exists():
        pytest.skip("swu.db not found")
    from swu.cards.repository import CardRepository
    repo = CardRepository(_DB)
    da = _build_keyword_deck(repo, "Darth Vader", "Security Complex")
    db = _build_keyword_deck(repo, "Luke Skywalker", "Administrator's Tower")
    return da, db


@pytest.fixture(scope="module")
def starter_decks():
    """Real Luke vs Vader starter decks from tests/fixtures/."""
    if not _DB.exists():
        pytest.skip("swu.db not found")
    from swu.cards.repository import CardRepository
    from swu.cards.decklist import load_decklist
    from pathlib import Path
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    repo = CardRepository(_DB)
    da = load_decklist(fixture_dir / "starter_vader.json", repo)
    db = load_decklist(fixture_dir / "starter_luke.json", repo)
    return da, db


def test_soak_200_starter_games(starter_decks):
    """200 games with the real Luke vs Vader starter decks — full ability coverage."""
    deck_a, deck_b = starter_decks
    action_cap = 5000
    for seed in range(200):
        state, n_actions = _play_game(deck_a, deck_b, seed, action_cap)
        if not state.is_terminal():
            pytest.fail(
                f"Starter deck game {seed} did not terminate within {action_cap} actions"
            )


def test_soak_100_vanilla_games(vanilla_decks):
    """100 games with vanilla decks — baseline correctness."""
    deck_a, deck_b = vanilla_decks
    action_cap = 3000
    for seed in range(100):
        state, n_actions = _play_game(deck_a, deck_b, seed, action_cap)
        if not state.is_terminal():
            pytest.fail(f"Vanilla game {seed} did not terminate within {action_cap} actions")


def test_soak_100_keyword_games(keyword_decks):
    """100 games with keyword-rich decks — exercises Tier 1/2 keyword paths."""
    deck_a, deck_b = keyword_decks
    action_cap = 3000
    for seed in range(100):
        state, n_actions = _play_game(deck_a, deck_b, seed, action_cap)
        if not state.is_terminal():
            pytest.fail(f"Keyword game {seed} did not terminate within {action_cap} actions")
