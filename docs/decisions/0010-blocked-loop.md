# 0010 — A block is a suspension, and the loop bounds itself

- **Status:** Accepted, 2026-08-22
- **Settles:** [#33](https://github.com/eddiefiggie/srd-rules-engine/issues/33)
- **Requirements:** R22, R26, R30 · touches R8, R21, R25, R28
- **Related:** [0005 — retry bounds](0005-retry-bounds.md), which deliberately excluded this;
  [0001 — the agent seam](0001-agent-seam.md) makes the driver the decider;
  [0004 — the trigger catalogue](0004-trigger-catalogue.md) supplies the defect-class analogue

## Context

[0005](0005-retry-bounds.md) bounded the loops behind `challenged` and `rejected` and excluded
`blocked`, on the grounds that a driver failing to supply a fact is a different actor failing than
an agent misjudging a rule. This is that residue.

R22 returns `blocked` when a rule declares a fact dependency, the port holds no value, and no
default of any kind exists. The caller supplies the fact and adjudication proceeds. Nothing
bounded that.

Two things turned out to be true that the issue — which this project filed itself — did not
account for.

### A block is a suspension, not a refusal

A challenge or a rejection means the declaration was *wrong*. A `blocked` means the declaration
was **accepted** — it passed R3's validation and the trigger check — and then stalled at fact
resolution. Nothing the agent did needs redoing.

That is what decides whether it belongs in 0005's budget. That budget counts refusals, and its
terminal reasons (`challenge-churn`, `rejection-churn`, `mixed-churn`) all name agent behaviour. A
block is not in that family, and describing one with those words would misattribute it.

### The loop is self-terminating

R21 makes a rule's fact dependencies a **static declaration**, fixed when the rule is defined. So
for a given declaration the set of unresolved facts can only ever shrink: supplying a fact removes
it from the set, and nothing can add to it, because the rule's dependencies were settled before
the turn began.

Either a round shrinks the set — which terminates in at most as many rounds as the rule declares
facts — or it does not, and there is nothing to wait for. **There is no path that loops
indefinitely while making progress.**

### Blocking is usually correct behaviour

R22 returns `blocked` precisely when no default of any kind would be honest. In a human-driven
session that is the engine refusing to invent and asking the person to decide — a prompt, not a
fault. This is a real asymmetry with 0005, where a challenge loop is always pathological.

The pathological case here is narrower: a fact type that blocks *repeatedly* is evidence its R22
classification is wrong.

## Options considered

- **Share 0005's declaration budget.** Rejected. It charges the agent for a driver's omission,
  which is the reason this was split out, and every terminal reason in that vocabulary describes
  something the agent did.
- **Require the agent to re-declare after a block.** Rejected. Uniform with challenge and
  rejection, and one resume path instead of two — but it spends a model call reproducing a
  declaration that was already correct, and it would pull blocks back into a budget whose
  vocabulary does not fit them.
- **Name one missing fact at a time.** Rejected. It turns one integration problem into N round
  trips, and a driver able to supply two of three facts discovers that only after two rounds it
  could have skipped.
- **A configurable count bound alongside no-progress.** Rejected. See below.
- **Report repeated blocking without calling it a defect.** Rejected, though it has a real point
  behind it, addressed below.

## Decision

**1. `blocked` names every unresolved fact type**, with each type's R22 default classification —
which is `absent` for all of them, since that is what blocking means. Same shape as
[0004](0004-trigger-catalogue.md)'s rule that a challenge names every trigger that fired.

**2. Supplying the facts resumes the same declaration.** The engine re-resolves and rules. The
agent does not re-declare, and the turn loop holds the pending declaration on its own stack, where
[0001](0001-agent-seam.md) already puts session state.

**3. There is no count bound.** The shrinking-set invariant bounds the loop already.

**4. A round that fails to shrink the unresolved set terminates immediately.** Identity is
**structural** — the set of unresolved fact types, compared as a set — never a message or a
rendered prompt. The same discipline R6 imposes on the matcher and
[0005](0005-retry-bounds.md) imposes on refusal comparison.

Note this catches the case a count bound is usually reached for: a driver that writes facts but
writes the *wrong* ones makes no progress by definition, because the unresolved set is unchanged.

**5. Termination is a terminal turn outcome, not a rules status**, carrying the reason
`fact-unavailable`. The driver decides what follows, exactly as in
[0005](0005-retry-bounds.md) — the scripted driver aborts, the human-CLI driver can hand control
to the person.

**6. The engine never invents a default at the terminal.** R22 blocking *means* no default is
honest; supplying one at the bound would be the engine fabricating a rules input, which is worse
than [0005](0005-retry-bounds.md)'s rejected bypass rather than merely equivalent to it.

**7. The terminal entry carries the unresolved fact types and their classification**, and R30's
report flags turns that ended this way.

**8. A fact type that blocks repeatedly is a data-model defect.** A type declared `absent` that
blocks in session after session probably warranted an engine-chosen default. Repeated occurrences
are grounds to revisit the declaration rather than to keep supplying the value by hand. Because
R30's report is per session, the cross-session view belongs to the ledger reader's audit
capability ([0006](0006-ledger-format.md)), which already reads across many closed ledgers.

**9. Only core fact types can block.** [0008](0008-extension-channel.md) established that no
engine rule may consume an extension fact, so no extension type ever appears in an unresolved set.

## Why

### The shrinking-set invariant, and why a count bound would be worse than nothing

A count bound placed on top of a self-terminating loop can do exactly one thing: cut off a
sequence that was making progress. In a human-driven session that sequence is a person supplying
facts one at a time and thinking in between, which is the behaviour the design should most want to
permit.

There is a second objection. A bound that essentially never fires is machinery whose terminal path
is never exercised outside tests — and it is a *safeguard*, so the first time it runs for real will
be the first time anyone finds out whether it works.

That is worth distinguishing from [0007](0007-alternatives-verification.md), which deliberately
kept `verified-stale` even though a sequential single-actor loop may make it unreachable. The
difference is what the rare path is for. **A signal that never fires is telling you something is
healthy, and its value is entirely in the case where it does fire. A safeguard that never fires is
untested code guarding a case that cannot occur.** Keep the first; do not add the second.

### Suspension explains the whole shape

Almost every part of this decision follows from a block being a suspension rather than a refusal.
The declaration survives, so it resumes rather than being re-made. The agent is not at fault, so
the agent's budget is not charged. The engine has not refused anything, so no rules status changes
hands. And the terminal reason names an *unavailability* rather than a behaviour, because nobody
misbehaved — the campaign simply has no answer and nothing may invent one.

The one place it does not reach is decision 8, which is about the fact type's declaration rather
than about any session.

### Repeated blocking is a defect claim worth making

The counter-argument is real: blocking is legitimate, so calling a repeatedly-blocking type
defective risks flagging a campaign that genuinely leaves something undecided.

It is outweighed by the same reasoning [0004](0004-trigger-catalogue.md) applied to a repeating
trigger set. R22's classification is a **design-time claim about the SRD** — that this fact has no
defensible default, so the engine must stop rather than choose. If in practice every session must
supply it by hand, that claim is being tested and failing, and the response is to revisit the
classification rather than to accept the friction indefinitely.

Framing it as a defect is also what gets it looked at. A signal recorded without a name is a signal
nobody triages.

## Consequences

**Accepted costs.**

- **The turn loop holds a pending declaration across a block.** That is new session state and a
  new lifetime to reason about. A crash mid-block loses it — consistent with
  [0002](0002-ledger-durability.md)'s finding that recovery is not resumption, so a restart
  replays the transcript and the agent re-declares. Worth stating because the declaration *is* in
  the ledger, and a reader may reasonably expect it to resume.
- **Drivers acquire an obligation.** A driver must not return from a blocked-fact request without
  either supplying facts or intending to stop, because a bare return is indistinguishable from no
  progress and terminates the turn. That is an easy thing to get wrong in a driver that polls, and
  it belongs in the driver documentation rather than being discovered.
- **No count bound means a pathological driver can be slow rather than stopped.** One that shrinks
  the set by one fact per round, very slowly, is making progress by this definition. Bounded by the
  rule's declared fact count, so it is finite — but "finite" is doing some work there.
- **Decision 8 asserts something about a fact type from session evidence**, which is an inference
  and can be wrong for a campaign that is genuinely undecided.

**Follow-on effects.**

- **R22 is amended** with the every-unresolved-fact rule, the resume behaviour, the no-progress
  termination, and the prohibition on inventing a default at the terminal. **R30's report** flags
  `fact-unavailable` terminations.
- **[0006](0006-ledger-format.md)'s ledger gains a second terminal reason** on the exhaustion entry
  type — `fact-unavailable` alongside [0005](0005-retry-bounds.md)'s four. The entry type itself is
  unchanged, which is the envelope/payload split working as intended.
- **The ledger reader's audit capability gains a query**: fact types that blocked across sessions.
  This is the second use for cross-session reading, after
  [0004](0004-trigger-catalogue.md)'s trigger recall — enough that it is a capability rather than a
  one-off.
- **M0 closes with [#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13).**

## Evidence

No spike. The shrinking-set invariant is checkable directly against R21: a rule's fact
dependencies are declared with the rule, not computed per adjudication, so the unresolved set for
a fixed declaration has no mechanism by which to grow. Enumerate what could add to it — a rule
consuming a fact conditionally on another fact's value would be the candidate — and confirm R21
does not permit it.

A note on method: this issue was filed by this project, and it proposed that
[0005](0005-retry-bounds.md)'s no-progress rule "probably transfers directly and is probably the
whole answer." That guess was right and the reasoning behind it was not — it rested on an analogy
to 0005 rather than on anything about this loop. The actual reason is the invariant above, which
is stronger than the analogy and also explains why the *other* half of 0005's mechanism, the count
bound, should not transfer. **An analogy that produces the right answer will still produce the
wrong scope.**

## Status of implementation

**None.** M0 holds that nothing is built until the gates close. This record specifies the blocked
loop's shape and termination; it lands with the memory port and the turn loop when M1 opens.
