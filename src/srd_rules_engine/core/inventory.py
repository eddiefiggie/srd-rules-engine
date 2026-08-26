"""The effect-shape inventory (R17) and the coverage claim it makes falsifiable.

"Full SRD 5.2 coverage is the definition of done" is unfalsifiable on its own — there is
no way to tell a complete engine from one whose author stopped noticing gaps. This module
is the measuring stick: `src/srd_rules_engine/data/effect_shapes.json` enumerates the
distinct effect shapes SRD v5.2.1 defines, each marked implemented or not, and
`ENGINE_SHAPES` records which of them this engine actually resolves.

The two are checked against each other in both directions by
`tests/test_effect_shape_inventory.py`, because each direction catches a different lie:

* An engine resolving a shape the inventory does not list means the inventory is stale,
  and coverage is being measured against the wrong denominator.
* An inventory marking a shape implemented that `ENGINE_SHAPES` does not claim means the
  engine is reporting coverage it does not have — the failure R17 exists to prevent.

Entries are at **independently-failable** granularity: each of the fifteen conditions is
its own shape rather than one "apply a condition" family, so an engine that resolves Prone
and nothing else reports 1/15 instead of reporting conditions done.

Glossary entries that define a term without naming a mechanical change — "Alignment",
"Campaign" — are carried in `vocabulary` rather than dropped. Silent omission is what R17
names; an entry that was considered and set aside is a decision, and it stays visible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from types import MappingProxyType

from srd_rules_engine.core.adjudicate import EffectKind
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.d20 import Advantage, TestKind
from srd_rules_engine.core.position import MovementMode

_DATA_PACKAGE = "srd_rules_engine.data"
_DATA_FILE = "effect_shapes.json"


#: What this engine can actually resolve, keyed by inventory shape id.
#:
#: This is a claim, and the guard test makes it an expensive one to get wrong. Adding an
#: id here without the engine resolving it fails the build; so does resolving something
#: whose id is absent from the inventory. Membership is therefore edited when capability
#: changes, never to make a test pass.
ENGINE_SHAPES: MappingProxyType[str, str] = MappingProxyType(
    {
        # The unified D20 test primitive (U8).
        "d20-test": "core.d20.D20Test",
        # What a natural 20 or 1 means, and the score derived without rolling (#15).
        "critical-hit": "core.d20.Critical.HIT",
        "natural-20-auto-hit": "core.d20._critical",
        "advantage-does-not-stack": "core.d20.D20Test.has_advantage",
        "passive-perception": "core.d20.passive_score",
        # The one hazard that fires on no occasion, so it needed no phase (#140, 0027
        # clause 7). The other four are blocked on occasions this engine does not have.
        "falling": "core.hazards.falling_resolver",
        # Burning fires at the turn's start, the phase 0027 clauses 1-4 built. The other
        # three hazards each inflict an Exhaustion level, which nothing can raise through a
        # ruling (#178) — that, not the occasion, is what blocks them now.
        "burning": "core.hazards.burning_resolver",
        # Death saving throws and what follows them (#15).
        "death-saving-throw": "core.death.death_save_resolver",
        "stable": "core.state.DeathSaves.stable",
        # Modifiers applied to a d20 test, and the two ways a resolved one can move (#15).
        "numeric-bonus": "core.combat.Weapon.bonus",
        "die-applied-to-a-roll": "core.d20.adjust_roll",
        "die-replacement": "core.d20.replace_die",
        "failed-test-overridden-to-success": "core.d20.override_to_success",
        # Damage application: the types and what the defences do to an amount (#16).
        "damage-types": "core.damage.DamageType",
        "resistance": "core.damage.Defences.resistances",
        "vulnerability": "core.damage.Defences.vulnerabilities",
        "damage-application-order": "core.damage.after_defences",
        "damage-modifier-no-stacking": "core.damage.Defences",
        # Weapon properties and the one mastery property nothing else gates (#16).
        "weapon-finesse": "core.combat.Weapon.finesse",
        "weapon-heavy": "core.combat.Weapon.heavy_disadvantage",
        "weapon-versatile": "core.combat.Weapon.sides_in_use",
        "mastery-graze": "core.combat.Weapon.graze",
        # Position, movement and range in feet (#17, #20).
        "speed": "core.position.Speeds.walk",
        "difficult-terrain": "core.position.movement_cost",
        "climbing": f"core.position.MovementMode.{MovementMode.CLIMB.name}",
        "swimming": f"core.position.MovementMode.{MovementMode.SWIM.name}",
        "crawling": f"core.position.MovementMode.{MovementMode.CRAWL.name}",
        "split-movement": "core.state.EncounterState.with_movement",
        "reach": "core.position.DEFAULT_REACH_FEET",
        "weapon-range": "core.combat.Weapon.normal_range",
        # The six areas of effect, as unobstructed volume (#20, and #91 for what is missing).
        "area-of-effect": "core.areas.Area",
        "sphere": "core.areas.Sphere",
        "cube": "core.areas.Cube",
        "cylinder": "core.areas.Cylinder",
        "cone": "core.areas.Cone",
        "line": "core.areas.Line",
        "emanation": "core.areas.Emanation",
        # The fifteen conditions, with their mechanical effects attached (#18).
        **{c.value: f"core.conditions.Condition.{c.name}" for c in Condition},
        # The action economy: what may be spent and when it refreshes (#16).
        "bonus-action": "core.actions.ActionKind.BONUS_ACTION",
        "reaction": "core.actions.ActionKind.REACTION",
        "dash": "core.actions.ActionBudget.dashed",
        "dodge": "core.actions.dodging",
        "disengage": "core.actions.ActionBudget.disengaged",
        # Spell slots, save DCs, spell attacks and Concentration (#19).
        "spell-slot": "core.spellcasting.SpellSlots",
        "regain-spell-slots": "core.spellcasting.SpellSlots.restored",
        "cantrip": "core.spellcasting.CANTRIP_LEVEL",
        "concentration": "core.spellcasting.Concentration",
        "spell-attack": "core.spellcasting.spell_attack_modifier",
        "ability-check": f"core.d20.TestKind.{TestKind.CHECK.name}",
        "saving-throw": f"core.d20.TestKind.{TestKind.SAVE.name}",
        "save": f"core.d20.TestKind.{TestKind.SAVE.name}",
        "attack-roll": f"core.d20.TestKind.{TestKind.ATTACK.name}",
        "difficulty-class": "core.d20.D20Test.target",
        "advantage": f"core.d20.Advantage.{Advantage.ADVANTAGE.name}",
        "disadvantage": f"core.d20.Advantage.{Advantage.DISADVANTAGE.name}",
        "ability-score-and-modifier": "core.d20.Modifier",
        # Effects a ruling applies (U9).
        "damage": f"core.adjudicate.EffectKind.{EffectKind.DAMAGE.name}",
        "healing": f"core.adjudicate.EffectKind.{EffectKind.HEALING.name}",
        "damage-roll": "core.adjudicate.DamageDice",
        # Combat (U12).
        "initiative": "core.combat.initiative",
        "armor-class": "core.combat.Weapon",
        "hit-points": "core.combat.hit_points",
        "action": "core.state.action",
        "attack": "core.combat.attack",
    }
)


@dataclass(frozen=True)
class Shape:
    """One distinct effect shape SRD v5.2.1 defines, and whether this engine resolves it."""

    id: str
    name: str
    #: Which part of the rules this shape is filed under, for measuring coverage — **not**
    #: a claim about what it does (decision 0019). The behaviour lives in typed code:
    #: `ConditionEffects` says what Prone changes, not this label. Where a shape could be
    #: filed two ways, it goes under the subsystem that implements it, or would.
    #:
    #: Nothing in the engine branches on it, and a guard in
    #: `tests/test_effect_shape_inventory.py` keeps that true.
    kind: str
    reference: str
    implemented: bool
    tag: str | None = None


@dataclass(frozen=True)
class Inventory:
    """The published inventory.

    `scope` reads for a human; `unswept_sections` is the machine-readable form of the same
    claim and is the one a guard checks. Both exist because the prose alone was wrong for
    eight builds: a substring check on it could not distinguish a section named as *swept*
    from one named as *still outstanding*. An empty `unswept_sections` is the only thing
    that may be read as complete coverage.
    """

    schema_version: int
    compat: int
    source: MappingProxyType[str, str]
    scope: str
    unswept_sections: tuple[str, ...]
    shapes: tuple[Shape, ...]
    vocabulary: tuple[str, ...]

    @property
    def implemented(self) -> tuple[Shape, ...]:
        return tuple(s for s in self.shapes if s.implemented)

    @property
    def unimplemented(self) -> tuple[Shape, ...]:
        """The disclosure surface. R17 requires these be shown, not quietly omitted."""
        return tuple(s for s in self.shapes if not s.implemented)

    def by_id(self, shape_id: str) -> Shape | None:
        return next((s for s in self.shapes if s.id == shape_id), None)


@lru_cache(maxsize=1)
def load_inventory() -> Inventory:
    """Read the published inventory. Cached — the file ships with the package and is fixed."""
    raw = json.loads(
        resources.files(_DATA_PACKAGE).joinpath(_DATA_FILE).read_text(encoding="utf-8")
    )
    shapes = tuple(
        Shape(
            id=s["id"],
            name=s["name"],
            kind=s["kind"],
            reference=s["reference"],
            implemented=s["implemented"],
            tag=s.get("tag"),
        )
        for s in raw["shapes"]
    )
    return Inventory(
        schema_version=raw["schema_version"],
        compat=raw["compat"],
        source=MappingProxyType(dict(raw["source"])),
        scope=raw["coverage_scope"],
        unswept_sections=tuple(raw["unswept_sections"]),
        shapes=shapes,
        vocabulary=tuple(v["name"] for v in raw["vocabulary"]),
    )


def coverage_report() -> str:
    """A plain-text statement of what does not resolve yet, for a human to read."""
    inv = load_inventory()
    lines = [
        f"{inv.source['document']} effect-shape coverage: "
        f"{len(inv.implemented)}/{len(inv.shapes)} shapes resolve.",
        f"Scope: {inv.scope}",
        (
            "Sections still unswept: " + ", ".join(inv.unswept_sections)
            if inv.unswept_sections
            else "Every section of the document has been swept."
        ),
        "",
        "Not yet implemented:",
    ]
    for shape in inv.unimplemented:
        lines.append(f"  [{shape.kind}] {shape.name} — {shape.reference}")
    return "\n".join(lines)
