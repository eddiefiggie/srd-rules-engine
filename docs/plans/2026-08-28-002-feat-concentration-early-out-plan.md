---
title: An effect ends when its creator's Concentration does - Plan
type: feat
date: 2026-08-28
topic: concentration-early-out
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/240
---

# An effect ends when its creator's Concentration does - Plan

## Goal Capsule

- **Objective:** Build [0037](../decisions/0037-a-concentration-is-an-early-out-not-an-axis.md)
  clauses 1, 2, 3, 5 and 6, so that p. 179's first consequence — "If the effect's creator loses
  Concentration, the effect ends" — actually happens.
- **Headline finding:** **clauses 3 and 4 of the record disagree, and clause 3 is the one that
  is wrong.** Clause 3 says retirement happens in `EncounterState.with_concentration_ended`.
  Clause 4 shipped in #238 and ends Concentration in `Combatant.__post_init__`, which
  `with_condition` and `with_death` reach through `replace` and which **never calls**
  `with_concentration_ended`. So two of the four routes that end Concentration would retire
  nothing, and the two that would are the two a test is most likely to cover.
- **The shape:** the same move that fixed #238 one level up. Retirement is a **whole-state
  invariant** in `EncounterState.__post_init__`, not a step inside one transition — because
  "where the Concentration ends" turned out to be more than one place, and a rule that has to
  be remembered at three call sites is 0036 clause 6's argument for a shared helper made
  again and lost.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. The official SRD v5.2.1 PDF at
  `/path/to/SRD_CC_v5.2.1.pdf` is the authority on every mechanic (R31). p. 179's entry was
  read whole for 0037 and is not re-litigated here.
- **Stop conditions:** Stop and ask if retiring an effect turns out to need a roll (R1), if the
  invariant would have to read prose to decide what a Concentration sustains (R20), or if the
  walk cannot be made to terminate in one pass.
- **Tail ownership:** One PR. 0037 is amended to say what actually landed, and every clause it
  specifies that this PR does not build is filed before the PR merges.

---

## Problem Frame

p. 179, first paragraph:

> Some spells and other effects require Concentration to remain active, as specified in their
> descriptions. **If the effect's creator loses Concentration, the effect ends.**

0037 settled the shape and built none of it except the materialised end. `Duration` carries
`kind`, one expiry point, a `save` early-out and the span as stated — and nothing that says
"while this creature concentrates". So a Concentration can end today and every condition it
was holding up stays exactly where it is.

---

## What the Investigation Found

**Finding 1 — the record contradicts itself, and this plan is where that surfaces.** 0037
clause 3:

> Retirement happens where the Concentration ends […] `EncounterState.with_concentration_ended`
> already exists and is the place.

0037 clause 4, built in #238:

> The end of Concentration is materialised in state, never derived.

Clause 4 landed in `Combatant.__post_init__`, which is reached by `replace` — so
`with_condition` and `with_death` end a Concentration **without going through**
`with_concentration_ended`. Retiring only in that method covers the failed damage save and the
voluntary end, and silently misses Incapacitated and death. The record was written before
clause 4 had an implementation, and clause 3 named the only place that then existed.

**Finding 2 — `retirable` currently answers the wrong question for this case.** It reads
`kind is not UNTIL_REMOVED`, and `Conditions.unretirable()` reports anything failing it as a
condition "this engine cannot end on its own". p. 179 says "**If** the effect has a maximum
duration", so a Concentration spell that states none is `UNTIL_REMOVED` *and* perfectly
retirable — the engine ends it the moment Concentration drops. Left alone, the engine would
disclose that it cannot end an effect it can, which 0037's Option 5 rejected as a wrong
disclosure being worse than a missing feature.

**Finding 3 — nothing needs to know which spells require Concentration, and that is the
point.** p. 179 puts it "in their descriptions", so the imposing effect states the duration and
the engine never infers it (0037 clause 5, R31). No spell list ships here, and this change adds
no place one could be added by accident: the field is set by whoever built the `Duration`.

**Finding 4 — the walk is bounded and cannot cascade.** Retiring a condition cannot itself end
a Concentration: `Conditions.without` removes conditions, and `Combatant.__post_init__` only
*ends* Concentration when a breaking condition is **present**. So one pass reaches a fixed
point, and the invariant does not need to iterate to convergence. Worth checking rather than
assuming, because a self-triggering invariant in a constructor is an infinite recursion.

---

## Key Technical Decisions

**KTD1 — A plain field, not a one-field wrapper.** `Duration.concentration_of: str | None`,
beside `save: SaveEnds | None`. `SaveEnds` is a type because p. 63 states two values per effect
— an ability and a DC — and they travel together. p. 179 states one: whose Concentration. A
dataclass holding a single string is a box, and its only invariant (non-empty) has a home
already in `Duration.__post_init__`, where every other field's invariant lives.

