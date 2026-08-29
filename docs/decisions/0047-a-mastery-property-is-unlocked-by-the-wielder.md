# 0047 — A mastery property is unlocked by the wielder

- **Status:** Accepted, 2026-08-29
- **Settles:** [#317](https://github.com/eddiefiggie/srd-rules-engine/issues/317)
- **Requirements:** R15, R31, R32
- **Related:** [0040 — a weapon is an item and proficiency is the wielder's](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2, whose split this repeats for a second permission;
  [0046 — a default and the rule that says otherwise are two shapes](0046-a-default-and-the-rule-that-says-otherwise-are-two-shapes.md),
  which built the tenth weapon property immediately before this

## Context

p. 90 opens its Mastery Properties section by gating every one of the eight:

> Each weapon has a mastery property, which is **usable only by a character who has a feature,
> such as Weapon Mastery, that unlocks the property for the character**.

p. 89 says it a second time, in the Weapons table's column list:

> **Mastery.** Each weapon has a mastery property… **To use that property, you must have a
> feature that lets you use it.**

**Graze shipped ungated.** `_graze` fired on `weapon.graze` alone, so any creature handed a
Graze weapon got Graze. That is the permissive direction — a mechanic given to creatures the
rules do not give it to — and it was the state of the engine for the whole life of the
property.

The question had no default answer, and it governs all eight rather than any one of them,
which is why it was a gate. Deciding it per-mastery, seven more times, is how it gets decided
seven different ways.

### What the document actually supplies

The issue was filed assuming the unlocking feature was content outside the SRD. It is not.
**Five classes ship Weapon Mastery in SRD 5.2**, and the wording is close to identical:

| Class | p. | Kinds at level 1 | Constraint on the choice |
|---|---|---|---|
| Barbarian | 29 | 2 | "Simple or Martial **Melee** weapons of your choice" |
| Fighter | 48 | 3 | "Simple or Martial weapons of your choice" |
| Paladin | 54 | 2 | "of your choice **with which you have proficiency**" |
| Ranger | 59 | 2 | "of your choice **with which you have proficiency**" |
| Rogue | 62 | 2 | "of your choice **with which you have proficiency**" |

All five phrase the grant the same way — *"Your training with weapons allows you to use the
mastery properties of N kinds of … weapons"* — all five let the choice change on a Long Rest,
and each class's table has a **Weapon Mastery** column widening the count with level.

So the permission is a **set of weapon kinds the character chose**, bounded in size by a class
progression, and the document supplies it rather than leaving it to be invented.

## Options considered

**Option 1 — a permission on the creature, by weapon id.** Chosen.

**Option 2 — ungated, disclosed in `unenforced_clauses`.** Rejected. It is what the repository
does when a rule's input is genuinely absent, and the input is not absent: the classes are in
the document and the relation they produce is expressible. Disclosing a rule the engine could
enforce would be R32 covering for a gap rather than naming one.

**Option 3 — derive mastery from `weapon_proficiencies`.** Rejected, and the table above is
why. See clause 2.

**Option 4 — refuse the property until creatures can carry features, removing Graze.**
Rejected. It throws away a built, correct mechanic to avoid modelling a permission that is one
frozenset.

## Decision

**1. The permission is the wielder's, held as resolved weapon ids.** `Combatant.mastery_weapons:
frozenset[str]`. p. 90 writes "**such as** Weapon Mastery", deliberately leaving the set of
unlocking features open, and the features themselves are class content this repository does not
ship (R31). So the engine holds the *result* — which weapons this creature may use the mastery
property of — and never the *source*. A ruleset that knows the class tables expands them into
ids. This is 0040 clause 2's split exactly, and `may_substitute_focus` is the same shape again.

**2. It is a separate relation from proficiency, not a subset of it.** The five classes do not
agree: Paladin, Ranger and Rogue require proficiency; Barbarian and Fighter do not. Deriving
one from the other would be right for three classes and invented for two — and it is the
smaller set in every case, since a Fighter is proficient with far more weapons than the three
whose mastery it may use. Two independent frozensets, and the pair is asserted in both
directions: proficient without mastery adds the Proficiency Bonus and no Graze; a master who is
not proficient gets Graze and no bonus.

**3. Empty by default, and that is the answer for every monster.** p. 89 gives proficiency an
explicit monster rule — "A monster is proficient with any weapon in its stat block" — and p. 90
gives mastery **no parallel**. It says "a **character**". Reading one across from the other
would grant every monster the mastery property of everything it holds, on the engine's own
authority. An empty default also errs the safe way: it withholds a benefit rather than
inventing one, which is the same direction `reactions` chooses for an Opportunity Attack it
cannot fully evaluate.

**4. Graze is retro-fitted in the same change.** A mastery that already shipped under the old
answer is exactly the drift a settled record exists to prevent. No shipped data loses anything:
no bestiary entry and no fixture carries a Graze weapon, so the only creatures affected are the
ones a caller constructs.

**5. The size bound and the Long Rest re-choice are the ruleset's, and nothing is owed here.**
"N kinds" comes from a class-and-level table, and "whenever you finish a Long Rest, you can
practice weapon drills and change one of those weapon choices" is a character-building rule
rather than an adjudication one. The engine holds the current set and does not police how it
came to be — precisely as it does not check that a creature's `weapon_proficiencies` matches a
class it never sees. This is **not** an `unenforced_clauses` disclosure for the same reason
that one does not exist for proficiency: the engine is not holding a rule it declines to
enforce, it is holding a resolved relation whose provenance belongs to the ruleset.

**6. Every mastery built from here takes this gate, and none is built without it.** The seven
remaining are [#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318) (Vex),
[#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319) (Sap),
[#320](https://github.com/eddiefiggie/srd-rules-engine/issues/320) (Nick),
[#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321) (Topple),
[#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322) (Slow),
[#323](https://github.com/eddiefiggie/srd-rules-engine/issues/323) (Cleave) and
[#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324) (Push). The check belongs at
the point the property takes effect, next to the `weapon.<property>` flag, so a mastery cannot
be added without meeting it.

## Consequences

**No shape moves.** The inventory measures resolved effect shapes, and `mastery-graze` was
claimed before this and is claimed after. Reading a still figure as "nothing happened" is the
misreading the README's own note warns about: what changed is that the mechanic is now given to
the creatures the rules give it to, rather than to all of them.

**A caller that wants Graze must now say so.** That is a behavioural change to a shipped
mechanic, and it is the point. It is also discoverable in the only way that matters — a Graze
weapon that no longer grazes sends its author to `mastery_weapons`, where the field's own note
carries p. 90.

## Status of implementation

**Every clause is built** by [#317](https://github.com/eddiefiggie/srd-rules-engine/issues/317),
except clause 6, which constrains work tracked elsewhere and is listed with its issues.

| Clause | State |
|---|---|
| 1 — the permission is the wielder's, by id | **Built.** `Combatant.mastery_weapons` ([#317](https://github.com/eddiefiggie/srd-rules-engine/issues/317)) |
| 2 — separate from proficiency, neither implying the other | **Built.** Asserted in both directions in `test_mastery_is_not_derived_from_proficiency` ([#317](https://github.com/eddiefiggie/srd-rules-engine/issues/317)) |
| 3 — empty by default, monsters included | **Built.** The field defaults to `frozenset()`, and the field's note carries p. 89's monster rule and p. 90's absence of one ([#317](https://github.com/eddiefiggie/srd-rules-engine/issues/317)) |
| 4 — Graze retro-fitted in the same change | **Built.** `_graze` takes the actor and checks `mastery_weapons` ([#317](https://github.com/eddiefiggie/srd-rules-engine/issues/317)) |
| 5 — the size bound and Long Rest re-choice are the ruleset's | **Nothing to build.** A deliberate non-requirement, and deliberately not a disclosure — see the clause for why proficiency has none either |
| 6 — every mastery built from here takes this gate | **Not built**, seven times, and each is tracked: [#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318), [#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319), [#320](https://github.com/eddiefiggie/srd-rules-engine/issues/320), [#321](https://github.com/eddiefiggie/srd-rules-engine/issues/321), [#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322), [#323](https://github.com/eddiefiggie/srd-rules-engine/issues/323), [#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324) |
