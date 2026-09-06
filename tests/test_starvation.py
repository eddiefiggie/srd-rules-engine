"""p. 185's second rule: a run of days without food, counted (#401, 0088).

> A creature that eats nothing for 5 days automatically gains 1 Exhaustion level at the end
> of the fifth day as well as an additional level at the end of each subsequent day without
> food.

[0081](../docs/decisions/0081-a-campaign-days-end-is-the-fifth-occasion.md) built the first
sentence — the DC 10 Constitution save for eating too little — and left this one as #401,
because it needed a kind of state nothing held: a running count of days in which something
did **not** happen. The count is `Hazards.days_without_food`, the engine's arithmetic over the
food the caller states at each day's end, and this module is where each clause of the rule is
pinned. Every assertion was proved by corrupting the behaviour it guards and watching this
test go red; the module is new, so its collection error against the base tree is indivisible.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from fixtures.ruleset import fixture_catalogue
from srd_rules_engine.core import ENGINE_SHAPES, load_inventory
from srd_rules_engine.core.adjudicate import Adjudicator
from srd_rules_engine.core.conditions import MAX_EXHAUSTION, Condition
from srd_rules_engine.core.hazards import malnutrition_resolver, malnutrition_rule
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.rules import load_ruleset
from srd_rules_engine.core.size import Size, undernourished
from srd_rules_engine.core.state import (
    DEHYDRATION_RULE_ID,
    MALNUTRITION_RULE_ID,
    STARVATION_DAYS,
    Combatant,
    EncounterState,
    Hazards,
)
from srd_rules_engine.loop.turn import DayEnd, Narrated, TurnLoop
from srd_rules_engine.memory.store import JsonMemoryStore

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
NOTHING = Fraction(0)
A_DAYS_FOOD = Fraction(1)
A_MOUTHFUL = Fraction(1, 4)


def _combatant(cid: str = "pc", size: Size | None = Size.MEDIUM) -> Combatant:
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


def _state(*combatants: Combatant) -> EncounterState:
    return EncounterState.new(list(combatants) or [_combatant()])


def _days(state: EncounterState, *meals: Fraction, cid: str = "pc") -> EncounterState:
    """End one day per meal, each with a full day's water so p. 181 stays out of it."""
    for meal in meals:
        state = state.with_day_ended(water={cid: A_DAYS_FOOD}, food={cid: meal})
    return state


def _levels(state: EncounterState, cid: str = "pc") -> tuple[str, ...]:
    return state.combatant(cid).conditions.exhaustion_levels


def _run(state: EncounterState, cid: str = "pc") -> int:
    return state.combatant(cid).hazards.days_without_food


# --- The count ------------------------------------------------------------------------------


def test_four_days_without_food_gain_nothing_and_the_fifth_gains_a_level() -> None:
    """p. 185's boundary from both sides: the fourth day is one short and the fifth is the
    day. A test on the fifth alone would pass against a count that fired on the first."""
    assert STARVATION_DAYS == 5
    hungry = _days(_state(), *([NOTHING] * 4))

    assert _run(hungry) == 4
    assert _levels(hungry) == ()

    starving = _days(hungry, NOTHING)
    assert _run(starving) == 5
    assert _levels(starving) == (MALNUTRITION_RULE_ID,)


def test_each_subsequent_day_without_food_gains_another_level() -> None:
    """ "As well as an additional level at the end of each subsequent day" — the run does not
    latch on the fifth day, it keeps counting, and every day from then on is a level."""
    state = _days(_state(), *([NOTHING] * 7))

    assert _run(state) == 7
    assert _levels(state) == (MALNUTRITION_RULE_ID,) * 3


def test_a_single_mouthful_breaks_the_run() -> None:
    """ "Eats nothing" is the condition, so any food at all resets the count — even a
    quarter-pound, which is less than half a Medium creature's day and compels the save
    besides. Four days, a mouthful, and four more days is two runs of four, not one of eight."""
    state = _days(_state(), *([NOTHING] * 4), A_MOUTHFUL, *([NOTHING] * 4))

    assert _run(state) == 4
    assert _levels(state) == ()


def test_the_mouthful_still_compels_the_save_the_first_sentence_states() -> None:
    """The two rules read one day's food twice. A quarter-pound resets the run **and** is
    "less than half", so the save is owed — resetting is not an exemption from p. 185's
    first sentence."""
    state = _days(_state(), *([NOTHING] * 4), A_MOUTHFUL)

    assert _run(state) == 0
    assert undernourished(Size.MEDIUM, A_MOUTHFUL)
    assert [d.rule_id for d in state.forced_saves_owed] == [MALNUTRITION_RULE_ID]


def test_a_full_days_food_resets_the_run_and_compels_nothing() -> None:
    state = _days(_state(), *([NOTHING] * 4), A_DAYS_FOOD)

    assert _run(state) == 0
    assert state.forced_saves_owed == ()


def test_a_day_the_caller_says_nothing_about_neither_advances_nor_resets() -> None:
    """0080 clause 3, applied to the count: a day ending is not a claim about every creature,
    so a creature the caller does not name has had a day the engine knows nothing about.
    Advancing would starve a bystander on no evidence; resetting would feed one."""
    state = _days(_state(), *([NOTHING] * 4))
    unmentioned = state.with_day_ended(water={"pc": A_DAYS_FOOD})

    assert _run(unmentioned) == 4
    assert _levels(_days(unmentioned, NOTHING)) == (MALNUTRITION_RULE_ID,)


