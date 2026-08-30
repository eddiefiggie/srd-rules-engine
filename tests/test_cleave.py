"""p. 90's Cleave: a second swing at a creature beside the first (#323).

> **Cleave.** If you hit a creature with a **melee** attack roll using this weapon, you can
> make a melee attack roll with the weapon against a second creature within 5 feet of the
> first that is also within your reach. On a hit, the second creature takes the weapon's
> damage, but don't add your ability modifier to that damage unless that modifier is negative.
> You can make this extra attack only once per turn.

Four things the document says that an implementation is likely not to:

* **Two positional tests, with different origins.** "within 5 feet of **the first**" and "also
  within **your** reach". Checking only the second offers a swing at somebody standing behind
  the attacker.
* **The trigger is a melee hit**, said twice. A Thrown weapon carrying Cleave would otherwise
  open one from across the room.
* **Its cap is its own.** "You can make **this** extra attack only once per turn" is p. 90's
  sentence, not p. 89's — so a creature may take the Light property's extra attack *and* a
  Cleave in the same turn.
* **The damage exception is p. 89's, restated.** A positive ability modifier is dropped and a
  negative one is kept.

Cleave was blocked on Reach until #316: "within your reach" is the wielder's reach *with this
weapon*, and a Glaive reaches 10 feet.
"""

from __future__ import annotations

from srd_rules_engine.core import (
    Carriage,
    Carried,
    Combatant,
    DamageDice,
    Declaration,
    EncounterState,
    Intent,
    Weapon,
    attack_key,
    attack_resolver,
    read,
)
from srd_rules_engine.core.adjudicate import Effect, EffectKind, Proposal
from srd_rules_engine.core.equipment import Multiattack
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import bonus_attack_key, cleave_attack_key

#: p. 91 gives Cleave to the Greataxe and the Halberd. A fixture, so the numbers are invented.
GREATAXE = Weapon(
    id="fixture:greataxe", damage_dice=1, damage_sides=12, cleave=True, hands_when_held=2
)
#: A Reach weapon with Cleave — p. 91's Halberd is both, and it is what makes "within your
#: reach" observable as something other than a flat 5 feet (#316).
HALBERD = Weapon(
    id="fixture:halberd",
    damage_dice=1,
    damage_sides=10,
    cleave=True,
    reach=True,
    hands_when_held=2,
)
#: The same weapon without the property, so a difference is the property's doing.
MAUL = Weapon(id="fixture:maul", damage_dice=2, damage_sides=6, hands_when_held=2)
#: Cleave on a weapon that can be thrown, which p. 90's "melee attack roll" excludes.
AXE = Weapon(
    id="fixture:throwing-axe",
    damage_dice=1,
    damage_sides=6,
    cleave=True,
    thrown=True,
    normal_range=20,
    long_range=60,
    hands_when_held=1,
)


def hewer(weapon: Weapon = GREATAXE, *, masters: bool = True, **kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 40,
        "max_hit_points": 40,
        "armour_class": 15,
        "abilities": {"str": 16, "dex": 12},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "hands": 2,
        "equipment": (Carried(weapon, Carriage.HELD),),
        "weapon_proficiencies": frozenset({weapon.id}),
        "mastery_weapons": frozenset({weapon.id}) if masters else frozenset(),
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


def foe(cid: str, at: int, aside: int = 0) -> Combatant:
    """A creature `at` feet along x and `aside` feet along y.

    The second axis is what separates Cleave's two distance tests. On a straight line the
    spread and the wielder's reach covary, so a fixture in one dimension cannot show which of
    them refused an offer — and one of them not being asked at all would look identical.
    """
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=100,
        max_hit_points=100,
        armour_class=10,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(at, aside, 0),
    )


def encounter(actor: Combatant | None = None, *foes: Combatant) -> EncounterState:
    people = [actor or hewer(), *(foes or (foe("boar", 4), foe("ogre", 5)))]
    return EncounterState.new(people).with_initiative({c.id: 20 - i for i, c in enumerate(people)})


def propose(state: EncounterState, weapon: Weapon, key: str) -> Proposal:
    return attack_resolver()(
        state=state,
        declaration=Declaration(actor_id="pc", intent=Intent(action_key=key), rule_id="attack"),
        facts={},
    )


def _effects(branch: tuple[object, ...]) -> list[Effect]:
    return [e for e in branch if isinstance(e, Effect)]


def openings(proposal: Proposal) -> list[Effect]:
    return [e for e in _effects(proposal.on_success) if e.kind is EffectKind.CLEAVE_OPENED]


def opened(state: EncounterState, weapon: Weapon = GREATAXE, first: str = "boar") -> EncounterState:
    """The state after a melee hit with that weapon opened a Cleave against `first`.

    **The attack tally moves too**, because a Cleave opening cannot exist without the attack
    roll that made it: the same hit emits `ATTACK_MADE`. Injecting only the opening builds a
    state play cannot reach, and it is not a harmless one — the Action-cost clause reads that
    tally, so a fixture missing it makes a Cleave look as though it charges the Action.
    """
    return state.with_cleave_opening("pc", weapon.id, first).with_attack_made("pc")


