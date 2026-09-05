# 0085 — A target is a role in a mechanic, not a mechanic

- **Status:** Accepted, 2026-09-04
- **Settles:** [#453](https://github.com/eddiefiggie/srd-rules-engine/issues/453)
- **Requirements:** R17, R31, R32
- **Related:** [0013 — the effect-shape vocabulary normalises on mechanism](0013-effect-shape-normalisation.md),
  which owns the shape/vocabulary boundary and supplies the criterion this record applies;
  [0034 — a term the document defines and never uses](0034-a-term-the-document-defines-and-never-uses.md)
  and [0035 — two names for one thing are one shape](0035-two-names-for-one-thing-are-one-shape.md),
  the two prior classification records, whose tests do **not** decide this one;
  [0033 — a glossary entry is an index, not a shape's boundary](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md),
  whose clause 1 supplies the strongest reading against this record;
  [0084 — a space is a control area, not a volume](0084-a-space-is-a-control-area-not-a-volume.md),
  which closed the gate this entry was waiting behind and found it was not waiting on anything

## Context

[#453](https://github.com/eddiefiggie/srd-rules-engine/issues/453) asks one question:

> Is p. 190's Target a shape or vocabulary?

The entry is the whole of:

> A target is the creature or object targeted by an attack roll, forced to make a saving
> throw by an effect, or selected to receive the effects of a spell or another phenomenon.

`target` sat in the inventory as a `targeting` shape, unclaimed, and the coverage audit on
[#426](https://github.com/eddiefiggie/srd-rules-engine/issues/426) grouped it under
[#337](https://github.com/eddiefiggie/srd-rules-engine/issues/337) — "a creature occupies no
space" — on the assumption that targeting needs spaces. 0084 closed #337, built the space,
and reported `target` still unclaimed because it "needs more than occupancy". Reading the
entry, it needs nothing: it does not state a mechanic that occupancy or anything else could
supply.

The issue asked for a second look rather than a decision at the end of a long session, for
one stated reason: the entry sits beside `cover`, `area-of-effect` and the two space entries,
which **are** mechanics, and whether it was filed there because it is one or because the word
belongs to the same family was the open question. This record is the second look.

## Options considered

**Option 1 — claim it.** The three routes the entry names are attack rolls, forced saves and
spell effects; the first two are claimed shapes and the engine produces both. Rejected. That
is counting the receiving end of three mechanics as a fourth — the double count 0034 refused
for `weapon-attack`, from the other side. And there is nothing to claim it *against*: the
engine's one symbol named `target` is `D20Test.target`, which is p. 178's Difficulty Class —
the **number** a roll must reach, already claimed under `difficulty-class`. No resolver
produces a consequence of being a target, because the document states none.

**Option 2 — leave it a shape, permanently unclaimed.** Rejected, as 0034 rejected it: a
shape nobody can claim without inventing a mechanic is a ceiling that cannot be reached,
under a README that publishes a denominator implying otherwise.

**Option 3 — read p. 106's *Targets* section as the term's content, and hold or claim
`target` on it.** This is the strongest reading against this record and it is why the second
look was worth taking. [0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md)
clause 1 says a shape's content is what the document states about the term *anywhere*, and
p. 106 has a subsection headed **Targets** with five rules under it. Rejected, on reading the
five — see clause 5. Every one is a rule about **the spell**: how it picks, whether it can
reach, what its area decides, whether the recipient notices, and what happens to the slot when
the recipient cannot be affected. The two that state a consequence are claimed already, under
the shapes that own them. None states a consequence of *being* a target, and the one sentence
that is about being targeted says the target does not know it happened.

**Option 4 — vocabulary.** Taken.

## Decision

**1. `target` is vocabulary. p. 190 defines a role, not a mechanic.** A target is the
creature or object at the receiving end of an attack roll, a forced saving throw or a spell's
effect, and each of those routes is inventoried on its own: `attack-roll`, `saving-throw`,
`area-of-effect` and the spell shapes. The entry names **no mechanical change to state the
engine holds**, which is [0013](0013-effect-shape-normalisation.md)'s `engine-held-state`
criterion — the one that files `creature`, `object`, `spell` and `weapon`. The entry is one
sentence and is followed by the next heading, and that is asserted rather than described (see
**Evidence**): a revision that gave it a second sentence goes red.

**2. The criterion that decides it is 0013's own, and neither prior classification test
reaches it.** [0034](0034-a-term-the-document-defines-and-never-uses.md)'s test is a count
built to discriminate between two renames of a parent — `weapon-attack` at 3 uses against
`spell-attack` at 62. [0035](0035-two-names-for-one-thing-are-one-shape.md)'s test is
identity, for a synonym. `target` is neither: it fixes no parameter of any parent and is
another name for nothing. It is the first entry set aside on the plain criterion that also
needed a record, and it needed one for the reason the issue gave — the reclassification moves
a published figure, and a figure that moves without a record reads as a figure being managed.

**3. Heavy use is not evidence against, and neither is being branched on.** The document
uses `target` **1,214** times; it uses `creature` **1,950** times and `creature` is
vocabulary. Both are branched on: *"is a creature"* occurs **20** times, and the document says
*"If you are the target"* (p. 144, Levitate) and *"If you are targeted by a spell"* (p. 241,
Rod of Absorption). Those are effects stating their own branches, which
[0013](0013-effect-shape-normalisation.md) Q4 files as content; the role is what they branch
on, and the branch belongs to the effect. A rule that read a conditional use as a consumer
would make `creature` a shape by the same sentence.

**4. The absence is asserted, with two controls, and the record says exactly what the
assertion proves.** No count of a term used 1,214 times can state an absence the way
`weapon attack` at 3 did. What can be counted is the **form** the document uses to state a
held state — *"has the X condition"* (313 times), *"is Bloodied"* (10) — and whether the term
ever takes it. It never does: *"is a target"*, *"becomes a target"* and *"counts as a target"*
occur **nowhere**. That is the narrow claim, and it is the form 0013 Q2 asks about: target-ness
is never stated as a state something is in or becomes. It is **not** a claim that no effect
ever branches on the role — clause 3 names two that do. The rows are in
`scripts/verify_d20_rules.py` as of this change, with two controls, for the reason **Why**
gives.

**5. p. 106 is the spell's, and it is now asserted.** Five clauses pin what the *Targets*
section states, so the reading in option 3 is checkable against sentences rather than against
this paraphrase:

| p. 106 | Whose rule it is | Where it lives |
|---|---|---|
| *A Clear Path to the Target* — a caster must have a clear path, so the target can't be behind Total Cover | the spell's reach | `cover`, whose own p. 179 entry states the refusal; `spell_reaches` applies it |
| *Targeting Yourself* — a spell targeting "a creature of your choice" may target the caster | the spell's choice | needs a spell with a target clause ([#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)) |
| *Areas of Effect* — "the area determines what the spell targets" | the spell's area | `area-of-effect` |
| *Awareness of Being Targeted* — a creature doesn't know it was targeted unless the spell is perceptible | narration | no state changes; nothing to hold |
| *Invalid Targets* — nothing happens, and the slot is still expended | the slot | `core.casting` ties expenditure to the casting, not the outcome (p. 104), so this holds by construction; the rest needs a spell ([#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)) |

The first row is the one that mattered before this record existed: `spell_reaches` **quoted**
it in a docstring and nothing asserted it — the shape
[#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371) named, where a
word-perfect quotation stands in for a sentence nobody in the repository has verified.

**6. The `targeting` kind loses a member and keeps its meaning.** Its thirteen remaining
members each constrain or shape *what may be targeted*: `cover`, `area-of-effect` and its five
shapes, `reach`, the two space entries, `swarm-space-sharing` and `trap-trigger`. `target` was
filed among them by family resemblance — the issue's own suspicion, confirmed. The five
glossary members are pinned as shapes in the same test that pins `target` as vocabulary, so a
guard satisfied by moving the whole family cannot pass.

**7. The denominator moves: 210 → 209. The numerator does not, and `ENGINE_SHAPES` is not
touched.** Coverage reads **142 of 209**; `vocabulary` gains its twenty-third entry; the 155
Rules-Glossary headings split **132 shapes / 23 vocabulary**. `target` was `implemented:
false`, so no claim changes. Stated explicitly, as 0034 clause 5 stated it: a denominator
falling on its own is the shape of a managed figure, and a reader is right to check. The
honest reading is that the denominator was wrong by one.

**8. Two p. 106 rules are recorded here and not filed.** *Targeting Yourself* and the
spell-side half of *Invalid Targets* each need a spell with a target clause before there is
anything to build, and that antecedent is
[#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21). They are named here so an
audit does not re-raise them as rules held by nothing; filing them separately would file #21
twice.

## Why

**The second look was worth taking because the counter-reading was real.** Read from the
inventory, `target` looked like a mechanic waiting on #337. Read from p. 190, it is a
definition. Read from p. 106 under 0033 clause 1, it has five rules of content — and that
reading is the one this record had to answer rather than wave past, because 0033 is exactly
the record that says a glossary paragraph is not a shape's boundary. The answer is not that
0033 does not apply; it is that p. 106's subject is the spell. Each rule's consequence is
either already claimed under the shape that owns it or has no antecedent, and none is a
consequence of being a target. That is a finding about five sentences, and it is pinned as
five clauses so it stays one.

**Clause 2 is the clause this record would have got wrong by following its siblings.** The
issue framed the question "by 0034's test" and counted occurrences. 0034's count was the
right instrument for a term the document defined and then used three times; it says nothing
about a term the document uses on every page. Reaching for it here would have produced a
table of large numbers proving nothing either way — which is what 0035 clause 6 warned about
when it declined to use 0034's machinery for `save`. The instrument here is reading the entry,
and the entry is one sentence.

**Clause 4 exists because clause 1 rests partly on an absence, and 0034 clause 3 does not
let an absence go unasserted.** The record could have rested on the presence clause alone —
one sentence, followed by a heading — and 0035 clause 6 would have approved. But "states no
consequence" is a claim about the entry, and "nothing gates on it" is a claim about the
document, and the second is what makes the first safe: a rule elsewhere that said "a target
of an attack roll has Disadvantage until its next turn" would make `target` a shape without
touching p. 190. So the absence is asserted, narrowly, in the one form that can be counted.

**Two controls rather than one, because the row asserts zero.** 0034's `exactly 3` went red
at 0 on its own, which is why its control only had to guard partial extraction. An `exactly 0`
row is the one shape of assertion a sweep that read *nothing* passes — and the issue's own
count did read nothing, once: a regex built as `rf"\\b{term}\\b"` searched for a literal
backslash and returned zero for everything, including `creature`. It was caught by a control
term whose answer was known to be large. So the first control proves the sweep reads the noun
(`target` ≥ 1,000), and the second proves the *phrasing family* is one the sweep finds where
the document uses it (`is Bloodied` ≥ 5, p. 177's held state in exactly the form the zero row
says `target` never takes). Without the second, a zero could mean the form matches nothing
rather than that the term never takes it.

## Consequences

**Accepted costs.**

- **A published denominator falls with no capability change**, for the third time. Clause 7
  is the disclosure: the numerator is unchanged and `ENGINE_SHAPES` is untouched.
- **The verifier gains six presence clauses and three document-wide rows** for an entry that
  moves to vocabulary — more assertion than the entry's own sentence would seem to earn. Five
  of the six are p. 106, and one of those was already load-bearing and unasserted. That is the
  cost of answering option 3 properly rather than by paraphrase.
- **Clause 4's row is narrow by design**, and a reader who expects it to prove "no effect
  branches on being a target" will find it does not. The record says so where the row is
  stated, and clause 3 names the branches that exist.

**Follow-on effects.**

- Coverage is **142 of 209**; the d20 test is unchanged at **11 of 12**; `vocabulary`
  twenty-three entries. The remainder is **67**.
- **0033 clause 6's arithmetic shifts again, and its decision does not.** The 155 headings
  split 135/20 when 0033 was written, 134/21 after 0034, 133/22 after 0035, and **132/23**
  now. None of the four is wrong; each states the split at its date.
- The coverage audit on [#426](https://github.com/eddiefiggie/srd-rules-engine/issues/426)
  grouped four shapes under #337. Two were built by 0084, one is `teleportation`
  ([#444](https://github.com/eddiefiggie/srd-rules-engine/issues/444)), and the fourth was
  this entry, which was never waiting on it. That group is now empty.
- `spell_reaches`'s p. 106 sentence is asserted for the first time. It was quoted in the
  docstring and verified by nobody.
- No sweep for further role-defining entries was run, and that scope is stated rather than
  assumed (R32). The rule is stated generally so the next one is decided rather than
  re-argued.

## Evidence

Read in the official SRD v5.2.1 PDF for this record:

- **p. 190**, *Target*: the one sentence quoted in **Context**, followed immediately by the
  *Telepathy* heading. Asserted with the heading in the pattern, so the clause pins the entry
  entire.
- **p. 106**, *Targets*: the five sentences in clause 5's table, each asserted.
- **p. 179**, *Cover*: "Total Cover (can't be targeted directly)" — already asserted since
  #20, and the consequence p. 106's first rule restates from the spell's side.

Document-wide term counts over the verifier's normalised text, with the issue's figures
reproduced by an independent count before anything was written down:

| Pattern | Occurrences | Reading |
|---|---|---|
| `target` | **1,214** | the noun, on every page |
| `creature` | **1,950** | the control term: vocabulary, and used more |
| `is a creature` | 20 | effects branching on a fact — content, and `creature` stays vocabulary |
| `has the … condition` | 313 | how the document states a held state |
| `is Bloodied` | 10 | likewise, for p. 177's derived state — the second control |
| `is a target` / `becomes a target` / `counts as a target` | **0** | the form `target` never takes |
| `If you are the target` | 1 | p. 144, Levitate — the spell's own branch |
| `If you are targeted` | 1 | p. 241, Rod of Absorption — the item's own branch |

**The two conditional hits were read, not just counted.** Levitate's is *"If you are the
target, you can move up or down as part of your move"* — a rule about who moves the levitated
creature, stated by the spell. The rod's is *"If you are targeted by a spell that the rod
can't store, the rod has no effect"* — the item's own limit. Neither is a general rule, and
neither changes state because something is a target; each changes what *that effect* does.

Engine side, in the tree: no resolver, test or adapter names the shape id. `ENGINE_SHAPES`
has no `"target"` key. The word appears as a field on `D20Test` — the Difficulty Class, claimed
under `difficulty-class` — and as a key in read-surface option details naming the recipient of
an offered action, which is the document's usage exactly: the name of a role, held by the
mechanic that has one.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `target` is vocabulary | **Built.** `KINDS` and `effect_shapes.json` agree, regenerated from the document; the entry carries a `VOCABULARY_REASONS` reason. Coverage reports 142 of 209 |
| 2 — 0013's criterion decides, not 0034's or 0035's | Not a mechanism. Stated so the next role-defining entry is decided on the same ground |
| 3 — heavy use and being branched on are not evidence | Not a mechanism. The two conditional hits are read in **Evidence** |
| 4 — the absence is asserted, with two controls | **Built.** Three rows in `DOCUMENT_CLAUSES`: `(?:is\|becomes\|counts as) a target` exactly 0, `target` at least 1,000, `is Bloodied` at least 5. `tests/test_effect_shape_inventory.py` asserts the rows and both controls are present |
| 5 — p. 106 is the spell's, and is asserted | **Built.** Five p. 106 clauses in `scripts/verify_d20_rules.py`, including the one `spell_reaches` rested on unasserted |
| 6 — the `targeting` kind keeps its meaning | **Built.** The five glossary members are pinned as shapes beside `target` pinned as vocabulary |
| 7 — the denominator moves to 209 | **Built.** README publishes 142 of 209, derived from the inventory by `tests/test_readme_reports_real_coverage.py`; `ENGINE_SHAPES` is unchanged in this diff |
| 8 — two p. 106 rules recorded, not filed | **Built** by recording them here. Their antecedent is [#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21) |

**#453 is closed with the criterion that was always the applicable one** — a shape names a
mechanical change to state the engine holds, and a role in someone else's mechanic names none.

_Written 2026-09-04 against SRD v5.2.1._
