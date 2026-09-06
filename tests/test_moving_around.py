"""p. 14's *Moving around Other Creatures* (#451, 0087), built once 0086 put every melee
position against a big creature outside its space.

> During your move, you can pass through the space of an ally, a creature that has the
> Incapacitated condition, a Tiny creature, or a creature that is two sizes larger or smaller
> than you. Another creature's space is Difficult Terrain for you unless that creature is Tiny
> or your ally. You can't willingly end a move in a space occupied by another creature. If you
> somehow end a turn in a space with another creature, you have the Prone condition unless
> you are Tiny or are of a larger size than the other creature.

Three of the four are refusals and a price in `with_movement`; the fourth is an obligation the
turn's end derives and the one adjudication entry point resolves. Every assertion here was
proved by corrupting the behaviour it guards and watching **this** test go red — the module
is new, so its collection error against the base tree proves nothing about any one of them
(`AGENTS.md`, #298).
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    ENGINE_SHAPES,
    MOVING_AROUND_VERIFICATION,
    SHARED_SPACE_RULE_ID,
    Adjudicator,
    Combatant,
    Condition,
    Conditions,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    VerificationState,
    load_ruleset,
    shared_space_resolver,
    shared_space_rule,
)
from srd_rules_engine.core.position import (
    MovementMode,
    Position,
    Speeds,
    feet_along,
    segment_in_space,
)
from srd_rules_engine.core.size import Size
from srd_rules_engine.core.state import PASS_THROUGH_SIZES_APART, SpaceCrossed
from srd_rules_engine.loop import Narrated, TurnEnd, TurnLoop
from srd_rules_engine.memory.store import JsonMemoryStore

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
ORIGIN = Position(0, 0, 0)


def _at(
    cid: str,
    x: int,
    y: int = 0,
    *,
    size: Size | None = Size.MEDIUM,
    side: str | None = None,
    conditions: Conditions | None = None,
    walk: int = 30,
) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        position=Position(x, y, 0),
        size=size,
        side=side,
        speeds=Speeds(walk=walk, fly=30),
        conditions=conditions or Conditions(),
    )


def _incapacitated() -> Conditions:
    return Conditions(applied=frozenset({Condition.INCAPACITATED}))


def _state(*combatants: Combatant) -> EncounterState:
    rolls = {c.id: 20 - i for i, c in enumerate(combatants)}
    return EncounterState.new(list(combatants)).with_initiative(rolls)


def _loop(tmp_path: Path) -> TurnLoop:
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset((shared_space_rule(),)),
            resolvers={SHARED_SPACE_RULE_ID: shared_space_resolver()},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "m.json"),
            ledger=Ledger.open(
                tmp_path / "l.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            seed_source=lambda: 4242,
        )
    )


def _run_end(loop: TurnLoop, state: EncounterState, actor_id: str) -> TurnEnd:
    generator = loop.end_turn(state, actor_id)
    try:
        next(generator)
        while True:
            generator.send(Narrated(text="it goes down"))
    except StopIteration as stop:
        return stop.value  # type: ignore[no-any-return]


# --- The path: a straight move through a square, as an interval -----------------------------


def test_the_stretch_inside_a_space_is_an_interval_along_the_move() -> None:
    """A twenty-foot move along an axis through a Large creature at its midpoint is inside
    that creature's ten-foot square for the middle half: from 5 feet in to 15 feet in."""
    inside = segment_in_space(ORIGIN, Position(20, 0, 0), Position(10, 0, 0), Fraction(10))

    assert inside == (Fraction(1, 4), Fraction(3, 4))


def test_a_move_that_misses_the_square_crosses_nothing() -> None:
    assert segment_in_space(ORIGIN, Position(20, 0, 0), Position(10, 10, 0), Fraction(10)) is None


def test_a_corner_grazed_is_not_a_crossing() -> None:
    """The diagonal from (0, 10) to (10, 0) touches a Large creature at (10, 10) at exactly one
    point — the corner of its square at (5, 5). No foot of the move is inside, so nothing
    was passed through and there is nothing to price."""
    grazed = segment_in_space(
        Position(0, 10, 0), Position(10, 0, 0), Position(10, 10, 0), Fraction(10)
    )

    assert grazed is None


