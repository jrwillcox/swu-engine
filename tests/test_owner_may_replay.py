"""Tests for the multi-decider return-then-owner-replays-free primitive — the
``owner_may_replay`` decision kind (Stage 4 batch 20 framework escalation).

Serves Baylan Skoll LOF_185 ("You may use the Force. If you do, return a
non-leader unit that costs 4 or less to its owner's hand. Then, its owner may
play it for free.") and Rio Durant LAW_93 (ungated, cost ≤ 3, grants the replay
Shielded for this phase).  The novelty is that the returned unit's OWNER — who
may be the source's opponent — decides whether to replay it (the say_no SOR_233
deciding-player shift), and the replay is FREE.

Method names embed the card number so the encoding verifier's ``-k`` gate selects
them.
"""
from __future__ import annotations

from tests.test_sor_cards import (
    repo,  # noqa: F401 — pytest fixture
    _get_card, _make_state, _place, _fire_when_played, _find_instance,
    _shield_count,
)


def _accept(state):
    from swu.engine.actions import legal_actions, apply, AcceptTrigger
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, AcceptTrigger)))


def _decline(state):
    from swu.engine.actions import legal_actions, apply, DeclineTrigger
    return apply(state, next(a for a in legal_actions(state)
                             if isinstance(a, DeclineTrigger)))


def _drain(state):
    """Drive AutoResolveEffects to quiescence (for no-target CustomEffects)."""
    from swu.engine.actions import legal_actions, apply, AutoResolveEffects
    for _ in range(40):
        auto = [a for a in legal_actions(state) if isinstance(a, AutoResolveEffects)]
        if not auto:
            break
        state = apply(state, auto[0])
    return state


def _in_arena(state, pid, iid):
    ps = state.player_by_id(pid)
    return any(c.instance_id == iid for c in ps.ground_arena + ps.space_arena)


def _in_hand(state, pid, iid):
    return any(c.instance_id == iid for c in state.player_by_id(pid).hand)


# ── Baylan Skoll LOF_185 (force-gated, cost ≤ 4, no keyword grant) ────────────

