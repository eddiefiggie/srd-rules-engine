# 0075 — Ties are a person's, and Initiative is a Dexterity check

- **Status:** Accepted, 2026-08-30
- **Settles:** [#385](https://github.com/eddiefiggie/srd-rules-engine/issues/385)
- **Requirements:** R4, R12, R31, R32
- **Related:** [0026 — terrain enters as state](0026-terrain-enters-as-state.md), whose dial
  argument this applies to the initiative ability;
  [0025 — sight is a relation over stored state](0025-sight-is-a-relation-over-stored-state.md),
  the same move for light;
  [0059 — initiative draws a pair for everyone](0059-initiative-draws-a-pair-for-everyone.md),
  which built the machinery this verifies

## Context

`scripts/verify_d20_rules.py` carried **no initiative clause at all**, and `core.combat` held
`Verification` objects for weapon properties and the Unarmed Strike only. Initiative had a
decision record ([0059](0059-initiative-draws-a-pair-for-everyone.md)), its own seed band
(#82), and a pair of dice for every combatant (#359) — everything except the thing this
repository treats as load-bearing.

Two rules had therefore been settled by default rather than by reading, and the code said so
in both places:

> Which ability the modifier comes from is a rule with a section citation, so it is a
> *parameter* rather than a constant here.

> Order the combatants and begin round 1. **Ties break by the order given.**

The first was honest and the second was a convention presented as an implementation detail.
Neither was wrong; both were unfalsifiable.

## What the document says

p. 13, read for this record:

> When combat starts, every participant rolls Initiative; **they make a Dexterity check** that
> determines their place in the Initiative order.

> **Initiative Order.** The GM ranks the combatants, from highest to lowest Initiative. This
> is the order in which they act during each round. The Initiative order remains the same
> from round to round.

> **Ties.** If a tie occurs, the GM decides the order among tied monsters, and the players
> decide the order among tied characters. The GM decides the order if the tie is between a
> monster and a player character.

## Decision

1. **`INITIATIVE_ABILITY` is a constant and `initiative_order` takes no `ability`.** The page
   is asserted, so the parameter's reason for existing is gone. A caller able to roll
   Initiative off Strength could reorder an encounter and leave a ledger that looks
   legitimate — the dial 0026 removed for terrain and 0025 for light, one level smaller.

2. **`INITIATIVE_VERIFICATION` names p. 13 and p. 184**, so the module states what it rests
   on the way it already does for weapon properties.

3. **Ties are not implemented, because the document does not leave them to be implemented.**
   It **assigns** them, in three clauses, to a person: the GM among monsters, the players
   among characters, the GM between the two. There is no rule here for an engine to hold.

4. **Insertion order is declared as a convention.** The engine needs a total order to be
   reproducible and the document supplies none it may use, so the tie-break is stable,
   stated, and not a claim about the rules — the construction `Lighting` uses for overlapping
   volumes, for the same reason and in the same words.

5. **The person's decision reaches the engine as the order the combatants are passed in.**
   That is not a workaround; it is the only input `with_initiative` has, and it is exactly
   what p. 13 describes someone doing.

## Why

### A verified value and an inferred one look identical from inside

`ability="dex"` was right. It has been right since the day it shipped, and it would have gone
on being right. What it lacked was any way for a reader to tell it from a value somebody
remembered — which is the whole of R31's concern, and the reason this repository spends
effort on provenance rather than on correctness alone.

[#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371), one build before this one,
is the case that makes the point: p. 105's ritual clause was quoted **accurately** in a
docstring by someone who had not read p. 105, and the quote was load-bearing for an entire
issue. Accuracy is not provenance. The same build found a turn count that had been wrong for
five builds behind a test that asserted it.

### Ties are the third instance of "the document gave this to a person"

The engine already declines to decide two things the SRD hands to a human: the *degree* of
Cover (p. 15 gives thresholds and no method for measuring what fraction of a target is
covered) and an improvised weapon's damage type (p. 183: "a type the GM thinks is
appropriate", [#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264)).

Ties are the third, and the cleanest, because the document is not vague about it — it is
explicit, and it names three different people for three different cases. An engine
implementing a tie-break would not be filling a gap; it would be overriding an instruction.

**The distinction worth keeping is between a gap and an assignment.** A gap invites a future
rule. An assignment closes the question, and what this engine owes is a stable convention and
a sentence saying it is one.

### Why the convention is not disclosed as an unenforced clause

`unenforced_clauses` names a mechanic the engine holds and does not enforce, per creature, at
the read surface. A tie-break is neither per-creature nor unenforced — it happens, every time,
deterministically. What it is not is *the SRD's answer*, and that belongs in the method's own
docstring beside the sentence it declines to implement, which is where `Lighting` puts the
identical claim.

## Consequences

- **`initiative_order`'s signature changes.** No caller supplied `ability`, so nothing in the
  tree breaks, but it is a narrowing of a public surface.
- **A test that asserted the opposite is replaced.** `test_the_ability_initiative_uses_is_a_parameter_not_a_constant`
  was correct when written and inverted by the page being read. Its replacement says so, since
  the reasoning is the interesting part and a silent flip would look like a reversal.
- **p. 184's Initiative *score* variant is modelled by nothing**, and is asserted so that the
  absence is visible: "Sometimes a GM might have combatants use their Initiative scores
  instead of rolling." Optional in the document, absent here, and now findable.

## Status of implementation

| Clause | State |
|---|---|
| 1 — `INITIATIVE_ABILITY`, and no parameter | **Built** |
| 2 — `INITIATIVE_VERIFICATION` | **Built** |
| 3 — ties not implemented | **Built**, in the sense that the decision is to hold no rule |
| 4 — insertion order declared a convention | **Built.** `EncounterState.with_initiative` |
| 5 — the caller's order is the person's decision | **Built**, and asserted both ways |

The Initiative *score* variant (p. 184) is **not built** and is not filed: it is an optional
alternative the GM may use instead of rolling, and this engine rolls (R4). Recorded here so a
later audit does not re-raise it — `AGENTS.md`'s first exception to the filing rule.

`scripts/verify_d20_rules.py` carries 287 clauses, up from 283, and the whole file was re-run
against the document for this change.

### Evidence

Five corruption proofs, each red on the assertion written for it.

| Corruption | Went red on |
|---|---|
| `INITIATIVE_ABILITY` set to `"str"` | `test_initiative_rolls_dexterity_and_a_caller_cannot_choose` |
| the `ability` parameter restored | that test, and `test_the_ability_initiative_uses_is_a_verified_constant_not_a_parameter` |
| the sort reversed to lowest-first | `test_the_order_is_highest_to_lowest_and_survives_the_round` |
| the tie-break keyed on id instead of insertion order | `test_a_tie_breaks_by_the_order_given_and_that_is_a_convention` |
| the verification's pages blanked | `test_the_initiative_rules_are_asserted_against_their_pages` |

The fixture for the first gives every creature Strength 20 and Dexterity 6, so a roll
consulting the wrong ability comes out visibly different rather than coinciding — the
vacuous-fixture failure this repository has now hit twice.
