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

## Why a pin rather than a per-clause pairing

Asserting that each string's rule is genuinely unbuilt is the judgement no machine can make,
the same one `tests/test_decision_records.py` declines. What a pin holds is that **any** change
is deliberate: the set is small, changes rarely, and a diff is where a reviewer asks "was the
rule built?". The stronger per-clause form — assert the removal and the enforcement together —
is what #280 did for `drops-what-it-holds` and #288 did for the two the object-interaction cap
replaced, and it belongs with whoever builds each rule.
"""

from __future__ import annotations

from srd_rules_engine.core.actions import ActionBudget
from srd_rules_engine.core.conditions import EFFECTS, Condition, Conditions
from srd_rules_engine.core.reactions import SIGHT_QUALIFIER
from srd_rules_engine.core.read_surface import (
    CARRYING_CAPACITY_SPEED_CAP,
    OBJECT_INTERACTION_CAP,
    UTILIZE_REACHES_FOUR_MOVES,
)

#: Every clause the condition set discloses, by condition. Each is a sentence of the document
#: the engine holds and does not enforce, and each is here so removing one is a diff someone
#: reads rather than a silence.
CONDITION_DISCLOSURES: dict[Condition, tuple[str, ...]] = {
    # p. 178: cannot attack or target the charmer with a harmful effect, and the charmer has
    # Advantage on social checks — the second needs the Influence action (#143), the first
    # needs a target the engine can compare against the source.
    Condition.CHARMED: ("cannot-attack-or-target-the-charmer", "charmer-social-advantage"),
    # p. 182: cannot willingly move closer to the source. Movement has no notion of a
    # direction relative to a creature.
    Condition.FRIGHTENED: ("cannot-willingly-approach-the-source",),
    # p. 184: hidden from effects that require sight. #150's mapping is unfilled.
    Condition.INVISIBLE: ("concealed-from-effects-requiring-sight",),
    # p. 186: turned to inanimate substance, and weight times ten with ageing stopped. Neither
    # is a quantity this engine holds.
    Condition.PETRIFIED: ("turned-to-inanimate-substance", "weight-and-ageing"),
    # p. 186: righting yourself costs half your movement, and movement is crawling. Both need
    # a movement model that distinguishes standing from moving.
    Condition.PRONE: ("righting-costs-half-speed", "movement-limited-to-crawling"),
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
        # p. 185's Opportunity Attack fires on a mover "that you can see", and sight is #150.
        SIGHT_QUALIFIER,
        # 0045 clause 1: one object interaction a turn is the engine's cap, taken as the
        # intersection of two readings the document does not compose.
        OBJECT_INTERACTION_CAP,
        # 0045 clause 5: p. 14's GM escalation and p. 177's Breaking Objects are beyond it.
        UTILIZE_REACHES_FOUR_MOVES,
        # 0051 clause 5: p. 178's "your Speed can be no more than 5 feet" is computed against
        # and not applied, because its trigger is dragging, lifting or pushing rather than
        # carrying too much, and p. 12 leaves the subsystem to a person (#336).
        CARRYING_CAPACITY_SPEED_CAP,
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


def test_the_other_disclosures_are_exactly_these() -> None:
    """**This half of the pin is weaker than it reads, and #334 holds the repair.** It compares
    a literal set against a constant built from the same names, so it catches an edit to
    `OTHER_DISCLOSURES` and is blind to a disclosure that exists in the source and was never
    added here — which has already happened once, to `VERBAL_UNCHECKED`. The condition half
    above derives `actual` from `EFFECTS` and is a real guard; this one is not, until the set
    is derived from what the read surface actually appends.
    """
    assert {
        SIGHT_QUALIFIER,
        OBJECT_INTERACTION_CAP,
        UTILIZE_REACHES_FOUR_MOVES,
        CARRYING_CAPACITY_SPEED_CAP,
    } == OTHER_DISCLOSURES


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
