# 0077 — Armour Class is a chosen base, plus bonuses

- **Status:** Accepted, 2026-08-30
- **Settles:** [#380](https://github.com/eddiefiggie/srd-rules-engine/issues/380)
- **Requirements:** R12, R15, R18, R31, R32
- **Related:** [0040 — a weapon is an item and proficiency is the wielder's](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2, whose by-item-id relation this reuses for armour training;
  [0076 — improvised is a use, not an object](0076-improvised-is-a-use-not-an-object.md) and
  [0075 — ties are a person's](0075-ties-are-a-persons-and-initiative-is-a-dexterity-check.md),
  whose decline-or-declare rule this applies a third time;
  [0039 — equipment is what a creature carries](0039-equipment-is-what-a-creature-carries.md),
  clause 2, which every new `Item` field has to pass

## Context

`Combatant.armour_class` is an `int` a caller supplies. Nothing derives it, so **nothing can
withhold a contribution to it** — and p. 177's Shield clause needs exactly that:

> If you use a Shield and lack training with it, you don't gain its AC bonus.

Disclosed as `untrained-shield-still-grants-ac` since [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367),
with the reason stated at the read surface: *"the clause needs a shield's AC bonus to withhold,
which nothing models: Armour Class is a stored number rather than a derivation over what is
worn."* A withheld bonus is not expressible against a total, because the engine does not know
what the total was built from.

#380 was filed as a `gate` with three questions it said had no default answer. **All three are
answered by the document**, which is the finding: the structure is stated on pp. 177 and 92 and
was never a design question at all.

## What the document says

p. 177, *Armor Class*:

> An Armor Class (AC) is the target number for an attack roll... **Your base AC calculation is
> 10 plus your Dexterity modifier. If a rule gives you another base AC calculation, you choose
> which calculation to use; you can't use more than one.**

p. 92:

> **One at a Time.** A creature can wear only one suit of armor at a time and wield only one
> Shield at a time.

> **Shield.** You gain the Armor Class benefit of a Shield only if you have training with it.

> A monster has training with any armor in its stat block.

And the armour table gives each entry a *base* — `11 + Dex modifier`, `14 + Dex modifier (max
2)`, a flat `16` — while the Shield gives `+2`.

## Decision

1. **AC is a chosen base plus bonuses**, and those are two different kinds of thing. p. 177
   makes base calculations **alternatives** — "you choose which calculation to use; you can't
   use more than one" — while a Shield is a bonus on top of whichever base won. An
   implementation that summed them would be adding what the document says to choose between.

2. **A base calculation is `flat + Dexterity, optionally capped`**, which is the shape every
   row of p. 92's table has and the shape p. 177's default has. `10 + Dex` uncapped,
   `14 + Dex (max 2)`, and `16` with no Dex are the same structure with different parameters —
   so the engine holds the structure and the ruleset supplies the numbers.

3. **The numbers are content and do not ship.** Padded Armor being `11 + Dex` is pp. 92-97,
   which this repository does not carry (R31), exactly as it carries no weapon table and no
   spell list. `Item` gains what an armour *contributes*, supplied by the ruleset.

4. **A supplied total survives, and the document is why.** p. 254 says a stat block provides
   Armor Class, and p. 92 says a monster has training with any armour in its stat block. A
   stat-block AC is therefore **not** an unverified number to be replaced — it is precisely
   "another base AC calculation" that p. 177 permits, arriving from the ruleset. So
   `Combatant.armour_class` stays, and gains a derivation beside it rather than being replaced
   by one.

5. **`effective_armour_class` is the derivation**, named for `effective_speeds` and
   `effective_defences` and working the way they do: the stored field is what the creature
   *has*, and this is what an attack roll meets.

6. **The choice among bases is the creature's and is stated, not computed.** p. 177 says "you
   choose". The engine must not pick the highest — that is a decision the document assigns,
   and taking the best available is the kind of helpful invention this repository refuses.
   It arrives as state on the combatant, the way `mode` arrives on a move.

   **This is the third instance of the decline-or-declare rule** 0075 and 0076 established
   together, and it lands on the third branch: an attack must resolve against *an* AC, so
   declining is impossible; but unlike an initiative tie, the choice is one a caller can state
   in advance. **So it is neither refused nor conventional — it is asked for once and stored.**

7. **The Shield is a bonus, conditional on training**, which closes
   [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367)'s Shield half. Training
   is already held by item id (0040 clause 2), so the clause needs no armour *category* —
   which is what made it look blocked on content it will never have.

8. **One suit and one Shield are refused at the state transition**, beside the refusals
   `with_movement` already carries (0056 clause 1). A refusal produces no result, so R1 is
   untouched.

9. **`armour_class` stops being read directly by the attack path.** That is the change with
   reach: `core.combat` reads it in two places and the read surface reports it in several, and
   every one of them wants the derived value.

## Why

### The gate's three questions were answered on the page

#380 asked what the base is, whether a supplied total survives, and what R31 permits, and said
each had no default answer. Reading pp. 177 and 92 answered all three in about ten minutes —
which is the standing rule this repository added one build earlier, arriving immediately:
*accuracy is not provenance, and a quotation is not an assertion.*

Worth recording plainly: **the gate label was right and its premise was wrong.** The design was
undecided because nobody had read the pages, not because the pages left it open. A `gate` that
survives contact with the document is a different thing from one that does not, and this was
the second kind.

### Base-versus-bonus is the whole of the modelling

Almost every wrong implementation of AC comes from treating armour as a bonus. The table
invites it — `+2` for a Shield sits in the same column as `11 + Dex modifier` — and p. 177 is
the sentence that forbids it. Getting this wrong is not a rounding error: a character in Plate
with a Shield is 20, and an engine that added a base to a base makes them 28.

### Why the choice is stored rather than offered

R18's read surface enumerates what is *legal*, and a base calculation is not an action. The
creature is not choosing each turn; it is wearing what it is wearing and using the calculation
it uses. Storing it keeps the choice explicit and the derivation pure, and it means a ruleset
that states one base — the overwhelming case — states nothing extra.

## Status of implementation

**Nothing here is built.** This record settles the gate and the work follows, filed rather than
described, per `AGENTS.md`: a gate closes by producing a record, and the record's unbuilt
clauses are filed at that moment because a *closed* gate issue reads as finished work.

| Clause | Held by |
|---|---|
| 1, 2, 3 — base-plus-bonus, its shape, and the numbers staying content | [#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393) |
| 4, 5 — the supplied total survives; `effective_armour_class` | [#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393) |
| 6 — the creature's stated choice among bases | [#394](https://github.com/eddiefiggie/srd-rules-engine/issues/394) |
| 7 — the Shield's bonus, withheld without training | [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367) |
| 8 — one suit, one Shield, refused at the transition | [#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393) |
| 9 — the attack path reads the derived value | [#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393) |

The four sentences this rests on are asserted in `scripts/verify_d20_rules.py`, which now
carries 295 clauses. That is the part of this workload that does not need re-doing: whoever
builds #393 does not re-read pp. 177 and 92, and cannot quietly disagree with them.

`untrained-shield-still-grants-ac` **stays disclosed** until #367 retires it, and the
disclosure's stated reason is now wrong in the way 0060 and 0071 describe — it says the bonus
"needs a derivation over what is worn, which nothing models", and what is missing after this
record is the derivation being *built*, not designed. #393 carries the correction.
