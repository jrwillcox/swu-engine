"""
Phase 2b — download card art images.

Usage:
    python scripts/fetch_images.py [--delay 1.5]
                                   [--variants-only]

Downloads base card art (data/images/<set>/) and art-variant images
(data/images/variants/<set>/) for any rows in the card_variants table.

--variants-only  download only the variant images (skip the base pass)

Resumable: skips any file that already exists and is > 1 KB, so interrupt and
re-run to pick up where you left off.
"""

import argparse
import logging
import logging.handlers
import mimetypes
import os
import random
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "swu.db"
IMAGES_DIR = ROOT / "data" / "images"
LOG_PATH = ROOT / "data" / "pipeline.log"

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

HEADERS = {
    "Accept": "image/*,*/*",
    "Origin": "https://starwarsunlimited.com",
    "Referer": "https://starwarsunlimited.com/",
    "User-Agent": "swu-home-game/0.1 (personal hobby project)",
}

MIN_IMAGE_BYTES = 1024  # 1 KB sanity floor
_base_delay = 1.5


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


def _after_retry(state: RetryCallState) -> None:
    exc = state.outcome.exception()
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code == 429:
            global _base_delay
            _base_delay = min(_base_delay * 2, 60.0)
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after:
                time.sleep(float(retry_after))


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=5, max=120),
    stop=stop_after_attempt(5),
    after=_after_retry,
    reraise=True,
)
def _download(url: str) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
    resp.raise_for_status()
    return resp


def _ext_from_response(resp: requests.Response, url: str) -> str:
    ct = resp.headers.get("Content-Type", "")
    ext = mimetypes.guess_extension(ct.split(";")[0].strip(), strict=False)
    if ext in (".jpe", ".jpeg"):
        ext = ".jpg"
    if ext:
        return ext
    # Fall back to URL path
    path = urlparse(url).path
    suffix = Path(path).suffix
    return suffix if suffix else ".webp"


def _safe_card_number(card_number: str) -> str:
    return re.sub(r'[^\w\-]', '_', card_number)


def _image_dir(set_code: str, *, variant: bool) -> Path:
    safe_set = re.sub(r'[^\w]', '_', set_code or "UNKNOWN")
    return (IMAGES_DIR / "variants" / safe_set) if variant else (IMAGES_DIR / safe_set)


class _Job:
    """One image to fetch: a url, where it lives on disk, and how to record it."""

    __slots__ = ("url", "parent", "stem", "update")

    def __init__(self, url: str, parent: Path, stem: str, update):
        self.url = url
        self.parent = parent
        self.stem = stem
        self.update = update  # callable(con, final_path) -> None


def _base_jobs(con: sqlite3.Connection) -> list[_Job]:
    rows = con.execute(
        "SELECT id, set_code, card_number, image_front_url, image_back_url FROM cards"
    ).fetchall()
    # (set_code, card_number) is NOT unique — every Leader shares its number with
    # a Token (and a few promo Units do too). Naming files by number alone makes
    # the two cards collide on one physical file (the Leader rendered as a Shield
    # token bug). For a colliding key, disambiguate the filename with the unique
    # card id (matching scripts/fix_image_collisions.py); non-colliding cards keep
    # the plain number-based name so already-downloaded art is still found.
    from collections import Counter
    key_counts = Counter((r[1], r[2]) for r in rows)
    jobs: list[_Job] = []
    for card_id, set_code, card_number, front_url, back_url in rows:
        parent = _image_dir(set_code, variant=False)
        safe_num = _safe_card_number(card_number or "0")
        collides = key_counts[(set_code, card_number)] > 1
        prefix = f"{safe_num}_{card_id}" if collides else safe_num
        for url, side in ((front_url, "front"), (back_url, "back")):
            if not url:
                continue
            col = "image_front_path" if side == "front" else "image_back_path"
            jobs.append(_Job(
                url, parent, f"{prefix}_{side}",
                lambda con, path, _id=card_id, _col=col: con.execute(
                    f"UPDATE cards SET {_col} = ? WHERE id = ?",
                    (str(path.relative_to(ROOT / 'data')), _id),
                ),
            ))
    return jobs


