# 0013 — The effect-shape vocabulary normalises on mechanism, not on the feature that exhibits it

- **Status:** Accepted, 2026-08-23
- **Settles:** [#76](https://github.com/eddiefiggie/srd-rules-engine/issues/76)
- **Requirements:** R17 · touches R31, R32
- **Related:** [0003 — seed and verification](0003-seed-and-verification.md), whose rule governs
  every citation below; [#78](https://github.com/eddiefiggie/srd-rules-engine/issues/78) took Q5's
  answer for the number of callers its API seam must serve, and shipped before this was accepted

## Context

Eleven sweeps closed [#14](https://github.com/eddiefiggie/srd-rules-engine/issues/14) with
`unswept_sections` empty and 215 shapes inventoried. Coverage of the document is complete. The
*vocabulary* is not settled, and #76 was filed precisely so that closing #14 did not imply it was.

Three facts about the current state bound what this record can cost:

**Only 17 of the 215 shapes are `implemented: true`.** Every shape named in all five questions is
`implemented: false`. Renaming, merging, or splitting any of them changes no engine behaviour and
migrates no caller. The normalisation is close to free *now* and gets monotonically more expensive
with every coverage issue that lands against the current names — which is the argument for doing it
before [#15–#20](https://github.com/eddiefiggie/srd-rules-engine/issues/15) rather than after.

**`kind` has no guard.** `KINDS` in `scripts/derive_effect_shapes.py` forces every *name* to be
classified — an unclassified glossary entry fails derivation — but nothing constrains the *value*.
It now holds 19 distinct values. #76 estimated "roughly fifteen"; it drifted by four while the issue
sat open, which is the unguarded-enum failure the issue predicts, observed rather than hypothesised.

**The Q2 exclusion criterion exists only in generator comments.** "No Ruling applies it, so it is
not a shape" appears four times as `#:` prose in `derive_effect_shapes.py` and nowhere in
`effect_shapes.json`. The `vocabulary` block records 19 set-aside entries, but all 19 carry the same
reason — the glossary-term exclusion. The progression exclusion is a *second, different* criterion
that no consumer of the artifact can see, and no guard checks.

### On method

Every claim below was checked against the official SRD v5.2.1 PDF. Following
`scripts/verify_d20_rules.py`, evidence is recorded as **the pattern that must match the cited
printed page**, not as transcribed prose — the repository deliberately carries no SRD prose (see
`NOTICE.md`), and a pattern is falsifiable where a paraphrase is not.

One method note, because it cost time and would cost it again: `derive_effect_shapes.py` matches
monster patterns against **whole stat-block text**, and a stat block spans pages. `recharge` cites
Air Elemental at p. 258 and its Whirlwind trait is printed on p. 259. A page-scoped search reports a
false miss. The citation is correct; a naive re-check is not.

### Three mechanics that acceptance forced

The draft recommended merges without saying how a merged shape carries a citation, which the data
model allows only one of. Settling that is part of settling the questions:

1. **A merged shape cites the exemplar that appears earliest in the document**, because that is
   where a reader first meets the mechanism. The other exemplars become content, which is the
   shape-versus-content line the sweeps already draw.
2. **Where the document's own Rules Glossary names one instance of a merged mechanism, that entry
   moves to `vocabulary` with a reason of its own** — naming which shape subsumes it. It is not
   dropped, because silent omission is the failure R17 exists to name.
3. **The criteria move into the artifact.** Q2's finding is that a rule applied across eleven
   sweeps while living only in generator comments is not a record. `criteria` is now a field.

---

## Q1 — Three recharge shapes

**Current:** `recharge` (Monsters, p. 258), `daily-recharge` (Magic Items, p. 215),
`rest-recharge` (Classes, p. 28). All `kind: resource`, all unimplemented.

### Evidence

The document defers the recharge *mechanism* to each feature, in identical language in two places:

| Printed page | Pattern that must match |
|---|---|
| 185 (Long Rest) | `Some features are recharged by a Long Rest` … `it recharges in the way specified in its description` |
| 187 (Short Rest) | `Some features are recharged by a Short Rest` … `it recharges in the way specified in its description` |
| 206 (Magic Items) | `Some magic items have charges that must be ex-\s*pended` |

The rest rules do not describe *how much* is regained or *when* — they say the feature's own
description settles it. Magic-item charges are introduced once as a general mechanism on p. 206;
"1d3 at dawn" is Cloak of Invisibility's own text, not a rule about dawn.

### Decision — **merged into one `resource-recharge`, parameterised by trigger**

The three differ only in a trigger value (`die-roll-at-turn-start`, `dawn`, `short-rest` /
`long-rest`) and a quantity. The document itself treats the trigger as a per-feature parameter
rather than as three mechanics; three entries reproduce the *content* layer inside the *vocabulary*
layer, which is the exact line `derive_effect_shapes.py` says it is drawing.

**Cost:** the stated granularity rule is "distinct trigger, fails independently." These do fail
independently, so this recommendation genuinely relaxes it. The relaxation is bounded by requiring
the trigger to be an enumerated parameter — a shape whose trigger is *not* expressible in that enum
stays its own shape.

---

## Q2 — "No Ruling applies it, so it is not a shape"

**Current:** excludes Ability Score Improvement (#70), Ability Score Increase across most feats
(#71), Level Advancement (#73), and is cited as governing whether `split-movement` (#75) belongs.
Never agreed.

### Evidence

| Printed page | Pattern that must match | What it settles |
|---|---|---|
| 51 | `You gain the Ability Score Improvement feat` | The class feature grants a **feat**; it is not itself a score change |
| 88 | `Increase one ability score of your choice by 1, to a maximum of 30` | The actual increase is a bounded numeric change to engine-held state |
| 14 | `You can break up your move, using some of its movement before and after any action` | Resolved *within a turn* |

Two things follow. First, in 5.2 the ASI class feature is a *delivery mechanism* for a feat, and the
mechanical effect lives in the feat — so the sweeps excluded it at the wrong layer. Second, the
effect it delivers is a bounded change to ability scores, and ability scores are state the engine
holds and derives every modifier from.

### The criterion is on the wrong axis

"No **Ruling** applies it" is an *API* test: it asks whether `adjudicate()` currently touches the
shape. That couples the vocabulary to today's API surface — and
[#78](https://github.com/eddiefiggie/srd-rules-engine/issues/78) is about to change that surface. A
criterion that must be re-evaluated whenever the API grows is not a criterion.

The state axis asks instead: **does the shape name a mechanical change to state the engine holds?**
Ability scores: yes. XP-to-level thresholds: no — the engine holds a level, and the threshold table
is the procedure for arriving at one, resolved by no engine operation.

### Decision — **restated on the state axis; `ability-score-increase` admitted; Level Advancement stays excluded; `split-movement` stays**

The repair is the mechanical one #76 already names: one `ability-score-increase` entry cited to
Boon of Combat Prowess, p. 88. `split-movement` survives on either axis — it is resolved during a
turn and the read surface must report movement remaining — so it was never really in question, and
this record says so explicitly to stop it being re-raised.

**Cost:** the state axis is broader and will admit shapes the API axis excluded. That is the
intended direction — R17's inventory is a measure of *the document*, and a gap that the engine
cannot yet resolve is exactly what `implemented: false` is for. Recording a shape as absent is
cheaper than discovering it is missing from the measuring stick.

---

## Q3 — `miss-becomes-hit` and `legendary-resistance`

**Current:** two shapes, both `kind: test-modifier`, both unimplemented.

### Evidence

| Printed page | Pattern that must match |
|---|---|
| 88 (Peerless Aim) | `When you miss with an attack roll, you can hit instead` |
| 258 (Aboleth) | `If the aboleth fails a saving throw, it can choose to suc-\s*ceed instead` |

The two sentences are structurally identical: *a failed d20 test of kind K is overridden to a
success, at the holder's choice.* They differ in the test kind (attack roll / saving throw) and in
the usage budget (once per turn / 3 per day, 4 in lair). Both differences are parameters that other
shapes already carry.

### Decision — **merged into one shape, named for the mechanism**

Something like `failed-test-overridden-to-success`, parameterised by test kind. #76's own diagnosis
is confirmed: `legendary-resistance` is named after the monster feature that exhibits the mechanic
rather than after the mechanic, which is what obscured the duplication. The usage budget is a
separate concern and should not be encoded in the shape name.

This one is the clearest of the five. It is a naming failure with a structural consequence, not a
genuine granularity trade-off.

---

## Q4 — Poisons and contagions treated oppositely

**Current:** four poison shapes keyed by delivery type (`kind: poison-delivery`); one
`magical-contagion` shape (`kind: effect`) with the three contagions as content.

### Evidence

| Printed page | Pattern that must match | What it settles |
|---|---|---|
| 197 | `Poisons come in the following four types` | The four types are an explicitly enumerated closed set, in their own subsection, each with its own exposure rule |
| 194 | `Magical Contagions` … `If a creature infected with a magical contagion spends 3 days recuperating` | Contagions get **one shared mechanic** (Rest and Recuperation, a DC 15 Constitution save), then named instances |

### Decision — **both kept as they are; the criterion is recorded in the artifact**

This is the question where the evidence contradicts the issue. The two treatments are not
inconsistent — they mirror an asymmetry in the document. The SRD itself enumerates poison's four
types as a closed named set with its own rules subsection, and gives contagions a single shared
mechanic with the instances as content. Each sweep followed the document.

The criterion is already in the repository, applied and stated in the Gameplay Toolbox sweep, where
it admitted the eight weapon mastery properties and declined the nine Environmental Effects: **a
closed named set with its own rules subsection is vocabulary; worked examples that compose existing
shapes are content.** Poison's four types pass it. The three contagions fail it. The rule is sound
and was applied correctly; it was simply never written anywhere a reader of the *artifact* could
find it.

**One real defect survives.** `poison-delivery` is its own `kind` while `magical-contagion` is
`effect`. That inconsistency is real, and it belongs to the `kind` question below rather than to the
shape-count question.

---

## Q5 — The reroll family is four shapes

**Current:** `reroll` (Wish), `roll-twice-take-either` (Savage Attacker), `reroll-a-natural-one`
(Halfling), "and arguably `legendary-resistance`". Also `heroic-inspiration`, which #76 does not
list among them but #78 does.

### Evidence

| Printed page | Pattern that must match | Structure |
|---|---|---|
| 86 (Halfling Luck) | `When you roll a 1 on the d20 of a D20 Test, you can reroll the die, and you must use the new roll` | Replace a d20 · conditional trigger · **new roll binding** |
| 183 (Heroic Inspiration) | `you can expend it to reroll any die immediately af-\s*ter rolling it, and you must use the new roll` | Replace any die · costs a resource · **new roll binding** |
| 175 (Wish) | `forcing a reroll of any die roll made within the last round` · `You can force the reroll to be made with Advantage or Dis` | Replace another creature's die · retroactive within a round · **and may impose Advantage/Disadvantage on the replacement** |
| 87 (Savage Attacker) | `you can roll the weapon's damage dice twice and use either roll against the target` | Roll **damage dice** twice up front · **choose either** · nothing is replaced |

### Decision — **the family is three, not four, and becomes one parameterised shape**

**`roll-twice-take-either` is not a reroll.** Savage Attacker rolls damage dice — not a d20 test —
twice up front and lets you choose. Both results exist simultaneously and the result is not binding.
That is structurally the *advantage* pattern applied to damage, and it belongs nowhere near a family
whose defining property is that a die is replaced and the replacement is binding. Keep it separate;
consider renaming it toward the advantage analogy.

**`legendary-resistance` is not a reroll either.** No die is rerolled — the outcome is overridden.
It belongs to Q3.

**The genuine family is Halfling Luck, Heroic Inspiration, and Wish**, which share "an already-rolled
die is replaced, and the replacement is binding" and differ in trigger, cost, whose die, and how far
back. They become **one `die-replacement`**, parameterised on those four axes, cited to Halfling
(Character Origins, p. 86) as the earliest exemplar. Wish's Forced Reroll is declined as expressible
by it. Heroic Inspiration is a Rules Glossary entry, so by mechanic 2 above it moves to `vocabulary`
carrying a reason that names `die-replacement` — the document's own word for one instance of the
mechanism, kept visible rather than dropped.

`#81` is the argument that closed this. It shipped `replace_die`, **one** seam serving all three
callers, so a single shape is what the engine actually exposes; three shapes would have described a
distinction the implementation does not make.

### This was the answer #78 was waiting on

#78 asked how many callers its API seam must serve. Three — and Wish set the hardest requirement,
since the replacement die may itself be rolled with Advantage or Disadvantage, so the seam cannot
return a single substitute value. That constraint is invisible from the other two and would have
been missed by designing against Heroic Inspiration alone. #78 shipped on this reading in #81,
before this record was accepted; that ordering was deliberate and is noted in its PR.

---

## Also pending

**`bonus-die-on-roll` is misnamed — confirmed.** Named from Bardic Inspiration (Classes, p. 31),
which only ever adds. The Feats sweep recorded in its own generator comment that Boon of Fate applies
its roll "as a penalty as well as a bonus, which that entry does not currently say." Rename toward
direction-neutrality — the mechanism is *a rolled die applied to a d20 test in either direction*.

**`kind` is now a closed vocabulary with a guard, on one axis.** 19 values, no check, drifted by
four while #76 was open. `KIND_VALUES` closes it, the generator refuses to emit a stray value, and
`tests/test_effect_shape_inventory.py` checks the published artifact in **both** directions — a
one-way check would let a retired value sit in the declaration forever, which is the same drift
running backwards. Both directions were seen red before being trusted.

The Q4 defect is fixed with it: `poison-delivery` becomes `affliction`, and `magical-contagion` —
its structural peer, previously `effect` — takes the same kind.

**The two-axis question is deliberately not settled here.** `kind` still mixes *what a shape is*
with *what it applies to*: Heroic Inspiration was `resource` while `reroll-a-natural-one` was
`test-modifier`, though the mechanism is both a resource you expend and a die replacement. Q5's merge
removes that particular collision, but not the conflation behind it. Splitting `kind` into two fields
would re-classify all 211 shapes and change the schema, so it is a decision of its own rather than
something to settle in passing — and closing the enum now stops the drift while it waits.

**`damage-reduction` vs `resistance` — keep separate.** Resistance halves (a rule that needs no
roll); Goliath's Stone's Endurance subtracts a rolled amount (a rule that requires one). A shape that
consumes a die roll and one that does not are not the same shape, whatever they have in common
downstream.

---

## What changed

| Question | Change | Net shapes |
|---|---|---|
| Q1 | 3 recharge → 1 `resource-recharge` | −2 |
| Q2 | admit `ability-score-increase` | +1 |
| Q3 | 2 override → 1 `failed-test-overridden-to-success` | −1 |
| Q4 | no shape change; `poison-delivery` → `affliction`, and `magical-contagion` joins it | 0 |
| Q5 | 3 reroll shapes → 1 `die-replacement`; Heroic Inspiration → `vocabulary` | −2 |

**215 → 211**, 17 still implemented, `vocabulary` 19 → 20. Plus one rename
(`bonus-die-on-roll` → `die-applied-to-a-roll`), a closed `kind` enum guarded in both the generator
and the artifact, a `criteria` block in the data, and one regeneration.

## Consequences

**Accepted costs.**

- Q1 relaxes the "distinct trigger, fails independently" rule. Bounded by making the trigger an
  enumerated parameter, so an inexpressible trigger still earns its own shape.
- Q2's state axis is broader than the API axis and will admit shapes the engine cannot resolve.
  That is what `implemented: false` is for.
- Seven shape ids change or retire. Free today because none of them are implemented — 17 of 211
  are, and none appear here — and not free after #15–#20 land against these names.
- A merged shape now cites one exemplar where two or three features exhibit it. The others are
  content, findable through the decision rather than through the inventory.

**Follow-on effects.**

- The two-axis `kind` question is left open, above. It wants its own record if it is ever taken up.
- `criteria` and `kind_values` are new top-level fields. The loader reads named fields only, so
  older readers ignore them and `compat` is unchanged.
- Anything citing a retired id — `recharge`, `daily-recharge`, `rest-recharge`,
  `legendary-resistance`, `miss-becomes-hit`, `reroll`, `reroll-a-natural-one`,
  `bonus-die-on-roll`, `heroic-inspiration` — is now citing something that does not exist. Nothing
  in the engine does; this record is the map for anything outside it.

## Evidence

Reproduce with a copy of the official SRD v5.2.1 PDF, which this repository does not carry:

```
python3 scripts/derive_effect_shapes.py /path/to/SRD_CC_v5.2.1.pdf
python3 scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf
```

Every pattern in the tables above was matched against whitespace-normalised text of the cited
printed page (printed page N is PDF index N−1), except monster patterns, which match whole
stat-block text spanning pages — see the method note in Context.

**Where the method went wrong:** the first pass searched `recharge`'s cited page in isolation and
reported a false miss, because Air Elemental's stat block begins on p. 258 and its Whirlwind trait is
printed on p. 259. Any re-check of a monster citation must match the block, not the page.

## Status of implementation

**Implemented with this record.** `effect_shapes.json` is regenerated (211 shapes, 17 implemented,
20 vocabulary), `KINDS` and `KIND_VALUES` are edited, and three guards are added to
`tests/test_effect_shape_inventory.py` — each seen red before being trusted. No engine behaviour
changes: none of the shapes touched here is implemented, and the seam their callers need shipped
separately in #81.
