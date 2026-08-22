"""The append-only ledger: the system of record, and the thing nothing escapes ahead of.

R26 requires every declaration, challenge, rejection, ruling, and fact write to append
here, and requires that a Ruling, challenge, or rejection is **not returned until its
entry is durable**. An outcome that never left the engine is not lost; the only bad
state is one that reached the caller with no durable trace, which is the project's
defining defect arriving through the back door.

So the durability boundary is the *escape* boundary rather than the roll. Entries
buffer, and one synchronising write covers all of them at the point an outcome would
become visible — declarations, resolved facts, and challenges ride along in the same
sync as the ruling they precede.

**The envelope is fixed for the life of the project**: `seq`, `type`, `v`, `prev`,
`sum`, `payload`. Integrity checking and listing therefore work across every payload
version ever written, and only interpreting a payload needs a version the reader knows.
`v` versions the payload alone, and every payload carries the reserved `compat` key
naming the lowest reader version that can correctly interpret it.

`sum` is the digest of the entry with `sum` itself omitted — so it covers `seq`, `type`,
`v`, `prev`, and `payload` — and `prev` is the previous entry's `sum`. That makes the
chain detect the one corruption a checksum alone cannot: an edited value whose checksum
was recomputed.

**A failed append raises rather than returning a status.** Infrastructure failure is not
a rules outcome, and a `blocked`-shaped status would invite an agent to re-declare
against a full disk.

See `docs/decisions/0002-ledger-durability.md` and `docs/decisions/0006-ledger-format.md`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.canonical import CanonicalizationError, canonicalize, digest

# The on-disk container's own version, distinct from any payload's `v`.
FORMAT_VERSION: Final = 1

# Fixed for the life of the project. Nothing may be added here later, which is why
# `compat` lives inside the payload instead.
ENVELOPE_FIELDS: Final = ("seq", "type", "v", "prev", "sum", "payload")

SESSION: Final = "session"

ENTRY_TYPES: Final = frozenset(
    {
        SESSION,
        "declaration",
        "challenge",
        "rejection",
        "ruling",
        "fact-write",
        "narration",
        "exhaustion",
    }
)

# The reserved payload key. The second permanently reserved name in the format, after
# the envelope fields — every payload schema inherits it.
COMPAT: Final = "compat"


class LedgerUnavailable(Exception):
    """The ledger could not be written, so nothing may be returned to a caller.

    Deliberately not a rules status. A caller can fix a missing fact by supplying it;
    it cannot fix a full disk by re-declaring.
    """


class Ledger:
    """An open ledger, positioned to append after its last durable entry."""

    def __init__(self, path: Path, next_seq: int, prev_sum: str | None) -> None:
        self._path = path
        self._next_seq = next_seq
        self._prev_sum = prev_sum
        self._buffer: list[str] = []

    # --- Opening ------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        path: Path | str,
        *,
        engine_version: str,
        catalogue_version: int,
        session_id: str,
    ) -> Ledger:
        """Open or create a ledger, ready to append after its last durable entry.

        A new file gets a `session` entry at `seq` 0 carrying the format, engine, and
        trigger-catalogue versions. Reopening under a *different* engine version appends
        a new session entry rather than continuing the old one, so every entry's
        governing engine version is the nearest preceding session entry — always
        answerable, never inferred.
        """
        path = Path(path)
        next_seq, prev_sum, governing_engine = _tail_state(path)
        ledger = cls(path, next_seq, prev_sum)

        if governing_engine is None or governing_engine != engine_version:
            ledger.append(
                SESSION,
                v=1,
                payload={
                    COMPAT: 1,
                    "format_version": FORMAT_VERSION,
                    "engine_version": engine_version,
                    "catalogue_version": catalogue_version,
                    "session_id": session_id,
                },
            )
            ledger.commit()
        return ledger

    # --- Appending ----------------------------------------------------------------

    @property
    def next_seq(self) -> int:
        return self._next_seq

    @property
    def pending(self) -> int:
        """Entries buffered but not yet durable. Nothing may escape while this is > 0."""
        return len(self._buffer)

    def append(self, entry_type: str, *, v: int, payload: Mapping[str, object]) -> None:
        """Buffer an entry. It is not durable until `commit`."""
        if entry_type not in ENTRY_TYPES:
            raise LedgerUnavailable(
                f"{entry_type!r} is not a ledger entry type; expected one of "
                f"{', '.join(sorted(ENTRY_TYPES))}"
            )
        _validate_payload(payload, v)

        entry: dict[str, object] = {"seq": self._next_seq, "type": entry_type, "v": v}
        if self._prev_sum is not None:
            entry["prev"] = self._prev_sum
        entry["payload"] = dict(payload)

        try:
            entry["sum"] = digest(entry)
            line = canonicalize(entry).decode("utf-8")
        except CanonicalizationError as exc:
            raise LedgerUnavailable(f"entry {self._next_seq} has no canonical form: {exc}") from exc

        self._buffer.append(line)
        self._prev_sum = str(entry["sum"])
        self._next_seq += 1

    def commit(self) -> None:
        """Make every buffered entry durable in one synchronising write.

        One `fsync` per call, not per entry — the whole point of buffering is that a
        turn's declarations and challenges are covered by the same sync as the ruling
        they precede.
        """
        if not self._buffer:
            return
        blob = "".join(f"{line}\n" for line in self._buffer)
        try:
            created = not self._path.exists()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            if created:
                _fsync_directory(self._path.parent)
        except OSError as exc:
            raise LedgerUnavailable(f"could not append to {self._path.name}: {exc}") from exc
        self._buffer.clear()

    @contextmanager
    def escape_boundary(self) -> Iterator[Ledger]:
        """Commit on the way out, so an outcome cannot escape ahead of its record.

        Leaving by exception discards the buffer rather than committing it: nobody saw
        the outcome, nothing was narrated, and on restart the agent simply re-declares.
        """
        try:
            yield self
        except BaseException:
            self._buffer.clear()
            raise
        self.commit()


# --- Helpers ----------------------------------------------------------------------


def _validate_payload(payload: Mapping[str, object], v: int) -> None:
    if COMPAT not in payload:
        raise LedgerUnavailable(
            f"the payload carries no {COMPAT!r} key. Every payload names the lowest "
            "reader version that can correctly interpret it, so an additive change "
            "stays readable by older readers"
        )
    compat = payload[COMPAT]
    if isinstance(compat, bool) or not isinstance(compat, int):
        raise LedgerUnavailable(f"{COMPAT!r} must be an integer, not {type(compat).__name__}")
    if compat < 1:
        raise LedgerUnavailable(f"{COMPAT!r} must be at least 1, not {compat}")
    if compat > v:
        raise LedgerUnavailable(
            f"{COMPAT!r} is {compat} but the payload version is {v}; a payload no reader "
            "of its own version can interpret has no coherent meaning"
        )


def _fsync_directory(directory: Path) -> None:
    """Make a newly created file's directory entry durable, not just its contents."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover - not every platform permits it
        pass
    finally:
        os.close(fd)


