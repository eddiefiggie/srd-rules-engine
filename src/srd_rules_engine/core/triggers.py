"""The trigger catalogue: the challenge mechanism, and the answer to the defining defect.

R6 turns a silent skip into a recorded exchange. When a no-test claim collides with a
trigger, the engine returns `challenged` naming every row that fired and its grounding,
and the declaration must be resubmitted.

**A trigger is a row, not a function.** The catalogue is data, interpreted by a fixed
matcher over a closed operator set — and the matcher is handed a `MatchContext` that has
**no field for the declaration's free-text label**. R6's prohibition therefore holds
because the label is out of scope, not because a reviewer checked. A predicate would have
every expressive advantage and one disqualifying property: it is handed the declaration,
so reading `declaration.intent.label` is one attribute access away, and the failure is
silent — a catalogue that reads prose behaves *better* on the cases anyone would test,
right up until it fires on the agent's choice of words.

**A row is a conjunction. An "or" is two rows.** There is no disjunctive operator, which
is deliberate rather than a simplification: each alternative stays separately citable in a
challenge, separately reportable, and separately narrowable when it over-fires. A
disjunctive row that fires wrongly on one branch cannot be narrowed without weakening the
other.

**Every matching row is reported, in identifier order.** Deterministic ordering is
required for replay, and naming all of them is what makes a false-positive report
actionable — the reporter can say which row was wrong.

**Grounding is two-valued.** `cited` when the SRD states the trigger outright and can be
pointed at; `authored` when it is project judgment. A third "derived" tier was considered
and rejected: its boundary is a judgment made at intake by whoever is most convinced the
trigger is warranted, so the tier would stop carrying information.

**The catalogue is known-incomplete by construction**, and over-firing is not the milder
failure. A wrongly-fired trigger makes the agent resubmit naming a test, and the engine
then rolls for something the SRD never called for — a ruling with no rule behind it, which
is the project's defining defect with the sign flipped. False positives carry
`srd-fidelity`.

See `docs/decisions/0004-trigger-catalogue.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

#: Fields of the projection that come from the declaration rather than from state.
INTENT_FIELDS: Final = ("action_key", "improvised", "actor_id")


class TriggerError(Exception):
    """A catalogue row is malformed. Never a rules status."""


class Grounding(StrEnum):
    """Whether the SRD says this, or the project does."""

    CITED = "cited"
    AUTHORED = "authored"


class Operator(StrEnum):
    """The closed set. There is deliberately no disjunction and no prose comparison."""

    EQUALS = "equals"
    IN = "in"
    PRESENT = "present"
    ABSENT = "absent"


@dataclass(frozen=True)
class MatchContext:
    """Everything the matcher can see. **There is no field for the free-text label.**

    That absence is the mechanism. Adding one here would put R6's prohibition back in the
    hands of whoever writes the next matcher.
    """

    actor_id: str
    action_key: str | None
    improvised: bool
    situation: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "situation", MappingProxyType(dict(self.situation)))

    def lookup(self, field: str) -> tuple[bool, object]:
        """Resolve a condition's field. Returns (present, value)."""
        if field == "actor_id":
            return True, self.actor_id
        if field == "action_key":
            return self.action_key is not None, self.action_key
        if field == "improvised":
            return True, self.improvised
        if field in self.situation:
            return True, self.situation[field]
        return False, None


@dataclass(frozen=True)
class Condition:
    """One test against the projection. Conditions within a row are ANDed."""

    field: str
    operator: Operator
    value: object = None

    def __post_init__(self) -> None:
        if not self.field:
            raise TriggerError("a condition names the field it tests")
        needs_value = self.operator in {Operator.EQUALS, Operator.IN}
        if needs_value and self.value is None:
            raise TriggerError(f"{self.operator} needs a value to compare against")
        if not needs_value and self.value is not None:
            raise TriggerError(f"{self.operator} takes no value")
        if self.operator is Operator.IN:
            if not isinstance(self.value, tuple | list | frozenset):
                raise TriggerError("'in' compares against a collection")
            if None in self.value:
                # An unrecorded field reads as None, so a collection containing None
                # would fire on a hazard nobody ever wrote — which is precisely the
                # discretion this guard is supposed to narrow rather than widen.
                raise TriggerError(
                    "'in' may not include None: an unrecorded field would then satisfy it, "
                    "and a hazard the agent never recorded must not collide with anything"
                )

    def holds(self, context: MatchContext) -> bool:
        present, value = context.lookup(self.field)
        if self.operator is Operator.PRESENT:
            return present
        if self.operator is Operator.ABSENT:
            return not present
        if not present:
            return False
        if self.operator is Operator.EQUALS:
            return bool(value == self.value)
        assert isinstance(self.value, tuple | list | frozenset)
        return value in self.value


@dataclass(frozen=True)
class Trigger:
    """One catalogue row. A conjunction of conditions, with the grounding behind it."""

    id: str
    grounding: Grounding
    when: tuple[Condition, ...]
    message: str
    reference: str | None = None
    rationale: str | None = None
    added_in: int = 1

    def __post_init__(self) -> None:
        if not self.id or not self.message:
            raise TriggerError("a trigger carries an id and the message a challenge shows")
        if not self.when:
            raise TriggerError(
                f"{self.id!r} has no conditions, so it would fire on every declaration"
            )
        if self.grounding is Grounding.CITED:
            if not self.reference:
                raise TriggerError(f"{self.id!r} is cited and must name the SRD section")
            if self.rationale:
                raise TriggerError(f"{self.id!r} is cited, so it points at a section, not a case")
        else:
            if not self.rationale:
                raise TriggerError(
                    f"{self.id!r} is authored and must state why it warrants a check. The SRD "
                    "leaves most of that to judgment, so the judgment is the record"
                )
            if self.reference:
                raise TriggerError(
                    f"{self.id!r} is authored; a section reference would claim grounding it "
                    "does not have"
                )

    def fires(self, context: MatchContext) -> bool:
        """Every condition must hold. There is no disjunction — an "or" is a second row."""
        return all(condition.holds(context) for condition in self.when)


@dataclass(frozen=True)
class Catalogue:
    """The versioned set of rows, and the fixed matcher over them."""

    version: int
    triggers: tuple[Trigger, ...] = ()

    def __post_init__(self) -> None:
        if self.version < 1:
            raise TriggerError("a catalogue version starts at 1")
        seen: set[str] = set()
        for trigger in self.triggers:
            if trigger.id in seen:
                raise TriggerError(f"{trigger.id!r} appears twice; a catalogue has one row per id")
            seen.add(trigger.id)
        object.__setattr__(self, "triggers", tuple(sorted(self.triggers, key=lambda t: t.id)))

    def matching(self, context: MatchContext) -> tuple[Trigger, ...]:
        """Every row that fires, in identifier order — not the first, and not one of them."""
        return tuple(trigger for trigger in self.triggers if trigger.fires(context))

    def __len__(self) -> int:
        return len(self.triggers)


def challenge_text(fired: tuple[Trigger, ...]) -> str:
    """What the challenge tells the agent: each row, its grounding, and its message."""
    return "; ".join(
        f"{t.id} ({t.grounding}: {t.reference or t.rationale}) — {t.message}" for t in fired
    )
