"""The six areas of effect (#20).

Two things are tested against the *wrong* answer rather than only the right one, because
both are the kind of detail an implementer settles by assuming rather than by reading:

* **Whether the origin is inside its own area differs by shape.** Three include it and
  three do not. One answer applied to all six would be right half the time.
* **A Cone's width is the full spread, not the radius.** Halving it or not halving it both
  produce a plausible cone, and the document supplies a worked example that separates them.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.areas import (
    AREA_VERIFICATION,
    Cone,
    Cube,
    Cylinder,
    Direction,
    Emanation,
    Line,
    Sphere,
    creatures_in,
)
from srd_rules_engine.core.obstructions import Obstruction
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import VerificationState

ORIGIN = Position(0, 0, 0)
EAST = Direction(1, 0, 0)


# --- Whether the origin is in its own area -------------------------------------------


def test_a_sphere_and_a_cylinder_include_their_origin() -> None:
    """p. 188 and p. 180 both say so in terms."""
    assert Sphere(ORIGIN, 20).contains(ORIGIN)
    assert Cylinder(ORIGIN, 10, 20).contains(ORIGIN)


def test_a_cone_cube_line_and_emanation_do_not() -> None:
    """pp. 179, 179, 184, 181 — each says "isn't included ... unless its creator decides
    otherwise". Assuming one answer for all six shapes would be right half the time."""
    assert not Cone(ORIGIN, EAST, 15).contains(ORIGIN)
    assert not Cube(ORIGIN, EAST, 10).contains(ORIGIN)
    assert not Line(ORIGIN, EAST, 30, 5).contains(ORIGIN)
    assert not Emanation(ORIGIN, 10).contains(ORIGIN)


def test_the_creator_may_decide_otherwise() -> None:
    """The exclusion is a default, not a rule — all four carry the same escape clause."""
    assert Cone(ORIGIN, EAST, 15, origin_included=True).contains(ORIGIN)
    assert Emanation(ORIGIN, 10, origin_included=True).contains(ORIGIN)


# --- Sphere and Emanation -------------------------------------------------------------


def test_a_sphere_reaches_exactly_its_radius() -> None:
    sphere = Sphere(ORIGIN, 20)
    assert sphere.contains(Position(20, 0, 0))
    assert not sphere.contains(Position(21, 0, 0))


def test_a_sphere_extends_in_all_directions_including_up() -> None:
    """p. 188: "outward in all directions". A flat model would include a point 20 feet up
    only by accident."""
    sphere = Sphere(ORIGIN, 20)
    assert sphere.contains(Position(0, 0, 20))
    assert not sphere.contains(Position(0, 0, 21))
    assert sphere.contains(Position(0, 12, 16)), "12² + 16² = 400, exactly the radius"


def test_the_sphere_boundary_is_exact_at_the_diagonal() -> None:
    """(12, 12, 12) is about 20.78 feet out. A rounded distance calls it 20 and includes
    it; the squared comparison does not. Same boundary error decision 0014 names.
    """
    assert not Sphere(ORIGIN, 20).contains(Position(12, 12, 12))
    assert Sphere(ORIGIN, 21).contains(Position(12, 12, 12))


def test_an_emanation_is_a_sphere_that_excludes_its_source() -> None:
    emanation = Emanation(ORIGIN, 10)
    assert emanation.contains(Position(10, 0, 0))
    assert not emanation.contains(Position(11, 0, 0))
    assert not emanation.contains(ORIGIN)


# --- Cone -----------------------------------------------------------------------------


def test_a_cones_width_equals_its_distance_from_the_origin() -> None:
    """p. 179, with the document's own example: "a Cone is 15 feet wide at a point along
    its length that is 15 feet from the point of origin".

    Width is the full spread, so the half-width there is 7.5 feet: an offset of 7 is
    inside and 8 is outside. An implementation treating the stated width as a *radius*
    would admit 15, and would still look like a cone.
    """
    cone = Cone(ORIGIN, EAST, 15)
    assert cone.contains(Position(15, 7, 0))
    assert not cone.contains(Position(15, 8, 0))
    assert not cone.contains(Position(15, 15, 0)), "the width is the spread, not the radius"


def test_a_cone_stops_at_its_maximum_length() -> None:
    cone = Cone(ORIGIN, EAST, 15)
    assert cone.contains(Position(15, 0, 0))
    assert not cone.contains(Position(16, 0, 0))


def test_a_cone_does_not_extend_backwards() -> None:
    """It goes "in a direction its creator chooses" — one direction."""
    assert not Cone(ORIGIN, EAST, 15).contains(Position(-5, 0, 0))


def test_a_cone_narrows_towards_its_origin() -> None:
    """The width rule is proportional, so close to the origin the cone is tight."""
    cone = Cone(ORIGIN, EAST, 30)
    assert cone.contains(Position(4, 2, 0))
    assert not cone.contains(Position(4, 3, 0))


# --- Line, Cylinder, Cube -------------------------------------------------------------


def test_a_line_is_bounded_by_its_length_and_its_width() -> None:
    line = Line(ORIGIN, EAST, 30, 5)
    assert line.contains(Position(30, 2, 0))
    assert not line.contains(Position(30, 3, 0)), "half of 5 is 2.5, so 3 is outside"
    assert not line.contains(Position(31, 0, 0))


