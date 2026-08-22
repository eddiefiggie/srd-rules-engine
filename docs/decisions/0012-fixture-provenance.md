# 0012 — Provenance selects the entry point, not a branch inside one

- **Status:** Accepted, 2026-08-22
- **Settles:** [#41](https://github.com/eddiefiggie/srd-rules-engine/issues/41)
- **Requirements:** R31, R32 · touches R21
- **Related:** [0003 — seed and verification](0003-seed-and-verification.md), whose rule this
  scopes rather than relaxes; [0008 — the extension channel](0008-extension-channel.md) settled a
  structurally similar case

## Context

The M1 plan runs its vertical slice on invented fixture rules so the milestone is provable
without waiting on the attribution errand. That needs the loader to admit something
[0003](0003-seed-and-verification.md) appears to forbid:

> Only `verified` entries reach the engine. The loader refuses `unverified` and `excluded`
> entries rather than filtering them silently, and a guard test asserts that it does.

The plan resolved this by reading a fixture as outside that rule's scope — it is not
SRD-derived, so it has nothing to verify against, exactly as
[0008](0008-extension-channel.md) reasoned about `authored` trigger rows. The reading is
defensible. It was also made **in a plan rather than in a record**, which is the problem
this issue exists to fix.

### The failure this prevents is specific

A contributor reads 0003 in isolation, finds a loader that admits fixtures, and concludes
one of them is a bug. They "reconcile" it by loosening the gate — and unverified **SRD**
entries begin loading, which is precisely the defect 0003 exists to prevent.

The danger is not that fixtures are risky. A fixture never reaches a user. The danger is
that a loader with two arms of different strictness looks like an inconsistency, and
inconsistencies invite tidying.

### The parallel to 0008 is close but not exact

An `authored` trigger row **ships**; it is part of the product, and 0008 widened what may
ship because a verification gate would have meant the catalogue could never exist. A
fixture rule ships to nobody. So this case is safer than 0008's, and the reasoning that
justified widening there does not have to be stretched here.

## Options considered

- **Record the reading and keep one loader.** Rejected. It closes the documentation gap
  and leaves the mechanism that caused it: a single entry point whose behaviour depends on
  a provenance branch, with one arm stricter than the other. Recording *why* the branch
  exists helps a careful reader and does nothing for a hurried one.
- **Fixtures never touch a loader at all.** Rejected, though it is the cleanest separation
  available — 0003 would need no amendment and this record would not be required. It puts
  a synthetic seam in the middle of the milestone's end-to-end proof: U14 would exercise a
  construction path production never uses, and the slice's claim to run "end to end" would
  quietly mean "end to end apart from loading."
- **Two entry points sharing their validation.** Adopted.

## Decision

**1. There are two loaders, and provenance selects which one a caller reaches for.**

| Entry point | Admits | Refuses |
|---|---|---|
| `load_ruleset` | `provenance: srd` entries whose verification state is `verified` | any fixture-provenance entry, outright |
| `load_fixture_ruleset` | `provenance: fixture` entries | any SRD-provenance entry, outright |

Each refuses the other's provenance as a matter of identity rather than of policy. **There
is no mode flag**, so widening one cannot widen the other — a contributor loosening the
fixture loader cannot thereby admit an unverified SRD entry, because that loader does not
accept SRD entries at all.

**2. They share everything except the gate.** Parsing, shape validation, and the check that
a rule declares core fact types only (R21) are one implementation used by both. The slice
therefore exercises the real machinery; the only thing it does not exercise is the SRD
verification gate, which has direct tests of its own and cannot be exercised at all until
[#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3) closes.

**3. 0003 is scoped, not relaxed.** Its rule governs SRD-derived data, and a fixture is not
that. R31 gains a sentence saying so; nothing in 0003's substance changes, and the SRD
loader behaves exactly as it specified.

**4. A guard asserts no fixture-provenance definition exists under `src/`.** Fixtures live
in `tests/`, so the packaging half of the guarantee is checkable rather than trusted —
what ships cannot contain one, whatever a loader would have done with it.

## Why

### A branch invites tidying; two functions do not

The reading recorded in the plan is correct, and correctness was never the weak point. The
weak point is that a single loader with a strict arm and a lenient arm *reads* as an
inconsistency to anyone who has not read the reasoning, and the natural response to an
inconsistency is to remove it.

Splitting the entry point removes the appearance along with the risk. Two functions with
different names and different admissible inputs do not look like a rule applied
inconsistently; they look like two rules, which is what they are.

This is the same instinct as every other structural choice here — the empty dependency
list, the label-free matcher projection, the reader API in front of the ledger file, the
generation that `_evolve` will not let a caller override. In each, the alternative was a
rule someone has to remember.

### Scoping is honest where relaxing would not be

It would be easy to write this record as "0003 is amended to permit fixtures." That would
be false to what 0003 decided. 0003 is about **provenance chains with no unnameable link
in them**, and it reached its conclusion by finding that every candidate dataset either
carried effect-shape-free prose, mixed document revisions, or mislabelled its licence.

None of that is about fixtures. An invented rule has a perfectly nameable provenance: it
was invented, here, for this test. What it lacks is an SRD section to verify against —
because it makes no claim about the SRD.

### The cost is named

The slice does not exercise the SRD verification gate. That gate is where the project's
data-fidelity promise actually lives, so leaving it unexercised end to end is a real gap,
not a technicality. It is unavoidable while #3 is open — there is nothing verified to load
— and it closes when the first real mechanic lands.

## Consequences

**Accepted costs.**

- **Two entry points to keep in step.** A change to shape validation must not drift between
  them, which is why they share it rather than duplicating it — but the sharing is now a
  thing to preserve rather than a thing that cannot break.
- **The SRD verification gate is not exercised by the slice**, as above.
- **A fixture ruleset is a real artifact with a real loader**, so it can rot. It lives with
  the tests that use it, which is the smallest blast radius available.

**Follow-on effects.**

- **R31 is amended** to scope its rule to SRD-derived definitions and to name the fixture
  path explicitly, so the two rules are visible in the same place a reader meets either.
- **U7 implements both entry points**, and its guard tests cover each refusal in both
  directions.
- **A packaging guard** asserts `src/` carries no fixture-provenance definition.

## Evidence

No spike. The argument is from the failure mode: take 0003's rule and the plan's KTD2 as a
contributor would find them, and ask what a reasonable person does when the loader appears
to contradict a decision record. Under one loader the repair is to loosen the branch. Under
two, there is no branch to loosen, and the SRD loader's rule reads exactly as 0003 states
it.

## Status of implementation

**None at time of writing.** Both entry points and their guards land with U7.
