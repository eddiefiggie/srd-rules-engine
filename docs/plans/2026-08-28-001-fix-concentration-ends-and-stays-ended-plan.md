---
title: Concentration ends, and stays ended - Plan
type: fix
date: 2026-08-28
topic: concentration-ends-and-stays-ended
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/238
---

# Concentration ends, and stays ended - Plan

## Goal Capsule

- **Objective:** Make p. 179's word *ends* true. Concentration is spent by an event, not
  suspended while a condition happens to hold, and every route that ends it says so in state.
- **Headline finding:** the engine **suspends** where the document **ends**.
  `Concentration.after_conditions` is a pure derivation applied at read time and nothing ever
  writes the field, so when Incapacitated lifts the spell comes back
  ([#238](https://github.com/eddiefiggie/srd-rules-engine/issues/238)). It is not only a
  read: `with_damage` decides whether a save is owed through the same derivation — by design,
  so state and the surface agree — so both are wrong together, and the engine compels a
  Constitution save to maintain a spell p. 179 already ended. A save that can **fail**, so
  the wrong outcome arrives through the one adjudication entry point carrying a Ruling, a
  seed and a ledger entry, indistinguishable from a right one.
- **The shape:** **materialise, then delete the derivation.** The end of Concentration is a
  state change and belongs where the state change happens — 0023 clause 5's principle, which
  0036 clause 2 already applied to the damage half. One shape covers three of p. 179's four
  routes, which is why they are one change rather than three.
- **Secondary finding:** the derivation cannot be *fixed*, only removed. A derivation
  recomputes a fact from present state; p. 179 states an **event**. No amount of care makes a
  function of the current conditions remember that a condition arrived and departed.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. The official SRD v5.2.1 PDF at
  `/path/to/SRD_CC_v5.2.1.pdf` is the authority on every mechanic; no mechanic is inferred
  from memory (R31). p. 179's entry was read whole for this plan.
- **Stop conditions:** Stop and ask if materialising requires a read-surface call to mutate
  (R19), or if ending the sustained *effects* turns out to be unavoidable here — that is
  [#239](https://github.com/eddiefiggie/srd-rules-engine/issues/239)'s gate and is designed,
  not built, by this change.
- **Tail ownership:** One PR. The gate closes by producing decision record 0037; every clause
  that record specifies and this PR does not build is filed before the PR merges.

---

## Problem Frame

p. 179, *Concentration*, read whole from the PDF:

> Some spells and other effects require Concentration to remain active, as specified in their
> descriptions. If the effect's creator loses Concentration, the effect ends. […] The creator
> can end Concentration at any time (no action required). The following factors break
> Concentration.
>
> **Another Concentration Effect.** You lose Concentration on an effect the moment you start
> casting a spell that requires Concentration or activate another effect that requires
> Concentration.
>
> **Damage.** […]
>
> **Incapacitated or Dead.** Your Concentration ends if you have the Incapacitated condition
> or you die.

Four ways it goes, plus the voluntary end. #215 built **Damage**. Of the rest:

| Route | Today | This plan |
|---|---|---|
| Damage | built (#215, 0036) | untouched |
| Incapacitated | **derived at read time — suspends, does not end** | materialised |
| Dead | not reachable: death is not one of the fifteen conditions | materialised |
| Voluntary end | nothing calls `Concentration.ended` | an affordance |
| Another Concentration Effect | nothing can start concentrating | **not this plan** (#235) |

---

## What the Investigation Found

**Finding 1 — the bug, reproduced rather than reasoned about.** Three lines of the public API:

```python
read(state, "mage").situation.concentrating_on  # 'bless'
state = state.with_condition("mage", Condition.INCAPACITATED)
read(state, "mage").situation.concentrating_on  # None
state = state.with_condition_ended("mage", Condition.INCAPACITATED)
read(state, "mage").situation.concentrating_on  # 'bless'  <- p. 179 ended it
```

**Finding 2 — and it reaches an outcome, which is what raises the severity.** `with_damage`
asks the same derivation, deliberately (0036 clause 2's comment says so: "so this agrees with
the read surface about who is concentrating"). The agreement holds and both are wrong:

```python
state.with_damage("mage", 12).concentration_saves_owed
# while Incapacitated:  ()                                 correct
# after it lifts:       (ConcentrationDebt('mage', 12),)   a save for a spell that is over
```

R1 says the one entry point is the only thing that produces an outcome. It did — the save is
rolled, recorded and narratable. The invariant held and the *input* was wrong, which is the
failure mode the ledger cannot catch.

**Finding 3 — the derivation was right for the case it was made against, and that is why it
is worth recording rather than simply deleting.** `e2bd196`'s reasoning: nothing writes the
field when a condition lands, so a surface reporting it raw would say a spell is still up
after the condition that broke it. True, and the fix chosen was the one that could be made
without touching any writer. The direction it cannot cover is the one the document actually
states: **a derivation recomputes; an event is spent.**

**Finding 4 — the Damage route got this right by accident, and its shape is the answer.** A
failed save applies `EffectKind.CONCENTRATION_ENDED`, which materialises the end through
`with_concentration_ended`. Only the condition route derives. So the fix is not a new idea —
it is the shape already in the tree, applied to the three routes that skipped it.

**Finding 5 — death is not a condition, so `after_conditions` structurally cannot see it.**
`EncounterState.with_death` sets `death_saves.dead` and applies no conditions at all. A
player character dying is usually Unconscious and so Incapacitated by implication, but p. 17
kills a monster outright — "a monster dies the instant it drops to 0 Hit Points" — and it
never acquires the condition. Feeding death *into* `after_conditions` would widen a
conditions function to take a fact that is not a condition; ending it where death happens is
0023 clause 5 unchanged.

**Finding 6 — the voluntary end is not a declaration.** p. 179: "The creator can end
Concentration at any time **(no action required)**." A declaration slot is where an agent
proposes something the rules may refuse; this is a thing the document gives outright and
costs nothing. `Concentration.ended` is already the whole rule, and what is missing is a
state transition a driver can call.

---

## Key Technical Decisions

**KTD1 — Materialise the end, and delete the derivation in the same change.**
*(session-settled: user-approved scope — the small half of #235, plus the bug scoping it
surfaced.)* Leaving the derivation beside a materialised field is worse than either alone:
two answers to "who is concentrating", disagreeing whenever a writer is added and nobody
updates the other. `after_conditions` goes; `with_condition` and `with_death` write the field;
the read surface reports what is stored.

**KTD1a — Rejected: keep the derivation and also write the field.** It is the smaller diff
and it is the shape 0035 refuses — two names for one thing, drifting apart on schedule.

**KTD1b — Rejected: fix the derivation to remember.** It cannot. A function of the present
conditions has no access to the fact that a condition arrived and departed, and giving it one
means storing the event, which is materialising with extra steps.

**KTD2 — `Concentration.after_conditions` is removed, not deprecated.** It is not on any
stability tier — `Concentration` itself is not in `COMMITTED` — and its only callers are
`core.state`, `core.read_surface` and its own tests. 0018 clause 4 governs removal from the
committed surface and is not engaged. Leaving it as a trap for the next writer is the cost
0024 declined to pay for `CHANGELOG.md`.

**KTD3 — Incapacitated ends it where the condition lands.** `with_condition` materialises
when the applied condition's effects carry `concentration_broken`, which keeps the "which
conditions qualify" question in `core.conditions` where it already lives — one rule, one
place, exactly as `after_conditions` read it.

**KTD4 — Death ends it in `with_death`.** Finding 5. p. 179's "or you die" is a state change
resolving where the state change resolves, and it needs no roll.

**KTD5 — The voluntary end is a state transition, not a declaration and not a legal action.**
Finding 6. `EncounterState.with_concentration_ended` already exists and is exactly this; what
this plan adds is that a driver may call it and the read surface says so. **No `LegalAction`
is enumerated for it**, because the read surface enumerates what the creature may *do on its
turn* and this costs no action and is not turn-bound.

**KTD6 — The sustained effects are designed and not built.** p. 179's "the effect ends" is
[#239](https://github.com/eddiefiggie/srd-rules-engine/issues/239)'s gate, settled by record
0037 in this change and built under a follow-up. Ending Concentration correctly is a
prerequisite for retiring what it sustained, not the same work — and #238 is live on `main`
today, which is the argument for not waiting.

**KTD7 — Grounded in the PDF, read whole.** *(session-settled: user-directed standing rule.)*
The entry was read from `/path/to/SRD_CC_v5.2.1.pdf` rather than recalled, which is how the
"or activate another effect that requires Concentration" clause — absent from the engine's
paraphrase of the replacement rule — was noticed and recorded for #235.

---

## Scope Boundaries

**In scope:** the gate's decision record 0037; materialising the end on the Incapacitated,
death and voluntary routes; removing `after_conditions` and the derived read; the read surface
reporting the stored value; a verifier clause for p. 179's "or you die"; guards and their
proofs; the build stamp.

### Deferred to Follow-Up Work

- **Starting to concentrate, and the replacement rule.** #235 items 1 and 2, unchanged by
  this plan and still blocked on #239. **Already filed** — do not re-file.
- **Retiring the effects a Concentration sustained.** Designed by 0037, built by nobody yet.
  **File before merge** and put the number beside the clause in 0037's *Status of
  implementation*, because a gate issue closes when the record lands and the unbuilt half
  would then be tracked by nothing.
- **"Or activate another effect that requires Concentration"** — the second half of p. 179's
  replacement clause, which the engine's paraphrase drops. Belongs with #235 item 2.
  **File before merge**, because it is a rule the document states and the tree does not, and
  a note in a plan is not a queue.

**Out of scope:** slots, preparation and components (#19); anything that decides *which*
effects require Concentration, which p. 179 puts in the effect's description and R31 forbids
inventing.

---

## Implementation Units

### U1. Decision record 0037, closing the gate

- **Goal:** Settle #239 — how a Concentration holds the effects it sustains, and what retires
  them — so #235 items 1 and 2 are unblocked.
- **Requirements:** R1, R31, R5.
- **Dependencies:** none.
- **Files:** `docs/decisions/0037-*.md`, `docs/decisions/README.md`.
- **Approach:** Lead with **the sentence that has no mechanism**, not with the options. The
  decisive argument is that the obvious answer — a fifth `DurationKind` — loses p. 179's own
  third sentence, because `Duration` sets one expiry point "never both" and a Concentration
  spell states a maximum duration *and* the early-out. Related: 0013 (effect shapes), 0020
  and 0021 (the two axes and one expiry point), 0023 clause 5, 0036.
- **Test scenarios:** `tests/test_decision_records.py`.
- **Verification:** `pytest tests/test_decision_records.py` green; index row renders; every
  unbuilt clause carries an issue number.

### U2. The end is materialised, and the derivation goes

- **Goal:** p. 179's *ends*, in state, on every route that reaches it.
- **Requirements:** R19, R31.
- **Dependencies:** U1 (for the reasoning it records), not blocking.
- **Files:** `src/srd_rules_engine/core/spellcasting.py`, `core/state.py`, `core/read_surface.py`.
- **Approach:** `with_condition` writes `Concentration()` when the applied condition's
  effects carry `concentration_broken`; `with_death` writes it too; `after_conditions` is
  deleted along with the derived read. `with_damage` then reads the stored field, and the
  comment explaining why it derived is replaced by one saying why it no longer needs to.
- **Test scenarios:** the reproduction from Finding 1, asserted the other way — the spell does
  **not** come back when Incapacitated lifts; a monster killed outright by `with_death` is not
  concentrating; a character reduced to 0 is not either; the read surface still does not
  mutate (R19); no debt is owed after the condition lifts (Finding 2).
- **Execution note:** the lifted-condition case is the whole bug. Write it first, watch it
  fail against `main`, then fix.
- **Verification:** `pytest`, `mypy` green; no caller of `after_conditions` remains.

### U3. The voluntary end reaches a driver

- **Goal:** p. 179's "(no action required)", callable.
- **Requirements:** R18, R19.
- **Dependencies:** U2.
- **Files:** `core/state.py`, `core/read_surface.py`, `adapters/surface.py`.
- **Approach:** `with_concentration_ended` is already the transition (0036). This unit gives
  it a docstring that states p. 179's sentence as its licence rather than only its mechanism,
  and confirms the read surface reports what a driver needs to decide — no `LegalAction`
  (KTD5).
- **Test scenarios:** ending voluntarily leaves the creature concentrating on nothing and
  costs no action budget; it is not offered as a legal action; it is idempotent.
- **Verification:** `pytest` green; `test_every_read_surface_field_reaches_a_transport` green.

### U4. Assert p. 179's death clause, and guard what was proved

- **Goal:** Pin the sentence and make the invariants checkable.
- **Requirements:** R31, R32.
- **Dependencies:** U2, U3.
- **Files:** `scripts/verify_d20_rules.py`, `tests/test_spellcasting.py`.
- **Approach:** p. 179's "Incapacitated or Dead" clause is **already** a `CLAUSES` row from
  #19. Confirm it covers "or you die" as asserted text rather than adding a duplicate — the
  clause reads `Your Concentration ends if you have the Incapacitated condition or you die`,
  so what U4 adds is the **CI presence anchor** naming the death half, not a second row.
- **Test scenarios:** corrupt the clause on a **copy** of the verifier and confirm unmatched;
  the pytest guards through `scripts/prove_guard_red.sh`.
- **Execution note:** the verifier is hand-run and `prove_guard_red.sh` cannot drive it —
  corrupt a copy and delete the copy, as #231, #233 and #215 did.
- **Verification:** verifier green against the document; corruption red.

### U5. Figures, build stamp, and the issues

- **Goal:** Publish what changed and close what closed.
- **Requirements:** R17.
- **Dependencies:** U1-U4.
- **Files:** `README.md`, `src/srd_rules_engine/__init__.py`.
- **Approach:** **Coverage does not move** — `concentration` is claimed and was already
  reachable (0036 clause 8); this makes it *correct* rather than larger. Bump `__version__`
  and both README stamps, and say what actually shipped.
- **Test scenarios:** `tests/test_build_stamp.py`,
  `tests/test_readme_reports_real_coverage.py`; `check_build_stamp_advanced.py main`.
- **Verification:** full gate green.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy` — all four, per `AGENTS.md`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses verified.
- `scripts/prove_guard_red.sh` for U2's and U3's guards.
- **U4's verifier clause by hand:** corrupt a copy, run it, delete the copy.
- `scripts/prove_against_base.sh main tests/test_spellcasting.py tests/test_read_surface.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- Record 0037 exists, is indexed, closes #239, and every clause it specifies and nobody has
  built carries an issue number in **Status of implementation**.
- Concentration does not come back when Incapacitated lifts, and no save is owed for a spell
  that ended; #238 closed with the reproduction asserted as a test.
- A creature that dies is not concentrating, by whichever route killed it.
- The voluntary end is callable and costs nothing; it is not a legal action.
- `after_conditions` has no callers and no definition.
- p. 179's death clause is anchored for CI; guards proved red.
- Coverage unchanged; build stamp advanced; full gate green.
- The two deferrals above filed, with their numbers written beside the prose.

## Open Questions

- **None blocking.** #239 is settled by U1 rather than deferred; #235 items 1 and 2 stay open
  by the scope decision above rather than by omission.

## Risks

- **Materialising in `with_condition` fires on every application**, including one that lands
  while the creature holds no Concentration. Harmless — writing `Concentration()` over
  `Concentration()` changes nothing — but it does bump `generation` through `_evolve`, which
  is what read tokens are compared on. Mitigated by writing only when the field is active.
- **A creature Incapacitated *before* this change ships** carries a stored Concentration that
  the old derivation hid. After it, the stored value is what is reported — so a persisted
  encounter could read as concentrating when the old build said otherwise. There is no
  persistence format for `EncounterState` today, so nothing is stranded; named because the
  next thing that adds one inherits the question.
- **0037 designs more than this PR builds**, which is the state `AGENTS.md` warns produces
  closed issues that read as finished work. Mitigated by filing the unbuilt clause before
  merge and putting its number in the record.

## Sources & Research

- SRD v5.2.1 PDF, p. 179 (*Concentration*, entire entry) read whole for this plan; p. 17
  ("a monster dies the instant it drops to 0 Hit Points"); p. 184 (Incapacitated).
- `core.spellcasting` (`Concentration.after_conditions`, `.ended`, `.begin`), `core.state`
  (`with_damage`, `with_condition`, `with_death`, `with_concentration_ended`),
  `core.read_surface`, `core.conditions` (`ConditionEffects.concentration_broken`),
  `core.duration` (`Duration`, `SaveEnds`, `DurationKind`, and the module docstring's "a span
  with optional early-outs").
- [0023](../decisions/0023-the-turns-end-is-a-loop-owned-phase.md) clause 5,
  [0036](../decisions/0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md) clauses 2 and
  8, [0020](../decisions/0020-two-kinds-of-time.md),
  [0021](../decisions/0021-a-round-is-six-seconds.md) clauses 3 and 4,
  [0018](../decisions/0018-api-stability.md) clause 4.