**KTD2 — The invariant lives in `EncounterState.__post_init__`, not in one transition.**
Finding 1. This is #238's lesson at the state level: the fix that survives is the one every
writer passes through rather than the one every writer must remember. `_evolve` is documented
as "the only way to produce a successor", and construction is the other way in — a
hand-built `EncounterState` gets the same treatment, which is the case a per-transition hook
would miss.

**KTD2a — Rejected: retire in `with_concentration_ended` and route the other two through it.**
Three call sites, and 0036 clause 6 already argued this exact point for the loop's drain:
"three copies is how one gets missed". The one that would be missed here is death, which has no
caller to make the omission obvious.

**KTD2b — Rejected: derive `held` from whether the sustainer is concentrating.** #238 is four
days old and says why. A derivation is also impossible here without giving `Conditions` a view
of the whole encounter, which would invert the containment.

**KTD3 — `retirable` becomes a two-part question, and `unretirable()` follows it.** Finding 2.
A duration is retirable if its kind is retirable **or** it carries a concentration early-out.
`derivation()` says both halves, because R5 wants the record to show what the engine was going
on and "ends when Bree's Concentration does" is the whole reason an `UNTIL_REMOVED` span is
not permanent.

**KTD4 — A sustainer that is absent is not concentrating.** A duration naming a creature the
encounter does not contain sustains nothing this engine can see, and leaving the effect up
would hold it on nothing. Retired, and stated rather than left to be discovered.

**KTD5 — Clause 6's disclosure is prose, because there is nothing to enumerate.** What this
engine can retire is a condition with a duration. A Concentration spell that also creates an
area, an obstruction or a summoned creature has parts the engine does not model *at all*, so
there is no list of them to report — `Conditions.unretirable()` can only speak about conditions
that exist. R32 discloses the boundary in the module that owns it, and a guard asserts the
disclosure is still there.

**KTD6 — 0037 is amended, not superseded.** Clause 3 named a place; the decision it encodes —
retirement is deterministic bookkeeping that happens when Concentration ends, and needs no roll
— is unchanged and correct. **Status of implementation** is where the correction goes, per
`AGENTS.md`, and the record gets the note rather than a second record.

---

## Scope Boundaries

**In scope:** the `Duration` field and its invariants; `retirable`, `unretirable()` and
`derivation()`; the retirement query on `Conditions`; the whole-state invariant; the R32
disclosure and its guard; 0037's amendment; guards and their proofs; the build stamp.

### Deferred to Follow-Up Work

