# 0026 — Terrain enters by one route, and it is state

- **Status:** Accepted, 2026-08-25
- **Settles:** [#151](https://github.com/eddiefiggie/srd-rules-engine/issues/151)
- **Requirements:** R1, R4 · touches R16, R19, R28
- **Related:** [0025 — sight is a relation over stored state](0025-sight-is-a-relation-over-stored-state.md),
  whose clause 2 created this seam knowingly; [#91](https://github.com/eddiefiggie/srd-rules-engine/issues/91),
  which built obstructions as a query argument;
  [0002 — ledger durability](0002-ledger-durability.md) and
  [0006 — JSONL with a fixed envelope](0006-jsonl-and-a-reader-api.md), which #151 asked to be
  checked and which turned out to decide the opposite of what it expected

## Context

Two kinds of terrain enter the engine by two routes:

| | How it enters | Where it lives |
|---|---|---|
| **Obstructions** (#91) | `areas.creatures_in(area, positions, obstructions=())` — a query argument | nowhere; the caller holds them |
| **Light** (0025 clause 2) | `EncounterState.lighting`, set at construction or through a ruling | state, versioned by `generation` |

0025 chose that inconsistency deliberately, disclosed it in its Consequences, and filed it rather
than leaving it as prose. This record settles it.

### The argument #151 expected to be decisive is wrong

#151 offered, as option 1's strongest point, that putting obstructions on state "makes both kinds
of terrain versioned by `generation` — which also makes a replay reproduce them, where today a
caller's obstruction list is outside the ledger entirely", and asked that it be checked against
0002 and 0006 before choosing. It was, and it does not hold.

**Replay never reads `EncounterState`.** `core/report.py` does not reference the type at all.
`replay_entry` rebuilds the `D20Test` from the ruling entry's own `roll` payload —
`declared_advantage`, `declared_disadvantage`, `kind`, `target`, `target_basis`, `modifiers` — and
re-derives the dice from the recorded `seed`. Neither `lighting` nor any obstruction appears in
`core/ledger.py`, `core/ledger_reader.py`, or `core/adjudicate.py`.

Two consequences follow, and the second is the uncomfortable one:

1. Moving obstructions onto state would **not** make them replayable.
2. Light being on state does **not** make light replayable either. 0025 clause 2 never claimed it
   did — its argument was R1/R4 throughout — but a reader could easily infer the guarantee, and it
   is not there.

What actually makes a derived input replayable is **the ruling entry recording it**. That is
exactly what `REPLAYABLE_FROM = 2` did for advantage: before it, a ruling made with advantage
replayed as though it had none, rolled one die where two were rolled, and reported a mismatch
indistinguishable from real drift. Where terrain *lives* is orthogonal to that.

So the seam has to be decided on the outcome-authority question alone, which is the one 0025
clause 2 actually made.

## Options considered

**Leave obstructions as a query argument and re-argue when cover reaches a roll** (#151 option 2).
Rejected. The R1/R4 argument does not wait for the attack roll, and #151 names the risk itself:
the moment arrives inside a PR about something else. `Cover.bonus` already returns an AC bonus, so
the plumbing is half-built and the dial appears the moment anything reads it.

**Split it — a parameter for read-only geometry, state for anything feeding a roll** (#151
option 3). Rejected under 0025 clause 4's reasoning, which this record is applying rather than
extending: two sources for one kind of fact is a second thing to keep consistent with the first,
and the inconsistency is silent. It also puts the boundary in the worst available place — a
caller cannot tell which of its calls are the load-bearing ones, and the classification changes
under it whenever a read surface starts feeding an adjudication path.

**Move light back off state to match obstructions.** Not raised in #151, and rejected here so it is
not re-raised: it resolves the inconsistency in the direction that gives the caller the dial, which
is the direction R1 forbids.

## Decision

**1. Obstructions are state, never a query argument.** They live on `EncounterState` beside
`lighting`, set when the encounter is constructed or changed through a ruling. This is 0025
clause 2's sentence with the noun swapped, and deliberately so: an input the caller hands over at
the moment an outcome is computed is an input the caller *chooses*. #119 settled the same question
for conditions — a condition reaches state through a ruling, or not at all — and 0025 applied it to
light. Terrain now has one rule instead of two.

**2. The route is decided by what the input can become, not by what it currently feeds.** #151
records that obstructions "reach no adjudication path" today, and that is true of `core.adjudicate`
and `core.combat`. It is not the whole picture. `creatures_in` decides membership in an area of
effect, and a caller varying the obstruction list between calls changes who is caught in a
Fireball — which is to say, who takes damage. That the arithmetic happens in the caller rather than
in `core.adjudicate` does not move the authority; it only hides it. This clause exists so the
"not yet load-bearing" framing is not inherited by the next reader.

**3. One box, carried by both.** `LitVolume` and `Obstruction` hold the same axis-aligned box in
feet, including the corner normalisation, as two copies. `core/sight.py` said in prose that they
were not unified "because the two kinds of terrain do not yet enter the engine by the same route —
obstructions are a query argument, light is state — and that seam is #151". The seam is now
settled, so the reason lapses: the shared box is extracted and both carry it. Unifying the
*geometry* is not unifying the *meaning* — a volume that emits light and a volume that blocks a
line stay distinct types.

**4. Replay is not an argument for either side, and no clause here may be read as improving it.**
A terrain input reaches replay only by being recorded on the ruling entry that depended on it, in
the `REPLAYABLE_FROM` pattern. Nothing in this record does that, because nothing yet feeds a roll.
When cover or light first modifies a d20 test, the entry must record the derived value — not the
terrain it came from — and that is filed as
[#159](https://github.com/eddiefiggie/srd-rules-engine/issues/159).

**5. Supplying no obstructions still means none exist.** `core/areas.py` already draws this
distinction — "**Supplying none means none exist**, not that they are ignored" — and moving the
source from an argument to a field does not soften it. An `EncounterState` with an empty
obstruction tuple describes an open field, which is the correct answer for an open field and a
wrong one for a dungeon. The engine cannot tell those apart and does not pretend to. What changes
is only *who* may say so, and when.

## Why

**The order of the clauses is the argument.** Clause 1 decides the route on R1/R4 alone, because
clause 4 has removed the argument everyone reaches for first. Clause 2 answers the objection that
would otherwise defer clause 1 indefinitely. Clause 3 is the consequence that was explicitly parked
on this issue and would be re-orphaned by silence.

**This record is smaller than it looks.** It changes no rule value, resolves no effect shape, and
touches no page of the document. It decides where a caller's terrain is allowed to enter, which is
a product-contract question rather than an SRD one.

**The replay finding is the part worth carrying forward.** It was not sought — #151 asked for a
check against 0002 and 0006 and the check falsified the premise. The correction matters beyond this
seam, because "put it on state so replay reproduces it" is a plausible sentence that will occur to
somebody else about some other input, and it is false for every one of them.

## Consequences

**Accepted costs.**

- **`areas.creatures_in`'s signature changes**, and every caller with it. This is free in the only
  sense that matters here: neither `creatures_in` nor `EncounterState` nor `Obstruction` appears in
  `stability.COMMITTED`, so all three are Internal tier under 0018 — importable, unpromised. No
  `API_VERSION` bump, and nothing to deprecate.
- **An encounter must now be constructed with its walls**, where before a caller could pass them
  per query. That is the point rather than a side effect, but it is a real ergonomic cost to a
  consumer doing one-off geometry questions, and there is no escape hatch by design — an escape
  hatch is the query argument under another name.
- **The shared box is a third type** where there were two, and neither of the originals gets
  simpler. The win is that a fix to the corner normalisation lands once.

**Follow-on effects.**

- #91's design is amended, not reversed: the p. 177 blocking rule and `line_is_blocked` are
  untouched, and only the source of the obstruction list moves.
- 0025 clause 2's Consequences entry describing this as a deliberate inconsistency is now history
  rather than a live disclosure. Its **body is not edited** — records are immutable, and the
  Consequences and Evidence paragraphs correctly describe what was believed when it was written.
  Its **Status of implementation** row for the seam *is* updated to point here, because that
  section is maintained as work lands rather than frozen with the decision (0024), which 0025's
  own footer records having done once already.
- `core/sight.py`'s "The box, and why there are two of them" is live prose in code rather than a
  record, so it is corrected in this change: it pointed at #151 as an open seam, and a note
  pointing at a closed issue reads as finished work rather than absent work.
- The inventory's count is unchanged at **76 of 211**. A routing decision resolves no shape, which
  is the README's standing warning about reading that number as progress.

## Evidence

No spike. #151 asked for one check and it decided the record:

- `core/report.py` — no reference to `EncounterState` anywhere in the module; `replay_entry`
  reconstructs from `entry.payload["roll"]` and `_test_from` reads only recorded fields.
- `core/ledger.py`, `core/ledger_reader.py`, `core/adjudicate.py` — no occurrence of `lighting` or
  `obstruction`.
- `REPLAYABLE_FROM = 2` in `core/report.py`, and the `UNREPLAYABLE` detail string explaining what a
  thin record costs. This is the pattern clause 4 points at.
- `stability.COMMITTED` in `src/srd_rules_engine/stability.py` — `areas`, `EncounterState` and
  `Obstruction` are absent, which is what makes clause 1 cheap.
- `core/sight.py`'s "The box, and why there are two of them", which parks the unification on this
  issue and is what clause 3 answers.
- `core/areas.py`'s "Supplying none means none exist", which clause 5 preserves.

## Status of implementation

**Clause 1 is built; clauses 3 and 4 are not.** `EncounterState.obstructions` landed 2026-08-25,
with `tests/test_areas.py` covering it.

| Clause | State |
|---|---|
| 1 — obstructions are state | Built. `EncounterState.obstructions`, and the composed question is `EncounterState.creatures_in(area)`. `core.areas` no longer has a `creatures_in` at all — the composition moved rather than gaining a parameter, so `Area.contains` stays pure volume |
| 2 — the route follows what the input can become | Nothing to build; it is the reasoning clause 1 rests on |
| 3 — one box, carried by both | Not built. [#161](https://github.com/eddiefiggie/srd-rules-engine/issues/161), unblocked by clause 1 landing |
| 4 — replay is not an argument, and terrain reaches it via the entry | Not built, and deliberately not part of clause 1. [#159](https://github.com/eddiefiggie/srd-rules-engine/issues/159) |
| 5 — supplying none still means none exist | Built as the field's default and its own test. An `EncounterState` with an empty tuple describes an open field |

The route is a guard rather than a note: `test_no_area_query_lets_a_caller_supply_the_walls`
asserts no public callable in `core.areas` takes an `obstructions` parameter, so re-introducing
the dial turns red. `core.obstructions.line_is_blocked` is deliberately outside that guard — it is
a pure predicate over three explicit arguments with no encounter to be wrong about, and 0026 did
not move it.

_Updated 2026-08-25 when [#160](https://github.com/eddiefiggie/srd-rules-engine/issues/160)
landed. This record shipped saying "Decided, not built", which was true for about an hour._

**No effect shape is resolved by any of it.** Coverage stays at 76 of 211, and #138 stays open for
the nine sight shapes it was already blocked on.
