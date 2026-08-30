# 0066 — A move that brings someone with it

- **Status:** Accepted, 2026-08-30
- **Settles:** [#340](https://github.com/eddiefiggie/srd-rules-engine/issues/340)
- **Requirements:** R15, R19, R30, R31, R32
- **Related:** [0055 — a creature moved by something other than itself](0055-a-creature-moved-by-something-other-than-itself.md),
  whose reasoning about what a forced move does *not* cost is reused here;
  [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which is why this lives in `with_movement`;
  [0051 — a size is stated, or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md), whose
  `Size | None` is what makes the exemption a three-way question;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md)

## Context

p. 182, *Grappled*, third clause:

> **Movable.** The grappler can drag or carry you when it moves, but every foot of movement
> costs it 1 extra foot unless you are Tiny or two or more sizes smaller than it.

Disclosed as `grappled-creature-is-movable-by-the-grappler` since [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335)
built the grapple's endings, for two stated reasons: **movement moved the mover**, and the
exemption is a size comparison the engine could not make. `Combatant.size` arrived with
[0051](0051-a-size-is-stated-or-it-is-unknown.md) and removed the second. The first was still
true this morning: `with_movement` advanced one creature, and a grappled creature has Speed 0,
so the carrying could not be modelled as the passenger moving itself.

Three questions the sentence does not answer, and each had to be decided before any of it
could be built.

## Options considered

### Where the passenger ends up

The document says "drag or carry" and says nothing about the result.

**Option 1 — the passenger lands where the grappler was.** Rejected. It is a *trailing* rule,
and it is a rule: nothing on p. 182 says a dragged creature follows in the grappler's
footsteps rather than being carried beside it, and a five-foot grapple would become a
zero-foot one on every move.

**Option 2 — the caller states where the passenger goes.** Rejected for R1's reason applied to
state: a caller choosing where a creature ends up is a caller choosing an outcome, one move at
a time. Every other position this engine produces is computed.

**Option 3 — translate the passenger by the grappler's displacement.** Chosen. It is the only
answer that **preserves the distance between the two** rather than inventing one, and the
distance is a fact p. 182 itself reads: "the condition also ends if the distance between the
Grappled target and the grappler exceeds the grapple's range." An implementation that changed
that distance on every move would be quietly deciding when grapples end.

### Whether the extra foot stacks with Difficult Terrain

**Option 1 — it replaces, as the climb parenthetical does.** Rejected. The climb rule is read
as replacing because *the document itself prints the combined number*: "1 extra foot (2 extra
feet in Difficult Terrain)". *Movable* prints no such parenthetical, so there is no sentence to
read as replacing.

**Option 2 — it adds.** Chosen, with the evidence named: Difficult Terrain carries its own
non-cumulative clause — "it isn't cumulative; either a space is Difficult Terrain or it isn't"
— and *Movable* carries none. A document that says so where it means it has not said so here.
The same reasoning gives a second carried creature its own extra foot: two grappled creatures
have two *Movable* clauses, each charging one.

### What an unstated size does to the exemption

**Option 1 — an unstated size is exempt.** Rejected. It grants an exception on no evidence and
does so in the caller's favour, silently.

**Option 2 — an unstated size is not exempt, so the extra applies.** Chosen, and it is not
0030's tiebreak — it is the difference between a rule and its exception. p. 182 states the
extra foot as **what happens**, and names two facts that lift it. A fact the ruleset never
stated is not one of them, so the exception is simply not made out. Nothing about the creature's
size is decided; the engine declines to find an exemption it was given no grounds for.

## Decision

**1. A carry is a parameter of the grappler's move.** `with_movement(..., carrying=(...))`,
naming the grappled creatures that come along. p. 182 makes it optional — "the grappler
**can** drag or carry you" — so it is a declaration of the same kind as `mode`, not an outcome.
[0056](0056-a-move-is-refused-where-it-is-made.md) is why it lives here rather than at a new
entry point.

**2. Passengers are translated by the grappler's displacement**, preserving the distance
between them exactly.

**3. Each carried creature not carried free adds one extra foot per foot to the *grappler's*
cost.** "every foot of movement costs **it** 1 extra foot" — the cost is the mover's, and
`movement_cost` gained a `carrying` count rather than a boolean so that two passengers charge
two feet.

**4. The extra adds to Difficult Terrain's and to a climb's**, on the evidence above.

**5. Nothing is spent by the passenger and nothing is provoked**, for
[0055](0055-a-creature-moved-by-something-other-than-itself.md)'s reason. A carried creature
has Speed 0 and uses none of the four things p. 185 provokes an Opportunity Attack on — "its
action, its Bonus Action, its Reaction, or one of its speeds".

**6. A Frightened passenger may be carried toward what it fears.** p. 182 refuses a move that
closes on the source of fear only when it is made **willingly**, and being carried is not
willing. The refusal is on the mover, and the mover is the grappler.

**7. Two exemptions, and an unstated size makes out neither.** `carried_without_extra_cost`,
with Tiny absolute — a Tiny creature is carried free by a Gargantuan and by another Tiny,
because the sentence says so without qualification — and "two or more sizes smaller" answered
by `Size.categories_above`.

