# 0025 — sight is a relation derived over stored state, and the mapping that resolves it ships empty

- **Status:** Accepted, 2026-08-24
- **Settles:** the design questions [#138](https://github.com/eddiefiggie/srd-rules-engine/issues/138) poses. The coverage work itself stays open there
- **Requirements:** R14, R17, R18 · touches R1, R4, R19, R31
- **Related:** [0014 — positional state](0014-positional-state.md), which gives distance in feet and
  is what a sense range is measured with; [0004 — the trigger catalogue](0004-trigger-catalogue.md),
  whose over-firing rule decides clause 6; [0021 — a round is six seconds](0021-a-round-is-six-seconds.md)
  clause 3, whose re-derivation warning clause 4 has to answer; [0019 — `kind` is a filing
  label](0019-kind-is-a-filing-label.md), which is why the subsystem is not defined by the
  inventory's `kind` column

## Context

Ten inventory shapes are unimplemented and nothing has been built toward any of them: five tagged
`sense` and five tagged `environment`. #138 filed them as one issue rather than ten on the grounds
that they are one mechanism read three ways — a creature's sense decides what a light level means
for it, obscurement is what light resolves into, and some senses bypass the chain entirely.

Four clauses the engine already holds are waiting on the result, and `Conditions.unenforced_clauses`
names them in typed form rather than leaving them to be discovered: Invisible's
`concealed-from-effects-requiring-sight` and `unless-seen-exception`, Frightened's
`line-of-sight-qualifier`, and Charmed's `cannot-attack-or-target-the-charmer`. `core.conditions`
discloses the compromise being made meanwhile — Frightened's Disadvantage is applied whenever the
condition is held, because line of sight is not modelled, which is the stricter reading and the
direction that cannot invent a success.

This record answers the four design questions #138 raises. It does **not** transcribe the rules,
and clause 5 is why.

## Options considered

**Build a shape at a time, starting with Darkvision.** Rejected, and #138 already says why:
Darkvision without light levels produces a value nothing can consume. The dependency runs
sense → light → obscurement → visibility, and the far end is where the four waiting clauses attach.

**Model visibility as a stored per-pair fact.** Rejected under clause 4's reasoning: a stored
relation between every observer and every target is a second thing to keep consistent with the two
it is computed from, and the inconsistency would be silent.

**Take light as an argument at the point of adjudication**, the way `areas.creatures_in` already
takes its obstructions. Rejected, and clause 2 is the argument. This was the closest call in the
record, because there is a precedent in the tree pointing the other way.

**Wait for the document before deciding any of it.** Rejected as the wrong granularity: the
structural questions do not depend on the rule values, and leaving them open means the next person
to reach for this subsystem re-derives them. The questions that *do* depend on the document are
isolated in clause 5 rather than answered from memory.

## Decision

**1. This subsystem is nine shapes. Telepathy is not one of them.** The other four `sense` shapes
are ranges over `0014`'s distance that answer "can this creature perceive that one, and how".
Telepathy is a communication channel, and nothing about light, obscurement or line of sight changes
what it does. It stays in the inventory as an unimplemented shape and gets its own consumer, filed
as [#149](https://github.com/eddiefiggie/srd-rules-engine/issues/149). Grouping by mechanism rather
than by the inventory's `kind` column is 0019's rule, applied: `kind` is a filing label, and a test
already refuses to let any module under `src/` branch on it.

**2. Light is state, never a query argument.** Illuminated volumes live on `EncounterState`
alongside the combatants, set when the encounter is constructed or changed through a ruling — never
supplied by the caller at the moment an outcome is computed. An input the caller hands over at
adjudication time is an input the caller *chooses*, and choosing between Bright Light and Darkness
is choosing between Advantage and Disadvantage. That is the agent deciding how it turns out, which
is the one thing the product contract does not permit (R1, R4). #119 settled the same question for
conditions — a condition reaches state through a ruling, or not at all — and this is that rule
applied to terrain.

**3. Senses are per-creature state, shaped like `Speeds`.** A `Senses` value on `Combatant`, with
each sense a range in feet and `None` meaning the creature has no such sense — the distinction
`Speeds` already draws between "no Fly Speed" and "a Fly Speed of 0".

**4. Visibility is derived on demand, and that does not violate 0021 clause 3.** Whether an observer
can see a target is a *relation* over two stored values — the observer's senses and the light where
the target is — so it is computed per query rather than stored. 0021 clause 3 warns that "a value
re-derived on every query is a value a caller can re-draw by choosing when to ask", and the warning
does not reach here: both inputs are stored state, neither is caller-supplied at query time, and
the derivation is therefore a pure function of a generation of `EncounterState`. The hazard 0021
names is a caller varying an *input*, not a caller repeating a *computation*.

**5. The mapping from light and sense to obscurement ships as a verified table, and it ships empty
and refusing.** Which light level a sense converts into which other, and what obscurement means for
an attack roll, are rule values. R31 forbids inferring them, and this repository holds no copy of
the document — so the table is declared with a `Verification` block in the `unverified` state, no
rows, and every query against it refuses rather than defaulting. `core.spellcasting` is the
precedent: it ships **no** slot table because compiling one would be the inferred rule value R31
forbids, and `MAX_SPELL_LEVEL` is the one value that slipped past that discipline
([#130](https://github.com/eddiefiggie/srd-rules-engine/issues/130)). The pages must be asserted in
the verifier before a single row is added, which is [#150](https://github.com/eddiefiggie/srd-rules-engine/issues/150)
and needs someone holding the SRD v5.2.1 PDF.

**6. Nothing here reaches the trigger catalogue.** A trigger exists to challenge a declaration that
claims *no test is needed*. Sight changes how a test resolves — Advantage, Disadvantage, whether a
target is legal at all — and creates no test that would otherwise be skipped in silence. Adding
"attacking a creature you cannot see" as a trigger would fire on declarations that already resolve
correctly through the ruling, which is 0004's over-firing fidelity defect. Sight enters through
derivation and target legality, and the catalogue is untouched.

**7. The read surface is already observer-relative, so clause 4's blast radius is small.** #138
names this as the question with the widest reach: if the same square is Bright Light to one observer
and Darkness to another, "what is legal" becomes observer-relative in a way it currently is not.
It already is. `read(state, actor_id)` is keyed to an actor and `Situation` already reports
observer-relative values such as `attack_rolls_against_you`. What is missing is the input, not an
axis. `Situation` gains typed fields for the actor's own light level, its obscurement and its
senses; `unenforced_clauses` shrinks as clauses become enforceable, which is the completion signal
for this subsystem and is already machine-readable.

## Why

**The order of the clauses is the argument.** Clause 2 decides *where* the inputs live, clause 4
decides that the answer is computed rather than kept, and clause 5 decides that the computation
refuses until the document has been read. Together they make the failure mode visible: an engine
that cannot yet answer "can this creature see that one" says so, rather than answering from a table
somebody assembled from memory of a game they have played.

**Clause 2 is the one that carries the product contract.** Everything else here is modelling
preference. Light as a per-call argument would work, would be less code, and would hand the agent a
dial marked *Advantage* — the failure this engine exists to remove, arriving as an API convenience.

**Clause 5 is what stops this record from becoming the rules.** #138's own summary of the
mechanism — Darkvision treating Dim Light as Bright, Heavily Obscured meaning the Blinded condition
— is cited to pages 180 and 182 and is very likely right. It is also not asserted anywhere in this
repository, and a right value is indistinguishable from a wrong one once it is inside a finished
ruling. The structure can be built now; the table waits for the page.

## Consequences

**Accepted costs.**

- **The subsystem is unusable between the structure landing and the table being filled.** A
  `Senses` value that nothing can resolve is a stub with a citation attached — the same shape as
  `Speeds.hover`, which #130's sweep recorded as declared-and-read-by-nothing rather than as a
  defect. It is a visible gap, which is the trade this project makes everywhere.
- **The four waiting clauses stay unenforced until then**, and `core.conditions` keeps applying
  Frightened's Disadvantage on the stricter reading. That divergence is disclosed today and stays
  disclosed; what changes is that it now has a named end.
- **Obstructions and light will enter by different routes**, which is an inconsistency this record
  creates deliberately rather than one it inherits. `areas.creatures_in` takes obstructions as a
  query argument; clause 2 puts light on state. Both are terrain. The seam is worth resolving in
  one direction and is filed as [#151](https://github.com/eddiefiggie/srd-rules-engine/issues/151)
  rather than settled here, because obstructions currently reach no adjudication path and the
  question is not yet load-bearing.

**Follow-on effects.**

- #138 stays open as the coverage issue for the nine shapes. This record answers its design
  questions; it does not build anything.
- The inventory's count is unchanged at 76 of 211. A design pass moves no shape, which is the
  README's standing warning about reading that number as progress.

## Evidence

No spike. The three questions that looked open were answered by reading what is already in the
tree, and one of them turned out to be already decided:

- `read(state, actor_id)` and `Situation.attack_rolls_against_you` in `core/read_surface.py` —
  the surface is observer-keyed today, which is clause 7.
- `Speeds` in `core/position.py`, with its `None`-versus-zero distinction, which clause 3 mirrors.
- `areas.creatures_in(..., obstructions=())` in `core/areas.py` — the precedent clause 2 declines
  to follow, and the reason #151 exists.
- `core/spellcasting.py`'s absent slot table, which is clause 5's precedent for shipping a table
  with no rows rather than a table filled from memory.

## Status of implementation

**The structure is built; the rules are not, and cannot be until the document is read.**
`core.sight` landed 2026-08-24, with `tests/test_sight.py` covering it.

| Clause | State |
|---|---|
| 1 — Telepathy is not in this subsystem | Built as an absence: `Sense` has no Telepathy member and `tests/test_sight.py` asserts it. Its own consumer is [#149](https://github.com/eddiefiggie/srd-rules-engine/issues/149) |
| 2 — light is state | `EncounterState.lighting`, with `Lighting.ambient` and `LitVolume`. `None` ambient means nobody has stated a level, not Bright Light |
| 3 — senses are per-creature state | `Combatant.senses`, shaped like `Speeds`, with `None` distinct from a range of 0 |
| 4 — visibility is derived | The seam exists as `obscurement_at` and `can_see`; both refuse. Nothing is stored |
| 5 — the table ships empty and refusing | `SIGHT_VERIFICATION` is `unverified`, both tables carry no rows, and a guard fails if a row appears while the state has not moved. The reading is [#150](https://github.com/eddiefiggie/srd-rules-engine/issues/150) |
| 6 — no new triggers | Nothing to build. `core.triggers` is untouched |
| 7 — the read surface reports the input | `Situation.light_level` and `Situation.senses`, and all three transports render them |
| The obstruction seam, deliberately left inconsistent | [#151](https://github.com/eddiefiggie/srd-rules-engine/issues/151) |

**No effect shape is resolved by any of it**, and none is marked implemented: the engine can hold
a creature's Darkvision and still cannot say what it does. Coverage stays at 76 of 211, and #138
stays open for the nine shapes.

_Updated 2026-08-24 while implementing the structural half of [#138](https://github.com/eddiefiggie/srd-rules-engine/issues/138). This record
shipped saying "None. Nothing in clauses 1-7 is built", which was true for about a day — the
section is maintained as work lands rather than frozen with the decision (0024)._
