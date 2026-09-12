# 0092 — An object fills a space because its placer said so

- **Status:** Accepted, 2026-09-06
- **Settles:** [#459](https://github.com/eddiefiggie/srd-rules-engine/issues/459)
- **Requirements:** R15, R19, R31, R32
- **Related:** [0084 — a space is a control area, not a volume](0084-a-space-is-a-control-area-not-a-volume.md),
  whose clause 9 left this unasked and whose reads this completes; [0029 — sight is stated
  per barrier](0029-whether-a-wall-blocks-sight-is-a-property-of-the-wall.md) and #416's cover degree, the
  two earlier facts an `Obstruction` carries because the document answers them per barrier;
  [0087 — a move is a path through spaces](0087-a-move-is-a-path-through-spaces-and-a-turn-ended-in-one-is-prone.md),
  which filed this and whose creature-only refusal stands; [0041 — an item that leaves a
  creature](0041-an-item-that-leaves-a-creature-is-an-object-somewhere-unstated.md), whose
  detached objects still fill nothing

## Context

p. 185 and p. 191 define occupancy in two terms each:

> **Occupied Space.** A space is occupied if a creature is in it or if it is completely
> filled by objects.

> **Unoccupied Space.** A space is unoccupied if no creatures are in it and it isn't
> completely filled by objects.

[0084](0084-a-space-is-a-control-area-not-a-volume.md) built the creature half —
`occupants_of`, point-in-square — and its clause 9 left the object half unasked, on a
reason rather than an oversight: the engine had no object that *fills* a space. Its objects
were equipment a creature carries, and its one free-standing thing, `Obstruction`, is a
barrier — a box that gives cover and stops a line of effect, which are different questions
from whether a creature may stand there. So `is_unoccupied` answered `True` where p. 191
might say `False`, and said so, because that is the honest direction for a read that cannot
see the crates.

[#459](https://github.com/eddiefiggie/srd-rules-engine/issues/459) named the three consumers
a filled space would have: `is_unoccupied` itself, p. 190's teleport, and p. 14's move — and
noted the third might not change at all.

## Options considered

**Option 1 — a solid obstruction fills its space.** Read `fills` off `degree`: a box that
gives cover is something a body cannot stand in. Rejected. It is the teleport's reading of
"solid" (0084's #444 note calls it a convention, stated as one), and it is wrong for
occupancy in both directions: a low wall gives Half Cover and fills nothing, and a heap of
loose sacks can fill a space while covering nobody. p. 190 keeps the two apart in one
sentence — "occupied by another creature **or** blocked by a solid obstacle" — and a model
that derived one from the other would collapse a distinction the document draws.

**Option 2 — a new occupant type beside `Obstruction`.** A box that occupies and does not
obstruct. Rejected as a second geometry for one fact: the crates that fill a space also
stand between an archer and a target, and two boxes over one volume is the duplication
#161 removed.

**Option 3 — a stated field on `Obstruction`.** Taken. `fills_space: bool = False`, beside
`degree` and `blocks_sight`, for the reason each of those is a field: the document answers
the question per object and gives no method for measuring it. "Completely" is a judgement
p. 185 hands to a person, as p. 15 hands "at least half" to one.

**Option 4 — on p. 14, extend the refusal to a filled space.** Rejected as a rule the
document does not state (R31). p. 14's sentence is "a space occupied by another
**creature**", and it names no object; 0087 clause 5 built it on those words.

## Decision

**1. `Obstruction.fills_space`, stated by the placer, default `False`.** The default is
what every obstruction meant before the field existed — a barrier, not an occupant — so no
existing scene changes. Independent of `degree` in both directions, by option 1's reasoning.

**2. `EncounterState.filled_by_objects(point)`**, a read (R19): whether any obstruction that
fills its space contains the point. Faces included, as `Box.contains` has always answered.

**3. `is_unoccupied` reads both halves.** The creature half is `occupants_of`, unchanged and
still creatures only by name, because every consumer names which half it means.

**4. p. 190's teleport diverts on it, under the word the sentence uses.** `_teleport_blockage`
asks the filled space after other creatures and before the solid obstacle, and the refusal
says "occupied" rather than "blocked": a heap that gives no cover diverts on this clause,
where smoke — which gives none and fills nothing — never diverted and still does not.

**5. p. 14's move is unchanged.** "You can't willingly end a move in a space occupied by
another creature" names creatures, and the refusal 0087 built on it stays creature-only. A
test pins that a walk may end among the crates, as a "nothing changed" guard with its reason
attached. What a walk does about a wall in its path is a question `with_movement` has never
asked, and this record leaves it whole rather than answering the crate half of it.

**6. A detached item still fills nothing.** 0041's sword on the floor is an object somewhere
unstated, and nothing here promotes it; an object that fills a space is one its placer put
there as an `Obstruction` and said so.

## Why

**The fact is the placer's because the measure is nobody's.** Every earlier fact on an
`Obstruction` is stated rather than derived, and each time for the same finding: the
document says what a thing does (covers half, blocks sight) without saying how to tell.
"Completely filled" is the third instance. An engine that decided it from a box's volume,
or from its cover, would be producing a rule value R31 forbids, and the cover shortcut is
also simply wrong, which option 1 sets out.

**Clause 5 is the restraint the issue asked for.** The tempting move is to let a filled
space refuse a walk's destination, since a creature plainly cannot stand in a stack of
crates. But the sentence that refuses destinations is about creatures, and the sentence
that would refuse walking into objects is one the document does not write for a walk — it
writes it for a teleport, and only there. Answering it for crates while leaving walls
unanswered would be half a rule in the direction that looks complete.

## Consequences

**Accepted costs.**

- **`Obstruction` carries a third stated fact**, and a placer who wants a filled space has
  to say so. That is the cost of every stated field here, and the alternative is a guess.
- **A walk can still end inside crates**, by clause 5, exactly as it could end inside a wall
  before. Neither is new; both are now written down.

**Follow-on effects.**

- Coverage does not move: **146 of 210**. Occupancy has no shape of its own; 0084 built it
  as a read two entries share.
- The verifier's p. 185 note no longer says the clause is unbuilt. No clause is added: both
  entries were asserted by 0084, and p. 190's diversion by #444.
- 0084's row 9 is superseded here; 0087's and 0041's notes that pointed at #459 point here.

## Evidence

Read in the official SRD v5.2.1 PDF for 0084 and #444, and already asserted in
`scripts/verify_d20_rules.py`:

- **p. 185**, *Occupied Space*, and **p. 191**, *Unoccupied Space*, whole.
- **p. 190**, *Teleportation*: "occupied by another creature or blocked by a solid obstacle,
  you instead appear in the nearest unoccupied space of your choice".
- **p. 14**, *Moving around Other Creatures*: "You can't willingly end a move in a space
  occupied by another creature", the sentence clause 5 rests on.

Engine side: eight corruption proofs through `scripts/prove_guard_red.sh`, each red on the
test written for it — the read itself, `is_unoccupied`'s object half, filling read off cover
instead of stated, the default, the teleport's diversion, the heap that covers nobody, the two
clauses named apart, and the reworded 0084 test that a wall nobody said is full is not an
occupant. The new module goes red against the base tree on import, because its fixtures name
a field the base tree's `Obstruction` lacks; the two "nothing changed" guards are marked as
such in the module and were not proved red.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `Obstruction.fills_space`, stated | **Built** |
| 2 — `filled_by_objects` | **Built.** `EncounterState.filled_by_objects` |
| 3 — `is_unoccupied` reads both halves | **Built** |
| 4 — the teleport diverts under "occupied" | **Built.** `_teleport_blockage` |
| 5 — p. 14's move unchanged | **Built** by leaving it, and pinned with its reason |
| 6 — a detached item fills nothing | **Built** by construction: nothing promotes one |

_Written 2026-09-06 against SRD v5.2.1._
