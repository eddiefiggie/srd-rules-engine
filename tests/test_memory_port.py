"""The port's vocabulary: typed values, declared defaults, namespaces, and provenance.

The load-bearing property is that prose cannot be stored as a core fact — not because a
rule forbids it, but because no core type can hold it. The moment the engine reads prose
it is interpreting narrative again, which is the capability the whole design removes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    DefaultKind,
    Fact,
    FactType,
    Ledger,
    LedgerBackedPort,
    MemoryError_,
    Provenance,
    ValueKind,
    Writer,
    check_storable,
    fact_from_payload,
    fact_write_payload,
    is_extension,
    read_ledger,
    resolve,
)
from srd_rules_engine.memory.store import JsonMemoryStore

ATTITUDE = FactType(
    name="attitude",
    kind=ValueKind.CHOICE,
    choices=("friendly", "indifferent", "hostile"),
    default_kind=DefaultKind.SRD_PRESCRIBED,
    default="indifferent",
)
INSPIRATION = FactType(name="inspiration", kind=ValueKind.BOOLEAN)
TRUE_NAME_KNOWN = FactType(
    name="true_name_known",
    kind=ValueKind.BOOLEAN,
    default_kind=DefaultKind.ENGINE_CHOSEN,
    default=False,
)

RULED = Provenance(writer=Writer.RULING, reference="7")


def store(tmp_path: Path) -> JsonMemoryStore:
    return JsonMemoryStore(tmp_path / "memory.json")


# --- Typed values only, never prose ------------------------------------------------


def test_a_choice_type_refuses_anything_but_its_choices() -> None:
    """This is the structural form of "never prose" — there is no free-text kind at all."""
    ATTITUDE.check("friendly")
    with pytest.raises(MemoryError_, match="never prose"):
        ATTITUDE.check("cautiously warm after the incident at the bridge")


def test_an_integer_type_refuses_a_boolean() -> None:
    """`bool` subclasses `int`, so an unguarded check would accept True as a number."""
    with pytest.raises(MemoryError_, match="holds an integer"):
        FactType(name="favour", kind=ValueKind.INTEGER).check(True)


def test_a_boolean_type_refuses_an_integer() -> None:
    with pytest.raises(MemoryError_, match="holds a boolean"):
        INSPIRATION.check(1)


def test_a_choice_type_refuses_a_non_string() -> None:
    with pytest.raises(MemoryError_, match="one of"):
        ATTITUDE.check(3)


def test_a_choice_type_must_declare_choices() -> None:
    with pytest.raises(MemoryError_, match="declares no choices"):
        FactType(name="mood", kind=ValueKind.CHOICE)


def test_a_non_choice_type_may_not_declare_choices() -> None:
    with pytest.raises(MemoryError_, match="not a choice type"):
        FactType(name="favour", kind=ValueKind.INTEGER, choices=("a",))


def test_a_float_is_refused_because_the_write_must_be_ledger_representable() -> None:
    with pytest.raises(MemoryError_, match="no ledger value may be one"):
        check_storable("weight", 1.5)


# --- R22: what an absence means ----------------------------------------------------


def test_a_held_value_resolves_without_defaulting(tmp_path: Path) -> None:
    memory = store(tmp_path)
    memory.put(Fact("attitude", "innkeeper", "friendly", RULED))

    resolution = resolve(memory, ATTITUDE, "innkeeper")
    assert resolution.value == "friendly"
    assert resolution.defaulted is None
    assert resolution.provenance == RULED
    assert not resolution.blocked


def test_an_absent_value_applies_the_default_and_names_which_kind(tmp_path: Path) -> None:
    """The Ruling must be able to say it defaulted, and say what kind of default it was."""
    resolution = resolve(store(tmp_path), ATTITUDE, "stranger")
    assert resolution.value == "indifferent"
    assert resolution.defaulted is DefaultKind.SRD_PRESCRIBED
    assert not resolution.blocked


def test_an_engine_chosen_default_is_distinguishable_from_an_srd_prescribed_one(
    tmp_path: Path,
) -> None:
    """They are epistemically different, so a Ruling must not present them alike."""
    resolution = resolve(store(tmp_path), TRUE_NAME_KNOWN, "lich")
    assert resolution.defaulted is DefaultKind.ENGINE_CHOSEN


def test_a_type_with_no_honest_default_blocks_rather_than_inventing(tmp_path: Path) -> None:
    resolution = resolve(store(tmp_path), INSPIRATION, "pc")
    assert resolution.value is None
    assert resolution.blocked


def test_a_type_classified_as_having_no_default_may_not_supply_one() -> None:
    with pytest.raises(MemoryError_, match="yet supplies one"):
        FactType(name="favour", default_kind=DefaultKind.ABSENT, default=3)


def test_a_declared_default_must_satisfy_its_own_type() -> None:
    with pytest.raises(MemoryError_, match="never prose"):
        FactType(
            name="attitude",
            kind=ValueKind.CHOICE,
            choices=("friendly",),
            default_kind=DefaultKind.SRD_PRESCRIBED,
            default="wary",
        )


# --- R24: a namespace is what makes a type an extension ----------------------------


def test_a_namespace_is_what_makes_a_type_an_extension() -> None:
    assert not is_extension("attitude")
    assert is_extension("com.example.tool.mood")
    assert is_extension("io.github.someone.thing")


def test_an_extension_type_cannot_be_declared_as_a_core_type() -> None:
    """No engine rule may consume one, so declaring one here would be meaningless."""
    with pytest.raises(MemoryError_, match="carries a namespace"):
        FactType(name="com.example.tool.mood")


# --- R25: a write cannot happen without being recorded -----------------------------


def test_a_ledger_backed_put_records_the_write(tmp_path: Path) -> None:
    ledger = Ledger.open(
        tmp_path / "l.jsonl", engine_version="test", catalogue_version=1, session_id="s"
    )
    port = LedgerBackedPort(store(tmp_path), ledger)
    port.put(Fact("attitude", "innkeeper", "hostile", RULED))
    ledger.commit()

    writes = [e for e in read_ledger(tmp_path / "l.jsonl").entries if e.type == "fact-write"]
    assert len(writes) == 1
    assert writes[0].payload["subject"] == "innkeeper"


def test_a_recorded_write_round_trips_through_its_payload() -> None:
    fact = Fact("attitude", "innkeeper", "hostile", RULED)
    assert fact_from_payload(fact_write_payload(fact)) == fact


def test_a_payload_with_no_provenance_is_refused() -> None:
    with pytest.raises(MemoryError_, match="no usable provenance"):
        fact_from_payload({"type": "attitude", "subject": "x", "value": 1, "provenance": {}})


def test_a_payload_naming_no_type_is_refused() -> None:
    with pytest.raises(MemoryError_, match="names no type"):
        fact_from_payload({"subject": "x", "value": 1, "provenance": RULED.as_payload()})


def test_provenance_distinguishes_a_ruling_from_an_out_of_band_write() -> None:
    """R25: a consumed fact traces to the ruling that produced it, or to an explicit entry."""
    out_of_band = Provenance(writer=Writer.OUT_OF_BAND, reference="session-notes")
    assert out_of_band.writer is not RULED.writer
    assert (
        fact_from_payload(
            fact_write_payload(Fact("attitude", "x", "friendly", out_of_band))
        ).provenance
        == out_of_band
    )


def test_a_float_never_reaches_the_ledger_through_a_fact_write() -> None:
    with pytest.raises(MemoryError_, match="no ledger value may be one"):
        fact_write_payload(Fact("weight", "pc", 1.5, RULED))
