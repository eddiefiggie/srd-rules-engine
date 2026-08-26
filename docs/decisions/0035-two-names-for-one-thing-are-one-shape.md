# 0035 — Two names for one thing are one shape

- **Status:** Accepted, 2026-08-26
- **Settles:** [#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230)
- **Requirements:** R17, R31, R32
- **Related:** [0013 — the effect-shape vocabulary normalises on mechanism](0013-effect-shape-normalisation.md),
  which owns the shape/vocabulary boundary and the `criteria` block this record extends;
  [0033 — a glossary entry is an index, not a shape's boundary](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md),
  whose clause 5 filed the question and whose guard set this change edits;
  [0034 — a term the document defines and never uses](0034-a-term-the-document-defines-and-never-uses.md),
  the sibling classification record whose test does **not** decide this one

## Context

[#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230) asks one question:

> Does a term whose entire entry is "X is another name for Y" belong in `vocabulary`?

The instance is **Save** (p. 187), whose entry is the whole of:

> Save is another name for a saving throw. See also "Saving Throw."

Under [0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) clause 1 it is
claimed **correctly** — the document states the saving throw's mechanic elsewhere and the
engine produces it. But `vocabulary` means *defined here, not an effect shape*
([0013](0013-effect-shape-normalisation.md)), and a pure synonym is arguably the clearest
case of that.

**The two questions are different, which is why there is no contradiction between this
record and 0033.** 0033 asked *can a definitional entry ever be claimed?* and answered yes.
This asks *should this entry exist at all?* — a classification question 0013 owns and which
0033 clause 5 explicitly declined to open, because moving an entry between shape and
vocabulary changes a published figure.

**[0034](0034-a-term-the-document-defines-and-never-uses.md) does not decide it either, and
the precision matters.** 0034's operative test is *zero consumers*: `weapon-attack` moved
because the document defines the term and never uses it. That test does not reach `save`,
which the document uses **1544** times against `saving throw`'s **636**. A rule phrased
around usage would keep `save` a shape. This record states a different test, and the two are
independent.

## Options considered

**Option 1 — keep `save` a claimed shape.** Rejected, and the reason is not a reading of the
glossary. The tree already resolves both ids to one symbol:

```
save                 -> core.d20.TestKind.SAVE
saving-throw         -> core.d20.TestKind.SAVE
```

`core.inventory`, adjacent lines. Two inventory entries claiming the same enum member, in a
figure whose whole purpose is to be falsifiable, and it has been so for as long as both were
claimed. Keeping the entry means keeping one mechanic counted twice — in the **numerator and
the denominator both** — with nothing to point at as the second thing.

**Option 2 — fold `save` into `saving-throw` as an alias field on the shape.** Rejected. It
would add schema for one entry, and it would move `save` *out of the artifact's visible
accounting*: `vocabulary` exists precisely so that an entry considered and set aside stays
visible with its reason, because silent omission is the exact failure R17 names. An alias
field is a quieter place to put something than the category the project already uses for
this, and `heroic-inspiration` and `weapon-attack` are both filed the established way.

**Option 3 — apply 0034's consumers test and keep it.** Rejected as the wrong instrument
rather than the wrong answer. `save` has 1544 uses; on that test it is emphatically a
shape. But heavy use of a synonym is use of the thing it names, and a test that counts uses
cannot see that. The instrument has to be identity.

## Decision

**1. `save` is vocabulary. Two names for one thing are one shape.** p. 187 states the
identity in both directions, and the parent entry declares the alias itself:

> **Save.** Save is another name for a saving throw.

> **Saving Throw.** A saving throw—also called a save—represents an attempt to avoid or
> resist a threat.

This is not an inference from two entries that happen to resemble each other. The document
says outright, in each entry, that the two words name one thing. There is no parameter, no
restriction and no sub-case — unlike `weapon-attack`, which at least named a proper subset by
fixing what the attack was made with.

**2. The test is identity, not usage.** A term whose entry states it **denotes the same
thing** as an inventoried term is one shape with that term, however often the document uses
it. This is the fourth entry in the artifact's `criteria` block as of this change, because
the rule is not derivable from the three already there: the nearest,
`mechanism-not-exemplar`, reads *"Two features whose rules differ only in a parameter are one
shape"*, and `save` and `saving-throw` do not differ even in a parameter. The criterion
covers this case *a fortiori* without stating it, and 0034 deliberately did not extend the
block because `weapon-attack` genuinely was a parameter case. A pure synonym is not.

**3. The discriminator against a specialised namesake is the resolver symbol.**
`death-saving-throw` (p. 181) is a saving throw by name and remains its own shape, correctly:
it resolves to `core.death.death_save_resolver`, its own mechanism with three successes,
three failures and a fixed DC. **Two ids sharing one symbol is the machine-checkable form of
"one mechanism"; similar names are evidence of nothing.** Without this clause the rule
over-fires on the nearest neighbour it has.

**4. Both figures fall: 96 of 210 → 95 of 209.** The d20 test goes 12 of 13 → 11 of 12, and
`vocabulary` gains its twenty-second entry. `ENGINE_SHAPES` loses its `"save"` key — the real
difference from 0034, which touched no claim at all. **Nothing is lost**: `TestKind.SAVE`
stays claimed under `saving-throw`, no resolver changes, and the suite is what confirms it
rather than inspection.

**5. A numerator that falls this way is the figure becoming more true, and the README must
say so.** 0034 clause 5 had to explain a denominator falling on its own; this is the harder
direction, because a coverage number going *down* reads as a regression to anyone who does
not know why. It is not one: no capability changed, a duplicate stopped being double-counted.
An unexplained movement in either direction reads as a figure being managed, so the milestone
row states it where a reader meets it.

**6. The evidence is a presence, so ordinary clauses assert it.** 0034 clause 3 required a
document-wide **count** because its evidence was an absence, and nothing goes red when an
unused term starts being used. This decision rests on two stated sentences instead, so two
ordinary `CLAUSES` rows are the right instrument. The standing obligation is to assert
whatever the decision actually rests on — not to reach for the newest machinery because it
exists.

**7. [0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md)'s guard set loses a
member, and 0033 is not weakened.** `tests/test_effect_shape_inventory.py`'s
`CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY` — added by #231 to pin 0033 clause 1 — carried `save`
among five entries. Once `save` is not a shape, its assertion cannot hold, so the set drops
to four: `bright-light`, `damage`, `damage-types`, `healing`. Those four make 0033's point
intact — each is as definitional in the glossary as Bright Light and each is claimed on text
elsewhere. **Recorded rather than silently deleted**, because a guard member vanishing
without explanation is how a guard comes to inspect less than it appears to, which is the
failure 0033 itself was written about.

**8. No sweep for further synonyms was run, and that scope is stated rather than assumed.**
This record settles the entry #230 names. The glossary may contain other pure synonyms; if
it does, they are not inventoried by this change and no claim is made either way (R32). The
rule is stated generally so that the next one is decided rather than re-argued.

## Why

**The decisive evidence is in the tree, not in the document.** Both entries were already
quoted in #230, and read alone they leave a real question — the glossary does print two
headings, and the project's job is to mirror the document's mechanics faithfully. What
settles it is that `ENGINE_SHAPES` resolves both ids to `core.d20.TestKind.SAVE` on adjacent
lines. No reading of p. 187 turns two ids pointing at one enum member into two shapes. That
is a fact about the inventory rather than an interpretation of the SRD, and it is why this
question was easier to answer than #229's despite being filed alongside it.

**Clause 3 is the clause this record would have got wrong.** The natural statement of the
rule — *a term that renames an inventoried term is vocabulary* — over-fires immediately on
`death-saving-throw`, which is named for a saving throw and is a real, separate mechanism.
Any rule here has to distinguish "a second name for the same thing" from "a specialised thing
named similarly", and the only reliable discriminator is the symbol each id resolves to.
Names are exactly what is unreliable in a question about names.

**Clause 6 is a restraint rather than a rule.** 0034 built document-wide count assertions and
they were the right instrument there. The temptation on the next classification record is to
use them again, because they are newer and look more rigorous. They would be wrong here:
this decision rests on sentences the document prints, and a count would assert something the
argument does not depend on. Machinery earns its place per claim.

**Clause 5 is where this differs most from its siblings.** 0033 raised a figure, 0034 lowered
a denominator, and this lowers the number a reader meets first. That is the one most likely
to be "fixed" later by someone restoring the key and gaining a point of coverage for no work.
The guard is what stops it — putting `save` back into `shapes` must go red — and the record
is what explains why anyone would want to.

## Consequences

**Accepted costs.**

- **The headline coverage figure falls, with no capability change to explain it.** Clause 5
  is the mitigation and it is prose rather than machinery: the README states what happened
  where the figure appears. A reader who checks will find the engine resolves exactly what it
  resolved before.
- **An `ENGINE_SHAPES` key is removed**, which is the first time a classification record has
  dropped a claim. The claim survives under `saving-throw`, but the safety net is the full
  suite rather than a targeted assertion, because no resolver referenced the id.
- **0033's guard set shrinks**, and a smaller guard inspects less by definition. Clause 7
  records why the remaining four still carry 0033's finding.
- **The `criteria` block grows to four**, which is a change to the shipped artifact's schema
  content and therefore to what consumers read. That is the block's purpose (0013, Q2) and
  the cost is only that the rules are now four rather than three to hold in mind.

**Follow-on effects.**

- Coverage is **95 of 209**; the d20 test **11 of 12**; `vocabulary` twenty-two entries. The
  remainder is unchanged at **114**, since `save` was implemented and both sides fall by one.
- **[0034](0034-a-term-the-document-defines-and-never-uses.md)'s arithmetic is unaffected**
  but its neighbour's is: the 155 Rules-Glossary headings now split **133 shapes / 22
  vocabulary**, where 0033 clause 6 recorded 135/20 and 0034 recorded 134/21. None of the
  three is wrong; each states the split at the time it was written.
- `death-saving-throw` and `saving-throw` are untouched and asserted to stay shapes.
- No further synonym is filed as an issue, because none was looked for — clause 8 states
  that limit. Finding one later is new work, not a re-raise of this.

## Evidence

Read in the official SRD v5.2.1 PDF for this record, printed **p. 187**, both entries
adjacent on the page:

- *Save*: "Save is another name for a saving throw. See also 'Saving Throw.'"
- *Saving Throw*: "A saving throw—also called a save—represents an attempt to avoid or resist
  a threat. You normally make a saving throw only when a rule requires you to do so, but you
  can decide to fail the save without rolling. […] See also 'Playing the Game' ('D20
  Tests')."

Both sentences are asserted in `scripts/verify_d20_rules.py` as of this change. The second
matters as much as the first: it is the **parent** declaring the alias, which is what makes
the identity a statement of the document rather than a comparison of two entries.

Document-wide term counts over the verifier's normalised text: `save` **1544**, `saving
throw` **636**. These are the figures showing 0034's consumers test does not reach this case
— on that test `save` is emphatically a shape.

Engine side, in the tree, and this is the finding the decision rests on:

```
ENGINE_SHAPES["save"]         == "core.d20.TestKind.SAVE"
ENGINE_SHAPES["saving-throw"] == "core.d20.TestKind.SAVE"
```

Equal, on adjacent lines of `core.inventory`. The counter-case is one line away:
`ENGINE_SHAPES["death-saving-throw"]` is `core.death.death_save_resolver`, a different symbol
for a different mechanism — which is clause 3's discriminator, present in the tree before
this record needed it.

A sweep for the shape id outside the data file finds exactly one reference, the
`ENGINE_SHAPES` line being removed. No resolver, test or adapter names it.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `save` is vocabulary | **Built.** `KINDS` and `effect_shapes.json` agree; the entry carries a `VOCABULARY_REASONS` reason naming `saving-throw`. Coverage reports 95 of 209 |
| 2 — the test is identity, not usage | **Built** as data: the fourth entry in the artifact's `criteria` block, `decided_by` this record. Enforced by review beyond the one instance |
| 3 — the discriminator is the resolver symbol | Not a mechanism. Pinned by `tests/test_effect_shape_inventory.py`, which asserts `death-saving-throw` resolves to a symbol *different* from `saving-throw`'s — the corruption that points it at `TestKind.SAVE` goes red |
| 4 — both figures fall, and `ENGINE_SHAPES` loses a key | **Built.** README publishes 95 of 209 and the d20 test 11 of 12, both derived from the inventory by `tests/test_readme_reports_real_coverage.py`. Full suite green with the key removed |
| 5 — the README says why a numerator fell | **Built** in the milestone row, which no guard checks — the accuracy half is on the author (0033's standing note) |
| 6 — the evidence is a presence, so ordinary clauses assert it | **Built.** Two p. 187 clauses in `scripts/verify_d20_rules.py`. No document-wide clause was added, deliberately |
| 7 — 0033's guard set drops to four, recorded not deleted | **Built.** `CLAIMED_ON_TEXT_OUTSIDE_THE_ENTRY` loses `save`, and its docstring records where the member went |
| 8 — no sweep for further synonyms was run | **Built** by not sweeping. Stated as scope rather than left as an implied audit (R32) |

**#230 is closed with the rule and the duplicate that proved it** — two ids resolving to one
symbol are one shape, whatever the glossary prints as headings.

_Written 2026-08-26 against SRD v5.2.1._