def keys(state: EncounterState) -> set[str]:
    return {a.key for a in read(state, "pc").actions}


# --- the opening ---------------------------------------------------------------------------


def test_a_melee_hit_opens_a_cleave() -> None:
    [effect] = openings(propose(encounter(), GREATAXE, attack_key(GREATAXE.id, "boar")))

    assert effect.target_id == "pc", "the opening is the wielder's"
    assert effect.weapon_id == GREATAXE.id
    assert effect.source_id == "boar", "and it remembers whom the swing landed on"


def test_a_weapon_without_cleave_opens_nothing() -> None:
    state = encounter(hewer(MAUL))
    assert openings(propose(state, MAUL, attack_key(MAUL.id, "boar"))) == []


def test_cleave_is_refused_to_a_wielder_with_no_feature_unlocking_it() -> None:
    """0047 clause 6: every mastery takes the gate, beside its own flag."""
    state = encounter(hewer(masters=False))
    assert openings(propose(state, GREATAXE, attack_key(GREATAXE.id, "boar"))) == []


def test_a_thrown_hit_opens_nothing() -> None:
    """ "If you hit a creature with a **melee** attack roll using this weapon". Said twice in
    one sentence, and a Thrown weapon with Cleave would otherwise open one at sixty feet."""
    from srd_rules_engine.core.read_surface import attack_throw_key

    state = encounter(hewer(AXE), foe("boar", 30), foe("ogre", 33))
    thrown = propose(state, AXE, attack_throw_key(AXE.id, "boar"))

    assert openings(thrown) == []


def test_a_cleave_swing_does_not_open_another() -> None:
    """ "You can make this extra attack only once per turn" — and a Cleave that opened a Cleave
    would chain through a whole crowd off one hit."""
    state = opened(encounter())
    assert openings(propose(state, GREATAXE, cleave_attack_key(GREATAXE.id, "ogre"))) == []


# --- the two distances -----------------------------------------------------------------


def test_the_second_creature_must_be_within_five_feet_of_the_first() -> None:
    """The test with the origin an implementation is likely to get wrong: measured from the
    creature that was hit, not from the attacker.

    A Halberd, so the wielder's reach is 10 and cannot be what refuses either case — the only
    thing separating them is the distance from the **first** creature.
    """
    near = encounter(hewer(HALBERD), foe("boar", 5), foe("ogre", 5, aside=3))
    far = encounter(hewer(HALBERD), foe("boar", 5), foe("ogre", 5, aside=8))

    assert cleave_attack_key(HALBERD.id, "ogre") in keys(opened(near, HALBERD)), "3 feet away"
    assert cleave_attack_key(HALBERD.id, "ogre") not in keys(opened(far, HALBERD)), "8, and out"


def test_the_second_creature_must_also_be_within_the_wielders_reach() -> None:
    """ "**also** within your reach". A creature beside the first but beyond the attacker is
    ineligible, and checking only the spread would offer a swing at somebody unreachable."""
    state = encounter(hewer(), foe("boar", 5), foe("ogre", 5, aside=3))

    assert cleave_attack_key(GREATAXE.id, "ogre") not in keys(opened(state)), (
        "3 feet from the first, and 5.83 from a wielder whose Greataxe reaches 5"
    )


def test_reach_is_the_wielders_reach_with_this_weapon() -> None:
    """#316's Reach, which is why this issue was blocked on it. The same geometry, and only
    the weapon differs: a Halberd reaches 10 feet and a Greataxe 5."""
    state = encounter(hewer(HALBERD), foe("boar", 5), foe("ogre", 5, aside=3))

    assert cleave_attack_key(HALBERD.id, "ogre") in keys(opened(state, HALBERD)), (
        "the same geometry the Greataxe could not reach"
    )


def test_the_first_creature_is_not_a_cleave_target() -> None:
    """ "a **second** creature". Cleaving back into the one just hit is a second swing the
    document does not grant."""
    assert cleave_attack_key(GREATAXE.id, "boar") not in keys(opened(encounter()))


# --- the cap, which is Cleave's own ----------------------------------------------------


def test_the_cleave_is_offered_until_it_is_taken() -> None:
    state = opened(encounter())

    assert cleave_attack_key(GREATAXE.id, "ogre") in keys(state)
    assert not state.has_cleaved("pc")

    taken = state.with_cleave_taken("pc")
    assert taken.has_cleaved("pc")
    assert cleave_attack_key(GREATAXE.id, "ogre") not in keys(taken)


