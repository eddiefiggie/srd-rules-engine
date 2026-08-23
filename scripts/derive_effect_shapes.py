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


# Printed pages 107-175 are Spell Descriptions.
SPELL_PAGES = range(106, 175)
#: Lines that are the running header rather than content. Filtering these by position
#: rather than by content silently dropped 25 spell headings sitting at y=38.9.
RUNNING_HEADER = re.compile(r"^\s*(System Reference Document 5\.2\.1|\d{1,3})\s*$")

#: Effect shapes the Rules Glossary never names, found by sweeping Spell Descriptions.
#:
#: The Glossary could be enumerated by typography — its entry headings are the only 12pt
#: GillSans-SemiBold in the document. Spell *effects* have no such handle: they are body
#: text, so which shapes exist here is editorial in a way the Glossary pass was not.
#:
#: What keeps that honest is `verify`: every row names a spell, its printed page, and a
#: pattern that must match that spell's text in the PDF. `sweep_spells` asserts all three,
#: so a row invented at a desk, a mis-transcribed page, or a shape the document stopped
#: supporting fails the derivation instead of shipping. The exemplar is the citation, not
#: the whole population — several of these appear in dozens of spells.
SPELL_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar spell, printed page, pattern that must match its text
    (
        "half-damage-on-save",
        "Half Damage on a Successful Save",
        "effect",
        "Blade Barrier",
        113,
        r"half as much damage on a successful",
    ),
    (
        "ongoing-damage",
        "Damage on a Recurring Schedule",
        "effect",
        "Acid Arrow",
        107,
        r"damage at the end of its next turn",
    ),
    (
        "forced-movement",
        "Forced Movement",
        "effect",
        "Thunderwave",
        169,
        r"pushed 10 feet away from you",
    ),
    (
        "summon-creature",
        "Summoned Creature",
        "effect",
        "Conjure Animals",
        117,
        r"appear as a Large",
    ),
    (
        "create-object",
        "Created Object or Material",
        "effect",
        "Creation",
        121,
        r"You pull wisps of shadow material",
    ),
    (
        "control-creature",
        "Commanded Creature",
        "effect",
        "Animate Objects",
        108,
        r"Objects animate at your command",
    ),
    (
        "end-magical-effect",
        "Ending or Suppressing a Magical Effect",
        "effect",
        "Dispel Magic",
        124,
        r"spell of level 3 or lower on the target ends",
    ),
    (
        "planar-travel",
        "Planar Travel",
        "effect",
        "Plane Shift",
        153,
        r"attuned to a plane of existence",
    ),
    (
        "resurrection",
        "Returning a Dead Creature to Life",
        "effect",
        "Raise Dead",
        157,
        r"you revive a dead creature",
    ),
    (
        "damage-transfer",
        "Damage Transferred to Another Creature",
        "effect",
        "Warding Bond",
        173,
        r"you take the same amount of damage",
    ),
    ("reroll", "Forced Reroll", "test-modifier", "Wish", 175, r"forcing a reroll of any die roll"),
    (
        "information-granted",
        "Information Granted to the Caster",
        "effect",
        "Commune with Nature",
        116,
        r"you learn those facts",
    ),
)


def read_spells(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Spell Descriptions entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    spells: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in SPELL_PAGES:
        page = doc[pno]
        mid = page.rect.width / 2
        columns: dict[int, list[tuple[float, str, bool]]] = {0: [], 1: []}
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if RUNNING_HEADER.match(text):
                    continue
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    spells[text.strip()] = current
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in spells.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return spells


def sweep_spells(pdf: Path) -> list[dict[str, object]]:
    """Verify every SPELL_SHAPES row against the document, then return the shapes."""
    spells = read_spells(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, spell, page, pattern in SPELL_SHAPES:
        entry = spells.get(spell)
        if entry is None:
            raise SystemExit(f"{shape_id}: cites {spell!r}, which is not a spell in the document")
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {spell} at p. {page}, document has it at p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {spell} — the citation is "
                "wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Spell Descriptions, p. {page} ({spell})",
                "kind": kind,
                "implemented": False,
            }
        )
    return shapes