class TestBaylanSkoll:
    def _setup(self, repo, target_set="SOR", target_num="128"):
        """P0 plays Baylan with a Force token; P1 owns a cheap returnable unit."""
        state = _make_state()
        baylan = _place(state, "P0", _get_card(repo, "LOF", "185"), "ground")
        state.player_by_id("P0").has_force_token = True
        target = _place(state, "P1", _get_card(repo, target_set, target_num), "ground")
        return state, baylan, target

    def test_lof_185_force_return_then_owner_replays(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, ReplayReturnedUnit
        state, baylan, target = self._setup(repo)
        tid = target.instance_id
        state = _fire_when_played(state, baylan)
        state = _accept(state)                       # "you may use the Force"
        state = apply(state, ChooseTarget(tid))      # return this enemy unit
        state = _drain(state)
        top = state.pending_decisions[-1]
        assert top.kind == "owner_may_replay"
        assert top.deciding_player_id == "P1"        # the OWNER decides (opponent)
        replay = next(a for a in legal_actions(state)
                      if isinstance(a, ReplayReturnedUnit))
        state = apply(state, replay)
        state = _drain(state)
        assert not state.player_by_id("P0").has_force_token   # Force was spent
        assert _in_arena(state, "P1", tid)                    # replayed into play
        assert not _in_hand(state, "P1", tid)
        # Baylan grants no keyword on the replay (unlike Rio's Shielded).
        assert _shield_count(_find_instance(state, tid)) == 0

    def test_lof_185_owner_may_decline_replay(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, DeclineReplay
        state, baylan, target = self._setup(repo)
        tid = target.instance_id
        state = _fire_when_played(state, baylan)
        state = _accept(state)
        state = apply(state, ChooseTarget(tid))
        state = _drain(state)
        decline = next(a for a in legal_actions(state)
                       if isinstance(a, DeclineReplay))
        state = apply(state, decline)
        state = _drain(state)
        # Declined: the unit sits in its owner's hand, not in play.
        assert not state.player_by_id("P0").has_force_token   # Force still spent
        assert _in_hand(state, "P1", tid)
        assert not _in_arena(state, "P1", tid)

    def test_lof_185_decline_force_keeps_token(self, repo):
        state, baylan, target = self._setup(repo)
        tid = target.instance_id
        state = _fire_when_played(state, baylan)
        state = _decline(state)                      # decline the "use the Force"
        state = _drain(state)
        assert state.player_by_id("P0").has_force_token       # token kept
        assert _in_arena(state, "P1", tid)                    # unit untouched
        assert not state.pending_decisions

    def test_lof_185_no_force_token_not_offered(self, repo):
        # No Force token → the WhenPlayed trigger is gated off (not collected).
        state = _make_state()
        baylan = _place(state, "P0", _get_card(repo, "LOF", "185"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")
        state = _fire_when_played(state, baylan)
        assert not state.pending_decisions
        assert _in_arena(state, "P1", target.instance_id)

    def test_lof_185_cost_max_4_allows_cost_4(self, repo):
        # A cost-4 unit IS a legal return target (cost ≤ 4).
        from swu.engine.actions import legal_actions, apply, ChooseTarget, ReplayReturnedUnit
        state, baylan, target = self._setup(repo, "SOR", "46")  # cost 4
        tid = target.instance_id
        state = _fire_when_played(state, baylan)
        state = _accept(state)
        state = apply(state, ChooseTarget(tid))
        state = _drain(state)
        assert state.pending_decisions[-1].kind == "owner_may_replay"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ReplayReturnedUnit)))
        state = _drain(state)
        assert _in_arena(state, "P1", tid)


# ── Rio Durant LAW_93 (ungated, cost ≤ 3, grants Shielded on the replay) ──────

class TestRioDurant:
    def test_law_93_return_then_replay_with_shield(self, repo):
        from swu.engine.actions import legal_actions, apply, ChooseTarget, ReplayReturnedUnit
        state = _make_state()
        rio = _place(state, "P0", _get_card(repo, "LAW", "93"), "ground")
        target = _place(state, "P1", _get_card(repo, "SOR", "128"), "ground")  # cost 1
        tid = target.instance_id
        state = _fire_when_played(state, rio)
        state = _accept(state)                       # "you may return a unit"
        state = apply(state, ChooseTarget(tid))
        state = _drain(state)
        top = state.pending_decisions[-1]
        assert top.kind == "owner_may_replay"
        assert top.deciding_player_id == "P1"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ReplayReturnedUnit)))
        state = _drain(state)
        assert _in_arena(state, "P1", tid)
        # "It gains Shielded for this phase" → a Shield token on entry.
        assert _shield_count(_find_instance(state, tid)) == 1

    def test_law_93_friendly_return_owner_is_controller(self, repo):
        # Returning a FRIENDLY unit → its owner (the controller) decides.
        from swu.engine.actions import legal_actions, apply, ChooseTarget, ReplayReturnedUnit
        state = _make_state()
        rio = _place(state, "P0", _get_card(repo, "LAW", "93"), "ground")
        friendly = _place(state, "P0", _get_card(repo, "SOR", "225"), "ground")  # cost 1
        fid = friendly.instance_id
        state = _fire_when_played(state, rio)
        state = _accept(state)
        state = apply(state, ChooseTarget(fid))
        state = _drain(state)
        top = state.pending_decisions[-1]
        assert top.kind == "owner_may_replay"
        assert top.deciding_player_id == "P0"
        state = apply(state, next(a for a in legal_actions(state)
                                  if isinstance(a, ReplayReturnedUnit)))
        state = _drain(state)
        assert _in_arena(state, "P0", fid)
        assert _shield_count(_find_instance(state, fid)) == 1

    def test_law_93_cost_cap_excludes_cost_4(self, repo):
        # Rio's cap is cost ≤ 3; with only a cost-4 unit (and Rio, also cost 4)
        # on the board, the optional trigger has no legal target → auto-declines.
        state = _make_state()
        rio = _place(state, "P0", _get_card(repo, "LAW", "93"), "ground")
        big = _place(state, "P1", _get_card(repo, "SOR", "46"), "ground")  # cost 4
        state = _fire_when_played(state, rio)
        assert not state.pending_decisions
        assert _in_arena(state, "P1", big.instance_id)
