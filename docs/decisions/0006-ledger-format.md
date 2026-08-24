# 0006 — JSONL with a fixed envelope, and a reader API rather than a public file format

- **Status:** Accepted, 2026-08-22
- **Settles:** [#10](https://github.com/eddiefiggie/srd-rules-engine/issues/10)
- **Requirements:** R26, R28, R30, R35 · touches R8, R33
- **Related:** [0002 — ledger durability](0002-ledger-durability.md), whose chain this makes
  implementable; [0004 — the trigger catalogue](0004-trigger-catalogue.md) and
  [0005 — retry bounds](0005-retry-bounds.md), which each added an entry requirement.
  Schema-versioning *mechanics* are [#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13)

## Context

The ledger is append-only (R26), must support exact replay (R28) and report generation (R30), and
three settled records have since told it what to carry: `seq` / `sum` / `prev` and a torn-tail
rule from [0002](0002-ledger-durability.md), the trigger-catalogue version on declarations from
[0004](0004-trigger-catalogue.md), and a retry-exhaustion terminal entry from
[0005](0005-retry-bounds.md).

Behind the format sat a larger question: whether the ledger is *also* the interchange format for
sharing a session, in which case every field is a compatibility commitment. Deciding late means
deciding by accident, because the first person to parse a ledger file makes it an interface
whether or not anyone intended it.

Two things turned up that reshaped the question.

### 0002's hash chain is not implementable as specified

0002 requires each entry to carry "a checksum of its own body, and the digest of the previous
entry." It never said **how bytes are derived from an entry**, because format was not its gate.

JSON has no canonical form. Key order, whitespace, unicode escaping, and number formatting all
vary between serializers and between language runtimes. Two writers disagreeing on any of them
produce a chain that fails to verify against a file with nothing wrong with it — and it fails as
*tamper detected*, which is the worst available misdiagnosis. The chain would have been a
liability rather than a safeguard.

So this gate has to fix a canonicalization rule, not merely a format.

### R35 had already answered half the interchange question

R35 makes the Declaration, Ruling, and memory-port schemas versioned public API today. The
contents are therefore committed already, and the open question is narrower than it looked: is the
**envelope** public — the framing, the chain, the file layout?

That reframing matters, because it makes the asymmetry visible. Publishing an envelope later is
cheap; unpublishing one is not. And the issue's own warning is correct: declaring the envelope
private does not survive a readable format.

## Options considered

### Whether the file is public API

- **Commit to the on-disk format as public API.** Rejected. It makes session sharing free — the
  case 0002 named when it kept the hash chain — but it freezes every field before the engine has
  been written once, at the moment the design knows least.
- **Keep the file private and ship a separate export format.** Rejected. An export has to carry
  the replay inputs to be worth anything, and R5 established that those *are* the Ruling's
  contents. The export would be a near-duplicate of the ledger with a second serializer, a second
  schema, and a standing obligation to keep the two in step.
- **A reader API as the supported interface.** Adopted.

### Format

- **SQLite in append-only discipline.** Rejected, though it was the closest call. It is in the
  standard library, so R33 holds; it brings atomic commits and durability primitives; and its
  indexes would genuinely help [0004](0004-trigger-catalogue.md)'s cross-session retrospective
  audit. Against that: append-only becomes discipline over a mutable B-tree rather than a property
  of the medium, which is a poor fit for a record whose whole value is that it cannot be quietly
  rewritten. A corrupted database is also far harder to inspect or salvage than a text file with
  one bad final line — and 0002's crash model showed the torn tail is the reachable failure.
- **Length-prefixed binary log.** Rejected. Best-in-class torn-tail detection and no
  canonicalization ambiguity, bought by giving up human inspectability entirely, on a workload —
  solo play, one character — with no performance pressure to justify the trade.
- **JSONL, one entry per line.** Adopted.

### Replay scope

Best-effort cross-version replay was rejected because, with no version pinned, a difference is
ambiguous between a deliberate rules fix, a data change, and real corruption — and the report
cannot tell the reader which. Fully self-describing entries were rejected as requiring the rule's
*logic* to be serialized rather than its inputs, which is a far larger commitment than R28 asks
for.

## Decision

**1. JSONL. One entry per line, appended, never rewritten.** Several entries may be written into
the buffer before the single `fsync` 0002 requires at the escape boundary.

**2. The envelope is fixed for good; the payload is versioned.**

| Field | Meaning |
|---|---|
| `seq` | Monotonic integer, gap-free |
| `type` | `session` \| `declaration` \| `challenge` \| `rejection` \| `ruling` \| `fact-write` \| `narration` \| `exhaustion` |
| `v` | Payload schema version |
| `prev` | The previous entry's `sum`. Absent on `seq` 0 |
| `sum` | Digest over the canonical form of the entry with `sum` omitted — so it covers `seq`, `type`, `v`, `prev`, and `payload` |
| `payload` | Versioned by `v` |

Chain verification, sequence checking, and entry listing depend only on the envelope, so **they
work across every version ever written**. Only payload interpretation — replay, reporting details
— requires a version the reader knows. The retrospective audit reads the payloads it understands
and reports the rest as **unauditable**, never skipping them silently.

**3. The canonical form is RFC 8785 (JSON Canonicalization Scheme), restricted to exclude
floating-point numbers.** UTF-8, object keys sorted, no insignificant whitespace.

**4. No binary floating-point value may appear in a ledger entry.** This is what makes point 3
implementable without a dependency: JCS's genuinely hard part is ECMAScript number serialization,
and the domain does not need it. Dice, damage, DCs, AC, hit points, modifiers, spell slot levels,
and distances in feet are all integers.

The SRD's few fractional quantities — challenge ratings of 1/8, 1/4, 1/2, and item weights — are
carried as **exact strings or integer subunits**, never as doubles. A guard test rejects a float
anywhere in an entry, and is proven red before it is trusted.

This is not only a canonicalization convenience. `0.1 + 0.2 == 0.3` is false, and a record whose
purpose is to be authoritative about what happened should not contain values that are
approximately what they say they are.

**5. Entry `seq` 0 of a file is a `session` entry** carrying the file format version, the **engine
version**, the trigger-catalogue version at open, and a session identifier. It participates in the
chain like any other entry, so the header cannot be swapped without breaking it.

**A session may not span engine versions.** Reopening a ledger under a different engine appends a
**new `session` entry** rather than continuing the old one. Every entry's governing engine version
is therefore the nearest preceding `session` entry, which makes the question always answerable and
never inferred.

**6. R28's guarantee holds within an engine version, and cross-version replay is reconciliation,
not corruption.** Replaying an entry whose governing engine version differs from the running one
produces a **reconciliation result** — outcomes differ, versions differ, here are both — and never
an integrity verdict. This is the same distinction 0004 drew between replay and audit, applied to
the rules code rather than the catalogue.

**7. A torn tail is reported, and repair is explicit.** A trailing line that fails to parse, whose
`sum` does not verify, whose `seq` is not its predecessor's plus one, or whose `prev` does not
match, is rejected. The reader **reports** it and offers truncation to the last valid entry as an
explicit operation. It never truncates silently, and it never refuses to open the file — a crashed
session must be reopenable, and 0002 guarantees nothing escaped the engine, so discarding the
fragment is safe once a human has been told.

**8. A shipped reader API is the supported interface; the file is an implementation detail.** The
reader opens and verifies a ledger, iterates envelopes across all versions, exposes typed payloads
for known ones, replays, feeds R30's report, feeds the retrospective audit, and produces a session
export. Export is a **function of the reader**, not a second format.

**9. Schema-versioning mechanics go to [#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13).**
This record fixes that `v` exists, that it versions the payload only, and what a reader does with
an unknown value. How versions are declared, negotiated, and migrated is that gate's, and there
should be one mechanism across the Declaration, Ruling, memory-port, and ledger-payload schemas
rather than two.

## Why

### A reader API is the promise in structural form

The project has now made the same move three times: 0002 expressed "no runtime dependencies" as an
empty `[project].dependencies`, 0004 kept the free-text label out of the matcher's scope rather
than forbidding its use, and this record puts a reader between consumers and the bytes. In each
case the alternative was a rule someone has to remember, and the chosen form is one where
forgetting is not possible.

Here the failure being prevented is specific. If consumers parse the file, the file is the
interface, and the first bug fix that changes a field breaks them — after which the format is
frozen by other people's code rather than by anyone's decision. A reader gives them something
stable to depend on that the project intends to keep stable, which is the only version of this
promise that survives contact with users.

It also costs nothing that was avoidable. Replay, R30's report, and the retrospective audit are
three readers already required. Naming the shared surface and shipping it is a smaller change than
maintaining a second export format would have been.

### JSONL because the product is auditability

The performance case for a binary log is absent, and the structural case for SQLite is real but
points the wrong way: it offers transactional mutation to a design whose value proposition is that
entries cannot be quietly rewritten. Append-only-by-discipline is exactly the kind of guarantee
this project has consistently refused to accept.

What JSONL buys is that a person can read the ledger. For an engine whose purpose is that
outcomes are explainable after the fact, a record you can open in an editor and follow is not a
convenience — it is the feature working at the last possible level.

### Excluding floats is a correctness decision that happens to be convenient

The canonicalization argument is real but secondary. The primary reason is that a ledger entry is
a claim about what happened, and binary floating point cannot represent most decimal fractions
exactly. A recorded damage total or distance that is *nearly* the value it prints is a defect in a
record designed to be authoritative — and it is a defect that would surface first as a replay
mismatch on a different platform, which is the most confusing possible symptom.

Discovering that the domain has no need for floats at all turned a hard constraint into a free
one.

### Cross-version replay had to stop claiming what it cannot do

0004 found that a growing catalogue makes replay report sound ledgers as corrupt, and fixed it by
pinning the catalogue version. The same defect sits one level up and is easier to miss: **the
rules code is an input to the outcome too.** Fix a bug in a rule and every prior entry that
exercised it now replays differently.

Pinning the engine version does not enable replay under old rules — that would need the old code.
What it buys is that the failure explains itself. "Outcomes differ, and so do the versions" sends
a reader to a changelog. "This ledger is inconsistent" sends them looking for corruption that is
not there, in the one artifact the whole design asks them to trust.

## Consequences

**Accepted costs.**

- **The envelope can never change.** Five fields are committed for the life of the project, before
  a line of the engine exists. They were chosen to be the minimum that supports integrity checking
  and dispatch, and the payload carries everything else — but a mistake here is permanent.
- **JSONL is larger than a binary log** and offers no random access. Replay of a specific entry
  means scanning, and the retrospective audit scans whole files. Acceptable at solo-campaign
  scale; it would not be at another.
- **The no-float rule constrains every future payload**, including ones nobody has designed yet.
  A future mechanic wanting a genuine real number has to represent it exactly instead, and the
  guard test will make that non-negotiable at the moment it comes up.
- **A reader API is public surface to maintain**, and versioning it is a real obligation. It is
  smaller than the file's surface would have been, but it is not nothing.
- **Sessions cannot span engine versions.** An upgrade mid-campaign starts a new session entry,
  which is a slightly odd artifact in a long-running ledger and the price of every entry having an
  unambiguous governing version.

**Follow-on effects.**

- **[#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13) inherits the versioning
  mechanism**, and should cover the ledger payload alongside the R35 schemas rather than letting a
  second scheme grow.
- **[#8](https://github.com/eddiefiggie/srd-rules-engine/issues/8) has a place to put the offered
  alternatives.** 0005 noted an exhausted slot carries them with no Ruling to attach to; the
  `exhaustion` entry type is that place. What still needs settling there is how the offering is
  captured given R19 forbids the read surface from appending.
- **R26 is amended** with the envelope, the canonical form, the no-float rule, and the `session`
  entry. **R28 is amended** to scope its guarantee to a matching engine version and to define the
  cross-version result as reconciliation. **R30's report** names the engine version alongside the
  catalogue version.
- **The reader API joins R35's list of versioned public API.**
- A guard test rejects floats in entries; another verifies that a canonicalization round trip is
  stable. Both are proven red before being trusted.

## Evidence

No spike beyond a domain check, which is reproducible in a few lines: enumerate the values a
ledger entry actually carries — dice results, damage, DCs, AC, hit points, modifiers, slot levels,
distances in feet — and confirm every one is integral. Then enumerate the SRD's fractional
quantities: challenge ratings of 1/8, 1/4, and 1/2, and item weights. None of them is a value the
engine computes with; all are exactly representable as strings or integer subunits.

The float hazard is demonstrable in one line — `0.1 + 0.2` is `0.30000000000000004` — and the
serializer-divergence hazard in two, since shortest-round-trip representations of values like
`1e+22` and `5e-324` are formatted differently by different runtimes while denoting the same
double.

A note on method: this gate was very nearly settled without a canonicalization rule at all. The
question "what format?" does not naturally surface it, because JSONL answers the framing question
completely and the chain looks like it was already settled by 0002. It surfaced only when checking
what 0002 had actually specified about `sum` — which is an argument for re-reading a record's
exact wording rather than a summary of it, including one's own.

## Status of implementation

**Implemented.** `core/ledger.py` carries the JSONL container, `ENVELOPE_FIELDS`, and
`FORMAT_VERSION`; `core/canonical.py` is the RFC 8785 canonical form with floats excluded;
`core/ledger_reader.py` is the reader API, with `LedgerReport`, `Finding`, `CHAIN_BREAK` and
`CHECKSUM_MISMATCH`. Entry `seq` 0 is the `session` entry carrying the format, engine and
catalogue versions.

One clause has been amended since: [0022](0022-compat-is-a-reader-version.md) settles that `compat`
is a **reader** version and no payload derives it from its own schema version.

_Corrected 2026-08-24 ([#126](https://github.com/eddiefiggie/srd-rules-engine/issues/126)). This section read **"None"** for every build between this record landing and that date, while the work it specifies had shipped — a dated claim that could not notice its own staleness._
