"""What a Ruling says a blow came to, and whether the state agrees (#105, R5, R7).

`core.damage` had the p. 17 arithmetic right from the day it landed. What it did not have
was a way for anyone to *see* it: defences were applied inside `with_damage`, downstream of
the `Effect` a `Ruling` carries, and the `DamageOutcome` they produced was dropped on the
floor. So the ruling reported the dice and the state recorded something else.

That gap is not cosmetic, because of what reads a Ruling. R7 makes narration bounds
advisory — the engine states what may be asserted and does not enforce it — so the agent
narrates from `Effect.amount`. A creature with Immunity to Fire whose ruling says 12 gets
narrated as taking twelve points of fire damage it did not take, and the invented outcome
arrives through the one object that exists to make inventing one impossible.

So the tests here are about agreement rather than about arithmetic: the amount reported,
the hit points lost, and the number written to the ledger are one number or the fix is not
done. The arithmetic itself is `tests/test_damage_application.py`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from srd_rules_engine.core import (
    Adjudicator,
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
    read_ledger,
)
from srd_rules_engine.core.adjudicate import RULING_VERSION, Effect, EffectKind, _apply
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.memory.store import JsonMemoryStore

FIRE = DamageType.FIRE

UNDEFENDED = Defences()
IMMUNE = Defences(immunities=frozenset({FIRE}))
RESISTANT = Defences(resistances=frozenset({FIRE}))
VULNERABLE = Defences(vulnerabilities=frozenset({FIRE}))


def target(defences: Defences = UNDEFENDED, hit_points: int = 40) -> EncounterState:
    return EncounterState.new(
        [
            Combatant(
                id="troll",
                name="Troll",
                hit_points=hit_points,
                max_hit_points=40,
                armour_class=15,
                abilities={"str": 18, "dex": 13},
                proficiency_bonus=2,
                defences=defences,
            )
        ]
    )


def blow(amount: int, damage_type: DamageType | None = FIRE) -> Effect:
    return Effect(
        kind=EffectKind.DAMAGE,
        target_id="troll",
        amount=amount,
        damage_type=damage_type,
        description=f"fangs: 2d6 + 5 -> 3 + 4 + 5 = {amount}",
    )


def apply_one(state: EncounterState, effect: Effect) -> tuple[EncounterState, Effect]:
    after, landed = _apply(state, (effect,), seed=1)
    return after, landed[0]


# --- A real fight, for the end-to-end record ------------------------------------------

STRIKE = Rule(
    id="fire-blade",
    summary="An attack with a held weapon that deals Fire damage.",
    provenance=RuleProvenance.FIXTURE,
    rationale=(
        "An invented weapon. No rule value is inferred: the damage type is real (p. 180) "
        "and the dice are declared fixture, which is what a defence needs to key off."
    ),
)
#: Fire, so the target's Immunity has something to match. The dice are fixture values.
FIRE_BLADE = Weapon(name="fixture fire blade", damage_dice=2, damage_sides=6, damage_type=FIRE)
RULESET = load_fixture_ruleset("damage-reporting", [STRIKE])


def attacking_encounter(defences: Defences) -> EncounterState:
    return EncounterState.new(
        [
            Combatant(
                id="pc",
                name="Pc",
                hit_points=20,
                max_hit_points=20,
                armour_class=13,
                abilities={"str": 16, "dex": 14},
                proficiency_bonus=2,
            ),
            Combatant(
                id="troll",
                name="Troll",
                hit_points=40,
                max_hit_points=40,
                armour_class=13,
                abilities={"str": 18, "dex": 13},
                proficiency_bonus=2,
                defences=defences,
            ),
        ]
    )


def build_adjudicator(path: Path, *, seed: int) -> Adjudicator:
    return Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver(FIRE_BLADE)},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def strike_declaration(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key("troll")),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def hitting_seed(state: EncounterState, tmp_path: Path) -> int:
    """The first seed whose attack lands. Found rather than written down: the dice derive
    from the seed, so a literal would go on passing while testing something else."""
    for candidate in range(500):
        ruling, _ = build_adjudicator(tmp_path / f"probe{candidate}", seed=candidate).adjudicate(
            state, strike_declaration(state)
        )
        assert ruling.result is not None
        if ruling.result.succeeded:
            return candidate
    raise AssertionError("no seed below 500 landed the attack")


# --- The reported number is the number that happened -----------------------------------


def test_an_immune_creature_is_not_reported_as_taking_a_full_hit() -> None:
    """The reproduction from #105. The ruling said 12; the creature took nothing."""
    state = target(IMMUNE)
    after, landed = apply_one(state, blow(12))

    assert landed.amount == 0, "p. 183: Immunity means it 'doesn't affect you in any way'"
    assert after.combatant("troll").hit_points == 40, "and the hit points agree"


