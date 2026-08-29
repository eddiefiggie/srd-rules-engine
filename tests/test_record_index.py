"""The README lists every decision record, and the list is generated (#282).

A hand-written list stopped at 0022 and read as complete for nineteen records. It was
introduced with a colon and no qualifier, so a reader looking for the record covering an area
— which `AGENTS.md` **instructs** them to do before reopening a question in it — did not find
0026 on terrain or 0039 on equipment and concluded none existed. That is the re-litigation the
whole corpus exists to prevent, and the twenty-two entries that *were* listed made the list
look maintained.

## Why generated rather than curated

#282 offered three options and framed the choice as honesty against length. The framing had a
false premise: the hand-written list was **64 lines for 22 records**, because each entry
restated the record's title as a gloss and wrapped over two or three lines. One generated line
per record covers all 45 in 45 lines, so **completeness is shorter than the partial list it
replaced**.

The restatement was also a second place for the same claim to drift, which is the shape #291
had just finished fixing in the Status tables.

## Hermetic

This reads the tree only. `scripts/render_record_index.py --check` is the same assertion for a
CI job, and needs no network — unlike #291's, which does.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from render_record_index import (  # noqa: E402
    DECISIONS,
    END,
    RECORD,
    START,
    entry,
    readme_index,
    render,
)

README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_the_readme_carries_the_generated_index() -> None:
    """The completeness guard. A record added without regenerating goes red here."""
    assert readme_index(README) == render(), (
        "README.md's record index is out of date — run scripts/render_record_index.py. A "
        "record that exists and is not listed is one a reader concludes does not exist, "
        "which is how the hand-written list came to omit nineteen."
    )


def test_every_record_on_disk_appears() -> None:
    """Asserted against the directory rather than against `render()`, so a generator that
    silently skipped records could not satisfy both this and the test above."""
    on_disk = sorted(p.name for p in DECISIONS.iterdir() if RECORD.match(p.name))
    listed = readme_index(README) or ""
    missing = [name for name in on_disk if f"](docs/decisions/{name})" not in listed]
    assert not missing, f"records on disk and absent from the README: {missing}"
    assert len(on_disk) >= 45, f"only {len(on_disk)} records matched; the glob reads nothing"


def test_the_markers_are_present_and_ordered() -> None:
    """Without them the block cannot be located, and `--check` would report a missing index
    rather than a stale one."""
    assert README.count(START) == 1
    assert README.count(END) == 1
    assert README.index(START) < README.index(END)


def test_an_entry_carries_the_records_own_title() -> None:
    """The title is the record's own claim, so the index cannot paraphrase it into drift —
    which is what the hand-written glosses were."""
    path = DECISIONS / "0041-an-item-that-leaves-a-creature-is-an-object-somewhere-unstated.md"
    line = entry(path)
    assert (
        "0041 — An item that leaves a creature is an object, and where it lands is unstated" in line
    )
    assert f"](docs/decisions/{path.name})" in line


def test_an_entry_names_what_the_record_settles() -> None:
    """`AGENTS.md` requires a gate to name the issue it closes, so the index can read it rather
    than a maintainer restating it."""
    assert "/issues/4" in entry(DECISIONS / "0001-agent-seam.md")
