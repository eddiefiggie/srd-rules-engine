"""Staying in the air, and the two different ways of leaving it (p. 182, p. 188).

p. 182's Flying entry names three triggers and one exception: "While flying, you fall if
you have the Incapacitated or Prone condition or your Fly Speed is reduced to 0. You can
stay aloft in those circumstances if you can hover."

The interesting part is that **two of those triggers arrive by different routes**, and an
engine can implement one and look correct:

* Incapacitated drops a creature whose Fly Speed is untouched. A Stunned flyer still has
  its 60 feet and still falls.
* A Fly Speed "reduced to 0" is almost never reduced directly. It goes to 0 because
  *Speed* went to 0 and p. 188 carried the change across — "if your Speed is reduced to 0
  and you have a Climb Speed, your Climb Speed is also reduced to 0". A Grappled flyer
  falls, and nothing in Grappled's own text (p. 182) mentions flight.

An engine that applied conditions to the walking Speed alone — which this one did until
now — keeps the Grappled flyer aloft at 60 feet of flight, and every test about Grappled
and every test about flying still passes.
"""

from __future__ import annotations

from typing import Final

import pytest

from srd_rules_engine.core import Combatant, EncounterState
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.position import MovementMode, Position, Speeds

#: A Speed of 30 and a Fly Speed of 60 — deliberately unequal, so that an implementation
#: subtracting one from the other is visible rather than accidentally right.
AIRBORNE: Final = Speeds(walk=30, fly=60)


def flyer(
    *,
    speeds: Speeds = AIRBORNE,
    held: frozenset[Condition] = frozenset(),
    exhaustion: tuple[str, ...] = (),
) -> Combatant:
    return Combatant(
        id="roc",
        name="Roc",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 14, "dex": 12},
        proficiency_bonus=2,
        position=Position(0, 0, 60),
        speeds=speeds,
        conditions=Conditions(held=held, exhaustion_levels=exhaustion),
    )


# --- p. 182's three triggers -------------------------------------------------------------


def test_an_untroubled_flyer_stays_up() -> None:
    assert not flyer().falls_if_flying


def test_the_incapacitated_condition_drops_it() -> None:
    assert flyer(held=frozenset({Condition.INCAPACITATED})).falls_if_flying


def test_a_stunned_flyer_falls_with_its_fly_speed_intact() -> None:
    """The trigger that a speed-based implementation misses entirely.

    Stunned (p. 189) does not zero Speed; it gives the Incapacitated condition, which
    p. 182 lists as its own trigger for exactly this reason.
    """
    stunned = flyer(held=frozenset({Condition.STUNNED}))

    assert stunned.effective_speeds.fly == 60, "Stunned takes nothing off a Fly Speed"
    assert stunned.falls_if_flying


def test_the_prone_condition_drops_it() -> None:
    assert flyer(held=frozenset({Condition.PRONE})).falls_if_flying


def test_a_fly_speed_of_zero_drops_it() -> None:
    assert flyer(speeds=Speeds(walk=30, fly=0)).falls_if_flying


def test_a_grappled_flyer_falls_because_page_188_carries_the_zero_across() -> None:
    """Grappled (p. 182) says "Your Speed is 0 and can't increase" and says nothing about
    flight. p. 188 is what connects them, and without it this creature keeps 60 feet."""
    grappled = flyer(held=frozenset({Condition.GRAPPLED}))

    assert grappled.effective_speeds.fly == 0
    assert grappled.falls_if_flying


def test_a_creature_with_no_fly_speed_was_never_up() -> None:
    """p. 182 grants staying aloft to a creature that *has* a Fly Speed. There is no
    reading under which one without it stays up, so this is not a tiebreak."""
    assert flyer(speeds=Speeds(walk=30)).falls_if_flying


# --- p. 183's one exception, which covers all three ---------------------------------------


@pytest.mark.parametrize(
    "held",
    [frozenset({Condition.INCAPACITATED}), frozenset({Condition.PRONE}), frozenset()],
)
def test_hovering_answers_every_circumstance(held: frozenset[Condition]) -> None:
    """ "You can stay aloft in **those circumstances**" — plural, all three. An exception
    written against the Fly-Speed-of-0 trigger alone would drop a hovering Prone flyer."""
    assert not flyer(speeds=Speeds(walk=30, fly=60, hover=True), held=held).falls_if_flying


def test_hovering_survives_a_zeroed_fly_speed() -> None:
    assert not flyer(
        speeds=Speeds(walk=30, fly=60, hover=True), held=frozenset({Condition.GRAPPLED})
    ).falls_if_flying


def test_hovering_does_not_grant_flight_to_a_creature_without_it() -> None:
    """Hover is p. 183's modifier on flying, not a way to fly. A creature with no Fly
    Speed and `hover` set has nothing to hover on."""
    assert flyer(speeds=Speeds(walk=30, hover=True)).falls_if_flying


# --- p. 188: a change to Speed reaches every speed ----------------------------------------