# Printed pages 254-364 are Monsters and the Animals section that continues it. The
# Animals list runs to the last page of the document; stopping at the contents' "358"
# silently truncated Reef Shark, Seahorse, and Swarm of Piranhas.
MONSTER_PAGES = range(253, 364)
MONSTER_HEADING_SIZE = 14.8

#: Effect shapes found by sweeping Monsters, verified the same way SPELL_SHAPES are.
#:
#: Stat blocks are set in Optima with names in 14.8pt GillSans-SemiBold, so the entries
#: enumerate mechanically; which of their mechanics is a distinct shape is editorial.
#:
#: Shapes the earlier sweeps already name are deliberately absent: a monster's aura is an
#: Emanation, Pack Tactics is Advantage, Frightful Presence applies Frightened, Sunlight
#: Sensitivity is Disadvantage, Flyby is an Opportunity Attack exception, and a
#: Spellcasting trait is the Magic action bounded by Per Day. Re-adding them would inflate
#: the denominator with duplicates and make coverage read worse than it is.
MONSTER_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar monster, printed page, pattern that must match its stat block
    (
        "multiattack",
        "Multiattack",
        "action",
        "Aboleth",
        258,
        r"Multiattack\. The aboleth makes two Tentacle attacks",
    ),
    ("recharge", "Recharging Ability", "resource", "Air Elemental", 258, r"Whirlwind \(Recharge 4"),
    (
        "legendary-resistance",
        "Legendary Resistance",
        "test-modifier",
        "Aboleth",
        258,
        r"Legendary Resistance \(3/Day",
    ),
    ("legendary-action", "Legendary Action", "action", "Aboleth", 258, r"Legendary Action Uses: 3"),
    (
        "regeneration",
        "Regeneration",
        "effect",
        "Troll",
        333,
        r"regains 15 Hit Points at the start of each of its turns",
    ),
    (
        "hit-point-maximum-reduction",
        "Hit Point Maximum Reduction",
        "effect",
        "Clay Golem",
        274,
        r"Hit Point maximum decreases by an amount equal to",
    ),
    (
        "death-triggered-effect",
        "Effect Triggered by Death",
        "effect",
        "Magmin",
        305,
        r"Death Burst\. The magmin explodes when it dies",
    ),
    (
        "swarm-space-sharing",
        "Swarm Occupying Another Creature's Space",
        "targeting",
        "Swarm of Bats",
        361,
        r"can occupy another creature.s space",
    ),
    (
        "escape-dc",
        "Escape DC for an Applied Grapple",
        "state",
        "Aboleth",
        258,
        r"Grappled condition \(escape DC 14\)",
    ),
    (
        "repeat-save-to-end-effect",
        "Repeated Save to End an Effect",
        "test",
        "Basilisk",
        262,
        r"repeats the save at the end of its next turn",
    ),
)


def read_monsters(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every stat block as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    monsters: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in MONSTER_PAGES:
        page = doc[pno]
        mid = page.rect.width / 2
        columns: dict[int, list[tuple[float, str, bool]]] = {0: [], 1: []}
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if RUNNING_HEADER.match(text):
                    continue
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == MONSTER_HEADING_SIZE
                    for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    monsters[text.strip()] = current
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in monsters.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return monsters


def sweep_monsters(pdf: Path) -> list[dict[str, object]]:
    """Verify every MONSTER_SHAPES row against the document, then return the shapes."""
    monsters = read_monsters(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, monster, page, pattern in MONSTER_SHAPES:
        entry = monsters.get(monster)
        if entry is None:
            raise SystemExit(f"{shape_id}: cites {monster!r}, which is not a stat block")
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {monster} at p. {page}, document has it at p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {monster} — the citation is "
                "wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Monsters, p. {page} ({monster})",
                "kind": kind,
                "implemented": False,
            }
        )
    return shapes


# Printed pages 204-253 are Magic Items, including the intro sections on charges,
# attunement, and sentient items.
MAGIC_ITEM_PAGES = range(203, 253)

