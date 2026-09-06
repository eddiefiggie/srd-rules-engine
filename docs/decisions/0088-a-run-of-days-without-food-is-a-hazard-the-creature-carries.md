# 0088 — A run of days without food is a hazard the creature carries

- **Status:** Accepted, 2026-09-06
- **Settles:** [#401](https://github.com/eddiefiggie/srd-rules-engine/issues/401)
- **Requirements:** R1, R4, R15, R17, R31, R32
- **Related:** [0080 — Dehydration is bookkeeping, and Malnutrition is two rules](0080-dehydration-is-bookkeeping.md),
  whose clause 7b this builds; [0081 — a campaign day's end is the fifth occasion](0081-a-campaign-days-end-is-the-fifth-occasion.md),
  which built the other half of p. 185 and left this one; [0028 — an Exhaustion level carries
  its cause](0028-a-level-carries-the-rule-that-caused-it.md), whose lock this puts a second
  rule's levels behind; [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  whose clause 5 put hazards on the creature

## Context

p. 185's *Malnutrition* is two rules, which 0080 found and 0081 built one of:

> A creature that eats but consumes less than half the required food for a day must succeed
> on a DC 10 Constitution saving throw or gain 1 Exhaustion level at the day's end. A creature
> that eats nothing for 5 days automatically gains 1 Exhaustion level at the end of the fifth
> day as well as an additional level at the end of each subsequent day without food.

The first sentence is an outcome — a die is asked — and 0081 compels it at a day's end and
rolls it through the one door. The second is bookkeeping, exactly p. 181's shape, and
[#401](https://github.com/eddiefiggie/srd-rules-engine/issues/401) said what it needed that
nothing had: **consecutive days without food, counted.** Every other campaign-axis fact was a
point in time or a condition with an expiry. A running count of days in which something did
*not* happen was a new kind of state, and #401 asked three questions about it: where it lives,
whether `with_day_ended` updates it, and how it interacts with the save.

## Options considered

**Option 1 — a field on `EncounterState`.** Rejected. A creature's hunger is a fact about the
creature and outlives any encounter; 0081's Consequences already say `EncounterState` is doing
campaign duty its name does not admit, and this would add to it.

**Option 2 — a bare field on `Combatant`.** The obvious home, and #401 called it the wrong
shape. It is not wrong, but it is one field short of a category the creature already has.

**Option 3 — a field on `Hazards`.** Taken. `Hazards` is "ongoing hazards a creature is
subject to" (0027 clause 5), it sits on the creature, and it exists precisely because Burning
and Suffocation are facts about one creature that are not conditions. Hunger is the third.

**Option 4 — the caller states the count.** Rejected outright. `burning` and `suffocating` are
caller-set because they are narrative facts the engine cannot observe. The count is
arithmetic over a fact the caller *already* states — how much each creature ate on each day
that ended — and a caller that set it would be choosing when a creature starves (R4's
direction, applied to a number that is not a die).

## Decision

**1. `Hazards.days_without_food`, an integer the engine advances and resets.** Never set by a
caller. Zero is a creature that ate on the last day anybody described, or that nobody has
described; the two are not distinguished because the rule does the same thing with both.

**2. `with_day_ended` counts it, for the creatures the caller names and no others.** A day the
caller says nothing about neither advances the count nor resets it — 0080 clause 3, applied
to the run. Advancing would starve a bystander on no evidence; resetting would feed one.

**3. A single mouthful breaks the run.** "Eats nothing" is the condition, so any food at all
resets the count to zero — including a quarter-pound that is also "less than half" and
compels the save. One day's food is read twice, for two different questions, and resetting
is not an exemption from the first sentence.

**4. The fifth day and every day after.** A level is gained outright when the count reaches
`STARVATION_DAYS` and on each day it rises past it. The run does not latch: "each subsequent
day" is a level every day, and a count that fired once and stopped would understate the rule
by a level a day.

**5. No die.** The level is `with_exhaustion` with `MALNUTRITION_RULE_ID`, applied in the state
transition and never adjudicated — p. 181's shape (0080 clause 1), and a `TurnLoop.end_day`
that ends a fifth day of nothing produces no ruling. The level carries the rule id (0028
clause 1), so 0028 clause 3's lock holds it against a Long Rest.

**6. A creature that has starved to death gains nothing more.** p. 181 makes level 6 death and
`with_exhaustion` refuses a seventh; a run that carries on past death adds nothing rather than
raising. The count keeps rising, because it is a count and not a condition.

**7. A negative day's food is refused.** It was read as "nothing" before, silently. A day's
food is what was eaten, and nothing was un-eaten.

**8. The `malnutrition` shape is claimed**, against the resolver, now that both sentences are
built — and only now, which is the standard #401 set: a shape claimed at half is the
overstatement R17's inventory exists to prevent.

## Why

**The count is arithmetic, and arithmetic is the engine's.** Every hazard flag before this
was a caller's because it stood for something the engine could not see. This one stands for
something the engine is told every day, in the same argument the save reads. Putting it in
the caller's hands would be the one thing R4 exists to prevent, in a form that has no die in
it: a number the caller supplies that decides an outcome.

**Clause 3 is the reading the sentence forces, and it is worth saying that it is harsh.** A
creature that eats a mouthful on day four starts over, and could eat a mouthful every fourth
day forever while rolling a save each time. That is what "eats nothing" means, and softening
it — a threshold below which food counts as nothing — would be a rule value R31 forbids.

**Clause 6 is the one a test found.** The first draft refused on the eleventh day, because
`with_exhaustion` refuses a seventh level and the count had reached it. A refusal there is a
day's end that cannot happen because a creature is dead, which is the wrong creature to stop a
campaign for.

## Consequences

**Accepted costs.**

- **`Hazards` now carries an integer beside two booleans**, and one the engine writes where
  the other two are the caller's. The docstring says which is which.
- **The lock never lifts, and that is not this record's.** p. 185's "until the creature eats
  the full amount of food required for a day" needs a per-creature unlock at a day's end and
  a `with_long_rest` that reads it; neither exists, for dehydration either. Filed as
  [#461](https://github.com/eddiefiggie/srd-rules-engine/issues/461), and the antecedent it
  needs — a day's food compared against the table — is what this change reads.

**Follow-on effects.**

- Coverage moves to **145 of 210**: `malnutrition` is claimed. Hazards are 5 of 5.
- 0080's row 7b and 0081's status prose both point here now.

## Evidence

Read in the official SRD v5.2.1 PDF, and asserted in `scripts/verify_d20_rules.py`:

- **p. 185**, *Malnutrition*: both sentences were asserted by #399 as one clause reaching "at
  the end of the fifth day". This change adds the continuation — "as well as an additional
  level at the end of each subsequent day without food" — as its own clause, because clause
  4 rests on it. A run of the verifier by somebody holding the document is what confirms the
  wording; the pattern is taken from the sentence as #401 quoted it.
- **p. 181**, *Exhaustion*: "You die if your Exhaustion level is 6", already asserted.

Engine side: twelve corruption proofs through `scripts/prove_guard_red.sh`, each red on the
test written for it — the fifth-day bound, the reset, the non-latching count, the death cap,
the unnamed creature left alone, the rule id, the lock, the negative refusal, the per-creature
count, the shape claim, the absence of a die, and the field's home.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `Hazards.days_without_food` | **Built** |
| 2 — counted at the day's end, named creatures only | **Built**, in `with_day_ended` |
| 3 — a mouthful resets | **Built**, and asserted beside the save it still compels |
| 4 — the fifth day and each after | **Built.** `STARVATION_DAYS` |
| 5 — no die, and the level carries the rule id | **Built**, and `end_day` is asserted to produce no ruling |
| 6 — past death, nothing more | **Built** |
| 7 — negative food refused | **Built** |
| 8 — the shape claimed | **Built.** `ENGINE_SHAPES`, the generator's `KINDS`, and the data file |

The unlock is not this record's and is [#461](https://github.com/eddiefiggie/srd-rules-engine/issues/461).

_Written 2026-09-06 against SRD v5.2.1._
