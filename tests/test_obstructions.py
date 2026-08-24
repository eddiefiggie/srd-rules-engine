"""What blocks a line, and the degree of cover this engine refuses to guess (#91).

Two questions live under "cover" and only one has a method in the SRD. p. 177 gives a
geometric rule for blocking — a straight line from the point of origin — and that is
computed. p. 15 gives the *degrees* by what fraction of a target is covered, and supplies no
way to measure a fraction, so this engine decides Total and never Half or Three-Quarters.

The tests below assert both halves: that blocking works, and that the guess is not made.
"""

from __future__ import annotations

from srd_rules_engine.core.obstructions import (
    COVER_VERIFICATION,
    Cover,
    Obstruction,
    line_is_blocked,
    most_protective,
    total_cover,
)
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import VerificationMethod, VerificationState

WALL = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20))
HERE = Position(0, 0, 0)


# --- Blocking -------------------------------------------------------------------------


def test_a_wall_between_two_points_blocks_the_line() -> None:
    assert line_is_blocked(HERE, Position(30, 0, 0), [WALL])


def test_a_line_that_misses_the_wall_is_not_blocked() -> None:
    assert not line_is_blocked(HERE, Position(0, 30, 0), [WALL])


def test_a_line_over_the_top_of_a_wall_is_not_blocked() -> None:
    """The wall stops at 20 feet, and elevation is why 0014 chose three axes: a flat model
    would call this blocked and a flying creature would have nowhere to go."""
    assert not line_is_blocked(Position(0, 0, 30), Position(30, 0, 30), [WALL])


def test_a_line_short_of_the_wall_is_not_blocked() -> None:
    """The segment ends before reaching it — an infinite ray would be blocked and a segment
    is not, which is the difference between "in that direction" and "between them"."""
    assert not line_is_blocked(HERE, Position(5, 0, 0), [WALL])


def test_a_creature_inside_an_obstruction_is_not_blocked_from_itself() -> None:
    """Standing in the rubble does not shelter you from it. Without this, an endpoint inside
    a box would make every line to it blocked, which is the wrong answer twice over."""
    inside = Position(11, 0, 10)
    assert not line_is_blocked(HERE, inside, [WALL])


def test_no_obstructions_block_nothing() -> None:
    assert not line_is_blocked(HERE, Position(30, 0, 0), [])


def test_corners_may_be_given_in_any_order() -> None:
    """A caller describing a wall should not have to sort its corners first."""
    reversed_corners = Obstruction(lo=Position(12, 20, 20), hi=Position(10, -20, 0))
    assert reversed_corners.lo == Position(10, -20, 0)
    assert line_is_blocked(HERE, Position(30, 0, 0), [reversed_corners])


def test_any_one_obstruction_is_enough() -> None:
    far = Obstruction(lo=Position(20, -5, 0), hi=Position(21, 5, 10))
    assert line_is_blocked(HERE, Position(30, 0, 0), [far])
    assert line_is_blocked(HERE, Position(30, 0, 0), [WALL, far])


# --- Degrees --------------------------------------------------------------------------


def test_a_blocked_line_is_total_cover_and_cannot_be_targeted() -> None:
    """p. 15: Total Cover is "an object that covers the whole target"; p. 179: it "can't be
    targeted directly"."""
    cover = total_cover(HERE, Position(30, 0, 0), [WALL])
    assert cover is Cover.TOTAL
    assert not cover.can_be_targeted
    assert cover.bonus == 0, "Total is a prohibition, not a bonus on a roll nobody makes"


def test_an_unblocked_line_is_no_cover() -> None:
    assert total_cover(HERE, Position(0, 30, 0), [WALL]) is Cover.NONE


def test_the_engine_never_returns_half_or_three_quarters() -> None:
    """The refusal that matters. p. 15 defines those degrees by what fraction of a target is
    covered and gives no method for measuring a fraction — so any answer here would be a
    house rule wearing a citation.

    The degrees exist with their benefits so a caller who has determined one can apply it.
    """
    for target in (Position(30, 0, 0), Position(0, 30, 0), Position(11, 0, 10)):
        assert total_cover(HERE, target, [WALL]) in (Cover.TOTAL, Cover.NONE)


def test_the_benefits_are_the_documents() -> None:
    """p. 15: +2 for Half, +5 for Three-Quarters."""
    assert Cover.HALF.bonus == 2
    assert Cover.THREE_QUARTERS.bonus == 5
    assert Cover.NONE.bonus == 0
    assert Cover.HALF.can_be_targeted and Cover.THREE_QUARTERS.can_be_targeted


def test_only_the_most_protective_degree_applies() -> None:
    """p. 15's own example: behind a creature giving Half and a tree giving Three-Quarters,
    the target has Three-Quarters. Adding them would give +7, a number the rules never
    produce."""
    best = most_protective([Cover.HALF, Cover.THREE_QUARTERS])
    assert best is Cover.THREE_QUARTERS
    assert best.bonus == 5


def test_the_most_protective_of_nothing_is_no_cover() -> None:
    assert most_protective([]) is Cover.NONE


def test_total_beats_everything() -> None:
    assert most_protective([Cover.THREE_QUARTERS, Cover.TOTAL, Cover.HALF]) is Cover.TOTAL


# --- Provenance -----------------------------------------------------------------------


def test_the_cover_rules_carry_a_verified_citation() -> None:
    assert COVER_VERIFICATION.state is VerificationState.VERIFIED
    assert COVER_VERIFICATION.method is VerificationMethod.ASSERTED
    assert COVER_VERIFICATION.reference is not None
    for cited in ("p. 177", "p. 179", "p. 15"):
        assert cited in COVER_VERIFICATION.reference


def test_the_module_discloses_what_the_document_does_not_supply() -> None:
    """The measurement of a coverage fraction is project territory, not the document's, and
    a docstring saying so is the kind of sentence that disappears when somebody tidies."""
    from srd_rules_engine.core import obstructions

    assert obstructions.__doc__ is not None
    assert "supplies no method for measuring what" in obstructions.__doc__
    assert "axis-aligned boxes" in obstructions.__doc__
