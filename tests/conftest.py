"""Shared fixtures for the engine test suite."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make the package importable without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tests.dbpath import db_path  # noqa: E402 — after the sys.path insert above

_DB = db_path()


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run opt-in live tests that hit the real Anthropic API (costs money)",
    )


def pytest_configure(config):
    # Default pytest's tmp_path/tmpdir basetemp to a dir under the OS temp,
    # NOT an in-repo .pytest_tmp.  Two Windows WinError-5 failure modes this
    # avoids (both routinely broke the fast suite + the --graduate gate):
    #   * The repo lives under Documents, which Windows Search / Defender scan;
    #     they leave transient handles that make pytest's session-start rm_rf of
    #     an in-repo temp dir fail with "Access is denied", erroring EVERY
    #     tmp_path test (web/auth/deckstore/bugs — ~118 errors).  One stale run
    #     even left .pytest_tmp with a corrupted ACL that only admin can remove.
    #   * pytest's pytest-of-<user>/pytest-current symlink + atexit cleanup only
    #     fires when basetemp is auto-generated; setting an explicit basetemp
    #     here suppresses that machinery too.
    # The OS %TEMP% is excluded from those scanners and is the OS's designated
    # scratch area, so its rm_rf is reliable.  A CLI --basetemp still wins
    # (config.option.basetemp is already truthy in that case).
    if not config.option.basetemp:
        import tempfile
        config.option.basetemp = os.path.join(tempfile.gettempdir(), "swu_pytest")

    config.addinivalue_line("markers", "slow: mark test as slow (soak)")
    config.addinivalue_line(
        "markers",
        "live: hits the real Anthropic API; skipped unless --live is passed and "
        "ANTHROPIC_API_KEY is set",
    )


def pytest_collection_modifyitems(config, items):
    # In fixture mode the card database is tests/fixtures/swu_fixture.db — a few
    # hundred cards, not the corpus.  The suites whose subject IS the corpus
    # (every deck fully implemented, the reprint sweep, the coverage audit) would
    # fail on it for reasons unrelated to the code, so their DB-backed tests skip
    # here rather than report false failures.  tests/fixture_scope.py owns the
    # list; scripts/make_fixture_db.py records against its complement.
    #
    # Only the tests that ASK for card data, though — keyed on the DB fixtures
    # they request.  Those modules also hold ~1,000 tests that read the ability
    # registry alone (test_reprints parametrised over the whole alias table) and
    # pass with no database whatsoever; skipping the modules wholesale threw all
    # of those away, which would make a fresh clone look worse, not better.
    from tests.dbpath import using_fixture
    if using_fixture():
        from tests.fixture_scope import DB_FIXTURE_NAMES, needs_full_corpus
        skip_corpus = pytest.mark.skip(
            reason="needs the full card corpus (running on the small fixture DB) — "
                   "build it per docs/pipeline.md"
        )
        for item in items:
            if (needs_full_corpus(Path(str(item.fspath)).name)
                    and DB_FIXTURE_NAMES.intersection(getattr(item, "fixturenames", ()))):
                item.add_marker(skip_corpus)

    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="needs --live (and ANTHROPIC_API_KEY) to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _offline_unless_live(request, monkeypatch):
    """Guarantee the default suite never touches the network.

    The LLM opponent (Normal/Hard) only constructs a real Anthropic client when
    ``ANTHROPIC_API_KEY`` is present; stripping it for every non-``live`` test
    means even a developer with a key set runs the whole default suite offline
    (the bot transparently uses its heuristic fallback).  ``live``-marked tests
    keep the key so the opt-in smoke test can hit the real API.
    """
    if "live" not in request.keywords:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


@pytest.fixture(scope="session")
def repo():
    if not _DB.exists():
        pytest.skip("swu.db not found")
    from swu.cards.repository import CardRepository
    return CardRepository(_DB)


@pytest.fixture(scope="session")
def fixture_dir():
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def deck_a(repo, fixture_dir):
    from swu.cards.decklist import load_decklist
    p = fixture_dir / "vanilla_deck_a.json"
    if not p.exists():
        pytest.skip("vanilla_deck_a.json not found")
    return load_decklist(p, repo)


@pytest.fixture(scope="session")
def deck_b(repo, fixture_dir):
    from swu.cards.decklist import load_decklist
    p = fixture_dir / "vanilla_deck_b.json"
    if not p.exists():
        pytest.skip("vanilla_deck_b.json not found")
    return load_decklist(p, repo)


def make_game(deck_a, deck_b, seed=42):
    from swu.engine.actions import create_game
    return create_game("P0", deck_a, "P1", deck_b, seed=seed)


def ensure_affordable(state, card_type):
    """Guarantee the active player holds an affordable card of ``card_type``.

    Several engine tests used to hunt through the opening hand for "a unit I can
    afford" and ``pytest.skip`` when the shuffle didn't provide one — a skip that
    silently turns into a pass-or-vanish depending on the seed, so the test proved
    nothing on the runs where it mattered.  This arranges the precondition
    instead: the cheapest matching card is moved from the deck into hand if the
    hand has none, and cards are moved deck -> resources until it is affordable.

    Moving cards between the player's own zones keeps the total card count
    unchanged, so the card-conservation invariant still holds.  Returns the
    CardInstance, which is now in hand and playable this turn.
    """
    from swu.engine.actions import _effective_cost
    from swu.engine.state import Zone

    ps = state.active_player

    def cost_of(ci):
        return _effective_cost(ci.card_def, ps, state)

    in_hand = [ci for ci in ps.hand if isinstance(ci.card_def, card_type)]
    if in_hand:
        target = min(in_hand, key=cost_of)
    else:
        from_deck = [ci for ci in ps.deck if isinstance(ci.card_def, card_type)]
        assert from_deck, f"vanilla deck holds no {card_type.__name__} at all"
        target = min(from_deck, key=cost_of)
        ps.deck.remove(target)
        target.zone = Zone.HAND
        ps.hand.append(target)

    fund_for(state, target)
    return target


def fund_for(state, ci):
    """Give the active player enough ready resources to play ``ci``.

    Resources come out of their own deck, so the total card count is unchanged and
    the card-conservation invariant still holds.
    """
    from swu.engine.actions import _effective_cost
    from swu.engine.state import Zone

    ps = state.active_player
    need = _effective_cost(ci.card_def, ps, state)
    while ps.available_resources < need:
        filler = next((c for c in ps.deck if c is not ci), None)
        assert filler is not None, "deck exhausted while arranging resources"
        ps.deck.remove(filler)
        filler.zone = Zone.RESOURCES
        filler.exhausted = False
        ps.resources.append(filler)


def inject_into_hand(state, card_def):
    """Put a card of ``card_def`` into the active player's hand, funded to play.

    For card types the vanilla decks simply don't contain: ``build_vanilla_deck``
    fills a deck from Units and Upgrades only, so a test needing an EVENT found
    nothing and skipped — i.e. never ran at all, on any seed.  A deck card is
    discarded from the deck as this instance is added, keeping the player's total
    card count (and so the conservation invariant) unchanged.
    """
    import uuid

    from swu.engine.state import CardInstance, Zone

    ps = state.active_player
    swapped_out = ps.deck.pop() if ps.deck else None
    assert swapped_out is not None, "empty deck: nothing to swap the injected card for"
    ci = CardInstance(
        instance_id=f"inj_{uuid.uuid4().hex[:8]}",
        card_def=card_def,
        owner_id=ps.player_id,
        zone=Zone.HAND,
    )
    ps.hand.append(ci)
    fund_for(state, ci)
    return ci


def run_through_setup(state):
    """
    Fast-forward through SETUP_MULLIGAN and SETUP_RESOURCES by
    keeping hand and choosing the first two cards as resources.
    Returns the first ACTION-phase state.
    """
    from swu.engine.actions import legal_actions, apply
    from swu.engine.state import Phase
    from swu.engine.actions import KeepHand, ResourceCard

    while state.phase != Phase.ACTION:
        acts = legal_actions(state)
        if state.phase.name == "SETUP_MULLIGAN":
            keep = next((a for a in acts if isinstance(a, KeepHand)), acts[0])
            state = apply(state, keep)
        elif state.phase.name == "SETUP_RESOURCES":
            res = next((a for a in acts if isinstance(a, ResourceCard)), acts[0])
            state = apply(state, res)
        else:
            break
    return state
