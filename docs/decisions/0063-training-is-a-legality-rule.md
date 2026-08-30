# 0063 — Training is a legality rule, and it is by item id

- **Status:** Accepted, 2026-08-30
- **Settles:** [#247](https://github.com/eddiefiggie/srd-rules-engine/issues/247)
- **Requirements:** R15, R18, R31, R32
- **Related:** [0040 — a weapon is an item, and proficiency is the wielder's](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2, whose reasoning this reuses unchanged;
  [0039 — equipment is what a creature holds, wears and carries](0039-equipment-is-what-a-creature-holds-wears-and-carries.md),
  clause 3; [0062 — the menu is not a promise](0062-the-menu-is-not-a-promise.md)

## Context

> p. 104, *Casting in Armor*: You must have training with any armor you are wearing to cast
> spells while wearing it. You are otherwise too hampered by the armor for spellcasting.

#247 said the engine could not evaluate it because "nothing models **what a creature is
wearing**, and nothing models **armour training**". The first half went stale when 0039 built
`Carriage.WORN`; the second was still true.

p. 177 states the rule again and states two more drawbacks with it:

> Armor training allows you to use armor of a certain category without the following drawbacks.
> If you wear Light, Medium, or Heavy armor and lack training with it, you have Disadvantage on
> any D20 Test that involves Strength or Dexterity, and you can't cast spells. If you use a
> Shield and lack training with it, you don't gain its AC bonus.

## Decision

1. **`Combatant.armour_training` is a set of item ids**, and that is 0040 clause 2's reasoning
   unchanged: p. 19 grants training with "certain **categories** of armor", the categories live
   in pp. 93-97's tables, and those are content this repository does not ship (R31). The engine
   holds the resolved relation; a ruleset that knows the table expands it.

2. **`Item.is_armour` is a flag and not a category**, for the same reason. It is enough for
   p. 104's rule and deliberately not enough for p. 177's Shield clause, which needs the
   distinction back ([#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367)).

3. **Empty training refuses rather than grants.** A creature nobody trained cannot cast *while
   wearing armour*, and one wearing none is unaffected — so the default costs nothing to a
   caster who dresses like one.

4. **Worn only.** p. 104 says "any armor you are **wearing**", and armour in a pack hampers
   nobody. `is_armour` and `Carriage.WORN` are both required, which is why a worn robe is not
   armour and stowed plate is not worn.

5. **It is a legality rule, so the read surface answers it.** A caster in untrained armour is
   offered no spells at all. An engine that skipped it would be *confidently wrong* rather than
   incomplete, which is the distinction R18 exists for.

6. **And the resolver refuses too** — 0062's rule applied in the change after it rather than
   three builds later. Both call `untrained_armour`, so the offer and the refusal cannot
   disagree.

7. **Every untrained piece is named**, not the first. A caster in two is refused for two
   reasons and a ruling naming one would be half a record (R30).

8. **The other two drawbacks are disclosed** (#367) and not approximated.

## Why

### The Disadvantage is wider than it looks, and that is why it waits

"Any D20 Test that involves Strength or Dexterity" reaches attacks and ability checks as well as
saves. `D20Test.ability` exists since 0054 and is passed by the **six save sites only** — attack
rolls carry the ability in `Modifier.source` and checks vary — so a central rule would need the
field threaded through every test-building site first. That is 0054's work one level wider, and
it should be done once for whatever else needs it rather than for this clause alone.

### The Shield clause needs a subsystem nobody has filed

"You don't gain its AC bonus" needs the bonus to withhold, and Armour Class is a stored number
on the combatant rather than a derivation over what it wears. That dependency is real and was
not obvious from the sentence, so #367 states it — a reader reaching for `is_armour` expecting
it to be enough would find out the hard way.

## Consequences

- **`armor-training` becomes implemented**, 117 of 210.
- **Two new disclosures**, so the clause count rises from 17 to 19. That is 0061's figure
  working as described: a rise here is an honesty improvement, because both clauses were
  unbuilt and unnamed before this change.
- **`Item` gains its sixth field**, and the pin in `tests/test_equipment.py` records why.

## Evidence

- p. 104 — Casting in Armor, the flat prohibition.
- p. 177 — Armor Training, all three drawbacks.
- p. 19 — that training is granted by category, and by a class.

## Status of implementation

**Every clause is built** by [#247](https://github.com/eddiefiggie/srd-rules-engine/issues/247).

| Clause | State |
|---|---|
| 1 — training by item id | **Built.** `Combatant.armour_training` |
| 2 — `is_armour` is a flag | **Built.** The category stays out; the Shield clause is [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367) |
| 3 — empty refuses | **Built.** Asserted against a caster wearing nothing |
| 4 — worn only | **Built.** Asserted with stowed plate and a worn robe |
| 5 — the menu offers nothing | **Built.** `legal_actions` |
| 6 — the resolver refuses too | **Built.** `spell_resolver`, both through `untrained_armour` |
| 7 — every piece named | **Built.** Asserted with two |
| 8 — the other two disclosed | **Built as disclosures.** [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367) |
