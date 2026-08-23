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
SECTIONS = "Rules Glossary|Spell Descriptions|Monsters|Magic Items|Equipment|Classes|Feats"
CITATION = re.compile(rf"^({SECTIONS}), p\. \d{{1,3}}(?: \([A-Z][\w' -]+\))?$")


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
