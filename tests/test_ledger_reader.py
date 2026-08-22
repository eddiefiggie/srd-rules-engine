"""What the reader must catch, what it must tolerate, and what it must not touch.

Four corruptions are named distinctly because they mean different things, and the
distinction is what tells an operator whether truncation would help. The compat tier is
separate from all of them: an entry this reader cannot interpret is not damaged, and is
listed rather than skipped.

The reader never repairs on the way past and never refuses to open. A crashed session
must stay reopenable, and a silent truncation is indistinguishable from a ledger that
was always that length.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from srd_rules_engine.core import Ledger, digest, read_ledger, repair_truncated_tail, summarize
from srd_rules_engine.core.ledger import COMPAT, SESSION
from srd_rules_engine.core.ledger_reader import (
    CHAIN_BREAK,
    CHECKSUM_MISMATCH,
    MALFORMED_ENTRY,
    MISSING_COMPAT,
    SEQUENCE_GAP,
    TORN_TAIL,
)

ENGINE = "08222026.3"


def build(path: Path, count: int = 3) -> Path:
    ledger = Ledger.open(path, engine_version=ENGINE, catalogue_version=1, session_id="s-1")
    for index in range(count):
        ledger.append("ruling", v=1, payload={COMPAT: 1, "roll": 10 + index})
    ledger.commit()
    return path


def lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rewrite(path: Path, rows: list[str]) -> None:
    path.write_text("".join(f"{row}\n" for row in rows), encoding="utf-8")


def reseal(entry: dict[str, object]) -> dict[str, object]:
    """Recompute an edited entry's checksum, so only the chain can still catch it."""
    body = {k: v for k, v in entry.items() if k != "sum"}
    return {**body, "sum": digest(body)}


# --- The intact case ---------------------------------------------------------------


def test_an_intact_ledger_reports_no_findings(tmp_path: Path) -> None:
    report = read_ledger(build(tmp_path / "l.jsonl"))
    assert report.intact
    assert [e.seq for e in report.entries] == [0, 1, 2, 3]
    assert report.entries[0].type == SESSION
    assert all(e.interpretable for e in report.entries)


def test_a_missing_file_reads_as_empty_rather_than_raising(tmp_path: Path) -> None:
    report = read_ledger(tmp_path / "absent.jsonl")
    assert report.entries == ()
    assert report.intact


def test_summarize_names_the_state_in_one_line(tmp_path: Path) -> None:
    assert "intact" in summarize(read_ledger(build(tmp_path / "l.jsonl")))


# --- The four corruptions, each named distinctly -----------------------------------


