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

from srd_rules_engine.core import (
    ENGINE_SHAPES,
    Declaration,
    EncounterState,
    Intent,
    Position,
    legal_actions,
)
from srd_rules_engine.core.adjudicate import DamageDice, Effect, EffectKind, Proposal
from srd_rules_engine.core.combat import IMPROVISED_VERIFICATION, improvised_attack_resolver
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import Carriage, Carried, Item, Weapon
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import (
    IMPROVISED_DAMAGE_DICE,
    IMPROVISED_DAMAGE_SIDES,
    IMPROVISED_THROWN_LONG_FEET,
    IMPROVISED_THROWN_NORMAL_FEET,
    attack_throw_key,
    improvised_attack_key,
    improvised_throw_key,
)
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.size import Size
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

#: A Melee weapon without the Thrown property. p. 183's own example of an improvised throw —
#: "throw a Melee weapon that lacks the Thrown property" — with the type a throw of it deals.
CLUB = Weapon(
    id="fixture:club",
    weight=2,
    damage_dice=1,
    damage_sides=6,
    ability="str",
    melee=True,
    damage_type=DamageType.BLUDGEONING,
    improvised_damage_type=DamageType.BLUDGEONING,
)

#: Strength 16 (+3) and Dexterity 12 (+1), so the modifier that reaches a roll says which of
#: p. 15's two halves was followed.
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


def _encounter(
    actor: Combatant, *, feet: int = 5, target_size: Size | None = None
) -> EncounterState:
    boar = _combatant("boar", Position(feet, 0, 0), size=target_size)
    state = EncounterState(generation=0, combatants=(actor, boar))
    return state.with_initiative({"brawler": 20, "boar": 5})


def _keys(state: EncounterState) -> set[str]:
    return {action.key for action in legal_actions(state, "brawler")}


