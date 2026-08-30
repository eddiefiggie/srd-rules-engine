# 0053 — The target chooses, and the engine rolls

- **Status:** Accepted, 2026-08-30
- **Settles:** [#343](https://github.com/eddiefiggie/srd-rules-engine/issues/343), and with it the
  p. 190 half of [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335)
- **Requirements:** R1, R4, R15, R18, R31, R32
- **Related:** [0001 — the agent seam](0001-agent-seam.md), whose typed requests this adds a
  fourth to; [0048 — a forced save is one mechanism](0048-a-forced-save-is-one-mechanism.md),
  whose queue this extends without touching either occupant;
  [0052 — the exit is built before the entrance](0052-the-exit-is-built-before-the-entrance.md),
  clause 5, which met the same choice and paid nothing for it;
  [0051 — a size is stated, or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md)

## Context

> p. 190, *Unarmed Strike*, **Grapple.** The target must succeed on a **Strength or Dexterity
> saving throw (it chooses which)**, or it has the Grappled condition.
>
> **Shove.** The target must succeed on a **Strength or Dexterity saving throw (it chooses
> which)**, or you either push it 5 feet away or cause it to have the Prone condition.

Two hits in the whole document, both on p. 190, and they are the same sentence twice. Every
other compelled save names its ability outright.

### The same shape cost nothing one record ago

0052 clause 5 met "the creature chooses" in p. 182's escape check — "a Strength (Athletics)
**or** Dexterity (Acrobatics) check" — and it needed no seam at all. The escape is an action
the creature *declares*, so the choice is which action key it declares: one offer per check,
each carrying its bonus.

p. 190 is the mirror image and that is the whole difficulty. The choosing creature is the
**target of a forced save**. It declares nothing; `TurnLoop` drains `forced_saves_owed`,
synthesises a declaration through `_obligation_declaration`, and adjudicates. That function's
own docstring says why nobody is asked:

> `alternatives` is empty and `read_token` is `None`, so the ruling's verdict comes back
> `unread`. That is the honest value: no read surface offered this, **because nothing was
> choosing**.

Exactly true for p. 179's Concentration and p. 90's Topple. Exactly false for these two.

## Options considered

**Option 1 — the engine picks the higher modifier.** Rejected, and the evidence is stronger
than "it is a strategy rather than a rule". **The better modifier is not the better save.**
p. 187's Restrained gives Disadvantage on *Dexterity* saves alone, so a Restrained creature
with a better Dexterity modifier should still choose Strength. The correct answer depends on
the conditions held at the moment of the save.

There is a second reason, found while writing this and filed as
[#344](https://github.com/eddiefiggie/srd-rules-engine/issues/344): the engine **cannot**
compute which save is better even in principle today, because a creature's conditions do not
reach its saving throws at all. `ConditionEffects.dexterity_saves` and
`auto_fail_strength_and_dexterity_saves` are modelled in data and consumed by none of the six
`TestKind.SAVE` sites. An engine choosing optimally would be choosing on incomplete
information *and* deciding a choice the document gave away.

**Option 2 — the ruleset states a standing preference on the creature.** Rejected for the same
Restrained row: a standing preference cannot vary with the conditions the creature is holding,
and p. 190 gives the choice per save. It is also policy, and this engine holds rules.

**Option 3 — the attacker's declaration names the defender's save.** Rejected. One agent voices
both sides in solo play, but the attacker choosing the target's defence is wrong-shaped
whoever is speaking.

**Option 4 — `ForcedSave` carries the permitted abilities, and the choice arrives as a typed
request from whoever controls the target.** Chosen. Choosing *which* of two saves to roll is a
choice the rules assign to a creature; it is not a decision about how the roll turns out, and
the engine still rolls it. That is 0001's seam doing its job, and it stays on the right side of
the product invariant — the agent decides that a rule applies and which one, never how it turns
out.

## Decision

1. **`ForcedSave.ability_choices` names what the target may pick between**, and is empty for
   every save the document states outright. Concentration and Topple do not notice the field
   exists.

2. **A save with choices is unsettled until one arrives.** `ability` is empty, `is_settled` is
   `False`, and **no resolver may roll it** — the resolver raises rather than picking. That
   refusal is the whole record in one line: an engine that rolled here would have chosen.

3. **The choice reaches state before adjudication, not on the declaration.**
   `EncounterState.with_forced_save_choice` settles it, and the resolver then reads the same
   debt it always read. A compelled save has no declaration of its own — the engine authors it
   — so a choice carried there would be the engine putting words in an agent's mouth. R4 is
   untouched: the engine still rolls.

4. **`SaveAbilityRequest` is the fourth typed request**, beside declaration, narration and
   blocked facts. It carries the DC and its derivation, and one `SaveOption` per ability with
   the modifier the roll would use — because a choice presented without them is not a choice an
   agent can make, which is 0052 clause 5's rule read again. It is addressed to the **target**,
   which is not the creature whose turn it is.

5. **Declining is a refusal, not a default.** `SaveAbilityChosen(ability=None)` leaves the save
   unrolled and records an unresolvable obligation, the way a rejected one is recorded. There is
   no fallback ability, because every fallback is Option 1 through the back door. A grapple
   whose save nobody answered neither lands nor misses, and the ledger says so.

6. **`ForcedSave.source_id` carries who compelled the save.** p. 190's Grapple applies Grappled,
   and p. 182 gives that condition "Disadvantage on attack rolls against any target other than
   **the grappler**". The save is rolled on the target's own declaration, so by then the
   attacker is recoverable from nothing else. `None` for Concentration and Topple, whose
   consequences name nobody.

7. **The grapple's escape DC travels with the application.** p. 190 states one number for "the
   saving throw **and any escape attempts**", so `Effect.grapple` carries it into the condition
   and p. 182 reads it back — 0052 clause 4 from the other end. **The range does not**: p. 190
   states the reach of the *strike*, not the range of the grapple, and reading one as the other
   is an inference ([#346](https://github.com/eddiefiggie/srd-rules-engine/issues/346)).

8. **Shove knocks Prone and cannot push.** p. 190 lets the attacker choose between the two, and
   the push is forced movement relative to another creature — the primitive Frightened and the
   Push mastery also wait on. Disclosed as `shove-cannot-push-only-knock-prone`
   ([#345](https://github.com/eddiefiggie/srd-rules-engine/issues/345)) rather than approximated,
   because a Shove that always knocks Prone has decided the attacker's choice for it.

## Why

### A bug this change had to find

`EncounterState.with_condition` rebuilds a creature's `Conditions` field by field, and 0052's
new `grapple` was not among them. So **applying any condition to a grappled creature erased the
grapple's escape DC** — and the ordinary case that reaches it is a Shove knocking a grappled
creature Prone, which is precisely what this record builds. `Conditions.without` had the mirror
of it: it dropped the terms on every ending rather than on the grapple's own.

Both are fixed here and asserted. It is worth naming because 0052 shipped green: the field was
new, nothing else wrote a condition onto a grappled creature, and no test could have noticed.

### What the seam does not do

It does not make the choice *well-informed*. `SaveOption.modifier` is the bare ability modifier,
because that is what the engine will actually roll (#344). The number is honest about the
engine's behaviour and is not yet the whole of what p. 187 says, and that is where the
difference will have to show when #344 lands.

## Consequences

- **`unarmed-strike` becomes implemented**, 114 of 210 — with a disclosure rather than in spite
  of one, the arrangement `carrying-capacity` already ships under.
- **A fourth `Request`/`Response` pair.** Every driver gains a branch, and the type checker
  found each one: `ScriptedDriver`, `HumanCliDriver`, and the test fixture's driver all failed
  to compile until they answered it. That is the union doing its job.
- **The fixture driver picks the first ability the rule offered**, deliberately not the best
  one. A fixture that optimised would make every test read as though the engine had chosen.
- **Two prose disclosures retired against the build.** `core.combat`'s Grapple-and-Shove note
  and the guard asserting it named an open issue are both replaced by an assertion that the two
  options are genuinely offered.
- **Eight clauses added to `scripts/verify_d20_rules.py`**, which reports 260 verified —
  including p. 187's Restrained row, because the whole of Option 1's rejection rests on it.

## Evidence

- p. 190 — the three options and that the attacker chooses one; both saves with "it chooses
  which"; the one DC serving the save and every escape attempt; Grapple's two qualifiers
  including the free hand; Shove's single qualifier without one; and the 5 feet, which belongs
  to the strike.
- p. 187 — Restrained's Disadvantage on Dexterity saving throws.

## Status of implementation

**Every clause is built** by [#343](https://github.com/eddiefiggie/srd-rules-engine/issues/343)
and the p. 190 half of [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335).

| Clause | State |
|---|---|
| 1 — `ability_choices`, empty for every other save | **Built.** `ForcedSave`, asserted to leave Concentration and Topple untouched |
| 2 — unsettled saves are refused, not picked | **Built.** `is_settled`, and the resolver raises |
| 3 — the choice reaches state, not the declaration | **Built.** `EncounterState.with_forced_save_choice` |
| 4 — `SaveAbilityRequest` carries the options and their modifiers | **Built.** Asserted to be addressed to the target and to carry both modifiers |
| 5 — declining leaves the save unresolved | **Built.** Asserted to produce an unresolvable obligation and no condition |
| 6 — `source_id` carries who compelled it | **Built.** Asserted through to `grappler_id` on the applied condition |
| 7 — the escape DC travels, the range does not | **Built.** Asserted both ways; the range is [#346](https://github.com/eddiefiggie/srd-rules-engine/issues/346) |
| 8 — Shove knocks Prone and cannot push | **Built as a disclosure.** The push is [#345](https://github.com/eddiefiggie/srd-rules-engine/issues/345) |
