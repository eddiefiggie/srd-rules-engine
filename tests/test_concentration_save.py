"""The fourth occasion: the Concentration save damage compels (p. 179, 0036).

`concentration_save_dc` has implemented p. 179's arithmetic since #19 and nothing rolled it.
The rule was never missing — only the moment it applies — and the moment is what this file
pins.

Three things here are easy to get wrong, and the engine that gets each of them wrong reads
exactly like the engine that gets them right:

* **Two damage instances owe two saves.** The obvious implementation reuses
  `EncounterState.discharged`, which is keyed `(actor_id, rule_id)` and cleared once per
  turn. A creature struck twice by a Multiattack would then roll one save and the second
  would silently not happen — a skip, invisible in play, because a save that was never
  rolled leaves the spell up exactly as a successful one does.
* **Damage lands in three phases, not one.** Burning deals its damage at the *start* of a
  turn (p. 178), so a design that discharged only after the declaration slot would serve
  every attack and miss the hazard — and the hazard has no attacker to make the gap obvious.
* **The save is owed by whoever took the damage**, who is usually not the creature whose
  turn it is. An attack on the monster's turn breaks the *player's* Concentration.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    BURNING_RULE_ID,
    CONCENTRATION_RULE_ID,
    Adjudicator,
    Combatant,
    Declaration,
    EffectKind,
    EncounterState,
    ForcedSave,
    Intent,
    Ledger,
    Rule,
    RuleProvenance,
    Ruling,
    Status,
    burning_resolver,
    burning_rule,
    concentration_resolver,
    concentration_rule,
    falling_resolver,
    load_ruleset,
    read_ledger,
)
from srd_rules_engine.core.hazards import FALLING_VERIFICATION
from srd_rules_engine.core.inventory import ENGINE_SHAPES, load_inventory
from srd_rules_engine.core.spellcasting import Concentration, concentration_save_dc
from srd_rules_engine.loop import Narrated, NarrationRequest, TurnLoop
from srd_rules_engine.loop.drivers import ScriptedDriver, drive
from srd_rules_engine.loop.turn import DeclarationRequest, Declared, TurnOutcome
from srd_rules_engine.memory.store import JsonMemoryStore

#: p. 182's fall, as a rule a ruleset registers. `core.hazards` ships the resolver and the
#: verification but no rule constructor, because the distance is the caller's: a fall of a
#: stated height is what a ruleset declares. SRD provenance, because falling is an SRD rule
#: verified against p. 182 — the *distance* is the situation, not an invented mechanic.
FALL_RULE_ID = "falling"
FALL_FEET = 20

FALL = Rule(
    id=FALL_RULE_ID,
    summary="A falling creature takes 1d6 Bludgeoning damage per 10 feet fallen, to 20d6.",
    provenance=RuleProvenance.SRD,
    verification=FALLING_VERIFICATION,
)

RULESET = load_ruleset((concentration_rule(), burning_rule(), FALL))


def caster(*, spell: str | None = "bless", burning: bool = False) -> Combatant:
    mage = Combatant(
        id="mage",
        name="Mage",
        hit_points=40,
        max_hit_points=40,
        armour_class=12,
        abilities={"str": 8, "dex": 12, "con": 14},
        proficiency_bonus=2,
        is_player_character=True,
        concentration=Concentration(rule_id=spell),
    )
    return mage if not burning else _burning(mage)


def _burning(mage: Combatant) -> Combatant:
    from dataclasses import replace

    return replace(mage, hazards=replace(mage.hazards, burning=True))


def boar() -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=11,
        abilities={"str": 12, "dex": 10, "con": 12},
        proficiency_bonus=2,
    )


def encounter(**kwargs: object) -> EncounterState:
    state = EncounterState.new([caster(**kwargs), boar()])  # type: ignore[arg-type]
    return state.with_initiative({"mage": 15, "boar": 5})


def build_loop(path: Path, *, seed: int = 3, rules: Sequence[Rule] | None = None) -> TurnLoop:
    """A loop over the real p. 179 rule, not a fixture one."""
    path.mkdir(parents=True, exist_ok=True)
    ruleset = RULESET if rules is None else load_ruleset(rules)
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=ruleset,
            resolvers={
                CONCENTRATION_RULE_ID: concentration_resolver(),
                BURNING_RULE_ID: burning_resolver(),
                FALL_RULE_ID: falling_resolver(FALL_FEET),
            },
            fact_types={},
            port=JsonMemoryStore(path / "memory.json"),
            ledger=Ledger.open(
                path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            seed_source=lambda: seed,
        )
    )


def falls(actor: str = "mage") -> Declaration:
    """A declaration that deals damage to the creature making it."""
    return Declaration(
        actor_id=actor,
        intent=Intent(improvised=True, label=f"falls {FALL_FEET} feet"),
        rule_id=FALL_RULE_ID,
    )


def take_turn(loop: TurnLoop, state: EncounterState, actor: str = "mage") -> TurnOutcome:
    return drive(
        loop.run(state, actor),
        ScriptedDriver(
            declarations=[falls(actor)],
            narrations=["it happened"] * 8,
        ),
    )


def narrated(loop: TurnLoop, state: EncounterState, actor: str) -> tuple[Ruling, ...]:
    """Drive `end_turn`, answering every narration, and hand back the rulings it produced."""
    end = drive(
        loop.end_turn(state, actor),
        ScriptedDriver(narrations=["it happened"] * 8),
    )
    return end.rulings


def damage_taken(ruling: Ruling) -> int:
    return sum(e.amount for e in ruling.effects if e.kind is EffectKind.DAMAGE)


def hurt(state: EncounterState, amount: int, who: str = "mage") -> EncounterState:
    return state.with_damage(who, amount)


# --- The occasion exists at all ---------------------------------------------------------


def test_damage_in_a_declaration_slot_compels_the_save_in_the_same_slot(tmp_path: Path) -> None:
    """p. 179: "If you take damage, you must succeed on a Constitution saving throw to
    maintain Concentration." The arithmetic was built in #19 and rolled by nothing."""
    loop = build_loop(tmp_path)
    outcome = take_turn(loop, encounter())

    assert outcome.ruling is not None
    assert outcome.ruling.rule_id == FALL_RULE_ID
    assert [r.rule_id for r in outcome.consequential] == [CONCENTRATION_RULE_ID]
    assert outcome.consequential[0].declaration.actor_id == "mage"


