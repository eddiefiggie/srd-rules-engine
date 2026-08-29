"""p. 105's spell components, and the word the rule turns on (#245, 0038 clause 2).

> If the spellcaster can't provide one or more of a spell's components, the spellcaster can't
> cast the spell.

Components were deferred by 0038 clause 2 — holding V/S/M while enforcing nothing is the decay
this repository has found twice — and the hand count #257 built is what made two of the three
checkable.

**The word the rule turns on is "free", and it appears once:**

* **Somatic** — "A spellcaster must use **at least one of their hands** to perform these
  movements."
* **Material** — "The spellcaster must have **a hand free** to access them."

So a creature with both hands full can still gesture. That contradicts how the rule is usually
played and is what the document says; reading "free" into Somatic would be an inferred rule
value of exactly the kind that is plausible, universal in most people's memory, and stated
nowhere (R31).
"""

from __future__ import annotations

from srd_rules_engine.core.equipment import Carriage, Carried, Item, Weapon
from srd_rules_engine.core.spellcasting import Spell, component_refusal

BLADE = Weapon(id="fixture:blade", damage_dice=1, damage_sides=6, hands_when_held=1)
SHIELD = Item(id="fixture:shield", weight=6.0, hands_when_held=1)
ROD = Item(id="fixture:rod", weight=2.0, hands_when_held=1, is_spellcasting_focus=True)
POUCH = Item(id="fixture:pouch", weight=2.0, is_component_pouch=True)

BOTH_FULL = (Carried(BLADE, Carriage.HELD), Carried(SHIELD, Carriage.HELD))
ONE_FREE = (Carried(BLADE, Carriage.HELD),)


def spell(**kw: object) -> Spell:
    fields: dict[str, object] = {"rule_id": "fixture:spell", "level": 1}
    fields.update(kw)
    return Spell(**fields)  # type: ignore[arg-type]


# --- the word the rule turns on ---------------------------------------------------------


def test_somatic_needs_a_hand_and_not_a_free_one() -> None:
    """p. 105 says "at least one of their hands" and does not say *free* — the word appears
    for Material and not for Somatic. Both hands full, and the gesture is still possible."""
    assert component_refusal(spell(somatic=True), BOTH_FULL, hands=2) is None


def test_material_needs_a_free_one() -> None:
    """ "The spellcaster must have a hand free to access them." Same creature, same hands, and
    the other component refuses — which is the distinction stated as a pair."""
    refusal = component_refusal(spell(material=True), BOTH_FULL, hands=2)
    assert refusal is not None and "hand free" in refusal


def test_a_creature_with_no_hands_cannot_gesture() -> None:
    """The Somatic rule does bite, on a creature whose ruleset said it has none."""
    refusal = component_refusal(spell(somatic=True), (), hands=0)
    assert refusal is not None and "at least one hand" in refusal


def test_one_free_hand_serves_somatic_and_material_together() -> None:
    """0039 clause 4, and the clause an implementation drops: "…but it can be the same hand
    used to perform Somatic components, if any." An S,M spell needs one free hand, not two."""
    assert component_refusal(spell(somatic=True, material=True), ONE_FREE, hands=2) is None


def test_an_unstated_hand_count_refuses_nothing() -> None:
    """`Combatant.__post_init__` already settles this direction for p. 90's Two-Handed: "no
    SRD rule states how many hands a creature has, so an unstated count cannot be exceeded"
    (R31). Refusing here would assert the count the engine declines to assume."""
    assert component_refusal(spell(somatic=True, material=True), BOTH_FULL, hands=None) is None


# --- the substitution, and the hand it does or does not need ----------------------------


def test_a_held_focus_provides_materials_with_no_free_hand() -> None:
    """p. 106: "to use a Spellcasting Focus, you must **hold** it". So it occupies a hand and
    needs no free one — the only route by which a caster with both hands full casts an M
    spell."""
    holding_focus = (Carried(BLADE, Carriage.HELD), Carried(ROD, Carriage.HELD))
    assert component_refusal(spell(material=True), holding_focus, hands=2) is None


def test_a_stowed_focus_is_not_held_and_does_not_help() -> None:
    """ "You must hold it" is the condition, and a focus in a pack is not held."""
    stowed = (Carried(BLADE, Carriage.HELD), Carried(SHIELD, Carriage.HELD), Carried(ROD))
    assert component_refusal(spell(material=True), stowed, hands=2) is not None


def test_a_focus_does_not_stand_in_for_consumed_or_costed_materials() -> None:
    """p. 188: it substitutes only for materials that "aren't consumed by the spell and don't
    have a cost specified" — properties of the **spell's** component, which is why 0039
    clause 2 kept them off `Item` and sent them to `Spell`."""
    holding_focus = (Carried(BLADE, Carriage.HELD), Carried(ROD, Carriage.HELD))
    for consumed, costed in ((True, False), (False, True)):
        refusal = component_refusal(
            spell(material=True, material_consumed=consumed, material_has_cost=costed),
            holding_focus,
            hands=2,
        )
        assert refusal is not None and "neither consumed nor costed" in refusal


def test_a_pouch_needs_a_free_hand_like_the_materials_it_replaces() -> None:
    """p. 106: "To use a Component Pouch, you must have **a hand free** to reach into it." So
    carrying one changes nothing about the hand — which is why it is not consulted here, and
    a creature with a free hand is already permitted."""
    with_pouch = (Carried(BLADE, Carriage.HELD), Carried(SHIELD, Carriage.HELD), Carried(POUCH))
    assert component_refusal(spell(material=True), with_pouch, hands=2) is not None
    assert component_refusal(spell(material=True), (*ONE_FREE, Carried(POUCH)), hands=2) is None


# --- what it does not check -------------------------------------------------------------


def test_verbal_is_carried_and_never_refused() -> None:
    """p. 105 refuses it to "a creature who is gagged or in an area of magical silence", and
    the engine models neither (#246). A `verbal` spell passes here, and the read surface names
    the rule that went unchecked rather than letting a silent pass imply it was satisfied."""
    assert component_refusal(spell(verbal=True), BOTH_FULL, hands=2) is None


def test_a_spell_with_no_components_is_never_refused() -> None:
    """A deliberate control: it covers nothing on its own, because no corruption of the
    component path can change what a componentless spell does."""
    assert component_refusal(spell(), (), hands=0) is None
