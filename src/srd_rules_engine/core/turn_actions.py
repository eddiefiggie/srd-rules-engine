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
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.adjudicate import (
    Declaration,
    Effect,
    EffectKind,
    Proposal,
    Resolver,
    action_spent,
    dashed,
    disengaged,
    dodging_taken,
)
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
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
from srd_rules_engine.core.skills import SKILL_ABILITY, Skill
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


# --- The two actions that make a check the document gives no DC for (p. 187, p. 189) ----

SEARCH_RULE_ID: Final = "srd:rules-glossary/search"
STUDY_RULE_ID: Final = "srd:rules-glossary/study"

#: p. 187's Search table, and p. 189's Areas of Knowledge. **Suggested, not required** —
#: both entries say the table "suggests which skills are applicable", so these are held so a
#: caller can be *offered* them and never to refuse one that is absent.
#:
#: Every skill the document lists for Search is a Wisdom skill and every one it lists for
#: Study is an Intelligence skill, which is what makes the ability check below a reading of
#: the tables rather than a rule imported from outside them.
SEARCH_SKILLS: Final[Mapping[Skill, str]] = MappingProxyType(
    {
        Skill.INSIGHT: "a creature's state of mind",
        Skill.MEDICINE: "a creature's ailment or cause of death",
        Skill.PERCEPTION: "a concealed creature or object",
        Skill.SURVIVAL: "tracks or food",
    }
)

STUDY_SKILLS: Final[Mapping[Skill, str]] = MappingProxyType(
    {
        Skill.ARCANA: "spells, magic items, eldritch symbols, magical traditions, planes of "
        "existence, and certain creatures",
        Skill.HISTORY: "historic events and people, ancient civilizations, wars, and certain "
        "creatures",
        Skill.INVESTIGATION: "traps, ciphers, riddles, and gadgetry",
        Skill.NATURE: "terrain, flora, weather, and certain creatures",
        Skill.RELIGION: "deities, religious hierarchies and rites, holy symbols, cults, and "
        "certain creatures",
    }
)

INSPECTION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Rules Glossary: Search p. 187 ("you make a Wisdom check to discern '
        'something that isn\'t obvious"), Study p. 189 ("you make an Intelligence check to '
        'study your memory, a book, a clue, or another source of knowledge"), with both '
        "skill tables"
    ),
    date="2026-08-31",
    method=VerificationMethod.ASSERTED,
)


def search_rule() -> Rule:
    return Rule(
        id=SEARCH_RULE_ID,
        summary=(
            "The Search action makes a Wisdom check to discern something that is not "
            "obvious. The document suggests Insight, Medicine, Perception and Survival "
            "depending on what is being detected, and states no DC."
        ),
        provenance=RuleProvenance.SRD,
        verification=INSPECTION_VERIFICATION,
    )


def study_rule() -> Rule:
    return Rule(
        id=STUDY_RULE_ID,
        summary=(
            "The Study action makes an Intelligence check to call to mind an important piece "
            "of information. The document suggests Arcana, History, Investigation, Nature "
            "and Religion depending on the area of knowledge, and states no DC."
        ),
        provenance=RuleProvenance.SRD,
        verification=INSPECTION_VERIFICATION,
    )


def _inspection_resolver(
    *,
    rule_id: str,
    label: str,
    page: int,
    ability: str,
    suggested: Mapping[Skill, str],
    citation: str,
    dc: int,
    basis: str,
    skill: Skill | None,
) -> Resolver:
    """Search and Study are one mechanism differing in ability and table.

    p. 187 and p. 189 are the same sentence twice: take the action, make a check of a named
    ability to learn something. Building them separately would be two implementations of one
    rule, which 0013's `mechanism-not-exemplar` criterion is about — they stay two *shapes*
    because the document gives each its own entry, its own ability and its own table.

    **The DC is the caller's and is recorded with its derivation.** Neither entry states one,
    which is `perception_resolver`'s situation exactly: "a DC the document does not state must
    say where it came from" (R5). Setting it is interpretation, which is the agent's half;
    rolling against it is the outcome, which is never.

    **The skill is optional, because the tables only suggest.** Both entries say the table
    "suggests which skills are applicable", so a check with no skill is a plain ability check
    and is legal. What is refused is a skill of the *wrong ability* — a Proficiency Bonus in
    an Intelligence skill cannot reach a Wisdom check, and every skill in the document's own
    table for each action is of that action's ability. That refusal is a modelling judgement
    read off the tables rather than a sentence the document states, and it is disclosed as
    one here rather than presented as a rule.
    """

    if skill is not None and SKILL_ABILITY[skill] != ability:
        raise ValueError(
            f"{skill.value} is a {SKILL_ABILITY[skill]} skill and p. {page}'s {label} is "
            f"an {ability} check, so its Proficiency Bonus cannot apply. Every skill the "
            f"document suggests for {label} is an {ability} skill; a check with no skill at "
            "all is legal and is what an unsuggested area of expertise gets"
        )

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        bonus = actor.check_bonus(skill) if skill is not None else actor.modifier(ability)
        source = f"skill:{skill.value}" if skill is not None else f"ability:{ability}"

        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description=f"the Action spent on the {label} (p. 176, p. {page})",
                ),
            ),
            test=D20Test(
                kind=TestKind.CHECK,
                ability=ability,
                target=dc,
                target_basis=basis,
                modifiers=(Modifier(source=source, value=bonus),),
            ),
            citations=(citation,),
            may_claim=(
                f"that {actor.name} took the {label} and the check came out as the roll says",
                f"what a success establishes: {suggested.get(skill, 'what was looked for')}"
                if skill is not None
                else f"that {actor.name} learned what the check was set to establish",
            ),
            may_not_claim=(
                f"that {actor.name} learned anything the check did not establish",
                f"that the DC was the rules' rather than the caller's — p. {page} states "
                "none, and this one came from: " + basis,
                "that a failure means the thing is not there; it means it was not found",
            ),
        )

    return resolve


