# Concepts

Shared vocabulary for this project. Use these names for these things rather than inventing
synonyms — a rules engine acquires near-synonyms fast ("check", "test", "roll", "resolution"),
and once two names exist for one concept, code and prose start disagreeing about which is which.

Each entry names the requirement it comes from, so the contract stays the authority.

---

**Declaration** (R2) — what the agent submits: the actor, the intent, and either the test it
believes applies or an explicit *no-test claim with a stated reason*. Intent is either a
structured value drawn from the read surface's enumerated legal actions, or an intent marked
*improvised* carried alongside an optional free-text label. Improvised intents are validated,
trigger-checked, and adjudicated exactly like enumerated ones.

**No-test claim** (R2, R6) — the branch of a Declaration asserting that no mechanic applies.
The observed defect in agent-run play is that this happens *silently*; making it an explicit,
recorded, challengeable object is the point of the whole design.

**Challenge** (R6) — the engine's rejection of a no-test claim that collides with a trigger.
Returns the trigger and its citation, produces no outcome, and requires resubmission. Collision
is evaluated against the declaration's *structured* intent and engine-held situational state —
never against its free-text label.

**Rejection** (R3) — the engine's refusal of a declaration naming a test the character or
situation cannot support. Distinct from a Challenge: a rejection says *not that test*, a
challenge says *some test*.

**Declaration slot** (R8) — one actor's attempt to produce one adjudicated action within a turn.
A slot may absorb several refused declarations before a Ruling ends it. The retry budget is
counted per slot, and resets when a Ruling is produced or the turn ends.

**Retry exhaustion** (R8, R30) — the turn loop ending a declaration slot because its budget ran
out or a refusal repeated. **Not a rules status** — it sits beside a failed ledger append, not
beside `challenged` and `rejected`, because no rule says a badly-declared action has a result.
Carries a reason (`no-progress`, `challenge-churn`, `rejection-churn`, `mixed-churn`), the
refusal history, and the alternatives the read surface had offered. The engine never breaks the
loop by selecting a test: that would let an agent reach an outcome by failing. Specified in
`docs/decisions/0005-retry-bounds.md`.

**Read token** (R10, R18, R19) — the opaque value a read-surface call returns alongside the legal
set, encoding the state generation the set was derived from and a digest of the set. The
declaration echoes it, which makes the agent's claim about what it was offered checkable *without*
the read surface recording anything — so R19 stands. Derived and returned, never stored.

**Alternatives verdict** (R10) — what the engine reports about that claim: `verified-fresh`
(genuine and current), `verified-stale` (genuine, but the agent decided from state that has since
changed), `unverified` (not what was offered), or `unread` (no token — the expected verdict for a
caller outside the turn loop). A failed verification is recorded and flagged in the report, never
a refusal to adjudicate: the alternatives are metadata about a decision, not the decision.
Specified in `docs/decisions/0007-alternatives-verification.md`.

**Block** (R22) — the engine declining to adjudicate because a rule consumes a fact the port does
not hold and no default of any kind would be honest. **A suspension, not a refusal**: the
declaration was accepted, so supplying the facts resumes *that* declaration rather than requiring
a new one, and the agent's retry budget is not charged. Names every unresolved fact at once. The
loop is self-terminating because R21 makes fact dependencies static, so the unresolved set can
only shrink; a round that fails to shrink it ends the turn as `fact-unavailable`. Blocking is
usually correct behaviour — what is defective is a fact type that blocks session after session,
which means its `absent` classification is failing. Specified in
`docs/decisions/0010-blocked-loop.md`.

**Ruling** (R5) — the only object that constitutes an outcome. Carries status, the test
performed, raw dice and seed, the target number *and its derivation*, the outcome, applied
effects, the resolved value and provenance of every memory-port fact consumed, SRD citations,
and narration bounds.

**Narration bounds** (R7) — the part of a Ruling stating what the caller may and may not assert
as having happened, so consequences the ruling did not resolve must be declared separately.
**Advisory to the caller; not enforced by the engine.**

**Read surface** (R18, R19) — the query API answering what is legal for a character at the
current moment: available actions, movement remaining, castable spells given slots, active
conditions and their mechanical effects. Idempotent, non-mutating, never appends to the ledger.

**Turn loop** (R8) — the engine-driven loop that owns the turn and invokes the agent only at
defined points. Ships as a v1 deliverable *outside* the LLM-free core, and is what the adapters
expose. The skip guarantee holds for callers it drives, and not for callers that bypass it.

**Memory port** (R20–R25) — the typed interface through which narrative facts that carry
mechanical weight (attitude, knowledge, inspiration) reach the rules. Returns typed values only,
never prose. The engine owns the interface and does not implement it.

**Fact type** (R21, R22, R24) — one narrative value a rule declares a dependency on. Carries
whether its absent-value default is *SRD-prescribed*, *engine-chosen*, or *absent entirely*;
when no default of any kind exists, the engine returns **blocked** rather than adjudicating.
Core fact types are SRD-derived; consumers add their own through the namespaced extension
channel without a schema break.

