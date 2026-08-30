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

| Clause | State |
|---|---|
| 1, 2, 3 — base-plus-bonus, its shape, the numbers staying content | **Built** by [#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393). `ArmourClassBase`, `Item.armour_class_base`, `Item.armour_class_bonus` |
| 4 — the supplied total survives | **Built, and corrected while building** — see below |
| 5 — `effective_armour_class` | **Built.** `Combatant.effective_armour_class`, and every consumer moved to it |
| 6 — the creature's stated choice among bases | **Settled** by [#394](https://github.com/eddiefiggie/srd-rules-engine/issues/394) ([0079](0079-a-second-base-refuses-rather-than-being-picked-between.md)): an unstated choice **refuses**, and the mechanism for stating one waits on something that can grant a second base |
| 7 — the Shield's bonus, withheld without training | **Half built.** The bonus is granted ([#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393)); the withholding is [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367) |
| 8 — one suit, one Shield | **Built**, as refusals in the derivation |
| 9 — the attack path reads the derived value | **Built.** Ten sites in `core.combat` and `core.read_surface` |

### Clause 4 was right about provenance and wrong about shape

This record read p. 254's stat-block AC as "another base AC calculation" that p. 177 permits.
That is right about where the number *comes from* and wrong about what it **is**: a stat block
states an AC, which is a result, while p. 177's alternatives are calculations.

Built as written, it put the stated total beside worn armour as a rival base — and the first
demonstration showed a creature in Plate reading as its unarmoured value, silently, because
`armour_class` is a required field every ruleset already sets. The armour was inert.

The correction: **they are the same claim at two levels of detail.** A total is the shorthand a
ruleset uses when it has not described the armour, and p. 92's "a monster has training with any
armor **in its stat block**" is the document contemplating a stat block that lists the armour.
So the derivation prefers described armour and falls back to the stated total, and no existing
creature's AC changes.

Genuinely competing bases — a feature granting an alternative calculation, which is p. 177's
actual case — remain [#394](https://github.com/eddiefiggie/srd-rules-engine/issues/394).

### A disclosure that could never fire

`untrained-shield-still-grants-ac` was appended only when `untrained_armour` found something,
and that function reads **worn** items because p. 104 is about armour "you are wearing". p. 92's
Shield is **held**. So the clause was told to a creature in untrained plate holding no Shield,
and never to a creature holding an untrained Shield — the only creature it is about.

It was pinned, it was disclosed, and it was unreachable by its own case. Found by writing the
first test that tried to observe it firing. `untrained_shields` now names the right creature,
and `tests/test_casting.py`'s assertion — which had been passing against worn armour since
#367 — is corrected to say so.

### Evidence

Six corruption proofs, each red on the assertion written for it.

| Corruption | Went red on |
|---|---|
| bases summed instead of chosen between | `test_a_shield_adds_to_the_base_rather_than_replacing_it` |
| the stated total preferred over worn armour | `test_described_armour_beats_a_stated_total`, `test_worn_armour_supplies_the_base` |
| the Dexterity cap clamped at 0 | `test_a_capped_base_caps_the_modifier_and_does_not_clamp_it` |
| the one-suit refusal disabled | `test_two_suits_of_armour_are_refused` |
| carriage ignored when collecting bases | `test_armour_contributes_only_while_worn` |
| the disclosure gated back on `untrained_armour` | the two tests that observe it firing |

The first is the one this record exists for: it makes a character in Plate with a Shield 28.
The last reproduces the unreachable disclosure exactly.
