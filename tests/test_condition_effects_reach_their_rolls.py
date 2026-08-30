"""Three condition effects that were modelled in data and read by nothing (#357, 0058).

`ConditionEffects` is transcribed from the glossary field by field, and seven of its fields were
populated and never read. Three are built here — the two that change **outcomes** rather than
probabilities, plus the condition Immunity beside one of them — and four are disclosed.

The guard that found them is `test_every_condition_effect_is_read_or_disclosed`, below.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from srd_rules_engine.core import Combatant, Condition, EncounterState
from srd_rules_engine.core.conditions import (
    AUTO_CRITICAL_FEET,
    EFFECTS,
    ConditionEffects,
    Conditions,
)
from srd_rules_engine.core.d20 import Critical, D20Test, TestKind, resolve
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.core.position import Position

ORIGIN = Position(0, 0, 0)


def creature(cid: str = "pc", **overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 40,
        "max_hit_points": 40,
        "armour_class": 10,
        "abilities": {"str": 12, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "position": ORIGIN,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(*people: Combatant) -> EncounterState:
    crowd = people or (creature(),)
    return EncounterState.new(list(crowd)).with_initiative(
        {c.id: 20 - i for i, c in enumerate(crowd)}
    )


# --- The guard that found all seven ------------------------------------------------------------


def test_every_condition_effect_is_read_or_disclosed() -> None:
    """A field on a rule-data structure that nothing reads is a rule modelled and not applied.

    #356's guard, in the shape #334 taught: walk the AST of every `core` module, collect
    attribute **reads** of `ConditionEffects` field names, and compare against the dataclass.
    Run against `main` before this change it returned seven; every one is now either read by
    something or named in `unenforced_clauses`.

    **Reads, not keyword arguments.** `ConditionEffects(cannot_speak=True)` in the `EFFECTS`
    table is the field being *populated*, which is exactly the state this is looking for — a
    walk that counted it would find nothing wrong with any of the seven.
    """
    fields = {f.name for f in dataclasses.fields(ConditionEffects)}
    read: set[str] = set()
    for path in pathlib.Path("src/srd_rules_engine").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in fields
                and isinstance(node.ctx, ast.Load)
            ):
                read.add(node.attr)

    disclosed = {c for effects in EFFECTS.values() for c in effects.unenforced_clauses}
    #: Each unread field, and the clause that names the gap instead.
    named: dict[str, str] = {
        "cannot_speak": "cannot-speak",
        "initiative": "initiative-advantage-not-applied",
        "auto_fail_checks_requiring_sight": "checks-requiring-sight-not-identified",
        "auto_fail_checks_requiring_hearing": "checks-requiring-hearing-not-identified",
    }
    unaccounted = sorted(f for f in fields - read if named.get(f) not in disclosed)

    assert not unaccounted, (
        f"these `ConditionEffects` fields are populated from the glossary and read by "
        f"nothing, and no disclosure names the gap: {unaccounted}. A field nothing reads is a "
        "rule modelled and not applied — build it, or name it in `unenforced_clauses`."
    )
    assert set(named) <= fields, "the allowlist names a field that no longer exists"


# --- p. 186 and p. 191: a hit is a Critical Hit ------------------------------------------------


@pytest.mark.parametrize("condition", [Condition.PARALYZED, Condition.UNCONSCIOUS])
def test_a_hit_within_five_feet_is_critical(condition: Condition) -> None:
    """ "Any attack roll that hits you is a Critical Hit if the attacker is within 5 feet."

    Asserted on an ordinary hit — a total that beats the AC on a die that is neither a 20 nor
    a 1 — because a natural 20 would be critical anyway and would prove nothing.
    """
    test = D20Test(kind=TestKind.ATTACK, target=5, target_basis="AC 5", critical_on_hit=True)
    result = resolve(test, seed=5)
    assert result.used not in (1, 20), "an ordinary die, or this asserts nothing"
    assert result.succeeded
    assert result.critical is Critical.HIT
    assert EFFECTS[condition].auto_critical_within_5_feet, "and the condition sets the flag"


def test_a_miss_is_not_upgraded() -> None:
    """p. 186 says "any attack roll that **hits**". A miss is not a hit to upgrade, and a
    natural 1 misses regardless (p. 7)."""
    missed = resolve(
        D20Test(kind=TestKind.ATTACK, target=30, target_basis="AC 30", critical_on_hit=True),
        seed=5,
    )
    assert not missed.succeeded
    assert missed.critical is Critical.NONE


def test_without_the_flag_an_ordinary_hit_stays_ordinary() -> None:
    """The negative case for the two above."""
    plain = resolve(D20Test(kind=TestKind.ATTACK, target=5, target_basis="AC 5"), seed=5)
    assert plain.succeeded
    assert plain.critical is Critical.NONE


def test_the_five_feet_is_the_conditions_number_not_the_attackers_reach() -> None:
    """pp. 186, 191 state the distance themselves, and p. 90's Reach weapons extend a reach to
    10 feet without extending this."""
    assert AUTO_CRITICAL_FEET == 5


def test_the_attack_path_asks_both_halves_of_the_sentence() -> None:
    """The condition **and** the distance, through `core.combat`'s own helper rather than
    through `resolve` — the tests above prove the die honours the flag, and this proves the
    flag is set for the right reason."""
    from srd_rules_engine.core.combat import _hit_is_automatically_critical

    limp = creature("ogre", conditions=Conditions(applied=frozenset({Condition.PARALYZED})))
    assert _hit_is_automatically_critical(creature(), limp), "adjacent and paralyzed"

    far = creature("ogre", position=Position(10, 0, 0), conditions=limp.conditions)
    assert not _hit_is_automatically_critical(creature(), far), "paralyzed and ten feet away"

    upright = creature("ogre")
    assert not _hit_is_automatically_critical(creature(), upright), "adjacent and upright"


def test_an_unmeasurable_distance_does_not_upgrade_the_hit() -> None:
    """0030 clause 1. A Critical Hit doubles dice, so granting one on a distance the engine
    could not measure manufactures damage; withholding it only fails to double."""
    from srd_rules_engine.core.combat import _hit_is_automatically_critical

    limp = creature(
        "ogre", position=None, conditions=Conditions(applied=frozenset({Condition.PARALYZED}))
    )
    assert not _hit_is_automatically_critical(creature(), limp)


# --- p. 186: Resistance to all damage -----------------------------------------------------------


def test_a_petrified_creature_resists_everything() -> None:
    """ "You have Resistance to all damage." `Defences.resists_all` already expressed it and no
    condition had ever set it — which is exactly the shape #357 is about."""
    petrified = creature(conditions=Conditions(applied=frozenset({Condition.PETRIFIED})))
    state = encounter(petrified)
    assert state.damage_after_defences("pc", 10, DamageType.SLASHING).amount == 5


