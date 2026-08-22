# 0005 — Retry bounds belong to the turn loop, and exhaustion is not a rules outcome

- **Status:** Accepted, 2026-08-22
- **Settles:** [#11](https://github.com/eddiefiggie/srd-rules-engine/issues/11)
- **Requirements:** R3, R6, R26, R30 · touches R8, R10, R22, R29
- **Related:** [0001 — the agent seam](0001-agent-seam.md) makes the driver the decider;
  [0002 — ledger durability](0002-ledger-durability.md) supplies the terminal-outcome precedent;
  [0004 — the trigger catalogue](0004-trigger-catalogue.md) is why a repeating challenge is
  usually the engine's fault

## Context

F2 and F3 both loop. The engine refuses, the agent resubmits, and F3 said only that "bounded
retries apply" — without a bound, a behaviour at the bound, or an owner.

The failure is real rather than theoretical. An agent that misunderstands *why* its declaration
was refused will usually resubmit something equivalent, and every cycle costs a model call. Left
open, a confused agent burns a session and leaves a ledger full of refusals with no terminal
record explaining why it stopped.

Three things reshaped the question before any preference entered.

### Two of the issue's three candidates are the same candidate

The issue offered a terminal status surfaced to the human, an engine-selected legal default, and
aborting the turn. But under [0001](0001-agent-seam.md) the loop ends the turn with a terminal
outcome and the **driver** decides what follows — which is already how
[0002](0002-ledger-durability.md) handles a failed ledger append. "Surface it to the human" and
"abort the turn" are therefore the same engine behaviour under two different drivers, not two
engine behaviours. The scripted reference driver aborts; the human-CLI one can hand control to
the person.

That leaves one genuine question about behaviour at the bound: does the engine ever produce an
outcome on its own?

### Exhaustion is not a rules status

[0002](0002-ledger-durability.md) settled the shape of this for infrastructure failure: rules
statuses describe rules, and reusing one for something a caller cannot fix by re-declaring hands
the agent a status it will reasonably try to act on.

Exhaustion is the same kind of thing. **No rule says "you declared badly three times, therefore
X."** It is the loop giving up, and it belongs in the same vocabulary as a full disk rather than
alongside `challenged`, `rejected`, and `blocked`.

### The bound cannot live in the core

The adjudication core answers one declaration and has no memory of having answered before.
Counting attempts is session state, which R9 requires to have a named owner. And a bound placed
in the core would be a half-measure regardless, because a consumer calling adjudication directly
gets outcome authority without the skip guarantee — so the core cannot be where the loop is
governed.

## Options considered

### What happens at the bound

- **The engine selects a legal default and discloses it.** Rejected, on a ground the issue does
  not name. It creates a **bypass**: an agent that cannot or will not produce a legal declaration
  is adjudicated anyway by exhausting the budget, which converts the retry bound from a brake
  into a second route to an outcome. It also makes R10 vacuous — recording "the alternatives the
  read surface offered" exists so a legal-but-wrong classification is reviewable after the fact,
  and there is nothing to review when the engine did the classifying. Finally it takes *which
  rule applies* from the agent, which is the half of the division of labour the agent is supposed
  to keep.
- **The loop ends the turn unconditionally.** Rejected. It is the right behaviour for a scripted
  driver and the wrong one for a human at a terminal who could resolve the confusion in a single
  exchange. Making it unconditional in the loop denies the driver a choice that costs the loop
  nothing to offer.
- **A terminal outcome the driver decides on.** Adopted.

### Budget structure

- **Separate budgets for challenges and rejections.** Rejected. The asymmetry the issue names is
  real — a rejection says *not that test*, a challenge says *some test* — but the two interleave:
  a challenge answered with an illegal test produces a rejection, so a sequence can alternate.
  Separate counters then need an arbitration rule for interleaved sequences, and the rule would
  be arbitrary. The argument that a challenged agent is "closer to succeeding" also describes an
  agent that *succeeds* on its next attempt and never touches the bound.
- **One budget, with the terminal reason naming the signature.** Adopted. The distinction is
  preserved where it does work — in triage and in R30's report — rather than in the arithmetic.

### The number

Two was rejected as cutting off a legitimate recovery: challenged, then a wrong test rejected,
then correct is a two-refusal sequence a competent agent can produce. Five was rejected as making
the terminal path rare enough to stay untested while costing more calls on every confused agent.

## Decision

**1. The bound is the turn loop's, not the core's.** The core keeps returning `challenged`,
`rejected`, and `blocked` per declaration as it always did, with no attempt counting. R33 is
unaffected: this is policy, not rules.

**2. One budget per declaration slot. Default 3 refusals, configurable, `None` meaning
unbounded.** A *declaration slot* is one actor's attempt to produce one adjudicated action within
a turn; the counter resets when a Ruling is produced or the turn ends. Unbounded is an explicit
opt-in, and the human-CLI reference driver is expected to use it — a person burns no model calls
and can be told exactly what is wrong.

**3. Two identical refusals terminate immediately, ahead of the general bound.** A resubmission
that draws the *same* refusal has demonstrated the agent cannot use the feedback, and further
retries spend calls on a loop already going nowhere.

Identity is **structural, never textual**:

| Refusal | Identical when |
|---|---|
| `challenged` | The same set of trigger ids fired, in the ordering [0004](0004-trigger-catalogue.md) fixes |
| `rejected` | The same reason code and the same citation |

Prose is not compared. The engine does not read its own messages any more than it reads the
agent's label — the same discipline R6 imposes, applied to the engine's own output.

**4. Exhaustion is a terminal turn outcome, not a Ruling status.** It carries a reason naming the
signature that ended it:

| Reason | Meaning |
|---|---|
| `no-progress` | Two identical refusals. Under 0004, a repeating trigger set usually means an over-broad row — **an `srd-fidelity` defect, not an agent failure** |
| `challenge-churn` | The bound reached on challenges that differed |
| `rejection-churn` | The bound reached on rejections that differed |
| `mixed-churn` | The bound reached on a mixture |

**5. The terminal outcome discloses what would have been accepted, without choosing among it.**
It carries the full refusal history for the slot and the legal alternatives the read surface had
offered. That is what makes a report actionable — and under 0004 a `no-progress` terminal entry
naming the trigger ids that would not clear is most of the required fixture already.

Disclosing the alternative set is not the rejected option: naming what is legal is the read
surface's existing job (R18), while *picking* one is the agent's.

**6. Exhaustion appends its own ledger entry**, distinct from a declaration, a challenge, a
rejection, and a Ruling.

**7. R30's report flags exhausted slots, and must not count them as narration gaps.** An
exhausted slot produces no Ruling, so there is nothing to narrate. Without an explicit rule, every
exhaustion would surface as "a Ruling with no narration" — a different defect entirely, and one
that would make the report's most important signal noisy.

**8. The `blocked` loop is deliberately out of scope.** R22's `blocked` status also invites a
resubmission, but it is a different actor failing: the driver has not supplied a fact, rather than
the agent misjudging a rule. It is a distinct request type under 0001 and wants its own treatment.
Filed as [#33](https://github.com/eddiefiggie/srd-rules-engine/issues/33) rather than folded in
here, because bounding it under this budget would charge an agent for a driver's omission.

## Why

### A bypass is worse than a stall

The instinct behind an engine-selected default is that play should continue. But consider what the
agent learns. If failing to declare legally three times produces an adjudicated outcome anyway,
then declaration is optional — expensive, but optional — and the mechanism that makes the agent
state which rule applies has an exit that costs only latency.

This project's guard against invented outcomes is that **the only path to a result runs through a
declaration the agent is accountable for**. An engine-selected default puts a second path beside
it, reached by failure. A stalled turn is a visible, diagnosable, recoverable state; a bypass is
an invisible erosion of the contract, and it erodes fastest under exactly the conditions that
produce it.

### One counter, because the interesting distinction is not arithmetic

Splitting the budget assumes the useful question is *how many more tries does this agent get*.
It is not. The useful question is *what kind of stuck is this*, and that is answered by the
terminal reason, which a single counter reports just as well.

The signatures also do not map onto the split cleanly. A `no-progress` termination on a repeating
trigger set is, under 0004, most likely **the engine's fault** — an over-broad catalogue row that
no declaration can clear. A separate challenge budget would have given that case *more* attempts,
which is precisely backwards: the fastest possible termination is what produces the fixture that
gets the row narrowed.

### Structural identity, because the alternative reintroduces prose

Comparing refusal messages as text would be the obvious implementation and a quiet mistake. Messages
carry citations and phrasing that may be templated on situational values, so two refusals of the
same kind can differ textually while being the same refusal — and two different refusals could
coincide textually. Comparing the trigger id set and the reason code answers the question that was
actually asked, and it keeps the engine out of the business of reading prose, including its own.

### Unbounded is a real configuration, not an escape hatch

The cost model that motivates a bound is model calls. A human driver has none. Treating the bound
as universally desirable would import a constraint from one deployment into all of them, and the
human-CLI driver is exactly where a person could resolve in one exchange what an agent could not
resolve in ten.

## Consequences

**Accepted costs.**

- **Three is a magic number.** No principle sets it; it is the smallest value leaving room for the
  realistic recovery sequence. It is configurable precisely because it is a guess.
- **An exhausted turn loses the actor's action** unless the driver intervenes. That is intended —
  the alternative is manufacturing an outcome — but it is a genuine cost in play, not a neutral
  one.
- **Two mechanisms instead of one.** The no-progress path and the general bound can both fire, and
  a reader has to know which one did. The terminal reason carries it, at the price of a
  vocabulary to learn.
- **Unbounded configurations can still hang**, by design. A driver that opts out of the bound owns
  the consequence, and the no-progress path is the only protection that remains.

**Follow-on effects.**

- **[#10](https://github.com/eddiefiggie/srd-rules-engine/issues/10) gains an entry type:** the
  exhaustion terminal entry, carrying the reason, the refusal history, and the offered
  alternatives. That is the second constraint 0004 and this record have added to that gate.
- **R8 is amended** to state that the turn loop owns the retry bound, its default and
  configurability, and the terminal outcome it produces. **R30 is amended** to flag exhausted
  slots and to exclude them from the narration-gap check.
- **[#8](https://github.com/eddiefiggie/srd-rules-engine/issues/8) (verifying recorded
  alternatives) inherits a second consumer.** The terminal entry carries the offered alternatives
  for the same reason R10 does, so whatever that gate decides about capturing and verifying them
  has to cover the exhaustion path too, where no Ruling exists to hang them on.
- **[#33](https://github.com/eddiefiggie/srd-rules-engine/issues/33)** filed for the `blocked`
  loop.
- The `no-progress` reason is a **triage input for `srd-fidelity`**, since 0004 classified an
  over-firing trigger as a rule modelled wrongly.

## Evidence

No spike. The argument is from the requirements and from two traces, both reproducible on paper.

**The bypass trace.** Follow an agent that never produces a legal declaration through each
candidate behaviour at the bound. Under an engine-selected default it reaches a Ruling carrying a
seed, a target derivation, and citations, having never named a test — and the ledger entry is
well-formed. Under a terminal outcome it reaches a recorded stop naming what it was offered and
never refused. The first is indistinguishable after the fact from an agent that declared
correctly; the second is unmistakable.

**The interleaving trace.** Enumerate the sequences a two-status loop can produce — challenge
then rejection, rejection then challenge, repeats of each — and try to charge them against
separate budgets. Every allocation rule that resolves the alternating case is a choice with no
justification behind it, which is the signal that the split is not carrying its weight.

A note on method: the first pass treated "surface to the human" and "abort the turn" as competing
engine behaviours, and only re-reading [0001](0001-agent-seam.md) showed they are one behaviour
under two drivers. The issue's option list had framed a driver policy as an engine decision, and
taking that framing at face value would have put a deployment concern inside the loop.

## Status of implementation

**None.** M0 holds that nothing is built until the gates close. This record specifies where the
bound lives, its shape and defaults, and the terminal outcome's contents; it lands with the turn
loop when M1 opens.
