# 0008 — Reverse-DNS extension namespaces that no engine rule may consume

- **Status:** Accepted, 2026-08-22
- **Settles:** [#9](https://github.com/eddiefiggie/srd-rules-engine/issues/9)
- **Requirements:** R24, R21, R22, R35 · touches R25, R31
- **Related:** [0009 — the reference memory store](0009-reference-memory-store.md) is its sibling
  gate; [0006 — ledger format](0006-ledger-format.md) supplies the versioning precedent.
  Versioning *mechanics* remain [#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13)

## Context

R24 says the port supports namespaced extension fact types that consumers add without a schema
break, distinct from the SRD-derived core set. The mechanism was unspecified, and the plan
deliberately declined to defer it past release: a closed set forces forks, a minimal set is
certain to need breaking additions, and leaving it open strands consumers who could already be
building.

Four questions were open — namespace form, how core and extension are told apart, how R22's
default classification applies, and how versioning works. **Three of them turned out to be
downstream of the fourth**, which the issue lists without flagging as decisive: can an engine rule
consume an extension fact?

R31 is what puts pressure on that. Every mechanic traces to the SRD 5.2.1, and a rule whose
outcome moves on a fact the SRD never contemplated no longer traces to anything. The honest
counter-argument is that the SRD delegates some determinations to the DM, and that delegated slot
is exactly what core facts like attitude already fill — so the boundary is not self-evident.

## Options considered

### Namespace form

- **A registered short prefix.** Disqualified by the requirement that states the problem. "Collision
  between two independent consumers must be impossible without coordination" — and a registry *is*
  coordination, whether it lives in a repository file or a service.
- **URI-based namespaces.** Rejected. Equally collision-free and unambiguously owned, but heavier
  in every record that carries one, and a URI invites the assumption that it dereferences to a
  schema. It never will, which makes it a promise the format does not keep.
- **Reverse-DNS.** Adopted.

### Whether a rule may consume an extension fact

- **On the same footing as core facts.** Rejected. It means a consumer can change what rulings
  produce, which is the boundary the whole project exists to hold, and R31 stops meaning what it
  says.
- **Only where the SRD delegates to DM judgment.** Rejected for v1, and it is the option worth
  revisiting. It is genuinely more useful, and structurally identical to what attitude already
  does. It was set aside because "where the SRD delegates" is a judgment made per rule by whoever
  wants the extension, so R31's traceability would become an argument rather than a property —
  and because this direction can be opened later without a break, while the reverse is not true.
- **Never.** Adopted.

## Decision

**1. Extension namespaces are reverse-DNS.** `com.example.tool.mood`. A consumer without a domain
uses `io.github.<user>.<tool>`, which is unique for the same reason.

Nothing verifies that a claimant controls the domain, and nothing needs to. The hazard being
prevented is two independent consumers **accidentally** choosing the same name, not one of them
squatting another's. Squatting has no payoff here — a namespace collision hurts only the consumers
involved, and the engine never resolves either.

**2. The core set is unnamespaced. Carrying a namespace is what makes a fact type an extension.**
`attitude` is core; `com.example.tool.mood` is not. The distinction costs no lookup and cannot
drift out of step with a list that someone has to maintain. A future core addition can never
shadow an existing extension, because core names carry no namespace at all.

**3. No engine rule may consume an extension fact.** A rule declaring one is a **load-time error**,
not a runtime failure — it is a defect in the rule definition and should be impossible to ship,
not merely impossible to hit.

**4. Extensions keep everything else the port provides.** They are declared, written, and read
through the same port; R25's provenance and ledger obligations apply unchanged; a write appends to
the ledger like any other. What they do not get is a resolver.

**5. R22's default classification does not apply to extension types.** R22 governs what happens
when a rule consumes a fact the port does not hold. No rule consumes an extension, so the
situation never arises. If decision 3 is ever widened, the classification to add is
**`consumer-declared`** — distinct from `engine-chosen`, because the engine did not choose it and
should not appear to vouch for it. Recorded here so the future does not have to rediscover it.

**6. Each namespace versions independently of the core schema, and the engine never interprets
either.** It records the namespace and its declared version, stores the value, and returns it
unchanged. There is no such thing as a namespace version the engine does not know, because it
knows none of them. The consumer owning a namespace is the only party that interprets it.

## Why

### One answer made three questions disappear

The issue poses four open questions. Deciding that no rule may consume an extension fact does not
merely answer one of them — it dissolves two others and simplifies the third:

| Question | Under "never" |
|---|---|
| Can a rule declare an extension fact? | No, by construction |
| How does R22's classification apply? | It does not apply — R22 only fires for facts rules consume |
| What if the engine meets an unknown namespace version? | It cannot: it interprets no namespace |
| Namespace form | Still a real choice, decided on the collision constraint |

That is a signal worth naming rather than a coincidence. A question set that collapses under one
answer usually means the answer is at the right altitude, and the remaining question is the one
that was genuinely independent.

### The channel earns its place even though the engine ignores it

An extension channel nothing consumes looks inert, and the obvious objection is that R24 is
therefore ceremony. It is not, for two reasons the plan already gave.

**A closed set forces forks.** A consumer needing to attach narrative state to a campaign, with
provenance and a ledger record, either has a supported way to do it or edits the engine. The
second produces a fork that diverges on the schema, which is the outcome R24 exists to prevent.

**The stable part stays stable.** Committing only to what the SRD demands, and letting growth
happen additively in namespaces nobody has to coordinate, is what lets the core schema be public
API from day one — which R35 requires and the plan explicitly refused to defer.

What consumers get is real: typed storage with provenance, ledger integration, and continuity
across sessions, for state the engine has no opinion about.

### Widening is additive, narrowing is a break

The rejected middle option — extensions permitted where the SRD delegates to judgment — remains
reachable. Adding it later means some rules gain a capability; no existing consumer breaks, no
schema changes, no recorded ledger entry becomes invalid.

Shipping it now and retracting it later would break every consumer that used it, and would do so
after real campaigns had rulings that depended on it. The same asymmetry decided
[0006](0006-ledger-format.md)'s treatment of the ledger file, and it points the same way here.

## Consequences

**Accepted costs.**

- **Extensions are inert to the engine, and someone will expect otherwise.** "Namespaced extension
  fact types" reads like extensibility of behaviour, and it is extensibility of *storage*. This has
  to be stated plainly in the port's documentation, not left for a consumer to discover by writing
  a rule that will not load.
- **Reverse-DNS is verbose**, in the port, in the ledger, and in every Ruling that cites a fact.
- **Load-time validation is new machinery.** Rule definitions must be checked against the namespace
  rule when they are registered, and that check needs a guard test proven red.
- **Namespace ownership is unenforced.** Two consumers who both pick `com.example.tool` collide,
  and the engine will not notice. Accepted, because the failure is local to them.

**Follow-on effects.**

- **[#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13) inherits a fifth versioned
  thing**, and an unusual one: extension namespace versions are declared by consumers and never
  interpreted by the engine, so whatever mechanism that gate settles must accommodate a version
  the engine only records.
- **R24 is amended** with the namespace form, the unnamespaced-core rule, and the
  no-rule-may-consume rule. **R21 is amended** to say a rule may declare only core fact types.
  **R22** gains a note that its classification covers core types only.
- **[0009](0009-reference-memory-store.md) inherits a requirement**: the reference implementation
  must round-trip extension facts opaquely, including namespaces it has never seen.

## Evidence

No spike. The argument is from the requirements, and the collapse described above is reproducible
by taking each of the issue's four open questions in turn under each of the three answers to the
rule-access question — two of the four have no content under "never" and become live, contested
design work under either alternative.

A note on method: the issue lists rule access third of four, phrased as a clarification ("can a
rule ever declare an *extension* fact, or are extensions readable only by consumer-side code?").
It reads like a detail and is the hinge. Working the questions in the order given would have meant
designing a default classification and a version-negotiation scheme for extensions before
discovering that neither is needed.

## Status of implementation

**None.** M0 holds that nothing is built until the gates close. This record specifies the namespace
form, the core/extension boundary, and what the engine will and will not do with an extension; it
lands with the memory port when M1 opens.
