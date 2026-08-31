#!/usr/bin/env python3
"""Fail when a Status table cites a closed issue for unbuilt work (#291, #312).

    scripts/check_status_rows.py

Exits 0 when every unbuilt claim in `docs/decisions/` **and in `README.md`** cites only open
issues, and every issue number cited anywhere in a Status table exists. Exits non-zero with
the offending claims named otherwise.

README joined in #312, where the cell that had been outside the guard was found calling p.
89's ammunition recovery "disclosed and unbuilt" over closed #301 with the recovery shipped.
The unit is the `Claim` rather than the row, because README's cells are milestone paragraphs
that cite closed issues as provenance on purpose; `status_rows` carries the reasoning.

## Why this is not a pytest test

It needs the GitHub API to mean anything, and `pytest` is hermetic here — a test that skipped
whenever the network was absent would be a guard inspecting nothing for most of its life,
which is the failure mode this repository names most often. So the parsing lives in
`status_rows.py` and is unit-tested there on fixtures, and this file is the plumbing that runs
as its own CI job.

## What it catches, and what it cannot

**Catches:** a row saying a clause is unbuilt while the issue holding it is closed. That reads
as finished work and as absent work at the same time, and `AGENTS.md` calls it worse than
unfiled. It also catches a typo'd issue number, which is otherwise a dead link nobody follows.

**Cannot catch:** the mirror — an *open* issue sitting over work that shipped. "Is this clause
built" is the judgement `tests/test_decision_records.py` deliberately declines to make, and
nothing in the repository can make it. That direction stays a process rule, and it has been
met by hand four times in one day (#277/#278, the 0039 and 0026 audit, and #263).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from status_rows import StatusRow, all_rows

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISIONS = REPO_ROOT / "docs" / "decisions"
README = REPO_ROOT / "README.md"


def issue_state(number: int) -> str | None:
    """`OPEN`, `CLOSED`, or `None` when the issue does not exist."""
    result = subprocess.run(
        ["gh", "issue", "view", str(number), "--json", "state"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return str(json.loads(result.stdout)["state"])


def main() -> int:
    rows: tuple[StatusRow, ...] = all_rows(DECISIONS, README)
    if not rows:
        print("no Status table rows found at all — the parser is reading nothing", file=sys.stderr)
        return 1

    states = {n: issue_state(n) for n in sorted({n for row in rows for n in row.issues})}

    missing = [
        f"  {row.record}: clause {row.clause[:48]!r} cites #{n}, which does not exist"
        for row in rows
        for n in row.issues
        if states[n] is None
    ]
    stale = [
        f"  {row.record}: clause {row.clause[:48]!r}\n"
        f"      says {claim.text[:70]!r}\n"
        f"      but #{n} is CLOSED"
        for row in rows
        for claim in row.claims
        if claim.outstanding
        for n in claim.issues
        if states[n] == "CLOSED"
    ]

    if missing or stale:
        if missing:
            print("Status rows citing an issue that does not exist:\n", file=sys.stderr)
            print("\n".join(missing), file=sys.stderr)
        if stale:
            print("\nStatus rows claiming unfinished work over a CLOSED issue:\n", file=sys.stderr)
            print("\n".join(stale), file=sys.stderr)
        print(
            "\nA closed issue reads as finished work rather than as absent work "
            "(AGENTS.md). Either the clause was built and the row is stale, or the work is "
            "still owed and needs an open issue to hold it.",
            file=sys.stderr,
        )
        return 1

    outstanding = sum(claim.outstanding for row in rows for claim in row.claims)
    print(
        f"  ok  {len(rows)} Status rows across {len({r.record for r in rows})} files; "
        f"{outstanding} claims say work is unfinished and every issue they cite is open"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
