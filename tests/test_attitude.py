"""p. 184's Influence and the three attitudes, and the first core fact type (#142).

Two things land together and neither works without the other. Attitude is a **narrative fact
carrying mechanical weight** — the engine cannot derive whether a creature views you
favourably from anything `EncounterState` holds — so it arrives through the typed port, which
is the exact boundary R20 draws. Influence is the only rule that reads it.

The port has been built since #9 and every `FactType` in the repository was a **fixture**, so
R22's `DefaultKind` had never been applied to a core type. This is the first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import Declaration, Effect, EffectKind, Intent
from srd_rules_engine.core.attitude import (
    ATTITUDE_FACT,
    ATTITUDE_TYPE,
    CORE_FACT_TYPES,
    INFLUENCE_RULE_ID,
    Attitude,
    Reception,
    influence_dc,
    influence_resolver,
)
from srd_rules_engine.core.memory_port import DefaultKind, Provenance, Resolution, ValueKind, Writer
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 16}


def _pair(*, subject_int: int = 10) -> EncounterState:
    return EncounterState.new(
        [
            Combatant(
                id="pc",
                name="Wren",
                hit_points=20,
                max_hit_points=20,
                armour_class=13,
                abilities=ABILITIES,
                proficiency_bonus=3,
                is_player_character=True,
            ),
            Combatant(
                id="guard",
                name="Guard",
                hit_points=11,
                max_hit_points=11,
                armour_class=12,
                abilities={**ABILITIES, "int": subject_int},
                proficiency_bonus=2,
            ),
        ]
    )


def _fact(
    value: str | None, *, defaulted: DefaultKind | None, reference: str | None = None
) -> dict[str, Resolution]:
    return {
        ATTITUDE_FACT: Resolution(
            type_name=ATTITUDE_FACT,
            subject="guard",
            value=value,
            defaulted=defaulted,
            provenance=Provenance(writer=Writer.OUT_OF_BAND, reference=reference)
            if reference
            else None,
        )
    }


def _propose(  # type: ignore[no-untyped-def]
    resolver,
    state: EncounterState | None = None,
    facts: dict[str, Resolution] | None = None,
):
    return resolver(
        state=state or _pair(),
        declaration=Declaration(
            actor_id="pc",
            intent=Intent(improvised=True, label="urge the guard"),
            rule_id=INFLUENCE_RULE_ID,
        ),
        facts=facts if facts is not None else _fact("indifferent", defaulted=None),
    )


# --- The first core fact type (R22) ------------------------------------------------------


def test_the_default_is_the_documents_rather_than_the_engines() -> None:
    """#142 said this had to be checked and not assumed, and it was right to: p. 184 states
    it outright — "Indifferent is the default attitude of a monster" — so the classification
    is SRD_PRESCRIBED, not the ENGINE_CHOSEN guess it would otherwise have been."""
    assert ATTITUDE_TYPE.default_kind is DefaultKind.SRD_PRESCRIBED
    assert ATTITUDE_TYPE.default == Attitude.INDIFFERENT.value
    assert ATTITUDE_TYPE.kind is ValueKind.CHOICE
    assert set(ATTITUDE_TYPE.choices) == {"friendly", "indifferent", "hostile"}


def test_no_ruling_may_write_an_attitude() -> None:
    """p. 184's Influence changes nothing about the attitude: a successful check makes the
    monster comply, not like you. So the writer is out-of-band only, and admitting
    `Writer.RULING` would be a capability the document never exercises."""
    assert ATTITUDE_TYPE.writable_by == frozenset({Writer.OUT_OF_BAND})


def test_the_engine_now_ships_a_core_fact_type_at_all() -> None:
    """Until this, every `FactType` in the repository was a fixture, so R22's machinery had
    been exercised only by rules that do not ship."""
    assert CORE_FACT_TYPES[ATTITUDE_FACT] is ATTITUDE_TYPE


# --- p. 184's DC ---------------------------------------------------------------------------


def test_the_dc_is_the_higher_of_fifteen_and_the_intelligence_score() -> None:
    """p. 184: "a default DC equal to 15 or the monster's Intelligence score, whichever is
    higher". The **score**, not the modifier — reaching for the modifier would silently drop
    the DC by about seven for an ordinary monster."""
    assert influence_dc(3) == 15, "a floor, not a sum"
    assert influence_dc(20) == 20
    assert influence_dc(15) == 15


def test_the_proposal_carries_the_score_derived_dc() -> None:
    proposal = _propose(
        influence_resolver(subject_id="guard", reception=Reception.HESITANT),
        state=_pair(subject_int=18),
    )
    assert proposal.test is not None
    assert proposal.test.target == 18
    assert "Intelligence score" in proposal.test.target_basis


# --- The three attitudes move the check ----------------------------------------------------


@pytest.mark.parametrize(
    ("attitude", "advantage", "disadvantage"),
    [("friendly", True, False), ("indifferent", False, False), ("hostile", False, True)],
)
def test_each_attitude_does_what_its_entry_says(
    attitude: str, advantage: bool, disadvantage: bool
) -> None:
    """p. 182 gives Advantage, p. 183 Disadvantage, and p. 184's Indifferent states no effect
    on the check at all — which is what makes it the neutral case rather than a third
    modifier somebody has to invent."""
    proposal = _propose(
        influence_resolver(subject_id="guard", reception=Reception.HESITANT),
        facts=_fact(attitude, defaulted=None),
    )
    assert proposal.test is not None
    assert proposal.test.has_advantage is advantage
    assert proposal.test.has_disadvantage is disadvantage


def test_a_defaulted_attitude_cites_the_document_rather_than_the_agent() -> None:
    """R27: a ruling that consumed a fact cites it. p. 184's default is a *rule*, so a ruling
    resting on it must say the document supplied the value and not the agent."""
    proposal = _propose(
        influence_resolver(subject_id="guard", reception=Reception.HESITANT),
        facts=_fact("indifferent", defaulted=DefaultKind.SRD_PRESCRIBED),
    )
    assert any("p. 184" in claim for claim in proposal.may_claim)


# --- Two of the three branches throw no die (0027 clause 6) --------------------------------


def test_a_willing_monster_complies_with_no_check() -> None:
    """p. 184: "If your urging aligns with the monster's desires, no ability check is
    necessary; the monster fulfills your request in a way it prefers."

    It is still a Ruling. An agent deciding off its own bat that the guard stood aside has
    produced an outcome no rule resolved, which is the whole of R1."""
    proposal = _propose(influence_resolver(subject_id="guard", reception=Reception.WILLING))

    assert proposal.test is None, "p. 184 asks for no check"
    (effect,) = proposal.outcome
    assert effect.kind is EffectKind.INFLUENCED
    assert effect.amount == 1


def test_an_unwilling_monster_refuses_with_no_check() -> None:
    """p. 184: "If your urging is repugnant to the monster or counter to its alignment, no
    ability check is necessary; it doesn't comply." A refusal is an outcome too."""
    proposal = _propose(influence_resolver(subject_id="guard", reception=Reception.UNWILLING))

    assert proposal.test is None
    (effect,) = proposal.outcome
    assert effect.amount == 0
    assert any("asks for none" in claim for claim in proposal.may_not_claim)


