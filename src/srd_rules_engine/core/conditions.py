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

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.position import Position, within
from srd_rules_engine.core.rules import Verification, VerificationState

#: p. 186, Prone; p. 191, Unconscious — both name 5 feet.
ADJACENT_FEET: Final = 5

#: p. 181: "You die if your Exhaustion level is 6."
MAX_EXHAUSTION: Final = 6

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
        unenforced_clauses=("line-of-sight-qualifier", "cannot-willingly-approach-the-source"),
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
        unenforced_clauses=("concealed-from-effects-requiring-sight", "unless-seen-exception"),
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
    #: p. 181: 1 to 6. Zero means the condition is not held at all.
    exhaustion_level: int = 0
    #: p. 182: who is grappling, so "any target other than the grappler" is computable.
    grappler_id: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.exhaustion_level <= MAX_EXHAUSTION:
            raise ValueError(
                f"an Exhaustion level runs from 0 to {MAX_EXHAUSTION}, not "
                f"{self.exhaustion_level} — 6 is death (p. 181)"
            )
        object.__setattr__(self, "held", _closure(self.held, self.exhaustion_level))

    def has(self, condition: Condition) -> bool:
        return condition in self.held

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
        self, *, attacker: Position | None, target: Position | None
    ) -> Advantage:
        """What an attack against this creature has, given where the attacker stands.

        Prone is the reason this takes positions rather than being a flat field. p. 186:
        an attack against a Prone creature "has Advantage if the attacker is within 5 feet
        of you. **Otherwise, that attack roll has Disadvantage.**" The second half is the
        part usually played as a flat Advantage, and getting it wrong helps the attacker
        at every range.

        Sources combine by the d20's own rule: holding both cancels to neither (p. 8).
        """
        advantage = any(e.attack_rolls_against is Advantage.ADVANTAGE for e in self.effects)
        disadvantage = any(e.attack_rolls_against is Advantage.DISADVANTAGE for e in self.effects)

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

    def own_attack_rolls(self, *, target_id: str | None = None) -> Advantage:
        """What this creature's own attack rolls have.

        Grappled is conditional: Disadvantage "on attack rolls against any target other
        than the grappler" (p. 182), so attacking the grappler itself is unaffected.
        """
        advantage = any(e.own_attack_rolls is Advantage.ADVANTAGE for e in self.effects)
        disadvantage = any(e.own_attack_rolls is Advantage.DISADVANTAGE for e in self.effects)

        if self.has(Condition.GRAPPLED) and target_id != self.grappler_id:
            disadvantage = True

        return _combine(advantage, disadvantage)

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
