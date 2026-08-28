---
title: Cast a spell - Plan
type: feat
date: 2026-08-28
topic: cast-a-spell
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
origin: https://github.com/eddiefiggie/srd-rules-engine/issues/248
---

# Cast a spell - Plan

## Goal Capsule

- **Objective:** Build [0038](../decisions/0038-a-spell-is-data-the-caster-carries.md), so a
  caster can cast a spell through the one adjudication entry point and the engine spends what
  casting costs.
- **Headline finding:** **this is the first time an adjudication spends anything.**
  `ActionBudget.spend` has no caller outside `dodging()`, so an attack does not cost the
  Action. A slot is not a new use of an existing mechanism — the mechanism does not exist, and
  `Proposal` has nowhere to put a cost that is not an outcome. That is 0038 clause 6 and it is
  the piece most likely to be underestimated.
- **The shape:** a `Spell` the caster carries, a wrapper resolver the engine owns, and an
  `always` branch for what casting costs regardless of how the roll came out.
- **Product authority:** `AGENTS.md`, then `docs/decisions/`. p. 104, p. 105 and p. 185 were
  read whole from `/path/to/SRD_CC_v5.2.1.pdf` (R31); 0038 carries the reasoning and is not
  re-litigated here.
- **Stop conditions:** Stop and ask if the engine would have to read a spell's description to
  decide anything (R20), if `legal_actions` would need an argument beyond state (0026 clause
  1), or if a cost cannot be applied without the resolver's cooperation (0038 clause 3).
- **Tail ownership:** One PR. Every clause 0038 states that this does not build is filed
  before it merges.

---

## What the Investigation Found

**Finding 1 — nothing spends anything, so the cost mechanism is new.** `ActionBudget.spend`
is called by `dodging()` and by tests. `_apply` walks a *selected branch*, and every effect
kind it knows is a consequence of the roll. A slot is spent because the casting happened, so
it belongs in neither `outcome` nor `on_success`.

**Finding 2 — `EffectKind.EXHAUSTION_GAINED` already solved "which rule caused this".** 0028
clause 1 takes the rule id from the *ruling* rather than from a payload field, "so there is no
way for an effect to claim a source its ruling did not have". Beginning Concentration needs
exactly that: what the Concentration is *on* is the spell's rule id, which is the ruling's own.
So 0038 clause 7 needs no new field, and `Concentration.spell` becoming a rule id is a rename
rather than a redesign.

**Finding 3 — one-slot-per-turn is `discharged`-shaped and must not be `discharged`.** The
cardinality matches — once per turn, cleared on advance — but the *meaning* does not:
`discharged` records that an **obligation was met**, and this records that a **resource was
spent**. A guard reading one for the other answers a different question, and 0036 clause 3 is
the record of what happens when one structure carries two meanings. Its own field, cleared in
the same place for a different reason.

**Finding 4 — legality has to account for three things the read surface has never asked.**
Whether the casting time's action is still available (p. 185), whether a slot can pay
(`payable_by`), and whether a slot has already gone this turn (p. 105). A cantrip passes the
second and third trivially, which is p. 104's point and not a special case.

---

## Key Technical Decisions

**KTD1 — `Proposal.always`, applied in addition to the selected branch.** 0038 clause 6.
`_apply` walks it first, so a `when` predicate in the branch can read what a cost settled —
and so the ledger records the cost before the consequence, which is the order they happened in.

**KTD2 — The only documented way to register a spell is `spell_resolvers`, which wraps.**
0038 clause 3's guard, built as a construction-time invariant rather than a runtime check:
the registry helper takes the ruleset's *effects* resolver and returns the wrapper keyed by
rule id, so an unwrapped resolver cannot be registered through the path the docs describe.
This is the shape that has worked three times this month — `Combatant.__post_init__`,
`EncounterState.__post_init__`, and 0036's shared drain.

**KTD3 — The action key carries the slot level, and a parser reads it back.**
`cast:<rule_id>:<level>`, with level 0 meaning "no slot" (p. 104's four slotless routes, of
which this builds Cantrips). `attack_key`/`attack_target` is the existing shape.

