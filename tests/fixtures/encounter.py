"""One character, one invented creature, and the harness that runs a whole fight.

The driver here is scripted in R8's sense — **no model and no network**. It chooses from
what the read surface offered, which is the only thing an agent is supposed to do, and it
does it by a fixed policy rather than by recalling rules.

That is also this harness's honest limit, and it is worth stating where the harness lives
rather than only in the plan: a scripted driver asserts exactly what it was told to, so it
cannot produce an unprompted silent skip. The slice proves the report **detects** each
defect when one is injected, not that a live agent **cannot evade** it. The second is
[#42](https://github.com/eddiefiggie/srd-rules-engine/issues/42).

Nothing here supplies a roll, a result, or a target number. The driver names an action and
a rule; everything else is the engine's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

from fixtures.ruleset import (
    ATTACK,
    CROSSING,
    FACT_TYPES,
    FIXTURE_BLADE,
    FIXTURE_FANGS,
    STEADYING,
    fixture_catalogue,
    fixture_ruleset,
)
from srd_rules_engine.core import (
    UNARMED_STRIKE_ID,
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    D20Test,
    Declaration,
    EncounterState,
    Fact,
    Intent,
    Ledger,
    Modifier,
    Proposal,
    Resolution,
    Ruling,
    Status,
    TestKind,
    attack_key,
    attack_resolver,
    attack_weapon,
    initiative_order,
)
from srd_rules_engine.core.adjudicate import SEED_BITS
from srd_rules_engine.core.read_surface import END_TURN, attack_target
from srd_rules_engine.loop.drivers import drive
from srd_rules_engine.loop.turn import (
    BlockedFactRequest,
    DeclarationRequest,
    Declared,
    FactsSupplied,
    Narrated,
    NarrationRequest,
    Request,
    Response,
    SaveAbilityChosen,
    SaveAbilityRequest,
    TurnLoop,
    TurnOutcome,
)
from srd_rules_engine.memory.store import JsonMemoryStore

#: The widest seed a ledger entry can record exactly. The engine draws inside it.
SEED_BITS_LIMIT = 2**SEED_BITS - 1

ENGINE_VERSION = "slice-engine"
SESSION_ID = "vertical-slice"

#: A hard stop on the harness, not on the rules. A fight that has not ended after this many
#: turns is a harness bug, and looping forever would report it as a hang rather than a
#: failure — which is the slower and less informative of the two.
TURN_LIMIT = 40


def character() -> Combatant:
    """Invented ability values and an invented armour value. Every number here is made up."""
    return Combatant(
        id="pc",
        name="The character",
        hit_points=24,
        max_hit_points=24,
        armour_class=14,
        abilities={"str": 16, "dex": 14, "con": 14},
        proficiency_bonus=2,
        hands=2,
        equipment=(Carried(FIXTURE_BLADE, Carriage.HELD),),
        weapon_proficiencies=frozenset({FIXTURE_BLADE.id}),
    )


def creature() -> Combatant:
    """An invented creature, so it cannot be mistaken for a transcribed stat block."""
    return Combatant(
        id="scree-hound",
        name="Scree-hound",
        hit_points=13,
        max_hit_points=13,
        armour_class=12,
        abilities={"str": 13, "dex": 12, "con": 12},
        proficiency_bonus=2,
        hands=2,
        equipment=(Carried(FIXTURE_FANGS, Carriage.HELD),),
        # p. 89: "A monster is proficient with any weapon in its stat block."
        weapon_proficiencies=frozenset({FIXTURE_FANGS.id}),
    )


def opening_state(*, seed: int) -> EncounterState:
    """The encounter with initiative rolled and applied, ready for the first turn.

    **The slice needs the player character to act first**, because every test built on this
    declares for `pc` and a state where the creature leads rejects that declaration before
    anything under test runs. That used to hold by luck: the seed the callers happened to
    pass produced the order they happened to need, and nothing said so. When #82 moved
    initiative into a band of its own, the same seed produced the other order and four
    tests failed for reasons that named neither initiative nor the seed.

    So the requirement is stated and checked here, where the message can say what to do.
    """
    start = EncounterState.new([character(), creature()])
    ordered = start.with_initiative(initiative_order(start, seed=seed))
    if ordered.combatants[0].id != "pc":
        raise AssertionError(
            f"seed {seed} puts {ordered.combatants[0].id!r} first, and this fixture is "
            "built for encounters the player character opens. Pick another seed — the "
            "order derives from the seed, so a literal stops meaning what it says the "
            "moment the derivation moves"
        )
    return ordered


# --- Resolvers ----------------------------------------------------------------------------


def _crossing(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    """AE4. The resolved fact moves the target number, and is cited with its provenance.

    The difficulty is not a constant with a fact bolted on afterwards — the fact selects it,
    and the basis says which value did the selecting. A ruling whose target number cannot be
    traced to the fact that set it is a ruling nobody can argue with after the fact.
    """
    footing = facts["footing"]
    difficulty = {"firm": 8, "uncertain": 12, "treacherous": 16}[str(footing.value)]
    provenance = footing.provenance.reference if footing.provenance else "an engine-chosen default"

    return Proposal(
        test=D20Test(
            kind=TestKind.CHECK,
            target=difficulty,
            target_basis=(
                f"invented difficulty {difficulty}, selected by footing={footing.value!r} "
                f"(from {provenance})"
            ),
            modifiers=(
                Modifier(
                    source="ability:dex",
                    value=state.combatant(declaration.actor_id).modifier("dex"),
                ),
            ),
        ),
        citations=(f"fixture:{CROSSING.id}", f"fact:footing={footing.value}"),
        may_claim=("that the crossing was attempted",),
    )


def _steadying(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    """AE3's other side: this only runs once the blocking fact has actually been supplied."""
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10"),
        citations=(f"fixture:{STEADYING.id}",),
        may_claim=("that the character held steady, or did not",),
    )


