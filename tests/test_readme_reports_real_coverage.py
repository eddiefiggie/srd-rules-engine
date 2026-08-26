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

That promise was half kept. The totals were checked and the **per-kind** figures added to
the milestone row by #132 were not, so "senses, light and obscurement are 0 of 23" shipped
in the table rewritten for accuracy: 23 is a true count of five zeroed categories, and the
row named three of them. A figure can be arithmetically right and still describe something
else, which is the failure a total-only check cannot see.

So `test_every_figure_in_the_milestone_row_describes_a_real_slice` asks the harder question:
every number in that row must match a slice of the inventory that something *names*. A
figure matching no slice fails even if nobody remembered to register it — which is the
point, since forgetting is what happened.
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

# The milestone row, from which every figure is checked.
MILESTONE_ROW = re.compile(r"^\| \*\*v1\.0 — mechanics\*\* \|.*$", re.MULTILINE)

# Any "N of M" or "N/M" in that row, with or without the bold markers around either
# number. The first draft of this required a space before the separator and therefore never
# matched "15/15" at all — a guard that inspected less than it appeared to, which is the
# same defect it exists to catch.
FIGURE = re.compile(r"\*{0,2}(\d+)\*{0,2}\s*(?:of|/)\s*\*{0,2}(\d+)\*{0,2}")

#: The slices a figure in that row is allowed to describe, by the kinds it covers. `None`
#: means the whole inventory. A claim over kinds nobody lists here is a claim about nothing.
NAMED_SLICES: dict[str, tuple[str, ...] | None] = {
    "everything": None,
    "conditions": ("condition",),
    "the d20 test": ("test",),
    "senses and light": ("sense", "environment"),
}


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


def _slice(kinds: tuple[str, ...] | None) -> tuple[int, int]:
    shapes = load_inventory().shapes
    chosen = [s for s in shapes if kinds is None or s.kind in kinds]
    return sum(1 for s in chosen if s.implemented), len(chosen)


def test_every_figure_in_the_milestone_row_describes_a_real_slice() -> None:
    """The guard #132 should have come with.

    Stated as "every figure matches some slice" rather than as a list of expected numbers,
    because a list is what failed: the row's totals were checked and its per-kind figures
    were not, so a number describing five categories shipped under a label naming three.
    """
    row = MILESTONE_ROW.search(_readme())
    assert row is not None, "README.md has no 'v1.0 — mechanics' milestone row"

    allowed = {_slice(kinds) for kinds in NAMED_SLICES.values()}
    figures = [(int(a), int(b)) for a, b in FIGURE.findall(row.group(0))]
    assert figures, "the milestone row states no coverage figures at all"

    unexplained = [f for f in figures if f not in allowed]
    assert not unexplained, (
        f"{unexplained} appear in the milestone row and describe no slice of the inventory "
        f"that NAMED_SLICES names. Known slices are {sorted(allowed)}. Either the figure is "
        "wrong, or it describes something real that belongs in NAMED_SLICES — a number that "
        "is arithmetically true of some other set is the way 'senses, light and obscurement "
        "are 0 of 23' shipped."
    )


def test_the_senses_and_light_slice_is_the_one_the_row_names() -> None:
    """Pinned separately, because it is the figure that was wrong (#138). The row names
    senses and light; 23 was the total across five unrelated zeroed categories, including
    hazards, poisons and attitudes.

    Scoped to the milestone row rather than the whole file. The first version forbade
    "0 of 23" anywhere in README.md and went red on the build note *describing* the mistake
    — a guard cannot forbid the repository from discussing its own history, and one that
    does will be relaxed by whoever hits it next.
    """
    assert _slice(("sense", "environment")) == (0, 10)

    # The five-category group is no longer zeroed: Falling landed (#140), so it is 1 of 23.
    # That is the point rather than an inconvenience — the wrong figure was wrong *because*
    # it described this set instead of the one the row names, and it stays wrong now for a
    # second reason. Asserting the count keeps the slice real rather than merely absent.
    resolved, total = _slice(("sense", "environment", "hazard", "affliction", "attitude"))
    assert (resolved, total) == (2, 23)

    row = MILESTONE_ROW.search(_readme())
    assert row is not None
    assert "0 of 10" in row.group(0)
    assert "0 of 23" not in row.group(0)
    assert "1 of 23" not in row.group(0), (
        "the five-category group is still not what this row names, whatever its count"
    )
