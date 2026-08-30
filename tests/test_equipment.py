"""What a creature holds, wears and carries (#257, 0039 clauses 1-4 and 7).

Three things here are easy to get wrong, and the first is the one that would have shipped:

* **No SRD rule says how many hands a creature has.** Every printed rule is relational — "a
  free hand" (pp. 89, 105, 182, 190), "requires two hands" (p. 90) — and two is what everyone
  remembers and nothing in the document states. So the count is `None` until a ruleset says,
  and a rule turning on it declines rather than guessing.
* **One free hand serves Somatic and Material together.** p. 105 says so in a subordinate
  clause at the end of a paragraph about pouches, and most spells with material components
  have somatic ones — so a model charging a hand per component is wrong for the common case.
* **Worn gear still counts as carried.** p. 178 asks for "the maximum weight in pounds that
  you can carry", and armour on your back is carried as surely as rope in your pack.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core import Combatant, EncounterState, read
from srd_rules_engine.core.equipment import (
    Carriage,
    Carried,
    DetachedObject,
    Item,
    Weapon,
    carried_weight,
    free_hands,
    items_in,
    reachable_objects,
    unplaced_objects,
)
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.size import Size

SWORD = Item(id="fixture:sword", weight=3.0, hands_when_held=1)
GREATAXE = Item(id="fixture:greataxe", weight=7.0, hands_when_held=2)
MAIL = Item(id="fixture:mail", weight=55.0)
POUCH = Item(id="fixture:pouch", weight=2.0, is_component_pouch=True)
FOCUS = Item(id="fixture:rod", weight=2.0, hands_when_held=1, is_spellcasting_focus=True)


def creature(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 14, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(actor: Combatant) -> EncounterState:
    return EncounterState.new([actor]).with_initiative({"pc": 10})


# --- The count nobody stated ---------------------------------------------------------------


def test_a_creature_whose_ruleset_did_not_say_has_an_unanswerable_hand_count() -> None:
    """R31, and the value this build would have inferred.

    No rule in SRD v5.2.1 states how many hands a creature has — a sweep of every "free hand",
    "one hand", "two hands" and "a hand" in the document returns only *relational* rules. Two
    is plausible, universal in recall, and stated nowhere, which is precisely the shape R31
    forbids. `None` is the honest answer and it is not zero: zero would refuse a spell the
    document might permit.
    """
    assert creature().hands is None
    assert creature().free_hands is None
    assert creature(equipment=(Carried(SWORD, Carriage.HELD),)).free_hands is None


def test_a_ruleset_that_says_gets_an_answer() -> None:
    two = creature(hands=2, equipment=(Carried(SWORD, Carriage.HELD),))
    assert two.free_hands == 1


def test_a_two_handed_item_takes_both() -> None:
    """p. 90: "A Two-Handed weapon requires two hands when you attack with it.\""""
    assert creature(hands=2, equipment=(Carried(GREATAXE, Carriage.HELD),)).free_hands == 0


def test_only_held_things_cost_hands() -> None:
    """p. 105 asks whether a hand is free, not whether the creature owns anything. Armour worn
    and a greataxe slung cost nothing, which is why `Carriage` is a field rather than a flag.

    **The stowed item is one that would take two hands if held**, deliberately. A first draft
    of this test stowed a pouch and wore mail — both `hands_when_held=0` — so charging every
    item regardless of carriage gave the same answer and the assertion could not fail. The
    corruption proof caught it, which is what corruption proofs are for.
    """
    laden = creature(
        hands=2,
        equipment=(
            Carried(MAIL, Carriage.WORN),
            Carried(GREATAXE, Carriage.STOWED),
            Carried(SWORD, Carriage.HELD),
        ),
    )
    assert laden.free_hands == 1


def test_holding_more_than_there_are_hands_is_refused() -> None:
    """p. 90: "A Two-Handed weapon **requires two hands** when you attack with it."

    **This test asserted 0 free hands until #263**, and accepting the state was the reason
    Two-Handed was representable and unenforced: a one-handed creature could grip a greataxe
    and simply report nothing free. The requirement is only real if the state that violates it
    cannot be built.

    Refused at construction, where every writer passes.
    """
    with pytest.raises(ValueError, match="Two-Handed weapon requires two hands"):
        creature(
            hands=1,
            equipment=(Carried(SWORD, Carriage.HELD), Carried(GREATAXE, Carriage.HELD)),
        )


