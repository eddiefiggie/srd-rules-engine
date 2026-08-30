"""Moving a creature by something other than itself (#349, 0055).

The gate was the geometry. [0014](../docs/decisions/0014-positional-state.md) makes a
`Position` three **integer** feet, and "10 feet straight away from yourself" lands on integers
only when the ray is axis-aligned. What is asserted here is that the destination is the nearest
lattice point that is **never further than the rule allows**, and that a push is not movement in
the sense every other rule uses.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core import Combatant, Declaration, EncounterState, Intent, Size, read
from srd_rules_engine.core.adjudicate import Effect, EffectKind
from srd_rules_engine.core.combat import attack_resolver
from srd_rules_engine.core.equipment import Carriage, Carried, Weapon
from srd_rules_engine.core.forced_movement import (
    PUSH_STEP_FEET,
    displaced,
    push_distances,
)
from srd_rules_engine.core.position import Position, distance_feet, squared_distance
from srd_rules_engine.core.read_surface import (
    PUSH_DISTANCES_IN_STEPS,
    PUSH_MASTERY_FEET,
    push_attack_key,
)

MAUL = Weapon(
    id="fixture:maul",
    weight=10.0,
    damage_dice=2,
    damage_sides=6,
    ability="str",
    melee=True,
    push=True,
    hands_when_held=2,
)
#: The same weapon without the property, so a test about the gate is not also a test about the
#: weapon table this repository does not ship.
PLAIN = Weapon(
    id="fixture:club",
    weight=2.0,
    damage_dice=1,
    damage_sides=6,
    ability="str",
    melee=True,
    hands_when_held=1,
)

ORIGIN = Position(0, 0, 0)


def creature(cid: str, name: str, **overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": cid,
        "name": name,
        "hit_points": 30,
        "max_hit_points": 30,
        # Low enough that any roll hits, so a test about the push is not about the seed.
        "armour_class": 5,
        "abilities": {"str": 18, "dex": 10, "con": 12},
        "proficiency_bonus": 2,
        "position": ORIGIN,
        "size": Size.MEDIUM,
        "hands": 2,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def hewer(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "equipment": (Carried(MAUL, Carriage.HELD),),
        "mastery_weapons": frozenset({MAUL.id}),
        "is_player_character": True,
    }
    fields.update(overrides)
    return creature("pc", "Pc", **fields)


def encounter(actor: Combatant | None = None, target: Combatant | None = None) -> EncounterState:
    # (3, 4, 0) is exactly five feet away and is not axis-aligned, so it is inside an Unarmed
    # Strike's and a melee weapon's reach *and* exercises the diagonal case.
    foe = target or creature("ogre", "Ogre", position=Position(3, 4, 0), size=Size.LARGE)
    return EncounterState.new([actor or hewer(), foe]).with_initiative({"pc": 20, foe.id: 5})


def push_effects(state: EncounterState, key: str) -> list[Effect]:
    proposal = attack_resolver()(
        state=state,
        declaration=Declaration(actor_id="pc", intent=Intent(action_key=key), rule_id="attack"),
        facts={},
    )
    return [
        e
        for e in proposal.on_success
        if isinstance(e, Effect) and e.kind is EffectKind.MOVED_BY_FORCE
    ]


# --- The geometry -------------------------------------------------------------------------


def test_an_axis_aligned_push_lands_exactly() -> None:
    """The case with no difficulty: the ray is a coordinate axis, so the exact destination is
    already a lattice point and the achieved distance is the requested one."""
    moved = displaced(Position(5, 0, 0), anchor=ORIGIN, feet=10, away=True)
    assert moved is not None
    assert moved.to == Position(15, 0, 0)
    assert moved.achieved_feet == moved.requested_feet == 10


def test_a_pythagorean_direction_also_lands_exactly() -> None:
    """A 3-4-5 ray is not axis-aligned and still lands on integers. Asserted because it is the
    case a reader would assume impossible after reading the docstring, and because the fixture
    below leans on it."""
    moved = displaced(Position(3, 4, 0), anchor=ORIGIN, feet=10, away=True)
    assert moved is not None
    assert moved.to == Position(9, 12, 0)
    assert moved.achieved_feet == 10


def test_a_push_never_travels_further_than_the_rule_allows() -> None:
    """0030 clause 1, and the hard constraint of the whole primitive.

    A 45-degree push of 10 feet has no lattice point at exactly 10 feet along the ray, so the
    engine falls short rather than overshooting: going further would carry a creature out of an
    area or past a boundary the rule did not reach, and only that direction manufactures
    something.
    """
    origin = Position(5, 5, 0)
    moved = displaced(origin, anchor=ORIGIN, feet=10, away=True)
    assert moved is not None
    assert squared_distance(origin, moved.to) <= 10 * 10
    assert moved.achieved_feet == 9, "nine feet of the ten, and never eleven"
    assert moved.requested_feet == 10, "and the number the rule stated is still recorded"


@pytest.mark.parametrize("feet", [5, 10, 15, 20, 25, 30, 60])
@pytest.mark.parametrize(
    "origin", [Position(5, 5, 0), Position(1, 7, 3), Position(2, 0, 9), Position(11, 4, 6)]
)
def test_no_push_ever_overshoots(origin: Position, feet: int) -> None:
    """Swept over every push distance the document names and four awkward directions. The bound
    is the one property nothing may violate, so it is asserted over a range rather than at a
    point."""
    moved = displaced(origin, anchor=ORIGIN, feet=feet, away=True)
    assert moved is not None
    assert squared_distance(origin, moved.to) <= feet * feet
    assert moved.achieved_feet == distance_feet(origin, moved.to)


def test_the_destination_is_the_one_nearest_the_exact_point_not_merely_a_legal_one() -> None:
    """The objective, on a case where the distance bound does **not** decide it alone.

    Most pushes leave exactly one lattice corner inside the stated distance, so the bound picks
    the destination and the "nearest the exact point" rule never runs. A corruption proof found
    that: inverting the objective changed nothing, because there was nothing to choose between.

    Here two corners are both legal — `(0, 4, 12)` and `(0, 5, 12)` — and only one of them is
    near the ray. Choosing the other would push the creature a legal distance in a direction
    p. 90 did not name.
    """
    moved = displaced(Position(0, 1, 3), anchor=ORIGIN, feet=10, away=True)
    assert moved is not None
    assert moved.to == Position(0, 4, 12), "the nearer of two legal corners"
    assert squared_distance(Position(0, 1, 3), Position(0, 5, 12)) <= 100, (
        "and the one it did not pick was legal too, or this asserts nothing"
    )


def test_ties_are_broken_the_same_way_every_time() -> None:
    """R4. A 45-degree push can leave two corners equally near the exact destination, and a
    `min` over an unordered key would resolve them by whichever the loop reached first."""
    twice = [displaced(Position(1, 1, 1), anchor=ORIGIN, feet=15, away=True) for _ in range(5)]
    assert len({m.to for m in twice if m is not None}) == 1


def test_a_pull_stops_at_the_puller_rather_than_passing_through() -> None:
    """p. 320's roper reels a creature *toward* it. A creature that arrived on the far side
    would be somewhere no rule put it."""
    moved = displaced(Position(30, 0, 0), anchor=ORIGIN, feet=100, away=False)
    assert moved is not None
    assert moved.to == ORIGIN


def test_a_pull_that_falls_short_simply_falls_short() -> None:
    moved = displaced(Position(30, 0, 0), anchor=ORIGIN, feet=10, away=False)
    assert moved is not None
    assert moved.to == Position(20, 0, 0)


def test_two_creatures_in_one_place_have_no_direction_to_push_along() -> None:
    """ "Straight away from yourself" names a ray, and there is none. Refused rather than
    resolved, because picking a direction would be the engine deciding where a creature is
    thrown."""
    assert displaced(ORIGIN, anchor=ORIGIN, feet=10, away=True) is None


def test_a_push_of_no_distance_moves_nobody() -> None:
    moved = displaced(Position(3, 4, 0), anchor=ORIGIN, feet=0, away=True)
    assert moved is not None
    assert moved.to == Position(3, 4, 0)


def test_a_negative_distance_is_refused() -> None:
    with pytest.raises(ValueError, match="zero or more feet"):
        displaced(Position(3, 4, 0), anchor=ORIGIN, feet=-5, away=True)


def test_the_derivation_carries_both_numbers() -> None:
    """R30. A reader checking a push against the page needs the distance the rule stated and
    the one the engine produced, and they are usually not the same."""
    moved = displaced(Position(5, 5, 0), anchor=ORIGIN, feet=10, away=True)
    assert moved is not None
    assert "9 feet" in moved.derivation()
    assert "10 the rule allows" in moved.derivation()


# --- The distances a push is offered at -------------------------------------------------------


def test_a_push_is_offered_in_five_foot_steps() -> None:
    """Every push and pull distance the document names is a multiple of five, so five is its
    own vocabulary rather than the grid's."""
    assert PUSH_STEP_FEET == 5
    assert push_distances(10) == (5, 10)
    assert push_distances(30) == (5, 10, 15, 20, 25, 30)


