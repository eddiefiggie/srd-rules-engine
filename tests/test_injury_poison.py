"""p. 197's Injury poison: the one delivery type the engine can observe (#141).

#141 held all five affliction shapes on one reading — *exposure is a narrative fact* — and
p. 197 contradicts it for this type outright:

> A creature that takes **Piercing or Slashing** damage from an object coated with the poison
> is exposed to its effects.

That is a damage-type condition, and this engine already resolves damage types. So Injury
needs no memory-port fact at all, while Contact and Ingested still do and Inhaled needs an
area. The other three stay unbuilt and named (R32).

Two clauses an implementation drops by building the exposure half and stopping:

* **A coated club delivers nothing.** Piercing *or Slashing*, and firing on any hit at all is
  the natural shortcut.
* **The coating is spent.** "The poison remains potent until **delivered through a wound** or
  washed off" — without that, one smeared dagger is venomous forever.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Ledger,
    Status,
    Weapon,
    attack_resolver,
    read,
)
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.core.poison import Delivery, Poison
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
from srd_rules_engine.memory.store import JsonMemoryStore

STRIKE = Rule(
    id="fixture-strike",
    summary="An attack.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented; the mechanism is what is under test.",
)
RULESET = load_fixture_ruleset("injury-poison", (STRIKE,))

DAGGER = Weapon(
    id="fixture:dagger",
    damage_dice=1,
    damage_sides=4,
    damage_type=DamageType.PIERCING,
    ability="dex",
)
CLUB = Weapon(
    id="fixture:club",
    damage_dice=1,
    damage_sides=4,
    damage_type=DamageType.BLUDGEONING,
    ability="str",
)

#: Ruleset data, as a weapon is. No SRD poison ships — p. 197's DCs and damage are content
#: that has not been verified entry by entry (#21).
VENOM = Poison(
    name="fixture venom", delivery=Delivery.INJURY, save_dc=11, rule_id="fixture-venom-effects"
)
#: The same numbers, delivered by a route the engine cannot see.
SMEARED = Poison(
    name="fixture unguent", delivery=Delivery.CONTACT, save_dc=11, rule_id="fixture-unguent-effects"
)


def _attacker(weapon: Weapon = DAGGER, poison: Poison | None = VENOM) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=13,
        abilities={"str": 14, "dex": 16},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        equipment=(Carried(weapon, Carriage.HELD, poison=poison),),
        weapon_proficiencies=frozenset({weapon.id}),
    )


def _encounter(attacker: Combatant | None = None) -> EncounterState:
    boar = Combatant(
        id="boar",
        name="Boar",
        hit_points=200,
        max_hit_points=200,
        armour_class=1,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(5, 0, 0),
    )
    return EncounterState.new([attacker or _attacker(), boar]).with_initiative(
        {"pc": 20, "boar": 5}
    )


def _hit(  # type: ignore[no-untyped-def]
    path: Path, state: EncounterState, *, seed: int = 3, weapon: Weapon = DAGGER
):
    path.mkdir(parents=True, exist_ok=True)
    adjudicator = Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )
    offered = read(state, "pc")
    attack = next(a for a in offered.actions if a.key == f"attack:{weapon.id}:boar")
    return adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=attack.key),
            rule_id=STRIKE.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )


# --- The exposure p. 197 states -----------------------------------------------------------


def test_piercing_damage_from_a_coated_weapon_compels_the_save(tmp_path: Path) -> None:
    """p. 197's sentence, end to end: a wound from a coated object exposes the creature, and
    the save reaches the loop as a debt the way every compelled save has since 0048."""
    ruling, state = _hit(tmp_path, _encounter())
    assert ruling.status is Status.RULED

    compelled = [e for e in ruling.effects if e.kind is EffectKind.SAVE_COMPELLED]
    assert len(compelled) == 1, [e.kind for e in ruling.effects]
    save = compelled[0].forced_save
    assert save is not None
    assert save.combatant_id == "boar"
    assert save.dc == 11, "the DC is the poison's, and the poison's is the ruleset's"
    assert save.ability == "con", "p. 197 compels a Constitution save for every poison"
    assert state.forced_saves_owed, "and the loop has a debt to roll"


def test_a_coated_club_delivers_nothing(tmp_path: Path) -> None:
    """p. 197 says Piercing **or Slashing**. Bludgeoning is neither, so a smeared club is a
    smeared club — and firing on any hit at all is the shortcut this is written against."""
    ruling, state = _hit(tmp_path, _encounter(_attacker(weapon=CLUB)), weapon=CLUB)

    assert not [e for e in ruling.effects if e.kind is EffectKind.SAVE_COMPELLED]
    assert not state.forced_saves_owed


def test_a_poison_of_another_delivery_type_is_not_delivered_by_a_wound(tmp_path: Path) -> None:
    """Contact poison smeared on a blade is still Contact poison. p. 197 exposes a creature to
    it by touch, and a wound is not a touch — the engine cannot see one, which is exactly why
    the other three types are unbuilt."""
    ruling, state = _hit(tmp_path, _encounter(_attacker(poison=SMEARED)))

    assert not [e for e in ruling.effects if e.kind is EffectKind.SAVE_COMPELLED]
    assert not state.forced_saves_owed


def test_an_uncoated_weapon_compels_nothing(tmp_path: Path) -> None:
    ruling, state = _hit(tmp_path, _encounter(_attacker(poison=None)))
    assert not [e for e in ruling.effects if e.kind is EffectKind.SAVE_COMPELLED]
    assert not state.forced_saves_owed


# --- "until delivered through a wound" -----------------------------------------------------


def test_delivery_spends_the_coating(tmp_path: Path) -> None:
    """p. 197: "The poison remains potent until **delivered through a wound** or washed off."

    Without this a single smeared dagger poisons every creature it ever hits, which is the
    rule an implementation drops by building the exposure half and stopping."""
    _, state = _hit(tmp_path, _encounter())

    (held,) = state.combatant("pc").equipment
    assert held.poison is None, "the dose went into the wound"


def test_a_miss_leaves_the_coating_on_the_blade(tmp_path: Path) -> None:
    """Both effects are conditioned on damage being taken, so a swing that lands nothing
    spends nothing. Seed 1 misses an armour class the attacker cannot reach."""
    armoured = EncounterState.new(
        [
            _attacker(),
            Combatant(
                id="boar",
                name="Boar",
                hit_points=200,
                max_hit_points=200,
                armour_class=30,
                abilities={"str": 12, "dex": 10},
                proficiency_bonus=2,
                position=Position(5, 0, 0),
            ),
        ]
    ).with_initiative({"pc": 20, "boar": 5})

    ruling, state = _hit(tmp_path, armoured, seed=1)

    assert not [e for e in ruling.effects if e.kind is EffectKind.SAVE_COMPELLED]
    (held,) = state.combatant("pc").equipment
    assert held.poison is not None, "nothing went through a wound, so nothing was spent"


def test_a_target_immune_to_the_damage_is_not_exposed(tmp_path: Path) -> None:
    """What `When.DAMAGE_TAKEN` is actually for, and the miss test does not reach it — a miss
    never runs the success branch at all.

    p. 197 exposes a creature that **takes** Piercing or Slashing damage. p. 17's Immunity is
    the whole difference between being hit and taking damage: a creature immune to Piercing
    takes none from a dagger, so nothing goes through the wound and there is no wound. That is
    0032 clause 2's reasoning, and the same shape #173 is about for Falling.
    """
    immune = EncounterState.new(
        [
            _attacker(),
            Combatant(
                id="boar",
                name="Boar",
                hit_points=200,
                max_hit_points=200,
                armour_class=1,
                abilities={"str": 12, "dex": 10},
                proficiency_bonus=2,
                position=Position(5, 0, 0),
                defences=Defences(immunities=frozenset({DamageType.PIERCING})),
            ),
        ]
    ).with_initiative({"pc": 20, "boar": 5})

    ruling, state = _hit(tmp_path, immune)

    assert not [e for e in ruling.effects if e.kind is EffectKind.SAVE_COMPELLED], (
        "the blow landed and the creature took nothing, so p. 197 exposes it to nothing"
    )
    (held,) = state.combatant("pc").equipment
    assert held.poison is not None, "and the dose is still on the blade"


# --- The three that stay unbuilt, named rather than omitted (R32) ---------------------------


def test_all_four_delivery_types_are_named() -> None:
    """An enum with one member would say the document has one delivery type, and a reader who
    cannot see the other three cannot tell a modelled rule from an unmodelled one."""
    assert {d.value for d in Delivery} == {"contact", "ingested", "inhaled", "injury"}


@pytest.mark.parametrize("delivery", [Delivery.CONTACT, Delivery.INGESTED, Delivery.INHALED])
def test_only_injury_is_deliverable_by_a_wound(delivery: Delivery) -> None:
    """p. 197 exposes the other three by a touch, a swallow and a cloud. None is a thing this
    engine observes, so none of them is delivered by damage — and saying so keeps the
    distinction where the document put it rather than in a comment."""
    poison = Poison(name="x", delivery=delivery, save_dc=10, rule_id="r")
    assert not poison.is_deliverable_by_a_wound
    assert not poison.delivers(DamageType.PIERCING)
