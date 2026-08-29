# 0027 — The turn's start is a phase too, and not every outcome rolls a d20

- **Status:** Accepted, 2026-08-25
- **Settles:** [#124](https://github.com/eddiefiggie/srd-rules-engine/issues/124), and the design
  half of [#140](https://github.com/eddiefiggie/srd-rules-engine/issues/140)
- **Requirements:** R1, R4 · touches R14, R19, R28, R29
- **Related:** [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  whose clause 1 this mirrors and whose clause 5 it applies unchanged;
  [0020](0020-two-kinds-of-time.md) and [0021](0021-a-round-is-six-seconds.md), the two axes;
  [0019 — `kind` is a filing label](0019-kind-is-a-filing-label.md), which decides clause 2;
  [#119](https://github.com/eddiefiggie/srd-rules-engine/issues/119)

## Context

0023 found that the save-ends save and the death save were **one missing phase rather than two
oversights**, and built one of them: `TurnLoop.end_turn`. It could not place the death save,
because the sentence saying when a death save is made was not in this repository and 0023
refused to supply it from memory.

Two readings since have supplied it, and both went the other way from the convenient guess:

- **#124** — p. 17. The death save is made when a creature **starts** its turn at 0 hit points.
  Not the end. Had 0023 assumed the two obligations shared a phase, the save would have been
  rolled at the wrong moment and looked correct doing it.
- **#140** — the five hazard pages. **Burning fires at the start of a turn too** (p. 178), and
  the other four fire on three further occasions, one of which is not an occasion at all.

So five things now want occasions, across four of them:

| Wants | Page | Occasion |
|---|---|---|
| save-ends save | 63 | end of turn — **built** (0023) |
| Suffocation | 189 | end of turn |
| death save | 17 | **start of turn** |
| Burning | 178 | **start of turn** |
| Dehydration | 181 | a day's end, no roll |
| Malnutrition | 185 | a day's end, DC 10 Constitution save |
| Falling | 182 | **none** — it resolves on landing |

Two of those rows are not occasion questions at all, and separating them is most of this record.

## Options considered

**Generalise `Obligation` with a `kind` field and let each consumer branch on it.** Rejected
under 0019, which is the nearest prior reasoning and says exactly this: `kind` is a filing label
rather than a model, and a test already refuses to let any module under `src/` branch on one. An
obligation that carries its occasion as data invites precisely the branch 0019 forbids.

**One phase that fires everything, with the occasion as a parameter.** Rejected. It would put the
day's-end hazards inside the turn loop, which is 0023 clause 5's mistake in a new place —
detection belongs where the triggering thing happens, not in a catch-all.

**Give Falling a d20 test so it fits the existing `Proposal`.** Rejected, and it is the reason
clause 6 exists. p. 182 calls for no roll. Inventing one to reach the existing shape is inventing
a roll the rules do not call for, which is what R4 protects against — from the other direction
than usual.

**Wait for all five hazards before deciding any of it.** Rejected as the wrong granularity, for
0025's reason: the structural questions do not depend on the remaining rule values, and leaving
them open means the next person re-derives them.

## Decision

**1. The turn's start is a loop-owned phase, exactly as its end is.** `TurnLoop` gets a third
generator entry point — sketch, not a signature to hold anyone to:

```python
def start_turn(
    self, state: EncounterState, actor_id: str
) -> Generator[Request, Response, TurnStart]:
    """Every obligation the start of this creature's turn incurs, resolved."""
```

It enumerates obligations from state, adjudicates each through the one entry point, and yields a
`NarrationRequest` per ruling — 0023 clauses 1, 2 and 3 unchanged, one phase earlier. The death
save and Burning both fire here.

**The adapters' `begin_turn` is not this phase and must not become it.** It maps to
`TurnLoop.run`, which opens a *declaration slot*. The names would collide in a way that reads as
though the obligation phase were already built.

**2. An obligation is identified by its rule id, not by its condition.** `Obligation` today
carries `condition: Condition` and a label reading "repeats the save that ends X". A death save
has no condition, and Burning is not one of the fifteen. The field generalises by being
**removed** rather than by being widened: an obligation is an actor, a `rule_id`, and a label,
and the `rule_id` already selects the resolver.

This is the shape 0019 argues for. Widening `condition` into a union, or adding a `kind`
alongside it, would put the occasion in the data and the branch in every consumer.

**3. Each occasion enumerates its own obligations.** `TurnLoop.obligations` becomes scoped to a
phase rather than gaining an occasion argument. A single enumerator returning obligations tagged
with their occasion is clause 2's rejected shape wearing different clothes.

**4. The skip guarantee at the turn's start is enforced by refusing the declaration.** 0023
clause 6 made `advanced_turn` refuse while an end-of-turn obligation is owed. The symmetric guard
cannot be `advanced_turn` — by the time the pointer has moved, the incoming creature's
start-of-turn obligations are *newly* due, not overdue. So `TurnLoop.run` refuses to open a
declaration slot while the actor owes one, the way it already refuses while a narration is owed
(R29).

*This is the clause this record is least confident in*, and 0023 said the same of its own clause
6 — which is the honest precedent rather than a coincidence. A creature that must roll a death
save before acting cannot act first; that much is clear. Whether refusing the declaration is the
right *mechanism*, or whether it belongs in `advanced_turn` producing a state that is already
blocked, is the first place to look if the design fights back.

**5. Per-creature hazard state lives on `Combatant`, and not on `Conditions`.** "This creature is
Burning" is not one of the fifteen SRD conditions, and putting it on `Conditions` would misfile
it in the one structure whose completeness is a checked claim (15/15). It gets its own value
object on `Combatant`, shaped like `Senses` and `Speeds` — the pattern this repository already
uses twice, including their `None`-versus-zero distinction.

**6. An outcome may exist without a d20 test, and it reaches state through the same entry
point.** `Proposal.test` becomes optional. When it is absent, `adjudicate` skips `roll_d20`, and
**everything else is unchanged**: one adjudication entry point (R1), a seed is still drawn, the
`DamageDice` are still rolled by the engine at their offset (R4), and the ruling appends like any
other. This creates no second path to a result — it creates a proposal that has no d20 in it.

Falling needs this and it is not an occasion question at all. So does anything else the SRD
resolves without a roll, which is why this is stated generally rather than for Falling.

**A testless ruling must not replay as `UNREPLAYABLE`.** `replay_entry` returns that verdict when
an entry carries no reconstructible test, which is correct for a *thin* record and wrong for a
proposal that never had one — the damage is reproducible from the recorded seed. Getting this
wrong would make every automatic outcome permanently unverifiable while looking like a normal
limitation. Filed as [#170](https://github.com/eddiefiggie/srd-rules-engine/issues/170) with the
implementation.

**7. Falling does not use the occasion path.** It resolves where the state change resolves. This
is 0023 clause 5 applied unchanged — the event-triggered early-out does not route through the
turn loop, because detection belongs where the triggering thing happens. A fall is an event, and
routing it through a phase would force every event-shaped rule to acquire an occasion it does not
have.

**8. Dehydration is bookkeeping; Malnutrition is an outcome; they do not share an
implementation.** They share an axis, an effect, and very nearly a sentence, which is what makes
this worth stating. `EncounterState.with_time_passed` already draws the line and this record only
applies it — it says what it applies is "deterministic bookkeeping rather than outcomes … and no
die is thrown". Dehydration inflicts Exhaustion outright and fits that rule as written.
Malnutrition is a **DC 10 Constitution saving throw**, which is a die, and therefore an
adjudication — so it needs a campaign-axis *occasion*, which does not exist.

**9. Ending is event-driven for both turn-based hazards, and that is not a clock question.**
0020 and 0021's two axes decide when a hazard **fires**. Neither Burning nor Suffocation retires
on either axis: Burning goes out when it is doused, submerged, suffocated, or extinguished by an
action; Suffocation ends when the creature can breathe again. Both endings are facts the engine
cannot observe, so they arrive the way every other narrative fact does — never on a timer this
engine runs.

## Why

**The order of the clauses is the argument.** Clauses 1-5 answer "what occasion", clause 6
answers "what if there is none", and clauses 7-9 remove three things from the occasion question
that looked like they belonged in it. #140 asked four design questions; three of its five hazards
turn out not to need the answers.

**Two readings falsified the framing before it was written.** #124 assumed the death save might
share save-ends' phase; #140 assumed the hazards were cheap and that the death save was a third
obligation on one seam. Both were written carefully and both were wrong about the document. That
is the argument for asserting the sentences *before* the design rather than after, which #140's
clauses now do.

**The riskiest clause is named as such.** Clause 4 mirrors 0023 clause 6, including its
uncertainty. A record that hedges everything is useless and a record that hedges nothing is
dishonest; this one hedges the clause that has a real alternative.

## Consequences

**Accepted costs.**

- **`Obligation` changes shape and `TurnLoop.obligations` is replaced by per-occasion
  enumerators.** Both are Internal tier under [0018](0018-api-stability.md) — neither appears in
  `stability.COMMITTED` — so no `API_VERSION` bump, but `tests/test_turn_end.py` moves with them.
- **`Proposal.test` becoming optional weakens a type that was load-bearing by being required.**
  Every resolver today supplies one, and nothing enforces that a *testless* proposal is
  legitimate rather than a resolver that forgot. The compensation is that a proposal with no test
  and no effects resolves to nothing observable, which is a visible failure rather than a silent
  one.
- **Three of the five hazards stay blocked after this record**, on narrative facts the engine
  cannot observe: whether a creature drank, ate, or can breathe. That is the same shape #141
  reports for the afflictions, and it is not solved here.

**Follow-on effects.**

- #124 stays open as the implementation of clauses 1-4, and stays `srd-fidelity`: a downed player
  character still makes no death saves.
- #140 stays open for the hazards, with its design questions answered.
- Coverage is unchanged at **76 of 211**. A record resolves no shape.

## Evidence

No spike. Every question was answered by reading the document and the tree:

- `Proposal.test: D20Test` in `core/adjudicate.py` — required, no default — and
  `roll_d20(proposal.test, seed=seed)` called unconditionally. `with_damage` has exactly one
  caller, inside `adjudicate`. That is clause 6's problem, stated as a fact about the code.
- `EncounterState.with_time_passed`'s own docstring: "deterministic bookkeeping rather than
  outcomes … and no die is thrown". Clause 8 applies that sentence rather than inventing a rule.
- 0023 clause 5, which already decided the event-shaped case and needed no amendment for clause 7.
- `Senses` and `Speeds` in `core/sight.py` and `core/position.py`, the twice-used pattern clause 5
  follows.
- The MCP adapter's `BEGIN_TURN` dispatching to `TurnLoop.run`, which is why clause 1 names the
  collision.
- The six hazard clauses and the death-save timing clause in `scripts/verify_d20_rules.py`, all
  asserted before this record was written.

## Status of implementation

**Clause 6 is built; the rest is not.** `Proposal.test` became optional 2026-08-25, with `tests/test_outcome_without_a_roll.py` covering it.

| Clause | State |
|---|---|
| 1 — the turn's start is a loop-owned phase | **Built.** `TurnLoop.start_turn`, mirroring `end_turn` one phase earlier, returning `TurnStart`. The death save fires there; Burning will, once clause 5 exists |
| 2 — an obligation is identified by its rule id | **Built.** `Obligation` lost `condition` and gained `label`. `EncounterState.discharged` is keyed by `(actor_id, rule_id)`, which needed `save_ends_rule_id` moved to `core.conditions` — `core.save_ends` imports `EncounterState`, so the resolver module could not own the name state had to reach |
| 3 — each occasion enumerates its own | **Built.** `start_turn_obligations` and `end_turn_obligations` replace the single `obligations` |
| 4 — the declaration refuses while a start-of-turn obligation is owed | **Built**, and it survived contact. `TurnLoop.run` raises `ObligationOwed`, naming the phase that clears it. The guard opens again once the save is discharged — refusing forever would invent a rule out of a guard, since p. 17 does not say a creature at 0 hit points cannot act |
| 5 — hazard state on `Combatant`, not `Conditions` | **Built.** `Hazards`, with `burning` and nothing else — Suffocation's field would have no consumer while [#178](https://github.com/eddiefiggie/srd-rules-engine/issues/178) is open. It lives in `core.state` rather than `core.hazards` for the reason `DeathSaves` does: that module imports `core.adjudicate`, which imports this one |
| 6 — an outcome may exist without a d20 test | **Built.** `Proposal.test` is optional and `Proposal.outcome` is the branch a testless proposal resolves to; `adjudicate` skips the d20 and still draws a seed and rolls the declared dice. `RULING_VERSION` is 5, recording `testless` rather than leaving replay to infer it from an absent roll, and `ReplayVerdict.NO_ROLL` keeps such a ruling out of `UNREPLAYABLE`. Two shapes are refused outright: a proposal with neither a test nor an outcome, and one with both |
| 7 — Falling does not use the occasion path | **Built** as `core.hazards`, and it needed nothing from this phase — 0023 clause 5 had already decided the case |
| 8 — Dehydration is bookkeeping, Malnutrition is an outcome | **Decided, not built.** [#315](https://github.com/eddiefiggie/srd-rules-engine/issues/315) — Dehydration is bookkeeping on an axis that exists, Malnutrition needs a campaign-axis occasion that does not |
| 9 — ending is event-driven for both turn-based hazards | Nothing to build; it is a constraint on #140 rather than work |

**No effect shape is resolved by any of it.** Coverage stays at 76 of 211 — clause 6 built the capability Falling needs, not Falling, and a capability nothing uses resolves nothing.

_Updated 2026-08-25 as [#170](https://github.com/eddiefiggie/srd-rules-engine/issues/170), Falling and [#124](https://github.com/eddiefiggie/srd-rules-engine/issues/124) landed. This record shipped saying "Decided, not built", which was true for about two hours._