def _variant_jobs(con: sqlite3.Connection) -> list[_Job]:
    try:
        rows = con.execute(
            "SELECT base_card_id, variant_type, set_code, card_number, "
            "image_front_url, image_back_url FROM card_variants"
        ).fetchall()
    except sqlite3.OperationalError:
        log.warning("No card_variants table — run build_db.py --variants-only first")
        return []
    jobs: list[_Job] = []
    for base_id, vtype, set_code, card_number, front_url, back_url in rows:
        parent = _image_dir(set_code, variant=True)
        safe_num = _safe_card_number(card_number or "0")
        for url, side in ((front_url, "front"), (back_url, "back")):
            if not url:
                continue
            col = "image_front_path" if side == "front" else "image_back_path"
            jobs.append(_Job(
                url, parent, f"{safe_num}_{vtype}_{side}",
                lambda con, path, _b=base_id, _v=vtype, _col=col: con.execute(
                    f"UPDATE card_variants SET {_col} = ? "
                    "WHERE base_card_id = ? AND variant_type = ?",
                    (str(path.relative_to(ROOT / 'data')), _b, _v),
                ),
            ))
    return jobs


def _download_all(con: sqlite3.Connection, jobs: list[_Job], label: str) -> tuple[int, int, int]:
    """Fetch every job, skipping files already on disk.  Returns (done, skipped, failed)."""
    try:
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeRemainingColumn,
        )
        use_rich = True
    except ImportError:
        use_rich = False

    done = skipped = failed = 0
    progress = task = None
    if use_rich:
        progress = Progress(
            SpinnerColumn(),
            TextColumn(f"[bold blue]{label}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        )
        progress.__enter__()
        task = progress.add_task(label, total=len(jobs))

    try:
        for job in jobs:
            job.parent.mkdir(parents=True, exist_ok=True)

            # Already done? (any extension)
            existing = list(job.parent.glob(f"{job.stem}.*"))
            existing = [p for p in existing if p.suffix != ".tmp"]
            if existing and existing[0].stat().st_size >= MIN_IMAGE_BYTES:
                job.update(con, existing[0])
                skipped += 1
                if use_rich and task is not None:
                    progress.update(task, advance=1)
                continue

            try:
                resp = _download(job.url)
                ext = _ext_from_response(resp, job.url)
                final_path = job.parent / f"{job.stem}{ext}"
                tmp = final_path.with_suffix(".tmp")
                content = resp.content
                if len(content) < MIN_IMAGE_BYTES:
                    log.warning("Image too small (%d bytes): %s", len(content), job.url)
                    failed += 1
                else:
                    tmp.write_bytes(content)
                    os.replace(tmp, final_path)
                    job.update(con, final_path)
                    done += 1
            except Exception as e:
                log.error("Failed to download %s: %s", job.url, e)
                failed += 1

            if use_rich and task is not None:
                progress.update(task, advance=1)
            time.sleep(_base_delay + random.uniform(0, 0.5))
    finally:
        if use_rich and progress is not None:
            progress.__exit__(None, None, None)

    return done, skipped, failed


def run(delay: float, *, base: bool = True, variants: bool = True) -> None:
    _configure_logging()
    global _base_delay
    _base_delay = delay

    if not DB_PATH.exists():
        log.error("DB not found at %s — run build_db.py first", DB_PATH)
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    try:
        if base:
            jobs = _base_jobs(con)
            log.info("Base image download: %d targets", len(jobs))
            d, s, f = _download_all(con, jobs, "Images")
            con.commit()
            log.info("Base images: %d downloaded, %d skipped, %d failed", d, s, f)
        if variants:
            jobs = _variant_jobs(con)
            log.info("Variant image download: %d targets", len(jobs))
            d, s, f = _download_all(con, jobs, "Variants")
            con.commit()
            log.info("Variant images: %d downloaded, %d skipped, %d failed", d, s, f)
    finally:
        con.commit()
        con.close()


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Download SWU card images")
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--variants-only", action="store_true",
                        help="Download only variant images (skip the base card pass)")
    args = parser.parse_args()
    run(delay=args.delay, base=not args.variants_only, variants=True)


if __name__ == "__main__":
    main()