def test_the_reported_amount_equals_the_hit_points_actually_lost() -> None:
    """The property the whole fix is for, across all three defences and no defence at all.

    Stated as an equality rather than as four expected numbers, because the failure this
    guards against is *disagreement* between two places, not a wrong constant in one.
    """
    for defences in (UNDEFENDED, IMMUNE, RESISTANT, VULNERABLE):
        state = target(defences)
        after, landed = apply_one(state, blow(13))
        lost = 40 - after.combatant("troll").hit_points
        assert landed.amount == lost, f"{defences} reported {landed.amount}, applied {lost}"


def test_resistance_halves_the_blow_exactly_once() -> None:
    """The failure mode a pre-adjusted amount handed back to `with_damage` would produce:
    defences applied twice, 13 arriving as 3 instead of 6."""
    after, landed = apply_one(target(RESISTANT), blow(13))
    assert landed.amount == 6, "13 halved once, rounded down"
    assert after.combatant("troll").hit_points == 34


def test_vulnerability_doubles_it_and_says_so() -> None:
    after, landed = apply_one(target(VULNERABLE), blow(7))
    assert landed.amount == 14
    assert after.combatant("troll").hit_points == 26


# --- The working is visible (R5) -------------------------------------------------------


def test_the_effect_keeps_the_rolled_figure_and_shows_the_defence_that_changed_it() -> None:
    _, landed = apply_one(target(RESISTANT), blow(13))

    assert landed.rolled == 13, "what the dice came to, before the defence"
    assert landed.amount == 6, "and what the target took"
    assert "3 + 4 + 5 = 13" in landed.description, "the dice are still accounted for"
    assert "Resistance" in landed.description and "round down" in landed.description


def test_an_undefended_blow_is_left_exactly_as_it_was() -> None:
    """`rolled` is populated only when a defence really acted, so its presence means
    something. An unchanged number would otherwise carry a redundant second copy of itself.
    """
    effect = blow(13)
    _, landed = apply_one(target(), effect)

    assert landed == effect, "no defence touched it, so there is nothing to rewrite"
    assert landed.rolled is None


def test_untyped_damage_is_reported_unchanged() -> None:
    """A resolver need not name a type. An untyped amount matches no defence, so nothing
    about the report changes — including against a creature that resists a named type."""
    _, landed = apply_one(target(RESISTANT), blow(13, damage_type=None))
    assert landed.amount == 13
    assert landed.rolled is None


def test_resistance_to_all_damage_reaches_an_untyped_blow() -> None:
    """The case that makes an "already adjusted" flag unworkable: `resists_all` matches an
    amount with no type, so passing a pre-halved number with the type stripped would halve
    it a second time rather than skip the defence.
    """
    _, landed = apply_one(target(Defences(resists_all=True)), blow(13, damage_type=None))
    assert landed.amount == 6
    assert landed.rolled == 13


# --- Effects other than damage ---------------------------------------------------------


def test_a_healing_effect_passes_through_untouched() -> None:
    """Defences act on damage. Nothing here may quietly rewrite anything else."""
    healing = Effect(
        kind=EffectKind.HEALING, target_id="troll", amount=5, description="a draught: 5"
    )
    after, landed = apply_one(target(IMMUNE, hit_points=20), healing)

    assert landed == healing
    assert after.combatant("troll").hit_points == 25


def test_every_effect_comes_back_in_the_order_it_went_in() -> None:
    """The applier hands back a rewritten sequence, so losing or reordering one is the
    obvious way to break it while every individual assertion still passes."""
    effects = (blow(13), blow(4, damage_type=None), blow(9))
    _, landed = _apply(target(RESISTANT), effects, seed=1)

    assert len(landed) == 3
    assert [e.rolled for e in landed] == [13, None, 9]
    assert [e.amount for e in landed] == [6, 4, 4]


# --- The record (R5) -------------------------------------------------------------------


