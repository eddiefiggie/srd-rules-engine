# 0069 — The attack path asks what the menu asks

- **Status:** Accepted, 2026-08-30
- **Settles:** [#376](https://github.com/eddiefiggie/srd-rules-engine/issues/376)
- **Requirements:** R1, R18, R31
- **Related:** [0068 — a rule the menu asks and nothing else does](0068-a-rule-the-menu-asks-and-nothing-else-does.md),
  whose guard found these six; [0062 — the menu is not a promise](0062-the-menu-is-not-a-promise.md),
  which is why the resolver asks the rules rather than asking the menu;
  [0043 — one action, several attacks, and one swap](0043-one-action-several-attacks-and-one-swap.md),
  whose roll count this now enforces on both paths

## Context

[0068](0068-a-rule-the-menu-asks-and-nothing-else-does.md) shipped a guard that walks for names
`core.read_surface` uses and nothing else in `core` does. On its first run it found thirteen,
seven of them values the surface publishes and **six of them rules**:

| name | rule | what a direct caller got |
| --- | --- | --- |
| `attacks_remaining` | p. 257, *Multiattack* — how many rolls the Attack action buys | as many attacks as it declared |
| `Multiattack.allows` | which weapons the entry names | an attack the stat block does not grant |
| `has_taken_extra_attack` | p. 89's **one** extra Light attack | a second, and a third |
| `has_cleaved` / `cleave_openings` | p. 90's Cleave, once per turn, onto a hit | a Cleave every turn, out of nowhere |
| `has_fired_loading` | p. 90's Loading | a crossbow fired twice in one action |
| Ammunition, via `can_fire` | p. 89 — "only if you have ammunition to fire from it" | a shot with an empty quiver |

Each was written correctly and asked in one place. `AGENTS.md` already discloses that a
consumer calling adjudication directly gets outcome authority without *skip prevention*; this
was narrower and worse — the rule existed, was computed, and was simply not asked on the path
that produces outcomes.

## Options considered

**Option 1 — the resolver calls `legal_actions` and refuses anything absent from it.** Rejected,
and it is one line, which is exactly why it needs a reason. It makes the menu a **promise**,
which [0062](0062-the-menu-is-not-a-promise.md) refused on its own terms: the menu answers
*what may I do* and the resolver answers *may I do this*. Deriving the second from the first
turns every menu defect into an outcome defect, and couples the two so that neither can be
simplified — and the menu is the larger, more presentational, more frequently edited of them.

**Option 2 — ask each rule directly in the resolver, against the same state.** Chosen. It is
what 0062's own components check does, what 0063's armour-training refusal does, and what 0055
and 0057 did for the Push bound and the righting cost. Four precedents, one answer.

**Option 3 — move the checks out of the menu entirely and refuse only at the resolver.**
Rejected outright. R18 asks for legality to be **computable** rather than checkable afterwards:
an agent has to be able to see what it may do before declaring, or the whole read surface is
advisory. The resolver check is the floor under the menu, not a replacement for it.

## Decision

**1. `_refuse_what_the_menu_would_not_offer` asks all six, before anything else in the
resolver.** Ahead of `_refuse_if_behind_total_cover`, because these are questions about whether
the attack exists at all rather than about where it lands.

**2. It asks the rules, not the menu.** Option 1's reasoning, recorded so that the one-line
version is not reintroduced as a simplification.

**3. An extra attack and a Cleave are not charged against p. 257's roll count.** "as part of"
the Attack action is not "bought by" it (0043). Getting this wrong would quietly cost a
Multiattack creature one of its own rolls, and the failure is invisible — the attack simply
stops being offered a roll early.

**4. Loading is capped per action used, not per turn.** The Bonus Action route is charged
against the Bonus Action and Nick's against the Action it is part of, which is the distinction
[#271](https://github.com/eddiefiggie/srd-rules-engine/issues/271) drew at the menu and this
mirrors.

**5. `can_fire` moved from `core.read_surface` to `EncounterState.can_fire`.** The read surface
is imported *by* the attack resolver and cannot import it back, so a predicate both need lives
where the state does — which is also where [0056](0056-a-move-is-refused-where-it-is-made.md)
put a movement refusal, for the same reason.

**6. Two test fixtures were wrong, and they were wrong in the way this record is about.**
`test_nick.py` and `test_cleave.py` each declared an *ordinary* attack on a state whose Attack
action had already been spent — a declaration the menu would never have offered. Both were
asserting a damage property and neither needed that state; both now read the ordinary swing off
a fresh encounter.

## Why

**Option 1 is the trap.** It is shorter, it covers every rule at once, and it covers future
ones for free. It is also the one change that would make a bug in `legal_actions` produce a
wrong *outcome* rather than a wrong *offer* — and 0062 already decided that the menu is allowed
to be wrong in the safe direction. Writing the rejection down is most of this record's value,
because the next person to notice the duplication will reach for it.

**Clause 6 is evidence rather than housekeeping.** Two tests in the suite were exercising
declarations the rules forbid, and they passed for as long as the rules went unasked. That is
the same defect one level up: a fixture reaching a state play cannot produce. Neither test was
about the rule it violated, which is why nobody noticed.

**The guard closed its own loop.** Six names left
[0068](0068-a-rule-the-menu-asks-and-nothing-else-does.md)'s list, and they left through its
`test_a_name_that_stopped_being_menu_only_leaves_this_list` failing — nobody had to remember to
delete the annotations. That direction was written on the argument that it would matter later;
later was the next day.

## Consequences

**Accepted costs.**

- **Six rules are now asked twice**, and the two call sites can drift. That is the cost Option
  1 avoids and 0062 accepted deliberately; what makes it survivable is that both read the same
  state through the same predicates.
- **The attack resolver refuses more**, and a ruleset driving it directly with hand-built state
  may now hit refusals it did not before. Two of this repository's own tests did, which is the
  best available evidence that the refusals bite.
- **`can_fire` is on `EncounterState`**, which grows again. It is the right home and it is
  still growth.

**Follow-on effects.**

- **[0068](0068-a-rule-the-menu-asks-and-nothing-else-does.md)'s rule list is empty**, and its
  seven `REPORTED` entries remain. The guard now sits over a surface with no known gaps, which
  is the state it should spend most of its life in.
- **Coverage does not move.** Every one of these mechanics was already claimed; what changes is
  where they are enforced ([0061](0061-a-shape-resolves-and-a-clause-may-not.md)).

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 257** (*Multiattack*), **p. 89**
(*Extra Attack*'s one extra, and *Ammunition*), and **p. 90** (*Cleave*, *Nick*, *Loading*).
Every clause is already pinned in `scripts/verify_d20_rules.py` from when the menu built them,
and the suite still verifies 282.

In the tree: thirteen assertions, each proved by corrupting the behaviour it guards, and the
new module goes red against the base tree on **failing assertions** rather than on import —
the six rules genuinely were not asked.

## Status of implementation

**All six clauses are built** by [#376](https://github.com/eddiefiggie/srd-rules-engine/issues/376).

| Clause | State |
|---|---|
| 1 — one refusal function, asked first | **Built.** `core.combat._refuse_what_the_menu_would_not_offer` |
| 2 — it asks the rules, not the menu | **Built**, and the rejected alternative is recorded above |
| 3 — an extra attack and a Cleave are not bought rolls | **Built**, and each has its own test asserting it is *not* refused |
| 4 — Loading is per action used | **Built.** The action kind comes from the route |
| 5 — `can_fire` lives on the state | **Built.** `EncounterState.can_fire` |
| 6 — two fixtures corrected | **Built.** `test_nick.py` and `test_cleave.py`, each with a comment saying why |

_Written 2026-08-30 against SRD v5.2.1._
