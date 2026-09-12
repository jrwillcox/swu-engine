"""Which test modules may run against the small fixture database.

The repository ships no card corpus, so a fresh clone has two ways to run the
DB-backed tests: build the real database (``docs/pipeline.md``), or fall back to
``tests/fixtures/swu_fixture.db`` — a few hundred committed card definitions,
built by ``scripts/make_fixture_db.py``.

Some tests can't use the fixture, because what they assert is a property of the
*whole* corpus: "every card in this deck is implemented", "the coverage audit
reports 100%", "every reprint mirrors its twin".  Run those against a few
hundred cards and they fail for a reason that has nothing to do with the code.
They are listed here and skip cleanly in fixture mode instead.

This one list drives both directions, so they can't drift apart:

* ``tests/conftest.py`` skips these modules when the fixture is standing in.
* ``scripts/make_fixture_db.py --record`` records card loads from everything
  NOT listed here, which is what makes the fixture complete for the tests that
  do use it.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

#: Modules whose SUBJECT is the whole corpus, so every test in them is skipped in
#: fixture mode.  Matched by fnmatch against the file NAME (not the path), so the
#: patterns read the way the files are named.
FULL_CORPUS_PATTERNS = (
    "test_deck_coverage.py",    # every card in every shipped deck is implemented
    "test_reprints.py",         # every reprint aliases an implemented twin
    "test_plan_encoding.py",    # walks the unimplemented-card queue
    "test_verify_encoding.py",  # per-deck coverage percentages
    "test_swudb_import.py",     # resolves arbitrary decklist codes
    "test_explorer.py",         # the assembled all-cards catalog and its facets
    "test_repository.py",       # corpus-scale properties: ">100 units", every
                                # Leader has a back image (the fixture carries no
                                # image URLs at all)
)

#: The fixtures that hand a test card data.  A test in a FULL_CORPUS module is
#: skipped in fixture mode only if it requests one of these — the rest of those
#: modules reads the ability registry, needs no database, and must keep running.
DB_FIXTURE_NAMES = frozenset({"repo", "deck_a", "deck_b"})

#: Modules the fixture is NOT sized for.  The per-set card suites test one card
#: per printed card across 24 sets: recording them would put the entire corpus in
#: the fixture, which is the thing this whole arrangement exists to avoid.
#:
#: They are deliberately NOT in FULL_CORPUS_PATTERNS — they still RUN in fixture
#: mode, per test: ``tests/test_sor_cards._get_card`` skips a test whose card
#: isn't in the fixture, while the registration-only tests in those same modules
#: (which read the ability registry, not the DB) pass without it.  Skipping the
#: modules wholesale instead cost ~970 passing tests on a fresh clone.
RECORD_EXCLUDE_PATTERNS = FULL_CORPUS_PATTERNS + ("test_*_cards.py",)


def needs_full_corpus(module_name: str) -> bool:
    """Whether ``module_name`` (a file name like ``test_reprints.py``) is listed."""
    return any(fnmatch.fnmatch(module_name, pat) for pat in FULL_CORPUS_PATTERNS)


def fixture_eligible_args() -> list[str]:
    """pytest targets the fixture manifest is recorded from.

    Returned as explicit paths rather than an ``--ignore`` list so the recorder's
    scope is visible in its own command line.
    """
    targets = [
        f"tests/{p.name}"
        for p in sorted(TESTS_DIR.glob("test_*.py"))
        if not any(fnmatch.fnmatch(p.name, pat) for pat in RECORD_EXCLUDE_PATTERNS)
    ]
    targets.append("tests/regressions")
    return targets
