# 0071 — A blocker that closed, and a disclosure that did not notice

- **Status:** Accepted, 2026-08-30
- **Settles:** [#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381)
- **Requirements:** R12, R18, R31, R32
- **Related:** [0060 — a disclosure can be wrong about why](0060-a-disclosure-can-be-wrong-about-why.md),
  which found the same shape in three condition disclosures;
  [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which found it in Frightened's;
  [0015 — reactions and the agent seam](0015-reactions-and-the-agent-seam.md), whose Status
  table carried the lapsed blocker;
  [0025 — sight is a relation over stored state](0025-sight-is-a-relation-over-stored-state.md),
  whose `UNSTATED` is what keeps the withholding from disappearing entirely

## Context

`core.reactions.provocations` computes who an Opportunity Attack provokes. Every result came
back withheld, on p. 185's one clause the engine could not answer — *"a creature that you can
see"* — naming [#150](https://github.com/eddiefiggie/srd-rules-engine/issues/150), the issue
that would read the nine sight pages.

**#150 closed on 2026-08-25.** `core.sight` has answered ever since, and says so in its own
docstring: *"The chain 0025 clause 4 described, now that #150 has read it."* The withholding
stayed for five days and four builds, and with it:

- four prose claims in live source that sight was unanswerable, one of them in the module
  whose table it said was empty;
- 0015's Status row, saying the same and citing the closed issue;
- a read-surface disclosure, `opportunity-attack-requires-seeing-the-mover`, naming sight as
  the reason no reaction is ever offered;
- `tests/test_reactions.py`, asserting that every offer is withheld — so the suite **defended**
  the staleness rather than catching it.

The subsystem was reachable from tests only. `provocations` and `may_be_offered` had no
production caller, and `with_movement` deliberately did not call the detection because *"a
detection that always withholds would add a step to every move to produce nothing."*

## Decision

1. **`provocations` consults `EncounterState.can_see` per reactor**, and `Visibility`'s three
   verdicts are three results rather than two:

   | Verdict | Result | Why |
   |---|---|---|
   | `CAN_SEE` | offerable, `withheld is None` | every clause of p. 185 is answered |
   | `CANNOT_SEE` | **no provocation at all** | p. 185 grants the attack *when* you can see; a reactor who cannot was never owed one, so this is an absence rather than a withheld offer |
   | `UNSTATED` | withheld, naming `SIGHT_UNSTATED` | the document states no answer for this pair (0025, 0029). "The SRD does not say" must not become a no |

2. **The withholding narrows rather than disappears.** It was a fact about the engine; it is
   now a fact about one pair of creatures in one encounter. An encounter that states no light
   is exactly that case — `Lighting.ambient` of `None` means nobody has said, and this engine
   does not assume daylight (0025 clause 2), so the common fixture still yields no offer.

3. **`withheld` loses its default.** It defaulted to the withholding clause, which was
   fail-safe while the answer was constant and is a silent answer now that it is computed.
   The fail-open direction invents an attack out of nothing; the fail-closed direction hides
   one that should be offered. Requiring the field removes the question instead of choosing
   an answer to it.

4. **The disclosure is renamed for what is actually missing**:
   `opportunity-attack-detected-but-never-offered`. The engine can now tell *when* p. 185
   provokes, and nothing calls the detection — no offer, no Reaction spent, no attack
   adjudicated out of turn. Swapped in `tests/test_disclosures_are_pinned.py` in the same
   change, per `AGENTS.md`.

5. **The offer itself stays unbuilt and stays tracked**, by
   [#382](https://github.com/eddiefiggie/srd-rules-engine/issues/382) — filed as part of this change rather than left to #381's closure, because
   a closed issue over absent work reads as finished work. It is now *provable*, which it was
   not: 0015 filed it as "unprovable until an offer can be made."

## Why

### A disclosure keyed on a reason goes quiet when the reason lapses

This is the third instance in six builds. 0056 found Frightened's disclosure saying the clause
needed a direction when it needed two distances; 0060 found two of three condition disclosures
misdiagnosed, one naming a rule that had been built in a second module. Both were *wrong about
why* while being right that something was missing.

This one adds a mechanism the other two did not have. Frightened's and Blinded's were wrong
when written. **This one was correct when written** and was made wrong by another change
landing — the disclosure names an issue, the issue closes, and nothing connects the two. That
failure mode does not need an author to make a mistake, which is why it survived four builds
and a green suite.

The correction is to name the *gap* rather than the *blocker*: `detected-but-never-offered` is
a claim about this engine that stays true or false on its own terms, and does not quietly
become false when someone else's work merges.

### Why no guard caught it, and why that is a third direction

`AGENTS.md` names two directions and machine-checks one. `scripts/check_status_rows.py` fails
a table row claiming `not built` while the issue it cites is **closed** — the state the
document calls worse than unfiled. The mirror — an *open* issue over work that shipped — is
explicitly left to a person.

0015's row was neither. It said **Built**, and carried the lapsed blocker in its prose. The
guard read the claim, found it did not say `not built`, and passed. It reported `ok` on this
tree on the day the staleness was found.

So: **a resolved blocker still cited as live**. It is the most durable of the three, because
it reads as a deliberate limit. A reader meeting *"sight is unanswerable until #150"* has no
reason to check #150 — the sentence explains itself, and explains the withheld offer beside
it. The two directions `AGENTS.md` names both look like absences; this one looks like a
decision.

No guard is proposed here. The check would be "does any prose cite a closed issue as a present
blocker", and the corpus is full of correct past-tense citations of closed issues — *"was X
until #258"* is the house style and there are more than thirty of them. Separating a live
citation from a historical one is a reading, not a match. What is done instead is narrower and
holds: the sight clause is 0015's own row, so it is checkable separately from the offer, and
the disclosure no longer names an issue at all.

### `CANNOT_SEE` drops rather than withholds

Both are "no attack", and they are different claims. Withheld means *this engine cannot say*;
absent means *the rule does not grant one*. Collapsing them would make the withheld count
meaningless as a measure of what the engine cannot answer, and would report a gap where p. 185
gave a plain answer. `core.sight` draws exactly this line and 0025 records why — which is what
makes `UNSTATED` a third value rather than a stub.

## Status of implementation

| Clause | State |
|---|---|
| 1 — `provocations` consults `can_see`, three verdicts | **Built.** `core/reactions.py` |
| 2 — the withholding narrows to a pair | **Built.** `SIGHT_UNSTATED` on the `Provocation` |
| 3 — `withheld` has no default | **Built.** Proved by corrupting the field back to a default |
| 4 — the disclosure names the offer | **Built.** `OFFER_NEVER_MADE`, pinned |
| 5 — the offer itself | **Not built.** [#382](https://github.com/eddiefiggie/srd-rules-engine/issues/382) |

The `opportunity-attacks` shape stays **unclaimed** in `effect_shapes.json`. A trigger that
nothing calls has not resolved the shape, and R17's inventory is what makes "full SRD 5.2
coverage" falsifiable — marking it on machinery alone is the failure the inventory exists to
prevent. `tests/test_reactions.py` asserts it stays unclaimed.

### Evidence

Six corruption proofs, each against the assertion written for it, per `AGENTS.md`'s rule that
a base-tree proof satisfied by a collection error has proved nothing about any individual
assertion — which is this change's case exactly, since `test_reactions.py` cannot import
against the base tree.

| Corruption | Went red on |
|---|---|
| `withheld` forced to `SIGHT_UNSTATED` | `test_a_reactor_who_can_see_the_mover_may_be_offered_the_attack` |
| the `CANNOT_SEE` branch disabled | `test_a_reactor_who_cannot_see_the_mover_provokes_nothing`, `test_darkness_is_the_same_refusal_and_reaches_it_through_obscurement` |
| `withheld` forced to `None` | `test_an_unstated_view_is_withheld_rather_than_offered` |
| `effective_light` ignoring senses | `test_darkvision_restores_the_offer_that_darkness_took_away` |
| `withheld` given a default | `test_withheld_has_no_default_so_no_construction_answers_it_silently` |
| the disclosure gated on lighting being unstated | `test_the_disclosure_stands_even_where_sight_is_fully_answerable` |

The last is the one that matters for clause 4: it reproduces the failure this record is about —
a disclosure that goes quiet once sight is answerable, while the gap it names remains.
