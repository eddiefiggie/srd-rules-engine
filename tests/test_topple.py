"""p. 90's Topple: a Constitution save on a hit, Prone on a failure (#321).

> **Topple.** If you hit a creature with this weapon, you can force the creature to make a
> Constitution saving throw (DC 8 plus the ability modifier used to make the attack roll and
> your Proficiency Bonus). On a failed save, the creature has the Prone condition.

Three things here are easy to get wrong, and the document rules out each in one clause:

* **The trigger is the hit, not the damage.** Vex and Slow say "and deal damage to it"; this
  and Sap say only "if you hit". A hit reduced to zero by Resistance still topples.
* **The DC uses the ability the attacker chose for *that* roll**, which a Finesse weapon
  leaves open (p. 89) and nothing records afterwards. That is why it is computed where the
  attack lands rather than where the save is rolled (0048).
* **The Proficiency Bonus is added unconditionally.** p. 89 conditions the *attack roll's*
  bonus on proficiency; p. 90's DC formula states no such condition. Inferring one across
  would be the rule value R31 forbids.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

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
    Weapon,
    attack_key,
    attack_resolver,
    load_ruleset,
)
from srd_rules_engine.core.adjudicate import Effect, EffectKind, Proposal
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.spellcasting import CONCENTRATION_RULE_ID
from srd_rules_engine.core.state import ForcedSave
from srd_rules_engine.core.topple import (
    TOPPLE_RULE_ID,
    TOPPLE_SAVE_ABILITY,
    topple_resolver,
    topple_rule,
    topple_save_dc,
)
from srd_rules_engine.loop import TurnLoop
from srd_rules_engine.loop.drivers import ScriptedDriver, drive
from srd_rules_engine.memory.store import JsonMemoryStore

#: p. 91 gives Topple to the Quarterstaff, Battleaxe, Lance, Maul and Trident. This is a
#: fixture, so its numbers are invented and labelled — only the property matters here.
MAUL = Weapon(id="fixture:maul", damage_dice=2, damage_sides=6, topple=True, hands_when_held=2)
#: A Finesse weapon with Topple, so "the ability modifier **used**" has two candidates. No
#: SRD weapon is both; the engine asserts no invariant refusing one, because p. 90 states
#: none — and the DC clause is only observable when the choice is real.
FOIL = Weapon(
    id="fixture:foil",
    damage_dice=1,
    damage_sides=8,
    ability="dex",
    finesse=True,
    topple=True,
    hands_when_held=1,
)
#: The same weapon without the property, so a difference is the property's doing.
CLUB = Weapon(id="fixture:club", damage_dice=1, damage_sides=6, hands_when_held=1)


def wielder(
    *,
    weapon: Weapon = MAUL,
    masters: bool = True,
    proficient: bool = True,
    strength: int = 16,
    dexterity: int = 12,
    proficiency_bonus: int = 2,
) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=15,
        abilities={"str": strength, "dex": dexterity},
        proficiency_bonus=proficiency_bonus,
        position=Position(0, 0, 0),
        hands=2,
        equipment=(Carried(weapon, Carriage.HELD),),
        weapon_proficiencies=frozenset({weapon.id}) if proficient else frozenset(),
        mastery_weapons=frozenset({weapon.id}) if masters else frozenset(),
    )


def boar(**kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "boar",
        "name": "Boar",
        "hit_points": 40,
        "max_hit_points": 40,
        "armour_class": 10,
        "abilities": {"str": 12, "dex": 10, "con": 14},
        "proficiency_bonus": 2,
        "position": Position(5, 0, 0),
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(actor: Combatant | None = None, target: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or wielder(), target or boar()]).with_initiative(
        {"pc": 20, "boar": 5}
    )


def propose(state: EncounterState, weapon: Weapon) -> Proposal:
    return attack_resolver()(
        state=state,
        declaration=Declaration(
            actor_id="pc",
            intent=Intent(action_key=attack_key(weapon.id, "boar")),
            rule_id="attack",
        ),
        facts={},
    )


def _effects(branch: tuple[object, ...]) -> list[Effect]:
    """The `Effect`s in a proposal branch.

    Filtered by type rather than by attribute: an attack's success branch also carries a
    `DamageDice`, which is a declared roll rather than an effect and has no `kind`.
    """
    return [e for e in branch if isinstance(e, Effect)]


def compelled(proposal: Proposal) -> ForcedSave:
    """The save the hit branch records, asserted to be exactly one."""
    saves = [
        e.forced_save for e in _effects(proposal.on_success) if e.kind is EffectKind.SAVE_COMPELLED
    ]
    assert len(saves) == 1, f"expected one compelled save, got {len(saves)}"
    assert saves[0] is not None
    return saves[0]


# --- the trigger -------------------------------------------------------------------------


def test_a_hit_with_a_topple_weapon_compels_a_constitution_save() -> None:
    """The property, in one assertion."""
    debt = compelled(propose(encounter(), MAUL))

    assert debt.combatant_id == "boar", "owed by the creature that was hit"
    assert debt.rule_id == TOPPLE_RULE_ID
    assert debt.ability == TOPPLE_SAVE_ABILITY == "con"


def test_a_weapon_without_topple_compels_nothing() -> None:
    """Shown to be the property's doing rather than the attack's."""
    state = encounter(wielder(weapon=CLUB))

    assert not [
        e for e in _effects(propose(state, CLUB).on_success) if e.kind is EffectKind.SAVE_COMPELLED
    ]


def test_topple_is_refused_to_a_wielder_with_no_feature_unlocking_it() -> None:
    """0047 clause 6: every mastery takes the gate, checked beside its own flag."""
    withheld = encounter(wielder(masters=False))

    assert not [
        e
        for e in _effects(propose(withheld, MAUL).on_success)
        if e.kind is EffectKind.SAVE_COMPELLED
    ]


def test_the_save_rides_on_the_hit_and_not_on_the_damage() -> None:
    """**"If you hit a creature"**, and p. 90 says nothing about damage — unlike Vex and Slow,
    which both say "and deal damage to it".

    The save is proposed in `on_success`, which is the branch the *roll* selects, so a hit
    whose damage is later reduced to nothing still compels it. Putting it where damage is
    applied would be reading Vex's clause into Topple.
    """
    proposal = propose(encounter(), MAUL)

    assert any(e.kind is EffectKind.SAVE_COMPELLED for e in _effects(proposal.on_success))
    assert not any(e.kind is EffectKind.SAVE_COMPELLED for e in _effects(proposal.on_failure)), (
        "a miss compels nothing"
    )


def test_a_hit_absorbed_by_immunity_still_compels_the_save() -> None:
    """The consequence of the clause above, in play. p. 90's trigger is the hit, so a target
    Immune to the weapon's damage type takes none and still has to keep its feet.

    This is the opposite of 0036 clause 5, where p. 179's "the damage taken" means an Immune
    creature owes nothing — two forced saves in one queue whose triggers differ, which is why
    each rule records its own debt rather than the queue deciding when one is owed.
    """
    tough = boar(defences=Defences(immunities=frozenset({DamageType.BLUDGEONING})))
    state = encounter(target=tough)

    assert compelled(propose(state, MAUL)).rule_id == TOPPLE_RULE_ID


# --- the DC ------------------------------------------------------------------------------


def test_the_dc_is_eight_plus_the_attacks_ability_and_the_proficiency_bonus() -> None:
    """p. 90's arithmetic. Strength 16 is +3, Proficiency Bonus 2, so DC 13."""
    debt = compelled(propose(encounter(), MAUL))

    assert debt.dc == 8 + 3 + 2 == 13
    assert topple_save_dc(3, 2) == 13


