# Changelog

Builds are stamped `mmddyyyy.x` — the date they were produced, plus that day's iteration. The
stamp lives in `src/srd_rules_engine/__init__.py`; `tests/test_build_stamp.py` fails CI when
README.md's `**Current build:**` line drifts from it.

Nothing is released yet. Entries below record builds, not releases.

## Unreleased — 2026-08-22 — build `08222026.6`

U6 — the memory port and the flat-JSON reference store.

- **"Typed values only, never prose" is structural: there is no free-text fact kind.** A core fact
  is an integer, a boolean, or a choice from a set its type declares. Prose cannot be stored as a
  core fact because no type can hold it — the same move as the trigger matcher never receiving the
  declaration's label.
- **R22's three default kinds are distinguishable in the resolution**, so a Ruling can say it
  defaulted *and* say which kind: `srd-prescribed`, `engine-chosen`, or `absent`. A type classified
  as having no default may not then supply one, and a declared default must satisfy its own type.
- **A namespace is what makes a type an extension** (R24), so the distinction costs no lookup and
  cannot drift out of step with a list. Extension values round-trip unchanged including unknown
  namespaces and absent or malformed versions — the engine has no basis for an opinion about a
  namespace it does not interpret. They must still be ledger-representable: not interpreted is not
  unconstrained.
- **`LedgerBackedPort` makes R25 structural.** A put that skipped the ledger would break the rebuild
  quietly — the store would hold a value the rebuild could not produce — so recording is not left to
  the implementer to remember.
- **The store is a projection, and the rebuild proves it.** A deleted store is recoverable from the
  ledger, replay applies writes in order so the latest wins, and **a rebuild discards anything the
  ledger does not account for** — a stray value that survived would be a fact with no recorded
  provenance, which is the shape of an outcome nothing ruled. A write whose `compat` floor the
  reader cannot meet refuses the rebuild rather than being skipped.
- Sixteen mutations proven caught. One needed a new test (the discard property above); one anchor
  missed on indentation and was re-run.

## Unreleased — 2026-08-22 — build `08222026.5`

U5 — mechanical state, the read surface, and the read token.

- **The state is immutable, and the generation cannot be forgotten.** Every successor is produced
  by one private `_evolve`, which adds one to the generation and *discards* a generation a caller
  tries to pass. A mutator has no way to skip the bump. That matters because the failure direction
  is quiet: a mutation that did not bump would leave a read token from before it looking current,
  and a stale claim would read `verified-fresh`.
- **R19 is settled structurally rather than by convention.** The read surface is handed a frozen
  state it could not modify if it tried, and the ability mapping is a `mappingproxy` so it cannot be
  written through either.
- **One legality derivation**, used to enumerate here and to validate in adjudication, so what is
  offered and what is accepted cannot drift.
- **The read token** carries the state generation and a digest of the offered set, derived and
  returned but never stored. Verdicts are `verified-fresh`, `verified-stale`, `unverified`, and
  `unread` — and *stale* and *unverified* are told apart, because one is an agent deciding from
  state that has moved and the other is an agent misreporting what it saw.
- **The token commits to structure, never prose.** Relabelling an alternative still verifies;
  altering its structured detail does not. Same discipline R6 imposes on the trigger matcher.
- **An unparseable or absent token yields `unread`**, not an error — `0011` already ruled that is
  the right verdict, and it is the expected one for a caller outside the turn loop.
- Eighteen mutations proven caught. Two needed new tests: `state.py`'s own arithmetic was uncovered
  by a test file aimed at the read surface, so damage clamping, healing clamping, turn wrapping,
  initiative ordering and its tie-break, and the ability modifier's rounding are now held directly.

## Unreleased — 2026-08-22 — build `08222026.4`

U4 — the ledger reader, which is the supported way to consume a ledger. The on-disk format is not
public API; this is, and `core` now re-exports it.

- **Three tiers, not two.** The envelope is fixed, so chain verification, sequence checking, and
  listing work across every payload version ever written and never need a known `v`. Interpreting a
  payload is separate: the reader compares its own version against the payload's `compat` floor. At
  or above it, interpret; below it, the entry is **unauditable** — reported and still listed, never
  silently skipped. `v` is deliberately never consulted, so a payload from a future schema is
  interpretable whenever its floor says an older reader can read it correctly.
