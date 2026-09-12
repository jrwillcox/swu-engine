"""
Tests for scripts/audit_images.py.

Builds synthetic DBs + on-disk image trees under tmp_path (no network, no real
DB) and asserts the audit flags a deliberate collision / missing file, passes a
clean DB, and resolves the Leader-vs-Token (set, number) collision group and
Ahsoka's Padawan Lightsaber (TWI_248) to the right ids/paths.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.audit_images import audit_images

_SCHEMA = """
CREATE TABLE cards (
    id INTEGER PRIMARY KEY,
    set_code TEXT,
    card_number TEXT,
    name TEXT,
    type TEXT,
    image_front_path TEXT,
    image_back_path TEXT
);
"""


def _write_image(data_dir: Path, rel: str) -> None:
    p = data_dir / rel.replace("\\", "/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)


def _make_db(data_dir: Path, rows: list[tuple]) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    db = data_dir / "swu.db"
    con = sqlite3.connect(str(db))
    con.executescript(_SCHEMA)
    con.executemany(
        "INSERT INTO cards (id, set_code, card_number, name, type, "
        "image_front_path, image_back_path) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    con.close()
    return db


def _clean_rows() -> list[tuple]:
    # A Leader and a Token sharing (SOR, 4) — id-based, distinct files (the fix).
    # Ahsoka's Padawan Lightsaber TWI_248 (Upgrade) + a token sharing its number.
    return [
        (100, "SOR", "4", "Iden Versio", "Leader", "images/SOR/4_100_front.png", "images/SOR/4_100_back.png"),
        (101, "SOR", "4", "Shield", "Token Upgrade", "images/SOR/4_101_front.png", None),
        (15601, "TWI", "248", "Ahsoka's Padawan Lightsaber", "Upgrade", "images/TWI/248_front.png", None),
        (14030, "TWI", "1", "Battle Droid", "Token Unit", "images/TWI/1_14030_front.png", None),
        (200, "SOR", "50", "Vanilla Unit", "Unit", "images/SOR/50_front.png", None),
    ]


def _make_clean(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    rows = _clean_rows()
    for _id, _s, _n, _nm, _t, front, back in rows:
        if front:
            _write_image(data_dir, front)
        if back:
            _write_image(data_dir, back)
    return _make_db(data_dir, rows)


def test_clean_db_passes(tmp_path):
    db = _make_clean(tmp_path)
    audit = audit_images(db, db.parent)
    assert audit.ok
    assert audit.collisions == []
    assert audit.missing == []
    assert audit.stale == []
    assert audit.group_issues == []
    # Two (set, number) collision groups: (SOR,4) and (TWI,1 has one member -> no).
    assert audit.groups_checked == 1  # only (SOR, 4) has >1 member


def test_collision_flagged(tmp_path):
    """Two ids pointing at the same physical file is a collision (non-zero gate)."""
    data_dir = tmp_path / "data"
    shared = "images/SOR/4_front.png"
    _write_image(data_dir, shared)
    rows = [
        (100, "SOR", "4", "Iden Versio", "Leader", shared, None),
        (101, "SOR", "4", "Shield", "Token Upgrade", shared, None),
    ]
    db = _make_db(data_dir, rows)
    audit = audit_images(db, db.parent)
    assert not audit.ok
    assert len(audit.collisions) == 1
    path, ids = audit.collisions[0]
    assert path == shared
    assert ids == [100, 101]
    # The group check also flags the shared image within the (SOR, 4) group.
    assert any("share" in issue for issue in audit.group_issues)


def test_missing_file_flagged(tmp_path):
    data_dir = tmp_path / "data"
    rows = [
        (200, "SOR", "50", "Vanilla Unit", "Unit", "images/SOR/50_front.png", None),
    ]
    db = _make_db(data_dir, rows)  # note: no file written
    audit = audit_images(db, db.parent)
    assert not audit.ok
    assert audit.missing == [(200, "front", "images/SOR/50_front.png")]


def test_stale_file_flagged_but_not_fatal(tmp_path):
    """An unreferenced on-disk image is informational (stale), not a gate failure."""
    db = _make_clean(tmp_path)
    # Drop an old number-only scheme leftover no card references.
    _write_image(db.parent, "images/SOR/1_front.png")
    audit = audit_images(db, db.parent)
    assert audit.ok  # stale does not fail the gate
    normalised = {s.replace("\\", "/") for s in audit.stale}
    assert "images/SOR/1_front.png" in normalised


def test_twi248_and_token_resolve_to_right_paths(tmp_path):
    """The named bug card TWI_248 resolves to the TWI upgrade art, tokens to theirs."""
    db = _make_clean(tmp_path)
    audit = audit_images(db, db.parent)
    # No group issue mentioning the Ahsoka lightsaber, and it is a distinct id/path.
    assert not any("248" in issue for issue in audit.group_issues)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    ahsoka = con.execute(
        "SELECT id, type, image_front_path FROM cards WHERE set_code='TWI' AND card_number='248'"
    ).fetchall()
    con.close()
    assert len(ahsoka) == 1
    assert ahsoka[0]["type"] == "Upgrade"
    assert ahsoka[0]["image_front_path"] == "images/TWI/248_front.png"
    assert (db.parent / "images/TWI/248_front.png").exists()


def test_missing_ahsoka_lightsaber_reported(tmp_path):
    """If TWI_248's non-token row is absent, the dedicated check says so."""
    data_dir = tmp_path / "data"
    rows = [
        (14030, "TWI", "1", "Battle Droid", "Token Unit", "images/TWI/1_14030_front.png", None),
    ]
    _write_image(data_dir, "images/TWI/1_14030_front.png")
    db = _make_db(data_dir, rows)
    audit = audit_images(db, db.parent)
    assert any("Ahsoka" in issue for issue in audit.group_issues)
