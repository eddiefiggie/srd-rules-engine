# Decision records

One file per significant design decision: what was decided, what else was on the table, and why.

## Why these exist

The reasoning is the perishable part. Code shows what was built and git shows when, but neither
tells you that a callback-shaped agent seam was rejected because its asynchronous twin duplicated
100% of the rules logic, or that the ledger is hash-chained despite this project explicitly *not*
defending a solo campaign against its own owner.

Without that written down, the next person to read the code — a contributor, or you in six
months — sees an unusual choice, assumes nobody thought about it, and either re-argues it from
scratch or quietly changes it back. Both are expensive. The second is worse, because the reason
the choice was made is usually still true.

So: **read the record covering an area before reopening a question in it.** If the record is
wrong, that is worth knowing and worth saying. If it merely looks odd, the record probably
explains why.

## How they work here

**A `gate` issue closes by producing one.** A gate is a design question with no default answer,
and it blocks implementation — because an unanswered gate otherwise gets settled by whoever
writes the code first, silently and without the question ever being asked. The issue poses the
question, the record answers it, and the plan in [`../plans/`](../plans/) is amended to match.

**They are numbered and immutable.** A decision that changes does not get edited. It gets a new
record that supersedes the old one, so the trail stays intact and a reader can see what was
believed at the time and what changed. Both files carry `Supersedes:` and `Status:` lines for
this reason.

**They record rejected options, not just the winner.** A record listing only what was chosen is a
description of the code, which the code already provides for free.

## Format

Numbered `NNNN-short-slug.md`, four digits, allocated in order. The sections in use:

| Section | What goes in it |
|---|---|
| Header | Status, the issue it settles, requirements touched, related records, what it supersedes |
| **Context** | What forced a decision. The constraints, and the cases a candidate had to survive |
| **Options considered** | Including the ones rejected quickly, and why they were |
| **Decision** | The ruling, stated plainly, with signatures where they help |
| **Why** | The argument, with measurements where they exist |
| **Consequences** | Accepted costs and follow-on effects. Costs go here even when the decision is clearly right |
| **Evidence** | How to reproduce any spike behind it — including where the method went wrong |
| **Status of implementation** | Usually "none", because M0 gates close before anything is built |

Not a standard, and section names vary between projects that do this. What matters is that the
rejected options and the reason survive, not the exact headings.

## Current records

| # | Decision | Settles |
|---|---|---|
| [0001](0001-agent-seam.md) | The agent seam is a generator of typed requests | [#4](https://github.com/eddiefiggie/srd-rules-engine/issues/4) |
| [0002](0002-ledger-durability.md) | Nothing escapes the engine before its record is durable | [#5](https://github.com/eddiefiggie/srd-rules-engine/issues/5) |
| [0003](0003-seed-and-verification.md) | No structured seed for mechanics; the official SRD 5.2.1 is the verification reference | [#6](https://github.com/eddiefiggie/srd-rules-engine/issues/6) |
| [0004](0004-trigger-catalogue.md) | The trigger catalogue is data, and over-firing is a fidelity defect | [#7](https://github.com/eddiefiggie/srd-rules-engine/issues/7) |
| [0005](0005-retry-bounds.md) | Retry bounds belong to the turn loop, and exhaustion is not a rules outcome | [#11](https://github.com/eddiefiggie/srd-rules-engine/issues/11) |
| [0006](0006-ledger-format.md) | JSONL with a fixed envelope, and a reader API rather than a public file format | [#10](https://github.com/eddiefiggie/srd-rules-engine/issues/10) |

## What belongs here, and what doesn't

- [`../plans/`](../plans/) holds the requirements artifact behind each milestone — *what we are
  building*. Decision records amend it. Progress lives in git and in issues, never in the plan
  body.
- **GitHub Issues** holds open work — *what is left to do*. A record is the answer to a question;
  the issue is the question. Neither is a queue for the other.
- A record is **not** a bug postmortem. If a decision turns out badly it gets a superseding
  record, so the trail shows what was believed and what changed.