- **A declaration that starts concentrating, and the replacement rule.**
  [#235](https://github.com/eddiefiggie/srd-rules-engine/issues/235) items 1 and 2. **Already
  filed** — do not re-file. This change is what gives them somewhere to hang an effect.
- **Nothing in the SRD content set states a concentration duration yet**, because no spell
  data ships (R31). The field is exercised by tests and by whatever ruleset a consumer brings.
  That is the same state `SaveEnds` has been in since #18 and is **not** filed: it is a
  consequence of shipping no spell content, not an omission.

**Out of scope:** which effects require Concentration (p. 179 puts it in the description, R31);
anything that would let the engine retire a part of an effect it does not model.

---

## Implementation Units

### U1. The early-out exists and is honest about itself

- **Goal:** 0037 clauses 1 and 2, plus Finding 2's correction.
- **Requirements:** R5, R31.
- **Dependencies:** none.
- **Files:** `src/srd_rules_engine/core/duration.py`.
- **Approach:** `concentration_of: str | None = None` beside `save`; `__post_init__` refuses an
  empty string; `retirable` becomes kind-or-early-out; `derivation()` states both halves.
- **Test scenarios:** a span with a concentration early-out reports both in its derivation; an
  `UNTIL_REMOVED` duration carrying one is **retirable**; one carrying none still is not; an
  empty creature id is refused.
- **Verification:** `pytest`, `mypy` green.

### U2. The retirement query

- **Goal:** 0037 clause 2's read half — which of a creature's conditions a given Concentration
  sustains.
- **Requirements:** R19.
- **Dependencies:** U1.
- **Files:** `src/srd_rules_engine/core/conditions.py`.
- **Approach:** `sustained_by(creator_id) -> frozenset[Condition]`, the third sibling of
  `expired_after` and `expired_by` and a read in the same way — it answers and changes nothing.
- **Test scenarios:** it names only conditions whose duration carries that creature; a
  condition sustained by a *different* caster is not named; an implied condition is not named,
  because implication has no duration of its own.
- **Verification:** `pytest` green; asking twice gives the same answer.

### U3. The invariant

- **Goal:** 0037 clause 3, at the level Finding 1 says it has to live.
- **Requirements:** R1, R19.
- **Dependencies:** U2.
- **Files:** `src/srd_rules_engine/core/state.py`.
- **Approach:** `EncounterState.__post_init__` retires every condition sustained by a creature
  that is not concentrating, in one pass (Finding 4). No roll, no ruling, no ledger entry —
  the same standing as `advanced_turn` retiring a round count.
- **Test scenarios:** the failed damage save ends the spell **and** drops the condition it held
  up; so does the voluntary end; **so does Incapacitated, and so does death** — the two routes
  that never touch `with_concentration_ended` and the whole reason for the shape; a second
  caster's identical condition survives; a condition with no early-out survives; the walk
  terminates.
- **Execution note:** write the Incapacitated and death cases first. They are the two a
  `with_concentration_ended`-only implementation passes every other test without.
- **Verification:** `pytest` green; no new `generation` movement beyond the transition's own.

### U4. Disclose what "the effect ends" does not reach

- **Goal:** 0037 clause 6, R32.
- **Requirements:** R32.
- **Dependencies:** U3.
- **Files:** `src/srd_rules_engine/core/duration.py`, `tests/`.
- **Approach:** A named section in the module docstring saying that retirement reaches
  conditions with durations and nothing else, because the other parts of a spell are not
  modelled. A guard asserts the disclosure is present, the way the verifier's clauses are
  anchored for CI.
- **Test scenarios:** the disclosure exists; corrupting it goes red.
- **Verification:** `pytest` green; guard proved red.

### U5. Amend 0037, figures, and the build stamp

- **Goal:** Say what landed, and publish it.
- **Requirements:** R17.
- **Dependencies:** U1-U4.
- **Files:** `docs/decisions/0037-*.md`, `README.md`, `src/srd_rules_engine/__init__.py`.
- **Approach:** Clause 3's row records that the place named turned out to be one of four, and
  what replaced it. **Coverage does not move** — `concentration` is claimed and correct
  already; this makes p. 179's first sentence true rather than the figure larger.
- **Test scenarios:** `tests/test_decision_records.py`, `tests/test_build_stamp.py`,
  `tests/test_readme_reports_real_coverage.py`; `check_build_stamp_advanced.py main`.
- **Verification:** full gate green.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy` — all four, per `AGENTS.md`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses verified. No
  new clause: p. 179's sustaining sentence is already asserted, and this builds it rather than
  reading it again.
- `scripts/prove_guard_red.sh` for U1's, U3's and U4's guards.
- `scripts/prove_against_base.sh main tests/test_condition_duration.py tests/test_concentration_save.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- A `Duration` can say whose Concentration sustains it, and refuses an empty answer.
- An `UNTIL_REMOVED` span carrying the early-out reports as **retirable**, and its derivation
  says why.
- All four routes that end Concentration retire what it sustained, including the two that never
  call `with_concentration_ended`.
- A second caster's effects are untouched, and so is anything with no early-out.
- The R32 boundary is disclosed and guarded.
- 0037's clause 3 records where retirement actually went, and why.
- Coverage unchanged; build stamp advanced; full gate green.
- #240 closed; #235 items 1 and 2 left open and unblocked.

## Open Questions

- **None.** Finding 1's contradiction is resolved by KTD2 rather than deferred, and KTD6 says
  where the correction is written down.

## Risks

- **`EncounterState.__post_init__` runs on every transition**, and this repository has none
  today. A constructor that removes conditions is powerful, and a future bug there would be
  hard to attribute. Mitigated by keeping it to one pass, one rule, and an early exit when no
  duration carries an early-out — which is every state in the engine until a consumer ships a
  Concentration spell.
- **A condition sustained by a creature not in the encounter is retired** (KTD4). If some later
  feature builds an `EncounterState` incrementally, effects could retire during construction.
  Nothing does today: `EncounterState.new` takes every combatant at once.
- **The field is unexercised by shipped content**, so the first real consumer is also the first
  test of the ergonomics. Accepted: the alternative is shipping spell data, which R31 forbids.

## Sources & Research

- SRD v5.2.1 PDF, p. 179 (*Concentration*, first paragraph) — read whole for 0037.
- `core.duration` (`Duration`, `SaveEnds`, `DurationKind`, `retirable`, `derivation`), and its
  module docstring's "a duration is a span with optional early-outs".
- `core.conditions` (`Conditions.durations`, `expired_after`, `expired_by`, `saves_due_after`,
  `without`, `unretirable`), `core.state` (`Combatant.__post_init__`, `_evolve`,
  `with_concentration_ended`, `with_condition`, `with_death`, `_retiring_conditions_after`).
- [0037](../decisions/0037-a-concentration-is-an-early-out-not-an-axis.md) clauses 1-6,
  [0021](../decisions/0021-a-round-is-six-seconds.md) clauses 3 and 6,
  [0036](../decisions/0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md) clause 6.
