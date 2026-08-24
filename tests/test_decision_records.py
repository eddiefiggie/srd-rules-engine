"""Every decision record must say whether the thing it decided is built.

`AGENTS.md` tells an agent to read the relevant record before reopening a question in the
area it covers, which makes `docs/decisions/` load-bearing in a way most projects' ADRs are
not. A reader arriving at a record needs two things from it: the decision, and whether the
decision exists yet in the tree. The first is what the record is for. The second lives in
**Status of implementation**, and #126 found it failing in all three possible ways at once —
twelve records claiming "None" over work that had shipped, two carrying no section at all,
and 0023's six specified-but-unbuilt clauses held by no open issue after its gate closed.

The first two were repaired by #127 and #128. This guard holds the line they restored: a
record without the section is a record whose reader cannot tell "shipped" from "nobody wrote
it down", and that ambiguity is what made the drift invisible for as long as it lasted.

**It checks presence, not truth**, and the distinction is the whole reason the rest of #126
is a process rule rather than more machinery. A section reading "None" over a finished
subsystem passes here. Catching *that* would mean every clause naming the symbol it landed
as, which is the kind of scaffolding that decays faster than the prose it guards — and a
clause like 0023's "an obligation is derived from state and never declared" has no single
symbol to point at. So the accuracy half is `AGENTS.md`'s filing rule, enforced by review,
and this file covers the half a machine can hold without rotting.

The record count is asserted too. A glob that silently stops matching is a guard inspecting
nothing, which looks exactly like a guard that passes.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISIONS = REPO_ROOT / "docs" / "decisions"

#: `NNNN-slug.md`. `README.md` is the index and is not a record.
RECORD = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")

HEADING = "## Status of implementation"

#: The next top-level section, or the end of the file — whichever bounds the status prose.
NEXT_SECTION = re.compile(r"^## ", re.MULTILINE)

#: 23 records exist as of #126. The floor guards the glob rather than the number: records are
#: only ever added, so a count below this means the pattern stopped matching, not that a
#: decision was deleted.
KNOWN_RECORDS = 23


def _records() -> list[Path]:
    return sorted(p for p in DECISIONS.iterdir() if RECORD.match(p.name))


def test_the_record_glob_still_matches_records() -> None:
    found = _records()
    assert len(found) >= KNOWN_RECORDS, (
        f"{len(found)} records matched {RECORD.pattern!r}, below the {KNOWN_RECORDS} known to "
        "exist. Records are only added, so this is the glob failing rather than the corpus "
        "shrinking — and a guard over an empty set passes."
    )


def test_every_decision_record_states_whether_it_is_built() -> None:
    missing = [p.name for p in _records() if HEADING not in p.read_text(encoding="utf-8")]
    assert not missing, (
        f"decision records with no '{HEADING}' section: {missing}. A reader cannot tell "
        "'shipped' from 'nobody wrote one', which is how twelve records came to claim "
        "nothing was built over an engine that had shipped (#126)."
    )


def test_no_status_section_is_left_empty() -> None:
    empty = []
    for path in _records():
        text = path.read_text(encoding="utf-8")
        start = text.find(HEADING)
        if start == -1:
            continue  # The test above owns this failure.
        body = text[start + len(HEADING) :]
        end = NEXT_SECTION.search(body)
        if not (body[: end.start()] if end else body).strip():
            empty.append(path.name)
    assert not empty, (
        f"decision records whose '{HEADING}' section is empty: {empty}. A heading with "
        "nothing under it states less than no heading at all — it looks answered."
    )