def test_a_line_keeps_its_width_all_the_way_along() -> None:
    """Unlike a Cone, it does not widen."""
    line = Line(ORIGIN, EAST, 30, 5)
    assert line.contains(Position(5, 2, 0))
    assert line.contains(Position(25, 2, 0))


def test_a_cylinder_is_bounded_by_radius_and_height() -> None:
    cylinder = Cylinder(ORIGIN, 10, 20)
    assert cylinder.contains(Position(10, 0, 20))
    assert not cylinder.contains(Position(11, 0, 0))
    assert not cylinder.contains(Position(0, 0, 21))


def test_a_cylinder_from_its_top_extends_downwards() -> None:
    """p. 180 puts the origin "at the center of the circular top or bottom" — both are
    allowed, so which one it is has to be sayable."""
    down = Cylinder(ORIGIN, 10, 20, upward=False)
    assert down.contains(Position(0, 0, -20))
    assert not down.contains(Position(0, 0, 1))


def test_a_cube_is_bounded_on_every_axis() -> None:
    cube = Cube(ORIGIN, EAST, 10)
    assert cube.contains(Position(5, 5, 5))
    assert not cube.contains(Position(5, 6, 0)), "half of 10 is 5, so 6 is outside"
    assert not cube.contains(Position(11, 0, 0))
    assert not cube.contains(Position(-1, 0, 0))


def test_a_cube_must_be_axis_aligned_and_says_why() -> None:
    """A disclosed narrowing: p. 179 allows any orientation and puts the origin anywhere on
    a face. Refusing the cases it cannot model is better than silently mis-modelling them.
    """
    with pytest.raises(ValueError, match="axis-aligned Cubes only"):
        Cube(ORIGIN, Direction(1, 1, 0), 10)
    with pytest.raises(ValueError, match="positive"):
        Cube(ORIGIN, EAST, 0)


def test_a_direction_points_somewhere() -> None:
    with pytest.raises(ValueError, match="points nowhere"):
        Direction(0, 0, 0)


# --- Which creatures are caught -------------------------------------------------------


def test_creatures_in_reports_those_inside_in_the_order_supplied() -> None:
    caught = creatures_in(
        Sphere(Position(0, 0, 0), 20),
        {"near": Position(5, 0, 0), "far": Position(50, 0, 0), "above": Position(0, 0, 10)},
    )
    assert caught == ("near", "above")


def test_an_area_does_not_reach_through_a_wall() -> None:
    """p. 177: "If all straight lines extending from the point of origin to a location in
    the area of effect are blocked, that location isn't included in the area of effect."

    The gap #91 named, now closed. The creature behind the wall is *inside the sphere* and
    the effect does not reach it — two different questions, and the second is the one that
    decides.
    """
    origin = Position(0, 0, 0)
    wall = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20))
    sphere = Sphere(origin, 40)
    sheltered = Position(30, 0, 0)

    assert sphere.contains(sheltered), "inside the volume"
    assert creatures_in(sphere, {"hiding": sheltered}, [wall]) == ()


def test_the_same_creature_is_caught_with_no_wall_between() -> None:
    """The control. Without the obstruction the answer flips, so the exclusion is the wall
    doing work rather than the radius being wrong."""
    sphere = Sphere(Position(0, 0, 0), 40)
    assert creatures_in(sphere, {"hiding": Position(30, 0, 0)}) == ("hiding",)


def test_a_creature_around_the_end_of_a_wall_is_still_reached() -> None:
    """Blocking is per-line, not per-region: standing on the far side of a wall that does
    not lie between you and the origin shelters nobody."""
    wall = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20))
    sphere = Sphere(Position(0, 0, 0), 60)
    assert creatures_in(sphere, {"exposed": Position(0, 40, 0)}, [wall]) == ("exposed",)


def test_supplying_no_obstructions_means_there_are_none() -> None:
    """Not "ignore them". An encounter that tracks no walls gets unobstructed volume, which
    is right for an open field and wrong for a dungeon — and the engine cannot tell those
    apart, so the caller supplies the walls or accepts the open field.
    """
    sphere = Sphere(Position(0, 0, 0), 40)
    everyone = {"a": Position(30, 0, 0), "b": Position(0, 30, 0)}
    assert set(creatures_in(sphere, everyone)) == {"a", "b"}


def test_no_float_is_produced_by_any_membership_test() -> None:
    """The whole geometry is integer arithmetic; `core.canonical` refuses floats."""
    shapes = (
        Sphere(ORIGIN, 20),
        Emanation(ORIGIN, 10),
        Cylinder(ORIGIN, 10, 20),
        Cone(ORIGIN, EAST, 15),
        Line(ORIGIN, EAST, 30, 5),
        Cube(ORIGIN, EAST, 10),
    )
    for shape in shapes:
        assert isinstance(shape.contains(Position(3, 4, 5)), bool)


def test_the_area_definitions_carry_a_verified_citation() -> None:
    assert AREA_VERIFICATION.state is VerificationState.VERIFIED
    assert AREA_VERIFICATION.reference is not None
    for cited in ("p. 177", "p. 179", "p. 180", "p. 181", "p. 184", "p. 188"):
        assert cited in AREA_VERIFICATION.reference