def seeds_from(root: int) -> Callable[[], int]:
    """A reproducible *sequence* of seeds, not one seed repeated.

    In production a seed comes from `secrets`, so every adjudication gets a fresh one. A
    fixture returning a constant would be reproducible and useless: every d20 in the
    session would show the same face, the fight would never miss, and the slice would
    demonstrate a fight that cannot happen. Deriving each seed from a root keeps both
    properties — the same root replays the same session, and no two rolls share a seed.
    """
    counter = count()

    def next_seed() -> int:
        material = f"{root}:{next(counter)}".encode()
        drawn = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
        # Masked to the same width the production source draws, for the same reason: a
        # wider seed has no canonical form and cannot be written to the ledger.
        return int(drawn % (SEED_BITS_LIMIT + 1))

    return next_seed


def build_adjudicator(path: Path, *, seed: int, engine: str = ENGINE_VERSION) -> Adjudicator:
    """The slice's adjudicator. One root seed, so the whole encounter is reproducible."""
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=fixture_ruleset(),
        resolvers={
            ATTACK.id: attack_resolver(),
            CROSSING.id: _crossing,
            STEADYING.id: _steadying,
        },
        fact_types=FACT_TYPES,
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl",
            engine_version=engine,
            catalogue_version=fixture_catalogue().version,
            session_id=SESSION_ID,
        ),
        catalogue=fixture_catalogue(),
        seed_source=seeds_from(seed),
    )


# `_by_actor` lived here until #258, dispatching to one of two closures by actor id so each
# combatant swung its own invented weapon. It is gone: a weapon is now something a creature
# **holds**, so `attack_resolver()` reads it off the state and one resolver serves both.
# 0040 clause 4 is why there is no wrapper around it either.


# --- The driver ---------------------------------------------------------------------------


