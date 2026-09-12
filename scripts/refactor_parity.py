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
    """Waivers live under a ``"waivers"`` key, deliberately.

    The first version of this file kept them at the top level and skipped metadata by
    dropping any key starting with ``_``. That silently made the whole mechanism
    useless for exactly the names most likely to need it: 75 of this module's
    externally-referenced symbols are private, so ``_decision_legal_actions`` and
    every other ``_helper`` was filtered out as if it were a comment. A waiver that
    cannot match is worse than no waiver — the gate fails with no way to pass it, and
    the reason looks like a real parity failure.
    """
    if not WAIVERS_FILE.exists():
        return {}
    data = json.loads(WAIVERS_FILE.read_text(encoding="utf-8"))
    unknown = [k for k in data
               if not k.startswith("_") and k != "waivers"]
    if unknown:
        sys.exit(f"{WAIVERS_FILE.name}: unexpected top-level key(s) {unknown}. "
                 "Waivers belong under the \"waivers\" object; keys starting with "
                 "'_' are metadata. This used to be a flat mapping, and a qualname "
                 "left at the top level would be silently ignored.")
    waivers = data.get("waivers", {})
    if not isinstance(waivers, dict):
        sys.exit(f"{WAIVERS_FILE.name}: \"waivers\" must be an object of "
                 "qualname -> reason")
    return waivers


# ── The decision-dispatch gate ─────────────────────────────────────────────────
#
# Turning the ``if top.kind == "…"`` chain into a dispatch table is the one part of
# this refactor that whole-function AST parity CANNOT check: the body of
# ``_decision_legal_actions`` legitimately changes, so the check above rightly
# reports it and then has nothing left to say about the 601 lines that moved out.
#
# The plan's answer was "use the trace oracle for Phase C". That is too weak — the
# oracle is a sampling oracle, and it already demonstrably missed a real perturbation
# that AST parity pinpointed. So this gate proves the transformation the same way,
# one arm at a time, and it is the reason the dispatch commit needs no reading.
#
# Each of the baseline's arms is proved equivalent by one of two arguments:
#
#   DELEGATED  the arm was exactly ``return NAME(state, top)``. Proof: the table
#              maps the kind to that same NAME, so the same function is called with
#              the same arguments. The function itself is untouched (and whole-file
#              parity above proves that separately).
#   INLINED    the arm held a body. Proof: a handler exists whose body dumps to the
#              identical AST, so the code that runs is the code that ran.
#
# Plus the two structural facts a table depends on, re-checked every run rather than
# taken on trust: no arm may fall through, and no kind may be handled twice.

# The single statement an inlined handler may add: the chain computed the deciding
# player once up front, so a handler that used it has to recompute it. Anything else
# prepended is a body edit and fails.
ALLOWED_PROLOGUE = _dump(
    ast.parse("deciding_ps = state.player_by_id(top.deciding_player_id)").body[0]
)

DISPATCH_FUNC = "_decision_legal_actions"