**Provenance** (R25, R27) — where a fact came from: the ruling that produced it, or an explicit
out-of-band entry. A ruling influenced by a memory-supplied fact cites both the governing SRD
rule and the fact with its provenance, which is what makes a target number explainable after
the fact.

**Ledger** (R26, R28) — the append-only record of every declaration, challenge, rejection,
ruling, fact write, and narration. Any ruling entry replays to an identical outcome from its
recorded seed, inputs, and resolved fact values, *without re-querying the memory port* — within a
matching engine version.

JSONL, one entry per line. Every entry carries a **fixed envelope** — `seq`, `type`, `v`, `prev`,
`sum`, `payload` — committed for the life of the project, with `v` versioning the payload alone.
Integrity checking and listing therefore work across every version ever written; only payload
interpretation needs a version the reader knows. Digests are taken over canonical JSON with
**floating-point numbers excluded entirely**: the domain needs none, and a record meant to be
authoritative should not hold values that are approximately what they say. Specified in
`docs/decisions/0006-ledger-format.md`.

**Ledger reader** (R35) — the shipped API that opens, verifies, iterates, replays, reports,
audits, and exports a ledger. **It is the supported interface; the on-disk format is not.** A
consumer that parses the file makes the file an interface whether or not that was intended, so
the reader exists to give them something stable to depend on instead.

**Session-review report** (R30) — the report generated from the ledger listing, per turn, the
declaration, the alternatives offered, the Ruling, and the submitted narration — flagging turns
carrying a narration with no Ruling, a Ruling with no narration, or a challenge never
re-adjudicated. This is the instrument the primary success criterion is measured with.

**Trigger catalogue** (R6) — the set of conditions that cause a no-test claim to be challenged.
The SRD supplies explicit triggers only for forced saves, attacks, and stated hazards; the rest
is project-authored and grounded in rather than cited from the SRD. **Known-incomplete by
construction**, and disclosed as such.

It is **data, not code**: a trigger is a declarative row over a closed operator set, and the
matcher that interprets it is handed a projection of the declaration *excluding* the free-text
label — so R6's prohibition holds by construction. A row is a conjunction; a disjunction is
separate rows, so each alternative stays separately citable and separately narrowable. Grounding
is two-valued, `cited` or `authored`. The catalogue is versioned, the version is recorded on the
declaration, and replay uses the recorded one. Specified in
`docs/decisions/0004-trigger-catalogue.md`.

**Retrospective audit** (R6) — re-running closed ledgers against the *current* trigger catalogue
to find declarations that today's rules would have challenged. Distinct from replay, and the
distinction matters: replay asks whether a record is self-consistent and uses the catalogue
version the session ran under; the audit asks what was missed and deliberately uses a newer one.
Because a missed skip leaves no trace at the time, this is the only mechanism that measures
catalogue recall at all.

**Over-fire** (R6) — a challenge that fires where no test was warranted. Not a lesser failure than
a missed skip but the same one inverted: the agent must resubmit naming a test, so the engine
rolls for something the SRD never called for, and the resulting Ruling is well-formed and
unearned. Carries `srd-fidelity`.

**Extension fact type** (R24) — a consumer-defined fact type in a reverse-DNS namespace
(`com.example.tool.mood`). The core set is *unnamespaced*, so carrying a namespace is what makes a
type an extension — no lookup, no list to maintain. **No engine rule may consume one**: extensions
get typing, provenance, and ledger integration, but no resolver, so they cannot move an outcome
and R31 stays intact. Each namespace versions independently and the engine interprets none of
them. Specified in `docs/decisions/0008-extension-channel.md`.

**Memory store projection** (R23, R25) — the reference memory implementation holds *current values
only*. Because every fact write appends to the ledger with provenance, the **ledger is the system
of record** and the store rebuilds from it. That is why it is flat JSON rather than a database:
durability and indexing are advantages a rebuildable projection at solo-campaign scale does not
need, and a person can read their own campaign state. Specified in
`docs/decisions/0009-reference-memory-store.md`.

**Effect-shape inventory** (R17) — the published inventory of distinct SRD 5.2 effect shapes
against which coverage is checked. Mechanical coverage is complete when every shape resolves;
entries not yet implemented are disclosed rather than omitted silently.

**Content population** — per-entry data (the bestiary, the spell list) written entirely in the
effect vocabulary. A parallel data track, deliberately *not* a blocker on the mechanics code.
The line between it and mechanical coverage is the effect vocabulary itself.

**Verification state** (R31, R32) — per-entry record of whether a seeded mechanic has been
checked against the official SRD 5.2 document. Unverified entries are excluded from the engine
and the exclusion disclosed.

**Adapter** (R34) — MCP, HTTP, or CLI access built over the same contract, outside the core,
exposing the turn loop as the only outcome-producing path.
