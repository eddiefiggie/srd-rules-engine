"""However a grapple is initiated, it follows these rules (p. 182, *Grappling*).

> A creature can grapple another creature. Characters typically grapple by using an Unarmed
> Strike. Many monsters have special attacks that allow them to quickly grapple prey.
> **However a grapple is initiated, it follows these rules.**

That sentence is why this module exists apart from whatever imposes the condition. p. 190's
Unarmed Strike is one initiator and the bestiary is full of others — an ankheg's mandibles, an
aboleth's tentacle, a rug of smothering — each stating its own escape DC. The rules for
*being* grappled and for getting out are common to all of them, so they are built once, here,
and the initiators arrive separately
([#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335)).

**The exit is built before any initiator, and that ordering is deliberate.** A condition the
engine can impose and cannot lift is worse than one it cannot impose: the first ends a
playthrough, the second only fails to start one. So p. 182's endings ship first and p. 190's
options ship onto them.

## Three endings, and only one of them is a decision

p. 182 states four ways out and they are not the same kind of thing:

1. **The escape check.** "A Grappled creature can use its action to make a Strength
   (Athletics) or Dexterity (Acrobatics) check against the grapple's escape DC, ending the
   condition on itself on a success." A declared action with a roll — an adjudication.
2. **The grappler is Incapacitated.**
3. **The distance between the two exceeds the grapple's range.**
4. **The grappler releases**, "at any time (no action required)".

2 and 3 are **derived**: nothing decides them, they are simply true or not of the state, and a
creature whose grappler drops unconscious is not grappled whether or not anybody asks. They are
applied by `ended_by_circumstance` wherever state settles, never by a ruling. 4 is a
declaration that costs nothing and rolls nothing.

**Which check is the escaping creature's choice, and that needs no new seam.** p. 182 offers
Athletics or Acrobatics and lets the creature pick. Because the escape is an *action it
declares*, the choice is which action key it declares — the same shape the Dash offers one
entry per speed under. p. 190's Grapple and Shove are the harder case: there the choosing
creature is the *target of a forced save* and declares nothing, which is a seam this engine
does not have and #335 has to settle.
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
    condition_ended,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import Resolution

# The action keys live in `core.read_surface`, which is where they are offered, and this
# module imports them back — the arrangement `core.combat` already uses for Nick's and
# Cleave's keys. A resolver importing its own key from the surface that offers it is what
# keeps the two from drifting into two spellings of one string.
from srd_rules_engine.core.read_surface import (
    ESCAPE_SKILLS as ESCAPE_SKILLS,
)
from srd_rules_engine.core.read_surface import (
    can_be_escaped as can_be_escaped,
)
from srd_rules_engine.core.read_surface import (
    escape_declared,
    escape_key,
    release_declared,
    release_key,
)
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.skills import SKILL_ABILITY, Skill
from srd_rules_engine.core.state import EncounterState

# Re-exported: the two derivations below need `EncounterState` and are called from inside
# it, so they live in `core.state` for the same reason `hazards` keeps its rule ids there —
# a module `state` imports cannot be imported by `state`. This is where a reader looks for
# p. 182's endings, so this is where they are named.
from srd_rules_engine.core.state import ended_by_circumstance as ended_by_circumstance
from srd_rules_engine.core.state import grapples_released as grapples_released

ESCAPE_RULE_ID: Final = "grapple-escape"
RELEASE_RULE_ID: Final = "grapple-release"

#: R31. Every clause below is asserted in `scripts/verify_d20_rules.py` against p. 182.
GRAPPLING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=("SRD v5.2.1, Rules Glossary: Grappling p. 182, and the Grappled condition p. 182"),
    date="2026-08-30",
    method=VerificationMethod.ASSERTED,
)


def escape_rule() -> Rule:
    return Rule(
        id=ESCAPE_RULE_ID,
        summary=(
            "A Grappled creature can spend its action on a Strength (Athletics) or Dexterity "
            "(Acrobatics) check against the grapple's escape DC, ending the condition on a "
            "success."
        ),
        provenance=RuleProvenance.SRD,
        verification=GRAPPLING_VERIFICATION,
    )


def release_rule() -> Rule:
    return Rule(
        id=RELEASE_RULE_ID,
        summary="The grappler can release the target at any time, and no action is required.",
        provenance=RuleProvenance.SRD,
        verification=GRAPPLING_VERIFICATION,
    )


def grappling_rules() -> tuple[Rule, ...]:
    """Both, in a stable order. p. 182's other two endings are not rules a caller declares —
    nothing decides them, so they have no rule id and no resolver."""
    return (escape_rule(), release_rule())


def grappling_resolvers() -> dict[str, Resolver]:
    """Keyed by the rule id a declaration names.

    Both escape checks share **one** rule id and are told apart by the action key, because
    p. 182 states one rule that offers a choice of check rather than two rules. A rule id per
    check would report two rules in the ledger where the document has one.
    """
    return {
        ESCAPE_RULE_ID: _escape_resolver_for_declared_skill(),
        RELEASE_RULE_ID: release_resolver(),
    }


def _escape_resolver_for_declared_skill() -> Resolver:
    """Dispatches to the check the declaration named."""

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        skill = escape_declared(declaration.intent.action_key)
        if skill is None:
            raise ValueError(
                f"{declaration.intent.action_key!r} is not an escape attempt. p. 182 offers a "
                "Strength (Athletics) or Dexterity (Acrobatics) check and nothing else"
            )
        return escape_resolver(skill)(state=state, declaration=declaration, facts=facts)

    return resolve


def escape_resolver(skill: Skill) -> Resolver:
    """p. 182's escape check, for one of the two checks it offers.

    The DC is the **grapple's**, read from the condition the creature is holding rather than
    recomputed from the grappler — p. 190 sets it from the grappler's Strength and Proficiency
    Bonus at the moment of the grapple, and a stat block states it outright, so recomputing it
    would produce a different number for every grapple a stat block imposed (R4: the engine
    uses what it recorded, never what a caller supplies now).

    **The Proficiency Bonus is the escaping creature's**, through `check_bonus`, because
    p. 182 calls for a Strength (Athletics) or Dexterity (Acrobatics) *check* and p. 188 adds
    the bonus to a check when the creature has the skill. A creature without it rolls the bare
    ability modifier.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        if escape_declared(declaration.intent.action_key) is not skill:
            raise ValueError(
                f"this declaration is not an escape with {skill.value}: "
                f"{declaration.intent.action_key!r} names something else"
            )
        if Condition.GRAPPLED not in actor.conditions.held:
            raise ValueError(
                f"{actor.name} is not Grappled, and p. 182's escape check ends a condition "
                "the creature has to be holding"
            )
        grapple = actor.conditions.grapple
        if grapple is None or grapple.escape_dc is None:
            raise ValueError(
                f"{actor.name}'s grapple states no escape DC, so p. 182's check has no target "
                "number. A DC the engine chose would be a DC the document did not state"
            )
        grappler_id = actor.conditions.grappler_id
        held_by = f" from {state.combatant(grappler_id).name}" if grappler_id else ""

        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action p. 182 spends on an escape attempt",
                ),
            ),
            test=D20Test(
                kind=TestKind.CHECK,
                # p. 182's two checks are a Strength one and a Dexterity one, so which was
                # declared decides what p. 177's untrained-armour clause reaches.
                ability=SKILL_ABILITY[skill],
                target=grapple.escape_dc,
                target_basis=f"the grapple's escape DC {grapple.escape_dc} (p. 182)",
                modifiers=(
                    Modifier(
                        source=f"skill:{skill.value}",
                        value=actor.check_bonus(skill),
                    ),
                ),
            ),
            on_success=(
                condition_ended(
                    actor.id,
                    Condition.GRAPPLED,
                    description=f"escaped the grapple{held_by} with a {skill.value} check (p. 182)",
                ),
            ),
            citations=("srd:rules-glossary/grappling",),
            may_claim=(
                f"that {actor.name} twisted, wrenched or slipped as the check describes",
                "that the attempt cost it its action, whether or not it worked",
            ),
            may_not_claim=(
                "that a failed attempt made the grapple worse; p. 182 gives failure no effect "
                "beyond the spent action",
                "that the escape moved the creature anywhere — ending the condition is not a "
                "movement, and p. 182 grants none",
            ),
        )

    return resolve


