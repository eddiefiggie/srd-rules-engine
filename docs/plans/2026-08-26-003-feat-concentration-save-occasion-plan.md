---
title: A fourth occasion, owed by whoever took the damage - Plan
type: feat
date: 2026-08-26
topic: concentration-save-occasion
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/215
---

# A fourth occasion, owed by whoever took the damage - Plan

## Goal Capsule

- **Objective:** Give p. 179's Concentration save an occasion, so the arithmetic that has been built and unreachable since #19 is actually rolled when damage lands.
- **Headline finding:** the issue asks for an occasion, and the two constraints that decide its shape are **not in the issue**. First, [0023](../decisions/0023-the-turns-end-is-a-loop-owned-phase.md) clause 5 already routed a damage-triggered consequence through `EncounterState.with_damage` — *because it is not a save*, and said sharing one path "would force the damage path to route through the turn loop." Second, the existing obligation machinery is **once per turn by construction** (`discharged` is `(actor_id, rule_id)`, reset on every advance), and a Concentration save is owed **once per damage instance**. Reusing it would silently swallow the second save of a Multiattack — a skip, which is the failure class this product exists to make impossible.
- **The shape:** a **fourth occasion**. `with_damage` records saves *owed*, per instance, on a queue rather than the once-per-turn set; the turn loop discharges each through the one adjudication entry point, exactly as it already does for the turn's start and end. Nothing creates a second path to an outcome — it creates a fourth occasion on which the existing path is taken.
- **Secondary finding, and it needs saying:** `concentration` is **already claimed** in the inventory, and `Concentration` is referenced nowhere in `src/` outside its own module. No `Combatant` field holds one, so nothing in an encounter can be concentrating. This work is what makes that claim honest.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. The official SRD v5.2.1 PDF at `/path/to/SRD_CC_v5.2.1.pdf` is the authority on every mechanic; no mechanic is inferred from memory (R31).
- **Stop conditions:** Stop and ask if the design requires `core.state` to produce a result (R1), if a resolver would need to be handed a roll (R4), or if the per-instance queue turns out to need a bound this plan has not stated.
- **Tail ownership:** One PR. Every question the design surfaces and does not settle is filed before the PR merges.

---

## Problem Frame

p. 179, *Concentration*, under **Damage**:

> If you take damage, you must succeed on a Constitution saving throw to maintain
> Concentration. The DC equals 10 or half the damage taken (round down), whichever number is
> higher, up to a maximum DC of 30.

`core.spellcasting.concentration_save_dc` and `concentration_save` implement that arithmetic
— the floor of 10, the halving rounded down, the cap of 30 — and are **called by nothing
outside their own tests**. The gap is not the rule; it is the occasion.

