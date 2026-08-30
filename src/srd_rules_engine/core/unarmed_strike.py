"""p. 190's other two Unarmed Strike options: Grapple, and Shove's Prone half (0053).

> **Unarmed Strike.** Instead of using a weapon to make a melee attack, you can use a punch,
> kick, headbutt, or similar forceful blow. ... Whenever you use your Unarmed Strike, **choose
> one of the following options for its effect.**

Three options. **Damage** is an attack roll and lives in `core.combat` beside the machinery it
shares — cover, reach, the attack path. The two here are not attack rolls at all: each compels
a saving throw from the target and rolls nothing for the attacker, which is why they are a
separate module rather than a branch inside one.

## Both were blocked, and by three different things

They have been disclosed in `unarmed_strike_resolver`'s narration bounds since it shipped:

* **The size test** — "no more than one size larger than you" — needed a `Size`, which
  [0051](../../../docs/decisions/0051-a-size-is-stated-or-it-is-unknown.md) built.
* **Grapple's escape DC and the way out of it** needed p. 182's rules, which
  [0052](../../../docs/decisions/0052-the-exit-is-built-before-the-entrance.md) built. That
  ordering was the point: a condition the engine can impose and cannot lift ends a session.
* **"a Strength or Dexterity saving throw (it chooses which)"** needed a way for a creature
  that declares nothing to make a choice, which
  [0053](../../../docs/decisions/0053-the-target-chooses-and-the-engine-rolls.md) built.

## What each option does not do

**Shove pushes nobody** ([#345](https://github.com/eddiefiggie/srd-rules-engine/issues/345)).
p. 190 lets the attacker choose between pushing the target 5 feet away and knocking it Prone;
the push is forced movement relative to another creature, a primitive nothing here has and one
that should settle for Frightened, the Push mastery and Shove at once. Disclosed rather than
approximated, because a Shove that always knocks Prone is a Shove that decided the attacker's
choice for it.

**A grapple made here states no range.** p. 182 ends a grapple when "the distance between the
Grappled target and the grappler exceeds **the grapple's range**", and p. 190 states no range
for a grapple — it states the reach of the *strike* ("a target within 5 feet of you"), which is
the distance at which you may grapple rather than the distance at which the grapple holds.
Reading one as the other is an inference, and 0052 clause 3 already settled which way an
unstated bound resolves: the grapple is held rather than lifted
([#346](https://github.com/eddiefiggie/srd-rules-engine/issues/346)). The escape DC has no such
problem — p. 190 states it outright.
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
    condition_applied,
    save_compelled,
)
from srd_rules_engine.core.conditions import Condition, Grapple
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import (
    grapple_declared,
    no_more_than_one_size_larger,
    shove_prone_declared,
)
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import Combatant, EncounterState, ForcedSave

GRAPPLE_RULE_ID: Final = "unarmed-strike-grapple"
SHOVE_RULE_ID: Final = "unarmed-strike-shove"

#: p. 190 gives the target the choice, and names these two (0053).
SAVE_CHOICES: Final[tuple[str, ...]] = ("str", "dex")

#: R31. Every clause is asserted in `scripts/verify_d20_rules.py` against p. 190.
UNARMED_OPTIONS_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference="SRD v5.2.1, Rules Glossary: Unarmed Strike p. 190; Grappling p. 182",
    date="2026-08-30",
    method=VerificationMethod.ASSERTED,
)


def option_dc(actor: Combatant) -> int:
    """p. 190's DC, shared by both options and by the escape attempts a grapple allows.

    > The DC for the saving throw **and any escape attempts** equals 8 plus your Strength
    > modifier and Proficiency Bonus.

    **Unconditional, like p. 190's attack bonus and unlike a weapon's.** There is no
    proficiency to have with your own body, so the bonus is added flat — the same reading
    `unarmed_strike_resolver` takes for the Damage option.
    """
    return 8 + actor.modifier("str") + actor.proficiency_bonus


def _dc_basis(actor: Combatant) -> str:
    return (
        f"8 + {actor.modifier('str')} Strength modifier + {actor.proficiency_bonus} "
        f"Proficiency Bonus = {option_dc(actor)} (p. 190)"
    )


def _target_of(
    state: EncounterState, actor: Combatant, target_id: str | None, what: str
) -> Combatant:
    if target_id is None:
        raise ValueError(f"this declaration is not {what}: it names something else")
    target = state.combatant(target_id)
    if not no_more_than_one_size_larger(actor, target):
        raise ValueError(
            f"p. 190 permits this only if {target.name} is no more than one size larger than "
            f"{actor.name}, and that comparison "
            + (
                "does not hold"
                if actor.size is not None and target.size is not None
                else "cannot be made — one of them has no stated size (R31)"
            )
        )
    return target


def grapple_resolver() -> Resolver:
    """p. 190's Grapple option.

    > **Grapple.** The target must succeed on a Strength or Dexterity saving throw (it chooses
    > which), or it has the Grappled condition. ... This grapple is possible only if the target
    > is no more than one size larger than you **and if you have a hand free to grab it**.

    **The attacker rolls nothing.** There is no attack roll in this option — the whole of it is
    a save the target owes — so this is a testless proposal (0027 clause 6) whose outcome is
    the compelled save itself.

    **A free hand is required and an unknown hand count refuses.** `Combatant.hands` is
    `int | None` because no SRD rule states how many hands a creature has (0039), so
    `free_hands` is `None` for a creature whose ruleset never said. p. 190 asks for a free hand
    outright, and a creature that cannot be shown to have one has not been shown to satisfy the
    rule — offering the grapple anyway would be the engine granting a hand nobody stated.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        target = _target_of(
            state, actor, grapple_declared(declaration.intent.action_key), "a Grapple"
        )
        if not actor.free_hands:
            raise ValueError(
                f"p. 190 grapples only 'if you have a hand free to grab it', and {actor.name} "
                + (
                    "has none free"
                    if actor.free_hands == 0
                    else "has no stated hand count, so a free one cannot be shown (R31)"
                )
            )

        dc = option_dc(actor)
        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on the Attack (p. 176, p. 177)",
                ),
            ),
            outcome=(
                save_compelled(
                    target.id,
                    ForcedSave(
                        combatant_id=target.id,
                        rule_id=GRAPPLE_RULE_ID,
                        ability="",
                        dc=dc,
                        dc_basis=_dc_basis(actor),
                        label=f"the save {actor.name}'s grapple compels (p. 190)",
                        ability_choices=SAVE_CHOICES,
                        source_id=actor.id,
                    ),
                    description=(
                        f"{actor.name} grabs at {target.name}, compelling a DC {dc} save "
                        "the target chooses the ability for (p. 190)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/unarmed-strike",),
            may_claim=(
                f"that {actor.name} seized, clutched or took hold of {target.name}",
                "that the outcome is not settled until the target's save is rolled",
            ),
            may_not_claim=(
                "that the target is grappled — nothing is decided until the save resolves",
                "that the grapple deals damage; p. 190 makes Damage a different option",
            ),
        )

    return resolve


def shove_resolver() -> Resolver:
    """p. 190's Shove option, taking the Prone effect of the two it offers.

    > **Shove.** The target must succeed on a Strength or Dexterity saving throw (it chooses
    > which), or you either push it 5 feet away or cause it to have the Prone condition.

    **No free hand is required**, and that is the document's own distinction rather than an
    omission here: p. 190 asks for one in the Grapple sentence and not in this one.

    The push half is #345, disclosed at the read surface. The attacker chooses which effect,
    so the choice is which action key it declares — and only one key exists, which is exactly
    what the disclosure says.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        target = _target_of(
            state, actor, shove_prone_declared(declaration.intent.action_key), "a Shove"
        )

        dc = option_dc(actor)
        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on the Attack (p. 176, p. 177)",
                ),
            ),
            outcome=(
                save_compelled(
                    target.id,
                    ForcedSave(
                        combatant_id=target.id,
                        rule_id=SHOVE_RULE_ID,
                        ability="",
                        dc=dc,
                        dc_basis=_dc_basis(actor),
                        label=f"the save {actor.name}'s shove compels (p. 190)",
                        ability_choices=SAVE_CHOICES,
                        source_id=actor.id,
                    ),
                    description=(
                        f"{actor.name} shoves at {target.name}, compelling a DC {dc} save "
                        "the target chooses the ability for (p. 190)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/unarmed-strike",),
            may_claim=(
                f"that {actor.name} drove a shoulder, palm or hip into {target.name}",
                "that the outcome is not settled until the target's save is rolled",
            ),
            may_not_claim=(
                "that the target fell — nothing is decided until the save resolves",
                "that the target was pushed anywhere; this engine offers only p. 190's Prone "
                "effect and says so",
            ),
        )

    return resolve


def _save_resolver(rule_id: str, condition: Condition, *, what: str) -> Resolver:
    """The save either option compels, and the condition its failure applies.

    One builder for both, because p. 190 states the two saves in the same words and they
    differ only in the condition a failure imposes — and, for a grapple, in the escape DC that
    travels with it.
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
                f"{actor.name} owes no save, so there is nothing for p. 190's {what} to "
                "resolve. The save is read off the debt the engine recorded when the option "
                "was taken, and it is never declared"
            )
        if debt.rule_id != rule_id:
            raise ValueError(
                f"{actor.name} owes a {debt.rule_id!r} save, not p. 190's {what}. One queue "
                "serves every forced save since 0048, so a resolver reached for the wrong "
                "debt is the loop and the rule having come apart"
            )
        if not debt.is_settled:
            raise ValueError(
                f"{actor.name} has not chosen which ability to save with, and p. 190 gives "
                f"that choice to the target ({', '.join(debt.ability_choices)}). Rolling one "
                "now would be the engine choosing, which is what 0053 exists to refuse"
            )

        return Proposal(
            test=D20Test(
                kind=TestKind.SAVE,
                ability=debt.ability,
                target=debt.dc,
                target_basis=debt.dc_basis,
                modifiers=(
                    Modifier(source=f"ability:{debt.ability}", value=actor.modifier(debt.ability)),
                ),
            ),
            # p. 190 states one consequence and states it for the failure. Success is the
            # absence of that, so it carries no effect.
            on_success=(),
            on_failure=(
                condition_applied(
                    actor_id,
                    condition,
                    description=(
                        f"the DC {debt.dc} {debt.ability} save failed, and p. 190's {what} "
                        f"applies the {condition.value.title()} condition"
                    ),
                    source_id=debt.source_id,
                    # p. 190: the DC "and any escape attempts" are the same number, so the
                    # grapple carries it out of here — p. 182 reads it back and nothing
                    # recomputes it (0052 clause 4). The range is unstated (#346).
                    grapple=(
                        Grapple(escape_dc=debt.dc, range_feet=None)
                        if condition is Condition.GRAPPLED
                        else None
                    ),
                ),
            ),
            citations=("srd:rules-glossary/unarmed-strike",),
            may_claim=(
                f"that {actor.name} resisted, or did not, as the roll says",
                f"that it saved with {debt.ability}, which was its own choice",
            ),
            may_not_claim=(
                f"that {actor.name} took damage from this save — p. 190 states none",
                "that anything followed a success; the document states no consequence for one",
            ),
        )

    return resolve


