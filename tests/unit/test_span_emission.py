"""A Consumer Duty assessment opens ONE span, and that span carries no content.

A trace backend is not the WORM audit trail. It has no redaction stage, no retention policy
written against a regulator's requirement, and a far wider read audience than the audit store.
So the value of tracing the assessment path depends entirely on the span carrying structural
attributes only: which action, whose, which tenant, which pack version. A subject id, a
signal's citation snippet, a theme or any narration text reaching a span has left the boundary
the service's ``redact`` call exists to hold, and it has left it silently.

The content case runs the REAL seeded tenant, whose signal citations carry a planted NRIC, so
the check runs against input that would actually leak if any attribute were content-shaped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from consumer_duty_monitoring.adapters.local._seed import VULNERABLE_SUBJECT
from consumer_duty_monitoring.config import build_container
from consumer_duty_monitoring.domain.assessment_service import AssessmentService
from consumer_duty_monitoring.domain.models import OutcomeAssessment

from tests.conftest import local_settings
from tests.fixtures import sample_cases

#: Every attribute key the assess span is allowed to carry. A breach that started explaining
#: itself on the span (a finding, a subject, a theme) would widen this set, which is the point
#: of asserting on the set rather than on the individual keys.
_ASSESS_KEYS = {"action", "actor", "tenant", "policy_version"}


class _RecordingTracer:
    """Captures every span name and attribute so the test can inspect what was emitted."""

    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, str]]] = []

    @contextmanager
    def span(self, name: str, **attributes: str) -> Iterator[None]:
        self.spans.append((name, dict(attributes)))
        yield

    def record_token_usage(self, usage: object, model: str) -> None:
        return None


def _assess() -> tuple[_RecordingTracer, OutcomeAssessment]:
    """The REAL local adapters, exactly as ``service.build_service`` wires them."""
    container = build_container(local_settings())
    tracer = _RecordingTracer()
    service = AssessmentService(
        audit=container.audit,
        signals=container.signal_source,
        products=container.product_governance,
        consent=container.consent,
        store=container.assessment_store,
        review_router=container.review_router,
        narrator=container.narration,
        warehouse=container.warehouse,
        tracer=tracer,  # type: ignore[arg-type]
    )
    assessment = service.assess(
        sample_cases.TENANT_ID,
        sample_cases.reference_policy(),
        actor=sample_cases.ACTOR,
        as_of=sample_cases.AS_OF,
    )
    return tracer, assessment


def _emitted(tracer: _RecordingTracer) -> str:
    """Every attribute VALUE that was emitted, and every KEY, as one searchable blob."""
    parts: list[str] = []
    for name, attributes in tracer.spans:
        parts.append(name)
        parts.extend(attributes)
        parts.extend(attributes.values())
    return " ".join(parts)


def test_an_assessment_opens_exactly_one_named_span() -> None:
    tracer, _ = _assess()
    assert [name for name, _ in tracer.spans] == ["consumer_duty.assess"]


def test_the_span_carries_the_structural_attributes_an_operator_needs() -> None:
    """Enough to answer "whose assessment is slow, on which tenant and pack", nothing more."""
    tracer, _ = _assess()
    _, attributes = tracer.spans[0]
    assert attributes["action"] == "assess"
    assert attributes["actor"] == sample_cases.ACTOR
    assert attributes["tenant"] == sample_cases.TENANT_ID
    assert attributes["policy_version"] == sample_cases.reference_policy().version


def test_the_attribute_set_is_a_fixed_allowlist_whatever_the_verdict() -> None:
    """The seeded tenant BREACHES, and the breach must not explain itself on the span."""
    tracer, assessment = _assess()
    assert assessment.requires_human_review, (
        "the seeded tenant stopped breaching; this test must drive a consequential assessment"
    )
    for _, attributes in tracer.spans:
        assert set(attributes) == _ASSESS_KEYS


def test_no_span_attribute_carries_signal_content_or_the_planted_identifier() -> None:
    """The seeded signals carry an NRIC in a citation snippet, so a leak would show."""
    tracer, assessment = _assess()
    emitted = _emitted(tracer)

    forbidden: list[str] = [sample_cases.PLANTED_NRIC, VULNERABLE_SUBJECT]
    forbidden.extend(c.snippet for c in assessment.citations if c.snippet)
    if assessment.narration is not None:
        forbidden.append(assessment.narration.headline)
    assert len(forbidden) > 2, "the assessment stopped carrying citations worth guarding"

    for literal in forbidden:
        assert literal, "an empty needle would pass this test for the wrong reason"
        assert literal not in emitted, f"a span attribute carried {literal!r}"
        assert literal.lower() not in emitted.lower(), f"a span attribute carried {literal!r}"


def test_every_emitted_attribute_value_is_a_string_the_port_declares() -> None:
    """``span(name, **attributes: str)``: a non-string would serialise however the SDK felt."""
    tracer, _ = _assess()
    values: list[Any] = [v for _, attributes in tracer.spans for v in attributes.values()]
    assert values
    assert all(isinstance(value, str) for value in values)
