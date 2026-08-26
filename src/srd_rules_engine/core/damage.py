"""Damage types, and what a threshold, Resistance, Vulnerability and Immunity do to an amount.

R12's share of "damage application, types, resistance/vulnerability/immunity". The rules
are read off SRD v5.2.1 — "Playing the Game" ("Damage and Healing" -> "No Stacking" and
"Order of Application"), p. 17, and the Rules Glossary entries for Damage Types p. 180,
Immunity p. 183, Resistance p. 187 and Vulnerability p. 191.

## Three rules that are usually played wrong

* **Order is fixed and it is not commutative.** p. 17: "adjustments such as bonuses,
  penalties, or multipliers are applied first; Resistance is applied second; and
  Vulnerability is applied third." Halving before doubling is not the same as doubling
  before halving once rounding is involved, which is why the document states an order at
  all rather than leaving it to arithmetic.
* **Rounding happens at the halving, not at the end.** Resistance halves "(round down)",
  and the document's own worked example rounds there: 28 Fire damage reduced by 5 is 23,
  "then halved for the creature's Resistance (and rounded down to 11), then doubled for
  its Vulnerability (to 22)". Deferring the rounding gives 23, which is a different
  answer to the one the document prints.
* **Neither stacks.** p. 17: "Multiple instances of Resistance or Vulnerability that
  affect the same damage type count as only one instance." Holding Resistance to Necrotic
  *and* to all damage halves Necrotic once. Sets rather than counters make that the only
  representable reading — the same move `has_advantage` makes for the d20.

Resistance and Vulnerability on the same type do **not** cancel to nothing here. They are
applied in order, and the document gives the case in its own example: a creature with
Resistance to all damage and Vulnerability to Fire takes 28 down to 11 and back to 22, not
28. Cancelling them would be the advantage rule imported into a place the document never
put it.

## The damage threshold is here, and it is a defence (#214)

p. 180 gives big objects, vehicles and at least one trap a threshold below which they have
"**Immunity** to all damage". It reads like a rule keyed on the size of a blow — which is
the shape 0032 is about — and it is not one: what it modifies is *the damage itself*, before
anything else looks at the number, which is exactly what this module does.

Where it sits in the order is **derived rather than chosen**, and `after_defences` sets out
the derivation. The short version: p. 17's Order of Application names three steps and this is
not one of them, so no ordering is stated — but p. 180 classifies the threshold as Immunity,
Immunity is already first, and the sentence names what it is asked about ("an amount of
damage from a single attack or effect", "that entire instance").

## What is deliberately absent

**Condition Immunity.** The glossary entry covers "a damage type **or** a condition", and
conditions are [#18](https://github.com/eddiefiggie/srd-rules-engine/issues/18). Damage
immunity works here; the shape is not claimed as implemented, because a binary flag cannot
say half, and overstating coverage is the failure R17 exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: R31. The order and the no-stacking rule are the whole of this module's fidelity.
DAMAGE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Playing the Game" ("Damage and Healing" -> "No Stacking" and '
        '"Order of Application"), p. 17; Rules Glossary, Damage Threshold and Damage '
        "Types p. 180, Immunity p. 183, Resistance p. 187, Vulnerability p. 191"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


class DamageType(StrEnum):
    """The thirteen types the Damage Types table names (p. 180).

    "Damage types have no rules of their own, but other rules, such as Resistance, rely on
    the types." So this is a closed set of names and nothing more — the behaviour lives in
    the defences that reference them.
    """

    ACID = "acid"
    BLUDGEONING = "bludgeoning"
    COLD = "cold"
    FIRE = "fire"
    FORCE = "force"
    LIGHTNING = "lightning"
    NECROTIC = "necrotic"
    PIERCING = "piercing"
    POISON = "poison"
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    SLASHING = "slashing"
    THUNDER = "thunder"


@dataclass(frozen=True)
class Defences:
    """What a creature resists, is vulnerable to, and is immune to.

    Sets rather than counters, because "multiple instances ... count as only one instance"
    (p. 17). A count could represent two Resistances to Fire; a set cannot, so the
    no-stacking rule holds by construction rather than by a check somebody has to run.
    """

    resistances: frozenset[DamageType] = field(default_factory=frozenset)
    vulnerabilities: frozenset[DamageType] = field(default_factory=frozenset)
    immunities: frozenset[DamageType] = field(default_factory=frozenset)
    #: Resistance to *all* damage, as in the document's worked example. A separate flag
    #: rather than every type listed, so "all" survives a new type being added.
    resists_all: bool = False
    #: p. 180, Damage Threshold. `None` for a creature or object that has none, which is
    #: different from a threshold of 0 — every instance meets a threshold of 0, so it is a
    #: threshold that does nothing rather than the absence of one. The document gives them
    #: to big objects (p. 178, "castle walls"), vehicles (p. 101) and at least one trap
    #: (p. 201's rolling stone, threshold 10).
    damage_threshold: int | None = None

    def __post_init__(self) -> None:
        if self.damage_threshold is not None and self.damage_threshold < 0:
            raise ValueError(
                f"a damage threshold of {self.damage_threshold} is not a quantity of "
                "damage. p. 180 compares an instance against it, and no instance is "
                "negative"
            )

    def meets_threshold(self, amount: int) -> bool:
        """Whether an instance of this size gets through (p. 180).

        **Equal counts.** "unless it takes an amount of damage from a single attack or
        effect **equal to or greater than** its damage threshold", and the following
        sentence agrees from the other side — damage "that fails to **meet or exceed**" it
        is superficial. Both operative sentences say `>=`; only the worked example
        abbreviates to "fails to exceed", about a 9 against a threshold of 10, where the
        two readings cannot disagree.

        A creature with no threshold meets every instance, so the gate is a no-op for
        almost everything.
        """
        return self.damage_threshold is None or amount >= self.damage_threshold

    def resists(self, damage_type: DamageType | None) -> bool:
        return self.resists_all or (damage_type is not None and damage_type in self.resistances)

    def is_vulnerable_to(self, damage_type: DamageType | None) -> bool:
        return damage_type is not None and damage_type in self.vulnerabilities

    def is_immune_to(self, damage_type: DamageType | None) -> bool:
        return damage_type is not None and damage_type in self.immunities


@dataclass(frozen=True)
class DamageOutcome:
    """The final amount and the arithmetic that produced it (R5)."""

    amount: int
    steps: tuple[str, ...]

    def derivation(self) -> str:
        return " -> ".join(self.steps) if self.steps else str(self.amount)


def after_defences(
    amount: int, damage_type: DamageType | None, defences: Defences
) -> DamageOutcome:
    """Apply the damage threshold and Immunity, then Resistance, then Vulnerability.

    `amount` is already adjusted: bonuses, penalties and multipliers are "applied first"
    (p. 17), and by the time damage reaches here the dice and their modifier have been
    summed. So this is the second and third steps of the order, plus Immunity, which
    short-circuits because it "doesn't affect you in any way" (p. 183).

    Untyped damage is possible — a resolver need not name a type — and it simply matches
    no defence. That is the honest reading: an untyped amount is not secretly typed.

    ## Where the threshold sits, and why that is read rather than chosen (#214)

    p. 17's *Order of Application* names three steps — adjustments, Resistance,
    Vulnerability — and a damage threshold is **not one of them**. Its position is
    therefore not stated as an ordering, and picking one would be inferring a rule value
    (R31). It does not have to be picked, because p. 180 classifies the threshold instead
    of sequencing it:

    > A creature or an object that has a damage threshold **has Immunity to all damage**
    > unless it takes an amount of damage from a single attack or effect equal to or
    > greater than its damage threshold, in which case it takes that entire instance of
    > damage.

    Immunity is already first here, and for a reason the document gives (p. 183: it
    "doesn't affect you in any way"). A threshold that confers Immunity is Immunity, so it
    is asked in the same place — and what it is asked *about* follows from the same
    sentence: "an amount of damage **from a single attack or effect**", repeated as "that
    entire **instance** of damage". Both name the instance arriving, not a figure some
    later step produced. p. 180's example says it a third way, twice, in the passive:
    damage "is **dealt** to it".

    **This is a derivation from a stated classification, not a chosen order**, and the
    difference matters because the two readings disagree the moment a creature has both a
    threshold and Resistance: an instance of 12 against a threshold of 10 gets through and
    is then halved to 6, where comparing the halved 6 against the threshold would instead
    make the creature Immune and deal nothing.

    **0030 clause 1 does not decide this, and must not be reached for it** — the trap 0031
    clause 2 names. Resolving "away from invention" would compare after Resistance (less
    damage) but before Vulnerability (also less damage), which is not one rule read two
    ways. It is a thumb on the scale, picked per case to minimise a number.

    **The threshold reduces nothing itself.** "It takes that entire instance of damage" is
    the gate declining to interfere, not a suspension of p. 17 — so Resistance and
    Vulnerability act afterwards exactly as they always do.
    """
    if amount < 0:
        raise ValueError("damage is not negative; healing is a separate change")

    steps = [str(amount)]

    if not defences.meets_threshold(amount):
        # p. 180: below the threshold the creature "has Immunity to all damage", and that
        # damage "is superficial and doesn't reduce Hit Points". Immunity, so it
        # short-circuits with Immunity rather than reducing toward zero.
        steps.append(f"0 (Immunity, below the damage threshold of {defences.damage_threshold})")
        return DamageOutcome(amount=0, steps=tuple(steps))

    if defences.is_immune_to(damage_type):
        steps.append(f"0 (Immunity to {damage_type})")
        return DamageOutcome(amount=0, steps=tuple(steps))

    result = amount
    if defences.resists(damage_type):
        result //= 2
        source = (
            "all damage"
            if defences.resists_all and damage_type not in defences.resistances
            else damage_type
        )
        steps.append(f"{result} (halved, Resistance to {source}, round down)")

    if defences.is_vulnerable_to(damage_type):
        result *= 2
        steps.append(f"{result} (doubled, Vulnerability to {damage_type})")

    return DamageOutcome(amount=result, steps=tuple(steps))
