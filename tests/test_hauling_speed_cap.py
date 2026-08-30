"""p. 178's Speed cap, and the antecedent that had to arrive first (#336, 0067).

> While dragging, lifting, or pushing weight in excess of the maximum weight you can carry,
> your Speed can be no more than 5 feet.

[0051](../docs/decisions/0051-a-size-is-stated-or-it-is-unknown.md) built the bound and
disclosed the cap as unapplied, for two reasons that each sufficed: the clause fires on
*dragging, lifting or pushing*, which is not the same fact as carrying too much, and p. 12
leaves the whole subsystem to a person — "the GM **might** require you to abide by the rules
for carrying capacity."

`Combatant.hauled_weight` answers both at once. Stating one is the antecedent, and stating one
is also how p. 12's discretion is exercised: a haul nobody stated caps nothing.

**The comparison this file pins hardest is which two numbers it is between.** p. 178 compares
the *hauled* weight against the *Carry* column — not the creature's own gear, and not the
Drag/Lift/Push column, which is the other bound printed in the same table one line away.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core import Combatant, Condition, Conditions, EncounterState, read
from srd_rules_engine.core.equipment import Carriage, Carried, Item
from srd_rules_engine.core.position import SLOW_RULE_ID, SpeedReduction, Speeds
from srd_rules_engine.core.size import HAULING_SPEED_CAP_FEET, Size, carrying_capacity
from srd_rules_engine.core.turn_span import TurnBoundary

#: Strength 15, Medium: Carry is 225 lb and Drag/Lift/Push is 450 lb.
CARRY = carrying_capacity(Size.MEDIUM, 15).carry
DRAG = carrying_capacity(Size.MEDIUM, 15).drag_lift_push


def creature(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 15, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "size": Size.MEDIUM,
        "speeds": Speeds(walk=30),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(actor: Combatant) -> EncounterState:
    return EncounterState.new([actor]).with_initiative({"pc": 10})


# --- The antecedent, and p. 12's discretion ------------------------------------------------


def test_a_haul_nobody_stated_caps_nothing() -> None:
    """p. 12: "the GM **might** require you to abide by the rules for carrying capacity." The
    discretion is exercised by silence, and silence is the default."""
    unstated = creature()
    assert unstated.hauled_weight is None
    assert unstated.over_hauling_capacity is None, "not False — nobody asked the question"
    assert unstated.effective_speeds.walk == 30


def test_a_haul_under_the_carry_bound_caps_nothing_either() -> None:
    light = creature(hauled_weight=CARRY - 1)
    assert light.over_hauling_capacity is False
    assert light.effective_speeds.walk == 30


def test_a_haul_over_the_carry_bound_caps_the_speed_at_five_feet() -> None:
    assert HAULING_SPEED_CAP_FEET == 5
    heavy = creature(hauled_weight=CARRY + 1)
    assert heavy.over_hauling_capacity is True
    assert heavy.speeds.walk == 30, "what it has"
    assert heavy.effective_speeds.walk == 5, "what it can use"


def test_exactly_the_carry_bound_is_not_in_excess_of_it() -> None:
    """ "weight **in excess of** the maximum" — the maximum itself is not in excess of itself,
    and an off-by-one here caps a creature the document does not."""
    at_the_line = creature(hauled_weight=CARRY)
    assert at_the_line.over_hauling_capacity is False
    assert at_the_line.effective_speeds.walk == 30


# --- Which two numbers -----------------------------------------------------------------


def test_the_creatures_own_gear_is_not_added_to_the_haul() -> None:
    """p. 178 compares the weight being dragged, lifted or pushed. Summing the creature's own
    equipment into it would cap a Speed the sentence does not."""
    laden = creature(
        hauled_weight=CARRY - 10,
        equipment=(Carried(Item(id="fixture:pack", weight=50.0), Carriage.STOWED),),
    )
    assert laden.carried_weight == 50.0
    assert laden.over_carrying_capacity is False
    assert laden.over_hauling_capacity is False, "the haul alone, and it is under"
    assert laden.effective_speeds.walk == 30


def test_carrying_too_much_gear_caps_nothing_on_its_own() -> None:
    """The other direction, and the conflation #336 exists to undo: p. 178 attaches no
    consequence at all to a creature's own gear outweighing the Carry column."""
    hoarder = creature(
        equipment=(Carried(Item(id="fixture:hoard", weight=CARRY + 100), Carriage.STOWED),),
    )
    assert hoarder.over_carrying_capacity is True
    assert hoarder.over_hauling_capacity is None
    assert hoarder.effective_speeds.walk == 30


def test_the_bound_is_the_carry_column_and_not_the_drag_column() -> None:
    """The two are printed one line apart in the same table, and only one of them is what
    "the maximum weight you can carry" names."""
    assert DRAG == CARRY * 2
    between = creature(hauled_weight=CARRY + 1)
    assert between.hauled_weight is not None and between.hauled_weight < DRAG
    assert between.over_hauling_capacity is True


# --- The other maximum in the same table -----------------------------------------------


