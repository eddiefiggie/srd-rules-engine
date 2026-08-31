"""Hit Point Dice as a resource, and the half of p. 185 that restores them (#407).

**The spend is not here, and that is the point.** p. 183 states the mechanic as "A creature
can spend Hit Dice during a Short Rest to regain Hit Points", and the Short Rest is an
occasion this engine does not have — #406 holds it. So this module tests a resource that can
be counted, spent by a caller, and restored by a Long Rest, while nothing in the engine yet
spends one on a creature's behalf. The `hit-point-dice` shape stays **unclaimed** for exactly
that reason: p. 183's mechanic is the spend, and a shape claimed at half is the overstatement
#371 and #264 each found.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from srd_rules_engine.core.state import Combatant, EncounterState, HitDice


def test_a_die_size_the_document_does_not_state_is_the_callers() -> None:
    """p. 183 defers the size to Character Creation and to stat blocks, so no range is
    asserted — only that a die has faces. Asserting d4-d12 would be the inferred rule value
    R31 forbids, and the SRD states no such range in this entry."""
    for size in (4, 6, 8, 10, 12, 20, 100):
        assert HitDice(size=size, total=1).size == size
    with pytest.raises(ValueError, match="which is not a die"):
        HitDice(size=0, total=1)


def test_spent_dice_cannot_exceed_held_ones() -> None:
    assert HitDice(size=8, total=3, spent=3).remaining == 0
    with pytest.raises(ValueError, match="not a state a creature can be in"):
        HitDice(size=8, total=2, spent=3)


def test_spending_refuses_rather_than_clamping() -> None:
    """0044's reasoning for ammunition, applied to the other countable thing a creature
    carries: a request for more than it holds is a caller error, not a quantity to round
    down. Clamping would let a caller spend five dice, be given three, and record neither."""
    dice = HitDice(size=8, total=3)
    assert dice.spend().remaining == 2
    assert dice.spend(3).remaining == 0
    with pytest.raises(ValueError, match="cannot be spent; 3 of 3 remain"):
        dice.spend(4)
    with pytest.raises(ValueError, match="is not spending one"):
        dice.spend(0)


def test_the_resource_cannot_express_healing_at_all() -> None:
    """R1 and R4 in the negative. p. 187 rolls the die and adds a Constitution modifier,
    which is an outcome; if this object could carry or return hit points there would be a
    second path to one that never touched a Ruling (#406 is where it becomes a Ruling).

    Pinned as the **shape** — the fields are exactly the count, and `spend` hands back the
    same kind of thing it was called on. Written this way after the first attempt was
    vacuous: asserting `hit_points` was unchanged after `replace(creature, hit_dice=...)`
    is true by construction, because `replace` touches nothing else, and it stayed green
    against every corruption of the code it claimed to guard.
    """
    assert [f.name for f in fields(HitDice)] == ["size", "total", "spent"], (
        "a fourth field is how healing would arrive here"
    )
    assert type(HitDice(size=8, total=2).spend()) is HitDice, (
        "a spend that returned anything else is a spend that could return hit points"
    )


def test_a_long_rest_returns_every_spent_die() -> None:
    """p. 185: "You regain all lost Hit Points and all spent Hit Point Dice" — one sentence,
    and the engine had been doing half of it since #185."""
    resting = Combatant(
        id="pc",
        name="Wren",
        hit_points=4,
        max_hit_points=20,
        armour_class=13,
        abilities={"con": 14},
        proficiency_bonus=2,
        is_player_character=True,
        hit_dice=HitDice(size=8, total=5, spent=4),
    )
    rested = EncounterState.new([resting]).with_long_rest("pc").combatant("pc")

    assert rested.hit_points == 20, "the other half of the same sentence"
    assert rested.hit_dice is not None
    assert rested.hit_dice.spent == 0
    assert rested.hit_dice.remaining == 5, "all of them, not half — p. 185 says all"


def test_a_creature_whose_dice_nobody_recorded_is_not_given_any() -> None:
    """`None` is unrecorded, not zero. p. 183 says player characters have Hit Dice and "most
    monsters also have Hit Dice", so inventing some at a Long Rest would be the engine
    deciding a fact about the creature that its ruleset declined to state — 0051's reading of
    Size, and the same refusal `slots` makes one line above."""
    boar = Combatant(
        id="boar",
        name="Boar",
        hit_points=2,
        max_hit_points=11,
        armour_class=11,
        abilities={"con": 12},
        proficiency_bonus=2,
    )
    rested = EncounterState.new([boar]).with_long_rest("boar").combatant("boar")

    assert rested.hit_points == 11
    assert rested.hit_dice is None, "unrecorded stays unrecorded"
