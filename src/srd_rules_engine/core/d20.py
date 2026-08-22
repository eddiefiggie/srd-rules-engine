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

## A disclosed limit

The advantage rules implemented here — two dice taking the higher, disadvantage taking the
lower, and the two cancelling to a single roll — are specified by the M1 plan and are
**not yet verified against SRD v5.2.1**, which is gated behind
[#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3). They are load-bearing on
every roll the engine makes, so the gap is filed rather than assumed away. See
[#52](https://github.com/eddiefiggie/srd-rules-engine/issues/52).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

DIE_SIDES: Final = 20

#: Rejection threshold for an unbiased mapping of 32 random bits onto the die's faces.
_LIMIT: Final = (2**32 // DIE_SIDES) * DIE_SIDES


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
    dice = tuple(_die(seed, index) for index in range(count))

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


def _die(seed: int, index: int) -> int:
    """One die face from a seed, specified rather than borrowed from `random`.

    The hashed material is **fixed-width big-endian fields, not a formatted string.** A
    delimited string invites a collision the moment the delimiter is dropped or a field
    grows: `f"{seed}{index}"` renders seed 1 die 1 and seed 11 die 0 identically, so two
    unrelated rolls would share a die. Fixed widths make that unrepresentable rather than
    something a test has to keep catching.

    Rejection sampling rather than a modulo: `2**32` is not a multiple of 20, so a plain
    modulo would make four faces very slightly likelier than the other sixteen. The bias
    is small and the fix is free, and a loaded die inside an engine built for auditable
    outcomes is not a defect anyone would find by inspection.
    """
    if not 0 <= seed < 2**64:
        raise ValueError(f"a seed is a non-negative 64-bit integer, not {seed!r}")

    attempt = 0
    while True:
        material = seed.to_bytes(8, "big") + index.to_bytes(2, "big") + attempt.to_bytes(2, "big")
        value = int.from_bytes(hashlib.sha256(material).digest()[:4], "big")
        if value < _LIMIT:
            return value % DIE_SIDES + 1
        attempt += 1
