"""
User accounts for the web app — a tiny, file-backed login store.

Purpose: give the app a notion of *who* is using it, so features like the deck
builder (saving custom decks) and per-user saved games can be tied to a person.
This is a small-LAN app for a handful of known players, so the model is
deliberately small: a whitelist of permitted usernames, salted-PBKDF2 password
hashes, and opaque bearer tokens persisted client-side so the same machine stays
signed in.

Who may register is configuration, not code — see ``ALLOWED`` below.

Storage: ``data/users.json`` (path overridable via ``SWU_USERS``).  Deployment
should mirror *code only* and never touch ``data/``, so accounts created on a
deployed copy survive every deploy and separate instances keep separate user
files.

No new third-party dependency: hashing is stdlib ``hashlib.pbkdf2_hmac`` with a
per-user random salt, compared in constant time with ``hmac.compare_digest``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from pathlib import Path

from swu.web.paths import data_dir

# PBKDF2 work factor.  Plenty for a home LAN; not so high it slows tests.
PBKDF2_ITERATIONS = 200_000

# Default whitelist when nothing is configured: one admin account, so a fresh
# checkout can register and play immediately.
DEFAULT_ALLOWED_USERS = ("player",)


def _load_allowed() -> dict[str, bool]:
    """Build the registration whitelist from the environment.

    ``SWU_ALLOWED_USERS`` — comma-separated usernames permitted to register
    (case-insensitive; stored lowercased). Unset means ``DEFAULT_ALLOWED_USERS``.

    ``SWU_ADMIN_USERS`` — comma-separated subset granted admin rights (resetting
    other users' passwords, the admin screen). Unset means the *first* entry of
    the allowed list is the admin, which is the single-player default.

        SWU_ALLOWED_USERS=ada,grace,alan  SWU_ADMIN_USERS=ada

    An empty ``SWU_ALLOWED_USERS`` (set but blank) disables registration
    entirely, which is a legitimate way to freeze an instance's accounts.
    """
    raw = os.environ.get("SWU_ALLOWED_USERS")
    if raw is None:
        names = list(DEFAULT_ALLOWED_USERS)
    else:
        names = [n.strip().lower() for n in raw.split(",") if n.strip()]

    admin_raw = os.environ.get("SWU_ADMIN_USERS")
    if admin_raw is None:
        admins = set(names[:1])
    else:
        admins = {n.strip().lower() for n in admin_raw.split(",") if n.strip()}

    return {name: (name in admins) for name in names}


# The only usernames (lowercased) allowed to register, mapped to admin-ness.
# Read once at import; tests monkeypatch individual entries.
ALLOWED: dict[str, bool] = _load_allowed()


# ── errors (mapped to HTTP status codes by app.py) ────────────────────────────

class AuthError(Exception):
    """Base for all auth failures."""


class NotAllowed(AuthError):
    """Username is not on the whitelist."""


class AlreadyExists(AuthError):
    """Username is already registered (sign in instead)."""


class BadCredentials(AuthError):
    """Wrong username or password."""


class NotRegistered(AuthError):
    """No account for that username (can't reset)."""


class EmptyPassword(AuthError):
    """A password must be non-empty (no complexity rules otherwise)."""


# ── hashing ───────────────────────────────────────────────────────────────────

def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    ).hex()


# ── the store ─────────────────────────────────────────────────────────────────

class UserStore:
    """File-backed user accounts.  All public methods are thread-safe.

    The JSON shape (keyed by lowercased username)::

        {"version": 1, "users": {
            "ada": {"display": "Ada", "salt": "<hex>", "hash": "<hex>",
                     "admin": true, "tokens": ["<token>", ...]},
            ...
        }}
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._path = Path(path)
        else:
            env = os.environ.get("SWU_USERS")
            self._path = Path(env) if env else data_dir() / "users.json"
        self._lock = threading.RLock()

    # -- persistence -----------------------------------------------------------

    def _load(self) -> dict:
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"version": 1, "users": {}}
        if not isinstance(data, dict) or not isinstance(data.get("users"), dict):
            return {"version": 1, "users": {}}
        return data

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self._path)  # atomic-ish swap

    # -- queries ---------------------------------------------------------------

    def check(self, username: str) -> tuple[bool, bool]:
        """Return ``(exists, allowed)`` — drives the create-vs-enter-password UX."""
        key = username.strip().lower()
        allowed = key in ALLOWED
        with self._lock:
            exists = key in self._load()["users"]
        return exists, allowed

    def user_for_token(self, token: str | None) -> dict | None:
        """Resolve a bearer token to ``{username, admin}`` or ``None``."""
        if not token:
            return None
        with self._lock:
            for key, rec in self._load()["users"].items():
                if token in rec.get("tokens", []):
                    return {
                        "username": rec.get("display", key),
                        "admin": bool(rec.get("admin")),
                    }
        return None

    def list_users(self) -> list[dict]:
        """Every whitelisted user with a ``registered`` flag (for the admin screen)."""
        with self._lock:
            users = self._load()["users"]
        out: list[dict] = []
        for key, is_admin in ALLOWED.items():
            rec = users.get(key)
            out.append(
                {
                    "username": rec["display"] if rec else key.capitalize(),
                    "admin": is_admin,
                    "registered": rec is not None,
                }
            )
        return out

    # -- mutations -------------------------------------------------------------

    def register(self, username: str, password: str) -> str:
        key = username.strip().lower()
        if key not in ALLOWED:
            raise NotAllowed(username)
        if not password:
            raise EmptyPassword()
        with self._lock:
            data = self._load()
            if key in data["users"]:
                raise AlreadyExists(username)
            token = secrets.token_urlsafe(32)
            salt = secrets.token_bytes(16)
            data["users"][key] = {
                "display": username.strip() or key,  # keep the casing they typed
                "salt": salt.hex(),
                "hash": _hash_password(password, salt),
                "admin": ALLOWED[key],
                "tokens": [token],
            }
            self._save(data)
        return token

    def login(self, username: str, password: str) -> str:
        key = username.strip().lower()
        with self._lock:
            data = self._load()
            rec = data["users"].get(key)
            if rec is None or not self._verify(rec, password):
                raise BadCredentials()
            token = secrets.token_urlsafe(32)
            rec.setdefault("tokens", []).append(token)
            self._save(data)
        return token

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            data = self._load()
            changed = False
            for rec in data["users"].values():
                toks = rec.get("tokens", [])
                if token in toks:
                    toks.remove(token)
                    changed = True
            if changed:
                self._save(data)

    def set_password(self, username: str, password: str) -> None:
        """Admin reset — also invalidates the user's existing sessions."""
        key = username.strip().lower()
        if not password:
            raise EmptyPassword()
        with self._lock:
            data = self._load()
            rec = data["users"].get(key)
            if rec is None:
                raise NotRegistered(username)
            salt = secrets.token_bytes(16)
            rec["salt"] = salt.hex()
            rec["hash"] = _hash_password(password, salt)
            rec["tokens"] = []  # force re-login everywhere on a reset
            self._save(data)

    # -- internals -------------------------------------------------------------

    @staticmethod
    def _verify(rec: dict, password: str) -> bool:
        salt = bytes.fromhex(rec["salt"])
        return hmac.compare_digest(rec["hash"], _hash_password(password, salt))
