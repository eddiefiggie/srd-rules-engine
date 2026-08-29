"""p. 90's Thrown property: the arithmetic, and a destination the document never states (#284).

> **Thrown.** If a weapon has the Thrown property, you can throw the weapon to make a ranged
> attack, and you can draw that weapon as part of the attack. If the weapon is a Melee weapon,
> use the same ability modifier for the attack and damage rolls that you use for a melee
> attack with that weapon.

Three things here are easy to get wrong:

* **Which bound applies is a question about the attack, not the weapon.** A Dagger is a Melee
  weapon that carries a range, so it reaches five feet when swung and sixty when thrown. Range
  checks that read the weapon alone let it stab across the room.
* **A thrown Melee weapon keeps its melee ability modifier.** p. 90 spends its second sentence
  on this, which only makes sense as a warning: a ranged attack does not silently become a
  Dexterity attack because it is ranged.
* **Where it lands is stated by nothing.** 0041 clause 4, and the throw is where a player meets
  it — the javelin is gone and cannot be picked up unless a ruleset says where it fell.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    Rule,
    RuleProvenance,
    Weapon,
    attack_key,
    attack_resolver,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.adjudicate import RejectionCode, Status
from srd_rules_engine.core.combat import _weapon_and_target
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import attack_throw_key
from srd_rules_engine.memory.store import JsonMemoryStore

#: A Melee weapon that may be thrown — p. 90's own shape, and the one that makes the range
#: question a question. Finesse, so `ability` is a choice the wielder already made.
JAVELIN = Weapon(
    id="fixture:javelin",
    damage_dice=1,
    damage_sides=6,
    thrown=True,
    normal_range=30,
    long_range=120,
    hands_when_held=1,
)
#: The same weapon without the property, for p. 183's refusal.
CLUB = Weapon(id="fixture:club", damage_dice=1, damage_sides=6, hands_when_held=1)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("thrown", [STRIKE])


def thrower(
    *, carried: tuple[tuple[Weapon, Carriage], ...] = ((JAVELIN, Carriage.HELD),)
) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16, "dex": 10},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        hands=2,
        equipment=tuple(Carried(w, c) for w, c in carried),
        weapon_proficiencies=frozenset(w.id for w, _ in carried),
    )


def boar(distance: int) -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=20,
        max_hit_points=20,
        armour_class=8,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(distance, 0, 0),
    )


def encounter(distance: int = 5, actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or thrower(), boar(distance)]).with_initiative(
        {"pc": 20, "boar": 5}
    )


def build(path: Path, *, seed: int = 3) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def declare(state: EncounterState, key: str) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=key),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def keys(state: EncounterState) -> set[str]:
    return {a.key for a in read(state, "pc").actions}


# --- the bound belongs to the attack, not the weapon ------------------------------------


def test_a_thrown_melee_weapon_may_not_be_swung_across_the_room() -> None:
    """The trap this build had to avoid. `_within_weapon_range` keyed on `long_range is not
    None`, which was correct only while no Melee weapon carried a range — and p. 90's *Range*
    entry gives one to every Thrown weapon. A javelin thirty feet away is throwable and not
    stabbable."""
    offered = keys(encounter(distance=30))
    assert attack_throw_key(JAVELIN.id, "boar") in offered
    assert attack_key(JAVELIN.id, "boar") not in offered


def test_the_same_weapon_is_both_at_arms_length() -> None:
    offered = keys(encounter(distance=5))
    assert attack_throw_key(JAVELIN.id, "boar") in offered
    assert attack_key(JAVELIN.id, "boar") in offered


def test_beyond_long_range_no_throw_is_offered() -> None:
    """p. 90: "You can't attack a target beyond the long range.\""""
    assert attack_throw_key(JAVELIN.id, "boar") not in keys(encounter(distance=200))


def test_a_stowed_thrown_weapon_is_offered_without_spending_p177s_swap() -> None:
    """p. 90: "you can draw that weapon **as part of the attack**" — the Thrown property
    carries its own equip, so it needs none of p. 177's allowance."""
    state = encounter(actor=thrower(carried=((JAVELIN, Carriage.STOWED),)))
    assert attack_throw_key(JAVELIN.id, "boar") in keys(state)


def test_a_weapon_without_the_property_is_never_offered_as_a_throw() -> None:
    """p. 183 makes it an improvised weapon dealing "1d4 damage of a type the GM thinks is
    appropriate" — a person's judgement this engine may not invent (#264)."""
    state = encounter(actor=thrower(carried=((CLUB, Carriage.HELD),)))
    assert attack_throw_key(CLUB.id, "boar") not in keys(state)


