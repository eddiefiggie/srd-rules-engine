## What this changes

<!-- What it does and why it was wanted. Assume the reader hasn't read the issue. -->

Closes #

<!-- Use a closing keyword — `Closes #N`, `Fixes #N`, `Resolves #N`. A bare `#N` links the
     issue and leaves it open, and then closing depends on somebody remembering. -->

## Requirements implemented

<!-- Name them: R14, R22. Full SRD 5.2 coverage is the definition of done, so an
     untraceable implementation can't be counted toward it. Write "none" for docs/chores. -->

## Checklist

- [ ] `pytest && ruff check . && mypy` passes locally
- [ ] New tests were proven to fail against the pre-change tree (or this adds none)
- [ ] Any new guard was seen red before being trusted
- [ ] No rule value was inferred — everything traces to the SRD 5.2 document
- [ ] Deferrals introduced by this PR are filed as issues and linked in the prose
- [ ] Build stamp bumped in `src/srd_rules_engine/__init__.py`, and README's
      `**Current build:**` line updated to match and to say what shipped
- [ ] `CHANGELOG.md` records this build

## Anything a reviewer should push back on

<!-- Judgment calls, shortcuts taken, things you're unsure about. -->
