"""Where the card database lives, for tests — the single source of truth.

The repository deliberately ships no card data (see ``docs/pipeline.md``), so
every DB-backed test has to answer two questions the same way: *where* is the
database, and *what happens when it isn't there*.  Getting the second one wrong
is what made a fresh clone unusable: a module-local

    CardRepository("data/swu.db")

raises ``FileNotFoundError`` (a fixture ERROR, not a skip), and a bare
``sqlite3.connect("data/swu.db")`` is worse — it silently **creates** an empty
file, so the failure surfaces later as ``no such table: cards`` in thousands of
tests, and leaves a 0-byte ``data/swu.db`` behind that masks the real problem.
Route both through :func:`require_db` instead and a missing database becomes a
clean skip.

Resolving via ``SWU_DB`` (matching ``swu.web.paths.db_path`` and ``swu.cli``)
also means the no-database path can be exercised without moving the real data
directory::

    SWU_DB=/nonexistent pytest tests/ -q

The fallback is absolute rather than CWD-relative, so the suite no longer has to
be invoked from the repository root.

Fixture fallback
----------------
When the real corpus is absent, resolution falls through to the committed
``tests/fixtures/swu_fixture.db`` (a few hundred cards — see
``scripts/make_fixture_db.py``), so a fresh clone runs the engine, keyword, web
and regression tiers for real instead of skipping them.  ``SWU_DB``, when set,
always wins: pointing it at a nonexistent path still exercises the
no-database-at-all behaviour.

The tests whose subject IS the whole corpus must not run against the fixture;
``tests/fixture_scope.py`` lists them and ``conftest.py`` skips them in fixture
mode.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

FIXTURE_DB = _REPO_ROOT / "tests" / "fixtures" / "swu_fixture.db"


def db_path() -> Path:
    """Where the card database is: ``SWU_DB``, else the real corpus, else the fixture.

    Returns the conventional ``data/swu.db`` when nothing exists, so callers get
    a path to name in an error message — it is NOT proof the file is there.  Use
    :func:`require_db` before connecting.
    """
    env = os.environ.get("SWU_DB")
    if env:
        return Path(env)
    real = _REPO_ROOT / "data" / "swu.db"
    if real.exists():
        return real
    if FIXTURE_DB.exists():
        return FIXTURE_DB
    return real


def using_fixture() -> bool:
    """Whether the resolved database is the small committed fixture.

    Compares resolved paths, so pointing ``SWU_DB`` at the fixture (how the
    fixture-mode run is exercised without moving ``data/`` aside) counts.
    """
    try:
        return db_path().resolve() == FIXTURE_DB.resolve()
    except OSError:
        return False


def require_row(row, label: str):
    """A card row from a targeted lookup, or a skip when the fixture lacks it.

    The shared shape of the per-set suites' local lookup helpers (``_get_leader``,
    ``_get_by_type``, the token helpers): a missing row is a hard failure against
    the real corpus — the DB and the registry have drifted — but merely a card the
    small fixture doesn't carry when running on that.
    """
    if row is not None:
        return row
    if using_fixture():
        pytest.skip(f"{label} is not in the fixture DB")
    raise AssertionError(f"{label} not found")


def skip_on_fixture(what: str) -> None:
    """Skip the calling test in fixture mode, naming what the fixture can't supply.

    For the handful of tests inside otherwise fixture-friendly modules whose
    subject needs the real corpus (reprint aliasing across sets) or the card
    artwork (never distributed).  Module-wide cases belong in
    ``tests/fixture_scope.FULL_CORPUS_PATTERNS`` instead.
    """
    if using_fixture():
        pytest.skip(f"{what} — not available on the small fixture DB")


def require_db() -> Path:
    """The database path, or ``pytest.skip`` if there is no database at all.

    Safe to pass straight to ``sqlite3.connect`` — existence is checked first,
    so connecting cannot create a stray empty database.
    """
    path = db_path()
    if not path.exists():
        pytest.skip(f"swu.db not found at {path} — build it per docs/pipeline.md")
    return path
