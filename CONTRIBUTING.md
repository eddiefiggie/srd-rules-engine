# Contributing

Thanks for looking. This is a solo-maintained project with a specific and fairly opinionated
architecture, so the most useful thing before writing code is a shared understanding of what
the engine refuses to do.

Read [`AGENTS.md`](AGENTS.md) first — it carries the standing rules and the non-goals. Those
apply to humans too; the filename reflects that LLM agents are expected contributors here, not
that people aren't.

## The one thing to understand first

The agent decides **that** a rule applies and **which** one. It can never decide **how it turns
out**. A change that gives a caller any path to an outcome other than the single adjudication
entry point is not a feature this project wants, regardless of how convenient it is.

## Ways to help, roughly in order of usefulness

1. **SRD fidelity defects.** A rule modelled wrongly is the worst class of bug here, because a
   wrong ruling is indistinguishable from a right one. Use the *SRD fidelity defect* issue
   template and cite the SRD v5.2.1 section.
2. **Trigger catalogue misses.** A no-test claim that *should* have been challenged and wasn't.
   These are close to unmeasurable from play alone — a missed skip leaves no trace — so a
   reported one is genuinely valuable.
3. **Memory-port implementations.** The port is meant to be implemented by other people's
   systems. If the published schema didn't give you enough to build against without reading
   engine internals, that's a bug in the schema.
4. **Adapters.** MCP, HTTP, and CLI live outside the core over the same contract.

## Before you open a pull request

- **Open an issue first** for anything beyond a typo. Issues are the single source of truth for
  open work here, and an unlinked PR has nowhere to record why the work was wanted.
- **Never infer a rule value.** Every mechanic traces to the official SRD v5.2.1 document.
  If the SRD doesn't state it outright, it's excluded and the exclusion disclosed — not
  guessed. Widely
  known 5e behaviour that isn't in the SRD is still a guess.
- **Don't add Product Identity.** Settings, named characters, iconic monsters, and trade dress
  outside the SRD are not licensed here. See [`NOTICE.md`](NOTICE.md).
- **Cite the requirement.** When code implements a numbered requirement from the plan, name it
  (`R14`) in the docstring or the PR body. Full SRD 5.2 coverage is the definition of done, and
  an untraceable implementation can't be counted toward it.
- **Prove new tests fail against the pre-change tree.** A green suite can cover none of your
  diff.

## Setup and the gate

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest && ruff check . && ruff format --check . && mypy
```

CI runs exactly that on every PR, across Python 3.11–3.13. Branch off `main`; `main` is
protected.

Conventional-commit subjects please — `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`
— with a closing keyword (`Closes #N`) when the PR resolves an issue. A bare `#N` links without
closing, and then closing depends on someone remembering.

## Licensing of contributions

Contributions are accepted under the [MIT License](LICENSE) covering the engine's own code.
SRD-derived material remains under CC BY 4.0 and carries its own attribution obligations —
[`NOTICE.md`](NOTICE.md) explains the split, and it matters more here than in most projects.
