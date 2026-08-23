"""Where creatures are, how far apart, and what movement costs (R9, R13, R16).

Positions are **three coordinates in feet**, continuous rather than squared. The SRD
publishes movement and range in feet and offers the grid as an optional variant, so the
engine follows the published default — see `AGENTS.md`, where grid-based tactical movement
is a declined non-goal rather than deferred work.

## Why three dimensions

The document's areas of effect are solids: a Sphere "extends in straight lines from a point
of origin outward in all directions" (p. 188), a Cylinder specifies a height (p. 180), a
Cone widens with distance (p. 179). The inventory's movement shapes are elevation concepts
too — Fly Speed, Hover, Burrow Speed, Climb Speed. A flat model can hold those as numbers
but cannot resolve them, and adding a third axis afterwards would touch every distance
computation and every area shape.

## No floats, anywhere

`core.canonical` refuses floats in the ledger, and says in terms that "distances in feet are
all integers". Straight-line distance is irrational in general, so this module never
produces one:

* **Range tests compare squares.** `within` asks whether `dx² + dy² + dz² <= feet²`, which
  is exact integer arithmetic and answers the only question the rules actually ask.
* **A distance for the record uses `math.isqrt`**, an exact integer floor. It is a value to
  read, never a value to compare against, so its rounding cannot change an outcome.

## Straight-line measurement is a project decision, not a rule

**The SRD states no method for measuring distance.** It gives distances in feet and speaks
of straight lines, but it never says how to measure between two points on an open table.
Straight-line distance is therefore *grounded in* the document rather than *cited from* it —
the same standing this project gives the trigger catalogue.

It is disclosed here rather than presented as a rule the document supplies, because a
confident wrong number is indistinguishable from a right one once it is inside a finished
ruling. The optional grid variant, where diagonals are counted differently, is the SRD's
own alternative and is not implemented.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.rules import Verification, VerificationState

#: p. 186: "A creature has a reach of 5 feet unless a rule says otherwise."
DEFAULT_REACH_FEET: Final = 5

#: R31. The movement costs and the reach default are rule values; the measurement method
#: deliberately is **not** cited, because the document does not supply one.
MOVEMENT_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Speed p. 188, Difficult Terrain p. 181, Climbing "
        "p. 178, Swimming p. 189, Crawling p. 179, Reach p. 186; Playing the Game "
        '("Breaking Up Your Move"), p. 14'
    ),
    date="2026-08-23",
)


@dataclass(frozen=True)
class Position:
    """A point in feet. `z` is elevation, so a flying creature is genuinely above."""

    x: int
    y: int
    z: int = 0


class MovementMode(StrEnum):
    """How a creature is moving, because the cost differs by mode."""

    WALK = "walk"
    CLIMB = "climb"
    SWIM = "swim"
    FLY = "fly"
    BURROW = "burrow"
    CRAWL = "crawl"


@dataclass(frozen=True)
class Speeds:
    """A creature's Speed and its special speeds (p. 188).

    `None` means the creature has no such speed, which is different from a speed of 0 —
    a creature with a Fly Speed of 0 that Hovers is not the same as one that cannot fly.
    """

    walk: int = 30
    climb: int | None = None
    fly: int | None = None
    swim: int | None = None
    burrow: int | None = None
    #: p. 183: a creature that Hovers stays aloft without spending movement to do so.
    hover: bool = False

    def for_mode(self, mode: MovementMode) -> int | None:
        """The speed governing this mode, or None if the creature has no such speed.

        Walking and crawling both draw on Speed: crawling is not a separate speed, it is
        an ordinary move that costs more (p. 179).
        """
        if mode in (MovementMode.WALK, MovementMode.CRAWL):
            return self.walk
        return {
            MovementMode.CLIMB: self.climb,
            MovementMode.SWIM: self.swim,
            MovementMode.FLY: self.fly,
            MovementMode.BURROW: self.burrow,
        }[mode]

    def has_special_speed(self, mode: MovementMode) -> bool:
        return mode in (MovementMode.CLIMB, MovementMode.SWIM) and self.for_mode(mode) is not None


def squared_distance(a: Position, b: Position) -> int:
    """Distance squared, in square feet. Exact, and the basis of every range test."""
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2


def distance_feet(a: Position, b: Position) -> int:
    """Straight-line distance in whole feet, rounded down.

    For the record, never for a comparison — `within` answers those exactly. A rounded
    distance that decided an outcome would put the boundary in the wrong place at exactly
    the range where it matters.
    """
    return math.isqrt(squared_distance(a, b))


def within(a: Position, b: Position, feet: int) -> bool:
    """Whether `b` is within `feet` of `a`, decided without a square root.

    Exact where a rounded distance is not: two points 5.9 feet apart are not within 5
    feet, and `distance_feet` would call them 5.
    """
    if feet < 0:
        raise ValueError("a range is not negative")
    return squared_distance(a, b) <= feet * feet


def movement_cost(feet: int, *, mode: MovementMode, difficult_terrain: bool, speeds: Speeds) -> int:
    """What covering `feet` costs in movement, in feet.

    p. 181, Difficult Terrain: "every foot of movement in that space costs 1 extra foot",
    and it "isn't cumulative; either a space is Difficult Terrain or it isn't".

    pp. 178, 179, 189: climbing, swimming and crawling each cost "1 extra foot (2 extra
    feet in Difficult Terrain)". Climbing and swimming "ignore this extra cost" if the
    creature has the matching special speed and uses it; crawling has no such escape.

    **A reading is taken here and it is worth naming.** The parenthetical is read as
    *replacing* the extra rather than adding to Difficult Terrain's own — so climbing
    through Difficult Terrain costs 3 feet per foot, not 4. The alternative reading
    compounds them. Three is the arithmetic the two rules agree on when read together
    (1 base + 1 terrain + 1 climb), which is why it is taken; the document does not settle
    it outright.
    """
    if feet < 0:
        raise ValueError("movement is not negative")

    extra = 1 if difficult_terrain else 0
    costlier = (MovementMode.CLIMB, MovementMode.SWIM, MovementMode.CRAWL)
    if mode in costlier and not speeds.has_special_speed(mode):
        extra = 2 if difficult_terrain else 1

    return feet * (1 + extra)
