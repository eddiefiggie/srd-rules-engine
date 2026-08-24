"""The loader is the guard most likely to be quietly wrong.

A loader that admits everything passes every test that only checks the happy path, so the
refusals are what this file is mostly about — and each of them is proven red by mutation
rather than assumed.

Two loaders, not one branch. `load_ruleset` refuses a fixture outright and
`load_fixture_ruleset` refuses an SRD-derived rule outright, so loosening either cannot
make an unverified SRD entry admissible. That shape is the point: correctness was never
the weak spot, but a single loader with a strict arm and a lenient arm reads as an
inconsistency, and the natural repair removes the strictness.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from srd_rules_engine.core.rules import (
    Rule,
    RuleLoadError,
    RuleProvenance,
    Ruleset,
    Verification,
    VerificationState,
    load_fixture_ruleset,
    load_ruleset,
)

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

VERIFIED = Verification(
    state=VerificationState.VERIFIED,
    reference="Playing the Game > D20 Tests",
    date="2026-08-22",
)


def srd_rule(rule_id: str = "d20-test", **overrides: object) -> Rule:
    fields: dict[str, object] = {
        "id": rule_id,
        "summary": "Roll 1d20, add modifiers, compare to a target number.",
        "provenance": RuleProvenance.SRD,
        "verification": VERIFIED,
    }
    fields.update(overrides)
    return Rule(**fields)  # type: ignore[arg-type]


def fixture_rule(rule_id: str = "invented-check", **overrides: object) -> Rule:
    fields: dict[str, object] = {
        "id": rule_id,
        "summary": "An invented check, used only to exercise the machinery.",
        "provenance": RuleProvenance.FIXTURE,
        "rationale": "Gives the vertical slice something to adjudicate without SRD content.",
    }
    fields.update(overrides)
    return Rule(**fields)  # type: ignore[arg-type]


# --- What loads ---------------------------------------------------------------------


def test_a_verified_srd_rule_loads() -> None:
    ruleset = load_ruleset([srd_rule()])
    assert len(ruleset) == 1
    assert ruleset.rule("d20-test").is_verified


def test_a_fixture_loads_into_a_named_fixture_ruleset() -> None:
    ruleset = load_fixture_ruleset("slice", [fixture_rule()])
    assert ruleset.name == "slice"
    assert ruleset.provenance is RuleProvenance.FIXTURE


def test_a_rule_declaring_only_core_fact_types_loads() -> None:
    ruleset = load_ruleset([srd_rule(consumes=("attitude", "inspiration"))])
    assert ruleset.rule("d20-test").consumes == ("attitude", "inspiration")


def test_a_ruleset_is_a_read_only_mapping() -> None:
    ruleset = load_ruleset([srd_rule()])
    with pytest.raises(TypeError):
        ruleset.rules["other"] = srd_rule("other")  # type: ignore[index]


def test_an_unknown_rule_is_named_in_the_error() -> None:
    with pytest.raises(RuleLoadError, match="no rule 'absent'"):
        load_ruleset([srd_rule()]).rule("absent")


def test_is_verified_is_false_for_anything_but_a_verified_srd_rule() -> None:
    """Asserted negatively as well as positively — an always-true property proves nothing."""
    assert srd_rule().is_verified

    unverified = srd_rule(verification=Verification(state=VerificationState.UNVERIFIED))
    assert not unverified.is_verified

    excluded = srd_rule(
        verification=Verification(state=VerificationState.EXCLUDED, reason="not in the SRD")
    )
    assert not excluded.is_verified

    assert not fixture_rule().is_verified, "a fixture has nothing to be verified against"


# --- The verification gate (R31, R32) -----------------------------------------------


def test_an_unverified_srd_rule_is_refused_and_named() -> None:
    unverified = srd_rule(verification=Verification(state=VerificationState.UNVERIFIED))
    with pytest.raises(RuleLoadError, match="'d20-test' is unverified"):
        load_ruleset([unverified])


def test_an_excluded_rule_is_refused_with_its_reason_surfaced() -> None:
    """R32 excludes *and discloses* — an exclusion swallowed silently is a silent drop."""
    excluded = srd_rule(
        verification=Verification(
            state=VerificationState.EXCLUDED,
            reason="the SRD does not state a DC for this, and inferring one is a guess",
        )
    )
    with pytest.raises(RuleLoadError, match="inferring one is a guess"):
        load_ruleset([excluded])


def test_an_exclusion_with_no_reason_is_malformed() -> None:
    with pytest.raises(RuleLoadError, match="silent drop wearing a label"):
        Verification(state=VerificationState.EXCLUDED)


def test_a_verified_entry_must_name_the_section_it_was_verified_against() -> None:
    with pytest.raises(RuleLoadError, match="names the SRD"):
        Verification(state=VerificationState.VERIFIED, date="2026-08-22")


def test_a_verified_entry_must_carry_an_iso_date() -> None:
    with pytest.raises(RuleLoadError, match="ISO date"):
        Verification(state=VerificationState.VERIFIED, reference="Combat")
    with pytest.raises(RuleLoadError, match="ISO date"):
        Verification(state=VerificationState.VERIFIED, reference="Combat", date="22 Aug 2026")


def test_an_srd_rule_with_no_verification_block_is_malformed() -> None:
    """The state against the document is the whole basis for trusting the entry."""
    with pytest.raises(RuleLoadError, match="carries no verification block"):
        Rule(id="x", summary="s", provenance=RuleProvenance.SRD)


# --- The two entry points refuse each other -----------------------------------------


def test_the_srd_loader_refuses_a_fixture_outright() -> None:
    with pytest.raises(RuleLoadError, match="cannot be loaded as SRD-derived"):
        load_ruleset([fixture_rule()])


def test_the_fixture_loader_refuses_an_srd_rule_outright() -> None:
    """Even a verified one — provenance selects the loader, and this is not its loader."""
    with pytest.raises(RuleLoadError, match="cannot be loaded as a fixture"):
        load_fixture_ruleset("slice", [srd_rule()])


def test_loosening_the_fixture_loader_could_not_admit_an_unverified_srd_rule() -> None:
    """The property the two-entry-point shape exists for, asserted directly.

    Whatever the fixture loader admits, it is not a route for SRD-derived rules: it refuses
    them on provenance before any verification state is consulted.
    """
    unverified = srd_rule(verification=Verification(state=VerificationState.UNVERIFIED))
    with pytest.raises(RuleLoadError, match="cannot be loaded as a fixture"):
        load_fixture_ruleset("slice", [unverified])


def test_a_fixture_ruleset_must_be_asked_for_by_name() -> None:
    with pytest.raises(RuleLoadError, match="asked for by name"):
        load_fixture_ruleset("", [fixture_rule()])


# --- R21: a rule may declare core fact types only -----------------------------------


def test_a_rule_declaring_a_namespaced_extension_type_fails_to_load() -> None:
    """A load-time error, not a runtime failure — it should be impossible to ship."""
    with pytest.raises(RuleLoadError, match="carries a namespace"):
        srd_rule(consumes=("attitude", "com.example.tool.mood"))


def test_the_extension_refusal_applies_to_fixtures_too() -> None:
    with pytest.raises(RuleLoadError, match="carries a namespace"):
        fixture_rule(consumes=("io.github.someone.thing",))


# --- Fixture rules carry a rationale, not a verification ----------------------------


def test_a_fixture_with_no_rationale_is_malformed() -> None:
    """It has nothing to verify against, so what it is for is the only account of it."""
    with pytest.raises(RuleLoadError, match="carries no rationale"):
        Rule(id="x", summary="s", provenance=RuleProvenance.FIXTURE)


def test_a_fixture_may_not_carry_a_verification_block() -> None:
    with pytest.raises(RuleLoadError, match="nothing to verify against"):
        fixture_rule(verification=VERIFIED)


def test_an_srd_rule_may_not_carry_a_rationale() -> None:
    with pytest.raises(RuleLoadError, match="cites a section rather than a rationale"):
        srd_rule(rationale="because it seemed right")


# --- Shape ---------------------------------------------------------------------------


def test_a_rule_carries_an_id_and_a_summary() -> None:
    with pytest.raises(RuleLoadError, match="id and a summary"):
        srd_rule(rule_id="")
    with pytest.raises(RuleLoadError, match="id and a summary"):
        srd_rule(summary="")


def test_a_ruleset_has_one_rule_per_id() -> None:
    with pytest.raises(RuleLoadError, match="appears twice"):
        load_ruleset([srd_rule(), srd_rule()])


def test_an_empty_ruleset_loads() -> None:
    assert len(load_ruleset([])) == 0


# --- The packaging half of the guarantee ---------------------------------------------


def test_no_fixture_rule_is_defined_anywhere_under_src() -> None:
    """Fixtures live with the tests that use them, so what ships cannot contain one.

    This is the half a loader cannot enforce: whatever `load_fixture_ruleset` would admit,
    a fixture definition inside the distribution would be invented mechanics shipped inside
    a package about SRD fidelity.
    """
    findings: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
            if name != "Rule":
                continue
            for keyword in node.keywords:
                if keyword.arg == "provenance" and _names_fixture(keyword.value):
                    findings.append(f"{path.relative_to(SRC_ROOT)}:{node.lineno}")

    assert not findings, (
        "Fixture rules must not be defined under src/ — they are invented mechanics, and "
        "this is a package about SRD fidelity:\n  " + "\n  ".join(findings)
    )


def _names_fixture(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "FIXTURE"
    if isinstance(node, ast.Constant):
        return node.value == "fixture"
    return False


def test_the_packaging_guard_is_actually_scanning() -> None:
    """A scan of zero modules passes vacuously, which is worse than no scan at all."""
    modules = [p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts]
    assert len(modules) >= 4, f"only {len(modules)} modules found — the scan is not running"


def test_the_packaging_guard_recognises_a_fixture_definition() -> None:
    """Proves the detector, so the guard above is known to be inspecting something."""
    tree = ast.parse("Rule(id='x', provenance=RuleProvenance.FIXTURE)")
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert any(_names_fixture(k.value) for k in call.keywords if k.arg == "provenance")

    tree = ast.parse("Rule(id='x', provenance=RuleProvenance.SRD)")
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    assert not any(_names_fixture(k.value) for k in call.keywords if k.arg == "provenance")


# --- The two loaders share their machinery -------------------------------------------


def test_both_loaders_apply_the_same_shape_and_duplicate_checks() -> None:
    """Sharing is what makes a fixture ruleset exercise the real path, not a parallel one."""
    with pytest.raises(RuleLoadError, match="appears twice"):
        load_fixture_ruleset("slice", [fixture_rule(), fixture_rule()])

    for ruleset in (load_ruleset([srd_rule()]), load_fixture_ruleset("s", [fixture_rule()])):
        assert isinstance(ruleset, Ruleset)
        assert "d20-test" in ruleset or "invented-check" in ruleset


# --- Verification records its method (0017) ------------------------------------------


def test_a_verification_may_record_how_it_was_checked() -> None:
    """0017 splits the claim in two: `asserted` is a pattern that must match a cited page,
    `editorial` is a human modelling judgement. Both are recorded; neither is assumed."""
    from srd_rules_engine.core.rules import VerificationMethod

    asserted = Verification(
        state=VerificationState.VERIFIED,
        reference="SRD v5.2.1, Monsters, p. 347",
        date="2026-08-23",
        method=VerificationMethod.ASSERTED,
    )
    assert asserted.method is VerificationMethod.ASSERTED
    assert {m.value for m in VerificationMethod} == {"asserted", "editorial"}


def test_an_unrecorded_method_is_none_rather_than_a_guess() -> None:
    """Honest where a default would not be: `asserted` on an unchecked entry would be a
    claim nobody made."""
    assert Verification(state=VerificationState.UNVERIFIED).method is None


def test_every_srd_verification_in_the_engine_says_it_was_asserted() -> None:
    """Each of these rests on a pattern in `scripts/verify_d20_rules.py` or a derivation
    script, so `asserted` is the true answer and an unrecorded one would understate it."""
    from srd_rules_engine.core.actions import ACTION_VERIFICATION
    from srd_rules_engine.core.areas import AREA_VERIFICATION
    from srd_rules_engine.core.conditions import CONDITION_VERIFICATION
    from srd_rules_engine.core.d20 import (
        ADVANTAGE_VERIFICATION,
        CRITICAL_VERIFICATION,
        MODIFIER_VERIFICATION,
        REROLL_VERIFICATION,
    )
    from srd_rules_engine.core.damage import DAMAGE_VERIFICATION
    from srd_rules_engine.core.death import DEATH_SAVE_VERIFICATION
    from srd_rules_engine.core.position import MOVEMENT_VERIFICATION
    from srd_rules_engine.core.rules import VerificationMethod
    from srd_rules_engine.core.spellcasting import SPELLCASTING_VERIFICATION

    for verification in (
        ACTION_VERIFICATION,
        ADVANTAGE_VERIFICATION,
        AREA_VERIFICATION,
        CONDITION_VERIFICATION,
        CRITICAL_VERIFICATION,
        DAMAGE_VERIFICATION,
        DEATH_SAVE_VERIFICATION,
        MODIFIER_VERIFICATION,
        MOVEMENT_VERIFICATION,
        REROLL_VERIFICATION,
        SPELLCASTING_VERIFICATION,
    ):
        assert verification.method is VerificationMethod.ASSERTED, verification.reference
