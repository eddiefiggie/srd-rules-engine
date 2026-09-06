# 0087 — A move is a path through spaces, and a turn ended in one is Prone

- **Status:** Accepted, 2026-09-06
- **Settles:** [#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451)
- **Requirements:** R1, R4, R9, R15, R16, R19, R20, R31, R32
- **Related:** [0084 — a space is a control area, not a volume](0084-a-space-is-a-control-area-not-a-volume.md),
  whose reads this is built on and whose clause 8 this is the consumer of;
  [0086 — a range runs from the edge of a space](0086-a-range-runs-from-the-edge-of-a-space.md),
  which unblocked it; [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md)
  and [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md), whose obligation shape the
  fourth sentence takes; [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which is where the other three sentences live; [0051 — a size is stated or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md)
  and [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  which decide every unstated size and side here

## Context

p. 14, *Moving around Other Creatures*, is four sentences:

> During your move, you can pass through the space of an ally, a creature that has the
> Incapacitated condition, a Tiny creature, or a creature that is two sizes larger or smaller
> than you. Another creature's space is Difficult Terrain for you unless that creature is Tiny
> or your ally. You can't willingly end a move in a space occupied by another creature. If you
> somehow end a turn in a space with another creature, you have the Prone condition unless
> you are Tiny or are of a larger size than the other creature.

[#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451) said every ingredient
existed after 0084 and that *the one genuinely new thing is a path*: `with_movement` moves a
creature from one point to another, and nothing enumerated the spaces in between. That was
right. The first build then met the collision
[#456](https://github.com/eddiefiggie/srd-rules-engine/issues/456) records — reach was
point-to-point, so every melee position against a Huge creature was inside its space and the
four sentences read ordinary melee as forbidden, doubled and Prone — and was set aside until
[0086](0086-a-range-runs-from-the-edge-of-a-space.md) measured reach from a space's edge. Its
clause 8 is the premise here: a Medium creature in reach of a Huge one now has positions
outside its space, so p. 14 can be built on `space_contains` exactly as it stands.

Two things the first build met were recorded for this one: fixtures that co-locate creatures
at one point, and the inclusive boundary putting a Medium creature at exactly five feet from a
Large one *in* its space. Both were met again and both were fixtures.

## Options considered

**Option 1 — build the four sentences as four rulings.** Rejected. Three of them produce
nothing: a passage refused, a destination refused and a price charged are not outcomes, and
[0056](0056-a-move-is-refused-where-it-is-made.md) already puts a refused move in `with_movement`
rather than behind the one door. A ruling for a move that did not happen would be a record
of something that never occurred.

**Option 2 — "in a space with" as the overlap of two squares.** Rejected on one pair: two
Medium creatures five feet apart have squares that touch at 2½ feet, so every pair in
ordinary melee reach would be in a space together and Prone at the end of every turn. That
is the reading 0084 chose point-in-space *to avoid*, and it would reverse it under a new name.

**Option 3 — "in a space with" as the mover's point in the other's space, only.** Rejected
as asymmetric where the sentence is not. "In a space with another creature" is true of both
creatures or of neither, and a Huge creature whose square covers a Medium creature's point is
in a space with it whichever point is asked about. Under this option the Huge creature could
end its move on top of the Medium one and owe nothing.

**Option 4 — either point in the other's square, which is one test against the wider
square.** Taken. Both squares are centred on their own creature's point (0084 clause 4), so
"my point in your square or your point in mine" is exactly "the displacement is within the
larger half-width", and the same square answers the path.

**Option 5 — infer *ally* from who has attacked whom.** Rejected outright. p. 176's four
disjuncts are all designations, and inferring one is the engine reading narrative (R20). An
ally's space is crossed for free, so a guessed friendship grants movement the rules may not.

## Decision

**1. Sharing a space is symmetric, and it is point-in-square, not square-on-square.** Two
creatures are in a space together when either's point is inside the other's square:
`EncounterState.shares_space_with`, through `_shared_width`. An unsized creature has no
square (0051), so it shares only by standing in someone else's.

**2. A move is a straight segment, and the spaces it runs through are intervals along it.**
`position.segment_in_space` clips the segment against the closed square `space_contains`
uses, exactly, with `Fraction`; `EncounterState.spaces_crossed` lists every other creature's
interval. A corner grazed at a single point is not a crossing, and a move of no length crosses
nothing. **A space the move starts in is listed from 0 and is not *entered*** — leaving is
not passing through, and a reading that refused it would hold a creature where it may not
stay.

**3. The passage is refused unless one of the four permissions is made out**, in
`with_movement`, for every space the move enters. Ally is two stated sides; Incapacitated is
the condition; Tiny is the other creature's own size; two sizes apart needs **both** sizes
stated, and an unstated size makes the permission out for nobody (0051, 0030 clause 1 — the
direction `carried_without_extra_cost` already takes for p. 182).

**4. The stretch inside a non-exempt space is Difficult Terrain, merged and floored once.**
`position.feet_along` unions the intervals before it measures them, so p. 181's "isn't
cumulative" holds by construction, and `with_movement` prices the feet inside at double and
the rest at what the caller stated. The exemptions are the second sentence's **two** — Tiny
and ally — not the first sentence's four: an Incapacitated enemy may be crossed and costs
double to cross.

**5. A move may not end in a space with any other creature**, and the sentence names no
exception, so an ally's space may be crossed and may not be stopped in. Symmetric by clause
1, so a Huge creature may not end its move over a Medium one either.

**6. A carried passenger is outside all three questions.** p. 182's *Movable* moves the
grappled creature by the same displacement, so its space travels with the mover and is never
crossed, ended in, or priced. Without this a Large grappler holding a Medium captive inside
its own square could never move at all.

**7. The Prone is an obligation the turn's end derives, in Suffocation's shape.**
`EncounterState.owes_prone_for_shared_space` is read by `TurnLoop.end_turn_obligations`, the
one adjudication entry point resolves it under `SHARED_SPACE_RULE_ID`, no die is asked, and
the condition carries the rule id as its cause (0083). Owed when at least one creature shared
with makes neither exemption out; a creature already Prone owes nothing (p. 179: a condition
does not stack). **An unstated size withholds**: "of a larger size than the other creature"
compares two sizes, and a Prone applied on a guess would be an outcome the rules may not
produce.

**8. Ally is `Combatant.side`, a label the ruleset states.** Two creatures carrying the same
label are allies; a creature with no side is nobody's; a creature is not its own.
[#434](https://github.com/eddiefiggie/srd-rules-engine/issues/434) needs the same fact.

**9. The shape is `moving-around-other-creatures`, claimed against the one resolver.** The
generator had declined the entry as composing *Occupied Space* and *Difficult Terrain*, and it
does not: neither Glossary entry says whose space may be passed through, that a move may not
end in one, or that a turn ended in one is Prone. Four sentences of mechanism stated nowhere
else are a row.

**10. p. 190's five feet are measured from the edge of a space too.** The read surface's
`_within` — the Unarmed Strike, its Grapple and Shove, and the reaction menu's unarmed reach
— had stayed point-to-point through 0086, so a Medium creature could grapple a Large one only
from inside its space, which is the position clause 5 refuses to walk into. 0086 clause 4 says
every range between two things; this is the three sites it missed, built here because the
fixtures this change moved are what found them.

## Why

**Clause 1 is the whole reading, and one pair decides it.** The document's "in a space with"
was written for a grid where squares are cells and overlap is a fact about cells. Without a
grid there are two translations, and they disagree on exactly the pair the engine cares
most about: two Medium creatures five feet apart. Square-on-square puts them together;
point-in-square keeps them apart. 0084 chose the second for occupancy so that two Medium
creatures both contain the midpoint between them and neither contains the other, and this
record keeps it for the same pair — the reading under which a fighter beside an enemy is
standing beside it and not on it.

**Clause 2 is the path #451 named, and the interval is what makes both halves one geometry.**
Whether a space is entered and how much of the move is inside it are the same clip read two
ways. A second geometry for the price would be a second place for the boundary to fall.

**Clauses 3 and 7 withhold on an unstated size in opposite-looking directions for one
reason.** Refusing a passage withholds movement; refusing a Prone withholds a condition. Each
is the option that produces nothing the document did not state, which is what 0030 clause 1
asks for — the engine may decline to let a creature through, and may decline to knock it
down, and may not invent either.

**Clause 10 is the one this record would rather not carry.** It is 0086's change reaching
three sites 0086 said it had reached. It is here because the fixtures moved for clause 1 are
what exposed it: at seven feet a Medium creature stands outside a Large creature's square and
inside p. 190's reach from its edge, and the grapple was not offered. A reach measured one way
for a sword and another for a hand is the partial build 0086 clause 4 called the dangerous
one.

## Consequences

**Accepted costs.**

- **Fixtures moved.** Two suites placed a Medium creature at five feet from a Large one, on
  the inclusive boundary of its square (0084 clause 6). Both now stand at seven — outside the
  square and inside the reach 0086 measures from its edge — and one unsized case stands at
  five, because an unsized creature has neither a square to avoid nor an excess to reach
  with. Positions did not matter when those fixtures were written; they do now.
- **A creature standing five feet from a Large one is in its space.** That is 0084 clause 6
  and not this record, and 0086 clause 8 is why it needs no separate decision: in-reach
  positions off the boundary always exist. A caller that places creatures at exactly five
  feet from a Large one will find the Prone obligation, which is p. 14 working.
- **Diagonals stay 0014's.** A move that on the grid would cut a corner is a straight line
  here, and the square it clips is the one `space_contains` uses. No second reading.
- **The dead still occupy.** A creature at 0 hit points keeps its space, so ending a turn over
  a fallen enemy of your size is Prone. p. 14 says "another creature" and the document does
  not say a corpse is an object; reading it as one would be a rule value R31 forbids.

**Follow-on effects.**

- Coverage moves to **144 of 210**: `moving-around-other-creatures` is a row and is claimed.
- `Combatant.side` exists for [#434](https://github.com/eddiefiggie/srd-rules-engine/issues/434)
  to read. Nothing infers it and nothing should.
- p. 185's object clause — the half of #451 this does not touch — is
  [#459](https://github.com/eddiefiggie/srd-rules-engine/issues/459), and 0084's row 9 points
  there now.
- `tests/test_forced_movement.py`'s Large ogre at `(3, 4, 0)` is nearer than necessary and
  not wrong (0086's reading); nothing in that suite ends a turn, so it found no obligation
  and was left where it was.

## Evidence

Read in the official SRD v5.2.1 PDF, and asserted in `scripts/verify_d20_rules.py` by #457
before this rule was built:

- **p. 14**, *Moving around Other Creatures*: all four sentences, one clause each.
- **p. 176**, *Ally*: the four disjuncts.
- **p. 181**, *Difficult Terrain*: "every foot of movement in that space costs 1 extra foot"
  and "isn't cumulative", already asserted for `movement_cost`.

Engine side: twenty corruption proofs through `scripts/prove_guard_red.sh`, each red on the
test written for it — the sizes-apart bound, both exemption lists, the merge before the
floor, the corner graze, the inclusive edge, the passenger exclusion, the symmetric
destination, every withholding, the obligation's derivation, the cause on the condition, and
the unarmed reach from a space's edge. `prove_against_base.sh` against `main` fails to
collect the new module, which is indivisible and why the per-assertion proofs exist.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — sharing is symmetric point-in-square | **Built.** `shares_space_with`, `_shared_width`; asserted on the five-foot Medium pair and the eight-foot Large pair |
| 2 — a path of intervals | **Built.** `position.segment_in_space`, `EncounterState.spaces_crossed`, `SpaceCrossed.entered` |
| 3 — the passage refused unless permitted | **Built.** `may_pass_through`, in `with_movement` |
| 4 — priced as Difficult Terrain, merged | **Built.** `position.feet_along`, and the two-part cost in `with_movement` |
| 5 — no ending in a shared space | **Built**, in `with_movement`, both directions |
| 6 — passengers outside all three | **Built.** `excluding=` on `spaces_crossed`, and the destination skips them |
| 7 — the Prone as an end-of-turn obligation | **Built.** `owes_prone_for_shared_space`, `end_turn_obligations`, `core.moving_around` |
| 8 — `Combatant.side` | **Built.** `are_allies` reads it; #434's consumer is not |
| 9 — the shape row | **Built.** `PLAYING_SHAPES`, `IMPLEMENTED_SECTION_SHAPES`, the data file, `ENGINE_SHAPES` |
| 10 — p. 190's reach from the edge | **Built.** `read_surface._within` takes `range_slack` |

p. 185's object clause is not this record's and is [#459](https://github.com/eddiefiggie/srd-rules-engine/issues/459).

_Written 2026-09-06 against SRD v5.2.1._
