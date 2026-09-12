"""Piloting keyword tests — boba-fett:01.

Synthetic-card framework tests for the Piloting engine primitive, followed by
per-card acceptance tests for the 4 Piloting cards in the boba-fett deck:
  * JTL_139 Dengar (cost 4, 5/4 → pilot 1/2, Piloting [2 Aggression Villainy])
  * JTL_141 IG-88  (cost 5, 4/5 → pilot 0/3, Piloting [2 Aggression Villainy])
  * JTL_187 Bossk  (cost 4, 4/4 → pilot 2/2, Piloting [2 Cunning Villainy])
  * JTL_189 Boba Fett (cost 5, 5/4 → pilot 2/3, Piloting [2 Cunning Villainy])

Residual text ("Attached unit gains: …") is NOT tested here — it belongs in a
later ability group.  These tests assert only the Piloting play mechanic itself.

Method names embed the card number so the encoding verifier's -k gate finds them.
"""
from __future__ import annotations

import uuid

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _find_instance,
)


def _put_in_hand(state, owner_id, card_def):
    """Put card_def into owner's hand. Returns the CardInstance."""
    from swu.engine.state import CardInstance, Zone
    ci = CardInstance(
        instance_id=f"{owner_id}_hand_{uuid.uuid4().hex[:6]}",
        card_def=card_def, owner_id=owner_id, zone=Zone.HAND,
    )
    state.player_by_id(owner_id).hand.append(ci)
    return ci


def _give_resources(state, owner_id, n):
    """Give owner_id n ready resources (dummy Base cards as filler)."""
    from swu.engine.state import CardInstance, Zone
    from swu.cards.models import Base
    dummy = Base(
        id=99991, card_uid=None, set_code="TST", set_name="T", card_number="R2",
        name="Resource", subtitle=None, type="Base", rarity="Common", is_unique=False,
        artist=None, text=None, text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=(),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        hp=0, epic_action=None,
    )
    ps = state.player_by_id(owner_id)
    for _ in range(n):
        res = CardInstance(
            instance_id=f"{owner_id}_res_{uuid.uuid4().hex[:4]}",
            card_def=dummy, owner_id=owner_id, zone=Zone.RESOURCES,
        )
        res.exhausted = False
        ps.resources.append(res)


def _place_vehicle(state, owner_id, arena="space"):
    """Place a synthetic Vehicle unit in the arena. Returns the CardInstance."""
    from swu.engine.state import CardInstance, Zone

    class _FakeVehicleCard:
        id = 77700
        card_uid = None
        set_code = "TST"
        set_name = "T"
        card_number = "VH"
        name = "Test Vehicle"
        display_name = "Test Vehicle"
        subtitle = None
        type = "Unit"
        rarity = "Common"
        is_unique = False
        artist = None
        text = None
        text_styled = None
        rules = None
        rules_styled = None
        aspects = ()
        keywords = ()
        traits = ("Vehicle",)
        arenas = ("Space",)
        image_front_url = None
        image_back_url = None
        image_front_path = None
        image_back_path = None
        cost = 3
        power = 2
        hp = 5
        upgrade_power = None
        upgrade_hp = None
        epic_action = None
        deploy_box = None

    zone = Zone.GROUND_ARENA if arena == "ground" else Zone.SPACE_ARENA
    ci = CardInstance(
        instance_id=f"{owner_id}_vehicle_{uuid.uuid4().hex[:6]}",
        card_def=_FakeVehicleCard(), owner_id=owner_id, zone=zone,
    )
    ps = state.player_by_id(owner_id)
    if arena == "ground":
        ps.ground_arena.append(ci)
    else:
        ps.space_arena.append(ci)
    return ci


# ── parse_piloting_cost unit tests ────────────────────────────────────────────

