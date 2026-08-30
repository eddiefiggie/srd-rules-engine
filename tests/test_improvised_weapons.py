"""p. 183's Improvised Weapons: a use rather than an object (#264, 0076).

> An improvised weapon is an object wielded as a makeshift weapon, such as broken glass, a
> table leg, or a frying pan. **A Simple or Martial weapon also counts as an improvised
> weapon if it's wielded in a way contrary to its design**; if you use a Ranged weapon to
> make a melee attack or throw a Melee weapon that lacks the Thrown property, the weapon
> counts as an improvised weapon.

That second sentence settles the modelling: improvised-ness cannot be a property of the
object, because the document's own example is an ordinary weapon being used improvisedly. So
it is a property of the **attack** — its own key, its own resolver.

**The damage type is the one rule here the engine may not supply.** p. 183: "1d4 damage of a
type the GM thinks is appropriate for the object." It arrives as ruleset data on the item,
through the channel `Weapon.damage_type` already uses, and an object nobody has ruled on is
offered no attack at all.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from srd_rules_engine.core import Declaration, EncounterState, Intent, Position, legal_actions
from srd_rules_engine.core.adjudicate import DamageDice, Proposal
from srd_rules_engine.core.combat import IMPROVISED_VERIFICATION, improvised_attack_resolver
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import Carriage, Carried, Item, Weapon
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import (
    IMPROVISED_DAMAGE_DICE,
    IMPROVISED_DAMAGE_SIDES,
    IMPROVISED_THROWN_LONG_FEET,
    IMPROVISED_THROWN_NORMAL_FEET,
    improvised_attack_key,
)
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import Combatant

#: A frying pan. p. 183's own example, and the ruleset has said what it deals.
PAN = Item(id="fixture:pan", weight=4, improvised_damage_type=DamageType.BLUDGEONING)
#: Broken glass nobody has ruled on. Offered no attack, because the GM has not spoken.
GLASS = Item(id="fixture:glass", weight=1)
#: A Ranged weapon. p. 183's own example of a real weapon wielded contrary to its design —
#: and the ruleset has said what swinging it does, which is not what firing it does.
BOW = Weapon(
    id="fixture:bow",
    weight=2,
    damage_dice=1,
    damage_sides=8,
    ability="dex",
    melee=False,
    damage_type=DamageType.PIERCING,
    normal_range=80,
    long_range=320,
    improvised_damage_type=DamageType.BLUDGEONING,
)

ABILITIES = {"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10}


def _combatant(cid: str, position: Position, **kwargs: object) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": ABILITIES,
        "proficiency_bonus": 3,
        "position": position,
    }
    base.update(kwargs)
    return Combatant(**base)  # type: ignore[arg-type]


def _holding(*items: Item) -> Combatant:
    return _combatant(
        "brawler",
        Position(0, 0, 0),
        equipment=tuple(Carried(item=i, carriage=Carriage.HELD) for i in items),
    )


def _encounter(actor: Combatant) -> EncounterState:
    state = EncounterState(generation=0, combatants=(actor, _combatant("boar", Position(5, 0, 0))))
    return state.with_initiative({"brawler": 20, "boar": 5})


def _keys(state: EncounterState) -> set[str]:
    return {action.key for action in legal_actions(state, "brawler")}


def _resolve(state: EncounterState, item_id: str) -> Proposal:
    declaration = Declaration(
        actor_id="brawler",
        intent=Intent(action_key=improvised_attack_key(item_id, "boar")),
        rule_id="fixture:improvised",
    )
    facts: Mapping[str, Resolution] = {}
    return improvised_attack_resolver()(state=state, declaration=declaration, facts=facts)


# --- The pages -----------------------------------------------------------------------


def test_p183_is_asserted_against_its_page() -> None:
    assert IMPROVISED_VERIFICATION.state is VerificationState.VERIFIED
    assert "p. 183" in (IMPROVISED_VERIFICATION.reference or "")


# --- A use rather than an object -----------------------------------------------------


def test_a_plain_object_is_offered_as_an_improvised_weapon() -> None:
    assert improvised_attack_key(PAN.id, "boar") in _keys(_encounter(_holding(PAN)))


def test_a_real_weapon_is_offered_improvisedly_too() -> None:
    """p. 183's second sentence, and the reason improvised-ness is not a flag on the item: a
    Ranged weapon used for a melee attack "counts as an improvised weapon". The bow is a
    perfectly ordinary weapon and is offered both ways."""
    keys = _keys(_encounter(_holding(BOW)))

    assert improvised_attack_key(BOW.id, "boar") in keys
    assert any(key.startswith("attack:fixture:bow:") for key in keys), (
        "the bow is still a bow; improvising with it is a use, not a transformation"
    )


def test_an_object_nobody_has_ruled_on_is_offered_nothing() -> None:
    """p. 183 hands the damage type to a person, so an object without one is not offered —
    R18's computable-rather-than-checkable, and a menu that offered it would be a menu that
    lies about what the engine can resolve."""
    assert improvised_attack_key(GLASS.id, "boar") not in _keys(_encounter(_holding(GLASS)))


def test_the_offer_reports_the_dice_the_type_and_the_missing_bonus() -> None:
    offer = next(
        action
        for action in legal_actions(_encounter(_holding(PAN)), "brawler")
        if action.key == improvised_attack_key(PAN.id, "boar")
    )

    assert offer.detail["damage"] == "1d4"
    assert offer.detail["damage_type"] == "bludgeoning"
    assert offer.detail["proficiency_bonus_applies"] is False


# --- What p. 183 states outright ------------------------------------------------------


def test_the_proficiency_bonus_is_not_added() -> None:
    """p. 183: "**Don't add** your Proficiency Bonus to attack rolls with an improvised
    weapon." A prohibition rather than a proficiency the wielder lacks — the fixture's
    Proficiency Bonus is 3, so a path that added it would be visible rather than coincide."""
    proposal = _resolve(_encounter(_holding(PAN)), PAN.id)

    assert proposal.test is not None
    sources = {m.source for m in proposal.test.modifiers}
    assert sources == {"ability:str"}
    assert "proficiency" not in sources


def test_the_damage_is_one_d4_of_the_type_the_ruleset_supplied() -> None:
    proposal = _resolve(_encounter(_holding(PAN)), PAN.id)

    (dice,) = proposal.on_success
    assert isinstance(dice, DamageDice)
    assert (dice.count, dice.sides) == (IMPROVISED_DAMAGE_DICE, IMPROVISED_DAMAGE_SIDES)
    assert dice.damage_type is DamageType.BLUDGEONING
    assert dice.modifier == 3, "Strength 16, and p. 183 removes only the Proficiency Bonus"


def test_a_weapons_own_dice_and_type_do_not_carry_into_the_swing() -> None:
    """The discriminating case for "a use rather than an object". The bow is 1d8 Piercing;
    swung as a club it is 1d4 of the type the GM chose, because p. 183's rules replace the
    weapon's rather than sitting beside them."""
    proposal = _resolve(_encounter(_holding(BOW)), BOW.id)

    (dice,) = proposal.on_success
    assert isinstance(dice, DamageDice)
    assert (dice.count, dice.sides) == (1, 4), "not the bow's 1d8"
    assert dice.damage_type is DamageType.BLUDGEONING, "not the bow's Piercing"


