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
from types import MappingProxyType
from typing import Any, Final

from srd_rules_engine.core.actions import ActionBudget, still_dodging
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
    save_ends_rule_id,
)
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
from srd_rules_engine.core.obstructions import Obstruction, blocking, line_is_blocked
from srd_rules_engine.core.position import (
    DEFAULT_REACH_FEET,
    MovementMode,
    Position,
    Speeds,
    distance_feet,
    movement_cost,
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
from srd_rules_engine.core.spellcasting import SpellSlots

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

    Only `burning` today. Suffocation belongs here and is not built — it inflicts Exhaustion
    *levels*, and nothing can raise one through a ruling
    ([#178](https://github.com/eddiefiggie/srd-rules-engine/issues/178)). A field with no
    consumer would be a stub with a citation attached, which this repository has one of
    already and does not need two.

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
    #: Movement spent this turn. Reset when the turn advances, not carried.
    movement_used: int = 0
    #: Active conditions, with implication already resolved (R14, R18).
    conditions: Conditions = field(default_factory=Conditions)
    #: What is left of the action economy this turn (p. 176-177, 186).
    actions: ActionBudget = field(default_factory=ActionBudget)
    #: Spell slots, for a creature that has any. `None` for one that does not, which is a
    #: different thing from having none left.
    slots: SpellSlots | None = None
    #: Only meaningful at 0 hit points. Reset rather than carried once healing lands.
    death_saves: DeathSaves = DeathSaves()

    def __post_init__(self) -> None:
        object.__setattr__(self, "abilities", MappingProxyType(dict(self.abilities)))

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
    def makes_death_saves(self) -> bool:
        """p. 17-18: a **player character** at 0 hit points, unless Stable or dead.

        Three conditions, and each excludes a case the others let through. "A player
        character must make a Death Saving Throw" — a monster dies instead. "A Stable
        creature doesn't make Death Saving Throws even though it has 0 Hit Points" — so
        being down is not sufficient, which is why Stable is tracked separately from the
        hit point total.
        """
        return self.is_player_character and self.is_down and not self.death_saves.is_resolved

    @property
    def movement_remaining(self) -> int:
        """What is left of this creature's Speed on this turn (p. 188).

        Conditions act on the Speed first: Grappled and the rest set it to 0, and
        Exhaustion reduces it by 5 per level (pp. 182, 181). A creature whose Speed a
        condition zeroed has no movement left however little it has spent.
        """
        allowance = self.conditions.speed_after(self.speeds.walk) + self.actions.extra_movement
        return max(0, allowance - self.movement_used)

    def modifier(self, ability: str) -> int:
        """The SRD's ability modifier, floor-divided so negatives round the right way."""
        return (self.abilities.get(ability, 10) - 10) // 2


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

    # --- Evolving -----------------------------------------------------------------

    def _evolve(self, **changes: Any) -> EncounterState:
        """The only way to produce a successor, and the only place the generation moves.

        `generation` is deliberately not a parameter a caller can pass. A mutator that
        forgot to bump it would leave a stale read token reading as current, which is
        the quiet direction to fail in.
        """
        changes.pop("generation", None)
        return replace(self, generation=self.generation + 1, **changes)

    def _replacing(self, updated: Combatant) -> tuple[Combatant, ...]:
        return tuple(updated if c.id == updated.id else c for c in self.combatants)

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
        return after_defences(amount, damage_type, self.combatant(combatant_id).defences)

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
        state = self._evolve(combatants=self._replacing(reduced))
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

        restored = replace(target, hit_points=target.max_hit_points)
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
    ) -> EncounterState:
        """Move a creature, spending what the distance costs (p. 188, p. 181).

        The engine charges the cost; a caller states only where the creature is going.
        Refused when the cost exceeds what is left, because a move a creature cannot
        afford is not a move it makes slowly — it is one the rules do not allow, and the
        read surface is what a caller consults before proposing it.
        """
        target = self.combatant(combatant_id)
        if target.position is None:
            raise ValueError(
                f"{target.name} has no position, so there is no distance to move. An "
                "encounter that tracks no positions cannot answer a movement question"
            )

        feet = distance_feet(target.position, to)
        cost = movement_cost(
            feet, mode=mode, difficult_terrain=difficult_terrain, speeds=target.speeds
        )
        if cost > target.movement_remaining:
            raise ValueError(
                f"{target.name} has {target.movement_remaining} feet of movement left and "
                f"that move costs {cost}"
            )

        moved = replace(target, position=to, movement_used=target.movement_used + cost)
        return self._evolve(combatants=self._replacing(moved))

    def with_initiative(self, rolls: Mapping[str, int]) -> EncounterState:
        """Order the combatants and begin round 1. Ties break by the order given."""
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
        # outlive the turn it belonged to.
        following = self.turn_index + 1
        if following < len(self.combatants):
            return ended._evolve(
                turn_index=following,
                combatants=ended._refreshed(following),
                discharged=frozenset(),
            )
        return ended._evolve(
            turn_index=0,
            round_number=self.round_number + 1,
            combatants=ended._refreshed(0),
            discharged=frozenset(),
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
