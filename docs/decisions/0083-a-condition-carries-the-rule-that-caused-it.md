# 0083 — A condition carries the rule that caused it

- **Status:** Accepted, 2026-08-31
- **Settles:** [#428](https://github.com/eddiefiggie/srd-rules-engine/issues/428)
- **Requirements:** R1, R14, R17, R19, R31, R32
- **Related:** [0028 — an Exhaustion level carries its cause](0028-an-exhaustion-level-carries-its-cause.md),
  which answered this question for the one condition the document makes cumulative, and whose
  rule-id-rather-than-enum reasoning this reuses wholesale;
  [0019 — data over branches](0019-data-over-branches.md), for why the cause is a string;
  [#192](https://github.com/eddiefiggie/srd-rules-engine/issues/192), which added `sources` —
  the same shape answering *who* rather than *which rule*

## Context

p. 184's Knocking Out a Creature ends with two ways out:

> The creature remains Unconscious **until it regains any Hit Points or until someone uses an
> action to administer first aid** to it, which requires a successful DC 10 Wisdom (Medicine)
> check.

p. 191's Unconscious entry states the condition's **effects** — Inert, Speed 0, Attacks
Affected, Saving Throws Affected, Automatic Critical Hits, Unaware — and **never says when it
ends**. So the ending is not a fact about the condition. It is a fact about whatever applied
it, and different applications end differently.

`Conditions.applied` was a bare `frozenset[Condition]`. A creature knocked out by p. 184 and a
creature Unconscious for any other reason were the same state, so honouring p. 184's first
ending would have woken a sleeper with a cure wound.

## Options considered

**Option 1 — end Unconscious on any healing.** Rejected, and it is what an implementation
does by default. p. 184's ending is stated *by p. 184*, and applying it to every Unconscious
imports a rule the document gives to one case. It is also invisible: the wrong behaviour looks
exactly like the right one until something else applies the condition.

**Option 2 — a separate `knocked_out: bool`.** Rejected. It is the third field-per-condition
in a class that already refused that shape once — `sources` is a mapping *because* two of the
fifteen needed one and a field each is what arrives one PR at a time (#192). A second rule
needing its cause would add a fourth.

**Option 3 — an enum of causes.** Rejected for 0028's reason, unchanged: nothing suggests the
document's list of things that apply a condition is closed, and a closed set in the data is a
branch in every consumer (0019).

**Option 4 — a mapping of condition to the rule ids that caused it.** Taken.

## Decision

**1. `Conditions.causes: Mapping[Condition, frozenset[str]]`.** Which rule caused each applied
condition, as rule ids.

**2. Distinct from `sources`, which stays.** They answer different questions and both are
needed: p. 182's Grappled turns on *who* is grappling ("any target other than the grappler"),
and p. 184's Unconscious turns on *which rule* put the creature there. Neither can be derived
from the other.

**3. A set per condition, because a condition is binary and its causes are not.** p. 179: "A
condition doesn't stack with itself; a recipient either has a condition or doesn't." A creature
knocked out *and* put to sleep holds one Unconscious with two causes, and it ends only when
neither still holds. This is `sources`' reasoning and it arrives at the same shape.

**4. Keyed by `applied`, never by `held`.** An implied condition has no cause of its own:
p. 184's Unconscious implies Incapacitated and Prone, and neither of those is
knocked-out-ness. `durations` is keyed the same way for the same reason, and `__post_init__`
refuses a cause naming a condition nobody applied.

**5. An empty cause set is refused.** "Caused by nothing" is not a state — it is an entry that
should be absent, and a set that empties takes its key with it.

**6. `ended_where_caused_by` removes the cause, and the condition only if it was the last
one.** The arithmetic clause 3 exists for. An implementation that ended the condition outright
would wake a sleeper with a bandage.

**7. `without` keeps causes for what survives rather than dropping what ended.** p. 191
re-applies Prone on its own behalf when Unconscious ends — "When this condition ends, you
remain Prone" — and that Prone was not caused by whatever caused the Unconscious. Carrying the
cause across would say it was.

**8. p. 184's two endings are built, and `knocking-out-a-creature` is claimed.** Healing ends
the Unconscious p. 184 caused; `core.turn_actions.first_aid_resolver` is the other, an Action
and a **DC 10 Wisdom (Medicine)** check. That DC is the document's, unlike p. 187's Search and
p. 189's Study which leave theirs to the caller — so none may be supplied here. Medicine is
named outright rather than suggested, so there is no skill parameter either.

## Why

**The document told us the shape.** p. 191 not saying when Unconscious ends is not an omission
to work around; it is the rule. A condition's ending belongs to its cause, and a structure that
cannot name the cause cannot express the rule.

**0028 had already found this and stopped at one condition.** Exhaustion carries the rule that
caused each level so that a Long Rest takes an unlocked one and leaves dehydration's. That is
the same question, and it was answered for the one condition the document makes cumulative
because that is where it first bit. This generalises it rather than inventing it.

## Consequences

- `Conditions` gains a fifth field. It is the type whose completeness is a checked claim, and
  the count of conditions is untouched: 15 of 15, and causes are a property of an application
  rather than a member of the set.
- Coverage moves to **134 of 210**.
- Anything that ends a condition can now be scoped to the rule that applied it. Nothing but
  p. 184 does today, and that is the honest state — a general capability with one consumer,
  named rather than presented as broader.
- `EffectKind.FIRST_AID_GIVEN` exists so a ruling can say *which* Unconscious it ends. A plain
  `CONDITION_ENDED` cannot.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `causes`, keyed by condition | **Built** |
| 2 — distinct from `sources` | **Built**, and both are populated by `with_condition` |
| 3 — a set per condition | **Built**, and asserted over a doubly-Unconscious creature |
| 4 — applied, never implied | **Built**, and `__post_init__` refuses otherwise |
| 5 — an empty set is refused | **Built** |
| 6 — `ended_where_caused_by` | **Built** |
| 7 — `without` keeps rather than drops | **Built**, asserted through p. 191's surviving Prone |
| 8 — p. 184's two endings | **Built.** `with_healing`, and `first_aid_resolver` |

### Evidence

Six corruption proofs, each red on the assertion written for it. Two clauses of p. 184 in
`scripts/verify_d20_rules.py`, including the recovery sentence this record is about.
