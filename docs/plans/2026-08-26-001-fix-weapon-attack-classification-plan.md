---
title: A term the document defines and never uses - Plan
type: fix
date: 2026-08-26
topic: weapon-attack-classification
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/229
---

# A term the document defines and never uses - Plan

## Goal Capsule

- **Objective:** Settle whether `weapon-attack` names a second effect shape or double-counts `attack-roll`, and state the rule that decides every entry of that shape.
- **Headline finding:** **Neither.** #229 offers a two-way choice and the document supplies a third answer. SRD 5.2 defines *Weapon Attack* on p. 191 and then **never uses the term again** — two occurrences in the whole document, both inside the entry itself. It is not a mechanic the engine could double-count; it is a name with no consumer.
- **The rule:** a glossary entry that renames an inventoried mechanism with a parameter fixed, and that no other rule selects on, is **vocabulary**. It differs from its parent in a parameter rather than in mechanism, which is the `mechanism-not-exemplar` criterion already in the artifact (0013, Q1/Q3/Q5).
- **Consequence:** `weapon-attack` moves to `vocabulary`. The denominator moves **211 → 210** and coverage reads **96 of 210**. This is the classification move 0033 clause 5 deliberately declined to make in passing, and #229 is where it gets made.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. The official SRD v5.2.1 PDF at `/path/to/SRD_CC_v5.2.1.pdf` is the authority on every mechanic; no mechanic is inferred from memory (R31).
- **Stop conditions:** Stop and ask if the sweep finds any rule outside p. 191 that selects on "weapon attack", or if applying the rule would move a second entry not named in KTD4.
- **Tail ownership:** One PR. Any question the rule surfaces and does not settle is filed before the PR merges.

---

## Problem Frame

