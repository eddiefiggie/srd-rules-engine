"""p. 90's Reach property, the tenth weapon property and the last to be built (#316).

> **Reach.** A Reach weapon adds 5 feet to your reach when you attack with it, as well as when
> determining your reach for Opportunity Attacks with it.

The engine held p. 186's default — "A creature has a reach of 5 feet **unless a rule says
otherwise**" — and not the rule that says otherwise. `Combatant.reach` could be set to 10 by
hand, and that is wrong twice: the bonus then reaches a Dagger held in the same hand, and it
reaches Opportunity Attacks made with any weapon, where p. 90 says "with it" both times.

The same boundary 0040 clause 2 drew for `proficient` and #263 drew for the grip, in the other
direction — those were creature facts stored on the weapon, and this was a weapon fact stored
on the creature. So the two tests that matter here are not "a Whip reaches 10 feet": they are
**the Dagger in the same hand still reaches 5**, and **the bonus adds to the creature's own
reach rather than replacing it**. Either would pass against a `Combatant.reach` of 10.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    Rule,
    RuleProvenance,
    Weapon,
    attack_key,
    attack_resolver,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.position import DEFAULT_REACH_FEET, Position
from srd_rules_engine.core.reactions import Provocation, provocations
from srd_rules_engine.core.sight import Lighting, LightLevel
from srd_rules_engine.memory.store import JsonMemoryStore

#: A Reach weapon, one-handed so it can be held alongside a second one — the clause under
#: test is "with it", and two weapons at once is what makes that clause observable. p. 90
#: gives the property to Melee weapons throughout, and the engine asserts no invariant saying
#: so — see the field's own note and #284.
WHIP = Weapon(
    id="fixture:whip",
    damage_dice=1,
    damage_sides=4,
    reach=True,
    hands_when_held=1,
)
#: The same weapon without the property, so a difference is shown to be the property's doing.
SPEAR = Weapon(
    id="fixture:spear",
    damage_dice=1,
    damage_sides=6,
    hands_when_held=1,
)
#: Held alongside the Glaive, because "with it" is the clause under test.
DAGGER = Weapon(
    id="fixture:dagger",
    damage_dice=1,
    damage_sides=4,
    light=True,
    hands_when_held=1,
)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("weapon-reach", [STRIKE])


def wielder(*held: Weapon, reach: int = DEFAULT_REACH_FEET) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=15,
        abilities={"str": 16, "dex": 12},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        reach=reach,
        hands=2,
        equipment=tuple(Carried(w, Carriage.HELD) for w in held),
        weapon_proficiencies=frozenset(w.id for w in held),
    )


def target(feet: int) -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=40,
        max_hit_points=40,
        armour_class=10,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(feet, 0, 0),
    )


def encounter(actor: Combatant, feet: int) -> EncounterState:
    return EncounterState.new([actor, target(feet)]).with_initiative({"pc": 20, "boar": 5})


def build(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 3,
    )


def offered(state: EncounterState, weapon: Weapon) -> bool:
    """Whether the read surface presents this attack at all (R18).

    The refusal lives here rather than in an exception: an attack the rules do not permit is
    never offered, so `legal_actions` is where a reach bound is observable. `_out_of_range`
    behind adjudication is the second gate on the same fact, and `swing` below reaches it.
    """
    return attack_key(weapon.id, "boar") in {a.key for a in read(state, "pc").actions}


def swing(state: EncounterState, path: Path, weapon: Weapon) -> str:
    """Declare the attack and return the ruling's status — `resolved` or `rejected`."""
    path.mkdir(parents=True, exist_ok=True)
    menu = read(state, "pc")
    ruling, _after = build(path).adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=attack_key(weapon.id, "boar")),
            rule_id=STRIKE.id,
            alternatives=menu.actions,
            read_token=menu.token,
        ),
    )
    return str(ruling.status)


# --- the attack half of the sentence ----------------------------------------------------


def test_a_reach_weapon_attacks_five_feet_further(tmp_path: Path) -> None:
    """The property's first clause. Ten feet is beyond an ordinary reach and within a Whip's,
    so this is the attack the engine would not offer at all before #316."""
    state = encounter(wielder(WHIP), 10)

    assert offered(state, WHIP)
    assert swing(state, tmp_path, WHIP) == "ruled"


def test_the_same_swing_without_the_property_is_refused(tmp_path: Path) -> None:
    """Shown to be the property's doing rather than the distance's. Same creature, same own
    reach, same ten feet — a Spear is not offered and is rejected if declared anyway."""
    state = encounter(wielder(SPEAR), 10)

    assert not offered(state, SPEAR)
    assert swing(state, tmp_path, SPEAR) == "rejected"


def test_a_reach_weapon_is_still_bounded(tmp_path: Path) -> None:
    """Fifteen feet is beyond a Whip too. A property that lifted the bound rather than raising
    it by five would pass every other test here, and this is the one that says so."""
    state = encounter(wielder(WHIP), 15)

    assert not offered(state, WHIP)
    assert swing(state, tmp_path, WHIP) == "rejected"


def test_the_bonus_belongs_to_the_weapon_and_not_the_hand_holding_it(tmp_path: Path) -> None:
    """**The test that a `Combatant.reach` of 10 would pass and should not.**

    p. 90: the weapon adds to your reach "when you attack **with it**". A creature holding a
    Whip and a Dagger reaches 10 feet with one and 5 with the other, and storing the bonus on
    the creature — the only way to express any of this before #316 — gives the Dagger 10 too.
    """
    state = encounter(wielder(WHIP, DAGGER), 10)

    assert offered(state, WHIP)
    assert not offered(state, DAGGER)
    assert swing(state, tmp_path, DAGGER) == "rejected"


