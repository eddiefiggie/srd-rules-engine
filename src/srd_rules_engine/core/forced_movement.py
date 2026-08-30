"""Moving a creature by something other than itself (0055).

> p. 90, *Push.* If you hit a creature with this weapon, you can push the creature up to 10
> feet **straight away from yourself** if it is Large or smaller.
>
> p. 169, *Thunderwave.* ...a creature takes 2d8 Thunder damage and is **pushed 10 feet away
> from you**.
>
> p. 320, *Roper.* **Reel.** The roper pulls each creature Grappled by it up to 30 feet
> **straight toward it**.

Twenty-odd rules across spells, class features, a magic item, a weapon mastery and fourteen
stat blocks. This is the primitive they share.

## The geometry is the whole difficulty

[0014](../../../docs/decisions/0014-positional-state.md) makes a `Position` three **integer**
feet and is emphatic that distance is never a float. "Straight away from yourself" is the ray
from the anchor through the creature, and `d` feet along it lands on integer coordinates only
when that ray is axis-aligned. A source at `(0,0,0)` pushing a creature at `(5,5,0)` ten feet
lands at `(12.07…, 12.07…, 0)`, which this engine cannot represent.

**So the destination is the lattice point nearest the exact one, and it may not be further from
where the creature stood than the rule allows.** Two properties, and the second is a hard
constraint rather than a preference:

* *Nearest the exact destination* serves both objectives at once. The exact destination lies on
  the ray at exactly the stated distance, so a point near it is near the ray **and** near the
  right distance — one number to minimise instead of two to trade off.
* *Never further than stated* is 0030 clause 1. Overshooting moves a creature further than the
  rule grants, which can carry it out of an area or past a boundary the rule did not reach;
  falling short withholds distance the rule did grant. Only the first manufactures something.

There is always a solution: the corner of the unit cube around the exact destination that lies
nearest the origin is no further from the origin than the exact destination is.

**This is not a new kind of error.** Every position in this engine is already a lattice point,
so the resolution is the model's rather than this function's. What is new is that the *engine*
picks a destination where a caller used to. `Displacement` therefore records what was asked for
and what was achieved, and they are usually not the same number.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Final

from srd_rules_engine.core.position import Position, distance_feet, squared_distance

#: The granularity a push is offered in when a rule says "up to N feet".
#:
#: **Every push and pull distance in SRD v5.2.1 is a multiple of five** — 5, 10, 15, 20, 25,
#: 30 and 60 — so five feet is the document's own vocabulary rather than the grid's, which
#: this project treats as an optional variant. The rule permits any distance up to the
#: maximum, and the shorter ones between the steps are not offered; that narrowing is
#: disclosed rather than silent.
PUSH_STEP_FEET: Final = 5


@dataclass(frozen=True)
class Displacement:
    """Where a forced move put a creature, and how far that turned out to be.

    `requested` and `achieved` are usually different, because the exact destination is
    almost never a lattice point. Both are recorded because a reader checking a push against
    the page needs the number the rule stated *and* the number the engine produced — one
    without the other is half a ruling (R30).
    """

    to: Position
    requested_feet: int
    achieved_feet: int

    def derivation(self) -> str:
        exact = (
            ""
            if self.achieved_feet == self.requested_feet
            else (", the nearest whole-foot position not further than that")
        )
        return (
            f"moved {self.achieved_feet} feet to ({self.to.x}, {self.to.y}, {self.to.z}) "
            f"of the {self.requested_feet} the rule allows{exact}"
        )


def displaced(origin: Position, *, anchor: Position, feet: int, away: bool) -> Displacement | None:
    """Where a creature at `origin` ends up, pushed `feet` from or pulled toward `anchor`.

    `None` when there is no direction to move in — the creature and the anchor share a
    position, so "straight away from" names no ray. Refused rather than resolved, because
    picking a direction would be the engine choosing where a creature is thrown.

    A pull stops at the anchor rather than passing through it: p. 320's roper reels a creature
    *toward* itself, and a pull that overshot would put the creature on the far side, which no
    rule describes.
    """
    if feet < 0:
        raise ValueError(f"a forced move covers zero or more feet, not {feet}")
    span = squared_distance(origin, anchor)
    if span == 0:
        return None
    if feet == 0:
        return Displacement(to=origin, requested_feet=0, achieved_feet=0)

    length = math.sqrt(span)
    # The unit vector *from* the anchor *through* the creature. A push follows it; a pull
    # reverses it. One vector and a sign, because "straight away" and "straight toward" are
    # the same line read in two directions.
    step = 1.0 if away else -1.0
    ux = (origin.x - anchor.x) / length
    uy = (origin.y - anchor.y) / length
    uz = (origin.z - anchor.z) / length
    # A pull never travels further than the anchor itself. p. 320 reels a creature toward the
    # roper, and a creature that arrived past it would be somewhere no rule put it.
    travelled = feet if away else min(feet, int(length))
    exact = (
        origin.x + step * ux * travelled,
        origin.y + step * uy * travelled,
        origin.z + step * uz * travelled,
    )

    # Every corner of the unit cube around the exact destination, keyed by how far it is from
    # that destination and then by its own coordinates. **One expression, evaluated once per
    # candidate**: the key was computed in two places until a corruption proof showed the two
    # could disagree without any test noticing.
    #
    # The coordinate tie-break is not decoration. A 45-degree push has two corners at
    # identical distance, and a `min` over an unordered key would resolve them by whichever
    # the loop reached first — reproducible today and not promised to stay so (R4).
    candidates = [
        (sum((c - e) ** 2 for c, e in zip(corner, exact, strict=True)), corner)
        for corner in itertools.product(*((math.floor(c), math.ceil(c)) for c in exact))
        # Never further from where it stood than the rule allows (0030 clause 1).
        if squared_distance(origin, Position(*corner)) <= travelled * travelled
    ]
    # Unreachable in principle: the corner of the cube nearest the origin is never further
    # from it than the exact destination is. Asserted rather than assumed, because "in
    # principle" is where the arithmetic bugs live.
    assert candidates, "no lattice destination within the stated distance"
    destination = Position(*min(candidates)[1])
    return Displacement(
        to=destination,
        requested_feet=feet,
        achieved_feet=distance_feet(origin, destination),
    )


def push_distances(maximum: int) -> tuple[int, ...]:
    """The distances a push of "up to `maximum` feet" is offered at.

    Five-foot steps, and the maximum itself if it is not one of them. See `PUSH_STEP_FEET`
    for why five: it is every distance the document names, not the grid.
    """
    if maximum <= 0:
        return ()
    steps = list(range(PUSH_STEP_FEET, maximum + 1, PUSH_STEP_FEET))
    if maximum not in steps:
        steps.append(maximum)
    return tuple(steps)
