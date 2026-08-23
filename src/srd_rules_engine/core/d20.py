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

#: R31. The ways a resolved d20 test can still move: a flat bonus on both rolls, dice
#: applied afterwards in either direction, and a failure overridden to a success.
MODIFIER_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Magic Items, Berserker Axe p. 213; Classes, Bardic Inspiration "
        "p. 32; Feats, Boon of Fate p. 88 and Boon of Combat Prowess p. 88; Monsters, "
        "Aboleth p. 258"
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

#: How many times one roll may be replaced. Bounded so the replacement band *ends*, which
#: is what lets another band start above it — an unbounded band leaves no room for a
#: neighbour and is the shape of the problem #82 describes. Sixteen is far past any real
#: sequence: the document's rerolls cost a resource each.
_MAX_GENERATION: Final = 16

#: Where dice applied to an already-resolved roll start. Bardic Inspiration (p. 32) and
#: Boon of Fate (p. 88) both roll dice *after* the d20 and apply the total to it.
ADJUSTMENT_OFFSET: Final = 300

#: The most dice one adjustment may roll, and so the width of a generation's block.
MAX_ADJUSTMENT_DICE: Final = 8
_MAX_ADJUSTMENTS: Final = 16

# The seed's index bands, in one place rather than as constants a reader must compare:
#
#     0   - 1     the d20 itself, one die or two
#     100 - 199   damage (DAMAGE_OFFSET)
#     200 - 267   replacements, 16 generations of 4 (REPLACEMENT_OFFSET)
#     300 - 427   adjustments, 16 generations of 8 (ADJUSTMENT_OFFSET)
#
# Nothing enforces that a caller stays inside its band — `roll` still takes an arbitrary
# `count` and `offset`, which is #82. Bounding the two upper bands is what makes them
# finite enough to sit next to each other at all.


class TestKind(StrEnum):
    """The three kinds. They differ in where the target came from, not how it resolves."""

    CHECK = "ability-check"
    SAVE = "saving-throw"
    ATTACK = "attack-roll"


@dataclass(frozen=True)
class Adjustment:
    """Dice rolled after the d20 and applied to it.

    Bardic Inspiration (p. 32) adds; Boon of Fate (p. 88) "apply the total rolled as a
    bonus **or penalty**", which is why `penalty` exists rather than the caller passing a
    negative count. The dice are kept, because R5 wants the arithmetic shown.
    """

    dice: tuple[int, ...]
    value: int
    penalty: bool
    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("an adjustment names its source, or the total cannot be read")

    @property
    def applied(self) -> int:
        """Signed, as it lands on the total."""
        return -self.value if self.penalty else self.value


@dataclass(frozen=True)
class Override:
    """A failed test made to succeed, without touching a die.

    Peerless Aim (p. 88) — "When you miss with an attack roll, you can hit instead" — and
    Legendary Resistance (p. 258) — "If the aboleth fails a saving throw, it can choose to
    succeed instead". One shape since decision 0013; the test kind is the only difference.
    """

    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("an override names what granted it; otherwise it is an assertion")


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
    #: Dice applied to the roll after it resolved, in order.
    adjustments: tuple[Adjustment, ...] = ()
    #: Set when a failed test was overridden to a success.
    override: Override | None = None

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
        parts += [f"{a.applied:+d} ({a.source})" for a in self.adjustments]
        outcome = "meets or beats" if self.succeeded else "falls short of"
        line = f"{' '.join(parts)} = {self.total}, {outcome} {self.target} ({self.target_basis})"
        if self.override is not None:
            line += f" — overridden to a success by {self.override.source}"
        elif self.critical is Critical.HIT:
            line += " — natural 20, hits regardless"
        elif self.critical is Critical.MISS:
            line += " — natural 1, misses regardless"
        return line


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
        succeeded=_outcome(total, test.target, critical, None),
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


def _outcome(total: int, target: int, critical: Critical, override: Override | None) -> bool:
    """Whether the test succeeded, with the things that outrank arithmetic applied first.

    Order matters and is the document's rather than convenient. An override is a decision
    to succeed and nothing later un-makes it. A natural 20 or 1 then settles an attack
    "regardless of any modifiers" (p. 7) — so a die applied to a natural 1 raises the
    total and the attack still misses, which is the clause doing real work rather than
    decorating the docstring.
    """
    if override is not None:
        return True
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


def adjust_roll(
    result: D20Result,
    *,
    count: int,
    sides: int,
    source: str,
    penalty: bool = False,
) -> D20Result:
    """Roll dice and apply their total to a d20 test that has already resolved (R4, R5).

    Bardic Inspiration (p. 32): when a creature "fails a D20 Test, the creature can roll
    the Bardic Inspiration die and add the number rolled to the d20, potentially turning
    the failure into a success". Boon of Fate (p. 88) is the same shape in either
    direction — "apply the total rolled as a bonus or penalty to the d20 roll" — which is
    what `penalty` is for.

    Applied *after* the roll on purpose. Both features let the holder see the result before
    spending the resource, so folding these into `D20Test.modifiers` would resolve them a
    step too early and lose the choice the rules give.

    A natural 1 on an attack still misses. p. 7 says so "regardless of any modifiers", and
    a die applied afterwards is a modifier — so the total rises and the attack does not
    land. That is the rule, not an oversight.
    """
    if not source:
        raise ValueError("an adjustment names its source, or the total cannot be read")
    if not 1 <= count <= MAX_ADJUSTMENT_DICE:
        raise ValueError(
            f"an adjustment rolls between 1 and {MAX_ADJUSTMENT_DICE} dice, not {count}"
        )

    generation = len(result.adjustments) + 1
    if generation > _MAX_ADJUSTMENTS:
        raise ValueError(f"a roll cannot be adjusted more than {_MAX_ADJUSTMENTS} times")

    base = ADJUSTMENT_OFFSET + (generation - 1) * MAX_ADJUSTMENT_DICE
    rolled = tuple(die(result.seed, base + n, sides) for n in range(count))
    adjustment = Adjustment(dice=rolled, value=sum(rolled), penalty=penalty, source=source)

    total = result.total + adjustment.applied
    return replace(
        result,
        total=total,
        succeeded=_outcome(total, result.target, result.critical, result.override),
        adjustments=(*result.adjustments, adjustment),
    )


def override_to_success(result: D20Result, *, source: str) -> D20Result:
    """Make a failed test succeed, without touching a die (R5).

    One shape since decision 0013, because Peerless Aim and Legendary Resistance are the
    same sentence with the test kind changed: a failed d20 test overridden to a success at
    the holder's choice.

    Refuses a test that already succeeded. Both features are written as a response to
    failing — "When you miss", "If the aboleth fails a saving throw" — so overriding a
    success is not a no-op, it is a record of something that never happened.
    """
    if result.succeeded:
        raise ValueError(
            "only a failed test is overridden to a success. Recording one against a test "
            "that already succeeded would put a use of the feature in the ledger that the "
            "rules never called for"
        )
    return replace(result, succeeded=True, override=Override(source=source))


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
        succeeded=_outcome(total, result.target, critical, result.override),
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
