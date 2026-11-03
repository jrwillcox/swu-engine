"""
Phase 2a — parse raw page JSON into SQLite.

Usage:
    python scripts/build_db.py                 # full rebuild (drops & rebuilds cards)
    python scripts/build_db.py --variants-only  # SAFE: only (re)build the card_variants
                                                # table in the EXISTING db; never drops
                                                # the cards table or its image paths

Full run is idempotent: drops and rebuilds swu.db from data/raw/pages/*.json each
run, then populates card_variants from data/raw/variant_pages/*.json.
Requires data/raw/manifest.json (proof of complete harvest).

--variants-only opens the existing swu.db, creates card_variants if needed, and
upserts variant rows while PRESERVING any image paths already filled in — leaving
the cards table and base image paths completely untouched.  This is the
recommended path for adding art variants to an existing, fully-worked database.
"""

import argparse
import json
import logging
import logging.handlers
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
PAGES_DIR = DATA_RAW / "pages"
MANIFEST_PATH = DATA_RAW / "manifest.json"
VARIANT_PAGES_DIR = DATA_RAW / "variant_pages"
DB_PATH = ROOT / "data" / "swu.db"
LOG_PATH = ROOT / "data" / "pipeline.log"

# Art-variant types we store (the user-requested ones), keyed by the upstream
# `variantTypes` relation NAME (authoritative; the boolean flags are unreliable
# across sets).  Everything else (Standard Foil, Prestige, Weekly Play, promos…)
# is intentionally ignored.
VARIANT_TYPE_MAP = {
    "Hyperspace": "hyperspace",
    "Hyperspace Foil": "hyperspace_foil",
    "Showcase": "showcase",
}

def _configure_logging() -> None:
    """Console + rotating-file logging.  Called from run()/main(), never on import.

    Creating data/ and opening a log file are side effects no caller asks for by
    importing this module -- and an eagerly-created data/ is what allowed an
    empty swu.db to appear on machines that have not built the card database.
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.RotatingFileHandler(
                LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            ),
        ],
    )

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id               INTEGER PRIMARY KEY,
    card_uid         TEXT,
    set_code         TEXT,
    set_name         TEXT,
    card_number      TEXT,
    name             TEXT NOT NULL,
    subtitle         TEXT,
    type             TEXT NOT NULL,
    rarity           TEXT,
    cost             INTEGER,
    power            INTEGER,
    hp               INTEGER,
    upgrade_power    INTEGER,
    upgrade_hp       INTEGER,
    text             TEXT,
    text_styled      TEXT,
    rules            TEXT,
    rules_styled     TEXT,
    deploy_box       TEXT,
    epic_action      TEXT,
    is_unique        INTEGER,
    artist           TEXT,
    image_front_url  TEXT,
    image_back_url   TEXT,
    image_front_path TEXT,
    image_back_path  TEXT,
    raw_json         TEXT
);

CREATE TABLE IF NOT EXISTS card_aspects (
    card_id      INTEGER REFERENCES cards(id),
    position     INTEGER,
    name         TEXT,
    color        TEXT,
    is_duplicate INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS card_keywords (
    card_id INTEGER REFERENCES cards(id),
    name    TEXT
);

CREATE TABLE IF NOT EXISTS card_traits (
    card_id INTEGER REFERENCES cards(id),
    name    TEXT
);

CREATE TABLE IF NOT EXISTS card_arenas (
    card_id INTEGER REFERENCES cards(id),
    name    TEXT
);

CREATE INDEX IF NOT EXISTS idx_cards_type           ON cards(type);
CREATE INDEX IF NOT EXISTS idx_cards_set_number     ON cards(set_code, card_number);
CREATE INDEX IF NOT EXISTS idx_cards_name           ON cards(name);
"""

# Art variants live in their own additive table linked to cards(id).  The engine
# never reads this table — it is purely cosmetic art shown by the web UI.
VARIANTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS card_variants (
    base_card_id     INTEGER REFERENCES cards(id),
    variant_type     TEXT,    -- 'hyperspace' | 'hyperspace_foil' | 'showcase'
    variant_card_id  INTEGER, -- the variant's own Strapi id
    set_code         TEXT,
    card_number      TEXT,
    image_front_url  TEXT,
    image_back_url   TEXT,
    image_front_path TEXT,
    image_back_path  TEXT,
    PRIMARY KEY (base_card_id, variant_type)
);

