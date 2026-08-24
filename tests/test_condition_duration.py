"""How long a condition lasts, on the encounter axis (#18, decisions 0020 and 0021).

The shape of this is the finding rather than the code. All fifteen glossary entries state
*effects*; only Prone (p. 186) and Exhaustion (p. 181) carry an ending rule of their own.
Every other condition ends because whatever imposed it says when — so duration belongs to
the application, and a `duration` field on `Condition` would model something the document
does not have.

Two rules run through every test here:

* **Retiring a span is bookkeeping; ending one early is an outcome.** A duration's expiry
  point is settled when the condition is applied, so the lift decides nothing and rolls
  nothing. A save that could end a condition early is the opposite, and R1 leaves it to
  adjudication — reported here, never resolved.
* **The clock does not move.** 0021 clause 2: advancing a turn never touches campaign time,
  however many rounds a duration counts.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core import (
    Combatant,
    Condition,
    Duration,
    DurationKind,
    EncounterState,
    SaveEnds,
    read,
    rounds_in_minutes,
)
from srd_rules_engine.core.clock import SECONDS_PER_ROUND
from srd_rules_engine.core.conditions import Conditions

POISON_SAVE = SaveEnds(ability="con", dc=13)


def fighter(combatant_id: str, name: str) -> Combatant:
    return Combatant(
        id=combatant_id,
        name=name,
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 14, "dex": 12, "con": 14},
        proficiency_bonus=2,
    )


def encounter() -> EncounterState:
    """Two combatants in a fixed order: `first` acts, then `second`."""
    state = EncounterState.new([fighter("first", "First"), fighter("second", "Second")])
    return state.with_initiative({"first": 20, "second": 10})


def turns(state: EncounterState, count: int) -> EncounterState:
    for _ in range(count):
        state = state.advanced_turn()
    return state


def held(state: EncounterState, combatant_id: str) -> frozenset[Condition]:
    return state.combatant(combatant_id).conditions.held


# --- "Until the end of your next turn" (p. 29 and 61 others) ---------------------------


def test_applied_on_your_own_turn_it_survives_into_the_next_round() -> None:
    """Rage (p. 29) "lasts until the end of your next turn", and you start it on your own
    turn. If *this* turn's end counted, it would expire before it did anything."""
    state = encounter()
    assert state.round_number == 1 and state.active_id == "first"

    state = state.with_condition(
        "first", Condition.POISONED, duration=state.until_end_of_next_turn("first")
    )
    assert Condition.POISONED in held(state, "first")

    after_own_turn = turns(state, 1)
    assert Condition.POISONED in held(after_own_turn, "first"), "this turn is not the next one"

    end_of_next = turns(state, 2)
    assert end_of_next.round_number == 2 and end_of_next.active_id == "first"
    assert Condition.POISONED in held(end_of_next, "first"), "still held during that turn"

    assert Condition.POISONED not in held(turns(state, 3), "first"), "lifted as it closed"


def test_applied_to_a_creature_that_has_not_acted_yet_it_ends_this_round() -> None:
    """Its next turn is later in this round, not in the following one."""
    state = encounter()
    state = state.with_condition(
        "second", Condition.BLINDED, duration=state.until_end_of_next_turn("second")
    )
    assert Condition.BLINDED in held(state, "second")
    assert Condition.BLINDED not in held(turns(state, 2), "second"), "ended in round 1"


def test_a_condition_is_still_held_for_the_whole_of_the_turn_it_ends_on() -> None:
    """ "Until the end of" is inclusive. Lifting at the start would remove the effect for
    the turn the document says it applies to."""
    state = encounter()
    state = state.with_condition(
        "second", Condition.POISONED, duration=state.until_end_of_next_turn("second")
    )
    during = turns(state, 1)
    assert during.active_id == "second"
    assert Condition.POISONED in held(during, "second")


# --- A span in rounds (p. 106, counted as p. 98 counts it) -----------------------------


def test_a_span_in_rounds_ends_that_many_rounds_later_at_the_same_point_in_the_order() -> None:
    """p. 98 is the only place the document says what counting rounds from an event means:
    the oil burns "until the end of the turn 2 rounds from when the oil was lit"."""
    state = encounter()
    state = state.with_condition(
        "first", Condition.RESTRAINED, duration=state.for_rounds(2, "first")
    )
    assert state.combatant("first").conditions.durations[Condition.RESTRAINED].ends_after_round == 3

    assert Condition.RESTRAINED in held(turns(state, 4), "first"), "still held in round 3"
    assert Condition.RESTRAINED not in held(turns(state, 5), "first")


def test_a_negative_span_is_refused() -> None:
    with pytest.raises(ValueError, match="not negative"):
        encounter().for_rounds(-1, "first")


# --- Minutes convert once, at application (0021 clauses 3 and 4) -----------------------