class TestParsePilotingCost:
    """Unit tests for the bracketed-cost parser (no DB needed)."""

    def test_parses_aggression_villainy(self):
        from swu.engine.keywords import parse_piloting_cost
        text = "Piloting [2 resources Aggression Villainy]\nAttached unit gains: …"
        result = parse_piloting_cost(text)
        assert result is not None
        n, aspects = result
        assert n == 2
        assert "Aggression" in aspects
        assert "Villainy" in aspects

    def test_parses_cunning_villainy(self):
        from swu.engine.keywords import parse_piloting_cost
        text = "Piloting [2 resources Cunning Villainy]\nSome ability text"
        result = parse_piloting_cost(text)
        assert result is not None
        n, aspects = result
        assert n == 2
        assert "Cunning" in aspects
        assert "Villainy" in aspects

    def test_returns_none_for_no_piloting(self):
        from swu.engine.keywords import parse_piloting_cost
        assert parse_piloting_cost(None) is None
        assert parse_piloting_cost("") is None
        assert parse_piloting_cost("Smuggle [3 resources Command]") is None
        assert parse_piloting_cost("Just some text") is None


# ── PilotPlay framework tests (synthetic cards, no specific card abilities) ────

class TestPilotPlayMechanic:
    """Synthetic tests for the Piloting play mechanic engine-wide."""

    def _make_synthetic_pilot(self, state, owner_id,
                               epic_action="Piloting [2 resources Aggression Villainy]",
                               upgrade_power=1, upgrade_hp=2):
        """Put a synthetic Unit (real dataclass) with Piloting into owner's hand."""
        from swu.engine.state import CardInstance, Zone
        from swu.cards.models import Unit
        card = Unit(
            id=77701, card_uid=None, set_code="TST", set_name="T",
            card_number="PL", name="Test Pilot", subtitle=None, type="Unit",
            rarity="Common", is_unique=False, artist=None, text=None,
            text_styled=None, rules=None, rules_styled=None,
            aspects=(), keywords=("Piloting",), traits=(), arenas=("Ground",),
            image_front_url=None, image_back_url=None,
            image_front_path=None, image_back_path=None,
            cost=4, power=5, hp=4,
            upgrade_power=upgrade_power, upgrade_hp=upgrade_hp,
            epic_action=epic_action,
        )
        ci = CardInstance(
            instance_id=f"{owner_id}_pilot_{uuid.uuid4().hex[:6]}",
            card_def=card, owner_id=owner_id, zone=Zone.HAND,
        )
        state.player_by_id(owner_id).hand.append(ci)
        return ci

    def test_pilot_play_offered_when_vehicle_present(self):
        """PilotPlay appears in legal_actions when hand has a Piloting unit
        and the controller has a friendly Vehicle unit."""
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        pilot_ci = self._make_synthetic_pilot(state, "P0")
        vehicle_ci = _place_vehicle(state, "P0", "space")
        # Pilot cost = 2 base + 4 aspect penalty (no matching aspects) = 6
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        pilot_plays = [a for a in acts if isinstance(a, PilotPlay)]
        assert len(pilot_plays) == 1
        assert pilot_plays[0].instance_id == pilot_ci.instance_id
        assert pilot_plays[0].vehicle_target_id == vehicle_ci.instance_id

    def test_pilot_play_not_offered_without_vehicle(self):
        """PilotPlay is never offered when no friendly Vehicle unit is in play."""
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        self._make_synthetic_pilot(state, "P0")
        _place(state, "P0", _make_synthetic_nonvehicle(), "ground")
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        assert not any(isinstance(a, PilotPlay) for a in acts)

    def test_pilot_play_not_offered_when_unaffordable(self):
        """PilotPlay is not offered when the player can't afford the Piloting cost."""
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        # Pilot cost = 2 base + 4 aspect penalty = 6 total; give only 1
        self._make_synthetic_pilot(state, "P0")
        _place_vehicle(state, "P0", "space")
        _give_resources(state, "P0", 1)

        acts = legal_actions(state)
        assert not any(isinstance(a, PilotPlay) for a in acts)

    def test_pilot_play_only_targets_friendly_vehicles(self):
        """PilotPlay targets only the controller's own Vehicle units, not enemies'."""
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        self._make_synthetic_pilot(state, "P0")
        enemy_vehicle = _place_vehicle(state, "P1", "space")
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        pilot_plays = [a for a in acts if isinstance(a, PilotPlay)]
        assert not any(a.vehicle_target_id == enemy_vehicle.instance_id
                       for a in pilot_plays)

    def test_pilot_play_apply_attaches_to_vehicle(self):
        """Applying PilotPlay moves the unit from hand to vehicle's attached_upgrades."""
        from swu.engine.actions import apply, PilotPlay
        state = _make_state()
        pilot_ci = self._make_synthetic_pilot(state, "P0")
        vehicle_ci = _place_vehicle(state, "P0", "space")
        _give_resources(state, "P0", 8)

        action = PilotPlay(pilot_ci.instance_id, vehicle_ci.instance_id)
        s2 = apply(state, action)

        assert not any(c.instance_id == pilot_ci.instance_id
                       for c in s2.player_by_id("P0").hand)

        veh = _find_instance(s2, vehicle_ci.instance_id)
        pilot_ids = [u.instance_id for u in veh.attached_upgrades]
        assert pilot_ci.instance_id in pilot_ids

    def test_pilot_contributes_upgrade_power_and_hp(self):
        """compute_power / compute_hp add the pilot's upgrade_power / upgrade_hp."""
        from swu.engine.actions import apply, compute_power, compute_hp, PilotPlay
        state = _make_state()
        pilot_ci = self._make_synthetic_pilot(state, "P0",
                                              upgrade_power=1, upgrade_hp=2)
        vehicle_ci = _place_vehicle(state, "P0", "space")
        _give_resources(state, "P0", 8)

        vehicle_base_power = vehicle_ci.card_def.power  # 2
        vehicle_base_hp = vehicle_ci.card_def.hp        # 5

        action = PilotPlay(pilot_ci.instance_id, vehicle_ci.instance_id)
        s2 = apply(state, action)

        veh = _find_instance(s2, vehicle_ci.instance_id)
        assert compute_power(s2, veh) == vehicle_base_power + 1
        assert compute_hp(s2, veh) == vehicle_base_hp + 2

    def test_pilot_play_costs_resources(self):
        """Applying PilotPlay exhausts the correct number of resources."""
        from swu.engine.actions import apply, PilotPlay
        state = _make_state()
        # Use no-aspect piloting cost so the expected spend is exactly n
        pilot_ci = self._make_synthetic_pilot(state, "P0",
                                              epic_action="Piloting [3 resources]")
        vehicle_ci = _place_vehicle(state, "P0", "space")
        _give_resources(state, "P0", 8)

        ready_before = sum(1 for r in state.player_by_id("P0").resources
                           if not r.exhausted)
        action = PilotPlay(pilot_ci.instance_id, vehicle_ci.instance_id)
        s2 = apply(state, action)

        ready_after = sum(1 for r in s2.player_by_id("P0").resources
                          if not r.exhausted)
        assert ready_before - ready_after == 3

    def test_pilot_defeated_as_upgrade_not_double_homed(self):
        """Directly defeating a Pilot unit (attached via Piloting) detaches it from
        its host and sends it to discard exactly ONCE.

        Regression: a Pilot unit lives in its host's ``attached_upgrades`` but its
        ``card_def`` is a Unit, not an Upgrade.  ``_apply_defeat_unit`` used to key
        the detach branch on ``isinstance(card_def, Upgrade)`` and so routed the
        pilot through the unit-defeat path, which only scans the arenas — it never
        removed the pilot from the host, then appended it to discard, leaving the
        instance in BOTH places and tripping the "Duplicate instance_id" invariant
        (seen widely in soak with the boba_fett / han_solo Piloting decks).
        """
        from swu.engine.actions import apply, PilotPlay
        from swu.abilities.resolver import _apply_defeat_unit
        from swu.engine.state import Zone
        state = _make_state()
        pilot_ci = self._make_synthetic_pilot(state, "P0")
        vehicle_ci = _place_vehicle(state, "P0", "space")
        _give_resources(state, "P0", 8)

        s2 = apply(state, PilotPlay(pilot_ci.instance_id, vehicle_ci.instance_id))
        pid = pilot_ci.instance_id

        s3 = _apply_defeat_unit(s2, pid)

        # Detached from the host — no longer an attached upgrade.
        veh = _find_instance(s3, vehicle_ci.instance_id)
        assert pid not in [u.instance_id for u in veh.attached_upgrades]

        # Homed to the owner's discard exactly once, and nowhere else.
        p0 = s3.player_by_id("P0")
        assert sum(1 for c in p0.discard if c.instance_id == pid) == 1
        all_ids = [ci.instance_id for ci in s3.all_instances_for_player("P0")]
        assert all_ids.count(pid) == 1, "pilot instance must not be double-homed"
        discarded = next(c for c in p0.discard if c.instance_id == pid)
        assert discarded.zone == Zone.DISCARD

    def test_plain_play_still_offered_alongside_pilot_play(self):
        """A Piloting unit can still be played as a normal unit (PlayCard) too."""
        from swu.engine.actions import legal_actions, PilotPlay, PlayCard
        state = _make_state()
        pilot_ci = self._make_synthetic_pilot(state, "P0")
        _place_vehicle(state, "P0", "space")
        _give_resources(state, "P0", 10)  # enough for either cost

        acts = legal_actions(state)
        assert any(isinstance(a, PilotPlay) for a in acts)
        assert any(isinstance(a, PlayCard)
                   and a.instance_id == pilot_ci.instance_id for a in acts)


