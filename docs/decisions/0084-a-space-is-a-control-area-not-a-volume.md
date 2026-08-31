# 0084 — A space is a control area, not a volume

- **Status:** Accepted, 2026-08-31
- **Settles:** [#337](https://github.com/eddiefiggie/srd-rules-engine/issues/337)
- **Requirements:** R9, R15, R16, R19, R31, R32
- **Related:** [0051 — a size is stated or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md),
  which built the category and deliberately did not build the extent;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  whose reasoning decides what extent must *not* change

## Context

p. 14 gives every size a space:

> A creature belongs to a size category, which determines **the width of the square space the
> creature occupies on a map**... A creature's space is **the area that it effectively
> controls in combat** and the area it needs to fight effectively.

[0051](0051-a-size-is-stated-or-it-is-unknown.md) built the category and said outright that it
was not building the extent. #337 is that gap, and it holds four shapes: `occupied-space`,
`unoccupied-space`, `target`, and — found late, by a reading that had nothing to do with it —
`teleportation`, whose destination rule asks whether a space is occupied.

The issue's own framing is that extent "changes the meaning of things already built": distance
measured point-to-point, areas that ask whether a point is inside them, sight and cover tracing
a line between two points. That framing is what made this a gate rather than a field.

## Options considered

**Option 1 — extent everywhere.** Distance between nearest parts, areas that can contain a
creature partly, obstructions that a Gargantuan creature constitutes. Rejected, and it is the
reading #337 invites. **The document does not say how to measure between two extents without a
grid.** p. 14 describes a space as what a size determines "on a map", and the map it means is
the grid — which this project declines as a default. Nearest-part measurement is the answer a
*grid* gives; adopting it without one is a rule value R31 forbids, arrived at by geometry the
document never describes.

**Option 2 — a grid, so the question is answerable.** Rejected. Grid-as-default is a declined
non-goal, and this would make it one through the back door.

**Option 3 — extent answers only what the document asks it about.** Taken.

## Decision

**1. `Size.space_feet` transcribes p. 14's table.** Six rows, not a doubling — Small and
Medium share a space exactly as they share a carrying multiplier, and `core.size` already
refused that shortcut once for that reason.

**2. `Fraction`, because Tiny is 2½ feet.** `Position` is integer feet and every other
distance here is an integer, so an `int` loses the half and a `float` rounds it somewhere.
`Fraction` is this repository's existing answer for an exact non-integer quantity — p. 181's
water ration is one.

**3. The Squares column is not transcribed.** p. 14 prints both. The squares are the grid
variant, and they are derivable from the feet at five feet a square — which is what makes
omitting them safe rather than lossy. The feet are the primitive.

**4. A space is centred on the creature's point, and that is an engine convention.** p. 14
supplies no anchor without a grid to align to. Centring is stated as a convention rather than
read off the document, exactly as initiative's tie-break is.

**5. A square, not a cube.** p. 14 gives a *width* and says nothing about height, so `z` is
unbounded. A creature flying directly overhead is not in the space below it, and the document
does not say what would decide that.

**6. The boundary is inclusive**, because the alternative is a seam: two Medium creatures five
feet apart would otherwise both fail to contain the midpoint between them.

**7. Extent answers occupancy and nothing else.** `occupants_of` and `is_unoccupied` are
p. 185's and p. 191's entries and are reads (R19). **`within`, `core.areas`, `core.sight` and
`core.obstructions` are untouched.** A Gargantuan creature is exactly as far away as its point
is.

**8. Two creatures may occupy one point, and the model must allow it.** p. 14 says what
happens if you "somehow end a turn in a space with another creature", so overlap is a state
the document contemplates. A model that refused to represent it would make that rule
unaskable.

**9. p. 185's object clause is not asked.** "Completely filled by objects" needs an object
that fills a space, and this engine's objects are equipment a creature carries. `Obstruction`
is a barrier rather than an occupant — it gives Total Cover and stops a line of effect, which
are different questions from whether a creature may stand there. `is_unoccupied` therefore
answers `True` where p. 191 might say `False`, which is the honest direction for a read: it
reports what the engine can see rather than inventing an obstruction.

## Why

**The second sentence of p. 14 is the whole decision.** A space is "the area that it
effectively controls in combat" — a *control* area, not a volume the creature displaces. That
is why it answers who is standing where and does not answer how far away anything is. The
first sentence, read alone, invites option 1; the second is what bounds it.

**And the gate was a gate because of what it might have changed, not what it does.** #337
listed distance, areas, cover and sight as things extent would touch. Every one of those is a
question the document answers *with a grid* and does not answer without one. Once that is
seen, the change is small and the risk was in the framing.

## Consequences

- Coverage moves to **142 of 210**: `occupied-space` and `unoccupied-space`.
- `target` and `swarm-space-sharing` remain unclaimed. Both need more than occupancy, and
  `swarm-space-sharing` is monster content ([#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)).
- `teleportation`'s destination rule is now answerable and the shape still waits on
  [#444](https://github.com/eddiefiggie/srd-rules-engine/issues/444)'s other clauses.
- p. 14's *Moving around Other Creatures* — pass-through permission, Difficult Terrain, the
  refusal to end a move in an occupied space, and the Prone that follows if you do — is
  **unbuilt** and now expressible. Filed as
  [#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451).
- Clause 7 is pinned by a test rather than left as prose. If range ever becomes extent-aware,
  that test is what should fail and make someone say so.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — p. 14's table transcribed | **Built.** `core.size.SPACE_FEET`, six rows |
| 2 — `Fraction` for Tiny's half | **Built**, and asserted exactly rather than approximately |
| 3 — the Squares column omitted | **Built**, in the sense that the decision is to hold only the feet |
| 4 — centred, as a convention | **Built.** `core.position.space_contains`, and stated as a convention in its docstring |
| 5 — a square, not a cube | **Built**, and asserted with a creature overhead |
| 6 — the boundary is inclusive | **Built**, and asserted at the midpoint two Medium creatures share |
| 7 — extent does not move range | **Built** by not building it, and pinned by a test that fails if it changes |
| 8 — overlap is representable | **Built.** `occupants_of` returns every creature, not the first |
| 9 — p. 185's object clause unasked | **Not built**, and disclosed on `is_unoccupied` ([#451](https://github.com/eddiefiggie/srd-rules-engine/issues/451)) |

### Evidence

Four corruption proofs, each red on the assertion written for it. Two clauses of p. 14 and
both space entries in `scripts/verify_d20_rules.py`.
