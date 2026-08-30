"""p. 177's untrained-armour Disadvantage, which is not save-only (#367, 0064).

> If you wear Light, Medium, or Heavy armor and lack training with it, you have Disadvantage on
> **any D20 Test that involves Strength or Dexterity**, and you can't cast spells.

0063 built the casting prohibition and disclosed this, because `D20Test.ability` was passed by
the six save sites only. It is passed by every site now, which is 0054's work one level wider.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from srd_rules_engine.core import Combatant, EncounterState
from srd_rules_engine.core.adjudicate import Proposal, _as_this_creature_rolls
from srd_rules_engine.core.d20 import D20Test, TestKind
from srd_rules_engine.core.equipment import Carriage, Carried, Item

PLATE = Item(id="fixture:plate", weight=65.0, is_armour=True)


def creature(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": {"str": 12, "dex": 12, "con": 12, "wis": 12},
        "proficiency_bonus": 2,
        "equipment": (Carried(PLATE, Carriage.WORN),),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def rolled(actor: Combatant, *, kind: TestKind, ability: str | None) -> Proposal:
    state = EncounterState.new([actor]).with_initiative({"pc": 20})
    proposal = Proposal(test=D20Test(kind=kind, ability=ability, target=10, target_basis="b"))
    return _as_this_creature_rolls(state, "pc", proposal)


@pytest.mark.parametrize("kind", [TestKind.ATTACK, TestKind.CHECK, TestKind.SAVE])
@pytest.mark.parametrize("ability", ["str", "dex"])
def test_any_d20_test_of_strength_or_dexterity_is_hampered(kind: TestKind, ability: str) -> None:
    """ "**Any** D20 Test" — attacks and ability checks as much as saves, which is the whole
    difference from p. 187's Restrained and p. 181's Dodge."""
    after = rolled(creature(), kind=kind, ability=ability)
    assert after.test is not None
    assert after.test.has_disadvantage


@pytest.mark.parametrize("ability", ["con", "wis", "int", "cha", None])
def test_no_other_ability_is_touched(ability: str | None) -> None:
    """p. 177 names Strength and Dexterity and no others, so a Constitution save from the same
    creature in the same armour is an ordinary roll — and so is a test of no ability."""
    after = rolled(creature(), kind=TestKind.SAVE, ability=ability)
    assert after.test is not None
    assert not after.test.has_disadvantage


def test_training_with_what_you_wear_removes_it() -> None:
    """The negative case, changing one field."""
    trained = creature(armour_training=frozenset({PLATE.id}))
    after = rolled(trained, kind=TestKind.ATTACK, ability="str")
    assert after.test is not None
    assert not after.test.has_disadvantage


def test_armour_you_are_not_wearing_hampers_nothing() -> None:
    packed = creature(equipment=(Carried(PLATE, Carriage.STOWED),))
    after = rolled(packed, kind=TestKind.ATTACK, ability="str")
    assert after.test is not None
    assert not after.test.has_disadvantage


def test_it_cancels_against_advantage_the_rule_granted() -> None:
    """p. 8. The flag accumulates onto what the rule itself granted rather than replacing it,
    so a source on the other side can still cancel it."""
    state = EncounterState.new([creature()]).with_initiative({"pc": 20})
    granted = Proposal(
        test=D20Test(
            kind=TestKind.ATTACK, ability="str", target=10, target_basis="b", has_advantage=True
        )
    )
    after = _as_this_creature_rolls(state, "pc", granted)
    assert after.test is not None
    assert after.test.has_advantage and after.test.has_disadvantage


def test_it_stacks_with_the_save_only_rules_rather_than_replacing_them() -> None:
    """A Dodging creature in untrained armour: p. 181 grants Advantage on its Dexterity saves
    and p. 177 imposes Disadvantage on them, and p. 8 cancels the pair."""
    from srd_rules_engine.core.actions import ActionBudget
    from srd_rules_engine.core.position import Speeds

    dodging = creature(actions=ActionBudget(dodging=True), speeds=Speeds(walk=30))
    after = rolled(dodging, kind=TestKind.SAVE, ability="dex")
    assert after.test is not None
    assert after.test.has_advantage and after.test.has_disadvantage


# --- The guard that keeps a new test site from forgetting ----------------------------------------


def test_every_d20_test_the_core_builds_names_its_ability() -> None:
    """Widened from saves to **every kind** (0064).

    0054's version asked it of `TestKind.SAVE` only, because that was all the rules of the day
    needed. p. 177 reaches attacks and checks, so a site that omits the ability now silently
    escapes a rule rather than only the three save ones.

    `core.report` is excluded and named: it reconstructs a `D20Test` from a ledger entry rather
    than building one for a rule, and the ledger carries no ability.
    """
    missing: list[str] = []
    checked = 0
    for path in pathlib.Path("src/srd_rules_engine").rglob("*.py"):
        if path.name == "report.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "D20Test"):
                continue
            checked += 1
            if "ability" not in {k.arg for k in node.keywords}:
                missing.append(f"{path.stem}:{node.lineno}")

    assert checked >= 11, f"only {checked} D20 tests found in the core; the walk is looking wrong"
    assert not missing, (
        f"these build a D20 test without naming its ability: {missing}. p. 177 hampers any "
        "test of Strength or Dexterity, so a site that omits it escapes the rule silently."
    )


def test_the_disclosure_is_retired_because_the_rule_is_built() -> None:
    """Paired with the build, as AGENTS.md asks. The Shield clause stays disclosed — it needs
    an AC derived from what is worn, which nothing models."""
    from srd_rules_engine.core import read

    state = EncounterState.new([creature()]).with_initiative({"pc": 20})
    situation = read(state, "pc").situation
    assert situation is not None
    # The string rather than a constant: the constant is gone, which is the removal itself.
    assert "untrained-armour-disadvantage-not-applied" not in situation.unenforced_clauses

    after = rolled(creature(), kind=TestKind.ATTACK, ability="str")
    assert after.test is not None
    assert after.test.has_disadvantage, "and the rule that replaced it is enforced"


def test_disadvantage_the_rule_granted_survives_too() -> None:
    """The other side of the accumulation, and it was missing.

    A corruption proof showed `has_disadvantage=test.has_disadvantage or disadvantage` was
    untested: every case here already had the transform contributing the Disadvantage, so
    dropping the `or` changed nothing. This is a rule that granted one — p. 89's Heavy
    property, say — on a creature the transform gives Advantage to instead.
    """
    from srd_rules_engine.core.actions import ActionBudget
    from srd_rules_engine.core.position import Speeds

    dodging = creature(
        equipment=(),  # no armour, so the transform contributes only p. 181's Advantage
        actions=ActionBudget(dodging=True),
        speeds=Speeds(walk=30),
    )
    state = EncounterState.new([dodging]).with_initiative({"pc": 20})
    granted = Proposal(
        test=D20Test(
            kind=TestKind.SAVE,
            ability="dex",
            target=10,
            target_basis="b",
            has_disadvantage=True,
        )
    )
    after = _as_this_creature_rolls(state, "pc", granted)
    assert after.test is not None
    assert after.test.has_disadvantage, "the rule's own Disadvantage was not dropped"
    assert after.test.has_advantage, "and p. 181's Advantage arrived beside it"
