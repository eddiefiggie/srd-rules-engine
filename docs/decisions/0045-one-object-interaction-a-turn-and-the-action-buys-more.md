# 0045 — One object interaction a turn, and the Action buys more

- **Status:** Accepted, 2026-08-29
- **Settles:** the design half of [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288),
  which stays open as the build, and closes the remaining half of
  [0042](0042-equipping-rides-on-the-attack-that-permits-it.md) clause 6
- **Requirements:** R1, R15, R18, R31, R32
- **Related:** [0043 — one action, several attacks, and one swap](0043-one-action-several-attacks-and-one-swap.md),
  clause 3, whose intersection this applies a second time;
  [0042](0042-equipping-rides-on-the-attack-that-permits-it.md), clauses 1 and 6;
  [0041](0041-an-item-that-leaves-a-creature-is-an-object-somewhere-unstated.md), clause 4

## Context

0042 clause 6 recorded a silence and named two shapes that would make it reachable.
`multiattack` was the first, and 0043 clause 3 answered half of it by capping p. 177's swap at
one per turn. `utilize` is the second, and it arrives with 0042's own accepted cost attached:

> **A creature cannot swap a weapon except by attacking.** Faithful to p. 177, and it means
> the engine offers no way to sheathe a sword on a quiet turn — that is p. 13's free
> interaction, which clause 6 does not model.

The document supplies the missing route in three places that agree:

> p. 13, *Your Turn*: You can interact with **one object or feature of the environment for
> free**, during either your move or action… **If you want to interact with a second object,
> you need to take the Utilize action.**

> p. 12: interactions with objects are limited: **one free interaction per turn**… Any
> additional interactions require the Utilize action.

> p. 191, *Utilize [Action]*: You **normally interact with an object while doing something
> else, such as when you draw a sword as part of the Attack action**. When an object requires
> an action for its use, you take the Utilize action.

And the question 0043 clause 5 handed forward: **does the one swap this engine permits also
spend the free interaction?**

## Options considered

**Option 1 — two allowances: a creature may swap during its attack *and* interact freely.**
Rejected. It is p. 177 read in isolation, and 0043 clause 3 already declined the same reading
for the same pair of rules.

**Option 2 — one allowance, and p. 177's swap is it.** Chosen.

**Option 3 — model the free interaction and leave the composition disclosed, as 0042 did.**
Rejected *here*, and it was right there. 0042 could disclose because nothing else could spend
an object interaction, so the two readings were indistinguishable in play. Building this route
makes them distinguishable, and a disclosure that a reader can now catch the engine
contradicting is worse than a decision.

## Decision

**1. The engine permits one object interaction per turn, and p. 177's swap is one.** A
creature that swapped a weapon during its attack has spent it; one that has not may equip,
unequip, pick up or drop without attacking.

**This is 0043 clause 3's intersection applied a second time**, and the arithmetic is the same.
Two interactions are legal under the independent reading and not under the shared one; one is
legal under both. The engine offers what both permit.

**It closes 0042 clause 6 rather than narrowing it further.** The clause asked how p. 13 and
p. 177 compose; the answer is that the engine composes them into a single allowance and says
so, because the alternative is now observable.

**2. The four moves are the same four.** Equip, unequip, pick up and drop are what p. 177's
swap already performs, and p. 13's "interact with one object" reaches nothing else this engine
models. So the free interaction offers the moves that exist rather than a new vocabulary, and
`_swaps` and `_draw_and_use` gain a caller that is not an attack.

**3. The Utilize action buys another.** p. 13: "If you want to interact with a second object,
you need to take the Utilize action." So Utilize spends the Action to do one more of the same
four. That is the whole of what the action does here, and it is a real effect rather than a
placeholder — it is the only way to sheathe one weapon and draw another in one turn.

**4. A creature with no Action left gets no Utilize, and that is the economy rather than a
special case.** p. 176 gives one action per turn; spending it on an attack leaves none to
Utilize with, which is why p. 177's swap exists at all.

**5. What Utilize does *not* reach is disclosed rather than implied.** p. 10 summarises it as
"Use a nonmagical object", and the objects a rule could ask about — doors, levers, the tools on
pp. 93-94, p. 92's Shield with its own "Utilize Action to Don or Doff" — are content this
repository does not ship (R31), or need subsystems it does not have. The action is offered for
the interactions the engine models and for nothing else, and the read surface names the limit.

**And p. 14 puts a second thing beyond it, which is a rule rather than content:**

> The **GM might require** you to use an action for any of these activities when it needs
> special care or when it presents an unusual obstacle. For instance, the GM might require you
> to take the Utilize action to open a stuck door or turn a crank to lower a drawbridge.

So an interaction that is free by default may be escalated to an action **by a person's
judgement**. The engine cannot make that judgement and does not model the objects it would be
made about; what it must not do is conclude from its own silence that no interaction is ever
escalated. Named here for the reason p. 183's improvised damage type is named in 0040
clause 5 — a decision the document assigns to a person is not a gap in the rules.

