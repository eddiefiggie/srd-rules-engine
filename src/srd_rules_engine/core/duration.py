"""How long a condition lasts — and why that is not a property of the condition (#18, #111).

All fifteen glossary entries state *effects*. Only two carry an ending rule of their own:
Prone (p. 186, spend half your Speed to right yourself) and Exhaustion (p. 181, a Long Rest
removes a level). Every other condition ends because **whatever imposed it says when**.

So duration belongs to the application, not to `Condition`. A `duration` field on the
condition itself would model something the document does not have — which is why this is a
separate vocabulary that an applying effect supplies, and why a condition applied with no
duration is `UNTIL_REMOVED` rather than defaulting to some span nobody stated.

## The document's taxonomy, and the part of it that lives here

p. 106 gives three forms: **Concentration**, **Instantaneous**, and a **Time Span** —
"how long the spell lasts in rounds, minutes, hours, or the like".

This module covers **both axes** of the time span, plus the early-out that appears alongside
it. Concentration is `core.spellcasting` and already ends its own effects; Instantaneous
never produces a lasting condition.

## Which axis a span lands on, and why it is not a formatting detail

Decision [0020](../../../docs/decisions/0020-two-kinds-of-time.md) gives the engine two kinds
of time, and a duration resolves against exactly one of them:

* **The encounter axis** — rounds, and "until the end of your next turn". Retired by
  `EncounterState.advanced_turn`, at the close of a named creature's turn.
* **The campaign axis** — hours and days, as a minute on `Clock`. Retired by
  `EncounterState.with_time_passed` (#111), when the agent says that much time went by.

The two do not retire each other, and that is the honest consequence rather than a gap. An
eight-hour condition does not lift during a six-round fight, because the clock does not move
on a turn (0021 clause 2). A three-round condition does not lift because somebody rested,
because rounds are not on the clock. Each span is counted by the axis that can count it, and
`UNTIL_REMOVED` is what remains when neither can.

## A duration is a span with optional early-outs

p. 63 shows both at once: the target "has the Poisoned condition **for 1 minute**. At the
end of each of its turns, the Poisoned target **repeats the save**, ending the effect on
itself on a success." One outer span, one early-out. Elsewhere the early-out is an event —
"the Unconscious condition for 1 minute **or until it takes any damage**".

There is **no general save-ends rule** in the document. Every instance states its own, which
is why `SaveEnds` carries the ability and DC from the effect that imposed it rather than
reading them from a table that does not exist.

## Each axis reduces to one expiry point

On the encounter axis a span ends **at the end of a named creature's turn, in a named
round**; on the campaign axis it ends **at a minute the clock reaches**. Both are computed
when the condition is applied, which is 0021 clause 3: converted once, at application, never
re-derived on query. A value re-derived whenever somebody asks is a value a caller can
re-draw by choosing when to ask — which is also why the campaign expiry is stored as an
absolute minute rather than a remaining one.

"For N rounds" is read off p. 98, which is the only place the document says what counting
rounds from an event means: the oil burns "until the end of the turn 2 rounds from when the
oil was lit". So N rounds later, at that same point in the order — not N turns, and not the
start of a round.

## Minutes convert; the campaign clock still does not move

Decision [0021](../../../docs/decisions/0021-a-round-is-six-seconds.md) settles that a round
is exactly six seconds (p. 98: two rounds "or 12 seconds"). A span stated in minutes
therefore has a round count, and `StatedSpan` records what was said so the arithmetic is
visible rather than implied (0021 clause 4). Hours and days convert the same way, into
clock minutes, and the same record shows it.

**A minute is the boundary between the two axes, and it stays on the encounter one.** 0021
clause 3 converts it to rounds at application, so a one-minute condition applied in a fight
is retired by the fight. Once the encounter ends there is nothing counting it — that
disagreement between the axes is the cost 0021 accepted, and it is unchanged here.

What does **not** follow is that time is passing on the clock. `EncounterState.advanced_turn`
still leaves `Clock` untouched (0021 clause 2). Knowing what a round is worth is not knowing
how much campaign time has elapsed, and a converted duration can therefore disagree with a
clock the agent advances mid-encounter — an accepted cost that record names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.clock import (
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    SECONDS_PER_ROUND,
)
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: R31.
DURATION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Spells" -> Duration, p. 106 (Concentration, Instantaneous, Time '
        'Span); "Equipment" -> Oil, p. 98 (counting rounds from an event, and the '
        'round-to-seconds equivalence); "Spell Descriptions", p. 63 (the repeated save '
        "`SaveEnds` carries, stated per-effect with its own ability and DC); Rules "
        "Glossary, Prone p. 186 and Unconscious p. 191"
    ),
    # Unchanged, for the reason #129 gives for `TIME_VERIFICATION`: p. 63's clause was
    # asserted in `scripts/verify_d20_rules.py` on this date (#113). What was missing was
    # the citation, not the check.
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)

SECONDS_PER_MINUTE: Final = 60
#: Not an SRD value on its own — it is p. 98's six seconds, arranged. Named so the
#: conversion appears once rather than at every call site.
ROUNDS_PER_MINUTE: Final = SECONDS_PER_MINUTE // SECONDS_PER_ROUND


class DurationKind(StrEnum):
    """Why a condition will end, in the document's own terms."""

    #: A time span in rounds (p. 106), including one converted from minutes.
    ROUNDS = "rounds"
    #: "until the end of your next turn" — 62 occurrences, e.g. Rage (p. 29).
    END_OF_NEXT_TURN = "end-of-next-turn"
    #: A time span on the campaign clock — hours or days (p. 106's "or the like"), as a
    #: minute `Clock` will reach. Retired by elapsing time, never by taking a turn (#111).
    CAMPAIGN_TIME = "campaign-time"
    #: No span this engine can retire: the effect that imposed it names no time, or names
    #: one neither axis can count. Reported, never silently permanent.
    UNTIL_REMOVED = "until-removed"


