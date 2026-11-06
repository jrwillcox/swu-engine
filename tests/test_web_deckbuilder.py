"""
Custom deck builder — HTTP route + resolve/catalog integration tests (Stage 3).

Drive the ``/api/decks/custom`` CRUD entirely over HTTP: happy paths, owner
isolation (user B gets 404 on user A's deck), unsigned → 401, the ``custom:``
``resolve_deck`` branch (a full game over HTTP with a custom deck on each side),
and the ``/api/decks`` catalog merge (only *complete* customs appear, tagged
``kind="custom"``).

Both the auth store and the custom-deck store are redirected to throwaway tmp
paths so the tests never touch real data.  Card ids are real rows in
``data/swu.db`` (mirrors ``tests/test_deckstore.py``).
"""
from __future__ import annotations

import random

import pytest

from tests.dbpath import require_db

pytest.importorskip("fastapi", reason="web extra not installed (pip install -e '.[web]')")

from fastapi.testclient import TestClient

import swu.web.app as appmod
import swu.web.deckstore as deckstore
from swu.web.auth import UserStore
import swu.web.auth as authmod
from swu.web.deckstore import DeckStore

# Real DB rows (see tests/test_deckstore.py).
LEADER = 5      # Luke Skywalker
BASE = 55       # Administrator's Tower
UNITS = [15, 20, 25, 30, 35, 45, 70, 75, 105, 115,
         120, 130, 145, 150, 155, 160, 165, 180, 185, 190]


def _full_pool() -> dict[str, int]:
    """A legal 50-card pool: 16 units ×3 + 1 unit ×2 = 50, all within the 3-cap."""
    pool = {str(u): 3 for u in UNITS[:16]}
    pool[str(UNITS[16])] = 2
    assert sum(pool.values()) == 50
    return pool


# The registration whitelist is configuration (SWU_ALLOWED_USERS), so pin it here
# rather than letting these tests depend on whatever the developer has exported.
# Alice is the admin, Bob an ordinary player; tests add more with setitem.
TEST_ALLOWED = {"alice": True, "bob": False}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    require_db()  # deck validation looks every card up in the card database
    monkeypatch.setattr(authmod, "ALLOWED", dict(TEST_ALLOWED))
    monkeypatch.setattr(appmod, "AUTH", UserStore(tmp_path / "users.json"))
    # One store instance backs both the routes and resolve_deck.
    monkeypatch.setattr(deckstore, "_SINGLETON", DeckStore(tmp_path / "custom_decks"))
    return TestClient(appmod.app)


def _token(client, username, password="pw"):
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def alice(client):
    return _token(client, "Alice")


@pytest.fixture()
def bob(client):
    return _token(client, "Bob")