**8. Three refusals, each a fact rather than a judgement.** A creature not in the encounter, one
the mover is not grappling, and one nobody placed. The last matters because carrying translates
a position and there is none to translate; a move made approximately is not a move this engine
makes.

**9. The disclosure came off in this change.** `MOVABLE_UNENFORCED` is deleted, not merely
unreferenced, and `Condition.GRAPPLED` now discloses nothing: all three of p. 182's clauses are
built and none of them is a flat field on `ConditionEffects`.

## Why

**Clause 2 is the one worth the record.** The other two readings are arithmetic and can be
re-derived from the page; where a dragged creature ends up cannot, because the page does not say.
What makes the displacement reading right is not that it feels natural — it is that the distance
between grappler and passenger is a number the engine *already reads*, in `_out_of_range`, to
decide whether the grapple has ended. Any other answer makes carrying a creature a way of
ending the grapple that carries it, which is the kind of consequence an implementation ships
without noticing.

**Clause 7 is the clause an audit would come back to.** "Unstated means not exempt" looks like
the engine deciding the creature is large, and it is not: the engine decides nothing about the
size, it declines to find an exception. The distinction is the same one
[0063](0063-training-is-a-legality-rule.md) drew for armour training and
[0039](0039-equipment-is-what-a-creature-holds-wears-and-carries.md) drew for hands — the
direction that cannot invent something nobody stated.

**Clause 5 costs nothing to state and would cost a lot to get wrong.** A carried creature
leaving somebody's reach looks exactly like a creature walking out of it, and p. 185's four
named routes are the whole of what provokes. 0055 settled this for a shove; the same sentence
settles it for a drag, and saying so here means the next forced-movement mechanic does not
re-derive it.

## Consequences

**Accepted costs.**

- **`with_movement` grows a third keyword**, after `mode` and `difficult_terrain`. It is now
  the place four separate rules refuse a move and one adds a passenger, which is what
  [0056](0056-a-move-is-refused-where-it-is-made.md) chose deliberately and is worth watching.
- **Two readings are taken that the document does not settle**, both named in
  `movement_cost`'s docstring beside the climb reading that was already there. A future
  errata could contradict either.
- **`_replacing` now takes several combatants.** A small widening, and the first transition in
  this engine that changes two creatures at once.
- **Nothing offers a carry at the read surface**, because movement is not in the action menu at
  all. A caller driving `with_movement` learns about `carrying` from the signature, which is
  the same way it learns about `mode`.

**Follow-on effects.**

- **`Condition.GRAPPLED` discloses nothing at all**, and the pinned disclosure set shrinks from
  18 clauses to 17. [#292](https://github.com/eddiefiggie/srd-rules-engine/issues/292)'s pin is
  what makes that a deliberate edit rather than a quiet one.
- **[#337](https://github.com/eddiefiggie/srd-rules-engine/issues/337) is unaffected and worth
  naming.** A creature still occupies no space, so a carry can put two creatures on the same
  point. That was already true of every move and this does not make it worse.
- **Coverage does not move.** *Movable* is a clause under a shape already claimed
  ([0061](0061-a-shape-resolves-and-a-clause-may-not.md)).

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 182** (*Grappled* in full, and
*Grappling*'s "One Grapple per Hand", which is why two passengers are reachable), **p. 181**
(*Difficult Terrain*, for the non-cumulative clause that is the evidence for clause 4),
**p. 185** (*Opportunity Attacks*, for the four routes clause 5 turns on), **p. 188** and
**p. 14** (the six size categories and their ordering).

The existing p. 182 *Movable* verifier clause is retained and its description updated; the
suite still verifies 281 clauses.

## Status of implementation

**All nine clauses are built** by [#340](https://github.com/eddiefiggie/srd-rules-engine/issues/340).

| Clause | State |
|---|---|
| 1 — a carry is a parameter of the move | **Built.** `EncounterState.with_movement(..., carrying=...)` |
| 2 — passengers translate by the grappler's displacement | **Built**, and asserted against the grapple-range ending that depends on it |
| 3 — each non-free passenger costs the grappler a foot per foot | **Built.** `movement_cost(..., carrying=N)` |
| 4 — the extra adds rather than replacing | **Built**, and named as a reading in `movement_cost`'s docstring |
| 5 — the passenger spends nothing and provokes nothing | **Built**, and it is what *not* charging the passenger's `movement_used` means |
| 6 — a Frightened passenger may be carried toward its fear | **Built.** The refusal is on the mover; a test exercises the negative case so the absence is not vacuous |
| 7 — two exemptions, and unstated makes out neither | **Built.** `carried_without_extra_cost` |
| 8 — three refusals | **Built.** `EncounterState._passengers` |
| 9 — the disclosure retired with the rule | **Built.** `MOVABLE_UNENFORCED` deleted; `Condition.GRAPPLED` discloses nothing |

_Written 2026-08-30 against SRD v5.2.1._
