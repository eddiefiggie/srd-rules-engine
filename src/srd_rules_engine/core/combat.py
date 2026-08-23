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
    Effect,
    EffectKind,
    Proposal,
    Resolver,
)
from srd_rules_engine.core.d20 import Advantage, D20Test, Modifier, TestKind, roll
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.position import distance_feet, within
from srd_rules_engine.core.read_surface import attack_target
from srd_rules_engine.core.rules import Verification, VerificationState
from srd_rules_engine.core.state import Combatant, EncounterState

INITIATIVE_DIE = 20

#: R31. `HEAVY_SCORE_THRESHOLD` is a rule value, not machinery, so it carries what it was
#: checked against. A bare 13 in this module would read exactly like a verified one, which
#: is what `test_no_weapon_list_ships_in_this_module` exists to prevent.
WEAPON_PROPERTY_VERIFICATION = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Equipment ("Properties" -> Finesse, Heavy, Versatile), pp. 89-90; '
        '("Mastery Properties" -> Graze), p. 90'
    ),
    date="2026-08-23",
)

#: p. 89: Heavy names a *score* of 13, not a modifier. Comparing modifiers would put the
#: boundary in a different place.
HEAVY_SCORE_THRESHOLD = 13


@dataclass(frozen=True)
class Weapon:
    """What an attack needs. A ruleset supplies it; this module ships no weapon list."""

    name: str
    damage_dice: int
    damage_sides: int
    ability: str = "str"
    proficient: bool = True
    #: Melee or Ranged (p. 89). Heavy reads a different ability score for each.
    melee: bool = True
    damage_type: DamageType | None = None
    #: Finesse (p. 89): "use your choice of your Strength or Dexterity modifier for the
    #: attack **and** damage rolls. You must use the same modifier for both rolls." The
    #: choice is the wielder's and arrives as `ability`; what the engine holds is the
    #: constraint — a Finesse weapon may use either, anything else may not, and whichever
    #: is chosen reaches both rolls.
    finesse: bool = False
    #: Heavy (p. 89): Disadvantage unless the relevant score is at least 13.
    heavy: bool = False
    #: Versatile (p. 90): the damage die when "used with two hands to make a melee attack".
    versatile_sides: int | None = None
    wielded_two_handed: bool = False
    #: Graze (p. 90), a mastery property: damage on a miss equal to the ability modifier.
    graze: bool = False
    #: Range (p. 90): "The first is the weapon's normal range in feet, and the second is
    #: the weapon's long range." Ranged weapons only; a melee weapon uses the wielder's
    #: reach instead.
    normal_range: int | None = None
    long_range: int | None = None
    #: A flat bonus that reaches **both** rolls. Berserker Axe (Magic Items, p. 213) is
    #: the inventory's exemplar: "a +1 bonus to attack rolls and damage rolls made with
    #: this magic weapon". Applying it to only one of the two is the mistake worth
    #: guarding, because an attack-only bonus is invisible in every hit that lands.
    bonus: int = 0

    def __post_init__(self) -> None:
        if self.finesse and self.ability not in ("str", "dex"):
            raise ValueError(
                f"a Finesse weapon uses Strength or Dexterity, not {self.ability!r} — "
                "p. 89 offers the choice between those two and no others"
            )
        if self.versatile_sides is not None and not self.melee:
            raise ValueError(
                "Versatile is a melee property: it applies to two-handed melee attacks"
            )
        if (self.normal_range is None) != (self.long_range is None):
            raise ValueError("Range lists two numbers (p. 90): a normal range and a long range")
        if self.normal_range is not None and self.long_range is not None:
            if self.long_range < self.normal_range:
                raise ValueError("a weapon's long range is not shorter than its normal range")
            if self.melee:
                raise ValueError("Range is a ranged-weapon property; a melee weapon uses reach")

    @property
    def sides_in_use(self) -> int:
        """The damage die this attack rolls.

        p. 90: a Versatile weapon "deals that damage when used with two hands to make a
        melee attack". Both halves are conditions — a versatile weapon wielded in one hand
        rolls its ordinary die.
        """
        if self.versatile_sides is not None and self.wielded_two_handed and self.melee:
            return self.versatile_sides
        return self.damage_sides

    def heavy_disadvantage(self, scores: Mapping[str, int]) -> bool:
        """p. 89: Disadvantage "if it's a Melee weapon and your Strength score isn't at
        least 13 or if it's a Ranged weapon and your Dexterity score isn't at least 13".

        The *score*, not the modifier — 13 is the threshold the document names, and a
        modifier comparison would put the boundary in a different place.
        """
        if not self.heavy:
            return False
        required = "str" if self.melee else "dex"
        return scores.get(required, 10) < HEAVY_SCORE_THRESHOLD


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

        beyond_normal = _out_of_range(weapon, actor, target)
        attacker_state = actor.conditions.own_attack_rolls(target_id=target_id)
        defender_state = target.conditions.attack_rolls_against(
            attacker=actor.position, target=target.position
        )
        # p. 181: while Dodging, attacks against you have Disadvantage. It reaches the same
        # pair of flags as everything else, so it cancels against Advantage rather than
        # accumulating beside it.
        dodging = target.is_dodging

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
                # Heavy (p. 89). The disadvantage is a property of the weapon in these
                # hands, so it is decided here rather than asked of the caller.
                # Heavy (p. 89), or attacking beyond a ranged weapon's normal range
                # (p. 90). Both are Disadvantage and they do not stack — the d20 takes a
                # single flag, which is the cancellation rule holding by construction.
                has_disadvantage=(
                    weapon.heavy_disadvantage(actor.abilities)
                    or beyond_normal
                    or attacker_state is Advantage.DISADVANTAGE
                    or defender_state is Advantage.DISADVANTAGE
                    or dodging
                ),
                # Conditions on either side reach the same pair of flags, so the
                # cancellation rule (p. 8) resolves them exactly as it resolves any other
                # pair of circumstances rather than through a second mechanism.
                has_advantage=(
                    attacker_state is Advantage.ADVANTAGE or defender_state is Advantage.ADVANTAGE
                ),
            ),
            on_success=(
                DamageDice(
                    target_id=target_id,
                    count=weapon.damage_dice,
                    # Versatile (p. 90) selects the die; the ability modifier is whichever
                    # one Finesse let the wielder choose, and it reaches both rolls.
                    sides=weapon.sides_in_use,
                    damage_type=weapon.damage_type,
                    # The same bonus, on the other roll. p. 213 says "attack rolls **and**
                    # damage rolls", so a weapon bonus reaching only the attack would be
                    # half a rule — and the half nobody notices.
                    modifier=ability + weapon.bonus,
                    source=weapon.name,
                ),
            ),
            # Graze (p. 90): "If your attack roll with this weapon misses a creature, you
            # can deal damage to that creature equal to the ability modifier you used to
            # make the attack roll." The same modifier, and the weapon's own damage type.
            on_failure=_graze(weapon, target_id, ability),
            citations=(f"weapon:{weapon.name}",),
            may_claim=(f"that the attack on {target.name} resolved as the roll says",),
            may_not_claim=(
                f"that {target.name} is dead, unless its hit points reached 0",
                "any damage number other than the one the Ruling carries",
            ),
        )

    return resolve