def _make_synthetic_nonvehicle():
    """A synthetic non-Vehicle unit card def."""
    from swu.cards.models import Unit
    return Unit(
        id=77702, card_uid=None, set_code="TST", set_name="T",
        card_number="NV", name="Non-Vehicle", subtitle=None, type="Unit",
        rarity="Common", is_unique=False, artist=None, text=None,
        text_styled=None, rules=None, rules_styled=None,
        aspects=(), keywords=(), traits=(), arenas=("Ground",),
        image_front_url=None, image_back_url=None,
        image_front_path=None, image_back_path=None,
        cost=2, power=2, hp=2,
    )


# ── Per-card acceptance tests (DB-backed) ─────────────────────────────────────

class TestDengar:
    """JTL_139 — Dengar: Piloting [2 resources Aggression Villainy], 1/2 pilot stats."""

    def test_jtl_139_pilot_play_offered_on_vehicle(self, repo):
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        dengar_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "139"))
        vehicle = _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        pilot_plays = [a for a in acts if isinstance(a, PilotPlay)
                       and a.instance_id == dengar_ci.instance_id]
        assert pilot_plays, "PilotPlay not offered for Dengar"

    def test_jtl_139_attach_contributes_stats(self, repo):
        from swu.engine.actions import apply, compute_power, compute_hp, PilotPlay
        state = _make_state()
        dengar_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "139"))
        vehicle_ci = _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        base_power = compute_power(state, vehicle_ci)
        base_hp = compute_hp(state, vehicle_ci)

        s2 = apply(state, PilotPlay(dengar_ci.instance_id, vehicle_ci.instance_id))
        veh = _find_instance(s2, vehicle_ci.instance_id)
        # Dengar: upgrade_power=1, upgrade_hp=2
        assert compute_power(s2, veh) == base_power + 1
        assert compute_hp(s2, veh) == base_hp + 2


