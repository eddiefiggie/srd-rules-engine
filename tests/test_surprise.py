"""p. 189's Surprise: Disadvantage on Initiative, and nothing else (#440).

> If a creature is caught unawares by the start of combat, that creature is **surprised**,
> which causes it to have **Disadvantage on its Initiative roll**.

The whole entry, and it needed nothing new to express. 0059 rebuilt initiative to draw
**two dice for every combatant** precisely so Advantage and
Disadvantage on Initiative would be expressible without a creature's seed offset depending on
its neighbours' conditions — and the second die had been unused by anything but two conditions
until this.

**Surprise is not a condition.** It has its own glossary entry and is not among p. 179's
fifteen, so it lives on the creature rather than in `Conditions` — putting it there would make
that set sixteen and its checked completeness a different claim.
"""

from __future__ import annotations

from dataclasses import replace

from srd_rules_engine.core.combat import initiative_order
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

#: A seed whose two dice for the first combatant **differ**, so picking the lower rather than
#: the higher is visible in the result.
#:
#: Found by searching for one, after seed 3 gave the same face twice and made
#: `test_surprise_gives_disadvantage_on_initiative` assert `7 < 7`. A seed where the pair
#: matches would let every assertion here pass while the pick did nothing — which is why the
#: helper is also asserted directly below.
SEED = 4


def _creature(cid: str = "pc", **kw: object) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        **kw,  # type: ignore[arg-type]
    )


def _rolled(*combatants: Combatant) -> dict[str, int]:
    return dict(initiative_order(EncounterState.new(list(combatants)), seed=SEED))


def test_surprise_gives_disadvantage_on_initiative() -> None:
    """p. 189's whole mechanic. The two rolls come from the same seed and the same dice, so
    any difference is the pick and nothing else."""
    plain = _rolled(_creature(), _creature("boar"))["pc"]
    surprised = _rolled(_creature(surprised=True), _creature("boar"))["pc"]

    assert surprised < plain, "the lower of the same two dice"


def test_it_changes_nothing_else() -> None:
    """p. 189 states one consequence and stops. A surprised creature is not slowed, not
    Incapacitated, and holds no condition — reading "caught unawares" as more than the
    sentence says is the direction R31 names."""
    surprised = _creature(surprised=True)

    assert surprised.conditions.held == frozenset()
    assert surprised.hit_points == 20
    assert not surprised.is_down


def test_it_is_not_one_of_the_fifteen() -> None:
    """Surprise has its own glossary entry and is not a condition. Filing it among them would
    make the set sixteen, and 15 of 15 is a checked claim."""
    assert not hasattr(Condition, "SURPRISED")
    assert "surprised" not in {c.value for c in Condition}


def test_surprise_cancels_against_an_advantage_from_a_condition() -> None:
    """p. 8's cancellation, which is why the two sources are combined rather than one
    overriding the other. p. 184 gives an Invisible creature Advantage on Initiative; p. 189
    gives a surprised one Disadvantage. A creature with both rolls **flat**."""
    invisible = _creature(conditions=Conditions(held=frozenset({Condition.INVISIBLE})))
    both = replace(invisible, surprised=True)

    with_advantage = _rolled(invisible, _creature("boar"))["pc"]
    with_both = _rolled(both, _creature("boar"))["pc"]
    plain = _rolled(_creature(), _creature("boar"))["pc"]

    assert with_both == plain, "Advantage and Disadvantage cancel to a flat roll (p. 8)"
    assert with_advantage >= plain, "and the Advantage alone is at least as good"


def test_the_advantage_it_produces_is_named_directly() -> None:
    """Asserted at the helper as well as through the dice, because the roll can only show
    which die was picked — two sources agreeing by accident would look the same."""
    from srd_rules_engine.core.combat import _initiative_advantage

    assert _initiative_advantage(_creature()) is Advantage.NONE
    assert _initiative_advantage(_creature(surprised=True)) is Advantage.DISADVANTAGE

    invisible = _creature(conditions=Conditions(held=frozenset({Condition.INVISIBLE})))
    assert _initiative_advantage(invisible) is Advantage.ADVANTAGE
    assert _initiative_advantage(replace(invisible, surprised=True)) is Advantage.NONE

    incapacitated = _creature(conditions=Conditions(held=frozenset({Condition.INCAPACITATED})))
    assert _initiative_advantage(replace(incapacitated, surprised=True)) is (
        Advantage.DISADVANTAGE
    ), "two Disadvantages are still one Disadvantage, not a double penalty"
