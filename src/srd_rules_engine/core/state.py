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

from srd_rules_engine.core.conditions import Conditions
from srd_rules_engine.core.damage import DamageType, Defences, after_defences
from srd_rules_engine.core.position import (
    DEFAULT_REACH_FEET,
    MovementMode,
    Position,
    Speeds,
    distance_feet,
    movement_cost,
)

#: p. 17: "On your third success, you become Stable... On your third failure, you die."
DEATH_SAVE_THRESHOLD: Final = 3


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

    def __post_init__(self) -> None:
        if self.successes < 0 or self.failures < 0:
            raise ValueError("death save counts do not go backwards; they reset to zero")

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
    #: p. 186: "A creature has a reach of 5 feet unless a rule says otherwise."
    reach: int = DEFAULT_REACH_FEET
    #: Movement spent this turn. Reset when the turn advances, not carried.
    movement_used: int = 0
    #: Active conditions, with implication already resolved (R14, R18).
    conditions: Conditions = field(default_factory=Conditions)
    #: Only meaningful at 0 hit points. Reset rather than carried once healing lands.
    death_saves: DeathSaves = DeathSaves()

    def __post_init__(self) -> None:
        object.__setattr__(self, "abilities", MappingProxyType(dict(self.abilities)))

    @property
    def is_down(self) -> bool:
        """At 0 hit points a combatant stops acting."""
        return self.hit_points <= 0

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
        return max(0, self.conditions.speed_after(self.speeds.walk) - self.movement_used)

    def modifier(self, ability: str) -> int:
        """The SRD's ability modifier, floor-divided so negatives round the right way."""
        return (self.abilities.get(ability, 10) - 10) // 2


@dataclass(frozen=True)
class EncounterState:
    """The state the read surface reports over, and the only thing that carries a generation."""

    generation: int
    combatants: tuple[Combatant, ...]
    round_number: int = 0
    turn_index: int | None = None

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
        amount = after_defences(amount, damage_type, target.defences).amount
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
        self, combatant_id: str, *, successes: int = 0, failures: int = 0
    ) -> EncounterState:
        """Record a death save, and apply the thresholds it may have crossed.

        The thresholds live here rather than in the caller because reaching three is not a
        second decision — p. 17 states it as a consequence of the third mark, so a caller
        able to record a third failure without the creature dying would be a caller able
        to invent a survival.
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
        )
        return self._evolve(combatants=self._replacing(replace(target, death_saves=updated)))

    def with_stabilised(self, combatant_id: str) -> EncounterState:
        """Stable, and the counts reset with it — p. 17 resets on becoming Stable too."""
        target = self.combatant(combatant_id)
        if target.death_saves.dead:
            return self
        return self._evolve(
            combatants=self._replacing(replace(target, death_saves=DeathSaves(stable=True)))
        )

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

    def advanced_turn(self) -> EncounterState:
        """Move to the next combatant, wrapping into the next round.

        The incoming creature's movement resets, because Speed is "the distance in feet
        the creature can cover when it moves **on its turn**" (p. 188). A counter carried
        across turns would silently shorten every move after the first.
        """
        if self.turn_index is None:
            raise ValueError("the encounter has no turn order yet")
        following = self.turn_index + 1
        if following < len(self.combatants):
            return self._evolve(turn_index=following, combatants=self._refreshed(following))
        return self._evolve(
            turn_index=0, round_number=self.round_number + 1, combatants=self._refreshed(0)
        )

    def _refreshed(self, turn_index: int) -> tuple[Combatant, ...]:
        """The combatants with the one whose turn begins given its movement back."""
        starting = self.combatants[turn_index]
        return self._replacing(replace(starting, movement_used=0))
