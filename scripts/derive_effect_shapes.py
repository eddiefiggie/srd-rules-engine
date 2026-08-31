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

## It cannot notice its own staleness, so this line is the record

Not being in CI means nothing tells you it stopped working. It stopped working on 2026-08-29:
[#352](https://github.com/eddiefiggie/srd-rules-engine/issues/352) added `"mastery-push"` to
`IMPLEMENTED_SECTION_SHAPES` and, in the same edit, deleted the identical line from
`EQUIPMENT_SHAPES`'s Push row — leaving a 5-tuple in a table `sweep_equipment` unpacks into
six names. Every run after that died on `ValueError: not enough values to unpack`, and the
figures the README publishes went a day unable to be re-derived
([#373](https://github.com/eddiefiggie/srd-rules-engine/issues/373)).

Two things came out of that, because a fix that only repaired the row would leave the same
trap set:

* **`--check`**, which compares without writing and exits non-zero on a difference. A person
  holding the PDF can now verify the shipped inventory is current instead of overwriting it
  and reading a diff.
* **`tests/test_shape_tables_are_well_formed.py`**, which is hermetic and therefore *does*
  run in CI. It cannot read the document, but it can check that every one of the ten
  `*_SHAPES` tables holds rows of the arity its own sweep unpacks — which is the whole of what
  broke, and the half of this script that never needed the PDF.

**Last run green against SRD v5.2.1: 2026-08-31**, reproducing `effect_shapes.json`
byte-for-byte — 210 shapes, 134 implemented, 22 vocabulary. Update this line when you re-run
it, because nothing else can.

Usage: python3 scripts/derive_effect_shapes.py /path/to/SRD_CC_v5.2.1.pdf [--check]
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
        n: ("condition", True)
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
    # Three of the five hazards resolve (#140, #183); Dehydration and Malnutrition are held
    # by 0031 clause 3 — p. 236 and pp. 181/185 contradict each other about removing their
    # Exhaustion levels, and a contradiction states no rule.
    **{n: ("hazard", True) for n in ("Burning", "Falling", "Suffocation")},
    # p. 181's Dehydration is built (#315, 0080): a level at a day's end with no die, so a
    # state transition rather than a resolver. p. 185's Malnutrition is not — it compels a
    # DC 10 Constitution save, and the occasion that could produce a ruling on the campaign
    # axis does not exist (#399). They stopped sharing a flag when they stopped sharing a
    # blocker.
    "Dehydration": ("hazard", True),
    "Malnutrition": ("hazard", False),
    **{n: ("targeting", True) for n in ("Cone", "Cube", "Cylinder", "Emanation", "Line", "Sphere")},
    **{n: ("attitude", True) for n in ("Friendly", "Hostile", "Indifferent")},
    "Attack": ("action", True),
    # Dash, Disengage and Dodge need only the action economy and movement, both of which
    # exist. The other eight wait on skills, attitudes, spellcasting or reaction triggers.
    **{n: ("action", True) for n in ("Dash", "Disengage", "Dodge")},
    # p. 13's free object interaction and the action that buys a second (#288, 0045). It
    # reaches the four moves the engine models — equip, stow, drop, pick up — and p. 14's GM
    # escalation and p. 177's Breaking Objects stay beyond it, disclosed on the read surface.
    "Utilize": ("action", True),
    # p. 187 and p. 189: one mechanism, two entries, and neither states a DC — the caller
    # supplies it with its derivation, as `perception_resolver` does (#411).
    **{n: ("action", True) for n in ("Search", "Study")},
    # p. 184, and the three attitudes that move its check (#142). The first core fact type
    # this engine ships — attitude is a narrative fact carrying mechanical weight (R20).
    "Influence": ("action", True),
    **{
        n: ("action", False)
        for n in (
            "Help",
            "Hide",
            "Magic",
            "Ready",
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
    "Area of Effect": ("targeting", True),
    "Armor Class": ("state", True),
    "Armor Training": ("state", True),
    "Attack Roll": ("test", True),
    "Attitude": ("state", True),
    "Attunement": ("state", False),
    "Blindsight": ("sense", True),
    "Bloodied": ("state", True),
    "Bonus Action": ("action", True),
    "Breaking Objects": ("effect", False),
    "Bright Light": ("environment", True),
    "Burrow Speed": ("movement", False),
    "Campaign": ("vocabulary", False),
    "Cantrip": ("spellcasting", True),
    "Carrying Capacity": ("state", True),
    "Challenge Rating": ("vocabulary", False),
    "Character Sheet": ("vocabulary", False),
    "Climbing": ("movement", True),
    "Climb Speed": ("movement", True),
    "Concentration": ("state", True),
    "Condition": ("effect", False),
    "Cover": ("targeting", False),
    "Crawling": ("movement", True),
    "Creature": ("vocabulary", False),
    "Creature Type": ("state", False),
    "Critical Hit": ("test", True),
    "Curses": ("effect", False),
    "D20 Test": ("test", True),
    "Damage": ("effect", True),
    "Damage Roll": ("test", True),
    "Damage Threshold": ("state", True),
    "Damage Types": ("effect", True),
    "Darkness": ("environment", True),
    "Darkvision": ("sense", True),
    "Dead": ("state", False),
    "Death Saving Throw": ("test", True),
    "Difficult Terrain": ("movement", True),
    "Difficulty Class": ("test", True),
    "Dim Light": ("environment", True),
    "Disadvantage": ("test-modifier", True),
    "Encounter": ("vocabulary", False),
    "Enemy": ("vocabulary", False),
    "Experience Points": ("vocabulary", False),
    "Expertise": ("state", True),
    "Flying": ("movement", True),
    "Fly Speed": ("movement", True),
    "Grappling": ("effect", True),
    "Hazard": ("effect", False),
    "Healing": ("effect", True),
    "Heavily Obscured": ("environment", True),
    "Heroic Inspiration": ("vocabulary", False),
    "High Jump": ("movement", False),
    "Hit Point Dice": ("resource", True),
    "Hit Points": ("state", True),
    "Hover": ("movement", True),
    "Illusions": ("effect", False),
    "Immunity": ("effect", False),
    "Improvised Weapons": ("equipment", False),
    "Initiative": ("test", True),
    "Jumping": ("movement", True),
    "Knocking Out a Creature": ("effect", True),
    "Lightly Obscured": ("environment", True),
    "Long Jump": ("movement", True),
    "Long Rest": ("effect", False),
    "Magical Effect": ("vocabulary", False),
    "Monster": ("vocabulary", False),
    "Nonplayer Character": ("vocabulary", False),
    "Object": ("vocabulary", False),
    "Occupied Space": ("targeting", False),
    "Opportunity Attacks": ("action", True),
    "Passive Perception": ("test", True),
    "Per Day": ("resource", False),
    "Player Character": ("vocabulary", False),
    "Possession": ("effect", False),
    "Proficiency": ("state", False),
    "Reach": ("targeting", True),
    "Reaction": ("action", True),
    "Resistance": ("effect", True),
    "Ritual": ("spellcasting", True),
    "Round Down": ("vocabulary", False),
    # Not a `test`: p. 187 says outright it is another name for a saving throw, and both
    # ids already resolved to `TestKind.SAVE` (0035, #230).
    "Save": ("vocabulary", False),
    "Saving Throw": ("test", True),
    "Shape-Shifting": ("effect", False),
    "Short Rest": ("effect", True),
    "Simultaneous Effects": ("convention", False),
    "Size": ("state", True),
    "Skill": ("state", True),
    "Speed": ("movement", True),
    "Spell": ("vocabulary", False),
    "Spell Attack": ("test", True),
    # p. 188, #245. A held focus stands in for Material components that are neither
    # consumed nor costed, which is what `component_refusal` reads.
    "Spellcasting Focus": ("equipment", True),
    "Stable": ("state", True),
    "Stat Block": ("vocabulary", False),
    "Surprise": ("effect", False),
    "Swimming": ("movement", True),
    "Swim Speed": ("movement", True),
    "Target": ("targeting", False),
    "Telepathy": ("sense", False),
    "Teleportation": ("effect", False),
    "Temporary Hit Points": ("effect", True),
    "Tremorsense": ("sense", False),
    "Truesight": ("sense", False),
    "Unarmed Strike": ("action", True),
    "Unoccupied Space": ("targeting", False),
    "Vulnerability": ("effect", True),
    "Weapon": ("vocabulary", False),
    # Not a `test`: the document defines the term on p. 191 and never uses it (0034, #229).
    "Weapon Attack": ("vocabulary", False),
}

#: Why a glossary entry is vocabulary rather than an effect shape. Keyed by kind so the
#: reason is stated once rather than copy-pasted 20 times and drifting.
VOCABULARY_REASON = (
    "Defines a term the rules use; it names no mechanical change the engine resolves."
)

#: Entries set aside for a *different* reason than the default. Decision 0013 found the
#: artifact recording one reason for nineteen entries while a second criterion was being
#: applied that appeared nowhere outside generator comments. A reason per entry is what
#: stops that recurring: the exclusion a consumer can see is the exclusion that was used.
VOCABULARY_REASONS: dict[str, str] = {
    "Heroic Inspiration": (
        "Mechanical, but not a separate shape: it is the document's own name for one "
        "instance of `die-replacement`, differing from Halfling Luck and Wish in trigger "
        "and cost rather than in mechanism. Decision 0013, Q5."
    ),
    "Weapon Attack": (
        "Not a separate shape: it renames `attack-roll` with a parameter fixed — p. 177's "
        "entry already enumerates its three cases as weapon, Unarmed Strike and spell — and "
        "differs from it in that parameter rather than in mechanism. The deciding evidence "
        "is that the document defines the term on p. 191 and never uses it: `weapon attack` "
        "occurs three times in the whole document, twice in its own entry and once on p. 217 "
        "as a noun and a verb ('the hovering weapon attacks'). Nothing gates a mechanic on "
        "it. `spell-attack` reads the same way and is a shape anyway, because p. 106 gives "
        "it a bonus formula of its own — which is why the test is consumers rather than "
        "phrasing. Decisions 0034 and 0013, Q1/Q3/Q5."
    ),
    "Save": (
        "Not a separate shape: p. 187 states it is another name for `saving-throw`, and the "
        "parent entry declares the alias itself ('A saving throw—also called a save—'). It "
        "fixes no parameter and names the identical set, so the two are one shape. The "
        "deciding evidence is that both ids already resolved to the same symbol, "
        "`core.d20.TestKind.SAVE`, on adjacent lines of `core.inventory` — one mechanic "
        "counted twice in the numerator and the denominator both. Heavy use is not evidence "
        "either way: the document uses 'save' 1544 times and 'saving throw' 636, and use "
        "of a synonym is use of the thing it names. Decision 0035."
    ),
}

#: `kind` answers a **filing** question — which part of the rules a shape belongs to, for
#: measuring coverage — and not what the shape does (decision 0019). Where a shape could be
#: filed two ways, file it under the subsystem that implements it or would: Prone is
#: `condition` because `core.conditions` holds it, `die-replacement` is `test-modifier`
#: because `core.d20` does. The axis genuinely conflates "what it is" with "what it applies
#: to"; 0019 records that this does not matter, because the applies-to is plural for many
#: shapes and the behaviour is modelled in code rather than here.
#:
#: The closed set of `kind` values. Classification is editorial, so this is the reviewable
#: layer — but it was unguarded through eleven sweeps and drifted from roughly fifteen
#: values to nineteen without anything noticing. Decision 0013 closes it. Adding a value is
#: a deliberate edit here, not a typo that lands silently in the published artifact.
#: Section-swept shapes the engine resolves. The glossary carries its claim in `KINDS`;
#: the sweeps hard-coded `False`, which was fine while none of them was implemented and
#: became a floor the moment one was. Asserted against `ENGINE_SHAPES` in both directions
#: by tests/test_effect_shape_inventory.py, so an optimistic entry here fails the build.
#: Which of the section sweeps' shapes the engine resolves. The glossary sweep carries the
#: same claim in `KINDS`, and `tests/test_effect_shape_inventory.py` compares **both** against
#: the shipped data — because a generator whose flags disagree with the file it writes turns
#: the next regeneration into a silent rewrite of coverage.
#:
#: That guard read only `KINDS` until #325, and this set had drifted six deep behind it:
#: `multiattack`, `weapon-ammunition`, `weapon-light`, `weapon-loading`, `weapon-thrown` and
#: `weapon-two-handed` were each claimed in the JSON by hand as their PR landed and never
#: written back here. Regenerating would have reported 97 implemented over a shipped 103,
#: with the full suite green — the identical failure the `KINDS` half of the guard was
#: written for, one constant away from where it was looking.
IMPLEMENTED_SECTION_SHAPES: frozenset[str] = frozenset(
    {
        # p. 197, and the only one of the four delivery types whose exposure this engine can
        # observe: Piercing or Slashing damage from a coated object (#141). The other three
        # are exposed by a touch, a swallow and a cloud.
        "poison-injury",
        # p. 17's Instant Death, built since the death saves shipped and unclaimed until an
        # audit read the inventory against the code (#426). Two of its three clauses are in
        # `with_damage` with tests; the third, a hit point maximum reaching 0, has no
        # antecedent because nothing here reduces one.
        "instant-death",
        "natural-20-auto-hit",
        "advantage-does-not-stack",
        "damage-application-order",
        "damage-modifier-no-stacking",
        "multiattack",
        "weapon-ammunition",
        "weapon-finesse",
        "weapon-heavy",
        "weapon-light",
        "weapon-loading",
        "weapon-reach",
        "weapon-thrown",
        "weapon-two-handed",
        "weapon-versatile",
        "mastery-graze",
        "mastery-nick",
        "mastery-topple",
        "mastery-cleave",
        "forced-movement",
        "mastery-push",
        "mastery-slow",
        "mastery-vex",
        "mastery-sap",
        "split-movement",
        "weapon-range",
        "spell-slot",
        "regain-spell-slots",
        "numeric-bonus",
        "die-applied-to-a-roll",
        "die-replacement",
        "failed-test-overridden-to-success",
    }
)

KIND_VALUES: frozenset[str] = frozenset(
    {
        "action",
        "affliction",
        "attitude",
        "condition",
        "convention",
        "effect",
        "environment",
        "equipment",
        "hazard",
        "movement",
        "resource",
        "sense",
        "spellcasting",
        "state",
        "targeting",
        "test",
        "test-modifier",
        "weapon-mastery",
        "weapon-property",
    }
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


def baseline(spans: list[dict[str, object]]) -> float:
    """Where a line sits on the page, for ordering it against the others (#326).

    **The baseline, not the top of the bounding box.** The two are not interchangeable here
    and the difference reordered every entry in the document. Headings are 12pt
    GillSans-SemiBold and body text is 10pt Cambria, and the fonts declare very different
    boxes — Cambria's reported top sits about 31pt above its baseline, GillSans-SemiBold's
    about 11. So a heading and the body line beneath it sorted in the wrong order by a
    constant 7.14pt, and each entry's first line was appended to the *previous* entry:

        bbox top 211.03 / baseline 222.34  'Reach'
        bbox top 203.89 / baseline 235.06  'A Reach weapon adds 5 feet to your reach when you'

    Every entry's verified text was therefore a window shifted one line late at both ends —
    missing its own opening line and carrying the next entry's. Nothing went red, because
    every pattern in this file was chosen by someone reading that shifted text. The danger is
    that a pattern can match prose belonging to the **next** entry, which makes a citation
    verifiable against the wrong entry — the one thing these sweeps exist to prevent.

    A baseline is font-independent, which is why it is the right key rather than a corrected
    offset.
    """
    return min(float(s["origin"][1]) for s in spans)  # type: ignore[index]


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
                y0 = baseline(spans)
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
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
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
                y0 = baseline(spans)
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
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
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
                y0 = baseline(spans)
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
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 89-103 are Equipment.
EQUIPMENT_PAGES = range(88, 103)

#: Effect shapes found by sweeping Equipment, verified the same way the others are.
#:
#: One exclusion, deliberate: the armor subsections ("Light, Medium, or Heavy Armor",
#: "Shield") are subdivisions of `Armor Training`, which the Glossary already names.
#:
#: **`Reach` used to be a second, and it was wrong** (#316). The stated reason was that the
#: Rules Glossary already defines it at p. 186, which is true of the *term* and not of the
#: *mechanic*: p. 186 gives the 5-foot default "unless a rule says otherwise", and p. 90 is
#: the rule that says otherwise. Folding them let one flag claim two mechanics, and the
#: engine had built only the default — so `reach` read as implemented over an unbuilt weapon
#: property for as long as the fold stood. The inventory's own granularity rule settles it:
#: entries sit at independently-failable granularity, and these two failed independently for
#: forty-five builds. The fifteen conditions are separate entries for the same reason.
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
        "weapon-reach",
        "Reach",
        "weapon-property",
        "Reach",
        90,
        r"adds 5 feet to your reach when you attack with it",
    ),
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
                y0 = baseline(spans)
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
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 28-82 are Classes.
CLASS_PAGES = range(27, 82)
#: Class-feature headings read "Level 3: Sneak Attack". The level belongs to the class
#: progression, not to the shape, so the citation drops it.
LEVEL_PREFIX = re.compile(r"^Level \d+: ")

#: Effect shapes found by sweeping Classes, verified the same way the others are.
#:
#: This section is the one where the shape/content line matters most. It holds 294 class
#: features, and 294 features are not 294 shapes: a class feature is *content written in the
#: effect vocabulary*, which is the parallel data track, not the vocabulary itself. What is
#: harvested here is only the mechanisms this section introduces that no earlier sweep can
#: already express.
#:
#: Six candidates were declined as already expressible:
#:   Extra Attack     -> `multiattack`; both are "the Attack action yields N attacks"
#:   Second Wind      -> `healing`
#:   Unarmored Defense-> `Armor Class`, whose Glossary entry already provides for a rule
#:                       giving you another base AC calculation
#:   Proficiency Bonus-> `Proficiency`
#:   Expertise        -> `Expertise`
#:   Ability Score Improvement -> character progression rather than an adjudicated effect:
#:                       no Ruling applies it, so it is not a shape the engine resolves
CLASS_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar feature heading, printed page, pattern matching its text
    (
        "spell-slot",
        "Spell Slot",
        "resource",
        "Level 1: Spellcasting",
        32,
        r"how many spell slots you have",
    ),
    (
        "resource-recharge",
        "Resource Recharge",
        "resource",
        "Level 1: Rage",
        28,
        r"regain all expended uses when you finish a Long Rest",
    ),
    (
        "resource-point-pool",
        "Spendable Point Pool",
        "resource",
        "Level 2: Font of Magic",
        66,
        r"Sorcery Points, which allow you to create",
    ),
    (
        "regain-spell-slots",
        "Expended Spell Slots Recovered",
        "resource",
        "Level 1: Arcane Recovery",
        78,
        r"choose expended spell slots to recover",
    ),
    (
        "die-applied-to-a-roll",
        "Rolled Die Applied to a D20 Test in Either Direction",
        "test-modifier",
        "Level 1: Bardic Inspiration",
        31,
        r"Bardic Inspiration die, which is a d6",
    ),
    (
        "conditional-extra-damage",
        "Conditional Extra Damage",
        "effect",
        "Level 1: Sneak Attack",
        61,
        r"deal an extra 1d6 damage to one creature you hit",
    ),
    (
        "extra-action",
        "Additional Action on Your Turn",
        "action",
        "Level 2: Action Surge",
        48,
        r"take one additional action",
    ),
    (
        "modify-a-spell",
        "Modifying a Spell as It Is Cast",
        "spellcasting",
        "Level 2: Metamagic",
        66,
        r"alter your spells to suit your needs",
    ),
)


def read_classes(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every class-feature entry as heading -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in CLASS_PAGES:
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
                y0 = baseline(spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries.setdefault(text.strip(), current)
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_classes(pdf: Path) -> list[dict[str, object]]:
    """Verify every CLASS_SHAPES row against the document, then return the shapes."""
    entries = read_classes(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, heading, page, pattern in CLASS_SHAPES:
        entry = entries.get(heading)
        if entry is None:
            raise SystemExit(f"{shape_id}: cites {heading!r}, which is not a class feature")
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {heading} at p. {page}, document has it at p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {heading} — the citation is "
                "wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Classes, p. {page} ({LEVEL_PREFIX.sub('', heading)})",
                "kind": kind,
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 87-88 are Feats: 17 entries across four categories.
FEAT_PAGES = range(86, 88)

#: Effect shapes found by sweeping Feats, verified the same way the others are.
#:
#: Most feats compose shapes the earlier sweeps already name: Archery, Defense, and
#: Two-Weapon Fighting are `numeric-bonus`; Boon of Dimensional Travel is `Teleportation`;
#: Boon of the Night Spirit applies `Invisible`; Boon of Truesight is `Truesight`; Magic
#: Initiate is spellcasting; Skilled is `Proficiency`; Grappler is `Grappled` plus
#: `Advantage`; and Alert's Initiative Proficiency is another `numeric-bonus` — only its
#: Initiative Swap is new. Boon of Fate is `bonus-die-on-roll`, though it may apply the
#: rolled total as a penalty as well as a bonus, which that entry does not currently say.
#:
#: "Ability Score Increase" recurs in most feats here and is deliberately absent, on the
#: same ground the Classes sweep used: no Ruling applies it, so it is character progression
#: rather than an effect the engine resolves. That rule is doing real work now rather than
#: settling one edge case, and it is flagged for agreement on #70.
FEAT_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar feat, printed page, pattern that must match its text
    (
        "ability-score-increase",
        "Ability Score Increased to a Bounded Maximum",
        "state",
        "Boon of Combat Prowess",
        88,
        r"Increase one ability score of your choice by 1, to a maximum of 30",
    ),
    (
        "failed-test-overridden-to-success",
        "Failed D20 Test Overridden to a Success",
        "test-modifier",
        "Boon of Combat Prowess",
        88,
        r"When you miss with an attack roll, you can hit instead",
    ),
    (
        "ignore-resistance",
        "Damage That Ignores Resistance",
        "effect",
        "Boon of Irresistible Offense",
        88,
        r"always ignores Resistance",
    ),
    (
        "slot-not-expended",
        "Spell Slot Not Expended on Casting",
        "resource",
        "Boon of Spell Recall",
        88,
        r"the slot isn.t expended",
    ),
    (
        "initiative-swap",
        "Initiative Positions Exchanged",
        "state",
        "Alert",
        87,
        r"swap your Initiative with the Initiative of one willing ally",
    ),
    (
        "roll-twice-take-either",
        "Damage Dice Rolled Twice, Either Result Used",
        "test-modifier",
        "Savage Attacker",
        87,
        r"roll the weapon.s damage dice twice and use either roll",
    ),
    (
        "minimum-die-value",
        "Low Die Result Treated as Higher",
        "test-modifier",
        "Great Weapon Fighting",
        88,
        r"treat any 1 or 2 on a damage die as a 3",
    ),
)


def read_feats(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Feats entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in FEAT_PAGES:
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
                y0 = baseline(spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries.setdefault(text.strip(), current)
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_feats(pdf: Path) -> list[dict[str, object]]:
    """Verify every FEAT_SHAPES row against the document, then return the shapes."""
    entries = read_feats(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, feat, page, pattern in FEAT_SHAPES:
        entry = entries.get(feat)
        if entry is None:
            raise SystemExit(f"{shape_id}: cites {feat!r}, which is not a feat in the document")
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {feat} at p. {page}, document has it at p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {feat} — the citation is "
                "wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Feats, p. {page} ({feat})",
                "kind": kind,
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 192-203 are the Gameplay Toolbox.
TOOLBOX_PAGES = range(191, 203)
#: Poison entries are headed "Serpent Venom (200 GP)". The price is catalogue data, not
#: part of the shape's citation, so it is dropped the way class levels are.
PRICE_SUFFIX = re.compile(r"\s*\([\d,]+ GP\)$")

#: Effect shapes found by sweeping the Gameplay Toolbox, verified as the others are.
#:
#: Most of this section is guidance for a GM rather than mechanics the engine resolves, and
#: the declines are as considered as the entries:
#:   Fear Effects        -> the document itself says to "use the Frightened condition as the
#:                          baseline effect", so it composes rather than introduces
#:   Prolonged Effects   -> conditions plus `end-magical-effect` (removal by a named spell)
#:   Curses              -> the Rules Glossary already defines `Curses`
#:   Travel Pace, Creating a Background, Combat Encounters -> table and encounter-building
#:                          tooling; no Ruling applies them
#:
#: The nine Environmental Effects (Deep Water, Extreme Cold, Extreme Heat, Frigid Water,
#: Heavy Precipitation, High Altitude, Slippery Ice, Strong Wind, Thin Ice) are also declined,
#: and this is the closest call in the sweep. They are a closed named set, which is the
#: argument that admitted the eight mastery properties — but each composes existing shapes
#: (Exhaustion, Difficult Terrain, Prone) and the document presents them as worked examples of
#: applying rules rather than as a mechanic with its own rules subsection. Mastery Properties
#: has such a subsection; Environmental Effects does not.
TOOLBOX_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar entry, printed page, pattern that must match its text
    (
        "poison-contact",
        "Contact Poison",
        "affliction",
        "Crawler Mucus (200 GP)",
        197,
        r"Contact Poison",
    ),
    (
        "poison-ingested",
        "Ingested Poison",
        "affliction",
        "Assassin’s Blood (150 GP)",  # noqa: RUF001 — the document's own apostrophe
        197,
        r"Ingested Poison",
    ),
    (
        "poison-inhaled",
        "Inhaled Poison",
        "affliction",
        "Burnt Othur Fumes (500 GP)",
        197,
        r"Inhaled Poison",
    ),
    (
        "poison-injury",
        "Injury Poison",
        "affliction",
        "Purple Worm Poison (2,000 GP)",
        198,
        r"Injury Poison",
    ),
    (
        "trap-trigger",
        "Effect Fired by a Trap Trigger",
        "targeting",
        "Hidden Pit",
        200,
        r"Trigger: A creature moves onto the pit.s lid",
    ),
    (
        "magical-contagion",
        "Magical Contagion",
        "affliction",
        "Cackle Fever",
        194,
        r"Magical Contagion",
    ),
)


def read_toolbox(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Gameplay Toolbox entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in TOOLBOX_PAGES:
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
                y0 = baseline(spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries.setdefault(text.strip(), current)
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_toolbox(pdf: Path) -> list[dict[str, object]]:
    """Verify every TOOLBOX_SHAPES row against the document, then return the shapes."""
    entries = read_toolbox(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, entry_name, page, pattern in TOOLBOX_SHAPES:
        entry = entries.get(entry_name)
        if entry is None:
            raise SystemExit(
                f"{shape_id}: cites {entry_name!r}, which is not a Gameplay Toolbox entry"
            )
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
                "reference": f"Gameplay Toolbox, p. {page} ({PRICE_SUFFIX.sub('', entry_name)})",
                "kind": kind,
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 83-86 are Character Origins: backgrounds and the nine species.
ORIGIN_PAGES = range(82, 86)

#: Effect shapes found by sweeping Character Origins, verified as the others are.
#:
#: Species traits are overwhelmingly composition, and the declines are the bulk of this
#: section: Dragonborn's Breath Weapon is an area plus a save plus damage; the cantrip-
#: granting traits are spellcasting; Dwarven Resilience and Brave are `Advantage`; Orcish
#: Fury's temporary hit points are `Temporary Hit Points`; Darkvision, Speed, Size, and
#: Creature Type are all Glossary entries already.
ORIGIN_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar species, printed page, pattern that must match its text
    (
        "survive-drop-to-zero",
        "Dropping to 1 Hit Point Instead of 0",
        "effect",
        "Orc",
        86,
        r"you can drop to 1 Hit Point instead",
    ),
    (
        "damage-reduction",
        "Damage Reduced by a Rolled Amount",
        "effect",
        "Goliath",
        85,
        r"reduce the damage by that total",
    ),
    (
        "die-replacement",
        "Rolled Die Replaced, New Roll Binding",
        "test-modifier",
        "Halfling",
        86,
        r"you can reroll the die, and you must use the new roll",
    ),
    (
        "shortened-long-rest",
        "Long Rest Completed in Reduced Time",
        "resource",
        "Elf",
        84,
        r"finish a Long Rest in 4 hours",
    ),
)


def read_origins(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Character Origins entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in ORIGIN_PAGES:
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
                y0 = baseline(spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries.setdefault(text.strip(), current)
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_origins(pdf: Path) -> list[dict[str, object]]:
    """Verify every ORIGIN_SHAPES row against the document, then return the shapes."""
    entries = read_origins(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, species, page, pattern in ORIGIN_SHAPES:
        entry = entries.get(species)
        if entry is None:
            raise SystemExit(
                f"{shape_id}: cites {species!r}, which is not a Character Origins entry"
            )
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {species} at p. {page}, document has it at p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {species} — the citation is "
                "wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Character Origins, p. {page} ({species})",
                "kind": kind,
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 5-18 are Playing the Game.
PLAYING_PAGES = range(4, 18)

#: Effect shapes found by sweeping Playing the Game, verified as the others are.
#:
#: This chapter is largely the narrative form of what the Rules Glossary defines formally,
#: so the decline ratio is high by design: Difficulty Class, Armor Class, Initiative, Range,
#: Reach, Opportunity Attacks, Difficult Terrain, Breaking Objects, Death Saving Throws,
#: Stabilizing, Dropping Prone, Creature Size, and the Temporary Hit Points rules are all
#: Glossary entries already. Moving around Other Creatures composes `Occupied Space` and
#: `Difficult Terrain`; Ranged Attacks in Close Combat is `Disadvantage`.
#:
#: What is left is genuinely absent everywhere else — the roll-resolution overrides, the
#: two stacking rules, the damage application order, and the mounted and underwater combat
#: variants, none of which the Glossary states.
PLAYING_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar entry, printed page, pattern that must match its text
    (
        "natural-20-auto-hit",
        "Natural 20 Hits and Natural 1 Misses Regardless",
        "test-modifier",
        "Rolling 20 or 1",
        7,
        r"the attack hits regardless of any modifiers or the target.s AC",
    ),
    (
        "advantage-does-not-stack",
        "Advantage and Disadvantage Do Not Stack",
        "test-modifier",
        "They Don’t Stack",  # noqa: RUF001 — the document's own apostrophe
        8,
        r"you still roll only two d20s",
    ),
    (
        "split-movement",
        "Movement Broken Up Around Actions",
        "movement",
        "Breaking Up Your Move",
        14,
        r"movement before and after any action",
    ),
    (
        "controlled-mount",
        "Controlled Mount Sharing Your Initiative",
        "state",
        "Controlling a Mount",
        16,
        r"Initiative of a controlled mount changes to match yours",
    ),
    (
        "underwater-combat-penalties",
        "Underwater Attack Penalties",
        "test-modifier",
        "Impeded Weapons",
        16,
        r"Disadvantage on the attack roll unless the weapon deals Piercing",
    ),
    (
        "instant-death",
        "Death Without Death Saving Throws",
        "effect",
        "Instant Death",
        17,
        r"A monster dies the instant it drops to 0 Hit Points",
    ),
    (
        "damage-modifier-no-stacking",
        "Damage Modifiers of a Kind Count Once",
        "effect",
        "No Stacking",
        17,
        r"affect the same damage type count as only one instance",
    ),
    (
        "damage-application-order",
        "Order Damage Modifiers Are Applied",
        "effect",
        "Order of Application",
        17,
        r"Resistance is applied second; and Vulnerability is applied third",
    ),
)


def read_playing(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Playing the Game entry as name -> {page, text}, in reading order.

    Several headings repeat ("They Don't Stack" covers Advantage on p. 8 and Temporary Hit
    Points on p. 18), so first-wins keeps the citation stable and the page assertion in
    `sweep_playing` catches a row that meant the other one.
    """
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in PLAYING_PAGES:
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
                y0 = baseline(spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries.setdefault(text.strip(), current)
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_playing(pdf: Path) -> list[dict[str, object]]:
    """Verify every PLAYING_SHAPES row against the document, then return the shapes."""
    entries = read_playing(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, entry_name, page, pattern in PLAYING_SHAPES:
        entry = entries.get(entry_name)
        if entry is None:
            raise SystemExit(
                f"{shape_id}: cites {entry_name!r}, which is not a Playing the Game entry"
            )
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
                "reference": f"Playing the Game, p. {page} ({entry_name})",
                "kind": kind,
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
            }
        )
    return shapes


# Printed pages 19-27 are Character Creation.
CHARGEN_PAGES = range(18, 27)

#: Effect shapes found by sweeping Character Creation, verified as the others are.
#:
#: This is the thinnest section in the document for this purpose, and that is the right
#: result rather than a shortfall: almost all of it is the procedure for filling in a
#: character sheet - Choose a Background, Generate Your Scores, Write Your Level - which no
#: Ruling applies. Trinkets is a d100 table and is `random-effect-table`. Starting at Higher
#: Levels is procedure. Level Advancement is XP thresholds mapping to levels, declined on
#: the same ground as Ability Score Increase: no Ruling applies it, so it is character
#: progression rather than an effect the engine resolves. That rule is unresolved and
#: flagged on #70; this sweep applies it consistently rather than changing course.
CHARGEN_SHAPES: tuple[tuple[str, str, str, str, int, str], ...] = (
    # id, name, kind, exemplar entry, printed page, pattern that must match its text
    (
        "multiclass-spell-slots",
        "Spell Slots Derived from Combined Class Levels",
        "resource",
        "Spellcasting",
        25,
        r"combined levels in all your spellcasting classes",
    ),
    (
        "feature-does-not-stack",
        "The Same Feature from Two Classes Does Not Stack",
        "state",
        "Extra Attack",
        25,
        r"the features don.t stack",
    ),
)


def read_chargen(pdf: Path) -> dict[str, dict[str, object]]:
    """Return every Character Creation entry as name -> {page, text}, in reading order."""
    import pymupdf

    doc = pymupdf.open(pdf)
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for pno in CHARGEN_PAGES:
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
                y0 = baseline(spans)
                heading = any(
                    s["font"] == HEADING_FONT and round(s["size"], 1) == HEADING_SIZE for s in spans
                )
                columns[0 if x0 < mid else 1].append((y0, text, heading))
        for column in (0, 1):
            for _, text, heading in sorted(columns[column], key=lambda r: r[0]):
                if heading:
                    current = {"page": pno + 1, "text": []}
                    entries.setdefault(text.strip(), current)
                elif current is not None:
                    current["text"].append(text)  # type: ignore[union-attr]
    for entry in entries.values():
        joined = " ".join(entry["text"])  # type: ignore[arg-type]
        joined = joined.replace("\u00ad", "")
        joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", joined)
        entry["text"] = re.sub(r"\s+", " ", joined).strip()
    return entries


def sweep_chargen(pdf: Path) -> list[dict[str, object]]:
    """Verify every CHARGEN_SHAPES row against the document, then return the shapes."""
    entries = read_chargen(pdf)
    shapes: list[dict[str, object]] = []
    for shape_id, name, kind, entry_name, page, pattern in CHARGEN_SHAPES:
        entry = entries.get(entry_name)
        if entry is None:
            raise SystemExit(
                f"{shape_id}: cites {entry_name!r}, which is not a Character Creation entry"
            )
        if entry["page"] != page:
            raise SystemExit(
                f"{shape_id}: cites {entry_name} at p. {page}, document has it at "
                f"p. {entry['page']}"
            )
        if not re.search(pattern, str(entry["text"]), re.I):
            raise SystemExit(
                f"{shape_id}: pattern {pattern!r} does not match {entry_name} - the citation "
                "is wrong, or the shape is not in this document"
            )
        shapes.append(
            {
                "id": shape_id,
                "name": name,
                "tag": None,
                "reference": f"Character Creation, p. {page} ({entry_name})",
                "kind": kind,
                "implemented": shape_id in IMPLEMENTED_SECTION_SHAPES,
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
            reason = VOCABULARY_REASONS.get(name, VOCABULARY_REASON)
            vocabulary.append({**record, "reason": reason})
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
    shapes.extend(sweep_classes(pdf))
    shapes.extend(sweep_feats(pdf))
    shapes.extend(sweep_toolbox(pdf))
    shapes.extend(sweep_origins(pdf))
    shapes.extend(sweep_playing(pdf))
    shapes.extend(sweep_chargen(pdf))

    stray = sorted({str(sh["kind"]) for sh in shapes} - KIND_VALUES)
    if stray:
        raise SystemExit(
            "kind values outside the closed vocabulary. Add them to KIND_VALUES "
            f"deliberately, or fix the typo: {stray}"
        )

    return {
        "schema_version": 1,
        "compat": 1,
        "source": {
            "document": "System Reference Document 5.2.1",
            "revision": "5.2.1",
            "published": "2025-05-01",
            # Derived from the shapes rather than hand-written. Five successive edits to
            # the literal version silently no-opped when the string was reflowed, leaving
            # it naming five sections while ten had been swept. A field that restates what
            # the data already says should be computed from the data.
            "section": "; ".join(sorted({str(sh["reference"]).split(", p. ")[0] for sh in shapes})),
        },
        # `unswept_sections` is structured rather than prose because the prose version of
        # this claim was wrong for eight builds and a substring check could not tell a
        # section named as *swept* from one named as *outstanding*. An empty list is the
        # only thing that may be read as complete coverage.
        "unswept_sections": [],
        "coverage_scope": (
            "All eleven of the document's rules sections are swept. "
            "`unswept_sections` is empty, which is the only form of this claim a guard "
            "can check, and `section` lists what the shapes actually cite. Complete "
            "coverage of the document is not the same as a correct inventory: the "
            "granularity and consolidation questions raised across the sweeps were "
            "settled by decision 0013."
        ),
        # The rules that decided what is a shape and what is content. They were applied
        # across eleven sweeps while living only in this file's comments, so a consumer of
        # the artifact could not see them and an auditor could not check them. Decision
        # 0013 put them in the data. Anything set aside cites one of these by id.
        "criteria": [
            {
                "id": "engine-held-state",
                "rule": (
                    "A shape names a mechanical change to state the engine holds. Character "
                    "progression that no engine operation resolves does not — level "
                    "advancement maps experience to a level, and the engine holds the level "
                    "rather than the mapping."
                ),
                "supersedes": (
                    "'No Ruling applies it', which asked whether the adjudication entry "
                    "point happened to touch the shape and so moved whenever that surface "
                    "grew."
                ),
                "decided_by": "0013, Q2",
            },
            {
                "id": "closed-named-set",
                "rule": (
                    "A closed named set with its own rules subsection is vocabulary. Worked "
                    "examples that compose shapes already inventoried are content."
                ),
                "admitted": [
                    "the eight weapon mastery properties",
                    "the four poison delivery types",
                ],
                "declined": [
                    "the nine environmental effects",
                    "the three magical contagions",
                ],
                "decided_by": "0013, Q4",
            },
            {
                "id": "mechanism-not-exemplar",
                "rule": (
                    "A shape is named for the mechanism it is, not for the feature that "
                    "exhibits it. Two features whose rules differ only in a parameter are "
                    "one shape."
                ),
                "decided_by": "0013, Q1, Q3 and Q5",
            },
            {
                "id": "one-thing-under-two-names",
                "rule": (
                    "A term whose entry states it denotes the same thing as an inventoried "
                    "term is one shape with it, however often the document uses the term. "
                    "The test is identity, not usage. Two ids resolving to one symbol is "
                    "the machine-checkable form of it; a similar name is not, which is why "
                    "a specialised namesake with its own resolver stays a shape."
                ),
                "decided_by": "0035",
            },
        ],
        "kind_values": sorted(KIND_VALUES),
        "shapes": shapes,
        "vocabulary": vocabulary,
    }


def main() -> None:
    args = sys.argv[1:]
    check = "--check" in args
    positional = [a for a in args if a != "--check"]
    if len(positional) != 1:
        raise SystemExit(__doc__)

    out = Path(__file__).resolve().parents[1] / "src/srd_rules_engine/data/effect_shapes.json"
    data = build(Path(positional[0]))
    rendered = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    total = len(data["shapes"])
    done = sum(1 for s in data["shapes"] if s["implemented"])
    summary = f"{total} shapes ({done} implemented), {len(data['vocabulary'])} vocabulary"

    if not check:
        out.write_text(rendered, encoding="utf-8")
        print(f"{out}: {summary}")
        return

    # `--check` exists because the writing form cannot tell you the inventory was already
    # right: it overwrites and leaves you to read a diff, which is a different question from
    # "is what shipped still what the document says" (#373).
    if not out.is_file():
        raise SystemExit(f"{out} does not exist, so there is nothing to check it against")
    if out.read_text(encoding="utf-8") != rendered:
        raise SystemExit(
            f"{out} disagrees with the document. Re-run without --check to regenerate it, "
            "read the diff, and say in the build line what moved"
        )
    print(f"  ok  {out.name} is what the document says: {summary}")


if __name__ == "__main__":
    main()
