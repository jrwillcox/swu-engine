"""
Tests for CardRepository.

Requires a populated swu.db — run the full pipeline first.
Skipped automatically if swu.db is absent.
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "swu.db"


@pytest.fixture(scope="module")
def repo():
    if not DB_PATH.exists():
        pytest.skip("swu.db not found — run the full pipeline first")
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from swu.cards.repository import CardRepository
    return CardRepository(DB_PATH)


def test_db_has_cards(repo):
    cards = list(repo.iter_all())
    assert len(cards) > 100, "Expected at least 100 cards"


def test_leaders_have_back_images(repo):
    from swu.cards.models import Leader
    leaders = repo.all_of_type("Leader")
    assert len(leaders) > 0
    for leader in leaders:
        assert isinstance(leader, Leader)
        assert leader.image_back_url, f"Leader {leader.name} missing back image URL"


def test_unit_stats_present(repo):
    from swu.cards.models import Unit
    units = repo.all_of_type("Unit")
    assert len(units) > 100
    for u in units[:20]:  # spot-check first 20
        assert isinstance(u, Unit)
        assert u.cost is not None
        assert u.power is not None
        assert u.hp is not None


def test_search_returns_results(repo):
    results = repo.search("Darth")
    assert len(results) > 0


def test_by_name_case_insensitive(repo):
    results_lower = repo.by_name("luke skywalker")
    results_mixed = repo.by_name("Luke Skywalker")
    assert len(results_lower) == len(results_mixed)


def test_aspects_in_order(repo):
    for card in list(repo.iter_all())[:50]:
        positions = [a.position for a in card.aspects]
        assert positions == sorted(positions)


def test_upgrade_uses_upgrade_stats(repo):
    upgrades = repo.all_of_type("Upgrade")
    assert len(upgrades) > 0
    # At least some upgrades should have upgrade_power or upgrade_hp
    with_stats = [u for u in upgrades if u.upgrade_power is not None or u.upgrade_hp is not None]
    assert len(with_stats) > 0, "Expected some upgrades to have stat modifiers"


def test_to_text_includes_name(repo):
    for card in list(repo.iter_all())[:10]:
        text = card.to_text()
        assert card.name in text
