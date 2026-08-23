"""Verify the d20 rules this engine implements against the official SRD v5.2.1 PDF.

This is the reproducible half of `core.d20.ADVANTAGE_VERIFICATION`. Like
`derive_effect_shapes.py` it is **not** run in CI, because CI has no copy of the document:
the SRD is CC BY 4.0 but it is not ours to redistribute, and this repository deliberately
carries no SRD prose (see `NOTICE.md`). Anyone holding the PDF can re-run it.

A `Verification` block carries a date, and `AGENTS.md` is emphatic that a dated claim
cannot notice its own staleness. This script is what makes the date re-checkable rather
than merely asserted: every clause the implementation relies on is stated here as a
pattern that must match the cited printed page, and the script exits non-zero if any of
them stops matching. If a future SRD revision reworded the cancellation rule, this goes
red rather than the engine quietly resolving rolls against a sentence nobody re-read.

Patterns are matched against whitespace-normalised page text, because the document is set
in two columns with hyphenated line breaks — `Advantage and Dis-\\nadvantage` is one phrase
to a reader and three tokens to a naive search.

Usage: python3 scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: Printed page N is PDF index N-1.
PAGE_OFFSET = 1

#: Each clause the implementation depends on, as (printed page, what it settles, pattern).
#: The pattern must match that page's normalised text or the script fails.
CLAUSES: tuple[tuple[int, str, str], ...] = (
    (
        7,
        "advantage and disadvantage are a property of a D20 Test",
        r"Sometimes a D20 Test is modified by Advantage or Disadvantage",
    ),
    (
        8,
        "two dice, higher for advantage",
        r"roll a second d20 when you make the roll\.\s*Use the higher of the two rolls if you "
        r"have Advantage",
    ),
    (
        8,
        "two dice, lower for disadvantage",
        r"use the lower roll if you have Disadvantage",
    ),
    (
        8,
        "the document's own worked example: disadvantage on 18 and 3 uses the 3",
        r"if you have Disadvantage and roll an 18 and a 3, use the 3",
    ),
    (
        8,
        "sources on the same side do not accumulate: still two dice",
        r"If multiple situations affect a roll and they all grant Advantage on it, you still "
        r"roll only two d20s",
    ),
    (
        8,
        "opposing sources cancel to a single plain die",
        r"If circumstances cause a roll to have both Advantage and Disadvantage, the roll has "
        r"neither of them, and you roll one d20",
    ),
    (
        8,
        "cancellation is presence-based, not count-based — the question #52 asked",
        r"This is true even if multiple circumstances impose Disadvantage and only one grants "
        r"Advantage or vice versa",
    ),
    (
        8,
        "both dice stay individually addressable, so neither may be discarded",
        r"you can reroll or replace only one die, not both\.\s*You choose which one",
    ),
    (
        7,
        "a natural 20 on an attack roll hits regardless of modifiers or AC",
        r"If you roll a 20 on the d20 \(called a .natural 20.\) for an attack roll, the "
        r"attack hits regardless of any modifiers or the target.s AC",
    ),
    (
        7,
        "a natural 1 on an attack roll misses regardless of modifiers or AC",
        r"If you roll a 1 on the d20 \(a .natural 1.\) for an attack roll, the attack "
        r"misses regardless of any modifiers or the target.s AC",
    ),
    (
        179,
        "a Critical Hit doubles the damage dice and not the modifiers",
        r"Roll all of the attack.s damage dice twice and add them together\.\s*Then add "
        r"any relevant modifiers",
    ),
    (
        186,
        "Passive Perception is 10 plus the check bonus",
        r"Passive Perception equals 10 plus the creature.s Wisdom \(Perception\) check bonus",
    ),
    (
        186,
        "advantage and disadvantage shift a passive score by 5 rather than rolling",
        r"If the creature has Advantage on such checks, increase the score by 5\.\s*If the "
        r"creature has Disadvantage on them, decrease the score by 5",
    ),
    (
        8,
        "the reroll rule has a subsection of its own, which is what makes it a rule",
        r"Interactions with Rerolls",
    ),
    (
        8,
        "the document's worked reroll example names Heroic Inspiration",
        r"expend your Heroic Inspiration to reroll one of those dice, not both of them",
    ),
    (
        183,
        "Heroic Inspiration replaces one die and the new roll is binding",
        r"expend it to reroll any die immediately after rolling it, and you must use the "
        r"new roll",
    ),
    (
        86,
        "Halfling Luck replaces a natural 1, and is likewise binding",
        r"When you roll a 1 on the d20 of a D20 Test, you can reroll the die, and you must "
        r"use the new roll",
    ),
    (
        175,
        "Wish forces a reroll of a die already rolled",
        r"forcing a reroll of any die roll made within the last round",
    ),
    (
        175,
        "a forced reroll may itself be made with Advantage or Disadvantage — the clause "
        "that decides replace_die returns dice rather than one face",
        r"You can force the reroll to be made with Advantage or Disadvantage",
    ),
    (
        17,
        "a death save is DC 10 and tied to no ability score",
        r"this one isn.t tied to an ability score",
    ),
    (
        17,
        "10 or higher succeeds",
        r"Roll 1d20\.\s*If the roll is 10 or higher, you succeed\.\s*Otherwise, you fail",
    ),
    (
        17,
        "three of a kind resolves it, and they need not be consecutive",
        r"On your third success, you become Stable.{0,120}On your third failure, you die\."
        r"\s*The successes and failures don.t need to be consecutive",
    ),
    (
        17,
        "the counts reset on regaining any hit points or becoming Stable",
        r"reset to zero when you regain any Hit Points or become Stable",
    ),
    (
        17,
        "a monster dies the instant it drops to 0, rather than making saves",
        r"A monster dies the instant it drops to 0 Hit Points",
    ),
    (
        17,
        "massive damage kills on the REMAINDER, not on the whole blow",
        r"When damage reduces a character to 0 Hit Points and damage remains, the character "
        r"dies if the remainder equals or exceeds their Hit Point maximum",
    ),
    (
        18,
        "a natural 1 costs two failures and a natural 20 restores a hit point",
        r"When you roll a 1 on the d20 for a Death Saving Throw, you suffer two failures\."
        r"\s*If you roll a 20 on the d20, you regain 1 Hit Point",
    ),
    (
        18,
        "damage at 0 hit points is a failure, and two from a Critical Hit",
        r"If you take any damage while you have 0 Hit Points, you suffer a Death Saving "
        r"Throw failure\.\s*If the damage is from a Critical Hit, you suffer two failures",
    ),
    (
        18,
        "a Stable creature makes no saves, and damage ends that",
        r"A Stable creature doesn.t make Death Saving Throws.{0,200}If the creature takes "
        r"damage, it stops being Stable",
    ),
    (
        213,
        "a weapon bonus applies to attack rolls AND damage rolls, not one of them",
        r"You gain a \+1 bonus to attack rolls and damage rolls made with this magic weapon",
    ),
    (
        32,
        "a die may be rolled after a failed test and added to the d20",
        r"the creature can roll the Bardic Inspiration die and add the number rolled to "
        r"the d20, potentially turning the failure into a success",
    ),
    (
        88,
        "the same shape applies as a bonus OR a penalty",
        r"you can roll 2d4 and apply the total rolled as a bonus or penalty to the d20 roll",
    ),
    (
        88,
        "a missed attack may be overridden to a hit",
        r"When you miss with an attack roll, you can hit instead",
    ),
    (
        258,
        "and a failed save to a success — the same shape, a different test kind",
        r"If the aboleth fails a saving throw, it can choose to suc-?\s*ceed instead",
    ),
    (
        17,
        "damage modifiers apply in a fixed order: adjustments, Resistance, Vulnerability",
        r"adjustments such as bonuses, penalties, or multipliers are applied first; "
        r"Resistance is applied second; and Vulnerability is applied third",
    ),
    (
        17,
        "the document's worked example rounds AT the halving, and lands on 22",
        r"the damage is first reduced by 5 \(to 23\), then halved for the creature.s "
        r"Resistance \(and rounded down to 11\), then doubled for its Vulnerability \(to 22\)",
    ),
    (
        17,
        "Resistance and Vulnerability do not stack with themselves",
        r"Multiple instances of Resistance or Vulnerability that affect the same damage "
        r"type count as only one instance",
    ),
    (
        187,
        "Resistance halves and rounds down, once per instance of damage",
        r"damage of that type is halved against you \(round down\)\.\s*Resistance is "
        r"applied only once to an instance of damage",
    ),
    (
        191,
        "Vulnerability doubles, once per instance of damage",
        r"damage of that type is doubled against you\.\s*Vulnerability is applied only "
        r"once to an instance of damage",
    ),
    (
        183,
        "Immunity is not a reduction",
        r"If you have Immunity to a damage type or a condition, it doesn.t affect you in any way",
    ),
    (
        180,
        "damage types carry no rules of their own; other rules key off them",
        r"Damage types have no rules of their own, but other rules, such as Resistance, "
        r"rely on the types",
    ),
    (
        89,
        "Finesse offers Strength or Dexterity, and the same modifier for both rolls",
        r"use your choice of your Strength or Dexterity modifier for the attack and damage "
        r"rolls\.\s*You must use the same modifier for both rolls",
    ),
    (
        89,
        "Heavy names a SCORE of 13, and a different ability for melee and ranged",
        r"Disadvantage on attack rolls with a Heavy weapon if it.s a Melee weapon and your "
        r"Strength score isn.t at least 13 or if it.s a Ranged weapon and your Dexterity "
        r"score isn.t at least 13",
    ),
    (
        90,
        "Versatile applies only to a two-handed melee attack",
        r"The weapon deals that damage when used with two hands to make a melee attack",
    ),
    (
        90,
        "Graze deals the ability modifier on a miss, and nothing else may raise it",
        r"If your attack roll with this weapon misses a creature, you can deal damage to "
        r"that creature equal to the ability modifier you used to make the attack roll",
    ),
    (
        90,
        "and Graze damage is the weapon's own type",
        r"This damage is the same type dealt by the weapon, and the damage can be increased "
        r"only by increasing the ability modifier",
    ),
    (
        176,
        "the Rules Glossary states the same cancellation rule",
        r"Advantage and Dis-?\s*advantage on the same roll cancel each other",
    ),
    (
        181,
        "the glossary's Disadvantage entry agrees with its Advantage entry",
        r"roll two d20s and use the lower roll\. A roll can.t be affected by more than one "
        r"Disadvantage",
    ),
)


def normalise(text: str) -> str:
    """Rejoin hyphenated line breaks, then flatten whitespace.

    The document hyphenates across column breaks, so the operative sentence of the
    cancellation rule is physically `Advan-\\ntage and Disadvantage`. Matching the raw text
    would mean encoding this edition's line breaks into the patterns, which would go red on
    a reflow that changed nothing a reader would notice.
    """
    return re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "", text))


def page_text(pdf: Path) -> dict[int, str]:
    """Normalised text per printed page number."""
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - developer-machine tooling
        raise SystemExit(
            "pymupdf is required to verify against the PDF: pip install pymupdf"
        ) from None

    with pymupdf.open(pdf) as doc:
        return {
            index + PAGE_OFFSET: normalise(doc[index].get_text()) for index in range(doc.page_count)
        }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(f"usage: {argv[0]} /path/to/SRD_CC_v5.2.1.pdf")

    pdf = Path(argv[1])
    if not pdf.is_file():
        raise SystemExit(f"no such file: {pdf}")

    pages = page_text(pdf)
    failures: list[str] = []

    for printed, settles, pattern in CLAUSES:
        text = pages.get(printed)
        if text is None:
            failures.append(f"p. {printed}: no such page in this document")
            continue
        if not re.search(pattern, text):
            failures.append(f"p. {printed}: no match for {settles!r}\n    pattern: {pattern}")
        else:
            print(f"  ok  p. {printed:>3}  {settles}")

    if failures:
        raise SystemExit(
            "\nthe cited text no longer matches the document:\n\n"
            + "\n".join(failures)
            + "\n\ncore.d20 and core.death rest on these sentences. Re-read the "
            "document before touching the implementation to make this pass."
        )

    print(f"\nall {len(CLAUSES)} clauses verified against {pdf.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
