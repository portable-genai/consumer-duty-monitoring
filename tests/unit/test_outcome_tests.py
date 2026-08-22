"""The deterministic outcome-test engine: every number and verdict is code, and replayable.

These are the assertions that make "the model narrates, the engine decides" a true statement.
The engine is driven directly (no service, no adapters) so the maths is tested in isolation, and
the fail-closed GAP behaviour has its own proof: a family the pack does not configure is a GAP,
never a pass.
"""

from __future__ import annotations

from datetime import UTC, datetime

from consumer_duty_monitoring.adapters.local._seed import (
    TENANT,
    VULNERABLE_SUBJECT,
    seed_frame,
    seed_signals,
)
from consumer_duty_monitoring.domain.kernel import Severity
from consumer_duty_monitoring.domain.models import (
    AssessmentRequest,
    OutcomeTestFamily,
    TestOutcome,
)
from consumer_duty_monitoring.domain.outcome_tests import OutcomeTestEngine, overall_verdict
from consumer_duty_monitoring.domain.policy import OutcomePolicy
from consumer_duty_monitoring.outcome_pack import load_pack

_AS_OF = datetime(2026, 7, 20, 4, 0, tzinfo=UTC)


def _request(tenant: str = TENANT, *, denied: frozenset[str] = frozenset()) -> AssessmentRequest:
    return AssessmentRequest(
        tenant=tenant,
        as_of=_AS_OF,
        signals=seed_signals(tenant),
        frame=seed_frame(tenant),
        consent_denied_subjects=denied,
    )


def _by_test(results: tuple, test_id: str):
    return next(r for r in results if r.test_id == test_id)


def test_the_engine_is_deterministic_and_replayable() -> None:
    engine = OutcomeTestEngine()
    policy = load_pack()
    first = engine.assess(_request(denied=frozenset({VULNERABLE_SUBJECT})), policy)
    second = engine.assess(_request(denied=frozenset({VULNERABLE_SUBJECT})), policy)
    assert first == second


def test_each_family_breaches_exactly_where_the_synthetic_data_says() -> None:
    results = OutcomeTestEngine().assess(
        _request(denied=frozenset({VULNERABLE_SUBJECT})), load_pack()
    )
    breaches = {r.test_id for r in results if r.outcome is TestOutcome.BREACH}
    assert breaches == {
        "foreseeable_harm:P-PKG-04",
        "target_market_drift:P-INV-03",
        "price_vs_value:P-LOAN-02",
        "vulnerable_customer:P-SAVE-01",
    }


def test_a_vulnerable_subject_only_breaches_when_consent_was_denied() -> None:
    """The consent context is what turns a contact into a mishandling. Red-before, green-after."""
    engine = OutcomeTestEngine()
    policy = load_pack()
    allowed = engine.assess(_request(denied=frozenset()), policy)
    denied = engine.assess(_request(denied=frozenset({VULNERABLE_SUBJECT})), policy)
    assert _by_test(allowed, "vulnerable_customer:P-SAVE-01").outcome is TestOutcome.PASS
    assert _by_test(denied, "vulnerable_customer:P-SAVE-01").outcome is TestOutcome.BREACH


def test_an_unconfigured_family_is_a_gap_never_a_pass() -> None:
    """Fail-closed: drop a family from the pack and every one of its results becomes a GAP."""
    full = load_pack()
    without_harm = OutcomePolicy(
        version=full.version,
        thresholds={
            family: threshold
            for family, threshold in full.thresholds.items()
            if family is not OutcomeTestFamily.FORESEEABLE_HARM
        },
    )
    results = OutcomeTestEngine().assess(_request(), without_harm)
    harm = [r for r in results if r.family is OutcomeTestFamily.FORESEEABLE_HARM]
    assert harm and all(r.outcome is TestOutcome.GAP for r in harm)
    assert all(r.requires_human_review for r in harm), "a gap must escalate, not pass"


def test_the_overall_verdict_takes_the_worst_breaching_severity() -> None:
    results = OutcomeTestEngine().assess(
        _request(denied=frozenset({VULNERABLE_SUBJECT})), load_pack()
    )
    severity, review = overall_verdict(results)
    assert review is True
    assert severity is Severity.CRITICAL  # the vulnerable-customer breach is critical


def test_a_clean_book_breaches_nothing_and_does_not_escalate() -> None:
    results = OutcomeTestEngine().assess(_request("clean-bank"), load_pack())
    assert all(r.outcome is TestOutcome.PASS for r in results)
    severity, review = overall_verdict(results)
    assert review is False and severity is Severity.LOW


def test_price_vs_value_uses_a_robust_z_across_the_product_set() -> None:
    """The expensive-for-its-value product stands out from peers, not from an absolute number."""
    results = OutcomeTestEngine().assess(_request(), load_pack())
    loan = _by_test(results, "price_vs_value:P-LOAN-02")
    saver = _by_test(results, "price_vs_value:P-SAVE-01")
    assert loan.observed > saver.observed
    assert loan.outcome is TestOutcome.BREACH and saver.outcome is TestOutcome.PASS
