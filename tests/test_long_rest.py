"""Finishing a Long Rest, and the general Exhaustion removal rule that attaches to it (#185).

0028 decided that removal is a rule and that a level carries the rule that caused it. #183
built the data and the one removal with a live consumer — suffocation's. This is the other
one, and it is the general case: p. 185's "Exhaustion Reduced. If you have the Exhaustion
condition, its level decreases by 1."

Until it existed, **Exhaustion only ever accumulated**. A creature that marched through the
night gained a level it could never lose, and nothing in the engine said so.

Four things here are tested against the wrong answer, and each is a plausible implementation:

* **A creature at 0 hit points cannot start one** (p. 185). Every other benefit reads as
  unconditional, so this is the precondition an implementation drops — and dropping it lets a
  dying creature rest itself back to full.
* **One level, not the condition.** p. 185 says the level "decreases by 1"; an engine that
  ended the Exhaustion condition would clear five levels with one night's sleep.
* **A locked level is not a candidate** (0028 clause 3). Dehydration's and malnutrition's
  levels cannot be removed until the creature drinks or eats (pp. 181, 185), so a rest takes
  an unlocked one *or none* — never a locked one, and never a locked one put back.
* **It restores hit points**, which is the benefit most easily lost behind the Exhaustion
  work this issue was filed for.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.conditions import Conditions
from srd_rules_engine.core.state import (
    DEHYDRATION_RULE_ID,
    LOCKED_EXHAUSTION_RULES,
    MALNUTRITION_RULE_ID,
    SUFFOCATION_RULE_ID,
    Combatant,
    EncounterState,
)

MARCH = "a-tiring-march"


def creature(cid: str = "pc", *, hp: int = 30, levels: tuple[str, ...] = ()) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=hp,
        max_hit_points=30,
        armour_class=13,
        abilities={"con": 10},
        proficiency_bonus=2,
        is_player_character=True,
        conditions=Conditions(exhaustion_levels=levels),
    )


def encounter(**kwargs: object) -> EncounterState:
    return EncounterState.new([creature(**kwargs), creature("boar")])  # type: ignore[arg-type]


# --- The precondition -------------------------------------------------------------------


def test_a_creature_at_zero_hit_points_cannot_start_one() -> None:
    """p. 185: "To start a Long Rest, you must have at least 1 Hit Point."

    Without this a dying creature rests itself to full, which is the opposite of what being
    at 0 hit points means.
    """
    with pytest.raises(ValueError, match="at least 1"):
        encounter(hp=0).with_long_rest("pc")


def test_a_creature_with_one_hit_point_may() -> None:
    """One is enough — the rule is a floor, not a fraction."""
    rested = encounter(hp=1).with_long_rest("pc")
    assert rested.combatant("pc").hit_points == 30


# --- The benefits this engine can express -----------------------------------------------


def test_every_lost_hit_point_comes_back() -> None:
    assert encounter(hp=4).with_long_rest("pc").combatant("pc").hit_points == 30


def test_one_exhaustion_level_goes_and_the_rest_stay() -> None:
    """p. 185: the LEVEL decreases by 1. An engine that ended the condition would clear five
    levels with one night's sleep."""
    rested = encounter(levels=(MARCH, MARCH, MARCH)).with_long_rest("pc")
    assert rested.combatant("pc").conditions.exhaustion_level == 2


def test_the_last_level_ends_the_condition() -> None:
    """p. 181: "When your Exhaustion level reaches 0, the condition ends." Derived from the
    count rather than removed separately, so the two cannot disagree."""
    from srd_rules_engine.core.conditions import Condition

    rested = encounter(levels=(MARCH,)).with_long_rest("pc")
    assert rested.combatant("pc").conditions.exhaustion_level == 0
    assert not rested.combatant("pc").conditions.has(Condition.EXHAUSTION)


def test_a_creature_with_no_exhaustion_rests_without_complaint() -> None:
    """Nothing to remove is not an error — the other benefits still apply."""
    rested = encounter(hp=10).with_long_rest("pc")
    assert rested.combatant("pc").hit_points == 30
    assert rested.combatant("pc").conditions.exhaustion_level == 0


# --- 0028 clause 3: a locked level is not a candidate ------------------------------------


def test_a_rest_cannot_take_a_dehydration_level() -> None:
    """p. 181: "Exhaustion caused by dehydration can't be removed until the creature drinks
    the full amount of water required for a day."

    A creature holding only locked levels finishes a Long Rest and loses none of them — the
    answer an engine that subtracted one and re-applied the lock would report by a route
    that is wrong for the next rule to read.
    """
    rested = encounter(levels=(DEHYDRATION_RULE_ID, DEHYDRATION_RULE_ID)).with_long_rest("pc")
    assert rested.combatant("pc").conditions.exhaustion_from(DEHYDRATION_RULE_ID) == 2


def test_a_rest_takes_the_unlocked_level_and_leaves_the_locked_one() -> None:
    """The case that separates "skip locked levels" from "remove the newest"."""
    rested = encounter(levels=(MARCH, MALNUTRITION_RULE_ID)).with_long_rest("pc")
    held = rested.combatant("pc").conditions

    assert held.exhaustion_from(MALNUTRITION_RULE_ID) == 1, "malnutrition's level stays"
    assert held.exhaustion_from(MARCH) == 0, "and the removable one went"


def test_both_hazards_the_document_locks_are_locked() -> None:
    """Named ahead of the hazards themselves (#140). When either is built its rule id must
    be this string, or the lock stops applying and nothing says so."""
    assert {DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID} == LOCKED_EXHAUSTION_RULES
    assert SUFFOCATION_RULE_ID not in LOCKED_EXHAUSTION_RULES, (
        "suffocation's levels are removable — p. 189 removes them itself when the creature "
        "breathes again, and nothing stops a Long Rest taking one first"
    )


# --- 0028 clause 4: the order, declared as a convention ----------------------------------


def test_the_most_recently_gained_removable_level_goes_first() -> None:
    """p. 181 never says which level a Long Rest removes. This order is this engine's
    convention, declared in 0028 clause 4 rather than presented as SRD."""
    rested = encounter(levels=("an-old-march", "a-recent-march")).with_long_rest("pc")
    held = rested.combatant("pc").conditions

    assert held.exhaustion_from("a-recent-march") == 0
    assert held.exhaustion_from("an-old-march") == 1