# --- What is refused ------------------------------------------------------------------


def test_the_resolver_refuses_an_object_nobody_has_ruled_on() -> None:
    """0062: the menu is not a promise, so the rule is asked here as well as there."""
    with pytest.raises(ValueError, match="what 'fixture:glass' deals"):
        _resolve(_encounter(_holding(GLASS)), GLASS.id)


def test_the_resolver_refuses_an_object_that_is_not_held() -> None:
    """p. 183 improvises with an object **wielded** as a makeshift weapon."""
    with pytest.raises(ValueError, match="not holding"):
        _resolve(_encounter(_holding(PAN)), "fixture:absent")


# --- What is deliberately absent -------------------------------------------------------


def test_the_thrown_range_is_read_and_has_no_consumer_yet() -> None:
    """p. 183's fourth rule: "If you throw the weapon, it has a normal range of 20 feet and a
    long range of 60 feet."

    The numbers are read off the page and asserted in `verify_d20_rules.py`, and nothing
    consumes them — which is 0058's shape, filed as
    [#390](https://github.com/eddiefiggie/srd-rules-engine/issues/390) rather than left for a
    reader to discover. Pinned here so the gap is a stated one: an improvised
    throw offered without its range would be a rule half-applied.
    """
    assert (IMPROVISED_THROWN_NORMAL_FEET, IMPROVISED_THROWN_LONG_FEET) == (20, 60)
    assert not any(key.startswith("attack-throw:") for key in _keys(_encounter(_holding(PAN))))
