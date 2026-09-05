# 0086 — A range runs from the edge of a space, as the grid measures it

- **Status:** Accepted, 2026-09-04
- **Settles:** [#456](https://github.com/eddiefiggie/srd-rules-engine/issues/456)
- **Requirements:** R9, R16, R31, R32
- **Related:** [0084 — a space is a control area, not a volume](0084-a-space-is-a-control-area-not-a-volume.md),
  whose clause 7 this record **reverses for range** and whose other eight clauses it leaves
  standing; [0014 — positional state](0014-positional-state.md), whose straight line is kept;
  [0051 — a size is stated or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md),
  which decides what an unsized creature contributes; [0030 — an unanswerable qualifier
  resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  which decides the direction when it does

## Context

[#456](https://github.com/eddiefiggie/srd-rules-engine/issues/456) was raised while building
p. 14's *Moving around Other Creatures* ([#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451)),
and the build was correct. What was wrong was where the engine puts a creature in melee:

> Reach is point-to-point (0084 clause 7), so a Medium creature in melee reach of anything
> Huge or larger has its point **inside** the target's space. `tests/test_forced_movement.py`
> places a Huge ogre at `(3, 4, 0)` — five feet from the attacker, chosen for reach — and the
> attacker's point is three feet and four feet from the ogre's, inside a fifteen-foot square.

p. 14 then reads that position as forbidden to walk into, doubled to move in, and Prone at the
end of every turn. On the grid p. 14 is written for, the same fighter stands in the square
next to the giant's, ten feet from its centre, and is in reach because reach is measured
between squares. The gate's question was **is a creature's reach measured to a target's
point, or to its space?**

0084 had answered it in passing, and the answer rested on a premise:

> The document does not say how to measure between two extents without a grid... Nearest-part
> measurement is the answer a *grid* gives; adopting it without one is a rule value R31
> forbids, arrived at by geometry the document never describes.

**The document does describe it.** p. 13, *Playing on a Grid*:

> **Ranges.** To determine the range on a grid between two things — whether creatures or
> objects — count squares from a square adjacent to one of them and stop counting in the
> space of the other one. Count by the shortest route.

That is a rule for measuring a range between two things, and it runs from the **edge** of one
space — the adjacent square — into the **space** of the other. It is the grid's rule, and the
grid is the variant this project declines as a default. But the engine already translates the
grid's squares into feet everywhere else it meets them: p. 13's *"Speed of 30 feet translates
into 6 squares"* is why `Speed` is feet, and p. 14's *Space (Squares)* column is the one 0084
clause 3 declined to transcribe *because the feet are the primitive*. The question is not
whether to adopt the grid's geometry but what its measuring rule says in feet, and 0084 did
not ask because it had not read p. 13.

## Options considered

**Option 1 — the straight-line gap between the two spaces.** Measure from the nearest point
of one square to the nearest point of the other, and add the five feet of the square the count
stops in. Rejected, for a reason that is not obvious until it is tried: two Medium creatures
whose squares touch at a corner have a gap of zero, so this puts a creature at `(5, 5, 0)` in
reach of one at the origin. Today it is not — the straight line is 7.07 feet — and that is
[0014](0014-positional-state.md)'s decision that distance is a straight line rather than the
grid's shortest route, made when every creature was a point. Option 1 reverses 0014 for
every pair of creatures in the game in order to fix the pairs that involve a big one.

**Option 2 — keep point-to-point reach, and build p. 14 with strict-interior containment.**
Rejected on #456's own finding: a Medium creature at exactly five feet from a Large one would
stand on the boundary and be fine, and Huge and larger would stay unreachable on foot. A
fighter walks up to a giant.

**Option 3 — build p. 14 only against targets of Medium size or smaller.** A scope the
document does not state (R31). Rejected.

**Option 4 — the straight line between the two points, less what each space exceeds one
square.** Taken. It is p. 13's rule read in feet along the line 0014 already draws, and it
changes nothing for any pair of creatures the engine could already put in reach of each other.

## Decision

**1. p. 13's measuring rule is the document's, and it runs from a space's edge.** A range
between two things is counted from a square adjacent to one of them into the space of the
other. 0084's premise — that the document never describes measuring between extents — was
true of *distance between two extents in the abstract* and false of *range between two
things*, which is the only distance the rules ask about.

**2. In feet, along a straight line: the distance between two points, less each thing's
excess over one square.** A range test compares the straight-line distance between the two
points against the range **plus** the sum of each thing's `range_excess` — the half-width of
its space beyond a single square's 2½ feet:

| Thing | Half-width | Excess |
|---|---|---|
| a point, an object, a creature nobody sized | — | 0 |
| Tiny | 1¼ | 0 |
| Small, Medium | 2½ | 0 |
| Large | 5 | 2½ |
| Huge | 7½ | 5 |
| Gargantuan | 10 | 7½ |

On an axis this is p. 13 exactly. A Medium creature adjacent to a Huge one on the grid has
its centre 7½ + 2½ = 10 feet from the giant's; ten less the giant's excess of five is the
five feet p. 15 gives a reach. Two adjacent Large creatures have centres 10 feet apart, and
10 less 2½ less 2½ is 5. A Gargantuan creature reaching 10 feet, as its stat block says,
reaches a Medium creature with one empty square between them: centres 10 + 5 + 2½ = 17½
apart, less 7½, is 10.

Off an axis it departs from the grid **exactly as 0014 already does and no further**: the grid
counts a diagonal as one square and the engine draws a straight line. A Medium creature at
`(10, 10, 0)` from a Huge one is 14.1 feet away less 5 — not in reach, where the grid's
shortest route would say adjacent. That is the deviation 0014 accepted for two Medium
creatures at `(5, 5, 0)`, and this record adds no second kind.

**3. Tiny is zero, not negative.** p. 14 gives a Tiny creature 2½ feet of space and the grid
puts four in one square, each occupying it for counting. Nothing is further away for being
small.

**4. Every range between two things uses it, and the attacker's space counts too.** p. 13
counts *"from a square adjacent to one of them"*, and does not say which, so both extents come
off. The sites, each a fact the engine already asked point-to-point: melee reach and weapon
range (p. 15, p. 90), the Opportunity Attack's reach left (p. 185), p. 191's five feet for a
Critical Hit on an Unconscious target, p. 186's five feet for Advantage against a Prone one,
p. 90's five feet of Cleave spread and the reach of the second swing, a grapple's range
(p. 182), a sense's range (pp. 177, 180, 190), an object within reach (0041), and a spell's
range and Touch from its caster (p. 105) — where the origin is a point and only the caster's
space shortens it. `size.range_slack` sums the excesses for a site, and `within` and
`distance_feet` take it as `slack`.

**5. Occupancy is untouched.** 0084 clauses 1 to 6, 8 and 9 stand: a space is still a control
area centred on the point, `space_contains` is still inclusive, `occupants_of` and
`is_unoccupied` still answer for a point, a teleport still lands by them, and areas of effect
still ask whether a point is inside. p. 13's sentence is about *range between two things* and
says nothing about any of those, so none of them moves.

**6. An unsized creature contributes nothing** (0051), and that is the direction 0030 clause
1 picks: a range that reached further on a guess would land attacks the rules may not grant,
where one that reached no further only withholds.

**7. 0084 clause 7 is reversed for range, and its pin is turned round rather than deleted.**
The test 0084 wrote so that "if range ever becomes extent-aware, something fails and makes
someone say so" failed, and this record is someone saying so. It now asserts the reverse — a
Gargantuan creature's edge *does* change what 25 feet reaches — beside what still holds: a
Medium creature is as far as its point, and the point 30 feet away is outside the space.
0084's **Status of implementation** row for clause 7 is updated to say so; its prose is not
edited, because records are immutable and this one is where a reader finds the change.

**8. #451 is unblocked.** With reach measured this way, a Medium creature in reach of a Huge
one has positions outside its space: the reach runs 2½ feet past the boundary for every size,
so the band from the edge outward — 6 and 7 feet from a Large creature's point, 8 to 10 from a
Huge one's, 11 and 12 from a Gargantuan's — is in reach and unoccupied. p. 14's four sentences
can be built on `space_contains` as it stands; the boundary question #456 raised in passing
needs no separate answer, because in-reach positions off the boundary always exist.

## Why

**The decisive evidence is a sentence 0084 had not read, and reading it changed the
decision.** 0084's clause 7 was argued from an absence — "the document says nothing about
measuring between two extents without a grid" — and an absence is the claim that decays
most quietly ([0034](0034-a-term-the-document-defines-and-never-uses.md) clause 3). The
sentence was on p. 13 the whole time, under a heading about the grid, and it is the
document's only statement of how a range meets a creature that fills more than one square.
That it is the grid's rule does not make it the grid's geometry: what the engine takes from
it is *where the count starts and stops*, and it draws its own line between those points.

**Option 4 over option 1 is the clause this record would have got wrong by reasoning from the
page alone.** The gap between two squares is the natural translation of *"from a square
adjacent to one"*, and it is right for every pair on an axis. It is wrong for the pair the
engine already has an answer for: two Medium creatures corner to corner, whom 0014 put out of
reach and every reach test in the tree relies on. A rule that fixes the giant by moving the
fighter's neighbour is a rule that reopens a settled decision under cover of a new one. The
excess formulation is the one under which every test that held before this record holds
after it — which was checked by running them, not assumed.

**Clause 4 lists the sites because a partial build is the dangerous one.** A reach measured
one way for attacks and another for Opportunity Attacks is a creature that can hit what it
could not stop leaving. Every consumer of `within` and every `distance_feet` comparison was
found and changed in the one change, and each has a test that a Huge creature is in range
from where a Medium one is not.

**Clause 7 is the reason 0084's pin was worth writing.** It did exactly what it was for: the
first change that made range extent-aware failed it, and the failure is the sentence in this
record that says what changed and why. A pin that is deleted when it fires was never a pin.

## Consequences

**Accepted costs.**

- **A decision two records old is reversed in part**, and a reader comparing 0084 clause 7
  with this must hold both. 0084's status row is the pointer, and its prose stays as the
  reasoning it was.
- **Range grows against big creatures, and only against them.** Fixtures that place a Huge
  creature at `(3, 4, 0)` remain valid — nearer than necessary, not wrong. Every test that
  asserted a Medium creature out of reach of another still passes, because nothing changed for
  them.
- **Diagonals stay 0014's.** A creature diagonally adjacent on the grid is not always in reach
  here, for a big creature as for a small one. Disclosed as the same reading rather than fixed
  by a second one.

**Follow-on effects.**

- [#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451) is unblocked, with the
  design recorded on [#456](https://github.com/eddiefiggie/srd-rules-engine/issues/456) to
  rebuild from. Two things it will still meet are recorded there: fixtures that co-locate
  creatures at one point, and the inclusive boundary — which clause 8 shows needs no decision.
- `spell_reaches` has no caller in the engine ([#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21):
  there are no spells to cast at range), so its `caster_slack` is a parameter for the caller
  that arrives with them. Recorded so the unused parameter is not read as an omission.
- No shape moves. `reach` was claimed and stays claimed; what changed is what it measures.

## Evidence

Read in the official SRD v5.2.1 PDF for this record:

- **p. 13**, *Playing on a Grid — Ranges*: "To determine the range on a grid between two
  things — whether creatures or objects — count squares from a square adjacent to one of them
  and stop counting in the space of the other one. Count by the shortest route."
- **p. 13**, *Squares*: "Each square represents 5 feet."
- **p. 13**, *Entering a Square*: "an unoccupied square that's adjacent to your space
  (orthogonally or diagonally adjacent)" — the diagonal the grid counts as one, which 0014's
  straight line does not.
- **p. 14**, *Creature Size and Space*: the table, transcribed by 0084.
- **p. 15**, *Reach*: "A creature has a 5-foot reach and can thus attack targets within 5 feet
  when making a melee attack."

The first, second and last are asserted in `scripts/verify_d20_rules.py` as of this change;
the table was already.

Engine side: eleven `within` sites and two `distance_feet` comparisons, listed in clause 4.
The suite was run with every site changed and no fixture touched: 2336 tests, none
regressed, which is the arithmetic of clause 2 — a Medium creature's excess is zero.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — p. 13's rule runs from a space's edge | Not a mechanism. Asserted as three p. 13 clauses in the verifier |
| 2 — the straight line less each excess | **Built.** `Size.range_excess`, `size.range_slack`, and `slack` on `position.within` and `position.distance_feet` |
| 3 — Tiny is zero | **Built**, and asserted against the table |
| 4 — every range between two things, both spaces | **Built.** All eleven `within` sites and both `distance_feet` comparisons; each site has a test that a Huge creature is in range where a Medium one is not |
| 5 — occupancy untouched | **Built** by not touching it; `tests/test_occupied_space.py` asserts occupancy beside the reversal |
| 6 — an unsized creature contributes nothing | **Built.** `range_slack` skips `None` |
| 7 — 0084 clause 7 reversed, pin turned round | **Built.** `test_extent_moves_the_range_bound_as_the_grid_measures_it` replaces the pin; 0084's status row points here |
| 8 — #451 unblocked | Not a mechanism. The rebuild is [#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451)'s |

**#456 is closed with the sentence 0084 had not read** — the document does say how a range
meets a space, and it says it on p. 13.

_Written 2026-09-04 against SRD v5.2.1._
