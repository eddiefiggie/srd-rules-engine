# 0073 — A slot records the turn it happened in

- **Status:** Accepted, 2026-08-30
- **Settles:** [#120](https://github.com/eddiefiggie/srd-rules-engine/issues/120)
- **Requirements:** R13, R30
- **Related:** [0015 — the generator seam already serves reactions](0015-reactions-and-the-agent-seam.md),
  which deferred this and named it "the piece that will bite";
  [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  the first source of interleaving;
  [0072 — movement is a phase the loop drives](0072-movement-is-a-phase-the-loop-drives.md),
  the second, which is what made this decidable

## Context

A `Turn` in `session_report` is a **declaration slot**, not a game turn. Two things open a
slot inside another creature's turn:

* an **engine-authored obligation** — a save-ends save or a death save (0023 clause 2: its
  `Declaration` "is not the agent's"), which lands after the actor's own narration;
* a **reaction** (0072), whose declaration, ruling and narration land mid-resolution, inside
  the moving creature's turn.

`_turns` assembled slots from a flat entry sequence and closed one when a different actor
declared. So an Opportunity Attack made mid-move was filed as a turn of its own: in the
report, the mover's turn *ended* at the moment somebody reacted to it.

0015 predicted this in 2026-08-23 and deferred it deliberately — *"the interleaving is what
to settle before building, not the seam"* — then the seam question closed and this was not
filed until [#312](https://github.com/eddiefiggie/srd-rules-engine/issues/312)'s sweep found
it. `Turn`'s own docstring said the grouping was "left open on purpose until reactions supply
the second half of the question". 0072 supplied it.

### The question #120 asked first

> Today an entry names its actor and its position in the sequence; whether that is enough to
> distinguish "inside turn N" from "at the end of turn N" is the first thing to establish.

**It is not enough**, and the adjudicator has the answer in hand and was not writing it down:
`Adjudicator.adjudicate` holds the `EncounterState` when it appends the declaration entry, so
`state.active_id` and `state.round_number` were one line away the whole time.

## Decision

1. **The declaration entry records the game turn it happened in.**
   `DECLARATION_VERSION` 3 adds `during` — the id of the creature whose turn it is — and
   `round`. Together they identify one game turn.

2. **Recorded, never reconstructed.** A reader could infer turn boundaries from actor changes
   in the sequence, and that inference is wrong in exactly the case the field exists for: a
   reaction *is* an actor change inside a turn. So an older ledger comes back
   `attributable=False` and is not apportioned by a guess.

3. **Presence decides `attributable`, not truthiness.** `during=None` with the key present
   means *the engine says there was no turn* — the slot happened outside combat. An absent key
   means *this ledger cannot say*. Only the second is a limit, and collapsing them would
   publish a limit that is not there.

4. **`SessionReport.game_turns` groups by consecutive runs of `(round, during)`**, not
   globally. A run keeps the ledger's order and cannot merge two things that merely share a
   key — which matters most for slots outside combat, where every one carries `(None, None)`
   and a global grouping would gather an entire session into a single claim nobody made.

5. **`Turn.interjected`** is the slot-level form: this slot belongs to a creature other than
   the one whose turn it is. `render` names it, because a reaction rendered as a bare slot
   reads as the turn's own creature acting twice.

6. **`NOT_MEASURED` narrows rather than clears.** Turn grouping was published as undecided;
   it is decided, and what remains unmeasurable is a ledger written before the field existed.

## Why

### `improvised` was never enough, and only the second source showed it

`NOT_MEASURED` used to say: *"`Turn.improvised` tells them apart today; how they should be
grouped is undecided."* The first half was as load-bearing as the second, and it was **wrong
for reactions** — an Opportunity Attack is the agent's own declaration, so it arrives
`improvised=False` like any other attack.

A reader following that advice would have caught 0023's obligations and missed 0072's
reactions **silently**, which is the worse direction: an instrument that reports a boundary
where none exists looks like an instrument that works.

This is why the decision is to record a fact rather than derive one from a flag that happened
to correlate with the only source that existed when it was written. `tests/test_turn_attribution.py`
asserts the two are indistinguishable by `improvised`, so the reasoning cannot quietly rot back.

### Why not group by actor changes

It is the obvious rule and it is precisely backwards. The sequence

```
declaration(mover) ruling narration | declaration(guard) ruling narration
```

is one game turn when the guard's slot is a reaction and two when the guard's turn simply
followed. Nothing in the flat sequence separates them — the difference is a fact about the
encounter's state at the moment of writing, which is the thing the ledger was not recording.

### A pre-existing limit this makes visible rather than introduces

The report has always been able to say less about older ledgers than newer ones; `resumption`
(`DECLARATION_VERSION` 2, [#59](https://github.com/eddiefiggie/srd-rules-engine/issues/59)) set
the pattern and its comment states it: *a reader must be able to tell "not a resumption" from
"written before the field existed"*. This follows it exactly, including the always-present key.

## Consequences

- **`render` publishes two counts** — game turns and declaration slots — because they answer
  different questions and a reader given only the second reads it as the first.
- **`GameTurn` is a new public type**, exported from `core`.
- **The 0015 → 0023 → 0072 → 0073 chain closes.** 0015 deferred this and predicted what would
  bite; three records later the thing it predicted arrived and was fixed by the field it
  implied.

## Status of implementation

| Clause | State |
|---|---|
| 1 — `during` and `round` on the declaration entry | **Built.** `DECLARATION_VERSION` 3 |
| 2 — recorded, never reconstructed | **Built.** `attributable` |
| 3 — presence decides `attributable` | **Built.** Proved by a corruption that keyed on the value |
| 4 — `game_turns` groups consecutive runs | **Built.** `SessionReport.game_turns` |
| 5 — `interjected`, and `render` naming it | **Built** |
| 6 — `NOT_MEASURED` narrowed | **Built** |

### Evidence

Seven corruption proofs, each red on the assertion written for it. `prove_against_base.sh`
cannot discriminate — `tests/test_turn_attribution.py` is a new module and fails on *import*
against the base tree.

| Corruption | Went red on |
|---|---|
| `during` written as `None` | `test_a_reaction_is_attributed_to_the_turn_it_interrupted` |
| `round` written as `None` | `test_a_reaction_is_attributed_to_the_turn_it_interrupted` |
| every slot grouped on its own | `test_the_two_slots_group_into_one_game_turn` |
| `interjected` forced `False` | `test_the_reaction_is_marked_as_an_interjection` |
| `attributable` keyed on the **value** | `test_outside_combat_is_recorded_as_no_turn_rather_than_as_no_record` |
| the render's interjection marker removed | `test_the_rendered_report_shows_the_turn_and_names_the_interjection` |
| `NOT_MEASURED` reverted to claiming nothing | `test_the_limit_is_published_for_older_ledgers_only` |

**The fifth proof failed on its first run**, and that is worth recording rather than tidying
away. Keyed on the value instead of the key's presence, every assertion in the file stayed
green — because the legacy fixture has the field *absent*, so both readings agree there.
Clause 3's distinction was untested by anything, and nothing about reading the assertions
revealed it. The out-of-combat test exists because the proof went green, which is the exact
failure mode `AGENTS.md` describes as vacuous under its own fixture.