def test_the_dc_is_derived_from_that_instances_damage(tmp_path: Path) -> None:
    """p. 179: "The DC equals 10 or half the damage taken (round down), whichever number is
    higher, up to a maximum DC of 30." The *instance's* damage, which is why the debt
    carries it: by now the creature's hit points have already moved (0036 clause 4)."""
    loop = build_loop(tmp_path)
    outcome = take_turn(loop, encounter())

    save = outcome.consequential[0]
    assert outcome.ruling is not None
    assert save.result is not None
    assert save.result.target == concentration_save_dc(damage_taken(outcome.ruling))


def test_a_creature_concentrating_on_nothing_owes_no_save(tmp_path: Path) -> None:
    outcome = take_turn(build_loop(tmp_path), encounter(spell=None))

    assert outcome.ruling is not None
    assert damage_taken(outcome.ruling) > 0, "precondition: the fall hurt"
    assert outcome.consequential == ()


def test_damage_that_a_defence_absorbs_entirely_compels_nothing(tmp_path: Path) -> None:
    """0036 clause 5. p. 179 says "the damage taken", so a creature that took none owes
    none — and `with_damage` already reasons this way for the death-save failure."""
    state = encounter()
    assert hurt(state, 0).forced_saves_owed == ()


# --- Finding 2: once per instance, not once per turn -------------------------------------


