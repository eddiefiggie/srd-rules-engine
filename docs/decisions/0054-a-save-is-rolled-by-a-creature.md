# 0054 — A save is rolled by a creature

- **Status:** Accepted, 2026-08-30
- **Settles:** [#344](https://github.com/eddiefiggie/srd-rules-engine/issues/344)
- **Requirements:** R1, R14, R18, R31
- **Related:** [0053 — the target chooses, and the engine rolls](0053-the-target-chooses-and-the-engine-rolls.md),
  which found this and rests on it;
  [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  clause 6, whose testless shape this reaches from a proposal that had a test;
  [0018 — three stability tiers](0018-api-stability.md)

## Context

Three printed rules act on a saving throw because of what the **roller** is holding, and none
of them belongs to the rule that compelled the save:

> pp. 186, 189, 191 — **Saving Throws Affected.** You automatically fail Strength and Dexterity
> saving throws. *(Paralyzed, Petrified, Stunned, Unconscious)*
>
> p. 187 — **Saving Throws Affected.** You have Disadvantage on Dexterity saving throws.
> *(Restrained)*
>
> p. 181 — ...and you make Dexterity saving throws with Advantage. *(Dodge)*

**None of them reached a roll.** `ConditionEffects.dexterity_saves` and
`auto_fail_strength_and_dexterity_saves` were modelled field by field from the glossary, and
`ActionBudget.dexterity_saves` had existed since the Dodge action shipped. Six resolvers built
a `TestKind.SAVE` — concentration, death, topple, save_ends, spellcasting, and 0053's Grapple
and Shove — and not one consulted the creature rolling it. Every save in this engine was a bare
ability modifier against a DC.

The tests that existed asserted the *data*: that Restrained's `dexterity_saves` is
`DISADVANTAGE`, and that the four auto-fail conditions are those four. Nothing asserted that a
Restrained creature's Dexterity save was actually rolled at Disadvantage, because nothing made
it so.

### How it was found, and what the inventory could not see

0053 rejected "let the engine pick the better save" on the strength of p. 187: a Restrained
creature with a better Dexterity modifier should still choose Strength. Checking that the
engine could *express* that turned up the fact that it could not — it does not apply the rules
that decide which save is better.

All five conditions were already marked implemented in the effect-shape inventory, and
correctly by its own terms: the condition exists, is applied, is held, and is reported. R17's
instrument measures whether a shape resolves, not whether every clause of it reaches a roll.
That gap is real and this record does not close it; what it closes is these three clauses.

## Options considered

**Option 1 — each resolver consults the roller.** Rejected. Six copies of the same three rules,
and a seventh resolver written next year that does not know they exist. This repository names
that failure more often than any other: a rule every call site must remember is a rule some
call site will not.

**Option 2 — a shared `save_test(...)` constructor resolvers call.** Rejected, and it is the
respectable version of Option 1. It removes the duplication and keeps the forgetting: a new
resolver that builds a `D20Test` directly gets nothing, and nothing tells it.

**Option 3 — apply it centrally, where the proposal is turned into a roll.** Chosen. One place,
after the resolver returns and before the die. A resolver written next year gets all three
rules without knowing they exist, and the rules stay where they are described — `Conditions`
and `ActionBudget` answer, the adjudicator applies.

**Option 4 — roll the die and force a failure.** Rejected for the automatic-failure half.
p. 186 says the save fails, not that it is rolled badly. A die in the ledger that decided
nothing reads exactly like a save that was rolled and lost.

## Decision

1. **`D20Test.ability` is first-class.** Two of the three rules key on which ability is being
   rolled, and it was recoverable only by parsing `Modifier.source` for an `"ability:"` prefix —
   a convention nothing enforced and a new resolver would not know to follow.

2. **`ability=None` is a value, not an omission.** p. 17: "Unlike other saving throws, this one
   isn't tied to an ability score." A Death Saving Throw is a save of no ability, and it is made
   by an Unconscious creature — one of the four that auto-fail Strength and Dexterity saves. A
   rule that reached it would kill every character who ever dropped.

3. **The three rules are applied in `Adjudicator._adjudicate`**, between the resolver and the
   roll.

4. **An automatic failure is not a roll**, so no die is drawn and the `Ruling` carries no
   `D20Result`. The failure branch is selected by the adjudicator directly rather than by
   rewriting the proposal — see below.

5. **Advantage and Disadvantage accumulate onto what the rule granted**, never replacing it.
   p. 8 cancels sources on opposite sides, and cancellation needs both to arrive.

6. **Dodge is re-asked, not remembered.** `Combatant.is_dodging` re-checks p. 181's two
   take-backs rather than trusting the flag.

7. **A static guard asserts every save in the core names its ability**, walking the AST of
   every `core` module for a `D20Test` of kind `SAVE`. It checks that the keyword is
   **present**, not that it is non-`None`: presence is a decision and absence is an oversight.

## Why

### The auto-failure could not be a rewritten proposal, and a test found out

The obvious implementation is `replace(proposal, test=None, outcome=proposal.on_failure)`,
resolving through 0027 clause 6's existing testless path. It is wrong, and the case that breaks
it was already in the tree: **`core.save_ends` builds a save with an empty `on_failure`.**
Failing to shake a condition off simply leaves it, so there is nothing to record — and a
proposal with no test and no outcome is one `Proposal` refuses to construct, by a validator
that is right to.

So the branch is selected in the adjudicator and the proposal is never rewritten. `always`
survives untouched, which is 0038 clause 6: what the act cost does not depend on how it went.

### An interaction that does not cancel, for a better reason

Restrained gives Disadvantage on Dexterity saves and Dodge gives Advantage, so a Restrained
dodger looks like p. 8's cancellation. It is not. **Restrained sets Speed 0**, and p. 181 ends
the Dodge for exactly that — "You lose these benefits if you have the Incapacitated condition or
if your Speed is 0". The Advantage is gone before cancellation could happen, and the save is at
plain Disadvantage.

That is `is_dodging` re-asking rather than trusting a flag, and it is why clause 6 is a clause.
The test asserting it was written expecting the opposite.

### What this does not do

Nothing here gives an agent a *better-informed* choice under 0053: `SaveOption.modifier` is
still the bare ability modifier, because the advantage state is not a modifier and the automatic
failure is not a number. Reporting either at the point of choice is a read-surface question and
is not this record.

## Consequences

- **No coverage figure moves.** All five conditions and the Dodge action were already claimed,
  and correctly by R17's terms — the shape resolved, and two of its clauses reached no roll.
  A build that fixes fidelity inside a claimed shape is exactly the kind the inventory cannot
  see, which is worth knowing about the instrument.
- **A new static guard**, in the shape [#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334)
  taught: derived from the source rather than pinned against a list of the six saves that exist
  today.
- **Five clauses added to `scripts/verify_d20_rules.py`**, which reports 265 verified. The
  Death Saving Throw one was written from memory, failed, and was corrected against the
  document — the verifier catching an author, which is what it is for.

## Evidence

- pp. 186, 189, 191 — Paralyzed, Stunned and Unconscious each failing Strength and Dexterity
  saves outright, matched inside each condition's own entry so the sentence is attributed
  rather than merely present. Petrified carries the same clause and is asserted through
  `EFFECTS`.
- p. 187 — Restrained's Disadvantage on Dexterity saving throws.
- p. 181 — Dodge's Advantage, and the two circumstances that take it back.
- p. 17 — that a Death Saving Throw is tied to no ability score.

## Status of implementation

**Every clause is built** by [#344](https://github.com/eddiefiggie/srd-rules-engine/issues/344).

| Clause | State |
|---|---|
| 1 — `D20Test.ability` | **Built.** Passed by all six save sites |
| 2 — `None` is a value, and death saves are it | **Built.** Stated at `core.death`'s call site and asserted |
| 3 — applied centrally | **Built.** `_as_this_creature_saves`, between the resolver and the roll |
| 4 — an automatic failure draws no die | **Built.** `_save_fails_outright`; asserted over all four conditions and both abilities |
| 5 — the flags accumulate | **Built.** Asserted against a rule that granted Advantage |
| 6 — Dodge is re-asked | **Built.** Asserted through the Restrained dodger |
| 7 — a static guard over every save in the core | **Built.** `test_every_save_the_core_builds_names_its_ability` |