def test_the_bonus_adds_to_the_creatures_own_reach(tmp_path: Path) -> None:
    """p. 90 says "adds 5 feet", and p. 186's 5 feet is a default rather than a ceiling — "a
    reach of 5 feet **unless a rule says otherwise**". A creature that already reaches 10
    reaches 15 with a Whip, and an implementation returning a flat 10 for any Reach weapon
    would *shorten* this one's reach while passing every test above."""
    assert offered(encounter(wielder(WHIP, reach=10), 15), WHIP)
    assert not offered(encounter(wielder(WHIP, reach=10), 20), WHIP)


def test_the_reported_reach_is_the_one_the_offer_was_bounded_by() -> None:
    """The read surface reports `reach` beside each attack so the agent can weigh it. Left as
    `actor.reach` it would say 5 next to an offer made at 10 — the detail contradicting the
    offer it describes, which is worse than omitting it."""
    state = encounter(wielder(WHIP, DAGGER), 10)
    detail = {a.key: a.detail for a in read(state, "pc").actions}

    assert detail[attack_key(WHIP.id, "boar")]["reach"] == 10


# --- the Opportunity Attack half, which is the clause that is easy to drop --------------

MOVER_AT = Position(0, 0, 0)
REACTOR_AT = Position(5, 0, 0)


def reactor(*held: Weapon, reach: int = DEFAULT_REACH_FEET) -> Combatant:
    held_by = wielder(*held, reach=reach)
    return Combatant(
        id="guard",
        name="Guard",
        hit_points=30,
        max_hit_points=30,
        armour_class=15,
        abilities={"str": 16, "dex": 12},
        proficiency_bonus=2,
        position=REACTOR_AT,
        reach=reach,
        hands=2,
        equipment=held_by.equipment,
        weapon_proficiencies=held_by.weapon_proficiencies,
    )


def mover() -> Combatant:
    return Combatant(
        id="mover",
        name="Mover",
        hit_points=10,
        max_hit_points=10,
        armour_class=13,
        abilities={"str": 12, "dex": 14},
        proficiency_bonus=2,
        position=MOVER_AT,
    )


def leaving(guard: Combatant, *, frm_feet: int, to_feet: int) -> tuple[Provocation, ...]:
    """Whether moving between those two points along the x axis provokes `guard` at (5, 0, 0).

    Distances from the guard are therefore `|feet - 5|`, which is worth stating once: every
    case below turns on which reach each endpoint falls inside.

    Bright Light is stated so that `can_see` answers p. 185's sight clause and these cases
    turn on reach alone. An encounter that states no light answers `UNSTATED` (0025 clause 2),
    which would withhold every offer here and make the assertions below about two things.
    """
    state = EncounterState(
        generation=0,
        combatants=(mover(), guard),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )
    return provocations(state, "mover", frm=Position(frm_feet, 0, 0), to=Position(to_feet, 0, 0))


PROVOKED = (Provocation(reactor_id="guard", mover_id="mover", withheld=None),)


def test_a_reach_weapon_extends_what_counts_as_leaving() -> None:
    """p. 90's second clause, which a build of the first alone would silently omit.

    The discriminating move has to start **outside** an ordinary reach, because the creature's
    own 5 feet is a candidate either way — so any move that leaves it provokes for both, and
    proves nothing about the property. From 8 feet out to 15: the Whip-holder had the mover in
    reach and loses it, and the Spear-holder never had it at all.
    """
    assert leaving(reactor(WHIP), frm_feet=13, to_feet=20) == PROVOKED
    assert leaving(reactor(SPEAR), frm_feet=13, to_feet=20) == ()


def test_a_reach_weapon_does_not_stop_provoking_at_its_own_reach() -> None:
    """The Whip's 10 feet is a reach it *adds*, not one it replaces (`_reaches` returns a set).

    A mover going from 5 feet to 7 leaves the wielder's own reach while staying inside the
    Whip's — and leaving a reach it could attack at is what p. 185 makes the trigger, because
    p. 191's Unarmed Strike is always available. **Taking the largest reach would report no
    provocation here**, which is the specific way a maximum gets this wrong.
    """
    assert leaving(reactor(WHIP), frm_feet=0, to_feet=12) == PROVOKED


def test_a_creature_holding_nothing_still_has_its_own_reach() -> None:
    """The creature's own reach is a candidate independently of what it holds. An
    implementation that read only held weapons would provoke nothing for an empty-handed
    guard, which is the mirror of the bug being fixed."""
    assert leaving(reactor(), frm_feet=0, to_feet=12) == PROVOKED
    assert leaving(reactor(), frm_feet=13, to_feet=20) == ()


def test_a_stowed_reach_weapon_grants_nothing() -> None:
    """p. 90 extends the reach of an attack made **with it**, and an Opportunity Attack cannot
    be made with a weapon the creature is not holding. `_reaches` reads held items for that
    reason, and a version reading all carried equipment would pass every other test here."""
    guard = reactor(WHIP)
    stowed = replace(
        guard, equipment=tuple(replace(c, carriage=Carriage.STOWED) for c in guard.equipment)
    )

    assert leaving(guard, frm_feet=13, to_feet=20) == PROVOKED
    assert leaving(stowed, frm_feet=13, to_feet=20) == ()
