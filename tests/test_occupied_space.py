"""p. 14's Creature Size and Space, and the two entries that ask about it (#337, 0084).

> A creature belongs to a size category, which determines **the width of the square space**
> the creature occupies on a map... A creature's space is **the area that it effectively
> controls in combat** and the area it needs to fight effectively.

> **Occupied Space** (p. 185): A space is occupied if a creature is in it or if it is
> completely filled by objects.
> **Unoccupied Space** (p. 191): A space is unoccupied if no creatures are in it and it isn't
> completely filled by objects.

Every creature in `core.position` was a point until this. What the extent answers is
**occupancy** — and, deliberately, not distance: p. 14 calls the space a *control* area, and
the document says nothing about measuring between two extents without a grid, which this
project declines as a default.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from srd_rules_engine.core.position import Position, space_contains
from srd_rules_engine.core.size import SPACE_FEET, Size
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _at(cid: str, x: int, size: Size | None = Size.MEDIUM) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        position=Position(x, 0, 0),
        size=size,
    )


# --- p. 14's table, transcribed --------------------------------------------------------------


def test_the_table_is_the_documents() -> None:
    """p. 14 prints six rows. Small and Medium share a space exactly as they share a carrying
    multiplier, which is why this is a table and not a doubling."""
    assert {
        Size.TINY: Fraction(5, 2),
        Size.SMALL: Fraction(5),
        Size.MEDIUM: Fraction(5),
        Size.LARGE: Fraction(10),
        Size.HUGE: Fraction(15),
        Size.GARGANTUAN: Fraction(20),
    } == SPACE_FEET


def test_tiny_keeps_its_half_foot() -> None:
    """The row that decided the type. `Position` is integer feet and every other distance here
    is an integer — an int would lose the half outright and a float would round it somewhere.
    `Fraction` is this repository's existing answer for an exact non-integer quantity."""
    assert Size.TINY.space_feet == Fraction(5, 2)
    assert Size.TINY.space_feet != 2 and Size.TINY.space_feet != 3
    assert Size.TINY.space_feet * 2 == 5, "exact, not 2.5 rounded anywhere"


# --- Extent is real -------------------------------------------------------------------------


def test_a_large_creature_occupies_a_point_its_centre_does_not_touch() -> None:
    """The case that decides whether any of this is more than a field. A Large creature at the
    origin controls 10 feet, so a point four feet away is inside its space and would not be
    inside a Medium creature's."""
    ogre = _at("ogre", 0, Size.LARGE)
    guard = _at("guard", 0, Size.MEDIUM)

    four_away = Position(4, 0, 0)
    assert space_contains(ogre.position, Size.LARGE.space_feet, four_away)  # type: ignore[arg-type]
    assert not space_contains(guard.position, Size.MEDIUM.space_feet, four_away)  # type: ignore[arg-type]


def test_the_space_is_a_square_and_not_a_cube() -> None:
    """p. 14 gives a *width* and a square and says nothing about height, so `z` is not
    bounded. A creature flying directly overhead is not in the space below it, and the
    document does not say what would decide that."""
    here = Position(0, 0, 0)
    overhead = Position(0, 0, 40)

    assert space_contains(here, Size.GARGANTUAN.space_feet, overhead)
    assert not space_contains(here, Size.GARGANTUAN.space_feet, Position(30, 0, 0))


def test_the_boundary_is_inclusive_so_there_is_no_seam() -> None:
    """Two Large creatures ten feet apart share the point between them, and an exclusive
    boundary would leave it in **neither** space — a point falling through the floor of the
    map.

    **Large, not Medium**, and the first version of this got that wrong. A Medium creature's
    half-width is 2½ feet, and `Position` is integer feet — so no point can ever land on a
    Medium boundary and the test passed identically with `<` in place of `<=`. A corruption
    proof caught it. Large's half-width is a whole 5, which is the smallest size whose edge an
    integer position can reach at all.
    """
    left, right = Position(0, 0, 0), Position(10, 0, 0)
    between = Position(5, 0, 0)

    assert space_contains(left, Size.LARGE.space_feet, between)
    assert space_contains(right, Size.LARGE.space_feet, between)


def test_no_integer_point_can_sit_on_a_medium_creatures_edge() -> None:
    """Why the test above uses Large. p. 14 gives Small and Medium a 5-foot space, so their
    half-width is 2½ — and `Position` is integer feet. The boundary is real and unreachable,
    which is a property of the grid this engine does not have rather than of the rule."""
    half = Size.MEDIUM.space_feet / 2
    assert half == Fraction(5, 2)
    assert half.denominator == 2, "not an integer number of feet"