def test_arriving_on_the_boundary_is_not_passing_through_but_is_standing_in() -> None:
    """The two questions p. 14 asks meet at the edge, and they get different answers by
    design. A move that ends exactly on a Large creature's boundary crosses nothing on the
    way — the interval would be a single point — but the boundary is inclusive (0084 clause
    6), so the creature *stands* in that space at the end. `spaces_crossed` says nothing;
    `shares_space_with` says yes; and it is the second that refuses the move."""
    state = _state(_at("pc", 0), _at("ogre", 10, size=Size.LARGE))

    assert segment_in_space(ORIGIN, Position(5, 0, 0), Position(10, 0, 0), Fraction(10)) is None
    assert state.spaces_crossed("pc", Position(5, 0, 0)) == ()
    assert [c.id for c in state.shares_space_with("pc", at=Position(5, 0, 0))] == ["ogre"]
    with pytest.raises(ValueError, match="end that move in a space with Ogre"):
        state.with_movement("pc", Position(5, 0, 0))


def test_a_move_of_no_length_passes_through_nothing() -> None:
    assert segment_in_space(ORIGIN, ORIGIN, ORIGIN, Fraction(15)) is None


def test_a_climb_straight_up_stays_in_the_space_below() -> None:
    """0084 clause 5: a space is a square, not a cube. A creature in a Huge creature's space
    that flies straight up is inside that space for the whole of the climb."""
    assert segment_in_space(ORIGIN, Position(0, 0, 30), ORIGIN, Fraction(15)) == (
        Fraction(0),
        Fraction(1),
    )


def test_the_clip_is_exact_and_the_edge_is_the_one_space_contains_uses() -> None:
    """A Medium creature's half-width is 2½ feet, which no integer position reaches, and the
    interval lands on it exactly: a ten-foot move past a Medium creature at its midpoint is
    inside from 2½ feet in to 7½ feet in. A float would put the edge somewhere nearby."""
    inside = segment_in_space(ORIGIN, Position(10, 0, 0), Position(5, 0, 0), Fraction(5))

    assert inside == (Fraction(1, 4), Fraction(3, 4))


def test_feet_inside_are_merged_before_they_are_floored() -> None:
    """p. 181: Difficult Terrain "isn't cumulative". Two overlapping stretches of a twenty-foot
    move are one stretch of twelve feet, not ten and ten — and two three-foot stretches are
    six, not two floored threes."""
    move = Position(20, 0, 0)

    assert feet_along(ORIGIN, move, (Fraction(1, 4), Fraction(3, 4))) == 10
    assert (
        feet_along(
            ORIGIN, move, (Fraction(1, 4), Fraction(1, 2)), (Fraction(3, 8), Fraction(17, 20))
        )
        == 12
    )
    assert feet_along(ORIGIN, Position(7, 0, 0), (Fraction(0), Fraction(1, 2))) == 3
    assert feet_along(ORIGIN, move) == 0


def test_a_space_the_move_starts_in_is_listed_from_zero_and_not_entered() -> None:
    """Leaving is not passing through. A creature standing in a Large creature's space and
    walking out of it crosses that space from the very start of its move."""
    state = _state(_at("pc", 4), _at("ogre", 0, size=Size.LARGE))

    (crossing,) = state.spaces_crossed("pc", Position(10, 0, 0))
    assert crossing == SpaceCrossed("ogre", Fraction(0), Fraction(1, 6))
    assert not crossing.entered


# --- Sharing a space, read symmetrically ----------------------------------------------------


def test_two_creatures_share_a_space_when_either_point_is_in_the_others() -> None:
    """A Medium creature four feet from a Large one has its point inside the Large one's
    ten-foot square, and the answer is the same whichever of the two is asked."""
    state = _state(_at("pc", 0), _at("ogre", 4, size=Size.LARGE))

    assert [c.id for c in state.shares_space_with("pc")] == ["ogre"]
    assert [c.id for c in state.shares_space_with("ogre")] == ["pc"]


def test_two_medium_creatures_five_feet_apart_do_not_share_a_space() -> None:
    """The pair that decides the reading. Their squares touch at 2½ feet, and a test on the
    squares would put every pair in ordinary melee reach in a space together — Prone at the
    end of every turn. Point-in-space is what 0084 chose, and it keeps them apart."""
    state = _state(_at("pc", 0), _at("guard", 5))

    assert state.shares_space_with("pc") == ()
    assert not state.owes_prone_for_shared_space("pc")


def test_two_large_creatures_eight_feet_apart_do_not_share_a_space() -> None:
    """Not the overlap of the two squares, which would begin at ten feet."""
    state = _state(_at("a", 0, size=Size.LARGE), _at("b", 8, size=Size.LARGE))

    assert state.shares_space_with("a") == ()


