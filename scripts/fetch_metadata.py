"""
Phase 1 — fetch every card metadata page from the SWU API.

Usage:
    python scripts/fetch_metadata.py [--delay 1.5] [--refresh]
                                     [--variants | --variants-only]

--delay          seconds between requests (default 1.5)
--refresh        wipe the target pages dir(s) and start clean
--variants       also fetch art-variant cards (Hyperspace / Hyperspace Foil /
                 Showcase, etc.) into data/raw/variant_pages/ after the base pass
--variants-only  fetch ONLY the variant pages (skip the base pass entirely)

Base cards (the ones the engine plays) live in data/raw/pages/; their fetch and
on-disk layout are unchanged.  Variant cards (separate API records whose
`variantOf` is non-null) live in data/raw/variant_pages/.  Both passes are
independently resumable — interrupt and re-run to pick up where you left off.
"""

import argparse
import json
import logging
import logging.handlers
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
PAGES_DIR = DATA_RAW / "pages"
MANIFEST_PATH = DATA_RAW / "manifest.json"
VARIANT_PAGES_DIR = DATA_RAW / "variant_pages"
VARIANT_MANIFEST_PATH = DATA_RAW / "variant_manifest.json"
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

BASE_URL = "https://admin.starwarsunlimited.com/api/card-list"

HEADERS = {
    "Accept": "application/json",
    "Origin": "https://starwarsunlimited.com",
    "Referer": "https://starwarsunlimited.com/",
    "User-Agent": "swu-home-game/0.1 (personal hobby project)",
}

# Common query params; the per-pass `variantOf` filter is added in _query_params().
QUERY_PARAMS = {
    "locale": "en",
    "filters[variantOf][id][$null]": "true",
    "pagination[pageSize]": "50",
    "sort[0]": "type.sortValue:asc,expansion.sortValue:desc,cardNumber:asc",
    "populate": "*",
}

# Variant pass: same params but selecting cards that ARE variants (variantOf set).
VARIANT_QUERY_PARAMS = {
    **{k: v for k, v in QUERY_PARAMS.items() if k != "filters[variantOf][id][$null]"},
    "filters[variantOf][id][$notNull]": "true",
}

# Mutable state for the run — doubles if we keep hitting 429s
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
                wait = float(retry_after)
                log.warning("429 — Retry-After: %.0f s, sleeping...", wait)
                time.sleep(wait)
            else:
                log.warning("429 — doubling base delay to %.1f s", _base_delay)


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=5, max=120),
    stop=stop_after_attempt(5),
    after=_after_retry,
    reraise=True,
)
def _fetch_page_raw(page: int, query_params: dict) -> requests.Response:
    params = {**query_params, "pagination[page]": str(page)}
    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp


def _page_path(pages_dir: Path, page: int) -> Path:
    return pages_dir / f"page_{page:04d}.json"


def _is_valid_page_file(path: Path) -> bool:
    """True if path exists, is valid JSON, and has meta.pagination."""
    if not path.exists():
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return "meta" in data and "pagination" in data["meta"]
    except (json.JSONDecodeError, OSError):
        return False


def _find_resume_page(pages_dir: Path) -> int:
    """Return the first page we need to fetch (1-based)."""
    existing = sorted(pages_dir.glob("page_*.json"))
    valid = [p for p in existing if _is_valid_page_file(p)]
    if not valid:
        return 1
    # Re-fetch the last valid page (cheap insurance) and continue from there
    last_num = int(valid[-1].stem.split("_")[1])
    return max(1, last_num)


def _save_page(pages_dir: Path, page: int, raw_text: str, data: dict) -> None:
    tmp = _page_path(pages_dir, page).with_suffix(".tmp")
    tmp.write_text(raw_text, encoding="utf-8")
    os.replace(tmp, _page_path(pages_dir, page))  # atomic on Windows
    log.info("Saved page %d (%d cards)", page, len(data.get("data", [])))