def _out_of_range(weapon: Weapon, actor: Combatant, target: Combatant) -> bool:
    """Whether the attack is beyond normal range, refusing one beyond long range.

    p. 90: "When attacking a target beyond normal range, you have Disadvantage on the
    attack roll. You can't attack a target beyond the long range." The second sentence is
    not a penalty, so it is refused rather than resolved — a ruling for an attack the rules
    forbid would be an outcome for something that never happened.

    A melee weapon reaches as far as its wielder does (p. 186). An encounter tracking no
    positions cannot answer the question at all, and says so rather than assuming.
    """
    if actor.position is None or target.position is None:
        return False

    if weapon.normal_range is None:
        if not within(actor.position, target.position, actor.reach):
            raise ValueError(
                f"{target.name} is {distance_feet(actor.position, target.position)} feet "
                f"away and {actor.name} has a reach of {actor.reach} feet"
            )
        return False

    assert weapon.long_range is not None
    if not within(actor.position, target.position, weapon.long_range):
        raise ValueError(
            f"{target.name} is beyond the long range of {weapon.name} "
            f"({weapon.long_range} feet), and no attack may be made at all (p. 90)"
        )
    return not within(actor.position, target.position, weapon.normal_range)


def _graze(weapon: Weapon, target_id: str, ability: int) -> tuple[Effect, ...]:
    """A miss that still deals the ability modifier, if the weapon has Graze.

    Clamped at zero because a negative modifier would be negative damage, and the document
    gives no rule for a miss that heals. "The damage can be increased only by increasing
    the ability modifier", so nothing else may be folded in here.
    """
    if not weapon.graze or ability <= 0:
        return ()
    return (
        Effect(
            kind=EffectKind.DAMAGE,
            target_id=target_id,
            amount=ability,
            description=(
                f"{weapon.name} (Graze): a miss still deals {ability}, "
                "the ability modifier used for the attack roll"
            ),
            damage_type=weapon.damage_type,
        ),
    )


def _target_of(declaration: Declaration) -> str:
    """Read the target from the structured intent — never from the free-text label."""
    target_id = attack_target(declaration.intent.action_key)
    if target_id is None:
        raise ValueError(
            f"{declaration.intent.action_key!r} is not an attack. The target is read from "
            "the action key the read surface issued, which is what the token commits to"
        )
    return target_id
