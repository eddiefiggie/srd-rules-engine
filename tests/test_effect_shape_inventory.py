"""R17. The coverage claim is checked in both directions, because each catches a lie.

The inventory says which SRD v5.2.1 effect shapes exist and which this engine resolves.
`ENGINE_SHAPES` says what the engine actually resolves. Left unchecked, the two drift in
opposite ways and both drifts read as success:

* The inventory marks a shape implemented that the engine cannot resolve — coverage is
  overstated, which is the failure R17 is written to prevent.
* The engine resolves a shape the inventory never lists — the denominator is wrong, so
  the percentage is meaningless even though every number in it is real.

A test that checked one direction would pass through the other.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

import pytest

from srd_rules_engine.core.inventory import (
    ENGINE_SHAPES,
    Inventory,
    coverage_report,
    load_inventory,
)


@pytest.fixture
def inventory() -> Inventory:
    return load_inventory()


def test_every_engine_shape_is_listed_in_the_inventory(inventory: Inventory) -> None:
    """The engine may not resolve a shape the measuring stick has never heard of."""
    missing = sorted(sid for sid in ENGINE_SHAPES if inventory.by_id(sid) is None)
    assert not missing, (
        f"ENGINE_SHAPES claims shapes absent from the inventory: {missing}. "
        "Either the inventory is stale or the id is wrong; coverage is measured against "
        "the inventory, so an unlisted shape is uncounted rather than free."
    )


def test_every_engine_shape_is_marked_implemented(inventory: Inventory) -> None:
    """A shape the engine resolves must not still read as a gap."""
    understated = sorted(
        sid
        for sid in ENGINE_SHAPES
        if (shape := inventory.by_id(sid)) is not None and not shape.implemented
    )
    assert not understated, (
        f"the engine resolves these, but the inventory reports them unimplemented: {understated}"
    )


def test_no_shape_claims_coverage_the_engine_lacks(inventory: Inventory) -> None:
    """The direction that matters most: an implemented flag with nothing behind it."""
    overstated = sorted(s.id for s in inventory.implemented if s.id not in ENGINE_SHAPES)
    assert not overstated, (
        f"the inventory marks these implemented, but ENGINE_SHAPES does not claim them: "
        f"{overstated}. Marking a shape implemented is a claim about the engine, not a "
        "note about intent."
    )


def test_the_unimplemented_set_is_disclosed_rather_than_omitted(inventory: Inventory) -> None:
    """R17's disclosure half. Every shape is accounted for, and gaps are nameable."""
    assert len(inventory.implemented) + len(inventory.unimplemented) == len(inventory.shapes)
    assert inventory.unimplemented, "an engine at full coverage should retire this test"
    report = coverage_report()
    for shape in inventory.unimplemented:
        assert shape.name in report, f"{shape.name} is a gap the report does not disclose"


def test_the_inventory_states_the_scope_it_does_not_cover(inventory: Inventory) -> None:
    """A partial inventory that does not say so is indistinguishable from a complete one."""
    assert inventory.scope.strip(), "coverage_scope must state what is not yet swept"
    assert inventory.source["revision"] == "5.2.1"


#: A citation names a section of the document and a printed page, and may name the entry
#: that exhibits the shape. Deliberately strict: "cites the document" is the claim every
#: entry makes, and a pattern loose enough to accept free text would stop checking it.


def test_every_shape_cites_the_document_and_ids_are_unique(inventory: Inventory) -> None:
    """Provenance per entry, per the exclude-until-verified rule."""
    ids = [s.id for s in inventory.shapes]
    assert len(ids) == len(set(ids)), "shape ids must be unique — they are the join key"
    for shape in inventory.shapes:
        assert CITATION.match(shape.reference), f"{shape.id} cites {shape.reference!r}"


def test_body_text_shapes_name_the_entry_that_exhibits_them(inventory: Inventory) -> None:
    """A Glossary shape can cite its own heading. A shape found in spell or stat-block
    prose cannot: a bare page number into body text is not something a reader can check,
    so those must name the entry that exhibits them.

    Written against "not the Glossary" rather than against a list of section names, so a
    later sweep inherits the requirement instead of quietly escaping it.
    """
    from_body = [s for s in inventory.shapes if not s.reference.startswith("Rules Glossary")]
    assert from_body, "the spell and monster sweeps landed; their shapes should be present"
    for shape in from_body:
        assert shape.reference.endswith(")"), f"{shape.id} cites no exemplar entry"


