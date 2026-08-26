# Agent Instructions

SRD 5.2 Rules Engine — an open-source Python library implementing D&D SRD 5.2 (2024) mechanics,
where an LLM agent holds interpretation and the code holds **outcome authority**. Solo play, one
player character. The core is a plain typed library; MCP, HTTP, and CLI are adapters.

See `README.md` for what it does, `NOTICE.md` for the two-licence situation, and
`docs/plans/` for the requirements artifact behind each milestone.

**[`docs/decisions/`](docs/decisions/) holds settled design decisions.** Read the relevant record before reopening a
question in the area it covers — each one states what was chosen, what was rejected, and the
evidence, so a decision does not get re-litigated from scratch by whoever arrives next. A gate
issue closes by producing one of these, and the plan is amended to match.

## The invariant everything else serves

**The agent decides *that* a rule applies and *which* one. It can never decide *how it turns
out*.**

Every architectural rule below is downstream of that sentence. When a design question is
genuinely ambiguous, the resolution is whichever option makes inventing an outcome *impossible*
rather than *discouraged*. That distinction is the whole product — a tool the model may call is
a tool a model that doesn't realise a check is warranted will not call.

Concretely, these are not negotiable without re-opening the Product Contract:

- **One adjudication entry point.** No other API produces, modifies, or implies a result (R1).
- **The engine rolls.** No caller ever supplies a roll or a result (R4).
- **The core takes no LLM dependency and no network dependency** (R33). Guarded by
  `tests/test_core_has_no_runtime_dependencies.py` — an empty `[project].dependencies` is the
  machine-readable form of the promise. Adapters declare extras instead.
- **Read-surface calls never mutate and never append to the ledger** (R19).
- **The memory port returns typed values only, never prose** (R20). The moment the engine reads
  prose, it is interpreting narrative again, which is the capability being removed.

## Open work lives in GitHub Issues

**GitHub Issues is the single source of truth for open work** — bugs, feature requests,
code-review findings, and work a plan deferred. If it is not an issue, it is not tracked,
however carefully it is written down elsewhere.

**A plan's deferrals must be filed before its PR merges.** When a plan writes a "Deferred to
follow-up work", "Scope Boundaries", or "Outstanding Questions" entry describing work someone
should eventually do, open the issue and put its number next to the prose. Do not rely on the
plan being re-read — prose in a plan is not a queue, and nobody greps the plans folder before
choosing what to work on.

This rule is inherited deliberately. In a sibling project it was broken 44 times before an audit
caught it, including four whole subsystems re-deferred across as many as nine separate plans
without ever being filed.

**A decision record's unbuilt clauses must be filed too, and a gate closing is when to do it.**
A `gate` issue closes by producing a record, so the moment the design is written down the issue
that held it disappears. Any clause the record specifies and nobody has built is then tracked by
nothing — and worse than merely unfiled, because a *closed* issue reads as finished work rather
than as absent work. Open the issue and put its number beside the clause in the record's **Status
of implementation** section. The same two exceptions apply.

