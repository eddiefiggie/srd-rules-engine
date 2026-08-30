"""p. 190's Unarmed Strike, and the half of p. 177 that went missing (#267).

p. 177 allows "one attack roll **with a weapon or an Unarmed Strike**". #258 made an attack an
offer *per held weapon*, which is right for the first half and silently dropped the second — a
creature that lost its sword was offered nothing at all. This is that half.

Two things here are easy to get wrong:

* **The Proficiency Bonus is unconditional.** p. 89 adds it only "if you have proficiency
  with" the weapon; p. 190 states it flat, with no proficiency to have. So this is a second
  bonus rule beside the weapon path rather than a case of it.
* **The damage is not a die.** "Bludgeoning damage equal to 1 plus your Strength modifier" —
  an implementation reaching for `DamageDice` because every other attack uses one would be
  inventing a roll the rules do not call for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    UNARMED_STRIKE_ID,
    Adjudicator,
    Combatant,
    DamageType,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Ledger,
    Status,
    attack_key,
    load_ruleset,
    read,
    unarmed_strike_resolver,
    unarmed_strike_rule,
)
from srd_rules_engine.core.d20 import TestKind
from srd_rules_engine.core.position import Position
from srd_rules_engine.memory.store import JsonMemoryStore

RULESET = load_ruleset((unarmed_strike_rule(),))


def brawler(strength: int = 16, **overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": strength, "dex": 12},
        "proficiency_bonus": 3,
        "is_player_character": True,
        "position": Position(0, 0, 0),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


#: Inside p. 190's five feet, so the strike is offered by default.
ADJACENT = Position(5, 0, 0)


def boar(at: Position = ADJACENT) -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=10,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=at,
    )


def encounter(actor: Combatant | None = None, target: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or brawler(), target or boar()]).with_initiative(
        {"pc": 20, "boar": 5}
    )


def build(path: Path, *, seed: int = 2) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={UNARMED_STRIKE_ID: unarmed_strike_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def strike(state: EncounterState, target: str = "boar") -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key(UNARMED_STRIKE_ID, target)),
        rule_id=UNARMED_STRIKE_ID,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def seed_that(hits: bool, tmp_path: Path) -> int:
    """The first seed whose strike lands, or misses. Found, never hardcoded."""
    state = encounter()
    for candidate in range(500):
        ruling, _ = build(tmp_path / f"p{candidate}", seed=candidate).adjudicate(
            state, strike(state)
        )
        assert ruling.result is not None
        if ruling.result.succeeded is hits:
            return candidate
    raise AssertionError("no seed below 500 produced the wanted outcome")


# --- The half that was missing --------------------------------------------------------------


def test_a_creature_with_empty_hands_is_offered_an_attack() -> None:
    """#267, and the regression #258 shipped. p. 177: "one attack roll with a weapon **or an
    Unarmed Strike**." Offering per held weapon offered only the first half, so a creature
    that dropped its sword could not act against an enemy at all."""
    empty_handed = brawler()
    assert empty_handed.weapons_held == (), "precondition: nothing in hand"

    offered = {a.key for a in read(encounter(empty_handed), "pc").actions}
    assert attack_key(UNARMED_STRIKE_ID, "boar") in offered


def test_it_is_offered_beside_a_weapon_rather_than_instead_of_one() -> None:
    """p. 177 offers a choice, so holding a sword does not take the fists away."""
    from srd_rules_engine.core.equipment import Carriage, Carried, Weapon

    blade = Weapon(id="fixture:blade", damage_dice=1, damage_sides=6, hands_when_held=1)
    armed = brawler(hands=2, equipment=(Carried(blade, Carriage.HELD),))

    offered = {a.key for a in read(encounter(armed), "pc").actions}
    assert attack_key(UNARMED_STRIKE_ID, "boar") in offered
    assert attack_key(blade.id, "boar") in offered


def test_it_reaches_five_feet_and_no_further() -> None:
    """p. 190: "a target **within 5 feet of you**". The entry names its own distance, and
    p. 186 defers to it — "a reach of 5 feet **unless a rule says otherwise**"."""
    close = encounter(target=boar(Position(5, 0, 0)))
    far = encounter(target=boar(Position(10, 0, 0)))

    assert attack_key(UNARMED_STRIKE_ID, "boar") in {a.key for a in read(close, "pc").actions}
    assert attack_key(UNARMED_STRIKE_ID, "boar") not in {a.key for a in read(far, "pc").actions}


# --- p. 190's Damage option ------------------------------------------------------------------


def test_the_proficiency_bonus_is_unconditional(tmp_path: Path) -> None:
    """The difference from a weapon, and the reason this is its own resolver. p. 89 adds the
    bonus "if you have proficiency with" the weapon; p. 190 states it flat — there is no
    proficiency in fists to have, so a creature with an empty `weapon_proficiencies` still
    gets it."""
    state = encounter()
    assert state.combatant("pc").weapon_proficiencies == frozenset(), "precondition"

    ruling, _ = build(tmp_path).adjudicate(state, strike(state))
    assert ruling.result is not None
    assert {m.source for m in ruling.result.modifiers} == {"ability:str", "proficiency"}
    assert dict((m.source, m.value) for m in ruling.result.modifiers) == {
        "ability:str": 3,
        "proficiency": 3,
    }


def test_the_damage_is_one_plus_strength_and_is_not_rolled(tmp_path: Path) -> None:
    """p. 190: "Bludgeoning damage equal to 1 plus your Strength modifier." Flat. An
    implementation reaching for `DamageDice` because every other attack uses one would be
    inventing a roll the rules do not call for (R4, 0027 clause 6's direction)."""
    ruling, _ = build(tmp_path / "hit", seed=seed_that(True, tmp_path)).adjudicate(
        encounter(), strike(encounter())
    )
    damage = [e for e in ruling.effects if e.kind is EffectKind.DAMAGE]
    assert [e.amount for e in damage] == [4], "1 + 3 for a Strength of 16"
    assert damage[0].damage_type is DamageType.BLUDGEONING


def test_a_feeble_striker_deals_no_negative_damage(tmp_path: Path) -> None:
    """p. 190 states no floor, and 1 plus a Strength modifier of -3 is -2. Negative damage is
    healing, which the document neither states nor contemplates — so it floors at 0, which is
    0030 clause 1's direction: the reading that cannot manufacture an outcome."""
    feeble = brawler(strength=4)
    assert feeble.modifier("str") == -3, "precondition"

    state = encounter(feeble)
    ruling, after = build(tmp_path / "weak", seed=seed_that(True, tmp_path)).adjudicate(
        state, strike(state)
    )
    damage = [e for e in ruling.effects if e.kind is EffectKind.DAMAGE]
    if damage:
        assert damage[0].amount == 0
    assert after.combatant("boar").hit_points <= state.combatant("boar").hit_points


def test_it_is_an_attack_roll_against_armour_class(tmp_path: Path) -> None:
    ruling, _ = build(tmp_path).adjudicate(encounter(), strike(encounter()))
    assert ruling.result is not None
    assert ruling.result.kind is TestKind.ATTACK
    assert ruling.result.target == 10


def test_it_costs_the_action(tmp_path: Path) -> None:
    """p. 177 makes it one of the Attack action's options, so it is charged like the other."""
    from srd_rules_engine.core.actions import ActionKind

    _, after = build(tmp_path).adjudicate(encounter(), strike(encounter()))
    assert not after.combatant("pc").actions.available(ActionKind.ACTION)


def test_a_declaration_naming_a_weapon_is_refused(tmp_path: Path) -> None:
    """The resolver reads its own key, so a declaration routed here under a weapon's key is a
    mismatch rather than something to interpret."""
    state = encounter()
    wrong = Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key("fixture:blade", "boar")),
        rule_id=UNARMED_STRIKE_ID,
    )
    with pytest.raises(ValueError, match="not an Unarmed Strike"):
        unarmed_strike_resolver()(state=state, declaration=wrong, facts={})


# --- R32: the two options this does not offer ------------------------------------------------


def test_grapple_and_shove_are_disclosed_rather_than_approximated(tmp_path: Path) -> None:
    """p. 190 offers three effects and this engine offers one. Grapple and Shove both turn on
    "the target is no more than one size larger than you", and nothing has a `Size` (#259) —
    so offering them would decide a condition the document states.

    The bounds say so, because a narrator told only that a strike happened would have no way
    to know the other two were never on the table."""
    ruling, _ = build(tmp_path).adjudicate(encounter(), strike(encounter()))
    assert ruling.status is Status.RULED
    assert any("grappled or shoved" in claim for claim in ruling.bounds.may_not)


def test_the_grapple_and_shove_dependency_is_named_in_the_module() -> None:
    """A prose disclosure, guarded — this repository has watched three of them decay.

    It pointed at #259 while a `Size` was what Grapple and Shove waited on. 0051 built one,
    so the wait moved to the effects themselves and the pointer moved with it. A guard left
    naming a closed issue is the decay it exists to catch.
    """
    module = (
        Path(__file__).resolve().parents[1] / "src" / "srd_rules_engine" / "core" / "combat.py"
    ).read_text()
    assert "#335" in module, "the issue Grapple and Shove now wait on is no longer named"