def test_an_unsized_creature_shares_only_through_the_other_creatures_space() -> None:
    """0051: an unstated size is no space at all. Two unsized creatures at one point share
    nothing; an unsized creature standing in a Large creature's square does."""
    nobody = _state(_at("a", 0, size=None), _at("b", 0, size=None))
    assert nobody.shares_space_with("a") == ()

    inside = _state(_at("pc", 3, size=None), _at("ogre", 0, size=Size.LARGE))
    assert [c.id for c in inside.shares_space_with("pc")] == ["ogre"]
    assert [c.id for c in inside.shares_space_with("ogre")] == ["pc"]


# --- p. 176's ally: two stated sides ----------------------------------------------------------


def test_allies_are_two_creatures_on_the_same_stated_side_and_nobody_else() -> None:
    state = _state(
        _at("pc", 0, side="party"),
        _at("friend", 10, side="party"),
        _at("stranger", 20),
        _at("foe", 30, side="warband"),
    )

    assert state.are_allies("pc", "friend")
    assert state.are_allies("friend", "pc")
    assert not state.are_allies("pc", "stranger"), "a creature with no side is nobody's ally"
    assert not state.are_allies("pc", "foe")
    assert not state.are_allies("pc", "pc"), "p. 176 defines the term relative to *you*"


def test_two_creatures_with_no_side_are_not_allies_by_default() -> None:
    """The direction 0030 picks: a guessed friendship would grant passage and free movement
    the rules may not, where a withheld one only charges what everyone else pays."""
    state = _state(_at("pc", 0), _at("guard", 10))

    assert not state.are_allies("pc", "guard")


# --- Sentence 1: whose space may be passed through ------------------------------------------


def test_a_creatures_space_may_not_be_passed_through_by_default() -> None:
    """Two Medium creatures, no side, no condition, one size: none of the four permissions."""
    state = _state(_at("pc", 0), _at("guard", 5))

    with pytest.raises(ValueError, match="cannot pass through Guard's space"):
        state.with_movement("pc", Position(10, 0, 0))
    assert not state.may_pass_through("pc", "guard")


def test_an_allys_space_may_be_passed_through() -> None:
    state = _state(_at("pc", 0, side="party"), _at("friend", 5, side="party"))

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").position == Position(10, 0, 0)


def test_an_incapacitated_creatures_space_may_be_passed_through() -> None:
    state = _state(_at("pc", 0), _at("guard", 5, conditions=_incapacitated()))

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").position == Position(10, 0, 0)


def test_a_tiny_creatures_space_may_be_passed_through() -> None:
    state = _state(_at("pc", 0), _at("rat", 5, size=Size.TINY))

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").position == Position(10, 0, 0)


def test_two_sizes_apart_may_pass_and_one_size_apart_may_not() -> None:
    """Medium through Huge is two categories and permitted; Medium through Large is one and
    refused. The same number both ways: a Huge creature may pass over a Medium one."""
    assert PASS_THROUGH_SIZES_APART == 2

    # Sixty feet of Speed, because fifteen of the twenty feet lie in the giant's square and
    # cost double: a thirty-foot creature would be refused for the price, not the passage.
    through_huge = _state(_at("pc", 0, walk=60), _at("giant", 10, size=Size.HUGE))
    assert through_huge.with_movement("pc", Position(20, 0, 0)).combatant(
        "pc"
    ).position == Position(20, 0, 0)

    through_large = _state(_at("pc", 0), _at("ogre", 10, size=Size.LARGE))
    with pytest.raises(ValueError, match="cannot pass through Ogre's space"):
        through_large.with_movement("pc", Position(20, 0, 0))

    over_medium = _state(_at("giant", 0, size=Size.HUGE, walk=60), _at("pc", 10))
    assert over_medium.with_movement("giant", Position(20, 0, 0)).combatant(
        "giant"
    ).position == Position(20, 0, 0)


