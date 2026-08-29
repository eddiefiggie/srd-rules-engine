# 0041 — An item that leaves a creature is an object, and where it lands is unstated

- **Status:** Accepted, 2026-08-29
- **Settles:** [#265](https://github.com/eddiefiggie/srd-rules-engine/issues/265),
  [#272](https://github.com/eddiefiggie/srd-rules-engine/issues/272)
- **Requirements:** R1, R15, R18, R19, R31, R32
- **Related:** [0039 — equipment is what a creature holds, wears and carries](0039-equipment-is-what-a-creature-holds-wears-and-carries.md),
  whose clause 3 closed the carriage vocabulary this reopens;
  [0040 — a weapon is an item, and proficiency is the wielder's](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 1; [0026 — terrain enters as state](0026-terrain-enters-as-state.md), clause 1;
  [0019 — kind is a filing label](0019-kind-is-a-filing-label.md);
  [0014 — positional state](0014-positional-state.md)

## Context

0039 clause 3 gave an item three carriages — worn, held, stowed — and all three are
*carried*. Two rules the engine is now close enough to build both need a fourth thing, and
neither fits:

> p. 177, *Attack [Action]*: Unequipping a weapon includes sheathing, stowing, or **dropping**
> it.

> p. 90, *Thrown*: you can **throw the weapon** to make a ranged attack, and you can draw that
> weapon as part of the attack.

A javelin in flight, or a sword on the floor across the room, is neither worn, held nor
stowed. #265 and #272 each named this and each said the other should be decided with it.

**The document drops things in more places than those two**, which is what makes this a
vocabulary question rather than a weapon-property question:

- p. 191, *Unconscious*: "Inert. You have the Incapacitated and Prone conditions, and **you
  drop whatever you're holding**." The engine has held this condition since
  [#93](https://github.com/eddiefiggie/srd-rules-engine/issues/93) and discloses the clause as
  unenforced.
- p. 183, *Improvised Weapons*: "if you … **throw a Melee weapon that lacks the Thrown
  property**, the weapon counts as an improvised weapon" — so throwing any weapon is legal,
  and only the arithmetic changes.
- p. 116's *Command* and p. 130's *Fear* both compel a creature to drop what it holds. Neither
  ships here (R31), and both would arrive through a ruleset the moment spells do.

So five printed rules detach an item from a creature. **Not one of them says where it goes.**

## Options considered

**Option 1 — a fourth `Carriage` member.** Rejected, and it is the small-diff one. Every
member of that enum is a way of *being carried*, which p. 190 then reads: "When you teleport,
all the equipment you're **wearing and carrying** teleports with you." A dropped sword inside
`Combatant.equipment` is a dropped sword that teleports with the creature who dropped it, and
the repair is a special case inside a closed vocabulary — the failure 0019 exists to refuse.

**Option 2 — the item ceases to be tracked.** Rejected. It is honest about location and
destroys the object: p. 177 says "Equipping a weapon includes … **picking it up**", so the
document contemplates the reverse trip and this option makes it unreachable forever.

**Option 3 — a new type for a detached object (`GroundItem`, `DroppedWeapon`).** Rejected by
the document rather than on taste. p. 191: "A **weapon is an object** that is in the Simple or
Martial weapon category." p. 12: "an object is a discrete, inanimate item like a window, door,
**sword**, book, table, chair, or stone." A sword is an object while it is in a hand. Nothing
changes type by being let go, and a second type would make `isinstance` answer a question
about a *relation*.

**Option 4 — detachment ends the relation, and the object's position is state that may be
unknown.** Chosen.

**Option 5 — Option 4, but a drop defaults to the dropping creature's space.** Rejected, and
this is the one worth the paragraph. See clause 5.

## Decision

**1. Detachment is a change of relation, not of type.** The `Item` that was held is the
`Item` that is on the floor, because the document already calls both an object (p. 12, p. 185,
p. 191). 0040 clause 1 made `Weapon` a subtype of `Item`; nothing here subtypes further.

**2. Detachment removes the item from `Combatant.equipment`.** `Carriage` stays exactly the
three members 0039 closed it at. An item a creature no longer has is not a creature's item
with a flag on it — and p. 190's teleportation clause is the rule that makes the difference
observable rather than stylistic.

**3. A detached object rides on `EncounterState`, beside `obstructions` and `lighting`, for
the reason 0026 clause 1 put those there.** Where the swords on the floor are is not a fact a
caller may hand to a query at the moment an outcome is computed, because choosing which
objects are within reach is choosing whether a disarmed creature can re-arm itself.

**4. Its position is `Position | None`, and the engine never defaults it.** This is the clause
the record exists for. Five rules detach an item and none states a destination, so there is no
rule value to read (R31). `None` means *the document did not say and nobody has*, which is
the shape `Combatant.position` and `Combatant.hands` already carry — the second by 0039
clause 4, for exactly this reason. A ruleset that knows its scene says; nothing else does.

**The document's silence is positive evidence, not a gap in the reading.** Where a destination
is stated, it is stated by the *effect that caused the detachment*, as its own clause:

- p. 217, *Dancing Sword*: "If you have no hand free, the weapon **falls to the ground in your
  space**."
- p. 209, *Animated Shield*: "the Shield **falls to the ground or into your hand if you have
  one free**."
- p. 247, *Staff of the Python*: "you can throw this staff so that it **lands in an unoccupied
  space within 10 feet** of you."

Three magic items spend a sentence each saying where a thing ends up. If a general rule put a
released object in its holder's space, p. 217 would not need the clause — and it is a magic
item, which is content this repository does not ship.

**5. Dropping and throwing are one vocabulary question and two destination questions.** #265
and #272 both frame them as one question asked by two rules, and say the answers will differ
if answered apart. The first half is right and clauses 1-4 answer it once. **The second half
is wrong**, and reading the two entries together is what shows it: a dropped weapon is
released where its holder stands, while a thrown weapon has travelled up to a long range away
— p. 90 gives it a range in feet, and the thrower's position is the one place the javelin
certainly *is not*.

So a `detached_at = holder's position` default would look right for the common case and be
wrong for every throw, in the direction that returns a weapon to the feet of the creature who
threw it. That is why clause 4 refuses a default instead of picking the destination that
serves the commoner rule.

**6. Picking up is p. 12's object interaction, and the whole mechanism is printed.** Legality
is buildable today and does not wait on clause 4:

- p. 177: "You can either equip or unequip **one** weapon when you make an attack as part of
  this action. You do so either before or after the attack" — one per attack, and the ordering
  matters because equipping after means the weapon drawn is not the weapon swung.
- p. 12: "interactions with objects are limited: **one free interaction per turn**. That
  interaction must occur during a creature's movement or action. Any additional interactions
  require the Utilize action."
- p. 191, *Utilize*: "You normally interact with an object while doing something else, such as
  when you draw a sword as part of the Attack action."

**Reachability is the half clause 4 refuses.** An object with no position is offered no
pick-up, and the read surface says that it declined and why — rather than presenting a menu
whose emptiness a reader has to interpret, which is the narrowing #267 caught in 0040 clause 3.

**7. Detachment happens through a ruling.** A caller may not move an item out of a creature's
hands by mutating state, for the reason #119 stopped a caller applying a condition that way:
R19 keeps the read surface from mutating, and R1 keeps one entry point the only thing that
produces an outcome. Dropping is an outcome — p. 191 makes it a consequence of a condition,
and p. 130 makes it a consequence of a failed save.

## Why

**Clause 4 is the clause this record exists for, and clause 5 is the reason it is stated as a
refusal.** "A dropped item is in your space" is the single most plausible sentence in this
whole area. It is what every table plays, it is what p. 217 says for one magic item, and it
would pass review. It is also not in the document, and the engine that assumes it produces a
pick-up that is adjudicated, ledgered and replayable — a wrong position made
indistinguishable from a right one by the machinery built to make outcomes trustworthy. That
is the specific harm R31 names, and it arrives here wearing common sense.

**The absence had to be searched for, not recalled.** A reader who knows the game will supply
the missing sentence from memory without noticing, which is why the Evidence section below
records the sweep rather than the conclusion.

**Clause 2 is a rules fix hiding in a refactor.** Growing `Carriage` is a two-line change that
review would wave through, and it silently makes p. 190 teleport a creature's dropped weapon
along with it. The cost of the fourth member is not the member; it is that every existing
reader of "wearing and carrying" quietly acquires a bug.

**Clause 6 keeps the record from being purely subtractive.** Clause 4 refuses something, and a
record that only refuses reads as a reason not to build. The pick-up mechanism is fully
printed across three pages, and all of it is buildable now — what waits is one coordinate.

## Consequences

**Accepted costs.**

- **A dropped weapon cannot be picked up in a ruleset that states no positions.** This is the
  real loss in play #265 named, and it is accepted rather than solved. The alternative is
  clause 5's wrong default, and a gap a player can see beats a coordinate they cannot.
- **`Item.id` becomes load-bearing across the creature boundary.** Two identical daggers are
  distinguishable while one is held and one is on the floor only if their ids differ. 0040
  clause 1 already made identity the thing a declaration names; this makes it matter to a
  ruleset author who was free to be careless with it.
- **`EncounterState` grows a field**, and the read surface grows offers that are frequently
  empty. Existing rulesets are unaffected — the default is no detached objects, which
  describes a scene where nobody has dropped anything and is the right answer for one.
- **Nothing here models an object's own space.** p. 185 says a space is occupied if it "is
  **completely filled by objects**", and a sword on the floor does not fill one. The engine
  stores where an object is and draws no conclusion about what that blocks.

**Follow-on effects.**

- **#265 becomes buildable in full** — clause 6 is its whole mechanism, and clause 4 is the
  "or dropping it" half it was blocked on.
- **#272 becomes buildable except its destination.** Thrown's attack half is arithmetic p. 90
  states outright, and "you can draw that weapon as part of the attack" is #265's equip clause
  again. Where the javelin lands stays refused.
- **p. 191's `drops-what-it-holds` is now enforced**, and the disclosure is off
  ([#280](https://github.com/eddiefiggie/srd-rules-engine/issues/280)). The clause is declared on `ConditionEffects` beside its citation rather
  than matched on in the adjudicator, so a second condition that sheds arrives with its own
  printed sentence and needs no change to the code that reads it.
- **#273's ammunition touches this and is not settled by it.** p. 128 groups "a thrown weapon
  **or piece of ammunition**" as one category of released thing, so a spent arrow detaches the
  way a thrown javelin does. The quantity question #273 names is untouched.
- **Coverage does not move on this record.** It decides; the issues below build.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 12** (*What Is an Object?*,
*Time-Limited Object Interactions*, whole), **p. 89-90** (the weapon properties, whole),
**p. 177** (*Attack [Action]*), **p. 183** (*Improvised Weapons*), **p. 185** (*Object*,
*Occupied Space*), **p. 190** (*Target*, *Teleportation*), **p. 191** (*Unconscious*,
*Unoccupied Space*, *Utilize*, *Weapon*).

**The sweep behind clause 4, because an absence cannot be cited.** Every page of the document
was searched, on whitespace-normalised text, for `drop\w*`, `pick(ing|s)? … up`, `picked up`,
`falls to the ground`, `lands? in`, and `on the ground`. What it returned:

- `drop` is overwhelmingly *Dropping to 0 Hit Points* (pp. 2, 17, 30, 73, 86 and most spell
  entries) — a different sense of the word, and the reason a naive grep looks like coverage.
- The rules that drop **items** are p. 177, p. 191, p. 116 and p. 130. None names a
  destination.
- `falls to the ground` appears five times and **every one is an effect stating its own
  outcome** — pp. 133, 171, 209, 217 (twice). p. 217 is the only text in the document that
  ever puts a released weapon somewhere specific, and it is a magic item describing itself.
- `picking it up` appears **once in the document**, on p. 177, and describes the trip back.

Reproduce with `pymupdf` over the PDF; the normalisation is `page_text()` from
`scripts/verify_d20_rules.py`, because the document is two-column with hyphenated line breaks
and `Dis-\nadvantage` is one phrase to a reader and three tokens to a search.

**Where the method nearly went wrong.** The first reading of #265 and #272 accepted their
shared premise — one question, one answer — and would have produced a `detached_at` defaulting
to the holder's position, satisfying both issues and breaking every throw. What caught it was
reading p. 90's Thrown entry next to p. 177's drop clause rather than trusting the summary
each issue gives of the other.

In the tree:

- `Carriage` is `WORN | HELD | STOWED` in `core/equipment.py`, and its docstring records that
  "stowed" is this repository's word rather than the document's.
- `Combatant.equipment` holds `Carried` items; `Combatant.position` is `Position | None` and
  `Combatant.hands` is `int | None` — both already refusing a default.
- `EncounterState` carries `obstructions` and `lighting` as state for 0026's reason.
- `Condition.UNCONSCIOUS` lists `"drops-what-it-holds"` in `unenforced_clauses`.

## Status of implementation

**Clauses 1 to 4 and 7 are built.** [#279](https://github.com/eddiefiggie/srd-rules-engine/issues/279) shipped all four: clauses 3 and 4 were its
stated scope, and clauses 1 and 2 landed inside it because the state could not be built
without settling the shape it holds. Clauses 6 and 7 are decided and held by issues below.

**A second tracking defect, and it is the mirror of the first.** #277 and #278 stayed open for
a build over work that had shipped — which reads as outstanding exactly as a *closed* issue
reads as finished. Both are now closed with the evidence. #278 was complete on merge; **#277
was not**, and the audit is what found it: the issue asked for the vocabulary "plus the guard
that keeps a second type from arriving later", and only the vocabulary had shipped. A decision
*not* to add a type leaves no code behind to read, so the guard is the only thing that records
it — `test_letting_go_of_an_item_adds_no_type_to_the_item_hierarchy`, proved red against an
appended `GroundItem(Item)`.

**Two clauses were held by nothing for the length of one build, and the mechanism is worth
recording.** This record closed [#265](https://github.com/eddiefiggie/srd-rules-engine/issues/265) and [#272](https://github.com/eddiefiggie/srd-rules-engine/issues/272) by keyword and said each
was "re-filed as the build it unblocks" — but the table pointed clause 6 at #265 itself, and
no re-filing happened. So the moment the record merged, clause 6 and Thrown's arithmetic were
tracked by *closed* issues, which `AGENTS.md` calls worse than unfiled: a closed issue reads
as finished work rather than as absent work. Filed as [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283) and [#284](https://github.com/eddiefiggie/srd-rules-engine/issues/284)
during #279. **A record that closes an issue may not also cite it as the holder of unbuilt
work** — the closing keyword and the tracking pointer cannot be the same number.

| Clause | State |
|---|---|
| 1 — detachment changes a relation, not a type | **Built.** `DetachedObject` composes an `Item` rather than subtyping one, and `Item.__subclasses__() == [Weapon]` is pinned — the only record a not-built decision leaves ([#277](https://github.com/eddiefiggie/srd-rules-engine/issues/277)) |
| 2 — detachment removes the item from `Combatant.equipment`; `Carriage` stays at three | **Built.** `Carriage` pinned at three members, so p. 190's "wearing and carrying" cannot quietly acquire a fourth ([#278](https://github.com/eddiefiggie/srd-rules-engine/issues/278)) |
| 3 — detached objects ride on `EncounterState` | **Built.** `EncounterState.detached_objects`, beside `obstructions` and `lighting` ([#279](https://github.com/eddiefiggie/srd-rules-engine/issues/279)) |
| 4 — position is `Position \| None`, never defaulted | **Built.** `DetachedObject.position`, with `reachable_objects` returning `None` for a positionless actor and `unplaced_objects` naming what no rule placed ([#279](https://github.com/eddiefiggie/srd-rules-engine/issues/279)) |
| 5 — dropping and throwing share a vocabulary and not a destination | **Decided.** Records why clause 4 refuses; nothing to build |
| 6 — pick-up is p. 12's object interaction and p. 177's equip | **Built** by [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283) — *not* #265, which this record closed. p. 13's standalone route followed in [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) |
| 7 — detachment happens through a ruling | **Built.** `EffectKind.OBJECT_DETACHED` and `EncounterState.with_object_detached`; p. 191's drop is derived by the engine when Unconscious lands, and its `drops-what-it-holds` disclosure is retired ([#280](https://github.com/eddiefiggie/srd-rules-engine/issues/280)) |

**#265 and #272 are closed by this record**, and each was re-filed as the build it unblocks:
#265's equip/unequip mechanism as [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283), #272's Thrown arithmetic as
[#284](https://github.com/eddiefiggie/srd-rules-engine/issues/284) with its destination disclosed as refused under clause 4.

**What #279's build found that this record did not.** Clause 4 said the position is never
defaulted and did not say what *reads* it. Three outcomes were needed rather than two: an
actor with no position gets `None` — the question is unanswerable — while an actor who does
have one gets a computed list that an unplaced object is absent from. Those two absences are
different facts, so `unplaced_objects` names the second rather than leaving a reader to infer
it from an empty list. That is the same narrowing [#267](https://github.com/eddiefiggie/srd-rules-engine/issues/267) caught in 0040 clause 3, and
the record would have shipped it again.

**And what the #277/#278 audit found.** Clause 1 is a decision not to add a type, so unlike
every other clause here it ships as *nothing* — no symbol, no branch, no field. That made it
the one clause whose completion could not be checked by reading the diff, and it was reported
complete on that basis before the guard existed. **A clause whose content is an absence needs
a guard to be finishable at all**, which is the same lesson the document-wide verifier clauses
in this record's Evidence section carry, arriving a second time from the other direction.

**And what #280 found.** Clause 7 said detachment happens through a ruling and did not say
**who derives it**. Leaving p. 191's drop to the resolver that applies Unconscious would have
satisfied the clause as written and reproduced the failure this engine exists to remove: a
ruleset that forgot would keep a sword in an unconscious hand, and nothing would say so. So
the engine derives the drop from the condition, the way it derives implication, and each
dropped item lands as its own recorded `Effect` rather than as a side effect of applying the
condition — a mechanical change the ledger cannot see is one no narrator can report and no
replay can reproduce.

**A disclosure retired without its rule would have been invisible.** Nothing pinned
`"drops-what-it-holds"`, so the string could have been deleted and the behaviour never built,
leaving R32 dishonest with every test green. The removal and the enforcement are now asserted
in one test for that reason, and the pairing was proved by building the rule and taking it
away again.

_Written 2026-08-29 against SRD v5.2.1._

_Updated 2026-08-29 ([#284](https://github.com/eddiefiggie/srd-rules-engine/issues/284)). Both re-filed issues have landed: [#283](https://github.com/eddiefiggie/srd-rules-engine/issues/283) built
clause 6 and #284 built p. 90's Thrown. **Clause 4's accepted cost is now something a player
meets rather than a paragraph** — a thrown javelin leaves the hand whether it hits or misses,
lands where no rule states, and cannot be picked up unless a ruleset says where it fell. The
record predicted that and the build is where it bites. #284 also found the cost has a second
face the record did not see: the same silence that refuses a destination is what makes
`Weapon`'s range fields mean different things for a swing and for a throw, and an invariant
written when no melee weapon could carry a range had to be corrected rather than merely
extended._

