"""Dash, Dodge and Disengage: the three Actions that were offered and did nothing (#252).

Each has been in `ENGINE_SHAPES` as implemented since the action economy landed, and each
was **reachable by nothing**. `ActionBudget.dashed`, `ActionBudget.disengaged` and
`core.actions.dodging` existed, were tested, and had no caller in `src/` outside their own
module — so the read surface offered three actions, an agent could declare one, and the
adjudicator accepted it as `no-test-accepted` with no effects and no state change.

Their *consequences* were wired the whole time: `core.combat` reads `is_dodging` and gives
an attacker Disadvantage. What was missing was the **occasion**, which is the third time this
repository has found that exact shape — `concentration_save_dc` before #215, `Concentration`
before #235, and these.

## No d20, and the Action is the cost

All three are testless proposals (0027 clause 6): p. 180 and p. 181 state what each does and
ask nothing of the dice, so inventing a test to reach the outcome would invent a roll the
rules do not call for.

Each spends the Action through `Proposal.always`, which is where #248 put casting's costs and
is now where every charge in this engine lives. Before that, **nothing an adjudication did
cost anything** — which is why `dodging()` used to spend the Action itself and no longer does.

## What each one does not model

- **Dodge's "if you can see the attacker"** (p. 181) is carried as an unenforced clause by
  `ActionBudget.unenforced_clauses`, not decided here. It was already disclosed.
- **Disengage suppresses Opportunity Attacks**, which are an unimplemented shape (p. 185).
  The flag is set truthfully so the rule that eventually reads it finds an answer; today
  nothing does, and that is a gap in Opportunity Attacks rather than in Disengage.
- **Dash's choice of speed** is offered by the read surface, one entry per speed the creature
  actually has, because p. 180 gives the creature the choice — "You choose which speed to use
  each time you take it" — and a single Walk-only offer would take that choice away.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    action_spent,
    dashed,
    disengaged,
    dodging_taken,
)
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.position import MovementMode
from srd_rules_engine.core.read_surface import DASH, DISENGAGE, DODGE, dash_mode
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

DASH_RULE_ID: Final = DASH
DODGE_RULE_ID: Final = DODGE
DISENGAGE_RULE_ID: Final = DISENGAGE

#: R31. All three entries are asserted in `scripts/verify_d20_rules.py`.
TURN_ACTION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Dash p. 180, Disengage p. 181, Dodge p. 181; the "
        'Action entry naming all three, p. 176 ("On your turn, you can take one action")'
    ),
    date="2026-08-28",
    method=VerificationMethod.ASSERTED,
)


def dash_rule() -> Rule:
    return Rule(
        id=DASH_RULE_ID,
        summary=(
            "The Dash action grants extra movement for the current turn equal to the "
            "creature's speed after modifiers, in a speed it chooses."
        ),
        provenance=RuleProvenance.SRD,
        verification=TURN_ACTION_VERIFICATION,
    )


def dodge_rule() -> Rule:
    return Rule(
        id=DODGE_RULE_ID,
        summary=(
            "The Dodge action gives attack rolls against the creature Disadvantage and its "
            "Dexterity saves Advantage until the start of its next turn."
        ),
        provenance=RuleProvenance.SRD,
        verification=TURN_ACTION_VERIFICATION,
    )


def disengage_rule() -> Rule:
    return Rule(
        id=DISENGAGE_RULE_ID,
        summary=(
            "The Disengage action stops the creature's movement provoking Opportunity "
            "Attacks for the rest of the turn."
        ),
        provenance=RuleProvenance.SRD,
        verification=TURN_ACTION_VERIFICATION,
    )


def turn_action_rules() -> tuple[Rule, ...]:
    """All three, in a stable order."""
    return (dash_rule(), disengage_rule(), dodge_rule())


def dash_resolver() -> Resolver:
    """p. 180's extra movement, in the speed the declaration chose."""

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        mode = dash_mode(declaration.intent.action_key) or MovementMode.WALK
        # p. 180: "The increase equals your Speed **after applying any modifiers**", so the
        # conditions have already acted on it. `speeds_after` is what applies them, and it
        # reaches special speeds too (p. 188).
        available = actor.conditions.speeds_after(actor.speeds).for_mode(mode)
        if available is None:
            raise ValueError(
                f"{actor.name} has no {mode.value} speed, so p. 180 offers no choice of it. "
                "The read surface enumerates only the speeds a creature has"
            )

        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on the Dash (p. 176, p. 180)",
                ),
            ),
            outcome=(
                dashed(
                    actor.id,
                    available,
                    description=(
                        f"{available} extra feet of {mode.value} movement this turn, equal "
                        "to that speed after modifiers (p. 180)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/dash",),
            may_claim=(
                f"that {actor.name} put on a burst of speed and may move {available} feet "
                "farther this turn",
            ),
            may_not_claim=(
                "that anything was rolled for — Dash is not a test and nothing about it can "
                "be passed or failed",
                "that the extra movement persists beyond this turn",
            ),
        )

    return resolve


def dodge_resolver() -> Resolver:
    """p. 181's Dodge. The benefits are stated, and whether they hold is re-asked on read."""

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on the Dodge (p. 176, p. 181)",
                ),
            ),
            outcome=(
                dodging_taken(
                    actor.id,
                    description=(
                        "attack rolls against it have Disadvantage and its Dexterity saves "
                        "have Advantage, until the start of its next turn (p. 181)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/dodge",),
            may_claim=(f"that {actor.name} is giving ground and watching for the next blow",),
            may_not_claim=(
                "that anything was rolled for — Dodge is not a test",
                "that the benefits hold while the creature is Incapacitated or its Speed is "
                "0; p. 181 takes them away in both cases and the engine re-checks on read",
                "that an attacker the creature cannot see has Disadvantage — p. 181 requires "
                "seeing the attacker and this engine does not check it",
            ),
        )

    return resolve


def disengage_resolver() -> Resolver:
    """p. 181's Disengage. The flag is set; Opportunity Attacks are what would read it."""

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on the Disengage (p. 176, p. 181)",
                ),
            ),
            outcome=(
                disengaged(
                    actor.id,
                    description=(
                        "its movement does not provoke Opportunity Attacks for the rest of "
                        "this turn (p. 181)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/disengage",),
            may_claim=(f"that {actor.name} disengaged and may withdraw safely this turn",),
            may_not_claim=(
                "that anything was rolled for — Disengage is not a test",
                "that an Opportunity Attack was avoided; this engine does not model them, so "
                "nothing reads the flag this sets",
            ),
        )

    return resolve


def turn_action_resolvers() -> dict[str, Resolver]:
    """All three, keyed by the id the read surface offers and the declaration names."""
    return {
        DASH_RULE_ID: dash_resolver(),
        DODGE_RULE_ID: dodge_resolver(),
        DISENGAGE_RULE_ID: disengage_resolver(),
    }
