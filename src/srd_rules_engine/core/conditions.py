"""The fifteen SRD conditions, with their mechanical effects attached (R14, R18).

R18 requires the read surface to report "active conditions **with their mechanical
effects**". A name alone puts the agent back to recalling 5e from training, which is the
capability this engine exists to remove — so every effect here is a typed field, and none
of them is prose.

Read off the Rules Glossary, pp. 177-191. `CONDITION_VERIFICATION` carries the citation and
`scripts/verify_d20_rules.py` re-checks the sentences they rest on.

## Conditions imply other conditions

Four of them include Incapacitated, and Unconscious includes Prone as well: "You have the
Incapacitated and Prone conditions" (p. 191). Implication is transitive and is resolved when
the set is built, so a caller asking whether a creature is Incapacitated never has to know
that Paralyzed implies it.

Unconscious carries a rule the implication cannot express — "When this condition ends, you
remain Prone" — so Prone survives it rather than lifting with it.

## Three effects are conditional, and only two can be computed

* **Prone** (p. 186): an attack against you "has Advantage if the attacker is within 5 feet
  of you. Otherwise, that attack roll has Disadvantage." Both directions, decided by
  distance — computable since decision 0014, and the two-sidedness is the part usually
  played as a flat Advantage.
* **Grappled** (p. 182): Disadvantage "on attack rolls against any target other than the
  grappler". Computable, because the grappler is recorded with the condition.
* **Frightened** (p. 182): Disadvantage "while the source of fear is within line of sight",
  and you "can't willingly move closer". **Line of sight is not modelled** — it needs the
  obstruction work of [#91](https://github.com/eddiefiggie/srd-rules-engine/issues/91) — so
  this engine applies the penalty whenever the condition is held, which is the *stricter*
  reading. Erring toward applying a penalty is disclosed rather than silent, and it is the
  direction that cannot invent a success.

## What is deliberately absent

**Charmed's "can't attack the charmer"** and **Invisible's "unless a creature can somehow
see you"** both need target legality and sight, which are #16's action economy and #91's
obstructions. The conditions are held and reported; those two clauses are not enforced, and
`unenforced_clauses` names them in typed form rather than leaving them to be discovered.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.duration import Duration, SaveEnds
from srd_rules_engine.core.position import Position, within
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: p. 186, Prone; p. 191, Unconscious — both name 5 feet.
ADJACENT_FEET: Final = 5

#: p. 181: "You die if your Exhaustion level is 6."
MAX_EXHAUSTION: Final = 6

#: The rule-id namespace for a condition's repeated save (p. 63).
#:
#: It lives here rather than in `core.save_ends` because `EncounterState` needs it and
#: `core.save_ends` imports `EncounterState` — so the resolver module cannot own the name
#: without a cycle. That is not merely a workaround: the id of "the save that ends
#: Poisoned" is a fact about the condition, and the resolver is what acts on it.
#:
#: `core.save_ends` re-exports both, so nothing importing them from there has to move.
SAVE_ENDS_PREFIX: Final = "save-ends"


def save_ends_rule_id(condition: Condition) -> str:
    """The rule id for this condition's repeated save."""
    return f"{SAVE_ENDS_PREFIX}:{condition.value}"


#: R31.
CONDITION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Blinded p. 177, Charmed p. 178, Deafened p. 181, "
        "Exhaustion p. 181, Frightened p. 182, Grappled p. 182, Incapacitated p. 184, "
        "Invisible p. 184, Paralyzed p. 186, Petrified p. 186, Poisoned p. 186, Prone "
        "p. 186, Restrained p. 187, Stunned p. 189, Unconscious p. 191"
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)


class Condition(StrEnum):
    """The fifteen conditions the Rules Glossary tags `[Condition]`."""

    BLINDED = "blinded"
    CHARMED = "charmed"
    DEAFENED = "deafened"
    EXHAUSTION = "exhaustion"
    FRIGHTENED = "frightened"
    GRAPPLED = "grappled"
    INCAPACITATED = "incapacitated"
    INVISIBLE = "invisible"
    PARALYZED = "paralyzed"
    PETRIFIED = "petrified"
    POISONED = "poisoned"
    PRONE = "prone"
    RESTRAINED = "restrained"
    STUNNED = "stunned"
    UNCONSCIOUS = "unconscious"


