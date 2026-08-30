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
        # Suffocation, once 0028 gave a level the rule id that caused it — p. 189's removal
        # is "all levels of Exhaustion it gained from suffocating", which a count could not
        # answer (#183).
        "suffocation": "core.hazards.suffocation_resolver",
        # Sight. Three shapes stay unclaimed and each for a stated reason, so that the next
        # sweep does not have to re-derive them: Truesight pierces illusions, transformations
        # and the Ethereal Plane besides the two piercings `can_see` enforces, and the entry's
        # substance is that list; Tremorsense pinpoints a location and p. 190 says outright it
        # "doesn't count as a form of sight", so nothing consumes its range; Telepathy needs
        # languages, which this engine does not model at all (#149).
        #
        # Lightly Obscured was the fourth until #138 gave p. 184's Disadvantage a consumer,
        # and this note went on saying it was produced by nothing for as long as nobody read
        # it — which is the same decay #228 found one block below.
        "blindsight": "core.state.EncounterState.can_see",
        "darkvision": "core.sight.effective_light",
        # Three `environment` shapes under the standard the sight sweep already used — **a
        # shape is claimed when the engine produces the consequence its entry states** — two
        # from #138, applied to the four the sweep grouped together and did not separate, and
        # the third from #228, which found the standard had never said where "its entry" ends.
        #
        # * p. 182, Heavily Obscured: "You have the Blinded condition **while trying to see
        #   something** in a Heavily Obscured space." Scoped to the attempt, so it is a
        #   relation between an observer and a target rather than a condition on a creature —
        #   which the verifier's own clause note settled before the code did. `can_see`
        #   answers exactly that relation and cites exactly that sentence. There is no
        #   wholesale Blinded to apply, so withholding one is not a gap.
        # * p. 180, Darkness: "An area of Darkness is Heavily Obscured." The whole entry, and
        #   the consequence flows: the mapping produces it and `can_see` acts on it.
        # * p. 11, Bright Light: "Bright Light lets most creatures see normally." **The
        #   mechanic is here rather than in the glossary entry**, whose whole body is "Bright
        #   Light is normal illumination" and whose `See also` points at *Playing the Game*.
        #   A shape's content is what the document states about it anywhere, not what its
        #   glossary paragraph states — the same rule under which `healing`, `save`, `damage`
        #   and `damage-types` were already claimed, and the one entry nobody had noticed it
        #   applied to (0033, #228). The consequence is a null one, and the mapping produces
        #   it: `OBSCUREMENT_BY_LIGHT[BRIGHT]` is `Obscurement.NONE`, `can_see` returns
        #   `CAN_SEE`, and `perception_of` says the light obscures nothing.
        "bright-light": "core.sight.OBSCUREMENT_BY_LIGHT",
        "darkness": "core.sight.OBSCUREMENT_BY_LIGHT",
        "heavily-obscured": "core.state.EncounterState.can_see",
        # #138's keystone, and the two shapes that were waiting behind it. p. 184's
        # Disadvantage was *derivable* from the day #150 filled the tables and **produced by
        # nothing** — so by this sweep's own standard neither resolved. A Wisdom (Perception)
        # check now reads the obscurement, which makes the consequence real:
        #
        # * `lightly-obscured` (p. 184) — the Disadvantage is applied to a real D20Test.
        # * `dim-light` (p. 181) — its whole entry is "an area with Dim Light is Lightly
        #   Obscured", and that classification is now read rather than computed and dropped.
        #
        # `bright-light` **is** here now, above — not because p. 178 gained a consequence,
        # but because the mechanic was never on p. 178. It is on p. 11, and the sweep that
        # wrote this note read the glossary entry as the shape's boundary (0033, #228).
        "lightly-obscured": "core.state.EncounterState.perception_of",
        "dim-light": "core.state.EncounterState.perception_of",
        # p. 188's Skill, whole: the association with an ability (p. 9's table) and the one
        # rule the entry states — proficiency adds the Proficiency Bonus to a check.
        #
        # `proficiency` is NOT here. p. 186 gives it four kinds — "a skill or saving throw
        # or with a weapon or tool" — and this engine models two, so claiming it would
        # report two of four as four. `expertise` is not here either: p. 182 doubles the
        # bonus for a class feature, and no class data ships.
        "skill": "core.state.Combatant.check_bonus",
        # p. 187's Ritual, whole: the prepared-and-tagged precondition, the 10 minutes, the
        # slot it does not expend, and the upcasting that therefore cannot happen (#19).
        "ritual": "core.spellcasting.ritual_cast",
        # Jumping. `high-jump` is NOT here: p. 183 adds one and a half times the creature's
        # height to what it can reach, and nothing models height — the arithmetic exists in
        # `core.position.high_jump_feet` and the entry says more than it computes.
        "jumping": "core.position.long_jump_feet",
        "long-jump": "core.hazards.landing_resolver",
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
        # p. 180's Damage Threshold, which is a DEFENCE and not a conditional effect (#214,
        # and 0032's sweep is what separated them). The entry says "has Immunity to all
        # damage unless...", so it is asked where Immunity is asked and against the instance
        # arriving — "an amount of damage from a single attack or effect", repeated as "that
        # entire instance". p. 17's Order of Application names three steps and not this one,
        # so the position is derived from the classification rather than read off an
        # ordering the document does not give.
        "damage-threshold": "core.damage.Defences.damage_threshold",
        "damage-modifier-no-stacking": "core.damage.Defences",
        # Weapon properties and the one mastery property nothing else gates (#16).
        "weapon-finesse": "core.combat.Weapon.finesse",
        "weapon-heavy": "core.combat.Weapon.heavy_disadvantage",
        "weapon-versatile": "core.equipment.Weapon.sides_in_use",
        # p. 90: "A Two-Handed weapon requires two hands when you attack with it." Claimed
        # since #263, when the requirement stopped being merely representable: a creature
        # holding more than its hands allow is refused at construction, so a two-handed
        # weapon cannot be wielded by a creature that cannot spare two hands. The path is the
        # invariant rather than a field, because the field alone enforced nothing.
        "weapon-two-handed": "core.state.Combatant.__post_init__",
        # p. 89: "When you take the Attack action on your turn and attack with a Light weapon,
        # you can make one extra attack as a Bonus Action later on the same turn." Claimed
        # since #270 — the offer, the different-weapon condition, and the damage rule whose
        # exception is the whole of it are all enforced, and `light_attacks_this_turn` is what
        # remembers the condition across the turn.
        "weapon-light": "core.read_surface._light_bonus_attacks",
        # p. 90, #284. The offer is bounded by the weapon's range rather than the wielder's
        # reach, the melee ability modifier survives the throw, and the weapon detaches
        # unplaced whether it hits or misses.
        "weapon-thrown": "core.read_surface._throwable",
        # p. 257, #289. One Action buys several rolls; the composition is the ruleset's.
        "multiattack": "core.state.EncounterState.attacks_remaining",
        # p. 90, #271. One shot per action used, which only bites once one action buys
        # several rolls — so this shape waited on `multiattack` rather than on Light.
        "weapon-loading": "core.state.EncounterState.has_fired_loading",
        # p. 89, #273. A count on `Carried`, one piece per attack, and the shot refused
        # without any. p. 89's recovery is #301 and needs a fight boundary.
        "weapon-ammunition": "core.state.EncounterState.with_ammunition_spent",
        # p. 13, p. 191, #288. One object interaction a turn, and the Action buys another.
        "utilize": "core.combat.object_interaction_resolver",
        # p. 188, #245. A held focus provides Material components that are neither consumed
        # nor costed, and the caster needs the feature p. 106 requires.
        "spellcasting-focus": "core.spellcasting.component_refusal",
        # p. 104, p. 177, #247, 0063. Training is held by item id because the categories are
        # content (0040 clause 2), and p. 104's prohibition is asked at the offer and at the
        # resolver. p. 177's other two drawbacks are disclosed (#367).
        "armor-training": "core.equipment.untrained_armour",
        # p. 90, #316. The tenth weapon property, and the one that was folded into p. 186's
        # glossary entry on the reasoning that the Glossary already defines the term. The
        # term, yes; the mechanic, no — so the fold let `reach`'s implemented flag claim a
        # rule that was not built. Both call sites take it: the attack's range bound and the
        # reach an Opportunity Attack is determined at.
        "weapon-reach": "core.equipment.Weapon.reach_in_use",
        # p. 188, #259, 0051. The category itself, carried by the creature and `None` when
        # nobody stated one. p. 188's entry folds three mechanics and the neighbouring
        # entries own the other two: the space a creature occupies is `occupied-space`
        # (p. 185) and an object's Hit Points are `breaking-objects` (p. 177), both still
        # unbuilt. What is claimed here is exactly what is built — a creature belongs to one
        # of six ordered categories, and rules can ask how far apart two of them are.
        "size": "core.size.Size",
        # p. 178, #259, 0051. The table, read at the carrying size p. 86 and p. 357 move one
        # row up. The Speed consequence is disclosed rather than applied — it turns on
        # dragging, lifting or pushing, and p. 12 leaves the subsystem to a person.
        "carrying-capacity": "core.size.carrying_capacity",
        # p. 182, #335, 0052. The rules a grapple follows "however a grapple is initiated" —
        # the escape check, the release, and the two endings nobody decides. Deliberately not
        # `unarmed-strike`: p. 190's three options are a separate entry and remain unbuilt,
        # and a flag over both would be 0046's defect again.
        "grappling": "core.grappling.escape_resolver",
        # p. 185, #382, 0072. The whole sentence: the trigger in `core.reactions`, the offer
        # and the Reaction spent in `loop.turn.TurnLoop.move`, the attack itself through the
        # one adjudication entry point.
        #
        # **Claimed only once the offer existed.** The trigger shipped on 2026-08-24 and this
        # entry did not, deliberately — `provocations` had no production caller and withheld
        # every result, so the shape was machinery rather than a resolved rule. R17's
        # inventory is what makes "full SRD 5.2 coverage" falsifiable, and a flag over a
        # detection nothing called would have been the exact overstatement it exists to
        # prevent (#381's five days are the evidence that nobody would have noticed).
        #
        # The named symbol is in `loop` rather than `core`, and that is the honest address: a
        # consumer calling `core.EncounterState.with_movement` directly provokes nothing, and
        # 0072 clause 6 ships that limit rather than implying the core resolves this alone.
        "opportunity-attacks": "loop.turn.TurnLoop.move",
        # p. 190, #335, 0053. All three options of the Unarmed Strike: Damage in `core.combat`
        # since the strike shipped, and Grapple and Shove here. Each is offered under its own
        # key, because p. 190 says "choose one of the following options for its effect".
        #
        # **Claimed with a disclosure rather than in spite of one.** p. 190 lets a Shove push
        # the target 5 feet away *or* knock it Prone, and only the Prone half is built — the
        # push is forced movement relative to another creature (#345). That is named at the
        # read surface as `shove-cannot-push-only-knock-prone`, which is the same arrangement
        # `carrying-capacity` ships under: the shape resolves, and the clause it does not
        # enforce is disclosed rather than left for a reader to find.
        "unarmed-strike": "core.unarmed_strike.unarmed_option_resolvers",
        # p. 90, #324, 0055. The eighth and last mastery property, and the only one that
        # needed a primitive rather than a rule: "push the creature up to 10 feet straight
        # away from yourself if it is Large or smaller".
        "mastery-push": "core.combat._push",
        # p. 169, 0055. Moving a creature by something other than itself, which twenty-odd
        # rules across spells, class features, a magic item and fourteen stat blocks share.
        # Thunderwave is the inventory's exemplar; p. 90's Push and p. 190's Shove are the
        # two callers built on it.
        "forced-movement": "core.forced_movement.displaced",
        "mastery-graze": "core.combat.Weapon.graze",
        # p. 90, #320. p. 89's extra attack, re-routed into the Attack action: offered under
        # its own key, costing nothing, and capped with the Bonus Action route at the one
        # extra attack p. 89 grants — which needed a per-turn record, because the Bonus Action
        # spend had been doing that job and a Nick attack spends nothing.
        "mastery-nick": "core.read_surface.nick_attack_key",
        # p. 90, #321. The hit records a save the engine's own DC derives from, and the loop
        # rolls it through the one adjudication entry point — the second occupant of the
        # forced-save queue 0048 generalised out of 0036's Concentration-shaped one.
        "mastery-topple": "core.topple.topple_resolver",
        # p. 90, #318 and #319. One mechanism, two sides: a token granted by a hit,
        # scoped and expiring differently for each, and spent by the roll it applies to.
        # p. 90, #323. A melee hit opens a second swing at a creature beside the first;
        # the offer measures both distances and the cap is its own, not p. 89's.
        "mastery-cleave": "core.read_surface.cleave_attack_key",
        "mastery-vex": "core.pending_rolls.PendingAdvantage",
        "mastery-sap": "core.pending_rolls.PendingAdvantage",
        # p. 90, #322. Sap's window and Vex's trigger, imposing a Speed reduction rather
        # than a d20 state — capped across sources, which is the clause a per-hit
        # reduction gets wrong.
        "mastery-slow": "core.position.slow_feet_taken",
        # Position, movement and range in feet (#17, #20).
        "speed": "core.position.Speeds.walk",
        "difficult-terrain": "core.position.movement_cost",
        "climbing": f"core.position.MovementMode.{MovementMode.CLIMB.name}",
        "swimming": f"core.position.MovementMode.{MovementMode.SWIM.name}",
        "crawling": f"core.position.MovementMode.{MovementMode.CRAWL.name}",
        # Claimed since #17 and wrong until #206: `with_movement` charged every mode
        # against the walking Speed, so p. 188's own worked example — fly 10, walk 10,
        # fly 20 more — was not expressible. A claimed clause is not a checked one, which
        # is the second time this instrument has misreported in as many builds.
        "split-movement": "core.state.EncounterState.with_movement",
        # The special speeds, and the one of them that is a rule rather than a number.
        #
        # `climb-speed` and `swim-speed` say only that the speed removes the extra cost of
        # climbing or swimming, which `movement_cost` has enforced since #17 — they were
        # unclaimed because nothing had read their glossary entries, not because anything
        # was missing. A count that was wrong in this direction is worth naming: the
        # instrument that measures this engine's gaps had two false ones.
        "climb-speed": "core.position.movement_cost",
        "swim-speed": "core.position.movement_cost",
        # p. 182's Flying is the whole of `falls_if_flying`, and `fly-speed` is the same
        # sentence read from the other side — "you can stay aloft until you land, fall, or
        # die" is the False branch. p. 183's Hover is its one exception.
        "flying": "core.state.Combatant.falls_if_flying",
        "fly-speed": "core.state.Combatant.falls_if_flying",
        "hover": "core.position.Speeds.hover",
        # `burrow-speed` is NOT here. p. 178 permits sand, earth, mud and ice and refuses
        # solid rock "unless the creature has a trait that allows it to do so" — a medium
        # this engine does not model and a trait it cannot read. `Speeds.burrow` carries the
        # number and `with_movement` refuses the mode without it; the entry's substance is
        # the restriction, and none of it is enforced.
        # p. 186's entry is the *default* — "a reach of 5 feet unless a rule says otherwise"
        # — and that is all this id has ever claimed. The rule that says otherwise is p. 90's
        # Reach property, filed separately below (#316).
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
        # `save` was here too, resolving to this same symbol — one mechanic counted twice
        # in both halves of the coverage figure. 0035 files it as vocabulary: p. 187 says it
        # is another name for a saving throw, so there was never a second thing to claim.
        "saving-throw": f"core.d20.TestKind.{TestKind.SAVE.name}",
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
        "initiative": "core.combat.initiative_order",
        "armor-class": "core.combat.Weapon",
        "hit-points": "core.state.Combatant.hit_points",
        "action": "core.adjudicate.EffectKind.ACTION_SPENT",
        "attack": "core.combat.attack_resolver",
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
