# 0028 — An Exhaustion level carries the rule that caused it

- **Status:** Accepted, 2026-08-25
- **Settles:** [#180](https://github.com/eddiefiggie/srd-rules-engine/issues/180)
- **Requirements:** R1, R14, R31, R32 · touches R19
- **Related:** [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  whose clause 2 supplies the shape this borrows;
  [0019 — `kind` is a filing label](0019-kind-is-a-filing-label.md);
  [#178](https://github.com/eddiefiggie/srd-rules-engine/issues/178), which built the gain;
  [#140](https://github.com/eddiefiggie/srd-rules-engine/issues/140) and
  [#141](https://github.com/eddiefiggie/srd-rules-engine/issues/141), which wait on this

## Context

#178 built `EffectKind.EXHAUSTION_GAINED` and `EncounterState.with_exhaustion`, so a level can
be gained through a ruling. Nothing removes one, and the question of *what may* turned out to be
the whole remaining blocker on three hazards.

#180 framed it over three sources and four rules. Reading the document rather than the issue
found **seven sources and five removal shapes**, and two of the shapes are not what #180
anticipated.

### Every source, and every removal rule

| Source | Page | Gains |
|---|---|---|
| Dehydration | 181 | 1 at a day's end |
| Malnutrition | 185 | 1 at a day's end, on a failed DC 10 Constitution save |
| Suffocation | 189 | 1 at the end of each of its turns |
| Extended travel | 192 | 1 per hour beyond 8, on a failed Constitution save |
| Extreme cold | 195 | 1 per hour, on a failed DC 10 Constitution save |
| Extreme heat | 195 | 1 per hour, on a failed Constitution save |
| A contagion | 194 | 1, "which lasts until the contagion ends on the creature" |

| Removal | Page | Shape |
|---|---|---|
| A Long Rest removes **1** level | 181 | count-based, source-agnostic |
| Breathing again removes **all levels suffocation caused** | 189 | **source-scoped bulk** |
| Dehydration's and malnutrition's levels cannot be removed until the creature drinks or eats a full day's worth | 181, 185 | **source-scoped lock** |
| While a contagion holds *any* Exhaustion, a Long Rest reduces **none** of it | 194 | **global suppression** |
| A Potion of Vitality removes **any** levels | 236 | blanket |

Four of the five need to know something a count cannot hold. A creature at three levels — one
from suffocating, one from dehydration, one from a night's forced march — finishes a Long Rest,
and a bare integer cannot say which level came off or whether one could.

## Options considered

**Track only the sources that need it**, leaving an unattributed remainder (#180's option 2).
Rejected on the count: four of seven sources carry a removal rule of their own, and the fifth
shape suppresses the general rule entirely. "These few are special" is a claim the document does
not support, and a fourth, fifth and sixth special case is the shape that arrives one PR at a
time.

**An enum of sources.** Rejected under 0019. Enumerating them makes the set closed, and it is
demonstrably not: seven appear across the Rules Glossary, the Gameplay Toolbox and the magic
items, and nothing suggests that is all of them. An enum also has to be extended by whoever adds
a source, which is the step that gets missed.

**Model removal as a subtraction and let each rule compute a number.** Rejected. It puts the
provenance logic in every caller and keeps the wrong thing — a count — as the state. The lock
rules are not about how many levels come off; they are about *which*.

**Do not model removal, and disclose.** Rejected. Suffocation's removal is half its glossary
entry, and a hazard nothing can recover from is a wrong model rather than an incomplete one.

## Decision

**1. A level carries the id of the rule that caused it, and the count is derived.** Not an enum,
not a boolean per special case: the **rule id**, which is the shape
[0027](0027-occasions-and-outcomes-without-a-roll.md) clause 2 chose for obligations and for the
same reason. The engine already names every rule, a new source needs no type extended, and what
a level *is* is already answered by which rule produced it.

`Conditions.exhaustion_level` stays readable and becomes a derived sum, because p. 181's
arithmetic — ×2 on every D20 Test, ×5 feet of Speed, death at 6 — is over the total and nothing
else.

**2. Removal is a rule, not a subtraction.** Each removal names what it may take: a Long Rest one
level, breathing again every level a given rule caused, a potion all of them. A caller cannot
decrement the count, and `with_exhaustion` already refuses a gain below one for this reason —
removal that went through the gain would be the general rule wearing a minus sign.

**3. A locked level is invisible to the general rule rather than subtracted from it.** Dehydration
and malnutrition levels are excluded from what a Long Rest may remove. So a creature holding only
locked levels finishes a Long Rest and loses nothing, which is what pp. 181 and 185 say and is
easy to get backwards — an engine that removed one and then re-applied the lock would report the
same total by a route that is wrong for the next rule to read.

**4. When more than one level is removable, the engine declares an order and says so.** p. 181
says "removes 1 of your Exhaustion levels" and never which. The order is **most recently gained
first**, and that is an engine convention rather than SRD — declared here the way
[0025](0025-sight-is-a-relation-over-stored-state.md) clause 2 declares last-volume-wins for
overlapping light, because the document supplies no precedence and something has to be chosen.

It is very nearly immaterial: locked levels are already excluded by clause 3, and the levels that
remain differ only in which later rule could have taken them.

**5. A removal rule may be suppressed by state, and that is a third shape rather than a lock.**
p. 194's contagion does not mark its own levels as unremovable — it stops the Long Rest working
*at all*, on every level the creature holds. Marking levels cannot express that, so a removal
asks state whether it may run before it asks which levels it may take. The contagion itself is
[#141](https://github.com/eddiefiggie/srd-rules-engine/issues/141) and is not built here; what is
decided is that the shape exists and removal is written to admit it.

**6. Nothing removes a level yet, because nothing finishes a Long Rest.** `long-rest` and
`short-rest` are both unimplemented shapes. The general rule attaches to the rest and lands with
it — this record decides the data and the shape of a removal, and deliberately builds neither.
Filed as [#183](https://github.com/eddiefiggie/srd-rules-engine/issues/183).

**7. The potion is not reconciled here.** p. 236 removes "any" levels and pp. 181 and 185 say
theirs cannot be removed. That is two printed rules contradicting each other rather than one being
absent, and picking a winner would be inferring a rule value. Filed as
[#182](https://github.com/eddiefiggie/srd-rules-engine/issues/182), and nothing can reach it today
because neither the potion nor Dehydration is built.

## Why

**Clause 1 is the whole record and the rest follows.** Once a level knows its rule, three of the
five removal shapes are lookups. Clause 5 is the one that does not follow, which is why it is
stated rather than left to be discovered by whoever builds the contagion.

**The rule id rather than a source enum is the reuse that matters.** 0027 clause 2 reached the
same answer from the other direction — an obligation generalised by *removing* its
condition-specific field rather than widening it — and the argument is 0019's either way: a
closed set in the data is a branch in every consumer and a type to extend at every addition.

**#180's option list was built on a third of the evidence.** It reasoned over three sources
because three were in front of it; there are seven, and the two removal shapes it did not know
about are the two that decide the design. That is the fourth time in this project that reading
the document has falsified the framing of an issue written carefully without it.

## Consequences

**Accepted costs.**

- **`Conditions` changes shape**, and `exhaustion_level` stops being settable directly. Every
  construction site that sets it moves to naming a source. Internal tier under
  [0018](0018-api-stability.md) — `Conditions` is not in `stability.COMMITTED` — so no
  `API_VERSION` bump, but the test suite moves with it.
- **A level's rule id has to be recorded in the ledger** for a replay to reconstruct what a
  removal was entitled to take. That is a ruling payload change, additive, and it is
  [#183](https://github.com/eddiefiggie/srd-rules-engine/issues/183)'s to make rather than this
  record's.
- **Clause 4's order is a convention this engine invented.** It is disclosed, and it is the kind
  of thing that should be revisited if the document ever supplies one.

**Follow-on effects.**

- #140's Suffocation unblocks once #183 lands; Dehydration and Malnutrition still need a
  campaign-axis occasion (0027 clause 8).
- #141's afflictions gain a home for the contagion's Exhaustion, and clause 5 is what they need.
- Coverage is unchanged at **78 of 211**. A record resolves no shape.

## Evidence

No spike. Every source and every removal rule above was read off the document, and the two the
record turns on are now clauses in `scripts/verify_d20_rules.py`:

- p. 194's suppression, which is the only removal rule that marking levels cannot express.
- p. 236's blanket removal, which is what makes #182 a conflict rather than a gap.

The other six sentences were asserted by #178. `long-rest` and `short-rest` were confirmed
unimplemented in `effect_shapes.json`, which is what makes clause 6 a scoping fact rather than a
deferral.

## Status of implementation

**Clauses 1 and 2 are built. Clauses 3-5 are not, and clause 6 is why.**
`Conditions.exhaustion_levels` landed 2026-08-25 with Suffocation, the first rule whose
removal needed it.

| Clause | State |
|---|---|
| 1 — a level carries its rule id | **Built.** `Conditions.exhaustion_levels` is a tuple of rule ids and `exhaustion_level` is a derived sum. `exhaustion_from(rule_id)` answers p. 189's question. A level with an empty id is refused |
| 2 — removal is a rule, not a subtraction | **Built** for the one removal with a live consumer: `with_exhaustion_removed(caused_by=...)` takes the rule whose levels go, never a count. `with_breath_regained` is p. 189's caller |
| 3 — a locked level is invisible to the general rule | Not built, and unreachable: the general rule is the Long Rest, which does not exist. [#185](https://github.com/eddiefiggie/srd-rules-engine/issues/185) |
| 4 — most recently gained first, by engine convention | Not built, for the same reason. The order only matters to the general rule. #185 |
| 5 — a removal may be suppressed by state | Not built, and deliberately not exercised until the contagion exists ([#141](https://github.com/eddiefiggie/srd-rules-engine/issues/141)) |
| 6 — the general rule lands with the Long Rest | Still true, and now the only thing between clauses 3 and 4 and being built. #185 |
| 7 — the potion is not reconciled | Nothing to build. [#182](https://github.com/eddiefiggie/srd-rules-engine/issues/182) |

**Suffocation resolves because of clauses 1 and 2**, and nothing else here does. Coverage is
79 of 211.

_Updated 2026-08-25 when [#183](https://github.com/eddiefiggie/srd-rules-engine/issues/183)
landed. This record shipped saying "Decided, not built"._
