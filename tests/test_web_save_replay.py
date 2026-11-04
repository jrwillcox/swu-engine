"""
Save/restore + replay tests (Phase 7, Part D).

Driven through the HTTP surface and the session layer:
  * a mid-game state round-trips through save -> load exactly (incl. pending
    decisions, i.e. mid-decision / mid-animation);
  * a recorded game replays to an identical final state (determinism).
"""
from __future__ import annotations

import json
import random

import pytest

from tests.dbpath import require_db

pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient

import swu.web.app as webapp
from swu.web.app import app
from swu.web.session import replay_to_state

_WEIGHTS = {
    "PlayCard": 8, "AttackWithUnit": 6, "DeployLeader": 5, "AttackWithLeader": 4,
    "UseAbility": 4, "AcceptTrigger": 4, "ExploitCommit": 5, "ExploitSacrifice": 4,
    "KeepHand": 3, "ResourceCard": 3, "ClaimInitiative": 2, "TakeMultiligan": 1,
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolate the on-disk save dir so tests never touch data/saves.
    monkeypatch.setattr(webapp.STORE, "save_dir", tmp_path / "saves")
    return TestClient(app)


def _fingerprint(state) -> str:
    """Canonical state JSON excluding the (non-restored) event log."""
    d = json.loads(state.to_json())
    d.pop("event_log", None)
    return json.dumps(d, sort_keys=True)


def _new(client, seed=7, difficulty="easy"):
    resp = client.post("/api/games", json={
        "human": {"kind": "human", "deck": "luke"},
        "bot": {"kind": "heuristic", "deck": "vader"},
        "seed": seed, "difficulty": difficulty,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _drive(client, game_id, rng, max_steps):
    """Play a few human steps (advancing the bot between), return last snapshot."""
    snap = client.get(f"/api/games/{game_id}/state").json()
    for _ in range(max_steps):
        if snap["winner"] or snap["awaiting"] == "terminal":
            break
        if snap["awaiting"] == "bot":
            snap = client.post(f"/api/games/{game_id}/advance").json()
            continue
        actions = snap["actions"]
        if not actions:
            break
        weights = [_WEIGHTS.get(a["kind"], 1) for a in actions]
        choice = rng.choices(actions, weights=weights, k=1)[0]
        snap = client.post(f"/api/games/{game_id}/actions/{choice['action_id']}").json()
    return snap


def test_save_restore_roundtrips_mid_game(client):
    require_db()  # engine token lookup / from_json needs the card database
    game = _new(client, seed=11)
    gid = game["game_id"]
    rng = random.Random(11)
    _drive(client, gid, rng, max_steps=12)

    live = webapp.STORE.get(gid)
    before_fp = _fingerprint(live.state)
    before_hist = list(live.action_history)

    save = client.post(f"/api/games/{gid}/save", params={"slot": "slot1"}).json()
    assert save["ok"] and save["slot"] == "slot1"
    assert "slot1" in client.get("/api/saves").json()

    loaded = client.post("/api/saves/slot1/load").json()
    new_gid = loaded["game_id"]
    assert new_gid != gid
    restored = webapp.STORE.get(new_gid)

    # Full state (incl. any pending decisions) and the action history round-trip.
    assert _fingerprint(restored.state) == before_fp
    assert restored.action_history == before_hist
    # The human's redacted view is identical too — except event_log_tail, which is
    # deliberately not persisted (the log isn't needed for replay; re-run actions).
    live_view = client.get(f"/api/games/{gid}/state").json()["view"]
    a, b = dict(loaded["view"]), dict(live_view)
    a.pop("event_log_tail", None)
    b.pop("event_log_tail", None)
    assert a == b


@pytest.mark.parametrize("difficulty", ["easy", "hard"])
def test_save_restore_keeps_difficulty(client, difficulty):
    """Regression: saves stored str(Difficulty.EASY) == "Difficulty.EASY", which
    coerce() read as NORMAL, so a restored Easy game got the LLM bot.  NORMAL is
    the fallback, so only EASY and HARD can catch this."""
    require_db()  # engine token lookup / from_json needs the card database
    gid = _new(client, seed=4, difficulty=difficulty)["game_id"]
    assert client.get(f"/api/games/{gid}/replay").json()["difficulty"] == difficulty

    client.post(f"/api/games/{gid}/save", params={"slot": "diff"})
    new_gid = client.post("/api/saves/diff/load").json()["game_id"]
    assert webapp.STORE.get(new_gid).difficulty.value == difficulty


def test_restored_game_is_playable(client):
    require_db()  # engine token lookup / from_json needs the card database
    game = _new(client, seed=3)
    gid = game["game_id"]
    _drive(client, gid, random.Random(3), max_steps=6)
    client.post(f"/api/games/{gid}/save", params={"slot": "s2"})
    loaded = client.post("/api/saves/s2/load").json()
    new_gid = loaded["game_id"]
    # The restored game can continue to a terminal state without error.
    snap = _drive(client, new_gid, random.Random(99), max_steps=400)
    # advance to flush any trailing bot turns
    for _ in range(50):
        if snap["winner"] or snap["awaiting"] == "terminal":
            break
        snap = client.post(f"/api/games/{new_gid}/advance").json()
    assert snap["awaiting"] in ("human", "bot", "terminal")


def test_replay_reproduces_final_state(client):
    """A recorded game replays deterministically to the same final state."""
    require_db()  # engine token lookup / from_json needs the card database
    game = _new(client, seed=5)
    gid = game["game_id"]
    snap = _drive(client, gid, random.Random(5), max_steps=2000)
    for _ in range(200):
        if snap["winner"] or snap["awaiting"] == "terminal":
            break
        snap = client.post(f"/api/games/{gid}/advance").json()

    live = webapp.STORE.get(gid)
    bundle = client.get(f"/api/games/{gid}/replay").json()
    assert bundle["seed"] == 5 and bundle["action_history"]

    replayed = replay_to_state(bundle)
    assert _fingerprint(replayed) == _fingerprint(live.state)
    assert replayed.winner == live.state.winner


def test_seedless_game_records_concrete_seed_and_replays(client):
    """A game created WITHOUT a seed (the web UI's default) still pins a concrete
    seed, so its replay bundle reproduces the game exactly.

    Regression: web games used to be created with seed=None, which let
    create_game draw fresh OS entropy that was never recorded.  The exported
    bundle carried "seed": null and diverged on the first hand-dependent action
    when re-driven.  SessionStore.create now generates the seed up front.
    """
    require_db()  # engine token lookup / from_json needs the card database
    game = _new(client, seed=None)
    gid = game["game_id"]
    snap = _drive(client, gid, random.Random(123), max_steps=2000)
    for _ in range(200):
        if snap["winner"] or snap["awaiting"] == "terminal":
            break
        snap = client.post(f"/api/games/{gid}/advance").json()

    live = webapp.STORE.get(gid)
    bundle = client.get(f"/api/games/{gid}/replay").json()
    assert bundle["seed"] is not None, "a seedless game must record a concrete seed"

    replayed = replay_to_state(bundle)
    assert _fingerprint(replayed) == _fingerprint(live.state)
    assert replayed.winner == live.state.winner


def test_replay_matches_recorded_fields_not_description():
    """Regression: replay matched moves by describe(), which gave both targets of
    a Force exhaust the same text, so a replay could exhaust the wrong unit."""
    from swu.engine.actions import UseForceOption
    from swu.web.session import IllegalStep, _action_params, _match_recorded

    a, b = UseForceOption("exhaust_friendly", "human_1"), UseForceOption("exhaust_friendly", "human_2")
    entry = {"kind": "UseForceOption", "desc": "ignored", "params": _action_params(b)}
    assert _match_recorded([a, b], entry, 0) is b
    # A recorded move that is no longer legal is a divergence, not a guess.
    with pytest.raises(IllegalStep):
        _match_recorded([a], entry, 0)
    # Entries saved before fields were recorded still match by description.
    assert _match_recorded([a, b], {"kind": "UseForceOption", "desc": b.describe()}, 0) is b


def test_replay_steps_endpoint(client):
    """The per-step replay endpoint returns one board snapshot per action (+1 for
    the initial state), with the final winner matching the live game."""
    require_db()  # engine token lookup / from_json needs the card database
    game = _new(client, seed=8)
    gid = game["game_id"]
    snap = _drive(client, gid, random.Random(8), max_steps=2000)
    for _ in range(200):
        if snap["winner"] or snap["awaiting"] == "terminal":
            break
        snap = client.post(f"/api/games/{gid}/advance").json()

    live = webapp.STORE.get(gid)
    bundle = client.get(f"/api/games/{gid}/replay").json()
    resp = client.post("/api/replay", json={"bundle": bundle})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    steps = body["steps"]
    assert len(steps) == len(bundle["action_history"]) + 1  # +1 initial state
    assert steps[0]["events"] == []                          # nothing before move 1
    assert body["human_id"] == "human"
    assert steps[-1]["winner"] == live.state.winner          # ends as it really did