def test_an_unstated_hand_count_cannot_be_exceeded() -> None:
    """R31. No SRD rule says how many hands a creature has, so a creature whose ruleset did
    not say has no limit to break — refusing it would enforce a number the document does not
    state."""
    unstated = creature(equipment=(Carried(GREATAXE, Carriage.HELD),))
    assert unstated.free_hands is None


def test_a_versatile_grip_is_the_creature_s_and_not_the_weapon_s() -> None:
    """p. 90: "A Versatile weapon can be used with one or two hands." A choice the creature
    makes each time, so it lives on `Carried` — `Weapon.wielded_two_handed` was a field on the
    weapon describing how the creature held it, which is `Weapon.proficient`'s mistake one
    field further down (#263)."""
    from srd_rules_engine.core.equipment import Weapon

    longsword = Weapon(
        id="fixture:longsword", damage_dice=1, damage_sides=8, versatile_sides=10, hands_when_held=1
    )
    assert "wielded_two_handed" not in Weapon.__dataclass_fields__

    one_handed = Carried(longsword, Carriage.HELD)
    two_handed = Carried(longsword, Carriage.HELD, hands=2)
    assert longsword.sides_in_use(one_handed.hands_used) == 8
    assert longsword.sides_in_use(two_handed.hands_used) == 10

    # The same weapon, two creatures, two grips — unexpressible before.
    assert creature(hands=2, equipment=(one_handed,)).free_hands == 1
    assert creature(hands=2, equipment=(two_handed,)).free_hands == 0


def test_a_grip_is_stated_only_for_something_held() -> None:
    """p. 90's choice is about a weapon being *used*, so a grip on a stowed item describes
    nothing and is refused rather than silently ignored."""
    with pytest.raises(ValueError, match="commits no hands"):
        Carried(SWORD, Carriage.STOWED, hands=1)


def test_one_free_hand_is_what_an_s_m_spell_needs() -> None:
    """p. 105: "The spellcaster must have a hand free to access them, **but it can be the same
    hand used to perform Somatic components, if any**."

    The clause an implementation gets wrong, asserted from the creature's side: a caster
    holding a one-handed focus in a two-handed pair has **one** hand free, and that one hand
    satisfies Somatic and Material together. Nothing here performs that check — it needs the
    spell's V/S/M data too (#245) — but the number it will read is this one.
    """
    caster = creature(hands=2, equipment=(Carried(FOCUS, Carriage.HELD),))
    assert caster.free_hands == 1


# --- p. 178: what is carried ---------------------------------------------------------------


def test_worn_and_held_and_stowed_all_count_as_carried() -> None:
    """p. 178: "the maximum weight in pounds that you can carry". Armour on your back is
    carried as surely as rope in your pack, so all three carriages add up."""
    laden = creature(
        equipment=(
            Carried(MAIL, Carriage.WORN),
            Carried(SWORD, Carriage.HELD),
            Carried(POUCH, Carriage.STOWED),
        )
    )
    assert laden.carried_weight == pytest.approx(60.0)


def test_whether_it_is_too_much_needs_a_size_and_still_refuses_without_one() -> None:
    """The assertion this replaces said the engine could not answer at all, because p. 178's
    table is keyed on a `Size` nothing had (#259). It has one now — and the refusal survives
    for a creature nobody sized, which is the half worth keeping.

    Retired and rebuilt in one change, because a removed absence-assertion that nothing
    replaces is how a gap closes with no test covering the rule that closed it.
    """
    unsized = creature(equipment=(Carried(MAIL, Carriage.WORN),))
    assert unsized.size is None
    assert unsized.carrying_capacity is None, "no row to read without a size"
    assert unsized.over_carrying_capacity is None, "and no verdict either — not False"

    sized = replace(unsized, size=Size.MEDIUM)
    assert sized.carrying_capacity is not None
    assert sized.over_carrying_capacity is False


