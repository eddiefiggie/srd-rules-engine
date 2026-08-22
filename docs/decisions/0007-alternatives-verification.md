# 0007 — Read tokens make the alternatives claim checkable without touching R19

- **Status:** Accepted, 2026-08-22
- **Settles:** [#8](https://github.com/eddiefiggie/srd-rules-engine/issues/8)
- **Requirements:** R10, R19 · touches R5, R9, R18, R30
- **Related:** [0005 — retry bounds](0005-retry-bounds.md), whose exhaustion entry also carries
  alternatives; [0006 — ledger format](0006-ledger-format.md) supplies the canonical form the
  digest is taken over

## Context

R10 exists so that a *legal-but-wrong* classification is reviewable after the fact: the
declaration records the alternatives the read surface offered, and the Ruling and its ledger entry
carry them.

R19 makes read-surface calls idempotent, non-mutating, and explicitly forbidden from appending to
the ledger. So there is no server-side record of the menu the agent was shown, and the
alternatives on a declaration are **the agent's claim about what it was offered**.

That is worse than a missing field. A missing field is honestly absent; an unverified claim
occupies the place where evidence should be and reads as evidence. The one mechanism meant to
catch the agent misclassifying is supplied by the agent.

Two things reshaped the question.

### The mismatch ambiguity is an artefact of not recording enough

The issue set re-derivation aside partly because state may move between the read and the
declaration, making a mismatch ambiguous between drift and falsehood.

That ambiguity only exists if nothing records *which state the read was taken against*. R9 already
requires mechanical state to have a named owner and a stated lifetime; a monotonic **generation**
on it costs almost nothing, and with it a mismatch splits cleanly:

| Condition | Meaning |
|---|---|
| Same generation, different set | The claim is false |
| Older generation | The agent decided from information that has since changed |

Neither is ambiguous. They are different problems with different responses.

### Staleness should be impossible here, which is exactly why it is worth detecting

Solo play, one character, a sequential turn loop: between a read and the declaration that follows
it, there is no other actor to move state. A stale read should therefore never occur in normal
operation.

A signal that fires only when something is genuinely wrong is the most valuable kind available.
The realistic cause is an agent **caching a read across turns** — plausible LLM behaviour, and
otherwise completely invisible, because a cached menu that happens to still be correct produces
indistinguishable output from a fresh one right up until it doesn't.

## Options considered

- **Trust the claim and document the limit.** Rejected. It is the honest version of doing nothing,
  and honesty about the gap does not close it. R10's entire purpose is review, and a reviewer
  holding only the agent's account of what it was offered cannot distinguish a good classification
  from a well-reported bad one.
- **Re-derive at adjudication, with a generation counter.** Rejected, though it survives the
  ambiguity objection once generations are recorded. Its failure is precisely at the case worth
  catching: when the read *was* stale, the engine cannot reconstruct the set that was offered
  without retaining state history, so the claim stays unverifiable exactly when it matters.
- **Relax R19 so reads append.** Rejected on its face, as the issue notes: orientation would
  become expensive and the ledger would fill with reads.
- **Read tokens.** Adopted.
- **A MAC over the token.** Rejected as unnecessary. See below.

## Decision

**1. The read surface returns an opaque read token alongside the legal set.** The token encodes
the **state generation** the set was derived from and a **digest of the offered set**, taken over
[0006](0006-ledger-format.md)'s canonical form.

R19 is untouched. The read surface computes and returns; it does not mutate, and it does not
append. The generation is *read* from the state R9 already governs, and is incremented by the
operations that mutate that state — applied effects and fact writes — never by a read.

**2. The token is opaque.** Its encoding is an implementation detail, consistent with
[0006](0006-ledger-format.md)'s treatment of the ledger file: what is committed is that a token
round-trips and what the engine reports about it, not its bytes.

**3. The declaration carries the token and the alternatives it was offered** — or, per R10, the
explicit marker that no enumerated alternative covered the intent. A token accompanies one read
call and covers the set that call returned; where an agent consulted several read surfaces, it
echoes the one it decided its intent from.

**4. At adjudication the engine returns a verdict**, from a closed vocabulary:

| Verdict | Meaning |
|---|---|
| `verified-fresh` | Digest matches, generation is current. The claim is exactly what was offered, and it was current |
| `verified-stale` | Digest matches, generation is older. The claim is genuine, but the agent decided from state that has since changed |
| `unverified` | Digest does not match. The claim is not what was offered |
| `unread` | No token supplied |

**5. `unread` is the expected verdict for a direct caller**, not an error. A consumer calling
adjudication outside the turn loop already gets outcome authority without the skip guarantee, and
this makes that disclosed limit visible **per ruling** rather than only in prose.

**6. There is one derivation of what is legal**, used by the read surface to enumerate and by the
adjudicator to validate. Drift between what the agent is offered and what will be accepted becomes
impossible by construction rather than detectable afterwards.

**7. A failed verification does not block adjudication.** The engine records the verdict and rules
normally. R30's report flags every verdict that is not `verified-fresh`.

**8. The Ruling carries the verdict alongside the alternatives**, and so does the ledger entry —
including [0005](0005-retry-bounds.md)'s `exhaustion` entry, where each refusal in the history
carries the verdict its declaration earned.

**9. R10's guarantee is restated in the plan to say what it actually delivers**: the alternatives
are the agent's claim, carried with a verdict stating whether that claim was verified against what
the read surface issued and whether it was current.

## Why

### A digest is enough, because forgery is not the threat

[0002](0002-ledger-durability.md) established that this project "is not defending a solo campaign
against its own owner." That does **not** extend to the agent. The agent's unreliability is the
premise of the entire design — it is the party whose claims every other mechanism here exists to
check.

But recognising the agent as untrusted also bounds what is needed, because the agent is an LLM
rather than an adversary with a debugger:

| Failure | Caught by |
|---|---|
| Garbles or paraphrases the offered set | Digest mismatch → `unverified` |
| Invents a token wholesale | Digest mismatch → `unverified` |
| Replays a genuine token from an earlier turn with its matching set | Generation older → `verified-stale` |
| Computes a valid digest for a fabricated set | Not defended against |

The last row is a cryptographic attack requiring deliberate effort and tooling, from a component
that is generating text. A MAC would close it and would bring key management, a secret with a
lifetime, and a new failure mode when the secret rotates — for a threat nobody has. The digest
that [0006](0006-ledger-format.md) already requires for the ledger chain covers everything real.

### One derivation, because two would be two things that can disagree

If the read surface enumerates legal actions with one implementation and the adjudicator validates
with another, they can drift — and the failure mode is the agent being offered an action that is
then rejected. That is an ugly bug: it looks like the agent misbehaving, it consumes
[0005](0005-retry-bounds.md)'s retry budget, and under sufficiently bad luck it exhausts a slot for
something the agent did correctly.

An independent second implementation would catch that drift loudly, which is genuinely attractive.
It was rejected because the alternative is better: with one derivation there is no drift to catch.
This project has now made that trade four times — an empty dependencies list, a matcher that
cannot see the label, a reader API rather than a file format, and now a single legality
derivation. In each case a cross-check was available and a structural impossibility was preferred.

The accepted cost is real and worth naming: a bug *inside* the shared derivation is invisible to
this mechanism, because both sides agree on the same wrong answer. That is what tests are for, and
it is a smaller surface than two implementations that must be kept in agreement.

### Recording rather than rejecting, because this is metadata about a decision, not the decision

The alternatives field is audit metadata. The declaration's named test is validated independently
by R3, so a false alternatives claim does not make the resulting Ruling wrong — it makes the
*record* of it wrong.

Rejecting would repeat the category error [0002](0002-ledger-durability.md) identified when it
declined to reuse `blocked` for a failed ledger append: a rules status names something the caller
can fix by re-declaring, and a buggy agent that misreports what it saw will misreport it again.
Under [0005](0005-retry-bounds.md) that is a `no-progress` termination — a slot burned over
metadata, while a perfectly sound declaration goes unadjudicated.

The disclosure route is also the one the project takes everywhere else. R32 excludes unverified
mechanics *and discloses the exclusion*; R17 discloses unimplemented effect shapes; R22 names when
it defaulted. An unverified claim recorded as `unverified` and flagged in the report is the same
shape: the defect is preserved and visible rather than converted into a refusal that hides it.

## Consequences

**Accepted costs.**

- **A new value crosses the seam.** Every read returns a token and every declaration echoes one,
  which is more surface on the two most-used calls, and one more thing a driver implementer must
  thread through correctly.
- **An agent that consults several read surfaces echoes one token.** The alternatives from the
  others go unrecorded. Acceptable because R10 concerns the alternatives *for the declared
  intent*, but it means a broad read-then-narrow pattern is only partly captured.
- **The generation counter is a new invariant on state.** Everything that mutates R9's state must
  increment it, and a mutation that forgets to will produce false `verified-fresh` verdicts —
  which is the quiet direction to fail in.
- **A bug in the shared legality derivation is undetectable here**, as above.
- **`verified-stale` may prove unreachable in practice.** If the sequential loop makes it
  impossible, the code path exists and is never exercised outside tests. That is the correct
  outcome for a signal of this kind, and it should not tempt anyone to remove it.

**Follow-on effects.**

- **R10 is rewritten** to state what "recorded" guarantees. **R5** adds the verdict to the Ruling's
  contents, **R18** notes that read-surface results carry a token, and **R30's report** flags
  verdicts other than `verified-fresh`. **R19 is unchanged**, which is the point.
- **[0006](0006-ledger-format.md)'s payload versioning gets its first exercise.** Declaration
  entries gain the token, the claimed alternatives, and the verdict — a payload change with no
  envelope change, which is exactly the split that record predicted.
- **[0005](0005-retry-bounds.md)'s `exhaustion` entry gains verdicts** on each refusal in its
  history.
- **[#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13) inherits the token's opacity
  question** — an opaque value still needs a versioning story if its encoding ever changes, and
  that belongs with the other four schemas rather than beside them.

## Evidence

No spike. The argument is from the requirements, plus a threat enumeration that is reproducible by
listing the ways an LLM can produce a wrong alternatives claim and checking each against a digest
and a generation counter — the table above is that enumeration, and the single uncovered row is
the one requiring deliberate cryptographic work from a text generator.

The staleness analysis is checkable by inspection: enumerate what can mutate R9's state between a
read-surface call and the declaration that follows it in a single-actor sequential loop. In solo
play the answer is nothing, which is what makes the signal high-value rather than redundant.

A note on method: this gate looked at first like a choice between an unverifiable claim and a
relaxation of R19, because the issue's framing presented drift-versus-falsehood as an inherent
ambiguity. It is not inherent — it is the consequence of recording a set without recording what it
was a set *of the legal actions at*. Adding one counter to state made two of the four options
viable that had looked closed, and the chosen one is the weaker-looking option from that pair
made strong by the same addition.

## Status of implementation

**None.** M0 holds that nothing is built until the gates close. This record specifies the token's
contents, the verdict vocabulary, and where the verdict is recorded; it lands with the read
surface and the adjudication core when M1 opens.
