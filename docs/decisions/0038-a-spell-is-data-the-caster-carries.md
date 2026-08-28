# 0038 — A spell is data the caster carries, and the engine spends what casting costs

- **Status:** Accepted, 2026-08-28
- **Settles:** [#244](https://github.com/eddiefiggie/srd-rules-engine/issues/244)
- **Requirements:** R1, R4, R15, R18, R31, R32
- **Related:** [0026 — the state carries what an outcome is computed from](0026-terrain-enters-as-state.md),
  clause 1, which is why the spell list rides on the caster rather than arriving as an
  argument; [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  clause 6, the precedent for adding a branch to `Proposal`;
  [0034](0034-a-term-the-document-defines-and-never-uses.md), for a term the document
  defines and gives no rules to;
  [0037](0037-a-concentration-is-an-early-out-not-an-axis.md), whose clause 1 is what a
  Concentration spell's effect will hang on

## Context

`core.spellcasting` holds slots with upcasting, save DCs, attack modifiers, cantrip level,
ritual timing, range and reach, and since #240 the whole of Concentration. **Nothing can cast
a spell**, and the reason is not a missing function: there is no answer to what a spell *is*
as something the engine holds.

There cannot be a table of them here. Spell descriptions are content, and shipping them would
be the inferred rule values R31 forbids and the redistribution `NOTICE.md` declines. So a
spell is ruleset data — and the question is what shape it takes, where its effect comes from,
and what the engine may enforce while knowing nothing about that effect.

### The precedent, and where it stops reaching

`core.combat` solved this for weapons:

> **A closure rather than a registry entry**: a weapon is ruleset data, and binding a table of
> them here would make the engine carry rule values it cannot verify.

`attack_resolver(weapon)` closes over a `Weapon` and returns a `Resolver`. It has never been
recorded, and copying it wholesale would be wrong in one specific way.

**A weapon is invisible to legality; a spell is not.** `legal_actions` enumerates
`attack:<target>` against every standing opponent **without consulting any weapon at all** —
what an attack does is combat's business, that one is on the menu is the state's. Whether a
caster may cast Fireball is a fact about the *caster*: does it have the spell, is there a slot
that can pay for it. So the spell list cannot live only in the ruleset the way weapons do.

### The finding that decides where the list lives

`legal_actions(state, actor_id)` takes state and nothing else, and R18 requires the legality
question to be computable rather than checkable after the fact. Passing the caster's spells in
as an argument is the shape [0026](0026-terrain-enters-as-state.md) clause 1 already
refused for light and walls:

> an input the caller supplies at the moment an outcome is computed is an input the caller
> **chooses**

A caller that hands `legal_actions` a spell list is a caller that decides what a caster may
cast, one call at a time. Lighting and obstructions ride on the state for exactly this reason,
and `SpellSlots` already rides on `Combatant`. The spells do too.

### The finding that makes this bigger than it looks

**Nothing in the adjudication path spends anything.** `ActionBudget.spend` has no caller
outside `dodging()` and the tests: an attack does not cost the Action, and there is no
mechanism by which adjudicating a declaration costs a resource. A spell slot would be the
**first**, so the keystone is building that mechanism rather than using one, and this record
has to say how.

## Options considered

**Option 1 — a spell registry in the engine, keyed by name.** Rejected outright. It is the
content this repository does not ship, and every entry would be a rule value nobody could
verify (R31).

**Option 2 — `spell_resolver(spell)` and nothing else, exactly as weapons work.** Rejected as
incomplete rather than wrong. It answers where the effect comes from and leaves legality
unanswerable: `legal_actions` still cannot say what this caster may cast, which is the half
R18 asks for.

**Option 3 — the ruleset resolver expends the slot itself.** Rejected, and this is the
important rejection. A ruleset that forgot the expenditure would be a ruleset whose caster
casts for free, and the failure is invisible: the spell works, the ledger records a Ruling,
and only the slot count is wrong. Outcome authority means the engine spends what the rules
say casting costs, not that it hopes a consumer did.

**Option 4 — the adjudicator expends the slot when it sees a cast.** Rejected. It puts
spell-specific knowledge inside the one adjudication entry point, which is the surface that
must stay ignorant of *which* mechanic it is running. R1 is about there being one path to an
outcome, not about that path knowing what a spell is.

**Option 5 — duplicate the cost into every branch of the proposal.** Rejected. It is
mechanical and safe and it says the wrong thing: p. 104 ties expenditure to the *casting* —
"When you cast a spell, you expend a slot of that spell's level or higher" — not to how the
roll came out. A cost written into each outcome is a claim that each outcome charges it, and
it goes wrong the moment a branch is added and the duplication is not.

## Decision

**1. A spell is ruleset data carried by the caster.** `Combatant` holds what this creature can
cast, beside `slots`, because legality is a question about the creature and
`legal_actions(state, actor_id)` may not take a second argument (0026 clause 1). What a spell
*does* is not here.

**2. The engine holds only the fields it has rules about**: the spell's level, its casting
time, its range, and whether it requires Concentration. Each of those is something the engine
itself acts on — picking the slot, spending the action, asking `spell_reaches`, starting
Concentration.

**School is excluded because the document excludes it.** p. 105: "Each spell belongs to a
school of magic […] These categories help describe spells but **have no rules of their own**."
A field for it would be a field nothing reads, which is the decay 0033 and #228 keep finding.
It is not a gap and should not be filed as one.

**Components are not held yet either**, and for a different reason: the engine cannot check
any of the three ([#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245),
[#246](https://github.com/eddiefiggie/srd-rules-engine/issues/246)). Holding V/S/M while
enforcing none of them is a capability with no consumer; the honest form is the R32
disclosure the keystone ships, and the field arrives with the subsystem that can read it.

**3. The effect is a ruleset resolver, and the engine wraps it.** `spell_resolver(spell,
effects)` is engine code: it pays what casting costs, starts Concentration when the spell
requires it, and delegates the spell's actual effects to the resolver the ruleset brought. A
ruleset registers the wrapper, never a bare effect resolver — which is what makes Option 3's
failure unreachable rather than discouraged.

**4. Upcasting is enumerated, not parameterised.** `SpellSlots.payable_by(level)` already
computes which slot levels can pay for a spell. The read surface offers **one `LegalAction`
per payable level**, so the level the agent casts at is chosen from a menu the engine
computed rather than supplied as a number the engine has to trust. The action key carries it
and a parser reads it back, which is `attack_key` / `attack_target`'s existing shape.

What the extra level *does* is the resolver's, because p. 105 puts it "as detailed in a
spell's description". The engine never infers a scaling rule.

**5. Casting and spending a slot are separate facts.** p. 104, *Casting without Slots*, names
four routes that expend none: Cantrips, Rituals, Special Abilities, and Magic Items. So the
wrapper asks the spell what casting it costs rather than assuming a slot, and a cantrip is not
a special case bolted on afterwards — it is the second-most ordinary case the page describes.

**6. `Proposal` gains an `always` branch, and that is where a cost goes.** Effects that apply
because the casting happened, rather than because a branch was selected. 0027 clause 6 added
`outcome` for the same kind of reason and `Proposal` is not on the COMMITTED surface, so this
is additive and costs no `API_VERSION` movement. It is what makes clause 3's wrapper one
place with one effect instead of a duplication that a later branch silently escapes.

**7. What a Concentration names is the rule id of whatever started it.** Not a spell name.
p. 179's clause is "the moment you start casting a spell that requires Concentration **or
activate another effect that requires Concentration**", so an item-granted Concentration has
to be expressible — and `Concentration.spell` is currently named for the half the tree quoted
([#241](https://github.com/eddiefiggie/srd-rules-engine/issues/241)). A rule id is what the
engine already uses to say which mechanic something is, everywhere else.

**8. The spell list is one list.** p. 104 says features specify "which spells you have access
to, if any; whether you always have certain spells prepared; and whether you can change the
list". It does not define a "known spells" list beside a prepared one. Preparation
([#249](https://github.com/eddiefiggie/srd-rules-engine/issues/249)) later refines **how the
list is arrived at**; it does not add a second list, and an engine that modelled two because
the phrase "prepared and known" is familiar would be drawing a distinction the SRD text does
not (R31).

## Why

**Clause 1 is the clause this record would have got wrong.** The weapon precedent is right
there, it is well-reasoned, and copying it gives a spell that lives entirely in the ruleset
— at which point `legal_actions` cannot answer what a caster may cast, and the natural repair
is to pass the list in. That repair is the thing 0026 clause 1 exists to refuse, and it would
have arrived looking like a small signature change rather than like a caller choosing
outcomes.

**Clause 3 is where outcome authority actually lives for spells.** Every other rule in this
engine is resolved by code the engine ships. A spell is the first mechanic whose *effect*
comes from outside, so "the engine holds outcome authority" has to mean something more
specific here: the engine owns the costs and the compelled consequences, and the ruleset owns
only what the spell does. A wrapper is the difference between that being structural and being
a convention in a consumer's head.

**Clause 4 turns a trust problem into an enumeration.** If the agent supplied a slot level,
the engine would have to check it against `payable_by` anyway — so the set is computed either
way, and offering it is strictly better than validating against it. It also makes the read
surface answer R18's question fully: not "you may cast Fireball" but "you may cast Fireball
at 3rd, 4th or 5th".

**Clause 5 is the sentence a summary drops.** "Cast a spell" and "expend a slot" are one
action in most people's memory of the game and two facts on p. 104, and the engine that
couples them is wrong for every cantrip — which is the most frequently cast thing in play.

**Nothing here needs the engine to read prose.** Every field in clause 2 is a value; the
effect is code; the school is excluded because the document gives it no rules. R20 holds: the
memory port is not involved and no part of this asks the engine to interpret a description.

## Consequences

**Accepted costs.**

- **`Combatant` grows a spell list**, and it is ruleset-shaped data on a core type. That is
  already true of `SpellSlots` and of `Defences`, and clause 1 says why the alternative is
  worse.
- **A wrapper is indirection**, and a consumer who registers the inner resolver by mistake
  gets a spell that costs nothing. Mitigated by the wrapper being the only documented way to
  register a spell, and by a guard the keystone owes: a registered spell resolver that is not
  the wrapper should be refused rather than trusted.
- **`Proposal` grows a branch**, and the type now has five ways to state effects. Clause 6
  accepts it; the alternative duplicates a cost across branches and escapes the next one.
- **One `LegalAction` per payable slot level** makes the offered set larger — a level 5 caster
  with a level 1 spell prepared sees five entries for it. That is the honest menu, and 0007's
  read token commits to whatever is offered, so nothing else has to change.

**Follow-on effects.**

- **The first resource an adjudication ever spends.** Nothing in the path spends anything
  today, so the keystone builds that mechanism rather than using one. The Magic action
  (p. 185) is its obvious next user: `ActionBudget.spend` exists, is fully tested, and has no
  caller outside `dodging()` — an attack does not cost the Action today.
- **#241 is settled by clause 7** and closes with the keystone that renames the field.
- **#249's trap is closed by clause 8** before it can be walked into.
- **Coverage does not move on this record.** It decides; the keystone builds.

## Evidence

Read in the official SRD v5.2.1 PDF for this record, printed **p. 104** (*Gaining Spells*,
*Preparing Spells*, *Casting Spells*, *Spell Level*, *Spell Slots*, *Casting without Slots*)
and **p. 105** (*School of Magic*, *Casting Time*, *One Spell with a Spell Slot per Turn*,
*Longer Casting Times*, *Range*, *Components*), both whole.

The sentences the clauses rest on:

- p. 104: "When you cast a spell, you expend a slot of that spell's level or higher" — clause 6.
- p. 104, *Casting without Slots*: Cantrips, Rituals, Special Abilities, Magic Items — clause 5.
- p. 105: "These categories help describe spells but have no rules of their own" — clause 2's
  exclusion of school.
- p. 105: "as detailed in a spell's description" — clause 4's refusal to infer scaling.
- p. 105, *Components*: "If the spellcaster can't provide one or more of a spell's components,
  the spellcaster can't cast the spell" — the rule clause 2 declines to hold a field for until
  it can be checked.
- p. 179: "or activate another effect that requires Concentration" — clause 7.

In the tree:

- `legal_actions(state, actor_id)` takes state alone and its docstring names spells as a
  future extension of that seam: "Movement, spells, and conditions arrive with the units that
  implement them."
- `attack_resolver(weapon)` closes over ruleset data; `legal_actions` enumerates attacks
  without consulting a weapon, which is the asymmetry clause 1 turns on.
- `SpellSlots.payable_by` already returns the payable slot levels, lowest first — clause 4
  needs no new arithmetic.
- `ActionBudget.spend` is called only by `dodging()` and by tests. No adjudication spends a
  resource.
- `Proposal` is not listed in `stability.COMMITTED`.
- `Concentration.spell` is a `str | None` naming a spell.

## Status of implementation

**All eight clauses are built**, by
[#248](https://github.com/eddiefiggie/srd-rules-engine/issues/248) — the casting keystone,
filed when #19 was scoped and before this record landed.

**What the build found that this record did not anticipate.** Clause 6 said `Proposal.always`
was for "a cost", and the slot turned out not to be the only one: p. 185 charges the Magic
action for an action-timed spell, so casting spends an action too — and that made it the
**first thing an adjudication has ever charged**. The Consequences section above called this
out as a follow-on; what it did not see is that the asymmetry ships. **An attack still does
not cost the Action**, because charging it is a behavioural change to a mechanic that has
shipped since the vertical slice and does not belong inside a spellcasting change. Filed as
[#252](https://github.com/eddiefiggie/srd-rules-engine/issues/252) and disclosed in
`core.casting` rather than left for a reader to notice.

| Clause | State |
|---|---|
| 1 — a spell is ruleset data carried by the caster | **Built.** `Combatant.spells`, and `legal_actions` still takes state and `actor_id` only |
| 2 — the engine holds only fields it has rules about; school excluded, components deferred | **Built.** `Spell` holds level, casting time, range and requires-Concentration. No school, no components; both disclosed in `core.casting` (R32) |
| 3 — the effect is a ruleset resolver the engine wraps | **Built.** `spell_resolver` wraps; `spell_resolvers` is the only documented registration path, so an unwrapped resolver is not expressible through it. A test asserts what an unwrapped one costs: nothing |
| 4 — upcasting is enumerated, not parameterised | **Built.** One `LegalAction` per level `payable_by` returns, with the level in the action key and a parser reading it back |
| 5 — casting and spending a slot are separate facts | **Built** for Cantrips, which is the one of p. 104's four slotless routes this engine has. Rituals, Special Abilities and Magic Items remain unbuilt |
| 6 — `Proposal` gains an `always` branch | **Built**, and it carries two costs rather than the one this clause imagined: the slot, and the action p. 185 charges |
| 7 — a Concentration names a rule id | **Built.** `Concentration.rule_id`, closing [#241](https://github.com/eddiefiggie/srd-rules-engine/issues/241) |
| 8 — one spell list, not two | **Built** as one list, and still at risk only where [#249](https://github.com/eddiefiggie/srd-rules-engine/issues/249) refines it |

**#244 is closed by this record**, and #248 by the change that built it. #19 stays open as the umbrella until its slices do — #249, #250, #245, #246, #247, #252 and #253.

_Written 2026-08-28 against SRD v5.2.1._
