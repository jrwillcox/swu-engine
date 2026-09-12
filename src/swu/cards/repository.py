"""
Query layer — loads cards from swu.db into typed model objects.

Usage:
    repo = CardRepository("data/swu.db")
    darth = repo.by_name("Darth Vader")
    sor_units = repo.by_set("SOR", card_type="Unit")
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator, Optional

from swu.cards.models import (
    AnyCard, AspectPip, Base, CreditToken, Event, ForceToken,
    Leader, TokenUnit, TokenUpgrade, Unit, Upgrade,
)
from swu.cards.keyword_sanitizer import sanitize_keywords


class CardRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        if not self._db_path.exists():
            raise FileNotFoundError(f"Database not found: {self._db_path}")

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    def by_id(self, card_id: int) -> Optional[AnyCard]:
        """Return a single card by its Strapi id, or None."""
        with self._con() as con:
            row = con.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            if row is None:
                return None
            return self._hydrate(con, row)

    def by_name(self, name: str) -> list[AnyCard]:
        """Return all cards whose name matches exactly (case-insensitive)."""
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM cards WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchall()
            return [self._hydrate(con, r) for r in rows]

    def by_set(self, set_code: str, card_type: Optional[str] = None) -> list[AnyCard]:
        """Return all cards in a set, optionally filtered by type."""
        with self._con() as con:
            if card_type:
                rows = con.execute(
                    "SELECT * FROM cards WHERE set_code = ? AND type = ? ORDER BY card_number",
                    (set_code, card_type),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM cards WHERE set_code = ? ORDER BY card_number", (set_code,)
                ).fetchall()
            return [self._hydrate(con, r) for r in rows]

    def search(self, query: str) -> list[AnyCard]:
        """Full-text search on name, subtitle, and rules text."""
        pattern = f"%{query}%"
        with self._con() as con:
            rows = con.execute(
                """SELECT * FROM cards
                   WHERE name LIKE ? OR subtitle LIKE ? OR text LIKE ?
                   ORDER BY type, name""",
                (pattern, pattern, pattern),
            ).fetchall()
            return [self._hydrate(con, r) for r in rows]

    def all_of_type(self, card_type: str) -> list[AnyCard]:
        """Return every card of a given type."""
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM cards WHERE type = ? ORDER BY set_code, card_number", (card_type,)
            ).fetchall()
            return [self._hydrate(con, r) for r in rows]

    def iter_all(self) -> Iterator[AnyCard]:
        """Iterate over every card in the database."""
        with self._con() as con:
            rows = con.execute("SELECT * FROM cards ORDER BY id").fetchall()
            for row in rows:
                yield self._hydrate(con, row)

    def sets(self) -> list[tuple[str, str]]:
        """Return (set_code, set_name) pairs for all known sets."""
        with self._con() as con:
            return con.execute(
                "SELECT DISTINCT set_code, set_name FROM cards ORDER BY set_code"
            ).fetchall()

    # ------------------------------------------------------------------
    # Hydration
    # ------------------------------------------------------------------

    def _hydrate(self, con: sqlite3.Connection, row: sqlite3.Row) -> AnyCard:
        aspects = tuple(
            AspectPip(
                position=r["position"],
                name=r["name"],
                color=r["color"],
                is_duplicate=bool(r["is_duplicate"]),
            )
            for r in con.execute(
                "SELECT * FROM card_aspects WHERE card_id = ? ORDER BY position", (row["id"],)
            )
        )
        keywords = tuple(
            r["name"]
            for r in con.execute("SELECT name FROM card_keywords WHERE card_id = ?", (row["id"],))
        )
        # Correct an upstream data quirk: the source data tags some cards with
        # keywords they only *grant to other units* (e.g. Admiral Piett SOR_079
        # with Ambush).  See swu.cards.keyword_sanitizer.
        keywords = sanitize_keywords(
            row["type"], row["text"], keywords,
            set_code=row["set_code"], card_number=row["card_number"],
            deploy_box=row["deploy_box"],
        )
        traits = tuple(
            r["name"]
            for r in con.execute("SELECT name FROM card_traits WHERE card_id = ?", (row["id"],))
        )
        arenas = tuple(
            r["name"]
            for r in con.execute("SELECT name FROM card_arenas WHERE card_id = ?", (row["id"],))
        )

        base_kwargs = dict(
            id=row["id"],
            card_uid=row["card_uid"],
            set_code=row["set_code"],
            set_name=row["set_name"],
            card_number=row["card_number"],
            name=row["name"],
            subtitle=row["subtitle"],
            type=row["type"],
            rarity=row["rarity"],
            is_unique=bool(row["is_unique"]),
            artist=row["artist"],
            text=row["text"],
            text_styled=row["text_styled"],
            rules=row["rules"],
            rules_styled=row["rules_styled"],
            aspects=aspects,
            keywords=keywords,
            traits=traits,
            arenas=arenas,
            image_front_url=row["image_front_url"],
            image_back_url=row["image_back_url"],
            image_front_path=row["image_front_path"],
            image_back_path=row["image_back_path"],
        )

        t = row["type"]

        if t == "Unit":
            return Unit(
                **base_kwargs,
                cost=row["cost"],
                power=row["power"],
                hp=row["hp"],
                upgrade_power=row["upgrade_power"],
                upgrade_hp=row["upgrade_hp"],
                epic_action=row["epic_action"],
            )
        if t == "Leader":
            return Leader(
                **base_kwargs,
                power=row["power"],
                hp=row["hp"],
                deploy_box=row["deploy_box"],
                epic_action=row["epic_action"],
                upgrade_power=row["upgrade_power"],
                upgrade_hp=row["upgrade_hp"],
            )
        if t == "Base":
            return Base(**base_kwargs, hp=row["hp"], epic_action=row["epic_action"])
        if t == "Event":
            return Event(**base_kwargs, cost=row["cost"])
        if t == "Upgrade":
            return Upgrade(
                **base_kwargs,
                cost=row["cost"],
                upgrade_power=row["upgrade_power"],
                upgrade_hp=row["upgrade_hp"],
            )
        if t == "Token Unit":
            return TokenUnit(**base_kwargs, power=row["power"], hp=row["hp"])
        if t == "Token Upgrade":
            return TokenUpgrade(
                **base_kwargs,
                upgrade_power=row["upgrade_power"],
                upgrade_hp=row["upgrade_hp"],
            )
        if t == "Credit Token":
            return CreditToken(**base_kwargs)
        if t == "Force Token":
            return ForceToken(**base_kwargs)
        # Unknown type — return as a generic Unit so the engine doesn't crash
        return Unit(**base_kwargs, cost=row["cost"] or 0, power=row["power"] or 0, hp=row["hp"] or 0)
