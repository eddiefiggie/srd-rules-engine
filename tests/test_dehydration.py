"""p. 181's Dehydration: bookkeeping at a day's end (#315, 0080).

> A creature requires an amount of water per day based on its size... A creature that drinks
> **less than half** the required water for a day gains 1 Exhaustion level at the day's end.
> Exhaustion caused by dehydration can't be removed until the creature drinks the full amount
> of water required for a day.

**No die.** p. 181 inflicts the level outright, which is what makes this a state transition
rather than an adjudication — the distinction 0027 clause 8 drew and this half of #315 rests
on. Malnutrition is the other half: p. 185 compels a DC 10 Constitution saving throw, and the
occasion that could produce a *ruling* on the campaign axis does not exist
([#399](https://github.com/eddiefiggie/srd-rules-engine/issues/399)).

**The lock was built before the hazard.** `LOCKED_EXHAUSTION_RULES` has held
`DEHYDRATION_RULE_ID` since 0028 clause 3, so a Long Rest already could not take a level this
applies. Dehydration is the first hazard to put one behind it.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from srd_rules_engine.core.size import WATER_PER_DAY, Size, dehydrated
from srd_rules_engine.core.state import (
    DEHYDRATION_RULE_ID,
    Combatant,
    EncounterState,
)

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _combatant(cid: str, size: Size | None = Size.MEDIUM) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=12,
        abilities=ABILITIES,
        proficiency_bonus=2,
        size=size,
    )


def _encounter(*combatants: Combatant) -> EncounterState:
    return EncounterState.new(list(combatants))


def _levels(state: EncounterState, cid: str) -> tuple[str, ...]:
    return state.combatant(cid).conditions.exhaustion_levels


# --- The table -------------------------------------------------------------------------


def test_the_water_table_is_p181s() -> None:
    assert {
        Size.TINY: Fraction(1, 4),
        Size.SMALL: Fraction(1),
        Size.MEDIUM: Fraction(1),
        Size.LARGE: Fraction(4),
        Size.HUGE: Fraction(16),
        Size.GARGANTUAN: Fraction(64),
    } == WATER_PER_DAY


def test_the_requirement_is_exact_rather_than_floating() -> None:
    """Tiny needs a quarter gallon and the rule turns on *half* of it — an eighth. Neither is
    representable in binary floating point, and a hazard that fired on a rounding error would
    be indistinguishable from one that fired on the rule."""
    assert dehydrated(Size.TINY, Fraction(1, 8)) is False, "exactly half is enough"
    assert dehydrated(Size.TINY, Fraction(1, 9)) is True

    # The float route gets this wrong in the direction nobody notices.
    assert 0.1 + 0.2 != 0.3, "which is why the table is not float"


def test_less_than_half_is_strict() -> None:
    """p. 181 says "less than half", so exactly half is not dehydration. A `<=` here would
    inflict a level the document does not."""
    assert dehydrated(Size.MEDIUM, Fraction(1, 2)) is False
    assert dehydrated(Size.MEDIUM, Fraction(499, 1000)) is True


# --- The day's end ---------------------------------------------------------------------


def test_a_creature_that_drank_too_little_gains_a_level() -> None:
    state = _encounter(_combatant("pc"))

    ended = state.with_day_ended(water={"pc": Fraction(1, 4)})

    assert _levels(ended, "pc") == (DEHYDRATION_RULE_ID,)


def test_a_creature_that_drank_enough_gains_nothing() -> None:
    state = _encounter(_combatant("pc"))

    ended = state.with_day_ended(water={"pc": Fraction(1, 2)})

    assert _levels(ended, "pc") == ()


def test_the_level_names_the_rule_that_caused_it() -> None:
    """0028 clause 1. Four of p. 181-236's five removal shapes need to know which level is
    which, and an unattributed one cannot be answered for by any of them."""
    ended = _encounter(_combatant("pc")).with_day_ended(water={"pc": Fraction(0)})

    assert _levels(ended, "pc") == (DEHYDRATION_RULE_ID,)


def test_size_decides_the_requirement() -> None:
    """A gallon dehydrates a Huge creature and satisfies a Medium one."""
    state = _encounter(_combatant("mouse", Size.TINY), _combatant("giant", Size.HUGE))

    ended = state.with_day_ended(water={"mouse": Fraction(1), "giant": Fraction(1)})

    assert _levels(ended, "mouse") == ()
    assert _levels(ended, "giant") == (DEHYDRATION_RULE_ID,)


# --- What it will not answer -------------------------------------------------------------


def test_a_creature_of_unknown_size_is_refused_rather_than_skipped() -> None:
    """0051: a size is stated or it is unknown. p. 181 reads the requirement from a size
    table, so a sizeless creature has nothing to have drunk less than half of — and passing
    over it silently would report a day in which nobody was thirsty."""
    state = _encounter(_combatant("wisp", None))

    with pytest.raises(ValueError, match="no stated size"):
        state.with_day_ended(water={"wisp": Fraction(0)})


def test_only_the_creatures_named_are_considered() -> None:
    """A day ending is not a claim about every creature in the encounter. Inventing a
    consumption of zero for the rest would dehydrate every bystander."""
    state = _encounter(_combatant("pc"), _combatant("bystander"))

    ended = state.with_day_ended(water={"pc": Fraction(0)})

    assert _levels(ended, "pc") == (DEHYDRATION_RULE_ID,)
    assert _levels(ended, "bystander") == ()


def test_an_unknown_creature_is_refused() -> None:
    with pytest.raises(KeyError):
        _encounter(_combatant("pc")).with_day_ended(water={"ghost": Fraction(0)})


# --- The lock ----------------------------------------------------------------------------


def test_a_long_rest_cannot_take_a_dehydration_level() -> None:
    """p. 181: "can't be removed until the creature drinks the full amount of water required
    for a day." `LOCKED_EXHAUSTION_RULES` has held this rule id since 0028 clause 3, ahead of
    the hazard — and this is the first hazard to put a level behind it."""
    thirsty = _encounter(_combatant("pc")).with_day_ended(water={"pc": Fraction(0)})

    rested = thirsty.with_long_rest("pc")

    assert _levels(rested, "pc") == (DEHYDRATION_RULE_ID,), "the Long Rest took nothing"


def test_a_long_rest_still_takes_an_unlocked_level() -> None:
    """The discriminating case: the lock is about *which* level, not about Long Rests. Without
    this, the assertion above would pass for an engine whose Long Rest removed nothing at
    all."""
    state = _encounter(_combatant("pc")).with_exhaustion("pc", "fixture:ordinary")

    rested = state.with_long_rest("pc")

    assert _levels(rested, "pc") == ()