def test_a_weight_may_be_fractional() -> None:
    """p. 178's own table produces halves — Tiny carries Strength times 7.5 lb — so an integer
    pound would round a bound the document states exactly."""
    assert Item(id="fixture:dart", weight=0.25).weight == pytest.approx(0.25)


# --- The vocabulary ------------------------------------------------------------------------


def test_items_can_be_listed_by_where_they_are() -> None:
    gear = (
        Carried(MAIL, Carriage.WORN),
        Carried(SWORD, Carriage.HELD),
        Carried(POUCH, Carriage.STOWED),
    )
    actor = creature(equipment=gear)
    assert actor.items_carried(Carriage.WORN) == (MAIL,)
    assert actor.items_carried(Carriage.HELD) == (SWORD,)
    assert actor.items_carried(Carriage.STOWED) == (POUCH,)


def test_an_item_defaults_to_stowed() -> None:
    """The residual state. Nothing is worn or held unless a ruleset says it is — the direction
    that cannot invent a free hand or a suit of armour nobody put on."""
    assert Carried(SWORD).carriage is Carriage.STOWED
    assert creature(hands=2, equipment=(Carried(SWORD),)).free_hands == 2


def test_the_two_component_substitutes_are_separate_flags() -> None:
    """p. 105 names a Component Pouch and a Spellcasting Focus as alternatives **to each
    other**, and the classes granting one are not those granting the other. One flag with two
    meanings would make them interchangeable, which the document does not."""
    assert POUCH.is_component_pouch and not POUCH.is_spellcasting_focus
    assert FOCUS.is_spellcasting_focus and not FOCUS.is_component_pouch


def test_an_item_carries_no_price_and_no_name() -> None:
    """0039 clause 2. pp. 93-97 are content this repository does not ship (R31), and a field
    the engine has no rule about is one nothing reads — the decay found three times already."""
    fields = {f for f in Item.__dataclass_fields__}
    assert fields == {
        "id",
        "weight",
        "hands_when_held",
        "is_spellcasting_focus",
        "is_component_pouch",
    }


def test_an_item_is_identified_and_its_numbers_are_sane() -> None:
    with pytest.raises(ValueError, match="identified"):
        Item(id="")
    with pytest.raises(ValueError, match="not negative"):
        Item(id="fixture:odd", weight=-1)
    with pytest.raises(ValueError, match="zero or more hands"):
        Item(id="fixture:odd", hands_when_held=-1)


# --- R18: the agent can see it -------------------------------------------------------------


def test_the_read_surface_reports_both_and_mutates_nothing() -> None:
    """R18 wants a value the agent can act on; R19 keeps the read a read."""
    actor = creature(
        hands=2, equipment=(Carried(SWORD, Carriage.HELD), Carried(MAIL, Carriage.WORN))
    )
    state = encounter(actor)

    situation = read(state, "pc").situation
    assert situation is not None
    assert situation.free_hands == 1
    assert situation.carried_weight == pytest.approx(58.0)

    # `with_initiative` gives the combatant its initiative, so comparing against the one
    # passed in would compare against a different creature. What R19 asks is that *reading*
    # changes nothing — the generation stays put and a second read agrees with the first.
    before = state.generation
    assert read(state, "pc").situation == situation
    assert state.generation == before, "a read moved the generation"


def test_the_surface_reports_an_unknown_hand_count_as_unknown() -> None:
    """Not zero. An agent told it has no free hands would decline a spell the document might
    permit, which is the wrong direction to be wrong in."""
    situation = read(encounter(creature()), "pc").situation
    assert situation is not None
    assert situation.free_hands is None


# --- R32: the boundary --------------------------------------------------------------------


def test_the_module_discloses_what_it_does_not_model() -> None:
    """0039 clause 7. "The creature's equipment" reads as complete to anyone who does not find
    the limit, and the limit is large: attunement, item charges, carrying capacity, weapons."""
    from pathlib import Path

    module = (
        Path(__file__).resolve().parents[1] / "src" / "srd_rules_engine" / "core" / "equipment.py"
    ).read_text()

    assert "What this does not model" in module
    # #259 was here until 0051 closed it. #336 replaces it: the bound is built and the Speed
    # consequence is not, so what the module owes a reader is a pointer at the half that is
    # still missing rather than at the issue that closed.
    for issue in ("#245", "#247", "#258", "#336"):
        assert issue in module, f"the disclosure no longer points at {issue}"


