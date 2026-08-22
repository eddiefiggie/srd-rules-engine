"""R23's five properties, which are what "sufficient to run a solo campaign" means.

The load-bearing one is the rebuild. The store holds current values only because the
ledger holds the history, and a store that cannot be reconstructed from that history is
not a projection however it is described — it is a second system of record with no
durability guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Fact,
    Ledger,
    LedgerBackedPort,
    MemoryError_,
    Provenance,
    Writer,
)
from srd_rules_engine.memory.store import JsonMemoryStore, rebuild_from_ledger

RULED = Provenance(writer=Writer.RULING, reference="7")
NOTED = Provenance(writer=Writer.OUT_OF_BAND, reference="session-notes")


def ledger_at(path: Path) -> Ledger:
    return Ledger.open(path, engine_version="test", catalogue_version=1, session_id="s")


def recorded_port(tmp_path: Path) -> tuple[LedgerBackedPort, Ledger, Path, Path]:
    store_path, ledger_path = tmp_path / "memory.json", tmp_path / "ledger.jsonl"
    ledger = ledger_at(ledger_path)
    return LedgerBackedPort(JsonMemoryStore(store_path), ledger), ledger, store_path, ledger_path


# --- Property 1: every core fact type round-trips with its declared type ------------


def test_each_typed_value_round_trips_unchanged(tmp_path: Path) -> None:
    memory = JsonMemoryStore(tmp_path / "memory.json")
    written = [
        Fact("attitude", "innkeeper", "friendly", RULED),
        Fact("inspiration", "pc", True, NOTED),
        Fact("favour", "guild", -3, RULED),
    ]
    for fact in written:
        memory.put(fact)

    for fact in written:
        held = memory.get(fact.type_name, fact.subject)
        assert held is not None
        assert held.value == fact.value
        assert type(held.value) is type(fact.value), "the declared type survives, not just the text"


def test_a_later_write_replaces_an_earlier_one(tmp_path: Path) -> None:
    memory = JsonMemoryStore(tmp_path / "memory.json")
    memory.put(Fact("attitude", "innkeeper", "friendly", RULED))
    memory.put(Fact("attitude", "innkeeper", "hostile", RULED))

    held = memory.get("attitude", "innkeeper")
    assert held is not None and held.value == "hostile"


def test_an_absent_fact_reads_as_none(tmp_path: Path) -> None:
    assert JsonMemoryStore(tmp_path / "memory.json").get("attitude", "nobody") is None


# --- Property 2: values survive a process restart ----------------------------------


def test_values_survive_reopening_the_store(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    JsonMemoryStore(path).put(Fact("attitude", "innkeeper", "friendly", RULED))

    reopened = JsonMemoryStore(path)
    held = reopened.get("attitude", "innkeeper")
    assert held is not None
    assert held.value == "friendly"
    assert held.provenance == RULED


def test_the_store_is_readable_by_a_person(tmp_path: Path) -> None:
    """Flat JSON is the point: a campaign's current state is not opaque to its owner."""
    path = tmp_path / "memory.json"
    JsonMemoryStore(path).put(Fact("attitude", "innkeeper", "friendly", RULED))

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["facts"][0]["subject"] == "innkeeper"
    assert "\n" in path.read_text(encoding="utf-8"), "indented, not minified"


# --- Property 3: the store rebuilds from the ledger --------------------------------


def test_a_rebuilt_store_is_identical_to_the_live_one(tmp_path: Path) -> None:
    """The executable form of "the store is a projection"."""
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    port.put(Fact("attitude", "innkeeper", "friendly", RULED))
    port.put(Fact("inspiration", "pc", True, NOTED))
    port.put(Fact("attitude", "innkeeper", "hostile", RULED))
    ledger.commit()

    live = dict(port.facts())
    rebuilt = rebuild_from_ledger(store_path, ledger_path)
    assert dict(rebuilt.facts()) == live


def test_a_deleted_store_is_recoverable(tmp_path: Path) -> None:
    """Store corruption costs a rebuild, not a campaign."""
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    port.put(Fact("attitude", "innkeeper", "friendly", RULED))
    ledger.commit()
    before = dict(port.facts())

    store_path.unlink()
    assert dict(rebuild_from_ledger(store_path, ledger_path).facts()) == before


def test_the_rebuild_replays_writes_in_order_so_the_latest_wins(tmp_path: Path) -> None:
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    for value in ("friendly", "indifferent", "hostile"):
        port.put(Fact("attitude", "innkeeper", value, RULED))
    ledger.commit()

    rebuilt = rebuild_from_ledger(store_path, ledger_path)
    held = rebuilt.get("attitude", "innkeeper")
    assert held is not None and held.value == "hostile"


