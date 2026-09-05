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
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Final

from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.turn_span import TurnBoundary

#: p. 186: "A creature has a reach of 5 feet unless a rule says otherwise."
DEFAULT_REACH_FEET: Final = 5

#: p. 90: a Reach weapon "adds 5 feet to your reach". Added to the creature's own reach
#: rather than replacing it, because p. 186's 5 is a default and not a ceiling — a creature
#: that already reaches further keeps the difference (#316).
REACH_PROPERTY_FEET: Final = 5

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
    method=VerificationMethod.ASSERTED,
)


@dataclass(frozen=True)
class Position:
    """A point in feet. `z` is elevation, so a flying creature is genuinely above."""

    x: int
    y: int
    z: int = 0


@dataclass(frozen=True)
class Box:
    """An axis-aligned box in feet, given by two opposite corners.

    The corners are normalised on construction, so `lo` always holds the minimum of each
    axis and `hi` the maximum: a caller describing a wall or a lit room should not have to
    sort its corners first, and every reader downstream can rely on the ordering without
    re-checking it.

    **This is a shape, not a meaning.** It carries no opinion about what occupying that
    volume does — blocking a line and holding a light level are different facts about the
    same geometry, and they stay different types (`Obstruction` and `LitVolume`). What is
    shared is the box and its normalisation, which existed as two identical copies until
    [#161](https://github.com/eddiefiggie/srd-rules-engine/issues/161); the reason they were
    kept apart lapsed when [0026](../../../docs/decisions/0026-terrain-enters-as-state.md)
    settled that both kinds of terrain enter the engine as state.

    Integer arithmetic throughout, like everything built on
    [0014](../../../docs/decisions/0014-positional-state.md): no boundary is decided by a
    rounded value.
    """

    lo: Position
    hi: Position

    def __post_init__(self) -> None:
        low = Position(
            min(self.lo.x, self.hi.x), min(self.lo.y, self.hi.y), min(self.lo.z, self.hi.z)
        )
        high = Position(
            max(self.lo.x, self.hi.x), max(self.lo.y, self.hi.y), max(self.lo.z, self.hi.z)
        )
        object.__setattr__(self, "lo", low)
        object.__setattr__(self, "hi", high)

    def contains(self, point: Position) -> bool:
        """Whether the point is inside, faces included."""
        return (
            self.lo.x <= point.x <= self.hi.x
            and self.lo.y <= point.y <= self.hi.y
            and self.lo.z <= point.z <= self.hi.z
        )


class MovementMode(StrEnum):
    """How a creature is moving, because the cost differs by mode."""

    WALK = "walk"
    CLIMB = "climb"
    SWIM = "swim"
    FLY = "fly"
    BURROW = "burrow"
    CRAWL = "crawl"


#: p. 90's Slow, as a rule id. A literal repeated at both ends is one that drifts.
SLOW_RULE_ID: Final = "mastery-slow"

#: p. 90's Slow: "you can reduce its Speed by 10 feet".
SLOW_REDUCTION_FEET: Final = 10

#: p. 90's cap: "If the creature is hit more than once by weapons that have this property,
#: the Speed reduction doesn't exceed 10 feet." **The cap belongs to Slow**, not to speed
#: reductions in general — a future rule reducing a Speed by 15 is not bounded by this
#: sentence, so the sum is capped per rule rather than per creature (#322).
SLOW_REDUCTION_CAP_FEET: Final = 10


@dataclass(frozen=True)
class SpeedReduction:
    """A Speed reduction that stands until a named turn boundary (p. 90, #322, 0050).

    **Not a condition**, though it is retired the way one is. p. 90 gives it no name the
    Rules Glossary tags `[Condition]`, and nothing else reads it.

    **Not spent, unlike a `PendingAdvantage`.** 0049's tokens are consumed by the roll they
    apply to; this one simply stands for its window. The two share `core.turn_span`'s
    boundary and nothing else, which is why they are separate structures.
    """

    #: Which rule imposed it, and therefore which cap it counts against.
    rule_id: str
    feet: int
    #: Whose turn bounds it, in which round, and at which end of that turn. p. 90's Slow ends
    #: at the **start** of the attacker's next turn, so the creature whose turn ends it is not
    #: the creature carrying it.
    expires_after_actor_id: str
    expires_in_round: int
    expires_at: TurnBoundary

    def __post_init__(self) -> None:
        if self.feet <= 0:
            raise ValueError(
                "a Speed reduction takes feet away; zero takes nothing and a negative one "
                "would be a rule granting speed, which p. 90 does not"
            )


def slow_feet_taken(reductions: Sequence[SpeedReduction]) -> int:
    """How many feet p. 90's Slow takes from a Speed, across every source (#322).

    > If the creature is hit more than once by weapons that have this property, the Speed
    > reduction **doesn't exceed 10 feet**.

    A cap on the sum rather than a cap per source, and one that counts only Slow's own
    reductions — the sentence bounds *this* property, so a future rule taking 15 feet is not
    quietly limited by it. Two Slow hits from different wielders therefore take 10 feet
    between them and each keeps its own expiry, so the creature stays slowed until the later
    boundary passes.
    """
    slow = sum(r.feet for r in reductions if r.rule_id == SLOW_RULE_ID)
    return min(slow, SLOW_REDUCTION_CAP_FEET)


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


