# 0048 — A forced save is one mechanism, whatever compelled it

- **Status:** Accepted, 2026-08-29
- **Settles:** the design half of [#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)
- **Requirements:** R1, R4, R15, R30, R31
- **Related:** [0036 — a fourth occasion, owed by whoever took the damage](0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md),
  whose clauses 3 and 4 this generalises and whose clause 6 decides it;
  [0047 — a mastery property is unlocked by the wielder](0047-a-mastery-property-is-unlocked-by-the-wielder.md),
  clause 6, which every mastery built from here answers to;
  [0018 — API stability](0018-api-stability.md), for the rename on a Provisional surface

## Context

p. 90's Topple compels a save the engine had no general way to owe:

> **Topple.** If you hit a creature with this weapon, you can force the creature to make a
> Constitution saving throw (DC 8 plus the ability modifier used to make the attack roll and
> your Proficiency Bonus). On a failed save, the creature has the Prone condition.

The engine had exactly one mechanism for a save a creature owes and has not rolled:
`concentration_saves_owed`, a queue of `ConcentrationDebt(combatant_id, amount)`, drained by
one helper the loop calls from all three adjudicating phases. 0036 built it for p. 179 and
built it well — detection where the trigger fires, production in the loop, one debt per
triggering instance rather than the once-per-turn keying `discharged` uses.

**It was Concentration-shaped in its payload and general in its design.** The queue carried a
damage amount because p. 179's DC is a function of damage; everything else about it — the
cardinality, the drain, the discharge-regardless-of-outcome rule — is about forced saves in
general.

## The argument is 0036's own, read forwards

Clause 3 justified refusing to widen `discharged`:

> Two mechanisms with different cardinalities are two structures.

Topple's cardinality is the queue's: **one save per triggering instance, owed by one
creature.** A Multiattack landing twice with a Topple weapon compels two, exactly as being
struck twice while concentrating compels two. By clause 3's own rule, same cardinality means
one structure.

Clause 6 decides what happens if that is ignored:

> **All three adjudicating phases discharge the queue**, through one shared helper rather
> than three call sites. Three copies is how one gets missed.

A second, Topple-shaped queue would need draining from the same three phases — so the choice
was one queue, or a second copy of the thing 0036 wrote a clause to avoid.

## Options considered

**Option 1 — generalise the queue.** Chosen.

**Option 2 — a parallel `topple_saves_owed`.** Rejected. It duplicates the drain across the
three phases, which is clause 6's named hazard, and it does so to keep a payload field one
rule uses — the shape [0019](0019-kind-is-a-filing-label.md) refuses.

**Option 3 — resolve the save inside the attack's ruling.** Rejected, and it is not available
anyway: a `Proposal` carries one `D20Test`, and a second outcome produced inside a resolver
would be a second path to an outcome (R1).

## Decision

**1. One queue, `forced_saves_owed`, holding `ForcedSave`.** `ConcentrationDebt` is renamed
and widened; `concentration_saves_owed` becomes `forced_saves_owed`. The cardinality, the
oldest-first order, the not-`discharged` keying and the discharge-regardless-of-outcome rule
are 0036's and are unchanged.

**2. The debt carries `rule_id`, and the rule id selects the resolver.** The declaration's
label is prose, and an engine reading prose to choose a mechanic is the capability being
removed — which is the reason `core.save_ends` gives for one rule per condition. Each
resolver checks that the debt in front of it is its own, because a loop and a rule that have
come apart would otherwise roll the wrong save silently.

**3. The DC and its derivation are computed where the trigger fires, not where the save is
rolled.** 0036 clause 4 carried the damage amount because the hit points it came from move
before the save is discharged. That reason reaches further than the amount, and Topple is why:

- The DC uses **"the ability modifier used to make the attack roll"**, and p. 89 lets a
  Finesse wielder choose Strength or Dexterity. Nothing records the choice once the attack is
  over.
- It uses **the attacker's** Proficiency Bonus, and by the time the loop rolls the save it has
  the target and no attacker at all.

Neither is stale afterwards; both are *gone*. So the debt carries `dc` and `dc_basis`, and
R4 holds for the same reason it did before — the resolver closes over numbers the **engine**
recorded, never ones a caller supplied. `dc_basis` travels with the DC because a target number
without its derivation is half a ruling (R30).

**4. Each rule decides when its own save is owed; the queue decides nothing.** p. 179 owes a
save on "the damage taken", so an Immune creature owes none (0036 clause 5). p. 90 owes one
on the **hit**, so an Immune creature owes one anyway — it took nothing and still has to keep
its feet. Two triggers, one queue, and the queue is right not to have an opinion.

**5. Staleness is the rule's, and it stays a branch until a fourth rule needs one.** The drain
drops a debt for a creature that has left the encounter — general, and not a skip, because
there is nobody for the outcome to be about. It also drops a Concentration debt for a creature
no longer concentrating, which is p. 179's alone: the save is compelled *to maintain*
Concentration. Topple has no counterpart, because a creature already Prone still rolls and
p. 90 states no exemption. The branch is keyed by `rule_id`; a third rule with its own
staleness adds one, and a fourth wants a registry. The comment in the drain says so, which is
where that decision starts rather than where it is made.

**6. `CONCENTRATION_RULE_ID` and `CONCENTRATION_SAVE_ABILITY` move to `core.spellcasting`.**
`EncounterState.with_damage` now builds the whole `ForcedSave` where the trigger fires, so it
needs both — and `core.concentration` imports state, so state cannot import it back. They are
facts about the rule, and `core.spellcasting` already holds p. 179's arithmetic.
`core.concentration` re-exports them explicitly, so neither name moved for a reader and
`core/__init__.py` is untouched.

**7. The rename is on a Provisional surface, and `API_VERSION` is not bumped.**
`EncounterState`'s fields are not part of the COMMITTED surface [0018](0018-api-stability.md)
enumerates, and no COMMITTED type gains, loses or renames anything. `TurnOutcome.consequential`
— added by 0036 clause 7 — needed nothing: it was named for what a ruling *is* rather than for
the rule that caused it, so a Topple save arrives in it unchanged. Its docstring did need
correcting, because it said "today, the Concentration save damage compels" and there are now
two. Stated here rather than left to be inferred.

## Consequences

**Topple ships**, and the inventory moves to **106 of 210**. Weapon masteries are 3 of 8.

**Concentration's behaviour does not change.** Its DC is now computed when the damage lands
rather than when the save is rolled, from the same input to the same function, so the number
and its sentence are identical. The pre-existing tests are the evidence: they assert the DC
rather than the amount now, and none of them changed what it expects the save to be rolled
against.

**The next forced save is a `ForcedSave` and a resolver.** Spells that allow a save, p. 191's
Breaking Objects, the Gameplay Toolbox poisons — none of them needs a queue, a drain, or a
turn-loop change. That is the return on generalising here rather than after the third one.

## Status of implementation

**Every clause is built** by [#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321).

| Clause | State |
|---|---|
| 1 — one queue, `ForcedSave` | **Built.** `EncounterState.forced_saves_owed`, `with_forced_save`, `forced_save_for`, `with_forced_save_discharged` ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
| 2 — the rule id selects the resolver, and each checks its own | **Built.** Asserted in both resolvers, and `test_the_resolver_refuses_a_debt_belonging_to_another_rule` covers the crossed case ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
| 3 — the DC and its derivation are computed at the trigger | **Built.** `ForcedSave.dc` and `dc_basis`, refused empty at construction ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
| 4 — each rule decides when its save is owed | **Built.** p. 179 records after defences, p. 90 records on the hit branch; asserted against an Immune target ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
| 5 — staleness is the rule's, keyed by `rule_id` | **Built.** The drain's Concentration branch, with the general departed-creature check above it ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
| 6 — the two constants move to `core.spellcasting` | **Built.** Re-exported from `core.concentration`, and the module-constant pin updated to say so ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
| 7 — Provisional rename, no `API_VERSION` bump | **Built.** No COMMITTED type changed; `TurnOutcome.consequential` needed no rename and its docstring is corrected ([#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321)) |