def _complete_deck(client, token) -> dict:
    """Create + fully populate a deck over HTTP; return the complete CustomDeck."""
    deck = client.post("/api/decks/custom", json={"name": "My Deck"},
                       headers=_auth(token)).json()
    r = client.patch(
        f"/api/decks/custom/{deck['id']}",
        json={"leader_id": LEADER, "base_id": BASE, "cards": _full_pool()},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["complete"] is True and body["count"] == 50 and body["errors"] == []
    return body


# ── auth gating ─────────────────────────────────────────────────────────────────

def test_list_requires_auth(client):
    assert client.get("/api/decks/custom").status_code == 401


def test_create_requires_auth(client):
    assert client.post("/api/decks/custom", json={"name": "x"}).status_code == 401


# ── CRUD happy paths ─────────────────────────────────────────────────────────────

def test_create_returns_empty_draft(client, bob):
    r = client.post("/api/decks/custom", json={"name": "Aggro"}, headers=_auth(bob))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["owner"] == "bob" and body["name"] == "Aggro"
    assert body["leader_id"] is None and body["cards"] == {}
    assert body["complete"] is False and body["errors"]


def test_list_reflects_created_decks(client, bob):
    a = client.post("/api/decks/custom", json={"name": "A"}, headers=_auth(bob)).json()
    b = client.post("/api/decks/custom", json={"name": "B"}, headers=_auth(bob)).json()
    listed = client.get("/api/decks/custom", headers=_auth(bob)).json()
    assert {d["id"] for d in listed} == {a["id"], b["id"]}
    assert all(d["complete"] is False for d in listed)


def test_get_roundtrips(client, bob):
    d = client.post("/api/decks/custom", json={"name": "Deck"}, headers=_auth(bob)).json()
    got = client.get(f"/api/decks/custom/{d['id']}", headers=_auth(bob))
    assert got.status_code == 200
    assert got.json()["id"] == d["id"]


def test_get_missing_is_404(client, bob):
    assert client.get("/api/decks/custom/nope-nope", headers=_auth(bob)).status_code == 404


def test_patch_rename_and_slots(client, bob):
    d = client.post("/api/decks/custom", json={"name": "Old"}, headers=_auth(bob)).json()
    r = client.patch(
        f"/api/decks/custom/{d['id']}",
        json={"name": "New", "leader_id": LEADER, "base_id": BASE},
        headers=_auth(bob),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "New" and body["leader_id"] == LEADER and body["base_id"] == BASE


def test_patch_clear_leader_with_explicit_null(client, bob):
    d = client.post("/api/decks/custom", json={"name": "Deck"}, headers=_auth(bob)).json()
    client.patch(f"/api/decks/custom/{d['id']}", json={"leader_id": LEADER},
                 headers=_auth(bob))
    r = client.patch(f"/api/decks/custom/{d['id']}", json={"leader_id": None},
                     headers=_auth(bob))
    assert r.json()["leader_id"] is None


def test_patch_rejects_non_leader_in_leader_slot(client, bob):
    d = client.post("/api/decks/custom", json={"name": "Deck"}, headers=_auth(bob)).json()
    r = client.patch(f"/api/decks/custom/{d['id']}", json={"leader_id": UNITS[0]},
                     headers=_auth(bob))
    assert r.status_code == 400


def test_card_delta_endpoint(client, bob):
    d = client.post("/api/decks/custom", json={"name": "Deck"}, headers=_auth(bob)).json()
    r = client.post(f"/api/decks/custom/{d['id']}/cards",
                    json={"card_id": UNITS[0], "delta": 2}, headers=_auth(bob))
    assert r.status_code == 200
    assert r.json()["cards"] == {str(UNITS[0]): 2}
    r = client.post(f"/api/decks/custom/{d['id']}/cards",
                    json={"card_id": UNITS[0], "delta": -2}, headers=_auth(bob))
    assert str(UNITS[0]) not in r.json()["cards"]


def test_delete_removes_deck(client, bob):
    d = client.post("/api/decks/custom", json={"name": "Doomed"}, headers=_auth(bob)).json()
    assert client.delete(f"/api/decks/custom/{d['id']}", headers=_auth(bob)).json() == {"ok": True}
    assert client.get(f"/api/decks/custom/{d['id']}", headers=_auth(bob)).status_code == 404


# ── owner isolation ──────────────────────────────────────────────────────────────

def test_owner_isolation_get(client, bob, alice):
    d = client.post("/api/decks/custom", json={"name": "Bob's"}, headers=_auth(bob)).json()
    # Alice can't see Bob's deck.
    assert client.get(f"/api/decks/custom/{d['id']}", headers=_auth(alice)).status_code == 404
    assert d["id"] not in {x["id"] for x in client.get("/api/decks/custom", headers=_auth(alice)).json()}


def test_owner_isolation_mutations(client, bob, alice):
    d = client.post("/api/decks/custom", json={"name": "Bob's"}, headers=_auth(bob)).json()
    assert client.patch(f"/api/decks/custom/{d['id']}", json={"name": "hax"},
                        headers=_auth(alice)).status_code == 404
    assert client.delete(f"/api/decks/custom/{d['id']}", headers=_auth(alice)).status_code == 404


# ── catalog merge ────────────────────────────────────────────────────────────────

def test_catalog_anonymous_is_official_only(client, bob):
    _complete_deck(client, bob)
    decks = client.get("/api/decks").json()  # no bearer
    assert decks  # built-ins present
    assert all(d["kind"] == "official" for d in decks)
    assert not any(d["key"].startswith("custom:") for d in decks)


def test_catalog_appends_only_complete_customs(client, bob):
    complete = _complete_deck(client, bob)
    # a draft that must NOT appear
    client.post("/api/decks/custom", json={"name": "Draft"}, headers=_auth(bob))
    decks = client.get("/api/decks", headers=_auth(bob)).json()
    customs = [d for d in decks if d["kind"] == "custom"]
    assert len(customs) == 1
    c = customs[0]
    assert c["key"] == f"custom:bob:{complete['id']}"
    assert c["leader_name"] == "Luke Skywalker"
    assert "official" in {d["kind"] for d in decks}  # still merged with built-ins


# ── resolve_deck + full HTTP game ────────────────────────────────────────────────

def test_resolve_deck_builds_custom(client, bob):
    from swu.web.decks import resolve_deck
    complete = _complete_deck(client, bob)
    cards = resolve_deck(f"custom:bob:{complete['id']}")
    # 1 leader + 1 base + 50 pool = 52 cards
    assert len(cards) == 52


def test_resolve_incomplete_custom_raises(client, bob):
    from swu.web.decks import resolve_deck
    draft = client.post("/api/decks/custom", json={"name": "Draft"},
                        headers=_auth(bob)).json()
    with pytest.raises(FileNotFoundError):
        resolve_deck(f"custom:bob:{draft['id']}")


def test_create_game_with_incomplete_custom_is_400(client, bob):
    draft = client.post("/api/decks/custom", json={"name": "Draft"},
                        headers=_auth(bob)).json()
    r = client.post("/api/games", json={
        "human": {"kind": "human", "deck": f"custom:bob:{draft['id']}"},
        "bot": {"kind": "weighted_bot", "deck": "vader"},
        "seed": 1,
    })
    assert r.status_code == 400


_WEIGHTS = {
    "PlayCard": 8, "AttackWithUnit": 6, "DeployLeader": 5, "AttackWithLeader": 4,
    "UseAbility": 4, "AcceptTrigger": 4, "ExploitCommit": 5, "ExploitSacrifice": 4,
    "KeepHand": 3, "ResourceCard": 3, "ClaimInitiative": 2,
}


def _pick(rng, actions):
    weights = [_WEIGHTS.get(a["kind"], 1) for a in actions]
    return rng.choices(actions, weights=weights, k=1)[0]


def test_full_game_with_custom_deck_each_side(client, bob, alice):
    """A full game over HTTP with a custom deck on BOTH seats plays to a winner."""
    require_db()  # engine token lookup / from_json needs the card database
    bob_deck = _complete_deck(client, bob)
    alice_deck = _complete_deck(client, alice)
    resp = client.post("/api/games", json={
        "human": {"kind": "human", "deck": f"custom:bob:{bob_deck['id']}"},
        "bot": {"kind": "weighted_bot", "deck": f"custom:alice:{alice_deck['id']}"},
        "seed": 7,
    })
    assert resp.status_code == 200, resp.text
    snap = resp.json()
    gid = snap["game_id"]
    rng = random.Random(7)

    for _ in range(4000):
        if snap["winner"] is not None:
            break
        if snap["awaiting"] == "human":
            actions = snap["actions"]
            assert actions
            chosen = _pick(rng, actions)
            snap = client.post(f"/api/games/{gid}/actions/{chosen['action_id']}").json()
        elif snap["awaiting"] == "bot":
            snap = client.post(f"/api/games/{gid}/advance").json()
        else:  # terminal
            break

    assert snap["winner"] is not None, "custom-deck game did not reach a winner"
