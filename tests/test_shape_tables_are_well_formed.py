"""The half of the coverage instrument that never needed the document (#373, 0070).

`scripts/derive_effect_shapes.py` is the reproducible half of `effect_shapes.json`, and it is
deliberately **not** in CI: CI has no copy of the SRD, which `NOTICE.md` explains is not ours
to redistribute. The consequence is that nothing tells you when it stops working.

It stopped working on 2026-08-29. [#352](https://github.com/eddiefiggie/srd-rules-engine/issues/352)
added `"mastery-push"` to `IMPLEMENTED_SECTION_SHAPES` and, in the same edit, deleted the
identical line from `EQUIPMENT_SHAPES`'s Push row — leaving a **5-tuple in a table its sweep
unpacks into six names**. Every run after that died on `ValueError: not enough values to
unpack`, and the two figures the README publishes went a day unable to be re-derived.

## Why this test exists rather than just the repaired row

Ten tables share that shape and every one of them was exposed to the same accident. Repairing
the row leaves the trap set.

**Nothing here reads the PDF**, so it runs in CI on every pull request. It cannot check that
the inventory still matches the document — only a person holding the SRD can, now with
`--check` — but it can check the structural claim that broke, which is the one that needs no
document at all.

## What it derives, and what it refuses to assume

Both sides come from the source: the arity a table's rows *have*, and the arity its sweep
*unpacks*. A pin that restated either would be a pin over itself, which is the lesson
[#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334) paid for — an assertion true
by construction over the thing it claimed to check.

And a table or a sweep this walk cannot parse **raises** rather than being skipped. A walk that
quietly ignores what it cannot read goes blind in exactly the way the assertion it replaced
did.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

SCRIPT: Final = Path(__file__).resolve().parents[1] / "scripts" / "derive_effect_shapes.py"

#: Every shape table in the script, as it stood when this file was written. A canary: a walk
#: that found none of them would pass every assertion below and look like a clean bill of
#: health, which is the failure a derived guard is most exposed to.
EXPECTED_TABLES: Final = 10


def _tree() -> ast.Module:
    return ast.parse(SCRIPT.read_text(encoding="utf-8"))


def _is_row_table(annotation: ast.expr) -> bool:
    """Whether this annotation says "a tuple of rows" — `tuple[tuple[...], ...]`.

    **The annotation and not the name.** `IMPLEMENTED_SECTION_SHAPES` ends in `_SHAPES` and is
    a `frozenset[str]`, so a name-suffix selector picks it up and then has to decide what to do
    with something it cannot read. Selecting on the shape says what is meant, and leaves the
    raise below for a genuine table this walk has stopped understanding.
    """
    if not isinstance(annotation, ast.Subscript):
        return False
    if getattr(annotation.value, "id", "") != "tuple":
        return False
    inner = annotation.slice
    if not isinstance(inner, ast.Tuple) or not inner.elts:
        return False
    first = inner.elts[0]
    return isinstance(first, ast.Subscript) and getattr(first.value, "id", "") == "tuple"


def declared_arities() -> dict[str, int]:
    """Each shape table's row arity, read off its own rows.

    From the rows rather than from the annotation: the annotation is a claim and the rows are
    the data, and it was the rows that drifted. A table whose rows disagree with each other is
    reported as the set of arities it holds, so the assertion names the real state.
    """
    found: dict[str, int] = {}
    for node in _tree().body:
        if not isinstance(node, ast.AnnAssign) or node.value is None:
            continue
        if not _is_row_table(node.annotation):
            continue
        name = getattr(node.target, "id", "")
        if not isinstance(node.value, ast.Tuple):
            raise AssertionError(
                f"{name} is annotated as a table of rows and is not a tuple literal. This walk "
                "cannot read it, and skipping what it cannot read is how the assertion it "
                "replaced went blind"
            )
        arities = set()
        for row in node.value.elts:
            if not isinstance(row, ast.Tuple):
                raise AssertionError(f"{name} holds a row this walk cannot read: {ast.dump(row)}")
            arities.add(len(row.elts))
        assert len(arities) == 1, (
            f"{name} holds rows of {sorted(arities)} elements. Every row is unpacked by the "
            "same `for` statement, so one short row is a crash for the whole table — which is "
            "exactly what #352 did to EQUIPMENT_SHAPES's Push row"
        )
        found[name] = arities.pop()
    return found


def unpacked_arities() -> dict[str, int]:
    """How many names each table's `for` statement unpacks a row into."""
    tables = set(declared_arities())
    found: dict[str, int] = {}
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Name):
            continue
        name = node.iter.id
        if name not in tables:
            continue
        if not isinstance(node.target, ast.Tuple):
            raise AssertionError(
                f"the loop over {name} does not unpack its rows into named parts, so this walk "
                "cannot tell how many it expects"
            )
        assert name not in found, (
            f"{name} is swept in two places. Both would have to agree with the table and with "
            "each other, and this guard checks one of them"
        )
        found[name] = len(node.target.elts)
    return found


def test_the_walk_finds_every_table() -> None:
    """The canary. Both halves must see the same tables, or one of them is reading nothing."""
    declared = declared_arities()
    unpacked = unpacked_arities()

    assert len(declared) == EXPECTED_TABLES, sorted(declared)
    assert set(declared) == set(unpacked), (
        f"tables with rows but no sweep: {sorted(set(declared) - set(unpacked))}; "
        f"sweeps with no table: {sorted(set(unpacked) - set(declared))}"
    )


def test_every_row_has_as_many_parts_as_its_sweep_unpacks() -> None:
    """The assertion that would have caught #352 at the pull request instead of a day later.

    `sweep_equipment` unpacks six names; the Push row held five. The script died on its next
    run, and nothing ran it.
    """
    declared = declared_arities()
    unpacked = unpacked_arities()

    mismatched = {
        name: (declared[name], unpacked[name])
        for name in declared
        if declared[name] != unpacked[name]
    }
    assert not mismatched, (
        f"{mismatched} — each entry is (row arity, names the sweep unpacks). The script raises "
        "ValueError on the first row of a table that disagrees, and it is not in CI, so "
        "nothing else would tell you"
    )


def test_the_row_that_broke_it_is_whole_again() -> None:
    """Named rather than left implicit. The general assertion above covers it, and this says
    which row, so a reader of a failing suite is not left bisecting."""
    declared = declared_arities()
    assert declared["EQUIPMENT_SHAPES"] == 6

    rows: list[ast.Tuple] = [
        row
        for node in _tree().body
        if isinstance(node, ast.AnnAssign)
        and getattr(node.target, "id", "") == "EQUIPMENT_SHAPES"
        and isinstance(node.value, ast.Tuple)
        for row in node.value.elts
        if isinstance(row, ast.Tuple)
    ]
    ids = [row.elts[0].value for row in rows if isinstance(row.elts[0], ast.Constant)]
    assert "mastery-push" in ids, "p. 90's Push lost its shape id in #352 and is back"