# --- The helpers, used directly ------------------------------------------------------------


def test_the_helpers_answer_the_same_as_the_combatant() -> None:
    gear = (Carried(SWORD, Carriage.HELD), Carried(MAIL, Carriage.WORN))
    actor = creature(hands=2, equipment=gear)

    assert free_hands(gear, 2) == actor.free_hands
    assert carried_weight(gear) == actor.carried_weight
    assert items_in(gear, Carriage.HELD) == actor.items_carried(Carriage.HELD)


def test_a_carried_item_reports_what_it_costs_in_hands() -> None:
    assert Carried(GREATAXE, Carriage.HELD).hands_used == 2
    assert Carried(GREATAXE, Carriage.STOWED).hands_used == 0
    assert replace(Carried(GREATAXE, Carriage.HELD), carriage=Carriage.WORN).hands_used == 0


# --- 0040: a weapon is one of these ---------------------------------------------------------


def test_a_weapon_is_an_item() -> None:
    """0040 clause 1. Composition would have put the weapon *outside* `Carried`, so state
    would hold the item and not the weapon and `legal_actions` would need it passed in —
    the repair 0026, 0038 and 0039 each refused."""
    from srd_rules_engine.core.equipment import Weapon

    blade = Weapon(id="fixture:blade", damage_dice=2, damage_sides=6, weight=3.0, hands_when_held=1)
    assert isinstance(blade, Item)
    assert blade.weight == pytest.approx(3.0)
    assert Carried(blade, Carriage.HELD).hands_used == 1


def test_a_weapon_carries_no_proficiency_of_its_own() -> None:
    """0040 clause 2, and the rules fix inside the refactor. p. 89: "Anyone can wield a
    weapon, but **you** must have proficiency with it." A `proficient` field on the weapon
    worked exactly while a weapon belonged to one wielder, and failed toward *granting* a
    bonus once one could be picked up."""
    from srd_rules_engine.core.equipment import Weapon

    assert "proficient" not in Weapon.__dataclass_fields__
    assert "weapon_proficiencies" in Combatant.__dataclass_fields__


def test_only_weapons_in_hand_count_as_wielded() -> None:
    """A sword in a pack is not a sword you can swing. `weapons_held` is what the read
    surface offers attacks for, so a stowed weapon must not appear in it."""
    from srd_rules_engine.core.equipment import Weapon

    blade = Weapon(id="fixture:blade", damage_dice=2, damage_sides=6, hands_when_held=1)
    armed = creature(hands=2, equipment=(Carried(blade, Carriage.HELD),))
    packed = creature(hands=2, equipment=(Carried(blade, Carriage.STOWED),))

    assert armed.weapons_held == (blade,)
    assert packed.weapons_held == ()


def test_an_ordinary_item_is_not_a_weapon() -> None:
    """The discriminator is the subtype, not a flag — so a rope in hand offers no attack."""
    roped = creature(hands=2, equipment=(Carried(Item(id="fixture:rope"), Carriage.HELD),))
    assert roped.weapons_held == ()


# --- 0041: an object no creature has (#279) ---------------------------------------------


def test_a_detached_object_has_no_position_until_something_states_one() -> None:
    """0041 clause 4. Five printed rules detach an item and **none says where it lands**.

    p. 177's Attack action, p. 191's Unconscious, p. 90's Thrown, and the *Command* and
    *Fear* spells on pp. 116 and 130. `None` is therefore the honest default and means
    *nobody has said* — the reading `Combatant.position` and `Combatant.hands` already carry.
    """
    assert DetachedObject(Item(id="dagger")).position is None