def grapple_save_resolver() -> Resolver:
    return _save_resolver(GRAPPLE_RULE_ID, Condition.GRAPPLED, what="Grapple")


def shove_save_resolver() -> Resolver:
    return _save_resolver(SHOVE_RULE_ID, Condition.PRONE, what="Shove")


def unarmed_option_rules() -> tuple[Rule, ...]:
    """All four, in a stable order: the two options and the two saves they compel."""
    return (
        Rule(
            id=GRAPPLE_RULE_ID,
            summary=(
                "p. 190's Grapple option compels a Strength or Dexterity saving throw the "
                "target chooses between, applying the Grappled condition on a failure."
            ),
            provenance=RuleProvenance.SRD,
            verification=UNARMED_OPTIONS_VERIFICATION,
        ),
        Rule(
            id=SHOVE_RULE_ID,
            summary=(
                "p. 190's Shove option compels a Strength or Dexterity saving throw the "
                "target chooses between, applying the Prone condition on a failure."
            ),
            provenance=RuleProvenance.SRD,
            verification=UNARMED_OPTIONS_VERIFICATION,
        ),
    )


def unarmed_option_resolvers() -> dict[str, Resolver]:
    """Keyed by rule id.

    **The option and the save it compels share a rule id**, and are told apart by whether the
    creature owes a debt: the declaration comes from the attacker and the save from the target,
    so one id names one rule of the document exactly as 0052 gave both escape checks one.
    """
    return {
        GRAPPLE_RULE_ID: _either(grapple_resolver(), grapple_save_resolver()),
        SHOVE_RULE_ID: _either(shove_resolver(), shove_save_resolver()),
    }


def _either(option: Resolver, save: Resolver) -> Resolver:
    """The option when the actor declared it, the save when the actor owes one."""

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        owed = state.forced_save_for(declaration.actor_id)
        chosen = save if owed is not None and declaration.intent.action_key is None else option
        return chosen(state=state, declaration=declaration, facts=facts)

    return resolve