#: The kinds the encounter axis retires, as against the one the clock does. Named because
#: two places have to agree on the split, and a membership test that lives at both of them
#: is a split that can drift.
ENCOUNTER_KINDS: Final = frozenset({DurationKind.ROUNDS, DurationKind.END_OF_NEXT_TURN})


class SpanUnit(StrEnum):
    """The unit an effect stated its span in, before the engine converted it."""

    MINUTES = "minute"
    HOURS = "hour"
    DAYS = "day"


@dataclass(frozen=True)
class StatedSpan:
    """What the effect actually said, kept so the conversion is visible (0021 clause 4).

    A round count or a clock minute alone is a number nobody can trace back to the sentence
    that produced it. This is the sentence's half of the arithmetic.
    """

    amount: int
    unit: SpanUnit

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("a duration is not negative")

    @property
    def in_minutes(self) -> int:
        """The span as minutes of campaign time."""
        if self.unit is SpanUnit.MINUTES:
            return self.amount
        if self.unit is SpanUnit.HOURS:
            return self.amount * MINUTES_PER_HOUR
        return self.amount * MINUTES_PER_DAY

    def __str__(self) -> str:
        plural = "" if self.amount == 1 else "s"
        return f"{self.amount} {self.unit.value}{plural}"


@dataclass(frozen=True)
class SaveEnds:
    """p. 63's shape: "repeats the save at the end of each of its turns, ending the effect
    on itself on a success".

    The ability and DC come from the effect that imposed the condition, because the document
    states this per-effect and has no general rule to read them from.

    **Nothing here rolls it.** A save is an outcome, and R1 leaves outcomes to the one
    adjudication entry point — so this records that a save is *due*, exactly as
    `Combatant.makes_death_saves` records that a death save is due, and the turn loop is what
    consults it.
    """

    ability: str
    dc: int

    def __post_init__(self) -> None:
        if self.dc < 1:
            raise ValueError(f"a save DC is a positive target number, not {self.dc}")


