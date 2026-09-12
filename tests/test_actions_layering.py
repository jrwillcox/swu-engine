"""The ``actions`` package is layered, and these tests are what keeps it that way.

``engine/actions.py`` was one 24,788-line module for a reason that was never
tidiness: the engine, the ability DSL and the card modules are mutually recursive,
and the single file papered over that with **319 function-local imports** — 131 into
``abilities.resolver``, 79 into ``abilities.registry``. ``abilities/resolver.py``
says so in a comment: *"All imported inside the functions that use them at runtime,
to break the state/actions import cycle."*

Splitting the file into layers is only worth anything if the layering holds, and a
layering with no test decays back into a cycle one convenient import at a time.
These tests parse the package with ``ast`` and assert on the edge set, so a
module-scope import that would recreate the cycle fails here rather than in a
confusing ``ImportError`` months later.

Note what is *not* asserted: function-local imports are still allowed. Some are
legitimate (a genuinely cyclic dependency on the ability registry, resolved at call
time), and banning them outright would be a bigger change than this refactor. What
must not happen is a **module-scope** edge that closes a cycle.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "src" / "swu" / "engine" / "actions"

# Bottom-up. A module may import from any module EARLIER in this list and from no
# module later in it. Derived from the measured dependency graph, not chosen by
# taste: each layer's transitive closure was self-contained, which is why the
# extraction needed no upward reaches at all.
LAYERS = [
    "base",
    # `dispatch` is deliberately near the floor: it holds the decision-kind table and
    # imports nothing, which is what lets a family module depend on it instead of the
    # dispatcher depending on every family. If it ever imports a family, the fan-out
    # it was built to remove is back.
    "dispatch",
    "stats",
    "costs",
    "damage",
    "zones",
    "flow",
    # `shared` holds the primitives that two or more DECISION families need, so no
    # family can own one: moving such a helper to a consumer would only reverse the
    # arrow. It sits above `flow` because two of them use it and below `combat`
    # because none of them needs the attack pipeline. Anything here that grows a
    # dependency on a decision family belongs in that family instead.
    "shared",
    "combat",
    # `observers` sits directly below `turn` because the turn machinery is one of its
    # callers: _start_action_phase and _regroup_rollover both fire scheduled effects,
    # and _ready_all_cards notes every unit it readies. The 19 `_fire_*` functions run
    # from `apply` in a fixed order that is behaviour rather than style, so they live
    # in one module and move as one block or not at all.
    "observers",
    "turn",
    # ---- the decision families ------------------------------------------------
    # One module per mechanic family, each claiming its own decision kinds from
    # `dispatch`. They rank BELOW `_legacy` for the same reason the kernel modules do:
    # `_legacy` back-imports whatever has already left it, so every reference points
    # downward at every commit and this test passes throughout the migration rather
    # than only at the end of it. When `_legacy` is empty it goes, and these are the
    # top of the package.
    #
    # The order among them is the topological order of the push graph, which is
    # acyclic -- measured, not assumed. `push_modal` is called from `sacrifice`, so
    # `modal` must rank lower; `push_play_from_hand` is called from `capture`, `deck`
    # and `discard`, so `hand` must rank lower than all three. That ordering is what
    # makes a push call an ordinary downward import, which is why no dispatch registry
    # for `push_*` is needed.
    "targeting",
    "upgrades",
    "modal",
    # `distribute` is the damage DECISIONS -- where player-directed damage lands. The
    # kernel's `damage` module, far below, is what actually happens when it lands. Two
    # modules, one word, and the distinction is the point: this one never deals damage.
    "distribute",
    "scheduling",
    # `hand` covers both playing from an unusual source AND the opponent-facing
    # decisions (say_no, opponent_ready, look-at-hand). Splitting those two apart was
    # tried and measured: they are mutually recursive, because SayNo.apply plays a card
    # from hand while PlayFromHand pushes an opponent-ready decision. Its docstring
    # records the measurement, so the seam does not get re-litigated.
    "hand",
    "capture",
    "deck",
    "tokens",
    "sacrifice",
    "discard",
    "reveal",
    "_legacy",
    "api",
]


def _modules() -> dict[str, ast.Module]:
    out = {}
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG).with_suffix("").as_posix().replace("/", ".")
        out[rel] = ast.parse(path.read_text(encoding="utf-8"))
    return out


def _module_scope_imports(tree: ast.Module) -> list[str]:
    """Dotted module names imported at module scope (not inside any def/class)."""
    names = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
    return names


def test_no_module_scope_import_of_the_abilities_layer():
    """The cycle this refactor exists to break must not be reintroduced.

    ``swu.abilities`` imports back into ``swu.engine.actions``, so a module-scope
    import in this direction closes the loop. The card-ability registry is reached
    from inside functions instead, which is deliberate rather than accidental.
    """
    offenders = {}
    for name, tree in _modules().items():
        bad = [m for m in _module_scope_imports(tree) if m.startswith("swu.abilities")]
        if bad:
            offenders[name] = bad
    assert not offenders, (
        "module-scope import of swu.abilities recreates the import cycle:\n"
        + "\n".join(f"  {k}: {v}" for k, v in offenders.items())
        + "\nImport it inside the function that uses it, as the rest of the package does."
    )


def test_intra_package_imports_point_strictly_downward():
    """No module imports a module above it in the layering."""
    rank = {name: i for i, name in enumerate(LAYERS)}
    violations = []
    for name, tree in _modules().items():
        if name == "__init__":
            continue  # the facade sits above everything by definition
        if name not in rank:
            continue
        for imported in _module_scope_imports(tree):
            if not imported.startswith("swu.engine.actions."):
                continue
            target = imported[len("swu.engine.actions."):]
            if target not in rank:
                continue
            if rank[target] >= rank[name]:
                violations.append(f"{name} imports {target} (same layer or above)")
    assert not violations, (
        "the layering is broken:\n  " + "\n  ".join(violations)
        + "\nEither move the shared code down into a lower module, or import it "
          "inside the function that needs it."
    )


def test_the_intra_package_import_graph_is_acyclic():
    """Belt and braces: no cycle among the package's own modules, whatever the order.

    ``test_intra_package_imports_point_strictly_downward`` enforces a specific
    order; this one catches a cycle among modules that the LAYERS list does not yet
    mention, so a newly added module cannot quietly form one.
    """
    edges: dict[str, set[str]] = {}
    for name, tree in _modules().items():
        targets = set()
        for imported in _module_scope_imports(tree):
            if imported.startswith("swu.engine.actions."):
                targets.add(imported[len("swu.engine.actions."):])
        edges[name] = targets

    colour: dict[str, int] = {}
    cycle: list[str] = []

    def visit(node: str, path: list[str]) -> bool:
        if colour.get(node) == 2:
            return False
        if colour.get(node) == 1:
            cycle.extend(path[path.index(node):] + [node])
            return True
        colour[node] = 1
        for nxt in sorted(edges.get(node, ())):
            if nxt in edges and visit(nxt, path + [node]):
                return True
        colour[node] = 2
        return False

    for start in sorted(edges):
        if visit(start, []):
            break

    assert not cycle, "import cycle inside the actions package: " + " -> ".join(cycle)


@pytest.mark.parametrize("module", ["base", "dispatch", "stats"])
def test_the_bottom_modules_depend_on_nothing_in_the_package(module):
    """``base`` and ``stats`` are the floor; 206 definitions rest on ``base`` alone.

    If either grows a dependency on a sibling, every module above it inherits that
    dependency and the layering stops being a layering.
    """
    tree = _modules().get(module)
    if tree is None:
        pytest.skip(f"{module} not present")
    intra = [m for m in _module_scope_imports(tree)
             if m.startswith("swu.engine.actions.")]
    assert not intra, f"{module} should sit at the bottom but imports {intra}"
