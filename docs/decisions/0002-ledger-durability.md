# 0002 — Nothing escapes the engine before its record is durable

- **Status:** Accepted, 2026-08-21
- **Settles:** [#5](https://github.com/eddiefiggie/srd-rules-engine/issues/5)
- **Requirements:** R26, R28, R30 · touches R5, R22, R29
- **Related:** [0001 — the agent seam](0001-agent-seam.md); the storage *format* is [#10](https://github.com/eddiefiggie/srd-rules-engine/issues/10)

## Context

R26 says every declaration, challenge, rejection, ruling, and fact write appends to an
append-only ledger. It did not say whether the append must *succeed* before the Ruling is
returned.

The issue framed this as append-before versus append-after, with a durability cost on one side
and a correctness risk on the other. Modelling it showed the framing was slightly off in two
ways, and both mattered.

### An outcome that never left the engine is not lost

A crash after the dice are rolled but before the Ruling is returned looks alarming and isn't.
Nobody saw the outcome, nothing was narrated, and on restart the agent simply re-declares. The
only genuinely bad state is an outcome that **escaped** — was returned to the caller, possibly
already narrated — with nothing durable to reconstruct it from. That is the original defect
arriving through the back door: an unrecorded ruling is indistinguishable from a silent skip
when the session-review report is read later.

So the boundary that matters is not the roll. It is the **escape point**, and the question is
only ever: can an outcome cross it before its record is durable?

### R5 already collapses the interesting choice

A first pass considered writing the *determinants* (seed, resolved facts, target derivation)
before rolling, so that a lost outcome could be rebuilt by replay under R28 rather than lost.
That turned out not to be a separate option at all.

R5 requires the Ruling to carry "raw dice and seed, the target number and its derivation... the
resolved value and provenance of every memory-port fact the ruling consumed." R28 requires replay
from "its recorded seed, inputs, and resolved fact values."

**Those are the same set.** The Ruling record *is* the determinants record. Writing it before the
Ruling escapes gets the recorded outcome and the ability to verify it by replay, in one record,
for one write.

## Decision

**A Ruling, a challenge, or a rejection may not be returned until its ledger entry is durable.**

- **One `fsync` per adjudication**, at the escape boundary. Not per entry and not per turn.
  Declarations, resolved facts, and challenges all precede the escape, so they ride along in the
  same buffered write and are covered by the same sync.
- **Narration appends are not on the critical path.** R29 already provides for a narration that
  never arrives — the turn carries an explicit missing-narration marker — so a lost narration is
  a detectable, named state rather than a silent hole. It does not need its own sync.
- **Replay is a verification mechanism, not a recovery one.** Because the outcome is always
  recorded, replay exists to confirm the record is self-consistent, not to reconstruct something
  missing.
- **Entries are hash-chained.** Each carries a monotonic sequence number, a checksum of its own
  body, and the digest of the previous entry.
- **A failed append raises, it does not return a status.** The core raises `LedgerUnavailable`;
  the turn loop catches it and ends the turn with a terminal outcome the adapters surface.

## Why

### The safe options cost the same, so pick the one that reads simplest

Modelling seven crash points across three policies:

| Crash point | append-after | append-first |
|---|---|---|
| Declaration appended | safe — retry | safe — retry |
| Facts resolved | safe — retry | safe — retry |
| Durable write in progress | safe — retry | safe — retry |
| Dice rolled, outcome in memory | safe — retry | safe — retry |
| **Ruling returned to caller** | **UNRECORDED OUTCOME** | safe — R29 marker |
| Agent narrated it | safe — R29 marker | safe — R29 marker |
| Narration appended | clean | clean |

Append-after has exactly one bad window, and it is the window that matters. Append-first has
none, for **one** critical-path `fsync` — the same count the alternatives need. A durability cost
that buys the elimination of the project's defining failure mode, at no premium over the unsafe
option, is not a trade-off worth agonising over.

### The hash chain is nearly free and covers a case checksums cannot

Testing four corruptions against two schemes:

| Corruption | checksum + sequence | + hash chain |
|---|---|---|
| Torn tail (crash mid-write) | rejected | rejected |
| Deleted middle entry | sequence gap | gap + chain broken |
| Edited roll, stale checksum | checksum mismatch | mismatch + chain broken |
| **Edited roll, checksum recomputed** | **not detected** | **chain broken** |

The torn tail is the one the crash model showed is genuinely reachable, and a checksum handles
it — a truncated ruling that still parses as valid JSON is worse than a missing one, because it
reads as a real entry.

The recomputed-checksum edit is a different matter. **This project is not defending a ledger
against its own owner** — it is solo play, one human, their own campaign, and someone determined
to change a roll can change a roll. The chain earns its place for two other reasons: it costs one
field and one comparison, and #10 is still deciding whether the ledger doubles as the interchange
format for sharing sessions. A shared session is the case where tamper-evidence stops being
theatre, and retrofitting a chain across a format that consumers already parse is far more
expensive than carrying one from the start.

### Infrastructure failure is not a rules outcome

R22 established a `blocked` status for a missing fact with no default. Reusing it for a failed
append would be a uniform surface over two unlike things: `blocked` names something the caller
can *fix* by supplying the fact, whereas a full disk cannot be fixed by re-declaring — and an
agent handed a status will reasonably try. Rules statuses describe rules. An exception crossing
the core boundary, translated by the turn loop into a terminal turn outcome, keeps the rules
vocabulary about rules.

## Consequences

**Accepted costs.**

- An `fsync` per adjudication is real latency, and on a degraded filesystem the session stops
  rather than degrading. That is intended: continuing without a ledger produces exactly the
  unrecorded outcomes the project exists to prevent.
- The chain constrains the ledger to a single ordered log, which makes later compaction,
  truncation, or splitting across files more awkward. Acceptable for a solo append-only log, and
  named here so #10 does not rediscover it.
- Recovery is not resumption. A crashed session restarts from a durable ledger, but the turn loop
  holds session state on its own stack ([0001](0001-agent-seam.md)), so resuming mid-turn means
  replaying the transcript.

**Follow-on effects.**

- **#10 (ledger format) inherits three constraints:** entries carry `seq`, `sum`, and `prev`;
  the format must support a single buffered write covering several entries; and a torn tail
  record must be rejectable on read rather than parsed.
- **R26 is amended** to state the escape-boundary rule, and **R30's report gains a verification
  pass** — chain and sequence integrity are checked when the report is generated, so a corrupted
  ledger is reported as corrupted rather than silently summarised.

## Evidence

Two spikes, neither committed. The first modelled seven crash points across three append
policies, distinguishing an outcome that merely existed in memory from one that escaped to the
caller. The second built ledgers under both integrity schemes and corrupted them four ways.
Reproduce by simulating the crash points as early returns from a turn function and asserting on
what reached durable storage.

A note on method: the first version of the crash model was **wrong in a way that flattered the
answer it was testing** — it omitted the ruling append from the determinants-first policy
entirely, and counted an unobserved in-memory outcome as "lost". Corrected, it showed the two
safe policies are equivalent, which is what led to noticing that R5 had already collapsed the
choice.

## Status of implementation

**Implemented.** `core/ledger.py`: `Ledger.escape_boundary` is the synchronising write, so no
Ruling, challenge or rejection returns before its entry is durable. A failed append raises rather
than returning a status, because infrastructure failure is not a rules outcome.
`tests/test_ledger_writer.py` carries the guards.

_Corrected 2026-08-24 ([#126](https://github.com/eddiefiggie/srd-rules-engine/issues/126)). This section read **"None"** for every build between this record landing and that date, while the work it specifies had shipped — a dated claim that could not notice its own staleness._
