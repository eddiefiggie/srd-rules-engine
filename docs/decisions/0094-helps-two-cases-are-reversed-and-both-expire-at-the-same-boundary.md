# 0094 — Help's two cases are reversed, and both expire at the same boundary

- **Status:** Accepted, 2026-09-12
- **Settles:** [#434](https://github.com/eddiefiggie/srd-rules-engine/issues/434)
- **Requirements:** R14, R17, R31, R32
- **Related:** [0049 — advantage that outlives its roll](0049-advantage-that-outlives-its-roll.md),
  whose `PendingAdvantage` this widens and whose reversed-axes reading it repeats;
  [0093 — a readied spell is cast, and what waits is its
  effect](0093-a-readied-spell-is-cast-and-what-waits-is-its-effect.md), which settled the
  one-action-two-cases reading a day earlier and whose refusal idiom clause 6 reuses;
  [0087 — a move is a path through spaces](0087-a-move-is-a-path-through-spaces-and-a-turn-ended-in-one-is-prone.md),
  which built the ally relation clause 4 turns out to need;
  [0061 — a shape resolves, and a clause may not](0061-a-shape-resolves-and-a-clause-may-not.md),
  for why `help` stays unclaimed while a stated case refuses

## Context

p. 182-183, *Help [Action]*, whole — the entry spans the page break and the constraints are in
the continuation:

> When you take the Help action, **you do one of the following**.
>
> **Assist an Ability Check.** Choose one of your **skill or tool proficiencies** and one ally
> who is near enough for you to assist verbally or physically when they make an ability check.
> That ally has **Advantage on the next ability check they make with the chosen skill or
> tool**. This benefit **expires if the ally doesn't use it before the start of your next
> turn**. The GM has final say on whether your assistance is possible.
>
> **Assist an Attack Roll.** You momentarily distract an enemy **within 5 feet of you**, giving
> Advantage to the next attack roll **by one of your allies** against that enemy. This benefit
> **expires at the start of your next turn**.

#434 asked whether `PendingAdvantage` can carry an unassigned holder and a non-target scope, or
whether Help is a second mechanism. It is one mechanism; the gate's three mismatches come to
two, one of them is smaller than it looked, and one of the two things the gate set apart turns
out to be a single thing seen twice.

## Options considered

**Option 1 — Help is a second mechanism, beside `PendingAdvantage`.** Rejected. Two mechanisms
that both grant a held Advantage spent by a later roll would have to agree with each other
forever about liveness, spending and sweeping — and 0049 derived liveness rather than
retiring it precisely so there would be one answer. A second mechanism re-opens that.

**Option 2 — add `holder_id: str | None` and `against_skill: str | None` to
`PendingAdvantage`.** Rejected, and it is the option the gate was written to fear: a fourth and
fifth nullable field on a token that has none, arriving one PR at a time, each legal
combination of the two a state nobody enumerated. It also puts two fields where one question
is asked — a token would carry both `against_id` and `against_skill` with a rule, written
nowhere, that exactly one is set.

**Option 3 — widen two fields into two closed vocabularies.** Chosen. Same axis count as
0049, no nullable pair, and the illegal combinations stop being representable rather than
being forbidden by a comment. See clause 3.

**Option 4 — ship neither case until tools are modelled.** Rejected. It treats a refusal as
though it were an overstatement, and they are opposites; see clause 6.

## Decision

**1. Help is one mechanism with two cases.** p. 183: "When you take the Help action, **you do
one of the following**." That is the same sentence shape as p. 186's Ready, and 0093 clause 4
settled the reading a day earlier — the document states one action and then says what changes
per case. This record does not re-derive it.

**2. The two cases are reversed, and that is the 0049 pattern rather than a bag of fields.**

| | Assist an Ability Check | Assist an Attack Roll |
|---|---|---|
| Holder | **named** — "one ally who is near enough" | **unnamed** — "by one of your allies" |
| Scope | a **skill or tool** | an **enemy** |
| Expires | start of the helper's next turn | start of the helper's next turn |

Two axes reversed and the third shared. 0049 found Vex and Sap reversed on all four; this is
the same finding one axis shallower, and it is the argument for one mechanism rather than
against it.

**3. `holder` and `scope` each become a closed vocabulary, replacing `holder_id: str` and
`against_id: str | None`.** A holder is *this creature* or *the allies of this creature*; a
scope is *attacks against this creature*, *any attack*, or *ability checks with this skill*.
Vex, Sap and both Help cases are then four points in one space with **no nullable field
between them**, and the combinations the document never states — an ability-check scope held
by "any ally of nobody" — are unrepresentable rather than merely unwritten.

This is the move `TurnBoundary` already makes, and its reason is stated in
`core.turn_span`: a vocabulary rather than a boolean, "because the two are mutually exclusive
and a `bool` at a call site reads as neither". The principle is in the tree, not in a record
(see Evidence).

**4. The unassigned holder needs no new state, because the ally relation already exists.**
`EncounterState.are_allies` is built (0087), reading a stated side off both creatures and
refusing to guess when either lacks one. "One of your allies" resolves through it **at the
moment of spending**, which is where scope has always been resolved — `applies_to` is already
a question asked of a roll rather than a field read off a creature. The gate called an
unassigned token "a new axis"; it is the axis `against_id is None` already had, applied to the
other end.

**5. Which ally gets it needs no arbitration rule either.** 0049's *"spent, not merely
expired"* already decides it: the first roll in scope consumes the token. p. 183 says "the
**next** attack roll by one of your allies", and "the next" is exactly what spending means.
A rule for choosing among allies would be a rule the document does not state (R31).

**6. Both expiries are the same boundary, and the gate was wrong that they differ.** #434 notes
them as "not the same" — one expiring *if unused before* the start of your next turn, the other
*at* it. Both name the start of the helper's next turn and both die there; the first is phrased
as a condition on use and the second as a moment, which is one boundary described from two
sides. `TurnBoundary.START` with `expires_after_actor_id` set to the **helper** carries both,
and nothing new is needed.

**7. Assist an Ability Check ships for skills and refuses for tools, with its reason.** p. 183
says "skill **or** tool" and `core.skills` does not model tools. The skill half is fully
resolvable; the tool half refuses, naming what is not modelled. This is 0093 clause 5's idiom.

**8. A refusal is not the overstatement #371 and #264 found.** The gate reads a skills-only
build as "a rule stated at half", and it would be — *if the tool half were silently absent*.
An overstatement is claiming a completeness you do not have; a refusal that names the missing
half is the opposite move, and it is the only one that makes the gap visible at the point of
use rather than in a document nobody re-reads.

**9. `help` stays unclaimed while clause 7 refuses**, so coverage does not move when the
mechanism lands. Narrower than 0061's disclosed-clause instrument, which counts sentences
inside a shape that does resolve.

**10. "Near enough to assist", "the GM has final say", and "within 5 feet" are settled
already.** The first two are narrative judgements the caller states, as it states a rest's
interruption and a Cover degree; the third is the reach machinery. The gate agreed, and this
records it so it is not re-asked.

## Why

**The gate's three mismatches were one real widening, one relation already built, and one
sentence read twice.** Taken at face value they argue for a second mechanism: three things
`PendingAdvantage` cannot do is a lot for one token to absorb. Checked against the tree, the
unnamed holder needs `are_allies`, which exists; the two expiries are one boundary; and what
is left is a single question — can one token scope to something other than a target — which is
the widening clause 3 makes. **A count of mismatches is not a measure of distance until each
one has been checked against the code**, and two of these three dissolved on contact.

**Option 2 is the one that would have been taken by default,** because each field is
individually reasonable and arrives attached to a real requirement. The thing that makes it
wrong is only visible when both are present: two nullable scope fields with an unwritten rule
that exactly one is set, which is a state machine kept in prose. 0049's virtue was that it
had no such field, and preserving that is worth more than the smaller diff.

**Clause 8 is the restraint, and it points the other way from the gate's.** #434 invokes two
issues that found overstatements, and the inference — build nothing until everything is
modelled — would have held p. 186's Ready back too. The distinction that matters is not how
much of a rule is built but whether the unbuilt part is **audible**: #371's quotation and
#264's object both looked finished, which is why they cost something. A refusal cannot look
finished.

## Consequences

**Accepted costs.**

- **`PendingAdvantage` changes shape**, and Vex and Sap move with it. Two working mechanics are
  touched to admit a third — the cost of clause 3 over clause 2's additive fields, and the
  reason 0049's tests are the ones that must go red first.
- **`help` stays unclaimed after the mechanism lands** (clause 9), the same cost 0093 accepted
  for `ready`. Coverage does not move; the mechanism does.
- **A caller assisting with a tool gets a refusal**, and will until tools are modelled.

**Follow-on effects.**

- Coverage does not move: **146 of 210**. No shape resolves and none is added.
- 0049 is widened rather than superseded; its four-axis reading is what clause 2 extends.
- Two of the gate's three mismatches are recorded as dissolved, so a later reader does not
  re-derive them from the issue body.

## Evidence

Read in the official SRD v5.2.1 PDF, pp. 182-183:

- **p. 182-183**, *Help [Action]*, whole and including the continuation past the page break —
  quoted above and verified verbatim against the document rather than from the issue body.
- The two expiry sentences clause 6 rests on, read side by side in the document: "expires if
  the ally doesn't use it before the start of your next turn" and "expires at the start of your
  next turn".

Engine side, read at `7630b01`:

- `core.pending_rolls.PendingAdvantage` carries `holder_id: str` and `against_id: str | None`,
  and `applies_to(attacker_id, target_id)` resolves scope at spend time — clause 4.
- `PendingAdvantage`'s docstring states *"spent, not merely expired … the first roll in scope
  consumes it"* — clause 5.
- `EncounterState.are_allies` exists and refuses to guess when either creature lacks a stated
  side — clause 4.
- `core.turn_span.TurnBoundary` holds `START` and `END` — clause 6.
- `core.skills` states that saving throws and tools are not modelled — clause 7.

**One citation checked and found wrong.** `core.turn_span` attributes the vocabulary-rather-than-
boolean rule to 0019, and 0019 is about the effect-shape inventory's `kind` field and says
nothing about booleans. The principle is sound and is stated in that docstring; the record
number is not its source, so clause 3 cites the tree rather than repeating the attribution.
Filed as [#472](https://github.com/eddiefiggie/srd-rules-engine/issues/472).

No guard was proved red for this record, because it adds no code. The corruption proofs belong
to the change that builds clauses 3 through 9.

## Status of implementation

**Decided, not built.** A gate closes by producing this record; the work it scopes is filed.

| Clause | State |
|---|---|
| 1 — Help is one mechanism with two cases | **Decided.** 0093 clause 4's reading, applied |
| 2 — the two cases are reversed | **Decided.** A reading of the document; nothing to build |
| 3 — `holder` and `scope` become closed vocabularies | **Decided, not built.** [#471](https://github.com/eddiefiggie/srd-rules-engine/issues/471) |
| 4 — the unassigned holder resolves through `are_allies` | **Decided, not built.** [#471](https://github.com/eddiefiggie/srd-rules-engine/issues/471); the relation is built |
| 5 — the first roll in scope spends it | **Decided.** 0049 already built spending; this names it as sufficient |
| 6 — both expiries are `TurnBoundary.START` | **Decided, not built.** [#471](https://github.com/eddiefiggie/srd-rules-engine/issues/471); the vocabulary is built |
| 7 — skills ship, tools refuse with their reason | **Decided, not built.** [#471](https://github.com/eddiefiggie/srd-rules-engine/issues/471), and the refusal comes off when tools are modelled ([#473](https://github.com/eddiefiggie/srd-rules-engine/issues/473)) |
| 8 — a refusal is not an overstatement | **Decided.** The reasoning behind clause 7 |
| 9 — `help` stays unclaimed while clause 7 refuses | **Decided, not built.** [#471](https://github.com/eddiefiggie/srd-rules-engine/issues/471); the shape is claimed by [#473](https://github.com/eddiefiggie/srd-rules-engine/issues/473) |
| 10 — nearness, GM say-so and 5 feet are settled | **Decided.** Caller-stated and the reach machinery, both built |
