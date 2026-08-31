"""p. 183's Hide action: the check, the conditions it needs, and the four ways it ends.

> With the Hide action, you try to hide yourself. To do so, you must succeed on a **DC 15
> Dexterity (Stealth) check** while you're **Heavily Obscured or behind Three-Quarters Cover
> or Total Cover**, and you must be **out of any enemy's line of sight**; if you can see a
> creature, you can discern whether it can see you. On a successful check, you have the
> **Invisible** condition while hidden. Make note of your **check's total**, which is the DC
> for a creature to find you with a Wisdom (Perception) check. You stop being hidden
> immediately after any of the following occurs: you make a sound louder than a whisper, an
> enemy finds you, you make an attack roll, or you cast a spell with a Verbal component.

Nothing here is new machinery. Every piece it needs arrived for something else:

* **Three-Quarters and Total Cover** — `core.obstructions.cover_between`, directional by the
  line test, with the degree stated on the barrier (#416).
* **Heavily Obscured** — `core.sight.obscurement_at`.
* **Out of line of sight** — `EncounterState.can_see`.
* **Invisible** — one of the fifteen, and `Conditions.causes` scopes its ending to *this*
  rule so a creature Invisible by other means is not revealed by drawing a bow (0083).
* **The check's total as a DC** — the `D20Result` is in hand before effects are settled, so
  the engine fills the number and no caller supplies one (R4).

## The total is declared, never supplied

p. 183 makes the DC *the roll*. A resolver returning `Effect(amount=17)` would be a caller
supplying a result, which R4 exists to make impossible — and it could not know the number
anyway. So `HidingTotal` is declared the way `DamageDice` and `HealingDice` are, and the
engine settles it from the roll it just made.

This is **not** the gap [#216](https://github.com/eddiefiggie/srd-rules-engine/issues/216)
names. That one is a magnitude derived from a *sibling effect's settled damage*, which
nothing can express. This one derives from the test's own total, which `adjudicate` has in
hand two lines before it builds the branch.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    HidingTotal,
    Proposal,
    Resolver,
    condition_applied,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.obstructions import Cover, cover_between
from srd_rules_engine.core.read_surface import HIDE_DC
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.sight import Visibility
from srd_rules_engine.core.skills import Skill
from srd_rules_engine.core.state import HIDE_RULE_ID, Combatant, EncounterState

#: p. 183: the degrees that will do. Half Cover will **not** — the entry names
#: Three-Quarters and Total and stops, and admitting Half would be a rule the document
#: does not state, in the direction that helps the hider.
HIDING_COVER: Final[frozenset[Cover]] = frozenset({Cover.THREE_QUARTERS, Cover.TOTAL})

HIDE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Rules Glossary -> Hide, p. 183 ("you must succeed on a DC 15 Dexterity '
        "(Stealth) check while you're Heavily Obscured or behind Three-Quarters Cover or "
        "Total Cover, and you must be out of any enemy's line of sight\"; the Invisible "
        "condition, the check's total as the DC to find you, and the four ways hiding ends)"
    ),
    date="2026-08-31",
    method=VerificationMethod.ASSERTED,
)


def hide_rule() -> Rule:
    return Rule(
        id=HIDE_RULE_ID,
        summary=(
            "The Hide action makes a DC 15 Dexterity (Stealth) check, available only while "
            "the creature is Heavily Obscured or behind Three-Quarters or Total Cover and "
            "out of every enemy's line of sight. On a success it has the Invisible condition "
            "while hidden, and the check's total is the DC to find it."
        ),
        provenance=RuleProvenance.SRD,
        verification=HIDE_VERIFICATION,
    )


def refusal_to_hide(state: EncounterState, actor: Combatant) -> str | None:
    """Why p. 183 will not let this creature hide, or `None` if it may try.

    Two conditions, and **both** must hold. The entry joins them with "and", so a creature
    behind a boulder that an enemy is watching may not hide, and neither may one nobody can
    see standing in the open.

    **Every enemy, not any.** "out of **any** enemy's line of sight" is a universal in the
    document's phrasing — one watcher is enough to prevent it — and reading it as "some
    enemy cannot see you" would let a creature hide in front of a crowd because one of them
    happened to be Blinded.

    A creature the engine cannot place, or an encounter with no positions, gets `None` from
    the cover test rather than an invented barrier — so the obscurement half must carry it,
    which is the same refusal `_refuse_if_behind_total_cover` makes.
    """
    enemies = [other for other in state.combatants if other.id != actor.id and not other.is_down]

    watching = [
        other.name
        for other in enemies
        if state.can_see(other.id, actor.id).verdict is Visibility.CAN_SEE
    ]
    if watching:
        return (
            f"{', '.join(watching)} can see {actor.name}, and p. 183 requires being out of "
            "any enemy's line of sight"
        )

    # **`UNSTATED` blocks, and reading it as "cannot see" is the bug this is written
    # against.** p. 182's third value is not "we have not built it" — it is *the document
    # does not say*, and an encounter tracking no positions returns it for every pair. Taking
    # it as an answer would let a creature standing in an open room with no positional data
    # hide from everyone in it, which is the engine inventing the fact p. 183 asks for
    # (0025 clause 2, #166).
    unstated = [
        other.name
        for other in enemies
        if state.can_see(other.id, actor.id).verdict is Visibility.UNSTATED
    ]
    if unstated:
        return (
            f"this engine cannot say whether {', '.join(unstated)} can see {actor.name}, and "
            "p. 183 needs that answered. `Visibility.UNSTATED` is the document declining to "
            "say rather than a 'no' to build on"
        )

    if _heavily_obscured(state, actor):
        return None

    here = actor.position
    placed = [other.position for other in enemies if other.position is not None]
    if (
        here is not None
        and placed
        and len(placed) == len(enemies)
        and all(cover_between(seat, here, state.obstructions) in HIDING_COVER for seat in placed)
    ):
        return None

    return (
        f"{actor.name} is neither Heavily Obscured nor behind Three-Quarters or Total Cover "
        "from every enemy, and p. 183 requires one of them. Half Cover is not among them"
    )


def _heavily_obscured(state: EncounterState, actor: Combatant) -> bool:
    """Whether nothing can see the creature for obscurement's sake (p. 181, p. 183).

    Read off the sight chain rather than recomputed: `can_see` already resolves light,
    senses and distance into a verdict, and p. 182 makes a creature trying to see into a
    Heavily Obscured space effectively Blinded. A second computation here would be a second
    answer to a question already settled (0025).
    """
    enemies = [other for other in state.combatants if other.id != actor.id and not other.is_down]
    return bool(enemies) and all(
        state.can_see(other.id, actor.id).verdict is Visibility.CANNOT_SEE for other in enemies
    )


def hide_resolver() -> Resolver:
    """p. 183's Hide: a DC 15 Dexterity (Stealth) check whose total becomes a DC.

    **The DC is the document's**, so no caller supplies one — unlike p. 187's Search and
    p. 189's Study, which state none and take theirs from the situation.

    **Stealth, and only Stealth.** p. 183 names the skill outright rather than suggesting it,
    so there is no skill parameter and no open set. A creature without the proficiency rolls
    its bare Dexterity modifier, which is what p. 188 gives it.

    **The preconditions are re-checked here as well as at the offer**, for `_push`'s reason:
    a menu is a menu, not a promise about what will arrive.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        refusal = refusal_to_hide(state, actor)
        if refusal is not None:
            raise ValueError(f"p. 183 does not allow this Hide: {refusal}")

        return Proposal(
            test=D20Test(
                kind=TestKind.CHECK,
                ability="dex",
                target=HIDE_DC,
                target_basis=f"DC {HIDE_DC}, stated by p. 183 rather than by the situation",
                modifiers=(
                    Modifier(
                        source=f"skill:{Skill.STEALTH.value}",
                        value=actor.check_bonus(Skill.STEALTH),
                    ),
                ),
            ),
            on_success=(
                condition_applied(
                    actor.id,
                    Condition.INVISIBLE,
                    description="hidden, and p. 183 gives the Invisible condition while so",
                    caused_by=HIDE_RULE_ID,
                ),
                HidingTotal(target_id=actor.id),
            ),
            # p. 183 states nothing for a failure — no noise, no penalty, no bar on trying
            # again. An effect here would be a consequence the document does not give.
            on_failure=(),
            citations=("srd:rules-glossary/hide",),
            may_claim=(
                f"that {actor.name} tried to hide, and how the check came out",
                f"that {actor.name} is hidden if it succeeded, and unseen while it lasts",
            ),
            may_not_claim=(
                f"that {actor.name} is hidden from anything the check did not establish",
                "that the hiding survives an attack, a Verbal spell, a noise louder than a "
                "whisper, or an enemy finding it — p. 183 ends it on all four",
                f"that anything failed to notice {actor.name} without rolling for it",
            ),
        )

    return resolve