def test_the_cap_is_spent_by_swinging_rather_than_by_hitting() -> None:
    """p. 90 caps the **attack**, not the hit, so a missed Cleave is still the one this turn
    allowed. Spent from `always`, which is the branch that runs either way."""
    proposal = propose(opened(encounter()), GREATAXE, cleave_attack_key(GREATAXE.id, "ogre"))

    assert [e.kind for e in _effects(proposal.always) if e.kind is EffectKind.CLEAVE_TAKEN] == [
        EffectKind.CLEAVE_TAKEN
    ]


def test_cleaves_cap_is_not_p89s_extra_attack_allowance() -> None:
    """**Its own sentence, so its own cap.** A creature that has already made p. 89's extra
    Light attack may still Cleave, and sharing one record would refuse one of them."""
    state = opened(encounter()).with_extra_attack("pc")

    assert state.has_taken_extra_attack("pc"), "p. 89's is spent"
    assert cleave_attack_key(GREATAXE.id, "ogre") in keys(state), "p. 90's is not"


def test_taking_the_cleave_leaves_p89s_allowance_alone() -> None:
    """The mirror. `is_extra` covers Cleave for the damage exception and the Multiattack
    tally, and an implementation reusing it for p. 89's allowance too would spend one cap by
    exercising the other."""
    proposal = propose(opened(encounter()), GREATAXE, cleave_attack_key(GREATAXE.id, "ogre"))

    assert not [e for e in _effects(proposal.always) if e.kind is EffectKind.EXTRA_ATTACK_MADE], (
        "p. 89's allowance is untouched"
    )


def test_the_allowance_returns_next_turn() -> None:
    state = opened(encounter()).with_cleave_taken("pc")

    assert not state.advanced_turn().has_cleaved("pc"), "the step to the next turn"
    assert state.cleave_openings("pc"), "precondition: an opening was recorded"
    assert state.advanced_turn().cleave_openings("pc") == (), "and the opening goes with it"


# --- what the swing deals ----------------------------------------------------------------


def _damage(effects: tuple[object, ...]) -> DamageDice:
    dice = [e for e in effects if isinstance(e, DamageDice)]
    assert len(dice) == 1
    return dice[0]


def test_the_cleave_swing_drops_a_positive_ability_modifier() -> None:
    """p. 89's exception, restated by p. 90 for this attack. Strength 16 is +3 on the ordinary
    swing and nothing on the Cleave."""
    state = opened(encounter())

    ordinary = _damage(propose(state, GREATAXE, attack_key(GREATAXE.id, "boar")).on_success)
    cleaved = _damage(propose(state, GREATAXE, cleave_attack_key(GREATAXE.id, "ogre")).on_success)

    assert ordinary.modifier == 3
    assert cleaved.modifier == 0


def test_a_negative_ability_modifier_is_kept() -> None:
    """ "**unless that modifier is negative**" — the exception is the whole of the rule, and an
    implementation that simply dropped the modifier would be wrong for every creature with a
    penalty, in the direction that helps them."""
    feeble = hewer(abilities={"str": 6, "dex": 12})
    assert feeble.modifier("str") == -2, "precondition"

    state = opened(encounter(feeble))
    cleaved = _damage(propose(state, GREATAXE, cleave_attack_key(GREATAXE.id, "ogre")).on_success)

    assert cleaved.modifier == -2


def test_the_cleave_swing_is_not_one_of_the_attack_actions_rolls() -> None:
    """p. 257 counts the rolls the Attack action **bought**, and this one was bought by a hit
    rather than by the Action — so counting it would quietly cost a Multiattack creature one
    of its own rolls."""
    state = opened(encounter(hewer(multiattack=Multiattack(attacks=2))))
    proposal = propose(state, GREATAXE, cleave_attack_key(GREATAXE.id, "ogre"))

    assert not [e for e in _effects(proposal.always) if e.kind is EffectKind.ATTACK_MADE]


def test_the_cleave_swing_spends_no_action() -> None:
    """p. 90 names no cost, and the Action was already spent on the attack that opened this
    one — the same clause p. 257's Multiattack relies on, which is what makes a Cleave free
    without a test of its own (as with Nick, #320).

    The fixture has to carry the opening attack's tally for this to mean anything: the state
    where an opening exists and no attack was ever made is one play cannot reach, and in it
    a Cleave *does* charge the Action.
    """
    state = opened(encounter())
    proposal = propose(state, GREATAXE, cleave_attack_key(GREATAXE.id, "ogre"))

    assert not [e for e in _effects(proposal.always) if e.kind is EffectKind.ACTION_SPENT]


def test_a_cleave_key_is_offered_alongside_the_ordinary_attacks() -> None:
    """The offer is an addition, not a replacement: the wielder may swing at the Cleave target
    normally instead, and the two keys differ in what they deal."""
    state = opened(encounter())

    assert {
        cleave_attack_key(GREATAXE.id, "ogre"),
        attack_key(GREATAXE.id, "ogre"),
    } <= keys(state)
    assert bonus_attack_key(GREATAXE.id, "ogre") not in keys(state), "a Greataxe is not Light"
