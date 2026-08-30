# 0059 — Initiative draws a pair for everyone

- **Status:** Accepted, 2026-08-30
- **Settles:** [#359](https://github.com/eddiefiggie/srd-rules-engine/issues/359)
- **Requirements:** R4, R14, R18, R32
- **Related:** [0058 — a field nothing reads is a rule modelled and not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md),
  which disclosed this and deferred it; [#82](https://github.com/eddiefiggie/srd-rules-engine/issues/82),
  whose band capacities exist because of the failure this change had to avoid repeating

## Context

> p. 184, *Incapacitated*: You have **Disadvantage** on Initiative.
>
> p. 184, *Invisible*: You have **Advantage** on Initiative.

`ConditionEffects.initiative` held both and `core.combat.initiative_order` read neither — it
rolled one d20 per combatant, added an ability modifier, and consulted nothing else. Two of the
seven fields 0058 found.

0058 built three of the seven and disclosed four. This one was disclosed rather than built
because Advantage means **two dice**, and one die per combatant is not a modifier that was
forgotten — it is the seed layout.

## Options considered

**Option 1 — draw the pair only for the creatures that need one.** Rejected, and it is the
option that arrives by accident. It makes a combatant's seed offset depend on the *conditions of
the combatants before it*: reproducible, and fragile in exactly the way #82 was, where a run
walked out of its band and silently agreed with another band's dice. A creature gaining
Incapacitated mid-encounter would move every later creature's initiative.

**Option 2 — two dice for everyone, always.** Chosen. The layout is uniform, one creature's
offset never depends on another's state, and the second die is drawn and unused where nothing
modifies the roll.

## Decision

1. **`DICE_PER_COMBATANT = 2`, drawn for every combatant.** Creature *i* reads
   `faces[2i:2i+2]`.

2. **The pick goes through `core.d20.pick`**, which is public since this change. Initiative is
   a second roll that needs "higher for Advantage, lower for Disadvantage" and does not go
   through `D20Test`; two copies of that rule would be two chances to answer it differently,
   which is the reason `_cancel` was extracted in the first place.

3. **`Conditions.initiative_advantage` aggregates through `_combine`**, so a creature that is
   both Incapacitated and Invisible rolls flat — p. 8's cancellation, not a third rule.

4. **The band states the ceiling rather than aliasing past it.** `roll` checks the run against
   the band it starts in, so 256 slots at two dice each refuses the 129th combatant by name.

5. **The modifier is added after the pick**, which is only distinguishable because the two dice
   differ.

## Why

### The seed layout moved, and the fixtures said so themselves

Every initiative result changed, because the dice a combatant reads moved. Two tests failed and
both failure messages were the ones somebody had written for this: `opening_state` refused seed
4 by name — *"Pick another seed — the order derives from the seed, so a literal stops meaning
what it says the moment the derivation moves"* — and the layout assertion in `test_combat`
compared against `faces[1]` where the second creature now reads `faces[2]`.

Nothing records initiative in the ledger, so no history was rewritten.

### A seed that cannot discriminate makes a test pass for the wrong reason

The first draft used one seed for both directions and it could not tell Disadvantage from no
condition at all: seed 7's first pair is `(11, 13)`, and `min` of that is `11` — which is
exactly what a creature holding nothing would have rolled. The assertion was `rolled == min(faces)`
and it was true for the wrong reason.

So each direction now uses a seed whose pair runs the right way, and each test asserts the
discriminating property first — `min(faces) != faces[0]`, or it cannot distinguish anything.
That check is the test's own guard against the fixture drifting under it.

## Consequences

- **Both disclosures retire**, in the change that builds their rules. They were two strings
  rather than one because the pin refuses a repeated clause, and that was right: sharing one
  would have made a single removal look like both.
- **Two clauses retire, and no condition stops disclosing.** Incapacitated keeps
  `cannot-speak` and Invisible keeps `concealed-from-effects-requiring-sight`, so the
  clause count falls from 12 to 10 while the condition count stays at eight.

  *This line said "six conditions still disclose something, down from eight" when the
  record shipped, and both halves were wrong: the number, and which of the two figures
  moved. Corrected on 2026-08-30 after an audit counted the conditions at each commit.
  0060 is about a disclosure being wrong about **why**; this is a record being wrong about
  **how many**, and neither is caught by anything but a person.*
- **`core.d20.pick` is public**, and `DICE_PER_COMBATANT` joins `core.combat`'s pinned
  constants — a deliberate diff, and a seed-layout decision rather than a rule value.
- **One test states a property rather than guarding an implementation**, and says so:
  `test_the_unused_die_is_still_drawn` is true by construction under this layout and no
  single-line corruption violates it. It is kept because it is what would fail if somebody
  replaced the layout with Option 1, and the docstring is explicit that the layout itself is
  held by its neighbour.
- **No coverage figure moves — 116 of 210.** The fourth record to say so, and #356 now holds
  the general point.

## Evidence

- p. 184 — Incapacitated's Disadvantage and Invisible's Advantage on Initiative.
- p. 8 — that sources on opposite sides cancel.

## Status of implementation

**Every clause is built** by [#359](https://github.com/eddiefiggie/srd-rules-engine/issues/359).

| Clause | State |
|---|---|
| 1 — two dice for everyone | **Built.** `DICE_PER_COMBATANT`, asserted against the raw band |
| 2 — one picker | **Built.** `core.d20.pick`, public |
| 3 — cancellation through `_combine` | **Built.** Asserted with both conditions held |
| 4 — the band states the ceiling | **Built.** Asserted at 128 and 129 combatants |
| 5 — modifier after the pick | **Built.** Asserted with a +3 Dexterity and Advantage |