@dataclass(frozen=True)
class Duration:
    """When a condition ends, computed once at the moment it is applied.

    One of two expiry points is set, never both, because a span is counted by one axis:

    * **Encounter** — `ends_after_round` and `ends_after_actor_id`: the end of that
      creature's turn, in that round.
    * **Campaign** — `ends_at_minute`: the minute `Clock` reaches, absolute rather than
      remaining, so that reading it twice cannot give two answers.

    All three are `None` for `UNTIL_REMOVED`, which is the honest answer when nothing stated
    a span either axis can count.
    """

    kind: DurationKind
    ends_after_round: int | None = None
    ends_after_actor_id: str | None = None
    #: The campaign axis (#111): an elapsed-minute count on `Clock`, not a remaining one.
    ends_at_minute: int | None = None
    #: An early-out that runs alongside the span, not instead of it (p. 63).
    save: SaveEnds | None = None
    #: 0021 clause 4: the span as the effect stated it, before this engine converted it.
    stated: StatedSpan | None = None

    def __post_init__(self) -> None:
        on_encounter_axis = self.kind in ENCOUNTER_KINDS
        on_campaign_axis = self.kind is DurationKind.CAMPAIGN_TIME

        if on_encounter_axis and (
            self.ends_after_round is None or self.ends_after_actor_id is None
        ):
            raise ValueError(
                f"a {self.kind} duration ends at the end of a named creature's turn in a "
                "named round, so both are required. A span with no expiry point is "
                "UNTIL_REMOVED, which says so"
            )
        if not on_encounter_axis and (
            self.ends_after_round is not None or self.ends_after_actor_id
        ):
            raise ValueError(
                f"a {self.kind} duration is not counted by the turn order, so it names no "
                "round and no creature. Naming one would put an expiry point on an axis "
                "that will never read it"
            )
        if on_campaign_axis and self.ends_at_minute is None:
            raise ValueError(
                "a campaign-time duration ends at a minute on the clock, so one is required"
            )
        if not on_campaign_axis and self.ends_at_minute is not None:
            raise ValueError(
                f"a {self.kind} duration is not counted by the clock, so it names no minute"
            )
        if self.ends_at_minute is not None and self.ends_at_minute < 0:
            raise ValueError("the clock counts forward only, so an expiry minute is not negative")

    @property
    def retirable(self) -> bool:
        """Whether this engine can end it on its own. `False` is reported, not hidden."""
        return self.kind is not DurationKind.UNTIL_REMOVED

    def expires_at(self, round_number: int, actor_id: str) -> bool:
        """Whether the turn that just ended is the one this duration was waiting for.

        The encounter axis only. A campaign-time span is never retired by taking a turn,
        because taking a turn does not move the clock (0021 clause 2).
        """
        return (
            self.kind in ENCOUNTER_KINDS
            and round_number >= (self.ends_after_round or 0)
            and actor_id == self.ends_after_actor_id
        )

    def expires_by(self, elapsed_minutes: int) -> bool:
        """Whether the clock has reached the minute this duration was waiting for (#111).

        The campaign axis only, and the mirror of `expires_at`. `>=` rather than `==`
        because the agent supplies elapsed time in whatever chunks the narrative came in:
        a span due at minute 90 must still retire when someone rests for two hours.
        """
        return self.kind is DurationKind.CAMPAIGN_TIME and elapsed_minutes >= (
            self.ends_at_minute or 0
        )

    def derivation(self) -> str:
        """How this expiry point was arrived at (R5), including any conversion."""
        if not self.retirable:
            return "until removed: no span either axis can count"
        save = (
            f"; or a DC {self.save.dc} {self.save.ability} save at end of turn" if self.save else ""
        )
        if self.kind is DurationKind.CAMPAIGN_TIME:
            stated = f"{self.stated} = {self.stated.in_minutes} minutes; " if self.stated else ""
            return f"{stated}ends once the clock reaches minute {self.ends_at_minute}{save}"
        stated = (
            f"{self.stated} = {self.stated.in_minutes * ROUNDS_PER_MINUTE} rounds "
            f"(p. 98: a round is {SECONDS_PER_ROUND} seconds); "
            if self.stated is not None
            else ""
        )
        return (
            f"{stated}ends after {self.ends_after_actor_id}'s turn in round "
            f"{self.ends_after_round}{save}"
        )


def rounds_in_minutes(minutes: int) -> int:
    """A span stated in minutes as a round count (0021).

    p. 98 prints the equivalence the arithmetic rests on — two rounds "or 12 seconds" — so
    this is transcription rather than an inferred rule value. It converts in one direction
    only: elapsed campaign minutes are never expressed as rounds, because outside an
    encounter there are no rounds to count (0021 clause 5).
    """
    if minutes < 0:
        raise ValueError("a duration is not negative")
    return minutes * ROUNDS_PER_MINUTE