#: Effect shapes found by sweeping Magic Items, verified the same way the others are.
#:
#: Shapes the earlier sweeps already name are deliberately absent: an item granting a Fly
#: Speed, Resistance, Advantage, or Proficiency is those shapes, not new ones.
#:
#: One candidate was dropped rather than recorded. A "set an ability score to N" shape looked
#: likely, but the only supporting text in this section is Gauntlets of Ogre Power's negative
#: clause — "no effect on you if your Strength is 19 or higher" — which states a condition,
#: not a score being set. Absent clearer wording in the document, it is not recorded: a shape
#: invented from a plausible reading is exactly the inference the seed decision forbids.
MAGIC_ITEM_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar item, printed page, pattern that must match its text
    (
        "item-charges",
        "Expending Item Charges",
        "resource",
        "Cloak of Invisibility",
        215,
        r"This cloak has 3 charges",
    ),
    (
        "daily-recharge",
        "Charges Regained on a Daily Schedule",
        "resource",
        "Cloak of Invisibility",
        215,
        r"regains 1d3 expended",
    ),
    (
        "numeric-bonus",
        "Flat Numeric Bonus to Rolls",
        "test-modifier",
        "Berserker Axe",
        213,
        r"\+1 bonus to attack rolls and damage rolls",
    ),
    (
        "spell-cast-from-item",
        "Spell Cast from an Item",
        "spellcasting",
        "Necklace of Prayer Beads",
        233,
        r"contains a spell that you can cast from it",
    ),
    (
        "item-destruction",
        "Item Destroyed by a Stated Condition",
        "effect",
        "Bag of Holding",
        212,
        r"it is destroyed, and its contents are scattered",
    ),
    (
        "random-effect-table",
        "Effect Chosen at Random from a Table",
        "effect",
        "Bag of Beans",
        211,
        r"determine it randomly",
    ),
)


def read_magic_items(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Magic Items entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in MAGIC_ITEM_PAGES:
        page = doc[pno]
        mid = page.rect.width / 2
        columns: dict[int, list[tuple[float, str, bool]]] = {0: [], 1: []}
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if RUNNING_HEADER.match(text):
                    continue
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries[text.strip()] = current
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_magic_items(pdf: Path) -> list[dict[str, object]]:
    """Verify every MAGIC_ITEM_SHAPES row against the document, then return the shapes."""
    entries = read_magic_items(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, item, page, pattern in MAGIC_ITEM_SHAPES:
        entry = entries.get(item)
        if entry is None:
            raise SystemExit(f"{shape_id}: cites {item!r}, which is not a Magic Items entry")
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {item} at p. {page}, document has it at p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {item} — the citation is "
                "wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Magic Items, p. {page} ({item})",
                "kind": kind,
                "implemented": False,
            }
        )
    return shapes


# Printed pages 89-103 are Equipment.
EQUIPMENT_PAGES = range(88, 103)

