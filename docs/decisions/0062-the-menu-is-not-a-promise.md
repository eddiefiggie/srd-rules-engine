# 0062 — The menu is not a promise

- **Status:** Accepted, 2026-08-30
- **Settles:** [#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245), and a
  preparation gap found beside it
- **Requirements:** R1, R15, R18
- **Related:** [0038 — a spell is data the caster carries](0038-a-spell-is-data-the-caster-carries.md),
  clause 2; [0039 — equipment is what a creature holds, wears and carries](0039-equipment-is-what-a-creature-holds-wears-and-carries.md),
  clause 4; [0052](0052-the-exit-is-built-before-the-entrance.md) and
  [0057](0057-prone-crawls-or-stands.md), where the same pattern was caught twice before

## Context

> p. 105, *Components*: If the spellcaster can't provide one or more of a spell's components,
> the spellcaster can't cast the spell.

`core.spellcasting.component_refusal` has answered that since #257 — Somatic's hand, Material's
*free* hand, the one hand that serves both, the Pouch and the Focus. **It had exactly one
caller**: `legal_actions`, which drops a spell the caster cannot provide for.

So the rule was enforced by the *menu* and by nothing else. A caller reaching adjudication
without consulting the read surface cast the spell anyway — and AGENTS.md already names that
consumer: "a consumer calling adjudication directly gets outcome authority without skip
prevention."

**p. 104's preparation had the identical shape**, one screen away in the same function.
`legal_actions` has checked `spell.rule_id not in actor.prepared` since #249; `spell_resolver`
never did. It was found by reading the one while fixing the other.

## Decision

1. **Both rules are asked in the resolver as well as at the offer**, through the same
   functions, so the two answers cannot disagree about which hand is free or what is prepared.

2. **The refusal raises**, as every other resolver refusal here does. A quiet rejection would
   let an impossible cast pass for one that merely failed.

3. **The offer keeps its check.** R18 asks for legality to be *computable* rather than
   checkable afterwards, so a spell that cannot be cast must not appear on the menu — and the
   resolver's refusal is not a substitute for that, it is the floor under it.

## Why

### Four instances in one session, and none found by a guard

The pattern is: a rule computed once, consumed at the read surface, and absent from the
adjudication path.

| rule | offered | refused |
|---|---|---|
| p. 90's Push, bounded at 10 feet | menu | added in 0055 |
| p. 182's escape check, needing an escape DC | menu | added in 0052 |
| p. 186's righting, needing the movement to spend | menu | added in 0057 |
| p. 105's components, p. 104's preparation | menu | added here |

Every one was found by a person writing a test or reading a neighbouring function. Nothing
mechanical looks for a predicate the read surface consults and the resolver does not, and the
two live in different modules by design — `legal_actions` decides legality, resolvers decide
outcomes, and the overlap is exactly this class of rule.

**A guard is plausible and is not built here**: the shapes differ enough (a helper, a set
membership, a bound on a declared number) that a walk would need to know which predicates are
rules. It is filed as [#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365) rather
than attempted at the end of a change about spells.

## Consequences

- **#245 closes.** Its stated blocker — no equipment model — was removed by 0039, and the
  check has existed since #257; what was missing was the second call site.
- **No coverage figure moves, and no clause count either.** `spellcasting-focus` was already
  claimed and correctly: the shape resolved. This is the third kind of gap the instruments
  cannot see, after 0058's unread field and 0061's unenforced clause — a rule enforced in one
  of the two places it belongs.
- **#19's umbrella is one slice shorter**, with #245 and #249 now closed and #246, #247, #250
  and #253 open.

## Evidence

- p. 105 — the components sentence, and the difference between Somatic's hand and Material's
  *free* hand, already transcribed in `component_refusal`.
- p. 104 — "you must have the spell prepared in your mind".

## Status of implementation

**Every clause is built** by [#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245).

| Clause | State |
|---|---|
| 1 — asked in both places, through one function | **Built.** `spell_resolver`, asserted from both sides |
| 2 — the refusal raises | **Built.** Asserted with `pytest.raises` |
| 3 — the offer keeps its check | **Built.** Asserted by dropping the menu check and going red |
