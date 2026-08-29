"""Parse the **Status of implementation** tables in `docs/decisions/` (#291).

The pure half of `check_status_rows.py`, separated for the reason
`srd_rules_engine.build_stamp` is separated from `check_build_stamp_advanced.py`: the
plumbing needs a network call and answers nothing without one, while the parsing is where the
mistakes actually are — and the mistakes are provable on fixtures.

**Not in the package**, unlike `build_stamp`. This reads `docs/`, and a documentation parser
shipped to library users is noise in a product that is a rules engine.

## Why it keys on table rows

`AGENTS.md` requires every record to carry a Status section, and a naive scan for "not built"
inside one produces a permanent false positive. 0027's section ends with a dated append:

    _Updated 2026-08-25 as #170, Falling and #124 landed. This record shipped saying
    "Decided, not built", which was true for about two hours._

That is narrative *about* history, and it correctly cites closed issues because the work
landed. A guard keyed on the phrase would flag it forever, and loosening the phrase to
suppress it would blind the guard to real rows. So only `|`-delimited table rows are read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

HEADING = "## Status of implementation"

#: `NNNN-slug.md`. `README.md` is the index and is not a record.
RECORD = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")

#: The next top-level section, or the end of the file.
NEXT_SECTION = re.compile(r"^## ", re.MULTILINE)

ISSUE_REF = re.compile(r"/issues/(\d+)")

#: What a state cell says when the clause is decided and nobody has built it. Matched
#: case-insensitively against the cell alone, so "**Built, and the clause gained a finding.**"
#: cannot trip it by containing the word "built".
UNBUILT = re.compile(r"not built", re.IGNORECASE)


@dataclass(frozen=True)
class StatusRow:
    """One row of one record's Status table."""

    record: str
    clause: str
    state: str
    issues: tuple[int, ...]

    @property
    def unbuilt(self) -> bool:
        """Whether this row claims the clause is decided and unbuilt."""
        return bool(UNBUILT.search(self.state))


def status_section(text: str) -> str:
    """The Status of implementation section of one record, or the empty string."""
    start = text.find(HEADING)
    if start == -1:
        return ""
    body = text[start + len(HEADING) :]
    end = NEXT_SECTION.search(body)
    return body[: end.start()] if end else body


def rows_in(record: str, text: str) -> tuple[StatusRow, ...]:
    """Every table row in that record's Status section.

    The header and the `|---|---|` separator are skipped, and so is every line that is not a
    table row — which is the whole point (see the module docstring).
    """
    found: list[StatusRow] = []
    for line in status_section(text).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 2:
            continue
        clause, state = cells
        if state.lower() == "state" or set(state) <= set("- :"):
            continue
        found.append(
            StatusRow(
                record=record,
                clause=clause,
                state=state,
                issues=tuple(int(n) for n in ISSUE_REF.findall(state)),
            )
        )
    return tuple(found)


def all_rows(decisions: Path) -> tuple[StatusRow, ...]:
    """Every Status table row across every record, in record order."""
    found: list[StatusRow] = []
    for path in sorted(p for p in decisions.iterdir() if RECORD.match(p.name)):
        found.extend(rows_in(path.name, path.read_text(encoding="utf-8")))
    return tuple(found)