@dataclass(frozen=True)
class ConditionEffects:
    """What holding a condition does, in typed fields rather than prose (R18)."""

    #: Advantage/Disadvantage the condition confers, unconditionally.
    attack_rolls_against: Advantage = Advantage.NONE
    own_attack_rolls: Advantage = Advantage.NONE
    own_ability_checks: Advantage = Advantage.NONE
    initiative: Advantage = Advantage.NONE
    speed_zero: bool = False
    auto_fail_strength_and_dexterity_saves: bool = False
    dexterity_saves: Advantage = Advantage.NONE
    #: p. 186, p. 191: "Any attack roll that hits you is a Critical Hit if the attacker is
    #: within 5 feet of you."
    auto_critical_within_5_feet: bool = False
    #: p. 184: "You can't take any action, Bonus Action, or Reaction."
    cannot_act: bool = False
    concentration_broken: bool = False
    cannot_speak: bool = False
    auto_fail_checks_requiring_sight: bool = False
    auto_fail_checks_requiring_hearing: bool = False
    resistance_to_all_damage: bool = False
    immune_to_poisoned: bool = False
    implies: frozenset[Condition] = field(default_factory=frozenset)
    #: Clauses the engine holds but does not enforce, named rather than left to discovery.
    unenforced_clauses: tuple[str, ...] = ()


#: Each condition's effects, transcribed field by field from its glossary entry.
EFFECTS: Final[dict[Condition, ConditionEffects]] = {
    Condition.BLINDED: ConditionEffects(
        attack_rolls_against=Advantage.ADVANTAGE,
        own_attack_rolls=Advantage.DISADVANTAGE,
        auto_fail_checks_requiring_sight=True,
    ),
    Condition.CHARMED: ConditionEffects(
        unenforced_clauses=("cannot-attack-or-target-the-charmer", "charmer-social-advantage"),
    ),
    Condition.DEAFENED: ConditionEffects(auto_fail_checks_requiring_hearing=True),
    Condition.EXHAUSTION: ConditionEffects(),  # levels carry its arithmetic; see Conditions
    Condition.FRIGHTENED: ConditionEffects(
        own_attack_rolls=Advantage.DISADVANTAGE,
        own_ability_checks=Advantage.DISADVANTAGE,
        # `line-of-sight-qualifier` left this list in #192, when the source of fear
        # became state and `own_attack_rolls` could be told whether it is visible.
        unenforced_clauses=("cannot-willingly-approach-the-source",),
    ),
    Condition.GRAPPLED: ConditionEffects(speed_zero=True),
    Condition.INCAPACITATED: ConditionEffects(
        cannot_act=True,
        concentration_broken=True,
        cannot_speak=True,
        initiative=Advantage.DISADVANTAGE,
    ),
    Condition.INVISIBLE: ConditionEffects(
        attack_rolls_against=Advantage.DISADVANTAGE,
        own_attack_rolls=Advantage.ADVANTAGE,
        initiative=Advantage.ADVANTAGE,
        # `unless-seen-exception` left this list in #193, when the condition surface
        # could be told whether one creature sees another. The other clause needs a
        # notion of "an effect that requires its target to be seen", which nothing here
        # marks — a resolver knows whether its own rule needs sight and records it
        # nowhere.
        unenforced_clauses=("concealed-from-effects-requiring-sight",),
    ),
    Condition.PARALYZED: ConditionEffects(
        attack_rolls_against=Advantage.ADVANTAGE,
        speed_zero=True,
        auto_fail_strength_and_dexterity_saves=True,
        auto_critical_within_5_feet=True,
        implies=frozenset({Condition.INCAPACITATED}),
    ),
    Condition.PETRIFIED: ConditionEffects(
        attack_rolls_against=Advantage.ADVANTAGE,
        speed_zero=True,
        auto_fail_strength_and_dexterity_saves=True,
        resistance_to_all_damage=True,
        immune_to_poisoned=True,
        implies=frozenset({Condition.INCAPACITATED}),
        unenforced_clauses=("turned-to-inanimate-substance", "weight-and-ageing"),
    ),
    Condition.POISONED: ConditionEffects(
        own_attack_rolls=Advantage.DISADVANTAGE,
        own_ability_checks=Advantage.DISADVANTAGE,
    ),
    Condition.PRONE: ConditionEffects(
        own_attack_rolls=Advantage.DISADVANTAGE,
        unenforced_clauses=("righting-costs-half-speed", "movement-limited-to-crawling"),
    ),
    Condition.RESTRAINED: ConditionEffects(
        attack_rolls_against=Advantage.ADVANTAGE,
        own_attack_rolls=Advantage.DISADVANTAGE,
        speed_zero=True,
        dexterity_saves=Advantage.DISADVANTAGE,
    ),
    Condition.STUNNED: ConditionEffects(
        attack_rolls_against=Advantage.ADVANTAGE,
        auto_fail_strength_and_dexterity_saves=True,
        implies=frozenset({Condition.INCAPACITATED}),
    ),
    Condition.UNCONSCIOUS: ConditionEffects(
        attack_rolls_against=Advantage.ADVANTAGE,
        speed_zero=True,
        auto_fail_strength_and_dexterity_saves=True,
        auto_critical_within_5_feet=True,
        implies=frozenset({Condition.INCAPACITATED, Condition.PRONE}),
        unenforced_clauses=("drops-what-it-holds", "remains-prone-when-this-ends", "unaware"),
    ),
}