def test_the_dc_uses_the_ability_the_attack_actually_used() -> None:
    """**The clause that makes the DC unrecoverable afterwards** (0048).

    p. 89 lets a Finesse wielder use Strength or Dexterity, and p. 90 says "the ability
    modifier **used to make the attack roll**" — so the same creature swinging the same
    weapon sets a different DC depending on a choice nothing records once the attack is over.
    Here Dexterity 18 is +4 against Strength 8's -1.
    """
    nimble = wielder(weapon=FOIL, strength=8, dexterity=18)

    assert compelled(propose(encounter(nimble), FOIL)).dc == 8 + 4 + 2 == 14, "dex 18 is +4"


def test_a_negative_ability_modifier_lowers_the_dc_rather_than_being_clamped() -> None:
    """p. 90 states no floor, so the engine invents none (R31) — and the direction matters:
    a clamp at 8 would raise the DC, helping the attacker on the engine's own authority.

    **The total has to fall below the base for that to be observable.** Strength 6 is -2
    against a Proficiency Bonus of +2, which sums to exactly 8 — a clamp at 8 is invisible
    there, and the corruption proof for this clause said so by staying green. Strength 3 is
    -4, so the DC is 6 and a floor would show.
    """
    feeble = wielder(strength=3)
    assert feeble.modifier("str") == -4, "precondition"

    assert compelled(propose(encounter(feeble), MAUL)).dc == 8 - 4 + 2 == 6
    assert topple_save_dc(-4, 2) == 6, "the arithmetic, with no floor applied"


def test_the_proficiency_bonus_applies_even_without_weapon_proficiency() -> None:
    """p. 89 conditions the **attack roll's** Proficiency Bonus on proficiency with the
    weapon. p. 90's DC formula states no such condition — it says "your Proficiency Bonus"
    flatly — so a wielder with the mastery and without the proficiency sets the same DC.

    Uncomfortable, and the document's. Reading p. 89's condition across would be exactly the
    inferred rule value R31 forbids.
    """
    unschooled = wielder(proficient=False)

    assert compelled(propose(encounter(unschooled), MAUL)).dc == 13, "the same DC"