def test_a_condition_that_zeroes_speed_zeroes_them_all() -> None:
    """p. 188's worked example, generalised as its own sentence generalises it: "any
    special speed you have"."""
    speeds = Conditions(held=frozenset({Condition.RESTRAINED})).speeds_after(
        Speeds(walk=30, climb=20, fly=60, swim=15, burrow=10)
    )

    assert (speeds.walk, speeds.climb, speeds.fly, speeds.swim, speeds.burrow) == (0, 0, 0, 0, 0)


def test_zeroing_is_not_a_subtraction_of_the_walking_speed() -> None:
    """The bug the obvious implementation has. Subtracting Speed from each special speed
    reproduces p. 188's example whenever the numbers happen to match, and leaves a Fly
    Speed of 60 at 30 feet when they do not — a Grappled creature flying away at half
    speed."""
    speeds = Conditions(held=frozenset({Condition.GRAPPLED})).speeds_after(Speeds(walk=30, fly=60))

    assert speeds.fly == 0


def test_a_speed_the_creature_lacks_stays_absent() -> None:
    """`None` is not 0, and p. 182 turns on the difference: a Fly Speed of 0 belongs to a
    creature that can fly and currently cannot, which is what Hover rescues."""
    speeds = Conditions(held=frozenset({Condition.GRAPPLED})).speeds_after(Speeds(walk=30))

    assert speeds.fly is None
    assert speeds.climb is None


def test_exhaustion_takes_its_five_feet_from_every_speed() -> None:
    """p. 181 denominates its reduction in feet, which is what p. 188's "an equal amount"
    transfers cleanly. Two levels is 10 feet off each."""
    speeds = Conditions(exhaustion_levels=("a", "b")).speeds_after(
        Speeds(walk=30, climb=20, fly=60)
    )

    assert (speeds.walk, speeds.climb, speeds.fly) == (20, 10, 50)


def test_no_speed_goes_negative() -> None:
    speeds = Conditions(exhaustion_levels=("a", "b", "c")).speeds_after(Speeds(walk=30, swim=10))

    assert speeds.swim == 0


def test_an_unexhausted_unconditioned_creature_keeps_what_it_had() -> None:
    original = Speeds(walk=30, climb=20, fly=60, hover=True)
    assert Conditions().speeds_after(original) == original


def test_exhaustion_can_ground_a_flyer() -> None:
    """Six levels kills (p. 181), so this is reachable only below that — a Fly Speed of 20
    at four levels is 0, and p. 182 then drops the creature."""
    grounded = flyer(speeds=Speeds(walk=30, fly=20), exhaustion=("a", "b", "c", "d"))

    assert grounded.effective_speeds.fly == 0
    assert grounded.falls_if_flying


# --- What a Fly Speed and a Burrow Speed are for ------------------------------------------


def encounter(speeds: Speeds) -> EncounterState:
    return EncounterState.new([flyer(speeds=speeds)])


def test_a_creature_without_a_fly_speed_cannot_fly() -> None:
    """0030 clause 1 at a movement question. The SRD prices climbing, swimming and
    crawling for a creature that lacks the speed (pp. 178, 179, 189) and prices flying
    nowhere — so allowing the move would grant movement no rule grants."""
    with pytest.raises(ValueError, match="no fly speed"):
        encounter(Speeds(walk=30)).with_movement("roc", Position(10, 0, 60), mode=MovementMode.FLY)


def test_a_creature_without_a_burrow_speed_cannot_burrow() -> None:
    with pytest.raises(ValueError, match="no burrow speed"):
        encounter(Speeds(walk=30)).with_movement(
            "roc", Position(10, 0, 60), mode=MovementMode.BURROW
        )


def test_the_refusal_says_why_climbing_is_different() -> None:
    """A refusal a caller can act on. "You have no Fly Speed" invites the question of why
    climbing works without a Climb Speed, and the answer is in the document."""
    with pytest.raises(ValueError, match="priced nowhere"):
        encounter(Speeds(walk=30)).with_movement("roc", Position(10, 0, 60), mode=MovementMode.FLY)


def test_climbing_without_a_climb_speed_is_still_allowed() -> None:
    """The other half, and the reason the guard names two modes rather than four."""
    moved = encounter(Speeds(walk=30)).with_movement(
        "roc", Position(10, 0, 60), mode=MovementMode.CLIMB
    )

    assert moved.combatant("roc").movement_used == 20, "10 feet at 1 extra foot each"


def test_a_flyer_flies() -> None:
    moved = encounter(Speeds(walk=30, fly=60)).with_movement(
        "roc", Position(10, 0, 60), mode=MovementMode.FLY
    )

    assert moved.combatant("roc").position == Position(10, 0, 60)
    assert moved.combatant("roc").movement_used == 10, "flying costs no extra"


def test_a_grappled_creature_cannot_fly_away() -> None:
    """The zeroed Fly Speed reaches `with_movement` too, and it arrives as the ordinary
    out-of-movement refusal rather than as a special case."""
    state = EncounterState.new(
        [flyer(speeds=Speeds(walk=30, fly=60), held=frozenset({Condition.GRAPPLED}))]
    )

    with pytest.raises(ValueError, match="feet of fly movement left"):
        state.with_movement("roc", Position(10, 0, 60), mode=MovementMode.FLY)
