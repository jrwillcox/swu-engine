"""Synthetic framework tests for the capture primitive (the-mandalorian:07).

Exercises actions._apply_capture / _release_captured_cards directly with
arbitrary cards (independent of any specific card), and asserts the engine
invariants (card conservation, zone-tag consistency) hold across a
capture-then-release cycle.  The card-level test for The Mandalorian's Rifle
SHD_251 lives in tests/test_shd_cards.py::TestTheMandaloriansRifle.
"""
from __future__ import annotations

from tests.test_sor_cards import repo, _get_card, _make_state, _place  # noqa: F401


def _capture_setup(repo):
    captor = _get_card(repo, "SOR", "46")
    target = _get_card(repo, "SOR", "46")
    state = _make_state()
    captor_ci = _place(state, "P0", captor, "ground")
    target_ci = _place(state, "P1", target, "ground")
    return state, captor_ci, target_ci


class TestCaptureSeam:
    def test_capture_moves_target_to_captor_capture_pile(self, repo):
        from swu.engine.actions import _apply_capture
        from swu.engine.state import Zone
        state, captor_ci, target_ci = _capture_setup(repo)

        state = _apply_capture(state, captor_ci.instance_id, target_ci.instance_id)

        # Left P1's arena, now facedown in P0's capture pile, owner unchanged.
        assert all(c.instance_id != target_ci.instance_id
                   for c in state.player_by_id("P1").ground_arena)
        cap = state.player_by_id("P0").capture_pile
        assert [c.instance_id for c in cap] == [target_ci.instance_id]
        captured = cap[0]
        assert captured.owner_id == "P1"
        assert captured.captured_by == captor_ci.instance_id
        assert captured.zone == Zone.CAPTURE_PILE
        assert captured.face_down is True

    def test_capture_clears_damage_and_strips_upgrades(self, repo):
        from swu.engine.actions import _apply_capture
        from swu.engine.state import CardInstance, Zone
        import uuid
        state, captor_ci, target_ci = _capture_setup(repo)
        target_ci.damage = 2
        real_upg = _get_card(repo, "SOR", "53")  # a real (non-token) upgrade
        up = CardInstance(instance_id=f"up_{uuid.uuid4().hex[:6]}",
                          card_def=real_upg, owner_id="P1", zone=Zone.GROUND_ARENA)
        target_ci.attached_upgrades.append(up)

        state = _apply_capture(state, captor_ci.instance_id, target_ci.instance_id)

        captured = state.player_by_id("P0").capture_pile[0]
        assert captured.damage == 0
        assert captured.attached_upgrades == []
        # The detached real upgrade went to its owner's discard.
        assert any(c.instance_id == up.instance_id
                   for c in state.player_by_id("P1").discard)

    def test_release_returns_card_to_owner_arena_ready(self, repo):
        from swu.engine.actions import _apply_capture, _release_captured_cards
        state, captor_ci, target_ci = _capture_setup(repo)

        state = _apply_capture(state, captor_ci.instance_id, target_ci.instance_id)
        _release_captured_cards(state, captor_ci)

        assert state.player_by_id("P0").capture_pile == []
        p1_arena = state.player_by_id("P1").ground_arena
        returned = next(c for c in p1_arena if c.instance_id == target_ci.instance_id)
        assert returned.captured_by is None
        assert returned.face_down is False
        assert returned.exhausted is False

    def test_release_only_affects_that_captor(self, repo):
        """A different captor's captives stay put."""
        from swu.engine.actions import _apply_capture, _release_captured_cards
        state, captor_ci, target_ci = _capture_setup(repo)
        other_captor = _place(state, "P0", _get_card(repo, "SOR", "46"), "ground")

        state = _apply_capture(state, captor_ci.instance_id, target_ci.instance_id)
        # Release a captor that holds nothing — the captive remains captured.
        _release_captured_cards(state, other_captor)
        assert len(state.player_by_id("P0").capture_pile) == 1

    def test_invariants_hold_across_capture_and_release(self, repo):
        from swu.engine.actions import _apply_capture, _release_captured_cards
        from swu.engine.invariants import CheckContext, check
        state, captor_ci, target_ci = _capture_setup(repo)
        ctx = CheckContext.from_state(state)
        check(state, ctx)

        state = _apply_capture(state, captor_ci.instance_id, target_ci.instance_id)
        check(state, ctx)   # conservation + zone-tag consistency while captured

        _release_captured_cards(state, captor_ci)
        check(state, ctx)   # and after the captive returns
