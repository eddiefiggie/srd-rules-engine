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

from status_rows import (  # noqa: E402
    ISSUE_REF,
    README_HEADING,
    Claim,
    all_rows,
    issues_in,
    readme_rows,
    rows_in,
    sentences,
    status_section,
)

DECISIONS = REPO_ROOT / "docs" / "decisions"
README = REPO_ROOT / "README.md"

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
    rows = all_rows(DECISIONS, README)
    assert len(rows) > 100, f"only {len(rows)} Status rows parsed across the whole corpus"
    assert len({r.record for r in rows}) > 20
    assert any(r.unbuilt for r in rows), "no record claims any unbuilt work, which is unlikely"


def test_every_status_row_that_cites_an_issue_cites_a_plausible_one() -> None:
    """The hermetic half of the script's existence check: a number, not a fragment. Whether it
    is *open* needs the network and is the CI job's question."""
    for row in all_rows(DECISIONS, README):
        for number in row.issues:
            assert 0 < number < 10_000, f"{row.record}: #{number} is not a plausible issue"


# --- README's table, which is a different shape (#312) -----------------------------------


README_STATUS = """## Status

Some prose before the table.

| Milestone | Where it stands |
|---|---|
| **v1.0 — mechanics** | **9 of 9.** p. 89-90's nine are complete, and the last two \
waited on [#271](/issues/271). p. 89's recovery is unbuilt ([#301](/issues/301)). |
| **SRD fidelity** | **No open gap.** An unbuilt one now carries an issue of its own \
([#126](/issues/126)). |

## Effect-shape coverage

| **not a status row** | **Decided, not built.** [#9](https://github.com/x/y/issues/9) |
"""


def test_readme_splits_a_cell_into_one_claim_per_sentence() -> None:
    """The reason README could not simply be handed to `rows_in`. Its cells are milestone
    paragraphs that cite closed issues as provenance on purpose, so the row is the wrong unit
    and the whole cell would be condemned by its own history."""
    (mechanics, _) = readme_rows(README_STATUS)
    assert len(mechanics.claims) == 3, [c.text for c in mechanics.claims]
    unbuilt = [c for c in mechanics.claims if c.unbuilt]
    assert [c.issues for c in unbuilt] == [(301,)], "only the recovery sentence is a claim"
    assert 271 in mechanics.issues, "the row still cites it; the claim is what narrows"


def test_a_page_reference_is_not_a_sentence_boundary() -> None:
    """`p. 89` is the hazard in this corpus specifically: every citation of the document is a
    page reference, so a splitter that does not know the abbreviation cuts a claim in half and
    separates an assertion from the issue that holds it."""
    assert sentences("p. 89's recovery is unbuilt. Senses are 7 of 10.") == (
        "p. 89's recovery is unbuilt.",
        "Senses are 7 of 10.",
    )


def test_a_full_stop_inside_markdown_emphasis_still_ends_a_sentence() -> None:
    """ "**9 of 9.**" is the ordinary shape of these cells, not an unusual one. Missing the
    boundary would merge the headline into the sentence after it and widen every claim."""
    assert sentences("**9 of 9.** p. 89-90's nine are complete.") == (
        "**9 of 9.**",
        "p. 89-90's nine are complete.",
    )


def test_attributive_unbuilt_is_not_a_claim() -> None:
    """0027's narrative-append false positive in new clothes, and it was live: README's M0 row
    says "an **unbuilt** one now carries an issue of its own ([#126])" and cites #126 correctly,
    because #126 is the closed issue that instituted the practice. A predicate ends its clause;
    an attributive is followed by the noun it modifies."""
    (_, fidelity) = readme_rows(README_STATUS)
    assert not fidelity.unbuilt, [c.text for c in fidelity.claims if c.unbuilt]
    assert 126 in fidelity.issues, "still cited, so the existence half still reads it"


def test_predicative_unbuilt_is_a_claim_in_every_punctuation_it_ends_on() -> None:
    """The other direction. A lookahead tuned until the nuisance stopped would be a guard
    inspecting nothing, which is the failure this repository names most often."""
    for text in (
        "Rituals remain unbuilt",
        "**Decided, unbuilt.**",
        "still unbuilt;",
        "unbuilt ([#1](i))",
    ):
        assert Claim(text).unbuilt, text
    for text in ("nothing tracks its unbuilt clauses", "an unbuilt one", "unbuilt work is filed"):
        assert not Claim(text).unbuilt, text