def test_vocabulary_entries_are_recorded_with_a_reason() -> None:
    """A glossary entry set aside is a decision, and a decision states why."""
    raw = json.loads(
        resources.files("srd_rules_engine.data")
        .joinpath("effect_shapes.json")
        .read_text(encoding="utf-8")
    )
    assert raw["vocabulary"], "the glossary defines terms that are not effect shapes"
    for entry in raw["vocabulary"]:
        assert entry["reason"].strip(), f"{entry['name']} was set aside with no reason"


def test_the_weapon_mastery_set_is_complete(inventory: Inventory) -> None:
    """SRD v5.2.1 names exactly eight mastery properties (Equipment, p. 90).

    A closed set the document enumerates is a completeness claim, and a completeness claim
    gets a guard rather than a comment: these eight were the proof that the inventory was
    incomplete after four sweeps, and losing one to a refactor would be invisible otherwise.
    """
    expected = {"Cleave", "Graze", "Nick", "Push", "Sap", "Slow", "Topple", "Vex"}
    found = {s.name for s in inventory.shapes if s.kind == "weapon-mastery"}
    assert found == expected, (
        f"missing {expected - found or 'none'}, unexpected {found - expected or 'none'}"
    )


#: The eleven rules sections of SRD v5.2.1, read off its table of contents. Legal
#: Information is excluded: it is the licence page, not rules. This list is the
#: completeness claim in its checkable form — the sweeps are done when every one of these
#: is cited by at least one shape.
DOCUMENT_SECTIONS = frozenset(
    {
        "Playing the Game",
        "Character Creation",
        "Classes",
        "Character Origins",
        "Feats",
        "Equipment",
        "Spell Descriptions",
        "Rules Glossary",
        "Gameplay Toolbox",
        "Magic Items",
        "Monsters",
    }
)


#: A citation names a section of the document and a printed page, and may name the entry
#: that exhibits the shape. The alternation is built from DOCUMENT_SECTIONS rather than
#: written out, so adding a section in one place cannot leave the other behind — which is
#: how `source.section` drifted for five sweeps.
#:
#: Some exemplar names carry the document's typographic right single quote rather than the
#: ASCII apostrophe, so the class allows both. Normalising instead would edit the citation
#: away from the name the document actually prints, which is the one thing it must match.
CITATION = re.compile(
    rf"^({'|'.join(sorted(DOCUMENT_SECTIONS))}), p\. \d{{1,3}}"
    rf"(?: \([A-Z][\w'’ -]+\))?$"  # noqa: RUF001
)


def test_every_section_of_the_document_is_represented(inventory: Inventory) -> None:
    """The completeness claim, in the only form that can fail.

    Coverage was described in prose for eight builds and was wrong the whole time: two
    sections had never been swept and were never named as outstanding. Prose could not
    catch that, and neither could a test that checked the prose, because a section's name
    stays in the string once it moves from the unswept list to the swept one.

    Comparing the sections the shapes actually cite against the document's own table of
    contents is what catches it. A twelfth section appearing here means the constant is
    wrong; a missing one means a sweep is outstanding and `unswept_sections` should say so.
    """
    cited = {s.reference.split(", p. ")[0] for s in inventory.shapes}
    assert cited == DOCUMENT_SECTIONS, (
        f"not swept: {sorted(DOCUMENT_SECTIONS - cited) or 'none'}; "
        f"cited but not a known section: {sorted(cited - DOCUMENT_SECTIONS) or 'none'}"
    )


def test_the_unswept_list_agrees_with_the_sections_actually_cited(inventory: Inventory) -> None:
    """`unswept_sections` is the disclosure; the citations are the fact. They must match.

    Empty is a claim of complete coverage, and it is only true while every section of
    `DOCUMENT_SECTIONS` is cited. Whichever of the two is edited, this fails if the other
    is not.
    """
    cited = {s.reference.split(", p. ")[0] for s in inventory.shapes}
    outstanding = {name.split(" (")[0] for name in inventory.unswept_sections}
    assert outstanding == DOCUMENT_SECTIONS - cited, (
        f"unswept_sections says {sorted(outstanding) or 'nothing outstanding'}, "
        f"but the citations say {sorted(DOCUMENT_SECTIONS - cited) or 'nothing outstanding'}"
    )


