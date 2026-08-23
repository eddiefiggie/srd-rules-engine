"""Verify the d20 advantage rules in `core.d20` against the official SRD v5.2.1 PDF.

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
            + "\n\ncore.d20's advantage semantics rest on these sentences. Re-read the "
            "document before touching the implementation to make this pass."
        )

    print(f"\nall {len(CLAUSES)} clauses verified against {pdf.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