def test_throwing_one_anyway_is_rejected_by_the_surface(tmp_path: Path) -> None:
    """Refused, not silently resolved as an ordinary throw — which would keep the weapon's own
    dice and quietly answer the question p. 183 leaves to a person.

    The refusal arrives from **legality** rather than from the resolver: the surface never
    offered the key, so R18's "computable rather than checkable afterwards" catches it before
    any weapon is looked up. That is the better of the two refusals, and the resolver keeps
    its own below.
    """
    state = encounter(actor=thrower(carried=((CLUB, Carriage.HELD),)))
    ruling, _after = build(tmp_path).adjudicate(
        state, declare(state, attack_throw_key(CLUB.id, "boar"))
    )
    assert ruling.status is Status.REJECTED
    assert ruling.reason_code is RejectionCode.ACTION_NOT_LEGAL


def test_the_resolver_refuses_a_throw_the_surface_somehow_offered() -> None:
    """Defence in depth, and it is not redundant: a ruleset registering its own resolver, or
    a future surface change, could put a non-Thrown weapon on this path. p. 183's damage type
    is a person's judgement, so the engine declines rather than substituting the weapon's."""
    actor = thrower(carried=((CLUB, Carriage.HELD),))
    declaration = Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_throw_key(CLUB.id, "boar")),
        rule_id=STRIKE.id,
    )
    with pytest.raises(ValueError, match="does not have the Thrown property"):
        _weapon_and_target(actor, declaration)


# --- the arithmetic, and the destination ------------------------------------------------


def test_a_thrown_melee_weapon_keeps_its_melee_ability_modifier(tmp_path: Path) -> None:
    """p. 90's second sentence, which only makes sense as a warning: a ranged attack does not
    become a Dexterity attack because it is ranged. Strength 16 (+3), Dexterity 10 (+0), so
    the modifier that reaches the roll says which rule was followed."""
    state = encounter(distance=20)
    ruling, _after = build(tmp_path).adjudicate(
        state, declare(state, attack_throw_key(JAVELIN.id, "boar"))
    )
    assert ruling.result is not None
    sources = {m.source: m.value for m in ruling.result.modifiers}
    assert sources["ability:str"] == 3


def test_a_thrown_weapon_leaves_the_hand_and_lands_nowhere(tmp_path: Path) -> None:
    """0041 clause 4, arriving where a player meets it. p. 90 says the weapon is thrown and
    never says where it goes, so it is detached with no position — and cannot be picked up
    until a ruleset states one."""
    state = encounter(distance=20)
    _ruling, after = build(tmp_path).adjudicate(
        state, declare(state, attack_throw_key(JAVELIN.id, "boar"))
    )
    assert [c.item.id for c in after.combatant("pc").equipment] == []
    assert [o.item.id for o in after.detached_objects] == [JAVELIN.id]
    assert after.detached_objects[0].position is None
    situation = read(after, "pc").situation
    assert situation is not None
    assert situation.unplaced_objects == (JAVELIN.id,)


def test_the_weapon_leaves_the_hand_on_a_miss_too(tmp_path: Path) -> None:
    """p. 128: "a thrown weapon or piece of ammunition returns to normal size immediately
    after it **hits or misses** a target" — the document treating both outcomes as leaving the
    weapon elsewhere. So the detachment rides in `always`, not in a hit branch."""
    state = encounter(distance=20)
    armoured = replace(state.combatant("boar"), armour_class=30)
    state = replace(state, combatants=(state.combatant("pc"), armoured))
    ruling, after = build(tmp_path, seed=1).adjudicate(
        state, declare(state, attack_throw_key(JAVELIN.id, "boar"))
    )
    assert ruling.result is not None and not ruling.result.succeeded
    assert [o.item.id for o in after.detached_objects] == [JAVELIN.id]


def test_a_throw_beyond_normal_range_has_disadvantage(tmp_path: Path) -> None:
    """p. 90: "When attacking a target beyond normal range, you have Disadvantage on the
    attack roll." 30 feet normal, 120 long — so 60 feet is inside the bound and penalised."""
    state = encounter(distance=60)
    ruling, _after = build(tmp_path).adjudicate(
        state, declare(state, attack_throw_key(JAVELIN.id, "boar"))
    )
    assert ruling.result is not None and ruling.result.declared_disadvantage