[#215](https://github.com/eddiefiggie/srd-rules-engine/issues/215) names three candidate
shapes and says the choice "probably wants a short record since it turns on R1". It does,
and the record has more to settle than the issue knew.

---

## What the Investigation Found

**Finding 1 — 0023 clause 5 is the governing precedent, and it points away from the obvious
answer.** The clause reads:

> **5. The event-triggered early-out does not use this path.** "The Unconscious condition for
> 1 minute **or until it takes any damage**" (p. 63) **is not a save** and is not
> end-of-turn. It is a state change, and it resolves **where the state change resolves** —
> `EncounterState.with_damage` […] sharing one would force the damage path to route through
> the turn loop.

So there is a precedent for damage-triggered consequences living in `with_damage`, and it
holds **because that case needs no roll**. Concentration's trigger *is* a save. `with_damage`
cannot roll one without `core.state` producing an outcome, which R1 forbids outright.

**This is not a re-opening of 0023.** Clause 5 anticipated exactly this: it said the two
shapes "are genuinely different mechanisms". #215 is the different mechanism arriving, and
the record should say so rather than letting a reader think 0023 is being revisited.

**Finding 2 — the decisive one. The obligation machinery is once-per-turn and this save is
once-per-damage-instance.** `EncounterState.discharged` is a `frozenset[tuple[str, str]]` of
`(actor_id, rule_id)`, and the turn advance resets it with the comment:

> An obligation is owed once per turn, so the record of having met it does not outlive the
> turn it belonged to.

Every existing obligation is gated on `(actor_id, RULE_ID) not in state.discharged`. A
creature struck twice by a Multiattack owes **two** Concentration saves; keyed that way the
second is suppressed and never rolled. That is a skip — a compelled save that silently does
not happen — and it is the precise failure this engine exists to remove. **The existing
mechanism cannot be reused unchanged**, and this is the constraint that most shapes the issue
proposes would have discovered late.

**Finding 3 — the save is owed by the target, who is usually not the acting creature.**
Obligations today are enumerated for `actor_id`, the creature whose turn it is. Damage
lands on someone else: an attack on the monster's turn breaks the *player's* Concentration.
So the queue is keyed by the creature that took the damage, and the loop discharges it
regardless of whose turn produced it.

**Finding 4 — three phases can deal damage, so one discharge point is not enough.**
`TurnLoop` adjudicates in three places: `start_turn`, `run` and `end_turn`. Burning deals its
damage at the *start* of a turn (p. 178), so a burning concentrating creature owes a
Concentration save during `start_turn`. A design that only discharged after `run` would work
for attacks and silently miss the hazard — the same shape of gap as Finding 2, reached a
different way.

**Finding 5 — nothing records that a creature is concentrating, and the shape is claimed
anyway.** `Combatant` has no `concentration` field. `Concentration` is referenced nowhere in
`src/` outside `core.spellcasting` — the only other mentions are prose in `core.duration`'s
module docstring and the `ENGINE_SHAPES` line that claims it. `core.duration` says:

> Concentration is `core.spellcasting` and **already ends its own effects**

That sentence describes a capability with no consumer, which is the same decay #228 found in
`core.inventory` ("this note went on saying it was produced by nothing for as long as nobody
read it"). Meanwhile `ENGINE_SHAPES["concentration"]` claims the shape, and
`effect_shapes.json` marks it implemented.

**The claim is overstated today**, and under 0033's standard the bar is the consequence the
shape's own entry states — p. 179 states the damage save explicitly. This plan closes the gap
by building the occasion rather than by unclaiming the shape, and adds the guard that stops
the claim being true only by assertion. **If the work does not land, the claim should be
revisited rather than left**; that is stated in Scope Boundaries rather than assumed.

---

## Key Technical Decisions

**KTD1 — A fourth occasion: a consequential obligation, discharged through the one
adjudication entry point.** *(session-settled: user-approved — chosen over a third turn-phase
occasion, and over resolving the save inside `with_damage`.)* `TurnLoop.start_turn`'s
docstring already states the principle this reuses: *"Nothing here creates a second path to
an outcome. It creates a third occasion on which the existing path is taken."* This is the
fourth. The loop synthesises a `Declaration` for the owed save exactly as
`_obligation_declaration` does now, and `Adjudicator.adjudicate` produces the result. R1
holds because nothing else produces one; R4 holds because the engine rolls it.

**KTD1a — Rejected on purpose: resolving the save in `with_damage`.** It is the literal
reading of 0023 clause 5 and it is wrong here. `core.state` would have to roll a d20 and
produce a result, which is the one thing R1 forbids no matter how convenient the call site.
Named here so the record rejects it deliberately rather than leaving a future reader to think
clause 5 was simply overlooked.

**KTD1b — Rejected on purpose: a third turn-phase occasion.** Enumerating Concentration saves
alongside start- and end-of-turn obligations reuses 0027's machinery unchanged, and defers the
save by up to a round. The spell would keep working after the damage that should have broken
it, which is a wrong outcome rather than a late one.

**KTD1c — Rejected on purpose: a reaction-shaped offer.** `core.reactions` exists to *offer*.
p. 179 compels the save, and a slot in which declining is expressible is a slot in which the
save can fail to happen — which is `Obligation`'s own docstring, and the reason obligations
are never declared.

**KTD2 — The queue is per damage instance, and it is not `discharged`.** Finding 2 is the
whole of this decision. Concentration saves owed are held as an ordered structure keyed by the
creature that took the damage, one entry per instance, each carrying the **damage amount that
occasion's DC derives from**. `discharged`'s `(actor_id, rule_id)` set is left exactly as it
is — widening it to carry a count would make every existing obligation's once-per-turn
semantics depend on a field only one rule uses, which is the shape 0019 refuses.

**KTD2a — The amount is carried, not recomputed.** The DC is a function of *that* instance's
damage, and by the time the loop discharges the save the creature's hit points have already
moved. Reading the damage back off state is not possible, so the queue entry carries it. This
is also what keeps R4 intact: the resolver is a closure over the amount the engine recorded,
never a number a caller supplied.

**KTD3 — Detection is in state; production is in the loop.** `with_damage` notices that the
damaged creature is concentrating and records the debt. It does not roll, does not adjudicate
and does not decide the outcome. The split is exactly 0023 clause 5's principle — detection
belongs where the triggering thing happens — with the rolling half moved to where R1 requires
it.

**KTD4 — Concentration is state on `Combatant`.** A `concentration: Concentration` field,
defaulting to the inactive value, alongside `hazards` and `conditions`. 0027 clause 5's
reasoning applies unchanged: this is per-creature state and not a condition, so it does not go
on `Conditions`.

**KTD5 — All three adjudicating phases discharge the queue.** Finding 4. A shared helper the
loop calls after every adjudication, rather than three copies — three copies is how one gets
missed, and the one that would be missed is the hazard path, which has no attacker to make the
omission obvious.

**KTD6 — `TurnOutcome` gains a field, additively.** The consequential rulings must be visible
to a driver: R30 wants them in the record, and R29's narration bounds have to reach the
narrator for each. `TurnOutcome` is on the **COMMITTED** surface
([0018](../decisions/0018-api-stability.md)), so the field is added with a default and nothing
is removed or renamed. 0018 clause 4 governs removal and is not engaged; `API_VERSION` is not
bumped, and the plan states that rather than leaving it to be inferred.

**KTD7 — This work makes the existing `concentration` claim honest; it does not move the
figure.** Finding 5. The shape is already claimed, so coverage stays **95 of 209**. What
changes is that the claim becomes true in play, and a guard asserts the reachability so it
cannot decay back to an assertion. `core.duration`'s "already ends its own effects" sentence
is corrected in the same change rather than left contradicting the module beside it.

**KTD8 — Grounded in the PDF, read before deciding.** *(session-settled: user-directed.)*
p. 179's Concentration entry is read from `/path/to/SRD_CC_v5.2.1.pdf` and the damage sentence
asserted as a verifier clause, because the DC arithmetic is a rule value and a wrong one is
indistinguishable from a right one inside a finished ruling (R31).

---

## Scope Boundaries

**In scope:** the decision record; `concentration` on `Combatant`; the per-instance queue and
its recording in `with_damage`; the loop's discharge across all three phases; the resolver
wiring; the p. 179 verifier clause; guards and their proofs; the reachability guard for the
existing claim; the build stamp.

### Deferred to Follow-Up Work

- **The other three Concentration breakers in play.** `Concentration.begin`, `.ended` and
  `.after_conditions` exist and are tested, but nothing in the loop calls them either — a
  caster has no way to *start* concentrating through a declaration. That is #19's territory
  and larger than this issue. **File before merge**, because after this change the damage
  breaker will work while the other three still have no consumer, which is a strictly odder
  state than the one this plan found and must not be left untracked.
- **Saving-throw proficiency**, which `core.save_ends` already discloses as absent for every
  save in the engine. Not this issue, not newly broken by it, and already disclosed — **do not
  file**, per the note-to-prevent-re-raising exception.

**Out of scope:** starting Concentration from a declaration (#19); the Green Hag magnitude
shape ([#216](https://github.com/eddiefiggie/srd-rules-engine/issues/216)); any change to
`discharged`'s semantics for existing obligations.

---

## Implementation Units

### U1. Decision record 0036

- **Goal:** Record KTD1-KTD3 and why 0023 clause 5's path cannot serve a save.
- **Requirements:** R1, R4, R17, R31.
- **Dependencies:** none.
- **Files:** `docs/decisions/0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md`, `docs/decisions/README.md`.
- **Approach:** House format with a clause table in **Status of implementation**. Related:
  [0023](../decisions/0023-the-turns-end-is-a-loop-owned-phase.md) (clause 5, the precedent
  that does not reach), [0027](../decisions/0027-occasions-and-outcomes-without-a-roll.md)
  (clauses 1-3, the occasion machinery this extends), [0015](../decisions/0015-reactions-and-the-agent-seam.md)
  (why a compelled save is not reaction-shaped), [0018](../decisions/0018-api-stability.md)
  (the additive field).
- **Lead with Finding 2**, not with the three shapes. The once-per-turn/once-per-instance
  mismatch is what makes the decision non-obvious, and a record that opened with the shapes
  would read as picking one on taste.
- **Test scenarios:** `tests/test_decision_records.py`.
- **Verification:** `pytest tests/test_decision_records.py` green; index row renders.

### U2. Concentration as state

- **Goal:** Give the engine somewhere to record that a creature is concentrating, so there is
  someone to compel the save from.
- **Requirements:** R14, R18.
- **Dependencies:** U1.
- **Files:** `src/srd_rules_engine/core/state.py`, `src/srd_rules_engine/core/read_surface.py`.
- **Approach:** `concentration: Concentration = Concentration()` on `Combatant`, sited beside
  `hazards` with the same reasoning (0027 clause 5: per-creature state, not a condition).
  Expose it on the read surface as a typed value — what the creature is concentrating on —
  because a driver deciding whether to cast needs it and R19 makes reads non-mutating.
- **The import direction is already settled, and was checked during planning rather than
  left to be discovered.** `core.state` line 76 already reads
  `from srd_rules_engine.core.spellcasting import SpellSlots`, and `core.spellcasting` does
  not import `core.state`. Adding `Concentration` to that existing import introduces no cycle
  and moves no type.
- **Test scenarios:** a combatant defaults to not concentrating; `after_conditions` still
  ends it on Incapacitated when read through state; the read surface reports it without
  mutating (R19).
- **Verification:** `pytest`, `mypy` green; no import cycle.

### U3. The occasion: `with_damage` records the debt

- **Goal:** Record one owed save per damage instance, carrying the amount its DC derives from.
- **Requirements:** R1, R4.
- **Dependencies:** U2.
- **Files:** `src/srd_rules_engine/core/state.py`.
- **Approach:** In `with_damage`, **after defences resolve** — the DC derives from damage
  *taken*, so a creature immune to the type takes none and owes no save, exactly as the death
  save failure already reasons three lines above. Append an entry to the queue for the damaged
  creature carrying the post-defences amount. **No roll, no adjudication, no outcome** (KTD3).
  Zero damage owes nothing.
- **Patterns to follow:** the existing defences-first ordering in `with_damage` and its
  comment, which already states this reasoning for the death save.
- **Test scenarios:** two instances in one turn record two debts (the Finding 2 case,
  explicitly); damage fully absorbed by Immunity records none; a non-concentrating creature
  records none; the queue survives a turn advance, because the debt is not once-per-turn.
- **Execution note:** the turn-advance case is the one most likely to be got wrong by reflex,
  since every neighbouring structure resets there. Assert it directly.
- **Verification:** `pytest` green; `with_damage` still produces no result of its own.

### U4. The loop discharges it, in all three phases

- **Goal:** Roll each owed save through the one adjudication entry point.
- **Requirements:** R1, R4, R29, R30.
- **Dependencies:** U3.
- **Files:** `src/srd_rules_engine/loop/turn.py`, `src/srd_rules_engine/core/spellcasting.py`.
- **Approach:** A shared helper — called by `start_turn`, `run` and `end_turn` after each
  adjudication (KTD5) — that drains the queue, synthesising a declaration per owed save via
  the existing `_obligation_declaration` shape and adjudicating it. A resolver closure over
  the recorded amount supplies the DC from `concentration_save_dc`; on failure the effect ends
  the Concentration. Each ruling yields a `NarrationRequest`, as every other obligation's does.
  `TurnOutcome` gains the additive field (KTD6), and `TurnStart`/`TurnEnd` carry theirs the
  way they already carry `rulings`.
- **Drain, do not iterate a snapshot.** `start_turn` already re-reads its pending list each
  pass with a stated reason; the same applies here, and more sharply — a Concentration save
  that fails can itself change state.
- **Patterns to follow:** `start_turn`'s while-loop and its "re-read each time" comment;
  `_obligation_declaration`; `core.save_ends` for a resolver closed over per-effect values.
- **Test scenarios:** an attack that damages a concentrating creature produces a second ruling
  in the same declaration slot; **Burning at the turn's start does too** (Finding 4); a
  Multiattack dealing two instances produces **two** saves, not one; a failed save ends the
  Concentration and the ledger records both rulings (R30); the save is rolled on the target's
  behalf while another creature is the actor (Finding 3).
- **Execution note:** the two-instance and the Burning cases are the ones a design that looked
  right would fail. Write them first.
- **Verification:** `pytest` green; the ledger shows two entries for one declaration.
- **As built, where it differs from the above** (amended after the work landed, so the plan
  and the tree agree). The rule and resolver are **`core.concentration`**, a module of their
  own: a resolver takes an `EncounterState`, and `core.state` already imports *from*
  `core.spellcasting`, so putting them there inverts that edge into a cycle. `core.save_ends`
  is the same shape for the same reason. The resolver **reads the amount off the debt in
  state** rather than closing over it, because resolvers are registered per rule id and a
  closure would need one rule per damage total. The drain is called at the **top of each
  pass** of the two obligation loops rather than after them, so a phase with no obligations
  of its own still discharges a queue an earlier phase left. `TurnOutcome` gained **three**
  fields, not one: the rulings, their narrations (R29 owes one each), and the `unresolvable`
  obligations `TurnStart` and `TurnEnd` already name.

### U5. Assert p. 179, and guard what was proved

- **Goal:** Pin the rule value and make the new invariants checkable.
- **Requirements:** R31, R32, R17.
- **Dependencies:** U4.
- **Files:** `scripts/verify_d20_rules.py`, `tests/test_spellcasting.py`, `tests/test_effect_shape_inventory.py`.
- **Approach:** A `CLAUSES` row for p. 179's damage sentence — the DC being 10 or half the
  damage, capped at 30 — so the arithmetic rests on asserted text rather than on a constant
  somebody typed. A CI presence check anchors it, since CI has no PDF.
  Plus the **reachability guard** for KTD7: `concentration` is claimed, so assert something
  in the loop actually reaches `Concentration` — the failure Finding 5 describes is a claim
  true only by assertion, and it survived precisely because nothing checked.
- **Test scenarios:** corrupt the DC floor from 10 to 11 and confirm red; corrupt the p. 179
  pattern on a **copy** of the verifier and confirm the clause reports unmatched.
- **Execution note:** the verifier is hand-run and `prove_guard_red.sh` cannot drive it —
  prove that corruption on a copy and delete the copy, as #231 and #233 did. The pytest guards
  go through the script.
- **Verification:** verifier reports the new clause; both corruptions red.
- **As built.** The DC clause p. 179's arithmetic rests on was already asserted (#19); what
  had no clause was the **trigger** sentence, so that is the row added. The floor corruption
  did **not** go red as this unit assumed — every assertion in `tests/test_spellcasting.py`
  compares against `CONCENTRATION_DC_FLOOR` and `CONCENTRATION_DC_CAP` rather than against 10
  and 30, so the whole file stays green against a wrong floor. The literals are now pinned as
  literals and both corruptions go red. Proving the cap red then exposed a second defect, in
  `scripts/prove_guard_red.sh`: it restored the source and not its bytecode, so a same-size
  corruption survived the restore in the running engine while `git diff` read clean.

### U6. Figures, build stamp, and the issue's answer

- **Goal:** Publish what changed and close #215.
- **Requirements:** R17.
- **Dependencies:** U1-U5.
- **Files:** `README.md`, `src/srd_rules_engine/__init__.py`, `src/srd_rules_engine/core/duration.py`.
- **Approach:** **Coverage does not move** — `concentration` was already claimed (KTD7), so
  the figure stays 95 of 209 and the build line says what became *true* rather than what
  became larger. Correct `core.duration`'s "already ends its own effects" sentence in the same
  change. Bump `__version__` and both README stamps.
- **Test scenarios:** `tests/test_build_stamp.py`, `tests/test_readme_reports_real_coverage.py`
  green; `check_build_stamp_advanced.py main` advanced.
- **Verification:** full gate green.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy` — all four, per `AGENTS.md`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses verified.
- `scripts/prove_guard_red.sh` for U3's and U5's pytest guards.
- **U5's verifier clause by hand:** corrupt a copy, run it, delete the copy.
- `scripts/prove_against_base.sh main tests/test_spellcasting.py tests/test_turn_loop.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- Decision record 0036 exists, is indexed, and its **Status of implementation** names what landed.
- `Combatant` carries `concentration`; the read surface reports it without mutating.
- `with_damage` records one debt per instance, after defences, and produces no result of its own.
- All three loop phases discharge the queue; two instances produce two saves; Burning at the turn's start produces one.
- p. 179's damage sentence asserts in the verifier, with a CI anchor; guards proved red.
- The `concentration` claim is reachable and guarded; `core.duration`'s stale sentence corrected.
- Coverage unchanged at 95 of 209; build stamp advanced; full gate green.
- The deferred breakers filed as an issue, with its number written beside the entry.
- #215 closed with the occasion built.

---

## Open Questions

- **None.** The one this plan opened — whether `core.state` importing `Concentration` would
  invert a dependency — was answered during planning rather than deferred into U2: the import
  already exists for `SpellSlots` and runs in that direction.

## Risks

- **The queue is unbounded.** A creature taking many small hits accumulates debts, and nothing
  states a maximum. p. 179 gives one save per instance and no cap, so a bound would be an
  invented rule (R31) — but an unbounded structure in state is worth naming. Mitigated by the
  debts being drained at the next adjudication, which is at most one declaration away.
- **A failed save changing state mid-drain could invalidate the rest of the queue.** Mitigated
  by draining rather than iterating a snapshot (U4), which is `start_turn`'s existing pattern
  and exists for the same reason.
- **The reachability guard could pass on a token call.** A guard asserting "something calls
  `Concentration`" is satisfiable by a call that does nothing. Mitigated by asserting the
  behaviour — a damaged concentrating creature produces a second ruling — rather than the
  reference.

## Sources & Research

- SRD v5.2.1 PDF, p. 179 (*Concentration*, and the Damage sentence), read during planning.
- `core.spellcasting` (`Concentration`, `concentration_save_dc`, `concentration_save`),
  `core.state` (`Combatant`, `with_damage`, `discharged` and its turn-advance reset),
  `loop.turn` (`TurnLoop.run`, `start_turn`, `start_turn_obligations`, `_obligation_declaration`,
  `Obligation`, `TurnOutcome`), `core.save_ends`, `core.duration`, `stability.COMMITTED`.
- [0023](../decisions/0023-the-turns-end-is-a-loop-owned-phase.md) clause 5,
  [0027](../decisions/0027-occasions-and-outcomes-without-a-roll.md) clauses 1-3 and 5,
  [0018](../decisions/0018-api-stability.md) clause 4.