def test_a_maximum_that_is_not_a_multiple_of_five_is_still_offered() -> None:
    """No rule in SRD 5.2 states one, and a menu that silently dropped the maximum would offer
    less than the rule allows."""
    assert push_distances(7) == (5, 7)


# --- p. 90's Push -----------------------------------------------------------------------------


def test_both_distances_are_offered_and_the_choice_is_the_wielders() -> None:
    """p. 90: "you **can** push the creature **up to** 10 feet". Both halves of that choice are
    on the menu — whether to push, and how far."""
    keys = {a.key for a in read(encounter(), "pc").actions}
    assert push_attack_key(MAUL.id, "ogre", 5) in keys
    assert push_attack_key(MAUL.id, "ogre", PUSH_MASTERY_FEET) in keys
    assert any(k.startswith("attack:") for k in keys), "and the plain attack is still there"


def test_a_hit_with_the_push_key_shoves_the_target() -> None:
    moved = push_effects(encounter(), push_attack_key(MAUL.id, "ogre", 10))
    assert len(moved) == 1
    assert moved[0].position == Position(9, 12, 0)
    assert moved[0].amount == 10


def test_a_plain_attack_with_the_same_weapon_pushes_nobody() -> None:
    """The negative case. p. 90 says "you can", so a push that happened without being declared
    would be the engine taking the wielder's choice."""
    assert push_effects(encounter(), f"attack:{MAUL.id}:ogre") == []


