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

**A closing gate files what it did not build.** Closing the gate is the moment the design stops
being tracked: the record makes it look settled, and a closed issue looks finished. So a clause
this record specifies and nobody has built gets an issue of its own, named beside the clause in
**Status of implementation**. `AGENTS.md` carries the rule; `tests/test_decision_records.py`
asserts the section is there.

**They are numbered and immutable.** A decision that changes does not get edited. It gets a new
record that supersedes the old one, so the trail stays intact and a reader can see what was
believed at the time and what changed. Both files carry `Supersedes:` and `Status:` lines for
this reason.

**One section is exempt from that, and has to be.** **Status of implementation** describes the
tree rather than the decision, so it is updated as work lands — by appending a dated note rather
than by rewriting history, the way [0021](0021-a-round-is-six-seconds.md) and
[0022](0022-compat-is-a-reader-version.md) carry theirs. Nothing else in a record moves.

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
| **Status of implementation** | What is built, what is not, and the issue holding each unbuilt clause. Maintained as work lands — every other section is frozen |

Not a standard, and section names vary between projects that do this. What matters is that the
rejected options and the reason survive, not the exact headings.

## Current records

| # | Decision | Settles |
|---|---|---|
| [0001](0001-agent-seam.md) | The agent seam is a generator of typed requests | [#4](https://github.com/eddiefiggie/srd-rules-engine/issues/4) |
| [0002](0002-ledger-durability.md) | Nothing escapes the engine before its record is durable | [#5](https://github.com/eddiefiggie/srd-rules-engine/issues/5) |
| [0003](0003-seed-and-verification.md) | No structured seed for mechanics; the official SRD 5.2.1 is the verification reference — **superseded in part by [0017](0017-verification-is-asserted-not-read.md)** | [#6](https://github.com/eddiefiggie/srd-rules-engine/issues/6) |
| [0004](0004-trigger-catalogue.md) | The trigger catalogue is data, and over-firing is a fidelity defect | [#7](https://github.com/eddiefiggie/srd-rules-engine/issues/7) |
| [0005](0005-retry-bounds.md) | Retry bounds belong to the turn loop, and exhaustion is not a rules outcome | [#11](https://github.com/eddiefiggie/srd-rules-engine/issues/11) |
| [0006](0006-ledger-format.md) | JSONL with a fixed envelope, and a reader API rather than a public file format | [#10](https://github.com/eddiefiggie/srd-rules-engine/issues/10) |
| [0007](0007-alternatives-verification.md) | Read tokens make the alternatives claim checkable without touching R19 | [#8](https://github.com/eddiefiggie/srd-rules-engine/issues/8) |
| [0008](0008-extension-channel.md) | Reverse-DNS extension namespaces that no engine rule may consume | [#9](https://github.com/eddiefiggie/srd-rules-engine/issues/9) |
| [0009](0009-reference-memory-store.md) | The reference memory store is flat JSON, because it is a projection of the ledger | [#12](https://github.com/eddiefiggie/srd-rules-engine/issues/12) |
| [0010](0010-blocked-loop.md) | A block is a suspension, and the loop bounds itself | [#33](https://github.com/eddiefiggie/srd-rules-engine/issues/33) |
| [0011](0011-module-layout-and-versioning.md) | Layer boundaries are a guard test, and schemas carry a min-reader floor | [#13](https://github.com/eddiefiggie/srd-rules-engine/issues/13) |
| [0012](0012-fixture-provenance.md) | Provenance selects the entry point, not a branch inside one | [#41](https://github.com/eddiefiggie/srd-rules-engine/issues/41) |
| [0013](0013-effect-shape-normalisation.md) | The effect-shape vocabulary normalises on mechanism, not on the feature that exhibits it | [#76](https://github.com/eddiefiggie/srd-rules-engine/issues/76) |
| [0014](0014-positional-state.md) | Position is three integer coordinates in feet, and distance is never a float | [#17](https://github.com/eddiefiggie/srd-rules-engine/issues/17), [#20](https://github.com/eddiefiggie/srd-rules-engine/issues/20) |
| [0015](0015-reactions-and-the-agent-seam.md) | The generator seam already serves reactions; what they need is state and triggers | [#16](https://github.com/eddiefiggie/srd-rules-engine/issues/16), [#4](https://github.com/eddiefiggie/srd-rules-engine/issues/4) |
| [0016](0016-adapters-hold-the-turn.md) | An adapter holds the suspended turn, and never exposes adjudication | [#97](https://github.com/eddiefiggie/srd-rules-engine/issues/97) |
| [0017](0017-verification-is-asserted-not-read.md) | Verification is a pattern asserted against the document, and it does not cover modelling — supersedes [0003](0003-seed-and-verification.md) in part | [#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21) |
| [0018](0018-api-stability.md) | Three stability tiers, an integer API version, and a committed surface that is enumerated | [#39](https://github.com/eddiefiggie/srd-rules-engine/issues/39) |
| [0019](0019-kind-is-a-filing-label.md) | `kind` is a filing label, not a model, and stays one axis | [#84](https://github.com/eddiefiggie/srd-rules-engine/issues/84) |
| [0020](0020-two-kinds-of-time.md) | Two kinds of time, minutes as the unit, and the round-to-clock bridge left unbuilt — clause 1 amended by [0021](0021-a-round-is-six-seconds.md) | [#85](https://github.com/eddiefiggie/srd-rules-engine/issues/85) |
| [0021](0021-a-round-is-six-seconds.md) | A round is exactly six seconds, and the clock still does not advance itself — amends [0020](0020-two-kinds-of-time.md) clause 1 | [#108](https://github.com/eddiefiggie/srd-rules-engine/issues/108) |
| [0022](0022-compat-is-a-reader-version.md) | `compat` is a reader version, and no payload derives it from its own schema version — amends [0011](0011-module-layout-and-versioning.md) clause 5 | [#106](https://github.com/eddiefiggie/srd-rules-engine/issues/106) |
| [0023](0023-the-turns-end-is-a-loop-owned-phase.md) | The turn's end is a loop-owned phase, and an early-out is two mechanisms rather than one | [#110](https://github.com/eddiefiggie/srd-rules-engine/issues/110) |
| [0024](0024-the-build-line-is-the-build-record.md) | The README's build line is the build record, and `CHANGELOG.md` is retired — amends [0018](0018-api-stability.md)'s Provisional tier | [#146](https://github.com/eddiefiggie/srd-rules-engine/issues/146) |
| [0025](0025-sight-is-a-relation-over-stored-state.md) | Sight is a relation derived over stored state, and the mapping that resolves it ships empty until the pages are read | [#138](https://github.com/eddiefiggie/srd-rules-engine/issues/138) |
| [0026](0026-terrain-enters-as-state.md) | Terrain enters by one route and it is state, and replay is not an argument for either side — resolves the seam [0025](0025-sight-is-a-relation-over-stored-state.md) clause 2 created | [#151](https://github.com/eddiefiggie/srd-rules-engine/issues/151) |
| [0027](0027-occasions-and-outcomes-without-a-roll.md) | The turn's start is a phase too, an obligation is identified by its rule id, and an outcome may exist without a d20 test — extends [0023](0023-the-turns-end-is-a-loop-owned-phase.md) one phase earlier | [#124](https://github.com/eddiefiggie/srd-rules-engine/issues/124), [#140](https://github.com/eddiefiggie/srd-rules-engine/issues/140) |
| [0028](0028-a-level-carries-the-rule-that-caused-it.md) | An Exhaustion level carries the rule id that caused it and the count is derived, because four of the five removal rules turn on a level's provenance | [#180](https://github.com/eddiefiggie/srd-rules-engine/issues/180) |
| [0029](0029-whether-a-wall-blocks-sight-is-a-property-of-the-wall.md) | Whether a barrier blocks sight is a field on the barrier, not a rule — the document answers it per wall and answers it both ways | [#188](https://github.com/eddiefiggie/srd-rules-engine/issues/188) |
| [0030](0030-an-unanswerable-qualifier-resolves-away-from-invention.md) | A qualifier this engine cannot check resolves in whichever direction cannot manufacture an outcome — which is why reactions withhold and Frightened applies | [#190](https://github.com/eddiefiggie/srd-rules-engine/issues/190) |
| [0031](0031-a-contradiction-in-the-document-is-an-absent-rule.md) | Two printed rules that disagree state no rule, so the mechanic is excluded under R31 — and [0030](0030-an-unanswerable-qualifier-resolves-away-from-invention.md) clause 1 must not be reached for one | [#182](https://github.com/eddiefiggie/srd-rules-engine/issues/182), [#205](https://github.com/eddiefiggie/srd-rules-engine/issues/205) |
| [0032](0032-an-outcome-conditional-on-its-own-damage.md) | An effect may be conditional on a sibling's settled damage, asked where the damage is *taken* rather than rolled — and the seven rules that key off damage dealt are three shapes, not one | [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173) |
| [0033](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md) | A glossary entry is an index into the rules, not the boundary of one — a shape's content is what the document states about it anywhere, and #228's three options are all rejected | [#228](https://github.com/eddiefiggie/srd-rules-engine/issues/228) |
| [0034](0034-a-term-the-document-defines-and-never-uses.md) | A term the document defines and never uses is vocabulary — `weapon-attack` has no consumers, so it is neither a second shape nor a double count, and the denominator falls to 210 | [#229](https://github.com/eddiefiggie/srd-rules-engine/issues/229) |
| [0035](0035-two-names-for-one-thing-are-one-shape.md) | Two names for one thing are one shape — `save` and `saving-throw` already resolved to the same symbol, so the test is identity rather than usage, and both figures fall to 95 of 209 | [#230](https://github.com/eddiefiggie/srd-rules-engine/issues/230) |

## What belongs here, and what doesn't

- [`../plans/`](../plans/) holds the requirements artifact behind each milestone — *what we are
  building*. Decision records amend it. Progress lives in git and in issues, never in the plan
  body.
- **GitHub Issues** holds open work — *what is left to do*. A record is the answer to a question;
  the issue is the question. Neither is a queue for the other.
- A record is **not** a bug postmortem. If a decision turns out badly it gets a superseding
  record, so the trail shows what was believed and what changed.
