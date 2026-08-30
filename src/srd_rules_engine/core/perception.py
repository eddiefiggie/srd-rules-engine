"""A Wisdom (Perception) check to see a particular creature, and what obscurement does to it.

The consumer #138 was missing. `core.sight` has classified a space as Lightly or Heavily
Obscured since #150, and **nothing read the answer** — p. 184's Disadvantage was produced by
nothing, which is why `lightly-obscured` and `dim-light` stayed unclaimed while the table
that decides them was full. A value computed and read by nobody has resolved nothing.

## The three sentences this composes, and one of them is not about obscurement

* **p. 184, Lightly Obscured:** "You have Disadvantage on Wisdom (Perception) checks to see
  something in a Lightly Obscured space."
* **p. 182, Heavily Obscured:** "You have the Blinded condition **while trying to see
  something** in a Heavily Obscured space." Scoped to the attempt — a relation between
  observer and target, not a condition on the creature (0025 clause 4, and the verifier's
  clause note settled it before any code was written against it).
* **p. 177, Blinded:** "You can't see and **automatically fail any ability check that
  requires sight**."

The third is what makes the second mechanical. Heavily Obscured on its own says a condition
applies; Blinded's own entry says what that costs a check. Neither sentence alone gives an
automatic failure, and reading only p. 182 would have left the Heavily Obscured case as a
Disadvantage — plausible, and not what the document says.

## An automatic failure is an outcome, and it is not a roll

0027 clause 6 made an outcome expressible without a d20, for Falling. This is the second
instance and the first that is a *check*: p. 177 says the check fails, so rolling one would
be inventing a test whose result the rules had already settled (R4 from the direction it is
usually not read from).

## What is deliberately absent

**A DC.** The SRD sets no difficulty for seeing a creature; p. 187's Search action says only
that you "make a Wisdom check to discern something that isn't obvious". Against a hiding
creature it would be contested by Stealth, and Hide is not built (#143). So the resolver
takes the difficulty as a closure parameter, exactly as `falling_resolver` takes a distance:
the situation is the caller's, the outcome is the engine's.

**The Search action.** p. 187's entry has a table mapping four skills to four things to
detect, and this builds one of them. The `search` shape stays unclaimed.

**Passive Perception's interaction.** p. 186 shifts the score by 5 for Advantage or
Disadvantage "on such checks", and obscurement's Disadvantage is per *target space* rather
than a standing property of the creature. A passive score has no target, so applying a
per-target modifier to it would answer a question p. 186 does not ask. `passive_score`
already takes the flags for a caller that has decided one applies.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import Declaration, Proposal, Resolver
from srd_rules_engine.core.d20 import Advantage, D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.skills import PerceptionCheck as PerceptionCheck
from srd_rules_engine.core.skills import Skill
from srd_rules_engine.core.state import EncounterState

PERCEPTION_RULE_ID: Final = "perception-check"

#: R31. Every sentence this module composes is a clause in `scripts/verify_d20_rules.py`.
PERCEPTION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Lightly Obscured p. 184, Heavily Obscured p. 182, "
        "Blinded p. 177, Skill p. 188, Search p. 187; the Skills table, p. 9"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def perception_rule() -> Rule:
    """The rule a Perception check is adjudicated under.

    `SRD` provenance, because every clause it applies is printed: p. 187 makes the check,
    p. 9 pairs Perception with Wisdom, p. 188 adds the Proficiency Bonus, and pp. 184, 182
    and 177 supply what obscurement does to it.

    **What is this engine's is the packaging**, and the summary says so. The document names
    a Search action that may use the skill; it does not name a "perception-check" rule.
    `RuleProvenance` has two members and neither is "composed from printed clauses", and an
    SRD rule may not carry a `rationale` — it cites a section instead — so the distinction
    is drawn where a reader of the rule will actually meet it.
    """
    return Rule(
        id=PERCEPTION_RULE_ID,
        summary=(
            "A Wisdom (Perception) check to see a particular creature. Every clause is "
            "printed — p. 187 makes the check, p. 9 pairs the skill with Wisdom, p. 188 "
            "adds the Proficiency Bonus, pp. 184 and 182 say what obscurement does and "
            "p. 177 what being Blinded does — but packaging them as one adjudicable rule "
            "is this engine's, not the document's."
        ),
        provenance=RuleProvenance.SRD,
        verification=PERCEPTION_VERIFICATION,
    )


def perception_resolver(target_id: str, *, dc: int, basis: str) -> Resolver:
    """Build the resolver for a check to see `target_id`.

    A closure over the target and the difficulty, as `falling_resolver` is a closure over a
    distance. The engine decides what the check *has* — advantage, or no roll at all — and
    rolls it; the caller supplies only which creature is being looked for and how hard the
    situation makes it. `basis` is recorded as the target number's derivation, because a DC
    the document does not state must say where it came from (R5).
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        observer_id = declaration.actor_id
        check = state.perception_of(observer_id, target_id)
        observer = state.combatant(observer_id)

        if check.automatic_failure:
            # p. 177 has already settled it, so there is nothing to adjudicate — and
            # nothing to *record* either, which is why this refuses rather than proposing.
            #
            # A proposal here would have to be testless with no effects, and
            # `Proposal.__post_init__` refuses that shape: "a proposal with no test and no
            # outcome decides nothing." That guard is right for the case it was written for
            # and wrong for this one — an automatic failure decides something and changes
            # no state. Relaxing it is a change to what a Proposal means, which is a
            # decision rather than a fix, so it is filed rather than made here (#224).
            #
            # Meanwhile the answer is not lost: `EncounterState.perception_of` reports it,
            # which is a read stating a rule value (R19) and cannot be argued with. The
            # caller learns the check fails before proposing one.
            raise ValueError(
                f"{observer.name} automatically fails this check, so there is nothing to "
                f"roll: {check.because}. Ask `EncounterState.perception_of` before "
                "declaring — this outcome is settled by the rules rather than by a die"
            )

        bonus = observer.check_bonus(Skill.PERCEPTION)
        return Proposal(
            test=D20Test(
                kind=TestKind.CHECK,
                # Wisdom, so p. 177's Strength-or-Dexterity clause does not reach it — which
                # is a fact worth stating rather than leaving to an absent field.
                ability="wis",
                target=dc,
                target_basis=basis,
                modifiers=(Modifier(source="skill:perception", value=bonus),),
                has_advantage=check.advantage is Advantage.ADVANTAGE,
                has_disadvantage=check.advantage is Advantage.DISADVANTAGE,
            ),
            citations=("srd:rules-glossary/skill", "srd:rules-glossary/search"),
            may_claim=(
                f"that {observer.name} looked for the target",
                f"what the looking was worth: {check.because}",
            ),
            may_not_claim=(
                "that the target was found unless the check succeeded",
                "anything the check did not establish; a success says the target was "
                "perceived, not what it is doing",
            ),
        )

    return resolve
