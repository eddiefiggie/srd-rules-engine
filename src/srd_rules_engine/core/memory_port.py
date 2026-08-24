"""The typed port narrative facts reach rulings through, and the vocabulary it speaks.

R20 says the port returns typed values only, never prose. The moment the engine reads
prose it is interpreting narrative again, which is the capability being removed — so the
enforcement here is structural rather than advisory: **there is no free-text fact kind.**
A core fact is an integer, a boolean, or a choice from a set its type declares. Prose
cannot be stored as a core fact because no type can hold it.

Three further rules shape the vocabulary:

- **R22 — every core type declares what its absence means.** `srd-prescribed` when the
  SRD states the default, `engine-chosen` when the engine picks one and says so, and
  `absent` when no default is honest and the engine must stop rather than invent. The
  classification does not apply to extension types, since no rule consumes one.
- **R24 — a namespace is what makes a type an extension.** Core types are unnamespaced;
  `com.example.tool.mood` is not core. The distinction costs no lookup and cannot drift
  out of step with a list someone maintains. Extensions are stored and returned
  unchanged: the engine records a namespace's declared version and never interprets it,
  so absent or malformed is not an error.
- **R25 — every write appends to the ledger with provenance.** That is what makes the
  ledger authoritative over fact history and the store a rebuildable projection of it,
  and it is why `LedgerBackedPort` exists: a put that did not record would silently
  break the rebuild, so recording is not left to the implementer.

See `docs/decisions/0008-extension-channel.md` and
`docs/decisions/0009-reference-memory-store.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from srd_rules_engine.core.canonical import CanonicalizationError, canonicalize
from srd_rules_engine.core.ledger import COMPAT, Ledger

FACT_WRITE: Final = "fact-write"
FACT_PAYLOAD_VERSION: Final = 1
#: The lowest reader version that can read a fact payload, which is not the same number as
#: the schema version above (#106, decision 0022). This one was a live landmine rather than
#: a latent one: `memory.store.rebuild` **raises** on an uninterpretable fact write, so
#: bumping `FACT_PAYLOAD_VERSION` would have made every store rebuild fail outright.
FACT_PAYLOAD_COMPAT: Final = 1


class DefaultKind(StrEnum):
    """What a core fact type's absence means. R22, and only for core types."""

    SRD_PRESCRIBED = "srd-prescribed"
    ENGINE_CHOSEN = "engine-chosen"
    ABSENT = "absent"


class ValueKind(StrEnum):
    """The typed shapes a core fact may take. There is deliberately no prose kind."""

    INTEGER = "integer"
    BOOLEAN = "boolean"
    CHOICE = "choice"


class Writer(StrEnum):
    """Who may write a fact type, and how a recorded value is traced back (R25)."""

    RULING = "ruling"
    OUT_OF_BAND = "out-of-band"


class MemoryError_(Exception):
    """The port refused a value or a write. Never a rules status."""


@dataclass(frozen=True)
class Provenance:
    """Where a value came from, in the same vocabulary a ruling entry uses."""

    writer: Writer
    reference: str

    def as_payload(self) -> Mapping[str, object]:
        return {"writer": str(self.writer), "reference": self.reference}

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> Provenance:
        writer = payload.get("writer")
        reference = payload.get("reference")
        if not isinstance(writer, str) or not isinstance(reference, str):
            raise MemoryError_("a fact write carries no usable provenance")
        return cls(writer=Writer(writer), reference=reference)


@dataclass(frozen=True)
class FactType:
    """A declared fact the engine may consume, or an extension it merely stores."""

    name: str
    kind: ValueKind = ValueKind.INTEGER
    choices: tuple[str, ...] = ()
    default_kind: DefaultKind = DefaultKind.ABSENT
    default: object | None = None
    writable_by: frozenset[Writer] = frozenset({Writer.RULING, Writer.OUT_OF_BAND})

    def __post_init__(self) -> None:
        if is_extension(self.name):
            raise MemoryError_(
                f"{self.name!r} carries a namespace, so it is an extension type. "
                "Extensions are stored and returned unchanged and are never declared here"
            )
        if self.kind is ValueKind.CHOICE and not self.choices:
            raise MemoryError_(f"{self.name!r} is a choice type but declares no choices")
        if self.kind is not ValueKind.CHOICE and self.choices:
            raise MemoryError_(f"{self.name!r} declares choices but is not a choice type")
        if self.default_kind is DefaultKind.ABSENT and self.default is not None:
            raise MemoryError_(
                f"{self.name!r} is classified as having no default, yet supplies one"
            )
        if self.default is not None:
            self.check(self.default)

    def check(self, value: object) -> None:
        """Refuse a value the type cannot hold. This is where "never prose" is enforced."""
        if self.kind is ValueKind.BOOLEAN:
            if not isinstance(value, bool):
                raise MemoryError_(f"{self.name!r} holds a boolean, not {type(value).__name__}")
            return
        if self.kind is ValueKind.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise MemoryError_(f"{self.name!r} holds an integer, not {type(value).__name__}")
            return
        if not isinstance(value, str):
            raise MemoryError_(
                f"{self.name!r} holds one of its choices, not {type(value).__name__}"
            )
        if value not in self.choices:
            raise MemoryError_(
                f"{value!r} is not one of {self.name!r}'s choices "
                f"({', '.join(self.choices)}); the port holds typed values, never prose"
            )


