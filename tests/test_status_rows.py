"""The Status-table parser behind `scripts/check_status_rows.py` (#291).

`tests/test_decision_records.py` guards that every record *carries* a Status section and says
outright that it "checks presence, not truth". #291 is the half of the truth a machine can
hold: **a row claiming a clause is unbuilt while the issue holding it is closed.** That reads
as finished work and as absent work at the same time, and `AGENTS.md` calls it worse than
unfiled.

The network half lives in the script and runs as its own CI job. What is tested here is the
parsing, because that is where the mistakes are — and one of them is already known.

## The false positive this exists to avoid

0027's Status section ends with a dated append narrating its own history:

    _Updated 2026-08-25 as #170, Falling and #124 landed. This record shipped saying
    "Decided, not built", which was true for about two hours._

It contains the phrase and cites closed issues, and it is **correct** — the work landed. A
guard keyed on the phrase would flag it forever; loosening the phrase to suppress it would
blind the guard to real rows. Keying on `|`-delimited table rows is what separates them, and
both directions are asserted below.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The parser is not in the package: it reads `docs/`, and a documentation parser shipped to
# library users is noise in a product that is a rules engine (R33's spirit). So it is imported
# the way the script imports it.
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from status_rows import all_rows, rows_in, status_section  # noqa: E402

DECISIONS = REPO_ROOT / "docs" / "decisions"

#: 0027's real shape, reduced to the two lines that matter.
NARRATING_RECORD = """## Status of implementation

| Clause | State |
|---|---|
| 1 — something | **Built.** [#170](https://github.com/x/y/issues/170) |

_Updated 2026-08-25 as [#170](https://github.com/x/y/issues/170) landed. This record shipped
saying "Decided, not built", which was true for about two hours._
"""

TABLE_RECORD = """## Status of implementation

| Clause | State |
|---|---|
| 1 — built one | **Built.** [#1](https://github.com/x/y/issues/1) |
| 2 — unbuilt one | **Decided, not built.** [#2](https://github.com/x/y/issues/2) |

## Something else

| 9 — not in the status section | **Decided, not built.** [#9](https://github.com/x/y/issues/9) |
"""


def test_a_narrative_append_is_not_a_row() -> None:
    """The permanent false positive, asserted so a future parser cannot reintroduce it."""
    rows = rows_in("0027.md", NARRATING_RECORD)
    assert [r.clause for r in rows] == ["1 — something"]
    assert not any(r.unbuilt for r in rows), "the append says the phrase and is not a row"


def test_a_table_row_saying_not_built_is_caught_with_its_issues() -> None:
    """The other direction. A guard that only avoided the false positive would be inspecting
    nothing, which is the failure this repository names most often."""
    rows = rows_in("t.md", TABLE_RECORD)
    unbuilt = [r for r in rows if r.unbuilt]
    assert [r.clause for r in unbuilt] == ["2 — unbuilt one"]
    assert unbuilt[0].issues == (2,)


def test_the_header_and_separator_are_not_rows() -> None:
    assert [r.clause for r in rows_in("t.md", TABLE_RECORD)] == ["1 — built one", "2 — unbuilt one"]


def test_only_the_status_section_is_read() -> None:
    """A table under a later heading is a different claim, and 0031 and 0038 both carry one."""
    assert all(r.clause != "9 — not in the status section" for r in rows_in("t.md", TABLE_RECORD))


def test_built_is_not_read_as_not_built() -> None:
    """ "**Built, and the clause gained a finding.**" contains the word and is not the phrase —
    the match is on the state cell alone, so a row cannot trip it by mentioning building."""
    record = """## Status of implementation

| Clause | State |
|---|---|
| 1 — x | **Built, and the clause gained a finding.** [#1](https://github.com/x/y/issues/1) |
"""
    assert not any(r.unbuilt for r in rows_in("t.md", record))


def test_a_record_with_no_status_section_yields_nothing() -> None:
    assert status_section("# 0001\n\n## Context\n\nprose\n") == ""
    assert rows_in("t.md", "# 0001\n\n## Context\n\nprose\n") == ()


# --- against the corpus, not a fixture --------------------------------------------------


def test_the_parser_reads_the_real_records() -> None:
    """A parser that silently matched nothing would pass every test above. This is the control
    that says it is reading the corpus — the shape `test_decision_records.py` uses for its own
    glob, and for the same reason."""
    rows = all_rows(DECISIONS)
    assert len(rows) > 100, f"only {len(rows)} Status rows parsed across the whole corpus"
    assert len({r.record for r in rows}) > 20
    assert any(r.unbuilt for r in rows), "no record claims any unbuilt work, which is unlikely"


def test_every_status_row_that_cites_an_issue_cites_a_plausible_one() -> None:
    """The hermetic half of the script's existence check: a number, not a fragment. Whether it
    is *open* needs the network and is the CI job's question."""
    for row in all_rows(DECISIONS):
        for number in row.issues:
            assert 0 < number < 10_000, f"{row.record}: #{number} is not a plausible issue"