`tests/test_decision_records.py` asserts every record carries that section. It checks presence,
not truth: a section can be stale and stay green, which is how twelve records came to claim
nothing was built over an engine that had shipped
([#127](https://github.com/eddiefiggie/srd-rules-engine/issues/127)). Updating it when the work lands is the
author's job, and the issue number is what makes the claim checkable by someone who was not
there.

Two exceptions, both meaning **do not file**:

- **A note recorded specifically so a later audit does not re-raise it.** Filing it re-raises
  exactly what the note prevents.
- **A non-goal.** See below.

**A PR that resolves an issue closes it with a keyword — `Closes #N`, not a bare `#N`.** GitHub
only auto-closes on `Closes` / `Fixes` / `Resolves`. A bare `#N` links the issue and leaves it
open, so closing then depends on somebody remembering days later. That dependency has already
failed in a sibling project of mine: a single sweep found five issues fixed, shipped, and still open.

**An issue resolved as already-correct still gets closed, with the evidence.** Some
investigations end in "no code change." That is a result, not the absence of one — record it and
close, or the issue reads as untouched forever.

**Label meanings.** `gate` blocks implementation until settled — a design question with no
default answer. `backlog` is self-deferred work postponed by a plan, not user-reported.
`srd-fidelity` means a rule may be modelled wrongly, which outranks everything except a crash.

## Standing rules

**Never infer a rule value.** Every mechanic traces to the official SRD v5.2.1 document. If
the SRD does not state it outright, it is excluded and the exclusion disclosed rather than
guessed (R31, R32). A
visible gap beats a confident wrong number, because a wrong number is indistinguishable from a
right one once it's inside a finished ruling. Widely-known 5e behaviour that isn't in the SRD is
still a guess, and Product Identity outside the SRD must not enter this repository at all.

**Seeded is not verified.** A community dataset is a seed, never a source. Each entry carries its
own verification state against the official document, and unverified entries do not reach the
engine. The closest prior art I have — [`ddo-loadout-optimizer`](https://github.com/eddiefiggie/ddo-loadout-optimizer)
— found that rules fidelity lives or dies on data provenance rather than on the solver.

**Prove a guard fails before trusting it.** Corrupt the input a new gate exists to reject and
confirm it goes red. A guard that has never been seen red is a guard that might be inspecting
nothing — and coverage of one data source is not coverage of another. Run it through
`scripts/prove_guard_red.sh <target-file> <sed-expression> <pytest-arg>...`, which snapshots the
file, corrupts it, runs the guard, and restores from the snapshot on every exit path — success,
failure, interrupt, or **hang**. A hang is an ordinary result rather than a freak one: corrupting
a discharge, a counter or a loop bound is a normal way to prove a guard, and each can turn a
terminating suite into a non-terminating one. That case left the corruption in the tree until
[#175](https://github.com/eddiefiggie/srd-rules-engine/issues/175), because bash defers a trap
until the foreground command returns. The run is now backgrounded and watched; it exits `124`
after `PROOF_TIMEOUT` seconds (default 120) and says a timeout is **not** a proof — a run that
never terminates shows the corruption broke something, not that your assertion fires. **Never restore with `git checkout -- <file>`.** Corruption proofs are run mid-change,
so the tree always has uncommitted work and usually untracked new files, and `git checkout` is
wrong in both states: on a file carrying an uncommitted edit it reverts the whole file and
silently discards the very code the guard protects, and on an untracked file it fails outright and
leaves the corruption in the tree. Both happened while building #153, and the second is the shape
this repository cares most about — the corruption a guard test uses is by construction the wrong
value that looks right ([#155](https://github.com/eddiefiggie/srd-rules-engine/issues/155)).

**Prove a new test fails against the pre-change tree.** A fully green suite can cover none of the
diff. Run `scripts/prove_against_base.sh <base-ref> <test-path>...`; anything still passing is
covering nothing. Deliberate "nothing changed" guards are the exception. **Do not do this by hand
from memory.** The venv carries an editable install — a `.pth` in `site-packages` pointing at the
working tree's `src` — so `pytest` run inside an exported base tree imports the *working tree*.
The new code is already there, the new tests pass, and the run reports success for the wrong
reason. That produced a false green three times
([#123](https://github.com/eddiefiggie/srd-rules-engine/issues/123),
[#136](https://github.com/eddiefiggie/srd-rules-engine/issues/136),
[#153](https://github.com/eddiefiggie/srd-rules-engine/issues/153)) before the procedure was
fixed here ([#154](https://github.com/eddiefiggie/srd-rules-engine/issues/154)). Two steps defeat
it and the script does both: `PYTHONPATH=<export>/src`, and asserting `srd_rules_engine.__file__`
resolves *inside* the export before trusting the run. The second is the one that matters — it is
the only step that can tell a real red from a false green, so the script aborts rather than
reporting when it fails.

**Bump the build stamp and the README together, on every pull request.** Not "every build" —
that wording left it open whether a docs-only or test-only change ships one, and the repository
answered in practice long before it said so: the last PR to merge without a bump was
[#122](https://github.com/eddiefiggie/srd-rules-engine/pull/122) on 2026-08-24, and the 44 since
have all bumped, records and test-only changes included.
`src/srd_rules_engine/__init__.py` carries `__version__` in `mmddyyyy.x` form (see the
`build-versioning` skill). README.md's `**Current build:**` line and its `_Last updated:_` footer
must both match it, and the prose must say what actually shipped.

Two guards, because they catch different things
([#147](https://github.com/eddiefiggie/srd-rules-engine/issues/147)):

- `tests/test_build_stamp.py` fails on **drift** — the three stamps disagreeing. It is blind to
  the pair standing still *together*, which is how build `08232026.39` came to cover two merged
  pull requests.
- The **Build stamp advanced** CI job runs `scripts/check_build_stamp_advanced.py` and fails when
  `__version__` is not strictly later than the one at the **tip of the base branch**. The tip,
  not the merge base: two branches cut from the same commit can each advance past their shared
  base and still land on the same stamp, which happened on 2026-08-25 with #208 and #210 and is
  why the merge-base version of this check was rejected. If `main` moves under you, rebase and
  re-stamp — a bump has to be *free at merge time*, not merely later than where you started.

Neither guard checks that the prose is honest. That part is on you.

**That line is the build record; there is no changelog.** `CHANGELOG.md` is retired and frozen at
build `08232026.36` — it duplicated the README line, went fifteen PRs without an entry, and nothing
guarded it ([0024](docs/decisions/0024-the-build-line-is-the-build-record.md),
[#146](https://github.com/eddiefiggie/srd-rules-engine/issues/146)). Do not append to it, and do
not write a promise that some change will be written down there — including for
[0018](docs/decisions/0018-api-stability.md)'s Provisional surfaces, whose changes are recorded in
the build line. `tests/test_changelog_is_retired.py` refuses one, by matching the phrasings that
existed before the retirement.

**Nothing about the local machine reaches this repository.** No absolute or home-relative
filesystem paths, no private project-collection names, no personal contact addresses, and
obviously no credentials. This is a public repo maintained from a private working tree, and the
confusion is easy to make in *prose* rather than in code — a path that reads naturally in a local
note becomes a disclosure once pushed. Describe the project, not the machine; if a path is
genuinely needed, make it relative to the repository root. `tests/test_no_local_leakage.py`
scans every tracked text file and fails CI on a hit. Local-only metadata belongs in the
gitignored `GARAGE.md`.

**Narration bounds are advisory to the caller** (R7). The engine states what may and may not be
asserted; it does not enforce it. Do not add enforcement machinery that implies otherwise, and do
not describe bounds as enforced in user-facing prose.

**The skip guarantee holds only for callers the turn loop drives.** A consumer calling
adjudication directly gets outcome authority without skip prevention. That limit ships disclosed,
never quietly.

**The trigger catalogue is known-incomplete.** The SRD supplies explicit triggers only for forced
saves, attacks, and stated hazards; everything else is project-authored and *grounded in* rather
than *cited from* the SRD. Catalogue recall is unmeasurable from play alone, because a missed skip
leaves no trace. Disclose the scope the same way excluded mechanics are disclosed.

## Non-goals

Considered and deliberately declined. These are **not** backlog, and filing them as issues
misrepresents them as unfinished work. If a request maps onto one, the answer is a pointer here,
not a new issue.

- **Multiplayer, shared sessions, and any multi-user surface.** The product is solo, one player
  character. No concurrency, turn arbitration, or shared-session state is assumed anywhere in the
  design, and adding it later is a redesign rather than a feature.
- **Any user interface.** The deliverable is a library plus adapters.
- **Narrative or content generation.** The engine adjudicates; it does not author.
- **Coupling to a specific LLM or agent framework.** The engine serves any agent, or none.
- **Grid-based tactical movement as the default.** Movement resolves in feet, with the grid as
  the optional variant the SRD publishes it as.
- **Enforcing narration bounds.** They are advisory by design (R7). Enforcement would require the
  engine to read prose.

## Working agreement

- Branch off `main`; `main` is protected and takes changes through pull requests.
- Conventional-commit subjects (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`), with
  the issue number in the body or subject and a closing keyword when it resolves one.
- The full gate is `pytest && ruff check . && ruff format --check . && mypy`. CI runs exactly
  that on every PR across 3.11–3.13. Run all four — a subset passing locally and CI failing on
  the one you skipped has already happened. Note `ruff format` also formats fenced Python in
  Markdown, so documentation with code samples is subject to it too.
- Requirements traceability is load-bearing: when code implements a numbered requirement, name it
  (`R14`) in the docstring or the PR body. Full coverage is the definition of done for v1, and an
  untraceable implementation can't be counted toward it.
