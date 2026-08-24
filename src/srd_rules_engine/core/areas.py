"""The six areas of effect, resolved in feet without a grid (R16).

p. 177: "The descriptions of many spells and other features specify that they have an area
of effect, which typically has one of six shapes... An area of effect has a point of
origin, a location from which the effect's energy erupts."

Built on decision [0014](../../../docs/decisions/0014-positional-state.md): positions are
three integers in feet, and **no float is produced here either**. Every membership test is
integer arithmetic — see "How the geometry stays exact" below.

## Whether the origin is in its own area differs by shape

This is the detail most likely to be got wrong by assuming one answer, so it is a field
rather than a constant, defaulted per shape from the document:

| Shape | Origin included? | Where it says so |
|---|---|---|
| Sphere | **yes** | p. 188 |
| Cylinder | **yes** | p. 180 |
| Cone | no | p. 179 |
| Cube | no | p. 179 |
| Line | no | p. 184 |
| Emanation | no | p. 181 |

The four that exclude it all add "unless its creator decides otherwise", so the default is
overridable rather than fixed.

## How the geometry stays exact

For a point `p`, an origin `o` and an integer direction `d`, with `v = p - o`:

* the along-axis component is `dot(v, d)`, and comparing it to a length `L` is
  `dot(v, d)² <= L² · |d|²` with `dot(v, d) >= 0`;
* the perpendicular offset squared, scaled by `|d|²`, is `|v|²·|d|² - dot(v, d)²`.

Both are integers, so a Cone's widening — "a Cone's width at any point along its length is
equal to that point's distance from the point of origin" (p. 179), so the radius is half
the along-axis distance — becomes `4·(|v|²·|d|² - dot²) <= dot²`. No square root is taken
anywhere, and no boundary is decided by a rounded value.

## Obstructions are honoured, when you supply them

p. 177: "If all straight lines extending from the point of origin to a location in the area
of effect are blocked, that location isn't included in the area of effect. To block a line,
an obstruction must provide Total Cover."

`creatures_in` takes the obstructions and applies that rule (#91). A shape's `contains` is
still pure volume — geometry with no opinion about walls — because a caller asking "is this
point inside a sphere" is asking a different question from "would the effect reach it".

**Supplying none means none exist**, not that they are ignored. An encounter that tracks no
walls gets unobstructed volume, which is the correct answer for an open field and a wrong one
for a dungeon. The engine cannot tell those apart and does not pretend to.

**A Cube's freedom of placement.** p. 179 puts the point of origin "anywhere on a face of
the Cube" and constrains the orientation no further. This models the origin at the *centre*
of a face, with the cube axis-aligned to the chosen direction. Both are narrowings, and a
Cube placed cornerwise is not expressible.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from srd_rules_engine.core.obstructions import Obstruction, line_is_blocked
from srd_rules_engine.core.position import Position, squared_distance
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: R31.
AREA_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Area of Effect p. 177, Cone p. 179, Cube p. 179, "
        "Cylinder p. 180, Emanation p. 181, Line p. 184, Sphere p. 188"
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)


@dataclass(frozen=True)
class Direction:
    """An integer direction. Never normalised, so no float enters the geometry."""

    dx: int
    dy: int
    dz: int = 0

    def __post_init__(self) -> None:
        if (self.dx, self.dy, self.dz) == (0, 0, 0):
            raise ValueError("a direction points somewhere; (0, 0, 0) points nowhere")

    @property
    def squared_length(self) -> int:
        return self.dx**2 + self.dy**2 + self.dz**2


class Area(Protocol):
    """Anything with a point of origin that can say whether a point is inside it.

    The origin is part of the protocol because p. 177's blocking rule measures from it —
    "all straight lines extending from the point of origin" — so an area that could not name
    its own origin could not be checked against a wall.
    """

    @property
    def origin(self) -> Position: ...

    def contains(self, point: Position) -> bool: ...


def _offset(origin: Position, point: Position) -> tuple[int, int, int]:
    return (point.x - origin.x, point.y - origin.y, point.z - origin.z)


def _dot(v: tuple[int, int, int], d: Direction) -> int:
    return v[0] * d.dx + v[1] * d.dy + v[2] * d.dz


def _at_origin(origin: Position, point: Position) -> bool:
    return origin == point


@dataclass(frozen=True)
class Sphere:
    """p. 188: extends "outward in all directions"; the radius is the stated distance.

    "A Sphere's point of origin is included in the Sphere's area of effect."
    """

    origin: Position
    radius: int
    origin_included: bool = True

    def contains(self, point: Position) -> bool:
        if _at_origin(self.origin, point):
            return self.origin_included
        return squared_distance(self.origin, point) <= self.radius**2


@dataclass(frozen=True)
class Emanation:
    """p. 181: the same geometry as a Sphere, from a creature or object.

    Two things differ and both are rules rather than conveniences: the origin "isn't
    included in the area of effect unless its creator decides otherwise", and an Emanation
    "moves with the creature or object that is its origin unless it is an instantaneous or
    a stationary effect" — so the origin here is a position read afresh each time rather
    than a point fixed when the effect began.
    """

    origin: Position
    distance: int
    origin_included: bool = False

    def contains(self, point: Position) -> bool:
        if _at_origin(self.origin, point):
            return self.origin_included
        return squared_distance(self.origin, point) <= self.distance**2


@dataclass(frozen=True)
class Cylinder:
    """p. 180: the origin sits "at the center of the circular top or bottom".

    So `upward` is which of the two: a Cylinder specified from its base extends up, one
    specified from its top extends down. "A Cylinder's point of origin is included."
    """

    origin: Position
    radius: int
    height: int
    upward: bool = True
    origin_included: bool = True

    def contains(self, point: Position) -> bool:
        if _at_origin(self.origin, point):
            return self.origin_included
        dx, dy, dz = _offset(self.origin, point)
        if dx**2 + dy**2 > self.radius**2:
            return False
        return 0 <= dz <= self.height if self.upward else -self.height <= dz <= 0


@dataclass(frozen=True)
class Cone:
    """p. 179: "A Cone's width at any point along its length is equal to that point's
    distance from the point of origin."

    Width is the full spread, so the radius at distance `t` is `t / 2` — the document's own
    example is a Cone "15 feet wide at a point along its length that is 15 feet from the
    point of origin". The effect "specifies its maximum length", and the origin is excluded
    unless its creator decides otherwise.
    """

    origin: Position
    direction: Direction
    length: int
    origin_included: bool = False

    def contains(self, point: Position) -> bool:
        if _at_origin(self.origin, point):
            return self.origin_included
        v = _offset(self.origin, point)
        along = _dot(v, self.direction)
        if along < 0:
            return False
        scale = self.direction.squared_length
        if along**2 > self.length**2 * scale:
            return False
        squared_v = v[0] ** 2 + v[1] ** 2 + v[2] ** 2
        # perpendicular² · scale <= (along/2)² · scale, cleared of denominators.
        return 4 * (squared_v * scale - along**2) <= along**2


@dataclass(frozen=True)
class Line:
    """p. 184: "extends from a point of origin in a straight path along its length and
    covers an area defined by its width." Both are specified; the origin is excluded
    unless its creator decides otherwise.
    """

    origin: Position
    direction: Direction
    length: int
    width: int
    origin_included: bool = False

    def contains(self, point: Position) -> bool:
        if _at_origin(self.origin, point):
            return self.origin_included
        v = _offset(self.origin, point)
        along = _dot(v, self.direction)
        if along < 0:
            return False
        scale = self.direction.squared_length
        if along**2 > self.length**2 * scale:
            return False
        squared_v = v[0] ** 2 + v[1] ** 2 + v[2] ** 2
        return 4 * (squared_v * scale - along**2) <= self.width**2 * scale


@dataclass(frozen=True)
class Cube:
    """p. 179: "extends in straight lines from a point of origin located anywhere on a face
    of the Cube", with the size being "the length of each side". The origin is excluded
    unless its creator decides otherwise.

    **Narrowed, and the narrowing is disclosed.** The document places the origin anywhere on
    a face and does not constrain the orientation. This models the origin at the *centre* of
    a face, with the cube axis-aligned to `direction`, which must therefore be an axis. A
    Cube placed cornerwise is not expressible.
    """

    origin: Position
    direction: Direction
    size: int
    origin_included: bool = False

    def __post_init__(self) -> None:
        axes = [self.direction.dx, self.direction.dy, self.direction.dz]
        if sum(1 for a in axes if a != 0) != 1:
            raise ValueError(
                "this models axis-aligned Cubes only: `direction` must point along one "
                "axis. p. 179 allows any orientation; that is a disclosed narrowing"
            )
        if self.size <= 0:
            raise ValueError("a Cube's size is the length of each side, and is positive")

    def contains(self, point: Position) -> bool:
        if _at_origin(self.origin, point):
            return self.origin_included
        dx, dy, dz = _offset(self.origin, point)
        along_axis, across = self._split(dx, dy, dz)
        if not 0 <= along_axis <= self.size:
            return False
        # The face is centred on the origin, so the other two axes span half the size each
        # way. Compared doubled rather than halved: an odd size stays exact, and no float
        # enters the geometry.
        return all(abs(value) * 2 <= self.size for value in across)

    def _split(self, dx: int, dy: int, dz: int) -> tuple[int, tuple[int, int]]:
        d = self.direction
        if d.dx:
            return (dx if d.dx > 0 else -dx, (dy, dz))
        if d.dy:
            return (dy if d.dy > 0 else -dy, (dx, dz))
        return (dz if d.dz > 0 else -dz, (dx, dy))


def creatures_in(
    area: Area,
    positions: Mapping[str, Position],
    obstructions: Sequence[Obstruction] = (),
) -> tuple[str, ...]:
    """Which creatures the area reaches, in the order supplied.

    Two conditions, and they are different questions. A creature must be **inside the
    volume**, and the line to it from the point of origin must not be **blocked** (p. 177).
    A creature standing behind a wall inside a Fireball's radius satisfies the first and
    fails the second.

    Obstructions default to none, which means *there are none* rather than *ignore them*.
    """
    return tuple(
        who
        for who, where in positions.items()
        if area.contains(where) and not line_is_blocked(area.origin, where, obstructions)
    )