def search_resolver(*, dc: int, basis: str, skill: Skill | None = None) -> Resolver:
    """p. 187's Search: a Wisdom check to discern something that is not obvious."""
    return _inspection_resolver(
        rule_id=SEARCH_RULE_ID,
        label="Search",
        page=187,
        ability="wis",
        suggested=SEARCH_SKILLS,
        citation="srd:rules-glossary/search",
        dc=dc,
        basis=basis,
        skill=skill,
    )


def study_resolver(*, dc: int, basis: str, skill: Skill | None = None) -> Resolver:
    """p. 189's Study: an Intelligence check to call to mind an important piece of
    information."""
    return _inspection_resolver(
        rule_id=STUDY_RULE_ID,
        label="Study",
        page=189,
        ability="int",
        suggested=STUDY_SKILLS,
        citation="srd:rules-glossary/study",
        dc=dc,
        basis=basis,
        skill=skill,
    )


# --- p. 184's first aid, the other way a knocked-out creature wakes (0083, #428) ---------

FIRST_AID_RULE_ID: Final = "srd:rules-glossary/knocking-out-a-creature/first-aid"

#: p. 184: "someone uses an action to administer first aid to it, which requires a successful
#: **DC 10 Wisdom (Medicine) check**." The DC is the document's, unlike p. 187's Search and
#: p. 189's Study — so no caller supplies one here, and none may.
FIRST_AID_DC: Final = 10

FIRST_AID_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Rules Glossary -> Knocking Out a Creature ("The creature remains '
        "Unconscious until it regains any Hit Points or until someone uses an action to "
        "administer first aid to it, which requires a successful DC 10 Wisdom (Medicine) "
        'check"), p. 184'
    ),
    date="2026-08-31",
    method=VerificationMethod.ASSERTED,
)


def first_aid_rule() -> Rule:
    return Rule(
        id=FIRST_AID_RULE_ID,
        summary=(
            "A creature uses its Action to administer first aid to a creature knocked out by "
            "a subduing blow, making a DC 10 Wisdom (Medicine) check. On a success the "
            "target stops being Unconscious."
        ),
        provenance=RuleProvenance.SRD,
        verification=FIRST_AID_VERIFICATION,
    )


def first_aid_resolver(*, patient_id: str) -> Resolver:
    """p. 184's first aid: an Action and a DC 10 Wisdom (Medicine) check.

    **The DC is the document's**, which is worth saying because p. 187's Search and p. 189's
    Study both leave theirs to the caller. Here p. 184 states it, so no caller supplies one
    and none may — a difficulty a rule gives is not a difficulty a situation sets.

    **Medicine, and only Medicine.** p. 184 names the skill outright, unlike the tables on
    pp. 187 and 189 which only *suggest*. So there is no skill parameter and no open set: a
    creature without the proficiency rolls its bare Wisdom modifier, which is what p. 188
    gives it.

    **Success ends only the Unconscious p. 184 caused** (0083). A creature Unconscious for
    another reason is not woken by a bandage, and p. 191's entry never says when the condition
    ends — so the ending belongs to the cause, and `EffectKind.FIRST_AID_GIVEN` is how the
    ruling names which one it means.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        patient = state.combatant(patient_id)

        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent administering first aid (p. 176, p. 184)",
                ),
            ),
            test=D20Test(
                kind=TestKind.CHECK,
                ability="wis",
                target=FIRST_AID_DC,
                target_basis=f"DC {FIRST_AID_DC}, stated by p. 184 rather than by the situation",
                modifiers=(
                    Modifier(
                        source=f"skill:{Skill.MEDICINE.value}",
                        value=actor.check_bonus(Skill.MEDICINE),
                    ),
                ),
            ),
            on_success=(
                Effect(
                    kind=EffectKind.FIRST_AID_GIVEN,
                    target_id=patient_id,
                    amount=0,
                    description=(
                        f"{patient.name} was knocked out and is roused by first aid (p. 184)"
                    ),
                ),
            ),
            # p. 184 states nothing for a failure — no damage, no worsening, no bar on trying
            # again. An effect here would be a consequence the document does not give.
            on_failure=(),
            citations=("srd:rules-glossary/knocking-out-a-creature",),
            may_claim=(
                f"that {actor.name} tended to {patient.name}, and how it went",
                f"that {patient.name} is awake, if the check succeeded",
            ),
            may_not_claim=(
                f"that {patient.name} regained any hit points — p. 184 restores none",
                f"that {patient.name} woke for any other reason it might be Unconscious; "
                "this rouses only a creature a subduing blow knocked out",
                "that a failure cost anything; p. 184 states no consequence for one",
            ),
        )

    return resolve
