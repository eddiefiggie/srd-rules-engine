# 0067 — p. 178's cap needed an antecedent, and stating it is the permission

- **Status:** Accepted, 2026-08-30
- **Settles:** [#336](https://github.com/eddiefiggie/srd-rules-engine/issues/336)
- **Requirements:** R19, R30, R31, R32
- **Related:** [0051 — a size is stated, or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md),
  whose clause 5 disclosed this cap as unapplied and whose bound this now reads;
  [0026 — terrain enters as state](0026-terrain-enters-as-state.md) clause 1, which is the
  pattern the antecedent follows; [0019 — kind is a filing label](0019-kind-is-a-filing-label.md),
  for why the three verbs are not modelled apart;
  [0058 — a field nothing reads is a rule modelled and not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md)

## Context

p. 178, *Carrying Capacity*:

> Your size and Strength score determine the maximum weight in pounds that you can carry, as
> shown in the Carrying Capacity table. **The table also shows the maximum weight you can
> drag, lift, or push. While dragging, lifting, or pushing weight in excess of the maximum
> weight you can carry, your Speed can be no more than 5 feet.**

[0051](0051-a-size-is-stated-or-it-is-unknown.md) built the table and the comparison, and
disclosed the cap as unapplied under `carrying-capacity-speed-cap-is-not-applied`. #336 held
the two reasons, and each alone was sufficient:

**The trigger is not the state the engine held.** The sentence fires on *dragging, lifting, or
pushing* — not on carrying too much. A creature at 400 lb of worn and stowed gear is over its
Carry bound and is not, on that fact alone, dragging anything.

**p. 12 makes the subsystem discretionary.** "If you try to haul an unusually heavy object or a
massive number of lighter objects, the GM **might** require you to abide by the rules for
carrying capacity."

## Options considered

### Where the antecedent comes from

**Option 1 — derive it from the equipment list.** Rejected outright, and it is what #336 was
filed to prevent. `carried_weight` is weight *borne*; p. 178's sentence is about weight
*shifted*. Equating them applies a Speed cap the document does not state for a laden creature,
and does it silently.

**Option 2 — a parameter on the queries that need it.** Rejected for
[0026](0026-terrain-enters-as-state.md) clause 1's reason, now applied for the fourth time: a
caller handing a fact to `legal_actions` is a caller deciding what a creature may do, one call
at a time. Terrain, spells and equipment each got the same answer.

**Option 3 — a stated fact on the creature.** Chosen. `Combatant.hauled_weight`, supplied by the
ruleset, read by everything.

### Where p. 12's discretion lives

**Option 1 — a separate switch on the encounter.** Rejected. Two fields, and the second one
does nothing except gate the first — a creature with a stated haul and the rules "off" is a
creature the ruleset described and the engine ignores, which is a state with no meaning.

**Option 2 — stating a haul *is* exercising the discretion.** Chosen. The only mechanical
consequence of "this creature is hauling" in this engine is the cap, so the two facts are
operationally one. A caller that states a weight has decided the subsystem binds; a caller that
says nothing has decided it does not, which is also the default and the document's own
starting position ("You can usually carry your gear and treasure without worrying about the
weight", p. 12).

## Decision

**1. The antecedent is `Combatant.hauled_weight: float | None`, stated by the ruleset.** Never
derived from `equipment`, for the reason above.

**2. `None` is how p. 12's discretion is exercised.** A haul nobody stated caps nothing, and
`over_hauling_capacity` answers `None` rather than `False` — a verdict about a question nobody
asked would be a claim.

**3. The comparison is the hauled weight against the Carry column.** Not the creature's own
gear added to it, and not the Drag/Lift/Push column one line away in the same table. "weight
in excess of the maximum weight you can carry" names one of the two printed numbers, and
strictly exceeding it — the maximum is not in excess of itself.

**4. A haul above the Drag/Lift/Push column is refused at construction.** "The table also shows
the **maximum** weight you can drag, lift, or push", and above a maximum is not a slower haul.
Refused only for a creature the ruleset sized, because an unsized one has no row to read and an
unstated bound cannot be exceeded (R31, and the direction `Combatant.hands` already takes).

**5. The cap is a ceiling on the walking Speed, applied last.** "can be **no more than** 5
feet" — `min`, not a subtraction, so a creature already slower is not sped up to it. The
walking Speed only, because p. 188 makes "Speed" the walking one; that is the same reading
p. 90's Slow already takes here, and a cap reaching a Fly or Swim Speed would be a rule the
sentence does not state.

**6. The two bounds are published separately and the disclosure is retired.**
`over_carrying_capacity` stays as arithmetic with no consequence attached, because p. 178
attaches none to it; `over_hauling_capacity` is the one with a rule. They were conflated only
because a single disclosure stood for both.

**7. The Speed is read from one place.** `Situation.speed` and the Dash's `extra_movement` both
recomputed `conditions.speed_after(...)`, which is `effective_speeds` seen through a narrower
window. Both now read `effective_speeds`.

## Why

**Clause 2 is the record.** "The GM might require you" reads like a feature request for a
configuration flag, and it is not one — it is a sentence about *whether a fact enters play at
all*. Modelling it as a switch beside the fact creates a state the document has no meaning for.
Modelling it as the presence of the fact costs nothing and is exactly what p. 12 describes.

**Clause 7 fixed a defect this change did not cause.** `Situation.speed` had recomputed a
partial `effective_speeds` since before p. 90's Slow existed, so from
[#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322) onward a Slowed creature was
published a Speed of **30** beside a `movement_remaining` of **20** — the surface's own two
numbers disagreeing about one creature, in the direction that overstates what it may do. It was
found because the hauling cap would have been the third divergence, and it is the
[#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365) pattern in mirror image: a
rule computed in one place and *re-derived*, worse than one computed and never consumed, since
a stale copy reads as an answer. A regression test pins it.

**Clause 3 is three near-misses in one sentence.** The Drag column is one line above in the
same table; the creature's own gear is the other weight in scope; and `>` versus `>=` moves the
line by a pound. Each would pass a suite that only ever tested a haul far over or far under.

**Clause 4 is the clause a reviewer should push on.** Refusing at construction is strong, and
the justification is that p. 178 prints the word "maximum". If a future rule grants a creature
a haul beyond the table, this refusal is where it will bite — and it will bite loudly, which is
the right failure for a bound the document states.

## Consequences

**Accepted costs.**

- **`Combatant` grows again**, and the field is one a ruleset must set for a rule to apply at
  all. That is 0026's pattern and its familiar cost: a caller that does not know the field
  exists gets no cap and no warning.
- **A construction-time refusal is new territory for weight.** `Combatant.__post_init__` now
  reads `carrying_capacity`, which reads `size` and `abilities` — a validation with a wider
  reach than the hands check beside it.
- **`over_carrying_capacity` now names a fact with no rule attached.** Kept because it is a
  published surface field with a committed name and a caller may want it; the docstring says
  plainly that p. 178 attaches nothing to it, so a reader does not take silence for a rule.

**Follow-on effects.**

- **The disclosed clause count falls 17 → 16.** The clause came off in the change that built
  its rule, which is the second time in this session
  ([0066](0066-a-move-that-brings-someone-with-it.md) was the first).
- **[#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365) gains a case in the
  other direction** — a rule re-derived rather than un-consumed — and clause 7 is the evidence
  that the guard it proposes should look both ways.
- **Coverage does not move.** `carrying-capacity` was already claimed
  ([0061](0061-a-shape-resolves-and-a-clause-may-not.md)).

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 178** (*Carrying Capacity* in full,
both columns, both maxima and the cap), **p. 12** (*Carrying Objects*, for the discretion),
**p. 188** (*Speed*, for which speed a bare "Speed" names), and **p. 180** (*Dash*, for
"extra movement equal to your Speed").

One verifier clause added — the Drag/Lift/Push maximum, which clause 4 turns on and which was
not pinned — taking the suite to **282**. Two existing clause descriptions were corrected,
since both said the cap was not applied.

## Status of implementation

**All seven clauses are built** by [#336](https://github.com/eddiefiggie/srd-rules-engine/issues/336).

| Clause | State |
|---|---|
| 1 — a stated antecedent on the creature | **Built.** `Combatant.hauled_weight`, never derived from `equipment` |
| 2 — `None` is p. 12's discretion | **Built.** `over_hauling_capacity` answers `None`, not `False` |
| 3 — the haul against the Carry column, strictly | **Built**, and each of the three near-misses has its own test |
| 4 — above the Drag maximum is refused | **Built** in `Combatant.__post_init__`, and only for a sized creature |
| 5 — a ceiling on the walking Speed, applied last | **Built** in `effective_speeds`, as a `min` |
| 6 — two bounds published apart, disclosure retired | **Built.** `CARRYING_CAPACITY_SPEED_CAP` is deleted and `over_hauling_capacity` is on `Situation` and on the adapter's committed list |
| 7 — the Speed read from one place | **Built**, and it retired a defect that predated this work by many builds |

_Written 2026-08-30 against SRD v5.2.1._
