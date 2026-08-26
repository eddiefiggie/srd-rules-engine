# 0032 — An effect may be conditional on what a sibling effect turned out to be, and the only honest place to ask is where the damage settles

- **Status:** Accepted, 2026-08-25
- **Settles:** the design question in
  [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173), which stays open as the
  defect it also describes
- **Requirements:** R1, R4, R5, R7 · touches R14, R31, R32
- **Related:** [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  whose clause 6 moved the proposal shape for the same module and the same reason;
  [0019 — kind is a filing label](0019-kind-is-a-filing-label.md);
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  which is what the engine is doing *instead* of this today

## Context

p. 182, *Falling*: "When the creature lands, it has the Prone condition **unless it avoids
taking any damage from the fall**."

`falling_resolver` returns `Proposal(outcome=(damage, *prone))`, and the `prone` member is
decided **before the dice are thrown**. Two of the three ways to take no damage are decidable
there and are decided — a fall under 10 feet is refused outright, and Immunity to Bludgeoning
withholds the Prone. The third is not: p. 17 halves and rounds down, so a creature with
Resistance that rolls a 1 on a single die takes 0 damage and by p. 182 should not be Prone.
**This engine makes it Prone**, disclosed in `core/hazards.py` and filed as #173.

#173 asked the question this record answers:

> Worth checking whether anything else in the SRD wants that shape before building it for one
> 1-in-6 case on one hazard. If nothing does, the honest resolution may be to leave this
> disclosed and close the issue as such.

### The document was swept, and the answer refines the question

Seven rules make something depend on damage already dealt. They are **not one shape**, and an
earlier comment on #173 said "seven places" without separating them — corrected here, because
building one mechanism for all seven would over-build three different things.

| Page | Rule | Keys on | Produces | Shape |
|---|---|---|---|---|
| 182 | Falling | damage taken > 0 | whether Prone applies | **predicate** |
| 18 | Damage at 0 Hit Points | amount, criticality, amount vs HP max | which effects, how many | **predicate** |
| 124 | Disintegrate | "if this damage reduces it to 0 Hit Points" | whether effects apply | **predicate** |
| 314 | Phase Spider, Bite | the same sentence | whether effects apply | **predicate** |
| 311 | Green Hag, Dream | damage taken | *how much* HP maximum is lost | **magnitude** |
| 179 | Concentration | damage taken | *the DC of a further save* | **a second test** |
| 180 | Damage Threshold | amount vs threshold | *the damage itself* | **a defence** |

So the predicate shape recurs five times, and the other two are different problems that merely
share a page of evidence. p. 180 says "**Immunity** to all damage unless…", which places it
beside p. 17 rather than here ([#214](https://github.com/eddiefiggie/srd-rules-engine/issues/214)).
p. 179 needs a further D20 test rather than an effect, and R1 puts exactly one adjudication
behind one declaration ([#215](https://github.com/eddiefiggie/srd-rules-engine/issues/215)).

**A near-miss worth naming, because there are about twenty of it.** Sleep (pp. 163, 167), the
Frightened aura on p. 55, Hold Person (p. 141), Modify Memory (p. 150), several dragons'
Frightful Presence (pp. 268-269), the Torpor and Midnight Tears poisons (p. 198) and more all
read *"the condition ends if the target takes damage"*. Those are **duration terminators** — a
later, separate damage event ending an already-applied condition. `core.duration` territory.
Counting them here would make this shape look four times commoner than it is and would build
the wrong thing.

### The engine is closer to this than #173 says, and further than it looks

> An effect that is conditional on what a *sibling* effect turned out to be. The engine has no
> such shape.

True of `Effect` and of `Proposal`. **Not true of the state transition.**
`EncounterState.with_damage` already branches on the settled amount, and says so:

> Defences resolve before anything else looks at the number. Everything downstream — the death
> save failure for "any damage", and Massive Damage's remainder — is about damage *taken*.

`if amount == 0 or reduced.hit_points > 0 …: return state` is p. 18's "if you take any damage",
evaluated after defences — **the identical predicate p. 182 needs**. The capability exists. What
is missing is any way for a *resolver* to reach it, which is why p. 18 is hard-coded in a state
method and Falling's Prone is decided in a resolver that cannot see a number.

### There are three moments, and only one of them is right

    resolver          →  _branch()  →  _roll_declared()  →  _apply()
    no number yet                      ROLLED number        TAKEN number
    (Falling decides here)             (pre-defences)       (post-defences, per effect)

`_apply` already computes `state.damage_after_defences(...)` for each damage effect, to rewrite
the reported amount to what landed (#105). **The number a conditional needs is already in hand,
in a loop that is already iterating the siblings in order.**

The middle moment is the trap. It has *a* number, and using it would look correct and be wrong
in exactly the case #173 is about: Resistance is the entire difference between rolled and taken.

## Options considered

**Leave it disclosed and close #173.** Rejected — this was the option #173 offered conditionally,
and the condition failed. Five instances is not one 1-in-6 case on one hazard.

**Push it into the state transition, as p. 18 already is.** Rejected. It is where the number
lives, but `with_damage` would grow a parameter per rule, and every such rule becomes
inexpressible by the resolver that owns it. p. 18 is the evidence: it is correct, and it is
correct *in the wrong place* — no proposal can state it, so no ruling can cite it, and a reader
of `core.death` cannot find it.

**A conditional evaluated in `_roll_declared`.** Rejected on the rolled-versus-taken distinction
above. It is the cheapest option and it fails the only case that motivated the record.

**Call the resolver a second time with the settled effects.** Rejected. It is the most general
option, and it breaks the promise that a proposal is a complete statement of what follows: a
resolver invoked twice may roll different dice, and R5's record would have to say which
invocation produced what. 0027 clause 6 met the same fork and moved the *shape* rather than the
*protocol*, which is the precedent.

**A callable predicate carried on the proposal.** Rejected, and it is the option that looks most
natural — `Resolver` is already "code, not data", so a lambda in a `Proposal` breaks no rule.
It breaks something else: **a callable cannot be recorded.** R5 makes the ledger the record of
what the engine decided, and this project's habit is to record the question as well as the
answer — `Sight.because`, `unenforced_clauses`, `Replay.detail`. A withheld Prone that leaves no
trace is indistinguishable from a Prone nobody considered, which is the exact confusion #173's
disclosure exists to prevent.

## Decision

**1. An effect may be declared conditional on a predicate over what a sibling effect settled
to.** The proposal states the predicate; the engine evaluates it. A resolver never supplies the
number and never supplies the answer, which is R4 in the same form `DamageDice` gives it — a
resolver that could state the amount could state the outcome.

**2. The predicate is evaluated in `_apply`, against the damage *taken*, never the damage
rolled.** Post-defences, per effect, in sibling order — a conditional keys on effects already
applied earlier in the same ruling. This clause is the whole of #173: p. 17's Resistance is the
difference between the two numbers, and the middle moment is wrong precisely where it matters.

**3. The predicate is data, not a callable**, from a vocabulary that grows one entry at a time,
each entry carrying the SRD sentence it serves and that sentence asserted in
`scripts/verify_d20_rules.py`. Data because clause 4 requires it to be recordable, and one at a
time because a vocabulary invented ahead of its rules is a vocabulary invented from memory of a
game (R31).

**4. A conditional that does not fire is recorded, not silently absent.** The ruling states that
the engine asked, which predicate it asked, and what the answer was. R5's record is what
separates "the rules withheld this" from "nobody thought of it", and the second is what this
engine exists to make impossible.

**5. A conditional effect's claim may not appear in the proposal's static `may_claim`.**
`_bounds` is built from the proposal *before* `_apply` runs, so a bound naming a conditional
effect would license a claim the conditional may have withheld. The standing bound already
covers the honest case — "that the effects recorded here happened" — so a conditional's positive
claim needs no bound at all, and its `may_not_claim` must not assert the branch either. This is
R7 being advisory *and correct*, rather than advisory and stale.

**6. The vocabulary is predicates only. An effect whose magnitude derives from a sibling is out
of scope**, and is filed as [#216](https://github.com/eddiefiggie/srd-rules-engine/issues/216)
rather than left to look overlooked. One instance (p. 311), unreachable — the bestiary is not
shipped (#21) — against five for the predicate shape.

**7. p. 18 is not migrated as part of this.** It is correct where it is, and moving a built,
tested rule to prove a mechanism is a change whose only benefit is tidiness. It becomes
expressible; whether it is re-expressed is a separate decision with its own risk.

## Why

**The taxonomy is the load-bearing part, not the mechanism.** "Seven rules want this" would have
justified building one general thing. Seven rules want *three* things, and two of them belong
somewhere else entirely — a defence beside p. 17, and a further test behind R1. Getting that
wrong would have put a damage threshold outside the one place defences are applied, which
`with_damage` is explicit is the thing that must not happen.

**Clause 2 is the clause #173 is actually about**, and it is one word: *taken*. Every other
design here would work with the rolled number and would ship the same bug in a more elaborate
form. That the loop already holds the taken number, for a different reason (#105), is what makes
this small.

**Clause 3 costs generality on purpose.** A callable would express every predicate in the
document today and every one it might add. It would also make the ledger unable to say what was
asked — and this project has repeatedly chosen the recordable answer over the general one:
`Obstruction.blocks_sight` is a field rather than a rule (0029), `Visibility.UNSTATED` is a
value rather than an exception (0025), and the build line is prose in a guarded file rather than
a changelog nothing checked (0024).

**Clause 5 is the one a reviewer would miss.** The bounds are built from the proposal, so making
an *effect* conditional silently makes a *claim* wrong. Falling gets away with it today only
because immunity is decidable at proposal time and the resolver branches its `may_claim` on it.
The moment the branch moves later than the bounds, that trick stops working.

## Consequences

**Accepted costs.**

- **The predicate vocabulary will be incomplete for as long as the document is unread.** That is
  clause 3 working, not failing: an entry arrives with its sentence, or it does not arrive.
- **Two engines of conditionality will coexist** — this one, and p. 18's inside `with_damage` —
  until somebody decides clause 7 the other way. Named here so it reads as a choice rather than
  as drift.
- **This does not make Falling correct.** It decides how to make it correct. #173 stays open,
  and the disclosure in `core/hazards.py` stays accurate until it closes.

**Follow-on effects.**

- Nothing in this record is built. #173 is the tracker for clauses 1-5 reaching the tree, and
  Falling is their first and smallest instance.
- [#214](https://github.com/eddiefiggie/srd-rules-engine/issues/214) — Damage Threshold, as a
  defence.
- [#215](https://github.com/eddiefiggie/srd-rules-engine/issues/215) — Concentration's DC, as a
  further test.
- [#216](https://github.com/eddiefiggie/srd-rules-engine/issues/216) — clause 6's magnitude
  derivation.
- Coverage is unchanged at **91 of 211**. A record resolves no shape.

## Evidence

Every sentence in the table was read in the official SRD v5.2.1 PDF for this record, not taken
from the issue that reported it. The sweep matched
`avoids taking any damage|takes no damage|if .* takes any damage|if the damage|damage reduces .* to 0`
across all 364 pages; the twenty duration terminators are that sweep's other half, separated by
reading rather than by pattern.

In the tree, read rather than recalled:

- `core/hazards.py`, `falling_resolver`: `outcome=(damage, *prone)`, with `prone` chosen from
  `actor.defences.is_immune_to(DamageType.BLUDGEONING)` before any die is thrown, and
  `may_claim` branching on the same flag — which is clause 5's precedent and its limit.
- `core/adjudicate.py`, `_roll_declared` → `_apply`: the rolled amount and the taken amount are
  produced in different functions, and `_apply` already calls `damage_after_defences` per effect
  to rewrite the reported number (#105).
- `core/adjudicate.py`, `_bounds(proposal, result)`: built from the proposal, before `_apply`.
- `core/state.py`, `with_damage`: p. 18's three branches on the settled amount, and the comment
  stating that defences resolve before anything else looks at the number.
- `core/spellcasting.py`, `concentration_save_dc`: built, tested, and called by nothing outside
  its own tests.

## Status of implementation

**Decided, not built.** No clause of this record is in the tree, and #173 — the defect that
prompted it — is deliberately still open.

| Clause | State |
|---|---|
| 1 — an effect may be conditional on a sibling's settled damage | **Not built.** [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173) |
| 2 — evaluated in `_apply`, against damage *taken* | **Not built**, and it is the clause #173 turns on. The number is already computed there for a different reason (#105) |
| 3 — the predicate is data, from a vocabulary that grows one sentence at a time | **Not built.** The first entry is p. 182's "unless it avoids taking any damage" |
| 4 — a conditional that does not fire is recorded | **Not built.** The ruling payload records effects that landed and has no shape for one considered and withheld |
| 5 — a conditional's claim stays out of static `may_claim` | **Not built**, and it is a constraint on how 1-4 are built rather than a thing of its own. `falling_resolver` currently does the opposite, legitimately, because its branch is decided at proposal time |
| 6 — predicates only; magnitude derivation is out of scope | **Decided.** Filed as [#216](https://github.com/eddiefiggie/srd-rules-engine/issues/216) |
| 7 — p. 18 is not migrated | **Decided.** `with_damage` is unchanged and stays correct where it is |

**Two findings left this record for issues of their own**, because they are not this shape:
[#214](https://github.com/eddiefiggie/srd-rules-engine/issues/214) (Damage Threshold is a
defence, p. 180) and [#215](https://github.com/eddiefiggie/srd-rules-engine/issues/215)
(Concentration's DC is a further test, p. 179). Both were found by the sweep that produced the
table above, and both would have been built wrongly had the seven been treated as one shape.

_Written 2026-08-25 against SRD v5.2.1._