@dataclass
class SliceDriver:
    """Chooses from what it was offered, by a fixed policy. No model, no network.

    The policy is the smallest one that produces a fight: attack the first opponent the
    read surface still lists, and end the turn when it lists none. It never names an action
    it was not offered, which is what makes an *injected* illegal declaration visible as an
    injection rather than as ordinary behaviour.
    """

    narrate: bool = True
    #: Supplied only when the engine blocks on them. This is the AE3 path: the declaration
    #: suspends, the driver is asked for exactly what is missing, and the slot resumes.
    facts: Sequence[Fact] = ()
    #: Written to the port before the encounter starts, the way a fact learned earlier in a
    #: campaign would already be there. A fact type with a default never blocks, so this is
    #: the only way such a fact can differ from its default.
    known: Sequence[Fact] = ()
    #: Injected declarations, consumed before the policy is consulted. This is how a defect
    #: gets into the run: deliberately, from the outside, and named at the call site.
    scripted: Sequence[Callable[[DeclarationRequest], Declaration]] = ()
    #: 0053. Which ability this driver picks when a save offers the target a choice, or
    #: `None` to take the first the rule offered. A test that turns on the choice sets it.
    save_ability: str | None = None
    seen: list[Ruling] = field(default_factory=list)
    narrations: list[str] = field(default_factory=list)
    _used: int = 0

    def __call__(self, request: Request) -> Response:
        if isinstance(request, DeclarationRequest):
            return Declared(self._declare(request))
        if isinstance(request, NarrationRequest):
            self.seen.append(request.ruling)
            if not self.narrate:
                return Narrated(None)
            text = _narration_for(request.ruling)
            self.narrations.append(text)
            return Narrated(text)
        if isinstance(request, SaveAbilityRequest):
            return self._choose(request)
        return self._supply(request)

    def _declare(self, request: DeclarationRequest) -> Declaration:
        if self._used < len(self.scripted):
            scripted = self.scripted[self._used]
            self._used += 1
            return scripted(request)
        return policy_declaration(request)

    def _choose(self, request: SaveAbilityRequest) -> SaveAbilityChosen:
        """0053. The fixture's policy is **the first ability the rule offered**, in the
        document's own order.

        Deliberately not the best one: a fixture that optimised would make every test read as
        though the engine had chosen, which is the behaviour 0053 exists to prevent. A test
        that cares which ability was picked says so by scripting it.
        """
        if self.save_ability is not None:
            return SaveAbilityChosen(self.save_ability)
        return SaveAbilityChosen(request.options[0].ability if request.options else None)

    def _supply(self, request: BlockedFactRequest) -> FactsSupplied:
        wanted = set(request.unresolved)
        return FactsSupplied(tuple(f for f in self.facts if f.type_name in wanted))


def policy_declaration(request: DeclarationRequest) -> Declaration:
    """Attack the first opponent still on the menu with a **weapon**; otherwise end the turn.

    The weapon qualifier arrived with #267. p. 177 offers "one attack roll with a weapon **or
    an Unarmed Strike**", and the read surface now offers both — but this fixture's ruleset is
    a fixture one, so it cannot register p. 190's SRD Unarmed Strike rule beside its invented
    weapon rule (`load_fixture_ruleset` and `load_ruleset` refuse each other's provenance).

    A driver that took the first attack offered would take the strike and be rejected for a
    rule its own ruleset does not have. That rejection is *correct* — an offer the ruleset
    cannot resolve is a deployment fact the engine reports rather than hides — so the policy
    picks what this deployment can resolve rather than the engine pretending the offer is not
    there.
    """
    offered = request.offered
    target = next(
        (
            a.key
            for a in offered.actions
            if attack_target(a.key) and attack_weapon(a.key) != UNARMED_STRIKE_ID
        ),
        None,
    )
    key = target or (END_TURN if END_TURN in offered.keys else None)

    return Declaration(
        actor_id=request.actor_id,
        intent=Intent(action_key=key) if key else Intent(improvised=True, label="waits"),
        rule_id=ATTACK.id if target else None,
        no_test_reason=None if target else "the turn is being ended, which resolves nothing",
        alternatives=offered.actions,
        read_token=offered.token,
    )


def _narration_for(ruling: Ruling) -> str:
    """Prose derived from the Ruling, which is the only thing it is allowed to describe."""
    if ruling.status is not Status.RULED or ruling.result is None:
        return "nothing was resolved"
    landed = "lands" if ruling.result.succeeded else "goes wide"
    return f"{ruling.declaration.actor_id}: the attempt {landed}"


# --- Running a whole encounter --------------------------------------------------------------


