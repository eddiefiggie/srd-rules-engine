"""Six attack-legality rules the menu asked and nothing else did (#376, 0069).

[0068](../docs/decisions/0068-a-rule-the-menu-asks-and-nothing-else-does.md)'s guard found them
on its first run: `Multiattack.allows`, `attacks_remaining`, `has_taken_extra_attack`,
`has_cleaved`, `cleave_openings`, and the Ammunition pair. Each was computed once, consumed by
`legal_actions`, and absent from the path that produces outcomes — so a caller reaching
adjudication directly could attack five times with an Extra Attack of two, cleave every turn,
and fire a crossbow twice with an empty quiver.

**Every test here declares through the resolver, never through the menu.** That is the whole
point: `read` would have refused all six for years, and the question is what happens to a
caller who never asks it. R18 keeps the menu check — legality has to be computable *before* a
caller declares — and these are the floor under it rather than a replacement.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core import (
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EncounterState,
    Intent,
    Weapon,
    attack_key,
    attack_resolver,
    read,
)
from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.equipment import Item, Multiattack
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import bonus_attack_key, cleave_attack_key

SWORD = Weapon(id="fixture:sword", damage_dice=1, damage_sides=8, hands_when_held=1)
AXE = Weapon(id="fixture:axe", damage_dice=1, damage_sides=12, cleave=True, hands_when_held=2)
DAGGER = Weapon(id="fixture:dagger", damage_dice=1, damage_sides=4, light=True, hands_when_held=1)
SHORTSWORD = Weapon(
    id="fixture:shortsword", damage_dice=1, damage_sides=6, light=True, hands_when_held=1
)
#: p. 91 gives Loading and Ammunition to the crossbows. Fixture numbers.
CROSSBOW = Weapon(
    id="fixture:crossbow",
    damage_dice=1,
    damage_sides=8,
    melee=False,
    loading=True,
    ammunition_id="fixture:bolt",
    hands_when_held=2,
    normal_range=80,
    long_range=320,
)
BOLT = Item(id="fixture:bolt", weight=0.1)


def fighter(*held: Weapon, **kw: object) -> Combatant:
    weapons = held or (SWORD,)
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 40,
        "max_hit_points": 40,
        "armour_class": 15,
        "abilities": {"str": 16, "dex": 14},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "hands": 2,
        "equipment": tuple(Carried(w, Carriage.HELD) for w in weapons),
        "weapon_proficiencies": frozenset(w.id for w in weapons),
        "mastery_weapons": frozenset(w.id for w in weapons),
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


def foe(cid: str, at: int, aside: int = 0) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=100,
        max_hit_points=100,
        armour_class=10,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(at, aside, 0),
    )


def encounter(actor: Combatant | None = None, *foes: Combatant) -> EncounterState:
    people = [actor or fighter(), *(foes or (foe("boar", 4), foe("ogre", 5)))]
    return EncounterState.new(people).with_initiative({c.id: 20 - i for i, c in enumerate(people)})


def light_attack_made(state: EncounterState) -> EncounterState:
    """The Attack action spent on a Light weapon, which is what buys p. 89's extra attack."""
    return state.with_action_spent("pc", ActionKind.ACTION, weapon_id=SHORTSWORD.id)


def swing(state: EncounterState, key: str) -> None:
    """Declare an attack straight at the resolver, bypassing the menu entirely."""
    attack_resolver()(
        state=state,
        declaration=Declaration(actor_id="pc", intent=Intent(action_key=key), rule_id="attack"),
        facts={},
    )


# --- p. 257: how many rolls the Attack action bought ----------------------------------------


def test_a_second_attack_from_a_one_attack_action_is_refused() -> None:
    """p. 257: "Some creatures can make more than one attack when they take the Attack
    action", and a creature with no Multiattack makes one."""
    state = encounter()
    # the first is fine
    swing(state, attack_key(SWORD.id, "boar"))

    spent = state.with_attack_made("pc")
    assert spent.attacks_remaining("pc") == 0
    with pytest.raises(ValueError, match="no attacks left"):
        swing(spent, attack_key(SWORD.id, "boar"))


def test_a_multiattack_spends_exactly_what_it_bought() -> None:
    """Two, then refused on the third — the number is the stat block's, not the engine's."""
    state = encounter(fighter(multiattack=Multiattack(attacks=2)))
    after_one = state.with_attack_made("pc")
    # the second is bought
    swing(after_one, attack_key(SWORD.id, "boar"))

    after_two = after_one.with_attack_made("pc")
    with pytest.raises(ValueError, match="no attacks left"):
        swing(after_two, attack_key(SWORD.id, "boar"))


def test_the_menu_and_the_resolver_agree_about_the_same_state() -> None:
    """R18 keeps the menu check and this is the floor under it, so the two must not diverge —
    a menu that offers what the resolver refuses is the defect in the other direction."""
    spent = encounter().with_action_spent("pc", ActionKind.ACTION).with_attack_made("pc")
    assert attack_key(SWORD.id, "boar") not in {a.key for a in read(spent, "pc").actions}
    with pytest.raises(ValueError, match="no attacks left"):
        swing(spent, attack_key(SWORD.id, "boar"))


# --- p. 257: which weapons a Multiattack names ----------------------------------------------


