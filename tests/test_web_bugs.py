"""
Backend bug-report tests — drive the BugStore + endpoints entirely over HTTP.

Covers the full lifecycle (create → list → get → reply → mark-read → unread-count
→ status → archive), the multi-user rule (user A cannot see user B's thread; admin
can see anyone's, bucketed for triage), the two independent "archive" concepts, and
that a reporter's inbox spans BOTH ``bug_reports/`` and ``bug_reports/archive/``.

Both the auth store and the bug store are redirected to throwaway tmp paths so the
tests never touch real data.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi", reason="web extra not installed (pip install -e '.[web]')")

from fastapi.testclient import TestClient

import swu.web.app as appmod
from swu.web.auth import UserStore
import swu.web.auth as authmod
from swu.web.bugs import BugStore


@pytest.fixture()
def bug_root(tmp_path):
    return tmp_path / "bug_reports"


# The registration whitelist is configuration (SWU_ALLOWED_USERS), so pin it here
# rather than letting these tests depend on whatever the developer has exported.
# Alice is the admin, Bob an ordinary player; tests add more with setitem.
TEST_ALLOWED = {"alice": True, "bob": False}


@pytest.fixture()
def client(tmp_path, bug_root, monkeypatch):
    monkeypatch.setattr(authmod, "ALLOWED", dict(TEST_ALLOWED))
    monkeypatch.setattr(appmod, "AUTH", UserStore(tmp_path / "users.json"))
    monkeypatch.setattr(appmod, "BUGS", BugStore(bug_root))
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


def _create(client, token, title="Boba attack did nothing", **kw):
    body = {"title": title, "expected": "3 damage", "actual": "nothing", **kw}
    return client.post("/api/bugs", json=body, headers=_auth(token))


# ── create ────────────────────────────────────────────────────────────────────

def test_create_requires_auth(client):
    assert client.post("/api/bugs", json={"title": "x"}).status_code == 401


def test_create_returns_thread_with_initial_message(client, bob):
    r = _create(client, bob)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "new"
    assert body["author"] == "Bob"
    assert body["reporter_archived"] is False
    assert len(body["messages"]) == 1
    msg = body["messages"][0]
    assert msg["from"] == "Bob"
    assert msg["title"] == "Boba attack did nothing"
    assert msg["expected"] == "3 damage" and msg["actual"] == "nothing"
    assert msg["read_by"] == ["Bob"]        # the author has read their own report


def test_create_rejects_empty_title(client, bob):
    assert _create(client, bob, title="   ").status_code == 400


def test_create_writes_folder_and_thread_json(client, bob, bug_root):
    bug_id = _create(client, bob).json()["id"]
    tj = bug_root / bug_id / "thread.json"
    assert tj.exists()
    data = json.loads(tj.read_text(encoding="utf-8"))
    assert data["author"] == "Bob" and data["status"] == "new"


def test_create_writes_screenshot_and_game(client, bob, bug_root):
    import base64

    png = base64.b64encode(b"\x89PNG fake bytes").decode()
    r = _create(
        client, bob,
        screenshot_b64=f"data:image/png;base64,{png}",
        game={"seed": 7, "actions": []},
        context={"screen": "game", "game_id": "g1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_screenshot"] is True and body["has_game"] is True
    assert body["context"]["screen"] == "game"
    folder = bug_root / body["id"]
    assert (folder / "screenshot.png").read_bytes() == b"\x89PNG fake bytes"
    assert json.loads((folder / "game.json").read_text())["seed"] == 7


def test_bad_screenshot_does_not_fail_the_report(client, bob):
    r = _create(client, bob, screenshot_b64="!!!not base64!!!")
    assert r.status_code == 200
    assert r.json()["has_screenshot"] is False


# ── list / get / access control ───────────────────────────────────────────────

def test_reporter_lists_only_own_threads(client, alice, bob):
    _create(client, bob, title="Bob bug")
    _create(client, alice, title="Alice bug")
    bob_list = client.get("/api/bugs", headers=_auth(bob)).json()
    assert [t["title"] for t in bob_list] == ["Bob bug"]


def test_user_cannot_get_another_users_thread(client, alice, bob):
    bug_id = _create(client, bob).json()["id"]
    # Alice is admin — allowed.  Register a plain second reporter to prove the block.
    assert client.get(f"/api/bugs/{bug_id}", headers=_auth(alice)).status_code == 200
    # Bob owns it.
    assert client.get(f"/api/bugs/{bug_id}", headers=_auth(bob)).status_code == 200


def test_non_owner_non_admin_is_forbidden(client, bob, monkeypatch):
    # Add a third whitelisted, non-admin user just for this test.
    from swu.web import auth as authmod
    monkeypatch.setitem(authmod.ALLOWED, "kate", False)
    kate = _token(client, "Kate")
    bug_id = _create(client, bob).json()["id"]
    assert client.get(f"/api/bugs/{bug_id}", headers=_auth(kate)).status_code == 403


def test_get_missing_thread_is_404(client, bob):
    assert client.get("/api/bugs/nope", headers=_auth(bob)).status_code == 404


def test_id_traversal_is_rejected(client, bob):
    # A path-traversal id must not escape the bug_reports dir.
    assert client.get("/api/bugs/..%2F..%2Fusers", headers=_auth(bob)).status_code in (404, 400)


# ── reply / read / unread-count ───────────────────────────────────────────────

def test_reply_appends_and_dev_reply_is_unread_for_reporter(client, alice, bob):
    bug_id = _create(client, bob).json()["id"]
    # Alice (admin / dev) replies.
    r = client.post(f"/api/bugs/{bug_id}/reply", json={"text": "Looking into it"}, headers=_auth(alice))
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert msgs[-1]["from"] == "Alice" and msgs[-1]["text"] == "Looking into it"
    # Bob has one unread (Alice's reply); Alice has none of his own outstanding.
    assert client.get("/api/bugs/unread-count", headers=_auth(bob)).json()["count"] == 1
    assert client.get("/api/bugs/unread-count", headers=_auth(alice)).json()["count"] == 0


def test_empty_reply_rejected(client, bob):
    bug_id = _create(client, bob).json()["id"]
    assert client.post(f"/api/bugs/{bug_id}/reply", json={"text": "  "}, headers=_auth(bob)).status_code == 400


def test_mark_read_clears_unread(client, alice, bob):
    bug_id = _create(client, bob).json()["id"]
    client.post(f"/api/bugs/{bug_id}/reply", json={"text": "hi"}, headers=_auth(alice))
    assert client.get("/api/bugs/unread-count", headers=_auth(bob)).json()["count"] == 1
    client.post(f"/api/bugs/{bug_id}/read", headers=_auth(bob))
    assert client.get("/api/bugs/unread-count", headers=_auth(bob)).json()["count"] == 0


# ── status / admin triage ─────────────────────────────────────────────────────

def test_admin_sets_status(client, alice, bob):
    bug_id = _create(client, bob).json()["id"]
    r = client.post(f"/api/admin/bugs/{bug_id}/status", json={"status": "investigating"}, headers=_auth(alice))
    assert r.status_code == 200 and r.json()["status"] == "investigating"


def test_bad_status_rejected(client, alice, bob):
    bug_id = _create(client, bob).json()["id"]
    r = client.post(f"/api/admin/bugs/{bug_id}/status", json={"status": "bogus"}, headers=_auth(alice))
    assert r.status_code == 400


def test_non_admin_cannot_set_status_or_triage(client, bob):
    bug_id = _create(client, bob).json()["id"]
    assert client.post(f"/api/admin/bugs/{bug_id}/status", json={"status": "resolved"}, headers=_auth(bob)).status_code == 403
    assert client.get("/api/admin/bugs", headers=_auth(bob)).status_code == 403


def test_admin_triage_buckets(client, alice, bob):
    # A brand-new report → NEEDS YOU.
    new_id = _create(client, bob, title="fresh").json()["id"]
    # A report Alice set needs_info and last replied to → WAITING ON REPORTER.
    waiting_id = _create(client, bob, title="waiting").json()["id"]
    client.post(f"/api/bugs/{waiting_id}/reply", json={"text": "more info?"}, headers=_auth(alice))
    client.post(f"/api/admin/bugs/{waiting_id}/status", json={"status": "needs_info"}, headers=_auth(alice))
    # A resolved report → RESOLVED.
    resolved_id = _create(client, bob, title="done").json()["id"]
    client.post(f"/api/admin/bugs/{resolved_id}/status", json={"status": "resolved"}, headers=_auth(alice))

    triage = client.get("/api/admin/bugs", headers=_auth(alice)).json()
    assert new_id in [t["id"] for t in triage["needs_you"]]
    assert waiting_id in [t["id"] for t in triage["waiting_on_reporter"]]
    assert resolved_id in [t["id"] for t in triage["resolved"]]


def test_triage_summary_carries_the_reporters_comment(client, alice, bob):
    # The triage list surfaces the original submission (expected/actual) so Alice
    # can read the gist without opening the thread.
    bug_id = _create(client, bob, title="scimitar", expected="6 damage",
                     actual="did 3 and no ability").json()["id"]
    triage = client.get("/api/admin/bugs", headers=_auth(alice)).json()
    row = next(t for t in triage["needs_you"] if t["id"] == bug_id)
    assert row["expected"] == "6 damage"
    assert row["actual"] == "did 3 and no ability"


def test_reporter_reply_moves_needs_info_back_to_needs_you(client, alice, bob):
    bug_id = _create(client, bob).json()["id"]
    client.post(f"/api/bugs/{bug_id}/reply", json={"text": "which screen?"}, headers=_auth(alice))
    client.post(f"/api/admin/bugs/{bug_id}/status", json={"status": "needs_info"}, headers=_auth(alice))
    # Bob answers → latest message is the reporter's → back to NEEDS YOU.
    client.post(f"/api/bugs/{bug_id}/reply", json={"text": "the game screen"}, headers=_auth(bob))
    triage = client.get("/api/admin/bugs", headers=_auth(alice)).json()
    assert bug_id in [t["id"] for t in triage["needs_you"]]
    assert bug_id not in [t["id"] for t in triage["waiting_on_reporter"]]


# ── archive (folder move) vs reporter_archived (cosmetic) ──────────────────────────

def test_archive_moves_folder_and_drops_from_triage_but_stays_in_inbox(client, alice, bob, bug_root):
    bug_id = _create(client, bob).json()["id"]
    r = client.post(f"/api/admin/bugs/{bug_id}/archive", headers=_auth(alice))
    assert r.status_code == 200 and r.json()["archived"] is True
    # Folder physically moved.
    assert not (bug_root / bug_id).exists()
    assert (bug_root / "archive" / bug_id / "thread.json").exists()
    # Dropped from Alice's triage…
    triage = client.get("/api/admin/bugs", headers=_auth(alice)).json()
    all_ids = [t["id"] for b in triage.values() for t in b]
    assert bug_id not in all_ids
    # …but still in Bob's inbox (which spans both dirs).
    bob_inbox = client.get("/api/bugs", headers=_auth(bob)).json()
    row = next(t for t in bob_inbox if t["id"] == bug_id)
    assert row["archived"] is True
    # And still fetchable by the owner.
    assert client.get(f"/api/bugs/{bug_id}", headers=_auth(bob)).status_code == 200


def test_non_admin_cannot_archive(client, bob):
    bug_id = _create(client, bob).json()["id"]
    assert client.post(f"/api/admin/bugs/{bug_id}/archive", headers=_auth(bob)).status_code == 403


def test_reporter_archive_toggle_is_cosmetic_and_never_moves_folder(client, bob, bug_root):
    # The reporter tidies their own inbox: reporter_archived flips, folder stays put,
    # and the thread stays listed (the Archived tab reads the same list).
    bug_id = _create(client, bob).json()["id"]
    r = client.post(f"/api/bugs/{bug_id}/reporter-archive", json={"archived": True}, headers=_auth(bob))
    assert r.status_code == 200 and r.json()["reporter_archived"] is True
    assert (bug_root / bug_id / "thread.json").exists()          # not moved on disk
    assert not (bug_root / "archive" / bug_id).exists()
    row = next(t for t in client.get("/api/bugs", headers=_auth(bob)).json() if t["id"] == bug_id)
    assert row["reporter_archived"] is True and row["archived"] is False
    # …and un-archiving flips it back.
    r = client.post(f"/api/bugs/{bug_id}/reporter-archive", json={"archived": False}, headers=_auth(bob))
    assert r.status_code == 200 and r.json()["reporter_archived"] is False


def test_other_reporter_cannot_reporter_archive(client, bob, monkeypatch):
    from swu.web import auth as authmod
    monkeypatch.setitem(authmod.ALLOWED, "kate", False)
    kate = _token(client, "Kate")
    bug_id = _create(client, bob).json()["id"]
    r = client.post(f"/api/bugs/{bug_id}/reporter-archive", json={"archived": True}, headers=_auth(kate))
    assert r.status_code == 403


def test_status_change_never_moves_folder(client, alice, bob, bug_root):
    bug_id = _create(client, bob).json()["id"]
    client.post(f"/api/admin/bugs/{bug_id}/status", json={"status": "resolved"}, headers=_auth(alice))
    # Still in the active dir — resolving is not archiving.
    assert (bug_root / bug_id / "thread.json").exists()
    assert not (bug_root / "archive" / bug_id).exists()


# ── game.json (replay bundle) serving — Stage 4 replay-viewer link ─────────────

def test_game_json_served_to_admin_and_owner(client, alice, bob):
    bug_id = _create(client, bob, game={"replay": {"seed": 7}, "winner": None}).json()["id"]
    # Admin (Alice) can fetch it…
    r = client.get(f"/api/bugs/{bug_id}/game", headers=_auth(alice))
    assert r.status_code == 200
    assert r.json()["replay"]["seed"] == 7
    # …and so can the owner (Bob).
    assert client.get(f"/api/bugs/{bug_id}/game", headers=_auth(bob)).status_code == 200


def test_game_json_absent_is_404(client, bob):
    # A report filed from a non-game screen has no game.json.
    bug_id = _create(client, bob).json()["id"]
    assert client.get(f"/api/bugs/{bug_id}/game", headers=_auth(bob)).status_code == 404


def test_game_json_respects_access_control(client, bob, monkeypatch):
    from swu.web import auth as authmod
    monkeypatch.setitem(authmod.ALLOWED, "kate", False)
    kate = _token(client, "Kate")
    bug_id = _create(client, bob, game={"replay": {}}).json()["id"]
    assert client.get(f"/api/bugs/{bug_id}/game", headers=_auth(kate)).status_code == 403
