# 0044 — A quantity is a fact about the creature, not about the item

- **Status:** Accepted, 2026-08-29
- **Settles:** the design half of [#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273),
  which stays open as the build, and closes
  [0040](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md)'s watch on the next
  subtype of `Item`
- **Requirements:** R1, R15, R19, R20, R31, R32
- **Related:** [0039 — equipment is what a creature holds, wears and carries](0039-equipment-is-what-a-creature-holds-wears-and-carries.md),
  clause 2; [0040 — a weapon is an item](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2 and its accepted cost; [0020 — two kinds of time](0020-two-kinds-of-time.md)

## Context

> p. 89, **Ammunition.** You can use a weapon that has the Ammunition property to make a
> ranged attack **only if you have ammunition to fire from it**. The type of ammunition
> required is specified with the weapon's range. **Each attack expends one piece of
> ammunition.** Drawing the ammunition is part of the attack (you need a free hand to load a
> one-handed weapon). **After a fight, you can spend 1 minute to recover half the ammunition
> (round down) you used in the fight; the rest is lost.**

Ammunition is the last of p. 89-90's nine properties, and the only one that needs something
the engine has never had: **a thing there can be twenty of**. Every `Item` to date has been
one item.

**0040 named this moment in advance**, in its accepted costs:

> `isinstance` enters the engine as a discriminator. It is a real subtype test and not a
> `kind` field, but it is still a branch, and **the next subtype of `Item` will make it a
> chain**. Worth watching; not worth a registry today.

This is the next subtype — or would be.

## Options considered

**Option 1 — `Item.quantity`.** Rejected on 0039 clause 2, which holds `Item` to the fields
the engine has rules about *for every item*. A rope has a quantity of one and always will.
The rule that would read a count for every item is p. 178's carrying capacity — weight times
quantity — and it is not built, blocked on a `Size` this engine does not have
([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)). A field whose only
reader is unbuilt is the decay #228, #215 and #252 each found.

**Option 2 — an `Ammunition(Item)` subtype carrying a count.** Rejected, and it is the option
#273 framed the choice around. It follows 0040 clause 1's precedent honestly, and it makes
0040's own warning come true: a second `isinstance` branch beside `Weapon`, in a codebase that
already noted the chain was the thing to watch for.

**Option 3 — the count is a fact about the creature-item relation, and rides on `Carried`.**
Chosen, and it is the option #273 did not name.

## Decision

**1. A quantity belongs on `Carried`, not on `Item` and not on a subtype.** "How many arrows
this creature has" is a fact about the *having*, not about the arrow. Two creatures may hold
different numbers of the same thing; the same twenty arrows become a different number the
moment half are fired.

**This repository has made the opposite mistake twice and corrected it twice.** `proficient`
was a field on `Weapon` describing the *wielder* until 0040 clause 2. `wielded_two_handed` was
a field on `Weapon` describing how the *creature* gripped it until #263. Both were facts about
the creature-item relation stored on the item, both worked exactly while one item belonged to
one creature, and both failed the moment a second creature touched the same kind of thing.
**A count is the third instance of that shape**, and `Carried` — which already holds carriage
and grip — is where the first two ended up.

**It also disposes of 0040's watch item rather than triggering it.** No new subtype, no second
`isinstance` branch. The chain 0040 said to watch for does not form here, and the reason is
not restraint: it is that a count was never a kind of item in the first place.

**2. Which ammunition a weapon needs is the weapon's, and is content.** p. 89: "The type of
ammunition required is specified with the weapon's range." So `Weapon` carries the **id** of
the item it consumes, and what a Light Crossbow actually fires is a ruleset's to say — the
same split as 0040 clause 2's proficiency-by-id.

**3. Firing expends one piece, and firing without any is refused rather than resolved.** p. 89
makes having ammunition a condition of the attack — "only if you have ammunition to fire from
it" — so the read surface does not offer the shot, which is where R18 puts a legality this
computable.

**4. The free hand is p. 105's question asked again.** "(you need a free hand to load a
one-handed weapon)" is answerable today: #257 built the hand count, and `free_hands` already
returns `None` when no rule said how many a creature has. A creature whose count is unknown
gets the refusal that cannot invent one (0039 clause 4).

**5. The document defines when combat ends, and the engine may evaluate none of it.** This is
the clause that makes the second half a gate, and the reason is not the silence this record
first assumed.

> p. 14, *Ending Combat*: Combat ends when one side or the other is defeated, which can mean
> the creatures are **killed** or **knocked out** or have **surrendered** or **fled**. Combat
> can also end when **both sides agree to end it**.

Five conditions, and the engine can observe **two**. Killed and knocked out are hit points and
the Unconscious condition. Surrendered, fled, and both sides agreeing are judgements about the
fiction that no state this engine holds can answer — and R20 keeps the memory port typed
precisely so the engine never reads prose to find out.

**A test the engine can evaluate half of is a test it must not evaluate.** Deciding combat had
ended on the killed-and-knocked-out half alone would fire early and silently: a fight paused
while one side parleys is not over, and the engine would spend a minute and return arrows on
its own authority. The half it can see is the half that produces a *positive* answer, so the
error runs entirely in the direction of inventing an outcome — which is what makes this worse
than a coin flip rather than better.

**So it arrives supplied**, in the shape `with_time_passed` already uses: "the caller says how
much time passed — a narrative fact only the agent holds — and this decides every consequence."
The agent says the fight ended; the engine decides what that recovers.

**6. What was *used* is tracked, and it is the first per-encounter tally.** p. 89 recovers
"half the ammunition (round down) **you used in the fight**", which is not derivable from what
remains — a creature that started with six arrows and holds two may have fired four or fired
one and dropped three. So the tally is its own structure, and it is the first one on
`EncounterState` that **does not clear when the turn advances**: `discharged`,
`slots_expended_this_turn`, `light_attacks_this_turn`, `attacks_this_turn`, `swaps_this_turn`
and `loading_shots_this_turn` are all per-turn, and this one is per-fight.

## Why

**Clause 1 is the clause this record exists for, and the argument is historical rather than
aesthetic.** Options 1 and 2 are both defensible readings of where a count goes, and the
repository has already run this experiment twice with a different field and got the same
answer both times. Choosing the subtype would be choosing the shape that has failed here
before, on the strength of a precedent (`Weapon(Item)`) that is a genuine subtype rather than
a relation wearing one.

**Clause 5 is where the fidelity risk actually is, and this record got it wrong first.** The
sweep behind it initially reported that the document states no test for combat ending, and the
clause was written on that basis. It does state one, on p. 14, and finding it made the clause
*stronger* rather than weaker: an absent rule would leave the engine free to adopt any
reasonable convention, while a stated rule the engine can evaluate two-fifths of forbids the
convention outright. The wrong version and the right one reach the same decision by opposite
routes, which is exactly the kind of agreement that hides a bad argument — so the argument is
recorded rather than only the answer.

**Clause 6 is a structure worth naming rather than folding in.** Six per-turn structures exist
and a seventh that looks like them but clears on a different boundary is exactly the kind of
neighbour a reader generalises from. 0036 clause 3 made this argument once for cardinality;
this is the same argument for lifetime.

## Consequences

**Accepted costs.**

- **`Carried` grows a field, and `DetachedObject` does not.** A dropped quiver loses its count,
  because 0041 gave a detached object an `Item` and no relation. Disclosed; the rule that
  needs it can bring it.
- **Recovery does not ship with the firing half.** Clause 5 settles *how* it must arrive and
  clause 6 *what* it needs; building it needs a supplied-fact route this engine has not opened
  for encounters.
- **Nothing stops a ruleset giving a creature a quantity of a weapon.** Twenty longswords is
  expressible and meaningless. The alternative is a constraint the document does not state.

**Follow-on effects.**

- **`weapon-ammunition` resolves when the build lands**, and p. 89-90's nine properties are
  complete.
- **0040's watch on the `isinstance` chain closes** without the chain forming.
- **A per-encounter lifetime arrives on `EncounterState`**, which the next rule needing one can
  follow rather than re-decide.
- **The fight boundary becomes a named limit** rather than an unexamined one — and a
  *stated* rule the engine declines to evaluate, which is a different disclosure from a gap
  ([#301](https://github.com/eddiefiggie/srd-rules-engine/issues/301)).

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 89** (*Ammunition*, whole, and
*Weapon Proficiency*), **p. 90** (*Range*, *Loading*), **p. 105** (the free-hand clause
0039 clause 4 rests on), **p. 178** (carrying capacity, the only rule that would read a count
for every item).

**The sweep behind clause 5, including where it went wrong.** The document was searched for
`after a fight`, `combat ends`, `the fight ends`, `end of combat` and `when combat`. The first
returns exactly one hit, p. 89's own entry — and an earlier draft of this record stopped there
and concluded the document never says when a fight is over. **`combat ends` returns p. 14's
*Ending Combat* section**, which says precisely that.

The correction matters because it inverts the argument while preserving the conclusion. What
the engine faces is not a silence it may fill with a convention, but a **stated five-part test
it can evaluate two parts of** — and the two it can see are the ones that answer *yes*.

In the tree:

- `Carried` holds `item`, `carriage` and `hands` — the last two both facts about the relation
  that were fields on `Weapon` until #258 and #263.
- `Item.__post_init__` refuses a sixth field by test, and 0039 clause 2 states the bar.
- `EncounterState.with_time_passed` takes minutes from the caller and decides the consequences,
  which is clause 5's shape already in the tree.
- Six per-turn structures exist on `EncounterState`; none is per-encounter.

## Status of implementation

**Nothing here is built.** This record decides;
[#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273) builds clauses 1 to 4 and
6 and **remains open**. Clause 5's recovery is [#301](https://github.com/eddiefiggie/srd-rules-engine/issues/301).

| Clause | State |
|---|---|
| 1 — a quantity rides on `Carried` | **Decided, not built.** [#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273), the clause this record exists for |
| 2 — which ammunition a weapon needs is content, by id | **Decided, not built.** [#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273) |
| 3 — firing expends one, and firing without any is not offered | **Decided, not built.** [#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273) |
| 4 — the free hand is p. 105's question again | **Decided, not built.** [#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273) |
| 5 — p. 14's test is stated, and the engine may evaluate none of it | **Decided, not built.** [#301](https://github.com/eddiefiggie/srd-rules-engine/issues/301), split out so the firing half is not blocked behind a route for encounter-scoped narrative facts that does not exist |
| 6 — the used-tally is the first per-encounter structure | **Decided, not built.** [#273](https://github.com/eddiefiggie/srd-rules-engine/issues/273) |

_Written 2026-08-29 against SRD v5.2.1._
