"""p. 14's *Moving around Other Creatures*: the one sentence of four that is a ruling (0087).

> During your move, you can pass through the space of an ally, a creature that has the
> Incapacitated condition, a Tiny creature, or a creature that is two sizes larger or smaller
> than you. Another creature's space is Difficult Terrain for you unless that creature is Tiny
> or your ally. You can't willingly end a move in a space occupied by another creature. If you
> somehow end a turn in a space with another creature, you have the Prone condition unless
> you are Tiny or are of a larger size than the other creature.

Four sentences, and three of them live where a move is made. The first and third are
**refusals** in `EncounterState.with_movement`, beside the five already there (0056): a move
through a space p. 14 does not permit, or ending in one, is a move the rules do not allow
rather than an outcome. The second is a **price**: the stretch of a move inside another's
space is Difficult Terrain, and `with_movement` charges it. None of the three produces a
result, so none of them is a ruling (R1).

The fourth is different in kind. "You have the Prone condition" is an **outcome**, and it is
compelled by the turn ending rather than declared — "somehow", because the sentence before it
forbids arriving by moving, so the creature was pushed, teleported, or placed. That is
Suffocation's shape exactly (0023 clause 2, 0027 clause 6): the loop derives the obligation
from state at the end of the turn, the one adjudication entry point resolves it, and no die is
asked because the document states the condition outright. This module is that rule.

## What "in a space with another creature" means here

0084 gives every sized creature a square centred on its point, and clause 8 says two of them
may overlap. `EncounterState.shares_space_with` reads the fourth sentence **symmetrically**:
two creatures share a space when either's point is inside the other's square, which is one
test against the wider square. It is deliberately not the overlap of the two squares — two
Medium creatures five feet apart have squares that touch, and that reading would knock every
pair in ordinary melee reach Prone at the end of every turn.

## What is withheld, and why

"Of a larger size than the other creature" compares two sizes. A creature nobody sized is
unknown rather than Medium (0051), and a Prone applied on a guessed comparison would be an
outcome the rules may not produce — so a pair missing either size contributes nothing, which
is 0030 clause 1's direction. Tiny is the creature's own size and needs only that.

Ally is p. 176's, and p. 176 makes it a designation in all four of its disjuncts. So it is a
label the ruleset states on `Combatant.side`, and a creature with no side is nobody's ally:
an ally's space is passed through and crossed for free, and a guessed friendship would grant
movement the rules may not.
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
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

#: The rule id the loop asks for and a ruleset registers under. The Prone it applies carries
#: this id as its cause (0083), so a reader of the condition can see which sentence put the
#: creature on the ground.
SHARED_SPACE_RULE_ID: Final = "shared-space-prone"

#: R31. All four of p. 14's sentences and p. 176's *Ally* are clauses in
#: `scripts/verify_d20_rules.py`, asserted on 2026-09-04 by the change that filed #456 —
#: before this rule was built, which is the order `AGENTS.md` asks for.
MOVING_AROUND_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Playing the Game: Moving around Other Creatures p. 14 — who may be "
        "passed through, whose space is Difficult Terrain, where a move may not end, and the "
        "Prone for ending a turn in a space with another creature; Rules Glossary: Ally p. 176"
    ),
    date="2026-09-04",
    method=VerificationMethod.ASSERTED,
)


def shared_space_rule() -> Rule:
    """The SRD rule the end of a turn incurs for a creature in another's space (p. 14)."""
    return Rule(
        id=SHARED_SPACE_RULE_ID,
        summary=(
            "A creature that ends its turn in a space with another creature has the Prone "
            "condition, unless it is Tiny or larger than the other creature."
        ),
        provenance=RuleProvenance.SRD,
        verification=MOVING_AROUND_VERIFICATION,
    )


def shared_space_resolver() -> Resolver:
    """Build the resolver for p. 14's Prone at the end of a turn.

    No d20 (0027 clause 6): the sentence states the condition and asks nothing of the dice.
    Whether it is owed is `EncounterState.owes_prone_for_shared_space`, which the loop reads
    to derive the obligation and this reads again to refuse a declaration for a creature
    that owes nothing — the obligation is read off state and is never declared.

    The Prone carries no duration, as p. 90's Topple and p. 182's fall leave theirs: the
    condition ends when the creature rights itself (p. 186, `core.prone`), and nothing here
    says otherwise.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        if not state.owes_prone_for_shared_space(actor_id):
            raise ValueError(
                f"{actor.name} is not in a space with another creature it is no larger than, "
                "so p. 14 has nothing to resolve. The Prone is read off state at the end of "
                "a turn and never declared"
            )
        sharing = ", ".join(other.name for other in state.shares_space_with(actor_id))

        return Proposal(
            outcome=(
                condition_applied(
                    actor_id,
                    Condition.PRONE,
                    description=(
                        f"ended its turn in a space with {sharing}: the Prone condition (p. 14)"
                    ),
                    caused_by=SHARED_SPACE_RULE_ID,
                ),
            ),
            citations=("srd:playing-the-game/moving-around-other-creatures",),
            may_claim=(
                "that the creature is on the ground, in a space it shares with another",
                "that it can crawl, or spend half its Speed to stand (p. 186)",
            ),
            may_not_claim=(
                "that anything was rolled for, resisted or avoided — p. 14 states the "
                "condition and asks nothing of the dice",
                "that the creature was moved, shoved aside or displaced; it is where it was, "
                "and only its posture changed",
                "how it came to be there — this engine holds the position and not the story",
            ),
        )

    return resolve
