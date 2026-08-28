# 0036 — A fourth occasion, owed by whoever took the damage

- **Status:** Accepted, 2026-08-26
- **Settles:** [#215](https://github.com/eddiefiggie/srd-rules-engine/issues/215)
- **Requirements:** R1, R4, R17, R29, R30, R31
- **Related:** [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  whose clause 5 is the governing precedent and does not reach this case;
  [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  whose clauses 1-3 are the occasion machinery this extends;
  [0015 — the generator seam already serves reactions](0015-reactions-and-the-agent-seam.md),
  which is why a compelled save is not reaction-shaped;
  [0018 — API stability](0018-api-stability.md), for the additive field on a committed type

## Context

p. 179, *Concentration*, lists three factors that break it. The engine handles two of them
and the voluntary end. The third is the one with no occasion:

> **Damage.** If you take damage, you must succeed on a Constitution saving throw to maintain
> Concentration. The DC equals 10 or half the damage taken (round down), whichever number is
> higher, up to a maximum DC of 30.

`core.spellcasting.concentration_save_dc` and `concentration_save` implement that arithmetic
and are **called by nothing outside their own tests**. The rule is built; the occasion is
missing.

[#215](https://github.com/eddiefiggie/srd-rules-engine/issues/215) names three candidate
shapes and asks which. **Neither of the two constraints that actually decide the shape is in
the issue**, and both were found by reading the tree rather than the document.

### The constraint that decides it

`EncounterState.discharged` is a `frozenset[tuple[str, str]]` of `(actor_id, rule_id)`, and
the turn advance clears it under a comment stating the design:

> An obligation is owed once per turn, so the record of having met it does not outlive the
> turn it belonged to.

Every existing obligation is gated on `(actor_id, RULE_ID) not in state.discharged`. **A
Concentration save is owed once per damage instance, not once per turn.** A creature struck
twice by a Multiattack owes two saves; keyed the existing way, the second is suppressed and
never rolled.

That is a **skip** — a compelled save that silently does not happen — which is the failure
class this product exists to make structurally impossible rather than merely discouraged. It
is also invisible in play: a missed save leaves no trace, the spell simply stays up. So the
existing mechanism cannot be reused unchanged, and any shape that assumed it could would have
discovered this after the design was committed.

### The precedent that does not reach

[0023](0023-the-turns-end-is-a-loop-owned-phase.md) clause 5 already ruled on a
damage-triggered consequence:

> **5. The event-triggered early-out does not use this path.** "The Unconscious condition for
> 1 minute **or until it takes any damage**" (p. 63) **is not a save** and is not end-of-turn.
> It is a state change, and it resolves **where the state change resolves** —
> `EncounterState.with_damage` — which is 0015's precedent applied unchanged: detection
> belongs where the triggering thing happens, not in a catch-all. […] sharing one would force
> the damage path to route through the turn loop.

The literal reading is that Concentration's damage save belongs in `with_damage` too. It does
not, and clause 5 says why in its own second word: *it is not a save*. Concentration's trigger
**is** one, and `with_damage` cannot roll it without `core.state` producing a result — the one
thing R1 forbids regardless of how natural the call site is.

**This record does not revise 0023.** Clause 5 said the two shapes "are genuinely different
mechanisms" and would not force a reopening. It was right; this is the other mechanism
arriving, and it needs a different answer rather than a correction to that one.

### Two further constraints

**The save is owed by the target, who is usually not the acting creature.** Obligations today
are enumerated for `actor_id`, the creature whose turn it is. An attack on the monster's turn
breaks the *player's* Concentration.

**Three phases deal damage, so one discharge point is not enough.** `TurnLoop` adjudicates in
`start_turn`, `run` and `end_turn`. Burning deals damage at the start of a turn (p. 178), so a
burning concentrating creature owes a save during `start_turn`. A design discharging only
after `run` would serve attacks and silently miss the hazard — the same gap as the
once-per-turn one, reached by a different road.

## Options considered

**Option 1 — resolve the save inside `with_damage`.** Rejected, and named so a later reader
does not think 0023 clause 5 was simply overlooked. It is the literal application of that
clause and it would put a d20 roll and a produced result inside `core.state`. R1 admits no
convenient exception: the moment a second API produces an outcome, the invariant the whole
product rests on is a convention rather than a structure.

**Option 2 — a third turn-phase occasion**, enumerating Concentration saves alongside the
start- and end-of-turn obligations. Rejected. It reuses 0027's machinery unchanged, which is
its appeal, and it defers the save by up to a full round — the spell keeps working after the
damage that should have broken it. That is a **wrong** outcome, not a late one, and it also
inherits the once-per-turn keying that the Context section shows is disqualifying.

**Option 3 — a reaction-shaped offer.** Rejected. `core.reactions` exists to *offer*, and
p. 179 compels. `Obligation`'s own docstring states the reason: "a slot in which declining is
expressible is a slot in which the save can fail to happen."

**Option 4 — an effect that schedules a test.** Rejected, and #215 named it precisely so it
would be rejected on purpose rather than drifted into. It would make R1 ambiguous: an effect
that schedules an adjudication is an effect that implies a result, and "no other API produces,
modifies, or **implies** a result" is the requirement's own wording.

## Decision

**1. A fourth occasion, discharged through the one adjudication entry point.**
`TurnLoop.start_turn`'s docstring already states the principle this reuses:

> Nothing here creates a second path to an outcome. It creates a third *occasion* on which the
> existing path is taken.

This is the fourth. The loop synthesises a `Declaration` for each owed save exactly as
`_obligation_declaration` does for turn obligations, and `Adjudicator.adjudicate` produces the
result. R1 holds because nothing else produces one. R4 holds because the engine rolls it.

**2. Detection is in state; production is in the loop.** `EncounterState.with_damage` notices
that the damaged creature is concentrating and records the debt. It does not roll, does not
adjudicate, and does not decide an outcome. This is 0023 clause 5's principle — detection
belongs where the triggering thing happens — with only the rolling half moved to where R1
requires it. The two records agree on where detection lives and differ only on what may
follow it.

**3. The debt is per damage instance, and it is not `discharged`.** Saves owed are held as an
ordered structure keyed by the creature that took the damage, one entry per instance. The
existing `(actor_id, rule_id)` set is left exactly as it is: widening it to carry a count
would make every obligation's once-per-turn semantics depend on a field one rule uses, which
is the shape [0019](0019-kind-is-a-filing-label.md) refuses. Two mechanisms with different
cardinalities are two structures.

**4. Each debt carries the amount its DC derives from.** The DC is a function of *that*
instance's damage, and by the time the loop discharges the save the creature's hit points have
moved — often more than once. The amount cannot be read back off state, so it is recorded when
the damage lands. This is also what keeps R4 intact: the resolver is a closure over a number
the **engine** recorded, never one a caller supplied.

**5. The debt is recorded after defences resolve.** p. 179 says "the damage taken", so a
creature Immune to the type takes none and owes no save. `with_damage` already reasons exactly
this way three lines earlier for the death-save failure — "a creature immune to Fire takes none
and suffers none of it" — and the same ordering is correct for the same reason. Zero damage
owes nothing.

**6. All three adjudicating phases discharge the queue**, through one shared helper rather
than three call sites. Three copies is how one gets missed, and the one that would be missed
is the hazard path, which has no attacker to make the omission obvious.

**7. `TurnOutcome` gains a field, additively.** The consequential rulings must reach a driver:
R30 wants them in the record and R29's narration bounds have to reach the narrator for each.
`TurnOutcome` is on the **COMMITTED** surface, so the field is added with a default and nothing
is removed or renamed. [0018](0018-api-stability.md) clause 4 governs removal and is not
engaged, and `API_VERSION` is not bumped — stated here rather than left to be inferred.

**8. This makes the existing `concentration` claim honest; it does not move the figure.** The
shape is already claimed and `effect_shapes.json` already marks it implemented, so coverage
stays **95 of 209**. What changes is that the claim becomes true in play — see Consequences,
because the state it was in is worth recording.

## Why

**The issue asked "which of three shapes", and the answerable question was different.** All
three of #215's candidates are defensible against the document; none of them survives the
once-per-turn keying, and the issue could not have known that because the constraint lives in
a comment on a turn-advance branch. The lesson is the one 0033 recorded in a different area: the
decisive evidence for a design question is as likely to be in the tree as in the SRD.

**Clause 3 is the clause this record would have got wrong.** Reusing `discharged` is the
obvious move — it is the mechanism for exactly this concept, it is already wired into all
three phases, and adding a rule id to it is a two-line change. It would also have produced an
engine that rolls one Concentration save per turn no matter how many times the caster is hit,
and nothing would have gone red. A wrong design here is indistinguishable from a right one
from the outside, which is the same property that makes a missed skip unmeasurable from play.

**Clause 1 is a smaller change than it looks, and that is the argument for it.** No new path
to an outcome, no new adjudication surface, no change to what a `Ruling` is. The loop already
knows how to turn an obligation into a declaration and hand it to the adjudicator; this adds
a fourth occasion on which it does so. Options 1 and 4 are each *smaller edits* and *larger
architectural changes*, which is the trade this project has consistently refused.

**Clause 5 was nearly wrong in the other direction.** Recording the debt before defences would
compel a save from a creature that took no damage at all — a save that can fail, ending a spell
because of a blow that never landed. The existing comment in `with_damage` is what caught it,
which is an argument for the habit of stating reasoning next to ordering.

## Consequences

**Accepted costs.**

- **A second structure in state with different cardinality from `discharged`.** Two mechanisms
  that both mean "owed" and behave differently is a real cost in comprehension. Clause 3
  accepts it deliberately: the alternative is one structure whose semantics vary by rule id,
  which is worse and is what 0019 refuses.
- **The queue is unbounded.** p. 179 gives one save per instance and states no maximum, so a
  bound would be an invented rule (R31). Named rather than fixed. Debts drain at the next
  adjudication, which is at most one declaration away.
- **A committed type grows a field.** Additive and defaulted, so no consumer breaks, but the
  COMMITTED surface is meant to be slow-moving and this is a change to it.
- **The damage breaker will work while the other three factors still have no consumer.**
  `Concentration.begin`, `.ended` and `.after_conditions` are built and tested and nothing in
  the loop calls them either — a caster has no way to *start* concentrating through a
  declaration. This change therefore leaves a stranger state than it found: the save fires for
  a creature that nothing can put into the state it is being saved for. Filed as
  [#235](https://github.com/eddiefiggie/srd-rules-engine/issues/235) rather than left in prose.

**Follow-on effects.**

- **The `concentration` claim was overstated, and this is the record of it.** Before this
  change `Concentration` was referenced nowhere in `src/` outside its own module — no
  `Combatant` field held one — while `ENGINE_SHAPES` claimed the shape and the inventory marked
  it implemented. `core.duration`'s module docstring asserted it "already ends its own
  effects", a capability with no consumer. That is the decay #228 found in `core.inventory`,
  in a second place: a note that went on being true-sounding for as long as nobody read it. The
  sentence is corrected in this change, and a guard now asserts the **behaviour** rather than
  the reference, because "something calls `Concentration`" is satisfiable by a call that does
  nothing.
- **Coverage does not move.** 95 of 209 before and after.
- **p. 179's "Incapacitated or Dead" is handled for Incapacitated only.**
  `Concentration.after_conditions` reads `concentration_broken` off `Conditions`, and death is
  not a condition in this engine. Not settled here — it belongs with the other breakers in
  [#235](https://github.com/eddiefiggie/srd-rules-engine/issues/235), which names it.

## Evidence

Read in the official SRD v5.2.1 PDF for this record, printed **p. 179**, *Concentration*. The
entry names three breaking factors — **Another Concentration Effect**, **Damage**,
**Incapacitated or Dead** — besides the voluntary end ("The creator can end Concentration at
any time (no action required)"). The Damage sentence is quoted in **Context** and is asserted
as a clause in `scripts/verify_d20_rules.py` as of this change, because the DC is a rule value
and a wrong one is indistinguishable from a right one inside a finished ruling (R31).

In the tree, and these are the findings the decision rests on:

- `EncounterState.discharged` is `frozenset[tuple[str, str]]`; the turn advance resets it with
  the comment "An obligation is owed once per turn, so the record of having met it does not
  outlive the turn it belonged to." Both existing obligations gate on membership.
- `TurnLoop` adjudicates in three methods: `start_turn`, `run`, `end_turn`.
  `start_turn_obligations` enumerates the death save and Burning, both keyed to `actor_id`.
- `Combatant` has no `concentration` field. A sweep for `Concentration` across `src/` finds it
  only in `core.spellcasting` (its definition), `core.duration` (prose) and `core.inventory`
  (the claim).
- `core.state` already imports `SpellSlots` from `core.spellcasting`, and `core.spellcasting`
  does not import `core.state`, so holding a `Concentration` on `Combatant` introduces no
  cycle. Checked during planning rather than discovered during implementation.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — a fourth occasion through the one entry point | **Built.** `TurnLoop._concentration_saves` drains the queue via `_obligation_declaration` and `Adjudicator.adjudicate`; no new path to an outcome. The rule and resolver are **`core.concentration`**, not `core.spellcasting` as the plan said: a resolver takes an `EncounterState`, and `core.state` already imports *from* `core.spellcasting`, so putting it there inverts that edge into a cycle. `core.save_ends` is the same shape for the same reason |
| 2 — detection in state, production in the loop | **Built.** `EncounterState.with_damage` records; it rolls nothing and returns no result of its own |
| 3 — per damage instance, not `discharged` | **Built.** A separate ordered structure keyed by the damaged creature; `discharged` is unchanged. Guarded by a test asserting two instances in one turn owe two saves |
| 4 — each debt carries its amount | **Built.** Recorded at damage time. The resolver **reads it back off the debt** rather than closing over it, which the clause's wording anticipated poorly: resolvers are registered per rule id, so a closure would need one rule per damage total, with a number inside an identifier. Reading it back also leaves one number in one place, so the roll and the record cannot disagree — and it is still a number the *engine* recorded, which is the half R4 turns on |
| 5 — recorded after defences | **Built.** Immunity to the damage type owes no save; guarded |
| 6 — all three phases discharge | **Built** through one shared helper, called at the **top of each pass** of the two obligation loops rather than after them — so the pass that finds nothing pending still discharges what the previous one incurred, and a phase with no obligations of its own drains a queue an earlier one left. Guarded by the Burning-at-turn-start case |
| 7 — `TurnOutcome` gains a field additively | **Built**, as three: `consequential`, `consequential_narrations` and `unresolvable`. The clause said one because it was counting the rulings and had not counted their narrations (R29 owes one per ruling) or the ruleset gap `TurnStart` and `TurnEnd` already name. All defaulted; no name removed or renamed; `API_VERSION` unchanged |
| 8 — the claim becomes honest, the figure does not move | **Built.** Coverage 95 of 209 before and after; a behavioural reachability guard replaces the assertion, and `core.duration`'s stale sentence is corrected |

**Two defects the corruption proofs found, both fixed in this change and neither visible to
review.** They are recorded here because each is an argument for the procedure rather than a
detail of this rule. First, p. 179's DC floor and cap were **pinned to nothing**: every
assertion in `tests/test_spellcasting.py` compared against `CONCENTRATION_DC_FLOOR` and
`CONCENTRATION_DC_CAP` rather than against 10 and 30, so a floor of 11 left the entire file
green — the plan asked for that corruption to be proved red and it was not. Second,
`scripts/prove_guard_red.sh` restored the source and not its bytecode, so a same-size
corruption (`30` -> `31`) restored inside the same second the corrupt run compiled in left a
`.pyc` CPython still considered current: `git diff` read clean while the **engine** went on
running the corrupt constant.

**The unbuilt breakers are filed rather than left in prose**:
[#235](https://github.com/eddiefiggie/srd-rules-engine/issues/235) holds starting Concentration
from a declaration, and p. 179's "or Dead".

**#215 is closed with the occasion built** — the rule was never missing, only the moment it
applies.

_Written 2026-08-26 against SRD v5.2.1._
