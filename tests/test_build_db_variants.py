"""
Unit test for build_db's variant parsing (_build_variants).

Exercises the additive card_variants population in isolation: a synthetic
variant page is linked to a base card, classified by its variantTypes name, and
re-running preserves any downloaded image paths.  No network, no real DB.
"""
from __future__ import annotations

import json
import sqlite3

import scripts.build_db as bd


def _make_cards_db(con: sqlite3.Connection) -> None:
    con.executescript(bd.SCHEMA)
    # One base unit (Strapi id 389, SOR/12) + a token sharing the number 12.
    con.execute(
        "INSERT INTO cards (id, set_code, card_number, name, type) VALUES "
        "(389, 'SOR', '12', 'IG-88', 'Unit')"
    )
    con.execute(
        "INSERT INTO cards (id, set_code, card_number, name, type) VALUES "
        "(390, 'SOR', '12', 'IG-88 Token', 'Token Unit')"
    )
    con.commit()


def _variant_card(*, vid, base_id, base_num, set_code, number, variant_name, front, back):
    return {
        "id": vid,
        "attributes": {
            "cardNumber": number,
            "expansion": {"data": {"attributes": {"code": set_code}}},
            "variantOf": {"data": {"id": base_id, "attributes": {"cardNumber": base_num}}},
            "variantTypes": {"data": [{"attributes": {"name": variant_name}}]},
            "artFront": {"data": {"attributes": {"url": front}}},
            "artBack": {"data": {"attributes": {"url": back}}} if back else {"data": None},
        },
    }


def test_build_variants_links_classifies_and_preserves_paths(tmp_path, monkeypatch):
    pages = tmp_path / "variant_pages"
    pages.mkdir()
    page = {
        "data": [
            _variant_card(vid=964, base_id=389, base_num=12, set_code="SOR",
                          number=278, variant_name="Hyperspace",
                          front="https://x/ig88_hyp.png", back="https://x/ig88_hyp_b.png"),
            _variant_card(vid=965, base_id=389, base_num=12, set_code="SOR",
                          number=500, variant_name="Showcase",
                          front="https://x/ig88_sc.png", back=None),
            # An ignored variant type (not one of the three we keep).
            _variant_card(vid=966, base_id=389, base_num=12, set_code="SOR",
                          number=600, variant_name="Standard Foil",
                          front="https://x/ig88_foil.png", back=None),
            # Base resolved by (set, number) fallback (variantOf.id unknown).
            _variant_card(vid=967, base_id=99999, base_num=12, set_code="SOR",
                          number=700, variant_name="Hyperspace Foil",
                          front="https://x/ig88_hypfoil.png", back=None),
        ]
    }
    (pages / "page_0001.json").write_text(json.dumps(page), encoding="utf-8")
    monkeypatch.setattr(bd, "VARIANT_PAGES_DIR", pages)

    con = sqlite3.connect(":memory:")
    _make_cards_db(con)

    written = bd._build_variants(con)
    assert written == 3  # Standard Foil ignored

    rows = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT variant_type, base_card_id, image_back_url FROM card_variants"
        )
    }
    assert set(rows) == {"hyperspace", "showcase", "hyperspace_foil"}
    # All three resolve to the non-token base row (id 389), incl. the (set,number) fallback.
    assert rows["hyperspace"][0] == 389
    assert rows["hyperspace_foil"][0] == 389  # resolved via fallback
    assert rows["hyperspace"][1] == "https://x/ig88_hyp_b.png"  # back url captured
    assert rows["showcase"][1] is None  # no back

    # Image paths are NULL until fetch_images runs.
    assert con.execute(
        "SELECT image_front_path FROM card_variants WHERE variant_type='hyperspace'"
    ).fetchone()[0] is None

    # Simulate fetch_images filling a path, then a re-run of _build_variants:
    # the path must be PRESERVED (urls may refresh, local files must not be lost).
    con.execute(
        "UPDATE card_variants SET image_front_path='images/variants/SOR/278_hyperspace_front.png' "
        "WHERE variant_type='hyperspace'"
    )
    con.commit()
    bd._build_variants(con)
    assert con.execute(
        "SELECT image_front_path FROM card_variants WHERE variant_type='hyperspace'"
    ).fetchone()[0] == "images/variants/SOR/278_hyperspace_front.png"

    con.close()
