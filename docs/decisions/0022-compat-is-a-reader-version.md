# 0022 — `compat` is a reader version, and no payload derives it from its own schema version

- **Status:** Accepted, 2026-08-23
- **Settles:** [#106](https://github.com/eddiefiggie/srd-rules-engine/issues/106)
- **Requirements:** R35 · touches R28, R30
- **Amends:** [0011 — module layout and versioning](0011-module-layout-and-versioning.md), clause 5.
  Clauses 3 and 4 stand and are what this record enforces.
- **Related:** [0006 — ledger format](0006-ledger-format.md), whose permanently-frozen envelope is
  why `compat` lives in the payload at all; [0018 — API stability](0018-api-stability.md), which
  governs the *other* audience discussed below

## Context

0011 gave every payload a reserved `compat` key and defined it twice, in two clauses, as two
different things.

**Clause 4:** "the lowest **reader** version that can correctly interpret it."

**Clause 5:** "A version bump raises `compat` only when an older reader would get it wrong. …
Removing a field, changing a field's type or meaning, or adding a field a correct reading
requires, **raises it to the new version**" — the new *schema* version.

Those are two number lines. Clause 3 versions the four payload schemas **independently**, on the
explicit reasoning that "a change to the Ruling must not make a reader treat unchanged
Declarations as unknown". So there is no single reader version that could track all four, and a
scalar compared against floors drawn from four independent lines produces nonsense as soon as any
one of them moves.

Every payload writer implemented clause 5 — `COMPAT: RULING_VERSION`, `COMPAT:
FACT_PAYLOAD_VERSION`, and so on. The reader implemented clause 4 — `compat <= reader_version`.
The two met in the middle at a wrong answer.

## The fact that decides it

**Every `ruling` entry the engine has ever written reports `interpretable=False`.** Read off a
real ledger from the vertical-slice harness:

```
0 session     v=1 compat=1 interpretable=True
1 declaration v=1 compat=1 interpretable=True
2 ruling      v=2 compat=2 interpretable=False
3 narration   v=1 compat=1 interpretable=True
```

`RULING_VERSION` was 2 and `READER_VERSION` was 1, so `2 <= 1` was false. The reader R35 makes
public was telling every consumer it could not interpret the one entry type that carries an
outcome — and had been since the ruling schema first left 1.

It survived because the reader's own tests build their ledgers from hand-written payloads that all
carry `compat: 1`. The one entry type whose floor had drifted was the one those ledgers never
contained.

The session entry escaped only by accident: it was written as a literal `COMPAT: 1` rather than
from `FORMAT_VERSION`.

`memory.store.rebuild` makes this worse than a mislabel. It **raises** on an uninterpretable
fact write, so the first bump of `FACT_PAYLOAD_VERSION` would have made every store rebuild fail
outright. That landmine was armed and had not been stepped on.

## Options considered

**Bump `READER_VERSION` in step with the schemas.** The smallest diff, and it preserves the
conflation for the next person. It also cannot work: one number cannot follow four independent
ones, so it would only ever be right for whichever schema moved last.

**Put all four schemas on one number line.** Makes the scalar comparison coherent, and
reintroduces precisely the failure clause 3 was written to prevent — a Ruling change marking
unchanged Declarations as unknown.

**Per-type reader versions**, a map from entry type to the highest floor this reader can meet.
Faithful to clause 3, and more machinery than the problem needs while the answer is 1 everywhere.
Worth revisiting if a floor ever genuinely rises for one payload and not others.

**Take clause 4 literally and amend clause 5.** Chosen.

## Decision

**1. `compat` is a reader version.** Clause 4's definition is the operative one. Clause 5's
"raises it to the new version" is amended to **"raises it to the lowest reader version that can
read it correctly"**, which is the only reading consistent with clause 4 and with clause 3's
independent schema versions.

**2. Every payload names its floor in its own constant**, declared beside the schema version it is
not. `DECLARATION_COMPAT`, `RULING_COMPAT`, `NARRATION_COMPAT`, `TERMINATION_COMPAT`,
`FACT_PAYLOAD_COMPAT`, `SESSION_COMPAT` — all 1. The constant exists so the two numbers cannot be
confused for one another again by someone reaching for the nearest version-looking name.

**3. A floor rises only when the reading surface in this repository changes** such that an older
one would get the payload wrong. Not when the payload changes. Schema versions move freely and
independently, which is what clause 3 asked for and what clause 5 was accidentally preventing.

**4. `READER_VERSION` is the reader's own version**, not "the highest payload schema version this
reader knows how to interpret" — which is what its docstring said, and is the defect in prose.

**5. The reading surface is `read_ledger`, `replay`, and `session_report` together.** A change
that breaks any of them is what raises `READER_VERSION`, because a consumer holding an old build
holds all three.

**6. A guard reads a ledger the engine actually wrote.** `tests/test_replay_and_report.py` asserts
every entry a real adjudication produces is interpretable by the reader shipped alongside it, and
that no writer derives a floor from a schema version. The second is checked by *shape* rather than
by outcome, so `COMPAT: SOME_VERSION` fails in CI rather than in somebody's ledger.

## Why

### Schema evolution was never handled by `compat` anyway

`replay_entry` already copes with an older ruling payload **structurally**: a roll with no
`declared_advantage` is reported `UNREPLAYABLE` with a message naming `REPLAYABLE_FROM`, because
replaying it as though it had none would roll one die where two were rolled and report a mismatch
indistinguishable from real drift.

That is the mechanism that actually protects a reader from a payload it cannot handle, and it
inspects the payload rather than trusting a number in it. `compat` was carrying a job something
else was already doing, in a currency it did not have.

### Two audiences, two mechanisms, and conflating them is the same mistake one level up

#105 changed what `Effect.amount` **means** for damage. An external consumer reading `amount` from
a v2 payload as though it were v3 gets a different total for the same fight — so that change
raised `API_VERSION` to 2 (0018), which is the mechanism for *consumers of the types*.

It did **not** raise the ruling's `compat` floor, because nothing in this repository's reading
surface reads `amount`: `replay` re-derives rolls, and `session_report` reads status, rule ids,
alternatives, rolls and narration. The reader is fine. The consumer is not, and is told so through
the number that speaks to it.

Answering "can this build read this file" and "does the code I wrote against still behave" with
one integer is the same error as answering "what shape is this payload" and "which reader can read
it" with one integer. 0011 clause 3, 0018 clause 5 and this record are three applications of the
same rule.

### The floor will now rarely move, and that is the honest outcome

A floor that rises on every schema bump is not conservative, it is uninformative — it marks
readable payloads unreadable, and a signal that fires constantly is one consumers learn to ignore.
`compat` is worth having precisely because it is rare.

## Consequences

**Accepted costs.**

- **`compat` now looks inert**, sitting at 1 for every payload, and will until the reading surface
  genuinely breaks. That is the point, and it will read as dead weight to anyone who meets it
  before it has ever moved.
- **The floor is a hand-maintained claim.** 0011 already named this: "a wrong `compat` claim fails
  silently, in the direction of misparsing rather than refusing." Naming each floor separately
  makes the claim deliberate; it does not make it automatic.
- **`READER_VERSION` covers three modules**, so a change to `session_report` alone raises the
  floor for `replay` too. Coarse, and correct while they ship in one distribution — the clause
  that has to change if that ever splits, exactly as 0018 clause 6 says of adapters.
- **Per-type reader versions were declined**, so the first payload that genuinely needs a floor
  above another's will reopen this. The map is the answer waiting there.

**Follow-on effects.**

- `memory.store.rebuild`'s raise is defused: a fact payload schema bump no longer makes every
  store rebuild fail.
- A test that asserted `compat >= REPLAYABLE_FROM` was rewritten. It encoded the derivation this
  record forbids, and the protection it was reaching for is covered directly by
  `test_a_roll_recording_no_advantage_is_unreplayable_not_assumed_plain`.

## Evidence

The broken state was read off a real ledger before anything was changed, not inferred from the
code — the table above is verbatim output. The fix was then confirmed by restoring the exact
defect (`COMPAT: RULING_VERSION`) and watching all four guards go red, and by raising
`RULING_COMPAT` above `READER_VERSION` without touching the schema, which turns the two
floor-specific guards red on their own.

## Status of implementation

**Implemented in full.** All six clauses.

| Clause | State |
|---|---|
| 1 — `compat` is a reader version | The definition governs; clause 5 of [0011](0011-module-layout-and-versioning.md) reads as amended here. |
| 2 — every payload names its floor in its own constant | All six exist and all six are 1: `DECLARATION_COMPAT`, `RULING_COMPAT`, `NARRATION_COMPAT`, `TERMINATION_COMPAT` (`core.adjudicate`), `FACT_PAYLOAD_COMPAT` (`core.memory_port`), `SESSION_COMPAT` (`core.ledger`). |
| 3 — a floor rises only when the reading surface changes | Demonstrated since: `RULING_VERSION` moved 3 → 4 for [#119](https://github.com/eddiefiggie/srd-rules-engine/issues/119)'s condition fields and `RULING_COMPAT` stayed at 1, because the change was additive and a v3 reader misreads none of it. |
| 4 — `READER_VERSION` is the reader's own version | `core.ledger_reader.READER_VERSION`, with the docstring defect this record names corrected. |
| 5 — the reading surface is the three together | `read_ledger`, `replay` and `session_report`. |
| 6 — a guard reads a ledger the engine actually wrote | `tests/test_replay_and_report.py`, checking the no-derived-floor rule by **shape**, so `COMPAT: SOME_VERSION` fails in CI rather than in somebody's ledger. |

Clause 3 is the one worth noting as *exercised* rather than merely built. The failure this record
exists to prevent is a floor rising because a payload changed, and #119 was the first payload
change after it landed — the schema moved, the floor did not, and the guard did not have to say
anything. A decision holds when the next change makes it uneventful.

_Added 2026-08-24 ([#126](https://github.com/eddiefiggie/srd-rules-engine/issues/126)). This record carried no **Status of implementation** section, so a reader could not tell "shipped" from "nobody wrote one"._
