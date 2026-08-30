"""Armour Class derived: a chosen base, plus bonuses (#393, 0077).

`Combatant.armour_class` was an `int` a caller supplied, so **nothing could withhold a
contribution to it** — and p. 177's Shield clause needs exactly that. A withheld bonus is not
expressible against a total, because the engine does not know what the total was built from.

> **p. 177.** Your base AC calculation is 10 plus your Dexterity modifier. If a rule gives you
> another base AC calculation, you choose which calculation to use; **you can't use more than
> one**.

> **p. 92.** A creature can wear only one suit of armor at a time and wield only one Shield at
> a time.

**A base is chosen between; a bonus is added on top.** p. 92's table invites the opposite
reading — a Shield's `+2` sits in the same column as Padded Armor's `11 + Dex modifier` — and
getting it wrong is not a rounding error: a character in Plate with a Shield is 20, and an
engine that adds a base to a base makes them 28.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.equipment import (
    UNARMOURED,
    ArmourClassBase,
    Carriage,
    Carried,
    Item,
)
from srd_rules_engine.core.state import Combatant

#: p. 92's Heavy Armor: a flat number, no Dexterity at all.
PLATE = Item(
    id="fixture:plate",
    weight=65,
    is_armour=True,
    armour_class_base=ArmourClassBase(flat=18, adds_dexterity=False),
)
#: p. 92's Medium Armor: "12 + Dex modifier (max 2)".
HIDE = Item(
    id="fixture:hide",
    weight=12,
    is_armour=True,
    armour_class_base=ArmourClassBase(flat=12, dexterity_cap=2),
)
#: p. 92's Light Armor: uncapped.
LEATHER = Item(
    id="fixture:leather", weight=10, is_armour=True, armour_class_base=ArmourClassBase(flat=11)
)
#: p. 92's Shield: `+2`, and a **bonus** rather than a base.
SHIELD = Item(id="fixture:shield", weight=6, is_armour=True, armour_class_bonus=2)


def _combatant(
    *carried: Carried, dex: int = 14, stated: int = 13, trained: bool = True
) -> Combatant:
    """Trained by default, because p. 92's training clause is #367's and not this file's —
    every case below is about the *arithmetic*, and an untrained Shield contributing nothing
    would make half of them pass for the wrong reason."""
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=20,
        max_hit_points=20,
        armour_class=stated,
        abilities={"str": 10, "dex": dex, "con": 10, "int": 10, "wis": 10, "cha": 10},
        proficiency_bonus=2,
        equipment=carried,
        armour_training=frozenset(c.item.id for c in carried) if trained else frozenset(),
    )


def _worn(item: Item) -> Carried:
    return Carried(item=item, carriage=Carriage.WORN)


def _held(item: Item) -> Carried:
    return Carried(item=item, carriage=Carriage.HELD)


# --- The base calculation ------------------------------------------------------------


def test_the_default_base_is_ten_plus_dexterity() -> None:
    """p. 177, and the one base the document states without a table."""
    assert UNARMOURED.value(3) == 13
    assert UNARMOURED.value(-1) == 9


def test_a_capped_base_caps_the_modifier_and_does_not_clamp_it() -> None:
    """p. 92 writes "max 2", which is a maximum. A negative modifier stays negative — clamping
    it into range would turn a penalty into a bonus, which is the direction 0030 clause 1
    keeps away from."""
    hide = ArmourClassBase(flat=12, dexterity_cap=2)

    assert hide.value(3) == 14, "the +3 is capped to +2"
    assert hide.value(1) == 13, "under the cap, the modifier is untouched"
    assert hide.value(-1) == 11, "a penalty is not raised by a cap"


def test_a_base_that_adds_no_dexterity_ignores_it_entirely() -> None:
    """p. 92's Heavy Armor states a number and no modifier, which is different from a cap of
    0 — that would be a cap somebody set."""
    assert ArmourClassBase(flat=16, adds_dexterity=False).value(5) == 16


def test_a_cap_on_a_modifier_that_is_not_added_is_refused() -> None:
    with pytest.raises(ValueError, match="describes nothing"):
        ArmourClassBase(flat=16, adds_dexterity=False, dexterity_cap=2)


# --- The derivation --------------------------------------------------------------------


def test_an_undressed_creature_keeps_its_stated_armour_class() -> None:
    """Every creature in the tree today. A stat block states an AC (p. 254) and this changes
    no existing outcome — the derivation adds a path for a creature that is dressed."""
    assert _combatant(stated=13).effective_armour_class == 13


def test_worn_armour_supplies_the_base() -> None:
    assert _combatant(_worn(PLATE), stated=13).effective_armour_class == 18


def test_described_armour_beats_a_stated_total() -> None:
    """They are the same claim at two levels of detail rather than two competing bases: a
    total is the shorthand a ruleset uses when it has not described the armour.

    **This is the correction the build forced.** 0077 clause 4 read a stat-block AC as
    "another base AC calculation", which is right about its provenance and wrong about its
    shape — a stat block states a *result*, while p. 177's alternatives are *calculations*.
    Treating them as rivals put the stated total beside worn armour and made the armour inert.
    """
    assert _combatant(_worn(PLATE), stated=10).effective_armour_class == 18


def test_a_shield_adds_to_the_base_rather_than_replacing_it() -> None:
    """The case the whole record turns on. Plate is 18 and a Shield is +2, so 20 — and an
    engine that treated the Shield as another base, or added two bases, gives 28."""
    assert _combatant(_worn(PLATE), _held(SHIELD)).effective_armour_class == 20


def test_a_shield_adds_to_a_stated_total_too() -> None:
    """A Shield is not a calculation, so it rides on whichever base won — including the
    shorthand one."""
    assert _combatant(_held(SHIELD), stated=13).effective_armour_class == 15


def test_dexterity_reaches_the_derived_value_through_the_base() -> None:
    lightly = _combatant(_worn(LEATHER), dex=18)  # +4, uncapped
    heavily = _combatant(_worn(HIDE), dex=18)  # +4, capped to +2

    assert lightly.effective_armour_class == 15
    assert heavily.effective_armour_class == 14


# --- p. 92's one-at-a-time ---------------------------------------------------------------


#: A worn item that grants a base and is **not** armour. p. 177's "another base AC
#: calculation" comes from a rule — a class feature in the document — and no such feature
#: ships here; this is the nearest thing the engine can express, and it is what separates
#: p. 92's rule from p. 177's (#394).
BRACERS = Item(
    id="fixture:bracers", weight=1, is_armour=False, armour_class_base=ArmourClassBase(flat=13)
)


def test_two_suits_of_armour_are_refused_by_p92() -> None:
    """p. 92: "A creature can wear only one suit of armor at a time." About what a creature
    **wears**, and it names the suits."""
    with pytest.raises(ValueError, match="2 suits of armour"):
        assert _combatant(_worn(PLATE), _worn(HIDE)).effective_armour_class


def test_two_base_calculations_are_refused_by_p177_and_not_picked_between() -> None:
    """p. 177: "you choose which calculation to use; **you can't use more than one**."

    **Refusing is the safe direction and picking is not.** Taking the highest optimises
    invisibly — an optimised AC looks exactly like a chosen one — and taking the first depends
    on the order a ruleset happened to list the creature's equipment. The document did not
    leave this open; it assigned it, so there is nothing here for the engine to decide.
    """
    with pytest.raises(ValueError, match="base AC calculations"):
        assert _combatant(_worn(PLATE), _worn(BRACERS)).effective_armour_class


def test_p92_and_p177_are_different_rules_and_refuse_for_different_reasons() -> None:
    """They were **one check** until #394, and coincided only while worn armour was the
    engine's single source of a base. One suit of plate and a pair of bracers is one suit and
    two calculations — and the old check called it "wearing 2 suits of armour", which was
    false and cited the rule that was not broken.
    """
    one_suit_two_bases = _combatant(_worn(PLATE), _worn(BRACERS))
    assert len([i for i in (PLATE, BRACERS) if i.is_armour]) == 1, "p. 92 is not violated"
    assert len(one_suit_two_bases.armour_class_bases) == 2, "p. 177 is"

    with pytest.raises(ValueError, match=r"p\. 177") as refusal:
        assert one_suit_two_bases.effective_armour_class
    assert "suits of armour" not in str(refusal.value)


def test_the_selection_is_unreachable_with_anything_to_select_from() -> None:
    """#394's property, asserted as the structural fact it is rather than as a behaviour.

    `effective_armour_class` refuses **before** it reads a base, so by the time one is taken
    there is at most one to take. Picking is therefore impossible rather than avoided — and a
    corruption replacing the selection with `max(...)` is *unobservable*, which is why that
    proof came back green and is recorded rather than counted (0079).
    """
    for count in range(3):
        creature = _combatant(*[_worn(item) for item in (PLATE, BRACERS)][:count])
        if count > 1:
            with pytest.raises(ValueError):
                assert creature.effective_armour_class
        else:
            assert len(creature.armour_class_bases) <= 1
            assert isinstance(creature.effective_armour_class, int)


def test_a_single_non_armour_base_is_used_like_any_other() -> None:
    """One calculation is no choice, so nothing is refused — and the base need not come from
    armour. This is the shape a class feature would arrive in."""
    assert _combatant(_worn(BRACERS), dex=14).effective_armour_class == 15


def test_two_shields_are_refused() -> None:
    """p. 92: "wield only one Shield at a time". The document names nothing else that adds to
    AC by being held, so two held bonuses are two Shields."""
    other = Item(id="fixture:buckler", weight=3, is_armour=True, armour_class_bonus=2)

    with pytest.raises(ValueError, match="one Shield at a time"):
        assert _combatant(_held(SHIELD), _held(other)).effective_armour_class


def test_an_item_that_is_both_a_base_and_a_bonus_is_refused() -> None:
    """p. 177 chooses between bases and adds bonuses on top, so an item that is both is one
    the document does not describe."""
    with pytest.raises(ValueError, match="both a base AC calculation and an AC bonus"):
        Item(id="fixture:odd", armour_class_base=ArmourClassBase(flat=11), armour_class_bonus=2)


def test_an_ac_bonus_does_not_subtract() -> None:
    with pytest.raises(ValueError, match="adds to a base"):
        Item(id="fixture:cursed", armour_class_bonus=-1)


# --- Carriage decides which is which ------------------------------------------------------


def test_armour_contributes_only_while_worn() -> None:
    """p. 104's "any armor you are **wearing**", and the reason 0039 clause 3 made carriage
    one field: armour in a pack protects nobody."""
    stowed = _combatant(Carried(item=PLATE, carriage=Carriage.STOWED), stated=13)

    assert stowed.effective_armour_class == 13
    assert stowed.armour_class_bases == ()


def test_a_shield_contributes_only_while_held() -> None:
    """And this is how a Shield is told from armour without p. 177's *category*, which is
    content 0040 clause 2 declined to ship: a Shield is the thing you hold that adds to AC."""
    stowed = _combatant(Carried(item=SHIELD, carriage=Carriage.STOWED), stated=13)

    assert stowed.effective_armour_class == 13
    assert stowed.armour_class_bonus == 0


# --- What is still owed --------------------------------------------------------------------


def test_an_untrained_shield_adds_nothing() -> None:
    """p. 92: "You gain the Armor Class benefit of a Shield **only if you have training with
    it**" (#367). Built in the same change that retired
    `untrained-shield-still-grants-ac` — the clause was the stand-in for this rule, and it
    waited on #393 giving it a contribution to withhold rather than on effort.
    """
    untrained = _combatant(_held(SHIELD), stated=13, trained=False)
    trained = _combatant(_held(SHIELD), stated=13)

    assert untrained.effective_armour_class == 13
    assert trained.effective_armour_class == 15


def test_two_shields_are_refused_even_when_neither_is_trained() -> None:
    """p. 92's "wield only one Shield at a time" is about **wielding**, so the refusal is
    asked before training is consulted. Filtering first would let an untrained Shield hide a
    second one."""
    other = Item(id="fixture:buckler", weight=3, is_armour=True, armour_class_bonus=2)

    with pytest.raises(ValueError, match="one Shield at a time"):
        assert _combatant(_held(SHIELD), _held(other), trained=False).effective_armour_class
