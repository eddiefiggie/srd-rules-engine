# 0014 — Position is three integer coordinates in feet, and distance is never a float

- **Status:** Accepted, 2026-08-23
- **Settles:** the positional model for [#17](https://github.com/eddiefiggie/srd-rules-engine/issues/17)
  and [#20](https://github.com/eddiefiggie/srd-rules-engine/issues/20)
- **Requirements:** R9, R13, R16 · touches R31, R32
- **Related:** [0006 — ledger format](0006-ledger-format.md), whose no-float rule constrains this;
  [0004 — the trigger catalogue](0004-trigger-catalogue.md), which established the
  *grounded in* rather than *cited from* standing this record reuses

## Context

#20 is explicit that it "forces R9's positional state to be real rather than nominal. Everything
else can treat position as a distance the caller asserts; area of effect cannot." So the model had
to be chosen before either issue could start, and it is expensive to change afterwards: every
distance computation and every area shape inherits it.

Three constraints bounded the choice.

**The SRD's areas of effect are solids.** A Sphere "extends in straight lines from a point of origin
outward in all directions" (p. 188). A Cylinder specifies a radius *and a height* (p. 180). A Cone's
width equals its distance from the origin (p. 179).

**#17's own shapes are elevation concepts.** Fly Speed, Hover, Burrow Speed and Climb Speed are all
in the inventory. A flat model can hold them as numbers but cannot resolve them.

**The ledger refuses floats.** `core.canonical` states it in terms: "distances in feet are all
integers". Straight-line distance between integer points is irrational in general.

## Options considered

**Distances asserted by the caller, with no coordinates.** Simplest, and sufficient for reach and
weapon range. Rejected because #20 rules it out directly — area membership cannot be derived from
pairwise distances, and the caller asserting a distance is the caller supplying an input the engine
is supposed to compute.

**Two coordinates in feet.** Matches how most tables play, and every worked example in the document
is planar. Rejected because it makes four inventoried shapes unresolvable and a Cylinder's height
unrepresentable, and because adding a third axis later touches every distance computation and every
area shape — the same "free now, expensive later" argument decision 0013 made about renaming
unimplemented shapes.

**A grid.** Not considered seriously: `AGENTS.md` lists grid-based tactical movement as a declined
non-goal, and the SRD publishes the grid as an optional variant rather than the default.

## Decision

**1. A position is three integers in feet.** `Position(x, y, z)`, continuous rather than squared,
with `z` as elevation. Positions are optional: an encounter that tracks none simply cannot answer a
range question, and says so rather than assuming everyone is adjacent.

**2. Range tests compare squares; distances for the record use an exact integer square root.**
`within(a, b, feet)` asks whether `dx² + dy² + dz² <= feet²`, which is exact integer arithmetic.
`distance_feet` uses `math.isqrt` and is a value to *read*, never a value to compare against.

**3. Straight-line measurement is disclosed as a project decision, not a rule.** The SRD gives
distances in feet and speaks of straight lines, but **states no method for measuring between two
points**. The measurement is therefore *grounded in* the document rather than *cited from* it, and
`core.position` says so in its own docstring rather than in a note somebody has to find.

**4. The climbing-in-difficult-terrain reading is recorded rather than assumed.** Climbing costs "1
extra foot (2 extra feet in Difficult Terrain)" (p. 178). The parenthetical is read as *replacing*
the extra rather than adding to Difficult Terrain's own, so the total is 3 feet per foot rather
than 4.

## Why

### The squares are not an optimisation

They are the only exact answer available. Two points at `(0,0,0)` and `(5,3,0)` are about 5.83 feet
apart. `distance_feet` reports 5, and a range test built on it would call that within reach. The
error appears **only at the boundary**, which is precisely where reach and range decide outcomes —
so it would pass every test that did not probe the edge, and produce a wrong ruling in play.

A test pins that case, and a mutation replacing the squared comparison with the rounded one is
caught by it.

### Disclosing the measurement matters more than choosing it

Straight-line is almost certainly what a reader expects. But R31 does not ask whether a value is
*likely right*; it asks whether it traces to the document. This one does not, and the standing rule
is that a visible gap beats a confident wrong number, because a wrong number is indistinguishable
from a right one once it is inside a finished ruling.

The trigger catalogue already established this standing — project-authored, grounded in the
document, disclosed as such. This reuses it rather than inventing a second vocabulary for the same
situation.

### The third axis is cheap now and not later

One extra term in a squared distance, and one extra comparison per area shape. Against that: four
inventoried shapes that a flat model could hold but not resolve, and a retrofit that would touch
every caller. Decision 0013 made the same argument about renaming shapes while none were
implemented, and it was right there.

## Consequences

**Accepted costs.**

- Elevation must be supplied for flying and climbing to mean anything. A caller that leaves `z` at 0
  gets planar behaviour, which is correct but silently so.
- `distance_feet` rounds down. It is documented as a value to read, but nothing *enforces* that it
  is never compared against — a future caller could reintroduce the boundary error.
- The climbing reading could be wrong. It is recorded here and in the test's own docstring so that
  changing it is a decision rather than a discovery.

**Follow-on effects.**

- Areas of effect can now be built, and they will need obstructions: "If all straight lines
  extending from the point of origin to a location in the area of effect are blocked, that location
  isn't included" (p. 177). No obstruction model exists, so the first areas will ship disclosed as
  ignoring cover.
- `weapon-thrown` and `mastery-cleave` are unblocked by this record but not implemented by it.
- Nothing here helps the optional grid variant, which stays unimplemented.

## Evidence

Reproduce with a copy of the official SRD v5.2.1 PDF, which this repository does not carry:

```
python3 scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf
```

Eight of its clauses cover this record's rules. The absence of a measurement rule was checked by
searching the whole document for "measuring distance" and its variants and finding nothing — an
absence, so it is recorded as a search that returned empty rather than as a citation.

## Status of implementation

**Implemented with this record**, in `core.position`, plus `Combatant.position`, `speeds`, `reach`
and `movement_used`; `EncounterState.with_movement`; and reach and weapon range in
`core.combat.attack_resolver`. Eight shapes claimed. Ten mutations of the new code were run against
the tests and all ten were caught.