def test_an_unstated_size_makes_no_size_permission_out() -> None:
    """0051 and 0030: the comparison needs both sizes. A Huge creature may pass over a Medium
    one, and may not pass over one whose size nobody stated — the permission is not refused
    on a guess, it is simply not made out. The other three permissions need no size."""
    unknown = _state(_at("giant", 0, size=Size.HUGE), _at("pc", 10, size=None))
    with pytest.raises(ValueError, match="cannot pass through Pc's space"):
        unknown.with_movement("giant", Position(20, 0, 0))

    unknown_mover = _state(_at("pc", 0, size=None), _at("giant", 10, size=Size.HUGE))
    with pytest.raises(ValueError, match="cannot pass through Giant's space"):
        unknown_mover.with_movement("pc", Position(20, 0, 0))

    still_an_ally = _state(
        _at("pc", 0, size=None, side="party"), _at("giant", 10, size=Size.HUGE, side="party")
    )
    assert still_an_ally.with_movement("pc", Position(20, 0, 0)).combatant(
        "pc"
    ).position == Position(20, 0, 0)


def test_leaving_a_space_needs_no_permission() -> None:
    """A creature pushed into a Large enemy's space walks out of it: the sentence permits
    passing *through*, and a refusal to leave would hold it where it may not stay."""
    state = _state(_at("pc", 4), _at("ogre", 0, size=Size.LARGE))

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").position == Position(10, 0, 0)


# --- Sentence 2: the price ------------------------------------------------------------------


def test_the_stretch_inside_another_creatures_space_costs_double() -> None:
    """Five feet of a ten-foot move lie inside an Incapacitated guard's space, and those five
    cost ten: 5 + 10 = 15 feet of movement for ten feet of ground."""
    state = _state(_at("pc", 0), _at("guard", 5, conditions=_incapacitated()))

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").movement_used == 15


def test_an_allys_space_and_a_tiny_creatures_are_not_difficult_terrain() -> None:
    """The second sentence's exemptions are two, not the first sentence's four."""
    ally = _state(_at("pc", 0, side="party"), _at("friend", 5, side="party"))
    assert ally.with_movement("pc", Position(10, 0, 0)).combatant("pc").movement_used == 10

    tiny = _state(_at("pc", 0), _at("rat", 5, size=Size.TINY))
    assert tiny.with_movement("pc", Position(10, 0, 0)).combatant("pc").movement_used == 10


def test_an_incapacitated_enemy_may_be_crossed_and_costs_double_to_cross() -> None:
    """The case that tells the two exemption lists apart. Incapacitated opens the passage
    and does nothing to the price."""
    state = _state(_at("pc", 0), _at("guard", 5, conditions=_incapacitated()))

    assert state.may_pass_through("pc", "guard")
    assert state.with_movement("pc", Position(10, 0, 0)).combatant("pc").movement_used == 15


def test_two_overlapping_spaces_are_priced_once() -> None:
    """p. 181: "either a space is Difficult Terrain or it isn't". Two Incapacitated guards
    whose spaces overlap along the move make one stretch of six feet, not two of five."""
    state = _state(
        _at("pc", 0),
        _at("first", 5, conditions=_incapacitated()),
        _at("second", 6, conditions=_incapacitated()),
    )

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").movement_used == 4 + 2 * 6


def test_ground_the_caller_calls_difficult_is_priced_once_too() -> None:
    """Difficult ground outside the space and a creature's space inside it are each double,
    and the stretch inside is not doubled twice."""
    state = _state(_at("pc", 0), _at("guard", 5, conditions=_incapacitated()))

    moved = state.with_movement("pc", Position(10, 0, 0), difficult_terrain=True)
    assert moved.combatant("pc").movement_used == 20


def test_leaving_a_space_is_priced_for_the_foot_inside_it() -> None:
    """From four feet inside a Large enemy's square to ten feet out: one foot of the six is
    inside, and it costs two."""
    state = _state(_at("pc", 4), _at("ogre", 0, size=Size.LARGE))

    moved = state.with_movement("pc", Position(10, 0, 0))
    assert moved.combatant("pc").movement_used == 5 + 2


def test_the_price_is_refused_when_it_exceeds_what_is_left() -> None:
    """The engine charges the cost; the caller states only where the creature is going. A
    creature with 20 feet left cannot make a 20-foot move of which 15 lie in a giant's
    fifteen-foot square, because that move costs 5 + 30."""
    pc = replace(_at("pc", 0), movement_used=10)
    state = _state(pc, _at("giant", 10, size=Size.HUGE))

    with pytest.raises(
        ValueError, match="has 20 feet of walk movement left and that move costs 35"
    ):
        state.with_movement("pc", Position(20, 0, 0))


