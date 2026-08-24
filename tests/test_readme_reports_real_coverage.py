"""The README's coverage figures must be the inventory's, not a remembered number.

`tests/test_build_stamp.py` was the only test reading README.md, and it checks one
line. Everything else drifted: the Status section said "Nothing built yet" over
fourteen implemented units, and the coverage claim said 17 of 215 where the
inventory said 76 of 211 — wrong by a factor of four, in the one sentence that
makes "full SRD 5.2 coverage is the definition of done" falsifiable (R17).

A number a reader takes at face value is worse wrong than absent, and prose is
where this repository has already been wrong for eight builds running. So these
figures are derived from the inventory rather than trusted as typed.

Prose the README states in words rather than digits is still on the author. This
guards the counts, which are the part that rots on every merge.
"""

from __future__ import annotations

import re
from pathlib import Path

from srd_rules_engine.core.inventory import Inventory, load_inventory

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

# "**76 of 211 shapes resolve today.** The other 135 are listed, not omitted"
COVERAGE_CLAIM = re.compile(
    r"\*\*(?P<resolved>\d+) of (?P<total>\d+) shapes resolve today\.\*\*\s+"
    r"The other (?P<remaining>\d+) are listed, not omitted"
)

# "**76 of 211 effect shapes.**" — the same figure in the milestone table
MILESTONE_CLAIM = re.compile(r"\*\*(?P<resolved>\d+) of (?P<total>\d+) effect shapes\.\*\*")

SPELLED = {19: "Nineteen", 20: "Twenty", 21: "Twenty-one", 22: "Twenty-two"}


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_the_coverage_sentence_publishes_the_inventorys_own_figures() -> None:
    inventory: Inventory = load_inventory()
    match = COVERAGE_CLAIM.search(_readme())
    assert match is not None, (
        "README.md has no 'N of M shapes resolve today. The other K are listed' "
        "sentence. Restore it rather than relaxing this test — it is what makes "
        "R17's definition of done falsifiable to a reader."
    )

    published = (
        int(match.group("resolved")),
        int(match.group("total")),
        int(match.group("remaining")),
    )
    actual = (
        len(inventory.implemented),
        len(inventory.shapes),
        len(inventory.unimplemented),
    )
    assert published == actual, (
        f"README.md publishes {published[0]} of {published[1]} shapes resolving with "
        f"{published[2]} remaining; the inventory says {actual[0]} of {actual[1]} with "
        f"{actual[2]} remaining. Update the README — the number a reader meets first "
        f"is the one that has to be true."
    )


def test_the_milestone_table_agrees_with_the_coverage_sentence() -> None:
    """Two places quote the figure, so both are checked. One stale copy reads as current."""
    inventory = load_inventory()
    match = MILESTONE_CLAIM.search(_readme())
    assert match is not None, (
        "README.md's v1.0 milestone row no longer states 'N of M effect shapes'. "
        "It is the first coverage number a reader meets; keep it."
    )
    published = (int(match.group("resolved")), int(match.group("total")))
    actual = (len(inventory.implemented), len(inventory.shapes))
    assert published == actual, (
        f"README.md's milestone table says {published[0]} of {published[1]} effect "
        f"shapes; the inventory says {actual[0]} of {actual[1]}."
    )


def test_the_vocabulary_count_is_the_inventorys() -> None:
    """0013 moves entries between shape and vocabulary, so this count moves with it."""
    expected = len(load_inventory().vocabulary)
    spelled = SPELLED.get(expected)
    assert spelled is not None, (
        f"The inventory records {expected} vocabulary entries and this test has no "
        f"spelling for it. Add one to SPELLED rather than dropping the check."
    )
    claim = (
        f"{spelled} entries are\nrecorded as vocabulary with a stated reason rather than dropped."
    )
    assert claim in _readme(), (
        f"README.md does not say '{spelled} entries are recorded as vocabulary'. "
        f"The inventory holds {expected}; a count that trails a normalisation pass "
        f"understates what was deliberately excluded."
    )
