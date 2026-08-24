"""Death saving throws: what happens to a player character at 0 hit points.

R12's share of "dropping to 0". U12 built the fall; this is what follows it.

The rules are read off SRD v5.2.1, "Playing the Game" ("Damage and Healing" -> "Death
Saving Throws" and "Damage at 0 Hit Points"), pp. 17-18, with the Rules Glossary entry on
p. 181. `DEATH_SAVE_VERIFICATION` carries the citation and
`scripts/verify_d20_rules.py` re-checks the sentences it rests on.

## What makes this a d20 test like any other

The save resolves through the same primitive as everything else (R11) with a target of 10.
Two things about it are unusual and both are stated rather than inferred:

* **It is tied to no ability score.** "Unlike other saving throws, this one isn't tied to
  an ability score. You're in the hands of fate now." So the proposal carries no modifiers,
  and that emptiness is the rule rather than an omission.
* **The natural die matters beyond success and failure.** A natural 1 costs two failures
  and a natural 20 restores a hit point. Neither is expressible as "the save succeeded" or
  "the save failed", which is why `Proposal` grew `on_natural_20` and `on_natural_1`.

## What is deliberately absent

Three parts of the same pages are **not** modelled here, and they ship disclosed rather
than silently missing:

* **The Unconscious condition is modelled but not applied here.** `core.conditions` now
  carries it with its effects, and p. 18 says a Stable creature "still has the Unconscious
  condition" — but nothing in this module applies it when a creature reaches 0 hit points.
  A caller must set it. That is a narrower gap than before and still a gap.
* **Stabilizing by the Help action**, which needs a DC 10 Wisdom (Medicine) check and an
  action economy to spend the action from — [#16](https://github.com/eddiefiggie/srd-rules-engine/issues/16).
  `EncounterState.with_stabilised` exists, so the state transition is there; nothing yet
  reaches it through a ruling.
p. 18's *"A Stable creature that isn't healed regains 1 Hit Point after 1d4 hours"* is no
longer among them. `core.clock` is the campaign time it needed, the 1d4 is rolled when the
creature becomes Stable rather than when somebody asks, and `EncounterState.with_time_passed`
applies it. Recovery restores a hit point and no more: p. 18 does not say the Unconscious
condition ends, so this engine does not end it either.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Effect,
    EffectKind,
    Proposal,
    Resolver,
)
from srd_rules_engine.core.d20 import D20Test, TestKind
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

#: p. 17: "Roll 1d20. If the roll is 10 or higher, you succeed. Otherwise, you fail."
DEATH_SAVE_DC: Final = 10

#: R31. Its own citation rather than a clause on the d20 primitive's, because these
#: sentences sit in "Damage and Healing" rather than in "D20 Tests".
DEATH_SAVE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Playing the Game" ("Damage and Healing" -> "Death Saving Throws" '
        'and "Damage at 0 Hit Points"), pp. 17-18; Rules Glossary, Death Saving Throw '
        "p. 181"
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)


def death_save_resolver() -> Resolver:
    """Build the resolver for a death saving throw.

    A resolver like any other, so the save reaches an outcome only through the one
    adjudication entry point (R1) and the engine rolls it (R4). Nothing here decides
    whether the save was warranted — `Combatant.makes_death_saves` answers that, and the
    turn loop is what consults it.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        if not actor.makes_death_saves:
            raise ValueError(
                f"{actor.name} is not making death saving throws. They are made at 0 hit "
                "points by a creature that is neither Stable nor dead (p. 17)"
            )

        return Proposal(
            test=D20Test(
                kind=TestKind.SAVE,
                target=DEATH_SAVE_DC,
                target_basis=(
                    "death saving throw, DC 10 — tied to no ability score, so no modifier "
                    "applies (p. 17)"
                ),
            ),
            on_success=(_mark(actor_id, EffectKind.DEATH_SAVE_SUCCESS, 1, "a success"),),
            on_failure=(_mark(actor_id, EffectKind.DEATH_SAVE_FAILURE, 1, "a failure"),),
            # p. 18. Both are "instead of", not "as well as", which is why they are their
            # own branches rather than extra effects appended to the ordinary ones.
            on_natural_20=(
                Effect(
                    kind=EffectKind.HEALING,
                    target_id=actor_id,
                    amount=1,
                    description=(
                        "natural 20 on a death saving throw: regain 1 hit point (p. 18). "
                        "Regaining hit points resets both counts to zero (p. 17)"
                    ),
                ),
            ),
            on_natural_1=(_mark(actor_id, EffectKind.DEATH_SAVE_FAILURE, 2, "two failures"),),
            citations=("srd:playing-the-game/damage-and-healing/death-saving-throws",),
            may_claim=(
                "that the save resolved as the roll says",
                "that the character is closer to death or to stability by the marks recorded",
            ),
            may_not_claim=(
                "that the character died, unless the ruling recorded a third failure",
                "that the character stabilised, unless the ruling recorded a third success",
                "that the character woke, acted, or spoke — a creature at 0 hit points "
                "does none of those, and the Unconscious condition is not yet modelled",
            ),
        )

    return resolve


def _mark(actor_id: str, kind: EffectKind, amount: int, phrase: str) -> Effect:
    """One death save mark. "A success or failure has no effect by itself" (p. 17)."""
    return Effect(
        kind=kind,
        target_id=actor_id,
        amount=amount,
        description=(
            f"death saving throw: {phrase}. Three of a kind resolves it — three successes "
            "and the character is Stable, three failures and the character dies (p. 17)"
        ),
    )