def test_nothing_defaults_a_dropped_object_to_its_holders_space() -> None:
    """The default 0041 clause 5 exists to refuse, asserted rather than trusted.

    "A dropped item is in your space" is the most plausible sentence in this area and is not
    in the document: p. 217's Dancing Sword spends a clause saying "falls to the ground in
    your space", which a general rule would make unnecessary. It is also wrong for the other
    half of the vocabulary — p. 90 gives a thrown weapon a range in feet, so the thrower's
    position is the one place the javelin certainly is not.

    A future implementer wiring detachment (#280) has to state a position or leave it `None`;
    this fails if a default is ever wired in behind them.
    """
    holder = Position(15, 15, 0)
    detached = DetachedObject(Item(id="javelin"))
    assert detached.position is None
    assert detached.position != holder


def test_reach_is_unanswerable_for_a_creature_with_no_position() -> None:
    """`None`, not an empty tuple. An encounter that tracks no positions cannot answer the
    question, and an empty tuple would claim it had and found nothing."""
    objects = (DetachedObject(Item(id="dagger"), Position(0, 0, 0)),)
    assert reachable_objects(objects, None, 5) is None


def test_an_object_nobody_placed_is_never_reachable_and_never_silently_dropped() -> None:
    """The two halves of 0041 clause 4 in one assertion.

    Returning it as reachable would invent the coordinate the type exists to refuse.
    Omitting it without a word would show an empty menu whose emptiness a reader has to
    interpret, which is the narrowing #267 caught in 0040 clause 3. So it is absent from one
    list and named in the other.
    """
    unplaced = DetachedObject(Item(id="lost-sword"))
    objects = (unplaced,)
    assert reachable_objects(objects, Position(0, 0, 0), 5) == ()
    assert unplaced_objects(objects) == (unplaced,)


def test_reach_distinguishes_in_reach_from_out_of_reach() -> None:
    """p. 186: "A creature has a reach of 5 feet unless a rule says otherwise.\""""
    near = DetachedObject(Item(id="dagger"), Position(5, 0, 0))
    far = DetachedObject(Item(id="halberd"), Position(30, 0, 0))
    reachable = reachable_objects((near, far), Position(0, 0, 0), 5)
    assert reachable == (near,)
    assert unplaced_objects((near, far)) == ()


def test_letting_go_of_an_item_adds_no_type_to_the_item_hierarchy() -> None:
    """0041 clause 1, which is a decision **not** to add a type — so only a guard records it.

    p. 191: "A weapon is an object that is in the Simple or Martial weapon category." p. 12
    lists a *sword* among its examples of an object, and p. 185 defines one as "a nonliving,
    distinct thing". The `Item` that was held is the `Item` on the floor. What changed when
    the creature let go is a **relation**, and a `GroundItem` or `DroppedWeapon` subtype would
    make `isinstance` answer a question about a relation rather than about a kind.

    That subtype is the obvious shape for a reader who finds an item no longer in
    `Combatant.equipment`, which is exactly why the absence needs asserting: nothing else in
    the tree says "do not add one here", and a decision not to build something leaves no code
    behind to read.

    `Weapon` is the one legitimate subtype (0040 clause 1) — it *is* an item with more rules
    attached. `DetachedObject` composes instead, because it is not a kind of item at all.
    """
    assert [subtype.__name__ for subtype in Item.__subclasses__()] == [Weapon.__name__]
    assert not issubclass(DetachedObject, Item)
    assert DetachedObject(SWORD).item is SWORD


def test_carriage_stays_at_three_because_every_member_is_a_way_of_being_carried() -> None:
    """0041 clause 2, pinned so a fourth member cannot arrive quietly.

    p. 190: "When you teleport, all the equipment you're **wearing and carrying** teleports
    with you." Every `Carriage` member is a way of being carried, so that rule reads the whole
    enum. A fourth member for a dropped or thrown object would put it inside `equipment` and
    teleport it away with the creature who let go of it — and the repair would be a special
    case inside a closed vocabulary, which is the failure 0019 exists to refuse.

    The cost of the fourth member is not the member. It is that every existing reader of
    "wearing and carrying" quietly acquires a bug, and this engine does not implement
    Teleportation yet — so the bug would ship well ahead of the rule that reveals it.

    A detached object is `DetachedObject` on `EncounterState` instead, holding no `Carriage`
    at all.
    """
    assert {c.value for c in Carriage} == {"worn", "held", "stowed"}
    assert not hasattr(DetachedObject(Item(id="dagger")), "carriage")
