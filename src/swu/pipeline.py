"""
Entry point: python -m swu.pipeline run [options]

Chains: fetch_metadata → build_db → fetch_images → validate
Each stage is individually skippable.
"""

import argparse
import importlib
import logging
import logging.handlers
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_PATH = ROOT / "data" / "pipeline.log"

log = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Set up console + rotating-file logging for a pipeline run.

    Called from ``main()``, never at import time.  Creating ``data/`` and
    opening a log file are side effects no caller asks for by importing a
    module, and doing them eagerly actively broke the test suite on a machine
    with no card database: importing this module re-created ``data/``, which
    let a later bare ``sqlite3.connect`` put an empty ``swu.db`` inside it, so
    tests that should have skipped instead ran against an empty database.
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


def _add_scripts_to_path() -> None:
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _run_stage(module_name: str, fn_name: str, kwargs: dict) -> bool:
    log.info("=== Stage: %s ===", module_name)
    try:
        mod = importlib.import_module(module_name)
        fn = getattr(mod, fn_name)
        fn(**kwargs)
        return True
    except SystemExit as e:
        if e.code != 0:
            log.error("Stage %s exited with code %s", module_name, e.code)
            return False
        return True
    except Exception as e:
        log.exception("Stage %s failed: %s", module_name, e)
        return False


def cmd_run(args: argparse.Namespace) -> None:
    _add_scripts_to_path()

    stages = [
        ("fetch_metadata", "run", {"delay": args.delay, "refresh": args.refresh},
         args.skip_fetch),
        ("build_db", "run", {},
         args.skip_db),
        ("fetch_images", "run", {"delay": args.delay},
         args.skip_images),
        ("validate", "run", {},
         False),
    ]

    for module_name, fn_name, kwargs, skip in stages:
        if skip:
            log.info("Skipping stage: %s", module_name)
            continue
        ok = _run_stage(module_name, fn_name, kwargs)
        if not ok:
            log.error("Pipeline aborted at stage: %s", module_name)
            sys.exit(1)

    log.info("Pipeline complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SWU data pipeline")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run the full pipeline")
    run_parser.add_argument("--delay", type=float, default=1.5)
    run_parser.add_argument("--refresh", action="store_true", help="Re-fetch all metadata pages")
    run_parser.add_argument("--skip-fetch", action="store_true")
    run_parser.add_argument("--skip-db", action="store_true")
    run_parser.add_argument("--skip-images", action="store_true")

    args = parser.parse_args()

    if args.command == "run":
        _configure_logging()
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