@dataclass(frozen=True)
class Conditions:
    """The conditions a creature holds, with implication already resolved.

    Held as a set, so a condition applied twice is held once — the same move
    `has_advantage` makes for the d20 and `Defences` makes for Resistance. Exhaustion is
    the exception the document itself carves out: "This condition is cumulative", so it
    carries a level rather than a membership.
    """

    held: frozenset[Condition] = field(default_factory=frozenset)
    #: Every Exhaustion level this creature holds, as the **rule id that caused it**, oldest
    #: first (0028 clause 1). The count is `exhaustion_level` and is derived from this.
    #:
    #: A tuple rather than an integer because four of the five removal rules turn on which
    #: level is which: breathing again takes every level *suffocation* caused (p. 189), and
    #: dehydration's and malnutrition's cannot be taken at all until the creature drinks or
    #: eats (pp. 181, 185). A count cannot answer either.
    #:
    #: The rule id rather than an enum of sources: seven sources appear across the Rules
    #: Glossary, the Gameplay Toolbox and the magic items, nothing suggests that is all of
    #: them, and a closed set in the data is a branch in every consumer (0019). It is the
    #: shape 0027 clause 2 chose for obligations.
    exhaustion_levels: tuple[str, ...] = ()
    #: Who imposed each condition, where the condition's own text turns on it (#192).
    #:
    #: A mapping rather than a field per condition, because two of the fifteen already need
    #: one and a third field beside the first two is the shape that arrives one PR at a time:
    #: Grappled's "any target other than the grappler" (p. 182) and Frightened's "while the
    #: source of fear is within line of sight" (p. 182).
    #:
    #: **A set per condition, because a condition is binary but its causes are not.** p. 179:
    #: "A condition doesn't stack with itself; a recipient either has a condition or doesn't."
    #: So a creature frightened by two monsters holds *one* Frightened condition with two
    #: sources — and Exhaustion, which p. 179 names as the exception to that rule, is why
    #: 0028 gave it levels instead.
    sources: Mapping[Condition, frozenset[str]] = field(default_factory=dict)
    #: How long each **applied** condition lasts (#18). Keyed by condition, and an implied
    #: one never appears here — it is held because its source is, so it lifts when that
    #: source does rather than carrying a span of its own. A condition absent from this map
    #: has no stated duration, which reads as `UNTIL_REMOVED` rather than as permanent.
    durations: Mapping[Condition, Duration] = field(default_factory=dict)
    #: What was applied, before implication. `held` is the closure over this and is what
    #: every reader wants; this is what removal has to work against, because taking a
    #: condition out of the closure would strand the ones it was implying.
    applied: frozenset[Condition] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if len(self.exhaustion_levels) > MAX_EXHAUSTION:
            raise ValueError(
                f"an Exhaustion level runs from 0 to {MAX_EXHAUSTION}, not "
                f"{len(self.exhaustion_levels)} — 6 is death (p. 181)"
            )
        if any(not rule_id for rule_id in self.exhaustion_levels):
            raise ValueError(
                "every Exhaustion level names the rule that caused it (0028 clause 1). An "
                "unattributed level cannot be answered for by four of the five rules that "
                "remove one"
            )
        # `held` is given as what was applied and is replaced by its closure, so a caller
        # constructing one the ordinary way needs to know nothing about implication.
        # Exhaustion is **implied by the level and never applied on its own**, so it is
        # stripped from `applied` before the closure puts it back from the level. Without
        # that, `replace(conditions, exhaustion_levels=())` keeps it: `applied` is legitimately
        # empty, `or` reads that as unspecified, and the already-closed `held` — which
        # contains the derived Exhaustion — becomes what was applied. The condition then
        # outlives its last level, which p. 181 says ends it ("When your Exhaustion level
        # reaches 0, the condition ends"). Found by #185, where a Long Rest first took one.
        applied = (self.applied or self.held) - {Condition.EXHAUSTION}
        object.__setattr__(self, "applied", applied)
        object.__setattr__(self, "held", _closure(applied, len(self.exhaustion_levels)))
        unknown = set(self.durations) - set(self.applied)
        if unknown:
            raise ValueError(
                f"durations name {sorted(unknown)}, which this creature was not given. A "
                "duration belongs to the application that imposed the condition, so one "
                "for a condition nobody applied has nothing to end"
            )
        object.__setattr__(self, "durations", MappingProxyType(dict(self.durations)))

    @property
    def grappler_id(self) -> str | None:
        """Who is grappling, or `None`. p. 182 speaks of one grappler and this engine keeps
        the singular reading: a second grappler is not expressible, and would be a second
        application of a condition that does not stack (p. 179)."""
        return next(iter(sorted(self.sources.get(Condition.GRAPPLED, frozenset()))), None)

    def sources_of(self, condition: Condition) -> frozenset[str]:
        """Who imposed this condition, in no particular order. Empty when nobody said."""
        return self.sources.get(condition, frozenset())

    def has(self, condition: Condition) -> bool:
        return condition in self.held

    @property
    def exhaustion_level(self) -> int:
        """p. 181: 1 to 6, and the number all of its arithmetic reads. Zero means the
        condition is not held at all.

        Derived rather than stored (0028 clause 1). p. 181 reduces every D20 Test by twice
        it and Speed by five feet times it, and kills at 6 — all over the total, and none of
        it over which levels they are.
        """
        return len(self.exhaustion_levels)

    def exhaustion_from(self, rule_id: str) -> int:
        """How many of this creature's levels that rule caused.

        p. 189's "all levels of Exhaustion it gained from suffocating" is this question, and
        it is the one a bare count could not answer.
        """
        return sum(1 for held in self.exhaustion_levels if held == rule_id)

    @property
    def dead_of_exhaustion(self) -> bool:
        """p. 181: "You die if your Exhaustion level is 6."""
        return self.exhaustion_level >= MAX_EXHAUSTION

    @property
    def effects(self) -> tuple[ConditionEffects, ...]:
        """Every held condition's effects, in a stable order."""
        return tuple(EFFECTS[c] for c in sorted(self.held, key=lambda c: c.value))

    @property
    def d20_penalty(self) -> int:
        """p. 181: "When you make a D20 Test, the roll is reduced by 2 times your
        Exhaustion level." A penalty rather than Disadvantage, so it is arithmetic."""
        return -2 * self.exhaustion_level

    def speed_after(self, speed: int) -> int:
        """The Speed left after every held condition has acted on it.

        Zero beats reduction: Grappled, Restrained, Paralyzed, Petrified and Unconscious
        each set Speed to 0 and say it "can't increase" (pp. 182, 186, 187, 191), so no
        later arithmetic lifts it. Exhaustion reduces "by 5 times your Exhaustion level"
        (p. 181), and Speed does not go negative.
        """
        if any(e.speed_zero for e in self.effects):
            return 0
        return max(0, speed - 5 * self.exhaustion_level)

    def cannot_act(self) -> bool:
        return any(e.cannot_act for e in self.effects)

    def attack_rolls_against(
        self,
        *,
        attacker: Position | None,
        target: Position | None,
        attacker_sees_you: bool = False,
    ) -> Advantage:
        """What an attack against this creature has, given where the attacker stands.

        `attacker_sees_you` is p. 184's exception to Invisible: "Attack rolls against you
        have Disadvantage... If a creature can somehow see you, you don't gain this benefit
        against that creature." It defaults to **False** — the reading that keeps the
        Disadvantage — because 0030 clause 1 asks what the wrong answer would *produce*, and
        dropping a Disadvantage the rules require makes an attacker hit more often and
        manufactures damage. Keeping one they do not require can only omit a hit.

        Its sibling `own_attack_rolls` takes the opposite default for the same sentence,
        which is 0030 clause 3 inside one condition: the question is asked of the outcome,
        not of the creature, and Invisible's two halves point opposite ways.

        Prone is the reason this takes positions rather than being a flat field. p. 186:
        an attack against a Prone creature "has Advantage if the attacker is within 5 feet
        of you. **Otherwise, that attack roll has Disadvantage.**" The second half is the
        part usually played as a flat Advantage, and getting it wrong helps the attacker
        at every range.

        Sources combine by the d20's own rule: holding both cancels to neither (p. 8).
        """
        # Invisible's Disadvantage is dropped only against a creature that certainly sees
        # this one (p. 184). Every other condition contributes unconditionally.
        contributing = [
            EFFECTS[c] for c in self.held if not (c is Condition.INVISIBLE and attacker_sees_you)
        ]
        advantage = any(e.attack_rolls_against is Advantage.ADVANTAGE for e in contributing)
        disadvantage = any(e.attack_rolls_against is Advantage.DISADVANTAGE for e in contributing)

        if self.has(Condition.PRONE):
            if attacker is not None and target is not None:
                if within(attacker, target, ADJACENT_FEET):
                    advantage = True
                else:
                    disadvantage = True
            else:
                # Without positions the engine cannot say which half applies, so it applies
                # neither rather than guessing the one that favours the attacker.
                pass

        return _combine(advantage, disadvantage)

    def own_attack_rolls(
        self,
        *,
        target_id: str | None = None,
        fear_in_sight: bool = True,
        target_blind_to_you: bool = False,
    ) -> Advantage:
        """What this creature's own attack rolls have.

        Grappled is conditional: Disadvantage "on attack rolls against any target other
        than the grappler" (p. 182), so attacking the grappler itself is unaffected.

        **Frightened is conditional too, and was not until #192.** p. 182 gives its
        Disadvantage "while the source of fear is within line of sight", and the source was
        not recorded, so the qualifier could not be asked. `fear_in_sight` is that answer,
        supplied by whoever holds the encounter — `EncounterState.fear_in_sight`.

        It **defaults to True**, which is 0030 clause 1 rather than convenience: a caller
        that cannot answer gets the reading that omits nothing, because applying a
        Disadvantage the rules may not require can only omit a hit, while dropping one they
        do require produces damage that should not exist.
        """
        # Iterated over the conditions rather than over `self.effects`, because one of them
        # now has to be skipped by name and the effects tuple does not say which is which.
        # Two conditional clauses, defaulting in opposite directions because 0030 clause 3
        # asks what the wrong answer would produce rather than which reading is kinder.
        # Frightened's Disadvantage is KEPT when unknown — keeping it can only omit a hit.
        # Invisible's Advantage is WITHHELD when unknown — granting one the rules may not
        # grant makes this creature hit more often and manufactures damage (p. 184).
        contributing = [
            EFFECTS[c]
            for c in self.held
            if not (c is Condition.FRIGHTENED and not fear_in_sight)
            and not (c is Condition.INVISIBLE and not target_blind_to_you)
        ]
        advantage = any(e.own_attack_rolls is Advantage.ADVANTAGE for e in contributing)
        disadvantage = any(e.own_attack_rolls is Advantage.DISADVANTAGE for e in contributing)

        if self.has(Condition.GRAPPLED) and target_id != self.grappler_id:
            disadvantage = True

        return _combine(advantage, disadvantage)

    # --- Duration (#18) ---------------------------------------------------------------

    def expired_after(self, round_number: int, actor_id: str) -> frozenset[Condition]:
        """Which applied conditions the end of that creature's turn retires.

        A read: it answers the question and changes nothing, so a caller that asks twice
        gets the same answer and the removal is a separate, deliberate step.
        """
        return frozenset(
            condition
            for condition, duration in self.durations.items()
            if duration.expires_at(round_number, actor_id)
        )

    def expired_by(self, elapsed_minutes: int) -> frozenset[Condition]:
        """Which applied conditions the clock reaching that minute retires (#111).

        The campaign-axis mirror of `expired_after`, and a read in the same way. Nothing
        here is an outcome: the minute was fixed when the condition was applied, so the
        clock arriving at it decides nothing that was not already decided.
        """
        return frozenset(
            condition
            for condition, duration in self.durations.items()
            if duration.expires_by(elapsed_minutes)
        )

    def saves_due_after(self, actor_id: str) -> Mapping[Condition, SaveEnds]:
        """Conditions on this creature that repeat a save at the end of its turns (p. 63).

        Reported rather than resolved. A save is an outcome and R1 leaves outcomes to the
        one adjudication entry point — this is the `makes_death_saves` move, one layer up.
        The turn loop consults it; the engine rolls it there or not at all.
        """
        return MappingProxyType(
            {
                condition: duration.save
                for condition, duration in self.durations.items()
                if duration.save is not None and condition in self.held
            }
        )

    def without(self, ending: frozenset[Condition]) -> Conditions:
        """The conditions left once these end, with implication recomputed rather than
        subtracted.

        Removing from the closure would strand what the ending condition was implying — a
        creature that stopped being Unconscious would keep an Incapacitated nobody applied.
        So removal works against `applied` and the closure is rebuilt, which also means a
        condition implied by *two* sources survives losing one of them.

        p. 191 carves out the exception: "When this condition ends, you remain Prone." So
        Prone is re-applied on its own behalf when Unconscious ends, rather than lifting
        with the source that was implying it.
        """
        if not ending:
            return self
        remaining = self.applied - ending
        if Condition.UNCONSCIOUS in ending and Condition.PRONE in self.held:
            remaining = remaining | {Condition.PRONE}
        return Conditions(
            held=frozenset(remaining),
            exhaustion_levels=self.exhaustion_levels,
            sources={c: s for c, s in self.sources.items() if c not in ending},
            durations={c: d for c, d in self.durations.items() if c in remaining},
        )

    def unretirable(self) -> tuple[Condition, ...]:
        """Held conditions this engine cannot end on its own, named rather than left to
        look permanent (0021 clause 6).

        Two ways in: a condition applied with no stated duration, and one whose stated span
        is on an axis the encounter does not count.
        """
        return tuple(
            sorted(
                (
                    c
                    for c in self.held
                    if c not in self.durations or not self.durations[c].retirable
                ),
                key=lambda c: c.value,
            )
        )

    def unenforced_clauses(self) -> tuple[str, ...]:
        """Everything held but not enforced, so a caller can see the gap rather than find it."""
        seen: list[str] = []
        for effects in self.effects:
            seen.extend(c for c in effects.unenforced_clauses if c not in seen)
        return tuple(seen)


def _closure(held: frozenset[Condition], exhaustion_level: int) -> frozenset[Condition]:
    """Resolve implication, transitively, when the set is built rather than when it is read."""
    resolved = set(held)
    if exhaustion_level > 0:
        resolved.add(Condition.EXHAUSTION)
    frontier = list(resolved)
    while frontier:
        implied = EFFECTS[frontier.pop()].implies - resolved
        resolved |= implied
        frontier.extend(implied)
    return frozenset(resolved)


def _combine(advantage: bool, disadvantage: bool) -> Advantage:
    """p. 8's cancellation rule, applied to conditions rather than to circumstances."""
    if advantage and disadvantage:
        return Advantage.NONE
    if advantage:
        return Advantage.ADVANTAGE
    if disadvantage:
        return Advantage.DISADVANTAGE
    return Advantage.NONE
