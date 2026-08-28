# 0037 — A concentration is an early-out, not an axis

- **Status:** Accepted, 2026-08-28
- **Settles:** [#239](https://github.com/eddiefiggie/srd-rules-engine/issues/239)
- **Requirements:** R1, R5, R31, R32
- **Related:** [0021 — a round is six seconds](0021-a-round-is-six-seconds.md), whose clause 3
  computes one expiry point at application and is the invariant this decision must not break;
  [0020 — two kinds of time](0020-two-kinds-of-time.md), which is why there are exactly two
  axes and why Concentration is not a third;
  [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  clause 5, for retirement resolving where the state change resolves;
  [0036 — a fourth occasion](0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md), which
  built the damage route and left this one open

## Context

p. 179 opens the *Concentration* entry with its central claim, and the engine has no
mechanism for it:

> Some spells and other effects require Concentration to remain active, as specified in their
> descriptions. **If the effect's creator loses Concentration, the effect ends.** If the
> effect has a maximum duration, the effect's description specifies how long the creator can
> concentrate on it: up to 1 minute, 1 hour, or some other duration.

Three sentences, and the second and third pull in opposite directions for anyone modelling
this. The second says an effect ends when Concentration does. The third says the effect
*also* has a maximum duration, stated by its description.

`DurationKind` has four members — `ROUNDS`, `END_OF_NEXT_TURN`, `CAMPAIGN_TIME`,
`UNTIL_REMOVED` — and none of them is "while the creator concentrates". `Conditions.sources`
maps a condition to the **combatant ids** that imposed it rather than to the effect that did,
so there is no handle to end things by: retiring everything a caster sourced would also end
their Grapple. `Concentration` holds `spell: str | None`, a name with nothing attached.

So `Concentration.begin` can be wired to a declaration tomorrow and the result will be a
value that names a string and, when broken, **ends nothing**. That is the state
`concentration_save_dc` was in before #215 — real machinery, no consumer — reproduced one
level up, and it is the failure [#235](https://github.com/eddiefiggie/srd-rules-engine/issues/235)
exists to remove rather than to relocate.

### Why the obvious answer is wrong

A fifth `DurationKind.CONCENTRATION` is the move that suggests itself, and it **loses p. 179's
own third sentence**. `Duration` sets one expiry point and says so:

> One of two expiry points is set, never both, because a span is counted by one axis.

Put Concentration in the `kind` slot and a Concentration spell has no maximum duration at
all. "Concentration, up to 1 minute" is not a spell that lasts until Concentration drops; it
is a spell that lasts one minute *and* drops earlier if Concentration does. The document
states both, and a model that can hold only one of them is a model that will silently keep a
spell up for an hour because nobody was hit.

This is the same error 0031 names from the other direction: not two rules that disagree, but
one rule with two clauses, modelled as though it had one.

### The shape the tree already has

`core.duration`'s module docstring answered this before the question was asked:

> ## A duration is a span with optional early-outs
>
> p. 63 shows both at once: the target "has the Poisoned condition **for 1 minute**. At the
> end of each of its turns, the Poisoned target **repeats the save** […]". One outer span,
> one early-out. Elsewhere the early-out is an event — "the Unconscious condition for 1
> minute **or until it takes any damage**".

And `Duration.save: SaveEnds | None` is already that field, commented "an early-out that runs
alongside the span, not instead of it (p. 63)". Concentration is a **second early-out of the
event kind**, sitting beside the first. Nothing about the axes changes, 0021 clause 3's
single computed expiry point is untouched, and the span the description states survives.

## Options considered

**Option 1 — a fifth `DurationKind`.** Rejected above: it spends the one `kind` slot on the
early-out and discards the span. Named here because it is what a reader will propose next,
and the reason it fails is a sentence rather than a preference.

**Option 2 — a registry of sustained effects in `EncounterState`,** keyed by concentrating
creature. Rejected. It is a second place where "what holds this condition up" is recorded,
and the first place — the condition's own duration — would still exist. Two records of one
fact, maintained by different writers, is 0035's finding restated: they drift, and the drift
reads as correct from either side. It also makes every condition-applying path responsible
for registering, which is the shape that gets one call site wrong.

**Option 3 — a list on `Concentration` of what it sustains.** Rejected, and it is Option 2
pointed the other way. The link is stored once, and it is stored on the **effect**, because
the effect is what knows it was cast with Concentration. A creature's `Concentration` holding
a list means every application, expiry, removal and death has to keep that list true.

**Option 4 — reuse `Conditions.sources`.** Rejected. It records *who* imposed a condition, not
*what* sustains it, and the two differ exactly where it matters: a caster's Grapple and their
Concentration spell have the same source and must not end together.

**Option 5 — leave it, and let a concentration spell be `UNTIL_REMOVED`.** Rejected as the
disclosed-gap option, which this project usually prefers. It fails here because
`UNTIL_REMOVED` means "no span either axis can count" and is reported as **not retirable** —
so the engine would state, in a field a driver reads, that it cannot end an effect it can in
fact end. A wrong disclosure is worse than a missing feature.

## Decision

**1. The link is a second early-out on `Duration`, beside `save`.** An event early-out naming
the creature whose Concentration sustains the effect. The `kind` and its expiry point continue
to carry the span the description stated, and `__post_init__`'s axis invariants are unchanged.

**2. The early-out names the concentrating creature, and the link points from the effect to
the concentrator.** One record of the fact, on the side that knows it at application time.
Ending X's Concentration retires exactly what X's Concentration sustained, and nothing another
caster is holding up. Finding what to retire is a walk over the combatants, which is always
consistent by construction — no list to maintain, and no writer that can forget to.

**3. Retirement happens where the Concentration ends, and needs no roll.**
`EncounterState.with_concentration_ended` already exists and is the place. Retiring a
sustained effect is deterministic bookkeeping rather than an outcome — the same reasoning
under which `advanced_turn` retires a round count and `with_time_passed` retires a clock
minute (0021 clause 2), and 0023 clause 5's principle that a state change resolves where the
state change happens.

**4. The end of Concentration is materialised in state, never derived.** A derivation
recomputes a fact from present state; p. 179 states an **event**, and an event is spent.
`Concentration.after_conditions` recomputed from the current conditions, so the spell came
back when Incapacitated lifted, and `with_damage` — asking the same derivation deliberately,
so that state and the read surface would agree — then compelled a save to maintain something
already over ([#238](https://github.com/eddiefiggie/srd-rules-engine/issues/238)). This clause
is a prerequisite for the others rather than a companion to them: an end that never *fires*
is an end nothing can hang retirement off.

**5. Which effects require Concentration is per-effect data, and the engine never infers it.**
p. 179: "as specified in their descriptions". The imposing effect states it, exactly as p. 63
states the save-ends ability and DC per effect and for the same reason — there is no general
rule to read it from, and a spell list compiled here would be the inferred rule value R31
forbids. No such list ships in this repository.

**6. "The effect ends" reaches as far as the engine can hold the effect, and the remainder is
disclosed.** What this engine can retire is a condition with a duration. A Concentration spell
that also creates an area, an obstruction or a summoned creature has parts this engine does
not model, and clause 1 does not pretend otherwise. R32 discloses the boundary rather than
letting "the effect ends" imply a completeness the tree does not have.

## Why

**The decisive evidence was a sentence, not a preference.** Options 1 and 5 are both
defensible against a summary of p. 179 and both fail against the entry itself — Option 1
against the third sentence, Option 5 against `retirable`'s meaning. Reading the entry whole is
what separated them, which is R31's argument in miniature: the summary of a rule and the rule
are different objects.

**Clause 2 is the clause this record would have got wrong.** A list on `Concentration` is the
intuitive model — a caster holds a spell up, so the caster holds the list — and it is the one
that requires every writer in `core.state` to be correct forever. The link belongs where it is
*known*, and it is known at the moment the effect is applied, by the effect. Everything after
that is a query.

**Clause 4 is here rather than in its own record because it is the same mistake at a different
size.** Deriving the end of Concentration and registering what it sustains are both attempts to
recompute something that happened. #238 is what the first one costs, live in the tree, and it
is the reason this record leads with the materialisation rather than treating it as a detail of
the fix.

**Nothing here creates a new way for an effect to end.** A condition already ends by span, by
save, or by an effect that removes it. This adds a second early-out to a field that already
holds one, retired by a transition that already exists.

## Consequences

**Accepted costs.**

- **`Duration` grows a second optional early-out**, and the pair will read as a list wanting to
  be generalised. It should not be: `save` is due at the end of each turn and is rolled;
  this one fires on an event and is not. Two fields that behave differently are two fields
  (0019).
- **`retirable` becomes a two-part question.** Today it means "not `UNTIL_REMOVED`". An effect
  with no span and a concentration early-out is retirable and has no expiry point, so the
  property and `derivation()` both need revisiting rather than extending. Named in
  [#240](https://github.com/eddiefiggie/srd-rules-engine/issues/240) rather than left to be
  discovered by whoever adds the field.
- **Retirement is a walk over the combatants.** Solo play with one player character bounds it
  to a handful of creatures, and a walk that is always right beats an index that can be stale.
- **Clause 6 is a disclosed incompleteness, and disclosures decay.** "The effect ends" will
  read as total to anyone who does not find this clause.

**Follow-on effects.**

- **#238 is fixed by clause 4 in the change that carries this record**, ahead of the rest.
- **p. 179's replacement clause is quoted short in the tree.** `Concentration.begin` cites
  "you start casting a spell that requires Concentration" and drops "or activate another
  effect that requires Concentration" — which also means `Concentration.spell` is named for the
  half that was quoted, and an item-granted Concentration has no honest value to put in it.
  Filed as [#241](https://github.com/eddiefiggie/srd-rules-engine/issues/241).
- **Coverage does not move.** `concentration` is claimed and was already reachable (0036 clause
  8). This makes it correct, not larger.

## Evidence

Read in the official SRD v5.2.1 PDF for this record, printed **p. 179**, the *Concentration*
entry **in full** — which is how the third sentence and the replacement clause's second half
were noticed. The entry names three breaking factors besides the voluntary end, and its
opening paragraph states both the sustaining relationship and the maximum duration.

In the tree, and these are the findings the decision rests on:

- `DurationKind` has four members and `Duration.__post_init__` enforces that exactly one
  expiry point is set; `Duration.save: SaveEnds | None` is already an early-out "that runs
  alongside the span, not instead of it".
- `core.duration`'s module docstring states the span-plus-early-outs shape and gives p. 63's
  worked example and the event-shaped case from the same page.
- `Conditions.sources` is `Mapping[Condition, frozenset[str]]` of combatant ids, and
  `Conditions.durations` is keyed by condition — so a condition knows its span and not what
  sustains it.
- `Concentration.after_conditions` is pure and was called at read time by
  `core.read_surface.read` and by `EncounterState.with_damage`; nothing wrote the field. The
  resurrection and the save it compels were reproduced through the public API, not inferred.
- `EncounterState.with_death` sets `death_saves.dead` and applies no condition, so death was
  structurally invisible to a conditions-only derivation.

## Status of implementation

**All six clauses are now built.** Clause 4 shipped with this record (#238); clauses 1, 2, 3,
5 and 6 shipped under [#240](https://github.com/eddiefiggie/srd-rules-engine/issues/240),
which was filed as this record landed — because the gate issue closed here, and an unbuilt
clause tracked by a *closed* issue reads as finished work rather than as absent work.

**Clause 3 named the wrong place, and the correction is the useful part of this section.**
It said retirement happens in `EncounterState.with_concentration_ended`, which was the only
place that existed when this was written. Clause 4 then landed in `Combatant.__post_init__`,
so `with_condition` and `with_death` end a Concentration through `replace` without
`EncounterState` hearing about it — and the two clauses, written together, disagreed. The
decision clause 3 encodes is unchanged and correct: retirement is deterministic bookkeeping
that happens when Concentration ends, and needs no roll. **Where** it lives moved to a
whole-state invariant.

That was demonstrated rather than argued. The clause-3 hook was built by hand and run against
the suite for #240: it passes fifteen of nineteen tests and misses exactly the Incapacitated
route, the death route, the absent-sustainer edge and the one-pass case. Death is the one with
no caller to make the omission obvious, which is the same shape as 0036 clause 6's argument
against three call sites.

| Clause | State |
|---|---|
| 1 — a second early-out on `Duration`, not a fifth kind | **Built.** `Duration.concentration_of`, beside `save`. A plain id rather than a `SaveEnds`-style type: p. 63 states two values per effect that travel together, p. 179 states one, and a box around one string is a box |
| 2 — it names the concentrating creature; the link points from the effect | **Built.** `Conditions.sustained_by` is the read half, the third sibling of `expired_after` and `expired_by`. No list is maintained anywhere, so nothing can forget to |
| 3 — retirement when Concentration ends, no roll | **Built, and this clause named the wrong place** — see above. It is `EncounterState.__post_init__`, a whole-state invariant, because `with_concentration_ended` is two of the four routes. No roll and no Ruling, as decided |
| 4 — the end is materialised, never derived | **Built.** `with_condition` and `with_death` write the field, `after_conditions` is removed, and the read surface reports what is stored. Guarded by the #238 reproduction asserted the other way |
| 5 — which effects require Concentration is per-effect data | **Built, and still holds by construction.** The imposing effect sets `concentration_of`; nothing in the engine infers it, and no spell list ships (R31) |
| 6 — "the effect ends" reaches as far as the engine holds the effect | **Built** as a disclosure rather than an enumeration — a condition carrying a duration, and nothing else, since a spell's area or summoned creature is not modelled at all. Guarded, because prose disclosures are the kind that decay quietly |

**#239 is closed by this record**, and #240 by the change that built the rest. #235 items 1
and 2 — starting to concentrate, and the replacement rule — are unblocked and remain open
there; this record's clause 1 is what gives the first of them somewhere to hang an effect.

_Written 2026-08-28 against SRD v5.2.1._
