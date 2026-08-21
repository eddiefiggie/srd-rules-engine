# Attribution and licensing

This repository contains two separately-licensed kinds of material. Keep the line
between them visible; it is the reason this file exists rather than a single
`LICENSE`.

## The engine's own code — MIT

Everything under `src/`, `tests/`, and the repository's own documentation is
original work licensed under the [MIT License](LICENSE). Embed it, fork it, ship
it inside a closed product — MIT asks only that the copyright notice travels with
it.

## SRD 5.2 derived material — CC BY 4.0

Game mechanics, rule names, statistics, and any rules text this project encodes
derive from the **System Reference Document 5.2** published by **Wizards of the
Coast LLC**, made available under the
[Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/legalcode)
(CC BY 4.0).

CC BY 4.0 is not a public-domain dedication. It requires attribution, a licence
link, and an indication of changes made. Those obligations attach to *anything
downstream of the SRD*, including a machine-readable re-expression of it, which
is precisely what a rules engine is.

## Verification gate

> **Status at build `08212026.1`: no SRD-derived content has been committed yet.**
> The repository currently holds project scaffolding, governance, and original
> prose only.

Before the first commit that lands SRD-derived mechanics or data:

1. The exact attribution statement WotC's published SRD 5.2 requires must be
   transcribed here **verbatim from the document**, not reconstructed from memory
   or from a third-party summary.
2. The indication-of-changes wording must state what this project altered — at
   minimum, that mechanics were re-expressed as executable code and that entries
   failing verification were excluded.
3. Every seeded entry must trace to the official document per the
   exclude-until-verified rule in [`AGENTS.md`](AGENTS.md).

That gate is tracked as a blocking issue. Do not land rules data ahead of it.

## What is *not* covered

The SRD is a subset of the full game. Product Identity — settings, named
characters, iconic monsters, and trade dress outside the SRD — is not licensed
here and must not enter this repository. If a mechanic cannot be traced to the
SRD 5.2 document, it does not belong in the engine, regardless of how widely it
is known.
