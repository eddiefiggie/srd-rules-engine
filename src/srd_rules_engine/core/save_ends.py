"""The save a condition repeats at the end of its holder's turns (p. 63, #110, R1, R4).

`Conditions.saves_due_after` has reported this since #18 and nothing ever rolled it. Two
docstrings promised that "the turn loop consults it"; the turn loop did not exist as a
phase, which is what decision
[0023](../../../docs/decisions/0023-the-turns-end-is-a-loop-owned-phase.md) found and
settled. This module is the rolling half — `loop.turn.TurnLoop.end_turn` is the occasion.

## Why one rule per condition

The resolver has to know *which* condition's save it is rolling, and there are only three
places that could say. The declaration's free-text label is out — the engine reading prose
to select a mechanic is the capability being removed, and R6 already excludes the label from
the trigger matcher for the same reason. `situation` never reaches a resolver. So the rule
id carries it, one per condition, and the resolver is a closure over that condition exactly
as `attack_resolver` is a closure over a weapon.

Everything else is read from state at resolution time. The ability and the DC live on the
`SaveEnds` the imposing effect supplied, because p. 63 states them per-effect and the
document has no general rule to read them from — so a condition applied without one simply
has no early-out, and nothing here invents a DC for it.

## What this does not model

**Saving-throw proficiency.** No combatant in this engine declares proficient saves, so the
modifier here is the bare ability modifier. Adding a proficiency bonus would be inventing a
rule value for a field that does not exist (R31). The gap is disclosed rather than papered
over, and it applies to every save in the engine rather than to this one.

**The event-triggered early-out.** "for 1 minute **or until it takes any damage**" (p. 63)
is not a save and not end-of-turn. 0023 clause 5 puts it where the state change happens —
`EncounterState.with_damage` — rather than routing damage through the turn loop.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    condition_ended,
)

# Both are re-exported: 0027 clause 2 moved them to `core.conditions` so that
# `EncounterState` could reach them without a cycle, and this is where callers look.
from srd_rules_engine.core.conditions import SAVE_ENDS_PREFIX as SAVE_ENDS_PREFIX
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.conditions import save_ends_rule_id as save_ends_rule_id
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

#: R31. p. 63 is the sentence, and it is the one `core.duration` was already built from.
#: `scripts/verify_d20_rules.py` has carried it as a re-runnable pattern since #18 — "the
#: save-ends shape is stated per-effect, with its own ability and DC" — so this module adds
#: no new clause to assert. It rolls a sentence the repository had already verified; what
#: was missing was the occasion, not the reading (0023).
SAVE_ENDS_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Spell Descriptions" (a spell whose effect "repeats the save at the '
        'end of each of its turns, ending the effect on itself on a success"), p. 63'
    ),
    date="2026-08-24",
    method=VerificationMethod.ASSERTED,
)

#: The rule id prefix. Public because a ruleset assembled elsewhere has to register these
#: under the same ids the obligation enumerator asks for, and a literal repeated at both
#: ends is a literal that drifts.


def save_ends_rule(condition: Condition) -> Rule:
    """The SRD rule for repeating this condition's save at the end of a turn."""
    return Rule(
        id=save_ends_rule_id(condition),
        summary=(
            f"At the end of its turn, a creature with the {condition.value.title()} condition "
            "repeats the save the imposing effect stated, ending the condition on a success."
        ),
        provenance=RuleProvenance.SRD,
        verification=SAVE_ENDS_VERIFICATION,
    )


def save_ends_rules() -> tuple[Rule, ...]:
    """One per condition, in a stable order.

    All fifteen, rather than the subset that happens to carry a `SaveEnds` today: which
    conditions an effect can impose with a repeated save is a property of the effect, not
    of the condition, so restricting the set here would decide something p. 63 does not.
    """
    return tuple(save_ends_rule(c) for c in sorted(Condition, key=lambda c: c.value))


def save_ends_resolver(condition: Condition) -> Resolver:
    """Build the resolver for this condition's repeated save.

    A resolver like any other, so the save reaches an outcome only through the one
    adjudication entry point (R1) and the engine rolls it (R4). Nothing here decides
    whether the save was warranted — `Conditions.saves_due_after` answers that, and
    `TurnLoop.end_turn` is what consults it.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        due = actor.conditions.saves_due_after(declaration.actor_id)
        save = due.get(condition)
        if save is None:
            raise ValueError(
                f"{actor.name} has no repeated save due for {condition.value}. The save is "
                "read from the SaveEnds the imposing effect supplied, so a condition "
                "carrying none has no early-out and this resolver has nothing to roll"
            )

        return Proposal(
            test=D20Test(
                kind=TestKind.SAVE,
                ability=save.ability,
                target=save.dc,
                target_basis=(
                    f"DC {save.dc} {save.ability} save, stated by the effect that imposed "
                    f"{condition.value} — p. 63 states the DC per effect, so it is read "
                    "from the condition's duration rather than derived"
                ),
                modifiers=(
                    Modifier(source=f"ability:{save.ability}", value=actor.modifier(save.ability)),
                ),
            ),
            on_success=(
                condition_ended(
                    declaration.actor_id,
                    condition,
                    description=(
                        f"the repeated DC {save.dc} {save.ability} save succeeded, ending "
                        f"{condition.value} (p. 63)"
                    ),
                ),
            ),
            # p. 63 says the effect ends "on a success" and says nothing about a failure, so
            # a failure does nothing rather than costing anything. An engine-chosen penalty
            # here would be a rule value the document does not state.
            on_failure=(),
            citations=(f"p. 63: {condition.value} repeats its save at the end of each turn",),
            may_claim=(
                f"that {actor.name} shook off {condition.value}, or did not, as the roll says",
            ),
            may_not_claim=(
                f"that {condition.value} ended for any reason other than this save",
                "that failing the save cost anything further — p. 63 states no penalty",
            ),
        )

    return resolve


def save_ends_resolvers() -> dict[str, Resolver]:
    """Every condition's resolver, keyed by the id `save_ends_rule` gives it."""
    return {save_ends_rule_id(c): save_ends_resolver(c) for c in Condition}
