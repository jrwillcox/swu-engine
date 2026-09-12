"""
Final validation report.

Usage:
    python scripts/validate.py

Exits non-zero if critical checks fail.
"""

import json
import logging
import logging.handlers
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "swu.db"
IMAGES_DIR = ROOT / "data" / "images"
MANIFEST_PATH = ROOT / "data" / "raw" / "manifest.json"
LOG_PATH = ROOT / "data" / "pipeline.log"

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

TYPES_NEEDING_COST = {"Unit", "Event", "Upgrade"}
TYPES_NEEDING_TEXT = {"Unit", "Event", "Upgrade", "Leader", "Base"}
TOKEN_TYPES = {"Token Unit", "Token Upgrade", "Credit Token", "Force Token"}


def run() -> bool:
    try:
        from rich.table import Table
        from rich.console import Console
        from rich import box
        use_rich = True
    except ImportError:
        use_rich = False

    issues: list[tuple[str, str, bool]] = []  # (check, detail, critical)
    ok: list[tuple[str, str]] = []

    if not DB_PATH.exists():
        print("FAIL: swu.db not found")
        return False

    con = sqlite3.connect(DB_PATH)

    # Load manifest
    if not MANIFEST_PATH.exists():
        issues.append(("Manifest", "manifest.json missing", True))
        manifest_total = None
    else:
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        manifest_total = manifest.get("total_cards")
        ok.append(("Manifest", f"total_cards={manifest_total}"))

    # Card counts by type
    type_counts = dict(con.execute("SELECT type, COUNT(*) FROM cards GROUP BY type").fetchall())
    total_db = sum(type_counts.values())

    if manifest_total and abs(total_db - manifest_total) > 10:
        issues.append(("Card total", f"DB has {total_db}, manifest says {manifest_total}", True))
    else:
        ok.append(("Card total", f"{total_db} cards in DB"))

    # Leaders should have back images
    leaders_no_back = con.execute(
        "SELECT COUNT(*) FROM cards WHERE type='Leader' AND image_back_url IS NOT NULL AND image_back_path IS NULL"
    ).fetchone()[0]
    if leaders_no_back:
        issues.append(("Leader back images", f"{leaders_no_back} leaders missing back image file", True))
    else:
        ok.append(("Leader back images", "all leaders have back image"))

    # All cards missing front image
    missing_front = con.execute(
        "SELECT COUNT(*) FROM cards WHERE image_front_url IS NOT NULL AND image_front_path IS NULL"
    ).fetchone()[0]
    if missing_front:
        issues.append(("Front images", f"{missing_front} cards with URL but no local file", False))
    else:
        ok.append(("Front images", "all cards with URLs have local files"))

    # Cards missing aspects (types that should have them)
    cards_no_aspects = con.execute(
        """SELECT COUNT(*) FROM cards c
           WHERE c.type NOT IN ('Token Unit','Token Upgrade','Credit Token','Force Token')
           AND NOT EXISTS (SELECT 1 FROM card_aspects a WHERE a.card_id = c.id)"""
    ).fetchone()[0]
    if cards_no_aspects:
        issues.append(("Aspects", f"{cards_no_aspects} non-token cards have no aspects", False))
    else:
        ok.append(("Aspects", "all non-token cards have aspects"))

    # Cost missing for types that require it
    for t in TYPES_NEEDING_COST:
        n = con.execute(
            "SELECT COUNT(*) FROM cards WHERE type=? AND cost IS NULL", (t,)
        ).fetchone()[0]
        if n:
            issues.append(("Cost", f"{n} {t}s missing cost", False))
        else:
            ok.append((f"Cost/{t}", f"all {t}s have cost"))

    # ── Art variants (optional, additive table; not all cards have variants) ──
    variant_counts: dict[str, int] = {}
    has_variants = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='card_variants'"
    ).fetchone() is not None
    if has_variants:
        variant_counts = dict(
            con.execute(
                "SELECT variant_type, COUNT(*) FROM card_variants GROUP BY variant_type"
            ).fetchall()
        )
        total_variants = sum(variant_counts.values())
        ok.append(("Variants", f"{total_variants} variant rows ({', '.join(f'{k}={v}' for k,v in sorted(variant_counts.items()))})"))
        # Variant rows with a URL but no downloaded file (WARN — fetch_images not run / interrupted)
        missing_variant_front = con.execute(
            "SELECT COUNT(*) FROM card_variants WHERE image_front_url IS NOT NULL AND image_front_path IS NULL"
        ).fetchone()[0]
        if missing_variant_front:
            issues.append(("Variant images", f"{missing_variant_front} variants with URL but no local file", False))
        else:
            ok.append(("Variant images", "all variant rows with URLs have local files"))

    # Orphaned image files (in images/ but not referenced in DB).
    # Variant images live under images/variants/ — include card_variants paths.
    if IMAGES_DIR.exists():
        image_files = {str(p.relative_to(ROOT / "data")) for p in IMAGES_DIR.rglob("*") if p.is_file()}
        db_paths = set()
        for row in con.execute("SELECT image_front_path, image_back_path FROM cards"):
            if row[0]:
                db_paths.add(row[0].replace("\\", "/"))
            if row[1]:
                db_paths.add(row[1].replace("\\", "/"))
        if has_variants:
            for row in con.execute("SELECT image_front_path, image_back_path FROM card_variants"):
                if row[0]:
                    db_paths.add(row[0].replace("\\", "/"))
                if row[1]:
                    db_paths.add(row[1].replace("\\", "/"))
        image_files_norm = {p.replace("\\", "/") for p in image_files}
        orphans = image_files_norm - db_paths
        if orphans:
            issues.append(("Orphaned images", f"{len(orphans)} image files not referenced in DB", False))
        else:
            ok.append(("Orphaned images", "none"))

    con.close()

    # Output
    if use_rich:
        console = Console()
        table = Table(title="SWU Pipeline Validation", box=box.SIMPLE_HEAVY)
        table.add_column("Check", style="bold")
        table.add_column("Status", style="bold")
        table.add_column("Detail")
        for check, detail in ok:
            table.add_row(check, "[green]OK[/green]", detail)
        for check, detail, critical in issues:
            sev = "[red]FAIL[/red]" if critical else "[yellow]WARN[/yellow]"
            table.add_row(check, sev, detail)
        console.print(table)

        console.print("\n[bold]Card counts by type:[/bold]")
        for t, n in sorted(type_counts.items()):
            console.print(f"  {t:<25} {n:>5}")
    else:
        print("\n=== SWU Pipeline Validation ===")
        for check, detail in ok:
            print(f"  OK   {check}: {detail}")
        for check, detail, critical in issues:
            sev = "FAIL" if critical else "WARN"
            print(f"  {sev} {check}: {detail}")
        print("\nCard counts by type:")
        for t, n in sorted(type_counts.items()):
            print(f"  {t:<25} {n:>5}")

    critical_failures = [i for i in issues if i[2]]
    if critical_failures:
        log.error("Validation failed: %d critical issue(s)", len(critical_failures))
        return False
    log.info("Validation passed%s", f" with {len(issues)} warning(s)" if issues else "")
    return True


def main() -> None:
    ok = run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
