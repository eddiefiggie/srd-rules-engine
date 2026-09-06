"""pp. 181 and 185's "until": a locked Exhaustion level becomes removable again (#461, 0089).

> Exhaustion caused by dehydration can't be removed until the creature drinks the full amount
> of water required for a day. (p. 181)
> Exhaustion caused by malnutrition can't be removed until the creature eats the full amount
> of food required for a day. (p. 185)

0028 clause 3 built the "can't be removed" half as `LOCKED_EXHAUSTION_RULES`, a constant over
rules, and nothing ever built the "until": a dehydration level was unremovable forever. The lift
is `Hazards.exhaustion_unlocked`, per creature and per rule, set by `with_day_ended` when the
day's water or food meets the table's row and closed again by `with_exhaustion` when a new
level of that rule arrives. Every assertion here was proved by corrupting the behaviour it
guards and watching this test go red.
"""

from __future__ import annotations

from fractions import Fraction

from srd_rules_engine.core.size import FOOD_PER_DAY, WATER_PER_DAY, Size
from srd_rules_engine.core.state import (
    DEHYDRATION_RULE_ID,
    LOCKED_EXHAUSTION_RULES,
    MALNUTRITION_RULE_ID,
    Combatant,
    EncounterState,
    Hazards,
)

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
NOTHING = Fraction(0)
A_DAY = Fraction(1)


def _combatant(cid: str = "pc", size: Size = Size.MEDIUM) -> Combatant:
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


def _state() -> EncounterState:
    return EncounterState.new([_combatant()])


def _day(
    state: EncounterState, *, water: Fraction = A_DAY, food: Fraction = A_DAY
) -> EncounterState:
    return state.with_day_ended(water={"pc": water}, food={"pc": food})


def _levels(state: EncounterState) -> tuple[str, ...]:
    return state.combatant("pc").conditions.exhaustion_levels


def _unlocked(state: EncounterState) -> frozenset[str]:
    return state.combatant("pc").hazards.exhaustion_unlocked


# --- Dehydration ------------------------------------------------------------------------------


def test_a_dehydration_level_is_locked_until_a_full_days_water_and_then_a_rest_takes_it() -> None:
    """The whole of #461, from both sides. The day the creature drinks nothing locks the
    level; a Long Rest takes nothing. The day it drinks its fill lifts the lock; the same
    rest takes the level."""
    thirsty = _day(_state(), water=NOTHING)
    assert _levels(thirsty) == (DEHYDRATION_RULE_ID,)
    assert _levels(thirsty.with_long_rest("pc")) == (DEHYDRATION_RULE_ID,)

    drank = _day(thirsty, water=A_DAY)
    assert DEHYDRATION_RULE_ID in _unlocked(drank)
    assert _levels(drank.with_long_rest("pc")) == ()


def test_half_a_days_water_is_enough_not_to_gain_a_level_and_not_enough_to_lift_the_lock() -> None:
    """Two thresholds in one row, and they differ. p. 181 gains a level below **half** and lifts
    the lock at the **full** amount, so half a gallon keeps a Medium creature from a second
    level and leaves the first one locked."""
    thirsty = _day(_state(), water=NOTHING)

    half = _day(thirsty, water=WATER_PER_DAY[Size.MEDIUM] / 2)
    assert _levels(half) == (DEHYDRATION_RULE_ID,), "no second level"
    assert DEHYDRATION_RULE_ID not in _unlocked(half)
    assert _levels(half.with_long_rest("pc")) == (DEHYDRATION_RULE_ID,), "still locked"

    full = _day(thirsty, water=WATER_PER_DAY[Size.MEDIUM])
    assert DEHYDRATION_RULE_ID in _unlocked(full), "exactly the full amount lifts it"


def test_the_requirement_is_the_creatures_size() -> None:
    """A Large creature needs four gallons (p. 181's table); one gallon is a Medium creature's
    day and a quarter of a Large one's."""
    large = EncounterState.new([_combatant(size=Size.LARGE)])
    thirsty = large.with_day_ended(water={"pc": NOTHING})

    one_gallon = thirsty.with_day_ended(water={"pc": Fraction(1)})
    assert DEHYDRATION_RULE_ID not in _unlocked(one_gallon)

    four = thirsty.with_day_ended(water={"pc": WATER_PER_DAY[Size.LARGE]})
    assert DEHYDRATION_RULE_ID in _unlocked(four)


def test_a_new_level_closes_the_lock_over_every_level_of_that_rule() -> None:
    """Thirsty, then a full day, then thirsty again: the creature holds levels dehydration
    caused and has not drunk its fill since the last, so both are locked and a Long Rest takes
    nothing."""
    state = _day(_day(_day(_state(), water=NOTHING), water=A_DAY), water=NOTHING)

    assert _levels(state) == (DEHYDRATION_RULE_ID,) * 2
    assert DEHYDRATION_RULE_ID not in _unlocked(state)
    assert _levels(state.with_long_rest("pc")) == (DEHYDRATION_RULE_ID,) * 2


