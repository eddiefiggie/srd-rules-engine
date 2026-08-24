"""Derive monster statistics from the official SRD v5.2.1 PDF (#21, R32).

The reproducible half of `src/srd_rules_engine/data/bestiary.json`. Like
`derive_effect_shapes.py` it is **not** run in CI, because CI has no copy of the document:
the SRD is CC BY 4.0 but it is not ours to redistribute, and this repository deliberately
carries no SRD prose (see `NOTICE.md`). Anyone holding the PDF can re-run it and diff.

Two halves, and the split is the same one the effect-shape sweep uses:

* **Extraction is mechanical.** A stat block's header line is a fixed grammar — `AC 17`,
  `HP 150 (20d10 + 40)`, `Speed 10 ft., Swim 40 ft.`, six ability scores, `CR 10 (... PB +4)`.
  Every field is read off the page with a pattern that must match, and a monster whose block
  does not parse is **excluded with a reason** rather than guessed at.
* **Admission is editorial**, lives in `WANTED` below, and is the reviewable layer. Nothing
  is swept in wholesale: each monster is named deliberately, so the set that ships is a
  decision somebody made rather than whatever the parser happened to survive.

**Statistics only.** Traits and actions are rules prose; `NOTICE.md` commits this repository
to not redistributing it, and what a trait *does* belongs in the effect vocabulary rather
than in a text field. `traits_modelled` is therefore `false` on every entry.

Usage: python3 scripts/derive_bestiary.py /path/to/SRD_CC_v5.2.1.pdf
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Final

#: Printed page N is PDF index N-1. Stat blocks run from the Monsters section onward.
PAGE_OFFSET: Final = 1
MONSTER_PAGES: Final = range(256, 364)

#: The monsters admitted, and the printed page each is expected on. Naming the page is what
#: turns "the parser found something called Bandit" into "the Bandit on p. 260 was read".
WANTED: Final[tuple[tuple[str, int], ...]] = (
    ("Aboleth", 258),
    ("Bandit", 261),
    ("Commoner", 275),
    ("Guard", 296),
    ("Wolf", 347),
    ("Giant Rat", 353),
)

#: Speed names the document prints, mapped to the engine's fields.
SPEED_KINDS: Final = {"climb": "climb", "fly": "fly", "swim": "swim", "burrow": "burrow"}

VERIFIED_ON: Final = "2026-08-23"


def normalise(text: str) -> str:
    """Rejoin hyphenated line breaks, then flatten whitespace — two columns, one string."""
    return re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "", text))


def page_text(pdf: Path) -> dict[int, str]:
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - developer-machine tooling
        raise SystemExit("pymupdf is required: pip install pymupdf") from None

    with pymupdf.open(pdf) as doc:
        return {
            index + PAGE_OFFSET: normalise(doc[index].get_text()) for index in range(doc.page_count)
        }


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def read_block(text: str, name: str) -> str | None:
    """The stretch of page text beginning at this monster's header, or None.

    Bounded rather than open-ended: a stat block's statistics all sit before its Traits, so
    reading past them would start absorbing the prose this project does not carry.
    """
    header = re.escape(name) + r"\s+(?:Tiny|Small|Medium|Large|Huge|Gargantuan)\b(.{0,700})"
    match = re.search(header, text)
    return match.group(1) if match else None


def parse(block: str) -> dict[str, Any] | str:
    """Every statistic, or a string saying which one could not be read."""
    armour = re.search(r"\bAC (\d+)", block)
    if not armour:
        return "no AC in the block"

    hit_points = re.search(r"\bHP (\d+) \(([^)]+)\)", block)
    if not hit_points:
        return "no HP with its hit dice"

    # The ability table follows the Speed line and always begins "MOD SAVE", so that is
    # the terminator rather than a guess about which words can appear in a speed.
    speed = re.search(r"\bSpeed (.*?)\s*MOD\b", block)
    if not speed:
        return "no Speed line"

    scores: dict[str, int] = {}
    for ability in ("Str", "Dex", "Con", "Int", "Wis", "Cha"):
        found = re.search(rf"\b{ability} (\d+)\b", block)
        if not found:
            return f"no {ability} score"
        scores[ability.lower()] = int(found.group(1))

    challenge = re.search(r"\bCR ([0-9/]+)\s*\([^)]*PB \+(\d+)\)", block)
    if not challenge:
        return "no CR with its proficiency bonus"

    return {
        "armour_class": int(armour.group(1)),
        "hit_points": int(hit_points.group(1)),
        "hit_dice": hit_points.group(2).strip(),
        "speeds": parse_speeds(speed.group(1)),
        "abilities": scores,
        "challenge_rating": challenge.group(1),
        "proficiency_bonus": int(challenge.group(2)),
    }


def parse_speeds(line: str) -> dict[str, int]:
    """`10 ft., Swim 40 ft.` — a walking speed and any named special speeds."""
    speeds: dict[str, int] = {}
    walk = re.match(r"\s*(\d+) ft\.", line)
    speeds["walk"] = int(walk.group(1)) if walk else 0
    for label, field in SPEED_KINDS.items():
        found = re.search(rf"{label} (\d+) ft\.", line, re.IGNORECASE)
        if found:
            speeds[field] = int(found.group(1))
    return speeds


def build(pdf: Path) -> dict[str, Any]:
    pages = page_text(pdf)
    entries: list[dict[str, Any]] = []
    failures: list[str] = []

    for name, printed in WANTED:
        text = pages.get(printed)
        if text is None:
            failures.append(f"{name}: no printed page {printed} in this document")
            continue

        block = read_block(text, name)
        if block is None:
            failures.append(f"{name}: no stat block header on p. {printed}")
            continue

        parsed = parse(block)
        if isinstance(parsed, str):
            # R32: an entry that cannot be read is excluded *with its reason*, never dropped.
            entries.append(
                {
                    "id": slug(name),
                    "name": name,
                    "verification": {
                        "state": "excluded",
                        "reference": f"Monsters, p. {printed}",
                        "date": VERIFIED_ON,
                        "reason": f"the stat block did not parse: {parsed}",
                        "method": "asserted",
                    },
                }
            )
            failures.append(f"{name}: {parsed}")
            continue

        entries.append(
            {
                "id": slug(name),
                "name": name,
                **parsed,
                "traits_modelled": False,
                "verification": {
                    "state": "verified",
                    "reference": f"SRD v5.2.1, Monsters, p. {printed} ({name})",
                    "date": VERIFIED_ON,
                    "reason": None,
                    "method": "asserted",
                },
            }
        )

    return {
        "schema_version": 1,
        "compat": 1,
        "source": {
            "document": "System Reference Document 5.2.1",
            "revision": "5.2.1",
            "published": "2025-05-01",
            "section": "Monsters",
        },
        "scope": (
            "Statistics only. A stat block's traits and actions are rules prose, which "
            "NOTICE.md commits this repository to not redistributing, and what a trait does "
            "belongs in the effect vocabulary rather than a text field. `traits_modelled` is "
            "false on every entry, so no consumer can mistake a statistics-only monster for "
            "a fully modelled one. The set is named in `WANTED` rather than swept: what "
            "ships is a decision, not whatever the parser survived."
        ),
        "entries": entries,
        "failures": failures,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = Path(__file__).resolve().parents[1] / "src/srd_rules_engine/data/bestiary.json"
    data = build(Path(sys.argv[1]))
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    verified = sum(1 for e in data["entries"] if e["verification"]["state"] == "verified")
    print(f"{out}: {verified} verified of {len(data['entries'])} entries")
    for failure in data["failures"]:
        print(f"  excluded — {failure}")


if __name__ == "__main__":
    main()