def test_a_passengers_space_travels_with_the_grappler() -> None:
    """p. 182's carried creature is excluded from every one of p. 14's three questions: its
    space moves with the mover, so it is never crossed, never ended in, and never priced. A
    Large grappler with a Medium captive four feet away — inside its own square — moves ten
    feet for twenty, which is p. 182's extra foot and nothing more."""
    captive = replace(
        _at("pc", 4),
        conditions=Conditions(
            applied=frozenset({Condition.GRAPPLED}),
            sources={Condition.GRAPPLED: frozenset({"ogre"})},
        ),
    )
    state = _state(_at("ogre", 0, size=Size.LARGE), captive)

    moved = state.with_movement("ogre", Position(0, 10, 0), carrying=("pc",))
    assert moved.combatant("ogre").movement_used == 20
    assert moved.combatant("pc").position == Position(4, 10, 0)


# --- Sentence 3: where a move may not end ---------------------------------------------------


def test_a_move_may_not_end_in_another_creatures_space() -> None:
    state = _state(_at("pc", 0), _at("guard", 10))

    with pytest.raises(ValueError, match="You can't willingly end a move"):
        state.with_movement("pc", Position(8, 0, 0))


def test_not_even_an_allys() -> None:
    """The third sentence names no exception, where the first names four: an ally's space may
    be crossed and may not be stopped in."""
    state = _state(_at("pc", 0, side="party"), _at("friend", 10, side="party"))

    assert state.with_movement("pc", Position(20, 0, 0)).combatant("pc").position == Position(
        20, 0, 0
    )
    with pytest.raises(ValueError, match="end that move in a space with Friend"):
        state.with_movement("pc", Position(8, 0, 0))


def test_a_big_creature_may_not_end_its_move_over_a_small_one() -> None:
    """Symmetric: a Huge creature whose square would cover a Medium creature's point ends its
    move in a space occupied by another creature, though its own point is in nobody's."""
    state = _state(_at("giant", 0, size=Size.HUGE), _at("pc", 20))

    with pytest.raises(ValueError, match="end that move in a space with Pc"):
        state.with_movement("giant", Position(14, 0, 0))
    assert state.with_movement("giant", Position(12, 0, 0)).combatant("giant").position == Position(
        12, 0, 0
    )


def test_the_band_0086_promised_is_in_reach_and_free_to_stand_in() -> None:
    """0086 clause 8: reach runs 2½ feet past every boundary, so a Medium creature has
    positions in melee reach of a Huge one that are outside its space — 8 to 10 feet from its
    point. A creature may walk to them and end its move there."""
    state = _state(_at("pc", 0), _at("giant", 20, size=Size.HUGE))

    for x in (10, 11, 12):
        moved = state.with_movement("pc", Position(x, 0, 0))
        assert moved.combatant("pc").position == Position(x, 0, 0)
        assert not moved.owes_prone_for_shared_space("pc")


# --- Sentence 4: the Prone, as an obligation the turn's end derives -------------------------


def test_ending_a_turn_in_anothers_space_owes_prone_at_the_turns_end(tmp_path: Path) -> None:
    """A Medium creature standing four feet from a Large one — pushed there, say — owes p. 14's
    Prone when its turn ends, and owes nothing when it starts."""
    state = _state(_at("pc", 0), _at("ogre", 4, size=Size.LARGE))
    loop = _loop(tmp_path)

    owed = loop.end_turn_obligations(state, "pc")
    assert [o.rule_id for o in owed] == [SHARED_SPACE_RULE_ID]
    assert "space with another creature" in owed[0].label
    assert loop.start_turn_obligations(state, "pc") == ()


def test_the_ruling_applies_prone_and_names_the_sentence_that_caused_it(tmp_path: Path) -> None:
    """Through the one door (R1), with no die (0027 clause 6), and the condition carries the
    rule id as its cause (0083)."""
    state = _state(_at("pc", 0), _at("ogre", 4, size=Size.LARGE))

    ended = _run_end(_loop(tmp_path), state, "pc")

    assert len(ended.rulings) == 1
    assert ended.rulings[0].result is None, "p. 14 asks nothing of the dice"
    conditions = ended.state.combatant("pc").conditions
    assert Condition.PRONE in conditions.held
    assert conditions.causes[Condition.PRONE] == frozenset({SHARED_SPACE_RULE_ID})
    assert ended.unresolvable == ()


def test_the_obligation_is_discharged_once_per_turn(tmp_path: Path) -> None:
    state = _state(_at("pc", 0), _at("ogre", 4, size=Size.LARGE))
    loop = _loop(tmp_path)

    ended = _run_end(loop, state, "pc")
    assert loop.end_turn_obligations(ended.state, "pc") == ()