def test_a_rebuild_discards_what_the_ledger_does_not_account_for(tmp_path: Path) -> None:
    """The ledger is authoritative, so a rebuild reproduces it exactly — not it plus extras.

    A stray value in the store is precisely the corruption a rebuild exists to clear. One
    that survived would be a fact with no recorded provenance, which is the shape of an
    outcome nothing ruled.
    """
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    port.put(Fact("attitude", "innkeeper", "friendly", RULED))
    ledger.commit()

    JsonMemoryStore(store_path).put(Fact("inspiration", "pc", True, NOTED))
    assert JsonMemoryStore(store_path).get("inspiration", "pc") is not None

    rebuilt = rebuild_from_ledger(store_path, ledger_path)
    assert rebuilt.get("inspiration", "pc") is None, "not in the ledger, so not in the store"
    assert rebuilt.get("attitude", "innkeeper") is not None


def test_the_rebuild_ignores_entries_that_are_not_fact_writes(tmp_path: Path) -> None:
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    ledger.append("ruling", v=1, payload={"compat": 1, "roll": 17})
    port.put(Fact("attitude", "innkeeper", "friendly", RULED))
    ledger.append("narration", v=1, payload={"compat": 1, "text": "the door opens"})
    ledger.commit()

    assert len(rebuild_from_ledger(store_path, ledger_path).facts()) == 1


def test_a_rebuild_refuses_a_fact_write_it_cannot_interpret(tmp_path: Path) -> None:
    """Silently skipping one would produce a store that is quietly missing a value."""
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    port.put(Fact("attitude", "innkeeper", "friendly", RULED))
    ledger.commit()

    rows = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
    entry = json.loads(rows[-1])
    entry["payload"] = {**entry["payload"], "compat": 99}
    body = {k: v for k, v in entry.items() if k != "sum"}
    from srd_rules_engine.core import digest

    rows[-1] = json.dumps({**body, "sum": digest(body)})
    ledger_path.write_text("".join(f"{r}\n" for r in rows), encoding="utf-8")

    with pytest.raises(MemoryError_, match="compat floor"):
        rebuild_from_ledger(store_path, ledger_path)


# --- Property 4: extensions round-trip opaquely ------------------------------------


def test_an_extension_fact_in_an_unknown_namespace_round_trips_unchanged(
    tmp_path: Path,
) -> None:
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    extension = Fact(
        "com.example.tool.mood",
        "innkeeper",
        {"schema": 3, "state": "brooding", "tags": ["rain", "debt"]},
        NOTED,
    )
    port.put(extension)
    ledger.commit()

    rebuilt = rebuild_from_ledger(store_path, ledger_path)
    held = rebuilt.get("com.example.tool.mood", "innkeeper")
    assert held is not None
    assert held.value == extension.value, "stored and returned, never interpreted"


def test_an_extension_whose_version_is_absent_or_malformed_round_trips_without_error(
    tmp_path: Path,
) -> None:
    """The engine has no basis for an opinion about a namespace it does not interpret."""
    memory = JsonMemoryStore(tmp_path / "memory.json")
    values: tuple[object, ...] = (
        {"state": "wary"},
        {"schema": "not-a-number", "state": "wary"},
        [],
    )
    for value in values:
        memory.put(Fact("io.github.someone.thing", "npc", value, NOTED))
        held = memory.get("io.github.someone.thing", "npc")
        assert held is not None and held.value == value


def test_an_extension_value_must_still_be_ledger_representable(tmp_path: Path) -> None:
    """Not interpreted is not unconstrained — a fact write appends to the ledger."""
    memory = JsonMemoryStore(tmp_path / "memory.json")
    with pytest.raises(MemoryError_, match="no ledger value may be one"):
        memory.put(Fact("com.example.tool.mood", "npc", {"weight": 1.5}, NOTED))


# --- Property 5: a read returns provenance sufficient to cite ----------------------


def test_a_read_returns_provenance_naming_the_ruling_that_produced_it(
    tmp_path: Path,
) -> None:
    memory = JsonMemoryStore(tmp_path / "memory.json")
    memory.put(Fact("attitude", "innkeeper", "friendly", RULED))

    held = memory.get("attitude", "innkeeper")
    assert held is not None
    assert held.provenance.writer is Writer.RULING
    assert held.provenance.reference == "7", "enough to cite the ruling in a Ruling"


def test_provenance_survives_a_rebuild(tmp_path: Path) -> None:
    port, ledger, store_path, ledger_path = recorded_port(tmp_path)
    port.put(Fact("attitude", "innkeeper", "friendly", NOTED))
    ledger.commit()

    held = rebuild_from_ledger(store_path, ledger_path).get("attitude", "innkeeper")
    assert held is not None and held.provenance == NOTED


# --- The store is a projection, and says so when it cannot be read -----------------


def test_an_unreadable_store_names_the_rebuild_rather_than_the_loss(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(MemoryError_, match="rebuild_from_ledger"):
        JsonMemoryStore(path)


def test_a_store_with_no_facts_list_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    path.write_text('{"store_version": 1}', encoding="utf-8")
    with pytest.raises(MemoryError_, match="no facts list"):
        JsonMemoryStore(path)


def test_the_store_is_created_with_its_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "campaigns" / "one" / "memory.json"
    JsonMemoryStore(path).put(Fact("attitude", "innkeeper", "friendly", RULED))
    assert path.exists()
