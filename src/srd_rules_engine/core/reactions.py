"""Opportunity Attacks: what provokes one, and why none is offered yet (R12, #16).

Decision [0015](../../../docs/decisions/0015-reactions-and-the-agent-seam.md) found that the
agent seam already serves reactions — a generator can yield a request for a *different*
actor mid-resolution — and that what they actually need is state and a trigger. The state
landed with the Reaction budget. This is the trigger, and it is the half the SRD supplies a
sentence for.

## The sentence, and the clause in it that stops here

p. 185: *"You can make an Opportunity Attack when a creature that you can see leaves your
reach."* Asserted in `scripts/verify_d20_rules.py` against printed page 185, so this module
transcribes nothing.

Every clause in it is answerable today except one. **"that you can see"** needs the mapping
from light and sense to obscurement, which ships empty until #150 reads the pages
([0025](../../../docs/decisions/0025-sight-is-a-relation-over-stored-state.md) clause 5). So
this module computes what *would* provoke and **withholds every offer**, naming the clause
it is waiting on.

## Withholding rather than firing, and why that is the safe direction

`core.conditions` makes the opposite choice for Frightened — it applies the Disadvantage
whenever the condition is held, without checking the line-of-sight qualifier it cannot
evaluate — and states the reasoning: erring toward applying a penalty cannot invent a
success.

That reasoning inverts here. An Opportunity Attack that fires when the rules would not grant
it produces an attack roll and damage **out of nothing**, which is precisely an outcome the
dice never should have decided. Withholding one that the rules *would* grant omits an attack
instead. An omission is visible in the ledger as an absence; an invention is indistinguishable
from a legitimate hit. So the two cases err in opposite directions for the same reason, and
`withheld` is the field that keeps the choice from being silent.

**The alternative — asking the agent whether it can see — is not available.** It is the agent
deciding whether a mechanic applies to it, in a case where saying "no" avoids being attacked
and saying "yes" grants a free attack. R18's read surface reports what *is* legal; it does not
delegate the question.

## What this module does not do

It does not move anyone, does not spend a Reaction, and does not reach adjudication. It
answers "who would this movement provoke", which is the input the turn loop will need when
the offer can be made. `EncounterState.with_movement` does not call it, because a detection
that always withholds would add a step to every move to produce nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.equipment import Carriage, Weapon, items_in
from srd_rules_engine.core.position import Position, within
from srd_rules_engine.core.rules import Verification, VerificationMethod, VerificationState
from srd_rules_engine.core.state import Combatant, EncounterState

#: The clause this engine holds and cannot yet apply, in the vocabulary
#: `ActionBudget.unenforced_clauses` and `Conditions.unenforced_clauses` already use.
SIGHT_QUALIFIER = "opportunity-attack-requires-seeing-the-mover"

#: R31. Every sentence below is asserted against its printed page in
#: `scripts/verify_d20_rules.py`; this module adds no rule value of its own.
REACTION_VERIFICATION = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Opportunity Attacks p. 185, Disengage p. 181, "
        "Incapacitated p. 184, Reaction p. 186"
    ),
    date="2026-08-24",
    method=VerificationMethod.ASSERTED,
)


@dataclass(frozen=True)
class Provocation:
    """A movement that would provoke, and whether the offer can be made.

    `withheld` is `None` once the engine can answer every clause of p. 185's sentence. Until
    then it names the clause that is missing, so a caller reading a provocation can tell
    "nobody may attack" from "somebody may, and this engine cannot say whether they see it".
    """

    reactor_id: str
    mover_id: str
    withheld: str | None = SIGHT_QUALIFIER

    @property
    def may_be_offered(self) -> bool:
        return self.withheld is None


def _reaches(reactor: Combatant) -> frozenset[int]:
    """Every reach this creature could make an Opportunity Attack at (p. 90, p. 186).

    The creature's own reach is always a candidate — a creature holding nothing still has
    one, and p. 191's Unarmed Strike is always available. A held Reach weapon adds a second,
    because p. 90 extends the reach "when determining your reach for Opportunity Attacks
    **with it**": the bonus belongs to the attack that weapon would make, not to the creature.

    A set rather than a maximum, and the difference is a real case rather than tidiness. A
    creature holding a Glaive and a Dagger has reaches of 10 and 5, and a mover going from 3
    feet to 7 leaves the Dagger's reach while staying inside the Glaive's — so it provokes,
    and a maximum would say it does not.
    """
    weapons = (
        item for item in items_in(reactor.equipment, Carriage.HELD) if isinstance(item, Weapon)
    )
    return frozenset({reactor.reach} | {w.reach_in_use(reactor.reach) for w in weapons})


def _left_reach(reactor: Combatant, frm: Position, to: Position) -> bool:
    """p. 185: the mover *leaves* the reach, so being outside it all along is not a trigger.

    Asked once per reach the reactor has, because leaving *a* reach it could attack at is
    what provokes (#316). Reading `reactor.reach` alone gave a Reach weapon no reach at all.
    """
    if reactor.position is None:
        return False
    return any(
        within(reactor.position, frm, reach) and not within(reactor.position, to, reach)
        for reach in _reaches(reactor)
    )


def provocations(
    state: EncounterState, mover_id: str, *, frm: Position, to: Position
) -> tuple[Provocation, ...]:
    """Who this movement would provoke, in id order.

    Nothing is spent and nothing is offered — see the module docstring for why every result
    comes back withheld. An encounter that tracks no positions provokes nothing, which is the
    same honest silence `with_movement` gives a creature with no position.
    """
    mover = state.combatant(mover_id)
    if mover.actions.disengaged:
        # p. 181: "your movement doesn't provoke Opportunity Attacks for the rest of the
        # current turn." A suppression rather than a saving throw — there is nothing to roll.
        return ()

    return tuple(
        Provocation(reactor_id=reactor.id, mover_id=mover_id)
        for reactor in sorted(state.combatants, key=lambda c: c.id)
        if reactor.id != mover_id
        and reactor.actions.available(ActionKind.REACTION, reactor.conditions)
        and _left_reach(reactor, frm, to)
    )
