"""Hazards: the effects the world has on a creature without anyone attacking it.

Two of the five are here.

**Falling** fires on no occasion at all — it resolves when the creature lands — which is why
it was the first that could be built (0027 clause 7, applying
[0023](../../../docs/decisions/0023-the-turns-end-is-a-loop-owned-phase.md) clause 5
unchanged: an event resolves where the event happens, not in a catch-all).

**Burning** fires at the start of each of the creature's turns (p. 178), which is a phase this
engine has held since 0027 clauses 1-4 — the same one the death save fires in.

The other three are not blocked on an occasion any more. Suffocation has one (the turn's end,
built by 0023); Dehydration and Malnutrition fire at a day's end on the campaign axis. All
three are blocked on the same thing instead: **each inflicts an Exhaustion *level*, and
nothing can raise one through a ruling** — no `EffectKind`, no state mutator, no method on
`Conditions` ([#178](https://github.com/eddiefiggie/srd-rules-engine/issues/178)). Burning is
the exception because it deals Fire *damage*, and damage has worked since #88.

## Falling asks nothing of the d20

p. 182: "A creature that falls takes 1d6 Bludgeoning damage at the end of the fall for every
10 feet it fell, to a maximum of 20d6."

There is no test in that sentence, and until #170 that made it inexpressible: `Proposal.test`
was required and `adjudicate` rolled it unconditionally. Reaching an outcome by inventing a
test would have been inventing a roll the rules do not call for, so the proposal shape moved
instead (0027 clause 6). The dice are still the engine's — the resolver declares `20d6` at
most and never a number.

The distance is a closure parameter, the way `attack_resolver` closes over a weapon and
`save_ends_resolver` over a condition. How far a creature fell is a fact about the world the
caller holds, like which weapon it swung; what the fall *costs* is this engine's, and it is
not told.

## Prone, and the qualifier this engine can only half-check

p. 182 continues: "When the creature lands, it has the Prone condition **unless it avoids
taking any damage from the fall**."

That qualifier is about the damage actually taken, and the damage is rolled after the
proposal is built. Two of the three ways to take none are decidable here and one is not:

* **A fall shorter than 10 feet** deals zero dice. Decidable — and this module refuses to
  adjudicate it at all rather than proposing an outcome that resolves nothing.
* **Immunity to Bludgeoning** zeroes any amount, whatever the dice say. Decidable from
  `Defences.is_immune_to`, so the Prone is withheld and the damage is still recorded as the
  zero it will be.
* **Resistance rounding a low roll to zero** is not. p. 17 halves and rounds down, so a
  resistant creature rolling a 1 on a single die takes 0 and by p. 182 should not be Prone —
  and the branch was fixed before the die was thrown. **This engine applies Prone anyway**,
  disclosed here and filed as
  [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173).

The direction of that error is deliberate and is the one `core.conditions` already takes for
Frightened: applying a penalty whose qualifier cannot be checked cannot invent a success. It
is the opposite of `core.reactions`, which withholds an Opportunity Attack rather than fire
one the rules may not grant — because a penalty wrongly applied costs the creature something,
while damage wrongly dealt produces a number out of nothing.

## What is not modelled

**The liquid Reaction.** p. 182 lets a creature falling into water use its Reaction for a
DC 15 Strength (Athletics) or Dexterity (Acrobatics) check to halve the damage. Whether a
creature fell *into a liquid* is a narrative fact this engine cannot observe, and the
Reaction economy would have to offer the check before the fall resolved. Excluded and
disclosed (R32), not silently dropped — [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    DamageDice,
    Declaration,
    Proposal,
    Resolver,
    condition_applied,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

#: p. 182: "1d6 Bludgeoning damage ... for every 10 feet it fell".
FEET_PER_FALLING_DIE: Final = 10

#: p. 182: "to a maximum of 20d6". The cap is on the dice, not on the distance, so a
#: creature that falls 500 feet and one that falls 200 take the same dice.
MAX_FALLING_DICE: Final = 20

#: The die itself. Named rather than inlined so the sentence and the code read alike.
FALLING_DIE_SIDES: Final = 6

#: R31. Both sentences this module rests on are clauses in `scripts/verify_d20_rules.py`
#: (#140), including the Prone qualifier — which is the half of p. 182 easiest to drop.
FALLING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Falling p. 182 — both the damage per 10 feet with its "
        "20d6 cap and the Prone that follows unless no damage was taken"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def falling_dice(feet: int) -> int:
    """How many d6 a fall of this distance deals (p. 182).

    Integer division, so a 35-foot fall deals 3d6 and not 3.5 — the document counts whole
    10-foot increments and states no rule for a partial one.
    """
    if feet < 0:
        raise ValueError(f"a fall cannot be {feet} feet; distances are non-negative")
    return min(feet // FEET_PER_FALLING_DIE, MAX_FALLING_DICE)


def falling_resolver(feet: int) -> Resolver:
    """Build the resolver for a fall of a given distance.

    A closure over the distance, as `attack_resolver` is a closure over a weapon. The
    caller supplies how far; this decides what it costs, and the engine rolls it (R1, R4).
    """
    dice = falling_dice(feet)
    if dice == 0:
        raise ValueError(
            f"a fall of {feet} feet deals no dice — p. 182 counts whole 10-foot increments, "
            f"so nothing below {FEET_PER_FALLING_DIE} feet has an outcome to adjudicate. "
            "A ruling here would record that nothing happened, which is not the same as a "
            "rule deciding that nothing happens"
        )

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        immune = actor.defences.is_immune_to(DamageType.BLUDGEONING)

        damage = DamageDice(
            target_id=actor_id,
            count=dice,
            sides=FALLING_DIE_SIDES,
            source=f"falling {feet} feet",
            damage_type=DamageType.BLUDGEONING,
        )

        # p. 182's Prone is conditional on damage being taken. Immunity is the one way to
        # take none that is decidable before the dice are thrown, so it is decided here
        # rather than applied and disclosed.
        prone = (
            ()
            if immune
            else (
                condition_applied(
                    actor_id,
                    Condition.PRONE,
                    description=(
                        f"landing after a {feet}-foot fall (p. 182). Prone follows the "
                        "fall unless no damage was taken"
                    ),
                ),
            )
        )

        return Proposal(
            outcome=(damage, *prone),
            citations=("srd:rules-glossary/falling",),
            may_claim=(
                f"that the creature fell {feet} feet and landed",
                "that the landing dealt the damage recorded here, and no more",
                *(
                    ("that the fall left it unhurt, being immune to Bludgeoning damage",)
                    if immune
                    else ("that it is now Prone",)
                ),
            ),
            may_not_claim=(
                "that anything was rolled for, tested, resisted or avoided — a fall is not "
                "a test, and nothing about it can be passed",
                "that the creature broke, died, or was otherwise harmed beyond the damage "
                "recorded; those need their own declarations",
                *(
                    ("that it is Prone; immunity to Bludgeoning left it undamaged",)
                    if immune
                    else ()
                ),
            ),
        )

    return resolve


#: p. 178: "A burning creature or object takes 1d4 Fire damage at the start of each of its
#: turns."
BURNING_DIE_SIDES: Final = 4

#: The rule id the turn's start enumerates Burning under (0027 clause 2).
BURNING_RULE_ID: Final = "burning"

#: R31. The sentence is a clause in `scripts/verify_d20_rules.py` (#140), including the part
#: that says *start* — which is what put it in the same phase as the death save rather than
#: the one save-ends lives in.
BURNING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Burning p. 178 — 1d4 Fire damage at the start of each "
        "of the creature's turns"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def burning_rule() -> Rule:
    """The SRD rule the turn's start incurs for a burning creature (p. 178)."""
    return Rule(
        id=BURNING_RULE_ID,
        summary=("A burning creature takes 1d4 Fire damage at the start of each of its turns."),
        provenance=RuleProvenance.SRD,
        verification=BURNING_VERIFICATION,
    )


