"""Opportunity Attacks: what provokes one, and what is still missing (R12, #381).

Decision [0015](../../../docs/decisions/0015-reactions-and-the-agent-seam.md) found that the
agent seam already serves reactions — a generator can yield a request for a *different*
actor mid-resolution — and that what they actually need is state and a trigger. The state
landed with the Reaction budget. This is the trigger.

## The sentence, and where each clause now stands

p. 185: *"You can make an Opportunity Attack when a creature that you can see leaves your
reach."* Asserted in `scripts/verify_d20_rules.py` against printed page 185, so this module
transcribes nothing.

**"that you can see" is answerable now, and was not when this module was written.** It waited
on the light-and-sense mapping, which [#150](https://github.com/eddiefiggie/srd-rules-engine/issues/150)
read off the document on 2026-08-25 — after which every result here went on being withheld
for five days, on a blocker that had closed
([#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381)). `EncounterState.can_see`
is consulted per reactor, and its three verdicts are three different answers rather than two:

* `CAN_SEE` — the clause is satisfied and the provocation is offerable.
* `CANNOT_SEE` — the clause **fails**, so there is no provocation to report. It is dropped
  rather than withheld: p. 185 grants the attack *when* you can see, and a creature that
  cannot see the mover was never owed one.
* `UNSTATED` — the document states no answer for this pair (0025, 0029). Withheld, naming
  `SIGHT_UNSTATED`, because "the SRD does not say" is not a no and must not become one.

That third value is why the withholding narrows rather than disappears. It is now a fact
about **one pair of creatures in one encounter**, not a fact about the engine.

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
`withheld` is the field that keeps the choice from being silent — which is why it has **no
default**: every construction states whether the offer may be made.

**The alternative — asking the agent whether it can see — is not available**, and is not made
available by sight now being answerable. It is the agent deciding whether a mechanic applies
to it, in a case where saying "no" avoids being attacked and saying "yes" grants a free
attack. R18's read surface reports what *is* legal; it does not delegate the question. That is
why `UNSTATED` withholds rather than escalating.

## What this module still does not do

It does not move anyone, does not spend a Reaction, and does not reach adjudication. It
answers "who would this movement provoke", which is the input the turn loop will need when
the offer can be made. `EncounterState.with_movement` does not call it.

**That is the remaining half, and it is what `OFFER_NEVER_MADE` now discloses.** The read
surface said sight was the reason no reaction had ever been offered; sight has not been the
reason since #150, and the disclosure went on saying so. 0056 and
[0060](../../../docs/decisions/0060-a-disclosure-can-be-wrong-about-why.md) found the same
shape twice before — a disclosure that is accurate about *that* something is missing and
wrong about *what*. The offer is [#382](https://github.com/eddiefiggie/srd-rules-engine/issues/382).
"""

from __future__ import annotations

from dataclasses import dataclass

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.equipment import Carriage, Weapon, items_in
from srd_rules_engine.core.position import Position, within
from srd_rules_engine.core.rules import Verification, VerificationMethod, VerificationState
from srd_rules_engine.core.sight import Visibility
from srd_rules_engine.core.state import Combatant, EncounterState

#: p. 185's sight clause, for a pair the document does not answer for. Not a gap in this
#: engine: `Visibility.UNSTATED` means the SRD states no rule, which 0029 clause 2 records
#: for an obstruction nobody has described. Carried on the `Provocation` rather than on the
#: creature, because it is true of one pair rather than of the encounter.
SIGHT_UNSTATED = "opportunity-attack-sight-unstated"

#: The half that is genuinely unbuilt: the detection runs, and nothing offers its result.
#: In the vocabulary `ActionBudget.unenforced_clauses` and `Conditions.unenforced_clauses`
#: already use. **This replaced `opportunity-attack-requires-seeing-the-mover`**, which named
#: sight as the reason and stayed after #150 made that untrue (#381).
OFFER_NEVER_MADE = "opportunity-attack-detected-but-never-offered"

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

    `withheld` is `None` when every clause of p. 185's sentence is answered for this pair,
    and otherwise names the clause that is not, so a caller can tell "nobody may attack"
    from "somebody may, and this engine cannot say whether they see it".

    **It has no default**, deliberately. A default is a silent answer to the one question
    this type exists to make explicit, and the fail-open direction invents an attack out of
    nothing — see the module docstring for why that error is worse than the other one.
    """

    reactor_id: str
    mover_id: str
    withheld: str | None

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

    Nothing is spent and nothing is offered — see the module docstring for the half that is
    still missing. An encounter that tracks no positions provokes nothing, which is the same
    honest silence `with_movement` gives a creature with no position, and which `can_see`
    gives for the same reason.

    **Sight is asked of the state as it stands**, which is the mover where it was: `frm` and
    `to` describe a movement that has not been applied. p. 185 does not say at which instant
    the seeing is judged, and the departure is the moment it names, so asking at the position
    the mover is leaving follows the sentence rather than choosing between two readings of
    it. A caller that applies the movement first and asks afterwards is asking a different
    question, and would be answered about `to`.
    """
    mover = state.combatant(mover_id)
    if mover.actions.disengaged:
        # p. 181: "your movement doesn't provoke Opportunity Attacks for the rest of the
        # current turn." A suppression rather than a saving throw — there is nothing to roll.
        return ()

    found: list[Provocation] = []
    for reactor in sorted(state.combatants, key=lambda c: c.id):
        if reactor.id == mover_id:
            continue
        if not reactor.actions.available(ActionKind.REACTION, reactor.conditions):
            continue
        if not _left_reach(reactor, frm, to):
            continue

        sight = state.can_see(reactor.id, mover_id)
        if sight.verdict is Visibility.CANNOT_SEE:
            # p. 185 grants the attack *when* you can see the mover. A reactor who cannot is
            # not owed one, so this is an absent provocation rather than a withheld offer —
            # the two are different facts and a caller counting withheld ones should not see
            # this.
            continue

        found.append(
            Provocation(
                reactor_id=reactor.id,
                mover_id=mover_id,
                withheld=None if sight.can_see else SIGHT_UNSTATED,
            )
        )
    return tuple(found)
