"""The layer boundary is a fact about the import graph, not a description of intent.

`tests/test_core_has_no_runtime_dependencies.py` guards what the *package* pulls in
from outside. It cannot see how the package's own layers depend on each other, and
that is where the more dangerous violation lives: a core module that imports an
adapter breaks R33's promise while `[project].dependencies` still reads empty. The
machine-readable form of the promise stays true while the promise does not.

Two rules, both visible here and in neither a dependency list nor a review:

1. **Nothing in `core` imports from an outer layer** (R33). This is the direction that
   silently falsifies the no-LLM-dependency claim.
2. **Nothing outside `core` imports a `core` submodule** (R34). Outer layers use what
   `core` re-exports, so "the adapters are built over the same contract" is checkable
   rather than aspirational.

Relative imports are resolved before the rules are applied, because `from ..loop import
x` inside the core is the same violation as the absolute form and would otherwise walk
straight past a naive scan.

**This guard is a floor, not a proof.** It walks the whole syntax tree, so an import
deferred inside a function body is caught like any other — but a *dynamic* import is
not: `importlib.import_module(name)`, `__import__(name)`, and any string-driven loader
name the target at runtime, where no static scan can see it. That limit is recorded in
`docs/decisions/0011-module-layout-and-versioning.md`, which describes it slightly more
broadly than it turned out to be.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE = "srd_rules_engine"

CORE = "core"
OUTER_LAYERS = frozenset({"loop", "memory", "adapters"})

# The core's public surface: the one name an outer layer may import.
CORE_SURFACE = f"{PACKAGE}.{CORE}"


def _source_files() -> list[Path]:
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _module_name(path: Path) -> str:
    """`src/srd_rules_engine/core/ledger.py` -> `srd_rules_engine.core.ledger`."""
    parts = list(path.relative_to(SRC_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_name(path: Path) -> str:
    """The package a relative import inside this file resolves against.

    A module and its package's `__init__` resolve against the same package, which is
    why the filename is dropped in both cases rather than special-cased.
    """
    return ".".join(path.relative_to(SRC_ROOT).parts[:-1])


def _layer_of(module: str) -> str | None:
    """`srd_rules_engine.core.ledger` -> `core`. Anything outside the package -> None."""
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != PACKAGE:
        return None
    return parts[1]


def _absolute(package: str, module: str | None, level: int) -> str:
    """Resolve a possibly-relative import target to its absolute dotted path."""
    if level == 0:
        return module or ""
    base = package.split(".")
    if level > 1:
        base = base[: -(level - 1)]
    prefix = ".".join(base)
    return f"{prefix}.{module}" if module else prefix


def _import_targets(tree: ast.Module, package: str) -> list[str]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            targets.append(_absolute(package, node.module, node.level))
    return targets


def _violations_in(module: str, package: str, tree: ast.Module) -> list[str]:
    layer = _layer_of(module)
    found: list[str] = []
    for target in _import_targets(tree, package):
        target_layer = _layer_of(target)
        if target_layer is None:
            continue
        if layer == CORE and target_layer in OUTER_LAYERS:
            found.append(
                f"{module} imports {target} — the core may not import from the "
                f"{target_layer} layer (R33)"
            )
        elif layer != CORE and target_layer == CORE and target != CORE_SURFACE:
            found.append(
                f"{module} imports {target} — only {CORE_SURFACE} itself may be imported "
                f"from outside the core (R34)"
            )
    return found


def _check_source(module: str, package: str, source: str) -> list[str]:
    """Run the rules against fabricated source, so the tree need not be corrupted."""
    return _violations_in(module, package, ast.parse(source))


# --- The guard, over the real tree ------------------------------------------------


def test_the_scan_is_running() -> None:
    """A scan of zero modules passes vacuously, which is worse than no scan at all."""
    files = _source_files()
    assert len(files) >= 4, f"Only {len(files)} modules found — the scan is not running."


def test_no_layer_boundary_violations() -> None:
    findings: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        findings.extend(_violations_in(_module_name(path), _package_name(path), tree))

    assert not findings, (
        "Layer boundaries are enforced here, not by convention:\n  "
        + "\n  ".join(findings)
        + f"\n\nThe core imports nothing outward, and outer layers use {CORE_SURFACE} "
        "rather than reaching into its submodules."
    )


# --- The rules themselves, over fabricated sources ---------------------------------


def test_core_importing_an_outer_layer_is_refused() -> None:
    findings = _check_source(
        f"{PACKAGE}.core.adjudicate",
        f"{PACKAGE}.core",
        f"from {PACKAGE}.loop import turn\n",
    )
    assert len(findings) == 1
    assert f"{PACKAGE}.core.adjudicate" in findings[0]
    assert f"{PACKAGE}.loop" in findings[0]


def test_core_importing_an_outer_layer_by_relative_path_is_refused() -> None:
    findings = _check_source(
        f"{PACKAGE}.core.adjudicate", f"{PACKAGE}.core", "from ..memory import store\n"
    )
    assert len(findings) == 1
    assert f"{PACKAGE}.memory" in findings[0]


def test_outer_layer_importing_a_core_submodule_is_refused() -> None:
    findings = _check_source(
        f"{PACKAGE}.loop.turn", f"{PACKAGE}.loop", f"from {PACKAGE}.core.adjudicate import rule\n"
    )
    assert len(findings) == 1
    assert f"{PACKAGE}.core.adjudicate" in findings[0]


def test_outer_layer_importing_the_core_surface_is_allowed() -> None:
    assert not _check_source(
        f"{PACKAGE}.loop.turn", f"{PACKAGE}.loop", f"from {PACKAGE}.core import Ruling\n"
    )


def test_memory_importing_the_core_surface_is_allowed() -> None:
    assert not _check_source(
        f"{PACKAGE}.memory.store", f"{PACKAGE}.memory", f"import {PACKAGE}.core\n"
    )


def test_core_importing_its_own_submodule_is_allowed() -> None:
    """The submodule rule binds outer layers only; the core is not sealed against itself."""
    assert not _check_source(
        f"{PACKAGE}.core.adjudicate",
        f"{PACKAGE}.core",
        f"from {PACKAGE}.core.ledger import append\n",
    )


def test_the_package_root_may_use_the_core_surface_but_not_reach_past_it() -> None:
    package_root = PACKAGE
    assert not _check_source(package_root, PACKAGE, f"from {PACKAGE}.core import Ruling\n")
    assert _check_source(package_root, PACKAGE, f"from {PACKAGE}.core.ledger import append\n")


def test_every_violation_is_reported_not_just_the_first() -> None:
    findings = _check_source(
        f"{PACKAGE}.core.adjudicate",
        f"{PACKAGE}.core",
        f"from {PACKAGE}.loop import turn\nfrom {PACKAGE}.memory import store\n",
    )
    assert len(findings) == 2


def test_an_import_deferred_inside_a_function_is_still_caught() -> None:
    """Deferring the import postpones the dependency, not the violation."""
    findings = _check_source(
        f"{PACKAGE}.core.adjudicate",
        f"{PACKAGE}.core",
        f"def build():\n    from {PACKAGE}.loop import turn\n    return turn\n",
    )
    assert len(findings) == 1
    assert f"{PACKAGE}.loop" in findings[0]


def test_imports_outside_the_package_are_ignored() -> None:
    assert not _check_source(
        f"{PACKAGE}.core.adjudicate", f"{PACKAGE}.core", "import json\nfrom pathlib import Path\n"
    )
