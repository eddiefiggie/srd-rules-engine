# 0004 — The trigger catalogue is data, and over-firing is a fidelity defect

- **Status:** Accepted, 2026-08-22
- **Settles:** [#7](https://github.com/eddiefiggie/srd-rules-engine/issues/7)
- **Requirements:** R6 · touches R2, R26, R28, R30, R31
- **Related:** [0001 — the agent seam](0001-agent-seam.md) bounds who the guarantee covers;
  [0002 — ledger durability](0002-ledger-durability.md) makes replay a verification mechanism;
  [0003 — seed and verification](0003-seed-and-verification.md) supplies the provenance vocabulary.
  Retry bounds are [#11](https://github.com/eddiefiggie/srd-rules-engine/issues/11)

## Context

R6 is the direct answer to the defect this project exists to fix: a no-test claim that collides
with a trigger comes back `challenged`, and the silent skip becomes a recorded exchange. The
catalogue behind it was undesigned.

Three constraints bound the design before any preference enters.

**R6 forbids matching on the declaration's free-text label.** The moment the guard reads prose it
is interpreting narrative again, which is the capability being removed.

**The catalogue is known-incomplete by construction.** The SRD supplies explicit triggers only
for forced saves, attacks, and stated hazards; it deliberately leaves most of "does this need a
check" to judgment. That is a disclosed property, not a bug awaiting a fix.

**Recall is unmeasurable from play.** A missed skip leaves no trace. The ledger records the
challenges that fired, never the ones that should have.

Two further constraints turned up in modelling, and neither was in the issue.

### A growing catalogue silently invalidates every past session

R28 requires any ruling entry to replay to an identical outcome, and
[0002](0002-ledger-durability.md) made replay a *verification* mechanism rather than a recovery
one — its job is to confirm a record is self-consistent. But a catalogue that grows is a catalogue
that answers differently over time. Re-run a year-old declaration against today's catalogue and it
may be challenged where the original was adjudicated, and the ledger reads as corrupt when
nothing is wrong with it.

The catalogue is therefore an **input to adjudication**, in exactly the sense R28 means by
"recorded inputs", and it has to be pinned like one.

### Over-firing is not the mild failure

The issue asks whether false positives should be tracked as seriously as misses, on the grounds
that an over-firing catalogue trains an agent to treat challenges as noise. That undersells it.

When a trigger fires wrongly, the agent must resubmit naming a test, and the engine then **rolls
dice for something the SRD never called for**. The result is a mechanical event that no rule
produced, carrying a seed, a target derivation, and citations — indistinguishable in the ledger
from an outcome the rules demanded.

That is the project's defining defect with the sign flipped. The silent skip is an outcome with
no ruling behind it; an over-fire is a ruling with no rule behind it. Both are unearned
mechanical facts entering the campaign as established ones. They deserve the same severity, and
under this repository's existing label meanings that severity has a name: `srd-fidelity`, which
"means a rule may be modelled wrongly, which outranks everything except a crash."

## Options considered

### How a trigger is expressed

- **Registered Python predicates.** Rejected. A callable has every expressive advantage and one
  disqualifying property: it is handed the declaration, so nothing but review stops it reading
  the free-text label. R6 would become a promise maintained by vigilance. A predicate set also
  cannot be published as the disclosed catalogue, diffed when it grows, or replayed against a
  pinned version without pinning the source tree.
- **Declarative rows with a predicate escape hatch.** Rejected. The escape hatch is where every
  genuinely hard trigger ends up, so the structural guarantee would cover the easy half of the
  catalogue and the reviewed-by-hand half would be the half that matters.
- **Declarative rows over a closed operator set.** Adopted.

### How grounding is recorded

A three-tier split was considered — `cited` (the SRD states the trigger outright), `derived` (the
SRD states a mechanic that implies a check here and can be pointed at), and `authored` (project
judgment with nothing behind it) — on the argument that a derived trigger names something a
reader can check and an authored one does not.

**Rejected in favour of two tiers**, `cited` and `authored`. Two reasons decided it. The plan and
`CONCEPTS.md` already speak of triggers as *cited from* or *grounded in* the SRD, and a third
tier would mean rewording settled vocabulary to accommodate a distinction that had not yet earned
it. More importantly, the boundary between derived and authored is itself a judgment call made at
intake, on every report, by whoever files it — and a provenance scheme whose tiers are assigned by
judgment reports less than it appears to. Two tiers ask one unambiguous question: **does the SRD
say this, yes or no?**

### What admits a report to the catalogue

- **Maintainer review, tests following the change.** Rejected. "Obvious" is precisely how an
  over-firing catalogue accretes, and a trigger admitted on plausibility leaves no artifact
  showing it was ever needed.
- **Evidence for false positives only.** Rejected as an asymmetry that points the wrong way.
- **Evidence in both directions.** Adopted, extending a rule the repository already holds.

### What can trigger-check an improvised intent

- **Require structured attributes from a closed vocabulary.** Rejected. It would improve coverage
  materially, and it does so by asking the agent to classify its own action into rules-relevant
  categories — handing back the judgment the design exists to take away, at the exact moment the
  agent has already decided no rule applies.
- **Challenge by default whenever trigger-relevant state is active.** Rejected. It closes the hole
  by over-firing, which by the argument above is the same class of defect it is closing.
- **Situational state only, with the gap disclosed.** Adopted.

## Decision

**1. A trigger is a row, not a function.** The catalogue is data. A fixed matcher interprets it
over a closed operator set, and **the matcher is never handed the declaration's free-text label** —
it receives the structured intent and engine-held situational state and nothing else. R6 holds
because the label is not in scope, not because a reviewer checked. This is the same move as
[0002](0002-ledger-durability.md)'s empty `[project].dependencies`: the promise expressed in a
form that cannot quietly stop being true.

Each row carries:

| Field | Meaning |
|---|---|
| `id` | Stable identifier. Named in the challenge, recorded in the ledger, cited in reports |
| `grounding` | `cited` \| `authored` |
| `reference` | SRD 5.2.1 section. Required when `cited` |
| `rationale` | Why this warrants a check. Required when `authored` |
| `when` | Match conditions over the closed operator set |
| `message` | What the challenge tells the agent. Project-authored prose, never quoted SRD text |
| `added_in` | Catalogue version in which the row first appeared |

**2. No disjunction. A row is a conjunction, and an "or" is two rows.** Conditions test the
structured intent and named situational-state facts with `equals`, `in`, `present`, and `absent`,
combined only by AND. This is a deliberate restriction rather than a simplification: each
alternative becomes separately citable in a challenge, separately reportable, and separately
narrowable when it over-fires. A disjunctive row that fires wrongly on one of its branches cannot
be narrowed without weakening the other.

**3. Every matching row is reported, in `id` order.** A challenge names all rows that fired, not
the first. Deterministic ordering is required for replay; naming all of them is what makes a
false-positive report actionable, since the reporter can say which row was wrong.

**4. The catalogue is versioned, and the version is an adjudication input.** The declaration's
ledger entry records the catalogue version in force. **Replay under R28 uses the recorded
version**, so a session verifies against the catalogue it actually ran under, and growth never
retroactively corrupts a record.

**5. Catalogue growth is the recall instrument.** A separate **retrospective audit** re-runs
closed ledgers against the *current* catalogue and reports every declaration that today's rules
would have challenged. This is distinct from replay and must never be confused with it: replay
answers "is this record self-consistent", the audit answers "what did we miss".

It is also the only real answer to the unmeasurable-recall problem. A missed skip leaves no trace
*at the time* — but it leaves a declaration, and a trigger added later can be run against it. Every
new row makes the whole history newly measurable, and the audit's output is a list of sessions
where that skip went through.

**6. A report becomes an entry only after it has been proven red.**

- **A miss** is first expressed as a fixture — structured state plus the declaration — and the
  current catalogue is shown **not** to challenge it. Only then is the row written, and the
  fixture flips green.
- **A false positive** is first expressed as a fixture asserting that no challenge fires, which
  goes red against the current catalogue. The offending row is then **narrowed by adding a
  condition**, not deleted. Deletion is reserved for a row that should never have existed.

Both fixtures stay permanently. The catalogue's test corpus therefore accumulates into a record
of adjudicated situations, which is the closest thing available to a statement of what the
catalogue does and does not cover.

This extends two rules the repository already holds — "prove a guard fails before trusting it" and
"prove a new test fails against the pre-change tree" — to the one guard whose failures are
invisible.

**7. A false-positive report carries `srd-fidelity` alongside `trigger-catalogue`.** By the
argument above it is a rule modelled wrongly, and it takes that label's priority.

**8. Improvised intents match on situational state alone**, and the reduced coverage ships
disclosed alongside the catalogue's other known limits. The mitigation is decision 5: an
improvised miss surfaces retrospectively when the trigger that covers it is eventually added.

**9. `cited` and `authored` rows are gated differently, and R31 does not block the catalogue.**
A `cited` row's `reference` is verified against SRD v5.2.1 under [0003](0003-seed-and-verification.md)
and carries the same `state` / `reference` / `date` / `reason` block. An `authored` row **has
nothing to verify against**, and applying a verification gate to it would mean the catalogue could
never ship. Its `rationale` is reviewed, not verified, and it is disclosed as project judgment.

## Why

### The label has to be out of scope, not merely off-limits

R6's prohibition is the whole guard. If the matcher receives the declaration object, then reading
`declaration.label` is one attribute access away and every future contributor is one convenience
away from it — and the failure is silent, because a catalogue that reads prose behaves *better* on
the cases anyone would test. It fires more accurately, right up until it fires on the agent's
choice of words.

Handing the matcher a projection that does not contain the label removes the option. That is
worth more than the expressiveness a predicate would buy, because the expressiveness is
recoverable — the operator set can grow — and the guarantee is not.

### Two tiers because a judgment-assigned provenance tier reports its own uncertainty badly

The three-tier scheme is more informative when the tiers are assigned correctly, and the
correctness of the assignment is exactly what nobody can check. "Does this section *imply* a
check here?" is a judgment, made once, by the person most convinced the trigger is warranted.
Over a few hundred rows the `derived` tier would fill with entries whose grounding is real and
entries whose grounding is wishful, and the tier itself would stop carrying information.

`cited` versus `authored` asks whether the SRD says it. That has an answer, and a wrong answer is
findable by anyone holding the document.

### The asymmetry of evidence corrects an asymmetry of visibility

Misses are invisible and false positives are loud, so unaided attention flows to false positives
while the catalogue's real weakness is recall. But the *fix* for that is not to lower the bar for
admitting triggers — that trades an invisible failure for a visible one and calls it progress.

Evidence-first in both directions decouples the two. A miss still has to be demonstrated, so the
catalogue does not accrete on plausibility. And the audit of decision 5 supplies the recall signal
that attention alone cannot, without weakening admission.

### Narrowing rather than deleting keeps the reason alive

A row that over-fires is usually right about something. Deleting it discards the case it did
catch, which then has to be rediscovered as a miss. Adding a condition records what the boundary
turned out to be, and the row's history shows where the catalogue learned it.

## Consequences

**Accepted costs.**

- **The operator set will need extending**, and each extension is a change to the matcher rather
  than to data. That is the price of the structural R6 guarantee, and it is paid in a place where
  it is visible.
- **No disjunction means more rows.** A trigger with three alternative situations is three
  entries with three ids. The catalogue is longer and its ids are less tidy.
- **Every declaration ledger entry carries a catalogue version**, which is one more field on the
  hottest record in the system.
- **The retrospective audit is a second execution path over the ledger**, with its own
  correctness burden, and it will report findings against sessions long finished — which is
  useful and also a source of noise if it is run without a bounded window.
- **Improvised coverage is genuinely weaker**, and this decision does not fix it. It disclosed it
  and gave it a delayed detection path.

**Follow-on effects.**

- **[#11](https://github.com/eddiefiggie/srd-rules-engine/issues/11) (retry bounds) inherits a
  case.** An over-firing row can produce a challenge the agent cannot satisfy, so retry bounds are
  what stops a challenge loop. That gate should treat repeated identical challenges as a distinct
  terminal condition rather than a generic retry cap, and the ledger should make the loop
  visible.
- **[#10](https://github.com/eddiefiggie/srd-rules-engine/issues/10) (ledger format) gains a
  field:** the catalogue version on declaration entries.
- **[#14](https://github.com/eddiefiggie/srd-rules-engine/issues/14) supplies the denominator.**
  Coverage is disclosed as two separate numbers and never as one: `cited` rows against the
  enumerable count of the SRD's explicit trigger sites, and `authored` rows as **a count with no
  denominator, stated as having none**. A single blended "recall" figure would be invented.
- **R6 is amended** to state that the matcher receives a projection excluding the free-text label,
  that all matching rows are reported, and that the catalogue version is recorded and used on
  replay. **R30's report gains** the catalogue version the session ran under.
- **The catalogue is not gated by [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3).**
  A section reference is a pointer, not SRD content, and challenge messages are project-authored
  prose. So the catalogue can be built while attribution is still open. This holds only as long
  as no `message` quotes SRD text — the moment one does, it is SRD-derived content and #3 applies.
- **`.github/ISSUE_TEMPLATE/trigger-miss.yml` needs two changes**: false-positive reports should
  carry `srd-fidelity`, and both directions should ask for the fixture, since a report without one
  cannot be admitted.

## Evidence

No spike. This decision is an argument from the requirements and from two failure models, and
both are reproducible on paper.

**The replay model.** Take a declaration adjudicated under catalogue vN, add a row to the
catalogue that matches it, and re-run R28 replay against the current catalogue: the entry now
challenges where it once ruled, and reports as inconsistent. Repeat with the version pinned and
it verifies. The same construction run *deliberately* is the retrospective audit — the difference
is entirely which catalogue version is used and what the result is called.

**The over-fire model.** Trace a wrongly-fired trigger through the turn loop: challenge →
resubmission naming a test → adjudication → Ruling with seed, target derivation, and citations →
narration under bounds → ledger. Nothing downstream of the challenge can tell that the first step
was wrong, and the resulting entry is well-formed at every point. That is what places over-firing
in the same severity class as the silent skip rather than below it.

A note on scope: the argument that the catalogue escapes #3's gate is a **design position about
what is SRD-derived content, not a legal opinion**, and it rests entirely on challenge messages
being original prose. If that ever stops being true the conclusion goes with it.

## Status of implementation

**Implemented.** `core/triggers.py`: `Catalogue` carries a `version` and its rows, `MatchCondition`
is the closed operator set, and `MatchContext` is the projection the matcher sees — which excludes
the declaration's free-text label, so a skip cannot be waved through by how it was worded. The
version in force is recorded on the declaration's ledger entry and replay uses the recorded one.

The catalogue remains **known-incomplete** and `AGENTS.md` discloses it: the SRD supplies explicit
triggers only for forced saves, attacks and stated hazards, and catalogue recall is unmeasurable
from play alone because a missed skip leaves no trace.

_Corrected 2026-08-24 ([#126](https://github.com/eddiefiggie/srd-rules-engine/issues/126)). This section read **"None"** for every build between this record landing and that date, while the work it specifies had shipped — a dated claim that could not notice its own staleness._
