"""The supported way to consume a ledger. The on-disk format is not public API; this is.

A consumer that parses the file makes the file an interface whether or not anyone
intended it, and the first bug fix that changes a field then breaks them. The reader
exists so there is something stable to depend on instead.

**Three tiers, not two.** The envelope is fixed for the life of the project, so
integrity checking, sequence checking, and listing work across every payload version
ever written and never need a known `v`. Interpreting a payload is separate: the
reader compares its own version against the payload's `compat` floor — the lowest
reader version that can correctly read it. At or above the floor, interpret. Below it,
the entry is reported **unauditable** and its envelope is still listed, never silently
skipped. Most schema changes are additive, and without the floor every one of them
would make old archives unreadable to exactly the retrospective audit that exists to
read them.

**Nothing is repaired on the way past.** A torn tail is reported and truncation is an
explicit operation, because a crashed session must stay reopenable and a silent
truncation is indistinguishable from a ledger that was always that length.

Four corruptions are named distinctly, because they mean different things:

- `torn-tail` — the last line does not parse. Crash mid-write; the reachable one.
- `checksum-mismatch` — an entry's recorded `sum` is not the digest of its body.
- `chain-break` — an entry's `prev` does not name its predecessor's true digest. This
  is what catches an edit whose checksum was **recomputed**, which a checksum alone
  cannot see.
- `sequence-gap` — a `seq` that does not follow its predecessor's.

See `docs/decisions/0006-ledger-format.md` and `docs/decisions/0002-ledger-durability.md`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from srd_rules_engine.core.canonical import CanonicalizationError, digest
from srd_rules_engine.core.ledger import COMPAT

#: The highest payload schema version this reader knows how to interpret. A payload
#: whose `compat` floor is at or below this is interpretable even when its own `v` is
#: higher — that is the whole point of the floor.
READER_VERSION: Final = 1

TORN_TAIL: Final = "torn-tail"
MALFORMED_ENTRY: Final = "malformed-entry"
CHECKSUM_MISMATCH: Final = "checksum-mismatch"
CHAIN_BREAK: Final = "chain-break"
SEQUENCE_GAP: Final = "sequence-gap"
MISSING_COMPAT: Final = "missing-compat"


@dataclass(frozen=True)
class Finding:
    """One integrity problem, named so it can be told apart from the others."""

    kind: str
    line: int
    seq: int | None
    detail: str

    def __str__(self) -> str:
        where = f"line {self.line}" + (f" (seq {self.seq})" if self.seq is not None else "")
        return f"{self.kind} at {where}: {self.detail}"


@dataclass(frozen=True)
class Entry:
    """One ledger entry as read. `interpretable` is the compat tier, not a defect."""

    seq: int
    type: str
    v: int
    prev: str | None
    sum: str
    payload: Mapping[str, object]
    line: int
    interpretable: bool


@dataclass(frozen=True)
class LedgerReport:
    """Everything the reader can say about a ledger, whether or not it is intact."""

    path: Path
    reader_version: int
    entries: tuple[Entry, ...] = ()
    findings: tuple[Finding, ...] = field(default=())

    @property
    def intact(self) -> bool:
        return not self.findings

    @property
    def torn_tail(self) -> bool:
        return any(f.kind == TORN_TAIL for f in self.findings)

    @property
    def unauditable(self) -> tuple[Entry, ...]:
        """Listed, chain-checked, and not interpretable by this reader."""
        return tuple(e for e in self.entries if not e.interpretable)

    def findings_of(self, kind: str) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.kind == kind)


def read_ledger(path: Path | str, *, reader_version: int = READER_VERSION) -> LedgerReport:
    """Read and verify a ledger. Never raises on a damaged file, and never repairs one."""
    path = Path(path)
    if not path.exists():
        return LedgerReport(path=path, reader_version=reader_version)

    lines = [
        (number, raw.strip())
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if raw.strip()
    ]

    entries: list[Entry] = []
    findings: list[Finding] = []
    previous: Mapping[str, object] | None = None
    previous_seq: int | None = None

    for position, (line_number, text) in enumerate(lines):
        is_last = position == len(lines) - 1
        raw_entry = _parse(text)
        if raw_entry is None:
            kind = TORN_TAIL if is_last else MALFORMED_ENTRY
            findings.append(
                Finding(
                    kind=kind,
                    line=line_number,
                    seq=None,
                    detail=(
                        "the line does not parse as an entry"
                        + (" — a write was interrupted here" if is_last else "")
                    ),
                )
            )
            continue

        envelope = _envelope(raw_entry)
        if envelope is None:
            findings.append(
                Finding(
                    kind=MALFORMED_ENTRY,
                    line=line_number,
                    seq=None,
                    detail="the entry parses but its envelope is not the fixed shape",
                )
            )
            continue

        seq, entry_type, v, prev, recorded_sum, payload = envelope
        true_sum = _true_digest(raw_entry)

        if true_sum is None:
            findings.append(
                Finding(
                    kind=MALFORMED_ENTRY,
                    line=line_number,
                    seq=seq,
                    detail="the entry has no canonical form, so its digest cannot be checked",
                )
            )
        elif true_sum != recorded_sum:
            findings.append(
                Finding(
                    kind=CHECKSUM_MISMATCH,
                    line=line_number,
                    seq=seq,
                    detail="the recorded sum is not the digest of this entry's body",
                )
            )

        if previous_seq is not None and seq != previous_seq + 1:
            findings.append(
                Finding(
                    kind=SEQUENCE_GAP,
                    line=line_number,
                    seq=seq,
                    detail=f"follows seq {previous_seq}, so an entry is missing or reordered",
                )
            )

        expected_prev = _true_digest(previous) if previous is not None else None
        if prev != expected_prev:
            findings.append(
                Finding(
                    kind=CHAIN_BREAK,
                    line=line_number,
                    seq=seq,
                    detail=(
                        "prev does not name the true digest of the preceding entry"
                        if previous is not None
                        else "the first entry names a predecessor it cannot have"
                    ),
                )
            )

        interpretable, compat_finding = _compat_tier(payload, v, seq, line_number, reader_version)
        if compat_finding is not None:
            findings.append(compat_finding)

        entries.append(
            Entry(
                seq=seq,
                type=entry_type,
                v=v,
                prev=prev,
                sum=recorded_sum,
                payload=payload,
                line=line_number,
                interpretable=interpretable,
            )
        )
        previous, previous_seq = raw_entry, seq

    return LedgerReport(
        path=path,
        reader_version=reader_version,
        entries=tuple(entries),
        findings=tuple(findings),
    )


def repair_truncated_tail(path: Path | str, *, reader_version: int = READER_VERSION) -> int:
    """Drop a torn trailing line, and only that. Returns the number of lines removed.

    Refuses when the damage is anywhere but the tail: truncating past a deleted middle
    entry would discard sound records to hide a problem truncation cannot fix.
    """
    path = Path(path)
    report = read_ledger(path, reader_version=reader_version)
    if not report.torn_tail:
        return 0

    other = [f for f in report.findings if f.kind not in {TORN_TAIL, MISSING_COMPAT}]
    if other:
        raise ValueError(
            "this ledger is damaged before its tail, which truncation cannot repair: "
            + "; ".join(str(f) for f in other)
        )

    kept = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    torn = {f.line for f in report.findings_of(TORN_TAIL)}
    remaining = [line for number, line in enumerate(kept, start=1) if number not in torn]
    path.write_text("".join(f"{line}\n" for line in remaining), encoding="utf-8")
    return len(torn)


# --- Helpers ----------------------------------------------------------------------


def _parse(text: str) -> Mapping[str, object] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _envelope(
    entry: Mapping[str, object],
) -> tuple[int, str, int, str | None, str, Mapping[str, object]] | None:
    seq, entry_type, v = entry.get("seq"), entry.get("type"), entry.get("v")
    recorded_sum, payload = entry.get("sum"), entry.get("payload")
    prev = entry.get("prev")

    if isinstance(seq, bool) or not isinstance(seq, int):
        return None
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    if not isinstance(entry_type, str) or not isinstance(recorded_sum, str):
        return None
    if not isinstance(payload, dict):
        return None
    if prev is not None and not isinstance(prev, str):
        return None
    return seq, entry_type, v, prev, recorded_sum, payload


def _true_digest(entry: Mapping[str, object] | None) -> str | None:
    """The digest an entry's body actually has, which is not always the one it records."""
    if entry is None:
        return None
    try:
        return digest({k: v for k, v in entry.items() if k != "sum"})
    except CanonicalizationError:
        return None


