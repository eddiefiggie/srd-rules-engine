"""Every unenforced-clause disclosure, pinned so neither direction moves quietly (#292).

`unenforced_clauses` is how this engine keeps R32 honest: a mechanic it holds but does not
enforce is **named** rather than left to be discovered. Nothing pinned the strings, so:

* a disclosure could be **deleted while its rule stayed unbuilt** — R32 quietly becoming a
  false claim, with every test still green. That is the dangerous direction: a reader is told
  nothing is missing and is entitled to conclude the mechanic is complete.
* a disclosure could be **added** without anyone noticing the engine had stopped enforcing
  something.

#280 surfaced it. Retiring `drops-what-it-holds` broke **no test**, which is the wrong result
for both possible reasons — if the rule had been built nothing confirmed the pairing, and if
it had not, nothing objected.

## `prove_against_base.sh` cannot bite on this file, and that is not a warning sign

A change confined to this module changes no engine behaviour, so the base tree passes the new
tests and the script reports "those tests cover none of the diff". It is right and it is
measuring the wrong thing: what changed is the guard, not what the guard guards. The evidence
that belongs here instead is the corruption comparison — the **predecessor** assertion, run
against a source that appends an unpinned disclosure, stays **green**, and the one below goes
red (#334). That reproduces the finding rather than asserting it.

## Why a pin rather than a per-clause pairing

Asserting that each string's rule is genuinely unbuilt is the judgement no machine can make,
the same one `tests/test_decision_records.py` declines. What a pin holds is that **any** change
is deliberate: the set is small, changes rarely, and a diff is where a reviewer asks "was the
rule built?". The stronger per-clause form — assert the removal and the enforcement together —
is what #280 did for `drops-what-it-holds` and #288 did for the two the object-interaction cap
replaced, and it belongs with whoever builds each rule.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from typing import Any

import srd_rules_engine.core as core_package
from fixtures.encounter import character
from srd_rules_engine.core import EncounterState, read
from srd_rules_engine.core.actions import ActionBudget
from srd_rules_engine.core.conditions import (
    EFFECTS,
    Condition,
    Conditions,
)
from srd_rules_engine.core.read_surface import (
    OBJECT_INTERACTION_CAP,
    PUSH_DISTANCES_IN_STEPS,
    RELEASE_ONLY_ON_YOUR_TURN,
    UNTRAINED_SHIELD_STILL_GRANTS_AC,
    UTILIZE_REACHES_FOUR_MOVES,
    VERBAL_UNCHECKED,
)

#: Every clause the condition set discloses, by condition. Each is a sentence of the document
#: the engine holds and does not enforce, and each is here so removing one is a diff someone
#: reads rather than a silence.
CONDITION_DISCLOSURES: dict[Condition, tuple[str, ...]] = {
    # p. 178: cannot attack or target the charmer with a harmful effect, and the charmer has
    # Advantage on social checks — the second needs the Influence action (#143), the first
    # needs a target the engine can compare against the source.
    # p. 178's automatic failure is applied to the one check this engine knows requires sight
    # — seeing a creature. What is not built is the general rule: no other check declares
    # which sense it needs, and the document does not tabulate that either (#360).
    Condition.BLINDED: ("only-seeing-declares-that-it-requires-sight",),
    Condition.CHARMED: ("cannot-attack-or-target-the-charmer", "charmer-social-advantage"),
    # p. 180: not the same gap as Blinded's, and the difference is the point — **no check in
    # this engine requires hearing at all**, so there is not even one consumer (#360).
    Condition.DEAFENED: ("no-check-requires-hearing",),
    # p. 184: speech is not modelled at all (#360).
    #
    # **`initiative-disadvantage-not-applied` is deliberately absent** (#359), along with
    # Invisible's Advantage twin below. They were two strings rather than one because the pin
    # refuses a repeat, and that was right: sharing one would have made a single removal look
    # like both. `initiative_order` rolls two dice per combatant now.
    # p. 184's "You can't speak", and the reason it stays is sharper than "speech is not
    # modelled": its one mechanical consumer is p. 105's Verbal component, and Incapacitated is
    # the only condition that sets the flag **while also setting `cannot_act`** — so the link
    # would be unreachable code (#360).
    Condition.INCAPACITATED: ("no-rule-consumes-speech",),
    # **`cannot-willingly-approach-the-source` is deliberately absent** (#350). It said
    # "movement has no notion of a direction relative to a creature", and that was the wrong
    # diagnosis twice over: "closer" is a comparison of two distances and needs no direction
    # at all, and what was actually missing was a refusal. `with_movement` makes one now, and
    # `test_the_retired_fear_disclosure_is_enforced_now` asserts the removal and the rule
    # together (0056).
    # **Grappled discloses nothing** (#340, 0066). All three of p. 182's clauses are built and
    # none of them is a flat field: Speed 0 is `speed_zero`; "Disadvantage on attack rolls
    # against any target other than the grappler" is relational and answered by
    # `own_attack_rolls(target_id=...)`; and *Movable* is the grappler's rule, answered by
    # `with_movement`'s `carrying` and by `carried_without_extra_cost`.
    # p. 184: hidden from effects that require sight. #150's mapping is unfilled.
    Condition.INVISIBLE: ("concealed-from-effects-requiring-sight",),
    # p. 186: turned to inanimate substance, and weight times ten with ageing stopped. Neither
    # is a quantity this engine holds.
    Condition.PETRIFIED: ("turned-to-inanimate-substance", "weight-and-ageing"),
    # **Prone's two clauses are deliberately absent** (#353). They needed "a movement model
    # that distinguishes standing from moving", which turned out to be two effect kinds —
    # `MOVED_BY_FORCE` covers ground and spends nothing, `MOVEMENT_SPENT` spends and moves
    # nobody. Both left together, because p. 186 states them in one sentence and the
    # restriction without the exit is a trap (0057).
    # p. 191: unaware of your surroundings — a fact about perception with no consumer.
    #
    # **`remains-prone-when-this-ends` is deliberately absent** (#292). It was here and was
    # stale in the harmless direction: `Conditions.without` enforces it, so the disclosure told
    # a reader less was modelled than is. The test named for that removal below is what
    # makes it checkable rather than asserted.
    Condition.UNCONSCIOUS: ("unaware",),
}

#: Disclosures that are not a condition's.
OTHER_DISCLOSURES: frozenset[str] = frozenset(
    {
        # **p. 185's Opportunity Attack is deliberately absent** (#382, 0072). Two clauses
        # stood here and were the same gap under two names, retired one build apart:
        # `opportunity-attack-requires-seeing-the-mover` went when #150 made sight answerable
        # and #381 consulted it, and `opportunity-attack-detected-but-never-offered` went with
        # the offer itself — `TurnLoop.move` asks every provoked creature whether it spends
        # its Reaction. Each was removed in the change that built its rule, and asserted with
        # it. The limit that remains — a direct `with_movement` caller provokes nothing — is
        # about which caller rather than which rule, so it is 0072 clause 6 and not a clause
        # here.
        # 0045 clause 1: one object interaction a turn is the engine's cap, taken as the
        # intersection of two readings the document does not compose.
        OBJECT_INTERACTION_CAP,
        # 0045 clause 5: p. 14's GM escalation and p. 177's Breaking Objects are beyond it.
        UTILIZE_REACHES_FOUR_MOVES,
        # `CARRYING_CAPACITY_SPEED_CAP` was here until #336 (0067). p. 178's cap is applied
        # now: `Combatant.hauled_weight` supplies the antecedent the clause turned on, and
        # stating it is how p. 12's "the GM **might** require you to abide by the rules" is
        # exercised. Removed in the change that built the rule.
        # p. 105 refuses a Verbal component to a creature "gagged or in an area of magical
        # silence" and the engine models neither (#246).
        #
        # **This one was missing for its whole life, and its addition is a correction rather
        # than a regression** (#334). Adding a clause normally means the engine stopped
        # enforcing something; here the engine never enforced it and the pin simply did not
        # know. Nothing could have caught that, because the test below used to compare a
        # literal against a constant built from the same names. It derives now.
        VERBAL_UNCHECKED,
        # p. 182 lets a grappler release "at any time"; the read surface offers actions only
        # to the creature whose turn it is, so the release is narrowed to the grappler's own
        # turn (#341). What is offered is p. 182's release; what is missing is its timing.
        RELEASE_ONLY_ON_YOUR_TURN,
        # p. 90's Push is "up to 10 feet" and the menu offers it in five-foot steps, so a
        # wielder who wants seven cannot say so (#351). Five is every push distance the
        # document names, and the ones in between are the ones not offered.
        PUSH_DISTANCES_IN_STEPS,
        # p. 177 states three drawbacks for untrained armour. 0063 built the casting
        # prohibition and 0064 the Disadvantage, once `D20Test.ability` reached every test
        # site. The Shield clause needs an AC derived from what is worn, which nothing
        # models — so `untrained-armour-disadvantage-not-applied` is deliberately absent and
        # this is what remains (#367).
        UNTRAINED_SHIELD_STILL_GRANTS_AC,
        # **`shove-cannot-push-only-knock-prone` is deliberately absent** (#345). It was
        # here for one build, while p. 190's Shove could knock a target Prone and not push it.
        # 0055 built the push and the clause came off in the change that built it, which is
        # the pairing AGENTS.md asks for — `tests/test_unarmed_options.py` asserts both
        # effects are offered, which is what makes the removal honest.
    }
)


def test_the_condition_disclosures_are_exactly_these() -> None:
    """Both directions. A pin that only caught removals would be half a guard: an addition
    means the engine stopped enforcing something, and that is as much a change as the
    reverse."""
    actual = {
        condition: effects.unenforced_clauses
        for condition, effects in EFFECTS.items()
        if effects.unenforced_clauses
    }
    assert actual == CONDITION_DISCLOSURES, (
        "the condition set's disclosures changed. If a rule was built, take its clause off "
        "here in the same change that builds it — the pairing is what #280 and #288 did, and "
        "the reason this pin exists is that neither was caught by anything but a person. If a "
        "rule was *not* built, R32 now has a false claim in it."
    )


#: The local every assembly site builds its disclosure list in. Naming it is what lets the
#: walk below find the sites without running them, and a rename makes the walk find nothing —
#: which fails loudly rather than passing, because the pin is not empty.
DISCLOSURE_LIST = "unenforced"


def appended_disclosures() -> frozenset[str]:
    """Every non-condition disclosure the core can emit, read out of the source (#334).

    The condition half of this pin derives `actual` from `EFFECTS`, which is why it is a real
    guard. This half compared a literal set against a constant built from the same names — an
    assertion true by construction over the thing it claimed to check, and the first shape
    AGENTS.md names from #298. It caught an edit to `OTHER_DISCLOSURES` and was blind to a
    disclosure that existed in the source and had never been added, which is exactly what
    happened to `VERBAL_UNCHECKED`.

    So the set is read from the code instead. Every module in `srd_rules_engine.core` is
    parsed, every `unenforced.append(...)` and `unenforced.extend(...)` is found, and the
    argument is resolved against the module that wrote it.

    **An argument shape this does not recognise raises rather than being skipped.** That is
    the whole difference between a guard and a scan: a walk that silently ignored what it
    could not read would go quiet in exactly the way the assertion it replaces did.
    """
    found: set[str] = set()
    sites = 0
    for info in pkgutil.iter_modules(core_package.__path__):
        module = importlib.import_module(f"{core_package.__name__}.{info.name}")
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in {"append", "extend"}:
                continue
            target = func.value
            if not isinstance(target, ast.Name) or target.id != DISCLOSURE_LIST:
                continue
            sites += 1
            for argument in node.args:
                found.update(_resolve(argument, module, info.name))
    assert sites, (
        f"no {DISCLOSURE_LIST}.append/extend call was found anywhere in "
        f"{core_package.__name__}. Either the assembly moved and DISCLOSURE_LIST is stale, or "
        "this walk is inspecting nothing — which is the state it was written to end."
    )
    return frozenset(found)


def _resolve(argument: ast.expr, module: Any, module_name: str) -> set[str]:
    """The disclosure strings one appended argument stands for."""
    if isinstance(argument, ast.Name):
        value = getattr(module, argument.id, None)
        assert isinstance(value, str), (
            f"core.{module_name} appends {argument.id!r} to {DISCLOSURE_LIST} and it does not "
            "resolve to a string in that module. A disclosure the pin cannot read is a "
            "disclosure the pin does not hold."
        )
        return {value}
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        # Nothing writes one inline today. Recognised anyway, because the alternative is a
        # literal disclosure slipping past a walk that only understands names.
        return {argument.value}
    if isinstance(argument, ast.GeneratorExp | ast.ListComp | ast.SetComp):
        # The condition set's clauses and the ActionBudget's, forwarded wholesale. Both are
        # pinned by their own tests above, and neither names a string here to read.
        return set()
    raise AssertionError(
        f"core.{module_name} appends a {type(argument).__name__} to {DISCLOSURE_LIST} and this "
        "walk does not know how to read it. Teach it that shape — skipping it would make the "
        "pin blind in the way #334 was."
    )


def test_the_other_disclosures_are_exactly_these() -> None:
    """Both directions, against a set **derived from the source** rather than restated (#334).

    What this now catches that its predecessor could not: a disclosure appended in the core and
    never pinned. `VERBAL_UNCHECKED` was in that state from the day it shipped — the engine had
    stopped enforcing p. 105's gagged-or-silenced refusal, the pin claimed to hold every
    disclosure, and no test disagreed.
    """
    assert appended_disclosures() == OTHER_DISCLOSURES, (
        "the disclosures the core appends and the ones pinned here have diverged. If a rule "
        "was built, take its clause off in the same change that builds it. If a disclosure "
        "was added, R32 now names a gap that nobody chose to name — which is the direction "
        "this test was blind to until #334."
    )


def test_the_walk_finds_every_site_and_not_merely_one() -> None:
    """The negative case for the assertion above, and the reason it is not vacuous.

    A walk that found a single `append` would satisfy an equality against a one-element pin and
    prove nothing about the rest. The names below are appended at distinct sites under
    different conditions, so finding all of them is evidence the walk reaches the
    whole assembly rather than the first line of it.
    """
    found = appended_disclosures()
    for disclosure in (
        OBJECT_INTERACTION_CAP,
        UTILIZE_REACHES_FOUR_MOVES,
        VERBAL_UNCHECKED,
        RELEASE_ONLY_ON_YOUR_TURN,
        PUSH_DISTANCES_IN_STEPS,
        UNTRAINED_SHIELD_STILL_GRANTS_AC,
    ):
        assert disclosure in found, f"{disclosure!r} is appended in the core and was not found"


def test_the_walk_reads_the_source_rather_than_a_situation_it_happened_to_build() -> None:
    """Why this is a static walk and not a play-and-collect.

    Every one of these is conditional — a held Reaction, a Verbal spell, an unspent object
    interaction, a weapon in hand. Collecting them by reading situations would pin
    whatever the fixtures happened to reach, so a disclosure with no fixture would look like a
    disclosure that does not exist. That is the same blindness in a new shape.
    """
    found = appended_disclosures()
    assert PUSH_DISTANCES_IN_STEPS in found
    # The fixture with no weapon in hand: the clause above cannot appear in any situation this
    # suite builds by default, and the pin holds it regardless.
    situation = read(EncounterState.new([character()]).with_initiative({"pc": 10}), "pc").situation
    assert situation is not None
    assert PUSH_DISTANCES_IN_STEPS not in situation.unenforced_clauses


def test_the_action_budget_discloses_nothing_by_default() -> None:
    """It has the machinery and no clause today, which is a real state rather than an empty
    stub — a Reaction held adds `SIGHT_QUALIFIER` at the read surface, not here."""
    assert ActionBudget().unenforced_clauses() == ()


def test_the_removed_disclosure_was_removed_because_it_is_enforced() -> None:
    """#292 suspected `remains-prone-when-this-ends` was stale in the harmless direction, and
    it was. p. 191: "When this condition ends, you remain Prone."

    Removing a disclosure is only honest when the rule is enforced, so the removal and the
    enforcement are asserted together — which is exactly the pairing the pin above cannot make
    on its own.
    """
    held = Conditions(applied=frozenset({Condition.UNCONSCIOUS}))
    assert Condition.PRONE in held.held, "implied while Unconscious"
    after = held.without(frozenset({Condition.UNCONSCIOUS}))
    assert after.held == frozenset({Condition.PRONE}), "and survives it (p. 191)"
    assert "remains-prone-when-this-ends" not in EFFECTS[Condition.UNCONSCIOUS].unenforced_clauses


def test_no_disclosure_string_is_empty_or_duplicated() -> None:
    """A blank clause discloses nothing and a repeated one is two claims about one gap."""
    every = [c for clauses in CONDITION_DISCLOSURES.values() for c in clauses]
    every.extend(OTHER_DISCLOSURES)
    assert all(c.strip() for c in every)
    assert len(every) == len(set(every))
