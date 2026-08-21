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
recorded seed, inputs, and resolved fact values, *without re-querying the memory port*.

**Session-review report** (R30) — the report generated from the ledger listing, per turn, the
declaration, the alternatives offered, the Ruling, and the submitted narration — flagging turns
carrying a narration with no Ruling, a Ruling with no narration, or a challenge never
re-adjudicated. This is the instrument the primary success criterion is measured with.

**Trigger catalogue** — the set of conditions that cause a no-test claim to be challenged. The
SRD supplies explicit triggers only for forced saves, attacks, and stated hazards; the rest is
project-authored and grounded in rather than cited from the SRD. **Known-incomplete by
construction**, and disclosed as such.

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