def test_a_minute_becomes_ten_rounds_and_says_so() -> None:
    """p. 98: two rounds is twelve seconds, so a round is six and a minute is ten rounds.
    `stated_minutes` keeps what was said, so the arithmetic is visible rather than implied
    by a round count nobody can trace back."""
    assert rounds_in_minutes(1) == 10
    assert SECONDS_PER_ROUND == 6

    state = encounter()
    duration = state.for_minutes(1, "first")
    assert duration.stated_minutes == 1
    assert duration.ends_after_round == state.round_number + 10
    assert "1 minute(s) = 10 rounds" in duration.derivation()
    assert "p. 98" in duration.derivation()


def test_the_conversion_happens_once_rather_than_on_every_query() -> None:
    """0020 clause 4's reasoning: a value re-derived whenever somebody asks is a value a
    caller can re-draw by choosing when to ask."""
    state = encounter()
    state = state.with_condition(
        "first", Condition.POISONED, duration=state.for_minutes(1, "first")
    )
    stored = state.combatant("first").conditions.durations[Condition.POISONED]

    later = turns(state, 3)
    assert later.round_number > state.round_number
    assert later.combatant("first").conditions.durations[Condition.POISONED] == stored


def test_the_clock_does_not_move_however_many_rounds_pass() -> None:
    """0021 clause 2, and the clause that must not be relaxed. Knowing a round is six
    seconds is not knowing how much campaign time has elapsed."""
    state = encounter()
    state = state.with_condition(
        "first", Condition.POISONED, duration=state.for_minutes(1, "first")
    )
    assert turns(state, 12).clock.elapsed_minutes == state.clock.elapsed_minutes == 0


def test_minutes_convert_but_elapsed_minutes_never_become_rounds() -> None:
    """0021 clause 5. Outside an encounter there are no rounds to count, so the inverse is
    not merely unimplemented — it has no meaning."""
    import srd_rules_engine.core as core

    assert not [n for n in core.__all__ if "minutes_in_rounds" in n or "rounds_elapsed" in n]
    assert not hasattr(EncounterState, "rounds_in_minutes")


# --- Implication lifts with its source -------------------------------------------------


def test_an_implied_condition_lifts_with_the_condition_that_implied_it() -> None:
    """Paralyzed implies Incapacitated (p. 186). Nobody applied Incapacitated, so nothing
    should keep holding it once Paralyzed ends."""
    state = encounter()
    state = state.with_condition(
        "second", Condition.PARALYZED, duration=state.until_end_of_next_turn("second")
    )
    assert {Condition.PARALYZED, Condition.INCAPACITATED} <= held(state, "second")

    after = turns(state, 2)
    assert Condition.PARALYZED not in held(after, "second")
    assert Condition.INCAPACITATED not in held(after, "second"), "it was only ever implied"


def test_unconscious_ending_leaves_the_creature_prone() -> None:
    """p. 191: "When this condition ends, you remain Prone." Unconscious implies Prone, so
    the naive removal lifts both — and the document says otherwise."""
    state = encounter()
    state = state.with_condition(
        "second", Condition.UNCONSCIOUS, duration=state.until_end_of_next_turn("second")
    )
    assert {Condition.UNCONSCIOUS, Condition.PRONE, Condition.INCAPACITATED} <= held(
        state, "second"
    )

    after = turns(state, 2)
    assert Condition.UNCONSCIOUS not in held(after, "second")
    assert Condition.INCAPACITATED not in held(after, "second"), "implied, so it lifts"
    assert Condition.PRONE in held(after, "second"), "p. 191 carves this one out"


def test_a_condition_implied_by_two_sources_survives_losing_one() -> None:
    """Recomputing the closure rather than subtracting from it is what makes this work.
    Paralyzed and Stunned both imply Incapacitated; ending one leaves the other holding it.
    """
    state = encounter()
    state = state.with_condition(
        "second", Condition.PARALYZED, duration=state.until_end_of_next_turn("second")
    )
    state = state.with_condition("second", Condition.STUNNED)
    assert Condition.INCAPACITATED in held(state, "second")

    after = turns(state, 2)
    assert Condition.PARALYZED not in held(after, "second")
    assert Condition.STUNNED in held(after, "second")
    assert Condition.INCAPACITATED in held(after, "second"), "Stunned still implies it"


# --- What the engine cannot retire is reported, not hidden (0021 clause 6) -------------


def test_a_condition_with_no_stated_span_is_named_rather_than_left_permanent() -> None:
    state = encounter().with_condition("first", Condition.PETRIFIED)
    conditions = state.combatant("first").conditions

    assert Condition.PETRIFIED in conditions.unretirable()
    assert Condition.PETRIFIED in held(turns(state, 6), "first"), "and it really does persist"


def test_an_until_removed_duration_names_no_expiry_point() -> None:
    with pytest.raises(ValueError, match="no expiry point"):
        Duration(kind=DurationKind.UNTIL_REMOVED, ends_after_round=3, ends_after_actor_id="a")