# --- p. 185 and p. 191 -----------------------------------------------------------------------


def test_a_space_with_a_creature_in_it_is_occupied() -> None:
    state = EncounterState.new([_at("pc", 0), _at("boar", 20)])

    assert [c.id for c in state.occupants_of(Position(1, 0, 0))] == ["pc"]
    assert not state.is_unoccupied(Position(1, 0, 0))


def test_a_space_with_nobody_in_it_is_unoccupied() -> None:
    state = EncounterState.new([_at("pc", 0), _at("boar", 20)])

    assert state.occupants_of(Position(10, 0, 0)) == ()
    assert state.is_unoccupied(Position(10, 0, 0))


def test_a_larger_creature_occupies_where_a_medium_one_would_not() -> None:
    """The same question through the state, so the extent is not merely computable but
    actually consulted."""
    big = EncounterState.new([_at("ogre", 0, Size.LARGE)])
    small = EncounterState.new([_at("guard", 0, Size.MEDIUM)])
    four_away = Position(4, 0, 0)

    assert [c.id for c in big.occupants_of(four_away)] == ["ogre"]
    assert small.is_unoccupied(four_away)


def test_a_creature_whose_size_nobody_stated_occupies_nothing() -> None:
    """0051: an unstated size is **unknown**, not Medium. Inventing a space for it would put a
    creature somewhere the ruleset never said it was."""
    state = EncounterState.new([_at("mystery", 0, None)])

    assert state.occupants_of(Position(0, 0, 0)) == ()
    assert state.is_unoccupied(Position(0, 0, 0)), "unknown, so not asserted to be anywhere"


def test_a_creature_with_no_position_occupies_nothing() -> None:
    """An encounter that tracks no positions cannot answer the question, and says so by
    answering nothing rather than by guessing."""
    nowhere = Combatant(
        id="pc",
        name="Pc",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        size=Size.MEDIUM,
    )
    state = EncounterState.new([nowhere])

    assert state.occupants_of(Position(0, 0, 0)) == ()


def test_two_creatures_can_both_occupy_one_point() -> None:
    """p. 185 asks whether *a* creature is in a space, not how many. Overlap is a state p. 14
    contemplates — it says what happens if you "somehow end a turn in a space with another
    creature" — so reporting both is the reading, and refusing to represent it would make
    that rule unaskable."""
    state = EncounterState.new([_at("pc", 0), _at("boar", 2)])

    assert {c.id for c in state.occupants_of(Position(1, 0, 0))} == {"pc", "boar"}


def test_the_object_half_of_p185_is_not_asked() -> None:
    """p. 185's second clause — "completely filled by objects" — needs an object that fills a
    space, and this engine's objects are equipment a creature carries. `Obstruction` is a
    barrier rather than an occupant: it gives Total Cover and stops a line of effect, which
    are different questions from whether a creature may stand there.

    So this answers `True` where p. 191 might say `False`, which is the honest direction for a
    read (R19) — it reports what the engine can see rather than inventing an obstruction."""
    from dataclasses import replace

    from srd_rules_engine.core.obstructions import Obstruction

    walled = replace(
        EncounterState.new([_at("pc", 40)]),
        obstructions=(Obstruction(lo=Position(-5, -5, -5), hi=Position(5, 5, 5)),),
    )

    assert walled.is_unoccupied(Position(0, 0, 0)), "the wall is not an occupant"


# --- What extent deliberately does not change ------------------------------------------------


def test_extent_does_not_move_the_range_bound() -> None:
    """The clause 0084 turns on. p. 14 calls a space "the area that it effectively controls",
    and the document says nothing about measuring between two extents without a grid — which
    this project declines as a default. So a Gargantuan creature is as far away as its point
    is, and reading its edge as nearer would be an inference (R31).

    Written as a pin rather than as an aspiration: if range ever becomes extent-aware, this
    test should be the thing that fails and makes someone say so."""
    from srd_rules_engine.core.position import within

    here, far = Position(0, 0, 0), Position(30, 0, 0)

    assert not within(here, far, 25), "25 feet does not reach a point 30 feet away"
    assert not within(here, far, 25), "and a Gargantuan creature's edge does not change that"

    with pytest.raises(TypeError):
        within(here, far, 25, Size.GARGANTUAN)  # type: ignore[call-arg]