CREATE INDEX IF NOT EXISTS idx_variants_base ON card_variants(base_card_id);
"""


def _dig(obj: dict, *keys, default=None):
    """Safe nested key access."""
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k, default)
        if obj is None:
            return default
    return obj


def _rel_names(attrs: dict, field: str) -> list[str]:
    """Extract list of names from a Strapi relation list field."""
    items = _dig(attrs, field, "data") or []
    return [_dig(item, "attributes", "name") for item in items if _dig(item, "attributes", "name")]


def _art_url(art_obj) -> str | None:
    """Pull the best URL from an artFront/artBack attribute object."""
    if not art_obj:
        return None
    data = art_obj.get("data")
    if not data:
        return None
    a = data.get("attributes", {}) if isinstance(data, dict) else {}
    url = a.get("url") or _dig(a, "formats", "card", "url")
    if url and url.startswith("/"):
        url = "https://admin.starwarsunlimited.com" + url
    return url


def parse_card(raw: dict) -> dict | None:
    """Convert a raw Strapi card object to a flat dict ready for DB insertion."""
    card_id = raw.get("id")
    attrs = raw.get("attributes", {})

    type_name = _dig(attrs, "type", "data", "attributes", "name")
    if not type_name:
        log.warning("Card id=%s has no type, skipping", card_id)
        return None

    name = attrs.get("title") or attrs.get("name") or ""
    if not name:
        log.warning("Card id=%s has no name, skipping", card_id)
        return None

    exp = _dig(attrs, "expansion", "data", "attributes") or {}
    rarity = _dig(attrs, "rarity", "data", "attributes", "name")

    # Aspects (ordered list + duplicate check)
    aspects_raw = _dig(attrs, "aspects", "data") or []
    aspects_dup_raw = _dig(attrs, "aspectDuplicates", "data") or []
    dup_names = {_dig(a, "attributes", "name") for a in aspects_dup_raw}
    aspects = []
    for pos, item in enumerate(aspects_raw):
        a_name = _dig(item, "attributes", "name")
        a_color = _dig(item, "attributes", "color")
        aspects.append({
            "position": pos,
            "name": a_name,
            "color": a_color,
            "is_duplicate": 1 if a_name in dup_names else 0,
        })

    # Token Upgrades store their stat modifiers in power/hp (not upgradePower/upgradeHp).
    # Regular Upgrades do the opposite. Normalise to upgrade_power/upgrade_hp in both cases.
    raw_upgrade_power = attrs.get("upgradePower")
    raw_upgrade_hp = attrs.get("upgradeHp")
    if type_name == "Token Upgrade" and raw_upgrade_power is None:
        raw_upgrade_power = attrs.get("power")
        raw_upgrade_hp = attrs.get("hp")

    # For Token Upgrades, power/hp now live in upgrade_power/upgrade_hp above,
    # so store None in the unit-stat columns.
    raw_power = None if type_name == "Token Upgrade" else attrs.get("power")
    raw_hp = None if type_name == "Token Upgrade" else attrs.get("hp")

    return {
        "id": card_id,
        "card_uid": attrs.get("cardUid") or attrs.get("serialCode"),
        "set_code": exp.get("code"),
        "set_name": exp.get("name"),
        "card_number": str(attrs.get("cardNumber") or ""),
        "name": name,
        "subtitle": attrs.get("subtitle"),
        "type": type_name,
        "rarity": rarity,
        "cost": attrs.get("cost"),
        "power": raw_power,
        "hp": raw_hp,
        "upgrade_power": raw_upgrade_power,
        "upgrade_hp": raw_upgrade_hp,
        "text": attrs.get("text"),
        "text_styled": attrs.get("textStyled"),
        "rules": attrs.get("rules"),
        "rules_styled": attrs.get("rulesStyled"),
        "deploy_box": attrs.get("deployBox"),
        "epic_action": attrs.get("epicAction"),
        "is_unique": 1 if attrs.get("unique") else 0,
        "artist": attrs.get("artist"),
        "image_front_url": _art_url(attrs.get("artFront")),
        "image_back_url": _art_url(attrs.get("artBack")),
        "image_front_path": None,
        "image_back_path": None,
        "raw_json": json.dumps(attrs, ensure_ascii=False),
        "_aspects": aspects,
        "_keywords": _rel_names(attrs, "keywords"),
        "_traits": _rel_names(attrs, "traits"),
        "_arenas": _rel_names(attrs, "arenas"),
    }


TOKEN_TYPES = {"Token Unit", "Token Upgrade", "Credit Token", "Force Token"}


def _build_variants(con) -> int:
    """Populate card_variants from data/raw/variant_pages/*.json.

    Additive and idempotent: creates the table if needed and upserts one row per
    (base_card_id, variant_type), PRESERVING any image_*_path already filled in
    (so re-running after fetch_images does not wipe downloaded-image paths).
    Returns the number of variant rows written.  Never touches the cards table.
    """
    con.executescript(VARIANTS_SCHEMA)

    page_files = sorted(VARIANT_PAGES_DIR.glob("page_*.json"))
    if not page_files:
        log.warning(
            "No variant page files in %s — run fetch_metadata.py --variants first",
            VARIANT_PAGES_DIR,
        )
        return 0

    # Resolve a variant to its base card id.  Prefer the direct variantOf.id link
    # (a cards.id); fall back to (set_code, card_number) of the base, preferring a
    # non-token row (a Leader and its Token share a card_number — see docs/encoding_guide.md).
    existing_ids: set[int] = {r[0] for r in con.execute("SELECT id FROM cards")}
    by_set_number: dict[tuple[str, str], tuple[int, bool]] = {}  # key -> (id, is_token)
    for cid, set_code, number, type_name in con.execute(
        "SELECT id, set_code, card_number, type FROM cards"
    ):
        key = (set_code, str(number))
        is_token = type_name in TOKEN_TYPES
        # Keep the first row seen, but let a non-token row replace a token one.
        if key not in by_set_number or (by_set_number[key][1] and not is_token):
            by_set_number[key] = (cid, is_token)

    written = 0
    unresolved = 0
    for pf in page_files:
        with open(pf, encoding="utf-8") as f:
            page_data = json.load(f)
        for raw in page_data.get("data", []):
            attrs = raw.get("attributes", {})
            names = _rel_names(attrs, "variantTypes")
            variant_type = next(
                (VARIANT_TYPE_MAP[n] for n in names if n in VARIANT_TYPE_MAP), None
            )
            if variant_type is None:
                continue  # not one of the three art variants we keep

            base = _dig(attrs, "variantOf", "data") or {}
            base_id = base.get("id") if isinstance(base, dict) else None
            if base_id not in existing_ids:
                base_attrs = base.get("attributes", {}) if isinstance(base, dict) else {}
                base_num = str(base_attrs.get("cardNumber") or "")
                set_code = _dig(attrs, "expansion", "data", "attributes", "code")
                hit = by_set_number.get((set_code, base_num))
                base_id = hit[0] if hit else None
            if base_id is None:
                unresolved += 1
                continue

            row = {
                "base_card_id": base_id,
                "variant_type": variant_type,
                "variant_card_id": raw.get("id"),
                "set_code": _dig(attrs, "expansion", "data", "attributes", "code"),
                "card_number": str(attrs.get("cardNumber") or ""),
                "image_front_url": _art_url(attrs.get("artFront")),
                "image_back_url": _art_url(attrs.get("artBack")),
            }
            con.execute(
                """INSERT INTO card_variants (
                       base_card_id, variant_type, variant_card_id, set_code,
                       card_number, image_front_url, image_back_url,
                       image_front_path, image_back_path
                   ) VALUES (
                       :base_card_id, :variant_type, :variant_card_id, :set_code,
                       :card_number, :image_front_url, :image_back_url, NULL, NULL
                   )
                   ON CONFLICT(base_card_id, variant_type) DO UPDATE SET
                       variant_card_id = excluded.variant_card_id,
                       set_code        = excluded.set_code,
                       card_number     = excluded.card_number,
                       image_front_url = excluded.image_front_url,
                       image_back_url  = excluded.image_back_url
                   -- image_*_path deliberately preserved across re-runs
                """,
                row,
            )
            written += 1

    con.commit()
    log.info("card_variants populated: %d rows (%d unresolved bases)", written, unresolved)
    counts = con.execute(
        "SELECT variant_type, COUNT(*) FROM card_variants GROUP BY variant_type ORDER BY variant_type"
    ).fetchall()
    for vt, n in counts:
        log.info("  %-18s %d", vt, n)
    return written


def run_variants_only() -> None:
    """SAFE path: add/refresh card_variants in the EXISTING db; never drop cards."""
    import sqlite3

    if not DB_PATH.exists():
        log.error("No db at %s — run a full build_db.py first", DB_PATH)
        sys.exit(1)

    log.info("--variants-only: updating card_variants in %s (cards untouched)", DB_PATH)
    con = sqlite3.connect(DB_PATH)
    try:
        _build_variants(con)
    finally:
        con.close()


def run() -> None:
    _configure_logging()
    import sqlite3

    if not MANIFEST_PATH.exists():
        log.error("No manifest found at %s — run fetch_metadata.py first", MANIFEST_PATH)
        sys.exit(1)

    page_files = sorted(PAGES_DIR.glob("page_*.json"))
    if not page_files:
        log.error("No page files in %s", PAGES_DIR)
        sys.exit(1)

    log.info("Building DB from %d page files...", len(page_files))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)

    inserted = 0
    skipped = 0

    for pf in page_files:
        with open(pf, encoding="utf-8") as f:
            page_data = json.load(f)
        for raw in page_data.get("data", []):
            card = parse_card(raw)
            if card is None:
                skipped += 1
                continue

            aspects = card.pop("_aspects")
            keywords = card.pop("_keywords")
            traits = card.pop("_traits")
            arenas = card.pop("_arenas")

            con.execute(
                """INSERT INTO cards VALUES (
                    :id, :card_uid, :set_code, :set_name, :card_number,
                    :name, :subtitle, :type, :rarity,
                    :cost, :power, :hp, :upgrade_power, :upgrade_hp,
                    :text, :text_styled, :rules, :rules_styled,
                    :deploy_box, :epic_action,
                    :is_unique, :artist,
                    :image_front_url, :image_back_url,
                    :image_front_path, :image_back_path,
                    :raw_json
                )""",
                card,
            )
            cid = card["id"]
            for asp in aspects:
                con.execute(
                    "INSERT INTO card_aspects VALUES (?,?,?,?,?)",
                    (cid, asp["position"], asp["name"], asp["color"], asp["is_duplicate"]),
                )
            for kw in keywords:
                con.execute("INSERT INTO card_keywords VALUES (?,?)", (cid, kw))
            for tr in traits:
                con.execute("INSERT INTO card_traits VALUES (?,?)", (cid, tr))
            for ar in arenas:
                con.execute("INSERT INTO card_arenas VALUES (?,?)", (cid, ar))

            inserted += 1

    # Populate art variants into the same fresh DB (additive, separate table).
    _build_variants(con)

    con.commit()
    con.close()

    log.info("DB built: %d cards inserted, %d skipped. Path: %s", inserted, skipped, DB_PATH)

    # Quick type summary
    con2 = sqlite3.connect(DB_PATH)
    rows = con2.execute("SELECT type, COUNT(*) FROM cards GROUP BY type ORDER BY type").fetchall()
    con2.close()
    log.info("Card counts by type:")
    for type_name, count in rows:
        log.info("  %-20s %d", type_name, count)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Build swu.db from raw page JSON")
    parser.add_argument(
        "--variants-only",
        action="store_true",
        help="Only (re)build card_variants in the existing db; never drop the cards table",
    )
    args = parser.parse_args()
    if args.variants_only:
        run_variants_only()
    else:
        run()


if __name__ == "__main__":
    main()