@dataclass(frozen=True)
class SliceRun:
    """What one encounter produced. The ledger is the artifact; the rest is convenience."""

    ledger: Path
    state: EncounterState
    outcomes: tuple[TurnOutcome, ...]
    driver: SliceDriver

    @property
    def finished(self) -> bool:
        return any(c.is_down for c in self.state.combatants)


def run_encounter(
    path: Path,
    *,
    seed: int = 10,
    driver: SliceDriver | None = None,
    engine: str = ENGINE_VERSION,
    budget: int | None = 3,
    situation: Mapping[str, object] | None = None,
) -> SliceRun:
    """Run turns until a combatant reaches 0 hit points, or the harness's limit trips.

    Downed combatants are skipped rather than asked to act: the read surface offers them
    nothing, so a turn spent on one would be a declaration with no legal answer.
    """
    driver = driver or SliceDriver()
    adjudicator = build_adjudicator(path, seed=seed, engine=engine)
    for fact in driver.known:
        adjudicator.port.put(fact)
    loop = TurnLoop(adjudicator=adjudicator, budget=budget)

    state = opening_state(seed=seed)
    outcomes: list[TurnOutcome] = []

    for _ in range(TURN_LIMIT):
        if any(c.is_down for c in state.combatants):
            break
        actor = state.active_id
        assert actor is not None, "the encounter has initiative, so someone is active"

        outcome = drive(loop.run(state, actor, situation=situation or {}), driver)
        outcomes.append(outcome)
        state = outcome.state

        if loop.owes_narration(actor):
            # R29 gates the next declaration for this actor. The harness stops rather than
            # walking into the exception, so a withheld narration shows up as a short
            # encounter with a flagged turn — not as a crash in the driver.
            break
        state = _next_actor(state)

    return SliceRun(
        ledger=path / "ledger.jsonl", state=state, outcomes=tuple(outcomes), driver=driver
    )


def _next_actor(state: EncounterState) -> EncounterState:
    """Advance past anyone who cannot act. Each advance moves the generation."""
    for _ in range(len(state.combatants)):
        state = state.advanced_turn()
        active = state.active_id
        if active is not None and not state.combatant(active).is_down:
            return state
    return state


# --- Injections, each one a named defect ------------------------------------------------------


def claims_no_test(request: DeclarationRequest) -> Declaration:
    """An improvised action declared as needing no test. Collides with the hazard row."""
    return Declaration(
        actor_id=request.actor_id,
        intent=Intent(improvised=True, label="I pick my way across the scree, I'm sure-footed"),
        no_test_reason="the character is athletic, so no test is needed",
        alternatives=request.offered.actions,
        read_token=request.offered.token,
    )


def crosses_properly(request: DeclarationRequest) -> Declaration:
    """The corrected resubmission: the same intent, now naming a rule."""
    return Declaration(
        actor_id=request.actor_id,
        intent=Intent(improvised=True, label="I pick my way across the scree"),
        rule_id=CROSSING.id,
        alternatives=request.offered.actions,
        read_token=request.offered.token,
    )


def needs_nerve(request: DeclarationRequest) -> Declaration:
    """Names a rule consuming a fact with no honest default, so the engine must block."""
    return Declaration(
        actor_id=request.actor_id,
        intent=Intent(improvised=True, label="I hold my ground"),
        rule_id=STEADYING.id,
        alternatives=request.offered.actions,
        read_token=request.offered.token,
    )


def with_a_stale_token(request: DeclarationRequest) -> Declaration:
    """The policy's declaration, carrying a token from a generation that has moved on."""
    honest = policy_declaration(request)
    return Declaration(
        actor_id=honest.actor_id,
        intent=honest.intent,
        rule_id=honest.rule_id,
        no_test_reason=honest.no_test_reason,
        alternatives=honest.alternatives,
        read_token="rt1.0.0000000000000000000000000000000",
    )


__all__ = [
    "ENGINE_VERSION",
    "SESSION_ID",
    "SliceDriver",
    "SliceRun",
    "attack_key",
    "build_adjudicator",
    "character",
    "claims_no_test",
    "creature",
    "crosses_properly",
    "needs_nerve",
    "opening_state",
    "policy_declaration",
    "run_encounter",
    "with_a_stale_token",
]
