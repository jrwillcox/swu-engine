"""
Repair card-image filename collisions.

`(set_code, card_number)` is NOT unique — every Leader (numbered 1, 2, 3, …)
shares its number with a Token reusing that low number (and a few promo Units do
too). `fetch_images.py` historically named files `{number}_{side}.png`, so both
cards in a colliding pair wrote / pointed at the *same* physical file; whichever
was fetched first won, and the other card's DB ``image_*_path`` pointed at the
wrong art (e.g. the Leader "Iden Versio" rendering as a Shield token).

This script gives EVERY card in a colliding group its own id-based image file
(`{number}_{id}_{side}.ext`), downloads the correct art for it, and repoints the
DB. Non-colliding cards are left untouched (their number-based files are already
unique). Idempotent and resumable: an already-correct id-based file is skipped.

Usage:
    python scripts/fix_image_collisions.py [--delay 1.0] [--dry-run]
"""
from __future__ import annotations

import argparse
import mimetypes
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "swu.db"
IMAGES_DIR = ROOT / "data" / "images"
MIN_IMAGE_BYTES = 1024

HEADERS = {
    "Accept": "image/*,*/*",
    "Referer": "https://starwarsunlimited.com/",
    "User-Agent": "swu-home-game/0.1 (personal hobby project)",
}


def _safe(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s or "0")


def _ext(resp: requests.Response, url: str) -> str:
    ct = resp.headers.get("Content-Type", "")
    ext = mimetypes.guess_extension(ct.split(";")[0].strip(), strict=False)
    if ext in (".jpe", ".jpeg"):
        return ".jpg"
    if ext:
        return ext
    return Path(urlparse(url).path).suffix or ".png"


def colliding_card_ids(con: sqlite3.Connection) -> list[int]:
    """Ids of every card sharing its (set_code, card_number) with another card."""
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for cid, sc, num in con.execute(
        "SELECT id, set_code, card_number FROM cards"
    ).fetchall():
        groups[(sc, num)].append(cid)
    return [cid for ids in groups.values() if len(ids) > 1 for cid in ids]


def run(delay: float, dry_run: bool) -> None:
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    ids = colliding_card_ids(con)
    print(f"{len(ids)} cards in colliding (set, number) groups")

    done = skipped = failed = 0
    for cid in ids:
        r = con.execute(
            "SELECT id, set_code, card_number, name, type, "
            "image_front_url, image_back_url FROM cards WHERE id = ?",
            (cid,),
        ).fetchone()
        set_dir = IMAGES_DIR / re.sub(r"[^\w]", "_", r["set_code"] or "UNKNOWN")
        safe_num = _safe(r["card_number"])
        for side, url in (("front", r["image_front_url"]), ("back", r["image_back_url"])):
            if not url:
                continue
            # Unique, id-based stem so no two cards ever share a file.
            existing = [
                p for p in set_dir.glob(f"{safe_num}_{cid}_{side}.*")
                if p.suffix != ".tmp" and p.stat().st_size >= MIN_IMAGE_BYTES
            ]
            col = "image_front_path" if side == "front" else "image_back_path"
            if existing:
                rel = str(existing[0].relative_to(ROOT / "data"))
                _set_path(con, col, rel, cid, dry_run)
                skipped += 1
                continue
            if dry_run:
                print(f"  would fetch {r['type']:<13} {r['name'][:22]:<22} "
                      f"{r['set_code']} {r['card_number']} {side}")
                continue
            try:
                resp = requests.get(url, headers=HEADERS, timeout=60)
                resp.raise_for_status()
                content = resp.content
                if len(content) < MIN_IMAGE_BYTES:
                    print(f"  too small ({len(content)}B): {url}", file=sys.stderr)
                    failed += 1
                    continue
                set_dir.mkdir(parents=True, exist_ok=True)
                final = set_dir / f"{safe_num}_{cid}_{side}{_ext(resp, url)}"
                tmp = final.with_suffix(".tmp")
                tmp.write_bytes(content)
                tmp.replace(final)
                _set_path(con, col, str(final.relative_to(ROOT / "data")), cid, dry_run)
                done += 1
                print(f"  fixed {r['type']:<13} {r['name'][:22]:<22} "
                      f"{r['set_code']} {r['card_number']} {side}")
                time.sleep(delay)
            except Exception as e:  # noqa: BLE001
                print(f"  FAILED {r['name']} {side}: {e}", file=sys.stderr)
                failed += 1

    if not dry_run:
        con.commit()
    con.close()
    print(f"Done: {done} downloaded, {skipped} already-correct, {failed} failed"
          + (" (dry run, no changes written)" if dry_run else ""))


def _set_path(con, col, rel, cid, dry_run):
    if dry_run:
        return
    con.execute(f"UPDATE cards SET {col} = ? WHERE id = ?", (rel, cid))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between downloads")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(delay=args.delay, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
