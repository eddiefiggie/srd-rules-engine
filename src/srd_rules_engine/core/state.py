"""Mechanical encounter state, with a generation that cannot be forgotten.

R9 requires the mechanical state — hit points, initiative order, whose turn it is — to
have a named owner and a stated lifetime. This is that owner.

**The state is immutable, and every successor is produced by one private method that
adds one to the generation.** A mutator therefore cannot forget to bump it: it has no
way to construct a successor without going through `_evolve`, and `_evolve` does not
accept a generation to override. That matters more than it looks, because the failure
direction is quiet — a mutation that does not bump would leave a read token from before
it looking current, and the alternatives verdict would read `verified-fresh` on a claim
made against state that has since changed.

Immutability also settles R19's non-mutation requirement structurally rather than by
convention: the read surface is handed a state it could not modify if it tried.

M1 carries only what the vertical slice needs — hit points, armour class, ability
scores, proficiency, initiative order, and the turn. Conditions, movement in feet, and
spell slots arrive with the units that implement them, not before.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from types import MappingProxyType
from typing import Any, Final

from srd_rules_engine.core.actions import ActionBudget, ActionKind, dodging, still_dodging
from srd_rules_engine.core.areas import Area
from srd_rules_engine.core.clock import (
    STABLE_RECOVERY_HIT_POINTS,
    Clock,
    stable_recovery_minute,
)
from srd_rules_engine.core.conditions import (
    MAX_EXHAUSTION,
    Condition,
    Conditions,
    Grapple,
    save_ends_rule_id,
)
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.damage import (
    DamageOutcome,
    DamageType,
    Defences,
    after_defences,
)
from srd_rules_engine.core.duration import (
    Duration,
    DurationKind,
    SaveEnds,
    SpanUnit,
    StatedSpan,
    rounds_in_minutes,
)
from srd_rules_engine.core.equipment import (
    ArmourClassBase,
    Carriage,
    Carried,
    DetachedObject,
    Item,
    Multiattack,
    Weapon,
    carried_weight,
    free_hands,
    items_in,
)
from srd_rules_engine.core.obstructions import Obstruction, blocking, line_is_blocked
from srd_rules_engine.core.pending_rolls import PendingAdvantage, is_live
from srd_rules_engine.core.position import (
    DEFAULT_REACH_FEET,
    MovementMode,
    Position,
    SpeedReduction,
    Speeds,
    distance_feet,
    movement_cost,
    slow_feet_taken,
    squared_distance,
)
from srd_rules_engine.core.sight import (
    Lighting,
    Obscurement,
    Sense,
    Senses,
    Sight,
    Visibility,
    obscurement_at,
)
from srd_rules_engine.core.size import (
    HAULING_SPEED_CAP_FEET,
    CarryingCapacity,
    Size,
    carried_without_extra_cost,
    carrying_capacity,
    dehydrated,
    one_size_larger_for_carrying,
    undernourished,
)
from srd_rules_engine.core.skills import SKILL_ABILITY, PerceptionCheck, Skill
from srd_rules_engine.core.spellcasting import (
    CONCENTRATION_RULE_ID,
    CONCENTRATION_SAVE_ABILITY,
    Concentration,
    LongCast,
    Spell,
    SpellSlots,
    concentration_save,
)
from srd_rules_engine.core.turn_span import TurnBounded

#: p. 17: "On your third success, you become Stable... On your third failure, you die."
DEATH_SAVE_THRESHOLD: Final = 3


class ObligationOutstanding(Exception):
    """0023 clause 6. The departing creature owes a repeated save this turn (p. 63)."""


#: The rule ids the two built hazards are enumerated and recorded under.
#:
#: They live here rather than in `core.hazards` for the reason `Hazards` itself does, and the
#: reason `save_ends_rule_id` lives in `core.conditions`: an id that **keys state** has to sit
#: where state can reach it, and `core.hazards` imports `core.adjudicate`, which imports this
#: module. Since 0028 clause 1 a Suffocation level literally carries `SUFFOCATION_RULE_ID`,
#: so this is not a naming convenience — it is the value in the field.
#:
#: `core.hazards` re-exports both, which is where a reader looks for them.
BURNING_RULE_ID: Final = "burning"
SUFFOCATION_RULE_ID: Final = "suffocation"

#: The two hazards whose Exhaustion the document puts beyond the general rule's reach, named
#: here ahead of the hazards themselves (#140) because 0028 clause 3 is about what a Long
#: Rest may *not* take and that is testable now.
#:
#: p. 181: "Exhaustion caused by dehydration can't be removed until the creature drinks the
#: full amount of water required for a day." p. 185 says the same for food. Neither hazard is
#: built; when one is, its rule id must be this string or the lock silently stops applying —
#: `tests/test_long_rest.py` is where that would be caught.
DEHYDRATION_RULE_ID: Final = "dehydration"
MALNUTRITION_RULE_ID: Final = "malnutrition"

#: p. 185: "must succeed on a **DC 10** Constitution saving throw". Stated outright by the
#: document rather than derived from anything, which is unusual enough to name — every other
#: forced save in this engine computes its DC when the trigger fires (0036 clause 4).
MALNUTRITION_SAVE_DC: Final = 10

#: 0028 clause 3. A level from one of these is **invisible** to the general removal rule
#: rather than subtracted from it: a creature holding only these finishes a Long Rest and
#: loses nothing, which is what pp. 181 and 185 say. Removing one and re-applying the lock
#: reports the same total by a route that is wrong for the next rule to read.
LOCKED_EXHAUSTION_RULES: Final = frozenset({DEHYDRATION_RULE_ID, MALNUTRITION_RULE_ID})


@dataclass(frozen=True)
class Hazards:
    """Ongoing hazards a creature is subject to (0027 clause 5).

    **Not `Conditions`, deliberately.** "This creature is Burning" is not one of the fifteen
    SRD conditions, and filing it there would corrupt the one structure whose completeness is
    a checked claim — 15/15 means fifteen, and a sixteenth member that is not in the glossary
    makes that number a different number.

    It lives here rather than in `core.hazards` for the reason `DeathSaves` lives here rather
    than in `core.death`: this is the state, that is the rules, and `core.hazards` imports
    `core.adjudicate`, which imports this module. The value object has to sit below both.

    `burning` and `suffocating`. The second waited on
    [#178](https://github.com/eddiefiggie/srd-rules-engine/issues/178) — Suffocation inflicts
    Exhaustion *levels*, and nothing could raise one through a ruling until that closed. It
    arrived with its consumer rather than ahead of one, `core.hazards.suffocation_resolver`,
    so it is not the stub-with-a-citation this docstring declined to add.

    **Nothing applies or removes this through a ruling yet.** p. 178 puts fire out when it is
    "doused, submerged, or suffocated", or by an action that also makes the creature Prone —
    the first three are narrative facts the engine cannot observe and the fourth needs an
    action to spend. So a caller sets it, which is the same disclosed gap `core.death` carries
    for the Unconscious condition, and it is a real one rather than a technicality: a creature
    that cannot stop burning burns until it dies.
    """

    burning: bool = False
    #: p. 189. Set when a creature "runs out of breath or is choking" — both narrative facts
    #: this engine cannot observe, so a caller says so, as it does for `burning`.
    suffocating: bool = False


@dataclass(frozen=True)
class DeathSaves:
    """How close a creature at 0 hit points is to either end of it.

    Both counts are kept, because p. 17 says "the successes and failures don't need to be
    consecutive; keep track of both until you collect three of a kind". A single
    net-progress integer would resolve two successes and two failures to zero, which is a
    creature one roll from death reported as untouched.
    """

    successes: int = 0
    failures: int = 0
    stable: bool = False
    dead: bool = False
    #: The campaign minute this creature regains 1 hit point, if it is Stable and stays
    #: unhealed (p. 18). Rolled once when it becomes Stable — see `core.clock` for why it
    #: is not rolled on demand — and `None` for a creature that is not Stable.
    #:
    #: It lives here rather than beside the clock so that p. 18's condition holds
    #: structurally: the rule applies to a Stable creature *that isn't healed*, and
    #: `with_healing` resets these counts wholesale, so healing voids the deadline by
    #: clearing the object it lives in rather than by remembering to check.
    recovers_at_minute: int | None = None

    def __post_init__(self) -> None:
        if self.successes < 0 or self.failures < 0:
            raise ValueError("death save counts do not go backwards; they reset to zero")
        if self.recovers_at_minute is not None and not self.stable:
            raise ValueError("only a Stable creature has a recovery time (p. 18)")

    @property
    def is_resolved(self) -> bool:
        return self.stable or self.dead


#: The modes no creature performs without the matching special speed (pp. 178, 182).
#:
#: Climbing, swimming and crawling are each priced for a creature that lacks the speed —
#: "1 extra foot (2 extra feet in Difficult Terrain)" — so anyone may do them slowly. The
#: SRD prices neither flying nor burrowing that way, and 0030 clause 1 settles what to make
#: of the silence: granting a move the rules never granted manufactures movement, refusing
#: it cannot.
_SPEED_ONLY_MODES: Final = (MovementMode.FLY, MovementMode.BURROW)


def ended_by_circumstance(state: EncounterState) -> tuple[str, ...]:
    """Ids of creatures whose grapple has ended for a reason nobody decides (p. 182).

    > The condition also ends if the grappler has the Incapacitated condition or if the
    > distance between the Grappled target and the grappler exceeds the grapple's range.

    **Derived, not swept.** 0050 put p. 90's Slow reduction on the creature and retired it on
    a turn boundary, because the thing it modifies is read through a property that sees no
    encounter. This is the opposite case in both halves: the question needs *two* creatures,
    so it can only be asked where both are, and its answer does not wait for a turn boundary —
    a creature whose grappler is knocked unconscious mid-turn is not grappled from that
    moment. So it is asked wherever state settles rather than only when the turn advances.

    Each of the three refusals below leaves the condition **held**, which is 0030 clause 1's
    direction: lifting a grapple on a fact the engine had to guess would remove a condition
    the rules did not remove, while declining leaves the state a ruleset stated.
    """
    ended: list[str] = []
    for creature in state.combatants:
        if Condition.GRAPPLED not in creature.conditions.held:
            continue
        grappler_id = creature.conditions.grappler_id
        if grappler_id is None:
            # Nobody said who is grappling, so neither ending can be evaluated: there is no
            # creature to be Incapacitated and none to measure a distance to.
            continue
        grappler = next((c for c in state.combatants if c.id == grappler_id), None)
        if grappler is None:
            # The grappler has left the encounter. p. 182 does not say what becomes of the
            # grapple, and inventing a release is inventing an outcome.
            continue
        if Condition.INCAPACITATED in grappler.conditions.held:
            ended.append(creature.id)
            continue
        if _out_of_range(creature, grappler):
            ended.append(creature.id)
    return tuple(ended)


def _out_of_range(creature: Combatant, grappler: Combatant) -> bool:
    """Whether the two have been separated by more than the grapple's range (p. 182).

    `False` whenever the question cannot be asked — an unstated range, or an encounter
    tracking no positions. p. 182 measures a distance and an engine with no distance to
    measure has not found the creatures close enough; it has found nothing.
    """
    grapple = creature.conditions.grapple
    if grapple is None or grapple.range_feet is None:
        return False
    if creature.position is None or grappler.position is None:
        return False
    return distance_feet(creature.position, grappler.position) > grapple.range_feet


def grapples_released(state: EncounterState) -> EncounterState:
    """`state` with every grapple p. 182 has already ended lifted from it.

    The one function both call sites share, for the reason 0050 gave for sharing one sweep:
    two implementations of "has this grapple ended" is how one gets remembered and the other
    forgotten.
    """
    ending = ended_by_circumstance(state)
    for creature_id in ending:
        state = state.with_condition_ended(creature_id, Condition.GRAPPLED)
    return state


def _swept(state: EncounterState) -> EncounterState:
    """Drop pending roll tokens the advanced turn has passed the expiry of (0049).

    **Run against the state the turn advanced *to*.** Liveness is a question about where the
    encounter has reached, so asking it before the index moves answers about the turn that
    just ended — which leaves every token alive exactly one turn too long. The rule is
    unaffected either way, because `live_pending_advantage` is what a roll consults; this is
    the hygiene that keeps the queue from growing, and a hygiene step that lags is a queue
    that never empties.
    """
    order = tuple(c.id for c in state.combatants)

    def alive(token: TurnBounded) -> bool:
        return is_live(
            token,
            round_number=state.round_number,
            turn_index=state.turn_index,
            order=order,
        )

    # p. 182's grapple endings retire here as well, through the one function both call sites
    # share (0050's rule read forwards). The turn boundary is not where they are *decided* —
    # `grapples_released` is called wherever state settles — but a sweep that skipped them
    # would leave the one state change nothing else triggers: a grappler who ended its turn
    # Incapacitated by a condition that arrived with no ruling behind it.
    state = grapples_released(state)
    live = tuple(token for token in state.pending_advantage if alive(token))
    # p. 90's Slow retires here too, through the **same** function (#322, 0050). Its liveness
    # is applied rather than derived — `Combatant.effective_speeds` sees no encounter — so the
    # sweep is the rule for it and only hygiene for the advantage above. Sharing one function
    # is what keeps a sweep from being remembered for one and forgotten for the other.
    slowed = tuple(
        replace(c, speed_reductions=kept)
        for c in state.combatants
        if (kept := tuple(r for r in c.speed_reductions if alive(r))) != c.speed_reductions
    )
    if len(live) == len(state.pending_advantage) and not slowed:
        return state
    combatants = tuple(next((s2 for s2 in slowed if s2.id == c.id), c) for c in state.combatants)
    return state._evolve(pending_advantage=live, combatants=combatants)


@dataclass(frozen=True)
class ForcedSave:
    """One save a creature owes and has not rolled, whatever compelled it (0048).

    **Generalised from `ConcentrationDebt`** (0036 clause 3), which held p. 179's damage
    amount and nothing else. 0036 decided the *cardinality* — one debt per triggering
    instance, deliberately not `discharged`'s once-per-turn keying — and that cardinality is
    the whole of what makes two forced saves the same mechanism. p. 90's Topple owes one save
    per hit; p. 179's Concentration owes one per damage instance. Same shape, so one
    structure, which is 0036 clause 3's own rule read forwards.

    **The DC and its derivation are computed when the trigger fires**, not when the save is
    rolled. 0036 clause 4 gave the reason for the amount and it reaches further than the
    amount: by the time the loop discharges the save, the state the DC came from has moved.
    Concentration's DC is a function of *that* instance's damage and the creature's hit
    points have since changed; Topple's is a function of the ability the attacker chose for
    *that* attack roll, which nothing records afterwards. Neither is recoverable.

    It is also what keeps R4 intact: the resolver closes over numbers the **engine** recorded
    when the trigger fired, never ones a caller supplied.

    `dc_basis` travels with the DC because a target number without its derivation is half a
    ruling (R30). It is the engine's own sentence, built where the rule is known.
    """

    combatant_id: str
    #: Which rule compelled it, and therefore which resolver rolls it. The rule id carries
    #: the selection for the reason `save_ends` gives: the declaration's label is prose, and
    #: an engine reading prose to choose a mechanic is the capability being removed.
    rule_id: str
    ability: str
    dc: int
    dc_basis: str
    #: What the obligation says it is. Written where the trigger fired, because that is the
    #: only place that knows what happened — the loop sees a debt, not an attack.
    label: str
    #: The abilities the **target** may choose between, when a rule gives it the choice
    #: (0053). Empty for every save the document names outright, which is all of them but
    #: two: p. 179's Concentration and p. 90's Topple each state one ability, and neither is
    #: touched by this field existing.
    #:
    #: > p. 190: The target must succeed on a **Strength or Dexterity saving throw (it chooses
    #: > which)**...
    #:
    #: Two hits in the whole document, both on p. 190 — Grapple and Shove, the same sentence
    #: twice. When this is non-empty, `ability` is empty until the choice arrives and the save
    #: is **unsettled**: no resolver may roll it, because rolling it would mean the engine
    #: picked, which is the one thing p. 190 gives to the creature.
    ability_choices: tuple[str, ...] = ()
    #: Who compelled it, for a rule whose *consequence* turns on the source (0053).
    #:
    #: `ForcedSave` otherwise holds what the **save** needs — a DC, its derivation, an
    #: ability. This is what the **condition** needs: p. 190's Grapple applies Grappled, and
    #: p. 182 gives that condition "Disadvantage on attack rolls against any target other than
    #: **the grappler**". The save is rolled by the target and resolved on its own
    #: declaration, so by then the attacker's identity is recoverable from nothing else.
    #:
    #: `None` for p. 179's Concentration and p. 90's Topple, whose consequences name nobody.
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.dc < 1:
            raise ValueError(f"a save DC is a positive target number, not {self.dc}")
        if not self.dc_basis:
            raise ValueError(
                "a forced save carries the derivation of its DC. A target number without one "
                "is a number the reader cannot check, which is what R30 exists to refuse"
            )
        if self.ability_choices:
            if len(set(self.ability_choices)) != len(self.ability_choices):
                raise ValueError(
                    f"a choice of saves offers each ability once, and {self.ability_choices} "
                    "repeats one. A menu with a duplicate is a menu that cannot say what was "
                    "picked"
                )
            if len(self.ability_choices) < 2:
                raise ValueError(
                    "a choice between fewer than two abilities is not a choice. A save the "
                    "document names outright carries no `ability_choices` at all"
                )
            if self.ability and self.ability not in self.ability_choices:
                raise ValueError(
                    f"{self.ability!r} was settled on a save that offers "
                    f"{self.ability_choices}. The chosen ability has to be one the rule "
                    "offered, or the choice was not the creature's"
                )
        elif not self.ability:
            raise ValueError(
                "a forced save with no choice states its ability. An empty one means the "
                "engine would pick, which is exactly what `ability_choices` exists to prevent"
            )

    @property
    def is_settled(self) -> bool:
        """Whether the ability to roll is known.

        Unsettled means a creature owes the engine a choice — never that the engine may make
        one. `TurnLoop` asks; `Adjudicator` refuses.
        """
        return bool(self.ability)

    def with_ability(self, ability: str) -> ForcedSave:
        """This save with the target's choice settled (0053 clause 3)."""
        if ability not in self.ability_choices:
            raise ValueError(
                f"{ability!r} is not one of the abilities this save offered "
                f"({', '.join(self.ability_choices) or 'none'}). p. 190 lets the target choose "
                "between the two the rule names, and nothing else"
            )
        return replace(self, ability=ability)


@dataclass(frozen=True)
class Combatant:
    """One participant's mechanical state. Narrative facts live behind the memory port."""

    id: str
    name: str
    hit_points: int
    max_hit_points: int
    armour_class: int
    abilities: Mapping[str, int]
    proficiency_bonus: int
    initiative: int | None = None
    #: p. 17, "Monster Death": a monster "dies the instant it drops to 0 Hit Points",
    #: while a player character makes Death Saving Throws. The two outcomes are different
    #: rules, so the engine has to know which it is holding. Defaults to the monster
    #: reading, because the product is solo play with exactly one player character and a
    #: combatant nobody marked is far more likely to be the bear.
    is_player_character: bool = False
    #: What this creature resists, is vulnerable to, and is immune to (p. 17).
    defences: Defences = field(default_factory=Defences)
    #: Where it is, in feet. `None` for an encounter that tracks no positions — the read
    #: surface then simply cannot answer a range question, which is the honest result.
    position: Position | None = None
    speeds: Speeds = field(default_factory=Speeds)
    #: Special senses, each a range in feet (0025 clause 3). The default is a creature with
    #: none, which is not the same as a creature whose senses nobody recorded — the engine
    #: cannot tell those apart and does not pretend to.
    senses: Senses = field(default_factory=Senses)
    #: Ongoing hazards (0027 clause 5). Not conditions, and not filed among them.
    hazards: Hazards = field(default_factory=Hazards)
    #: p. 186: "A creature has a reach of 5 feet unless a rule says otherwise."
    reach: int = DEFAULT_REACH_FEET
    #: Speed reductions standing over this creature (p. 90, #322, 0050).
    #:
    #: **On the creature rather than on the encounter**, unlike 0049's advantage tokens, and
    #: the reason is the reading path. Speed is read through `effective_speeds`, a `Combatant`
    #: property that by design sees no encounter — so deriving liveness here would mean
    #: threading the turn order into every reader of a creature's Speed, and putting
    #: turn-order knowledge inside a property about one creature. `conditions` already
    #: modifies Speed from exactly this seam and is retired by a turn phase; this joins them.
    #:
    #: The cost is that liveness is **applied rather than derived**, which 0049 clause 3
    #: declined for advantage. The failure directions differ: a missed sweep there would grant
    #: Advantage past its window, and here it leaves a creature slowed past its own. Neither
    #: is good and only the first invents something. `EncounterState._swept` retires both
    #: through one function so a sweep cannot be missed for one and not the other.
    speed_reductions: tuple[SpeedReduction, ...] = ()
    #: Movement spent this turn. Reset when the turn advances, not carried.
    movement_used: int = 0
    #: Skills this creature is proficient in (p. 188, #138). A set, because proficiency is
    #: held or not — p. 182's Expertise doubles the bonus and is a class feature this engine
    #: ships no data for, so a count would represent something the document does not give.
    skills: frozenset[Skill] = frozenset()
    #: Active conditions, with implication already resolved (R14, R18).
    conditions: Conditions = field(default_factory=Conditions)
    #: What is left of the action economy this turn (p. 176-177, 186).
    actions: ActionBudget = field(default_factory=ActionBudget)
    #: Spell slots, for a creature that has any. `None` for one that does not, which is a
    #: different thing from having none left.
    slots: SpellSlots | None = None
    #: What this creature has, and where (0039 clauses 1 and 3). Ruleset data, carried by the
    #: creature, for the reason `spells` is below: legality is a fact about the creature and
    #: `legal_actions(state, actor_id)` may not take a second argument (0026 clause 1).
    equipment: tuple[Carried, ...] = ()
    #: How many attack rolls the Attack action buys, or `None` for a creature that gets one
    #: (p. 257, 0043 clauses 1-2). Ruleset data on the creature, for the reason `equipment`
    #: and `spells` are: `legal_actions(state, actor_id)` may not take a second argument.
    #:
    #: `None` is the ordinary creature and the pre-existing behaviour — one Action, one attack
    #: roll — so a ruleset that says nothing keeps exactly what it had.
    multiattack: Multiattack | None = None
    #: Which weapons this creature is proficient with, by item id (p. 89, 0040 clause 2).
    #:
    #: "Anyone can wield a weapon, but **you** must have proficiency with it to add your
    #: Proficiency Bonus to an attack roll you make with it." A fact about the wielder, and it
    #: was a field on `Weapon` until #258 — which worked exactly while a weapon belonged to
    #: one resolver and therefore to one creature. Two creatures holding the same kind of
    #: weapon, or one picking up another's, broke it toward *granting* a bonus.
    #:
    #: **By id, because the categories are content.** p. 89 grants proficiency by category —
    #: Simple, Martial — and the categories live in the weapons table this repository does not
    #: ship (R31). So the engine holds the resolved relation and a ruleset that knows the
    #: categories expands them into ids, the same split under which no spell list ships.
    weapon_proficiencies: frozenset[str] = frozenset()
    #: Which weapons this creature may use the **mastery property** of, by item id (p. 90,
    #: 0047 clause 1).
    #:
    #: p. 90 opens the Mastery Properties section by gating every one of them: a mastery
    #: property is "usable only by a character who has a feature, such as Weapon Mastery,
    #: **that unlocks the property for the character**". p. 89 says it again in the Weapons
    #: table's column list — "To use that property, you must have a feature that lets you use
    #: it."
    #:
    #: **A separate relation from `weapon_proficiencies`, not a subset of it.** The five
    #: classes that ship the feature do not agree on whether proficiency is required: Paladin
    #: (p. 54), Ranger (p. 59) and Rogue (p. 62) each say "of your choice **with which you
    #: have proficiency**", while Barbarian (p. 29) says "two kinds of Simple or Martial Melee
    #: weapons of your choice" and Fighter (p. 48) "three kinds of Simple or Martial weapons
    #: of your choice", neither mentioning proficiency. Deriving one from the other would be
    #: right for three classes and invented for two, and it is smaller than proficiency in
    #: every case — a Fighter is proficient with far more weapons than the three it masters.
    #:
    #: **By id, and the source of the permission is deliberately not held.** p. 90 writes
    #: "**such as** Weapon Mastery", leaving the set of unlocking features open, and the
    #: features themselves are class content this repository does not ship (R31). So the
    #: engine holds the resolved relation and a ruleset that knows the class tables expands
    #: them into ids — the same split as `weapon_proficiencies` under 0040 clause 2, and as
    #: `may_substitute_focus` above.
    #:
    #: **Empty by default, and that is the answer for every monster too.** p. 89 gives
    #: proficiency an explicit monster rule — "A monster is proficient with any weapon in its
    #: stat block" — and p. 90 gives mastery no parallel. It says "a **character**". Reading
    #: one across from the other would grant every monster in the bestiary the mastery
    #: property of everything it holds, on the engine's own authority (R31).
    mastery_weapons: frozenset[str] = frozenset()
    #: Whether this creature may substitute a Spellcasting Focus for a spell's Material
    #: components (p. 105, p. 188, #245).
    #:
    #: **A fact about the caster, not about the focus.** p. 106: "a spellcaster can substitute
    #: a Spellcasting Focus **if the caster has a feature that allows that substitution**", and
    #: p. 188: "Some **classes** allow its members to use certain types of Spellcasting
    #: Focuses." The features are class content this repository does not ship (R31), so the
    #: engine holds the resolved permission and a ruleset says — the same split as
    #: `weapon_proficiencies` under 0040 clause 2.
    #:
    #: Defaults to `False`, which refuses a substitution nobody granted rather than inventing
    #: a feature. A Component Pouch needs no such permission and is unaffected.
    may_substitute_focus: bool = False
    #: Which armour this creature is trained with, by item id (p. 19, p. 177, #247).
    #:
    #: **By id, because the categories are content**, which is 0040 clause 2's reasoning for
    #: `weapon_proficiencies` unchanged: p. 19 says "your class might give you training with
    #: certain **categories** of armor", the categories are described in Equipment, and
    #: pp. 93-97 do not ship here (R31). The engine holds the resolved relation and a ruleset
    #: that knows the table expands it into ids.
    #:
    #: **Empty by default, and that refuses rather than grants.** A creature nobody trained is
    #: a creature p. 104 forbids to cast *while wearing armour* — and one wearing none is
    #: unaffected, so the default costs nothing to a caster who dresses like one.
    armour_training: frozenset[str] = frozenset()
    #: A casting of a minute or more, part-way through (p. 105, #250, 0065).
    #:
    #: `None` for a creature casting nothing long. The slot it will cost is **carried here and
    #: not spent** — p. 105 refunds nothing on a broken Concentration because nothing was
    #: expended, so the expenditure happens when the casting completes.
    long_cast: LongCast | None = None
    #: How many hands this creature has, or `None` because **no SRD rule says**.
    #:
    #: Every printed rule about hands is relational — "a free hand" (pp. 89, 105, 182, 190),
    #: "requires two hands" (p. 90) — and not one of them states a creature's count. Two is
    #: what everybody remembers and what nothing in the document supports, so it is exactly
    #: the inferred rule value R31 forbids: plausible, universal, and stated nowhere.
    #:
    #: `None` therefore means the ruleset did not say, and every rule turning on a free hand
    #: declines rather than guessing — the same distinction `slots` draws between a creature
    #: with no spell slots and one with none left.
    hands: int | None = None
    #: p. 188's size category, or `None` because **no ruleset said**.
    #:
    #: `hands` above gives the argument and this is the same one a step further on. p. 188 is
    #: emphatic that every creature has a size — "A creature or an object **belongs to** a
    #: size category" — so `None` is not a claim that this one has none. It is the claim that
    #: nobody stated which, and p. 14 says where the answer would have come from: "A
    #: character's size is determined by **species**, and a monster's size is specified in the
    #: monster's **stat block**." Both are content this repository does not ship (R31).
    #:
    #: **Medium is the tempting default and it is the one R31 forbids.** It is what almost
    #: every player character is, and the SRD states it as a default for nothing — it is a
    #: species' answer, not the game's. Taking it would be silent and wrong in the direction
    #: that matters: p. 178's table read at Medium gives an Ancient Red Dragon a carrying
    #: capacity of 450 lb against its true 3,600, and p. 190 would let a Halfling grapple a
    #: Kraken. A wrong number is indistinguishable from a right one once it is inside a
    #: finished ruling; a refusal is not.
    #:
    #: So every rule keyed on size answers `None` for a creature nobody sized, and #259 is
    #: closed by the engine being able to say "I was not told" rather than by it guessing.
    size: Size | None = None
    #: Whether this creature reads p. 178's table one row up (p. 86, p. 357).
    #:
    #: p. 86, *Powerful Build*: "You also count as one size larger when determining your
    #: carrying capacity." p. 357, *Beast of Burden*: "The mule counts as one size larger for
    #: the purpose of determining its carrying capacity." Two printings of one rule, so one
    #: flag rather than two (0035).
    #:
    #: **Scoped to carrying capacity by both sentences**, which is why it is not a general
    #: "counts as larger". Powerful Build's *other* half — Advantage on checks to end the
    #: Grappled condition — is a separate mechanic and is not this flag.
    #:
    #: A resolved permission the ruleset supplies, for the reason `mastery_weapons` and
    #: `may_substitute_focus` are: the trait belongs to a species and a stat block, and
    #: neither ships here.
    carries_as_one_size_larger: bool = False
    #: What this creature can cast — **ruleset data, carried by the caster** (0038 clause 1).
    #:
    #: It rides here rather than being handed to `legal_actions`, and that is 0026 clause 1
    #: rather than convenience: `legal_actions(state, actor_id)` takes state and nothing else,
    #: so a caller passing a spell list in would be a caller deciding what may be cast, one
    #: call at a time. Lighting and obstructions ride on the state for the same reason.
    #:
    #: **One list, not two** (0038 clause 8). p. 104 says features specify "which spells you
    #: have access to […] and whether you can change the list you have prepared"; it defines
    #: no separate "known spells" list. Preparation (#249) later refines how this list is
    #: arrived at rather than adding a second beside it.
    #:
    #: What each spell *does* is not here. That is the resolver the ruleset registers through
    #: `core.casting.spell_resolvers`.
    spells: tuple[Spell, ...] = ()
    #: The spells this creature has prepared, by id (p. 104, #19). Ids are the ruleset's,
    #: because this engine ships no spell list (#21) and will not invent one.
    #:
    #: **One set, not two.** p. 104 distinguishes always-prepared spells from the list you
    #: may change — but only for the *change limit*: "a spell that you always have prepared
    #: doesn't count against the number of spells on that list". For the question this engine
    #: asks — is it prepared *now* — the distinction does not exist.
    #:
    #: **The change limit is not modelled.** p. 104 puts when a list may change, and how
    #: many, in the spellcasting feature, and summarises it in a per-class table. That is
    #: class data, and this engine ships none of it, for the reason `core.spellcasting`
    #: ships no slot table.
    prepared: frozenset[str] = frozenset()
    #: What this creature is concentrating on, if anything (p. 179, 0036 clause 1).
    #:
    #: Per-creature state and **not** a condition, for 0027 clause 5's reason: "this creature
    #: is concentrating" is a fact about the creature, not one of the fifteen the glossary
    #: tags. It sits here beside `hazards` for the same reason `hazards` does.
    #:
    #: Held rather than derived. p. 179 names three factors that break Concentration and one
    #: voluntary end, and none of them is recomputable from anything else the engine stores —
    #: which effect is being concentrated on is a fact only the caster's declaration supplies.
    concentration: Concentration = field(default_factory=Concentration)
    #: Only meaningful at 0 hit points. Reset rather than carried once healing lands.
    death_saves: DeathSaves = DeathSaves()
    #: The weight this creature is dragging, lifting or pushing, in pounds (p. 178, #336).
    #:
    #: > While dragging, lifting, or pushing weight in excess of the maximum weight you can
    #: > carry, your Speed can be no more than 5 feet.
    #:
    #: **`None` is how p. 12's discretion is exercised** (0067 clause 2). "The GM **might**
    #: require you to abide by the rules for carrying capacity" — so the subsystem binds when
    #: somebody says it does, and saying so *is* stating this weight. A creature nobody stated
    #: one for is not hauling as far as this engine is concerned, and nothing caps its Speed.
    #:
    #: **Not derived from `equipment`, and it must not be.** p. 178 fires on dragging, lifting
    #: or pushing — which is not the same fact as carrying too much, and a creature laden with
    #: 400 lb of worn gear is not on that account dragging anything. Deriving one from the
    #: other would apply a Speed cap the document does not state for that creature.
    #:
    #: **Which of the three verbs it is, is deliberately absent.** p. 178 states one rule for
    #: all three and nothing in this engine branches on the distinction, so modelling it would
    #: be the `kind` field 0019 refuses.
    hauled_weight: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "abilities", MappingProxyType(dict(self.abilities)))

        # p. 179: "Your Concentration **ends** if you have the Incapacitated condition or you
        # die." Ends, not suspends — the event is spent when it happens, and the spell does
        # not come back when the condition lifts (0037 clause 4, #238).
        #
        # **Written here rather than at each writer**, which is the difference between an
        # invariant and a convention. `with_condition` and `with_death` both reach state
        # through `replace`, so both re-run this; so does anything added later, and so does a
        # `Combatant` a caller constructs by hand — the case a derivation covered and two
        # scattered writes would not.
        #
        # It is still materialised rather than derived, and that is the whole of #238: this
        # runs once, when the state carrying the condition is built, and the value it writes
        # is what every reader sees afterwards. `after_conditions` recomputed the answer from
        # whatever conditions were held at the moment somebody asked, so a condition that
        # arrived and departed left no trace and handed the spell back.
        # p. 90: "A Two-Handed weapon **requires two hands** when you attack with it", and
        # p. 105 asks whether a hand is free. Neither is checkable while a creature can hold
        # more than it has hands for — which it could until #263: a one-handed creature
        # gripping a greataxe reported 0 free hands and was accepted.
        #
        # Refused at construction, where every writer passes, rather than at the call sites
        # that put things in hands. `hands is None` is not a violation: no SRD rule states how
        # many hands a creature has, so an unstated count cannot be exceeded (R31).
        if self.hands is not None:
            committed = sum(carried.hands_used for carried in self.equipment)
            if committed > self.hands:
                raise ValueError(
                    f"{self.name} is holding things needing {committed} hands and has "
                    f"{self.hands}. A Two-Handed weapon requires two hands (p. 90), so a "
                    "creature that cannot spare them cannot be wielding it"
                )

        # p. 178: "The table also shows the **maximum** weight you can drag, lift, or push."
        # A maximum, so a haul above it is not a slow haul — it is one the rules do not
        # permit, and a caller stating it has stated an impossible fact (0067 clause 4).
        #
        # Refused only for a creature the ruleset sized, because an unsized one has no row to
        # read and an unstated bound cannot be exceeded — the same direction `hands` takes
        # three paragraphs above, and R31's.
        if self.hauled_weight is not None:
            if self.hauled_weight < 0:
                raise ValueError(f"a hauled weight is a weight in pounds, not {self.hauled_weight}")
            capacity = self.carrying_capacity
            if capacity is not None and self.hauled_weight > capacity.drag_lift_push:
                raise ValueError(
                    f"{self.name} cannot drag, lift or push {self.hauled_weight} lb: p. 178 "
                    f"makes {capacity.drag_lift_push} lb the maximum for a "
                    f"{capacity.size.value} creature of Strength {capacity.strength_score}. "
                    "Above the maximum is not a slower haul, it is one the rules do not allow"
                )

        if self.concentration.active and (
            self.death_saves.dead
            or any(effects.concentration_broken for effects in self.conditions.effects)
        ):
            object.__setattr__(self, "concentration", self.concentration.ended())

    @property
    def free_hands(self) -> int | None:
        """How many hands are free right now, or `None` if nobody said how many there are."""
        return free_hands(self.equipment, self.hands)

    @property
    def carried_weight(self) -> float:
        """Everything worn, held and stowed, in pounds (p. 178)."""
        return carried_weight(self.equipment)

    @property
    def armour_class_bases(self) -> tuple[ArmourClassBase, ...]:
        """Every base AC calculation **a rule gave** this creature (p. 177, p. 92, #393, 0077).

        Worn armour, one per suit. Empty for a creature the ruleset described by its total
        rather than by what it wears.

        **The stored `armour_class` is not in this list, and working out why was the build's
        one real correction.** 0077 clause 4 reads p. 254's stat-block AC as "another base AC
        calculation" that p. 177 permits, and that is right about its *provenance* and wrong
        about its *shape*: a stat block states an AC, which is the result, while p. 177's
        alternatives are calculations. Treating the stored number as a competing base put it
        beside worn armour and made the armour inert — a creature in Plate whose ruleset had
        set `armour_class` to its unarmoured value read as unarmoured, silently.

        So the two are not rivals. A stat-block total is the shorthand a ruleset uses when it
        has not described the armour; describing the armour is saying the same thing more
        precisely, and p. 92's "a monster has training with any armor **in its stat block**"
        is the document contemplating exactly that. `effective_armour_class` prefers the
        described armour and falls back to the stated total.

        **Genuinely competing bases are still coming** — a feature granting an alternative
        calculation is p. 177's actual case — and that is
        [#394](https://github.com/eddiefiggie/srd-rules-engine/issues/394). This property is
        where they will arrive, which is why it returns a tuple for what is today at most one.
        """
        return tuple(
            item.armour_class_base
            for item in items_in(self.equipment, Carriage.WORN)
            if item.armour_class_base is not None
        )

    @property
    def armour_class_bonus(self) -> int:
        """p. 92's Shield: what the creature holds that adds on top of the base.

        > You gain the Armor Class benefit of a Shield **only if you have training with it**.

        **Withheld without training** (#367), the last of p. 177's three drawbacks to be
        built — the casting prohibition landed with 0063 and the Disadvantage with 0064, and
        this one waited on there being a contribution to withhold at all. #393 supplied that
        by deriving Armour Class; before it there was only a stored total, and nothing can be
        taken out of a number whose parts are unknown.

        **The one-Shield refusal counts every Shield, trained or not.** p. 92's "wield only
        one Shield at a time" is about wielding, and a creature holding two is holding two
        whether it may benefit from either — so the refusal is asked before the training
        filter rather than after it. Filtering first would let an untrained Shield hide a
        second one.

        **Training is by item id** (0040 clause 2), which is why this needed no armour
        *category*: pp. 92-97 are content this repository does not ship, and the resolved
        relation was always enough.
        """
        held = [item for item in items_in(self.equipment, Carriage.HELD) if item.armour_class_bonus]
        if len(held) > 1:
            # Asked over every Shield, before training is consulted — see above.
            raise ValueError(
                f"{self.name} is holding {len(held)} things that add to Armour Class, and "
                "p. 92 allows one Shield at a time"
            )
        bonuses = [item.armour_class_bonus for item in held if item.id in self.armour_training]
        return bonuses[0] if bonuses else 0

    @property
    def effective_armour_class(self) -> int:
        """The number an attack roll meets (p. 177, #393, 0077).

        `armour_class` is what the creature *has*; this is what a blow is compared against —
        the shape `effective_speeds` and `effective_defences` already use.

        **The base is chosen and the bonus is added.** p. 177: "you choose which calculation
        to use; **you can't use more than one**." A Shield is not a calculation, so its `+2`
        rides on top of whichever base won, and a character in Plate with a Shield is 20
        rather than 28.

        **Described armour beats a stated total**, for the reason `armour_class_bases` gives:
        they are the same claim at two levels of detail rather than two competing bases. A
        creature nobody dressed keeps its stat-block number, which is every creature in the
        tree today — so this changes no existing outcome and adds a path for one that is
        dressed.

        **More than one described suit is refused** rather than picked between, and p. 92 is
        why: "A creature can wear only one suit of armor at a time." Reaching here with two is
        a state the equipment transitions do not permit, so the refusal is a floor under them
        rather than a rule with its own path (0062).
        """
        # **Two rules, and they were one check until #394.** p. 92 limits what a creature
        # *wears*; p. 177 limits what it *uses*. They coincide only while worn armour is the
        # engine's one source of a base — and a worn item that is not armour already breaks
        # that coincidence, which is how the conflation was found: a creature in one suit of
        # plate and a pair of bracers was told it wore "2 suits of armour".
        suits = [
            item
            for item in items_in(self.equipment, Carriage.WORN)
            if item.is_armour and item.armour_class_base is not None
        ]
        if len(suits) > 1:
            raise ValueError(
                f"{self.name} is wearing {len(suits)} suits of armour, and p. 92 allows one "
                f"at a time: {', '.join(item.id for item in suits)}"
            )

        bases = self.armour_class_bases
        if len(bases) > 1:
            # p. 177: "you choose which calculation to use; **you can't use more than one**."
            # The choice is the creature's and this engine has nowhere to state it yet
            # (#394), so it refuses rather than picking. **Refusing is the safe direction and
            # picking is not**: taking the highest optimises invisibly, and taking the first
            # depends on the order a ruleset listed the creature's equipment. Neither is a
            # decision the document left open — it assigned it.
            raise ValueError(
                f"{self.name} has {len(bases)} base AC calculations available and p. 177 "
                "says a creature chooses one — it cannot use more than one, and this engine "
                "has no way to record which was chosen. Picking for it would decide "
                "something the document assigns to the creature"
            )
        # **At most one by now**, because both refusals above have fired otherwise — so this
        # is not a choice and cannot become one by accident. A corruption that makes it
        # `max(bases, key=...)` is **unobservable**: there is never more than one base to
        # take the maximum of. That is the property #394 is about, and it is structural
        # rather than guarded — the refusal precedes the selection, so picking is impossible
        # rather than merely avoided.
        base = bases[0] if bases else ArmourClassBase(flat=self.armour_class, adds_dexterity=False)
        return base.value(self.modifier("dex")) + self.armour_class_bonus

    @property
    def effective_defences(self) -> Defences:
        """What this creature resists right now, with its conditions applied (#357).

        `defences` is what it has; this is what a blow meets. p. 186's Petrified grants
        "Resistance to all damage", which `Defences.resists_all` already expresses — the flag
        existed and no condition had ever set it, which is the shape #357 is about.

        Composed rather than replaced, so a creature that is both Petrified and Immune to Fire
        keeps the Immunity.
        """
        if not self.conditions.resists_all_damage:
            return self.defences
        return replace(self.defences, resists_all=True)

    @property
    def carrying_size(self) -> Size | None:
        """The size p. 178's table is read at, which is not always this creature's.

        p. 86 and p. 357 both move a creature one row up **for this table only**, so the
        effective size is computed here and the creature's own `size` is left alone.
        """
        if self.size is None:
            return None
        return (
            one_size_larger_for_carrying(self.size)
            if self.carries_as_one_size_larger
            else self.size
        )

    @property
    def carrying_capacity(self) -> CarryingCapacity | None:
        """p. 178's two bounds, or `None` for a creature nobody sized.

        `None` is a refusal and not a capacity of zero. p. 178's table is keyed on a size,
        and an engine that has not been told one cannot read a row without choosing it — see
        `size` for why choosing it is the failure R31 names.
        """
        size = self.carrying_size
        if size is None:
            return None
        return carrying_capacity(size, self.abilities.get("str", 10))

    @property
    def over_carrying_capacity(self) -> bool | None:
        """Whether what this creature has exceeds p. 178's Carry column, or `None` if unsized.

        Arithmetic, not a ruling: p. 178 calls Carry "the maximum weight in pounds that you
        can carry", so a total above it is over that maximum and nothing more is claimed. What
        p. 178 says *follows* — "your Speed can be no more than 5 feet" — is not applied, and
        the read surface discloses that rather than leaving it to be discovered. It turns on
        whether the creature is dragging, lifting or pushing, which is a narrative fact this
        engine does not hold, and p. 12 leaves the whole subsystem to a person: "the GM
        **might** require you to abide by the rules for carrying capacity."
        """
        capacity = self.carrying_capacity
        if capacity is None:
            return None
        return self.carried_weight > capacity.carry

    @property
    def over_hauling_capacity(self) -> bool | None:
        """Whether p. 178's Speed cap bites right now, or `None` if it cannot be told (#336).

        > While dragging, lifting, or pushing weight in excess of the maximum weight you can
        > carry, your Speed can be no more than 5 feet.

        **The comparison is against the Carry column, and against the hauled weight alone.**
        p. 178 says "weight in excess of the maximum weight you can carry" of the weight being
        dragged, lifted or pushed — it does not add the creature's own gear to it, and an
        implementation that summed the two would cap a Speed the sentence does not.

        `None` twice over, and they mean different things a caller may want to tell apart:
        a creature nobody stated a haul for is not hauling (`False` would be a verdict about a
        question nobody asked), while an **unsized** creature hauling something has no row of
        p. 178's table to read and the bound is genuinely unknown.
        """
        if self.hauled_weight is None:
            return None
        capacity = self.carrying_capacity
        if capacity is None:
            return None
        return self.hauled_weight > capacity.carry

    @property
    def weapons_held(self) -> tuple[Weapon, ...]:
        """Every weapon this creature has in hand (0040 clause 1).

        `isinstance` rather than a flag, because a weapon genuinely **is** an item with more
        rules attached — a subtype test rather than the `kind` field 0019 refuses, and the
        two are told apart by whether a consumer branches on data or on type.
        """
        return tuple(item for item in self.items_carried(Carriage.HELD) if isinstance(item, Weapon))

    def items_carried(self, carriage: Carriage) -> tuple[Item, ...]:
        """What this creature has in that carriage, in the order the ruleset gave it."""
        return items_in(self.equipment, carriage)

    @property
    def is_down(self) -> bool:
        """At 0 hit points a combatant stops acting."""
        return self.hit_points <= 0

    @property
    def is_dodging(self) -> bool:
        """Whether a Dodge taken earlier still stands (p. 181).

        Re-checked rather than trusted: a creature can be grappled or stunned after
        Dodging, and both end the benefit.
        """
        return still_dodging(
            self.actions, self.conditions, self.conditions.speed_after(self.speeds.walk)
        )

    @property
    def effective_speeds(self) -> Speeds:
        """This creature's speeds with its conditions applied (p. 188).

        `speeds` is what the creature has; this is what it can use now. Everything asking
        how far it may move, or whether it stays in the air, reads this one.
        """
        reduced = self.conditions.speeds_after(self.speeds)
        # p. 90's Slow acts on "its **Speed**", which p. 188 makes the walking one — a
        # reduction reaching a Fly or Swim Speed would be a rule the sentence does not state.
        # Floored at zero, because a Speed is a distance and not a debt.
        taken = slow_feet_taken(self.speed_reductions)
        if taken:
            reduced = replace(reduced, walk=max(0, reduced.walk - taken))
        # p. 178's hauling cap, applied last because it is a **ceiling** rather than a
        # reduction: "your Speed can be no more than 5 feet". A creature already slower than
        # five feet is not sped up to it, which is what `min` says and a subtraction would not.
        # The walking Speed only, for the same reason Slow reaches only that one — p. 188 makes
        # "Speed" the walking one, and a cap reaching a Fly or Swim Speed would be a rule this
        # sentence does not state.
        if self.over_hauling_capacity:
            reduced = replace(reduced, walk=min(reduced.walk, HAULING_SPEED_CAP_FEET))
        return reduced

    @property
    def falls_if_flying(self) -> bool:
        """Whether being aloft would end right now (p. 182).

        p. 182, *Flying*: "While flying, you fall if you have the Incapacitated or Prone
        condition or your Fly Speed is reduced to 0. You can stay aloft in those
        circumstances if you can hover." Three triggers and one exception that covers all
        three — "those circumstances", plural, which is also what p. 183's Hover entry
        means by "prevents you from falling in certain circumstances".

        **The engine does not claim to know the creature is flying.** No state says a
        creature is airborne on its Fly Speed rather than standing on a ledge, and nothing
        in the SRD makes that derivable from a position. This answers p. 182's condition
        and leaves the antecedent to the caller, which is a read reporting a rule value
        rather than an adjudication (R19).

        A creature with no Fly Speed at all answers `True`, and that is not a tiebreak:
        p. 182 grants staying aloft to a creature that *has* a Fly Speed, so there is no
        reading under which one without stays up.
        """
        speeds = self.effective_speeds
        if speeds.fly is None:
            return True
        if speeds.hover:
            return False
        return (
            speeds.fly == 0
            or Condition.INCAPACITATED in self.conditions.held
            or Condition.PRONE in self.conditions.held
        )

    @property
    def makes_death_saves(self) -> bool:
        """p. 17-18: a **player character** at 0 hit points, unless Stable or dead.

        Three conditions, and each excludes a case the others let through. "A player
        character must make a Death Saving Throw" — a monster dies instead. "A Stable
        creature doesn't make Death Saving Throws even though it has 0 Hit Points" — so
        being down is not sufficient, which is why Stable is tracked separately from the
        hit point total.
        """
        return self.is_player_character and self.is_down and not self.death_saves.is_resolved

    def movement_remaining_in(self, mode: MovementMode) -> int | None:
        """How much farther this creature may move *in this mode* (p. 188).

        p. 188, *Special Speeds*: "If you have more than one speed, choose which one to use
        when you move; you can switch between the speeds during your move. Whenever you
        switch, subtract the distance already moved from the new speed. The result
        determines how much farther you can move. If the result is 0 or less, you can't use
        the new speed during the current move."

        So the allowance is **per mode against one shared spend**, not one pool drawn from
        Speed. `movement_used` is the shared spend; the mode supplies the number it comes
        off. The document's own worked example is the test: with a Speed of 30 and a Fly
        Speed of 40 "you could fly 10 feet, walk 10 feet, and leap into the air to fly 20
        feet more" — 40 feet in total, which no single-pool reading reaches.

        **Which speed governs a mode is not always the special one.** Climbing, swimming
        and crawling are ordinary moves that cost extra (pp. 178, 189, 179), so a creature
        without the matching special speed makes them on its Speed; `Speeds.for_mode`
        already returns `walk` for crawling for that reason. Flying and burrowing have no
        such fallback — pp. 178 and 182 grant them only through the speed itself — so this
        answers `None` for a creature that has neither, which is the same refusal
        `with_movement` makes and is not the same fact as a remaining 0.

        **Dash adds movement, not speed.** p. 180: "you gain extra movement for the current
        turn", and "if you have a special speed ... you can use that speed instead of your
        Speed when you take this action". The size of the pool is chosen once, at the Dash;
        what it grants is feet, so those feet are spendable in any mode the creature has.
        """
        speed = self.effective_speeds.for_mode(mode)
        if speed is None:
            if mode in _SPEED_ONLY_MODES:
                return None
            speed = self.effective_speeds.walk
        return max(0, speed + self.actions.extra_movement - self.movement_used)

    @property
    def movement_remaining(self) -> int:
        """What is left of this creature's Speed on this turn (p. 188), walking.

        Conditions act on the Speed first: Grappled and the rest set it to 0, and
        Exhaustion reduces it by 5 per level (pp. 182, 181). A creature whose Speed a
        condition zeroed has no movement left however little it has spent.

        Walking only. A creature with a special speed has a *different* number for that
        mode and `movement_remaining_in` is what answers it — reading this one for a flying
        creature charges its flight against its Speed, which is the bug #206 filed.
        """
        walking = self.movement_remaining_in(MovementMode.WALK)
        assert walking is not None  # WALK always draws on Speed, which is never None
        return walking

    def modifier(self, ability: str) -> int:
        """The SRD's ability modifier, floor-divided so negatives round the right way."""
        return (self.abilities.get(ability, 10) - 10) // 2

    def check_bonus(self, skill: Skill) -> int:
        """The bonus on an ability check associated with this skill (p. 188).

        "If you have proficiency in a skill, you can add your Proficiency Bonus when you
        make an ability check associated with that skill" — so the ability's modifier
        always, and the Proficiency Bonus only when the skill is held.

        Which ability is the skill's, not the caller's: a Wisdom (Perception) check is a
        Wisdom check whoever rolls it, and `SKILL_ABILITY` is p. 9's table rather than a
        memory of it.
        """
        bonus = self.modifier(SKILL_ABILITY[skill])
        return bonus + self.proficiency_bonus if skill in self.skills else bonus


