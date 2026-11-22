"""The planet printed on every Base card — HAND-MAINTAINED data.

Cards such as "If you control a Naboo base" (Homeworlds) ask which planet a base
is on, but the official card API carries no planet field for bases: their traits
are empty, they have no subtitle, and ``raw_json`` never names it.  The planet is
printed only on the card ART, in the italic band under the illustration.  This
table was read from the stored base images (``cards.image_front_path``,
``type='Base'``) on 2026-11-22.

It lives in the repo, NOT in ``data/swu.db``, so a re-harvest can never wipe it.
``tests/test_base_planets.py`` fails when the card DB holds a base this table
does not cover — so a new release with new bases has to be read and added here
(see ``docs/dev/new_releases.md``).

Values are the printed name in title case.  A few printed "planets" are really
locations (Death Star, Cloud City, Starkiller Base, Starlight Beacon); they are
stored exactly as printed.  Keyed by ``(set_code, card_number)``: lookups are only
ever made for ``Base`` cards, and no two bases share a number, so the key is
unambiguous here (it is NOT unique across card types — leaders share numbers with
tokens).
"""
from __future__ import annotations

from typing import Any, Optional

BASE_PLANETS: dict[tuple[str, str], str] = {
    # ASH — Ashes of the Empire
    ("ASH", "19"): "Peridea",
    ("ASH", "20"): "Nevarro",
    ("ASH", "21"): "Death Star",
    ("ASH", "22"): "Kalevala",
    ("ASH", "23"): "Seatos",
    ("ASH", "24"): "Dagobah",
    ("ASH", "25"): "Pillio",
    ("ASH", "26"): "Tatooine",
    # GG
    ("GG", "1"): "Dagobah",
    ("GG", "2"): "Hoth",
    ("GG", "3"): "Jedha",
    ("GG", "4"): "Tatooine",
    # HMW — Homeworlds
    ("HMW", "19"): "Tatooine",
    ("HMW", "20"): "Naboo",
    ("HMW", "21"): "Kashyyyk",
    ("HMW", "22"): "Endor",
    ("HMW", "23"): "Endor",
    ("HMW", "24"): "Kashyyyk",
    ("HMW", "25"): "Naboo",
    ("HMW", "26"): "Tatooine",
    ("HMW", "27"): "Naboo",
    ("HMW", "28"): "Tatooine",
    ("HMW", "29"): "Endor",
    ("HMW", "30"): "Kashyyyk",
    ("HMW", "31"): "Kashyyyk",
    ("HMW", "32"): "Tatooine",
    ("HMW", "33"): "Naboo",
    ("HMW", "34"): "Endor",
    # IBH
    ("IBH", "2"): "Hoth",
    ("IBH", "54"): "Hoth",
    # IC27 — Icons 2027
    ("IC27", "9"): "Cloud City",
    ("IC27", "10"): "Hoth",
    ("IC27", "11"): "Mustafar",
    ("IC27", "12"): "Tatooine",
    # JTL — Jump to Lightspeed
    ("JTL", "19"): "Cloud City",
    ("JTL", "20"): "Endor",
    ("JTL", "21"): "Castilon",
    ("JTL", "22"): "D'Qar",
    ("JTL", "23"): "Naboo",
    ("JTL", "24"): "Scarif",
    ("JTL", "25"): "Starkiller Base",
    ("JTL", "26"): "Yavin 4",
    ("JTL", "27"): "Nadiri",
    ("JTL", "28"): "Ryloth",
    ("JTL", "29"): "Atollon",
    ("JTL", "30"): "Tatooine",
    ("JTL", "31"): "Naboo",
    # LAW — A Lawless Time
    ("LAW", "19"): "Lowick",
    ("LAW", "20"): "Tatooine",
    ("LAW", "21"): "Kessel",
    ("LAW", "22"): "Aldhani",
    ("LAW", "23"): "Tatooine",
    ("LAW", "24"): "Lothal",
    ("LAW", "25"): "Quarzite",
    ("LAW", "26"): "Bracca",
    ("LAW", "27"): "Stygeon Prime",
    ("LAW", "28"): "Cantonica",
    ("LAW", "29"): "Scarif",
    ("LAW", "30"): "Segra Milo",
    # LOF — Legends of the Force
    ("LOF", "19"): "Lothal",
    ("LOF", "20"): "Dathomir",
    ("LOF", "21"): "Coruscant",
    ("LOF", "22"): "Mortis",
    ("LOF", "23"): "Coruscant",
    ("LOF", "24"): "Starlight Beacon",
    ("LOF", "25"): "Malachor",
    ("LOF", "26"): "Mustafar",
    ("LOF", "27"): "Dathomir",
    ("LOF", "28"): "Zeffo",
    ("LOF", "29"): "Ilum",
    ("LOF", "30"): "Jedha",
    # P25 / P26 — promos
    ("P25", "97"): "Endor",
    ("P25", "98"): "Naboo",
    ("P25", "99"): "Yavin 4",
    ("P25", "100"): "Tatooine",
    ("P26", "129"): "Tatooine",
    ("P26", "130"): "Lothal",
    ("P26", "131"): "Stygeon Prime",
    ("P26", "132"): "Cantonica",
    # SEC — Secrets of Power
    ("SEC", "19"): "Ferrix",
    ("SEC", "20"): "Coruscant",
    ("SEC", "21"): "Hosnian Prime",
    ("SEC", "22"): "Coruscant",
    ("SEC", "23"): "Narkina 5",
    ("SEC", "24"): "Coruscant",
    ("SEC", "25"): "Coruscant",
    ("SEC", "26"): "Wayland",
    # SHD — Shadows of the Galaxy
    ("SHD", "19"): "Nevarro",
    ("SHD", "20"): "Sorgan",
    ("SHD", "21"): "Takodana",
    ("SHD", "22"): "Nevarro",
    ("SHD", "23"): "Concordia",
    ("SHD", "24"): "Kessel",
    ("SHD", "25"): "Corellia",
    ("SHD", "26"): "Tatooine",
    # SOR — Spark of Rebellion
    ("SOR", "19"): "Scarif",
    ("SOR", "20"): "Lothal",
    ("SOR", "21"): "Dagobah",
    ("SOR", "22"): "Eadu",
    ("SOR", "23"): "Death Star",
    ("SOR", "24"): "Hoth",
    ("SOR", "25"): "Lothal",
    ("SOR", "26"): "Jedha",
    ("SOR", "27"): "Vardos",
    ("SOR", "28"): "Jedha",
    ("SOR", "29"): "Cloud City",
    ("SOR", "30"): "Atollon",
    # TS26 — 2026 two-player starter
    ("TS26", "9"): "Coruscant",
    ("TS26", "10"): "Serenno",
    ("TS26", "11"): "Geonosis",
    ("TS26", "12"): "Mandalore",
    # TWI — Twilight of the Republic
    ("TWI", "19"): "Utapau",
    ("TWI", "20"): "Mandalore",
    ("TWI", "21"): "Christophsis",
    ("TWI", "22"): "Geonosis",
    ("TWI", "23"): "Vassek",
    ("TWI", "24"): "Kamino",
    ("TWI", "25"): "Zanbar",
    ("TWI", "26"): "Mustafar",
    ("TWI", "27"): "Onderon",
    ("TWI", "28"): "Geonosis",
    ("TWI", "29"): "Coruscant",
    ("TWI", "30"): "Oba Diah",
}


def base_planet(card_def: Any) -> Optional[str]:
    """The planet printed on a Base card, or None for any other card (or a base
    missing from the table — the guard test keeps that from happening silently)."""
    from swu.cards.models import Base
    if not isinstance(card_def, Base):
        return None
    return BASE_PLANETS.get((card_def.set_code or "", card_def.card_number))


def controls_planet_base(ps: Any, planets: Any) -> bool:
    """True when player ``ps`` controls a base on one of ``planets`` (a single
    name or a tuple of names)."""
    wanted = (planets,) if isinstance(planets, str) else tuple(planets or ())
    base = getattr(ps, "base_instance", None)
    return base is not None and base_planet(base.card_def) in wanted
