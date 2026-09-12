"""
Card-image resolution by the engine's card id.

`CardView.card_id` is the DB primary key (unique across all cards), so the image
endpoint keys on it directly — this avoids the (set, number) collision where a
Leader and its Token share a card_number.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from swu.web.paths import connect_ro, resolve_image


@lru_cache(maxsize=1)
def _image_index() -> dict[int, tuple[str | None, str | None]]:
    """Map DB card id -> (front_rel_path, back_rel_path)."""
    con = connect_ro()
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, image_front_path, image_back_path FROM cards"
        ).fetchall()
    finally:
        con.close()
    return {r["id"]: (r["image_front_path"], r["image_back_path"]) for r in rows}


@lru_cache(maxsize=1)
def _variant_index() -> dict[int, dict[str, tuple[str | None, str | None]]]:
    """Map base card id -> {variant_type: (front_rel_path, back_rel_path)}.

    Purely cosmetic alternate art (hyperspace / hyperspace_foil / showcase).  The
    engine never consults this; only the image endpoint and serializer do.  An
    absent or path-less variant simply doesn't appear, so the caller falls back
    to the standard art.
    """
    con = connect_ro()
    con.row_factory = sqlite3.Row
    try:
        has_table = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='card_variants'"
        ).fetchone()
        if not has_table:
            return {}
        rows = con.execute(
            "SELECT base_card_id, variant_type, image_front_path, image_back_path "
            "FROM card_variants"
        ).fetchall()
    finally:
        con.close()
    out: dict[int, dict[str, tuple[str | None, str | None]]] = {}
    for r in rows:
        # Only surface a variant that has at least a front image downloaded.
        if not r["image_front_path"]:
            continue
        out.setdefault(r["base_card_id"], {})[r["variant_type"]] = (
            r["image_front_path"],
            r["image_back_path"],
        )
    return out


def image_file_for_card(
    card_id: int, face: str = "front", variant: str | None = None
) -> Path | None:
    """Resolve a card id + face (+ optional variant) to an absolute image file.

    Falls back to the standard art when the variant — or the requested face of
    it — is not available, so a stale/partial variant request still renders.
    """
    if variant:
        vfaces = _variant_index().get(card_id, {}).get(variant)
        if vfaces is not None:
            front, back = vfaces
            rel = back if face == "back" else front
            if rel:
                return resolve_image(rel)
        # fall through to standard art
    entry = _image_index().get(card_id)
    if entry is None:
        return None
    front, back = entry
    rel = back if face == "back" else front
    return resolve_image(rel)


@lru_cache(maxsize=4096)
def image_version(card_id: int, face: str = "front", variant: str | None = None) -> int | None:
    """A cache-busting version token for a card image = the file's mtime (int).

    The image endpoint sends ``Cache-Control: immutable``, so a browser (notably
    iPad Safari) keeps serving whatever art it first cached for a given URL —
    even after the id-based collision fix rewrote *what art* that URL returns.
    Appending ``?v=<mtime>`` to the image URL changes the URL string whenever the
    underlying file changes, so corrected art is never served stale.  Cached for
    the process lifetime (files don't change under a running server; a deploy
    restarts it).  Returns None when the file can't be resolved.
    """
    path = image_file_for_card(card_id, face, variant)
    if path is None:
        return None
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return None


def has_back(card_id: int) -> bool:
    entry = _image_index().get(card_id)
    return bool(entry and entry[1])


def variants_for_card(card_id: int) -> dict[str, dict[str, bool]]:
    """Available variant art for a card: {variant_type: {"front": bool, "back": bool}}.

    Empty for cards with no downloaded variants.  Used by the serializer to tell
    the frontend which alternate printings exist.
    """
    out: dict[str, dict[str, bool]] = {}
    for vtype, (front, back) in _variant_index().get(card_id, {}).items():
        out[vtype] = {"front": bool(front), "back": bool(back)}
    return out