def test_an_upright_creature_takes_it_all() -> None:
    assert encounter().damage_after_defences("pc", 10, DamageType.SLASHING).amount == 10


def test_the_condition_composes_with_what_the_creature_already_had() -> None:
    """A creature that is both Petrified and Immune to Fire keeps the Immunity — the flag is
    added to its defences rather than replacing them."""
    both = creature(
        conditions=Conditions(applied=frozenset({Condition.PETRIFIED})),
        defences=Defences(immunities=frozenset({DamageType.FIRE})),
    )
    state = encounter(both)
    assert state.damage_after_defences("pc", 10, DamageType.FIRE).amount == 0
    assert state.damage_after_defences("pc", 10, DamageType.COLD).amount == 5


def test_the_resistance_reaches_the_damage_that_is_actually_applied() -> None:
    """`with_damage` is written in terms of `damage_after_defences`, so the reported number and
    the applied one cannot disagree — asserted rather than assumed."""
    petrified = creature(conditions=Conditions(applied=frozenset({Condition.PETRIFIED})))
    after = encounter(petrified).with_damage("pc", 10, damage_type=DamageType.SLASHING)
    assert after.combatant("pc").hit_points == 35


# --- p. 186: Immunity to the Poisoned condition --------------------------------------------------


def test_a_petrified_creature_cannot_be_poisoned() -> None:
    """ "You have Immunity to the Poisoned condition." p. 183: an Immunity means the condition
    "doesn't affect you in any way", so the application is a no-op rather than an error — a
    rule that tries to poison a statue is not a caller's mistake."""
    petrified = creature(conditions=Conditions(applied=frozenset({Condition.PETRIFIED})))
    state = encounter(petrified)
    after = state.with_condition("pc", Condition.POISONED)
    assert Condition.POISONED not in after.combatant("pc").conditions.held
    # The same state object, not an equal one: a no-op that rebuilt the encounter would move
    # the generation and make a read token stale for a change that did not happen (R19).
    assert after is state


def test_the_immunity_is_to_Poisoned_and_not_to_everything() -> None:
    """The negative case. p. 186 names one condition, and a statue can still be Frightened."""
    petrified = creature(conditions=Conditions(applied=frozenset({Condition.PETRIFIED})))
    after = encounter(petrified).with_condition("pc", Condition.FRIGHTENED)
    assert Condition.FRIGHTENED in after.combatant("pc").conditions.held


def test_an_ordinary_creature_is_poisoned_normally() -> None:
    after = encounter().with_condition("pc", Condition.POISONED)
    assert Condition.POISONED in after.combatant("pc").conditions.held
