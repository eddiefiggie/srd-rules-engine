# 0033 — A glossary entry is an index into the rules, not the boundary of one

- **Status:** Accepted, 2026-08-26
- **Settles:** [#228](https://github.com/eddiefiggie/srd-rules-engine/issues/228)
- **Requirements:** R17, R31, R32
- **Related:** [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  which is the same shape of record — a rule the project had been following consistently and had
  never named;
  [0025 — sight is a relation over stored state](0025-sight-is-a-relation-over-stored-state.md),
  whose subsystem raised the instance;
  [0013 — the effect-shape vocabulary normalises on mechanism](0013-effect-shape-normalisation.md),
  which owns the shape/vocabulary boundary this record declines to move

## Context

`README.md` states the v1 bar as **"full SRD 5.2 coverage is the definition of done"**, and
`tests/test_readme_reports_real_coverage.py` keeps the figure honest (R17). The standard behind
that figure is one sentence, used by every sweep since #138: **a shape is claimed when the engine
produces the consequence its entry states.**

[#228](https://github.com/eddiefiggie/srd-rules-engine/issues/228) asked whether that bar is
reachable at all. Some Rules Glossary entries appear to state no mechanic, so nothing could ever
"produce the consequence the entry states" and the shape could never be claimed — which would make
`211 of 211` unreachable and the published figure quietly mean something other than what it says.

The instance that raised it is **Bright Light** (p. 178), whose glossary body, minus its `See also`
tail, is the whole of:

> Bright Light is normal illumination.

**The observation holds. The inference does not.** The glossary entry defines the term and points
onward — its `See also` names *"Playing the Game" ("Exploration")* — and **p. 11** carries the
mechanic, under *Vision and Light → Light*:

> **Bright Light.** Bright Light lets most creatures see normally.

That is a mechanical statement. It says Bright Light imposes nothing, and the engine produces
exactly that consequence: `OBSCUREMENT_BY_LIGHT[BRIGHT]` is `Obscurement.NONE`, `can_see` returns
`CAN_SEE`, and `perception_of` returns no modifier and says the light "obscures nothing".

**The tree argued the opposite, deliberately and in writing.** Six sites recorded the superseded
reasoning, the strongest being the docstring of
`tests/test_sight.py::test_only_the_sight_shapes_whose_consequence_is_produced_are_claimed`:

> **Bright Light** (p. 178) states no consequence at all — "normal illumination" — so there is
> nothing for the engine to be judged as producing. Claiming it would count a definition.

This record supersedes that position. Every site is corrected in the same change rather than left
contradicting the claim beside it.

**And the inventory was already inconsistent on exactly this question, in the opposite direction.**
A sweep of all 155 Rules Glossary entries — bodies sliced between consecutive headings, `See also`
tails stripped, ranked by remaining length — found that contentlessness does not correlate with
`implemented`:

| Entry | Glossary body, minus `See also` | Claimed? |
|---|---|---|
| `healing` (p. 182) | "Healing is how you regain Hit Points." | **yes** |
| `save` (p. 187) | "Save is another name for a saving throw." | **yes** |
| `damage` (p. 180) | "Damage represents harm that causes a creature or an object to lose Hit Points." | **yes** |
| `damage-types` (p. 180) | "Damage types have no rules of their own…" | **yes** |
| `bright-light` (p. 178) | "Bright Light is normal illumination." | **no** |
| `weapon-attack` (p. 191) | "A weapon attack is an attack roll made with a weapon." | **no** |

`damage-types` is the *second* instance #228 named by name, and it is already claimed. The first
four are as definitional as Bright Light and are claimed **correctly** — their mechanics live on
p. 17 and in the D20 Test rules. The rule this record states was already being followed; it had
just never been written down, and the one entry where nobody noticed it applied was left out.

## Options considered

#228 offered three answers. **None is taken**, because each accepts the inference rather than the
observation.

**Option 1 — allow a vacuous claim: a shape counts as resolved when the engine models the term.**
Rejected. It would sever the coverage figure from the standard that makes it mean anything. R17's
bar is falsifiable only while "claimed" means a consequence is produced; "the enum member exists"
is true of every term the generator reads off a heading, which would claim the whole glossary at a
stroke.

**Option 2 — move the entry to `vocabulary`.** Rejected. `vocabulary` means *defined here, not an
effect shape* ([0013](0013-effect-shape-normalisation.md)), and Bright Light **is**
an effect shape whose rules sit elsewhere in the document. Moving it would encode the very error
this record corrects, and it would not stop at one entry: `healing`, `save` and `damage` are
equally definitional in the glossary and would have to follow, unclaiming three shapes that
resolve.

**Option 3 — disclose the ceiling as unreachable.** Rejected, because it would be false. p. 11
states Bright Light's consequence and the engine produces it, so the shape is reachable and so is
the ceiling. R32 asks that a real gap be disclosed; it does not ask for a disclosure of a gap that
is not there, and a false disclosure is worse than none — a reader who is told the bar is
unreachable stops checking whether it has been reached.

**Judge contentfulness from the glossary paragraph, and accept the split.** Rejected as the status
quo, and it is the option the sweep actually falsified. The inventory was already splitting six
near-identical entries four ways to two with no stated reason. A standard that produces a
different answer for `healing` than for `bright-light` is not being applied; it is being
remembered differently on different days.

## Decision

**1. A shape's content is what the document states about it anywhere, not what its glossary entry
states.** The existing standard is kept verbatim — *a shape is claimed when the engine produces the
consequence its entry states* — and its scope is made explicit: **"its entry" means the document's
treatment of the term, not the glossary paragraph.** The Rules Glossary is an index into the rules,
and several of its entries are pure pointers whose mechanics live in *Playing the Game*.

**2. The rule is asymmetric. Text outside the entry may _supply_ a consequence; it may never
_enlarge_ the bar.** Read symmetrically, clause 1 inverts itself and unclaims its own evidence:
`damage`'s document-wide content is damage types, thresholds, Resistance and the whole of p. 17 —
far more than the engine produces — so a symmetric rule would unclaim `damage`, `healing` and
`save`, the rows that show the rule was already being followed. It would even unclaim
`bright-light`, whose p. 11 paragraph continues *"Even gloomy days provide Bright Light, as do
torches, lanterns, fires, and other sources of illumination within a specific radius"* — light
source radii this engine does not model, since `LitVolume` is a caller-authored box.

So the bar for claiming remains **the consequence the shape's own entry states**. Outside text may
supply that consequence when the entry only points at it, and **a shape is never unclaimed for
document text beyond its entry**.

**3. A claim resting on text outside the entry must cite the page and assert the sentence.**
Otherwise the published figure moves on unpinned reasoning, which is the drift toward option 1 this
record rejects. `bright-light`'s claim rests on p. 11, and p. 11's three light sentences are
clauses in `scripts/verify_d20_rules.py` as of this change.

**4. `bright-light` is claimed.** p. 11 states its consequence and the engine produces it. Coverage
moves **95 → 96 of 211**, and senses and light **6 → 7 of 10**.

**5. The 211 denominator does not move, and no entry moves to `vocabulary`.** This record settles a
claiming question, not a classification one. Two classification questions it surfaces and does not
answer are filed rather than decided in passing —
[#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229) and
[#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230).

**6. The ceiling is not disclosed as unreachable, and the scope of that claim is stated rather than
assumed.** The sweep covered the **135 Rules-Glossary shapes plus the 20 `vocabulary` entries** —
155 headings. The inventory's other **76** shapes cite Equipment (17), Spell Descriptions (11),
Monsters (8), Classes (8), Playing the Game (8), Feats (7), Gameplay Toolbox (6), Magic Items (5),
Character Origins (4) and Character Creation (2), and were **not** swept.

They do not need to be, and the reason is *how they were found* rather than an assumption about
them. `scripts/derive_effect_shapes.py` enumerates the Glossary **mechanically**, by typography —
"the only text set in GillSans-SemiBold at 12pt" — so it sweeps in definitional entries alongside
mechanical ones, which is precisely why contentless entries exist in that population at all. No
other section has such a handle, so those 76 shapes were found **editorially, by sweeping for
mechanics**, each row carrying a pattern that must match its text in the PDF. A shape found by
looking for a mechanic is contentful by construction (R32: the scope is stated, not assumed).

## Why

**#228 is misscoped, not wrong, and the distinction is worth the record.** Its observation is
accurate and was worth reporting: a glossary entry really can state no mechanic. What does not
follow is that the *shape* states no mechanic, because a glossary entry is not the shape. Closing
#228 with one of its three options would have written that inference into the coverage standard
permanently — and options 1 and 3 in particular are irreversible in practice, since each removes
the pressure that would have caught the error later.

**Clause 2 is the clause this record would have got wrong.** Stating clause 1 symmetrically is the
natural way to write it, and it reads as more rigorous — *the whole document counts, both ways*.
It is also self-refuting: run it over the four already-claimed rows the sweep offers as proof, and
all four unclaim. The bar has to stay the entry's own consequence, or "claimed" comes to mean "the
engine implements everything the document says about this term", which is a different and much
larger promise than R17 makes.

**Clause 3 is what keeps clause 1 from becoming option 1 by drift.** Once a claim may rest on text
outside the entry, the cheap failure is a claim resting on text nobody re-read — the reasoning
lives in a commit message and decays. Requiring the page and the asserted sentence puts the
evidence where `scripts/verify_d20_rules.py` will go red if a future revision reworded it.

**This is 0030's shape, and it is worth naming the pattern.** 0030 found the project answering a
question consistently without having named the answer; so did this. The tell was the same in both
cases — a rule applied correctly four times and incorrectly once, where the single exception looked
principled because somebody had written a reason next to it. Six sites in the tree argued Bright
Light stated no consequence. All six were written by people applying a standard carefully. None of
them had read p. 11.

**A null consequence is the hard case, and it is why clause 3 exists.** For a mechanic that
*imposes nothing*, a produced result and a merely-modelled term are behaviourally identical: a
document clause alone cannot separate clause 4 from option 1. The discriminating evidence is
engine-side — `perception_of` reports Bright Light "obscures nothing", and
`tests/test_perception.py::test_bright_light_obscures_nothing` goes red when
`OBSCUREMENT_BY_LIGHT[BRIGHT]` is corrupted. Document side and engine side together are what
separate a claim from a definition; neither alone does.

## Consequences

**Accepted costs.**

- **A claim can now rest on a page outside the entry's own**, which is harder to audit than a
  glossary-local claim. Clause 3 is the mitigation, and it is a real obligation on every future
  claim of this shape rather than a note.
- **`SIGHT_VERIFICATION` now rests partly on a page outside the Rules Glossary.** The subsystem's
  reference gains p. 11. That is honest rather than tidy: the mechanic genuinely is not all in one
  chapter.
- **Two classification questions are opened and left open.**
  [#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229) and
  [#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230) are both reachable *because*
  of clause 1 — it is the rule that makes `weapon-attack` look claimable and `save` look like
  vocabulary. Both stay in the direction that cannot inflate the figure until settled.

**Follow-on effects.**

- Coverage is **96 of 211**, and senses and light **7 of 10**. Three of the four sight shapes the
  README described as remaining actually remain; Bright Light does not.
- `tests/test_effect_shape_inventory.py` gains a guard naming the five entries claimed on
  extra-glossary text, so the next sweep starts from this finding rather than re-deriving it — and
  asserting a counter-set unclaimed, so it fails in both directions rather than being satisfiable
  by claiming everything.
- **The sweep's other three findings need no action and are recorded so a later audit does not
  re-raise them.** `bloodied`, `temporary-hit-points`, `occupied-space` and `unoccupied-space` have
  no implementation at all; `immunity` is partial and disclosed in `core.damage` (the entry covers
  a damage type **or** a condition, and condition immunity is
  [#18](https://github.com/eddiefiggie/srd-rules-engine/issues/18)); `attitude` is
  [#142](https://github.com/eddiefiggie/srd-rules-engine/issues/142). None is affected by clause 1.

## Evidence

Printed **p. 11** was read in the official SRD v5.2.1 PDF for this record, under *Vision and Light
→ Light*, and all three light sentences quoted directly:

- "**Bright Light.** Bright Light lets most creatures see normally."
- "**Dim Light.** Dim Light, also called shadows, creates a Lightly Obscured area."
- "**Darkness.** Darkness creates a Heavily Obscured area."

All three are asserted in `scripts/verify_d20_rules.py`. The second and third are deliberate
redundancy: they are the same rule the glossary states on pp. 181 and 180, and asserting **both**
places is what demonstrates clause 1 — the glossary repeats some consequences and not others, and
Bright Light is the one it does not repeat. A single-clause version would have pinned the fact
without showing the pattern that makes it a rule.

The sweep extracted all 155 Rules Glossary entries with their bodies, sliced between consecutive
headings on each printed page using the generator's own heading enumeration, stripped of `See also`
tails — a cross-reference states nothing itself — and ranked by remaining length. Its four findings
are in **Context** and **Consequences** above.

Engine side, in the tree: `core.sight.OBSCUREMENT_BY_LIGHT` maps `BRIGHT` to `Obscurement.NONE`;
`EncounterState.can_see` returns `CAN_SEE` in Bright Light
(`tests/test_can_see.py::test_a_creature_in_bright_light_is_seen`); `EncounterState.perception_of`
applies no modifier and says the light obscures nothing
(`tests/test_perception.py::test_bright_light_obscures_nothing`).

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — a shape's content is what the document states anywhere | Not a mechanism. It is the existing claiming standard with its scope stated. Enforced by review, and pinned for five entries by `tests/test_effect_shape_inventory.py` |
| 2 — the rule is asymmetric | Not a mechanism, and the clause that keeps clause 1 from unclaiming its own evidence. Enforced by review |
| 3 — a claim on outside text cites the page and asserts the sentence | **Built for this instance.** Three p. 11 clauses in `scripts/verify_d20_rules.py`, with a CI presence check anchoring the Bright Light clause. A standing obligation on future claims, enforced by review |
| 4 — `bright-light` is claimed | **Built.** `KINDS`, `effect_shapes.json` and `ENGINE_SHAPES` agree; coverage reports 96 of 211 |
| 5 — the denominator does not move, and nothing moves to `vocabulary` | **Built** by not moving. The two questions it surfaces are filed as [#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229) and [#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230), both unclaimed until settled |
| 6 — the ceiling is not disclosed as unreachable, and the sweep's scope is stated | **Built** by not disclosing. The scope and its reasoning are in clause 6 rather than left as an untested assumption |

**Six sites carrying the superseded reasoning were corrected in this change**, not left to be found
later: two comment blocks in `core.inventory`, the hard-coded claimed set and its docstring in
`tests/test_sight.py`, `core.sight`'s `OBSCUREMENT_BY_LIGHT` docstring, and the existing p. 178
clause rationale in `scripts/verify_d20_rules.py`. The last two were **not reversed** —
`Obscurement.NONE` really is this engine's word for an absence, the same construction as
`Cover.NONE`. They gain p. 11 as the mechanic's home so a reader is not left thinking p. 178 is the
whole story.

**#228 is closed with the correction rather than with one of its options** — the observation held,
the inference did not, and a glossary entry is not the shape's boundary.

_Written 2026-08-26 against SRD v5.2.1._