def distance_feet(a: Position, b: Position, *, slack: Fraction = Fraction(0)) -> int:
    """Straight-line distance in whole feet, rounded down.

    For the record, never for a comparison — `within` answers those exactly. A rounded
    distance that decided an outcome would put the boundary in the wrong place at exactly
    the range where it matters.

    `slack` is what two things' spaces bring them nearer than their points (p. 13, 0086;
    `size.range_slack`), taken off before the rounding: the largest whole number of feet
    that, plus the slack, still fits inside the straight line. Zero at the least — two
    creatures whose spaces overlap are not a negative distance apart.
    """
    exact = squared_distance(a, b)
    feet = math.isqrt(exact)
    if slack == 0:
        return feet
    # The largest n with (n + slack)² <= exact. Start where the plain distance leaves off
    # and step down; the slack is a multiple of 2½ feet, so at most one step is needed.
    n = max(0, feet - math.ceil(slack))
    while (n + 1 + slack) * (n + 1 + slack) <= exact:
        n += 1
    return n


def within(a: Position, b: Position, feet: int, *, slack: Fraction = Fraction(0)) -> bool:
    """Whether `b` is within `feet` of `a`, decided without a square root.

    Exact where a rounded distance is not: two points 5.9 feet apart are not within 5
    feet, and `distance_feet` would call them 5.

    **`slack` is how a creature's space enters a range** (p. 13, 0086). The grid measures a
    range from a square adjacent to one thing to the space of the other, so a creature that
    fills more than one square is nearer than its point by the excess — `size.range_slack`
    sums it for both ends. The comparison stays exact: `Fraction` squares against an integer.
    A point, an object and a Medium creature add nothing, so every range test that held
    before 0086 holds unchanged for them.
    """
    if feet < 0:
        raise ValueError("a range is not negative")
    if slack < 0:
        raise ValueError("a space makes nothing further away than its point")
    limit = feet + slack
    return squared_distance(a, b) <= limit * limit


def movement_cost(
    feet: int,
    *,
    mode: MovementMode,
    difficult_terrain: bool,
    speeds: Speeds,
    carrying: int = 0,
) -> int:
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

    p. 182, *Movable*: "every foot of movement costs it 1 extra foot" for each grappled
    creature the grappler brings along and is not carrying free. `carrying` is how many of
    those there are, and it **adds** rather than replacing — a second reading this function
    takes, and a second one the document does not settle outright.

    The evidence for adding is that Difficult Terrain carries its own non-cumulative clause
    ("either a space is Difficult Terrain or it isn't") and *Movable* carries none. A
    document that says so where it means it has not said so here.
    """
    if feet < 0:
        raise ValueError("movement is not negative")
    if carrying < 0:
        raise ValueError(f"a grappler carries no fewer than nobody, not {carrying}")

    extra = 1 if difficult_terrain else 0
    costlier = (MovementMode.CLIMB, MovementMode.SWIM, MovementMode.CRAWL)
    if mode in costlier and not speeds.has_special_speed(mode):
        extra = 2 if difficult_terrain else 1

    return feet * (1 + extra + carrying)


#: p. 183: a High Jump is "3 plus your Strength modifier (minimum of 0 feet)".
HIGH_JUMP_BASE_FEET: Final = 3

#: pp. 183-185: both jumps need "at least 10 feet" of movement immediately before, or they
#: are standing jumps and reach half as far.
RUN_UP_FEET: Final = 10


def long_jump_feet(strength_score: int, *, running: bool = True) -> int:
    """How far a creature leaps horizontally (pp. 184-185).

    "You leap horizontally a number of feet up to your Strength **score**" — the score, not
    the modifier, which is the half of this pair most easily swapped with the other. A
    Strength 16 creature jumps 16 feet and high-jumps 6, and an engine that used the modifier
    for both would give it 3 and 3 while looking entirely reasonable.

    "When you make a standing Long Jump, you can leap only half that distance", rounded down
    like everything else (p. 187).

    Each foot costs a foot of movement, which is the caller's to spend — `movement_cost`
    charges it, and this returns the distance rather than deducting it.
    """
    if strength_score < 0:
        raise ValueError(f"a Strength score is not {strength_score}")
    return strength_score if running else strength_score // 2


def space_contains(centre: Position, width: Fraction, point: Position) -> bool:
    """Whether `point` falls inside the square space of a creature at `centre` (p. 14, #337).

    **Centred on the creature, which is an engine convention and is stated as one.** p. 14
    describes the space as what a size "determines... on a map", and a map here means a grid —
    which this project declines as a default (`AGENTS.md`). Without one there is no square to
    align to, so the width is hung symmetrically about the creature's own point. The document
    supplies no other anchor, and picking a corner would be the same invention with a worse
    reading.

    **A square, not a cube.** p. 14 gives a *width* and a square, and says nothing about
    height — so `z` is not bounded here. A flying creature directly overhead is not in the
    space below it, and the document does not say what would decide that; asking about `x` and
    `y` only is the reading that adds nothing.

    Inclusive at the boundary, because the alternative is a seam: two Medium creatures five
    feet apart would otherwise both fail to contain the midpoint that separates them.
    """
    half = width / 2
    return abs(Fraction(point.x - centre.x)) <= half and abs(Fraction(point.y - centre.y)) <= half


def high_jump_feet(strength_modifier: int, *, running: bool = True) -> int:
    """How far a creature leaps vertically (p. 183).

    "3 plus your Strength modifier (minimum of 0 feet)" — the **modifier** here, where the
    Long Jump takes the score. The floor is applied before the standing halving, because the
    document states it as a property of the distance rather than of the run-up.

    **What a creature can reach is not this**, and is not modelled: p. 183 adds "1½ times
    your height" to the jump, and nothing here knows how tall anything is. So `high-jump`
    stays unclaimed in the inventory while this arithmetic exists — the shape is the entry,
    and the entry says more than this can compute.
    """
    reached = max(0, HIGH_JUMP_BASE_FEET + strength_modifier)
    return reached if running else reached // 2