def _tail_state(path: Path) -> tuple[int, str | None, str | None]:
    """Read the last entry to position the writer: next seq, previous sum, engine version.

    The writer reads only what it needs to continue the chain. Verifying the whole
    ledger, and repairing a torn tail, belong to the reader.
    """
    if not path.exists() or path.stat().st_size == 0:
        return 0, None, None

    last_line = ""
    governing_engine: str | None = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                stripped = raw.strip()
                if not stripped:
                    continue
                last_line = stripped
                entry = _parse_or_none(stripped)
                if entry is not None and entry.get("type") == SESSION:
                    payload = entry.get("payload")
                    if isinstance(payload, dict):
                        engine = payload.get("engine_version")
                        governing_engine = engine if isinstance(engine, str) else None
    except OSError as exc:
        raise LedgerUnavailable(f"could not read {path.name}: {exc}") from exc

    entry = _parse_or_none(last_line)
    if entry is None:
        raise LedgerUnavailable(
            f"{path.name} ends in a partial entry, so the chain cannot be continued. "
            "Read it with the ledger reader, which reports a torn tail and offers "
            "truncation to the last valid entry as an explicit repair"
        )

    seq, checksum = entry.get("seq"), entry.get("sum")
    if not isinstance(seq, int) or isinstance(seq, bool) or not isinstance(checksum, str):
        raise LedgerUnavailable(f"{path.name} ends in an entry with no usable seq or sum")
    return seq + 1, checksum, governing_engine


def _parse_or_none(line: str) -> Mapping[str, object] | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return MappingProxyType(parsed) if isinstance(parsed, dict) else None
