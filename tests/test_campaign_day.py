"""A campaign day's end: the fifth occasion (#399, 0081).

The four occasions that could produce a ruling were all **encounter-scale** — a turn's start,
its declaration slot, its end, and a move. A campaign day ending is none of them and may happen
with no combat at all, which is what made #399 a gate rather than a wiring job.

Two rules fire there and they are **different shapes**, which is the whole of why one was built
four builds before the other:

* **p. 181's Dehydration** inflicts a level outright. No die, so `EncounterState.with_day_ended`
  applies it as bookkeeping (0080).
* **p. 185's Malnutrition** compels a DC 10 Constitution saving throw. That is an outcome, so
  it is *compelled* by the same state transition and *rolled* through
  `Adjudicator.adjudicate` like every other result (R1, R4).

`TurnLoop.end_day` is the occasion. It lives on `TurnLoop` despite not being a turn, and the
reason is `_owed`: R29's narration debt is held per loop, so a second driver would let a
creature owe a narration to one object and act through another.
"""

from __future__ import annotations

import shutil
from fractions import Fraction
from pathlib import Path

from fixtures.ruleset import fixture_catalogue
from srd_rules_engine.core.adjudicate import Adjudicator, Status
from srd_rules_engine.core.hazards import malnutrition_resolver, malnutrition_rule
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.rules import load_ruleset
from srd_rules_engine.core.size import Size
from srd_rules_engine.core.state import (
    DEHYDRATION_RULE_ID,
    MALNUTRITION_RULE_ID,
    MALNUTRITION_SAVE_DC,
    Combatant,
    EncounterState,
)
from srd_rules_engine.loop.turn import DayEnd, Narrated, TurnLoop
from srd_rules_engine.memory.store import JsonMemoryStore

#: Seed 2 rolls a 1 and seed 4 a 20, against a DC of 10 with no Constitution modifier — so
#: each half of the save is exercised by a die the engine threw rather than by a stub.
FAILING_SEED = 2
PASSING_SEED = 4

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


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


def _loop(tmp_path: Path, *, seed: int) -> TurnLoop:
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
            seed_source=lambda: seed,
        )
    )


def _end_day(
    tmp_path: Path,
    *,
    seed: int = PASSING_SEED,
    water: Fraction = Fraction(1),
    food: Fraction = Fraction(1),
    combatants: tuple[Combatant, ...] = (),
) -> DayEnd:
    state = EncounterState.new(list(combatants) or [_combatant()])
    gen = _loop(tmp_path, seed=seed).end_day(state, water={"pc": water}, food={"pc": food})
    try:
        next(gen)
        while True:
            gen.send(Narrated("the day ends"))
    except StopIteration as stop:
        assert isinstance(stop.value, DayEnd)
        return stop.value


def _levels(outcome: DayEnd) -> tuple[str, ...]:
    return outcome.state.combatant("pc").conditions.exhaustion_levels


# --- The two shapes, side by side ------------------------------------------------------


def test_a_well_fed_and_watered_day_produces_nothing(tmp_path: Path) -> None:
    outcome = _end_day(tmp_path)

    assert outcome.rulings == ()
    assert _levels(outcome) == ()


def test_dehydration_produces_a_level_and_no_ruling(tmp_path: Path) -> None:
    """p. 181 throws no die, so there is nothing to adjudicate — a state transition is not a
    ruling, and an engine that manufactured one would put a roll in the ledger that decided
    nothing (0027 clause 6)."""
    outcome = _end_day(tmp_path, water=Fraction(0))

    assert _levels(outcome) == (DEHYDRATION_RULE_ID,)
    assert outcome.rulings == (), "no die was thrown, so no ruling was produced"


def test_malnutrition_produces_a_ruling_because_it_asks_the_dice(tmp_path: Path) -> None:
    """p. 185's DC 10 Constitution save is the one hazard with a die, and the reason this
    occasion had to exist at all."""
    outcome = _end_day(tmp_path, food=Fraction(1, 4), seed=PASSING_SEED)

    assert [r.status for r in outcome.rulings] == [Status.RULED]
    assert _levels(outcome) == (), "the save was made"


