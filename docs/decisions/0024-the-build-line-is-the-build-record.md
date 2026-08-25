# 0024 — the README's build line is the build record, and `CHANGELOG.md` is retired

- **Status:** Accepted, 2026-08-24
- **Settles:** [#146](https://github.com/eddiefiggie/srd-rules-engine/issues/146)
- **Requirements:** none · touches R35 through [0018](0018-api-stability.md)'s Provisional tier
- **Amends:** [0018 — API stability](0018-api-stability.md), the Provisional tier's *venue*. The
  tier itself is unchanged: a provisional change is still recorded rather than versioned, and
  still raises nothing. What changes is where the record lives.
- **Related:** [0011 — module layout and versioning](0011-module-layout-and-versioning.md), which
  gives the data schemas their own monotonic versions and is untouched by this

## Context

`CHANGELOG.md` stopped being maintained after #115 and nobody noticed for fifteen merged PRs and
fourteen builds — including both new transports, the CLI (#136) and HTTP (#137) adapters. #146
found the reason it could go that long unnoticed: the only statement of the rule anywhere was an
unenforced checkbox in the pull-request template. Its two neighbours in that same checklist are
CI-enforced, so an unticked box for either goes red. This one went green fifteen times.

The file was also a duplicate. README's `**Current build:**` line already carries per-build prose —
what shipped, why, and how it was proven — and `tests/test_build_stamp.py` guards it at both of its
stamps. `CHANGELOG.md` was 148 KB across 65 entries saying the same things at greater length, one
merge behind.

Two things depended on the file existing, which is why this needed a decision rather than a
deletion:

1. **[0018](0018-api-stability.md)'s Provisional tier.** "A change is recorded in the changelog and
   raises nothing" is a promise to a consumer building on the MCP tool names, the CLI commands or
   the HTTP routes. Retiring the venue silently would leave the promise pointing at a dead file.
2. **The plan's M1 acceptance criteria**, which list `CHANGELOG.md` recording what shipped beside
   the build stamp and README line.

## Options considered

**Backfill and resume, with a guard** — a test asserting the newest `## ` heading names
`__version__`, exactly as `test_build_stamp.py` does for the README. Rejected: it means writing
fourteen builds of history from diffs, and reconstructed prose is worth less than the README lines
it would be reconstructed *from*. It also keeps the duplication permanently, at one entry per build.

**Guard without backfilling** — the same test, with the fourteen missing builds left missing and a
note saying so. Rejected for the same duplication reason, though it is the honest version of the
option above.

**Keep it for releases only.** Nothing is released yet, and the file's own header said entries
record builds rather than releases. Rejected as premature: it defers the question to a first
release that does not exist, and until then the file stays exactly as dead as it is now with a
reason attached.

**Retire it.** Chosen.

## Decision

1. **`CHANGELOG.md` is frozen, not deleted.** Its 65 entries are real history and stay readable.
   The file carries a header saying it is retired, at which build it stops, and where the record
   moved. Nothing is appended to it again.
2. **README's `**Current build:**` line is the build record.** It already is in practice, and it is
   the one a reader meets first. `git log` carries the rest.
3. **[0018](0018-api-stability.md)'s Provisional tier records a change in that line** instead of in
   the changelog. The tier is otherwise unchanged.
4. **The pull-request checklist loses the changelog box.** A checklist item with no guard behind it
   is a checklist item that will be ticked or ignored according to how the day is going.
5. **`tests/test_changelog_is_retired.py` refuses a live obligation pointing at the retired file**
   anywhere an obligation could live: `src/`, `.github/`, `docs/plans/`, `AGENTS.md`,
   `CONTRIBUTING.md`. `docs/decisions/` is exempt because records are immutable, and the file
   itself is exempt because it describes its own retirement.

## Why

**The duplication is what killed it, not the diligence.** Fifteen PRs of silence is not fifteen
lapses of attention; it is the file having no reader. Every one of those PRs *did* write the
per-build prose — into the README line, where the guard is. A second copy that no test reads and
no reader opens decays at exactly the rate observed.

**Freezing beats deleting** because the entries are prose about decisions, not generated release
notes, and `git log` alone does not carry them in a form anyone will find. The cost of keeping the
file is one header that tells the truth about it.

**The guard is the part that makes this stick.** #146's finding was that the obligation lived in
one place with nothing enforcing it. Retiring the file without a guard reproduces that exact shape
in reverse — a retirement nothing enforces, and a promise that reappears the first time somebody
writes "recorded in the changelog" from habit.

## Consequences

**Accepted costs.**

- **A provisional-surface change is now recorded in a line that is rewritten every build.** The
  README line describes the *current* build, so the history of provisional changes lives in
  `git log` rather than in one scrollable file. For a project with no release yet and a
  single-digit provisional surface, that is the right trade; it would not be if either grew.
- **The guard is pattern-based**, and its docstring says so. It catches the phrasings that exist
  today and the obvious variants, not every sentence someone could write.
- **The plan's M1 criterion changes.** A merged criterion is being amended after the fact, which is
  the thing plans are amended *for* — but it means the M1 checklist in the plan and the M1 checklist
  as merged differ by one line.

**Follow-on effects.**

- The stamp-advance gap #146 also found — build `08232026.39` covering two merged PRs, because
  `test_build_stamp.py` checks that README agrees with `__version__` and not that `__version__`
  moved — is **not** settled here and is filed separately as
  [#147](https://github.com/eddiefiggie/srd-rules-engine/issues/147). Retiring the changelog does
  not touch it, and closing #146 would otherwise bury it.

## Evidence

The guard was run against the pre-change tree (`26b88d9`, exported to a scratch dir with the test
copied over it) and went red on **four** live obligations across three files: `stability.py:17` and
`stability.py:109`, the pull-request template's checkbox, and the plan's M1 criterion. It is green
after this record's changes, so it covers the diff rather than standing over an already-clean tree.

Its companion check — that the searched paths still exist — was proven red separately by deleting
`CONTRIBUTING.md` from that same export. A guard whose file walk quietly stops finding files
passes.

One false positive was found and fixed in the prose rather than in an exemption list: `AGENTS.md`
stated the rule by quoting the phrase it forbids, so the guard flagged its own instruction. The
sentence was rewritten to describe the promise instead of quoting it, which keeps the pattern set
free of file-specific carve-outs.

## Status of implementation

**Implemented with this record.** `CHANGELOG.md` carries the retirement header and stops at
`08232026.36`; `.github/PULL_REQUEST_TEMPLATE.md` loses the box; `stability.py` names the README
build line in both places; the plan's M1 criterion is amended; `AGENTS.md` states the rule beside
the build-stamp rule it belongs with; and `tests/test_changelog_is_retired.py` holds it. No clause
is unbuilt.