def test_a_lift_is_per_rule() -> None:
    """A full day's water says nothing about food. A creature with a dehydration level and a
    starvation level that drinks its fill and eats a mouthful has one level removable, not two.

    **A mouthful, not nothing.** The first version of this ate nothing on the drinking day, and
    a corruption that lifted both locks on any lift stayed green: the sixth day of nothing
    gained a new starvation level, which closed malnutrition's lock again and hid the defect
    (#298's second shape). A mouthful resets the run without a level, so the lift is what
    the assertion sees.
    """
    state = _state()
    for _ in range(4):
        state = _day(state, water=A_DAY, food=NOTHING)
    state = _day(state, water=NOTHING, food=NOTHING)
    assert _levels(state) == (DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID)

    drank = _day(state, water=A_DAY, food=Fraction(1, 4))
    assert _levels(drank) == (DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID), "no new level"
    assert _unlocked(drank) == frozenset({DEHYDRATION_RULE_ID})

    rested = drank.with_long_rest("pc")
    assert DEHYDRATION_RULE_ID not in _levels(rested)
    assert MALNUTRITION_RULE_ID in _levels(rested)


def test_a_day_the_caller_says_nothing_about_lifts_nothing() -> None:
    thirsty = _day(_state(), water=NOTHING)
    silent = thirsty.with_day_ended(water={})

    assert DEHYDRATION_RULE_ID not in _unlocked(silent)


# --- Malnutrition, both of its rules --------------------------------------------------------


def test_a_starvation_level_is_locked_until_a_full_days_food() -> None:
    state = _state()
    for _ in range(5):
        state = _day(state, food=NOTHING)
    assert _levels(state) == (MALNUTRITION_RULE_ID,)
    assert _levels(state.with_long_rest("pc")) == (MALNUTRITION_RULE_ID,)

    fed = _day(state, food=FOOD_PER_DAY[Size.MEDIUM])
    assert MALNUTRITION_RULE_ID in _unlocked(fed)
    assert _levels(fed.with_long_rest("pc")) == ()


def test_a_level_from_the_failed_save_is_locked_and_lifted_the_same_way() -> None:
    """The save's level arrives through a ruling, not through `with_day_ended`, and it carries
    the same rule id — so the lock closes over it in `with_exhaustion`, which is where every
    gained level passes, and the same full day's food lifts it."""
    unlocked_first = _day(_state(), food=A_DAY)
    assert MALNUTRITION_RULE_ID in _unlocked(unlocked_first), "a full day, nothing to unlock"

    failed = unlocked_first.with_exhaustion("pc", MALNUTRITION_RULE_ID)
    assert MALNUTRITION_RULE_ID not in _unlocked(failed), "the new level closes it"
    assert _levels(failed.with_long_rest("pc")) == (MALNUTRITION_RULE_ID,)

    fed = _day(failed, food=A_DAY)
    assert _levels(fed.with_long_rest("pc")) == ()


def test_a_mouthful_resets_the_run_and_does_not_lift_the_lock() -> None:
    """Two different thresholds again: any food at all resets the starvation count (0088
    clause 3), and only the full amount lifts the lock."""
    state = _state()
    for _ in range(5):
        state = _day(state, food=NOTHING)

    mouthful = _day(state, food=Fraction(1, 4))
    assert state.combatant("pc").hazards.days_without_food == 5
    assert mouthful.combatant("pc").hazards.days_without_food == 0
    assert MALNUTRITION_RULE_ID not in _unlocked(mouthful)
    assert _levels(mouthful.with_long_rest("pc")) == (MALNUTRITION_RULE_ID,)


# --- The shape of the lift --------------------------------------------------------------------


def test_an_ordinary_level_is_never_locked_and_needs_no_lift() -> None:
    """The discriminating case for the constant: a level from a rule outside
    `LOCKED_EXHAUSTION_RULES` is removable without any day having ended."""
    assert "fixture:march" not in LOCKED_EXHAUSTION_RULES
    state = _state().with_exhaustion("pc", "fixture:march")

    assert _levels(state.with_long_rest("pc")) == ()
    assert _unlocked(state) == frozenset()


def test_the_most_recent_removable_level_goes_first_across_the_lift() -> None:
    """0028 clause 4's order runs over what the lock leaves. A march, then a thirsty day, then
    a full day: both levels are removable and the dehydration one is more recent."""
    state = _day(_day(_state().with_exhaustion("pc", "fixture:march"), water=NOTHING), water=A_DAY)
    assert _levels(state) == ("fixture:march", DEHYDRATION_RULE_ID)

    assert _levels(state.with_long_rest("pc")) == ("fixture:march",)


def test_the_lift_lives_with_the_other_hazards_and_the_engine_writes_it() -> None:
    assert Hazards().exhaustion_unlocked == frozenset()
    state = _day(_state(), water=A_DAY, food=A_DAY)
    assert state.combatant("pc").hazards == Hazards(
        exhaustion_unlocked=frozenset({DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID})
    )
