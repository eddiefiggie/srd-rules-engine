"""What time is in this engine, and what it deliberately is not (#85, #108).

Decisions [0020](../../../docs/decisions/0020-two-kinds-of-time.md) and
[0021](../../../docs/decisions/0021-a-round-is-six-seconds.md) govern this module; 0021
amends 0020's clause 1 and leaves the rest of it standing.

The engine could adjudicate a Stable creature's recovery, a rest, or any duration measured
in hours — except that there was nothing to hang them on. `EncounterState` advanced by
turns and had no representation of elapsed time at all. This module is that
representation, and the boundaries around it matter more than the arithmetic.

## Two kinds of time, one exact conversion, and no automatic bridge

* **Encounter time** is `EncounterState.round_number` — ordinal, and already here. "Until
  the end of your next turn" resolves against it.
* **Campaign time** is `Clock`, a monotonic count of elapsed minutes. "After 1d4 hours"
  resolves against it.

**A round is exactly six seconds** (p. 98: the oil burns "2 rounds from when the oil was lit
(or 12 seconds)"), and **the clock still never advances itself**. Those are two different
claims, and decision 0021 separates them after 0020 ran them together.

p. 13 says a round represents *about* 6 seconds; p. 98 needs a number to say when a fire goes
out and gives an exact one. The engine is in p. 98's position every time it retires a
duration, so it takes that sentence — transcription of an arithmetic the document performs,
not a precision it withholds.

What does **not** follow is that advancing a turn advances the clock. Campaign time also
passes outside encounters, so a three-hour march followed by a six-round fight would either
double-count or silently drop the march. The engine cannot know how much campaign time passed
between two encounters, which was 0020's real argument and is untouched. A caller who wants an
encounter's duration on the clock advances the clock itself.

## Minutes, because every campaign-scale duration in the document is one

Short Rest one hour (p. 187), Long Rest at least eight (p. 185), sixteen hours before
another may start (p. 185), a Stable creature after 1d4 hours (p. 18). Minutes express all
of them exactly, in integers. Seconds are the unit p. 98 states a round in, and `SECONDS_PER_ROUND`
carries that; the clock still counts minutes, because nothing at campaign scale is finer.

## The agent says how much time passed; the engine says what that did

Elapsed time is a narrative fact — only the agent knows the party walked for three hours —
so the agent supplies it, as a typed integer of minutes. That is R20's seam working as
designed: a typed value, never prose. What the elapsed time *does* is never the agent's
call. The invariant holds exactly as it does everywhere else: the agent decides *that* time
passed and *how much*, and can never decide how it turns out.

## The recovery die is rolled when the creature becomes Stable, not when the clock is read

This is the part that would be easy to get wrong. If the 1d4 were rolled at the moment
somebody asked "has it recovered yet", a caller could advance the clock an hour at a time
and re-draw until it liked the answer. So the die is rolled once, at stabilisation, from
that adjudication's own seed, and the resulting minute is stored. Crossing it is then a
comparison, not a roll — the same reasoning that gives replacements their own seed band in
`core.d20`.

Storing it on `DeathSaves` also settles the rule's condition structurally. p. 18 says a
Stable creature *that isn't healed* recovers, and `EncounterState.with_healing` already
resets `DeathSaves` wholesale — so healing voids the deadline because the deadline lives
inside the thing healing clears, rather than because somebody remembered to check.

## What recovery does not do

p. 18 says the creature regains 1 Hit Point. It does not say the Unconscious condition
ends, and the sentence that does end a condition on regaining hit points (p. 17) is about
Knocking Out a Creature, which is a different case. So this module restores a hit point and
touches no condition. Disclosed rather than tidied, because the tidy version would be a
rule the document does not contain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from srd_rules_engine.core.d20 import die
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: R31. Every value below appears on the cited page, and `scripts/verify_d20_rules.py`
#: matches each against the official PDF.
TIME_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Playing the Game" ("Combat" -> The Order of Combat, p. 13; '
        '"Damage and Healing" -> Stabilizing a Character, p. 18); Rules Glossary, '
        "Long Rest p. 185 and Short Rest p. 187"
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)

#: Not an SRD value — the unit the clock counts in, and the conversion into it.
MINUTES_PER_HOUR: Final = 60

#: p. 98, the Oil entry: the oil burns "2 rounds from when the oil was lit (or 12 seconds)".
#: Two rounds is twelve seconds, so a round is six — stated exactly, in a sentence doing rules
#: work, rather than the *about* p. 13 uses to describe what a round feels like. Decision 0021
#: settles that this is transcription of an equivalence the document performs rather than an
#: inferred rule value, and amends 0020 clause 1 accordingly.
#:
#: **Knowing what a round is worth is not knowing how much time has passed.** `advanced_turn`
#: still leaves the clock untouched, permanently — 0021 clause 2 — because campaign time also
#: flows outside encounters and only the agent knows how much.
SECONDS_PER_ROUND: Final = 6

#: p. 18: "A Stable creature that isn't healed regains 1 Hit Point after 1d4 hours."
STABLE_RECOVERY_SIDES: Final = 4
STABLE_RECOVERY_HIT_POINTS: Final = 1

#: Where the recovery die is drawn from in a seed's index space. `core.d20` bands the space
#: — d20 at 0-1, damage from 100, replacements from 200, adjustments from 300 — so a die
#: drawn here can never land on one that seed has already produced. The bands are still a
#: convention rather than an enforced invariant (#82); this one is deliberately far above
#: the highest band in use.
RECOVERY_OFFSET: Final = 500


@dataclass(frozen=True)
class Clock:
    """Elapsed campaign time, in minutes, counted from an unspecified zero.

    The zero has no meaning: nothing in the SRD is expressed as an absolute date, so the
    clock answers "how long since" and never "when". Monotonic, because a duration that
    could be un-elapsed would let a caller withdraw a consequence the engine had already
    decided.
    """

    elapsed_minutes: int = 0

    def __post_init__(self) -> None:
        if self.elapsed_minutes < 0:
            raise ValueError("elapsed time is not negative; the clock counts forward only")

    def advanced(self, minutes: int) -> Clock:
        """Move the clock forward. Zero is allowed and is a no-op; negative is refused."""
        if minutes < 0:
            raise ValueError("time does not run backwards")
        return Clock(self.elapsed_minutes + minutes)

    @property
    def elapsed_hours(self) -> int:
        """Whole hours elapsed. Floor division, so a partial hour is not one."""
        return self.elapsed_minutes // MINUTES_PER_HOUR


def hours(count: int) -> int:
    """Minutes in `count` hours, so a caller never writes the 60 itself."""
    if count < 0:
        raise ValueError("a duration is not negative")
    return count * MINUTES_PER_HOUR


def stable_recovery_minute(now: Clock, *, seed: int) -> int:
    """The minute a creature becoming Stable now would regain 1 hit point (p. 18).

    Rolled here, once, rather than at the moment somebody asks whether it has happened —
    see this module's docstring. `seed` is the adjudication's own seed, so the recovery
    replays from the record like every other die this engine throws (R4).
    """
    rolled = die(seed, RECOVERY_OFFSET, STABLE_RECOVERY_SIDES)
    return now.elapsed_minutes + hours(rolled)
