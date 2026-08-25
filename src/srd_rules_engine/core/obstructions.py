"""What blocks a line, and what that does to an area of effect (#91, R16).

Closes the fidelity gap `core.areas` shipped disclosed: an area computed as unobstructed
volume reports a creature behind a wall as caught by a Fireball, which is a confident wrong
answer rather than a declined one.

p. 177: "If all straight lines extending from the point of origin to a location in the area
of effect are blocked, that location isn't included in the area of effect. To block a line,
an obstruction must provide Total Cover."

## What the document computes, and what it does not

Two different questions live under "cover", and only one of them has a method in the SRD.

* **Is the line blocked?** Geometric, and p. 177 states it: a straight line from the point of
  origin, blocked by something providing Total Cover. That is computable and is computed
  here.
* **Which degree of cover applies?** p. 15 gives the thresholds — Half is "another creature
  or an object that covers at least half of the target", Three-Quarters "at least
  three-quarters", Total "the whole target" — and **supplies no method for measuring what
  fraction of a target is covered**. Corner-counting, silhouette area, and eyeballing it are
  all house rules.

So this module answers the first and refuses the second. `total_cover` is decided; `HALF`
and `THREE_QUARTERS` exist with their benefits attached so a caller that has determined the
degree can apply it, and nothing here guesses which one applies. Same standing as the
measurement decision in 0014: *grounded in* the document rather than *cited from* it, and
disclosed rather than presented as a rule the document supplies.

## Obstructions are axis-aligned boxes, and that is a narrowing

A wall, a pillar, a closed door — a box in feet with two opposite corners. Arbitrary
geometry is not expressible, so a diagonal barricade has to be approximated by boxes or left
out. Stated because a model that silently rounds a shape is worse than one that says what it
holds.

## No float, again

The slab test uses `fractions.Fraction`, which is exact rational arithmetic rather than
floating point — `core.canonical` refuses floats and this module produces none. Nothing here
is stored in a ledger regardless; the discipline is kept because a boundary decided by a
rounded value is wrong exactly at the boundary, which is decision 0014's finding.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Final

from srd_rules_engine.core.position import Box, Position
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: R31. The blocking rule is cited; the method for measuring a *degree* of cover is not,
#: because the document does not supply one.
COVER_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Rules Glossary, Area of Effect p. 177 and Cover p. 179; "Playing the '
        'Game" ("Combat" -> Cover table), p. 15'
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)


class Cover(StrEnum):
    """The three degrees (p. 179), and the benefit each confers (p. 15)."""

    NONE = "none"
    HALF = "half"
    THREE_QUARTERS = "three-quarters"
    TOTAL = "total"

    @property
    def bonus(self) -> int:
        """p. 15: +2 for Half, +5 for Three-Quarters. Total is not a bonus — it is a
        prohibition, so it contributes nothing to a roll that cannot be made."""
        return {Cover.HALF: 2, Cover.THREE_QUARTERS: 5}.get(self, 0)

    @property
    def can_be_targeted(self) -> bool:
        """p. 179: Total Cover "can't be targeted directly"."""
        return self is not Cover.TOTAL


def most_protective(degrees: Iterable[Cover]) -> Cover:
    """p. 15: "only the most protective degree applies; the degrees aren't added together."

    The document's own example: a target behind a creature giving Half Cover and a tree
    trunk giving Three-Quarters has Three-Quarters. Adding them would give +7, which is a
    number the rules never produce.
    """
    order = (Cover.NONE, Cover.HALF, Cover.THREE_QUARTERS, Cover.TOTAL)
    best = Cover.NONE
    for degree in degrees:
        if order.index(degree) > order.index(best):
            best = degree
    return best


@dataclass(frozen=True)
class Obstruction(Box):
    """A `Box` in feet that provides Total Cover.

    It adds one thing to the box: `blocks`. The corners, their normalisation and `contains`
    are the box's, shared with `LitVolume` since #161 — the same geometry, two different
    facts about it.
    """

    def blocks(self, start: Position, end: Position) -> bool:
        """Whether the segment from `start` to `end` passes through this box.

        The slab method, in exact rational arithmetic. A segment that merely grazes a face
        does intersect — and a creature *standing inside* an obstruction is not blocked from
        itself, so an endpoint inside the box does not block the line to it.
        """
        if self.contains(start) or self.contains(end):
            return False

        near, far = Fraction(0), Fraction(1)
        for origin, target, low, high in (
            (start.x, end.x, self.lo.x, self.hi.x),
            (start.y, end.y, self.lo.y, self.hi.y),
            (start.z, end.z, self.lo.z, self.hi.z),
        ):
            direction = target - origin
            if direction == 0:
                if not low <= origin <= high:
                    return False
                continue
            first = Fraction(low - origin, direction)
            second = Fraction(high - origin, direction)
            if first > second:
                first, second = second, first
            near = max(near, first)
            far = min(far, second)
            if near > far:
                return False
        return True


def line_is_blocked(start: Position, end: Position, obstructions: Sequence[Obstruction]) -> bool:
    """p. 177: whether every straight line from `start` to `end` is blocked.

    A location is modelled as a *point*, so there is exactly one such line — a narrowing the
    document does not make, since a creature occupies a space and a wall might block some
    lines to it and not others. Stated rather than smoothed over: a target half behind a
    pillar is reported as fully blocked or not blocked at all.
    """
    return any(obstruction.blocks(start, end) for obstruction in obstructions)


def total_cover(start: Position, end: Position, obstructions: Sequence[Obstruction]) -> Cover:
    """The only degree this engine decides.

    Total Cover follows from the line being blocked (p. 15: "an object that covers the whole
    target"). Half and Three-Quarters depend on what fraction of a target is covered, and the
    document supplies no method for measuring that — so they are never returned here, and a
    caller that has determined a degree by some other means applies it itself.
    """
    return Cover.TOTAL if line_is_blocked(start, end, obstructions) else Cover.NONE