def test_the_count_is_per_creature() -> None:
    state = _state(_combatant("pc"), _combatant("mule"))
    for _ in range(5):
        state = state.with_day_ended(
            water={"pc": A_DAYS_FOOD, "mule": A_DAYS_FOOD},
            food={"pc": NOTHING, "mule": A_DAYS_FOOD},
        )

    assert _levels(state, "pc") == (MALNUTRITION_RULE_ID,)
    assert _levels(state, "mule") == ()
    assert _run(state, "mule") == 0


def test_the_level_is_malnutritions_and_a_long_rest_cannot_take_it() -> None:
    """0028 clause 3's lock, reaching the second rule that puts a level behind it. p. 185:
    "Exhaustion caused by malnutrition can't be removed until the creature eats the full
    amount of food required for a day"."""
    state = _days(_state(), *([NOTHING] * 5))

    rested = state.with_long_rest("pc")
    assert _levels(rested) == (MALNUTRITION_RULE_ID,)


def test_a_creature_that_has_starved_to_death_gains_nothing_more() -> None:
    """p. 181: "You die if your Exhaustion level is 6." The run reaches six levels on the
    tenth day, and an eleventh day is not refused and adds nothing — a seventh level is not
    a state the document describes, and `with_exhaustion` would refuse it."""
    state = _days(_state(), *([NOTHING] * 10))
    assert len(_levels(state)) == MAX_EXHAUSTION

    eleventh = _days(state, NOTHING)
    assert len(_levels(eleventh)) == MAX_EXHAUSTION
    assert _run(eleventh) == 11


def test_a_negative_days_food_is_refused() -> None:
    with pytest.raises(ValueError, match="negative amount of food"):
        _state().with_day_ended(water={"pc": A_DAYS_FOOD}, food={"pc": Fraction(-1)})


def test_the_count_is_the_engines_and_lives_with_the_other_hazards() -> None:
    """A caller states what was eaten; the engine counts. The field sits beside `burning` and
    `suffocating` because hunger is a fact about one creature that outlives any encounter,
    and it is not one of p. 179's fifteen conditions."""
    assert Hazards().days_without_food == 0
    state = _days(_state(), NOTHING, NOTHING)
    # Two days of a full day's water lift dehydration's lock as they pass (0089), which is the
    # other thing the engine writes here; the count is the field under test.
    assert state.combatant("pc").hazards == Hazards(
        days_without_food=2, exhaustion_unlocked=frozenset({DEHYDRATION_RULE_ID})
    )
    assert Condition.EXHAUSTION not in state.combatant("pc").conditions.held


# --- Through the occasion ---------------------------------------------------------------------


def _loop(tmp_path: Path) -> TurnLoop:
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset((malnutrition_rule(),)),
            resolvers={MALNUTRITION_RULE_ID: malnutrition_resolver()},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "memory.json"),
            ledger=Ledger.open(
                tmp_path / "ledger.jsonl",
                engine_version="t",
                catalogue_version=fixture_catalogue().version,
                session_id="s",
            ),
            catalogue=fixture_catalogue(),
            seed_source=lambda: 4,
        )
    )


def _end_day(loop: TurnLoop, state: EncounterState, food: Fraction) -> DayEnd:
    gen = loop.end_day(state, water={"pc": A_DAYS_FOOD}, food={"pc": food})
    try:
        next(gen)
        while True:
            gen.send(Narrated("the day ends"))
    except StopIteration as stop:
        assert isinstance(stop.value, DayEnd)
        return stop.value


def test_the_fifth_day_produces_a_level_and_no_ruling(tmp_path: Path) -> None:
    """Bookkeeping, like p. 181's: the level is gained outright and no die is thrown, so the
    day's end that inflicts it puts nothing in the ledger. The save is the other sentence."""
    loop = _loop(tmp_path)
    state = _state()
    for _ in range(5):
        outcome = _end_day(loop, state, NOTHING)
        assert outcome.rulings == (), "eating nothing compels no save (0081)"
        state = outcome.state

    assert _levels(state) == (MALNUTRITION_RULE_ID,)


def test_a_starving_creature_that_is_already_prone_keeps_counting() -> None:
    """The count is independent of every condition: it reads the day's food and nothing
    else, so a creature knocked down on day three is still on day three of its run."""
    down = replace(_combatant(), hazards=Hazards(days_without_food=2))
    state = _days(_state(down), NOTHING)

    assert _run(state) == 3


# --- The claim --------------------------------------------------------------------------------


def test_the_shape_is_claimed_now_that_both_sentences_are_built() -> None:
    """#401 said the `malnutrition` shape stays unclaimed until both sentences are built — a
    shape claimed at half is the overstatement R17's inventory exists to prevent."""
    assert ENGINE_SHAPES["malnutrition"] == "core.hazards.malnutrition_resolver"
    shape = load_inventory().by_id("malnutrition")
    assert shape is not None and shape.implemented
