# 0018 — Three stability tiers, an integer API version, and a committed surface that is enumerated

- **Status:** Accepted, 2026-08-23
- **Settles:** [#39](https://github.com/eddiefiggie/srd-rules-engine/issues/39)
- **Requirements:** R35 · touches R20, R34
- **Related:** [0011 — module layout and versioning](0011-module-layout-and-versioning.md), whose
  decision point 8 deferred this; [0006 — ledger format](0006-ledger-format.md), which fixes the
  envelope permanently; [0016 — adapters hold the turn](0016-adapters-hold-the-turn.md), which
  created the newest surface

## Context

0011 settled that the build stamp carries no compatibility information — `mmddyyyy.x` says which
build, not what it is compatible with — and left the code API "explicitly unstable until v1.0". Data
schemas were covered: each carries a monotonic integer version and a `compat` floor.

The code surface was not, and it has since grown a transport. The MCP tool list is now the first
thing a consumer could build against without reading any Python at all, which is what makes this
worth settling rather than deferring again.

## The fact that decides the shape

**`srd_rules_engine.core` re-exports 110 names.** `loop` exports 17, `adapters` 7.

A policy promising stability across 110 symbols is promising something nobody can keep, and everyone
would know it. Most of those names exist because R34 requires outer layers to use what `core`
re-exports rather than reaching into submodules — they are there to satisfy an import rule, not
because a consumer was ever meant to depend on them.

So the question is not "how stable is the API" but **which of it is an API at all**.

## Options considered

**Semver for the distribution.** Familiar, and it implies one number describes the whole package.
That is the opposite of what is true here: the ledger envelope is permanently fixed, the memory port
is a protocol consumers implement, and the MCP tool list is young and expected to move. One number
would have to be governed by the least stable of them, which would make every tool-name change a
major version.

**Per-surface stability levels with no version number.** Honest and unactionable — a consumer cannot
diff a promise.

**Promise the whole of `core.__all__`.** Rejected on the count above.

**Three tiers plus one integer.** Chosen.

## Decision

**1. Three tiers, and each surface is assigned to one.**

| Tier | Meaning | Surfaces |
|---|---|---|
| **Committed** | Breaking it raises `API_VERSION`. Enumerated in `srd_rules_engine.stability`. | The ledger reader API (R35), the memory port protocol (R20), the turn loop's typed requests and responses (0001), the adapter session's `Pending` states (0016), and the named types a Ruling is made of |
| **Provisional** | Named, documented, expected to move. A change is recorded in the changelog and does not raise `API_VERSION`. | The MCP tool names and their argument schemas |
| **Internal** | Everything else, including most of `core.__all__`. Importable, unpromised. | The rest |

**2. `API_VERSION` is a monotonic integer, independent of everything else.** Not semver, for the
same reason 0011 gave the data schemas: the only question a consumer asks is "does what I built
against still work", and there is no useful meaning for a minor-versus-patch distinction on that.

It is independent of the build stamp (which identifies a build), of the data schema versions (which
answer "can I interpret this file"), and of the package version.

**3. The committed surface is enumerated, not described.** `srd_rules_engine.stability.COMMITTED`
lists it by name, and a test asserts every name resolves and that the set has not changed. Removing
or renaming a committed name turns that test red, which forces the removal to be a decision rather
than a diff nobody noticed.

**4. A committed name is not removed without a deprecation period.** It stays importable for at
least one `API_VERSION` after the replacement lands, and emits `DeprecationWarning` naming the
replacement. A consumer discovers a deprecation by running their own tests, which is the only
mechanism that works without a release announcement anybody reads.

**5. Schema versions and `API_VERSION` are orthogonal, permanently.** A schema bump need not be an
API break — adding an optional field to a ledger payload changes neither the reader's signature nor
its behaviour. An API break need not touch a schema — renaming a function changes no file on disk.
0006 drew this line between engine version and schema version for the same reason, and it holds.

**6. Adapters version with the core**, because 0011 kept them in one distribution. If that ever
splits, this clause is what has to change with it.

**7. Nothing here can relax the two fixed points.** The ledger envelope can never change (0006) and
the payload's reserved `compat` key is fixed alongside it (0011). Those are committed regardless of
what `API_VERSION` says, and this record does not have the authority to loosen them.

## Why

### Enumerating is the only version of this promise that survives contact

A policy in prose degrades the moment somebody renames a symbol during a refactor and nobody
connects it to the document. This project has already demonstrated the failure twice: `source.section`
in the effect-shape inventory was wrong for five sweeps because it was a hand-written literal nobody
compared to the data, and a no-prose guard passed while inspecting nothing because it tested content
rather than shape.

An enumerated list with a test is the same fix applied a third time. It cannot drift, because
drifting is what turns it red.

### Provisional is a real tier, not a hedge

The MCP tool list is six names old. Committing to it now would either freeze a first draft or make
`API_VERSION` meaningless within a month. Saying so is more useful to a consumer than a promise that
will be quietly broken — and the tier is bounded: the *session* underneath the tools is committed,
so a consumer who wants stability can build on `adapters.Session` rather than the tool names.

### The integer is not a smaller semver

Semver's minor-versus-patch split answers "may I upgrade without reading". For this surface there is
no such distinction: either what you built against still resolves and behaves, or it does not. A
number that only ever means "something committed changed" is honest about carrying exactly one bit
of information.

## Consequences

**Accepted costs.**

- **Most of `core.__all__` is explicitly unpromised**, which will surprise anyone who assumed a
  re-export was a contract. It is stated rather than implied, and R34's import rule is why the list
  is long.
- **The committed list is maintained by hand.** Adding a surface means adding a name; the test
  catches removal but cannot know that a *new* thing should have been committed.
- **`API_VERSION` starts at 1 with nothing to compare against.** Its value arrives later, and the
  cost of starting it now is one integer.
- **Deprecation has no release cadence to hang on**, so "one API version" is the unit rather than a
  time period. That is weaker than a dated policy and it is what the project's release model
  supports.

**Follow-on effects.**

- v1.0's definition of done gains a check: `API_VERSION` is 1 and the committed surface is whatever
  it is at that point.
- A future adapter (HTTP, CLI) inherits the tiers without a new decision — its transport surface is
  provisional, the session under it is committed.

## Evidence

Surface sizes were counted rather than estimated: `core.__all__` 110, `loop.__all__` 17,
`adapters.__all__` 7, MCP tools 6. The data schemas already carry independent monotonic versions —
`FORMAT_VERSION` 1, `READER_VERSION` 1, `DECLARATION_VERSION` 1, `RULING_VERSION` 2,
`FACT_PAYLOAD_VERSION` 1, `effect_shapes` 1, `bestiary` 1 — which is the precedent clause 2 follows.

## Status of implementation

**Implemented with this record**, in `srd_rules_engine/stability.py`, with a guard test that pins
the committed set and is proven red by removing a name from it.
