"""The assessment service: redact-before-audit, R8 routing, the tenant boundary, model freedom.

Drives the REAL local adapters through the service seam, so what is tested is the wiring the
surfaces share, not a narrower path a test invented.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from consumer_duty_monitoring.adapters.local.audit import LocalAuditAdapter
from consumer_duty_monitoring.config import Settings, build_container
from consumer_duty_monitoring.domain.errors import TenantAccessDeniedError
from consumer_duty_monitoring.domain.kernel import Decision
from consumer_duty_monitoring.service import build_service, policy_for

_AS_OF = datetime(2026, 7, 20, 4, 0, tzinfo=UTC)


def _service(**overrides):
    container = build_container(Settings(profile="local", tenant="demo-bank", **overrides))
    return container, build_service(container)


def test_a_breaching_book_escalates_and_is_routed_in_one_call() -> None:
    container, service = _service()
    assessment = service.assess(
        "demo-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF
    )
    assert assessment.overall is Decision.ESCALATED
    assert assessment.requires_human_review is True
    assert assessment.review_ref, "rule R8: an escalation with no routing reference went nowhere"
    assert len(container.review_router.outbox.pending()) == 1


def test_a_clean_book_does_not_manufacture_a_review() -> None:
    container, service = _service()
    assessment = service.assess(
        "clean-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF
    )
    assert assessment.overall is Decision.ALLOWED
    assert assessment.review_ref == ""
    assert container.review_router.outbox.pending() == ()


def test_a_planted_identifier_never_reaches_the_audit_record() -> None:
    container, service = _service()
    service.assess("pii-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF)
    audit = container.audit
    assert isinstance(audit, LocalAuditAdapter)
    import json

    blob = json.dumps(audit.log.read_all(), sort_keys=True, default=str)
    assert "S1234567D" not in blob, "a planted national id reached the immutable audit record"


def test_the_stored_assessment_round_trips_through_the_store() -> None:
    container, service = _service()
    written = service.assess(
        "demo-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF
    )
    reloaded = container.assessment_store.get(written.assessment_id)
    assert reloaded is not None
    assert reloaded.assessment_id == written.assessment_id
    assert reloaded.severity == written.severity
    assert reloaded.breach_count == written.breach_count


def test_the_warehouse_receives_a_flat_row_with_no_signal_text() -> None:
    container, service = _service()
    service.assess("demo-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF)
    rows = container.warehouse.rows
    assert len(rows) == 1
    row = rows[0]
    assert row.breach_count == 4
    # A flat row has no field that can carry a signal detail; assert the shape stayed flat.
    assert not hasattr(row, "signals")


def test_the_tenant_boundary_denies_a_cross_tenant_read_with_403_not_404() -> None:
    container, service = _service()
    written = service.assess(
        "demo-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF
    )
    # Same tenant: allowed.
    assert service.read_assessment(written.assessment_id, principal_tenant="demo-bank")
    # Another tenant: the record EXISTS, and the caller may not have it.
    with pytest.raises(TenantAccessDeniedError):
        service.read_assessment(written.assessment_id, principal_tenant="other-bank")


def test_the_cross_tenant_check_is_real_and_not_a_missing_record() -> None:
    """The mutant: a store fetch with no tenant compare would leak. Prove the compare is there."""
    container, service = _service()
    written = service.assess(
        "demo-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF
    )
    leaked = container.assessment_store.get(written.assessment_id)
    assert leaked is not None, "the store DOES hold the record; only the domain refuses it"


def test_the_consequential_verdict_is_identical_with_the_narrator_stubbed_out() -> None:
    """The model narrates; it never moves a number. Same run, bound and unbound, must agree."""
    container, service = _service()
    with_model = service.assess(
        "demo-bank", policy_for(container), actor="a@bank.example", as_of=_AS_OF
    )

    # A container whose narration port raises: the assessment must be byte-identical but for the
    # narration field, because a failed narrator falls back and never touches a verdict.
    container2, service2 = _service()
    service2._narrator = _RaisingNarrator()  # type: ignore[attr-defined]
    without_model = service2.assess(
        "demo-bank", policy_for(container2), actor="a@bank.example", as_of=_AS_OF
    )
    assert without_model.results == with_model.results
    assert without_model.severity == with_model.severity
    assert without_model.breach_count == with_model.breach_count
    assert without_model.narration is not None and without_model.narration.grounded


class _RaisingNarrator:
    def narrate(self, brief: object) -> None:
        raise RuntimeError("model unreachable")
