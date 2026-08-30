"""The single path by which an outcome comes into existence.

R1 says no other API produces, modifies, or implies a result. Everything the engine can
say about what happened comes back from `adjudicate`, in a `Ruling` that carries enough
to explain it and enough to replay it.

The shape follows from three requirements that pull in the same direction:

- **R4 — the engine rolls.** A caller supplies neither a roll nor a *seed*. A seed is not
  a roll, but a caller who chooses it chooses the outcome by searching for a favourable
  one, so the engine draws its own from a source that is unpredictable by default. Tests
  substitute the source; nothing substitutes the value.
- **R5 — the Ruling shows its working.** Status, the test performed, the raw dice and the
  seed, the target number *and its derivation*, applied effects, every resolved fact with
  its provenance, the alternatives the declaration recorded with their verdict, citations,
  and narration bounds. A reader must be able to ask why a result came out this way from
  the record alone.
- **R26 — nothing escapes before its record is durable.** The whole adjudication runs
  inside one escape boundary: the declaration and the ruling reach storage in a single
  synchronising write, and a failure raises rather than returning a rules status.

**Validation uses the same legality derivation the read surface does** (R3, R18), so what
was offered and what is accepted cannot drift.

A rule is a *declaration* — verifiable, provenance-tracked, loaded through U7's gates — and
a **resolver** is the code that turns it into a target number and effects. Keeping them
apart is what the seed decision found the hard way: no dataset supplies effect shapes, so
the data is the numbers and the code is the meaning.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.canonical import MAX_SAFE_INTEGER
from srd_rules_engine.core.conditions import EFFECTS as CONDITION_EFFECTS
from srd_rules_engine.core.conditions import Condition, Grapple
from srd_rules_engine.core.d20 import (
    DAMAGE_OFFSET,
    DIE_SIDES,
    Advantage,
    Critical,
    D20Result,
    D20Test,
    TestKind,
)
from srd_rules_engine.core.d20 import resolve as roll_d20
from srd_rules_engine.core.d20 import roll as dice
from srd_rules_engine.core.damage import DamageOutcome, DamageType
from srd_rules_engine.core.duration import Duration
from srd_rules_engine.core.equipment import Carriage, items_in
from srd_rules_engine.core.ledger import COMPAT, Ledger
from srd_rules_engine.core.memory_port import (
    DefaultKind,
    FactType,
    MemoryPort,
    Resolution,
)
from srd_rules_engine.core.memory_port import (
    resolve as resolve_fact,
)
from srd_rules_engine.core.pending_rolls import PendingAdvantage
from srd_rules_engine.core.position import SpeedReduction
from srd_rules_engine.core.read_surface import LegalAction, Verdict, legal_actions, verify
from srd_rules_engine.core.rules import Ruleset
from srd_rules_engine.core.spellcasting import MAX_SPELL_LEVEL
from srd_rules_engine.core.state import Combatant, EncounterState, ForcedSave, grapples_released
from srd_rules_engine.core.triggers import Catalogue, MatchContext, Trigger, challenge_text

#: A payload's schema version says *what shape it is*. Its `compat` floor says *which
#: reader can read it*, and the two are different number lines — 0011 clause 3 versions the
#: schemas independently, so no single reader version could track all four. Setting a floor
#: from a schema version is what made every ruling entry unreadable (#106), and these
#: constants exist so the two numbers cannot be confused for one another again.
#:
#: They are raised when **this repository's reading surface** must change to read the
#: payload correctly — not when the payload changes. Decision 0022.
DECLARATION_COMPAT = 1
RULING_COMPAT = 1
NARRATION_COMPAT = 1
TERMINATION_COMPAT = 1

#: 2 adds `resumption` (#59). A block is a *suspension*: the turn loop re-adjudicates the
#: same declaration once the missing facts arrive, and the agent is never asked again — so
#: the second entry recorded an agent declaration that did not happen. Recorded as a field
#: rather than inferred from the preceding ruling's status, for the reason `testless` was:
#: a resumption and a genuine second declaration look identical from the surrounding
#: entries alone, and only one of them is the agent trying again.
DECLARATION_VERSION = 2
#: 2 records the advantage the test was declared under. A v1 roll cannot be reconstructed
#: — a reader would build a test with neither flag set, roll one die where two were rolled,
#: and report a mismatch that looks like drift. Replay refuses those rather than guessing.
#:
#: 3 changes what an effect's `amount` **means** for damage: it is now what the target took
#: after p. 17's defences, with `rolled` and `damage_type` alongside it (#105). This is not
#: an additive field — a v2 reader adding up `amount` gets a different total for the same
#: fight — so the version moves rather than the payload growing quietly.
#:
#: 4 adds `condition`, `duration` and `grappler` to an effect (#119). Purely additive: a v3
#: reader misreads nothing, it simply cannot see a condition effect's subject. So this moves
#: the version and **not** `RULING_COMPAT`, which is 0022's rule — compat is what a reader
#: must be to read the payload *correctly*, not a record of the payload having changed.
#:
#: 7 adds `when` to every effect and an optional `withheld` list beside `effects` (0032,
#: #173). Additive, and not a `RULING_COMPAT` move: a v6 reader sees the effects that
#: applied exactly as before and simply cannot see which of them were conditional, or that
#: any were withheld. That is less of the record rather than a wrong reading of it — the
#: same judgement `testless` got at 5.
#:
#: 6 renames an effect's `grappler` to `source` (#192). Grappled was the only condition
#: whose text turned on who imposed it until Frightened's line-of-sight qualifier became
#: enforceable, and a field named for one of two users is a field that misleads about the
#: other. Not additive — a v5 reader looking for `grappler` finds nothing — but not a
#: `RULING_COMPAT` move either, for #119's reason: such a reader misreads nothing, it simply
#: cannot see the condition's source.
#:
#: 5 adds `testless` (#170, 0027 clause 6). Also additive, and also not a `RULING_COMPAT`
#: move. It is recorded rather than inferred from `roll` being absent, because inferring is
#: how the advantage gap got in: `REPLAYABLE_FROM = 2` exists because a ruling made with
#: advantage replayed as though it had none. A v4 reader sees no `testless` key and reports
#: such an entry unreplayable, which is the old behaviour rather than a new wrong answer.
RULING_VERSION = 7
NARRATION_VERSION = 1
TERMINATION_VERSION = 1


class Status(StrEnum):
    """What an adjudication produced. Only `RULED` and `NO_TEST` are outcomes."""

    RULED = "ruled"
    NO_TEST = "no-test-accepted"
    CHALLENGED = "challenged"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class RejectionCode(StrEnum):
    """Why a declaration was refused, as a code rather than a sentence.

    The retry bound compares refusals structurally — never by message text, which is
    templated on situational values and would make two identical refusals look different.
    """

    UNKNOWN_ACTOR = "unknown-actor"
    ACTION_NOT_LEGAL = "action-not-legal"
    UNKNOWN_RULE = "unknown-rule"
    UNDECLARED_FACT = "undeclared-fact"


class EffectKind(StrEnum):
    DAMAGE = "damage"
    HEALING = "healing"
    #: Death saves (p. 17-18). Marks rather than hit points: a success or failure "has no
    #: effect by itself", so they are their own effect rather than a healing of zero.
    DEATH_SAVE_SUCCESS = "death-save-success"
    DEATH_SAVE_FAILURE = "death-save-failure"
    STABILISED = "stabilised"
    DEATH = "death"
    #: A condition imposed or lifted by the ruling that caused it (#119). Before these,
    #: conditions reached state only through `EncounterState.with_condition`, which callers
    #: invoked directly — a mechanical change with no roll, no seed, no citation and no
    #: ledger entry behind it, which is the thing R1 exists to prevent.
    CONDITION_APPLIED = "condition-applied"
    CONDITION_ENDED = "condition-ended"
    #: Exhaustion levels gained (#178). Its own kind rather than a `CONDITION_APPLIED` for
    #: `Condition.EXHAUSTION`, because applying that condition cannot say **how many**, and
    #: the level is where all of its arithmetic lives — p. 181 reduces every D20 Test by
    #: twice the level and Speed by five feet times it, and kills at 6. A condition applied
    #: with no level attached is the one member of the fifteen that carries no effect.
    #:
    #: `amount` is the number of levels, as the death-save kinds use it for marks. Every
    #: SRD rule that grants Exhaustion grants exactly one, so the field is generality rather
    #: than a case anything exercises today.
    EXHAUSTION_GAINED = "exhaustion-gained"
    #: The Dash action's extra movement (p. 180). `amount` is the feet gained, which is the
    #: creature's speed **after modifiers** and in the mode it chose — p. 180 offers the
    #: choice ("you can use that speed instead of your Speed… You choose which speed to use
    #: each time you take it"), so the number is settled where the choice is offered.
    DASHED = "dashed"
    #: The Dodge action taken (p. 181). Carries no number: the benefits are stated, and
    #: whether they hold is re-asked whenever they are read rather than frozen here.
    DODGING = "dodging"
    #: The Disengage action taken (p. 181): movement does not provoke for the rest of the turn.
    DISENGAGED = "disengaged"
    #: A spell slot spent to cast a spell (p. 104, 0038 clause 6). `amount` is the **slot**
    #: level, which is not always the spell's — p. 104 lets a spell be cast "at a slot's
    #: level or higher", and what the extra level does is the spell's description's business.
    #:
    #: The first effect kind that is a **cost** rather than a consequence. It applies because
    #: the casting happened, not because a branch was selected, which is what `Proposal.always`
    #: is for.
    SPELL_SLOT_EXPENDED = "spell-slot-expended"
    #: An action spent by the thing that was declared (p. 185, p. 176-177). `amount` is
    #: unused and 0; which action it was is `ActionKind`, carried in `action`.
    #:
    #: **The first time the action economy is charged by an adjudication.** `ActionBudget`
    #: has been complete and tested since the economy landed, and `spend` had no caller
    #: outside `dodging()` — so an attack does not cost the Action to this day. Casting is
    #: charged because p. 185 states the cost as part of the act; the rest of the economy is
    #: a separate gap, filed rather than quietly half-fixed here.
    ACTION_SPENT = "action-spent"
    #: Concentration begun (p. 179, 0038 clause 7). What it is **on** is the ruling's own rule
    #: id, taken the way `EXHAUSTION_GAINED` takes it (0028 clause 1) — from `_apply`'s
    #: `rule_id` rather than from a field here, so no effect can claim a source its ruling did
    #: not have. That is also why p. 179's "or activate another effect" is expressible: a rule
    #: id says which mechanic, and says nothing about it being a spell.
    CONCENTRATION_BEGUN = "concentration-begun"
    #: Concentration broken by a failed save (0036 clause 1). Its own kind rather than a
    #: `CONDITION_ENDED`, because Concentration is not one of the fifteen conditions the
    #: glossary tags — it is per-creature state, which is 0027 clause 5's reasoning applied
    #: to the effect that ends it as well as to the field that holds it.
    #:
    #: Carries no number: p. 179 gives the save one consequence and it is not a quantity.
    CONCENTRATION_ENDED = "concentration-ended"
    #: An item let go of by the ruling that caused it (0041 clause 7, #280). `item_id` names
    #: which; `amount` is unused and 0.
    #:
    #: **Detachment is an outcome, not bookkeeping.** p. 191 makes it a consequence of a
    #: condition and p. 130 of a failed save, so a caller reaching past adjudication to move
    #: an item out of a hand would be a caller deciding one — the thing #119 stopped for
    #: conditions and R1 exists to prevent generally.
    #:
    #: **It carries no position, and that is 0041 clause 4 rather than an omission.** None of
    #: the five printed rules that detach an item says where it lands, so the object arrives
    #: unplaced and the read surface reports it as such. The three texts that *do* state a
    #: destination — pp. 209, 217, 247 — are magic items stating their own outcome, and this
    #: repository ships no magic items (R31). A field nothing sets is the decay #228, #215
    #: and #252 each found, so the rule that needs one brings it.
    OBJECT_DETACHED = "object-detached"
    #: An item moved between carriages the creature already keeps it in (p. 177, 0042
    #: clause 4): "drawing it from a sheath", "sheathing, stowing". `item_id` names which and
    #: `carriage` says where it went. The item never leaves the creature, which is what
    #: separates it from `OBJECT_DETACHED`.
    CARRIAGE_CHANGED = "carriage-changed"
    #: A detached object taken into a creature's hands (p. 177, 0042 clause 4) — "picking it
    #: up", which is `OBJECT_DETACHED` run backwards. It arrives `HELD`, because p. 177 puts
    #: this in a sentence about *equipping* a weapon.
    OBJECT_PICKED_UP = "object-picked-up"
    #: One attack roll made, counted against this turn's Multiattack allowance (p. 257, 0043
    #: clause 4). Its own kind rather than a field on `ACTION_SPENT`, because a Multiattack's
    #: second and third rolls spend **no** action — the Action was spent buying all of them.
    ATTACK_MADE = "attack-made"
    #: This turn's one object interaction, spent (0045 clause 1). Its own kind rather than
    #: inferred from the carriage change beside it, because p. 191's Unconscious also detaches
    #: an item and must not spend an allowance the creature never chose to use.
    #:
    #: Named for the **allowance**, not the move: p. 177's swap and p. 13's free interaction
    #: are one budget, and either spends this.
    OBJECT_INTERACTED = "object-interacted"
    #: p. 90's one shot from a Loading weapon, fired with the action named in `action`
    #: (#271). Its own kind rather than a flag on `ATTACK_MADE`, because the cap is keyed by
    #: the **action used** and a Multiattack's later rolls spend no action of their own — so
    #: the pair this records is not recoverable from the attack tally beside it.
    LOADING_FIRED = "loading-fired"
    #: p. 89's one extra Light attack, taken this turn (#320). Its own kind, and it exists
    #: because p. 90's Nick removed the thing that used to record it. The Bonus Action spend
    #: *was* the bookkeeping — a second extra attack was refused because no Bonus Action
    #: remained — and a Nick attack spends nothing, so nothing stopped a creature taking one
    #: by each route. p. 90 says "as part of the Attack action **instead of** as a Bonus
    #: Action", which is one attack made one way or the other, and p. 89 grants "**one**
    #: extra attack" whichever way it is made.
    EXTRA_ATTACK_MADE = "extra-attack-made"
    #: A save a rule compelled, owed by `target_id` and not yet rolled (0048, #321). Its own
    #: kind because the debt is neither a condition nor a spend: it is an **obligation**, and
    #: the loop drains it through the one adjudication entry point rather than the effect
    #: deciding anything. The DC and its derivation ride on `forced_save`, computed where the
    #: trigger fired, because neither is recoverable by the time the save is rolled.
    SAVE_COMPELLED = "save-compelled"
    #: Advantage or Disadvantage granted for a **later** roll (p. 90, 0049). Its own kind
    #: because every other advantage in this engine is recomputed at the moment of the
    #: roll and nothing records it: these are held and spent, so the grant is a state
    #: change rather than a fact recomputed later.
    ADVANTAGE_PENDING = "advantage-pending"
    #: One of those tokens, consumed by the roll it applied to (0049). Spent whether the
    #: roll hit or missed — p. 90 says "your **next** attack roll" — so it is emitted
    #: from `Proposal.always` rather than from either branch.
    ADVANTAGE_SPENT = "advantage-spent"
    #: A melee hit that opens p. 90's Cleave (#323): the wielder may swing the same
    #: weapon at a second creature beside the first. Its own kind because the opening is
    #: a fact about *this* hit — which weapon, and whom it landed on — and the second
    #: attack's eligibility is measured from that creature rather than from the attacker.
    CLEAVE_OPENED = "cleave-opened"
    #: p. 90's Cleave attack, taken (#323). Its own record rather than p. 89's
    #: `EXTRA_ATTACK_MADE`, because "you can make **this** extra attack only once per
    #: turn" caps Cleave alone — spending it must not spend the Light property's.
    CLEAVE_TAKEN = "cleave-taken"
    #: A Speed reduction standing until a turn boundary (p. 90, #322). Its own kind
    #: because it is neither a condition nor a spend: nothing consumes it, and it ends
    #: by the encounter passing a boundary it names rather than by anything acting.
    SPEED_REDUCED = "speed-reduced"
    #: One piece of ammunition expended by an attack (p. 89, #273). `item_id` names which.
    #: "Each attack expends one piece of ammunition" — a cost that applies because the attack
    #: happened, so it rides in `Proposal.always` beside the action charge rather than in a
    #: hit branch. p. 89 does not return a piece on a miss.
    AMMUNITION_SPENT = "ammunition-spent"
    #: Ammunition recovered after a fight (p. 89, #301). `item_id` names which and `amount`
    #: is how many pieces came back — "half the ammunition (round down) you used in the
    #: fight; the rest is lost", so the fight's tally clears whatever the half came to.
    AMMUNITION_RECOVERED = "ammunition-recovered"
    #: Campaign minutes elapsed because a rule said so (#301). `amount` is the minutes.
    #:
    #: **This is rule-stated time, not the agent-supplied kind 0020 clause 3 governs.** That
    #: clause is about a narrative fact — "only the agent knows the party walked for three
    #: hours" — and p. 89 is not asking: "you can spend **1 minute** to recover half the
    #: ammunition". The agent decides *that* the recovery is attempted; the document decides
    #: what it costs, which is the invariant working rather than an exception to it.
    #:
    #: `EncounterState.with_time_passed` still decides every consequence, so a minute spent
    #: here retires the spans and recoveries a minute retires anywhere else.
    TIME_PASSED = "time-passed"


#: The kinds that carry a condition rather than a number. Named because three places have
#: to agree on the split, and a membership test repeated at each of them is one that drifts.
CONDITION_KINDS: Final = frozenset({EffectKind.CONDITION_APPLIED, EffectKind.CONDITION_ENDED})

#: The kinds that name an item rather than a number. Named for `CONDITION_KINDS`' reason:
#: three places agree on the split, and a membership test repeated at each drifts.
#: The kinds that name one of p. 176-177's three actions. `ACTION_SPENT` says which was
#: spent; `LOADING_FIRED` says which one fired the shot p. 90 caps. Two meanings, one field,
#: and the split is named for `CONDITION_KINDS`' reason.
ACTION_KINDS: Final = frozenset({EffectKind.ACTION_SPENT, EffectKind.LOADING_FIRED})

ITEM_KINDS: Final = frozenset(
    {
        EffectKind.OBJECT_DETACHED,
        EffectKind.CARRIAGE_CHANGED,
        EffectKind.OBJECT_PICKED_UP,
        EffectKind.AMMUNITION_SPENT,
        EffectKind.AMMUNITION_RECOVERED,
    }
)


class When(StrEnum):
    """What an effect may be made conditional on (0032 clauses 1 and 3).

    **Data, not a callable.** A predicate the engine can evaluate but not *record* would let
    a withheld effect leave no trace, and an effect the rules withheld would then be
    indistinguishable from one nobody considered — which is the confusion
    [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173) exists to remove
    rather than relocate. R5 makes the ledger the record of what the engine decided, so the
    question has to be as recordable as the answer.

    **The vocabulary grows one printed sentence at a time** (0032 clause 3). An entry
    invented ahead of the rule that needs it is a rule value inferred from memory of a game
    (R31), so each member names the sentence it serves and that sentence is a clause in
    `scripts/verify_d20_rules.py`.
    """

    #: p. 182, Falling: "When the creature lands, it has the Prone condition **unless it
    #: avoids taking any damage from the fall**." True when damage this ruling already
    #: applied to the *same target* came to more than zero.
    DAMAGE_TAKEN = "damage-taken"


#: Why each predicate failed, for the narration bound a withheld effect earns (0032 clause 5).
#: Phrased as the reason rather than the negated predicate: "took no damage" is what a reader
#: needs, and "damage-taken was false" is what a reader has to translate.
WITHHELD_BECAUSE: Final[Mapping[When, str]] = MappingProxyType(
    {When.DAMAGE_TAKEN: "no damage was taken"}
)


#: The kinds that legitimately name a weapon. `ACTION_SPENT` because p. 89's Light property
#: reads which weapon the Attack *action* was spent on; `CLEAVE_OPENED` because p. 90's second
#: swing is made "with the weapon" that opened it, so the opening has to say which (#323).
#: The kinds that legitimately name a second creature. `CONDITION_APPLIED` because p. 183's
#: Grappled names "the grappler" and p. 182's Frightened "the source of fear"; `CLEAVE_OPENED`
#: because p. 90 measures the second swing's targets from **the creature that was hit**, which
#: makes that creature part of the mechanical effect rather than colour (#323).
_SOURCE_BEARING_KINDS: Final = frozenset({EffectKind.CONDITION_APPLIED, EffectKind.CLEAVE_OPENED})

_WEAPON_BEARING_KINDS: Final = frozenset({EffectKind.ACTION_SPENT, EffectKind.CLEAVE_OPENED})


@dataclass(frozen=True)
class Effect:
    """A mechanical change a ruling applies. The engine applies it; the narrator reports it.

    **`amount` is what happened, not what was rolled.** For damage that means the amount the
    target actually took, after p. 17's Immunity, Resistance and Vulnerability have acted —
    `rolled` carries the figure from before, whenever one of them did. The narrator reads this
    object and R7 leaves it free to assert what it finds, so a field that held the rolled
    number would let a creature immune to Fire be narrated as taking a full hit (#105). The
    number that is easiest to read has to be the number that is true.

    **A condition effect carries no number, and `amount` is 0 rather than meaningful.** One
    type with `kind` selecting which optional fields apply is 0019's ruling — `kind` is a
    filing label, not a model — and it is already how `critical`, `damage_type` and `rolled`
    work. `__post_init__` refuses the combinations that would let a reader take an amount
    seriously on a condition, or look for a condition on a damage.
    """

    kind: EffectKind
    target_id: str
    amount: int
    description: str
    #: Damage only. p. 18 makes a Critical Hit cost two death save failures rather than
    #: one, so the state transition has to know where the damage came from.
    critical: bool = False
    #: Damage only. Resistance and the rest key off it; untyped damage matches no defence.
    damage_type: DamageType | None = None
    #: Damage only, and set whenever one of the target's defences acted: what the dice and
    #: modifier came to before it did. `None` means no defence applied, so `amount` is the
    #: whole story. It can equal `amount` — Resistance and Vulnerability to the same type
    #: halve and then double rather than cancelling, which returns an even amount to itself.
    rolled: int | None = None
    #: Condition kinds only: which of the fifteen (#119).
    condition: Condition | None = None
    #: `CONDITION_APPLIED` only, and the reason this field exists at all. The duration
    #: belongs to the effect that imposed the condition rather than to the condition (#18),
    #: so the ruling that imposes one is the only place that knows the span. `None` is
    #: `UNTIL_REMOVED` — reported as unretirable, never silently permanent.
    duration: Duration | None = None
    #: `CONDITION_APPLIED` only. Who imposed it, where the condition's own text turns on
    #: that (#192): p. 182 gives Grappled's Disadvantage "on attack rolls against any target
    #: other than the grappler", and Frightened's "while the source of fear is within line of
    #: sight". Both make the source part of the mechanical effect rather than colour.
    #:
    #: Named `grappler` in the ledger until `RULING_VERSION` 6, when Grappled stopped being
    #: the only condition that needed one.
    source_id: str | None = None
    #: The terms of a grapple this effect imposes (p. 182, p. 190, 0053). Only ever set
    #: beside `condition=Condition.GRAPPLED`: p. 190 fixes the escape DC at the moment the
    #: grapple is made — "The DC for the saving throw **and any escape attempts**" is one
    #: number — so it travels with the application rather than being recomputed later, which
    #: is 0052 clause 4 read from the other end.
    grapple: Grapple | None = None
    #: `ACTION_SPENT` only: which of the three the act cost (p. 176-177).
    action: ActionKind | None = None
    #: `ACTION_SPENT` only, and only for an attack: which weapon the action was spent
    #: attacking with (p. 89). p. 89's Light property triggers on "when you take the **Attack
    #: action** … and attack with a Light weapon", so the weapon rides on the action that was
    #: taken rather than on an effect of its own — the trigger *is* the Attack action.
    #:
    #: `None` for every other action, and for an attack whose weapon does not matter to any
    #: rule the engine holds.
    weapon_id: str | None = None
    #: The three item kinds only: which item moved (0041 clause 7, 0042 clause 4). By id,
    #: because that is what a declaration names and what the ledger records — the same
    #: identity `Item.id` carries everywhere else.
    item_id: str | None = None
    #: `CARRIAGE_CHANGED` only: where the item went. The other two say it by their kind —
    #: detaching has no carriage at all, and picking up always arrives `HELD`.
    carriage: Carriage | None = None
    #: `when` only: **whose** damage the predicate reads, when that is not this effect's own
    #: target (0049). `None` means the target, which is p. 182's Falling — the creature that
    #: took the damage is the creature that falls Prone.
    #:
    #: p. 90's Vex needs the other shape: "If you hit a creature **and deal damage to the
    #: creature**, *you* have Advantage" — the damage is the defender's and the benefit is the
    #: attacker's. Without this the predicate would read the attacker's own damage, find none,
    #: and withhold Vex on every hit.
    when_subject_id: str | None = None
    #: The two advantage kinds only: the token granted or spent, whole (0049). Carried
    #: rather than rebuilt, because a token is identified by every field it has — the
    #: same holder may hold two with different scopes and expiries.
    pending_advantage: PendingAdvantage | None = None
    #: `SPEED_REDUCED` only: the reduction imposed, whole (#322). `amount` carries its feet
    #: for a reader; this carries the boundary that ends it.
    speed_reduction: SpeedReduction | None = None
    #: `SAVE_COMPELLED` only: the save that is owed, whole (0048, #321). The DC and its
    #: derivation are carried rather than recomputed later, because the attack they came
    #: from — and the ability its wielder chose for it — is gone by the time it is rolled.
    forced_save: ForcedSave | None = None
    #: 0032 clauses 1-3. When set, this effect applies only if the predicate holds against
    #: what a **sibling** effect in the same branch settled to — and `_apply` is the only
    #: place that can ask, because it is the only place the settled number exists.
    #:
    #: `None` is the ordinary effect: it applies because the branch selected it.
    when: When | None = None

    def __post_init__(self) -> None:
        carries_condition = self.kind in CONDITION_KINDS
        if carries_condition and self.condition is None:
            raise ValueError(
                f"a {self.kind} effect names which condition it applies or ends; one that "
                "names none has nothing to do"
            )
        if not carries_condition and self.condition is not None:
            raise ValueError(
                f"a {self.kind} effect does not carry a condition. Conditions are applied "
                "and ended by their own effect kinds, so a reader never has to guess "
                "whether one riding on another kind was meant to take effect"
            )
        if carries_condition and self.amount:
            raise ValueError(
                f"a {self.kind} effect carries no number, so its amount is 0. A non-zero "
                "one would be read as meaning something — stacking, or a level — and "
                "nothing in the document says what"
            )
        if self.when is not None and self.kind is EffectKind.DAMAGE:
            raise ValueError(
                "damage cannot be conditional on damage. Every predicate in `When` reads "
                "what siblings settled to, and a damage effect both contributes to that "
                "and would depend on it — so whether it applied would turn on where it sat "
                "in the branch. No rule the sweep behind 0032 found asks for this"
            )
        if self.weapon_id is not None and self.kind not in _WEAPON_BEARING_KINDS:
            raise ValueError(
                f"a {self.kind} effect names no weapon. p. 89's Light property reads which "
                "weapon the Attack *action* was spent on, so the weapon travels with the "
                "action and nowhere else"
            )
        if (self.kind in ITEM_KINDS) != (self.item_id is not None):
            raise ValueError(
                f"a {self.kind} effect names the item it moves, and only the item kinds "
                "carry one. An unnamed move could not be applied, and an item id riding on "
                "another kind would be a change no transition performs"
            )
        if (self.kind is EffectKind.CARRIAGE_CHANGED) != (self.carriage is not None):
            raise ValueError(
                "a carriage-changed effect names where the item went, and no other kind "
                "does. Detaching has no carriage at all and picking up always arrives held, "
                "so a carriage on either would describe a destination its transition ignores"
            )
        if (self.kind in ACTION_KINDS) != (self.action is not None):
            raise ValueError(
                f"a {self.kind} effect names which of p. 176-177's three actions it means, "
                "and only the action kinds carry one. They are not interchangeable — a "
                "Reaction is free of the other two, and p. 90 caps a Loading shot per action "
                "used rather than per turn"
            )
        if self.kind is not EffectKind.CONDITION_APPLIED and self.duration is not None:
            raise ValueError(
                f"a {self.kind} effect states no duration. A span belongs to the application "
                "that imposed a condition, and nothing else here has one to state"
            )
        if self.kind not in _SOURCE_BEARING_KINDS and self.source_id is not None:
            raise ValueError(
                f"a {self.kind} effect names no second creature. A source belongs to the "
                "application that imposed a condition — p. 183's grappler, p. 182's source "
                "of fear — or to p. 90's Cleave, which measures its second swing from the "
                "creature that was hit. A condition ending acquires neither on its way out"
            )


def condition_applied(
    target_id: str,
    condition: Condition,
    *,
    description: str,
    duration: Duration | None = None,
    source_id: str | None = None,
    grapple: Grapple | None = None,
    when: When | None = None,
) -> Effect:
    """A condition imposed by the ruling that caused it (#119).

    A resolver builds this rather than an `Effect` directly, so `amount=0` is written once
    here instead of at every call site — where a reader would reasonably wonder what the
    zero meant.

    `duration=None` is `UNTIL_REMOVED`: the effect stated no span this engine can count,
    which the read surface reports rather than treating as permanent. It is not a default
    span, because defaulting one would invent a rule the document does not state.
    """
    return Effect(
        kind=EffectKind.CONDITION_APPLIED,
        target_id=target_id,
        amount=0,
        description=description,
        condition=condition,
        duration=duration,
        source_id=source_id,
        grapple=grapple,
        when=when,
    )


def condition_ended(target_id: str, condition: Condition, *, description: str) -> Effect:
    """A condition lifted by the ruling that ended it — a successful save, or an effect
    that removes it (#119, 0023 clause 4).

    Retiring a *span* is not this: a duration's expiry point is settled when the condition
    is applied, so the turn or the clock reaching it decides nothing and needs no ruling.
    This is for the endings something had to decide.
    """
    return Effect(
        kind=EffectKind.CONDITION_ENDED,
        target_id=target_id,
        amount=0,
        description=description,
        condition=condition,
    )


def object_detached(target_id: str, item_id: str, *, description: str) -> Effect:
    """An item let go of by the ruling that caused it (0041 clause 7, #280).

    Built here rather than as a raw `Effect` so `amount=0` is written once, the way
    `condition_applied` does it — a zero at every call site is a number a reader has to
    interpret.

    The object arrives with **no position**: p. 191, p. 177, p. 90, p. 116 and p. 130 each
    detach an item and none states a destination, so the read surface reports it among
    `unplaced_objects` rather than somewhere invented (0041 clause 4).
    """
    return Effect(
        kind=EffectKind.OBJECT_DETACHED,
        target_id=target_id,
        amount=0,
        description=description,
        item_id=item_id,
    )


def attack_made(target_id: str, *, description: str) -> Effect:
    """One attack roll, counted against the Multiattack allowance (p. 257)."""
    return Effect(
        kind=EffectKind.ATTACK_MADE, target_id=target_id, amount=0, description=description
    )


def advantage_pending(
    token: PendingAdvantage,
    *,
    description: str,
    when: When | None = None,
    when_subject_id: str | None = None,
) -> Effect:
    """Advantage or Disadvantage granted for a later roll (0049).

    `when` carries p. 90's Vex condition — "and deal damage to the creature" — with
    `when_subject_id` naming the creature whose damage decides it, which is not the creature
    the token is granted to.
    """
    return Effect(
        kind=EffectKind.ADVANTAGE_PENDING,
        target_id=token.holder_id,
        amount=0,
        description=description,
        pending_advantage=token,
        when=when,
        when_subject_id=when_subject_id,
    )


def cleave_opened(
    actor_id: str, weapon_id: str, first_target_id: str, *, description: str
) -> Effect:
    """A melee hit that opens p. 90's Cleave (#323).

    Carries the weapon and the creature that was hit, because the second attack is made with
    that weapon and its eligible targets are measured from that creature.
    """
    return Effect(
        kind=EffectKind.CLEAVE_OPENED,
        target_id=actor_id,
        amount=0,
        description=description,
        weapon_id=weapon_id,
        source_id=first_target_id,
    )


def speed_reduced(
    target_id: str,
    reduction: SpeedReduction,
    *,
    description: str,
    when: When | None = None,
    when_subject_id: str | None = None,
) -> Effect:
    """A Speed reduction imposed until its boundary (p. 90, #322).

    `when` carries p. 90's Slow condition — "and deal damage to it" — and its subject is the
    creature that was hit, which here *is* the effect's target. It is passed explicitly all
    the same, because the default would make the pairing look accidental.
    """
    return Effect(
        kind=EffectKind.SPEED_REDUCED,
        target_id=target_id,
        amount=reduction.feet,
        description=description,
        speed_reduction=reduction,
        when=when,
        when_subject_id=when_subject_id,
    )


def cleave_taken(actor_id: str, *, description: str) -> Effect:
    """p. 90's one Cleave a turn, spent (#323)."""
    return Effect(
        kind=EffectKind.CLEAVE_TAKEN,
        target_id=actor_id,
        amount=0,
        description=description,
    )


def advantage_spent(token: PendingAdvantage, *, description: str) -> Effect:
    """A pending token consumed by the roll it applied to (0049)."""
    return Effect(
        kind=EffectKind.ADVANTAGE_SPENT,
        target_id=token.holder_id,
        amount=0,
        description=description,
        pending_advantage=token,
    )


def save_compelled(target_id: str, save: ForcedSave, *, description: str) -> Effect:
    """A save a rule compelled, recorded for the loop to roll (0048, #321).

    The whole `ForcedSave` rides on the effect because the DC's inputs belong to the moment
    the trigger fired — p. 90's Topple DC uses the ability the attacker *chose* for that
    roll — and nothing recovers them afterwards.
    """
    return Effect(
        kind=EffectKind.SAVE_COMPELLED,
        target_id=target_id,
        amount=0,
        description=description,
        forced_save=save,
    )


def extra_attack_made(target_id: str, *, description: str) -> Effect:
    """p. 89's one extra Light attack, taken by either route (#320). See the kind."""
    return Effect(
        kind=EffectKind.EXTRA_ATTACK_MADE,
        target_id=target_id,
        amount=0,
        description=description,
    )


def object_interacted(target_id: str, *, description: str) -> Effect:
    """This turn's one object interaction, spent (0045 clause 1)."""
    return Effect(
        kind=EffectKind.OBJECT_INTERACTED, target_id=target_id, amount=0, description=description
    )


def loading_fired(target_id: str, action: ActionKind, *, description: str) -> Effect:
    """p. 90's one shot from a Loading weapon, spent for that action (#271)."""
    return Effect(
        kind=EffectKind.LOADING_FIRED,
        target_id=target_id,
        amount=0,
        description=description,
        action=action,
    )


def ammunition_recovered(target_id: str, item_id: str, pieces: int, *, description: str) -> Effect:
    """Ammunition recovered after a fight (p. 89, #301)."""
    return Effect(
        kind=EffectKind.AMMUNITION_RECOVERED,
        target_id=target_id,
        amount=pieces,
        description=description,
        item_id=item_id,
    )


def time_passed(target_id: str, minutes: int, *, description: str) -> Effect:
    """Campaign minutes a rule states (#301). See `EffectKind.TIME_PASSED`."""
    return Effect(
        kind=EffectKind.TIME_PASSED,
        target_id=target_id,
        amount=minutes,
        description=description,
    )


def ammunition_spent(target_id: str, item_id: str, *, description: str) -> Effect:
    """One piece of ammunition expended by an attack (p. 89, #273)."""
    return Effect(
        kind=EffectKind.AMMUNITION_SPENT,
        target_id=target_id,
        amount=0,
        description=description,
        item_id=item_id,
    )


def carriage_changed(
    target_id: str, item_id: str, carriage: Carriage, *, description: str
) -> Effect:
    """An item sheathed, stowed or drawn (p. 177, 0042 clause 4)."""
    return Effect(
        kind=EffectKind.CARRIAGE_CHANGED,
        target_id=target_id,
        amount=0,
        description=description,
        item_id=item_id,
        carriage=carriage,
    )


def object_picked_up(target_id: str, item_id: str, *, description: str) -> Effect:
    """A detached object taken into a creature's hands (p. 177, 0042 clause 4)."""
    return Effect(
        kind=EffectKind.OBJECT_PICKED_UP,
        target_id=target_id,
        amount=0,
        description=description,
        item_id=item_id,
    )


def dashed(actor_id: str, feet: int, *, description: str) -> Effect:
    """The Dash action's extra movement (p. 180)."""
    return Effect(kind=EffectKind.DASHED, target_id=actor_id, amount=feet, description=description)


def dodging_taken(actor_id: str, *, description: str) -> Effect:
    """The Dodge action, taken (p. 181)."""
    return Effect(kind=EffectKind.DODGING, target_id=actor_id, amount=0, description=description)


def disengaged(actor_id: str, *, description: str) -> Effect:
    """The Disengage action, taken (p. 181)."""
    return Effect(kind=EffectKind.DISENGAGED, target_id=actor_id, amount=0, description=description)


def action_spent(
    actor_id: str, action: ActionKind, *, description: str, weapon_id: str | None = None
) -> Effect:
    """The action an act cost (p. 176-177, p. 185).

    A cost rather than a consequence, so it belongs in `Proposal.always` like every other
    cost — the act happened, whatever the roll said about it.
    """
    return Effect(
        kind=EffectKind.ACTION_SPENT,
        target_id=actor_id,
        amount=0,
        description=description,
        action=action,
        weapon_id=weapon_id,
    )


def spell_slot_expended(caster_id: str, slot_level: int, *, description: str) -> Effect:
    """The cost of casting with a slot (p. 104, 0038 clauses 5 and 6).

    The **slot** level, which p. 104 allows to exceed the spell's: "you expend a slot of that
    spell's level or higher". A cantrip produces no effect of this kind at all rather than one
    of level 0 — p. 104 lists four ways to cast without a slot, and none of them spends one.
    """
    if slot_level < 1:
        raise ValueError(
            f"a spell slot is level 1 to {MAX_SPELL_LEVEL}, not {slot_level}. p. 104 puts a "
            "level 0 spell outside the slot economy entirely, so a cantrip expends no slot "
            "rather than expending a slot of no level"
        )
    return Effect(
        kind=EffectKind.SPELL_SLOT_EXPENDED,
        target_id=caster_id,
        amount=slot_level,
        description=description,
    )


def concentration_begun(caster_id: str, *, description: str) -> Effect:
    """Concentration started by the ruling that is applying this (p. 179, 0038 clause 7).

    Carries no name for what is being concentrated on, deliberately: `_apply` takes the
    ruling's own rule id, so the record cannot disagree with the ruling that produced it.
    """
    return Effect(
        kind=EffectKind.CONCENTRATION_BEGUN,
        target_id=caster_id,
        amount=0,
        description=description,
    )


def concentration_ended(target_id: str, *, description: str) -> Effect:
    """The effect a failed Concentration save applies (p. 179, 0036 clause 1).

    A constructor rather than a raw `Effect` for `condition_ended`'s reason: the kind and
    the empty amount are the same at every call site, and a helper is one place for them to
    be right rather than one place per resolver for them to drift.
    """
    return Effect(
        kind=EffectKind.CONCENTRATION_ENDED,
        target_id=target_id,
        amount=0,
        description=description,
    )


@dataclass(frozen=True)
class DamageDice:
    """Damage a resolver **declares** and the engine rolls. Never a total.

    A resolver returning `Effect(amount=7)` for a longsword would be a caller supplying a
    roll, which R4 exists to make impossible. So a proposal states the dice and the engine
    rolls them — from the same seed as the attack, at `DAMAGE_OFFSET`, which is what makes
    a replay reproduce the damage as well as the hit.

    A fixed `Effect` is still legitimate in a branch: some rules deal a stated amount. The
    distinction is whether the number came from dice, and dice belong to the engine.
    """

    target_id: str
    count: int
    sides: int
    modifier: int = 0
    source: str = "damage"
    #: Carried through to the Effect, where the target's defences act on it.
    damage_type: DamageType | None = None

    def __post_init__(self) -> None:
        if self.count < 0 or self.sides < 1:
            raise ValueError(f"{self.count}d{self.sides} is not a damage expression")


#: What a proposal may put in a branch: a stated effect, or dice for the engine to roll.
Declared = Effect | DamageDice


@dataclass(frozen=True)
class Intent:
    """R2. Structured, or explicitly improvised — the label is carried and never matched on."""

    action_key: str | None = None
    improvised: bool = False
    label: str | None = None

    def __post_init__(self) -> None:
        if self.improvised and self.action_key is not None:
            raise ValueError("an improvised intent has no enumerated action key")
        if not self.improvised and not self.action_key:
            raise ValueError("an intent is either enumerated or marked improvised")


@dataclass(frozen=True)
class Declaration:
    """R2. What the agent believes applies, or an explicit claim that nothing does."""

    actor_id: str
    intent: Intent
    rule_id: str | None = None
    no_test_reason: str | None = None
    alternatives: tuple[LegalAction, ...] = ()
    read_token: str | None = None

    def __post_init__(self) -> None:
        if bool(self.rule_id) == bool(self.no_test_reason):
            raise ValueError(
                "a declaration names the test it believes applies, or claims no test is "
                "needed and states why. Exactly one, because a skip with no reason is the "
                "defect this engine exists to make impossible"
            )

    @property
    def claims_no_test(self) -> bool:
        return self.no_test_reason is not None


@dataclass(frozen=True)
class NarrationBounds:
    """R7. Advisory to the caller — the engine states them and does not enforce them."""

    may: tuple[str, ...] = ()
    may_not: tuple[str, ...] = ()


def _refuse_undecidable_conditional(branch_name: str, branch: Sequence[Declared]) -> None:
    """Refuse a conditional effect no sibling can ever satisfy (0032 clauses 1 and 2).

    Every predicate in `When` reads what damage a sibling **already applied** settled to, so
    a conditional placed before any damage to its own target is decided before the branch
    runs: it is always false. That is a resolver defect and not a rule question, and it is
    silent without this — the effect is simply withheld every time, which looks exactly like
    a rule that never applies.

    Order is the test rather than mere membership. `_apply` walks the branch once and
    accumulates as it goes, so a conditional reads only what precedes it.
    """
    damaged: set[str] = set()
    for declared in branch:
        if isinstance(declared, DamageDice):
            damaged.add(declared.target_id)
            continue
        if declared.kind is EffectKind.DAMAGE:
            damaged.add(declared.target_id)
            continue
        # The **subject** of the predicate, which is the effect's own target unless the rule
        # says otherwise (0049). p. 90's Vex conditions the attacker's benefit on the
        # defender's damage, so checking `target_id` here would refuse a correct proposal —
        # and, worse, checking neither would let a genuinely undecidable one through.
        subject = declared.when_subject_id or declared.target_id
        if declared.when is not None and subject not in damaged:
            raise ValueError(
                f"the {branch_name} branch makes an effect on {declared.target_id!r} "
                f"conditional on {declared.when} against {subject!r}, but no damage to that "
                f"creature precedes it. Every predicate reads what a sibling settled to, so "
                f"this one is false before the branch runs and the effect would never apply"
            )


@dataclass(frozen=True)
class Proposal:
    """What a resolver returns: the test to roll, and what follows from either outcome.

    **`test` is optional, and a proposal without one is still an outcome** (0027 clause 6).
    Some rules resolve with no d20 anywhere in them — Falling deals 1d6 per 10 feet to a cap
    (p. 182) and asks nothing of the dice but the damage. Until #170 that could not be
    expressed, and reaching it by inventing a test would be inventing a roll the rules do not
    call for, which is R4 from the other direction than usual.

    A testless proposal changes nothing else. It goes through the one adjudication entry
    point (R1), a seed is still drawn, and its `DamageDice` are still rolled by the engine
    (R4). What it does not do is roll a d20.

    **This is not `Status.NO_TEST`**, and the names are close enough to be worth separating.
    `NO_TEST` is an accepted claim that no rule was engaged — "the action happened as
    described, with no mechanical outcome". A testless proposal has a mechanical outcome and
    no roll. One decides nothing; the other decides something without a die.
    """

    test: D20Test | None = None
    citations: tuple[str, ...] = ()
    #: Effects that apply because the **action happened**, not because a branch was selected
    #: (0038 clause 6). A spell slot is the first: p. 104 ties expenditure to the casting —
    #: "When you cast a spell, you expend a slot" — and says nothing about how the roll came
    #: out.
    #:
    #: **Not the same as `outcome`.** That is the branch a *testless* proposal resolves to,
    #: and it is still a consequence — Falling's damage is what the fall did. This is what the
    #: act cost, and it applies alongside a test's branches rather than instead of them.
    #:
    #: The alternative was duplicating a cost into every branch, which is safe, says the wrong
    #: thing, and escapes the next branch somebody adds.
    always: tuple[Declared, ...] = ()
    #: The branch a testless proposal resolves to. Not `on_success`, because nothing
    #: succeeded — there was no test to succeed at, and a name implying one would be the
    #: record saying a roll happened.
    outcome: tuple[Declared, ...] = ()
    on_success: tuple[Declared, ...] = ()
    #: Branches selected by the **natural die** rather than by success or failure. The
    #: death save needs them and nothing else does yet: p. 18 makes a natural 1 cost two
    #: failures and a natural 20 restore a hit point, neither of which is "the save
    #: succeeded" or "the save failed". Left `None`, the ordinary branch runs.
    on_natural_20: tuple[Declared, ...] | None = None
    on_natural_1: tuple[Declared, ...] | None = None
    on_failure: tuple[Declared, ...] = ()
    may_claim: tuple[str, ...] = ()
    may_not_claim: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Refuse the two shapes that would resolve to nothing, or to nothing decidable.

        Both are resolver defects rather than rule questions, and both are silent without
        this: a proposal that decides nothing still appends a Ruling, and a ruling that
        recorded no outcome reads exactly like a rule that had none.
        """
        if self.test is None and not self.outcome:
            raise ValueError(
                "a proposal with no test and no outcome decides nothing. A rule that "
                "resolves without a d20 states its effects in `outcome` (0027 clause 6); "
                "a claim that no rule was engaged is Status.NO_TEST and is not a proposal"
            )
        if self.test is not None and self.outcome:
            raise ValueError(
                "a proposal with both a test and an `outcome` is ambiguous: `outcome` is "
                "the branch taken when there is no test, so nothing would select it here. "
                "Use on_success/on_failure for a proposal that rolls"
            )
        for name in (
            "always",
            "outcome",
            "on_success",
            "on_failure",
            "on_natural_20",
            "on_natural_1",
        ):
            _refuse_undecidable_conditional(name, getattr(self, name) or ())


class Resolver(Protocol):
    """Turns a rule plus resolved facts into a proposal. This is code, not data."""

    def __call__(
        self,
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal: ...


class SeedSource(Protocol):
    """Where a seed comes from. Unpredictable in production; substituted in tests."""

    def __call__(self) -> int: ...


#: How much entropy a seed carries. **Not 64.** A seed is recorded in the ledger, and the
#: canonical form admits only integers an ECMAScript number represents exactly — so a
#: 64-bit seed has no canonical form and the adjudication that drew it cannot be written
#: down. The failure is total (the Ruling never escapes) but it looked like a ledger
#: problem, and every test until the vertical slice used seeds small enough to miss it.
SEED_BITS: Final = 52


def _system_seed() -> int:
    """Unpredictable, and inside the range the record can hold. R5 needs both."""
    return secrets.randbits(SEED_BITS)


@dataclass(frozen=True)
class Ruling:
    """R5. The only object that constitutes an outcome, and it shows its working."""

    status: Status
    declaration: Declaration
    alternatives_verdict: Verdict
    rule_id: str | None = None
    result: D20Result | None = None
    effects: tuple[Effect, ...] = ()
    #: Effects this ruling considered and did not apply, because a `when` predicate did not
    #: hold (0032 clause 4). Kept apart from `effects` because the standing narration bound
    #: is "that the effects recorded here happened", and these did not — but recorded,
    #: because an effect the rules withheld must not read like one nobody thought of.
    withheld: tuple[Effect, ...] = ()
    facts: tuple[Resolution, ...] = ()
    citations: tuple[str, ...] = ()
    bounds: NarrationBounds = field(default_factory=NarrationBounds)
    reason: str | None = None
    reason_code: RejectionCode | None = None
    reason_subject: str | None = None
    unresolved: tuple[str, ...] = ()
    fired: tuple[Trigger, ...] = ()

    @property
    def signature(self) -> tuple[str, ...]:
        """Structural identity, for telling one refusal from a repeat of the same one."""
        if self.status is Status.CHALLENGED:
            return tuple(trigger.id for trigger in self.fired)
        if self.status is Status.REJECTED:
            return (str(self.reason_code), self.reason_subject or "")
        return ()

    @property
    def is_outcome(self) -> bool:
        return self.status in {Status.RULED, Status.NO_TEST}

    def why(self) -> str:
        """The one-line account a reader can check without reconstructing the session."""
        if self.status is Status.REJECTED:
            return f"rejected: {self.reason}"
        if self.status is Status.CHALLENGED:
            return f"challenged: {challenge_text(self.fired)}"
        if self.status is Status.BLOCKED:
            return f"blocked on {', '.join(self.unresolved)}"
        if self.result is None:
            return f"no test needed: {self.declaration.no_test_reason}"
        return self.result.derivation()


class Adjudicator:
    """Holds the ruleset, its resolvers, the port, and the ledger. Rules through one door."""

    def __init__(
        self,
        *,
        ruleset: Ruleset,
        resolvers: Mapping[str, Resolver],
        fact_types: Mapping[str, FactType],
        port: MemoryPort,
        ledger: Ledger,
        catalogue: Catalogue | None = None,
        seed_source: SeedSource = _system_seed,
    ) -> None:
        missing = [rule.id for rule in ruleset if rule.id not in resolvers]
        if missing:
            raise ValueError(
                f"no resolver for {', '.join(sorted(missing))}. A rule that cannot be "
                "resolved would be admitted by the loader and then fail at the table"
            )
        self._ruleset = ruleset
        self._resolvers = dict(resolvers)
        self._fact_types = dict(fact_types)
        self._port = port
        self._ledger = ledger
        self._catalogue = catalogue or Catalogue(version=1)
        self._seed_source = seed_source
        #: The status of the last ruling this adjudicator produced, so a `resuming=True`
        #: claim can be checked against what actually preceded it (#59). Set by
        #: `adjudicate` alone — `record_narration` and `record_termination` append entries
        #: but produce no ruling, so they leave it where it was.
        self._last_status: Status | None = None

    @property
    def port(self) -> MemoryPort:
        """The memory port, so a driver's supplied facts reach the same store."""
        return self._port

    @property
    def fact_types(self) -> Mapping[str, FactType]:
        """The declared fact types, so a caller answering a block cannot choose the kind.

        R20 keeps prose out of the port; this keeps the *shape* out of the caller's hands
        too. An adapter turning "12" into a value needs to know that `attitude` is an
        integer, and the alternative — the caller naming the kind alongside the value — lets
        it disagree with the engine about what it just wrote (#144).
        """
        return MappingProxyType(self._fact_types)

    def record_narration(self, ruling: Ruling, text: str) -> None:
        """R29. The narration is appended against the Ruling and the bounds it was issued under.

        Its own escape boundary: a narration is not an outcome, so it is not covered by the
        adjudication's sync, and R29 already provides for one that never arrives.
        """
        with self._ledger.escape_boundary():
            self._ledger.append(
                "narration",
                v=NARRATION_VERSION,
                payload={
                    COMPAT: NARRATION_COMPAT,
                    "actor": ruling.declaration.actor_id,
                    "rule_id": ruling.rule_id,
                    "text": text,
                    "bounds": {
                        "may": list(ruling.bounds.may),
                        "may_not": list(ruling.bounds.may_not),
                    },
                },
            )

    def record_termination(self, actor_id: str, reason: str, refusals: Sequence[Ruling]) -> None:
        """A declaration slot that ended without a Ruling, recorded as the event it is.

        R30's report is generated from the ledger, so a turn that terminated leaves no
        trace unless something writes one — and a run of refusals followed by silence is
        indistinguishable from a session that simply stopped. Naming the reason is what
        lets triage tell an over-broad catalogue row from a confused agent.

        Its own escape boundary, for the same reason a narration has one: exhaustion is
        not an outcome, so it is not covered by an adjudication's sync.
        """
        with self._ledger.escape_boundary():
            self._ledger.append(
                "exhaustion",
                v=TERMINATION_VERSION,
                payload={
                    COMPAT: TERMINATION_COMPAT,
                    "actor": actor_id,
                    "reason": reason,
                    "refusals": [
                        {
                            "status": str(r.status),
                            "reason_code": str(r.reason_code) if r.reason_code else None,
                            "reason_subject": r.reason_subject,
                            "fired": [t.id for t in r.fired],
                        }
                        for r in refusals
                    ],
                },
            )

    def adjudicate(
        self,
        state: EncounterState,
        declaration: Declaration,
        *,
        situation: Mapping[str, object] | None = None,
        resuming: bool = False,
    ) -> tuple[Ruling, EncounterState]:
        """The single entry point. Returns the Ruling and the state it left behind.

        `resuming` marks this call as the turn loop picking a **blocked** declaration back
        up once the missing facts arrived, rather than the agent declaring again (#59, and
        [0010](../../../docs/decisions/0010-blocked-loop.md)). It changes no outcome — only
        what the record says happened, which is the whole of the defect: one declaration by
        the agent used to leave two identical `declaration` entries, and a reader counting
        them over-reported agent declarations by one per block.

        **The caller states it because only the caller knows.** This method is called once
        per adjudication and has no view of the sequence; the loop that suspends and resumes
        does. Inferring it from the preceding ruling's status would be reading the record to
        write the record, and inference is how the advantage gap got in (`REPLAYABLE_FROM`).

        A claim that cannot be true is refused rather than recorded, so the flag cannot
        under-count agent declarations the way its absence over-counted them.
        """
        if resuming and self._last_status is not Status.BLOCKED:
            raise ValueError(
                "resuming=True says this declaration is being picked back up after a "
                "block, and the last ruling this adjudicator produced was "
                f"{self._last_status}. A resumption follows the block it resumes"
            )
        with self._ledger.escape_boundary():
            self._ledger.append(
                "declaration",
                v=DECLARATION_VERSION,
                payload=_declaration_payload(
                    declaration, self._catalogue.version, resuming=resuming
                ),
            )
            ruling, next_state = self._decide(state, declaration, situation or {})
            self._ledger.append(
                _entry_type(ruling.status), v=RULING_VERSION, payload=_ruling_payload(ruling)
            )
        self._last_status = ruling.status
        return ruling, next_state

    # --- The decision, in the order R5 requires it to be reconstructable ------------

    def _decide(
        self,
        state: EncounterState,
        declaration: Declaration,
        situation: Mapping[str, object],
    ) -> tuple[Ruling, EncounterState]:
        verdict = self._verdict(state, declaration)

        refusal = self._validate(state, declaration)
        if refusal is not None:
            return _refused(declaration, verdict, *refusal), state

        if declaration.claims_no_test:
            # R6. The matcher sees a projection with no field for the free-text label,
            # so a skip cannot be waved through by how it was worded.
            fired = self._catalogue.matching(project(declaration, state, situation))
            if fired:
                return _challenged(declaration, verdict, fired), state
            return _no_test(declaration, verdict), state

        assert declaration.rule_id is not None  # guaranteed by Declaration.__post_init__
        rule = self._ruleset.rule(declaration.rule_id)

        resolutions = [
            resolve_fact(self._port, self._fact_types[name], declaration.actor_id)
            for name in rule.consumes
        ]
        blocked = tuple(r.type_name for r in resolutions if r.blocked)
        if blocked:
            # R22: name *every* unresolved fact, not the first. The set can only shrink,
            # so a driver that supplies them all at once resolves in one round.
            return _blocked(declaration, verdict, blocked, tuple(resolutions)), state

        proposal = self._resolvers[rule.id](
            state=state, declaration=declaration, facts={r.type_name: r for r in resolutions}
        )
        # #344. What the creature's own state does to a saving throw, applied **here** rather
        # than in each resolver. Six resolvers build a save today and none of them consulted
        # the roller's conditions, which is the failure mode this engine names most often: a
        # rule that every call site has to remember is a rule some call site will not.
        proposal = _as_this_creature_saves(state, declaration.actor_id, proposal)
        # pp. 186, 189, 191. The save fails and **is not rolled**, so the branch is selected
        # here rather than by `_branch` and no die is drawn at all. Kept out of the proposal
        # because an auto-failure with nothing in `on_failure` is a real case —
        # `core.save_ends` has exactly that shape, since failing to shake a condition off
        # simply leaves it — and a proposal rewritten to hold it would be one `Proposal`
        # refuses to construct.
        auto_failed = _save_fails_outright(state, declaration.actor_id, proposal)
        seed = _checked_seed(self._seed_source())
        # 0027 clause 6. A seed is drawn either way: a testless proposal still rolls its
        # damage from it, so the outcome stays the engine's (R4) and stays reproducible.
        result = (
            None if auto_failed or proposal.test is None else roll_d20(proposal.test, seed=seed)
        )
        branch = (
            (*proposal.always, *proposal.on_failure) if auto_failed else _branch(proposal, result)
        )
        effects = _roll_declared(
            branch, seed=seed, critical=result.critical if result is not None else Critical.NONE
        )
        # The effects that go into the Ruling are the ones `_apply` hands back, not the
        # ones it was given: damage is rolled before a target is consulted, so only the
        # applier knows what p. 17's defences left of it (#105).
        next_state, effects, withheld = _apply(state, effects, seed=seed, rule_id=rule.id)

        return (
            Ruling(
                status=Status.RULED,
                declaration=declaration,
                alternatives_verdict=verdict,
                rule_id=rule.id,
                result=result,
                effects=effects,
                withheld=withheld,
                facts=tuple(resolutions),
                citations=proposal.citations,
                # `withheld` is known only after `_apply`, which is the whole of 0032
                # clause 5: a bound naming a conditional effect cannot be written at
                # proposal time, because the proposal does not yet know whether it applied.
                bounds=_bounds(proposal, result, withheld),
            ),
            next_state,
        )

    def _verdict(self, state: EncounterState, declaration: Declaration) -> Verdict:
        return verify(declaration.read_token, declaration.alternatives, state.generation)

    def _validate(
        self, state: EncounterState, declaration: Declaration
    ) -> tuple[str, RejectionCode, str] | None:
        """R3, against the same derivation the read surface enumerates with.

        Returns the sentence, the code, and the specific subject — the last two are what
        the retry bound compares, because message text is templated and would make two
        identical refusals look different.
        """
        if not state.has(declaration.actor_id):
            return (
                f"no combatant {declaration.actor_id!r} in this encounter",
                RejectionCode.UNKNOWN_ACTOR,
                declaration.actor_id,
            )

        offered = legal_actions(state, declaration.actor_id)
        key = declaration.intent.action_key
        if key is not None and key not in {action.key for action in offered}:
            return (
                f"{key!r} is not legal for {declaration.actor_id!r} right now; "
                f"the read surface offers {', '.join(a.key for a in offered) or 'nothing'}",
                RejectionCode.ACTION_NOT_LEGAL,
                key,
            )

        if declaration.rule_id is not None:
            if declaration.rule_id not in self._ruleset:
                return (
                    f"no rule {declaration.rule_id!r} in this ruleset",
                    RejectionCode.UNKNOWN_RULE,
                    declaration.rule_id,
                )
            for fact_type in self._ruleset.rule(declaration.rule_id).consumes:
                if fact_type not in self._fact_types:
                    return (
                        f"rule {declaration.rule_id!r} consumes undeclared fact {fact_type!r}",
                        RejectionCode.UNDECLARED_FACT,
                        fact_type,
                    )
        return None


# --- Ruling constructors ------------------------------------------------------------


def _refused(
    declaration: Declaration,
    verdict: Verdict,
    reason: str,
    code: RejectionCode,
    subject: str,
) -> Ruling:
    return Ruling(
        status=Status.REJECTED,
        declaration=declaration,
        alternatives_verdict=verdict,
        reason=reason,
        reason_code=code,
        reason_subject=subject,
        bounds=NarrationBounds(may_not=("that anything happened — no outcome was produced",)),
    )


def _challenged(declaration: Declaration, verdict: Verdict, fired: tuple[Trigger, ...]) -> Ruling:
    """R6. Names every row that fired, in identifier order, and produces no outcome."""
    return Ruling(
        status=Status.CHALLENGED,
        declaration=declaration,
        alternatives_verdict=verdict,
        fired=fired,
        bounds=NarrationBounds(
            may_not=("that anything happened — the skip must be re-declared as a test",)
        ),
    )


def project(
    declaration: Declaration, state: EncounterState, situation: Mapping[str, object]
) -> MatchContext:
    """Build what the matcher sees. The free-text label has nowhere to go."""
    derived: dict[str, object] = {
        "in_combat": state.in_combat,
        "round": state.round_number,
        "actor_is_active": state.is_active(declaration.actor_id),
    }
    if state.has(declaration.actor_id):
        actor = state.combatant(declaration.actor_id)
        derived["actor_hit_points"] = actor.hit_points
        derived["actor_is_down"] = actor.is_down
    return MatchContext(
        actor_id=declaration.actor_id,
        action_key=declaration.intent.action_key,
        improvised=declaration.intent.improvised,
        situation={**derived, **situation},
    )


def _no_test(declaration: Declaration, verdict: Verdict) -> Ruling:
    return Ruling(
        status=Status.NO_TEST,
        declaration=declaration,
        alternatives_verdict=verdict,
        bounds=NarrationBounds(
            may=("that the action happened as described, with no mechanical outcome",),
            may_not=("any consequence a rule would have had to resolve",),
        ),
    )


def _blocked(
    declaration: Declaration,
    verdict: Verdict,
    unresolved: tuple[str, ...],
    facts: tuple[Resolution, ...],
) -> Ruling:
    return Ruling(
        status=Status.BLOCKED,
        declaration=declaration,
        alternatives_verdict=verdict,
        rule_id=declaration.rule_id,
        facts=facts,
        unresolved=unresolved,
        bounds=NarrationBounds(may_not=("that anything happened — no outcome was produced",)),
    )


def _withheld_bound(effect: Effect) -> str:
    """The bound a withheld effect earns (0032 clauses 4 and 5).

    Written here rather than by the resolver, and that is the point. `_bounds` runs after
    `_apply`, so this is the first moment anything knows the predicate failed — a resolver
    naming the outcome in `may_claim` would be asserting a branch it could not yet see.
    """
    subject = (
        f"{effect.target_id} has the {effect.condition} condition"
        if effect.condition is not None
        else f"a {effect.kind} effect reached {effect.target_id}"
    )
    assert effect.when is not None  # only a conditional effect can be withheld
    return (
        f"that {subject} — this ruling considered it and withheld it, because "
        f"{WITHHELD_BECAUSE[effect.when]}"
    )


def _bounds(
    proposal: Proposal, result: D20Result | None, withheld: Sequence[Effect] = ()
) -> NarrationBounds:
    """R7. What may be claimed, and the standing limit on everything else.

    A testless outcome may not be narrated as a success or a failure, because it was
    neither — nothing was tested. Saying "the save succeeded" over a fall would describe a
    roll that never happened, which is the narration bound doing exactly its job.

    **A conditional effect states no bound of its own at proposal time** (0032 clause 5).
    The proposal is built before `_apply`, so a `may_claim` naming one would license a claim
    the predicate may have withheld — which is the defect being fixed, moved from the effect
    to the record of it. The positive case needs nothing: "that the effects recorded here
    happened" already covers an effect that applied, and one that did not is absent from the
    list. The negative case is added here, where it is known.
    """
    refusals = tuple(_withheld_bound(effect) for effect in withheld)
    if result is None:
        return NarrationBounds(
            may=("that the effects recorded here happened", *proposal.may_claim),
            may_not=(
                "that anything was rolled for, tested, resisted or avoided — this rule "
                "resolves without a d20",
                "any consequence this ruling did not resolve; it needs its own declaration",
                *refusals,
                *proposal.may_not_claim,
            ),
        )
    outcome = "succeeded" if result.succeeded else "failed"
    return NarrationBounds(
        may=(f"that the {result.kind} {outcome}", *proposal.may_claim),
        may_not=(
            "any consequence this ruling did not resolve; it needs its own declaration",
            *refusals,
            *proposal.may_not_claim,
        ),
    )


def _checked_seed(seed: int) -> int:
    """Refuse a seed the record cannot hold, and name the seed source rather than the ledger.

    Without this the failure surfaces at the ledger write, as `LedgerUnavailable` — which
    points at the ledger for a defect in whatever supplied the seed. The seed is never
    clamped: a quietly altered seed reproduces a different roll on replay, so the only
    honest options are the seed as given or a refusal.
    """
    if not 0 <= seed <= MAX_SAFE_INTEGER:
        raise ValueError(
            f"the seed source returned {seed}, which is outside the range a ledger entry "
            f"can record exactly (0..{MAX_SAFE_INTEGER}). R5 requires the seed to be part "
            "of the record, so a seed that cannot be written cannot be rolled with"
        )
    return seed


def _as_this_creature_saves(state: EncounterState, actor_id: str, proposal: Proposal) -> Proposal:
    """The proposal as the creature actually rolls it, once its own state is consulted (#344).

    Three printed rules act on a saving throw because of what the roller is holding, and none
    of them belongs to the rule that compelled the save:

    * **Four conditions make it fail outright** (pp. 186, 189, 191) — "You automatically fail
      Strength and Dexterity saving throws."
    * **Restrained hampers it** (p. 187) — "You have Disadvantage on Dexterity saving throws."
    * **Dodge helps it** (p. 181) — "you make Dexterity saving throws with Advantage", and the
      benefit is re-checked rather than remembered, because Incapacitated or a Speed of 0 ends
      it.

    **Central because the alternative is six copies and a seventh that forgets.** Every
    resolver that builds a save gets these free, and a resolver written next year gets them
    without knowing they exist. The rules themselves stay where they are described:
    `Conditions` and `ActionBudget` answer, and this applies.

    ## An automatic failure is not a roll, and is not a rolled failure

    p. 186 says the save fails, not that it is rolled badly. So the test is **removed** and the
    proposal resolves through 0027 clause 6's testless path, with `on_failure` becoming the
    outcome — a `Ruling` with no `D20Result` at all. Rolling a die and discarding it would put
    a number in the ledger that decided nothing, which reads exactly like a save that was
    rolled and lost.

    `always` survives untouched, because what the act cost does not depend on how it went
    (0038 clause 6).

    A proposal with no test, or a test that is not a save, or a save of no ability, is returned
    unchanged. The last is p. 17's Death Saving Throw, which has no ability and which none of
    these three rules reaches.
    """
    actor = _saving_creature(state, actor_id, proposal)
    test = proposal.test
    if actor is None or test is None:
        return proposal
    # No `test.ability is None` guard, deliberately. Every rule below keys on the ability and
    # answers "nothing" for a save that has none, so a guard here would be a second place for
    # the same fact — and a corruption proof showed it was carrying no weight: removing it
    # left the assertion green, because `Conditions` was already refusing.
    if actor.conditions.saves_fail_outright(test.ability):
        # Handled by the caller, which selects the failure branch without rolling. Returned
        # unchanged here so the advantage below is never computed for a save that will not
        # happen — an automatic failure is not a roll at Disadvantage.
        return proposal

    from_conditions = actor.conditions.save_advantage(test.ability)
    # p. 181's Dodge, through `is_dodging` rather than the raw flag: the benefit is lost to
    # Incapacitated or a Speed of 0, and `still_dodging` is what asks.
    dodging = actor.is_dodging and test.ability == "dex"
    advantage = from_conditions is Advantage.ADVANTAGE or dodging
    disadvantage = from_conditions is Advantage.DISADVANTAGE
    if not advantage and not disadvantage:
        return proposal
    # Accumulated onto whatever the rule itself granted, never replacing it — p. 8 cancels
    # sources on opposite sides, and cancellation needs both to arrive.
    return replace(
        proposal,
        test=replace(
            test,
            has_advantage=test.has_advantage or advantage,
            has_disadvantage=test.has_disadvantage or disadvantage,
        ),
    )


def _saving_creature(state: EncounterState, actor_id: str, proposal: Proposal) -> Combatant | None:
    """The creature rolling this proposal's saving throw, or `None` if it is not one.

    `None` covers a proposal with no test, a test that is not a save, and an actor the
    encounter no longer holds. A save of no ability still returns the creature, because the
    caller distinguishes "not a save" from "a save this cannot key on" — p. 17's Death Saving
    Throw is the second, and it is a save.
    """
    test = proposal.test
    if test is None or test.kind is not TestKind.SAVE:
        return None
    if not state.has(actor_id):
        return None
    return state.combatant(actor_id)


def _save_fails_outright(state: EncounterState, actor_id: str, proposal: Proposal) -> bool:
    """Whether this saving throw fails without being rolled (pp. 186, 189, 191, #344)."""
    actor = _saving_creature(state, actor_id, proposal)
    if actor is None or proposal.test is None:
        return False
    return actor.conditions.saves_fail_outright(proposal.test.ability)


def _branch(proposal: Proposal, result: D20Result | None) -> Sequence[Declared]:
    """Which branch the roll selected, or the only branch there is.

    The natural-die branches win where a resolver supplied one, because the rules that
    need them say so in terms: a natural 1 on a death save costs two failures *instead of*
    the one an ordinary failure costs, not as well as.
    """
    # 0038 clause 6. What the act cost comes first, and comes whatever was selected: p. 104
    # spends the slot on the casting, not on the outcome. First rather than last so that a
    # conditional in the selected branch reads a state the cost has already settled, and so
    # that the ledger records the cost before the consequence — which is the order they
    # happened in.
    if result is None:
        # 0027 clause 6: no test, so no branch was selected — there is one.
        return (*proposal.always, *proposal.outcome)
    if result.used == DIE_SIDES and proposal.on_natural_20 is not None:
        return (*proposal.always, *proposal.on_natural_20)
    if result.used == 1 and proposal.on_natural_1 is not None:
        return (*proposal.always, *proposal.on_natural_1)
    selected = proposal.on_success if result.succeeded else proposal.on_failure
    return (*proposal.always, *selected)


def _roll_declared(
    branch: Sequence[Declared], *, seed: int, critical: Critical = Critical.NONE
) -> tuple[Effect, ...]:
    """Turn a branch into settled effects, rolling any dice the resolver declared.

    Each expression consumes its own stretch of the seed's index space, so two damage
    dice in one branch cannot silently share a die and report the same number twice.

    On a Critical Hit the Rules Glossary (p. 179) says to "roll all of the attack's damage
    dice twice and add them together. Then add any relevant modifiers." Two things follow,
    and both are easy to get wrong: **every** damage expression in the branch doubles, not
    just the weapon's, and the **modifier does not** — it is added once, after.

    Doubling the count rather than rolling the same dice twice is deliberate: it consumes
    twice the index space, so the two halves of a critical cannot land on the same die.
    """
    settled: list[Effect] = []
    offset = DAMAGE_OFFSET
    for declared in branch:
        if isinstance(declared, Effect):
            settled.append(declared)
            continue
        count = declared.count * 2 if critical is Critical.HIT else declared.count
        faces = dice(seed, count=count, sides=declared.sides, offset=offset)
        offset += count
        total = max(0, sum(faces) + declared.modifier)
        crit = " (Critical Hit: damage dice doubled)" if critical is Critical.HIT else ""
        settled.append(
            Effect(
                kind=EffectKind.DAMAGE,
                target_id=declared.target_id,
                amount=total,
                critical=critical is Critical.HIT,
                damage_type=declared.damage_type,
                description=(
                    f"{declared.source}: {count}d{declared.sides}"
                    f"{_signed(declared.modifier)}{crit} -> "
                    f"{' + '.join(str(f) for f in faces) or '0'}"
                    f"{_signed(declared.modifier)} = {total}"
                ),
            )
        )
    return tuple(settled)


def _signed(modifier: int) -> str:
    return "" if modifier == 0 else f" {'+' if modifier > 0 else '-'} {abs(modifier)}"


def _apply(
    state: EncounterState,
    effects: Sequence[Effect],
    *,
    seed: int,
    rule_id: str | None = None,
) -> tuple[EncounterState, tuple[Effect, ...], tuple[Effect, ...]]:
    """Apply the settled effects, and hand back what landed and what was withheld (R5, #105).

    Damage arrives here as rolled, because the dice are rolled before a target's defences
    are consulted. p. 17's Immunity, Resistance and Vulnerability act inside `with_damage`,
    which is the single place they are ever applied — so this asks the state what the blow
    will come to, lets `with_damage` apply it from the *rolled* figure exactly as before,
    and rewrites the effect to say what landed. Both numbers come from one call on the
    state, so the reported amount and the applied amount cannot disagree.

    `seed` travels because becoming Stable rolls a die — p. 18's 1d4 hours to recovery,
    drawn at stabilisation rather than on demand (0020).

    ## Where a conditional effect is asked, and why it can only be here (0032 clause 2)

    An effect carrying a `when` applies only if its predicate holds. This is the one place
    that can ask, and the reason is one word: **taken**.

    A fall deals `1d6` and the creature is Prone "unless it avoids taking any damage"
    (p. 182). There are three moments a branch passes through — the resolver, which has no
    number at all; `_roll_declared`, which has the **rolled** number; and here, which has the
    number the target actually **took**. p. 17's Resistance is the entire difference between
    the last two, and it is exactly the case
    [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173) is about: a resistant
    creature rolling a 1 on one die takes 0 and must not be Prone. Asking one function
    earlier would look right and ship that bug.

    `taken` accumulates per target as the walk proceeds, so a conditional reads only what
    precedes it — which `Proposal.__post_init__` refuses to leave empty.

    **Withheld effects are returned, not dropped** (0032 clause 4). A withheld Prone that
    left no trace would be indistinguishable from a Prone nobody considered, and the second
    is the failure this engine exists to prevent. They are kept apart from `landed` because
    the standing narration bound is "that the effects recorded here happened" — an effect
    that did not happen cannot sit in the list that sentence describes.
    """
    landed: list[Effect] = []
    withheld: list[Effect] = []
    taken: dict[str, int] = {}
    for effect in effects:
        if effect.kind is EffectKind.DAMAGE:
            outcome = state.damage_after_defences(
                effect.target_id, effect.amount, effect.damage_type
            )
            taken[effect.target_id] = taken.get(effect.target_id, 0) + outcome.amount
            landed.append(_as_taken(effect, outcome))
            state = state.with_damage(
                effect.target_id,
                effect.amount,
                critical=effect.critical,
                damage_type=effect.damage_type,
            )
            continue

        subject = effect.when_subject_id or effect.target_id
        if effect.when is not None and not _holds(effect.when, subject, taken):
            withheld.append(effect)
            continue

        landed.append(effect)
        if effect.kind is EffectKind.HEALING:
            state = state.with_healing(effect.target_id, effect.amount)
        elif effect.kind is EffectKind.DEATH_SAVE_SUCCESS:
            state = state.with_death_save(effect.target_id, successes=effect.amount, seed=seed)
        elif effect.kind is EffectKind.DEATH_SAVE_FAILURE:
            state = state.with_death_save(effect.target_id, failures=effect.amount)
        elif effect.kind is EffectKind.STABILISED:
            state = state.with_stabilised(effect.target_id, seed=seed)
        elif effect.kind is EffectKind.DEATH:
            state = state.with_death(effect.target_id)
        elif effect.kind is EffectKind.CONDITION_APPLIED:
            assert effect.condition is not None  # __post_init__ refuses one without
            # Read before applying: what the creature holds is the thing p. 191 sheds, and
            # reading it afterwards would work today only because applying a condition
            # happens not to touch equipment.
            shed = _shed_by(state, effect.target_id, effect.condition)
            state = state.with_condition(
                effect.target_id,
                effect.condition,
                duration=effect.duration,
                source_id=effect.source_id,
                grapple=effect.grapple,
            )
            # p. 191: "you drop whatever you're holding". Derived by the engine rather than
            # left to the resolver that applied the condition, for the reason implication is
            # derived — a ruleset that forgot would keep a sword in an unconscious hand, and
            # nothing would say so. They land as their own effects, so the ledger records
            # each one and R7 leaves the narrator free to report it.
            for dropped in shed:
                landed.append(dropped)
                assert dropped.item_id is not None  # __post_init__ refuses one without
                state = state.with_object_detached(dropped.target_id, dropped.item_id)
        elif effect.kind is EffectKind.CONDITION_ENDED:
            assert effect.condition is not None
            state = state.with_condition_ended(effect.target_id, effect.condition)
        elif effect.kind is EffectKind.ACTION_SPENT:
            assert effect.action is not None  # __post_init__ refuses one without
            state = state.with_action_spent(
                effect.target_id, effect.action, weapon_id=effect.weapon_id
            )
        elif effect.kind is EffectKind.DASHED:
            state = state.with_dash(effect.target_id, effect.amount)
        elif effect.kind is EffectKind.DODGING:
            state = state.with_dodge(effect.target_id)
        elif effect.kind is EffectKind.DISENGAGED:
            state = state.with_disengage(effect.target_id)
        elif effect.kind is EffectKind.SPELL_SLOT_EXPENDED:
            state = state.with_spell_slot_expended(effect.target_id, effect.amount)
        elif effect.kind is EffectKind.CONCENTRATION_BEGUN:
            # 0028 clause 1's move, for the same reason: what the Concentration is *on* is
            # the ruling's own rule, so it is taken from here rather than carried on the
            # effect. No payload field, and no way to claim a source the ruling did not have.
            assert rule_id is not None, "an outcome always names the rule that produced it"
            state = state.with_concentration_begun(effect.target_id, rule_id)
        elif effect.kind is EffectKind.CONCENTRATION_ENDED:
            state = state.with_concentration_ended(effect.target_id)
        elif effect.kind is EffectKind.OBJECT_DETACHED:
            assert effect.item_id is not None  # __post_init__ refuses one without
            state = state.with_object_detached(effect.target_id, effect.item_id)
        elif effect.kind is EffectKind.CARRIAGE_CHANGED:
            assert effect.item_id is not None and effect.carriage is not None
            state = state.with_carriage_changed(effect.target_id, effect.item_id, effect.carriage)
        elif effect.kind is EffectKind.OBJECT_PICKED_UP:
            assert effect.item_id is not None
            state = state.with_object_picked_up(effect.target_id, effect.item_id)
        elif effect.kind is EffectKind.ATTACK_MADE:
            state = state.with_attack_made(effect.target_id)
        elif effect.kind is EffectKind.OBJECT_INTERACTED:
            state = state.with_object_interaction(effect.target_id)
        elif effect.kind is EffectKind.EXTRA_ATTACK_MADE:
            state = state.with_extra_attack(effect.target_id)
        elif effect.kind is EffectKind.CLEAVE_OPENED:
            assert effect.weapon_id is not None and effect.source_id is not None
            state = state.with_cleave_opening(effect.target_id, effect.weapon_id, effect.source_id)
        elif effect.kind is EffectKind.SPEED_REDUCED:
            assert effect.speed_reduction is not None  # the constructor requires one
            state = state.with_speed_reduction(effect.target_id, effect.speed_reduction)
        elif effect.kind is EffectKind.CLEAVE_TAKEN:
            state = state.with_cleave_taken(effect.target_id)
        elif effect.kind is EffectKind.ADVANTAGE_PENDING:
            assert effect.pending_advantage is not None  # the constructor requires one
            state = state.with_pending_advantage(effect.pending_advantage)
        elif effect.kind is EffectKind.ADVANTAGE_SPENT:
            assert effect.pending_advantage is not None
            state = state.without_pending_advantage((effect.pending_advantage,))
        elif effect.kind is EffectKind.SAVE_COMPELLED:
            assert effect.forced_save is not None  # the constructor requires one
            state = state.with_forced_save(effect.forced_save)
        elif effect.kind is EffectKind.AMMUNITION_SPENT:
            assert effect.item_id is not None  # __post_init__ refuses one without
            state = state.with_ammunition_spent(effect.target_id, effect.item_id)
        elif effect.kind is EffectKind.AMMUNITION_RECOVERED:
            assert effect.item_id is not None  # __post_init__ refuses one without
            state = state.with_ammunition_recovered(effect.target_id, effect.item_id, effect.amount)
        elif effect.kind is EffectKind.TIME_PASSED:
            state = state.with_time_passed(effect.amount)
        elif effect.kind is EffectKind.LOADING_FIRED:
            assert effect.action is not None  # __post_init__ refuses one without
            state = state.with_loading_shot(effect.target_id, str(effect.action))
        elif effect.kind is EffectKind.EXHAUSTION_GAINED:
            # 0028 clause 1: the level carries the rule that caused it, and the ruling's
            # own rule is that rule. Taking it from here rather than from the effect keeps
            # the ledger's existing `rule_id` the record of provenance — no payload field,
            # and no way for an effect to claim a source its ruling did not have.
            assert rule_id is not None, "an outcome always names the rule that produced it"
            state = state.with_exhaustion(effect.target_id, rule_id, effect.amount)
        else:
            # Death was this branch until #119, which is the hazard: every kind added since
            # would have silently become a death. An unhandled kind now says so instead.
            raise ValueError(
                f"no state transition for {effect.kind}. An effect kind reaches state "
                "through a branch here or not at all — falling through to another kind's "
                "transition is the quiet direction to be wrong in"
            )
    # p. 182's grapple endings, asked after the effects have landed rather than before.
    # They are *derived* — "the condition also ends if the grappler has the Incapacitated
    # condition or if the distance ... exceeds the grapple's range" — so the moment to ask is
    # the moment the state they read has settled. This ruling is what may have Incapacitated
    # the grappler or moved either creature, and asking first would answer about the state
    # that no longer holds.
    #
    # The same function the turn sweep calls, so an ending cannot be remembered in one place
    # and forgotten in the other (0050 clause 3's rule, applied to a second pair of sites).
    state = grapples_released(state)

    return state, tuple(landed), tuple(withheld)


def _shed_by(state: EncounterState, target_id: str, condition: Condition) -> tuple[Effect, ...]:
    """The items a condition makes its holder let go of (p. 191, #280).

    One condition states this today — Unconscious, whose entry reads "you drop whatever
    you're holding" — and it is declared on `ConditionEffects` rather than matched on here,
    so a second one arrives with its citation and needs no change to this function.

    **Held items only.** "Holding" is what p. 191 says; worn armour and a stowed rope are
    carried and are not shed. `Carriage.HELD` is exactly that distinction.

    A creature that already has the condition holds nothing to drop, so re-applying it is
    naturally idempotent rather than specially cased.
    """
    if not CONDITION_EFFECTS[condition].drops_held_items:
        return ()
    target = state.combatant(target_id)
    return tuple(
        object_detached(
            target_id,
            item.id,
            description=f"{target.name} drops {item.id}: p. 191, Unconscious",
        )
        for item in items_in(target.equipment, Carriage.HELD)
    )


def _holds(when: When, target_id: str, taken: Mapping[str, int]) -> bool:
    """Whether a predicate holds, against damage this ruling has already applied.

    One member, one sentence (0032 clause 3). A new member arrives with the printed rule it
    serves and a clause asserting it, and the exhaustiveness below is what makes forgetting
    the second half impossible to do quietly.

    `target_id` is the **subject** of the predicate rather than the effect's own target, and
    the two differ whenever a rule conditions one creature's benefit on another's damage —
    p. 90's Vex, which is why `Effect.when_subject_id` exists (0049).
    """
    if when is When.DAMAGE_TAKEN:
        # p. 182: "unless it avoids taking any damage". Any amount at all satisfies it, so
        # the test is `> 0` rather than a threshold — and it reads `taken`, which is the
        # post-defences figure, never the roll.
        return taken.get(target_id, 0) > 0
    raise ValueError(  # pragma: no cover - unreachable while `When` has one member
        f"no evaluation for {when}. A predicate reaches an answer through a branch here or "
        "not at all; falling through to a default would withhold or apply silently"
    )


def _as_taken(effect: Effect, outcome: DamageOutcome) -> Effect:
    """Rewrite a damage effect to report what the target took, showing p. 17's arithmetic.

    Left exactly as it was when no defence acted, so `rolled` being set means one did.

    The test is whether a defence *acted*, not whether the number moved, and the difference
    is not hypothetical: Resistance and Vulnerability to the same type do not cancel — they
    halve and then double, which returns an even amount to itself. Comparing the amounts
    would call that untouched and hide two steps the document walks through by name.
    """
    if len(outcome.steps) <= 1:
        return effect
    return replace(
        effect,
        amount=outcome.amount,
        rolled=effect.amount,
        description=f"{effect.description}; {outcome.derivation()}",
    )


# --- Ledger payloads ----------------------------------------------------------------


def _entry_type(status: Status) -> str:
    if status is Status.REJECTED:
        return "rejection"
    if status is Status.CHALLENGED:
        return "challenge"
    return "ruling"


def _declaration_payload(
    declaration: Declaration, catalogue_version: int, *, resuming: bool = False
) -> Mapping[str, object]:
    return {
        COMPAT: DECLARATION_COMPAT,
        # #59. True when the engine picked this declaration back up after a block, rather
        # than the agent declaring again. Always present rather than only when true: a
        # reader must be able to tell "not a resumption" from "written before the field
        # existed", and an absent key says only the second.
        "resumption": resuming,
        # R6: replay uses the catalogue version in force, not the current one, so a
        # grown catalogue never reports a sound ledger as inconsistent.
        "catalogue_version": catalogue_version,
        "actor": declaration.actor_id,
        "intent": {
            "action_key": declaration.intent.action_key,
            "improvised": declaration.intent.improvised,
            "label": declaration.intent.label,
        },
        "rule_id": declaration.rule_id,
        "no_test_reason": declaration.no_test_reason,
        "alternatives": [dict(a.identity()) for a in declaration.alternatives],
        "read_token": declaration.read_token,
    }


def _effect_payload(e: Effect) -> Mapping[str, object]:
    """One effect as the ledger records it.

    Shared by `effects` and `withheld` (0032 clause 4) rather than written twice: a withheld
    effect that recorded less than an applied one would be a record that says least about
    the case a reader is most likely to be checking.
    """
    return {
        "kind": str(e.kind),
        "target": e.target_id,
        # What the target took. `rolled` and `damage_type` are what make that recomputable:
        # without the type there is no way to check p. 17's arithmetic from the record,
        # which is the state this fixed (#105).
        "amount": e.amount,
        "rolled": e.rolled,
        "damage_type": str(e.damage_type) if e.damage_type else None,
        # #119. A condition effect's amount is 0, so without these the record says a
        # condition changed and not which one — and a replay comparing effects would call
        # two different conditions identical.
        "condition": str(e.condition) if e.condition else None,
        "duration": e.duration.derivation() if e.duration else None,
        "source": e.source_id,
        # 0032 clause 4. The predicate, so the record says what was ASKED as well as what
        # was answered — an effect that applied unconditionally and one whose condition
        # happened to hold are different facts.
        "action": str(e.action) if e.action else None,
        # p. 89. In the record because p. 89's Light property turns on *which* weapon the
        # Attack action was spent on, and a replay that could not see it could not check it.
        "weapon": e.weapon_id,
        "when": str(e.when) if e.when else None,
        "description": e.description,
    }


def _ruling_payload(ruling: Ruling) -> Mapping[str, object]:
    result = ruling.result
    return {
        COMPAT: RULING_COMPAT,
        "status": str(ruling.status),
        "actor": ruling.declaration.actor_id,
        "rule_id": ruling.rule_id,
        "alternatives_verdict": str(ruling.alternatives_verdict),
        "reason": ruling.reason,
        "reason_code": str(ruling.reason_code) if ruling.reason_code else None,
        "reason_subject": ruling.reason_subject,
        "unresolved": list(ruling.unresolved),
        "fired": [
            {"id": t.id, "grounding": str(t.grounding), "basis": t.reference or t.rationale}
            for t in ruling.fired
        ],
        "citations": list(ruling.citations),
        "facts": [
            {
                "type": r.type_name,
                "subject": r.subject,
                "value": r.value,
                "defaulted": str(r.defaulted) if r.defaulted else None,
                "provenance": dict(r.provenance.as_payload()) if r.provenance else None,
            }
            for r in ruling.facts
        ],
        "effects": [_effect_payload(e) for e in ruling.effects],
        # 0032 clause 4. Considered and not applied, kept in its own list so that "effects"
        # stays the set the standing narration bound describes — "the effects recorded here
        # happened". Absent from a record that withheld nothing, so a reader never has to
        # tell an empty list from a ruling that could not have one.
        **({"withheld": [_effect_payload(e) for e in ruling.withheld]} if ruling.withheld else {}),
        "bounds": {"may": list(ruling.bounds.may), "may_not": list(ruling.bounds.may_not)},
        # 0027 clause 6. Whether this outcome HAD a d20, stated rather than left to be
        # inferred from `roll` being null — a thin record and a rule that never rolled look
        # identical from the absence alone, and only one of them is a defect.
        "testless": ruling.status is Status.RULED and result is None,
        "roll": None
        if result is None
        else {
            "kind": str(result.kind),
            "seed": result.seed,
            # Without these the recorded dice cannot be re-derived: the count, and which
            # of them was used, both depend on the advantage the test was declared under.
            "declared_advantage": result.declared_advantage,
            "declared_disadvantage": result.declared_disadvantage,
            "effective_advantage": str(result.effective),
            "dice": list(result.dice),
            "used": result.used,
            "target": result.target,
            "target_basis": result.target_basis,
            "modifiers": [{"source": m.source, "value": m.value} for m in result.modifiers],
            "total": result.total,
            "succeeded": result.succeeded,
            "derivation": result.derivation(),
        },
    }


def defaulted_kinds(ruling: Ruling) -> Mapping[str, DefaultKind]:
    """Which facts defaulted, and which kind of default applied (R22, AE3)."""
    return {r.type_name: r.defaulted for r in ruling.facts if r.defaulted is not None}
