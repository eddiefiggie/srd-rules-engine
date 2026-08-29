# 0042 — Equipping rides on the attack that permits it, and the second interaction is unmodelled

- **Status:** Accepted, 2026-08-29
- **Settles:** the design half of [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283),
  which stays open as the build
- **Requirements:** R1, R15, R18, R19, R31, R32
- **Related:** [0041 — an item that leaves a creature is an object](0041-an-item-that-leaves-a-creature-is-an-object-somewhere-unstated.md),
  whose clause 6 this settles the shape of;
  [0040 — a weapon is an item](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 3, whose computed-menu principle is the constraint here;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md)

## Context

0041 clause 6 called p. 177's equip and unequip "printed in full across three pages" and
treated the build as mechanical. It is not. The **mechanism** is printed; how it attaches to
this engine's declaration model is not, and one composition question the document never
answers sits underneath it.

> p. 177, *Attack [Action]*: You can either equip or unequip **one** weapon when you make an
> attack as part of this action. You do so **either before or after the attack**. If you equip
> a weapon before an attack, you don't need to use it for that attack. Equipping a weapon
> includes drawing it from a sheath or picking it up. Unequipping a weapon includes sheathing,
> stowing, or dropping it.

> p. 13, *Your Turn*: You can interact with **one object or feature of the environment for
> free**, during either your move or action… If you want to interact with a second object, you
> need to take the Utilize action.

> p. 12: interactions with objects are limited: **one free interaction per turn**… Any
> additional interactions require the Utilize action.

> p. 191, *Utilize [Action]*: You **normally interact with an object while doing something
> else, such as when you draw a sword as part of the Attack action**. When an object requires
> an action for its use, you take the Utilize action.

**Two allowances, different cardinalities, and no stated relationship.** p. 13 grants one
interaction *per turn*; p. 177 grants one *per attack made as part of the Attack action*.
p. 191 uses drawing a sword during the Attack action as its example of interacting "while
doing something else", which reads as though the two are the same allowance — and never says
so. If they were one budget, p. 177's per-attack phrasing would mean nothing to a creature
with more than one attack; if they are two, a creature may swap a weapon *and* open a door.
The document supports neither reading over the other.

## Options considered

**Option 1 — declare the two budgets independent.** Rejected as a *stated* rule. It is the
reading p. 177's cardinality suggests and it is still a guess, and R31 does not soften for a
well-motivated one.

**Option 2 — declare them shared.** Rejected for the same reason, and it additionally makes
p. 177's "when you make an attack" phrasing inert, which is a poor way to treat a sentence the
document chose to write.

**Option 3 — offer equip and unequip as standalone actions, gated on the Attack action being
available.** Rejected. p. 177 licenses the swap "when you **make an attack** as part of this
action", so a creature that equips and then never attacks has done something no rule permits.
The engine would be granting a free weapon swap on the strength of an attack that never
happened.

**Option 4 — offer them only *after* an attack has been made.** Rejected, and it is the
tempting conservative one. It cannot invent anything, and it refuses the single commonest use
of the rule — drawing a sword and swinging it in the same turn. 0030 resolves *away from
invention*; it does not license refusing the mechanic's main case when a faithful shape exists.

**Option 5 — the equip rides on the attack declaration, enumerated one offer per (attack,
item) pair.** Chosen.

## Decision

**1. The equip is part of the attack, not an action beside it.** It is declared with the
attack and applies when the attack does. A creature that does not attack does not swap a
weapon, which is what p. 177 says and what Option 3 could not hold.

**2. "Before or after" is enumerated by *which weapon the attack names*, not by a separate
ordering field.** This is the clause that makes the shape small enough to build.

p. 177 draws the distinction for exactly one mechanical purpose: whether the newly-equipped
weapon is available to *this* attack. It then says the answer may be no even when you equipped
first — "you don't need to use it for that attack." So the pair `(attack weapon, equipped
item)` already carries the whole distinction:

- the attack names the item just equipped → equipped **before**, and used;
- the attack names a different weapon → equipped before and unused, or after, which p. 177
  makes mechanically identical.

An explicit `before`/`after` field would double the offer set to record a difference that
changes nothing the engine can observe. A third state nobody can distinguish is the kind of
field 0019 refuses.

**3. It is offered, not checked afterwards** (0040 clause 3, R18). One `LegalAction` per
(attack, equippable item) and per (attack, unequippable item), alongside the plain attack. The
set is computed from what the creature holds, what it has stowed, and what it can reach — so
the agent chooses from a menu the engine built rather than naming a swap the engine has to
validate after the fact.

