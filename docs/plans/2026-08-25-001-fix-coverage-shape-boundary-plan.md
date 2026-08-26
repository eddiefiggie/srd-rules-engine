---
title: A glossary entry is an index, not a shape's boundary - Plan
type: fix
date: 2026-08-25
topic: coverage-shape-boundary
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/228
---

# A glossary entry is an index, not a shape's boundary - Plan

## Goal Capsule

- **Objective:** Settle what the coverage figure means for SRD entries whose *glossary text* states no mechanic, and apply one rule to every entry of that shape.
- **Headline finding:** #228 is **misscoped, not wrong**. Its observation holds — Bright Light's glossary entry states no mechanic. Its inference does not: the glossary entry defines the term and points onward (*"Bright Light is normal illumination."* plus `See also "Playing the Game" ("Exploration")`), while **p. 11** carries the mechanic — *"Bright Light. Bright Light lets most creatures see normally."* The engine produces exactly that consequence.
- **The rule:** a shape's content is what the document states about it **anywhere**, not what its glossary paragraph states. The glossary is an index into the rules, not the boundary of one.
- **Consequence:** none of #228's three candidate answers is taken. The 211 denominator does not move, no vacuous-claim rule is introduced, and the ceiling is not disclosed as unreachable — because it is reachable.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. The official SRD v5.2.1 PDF at `/path/to/SRD_CC_v5.2.1.pdf` is the authority on every mechanic; no mechanic is inferred from memory (R31).
- **Stop conditions:** Stop and ask if applying the rule would require claiming a shape whose consequence the engine does not actually produce, or if a sweep result contradicts a labelled KTD below.
- **Tail ownership:** One PR. Issues filed for every question the rule surfaces and does not settle, before the PR merges.

---

## Problem Frame

`README.md` states the v1 bar as **"full SRD 5.2 coverage is the definition of done"**, and `tests/test_readme_reports_real_coverage.py` keeps the figure honest (R17). #228 asks whether that bar is reachable, because some glossary entries appear to state no mechanic at all — so nothing could ever "produce the consequence the entry states", and the shape could never be claimed.

The instance that raised it is Bright Light (p. 178), whose glossary body — minus its `See also` tail — is *"Bright Light is normal illumination."*

This matters beyond one row. If contentless entries can never be claimed, `211 of 211` is unreachable and the published figure quietly means something other than what it says.

---

## What the Sweep Found