**Also beyond it: p. 177's *Breaking Objects*** — "the GM may allow a creature to break it
automatically with the Attack or **Utilize** action" — which is its own unimplemented shape and
another GM judgement, and **p. 139's *Haste***, where a spell grants an action usable for
Utilize among others. Neither changes what the action does; both are consumers that would
arrive with their own mechanics.

**6. An unplaced object is still not reachable.** 0041 clause 4's cost does not soften because
a new route arrived: an object no rule placed is absent from this menu exactly as it is from
the attack's.

## Why

**Clause 1 is the clause this record exists for, and the interesting part is that 0042 was
right to disclose and this record is right not to.** The same silence, the same two readings,
and the correct handling changed — because building the second route turned a question nobody
could observe into one a player can. A disclosure is honest while the engine cannot be caught;
once it can, the disclosure becomes a way of not deciding.

**That is a distinction worth stating, because the instinct is to treat "the document does not
say" as a permanent property of a rule.** It is a property of the *pair* — rule, and what the
engine can do. R32 asks for exclusions to be disclosed; it does not ask for a decision to be
deferred once deferring it is what produces the inconsistency.

**Clause 3 is what keeps Utilize from being a placeholder.** An action the engine offers and
cannot resolve is the "built with no occasion" shape this repository has found repeatedly, and
`magic` and `unarmed-strike` sat unclaimed for that reason. Utilize escapes it because a
second object interaction is a thing the engine can now do and could not before.

## Consequences

**Accepted costs.**

- **A creature that swapped during its attack cannot also open a door**, which may be narrower
  than the rules allow. The same accepted cost 0043 clause 3 took, and taken for the same
  reason.
- **Utilize reaches four moves and no others.** A door is not an object this engine has, and
  the action offered for one it cannot resolve would be worse than the gap.
- **0042's accepted cost is lifted, and its record still states it.** The Status section says
  so; the Decision does not move (`docs/decisions/README.md`).

**Follow-on effects.**

- **`utilize` resolves** when the build lands, and `action` shapes go from 4 of 20 to 5.
- **0042 clause 6 and 0043 clause 3's disclosures come off together**, replaced by an
  enforced rule — and the pair must move as one, which is
  [#292](https://github.com/eddiefiggie/srd-rules-engine/issues/292)'s point exactly.
- **p. 92's Shield don/doff becomes expressible** the day armour is modelled, and is named in
  clause 5 rather than filed, because nothing about it is unfinished work today.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 10** (the Actions table's *Utilize*
row), **p. 12** (*Time-Limited Object Interactions*), **p. 13** (*Your Turn*, *Interacting with
Things*), **p. 92** (the Armor table's Shield row), **pp. 93-94** (the tool entries, for what
clause 5 excludes), **p. 177** (*Attack [Action]*), **p. 191** (*Utilize [Action]*).

**The sweep behind clause 5, and it was wrong twice before it was right.** `Utilize` appears on
**29 pages**: 10, 12, 13, 14, 64, 85, 92, 93, 94, 96-100, 139, 176, 177, 191, 210, 212, 213,
218-220, 224, 227, 228, 244, 250. A first pass listed only the handful the decision was written
from and called the rest content, which is true of most of them and not of all.

Three are mechanics rather than content, and clause 5 states each:

- **p. 14** — the GM may escalate an otherwise-free interaction to an action.
- **p. 177**, *Breaking Objects* — the GM may allow an object to be broken with the Attack or
  Utilize action; its own unimplemented shape.
- **p. 139**, *Haste* — a granted action usable for Utilize among others.

The remainder are content: p. 176's glossary index of the eleven actions, the tool rows
(pp. 93-94), adventuring gear (pp. 96-100), class features (pp. 64, 85), the Shield's don/doff
note (p. 92), and magic items (pp. 210-250).

**This is the second record in a row whose sweep understated its own result**, after 0044
reported that the document never says when combat ends. Both were caught by writing the
Evidence section rather than by review, which is the section doing more work than it appears
to: naming the search terms is what forces the search to be re-run.

In the tree:

- `_swaps` and `_draw_and_use` are called only from `_attackable`, per (weapon, target) —
  which is 0042 clause 1 and the reason no standalone route exists.
- `EncounterState.swaps_this_turn` records p. 177's allowance as of #289.
- `Situation.unenforced_clauses` carries `free-object-interaction-unmodelled` and
  `one-swap-per-turn-is-the-engines-cap`, both of which this replaces.
- `utilize` is `implemented: false` in `effect_shapes.json`.

## Status of implementation

**Nothing here is built.** This record decides;
[#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) builds clauses 1 to 6 and
**remains open**.

| Clause | State |
|---|---|
| 1 — one object interaction a turn, and p. 177's swap is one | **Decided, not built.** [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288), the clause this record exists for |
| 2 — the four moves are the same four | **Decided, not built.** [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) |
| 3 — Utilize spends the Action for another | **Decided, not built.** [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) |
| 4 — no Action, no Utilize | **Decided, not built.** [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) |
| 5 — what Utilize does not reach is disclosed | **Decided, not built.** [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) |
| 6 — an unplaced object stays unreachable | **Decided, not built.** [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288); 0041 clause 4 already holds the reasoning |

_Written 2026-08-29 against SRD v5.2.1._
