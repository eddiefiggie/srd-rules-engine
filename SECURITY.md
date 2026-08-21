# Security policy

## Reporting a vulnerability

Report privately through
[GitHub's security advisory form](https://github.com/eddiefiggie/srd-rules-engine/security/advisories/new)
rather than a public issue. Expect an acknowledgement within a week; this is a solo-maintained
project, not a staffed one.

## What counts as a vulnerability here

This is an offline library with no network dependency and no LLM dependency in its core, so the
usual web surface mostly doesn't exist. The realistic risks are narrower:

- **Deserialization of untrusted ledgers or memory-port files.** A session ledger or a
  reference-memory file is data that arrives from outside. Anything that turns one into code
  execution, path traversal, or resource exhaustion is a vulnerability.
- **Adapters.** MCP, HTTP, and CLI adapters accept input from outside the process and are the
  most likely place for a real finding.
- **Dependency compromise** in the dev toolchain or an adapter's extras.

## What doesn't

**A rule modelled wrongly is a correctness bug, not a security issue** — file it publicly with
the *SRD fidelity defect* template, where it can be discussed and cited. Likewise, an agent
narrating beyond its bounds is expected behaviour, not a vulnerability: narration bounds are
advisory by design (R7), and the engine does not enforce them. If that surprises you, the
disclosure isn't doing its job — please say so in an issue.