def release_resolver() -> Resolver:
    """p. 182's release: "the grappler can release the target at any time (no action required)".

    No test, and no cost. It is here rather than left to a caller mutating state because R1
    admits one entry point for a mechanical change: a release is an ending, and an ending that
    reached state without a ruling would carry no citation and no ledger entry.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        target_id = release_declared(declaration.intent.action_key)
        if target_id is None:
            raise ValueError(
                f"this declaration is not a release: {declaration.intent.action_key!r} names "
                "something else"
            )
        target = state.combatant(target_id)
        if target.conditions.grappler_id != actor.id:
            raise ValueError(
                f"{actor.name} is not grappling {target.name}, and p. 182 lets a grappler "
                "release only the creature it is holding"
            )

        return Proposal(
            # `outcome` rather than `always`: 0027 clause 6 says a rule that resolves without
            # a d20 states its effects here, and `always` is for what a *tested* rule charges
            # whichever way the roll goes. A release rolls nothing and charges nothing — the
            # ending is the whole of it.
            outcome=(
                condition_ended(
                    target.id,
                    Condition.GRAPPLED,
                    description=f"{actor.name} released the grapple (p. 182)",
                ),
            ),
            citations=("srd:rules-glossary/grappling",),
            may_claim=(f"that {actor.name} let {target.name} go",),
            may_not_claim=(
                "that releasing cost anything; p. 182 says no action is required",
                "that the released creature moved — p. 182 ends a condition and moves nobody",
            ),
        )

    return resolve


__all__ = [
    "ESCAPE_RULE_ID",
    "ESCAPE_SKILLS",
    "GRAPPLING_VERIFICATION",
    "RELEASE_RULE_ID",
    "can_be_escaped",
    "ended_by_circumstance",
    "escape_declared",
    "escape_key",
    "escape_resolver",
    "escape_rule",
    "grapples_released",
    "grappling_resolvers",
    "grappling_rules",
    "release_declared",
    "release_key",
    "release_resolver",
    "release_rule",
]