def test_the_ledger_records_the_type_and_the_rolled_figure(tmp_path: Path) -> None:
    """Without the damage type there is no way to recompute p. 17's arithmetic from the
    record, so the permanent account of a session was both wrong and uncheckable.

    End to end through a real adjudication rather than a hand-built payload, because the
    thing that broke was the *path* from the dice to the record, not the record's shape.
    """
    state = attacking_encounter(IMMUNE)
    seed = hitting_seed(state, tmp_path)
    ruling, after = build_adjudicator(tmp_path / "live", seed=seed).adjudicate(
        state, strike_declaration(state)
    )

    damage = [e for e in ruling.effects if e.kind is EffectKind.DAMAGE]
    assert damage, "the attack landed and dealt damage"
    assert all(e.amount == 0 for e in damage), "the target is immune to the blade's fire"
    assert after.combatant("troll").hit_points == 40, "and lost nothing"

    report = read_ledger(tmp_path / "live" / "ledger.jsonl")
    recorded: list[Mapping[str, object]] = []
    for entry in report.entries:
        if entry.type != "ruling":
            continue
        effects = entry.payload["effects"]
        assert isinstance(effects, list)
        recorded.extend(e for e in effects if e["kind"] == "damage")
    assert recorded, "the ruling reached the ledger with its damage"
    for effect in recorded:
        assert effect["damage_type"] == "fire", "the type the defence keyed off"
        assert effect["amount"] == 0, "what the target took"
        rolled = effect["rolled"]
        assert isinstance(rolled, int) and rolled > 0, "and what was rolled, to check it by"


def test_the_ruling_payload_version_moved_with_the_meaning() -> None:
    """`amount` means something different in a v3 payload than in a v2 one, so a reader
    adding up the old field gets a different total for the same fight. That is not an
    additive change and the version says so.

    The version has moved on since — 4 added the condition fields (#119) — so this pins
    "past 3" rather than "is 3". Pinning the literal would make every later payload change
    fail a test about #105's meaning change, which is not what it is checking."""
    assert RULING_VERSION >= 3


def test_the_payload_is_json_serialisable_with_the_new_fields() -> None:
    """`damage_type` is a StrEnum, and an enum member reaching the canonical form unstringed
    is the kind of thing that only fails when a ledger is written."""
    from srd_rules_engine.core.adjudicate import Ruling, Status, _ruling_payload
    from srd_rules_engine.core.read_surface import Verdict

    ruling = Ruling(
        status=Status.RULED,
        declaration=Declaration(
            actor_id="pc",
            intent=Intent(improvised=True, label="x"),
            no_test_reason="a stated amount, no test",
        ),
        alternatives_verdict=Verdict.UNVERIFIED,
        effects=(
            Effect(
                kind=EffectKind.DAMAGE,
                target_id="troll",
                amount=6,
                rolled=13,
                damage_type=FIRE,
                description="2d6 + 5 -> 13; 6 (halved, Resistance to fire, round down)",
            ),
        ),
    )
    payload = json.loads(json.dumps(_ruling_payload(ruling)))
    assert payload["effects"][0]["damage_type"] == "fire"
    assert payload["effects"][0]["rolled"] == 13
    assert payload["effects"][0]["amount"] == 6


def test_a_defence_that_returns_the_number_to_itself_still_shows_its_working() -> None:
    """Resistance and Vulnerability to the same type do not cancel (p. 17) — they halve and
    then double, which lands an even amount back on itself.

    So `rolled` records that a defence *acted*, not that the number moved. Keying it on the
    amount instead would report this blow as untouched and hide two steps the document
    walks through by name — and it would do so only for even numbers, which is the kind of
    gap that survives a test suite by never being the case anybody tried.
    """
    both = Defences(resistances=frozenset({FIRE}), vulnerabilities=frozenset({FIRE}))
    after, landed = apply_one(target(both), blow(12))

    assert landed.amount == 12, "halved to 6, doubled back to 12"
    assert landed.rolled == 12, "and a defence acted, even though the number came back"
    assert "Resistance" in landed.description and "Vulnerability" in landed.description
    assert after.combatant("troll").hit_points == 28

    odd_after, odd = apply_one(target(both), blow(13))
    assert odd.amount == 12, "13 halves to 6 and doubles to 12; the rounding is not undone"
    assert odd.rolled == 13
    assert odd_after.combatant("troll").hit_points == 28
