# 0023 — The turn's end is a loop-owned phase, and an early-out is two mechanisms rather than one

- **Status:** Accepted, 2026-08-23. Implemented 2026-08-24 — see Status of implementation.
- **Settles:** [#110](https://github.com/eddiefiggie/srd-rules-engine/issues/110)
- **Requirements:** R1, R4, R8 · touches R12, R29
- **Related:** [0001 — the agent seam is a generator of typed requests](0001-agent-seam.md), whose
  shape this extends rather than revises; [0015 — reactions and the agent
  seam](0015-reactions-and-the-agent-seam.md), which answered the same *kind* of question in the
  negative and whose deferred ledger-interleaving problem this one inherits;
  [0016 — adapters hold the turn](0016-adapters-hold-the-turn.md), which gains a phase

## Context

#110 states the gap precisely. `Conditions.saves_due_after` reports which held conditions repeat a
save at the end of a creature's turns (p. 63: "repeats the save at the end of each of its turns,
ending the effect on itself on a success"). `EncounterState.with_condition_ended` applies the result
once something has decided it. **Nothing joins those two ends.**

The issue also framed the open question, and that framing is what this record has to correct:

> The last one is the interesting part and it touches [0015]: `TurnLoop.run(state, actor_id)` yields
> for one actor's declaration slot, and an end-of-turn save is not a declaration. Whether that is a
> new request type or a variant of the existing one probably wants a decision record rather than a
> patch.

Three facts found while looking say the choice is not between those two.

### 1. Nothing owns the end of a turn

`TurnLoop.run` is one **declaration slot**, not a turn. It returns a `TurnOutcome` when the slot
resolves. `EncounterState.advanced_turn` — the thing that actually ends a turn, and where
encounter-axis durations retire — is called by the **caller**, outside the loop entirely:

```
$ grep -rn "advanced_turn()" src tests | grep -v "def advanced_turn"
tests/test_actions.py:126 …  tests/test_read_surface.py:123 …  tests/test_combat.py:374 …
tests/fixtures/encounter.py:363:        state = state.advanced_turn()
```

Every hit is a test or the fixture. Nothing under `src/srd_rules_engine/loop/` calls it. So there is
no moment inside the loop that *is* "the end of this creature's turn" — which is why neither
candidate in #110's framing fits. A new request type has no phase to be yielded from, and a
declaration-request variant would have to be yielded from a slot that has already returned.

### 2. The precedent named in the issue has the same hole

#110 says "the `death_save_resolver` is the precedent and the shape is the same". The shape *is* the
same — including the missing half. `death_save_resolver` is registered in no ruleset, and
`Combatant.makes_death_saves` has no consumer anywhere outside its own tests:

```
$ grep -rn "\.makes_death_saves" src
core/duration.py:185:   … `Combatant.makes_death_saves` records that a death save is due …   (a docstring)
core/death.py:85:       … `Combatant.makes_death_saves` answers that, and the turn loop is what consults it.
core/death.py:97:       if not actor.makes_death_saves:                                        (the resolver's own guard)
```

Two docstrings promising that the turn loop consults it, and one guard inside the resolver refusing
to run when it is false. **The turn loop does not consult it.** So this is not one omission with a
precedent to copy; it is two instances of one omission, and they want one mechanism rather than two.

### 3. No ruling can end a condition

`EffectKind` has six members — `damage`, `healing`, `death-save-success`, `death-save-failure`,
`stabilised`, `death` — and `_apply` has a branch for each. None of them touches `Conditions`.
Conditions reach state only through `EncounterState.with_condition` and `with_condition_ended`,
which callers invoke directly.

So even with the save rolled, its success has no route to `with_condition_ended` **through a
ruling**. Adding the request type without adding the effect kind would produce a save whose outcome
the engine announces and then does not apply — which is the same class of defect one layer along.

## The question this actually poses

Not "which request type", but: **who owns the end of a turn, and is a compulsory save something the
agent is asked about?**

## Options considered

**1. A new request type yielded from `run`.** Rejected on fact 1. `run` has returned by the time the
turn ends; there is no phase for the request to belong to. Making one would mean `run` no longer
returning at the end of the slot — which is a redesign of the seam, and 0001 chose that boundary
deliberately.

**2. A variant of `DeclarationRequest`, offering the save as the single legal action.** Rejected,
and this is the one worth rejecting loudly. p. 63 gives the creature no choice about repeating the
save. A declaration is the artefact the agent is *accountable* for — offering a compulsory
obligation through it invites the agent to decline it, substitute something else, or spend the
retry budget arguing, and every one of those is a path to a turn where the save did not happen. It
would also collide with R29, which gates the next declaration for an actor that already owes a
narration for this turn's ruling.

**3. A loop-owned turn-end phase.** Chosen. Below.

**4. Leave it reported, and let the caller drive it.** This is the status quo, and it recreates the
product's founding defect one level up. The README's own argument — "a correct dice function exposed
as a tool is a tool the model *may* call, and a model that doesn't realise a check is warranted will
not call it" — applies word for word to a driver that must remember to check `saves_due` after every
turn. A missed save leaves no trace, exactly like a missed skip.

## Decision

**1. `TurnLoop` gets a second generator entry point that owns the turn's end.** Sketch, not a
signature to hold anyone to:

```python
def end_turn(self, state: EncounterState, actor_id: str) -> Generator[Request, Response, TurnEnd]:
    """Every obligation the end of this creature's turn incurs, resolved."""
```

It enumerates the obligations from state, adjudicates each through the one entry point, and yields a
`NarrationRequest` per ruling so R29's bounds reach the narrator the same way they do for a declared
action. The caller calls it, then `advanced_turn`.

**2. An obligation is derived from state and never declared.** The driver is not asked *whether* the
save happens. This is not a weakening of the invariant but a strengthening of it: "the agent decides
*that* a rule applies and *which* one" describes the agent's own action, and for a compulsory
end-of-turn save the *state* decides both. Asking would be inventing a choice the document does not
give.

**3. The outcome is still an outcome.** The save resolves through the one adjudication entry point,
the engine rolls it, and the ruling appends like any other (R1, R4). Nothing about this decision
creates a second path to a result — it creates a second *occasion* on which the existing path is
taken.

**4. `EffectKind` grows a member for a condition ending,** so a successful save reaches
`with_condition_ended` through `_apply` rather than beside it. Applying a condition through a ruling
is the same missing half and is *not* settled here — it is [#119](https://github.com/eddiefiggie/srd-rules-engine/issues/119).

**5. The event-triggered early-out does not use this path.** "The Unconscious condition for 1 minute
**or until it takes any damage**" (p. 63) is not a save and is not end-of-turn. It is a state change,
and it resolves **where the state change resolves** — `EncounterState.with_damage` — which is 0015's
precedent applied unchanged: detection belongs where the triggering thing happens, not in a
catch-all. This answers #110's scope note, which feared "a design that only fits saves will have to
be reopened for it". It will not, because the two shapes are genuinely different mechanisms and
sharing one would force the damage path to route through the turn loop.

**6. `advanced_turn` refuses while an obligation is outstanding.** *This is the clause this record
is least confident in, and the first place to look if the design fights back.* It is what makes the skip structurally impossible rather
than merely serviced by well-behaved callers — and it directly narrows the limitation this project
ships disclosed, that "the skip guarantee holds only for callers the turn loop drives". The cost is
real: `advanced_turn` currently advances unconditionally, eight call sites assume that, and a
consumer that legitimately wants to fast-forward would need an explicit waiver. The alternative is to
leave `advanced_turn` alone and disclose the gap, which is consistent with how this project handles
every other limit — but it is also how the save came to be reported and never rolled in the first
place.

## Why

### Correcting the framing is most of the value

#110 asked which of two request shapes to use. Both answers would have been wrong, because the phase
they would attach to does not exist. A record that answered the question as posed would have
produced a design that could not be built, and the discovery would have happened during
implementation, with a half-written request type already in the tree.

### Compulsory is not declared, and the distinction is the invariant

The line this project will not cross is "the agent can never decide how it turns out". The line it
*also* should not cross, less obviously, is offering the agent a decision the rules do not give it.
A declaration slot for a mandatory save is a slot in which declining is expressible. Making
obligations state-derived means the only question left is the outcome, and the engine already owns
that.

### One mechanism for two obligations, found by looking rather than by design

The death save and the save-ends save were built eleven days apart and neither was wired. That is
not two oversights — it is one missing phase, and both docstrings say so while pointing at a
consumer that does not exist. Building a save-ends-specific path now would leave the death save
still unwired and a second path to add later.

## Consequences

**Accepted costs.**

- **A driver now pumps two generators.** Every driver, the CLI one included, grows a turn-end phase.
  0016's `Session` needs a matching state, since an adapter holding a suspended turn must be able to
  hold a suspended turn *end*.
- **The ledger interleaving question gets a second source.** 0015 deferred "how `session_report`
  groups interleaved entries into turns" and named it as the piece that will bite. Turn-end rulings
  land after the actor's own narration, so they hit the same unanswered question. This record does
  not answer it either, and 0015's deferral turned out never to have been filed — it is
  [#120](https://github.com/eddiefiggie/srd-rules-engine/issues/120) now, which is also the second source's home.
- **Clause 6 breaks `advanced_turn`'s current contract.** Eight call sites assume it advances
  unconditionally, and a consumer that legitimately wants to fast-forward past an obligation will
  need an explicit waiver rather than silence.
- **The death save's timing anchor is not transcribed anywhere in this repository.** `core.death`
  cites pp. 17-18 for what a death save *is* and never states when it is made. Wiring it needs that
  sentence checked against the document first — this record deliberately does not supply it from
  memory, and a design that assumed "end of turn" for both obligations because that is where
  save-ends lives would be inferring a rule value.
- **The save-ends DC and ability still come from the effect that imposed the condition**, because the
  document has no general rule to read them from. Nothing here changes that; a condition applied
  without a `SaveEnds` simply has no early-out.

**Follow-on effects.**

- Applying a condition through a ruling is the same gap in the other direction — [#119](https://github.com/eddiefiggie/srd-rules-engine/issues/119).
  It is the larger half: every condition in this engine is currently applied by a caller reaching
  past a ruling, which the vertical slice does not catch because the fixture does it too.
- #42's live-agent validation gains a case worth scripting: an agent that narrates past a turn-end
  save.
- The campaign axis this would apply to now exists (#111), so an early-out ending a span before its
  minute has somewhere to land.

## Evidence

Three greps, all reproducible from a clean checkout at `c5ab0e2`:

```
grep -rn "advanced_turn()" src tests | grep -v "def advanced_turn"    # no hit under loop/
grep -rn "\.makes_death_saves" src                                    # 2 docstrings, 1 self-guard
python -c "from srd_rules_engine.core import EffectKind; print([e.value for e in EffectKind])"
```

The third prints six members, none of them a condition.

No spike was run. The finding is an absence, and an absence is what a grep is good for — but that
also means this record has not proved the chosen design *works*, only that the two options #110
offered cannot. The first implementation is where clause 1's signature earns or loses its shape.

## Status of implementation

Built, 2026-08-24, except where noted. `tests/test_turn_end.py` covers it.

| Clause | State |
|---|---|
| 1 — a second generator entry point owning the turn's end | `TurnLoop.end_turn`, with `Obligation` and `TurnEnd` beside it. `drive` is generic over both phases, and `adapters.Session` holds a suspended turn end as `TurnEnded`. |
| 2 — obligations derived from state, never declared | `EncounterState.obligations_outstanding`. Asserted by a test whose driver supplies **no declarations at all** — if the phase asked for one, `ScriptedDriver` would raise. |
| 3 — the outcome still goes through the one entry point | `core.save_ends` is a resolver like any other; the engine rolls it (R1, R4). |
| 4 — an `EffectKind` for a condition ending | Landed with [#119](https://github.com/eddiefiggie/srd-rules-engine/issues/119) rather than here, which is what made clause 3 possible. |
| 5 — the event-triggered early-out does not use this path | **Decided, not built.** [#314](https://github.com/eddiefiggie/srd-rules-engine/issues/314). It belongs in `with_damage` and was not part of this work; `Duration` models the save and the Concentration early-outs and has no field for this one. |
| 6 — `advanced_turn` refuses while an obligation is outstanding | Built, with `waive_obligations=True` as the explicit escape. |

**Clause 6 cost less than this record feared, and needed one thing it did not anticipate.**
The record predicted eight call sites would break. Two did, both in
`tests/test_condition_duration.py`, and both were legitimately the fast-forward case the
waiver exists for.

What it missed is that `Conditions.saves_due_after` still reports a condition after a
**failed** save — so a guard reading it alone refuses to advance for as long as the creature
stays poisoned, which ends the encounter. Discharge is therefore tracked separately on
`EncounterState.discharged` and cleared as the turn advances: the question is *was the save
rolled this turn*, not *does the condition persist*. p. 63 gives one attempt per turn either
way.

**The death save remains unwired**, for the reason this record gives under Accepted costs:
its timing anchor is still not transcribed anywhere in the repository, and `save_ends` could
cite p. 63 only because `scripts/verify_d20_rules.py` had already verified that sentence.
There is no equivalent for pp. 17-18. Filed as
[#124](https://github.com/eddiefiggie/srd-rules-engine/issues/124), and held by a test so it
cannot be closed by assumption.