def test_a_failed_save_gains_a_level_attributed_to_malnutrition(tmp_path: Path) -> None:
    outcome = _end_day(tmp_path, food=Fraction(1, 4), seed=FAILING_SEED)

    assert _levels(outcome) == (MALNUTRITION_RULE_ID,)


def test_both_rules_fire_on_the_same_day(tmp_path: Path) -> None:
    """The one that throws no die and the one that does, in one occasion — which is what
    `end_day` exists to hold together."""
    outcome = _end_day(tmp_path, water=Fraction(0), food=Fraction(1, 4), seed=FAILING_SEED)

    assert sorted(_levels(outcome)) == [DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID]
    assert len(outcome.rulings) == 1, "one die thrown, for the one rule that asks for one"


# --- What the document says, and what it does not ----------------------------------------


def test_the_dc_is_p185s_and_is_recorded_on_the_debt(tmp_path: Path) -> None:
    """p. 185 states the DC outright rather than deriving it, which is unusual enough that the
    engine records it on the `ForcedSave` anyway — 0036 clause 4's rule kept rather than
    excepted for the one save that happens to be constant."""
    assert MALNUTRITION_SAVE_DC == 10

    compelled = EncounterState.new([_combatant()]).with_day_ended(
        water={"pc": Fraction(1)}, food={"pc": Fraction(1, 4)}
    )

    (debt,) = compelled.forced_saves_owed
    assert (debt.rule_id, debt.ability, debt.dc) == (MALNUTRITION_RULE_ID, "con", 10)


def test_eating_nothing_compels_no_save(tmp_path: Path) -> None:
    """p. 185's first sentence is about a creature that "**eats but** consumes less than half".
    Eating nothing is the five-day starvation clause, which compels no save and gains a level
    outright — a different rule, unbuilt, and
    [#401](https://github.com/eddiefiggie/srd-rules-engine/issues/401).

    **`False` here is not a claim that the creature is unharmed.** It is the engine declining
    to apply the wrong rule.
    """
    outcome = _end_day(tmp_path, food=Fraction(0), seed=FAILING_SEED)

    assert outcome.rulings == ()
    assert _levels(outcome) == ()


def test_exactly_half_a_day_of_food_compels_nothing(tmp_path: Path) -> None:
    """p. 185 says "less than half", so half is enough."""
    outcome = _end_day(tmp_path, food=Fraction(1, 2), seed=FAILING_SEED)

    assert outcome.rulings == ()


# --- The occasion itself ------------------------------------------------------------------


def test_the_day_ends_without_any_turn_having_happened(tmp_path: Path) -> None:
    """The property that made this a gate. `end_day` is reached on a state that has never
    rolled initiative — a campaign day is not a turn, and four of the five occasions could not
    have been asked."""
    state = EncounterState.new([_combatant()])
    assert not state.in_combat

    gen = _loop(tmp_path, seed=FAILING_SEED).end_day(
        state, water={"pc": Fraction(0)}, food={"pc": Fraction(1, 4)}
    )
    try:
        next(gen)
        while True:
            gen.send(Narrated("a long, hungry road"))
    except StopIteration as stop:
        outcome = stop.value

    assert not outcome.state.in_combat
    assert sorted(_levels(outcome)) == [DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID]


def test_the_ruling_is_narrated_like_any_other(tmp_path: Path) -> None:
    """R29. An obligation resolved outside a declaration slot still yields a
    `NarrationRequest`, which is 0023 clause 1's requirement and the reason this is a loop
    phase rather than a state method."""
    outcome = _end_day(tmp_path, food=Fraction(1, 4), seed=FAILING_SEED)

    assert outcome.narrations == ("the day ends",)
    assert not outcome.missing_narration


def test_a_long_rest_cannot_take_either_level(tmp_path: Path) -> None:
    """pp. 181 and 185 both hold their Exhaustion until the creature drinks or eats, and
    `LOCKED_EXHAUSTION_RULES` has held both rule ids since 0028 clause 3 — before either
    hazard existed."""
    outcome = _end_day(tmp_path, water=Fraction(0), food=Fraction(1, 4), seed=FAILING_SEED)

    rested = outcome.state.with_long_rest("pc")

    assert sorted(rested.combatant("pc").conditions.exhaustion_levels) == [
        DEHYDRATION_RULE_ID,
        MALNUTRITION_RULE_ID,
    ]
