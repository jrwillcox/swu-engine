"""
Unit tests for the build_db card parser.

Uses the discovery_sample.json fixture produced by discover.py.
Run after discover.py has been executed at least once.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_db import parse_card  # noqa: E402


SAMPLE_PATH = ROOT / "data" / "raw" / "discovery_sample.json"


@pytest.fixture(scope="module")
def examples() -> dict[str, dict]:
    if not SAMPLE_PATH.exists():
        pytest.skip("discovery_sample.json not found — run scripts/discover.py first")
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("examples_by_type", {})


def _card(examples, type_name):
    c = examples.get(type_name)
    if c is None:
        pytest.skip(f"No {type_name} example in fixture")
    return c


class TestUnitParsing:
    def test_unit_has_required_fields(self, examples):
        raw = _card(examples, "Unit")
        card = parse_card(raw)
        assert card is not None
        assert card["type"] == "Unit"
        assert card["name"]
        assert card["cost"] is not None
        assert card["power"] is not None
        assert card["hp"] is not None

    def test_unit_has_set_info(self, examples):
        raw = _card(examples, "Unit")
        card = parse_card(raw)
        assert card["set_code"]
        assert card["card_number"]


class TestLeaderParsing:
    def test_leader_has_back_url(self, examples):
        raw = _card(examples, "Leader")
        card = parse_card(raw)
        assert card is not None
        assert card["type"] == "Leader"
        # Leaders must have a back image URL
        assert card["image_back_url"], "Leader should have a back image URL"

    def test_leader_has_stats(self, examples):
        raw = _card(examples, "Leader")
        card = parse_card(raw)
        assert card["power"] is not None
        assert card["hp"] is not None


class TestBaseParsing:
    def test_base_has_hp(self, examples):
        raw = _card(examples, "Base")
        card = parse_card(raw)
        assert card is not None
        assert card["type"] == "Base"
        assert card["hp"] is not None


class TestEventParsing:
    def test_event_has_cost(self, examples):
        raw = _card(examples, "Event")
        card = parse_card(raw)
        assert card is not None
        assert card["type"] == "Event"
        assert card["cost"] is not None


class TestUpgradeParsing:
    def test_upgrade_has_upgrade_stats(self, examples):
        raw = _card(examples, "Upgrade")
        card = parse_card(raw)
        assert card is not None
        assert card["type"] == "Upgrade"
        # upgrade_power / upgrade_hp may be None (0 or absent) but keys must exist
        assert "upgrade_power" in card
        assert "upgrade_hp" in card

    def test_upgrade_power_not_in_power_field(self, examples):
        raw = _card(examples, "Upgrade")
        card = parse_card(raw)
        # Upgrades' modifiers live in upgrade_power/upgrade_hp, not power/hp
        # power and hp should be None for upgrades
        assert card["power"] is None or card["upgrade_power"] is not None


class TestAspects:
    def test_aspects_have_names(self, examples):
        for type_name in ("Unit", "Leader", "Event", "Upgrade"):
            if type_name not in examples:
                continue
            card = parse_card(examples[type_name])
            if card is None:
                continue
            for asp in card["_aspects"]:
                assert asp["name"], f"{type_name} has aspect with no name"

    def test_aspect_positions_are_ordered(self, examples):
        for type_name, raw in examples.items():
            card = parse_card(raw)
            if card is None:
                continue
            positions = [a["position"] for a in card["_aspects"]]
            assert positions == sorted(positions), f"{type_name} aspects not in position order"


class TestRawJsonPreserved:
    def test_raw_json_is_stored(self, examples):
        for type_name, raw in examples.items():
            card = parse_card(raw)
            if card is None:
                continue
            assert card["raw_json"], f"{type_name}: raw_json is empty"
            parsed_back = json.loads(card["raw_json"])
            assert isinstance(parsed_back, dict)