The sweep extracted all **155** Rules Glossary entries with their body text (sliced between consecutive headings on each printed page, using the generator's own heading enumeration). Bodies were stripped of their `See also` tails, since a cross-reference states nothing itself, and ranked by remaining length.

**What 155 covers, and what it does not.** Those 155 headings are **135 inventory shapes plus the 20 `vocabulary` entries**. The inventory holds **211** shapes; the other **76** cite Equipment (17), Spell Descriptions (11), Monsters (8), Classes (8), Playing the Game (8), Feats (7), Gameplay Toolbox (6), Magic Items (5), Character Origins (4) and Character Creation (2) — and were **not** swept.

They do not need to be, and the reason is how they were found rather than an assumption about them. The generator says it: the Glossary is enumerated **mechanically**, by typography ("the only text set in GillSans-SemiBold at 12pt"), so it sweeps in definitional entries alongside mechanical ones — which is exactly why contentless entries exist in that population. Every other section has no such handle, so those shapes were found **editorially, by sweeping for mechanics**, each row carrying "a pattern that must match that spell's text in the PDF". A shape found by looking for a mechanic is contentful by construction. KTD5 is scoped accordingly.

**Finding 1 — the mechanic is on p. 11, not in the glossary entry.** Bright Light's mechanic is on p. 11, under *Vision and Light -> Light*:

> **Bright Light.** Bright Light lets most creatures see normally.

That is a mechanical statement: it says Bright Light imposes nothing. The engine produces it — `OBSCUREMENT_BY_LIGHT[BRIGHT]` is `Obscurement.NONE`, `can_see` returns `CAN_SEE`, and `perception_of` returns no modifier and says the light "obscures nothing".

The same page states Dim Light and Darkness mechanically too, which is why those two were already claimable from their glossary entries alone — the glossary happens to repeat their consequence and does not repeat Bright Light's.

**The tree argues the opposite, deliberately and in writing, in four places.** This plan overturns a recorded position rather than filling a gap, so the strongest statement of it is quoted here and each site is corrected in U2/U3 rather than left contradicting the claim beside it:

> **Bright Light** (p. 178) states no consequence at all — "normal illumination" — so there is nothing for the engine to be judged as producing. Claiming it would count a definition.
> — `tests/test_sight.py`, the docstring of `test_only_the_sight_shapes_whose_consequence_is_produced_are_claimed`

The others: that test's hard-coded claimed set (six ids, no `bright-light`); `test_bright_light_obscures_nothing_and_that_is_this_engines_word`; `core/sight.py`'s `OBSCUREMENT_BY_LIGHT` docstring; and the existing p. 178 clause rationale in `scripts/verify_d20_rules.py`. The last two are about **representation** — that `Obscurement.NONE` is this engine's word for an absence — and stay true; they gain p. 11 as the mechanic's home rather than being reversed.

**Finding 2 — the inventory was already inconsistent on exactly this question, in the opposite direction.** Contentlessness does not correlate with `implemented`:

| Entry | Glossary body (minus See-also) | Claimed? |
|---|---|---|
| `healing` (p. 182) | "Healing is how you regain Hit Points." | **yes** |
| `save` (p. 187) | "Save is another name for a saving throw." | **yes** |
| `damage` (p. 180) | "Damage represents harm that causes a creature or an object to lose Hit Points." | **yes** |
| `damage-types` (p. 180) | "Damage types have no rules of their own..." | **yes** |
| `bright-light` (p. 178) | "Bright Light is normal illumination." | **no** |
| `weapon-attack` (p. 191) | "A weapon attack is an attack roll made with a weapon." | **no** |

**`damage-types` is the second instance #228 named by name** — "Damage Types (p. 180) says types 'have no rules of their own'" — and it is already claimed. Note it sits on the same page as the distinct `damage` entry, which is how the two get confused.

`healing`, `save`, `damage` and `damage-types` are as definitional as Bright Light, and all four are claimed. They are claimed **correctly** — their mechanics live on p. 17 and in the D20 Test rules — which is the rule this plan states, already being followed without being written down. That is the same shape as decision 0030: the project had been answering a question consistently and had never named the answer.

**Finding 3 — the remaining short-and-unclaimed entries are correctly unclaimed, each for a reason that already exists in the tree.** Verified individually against the code: `bloodied`, `temporary-hit-points`, `occupied-space` and `unoccupied-space` have no implementation at all; `immunity` is partial and disclosed in `core/damage.py` (the entry covers "a damage type **or** a condition", and condition immunity is #18); `attitude` is #142. None of these is affected by the rule.

**Finding 4 — one genuine open question.** `weapon-attack` (p. 191) is "an attack roll made with a weapon", and `attack_resolver(weapon)` is exactly that — but `attack-roll` (p. 177) is already claimed, and claiming both may count one mechanic twice. The rule does not settle it; it is filed rather than decided in passing.

---

## Key Technical Decisions

**KTD1 — A shape's content is what the document states about it anywhere, not what its glossary entry states.** *(session-settled: user-approved — chosen over judging contentfulness from the glossary paragraph: the glossary is an index into the rules, and several entries are pure pointers whose mechanics live in "Playing the Game".)* The existing standard — *a shape is claimed when the engine produces the consequence its entry states* — is kept verbatim and its scope is made explicit: **"its entry" means the document's treatment of the term, not the glossary paragraph.**

**KTD1a — The rule is asymmetric: extra-glossary text may _supply_ a consequence, never _enlarge_ the bar.** Read symmetrically, KTD1 inverts itself and unclaims its own evidence. `damage`'s document-wide content is damage types, thresholds, Resistance and the whole of p. 17 — far more than the engine produces — so a symmetric rule would unclaim `damage`, `healing` and `save`, the very rows Finding 2 offers as proof the rule was already being followed. It would even unclaim `bright-light`: p. 11's **second** sentence is *"Even gloomy days provide Bright Light, as do torches, lanterns, fires, and other sources of illumination within a specific radius"*, and the engine models no light-source radii — `LitVolume` is a caller-authored box. So the bar for claiming remains **the consequence the shape's own entry states**; text elsewhere may supply that consequence when the entry only points at it, and a shape is never unclaimed for document text beyond its entry.

**KTD1b — A claim resting on text outside the entry must cite the page and assert the sentence.** Otherwise the published figure moves on unpinned reasoning, which is the drift toward vacuous claims KTD4 rejects. U2 does this for `bright-light`; the record states it as the standing obligation so the next such claim carries the same evidence.

**KTD2 — `bright-light` is claimed.** p. 11 states its consequence and the engine produces it. Coverage moves 95 -> 96 of 211.

**KTD3 — The 211 denominator does not move, and no entry moves to `vocabulary`.** Rejecting #228's option 2: the `vocabulary` category means "defined here, not an effect shape", and Bright Light *is* an effect shape whose rules sit elsewhere. Moving it would encode the very error this plan corrects, and would unclaim `healing`, `save` and `damage` besides.

**KTD4 — No vacuous-claim rule.** Rejecting #228's option 1: nothing is claimed for merely being modelled. `bright-light` is claimed because p. 11 states a consequence and the engine produces it, not because `LightLevel.BRIGHT` exists.

**KTD5 — The ceiling is not disclosed as unreachable.** Rejecting #228's option 3: it is reachable, so a disclosure would be false. **Scoped honestly:** the sweep covered the 135 Rules-Glossary shapes, where contentless entries can exist because that population was enumerated by typography. The other 76 were found by sweeping their sections *for mechanics*, so they are contentful by construction and are not at risk — stated as reasoning rather than left as an untested assumption (R32).

**KTD6 — Grounded in the PDF, read before deciding.** *(session-settled: user-directed — chosen over reasoning from general 5e knowledge: a wrong rule value is indistinguishable from a right one once inside a finished ruling (R31).)* Every claim above was read from `/path/to/SRD_CC_v5.2.1.pdf` during planning; p. 11's sentences become verifier clauses in U2.

**KTD7 — One rule, applied to all 155 glossary entries.** *(session-settled: user-directed — chosen over fixing `bright-light` alone: a rule applied to one entry is not a rule.)* The sweep *examined* all 155, the 41 tagged entries (`[Condition]`, `[Action]`, ...) included — they are unambiguously mechanical, which is a sweep result and not an exemption. Scope Boundaries excludes them from *re-classification*, not from examination. U1 records the outcome so the next sweep starts from the finding rather than repeating it.

---

## Scope Boundaries

**In scope:** the decision record; p. 11's three light sentences as verifier clauses; claiming `bright-light` in generator + data + `ENGINE_SHAPES`; the coverage figures; a guard that pins the finding; the build stamp.

### Deferred to Follow-Up Work

- **`weapon-attack` vs `attack-roll`** — whether naming a sub-case of an already-claimed mechanic is a second shape or a double count (Finding 4). File before merge.
- **`save` as a synonym** — p. 187 says "Save is another name for a saving throw". Under KTD1 it is claimed correctly, but a pure synonym may belong in `vocabulary`; that is a classification question KTD3 deliberately does not open. File before merge.

**Out of scope:** re-classifying any other entry; the 41 tagged entries (`[Condition]`, `[Action]`, ...), which are unambiguously mechanical; changing the `vocabulary` set.

---

## Implementation Units

### U1. Decision record 0033

- **Goal:** Record KTD1 and why #228's three options were all rejected.
- **Requirements:** R17, R31, R32.
- **Dependencies:** none.
- **Files:** `docs/decisions/0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md`, `docs/decisions/README.md`.
- **Approach:** Follow the house format exactly (Status / Settles / Requirements / Related; Context; Options considered; Decision; Why; Consequences; Evidence; **Status of implementation**). Relate to 0030 (a rule followed consistently and never named) and to #212/#225, which applied the standard this record scopes. Carry the sweep's four findings as Evidence, with the p. 11 quote.
- **Patterns to follow:** `docs/decisions/0031-*.md` and `0032-*.md` — both written this session, both carrying a clause table in **Status of implementation**.
- **Test scenarios:** `tests/test_decision_records.py` asserts every record carries a **Status of implementation** section and that the record count floor holds. Adding the file exercises both. Verify the record count assertion still passes with 33 records.
- **Verification:** `pytest tests/test_decision_records.py` green; the index row renders.

### U2. Assert p. 11's light sentences

- **Goal:** Make the evidence for KTD2 machine-checkable, so a future revision that reworded p. 11 goes red rather than leaving `bright-light` claimed against a sentence nobody re-read.
- **Requirements:** R31.
- **Dependencies:** none.
- **Files:** `scripts/verify_d20_rules.py`.
- **Approach:** Add three clauses on p. 11 — Bright Light "lets most creatures see normally", Dim Light "creates a Lightly Obscured area", Darkness "creates a Heavily Obscured area". The second and third are deliberate: they are the same rule the glossary states on pp. 181 and 180, and asserting both places is what shows the glossary repeats some consequences and not others, which is the whole of KTD1. Patterns match whitespace-normalised page text.
- **Also in this unit:** rewrite the **existing p. 178 clause's rationale**, which currently reads "it states no obscurement, which is why `Obscurement.NONE` is this engine's absence rather than a glossary term" — the position 0033 supersedes. The pattern stays; the rationale becomes: the glossary entry names no obscurement, and p. 11 states the consequence the engine produces. Leaving both would put two clauses about Bright Light in the same file arguing opposite conclusions.
- **Patterns to follow:** the `--- The nine sight shapes (#150, 0025 clause 5) ---` block, and the sight clauses added in #225. For the CI anchor, `tests/test_hazards.py::test_the_prone_qualifier_is_asserted_against_the_document` — a presence check that reads the verifier's source, so CI can tell a hand-run clause was deleted even though it cannot run the verifier. Add one for the p. 11 Bright Light clause.
- **Test scenarios:** run the verifier against the PDF and confirm the clause count rises by three and all pass. Corrupt the Bright Light pattern to the plausible-wrong value — "lets most creatures see in Dim Light" — and confirm it goes red.
- **Execution note:** the verifier is hand-run and needs the PDF; CI has no copy. `scripts/prove_guard_red.sh` runs pytest and cannot drive it, so prove the corruption on a **copy** of the script and delete the copy afterwards.
- **Verification:** `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` reports all clauses verified; the corrupted copy reports the Bright Light clause unmatched.

### U3. Claim `bright-light`, and correct the six sites that argue against it

- **Goal:** Move the shape to implemented in the generator, the shipped data and `ENGINE_SHAPES` together — and correct every site that records the superseded reasoning, including the exact-set assertion that would otherwise turn the suite red.
- **Requirements:** R17.
- **Dependencies:** U2 (the clause must exist before the claim rests on it).
- **Files:** `scripts/derive_effect_shapes.py` (`KINDS`), `src/srd_rules_engine/data/effect_shapes.json`, `src/srd_rules_engine/core/inventory.py` (`ENGINE_SHAPES`), `tests/test_sight.py`, `src/srd_rules_engine/core/sight.py`.
- **Approach:** `ENGINE_SHAPES["bright-light"]` resolves to `core.sight.OBSCUREMENT_BY_LIGHT` — the mapping that produces "obscures nothing" — matching how `darkness` is claimed. (Not `dim-light`, which resolves to `core.state.EncounterState.perception_of`.) Six sites carry the superseded reasoning and all six are corrected here:
  1. `inventory.py`, the `environment` block: "Bright Light and Dim Light stay unclaimed, and the same test is why".
  2. `inventory.py`, the #138 block: "`bright-light` still is not here: p. 178 states no consequence to produce".
  3. `tests/test_sight.py`: the **hard-coded claimed set** in `test_only_the_sight_shapes_whose_consequence_is_produced_are_claimed` — an exact-set assertion of six ids that goes red the moment `bright-light` is claimed. **This is the gate-breaker.**
  4. The same test's docstring: "Six resolve" -> "Seven", and the Bright Light bullet moves from the unclaimed list to the claimed one, citing p. 11.
  5. `tests/test_sight.py::test_bright_light_obscures_nothing_and_that_is_this_engines_word` — **not** reversed: `Obscurement.NONE` really is this engine's word for an absence. It gains p. 11 as the mechanic's home so a reader is not left thinking p. 178 is the whole story.
  6. `core/sight.py`: the `OBSCUREMENT_BY_LIGHT` docstring, same treatment as (5), and `SIGHT_VERIFICATION.reference` gains p. 11 — the subsystem's verification now rests partly on a page outside the Rules Glossary.
- **Patterns to follow:** the `environment` block added in #212 and extended in #225 — it already carries per-shape reasoning in comments.
- **Test scenarios:** `test_every_engine_shape_is_marked_implemented` passes (data agrees with `ENGINE_SHAPES`); `test_the_glossary_claims_agree_with_the_generator_that_writes_them` passes (`KINDS` agrees with the data); `tests/test_sight.py` passes with the seven-shape set; re-running the generator against the PDF reproduces the shipped file byte-for-byte and reports 96 implemented.
- **Verification:** all three guards green; `coverage_report()` reports 96/211.

### U4. Pin the finding so the next sweep starts from it

- **Goal:** Make KTD1 checkable rather than only recorded, and stop the inventory drifting back toward judging contentfulness from the glossary paragraph.
- **Requirements:** R17, R32.
- **Dependencies:** U3.
- **Files:** `tests/test_effect_shape_inventory.py`.
- **Approach:** A test naming the entries whose glossary body is definitional but which are claimed because the document states their mechanic elsewhere — `bright-light`, `healing`, `save`, `damage`, `damage-types` — asserting each is claimed and carrying the rule in its docstring with the p. 11 quote. `damage-types` earns its place: it is the one other instance #228 named. This is the finding-2 inconsistency turned into a guard: before this plan the set was split for no stated reason.
- **Patterns to follow:** `tests/test_sight.py::test_only_the_sight_shapes_whose_consequence_is_produced_are_claimed` — same shape, same purpose, enumerates and explains rather than computing.
- **Test scenarios:** the five named shapes are all `implemented=True`; unclaiming any one goes red. Include the counter-set — `bloodied`, `temporary-hit-points`, `occupied-space` — asserted **unclaimed**, so the test fails in both directions and cannot be satisfied by claiming everything.
- **Execution note:** prove red both ways — unclaim `bright-light`, then claim `bloodied` — since a one-directional guard here would license exactly the over-claiming KTD4 rejects.
- **Verification:** `pytest tests/test_effect_shape_inventory.py` green; both corruptions red.

### U5. Coverage figures, build stamp, and the issue's answer

- **Goal:** Publish the moved figure and the reasoning, and close #228 with the correction rather than with one of its options.
- **Requirements:** R17.
- **Dependencies:** U1-U4.
- **Files:** `README.md`, `src/srd_rules_engine/__init__.py`, `tests/test_readme_reports_real_coverage.py`.
- **Approach:** name every site, because the README carries the figure in three places and the prose in a fourth:
  1. The coverage sentence: `95 of 211` -> `96 of 211`, **and its remainder `The other 116` -> `115`**.
  2. The v1.0 milestone row: `95 of 211 effect shapes` -> `96`, and `6 of 10` -> `7 of 10`.
  3. **The milestone row's prose**, which no guard checks and which currently asserts the error this plan corrects: *"The four that remain each state something nothing consumes — Bright Light's absence of any consequence, Truesight's third piercing, Tremorsense's pinpointing, and Telepathy's languages"*. Three remain; the Bright Light clause is replaced by a sentence recording that p. 11 states its consequence.
  4. `tests/test_readme_reports_real_coverage.py` pins **three** things, not one: `_slice(("sense","environment")) == (6, 10)` -> `(7, 10)`; the literal `"6 of 10"` row string -> `"7 of 10"`; and the five-category slice `(9, 23)` -> `(10, 23)`, whose derivation comment names its history and gains Bright Light (#228) as the increment.
  5. `__version__` to the next `mmddyyyy.x`, and both README stamps with it.

  The build line leads with the correction — #228 was misscoped, and the mechanic is on p. 11 — not with the count.
- **Patterns to follow:** the build lines from #212, #225.
- **Test scenarios:** `tests/test_build_stamp.py` green (all three stamps agree); `tests/test_readme_reports_real_coverage.py` green (every published figure matches a real inventory slice); `scripts/check_build_stamp_advanced.py main` reports advanced.
- **Verification:** full gate green; the stamp guard passes against `main`.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy` — all four, per `AGENTS.md`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses verified.
- `python scripts/derive_effect_shapes.py /path/to/SRD_CC_v5.2.1.pdf` then `git diff --stat` — regeneration is a no-op.
- `scripts/prove_guard_red.sh` for **U4 only**, both directions. It runs `python -m pytest "$@"`, so it cannot drive the hand-run verifier, and it corrupts the tracked file in place.
- **U2 by hand:** copy `scripts/verify_d20_rules.py` aside, corrupt the copy's Bright Light pattern to "lets most creatures see in Dim Light", run the copy against the PDF, confirm the clause reports unmatched, delete the copy. Never edit the tracked script to prove this.
- `scripts/prove_against_base.sh main tests/test_effect_shape_inventory.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- Decision record 0033 exists, is indexed, and its **Status of implementation** names what landed.
- Three p. 11 clauses assert in the verifier, the existing p. 178 rationale is rewritten, a CI presence check anchors the new clause, and the Bright Light clause is proved red on a copy.
- `bright-light` claimed in generator, data and `ENGINE_SHAPES`; regeneration byte-identical.
- U4's guard proved red in both directions.
- Coverage published as 96 of 211 and 7 of 10; build stamp advanced; full gate green.
- Both deferred questions filed as issues, with their numbers written beside the entries in the record.
- #228 closed with the correction — the observation held, the inference did not, and the glossary entry is not the shape's boundary — rather than with one of its three options.

---

## Open Questions

- **Does `weapon-attack` name a second shape or double-count `attack-roll`?** Deferred and filed (Scope Boundaries). Not blocking: the rule is stated without it.
- **Is a pure synonym (`save`) vocabulary?** Deferred and filed. KTD3 keeps it claimed for now; changing it is a classification move this plan deliberately does not make.

## Risks

- **Claiming `bright-light` looks like the vacuous claim KTD4 rejects.** A PDF-text clause alone cannot answer this: for a *null* consequence ("imposes nothing"), a produced result and a merely-modelled term are behaviourally identical, so U2 pins only the document side. The discriminating evidence is **engine-side and already in the tree** — `perception_of` reports Bright Light "obscures nothing", and `tests/test_perception.py::test_bright_light_obscures_nothing` plus `tests/test_sight.py` go red when `OBSCUREMENT_BY_LIGHT[BRIGHT]` is corrupted. The record cites that pair, document side and engine side together; neither alone separates KTD2 from KTD4.
- **U4's guard could ossify a wrong classification.** Mitigated by the counter-set: it asserts unclaimed shapes too, so it fails if the inventory drifts either way.

## Sources & Research

- SRD v5.2.1 PDF, p. 11 (*Vision and Light -> Light*), pp. 177-191 (Rules Glossary), read during planning.
- Sweep of all 155 glossary entries with bodies sliced between headings; bodies stripped of `See also` tails and ranked by length.
- `scripts/derive_effect_shapes.py` (`KINDS`, the `vocabulary` category and its 20 members), `src/srd_rules_engine/core/inventory.py`, `src/srd_rules_engine/core/sight.py`, `src/srd_rules_engine/core/damage.py`.
- Prior applications of the standard this record scopes: PR #212, PR #225.
