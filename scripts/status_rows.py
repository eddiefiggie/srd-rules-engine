"""Parse the **Status of implementation** tables in `docs/decisions/`, and README's (#291, #312).

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

## Why README needs a smaller unit than a record does (#312)

README's `## Status` table is the most-read status claim in the repository and was outside
this parser until #312, on the reasoning that it is an index rather than a record. The blind
spot had an occupant: the **v1.0 — mechanics** cell called p. 89's ammunition recovery
"disclosed and unbuilt" over closed #301 while the recovery had shipped, and named #273 and
#289 as remaining blockers in the same breath as calling their properties complete.

Pointing the existing guard at it does not work, because the two tables are not the same
shape. A record's row is **one clause and one state**, so "does this row cite a closed issue"
is a fair stand-in for "does this claim cite a closed issue". README's cells are **milestone
paragraphs**, and they mix provenance with outstanding work by design — the mechanics cell
legitimately cites #14, #229, #230 and #271 as closed history. A row-scoped guard fails on
every one of them.

So the unit is the `Claim`: a record's row is one claim, and a README cell's claim is the
sentence.

**The asymmetry is load-bearing, not tidiness left undone.** Making sentences the unit
everywhere blinds the guard on the *most common* record row in the corpus. `**Decided, not
built.** [#264](…)` puts a full stop between the phrase and the issue, so the sentence holding
"not built" cites nothing and the sentence citing #264 says nothing about building. Three of
the seven unbuilt rows had that shape when this was measured, and
`test_a_record_row_is_one_claim_however_many_sentences_it_has` is what stops the two units
being unified later by someone who reasonably assumes they should be.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: A record's Status heading, and README's. `## Status` is a prefix of the other, which is why
#: the match below is anchored to a whole line rather than done with `str.find`.
RECORD_HEADING = "## Status of implementation"
README_HEADING = "## Status"

#: `NNNN-slug.md`. `docs/decisions/README.md` is the record index and is not a record; the
#: repository README is read separately, by `readme_rows`.
RECORD = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")

#: The next top-level section, or the end of the file.
NEXT_SECTION = re.compile(r"^## ", re.MULTILINE)

ISSUE_REF = re.compile(r"/issues/(\d+)")

#: What a state cell says when the clause is decided and nobody has built it. Matched
#: case-insensitively against the claim alone, so "**Built, and the clause gained a finding.**"
#: cannot trip it by containing the word "built".
#:
#: `unbuilt` is here as well as `not built` (#312). Both phrasings are in live use — 0032
#: clause 6 says "**Decided, unbuilt.**" over open #216 and had never been read as a claim at
#: all — and a guard that knows one spelling of the thing it exists to catch is a guard the
#: next author defeats by accident.
#:
#: **`unbuilt` must be predicative**, which is the lookahead. Used attributively it modifies a
#: noun and is prose *about* the practice rather than a claim about a clause, and README's M0
#: cell is exactly that: "an **unbuilt** one now carries an issue of its own ([#126])" cites a
#: closed issue correctly, because #126 is the change that instituted the practice. That is
#: 0027's narrative-append false positive wearing different clothes, and the fix has to be the
#: same in spirit — separate the two by structure, not by weakening the phrase until the
#: nuisance stops. A predicate ends its clause, so the next thing after it is punctuation or
#: nothing; an attributive is followed by the noun. "unbuilt one", "unbuilt work" and
#: "unbuilt clauses" are excluded, and "unbuilt.", "unbuilt;" and "unbuilt ([#301])" are not.
UNBUILT = re.compile(r"not built|unbuilt(?=\s*$|\s*[^\w\s])", re.IGNORECASE)


@dataclass(frozen=True)
class Claim:
    """One assertion about one clause, and the issues it cites.

    The unit the guard actually judges. A record's row holds exactly one; a README cell holds
    one per sentence. See the module docstring for why those differ.
    """

    text: str

    @property
    def issues(self) -> tuple[int, ...]:
        """Every issue number this claim cites, in the order it cites them."""
        return tuple(int(n) for n in ISSUE_REF.findall(self.text))

    @property
    def unbuilt(self) -> bool:
        """Whether this claim says the clause is decided and nobody has built it."""
        return bool(UNBUILT.search(self.text))


@dataclass(frozen=True)
class StatusRow:
    """One row of one Status table."""

    record: str
    clause: str
    state: str
    claims: tuple[Claim, ...]

    @property
    def issues(self) -> tuple[int, ...]:
        """Every issue the row cites, across all its claims. Existence is checked against
        this; whether an issue is *open* is a question about one claim, not about the row."""
        return tuple(int(n) for n in ISSUE_REF.findall(self.state))

    @property
    def unbuilt(self) -> bool:
        """Whether any claim in the row says the clause is unbuilt."""
        return any(claim.unbuilt for claim in self.claims)


#: Words whose full stop ends an abbreviation rather than a sentence. `p.` is the one that
#: matters and it is everywhere in this repository's prose — every citation of the document is
#: a page reference, so a splitter that does not know it cuts "p. 89" into two claims and
#: separates half the assertions in README from the pages they rest on.
ABBREVIATIONS = frozenset({"p", "pp", "e.g", "i.e", "cf", "vs", "no", "fig", "ch", "vol"})

#: Sentence-ending punctuation, plus any Markdown emphasis closing after it. "…shapes.**" ends
#: a sentence and the `.` is not the last character, which is the ordinary case in these cells
#: rather than an unusual one.
SENTENCE_END = re.compile(r"[.!?][*_`)\]]*(?=\s)")

#: The word immediately before a candidate full stop, for the abbreviation test.
TRAILING_WORD = re.compile(r"([A-Za-z.]+)\Z")


def sentences(text: str) -> tuple[str, ...]:
    """Split a README state cell into sentences, keeping page references whole."""
    found: list[str] = []
    start = 0
    for end in SENTENCE_END.finditer(text):
        word = TRAILING_WORD.search(text[start : end.start()])
        if word and word.group(1).lower().rstrip(".") in ABBREVIATIONS:
            continue
        found.append(text[start : end.end()].strip())
        start = end.end()
    tail = text[start:].strip()
    if tail:
        found.append(tail)
    return tuple(sentence for sentence in found if sentence)


def status_section(text: str, heading: str = RECORD_HEADING) -> str:
    """That file's Status section, or the empty string.

    The heading is matched as a whole line: `## Status` is a prefix of `## Status of
    implementation`, so a substring search would find the wrong section in a record.
    """
    marker = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    found = marker.search(text)
    if not found:
        return ""
    body = text[found.end() :]
    end = NEXT_SECTION.search(body)
    return body[: end.start()] if end else body


def _rows(
    record: str,
    text: str,
    *,
    heading: str,
    header_state: str,
    per_sentence: bool,
) -> tuple[StatusRow, ...]:
    """Every table row in that file's Status section.

    The header and the `|---|---|` separator are skipped, and so is every line that is not a
    table row — which is the whole point (see the module docstring).
    """
    found: list[StatusRow] = []
    for line in status_section(text, heading).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 2:
            continue
        clause, state = cells
        if state.lower() == header_state or set(state) <= set("- :"):
            continue
        spans = sentences(state) if per_sentence else (state,)
        found.append(
            StatusRow(
                record=record,
                clause=clause,
                state=state,
                claims=tuple(Claim(span) for span in spans),
            )
        )
    return tuple(found)


def rows_in(record: str, text: str) -> tuple[StatusRow, ...]:
    """Every Status row in one decision record. One row is one claim."""
    return _rows(record, text, heading=RECORD_HEADING, header_state="state", per_sentence=False)


def readme_rows(text: str) -> tuple[StatusRow, ...]:
    """Every Status row in README. One row is one claim *per sentence* (#312)."""
    return _rows(
        "README.md",
        text,
        heading=README_HEADING,
        header_state="where it stands",
        per_sentence=True,
    )


def all_rows(decisions: Path, readme: Path) -> tuple[StatusRow, ...]:
    """Every Status row across every record and README, in record order then README.

    `readme` is required rather than optional. An argument that defaults to "do not read
    README" restores the blind spot #312 exists to close, silently, in whichever caller
    forgets it.
    """
    found: list[StatusRow] = []
    for path in sorted(p for p in decisions.iterdir() if RECORD.match(p.name)):
        found.extend(rows_in(path.name, path.read_text(encoding="utf-8")))
    found.extend(readme_rows(readme.read_text(encoding="utf-8")))
    return tuple(found)