- **Four corruptions named distinctly**, because the distinction is what tells an operator whether
  truncation would help: `torn-tail`, `checksum-mismatch`, `chain-break`, `sequence-gap` (plus
  `malformed-entry` and `missing-compat`). A malformed line in the *middle* is deliberately not a
  torn tail — truncation repairs one and not the other.
- **The chain compares against the true digest, not the recorded one.** That is what catches an
  edit whose checksum was recomputed: the entry is internally consistent and its successor still
  names the original digest. A stale-checksum edit therefore fires both findings, exactly as
  `0002`'s corruption table predicted.
- **Nothing is repaired on the way past**, and the reader never refuses to open a damaged file — a
  crashed session must stay reopenable. `repair_truncated_tail` is explicit, removes only the torn
  line, **refuses when the damage is anywhere else** (truncating past a deleted middle entry would
  discard sound records to hide it), and does not rewrite a file it has nothing to repair.
- A float smuggled in by hand is reported rather than crashed on — the reader must survive a file
  the writer would never have produced.
- Ten mutations proven caught. One needed a new test: repair would have silently rewritten an
  intact file, which byte equality is the only assertion that sees.

## Unreleased — 2026-08-22 — build `08222026.3`

U3 — the append-only ledger writer.

- **The fixed envelope**: `seq`, `type`, `v`, `prev`, `sum`, `payload`. `sum` is the digest of the
  entry with `sum` itself omitted, and `prev` is the predecessor's `sum` — so the chain catches the
  one corruption a checksum alone cannot, an edited value whose checksum was recomputed. The first
  entry's `prev` is **absent** rather than null: there is no predecessor to name.
- **The buffer/commit split makes "nothing escapes ahead of its record" structural.** Entries buffer;
  one synchronising write covers all of them at the escape boundary. An `escape_boundary()` context
  manager commits on the way out and **discards the buffer on the way out by exception** — nobody
  saw the outcome, so nothing was lost, and on restart the agent re-declares.
- **A session entry at `seq` 0** carrying the format, engine, and trigger-catalogue versions.
  Reopening under a *different* engine version appends a new session entry rather than continuing
  the old one, so every entry's governing engine version is the nearest preceding session entry.
- **A failed append raises `LedgerUnavailable`.** A caller can fix a missing fact by supplying it;
  it cannot fix a full disk by re-declaring.