def _compat_tier(
    payload: Mapping[str, object], v: int, seq: int, line: int, reader_version: int
) -> tuple[bool, Finding | None]:
    compat = payload.get(COMPAT)
    if isinstance(compat, bool) or not isinstance(compat, int):
        return False, Finding(
            kind=MISSING_COMPAT,
            line=line,
            seq=seq,
            detail=(
                f"the payload declares no usable {COMPAT!r} floor, so whether this reader "
                "can interpret it cannot be established"
            ),
        )
    # `v` is deliberately not consulted. A payload from a future schema is interpretable
    # whenever it says an older reader can read it correctly.
    return compat <= reader_version, None


def summarize(report: LedgerReport) -> str:
    """A one-line account of a ledger, for a report header or an operator message."""
    if not report.entries and not report.findings:
        return f"{report.path.name}: empty"
    parts = [f"{len(report.entries)} entries"]
    if report.unauditable:
        parts.append(f"{len(report.unauditable)} unauditable")
    if report.findings:
        kinds = sorted({f.kind for f in report.findings})
        parts.append("damaged: " + ", ".join(kinds))
    else:
        parts.append("intact")
    return f"{report.path.name}: " + ", ".join(parts)


def entries_of_type(report: LedgerReport, entry_type: str) -> Sequence[Entry]:
    return [entry for entry in report.entries if entry.type == entry_type]
