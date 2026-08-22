"""The file-backed reference memory implementation: flat JSON, and a projection.

R23 requires a reference implementation sufficient to run a solo campaign with continuity
across sessions. This is it, and it is flat JSON rather than a database for a reason that
is easy to state backwards.

**The store is not the system of record.** R25 already puts every fact write in the
ledger with provenance, so the ledger holds the history and this holds only current
values — a projection, rebuildable by replay. That removes both of a database's
advantages at once rather than weighing them: transactional durability protects a system
of record, and indexed reads matter at a scale a solo campaign never reaches. What is
left is the case for a person being able to read their own campaign state, which is the
same value this engine delivers everywhere else, at the smallest scale.

It lives on a substrate separate from the ledger so the port stays swappable — a consumer
replacing this would otherwise inherit ledger machinery it has no use for.

Store corruption is recoverable. `rebuild_from_ledger` reconstructs the whole store, and
that is a supported operation rather than a recovery hack.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from srd_rules_engine.core import (
    FACT_WRITE,
    Fact,
    MemoryError_,
    Provenance,
    check_storable,
    fact_from_payload,
    read_ledger,
)

STORE_VERSION: Final = 1


class JsonMemoryStore:
    """Current fact values for one campaign, in one JSON file."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._facts: dict[tuple[str, str], Fact] = {}
        if self._path.exists():
            self._load()

    # --- The port ------------------------------------------------------------------

    def get(self, type_name: str, subject: str) -> Fact | None:
        return self._facts.get((type_name, subject))

    def put(self, fact: Fact) -> None:
        check_storable(fact.type_name, fact.value)
        self._facts[(fact.type_name, fact.subject)] = fact
        self._save()

    def facts(self) -> Mapping[tuple[str, str], Fact]:
        return dict(self._facts)

    # --- Persistence ---------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    def _save(self) -> None:
        rows = [
            {
                "type": fact.type_name,
                "subject": fact.subject,
                "value": fact.value,
                "provenance": dict(fact.provenance.as_payload()),
            }
            for fact in sorted(self._facts.values(), key=lambda f: (f.type_name, f.subject))
        ]
        document = {"store_version": STORE_VERSION, "facts": rows}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")

    def _load(self) -> None:
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MemoryError_(
                f"{self._path.name} is not readable as a store. It is a projection, so "
                "rebuild_from_ledger reconstructs it rather than losing the campaign"
            ) from exc

        rows = document.get("facts") if isinstance(document, dict) else None
        if not isinstance(rows, list):
            raise MemoryError_(f"{self._path.name} carries no facts list")

        for row in rows:
            if not isinstance(row, dict):
                raise MemoryError_(f"{self._path.name} carries a malformed fact row")
            provenance = row.get("provenance")
            if not isinstance(provenance, dict):
                raise MemoryError_(f"{self._path.name} carries a fact with no provenance")
            fact = Fact(
                type_name=str(row.get("type")),
                subject=str(row.get("subject")),
                value=row.get("value"),
                provenance=Provenance.from_payload(provenance),
            )
            self._facts[(fact.type_name, fact.subject)] = fact


def rebuild_from_ledger(store_path: Path | str, ledger_path: Path | str) -> JsonMemoryStore:
    """Reconstruct a store by replaying the ledger's fact writes, latest write winning.

    This is the executable form of "the store is a projection". A store that cannot be
    rebuilt is not one, however it is described.
    """
    store_path = Path(store_path)
    if store_path.exists():
        store_path.unlink()

    store = JsonMemoryStore(store_path)
    report = read_ledger(ledger_path)
    for entry in report.entries:
        if entry.type != FACT_WRITE:
            continue
        if not entry.interpretable:
            raise MemoryError_(
                f"the fact write at seq {entry.seq} declares a compat floor this reader "
                "cannot meet, so the store cannot be rebuilt from it"
            )
        store.put(fact_from_payload(entry.payload))
    return store
