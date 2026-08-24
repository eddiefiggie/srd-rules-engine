# 0011 — Layer boundaries are a guard test, and schemas carry a min-reader floor

- **Status:** Accepted, 2026-08-22. **Clause 5 amended by**
  [0022 — `compat` is a reader version](0022-compat-is-a-reader-version.md), 2026-08-23: a floor
  rises to the lowest *reader* version that can read the payload, never to the payload's own
  schema version. Clauses 3 and 4 stand and are what that record enforces.
- **Settles:** [#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13)
- **Requirements:** R33, R34, R35 · touches R8, R20, R23, R24, R26
- **Related:** [0006 — ledger format](0006-ledger-format.md) froze the envelope this must live
  inside; [0007](0007-alternatives-verification.md) supplies the read token;
  [0008](0008-extension-channel.md) supplies the consumer-declared namespace versions.
  The v1.0 stability policy is [#39](https://github.com/eddiefiggie/srd-rules-engine/issues/39)

## Context

Build `08212026.1` settled the packaging half of this gate — hatchling, `src/` layout, `py.typed`,
`requires-python >=3.11`, and R33 expressed as an empty `dependencies` list. Two things remained:
module layout, and schema-versioning mechanics.

It was deliberately held until last, because module layout depends on what modules turned out to
exist, and by now they do. It has also accumulated a scope no single earlier gate would have
predicted.

### The layout risk runs both ways, and the more dangerous direction was unnamed

The issue names one: if the turn loop imports freely from the core's internals, then R34's
"adapters built over the same contract" becomes untrue, because adapters would really be built
over whatever the loop happened to reach for.

The other direction is worse. **If the core imports outward** — from the loop, an adapter, the
reference memory implementation — then R33's promise dies while `dependencies = []` continues to
read empty. The machine-readable form of the promise stays true and the promise does not, which is
the failure mode that form of guarantee exists to prevent.

Both directions are visible in the import graph, and neither is visible in a dependency list.

### Seven versioned things, of three different kinds

By the time this gate came up the list had grown well past R35's original three:

| Thing | Kind |
|---|---|
| Declaration schema | Engine-defined data |
| Ruling schema | Engine-defined data |
| Memory-port core schema | Engine-defined data |
| Ledger payload | Engine-defined data ([0006](0006-ledger-format.md)) |
| Ledger reader API | Public code surface (R35 as amended) |
| Read token ([0007](0007-alternatives-verification.md)) | Opaque engine-internal value |
| Extension namespaces ([0008](0008-extension-channel.md)) | **Consumer-declared, never interpreted** |

A scheme built only for "compare the version, dispatch or reject" covers the first four and none
of the rest.

### The build stamp carries no compatibility information

`mmddyyyy.x` says which build. It cannot say what that build is compatible with, and R35 promises
public API that is versioned. That gap is harmless while nothing is implemented and is not
harmless at v1.0.

## Options considered

- **Documented convention for the layer boundary.** Rejected. No new machinery, and no false
  confidence from a guard that only sees static imports — but it makes "the core is LLM-free" a
  claim maintained by attention, which this project has structurally refused everywhere else.
- **Separate distributions per layer.** Rejected. The strongest separation available: an adapter
  genuinely cannot import what is not installed. It costs a multi-package release process and
  cross-package version coordination, for a project that has not shipped once. Reachable later,
  and the guard test is what would keep the boundary clean enough to make the split easy.
- **One version across all four data schemas.** Rejected. It makes every reader treat every schema
  as changed whenever any one of them does, manufacturing exactly the false-unknown the compat
  mechanism exists to avoid.
- **No compat signal — unknown means unreadable.** Rejected, and it is the strongest alternative.
  It is simpler, adds nothing to any payload, and cannot let a wrong claim cause a misparse. It
  loses the additive case, which is most cases, across the long-lived archives
  [0004](0004-trigger-catalogue.md)'s audit is meant to read.
- **Encoding version and floor together in `v`.** Rejected. It stays within what
  [0006](0006-ledger-format.md) permits, and packing two values into one field ages badly — `v`
  stops being a number to compare and becomes a string to parse.
- **Semver alongside the date stamp now**, and **per-surface stability declarations.** Both
  rejected as premature rather than wrong. See decision 8.

## Decision

**1. Four layers, as packages.**

| Package | Contents |
|---|---|
| `core` | Adjudication, read surface, legality derivation, ledger writer and reader, trigger matcher, the memory-port protocol |
| `loop` | The turn loop of R8 — outside the core, per R33 |
| `memory` | The file-backed reference port implementation of R23 and [0009](0009-reference-memory-store.md) |
| `adapters` | MCP, HTTP, CLI (R34), each declaring its own extras |

**2. Two import rules, enforced by a guard test.** A test parses every module's imports and fails
on either violation:

- **Nothing in `core` may import from an outer layer.** This is R33's promise in its checkable
  form, and it catches what a dependency list cannot.
- **Nothing outside `core` may import a `core` submodule.** Outer layers use `core`'s re-exported
  surface only — `from srd_rules_engine.core import X`, never
  `from srd_rules_engine.core.adjudicate import Y`. That makes "the contract" a fact about the
  import graph rather than a description of intent, so R34's "built over the same contract" is
  checkable.

The guard is proven red before it is trusted: introduce each violation, confirm the test fails,
restore.

**3. The four engine-defined data schemas version independently, as monotonic integers.** Not
semver — a data schema's only question is "can I interpret this", and there is no useful meaning
for a minor bump. A change to the Ruling must not make a reader treat unchanged Declarations as
unknown.

**4. Every payload carries a reserved `compat` key at a fixed top-level position**, stable across
all versions of that payload: **the lowest reader version that can correctly interpret it.**

A reader at version 3 meeting `v=5, compat=2` interprets it. Meeting `v=5, compat=4` it reports
the payload **unauditable** — [0004](0004-trigger-catalogue.md)'s word, and its requirement.
Combined with [0006](0006-ledger-format.md)'s always-readable envelope, that gives three tiers
rather than two: structurally readable, interpretable, and neither-known-nor-claimed-compatible.

`compat` lives in the payload because 0006 froze the envelope permanently. It is now the second
permanently reserved name in the format, and that is stated here so it is not rediscovered.

**5. A version bump raises `compat` only when an older reader would get it wrong.**
*(Amended by [0022](0022-compat-is-a-reader-version.md): the floor rises to the lowest **reader**
version that can read the payload, never to the payload's own schema version. Deriving one from
the other made every ruling entry unreadable — see that record.)* Adding an
optional field a reader may ignore leaves `compat` where it was. Removing a field, changing a
field's type or meaning, or adding a field a correct reading requires, raises it to the new
version.

**6. The read token needs no external version.** It is opaque and only the engine reads it, so it
carries whatever internal marker it needs. An unrecognised token is not an error condition
requiring new vocabulary — [0007](0007-alternatives-verification.md) already defined `unread`, and
that is the correct verdict.

**7. Extension namespace versions are stored, never interpreted.** They are consumer-declared
strings ([0008](0008-extension-channel.md)). Absent or malformed is **not an error** — the engine
records what it was given and returns it unchanged, because it has no basis for an opinion.

**8. The date stamp identifies a build and makes no compatibility claim; the public code API is
unstable until v1.0.** Both stated plainly rather than left implied. A stability policy is a v1.0
release requirement, filed as
[#39](https://github.com/eddiefiggie/srd-rules-engine/issues/39). Writing one before any API
exists would be writing it blind; filing it now is what keeps it from being written late.

Data schemas are unaffected by this — they carry their own versions from the first entry, and they
are the real compatibility contract for anything reading a ledger or speaking to the port.

## Why

### The dependency list guards one thing and the import graph guards the other

R33's empty `dependencies` is a genuinely good guarantee, and it has a blind spot: it constrains
what the *package* pulls in from outside, not how the package's own layers depend on each other. A
core module importing an adapter adds no third-party dependency at all. The promise "the core takes
no LLM dependency" would be violated by a core that imports an adapter which imports an LLM
extra — and the empty list would still be empty.

Reading imports closes that, and it happens to close the other direction in the same pass. Two
rules, one traversal, one test.

### Most schema changes are additive, and a bare version number cannot tell

Over a long-lived ledger the common change is a new optional field. Under a bare version number
every one of those makes older readers report the payload as unreadable, and
[0004](0004-trigger-catalogue.md)'s retrospective audit — the only mechanism that measures trigger
recall at all — reads exactly those old archives.

The floor is also cheap to add now and lossy to add later. It lives in the payload, so it is not
blocked by 0006's frozen envelope; but payloads written before it exists have no floor, and a
reader must treat their absence as "assume incompatible." Deciding it at the same moment the
schemas are defined avoids ever having that generation.

The honest cost is that `compat` is a claim, and a wrong one lets an old reader misparse silently
rather than refuse loudly. That is the mechanism's failure mode and it belongs in tests: a schema
change that raises `compat` incorrectly is exactly the kind of thing a round-trip test across
adjacent versions catches.

### Three kinds of versioned thing, because forcing one mechanism would break the odd ones

The temptation with seven items is a single uniform scheme. It would not survive contact with two
of them.

The **read token** is opaque and engine-internal; giving it a public version would publish an
implementation detail and invite consumers to reason about it. The **extension namespace version**
is declared by someone else and never compared against anything — a uniform "compare and dispatch"
mechanism has nothing to compare it to, and treating a malformed one as an error would make the
engine police a namespace it explicitly does not interpret.

Naming three kinds is more vocabulary than one, and it is the vocabulary the system actually has.

### Deferring the stability policy, but not silently

The rejected alternatives — semver now, per-surface declarations — are both defensible and both
require knowing what the API is. It does not exist. A policy written now would describe an
imagined surface, and the usual outcome is that it is quietly ignored once the real one appears.

What makes deferring safe rather than convenient is that it is filed against v1.0 with the
constraints it inherits already written down. The failure this repository has seen before is a
deferral that lives in prose and is never queued; this one is an issue.

## Consequences

**Accepted costs.**

- **The import guard sees static imports only.** `importlib`, a deferred import inside a function,
  or a string-driven plugin loader all evade it. The guard is a floor, not a proof, and saying so
  here prevents it being cited as more than it is.
- **`compat` is permanently reserved**, the second such name after 0006's envelope fields. Every
  future payload schema inherits it whether or not its author read this record.
- **The layout is committed before the code exists.** Some churn is likely as M1 reveals what
  actually belongs where — and the guard test will make that churn loud, which is the intended
  behaviour and will occasionally be annoying.
- **A wrong `compat` claim fails silently**, in the direction of misparsing rather than refusing.
- **The stability policy is deferred**, so between now and v1.0 a consumer building against the
  reader API has no guarantee. Stated in the README rather than left for them to discover.

**Follow-on effects.**

- **R33 is amended** with the core-imports-nothing-outward rule, **R34** with the layer packages
  and the re-exported-surface rule, and **R35** with independent integer schema versions, the
  `compat` floor, the three kinds of versioned thing, and the pre-1.0 instability statement.
- **[#39](https://github.com/eddiefiggie/srd-rules-engine/issues/39)** filed against v1.0.
- **Two guard tests to write**, both proven red first: the layer-import guard, and a
  schema-round-trip guard checking that a reader at version N correctly interprets any payload
  declaring `compat <= N`.
- **This closes the last design gate.** M0 remains open on
  [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3), which is an errand rather than a
  design question — it needs the official SRD v5.2.1 document — and it gates data, not code.

## Evidence

No spike. The import guard is demonstrable in a few lines: parse each module with `ast`, collect
`Import` and `ImportFrom` targets, map each module to its layer by path, and assert the two rules.
It requires nothing beyond the standard library, which matters because it runs in the same suite
as the R33 guard it complements.

The compat mechanism is checkable by construction: write a payload at version N, add an optional
field at N+1 without raising `compat`, and confirm an N-reader still interprets it; change a
field's meaning at N+2 while raising `compat`, and confirm the N-reader now declines.

A note on method: this gate was held until last on the reasoning that module layout depends on
what modules exist. That was right, and it had a second benefit nobody planned — the versioning
half arrived with **seven** items rather than R35's original three, five of them contributed by
gates settled in the interim, and two of those five do not fit the obvious mechanism. Settled
first, this would have produced a uniform scheme that the read token and the extension namespace
would each have had to be bent to fit.

## Status of implementation

**None.** M0 holds that nothing is built until the gates close, and this is the last of them.
Layout and both guard tests land with the first code, when M1 opens.
