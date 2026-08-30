"""The Constitution save damage compels of a concentrating creature (p. 179, R1, R4).

`core.spellcasting.concentration_save_dc` and `concentration_save` have implemented p. 179's
arithmetic since #19 and were called by nothing outside their own tests. This module is the
rolling half —
[0036](../../../docs/decisions/0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md)
clause 1 — and `loop.turn.TurnLoop` is the occasion, exactly as `core.save_ends` is the
rolling half of p. 63 and `end_turn` its occasion.

## Why this is not in `core.spellcasting`, where the plan put it

A resolver takes an `EncounterState`, so it must import `core.state`. `core.state` already
imports `Concentration` and `SpellSlots` **from** `core.spellcasting`, so a resolver there
would invert that edge into a cycle. `core.save_ends` is the same shape for the same reason:
the arithmetic lives with the mechanic and the resolver lives beside the state it reads.

## Why one rule rather than one per amount

The DC is a function of the damage, and `core.save_ends` needed one rule id per condition
because the resolver had no other way to learn which condition it was rolling for. This one
does: the debt is in state, recorded by the engine when the damage landed
([0036](../../../docs/decisions/0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md)
clause 4), and the resolver reads it there. A rule id per amount would put a number in an
identifier, and a ruleset would have to enumerate every damage total that can ever occur.

Reading it back from state rather than closing over it is also what keeps the record and the
roll from disagreeing: there is one number, in one place, written by the engine.

## What this does not model

**Saving-throw proficiency.** No combatant declares proficient saves, so the modifier is the
bare Constitution modifier. Adding a Proficiency Bonus would invent a rule value for a field
that does not exist (R31). Disclosed by `core.save_ends` already, for every save in the
engine rather than for this one.

**The other three breakers.** p. 179 also ends Concentration on another Concentration effect,
on Incapacitated, and on death. The last two are materialised by `Combatant.__post_init__`
since #238 (0037 clause 4). `Concentration.begin` holds the first and nothing declares it —
[#235](https://github.com/eddiefiggie/srd-rules-engine/issues/235), not modelled here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    concentration_ended,
)
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)

# Re-exported, not merely imported (0048). Both constants moved to `core.spellcasting` so
# that `EncounterState.with_damage` could build the whole `ForcedSave` where the trigger
# fires — this module imports state, so state cannot import it back. The names stay here
# because this is where a reader looks for them, and `core/__init__.py` re-exports from here.
from srd_rules_engine.core.spellcasting import (
    CONCENTRATION_RULE_ID as CONCENTRATION_RULE_ID,
)
from srd_rules_engine.core.spellcasting import (
    CONCENTRATION_SAVE_ABILITY as CONCENTRATION_SAVE_ABILITY,
)
from srd_rules_engine.core.state import EncounterState

#: R31. Asserted as a clause in `scripts/verify_d20_rules.py` rather than trusted from
#: memory: the DC is a rule value, and a wrong one is indistinguishable from a right one
#: once it is inside a finished ruling.
CONCENTRATION_SAVE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Rules Glossary, Concentration, "Damage" ("If you take damage, you '
        "must succeed on a Constitution saving throw to maintain Concentration. The DC "
        "equals 10 or half the damage taken (round down), whichever number is higher, up "
        'to a maximum DC of 30"), p. 179'
    ),
    date="2026-08-26",
    method=VerificationMethod.ASSERTED,
)


def concentration_rule() -> Rule:
    """The SRD rule a damaged concentrating creature owes (p. 179)."""
    return Rule(
        id=CONCENTRATION_RULE_ID,
        summary=(
            "A creature that takes damage while concentrating makes a Constitution saving "
            "throw to maintain Concentration, against DC 10 or half the damage taken, "
            "whichever is higher, to a maximum of 30."
        ),
        provenance=RuleProvenance.SRD,
        verification=CONCENTRATION_SAVE_VERIFICATION,
    )


def concentration_resolver() -> Resolver:
    """Build the resolver for the Concentration save damage compels.

    A resolver like any other, so the save reaches an outcome only through the one
    adjudication entry point (R1) and the engine rolls it (R4). Nothing here decides whether
    the save was warranted — `EncounterState.with_damage` answered that when the damage
    landed, and the turn loop is what consults it.
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
                f"{actor.name} owes no Concentration save, so there is nothing for p. 179 "
                "to resolve. The save is read off the debt the engine recorded when the "
                "damage landed, and it is never declared"
            )
        if not actor.concentration.active:
            raise ValueError(
                f"{actor.name} is not concentrating on anything, so there is nothing for "
                "the save to maintain. p. 179 breaks Concentration; it does not compel a "
                "save from a creature holding none"
            )

        if debt.rule_id != CONCENTRATION_RULE_ID:
            raise ValueError(
                f"{actor.name} owes a {debt.rule_id!r} save, not p. 179's. One queue serves "
                "every forced save since 0048, so a resolver reached for the wrong debt is "
                "the loop and the rule having come apart"
            )

        # p. 179's arithmetic and its derivation are the rule, and both were computed where
        # the damage landed (0048) — the hit points they came from have since moved. What is
        # added here is the roll's modifier, which is the creature's.
        test = D20Test(
            kind=TestKind.SAVE,
            ability=debt.ability,
            target=debt.dc,
            target_basis=debt.dc_basis,
            modifiers=(
                Modifier(source=f"ability:{debt.ability}", value=actor.modifier(debt.ability)),
            ),
        )
        held = actor.concentration.rule_id

        return Proposal(
            test=test,
            # p. 179 states one consequence and states it for the failure: Concentration is
            # not maintained. Success is the absence of that, so it carries no effect —
            # anything else here would be a benefit the document does not grant.
            on_success=(),
            on_failure=(
                concentration_ended(
                    actor_id,
                    description=(
                        f"the DC {test.target} Constitution save failed, ending "
                        f"Concentration on {held} (p. 179)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/concentration",),
            may_claim=(
                f"that {actor.name} held its focus on {held}, or lost it, as the roll says",
                "that the damage the ruling names is what forced the save",
            ),
            may_not_claim=(
                f"that Concentration on {held} ended for any reason other than this save",
                "that succeeding cost or gained anything further — p. 179 states no other "
                "consequence either way",
            ),
        )

    return resolve
