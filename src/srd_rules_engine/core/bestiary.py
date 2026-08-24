"""Monster statistics, each carrying what it was verified against (#21, R32).

The engine defines and consumes stat blocks; this is the parallel data track that fills them
in. Decision [0003](../../../docs/decisions/0003-seed-and-verification.md) governs it: no
structured dataset seeds anything, the official SRD v5.2.1 PDF is the only verification
reference, verification state lives alongside the entry it describes, and **only `verified`
entries reach the engine**.

## Statistics only, and that is a licensing boundary as well as a scope one

A stat block has two halves. Its **statistics** — armour class, hit points, speeds, ability
scores, challenge rating — are values, and values are what this carries. Its **traits and
actions** are rules prose, and `NOTICE.md` commits this repository to not redistributing
rules prose: "Mechanics are modelled by hand from SRD v5.2.1 into typed effect shapes...
Rules prose is not redistributed."

So no trait text appears here, and none ever will. What a trait *does* belongs in the effect
vocabulary, and a monster whose traits need a shape the engine has not implemented is not a
monster the engine can fully run. `Statistics.traits_modelled` is `False` on every entry
today, because none of them are — an honest field rather than a silent omission.

## What verification means here

Every field is asserted against the printed page at derivation time by
`scripts/derive_bestiary.py`: the pattern must match, or the derivation fails. That is the
same standard the effect-shape inventory holds itself to. Decision
[0017](../../../docs/decisions/0017-verification-is-asserted-not-read.md) settles what that
means: verification is a pattern asserted against the document, it is re-runnable where a
human read is not, and it covers **transcription rather than modelling** — a pattern would
confirm that `AC 17` appears on p. 258 while the derivation wrote 17 into `hit_points`.
Every entry records `method: asserted` so the claim is legible rather than assumed.

## The gate

`load_bestiary` refuses anything not `verified`, exactly as `load_ruleset` does for rules,
and refuses it loudly rather than filtering it out. An excluded entry names its reason (R32),
because a gap that is visible is a gap somebody can close.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.position import Speeds
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

_DATA_PACKAGE: Final = "srd_rules_engine.data"
_DATA_FILE: Final = "bestiary.json"

#: The six ability scores every stat block prints, in the document's own order.
ABILITIES: Final = ("str", "dex", "con", "int", "wis", "cha")


class BestiaryLoadError(Exception):
    """An entry that does not reach the engine, and why."""


@dataclass(frozen=True)
class Statistics:
    """One monster's statistics. No prose, by construction — there is nowhere to put any."""

    id: str
    name: str
    armour_class: int
    hit_points: int
    #: The printed expression, as an exact string: "20d10 + 40". A string rather than a
    #: parsed average, because `core.canonical` refuses floats and an average is one.
    hit_dice: str
    speeds: Speeds
    abilities: Mapping[str, int]
    proficiency_bonus: int
    #: Printed as "10" or "1/2", so a string. Dividing it would produce a float.
    challenge_rating: str
    verification: Verification
    #: Always False today. A stat block's traits are prose and are not carried here; what
    #: they *do* needs effect shapes, and none of these monsters is fully expressible yet.
    traits_modelled: bool = False

    def __post_init__(self) -> None:
        missing = [a for a in ABILITIES if a not in self.abilities]
        if missing:
            raise ValueError(
                f"{self.id!r} is missing ability scores {missing}. A stat block prints all "
                "six, so a partial set means the derivation lost one rather than that the "
                "document omitted it"
            )
        object.__setattr__(self, "abilities", MappingProxyType(dict(self.abilities)))

    def modifier(self, ability: str) -> int:
        """The SRD's ability modifier, floor-divided so negatives round the right way."""
        return (self.abilities[ability] - 10) // 2


@dataclass(frozen=True)
class Bestiary:
    """The admitted entries. Anything unverified never got this far."""

    entries: Mapping[str, Statistics]

    def __getitem__(self, monster_id: str) -> Statistics:
        return self.entries[monster_id]

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, monster_id: object) -> bool:
        return monster_id in self.entries


def load_bestiary(entries: Iterable[Statistics]) -> Bestiary:
    """Admit verified entries and refuse the rest, loudly.

    The refusal is the point. Filtering silently would let a stat block the engine never
    checked sit in a campaign looking exactly like one it did — which is the failure R32
    exists to prevent, and the reason an exclusion states its reason.
    """
    admitted: dict[str, Statistics] = {}
    for entry in entries:
        state = entry.verification.state
        if state is VerificationState.EXCLUDED:
            raise BestiaryLoadError(
                f"{entry.id!r} is excluded: {entry.verification.reason}. R32 discloses an "
                "exclusion rather than dropping it silently"
            )
        if state is not VerificationState.VERIFIED:
            raise BestiaryLoadError(
                f"{entry.id!r} is {state} and does not reach the engine. Only an entry "
                "verified against SRD v5.2.1 is trusted"
            )
        if entry.id in admitted:
            raise BestiaryLoadError(f"{entry.id!r} appears twice; ids are the join key")
        admitted[entry.id] = entry
    return Bestiary(entries=MappingProxyType(admitted))


@lru_cache(maxsize=1)
def published_bestiary() -> Bestiary:
    """The bestiary that ships with the package, through the same gate as any other."""
    raw = json.loads(
        resources.files(_DATA_PACKAGE).joinpath(_DATA_FILE).read_text(encoding="utf-8")
    )
    return load_bestiary(_statistics(entry) for entry in raw["entries"])


def _statistics(entry: Mapping[str, object]) -> Statistics:
    speeds = entry["speeds"]
    assert isinstance(speeds, Mapping)
    verification = entry["verification"]
    assert isinstance(verification, Mapping)
    abilities = entry["abilities"]
    assert isinstance(abilities, Mapping)

    return Statistics(
        id=str(entry["id"]),
        name=str(entry["name"]),
        armour_class=int(str(entry["armour_class"])),
        hit_points=int(str(entry["hit_points"])),
        hit_dice=str(entry["hit_dice"]),
        speeds=Speeds(
            walk=int(str(speeds.get("walk", 30))),
            climb=_optional(speeds.get("climb")),
            fly=_optional(speeds.get("fly")),
            swim=_optional(speeds.get("swim")),
            burrow=_optional(speeds.get("burrow")),
        ),
        abilities={name: int(str(score)) for name, score in abilities.items()},
        proficiency_bonus=int(str(entry["proficiency_bonus"])),
        challenge_rating=str(entry["challenge_rating"]),
        verification=Verification(
            state=VerificationState(str(verification["state"])),
            reference=_text(verification.get("reference")),
            date=_text(verification.get("date")),
            reason=_text(verification.get("reason")),
            method=_method(verification.get("method")),
        ),
        traits_modelled=bool(entry.get("traits_modelled", False)),
    )


def _method(value: object) -> VerificationMethod | None:
    return None if value is None else VerificationMethod(str(value))


def _optional(value: object) -> int | None:
    return None if value is None else int(str(value))


def _text(value: object) -> str | None:
    return None if value is None else str(value)
