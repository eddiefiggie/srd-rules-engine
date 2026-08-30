# 0068 — A rule the menu asks and nothing else does

- **Status:** Accepted, 2026-08-30
- **Settles:** [#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365)
- **Requirements:** R1, R17, R18, R32
- **Related:** [0062 — the menu is not a promise](0062-the-menu-is-not-a-promise.md), at the end
  of which #365 was filed; [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which is why the guard is not keyed on resolvers;
  [0058 — a field nothing reads is a rule modelled and not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md),
  which is the same defect one step earlier

## Context

Four times in one session a rule turned out to be computed once, consumed by `legal_actions`,
and absent from the path that produces outcomes: p. 90's Push bound, p. 182's escape DC,
p. 186's righting cost, p. 105's components and p. 104's preparation. **Every one was found by
a person** — writing a test, or reading a neighbouring function while fixing something else.

R18 asks for legality to be *computable* rather than checkable afterwards, so the menu check is
right and stays. The second call site is the floor under it, and nothing looked for its absence.

#365 named the difficulty honestly: those four look nothing alike — a helper returning a
refusal string, a set membership, a bound on a number carried by the declaration, a state
precondition — so a guard cannot walk for a *shape* the way
[#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334)'s and
[#356](https://github.com/eddiefiggie/srd-rules-engine/issues/356)'s do.

## Options considered

**Option 1 — key the walk on resolver modules.** Rejected, and it was tried first. "Every name
the read surface uses that no resolver calls" reported **27** names and was wrong about most of
them, because the enforcement this repository wants is frequently in a **state transition**
rather than in a resolver: [0056](0056-a-move-is-refused-where-it-is-made.md) put a movement
refusal in `with_movement` precisely because that is where a move is made, and 0067 put a Speed
cap in `effective_speeds`. A guard keyed on resolvers calls those unenforced, which is false.

**Option 2 — require offer predicates to be named and registered.** Rejected for this change,
though #365 was right that it would have caught all four. It changes how the whole read surface
is written, and a large rewrite is a poor vehicle for a guard whose value is that it runs from
now on. Left as the option to revisit if the annotated list becomes unreadable.

**Option 3 — write it into `AGENTS.md` as a review step.** Rejected as the weakest, for #365's
own reason: all four gaps were added by someone who knew the rule.

**Option 4 — walk for names the read surface uses that nothing else in `core` uses.** Chosen.
It is the honest formulation of "computed once, for the menu": not "the resolver does not ask
it" but *nothing* asks it, anywhere the engine produces an outcome or changes state. It
reports **13** names, which is a list a person reads once.

## Decision

**1. The guard compares two derived sets and is keyed on nothing but usage.** Every name
`core.read_surface` calls or reads that is defined somewhere in `core` and used nowhere else in
`core`.

**2. Attributes as well as calls.** Half the gates in question are properties —
`actor.weapons_held`, `actor.attacks_remaining` — and a walk over `ast.Call` alone would miss
them entirely, which is the exact shape this file is about.

**3. Every name the walk finds carries a verdict a person wrote.** The walk cannot tell a rule
from a value: `movement_remaining` and `attacks_remaining` are the same shape and only one of
them decides anything. So the list is annotated, and an entry is either `REPORTED:` — the
surface publishes it and it gates nothing — or an issue number for a rule the outcome path does
not ask. A third state, "it is fine", is refused by a format check.

**4. Both directions are pinned.** A **new** name is a menu gate somebody added without a
second call site. A **vanished** name is a gate that was wired up or deleted, and its
annotation is now false — which is what `unenforced_clauses`'s pin exists to prevent for
disclosures ([#292](https://github.com/eddiefiggie/srd-rules-engine/issues/292)), in the same
shape.

**5. The guard ships with six unfixed entries, and that is the deliverable.** Its first run
found that `attacks_remaining`, `has_taken_extra_attack`, `has_cleaved`, `cleave_openings`,
`has_fired_loading`, `ammunition_for` and `Multiattack.allows` are asked by the menu and by
nothing else — p. 89's Extra Attack limit and Cleave, p. 90's Loading and Ammunition, and a
stat block's Multiattack. All on the attack path, filed together as
[#376](https://github.com/eddiefiggie/srd-rules-engine/issues/376). Fixing them is a
behavioural change to combat and is not this change.

**6. This is a deliberate "nothing changed" guard.** It passes against the base tree, because
it pins a property of code this record does not alter. `scripts/prove_against_base.sh` names
that as its one exception, and the four corruption proofs are what establish the walk inspects
something.

## Why

**Option 1 failing is the useful part of this record.** "Compare the menu against the
resolvers" is the obvious formulation, it is what #365 suggested first, and it is wrong for a
reason specific to this engine: outcomes are produced by resolvers *and* by state transitions,
and 0056 chose the latter deliberately. A guard built on the obvious formulation would have
flagged `with_movement`'s refusals as missing and buried the six real findings under twenty-one
false ones — the failure mode that gets a guard deleted rather than fixed.

**Clause 3 is what makes the noise survivable.** #365 predicted it: "the noise is a list a
person can read once and annotate." Thirteen entries with a sentence each is a page. What
matters is that the *set* is derived, so the annotations cannot silently fall behind the code;
only the verdicts are hand-written, and a wrong verdict is a claim somebody made rather than an
omission nobody noticed.

**The format check earned itself immediately.** The first draft annotated `Multiattack.allows`
as "REPORTED for now, and the weakest entry here" — an author hedging on a rule he had just
established nothing enforces. Clause 3's check refused it, and the entry moved to #376 where it
belonged. A guard that catches its own author fence-sitting on the day it is written is worth
more than the six findings.

**Clause 5 is the honest shape and should not be softened.** A guard whose allowlist is empty
on the day it ships is a guard nobody has seen find anything. This one ships red-in-substance
and green-in-form: the gaps are named, each cites an issue, and the failure mode it prevents —
a *seventh* one arriving unnoticed — is closed from today.

## Consequences

**Accepted costs.**

- **A hand-written verdict per name.** Thirteen today. If it reaches a size nobody reads,
  Option 2's registry is the answer and this record says so.
- **The walk is name-based and therefore approximate.** Two different things sharing a method
  name are one entry, and a name read inside its own definition keeps itself off the list —
  `Conditions.cannot_act` is the example, since the property reads `e.cannot_act` on each
  effect. Both directions fail *safe* in the noisy direction rather than the silent one, except
  that last case, which is a known blind spot and is named here rather than left to be found.
- **It runs over source, not behaviour.** A rule asked in dead code counts as asked.

**Follow-on effects.**

- **[#376](https://github.com/eddiefiggie/srd-rules-engine/issues/376) is new and is the
  guard's first catch** — six attack-legality rules a direct caller escapes today.
- **[#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365) closes with this
  record**, and its Option 2 is preserved above rather than lost with the issue.
- **Coverage does not move.** No mechanic ships here.

## Evidence

In the tree: the four fixed gaps are cited in #365 with the records that fixed them
([0055](0055-a-creature-moved-by-something-other-than-itself.md),
[0052](0052-the-exit-is-built-before-the-entrance.md),
[0057](0057-prone-crawls-or-stands.md), [0062](0062-the-menu-is-not-a-promise.md)). The
resolver-keyed formulation reports 27 names against the 13 this one reports, and the
difference is `with_movement`, `effective_speeds`, `ActionBudget.spend` and
`SpellSlots.can_cast` — every one of them a place an outcome is actually produced.

Four corruption proofs, one per direction the guard can fail: a new menu-only name in the
source, a name gaining a second call site, a deleted annotation, and a verdict that says
neither. Plus the canary, which is the failure a derived guard is most exposed to — a walk that
matches nothing pins an empty set and passes forever, looking like a clean bill of health.

## Status of implementation

**All six clauses are built** by [#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365), in `tests/test_menu_gates_are_asked_elsewhere.py`.

| Clause | State |
|---|---|
| 1 — the walk is keyed on usage across all of `core` | **Built.** `menu_only_names()` |
| 2 — attributes as well as calls | **Built**, and it is why the six properties are found |
| 3 — every name carries a verdict, and "it is fine" is refused | **Built.** `test_each_verdict_is_a_published_value_or_a_filed_issue` |
| 4 — both directions pinned | **Built.** Two tests, and each has its own corruption proof |
| 5 — six findings shipped as filed rather than fixed | **Built as filed.** [#376](https://github.com/eddiefiggie/srd-rules-engine/issues/376) holds them |
| 6 — a deliberate "nothing changed" guard | **Built**, and stated here because `prove_against_base.sh` requires it to be said |

_Written 2026-08-30 against SRD v5.2.1._
