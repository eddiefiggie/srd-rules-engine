"""p. 182's *Movable*: the grappler drags or carries, and pays a foot for the privilege (#340).

> **Movable.** The grappler can drag or carry you when it moves, but every foot of movement
> costs it 1 extra foot unless you are Tiny or two or more sizes smaller than it.

The clause was disclosed and unenforced from #335 until
[0066](../docs/decisions/0066-a-move-that-brings-someone-with-it.md), for two reasons:
movement moved the mover, and the exemption is a size comparison the engine could not make.
Both are gone, and the disclosure came off in the change that built the rule.

**Three readings this file pins**, because none of them is written out on the page:

* The passenger is translated by the **same displacement** as the grappler, which is the only
  answer that preserves the distance between them rather than inventing one.
* The extra foot **adds** to Difficult Terrain's rather than replacing it.
* An **unstated** size establishes no exemption, so the extra applies — the difference between
  a rule and its exception, not a size guessed at.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core import Combatant, Condition, Conditions, EncounterState, Grapple
from srd_rules_engine.core.grappling import ended_by_circumstance
from srd_rules_engine.core.position import MovementMode, Position, Speeds, movement_cost
from srd_rules_engine.core.size import (
    CARRIED_FREELY_CATEGORIES_SMALLER,
    Size,
    carried_without_extra_cost,
)

WALKING = Speeds(walk=30)


def grappled_by(grappler_id: str) -> Conditions:
    return Conditions(
        applied=frozenset({Condition.GRAPPLED}),
        sources={Condition.GRAPPLED: frozenset({grappler_id})},
        grapple=Grapple(escape_dc=13, range_feet=5),
    )


def creature(cid: str, **overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": {"str": 14, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "speeds": WALKING,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def held(
    *, passenger_size: Size | None = Size.MEDIUM, grappler_size: Size | None = Size.LARGE
) -> EncounterState:
    """An ogre at the origin with a captive five feet away, both able to walk."""
    grappler = creature("ogre", size=grappler_size)
    passenger = creature(
        "pc",
        position=Position(5, 0, 0),
        conditions=grappled_by("ogre"),
        size=passenger_size,
    )
    return EncounterState.new([grappler, passenger]).with_initiative({"ogre": 20, "pc": 5})


# --- The exemption ---------------------------------------------------------------------


def test_a_tiny_creature_is_carried_free_whatever_the_grappler_is() -> None:
    """p. 182 states Tiny without qualification, so it does not become a comparison."""
    for grappler in (*Size, None):
        assert carried_without_extra_cost(passenger=Size.TINY, grappler=grappler)


def test_two_categories_smaller_is_free_and_one_is_not() -> None:
    assert CARRIED_FREELY_CATEGORIES_SMALLER == 2
    assert carried_without_extra_cost(passenger=Size.SMALL, grappler=Size.LARGE)
    assert not carried_without_extra_cost(passenger=Size.MEDIUM, grappler=Size.LARGE)
    assert not carried_without_extra_cost(passenger=Size.LARGE, grappler=Size.MEDIUM)


def test_an_unstated_passenger_establishes_no_exemption() -> None:
    """The extra foot is what p. 182 says happens; the two escapes are the exception, and a
    fact the ruleset never stated does not make one out."""
    assert not carried_without_extra_cost(passenger=None, grappler=Size.GARGANTUAN)


def test_an_unstated_grappler_matters_only_for_a_passenger_that_is_not_tiny() -> None:
    assert carried_without_extra_cost(passenger=Size.TINY, grappler=None)
    assert not carried_without_extra_cost(passenger=Size.SMALL, grappler=None)


# --- The arithmetic --------------------------------------------------------------------


def cost(**kwargs: object) -> int:
    base: dict[str, object] = {
        "mode": MovementMode.WALK,
        "difficult_terrain": False,
        "speeds": WALKING,
    }
    base.update(kwargs)
    return movement_cost(10, **base)  # type: ignore[arg-type]


def test_each_carried_creature_costs_a_foot_per_foot() -> None:
    assert cost() == 10
    assert cost(carrying=1) == 20
    assert cost(carrying=2) == 30, "two Movable clauses, each charging its own foot"


def test_the_extra_adds_to_difficult_terrain_rather_than_replacing_it() -> None:
    """The reading, and the evidence: Difficult Terrain says it "isn't cumulative" of itself
    and *Movable* says nothing of the kind."""
    assert cost(difficult_terrain=True) == 20
    assert cost(difficult_terrain=True, carrying=1) == 30


def test_it_adds_to_a_climb_too() -> None:
    assert cost(mode=MovementMode.CLIMB, carrying=1) == 30


def test_carrying_a_negative_number_of_creatures_is_refused() -> None:
    with pytest.raises(ValueError, match="no fewer than nobody"):
        cost(carrying=-1)


# --- The move --------------------------------------------------------------------------


def test_the_passenger_is_translated_by_the_same_displacement() -> None:
    """p. 182 says the grappler carries you and does not say where you end up. The same
    displacement is the only answer that keeps the two exactly as far apart as they were."""
    after = held().with_movement("ogre", Position(0, 10, 0), carrying=("pc",))

    assert after.combatant("ogre").position == Position(0, 10, 0)
    assert after.combatant("pc").position == Position(5, 10, 0), "five feet away, still"


def test_the_grappler_pays_the_extra_and_the_passenger_pays_nothing() -> None:
    after = held().with_movement("ogre", Position(0, 10, 0), carrying=("pc",))

    assert after.combatant("ogre").movement_used == 20, "ten feet, at two feet a foot"
    assert after.combatant("pc").movement_used == 0, "it is not the passenger moving"


def test_a_free_passenger_costs_the_grappler_nothing_extra() -> None:
    after = held(passenger_size=Size.TINY).with_movement(
        "ogre", Position(0, 10, 0), carrying=("pc",)
    )
    assert after.combatant("ogre").movement_used == 10
    assert after.combatant("pc").position == Position(5, 10, 0), "carried all the same"


def test_leaving_the_passenger_behind_costs_nothing_and_moves_nobody() -> None:
    """ "The grappler **can** drag or carry you" — so it is a declaration, and declining it is
    an ordinary move."""
    after = held().with_movement("ogre", Position(0, 10, 0))

    assert after.combatant("ogre").movement_used == 10
    assert after.combatant("pc").position == Position(5, 0, 0)


def test_two_passengers_each_charge_their_own_foot() -> None:
    third = creature("kobold", position=Position(0, 5, 0), conditions=grappled_by("ogre"))
    state = EncounterState.new(
        [
            creature("ogre", size=Size.LARGE),
            creature("pc", position=Position(5, 0, 0), conditions=grappled_by("ogre")),
            third,
        ]
    ).with_initiative({"ogre": 20, "pc": 5, "kobold": 1})

    after = state.with_movement("ogre", Position(0, 10, 0), carrying=("pc", "kobold"))
    assert after.combatant("ogre").movement_used == 30
    assert after.combatant("kobold").position == Position(0, 15, 0)


def test_an_unaffordable_carry_is_refused_before_anyone_moves() -> None:
    """Twenty feet at two feet a foot is forty, and a Speed of 30 does not reach it — the
    same refusal an unaffordable ordinary move gets, and it takes the passenger with it."""
    state = held()
    with pytest.raises(ValueError, match="that move costs 40"):
        state.with_movement("ogre", Position(0, 20, 0), carrying=("pc",))


# --- What may not be carried -----------------------------------------------------------


def test_a_creature_this_one_is_not_grappling_is_refused() -> None:
    state = held()
    free = replace(state.combatant("pc"), conditions=Conditions())
    loose = EncounterState.new([state.combatant("ogre"), free]).with_initiative(
        {"ogre": 20, "pc": 5}
    )
    with pytest.raises(ValueError, match="is not grappling"):
        loose.with_movement("ogre", Position(0, 10, 0), carrying=("pc",))


def test_a_creature_grappled_by_somebody_else_is_refused() -> None:
    """The Movable clause belongs to the grapple, not to whoever happens to be moving."""
    state = held()
    other = replace(state.combatant("pc"), conditions=grappled_by("someone-else"))
    wrong = EncounterState.new([state.combatant("ogre"), other]).with_initiative(
        {"ogre": 20, "pc": 5}
    )
    with pytest.raises(ValueError, match="is not grappling"):
        wrong.with_movement("ogre", Position(0, 10, 0), carrying=("pc",))


def test_a_passenger_nobody_placed_is_refused() -> None:
    state = held()
    nowhere = replace(state.combatant("pc"), position=None)
    unplaced = EncounterState.new([state.combatant("ogre"), nowhere]).with_initiative(
        {"ogre": 20, "pc": 5}
    )
    with pytest.raises(ValueError, match="nowhere for"):
        unplaced.with_movement("ogre", Position(0, 10, 0), carrying=("pc",))


# --- What being carried is not ---------------------------------------------------------


def only_frightened() -> Conditions:
    return Conditions(
        applied=frozenset({Condition.FRIGHTENED}),
        sources={Condition.FRIGHTENED: frozenset({"terror"})},
    )


def test_a_frightened_passenger_may_be_carried_toward_what_it_fears() -> None:
    """p. 182 refuses a Frightened creature moving closer **willingly**, and being carried is
    not willing. The refusal is on the mover, and the mover is the grappler."""
    scary = creature("terror", position=Position(0, 40, 0))
    afraid = replace(
        creature("pc", position=Position(5, 0, 0)),
        conditions=Conditions(
            applied=frozenset({Condition.GRAPPLED, Condition.FRIGHTENED}),
            sources={
                Condition.GRAPPLED: frozenset({"ogre"}),
                Condition.FRIGHTENED: frozenset({"terror"}),
            },
            grapple=Grapple(escape_dc=13, range_feet=5),
        ),
    )
    state = EncounterState.new([creature("ogre", size=Size.LARGE), afraid, scary]).with_initiative(
        {"ogre": 20, "pc": 5, "terror": 1}
    )

    # The rule is live: the same creature moving itself toward the terror is refused. Without
    # this the test would pass for a Frightened creature the refusal never reached.
    walkable = replace(state.combatant("pc"), conditions=only_frightened())
    on_its_own = EncounterState.new([walkable, scary]).with_initiative({"pc": 20, "terror": 1})
    with pytest.raises(ValueError, match="Frightened"):
        on_its_own.with_movement("pc", Position(5, 10, 0))

    after = state.with_movement("ogre", Position(0, 10, 0), carrying=("pc",))
    assert after.combatant("pc").position == Position(5, 10, 0)


def test_carrying_keeps_a_ranged_grapple_alive_where_walking_off_would_end_it() -> None:
    """p. 182 ends a grapple when "the distance between the Grappled target and the grappler
    exceeds the grapple's range", and the displacement reading is what keeps that from firing
    on a carry."""
    carried = held().with_movement("ogre", Position(0, 10, 0), carrying=("pc",))
    assert ended_by_circumstance(carried) == ()

    abandoned = held().with_movement("ogre", Position(0, 10, 0))
    assert ended_by_circumstance(abandoned) == ("pc",)
