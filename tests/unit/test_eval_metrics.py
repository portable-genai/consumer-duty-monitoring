"""Every eval metric is proved able to go RED. A metric that cannot go red proves nothing.

Each metric is scored on a GREEN input (the real pipeline over the golden set) and a RED input
(the same, degraded in the exact way the metric exists to catch), and ``assert_can_go_red`` /
``assert_each_can_go_red`` require the first to pass the threshold and the second to fail it. The
oracle is the golden dataset, never the pipeline's own answer, which is what makes any of it
evidence.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import run_eval as ev
from agent_eval_kit import assert_can_go_red, assert_each_can_go_red

from consumer_duty_monitoring.config import Settings
from consumer_duty_monitoring.domain.models import Narration, TestOutcome
from consumer_duty_monitoring.domain.narration import deterministic_narration
from consumer_duty_monitoring.domain.policy import OutcomePolicy
from consumer_duty_monitoring.outcome_pack import load_pack

_DATASET = Path(ev.DEFAULT_DATASET)


def _assessments() -> list[ev.Assessment]:
    settings = Settings(profile="local", audit_path=":memory:", assessment_path=":memory:")
    return ev.assess(ev.load_dataset(_DATASET), settings)


def test_pack_schema_validity_can_go_red() -> None:
    good = load_pack()
    broken = OutcomePolicy(version="", thresholds=good.thresholds)  # no version
    assert_can_go_red(
        ev.pack_schema_validity,
        green=good,
        red=broken,
        threshold=1.0,
        metric="pack_schema_validity",
    )


def test_outcome_test_accuracy_can_go_red_per_family() -> None:
    """Per family: flip every result in that family and the family's accuracy must collapse."""
    green = _assessments()

    def _flip(items: list[ev.Assessment], family: str) -> list[ev.Assessment]:
        out: list[ev.Assessment] = []
        for item in items:
            results = tuple(
                replace(
                    r,
                    outcome=TestOutcome.PASS
                    if r.outcome is TestOutcome.BREACH
                    else TestOutcome.BREACH,
                )
                if r.family.value == family
                else r
                for r in item.assessment.results
            )
            out.append(
                ev.Assessment(
                    label=item.label, assessment=replace(item.assessment, results=results)
                )
            )
        return out

    families = ("foreseeable_harm", "target_market_drift", "price_vs_value", "vulnerable_customer")
    cases = {family: (green, _flip(green, family)) for family in families}
    assert_each_can_go_red(
        lambda items, fam=None: ev.outcome_test_accuracy(items),
        cases,
        threshold=0.95,
        metric="outcome_test_accuracy",
    )


def test_theme_citation_can_go_red() -> None:
    green = _assessments()

    def _uncite(items: list[ev.Assessment]) -> list[ev.Assessment]:
        out: list[ev.Assessment] = []
        for item in items:
            themes = tuple(replace(t, citations=()) for t in item.assessment.themes)
            out.append(
                ev.Assessment(label=item.label, assessment=replace(item.assessment, themes=themes))
            )
        return out

    # The demo/pii tenants have themes; strip their citations to force the metric red.
    with_themes = [item for item in green if item.assessment.themes]
    assert with_themes, "the golden set must include a tenant with themes"
    assert_can_go_red(
        ev.theme_citation,
        green=with_themes,
        red=_uncite(with_themes),
        threshold=1.0,
        metric="theme_citation",
    )


def test_narration_groundedness_can_go_red_with_a_permissive_gate() -> None:
    green = _assessments()

    def _permissive(draft: Narration | None, brief: object, assessment: object) -> Narration:
        # A gate that keeps whatever it is handed: an invented figure survives, so the metric red.
        return draft if draft is not None else deterministic_narration(assessment)  # type: ignore[arg-type]

    # The gate is the thing under test, so vary the GATE, not the data.
    assert ev.narration_groundedness(green) >= 1.0, "the real gate must accept the clean fallback"
    assert ev.narration_groundedness(green, gate=_permissive) < 1.0, (
        "a permissive gate must score red"
    )


def test_review_safety_can_go_red() -> None:
    green = _assessments()

    def _unroute(items: list[ev.Assessment]) -> list[ev.Assessment]:
        return [
            ev.Assessment(
                label=item.label,
                assessment=replace(item.assessment, review_ref="", requires_human_review=False),
            )
            for item in items
        ]

    assert_can_go_red(
        ev.review_safety,
        green=green,
        red=_unroute(green),
        threshold=1.0,
        metric="review_safety",
    )


def test_pii_safety_can_go_red() -> None:
    planted = ["S1234567D"]
    assert_can_go_red(
        lambda summaries: ev.pii_safety(summaries, planted),
        green=["assessment escalated, no identifier here"],
        red=["contact NRIC S1234567D on file"],
        threshold=0.99,
        metric="pii_safety",
    )
