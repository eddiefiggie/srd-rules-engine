# 0051 — A size is stated, or it is unknown

- **Status:** Accepted, 2026-08-30
- **Settles:** [#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)
- **Requirements:** R15, R30, R31, R32
- **Related:** [0039 — equipment is what a creature holds, wears and carries](0039-equipment-is-what-a-creature-holds-wears-and-carries.md),
  clause 6, which kept size out of the equipment model and pointed here;
  [0046 — a default and the rule that says otherwise are two shapes](0046-a-default-and-the-rule-that-says-otherwise-are-two-shapes.md),
  whose folded-glossary-entry problem this one turned out not to have;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  clause 1

## Context

> p. 188, *Size*: A creature or an object belongs to a size category: Tiny, Small, Medium,
> Large, Huge, or Gargantuan.

Nothing in this engine had one. p. 178's Carrying Capacity is a table keyed on it, so the
shape could not be computed at all; `core.equipment.carried_weight` answered what a creature
was carrying and nothing answered whether it was too much. Four further rules ask how many
categories apart two creatures are, and none of them could be asked.

### The default is the whole question

[#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259) proposed "a `Size` on
`Combatant`, defaulting to Medium." That is the reading this record rejects, and the
argument against it is already written down in this repository, one field away.

`Combatant.hands` is `int | None` and defaults to `None` because no SRD rule states how many
hands a creature has — two being "plausible, universal in most people's memory of the game,
and stated nowhere in the SRD" (0039). Size is the same shape one step further on. p. 188 is
emphatic that every creature *belongs to* a category, so unlike hands the fact certainly
exists; what does not exist is a rule saying which one it is by default. p. 14 says where the
answer comes from instead:

> A character's size is determined by **species**, and a monster's size is specified in the
> monster's **stat block**.

Both are content this repository does not ship (R31). A default of Medium would therefore not
be a conservative fallback. It would be the engine answering a question only a ruleset can
answer, in the voice of a rule.

**And it is wrong in the direction that does damage.** Read at Medium, p. 178 gives an Ancient
Red Dragon (Strength 30) a carrying capacity of 450 lb against its true 3,600 — an eightfold
error, arriving as a plain number inside a finished ruling with nothing marking it as invented.
p. 190 would let a Halfling grapple a Kraken. A visible gap beats a confident wrong number,
because a wrong number is indistinguishable from a right one and a refusal is not.

## Options considered

**Option 1 — `Size` defaulting to Medium**, as #259 proposed. Rejected, above. It buys a
capacity for every creature and pays for it by making "the ruleset said Medium" and "nobody
said" indistinguishable at every call site.

**Option 2 — `Size | None`, defaulting to `None`.** Chosen. Every rule keyed on size answers
`None` for a creature nobody sized, and #259 closes by the engine being able to say *I was not
told* rather than by it guessing.

**Option 3 — require a size at construction.** Rejected, and it is the strongest alternative:
it makes the unsized creature unrepresentable rather than merely unanswerable. It fails on
migration — every existing fixture, the bestiary, and every caller would have to state a size
today, and the only value available to state in bulk is the invented Medium of Option 1. The
refusal would be laundered into data.

**Option 4 — derive the capacity multiplier directly and skip the category.** Rejected. Four
other rules ask about the category and not about the table, so the category is the fact and
the table is one consumer of it.

## Decision

1. **`Size` is p. 188's six categories, ordered by p. 14**, with `rank` and
   `categories_above`. The order is a primitive rather than a convenience: five separate rules
   ask how many categories apart two creatures are — p. 14's two-sizes passage, p. 15's mount,
   p. 86's Naturally Stealthy, p. 190's Grapple and Shove, and p. 86's Powerful Build. One
   signed comparison answers all five, so the next to be built finds it stated.

2. **`Combatant.size` is `Size | None` and defaults to `None`**, meaning no ruleset stated one
   — never that the creature has no size. Every rule keyed on it refuses rather than assumes.

3. **p. 178's table is a table, not arithmetic on a step count.** The document prints
   **Small/Medium as one row**. Counting as one size larger therefore takes a Small creature to
   Medium and finds the identical multipliers, so p. 86's Powerful Build does nothing at all
   for a Small character's capacity. `carry * 2 ** steps` is right for four of the five steps
   and silently doubles the one that matters. Both columns are transcribed for the same reason:
   Drag/Lift/Push happens to be twice Carry in all six rows, and the document states a table
   rather than that relation.

4. **Counting as one size larger is scoped to carrying capacity, and Gargantuan stays
   Gargantuan.** p. 86 and p. 357 are two printings of one rule (0035), so one flag —
   `carries_as_one_size_larger` — and it produces a *carrying size* rather than changing
   `size`, because a trait that changed the creature's size would silently reach p. 190's
   Grapple where no rule grants it. p. 188 names six categories and there is nothing above the
   last, so the trait finds no larger row to move to (0030 clause 1's direction).

5. **The bound is computed and p. 178's Speed cap is not applied**, disclosed as
   `carrying-capacity-speed-cap-is-not-applied` at the read surface whenever the weight is over
   the bound. Two reasons, each sufficient. The sentence fires on *dragging, lifting, or
   pushing* — not on carrying too much — and nothing here distinguishes weight borne from
   weight shifted. And p. 12 leaves the subsystem to a person: "the GM **might** require you to
   abide by the rules for carrying capacity." An engine that always applied the cap would
   enforce a rule the document conditions on somebody deciding to enforce it.

6. **The verdict is read against the Carry column.** p. 178's sentence names "the maximum
   weight you can **carry**", so a load between the two columns is already in excess. Reading
   the larger column would put a Strength 15 Medium creature at 300 lb — over its 225 lb bound
   — under the limit instead of over it.

7. **The capacity carries its derivation** (R30). The result alone cannot show the step that
   matters: a Medium creature's numbers being a Large row's is invisible in the number 450.

## Why

### p. 188's entry folds three mechanics, and this time the neighbours already owned two

0046's defect was a glossary entry claiming a mechanic that was not built, because one
inventory flag covered two rules. p. 188 looked like a repeat — it states that a creature
belongs to a category, that its size "determines how much space the creature occupies in
combat", and that "an object's size affects its Hit Points".

It is not a repeat, because the other two halves are already separate entries. The space a
creature occupies is `occupied-space` (p. 185) and `unoccupied-space` (p. 191), both unbuilt
and now [#337](https://github.com/eddiefiggie/srd-rules-engine/issues/337). An object's Hit
Points are `breaking-objects` (p. 177), unbuilt. So `size` reduces to exactly what is built,
and marking it implemented claims exactly that. The check was worth making: had the split not
already existed, this record would have made one.

### The Strength score, not the modifier

p. 178 says "Your size and Strength **score** determine the maximum weight in pounds that you
can carry." A Strength of 15 is a +2 modifier, so the two readings differ by a factor of seven
and *both produce a believable load* — 225 lb and 30 lb are each a plausible thing for a person
to be carrying. It is the arithmetic an implementation working from memory gets wrong, and
nothing about the result would show it.

### What a refusal costs, and what it buys

The cost is real: today every combatant in the fixtures and the bestiary is unsized, so
`carrying_capacity` answers `None` for all of them, and the feature does nothing until a
ruleset states a size. That is the honest state of a repository that ships no species and no
stat blocks. What it buys is that the moment a ruleset does state one, the number is the
document's and not the engine's — and until then, an agent is told the question cannot be
answered rather than handed an answer that looks the same as a real one.

## Consequences

- **`carrying-capacity` and `size` become implemented** in the effect-shape inventory,
  112 of 210. The claim is checked in both directions by
  `tests/test_effect_shape_inventory.py` against `ENGINE_SHAPES`.
- **A new pinned disclosure.** `CARRYING_CAPACITY_SPEED_CAP` joins `OTHER_DISCLOSURES` in
  `tests/test_disclosures_are_pinned.py`. Adding one is as much a change as removing one, which
  is the direction that pin exists to make deliberate.
- **`test_nothing_here_says_whether_it_is_too_much` is retired**, and rebuilt in the same
  change as an assertion that the refusal survives for an unsized creature. A removed
  absence-assertion that nothing replaces is how a gap closes with no test over the rule that
  closed it.
- **Two prose guards were repointed, not deleted.** `core.equipment` and `core.combat` each
  asserted they still named #259. #259 is closed, so the pointers move to the halves still
  missing — [#336](https://github.com/eddiefiggie/srd-rules-engine/issues/336) and
  [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335). A guard left naming a
  closed issue is the decay it exists to catch.
- **Nine clauses added to `scripts/verify_d20_rules.py`**, including p. 178's table as one
  pattern covering both columns and all six rows. A revision that changed a multiplier or
  un-grouped Small/Medium goes red there.
- **[#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324)'s first blocker is
  gone.** The Push mastery's "if it is Large or smaller" is now expressible. It remains blocked
  on forced movement and on nothing else from this record.
- **A guard defect was found and filed, not fixed here.**
  [#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334):
  `test_the_other_disclosures_are_exactly_these` compares a literal set against a constant
  built from the same names, so it is blind to a disclosure that exists in the source and was
  never pinned — which has already happened once, to `VERBAL_UNCHECKED`. This record's own
  disclosure was added to the pin by hand, which is the current design and the reason the
  defect matters.

## Evidence

Every clause below is matched against the printed page by `scripts/verify_d20_rules.py`, which
reports 244 clauses verified against SRD_CC_v5.2.1.pdf.

- p. 188 — the six categories, and that a creature *belongs to* one.
- p. 14 — that size comes from a species or a stat block, and the smallest-to-largest order.
- p. 178 — the Strength score; the full table, both columns, six rows, Small/Medium grouped;
  and the Speed sentence.
- p. 12 — that the GM *might* require the capacity rules at all.
- p. 86 and p. 357 — counting as one size larger, scoped to carrying capacity, said twice.

## Status of implementation

**Every clause is built** by [#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259).

| Clause | State |
|---|---|
| 1 — six ordered categories, `categories_above` | **Built.** `core.size.Size` ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) |
| 2 — `Size \| None`, defaulting to `None` | **Built.** `Combatant.size`, with the refusal asserted for capacity and verdict alike ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) |
| 3 — a table, not a doubling; both columns transcribed | **Built.** `CARRY_MULTIPLIER` and `DRAG_LIFT_PUSH_MULTIPLIER`, with Small asserted to gain nothing ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) |
| 4 — the trait is scoped, Gargantuan stays put | **Built.** `one_size_larger_for_carrying` and `Combatant.carrying_size` ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) |
| 5 — the Speed cap is disclosed, not applied | **Built as a disclosure.** `CARRYING_CAPACITY_SPEED_CAP`, appended only when the weight is over the bound. The cap itself is unbuilt and tracked by [#336](https://github.com/eddiefiggie/srd-rules-engine/issues/336) |
| 6 — the verdict reads the Carry column | **Built.** `Combatant.over_carrying_capacity`, asserted with a load between the two columns ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) |
| 7 — the capacity carries its derivation | **Built.** `CarryingCapacity.derivation`, which travels on the transport ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) |

The **space** half of p. 188 is deliberately not in this record and is
[#337](https://github.com/eddiefiggie/srd-rules-engine/issues/337); Grapple and Shove, whose
blocker this removes, are [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335).