def test_a_weapon_the_multiattack_does_not_name_is_refused() -> None:
    """p. 257: the entry "details the attacks a creature can make" (0043 clause 2)."""
    named = Multiattack(attacks=2, permitted=frozenset({DAGGER.id}))
    state = encounter(fighter(SWORD, DAGGER, multiattack=named))

    # the one it names

    swing(state, attack_key(DAGGER.id, "boar"))
    with pytest.raises(ValueError, match="does not name"):
        swing(state, attack_key(SWORD.id, "boar"))


def test_a_multiattack_naming_nothing_permits_any_held_weapon() -> None:
    """An empty set refuses nothing, which is the reading for a ruleset that stated a count
    and no list — and it is what keeps this refusal from biting every ordinary creature."""
    state = encounter(fighter(SWORD, DAGGER, multiattack=Multiattack(attacks=2)))
    swing(state, attack_key(SWORD.id, "boar"))
    swing(state, attack_key(DAGGER.id, "boar"))


# --- p. 89: one extra attack -----------------------------------------------------------------


def test_a_second_p89_extra_attack_is_refused() -> None:
    """p. 89 grants "**one** extra attack", and p. 90's Nick re-routes that same attack rather
    than adding another (#320)."""
    state = light_attack_made(encounter(fighter(SHORTSWORD, DAGGER)))
    # the one p. 89 grants
    swing(state, bonus_attack_key(DAGGER.id, "boar"))

    taken = state.with_extra_attack("pc")
    with pytest.raises(ValueError, match=r"already taken p\. 89.s one extra attack"):
        swing(taken, bonus_attack_key(DAGGER.id, "boar"))


def test_the_extra_attack_is_not_charged_against_the_attack_actions_rolls() -> None:
    """ "as part of" the Attack action is not "bought by" it, so an extra attack must not be
    refused by the roll count — which would quietly cost a Multiattack creature one of its
    own (0043)."""
    spent = light_attack_made(encounter(fighter(SHORTSWORD, DAGGER))).with_attack_made("pc")
    assert spent.attacks_remaining("pc") == 0, "precondition: the Attack action is done"
    swing(spent, bonus_attack_key(DAGGER.id, "boar"))


# --- p. 90: Cleave, once, and only onto an opening --------------------------------------------


def opened(state: EncounterState) -> EncounterState:
    return state.with_cleave_opening("pc", AXE.id, "boar").with_attack_made("pc")


def test_a_second_cleave_in_one_turn_is_refused() -> None:
    """p. 90: "You can make this extra attack **only once per turn**"."""
    state = opened(encounter(fighter(AXE)))
    # the first
    swing(state, cleave_attack_key(AXE.id, "ogre"))

    with pytest.raises(ValueError, match="already cleaved"):
        swing(state.with_cleave_taken("pc"), cleave_attack_key(AXE.id, "ogre"))


def test_a_cleave_with_no_hit_behind_it_is_refused() -> None:
    """p. 90 hangs the swing on a hit that landed — "**If you hit** a creature with a melee
    attack roll using this weapon" — so a Cleave out of nowhere is an attack never granted."""
    state = encounter(fighter(AXE)).with_attack_made("pc")
    with pytest.raises(ValueError, match="has opened a Cleave"):
        swing(state, cleave_attack_key(AXE.id, "ogre"))


def test_a_cleave_is_not_refused_by_the_attack_actions_roll_count() -> None:
    """Its cap is its own sentence, so a Cleave rides on a spent Attack action — which is the
    only state it ever occurs in, since the opening comes from that action's hit."""
    state = opened(encounter(fighter(AXE)))
    assert state.attacks_remaining("pc") == 0, "precondition"
    swing(state, cleave_attack_key(AXE.id, "ogre"))


# --- p. 90: Loading, and p. 89: Ammunition ----------------------------------------------------


def archer(**kw: object) -> Combatant:
    return fighter(
        CROSSBOW,
        equipment=(
            Carried(CROSSBOW, Carriage.HELD),
            Carried(BOLT, Carriage.STOWED),
        ),
        **kw,
    )


def test_a_second_shot_from_a_loading_weapon_is_refused() -> None:
    """p. 90: "you can fire only one piece of ammunition… no matter how many attacks you can
    normally make." Capped per **action used** rather than per turn (#271)."""
    state = encounter(archer(multiattack=Multiattack(attacks=2)), foe("boar", 30))
    # the first shot
    swing(state, attack_key(CROSSBOW.id, "boar"))

    fired = state.with_loading_shot("pc", "action").with_attack_made("pc")
    with pytest.raises(ValueError, match="already fired"):
        swing(fired, attack_key(CROSSBOW.id, "boar"))


def test_a_shot_with_no_ammunition_is_refused() -> None:
    """p. 89: a ranged attack "only if you have ammunition to fire from it"."""
    empty = replace(archer(), equipment=(Carried(CROSSBOW, Carriage.HELD),))
    state = encounter(empty, foe("boar", 30))
    with pytest.raises(ValueError, match="cannot fire"):
        swing(state, attack_key(CROSSBOW.id, "boar"))


def test_the_same_shot_with_ammunition_is_allowed() -> None:
    """Shown to be the ammunition's doing, and not a fixture that could never fire."""
    swing(encounter(archer(), foe("boar", 30)), attack_key(CROSSBOW.id, "boar"))
