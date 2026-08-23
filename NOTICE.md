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
derive from the System Reference Document 5.2.1, made available under the
Creative Commons Attribution 4.0 International License (CC BY 4.0).

CC BY 4.0 is not a public-domain dedication. It requires attribution, a licence
link, and an indication of changes made. Those obligations attach to *anything
downstream of the SRD*, including a machine-readable re-expression of it, which
is precisely what a rules engine is.

### Required attribution statement

The following is transcribed verbatim from the Legal Information page of the
official **SRD v5.2.1** PDF (1 May 2025), which specifies this exact wording:

> This work includes material from the System Reference Document 5.2.1 (“SRD
> 5.2.1”) by Wizards of the Coast LLC, available at
> https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative
> Commons Attribution 4.0 International License, available at
> https://creativecommons.org/licenses/by/4.0/legalcode.

Two constraints come from the same page and are easy to violate by being helpful:

- **Do not add any further attribution.** The document asks that no other
  attribution to Wizards or its parent or affiliates appear beyond the statement
  above. A well-meant extra credit line is a departure from the terms, not a
  courtesy. This file names the publisher only inside the quoted statement for
  that reason.
- **Compatibility wording is permitted.** A work may state that it is
  "compatible with fifth edition" or "5E compatible".

The document also notes that Section 5 of CC BY 4.0 contains a Disclaimer of
Warranties and Limitation of Liability.

### Changes made

This project does not reproduce the System Reference Document. It re-expresses a
subset of its mechanics as executable code, and the differences below are the
indication of changes CC BY 4.0 requires.

- **Re-expressed, not reproduced.** Mechanics are modelled by hand from SRD
  v5.2.1 into typed effect shapes — what a ruling applies, to whom, for how long.
  Rules prose is not redistributed.
- **The revision is named, because it matters.** SRD v5.2.0 (22 April 2025) is a
  different document: it omits fifteen magic items and carries a duplicated Iron
  Golem stat block where the Knight belongs. A reader checking this project
  against v5.2.0 would find discrepancies that are the document's, not ours.
- **Reorganised.** Content is restructured from document order into per-entry
  records, each carrying its own verification block naming the section it was
  checked against.
- **Incomplete by design, and the gaps are visible.** Only entries verified
  against the official document reach the engine. Entries that fail verification
  are marked `excluded` with a stated reason, and the loader refuses them rather
  than filtering them silently.
- **Extended.** The engine adds material the SRD does not contain — the ledger,
  the read surface, the trigger catalogue, the adjudication contract. That
  material is this project's own work under MIT and is not derived from the SRD.

## What is *not* covered

The SRD is a subset of the full game, and the test is the document rather than
familiarity: **if a mechanic, name, or stat block cannot be located in SRD
v5.2.1, it does not belong in this repository, however widely known it is.**

Before adding a monster, a spell, or a proper noun, check:

1. **Is it in SRD v5.2.1?** Locate the actual section. The community markdown
   corpus is a finding aid for locating a passage; it is never the thing checked
   against. See [`docs/decisions/0003-seed-and-verification.md`](docs/decisions/0003-seed-and-verification.md).
2. **Is it the name the SRD uses?** The document renames or omits much of the
   game's iconic material. A name absent from it is out even when the mechanic is
   in.
3. **Is it a trademark rather than licensed content?** A content licence does not
   grant trademark rights, and CC BY 4.0 says so expressly.
4. **Does it trace?** Per the exclude-until-verified rule in
   [`AGENTS.md`](AGENTS.md), an entry with no citation to a section of the
   document is `unverified`, and the loader refuses it.

**There is no "Product Identity" boundary here, and invoking one is a category
error.** Product Identity is defined in Section 1(e) of the Open Game License
1.0a. SRD 5.2.1 is offered under CC BY 4.0 and *not* under the OGL: the strings
"Product Identity", "Open Game", and "OGL" appear nowhere in the document. Older
SRDs (5.0, 5.1) are OGL documents and do carry a Product Identity designation —
material transcribed from one of those is the wrong edition under the wrong
licence, and does not belong here.

## Verification gate

The attribution gate is settled: the statement above is transcribed from the
official document, and the indication of changes is stated. What remains standing
is the per-entry rule.

Every seeded entry must trace to the official SRD v5.2.1 document per the
exclude-until-verified rule in [`AGENTS.md`](AGENTS.md). Only `verified` entries
reach the engine; `unverified` and `excluded` entries are refused by the loader
rather than filtered silently.