def test_a_weapon_without_the_property_offers_no_push() -> None:
    plain = hewer(equipment=(Carried(PLAIN, Carriage.HELD),), mastery_weapons=frozenset({PLAIN.id}))
    keys = {a.key for a in read(encounter(plain), "pc").actions}
    assert not any(k.startswith("push-attack") for k in keys)


def test_the_property_is_gated_on_the_feature_that_unlocks_it() -> None:
    """0047 clause 6. p. 90 gates every mastery on a feature the wielder has, and a Maul in
    untrained hands is still a Maul."""
    untrained = hewer(mastery_weapons=frozenset())
    keys = {a.key for a in read(encounter(untrained), "pc").actions}
    assert not any(k.startswith("push-attack") for k in keys)


def test_a_creature_larger_than_large_is_not_pushed() -> None:
    """p. 90: "if it is **Large or smaller**"."""
    huge = creature("ogre", "Ogre", position=Position(3, 4, 0), size=Size.HUGE)
    keys = {a.key for a in read(encounter(target=huge), "pc").actions}
    assert not any(k.startswith("push-attack") for k in keys)


def test_a_creature_nobody_sized_is_not_pushed() -> None:
    """0051's refusal. Pushing an unsized creature would decide a rule the document
    conditions."""
    unsized = creature("ogre", "Ogre", position=Position(3, 4, 0), size=None)
    keys = {a.key for a in read(encounter(target=unsized), "pc").actions}
    assert not any(k.startswith("push-attack") for k in keys)


def test_a_declaration_beyond_the_stated_maximum_is_refused() -> None:
    """The menu is a menu, not a promise: the bound is checked where the rule is, because a
    declaration is input and input is checkable."""
    with pytest.raises(ValueError, match="up to 10 feet"):
        push_effects(encounter(), push_attack_key(MAUL.id, "ogre", 15))


def test_the_five_foot_steps_are_disclosed() -> None:
    """R32, and #351. The rule permits any distance up to the maximum; the menu offers seven of
    them and this says so."""
    situation = read(encounter(), "pc").situation
    assert situation is not None
    assert PUSH_DISTANCES_IN_STEPS in situation.unenforced_clauses


# --- A push is not movement -------------------------------------------------------------------


def test_a_push_spends_none_of_the_moved_creatures_allowance() -> None:
    """It is not the creature moving. No rule that pushes a creature charges the push to the
    creature's own Speed."""
    state = encounter()
    before = state.combatant("ogre").movement_used
    after = state.with_forced_movement("ogre", Position(9, 12, 0))
    assert after.combatant("ogre").position == Position(9, 12, 0)
    assert after.combatant("ogre").movement_used == before == 0


def test_a_creature_with_no_position_cannot_be_pushed() -> None:
    """An encounter tracking no positions has no origin to push from, and inventing one would
    put a creature on a map that does not exist."""
    nowhere = EncounterState.new([hewer(position=None)]).with_initiative({"pc": 20})
    with pytest.raises(ValueError, match="no position"):
        nowhere.with_forced_movement("pc", Position(5, 0, 0))