def test_a_record_row_is_one_claim_however_many_sentences_it_has() -> None:
    """**The asymmetry is load-bearing.** Making sentences the unit everywhere blinds the guard
    on the most common record row in the corpus: `**Decided, not built.** [#264](…)` puts a full
    stop between the phrase and the issue, so a sentence-scoped record guard reads one claim
    saying "not built" and citing nothing, and another citing #264 and saying nothing about
    building. Three of the seven unbuilt rows had that shape when this was measured."""
    record = """## Status of implementation

| Clause | State |
|---|---|
| 5 — improvised is a use | **Decided, not built.** [#264](https://github.com/x/y/issues/264) |
"""
    (row,) = rows_in("0040.md", record)
    assert len(row.claims) == 1, "a record row is one claim, whatever its punctuation"
    assert row.claims[0].unbuilt and row.claims[0].issues == (264,)
    assert len(sentences(row.state)) == 2, "and it really would have split — this is the risk"


def test_the_readme_header_cell_is_not_a_row() -> None:
    """ "Where it stands" is not "State", so the record's header test does not reach it."""
    assert [r.clause for r in readme_rows(README_STATUS)] == [
        "**v1.0 — mechanics**",
        "**SRD fidelity**",
    ]


def test_only_the_readme_status_section_is_read() -> None:
    """A table under `## Effect-shape coverage` is a different claim, and README carries one."""
    assert all(r.clause != "**not a status row**" for r in readme_rows(README_STATUS))


def test_the_status_heading_does_not_match_the_records_longer_one() -> None:
    """`## Status` is a prefix of `## Status of implementation`. A substring search would make
    `readme_rows` read a record's table and report it under README's name."""
    record = """## Status of implementation

| Clause | State |
|---|---|
| 1 — x | **Decided, not built.** [#1](https://github.com/x/y/issues/1) |
"""
    assert readme_rows(record) == ()
    assert status_section(record, README_HEADING) == ""


# --- against the corpus, not a fixture --------------------------------------------------


def test_the_parser_reads_the_real_readme() -> None:
    """The control for README, for the reason the record corpus has one: every fixture test
    above passes against a parser that silently matches nothing in the real file."""
    rows = readme_rows(README.read_text(encoding="utf-8"))
    assert len(rows) >= 5, f"only {len(rows)} milestone rows parsed"
    assert any(len(r.claims) > 3 for r in rows), "no cell is a paragraph, which is unlikely"
    assert all(r.record == "README.md" for r in rows)


def test_all_rows_reads_readme_as_well_as_the_records() -> None:
    """`all_rows` takes README as a required argument precisely so this cannot regress by
    someone dropping it at a call site — the blind spot #312 closed was one file's absence."""
    rows = all_rows(DECISIONS, README)
    assert any(r.record == "README.md" for r in rows)
    assert any(r.record.startswith("0040") for r in rows)


# --- both citation forms (#312 follow-up) -------------------------------------------------


def test_a_bare_issue_reference_is_read() -> None:
    """The form the guard could not see, and the one that was hiding a live defect: 0027
    clause 8 said "Not built. Part of #140" over closed #140 with both its shapes still
    unimplemented. Seven rows across five records cite an issue this way."""
    assert issues_in("Not built. Part of #140") == (140,)
    assert Claim("Not built. Part of #140").issues == (140,)


def test_a_linked_issue_is_counted_once_not_twice() -> None:
    """A Markdown link matches both alternatives — its href and the `#301` in its label. The
    dedupe is not tidiness: without it one citation is reported, and counted, twice."""
    assert issues_in("[#301](https://github.com/x/y/issues/301)") == (301,)


def test_both_forms_together_keep_citation_order() -> None:
    assert issues_in("bare #7, then [#9](https://github.com/x/y/issues/9)") == (7, 9)


def test_a_hex_colour_is_not_an_issue_reference() -> None:
    """`\\b` after the digits is what stops `#1a2b3c` reading as issue 1: the boundary fails
    between two word characters, so a reference has to end where its number ends."""
    assert issues_in("the swatch is #1a2b3c") == ()
    assert issues_in("see #1a") == ()


def test_every_bare_reference_in_the_corpus_is_a_plausible_issue() -> None:
    """The corpus control for the new form. A pattern that matched nothing bare would pass
    every fixture above and leave the hole exactly where it was."""
    rows = all_rows(DECISIONS, README)
    linked = {n for r in rows for n in ISSUE_REF.findall(r.state) for n in (n[0],) if n}
    assert linked, "no linked references at all, which means the parser is reading nothing"
    bare_only = {n for r in rows for n in r.issues if str(n) not in linked and f"#{n}" in r.state}
    assert bare_only, "no row cites an issue bare, which was true of neither corpus"
    for number in bare_only:
        assert 0 < number < 10_000, f"#{number} is not a plausible issue"