def test_a_haul_above_the_drag_column_is_refused_outright() -> None:
    """ "The table also shows the **maximum** weight you can drag, lift, or push." Above a
    maximum is not a slower haul; it is one the rules do not allow."""
    with pytest.raises(ValueError, match="cannot drag, lift or push"):
        creature(hauled_weight=DRAG + 1)


def test_exactly_the_drag_maximum_is_allowed() -> None:
    at_the_line = creature(hauled_weight=DRAG)
    assert at_the_line.over_hauling_capacity is True
    assert at_the_line.effective_speeds.walk == 5


def test_a_negative_haul_is_refused() -> None:
    with pytest.raises(ValueError, match="a weight in pounds"):
        creature(hauled_weight=-1.0)


def test_an_unsized_creature_has_no_bound_to_exceed_and_is_not_refused() -> None:
    """R31 in the direction 0051 chose: p. 178's table is keyed on a size, and an engine that
    was not told one cannot read a row without choosing it — so there is nothing to compare
    against and nothing to refuse."""
    unsized = creature(size=None, hauled_weight=10_000.0)
    assert unsized.carrying_capacity is None
    assert unsized.over_hauling_capacity is None
    assert unsized.effective_speeds.walk == 30


# --- How the cap composes ----------------------------------------------------------------


def test_it_is_a_ceiling_rather_than_a_reduction() -> None:
    """ "your Speed can be no more than 5 feet" — a creature already slower is not sped up to
    it, which is what a subtraction would have done."""
    slow = creature(speeds=Speeds(walk=5), hauled_weight=CARRY + 1)
    assert slow.effective_speeds.walk == 5

    slower = creature(speeds=Speeds(walk=0), hauled_weight=CARRY + 1)
    assert slower.effective_speeds.walk == 0


def test_it_reaches_the_walking_speed_only() -> None:
    """p. 188 makes "Speed" the walking one — the same reading p. 90's Slow already takes, and
    a cap reaching a Fly or Swim Speed would be a rule this sentence does not state."""
    winged = creature(speeds=Speeds(walk=30, fly=60, swim=20), hauled_weight=CARRY + 1)
    effective = winged.effective_speeds
    assert effective.walk == 5
    assert effective.fly == 60
    assert effective.swim == 20


def test_a_grappled_haulers_speed_is_still_zero() -> None:
    """p. 182's Speed 0 and p. 178's cap of 5 do not fight: the cap is a maximum, and zero is
    under it."""
    held = creature(
        hauled_weight=CARRY + 1,
        conditions=Conditions(applied=frozenset({Condition.GRAPPLED})),
    )
    assert held.effective_speeds.walk == 0


# --- What the read surface says ------------------------------------------------------------


def test_the_surface_reports_the_cap_and_the_capped_speed() -> None:
    """R19 and R30: the number a caller plans against is the capped one, and the fact that it
    was capped is reported beside it rather than left to be inferred from a Speed that
    changed."""
    situation = read(encounter(creature(hauled_weight=CARRY + 1)), "pc").situation
    assert situation is not None
    assert situation.over_hauling_capacity is True
    assert situation.speed == 5
    assert situation.movement_remaining == 5


def test_the_surface_separates_the_two_bounds() -> None:
    hoarder = replace(
        creature(hauled_weight=10.0),
        equipment=(Carried(Item(id="fixture:hoard", weight=CARRY + 100), Carriage.STOWED),),
    )
    situation = read(encounter(hoarder), "pc").situation
    assert situation is not None
    assert situation.over_carrying_capacity is True, "its gear is over the Carry column"
    assert situation.over_hauling_capacity is False, "and the ten pounds it drags is not"
    assert situation.speed == 30


def test_the_surface_no_longer_disagrees_with_itself_about_a_slowed_speed() -> None:
    """A regression the hauling cap surfaced rather than caused (0067).

    `Situation.speed` recomputed `conditions.speed_after(speeds.walk)`, which applies
    conditions and **neither** p. 90's Slow nor p. 178's cap — both of which live on the
    creature. `movement_remaining` already read `effective_speeds`, so the surface published a
    Speed of 30 beside 20 feet of movement for the same creature, from #322 until #336.
    """
    slowed = (
        EncounterState.new([creature()])
        .with_initiative({"pc": 10})
        .with_speed_reduction(
            "pc",
            SpeedReduction(
                rule_id=SLOW_RULE_ID,
                feet=10,
                expires_after_actor_id="pc",
                expires_in_round=2,
                expires_at=TurnBoundary.END,
            ),
        )
    )
    situation = read(slowed, "pc").situation
    assert situation is not None
    assert slowed.combatant("pc").effective_speeds.walk == 20
    assert situation.speed == 20
    assert situation.movement_remaining == 20


def test_a_dash_grants_the_speed_the_creature_has_now() -> None:
    """p. 180: "you gain extra movement equal to your Speed" — the Speed it has, which p. 178
    has capped at five feet."""
    offered = read(encounter(creature(hauled_weight=CARRY + 1)), "pc").actions
    dashes = [a for a in offered if a.key.startswith("dash:")]
    assert dashes, "a hauling creature may still Dash"
    assert all(a.detail["extra_movement"] == 5 for a in dashes)