def test_tiny_owes_nothing_and_neither_does_the_larger_creature() -> None:
    """Both exemptions, from both sides of one pair. A Tiny creature in a Medium one's space
    is exempt by size; the Medium creature is larger than the Tiny one and is exempt too."""
    state = _state(_at("rat", 0, size=Size.TINY), _at("pc", 1))

    assert state.shares_space_with("rat") != ()
    assert not state.owes_prone_for_shared_space("rat")
    assert not state.owes_prone_for_shared_space("pc")


def test_the_smaller_creature_owes_and_the_larger_does_not() -> None:
    state = _state(_at("pc", 0), _at("ogre", 4, size=Size.LARGE))

    assert state.owes_prone_for_shared_space("pc")
    assert not state.owes_prone_for_shared_space("ogre")


def test_two_creatures_of_one_size_at_one_point_both_owe() -> None:
    """0084 clause 8: two creatures may occupy one point, and this is the sentence that
    contemplates it. Neither is larger, so neither is exempt."""
    state = _state(_at("pc", 0), _at("guard", 0))

    assert state.owes_prone_for_shared_space("pc")
    assert state.owes_prone_for_shared_space("guard")


def test_an_unstated_size_withholds_the_prone() -> None:
    """0051, 0030: "of a larger size than the other creature" compares two sizes, and a Prone
    applied on a guessed one would be an outcome the rules may not produce. Neither the
    unsized creature nor the sized one it stands with owes anything."""
    state = _state(_at("pc", 3, size=None), _at("ogre", 0, size=Size.LARGE))

    assert state.shares_space_with("pc") != ()
    assert not state.owes_prone_for_shared_space("pc")
    assert not state.owes_prone_for_shared_space("ogre")


def test_a_creature_already_prone_owes_nothing(tmp_path: Path) -> None:
    """p. 179: a condition does not stack with itself, so there is no outcome left to
    produce — and an obligation that stayed owed would be re-derived every turn."""
    down = replace(_at("pc", 0), conditions=Conditions(applied=frozenset({Condition.PRONE})))
    state = _state(down, _at("ogre", 4, size=Size.LARGE))

    assert not state.owes_prone_for_shared_space("pc")
    assert _loop(tmp_path).end_turn_obligations(state, "pc") == ()


def test_the_resolver_refuses_a_creature_that_owes_nothing(tmp_path: Path) -> None:
    """Read off state and never declared: a declaration for a creature standing in nobody's
    space is refused rather than resolved."""
    state = _state(_at("pc", 0), _at("guard", 10))

    with pytest.raises(ValueError, match="never declared"):
        shared_space_resolver()(
            state=state,
            declaration=Declaration(
                actor_id="pc",
                intent=Intent(improvised=True, label="x"),
                rule_id=SHARED_SPACE_RULE_ID,
            ),
            facts={},
        )


def test_a_creature_that_walked_out_owes_nothing(tmp_path: Path) -> None:
    """The sentences compose. A creature pushed into a giant's space that spends its turn
    leaving ends it in nobody's space, and the obligation is not derived."""
    state = _state(_at("pc", 4), _at("ogre", 0, size=Size.LARGE))

    left = state.with_movement("pc", Position(10, 0, 0))
    assert _loop(tmp_path).end_turn_obligations(left, "pc") == ()


# --- The claim and its provenance ------------------------------------------------------------


def test_the_rule_is_verified_against_p14_and_p176() -> None:
    assert MOVING_AROUND_VERIFICATION.state is VerificationState.VERIFIED
    assert "p. 14" in (MOVING_AROUND_VERIFICATION.reference or "")
    assert "Ally p. 176" in (MOVING_AROUND_VERIFICATION.reference or "")


def test_the_shape_is_claimed_against_the_one_sentence_that_rules() -> None:
    assert (
        ENGINE_SHAPES["moving-around-other-creatures"] == "core.moving_around.shared_space_resolver"
    )


def test_a_mode_without_a_speed_is_still_refused_before_any_of_this() -> None:
    """The existing refusals stand in front. A creature with no Fly Speed asking to fly
    through an ally's space is refused for the speed, not priced for the space."""
    walker = replace(_at("pc", 0, side="party"), speeds=Speeds(walk=30))
    state = _state(walker, _at("friend", 5, side="party"))

    with pytest.raises(ValueError, match="has no fly speed"):
        state.with_movement("pc", Position(10, 0, 0), mode=MovementMode.FLY)
