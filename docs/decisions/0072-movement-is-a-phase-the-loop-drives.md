# 0072 — Movement is a phase the loop drives

- **Status:** Accepted, 2026-08-30
- **Settles:** the architectural half of [#382](https://github.com/eddiefiggie/srd-rules-engine/issues/382)
- **Requirements:** R1, R4, R8, R12, R18, R32
- **Related:** [0015 — the generator seam already serves reactions](0015-reactions-and-the-agent-seam.md),
  whose conclusion holds and whose assumption about *where* the trigger fires does not;
  [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which put movement rules in `with_movement` and is the reason the attack cannot go there;
  [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  the shape this copies;
  [0071 — a blocker that closed](0071-a-blocker-that-closed-and-a-disclosure-that-did-not-notice.md),
  which made the offer possible by making the sight clause answerable

## Context

[0015](0015-reactions-and-the-agent-seam.md) answered #16's warning that reactions might force
a redesign of the agent seam. The answer was no, and it still is:

> `TurnLoop.run` is `Generator[Request, Response, TurnOutcome]` and `DeclarationRequest`
> carries its own `actor_id`. … Yielding one for a different creature, part-way through
> resolving another creature's action, is the same operation the loop already performs.

That is verified rather than assumed now. `_concentration_saves` drives **another creature's**
roll mid-turn, through `Adjudicator.adjudicate`, and has since #215. The seam holds.

**What 0015 got wrong was where the trigger fires.** It said trigger detection "belongs where
movement resolves, not in the action economy", which is right, and then took for granted that
the loop would be there when it did. It is not:

```
$ grep -rn "with_movement(" src/srd_rules_engine/
src/srd_rules_engine/core/state.py:2886:    def with_movement(
```

**Voluntary movement has no caller in the engine.** It is a state transition a consumer makes
directly, and the turn loop never sees it. `MOVED_BY_FORCE` and `MOVEMENT_SPENT` are
adjudicated effects; ordinary travel is not one, and [0056](0056-a-move-is-refused-where-it-is-made.md)
deliberately put movement's *rules* in the state method rather than in adjudication.

So there was no seam between "the mover leaves reach" and "a driver is asked whether it
reacts", and nothing in 0015 said so, because in 2026-08-23 there was no movement to drive.

## The constraint that decides it

An Opportunity Attack cannot be resolved inside `with_movement`.

[0056](0056-a-move-is-refused-where-it-is-made.md) clause 1 permits movement *rules* there on a
precise argument:

> R1 says no other API "produces, modifies, or implies a **result**". A refusal produces no
> result; it is the absence of one.

An attack is the opposite of a refusal. It rolls dice, it deals damage, it produces a `Ruling`.
Putting it in a state method is exactly the second adjudication path R1 exists to forbid — and
`with_movement` is a pure function of state that cannot yield to a driver in any case, so it
could not make the offer even if R1 allowed the outcome.

## Decision

1. **`TurnLoop.move` is a phase**, alongside `start_turn`, `run` and `end_turn`. It takes what
   `with_movement` takes, and returns the moved state:

   ```
   move(state, mover_id, to, *, mode, difficult_terrain, carrying)
       -> Generator[Request, Response, MoveOutcome]
   ```

   Nothing here creates a second path to an outcome. It creates another **occasion** on which
   the existing path is taken — 0023's sentence, and the fourth time it has been the answer.

2. **The attack resolves before the movement is applied.** This is not a reading of p. 185's
   silence about ordering; it is the only order in which the attack exists. Provoking *means*
   the mover was inside the reactor's reach at the origin and is outside it at the
   destination — so at the destination a melee attack cannot reach, and p. 185 grants a melee
   attack. Resolving after would offer an attack the geometry forbids.

3. **A dropped mover stops, and building this found the rule missing.** The engine states no
   rule about interrupting movement and **must not invent one** — the SRD text asserted for
   p. 185 says only *"You can make an Opportunity Attack when a creature that you can see
   leaves your reach … take a Reaction to make one melee attack"*, and says nothing about
   interruption. What stops the move is a refusal, not an interruption.

   **This clause first said the refusal was already built, and it was not.** The claim was
   that a mover reduced to 0 is Unconscious and therefore Prone, and that `with_movement`
   already refuses a non-crawl move by a Prone creature (p. 186). The first step does not
   happen: **nothing in this engine applies Unconscious at 0 hit points.** A probe written to
   confirm the clause showed a creature dropped to 0 walking twenty feet, and the record was
   wrong before any of it shipped.

   What is built is `Combatant.is_down` — *"at 0 hit points a combatant stops acting"* — which
   `legal_actions` has enforced since the read surface shipped, and which **`with_movement`
   never asked**. That is [0058](0058-a-field-nothing-reads-is-a-rule-not-applied.md)'s shape:
   a rule modelled in one place and not applied in another. So the refusal is added here, on
   0056 clause 1's licence, and it is the engine's own doctrine reaching one more caller
   rather than a rule read off a document this repository does not hold.

   The pre-existing defect is worth naming separately: **before this change, any caller could
   move a creature at 0 hit points.** An Opportunity Attack is only what made it visible.

4. **The offer is a request the driver may decline, not an obligation.** `_obligation_declaration`
   authors a `Declaration` on the engine's behalf because p. 63 *compels* a save; nobody is
   choosing. p. 185 says "**can** make", so the reactor chooses, and the declaration is the
   agent's — which is what a `Declaration` is for (R2). Hence a new request/response pair
   rather than a reused `DeclarationRequest`: the reactor is not taking a turn, and the thing
   it is being offered is one specific attack rather than a menu.

5. **`read_surface.reaction_options` is where that offer is enumerated.** R18 has one
   derivation of what is legal, shared with adjudication. `legal_actions` returns `()` for a
   creature that is not active, and **correctly** — those are the actions of a turn. A reaction
   is legal precisely when it is not your turn, so it is a second entry point on the same
   surface rather than a loosening of the first.

6. **A consumer calling `EncounterState.with_movement` directly still provokes nothing**, and
   that ships disclosed. It is the limit `AGENTS.md` already states for skips — *"the skip
   guarantee holds only for callers the turn loop drives"* — appearing a second time for the
   same structural reason, and it is the honest cost of movement remaining a state method.

7. **The report's attribution is not settled here.** A reaction's entries land inside another
   creature's turn, and `core.report._turns` groups them by position in the sequence.
   [#120](https://github.com/eddiefiggie/srd-rules-engine/issues/120) holds it, has held it
   since 0015 deferred it, and already has a live source in 0023's end-of-turn obligations.
   This change adds a second instance of an existing defect rather than a new class of one, and
   does not pretend otherwise.

## Why

### The alternative — adjudicating movement — was considered and is worse

Making travel an `EffectKind` would put the trigger inside the adjudication path and need no
new phase. It would also move every rule [0056](0056-a-move-is-refused-where-it-is-made.md) put
in `with_movement` — the cost check, the mode check, Prone's two options, Frightened's Can't
Approach — into effect application, four builds after that record argued they belong at the
transition. The reason they belong there has not changed: they are refusals, and a refusal is
not a result.

More practically, it would make every move an agent declaration. Movement is not a declaration
today; a creature moves and the engine charges it. Turning travel into a rule the agent names
would enlarge the surface the agent is accountable for, in the direction the Product Contract
spends its effort narrowing.

### A phase is the shape this engine already reaches for

Four occasions now produce rulings outside a declaration: the turn's start, the turn's end,
the Concentration discharge, and this. Each was the same finding — a rule the document states
plainly, with no moment in the loop at which it could happen. 0023 put it best, and the
sentence has been reused twice since:

> nothing here creates a second path to an outcome; it creates another occasion on which the
> existing path is taken.

The recurrence is worth noticing rather than treating each as a surprise. **A rule whose
trigger is not a declaration needs an occasion**, and the loop is where occasions live.

### Why the ordering clause is not an inferred rule value

R31 forbids supplying a rule the document does not state, and p. 185 does not state whether the
attack precedes the movement. Clause 2 does not decide that question — it observes that only one
of the two answers is *expressible*. The reactor's reach is what defines provoking; a melee
attack at the destination has no target in reach. So the ordering is fixed by geometry the
engine already computes, not by a rule it has chosen.

The same distinction keeps clause 3 honest. The engine states no rule about interrupting
movement. It applies the attack, then applies the move, and the move is refused *if some other
built rule refuses it*. A reader who wants to know whether the SRD interrupts movement will
find that question open, not silently answered.

## Consequences

- **Movement gains two callers rather than one.** `TurnLoop.move` for callers who want the
  rules the loop enforces, and `EncounterState.with_movement` for those who do not. The second
  is disclosed as the lesser path rather than removed, because a state method the loop wraps is
  the same arrangement `advanced_turn` and `end_turn` already have.
- **`opportunity-attack-detected-but-never-offered` retires** in the change that builds the
  offer, and the two are asserted together.
- **The `opportunity-attacks` shape becomes claimable**, which it has not been since the
  inventory shipped. A trigger that nothing called had not resolved it; an offer that fires does.
- **#120 becomes harder to leave alone.** It had one source and now has two, and the second is
  the one 0015 predicted would bite.

## Status of implementation

| Clause | State |
|---|---|
| 1 — `TurnLoop.move` as a phase | **Built.** `loop/turn.py` |
| 2 — the attack resolves before the move | **Built.** Proved by applying the move first and watching the drop case go red |
| 3 — a dropped mover stops via an `is_down` refusal | **Built**, and the clause changed while being built — see its correction above. The refusal is new in `EncounterState.with_movement` |
| 4 — an offer the driver may decline, not an obligation | **Built.** `ReactionRequest` / `ReactionDeclined` |
| 5 — `read_surface.reaction_options`, and the key that selects it | **Built.** `reaction_options`, `opportunity_attack_key`, and `offered_actions` for the legality gate |
| 6 — the direct-`with_movement` limit disclosed | **Built** as prose here and in `core.reactions`, and pinned by `test_a_direct_state_move_provokes_nothing` |
| 7 — report attribution left where it is | **Not built.** [#120](https://github.com/eddiefiggie/srd-rules-engine/issues/120) |

`opportunity-attack-detected-but-never-offered` is **retired**, in the change that built the
offer and asserted beside it. It was the second of two names for one gap: its predecessor
named sight and went one build earlier ([#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381)), which is why the pin's comment now
records both removals rather than a single swap.

The `opportunity-attacks` shape is **claimed**, six days after the trigger shipped. It stayed
`False` deliberately in between: a detection with no production caller is machinery, and R17's
inventory is what makes "full SRD 5.2 coverage" falsifiable. `ENGINE_SHAPES` names
`loop.turn.TurnLoop.move` rather than a `core` symbol, which is the honest address given
clause 6.

### Evidence

Nine corruption proofs, each red on the assertion written for it. `prove_against_base.sh`
cannot discriminate here — `tests/test_opportunity_attack_offer.py` is a new module and fails
on *import* against the base tree, which `AGENTS.md` says proves nothing about any individual
assertion.

| Corruption | Went red on |
|---|---|
| `ActionKind.REACTION` → `ActionKind.ACTION` | `test_the_attack_spends_the_reaction_and_not_the_action` |
| the `is_opportunity` exemption from p. 257's cap disabled | `test_a_reactor_that_already_attacked_this_turn_is_still_charged` |
| the `is_down` refusal disabled | `test_a_mover_dropped_by_the_attack_does_not_move`, `test_a_creature_at_zero_hit_points_cannot_be_moved_at_all` |
| the move applied **before** the offers | `test_a_mover_dropped_by_the_attack_does_not_move` |
| a withheld provocation offered anyway | `test_an_unstated_view_is_reported_as_withheld_rather_than_offered` |
| the melee filter disabled | `test_a_ranged_weapon_is_not_offered_and_the_unarmed_strike_still_is` |
| `ReactionDeclined` ignored | `test_a_declined_reaction_spends_nothing_and_the_move_still_happens` |
| `offered_actions` routed back to `legal_actions` | `test_a_taken_reaction_is_adjudicated_and_the_move_still_happens` |
| the retired disclosure re-appended | `test_the_read_surface_no_longer_discloses_an_offer_that_is_never_made` |

**One assertion has no corruption proof, and it is named rather than counted.**
`test_a_direct_state_move_provokes_nothing` pins an *absence* — that `with_movement` does not
reach the loop — and there is no edit to the source that makes a state method acquire an agent
seam. What it guards against is somebody later wiring the offer into the state method and
leaving clause 6's disclosure standing; that is a review question, and the test is where it
gets asked.