def run(
    delay: float,
    refresh: bool,
    *,
    pages_dir: Path = PAGES_DIR,
    manifest_path: Path = MANIFEST_PATH,
    query_params: dict | None = None,
    label: str = "cards",
) -> None:
    _configure_logging()
    global _base_delay
    _base_delay = delay
    if query_params is None:
        query_params = QUERY_PARAMS

    pages_dir.mkdir(parents=True, exist_ok=True)

    if refresh:
        log.info("--refresh: wiping %s", pages_dir)
        for f in pages_dir.glob("*.json"):
            f.unlink()
        for f in pages_dir.glob("*.tmp"):
            f.unlink()

    start_page = _find_resume_page(pages_dir)
    log.info("[%s] Starting fetch from page %d", label, start_page)

    # Fetch page 1 first to learn pageCount (unless we already have a later start)
    page_count: int | None = None
    total: int | None = None

    try:
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeRemainingColumn,
        )
        use_rich = True
    except ImportError:
        use_rich = False

    page = start_page
    cards_fetched = 0  # running total of cards saved this run (updated per page)

    if use_rich:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=36),
            TextColumn("[cyan]{task.completed:,}[/cyan]/[white]{task.total:,}[/white] cards"),
            TextColumn("[dim]([progress.percentage]{task.percentage:>3.0f}%)[/dim]"),
            TimeRemainingColumn(),
        )
        progress.__enter__()
        task = None
    else:
        progress = None

    def _print_plain(page: int, page_count: int, cards: int, total: int) -> None:
        pct = 100 * cards / total if total else 0
        print(f"  Page {page}/{page_count}  |  {cards:,}/{total:,} cards  ({pct:.0f}%)", flush=True)

    try:
        while True:
            resp = _fetch_page_raw(page, query_params)
            data = resp.json()

            if page_count is None:
                meta = data["meta"]["pagination"]
                page_count = meta["pageCount"]
                total = meta["total"]
                page_size = meta["pageSize"]
                log.info("[%s] API: total=%d pages=%d", label, total, page_count)
                # Account for pages already on disk from a previous run
                already_done = max(0, start_page - 1) * page_size
                cards_fetched = already_done
                if use_rich:
                    task = progress.add_task(
                        f"Page {page}/{page_count}",
                        total=total,
                        completed=cards_fetched,
                    )

            cards_this_page = len(data.get("data", []))
            _save_page(pages_dir, page, resp.text, data)
            cards_fetched += cards_this_page

            if use_rich and task is not None:
                progress.update(
                    task,
                    completed=cards_fetched,
                    description=f"Page {page}/{page_count}",
                )
            else:
                _print_plain(page, page_count, cards_fetched, total)

            if page >= page_count:
                break

            page += 1
            sleep_time = _base_delay + random.uniform(0, 0.5)
            time.sleep(sleep_time)

    finally:
        if use_rich and progress is not None:
            progress.__exit__(None, None, None)

    _write_manifest(manifest_path, query_params, total, page_count)
    log.info("[%s] Metadata fetch complete. %d pages, %d total cards.", label, page_count, total)


def _write_manifest(manifest_path: Path, query_params: dict, total: int, page_count: int) -> None:
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cards": total,
        "page_count": page_count,
        "page_size": int(query_params["pagination[pageSize]"]),
        "query_params": query_params,
    }
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, manifest_path)
    log.info("Manifest written to %s", manifest_path)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Fetch SWU card metadata pages")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests (default 1.5)")
    parser.add_argument("--refresh", action="store_true", help="Wipe existing pages and start clean")
    parser.add_argument("--variants", action="store_true",
                        help="Also fetch art-variant cards into data/raw/variant_pages/")
    parser.add_argument("--variants-only", action="store_true",
                        help="Fetch ONLY variant pages (skip the base card pass)")
    args = parser.parse_args()

    if not args.variants_only:
        run(delay=args.delay, refresh=args.refresh)

    if args.variants or args.variants_only:
        run(
            delay=args.delay,
            refresh=args.refresh,
            pages_dir=VARIANT_PAGES_DIR,
            manifest_path=VARIANT_MANIFEST_PATH,
            query_params=VARIANT_QUERY_PARAMS,
            label="variants",
        )


if __name__ == "__main__":
    main()
