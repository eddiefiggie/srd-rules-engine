"""The unified d20 test: one primitive spanning checks, saving throws, and attack rolls.

R11 makes these one thing rather than three. They share advantage state, proficiency, and
modifier machinery, and **differ only in where the target number came from** — a
difficulty class for a check or a save, an armour class for an attack. Building them
separately would mean building a third of the primitive and retrofitting the rest.

R4 says the engine rolls. No caller supplies a roll or a result; a caller supplies a seed,
and the seed is drawn per adjudication so a single entry replays from its own record
without replaying the entries before it.

**Dice are derived from the seed by SHA-256, not by `random`.** The replay guarantee has
to hold across machines and across Python versions, and `random`'s bit-consumption is an
implementation detail of the standard library rather than a specification. A hash is
specified forever, so a recorded seed produces the same dice in 2036 as today. Rejection
sampling keeps the distribution flat rather than introducing modulo bias.

The result carries the raw dice alongside the total, because R5 requires a Ruling to show
the arithmetic rather than assert the outcome.

## The advantage rules are verified

They were machinery asserted by the M1 plan until #52. They are now read off SRD v5.2.1 —
"Playing the Game" ("D20 Tests", pp. 7-8), and the Rules Glossary entries for Advantage
(p. 176) and Disadvantage (p. 181) — and `ADVANTAGE_VERIFICATION` carries the citation.
`scripts/verify_d20_rules.py` re-checks every sentence they rest on against the document,
so the date is falsifiable rather than decorative.

Two of the four questions #52 raised had answers the implementation could have got wrong:

* **Cancellation is presence-based, not count-based.** The document settles it outright:
  the roll has neither state "even if multiple circumstances impose Disadvantage and only
  one grants Advantage or vice versa". `has_advantage` and `has_disadvantage` are booleans
  rather than counters, so the count-based reading is not merely untaken here — it is
  unrepresentable, which holds more firmly than a test.
* **The unused die is not discarded.** Both dice stay individually addressable, because
  anything that lets you reroll or replace the d20 may replace "only one die, not both.
  You choose which one." `dice` therefore carries the pair rather than the one that
  counted, and that is a requirement rather than a convenience.

## A disclosed limit

Nothing here can yet *act* on that second point. Rerolling or replacing one die of a pair —
Heroic Inspiration is the document's own example, and it makes the new roll binding — is
unmodelled. The record is sufficient for it and the API is not, so the gap is filed rather
than assumed away. See
[#78](https://github.com/eddiefiggie/srd-rules-engine/issues/78).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.rules import Verification, VerificationState

DIE_SIDES: Final = 20

#: R31: the advantage semantics below are SRD-derived, so what they were checked against is
#: the whole basis for trusting them. `scripts/verify_d20_rules.py` re-checks the cited text
#: against the document — a date alone cannot notice a revision that reworded the rule.
ADVANTAGE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Playing the Game" ("D20 Tests" -> "Advantage/Disadvantage"), '
        "pp. 7-8; Rules Glossary, Advantage p. 176 and Disadvantage p. 181"
    ),
    date="2026-08-23",
)

#: The width of the hash slice a single die consumes.
_BITS: Final = 32

#: Where damage dice start in a seed's index space. One adjudication draws its d20 from
#: the low indices and its damage from here, so the two can never collide on a die.
DAMAGE_OFFSET: Final = 100


class TestKind(StrEnum):
    """The three kinds. They differ in where the target came from, not how it resolves."""

    CHECK = "ability-check"
    SAVE = "saving-throw"
    ATTACK = "attack-roll"


class Advantage(StrEnum):
    """The *effective* state, after sources on each side have cancelled."""

    NONE = "none"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass(frozen=True)
class Modifier:
    """One named contribution to the total, so the derivation reads back."""

    source: str
    value: int

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("a modifier names its source, or the derivation cannot be read")


@dataclass(frozen=True)
class D20Test:
    """Everything the roll needs, and everything the record must show it needed."""

    kind: TestKind
    target: int
    target_basis: str
    modifiers: tuple[Modifier, ...] = ()
    # Two independent flags rather than one three-valued field: a character can hold
    # advantage from one source and disadvantage from another at the same time, and the
    # cancellation is what resolves that. A single enum cannot express the input.
    has_advantage: bool = False
    has_disadvantage: bool = False

    def __post_init__(self) -> None:
        if not self.target_basis:
            raise ValueError(
                "a target number carries its derivation. R5 requires the Ruling to show "
                "where the number came from, not merely what it was"
            )


@dataclass(frozen=True)
class D20Result:
    """The roll, its inputs, and enough of both to reconstruct it from the record."""

    kind: TestKind
    seed: int
    target: int
    target_basis: str
    dice: tuple[int, ...]
    used: int
    declared_advantage: bool
    declared_disadvantage: bool
    effective: Advantage
    modifiers: tuple[Modifier, ...]
    total: int
    succeeded: bool

    @property
    def modifier_total(self) -> int:
        return sum(modifier.value for modifier in self.modifiers)

    def derivation(self) -> str:
        """The arithmetic in one line, in the order the modifiers were supplied."""
        parts = [str(self.used)]
        parts += [f"{m.value:+d} ({m.source})" for m in self.modifiers]
        outcome = "meets or beats" if self.succeeded else "falls short of"
        return f"{' '.join(parts)} = {self.total}, {outcome} {self.target} ({self.target_basis})"


def resolve(test: D20Test, *, seed: int) -> D20Result:
    """Roll the test and return its result. The engine rolls; no caller supplies one."""
    effective = _effective_advantage(test)
    count = 1 if effective is Advantage.NONE else 2
    dice = tuple(die(seed, index) for index in range(count))

    if effective is Advantage.ADVANTAGE:
        used = max(dice)
    elif effective is Advantage.DISADVANTAGE:
        used = min(dice)
    else:
        used = dice[0]

    total = used + sum(modifier.value for modifier in test.modifiers)
    return D20Result(
        kind=test.kind,
        seed=seed,
        target=test.target,
        target_basis=test.target_basis,
        dice=dice,
        used=used,
        declared_advantage=test.has_advantage,
        declared_disadvantage=test.has_disadvantage,
        effective=effective,
        modifiers=test.modifiers,
        total=total,
        succeeded=total >= test.target,
    )


def _effective_advantage(test: D20Test) -> Advantage:
    """Advantage and disadvantage cancel to a plain roll rather than accumulating."""
    if test.has_advantage and test.has_disadvantage:
        return Advantage.NONE
    if test.has_advantage:
        return Advantage.ADVANTAGE
    if test.has_disadvantage:
        return Advantage.DISADVANTAGE
    return Advantage.NONE


def die(seed: int, index: int, sides: int = DIE_SIDES) -> int:
    """One die face from a seed, specified rather than borrowed from `random`.

    Damage dice come through here too. A second dice implementation would drift from this
    one, and the drift would show up as a replay that reproduces the attack roll and not
    the damage — which is worse than no replay at all, because it looks like it worked.

    The hashed material is **fixed-width big-endian fields, not a formatted string.** A
    delimited string invites a collision the moment the delimiter is dropped or a field
    grows: `f"{seed}{index}"` renders seed 1 die 1 and seed 11 die 0 identically, so two
    unrelated rolls would share a die. Fixed widths make that unrepresentable rather than
    something a test has to keep catching.

    Rejection sampling rather than a modulo: `2**32` is not a multiple of most die sizes,
    so a plain modulo would make some faces likelier than others. The bias is small and
    the fix is free, and a loaded die inside an engine built for auditable outcomes is not
    a defect anyone would find by inspection.
    """
    if not 0 <= seed < 2**64:
        raise ValueError(f"a seed is a non-negative 64-bit integer, not {seed!r}")
    if sides < 2:
        raise ValueError(f"a die has at least two faces, not {sides!r}")

    limit = (2**_BITS // sides) * sides
    attempt = 0
    while True:
        material = (
            seed.to_bytes(8, "big")
            + index.to_bytes(2, "big")
            + sides.to_bytes(2, "big")
            + attempt.to_bytes(2, "big")
        )
        value = int.from_bytes(hashlib.sha256(material).digest()[:4], "big")
        if value < limit:
            return value % sides + 1
        attempt += 1


def roll(seed: int, *, count: int, sides: int, offset: int = 0) -> tuple[int, ...]:
    """Several dice of one size from one seed. `offset` keeps separate rolls apart."""
    if count < 0:
        raise ValueError("a roll has a non-negative number of dice")
    return tuple(die(seed, offset + n, sides) for n in range(count))
