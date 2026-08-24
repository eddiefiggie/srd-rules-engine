# 0009 — The reference memory store is flat JSON, because it is a projection of the ledger

- **Status:** Accepted, 2026-08-22
- **Settles:** [#12](https://github.com/eddiefiggie/srd-rules-engine/issues/12)
- **Requirements:** R23, R33 · touches R21, R25, R26, R28
- **Related:** [0008 — the extension channel](0008-extension-channel.md) is its sibling gate;
  [0006 — ledger format](0006-ledger-format.md) decided the analogous question for the ledger and
  reaches a different conclusion here for a different reason

## Context

R23 requires a file-backed reference implementation of the memory port, sufficient to run a solo
campaign with continuity across sessions. "File-backed" was settled; the shape inside it was not.

The issue frames this as a real choice rather than a foregone one, and it is right to: `sqlite3` is
in the standard library, so R33's no-runtime-dependencies promise does not decide it. SQLite offers
transactional writes and indexed reads; flat files offer inspectability and diffability.

### The store is not the system of record

R25 already requires that **every fact write appends to the ledger with provenance**, and that a
fact consumed by a rule is traceable to the ruling that produced it or to an explicit out-of-band
entry.

So the write history, with provenance, is in the ledger. The memory store holds only *current
values* — it is a materialised view, and a lost or corrupted store can be **rebuilt by replaying
the ledger's fact writes**.

That reframing decides the gate, because it removes both of SQLite's advantages at once rather
than weighing them:

- **Transactional durability** protects a system of record. [0002](0002-ledger-durability.md)
  already places the durability boundary on the ledger append, before a Ruling escapes. A torn
  write to a rebuildable projection costs a rebuild, not data.
- **Indexed reads** matter at a scale this does not reach. Solo play, one character: the facts a
  campaign accumulates are attitudes of NPCs met, knowledge flags, and inspiration — hundreds over
  a long campaign, not thousands, and all of it fits in memory.

It also supplies the concrete acceptance criterion the issue asks for.

## Options considered

- **SQLite.** Rejected. In the standard library, so R33 holds, and its advantages are real in
  general — but both are advantages a rebuildable projection at this scale does not need. Against
  it: campaign state becomes opaque to the person whose campaign it is, and a corrupted database
  is harder to salvage than a JSON file, which matters more when the thing is meant to be readable
  than when it is meant to be fast.
- **Flat JSON sharing the ledger's substrate.** Rejected. One storage mechanism and one set of
  file-handling routines is genuinely attractive, and [0006](0006-ledger-format.md)'s canonical
  form would apply uniformly. It loses the port's swappability: a consumer replacing the memory
  implementation — which is the entire reason it is a port — would inherit ledger machinery it has
  no use for.
- **Flat JSON on its own substrate.** Adopted.

Note that this reaches the opposite conclusion to [0006](0006-ledger-format.md) on a
superficially similar question, and for a reason that does not transfer. 0006 rejected SQLite
partly because append-only would become discipline over a mutable B-tree. **The memory store is
mutable by nature** — updating a fact is the operation — so that objection does not apply here.
It is rejected on scale and inspectability instead.

## Decision

**1. Flat JSON, one file per campaign, on a substrate separate from the ledger.**

**2. The ledger is the system of record; the store is a projection.** The store may be rebuilt from
the ledger's fact writes at any time, and rebuilding is a supported operation rather than a
recovery hack.

**3. Fact values must be ledger-representable.** Because a write appends to the ledger,
[0006](0006-ledger-format.md)'s constraints reach through the port: **no binary floating-point
value may be a fact value.** A fact that is genuinely fractional carries an exact string or an
integer subunit, exactly as ledger payloads do.

**4. Extension facts round-trip opaquely**, including namespaces the implementation has never seen,
per [0008](0008-extension-channel.md).

**5. "Sufficient to run a solo campaign" means these five properties**, which are testable:

| # | Property |
|---|---|
| 1 | Every core fact type can be written and read back with its declared type |
| 2 | Values survive a process restart, unchanged |
| 3 | The store rebuilds from the ledger's fact writes to a state identical to the live one |
| 4 | Extension facts round-trip opaquely, including unknown namespaces and versions |
| 5 | A read returns provenance sufficient for R27's citation |

Property 3 is the load-bearing one: it is the executable form of decision 2, and a store that
cannot be rebuilt is not a projection however it is described.

## Why

### Deciding what the thing *is* settled what it should be made of

The gate reads as a storage-technology comparison, and technology comparisons at this scale rarely
resolve cleanly — both options work, and the argument becomes preference. Establishing that the
store is a projection rather than a system of record converted it into a question with an answer,
because it disqualified the two properties that would otherwise have carried SQLite.

That is worth noticing beyond this gate. R25 had already made the ledger authoritative over fact
history; nothing in #12 said so, and reading the store as a database in its own right would have
produced a defensible decision for the wrong reasons.

### Inspectability is the product working at the last level

This engine exists so that outcomes are explainable after the fact. The ledger is where that is
usually cashed out — but a campaign's *current* narrative state is the other half of the picture,
and a person being able to open the file and read who trusts them and what they know is the same
value delivered at the smallest scale.

An embedded database would make that state opaque to its owner in exchange for performance the
workload does not need.

### Separate substrate, because the port's purpose is substitution

The memory port exists so the engine can be given narrative facts by something it does not
implement — R20 defines it, and R23 ships a reference implementation precisely so that a campaign
runs standalone *without* that being the only option.

Coupling the reference implementation to the ledger's storage would be a small convenience now and
a structural obstacle later: a consumer swapping in their own store would find the reference
implementation was never a self-contained example of how to do it.

## Consequences

**Accepted costs.**

- **A whole-file write per fact update.** Fine at hundreds of facts, and it would not be at
  100,000. The scale assumption is explicit here so that a future consumer with a different one
  knows to substitute the port rather than assume it will hold.
- **No concurrent access.** Two processes writing one campaign file will corrupt it. Acceptable
  because multiplayer and shared sessions are declared non-goals — but it is a property of the
  reference implementation, not of the port, and a consumer needing otherwise substitutes.
- **Rebuild is a real code path**, and one that is exercised rarely in normal operation. It needs
  its own tests, because the failure mode is discovering it does not work at the moment it is
  needed.
- **The no-float rule now reaches into fact types**, constraining a schema whose author may not
  have read [0006](0006-ledger-format.md). It belongs in the port's documentation, not only in the
  ledger's.

**Follow-on effects.**

- **Store corruption is recoverable**, which is a property worth advertising rather than merely
  possessing. It should be stated in the port's documentation, since a user who loses a file will
  otherwise assume the campaign's continuity is gone.
- **R23 is amended** with the format, the projection relationship, and the five properties.
  **R25** gains a note that ledger authority over fact history is what makes the store rebuildable.
- **[#33](https://github.com/eddiefiggie/srd-rules-engine/issues/33) touches this.** A driver
  looping on `blocked` is failing to supply a fact through this port, and the reference
  implementation is what most drivers will be looping against.

## Evidence

No spike. The scale claim is checkable by enumerating what a solo campaign accumulates in the core
fact set — attitudes of NPCs encountered, knowledge flags, inspiration — against the fact types the
SRD's judgment-dependent rules actually contemplate. The count is in the hundreds over a long
campaign, which is three orders of magnitude below where indexed reads begin to matter.

The projection claim is checkable against R25 directly: if every fact write appends to the ledger
with provenance, then the ledger contains the information required to reconstruct any current
value, and property 3 above is the executable statement of that.

## Status of implementation

**Implemented.** `memory/store.py`: `JsonMemoryStore` is the flat-JSON store and
`rebuild_from_ledger` is the projection this record's argument turns on — the ledger is the system
of record for fact history, and the store rebuilds from it. All five properties this record calls
"sufficient" are asserted in `tests/test_reference_store.py`.

_Corrected 2026-08-24 ([#126](https://github.com/eddiefiggie/srd-rules-engine/issues/126)). This section read **"None"** for every build between this record landing and that date, while the work it specifies had shipped — a dated claim that could not notice its own staleness._
