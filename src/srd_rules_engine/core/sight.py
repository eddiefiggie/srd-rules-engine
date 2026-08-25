"""Senses, light and obscurement — the structure, with the rules deliberately absent.

Decision [0025](../../../docs/decisions/0025-sight-is-a-relation-over-stored-state.md)
settled this subsystem's design before any of it was built, because #138's ten shapes are
one mechanism read three ways and a shape built alone produces a value nothing can consume.
This module is clauses 2, 3 and 4 of that record. Clause 5 is why it cannot yet answer the
question it exists to answer.

## What is stored, and what is derived

**Light is state** (clause 2). `Lighting` hangs off `EncounterState`, set when the encounter
is built or changed through a ruling — never handed in by the caller at the moment an
outcome is computed. An input the caller supplies then is an input the caller *chooses*, and
choosing between Bright Light and Darkness is choosing between Advantage and Disadvantage.
That is the agent deciding how it turns out, which R1 and R4 do not permit. #119 settled the
same question for conditions.

**Senses are state** (clause 3), on the creature, shaped like `Speeds` — a range in feet per
sense, with `None` meaning the creature has no such sense. `None` is not zero, for the reason
`Speeds` gives: a creature with no Darkvision and one whose Darkvision has been reduced to
nothing are different creatures.

**Visibility is derived** (clause 4). Whether an observer can see a target is a *relation*
over those two stored values, so it is computed per query rather than kept. 0021 clause 3
warns that "a value re-derived on every query is a value a caller can re-draw by choosing
when to ask", and the warning does not reach here: both inputs are stored, neither is
caller-supplied at query time, and the derivation is a pure function of one generation of
`EncounterState`.

## The table is empty on purpose, and every query against it refuses

Which light level a sense converts into which other, and what obscurement means for a roll,
are **rule values** — nine of them, at nine printed pages, and not one of those pages is
asserted anywhere in this repository (#150). `core.conditions` cites the glossary span
pp. 177-191 for the fifteen conditions, which is a range-expansion artifact rather than a
claim about each page inside it.

So `SIGHT_VERIFICATION` is `unverified`, the two tables carry no rows, and `obscurement_at`
and `can_see` raise `SightUnverified` rather than defaulting to an answer. `core.spellcasting`
is the precedent: it ships **no** slot table, because compiling one from memory of a game is
exactly the inferred rule value R31 forbids. A right value and a wrong value are
indistinguishable once inside a finished ruling.

`tests/test_sight.py` holds that line — the tables must stay empty while the verification
says unverified, so a row cannot be added without the state moving with it.

## What is *not* a rule value here

The three light levels, the two obscurement degrees and the four senses are named by the
Rules Glossary's own entry headings, which `scripts/derive_effect_shapes.py` reads
mechanically off the document rather than recalling. Enumerating them is not transcribing
what they *do*, which is the part that waits for #150.

`Obscurement.NONE` is this engine's representation of the absence of obscurement, not a
glossary term — `Cover.NONE` in `core.obstructions` is the same construction for the same
reason.

## Telepathy is not here

It is filed as a `sense` in the inventory and is not part of this chain: nothing about light,
obscurement or line of sight changes what it does (0025 clause 1). `kind` is a filing label
rather than a model (0019), and Telepathy's own consumer is #149.

## The box, and why there are two of them

`LitVolume` carries the same axis-aligned box as `core.obstructions.Obstruction`, including
the corner normalisation, rather than sharing one. They are not unified *yet*: the seam
that justified the duplication is settled — decision
[0026](../../../docs/decisions/0026-terrain-enters-as-state.md) puts both kinds of terrain
on state — so the reason has lapsed and only the work remains.
Extracting the shared box is [#161](https://github.com/eddiefiggie/srd-rules-engine/issues/161),
and it waits on [#160](https://github.com/eddiefiggie/srd-rules-engine/issues/160) moving
obstructions onto `EncounterState` first, because unifying on the strength of a decision the
tree does not yet reflect is the same accident in the other direction.

Unifying the geometry would not unify the meaning: a volume that emits light and a volume
that blocks a line stay distinct types, and only the box and its normalisation are shared.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import Verification, VerificationState


class SightUnverified(RuntimeError):
    """Raised when a query needs a rule value nobody has read off the document yet.

    A refusal rather than a default. R31: a visible gap beats a confident wrong number,
    because the wrong number is indistinguishable from a right one once it is inside a
    ruling.
    """


class LightLevel(StrEnum):
    """The three light levels the Rules Glossary names."""

    BRIGHT = "bright-light"
    DIM = "dim-light"
    DARKNESS = "darkness"


class Obscurement(StrEnum):
    """The two degrees of obscurement the glossary names, plus the absence of one."""

    NONE = "none"
    LIGHTLY_OBSCURED = "lightly-obscured"
    HEAVILY_OBSCURED = "heavily-obscured"


class Sense(StrEnum):
    """The four senses that participate in seeing. Telepathy is not one — 0025 clause 1."""

    BLINDSIGHT = "blindsight"
    DARKVISION = "darkvision"
    TREMORSENSE = "tremorsense"
    TRUESIGHT = "truesight"


@dataclass(frozen=True)
class Senses:
    """A creature's special senses, each a range in feet (0025 clause 3).

    `None` means the creature has no such sense, which is different from a range of 0 — the
    distinction `Speeds` draws between a creature that cannot fly and one whose Fly Speed is
    zero. Nothing here says what any of them *does*; that is the table, and the table is
    empty (#150).
    """

    blindsight: int | None = None
    darkvision: int | None = None
    tremorsense: int | None = None
    truesight: int | None = None

    def range_of(self, sense: Sense) -> int | None:
        return {
            Sense.BLINDSIGHT: self.blindsight,
            Sense.DARKVISION: self.darkvision,
            Sense.TREMORSENSE: self.tremorsense,
            Sense.TRUESIGHT: self.truesight,
        }[sense]

    def has(self, sense: Sense) -> bool:
        return self.range_of(sense) is not None

    @property
    def held(self) -> tuple[Sense, ...]:
        """The senses this creature has, in a stable order."""
        return tuple(sense for sense in Sense if self.has(sense))


@dataclass(frozen=True)
class LitVolume:
    """An axis-aligned box in feet holding one light level.

    `lo` and `hi` are opposite corners and the constructor does not care which way round
    they were given, for the reason `Obstruction` gives: a caller describing a room should
    not have to sort its corners.
    """

    level: LightLevel
    lo: Position
    hi: Position

    def __post_init__(self) -> None:
        low = Position(
            min(self.lo.x, self.hi.x), min(self.lo.y, self.hi.y), min(self.lo.z, self.hi.z)
        )
        high = Position(
            max(self.lo.x, self.hi.x), max(self.lo.y, self.hi.y), max(self.lo.z, self.hi.z)
        )
        object.__setattr__(self, "lo", low)
        object.__setattr__(self, "hi", high)

    def contains(self, point: Position) -> bool:
        return (
            self.lo.x <= point.x <= self.hi.x
            and self.lo.y <= point.y <= self.hi.y
            and self.lo.z <= point.z <= self.hi.z
        )


@dataclass(frozen=True)
class Lighting:
    """Where the light is (0025 clause 2). Part of `EncounterState`, never a query argument.

    `ambient` is the level everywhere a volume does not override, and **`None` means nobody
    has said** — not Bright Light. Defaulting an unstated encounter to daylight would be a
    rule value nobody supplied, and it would be invisible: every roll would come out as
    though the question had been answered.

    **Overlap is resolved by order, and that is an engine convention rather than a rule.**
    The last volume containing the point wins, so a caller layering a torch inside a dark
    room writes the room first and the torch second. The document supplies no precedence
    rule for overlapping light, so this is declared here rather than presented as SRD.
    """

    ambient: LightLevel | None = None
    volumes: tuple[LitVolume, ...] = ()

    def level_at(self, point: Position) -> LightLevel | None:
        """The light level at a point, or `None` if nothing has stated one."""
        for volume in reversed(self.volumes):
            if volume.contains(point):
                return volume.level
        return self.ambient


#: R31/0025 clause 5. The mapping from light and sense to obscurement is nine rule values at
#: nine printed pages, none of them asserted in this repository. This stays `unverified`, the
#: tables below stay empty, and the queries refuse — until #150 reads the document.
SIGHT_VERIFICATION: Final = Verification(
    state=VerificationState.UNVERIFIED,
    reason=(
        "The Rules Glossary pages for Blindsight (177), Bright Light (178), Darkvision and "
        "Darkness (180), Dim Light (181), Heavily Obscured (182), Lightly Obscured (184), "
        "and Tremorsense and Truesight (190) are asserted in no verification block and in no "
        "clause of scripts/verify_d20_rules.py. Until they are, this engine states no "
        "relationship between a light level, a sense and an obscurement (#150)."
    ),
)

#: What each light level obscures to, before any sense is applied. Empty until #150.
OBSCUREMENT_BY_LIGHT: Final[Mapping[LightLevel, Obscurement]] = MappingProxyType({})

#: How a sense re-reads a light level for the creature that has it. Empty until #150.
SENSE_LIGHT_SHIFTS: Final[Mapping[Sense, Mapping[LightLevel, LightLevel]]] = MappingProxyType({})


def _refuse(question: str) -> SightUnverified:
    return SightUnverified(
        f"{question} is a rule value this engine has not read off the document. "
        f"{SIGHT_VERIFICATION.reason}"
    )


def obscurement_at(level: LightLevel, *, senses: Senses) -> Obscurement:
    """What a light level obscures to for a creature with these senses.

    Refuses. The structure is here and the table is not, which is the whole of 0025 clause 5.
    """
    raise _refuse("what a light level means for a creature's sight")


def can_see(observer_senses: Senses, *, at_level: LightLevel | None, distance_feet: int) -> bool:
    """Whether an observer can see a target at this distance in this light.

    Refuses, for the same reason `obscurement_at` does. Note that it would refuse even with
    the table filled when `at_level` is `None` — an unlit encounter is a question nobody has
    answered rather than one this engine may answer for them.
    """
    raise _refuse("whether a creature can see another")
