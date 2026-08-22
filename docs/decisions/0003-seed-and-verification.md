# 0003 — No structured seed for mechanics; the official SRD 5.2.1 is the verification reference

- **Status:** Accepted, 2026-08-22
- **Settles:** [#6](https://github.com/eddiefiggie/srd-rules-engine/issues/6)
- **Requirements:** R31, R32 · touches R36
- **Related:** [0002 — ledger durability](0002-ledger-durability.md); attribution wording is
  [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3); the effect-shape inventory is
  [#14](https://github.com/eddiefiggie/srd-rules-engine/issues/14); content population is
  [#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)

## Context

The plan assumed that "a machine-readable community SRD 5.2 dataset exists and is the intended
seed," and settled the sourcing question in its favour on the grounds that "verification is
cheaper than transcription when a dataset exists." Every word of that is conditional on a
dataset existing, and nobody had looked.

This issue exists because of a lesson from prior art in another repository: rules fidelity lives
or dies on data provenance rather than on the engine. So the assumption was tested before
anything was built on it.

Two things turned up that the framing had not anticipated, and both changed the answer.

### The reference document is SRD 5.2.1, not SRD 5.2

Wizards of the Coast published **SRD 5.2.0 on 22 April 2025** and **SRD 5.2.1 on 1 May 2025**.
The second is not a typographical revision. Per WotC's own community update, 5.2.1 added "15 new
magic items which were accidentally omitted from SRD 5.2," and separately "replaced duplicate
Iron Golem stat block with the Knight stat block" and "added Octopus stat block."

So a seed built against 5.2.0 is missing fifteen magic items and carries **a second Iron Golem
where the Knight belongs**. That is not a formatting difference; it is a wrong monster presented
as a right one, which is precisely the failure mode R31 exists to prevent.

It also hands us a **fingerprint**. Any candidate dataset can be interrogated for the Knight, the
Octopus, a duplicated Iron Golem, and three of the restored magic items, and it will say which
document it actually transcribed regardless of what it claims.

### No dataset carries effect shapes

Every candidate is structured down to the *statistic* and prose from there on. Open5e's Aboleth
carries typed `armor_class`, `hit_points`, `hit_dice`, and `speed`, and then states its action as
free text — `"Intelligence Saving Throw: DC 16, one creature within 30 feet that is Charmed or
Grappled by the aboleth. Failure: 10 (3d6) Psychic damage."` — with its `attacks` array empty.
5e-bits stores the entire Grappled condition as one markdown blob in a `description` field.

The engine does not consume statistics. It consumes **effects**: what a ruling applies, to whom,
for how long. That is [#14](https://github.com/eddiefiggie/srd-rules-engine/issues/14), and no
dataset removes an hour of it. A seed buys the numbers, and the numbers were never the expensive
part.

## Options considered

### The candidates

| Candidate | Edition | Licence claim | Outcome |
|---|---|---|---|
| [5e-bits/5e-database](https://github.com/5e-bits/5e-database) `src/2024` | unstated | **OGL 1.0a** | Rejected |
| [Open5e](https://open5e.com) `srd-2024` | self-labelled "5.2" | CC BY 4.0 | Rejected as a mechanics seed |
| [Tabyltop/CC-SRD](https://github.com/Tabyltop/CC-SRD), [palikhov/CC-SRD5-2](https://github.com/palikhov/CC-SRD5-2) | **5.1 only** | CC BY 4.0 | Rejected — wrong edition |
| [foundryvtt/dnd5e](https://github.com/foundryvtt/dnd5e) | 5.2 | MIT + CC BY 4.0, mixed | Rejected — contamination |
| [downfallx/dnd-5e-srd-markdown](https://github.com/downfallx/dnd-5e-srd-markdown) | **5.2.1, explicit** | CC BY 4.0 | Adopted as a finding aid only |

**5e-bits' 2024 tree is a shell.** Measured against its own 2014 tree in the same repository:

| File | `src/2024/en` | `src/2014/en` |
|---|---:|---:|
| `5e-SRD-Spells.json` | **absent** | 607,779 B |
| `5e-SRD-Monsters.json` | 22,618 B (**3 entries**) | 1,340,631 B |
| `5e-SRD-Rule-Sections.json` | **absent** | 196,655 B |
| `5e-SRD-Conditions.json` | 8,050 B (15 entries) | 7,127 B |

The three monsters are Aboleth, Adult Black Dragon, and Adult Blue Dragon. Conditions (15) and
Weapon Mastery properties (8) are complete and correct in count, and are stored as prose.

Its README states: "This project is licensed under the terms of the MIT license. The underlying
material is released using the Open Gaming License Version 1.0a." **SRD 5.2 is not offered under
the OGL** — it is CC BY 4.0 only. The repository carries no CC BY notice at all. Adopting it
would mean inheriting an attribution statement that does not match the content it covers, which
collides with R36 and with [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3).

**Open5e is the only genuinely structured candidate, and it fails on version identity.** Its
spells carry exactly the typed fields this project would want:

```json
{ "name": "Fireball", "level": 3, "school": {"key": "evocation"},
  "range_text": "150 feet", "damage_roll": "8d6", "damage_types": ["fire"],
  "saving_throw_ability": "dexterity", "shape_type": "sphere", "shape_size": 20,
  "concentration": false }
```

Coverage is real — 339 spells, 331 creatures, 440 items, 56 rules sections. Then the fingerprint
was applied:

| Probe | Expected in 5.2.1 | Open5e `srd-2024` |
|---|---|---|
| Knight stat block | present | present ✓ |
| Octopus stat block | present | present ✓ |
| Duplicate Iron Golem | absent | absent ✓ |
| Cloak of Invisibility | present | **absent** ✗ |
| Potion of Invulnerability | present | **absent** ✗ |
| Sentinel Shield | present | **absent** ✗ |

**Its creatures are 5.2.1 and its items are not.** Nor is this the fifteen restored items alone:
across all 440 item records, nothing matches "cloak", "invisib", "invulnerab", or "sentinel", so
the magic-item set is largely absent rather than merely one revision behind. The document record
self-describes as "System Reference Document 5.2" with a `publication_date` of `2024-01-01` — a
date that precedes both releases and belongs to neither.

A seed that cannot name the document it transcribes cannot support a per-entry verification
claim, because there is nothing to say the entry was verified *against*.

Open5e's second disqualifier is structural: its `srd-2024` document exposes **11 rulesets, none of
which is the Rules Glossary**. Conditions, the action list, Grappling, Cover, and Difficult
Terrain — the chapter that is most of this engine's M1 — are simply not there. The
`conditions` endpoint returns 21 records, **zero** attributed to either SRD document: 15 belong
to `core` ("5e Core Concepts", published by Open5e under a 2014 licence) and 6 to `a5e-ag`
(Advanced 5th Edition, EN Publishing). An unfiltered pull would attribute third-party and
Open5e-authored text to Wizards of the Coast's SRD 5.2.

**Foundry VTT's dnd5e system was rejected on contamination.** It integrates SRD 5.2 under CC BY
4.0 with MIT code, but the project documents that it also ships D&D Beyond "Free Rules" content
under a special agreement which **cannot be redistributed**. A corpus where redistributable and
non-redistributable material sit in the same compendium is one where separating them correctly
is a precondition of every use, and getting it wrong is a licence violation rather than a bug.

**The two CC-SRD conversions are SRD 5.1** despite one being named `CC-SRD5-2`, and both disclose
that "conversion from PDF is tricky, and the files may contain some formatting errors."

### The strategies

- **Seed from Open5e now.** Rejected. It supplies nothing for the Rules Glossary, so M1's
  actual content would be hand-modelled anyway, while the repository acquires a provenance chain
  to a source of mixed and unnameable version.
- **Seed statistics from Open5e and prose from the markdown corpus.** Rejected for M1 on the
  same ground: it pays two licence-tracking and verification costs immediately to accelerate a
  track ([#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)) that is already
  deferred. Worth revisiting when it opens.
- **Hand-model each mechanic from the document.** Adopted.

## Decision

**1. No structured dataset seeds the mechanics.** Each mechanic is modelled by hand from SRD
5.2.1 into the effect shapes [#14](https://github.com/eddiefiggie/srd-rules-engine/issues/14)
defines. The plan's sourcing decision is amended: its premise — that a usable dataset exists —
is false for the mechanics v1 needs.

**2. The official SRD v5.2.1 PDF is the verification reference, and the only one.** Every entry
is verified by a human against it, and cites the section it was verified against. The community
markdown corpus may be used as a **finding aid** — to locate a passage quickly, or to grep the
corpus — but it is never the thing checked against, and no entry is marked verified on its
authority. It is a transcription of unknown fidelity: it passes all five fingerprint probes and
transcribes Fireball and Grappled faithfully, and it also numbers the D20 Tests steps **4, 5, 6**
where the document has 1, 2, 3, a layout artifact absorbed from the PDF.

**3. Verification state lives alongside the entry it describes**, not in a separate manifest. Each
entry carries its own block:

| Field | Meaning |
|---|---|
| `state` | `unverified` \| `verified` \| `excluded` |
| `reference` | The SRD 5.2.1 section the entry was verified against |
| `date` | ISO date of the verification act |
| `reason` | Required on `excluded`; why it failed and what was wrong |

An entry is never readable without its provenance, and the pairing cannot go stale through a
join that nobody re-runs.

**4. Only `verified` entries reach the engine.** The loader refuses `unverified` and `excluded`
entries rather than filtering them silently, and a guard test asserts that it does. Per the
standing rule, the guard is proven red — an entry is flipped to `unverified`, the test is
confirmed to fail, and the entry restored — before it is trusted.

**5. Wherever the document is cited as the verification reference, it is named `SRD v5.2.1` with
its date.** "SRD 5.2" is ambiguous between two documents that differ in content, and a citation a
reader could act on must not be. The project name and the edition family ("SRD 5.2 mechanics")
may stand as they are, since 5.2.1 is a revision of 5.2 and not a separate edition. Bringing the
rest of the repository's prose into line is
[#30](https://github.com/eddiefiggie/srd-rules-engine/issues/30).

## Why

### The dataset was buying the cheap half

The work of landing a mechanic is: find the rule, decide its effect shape, express it, verify it.
A dataset supplies the numbers inside step one. It supplies nothing for steps two and three,
because no candidate stores effects as anything but prose — and it *cannot* shorten step four,
since verification against the official document is the same act whether the candidate text
arrived from a JSON file or was read off the page.

That is why the plan's reasoning inverted. "Verification is cheaper than transcription" is true
for a bestiary, where there are 331 statblocks of pure statistics and the shapes are uniform. It
is false for the Rules Glossary, where there are 15 conditions whose entire content is
effects — and the Rules Glossary is M1.

### Version identity is a precondition, not a quality metric

The instinct is to grade a seed on accuracy and accept it above some threshold. The Open5e result
shows why that is the wrong test. Its creature data is *correct* — it passes every creature probe.
Its item data is from a different revision of a differently-numbered document. Both live under one
`document` record claiming one version and one date, and nothing in the data distinguishes them.

An entry marked verified means "a human compared this to a named section of a named document." A
seed that mixes two documents cannot supply the second half of that sentence, so every entry
drawn from it would need the document identified per entry before verification could even begin —
which is the transcription cost, paid late and in a worse order.

### State alongside the entry, because the alternative fails silently

A separate manifest keeps upstream files pristine, which matters when you re-import upstream. This
decision removes upstream, so the benefit is largely gone. What remains is the cost: a manifest
is a join, and a join goes stale when an entry is added and its manifest row is not. That failure
is silent and reads as `unverified` at best, or as a missing key that a lenient loader skips at
worst. Carrying state in the entry makes the omission structural — an entry without a
verification block is malformed, not merely untracked.

## Consequences

**Accepted costs.**

- **The data track is slower, and its cost is now visible.** Every mechanic costs a human read of
  the PDF. Previously that cost was hidden inside "verification"; it was always going to be paid.
- **Obtaining and working from the official PDF is now on the critical path for data**, where the
  plan had it as a background dependency. It still does not gate the mechanics code.
- **The engine ships with less content, sooner.** M1 is one character and one encounter, which
  needs a handful of conditions and the d20 test, not 331 statblocks. v1.0 coverage is
  unaffected in scope, only in schedule.
- **The research must not be repeated.** That is what this record is for. The candidates above
  were evaluated on 2026-08-22 and the negative result is the finding.

**Follow-on effects.**

- **[#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21) (content population) inherits
  the open question.** Open5e is a plausible seed for the bestiary and spell list specifically —
  its creature data passes the 5.2.1 fingerprint and its spell fields are properly typed. That
  evaluation belongs to that track, with the version-identity problem stated up front.
- **[#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3) gains a precise target.** The
  attribution wording must be transcribed from **SRD v5.2.1** specifically, and the
  indication-of-changes wording must state which document version the project re-expressed.
- **[#14](https://github.com/eddiefiggie/srd-rules-engine/issues/14) is now upstream of all data
  work**, not parallel to it. Nothing can be modelled into effect shapes before the inventory
  names them.
- **R31 is amended**: mechanics are not seeded from a community dataset. **R32 keeps its meaning**
  — exclusion with disclosure — and gains the schema above.

## Evidence

All figures were taken on 2026-08-22 from the live sources, and every one is reproducible.

**The version fingerprint.** WotC's community update for 1 May 2025 names what 5.2.1 changed. Turn
those into probes and ask a candidate for the Knight, the Octopus, a duplicated Iron Golem, and
the restored magic items (Cloak of Invisibility, Potion of Invulnerability, Sentinel Shield). The
answer identifies the document regardless of the label. Against Open5e, query the `creatures` and
`items` collections filtered to `document__key=srd-2024`. Against a text corpus, grep the
statblock and item headings.

**Coverage measurement.** For 5e-bits, list `src/2024/en` and `src/2014/en` in the same repository
and compare file sizes; the same-repo comparison controls for schema differences that would
confound a cross-project count. For Open5e, request each v2 collection with
`document__key=srd-2024&limit=1` and read `count`.

**The contamination probe.** Request a collection *without* the document filter and group the
results by `document.key`. On `conditions` this returns 21 records across `core` and `a5e-ag` and
none from either SRD — the finding that a naive pull misattributes third-party content.

A note on method: the first pass at Open5e's rules content **read the section names and concluded
it was 2014 material**, on the strength of entries like "Step 4: Alignment" and "Playing on a
Grid" and a duplicated "Ability Checks". That was wrong on every count. Reading the bodies showed
2024 vocabulary throughout (the Influence action, capitalised Bonus Action and Reaction), the
ruleset keys include `srd-2024_d20-tests`, and the two "Ability Checks" entries are different
sections — one under D20 Tests, one under Social Interaction — not a duplicate. **Section titles
are not a version signal; the fingerprint is.** The conclusion that Open5e's rules coverage is
unusable rests on the missing Rules Glossary, which is a coverage fact, not on the misread.

## Status of implementation

**None.** M0 holds that nothing is built until the gates close. This record settles what seeds
the mechanics and what "verified" means; the verification block schema lands with the first data
to carry it, which remains gated behind
[#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3).