# --- What no branch may claim --------------------------------------------------------------


def test_no_branch_lets_a_narration_move_the_attitude() -> None:
    """The finding that dissolved #142's fourth design question. p. 184 ends with the monster
    complying, never with it liking you — so nothing writes an attitude, and every branch
    says so where a narrator would otherwise fill it in."""
    for reception in Reception:
        proposal = _propose(influence_resolver(subject_id="guard", reception=reception))
        assert any("attitude changed" in claim for claim in proposal.may_not_claim), reception


def test_the_failure_branch_carries_no_effect_and_discloses_the_bar() -> None:
    """p. 184 bars urging the same way again for 24 hours, and nothing tracks it (#418). The
    branch is empty and the bounds say so, rather than the rule being silently absent."""
    proposal = _propose(influence_resolver(subject_id="guard", reception=Reception.HESITANT))

    assert proposal.on_failure == ()
    assert any("24 hours" in claim for claim in proposal.may_not_claim)


def test_an_influenced_effect_can_actually_be_applied(tmp_path: Path) -> None:
    """The bug this shipped with (#448), and the test that would have caught it.

    Every test above asserts the **proposal**. None applied one, and `_apply` raises on an
    effect kind it has no branch for — a guard added with #119, because Death had been the
    fallback and every kind added since would silently have become one. `INFLUENCED` was in
    neither the branches nor the exemption, so **every Influence ruling raised on
    adjudication.**

    Its own docstring said `_apply` "has no branch for it because there is nothing to apply —
    which is the honest shape, not an omission". True of the intent, false of the code, and
    the guard does not read docstrings.
    """
    from srd_rules_engine.core.adjudicate import _apply

    state = _pair()
    after, landed, withheld = _apply(
        state,
        (
            Effect(
                kind=EffectKind.INFLUENCED,
                target_id="guard",
                amount=1,
                description="the guard was willing",
            ),
        ),
        seed=1,
    )

    assert after == state, "p. 184 moves nothing the engine holds"
    assert len(landed) == 1, "and the compliance is still recorded"
    assert withheld == ()


def test_every_recorded_only_kind_really_changes_nothing() -> None:
    """The set is an exemption from a guard, so it needs its own guard: a kind put there by
    mistake would silently stop applying. Asserted over the whole set rather than over its
    members, so a third one added later is checked without anyone remembering to."""
    from srd_rules_engine.core.adjudicate import RECORDED_ONLY, _apply

    state = _pair()
    for kind in RECORDED_ONLY:
        after, landed, _ = _apply(
            state,
            (Effect(kind=kind, target_id="guard", amount=0, description="x"),),
            seed=1,
        )
        assert after == state, f"{kind} changed state and is not recorded-only"
        assert len(landed) == 1, f"{kind} was not recorded"