[#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229) was filed by [0033](../decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) clause 5 and asks:

> Is naming a sub-case of an already-claimed mechanic a second shape, or a double count?

It is reachable *because* of 0033 clause 1. Once a shape's content is what the document states about it anywhere, `attack_resolver` with a weapon looks like exactly the consequence p. 191 states — so `weapon-attack` looks claimable. But `attack-roll` (p. 177) is already claimed, and claiming both may report one mechanic twice, inflating the figure R17 makes falsifiable.

The issue frames this as a two-way choice, and both branches are bad:

- **Claim it** and the coverage figure may count one mechanic twice, which is the R17 failure in the direction opposite to #228's.
- **Leave it unclaimed** and `211 of 211` is unreachable — which is #228's option 3, the one 0033 rejected as *false*, arrived at by a different road.

That second branch is the trap #229 does not name, and it is why the issue cannot be left to sit indefinitely. A shape nobody can ever claim without double-counting is a ceiling that cannot be reached, and 0033 already ruled that a false disclosure of an unreachable ceiling is worse than none.

---

## What the Sweep Found

Both entries were read in the PDF during planning, and the term was swept across all 361 pages.

**Finding 1 — `attack-roll`'s own entry already names the three cases.** p. 177:

> An attack roll is a D20 Test that represents making an attack with a weapon, an Unarmed Strike, or a spell. See also "Playing the Game" ("D20 Tests").

p. 191:

> A weapon attack is an attack roll made with a weapon. See also "Weapon."

`weapon-attack` is not a sub-case discovered elsewhere in the document. It is **one of the three disjuncts the parent entry itself enumerates**, restated as a heading. The issue's phrase "a sub-case of an already-claimed mechanic" is accurate but understates how tight the relationship is.

**Finding 2 — the decisive one. The defined term has no consumers.** Sweeping the document for each term, case-insensitively:

| Term | Occurrences | Where |
|---|---|---|
| `weapon attack` | **2** | Both on p. 191: the entry's heading and the one sentence of its body |
| `spell attack` | 56 | Spell descriptions, stat blocks, magic items |
| `melee attack` | 406 | Throughout |
| `ranged attack` | 104 | Throughout |
| `Unarmed Strike` | 28 | Throughout |

A third raw hit was checked and is a **false positive**: p. 217's Dancing Sword magic item reads *"After the hovering weapon attacks for the fourth time"* — a noun followed by a verb, not the defined term.

So SRD 5.2 defines *Weapon Attack* on p. 191 and never invokes it. Where the 2014 rules used "Melee Weapon Attack" in stat blocks, the 2024 document says **"Melee Attack Roll"** and **"Ranged Attack Roll"**; "melee attack" and "ranged attack" are the terms that carry load, at 406 and 104 uses. Nothing in the document gates a mechanic on whether an attack is a *weapon* attack.

**This is what makes the answer a third option rather than a choice between the issue's two.** There is no consequence for the engine to produce — not because the entry is terse (0033 settled that terseness decides nothing), but because the term is inert. And under 0033 clause 1, the document-wide sweep is exactly the right test: clause 1 says extra-entry text may *supply* a consequence, and here the sweep shows there is no extra-entry text at all.

**Finding 3 — its two siblings differ in mechanism, not in a parameter, and both correctly stay shapes.** This is what keeps the rule from over-firing:

- **`spell-attack` (p. 188, claimed) has its own bonus formula.** p. 106: *"Spell attack modifier = your spellcasting ability modifier + your Proficiency Bonus"* — a rule `attack-roll` does not state, already asserted in `scripts/verify_d20_rules.py` and resolved by `core.spellcasting.spell_attack_modifier`. Its `ENGINE_SHAPES` entry points at the formula, not at the attack roll.
- **`unarmed-strike` (p. 190, unclaimed) has its own effect table.** Three options — Damage, Grapple, Shove — with their own damage expression (1 + Strength modifier) and its own save.
- **`weapon-attack` adds only a parameter**: what the attack is made with. No formula, no options, no consumer.

The three disjuncts of `attack-roll` therefore split two-to-one on a stated criterion rather than on taste.

**Finding 4 — the precedent for the disposition is already in the tree, with its guard.** `heroic-inspiration` sits in `vocabulary` carrying a per-entry reason:

> Mechanical, but not a separate shape: it is the document's own name for one instance of `die-replacement`, differing from Halfling Luck and Wish in trigger and cost rather than in mechanism. Decision 0013, Q5.

`VOCABULARY_REASONS` in the generator exists for exactly this case — an entry set aside for a reason other than the default glossary-term exclusion — and `tests/test_effect_shape_inventory.py::test_an_entry_set_aside_carries_the_reason_that_actually_applied_to_it` already asserts that such an entry names the shape which subsumes it. **This plan adds no new category and no new machinery to the inventory.** It is the second member of a pattern that shipped with one.

---

## Key Technical Decisions

**KTD1 — `weapon-attack` is vocabulary, not a shape and not a double count.** *(session-settled: user-approved — chosen over claiming it at 97 of 211 and over leaving it permanently unclaimed.)* Its entry renames `attack-roll` with a parameter fixed, and no rule in the document selects on the result. It is filed with a per-entry reason naming `attack-roll` as the mechanism that subsumes it, following `heroic-inspiration`.

**KTD2 — The criterion is the one already in the artifact.** `mechanism-not-exemplar` (0013, Q1/Q3/Q5) reads *"A shape is named for the mechanism it is, not for the feature that exhibits it. Two features whose rules differ only in a parameter are one shape."* `weapon-attack` and `attack-roll` differ only in what the attack is made with. No new criterion is introduced, and `criteria` in the shipped data is not extended — the entry is a new *application* of a rule that was already stated and already had a member.

**KTD3 — Zero consumers is the discriminating evidence, and it is a negative that must be asserted.** *(session-settled: user-directed.)* Finding 3 shows that "renames a parent with a parameter fixed" alone does **not** decide the question: `spell-attack` reads that way too and is correctly a shape, because p. 106 gives it a formula. What separates them is whether the document uses the term to gate anything. So the reason `weapon-attack` moves is the *absence* of any other use — and an absence is precisely the kind of claim that decays silently, because nothing goes red when it stops being true. KTD3 requires the absence be machine-checked, which is the mirror of 0033 clause 3: a claim resting on text outside the entry cites the page and asserts the sentence; a **de**classification resting on the absence of text outside the entry must assert the absence.

**KTD3a — Asserting an absence needs machinery the verifier does not have.** `scripts/verify_d20_rules.py` holds `(printed page, what it settles, pattern)` triples and checks each pattern is *present* on one page. It cannot express "this term appears exactly twice in the whole document." U2 adds a second, small clause table for document-wide count assertions rather than bending the existing one, because the two make opposite claims and a reader must not have to work out which kind a row is.

**KTD4 — Exactly one entry moves.** The rule is stated generally and applied narrowly, and the reason is Finding 3: the other candidates fail the zero-consumer test. `save` (#230) is a *pure* synonym with no parameter at all and is a different question, deliberately left to its own issue. No other entry is re-classified in this change.

**KTD5 — The denominator moves, and that is the point rather than a side effect.** 211 → 210, coverage 96 of 210, `test` slice 12 of 13, vocabulary 20 → 21. 0033 clause 5 held the denominator still because it was settling a *claiming* question; #229 is a *classification* question, which 0013 owns and which moves the denominator by design. The published figure changing is the visible form of the answer.

**KTD6 — Grounded in the PDF, read before deciding.** *(session-settled: user-directed — chosen over reasoning from 5e knowledge, where "Melee Weapon Attack" is a familiar stat-block phrase from the 2014 rules and is exactly the false memory that would have produced the wrong answer here (R31).)* Both entries, the p. 106 formula, the p. 217 false positive and all five term counts were read from `/path/to/SRD_CC_v5.2.1.pdf` during planning.

---

## Scope Boundaries

**In scope:** the decision record; the document-wide absence assertion and the machinery for it; moving `weapon-attack` to `vocabulary` in generator and shipped data; the coverage figures; a guard pinning the finding; the build stamp.

### Deferred to Follow-Up Work

- **Nothing new is deferred.** This plan opens no question it does not answer. If the sweep in U2 turns up a consumer of the term (it did not during planning), that is a stop condition rather than a deferral.

**Out of scope:** `save` ([#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230)), which is a pure synonym and a distinct question; re-classifying `spell-attack` or `unarmed-strike`, which Finding 3 shows differ in mechanism; extending the `criteria` block, which already states the rule being applied.

---

## Implementation Units

### U1. Decision record 0034

- **Goal:** Record KTD1-KTD3 and why #229's two options are both declined.
- **Requirements:** R17, R31, R32.
- **Dependencies:** none.
- **Files:** `docs/decisions/0034-a-term-the-document-defines-and-never-uses.md`, `docs/decisions/README.md`.
- **Approach:** House format exactly (Status / Settles / Requirements / Related; Context; Options considered; Decision; Why; Consequences; Evidence; **Status of implementation** with a clause table). Related: [0013](../decisions/0013-effect-shape-normalisation.md), which owns the shape/vocabulary boundary and supplies the criterion; [0033](../decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md), which filed the question and whose clause 5 explicitly left it. Carry the term-count table as Evidence, and the p. 217 false positive with it — a sweep that reports 3 and is not checked reads as three consumers.
- **Note the supersession of an arithmetic, not a decision:** 0033 clause 6 states its sweep scope as "the 135 Rules-Glossary shapes plus the 20 `vocabulary` entries — 155 headings." After this change the same 155 headings split 134/21. 0033 is not edited; 0034 records the shift, because a reader comparing the two records will otherwise think one of them is wrong.
- **Test scenarios:** `tests/test_decision_records.py` asserts every record carries **Status of implementation** and that the record-count floor holds. Adding the file exercises both.
- **Verification:** `pytest tests/test_decision_records.py` green; the index row renders.

### U2. Assert the absence, and build the machinery to state one

- **Goal:** Make KTD3's negative machine-checkable, so a future SRD revision that starts using "weapon attack" goes red rather than leaving the entry filed as vocabulary on reasoning nobody re-ran.
- **Requirements:** R31, R32.
- **Dependencies:** none.
- **Files:** `scripts/verify_d20_rules.py`.
- **Approach:** Add a second clause table — `DOCUMENT_CLAUSES`, as `(what it settles, pattern, expected count)` — checked across every page rather than one, with its own reporting line in `main`. Three rows:
  1. `weapon attack` appears exactly **2** times, both on p. 191 — the claim KTD1 rests on.
  2. `spell attack` appears **more than twice** — the control. Without it, row 1 passes just as well against a PDF that failed to extract, and a guard that passes on an empty document is inspecting nothing.
  3. The p. 191 sentence itself, as an ordinary presence clause in `CLAUSES`, so the text being reasoned about is pinned alongside its count.
- **Also in this unit:** a presence clause for p. 177's *"an attack with a weapon, an Unarmed Strike, or a spell"*, which is Finding 1 — the parent entry enumerating its own three cases. It is the sentence that makes `weapon-attack` a restatement rather than an extension, and it belongs pinned next to the count.
- **Patterns to follow:** the existing `CLAUSES` tuple shape and `main`'s failure accumulation; the p. 11 clauses added by #231 for how a clause block introduced by a decision record is commented.
- **Test scenarios:** run against the PDF; confirm the new rows pass and the existing clause count is unchanged. Corrupt row 1's expected count from 2 to 3 and confirm it goes red — the plausible-wrong value, since 3 is what a naive sweep reports before the p. 217 false positive is discarded.
- **Execution note:** the verifier is hand-run and needs the PDF; CI has no copy, so `scripts/prove_guard_red.sh` cannot drive it. Prove the corruption on a **copy** of the script and delete the copy afterwards, exactly as #231's plan did for its p. 11 clause. Add a CI presence check anchoring the new table, following `tests/test_hazards.py::test_the_prone_qualifier_is_asserted_against_the_document` — a test that reads the verifier's source, so CI can tell the table was deleted even though it cannot run it.
- **Verification:** `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` reports all clauses verified including the new table; the corrupted copy reports the count mismatch.

### U3. Move `weapon-attack` to vocabulary

- **Goal:** Re-file the entry in the generator and the shipped data together, with a per-entry reason.
- **Requirements:** R17.
- **Dependencies:** U2 (the absence must be asserted before the classification rests on it).
- **Files:** `scripts/derive_effect_shapes.py` (`KINDS`, `VOCABULARY_REASONS`), `src/srd_rules_engine/data/effect_shapes.json`.
- **Approach:** `KINDS["Weapon Attack"]` becomes `("vocabulary", False)`. Add a `VOCABULARY_REASONS` entry naming `attack-roll` as the subsuming shape, the parameter that is fixed, and the zero-consumer finding — modelled on `Heroic Inspiration`'s wording and citing decision 0034. Regenerate the JSON from the PDF rather than hand-editing it; the shipped file is generator output and a hand-edit would diverge silently.
- **`ENGINE_SHAPES` is not touched.** `weapon-attack` was never in it — the entry was `implemented: false` — so this is a pure classification move with no claim change. Worth stating in the record, because a denominator moving without a numerator moving is the shape of an inflated figure and a reader is right to check.
- **Patterns to follow:** the `Heroic Inspiration` entry in `VOCABULARY_REASONS` and its guard.
- **Test scenarios:** `test_vocabulary_entries_are_recorded_with_a_reason` passes with 21 entries; `test_an_entry_set_aside_carries_the_reason_that_actually_applied_to_it` still finds more than one distinct reason; `test_the_glossary_claims_agree_with_the_generator_that_writes_them` passes; re-running the generator reproduces the shipped file byte-for-byte and reports 96 implemented of 210.
- **Verification:** all inventory guards green; `coverage_report()` reports 96/210.

### U4. Pin the finding so the next sweep starts from it

- **Goal:** Stop the entry drifting back to a shape, and record *why* it is vocabulary where a reader can see it — the zero-consumer test rather than "it looked definitional", which 0033 established decides nothing.
- **Requirements:** R17, R32.
- **Dependencies:** U3.
- **Files:** `tests/test_effect_shape_inventory.py`.
- **Approach:** A test asserting `weapon-attack` is in `vocabulary` and **not** in `shapes`, with the rule in its docstring and the term counts quoted. Assert the counter-set in the same test: `spell-attack` and `unarmed-strike` are **shapes**, each for the mechanism Finding 3 names. That is what makes the guard fail in both directions — without it, the test is satisfiable by moving every sub-case to vocabulary, which is the deflation failure mirroring the inflation KTD1 avoids.
- **Patterns to follow:** `test_a_definitional_glossary_body_does_not_decide_whether_a_shape_is_claimed`, added by #231 — same shape, same counter-set construction, and it already guards the neighbouring rule.
- **Test scenarios:** `weapon-attack` absent from `shapes` and present in `vocabulary`; `spell-attack` and `unarmed-strike` present in `shapes`. Prove red both ways: move `weapon-attack` back to a shape, then move `spell-attack` to vocabulary.
- **Execution note:** run through `scripts/prove_guard_red.sh` in both directions, corrupting `src/srd_rules_engine/data/effect_shapes.json`. Never restore with `git checkout --` — the file carries an uncommitted edit from U3 at this point, which is exactly the case that discards real work.
- **Verification:** `pytest tests/test_effect_shape_inventory.py` green; both corruptions red.

### U5. Coverage figures, build stamp, and the issue's answer

- **Goal:** Publish the moved denominator and the reasoning, and close #229 with the third answer rather than one of its two.
- **Requirements:** R17.
- **Dependencies:** U1-U4.
- **Files:** `README.md`, `src/srd_rules_engine/__init__.py`, `tests/test_readme_reports_real_coverage.py`.
- **Approach:** every site, because the README carries these figures in five places and only some are guarded:
  1. The coverage sentence: `96 of 211` → `96 of 210`, **and its remainder `The other 115` → `114`**. Guarded by `test_the_coverage_sentence_publishes_the_inventorys_own_figures`.
  2. The v1.0 milestone row: `96 of 211 effect shapes` → `96 of 210`, and **`the d20 test 12/14` → `12/13`**. Both guarded.
  3. **The vocabulary sentence**, currently *"Twenty entries are recorded as vocabulary with a stated reason rather than dropped"* → **"Twenty-one"**. Guarded by `test_the_vocabulary_count_is_the_inventorys`, whose `SPELLED` map already carries 21; no test change needed.
  4. **The milestone row's prose**, which no guard checks. It should gain a sentence recording that the d20-test denominator fell because a term the document never uses stopped being counted — otherwise `12/13` reads as a shape having been deleted.
  5. `__version__` to the next `mmddyyyy.x`, and both README stamps with it.

  `tests/test_readme_reports_real_coverage.py` needs **no numeric edit**, and this was checked rather than assumed during planning: its slices are computed from the inventory, `NAMED_SLICES["the d20 test"]` follows the data, no literal `"12/14"` appears in the file, and `SPELLED` already maps 21 to `"Twenty-one"`. The three moved figures are all guarded by tests that derive them, so a missed README edit fails the build rather than shipping.

  The build line leads with the finding — a term the document defines once and never uses — not with the count.
- **Patterns to follow:** the build lines from #231 and #225.
- **Test scenarios:** `tests/test_build_stamp.py` green; `tests/test_readme_reports_real_coverage.py` green; `scripts/check_build_stamp_advanced.py main` reports advanced.
- **Verification:** full gate green; the stamp guard passes against `main`'s tip.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy` — all four, per `AGENTS.md`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses verified, new table included.
- `python scripts/derive_effect_shapes.py /path/to/SRD_CC_v5.2.1.pdf` then `git diff --stat` — regeneration is a no-op against the committed JSON.
- `scripts/prove_guard_red.sh` for **U4 only**, both directions.
- **U2 by hand:** copy `scripts/verify_d20_rules.py` aside, corrupt the copy's expected count from 2 to 3, run the copy against the PDF, confirm the count mismatch reports, delete the copy. Never edit the tracked script to prove this.
- `scripts/prove_against_base.sh main tests/test_effect_shape_inventory.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- Decision record 0034 exists, is indexed, and its **Status of implementation** names what landed.
- The document-wide clause table asserts `weapon attack` at exactly 2 occurrences with `spell attack` as its control; a CI presence check anchors it; the count is proved red on a copy.
- `weapon-attack` is `vocabulary` in generator and data; regeneration byte-identical; `ENGINE_SHAPES` untouched.
- U4's guard proved red in both directions.
- Coverage published as **96 of 210**, the d20 test as **12 of 13**, vocabulary as **Twenty-one**; build stamp advanced; full gate green.
- #229 closed with the third answer — the term has no consumers, so it is neither a second shape nor a double count — rather than with one of its two options.

---

## Open Questions

- **None.** #230 (`save` as a pure synonym) is adjacent and stays open on its own issue; KTD4 states why it is not decided here.

## Risks

- **The absence could be an extraction artifact rather than a fact about the document.** A PDF text layer that dropped a ligature or a line break would under-count silently, and the whole decision rests on the count. Mitigated by U2's control row: `spell attack` must exceed two occurrences in the same sweep, so an extraction that lost the term loses the control too and the verifier goes red rather than confirming the convenient answer.
- **The rule could over-fire on the next reader.** "Renames a parent with a parameter fixed" describes `spell-attack` as well, which is claimed and correct. Mitigated by KTD3 making zero-consumers the operative test rather than the phrasing of the entry, and by U4 asserting `spell-attack` and `unarmed-strike` stay shapes — the guard fails if the rule is applied too widely.
- **A denominator that falls looks like a figure being managed.** Coverage rises from 45.5% to 45.7% without any new capability. Mitigated by stating it: U3 notes `ENGINE_SHAPES` is untouched, and the record says outright that the numerator does not move. The honest reading is that the denominator was wrong, not that the engine improved.

## Sources & Research

- SRD v5.2.1 PDF, p. 177 (*Attack Roll*), p. 188 (*Spell Attack*), p. 190 (*Unarmed Strike*), p. 191 (*Weapon Attack*), p. 106 (spell attack modifier), p. 217 (Dancing Sword, the false positive), read during planning.
- Document-wide term sweep across all pages for `weapon attack`, `spell attack`, `melee attack`, `ranged attack` and `Unarmed Strike`.
- `scripts/derive_effect_shapes.py` (`KINDS`, `VOCABULARY_REASONS`), `src/srd_rules_engine/core/inventory.py` (`ENGINE_SHAPES`), `src/srd_rules_engine/data/effect_shapes.json` (`criteria`), `tests/test_effect_shape_inventory.py`, `tests/test_readme_reports_real_coverage.py`.
- [0013](../decisions/0013-effect-shape-normalisation.md) for the criterion and the shape/vocabulary boundary; [0033](../decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) for the question and for clause 5 leaving it open.