def _recovers_by(participant: Combatant, clock: Clock) -> bool:
    """p. 18, and only for a creature still Stable and still at its deadline or past it."""
    saves = participant.death_saves
    return (
        saves.stable
        and saves.recovers_at_minute is not None
        and clock.elapsed_minutes >= saves.recovers_at_minute
    )


def _elapsed(participant: Combatant, clock: Clock) -> Combatant:
    """A creature with every campaign-axis condition the clock has now outlasted lifted (#111).

    `Conditions.without` recomputes implication rather than subtracting from the closure,
    which is why this goes through it instead of discarding keys: a creature whose eight-hour
    Unconscious elapses keeps the Prone that p. 191 says it keeps.
    """
    expiring = participant.conditions.expired_by(clock.elapsed_minutes)
    if not expiring:
        return participant
    return replace(participant, conditions=participant.conditions.without(expiring))


@dataclass(frozen=True)
class EncounterState:
    """The state the read surface reports over, and the only thing that carries a generation."""

    generation: int
    combatants: tuple[Combatant, ...]
    round_number: int = 0
    turn_index: int | None = None
    #: Elapsed campaign time (decision 0020). It rides here because this is the only state
    #: carrier the engine has; it is *not* encounter-scoped, and `round_number` does not
    #: convert into it — p. 13 says a round represents *about* 6 seconds, which is the
    #: document declining an exact conversion. `core.clock` has the reasoning.
    clock: Clock = field(default_factory=Clock)
    #: Where the light is (0025 clause 2). It rides on the state rather than arriving as an
    #: argument to a query, because an input the caller supplies at the moment an outcome is
    #: computed is an input the caller chooses — and Bright Light versus Darkness is
    #: Advantage versus Disadvantage. The default states no light at all, so a query about it
    #: refuses rather than assuming daylight.
    lighting: Lighting = field(default_factory=Lighting)
    #: What blocks a line, in feet (0026 clause 1, #91). Terrain rides on the state for the
    #: reason light does, and 0026 decided the two by one rule rather than two: an input the
    #: caller hands over at the moment an outcome is computed is an input the caller
    #: *chooses*, and choosing which walls exist is choosing who a Fireball reaches.
    #:
    #: **An empty tuple means there are none**, not that they are ignored (0026 clause 5).
    #: That describes an open field, which is the right answer for an open field and the
    #: wrong one for a dungeon. The engine cannot tell those apart and does not pretend to;
    #: what 0026 changed is only *who* may say so, and when.
    obstructions: tuple[Obstruction, ...] = ()
    #: Objects no creature has — dropped, thrown, or let go of by a rule (0041 clause 3).
    #: State rather than an argument, for the reason `obstructions` and `lighting` are: an
    #: input a caller hands over at the moment an outcome is computed is an input the caller
    #: *chooses*, and choosing which objects are within reach is choosing whether a disarmed
    #: creature can re-arm itself (0026 clause 1).
    #:
    #: **An empty tuple means nobody has dropped anything**, which is the right answer for a
    #: scene where nobody has — the same reading `obstructions` carries under 0026 clause 5.
    #:
    #: Each object's `position` is `Position | None` and is never defaulted, because five
    #: printed rules detach an item and not one says where it lands (0041 clause 4). Nothing
    #: here puts an item into this tuple yet: detachment is an outcome and belongs to a
    #: ruling, which is #280.
    detached_objects: tuple[DetachedObject, ...] = ()
    #: Obligations already discharged during the current turn, as `(actor_id, rule_id)`
    #: (0023 clause 6, #110). Cleared by `advanced_turn`, because an obligation is owed
    #: once per turn rather than once per encounter.
    #:
    #: Keyed by **rule id** rather than by condition since 0027 clause 2. A death save has
    #: no condition and Burning is not one of the fifteen, so the condition was the wrong
    #: key for two of the three things that discharge here — and one set covers both the
    #: turn's start and its end, because `advanced_turn` clears it between turns.
    #:
    #: This exists because "is an obligation outstanding" is *not* the same question as
    #: "does the creature still hold a save-ends condition". A **failed** save leaves the
    #: condition in place, so a guard reading `saves_due_after` alone would refuse to
    #: advance the turn forever — the obligation was met, and p. 63 states no penalty and
    #: no second attempt.
    discharged: frozenset[tuple[str, str]] = frozenset()
    #: Concentration saves owed but not yet rolled, oldest first (p. 179, 0036 clause 3).
    #:
    #: **A separate structure from `discharged`, and the cardinality is the whole reason.**
    #: An obligation above is owed *once per turn* — that is what the field means and why
    #: `advanced_turn` clears it. p. 179 compels a Constitution save on *every* instance of
    #: damage, so a creature struck twice by a Multiattack owes two. Keyed the way
    #: `discharged` is keyed, the second would be suppressed and never rolled: a compelled
    #: save that silently does not happen, which is the skip this engine exists to make
    #: impossible and which leaves no trace in play — the spell simply stays up.
    #:
    #: Widening `discharged` to carry a count was the alternative, and it would make every
    #: obligation's once-per-turn semantics depend on a field one rule uses. Two mechanisms
    #: with different cardinalities are two structures (0019, 0036 clause 3).
    #:
    #: **Not cleared by `advanced_turn`**, for the same reason: a debt incurred on the
    #: monster's turn is owed by the caster, who is not the creature whose turn is ending.
    forced_saves_owed: tuple[ForcedSave, ...] = ()
    #: Advantage and Disadvantage granted by one roll and spent by another (p. 90, 0049).
    #:
    #: **Not per turn, and not a condition.** Every other source of Advantage here is a
    #: standing fact recomputed at the moment of the roll; these are held and consumed. They
    #: outlive turns — Vex's window runs to the end of the granter's *next* turn — so
    #: `advanced_turn` sweeps the dead rather than clearing the field.
    pending_advantage: tuple[PendingAdvantage, ...] = ()
    #: Who has already expended a spell slot this turn (p. 105, 0038): "On a turn, you can
    #: expend only one spell slot to cast a spell."
    #:
    #: **Its own field rather than a `discharged` entry, and the cardinality is not the
    #: reason** — that matches, and both clear on the same advance. The *meaning* is what
    #: differs. `discharged` records that an **obligation was met**; this records that a
    #: **resource was spent**. A guard reading one for the other is answering a different
    #: question, and 0036 clause 3 is the record of what one structure carrying two meanings
    #: costs. Two mechanisms that clear together are still two mechanisms.
    #:
    #: A cantrip never appears here: p. 104 puts a level 0 spell outside the slot economy, so
    #: it spends nothing and this rule has nothing to say about it.
    slots_expended_this_turn: frozenset[str] = frozenset()
    #: Who took the Attack action with a **Light** weapon this turn, and with which (p. 89).
    #:
    #: p. 89 buys the extra attack on two conditions and this records both: "When you take
    #: the Attack action on your turn **and attack with a Light weapon**… That extra attack
    #: must be made with a **different** Light weapon." So the weapon has to be remembered,
    #: not merely the fact — a set of actors could not answer "different from which".
    #:
    #: **A third per-turn structure, and a third meaning.** `discharged` records an obligation
    #: met; `slots_expended_this_turn` records a resource spent; this records **what was done
    #: and with what**. They clear together and mean different things, which is 0036 clause 3
    #: applied a third time: two mechanisms that agree about *when* are still two mechanisms.
    light_attacks_this_turn: frozenset[tuple[str, str]] = frozenset()
    #: How many attack rolls each creature has made this turn (p. 257, 0043 clause 4). A
    #: **count**, because the question a Multiattack asks is "how many of the rolls this
    #: Action bought are left" and a set of actors cannot answer it — which is what separates
    #: this from the three structures above.
    attacks_this_turn: Mapping[str, int] = field(default_factory=dict)
    #: Who has already made p. 89's one extra Light attack this turn, by either route (#320).
    #:
    #: **A fourth per-turn structure, and it exists because Nick removed the third's stand-in.**
    #: Until p. 90's Nick, the Bonus Action spend *was* this record: a second extra attack was
    #: refused because no Bonus Action remained. A Nick attack is made "as part of the Attack
    #: action **instead of** as a Bonus Action" and spends nothing, so the old bookkeeping
    #: stopped bookkeeping — nothing prevented a creature taking one extra attack by each
    #: route. p. 89 grants "**one** extra attack" however it is made.
    #:
    #: Distinct from `light_attacks_this_turn`, which records the Attack-action attacks that
    #: *bought* the extra one and with which weapon. This records that the extra one is spent.
    #: 0036 clause 3 a fourth time: mechanisms agreeing about *when* are still different
    #: mechanisms.
    extra_attacks_this_turn: frozenset[str] = frozenset()
    #: Melee hits this turn that opened p. 90's Cleave, as (actor, weapon, creature hit)
    #: (#323). The creature is remembered because Cleave's second target is "within 5 feet of
    #: **the first**" — a set of actors could not answer "beside which".
    #:
    #: **A fifth per-turn structure, and a fifth meaning**, which is 0036 clause 3 again:
    #: `light_attacks_this_turn` records what bought p. 89's extra attack, this records what
    #: opened p. 90's, and the two caps are separate sentences.
    cleave_openings_this_turn: frozenset[tuple[str, str, str]] = frozenset()
    #: Who has already made p. 90's one Cleave attack this turn (#323).
    #:
    #: Distinct from `extra_attacks_this_turn`, and deliberately: "you can make **this** extra
    #: attack only once per turn" caps Cleave alone, so a creature may take p. 89's extra
    #: attack *and* a Cleave in the same turn. Sharing the record would refuse one of them.
    cleaves_this_turn: frozenset[str] = frozenset()
    #: Who has already spent this turn's one object interaction (0045 clause 1).
    #:
    #: **One allowance, two routes.** p. 13 grants "one object or feature of the environment
    #: for free" per turn and p. 177 grants one weapon swap per attack, and the document never
    #: composes them. Two interactions are legal under the independent reading and not under
    #: the shared one; one is legal under both, so the engine offers the intersection and
    #: records both routes here (0043 clause 3, 0045 clause 1).
    #:
    #: **This was `swaps_this_turn` until #288**, when p. 13's route arrived and the old name
    #: became a lie — it now records picking a rock up as readily as sheathing a sword.
    #:
    #: A set, not a count: the cap is one, so the only question is whether this creature has
    #: taken it. A second interaction needs the Utilize action (p. 13), which spends the
    #: Action rather than this.
    object_interactions_this_turn: frozenset[str] = frozenset()
    #: Which `(actor, action kind)` pairs have already fired a Loading weapon (p. 90, #271).
    #:
    #: **Keyed by the action used, not by the turn.** p. 90 caps the shot "when you use an
    #: action, a Bonus Action, or a Reaction to fire it", so a creature holding both may fire
    #: once with each — a per-turn key would refuse the second, which the document permits.
    #: And not keyed by weapon: two Loading weapons do not buy two shots from one action.
    loading_shots_this_turn: frozenset[tuple[str, str]] = frozenset()
    #: How much ammunition each creature has spent **in this fight**, as `(actor, item) ->
    #: count` (p. 89, 0044 clause 6).
    #:
    #: **The first structure here that does not clear when the turn advances.** The six above
    #: are per-turn; this one is per-encounter, because p. 89 recovers "half the ammunition
    #: (round down) **you used in the fight**" — which is not derivable from what remains. A
    #: creature that started with six arrows and holds two may have fired four, or fired one
    #: and dropped three.
    #:
    #: Nothing reads it yet: recovery needs a boundary for "after a fight", and p. 14's test
    #: for combat ending has five conditions of which this engine can observe two
    #: ([#301](https://github.com/eddiefiggie/srd-rules-engine/issues/301), 0044 clause 5).
    #: Recorded now because the fight it counts is happening now, and a tally started later
    #: cannot recover what it did not see.
    ammunition_used: Mapping[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Retire every effect whose sustaining Concentration is gone (p. 179, 0037 clause 3).

        > If the effect's creator loses Concentration, the effect ends.

        **Here rather than in `with_concentration_ended`, which is what 0037 clause 3 named.**
        That method is one of *four* routes to the end and covers two of them: the failed
        damage save reaches it through an effect, and the voluntary end through a driver.
        Incapacitated and death do not — they end Concentration in `Combatant.__post_init__`
        (clause 4, #238), which `with_condition` and `with_death` reach through `replace`
        without this class hearing about it. Retiring only in that method would silently miss
        both, and death is the one with no caller to make the omission obvious.

        So it is a whole-state invariant, which is #238's own lesson one level up: the rule
        that survives is the one every writer passes through rather than the one every writer
        must remember. `_evolve` is the only way to produce a successor and construction is
        the other way in, so both land here. 0036 clause 6 made the same argument against
        three call sites for the loop's drain.

        **Deterministic bookkeeping, not an outcome.** Nothing is rolled and no Ruling is
        produced — the same standing as `advanced_turn` retiring a round count (0021 clause
        2). The decision was made when the effect stated its early-out.

        **One pass reaches a fixed point.** Retiring a condition cannot end another
        Concentration: `Combatant.__post_init__` ends one only when a breaking condition is
        *present*, and this only ever removes conditions. Worth checking rather than
        assuming — a self-triggering invariant in a constructor is an infinite recursion.

        **A sustainer that is absent is not concentrating**, and its effects go too. A
        duration naming a creature this encounter does not contain is holding an effect up on
        nothing that can be observed, and leaving it standing would be sustaining it on a
        creature the engine cannot see.
        """
        relied_on: set[str] = set()
        for combatant in self.combatants:
            relied_on |= combatant.conditions.concentrations_relied_on()
        if not relied_on:
            # The common case, and every state in this engine until a consumer ships an
            # effect that states a concentration early-out. Nothing is walked twice.
            return

        concentrating = {c.id for c in self.combatants if c.concentration.active}
        lapsed = relied_on - concentrating
        if not lapsed:
            return

        updated = list(self.combatants)
        for index, combatant in enumerate(updated):
            ending: frozenset[Condition] = frozenset()
            for creator_id in sorted(lapsed):
                ending |= combatant.conditions.sustained_by(creator_id)
            if not ending:
                continue
            updated[index] = replace(combatant, conditions=combatant.conditions.without(ending))
        object.__setattr__(self, "combatants", tuple(updated))

    # --- Reading ------------------------------------------------------------------

    @classmethod
    def new(cls, combatants: Sequence[Combatant]) -> EncounterState:
        return cls(generation=0, combatants=tuple(combatants))

    def combatant(self, combatant_id: str) -> Combatant:
        for participant in self.combatants:
            if participant.id == combatant_id:
                return participant
        raise KeyError(f"no combatant {combatant_id!r} in this encounter")

    def has(self, combatant_id: str) -> bool:
        return any(participant.id == combatant_id for participant in self.combatants)

    @property
    def in_combat(self) -> bool:
        return self.turn_index is not None

    @property
    def active_id(self) -> str | None:
        """Whose turn it is, or None outside combat."""
        if self.turn_index is None:
            return None
        return self.combatants[self.turn_index].id

    def is_active(self, combatant_id: str) -> bool:
        return self.active_id == combatant_id

    def obligations_outstanding(self, combatant_id: str) -> tuple[Condition, ...]:
        """Repeated saves this creature owes at the end of its current turn (p. 63).

        Derived from state and never declared (0023 clause 2): p. 63 gives the creature no
        choice about repeating the save, so offering it through a declaration slot would be
        offering a decision the document does not give.
        """
        due = self.combatant(combatant_id).conditions.saves_due_after(combatant_id)
        return tuple(
            sorted(
                (c for c in due if (combatant_id, save_ends_rule_id(c)) not in self.discharged),
                key=lambda c: c.value,
            )
        )

    def can_see(self, observer_id: str, target_id: str) -> Sight:
        """Whether one creature sees another, and by what (0025 clause 4, #166).

        Derived on demand and stored nowhere, which is 0025 clause 4. It lives here rather
        than in `core.sight` for the reason `creatures_in` does: the answer needs the
        encounter's obstructions and its light, and taking either as an argument is the dial
        [0026](../../../docs/decisions/0026-terrain-enters-as-state.md) removed.

        ## The document stops before this question does

        `Visibility.UNSTATED` is a real answer here, not a stub. **The SRD never says that an
        obstruction blocks sight**, and it never defines "line of sight" — the term appears
        on pp. 130, 131, 173, 182, 183 and 310 and is defined on none of them. Total Cover is
        defined by what it does to *targeting*: "can't be targeted directly" (p. 179).

        The clearest evidence is p. 173, where a spell's wall has to state that it "blocks
        line of sight". If an obstruction blocked sight by default, that clause would be
        redundant.

        So a target behind Total Cover is `UNSTATED` for ordinary sight and for Truesight,
        and `CANNOT_SEE` for Blindsight alone — because Blindsight is the one sense whose
        bound the document gives: "you can see anything that isn't behind Total Cover even
        if you have the Blinded condition or are in Darkness" (p. 177).

        Answering `CANNOT_SEE` for the rest would be inferring a rule the document does not
        state (R31), and answering `CAN_SEE` would be worse.

        ## Tremorsense is not consulted

        p. 190: it "doesn't count as a form of sight". It pinpoints a location, which is a
        different question from seeing, and the document says so outright rather than leaving
        it to be inferred (#149's sibling argument for Telepathy).
        """
        observer = self.combatant(observer_id)
        target = self.combatant(target_id)

        if observer.position is None or target.position is None:
            return Sight(
                verdict=Visibility.UNSTATED,
                because=(
                    "an encounter that tracks no positions cannot answer a question about "
                    "distance or what lies between"
                ),
            )

        away = distance_feet(observer.position, target.position)
        between = blocking(observer.position, target.position, self.obstructions)
        blocked = bool(between)
        senses = observer.senses

        # Blindsight is the one sense whose bound the document gives, so it is asked first.
        # When the target IS behind Total Cover this rules Blindsight out and says nothing
        # about the other routes, which is why the answer can still fall through to UNSTATED.
        blindsight = senses.range_of(Sense.BLINDSIGHT)
        if blindsight is not None and away <= blindsight and not blocked:
            return Sight(
                verdict=Visibility.CAN_SEE,
                because=(
                    "p. 177: within Blindsight's range a creature sees anything that is "
                    "not behind Total Cover, even while Blinded or in Darkness — and sees "
                    "something with the Invisible condition"
                ),
                by=Sense.BLINDSIGHT,
            )

        if observer.conditions.has(Condition.BLINDED):
            # p. 177: "You can't see." Absolute, and checked after Blindsight because that
            # sense overrides it in terms — "even if you have the Blinded condition". No
            # other sense says it does, and granting one that reach would be inventing it.
            return Sight(
                verdict=Visibility.CANNOT_SEE,
                because=(
                    'p. 177: the observer has the Blinded condition — "You can\'t see". '
                    "Blindsight is the only sense the document gives that overrides it"
                ),
            )

        truesight = senses.range_of(Sense.TRUESIGHT)
        if truesight is not None and away <= truesight and not blocked:
            return Sight(
                verdict=Visibility.CAN_SEE,
                because=(
                    "p. 190: within Truesight's range a creature sees in normal and magical "
                    "Darkness and sees what has the Invisible condition"
                ),
                by=Sense.TRUESIGHT,
            )

        if between:
            # 0029 clause 4. Opaque beats unstated beats transparent: one barrier known to
            # block sight settles it, and a wall nobody has described cannot be assumed
            # transparent because its neighbour is.
            if any(o.blocks_sight for o in between):
                return Sight(
                    verdict=Visibility.CANNOT_SEE,
                    because=(
                        "an obstruction between them blocks sight, as this encounter "
                        "describes it (0029)"
                    ),
                )
            if any(o.blocks_sight is None for o in between):
                return Sight(
                    verdict=Visibility.UNSTATED,
                    because=(
                        "the target is behind Total Cover and nobody has said whether that "
                        "barrier blocks sight. The SRD answers this per barrier and answers "
                        "it both ways — Wall of Force is Invisible (p. 172) while Wall of "
                        "Thorns blocks line of sight (p. 173) — so this engine states no "
                        "default (0029 clause 2). Set `Obstruction.blocks_sight` to say"
                    ),
                )
            # Every barrier on the line is transparent, so the view continues.

        if target.conditions.has(Condition.INVISIBLE):
            # p. 184 never says an Invisible creature cannot be seen. It says an effect
            # needing sight misses it "unless the effect's creator can somehow see you",
            # and leaves *somehow* to the table. Blindsight and Truesight are the two the
            # document answers for, and both were asked above.
            return Sight(
                verdict=Visibility.UNSTATED,
                because=(
                    "the target has the Invisible condition, and p. 184 states what that "
                    "conceals it from rather than whether it can be seen — effects needing "
                    "sight miss it 'unless the effect's creator can somehow see you', and "
                    "the SRD leaves 'somehow' open. Blindsight (p. 177) and Truesight "
                    "(p. 190) are the two routes it does answer for (#166)"
                ),
            )

        level = self.lighting.level_at(target.position)
        if level is None:
            return Sight(
                verdict=Visibility.UNSTATED,
                because=(
                    "nobody has stated the light where the target is, and this engine does "
                    "not assume daylight (0025 clause 2)"
                ),
            )

        obscured = obscurement_at(level, senses=senses, distance_feet=away)
        if obscured is Obscurement.HEAVILY_OBSCURED:
            return Sight(
                verdict=Visibility.CANNOT_SEE,
                because=(
                    "p. 182: a creature has the Blinded condition while trying to see "
                    "something in a Heavily Obscured space"
                ),
            )
        return Sight(
            verdict=Visibility.CAN_SEE,
            because=(
                f"the target stands in {level.value} and nothing between blocks the view "
                f"({obscured.value})"
            ),
        )

    def perception_of(self, observer_id: str, target_id: str) -> PerceptionCheck:
        """What a Wisdom (Perception) check to see this creature has (#138).

        The consumer `core.sight`'s tables never had. Obscurement has been derivable since
        #150 and nothing read it, so p. 184's Disadvantage was produced by nothing.

        Here rather than in `core.perception` for the reason `can_see` is here: the answer
        needs the encounter's lighting and its obstructions, and taking either as an
        argument is the dial [0026](../../../docs/decisions/0026-terrain-enters-as-state.md)
        removed — a caller choosing the light is a caller choosing the outcome.

        ## The order, and why sight is asked first

        **A special sense answers before obscurement does.** p. 177 gives Blindsight sight
        "without relying on physical sight ... even if you have the Blinded condition or are
        in Darkness", and p. 190 gives Truesight sight in "normal and magical Darkness".
        Both are exemptions from the chain rather than positions along it, so a creature
        that sees by one has no light-based penalty at all — and applying one would be
        inventing a cost the document does not charge.

        **Then the Blinded condition**, held outright: p. 177's automatic failure.

        **Then obscurement**, which is where pp. 184 and 182 land. Heavily Obscured is not a
        worse Disadvantage — p. 182 confers *the Blinded condition* for the attempt, and
        p. 177 says what that costs a check, which is the whole of it.

        **Then Frightened**, whose Disadvantage on ability checks (p. 182) is not about
        sight at all and had no consumer until now. It cancels against nothing here, because
        nothing in this chain grants Advantage — but it is asked so that a Frightened
        creature peering into Dim Light is not reported as merely obscured.

        An unstated light is not a penalty. 0025 clause 2 refuses to assume daylight, and
        assuming Dim Light instead would be the same invention pointing the other way.
        """
        observer = self.combatant(observer_id)
        target = self.combatant(target_id)

        sight = self.can_see(observer_id, target_id)
        if sight.can_see and sight.by is not None:
            return PerceptionCheck(
                advantage=Advantage.NONE,
                because=(
                    f"{sight.by} does not rely on physical sight, so no light level "
                    f"modifies this check — {sight.because}"
                ),
            )

        # Asked of the aggregate rather than of `Condition.BLINDED` (#360). The sentence
        # quoted below is transcribed into `ConditionEffects.auto_fail_checks_requiring_sight`,
        # and naming the condition here kept a second copy of one rule in a second module — so
        # a condition that set the flag would have worked in the table and done nothing at the
        # check.
        #
        # `can_see` above still names the condition, and correctly: that is p. 178's *other*
        # clause — "You can't see" — which is about sight rather than about checks.
        if observer.conditions.auto_fails_checks_requiring_sight:
            return PerceptionCheck(
                advantage=Advantage.NONE,
                because=(
                    "p. 177: the observer has the Blinded condition — \"You can't see and "
                    'automatically fail any ability check that requires sight"'
                ),
                automatic_failure=True,
            )

        # p. 182's Frightened and p. 186's Poisoned both give Disadvantage on ability
        # checks, and neither is about sight. Named separately from the obscurement reason
        # so a creature penalised by a condition is not reported as penalised by the light.
        from_condition = observer.conditions.own_ability_checks(
            fear_in_sight=self.fear_in_sight(observer_id)
        )
        condition_note = (
            "" if from_condition is Advantage.NONE else f"; a held condition gives {from_condition}"
        )

        if target.position is None:
            return PerceptionCheck(
                advantage=from_condition,
                because=(
                    "no light level applies, because the target has no position and this "
                    f"encounter cannot say what it is standing in{condition_note}"
                ),
            )

        level = self.lighting.level_at(target.position)
        if level is None:
            return PerceptionCheck(
                advantage=from_condition,
                because=(
                    "nobody has stated the light where the target is, and this engine does "
                    "not assume daylight (0025 clause 2) — so no obscurement is applied"
                    f"{condition_note}"
                ),
            )

        away = (
            distance_feet(observer.position, target.position)
            if observer.position is not None
            else 0
        )
        obscured = obscurement_at(level, senses=observer.senses, distance_feet=away)

        if obscured is Obscurement.HEAVILY_OBSCURED:
            return PerceptionCheck(
                advantage=Advantage.NONE,
                because=(
                    "p. 182: the target stands in a Heavily Obscured space, which gives the "
                    "observer the Blinded condition while trying to see it — and p. 177: "
                    '"automatically fail any ability check that requires sight"'
                ),
                automatic_failure=True,
            )

        if obscured is Obscurement.LIGHTLY_OBSCURED:
            return PerceptionCheck(
                advantage=Advantage.DISADVANTAGE,
                because=(
                    f"p. 184: the target stands in a Lightly Obscured space ({level.value}), "
                    "so a Wisdom (Perception) check to see it has Disadvantage"
                ),
            )

        return PerceptionCheck(
            advantage=from_condition,
            because=(f"the target stands in {level.value}, which obscures nothing{condition_note}"),
        )

    def fear_in_sight(self, combatant_id: str) -> bool:
        """Whether any source of this creature's fear is within line of sight (p. 182, #192).

        `True` unless **every** source is definitively out of sight. That asymmetry is 0030
        clause 1: applying a Disadvantage the rules may not require can only omit a hit,
        while dropping one they do require produces damage that should not exist. So an
        `UNSTATED` source keeps the penalty, and so does a creature nobody recorded a source
        for — which is every Frightened creature until a caller starts naming them.

        Any source in sight is enough. p. 182 says "the source of fear", singular, because
        it describes one application; a creature frightened by two things holds one condition
        with two sources (p. 179), and this engine will not decide which of them the sentence
        meant.
        """
        held = self.combatant(combatant_id).conditions
        sources = held.sources_of(Condition.FRIGHTENED)
        if not held.has(Condition.FRIGHTENED) or not sources:
            return True
        return any(
            self.can_see(combatant_id, source).verdict is not Visibility.CANNOT_SEE
            for source in sorted(sources)
            if self.has(source)
        ) or not any(self.has(source) for source in sources)

    def creatures_in(self, area: Area) -> tuple[str, ...]:
        """Which creatures the area reaches, in combatant order (R16, p. 177).

        Two conditions, and they are different questions. A creature must be **inside the
        volume**, and the line to it from the point of origin must not be **blocked**. A
        creature standing behind a wall inside a Fireball's radius satisfies the first and
        fails the second.

        **This is the only way to ask**, and that is 0026 clause 1 rather than a style
        choice. The composition used to live in `core.areas` and took the obstructions from
        its caller, which meant a caller could decide who a Fireball reached by deciding
        which walls existed for that one call. `Area.contains` stays pure volume — geometry
        with no opinion about walls — and the composed question lives here, where the walls
        are state.

        A combatant with no position is not reached by anything: an encounter that tracks no
        positions cannot answer a geometry question, and reporting such a creature as either
        caught or spared would be inventing the answer it cannot compute.
        """
        return tuple(
            participant.id
            for participant in self.combatants
            if participant.position is not None
            and area.contains(participant.position)
            and not line_is_blocked(area.origin, participant.position, self.obstructions)
        )

    def with_obligation_discharged(self, combatant_id: str, rule_id: str) -> EncounterState:
        """Record that this turn's obligation under that rule has been rolled.

        Discharge is about the *obligation having been met*, not about its outcome. A failed
        save discharges it exactly as a successful one does, because p. 63 gives one attempt
        per turn either way — and a death save that fails is still a death save made.

        Keyed by rule id (0027 clause 2): the two other things that discharge here have no
        condition to be keyed by.
        """
        return self._evolve(discharged=self.discharged | {(combatant_id, rule_id)})

    def forced_save_for(self, combatant_id: str) -> ForcedSave | None:
        """The oldest save this creature owes, or `None` (0036 clause 3, 0048).

        Oldest first, because the debts are one per triggering instance and the document
        gives no other order. A read, so it mutates nothing (R19) — a resolver asks it for
        the DC its rule derived, and the loop asks it whether anything is owed.
        """
        for debt in self.forced_saves_owed:
            if debt.combatant_id == combatant_id:
                return debt
        return None

    def with_forced_save(self, debt: ForcedSave) -> EncounterState:
        """Record a save a creature owes (0048).

        Appended, because the queue is ordered and one creature may owe several — a
        Multiattack landing twice with a Topple weapon compels two, and p. 90 gives no rule
        merging them.
        """
        return self._evolve(forced_saves_owed=(*self.forced_saves_owed, debt))

    def with_forced_save_discharged(self, combatant_id: str) -> EncounterState:
        """Drop the oldest save this creature owed, having rolled it.

        **Not `discharged`, and that is 0036 clause 3 rather than an oversight.** An entry
        in `discharged` means "owed once this turn, and met"; this queue means "owed once
        per triggering instance". A creature hit twice by a Multiattack owes two saves, so
        the record of having met one has to remove *one* debt rather than mark the rule met.

        Dropped whether the save succeeded, failed or was refused, exactly as
        `with_obligation_discharged` records regardless of outcome — a debt that outlived
        its adjudication would spin the loop that drains it forever.
        """
        debt = self.forced_save_for(combatant_id)
        if debt is None:
            raise ValueError(
                f"{combatant_id!r} owes no save, so there is none to discharge. The debt is "
                "recorded when the trigger fires and dropped when it is rolled, and a "
                "discharge with nothing to drop means the two have come apart"
            )
        remaining = list(self.forced_saves_owed)
        remaining.remove(debt)
        return self._evolve(forced_saves_owed=tuple(remaining))

    def with_forced_save_choice(self, combatant_id: str, ability: str) -> EncounterState:
        """Settle the ability on the oldest save this creature owes (0053 clause 3).

        The oldest, for the reason `with_forced_save_discharged` drops the oldest: the queue
        is per triggering instance, and the loop asks about the debt it is holding.

        **The choice reaches state before adjudication rather than riding the declaration.**
        A `Declaration` is the artefact the agent is accountable for and a compelled save has
        none of its own — `_obligation_declaration` authors it — so a choice carried there
        would be the engine putting words in an agent's mouth. Recorded here, the resolver
        reads the same debt it always read, and R4 is untouched: the engine still rolls.
        """
        debt = self.forced_save_for(combatant_id)
        if debt is None:
            raise ValueError(
                f"{combatant_id!r} owes no save, so there is no choice to settle. The debt is "
                "recorded when the trigger fires, and a choice with nothing to attach to "
                "means the loop and the queue have come apart"
            )
        if not debt.ability_choices:
            raise ValueError(
                f"{combatant_id!r} owes a {debt.rule_id!r} save, which names its own ability "
                f"({debt.ability!r}). Settling a choice on a save that offers none would let a "
                "caller re-ability a save the document already decided"
            )
        remaining = list(self.forced_saves_owed)
        remaining[remaining.index(debt)] = debt.with_ability(ability)
        return self._evolve(forced_saves_owed=tuple(remaining))

    def with_movement_spent(self, combatant_id: str, feet: int) -> EncounterState:
        """Charge movement for something that is not travel (p. 186, 0057).

        The mirror of `with_forced_movement`: that one moves a creature and spends nothing,
        this one spends and moves nobody. p. 186 rights a Prone creature for "an amount of
        movement equal to half your Speed (round down)", and it ends up where it started.

        Refused when there is not that much left, for the reason `with_movement` refuses an
        unaffordable step: a creature cannot spend what it does not have, and p. 186 states a
        cost rather than a discount.
        """
        target = self.combatant(combatant_id)
        remaining = target.movement_remaining_in(MovementMode.WALK)
        assert remaining is not None  # WALK always draws on Speed
        if feet > remaining:
            raise ValueError(
                f"{target.name} has {remaining} feet of movement left and that costs {feet}"
            )
        spent = replace(target, movement_used=target.movement_used + feet)
        return self._evolve(combatants=self._replacing(spent))

    def with_long_cast_begun(self, combatant_id: str, cast: LongCast) -> EncounterState:
        """Record a casting of a minute or more as started (p. 105, 0065)."""
        target = self.combatant(combatant_id)
        return self._evolve(combatants=self._replacing(replace(target, long_cast=cast)))

    def with_long_cast_continued(self, combatant_id: str) -> EncounterState:
        """One Magic action later. Clears the casting when it completes (p. 105, 0065)."""
        target = self.combatant(combatant_id)
        if target.long_cast is None:
            raise ValueError(
                f"{target.name} is not part-way through a long casting, so there is nothing "
                "to continue. p. 105's Magic action each turn belongs to a casting that has "
                "begun"
            )
        return self._evolve(
            combatants=self._replacing(replace(target, long_cast=target.long_cast.continued()))
        )

    def with_long_cast_abandoned(self, combatant_id: str) -> EncounterState:
        """The casting fails and **nothing is refunded**, because nothing was spent (p. 105)."""
        target = self.combatant(combatant_id)
        return self._evolve(combatants=self._replacing(replace(target, long_cast=None)))

    def with_forced_movement(self, combatant_id: str, to: Position) -> EncounterState:
        """Put a creature somewhere it did not walk to (0055).

        **Nothing is spent and nothing is provoked**, which is what separates this from
        `with_movement`. p. 185 provokes an Opportunity Attack when a creature "leaves your
        reach using its action, its Bonus Action, its Reaction, or one of its speeds", and a
        shove uses none of those; and no rule that pushes a creature charges the push to the
        creature's own allowance, because it is not the creature moving.

        A creature with no position cannot be pushed anywhere: an encounter tracking no
        positions has no origin to push from, and inventing one would put a creature on a map
        that does not exist.
        """
        target = self.combatant(combatant_id)
        if target.position is None:
            raise ValueError(
                f"{target.name} has no position, so there is nowhere to push it from. An "
                "encounter that tracks no positions cannot answer a question about distance, "
                "which is the honest result rather than a placed creature"
            )
        return self._evolve(combatants=self._replacing(replace(target, position=to)))

    def with_action_spent(
        self, combatant_id: str, action: ActionKind, *, weapon_id: str | None = None
    ) -> EncounterState:
        """Charge the action economy for something a ruling did (p. 176-177, p. 185).

        `ActionBudget.spend` refuses one that is not available and asks the conditions itself,
        so a caller cannot spend an action a creature does not have by forgetting to check.

        **Casting is the only thing that charges this today**, and that is a disclosed gap
        rather than a design: an attack has never cost the Action, because nothing in the
        adjudication path spent anything until #248.
        """
        target = self.combatant(combatant_id)
        spent = replace(target, actions=target.actions.spend(action, target.conditions))

        # p. 89: "When you take the **Attack action** on your turn and attack with a Light
        # weapon…" Both halves are conditions, so both are checked here: the Action rather
        # than a Bonus Action or a Reaction, and a weapon the creature is holding that is
        # actually Light. Whether it is Light is read off the weapon rather than trusted from
        # the caller, which is what keeps a ruleset from buying the extra attack by asserting
        # a property its weapon does not have.
        light = self.light_attacks_this_turn
        if weapon_id is not None and action is ActionKind.ACTION:
            wielded = next((w for w in target.weapons_held if w.id == weapon_id), None)
            if wielded is not None and wielded.light:
                light = light | {(combatant_id, weapon_id)}

        return self._evolve(combatants=self._replacing(spent), light_attacks_this_turn=light)

    def with_dash(self, combatant_id: str, feet: int) -> EncounterState:
        """p. 180: "When you take the Dash action, you gain extra movement for the current
        turn. The increase equals your Speed after applying any modifiers."

        The feet arrive from the ruling rather than being recomputed here, because p. 180
        gives the creature a **choice** — "If you have a special speed, such as a Fly Speed
        or Swim Speed, you can use that speed instead of your Speed… You choose which speed
        to use each time you take it" — and a choice recomputed at application is a choice
        the caller did not make.
        """
        if feet < 0:
            raise ValueError("Dash grants movement; a negative increase is not a Dash")
        target = self.combatant(combatant_id)
        return self._evolve(
            combatants=self._replacing(replace(target, actions=target.actions.dashed(feet)))
        )

    def with_dodge(self, combatant_id: str) -> EncounterState:
        """p. 181's Dodge, taken. Whether the benefits hold is decided by `core.actions`,
        which re-asks p. 181's two conditions rather than freezing an answer."""
        target = self.combatant(combatant_id)
        held = dodging(
            target.actions,
            target.conditions,
            target.conditions.speed_after(target.speeds.walk),
        )
        return self._evolve(combatants=self._replacing(replace(target, actions=held)))

    def with_disengage(self, combatant_id: str) -> EncounterState:
        """p. 181: "your movement doesn't provoke Opportunity Attacks for the rest of the
        current turn."

        **Nothing reads it yet**, because Opportunity Attacks are an unimplemented shape
        (p. 185). The flag is set truthfully so that the rule which eventually reads it finds
        an answer, rather than the action being offered and doing nothing — which is the
        state all three of these were in before #252.
        """
        target = self.combatant(combatant_id)
        return self._evolve(
            combatants=self._replacing(
                replace(target, actions=replace(target.actions, disengaged=True))
            )
        )

    def with_spell_slot_expended(self, combatant_id: str, slot_level: int) -> EncounterState:
        """Spend a slot to cast, and record that this turn's one slot has gone (p. 104, p. 105).

        Two rules, one transition, because they are one event. p. 104 spends the slot; p. 105
        says "On a turn, you can expend only one spell slot to cast a spell", and a caller
        able to do the first without the second would be a caller able to cast twice by
        forgetting a rule.

        `SpellSlots.expend` refuses a slot that is not there, so an overspend is an error
        rather than a negative count. Reached only through a ruling — the wrapper in
        `core.spellcasting` is what puts the effect in the branch, so a ruleset cannot cast
        for free by declining to write it (0038 clause 3).
        """
        target = self.combatant(combatant_id)
        if target.slots is None:
            raise ValueError(
                f"{target.name} has no spell slots at all, so there is none to expend. A "
                "caster's slots are ruleset data and a creature without them casts only "
                "what p. 104 puts outside the slot economy"
            )
        spent = replace(target, slots=target.slots.expend(slot_level))
        return self._evolve(
            combatants=self._replacing(spent),
            slots_expended_this_turn=self.slots_expended_this_turn | {combatant_id},
        )

    def with_concentration_begun(self, combatant_id: str, rule_id: str) -> EncounterState:
        """Begin concentrating on what that rule produced (p. 179, 0038 clause 7).

        The rule id rather than a spell name, because p. 179's replacement clause is "the
        moment you start casting a spell that requires Concentration **or activate another
        effect that requires Concentration**" — so an item-granted Concentration has to be
        expressible, and a field called `spell` could not hold one honestly (#241).

        `Concentration.begin` is p. 179's own replacement rule and does the work: whatever
        came before ends, at the moment this starts rather than when it resolves, so a caster
        cannot hold two by having the second fail.
        """
        target = self.combatant(combatant_id)
        begun = replace(target, concentration=target.concentration.begin(rule_id))
        return self._evolve(combatants=self._replacing(begun))

    def with_concentration_ended(self, combatant_id: str) -> EncounterState:
        """End what this creature was concentrating on (p. 179).

        Two callers, and the distinction matters.

        **The state half of `EffectKind.CONCENTRATION_ENDED`.** Damage breaks Concentration
        only through a failed save, so that route reaches here through a ruling and through
        nothing else — a caller able to end it directly on the damage path would be a caller
        able to decide the outcome the save exists to decide (R1).

        **The voluntary end**, which is the caller's outright: "The creator can end
        Concentration at any time *(no action required)*." Nothing is rolled, nothing is
        spent, and no rule can refuse it — so it is a transition a driver calls, not a
        declaration and not a `LegalAction`. The read surface enumerates what a creature may
        do **on its turn**; this is neither turn-bound nor an action, and a slot in which it
        were expressible would price something the document gives away.

        The two are one method because they are one state change. What separates them is who
        may call it, and R1 constrains only the first — an agent that ends its own
        Concentration has decided nothing the dice were owed.

        `Concentration.ended` is p. 179's own sentence and does the work; this holds the
        state transition and no rule of its own. Idempotent, because three routes reach the
        end and none of them can see the others.
        """
        target = self.combatant(combatant_id)
        ended = replace(target, concentration=target.concentration.ended())
        return self._evolve(combatants=self._replacing(ended))

    # --- Evolving -----------------------------------------------------------------

    def _evolve(self, **changes: Any) -> EncounterState:
        """The only way to produce a successor, and the only place the generation moves.

        `generation` is deliberately not a parameter a caller can pass. A mutator that
        forgot to bump it would leave a stale read token reading as current, which is
        the quiet direction to fail in.
        """
        changes.pop("generation", None)
        return replace(self, generation=self.generation + 1, **changes)

    def _replacing(self, *updated: Combatant) -> tuple[Combatant, ...]:
        by_id = {c.id: c for c in updated}
        return tuple(by_id.get(c.id, c) for c in self.combatants)

    def damage_after_defences(
        self, combatant_id: str, amount: int, damage_type: DamageType | None = None
    ) -> DamageOutcome:
        """What `with_damage` will actually apply to this target, and the p. 17 arithmetic.

        A read (R19): it mutates nothing and appends nothing. It exists so that the number
        a `Ruling` reports and the number the state applies come from **one** call —
        `with_damage` is written in terms of this, so the two cannot drift into disagreeing
        about the same blow.

        Answering the question separately from applying it is what lets an outcome show its
        working (R5). The alternative — letting a caller pre-adjust an amount and hand the
        result to `with_damage` — needs an "already adjusted" flag, and a flag that skips
        defences is a flag that skips defences.
        """
        return after_defences(amount, damage_type, self.combatant(combatant_id).effective_defences)

    def with_damage(
        self,
        combatant_id: str,
        amount: int,
        *,
        critical: bool = False,
        damage_type: DamageType | None = None,
    ) -> EncounterState:
        """Apply damage, including what it costs a creature already at 0 hit points.

        p. 18, "Damage at 0 Hit Points": any damage there is a Death Saving Throw failure,
        two if it came from a Critical Hit, and damage that "equals or exceeds your Hit
        Point maximum" kills outright. Damage also ends Stable — "it stops being Stable and
        starts making Death Saving Throws again".

        These live here rather than in a caller for the same reason the thresholds do. A
        caller able to deal damage to a dying creature *without* the failure would be a
        caller able to keep it alive by forgetting a rule, which is the exact failure this
        engine exists to remove.
        """
        if amount < 0:
            raise ValueError("damage is not negative; healing is a separate change")
        target = self.combatant(combatant_id)

        # Defences resolve before anything else looks at the number. Everything downstream
        # — the death save failure for "any damage", and Massive Damage's remainder — is
        # about damage *taken*, so a creature immune to Fire takes none and suffers none of
        # it. Applying them after would charge a failure for damage that never landed.
        amount = self.damage_after_defences(combatant_id, amount, damage_type).amount
        before = target.hit_points

        reduced = replace(target, hit_points=max(0, before - amount))

        # p. 179, "Damage": damage taken by a concentrating creature compels a Constitution
        # save. **Recorded here, rolled nowhere near here** (0036 clause 2). Detection
        # belongs where the triggering thing happens — 0023 clause 5's principle — but that
        # clause put its whole mechanic in this method *because it is not a save*. This one
        # is, and rolling it here would make `core.state` produce a result, which is the one
        # thing R1 forbids however convenient the call site. So this appends a debt and the
        # turn loop discharges it through the one adjudication entry point.
        #
        # After defences, deliberately, and for the reason stated above for the death save:
        # p. 179 says "the damage taken", so a creature Immune to the type takes none and
        # owes none. `ConcentrationDebt` refuses an amount of 0 rather than trusting this.
        #
        # The **stored** field, which is now the only answer there is (0037 clause 4). This
        # read `after_conditions` until #238, deliberately, so that state and the read
        # surface would agree about who is concentrating. They agreed and were wrong
        # together: after an Incapacitated condition lifted, the derivation handed the spell
        # back and this compelled a save to maintain something p. 179 had already ended.
        owed = self.forced_saves_owed
        if amount > 0 and target.concentration.active:
            # 0048: the DC and its derivation are computed **here**, where the trigger fires,
            # rather than carried as a damage amount for the resolver to convert. 0036 clause
            # 4's reason for carrying the amount reaches one step further — by the time the
            # loop rolls this, the hit points the DC came from have moved, often more than
            # once — and it is what lets one queue serve rules whose DCs come from different
            # things entirely.
            test = concentration_save(amount)
            owed = (
                *owed,
                ForcedSave(
                    combatant_id=combatant_id,
                    rule_id=CONCENTRATION_RULE_ID,
                    ability=CONCENTRATION_SAVE_ABILITY,
                    dc=test.target,
                    dc_basis=test.target_basis,
                    label=(
                        f"makes a Constitution save to maintain Concentration, having taken "
                        f"{amount} damage (p. 179)"
                    ),
                ),
            )

        state = self._evolve(combatants=self._replacing(reduced), forced_saves_owed=owed)
        if amount == 0 or reduced.hit_points > 0 or target.death_saves.dead:
            return state

        # p. 17, "Monster Death": a monster dies the instant it drops to 0.
        if not target.is_player_character:
            return state.with_death(combatant_id)

        # p. 17, "Massive Damage": death if the damage **remaining** after the character
        # is reduced to 0 equals or exceeds their hit point maximum. The remainder, not
        # the whole blow — a character on 6 of 12 killed by 18 is the document's own
        # example, and comparing the full amount instead would kill them on 12.
        remainder = amount - before
        if remainder >= target.max_hit_points:
            return state.with_death(combatant_id)

        # p. 18, "Damage at 0 Hit Points". Only for a character already there: being
        # reduced to 0 this turn starts the saves, it does not also fail one.
        if before > 0:
            return state

        # Stable ends first, or the failure would be recorded against a creature the
        # engine still believes is not making saves (p. 18, "Stabilizing a Character").
        if target.death_saves.stable:
            state = state._evolve(
                combatants=state._replacing(
                    replace(state.combatant(combatant_id), death_saves=DeathSaves())
                )
            )
        return state.with_death_save(combatant_id, failures=2 if critical else 1)

    def with_healing(self, combatant_id: str, amount: int) -> EncounterState:
        """Heal, and clear any death saves the healing made irrelevant.

        p. 17: "The number of both is reset to zero when you regain any Hit Points or
        become Stable." Regaining *any* hit points, so a single point clears the record —
        and the reset is here rather than at the call sites because a caller that healed
        without clearing would leave a revived creature two failures from dying.
        """
        if amount < 0:
            raise ValueError("healing is not negative; damage is a separate change")
        target = self.combatant(combatant_id)
        healed = min(target.max_hit_points, target.hit_points + amount)
        restored = replace(
            target,
            hit_points=healed,
            death_saves=DeathSaves() if amount > 0 else target.death_saves,
        )
        return self._evolve(combatants=self._replacing(restored))

    def with_death_save(
        self,
        combatant_id: str,
        *,
        successes: int = 0,
        failures: int = 0,
        seed: int | None = None,
    ) -> EncounterState:
        """Record a death save, and apply the thresholds it may have crossed.

        The thresholds live here rather than in the caller because reaching three is not a
        second decision — p. 17 states it as a consequence of the third mark, so a caller
        able to record a third failure without the creature dying would be a caller able
        to invent a survival.

        `seed` is needed only on the mark that reaches the third success, because becoming
        Stable rolls the 1d4 that fixes when the creature recovers (p. 18). A stabilisation
        without one is refused rather than left without a recovery time: a Stable creature
        silently missing its deadline is a creature that never wakes up, which is the quiet
        direction to fail in.
        """
        target = self.combatant(combatant_id)
        saves = target.death_saves
        if saves.is_resolved:
            return self

        total_successes = saves.successes + successes
        total_failures = saves.failures + failures
        stable = total_successes >= DEATH_SAVE_THRESHOLD
        dead = total_failures >= DEATH_SAVE_THRESHOLD

        updated = DeathSaves(
            successes=0 if stable else total_successes,
            failures=total_failures if not stable else 0,
            stable=stable and not dead,
            dead=dead,
            recovers_at_minute=(self._recovery_minute(seed) if stable and not dead else None),
        )
        return self._evolve(combatants=self._replacing(replace(target, death_saves=updated)))

    def with_stabilised(self, combatant_id: str, *, seed: int | None = None) -> EncounterState:
        """Stable, and the counts reset with it — p. 17 resets on becoming Stable too.

        Becoming Stable also fixes when the creature regains 1 hit point (p. 18), so `seed`
        is required here for the same reason it is on the third success.
        """
        target = self.combatant(combatant_id)
        if target.death_saves.dead:
            return self
        return self._evolve(
            combatants=self._replacing(
                replace(
                    target,
                    death_saves=DeathSaves(
                        stable=True, recovers_at_minute=self._recovery_minute(seed)
                    ),
                )
            )
        )

    def _recovery_minute(self, seed: int | None) -> int:
        """When a creature becoming Stable *now* would regain 1 hit point.

        Rolled at stabilisation rather than when the clock is read. Rolling it on demand
        would let a caller advance the clock an hour at a time and re-draw until it got the
        answer it wanted — the same re-draw `core.d20` prevents by banding its seed space.
        """
        if seed is None:
            raise ValueError(
                "becoming Stable rolls 1d4 hours to recovery (p. 18), so it needs the "
                "adjudication's seed; a Stable creature without a recovery time never wakes"
            )
        return stable_recovery_minute(self.clock, seed=seed)

    # --- Conditions and their durations (#18) -----------------------------------------

    def _next_turn_end_round(self, actor_id: str) -> int:
        """The round in which that creature's *next* turn ends.

        Its turn is still to come this round only if it sits later in the order than the
        creature acting now. If it is acting now, its next turn is the following round —
        which is what Rage (p. 29) means by lasting "until the end of your next turn" when
        you started it on your own turn.
        """
        if self.turn_index is None:
            raise ValueError(
                "a duration measured in turns needs a turn order; roll initiative first"
            )
        index = next((i for i, c in enumerate(self.combatants) if c.id == actor_id), None)
        if index is None:
            raise ValueError(f"{actor_id!r} is not in this encounter, so it has no next turn")
        return self.round_number + (0 if index > self.turn_index else 1)

    def until_end_of_next_turn(self, actor_id: str, *, save: SaveEnds | None = None) -> Duration:
        """ "Until the end of your next turn" (p. 29 and 61 others), as an expiry point."""
        return Duration(
            kind=DurationKind.END_OF_NEXT_TURN,
            ends_after_round=self._next_turn_end_round(actor_id),
            ends_after_actor_id=actor_id,
            save=save,
        )

    def for_rounds(
        self,
        count: int,
        actor_id: str,
        *,
        save: SaveEnds | None = None,
        stated: StatedSpan | None = None,
    ) -> Duration:
        """A time span in rounds (p. 106), anchored to a creature's place in the order.

        p. 98 is the only place the document says what counting rounds from an event means:
        the oil burns "until the end of the turn 2 rounds from when the oil was lit". So the
        span ends at that same point in the order, `count` rounds later.
        """
        if count < 0:
            raise ValueError("a duration is not negative")
        return Duration(
            kind=DurationKind.ROUNDS,
            ends_after_round=self.round_number + count,
            ends_after_actor_id=actor_id,
            save=save,
            stated=stated,
        )

    def for_minutes(self, minutes: int, actor_id: str, *, save: SaveEnds | None = None) -> Duration:
        """A span stated in minutes, converted to rounds once, here (0021 clauses 3 and 4).

        Converting at application rather than on query is 0020 clause 4's reasoning: a value
        re-derived whenever somebody asks is a value a caller can re-draw by choosing when to
        ask. `stated` keeps what was said, so the conversion is visible in the derivation
        rather than implied by a round count nobody can trace.

        The clock is not consulted and does not move. Knowing a round is six seconds is not
        knowing how much campaign time has passed (0021 clause 2).
        """
        return self.for_rounds(
            rounds_in_minutes(minutes),
            actor_id,
            save=save,
            stated=StatedSpan(minutes, SpanUnit.MINUTES),
        )

    def for_hours(self, count: int, *, save: SaveEnds | None = None) -> Duration:
        """A span stated in hours, as a minute on the campaign clock (#111).

        No creature is named, because the campaign axis has no turn order to anchor to —
        the span ends when the clock says so, whoever is acting. `with_time_passed` is what
        retires it, and nothing in an encounter will: taking a turn does not move the clock
        (0021 clause 2), so an eight-hour condition correctly survives the whole fight.
        """
        return self._on_the_clock(StatedSpan(count, SpanUnit.HOURS), save=save)

    def for_days(self, count: int, *, save: SaveEnds | None = None) -> Duration:
        """A span stated in days. `clock.HOURS_PER_DAY` carries why a day is 24 hours."""
        return self._on_the_clock(StatedSpan(count, SpanUnit.DAYS), save=save)

    def _on_the_clock(self, stated: StatedSpan, *, save: SaveEnds | None) -> Duration:
        """A campaign-axis expiry point, resolved against the clock once, at application.

        The minute stored is absolute rather than remaining, for 0020 clause 4's reason: a
        remaining count would have to be re-derived every time the clock moved, and a value
        re-derived on query is one a caller can re-draw by choosing when to ask.
        """
        return Duration(
            kind=DurationKind.CAMPAIGN_TIME,
            ends_at_minute=self.clock.elapsed_minutes + stated.in_minutes,
            save=save,
            stated=stated,
        )

    def with_condition(
        self,
        combatant_id: str,
        condition: Condition,
        *,
        duration: Duration | None = None,
        source_id: str | None = None,
        grapple: Grapple | None = None,
    ) -> EncounterState:
        """Apply a condition, with the duration the effect that imposed it stated.

        `None` means the effect named no span this engine can count, and it is recorded as
        such rather than as permanent — `Conditions.unretirable` reports it, so a condition
        nothing will ever lift is visible instead of merely never lifting.
        """
        target = self.combatant(combatant_id)
        held = target.conditions
        durations = dict(held.durations)
        if duration is not None:
            durations[condition] = duration
        else:
            durations.pop(condition, None)
        # p. 183: Immunity to a condition means it "doesn't affect you in any way", so the
        # application is a **no-op** rather than an error — p. 186's Petrified is Immune to
        # Poisoned, and a rule that tries to poison a statue is not a caller's mistake (#357).
        if condition is Condition.POISONED and held.immune_to_poisoned:
            return self

        # A condition does not stack (p. 179), so a second application adds its source to
        # the one condition rather than making a second — #192.
        sources = dict(held.sources)
        if source_id is not None:
            sources[condition] = sources.get(condition, frozenset()) | {source_id}
        updated = Conditions(
            held=held.applied | {condition},
            exhaustion_levels=held.exhaustion_levels,
            sources=sources,
            durations=durations,
            # Carried forward, not rebuilt from the argument: applying *any* condition to a
            # grappled creature would otherwise erase the grapple's escape DC, which is the
            # number p. 182's escape check is rolled against. `grapple` overrides only when
            # the effect that imposed this condition stated terms — which is the Grapple
            # option and nothing else.
            grapple=grapple if grapple is not None else held.grapple,
        )
        return self._evolve(combatants=self._replacing(replace(target, conditions=updated)))

    def with_exhaustion(self, combatant_id: str, rule_id: str, levels: int = 1) -> EncounterState:
        """Raise this creature's Exhaustion level (p. 181, #178).

        "This condition is cumulative. Each time you receive it, you gain 1 Exhaustion
        level." So this adds rather than sets, and the condition follows from the level
        being above zero rather than being applied alongside it — `Conditions` already
        derives that.

        **Six is death, and seven is nothing.** p. 181 says "You die if your Exhaustion
        level is 6", so a level of 6 is a state the rules describe and 7 is not. A gain
        that would pass 6 is refused rather than clamped: clamping would silently discard
        the caller's arithmetic, and no SRD rule grants more than one level at a time, so
        reaching this is a caller doing something the document does not describe.

        Nothing here decides *who may remove* what it adds, which is the harder half. p. 181
        has a Long Rest remove one level; p. 189 has breathing again remove every level
        suffocation caused; pp. 181 and 185 have dehydration's and malnutrition's levels
        removable by nothing until the creature drinks or eats. One integer cannot say which
        of a creature's levels are which, and that is
        [#180](https://github.com/eddiefiggie/srd-rules-engine/issues/180) rather than a
        field.
        """
        if levels < 1:
            raise ValueError(
                f"an Exhaustion gain is at least one level; {levels} is not a gain. "
                "Removal runs by its own rules and is not a negative gain (0028 clause 2)"
            )
        if not rule_id:
            raise ValueError(
                "an Exhaustion level names the rule that caused it (0028 clause 1), because "
                "four of the five rules that remove one turn on which level it is"
            )
        target = self.combatant(combatant_id)
        held = target.conditions.exhaustion_levels
        if len(held) + levels > MAX_EXHAUSTION:
            raise ValueError(
                f"{target.name} is at Exhaustion level {len(held)} and gaining {levels} "
                f"would reach {len(held) + levels}. p. 181 says a creature dies at "
                f"{MAX_EXHAUSTION}, so nothing above it is a state the document describes"
            )
        return self._evolve(
            combatants=self._replacing(
                replace(
                    target,
                    conditions=replace(
                        target.conditions, exhaustion_levels=held + (rule_id,) * levels
                    ),
                )
            )
        )

    def with_exhaustion_removed(self, combatant_id: str, *, caused_by: str) -> EncounterState:
        """Remove every Exhaustion level that rule caused (0028 clause 2).

        p. 189's shape: "When a creature can breathe again, it removes all levels of
        Exhaustion it gained from suffocating." Scoped to one rule's levels and silent about
        every other, which is why a count could not answer it.

        **Removal is a rule rather than a subtraction**, so this takes the rule whose levels
        go rather than a number of levels to drop. A caller that could say "remove two" would
        be choosing which two, and the four removal rules disagree about that.

        Removing nothing is not an error: a creature that breathes again having never
        suffocated has lost nothing, and refusing would make the caller check first.
        """
        target = self.combatant(combatant_id)
        remaining = tuple(r for r in target.conditions.exhaustion_levels if r != caused_by)
        if len(remaining) == len(target.conditions.exhaustion_levels):
            return self
        return self._evolve(
            combatants=self._replacing(
                replace(
                    target,
                    conditions=replace(target.conditions, exhaustion_levels=remaining),
                )
            )
        )

    def with_day_ended(
        self, *, water: Mapping[str, Fraction], food: Mapping[str, Fraction] | None = None
    ) -> EncounterState:
        """p. 181's Dehydration, at the day's end (#315, 0080).

        > A creature that drinks less than half the required water for a day gains 1
        > Exhaustion level at the day's end. Exhaustion caused by dehydration can't be removed
        > until the creature drinks the full amount of water required for a day.

        **The caller says how much each creature drank**, which is a narrative fact only the
        agent holds — the same contract `with_time_passed` states for how much time passed.
        The engine decides every consequence of it.

        **Deterministic bookkeeping, and no die** (R1, R4). p. 181 attaches no saving throw:
        the level is gained outright, so this is a state transition rather than an
        adjudication. Malnutrition is the opposite case and is deliberately not here — p. 185
        compels a DC 10 Constitution save, which needs an occasion that can produce a *ruling*
        on the campaign axis. That occasion does not exist and is
        [#399](https://github.com/eddiefiggie/srd-rules-engine/issues/399).

        **A creature named without a stated size is refused**, not skipped. p. 181's
        requirement is read from a size table, so a sizeless creature has no requirement to
        compare against — and passing over it silently would report a day in which nobody was
        thirsty (0051's refusal rather than a comparison against a Medium nobody stated).

        **Only creatures the caller names are considered.** A day ending is not a claim about
        every creature in the encounter, and inventing a consumption of zero for the rest
        would dehydrate every bystander.

        **The removal restriction needs nothing here.** `LOCKED_EXHAUSTION_RULES` already
        holds `DEHYDRATION_RULE_ID`, so `with_long_rest` cannot take a level this applies —
        the lock was built ahead of the hazard by 0028 clause 3, and this is the first hazard
        to put a level behind it.
        """
        missing = [cid for cid in water if not self.has(cid)]
        if missing:
            raise KeyError(f"no combatant {missing[0]!r} in this encounter")
        sizeless = [cid for cid in sorted(water) if self.combatant(cid).size is None]
        if sizeless:
            raise ValueError(
                f"{', '.join(sizeless)} has no stated size, and p. 181 reads a day's water "
                "from the Water Needs per Day table. A creature of unknown size has no "
                "requirement to have drunk less than half of"
            )

        eaten = food or {}
        missing_food = [cid for cid in eaten if not self.has(cid)]
        if missing_food:
            raise KeyError(f"no combatant {missing_food[0]!r} in this encounter")
        unsized = [cid for cid in sorted(eaten) if self.combatant(cid).size is None]
        if unsized:
            raise ValueError(
                f"{', '.join(unsized)} has no stated size, and p. 185 reads a day's food from "
                "the Food Needs per Day table"
            )

        state = self
        for combatant_id in sorted(water):
            size = self.combatant(combatant_id).size
            assert size is not None  # refused above
            if dehydrated(size, water[combatant_id]):
                state = state.with_exhaustion(combatant_id, DEHYDRATION_RULE_ID)

        # p. 185's Malnutrition **compels a save rather than inflicting a level** (#399,
        # 0081), which is the whole difference from p. 181. Compelled here and rolled by
        # `TurnLoop.end_day`, through the machinery 0048 generalised: a `ForcedSave` is "one
        # save a creature owes and has not rolled, whatever compelled it", and this is the
        # third thing to compel one.
        #
        # **The DC is recorded now**, which 0036 clause 4 requires of every forced save: by
        # the time the loop rolls it, the state it came from has moved. Here it is a constant,
        # and recording it anyway keeps the one rule rather than an exception to it.
        for combatant_id in sorted(eaten):
            size = self.combatant(combatant_id).size
            assert size is not None  # refused above
            if undernourished(size, eaten[combatant_id]):
                state = state.with_forced_save(
                    ForcedSave(
                        combatant_id=combatant_id,
                        rule_id=MALNUTRITION_RULE_ID,
                        ability="con",
                        dc=MALNUTRITION_SAVE_DC,
                        dc_basis=(
                            f"DC {MALNUTRITION_SAVE_DC} Constitution saving throw, stated "
                            "outright by p. 185 rather than derived"
                        ),
                        label="the save p. 185 compels for a day's food (Malnutrition)",
                    )
                )
        return state

    def with_long_rest(self, combatant_id: str) -> EncounterState:
        """Finish a Long Rest, and apply the benefits this engine can express (p. 185).

        **Two of the four, and the other two are absent rather than skipped.**

        * *Regain All HP* — every lost hit point comes back. The same sentence restores
          spent Hit Point Dice and a reduced hit point maximum, and this engine models
          neither, so two thirds of one benefit is missing and disclosed.
        * *Exhaustion Reduced* — "its level decreases by 1". This is 0028's general removal
          rule, and it is the reason this method exists: without a rest, Exhaustion was a
          mechanic that only ever accumulated (#185).
        * *Ability Scores Restored* is not modelled, because nothing reduces an ability
          score.
        * *Special Feature* recharge is not modelled, because no feature has a recharge.

        **Spell slots come back**, and that sentence is not on p. 185 at all — p. 104 carries
        it: "Finishing a Long Rest restores any expended spell slots." `SpellSlots.restored`
        existed from #95 with a docstring saying nothing triggered it because there was no
        rest. There was a rest from #185, and this did not call it for a build: a benefit the
        document states, absent from the one method that exists to apply them (#19).

        **A creature at 0 hit points cannot start one.** p. 185: "To start a Long Rest, you
        must have at least 1 Hit Point." Every other benefit reads as unconditional, which is
        why this precondition is the one an implementation drops — and dropping it would let
        a dying creature rest itself back to full.

        **The level it removes is the most recently gained one that is not locked** (0028
        clauses 3 and 4). p. 181 never says *which* level goes, so the order is this engine's
        convention and is declared as one. Locked levels — dehydration's and malnutrition's —
        are not candidates at all, so a creature holding only those loses nothing.

        **Timing is not enforced.** The rest is "at least 8 hours" and another may not start
        for 16 more (p. 185); neither is checked here, and no clock advances. The caller
        advances campaign time with `with_time_passed`, which is where elapsing has its own
        consequences. Interruptions (p. 185) are not modelled either.
        """
        target = self.combatant(combatant_id)
        if target.is_down:
            raise ValueError(
                f"{target.name} has 0 hit points and cannot start a Long Rest — p. 185 "
                "requires at least 1. A creature this far gone is stabilised or dies; it "
                "does not rest"
            )

        restored = replace(
            target,
            hit_points=target.max_hit_points,
            # p. 104, not p. 185. A caster with no slots is left as one.
            slots=target.slots.restored() if target.slots is not None else None,
        )
        held = restored.conditions.exhaustion_levels
        removable = [i for i, rule in enumerate(held) if rule not in LOCKED_EXHAUSTION_RULES]
        if removable:
            # 0028 clause 4: most recently gained first, and that is a convention rather
            # than a rule the document supplies.
            drop = removable[-1]
            restored = replace(
                restored,
                conditions=replace(
                    restored.conditions,
                    exhaustion_levels=held[:drop] + held[drop + 1 :],
                ),
            )

        return self._evolve(combatants=self._replacing(restored))

    def with_breath_regained(self, combatant_id: str) -> EncounterState:
        """p. 189: the creature can breathe again, and every level suffocation caused goes.

        Deterministic bookkeeping rather than an outcome, and no die is thrown — the same
        rule `with_time_passed` states for what it applies. p. 189 removes the levels
        outright and offers no save, so arriving at air decides nothing that was not already
        decided.

        It resolves here rather than through a turn-loop occasion because "can breathe
        again" is an event rather than a schedule: 0023 clause 5, applied the way 0027
        clause 7 applied it to Falling. The caller says when, because air is a narrative
        fact this engine cannot observe.

        Levels from any other source stay, which is the whole point of 0028 clause 1 — a
        creature that suffocated *and* marched through the night keeps the march.
        """
        target = self.combatant(combatant_id)
        cleared = replace(target, hazards=replace(target.hazards, suffocating=False))
        return self._evolve(combatants=self._replacing(cleared)).with_exhaustion_removed(
            combatant_id, caused_by=SUFFOCATION_RULE_ID
        )

    def with_condition_ended(self, combatant_id: str, condition: Condition) -> EncounterState:
        """End a condition now — a successful save, or an effect that removes it.

        Implication is recomputed rather than subtracted, and p. 191's "when this condition
        ends, you remain Prone" survives it. Both live in `Conditions.without`.
        """
        target = self.combatant(combatant_id)
        remaining = target.conditions.without(frozenset({condition}))
        return self._evolve(combatants=self._replacing(replace(target, conditions=remaining)))

    def with_attack_made(self, combatant_id: str) -> EncounterState:
        """Count one attack roll against this turn's Multiattack allowance (0043 clause 4)."""
        tally = dict(self.attacks_this_turn)
        tally[combatant_id] = tally.get(combatant_id, 0) + 1
        return self._evolve(attacks_this_turn=tally)

    def with_ammunition_spent(self, combatant_id: str, item_id: str) -> EncounterState:
        """Spend one piece of ammunition and count it against this fight (p. 89, #273).

        "Each attack expends one piece of ammunition." Spending the last one **removes the
        entry**, because `Carried` means the creature has the thing and nought arrows is not
        a kind of carrying (0044 clause 1).

        The used-tally is not decremented alongside it: it counts what was spent in this
        fight, and that only ever goes up (0044 clause 6).
        """
        target = self.combatant(combatant_id)
        held = next((c for c in target.equipment if c.item.id == item_id), None)
        if held is None:
            raise ValueError(
                f'{combatant_id} has no {item_id!r} to fire. p. 89 allows the attack "only '
                'if you have ammunition to fire from it", so the read surface never offered '
                "this — spending what is not there would fire a shot from nothing"
            )
        remaining = tuple(
            replace(carried, quantity=carried.quantity - 1)
            if carried.item.id == item_id
            else carried
            for carried in target.equipment
            # The last piece takes the entry with it, rather than leaving a zero.
            if not (carried.item.id == item_id and carried.quantity == 1)
        )
        tally = dict(self.ammunition_used)
        tally[(combatant_id, item_id)] = tally.get((combatant_id, item_id), 0) + 1
        return self._evolve(
            combatants=self._replacing(replace(target, equipment=remaining)),
            ammunition_used=tally,
        )

    def with_ammunition_recovered(
        self, combatant_id: str, item_id: str, pieces: int
    ) -> EncounterState:
        """Return recovered pieces and close the fight's tally for them (p. 89, #301).

        > After a fight, you can spend 1 minute to recover **half the ammunition (round down)
        > you used in the fight**; the rest is lost.

        **The tally clears whatever the half came to**, because "the rest is lost" — a
        creature that used one piece recovers none and has nothing left to recover later.
        Leaving the tally would let a second minute recover from the same fight.

        Recovered pieces arrive **stowed**, which is 0039 clause 3's residual: p. 89 does not
        say where they go, and stowed is the carriage that commits no hands and asserts
        nothing. A creature that still has some gets more of them; one that spent the lot gets
        the entry back.

        **And a creature that spent the lot gets an `Item` carrying only its id** (R32). The
        last piece took the entry with it, so the weight and hand count are gone unless a
        detached object still names them. Nothing reads either today — p. 178's carrying
        capacity is blocked on a `Size` this engine does not have
        ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) — and the
        alternative is refusing a recovery p. 89 allows, or holding a registry of every item
        a creature ever had.
        """
        target = self.combatant(combatant_id)
        tally = dict(self.ammunition_used)
        tally.pop((combatant_id, item_id), None)
        if pieces < 1:
            return self._evolve(ammunition_used=tally)

        held = next((c for c in target.equipment if c.item.id == item_id), None)
        if held is not None:
            equipment = tuple(
                replace(c, quantity=c.quantity + pieces) if c.item.id == item_id else c
                for c in target.equipment
            )
        else:
            recovered = next(
                (o.item for o in self.detached_objects if o.item.id == item_id), None
            ) or Item(id=item_id)
            equipment = (*target.equipment, Carried(recovered, Carriage.STOWED, quantity=pieces))
        return self._evolve(
            combatants=self._replacing(replace(target, equipment=equipment)),
            ammunition_used=tally,
        )

    def recoverable_ammunition(self, combatant_id: str) -> Mapping[str, int]:
        """How much of each kind a minute would recover (p. 89). Half, rounding down."""
        return {
            item: used // 2
            for (who, item), used in self.ammunition_used.items()
            if who == combatant_id
        }

    def ammunition_for(self, combatant_id: str, item_id: str) -> int:
        """How many pieces of that ammunition the creature has (p. 89). Zero if none."""
        target = self.combatant(combatant_id)
        return next((c.quantity for c in target.equipment if c.item.id == item_id), 0)

    def with_loading_shot(self, combatant_id: str, action: str) -> EncounterState:
        """Record that a Loading weapon has been fired with that action (p. 90, #271)."""
        return self._evolve(
            loading_shots_this_turn=self.loading_shots_this_turn | {(combatant_id, action)}
        )

    def has_fired_loading(self, combatant_id: str, action: str) -> bool:
        """Whether p. 90's one shot is already spent for that action."""
        return (combatant_id, action) in self.loading_shots_this_turn

    def with_object_interaction(self, combatant_id: str) -> EncounterState:
        """Record this turn's one object interaction as spent (0045 clause 1).

        Either route spends it — p. 177's swap during an attack, or p. 13's free interaction
        on its own — because the engine treats them as one allowance.
        """
        return self._evolve(
            object_interactions_this_turn=self.object_interactions_this_turn | {combatant_id}
        )

    def with_cleave_opening(
        self, combatant_id: str, weapon_id: str, first_target_id: str
    ) -> EncounterState:
        """Record a melee hit that opened p. 90's Cleave (#323).

        Whether the weapon is Cleave-carrying and whether the wielder may use the property
        were both settled where the hit landed; this only remembers that it happened, and
        against whom.
        """
        return self._evolve(
            cleave_openings_this_turn=self.cleave_openings_this_turn
            | {(combatant_id, weapon_id, first_target_id)}
        )

    def with_cleave_taken(self, combatant_id: str) -> EncounterState:
        """Record p. 90's one Cleave a turn as spent (#323)."""
        return self._evolve(cleaves_this_turn=self.cleaves_this_turn | {combatant_id})

    def has_cleaved(self, combatant_id: str) -> bool:
        """Whether p. 90's one Cleave a turn is already spent (#323)."""
        return combatant_id in self.cleaves_this_turn

    def cleave_openings(self, combatant_id: str) -> tuple[tuple[str, str], ...]:
        """The (weapon, creature hit) pairs this creature's melee hits opened this turn."""
        return tuple(
            (weapon_id, first_target_id)
            for who, weapon_id, first_target_id in sorted(self.cleave_openings_this_turn)
            if who == combatant_id
        )

    def with_speed_reduction(self, combatant_id: str, reduction: SpeedReduction) -> EncounterState:
        """Impose a Speed reduction that stands until its boundary (p. 90, #322)."""
        target = self.combatant(combatant_id)
        slowed = replace(target, speed_reductions=(*target.speed_reductions, reduction))
        return self._evolve(combatants=self._replacing(slowed))

    def with_extra_attack(self, combatant_id: str) -> EncounterState:
        """Record p. 89's one extra Light attack as taken (#320).

        Either route spends it — the Bonus Action one or p. 90's Nick — because p. 89 grants
        one extra attack and p. 90 re-routes that same attack rather than adding another.
        """
        return self._evolve(extra_attacks_this_turn=self.extra_attacks_this_turn | {combatant_id})

    def has_taken_extra_attack(self, combatant_id: str) -> bool:
        """Whether p. 89's extra attack is already spent this turn (#320)."""
        return combatant_id in self.extra_attacks_this_turn

    def with_pending_advantage(self, token: PendingAdvantage) -> EncounterState:
        """Record Advantage or Disadvantage a rule granted for a later roll (0049)."""
        return self._evolve(pending_advantage=(*self.pending_advantage, token))

    def live_pending_advantage(self) -> tuple[PendingAdvantage, ...]:
        """The tokens the encounter has not yet passed the expiry of (0049).

        Derived rather than swept, so a token cannot outlive its window even if the sweep
        below never ran. The order is the recording order, which is the only one p. 90 gives.
        """
        order = tuple(c.id for c in self.combatants)
        return tuple(
            token
            for token in self.pending_advantage
            if is_live(
                token,
                round_number=self.round_number,
                turn_index=self.turn_index,
                order=order,
            )
        )

    def pending_advantage_for(
        self, attacker_id: str, target_id: str
    ) -> tuple[PendingAdvantage, ...]:
        """The live tokens in scope for that attack, which the roll will spend (0049)."""
        return tuple(
            token
            for token in self.live_pending_advantage()
            if token.applies_to(attacker_id, target_id)
        )

    def without_pending_advantage(self, spent: tuple[PendingAdvantage, ...]) -> EncounterState:
        """Drop tokens a roll consumed (0049).

        Spent whether the roll hit or missed: p. 90 says "your **next** attack roll", and a
        token that survived a miss would grant Advantage on every attack in the window.
        """
        remaining = [token for token in self.pending_advantage if token not in spent]
        return self._evolve(pending_advantage=tuple(remaining))

    def can_fire(self, combatant_id: str, weapon: Weapon) -> bool:
        """Whether p. 89's Ammunition property permits this shot (#273).

        > You can use a weapon that has the Ammunition property to make a ranged attack
        > **only if you have ammunition to fire from it**… Drawing the ammunition is part of
        > the attack (you need a free hand to load a one-handed weapon).

        Both halves are conditions of the attack, so they are **legality** rather than a
        refusal after the fact (R18) — the shot is not offered. The resolver asks the same
        question, because a caller reaching adjudication directly must not escape it (#376).

        **Here rather than in `core.read_surface`**, where it lived until #376. The read
        surface is imported *by* the attack resolver and cannot import it back, so a predicate
        both need has to live where the state does — which is also where 0056 put a movement
        refusal, for the same reason.

        **An unknown hand count does not refuse it.** `Combatant.__post_init__` already
        settles this direction for p. 90's Two-Handed: "no SRD rule states how many hands a
        creature has, so an unstated count cannot be exceeded (R31)." Only a *known* zero
        blocks the load, and refusing on `None` would assert the count the engine declines to
        assume (0039 clause 4).
        """
        if weapon.ammunition_id is None:
            return True
        actor = self.combatant(combatant_id)
        if not self.ammunition_for(combatant_id, weapon.ammunition_id):
            return False
        # `== 0` and not `not ...`: `free_hands` is `int | None`, and `None` means the count
        # is unstated rather than exhausted.
        return not (weapon.hands_when_held == 1 and actor.free_hands == 0)

    def attacks_remaining(self, combatant_id: str) -> int:
        """How many attack rolls this creature's Attack action still buys (p. 257).

        One for a creature with no Multiattack, which is the pre-existing behaviour and the
        reason a ruleset that says nothing keeps exactly what it had. Never negative.
        """
        target = self.combatant(combatant_id)
        bought = target.multiattack.attacks if target.multiattack is not None else 1
        return max(0, bought - self.attacks_this_turn.get(combatant_id, 0))

    def with_object_detached(self, combatant_id: str, item_id: str) -> EncounterState:
        """Take one item off a creature and leave it in the encounter (0041 clause 7, #280).

        The item stops being the creature's — it leaves `equipment` entirely rather than
        acquiring a fourth `Carriage` — and arrives in `detached_objects` **with no
        position**, because five printed rules detach an item and none says where it lands
        (0041 clause 4). p. 217's Dancing Sword is the only text in the document that ever
        places a released weapon, and it is a magic item stating its own outcome.

        The `Item` is carried across unchanged: p. 191 calls a weapon an object and p. 12
        lists a sword among its examples, so nothing here changes type (0041 clause 1).

        **The carriage is not consulted.** Which items a rule sheds is the rule's business —
        p. 191 sheds what is *held*, and a rule that shed a stowed thing would be no less
        expressible. Refusing an item the creature does not have is a different matter: that
        is a caller naming something that is not there, and inventing an object out of it
        would put a sword on the floor that never existed.
        """
        target = self.combatant(combatant_id)
        remaining = tuple(c for c in target.equipment if c.item.id != item_id)
        if len(remaining) == len(target.equipment):
            raise ValueError(
                f"{combatant_id} has no item {item_id!r} to let go of. Detaching one it does "
                "not have would create an object from nothing, which is the direction that "
                "quietly adds a weapon to the floor"
            )
        detached = next(c.item for c in target.equipment if c.item.id == item_id)
        return self._evolve(
            combatants=self._replacing(replace(target, equipment=remaining)),
            detached_objects=(*self.detached_objects, DetachedObject(detached)),
        )

    def with_carriage_changed(
        self, combatant_id: str, item_id: str, carriage: Carriage
    ) -> EncounterState:
        """Move one item between the carriages the creature already has it in (p. 177).

        "Equipping a weapon includes **drawing it from a sheath**… Unequipping a weapon
        includes **sheathing, stowing**" — both are the item staying with the creature and
        changing how it is kept, which is exactly what `Carriage` models (0039 clause 3).

        Dropping and picking up are not this: they cross the creature's boundary and are
        `with_object_detached` and `with_object_picked_up`.

        The grip is cleared on the way out of `HELD`, because `Carried.__post_init__`
        refuses one on an item that commits no hands — a stowed weapon has no grip to keep.
        """
        target = self.combatant(combatant_id)
        if not any(c.item.id == item_id for c in target.equipment):
            raise ValueError(
                f"{combatant_id} has no item {item_id!r} to move. Changing the carriage of "
                "one it does not have would conjure the item as a side effect"
            )
        moved = tuple(
            replace(c, carriage=carriage, hands=c.hands if carriage is Carriage.HELD else None)
            if c.item.id == item_id
            else c
            for c in target.equipment
        )
        return self._evolve(combatants=self._replacing(replace(target, equipment=moved)))

    def with_object_picked_up(self, combatant_id: str, item_id: str) -> EncounterState:
        """Take one detached object into a creature's hands (p. 177, 0042 clause 4).

        "Equipping a weapon includes … **picking it up**", which is `with_object_detached`
        run backwards: the object leaves `detached_objects` and arrives `HELD`.

        **Reach is not checked here.** Whether the creature can get to it is a question about
        two positions, and the read surface answers it while building the offer
        (`reachable_objects`) — an object no rule placed is never offered, which is 0041
        clause 4's accepted cost arriving where a player meets it. What this refuses is an
        object that is not there at all.
        """
        target = self.combatant(combatant_id)
        remaining = tuple(o for o in self.detached_objects if o.item.id != item_id)
        if len(remaining) == len(self.detached_objects):
            raise ValueError(
                f"no detached object {item_id!r} to pick up. Picking up one that is not "
                "there would create an item from a name"
            )
        taken = next(o for o in self.detached_objects if o.item.id == item_id)
        return self._evolve(
            combatants=self._replacing(
                replace(target, equipment=(*target.equipment, Carried(taken.item, Carriage.HELD)))
            ),
            detached_objects=remaining,
        )

    def with_time_passed(self, minutes: int) -> EncounterState:
        """Advance campaign time and apply what elapsing it decided (decision 0020).

        The caller says how much time passed — a narrative fact only the agent holds — and
        this decides every consequence. Two rules today: p. 18's Stable creature regaining
        1 hit point once its recovery minute is reached, and every campaign-axis condition
        whose minute the clock has now reached (#111). The rests resolve here when they
        arrive.

        Both are deterministic bookkeeping rather than outcomes, for the same reason
        `advanced_turn` retiring a round count is: the expiry point was fixed when the
        condition was applied, so arriving at it decides nothing that was not already
        decided, and no die is thrown (R1, R4).

        Recovery restores a hit point and nothing else. p. 18 does not say the Unconscious
        condition ends, and the sentence that does end a condition on regaining hit points
        (p. 17) is about Knocking Out a Creature, a different case. Not decided here rather
        than decided wrongly.
        """
        advanced = self.clock.advanced(minutes)
        recovered = tuple(
            _elapsed(
                replace(
                    participant,
                    hit_points=min(
                        participant.max_hit_points,
                        participant.hit_points + STABLE_RECOVERY_HIT_POINTS,
                    ),
                    death_saves=DeathSaves(),
                )
                if _recovers_by(participant, advanced)
                else participant,
                advanced,
            )
            for participant in self.combatants
        )
        return self._evolve(combatants=recovered, clock=advanced)

    def with_death(self, combatant_id: str) -> EncounterState:
        target = self.combatant(combatant_id)
        return self._evolve(
            combatants=self._replacing(
                replace(target, death_saves=replace(target.death_saves, dead=True, stable=False))
            )
        )

    def with_movement(
        self,
        combatant_id: str,
        to: Position,
        *,
        mode: MovementMode = MovementMode.WALK,
        difficult_terrain: bool = False,
        carrying: tuple[str, ...] = (),
    ) -> EncounterState:
        """Move a creature, spending what the distance costs (p. 188, p. 181).

        The engine charges the cost; a caller states only where the creature is going.
        Refused when the cost exceeds what is left, because a move a creature cannot
        afford is not a move it makes slowly — it is one the rules do not allow, and the
        read surface is what a caller consults before proposing it.

        **What is left is asked of the mode, not of Speed** (p. 188, and #206). One spend
        is shared across every mode; the number it comes off belongs to the mode being
        used, so a Fly Speed of 40 buys 40 feet of flight rather than the Speed's 30. See
        `Combatant.movement_remaining_in`.

        **`carrying` names the grappled creatures that come along** (p. 182, *Movable*,
        #340). It is the caller's to state because the document makes it optional — "the
        grappler **can** drag or carry you when it moves" — the same kind of declaration
        `mode` is, and not an outcome. Naming a creature this one is not grappling is
        refused; each named creature that p. 182 does not carry free adds its extra foot per
        foot to *this* creature's cost, and every one of them is translated by the same
        displacement so the grapple's geometry is preserved rather than invented.
        """
        target = self.combatant(combatant_id)
        if target.position is None:
            raise ValueError(
                f"{target.name} has no position, so there is no distance to move. An "
                "encounter that tracks no positions cannot answer a movement question"
            )

        # **The engine's own `is_down` doctrine, applied where it was not** (0072). "At 0 hit
        # points a combatant stops acting" is this engine's stated position, and
        # `legal_actions` has enforced it since the read surface shipped — a creature at 0 is
        # offered nothing. Movement never asked, so a creature could be dropped to 0 and walk
        # away in the same breath, which is what an Opportunity Attack made visible: the
        # attack lands, the mover reaches 0, and the move it provoked completes.
        #
        # A refusal rather than a result, so 0056 clause 1 covers it and R1 is untouched. It
        # is the engine's existing rule reaching one more caller rather than a new rule read
        # off the document — this repository does not model the 0-hit-point transition to
        # Unconscious (p. 186's Speed 0 would otherwise be the SRD's own route), and stating
        # that here is cheaper than a reader inferring it from a refusal.
        if target.is_down:
            raise ValueError(
                f"{target.name} is at 0 hit points and does not move. This engine holds "
                '"at 0 hit points a combatant stops acting" as `Combatant.is_down`, which '
                "the read surface has always enforced and this method did not"
            )

        speeds = target.effective_speeds
        if mode in _SPEED_ONLY_MODES and speeds.for_mode(mode) is None:
            raise ValueError(
                f"{target.name} has no {mode.value} speed, so there is no {mode.value} "
                f"move to make. pp. 178, 179 and 189 price climbing, swimming and crawling "
                f"for a creature that lacks the speed; flying and burrowing are priced "
                f"nowhere, because a Fly Speed and a Burrow Speed are the only things that "
                f"grant them (pp. 178, 182)"
            )

        passengers = self._passengers(target, carrying)
        feet = distance_feet(target.position, to)
        cost = movement_cost(
            feet,
            mode=mode,
            difficult_terrain=difficult_terrain,
            speeds=speeds,
            carrying=sum(
                not carried_without_extra_cost(passenger=p.size, grappler=target.size)
                for p in passengers
            ),
        )
        remaining = target.movement_remaining_in(mode)
        assert remaining is not None  # the refusal above covers the modes that answer None
        if cost > remaining:
            raise ValueError(
                f"{target.name} has {remaining} feet of {mode.value} movement left and "
                f"that move costs {cost}"
            )

        if Condition.PRONE in target.conditions.held and mode is not MovementMode.CRAWL:
            raise ValueError(
                f"{target.name} is Prone, so p. 186 leaves it two movement options and "
                f'{mode.value} is neither: "Your only movement options are to crawl or to '
                "spend an amount of movement equal to half your Speed (round down) to right "
                'yourself." Standing up is a ruling, not a move'
            )

        approached = self._fear_approached(target, to)
        if approached is not None:
            raise ValueError(
                f"{target.name} is Frightened of {approached.name} and that move is closer to "
                'it. p. 182: "You can\'t willingly move closer to the source of fear" — and a '
                "move a creature declares is one it makes willingly"
            )

        moved = [replace(target, position=to, movement_used=target.movement_used + cost)]
        # p. 182 says the grappler drags or carries the creature and says nothing about where
        # it ends up, so the passengers are translated by the same displacement: the only
        # answer that preserves the distance between the two rather than inventing one. And
        # nothing is spent and nothing is provoked, for 0055's reason — a carried creature has
        # Speed 0 and uses none of the four things p. 185 provokes on.
        dx = to.x - target.position.x
        dy = to.y - target.position.y
        dz = to.z - target.position.z
        moved.extend(
            replace(
                passenger,
                position=Position(
                    x=passenger.position.x + dx,
                    y=passenger.position.y + dy,
                    z=passenger.position.z + dz,
                ),
            )
            for passenger in passengers
            # Refused above, and narrowed here for the type checker.
            if passenger.position is not None
        )
        return self._evolve(combatants=self._replacing(*moved))

    def _passengers(self, grappler: Combatant, carrying: tuple[str, ...]) -> tuple[Combatant, ...]:
        """The creatures p. 182 lets this one bring along, refusing anything else (#340).

        > **Movable.** The grappler can drag or carry you when it moves…

        Three refusals, and each is a fact the engine has rather than a judgement it makes:
        a creature that is not in this encounter, one this creature is not grappling, and one
        nobody placed. The last matters because carrying translates a position, and there is
        no position to translate — a caller asking for it has a creature the engine cannot
        put anywhere, which is not a move made approximately.
        """
        passengers = []
        for passenger_id in carrying:
            passenger = self.combatant(passenger_id)
            if passenger.conditions.grappler_id != grappler.id:
                raise ValueError(
                    f"{grappler.name} is not grappling {passenger.name}, so p. 182's "
                    "Movable clause gives it nothing to drag or carry. A creature comes "
                    "along because it is Grappled by the mover, not because it was named"
                )
            if passenger.position is None:
                raise ValueError(
                    f"{passenger.name} has no position, so there is nowhere for "
                    f"{grappler.name} to carry it to. p. 182 moves a creature that is "
                    "somewhere"
                )
            passengers.append(passenger)
        return tuple(passengers)

    def _fear_approached(self, target: Combatant, to: Position) -> Combatant | None:
        """The source of fear this move would close on, or `None` (p. 182, #350).

        > **Can't Approach.** You can't willingly move closer to the source of fear.

        **A comparison of two distances, and nothing more.** "Closer" needs no direction and no
        ray — `squared_distance` answers it exactly, without a square root, and the source has
        been recorded on the condition since #192. Two open issues said this waited on the
        forced-movement primitive 0055 built; it never did.

        **A source whose distance cannot be measured is not approached.** One that has left the
        encounter, or that nobody placed, leaves the question unanswerable — and refusing a move
        on a distance the engine could not measure would forbid something the rules may permit.
        That is the direction `_within` already takes at the read surface for the same reason.
        """
        if target.position is None:
            return None
        for source_id in sorted(target.conditions.sources_of(Condition.FRIGHTENED)):
            if not self.has(source_id):
                continue
            source = self.combatant(source_id)
            if source.position is None:
                continue
            if squared_distance(to, source.position) < squared_distance(
                target.position, source.position
            ):
                return source
        return None

    def with_initiative(self, rolls: Mapping[str, int]) -> EncounterState:
        """Order the combatants and begin round 1 (p. 13, #385).

        > The GM ranks the combatants, from highest to lowest Initiative. This is the order
        > in which they act during each round. The Initiative order remains the same from
        > round to round.

        Sorted once and never re-sorted, which is that last sentence.

        ## Ties are a person's to break, and this engine has no person

        > **Ties.** If a tie occurs, the GM decides the order among tied monsters, and the
        > players decide the order among tied characters. The GM decides the order if the tie
        > is between a monster and a player character.

        The document does not leave ties open — it **assigns** them, to a person, in three
        clauses. So there is no rule here for the engine to implement, and inventing one
        would be inventing a decision the document gave away (R31).

        **Insertion order is therefore a convention, declared rather than presented as SRD.**
        The same construction `Lighting` uses for overlapping volumes and for the same reason:
        the engine needs a total order to be reproducible, the document supplies none it may
        use, so the tie-break is stable, stated, and not a claim about the rules.

        A ruleset that wants the document's answer supplies it the way p. 13 describes —
        by ordering the combatants it passes in. That is the person deciding, expressed as
        the only input this method has.
        """
        missing = [cid for cid in rolls if not self.has(cid)]
        if missing:
            raise KeyError(f"no combatant {missing[0]!r} in this encounter")
        if len(rolls) != len(self.combatants):
            raise ValueError("initiative must be rolled for every combatant")

        order = sorted(
            self.combatants,
            key=lambda c: (-rolls[c.id], self.combatants.index(c)),
        )
        ordered = tuple(replace(c, initiative=rolls[c.id]) for c in order)
        return self._evolve(combatants=ordered, round_number=1, turn_index=0)

    def advanced_turn(self, *, waive_obligations: bool = False) -> EncounterState:
        """Move to the next combatant, wrapping into the next round.

        The incoming creature's movement resets, because Speed is "the distance in feet
        the creature can cover when it moves **on its turn**" (p. 188). A counter carried
        across turns would silently shorten every move after the first.

        **Refuses while the departing creature owes a repeated save** (0023 clause 6).
        That is what makes the skip structurally impossible rather than merely serviced by
        well-behaved callers: `Conditions.saves_due_after` reported the obligation for
        eleven days and nothing rolled it, and a missed save leaves no trace — exactly like
        the missed skip this engine exists to prevent. `TurnLoop.end_turn` discharges the
        obligations, and the state records that it did.

        `waive_obligations=True` is the explicit escape for a consumer that legitimately
        wants to fast-forward. It is a parameter rather than silence because the record
        that mattered is *that a turn advanced unresolved*, and a caller has to say so.
        """
        if self.turn_index is None:
            raise ValueError("the encounter has no turn order yet")

        departing = self.combatants[self.turn_index].id
        outstanding = self.obligations_outstanding(departing)
        if outstanding and not waive_obligations:
            names = ", ".join(c.value for c in outstanding)
            raise ObligationOutstanding(
                f"{departing!r} owes a repeated save at the end of this turn for {names} "
                "(p. 63), and the turn cannot advance past it. Run TurnLoop.end_turn, or "
                "pass waive_obligations=True to advance without resolving it"
            )

        # Durations retire against the turn that is *ending*, not the one beginning (#18).
        # "Until the end of your next turn" means the condition is still held for the whole
        # of that turn, so the lift happens as it closes.
        ended = self._retired(self.combatants[self.turn_index].id)

        # An obligation is owed once per turn, so the record of having met it does not
        # outlive the turn it belonged to. p. 105's one spell slot is cleared in the same
        # breath and is deliberately not the same field: one records an obligation met, the
        # other a resource spent, and they agree about *when* rather than about what.
        following = self.turn_index + 1
        if following < len(self.combatants):
            return _swept(
                ended._evolve(
                    turn_index=following,
                    combatants=ended._refreshed(following),
                    discharged=frozenset(),
                    slots_expended_this_turn=frozenset(),
                    light_attacks_this_turn=frozenset(),
                    extra_attacks_this_turn=frozenset(),
                    cleave_openings_this_turn=frozenset(),
                    cleaves_this_turn=frozenset(),
                    attacks_this_turn={},
                    object_interactions_this_turn=frozenset(),
                    loading_shots_this_turn=frozenset(),
                )
            )
        return _swept(
            ended._evolve(
                turn_index=0,
                round_number=self.round_number + 1,
                combatants=ended._refreshed(0),
                discharged=frozenset(),
                slots_expended_this_turn=frozenset(),
                light_attacks_this_turn=frozenset(),
                extra_attacks_this_turn=frozenset(),
                cleave_openings_this_turn=frozenset(),
                cleaves_this_turn=frozenset(),
                attacks_this_turn={},
                object_interactions_this_turn=frozenset(),
                loading_shots_this_turn=frozenset(),
            )
        )

    def _retired(self, actor_id: str) -> EncounterState:
        """Lift every condition whose span ends at the close of that creature's turn.

        Deterministic bookkeeping rather than an outcome: the duration's expiry point was
        settled when the condition was applied, so nothing is decided here and no die is
        rolled. A save that *could* end a condition early is the opposite case — that is an
        outcome, and `Conditions.saves_due_after` reports it for adjudication rather than
        resolving it (R1, R4).
        """
        updated = self.combatants
        for combatant in self.combatants:
            expiring = combatant.conditions.expired_after(self.round_number, actor_id)
            if not expiring:
                continue
            remaining = combatant.conditions.without(expiring)
            updated = tuple(
                replace(c, conditions=remaining) if c.id == combatant.id else c for c in updated
            )
        if updated is self.combatants:
            return self
        # No generation bump: `advanced_turn` is about to make one, and two would leave a
        # read token from before this turn looking two changes stale instead of one.
        return replace(self, combatants=updated)

    def _refreshed(self, turn_index: int) -> tuple[Combatant, ...]:
        """The combatants with the one whose turn begins given its turn back.

        Movement, the action economy, and the Reaction all reset here. The Reaction is the
        one that matters for timing: it refreshes at "the start of your next turn" (p. 186)
        rather than at the end of the round, and those differ whenever a creature acts late
        in one round and early in the next.
        """
        starting = self.combatants[turn_index]
        return self._replacing(
            replace(starting, movement_used=0, actions=starting.actions.refreshed())
        )
