# 0034 — A term the document defines and never uses is vocabulary

- **Status:** Accepted, 2026-08-26
- **Settles:** [#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229)
- **Requirements:** R17, R31, R32
- **Related:** [0013 — the effect-shape vocabulary normalises on mechanism](0013-effect-shape-normalisation.md),
  which owns the shape/vocabulary boundary and supplies the criterion this record applies;
  [0033 — a glossary entry is an index, not a shape's boundary](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md),
  whose clause 1 makes the question reachable and whose clause 5 filed it rather than
  deciding it in passing

## Context

[#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229) asks one question:

> Is naming a sub-case of an already-claimed mechanic a second shape, or a double count?

The instance is **Weapon Attack** (p. 191), whose entry is the whole of:

> A weapon attack is an attack roll made with a weapon. See also "Weapon."

The question is reachable *because* of [0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md)
clause 1. Once a shape's content is what the document states about it anywhere,
`attack_resolver` with a weapon looks like exactly the consequence p. 191 states, and the
entry looks claimable. But **Attack Roll** (p. 177) is already claimed, and claiming both
may report one mechanic twice — inflating the figure R17 exists to make falsifiable, in the
direction opposite to the one #228 reported and reached by the same rule.

**Both of the issue's branches are bad, and the second one is a trap the issue does not
name.** Claiming it risks the double count. Leaving it permanently unclaimed makes
`211 of 211` unreachable — which is #228's option 3, the answer 0033 rejected as *false*,
arrived at by a different road. A shape nobody can ever claim without double-counting is a
ceiling that cannot be reached, whatever the README says.

**The document supplies a third answer, and it is not visible from either entry.**

## Options considered

**Option 1 — claim it: a named sub-case is a second shape.** Rejected. `attack-roll`'s own
entry (p. 177) reads *"An attack roll is a D20 Test that represents making an attack with a
weapon, an Unarmed Strike, or a spell."* `weapon-attack` is not a sub-case discovered
elsewhere in the document; it is **one of the three disjuncts the parent entry itself
enumerates**, restated as a heading. Claiming both would count the same D20 Test twice, once
under its general name and once under a name for one of its three cases — and it would set
the precedent for every other entry of that shape.

**Option 2 — leave it a shape, permanently unclaimed.** Rejected, because it is option 3 of
#228 in disguise. It makes the ceiling unreachable while the README continues to publish a
denominator that implies otherwise, which is the false disclosure 0033 ruled worse than
none. Holding a question open is fine; holding a *figure* open is not.

**Option 3 — a new criterion for sub-cases.** Rejected as unnecessary and as over-firing.
The criterion already exists: `mechanism-not-exemplar` (0013, Q1/Q3/Q5) reads *"A shape is
named for the mechanism it is, not for the feature that exhibits it. Two features whose
rules differ only in a parameter are one shape."* A new rule phrased around "sub-cases"
would also catch `spell-attack`, which is claimed and correct — see clause 3.

## Decision

**1. `weapon-attack` is vocabulary. It is neither a second shape nor a double count,
because there is no mechanic there to count either way.** SRD 5.2 defines *Weapon Attack* on
p. 191 and **never uses the term again**. Swept across the document, `weapon attack` occurs
**three** times: twice on p. 191 — the entry's heading and the one sentence of its body —
and once on p. 217, where it is a noun followed by a verb rather than the defined term (see
**Evidence**). Nothing in the rules gates a mechanic on whether an attack is a *weapon*
attack. The entry renames `attack-roll` with a parameter fixed — what the attack is made
with — and supplies nothing else.

**2. The operative test is zero consumers, not the phrasing of the entry.** This is the
clause that keeps clause 1 from over-firing, and it is the one this record would have got
wrong. "Renames a parent with a parameter fixed" describes **Spell Attack** (p. 188) just as
well — *"A spell attack is an attack roll made as part of a spell or another magical
effect"* — and `spell-attack` is claimed, correctly. What separates them is not how the
glossary sentence reads but whether the document uses the term to gate anything:

| Term | Occurrences | Disposition |
|---|---|---|
| `weapon attack` | **3** — two are its own entry, one is not the term | **vocabulary** |
| `spell attack` | 62 | shape — and p. 106 gives it a formula of its own |
| `melee attack` | 410 | the term the document actually uses |
| `ranged attack` | 110 | likewise |
| `Unarmed Strike` | 40 | shape — p. 190 gives it three effect options |

Counts are over the **normalised** page text the verifier reads — whitespace collapsed and
words de-hyphenated across column breaks — because that is what clause 3's assertion runs
against. Raw extraction reports fewer for every used term (56, 406, 104, 28), since
de-hyphenation recovers occurrences split across a line break. **The figure the decision
turns on is 3 under both**, which is the point: the terms that vary with extraction are the
ones used often enough for it to matter, and `weapon attack` is not one of them.

So the three disjuncts of `attack-roll` split two-to-one on a stated test. `spell-attack`
differs in **mechanism**: p. 106 states *"Spell attack modifier = your spellcasting ability
modifier + your Proficiency Bonus"*, a rule `attack-roll` does not state and which
`core.spellcasting.spell_attack_modifier` resolves. `unarmed-strike` differs in mechanism
too: p. 190 gives Damage, Grapple and Shove, with their own damage expression and their own
save. `weapon-attack` differs in a parameter and nothing else.

**3. A declassification resting on an absence must assert the absence.** This is the mirror
of [0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) clause 3 — *a claim
resting on text outside the entry must cite the page and assert the sentence* — and it
exists for the same reason. An absence is worse than a citation for decaying silently:
nothing goes red when a term the document did not use starts being used. The count is
asserted in `scripts/verify_d20_rules.py` as of this change, **with a control**, for the
reason clause 6 gives.

**4. The denominator moves: 211 → 210.** Coverage reads **96 of 210**, the d20 test **12 of
13**, and `vocabulary` gains its twenty-first entry. 0033 clause 5 held the denominator
still because it was settling a *claiming* question; this is a *classification* question,
which 0013 owns and which moves the denominator by design. The figure changing is the
visible form of the answer, not a side effect of it.

**5. The numerator does not move, and `ENGINE_SHAPES` is not touched.** `weapon-attack` was
`implemented: false`, so no claim changes. Stated explicitly because a denominator falling
on its own is the shape of a managed figure — coverage rises from 45.5% to 45.7% with no new
capability — and a reader is right to check. The honest reading is that the denominator was
wrong, not that the engine improved.

**6. Exactly one entry moves.** The rule is stated generally and applied narrowly, because
clause 2's test is what decides and the other candidates pass it. `save` (p. 187) is a
*pure* synonym with no parameter at all and is a different question, left open on
[#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230). No other entry is
re-classified here.

## Why

**#229 poses a two-way choice, and the answer required reading the document rather than the
two entries.** Both entries were already quoted in the issue, and neither settles it — the
relationship between them is genuinely ambiguous from the text alone, which is why the issue
was filed rather than resolved in passing. What settles it is a fact visible only from a
document-wide sweep: the term has no consumers. That is the sense in which #229 is
well-posed and still unanswerable as posed.

**This is exactly where recall would have produced the wrong answer, and it is worth naming.**
"Melee Weapon Attack" is a familiar stat-block phrase — it is how the 2014 rules wrote
monster attacks, and anyone who has read a 5e stat block has read it hundreds of times. It
would have been entirely natural to assume the term is load-bearing and claim the shape. The
2024 document says **"Melee Attack Roll"** and **"Ranged Attack Roll"** instead, and
"weapon attack" survives only as a glossary entry nothing points at. R31 exists for cases
like this one, where a wrong value is indistinguishable from a right one once it is inside a
finished figure.

**Clause 2 is the clause that keeps the rule honest.** The tempting general statement —
*a glossary entry that renames an inventoried mechanism is vocabulary* — is wrong, and it is
wrong against evidence already in the tree. `spell-attack`'s entry has the same grammatical
shape as `weapon-attack`'s, and unclaiming it would be a real loss: p. 106's formula is a
mechanic the engine resolves. Any rule for this question has to be able to tell those two
apart, and the only thing that does is whether the document ever uses the term again.

**Clause 3 is what stops clause 1 becoming unfalsifiable.** The whole decision rests on a
negative, and negatives are the claims that rot without anyone noticing. There is no page to
cite and no sentence to quote — the evidence *is* the absence — so the only way to hold it is
to assert the count and let a future revision break it.

**The control row earns its place, but not for the reason it first appeared to.** The
obvious argument is that a count assertion passes just as happily against a PDF whose text
layer failed to extract. **That argument is wrong, and running it is what showed so:** the
clause asserts *exactly* 3, so a document extracting to nothing reports 0 and goes red on
the load-bearing row itself. Both corruptions were run — see **Evidence**.

What the control actually guards is narrower and likelier: an extraction that degrades
**partially**, losing occurrences split across columns or hyphenated across line breaks. 3
is a small number a damaged parse can arrive at by accident; 62 is not. So `spell attack` at
20 or more certifies the sweep read a substantially intact document, where the `exactly`
comparison only certifies it read a non-empty one. That is a weaker claim than the one first
written down here, and it is the true one.

**The precedent was already here, with its guard.** `heroic-inspiration` sits in
`vocabulary` carrying a per-entry reason: *"Mechanical, but not a separate shape: it is the
document's own name for one instance of `die-replacement`… Decision 0013, Q5."*
`VOCABULARY_REASONS` exists for exactly this case, and
`tests/test_effect_shape_inventory.py::test_an_entry_set_aside_carries_the_reason_that_actually_applied_to_it`
already asserts such an entry names the shape which subsumes it. This record adds no new
category and no new inventory machinery; it is the second member of a pattern that shipped
with one.

## Consequences

**Accepted costs.**

- **A published denominator falls, which always looks like a figure being managed.** Clause 5
  is the mitigation and it is a disclosure rather than a fix: the numerator is unchanged and
  `ENGINE_SHAPES` is untouched. A reader who checks will find the engine resolves exactly
  what it resolved before.
- **The verifier gains a second kind of clause**, and the two make opposite claims. A reader
  must now know whether a row asserts presence on a page or a count across the document.
  Kept as a separate, named table rather than a flag on the existing tuple, so the two cannot
  be confused by skimming.
- **The decision rests on a sweep of a PDF text layer.** Clause 3's control row bounds this
  risk rather than removing it. An extraction fault that dropped *both* terms uniformly would
  defeat it; nothing short of a second extraction method would catch that, and it is not
  worth building for one row.

**Follow-on effects.**

- Coverage is **96 of 210**; the d20 test **12 of 13**; `vocabulary` twenty-one entries.
- **[0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) clause 6's arithmetic
  shifts, and its decision does not.** That clause states its sweep scope as "the **135**
  Rules-Glossary shapes plus the **20** `vocabulary` entries — 155 headings." After this
  change the same 155 headings split **134 / 21**. 0033 is not edited — records are immutable
  — and this note is where a reader comparing the two finds out that neither is wrong.
- **`weapon-attack` also exists as a fixture `Rule` id** in `tests/test_combat.py` and
  `tests/test_replay_and_report.py`, both `RuleProvenance.FIXTURE`. That is a different
  namespace and is untouched. Recorded so a later grep for the string does not read those two
  as sites this change missed.
- [#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230) stays open. Clause 6
  states why it is not settled here, and clause 2's test does not decide it: `save` has no
  parameter to fix, so the question it raises is about synonymy rather than about sub-cases.

## Evidence

Read in the official SRD v5.2.1 PDF for this record:

- **p. 177**, *Attack Roll*: "An attack roll is a D20 Test that represents making an attack
  with a weapon, an Unarmed Strike, or a spell."
- **p. 191**, *Weapon Attack*: "A weapon attack is an attack roll made with a weapon."
- **p. 188**, *Spell Attack*: "A spell attack is an attack roll made as part of a spell or
  another magical effect."
- **p. 106**: "Spell attack modifier = your spellcasting ability modifier + your Proficiency
  Bonus."
- **p. 190**, *Unarmed Strike*: the three options — Damage, Grapple, Shove.

The term sweep ran case-insensitively over every page, counting occurrences and recording
the page of each. Its results are the table in clause 2.

**One raw hit was discarded, and checking it is part of the method.** The naive sweep reports
**three** occurrences of `weapon attack`, not two. The third is **p. 217**, the Dancing Sword
magic item: *"After the hovering weapon attacks for the fourth time, it flies back to you"* —
a noun followed by a verb, not the defined term. A sweep that reported 3 and stopped would
have read as three consumers and reversed the decision.

**The assertion is nonetheless 3, not 2.** Asserting 2 would encode this editorial discard
into the count and hide it: a reader re-running the verifier would see a number that does
not match the document, and the p. 217 line would be invisible. So the raw truth is
asserted, and the discard is pinned by its own presence clause on p. 217 — the count reads
3, and the clause beside it says why one of the three is not the term. **2** is therefore
the plausible-wrong value the corruption proof uses: it is exactly the "helpful" correction
a later reader would be tempted to make.

Engine side, in the tree: `weapon-attack` appears in neither `ENGINE_SHAPES` nor any resolver.
`spell-attack` resolves to `core.spellcasting.spell_attack_modifier` — the p. 106 formula,
not the attack roll — which is itself evidence for clause 2: the inventory already recorded
that `spell-attack`'s claim rests on its own mechanism rather than on being an attack roll.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `weapon-attack` is vocabulary | **Built.** `KINDS` and `effect_shapes.json` agree; the entry carries a `VOCABULARY_REASONS` reason naming `attack-roll`. Coverage reports 96 of 210 |
| 2 — the operative test is zero consumers | Not a mechanism. Pinned in both directions by `tests/test_effect_shape_inventory.py`, which asserts `weapon-attack` is vocabulary **and** that `spell-attack` and `unarmed-strike` remain shapes. Enforced by review beyond those three |
| 3 — a declassification resting on an absence must assert the absence | **Built for this instance.** A document-wide clause table in `scripts/verify_d20_rules.py` asserts `weapon attack` at exactly 3 occurrences, with `spell attack` at 20 or more as the control, plus five presence clauses (pp. 177, 188, 191, 106, 217) and a CI check anchoring the table. Both corruptions were run. A standing obligation on future declassifications, enforced by review |
| 4 — the denominator moves to 210 | **Built.** README publishes 96 of 210 and the d20 test 12 of 13, both derived from the inventory by `tests/test_readme_reports_real_coverage.py` |
| 5 — the numerator does not move | **Built** by not moving. `ENGINE_SHAPES` is unchanged in this diff |
| 6 — exactly one entry moves | **Built** by not moving anything else. [#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230) stays open and unclaimed |

**#229 is closed with a third answer rather than one of its two** — the term has no
consumers, so it is neither a second shape nor a double count.

_Written 2026-08-26 against SRD v5.2.1._