@dataclass(frozen=True)
class Fact:
    """A stored value with the provenance a Ruling can cite (R27)."""

    type_name: str
    subject: str
    value: object
    provenance: Provenance


def is_extension(name: str) -> bool:
    """A namespace is what makes a type an extension — no lookup, no list to maintain."""
    return "." in name


def check_storable(name: str, value: object) -> None:
    """Every value must be ledger-representable, which is where the no-float rule lands."""
    try:
        canonicalize(value)
    except CanonicalizationError as exc:
        raise MemoryError_(f"{name!r} cannot hold this value: {exc}") from exc


class MemoryPort(Protocol):
    """What the engine requires of a memory system. Implementations may be anything."""

    def get(self, type_name: str, subject: str) -> Fact | None: ...

    def put(self, fact: Fact) -> None: ...

    def facts(self) -> Mapping[tuple[str, str], Fact]: ...


class LedgerBackedPort:
    """Wraps any port so a write cannot happen without being recorded.

    R25 makes the ledger authoritative over fact history, which is the whole reason the
    store can be rebuilt from it. A put that skipped the ledger would break that quietly
    — the store would hold a value the rebuild could not produce — so recording is not
    left to the implementer to remember.
    """

    def __init__(self, inner: MemoryPort, ledger: Ledger) -> None:
        self._inner = inner
        self._ledger = ledger

    def get(self, type_name: str, subject: str) -> Fact | None:
        return self._inner.get(type_name, subject)

    def facts(self) -> Mapping[tuple[str, str], Fact]:
        return self._inner.facts()

    def put(self, fact: Fact) -> None:
        self._ledger.append(FACT_WRITE, v=FACT_PAYLOAD_VERSION, payload=fact_write_payload(fact))
        self._inner.put(fact)


def fact_write_payload(fact: Fact) -> Mapping[str, object]:
    """The ledger payload for a fact write — the shape a rebuild reads back."""
    check_storable(fact.type_name, fact.value)
    return {
        COMPAT: FACT_PAYLOAD_COMPAT,
        "type": fact.type_name,
        "subject": fact.subject,
        "value": fact.value,
        "provenance": dict(fact.provenance.as_payload()),
    }


def fact_from_payload(payload: Mapping[str, object]) -> Fact:
    """Read a fact write back out of a ledger payload."""
    type_name, subject = payload.get("type"), payload.get("subject")
    provenance = payload.get("provenance")
    if not isinstance(type_name, str) or not isinstance(subject, str):
        raise MemoryError_("a fact write names no type or subject")
    if not isinstance(provenance, dict):
        raise MemoryError_("a fact write carries no usable provenance")
    return Fact(
        type_name=type_name,
        subject=subject,
        value=payload.get("value"),
        provenance=Provenance.from_payload(provenance),
    )


@dataclass(frozen=True)
class Resolution:
    """What resolving a declared fact produced, and how honest the engine can be about it."""

    type_name: str
    subject: str
    value: object | None
    defaulted: DefaultKind | None
    provenance: Provenance | None

    @property
    def blocked(self) -> bool:
        """No value, and no default that would be honest — the engine must stop (R22)."""
        return self.value is None and self.defaulted is None


def resolve(port: MemoryPort, fact_type: FactType, subject: str) -> Resolution:
    """Resolve a declared fact, naming whether it defaulted and which kind of default.

    A rule may declare core types only, so nothing here interprets an extension.
    """
    held = port.get(fact_type.name, subject)
    if held is not None:
        return Resolution(
            type_name=fact_type.name,
            subject=subject,
            value=held.value,
            defaulted=None,
            provenance=held.provenance,
        )
    if fact_type.default_kind is DefaultKind.ABSENT:
        return Resolution(fact_type.name, subject, None, None, None)
    return Resolution(fact_type.name, subject, fact_type.default, fact_type.default_kind, None)
