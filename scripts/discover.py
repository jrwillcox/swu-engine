"""
Throwaway discovery script.
Fetches pages with pageSize=50 until one example of every card type is found.
Output: data/raw/discovery_sample.json
"""

import json
import time
from pathlib import Path

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"

BASE_URL = "https://admin.starwarsunlimited.com/api/card-list"

HEADERS = {
    "Accept": "application/json",
    "Origin": "https://starwarsunlimited.com",
    "Referer": "https://starwarsunlimited.com/",
    "User-Agent": "swu-home-game/0.1 (personal hobby project)",
}

BASE_PARAMS = {
    "locale": "en",
    "filters[variantOf][id][$null]": "true",
    "pagination[pageSize]": "50",
    "sort[0]": "type.sortValue:asc,expansion.sortValue:desc,cardNumber:asc",
    "populate": "*",
}

TYPES_WANTED = {"Leader", "Base", "Unit", "Event", "Upgrade", "Token Unit", "Token Upgrade"}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=5, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def fetch_page(page: int) -> dict:
    params = {**BASE_PARAMS, "pagination[page]": str(page)}
    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_type_name(attrs: dict) -> str | None:
    try:
        return attrs["type"]["data"]["attributes"]["name"]
    except (KeyError, TypeError):
        return None


def main() -> None:
    print("Fetching discovery sample (pageSize=50)...")

    found: dict[str, dict] = {}
    all_pages: list[dict] = []
    page = 1
    page_count = None

    while True:
        print(f"  Page {page}...", flush=True)
        try:
            data = fetch_page(page)
        except Exception as e:
            print(f"  ERROR on page {page}: {e}")
            break

        all_pages.append(data)

        if page_count is None:
            meta = data["meta"]["pagination"]
            page_count = meta["pageCount"]
            total = meta["total"]
            print(f"  API reports {total} total cards across {page_count} pages.")

        for card in data["data"]:
            attrs = card.get("attributes", {})
            type_name = get_type_name(attrs)
            if type_name and type_name not in found:
                found[type_name] = card
                print(f"  Found example of type: {type_name!r}  (id={card['id']})")

        # Stop once we have all types, or we've reached the last page
        if found.keys() >= TYPES_WANTED or page >= page_count:
            break

        page += 1
        time.sleep(1.0)

    # Save whatever we found, even on partial success.  Created here rather than
    # at import time: importing a module should not make directories.
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    sample_path = DATA_RAW / "discovery_sample.json"
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump({"pages_fetched": all_pages, "examples_by_type": found}, f, indent=2, ensure_ascii=False)
    print(f"\nSaved sample to {sample_path}")
    print(f"Types found: {sorted(found.keys())}")
    missing = TYPES_WANTED - found.keys()
    if missing:
        print(f"Types NOT found: {sorted(missing)}")

    print("\n=== Attribute keys by card type ===")
    for type_name in sorted(found):
        attrs = found[type_name]["attributes"]
        keys = sorted(attrs.keys())
        print(f"\n  [{type_name}]  (id={found[type_name]['id']})")
        for k in keys:
            v = attrs[k]
            if isinstance(v, dict):
                print(f"    {k}: dict{list(v.keys())}")
            elif isinstance(v, list):
                print(f"    {k}: list[{len(v)}]")
            else:
                print(f"    {k}: {v!r}")

    if all_pages:
        print("\n=== Pagination sanity check ===")
        meta = all_pages[0]["meta"]["pagination"]
        print(f"  total={meta['total']}  pageCount={meta['pageCount']}  pageSize={meta['pageSize']}")
        expected_min, expected_max = 2_400, 3_200
        if expected_min <= meta["total"] <= expected_max:
            print(f"  OK — total is within expected range [{expected_min}, {expected_max}]")
        else:
            print(f"  WARNING — total {meta['total']} outside expected range [{expected_min}, {expected_max}]")

    print("\n=== Image URL spot-check ===")
    for type_name, card in sorted(found.items()):
        attrs = card["attributes"]
        f_url = _dig_url(attrs.get("artFront"))
        b_url = _dig_url(attrs.get("artBack"))
        print(f"  {type_name:<14} front={f_url!r}")
        if b_url:
            print(f"  {'':14} back ={b_url!r}")


def _dig_url(art_obj) -> str | None:
    try:
        d = art_obj["data"]["attributes"]
        return d.get("url") or d.get("formats", {}).get("card", {}).get("url")
    except (KeyError, TypeError, AttributeError):
        return None


if __name__ == "__main__":
    main()
