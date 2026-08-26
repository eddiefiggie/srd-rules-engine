"""Positions in feet, distance, movement cost, reach and weapon range (#17, #20).

Two design decisions are load-bearing here and both are tested rather than described:

* **No floats reach anything.** Range tests compare squared integers, so the boundary is
  exact where a rounded distance would put it in the wrong place.
* **Straight-line measurement is the project's choice, not the document's.** The SRD gives
  distances in feet and never says how to measure between two points, so the tests assert
  what the engine does without claiming the document requires it.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.actions import ActionBudget
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.position import (
    DEFAULT_REACH_FEET,
    MOVEMENT_VERIFICATION,
    MovementMode,
    Position,
    Speeds,
    distance_feet,
    movement_cost,
    squared_distance,
    within,
)
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import Combatant, EncounterState

ORIGIN = Position(0, 0, 0)


def hero(**kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "hero",
        "name": "Hero",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 15,
        "abilities": {"str": 14, "dex": 14},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "position": ORIGIN,
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


# --- Distance, without ever producing a float ----------------------------------------


def test_distance_is_straight_line_and_whole_feet() -> None:
    assert distance_feet(ORIGIN, Position(30, 40, 0)) == 50
    assert distance_feet(ORIGIN, Position(5, 0, 0)) == 5


def test_elevation_counts() -> None:
    """The reason for three axes: a creature 15 feet up is 15 feet away, not adjacent."""
    assert distance_feet(ORIGIN, Position(0, 0, 15)) == 15
    assert not within(ORIGIN, Position(0, 0, 15), DEFAULT_REACH_FEET)


def test_a_range_test_is_exact_where_a_rounded_distance_is_not() -> None:
    """(5, 3) is about 5.83 feet from the origin, so it is **not** within 5 — but a
    distance rounded down to whole feet reports 5 and would call it reachable.

    This is why `within` compares squares and never consults `distance_feet`. The error
    would appear only at the boundary, which is exactly where reach and range matter.
    """
    edge = Position(5, 3, 0)
    assert distance_feet(ORIGIN, edge) == 5
    assert not within(ORIGIN, edge, 5)
    assert squared_distance(ORIGIN, edge) == 34 > 25


def test_no_float_is_produced_anywhere() -> None:
    """`core.canonical` refuses floats in the ledger and names distances as integers."""
    for value in (
        squared_distance(ORIGIN, Position(7, 11, 13)),
        distance_feet(ORIGIN, Position(7, 11, 13)),
        movement_cost(15, mode=MovementMode.WALK, difficult_terrain=True, speeds=Speeds()),
    ):
        assert isinstance(value, int) and not isinstance(value, bool)


def test_a_negative_range_is_refused() -> None:
    with pytest.raises(ValueError, match="not negative"):
        within(ORIGIN, ORIGIN, -1)


# --- Movement cost --------------------------------------------------------------------


def test_difficult_terrain_costs_one_extra_foot_per_foot() -> None:
    """p. 181, with the document's own example: "moving 5 feet through Difficult Terrain
    costs 10 feet of movement"."""
    plain = Speeds(walk=30)
    assert movement_cost(5, mode=MovementMode.WALK, difficult_terrain=True, speeds=plain) == 10
    assert movement_cost(5, mode=MovementMode.WALK, difficult_terrain=False, speeds=plain) == 5


def test_climbing_swimming_and_crawling_each_cost_one_extra_foot() -> None:
    """pp. 178, 179, 189 — the same sentence three times."""
    plain = Speeds(walk=30)
    for mode in (MovementMode.CLIMB, MovementMode.SWIM, MovementMode.CRAWL):
        assert movement_cost(10, mode=mode, difficult_terrain=False, speeds=plain) == 20


def test_a_matching_special_speed_removes_the_extra_cost() -> None:
    """ "You ignore this extra cost if you have a Climb Speed and use it to climb."""
    climber = Speeds(walk=30, climb=20)
    assert movement_cost(10, mode=MovementMode.CLIMB, difficult_terrain=False, speeds=climber) == 10
    # ...but only for the matching mode. A Climb Speed does not help you swim.
    assert movement_cost(10, mode=MovementMode.SWIM, difficult_terrain=False, speeds=climber) == 20


def test_crawling_has_no_special_speed_to_escape_with() -> None:
    """Crawling's rule carries no "you ignore this" clause, and no Crawl Speed exists."""
    fast = Speeds(walk=30, climb=30, swim=30, fly=30, burrow=30)
    assert movement_cost(10, mode=MovementMode.CRAWL, difficult_terrain=False, speeds=fast) == 20