def _kinds_of(test: ast.expr) -> list[str]:
    """``top.kind == "x"`` -> ["x"]; ``top.kind in ("x", "y")`` -> ["x", "y"]."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return []
    left = test.left
    if not (isinstance(left, ast.Attribute) and left.attr == "kind"
            and isinstance(left.value, ast.Name) and left.value.id == "top"):
        return []
    rhs = test.comparators[0]
    if isinstance(test.ops[0], ast.Eq) and isinstance(rhs, ast.Constant):
        return [rhs.value]
    if isinstance(test.ops[0], ast.In) and isinstance(rhs, (ast.Tuple, ast.List)):
        return [e.value for e in rhs.elts if isinstance(e, ast.Constant)]
    return []


def _always_returns(body: list[ast.stmt]) -> bool:
    """Does this statement list return or raise on every path?

    An arm that can fall off its end depended on reaching a LATER arm, which a dict
    lookup would skip. That would make first-match ordering load-bearing, so it has
    to be checked rather than assumed.
    """
    for st in reversed(body):
        if isinstance(st, (ast.Return, ast.Raise)):
            return True
        if isinstance(st, ast.If):
            return bool(st.orelse) and _always_returns(st.body) and _always_returns(st.orelse)
        if isinstance(st, (ast.With, ast.For, ast.While, ast.Try)):
            return False
    return False


def _baseline_arms(ref: str) -> tuple[dict[str, ast.If], list[str], list[str]]:
    """Every ``top.kind`` arm of the baseline dispatcher, keyed by kind."""
    raw = subprocess.run(
        ["git", "show", f"{ref}:{BASELINE_PATH}"],
        cwd=REPO_ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    fn = next((n for n in ast.parse(raw).body
               if isinstance(n, ast.FunctionDef) and n.name == DISPATCH_FUNC), None)
    if fn is None:
        sys.exit(f"{DISPATCH_FUNC} not found in {ref}:{BASELINE_PATH}")
    arms: dict[str, ast.If] = {}
    duplicated, fell_through = [], []
    for st in fn.body:
        if not isinstance(st, ast.If):
            continue
        for kind in _kinds_of(st.test):
            if kind in arms:
                duplicated.append(kind)
            arms[kind] = st
            if not _always_returns(st.body):
                fell_through.append(kind)
    return arms, duplicated, fell_through


def _registrations() -> tuple[dict[str, str], dict[str, ast.FunctionDef], list[str]]:
    """Read the working tree's ``register_decisions({...})`` blocks statically.

    Static parse rather than import: importing ``swu.engine.actions`` triggers the
    whole card registry as an import side effect and needs a built card database, and
    a gate that cannot run on a bare clone is a gate that stops being run.
    """
    table: dict[str, str] = {}
    handlers: dict[str, ast.FunctionDef] = {}
    problems: list[str] = []
    files = sorted(TARGET_PACKAGE.rglob("*.py")) if TARGET_PACKAGE.is_dir() else []
    if TARGET_MODULE.is_file():
        files.append(TARGET_MODULE)
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                handlers[node.name] = node
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "register_decisions"
                    and len(node.value.args) == 1
                    and isinstance(node.value.args[0], ast.Dict)):
                for key, value in zip(node.value.args[0].keys, node.value.args[0].values):
                    if not (isinstance(key, ast.Constant) and isinstance(value, ast.Name)):
                        problems.append(f"{rel}: a registration row is not "
                                        f"'\"kind\": handler_name'")
                        continue
                    if key.value in table:
                        problems.append(f"{key.value!r} registered twice "
                                        f"({table[key.value]} and {value.id})")
                    table[key.value] = value.id
    return table, handlers, problems


# Waiver key prefix for this gate. A handler body will eventually need a legitimate
# edit — this gate outlives the refactor, so without an escape hatch the only way
# past it would be to stop running it. Waivers share the main file and the same
# MAX_WAIVERS budget, so they stay visible and stay countable.
ARM_WAIVER_PREFIX = "dispatch-arm:"


def decision_arms(ref: str, quiet: bool) -> int:
    arms, duplicated, fell_through = _baseline_arms(ref)
    table, handlers, problems = _registrations()
    waivers = load_waivers()

    if not table:
        sys.exit("no register_decisions({...}) block found — nothing to check")

    delegated, inlined, mismatched, unregistered, extra = [], [], [], [], []
    waived: list[str] = []

    for kind, arm in sorted(arms.items()):
        target = table.get(kind)
        if target is None:
            unregistered.append(kind)
            continue
        body = arm.body
        # DELEGATED: the arm was a bare `return NAME(state, top)`.
        if (len(body) == 1 and isinstance(body[0], ast.Return)
                and isinstance(body[0].value, ast.Call)
                and isinstance(body[0].value.func, ast.Name)
                and [getattr(a, "id", None) for a in body[0].value.args] == ["state", "top"]
                and not body[0].value.keywords):
            called = body[0].value.func.id
            if called == target:
                delegated.append(kind)
            else:
                mismatched.append(f"{kind}: arm called {called}(state, top) "
                                  f"but the table routes to {target}")
            continue
        # INLINED: compare the handler's body against the arm's, statement by
        # statement, allowing only the one documented prologue.
        fn = handlers.get(target)
        if fn is None:
            mismatched.append(f"{kind}: no module-level def named {target}")
            continue
        got = [_dump(s) for s in fn.body]
        want = [_dump(s) for s in body]
        if got and got[0] == ALLOWED_PROLOGUE and len(got) == len(want) + 1:
            got = got[1:]
        if got == want:
            inlined.append(kind)
        else:
            where = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b),
                         min(len(got), len(want)))
            mismatched.append(
                f"{kind}: {target} body differs from the baseline arm "
                f"(first difference at statement {where + 1} of "
                f"{len(want)}; handler has {len(got)})")

    extra = sorted(set(table) - set(arms))

    # Apply waivers last, so a waiver for an arm that in fact still matches is
    # reported as stale rather than sitting there forever implying a change.
    stale = []
    kept = []
    for entry in mismatched:
        kind = entry.split(":", 1)[0]
        reason = waivers.get(f"{ARM_WAIVER_PREFIX}{kind}")
        (waived if reason else kept).append(
            f"{kind} — {reason}" if reason else entry)
    mismatched = kept
    matched_kinds = set(delegated) | set(inlined)
    stale = sorted(
        key for key in waivers
        if key.startswith(ARM_WAIVER_PREFIX)
        and key[len(ARM_WAIVER_PREFIX):] in matched_kinds
    )

    if not quiet:
        print(f"baseline {ref}:{BASELINE_PATH} — {DISPATCH_FUNC} handled "
              f"{len(arms)} decision kinds")
        print(f"working tree — {len(table)} kinds registered across "
              f"{len({h for h in table.values()})} handlers")
        print(f"  proved by delegation (arm was `return NAME(state, top)`) : "
              f"{len(delegated)}")
        print(f"  proved by identical body (arm inlined into a handler)    : "
              f"{len(inlined)}")

    count = 0

    def report(label: str, items: list[str], hint: str = "") -> None:
        nonlocal count
        if not items:
            return
        count += len(items)
        print(f"\n{label} ({len(items)}){':' if not hint else f' — {hint}:'}")
        for item in items[:40]:
            print(f"  {item}")
        if len(items) > 40:
            print(f"  … and {len(items) - 40} more")

    report("UNREGISTERED — the baseline handled this kind, the table does not",
           unregistered, "these decisions would fall to the unknown-kind fallback")
    report("CHANGED — a handler body differs from the arm it replaced", mismatched,
           "the dispatch commit must not edit a body")
    report("REGISTERED BUT NOT IN THE BASELINE", extra,
           "a new kind is fine, but it is not covered by this proof")
    report("ARMS THAT FELL THROUGH in the baseline", fell_through,
           "ordering WAS load-bearing; a table is not equivalent — stop")
    report("KINDS HANDLED TWICE in the baseline", duplicated,
           "first-match-wins was load-bearing; a table is not equivalent — stop")
    report("REGISTRATION PROBLEMS", problems)
    report("STALE WAIVERS — waived but the body now matches the baseline arm", stale,
           "remove these from the waiver file")

    if waived and not quiet:
        print(f"\nWAIVED ({len(waived)}):")
        for item in waived:
            print(f"  {item}")

    print()
    if count:
        print(f"DISPATCH PARITY FAILED — {count} problem(s)")
        return 1
    print(f"DISPATCH PARITY OK — {len(matched_kinds)} of {len(arms)} decision kinds "
          f"route to code proved identical to the baseline chain"
          + (f", {len(waived)} waived" if waived else ""))
    return 0


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
    parser.add_argument("--decision-arms", action="store_true",
                        help="prove the decision dispatch table matches the baseline if-chain")
    parser.add_argument("--quiet", action="store_true", help="only report problems")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if args.decision_arms:
        return decision_arms(args.baseline, args.quiet)

    baseline_repeats: list[str] = []
    before = baseline_map(args.baseline, repeats=baseline_repeats)
    after, duplicates = current_map(set(baseline_repeats))
    waivers = load_waivers()

    missing = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = sorted(
        q for q in set(before) & set(after) if before[q][0] != after[q][0]
    )

    # Only this mode's waivers. The two modes share one file so the budget stays
    # countable, but a `dispatch-arm:` key is a decision KIND, never a qualname, so
    # it can never appear in `waived` here — treating it as one reported every arm
    # waiver as permanently stale and failed the gate with no way to pass it. Same
    # shape of bug as the `_`-prefix filter in load_waivers: a waiver namespace read
    # by the wrong mode is worse than no waiver.
    total_waivers = len(waivers)
    waivers = {k: v for k, v in waivers.items()
               if not k.startswith(ARM_WAIVER_PREFIX)}
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
        print(f"\nWAIVED ({len(waived)} here, {total_waivers}/{MAX_WAIVERS} in the "
              f"file):")
        for item in waived:
            print(f"  {item} — {waivers[item]}")

    # The budget is on the FILE, not on this mode, so splitting the waivers into two
    # namespaces cannot quietly double the allowance.
    if total_waivers > MAX_WAIVERS:
        problems += 1
        print(f"\nTOO MANY WAIVERS: {total_waivers} > {MAX_WAIVERS}. The layering is "
              "wrong; move a module boundary instead of waiving another function.")

    print()
    if problems:
        print(f"PARITY FAILED — {problems} problem(s)")
        return 1
    print(f"PARITY OK — {len(before)} definitions identical"
          + (f", {len(waived)} waived" if waived else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