def test_a_torn_tail_is_reported_and_the_file_is_left_alone(tmp_path: Path) -> None:
    path = build(tmp_path / "l.jsonl")
    before = path.read_text(encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq":4,"type":"rul')

    report = read_ledger(path)
    assert report.torn_tail
    assert [f.kind for f in report.findings] == [TORN_TAIL]
    assert path.read_text(encoding="utf-8").startswith(before), "nothing was repaired"


def test_a_deleted_middle_entry_reports_a_sequence_gap_and_a_broken_chain(
    tmp_path: Path,
) -> None:
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    rewrite(path, rows[:2] + rows[3:])

    report = read_ledger(path)
    assert {f.kind for f in report.findings} == {SEQUENCE_GAP, CHAIN_BREAK}
    assert report.findings_of(SEQUENCE_GAP)[0].seq == 3


def test_an_edit_with_a_stale_checksum_is_caught_by_the_checksum(tmp_path: Path) -> None:
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    entry = json.loads(rows[1])
    entry["payload"] = {COMPAT: 1, "roll": 20}
    rows[1] = json.dumps(entry)
    rewrite(path, rows)

    report = read_ledger(path)
    kinds = {f.kind for f in report.findings}
    assert CHECKSUM_MISMATCH in kinds
    assert report.findings_of(CHECKSUM_MISMATCH)[0].seq == 1


def test_an_edit_with_a_recomputed_checksum_still_breaks_the_chain(tmp_path: Path) -> None:
    """The corruption a checksum alone cannot see, and the whole reason `prev` exists."""
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    entry = json.loads(rows[1])
    entry["payload"] = {COMPAT: 1, "roll": 20}
    rows[1] = json.dumps(reseal(entry))
    rewrite(path, rows)

    report = read_ledger(path)
    kinds = {f.kind for f in report.findings}
    assert CHECKSUM_MISMATCH not in kinds, "the entry is internally consistent now"
    assert CHAIN_BREAK in kinds, "its successor still names the original digest"
    assert report.findings_of(CHAIN_BREAK)[0].seq == 2


def test_a_stale_checksum_edit_breaks_the_chain_as_well(tmp_path: Path) -> None:
    """The chain compares against the true digest, not the recorded one, so both fire."""
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    entry = json.loads(rows[1])
    entry["payload"] = {COMPAT: 1, "roll": 20}
    rows[1] = json.dumps(entry)
    rewrite(path, rows)

    kinds = {f.kind for f in read_ledger(path).findings}
    assert {CHECKSUM_MISMATCH, CHAIN_BREAK} <= kinds


def test_a_malformed_line_in_the_middle_is_not_a_torn_tail(tmp_path: Path) -> None:
    """Truncation repairs one of these and not the other, so they cannot share a name."""
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    rows[1] = '{"seq":1,"type":"rul'
    rewrite(path, rows)

    report = read_ledger(path)
    assert not report.torn_tail
    assert MALFORMED_ENTRY in {f.kind for f in report.findings}


def test_an_entry_whose_envelope_is_not_the_fixed_shape_is_malformed(tmp_path: Path) -> None:
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    entry = json.loads(rows[1])
    del entry["v"]
    rows[1] = json.dumps(entry)
    rewrite(path, rows)

    assert MALFORMED_ENTRY in {f.kind for f in read_ledger(path).findings}


def test_a_first_entry_claiming_a_predecessor_breaks_the_chain(tmp_path: Path) -> None:
    path = build(tmp_path / "l.jsonl", count=0)
    rows = lines(path)
    entry = json.loads(rows[0])
    entry["prev"] = "0" * 64
    rows[0] = json.dumps(reseal(entry))
    rewrite(path, rows)

    report = read_ledger(path)
    assert CHAIN_BREAK in {f.kind for f in report.findings}
    assert "cannot have" in report.findings_of(CHAIN_BREAK)[0].detail


def test_a_float_smuggled_in_by_hand_is_reported_not_crashed_on(tmp_path: Path) -> None:
    """The reader must survive a file the writer would never have produced."""
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    entry = json.loads(rows[1])
    entry["payload"] = {COMPAT: 1, "roll": 17.5}
    rows[1] = json.dumps(entry)
    rewrite(path, rows)

    report = read_ledger(path)
    assert MALFORMED_ENTRY in {f.kind for f in report.findings}
    assert len(report.entries) == 4, "the envelope is still listed"


# --- The compat tier, which is not damage ------------------------------------------


def rewrite_last(path: Path, *, v: int, compat: int) -> None:
    """Edit the final entry, which has no successor whose `prev` would then disagree.

    Resealing any earlier entry necessarily breaks the chain to the one after it — that
    is the mechanism working, and it would drown out what these tests are about.
    """
    rows = lines(path)
    entry = json.loads(rows[-1])
    entry["v"] = v
    entry["payload"] = {COMPAT: compat, "roll": 12}
    rows[-1] = json.dumps(reseal(entry))
    rewrite(path, rows)


def test_a_payload_above_the_readers_floor_is_unauditable_but_still_listed(
    tmp_path: Path,
) -> None:
    path = build(tmp_path / "l.jsonl")
    rewrite_last(path, v=7, compat=5)

    report = read_ledger(path, reader_version=1)
    assert [e.seq for e in report.unauditable] == [3]
    assert len(report.entries) == 4, "listed, not skipped"
    assert report.findings_of(CHAIN_BREAK) == ()


def test_a_future_version_is_interpretable_when_its_floor_allows_it(tmp_path: Path) -> None:
    """`v` is deliberately not consulted — the floor is the whole mechanism."""
    path = build(tmp_path / "l.jsonl")
    rewrite_last(path, v=99, compat=1)

    report = read_ledger(path, reader_version=1)
    assert report.entries[-1].v == 99
    assert report.entries[-1].interpretable
    assert report.unauditable == ()


def test_an_unusable_compat_floor_is_reported_and_the_entry_is_not_interpreted(
    tmp_path: Path,
) -> None:
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    entry = json.loads(rows[1])
    entry["payload"] = {"roll": 12}
    rows[1] = json.dumps(reseal(entry))
    rewrite(path, rows)

    report = read_ledger(path)
    assert MISSING_COMPAT in {f.kind for f in report.findings}
    assert not report.entries[1].interpretable


def test_the_compat_tier_does_not_depend_on_integrity(tmp_path: Path) -> None:
    """Chain verification works at any version, which is why the envelope is fixed."""
    path = build(tmp_path / "l.jsonl")
    rewrite_last(path, v=7, compat=5)

    report = read_ledger(path, reader_version=1)
    assert report.intact, "unauditable is a tier, not a defect"
    assert report.unauditable != ()


# --- Repair is explicit ------------------------------------------------------------


def test_repair_removes_only_the_torn_tail(tmp_path: Path) -> None:
    path = build(tmp_path / "l.jsonl")
    intact = path.read_text(encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq":4,"type":"rul')

    assert repair_truncated_tail(path) == 1
    assert path.read_text(encoding="utf-8") == intact
    assert read_ledger(path).intact


def test_repair_is_a_no_op_on_an_intact_ledger(tmp_path: Path) -> None:
    path = build(tmp_path / "l.jsonl")
    before = path.read_text(encoding="utf-8")
    assert repair_truncated_tail(path) == 0
    assert path.read_text(encoding="utf-8") == before


def test_repair_does_not_rewrite_a_file_it_has_nothing_to_repair(tmp_path: Path) -> None:
    """ "No torn tail" means leave the bytes alone, not rewrite them to the same content.

    A trailing blank line is not damage — the reader ignores it — but a rewrite would
    normalize it away. Touching a file nobody asked to repair is the behaviour this
    guards, and byte equality is the only assertion that sees it.
    """
    path = build(tmp_path / "l.jsonl")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    before = path.read_bytes()

    assert read_ledger(path).intact, "a blank line is not a finding"
    assert repair_truncated_tail(path) == 0
    assert path.read_bytes() == before


def test_repair_refuses_when_the_damage_is_not_at_the_tail(tmp_path: Path) -> None:
    """Truncating past a deleted middle entry would discard sound records to hide it."""
    path = build(tmp_path / "l.jsonl")
    rows = lines(path)
    rewrite(path, rows[:2] + rows[3:])
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq":9,"type":"rul')

    before = path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="damaged before its tail"):
        repair_truncated_tail(path)
    assert path.read_text(encoding="utf-8") == before


def test_a_repaired_ledger_can_be_appended_to_again(tmp_path: Path) -> None:
    """The point of repair: a crashed session must become writable, not just readable."""
    path = build(tmp_path / "l.jsonl")
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq":4,"type":"rul')
    repair_truncated_tail(path)

    ledger = Ledger.open(path, engine_version=ENGINE, catalogue_version=1, session_id="s-1")
    ledger.append("narration", v=1, payload={COMPAT: 1, "text": "and on"})
    ledger.commit()
    assert read_ledger(path).intact
