"""What the ledger writer must get right, and what it must refuse.

Three properties carry the weight. The envelope and chain make an edited entry
detectable even when its checksum was recomputed. The buffer/commit split makes
"nothing escapes ahead of its record" a fact about the code rather than a rule someone
remembers. And a failed append raises, because a caller can fix a missing fact by
supplying it and cannot fix a full disk by re-declaring.
"""

from __future__ import annotations

import itertools
import json
import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from srd_rules_engine.core import digest
from srd_rules_engine.core.ledger import COMPAT, SESSION, Ledger, LedgerUnavailable

ENGINE = "08222026.2"
CATALOGUE = 1
SESSION_ID = "s-0001"


def open_ledger(path: Path, *, engine: str = ENGINE) -> Ledger:
    return Ledger.open(
        path, engine_version=engine, catalogue_version=CATALOGUE, session_id=SESSION_ID
    )


def entries(path: Path) -> list[Mapping[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def payload(compat: int = 1, **fields: object) -> dict[str, object]:
    return {COMPAT: compat, **fields}


# --- The session entry -------------------------------------------------------------


def test_a_new_ledger_opens_with_a_session_entry_at_seq_zero(tmp_path: Path) -> None:
    open_ledger(tmp_path / "ledger.jsonl")
    written = entries(tmp_path / "ledger.jsonl")
    assert len(written) == 1
    assert written[0]["seq"] == 0
    assert written[0]["type"] == SESSION


def test_the_first_entry_has_no_prev(tmp_path: Path) -> None:
    """Absent, not null — there is no predecessor to name."""
    open_ledger(tmp_path / "ledger.jsonl")
    assert "prev" not in entries(tmp_path / "ledger.jsonl")[0]


def test_the_session_entry_names_the_versions_it_governs(tmp_path: Path) -> None:
    open_ledger(tmp_path / "ledger.jsonl")
    session = entries(tmp_path / "ledger.jsonl")[0]["payload"]
    assert isinstance(session, dict)
    assert session["engine_version"] == ENGINE
    assert session["catalogue_version"] == CATALOGUE
    assert session["session_id"] == SESSION_ID


def test_reopening_under_the_same_engine_version_continues_the_session(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    open_ledger(path).append("ruling", v=1, payload=payload())
    open_ledger(path)
    assert [e["type"] for e in entries(path)] == [SESSION]


def test_reopening_under_a_different_engine_version_starts_a_new_session(tmp_path: Path) -> None:
    """A session may not span engine versions, so the governing version stays answerable."""
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload())
    ledger.commit()

    open_ledger(path, engine="08232026.1")
    written = entries(path)
    assert [e["type"] for e in written] == [SESSION, "ruling", SESSION]
    assert written[2]["seq"] == 2


# --- The chain ---------------------------------------------------------------------


def test_each_entry_chains_to_its_predecessor(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("declaration", v=1, payload=payload(intent="climb"))
    ledger.append("ruling", v=1, payload=payload(outcome="success"))
    ledger.commit()

    written = entries(path)
    assert [e["seq"] for e in written] == [0, 1, 2]
    for previous, current in itertools.pairwise(written):
        assert current["prev"] == previous["sum"]


def test_the_sum_covers_the_entry_without_itself(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload(roll=17))
    ledger.commit()

    entry = dict(entries(path)[1])
    recorded = entry.pop("sum")
    assert recorded == digest(entry)


def test_an_edited_payload_fails_its_own_checksum(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload(roll=17))
    ledger.commit()

    entry = dict(entries(path)[1])
    entry["payload"] = payload(roll=20)
    recorded = entry.pop("sum")
    assert recorded != digest(entry)


def test_an_edit_with_a_recomputed_checksum_still_breaks_the_chain(tmp_path: Path) -> None:
    """The corruption a checksum alone cannot catch, and the reason `prev` exists."""
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload(roll=17))
    ledger.append("narration", v=1, payload=payload(text="the lock opens"))
    ledger.commit()

    written = [dict(e) for e in entries(path)]
    tampered = dict(written[1])
    tampered["payload"] = payload(roll=20)
    del tampered["sum"]
    tampered["sum"] = digest(tampered)

    assert tampered["sum"] == digest({k: v for k, v in tampered.items() if k != "sum"})
    assert written[2]["prev"] != tampered["sum"], "the successor still names the original"


def test_the_chain_continues_across_a_reopen(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    first = open_ledger(path)
    first.append("ruling", v=1, payload=payload(roll=9))
    first.commit()

    second = open_ledger(path)
    second.append("narration", v=1, payload=payload(text="it holds"))
    second.commit()

    written = entries(path)
    assert [e["seq"] for e in written] == [0, 1, 2]
    assert written[2]["prev"] == written[1]["sum"]


# --- Durability --------------------------------------------------------------------


def test_a_buffered_entry_is_not_durable_until_commit(tmp_path: Path) -> None:
    """The escape boundary is the point of the split — an uncommitted outcome is not one."""
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload())
    assert ledger.pending == 1
    assert [e["type"] for e in entries(path)] == [SESSION]

    ledger.commit()
    assert ledger.pending == 0
    assert [e["type"] for e in entries(path)] == [SESSION, "ruling"]


def test_several_entries_reach_storage_in_one_write(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    for index in range(4):
        ledger.append("declaration", v=1, payload=payload(index=index))
    assert [e["type"] for e in entries(path)] == [SESSION]

    ledger.commit()
    assert [e["type"] for e in entries(path)] == [SESSION] + ["declaration"] * 4


def test_the_escape_boundary_commits_on_the_way_out(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    with ledger.escape_boundary() as pending:
        pending.append("declaration", v=1, payload=payload())
        pending.append("ruling", v=1, payload=payload())
        assert [e["type"] for e in entries(path)] == [SESSION]
    assert [e["type"] for e in entries(path)] == [SESSION, "declaration", "ruling"]


def test_leaving_the_escape_boundary_by_exception_discards_the_buffer(tmp_path: Path) -> None:
    """Nobody saw the outcome, so nothing was lost — on restart the agent re-declares."""
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    with pytest.raises(RuntimeError), ledger.escape_boundary() as pending:
        pending.append("ruling", v=1, payload=payload())
        raise RuntimeError("crash before the outcome escaped")

    assert [e["type"] for e in entries(path)] == [SESSION]
    assert ledger.pending == 0


def test_commit_synchronises_once_regardless_of_how_many_entries_buffered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One `fsync` per adjudication, not per entry — that is the durability contract.

    Nothing else in this file would notice the sync disappearing, and a ledger that
    returns before its record is durable is the defect the whole design exists to
    prevent.
    """
    synced: list[int] = []
    real_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        synced.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", recording_fsync)

    ledger = open_ledger(tmp_path / "ledger.jsonl")
    synced.clear()  # the session entry's own commit already happened

    for index in range(5):
        ledger.append("declaration", v=1, payload=payload(index=index))
    assert synced == [], "buffering must not sync"

    ledger.commit()
    assert len(synced) == 1, "five entries, one synchronising write"


def test_committing_an_empty_buffer_does_not_synchronise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = open_ledger(tmp_path / "ledger.jsonl")
    synced: list[int] = []

    def recording_fsync(fd: int) -> None:
        synced.append(fd)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    ledger.commit()
    assert synced == []


def test_committing_nothing_is_not_an_error(tmp_path: Path) -> None:
    ledger = open_ledger(tmp_path / "ledger.jsonl")
    ledger.commit()
    assert len(entries(tmp_path / "ledger.jsonl")) == 1


# --- Failure is not a rules outcome ------------------------------------------------


def test_an_unwritable_destination_raises_rather_than_returning_a_status(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload())
    path.chmod(0o400)
    try:
        with pytest.raises(LedgerUnavailable, match="could not append"):
            ledger.commit()
    finally:
        path.chmod(0o600)


def test_an_unreadable_ledger_raises_on_open(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    open_ledger(path)
    path.chmod(0o000)
    try:
        with pytest.raises(LedgerUnavailable, match="could not read"):
            open_ledger(path)
    finally:
        path.chmod(0o600)


def test_a_torn_tail_refuses_the_writer_and_points_at_the_reader(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    open_ledger(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq":1,"type":"rul')

    with pytest.raises(LedgerUnavailable, match="partial entry"):
        open_ledger(path)


# --- What the envelope refuses -----------------------------------------------------


def test_a_payload_without_compat_is_refused_at_write_time(tmp_path: Path) -> None:
    ledger = open_ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(LedgerUnavailable, match="carries no 'compat' key"):
        ledger.append("ruling", v=1, payload={"roll": 17})


def test_a_compat_floor_above_its_own_version_is_refused(tmp_path: Path) -> None:
    """No reader of the payload's own version could interpret it, including this one."""
    ledger = open_ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(LedgerUnavailable, match="no coherent meaning"):
        ledger.append("ruling", v=2, payload=payload(compat=3))


def test_a_non_integer_compat_is_refused(tmp_path: Path) -> None:
    ledger = open_ledger(tmp_path / "ledger.jsonl")
    for bad in ("1", True, None):
        with pytest.raises(LedgerUnavailable, match="must be an integer"):
            ledger.append("ruling", v=1, payload={COMPAT: bad})


def test_an_unknown_entry_type_is_refused(tmp_path: Path) -> None:
    ledger = open_ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(LedgerUnavailable, match="not a ledger entry type"):
        ledger.append("outcome", v=1, payload=payload())


def test_a_float_in_a_payload_is_refused_before_it_reaches_the_file(tmp_path: Path) -> None:
    """The canonical form's refusal reaches through the writer — R25's no-float rule."""
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    with pytest.raises(LedgerUnavailable, match="no canonical form"):
        ledger.append("ruling", v=1, payload=payload(damage=4.5))
    assert [e["type"] for e in entries(path)] == [SESSION]


def test_the_written_line_is_the_canonical_form(tmp_path: Path) -> None:
    """The file is canonical, so a reader recomputes rather than re-serializing."""
    path = tmp_path / "ledger.jsonl"
    ledger = open_ledger(path)
    ledger.append("ruling", v=1, payload=payload(b=2, a=1, note="a spaced value"))
    ledger.commit()

    line = path.read_text(encoding="utf-8").splitlines()[1]
    assert line.index('"a"') < line.index('"b"'), "keys are sorted"
    # The only spaces in the line are the ones inside the quoted string value.
    assert line.count(" ") == "a spaced value".count(" ")
    assert ", " not in line and ": " not in line


def test_the_ledger_is_created_with_its_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "campaigns" / "one" / "ledger.jsonl"
    open_ledger(path)
    assert path.exists()
    assert os.access(path, os.R_OK)
