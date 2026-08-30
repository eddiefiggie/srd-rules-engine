# 0081 — A campaign day's end is the fifth occasion

- **Status:** Accepted, 2026-08-30
- **Settles:** [#399](https://github.com/eddiefiggie/srd-rules-engine/issues/399)
- **Requirements:** R1, R4, R8, R15, R29, R31
- **Related:** [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  whose shape this copies and whose sentence it reuses for the fifth time;
  [0080 — Dehydration is bookkeeping](0080-dehydration-is-bookkeeping.md), the other half of
  the same day's end;
  [0048](0048-a-forced-save-is-one-shape.md), whose `ForcedSave` this is the third thing to
  compel;
  [0072 — movement is a phase the loop drives](0072-movement-is-a-phase-the-loop-drives.md),
  the fourth occasion and the first non-turn one

## Context

p. 185's Malnutrition compels a DC 10 Constitution saving throw at a day's end. That is a die,
which is an adjudication (R1, R4), and every occasion that could produce a ruling was
**encounter-scale**: a turn's start, its declaration slot, its end, a move. A campaign day
ending is none of them and may happen with no combat at all.

`EncounterState.with_time_passed` and `with_day_ended` both say outright what they are —
*"deterministic bookkeeping rather than outcomes… no die is thrown"* — so neither could take
it. #399 asked what the fifth occasion is, what drives it, who is asked, and whether an
encounter is the right container.

## Decision

1. **`TurnLoop.end_day` is the occasion.** It applies p. 181's bookkeeping through
   `with_day_ended`, then drains the saves that transition compelled, adjudicating each
   through the one entry point and yielding a `NarrationRequest` per ruling.

2. **The save is compelled by the state transition and rolled by the loop.** `with_day_ended`
   emits a `ForcedSave`; `end_day` drains it through the helper that already drains
   Concentration's and Topple's. **No new machinery** — 0048 generalised `ForcedSave` to "one
   save a creature owes and has not rolled, whatever compelled it", and this is the third
   thing to compel one.

3. **It lives on `TurnLoop` despite not being a turn**, and `_owed` is the reason. R29's
   narration debt is held per loop, so a second driver would let a creature owe a narration to
   one object and act through another — a hole in the guarantee rather than a tidier design.

4. **`TurnLoop`'s docstring stops claiming to own the turn.** It owns the agent seam and the
   narration debt. That claim had already been false since `move` landed (0072); two of its
   five phases are not turn-shaped now.

5. **`EncounterState` is the container, and its name is the thing that is wrong.** It already
   holds `clock`, campaign-axis conditions and `with_time_passed`. A day passing between
   encounters has nowhere else to live, and inventing a second state type to hold what this one
   already holds would be renaming by other means.

6. **The DC is recorded on the debt** even though p. 185 states it as a constant. 0036 clause 4
   requires it of every forced save, and an exception for the one that happens to be constant
   is an exception somebody has to remember.

## Why

### Nothing here creates a second path to an outcome

0023's sentence, and the fifth time it has been the answer: *it creates another occasion on
which the existing path is taken.* The save resolves through `Adjudicator.adjudicate`, the
engine rolls it, the ruling appends like any other.

Worth counting, because the recurrence is the finding rather than each instance: **five
occasions, all discovered the same way** — a rule the document states plainly, with no moment
in the loop at which it could happen. 0023 found two at once and said so; 0036, 0072 and this
each found one more. A rule whose trigger is not a declaration needs an occasion, and the loop
is where occasions live.

### The gate's real question was "what owns it", and `_owed` answered it

Of #399's three questions, two dissolved on inspection. *Who is asked* is derived from the
caller's statement of consumption, the way `with_time_passed` derives from the caller's
statement of elapsed time. *Whether an encounter is the right container* was already answered
in practice, four builds ago, by every campaign-axis field on `EncounterState`.

The one that mattered was **what drives it**, and the answer came from a field rather than an
argument: `_owed` is per-loop, so anything that can produce a ruling and demand a narration has
to be on the object that tracks the debt. A `CampaignLoop` would have been the tidier diagram
and the worse engine.

### Two rules, two shapes, one occasion

p. 181 inflicts a level; p. 185 asks the dice for one. They fire at the same moment and are
built four builds apart, because the difference between them is exactly the difference between
a state transition and an adjudication — which is the distinction this whole engine is
organised around. `end_day` holding both is what makes that visible in one place:
`test_both_rules_fire_on_the_same_day` asserts two levels and **one** ruling.

## Consequences

- **`with_day_ended` grows a `food` argument** and compels saves without rolling them. A
  consumer calling it directly gets the bookkeeping and a debt nobody discharges — the same
  disclosed limit as every other state method the loop wraps.
- **`malnutrition` stays unclaimed.** p. 185 has two sentences and only the save is built; the
  five-day starvation clause is [#401](https://github.com/eddiefiggie/srd-rules-engine/issues/401).
  A shape claimed at half is the overstatement #371 and #264 each found.

## Status of implementation

| Clause | State |
|---|---|
| 1 — `TurnLoop.end_day` | **Built** |
| 2 — compelled by the transition, rolled by the loop | **Built**, through `ForcedSave` |
| 3 — it lives on `TurnLoop`, because `_owed` does | **Built** |
| 4 — the docstring stops claiming the turn | **Built** |
| 5 — `EncounterState` is the container | **Built**, in the sense that nothing changed |
| 6 — the DC on the debt | **Built** |

p. 185's starvation clause is **not built** and is #401. `scripts/verify_d20_rules.py` carries
p. 185 whole, including that sentence, so whoever takes it does not re-read the page.

### Evidence

Seven corruption proofs, each red on the assertion written for it.

| Corruption | Went red on |
|---|---|
| the save never compelled | the ruling test and the failed-save test |
| the eats-nothing guard removed | `test_eating_nothing_compels_no_save` |
| Dehydration made to compel a save | `test_dehydration_produces_a_level_and_no_ruling` |
| `food` dropped on the way into the transition | the no-combat test and the both-rules test |
| the narrations discarded | `test_the_ruling_is_narrated_like_any_other` |
| the level given a generic rule id | the attribution test and the Long Rest lock |
| `<` widened to `<=` | `test_exactly_half_a_day_of_food_compels_nothing` |

The third is the one that pins the record's central claim: p. 181 throws no die, so an engine
that compelled a save for it would put a roll in the ledger that decided nothing.
