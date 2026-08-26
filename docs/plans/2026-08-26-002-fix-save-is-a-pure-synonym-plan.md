---
title: Two names for one thing are one shape - Plan
type: fix
date: 2026-08-26
topic: save-is-a-pure-synonym
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/230
---

# Two names for one thing are one shape - Plan

## Goal Capsule

- **Objective:** Settle whether a term whose entire entry is *"X is another name for Y"* belongs in `vocabulary`, and state the rule that decides it.
- **Headline finding:** `save` is not merely *arguably* a duplicate — **the duplication is already in the tree and is exact.** `ENGINE_SHAPES["save"]` and `ENGINE_SHAPES["saving-throw"]` both resolve to `core.d20.TestKind.SAVE`, on adjacent lines. Two inventory entries, one symbol, counted twice in the numerator *and* the denominator of the figure R17 makes falsifiable.
- **The rule:** a term whose entry states it **denotes the same thing** as an inventoried term is one shape with that term, however heavily the document uses it. Identity, not usage.
- **Consequence:** `save` moves to `vocabulary`. Coverage **96 of 210 → 95 of 209**, the d20 test **12 of 13 → 11 of 12**, vocabulary 21 → 22. **The numerator falls too**, which is what makes this different from [#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229), and nothing is lost — `TestKind.SAVE` stays claimed under `saving-throw`.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. The official SRD v5.2.1 PDF at `/path/to/SRD_CC_v5.2.1.pdf` is the authority on every mechanic; no mechanic is inferred from memory (R31).
- **Stop conditions:** Stop and ask if any rule in the document turns out to treat a *save* differently from a *saving throw*, or if dropping `save` from `ENGINE_SHAPES` changes what any resolver produces.
- **Tail ownership:** One PR. Any question the rule surfaces and does not settle is filed before the PR merges.

---

## Problem Frame

[#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230) was filed by [0033](../decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) clause 5 and asks:

> Does a term whose entire entry is "X is another name for Y" belong in `vocabulary`?

p. 187 — *"Save is another name for a saving throw."* The entry states no mechanic of its own; it renames one. Under 0033 clause 1 it is claimed **correctly**, because the document states the saving throw's mechanic elsewhere and the engine produces it. But `vocabulary` means *defined here, not an effect shape*, and a pure synonym is arguably the clearest case of that.

**The two questions are different, and that is why there is no contradiction to resolve.** 0033 asked *can a definitional entry ever be claimed?* and answered yes. #230 asks *should this be an entry at all?* — a classification question 0013 owns and 0033 clause 5 explicitly declined to open, because moving an entry between shape and vocabulary changes a published figure.

**[0034](../decisions/0034-a-term-the-document-defines-and-never-uses.md) does not decide it either, and this is worth being precise about.** 0034's operative test is *zero consumers*: `weapon-attack` moved because the document defines the term and never uses it. That test does not reach `save`, which the document uses **1544 times** against `saving throw`'s 636. A rule phrased around usage would keep `save` a shape. The rule this plan states is about **identity** instead, and the two are independent.

---

## What the Sweep Found

Both entries were read in the PDF during planning, and the tree was inspected alongside them.

**Finding 1 — the document states the identity twice, in both directions, on the same page.** p. 187 carries both headings adjacently:

> **Save.** Save is another name for a saving throw. See also "Saving Throw."

> **Saving Throw.** A saving throw—also called a save—represents an attempt to avoid or resist a threat. You normally make a saving throw only when a rule requires you to do so, but you can decide to fail the save without rolling. […] See also "Playing the Game" ("D20 Tests").

The **parent entry declares the alias itself**. This is not an inference from two entries that happen to look similar: the SRD says outright, in each entry, that the two words name one thing. There is no parameter, no restriction, no sub-case — unlike `weapon-attack`, which at least named a proper subset by fixing what the attack was made with.

**Finding 2 — the decisive one. The double count is already in the tree, and it is exact.**

```
save                 -> core.d20.TestKind.SAVE
saving-throw         -> core.d20.TestKind.SAVE
identical: True
```

`src/srd_rules_engine/core/inventory.py` lines 219-220, adjacent. Two inventory ids claiming the same symbol. #229 worried that claiming a sub-case *might* count one mechanic twice; here the mechanic **is** counted twice, in a figure whose entire purpose is to be falsifiable, and it has been for as long as both entries have been claimed.

That fact does most of the work of this plan. It is not an argument about how a glossary entry reads — it is a duplicate visible in the code, and no reading of the document makes two ids pointing at one enum member into two shapes.

**Finding 3 — the counter-set, and it is close enough to matter.** `death-saving-throw` (p. 181) is also a "saving throw" by name and stays a shape, correctly: it resolves to `core.death.death_save_resolver`, its own mechanism with three successes, three failures and a fixed DC. The rule must distinguish "a second name for the same thing" from "a specialised thing named similarly", and the resolver symbol is what does it — `death-saving-throw` does not share `TestKind.SAVE`'s.

**Finding 4 — the existing `criteria` block does not cover this, and #229 declined to extend it.** The shipped artifact states three criteria (0013): `engine-held-state`, `closed-named-set`, `mechanism-not-exemplar`. The nearest is the third — *"Two features whose rules differ only in a parameter are one shape"* — and `save` and `saving-throw` do not differ even in a parameter, so the criterion covers the case *a fortiori* without stating it. [0034](../decisions/0034-a-term-the-document-defines-and-never-uses.md) deliberately did not extend `criteria`, because `weapon-attack` genuinely was a parameter case. A pure synonym is not, so this plan adds the fourth criterion rather than stretching the third.

**Finding 5 — one guard names `save` and must be edited, not worked around.** `tests/test_effect_shape_inventory.py::CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY` — the set #231 added to pin 0033 clause 1 — carries `"save": "the D20 Test rules — the entry renames a saving throw rather than defining one."` Once `save` is not a shape, that entry's assertion (`by_id` resolves, and is `implemented`) fails. The set drops to four members: `bright-light`, `damage`, `damage-types`, `healing`. Those four still make 0033's point, and the record must say so rather than leaving a reader to wonder whether 0033 was weakened.

**Finding 6 — nothing else in the tree references the shape id.** A sweep for the id outside the data file finds exactly one hit: `inventory.py:220`, the `ENGINE_SHAPES` line being removed. No resolver, no test, no adapter names it.

---

## Key Technical Decisions

**KTD1 — `save` is vocabulary. Two names for one thing are one shape.** *(session-settled: user-approved — chosen over keeping it a claimed shape, and over folding it into `saving-throw` as an alias field.)* p. 187 states the identity in both directions, and `ENGINE_SHAPES` already resolves both ids to one symbol.

**KTD2 — The test is identity, not usage, and it is a different test from 0034's.** 0034 moved `weapon-attack` because the document never uses the term. That reasoning does not reach `save` — 1544 uses to `saving throw`'s 636 — and a rule phrased around consumers would keep `save` a shape. The new criterion is: **a term whose entry states it denotes the same thing as an inventoried term is one shape with it, however often the document uses it.** Heavy use of a synonym is use of the thing it names.

**KTD3 — The discriminator against a specialised namesake is the resolver symbol.** `death-saving-throw` is a saving throw by name and is its own shape, because it resolves to `core.death.death_save_resolver` rather than to `TestKind.SAVE`. Two ids sharing one symbol is the machine-checkable form of "one mechanism"; similar names are not evidence either way. U3 asserts this in both directions.

**KTD4 — The numerator falls, and that is correct rather than a regression.** 96 → 95 with no capability lost: `TestKind.SAVE` stays claimed under `saving-throw`, and no resolver changes. A coverage figure that falls because a duplicate stopped being double-counted is the figure becoming *more* true. The README must say this where a reader meets it, for the same reason [0034](../decisions/0034-a-term-the-document-defines-and-never-uses.md) clause 5 said the opposite thing about a falling denominator: an unexplained movement in either direction reads as a figure being managed.

**KTD5 — `criteria` gains a fourth entry.** *(session-settled: user-directed.)* The rule is not derivable from the three present, and the artifact's `criteria` block exists precisely so a consumer can see the rules that decided shape from content rather than having to read generator comments (0013, Q2). Adding it there is what makes the rule auditable by someone who was not here.

**KTD6 — The evidence is a presence, so ordinary clauses assert it.** 0034 clause 3 required a *document-wide count* because its evidence was an absence, and nothing goes red when an unused term starts being used. This decision rests on a **stated sentence** instead, so two ordinary `CLAUSES` rows suffice. Worth stating in the record: the obligation is to assert whatever the decision actually rests on, not to reach for the newest machinery.

**KTD7 — Grounded in the PDF, read before deciding.** *(session-settled: user-directed.)* Both p. 187 entries, the counter-set entry on p. 181, and the two term counts were read from `/path/to/SRD_CC_v5.2.1.pdf` during planning, and the three candidate patterns were confirmed to match the normalised page text before being written into the plan.

---

## Scope Boundaries

**In scope:** the decision record; two p. 187 presence clauses; moving `save` to `vocabulary` in generator and data; dropping its `ENGINE_SHAPES` key; the fourth `criteria` entry; editing 0033's guard set; a two-direction guard; the coverage figures; the build stamp.

### Deferred to Follow-Up Work

- **Nothing new is deferred.** This plan opens no question it does not answer.

**Out of scope:** `death-saving-throw` and `saving-throw`, which Finding 3 shows are distinct mechanisms; any other entry — no sweep for further synonyms is run, and the record says so rather than implying the glossary was re-audited.

---

## Implementation Units

### U1. Decision record 0035

- **Goal:** Record KTD1-KTD3 and why the question is independent of both 0033 and 0034.
- **Requirements:** R17, R31, R32.
- **Dependencies:** none.
- **Files:** `docs/decisions/0035-two-names-for-one-thing-are-one-shape.md`, `docs/decisions/README.md`.
- **Approach:** House format (Status / Settles / Requirements / Related; Context; Options considered; Decision; Why; Consequences; Evidence; **Status of implementation** with a clause table). Related: [0013](../decisions/0013-effect-shape-normalisation.md) for the boundary and the `criteria` block; [0033](../decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md), which filed the question and whose guard set this change edits; [0034](../decisions/0034-a-term-the-document-defines-and-never-uses.md), the sibling classification record whose test does **not** decide this one.
- **State the relationship to 0033 explicitly**, since a reader will otherwise think one record contradicts the other: 0033 said a definitional entry *can* be claimed; this says this particular entry should not *be* an entry. Both are true, and 0033's guard set losing `save` weakens nothing — its remaining four members make the same point.
- **Test scenarios:** `tests/test_decision_records.py` asserts every record carries **Status of implementation** and that the record-count floor holds.
- **Verification:** `pytest tests/test_decision_records.py` green; the index row renders.

### U2. Assert p. 187, and move `save`

- **Goal:** Pin the sentences the decision rests on, then re-file the entry in generator, data and `ENGINE_SHAPES` together.
- **Requirements:** R17, R31.
- **Dependencies:** U1.
- **Files:** `scripts/verify_d20_rules.py`, `scripts/derive_effect_shapes.py` (`KINDS`, `VOCABULARY_REASONS`, the `criteria` block), `src/srd_rules_engine/data/effect_shapes.json`, `src/srd_rules_engine/core/inventory.py` (`ENGINE_SHAPES`).
- **Approach:** Two `CLAUSES` rows on p. 187, both confirmed to match during planning:
  1. `r"Save is another name for a saving throw"` — the entry itself.
  2. `r"A saving throw.also called a save.represents an attempt to avoid or resist a threat"` — the parent declaring the alias. The `.` stands for the em-dash the document sets, matching the file's existing convention for typographic characters.

  Then `KINDS["Save"]` becomes `("vocabulary", False)`, a `VOCABULARY_REASONS` entry names `saving-throw` as the shape it collapses into, and the fourth `criteria` entry is added with `decided_by: "0035"`. **Regenerate the JSON from the PDF rather than hand-editing it.**
- **`ENGINE_SHAPES` loses its `"save"` key**, which is the real difference from #229's unit — that change touched no claim, this one drops a duplicate claim. `TestKind.SAVE` remains claimed under `saving-throw`, so no resolver and no behaviour changes; confirm by running the full suite, not by inspection.
- **Patterns to follow:** the `Weapon Attack` entry in `VOCABULARY_REASONS`, added by #233; the three existing `criteria` entries for the fourth's shape.
- **Test scenarios:** `test_every_engine_shape_is_marked_implemented` and its converse both pass; `test_the_criteria_that_decided_shape_from_content_are_in_the_artifact` passes with four entries and unique ids; `test_kind_is_a_closed_vocabulary` still passes — `test` remains a used kind, since eleven `test` shapes remain; regeneration reproduces the shipped file byte-for-byte and reports 95 implemented of 209.
- **Verification:** `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` reports both new clauses; inventory guards green; `coverage_report()` reports 95/209.

### U3. Guards — edit 0033's set, and pin the new rule both ways

- **Goal:** Keep 0033's guard truthful after its subject leaves the inventory, and stop the synonym rule drifting in either direction.
- **Requirements:** R17, R32.
- **Dependencies:** U2.
- **Files:** `tests/test_effect_shape_inventory.py`.
- **Approach:** Two changes:
  1. Drop `"save"` from `CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY`, leaving four members, and extend the docstring to say where it went and why the guard is not weakened. **Not** a silent deletion: the set is evidence for 0033, and a member vanishing without explanation is how a guard comes to inspect less than it appears to.
  2. A new test asserting `save` is vocabulary and **not** a shape, that `saving-throw` **is** a shape, and that `death-saving-throw` is a shape resolving to a *different* symbol — the counter-set from Finding 3. Assert the symbol inequality directly rather than the ids, since the symbol is what KTD3 makes the discriminator.
- **Patterns to follow:** `test_a_renamed_mechanism_with_no_consumers_is_vocabulary_and_one_with_them_is_not`, added by #233 — same two-direction construction.
- **Test scenarios:** prove red both ways: put `save` back into `shapes`, then move `saving-throw` out. Also prove the symbol assertion red by pointing `death-saving-throw` at `TestKind.SAVE`, which is the corruption that would make the rule over-fire.
- **Execution note:** run through `scripts/prove_guard_red.sh`, corrupting `effect_shapes.json` and `inventory.py` respectively. Never restore with `git checkout --` — both files carry uncommitted edits from U2 at this point, which is exactly the case that discards real work.
- **Verification:** `pytest tests/test_effect_shape_inventory.py` green; all three corruptions red.

### U4. Coverage figures, build stamp, and the issue's answer

- **Goal:** Publish the fallen figures with the reason, and close #230.
- **Requirements:** R17.
- **Dependencies:** U1-U3.
- **Files:** `README.md`, `src/srd_rules_engine/__init__.py`.
- **Approach:** the figure sites, all guarded by tests that derive them from the inventory:
  1. Coverage sentence: `96 of 210` → `95 of 209`, remainder `114` → `114` (**confirm rather than assume** — the unimplemented count is unchanged only if `save` was implemented, which it was, so 114 stays 114).
  2. Milestone row: `96 of 210 effect shapes` → `95 of 209`, and `the d20 test 12/13` → `11/12`.
  3. Vocabulary sentence: `Twenty-one` → `Twenty-two`. `SPELLED` already maps 22; confirmed during planning.
  4. **The milestone row's prose**, which no guard checks. A *numerator* that falls needs saying more than a denominator did: it must record that nothing was lost, only that one mechanism stopped being counted twice.
  5. `__version__` to the next `mmddyyyy.x`, and both README stamps with it.

  The build line leads with the duplicate in `ENGINE_SHAPES`, which is the concrete finding, not with the rule.
- **Patterns to follow:** the build lines from #233 and #231.
- **Test scenarios:** `tests/test_build_stamp.py`, `tests/test_readme_reports_real_coverage.py` green; `scripts/check_build_stamp_advanced.py main` reports advanced.
- **Verification:** full gate green; stamp guard passes against `main`'s tip.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy` — all four, per `AGENTS.md`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses verified, both new ones included.
- `python scripts/derive_effect_shapes.py /path/to/SRD_CC_v5.2.1.pdf` then `git diff --stat` — regeneration is a no-op against the committed JSON.
- `scripts/prove_guard_red.sh` for U3, all three corruptions.
- `scripts/prove_against_base.sh main tests/test_effect_shape_inventory.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- Decision record 0035 exists, is indexed, and its **Status of implementation** names what landed.
- Two p. 187 clauses assert in the verifier.
- `save` is `vocabulary` in generator and data, its `ENGINE_SHAPES` key is gone, and `criteria` carries the fourth rule; regeneration byte-identical.
- 0033's guard set is down to four members **with the reason recorded**, not silently.
- U3's guard proved red three ways.
- Coverage published as **95 of 209**, the d20 test **11 of 12**, vocabulary **Twenty-two**, with the milestone row stating that nothing was lost; build stamp advanced; full gate green.
- #230 closed with the rule and the duplicate that proved it.

---

## Open Questions

- **None.** No sweep for further synonyms is run; the record states that limit rather than implying the glossary was re-audited.

## Risks

- **Dropping an `ENGINE_SHAPES` key could silently reduce what the engine claims.** It does not here — both ids resolve to one symbol, so the claim survives under `saving-throw` — but the guard that would catch a mistake is the full suite rather than inspection. Mitigated by running it, and by U3 asserting `saving-throw` is still a shape.
- **A falling numerator invites a later "fix" that restores it.** The duplicate looked like coverage for as long as it existed, and re-adding the key would raise the figure with no work. Mitigated by U3's first direction — putting `save` back into `shapes` must go red — and by the record naming the symbol equality as the reason.
- **The rule could over-fire on a specialised namesake.** `death-saving-throw` is the near case. Mitigated by KTD3 making the resolver symbol the discriminator and by U3's third corruption, which points it at `TestKind.SAVE` and must go red.

## Sources & Research

- SRD v5.2.1 PDF, p. 187 (*Save*, *Saving Throw*), p. 181 (*Death Saving Throw*), read during planning; the two candidate patterns confirmed against the normalised page text.
- Document-wide term counts: `save` 1544, `saving throw` 636 — the figures showing 0034's consumers test does not reach this case.
- `src/srd_rules_engine/core/inventory.py` (`ENGINE_SHAPES`, lines 219-220), `scripts/derive_effect_shapes.py` (`KINDS`, `VOCABULARY_REASONS`, `criteria`), `tests/test_effect_shape_inventory.py` (`CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY`, the criteria and closed-kind guards).
- [0013](../decisions/0013-effect-shape-normalisation.md), [0033](../decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md), [0034](../decisions/0034-a-term-the-document-defines-and-never-uses.md).
