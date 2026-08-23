"""Derive the effect-shape inventory (R17) from the official SRD v5.2.1 PDF.

This script is the reproducible half of `src/srd_rules_engine/data/effect_shapes.json`.
It is **not** run in CI, because CI has no copy of the document: the SRD is CC BY 4.0 but
it is not ours to redistribute, and this repository deliberately carries no SRD prose (see
`NOTICE.md`). Anyone holding the PDF can re-run it and diff the result.

Two halves, and the split is the point:

* **Enumeration is mechanical.** The Rules Glossary's entry headings are the only text set
  in GillSans-SemiBold at 12pt, so the 155 entries are read off the document rather than
  recalled. Their page numbers come from the same spans. Nothing here is typed from memory.
* **Classification is editorial**, lives in `KINDS` below, and is the reviewable layer. A
  glossary entry is not automatically an effect shape — "Alignment" defines a term, while
  "Prone" names a state a ruling applies. Every entry is placed either in the inventory or
  in `vocabulary`, with a reason. Nothing is dropped, because silent omission is the exact
  failure mode R17 exists to name.

Usage: python3 scripts/derive_effect_shapes.py /path/to/SRD_CC_v5.2.1.pdf
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Printed page N is PDF index N-1. The Rules Glossary runs pp. 176-191.
GLOSSARY_PAGES = range(175, 191)
HEADING_FONT = "GillSans-SemiBold"
HEADING_SIZE = 12.0

#: name -> (kind, implemented). `vocabulary` means "defined here, not an effect shape".
#: `implemented` is asserted against the engine by tests/test_effect_shape_inventory.py,
#: so an optimistic flag here fails the build rather than overstating coverage.
KINDS: dict[str, tuple[str, bool]] = {
    # --- tagged by the document itself -------------------------------------------------
    **{
        n: ("condition", False)
        for n in (
            "Blinded",
            "Charmed",
            "Deafened",
            "Exhaustion",
            "Frightened",
            "Grappled",
            "Incapacitated",
            "Invisible",
            "Paralyzed",
            "Petrified",
            "Poisoned",
            "Prone",
            "Restrained",
            "Stunned",
            "Unconscious",
        )
    },
    **{
        n: ("hazard", False)
        for n in ("Burning", "Dehydration", "Falling", "Malnutrition", "Suffocation")
    },
    **{
        n: ("targeting", False) for n in ("Cone", "Cube", "Cylinder", "Emanation", "Line", "Sphere")
    },
    **{n: ("attitude", False) for n in ("Friendly", "Hostile", "Indifferent")},
    "Attack": ("action", True),
    **{
        n: ("action", False)
        for n in (
            "Dash",
            "Disengage",
            "Dodge",
            "Help",
            "Hide",
            "Influence",
            "Magic",
            "Ready",
            "Search",
            "Study",
            "Utilize",
        )
    },
    # --- untagged entries ---------------------------------------------------------------
    "Ability Check": ("test", True),
    "Ability Score and Modifier": ("state", True),
    "Action": ("action", True),
    "Advantage": ("test-modifier", True),
    "Adventure": ("vocabulary", False),
    "Alignment": ("vocabulary", False),
    "Ally": ("vocabulary", False),
    "Area of Effect": ("targeting", False),
    "Armor Class": ("state", True),
    "Armor Training": ("state", False),
    "Attack Roll": ("test", True),
    "Attitude": ("state", False),
    "Attunement": ("state", False),
    "Blindsight": ("sense", False),
    "Bloodied": ("state", False),
    "Bonus Action": ("action", False),
    "Breaking Objects": ("effect", False),
    "Bright Light": ("environment", False),
    "Burrow Speed": ("movement", False),
    "Campaign": ("vocabulary", False),
    "Cantrip": ("spellcasting", False),
    "Carrying Capacity": ("state", False),
    "Challenge Rating": ("vocabulary", False),
    "Character Sheet": ("vocabulary", False),
    "Climbing": ("movement", False),
    "Climb Speed": ("movement", False),
    "Concentration": ("state", False),
    "Condition": ("effect", False),
    "Cover": ("targeting", False),
    "Crawling": ("movement", False),
    "Creature": ("vocabulary", False),
    "Creature Type": ("state", False),
    "Critical Hit": ("test", False),
    "Curses": ("effect", False),
    "D20 Test": ("test", True),
    "Damage": ("effect", True),
    "Damage Roll": ("test", True),
    "Damage Threshold": ("state", False),
    "Damage Types": ("effect", False),
    "Darkness": ("environment", False),
    "Darkvision": ("sense", False),
    "Dead": ("state", False),
    "Death Saving Throw": ("test", False),
    "Difficult Terrain": ("movement", False),
    "Difficulty Class": ("test", True),
    "Dim Light": ("environment", False),
    "Disadvantage": ("test-modifier", True),
    "Encounter": ("vocabulary", False),
    "Enemy": ("vocabulary", False),
    "Experience Points": ("vocabulary", False),
    "Expertise": ("state", False),
    "Flying": ("movement", False),
    "Fly Speed": ("movement", False),
    "Grappling": ("effect", False),
    "Hazard": ("effect", False),
    "Healing": ("effect", True),
    "Heavily Obscured": ("environment", False),
    "Heroic Inspiration": ("resource", False),
    "High Jump": ("movement", False),
    "Hit Point Dice": ("resource", False),
    "Hit Points": ("state", True),
    "Hover": ("movement", False),
    "Illusions": ("effect", False),
    "Immunity": ("effect", False),
    "Improvised Weapons": ("equipment", False),
    "Initiative": ("test", True),
    "Jumping": ("movement", False),
    "Knocking Out a Creature": ("effect", False),
    "Lightly Obscured": ("environment", False),
    "Long Jump": ("movement", False),
    "Long Rest": ("effect", False),
    "Magical Effect": ("vocabulary", False),
    "Monster": ("vocabulary", False),
    "Nonplayer Character": ("vocabulary", False),
    "Object": ("vocabulary", False),
    "Occupied Space": ("targeting", False),
    "Opportunity Attacks": ("action", False),
    "Passive Perception": ("test", False),
    "Per Day": ("resource", False),
    "Player Character": ("vocabulary", False),
    "Possession": ("effect", False),
    "Proficiency": ("state", False),
    "Reach": ("targeting", False),
    "Reaction": ("action", False),
    "Resistance": ("effect", False),
    "Ritual": ("spellcasting", False),
    "Round Down": ("vocabulary", False),
    "Save": ("test", True),
    "Saving Throw": ("test", True),
    "Shape-Shifting": ("effect", False),
    "Short Rest": ("effect", False),
    "Simultaneous Effects": ("convention", False),
    "Size": ("state", False),
    "Skill": ("state", False),
    "Speed": ("movement", False),
    "Spell": ("vocabulary", False),
    "Spell Attack": ("test", False),
    "Spellcasting Focus": ("equipment", False),
    "Stable": ("state", False),
    "Stat Block": ("vocabulary", False),
    "Surprise": ("effect", False),
    "Swimming": ("movement", False),
    "Swim Speed": ("movement", False),
    "Target": ("targeting", False),
    "Telepathy": ("sense", False),
    "Teleportation": ("effect", False),
    "Temporary Hit Points": ("effect", False),
    "Tremorsense": ("sense", False),
    "Truesight": ("sense", False),
    "Unarmed Strike": ("action", False),
    "Unoccupied Space": ("targeting", False),
    "Vulnerability": ("effect", False),
    "Weapon": ("vocabulary", False),
    "Weapon Attack": ("test", False),
}

#: Why a glossary entry is vocabulary rather than an effect shape. Keyed by kind so the
#: reason is stated once rather than copy-pasted 20 times and drifting.
VOCABULARY_REASON = (
    "Defines a term the rules use; it names no mechanical change the engine resolves."
)


def read_glossary(pdf: Path) -> list[dict[str, object]]:
    """Return the Rules Glossary headings, in document order, with printed page numbers."""
    import pymupdf  # imported here so the module stays importable without the dependency

    doc = pymupdf.open(pdf)
    entries: list[dict[str, object]] = []
    for pno in GLOSSARY_PAGES:
        current: dict[str, object] | None = None
        for block in doc[pno].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    if span["font"] != HEADING_FONT or round(span["size"], 1) != HEADING_SIZE:
                        continue
                    y = round(span["bbox"][1])
                    if current is not None and current["_y"] == y and current["page"] == pno + 1:
                        current["name"] = f"{current['name']}{text}"
                    else:
                        current = {"name": text, "page": pno + 1, "_y": y}
                        entries.append(current)
    for entry in entries:
        entry.pop("_y", None)
    return entries


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build(pdf: Path) -> dict[str, object]:
    headings = read_glossary(pdf)
    shapes: list[dict[str, object]] = []
    vocabulary: list[dict[str, object]] = []
    unclassified: list[str] = []

    for entry in headings:
        raw = str(entry["name"])
        tag_match = re.search(r"\[([^\]]+)\]", raw)
        name = re.sub(r"\s*\[[^\]]+\]\s*", "", raw).strip()
        if name not in KINDS:
            unclassified.append(name)
            continue
        kind, implemented = KINDS[name]
        record = {
            "id": slug(name),
            "name": name,
            "tag": tag_match.group(1) if tag_match else None,
            "reference": f"Rules Glossary, p. {entry['page']}",
        }
        if kind == "vocabulary":
            vocabulary.append({**record, "reason": VOCABULARY_REASON})
        else:
            shapes.append({**record, "kind": kind, "implemented": implemented})

    if unclassified:
        raise SystemExit(
            "Glossary entries with no entry in KINDS — classify them rather than "
            f"letting them vanish: {unclassified}"
        )

    return {
        "schema_version": 1,
        "compat": 1,
        "source": {
            "document": "System Reference Document 5.2.1",
            "revision": "5.2.1",
            "published": "2025-05-01",
            "section": "Rules Glossary (pp. 176-191)",
        },
        "coverage_scope": (
            "Rules Glossary only. The sweeps of Spell Descriptions, Monsters, and Magic "
            "Items are tracked separately; until they land this inventory understates "
            "what full coverage requires."
        ),
        "shapes": shapes,
        "vocabulary": vocabulary,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = Path(__file__).resolve().parents[1] / "src/srd_rules_engine/data/effect_shapes.json"
    data = build(Path(sys.argv[1]))
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    total = len(data["shapes"])
    done = sum(1 for s in data["shapes"] if s["implemented"])
    print(f"{out}: {total} shapes ({done} implemented), {len(data['vocabulary'])} vocabulary")


if __name__ == "__main__":
    main()
