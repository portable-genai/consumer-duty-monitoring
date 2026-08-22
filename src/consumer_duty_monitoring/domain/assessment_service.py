"""AssessmentService: the one path a Consumer Duty assessment takes. Deterministic, then narrated.

Gathers a tenant's signals, product frame and vulnerable-subject consent context; runs the
deterministic outcome-test engine; synthesises themes by deterministic counting; drafts a grounded
narration that may only restate the engine; redacts before the audit write; routes every
consequential assessment to Hrz7 (rule R8) in the same call that produced it; and stores and
exports the result. Every number and every verdict come from the engine; the narration adds no
figure and no citation the engine did not emit.

The domain stays pure: it talks only to ports (Protocols) and models, and to ``pii-kit`` for
redaction. It never imports ``config``. Every surface builds this service through ``service.py``,
so no surface can construct a narrower one and quietly stop honouring rule R8.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime

from consent_preference_kit import ConsentQuery
from pii_kit import redact

from ..ports.assessment_store import AssessmentStorePort
from ..ports.audit import AuditSinkPort
from ..ports.consent import ConsentLookupPort
from ..ports.narration import NarrationPort
from ..ports.observability import ObservabilityTracerPort
from ..ports.outcome_signals import SignalSourcePort
from ..ports.product_governance import ProductGovernancePort
from ..ports.review_router import ReviewRouterPort
from ..ports.warehouse import WarehouseExportPort
from .errors import TenantAccessDeniedError
from .kernel import AuditEvent, Citation, Decision, utcnow
from .models import (
    AssessmentRequest,
    Narration,
    OutcomeAssessment,
    OutcomeSignal,
    OutcomeTestResult,
    SignalKind,
    Theme,
)
from .narration import grounded_or_fallback, narration_brief
from .outcome_tests import ENGINE_VERSION, OutcomeTestEngine, overall_verdict
from .pii import PII_PATTERNS
from .policy import OutcomePolicy
from .serialization import assessment_to_row
from .theme_synthesis import synthesize_themes

#: The purpose the consent lookup asks about. The monitor checks whether a vulnerable subject who
#: was CONTACTED had granted a preference to be; "marketing" is the purpose Mkt5's outreach uses.
_CONSENT_PURPOSE = "marketing"

#: One span per assessment. Structural attributes only: see :meth:`AssessmentService.assess`.
_ASSESS_SPAN = "consumer_duty.assess"


class AssessmentService:
    """Produce, audit, route, store and export one tenant's Consumer Duty outcome assessment."""

    def __init__(
        self,
        *,
        audit: AuditSinkPort,
        signals: SignalSourcePort,
        products: ProductGovernancePort,
        consent: ConsentLookupPort,
        store: AssessmentStorePort,
        review_router: ReviewRouterPort,
        narrator: NarrationPort,
        warehouse: WarehouseExportPort,
        tracer: ObservabilityTracerPort,
    ) -> None:
        self._audit = audit
        self._signals = signals
        self._products = products
        self._consent = consent
        self._store = store
        self._review = review_router
        self._narrator = narrator
        self._warehouse = warehouse
        self._tracer = tracer
        self._engine = OutcomeTestEngine()

    # ------------------------------------------------------------------ #
    # Produce
    # ------------------------------------------------------------------ #
    def assess(
        self, tenant: str, policy: OutcomePolicy, *, actor: str, as_of: datetime
    ) -> OutcomeAssessment:
        """Run the whole path for ``tenant`` and return the stored, routed assessment.

        The whole path runs inside one span. Its attributes are STRUCTURAL only, never a
        subject id, a signal's citation snippet, a theme or any narration text: a trace backend
        is not the WORM audit trail. It has no redaction stage, a wider read audience and no
        retention rule written against a regulator's requirement, so anything content-shaped
        that reaches a span has left the boundary the ``redact`` call exists to hold, silently.
        """
        with self._tracer.span(
            _ASSESS_SPAN,
            action="assess",
            actor=actor,
            tenant=tenant,
            policy_version=policy.version,
        ):
            signals = self._signals.load(tenant)
            frame = self._products.load(tenant)
            denied = self._consent_denied_subjects(tenant, signals, as_of)

            request = AssessmentRequest(
                tenant=tenant,
                as_of=as_of,
                signals=tuple(signals),
                frame=frame,
                consent_denied_subjects=denied,
            )
            results = self._engine.assess(request, policy)
            themes = synthesize_themes(results)
            assessment = self._build(tenant, as_of, policy.version, results, themes, signals, frame)

            # The narration is advisory and grounded: it may restate the engine and nothing else.
            assessment = replace(assessment, narration=self._narrate(assessment))

            # Redact BEFORE the audit write: no raw identifier reaches the WORM record, in the
            # summary OR in a citation snippet (a signal citation can carry personal data).
            self._audit.record(
                AuditEvent(
                    action="assess",
                    actor=actor,
                    decision=assessment.overall,
                    severity=assessment.severity,
                    redacted_summary=redact(self._audit_summary(assessment), PII_PATTERNS),
                    citations=self._redacted_citations(assessment.citations[:8]),
                    timestamp=utcnow(),
                )
            )

            # Rule R8: a consequential assessment is ROUTED, not merely flagged.
            review_ref = ""
            if assessment.requires_human_review:
                review_ref = self._review.route(assessment, maker=actor, tenant=tenant)
            assessment = replace(assessment, review_ref=review_ref)

            self._store.put(assessment)
            self._warehouse.export((assessment_to_row(assessment),))
            return assessment

    # ------------------------------------------------------------------ #
    # Read (the tenant boundary lives here, answering 403)
    # ------------------------------------------------------------------ #
    def read_assessment(self, assessment_id: str, *, principal_tenant: str) -> OutcomeAssessment:
        """Fetch one assessment, denying with a 403-mapped error across the tenant boundary."""
        record = self._store.get(assessment_id)
        if record is None:
            raise KeyError(assessment_id)
        if not principal_tenant or record.tenant != principal_tenant:
            raise TenantAccessDeniedError(
                f"assessment {assessment_id} belongs to another tenant; refusing cross-tenant read"
            )
        return record

    # ------------------------------------------------------------------ #
    # Consent context for the vulnerable-customer test
    # ------------------------------------------------------------------ #
    def _consent_denied_subjects(
        self, tenant: str, signals: tuple[OutcomeSignal, ...], as_of: datetime
    ) -> frozenset[str]:
        """The vulnerable subjects whose consent is NOT an allow (fail-closed, read-only)."""
        subjects = {
            s.subject_id for s in signals if s.kind is SignalKind.VULNERABILITY_CUE and s.subject_id
        }
        channel_by_subject = {
            s.subject_id: s.channel
            for s in signals
            if s.kind is SignalKind.CONTACT_OUTCOME and s.subject_id and s.channel
        }
        denied: set[str] = set()
        for subject in sorted(subjects):
            query = ConsentQuery(
                tenant=tenant,
                subject_id=subject,
                purpose=_CONSENT_PURPOSE,
                channel=channel_by_subject.get(subject, "email"),
                as_of=as_of.date().isoformat(),
            )
            decision = self._consent.decide(query)
            if not decision.allowed:
                denied.add(subject)
        return frozenset(denied)

    # ------------------------------------------------------------------ #
    # Assembly
    # ------------------------------------------------------------------ #
    def _build(
        self,
        tenant: str,
        as_of: datetime,
        pack_version: str,
        results: tuple[OutcomeTestResult, ...],
        themes: tuple[Theme, ...],
        signals: tuple[OutcomeSignal, ...],
        frame: object,
    ) -> OutcomeAssessment:
        severity, requires_review = overall_verdict(results)
        overall = Decision.ESCALATED if requires_review else Decision.ALLOWED
        product_count = len(getattr(frame, "products", ()))
        assessment_id = self._assessment_id(tenant, as_of, pack_version, results)
        return OutcomeAssessment(
            assessment_id=assessment_id,
            tenant=tenant,
            as_of=as_of,
            pack_version=pack_version,
            engine_version=ENGINE_VERSION,
            results=results,
            themes=themes,
            overall=overall,
            severity=severity,
            requires_human_review=requires_review,
            signal_count=len(signals),
            product_count=product_count,
            citations=self._citations(results),
        )

    @staticmethod
    def _assessment_id(
        tenant: str,
        as_of: datetime,
        pack_version: str,
        results: tuple[OutcomeTestResult, ...],
    ) -> str:
        """A content digest, so a re-run over identical inputs updates in place, never piling up."""
        parts = [tenant, as_of.isoformat(), pack_version]
        for result in results:
            parts.append(f"{result.test_id}|{result.outcome.value}|{result.observed:.6f}")
        digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:16]
        return f"cda-{digest}"

    @staticmethod
    def _redacted_citations(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
        """Mask any personal data in a citation snippet before it reaches the WORM record."""
        return tuple(
            Citation(
                source_id=c.source_id,
                title=c.title,
                snippet=redact(c.snippet, PII_PATTERNS),
            )
            for c in citations
        )

    @staticmethod
    def _citations(results: tuple[OutcomeTestResult, ...]) -> tuple[Citation, ...]:
        seen: set[str] = set()
        out: list[Citation] = []
        for result in results:
            for citation in result.citations:
                if citation.source_id not in seen:
                    seen.add(citation.source_id)
                    out.append(citation)
        return tuple(out)

    @staticmethod
    def _audit_summary(assessment: OutcomeAssessment) -> str:
        families = ", ".join(sorted({r.family.value for r in assessment.breaches})) or "none"
        return (
            f"{assessment.assessment_id} {assessment.overall.value} sev "
            f"{assessment.severity.value}: {assessment.breach_count} breach(es), "
            f"{assessment.gap_count} gap(s); families {families}"
        )

    # ------------------------------------------------------------------ #
    # Narration (optional, grounded, never consequential)
    # ------------------------------------------------------------------ #
    def _narrate(self, assessment: OutcomeAssessment) -> Narration:
        brief = narration_brief(assessment)
        try:
            draft = self._narrator.narrate(brief)
        except Exception:  # noqa: BLE001 - a model failure must never block an assessment
            draft = None
        return grounded_or_fallback(draft, brief, assessment)