**KTD4 — Casting time is an engine field but only three of its values are built.** p. 105
names an action, a Bonus Action, a Reaction, and 1 minute or more. The fourth is
[#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250) and is **refused** rather
than silently treated as an action — an engine that cast a 10-minute spell instantly would be
wrong in the direction nobody notices.

**KTD5 — `Spell` holds no components and no school.** 0038 clause 2. Not gaps; the school has
no rules (p. 105) and components have nothing to read them
([#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245),
[#246](https://github.com/eddiefiggie/srd-rules-engine/issues/246)). Both disclosed in the
module (R32).

---

## Scope Boundaries

**In scope:** `Spell` and `CastingTime`; the spells a caster carries; `spell_resolver` and
`spell_resolvers`; `Proposal.always`; `EffectKind.SPELL_SLOT_EXPENDED` and
`CONCENTRATION_BEGUN` with their transitions; one-slot-per-turn; the Magic action for casting;
`legal_actions` offering one entry per payable level; `Concentration.spell` becoming a rule id;
the R32 disclosures; guards and proofs; the build stamp.

### Deferred to Follow-Up Work

- **Preparation** — [#249](https://github.com/eddiefiggie/srd-rules-engine/issues/249). The
  list this builds is "what this creature can cast", which 0038 clause 8 says is the *one*
  list preparation later refines.
- **Longer casting times** — [#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250),
  refused rather than approximated (KTD4).
- **Components and Casting in Armor** — #245, #246,
  [#247](https://github.com/eddiefiggie/srd-rules-engine/issues/247). Disclosed here.
- **The Magic action as a *general* action**, for features and magic items that require one
  (p. 185). This builds the casting half only. **File before merge** — p. 185 states two uses
  and this serves one, which is exactly the kind of half-built entry a later audit reads as
  finished.

**Out of scope:** any spell content, now or ever (R31).

---

## Implementation Units

### U1. The cost mechanism

- **Goal:** Findings 1 and 3. `Proposal.always`, the two effect kinds, their state
  transitions, and the once-per-turn record.
- **Requirements:** R1, R5.
- **Files:** `core/adjudicate.py`, `core/state.py`.
- **Test scenarios:** an `always` effect applies on success and on failure and on a testless
  proposal; it is recorded in the ledger; a slot is spent once; the once-per-turn record
  clears on `advanced_turn` and is not `discharged`.
- **Verification:** `pytest`, `mypy` green.

### U2. A spell, and the wrapper that owns its costs

- **Goal:** 0038 clauses 1, 2, 3, 5, 7.
- **Requirements:** R1, R4, R31.
- **Dependencies:** U1.
- **Files:** `core/spellcasting.py`, `core/state.py`.
- **Test scenarios:** a cantrip expends no slot; a levelled spell expends the declared one; a
  concentration spell begins Concentration naming the **rule id**; the wrapper refuses a slot
  level that cannot pay; `spell_resolvers` wraps, and the wrapper is what gets registered.
- **Execution note:** write the cantrip case first. An implementation that couples casting to
  slot expenditure passes every levelled test.
- **Verification:** `pytest` green; no spell content anywhere in `src/`.

### U3. The menu

- **Goal:** 0038 clause 4 and Finding 4.
- **Requirements:** R18.
- **Dependencies:** U2.
- **Files:** `core/read_surface.py`, `adapters/surface.py`.
- **Test scenarios:** one entry per payable level; a cantrip offered with no slot; nothing
  offered once the Action is spent; nothing levelled offered once a slot has gone this turn;
  a cantrip still offered then.
- **Verification:** `pytest` green; `legal_actions` still takes state and `actor_id` only.

### U4. Disclosures, figures, and the stamp

- **Goal:** R32, R17.
- **Dependencies:** U1-U3.
- **Files:** `core/spellcasting.py`, `README.md`, `src/srd_rules_engine/__init__.py`, 0038.
- **Verification:** full gate green; 0038's clause table updated to what landed.

---

## Verification Contract

- `pytest && ruff check . && ruff format --check . && mypy`.
- `python scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf` — all clauses, plus new rows
  for p. 105's one-slot-per-turn sentence and p. 104's *Casting without Slots*.
- `scripts/prove_guard_red.sh` for U1's, U2's and U3's guards.
- `scripts/prove_against_base.sh main tests/test_casting.py`.
- `python scripts/check_build_stamp_advanced.py main`.

## Definition of Done

- A caster casts a spell through the one entry point; the engine spends the slot and the
  action, and the ruleset decides only what the spell does.
- A cantrip costs no slot. A concentration spell starts Concentration naming a rule id.
- One slot per turn, in its own structure, cleared with the turn.
- The read surface offers one entry per payable level and nothing it cannot pay for.
- A resolver registered without the wrapper cannot reach the engine through the documented path.
- Components, armour and longer casts are disclosed; the general Magic action is filed.
- #248 and #241 closed; #235 item 1 closed; coverage moves and the README says by how much.

## Risks

- **`Proposal.always` is a fifth way to state effects**, and the type is getting wide. 0038
  accepted it; the alternative escapes the next branch someone adds.
- **The wrapper is indirection**, and a consumer who reaches past `spell_resolvers` gets a
  free spell. Mitigated by that being the only documented path and by a guard.
- **Coverage will move**, and the figure must be re-derived rather than guessed.
