# 0029 — Whether a wall blocks sight is a property of the wall

- **Status:** Accepted, 2026-08-25
- **Settles:** [#188](https://github.com/eddiefiggie/srd-rules-engine/issues/188)
- **Requirements:** R1, R4, R31, R32 · touches R16, R19
- **Related:** [0026 — terrain enters as state](0026-terrain-enters-as-state.md), whose clause 1
  decides where it is stated; [0025 — sight is a relation over stored state](0025-sight-is-a-relation-over-stored-state.md)
  clause 4; [#166](https://github.com/eddiefiggie/srd-rules-engine/issues/166), which found the gap

## Context

`EncounterState.can_see` answers `UNSTATED` for a target behind Total Cover, because the SRD
never says an obstruction blocks sight and never defines "line of sight" — the term appears on
pp. 130, 131, 173, 182, 183 and 310 and is defined on none of them. Total Cover is defined by
what it does to *targeting*: "can't be targeted directly" (p. 179).

That is honest and it is unusable. The most ordinary question in play — *can my character see the
goblin behind that pillar?* — is one the engine declines to answer.

#188 framed the choice as: leave it disclosed, declare a house rule, or let the ruleset supply
one. Reading the wall spells says all three are the wrong shape.

### The walls disagree with each other

| Spell | Page | Total Cover | Blocks sight |
|---|---|---|---|
| Wall of Force | 172 | yes | **no** — "An Invisible wall of force" |
| Wall of Thorns | 173 | yes | **yes** — "The wall blocks line of sight" |
| Wall of Stone | 173 | yes | says nothing |
| Wall of Ice | 172 | yes | says nothing |
| Wall of Fire | 172 | yes | says nothing |

**No single global answer can be right.** A rule that obstructions block sight makes Wall of
Force opaque; a rule that they do not makes Wall of Thorns' clause meaningless. Both are printed
in the same book, three pages apart.

That is the finding, and it is stronger than the one #166 reported. #166 argued from Wall of
Thorns — that a spell *has* to say it, so no general rule exists. That argument is weaker than it
looked: Wall of Stone is plainly opaque and says nothing, so the clause reads at least as well as
a clarification for an ambiguous material. **Wall of Force is the evidence that survives**, because
no reading of a general rule accommodates a barrier that is Invisible by definition.

## Options considered

**Declare a house rule that Total Cover blocks sight**, labelled as this engine's convention the
way [0025](0025-sight-is-a-relation-over-stored-state.md) clause 2 declares last-volume-wins and
[0028](0028-a-level-carries-the-rule-that-caused-it.md) clause 4 declares a removal order.
Rejected once the walls were read. Those two conventions settle a *precedence* the document is
indifferent about; this one would contradict a printed spell. The precedent does not reach it.

**Let the ruleset supply the rule.** Rejected for the same reason plus one more: it makes the
answer a property of the *deployment*, when the document makes it a property of the *barrier*.
Two walls in one encounter would get one answer.

**Leave it `UNSTATED` and disclose.** Rejected as the ship-it answer rather than the right one.
It is where #166 left things, and it declines a question every session asks.

**Ask the memory port.** Rejected under R20 and 0026: this is not a narrative fact resolved per
ruling, it is a standing property of a thing in the world, and terrain is state.

## Decision

**1. An `Obstruction` says whether it blocks sight, and the engine never decides.** A field on
the obstruction, beside the box that already says where it is. Wall of Force sets it false, Wall
of Thorns true, and a dungeon wall whatever the table says — the same barrier answering both
questions it is asked, which is what the document does.

**2. It is `None` until somebody says, and `None` means `UNSTATED`.** Not `True`, not `False`.
The SRD supplies no default and this record does not invent one: a caller that has not described
its walls gets the same visible gap #166 shipped, per obstruction rather than globally. The
pattern is `Lighting.ambient` and `Senses`, where absent is a third value rather than a zero.

**3. It is set where the obstruction is set, which is on `EncounterState`** ([0026](0026-terrain-enters-as-state.md)
clause 1). Not a query argument, and not a per-call override — choosing whether the wall is opaque
at the moment sight is computed is choosing whether the creature is seen, which is the dial 0026
removed.

**4. Only the obstructions actually between them are consulted.** Blocking is per-line (#91), so
a wall beside two creatures is not a wall between them and its opacity is irrelevant. A single
opaque obstruction on the line settles it; if every blocking obstruction is transparent, sight
continues to the light; if any is unstated, the answer is `UNSTATED`.

**Unstated wins over transparent, and loses to opaque.** A wall that is known to block sight
settles the question whatever else is on the line, because one opaque barrier is enough. A wall
nobody has described cannot be assumed transparent just because its neighbour is.

## Why

**The document models this per barrier, so the engine does too.** That is the whole argument.
Every other option answers a question the SRD answers differently in two places.

**It converts a global refusal into a local one.** `UNSTATED` does not disappear — it moves from
"this engine cannot answer sight through cover" to "nobody has said what this particular wall is
made of", which is a gap a caller can close by describing their world rather than one they must
work around.

**It adds no rule.** Clause 2 is the reason this record does not contradict R31 while #188's
option 2 would have: nothing here states what the document does not. It provides a place for the
*caller* to state what only they know, which is what 0026 already decided terrain is.

## Consequences

**Accepted costs.**

- **`Obstruction` grows a field, and every construction site is untouched** — the default is
  `None`, so existing callers keep the behaviour they have. That is deliberate and it is also the
  cost: a caller who never sets it never notices that sight is unanswerable through their walls.
- **`core.areas`' membership rule ignores the new field entirely.** p. 177 blocks a line of
  *effect* with Total Cover, and that has nothing to do with opacity — a Fireball is stopped by
  Wall of Force. Two questions over one box, and only one of them reads this field.
- **The three sight-blocked entries in `Conditions.unenforced_clauses` still do not shrink.**
  Frightened's "within line of sight" (p. 182) can now be answered where the walls are described,
  and enforcing it still needs a decision about what to do when the answer is `UNSTATED`. That is
  [#190](https://github.com/eddiefiggie/srd-rules-engine/issues/190).

**Follow-on effects.**

- Coverage is unchanged at **81 of 211**. No shape resolves here: this makes an existing answer
  reachable rather than resolving a new mechanic.

## Evidence

Read off the document, and all five wall spells were checked rather than the one that prompted
the question:

- Wall of Force (p. 172), "An Invisible wall of force" — a clause in `scripts/verify_d20_rules.py`.
- Wall of Thorns (p. 173), "The wall blocks line of sight" — likewise.
- Wall of Stone, Wall of Ice and Wall of Fire say nothing either way, which is what rules out the
  reading that each barrier declares its own opacity as a matter of course.
- Total Cover's own definition (p. 179), which is about targeting.

## Status of implementation

| Clause | State |
|---|---|
| 1 — an obstruction says whether it blocks sight | **Built.** `Obstruction.blocks_sight` |
| 2 — `None` until stated, and `None` is `UNSTATED` | **Built**, and its own test: a wall nobody described leaves the answer where #166 had it |
| 3 — set on `EncounterState`, never per query | **Built** by construction — it rides on the obstruction, which 0026 already put on state |
| 4 — only obstructions on the line, opaque beats unstated beats transparent | **Built** in `EncounterState.can_see` |

**No effect shape is resolved.** Coverage stays at 81 of 211.