def test_the_dc_carries_its_own_derivation() -> None:
    """R30. A target number without its derivation is one the reader cannot check, and the
    loop that rolls this save has no way to rebuild the sentence."""
    basis = compelled(propose(encounter(), MAUL)).dc_basis

    assert "DC 13" in basis
    assert "+3" in basis and "+2" in basis, "both contributions are named"
    assert "p. 90" in basis


# --- the resolver ------------------------------------------------------------------------


def owed(state: EncounterState, dc: int = 13) -> EncounterState:
    return state.with_forced_save(
        ForcedSave(
            combatant_id="boar",
            rule_id=TOPPLE_RULE_ID,
            ability="con",
            dc=dc,
            dc_basis=f"DC {dc}, a fixture",
            label="makes a Constitution save or falls Prone",
        )
    )


def test_the_resolver_proposes_the_debts_save_and_applies_prone_on_a_failure() -> None:
    state = owed(encounter())
    proposal = topple_resolver()(
        state=state,
        declaration=Declaration(
            actor_id="boar",
            intent=Intent(improvised=True, label="makes a Constitution save"),
            rule_id=TOPPLE_RULE_ID,
        ),
        facts={},
    )

    assert proposal.test is not None
    assert proposal.test.target == 13
    assert proposal.on_success == (), "p. 90 states no consequence for a success"
    assert [e.condition for e in _effects(proposal.on_failure)] == [Condition.PRONE]


def test_the_resolver_refuses_a_debt_belonging_to_another_rule() -> None:
    """One queue serves every forced save since 0048, so the resolver checks that the debt in
    front of it is its own. Reached only if the loop and the rule have come apart, which is
    exactly when a silent mis-roll would be least visible."""
    state = encounter().with_forced_save(
        ForcedSave(
            combatant_id="boar",
            rule_id=CONCENTRATION_RULE_ID,
            ability="con",
            dc=10,
            dc_basis="a fixture",
            label="maintains Concentration",
        )
    )

    with pytest.raises(ValueError, match=r"not p\. 90's Topple"):
        topple_resolver()(
            state=state,
            declaration=Declaration(
                actor_id="boar",
                intent=Intent(improvised=True, label="makes a Constitution save"),
                rule_id=TOPPLE_RULE_ID,
            ),
            facts={},
        )


def test_the_resolver_refuses_when_nothing_is_owed() -> None:
    with pytest.raises(ValueError, match="owes no save"):
        topple_resolver()(
            state=encounter(),
            declaration=Declaration(
                actor_id="boar",
                intent=Intent(improvised=True, label="makes a Constitution save"),
                rule_id=TOPPLE_RULE_ID,
            ),
            facts={},
        )


# --- the queue -------------------------------------------------------------------------


def test_two_hits_owe_two_saves() -> None:
    """0036 clause 3's cardinality, which is what makes this the same mechanism as p. 179's
    Concentration save and is why one queue serves both (0048). A Multiattack landing twice
    with a Topple weapon compels two, and merging them would be a rule p. 90 does not give.
    """
    state = owed(owed(encounter(), dc=13), dc=11)

    assert [d.dc for d in state.forced_saves_owed] == [13, 11], "oldest first, kept apart"


def test_a_topple_debt_is_not_cleared_by_the_turn_advancing() -> None:
    """Per triggering instance, not per turn — the distinction 0036 clause 3 drew and the
    reason the queue is not `discharged`. A creature toppled on the attacker's turn still
    owes the save when its own turn arrives."""
    state = owed(encounter())

    assert state.advanced_turn().forced_saves_owed == state.forced_saves_owed


# --- the drain, which is where a skip would hide -----------------------------------------


def test_a_topple_save_is_rolled_for_a_creature_that_is_not_concentrating() -> None:
    """0048 clause 5, and the assertion the whole record turns on.

    The drain drops a **Concentration** debt for a creature no longer concentrating, because
    p. 179 compels that save *to maintain* Concentration and there is nothing left to
    maintain. Applying that test to every debt would silently drop every Topple save — almost
    every creature hit by a Maul is concentrating on nothing — and a compelled save that never
    happens is the exact failure class this product exists to make impossible. It leaves no
    trace in play either: the target simply stays upright.

    So the staleness check is keyed by `rule_id`, and this drives the real loop to say so.
    """
    state = owed(encounter())
    assert not state.combatant("boar").concentration.active, "precondition: nothing to maintain"

    loop = TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset((topple_rule(),)),
            resolvers={TOPPLE_RULE_ID: topple_resolver()},
            fact_types={},
            port=JsonMemoryStore(Path(mkdtemp()) / "memory.json"),
            ledger=Ledger.open(
                Path(mkdtemp()) / "ledger.jsonl",
                engine_version="t",
                catalogue_version=1,
                session_id="s",
            ),
            seed_source=lambda: 3,
        )
    )
    end = drive(loop.end_turn(state, "pc"), ScriptedDriver(narrations=["it happened"] * 8))

    assert [r.rule_id for r in end.rulings] == [TOPPLE_RULE_ID], "the save was rolled"
    assert end.state.forced_saves_owed == (), "and the debt discharged"