class TestIG88:
    """JTL_141 — IG-88: Piloting [2 resources Aggression Villainy], 0/3 pilot stats."""

    def test_jtl_141_pilot_play_offered_on_vehicle(self, repo):
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        ig88_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "141"))
        _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        assert any(isinstance(a, PilotPlay) and a.instance_id == ig88_ci.instance_id
                   for a in acts)

    def test_jtl_141_attach_contributes_stats(self, repo):
        from swu.engine.actions import apply, compute_power, compute_hp, PilotPlay
        state = _make_state()
        ig88_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "141"))
        vehicle_ci = _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        base_power = compute_power(state, vehicle_ci)
        base_hp = compute_hp(state, vehicle_ci)

        s2 = apply(state, PilotPlay(ig88_ci.instance_id, vehicle_ci.instance_id))
        veh = _find_instance(s2, vehicle_ci.instance_id)
        # IG-88: upgrade_power=0, upgrade_hp=3
        assert compute_power(s2, veh) == base_power + 0
        assert compute_hp(s2, veh) == base_hp + 3


class TestBossk:
    """JTL_187 — Bossk: Piloting [2 resources Cunning Villainy], 2/2 pilot stats."""

    def test_jtl_187_pilot_play_offered_on_vehicle(self, repo):
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        bossk_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "187"))
        _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        assert any(isinstance(a, PilotPlay) and a.instance_id == bossk_ci.instance_id
                   for a in acts)

    def test_jtl_187_attach_contributes_stats(self, repo):
        from swu.engine.actions import apply, compute_power, compute_hp, PilotPlay
        state = _make_state()
        bossk_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "187"))
        vehicle_ci = _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        base_power = compute_power(state, vehicle_ci)
        base_hp = compute_hp(state, vehicle_ci)

        s2 = apply(state, PilotPlay(bossk_ci.instance_id, vehicle_ci.instance_id))
        veh = _find_instance(s2, vehicle_ci.instance_id)
        # Bossk: upgrade_power=2, upgrade_hp=2
        assert compute_power(s2, veh) == base_power + 2
        assert compute_hp(s2, veh) == base_hp + 2


