# 0080 — Dehydration is bookkeeping, and Malnutrition is two rules

- **Status:** Accepted, 2026-08-30
- **Settles:** the buildable half of [#315](https://github.com/eddiefiggie/srd-rules-engine/issues/315)
- **Requirements:** R1, R4, R15, R31, R32
- **Related:** [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  clause 8, which drew this split and got half of it wrong;
  [0028 — a level carries the rule that caused it](0028-a-level-carries-the-rule-that-caused-it.md),
  whose lock was built ahead of this hazard;
  [0051 — a size is stated, or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md),
  which is why an unsized creature is refused

## Context

p. 181:

> A creature requires an amount of water per day based on its size... A creature that drinks
> **less than half** the required water for a day gains 1 Exhaustion level at the day's end.
> Exhaustion caused by dehydration can't be removed until the creature drinks the full amount
> of water required for a day.

0027 clause 8 split the two remaining hazards: *"Dehydration is bookkeeping; Malnutrition is
an outcome; they do not share an implementation."* Both of the things that used to block
Dehydration were built years of builds ago — `EffectKind.EXHAUSTION_GAINED` and
`with_exhaustion` (#178), and level provenance (0028) — and #140 closed at 3 of 5, leaving
these two tracked by nothing until #315.

## Decision

1. **Dehydration is a state transition, not an adjudication.** p. 181 inflicts the level
   outright; there is no die, so R1 and R4 are untouched by putting it in
   `EncounterState.with_day_ended` rather than behind the adjudication entry point.

2. **The caller states what each creature drank.** A narrative fact only the agent holds,
   which is the contract `with_time_passed` already states for how much time passed. The
   engine decides every consequence of it.

3. **Only the creatures named are considered.** A day ending is not a claim about everybody in
   the encounter, and defaulting the rest to zero would dehydrate every bystander.

4. **A creature of unknown size is refused, not skipped.** The requirement is read from a size
   table, so a sizeless creature has nothing to have drunk less than half of — 0051's refusal
   rather than a comparison against a Medium nobody stated. Skipping it would report a day in
   which nobody was thirsty.

5. **The table is `Fraction`, not `float`.** Tiny needs a quarter gallon and the rule turns on
   *half* of it — an eighth. Neither is representable in binary floating point, and a hazard
   firing on a rounding error is indistinguishable from one firing on the rule.

6. **The table lives in `core.size`**, beside p. 178's carrying capacity, because `core.state`
   must reach it and `core.hazards` imports `core.state`. Re-exported from `core.hazards`,
   where a reader looking for a hazard looks.

7. **Malnutrition is not built**, and the occasion it needs is filed as a `gate`:
   [#399](https://github.com/eddiefiggie/srd-rules-engine/issues/399).

## Why

### 0027 clause 8 was half wrong, and reading p. 185 is what showed it

The clause says Malnutrition **is** an outcome. p. 185 states two rules:

> A creature that eats but consumes less than half the required food for a day **must succeed
> on a DC 10 Constitution saving throw** or gain 1 Exhaustion level at the day's end. A
> creature that eats nothing for 5 days **automatically gains 1 Exhaustion level** at the end
> of the fifth day as well as an additional level at each subsequent day without food.

The first is an outcome. **The second is bookkeeping**, exactly like Dehydration — no die, no
save, a level at a day's end. So Malnutrition is not the counterpart to Dehydration; it is
both kinds at once, and its bookkeeping half is blocked on something different from its
outcome half: it needs consecutive days without food *counted*, which is campaign-axis state
nothing holds.

#315 inherited the clause's framing and repeated it. Neither is wrong about what to build
first; both are wrong that the split is clean. Recorded here because the next person to reach
for Malnutrition will otherwise look for one blocker and find two.

### A lock that predates the thing it locks

`LOCKED_EXHAUSTION_RULES` has held `DEHYDRATION_RULE_ID` since 0028 clause 3, with a comment
saying the hazards were unbuilt and *"when one is, its rule id must be this string or the lock
silently stops applying"*. Dehydration is the first hazard to put a level behind it, and the
lock worked on the first run.

That is worth recording as a *success* of a habit this repository usually records failures of:
the machinery was built to a shape the document described rather than to the caller that
existed, and four builds later the caller arrived and fitted.

### Why the refusals, and why not a fifth occasion

Clauses 3 and 4 are both refusals of the same kind — the engine declines to answer for a
creature the caller has not described. That is [0079](0079-a-second-base-refuses-rather-than-being-picked-between.md)'s
rule applied again: declining is possible here, because a day's end that cannot be computed is
a day the ruleset has not finished stating.

What this deliberately does **not** do is invent an occasion. `with_day_ended` produces no
`Ruling` and throws no die, so it is not the fifth adjudicating occasion — it is a sibling of
`with_time_passed`. The fifth occasion is a real design question and it is #399's, not this
record's.

## Status of implementation

| Clause | State |
|---|---|
| 1 — a state transition | **Built.** `EncounterState.with_day_ended` |
| 2 — the caller states consumption | **Built** |
| 3 — only the named creatures | **Built**, and proved by widening it to every combatant |
| 4 — unknown size refuses | **Built** |
| 5 — `Fraction` | **Built.** `core.size.WATER_PER_DAY` |
| 6 — the table's home | **Built**, and re-exported from `core.hazards` |
| 7 — Malnutrition | **Not built.** [#399](https://github.com/eddiefiggie/srd-rules-engine/issues/399) holds the occasion; the starvation half additionally needs days without food counted |

The `dehydration` shape is **claimed**; `malnutrition` is not. `scripts/verify_d20_rules.py`
carries 300 clauses, including p. 185's — asserted although unbuilt, so whoever takes #399
does not re-read it and cannot quietly disagree with it.

### Evidence

Five corruption proofs, each red on the assertion written for it.

| Corruption | Went red on |
|---|---|
| `<` widened to `<=` | `test_less_than_half_is_strict`, `test_the_requirement_is_exact_rather_than_floating` |
| the level given a generic rule id | `test_the_level_names_the_rule_that_caused_it`, and the Long Rest lock |
| the unknown-size refusal disabled | `test_a_creature_of_unknown_size_is_refused_rather_than_skipped` |
| the loop widened to every combatant | `test_only_the_creatures_named_are_considered` |
| Huge's requirement changed to a gallon | `test_size_decides_the_requirement`, `test_the_water_table_is_p181s` |

The second is the one that matters most: it goes red on the Long Rest lock as well as on the
provenance assertion, which is the pairing 0028 built the lock for.