def test_the_source_section_list_matches_the_citations(inventory: Inventory) -> None:
    """`source.section` is derived, not typed, and this is what keeps it that way.

    The hand-written version silently stopped updating after the Equipment sweep — five
    successive edits to it no-opped when the string was reflowed — so it named five
    sections while ten had been swept. Nothing noticed, because nothing compared it to
    anything.
    """
    cited = {s.reference.split(", p. ")[0] for s in inventory.shapes}
    listed = set(inventory.source["section"].split("; "))
    assert listed == cited, f"source.section lists {sorted(listed)}, shapes cite {sorted(cited)}"


def test_the_disclosure_surface_states_coverage_is_complete() -> None:
    """With nothing outstanding, the report must say so rather than going quiet."""
    report = coverage_report()
    assert "Every section of the document has been swept." in report


# --- The vocabulary is closed, and the rules that closed it are in the data (0013) ---


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        resources.files("srd_rules_engine.data")
        .joinpath("effect_shapes.json")
        .read_text(encoding="utf-8")
    )
    return raw


def test_kind_is_a_closed_vocabulary(inventory: Inventory) -> None:
    """Decision 0013. `kind` went unguarded through eleven sweeps and drifted from roughly
    fifteen values to nineteen with nothing noticing — a typo would have landed in the
    published artifact as a new category.

    Checked in both directions. A one-way check on "every kind is declared" would let a
    retired value sit in the declaration forever, which is the same drift running backwards.
    """
    declared = set(_raw()["kind_values"])
    used = {shape.kind for shape in inventory.shapes}

    assert not used - declared, f"kinds used but not declared: {sorted(used - declared)}"
    assert not declared - used, f"kinds declared but unused: {sorted(declared - used)}"


def test_the_criteria_that_decided_shape_from_content_are_in_the_artifact() -> None:
    """0013's Q2 finding: the exclusion criteria were applied across eleven sweeps while
    living only in generator comments, so no consumer of the artifact could see them and
    no auditor could check them. Prose in a file nobody publishes is not a record.
    """
    criteria = _raw()["criteria"]
    assert criteria, "the rules that decided shape from content must ship with the data"

    for entry in criteria:
        assert entry["id"].strip()
        assert entry["rule"].strip(), f"{entry['id']} states no rule"
        assert entry["decided_by"].strip(), f"{entry['id']} names no decision"

    ids = [entry["id"] for entry in criteria]
    assert len(ids) == len(set(ids)), "criterion ids are the join key and must be unique"


def test_an_entry_set_aside_carries_the_reason_that_actually_applied_to_it() -> None:
    """The defect 0013 found: all nineteen `vocabulary` reasons recorded the glossary-term
    exclusion while a second, different criterion was being applied elsewhere. One reason
    repeated across every entry is indistinguishable from a reason nobody chose.
    """
    vocabulary = _raw()["vocabulary"]
    reasons = {entry["reason"] for entry in vocabulary}
    assert len(reasons) > 1, (
        "every entry carries the same reason, which is what a default looks like when it "
        "has quietly become the only answer"
    )

    heroic = next(e for e in vocabulary if e["name"] == "Heroic Inspiration")
    assert "die-replacement" in heroic["reason"], (
        "a mechanical entry set aside must say which shape subsumes it, or it reads as "
        "having been dropped"
    )


def test_nothing_in_the_engine_branches_on_a_shapes_kind() -> None:
    """Decision 0019: `kind` is a filing label, not a model.

    That claim is only worth making if it stays true, and the way it stops being true is
    somebody writing `if shape.kind == ...` when a shortcut needs a category. The behaviour
    a branch would be reaching for is already modelled in typed code — `ConditionEffects`
    says what Prone changes — so a branch here would be a second, weaker description beside
    the real one.

    Scoped to `Shape.kind` specifically: `Finding.kind`, `D20Test.kind` and `Effect.kind` are
    different types on different objects and are compared freely.
    """
    import ast
    from pathlib import Path

    inventory_source = Path("src/srd_rules_engine/core/inventory.py")
    offenders: list[str] = []

    for path in sorted(Path("src/srd_rules_engine").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for operand in (node.left, *node.comparators):
                if (
                    isinstance(operand, ast.Attribute)
                    and operand.attr == "kind"
                    and isinstance(operand.value, ast.Name)
                    and operand.value.id in {"shape", "s", "entry"}
                ):
                    offenders.append(f"{path}:{node.lineno}")

    assert not offenders, (
        f"{offenders} compare a shape's kind. 0019 makes it a filing label for coverage "
        "measurement; behaviour belongs in typed code, not in a catalogue string"
    )
    assert "decision 0019" in inventory_source.read_text(encoding="utf-8")
