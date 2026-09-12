"""
Filesystem layout resolution for the web backend.

The engine already resolves `swu.db`; here we locate the *data directory*
(which holds both `swu.db` and the `images/` tree) so the image endpoint can
turn a DB-stored relative path like ``images\\SOR\\5_front.png`` into an
absolute file on disk.

Resolution order:
1. ``SWU_DB`` env var (points at the .db file; data dir is its parent).
2. ``<repo>/swu-game/data/swu.db``
3. ``<repo>/data/swu.db``
"""
from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from pathlib import Path


def _candidates() -> list[Path]:
    env = os.environ.get("SWU_DB")
    here = Path(__file__).resolve()
    # .../swu-game/src/swu/web/paths.py -> parents[3] == .../swu-game
    swu_game = here.parents[3]
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.append(swu_game / "data" / "swu.db")
    out.append(swu_game.parent / "data" / "swu.db")
    return out


@lru_cache(maxsize=1)
def db_path() -> Path:
    for c in _candidates():
        if c.exists():
            return c
    # Fall back to the conventional location even if missing, so the error
    # message points somewhere sensible.
    return _candidates()[-2]


def connect_ro() -> sqlite3.Connection:
    """Open the card database read-only, for the web layer's lookup tables.

    Deliberately *not* a bare ``sqlite3.connect(db_path())``.  ``db_path()``
    falls back to the conventional location even when nothing is there, and
    ``sqlite3.connect`` **creates** a missing file — so on a machine where the
    card database has not been built yet, the two together silently produce an
    empty ``data/swu.db``.  That turns a clear "you haven't built the card
    database" into ``no such table: cards`` surfacing somewhere much further
    away, and leaves the empty file behind to confuse the next run.

    Raising here instead keeps the failure at the cause, and ``mode=ro`` means
    this path can never create a database even if the check races.
    """
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Card database not found at {path}. Build it with "
            "`python -m swu.pipeline run` — see docs/pipeline.md."
        )
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


@lru_cache(maxsize=1)
def data_dir() -> Path:
    return db_path().parent


def resolve_image(rel_path: str | None) -> Path | None:
    """Turn a DB-stored relative image path into an absolute file path.

    DB paths use Windows separators (``images\\SOR\\5_front.png``); normalise
    them so this works on any platform.
    """
    if not rel_path:
        return None
    norm = rel_path.replace("\\", "/")
    p = (data_dir() / norm).resolve()
    # Containment guard — never serve outside the data dir.
    try:
        p.relative_to(data_dir().resolve())
    except ValueError:
        return None
    return p if p.exists() else None