- **Refused at write time**: a payload with no `compat` key, a `compat` floor above its own payload
  version (no reader of that version could interpret it, including the writer's own), a non-integer
  `compat`, an unknown entry type, and a float anywhere in a payload — the canonical form's refusal
  reaches through the writer, which is R25's no-float rule arriving where it matters.
- **A torn tail refuses the writer** and points at the reader's repair path rather than guessing.
- Eleven mutations proven caught. The first pass found a real hole: **nothing tested that `commit`
  actually calls `fsync`**, so the durability contract could have been deleted with the suite still
  green. Two tests now hold it — one synchronising write per commit regardless of entries buffered,
  and none at all for an empty buffer.

## Unreleased — 2026-08-22 — build `08222026.2`

U2 — the canonical form, and the refusal that makes the ledger's chain mean something.

- **`core.canonicalize` and `core.digest`.** RFC 8785 (JSON Canonicalization Scheme) restricted to
  exclude floating-point numbers: UTF-8, object keys sorted by **UTF-16 code unit**, no
  insignificant whitespace. Every digest goes through `digest()` rather than over bytes a caller
  assembled, so "the canonical form is the only input to any digest" holds by construction.
- **A float is refused anywhere in a value, and the error names where it is.** Excluding floats is
  what makes the restriction implementable without a dependency — JCS's hard requirement is
  ECMAScript number serialization — but the reason is correctness first: a coerced value is
  silently wrong in a record meant to be authoritative, and would first surface as a replay
  mismatch on a different machine.
- **Two subtleties the plan did not name.** Key ordering is by UTF-16 code unit, not code point,
  and the two disagree once a key leaves the BMP — `U+FF01` sorts before `U+10000` by code point
  and after it by UTF-16. And `bool` subclasses `int` in Python, so the boolean branch must be
  reached before the integer one or `True` serializes as `1`. Both are tested.
- **Integers outside the ECMAScript safe range are refused** as a judgment call the plan did not
  specify: beyond 2**53 a conformant reader parses the canonical bytes back as a *different*
  number, which is the same class of defect as a float.
- Four mutations proven caught: float rejection removed, the integer branch reached before the
  boolean one, keys sorted by code point, and the safe-integer bound removed.

## Unreleased — 2026-08-22 — build `08222026.1`

First code. M0 is closed, the plan is implementation-ready, and U1 is the vertical slice's
foundation.

- **Layer packages established**: `core`, `loop`, `memory`. `adapters` is not created — M1 has no
  adapters, and the rule below is written to cover it when it arrives.
- **The layer boundary is a guard test, not a convention.** Two rules over the import graph: nothing
  in `core` imports from an outer layer (R33), and nothing outside `core` imports a `core` submodule
  rather than what it re-exports (R34). R33's empty dependency list constrains what the *package*
  pulls in from outside, not how its own layers depend on each other — a core module importing an
  adapter that imports an LLM extra adds no third-party dependency at all, so the promise would die
  while the machine-readable form of it still read empty.
- **Relative imports are resolved before the rules apply.** `from ..loop import x` inside the core is
  the same violation as the absolute form, and a naive scan walks past it.
- **All four guards proven red against the real tree and restored** — core importing outward, an
  outer layer reaching into a core submodule, the relative form of the first, and the vacuous-scan
  check with a module removed.
- **A correction to `0011` and the plan.** Both say a deferred import inside a function body evades a
  static scan. It does not — `ast.walk` sees the whole tree. Only genuinely dynamic imports escape:
  `importlib`, `__import__`, and string-driven loaders. The guard's docstring states the narrower
  limit and the function-body case now has a test.

## Unreleased — 2026-08-22 (eighth)

Design only; no build stamp change, because nothing a consumer runs was altered. **This closes the
last design gate.**

- **Gate #13 settled**: four layer packages — `core`, `loop`, `memory`, `adapters` — with **two
  import rules enforced by a guard test**. Recorded in
  `docs/decisions/0011-module-layout-and-versioning.md`; R33, R34, and R35 amended.
- **The layout risk ran both ways, and the more dangerous direction was unnamed.** The issue named
  the turn loop reaching into core internals. The worse case is **the core importing outward**: R33's
  promise would die while `dependencies = []` continued to read empty, because an empty dependency
  list constrains what the *package* pulls in from outside, not how its own layers depend on each
  other. A core importing an adapter that imports an LLM extra adds no third-party dependency at
  all. Both directions are visible in the import graph and neither is visible in a dependency list.
- **The four engine-defined data schemas version independently as monotonic integers.** Not semver:
  a data schema's only question is "can I interpret this", and a change to the Ruling must not make
  a reader treat unchanged Declarations as unknown.
- **Every payload carries a reserved `compat` key** — the lowest reader version that can correctly
  interpret it. Most schema changes are additive, and under a bare version number every one of them
  would be unreadable to exactly the long-lived archives `0004`'s retrospective audit exists to
  read. Combined with `0006`'s always-readable envelope this gives three tiers rather than two:
  structurally readable, interpretable, and neither. `compat` is now the second permanently
  reserved name in the format.
- **Three kinds of versioned thing, named rather than unified.** A single scheme would not survive
  the read token (opaque and engine-internal — giving it a public version would publish an
  implementation detail) or extension namespace versions (consumer-declared and never compared, so
  a compare-and-dispatch mechanism has nothing to compare them to, and treating a malformed one as
  an error would make the engine police a namespace it explicitly does not interpret).
- **The build stamp makes no compatibility claim**, stated plainly rather than left implied, and
  the public code API is explicitly unstable until v1.0. A stability policy is a v1.0 release
  requirement, filed as #39 rather than left in prose — writing one before any API exists would be
  writing it blind, and the failure this repo has seen before is the deferral that never becomes an
  issue.
- **Holding this gate until last paid twice.** Layout genuinely depended on what modules turned out
  to exist — and the versioning half arrived with **seven** items rather than R35's original three,
  five contributed by gates settled in the interim, two of which do not fit the obvious mechanism.
  Settled first, it would have produced a uniform scheme that the read token and the extension
  namespace would each have had to be bent to fit.
- `CONCEPTS.md` gains **Layer** and **Compat floor**.

## Unreleased — 2026-08-22 (seventh)

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #33 settled**: **a block is a suspension, not a refusal.** The declaration was accepted —
  it passed R3 and the trigger check — and stalled only at fact resolution, so supplying the facts
  resumes *that* declaration rather than requiring a new one, and `0005`'s declaration budget is
  not charged. That budget counts refusals, and its terminal reasons all name agent behaviour.
  Recorded in `docs/decisions/0010-blocked-loop.md`; R22 and R30 amended.
- **The loop needs no count bound, because it bounds itself.** R21 makes a rule's fact
  dependencies a *static* declaration, so the unresolved set can only shrink — the loop terminates
  in at most as many rounds as the rule declares facts. Only a round that fails to shrink the set
  ends the turn, as `fact-unavailable`.
- **A count bound would have been worse than nothing.** It could do exactly one thing: cut off a
  sequence that was progressing — which in a human-driven session is a person supplying facts one
  at a time and thinking in between. And a safeguard that essentially never fires is untested code
  guarding a case that cannot occur. Distinguished in the record from `0007`'s deliberately-kept
  `verified-stale`: **a signal that never fires tells you something is healthy; a safeguard that
  never fires is dead machinery.**
- **`blocked` names every unresolved fact at once**, with each type's R22 classification — one
  round trip rather than N. Same shape as `0004`'s rule for challenges. It also makes the
  shrinking-set invariant observable, and catches the case a count bound is usually reached for: a
  driver writing the *wrong* facts makes no progress by definition.
- **Blocking is usually correct behaviour** — the engine refusing to invent and asking. What is
  defective is a fact type that blocks session after session, which means its `absent`
  classification is a design-time claim being tested and failing. Treated as a data-model defect,
  the analogue of `0004`'s over-broad trigger row, and surfaced by the ledger reader's
  cross-session audit rather than a single session's report.
- **The engine never invents a default at the terminal.** R22 blocking *means* no default is
  honest, so supplying one would be worse than `0005`'s rejected bypass rather than equivalent to
  it.
- **Drivers acquire an obligation**: a driver must not return from a blocked-fact request without
  either supplying facts or intending to stop, since a bare return is indistinguishable from no
  progress. Easy to get wrong in a polling driver, so it belongs in the driver documentation.
- `CONCEPTS.md` gains **Block**. The exhaustion entry type gains a second terminal reason with no
  envelope change — `0006`'s payload split working as intended.

## Unreleased — 2026-08-22 (sixth)

Design only; no build stamp change, because nothing a consumer runs was altered. Two sibling gates
settled together.

- **Gate #9 settled**: extension fact types are **reverse-DNS namespaces**
  (`com.example.tool.mood`), the core set is **unnamespaced** so carrying a namespace is what makes
  a type an extension, and **no engine rule may consume an extension fact** — a rule declaring one
  is a load-time error. Extensions keep typing, provenance, and ledger integration; what they do
  not get is a resolver, so they cannot move an outcome and R31 stays intact by construction.
  Recorded in `docs/decisions/0008-extension-channel.md`; R21, R22, and R24 amended.
- **One answer dissolved most of that gate.** The issue posed four open questions and listed rule
  access third, phrased as a clarification. It was the hinge: under "never", R22's default
  classification never fires for extensions and the engine can be version-agnostic about
  namespaces because it interprets none. Working the questions in the order given would have meant
  designing a default classification and a version-negotiation scheme that turn out not to be
  needed.
- **A registry was disqualified by the constraint that named the problem.** "Collision between two
  independent consumers must be impossible without coordination" — and a registered short prefix
  *is* coordination, wherever the registry lives.
- **Gate #12 settled**: the reference memory store is **flat JSON, one file per campaign**, on a
  substrate separate from the ledger so the port stays swappable. Recorded in
  `docs/decisions/0009-reference-memory-store.md`; R23 and R25 amended.
- **Deciding what the store *is* settled what it should be made of.** R25 already requires every
  fact write to append to the ledger with provenance, so the ledger is the system of record and
  the store holds current values only — a **projection**, rebuildable by replay. That removes both
  of SQLite's advantages at once rather than weighing them: durability protects a system of
  record, and indexed reads matter at a scale solo play does not reach.
- **This reaches the opposite conclusion to `0006` on a similar-looking question**, for a reason
  that does not transfer: 0006 rejected SQLite partly because append-only would be discipline over
  a mutable B-tree, and the memory store is *mutable by nature*. It is rejected here on scale and
  inspectability instead.
- **"Sufficient to run a solo campaign" is now five testable properties**, of which the
  load-bearing one is that the store rebuilds from the ledger to an identical state — the
  executable form of the projection claim.
- **`0006`'s no-float rule reaches through the port**: because a fact write appends to the ledger,
  no fact value may be a binary float.
- `CONCEPTS.md` gains **Extension fact type** and **Memory store projection**.

## Unreleased — 2026-08-22 (fifth)

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #8 settled**: a **read token** makes the alternatives claim checkable without relaxing
  R19. The read surface returns the legal set plus an opaque token encoding the state generation
  it was derived from and a digest of the set; the declaration echoes it, and the engine reports
  `verified-fresh`, `verified-stale`, `unverified`, or `unread`. The read surface still computes
  and returns without mutating or appending — R19 is unchanged, which was the point. Recorded in
  `docs/decisions/0007-alternatives-verification.md`; R5, R10, R18, R19, and R30 amended.
- **The mismatch ambiguity turned out to be an artefact of recording too little.** The issue set
  re-derivation aside because state may move between the read and the declaration, making a
  mismatch ambiguous between drift and falsehood. Recording the **state generation** the set was
  derived from splits it cleanly: same generation with a different set is a false claim; an older
  generation is an agent deciding from stale information. Adding one counter to state reopened two
  options that had looked closed.
- **A stale read should be impossible here, which is exactly why it is worth detecting.** Solo
  play, one character, a sequential loop — nothing can move state between a read and the
  declaration that follows it. The realistic cause is an agent **caching a read across turns**,
  plausible LLM behaviour and otherwise entirely invisible.
- **No MAC.** 0002's "not defending against its own owner" does *not* extend to the agent, whose
  unreliability is the premise of the design — but the agent is an LLM, not an adversary with a
  debugger. A garbled or invented token fails the digest; a replayed genuine one fails the
  generation check. Only computing a valid digest for a fabricated set is uncovered, and that is
  cryptographic work from a text generator. The digest `0006` already requires covers the rest.
- **One derivation of what is legal**, shared by the read surface and the adjudicator, so what is
  offered and what is accepted cannot drift — an independent cross-check was rejected in favour of
  making the drift impossible, the fourth time this project has taken that trade. The accepted
  cost is named: a bug *inside* the shared derivation is invisible to this mechanism.
- **A failed verification is recorded, not rejected.** The alternatives are metadata about a
  decision, not the decision, and R3 validates the named test independently. Rejecting would
  repeat the category error `0002` identified with `blocked`, and under `0005` would burn a retry
  slot on something no resubmission by a buggy agent fixes.
- **`unread` is the expected verdict for a caller outside the turn loop**, making the already-known
  limit — a direct caller gets outcome authority without the skip guarantee — visible per ruling
  rather than only in prose.
- `CONCEPTS.md` gains **Read token** and **Alternatives verdict**. `0006`'s envelope/payload split
  gets its first exercise: declaration entries gain three fields with no envelope change.

## Unreleased — 2026-08-22 (fourth)

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #10 settled**: the ledger is **JSONL behind a reader API**, and its on-disk format is
  explicitly **not** public API. R35 already commits the entry schemas, so the open question was
  only whether the *envelope* was public — and publishing later is cheap where unpublishing is
  not. A shipped reader gives consumers something stable to depend on, which is the only version
  of that promise that survives contact with users; export becomes a function of the reader
  rather than a second near-duplicate format. Recorded in `docs/decisions/0006-ledger-format.md`;
  R26, R28, R30, and R35 amended.
- **0002's hash chain was not implementable as written.** It required "a checksum of its own body"
  without saying how bytes are derived from an entry, and JSON has no canonical form — key order,
  whitespace, escaping, and number formatting all vary by serializer. Two writers disagreeing
  would produce a chain that fails to verify on a sound file, reported as *tamper detected*. The
  canonical form is now RFC 8785, restricted.
- **No binary floating-point value may appear in a ledger entry.** This is what makes
  canonicalization implementable without a dependency, since JCS's hard part is ECMAScript number
  serialization — and the domain turns out to need no floats at all. Dice, damage, DCs, AC, hit
  points, modifiers, slot levels, and distances in feet are integers; the SRD's fractional
  quantities (challenge ratings of 1/8, 1/4, 1/2, and item weights) become exact strings or
  integer subunits. Primarily a correctness decision: `0.1 + 0.2` is `0.30000000000000004`, and a
  record meant to be authoritative should not hold values that are approximately what they say.
- **The envelope is fixed for good; only the payload is versioned.** `seq`, `type`, `v`, `prev`,
  `sum`, `payload`. Integrity checking, sequence checking, and listing therefore work across every
  version ever written, and the retrospective audit reports payloads it cannot read as
  **unauditable** rather than skipping them silently.
- **#7's version-pinning fix was partial — the rules code is an input too.** A bug fix in a rule
  makes every prior entry that exercised it replay differently, reported as inconsistency. The
  engine version is now recorded on a `session` entry, a session may not span engine versions, and
  cross-version replay yields a **reconciliation** result naming both versions and both outcomes —
  never an integrity verdict, because a rules fix is not corruption.
- **A torn tail is reported, never silently truncated and never fatal.** 0002 guarantees nothing
  escaped, so discarding the fragment is safe — but only once a human has been told, and a crashed
  session must stay reopenable.
- `CONCEPTS.md` gains **Ledger reader** and an expanded **Ledger**. Schema-versioning *mechanics*
  stay #13's, and should cover the ledger payload alongside the R35 schemas rather than growing a
  second scheme.

## Unreleased — 2026-08-22 (later still)

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #11 settled**: the retry bound belongs to the **turn loop**, not the adjudication core.
  The core answers one declaration and has no memory of having answered before; counting attempts
  is session state, and a bound in the core would be a half-measure anyway since a direct caller
  gets no skip guarantee. One budget per declaration slot covering challenges and rejections
  together, defaulting to **3 refusals**, configurable, with `None` meaning unbounded — the
  human-CLI driver is expected to use it, because a person burns no model calls. Recorded in
  `docs/decisions/0005-retry-bounds.md`; R8 and R30 amended, F3 filled in.
- **An engine-selected default was rejected as a bypass.** Letting the engine pick a legal test on
  exhaustion would let an agent reach an adjudicated outcome *by failing* — a second path beside
  the declaration it is accountable for — and would leave R10 nothing to review, since recording
  the offered alternatives exists so a legal-but-wrong classification can be checked after the
  fact. The terminal outcome instead **discloses** the alternatives that were offered without
  choosing among them.
- **Two of the issue's three candidates turned out to be one.** "Surface a terminal status to the
  human" and "abort the turn" are the same engine behaviour under two different drivers, per
  `docs/decisions/0001-agent-seam.md`. The issue's option list had framed a driver policy as an
  engine decision.
- **Exhaustion is not a rules status.** No rule says a badly-declared action has a result, so it
  sits beside a failed ledger append rather than beside `challenged` and `rejected` — the same
  distinction `0002` drew for infrastructure failure. It appends its own ledger entry and carries
  a reason: `no-progress`, `challenge-churn`, `rejection-churn`, or `mixed-churn`.
- **Two structurally identical refusals terminate at once**, ahead of the general bound. Identity
  is the trigger id set or the reason code and citation — **never the message text**, since
  templated messages can differ while naming the same refusal, and the engine should no more read
  its own prose than the agent's. Under `0004` a repeating trigger set usually means an over-broad
  catalogue row, so `no-progress` is often the engine's fault and is an `srd-fidelity` triage
  input.
- **R30 must not count an exhausted slot as a narration gap.** It produced no Ruling, so without
  an explicit exclusion every exhaustion would surface as "a Ruling with no narration" and make
  the report's most important signal noisy.
- `CONCEPTS.md` gains **Declaration slot** and **Retry exhaustion**.
- #33 filed for the `blocked` loop, which R22 also invites and this bound deliberately excludes —
  a driver failing to supply a fact is a different actor failing than an agent misjudging a rule,
  and charging it to the agent's budget would misattribute it.

## Unreleased — 2026-08-22 (later)

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #7 settled**: the trigger catalogue is **data, not code**. A trigger is a declarative row
  over a closed operator set, and the matcher is handed a projection of the declaration that
  *excludes* its free-text label — so R6's prohibition holds by construction rather than by review.
  Rows are conjunctions; a disjunction is separate rows, so each alternative stays separately
  citable and separately narrowable. Grounding is two-valued (`cited` / `authored`), because a tier
  assigned by judgment at intake stops carrying information. Recorded in
  `docs/decisions/0004-trigger-catalogue.md`; R6 and R30 amended.
- **Over-firing is reclassified as an `srd-fidelity` defect, equal in severity to a missed skip.**
  A wrongly-fired trigger makes the agent resubmit naming a test, so the engine rolls for
  something the SRD never called for — a ruling with no rule behind it, which is the project's
  defining defect with the sign flipped. Nothing downstream of the challenge can tell the first
  step was wrong.
- **A growing catalogue would have silently invalidated every past session.** The catalogue is an
  adjudication input, so it is versioned, the version is recorded on the declaration's ledger
  entry, and R28 replay uses the recorded version rather than the current one. #10 gains that
  field.
- **Catalogue growth is now the recall instrument.** A retrospective audit re-runs closed ledgers
  against the *current* catalogue and names every declaration today's rules would have challenged.
  A missed skip leaves no trace at the time, but it leaves a declaration — so each new row makes
  the whole history newly measurable. Distinct from replay, and deliberately so.
- **Admission is evidence-first in both directions**, extending "prove a guard fails before
  trusting it" to the one guard whose failures are invisible: a miss must be shown *not* to
  challenge before a row is written, and a false positive is narrowed by adding a condition rather
  than deleted. `.github/ISSUE_TEMPLATE/trigger-miss.yml` now requires the fixture and notes the
  `srd-fidelity` triage.
- Improvised intents are matched on situational state alone — disclosed as reduced coverage rather
  than closed, since the two ways to close it either hand classification back to the agent or
  over-fire by default. The retrospective audit is its delayed detection path.
- `CONCEPTS.md` gains **Retrospective audit** and **Over-fire**, and the trigger-catalogue entry
  gains the settled form.

## Unreleased — 2026-08-22

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #6 settled, against the plan's assumption.** No community dataset seeds the mechanics.
  The plan had assumed a machine-readable SRD 5.2 dataset existed and was the intended seed; five
  candidates were evaluated and none is usable for the mechanics v1 needs. Mechanics are modelled
  by hand from the official SRD v5.2.1, verification state lives alongside each entry
  (`unverified` / `verified` / `excluded`, with reference section, date, and a reason on an
  exclusion), and only `verified` entries reach the engine. Recorded in
  `docs/decisions/0003-seed-and-verification.md`; R31 amended, and the plan's sourcing decision,
  dataset assumption, and deferred question updated to match.
- **The verification reference is SRD v5.2.1, not "SRD 5.2".** WotC published v5.2.0 on
  22 April 2025 and v5.2.1 on 1 May 2025; the later document restores fifteen omitted magic items
  and replaces a duplicated Iron Golem stat block with the Knight. A seed built against the
  earlier one carries a wrong monster presented as a right one. Bringing the rest of the
  repository's prose into line is #30; `NOTICE.md` is left to #3, whose transcription must now
  target the specific revision.
- **The errata became a test.** Probing a candidate for the Knight, the Octopus, a duplicated
  Iron Golem, and three of the restored magic items identifies which document it transcribed
  regardless of what it claims. Open5e — the only structured candidate — turns out to carry
  5.2.1 creatures and pre-5.2.1 items under one version label and a publication date belonging to
  neither. Its `srd-2024` document also has no Rules Glossary at all, so it supplies none of the
  fifteen conditions M1 needs.
- Findings recorded on #21 (content population) and #3 (attribution) so neither re-runs the
  research.

## Unreleased — 2026-08-21

Design only; no build stamp change, because nothing a consumer runs was altered.

- **Gate #4 settled**: the agent seam is a generator of typed requests, with an object-shaped
  adapter for the common case and two non-LLM reference drivers (scripted, human CLI). Recorded
  in `docs/decisions/0001-agent-seam.md`; R8 amended and the plan's Key Decisions updated.
- **Gate #5 settled**: a Ruling, challenge, or rejection is not returned until its ledger entry is
  durable — one synchronising write per adjudication, at the escape boundary rather than at the
  roll. Entries are hash-chained; a failed append raises rather than returning a rules status.
  Recorded in `docs/decisions/0002-ledger-durability.md`; R26 and R30 amended. #10 inherits three
  format constraints, recorded on that issue.
- `docs/decisions/README.md` explains the convention — why the records exist, that a gate closes
  by producing one, that they are numbered and superseded rather than edited, and the section
  format. Someone browsing the directory previously had to infer all of it. Removed two empty
  scaffold directories that were never used and a reference to a learnings store that does not
  exist yet.
- Corrected the documented local gate, which listed three of the four checks CI runs. `ruff format`
  also formats fenced Python in Markdown, so documentation with code samples is subject to it.
- `docs/decisions/` established as the store for settled design decisions, so a closed gate leaves
  behind what was chosen, what was rejected, and the evidence — rather than only an issue nobody
  will reread.

## 08212026.2 — 2026-08-21

Keep local-machine details out of a public repository.

- `tests/test_no_local_leakage.py` scans every tracked text file and fails CI on an absolute or
  home-relative filesystem path, a private project-collection name, a credential shape (GitHub,
  AWS, OpenAI, Anthropic, bearer headers), or a private contact address. Proven red against eight
  planted leaks across all four categories, with a green control — and it refuses to pass
  vacuously if the file scan ever returns nothing.
- Scrubbed what was already public: a home-relative working path in the README's resume prompt,
  the local taxonomy line, and four references to the private project collection this repo is
  maintained from (`AGENTS.md` ×2, the plan ×2). The sibling project they cited is public, so
  they now cite it by URL, which is strictly more useful to a reader anyway.
- Local-only metadata moved to a gitignored `GARAGE.md`, so it has somewhere to live rather than
  drifting back into tracked prose.
- Commits are now authored with a GitHub noreply address instead of a mail relay.
- Standing rule added to `AGENTS.md`: describe the project, not the machine it is built on.

## 08212026.1 — 2026-08-21

Repository established. Scaffolding, governance, and CI only — no engine code.

- Repository initialised from the requirements-only plan produced 2026-08-19.
- MIT for the engine's own code; SRD 5.2 material remains CC BY 4.0 with the attribution
  wording gated until it's verified against the published document (`NOTICE.md`). **No
  SRD-derived content has been committed.**
- `AGENTS.md` (linked as `CLAUDE.md`): the architectural invariant, the issues-are-the-queue
  rule, standing rules, and the non-goals.
- `CONCEPTS.md`: shared vocabulary, each term traced to its requirement.
- Two guard tests that make promises mechanical rather than remembered — the README build stamp
  matching the package version, and R33's empty core dependency list.
- CI across Python 3.11–3.13 running `pytest`, `ruff`, and `mypy --strict`.
- The plan's ten outstanding questions, its attribution dependency, and its four deferred scope
  items filed as issues, per the rule that a plan's deferrals are filed before they can be
  forgotten. Each is annotated with its issue number in the plan itself.
- Six coverage epics filed against v1.0, one per SRD subsystem, plus the effect-shape inventory
  (#14) that makes "full coverage" falsifiable at all — filed against M0 instead, because the
  other six are unscoreable until it exists.
