# 0064 — Any D20 Test, not any saving throw

- **Status:** Accepted, 2026-08-30
- **Settles:** the Disadvantage half of [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367)
- **Requirements:** R14, R18, R32
- **Related:** [0054 — a save is rolled by a creature](0054-a-save-is-rolled-by-a-creature.md),
  which this widens; [0063 — training is a legality rule](0063-training-is-a-legality-rule.md),
  which disclosed it one build ago

## Context

> p. 177, *Armor Training*: If you wear Light, Medium, or Heavy armor and lack training with
> it, you have Disadvantage on **any D20 Test that involves Strength or Dexterity**, and you
> can't cast spells.

0063 built the casting prohibition and disclosed this one, because `D20Test.ability` existed
since 0054 and was passed by the **six save sites only**. Attacks and ability checks named no
ability, so a rule keyed on one could not reach them.

The disclosure said the field "would have to be threaded through those too before a central
rule could key on it — which is a change to every test-building site rather than to one", and
that it "should be done once for whatever else turns out to need it rather than for this clause
alone". Doing it as its own change is that, not a contradiction of it.

## Decision

1. **Every site that builds a `D20Test` names its ability.** The two attacks — `weapon.ability`,
   because p. 89 lets a Finesse wielder choose and what the attack *used* is what p. 177 keys
   on; p. 182's escape check, from the skill declared; p. 185's landing; and Perception, whose
   Wisdom is **stated** rather than left to an absent field.

2. **`core.report` is excluded and named.** It reconstructs a `D20Test` from a ledger entry
   rather than building one for a rule, and the ledger carries no ability.

3. **The transform is `_as_this_creature_rolls`, not `_saves`.** Three rules live there and
   each is scoped to what its own sentence says: p. 187's Restrained and p. 181's Dodge stay
   **save-only** because both say *saving throws*, and p. 177's does not.

4. **It accumulates, on both sides.** p. 8 cancels sources on opposite sides, so a Dodging
   creature in untrained armour rolls flat rather than at whichever the transform wrote last.

5. **The guard widened with the rule.** 0054's walk asked `TestKind.SAVE` sites to name their
   ability; it asks every kind now, because a site that omits it escapes a rule that is no
   longer save-only.

## Why

### Scoping three rules in one function is the risk, and the test says so

Putting p. 177's clause beside two save-only ones invites the next reader to assume all three
behave alike. Two corruptions guard that directly: one that makes p. 177's save-only, and one
that makes Restrained's reach an attack. Both go red, which is the pair that says the scoping
is a decision rather than an accident.

### One accumulation side was untested and a proof found it

`has_disadvantage=test.has_disadvantage or disadvantage` looked covered and was not: every case
had the *transform* contributing the Disadvantage, so dropping the `or` changed nothing. The
missing case is a rule that granted one — on a creature the transform gives Advantage to
instead. That test exists now, and the proof that found the gap is the one that passes on it.

## Consequences

- **`untrained-armour-disadvantage-not-applied` retires**, one build after it was written, and
  the clause count falls from 19 to 18 — the figure moving the way 0061 said it should.
- **The Shield clause is what remains of #367**, and it still waits on an Armour Class derived
  from what a creature wears.
- **No coverage figure moves — 117 of 210.** `armor-training` was claimed by 0063 while two of
  its three drawbacks were unbuilt, which is 0061's case again.

## Evidence

- p. 177 — "any D20 Test that involves Strength or Dexterity", and the two other drawbacks.
- p. 187, p. 181 — Restrained and Dodge, both of which say *saving throws*.
- p. 8 — that sources on opposite sides cancel.

## Status of implementation

**Every clause is built** by [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367)'s
Disadvantage half.

| Clause | State |
|---|---|
| 1 — every site names its ability | **Built.** Five sites threaded |
| 2 — `core.report` excluded and named | **Built.** In the guard's own docstring |
| 3 — three rules, each scoped to its sentence | **Built.** Asserted in both directions |
| 4 — accumulates on both sides | **Built.** Both asserted, the second added after a proof failed |
| 5 — the guard widened | **Built.** `test_every_d20_test_the_core_builds_names_its_ability` |