def test_a_timed_duration_must_name_one() -> None:
    with pytest.raises(ValueError, match="named creature's turn"):
        Duration(kind=DurationKind.ROUNDS, ends_after_round=3)


def test_a_duration_for_a_condition_nobody_applied_is_refused() -> None:
    """A duration belongs to the application that imposed the condition, so one floating
    free has nothing to end."""
    with pytest.raises(ValueError, match="nothing to end"):
        Conditions(
            held=frozenset({Condition.BLINDED}),
            durations={
                Condition.POISONED: Duration(
                    kind=DurationKind.ROUNDS, ends_after_round=2, ends_after_actor_id="first"
                )
            },
        )


# --- Save-ends is reported, never rolled (R1, R4, p. 63) -------------------------------


def test_a_repeated_save_is_reported_and_not_resolved() -> None:
    """p. 63: the target "repeats the save at the end of each of its turns, ending the
    effect on itself on a success". That is an outcome, and R1 leaves outcomes to the one
    adjudication entry point — so the state reports the save is due and never rolls it.

    The condition surviving many turns is the assertion that matters: if anything here
    rolled a DC 13 save twelve times, one would have succeeded.
    """
    state = encounter()
    state = state.with_condition(
        "second",
        Condition.POISONED,
        duration=state.for_minutes(1, "second", save=POISON_SAVE),
    )
    due = state.combatant("second").conditions.saves_due_after("second")
    assert due == {Condition.POISONED: POISON_SAVE}

    persisted = turns(state, 12)
    assert Condition.POISONED in held(persisted, "second"), "no save was rolled anywhere"


def test_the_span_still_retires_a_condition_that_carries_a_save() -> None:
    """p. 63 states both: "for 1 minute" *and* the repeated save. The early-out runs
    alongside the span rather than instead of it."""
    state = encounter()
    state = state.with_condition(
        "second", Condition.POISONED, duration=state.for_rounds(1, "second", save=POISON_SAVE)
    )
    assert Condition.POISONED not in held(turns(state, 4), "second")


def test_a_successful_save_ends_it_through_the_state_transition() -> None:
    """What adjudication calls once it has rolled the save. The transition applies a
    decided outcome; it does not decide one."""
    state = encounter()
    state = state.with_condition(
        "second", Condition.PARALYZED, duration=state.for_minutes(1, "second", save=POISON_SAVE)
    )
    ended = state.with_condition_ended("second", Condition.PARALYZED)

    assert Condition.PARALYZED not in held(ended, "second")
    assert Condition.INCAPACITATED not in held(ended, "second"), "implication recomputed"


def test_a_save_dc_is_a_positive_target_number() -> None:
    with pytest.raises(ValueError, match="positive target number"):
        SaveEnds(ability="con", dc=0)


# --- Reads do not mutate (R19) ---------------------------------------------------------


def test_asking_which_conditions_expired_changes_nothing() -> None:
    state = encounter()
    state = state.with_condition(
        "first", Condition.POISONED, duration=state.until_end_of_next_turn("first")
    )
    conditions = state.combatant("first").conditions

    first = conditions.expired_after(9, "first")
    assert first == conditions.expired_after(9, "first")
    assert Condition.POISONED in conditions.held, "the read did not retire it"


def test_retiring_a_duration_does_not_bump_the_generation_twice() -> None:
    """`advanced_turn` makes one generation. Two would leave a read token from before the
    turn looking two changes stale instead of one, which is a staleness report that
    overstates what happened."""
    state = encounter()
    with_condition = state.with_condition(
        "first", Condition.POISONED, duration=state.until_end_of_next_turn("first")
    )
    without = state.with_condition("first", Condition.PETRIFIED)

    expiring = turns(with_condition, 3).generation - with_condition.generation
    plain = turns(without, 3).generation - without.generation
    assert expiring == plain, "a turn that retires a condition costs the same as one that does not"


# --- The read surface (R18) ------------------------------------------------------------


def test_the_read_surface_reports_the_span_the_save_and_what_it_cannot_retire() -> None:
    """R18 asks for conditions "with their mechanical effects". An agent told a name but not
    how long it lasts is back to recalling 5e, which is the capability being removed."""
    state = encounter()
    state = state.with_condition(
        "first", Condition.POISONED, duration=state.for_minutes(1, "first", save=POISON_SAVE)
    )
    state = state.with_condition("first", Condition.PETRIFIED)

    situation = read(state, "first").situation
    assert situation is not None
    assert Condition.POISONED in situation.condition_durations
    assert "1 minute(s) = 10 rounds" in situation.condition_durations[Condition.POISONED]
    assert situation.saves_due[Condition.POISONED] == ("con", 13)
    assert Condition.PETRIFIED in situation.conditions_until_removed
    assert Condition.POISONED not in situation.conditions_until_removed
