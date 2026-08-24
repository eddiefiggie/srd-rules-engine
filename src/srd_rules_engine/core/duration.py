"""How long a condition lasts — and why that is not a property of the condition (#18).

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

This module covers the encounter axis of the time span, plus the early-out that appears
alongside it. Concentration is `core.spellcasting` and already ends its own effects;
Instantaneous never produces a lasting condition; campaign-scale spans are #18's remaining
scope and are named rather than silently treated as permanent.

## A duration is a span with optional early-outs

p. 63 shows both at once: the target "has the Poisoned condition **for 1 minute**. At the
end of each of its turns, the Poisoned target **repeats the save**, ending the effect on
itself on a success." One outer span, one early-out. Elsewhere the early-out is an event —
"the Unconscious condition for 1 minute **or until it takes any damage**".

There is **no general save-ends rule** in the document. Every instance states its own, which
is why `SaveEnds` carries the ability and DC from the effect that imposed it rather than
reading them from a table that does not exist.

## Everything reduces to one expiry point

A span ends **at the end of a named creature's turn, in a named round**. Both "for N rounds"
and "until the end of your next turn" compute to that pair when the condition is applied,
which is 0021 clause 3: converted once, at application, never re-derived on query. A value
re-derived whenever somebody asks is a value a caller can re-draw by choosing when to ask.

"For N rounds" is read off p. 98, which is the only place the document says what counting
rounds from an event means: the oil burns "until the end of the turn 2 rounds from when the
oil was lit". So N rounds later, at that same point in the order — not N turns, and not the
start of a round.

## Minutes convert; the campaign clock still does not move

Decision [0021](../../../docs/decisions/0021-a-round-is-six-seconds.md) settles that a round
is exactly six seconds (p. 98: two rounds "or 12 seconds"). A span stated in minutes
therefore has a round count, and `stated_minutes` records that it was converted so the
arithmetic is visible rather than implied (0021 clause 4).

What does **not** follow is that time is passing on the clock. `EncounterState.advanced_turn`
still leaves `Clock` untouched (0021 clause 2). Knowing what a round is worth is not knowing
how much campaign time has elapsed, and a converted duration can therefore disagree with a
clock the agent advances mid-encounter — an accepted cost that record names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.clock import SECONDS_PER_ROUND
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
        "round-to-seconds equivalence); Rules Glossary, Prone p. 186 and Unconscious "
        "p. 191"
    ),
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
    #: No span this engine can retire: the effect that imposed it names no time, or names
    #: one on an axis the encounter does not track. Reported, never silently permanent.
    UNTIL_REMOVED = "until-removed"


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

    `ends_after_round` and `ends_after_actor_id` are the expiry point: the end of that
    creature's turn, in that round. Both are `None` for `UNTIL_REMOVED`, which is the honest
    answer when nothing stated a span this engine can count.
    """

    kind: DurationKind
    ends_after_round: int | None = None
    ends_after_actor_id: str | None = None
    #: An early-out that runs alongside the span, not instead of it (p. 63).
    save: SaveEnds | None = None
    #: 0021 clause 4: the span as stated, when it was stated in minutes and converted.
    stated_minutes: int | None = None

    def __post_init__(self) -> None:
        timed = self.kind is not DurationKind.UNTIL_REMOVED
        if timed and (self.ends_after_round is None or self.ends_after_actor_id is None):
            raise ValueError(
                f"a {self.kind} duration ends at the end of a named creature's turn in a "
                "named round, so both are required. A span with no expiry point is "
                "UNTIL_REMOVED, which says so"
            )
        if not timed and (self.ends_after_round is not None or self.ends_after_actor_id):
            raise ValueError("an until-removed duration has no expiry point to name")
        if self.stated_minutes is not None and self.stated_minutes < 0:
            raise ValueError("a duration is not negative")

    @property
    def retirable(self) -> bool:
        """Whether this engine can end it on its own. `False` is reported, not hidden."""
        return self.kind is not DurationKind.UNTIL_REMOVED

    def expires_at(self, round_number: int, actor_id: str) -> bool:
        """Whether the turn that just ended is the one this duration was waiting for."""
        return (
            self.retirable
            and round_number >= (self.ends_after_round or 0)
            and actor_id == self.ends_after_actor_id
        )

    def derivation(self) -> str:
        """How this expiry point was arrived at (R5), including any conversion."""
        if not self.retirable:
            return "until removed: no span this engine can count"
        stated = (
            f"{self.stated_minutes} minute(s) = "
            f"{self.stated_minutes * ROUNDS_PER_MINUTE} rounds (p. 98: a round is "
            f"{SECONDS_PER_ROUND} seconds); "
            if self.stated_minutes is not None
            else ""
        )
        save = (
            f"; or a DC {self.save.dc} {self.save.ability} save at end of turn" if self.save else ""
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