**Bounded, and worth stating because Option 5's cost is the offer count.** The multiplier is
`1 + stowed items + held items + reachable detached objects`, not a combinatorial product with
an ordering flag.

**4. Unequipping to the ground is p. 191's detachment, and equipping from it is the reverse.**
p. 177's "sheathing, stowing, or **dropping** it" routes a drop through
[#280](https://github.com/eddiefiggie/srd-rules-engine/issues/280)'s `OBJECT_DETACHED`; its
"drawing it from a sheath or **picking it up**" is a `DetachedObject` becoming `HELD` again.
Nothing new is needed for either — 0041 built both directions of the boundary.

**5. An unplaced object cannot be picked up, and the refusal says so.** 0041 clause 4's
accepted cost lands here, which is where a player actually meets it: an object whose position
no rule stated is not reachable, so it is not on the menu. `unplaced_objects` is what keeps
that legible rather than an empty list (#267).

**6. p. 13's free object interaction is not modelled, and its relationship to p. 177 is
recorded as unstated rather than resolved.** The engine tracks p. 177's allowance on its own
terms and claims nothing about the other.

**This is a deferral the engine can currently make honestly, and that is checkable rather than
asserted.** The two readings differ only in a turn containing a *second* object interaction,
and the engine has no second route to one: `utilize` is an unimplemented shape (p. 191), and
nothing grants a second attack within the Attack action — Extra Attack is class content this
repository does not ship (R31) and `multiattack` (p. 258) is unimplemented. **The first of
those to land is what makes the question answerable-or-not, and it must be answered then
rather than inherited.**

**Both were tracked by nothing when this record was written**, which would have made the
condition above a promise rather than a trigger. They are [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288)
and [#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289), each filed carrying
this clause, so the work that makes the silence reachable is the work that finds it.

## Why

**Clause 2 is the clause this record exists for.** "Before or after" reads like state the
engine must carry, and modelling it that way is the obvious first move — it is what the
sentence appears to describe. Following the sentence to *what it decides* instead shows it
selects among weapons rather than among orderings, and the second half of p. 177's own clause
says so outright. The difference is a doubled offer set recording a distinction with no
observable consequence.

**Clause 6 is a deferral, and deferrals are where this repository has been wrong before.** The
protection is that the condition for revisiting is a *shipped mechanic* rather than a promise
to remember: whoever builds `utilize` or `multiattack` finds this clause because their work is
what makes the silence reachable. A deferral nobody can trip over is one nobody re-reads.

**Options 1 and 2 are both defensible and that is the argument against them.** A composition
rule the document does not state, chosen because it is the better-motivated of two guesses,
becomes indistinguishable from a printed rule as soon as it is inside a ruling — which is the
harm R31 names. Recording the silence costs a capability the engine does not have yet.

## Consequences

**Accepted costs.**

- **A creature cannot swap a weapon except by attacking.** Faithful to p. 177, and it means
  the engine offers no way to sheathe a sword on a quiet turn — that is p. 13's free
  interaction, which clause 6 does not model.
- **The attack offer set grows by a multiplier.** Bounded by what the creature carries and can
  reach, and the plain attack stays on the menu.
- **A dropped weapon in a positionless encounter still cannot be retrieved**, now visibly: the
  pick-up simply is not offered. 0041 shipped this cost; this is where it is felt.
- **Two SRD sentences are held unresolved against each other**, disclosed rather than settled.

**Follow-on effects.**

- **0041 clause 6 gains a shape**, and [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283)
  stays open as its build. **This record does not close it** — a record that closes an issue
  may not also cite it as the holder of unbuilt work, which 0041's Status section learned the
  hard way.
- **`utilize` and `multiattack` each acquire a prerequisite** they did not have, and each
  acquires an issue: [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) and
  [#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289). Whichever lands first has
  to answer clause 6's question. #289 also turns out to be named by
  [#271](https://github.com/eddiefiggie/srd-rules-engine/issues/271) and by p. 179's
  concentration-debt reasoning, so three separate pieces of work were waiting on a shape
  nothing tracked.
- **Coverage does not move.** This decides; #283 builds.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 10** (the Actions table, *Utilize*:
"Use a nonmagical object"), **p. 12** (*Time-Limited Object Interactions*, whole), **p. 13**
(*Your Turn*, *Interacting with Things*, whole), **p. 92** (the Armor table's "Shield (Utilize
Action to Don or Doff)"), **p. 177** (*Attack [Action]*, whole), **p. 191** (*Utilize
[Action]*, whole).

**The sweep behind clause 6.** Every page searched for `free interaction`,
`interact\w* with (?:an? )?object`, and `Utilize`. The object-interaction *budget* is stated
exactly twice — p. 12 and p. 13, saying the same thing — and p. 191's entry is the only text
that puts p. 177's sword-drawing and the object-interaction framing in one sentence. It is an
example of interacting "while doing something else"; it does not say the interaction is spent.
Every other `Utilize` hit is a tool entry (pp. 93-94), a class feature (pp. 64, 85), or the
Shield's don/doff note (p. 92) — none bears on the composition.

**Where the method went wrong, and it is the reason this record exists.** #283 was filed
asserting "the two coexist", and that sentence was written from the same reading of p. 177's
cardinality that Option 1 rests on. It was not checked against p. 191, and it was reported to
the user as an issue with no design question in it. The check that caught it was reading the
four passages together rather than the one the build needed.

In the tree:

- `_attackable` enumerates one offer per (held weapon, reachable target) since #258.
- `_castable` enumerates one offer per payable slot level, which is the precedent clause 3
  follows.
- `DetachedObject`, `reachable_objects` and `unplaced_objects` exist as of #279;
  `EffectKind.OBJECT_DETACHED` and `with_object_detached` as of #280.
- `utilize` and `multiattack` are both `implemented: false` in `effect_shapes.json`, which is
  the machine-readable form of clause 6's reachability argument.

## Status of implementation

**Clauses 1 to 5 are built** by [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283). Clause 6 is decided, disclosed, and its
revisit condition is held by the two shapes that would trigger it.

**Two things the build found that this record did not.**

**The key encoding was not a settled question, and the record treated it as one.** Clause 3
says "one `LegalAction` per (attack, item)" and says nothing about how a key carries two item
ids. It cannot, as the keys were written: `attack_declared` parses from the right because a
weapon id may contain colons while a combatant id is one segment, which works for exactly
**one** multi-segment field. Swap keys percent-escape each segment instead — chosen over
forbidding a character in `Item.id`, which would be this engine's encoding leaking into a
ruleset's vocabulary.

**Clause 2's enumeration could not produce clause 2's own case.** The clause says the pair
`(attack weapon, equipped item)` carries the before/after distinction and is equal when the
weapon was equipped and used. The first implementation enumerated swaps against weapons the
creature was *already holding*, so the equal pair never occurred — the encoding was right and
nothing could reach it. p. 177's "you **don't need to** use it for that attack" is the sentence
that makes using it permitted, and `_draw_and_use` is the enumeration it requires.

| Clause | State |
|---|---|
| 1 — the equip is part of the attack, not an action beside it | **Built.** The swap rides in `Proposal.always` beside the action charge, so it applies whether or not the attack lands — p. 177 licenses it by *making* an attack ([#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283)) |
| 2 — "before or after" is enumerated by which weapon the attack names | **Built, and the clause gained a finding.** Equips resolve before the attack and unequips after, derived rather than declared. The equal pair needed its own enumeration (`_draw_and_use`) that the first implementation omitted ([#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283)) |
| 3 — offered, not checked afterwards | **Built** as `attack-equip` / `attack-stow` / `attack-drop` keys — three prefixes for p. 177's three destinations, because collapsing sheathing and dropping gave two offers one key ([#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283)) |
| 4 — unequipping to the ground is #280's detachment, and equipping from it the reverse | **Built.** `CARRIAGE_CHANGED` for sheathing and drawing, `OBJECT_DETACHED` for dropping, `OBJECT_PICKED_UP` for the reverse ([#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283)) |
| 5 — an unplaced object is not offered, and the refusal is legible | **Built.** Absent from the menu, named in `unplaced_objects` ([#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283)) |
| 6 — p. 13's free interaction is unmodelled and its relationship unstated | **Decided and disclosed** as `free-object-interaction-unmodelled` in `Situation.unenforced_clauses`. Nothing to build here, and the revisit condition is held rather than promised: [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) (`utilize`) and [#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289) (`multiattack`) each carry it, and each says the question must be answered rather than inherited. |

_Written 2026-08-29 against SRD v5.2.1._
