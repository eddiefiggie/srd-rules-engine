---
title: A minimal playable SRD ruleset - Plan
type: feat
date: 2026-09-14
topic: minimal-playable-ruleset
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/475
---

# A minimal playable SRD ruleset - Plan

## Goal Capsule

- **Objective:** Ship the smallest ruleset that plays — one level-1 character, two of the six
  verified creatures given attacks, and three simple spells — so the recall half of the skip
  guarantee ([#403](https://github.com/eddiefiggie/srd-rules-engine/issues/403)) can be asked
  at all. README names #403 as M1's primary criterion and says *nothing else substitutes for
  it*; #403 says it is blocked on there being nothing to play. This is the unblocker, and it is
  **not** [#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21), which is the whole
  bestiary and spell list as a parallel data track.
- **Headline finding:** **#475's sharpest claim is wrong, and the true gap is narrower.** The
  issue says `load_ruleset` has no caller and *no SRD-derived rule has ever reached the
  engine*. `tests/test_hazards.py` loads `burning_rule()` and `suffocation_rule()` through it,
  both `RuleProvenance.SRD` with a `Verification` block, and `core.save_ends` ships fifteen more
  the same way. What has never existed is a **playable set** — SRD rules, creatures that can
  attack, spells with effects, and a catalogue with `cited` rows — assembled into one
  `Ruleset` an adapter can pick. Planning against the stronger claim would rebuild machinery
  that already works.
- **The shape:** a `core.playable` module that assembles what the engine already ships, plus
  the four things it does not yet have — creature attacks, three spell resolvers, a shipped
  trigger catalogue, and a console script. Zero new effect shapes, to be **proved rather than
  asserted** (Finding 4).
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. [0003](../decisions/0003-seed-and-verification.md)
  (verification), [0012](../decisions/0012-fixture-provenance.md) (provenance selects the entry
  point), [0016](../decisions/0016-adapters-hold-the-turn.md) (an adapter holds the turn),
  [0038](../decisions/0038-a-spell-is-data-the-caster-carries.md) (a spell is data the caster
  carries), [0040](../decisions/0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md) (a weapon
  is an item and proficiency is the wielder's). Every rule value this plan ships is read from
  `/path/to/SRD_CC_v5.2.1.pdf` at build time and asserted in `scripts/verify_d20_rules.py`
  (R31); the page numbers below are the ones the bestiary's own verification blocks cite, and
  the spell pages are **unread** until U3 reads them.
- **Stop conditions:** Stop and ask if any of the three spells needs a shape the inventory
  lists as unbuilt (Finding 4 fails), if a creature attack cannot be expressed as a `Weapon` the
  creature holds (0040 clause 1), if NOTICE.md's boundary would be crossed by a value that is
  prose rather than a mechanic, or if the console script would need a dependency (R33).
- **Tail ownership:** One PR for U1–U5. The recorded live run is #403's own acceptance and
  stays there (KTD3).
- **Where it can be built:** only on a machine holding `/path/to/SRD_CC_v5.2.1.pdf` with
  `pymupdf` installed. U1–U3 state no number until its page is read, and the stop condition
  above refuses a build that cannot open the page. The session that wrote this plan could
  not: its network policy denied the document's download hosts and PyPI, which is why the
  plan landed on its own.

---

## What the Investigation Found

Established against the tree at `0964c99`, build `09122026.3`.

**Finding 1 — SRD-derived rules already reach the engine, in-package and in Python.**
`core.save_ends.save_ends_rules()` returns fifteen `Rule`s with `RuleProvenance.SRD` and a
shared `Verification` citing p. 63; `core.hazards` ships `burning_rule`, `suffocation_rule`,
`malnutrition_rule` and `landing_rule` the same way, each with its own verification block and
each with rows in `scripts/verify_d20_rules.py`. `tests/test_hazards.py` builds an
`Adjudicator` over `load_ruleset((burning_rule(),))`. So the loader's SRD arm has been
exercised, the in-package precedent for SRD rules is Python rather than JSON, and #475's
finding that no SRD rule has ever reached the engine is false. **What is true:** nothing
assembles these into a set, no shipped creature can make an attack, and no adapter can start a
session without a consumer constructing everything by hand.

**Finding 2 — the six creatures are statistics only, and `Statistics` has no consumer.**
`core.bestiary.Statistics` carries armour class, hit points, hit dice, speeds, abilities,
challenge rating and proficiency bonus, every entry `traits_modelled: false`, and nothing in
`src/` outside `bestiary.py` reads the type. A `Combatant` needs `equipment`,
`weapon_proficiencies` and `is_player_character` on top of what `Statistics` holds — and
**not** `hands`: `Combatant.__post_init__` says *"`hands is None` is not a violation: no SRD
rule states how many hands a creature has, so an unstated count cannot be exceeded (R31)"*,
and `can_attack_with` reads `free_hands == 0` rather than `not free_hands` for the same
reason. A Wolf is built with `hands=None` and a Bite with `hands_when_held=0`; the fixture's
`FIXTURE_FANGS` says `hands_when_held=1` on a creature given two hands, which is the invented
shape and not the one to copy. The conversion is new, and it is where a creature's attack
has to enter.

**Finding 3 — an attack is a `Weapon` the creature holds, and the fixture already models a
natural weapon that way.** Since 0040, `attack_resolver()` closes over nothing and reads the
weapon off state; `tests/fixtures/ruleset.py` gives the scree-hound `FIXTURE_FANGS`, a
`Weapon` held in its hands, with a comment quoting p. 89 on a monster being proficient with
the weapons in its stat block as the proficiency's reason. **That sentence is quoted in the
fixture and asserted nowhere** — `scripts/verify_d20_rules.py` has no p. 89 row for it, which
is the #371 shape exactly, so U1 reads the page and adds the row before relying on it. A
Wolf's Bite is the same shape with verified numbers: `damage_dice`, `damage_sides`,
`damage_type`, `ability`, `melee`, `reach`. **Whether the stat block's attack line is a
mechanic or prose is NOTICE.md's question, and NOTICE.md answers it:** *"Game mechanics, rule
names, statistics, and any rules text this project encodes"* are what CC BY 4.0 covers and
what the project re-expresses; there is no Product Identity boundary in SRD 5.2.1 and
invoking one is a category error. A to-hit bonus, a damage expression, a damage type and a
reach are statistics. A trait's *description* is not, and stays out.

**Finding 4 — the three spells look like they need no new shape, and that is a claim to prove
on the page.** Spell Descriptions is 1 of 11 shapes in the inventory. The ten unbuilt are
`summon-creature`, `planar-travel`, `resurrection`, `control-creature`, `create-object`,
`end-magical-effect`, `ongoing-damage`, `half-damage-on-save`, `damage-transfer` and
`information-granted`. An attack-roll cantrip is `attack-roll` plus `DamageDice`; a
save-or-damage cantrip is `saving-throw` plus `DamageDice` **only if its failure clause is
"takes the damage" and its success clause is "no damage"** — a spell whose success clause is
*half* damage lands on `half-damage-on-save`, which is unbuilt; a healing spell is
`HealingDice`, which #438 already taught to refuse a corpse (p. 180). The candidates are named
in U3 and **none is chosen until its entry is read**, because the difference between "no
damage on a save" and "half damage on a save" is one word in the document and one unbuilt
shape in the tree.

**Finding 5 — no shipped trigger catalogue exists.** `Adjudicator` defaults to
`Catalogue(version=1)`, empty, and the only populated catalogue is
`tests/fixtures/ruleset.py`'s. #403's question is whether an agent skips when nobody has shown
it where the challenges are, and a session with an empty catalogue **cannot challenge**, so
its report can only ever say "no row" (`Report.not_measured`, second entry). The playable set
therefore needs a catalogue with at least the `cited` rows the SRD supplies outright — an
attack forces an attack roll, a hazard forces a save — or the experiment measures nothing.

**Finding 6 — the CLI is finished and has no entry point, by its own account.**
`adapters/cli.py` is a full command loop over `adapters.Session`; `[project.scripts]` is absent
from `pyproject.toml`, and the module docstring says why: *a console script has to pick a
ruleset, and the only rules this library ships are `core.save_ends`'s fifteen*. That sentence
is the definition of what this plan changes. `run()` takes an `ask` callable and there is no
`main()`, so the script is a small function that constructs the `Adjudicator`, the `Session`
and the adapter over the playable set, and nothing else.

**Finding 7 — two stale sentences, fixed with this plan.** `tests/fixtures/__init__.py` said #3
was open; it closed on 2026-08-23. `core.turn_span` attributed the vocabulary-over-boolean
rule to 0019, which is about the inventory's `kind` axis and says nothing about booleans
([#472](https://github.com/eddiefiggie/srd-rules-engine/issues/472)); the citation was copied
from 0049 clause 7, which carries the same error. The rule is
[0039](../decisions/0039-equipment-is-what-a-creature-holds-wears-and-carries.md)'s rejected
option 3 — *"they are mutually exclusive and a boolean triple can express states the rules have
no meaning for … a closed vocabulary refuses those by construction"* — and both citations now
say so.

---

## Key Technical Decisions

These are #475's four open decisions, settled.

**KTD1 — The playable set ships inside the library, as a `core` module, in Python.** #475
decision 1. The precedent is not `data/`'s JSON — it is `core.save_ends` and `core.hazards`,
which already ship SRD rules as `Rule` objects with `Verification` blocks and verifier rows.
A `core.playable` module assembles those, adds the three spells and the catalogue, and exposes
`playable_ruleset()`, `playable_catalogue()` and `playable_encounter(*, seed)`. In-package
means installing the engine gets you a game, which is what an executable needs (Finding 6);
[0011](../decisions/0011-module-layout-and-versioning.md) clause 1 puts anything the loop and
adapters consume in `core`, and a fifth package would need that record reopened. R33 is
unaffected: this is data and code, not a dependency.

**KTD2 — Creature attacks go in the playable set, not in `bestiary.json`.** #475 decision 2.
The bestiary's scope note says statistics only, and `traits_modelled: false` on every entry
is a claim consumers rely on; adding an attack line changes what the file asserts about all
six creatures to give two of them an action. The playable module holds the `Weapon` for each
creature it fields, cited to the same page the bestiary cites (Wolf p. 347, Giant Rat p. 353,
Bandit p. 261, Guard p. 296), and builds the `Combatant` from `Statistics` plus that weapon.
One creature in two places is the accepted cost; the bestiary stays honest and the conversion
(Finding 2) has to exist anyway.

**KTD3 — This plan is done when the set plays and the protocol is committed; the recorded run
is #403's.** #475 decision 3. U1–U5 are buildable in this repository by anyone; the live run
needs a person, a model in a fresh context, and no access to this tree. Putting the run inside
this plan's finish line leaves #475 open on somebody's calendar and a plan reporting
"outstanding" over shipped code, which is the state `AGENTS.md` calls worse than unfiled. So
the protocol is a deliverable here, the run is #403's acceptance, and #475 closes with the PR.

**KTD4 — Coverage may not move, and the README says why rather than the counter.** #475
decision 4. If Finding 4 holds, the headline reads 146 of 210 before and after, while the
engine goes from unplayable to playable. README already carries the paragraph explaining that
the inventory counts resolved shapes and a route moves nothing; the build line names this as
the largest instance of it so far. If Finding 4 fails on a spell, that spell is swapped for one
that needs no new shape rather than the shape being built here — building a shape is a
mechanics change with its own record, and this plan is content.

**KTD5 — The catalogue ships only `cited` rows.** Finding 5. A row is `Grounding.CITED`
only where the document states the trigger outright — a stat block's attack line names its
attack roll, and a spell's entry names its save — and each row's sentence is read and added to
the verifier before the row ships; a trigger whose sentence cannot be found is not `cited`
and is not shipped. `authored` rows are
project judgement and the catalogue is known-incomplete by construction (0004); a minimal
playable set adds none, so the recall experiment measures the document's own triggers and the
protocol says so.

**KTD6 — The console script is `srd`, needs nothing, and constructs only.**
`[project.scripts] srd = "srd_rules_engine.adapters.cli:main"`. `main()` builds the
`Adjudicator` over `playable_ruleset()` and `playable_catalogue()`, opens a `Session` on
`playable_encounter(seed=...)` with a ledger path from `argv`, and calls `run(input)`. No
dependency (R33), no command reaches adjudication (`FORBIDDEN_COMMAND_NAMES` still holds), and
the seed is an argument so a run is replayable.

---

## Scope Boundaries

**In scope:** `core.playable`; a `Combatant` from `Statistics`; a `Weapon` per fielded
creature; one level-1 character with no class features; three spell resolvers through
`spell_resolvers`; a `cited`-only catalogue; the console script; verifier rows for every
sentence relied on; the recall protocol document; the two stale sentences (Finding 7); the
build stamp and README.

### Deferred to Follow-Up Work

- **The recorded live run** — [#403](https://github.com/eddiefiggie/srd-rules-engine/issues/403),
  by KTD3. It is the acceptance of that issue, not of this plan.
- **Every other creature and spell** — [#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21).
  Its blocker line names #6 and #3 as gates and both are closed; the PR body says so on the
  issue.
- **Class features on the character** — the Classes shapes are unbuilt and are ruleset data by
  design (R31). Not filed separately: they are #21's content once the shapes exist.
- **Any spell that needs an unbuilt shape** — KTD4. Not filed: the ten shapes already carry
  their own reasons in the inventory and are #21's content.
- **Tool proficiencies for Help** — [#473](https://github.com/eddiefiggie/srd-rules-engine/issues/473),
  unaffected here; the character carries skills only.

**Out of scope:** any rule value not read from the document at build time; any trait
description; a second player character (a non-goal); any adapter beyond the console script.

---

## Implementation Units

### U1. A `Combatant` from `Statistics`, and the creatures that can attack

- **Goal:** Findings 2 and 3, KTD2.
- **Requirements:** R4, R31, R32.
- **Files:** `core/playable.py`, `scripts/verify_d20_rules.py`.
- **Test scenarios:** a Wolf built from the published bestiary carries its statistics
  unchanged, has no stated hand count, and holds its Bite with no hand committed; the
  Bite's to-hit is derived from the same ability and
  proficiency bonus the stat block prints, and the test asserts the printed number against the
  derived one so a transcription error goes red; the creature is proficient with it (p. 89); it
  is not a player character, so it dies at 0 (p. 17).
- **Execution note:** read p. 347 and p. 353 first and add their attack sentences to the
  verifier before writing a number. A stat block's to-hit is a derived figure, and the
  derivation is the check.
- **Verification:** `pytest`; `scripts/verify_d20_rules.py` against the document.

### U2. The character

- **Goal:** one level-1 player character, no class features, weapon and armour from
  `core.equipment`'s verified tables, skills from `core.skills`, spell slots and a spellcasting
  ability so U3 has a caster.
- **Requirements:** R31.
- **Dependencies:** none.
- **Files:** `core/playable.py`.
- **Test scenarios:** the character's armour class derives from a chosen base and bonuses
  (0077); every equipment id resolves to a verified entry; `is_player_character` is true so
  death saves apply.
- **Execution note:** ability scores are a choice, not a rule value — say so in the
  `rationale`, the way the fixture's docstring says its numbers are invented.

### U3. Three spells, and the proof they need no new shape

- **Goal:** Finding 4, KTD4.
- **Requirements:** R1, R4, R31, R32.
- **Dependencies:** U2.
- **Files:** `core/playable.py`, `scripts/verify_d20_rules.py`.
- **Candidates, none chosen until read:** an attack-roll cantrip, a save-or-damage cantrip,
  and a level-1 healing spell. For each, read the entry, record its page, and decide which of
  the inventory's shapes its effect is. **If a candidate's save clause is "half as much
  damage", it is `half-damage-on-save` and it is out** — pick another.
- **Test scenarios:** each spell is registered through `spell_resolvers` and nothing else; the
  cantrips expend no slot; the healing spell expends a level-1 slot and refuses a corpse
  (#438); each resolver names only shapes the inventory marks implemented, asserted by a test
  that reads `effect_shapes.json` rather than a list written beside the resolvers.
- **Verification:** `pytest`; verifier rows for every spell sentence relied on.

### U4. The catalogue, the set, and the console script

- **Goal:** Findings 5 and 6, KTD1, KTD5, KTD6.
- **Requirements:** R6, R33, R34.
- **Dependencies:** U1–U3.
- **Files:** `core/playable.py`, `adapters/cli.py`, `pyproject.toml`,
  `tests/test_core_has_no_runtime_dependencies.py` (unchanged, and it must stay green).
- **Test scenarios:** `playable_ruleset()` loads through `load_ruleset` and refuses nothing;
  every catalogue row is `Grounding.CITED`; a no-test declaration of an attack is challenged;
  `main` constructs and does not adjudicate; `[project].dependencies` is still empty.
- **Verification:** `pytest`; a scripted end-to-end run through the console script's own
  construction path, not only through `Session`.

### U5. The recall protocol, the stale sentences, and the stamp

- **Goal:** KTD3, Finding 7, R17.
- **Dependencies:** U1–U4.
- **Files:** `docs/recall-protocol.md`, `tests/fixtures/__init__.py`, `core/turn_span.py`,
  0049, `README.md`, `src/srd_rules_engine/__init__.py`.
- **The protocol states:** who runs it (a person with a model in a fresh context), what the
  model is given (the console script's output and nothing from this tree), what is committed
  as evidence (ledger, report, transcript), and that the answer is recorded in whichever
  direction the data supports — a skipped rule is a result, and a green report is not the bar
  (`Report.not_measured`, #197).
- **Verification:** full gate green; README's build line says what shipped and that coverage
  did not move.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — every existing row plus
  the attack sentences for each fielded creature and every spell sentence relied on.
- `scripts/prove_guard_red.sh` for U1's derived-to-hit check, U3's shape-reads-the-inventory
  check, and U4's cited-only check.
- `scripts/prove_against_base.sh main tests/test_playable.py` — and because the module is new,
  every assertion is additionally proved by corrupting the behaviour it guards and watching its
  own test go red, per `AGENTS.md`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- `srd` starts a session over SRD-provenance rules, two creatures that can attack, and a
  character who can cast three spells, with no dependency installed.
- Every number in the set is asserted in the verifier, and a transcription error in a to-hit
  goes red.
- The catalogue challenges a skipped attack roll, and every row is `cited`.
- The protocol is committed and #403's blocker line is replaced with a pointer to it.
- #472 closed with the PR that carried this plan; the PR that builds U1–U5 closes #475 and
  records on #21 that its blocker line names two closed gates.
- The README says coverage stood still and why.

## Risks

- **Finding 4 fails on a candidate.** Mitigated by KTD4: swap the spell, do not build the
  shape. The stop condition names the case where no simple spell of a kind exists.
- **A creature in two places drifts.** The bestiary and the playable set cite the same page;
  U1's test builds from the published bestiary rather than from copied statistics, so the only
  duplicated values are the attack line's.
- **The console script makes the library look like a game.** It is one: that is the point, and
  the CLI docstring's *"there is nothing to play"* paragraph is rewritten to say what there is.
- **The recall run is the thing that matters and it is not in this PR.** By design (KTD3), and
  the protocol is what makes the run repeatable by someone who was not here.
