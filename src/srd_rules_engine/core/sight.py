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

## The tables were empty on purpose, and are not any more

Which light level a sense converts into which other, and what obscurement means for a roll,
are **rule values** — nine of them, at nine printed pages. While none of those pages was
asserted anywhere in this repository, `SIGHT_VERIFICATION` said `unverified`, the two tables
carried no rows, and every query raised `SightUnverified` rather than defaulting to an answer.
`core.spellcasting` was the precedent: it ships **no** slot table, because compiling one from
memory of a game is exactly the inferred rule value R31 forbids.

**#150 read all nine and asserted them**, so the state is `VERIFIED`, both tables carry rows,
and `obscurement_at`, `effective_light` and `can_see` answer. `SightUnverified` remains
reachable and is not vestigial: it is what a future row would raise before its sentence was
asserted.

`tests/test_sight.py` still holds the line — a table row may not exist while the verification
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

## The box, and why there is one of it

`LitVolume` is a `core.position.Box`, and so is `core.obstructions.Obstruction`. The corners,
their normalisation and `contains` live once; each type adds the one thing that makes it
itself — a `level` here, `blocks` there.

They were two identical copies until #161, kept apart deliberately: the geometry could not be
unified while the two kinds of terrain entered the engine by different routes, because
choosing a shared shape would have been picking the answer to that question by accident.
[0026](../../../docs/decisions/0026-terrain-enters-as-state.md) settled the route — both are
state — and #160 put it in the tree, at which point the reason lapsed and only the work
remained.

**Unifying the geometry did not unify the meaning.** A volume that emits light and a volume
that blocks a line are still distinct types; what is shared is a shape with no opinion about
what occupying it does.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.position import Box, Position
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)


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
class LitVolume(Box):
    """A `Box` in feet holding one light level.

    It adds one thing to the box: `level`. The corners, their normalisation and `contains`
    are the box's, shared with `Obstruction` since #161. `level` comes last because the
    box's own fields come first, so construct it by keyword — the corners and the level
    read better named than positioned.
    """

    level: LightLevel


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


#: R31/0025 clause 5, discharged. All nine pages are now clauses in
#: `scripts/verify_d20_rules.py` (#150), so the tables below carry rows.
SIGHT_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Vision and Light p. 11 (Bright Light, Dim Light and Darkness stated as "
        "mechanics); Rules Glossary: Blindsight p. 177, Bright Light p. 178, Darkness and "
        "Darkvision p. 180, Dim Light p. 181, Heavily Obscured p. 182, Lightly Obscured "
        "p. 184, Tremorsense and Truesight p. 190"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)

#: What each light level obscures to, before any sense is applied.
#:
#: Dim Light and Darkness are not *related to* an obscurement by some further rule — the
#: glossary says each **is** one ("An area with Dim Light is Lightly Obscured", p. 181; "An
#: area of Darkness is Heavily Obscured", p. 180).
#:
#: **Bright Light's row is produced from p. 11, not from p. 178.** The glossary entry states
#: no obscurement, only that Bright Light "is normal illumination" — but the mechanic is on
#: p. 11, under *Vision and Light -> Light*: "Bright Light lets most creatures see normally."
#: That is a statement that Bright Light imposes nothing, and this row is it. `Obscurement.NONE`
#: remains this engine's representation of an absence rather than a term the glossary defines —
#: the same construction as `Cover.NONE` — and p. 178 is simply not where the rule lives
#: ([0033](../../../docs/decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md),
#: #228).
OBSCUREMENT_BY_LIGHT: Final[Mapping[LightLevel, Obscurement]] = MappingProxyType(
    {
        LightLevel.BRIGHT: Obscurement.NONE,
        LightLevel.DIM: Obscurement.LIGHTLY_OBSCURED,
        LightLevel.DARKNESS: Obscurement.HEAVILY_OBSCURED,
    }
)

#: How a sense re-reads a light level for the creature that has it, within that sense's range.
#:
#: **Darkvision is the only sense that does this**, and that is the document's shape rather
#: than an omission here. p. 180 gives it as a conversion — Dim Light seen "as if it were
#: Bright Light", Darkness "as if it were Dim Light" — which is exactly a re-reading of the
#: level. The other three senses do not convert anything:
#:
#: * **Blindsight** (p. 177) sees "without relying on physical sight" within its range, and
#:   its bound is **Total Cover**, not illumination. It bypasses this chain rather than
#:   shifting along it.
#: * **Truesight** (p. 190) *pierces* Darkness — "You can see in normal and magical Darkness"
#:   — rather than converting it to a lesser level.
#: * **Tremorsense** (p. 190) "doesn't count as a form of sight", which the document says
#:   outright. It is not in this chain at all.
#:
#: Modelling those three as light shifts would have been a wrong number that looked right.
#: They need their own shape, which is #166.
SENSE_LIGHT_SHIFTS: Final[Mapping[Sense, Mapping[LightLevel, LightLevel]]] = MappingProxyType(
    {
        Sense.DARKVISION: MappingProxyType(
            {
                LightLevel.DIM: LightLevel.BRIGHT,
                LightLevel.DARKNESS: LightLevel.DIM,
            }
        ),
    }
)


class Visibility(StrEnum):
    """What this engine can say about whether one creature sees another.

    Three values, and the third is the point. `UNSTATED` is not "we have not built it" — it
    is **the document does not say**, which is a different claim and a permanent one until
    the SRD says otherwise (#166, R32).
    """

    CAN_SEE = "can-see"
    CANNOT_SEE = "cannot-see"
    UNSTATED = "unstated"


@dataclass(frozen=True)
class Sight:
    """Whether an observer sees a target, and by what.

    `by` names the sense that decided it, or `None` for ordinary sight. `because` is the
    sentence the answer rests on, so a refusal explains itself rather than merely refusing.
    """

    verdict: Visibility
    because: str
    by: Sense | None = None

    @property
    def can_see(self) -> bool:
        """True only when the document says so. `UNSTATED` is not a yes."""
        return self.verdict is Visibility.CAN_SEE


def _refuse(question: str) -> SightUnverified:
    return SightUnverified(
        f"{question} is a rule value this engine has not read off the document. "
        f"{SIGHT_VERIFICATION.reason}"
    )


def effective_light(level: LightLevel, *, senses: Senses, distance_feet: int) -> LightLevel:
    """The light level as a creature with these senses reads it, at this distance.

    Darkvision converts within "a specified range" (p. 180), so the distance decides whether
    the conversion applies at all — a creature with Darkvision 60 reads Darkness at 90 feet
    as Darkness. That is why this takes a distance and `OBSCUREMENT_BY_LIGHT` does not.

    Only one sense converts, so no two conversions can meet and the document supplies no rule
    for combining them. `tests/test_sight.py` fails if a second is added, because that would
    need a combining rule read off the document rather than invented here.
    """
    for sense, shifts in SENSE_LIGHT_SHIFTS.items():
        reach = senses.range_of(sense)
        if reach is not None and distance_feet <= reach:
            return shifts.get(level, level)
    return level


def obscurement_at(level: LightLevel, *, senses: Senses, distance_feet: int) -> Obscurement:
    """What a light level obscures to for this creature, at this distance.

    The chain 0025 clause 4 described, now that #150 has read it: the sense re-reads the
    level, and the level *is* the obscurement.
    """
    return OBSCUREMENT_BY_LIGHT[effective_light(level, senses=senses, distance_feet=distance_feet)]