def _resolve(state: EncounterState, item_id: str, *, thrown: bool = False) -> Proposal:
    key = (improvised_throw_key if thrown else improvised_attack_key)(item_id, "boar")
    declaration = Declaration(
        actor_id="brawler", intent=Intent(action_key=key), rule_id="fixture:improvised"
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


# --- The throw (#390, 0090) -----------------------------------------------------------


def test_the_thrown_range_is_the_documents() -> None:
    """p. 183's fourth rule: "If you throw the weapon, it has a normal range of 20 feet and a
    long range of 60 feet." Asserted by 0076 before the throw existed; consumed since 0090."""
    assert (IMPROVISED_THROWN_NORMAL_FEET, IMPROVISED_THROWN_LONG_FEET) == (20, 60)


def test_a_throw_is_offered_within_sixty_feet_and_not_beyond() -> None:
    """Long range is the bound, as it is for a Thrown weapon: the offer stops at sixty."""
    assert improvised_throw_key(PAN.id, "boar") in _keys(_encounter(_holding(PAN), feet=60))
    assert improvised_throw_key(PAN.id, "boar") not in _keys(_encounter(_holding(PAN), feet=61))


def test_the_throw_is_measured_from_the_targets_space() -> None:
    """0086 clause 4: a Huge creature's edge is five feet nearer than its point, so it is a
    target at sixty-five where a Medium one is not."""
    thrower = _combatant(
        "brawler",
        Position(0, 0, 0),
        size=Size.MEDIUM,
        equipment=(Carried(item=PAN, carriage=Carriage.HELD),),
    )
    huge = _keys(_encounter(thrower, feet=65, target_size=Size.HUGE))
    medium = _keys(_encounter(thrower, feet=65, target_size=Size.MEDIUM))

    assert improvised_throw_key(PAN.id, "boar") in huge
    assert improvised_throw_key(PAN.id, "boar") not in medium


def test_the_offer_reports_the_throw_as_a_dexterity_attack_with_its_range() -> None:
    def offer(feet: int) -> Mapping[str, object]:
        return next(
            action.detail
            for action in legal_actions(_encounter(_holding(PAN), feet=feet), "brawler")
            if action.key == improvised_throw_key(PAN.id, "boar")
        )

    near = offer(20)
    assert near["thrown"] is True
    assert near["ability"] == "dex"
    assert near["proficiency_bonus_applies"] is False
    assert near["damage"] == "1d4"
    assert near["beyond_normal_range"] is False
    assert near["lands"] == "unplaced"
    assert offer(21)["beyond_normal_range"] is True


def test_a_thrown_improvised_weapon_is_a_dexterity_attack() -> None:
    """p. 15: "the ability modifier used for a ranged attack is Dexterity", and the exception
    is for weapons *that have* Finesse or Thrown — which an improvised weapon lacks by
    definition. Dexterity 12 (+1) against Strength 16 (+3), so the roll says which half of
    p. 15 was followed, on the attack and on the damage both."""
    proposal = _resolve(_encounter(_holding(PAN), feet=20), PAN.id, thrown=True)

    assert proposal.test is not None
    assert proposal.test.ability == "dex"
    assert {m.source for m in proposal.test.modifiers} == {"ability:dex"}
    (dice,) = proposal.on_success
    assert isinstance(dice, DamageDice)
    assert dice.modifier == 1, "Dexterity, not the swing's Strength"
    assert (dice.count, dice.sides) == (1, 4)
    assert dice.damage_type is DamageType.BLUDGEONING


def test_the_swing_is_still_strength() -> None:
    """The other half of p. 15, kept: the same object swung is a melee attack."""
    proposal = _resolve(_encounter(_holding(PAN)), PAN.id)

    assert proposal.test is not None
    assert proposal.test.ability == "str"


def test_the_object_leaves_the_hand_whether_or_not_the_throw_hits() -> None:
    """In `always`, as p. 90's Thrown weapon is: p. 128 treats a hit and a miss alike as the
    weapon being elsewhere, and where is stated by nothing (0041 clause 4)."""
    proposal = _resolve(_encounter(_holding(PAN), feet=20), PAN.id, thrown=True)

    detached = [
        e for e in proposal.always if isinstance(e, Effect) and e.kind is EffectKind.OBJECT_DETACHED
    ]
    assert [e.item_id for e in detached] == [PAN.id]
    assert any("landed" in claim for claim in proposal.may_not_claim)


def test_the_swing_keeps_the_object_in_hand() -> None:
    proposal = _resolve(_encounter(_holding(PAN)), PAN.id)

    assert not any(getattr(e, "kind", None) is EffectKind.OBJECT_DETACHED for e in proposal.always)


def test_beyond_normal_range_the_throw_has_disadvantage() -> None:
    """p. 90: "When attacking a target beyond normal range, you have Disadvantage on the attack
    roll." p. 183 gives the throw a normal range in p. 90's terms."""
    near = _resolve(_encounter(_holding(PAN), feet=20), PAN.id, thrown=True)
    far = _resolve(_encounter(_holding(PAN), feet=21), PAN.id, thrown=True)

    assert near.test is not None and near.test.has_disadvantage is False
    assert far.test is not None and far.test.has_disadvantage is True


def test_beyond_long_range_the_throw_is_refused() -> None:
    """p. 90: "You can't attack a target beyond the long range." A refusal rather than a
    penalty — a ruling for an attack the rules forbid would be an outcome for something that
    never happened."""
    with pytest.raises(ValueError, match="beyond the long range"):
        _resolve(_encounter(_holding(PAN), feet=61), PAN.id, thrown=True)


def test_the_swing_is_refused_beyond_five_feet() -> None:
    """0062: the menu is not a promise. The read surface has always bounded the swing by
    p. 190's five feet, and the resolver refuses one that arrives from further."""
    with pytest.raises(ValueError, match="swung from 5 feet"):
        _resolve(_encounter(_holding(PAN), feet=10), PAN.id)


def test_a_melee_weapon_lacking_thrown_is_thrown_improvisedly() -> None:
    """p. 183's own example: "throw a Melee weapon that lacks the Thrown property". The club is
    offered as an improvised throw under its own key and never as `attack-throw`, which would
    keep its 1d6, its Strength and the wielder's Proficiency Bonus."""
    keys = _keys(_encounter(_holding(CLUB), feet=20))

    assert improvised_throw_key(CLUB.id, "boar") in keys
    assert attack_throw_key(CLUB.id, "boar") not in keys

    proposal = _resolve(_encounter(_holding(CLUB), feet=20), CLUB.id, thrown=True)
    (dice,) = proposal.on_success
    assert isinstance(dice, DamageDice)
    assert (dice.count, dice.sides) == (1, 4), "not the club's 1d6"
    assert proposal.test is not None and proposal.test.ability == "dex"


def test_a_stowed_object_is_neither_offered_for_throwing_nor_thrown() -> None:
    """p. 90's "draw that weapon as part of the attack" belongs to the Thrown property, which
    an improvised weapon lacks by definition. A stowed rock is equipped first (p. 177)."""
    stowed = _combatant(
        "brawler", Position(0, 0, 0), equipment=(Carried(item=PAN, carriage=Carriage.STOWED),)
    )
    assert improvised_throw_key(PAN.id, "boar") not in _keys(_encounter(stowed, feet=20))
    with pytest.raises(ValueError, match="not holding"):
        _resolve(_encounter(stowed, feet=20), PAN.id, thrown=True)


def test_an_object_nobody_has_ruled_on_cannot_be_thrown_either() -> None:
    assert improvised_throw_key(GLASS.id, "boar") not in _keys(_encounter(_holding(GLASS), feet=20))
    with pytest.raises(ValueError, match="what 'fixture:glass' deals"):
        _resolve(_encounter(_holding(GLASS), feet=20), GLASS.id, thrown=True)


# --- The claim --------------------------------------------------------------------------


def test_p15s_ability_rule_is_asserted_beside_p183() -> None:
    """0076 built the swing as Strength "because this is a melee attack" without asserting the
    sentence that says so. Both halves of p. 15 are in the verifier now, and the reference
    names the page."""
    assert "p. 15" in (IMPROVISED_VERIFICATION.reference or "")


def test_the_shape_is_claimed_now_that_all_four_rules_are_built() -> None:
    assert ENGINE_SHAPES["improvised-weapons"] == "core.combat.improvised_attack_resolver"
