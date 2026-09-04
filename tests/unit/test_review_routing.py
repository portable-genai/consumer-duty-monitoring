"""Rule R8: an escalated assessment is ROUTED to human-review-console, not left in a per-repo
boolean.

This is the standing gate for the failure the rule exists to prevent. A repo can set
``requires_human_review = True``, pass every other test, and still auto-execute in practice
because nothing ever reads the flag. So the assertions here are about the ROUTING, not the flag:
an escalated assessment produces an outbound review, a routine one produces none, the payload
leaves redacted, dual control is conditional on severity, and the managed and on-prem placeholders
refuse rather than swallowing the escalation.

The assessments are the REAL engine-built artifacts (``sample_cases.CANONICAL_ASSESSMENT`` for the
seeded breaching tenant, and the live service path for the pii tenant), never hand-written
literals, so a change to the outcome-test engine cannot leave this gate asserting a stale shape.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from consumer_duty_monitoring.adapters.gcp.review_router import (
    CloudReviewRouter,
)
from consumer_duty_monitoring.adapters.local._seed import (
    PII_TENANT,
)
from consumer_duty_monitoring.adapters.local.review_router import (
    LocalReviewRouter,
)
from consumer_duty_monitoring.adapters.onprem.review_router import (
    OnPremReviewRouter,
)
from consumer_duty_monitoring.api.app import (
    app,
)
from consumer_duty_monitoring.config import (
    Container,
    Settings,
    build_container,
)
from consumer_duty_monitoring.domain.kernel import (
    Citation,
    Severity,
)
from consumer_duty_monitoring.domain.models import (
    OutcomeAssessment,
)
from consumer_duty_monitoring.service import (
    build_service,
)

from tests.fixtures import sample_cases

#: The one posture the local profile serves an end-user route to (see tests/conftest.py).
LOOPBACK_PEER = ("127.0.0.1", 50000)


def _settings(profile: str = "local", **overrides: str) -> Settings:
    base: dict[str, str] = {
        "profile": profile,
        "audit_path": ":memory:",
        "assessment_path": ":memory:",
        "tenant": sample_cases.TENANT,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _escalating() -> OutcomeAssessment:
    """A real, engine-built assessment over the seeded tenant: four breaches, severity critical."""
    return sample_cases.CANONICAL_ASSESSMENT


def _assess_through_service(tenant: str) -> tuple[OutcomeAssessment, Container]:
    """Run the WHOLE service path for a tenant and hand back the container it routed through."""
    container = build_container(_settings(tenant=tenant))
    assessment = build_service(container).assess(
        tenant, sample_cases.reference_policy(), actor=sample_cases.ACTOR, as_of=sample_cases.AS_OF
    )
    return assessment, container


def test_an_escalated_assessment_produces_an_outbound_review() -> None:
    router = LocalReviewRouter(_settings())
    ref = router.route(_escalating(), maker=sample_cases.ACTOR)
    assert ref, "routing must return a reference, so the caller can record where it went"
    pending = router.outbox.pending()
    assert len(pending) == 1
    review = pending[0].review
    assert review.maker == sample_cases.ACTOR
    assert review.tenant == sample_cases.TENANT
    assert review.severity == _escalating().severity.value
    assert review.source_key, "a durable outbox needs an idempotency key"


def test_a_critical_assessment_demands_dual_control() -> None:
    router = LocalReviewRouter(_settings())
    router.route(_escalating(), maker=sample_cases.ACTOR)  # the seeded assessment is critical
    assert router.outbox.pending()[0].review.required_approvals == 2


def test_a_high_but_not_critical_assessment_needs_only_a_single_checker() -> None:
    """Dual control is CONDITIONAL on severity, not always on: prove the else branch too."""
    high = replace(_escalating(), severity=Severity.HIGH)
    router = LocalReviewRouter(_settings())
    router.route(high, maker=sample_cases.ACTOR)
    assert router.outbox.pending()[0].review.required_approvals == 1


def test_the_payload_masks_a_raw_identifier_in_a_citation() -> None:
    """A citation snippet carrying an identifier is MASKED, not merely dropped, before the wire.

    The identifier is placed FIRST so the citation cap cannot make the point for the wrong reason
    (dropping it off the end): the assertion is that redaction replaced it with a token, so a
    reorder that pulled a real evidence citation into the payload could never leak it.
    """
    nric = Citation(
        source_id="e3:scorecard:001",
        title="E3 scorecard vulnerability cue",
        snippet=f"cue noted for NRIC {sample_cases.PLANTED_NRIC}",
    )
    assessment = replace(_escalating(), citations=(nric, *_escalating().citations[:3]))
    router = LocalReviewRouter(_settings())
    router.route(assessment, maker=sample_cases.ACTOR)
    wire = repr(router.outbox.pending()[0].review.to_payload())
    assert sample_cases.PLANTED_NRIC not in wire
    assert "REDACTED" in wire


def test_the_full_service_path_never_routes_a_raw_identifier() -> None:
    """End to end over the pii tenant: no raw identifier reaches the human-review-console wire,
    redacted or capped.

    The complement to the mask test above: that one proves the redactor masks; this one proves
    the whole real path (dedup, cap, submit) emits nothing, over the seed that actually plants
    an id.
    """
    assessment, container = _assess_through_service(PII_TENANT)
    assert any(sample_cases.PLANTED_NRIC in c.snippet for c in assessment.citations), (
        "the pii fixture must carry the planted identifier BEFORE redaction, or this proves nothing"
    )
    router = container.review_router
    assert isinstance(router, LocalReviewRouter)
    wire = repr(router.outbox.pending()[0].review.to_payload())
    assert sample_cases.PLANTED_NRIC not in wire


def test_the_managed_router_refuses_when_no_console_is_configured() -> None:
    """An escalation with nowhere to go must fail loudly, not return as if it were reviewed."""
    router = CloudReviewRouter(_settings("gcp", review_url=""))
    with pytest.raises(RuntimeError, match="R8"):
        router.route(_escalating(), maker=sample_cases.ACTOR)


def test_the_onprem_placeholder_refuses_rather_than_dropping_the_escalation() -> None:
    router = OnPremReviewRouter(_settings("onprem"))
    with pytest.raises(NotImplementedError, match="R8"):
        router.route(_escalating(), maker=sample_cases.ACTOR)


def test_the_api_routes_the_escalation_in_the_same_request() -> None:
    """The serving path, not just the adapter: an escalation must not depend on a later job.

    The verified principal's tenant drives the assessment: the seeded ``approver`` persona is the
    breaching tenant and escalates, while ``other-tenant`` has no seeded book and is the routine
    beat. A body tenant cannot widen either, so identity is what selects the case.
    """
    client = TestClient(app, client=LOOPBACK_PEER)
    escalated = client.post("/v1/assess", json={}, headers={"X-Dev-Persona": "approver"}).json()
    assert escalated["requires_human_review"] is True
    assert escalated["review_ref"], "an escalation with no routing reference went nowhere"

    routine = client.post("/v1/assess", json={}, headers={"X-Dev-Persona": "other-tenant"}).json()
    assert routine["requires_human_review"] is False
    assert routine["review_ref"] == "", "a non-escalation must not manufacture a review"
