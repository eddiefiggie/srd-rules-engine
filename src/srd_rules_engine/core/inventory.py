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
from srd_rules_engine.core.d20 import Advantage, TestKind

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
    kind: str
    reference: str
    implemented: bool
    tag: str | None = None


@dataclass(frozen=True)
class Inventory:
    """The published inventory. `scope` states what it does not yet cover, on purpose."""

    schema_version: int
    compat: int
    source: MappingProxyType[str, str]
    scope: str
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
        "",
        "Not yet implemented:",
    ]
    for shape in inv.unimplemented:
        lines.append(f"  [{shape.kind}] {shape.name} — {shape.reference}")
    return "\n".join(lines)