def test_climbing_through_difficult_terrain_costs_three_feet_per_foot() -> None:
    """The reading this engine takes, and it is a reading: the parenthetical "2 extra feet
    in Difficult Terrain" **replaces** the extra rather than adding to Difficult Terrain's
    own, so the total is 3 per foot rather than 4.

    Three is the arithmetic the two rules agree on when read together — 1 base, 1 for the
    terrain, 1 for the climb. The document does not settle it outright, which is why this
    test says which reading was taken instead of asserting it as fact.
    """
    plain = Speeds(walk=30)
    assert movement_cost(10, mode=MovementMode.CLIMB, difficult_terrain=True, speeds=plain) == 30
    assert movement_cost(10, mode=MovementMode.CLIMB, difficult_terrain=True, speeds=plain) != 40


def test_negative_movement_is_refused() -> None:
    with pytest.raises(ValueError, match="not negative"):
        movement_cost(-1, mode=MovementMode.WALK, difficult_terrain=False, speeds=Speeds())


# --- Movement through the state ------------------------------------------------------


def test_moving_spends_movement_and_the_engine_charges_it() -> None:
    state = EncounterState.new([hero(speeds=Speeds(walk=30))])
    moved = state.with_movement("hero", Position(20, 0, 0))

    assert moved.combatant("hero").position == Position(20, 0, 0)
    assert moved.combatant("hero").movement_used == 20
    assert moved.combatant("hero").movement_remaining == 10


def test_difficult_terrain_is_charged_on_the_way() -> None:
    state = EncounterState.new([hero(speeds=Speeds(walk=30))])
    moved = state.with_movement("hero", Position(10, 0, 0), difficult_terrain=True)
    assert moved.combatant("hero").movement_used == 20


def test_a_move_beyond_the_remaining_speed_is_refused() -> None:
    """Not a slower move — one the rules do not allow. The read surface is what a caller
    consults before proposing it."""
    state = EncounterState.new([hero(speeds=Speeds(walk=30))])
    with pytest.raises(ValueError, match="feet of walk movement left"):
        state.with_movement("hero", Position(40, 0, 0))


def test_movement_can_be_broken_up(  # p. 14, "Breaking Up Your Move"
) -> None:
    """ "You can break up your move, using some of its movement before and after any action."

    Which falls out of movement being spent rather than declared once — two moves of 10
    feet cost exactly what one move of 20 would.
    """
    state = EncounterState.new([hero(speeds=Speeds(walk=30))])
    twice = state.with_movement("hero", Position(10, 0, 0)).with_movement(
        "hero", Position(20, 0, 0)
    )
    assert twice.combatant("hero").movement_used == 20
    assert twice.combatant("hero").movement_remaining == 10


def test_a_creature_without_a_position_cannot_move() -> None:
    """An encounter that tracks no positions says so rather than assuming an origin."""
    state = EncounterState.new([hero(position=None)])
    with pytest.raises(ValueError, match="no position"):
        state.with_movement("hero", Position(5, 0, 0))


def test_movement_resets_when_the_turn_comes_round_again() -> None:
    """p. 188: Speed is what a creature can cover "on its turn". A counter carried across
    turns would silently shorten every move after the first."""
    other = Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=13,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(50, 0, 0),
    )
    state = EncounterState.new([hero(speeds=Speeds(walk=30)), other]).with_initiative(
        {"hero": 20, "boar": 10}
    )
    spent = state.with_movement("hero", Position(30, 0, 0))
    assert spent.combatant("hero").movement_used == 30

    back_round = spent.advanced_turn().advanced_turn()
    assert back_round.combatant("hero").movement_used == 0
    assert back_round.combatant("hero").movement_remaining == 30


# --- The per-mode allowance (p. 188, #206) --------------------------------------------

#: A Speed of 30 and a Fly Speed of 40 — the document's own numbers on p. 188, and
#: deliberately unequal, so an implementation charging flight against Speed is visible.
WINGED = Speeds(walk=30, fly=40)


def test_each_mode_draws_on_its_own_speed() -> None:
    """p. 188: "If you have more than one speed, choose which one to use when you move."

    Not one pool sized by Speed. A creature with a Fly Speed of 40 has 40 feet of flight
    available on a turn it has spent nothing, whatever its Speed happens to be.
    """
    winged = hero(speeds=WINGED)
    assert winged.movement_remaining_in(MovementMode.WALK) == 30
    assert winged.movement_remaining_in(MovementMode.FLY) == 40


def test_the_spend_is_shared_and_comes_off_whichever_speed_is_asked() -> None:
    """p. 188: "Whenever you switch, subtract the distance already moved from the new
    speed."

    One spend, two allowances. Ten feet of flight leaves 30 of flying and 20 of walking —
    the same ten feet, subtracted from different numbers.
    """
    state = EncounterState.new([hero(speeds=WINGED)])
    flown = state.with_movement("hero", Position(0, 0, 10), mode=MovementMode.FLY)

    moved = flown.combatant("hero")
    assert moved.movement_used == 10
    assert moved.movement_remaining_in(MovementMode.FLY) == 30
    assert moved.movement_remaining_in(MovementMode.WALK) == 20


