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

## Replacing one die of a pair

`replace_die` is the seam the second point requires (#78). "Interactions with Rerolls"
(p. 8) governs it: with Advantage or Disadvantage, anything that lets you reroll or replace
the d20 replaces **one** die, not both, and the holder chooses which. The replacement is
*binding* — Heroic Inspiration (p. 183) and Halfling Luck (p. 86) both say the new roll must
be used — so this is a replacement, not a take-the-better-of-two.

Three properties make it a seam rather than a second roller:

* **The replacement comes from the same seed**, in an index space of its own
  (`REPLACEMENT_OFFSET`). Replay reproduces a rerolled result from the original seed plus
  the record of what was replaced. Drawing it from a fresh seed would reproduce the roll and
  not the reroll — a replay that fails in the quiet direction, which is worse than one that
  fails loudly.
* **The lineage is kept, not overwritten.** `dice` is the pair as it now stands, and
  `replacements` records each position, the die that was there, and what replaced it.
  `original_dice` walks that back to the pair as first rolled. R5 wants the arithmetic
  shown, and a reroll that erased what it replaced would assert its outcome instead.
* **The replacement may itself carry Advantage or Disadvantage.** Wish (p. 175) can force a
  reroll and force it to be rolled with either, so a seam returning a single substitute
  value cannot serve it. The same cancellation rule applies to the replacement as to the
  original roll, because it is the same rule.

The engine still rolls (R4): a caller names *which* die and *why*, never what it became.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
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

#: R31, and separate from the advantage citation above because it rests on different
#: sentences: the reroll rules govern `replace_die`, and a revision could reword one set
#: without touching the other. `scripts/verify_d20_rules.py` re-checks both.
REROLL_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Playing the Game" ("D20 Tests" -> "Interactions with Rerolls"), '
        "p. 8; Rules Glossary, Heroic Inspiration p. 183; Character Origins, Halfling "
        "Luck p. 86; Spell Descriptions, Wish p. 175"
    ),
    date="2026-08-23",
)

#: R31. The natural-20 rules and the two scores derived without a roll rest on their own
#: sentences, so they carry their own citation rather than borrowing the advantage one.
CRITICAL_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, "Playing the Game" ("D20 Tests" -> "Rolling 20 or 1"), p. 7; '
        "Rules Glossary, Critical Hit p. 179 and Passive Perception p. 186"
    ),
    date="2026-08-23",
)

#: The width of the hash slice a single die consumes.
_BITS: Final = 32

#: Where damage dice start in a seed's index space. One adjudication draws its d20 from
#: the low indices and its damage from here, so the two can never collide on a die.
DAMAGE_OFFSET: Final = 100

#: Where replacement dice start. The seed's index space is banded — d20 at 0-1, damage from
#: 100, replacements from 200 — so a rerolled die is drawn from the same seed as the roll it
#: replaces without ever landing on a die that seed has already produced.
#:
#: The bands are a **convention, not an enforced invariant**: `roll` takes an arbitrary
#: `count` and `offset`, so a large enough damage roll would cross into this band and
#: silently alias a replacement onto a damage die. No caller does, and nothing checks.
#: Disclosed rather than assumed away — see
#: https://github.com/eddiefiggie/srd-rules-engine/issues/82.
REPLACEMENT_OFFSET: Final = 200

#: Indices a single replacement consumes: two, because the replacement may itself be rolled
#: with Advantage or Disadvantage (Wish, p. 175).
_REPLACEMENT_STRIDE: Final = 2

#: `die` packs the index into two bytes, which bounds how many times one roll can be
#: rerolled. The bound is far past any real sequence and is checked rather than assumed.
_MAX_GENERATION: Final = (2**16 - REPLACEMENT_OFFSET) // (_REPLACEMENT_STRIDE * 2) - 1


class TestKind(StrEnum):
    """The three kinds. They differ in where the target came from, not how it resolves."""

    CHECK = "ability-check"
    SAVE = "saving-throw"
    ATTACK = "attack-roll"


class Critical(StrEnum):
    """What a natural 20 or 1 did to this roll.

    Only attack rolls have them. The document gives the rule under "Rolling 20 or 1" for
    an *attack roll* and nowhere extends it to ability checks or saving throws, so neither
    does this. A natural 20 on a check is a 20 and nothing more, which is the rule as
    written rather than the one most tables play.
    """

    NONE = "none"
    HIT = "critical-hit"
    MISS = "critical-miss"


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
class Replacement:
    """One die swapped out, and everything needed to see that it was not invented.

    `dice` is what the *replacement* rolled — two faces when the reroll itself carried
    Advantage or Disadvantage, one otherwise — so the new value reads back as arithmetic
    the same way the original roll does.
    """

    position: int
    original: int
    dice: tuple[int, ...]
    effective: Advantage
    value: int
    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError(
                "a replacement names what replaced the die. A reroll whose cause is not "
                "recorded is indistinguishable from a result the engine chose to like"
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
    #: A natural 20 or 1 on an attack roll, which settles the outcome on its own.
    critical: Critical = Critical.NONE
    #: Applied in order. Empty for a roll nothing has rerolled, which is almost all of them.
    replacements: tuple[Replacement, ...] = ()

    @property
    def modifier_total(self) -> int:
        return sum(modifier.value for modifier in self.modifiers)

    @property
    def original_dice(self) -> tuple[int, ...]:
        """The pair as first rolled, before any replacement."""
        dice = list(self.dice)
        for replacement in reversed(self.replacements):
            dice[replacement.position] = replacement.original
        return tuple(dice)

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

    used = _pick(dice, effective)

    total = used + sum(modifier.value for modifier in test.modifiers)
    critical = _critical(test.kind, used)
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
        succeeded=_succeeded(total, test.target, critical),
        critical=critical,
    )