class TestBobaFettJTL:
    """JTL_189 — Boba Fett: Piloting [2 resources Cunning Villainy], 2/3 pilot stats."""

    def test_jtl_189_pilot_play_offered_on_vehicle(self, repo):
        from swu.engine.actions import legal_actions, PilotPlay
        state = _make_state()
        boba_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "189"))
        _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        acts = legal_actions(state)
        assert any(isinstance(a, PilotPlay) and a.instance_id == boba_ci.instance_id
                   for a in acts)

    def test_jtl_189_attach_contributes_stats(self, repo):
        from swu.engine.actions import apply, compute_power, compute_hp, PilotPlay
        state = _make_state()
        boba_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "189"))
        vehicle_ci = _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 8)

        base_power = compute_power(state, vehicle_ci)
        base_hp = compute_hp(state, vehicle_ci)

        s2 = apply(state, PilotPlay(boba_ci.instance_id, vehicle_ci.instance_id))
        veh = _find_instance(s2, vehicle_ci.instance_id)
        # Boba Fett: upgrade_power=2, upgrade_hp=3
        assert compute_power(s2, veh) == base_power + 2
        assert compute_hp(s2, veh) == base_hp + 3

    def test_jtl_189_pilot_play_also_allows_normal_play(self, repo):
        """Boba Fett can be played as a normal unit OR as a pilot."""
        from swu.engine.actions import legal_actions, PilotPlay, PlayCard
        state = _make_state()
        boba_ci = _put_in_hand(state, "P0", _get_card(repo, "JTL", "189"))
        _place(state, "P0", _get_card(repo, "JTL", "183"), "space")
        _give_resources(state, "P0", 10)

        acts = legal_actions(state)
        assert any(isinstance(a, PilotPlay) and a.instance_id == boba_ci.instance_id
                   for a in acts)
        assert any(isinstance(a, PlayCard) and a.instance_id == boba_ci.instance_id
                   for a in acts)
