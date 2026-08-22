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
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "abilities", MappingProxyType(dict(self.abilities)))

    @property
    def is_down(self) -> bool:
        """At 0 hit points a combatant stops acting. What happens next is R12's business."""
        return self.hit_points <= 0

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

    def with_damage(self, combatant_id: str, amount: int) -> EncounterState:
        if amount < 0:
            raise ValueError("damage is not negative; healing is a separate change")
        target = self.combatant(combatant_id)
        reduced = replace(target, hit_points=max(0, target.hit_points - amount))
        return self._evolve(combatants=self._replacing(reduced))

    def with_healing(self, combatant_id: str, amount: int) -> EncounterState:
        if amount < 0:
            raise ValueError("healing is not negative; damage is a separate change")
        target = self.combatant(combatant_id)
        restored = replace(
            target, hit_points=min(target.max_hit_points, target.hit_points + amount)
        )
        return self._evolve(combatants=self._replacing(restored))

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
        """Move to the next combatant, wrapping into the next round."""
        if self.turn_index is None:
            raise ValueError("the encounter has no turn order yet")
        following = self.turn_index + 1
        if following < len(self.combatants):
            return self._evolve(turn_index=following)
        return self._evolve(turn_index=0, round_number=self.round_number + 1)