#: Effect shapes found by sweeping Equipment, verified the same way the others are.
#:
#: Two exclusions, both deliberate. `Reach` is here as a weapon property but the Rules
#: Glossary already defines it (p. 186), so it is not re-added. The armor subsections
#: ("Light, Medium, or Heavy Armor", "Shield") are subdivisions of `Armor Training`, which
#: the Glossary already names.
#:
#: The eight mastery properties are listed individually even though five of them deliver
#: effects the inventory already names — Push is forced movement, Topple applies Prone, Vex
#: grants Advantage, Sap imposes Disadvantage, Slow reduces Speed. That looks like the
#: duplication declined in the monster sweep, and the distinction is deliberate: Pack
#: Tactics is one creature's trait, while Mastery Properties is a closed, named set the
#: document enumerates as a mechanic — the same shape as the fifteen conditions and the six
#: areas of effect, each of which is its own entry. An engine can implement Topple and not
#: Vex, so they fail independently, which is the granularity rule this inventory uses.
EQUIPMENT_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar entry, printed page, pattern that must match its text
    (
        "weapon-ammunition",
        "Ammunition",
        "weapon-property",
        "Ammunition",
        89,
        r"you have ammunition to fire from it",
    ),
    (
        "weapon-finesse",
        "Finesse",
        "weapon-property",
        "Finesse",
        89,
        r"Strength or Dexterity modifier for the attack and damage rolls",
    ),
    ("weapon-heavy", "Heavy", "weapon-property", "Heavy", 89, r"Strength score isn.t at least 13"),
    (
        "weapon-light",
        "Light",
        "weapon-property",
        "Light",
        89,
        r"make one extra attack as a Bonus Action",
    ),
    (
        "weapon-loading",
        "Loading",
        "weapon-property",
        "Loading",
        90,
        r"regardless of the number of attacks you can normally make",
    ),
    ("weapon-range", "Range", "weapon-property", "Range", 90, r"normal range in feet"),
    (
        "weapon-thrown",
        "Thrown",
        "weapon-property",
        "Thrown",
        90,
        r"throw the weapon to make a ranged attack",
    ),
    ("weapon-two-handed", "Two-Handed", "weapon-property", "Two-Handed", 90, r"you attack with it"),
    (
        "weapon-versatile",
        "Versatile",
        "weapon-property",
        "Versatile",
        90,
        r"deals that damage when used with two hands",
    ),
    (
        "mastery-cleave",
        "Cleave",
        "weapon-mastery",
        "Cleave",
        90,
        r"against a second creature within 5 feet of the first",
    ),
    (
        "mastery-graze",
        "Graze",
        "weapon-mastery",
        "Graze",
        90,
        r"equal to the ability modifier you used to make the attack roll",
    ),
    (
        "mastery-nick",
        "Nick",
        "weapon-mastery",
        "Nick",
        90,
        r"as part of the Attack action instead of as a Bonus Action",
    ),
    (
        "mastery-push",
        "Push",
        "weapon-mastery",
        "Push",
        90,
        r"up to 10 feet straight away from yourself",
    ),
    ("mastery-sap", "Sap", "weapon-mastery", "Sap", 90, r"Disadvantage on its next attack roll"),
    ("mastery-slow", "Slow", "weapon-mastery", "Slow", 90, r"reduce its Speed by 10 feet"),
    ("mastery-topple", "Topple", "weapon-mastery", "Topple", 90, r"Constitution saving throw"),
    (
        "mastery-vex",
        "Vex",
        "weapon-mastery",
        "Vex",
        90,
        r"Advantage on your next attack roll against that creature",
    ),
)


def read_equipment(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Equipment entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in EQUIPMENT_PAGES:
        page = doc[pno]
        mid = page.rect.width / 2
        columns: dict[int, list[tuple[float, str, bool]]] = {0: [], 1: []}
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if RUNNING_HEADER.match(text):
                    continue
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries[text.strip()] = current
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_equipment(pdf: Path) -> list[dict[str, object]]:
    """Verify every EQUIPMENT_SHAPES row against the document, then return the shapes."""
    entries = read_equipment(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, entry_name, page, pattern in EQUIPMENT_SHAPES:
        entry = entries.get(entry_name)
        if entry is None:
            raise SystemExit(f"{shape_id}: cites {entry_name!r}, which is not an Equipment entry")
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {entry_name} at p. {page}, document has it at "
                f"p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {entry_name} — the citation "
                "is wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Equipment, p. {page} ({entry_name})",
                "kind": kind,
                "implemented": False,
            }
        )
    return shapes


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

    shapes.extend(sweep_spells(pdf))
    shapes.extend(sweep_monsters(pdf))
    shapes.extend(sweep_magic_items(pdf))
    shapes.extend(sweep_equipment(pdf))

    return {
        "schema_version": 1,
        "compat": 1,
        "source": {
            "document": "System Reference Document 5.2.1",
            "revision": "5.2.1",
            "published": "2025-05-01",
            "section": (
                "Rules Glossary (pp. 176-191); Spell Descriptions (pp. 107-175); "
                "Monsters (pp. 254-364); Magic Items (pp. 204-253); Equipment (pp. 89-103)"
            ),
        },
        "coverage_scope": (
            "Rules Glossary, Spell Descriptions, Monsters, Magic Items, and Equipment. "
            "Still unswept: Classes, Character Origins, Feats, and the Gameplay Toolbox. "
            "Until those land this inventory understates what full coverage requires."
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
