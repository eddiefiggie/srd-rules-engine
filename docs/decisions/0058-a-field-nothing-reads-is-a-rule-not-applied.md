# 0058 — A field nothing reads is a rule modelled and not applied

- **Status:** Accepted, 2026-08-30
- **Settles:** [#357](https://github.com/eddiefiggie/srd-rules-engine/issues/357)
- **Requirements:** R14, R17, R18, R32
- **Related:** [#356](https://github.com/eddiefiggie/srd-rules-engine/issues/356), which this
  is the first evidence for; [0054 — a save is rolled by a creature](0054-a-save-is-rolled-by-a-creature.md),
  which was the same shape found by accident;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  clause 1

## Context

`ConditionEffects` is transcribed from the glossary field by field. **Seven of its fields were
populated and read by nothing in `src/`**, every one on a condition marked `implemented: true`,
and **not one named in `unenforced_clauses`** — so both of R17's instruments reported the rule
as present.

They were found by a guard proposed in
[#356](https://github.com/eddiefiggie/srd-rules-engine/issues/356) and run once by hand: walk
the AST of every module, collect attribute **reads** of the dataclass's field names, and
compare. [#344](https://github.com/eddiefiggie/srd-rules-engine/issues/344) had been an eighth
until it was fixed, and it was found by accident rather than by anything.

## Decision

1. **The guard ships**, as `test_every_condition_effect_is_read_or_disclosed`. Every field is
   read by something or named in `unenforced_clauses`, and a third state fails the build.

   It collects **reads** and not keyword arguments. `ConditionEffects(cannot_speak=True)` in
   `EFFECTS` is the field being *populated*, which is exactly the state being looked for — a
   walk that counted it would have found nothing wrong with any of the seven.

2. **Three are built**, the two that change outcomes and the Immunity beside one of them:

   - **pp. 186, 191, Automatic Critical Hits.** `D20Test.critical_on_hit`, set by the attack
     resolver when the target holds the condition **and** the attacker is within 5 feet.
   - **p. 186, Resistance to all damage.** `Combatant.effective_defences`, composed with what
     the creature already had rather than replacing it.
   - **p. 186, Immunity to the Poisoned condition.** `with_condition` returns the state
     unchanged.

3. **Four are disclosed**, because each waits on something that does not exist: the two
   Initiative clauses ([#359](https://github.com/eddiefiggie/srd-rules-engine/issues/359)), and
   speech and the two sense-check flags
   ([#360](https://github.com/eddiefiggie/srd-rules-engine/issues/360)).

4. **The critical is on the `D20Test`, not on the result**, because it is known before the dice
   are thrown: it is a fact about the target and the distance, and the roll only decides whether
   the attack hits at all.

5. **A hit, and only a hit.** p. 186 says "any attack roll that **hits** you", so a miss is not
   upgraded and a natural 1 is untouched — p. 7 misses "regardless of any modifiers or the
   target's AC". The upgrade is applied after the outcome for that reason, and never downgrades
   a natural 20 that is already critical.

6. **An unmeasurable distance does not upgrade the hit** (0030 clause 1). A Critical Hit doubles
   dice, so granting one on a distance the engine could not measure manufactures damage;
   withholding it only fails to double.

7. **Immunity to a condition is a no-op, not an error.** p. 183: an Immunity means the condition
   "doesn't affect you in any way", so a rule that tries to poison a statue is not a caller's
   mistake. The *same* state object is returned, because a no-op that rebuilt the encounter
   would move the generation and stale a read token for a change that did not happen (R19).

## Why

### The two that matter were silently costing damage

`auto_critical_within_5_feet` and `resistance_to_all_damage` change **outcomes**, not
probabilities. Every hit against a paralyzed or unconscious creature from within five feet was
dealing single dice where p. 186 doubles them, and every blow against a Petrified creature was
landing in full where p. 186 halves it. Both consequences were already wired — `core.d20.Critical`
and `Defences.resists_all` — and only the occasion was missing, which is the shape this
repository has now found six times.

### Two initiative clauses, two strings

Incapacitated gives Disadvantage on Initiative and Invisible gives Advantage. They are one *gap*
and two *clauses*, and the pin refuses a repeated string — correctly, because "a repeated one is
two claims about one gap". So they are named separately, which also makes the diff say which
condition lost which.

## Consequences

- **Eight conditions now disclose something**, up from five, and none of the three new ones is
  a regression: each names a rule that was already unbuilt and was previously invisible.
- **No coverage figure moves — 116 of 210** — which is #356's whole point, now with a guard
  behind it rather than an observation.
- **Four clauses added to `scripts/verify_d20_rules.py`**, which reports 278 verified. p. 183's
  Immunity sentence was written from memory, failed, and was corrected against the page.
- **A tautology was written and removed.** `assert after is encounter(petrified) or True` is
  true by construction; it now asserts the *same object* is returned, which is the R19 property
  clause 7 is about.

## Evidence

- pp. 186, 191 — Automatic Critical Hits, and that it is a *hit* within 5 feet.
- p. 186 — Petrified's Resistance to all damage and its Immunity to the Poisoned condition.
- p. 183 — that an Immunity means the thing "doesn't affect you in any way".

## Status of implementation

**Every clause is built** by [#357](https://github.com/eddiefiggie/srd-rules-engine/issues/357).

| Clause | State |
|---|---|
| 1 — the guard | **Built.** `test_every_condition_effect_is_read_or_disclosed`, proven red |
| 2 — three rules built | **Built.** `D20Test.critical_on_hit`, `Combatant.effective_defences`, `with_condition` |
| 3 — four disclosed | **Built as disclosures.** [#359](https://github.com/eddiefiggie/srd-rules-engine/issues/359) and [#360](https://github.com/eddiefiggie/srd-rules-engine/issues/360) hold the rules |
| 4 — on the test, not the result | **Built.** `core.d20.resolve` |
| 5 — a hit, and only a hit | **Built.** Asserted on a miss and on an ordinary hit |
| 6 — an unmeasurable distance does not upgrade | **Built.** `core.combat._hit_is_automatically_critical` |
| 7 — Immunity is a no-op returning the same state | **Built.** Asserted with `is` |