def _effective_advantage(test: D20Test) -> Advantage:
    """Advantage and disadvantage cancel to a plain roll rather than accumulating."""
    return _cancel(test.has_advantage, test.has_disadvantage)


def _critical(kind: TestKind, used: int) -> Critical:
    """p. 7: a natural 20 on an attack roll hits and a natural 1 misses, either way
    "regardless of any modifiers or the target's AC".

    Read off the **used** die, not off the pair. With Disadvantage on an 18 and a 3 the
    roll is a 3, and a 20 that was never used is a 20 nobody rolled for this test.
    """
    if kind is not TestKind.ATTACK:
        return Critical.NONE
    if used == DIE_SIDES:
        return Critical.HIT
    if used == 1:
        return Critical.MISS
    return Critical.NONE


def _succeeded(total: int, target: int, critical: Critical) -> bool:
    """A natural 20 or 1 settles an attack before the arithmetic is consulted."""
    if critical is Critical.HIT:
        return True
    if critical is Critical.MISS:
        return False
    return total >= target


def passive_score(
    bonus: int, *, has_advantage: bool = False, has_disadvantage: bool = False
) -> int:
    """A score used without rolling — Passive Perception is the document's example.

    p. 186: it "equals 10 plus the creature's Wisdom (Perception) check bonus", and
    Advantage on such checks raises it by 5 while Disadvantage lowers it by 5.

    Advantage and Disadvantage cancel here by the same rule as everywhere else, so a
    creature holding both gets the unmodified score rather than +5 and -5 arriving in an
    order that happens to work out.
    """
    effective = _cancel(has_advantage, has_disadvantage)
    shift = {Advantage.ADVANTAGE: 5, Advantage.DISADVANTAGE: -5}.get(effective, 0)
    return 10 + bonus + shift


def _cancel(has_advantage: bool, has_disadvantage: bool) -> Advantage:
    """The cancellation rule itself, in one place.

    A forced reroll may be made with Advantage or Disadvantage (Wish, p. 175), and the rule
    that resolves those two flags is the same rule that resolves them on the original roll.
    Two copies of it would be two chances to answer the count-versus-presence question
    differently.
    """
    if has_advantage and has_disadvantage:
        return Advantage.NONE
    if has_advantage:
        return Advantage.ADVANTAGE
    if has_disadvantage:
        return Advantage.DISADVANTAGE
    return Advantage.NONE


def _pick(dice: tuple[int, ...], effective: Advantage) -> int:
    """Which of the dice counts, given the effective state."""
    if effective is Advantage.ADVANTAGE:
        return max(dice)
    if effective is Advantage.DISADVANTAGE:
        return min(dice)
    return dice[0]


def _replacement_index(generation: int, position: int) -> int:
    """The first index a replacement draws from.

    Banded so that no two replacements of the same roll can land on the same die: each
    generation gets its own block, each position its own pair inside that block, and the
    pair is what lets a forced reroll carry Advantage or Disadvantage.
    """
    block = generation * _REPLACEMENT_STRIDE * 2
    return REPLACEMENT_OFFSET + block + position * _REPLACEMENT_STRIDE


def replace_die(
    result: D20Result,
    *,
    position: int,
    source: str,
    with_advantage: bool = False,
    with_disadvantage: bool = False,
) -> D20Result:
    """Replace one die of a result and return the result that follows from it (R4, R5).

    The caller names *which* die and *why*. It never supplies what the die became — the
    engine rolls the replacement, from `result`'s own seed in the replacement index space,
    so replay reproduces the reroll rather than only the roll it replaced.

    The new roll is binding. Heroic Inspiration (p. 183) and Halfling Luck (p. 86) both say
    so in terms, so nothing here compares the replacement against what it replaced; the
    advantage rule then picks from the pair as it now stands, exactly as it did before.

    `with_advantage` / `with_disadvantage` roll the *replacement* with that state, which
    Wish (p. 175) can force. They cancel by the same rule as the original roll.
    """
    if not 0 <= position < len(result.dice):
        raise ValueError(
            f"a result with {len(result.dice)} dice has no die at position {position}. "
            f'"You choose which one" presumes the die exists'
        )

    generation = len(result.replacements) + 1
    if generation > _MAX_GENERATION:
        raise ValueError(f"a roll cannot be replaced more than {_MAX_GENERATION} times")

    effective = _cancel(with_advantage, with_disadvantage)
    count = 1 if effective is Advantage.NONE else 2
    base = _replacement_index(generation, position)
    rolled = tuple(die(result.seed, base + n) for n in range(count))
    value = _pick(rolled, effective)

    dice = list(result.dice)
    original = dice[position]
    dice[position] = value

    used = _pick(tuple(dice), result.effective)
    total = used + result.modifier_total
    critical = _critical(result.kind, used)
    return replace(
        result,
        dice=tuple(dice),
        used=used,
        total=total,
        succeeded=_succeeded(total, result.target, critical),
        critical=critical,
        replacements=(
            *result.replacements,
            Replacement(
                position=position,
                original=original,
                dice=rolled,
                effective=effective,
                value=value,
                source=source,
            ),
        ),
    )


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
    """Several dice of one size from one seed. `offset` keeps separate rolls apart.

    `offset` is not checked against the band it lands in, so a large enough `count` runs
    past the next band's start and aliases onto its dice. See #82.
    """
    if count < 0:
        raise ValueError("a roll has a non-negative number of dice")
    return tuple(die(seed, offset + n, sides) for n in range(count))
