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

import importlib.util
import json
import re
from importlib import resources
from pathlib import Path
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


REPO_ROOT = Path(__file__).resolve().parents[1]


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

    Both branching forms are checked. A `match` on a string label is the more natural way to
    write this in modern Python and is not an `ast.Compare`, so a guard that only walked
    comparisons would pass while the thing it exists to catch sat in the tree.

    Scoped to `Shape.kind` specifically: `Finding.kind`, `D20Test.kind`, `Effect.kind` and
    `Fact.kind` are different types on different objects and are compared freely.
    """
    import ast
    from pathlib import Path

    def reads_a_shapes_kind(node: ast.expr) -> bool:
        # Keyed on the receiver's name, because the alternative is type inference. A branch
        # written with a differently-named variable would pass — stated in 0019 rather than
        # implied, and these are the names this codebase actually binds a shape to.
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "kind"
            and isinstance(node.value, ast.Name)
            and node.value.id in {"shape", "s", "entry"}
        )

    offenders: list[str] = []

    for path in sorted(Path("src/srd_rules_engine").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands: list[ast.expr] = [node.left, *node.comparators]
            elif isinstance(node, ast.Match):
                operands = [node.subject]
            else:
                continue
            if any(reads_a_shapes_kind(operand) for operand in operands):
                offenders.append(f"{path}:{node.lineno}")

    assert not offenders, (
        f"{offenders} branch on a shape's kind. 0019 makes it a filing label for coverage "
        "measurement; behaviour belongs in typed code, not in a catalogue string"
    )


def test_the_shape_field_says_what_kind_is_for() -> None:
    """The guard above stops a branch appearing. It cannot stop somebody assuming `kind`
    means something operational before they write one, and the field's own docstring is
    where that assumption gets corrected."""
    from pathlib import Path

    source = Path("src/srd_rules_engine/core/inventory.py").read_text(encoding="utf-8")
    assert "decision 0019" in source


# --- The generator and the data it generated (#138) -----------------------------------


def test_the_glossary_claims_agree_with_the_generator_that_writes_them() -> None:
    """`derive_effect_shapes.py` is the stated source of `effect_shapes.json`, so re-running
    it must not change what the engine claims.

    It would have. `KINDS` carried `("sense", False)` for **Blindsight and Darkvision** while
    the shipped data said `True` for both — claimed in the JSON by hand when `can_see` and
    `effective_light` landed, and never written back to the generator. Regenerating would have
    silently un-claimed two shapes and dropped coverage by two, with every other guard green:
    `test_every_engine_shape_is_marked_implemented` compares `ENGINE_SHAPES` against the
    **data**, and the data was right. Nothing compared the data against the thing that writes
    it.

    This reads `KINDS` directly rather than regenerating, because regenerating needs the SRD
    PDF and CI has no copy of it (`NOTICE.md`). The flag is the half that can be checked
    without the document — and the flag is the half that drifted.
    """
    spec = importlib.util.spec_from_file_location(
        "derive_effect_shapes", REPO_ROOT / "scripts" / "derive_effect_shapes.py"
    )
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    inventory = load_inventory()
    disagreements = []
    for name, (_kind, implemented) in generator.KINDS.items():
        shape = inventory.by_id(generator.slug(name))
        if shape is None:
            continue  # `vocabulary` entries are defined in the generator, not filed as shapes
        if shape.implemented != implemented:
            disagreements.append(
                f"{shape.id}: data says implemented={shape.implemented}, KINDS says {implemented}"
            )

    assert not disagreements, (
        "re-running scripts/derive_effect_shapes.py would change what the engine claims:\n  "
        + "\n  ".join(disagreements)
        + "\n\nClaim a shape in BOTH places — the generator's KINDS and the shipped "
        "effect_shapes.json — or the next regeneration silently rewrites coverage."
    )


# --- 0033: a glossary entry is an index, not a shape's boundary (#228) -------------------

#: Entries whose *glossary body* states no mechanic, and which are claimed anyway because the
#: document states the mechanic elsewhere. This is the set 0033 clause 1 governs.
CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY = {
    "bright-light": 'p. 11: "Bright Light lets most creatures see normally."',
    "damage": "p. 17, and the damage rules the glossary entry points at.",
    "damage-types": "p. 17: the entry says types have no rules of their own, and points on.",
    "healing": "p. 17, and the Hit Point rules the glossary entry points at.",
    "save": "the D20 Test rules — the entry renames a saving throw rather than defining one.",
}

#: Asserted **unclaimed**, so this guard fails in both directions. Without it the test is
#: satisfiable by claiming everything, which is exactly the vacuous claim 0033 rejects.
#: Each is unclaimed for a reason that predates 0033 and is unaffected by it: these four have
#: no implementation at all.
NOT_CLAIMED_AND_NOT_BECAUSE_OF_THIS_RULE = ("bloodied", "occupied-space", "temporary-hit-points")


def test_a_definitional_glossary_body_does_not_decide_whether_a_shape_is_claimed(
    inventory: Inventory,
) -> None:
    """0033 clause 1, pinned. #228 read Bright Light's glossary entry — "Bright Light is
    normal illumination" — as the shape's whole content, and concluded that 211 of 211 was
    unreachable because some entries state no mechanic.

    The entry is not the shape. **p. 11** states the mechanic: *"Bright Light lets most
    creatures see normally"* — Bright Light imposes nothing, and `OBSCUREMENT_BY_LIGHT`
    produces exactly that. A shape's content is what the document states about it anywhere.

    Before 0033 this set was split four to one for no stated reason: `healing`, `save`,
    `damage` and `damage-types` are as definitional in the glossary as `bright-light` and
    were all claimed. The rule was already being followed; only the one entry where nobody
    noticed it applied was left out. That is what this guard stops from happening twice.
    """
    claims = {sid: inventory.by_id(sid) for sid in CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY}
    absent = sorted(sid for sid, shape in claims.items() if shape is None)
    assert not absent, (
        f"{absent} are named by this guard and are not in the inventory at all. A renamed id "
        "makes the guard inspect nothing while still passing, which is the failure mode it "
        "exists to prevent — fix the id here rather than dropping the entry."
    )

    unclaimed = sorted(
        sid for sid, shape in claims.items() if shape is not None and not shape.implemented
    )
    assert not unclaimed, (
        f"{unclaimed} are claimed on text outside their glossary entry (0033 clause 1) and "
        "the inventory no longer claims them. If a claim was withdrawn, withdraw the record "
        "too — a definitional glossary body is not a reason, and it was not one for the four "
        "of these that were already claimed before #228 asked about the fifth."
    )


def test_the_rule_does_not_license_claiming_everything(inventory: Inventory) -> None:
    """The counter-direction. 0033 clause 2 keeps clause 1 asymmetric: text outside an entry
    may *supply* a consequence, never *enlarge* the bar — and nothing is claimed for merely
    being modelled. These three have no implementation at all, so a rule that claimed them
    would be the vacuous claim #228 offered as its first option and 0033 rejected.
    """
    counter = {sid: inventory.by_id(sid) for sid in NOT_CLAIMED_AND_NOT_BECAUSE_OF_THIS_RULE}
    absent = sorted(sid for sid, shape in counter.items() if shape is None)
    assert not absent, (
        f"{absent} are named by this guard and are not in the inventory at all. The "
        "counter-direction is only a counter-direction while its ids resolve."
    )

    wrongly_claimed = sorted(
        sid for sid, shape in counter.items() if shape is not None and shape.implemented
    )
    assert not wrongly_claimed, (
        f"{wrongly_claimed} are claimed and nothing in the engine resolves them. 0033 does "
        "not license claiming a shape for being modelled — it says where a claimed shape's "
        "consequence may be *read from*, which is a different question."
    )


def test_the_page_bright_lights_claim_rests_on_is_asserted_against_the_document() -> None:
    """0033 clause 3: a claim resting on text outside the entry cites the page and asserts
    the sentence. Presence, not truth — the verifier needs the PDF and CI has no copy."""
    verifier = (REPO_ROOT / "scripts" / "verify_d20_rules.py").read_text(encoding="utf-8")
    assert "Bright Light lets most creatures see normally" in verifier


def test_the_absence_weapon_attacks_declassification_rests_on_is_asserted() -> None:
    """0034 clause 3: a claim resting on text outside the entry cites the page and asserts
    the sentence (0033 clause 3), so a **de**classification resting on the *absence* of such
    text must assert the absence. Presence, not truth — the verifier needs the PDF and CI has
    no copy.

    An absence is the claim that decays most quietly: nothing goes red when a term the
    document did not use starts being used. `DOCUMENT_CLAUSES` is the table that holds it,
    and this guard exists so deleting the table is visible to CI, which cannot run it.

    The control row is checked by name too. It is the part a later reader is most likely to
    prune as redundant — it asserts a term the engine does not depend on — and pruning it
    would leave the count assertion unable to tell a substantially intact extraction from a
    partially degraded one.
    """
    verifier = (REPO_ROOT / "scripts" / "verify_d20_rules.py").read_text(encoding="utf-8")
    assert "DOCUMENT_CLAUSES" in verifier, (
        "the document-wide clause table is gone. 0034 clause 3 rests on it: without an "
        "asserted count there is nothing to go red when the SRD starts using the term."
    )
    assert "A weapon attack is an attack roll made with a weapon" in verifier
    assert "An attack roll is a D20 Test that represents making an attack with a weapon" in verifier
    assert "This is a CONTROL" in verifier, (
        "the control row was removed. The count assertion alone cannot distinguish an "
        "intact extraction from a partially degraded one, which is the case it guards."
    )


#: 0034 clause 2: the three cases p. 177's own entry enumerates, and where each one lands.
#: The value is the mechanism that decides it — which is the whole content of the rule, since
#: all three entries are phrased identically ("an attack roll made with/as part of ...").
THE_THREE_CASES_OF_AN_ATTACK_ROLL: dict[str, str] = {
    "spell-attack": "p. 106 gives it a bonus formula `attack-roll` does not state",
    "unarmed-strike": "p. 190 gives it three effect options, a damage expression and a save",
}


def test_a_renamed_mechanism_with_no_consumers_is_vocabulary_and_one_with_them_is_not(
    inventory: Inventory,
) -> None:
    """0034, pinned in both directions.

    `weapon-attack` is vocabulary because SRD 5.2 defines the term on p. 191 and never uses
    it: three occurrences in the document, two in its own entry and one on p. 217 that is a
    noun and a verb. It renames `attack-roll` with a parameter fixed and gates nothing.

    **The counter-direction is the point.** "Renames a parent with a parameter fixed"
    describes `spell-attack` word for word — *"A spell attack is an attack roll made as part
    of a spell"* — and it is a shape, correctly, because p. 106 gives it a formula of its
    own. A guard that only asserted `weapon-attack` had moved would be satisfied by moving
    every sub-case to vocabulary, which is the deflation failure mirroring the inflation
    0034 clause 1 avoids. So the two that stay are asserted here too.
    """
    moved = inventory.by_id("weapon-attack")
    assert moved is None, (
        "`weapon-attack` is back in `shapes`. 0034 files it as vocabulary: the document "
        "defines the term on p. 191 and never uses it, so there is no consequence to "
        "produce and nothing to claim. Re-read the record before moving it back."
    )
    assert "Weapon Attack" in inventory.vocabulary, (
        "`weapon-attack` is in neither `shapes` nor `vocabulary`. Silent omission is the "
        "exact failure R17 names — an entry set aside stays visible, with its reason."
    )

    for sid, mechanism in THE_THREE_CASES_OF_AN_ATTACK_ROLL.items():
        shape = inventory.by_id(sid)
        assert shape is not None, (
            f"`{sid}` is no longer a shape. 0034 clause 2 turns on consumers, not on how an "
            f"entry is phrased: {mechanism}, so it differs from `attack-roll` in mechanism "
            "rather than in a parameter and stays a shape."
        )
