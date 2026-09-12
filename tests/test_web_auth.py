"""
Backend auth tests — drive the login API entirely through HTTP.

Covers the whitelist, first-time register vs returning login, case-insensitive
usernames, bearer-token `me`/logout, the admin password reset (and its 403 for a
non-admin), the stdlib pbkdf2 hash round-trip, and JSON persistence to a temp
users file.  The module-level `AUTH` store is redirected to a tmp path so these
never touch the real `data/users.json`.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi", reason="web extra not installed (pip install -e '.[web]')")

from fastapi.testclient import TestClient

import swu.web.app as appmod
from swu.web.auth import UserStore
import swu.web.auth as authmod


@pytest.fixture()
def users_path(tmp_path):
    return tmp_path / "users.json"


# The registration whitelist is configuration (SWU_ALLOWED_USERS), so pin it here
# rather than letting these tests depend on whatever the developer has exported.
# Alice is the admin, Bob an ordinary player; tests add more with setitem.
TEST_ALLOWED = {"alice": True, "bob": False}


@pytest.fixture(autouse=True)
def _pin_whitelist(monkeypatch):
    """Apply TEST_ALLOWED to every test here, including those that drive
    UserStore directly rather than through the HTTP client."""
    monkeypatch.setattr(authmod, "ALLOWED", dict(TEST_ALLOWED))


@pytest.fixture()
def client(users_path, monkeypatch):
    # Redirect the app's global store to a throwaway file (routes read the global
    # at call time, so this swaps the store for every endpoint).
    monkeypatch.setattr(appmod, "AUTH", UserStore(users_path))
    return TestClient(appmod.app)


def _register(client, username, password):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── check: whitelist + existence ──────────────────────────────────────────────

def test_check_unknown_user_not_yet_registered_but_allowed(client):
    r = client.post("/api/auth/check", json={"username": "Alice"})
    assert r.status_code == 200
    assert r.json() == {"exists": False, "allowed": True}


def test_check_rejects_non_whitelisted_name(client):
    # "Zoe" is deliberately absent from TEST_ALLOWED.
    r = client.post("/api/auth/check", json={"username": "Zoe"})
    assert r.json() == {"exists": False, "allowed": False}


# ── register ──────────────────────────────────────────────────────────────────

def test_register_whitelisted_user_returns_token(client):
    r = _register(client, "Alice", "hunter2")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "Alice"      # display casing preserved
    assert body["admin"] is True            # Alice is the admin
    assert body["token"]


def test_register_non_whitelisted_is_forbidden(client):
    r = _register(client, "Zoe", "x")
    assert r.status_code == 403


def test_register_empty_password_is_rejected(client):
    r = _register(client, "Bob", "")
    assert r.status_code == 400


def test_duplicate_register_conflicts(client):
    assert _register(client, "Bob", "one").status_code == 200
    r = _register(client, "Bob", "two")
    assert r.status_code == 409


def test_non_admin_user_is_not_admin(client):
    assert _register(client, "Bob", "pw").json()["admin"] is False


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_after_register_succeeds(client):
    _register(client, "Bob", "pw")
    r = _login(client, "Bob", "pw")
    assert r.status_code == 200
    assert r.json()["username"] == "Bob"


def test_login_wrong_password_is_unauthorized(client):
    _register(client, "Bob", "pw")
    assert _login(client, "Bob", "nope").status_code == 401


def test_login_unknown_user_is_unauthorized(client):
    assert _login(client, "Bob", "pw").status_code == 401


def test_username_is_case_insensitive(client):
    _register(client, "Alice", "pw")
    # check sees the existing account regardless of casing…
    assert client.post("/api/auth/check", json={"username": "ALICE"}).json()["exists"] is True
    # …and login works with any casing.
    assert _login(client, "aLiCe", "pw").status_code == 200


# ── me / logout ───────────────────────────────────────────────────────────────

def test_me_resolves_the_token(client):
    token = _register(client, "Alice", "pw").json()["token"]
    r = client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == {"username": "Alice", "admin": True}


def test_me_without_token_is_unauthorized(client):
    assert client.get("/api/auth/me").status_code == 401


def test_logout_invalidates_the_token(client):
    token = _register(client, "Bob", "pw").json()["token"]
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 200
    assert client.post("/api/auth/logout", headers=_auth(token)).status_code == 200
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401


# ── admin reset ───────────────────────────────────────────────────────────────

def test_admin_can_list_users(client):
    token = _register(client, "Alice", "pw").json()["token"]
    r = client.get("/api/auth/users", headers=_auth(token))
    assert r.status_code == 200
    by_name = {u["username"]: u for u in r.json()}
    assert by_name["Alice"] == {"username": "Alice", "admin": True, "registered": True}
    assert by_name["Bob"] == {"username": "Bob", "admin": False, "registered": False}


def test_non_admin_cannot_list_users(client):
    token = _register(client, "Bob", "pw").json()["token"]
    assert client.get("/api/auth/users", headers=_auth(token)).status_code == 403


def test_admin_resets_another_users_password(client):
    admin = _register(client, "Alice", "adminpw").json()["token"]
    _register(client, "Bob", "oldpw")
    r = client.post(
        "/api/auth/reset",
        json={"username": "Bob", "new_password": "newpw"},
        headers=_auth(admin),
    )
    assert r.status_code == 200
    assert _login(client, "Bob", "oldpw").status_code == 401   # old password dead
    assert _login(client, "Bob", "newpw").status_code == 200   # new one works


def test_reset_invalidates_existing_sessions(client):
    admin = _register(client, "Alice", "adminpw").json()["token"]
    bob_token = _register(client, "Bob", "oldpw").json()["token"]
    client.post(
        "/api/auth/reset",
        json={"username": "Bob", "new_password": "newpw"},
        headers=_auth(admin),
    )
    assert client.get("/api/auth/me", headers=_auth(bob_token)).status_code == 401


def test_non_admin_cannot_reset(client):
    _register(client, "Alice", "adminpw")
    bob = _register(client, "Bob", "pw").json()["token"]
    r = client.post(
        "/api/auth/reset",
        json={"username": "Alice", "new_password": "x"},
        headers=_auth(bob),
    )
    assert r.status_code == 403


# ── store-level: hashing + persistence ────────────────────────────────────────

def test_passwords_are_hashed_not_plaintext(client, users_path):
    _register(client, "Bob", "supersecret")
    raw = users_path.read_text(encoding="utf-8")
    assert "supersecret" not in raw
    data = json.loads(raw)
    rec = data["users"]["bob"]
    assert rec["hash"] and rec["salt"]
    assert rec["hash"] != "supersecret"


def test_store_persists_across_instances(users_path):
    store = UserStore(users_path)
    store.register("Alice", "pw")
    # A fresh store reading the same file sees the account and verifies the login.
    reborn = UserStore(users_path)
    token = reborn.login("alice", "pw")
    assert reborn.user_for_token(token) == {"username": "Alice", "admin": True}


def test_pbkdf2_round_trip_rejects_wrong_password(users_path):
    store = UserStore(users_path)
    store.register("Bob", "right")
    from swu.web.auth import BadCredentials

    with pytest.raises(BadCredentials):
        store.login("Bob", "wrong")
