"""p. 90's Topple: a Constitution save on a hit, and Prone on a failure (#321, R1, R4).

> **Topple.** If you hit a creature with this weapon, you can force the creature to make a
> Constitution saving throw (DC 8 plus the ability modifier used to make the attack roll and
> your Proficiency Bonus). On a failed save, the creature has the Prone condition.

The second occupant of the forced-save queue that
[0048](../../../docs/decisions/0048-a-forced-save-is-one-mechanism.md) generalised, and the
reason it was generalised. `core.concentration` is the first, and the
two differ in what compels the save and in nothing else: both are owed by one creature, once
per triggering instance, and both are rolled by the loop through the one adjudication entry
point.

## What the attack records, and what this resolves

The debt is recorded by `attack_resolver` on a hit, carrying a DC the **engine** computed
from that attack (R4). This module is the rolling half: it reads the DC off the debt and
proposes the save. Nothing here decides whether the save was warranted.

## The DC is not recoverable afterwards, which is why it is carried

"DC 8 plus the ability modifier used to make the attack roll and your Proficiency Bonus."

Both inputs belong to the attack rather than to either creature's standing state:

* **The ability modifier used** is a choice for a Finesse weapon — p. 89 lets the wielder
  pick Strength or Dexterity — and nothing records which was picked once the attack is over.
* **The attacker's Proficiency Bonus** is the attacker's, and by the time the target rolls,
  the loop has only the target.

0036 clause 4 gave this reason for Concentration's damage amount, and it reaches further here:
the DC's inputs are not merely stale afterwards, they are gone.

## The Proficiency Bonus is added whether or not the wielder is proficient

p. 89 conditions the *attack roll's* bonus on proficiency — "you must have proficiency with it
to add your Proficiency Bonus to an attack roll you make with it". p. 90's DC formula states
no such condition: it says "your Proficiency Bonus" flatly. So a wielder who has the mastery
and lacks the proficiency sets the same DC.

That reading is uncomfortable and it is the document's. Inferring the condition across from
p. 89 would be exactly the rule value R31 forbids — plausible, universal, and stated nowhere.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    condition_applied,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

#: The rule id the loop asks for and a ruleset registers under. A literal repeated at both
#: ends is a literal that drifts, which is why `CONCENTRATION_RULE_ID` exists too.
TOPPLE_RULE_ID: Final = "mastery-topple"

#: p. 90's save is Constitution, and the ability is the rule rather than the caller's choice.
TOPPLE_SAVE_ABILITY: Final = "con"

#: The fixed part of p. 90's DC. The two variable parts are the attack's, computed where the
#: attack lands.
TOPPLE_DC_BASE: Final = 8

#: R31. Asserted as a clause in `scripts/verify_d20_rules.py` rather than trusted from
#: memory: the DC is a rule value, and a wrong one is indistinguishable from a right one
#: once it is inside a finished ruling.
TOPPLE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Equipment, "Mastery Properties" -> Topple ("If you hit a creature with '
        "this weapon, you can force the creature to make a Constitution saving throw (DC 8 "
        "plus the ability modifier used to make the attack roll and your Proficiency Bonus). "
        'On a failed save, the creature has the Prone condition"), p. 90'
    ),
    date="2026-08-29",
    method=VerificationMethod.ASSERTED,
)


def topple_save_dc(ability_modifier: int, proficiency_bonus: int) -> int:
    """p. 90's DC: 8 plus the ability modifier used for the attack, plus the Proficiency Bonus.

    **Not clamped.** A negative ability modifier lowers the DC, and the document states no
    floor — inventing one would be a rule value R31 forbids, and it would do so in the
    direction that helps the attacker.
    """
    return TOPPLE_DC_BASE + ability_modifier + proficiency_bonus


def topple_save_basis(ability: str, ability_modifier: int, proficiency_bonus: int) -> str:
    """The derivation that travels with the DC (R30), built where the DC is."""
    dc = topple_save_dc(ability_modifier, proficiency_bonus)
    return (
        f"Constitution save against a Topple weapon, DC {dc} — 8 plus the {ability} modifier "
        f"of {ability_modifier:+d} used for the attack roll and a Proficiency Bonus of "
        f"{proficiency_bonus:+d} (p. 90)"
    )


def topple_rule() -> Rule:
    """The SRD rule a creature hit by a Topple weapon owes (p. 90)."""
    return Rule(
        id=TOPPLE_RULE_ID,
        summary=(
            "A creature hit by a weapon with the Topple mastery property makes a Constitution "
            "saving throw against DC 8 plus the ability modifier used for the attack roll and "
            "the attacker's Proficiency Bonus, and has the Prone condition on a failure."
        ),
        provenance=RuleProvenance.SRD,
        verification=TOPPLE_VERIFICATION,
    )


def topple_resolver() -> Resolver:
    """Build the resolver for the save a Topple hit compels.

    A resolver like any other, so the save reaches an outcome only through the one
    adjudication entry point (R1) and the engine rolls it (R4).
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        debt = state.forced_save_for(actor_id)
        if debt is None:
            raise ValueError(
                f"{actor.name} owes no save, so there is nothing for p. 90's Topple to "
                "resolve. The save is read off the debt the engine recorded when the attack "
                "hit, and it is never declared"
            )
        if debt.rule_id != TOPPLE_RULE_ID:
            raise ValueError(
                f"{actor.name} owes a {debt.rule_id!r} save, not p. 90's Topple. One queue "
                "serves every forced save since 0048, so a resolver reached for the wrong "
                "debt is the loop and the rule having come apart"
            )

        test = D20Test(
            kind=TestKind.SAVE,
            target=debt.dc,
            target_basis=debt.dc_basis,
            modifiers=(
                Modifier(source=f"ability:{debt.ability}", value=actor.modifier(debt.ability)),
            ),
        )

        return Proposal(
            test=test,
            # p. 90 states one consequence and states it for the failure. Success is the
            # absence of that, so it carries no effect — anything else here would be a
            # benefit the document does not grant.
            on_success=(),
            on_failure=(
                condition_applied(
                    actor_id,
                    Condition.PRONE,
                    description=(
                        f"the DC {debt.dc} Constitution save failed, and p. 90's Topple "
                        "applies the Prone condition"
                    ),
                ),
            ),
            citations=("srd:equipment/mastery-properties/topple",),
            may_claim=(
                f"that {actor.name} kept its feet, or was knocked from them, as the roll says",
            ),
            may_not_claim=(
                f"that {actor.name} took any damage from this save — p. 90 states none",
                "that anything followed a success; the document states no consequence for one",
            ),
        )

    return resolve
