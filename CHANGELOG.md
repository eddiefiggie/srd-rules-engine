# Changelog

Builds are stamped `mmddyyyy.x` — the date they were produced, plus that day's iteration. The
stamp lives in `src/srd_rules_engine/__init__.py`; `tests/test_build_stamp.py` fails CI when
README.md's `**Current build:**` line drifts from it.

Nothing is released yet. Entries below record builds, not releases.

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
