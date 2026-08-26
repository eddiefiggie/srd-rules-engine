# 0030 — An unanswerable qualifier resolves in the direction that cannot invent an outcome

- **Status:** Accepted, 2026-08-25
- **Settles:** [#190](https://github.com/eddiefiggie/srd-rules-engine/issues/190)
- **Requirements:** R1, R4, R7, R31, R32 · touches R14
- **Related:** [0029 — whether a wall blocks sight is a property of the wall](0029-whether-a-wall-blocks-sight-is-a-property-of-the-wall.md),
  which made `Visibility.UNSTATED` reachable; [0015 — reactions and the agent seam](0015-reactions-and-the-agent-seam.md),
  whose withholding is one of the two precedents this reconciles;
  [#166](https://github.com/eddiefiggie/srd-rules-engine/issues/166)

## Context

Several SRD rules apply *while* something is true, and this engine sometimes cannot tell whether
it is. `EncounterState.can_see` now returns three values, and the third — `UNSTATED` — is a
report rather than a mechanic. A rule cannot half-apply.

**The project has been answering this question for months and has never written the answer down.**
It has answered it twice, in opposite directions, and both are right:

- **`core.reactions` withholds.** p. 185 provokes an Opportunity Attack against a mover "that you
  can see", and the engine cannot check that clause, so it computes who *would* be provoked and
  offers nothing.
- **`core.conditions` applies.** p. 182 gives Frightened's Disadvantage "while the source of fear
  is within line of sight", and the engine cannot check that clause either, so it applies the
  Disadvantage anyway.

Read as "when in doubt, withhold" the second is wrong. Read as "when in doubt, apply" the first
is. Neither reading is the rule, and the rule has never been stated — it has been re-derived
correctly at each site by whoever was there, which is exactly the thing a record exists to stop.

## Options considered

**"When the qualifier cannot be checked, do not apply the rule."** Rejected: it is the reactions
answer generalised, and generalising it removes Frightened's Disadvantage from a creature the
document penalises, quietly making it better off for standing somewhere the engine cannot see.

**"When the qualifier cannot be checked, apply the rule."** Rejected for the mirror reason: it is
the conditions answer generalised, and generalising it fires Opportunity Attacks the rules may not
grant.

**Refuse to resolve while the answer is `UNSTATED`.** Rejected, and it is the option that looks
most principled. The engine already refuses rather than guessing in several places — but every one
of those refusals is a **read** declining to state a rule value. This one would be an
**adjudication** declining to produce an outcome, and the caller's only recourse is to decide
themselves whether the qualifier held. That is the agent deciding how it turns out, which is the
one thing the product contract does not permit (R1). A refusal here does not avoid the choice; it
relocates it to the party who must not have it.

**Ask the memory port.** Rejected under R20 and 0026 both: whether a creature can see another is
derived from state (0025 clause 4), not a narrative fact, and the port returns typed values rather
than adjudications.

## Decision

**1. An unanswerable qualifier resolves in whichever direction cannot manufacture an outcome.**
Not "apply", not "withhold" — the test is what the wrong answer would *produce*. An engine that
omits an effect the rules required has failed to do something; an engine that produces one the
rules did not grant has invented something that was never in the world. The second is worse, and
it is the only one this project treats as a defect rather than a gap.

**2. Both existing precedents follow from clause 1, which is how it was chosen.** They are not
compromises with it:

| Site | Wrong answer would | So the engine |
|---|---|---|
| Opportunity Attack (p. 185) | roll an attack and deal damage the rules may not grant | **withholds** |
| Frightened (p. 182) | omit a Disadvantage the rules may have required | **applies** |

**3. The test is asked of the outcome, not of the creature.** "Which reading is generous" is the
wrong question and gives the wrong answer for Invisible. p. 184 gives an Invisible creature
Disadvantage on attack rolls against it, "unless a creature can somehow see you" — the *generous*
reading grants the concealment, and it is also the correct one under clause 1, because failing to
apply that Disadvantage makes an attacker hit more often and produces damage that may not exist.
Applying it can only omit a hit.

Generosity and invention point the same way there and opposite ways at the Opportunity Attack.
Only one of them is the rule.

**4. The read surface still reports `UNSTATED`, and only a ruling collapses it.** R32's disclosure
is not satisfied by resolving quietly in the safe direction. `Sight.verdict` keeps all three
values, `Situation` keeps reporting them, and a narrator can see that the engine chose rather than
knew. What clause 1 governs is the single point where a rule has to apply or not.

**5. A clause leaves `unenforced_clauses` when it is enforced, not when it becomes answerable.**
`can_see` answering more questions does not shrink that list on its own. The list is the honest
account of what the engine does not do, and moving an entry out of it while the behaviour is
unchanged would make the one instrument that measures this engine's own gaps report progress that
did not happen.

## Why

**The rule was already being followed; what was missing was its name.** Two sites, opposite
behaviour, both correct, no shared reason written down. The next site would have been decided by
whichever precedent its author happened to read first — and both were reachable.

**Clause 3 is the part that would have gone wrong.** "Withhold when unsure" and "be generous to
the creature" are the two summaries a reader invents from the precedents, and Invisible breaks
both. Only "do not manufacture an outcome" survives all three sites.

**Clause 4 keeps the record honest about what this is.** Clause 1 is a tie-breaker for a question
the document leaves open, not a claim about what the SRD says. The disclosure is what separates
those.

## Consequences

**Accepted costs.**

- **The engine will sometimes penalise a creature the rules would have spared.** Frightened's
  Disadvantage applies where the source of fear may be out of sight. That is the cost of clause 1
  and it is chosen, not overlooked.
- **`UNSTATED` becomes invisible at the point of application**, which is the price of clause 4
  bounding it to that point. A consumer wanting to know whether a ruling rested on a guess reads
  the situation, not the Ruling.

**Follow-on effects.**

- **Nothing in this record is implementable yet, and the reason is new.** Frightened's qualifier
  needs the **source of fear** stored, and it is not — `grappler_id` is the only source this
  engine tracks, for the only other conditional clause it enforces. Filed as
  [#192](https://github.com/eddiefiggie/srd-rules-engine/issues/192).
- Invisible's exception needs the condition surface to take creature ids and state rather than
  positions, so it can ask `can_see`. Filed as
  [#193](https://github.com/eddiefiggie/srd-rules-engine/issues/193).
- Coverage is unchanged at **81 of 211**. A record resolves no shape.

## Evidence

No spike. Both precedents are in the tree and were read rather than recalled:

- `core/reactions.py`: `withheld` defaults to `SIGHT_QUALIFIER`, and the module docstring says it
  "computes what *would* provoke and **withholds every offer**".
- `core/conditions.py`: `Condition.FRIGHTENED` carries `own_attack_rolls=DISADVANTAGE` with
  `line-of-sight-qualifier` among its `unenforced_clauses` — applied, and disclosed as applied
  without the qualifier.
- `Conditions.grappler_id`, the one source of a condition this engine stores, which is what makes
  Grappled's "any target other than the grappler" enforceable and Frightened's qualifier not.
- p. 184's Invisible entry, whose "unless a creature can somehow see you" is the third case that
  rules out both simpler summaries.

## Status of implementation

**Decided, not built**, and clause 5 is why the count does not move: `can_see` became more
answerable in 0029 without any clause becoming enforced.

| Clause | State |
|---|---|
| 1 — resolve away from invention | Not built as a mechanism, and it is not one. It is the rule the next author applies; the two sites that already follow it were written before it had a name |
| 2 — both precedents follow | Already true in the tree. `core.reactions` withholds, `core.conditions` applies, and neither changes |
| 3 — the test is asked of the outcome | Nothing to build; it is how clause 1 is applied |
| 4 — the read surface still reports `UNSTATED` | Already true. `Sight.verdict` has three values and `Situation` reports them |
| 5 — a clause leaves `unenforced_clauses` when enforced | Already true, and now stated so that a future PR does not empty the list to look finished |

The three sight-blocked entries stay in `unenforced_clauses`:
[#192](https://github.com/eddiefiggie/srd-rules-engine/issues/192) and
[#193](https://github.com/eddiefiggie/srd-rules-engine/issues/193) are what would move them.