def test_the_documents_own_worked_example() -> None:
    """p. 188, in full: "if you have a Speed of 30 and a Fly Speed of 40, you could fly 10
    feet, walk 10 feet, and leap into the air to fly 20 feet more."

    Forty feet in total, from a creature whose Speed is 30. This is the sentence #206 was
    filed against: no reading that charges every mode against Speed can express it, and
    the third leg is where it fails — 20 more feet with 20 already spent.
    """
    state = EncounterState.new([hero(speeds=WINGED)])

    state = state.with_movement("hero", Position(0, 0, 10), mode=MovementMode.FLY)
    state = state.with_movement("hero", Position(10, 0, 10))
    state = state.with_movement("hero", Position(10, 0, 30), mode=MovementMode.FLY)

    assert state.combatant("hero").movement_used == 40
    assert state.combatant("hero").position == Position(10, 0, 30)


def test_the_forty_first_foot_of_flight_is_refused() -> None:
    """p. 188: "If the result is 0 or less, you can't use the new speed during the current
    move." The Fly Speed is an allowance, not an exemption."""
    state = EncounterState.new([hero(speeds=WINGED)])
    spent = state.with_movement("hero", Position(0, 0, 40), mode=MovementMode.FLY)

    assert spent.combatant("hero").movement_remaining_in(MovementMode.FLY) == 0
    with pytest.raises(ValueError, match="feet of fly movement left"):
        spent.with_movement("hero", Position(0, 0, 45), mode=MovementMode.FLY)


def test_walking_still_charges_the_walking_speed_when_flight_is_the_larger() -> None:
    """The other direction, which a naive per-mode fix gets wrong by taking the maximum:
    30 feet of Speed is still 30 feet of walking for a creature that can fly 40."""
    state = EncounterState.new([hero(speeds=WINGED)])
    with pytest.raises(ValueError, match="feet of walk movement left"):
        state.with_movement("hero", Position(35, 0, 0))


def test_climbing_without_a_climb_speed_draws_on_speed() -> None:
    """p. 178 prices climbing for a creature that lacks the speed — it is an ordinary move
    that costs extra, so its allowance is the Speed. Only flying and burrowing have no
    such fallback."""
    plain = hero(speeds=Speeds(walk=30))
    assert plain.movement_remaining_in(MovementMode.CLIMB) == 30
    assert plain.movement_remaining_in(MovementMode.CRAWL) == 30


def test_a_mode_the_creature_cannot_use_answers_none_rather_than_zero() -> None:
    """pp. 178 and 182 grant flying and burrowing only through the speed itself, so "no
    flight" is a different fact from "no flight left". A 0 would say the creature had run
    out of something it never had."""
    plain = hero(speeds=Speeds(walk=30))
    assert plain.movement_remaining_in(MovementMode.FLY) is None
    assert plain.movement_remaining_in(MovementMode.BURROW) is None


def test_a_condition_that_zeroes_speed_zeroes_the_flying_allowance_too() -> None:
    """p. 188 carries the change across, so the per-mode allowance reads the *effective*
    speeds. A Grappled creature has no flight left, not 40 feet of it."""
    grappled = hero(speeds=WINGED, conditions=Conditions(held=frozenset({Condition.GRAPPLED})))
    assert grappled.movement_remaining_in(MovementMode.FLY) == 0
    assert grappled.movement_remaining_in(MovementMode.WALK) == 0


def test_dash_grants_feet_that_are_spendable_in_any_mode() -> None:
    """p. 180: "you gain extra movement for the current turn", and "if you have a special
    speed ... you can use that speed instead of your Speed when you take this action."

    The pool is sized once, at the Dash. What it grants is feet, so a creature that Dashed
    on its Speed of 30 still adds those 30 feet to its 40 of flight.
    """
    dashing = hero(speeds=WINGED, actions=ActionBudget().dashed(30))
    assert dashing.movement_remaining_in(MovementMode.WALK) == 60
    assert dashing.movement_remaining_in(MovementMode.FLY) == 70


# --- Provenance ----------------------------------------------------------------------


def test_a_creature_reaches_five_feet_unless_told_otherwise() -> None:
    """p. 186, and the default is the rule rather than a convenience."""
    assert DEFAULT_REACH_FEET == 5
    assert hero().reach == 5


def test_the_movement_rules_carry_a_verified_citation() -> None:
    assert MOVEMENT_VERIFICATION.state is VerificationState.VERIFIED
    assert MOVEMENT_VERIFICATION.reference is not None
    for cited in ("p. 188", "p. 181", "p. 178", "p. 189", "p. 179", "p. 186"):
        assert cited in MOVEMENT_VERIFICATION.reference


def test_the_measurement_method_is_not_claimed_as_a_citation() -> None:
    """The SRD supplies no method for measuring distance, so the citation must not imply
    one. This asserts the *absence* of a claim, which is the kind of thing that silently
    reappears when somebody tidies a docstring.
    """
    from srd_rules_engine.core import position

    assert position.__doc__ is not None
    assert "states no method for measuring distance" in position.__doc__
    assert "grounded in" in position.__doc__
