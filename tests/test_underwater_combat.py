"""p. 16's Underwater Combat: three rules, and the third needed #224 (#446).

> **Impeded Weapons.** When making a **melee** attack roll with a weapon underwater, a
> creature that **lacks a Swim Speed** has Disadvantage on the attack roll **unless the
> weapon deals Piercing damage**. A **ranged** attack roll with a weapon underwater
> **automatically misses** a target beyond the weapon's normal range, and the attack roll has
> Disadvantage against a target **within** normal range.
>
> **Fire Resistance.** Anything underwater has Resistance to Fire damage.

The automatic miss was the blocker. It is neither thing `_out_of_range` produces — p. 90 gives
Disadvantage beyond normal range and **refuses** beyond long range, because a ruling for an
attack the rules forbid would be an outcome for something that never happened. p. 16's shot
**happens** and settles without a roll, which is #224's shape and got its kind with #448.
"""

from __future__ import annotations

from dataclasses import replace

from srd_rules_engine.core import (
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Weapon,
    attack_resolver,
    read,
)
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.position import Position, Speeds
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset

STRIKE = Rule(
    id="fixture-strike",
    summary="An attack.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented; the mechanism is what is under test.",
)
RULESET = load_fixture_ruleset("underwater", (STRIKE,))

CLUB = Weapon(
    id="fix:club", damage_dice=1, damage_sides=6, damage_type=DamageType.BLUDGEONING, ability="str"
)
SPEAR = Weapon(
    id="fix:spear", damage_dice=1, damage_sides=6, damage_type=DamageType.PIERCING, ability="str"
)
BOW = Weapon(
    id="fix:bow",
    damage_dice=1,
    damage_sides=6,
    melee=False,
    damage_type=DamageType.PIERCING,
    ability="dex",
    normal_range=20,
    long_range=200,
)


def _fighter(weapon: Weapon, *, swims: bool = False, x: int = 0) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=13,
        abilities={"str": 14, "dex": 14, "con": 10},
        proficiency_bonus=2,
        position=Position(x, 0, 0),
        equipment=(Carried(weapon, Carriage.HELD),),
        weapon_proficiencies=frozenset({weapon.id}),
        speeds=Speeds(walk=30, swim=30) if swims else Speeds(walk=30),
    )


def _scene(
    weapon: Weapon, *, underwater: bool, swims: bool = False, away: int = 5
) -> EncounterState:
    state = EncounterState.new(
        [
            _fighter(weapon, swims=swims),
            Combatant(
                id="eel",
                name="Eel",
                hit_points=40,
                max_hit_points=40,
                armour_class=10,
                abilities={"str": 12, "dex": 10, "con": 10},
                proficiency_bonus=2,
                position=Position(away, 0, 0),
            ),
        ]
    ).with_initiative({"pc": 20, "eel": 5})
    return replace(state, underwater=underwater)


def _propose(state, weapon: Weapon):  # type: ignore[no-untyped-def]
    offered = read(state, "pc")
    key = f"attack:{weapon.id}:eel"
    return attack_resolver()(
        state=state,
        declaration=Declaration(
            actor_id="pc",
            intent=Intent(action_key=key),
            rule_id=STRIKE.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
        facts={},
    )


# --- Impeded Weapons: the melee clause ------------------------------------------------------


def test_a_bludgeoning_weapon_underwater_has_disadvantage() -> None:
    """The base case: melee, no Swim Speed, not Piercing."""
    proposal = _propose(_scene(CLUB, underwater=True), CLUB)
    assert proposal.test is not None and proposal.test.has_disadvantage


def test_a_piercing_weapon_is_exempt() -> None:
    """p. 16: "unless the weapon deals Piercing damage". Read off the weapon's own damage
    type, statically, as p. 197's Injury poison reads it."""
    proposal = _propose(_scene(SPEAR, underwater=True), SPEAR)
    assert proposal.test is not None and not proposal.test.has_disadvantage


def test_a_swim_speed_exempts_the_melee_attacker() -> None:
    proposal = _propose(_scene(CLUB, underwater=True, swims=True), CLUB)
    assert proposal.test is not None and not proposal.test.has_disadvantage


def test_none_of_it_applies_on_dry_land() -> None:
    """The control. Every assertion here would pass on a rule that fired always."""
    proposal = _propose(_scene(CLUB, underwater=False), CLUB)
    assert proposal.test is not None and not proposal.test.has_disadvantage


# --- Impeded Weapons: the ranged clause -----------------------------------------------------


def test_a_ranged_attack_within_normal_range_has_disadvantage() -> None:
    """p. 16 gives the ranged clause no Swim Speed exemption — the speed is attached to the
    first sentence only, and carrying it across would help the swimmer by a rule the document
    does not state."""
    proposal = _propose(_scene(BOW, underwater=True, swims=True, away=10), BOW)
    assert proposal.test is not None and proposal.test.has_disadvantage


def test_beyond_normal_range_underwater_misses_automatically() -> None:
    """The clause that needed #224. Not Disadvantage, and not the refusal p. 90 earns beyond
    *long* range — the shot happens and its outcome is settled without a die."""
    proposal = _propose(_scene(BOW, underwater=True, away=50), BOW)

    assert proposal.test is None, "settled without a roll"
    (effect,) = proposal.outcome
    assert effect.kind is EffectKind.AUTOMATIC_FAILURE
    assert "p. 16" in effect.description
    assert any("without a die" in c for c in proposal.may_not_claim)


def test_the_automatic_miss_still_costs_what_the_shot_cost() -> None:
    """p. 16 **misses** the attack; it does not forbid it. So the action is still spent and
    the attack still counts as made — built by replacing the finished proposal rather than
    as a second construction, so none of those costs can drift."""
    proposal = _propose(_scene(BOW, underwater=True, away=50), BOW)

    kinds = {e.kind for e in proposal.always}
    assert EffectKind.ACTION_SPENT in kinds, "the shot was taken"


def test_beyond_normal_range_on_dry_land_is_only_disadvantage() -> None:
    """p. 90's rule, unchanged. The automatic miss is p. 16's and applies nowhere else."""
    proposal = _propose(_scene(BOW, underwater=False, away=50), BOW)

    assert proposal.test is not None, "p. 90 rolls it"
    assert proposal.test.has_disadvantage


# --- Fire Resistance -------------------------------------------------------------------------


def test_anything_underwater_resists_fire() -> None:
    """p. 16, and it is read at the point of damage rather than written onto the creature —
    it is a fact about where the fight is, not about the creature."""
    wet = _scene(CLUB, underwater=True)
    dry = _scene(CLUB, underwater=False)

    assert wet.damage_after_defences("eel", 10, DamageType.FIRE).amount == 5
    assert dry.damage_after_defences("eel", 10, DamageType.FIRE).amount == 10


def test_it_resists_only_fire() -> None:
    wet = _scene(CLUB, underwater=True)
    assert wet.damage_after_defences("eel", 10, DamageType.SLASHING).amount == 10


def test_a_creature_already_resistant_gains_nothing() -> None:
    """p. 17: Resistance "is not cumulative". `Defences` holds sets, so that holds by
    construction rather than by a check."""
    from srd_rules_engine.core.damage import Defences

    wet = _scene(CLUB, underwater=True)
    fireproof = replace(
        wet,
        combatants=tuple(
            replace(c, defences=Defences(resistances=frozenset({DamageType.FIRE})))
            if c.id == "eel"
            else c
            for c in wet.combatants
        ),
    )
    assert fireproof.damage_after_defences("eel", 10, DamageType.FIRE).amount == 5
