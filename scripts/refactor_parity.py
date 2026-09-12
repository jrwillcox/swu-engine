"""Prove that a refactor moved code without changing it.

This is the gate for Phase A of the ``engine/actions.py`` decomposition: 24,788
lines are redistributed into a package, and the claim being made about every one
of those commits is *"no behaviour changed"*.  A test suite can only sample that
claim.  Comparing syntax trees proves it.

How it works
------------
For the baseline (``actions.py`` as it was, read out of git) and for the current
tree (the ``actions`` package, or the single module before the split), build a
map of

    qualname -> ast.dump(node, include_attributes=False)

covering every top-level class, function and assignment, plus every method.
``include_attributes=False`` drops line and column numbers, so **relocating a
function is invisible to this comparison while any edit to its body is not**.
Comments and blank lines never reach the AST at all, so re-indenting a section
header or adding a ``# noqa`` is likewise free.

What it deliberately does NOT check
-----------------------------------
Module-level ``import`` statements.  Phase A has to add imports to every new
module — that is the whole mechanical content of the move — so imports are
excluded from the comparison by design.  The consequence is that this script
cannot catch a moved function whose global no longer resolves (a ``NameError``
waiting to happen).  ``ruff --select F821`` catches exactly that, which is why
the ``actions`` package must not inherit the old blanket F821 per-file-ignore.
The two checks are complements; run both.

Usage
-----
    python scripts/refactor_parity.py                  # vs the baseline tag
    python scripts/refactor_parity.py --baseline HEAD~1
    python scripts/refactor_parity.py --self-test      # prove the gate works

Exit status is 0 only when every qualname is present and byte-identical, or
explicitly waived in ``scripts/refactor_parity_waivers.json``.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BASELINE_TAG = "pre-actions-split"
BASELINE_PATH = "src/swu/engine/actions.py"

# The split target: either the pre-split module or the post-split package.
TARGET_MODULE = REPO_ROOT / "src" / "swu" / "engine" / "actions.py"
TARGET_PACKAGE = REPO_ROOT / "src" / "swu" / "engine" / "actions"

WAIVERS_FILE = Path(__file__).resolve().parent / "refactor_parity_waivers.json"

# A waiver list longer than this means the layering is wrong: a kernel module is
# reaching upward often enough that the module boundaries should move instead.
# See the plan's Phase A note.  Raising this number is a decision, not a fix.
MAX_WAIVERS = 15


def _dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def _assign_targets(node: ast.Assign | ast.AnnAssign) -> list[str]:
    """The simple names a module-level assignment binds.

    Only plain ``NAME = ...`` and ``NAME: T = ...`` forms are tracked; tuple
    unpacking and subscript/attribute targets are skipped rather than guessed at,
    because a stable qualname is the whole point.
    """
    if isinstance(node, ast.AnnAssign):
        return [node.target.id] if isinstance(node.target, ast.Name) else []
    names = []
    for target in node.targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return names


def collect(source: str, origin: str,
            repeats: list[str] | None = None) -> dict[str, tuple[str, str]]:
    """Map qualname -> (dumped AST, origin file) for one parsed source file.

    Recurses into classes (so methods are compared individually, which matters:
    167 of the 169 classes here are dataclasses whose ``apply``/``describe``
    methods carry the actual behaviour) but not into functions — a nested
    function is already part of its parent's dump.
    """
    tree = ast.parse(source)
    out: dict[str, tuple[str, str]] = {}

    def record(qual: str, node: ast.AST) -> None:
        # A qualname defined twice in ONE file is what a buggy extraction produces:
        # Python just re-binds, so it is invisible at runtime until the two copies
        # diverge, and a dict-based comparison would silently collapse them.
        if qual in out and repeats is not None:
            repeats.append(qual)
        out[qual] = (_dump(node), origin)

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                record(f"{prefix}{node.name}", node)
            elif isinstance(node, ast.ClassDef):
                qual = f"{prefix}{node.name}"
                # The class node minus its body: decorators and bases are part of
                # the contract (``@dataclass``, the ``Action`` base), but the body
                # is compared member by member so a moved method is pinpointed.
                shell = ast.ClassDef(
                    name=node.name,
                    bases=node.bases,
                    keywords=node.keywords,
                    body=[ast.Pass()],
                    decorator_list=node.decorator_list,
                    type_params=getattr(node, "type_params", []),
                )
                record(f"{qual}#shell", shell)
                visit(node.body, f"{qual}.")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for name in _assign_targets(node):
                    record(f"{prefix}{name}", node)

    visit(tree.body, "")
    return out


def baseline_map(ref: str, repeats: list[str] | None = None) -> dict[str, tuple[str, str]]:
    spec = f"{ref}:{BASELINE_PATH}"
    try:
        # Bytes, not text=True: the file's section banners are UTF-8 box-drawing
        # characters, and letting subprocess decode with the Windows locale
        # codepage (cp1252) raises UnicodeDecodeError on them.
        raw = subprocess.run(
            ["git", "show", spec],
            cwd=REPO_ROOT, capture_output=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.exit(
            f"cannot read baseline {spec!r}: {exc.stderr.decode('utf-8', 'replace').strip()}\n"
            f"Create the baseline first:  git tag {BASELINE_TAG} <commit before the split>"
        )
    return collect(raw.decode("utf-8"), BASELINE_PATH, repeats=repeats)


def current_map(baseline_repeats: set[str]) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """The working tree's map, plus any qualname defined in two places.

    ``baseline_repeats`` are the names the pre-split module already rebound at top
    level; those are pre-existing, not introduced by the refactor.
    """
    files: list[Path] = []
    if TARGET_PACKAGE.is_dir():
        files.extend(sorted(TARGET_PACKAGE.rglob("*.py")))
    if TARGET_MODULE.is_file():
        files.append(TARGET_MODULE)
    if not files:
        sys.exit(f"no target found at {TARGET_MODULE} or {TARGET_PACKAGE}")

    merged: dict[str, tuple[str, str]] = {}
    duplicates: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        within: list[str] = []
        one = collect(path.read_text(encoding="utf-8"), rel, repeats=within)
        # Repeats WITHIN one file, which a per-file dict would otherwise hide.
        # Only new ones matter: the pre-split module may itself rebind a name.
        duplicates.extend(f"{q}: defined twice in {rel}"
                          for q in within if q not in baseline_repeats)
        for qual, (dumped, _) in one.items():
            if qual in merged:
                # Two modules defining the same qualname is the copy-paste
                # accident this refactor is most likely to produce, and the
                # facade would happily re-export whichever won the import race.
                duplicates.append(f"{qual}: {merged[qual][1]} and {rel}")
                continue
            merged[qual] = (dumped, rel)
    return merged, duplicates


def load_waivers() -> dict[str, str]:
    if not WAIVERS_FILE.exists():
        return {}
    data = json.loads(WAIVERS_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def self_test() -> int:
    """Prove the gate detects what it claims to, and ignores what it claims to.

    A gate nobody has tried to fool is an assumption, not a gate.
    """
    base = "def f(a):\n    x = a + 1\n    return x\n"
    cases = [
        ("relocation (leading comment + blank lines)", "# moved here\n\n\n" + base, True),
        ("a noqa comment", "def f(a):  # noqa: F821\n    x = a + 1\n    return x\n", True),
        ("re-indentation of a section banner", "# ── X ──\n" + base, True),
        ("an added module-level import", "import os\n" + base, True),
        ("a changed operator", "def f(a):\n    x = a - 1\n    return x\n", False),
        ("a changed constant", "def f(a):\n    x = a + 2\n    return x\n", False),
        ("a dropped statement", "def f(a):\n    return a + 1\n", False),
        ("a renamed local", "def f(a):\n    y = a + 1\n    return y\n", False),
    ]
    expected = collect(base, "base")
    ok = True
    for label, variant, should_match in cases:
        got = collect(variant, "variant")
        matches = got.get("f", ("", ""))[0] == expected["f"][0]
        verdict = "PASS" if matches == should_match else "FAIL"
        if matches != should_match:
            ok = False
        sense = "invisible to" if should_match else "caught by"
        print(f"  [{verdict}] {label} — {sense} the gate")

    # A duplicate WITHIN one file: Python silently rebinds, so this is the one
    # corruption a buggy extraction produces that runs fine and compares equal.
    # It went undetected in the first version of this script, which is why it is
    # pinned here.
    repeats: list[str] = []
    collect(base + "\n" + base, "variant", repeats=repeats)
    dup_caught = repeats == ["f"]
    ok = ok and dup_caught
    print(f"  [{'PASS' if dup_caught else 'FAIL'}] a definition duplicated within one "
          f"file — caught by the gate")

    print("\nself-test:", "the gate behaves as documented" if ok else "THE GATE IS BROKEN")
    return 0 if ok else 1


def main() -> int:
    # This repo's sources carry UTF-8 box-drawing section banners, and qualnames
    # or waiver reasons can quote them.  The Windows console defaults to cp1252,
    # where printing one raises UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=BASELINE_TAG,
                        help=f"git ref holding the pre-split actions.py (default: {BASELINE_TAG})")
    parser.add_argument("--self-test", action="store_true",
                        help="verify the comparison detects edits and ignores relocation")
    parser.add_argument("--quiet", action="store_true", help="only report problems")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    baseline_repeats: list[str] = []
    before = baseline_map(args.baseline, repeats=baseline_repeats)
    after, duplicates = current_map(set(baseline_repeats))
    waivers = load_waivers()

    missing = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = sorted(
        q for q in set(before) & set(after) if before[q][0] != after[q][0]
    )

    waived = [q for q in changed if q in waivers]
    changed = [q for q in changed if q not in waivers]
    stale = sorted(set(waivers) - set(waived))

    if not args.quiet:
        print(f"baseline {args.baseline}:{BASELINE_PATH} — {len(before)} definitions")
        print(f"working tree — {len(after)} definitions across "
              f"{len({o for _, o in after.values()})} file(s)")

    problems = 0

    def report(label: str, items: list[str], hint: str = "") -> None:
        nonlocal problems
        if not items:
            return
        problems += len(items)
        print(f"\n{label} ({len(items)}){':' if not hint else f' — {hint}:'}")
        for item in items[:40]:
            print(f"  {item}")
        if len(items) > 40:
            print(f"  … and {len(items) - 40} more")

    report("MISSING — in the baseline, absent now", missing,
           "a lost definition breaks callers silently")
    report("CHANGED — body differs from the baseline", changed,
           "Phase A must not edit bodies; waive deliberately or revert")
    report("DUPLICATED — defined in two modules", duplicates,
           "the facade would export whichever won")
    report("STALE WAIVERS — waived but now identical", stale,
           "remove these from the waiver file")

    if added and not args.quiet:
        # Additions are legitimate: the facade, ``__all__``, and any new helper.
        # Listed for review rather than failed on.
        print(f"\nADDED (review, not a failure) ({len(added)}):")
        for item in added[:20]:
            print(f"  {item}  [{after[item][1]}]")
        if len(added) > 20:
            print(f"  … and {len(added) - 20} more")

    if waived and not args.quiet:
        print(f"\nWAIVED ({len(waived)}/{MAX_WAIVERS}):")
        for item in waived:
            print(f"  {item} — {waivers[item]}")

    if len(waived) > MAX_WAIVERS:
        problems += 1
        print(f"\nTOO MANY WAIVERS: {len(waived)} > {MAX_WAIVERS}. The layering is wrong; "
              "move a module boundary instead of waiving another function.")

    print()
    if problems:
        print(f"PARITY FAILED — {problems} problem(s)")
        return 1
    print(f"PARITY OK — {len(before)} definitions identical"
          + (f", {len(waived)} waived" if waived else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
