# 0070 — An instrument that cannot notice its own staleness

- **Status:** Accepted, 2026-08-30
- **Settles:** [#373](https://github.com/eddiefiggie/srd-rules-engine/issues/373)
- **Requirements:** R17, R31
- **Related:** [0017 — verification is a pattern asserted against the document](0017-verification-is-asserted-not-read.md),
  whose reproducibility argument this restores;
  [0068 — a rule the menu asks and nothing else does](0068-a-rule-the-menu-asks-and-nothing-else-does.md),
  the same "derive both sides, and raise on what you cannot read" shape;
  [0024 — the build line is the build record](0024-the-build-line-is-the-build-record.md), on
  why a dated claim needs something that can re-check it

## Context

`scripts/derive_effect_shapes.py` is the reproducible half of `effect_shapes.json`, which is
where the README's two published coverage figures come from. It crashed:

```
  File "scripts/derive_effect_shapes.py", line 1021, in sweep_equipment
    for shape_id, name, kind, entry_name, page, pattern in EQUIPMENT_SHAPES:
ValueError: not enough values to unpack (expected 6, got 5)
```

`tests/test_readme_reports_real_coverage.py` guards that the published figures match
`core.inventory`. It does **not** guard that the inventory still matches the document, because
CI has no copy of the SRD — `NOTICE.md` explains it is not ours to redistribute. This script is
the only thing that closes that loop, and it was the same reproducibility promise
`scripts/verify_d20_rules.py` makes for the d20 rules.

So: *117 of 210* was checked against the inventory, and the inventory was checked against
nothing.

**The cause, exactly.** [#352](https://github.com/eddiefiggie/srd-rules-engine/issues/352) added
`"mastery-push"` to `IMPLEMENTED_SECTION_SHAPES` and, in the same diff, deleted the identical
line from `EQUIPMENT_SHAPES`'s Push row — a mis-anchored edit on two occurrences of one string.
The row went from six elements to five. The script had run correctly since
[#69](https://github.com/eddiefiggie/srd-rules-engine/issues/69) introduced that table on
2026-08-23 and broke on 2026-08-29, one day before it was found.

## Options considered

**Option 1 — repair the row.** Necessary and not sufficient, which is the whole finding. Ten
tables in that script share the shape `tuple[tuple[str, str, str, str, int, str], ...]` and each
is swept by its own six-name unpack. Every one of them was exposed to the identical accident,
and repairing the one that fired leaves the trap set for the other nine.

**Option 2 — put the script in CI.** Rejected: CI has no PDF and cannot be given one. This is
the constraint the whole design is downstream of, not an oversight.

**Option 3 — ship a fixture PDF or extracted text.** Rejected outright. It is SRD prose, and
this repository carries none.

**Option 4 — check the half that needs no document.** Chosen. The claim that broke was
*structural*: rows of the arity the sweep unpacks. That is a property of the script's own source
and needs no SRD at all, so it runs in CI on every pull request like any other test.

**Option 5 — a `--check` mode.** Chosen alongside. The writing form cannot tell you the
inventory was already right: it overwrites and leaves you to read a diff, which is a different
question from "is what shipped still what the document says".

## Decision

**1. The Push row is whole again**, and the regenerated `effect_shapes.json` is **byte-identical
to what shipped** — 210 shapes, 117 implemented, 22 vocabulary. Nothing about the inventory was
wrong; it had merely stopped being re-checkable.

**2. `tests/test_shape_tables_are_well_formed.py` runs in CI and reads no document.** Every
shape table's row arity must equal the number of names its sweep unpacks.

**3. Both sides are derived from the source.** The arity a table's rows *have*, and the arity
its sweep *unpacks*. A pin restating either would be a pin over itself —
[#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334)'s lesson, and the reason
that file's condition half worked for its whole life while its other half was blind.

**4. Tables are selected by their annotation, not by their name.** `IMPLEMENTED_SECTION_SHAPES`
ends in `_SHAPES` and is a `frozenset[str]`. A name-suffix selector picks it up and then has to
decide what to do with something it cannot read — which is precisely the decision clause 5
forbids.

**5. A table or sweep the walk cannot parse raises rather than being skipped.** A walk that
quietly ignores what it cannot read goes blind in the way the assertion it replaced did.

**6. `--check` compares without writing and exits non-zero on a difference.**

**7. The script's docstring carries the date it last ran green.** It is not in CI and cannot
notice its own staleness; nothing else can record that, so the line is the record — the same
argument [0024](0024-the-build-line-is-the-build-record.md) made for the build line.

## Why

**The interesting result is that the data was right.** A crashed generator invites the
assumption that its output has drifted. It had not: the first successful run in a day
reproduced the shipped file byte for byte. What was lost was not accuracy but *falsifiability* —
R17's whole claim is that coverage is checkable, and for a day the check could not be performed.
That distinction is worth a record, because the instinct on finding a broken instrument is to
distrust the readings, and here the readings were fine and the instrument was not.

**Clause 2 is the generalisable move.** "CI has no document" reads as "none of this can be
checked in CI", and that is one inference too far. The document-dependent half genuinely
cannot be; the structural half never needed the document, and it is where the defect actually
lived. Splitting a guard by *what it depends on* rather than by *which script it lives in*
recovered CI coverage of the exact failure with no PDF anywhere near it.

**Clause 4 is a mistake this record made and kept.** The first draft selected tables by the
`_SHAPES` suffix, hit `IMPLEMENTED_SECTION_SHAPES`, and — because clause 5 was already written —
raised instead of skipping. That was the guard working: it refused to quietly ignore something
it could not read, and the fix was to say what a table *is* rather than what it is *called*.
Had clause 5 not been there, the natural repair would have been a `continue`, and the walk would
have acquired its first blind spot on the day it was written.

**One day is the measure, and it is the good case.** The break was found because an unrelated
build needed the coverage figures. Nothing about the repository would have raised it otherwise,
and the figures are in the README of a public project.

## Consequences

**Accepted costs.**

- **The structural guard is not the document guard.** It cannot tell you the inventory has
  drifted from the SRD; only a person with the PDF and `--check` can. What it removes is the
  failure where nobody *can* ask.
- **Clause 7's date is prose, and prose is on the author.** `AGENTS.md` already says the build
  stamp's guards do not check that the prose is honest. This is another line of that kind, and
  it is the best available answer for a script CI cannot run.
- **Ten tables now have a shape they must keep.** Adding a seventh column to one means editing
  its sweep in the same change, which is the point and is still friction.

**Follow-on effects.**

- **The coverage figures are re-derivable again**, so R17's falsifiability claim is true rather
  than merely stated. `117 of 210` and `16 clauses` both stand unchanged.
- **The README says the script is not in CI and what is**, rather than leaving a reader to
  assume the whole instrument is unguarded.

## Evidence

`git log -S'mastery-push' -- scripts/derive_effect_shapes.py` names
[#352](https://github.com/eddiefiggie/srd-rules-engine/issues/352) as the only commit to touch
the id, and its diff shows the line added to `IMPLEMENTED_SECTION_SHAPES` and removed from the
`EQUIPMENT_SHAPES` row in the same hunk. An AST walk of the file at
[#69](https://github.com/eddiefiggie/srd-rules-engine/issues/69) reports row arities `[6]`; at
`main` before this change, `[5, 6]`.

After the repair, `derive_effect_shapes.py` exits 0 and `git diff` on
`src/srd_rules_engine/data/effect_shapes.json` is empty.

Five corruption proofs: the exact defect #352 shipped (twice, against the general assertion and
the named one), a sweep that grew a field, a table that lost its sweep, and the walk collapsing.
The new module goes red against the base tree on **failing assertions** rather than on import,
because the Push row was genuinely broken there.

## Status of implementation

**All seven clauses are built** by [#373](https://github.com/eddiefiggie/srd-rules-engine/issues/373).

| Clause | State |
|---|---|
| 1 — the row is whole and the data is unchanged | **Built.** Regenerating produces no diff |
| 2 — a hermetic guard in CI | **Built.** `tests/test_shape_tables_are_well_formed.py` |
| 3 — both sides derived | **Built.** `declared_arities()` and `unpacked_arities()` |
| 4 — selected by annotation, not by name | **Built.** `_is_row_table` |
| 5 — raise rather than skip | **Built**, and it fired during authoring |
| 6 — `--check` | **Built.** Compares and exits non-zero without writing |
| 7 — the last-run-green date | **Built** in the script's docstring |

_Written 2026-08-30 against SRD v5.2.1._