def test_two_damage_instances_compel_two_saves(tmp_path: Path) -> None:
    """The case that decided the design. Keyed the way every other obligation is keyed —
    `(actor_id, rule_id)` in `discharged`, cleared once per turn — the second save is
    suppressed and silently never rolled."""
    state = hurt(hurt(encounter(), 8), 30)
    assert len(state.forced_saves_owed) == 2, "precondition: two debts"

    rulings = narrated(build_loop(tmp_path), state, "mage")

    assert [r.rule_id for r in rulings] == [CONCENTRATION_RULE_ID, CONCENTRATION_RULE_ID]
    # Oldest first, and each against its own instance's DC rather than a shared one.
    targets = [r.result.target for r in rulings if r.result is not None]
    assert targets == [concentration_save_dc(8), concentration_save_dc(30)]


def test_the_saves_never_touch_the_once_per_turn_record(tmp_path: Path) -> None:
    """0036 clause 3. `discharged` is left exactly as it is: widening it to carry a count
    would make every obligation's semantics depend on a field one rule uses."""
    state = hurt(encounter(), 12)
    end = drive(
        build_loop(tmp_path).end_turn(state, "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert end.state.forced_saves_owed == ()
    assert not any(rule == CONCENTRATION_RULE_ID for _, rule in end.state.discharged)


def test_a_debt_survives_a_turn_advance(tmp_path: Path) -> None:
    """The debt is not once per turn, so the turn advance that clears `discharged` must
    leave it alone. Every neighbouring structure resets there, which is what makes this the
    case most likely to be got wrong by reflex."""
    state = hurt(encounter(), 12)
    advanced = state.advanced_turn()

    assert [(d.combatant_id, d.rule_id, d.dc) for d in advanced.forced_saves_owed] == [
        ("mage", CONCENTRATION_RULE_ID, 10)
    ], "10 or half of 12 (p. 179)"


# --- Finding 4: three phases deal damage -------------------------------------------------


def test_burning_at_the_turns_start_compels_the_save_there(tmp_path: Path) -> None:
    """p. 178: "A burning creature takes 1d4 Fire damage at the start of each of its
    turns." A design that discharged only after the declaration slot would serve every
    attack in the game and miss this one."""
    start = drive(
        build_loop(tmp_path).start_turn(encounter(burning=True), "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert [r.rule_id for r in start.rulings] == [BURNING_RULE_ID, CONCENTRATION_RULE_ID]
    assert start.state.forced_saves_owed == ()


def test_a_phase_with_no_obligations_of_its_own_still_drains_the_queue(tmp_path: Path) -> None:
    """The drain is at the top of each pass, so the pass that finds nothing pending — and
    every pass of a phase that never had anything pending — still discharges."""
    state = hurt(encounter(), 12)
    assert build_loop(tmp_path).end_turn_obligations(state, "mage") == ()

    assert [r.rule_id for r in narrated(build_loop(tmp_path), state, "mage")] == [
        CONCENTRATION_RULE_ID
    ]


# --- Finding 3: owed by the target, not the actor ----------------------------------------


def test_the_save_is_rolled_for_whoever_took_the_damage(tmp_path: Path) -> None:
    """An attack on the monster's turn breaks the *player's* Concentration. Obligations are
    enumerated for the creature whose turn it is; this one is not."""
    state = hurt(encounter(), 12)
    rulings = narrated(build_loop(tmp_path), state, "boar")

    assert [r.declaration.actor_id for r in rulings] == ["mage"]


def test_the_narration_is_asked_for_on_the_targets_behalf(tmp_path: Path) -> None:
    """R29. The bounds belong to whoever the ruling is about, so the debt is the target's
    and the loop refuses *their* next declaration until it is filled."""
    loop = build_loop(tmp_path)
    generator = loop.end_turn(hurt(encounter(), 12), "boar")
    request = next(generator)

    assert isinstance(request, NarrationRequest)
    assert request.ruling.declaration.actor_id == "mage"
    with pytest.raises(StopIteration):
        generator.send(Narrated(text=None))
    assert loop.owes_narration("mage")
    assert not loop.owes_narration("boar")


# --- What the save decides ---------------------------------------------------------------


def seed_where_save(*, fails: bool, tmp_path: Path) -> int:
    """The first seed whose Concentration save fails, or succeeds. Found, never hardcoded."""
    state = hurt(encounter(), 12)
    for candidate in range(500):
        rulings = narrated(
            build_loop(tmp_path / f"probe{candidate}", seed=candidate), state, "mage"
        )
        result = rulings[0].result
        assert result is not None
        if result.succeeded is not fails:
            return candidate
    raise AssertionError("no seed below 500 produced the wanted outcome")


def test_a_failed_save_ends_the_concentration(tmp_path: Path) -> None:
    """p. 179's one consequence, and the only one it states. Reached through a ruling, so
    the roll is what decides it (R1, R4) and the ledger carries the reason."""
    seed = seed_where_save(fails=True, tmp_path=tmp_path)
    end = drive(
        build_loop(tmp_path / "run", seed=seed).end_turn(hurt(encounter(), 12), "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert end.rulings[0].effects[0].kind is EffectKind.CONCENTRATION_ENDED
    assert not end.state.combatant("mage").concentration.active


def test_a_successful_save_leaves_the_spell_up_and_costs_nothing(tmp_path: Path) -> None:
    """p. 179 states no consequence for a success, so the ruling applies none. Anything
    here would be a benefit the document does not grant."""
    seed = seed_where_save(fails=False, tmp_path=tmp_path)
    end = drive(
        build_loop(tmp_path / "run", seed=seed).end_turn(hurt(encounter(), 12), "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert end.rulings[0].effects == ()
    assert end.state.combatant("mage").concentration == Concentration(rule_id="bless")


def test_a_creature_whose_concentration_already_broke_owes_no_further_save(
    tmp_path: Path,
) -> None:
    """Two debts, and the first save fails. p. 179 compels the save *to maintain*
    Concentration, and there is nothing left to maintain — so the second debt is dropped
    rather than rolled. Not a skip: the outcome it would decide is already settled."""
    seed = seed_where_save(fails=True, tmp_path=tmp_path)
    state = hurt(hurt(encounter(), 12), 12)
    end = drive(
        build_loop(tmp_path / "run", seed=seed).end_turn(state, "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert len(end.rulings) == 1
    assert end.state.forced_saves_owed == ()


def test_incapacitated_ends_it_before_the_save_is_ever_rolled(tmp_path: Path) -> None:
    """p. 179: "Your Concentration ends if you have the Incapacitated condition."

    The drain reads the stored field, which since #238 is where the end is written — so
    state, the read surface and this all give one answer because there is one answer, rather
    than because three callers remembered to derive it the same way."""
    from srd_rules_engine.core import Condition

    state = hurt(encounter(), 12).with_condition("mage", Condition.INCAPACITATED)
    assert narrated(build_loop(tmp_path), state, "mage") == ()


# --- R30: the record, and R7's bounds ----------------------------------------------------


def test_the_ledger_records_the_save_beside_the_damage_that_forced_it(tmp_path: Path) -> None:
    """R30's report derives from the ledger without the agent's cooperation, so a ruling
    nobody declared has to leave a trace of its own."""
    loop = build_loop(tmp_path)
    take_turn(loop, encounter())

    entries = read_ledger(tmp_path / "ledger.jsonl").entries
    rules = [e.payload.get("rule_id") for e in entries if e.type == "ruling"]
    assert rules.count(FALL_RULE_ID) == 1
    assert rules.count(CONCENTRATION_RULE_ID) == 1


def test_the_save_carries_narration_bounds_of_its_own(tmp_path: Path) -> None:
    """R7/R29. Advisory to the caller, and they still have to reach it — an obligation
    nobody declared is exactly the ruling a narrator has least context for."""
    outcome = take_turn(build_loop(tmp_path), encounter())
    bounds = outcome.consequential[0].bounds

    assert any("bless" in claim for claim in bounds.may)
    assert any("bless" in claim for claim in bounds.may_not)


def test_the_declaration_is_the_engines_and_is_marked_improvised(tmp_path: Path) -> None:
    """0023 clause 2. A `Declaration` is the artefact the *agent* is accountable for, and
    this one is not the agent's — p. 179 compels the save rather than offering it."""
    outcome = take_turn(build_loop(tmp_path), encounter())
    declaration = outcome.consequential[0].declaration

    assert declaration.intent.improvised
    assert declaration.read_token is None
    assert "Concentration" in (declaration.intent.label or "")


# --- A ruleset that cannot resolve it ----------------------------------------------------


def test_a_ruleset_without_the_rule_names_the_gap_rather_than_dropping_the_save(
    tmp_path: Path,
) -> None:
    """A deployment fact, named the way `TurnEnd.unresolvable` names one. A save that
    silently did not happen is the failure this engine exists to prevent, so the drain
    reports the obligation it could not resolve rather than swallowing it."""
    loop = build_loop(tmp_path, rules=[burning_rule(), FALL])
    end = drive(
        loop.end_turn(hurt(encounter(), 12), "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert end.rulings == ()
    assert [o.rule_id for o in end.unresolvable] == [CONCENTRATION_RULE_ID]
    assert end.state.forced_saves_owed == (), "the debt is dropped, not spun on"


def test_the_declaration_slot_reports_an_unresolvable_save_too(tmp_path: Path) -> None:
    """`TurnOutcome.unresolvable` is the same field, the same meaning and the same type as
    on `TurnStart` and `TurnEnd` — not to be read as `unresolved`, which is the fact types
    a blocked declaration could not obtain."""
    loop = build_loop(tmp_path, rules=[burning_rule(), FALL])
    outcome = take_turn(loop, encounter())

    assert outcome.consequential == ()
    assert [o.rule_id for o in outcome.unresolvable] == [CONCENTRATION_RULE_ID]


def test_a_missing_narration_on_a_compelled_save_is_reported(tmp_path: Path) -> None:
    """R29. A narration that never arrives is a named state, not a silent hole — and the
    compelled save is the one a driver is most likely to leave unnarrated."""
    loop = build_loop(tmp_path)
    state = encounter()
    outcome = drive(
        loop.run(state, "mage"),
        ScriptedDriver(declarations=[falls()], narrations=["the ground rose", None]),
    )

    assert outcome.narration == "the ground rose"
    assert outcome.consequential_narrations == (None,)
    assert outcome.missing_narration


def test_the_agents_declaration_is_answered_once(tmp_path: Path) -> None:
    """The fourth occasion takes the existing path; it does not open a second declaration
    slot. A drain that asked the agent again would be offering a decision p. 179 compels."""
    loop = build_loop(tmp_path)
    state = encounter()
    asked: list[str] = []

    def driver(request: object) -> object:
        if isinstance(request, DeclarationRequest):
            asked.append("declaration")
            return Declared(falls())
        assert isinstance(request, NarrationRequest)
        return Narrated(text="it happened")

    drive(loop.run(state, "mage"), driver)  # type: ignore[arg-type]
    assert asked == ["declaration"]


def test_the_status_of_a_compelled_save_is_an_outcome(tmp_path: Path) -> None:
    outcome = take_turn(build_loop(tmp_path), encounter())
    assert outcome.consequential[0].status is Status.RULED


# --- KTD7: the claim, made honest and kept that way ---------------------------------------


def test_the_claimed_concentration_shape_is_reachable_in_play(tmp_path: Path) -> None:
    """R17, and the guard 0036 clause 8 exists to install.

    `ENGINE_SHAPES` has claimed `concentration` and `effect_shapes.json` has marked it
    implemented since #19, while `Concentration` was referenced nowhere in `src/` outside its
    own module — no `Combatant` field held one, so nothing in an encounter could be
    concentrating and the shape's stated consequence could not occur. The claim was true only
    by assertion, and it survived because nothing checked.

    **The assertion here is behavioural on purpose.** A guard asserting that something
    *calls* `Concentration` is satisfied by a call that does nothing, which is the state this
    replaces. So it drives the real loop and asserts that the shape's own entry's stated
    consequence — p. 179's save, and the Concentration it ends — actually happens.
    """
    assert "concentration" in ENGINE_SHAPES, "precondition: the shape is claimed"
    shape = load_inventory().by_id("concentration")
    assert shape is not None and shape.implemented, "precondition: the inventory agrees"

    seed = seed_where_save(fails=True, tmp_path=tmp_path)
    end = drive(
        build_loop(tmp_path / "reach", seed=seed).end_turn(hurt(encounter(), 12), "mage"),
        ScriptedDriver(narrations=["it happened"] * 8),
    )

    assert [r.rule_id for r in end.rulings] == [CONCENTRATION_RULE_ID], (
        "the claimed `concentration` shape is unreachable in play again. p. 179's damage "
        "save is the consequence its own entry states, and a claim nothing can exercise is "
        "the decay 0036 clause 8 recorded"
    )
    assert not end.state.combatant("mage").concentration.active


# --- #238: p. 179 says ends, and the engine said suspends ---------------------------------


def concentrating(**kwargs: object) -> EncounterState:
    """An encounter whose mage is concentrating, for the routes that end it."""
    return encounter(**kwargs)


def test_concentration_does_not_come_back_when_incapacitated_lifts() -> None:
    """#238. p. 179: "Your Concentration **ends** if you have the Incapacitated condition."

    Ends, not suspends. `after_conditions` recomputed the answer from the conditions held at
    the moment somebody asked, and nothing wrote the field — so the condition lifting handed
    the spell back. A derivation cannot record an event, which is why 0037 clause 4
    materialises the end rather than repairing the derivation.
    """
    from srd_rules_engine.core import Condition

    state = concentrating().with_condition("mage", Condition.INCAPACITATED)
    assert not state.combatant("mage").concentration.active, "the end is written, not derived"

    lifted = state.with_condition_ended("mage", Condition.INCAPACITATED)
    assert not lifted.combatant("mage").concentration.active, (
        "p. 179 spends Concentration on the condition arriving. A spell that returns when "
        "the condition lifts is a spell the document already ended (#238)"
    )


def test_no_save_is_owed_for_a_spell_that_already_ended() -> None:
    """#238's consequence, and the half that reaches an outcome.

    `with_damage` asked the same derivation deliberately, so that state and the read surface
    would agree about who is concentrating. They agreed and were wrong together: after the
    condition lifted, damage compelled a Constitution save to maintain a spell p. 179 had
    already ended — a save that can **fail**, arriving through the one adjudication entry
    point with a Ruling, a seed and a ledger entry behind it.
    """
    from srd_rules_engine.core import Condition

    state = concentrating().with_condition("mage", Condition.INCAPACITATED)
    lifted = state.with_condition_ended("mage", Condition.INCAPACITATED)

    assert lifted.with_damage("mage", 12).forced_saves_owed == ()


def test_a_creature_killed_outright_is_not_concentrating() -> None:
    """p. 179: "Incapacitated **or Dead**." Death is not one of the fifteen conditions, so a
    conditions-only derivation could not see it at all (0037 clause 4).

    p. 17 kills a monster the instant it drops to 0, so it never acquires Unconscious on the
    way — the route where the gap is reachable rather than merely present.
    """
    state = concentrating().with_death("mage")
    assert not state.combatant("mage").concentration.active


def test_a_monster_dropped_to_zero_stops_concentrating_by_the_same_route() -> None:
    """`with_damage` kills a monster outright (p. 17) and reaches `with_death` to do it, so
    the end travels with the death rather than needing a second call."""
    from dataclasses import replace

    monster = replace(caster(), id="ogre", name="Ogre", is_player_character=False)
    state = EncounterState.new([monster, boar()]).with_initiative({"ogre": 12, "boar": 5})

    dead = state.with_damage("ogre", 40)
    assert dead.combatant("ogre").death_saves.dead, "precondition: p. 17 killed it outright"
    assert not dead.combatant("ogre").concentration.active


def test_the_voluntary_end_costs_nothing_and_is_not_offered_as_an_action() -> None:
    """p. 179: "The creator can end Concentration at any time **(no action required)**."

    Not a declaration and not a `LegalAction`: the read surface enumerates what a creature may
    do **on its turn**, and this is neither turn-bound nor an action. A slot in which it were
    expressible would price something the document gives outright.
    """
    from srd_rules_engine.core import read

    state = concentrating()
    offered = read(state, "mage")
    assert not any("concentrat" in action.key for action in offered.actions)

    ended = state.with_concentration_ended("mage")
    assert not ended.combatant("mage").concentration.active
    assert ended.combatant("mage").actions == state.combatant("mage").actions


def test_ending_concentration_twice_is_not_an_error() -> None:
    """Idempotent, because three routes can reach it and none of them can see the others."""
    state = concentrating().with_concentration_ended("mage")
    assert not state.with_concentration_ended("mage").combatant("mage").concentration.active


def test_a_creature_killed_by_the_blow_does_not_roll_the_save_it_owed(tmp_path: Path) -> None:
    """The debt is recorded before the death, and dropped rather than rolled.

    `with_damage` reads who is concentrating from the combatant as it was *before* the blow,
    which is correct — p. 179's DC derives from the damage taken, and the creature was
    concentrating when it was taken. The death then ends the Concentration (0037 clause 4),
    so by the time the loop drains the queue there is nothing left to maintain and the debt
    is dropped.

    Worth pinning because the alternative reads as reasonable and is not: a dead creature
    making a Constitution save to keep a spell up is an outcome for a creature p. 17 has
    already removed from the fight.
    """
    from dataclasses import replace as _replace

    monster = _replace(caster(), id="ogre", name="Ogre", is_player_character=False)
    state = EncounterState.new([monster, boar()]).with_initiative({"ogre": 12, "boar": 5})

    killed = state.with_damage("ogre", 40)
    assert killed.combatant("ogre").death_saves.dead
    assert killed.forced_saves_owed, "precondition: the debt was recorded by the blow"

    rulings = narrated(build_loop(tmp_path), killed, "boar")
    assert rulings == (), "the dead do not roll to maintain Concentration"
    assert killed.with_damage("ogre", 5).forced_saves_owed == killed.forced_saves_owed


# --- one queue, two rules (0048) ---------------------------------------------------------


def test_the_resolver_refuses_a_debt_belonging_to_another_rule() -> None:
    """0048 clause 2. One queue serves every forced save, so each resolver checks that the
    debt in front of it is its own.

    Reached only if the loop and the rule have come apart — and that is exactly when rolling
    the wrong save would be least visible, because a Constitution save against somebody
    else's DC looks like a Constitution save.
    """
    state = encounter().with_forced_save(
        ForcedSave(
            combatant_id="mage",
            rule_id="mastery-topple",
            ability="con",
            dc=13,
            dc_basis="a fixture",
            label="makes a Constitution save or falls Prone",
        )
    )

    with pytest.raises(ValueError, match=r"not p\. 179's"):
        concentration_resolver()(
            state=state,
            declaration=Declaration(
                actor_id="mage",
                intent=Intent(improvised=True, label="maintains Concentration"),
                rule_id=CONCENTRATION_RULE_ID,
            ),
            facts={},
        )