def burning_resolver() -> Resolver:
    """Build the resolver for Burning's damage at the start of a turn.

    No d20, like Falling — p. 178 asks nothing of the dice but the damage, and inventing a
    test to reach the outcome would invent a roll the rules do not call for (0027 clause 6).

    **What ends it is not here.** p. 178 puts the fire out when it is "doused, submerged, or
    suffocated", or by an action that gives the creature the Prone condition and rolls it on
    the ground. The first three are narrative facts this engine cannot observe; the fourth
    needs an action to spend and a ruling to apply Prone through. So a burning creature
    burns until a caller clears `Hazards.burning` directly — a disclosed gap rather than a
    silent one, and a consequential one: nothing here can stop it.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        if not actor.hazards.burning:
            raise ValueError(
                f"{actor.name} is not burning, so there is nothing for p. 178 to resolve. "
                "Burning is read off state and never declared"
            )

        return Proposal(
            outcome=(
                DamageDice(
                    target_id=actor_id,
                    count=1,
                    sides=BURNING_DIE_SIDES,
                    source="burning",
                    damage_type=DamageType.FIRE,
                ),
            ),
            citations=("srd:rules-glossary/burning",),
            may_claim=(
                "that the fire is still burning at the start of this turn",
                "that it dealt the damage recorded here, and no more",
            ),
            may_not_claim=(
                "that anything was rolled for, tested, resisted or avoided — Burning is not "
                "a test, and nothing about it can be passed",
                "that the fire went out; this engine cannot observe dousing, submersion or "
                "an action spent putting it out, and it has recorded none",
            ),
        )

    return resolve
