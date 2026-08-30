# 0049 — Advantage that outlives its roll

- **Status:** Accepted, 2026-08-30
- **Settles:** the design half of [#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318)
  and [#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319)
- **Requirements:** R4, R5, R11, R15, R18, R31
- **Related:** [0032 — an outcome conditional on its own damage](0032-an-outcome-conditional-on-its-own-damage.md),
  whose predicate this gives a subject;
  [0047 — a mastery property is unlocked by the wielder](0047-a-mastery-property-is-unlocked-by-the-wielder.md),
  clause 6;
  [0048 — a forced save is one mechanism](0048-a-forced-save-is-one-mechanism.md),
  the same "one mechanism, two rules" shape one build earlier;
  [0019 — kind is a filing label](0019-kind-is-a-filing-label.md), for the boundary vocabulary

## Context

> **Vex.** If you hit a creature with this weapon **and deal damage to the creature**, you have
> Advantage on your next attack roll against that creature before the **end** of your next turn.

> **Sap.** If you hit a creature with this weapon, that creature has Disadvantage on its next
> attack roll before the **start** of your next turn.

Every source of Advantage the engine had was a **standing fact asked at the moment of the
roll** — a condition held, a target Dodging, a weapon Heavy in these hands, a shot beyond
normal range. Each is recomputed from state every time it is needed and nothing is spent.
`D20Test` takes two booleans and p. 8's cancellation resolves them.

Vex and Sap are not that. They are granted by one roll, **held**, and **consumed** by another.
Nothing in the engine held one.

## One mechanism, reversed on all four axes

|  | Vex | Sap |
|---|---|---|
| Sign | Advantage | Disadvantage |
| Held by | the attacker | the creature that was hit |
| Scoped to | attacks **against that creature** | any attack the holder makes |
| Expires | **end** of the attacker's next turn | **start** of the attacker's next turn |

Building them separately would have produced two of everything and let the four axes drift
apart one at a time. The last row is the one with no precedent: `DurationKind.END_OF_NEXT_TURN`
is Vex's window exactly, and `Duration`'s own docstring says the encounter axis counts to "the
end of that creature's turn, in that round". Sap ends at a **start**, which nothing counted.

Note also that both windows are measured against the **attacker's** turns — "before the end of
*your* next turn", "before the start of *your* next turn" — even though Sap's token belongs to
somebody else entirely. A creature holding a Sap penalty and never attacking simply loses it
when the sapper's turn comes round.

## Options considered

**Option 1 — a held token, with liveness derived.** Chosen.

**Option 2 — a condition.** Rejected. `Duration` cannot express Sap's boundary, conditions are
not consumed by being used, and p. 90 gives neither of these a name the Rules Glossary tags
`[Condition]`. It would also make Vex visible to every rule that reads conditions.

**Option 3 — retire tokens in a turn phase, as conditions are retired.** Rejected, and this is
the substantive one. See clause 3.

## Decision

**1. A `PendingAdvantage` names its holder, its sign, its scope, and the boundary it dies at.**
One structure for both rules, with `rule_id` recording which sentence granted it so a ruling can
say. Scope is `against_id`: Vex names the creature, Sap names nothing.

**2. Spent, not merely expired.** p. 90 says "your **next** attack roll", so the first roll in
scope consumes the token whether it hits or misses. The spend is emitted from `Proposal.always`
rather than either branch, because a token surviving a miss turns "your next attack roll" into
"every attack until one lands" — a different and much larger rule. Scope and liveness stay
separate questions for the same reason: an out-of-scope attack must not consume a token, while
a dead one must not be honoured, and one predicate answering both would let an attack on a
bystander burn Vex.

**3. Liveness is derived; the sweep is hygiene.** A token carries its boundary and `is_live`
computes whether the encounter has passed it. Two reasons, and the second decided it:

- Sap would otherwise need a **start-of-turn retirement hook the loop does not have**, added to
  serve one property — the shape 0036 clause 6 warns about.
- A derived answer **cannot silently outlive its window**. A missed sweep leaves a dead row in
  state; a missed retirement grants Advantage in a round the document had already ended. Those
  fail in opposite directions and only one of them is visible in play.

`advanced_turn` still sweeps, and it sweeps **against the position it advanced to**. Asking
before the index moves answers about the turn that just ended and leaves every token alive
exactly one turn too long — which is invisible while liveness is what a roll consults, and is
why the sweep is hygiene rather than the rule.

**4. Both reach the same pair of flags as everything else.** A token contributes to
`has_advantage` or `has_disadvantage`, so p. 8's cancellation resolves it against every other
circumstance rather than through a second channel. A creature holding a Sap penalty attacking a
target it has Vex on rolls straight — the document's own answer, and nobody had to write it.

**5. `When` gains a subject rather than a member** (0032 clause 3). Vex's trigger is p. 182's
`DAMAGE_TAKEN` predicate exactly — "unless it avoids taking any damage" and "and deal damage to
the creature" ask the same question — but of a **different creature**: the damage is the
defender's and the benefit is the attacker's. `_holds` read the effect's own `target_id`, so
Vex would have looked for damage the attacker took, found none, and been withheld on every hit
that ever landed.

`Effect.when_subject_id` names whose damage the predicate reads, defaulting to the target,
which is p. 182 unchanged. 0032 clause 3 says the vocabulary grows one printed sentence at a
time; this sentence needed no new member, and finding that out is what showed the *subject* was
missing rather than the predicate. `_refuse_undecidable_conditional` reads the subject too —
without that it would refuse a correct Vex proposal, and it still catches the genuinely
undecidable ones.

**6. A token whose expiring creature has left the encounter stays live.** The boundary it named
can no longer arrive. Withdrawing a granted benefit because its clock left the fight would be
the engine deciding an outcome the document does not decide, so it errs toward honouring what
was granted.

**7. `TurnBoundary` is a vocabulary, not a boolean** (0019). Two mutually exclusive states,
and a `bool` at a call site reads as neither. It lives with the one mechanism that needs both;
`Duration` needs no such thing, because every span it counts ends at `END`.

## Consequences

The inventory moves to **108 of 210**. Weapon masteries are 5 of 8 — Cleave
([#323](https://github.com/eddiefiggie/srd-rules-engine/issues/323)), Slow
([#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)) and Push
([#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324)) remain, the last blocked on
a Size nothing carries ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)).

**The next held modifier is a `PendingAdvantage`.** Several class features and spells grant
Advantage on a *later* roll rather than the current one, and none of them now needs a queue, a
boundary vocabulary, or a turn-loop change.

## Status of implementation

**Every clause is built** by [#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318)
and [#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319).

| Clause | State |
|---|---|
| 1 — one structure, four axes | **Built.** `core.pending_rolls.PendingAdvantage`, granted by `_vex_and_sap` ([#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318), [#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319)) |
| 2 — spent by the roll, hit or miss | **Built.** `advantage_spent` in `Proposal.always`, with scope and liveness asserted apart ([#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318)) |
| 3 — liveness derived, sweep after the advance | **Built.** `is_live` and `EncounterState._swept`, asserted at the tick either side of both boundaries ([#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319)) |
| 4 — the same pair of flags, cancelling by p. 8 | **Built.** Folded into `has_advantage`/`has_disadvantage`, with the cancelling case asserted ([#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318)) |
| 5 — `When` gains a subject | **Built.** `Effect.when_subject_id`, read by `_holds` and by `_refuse_undecidable_conditional` ([#318](https://github.com/eddiefiggie/srd-rules-engine/issues/318)) |
| 6 — a departed clock leaves the token live | **Built.** `is_live` returns True when the expiring creature is not in the order ([#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319)) |
| 7 — `TurnBoundary` is a vocabulary | **Built.** A `StrEnum` with two members ([#319](https://github.com/eddiefiggie/srd-rules-engine/issues/319)) |
