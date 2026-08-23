"""Enough of combat to run one fight: turn order, attacks, damage, and dropping to 0.

R12 in full covers reactions, opportunity attacks, and the whole action economy. This is
the slice's share of it, and the rest is named as later work rather than stubbed here.

Two things in this module are machinery rather than content, which is what lets them
exist while [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3) — the official
document this project verifies against — is still open:

- **Initiative orders combatants and nothing more.** Which ability the modifier comes from
  is a rule with a section citation, so it is a *parameter* rather than a constant here.
- **An attack is the d20 test with the target's armour value as its target number.** That
  is R11 doing its job: the kind changes where the number came from, not how the roll
  resolves.

What a weapon *is* stays outside: `Weapon` is a shape a ruleset fills in, and no weapon
list ships in this module. A table of longswords compiled from memory would be exactly the
inferred rule value R31 forbids, and it would be indistinguishable from a verified one
once it was inside a finished ruling.

**The resolver declares damage; it never states a total.** It returns `DamageDice`, and
the engine rolls it from the same seed as the attack. A resolver handing back
`Effect(amount=7)` would be a caller supplying a roll — the thing R4 exists to make
impossible — and it would also break replay in the quiet direction, reproducing the hit
and not the damage, which looks like it worked.

**A Ruling's effects are a record, not an instruction.** Nothing public applies them: the
adjudication entry point applies effects itself and returns the state it left behind, so
there is no second way to apply the same Ruling and therefore no way to apply it twice.

Criticals are deliberately absent. A natural 20 means something specific in the SRD, and
that meaning is a rule with a citation rather than machinery — the primitive already
returns the raw die, so whatever lands criticals has what it needs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from srd_rules_engine.core.adjudicate import (
    DamageDice,
    Declaration,
    Proposal,
    Resolver,
)
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind, roll
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import attack_target
from srd_rules_engine.core.state import EncounterState

INITIATIVE_DIE = 20


@dataclass(frozen=True)
class Weapon:
    """What an attack needs. A ruleset supplies it; this module ships no weapon list."""

    name: str
    damage_dice: int
    damage_sides: int
    ability: str = "str"
    proficient: bool = True
    #: A flat bonus that reaches **both** rolls. Berserker Axe (Magic Items, p. 213) is
    #: the inventory's exemplar: "a +1 bonus to attack rolls and damage rolls made with
    #: this magic weapon". Applying it to only one of the two is the mistake worth
    #: guarding, because an attack-only bonus is invisible in every hit that lands.
    bonus: int = 0


def initiative_order(
    state: EncounterState, *, seed: int, ability: str = "dex"
) -> Mapping[str, int]:
    """Roll initiative for every combatant, deterministically from one seed.

    Returned rather than applied, because applying it is `EncounterState.with_initiative`
    and that is the only thing allowed to move the generation.
    """
    faces = roll(seed, count=len(state.combatants), sides=INITIATIVE_DIE)
    return {
        combatant.id: face + combatant.modifier(ability)
        for combatant, face in zip(state.combatants, faces, strict=True)
    }


def attack_resolver(weapon: Weapon) -> Resolver:
    """Build the resolver for attacks made with this weapon.

    A closure rather than a registry entry: a weapon is ruleset data, and binding a table
    of them here would make the engine carry rule values it cannot verify.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        target_id = _target_of(declaration)
        target = state.combatant(target_id)
        actor = state.combatant(declaration.actor_id)
        ability = actor.modifier(weapon.ability)

        modifiers = [Modifier(source=f"ability:{weapon.ability}", value=ability)]
        if weapon.proficient:
            modifiers.append(Modifier(source="proficiency", value=actor.proficiency_bonus))
        if weapon.bonus:
            modifiers.append(Modifier(source=f"{weapon.name} bonus", value=weapon.bonus))

        return Proposal(
            test=D20Test(
                kind=TestKind.ATTACK,
                target=target.armour_class,
                target_basis=f"armour class {target.armour_class}, worn by {target.name}",
                modifiers=tuple(modifiers),
            ),
            on_success=(
                DamageDice(
                    target_id=target_id,
                    count=weapon.damage_dice,
                    sides=weapon.damage_sides,
                    # The same bonus, on the other roll. p. 213 says "attack rolls **and**
                    # damage rolls", so a weapon bonus reaching only the attack would be
                    # half a rule — and the half nobody notices.
                    modifier=ability + weapon.bonus,
                    source=weapon.name,
                ),
            ),
            citations=(f"weapon:{weapon.name}",),
            may_claim=(f"that the attack on {target.name} resolved as the roll says",),
            may_not_claim=(
                f"that {target.name} is dead, unless its hit points reached 0",
                "any damage number other than the one the Ruling carries",
            ),
        )

    return resolve


def _target_of(declaration: Declaration) -> str:
    """Read the target from the structured intent — never from the free-text label."""
    target_id = attack_target(declaration.intent.action_key)
    if target_id is None:
        raise ValueError(
            f"{declaration.intent.action_key!r} is not an attack. The target is read from "
            "the action key the read surface issued, which is what the token commits to"
        )
    return target_id
