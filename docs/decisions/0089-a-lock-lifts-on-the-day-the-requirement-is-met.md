# 0089 — A lock lifts on the day the requirement is met, and closes on the next level

- **Status:** Accepted, 2026-09-06
- **Settles:** [#461](https://github.com/eddiefiggie/srd-rules-engine/issues/461)
- **Requirements:** R1, R4, R15, R31, R32
- **Related:** [0028 — an Exhaustion level carries its cause](0028-a-level-carries-the-rule-that-caused-it.md),
  whose clause 3 built the half of the sentence this completes; [0080 — Dehydration is
  bookkeeping](0080-dehydration-is-bookkeeping.md) and [0088 — a run of days without food is
  a hazard the creature carries](0088-a-run-of-days-without-food-is-a-hazard-the-creature-carries.md),
  which read the same two arguments this reads and found the gap

## Context

p. 181 and p. 185 each end with the same sentence:

> Exhaustion caused by dehydration can't be removed until the creature drinks the full amount
> of water required for a day.

> Exhaustion caused by malnutrition can't be removed until the creature eats the full amount
> of food required for a day.

[0028](0028-a-level-carries-the-rule-that-caused-it.md) clause 3 built "can't be removed" as a
**source-scoped lock**: `LOCKED_EXHAUSTION_RULES` names the two rule ids and `with_long_rest`
never takes a level either caused. That was built ahead of both hazards, and was right. What
nobody built was "until": the constant is over rules, not creatures, so a dehydration level
was unremovable **forever** — a creature that drank its fill for a week could not sleep it
off. [#461](https://github.com/eddiefiggie/srd-rules-engine/issues/461) found it while 0088
read a day's food for the starvation count, and noted that the antecedent now existed:
`with_day_ended` already compares each named creature's water and food against pp. 181 and
185's tables on the day it compares them against half.

## Options considered

**Option 1 — remove the levels outright when the requirement is met.** Rejected. The
sentence says the levels *can't be removed until*; it does not say they go. A creature that
drinks its fill still has to rest them off, one a night, like any other level.

**Option 2 — a per-level flag.** Change `exhaustion_levels` from a tuple of rule ids to a
tuple of `(rule, locked)` pairs. Rejected as a shape change to the one structure every
Exhaustion consumer reads, for a distinction the document does not draw: pp. 181 and 185 speak
of "Exhaustion caused by dehydration" as one thing, not of levels individually.

**Option 3 — a per-creature, per-rule lift on `Hazards`.** Taken. A set of the locked rules
whose requirement this creature has met since it last gained a level of that rule.

**Option 4 — the caller states that the requirement was met.** Rejected for 0088's reason: the
caller already states the water and the food, and the comparison against the table is the
engine's. A flag the caller set would be the caller deciding when a level becomes removable.

## Decision

**1. `Hazards.exhaustion_unlocked: frozenset[str]`** — the locked rules whose lock this
creature has lifted. Empty for a creature nobody has described.

**2. `with_day_ended` lifts a lock when the day's consumption meets the table's row.** The
full amount, not half: p. 181 gains a level *below half* and lifts the lock *at the full
amount*, two thresholds in one row, and a Large creature's row is four gallons. A creature the
caller does not name has had a day the engine knows nothing about (0080 clause 3), and nothing
lifts.

**3. A new level of a locked rule closes the lift over every level of that rule.** Done in
`with_exhaustion`, which every gained level passes through — the day's-end levels and the
save's failure alike — so a creature that is thirsty again holds "Exhaustion caused by
dehydration" and has not drunk its fill *since*. The document speaks of the cause as one
thing, and the lift is read the same way.

**4. `with_long_rest` reads it.** A locked rule's levels are candidates again when the rule is
in the creature's lift; 0028 clause 4's most-recent-first order then runs over what is left,
unchanged.

**5. The lift is recorded whether or not a level is held.** A creature that drinks its fill
holding no dehydration level has nothing to unlock and the flag is harmless; the next
dehydration level closes it, so no stale lift survives into the state it would matter for.

**6. Bookkeeping, no die.** The lift is a state transition at a day's end like the levels
themselves (0080 clause 1), and the ledger records no ruling for it.

## Why

**The "until" is the half a lock most needs, and it was the half nobody wrote down as
missing.** 0028 shipped the lock ahead of both hazards and said so; 0080 put a level behind it
and tested that a Long Rest took nothing; 0088 put a second rule's levels behind it. Every
test asserted the closed state and none asserted that it could open, and a lock that never
opens is a stronger claim than either page makes. Filing #461 rather than folding the lift
into 0088 is what made it visible as its own sentence.

**Clause 3's reading is the one the sentence's grammar gives.** "Exhaustion caused by
dehydration can't be removed until the creature drinks" is a statement about a creature that
has Exhaustion from that cause, and drinking is what ends it. A creature that drinks and then
goes thirsty again is, on the day the new level arrives, a creature with Exhaustion caused by
dehydration that has not drunk its fill since. Tracking the old levels as separately lifted
would be option 2's distinction, which the document does not draw.

**Clause 2's "full amount" is not "not dehydrated".** The tempting shortcut is to lift the lock
on any day the creature does not gain a level, and it is wrong by the row's own arithmetic:
half a day's water is enough to avoid the level and is not the full amount. The test that pins
this is the one that would have passed against the shortcut for a Medium creature drinking a
gallon, and fails against it at half.

## Consequences

**Accepted costs.**

- **`Hazards` now carries two things the engine writes** beside two the caller sets. The
  docstrings say which is which; the shape is unchanged.
- **Re-locking closes over every level of the rule**, so a creature that lifted its lock, gained
  one more level, and then drinks its fill again has to lift it again for all of them. That is
  the reading of clause 3 and it costs the creature one full day, which is what the sentence
  asks for.

**Follow-on effects.**

- No shape moves. `dehydration` and `malnutrition` were claimed on the level being gained, and
  the lift completes the sentence each entry ends with.
- 0028's Status gains a dated note; 0080's and 0088's notes that pointed at #461 point here.

## Evidence

Read in the official SRD v5.2.1 PDF, and already asserted in `scripts/verify_d20_rules.py`:

- **p. 181**, *Dehydration*: the whole entry, including "can't be removed until the creature
  drinks the full amount of water required for a day".
- **p. 185**, *Malnutrition*: "Exhaustion caused by malnutrition can't be removed until the
  creature eats the full amount of food required for a day".

Both sentences were asserted by #182's reading before either hazard was built, so this change
adds no clause.

Engine side: nine corruption proofs through `scripts/prove_guard_red.sh`, each red on the
test written for it — the lift itself, the full-amount threshold, the size-keyed row, the
close on a new level, the per-rule scope, the unnamed creature, the save's level, the
mouthful, and the field's home.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `Hazards.exhaustion_unlocked` | **Built** |
| 2 — lifted at the day's end, at the full amount | **Built**, in `with_day_ended`, both rules |
| 3 — a new level closes it | **Built**, in `with_exhaustion` |
| 4 — `with_long_rest` reads it | **Built** |
| 5 — recorded without a level held | **Built** |
| 6 — no die | **Built** by construction: nothing here adjudicates |

_Written 2026-09-06 against SRD v5.2.1._
