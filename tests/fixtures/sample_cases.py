"""Canonical synthetic fixtures, shared by the unit and contract suites.

Every party is obviously fictional, every product code is invented, and every subject id is a
synthetic pseudonym (never a real identifier). The shared offline dataset lives in the package
(``adapters/local/_seed.py``) so the local adapters and these fixtures agree; this module re-exposes
the pieces the tests reason about and adds a canonical assessment built by the real engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from consent_preference_kit import ConsentQuery

from consumer_duty_monitoring.adapters.local._seed import (
    TENANT,
    VULNERABLE_SUBJECT,
    seed_frame,
    seed_signals,
)
from consumer_duty_monitoring.domain.assessment_service import AssessmentService
from consumer_duty_monitoring.domain.models import AssessmentRequest, OutcomeAssessment
from consumer_duty_monitoring.domain.narration import narration_brief
from consumer_duty_monitoring.domain.outcome_tests import OutcomeTestEngine, overall_verdict
from consumer_duty_monitoring.domain.policy import OutcomePolicy
from consumer_duty_monitoring.domain.theme_synthesis import synthesize_themes
from consumer_duty_monitoring.outcome_pack import load_pack

#: The verified principal the tests attribute work to (never a client-asserted actor).
ACTOR = "analyst@bank.example"

#: The seeded tenant partition (re-exported under the shared name the infra tests use).
TENANT_ID = TENANT

#: A fixed assessment moment, so a replayed assessment id is byte-identical.
AS_OF = datetime(2026, 7, 20, 4, 0, tzinfo=UTC)

#: A planted identifier, so a redaction assertion has an independent literal to look for rather
#: than trusting the pattern pack to agree with itself.
PLANTED_NRIC = "S1234567D"


def reference_policy() -> OutcomePolicy:
    """The shipped reference outcome pack, loaded once for the tests."""
    return load_pack()


def canonical_assessment() -> OutcomeAssessment:
    """One real assessment over the seeded tenant, produced by the pure engine (no side effects).

    Built by running the engine directly, so the contract suite carries the SAME verdicts the
    service produces rather than a stale hand-written literal.
    """
    signals = seed_signals(TENANT_ID)
    frame = seed_frame(TENANT_ID)
    policy = reference_policy()
    denied = frozenset({VULNERABLE_SUBJECT})
    request = AssessmentRequest(
        tenant=TENANT_ID,
        as_of=AS_OF,
        signals=signals,
        frame=frame,
        consent_denied_subjects=denied,
    )
    results = OutcomeTestEngine().assess(request, policy)
    themes = synthesize_themes(results)
    severity, review = overall_verdict(results)
    from consumer_duty_monitoring.domain.kernel import Decision
    from consumer_duty_monitoring.domain.outcome_tests import ENGINE_VERSION

    citations: list = []
    seen: set[str] = set()
    for result in results:
        for citation in result.citations:
            if citation.source_id not in seen:
                seen.add(citation.source_id)
                citations.append(citation)
    return OutcomeAssessment(
        assessment_id=AssessmentService._assessment_id(TENANT_ID, AS_OF, policy.version, results),
        tenant=TENANT_ID,
        as_of=AS_OF,
        pack_version=policy.version,
        engine_version=ENGINE_VERSION,
        results=results,
        themes=themes,
        overall=Decision.ESCALATED if review else Decision.ALLOWED,
        severity=severity,
        requires_human_review=review,
        signal_count=len(signals),
        product_count=len(frame.products),
        citations=tuple(citations),
    )


#: The canonical assessment used by the review-router and store contract cases.
CANONICAL_ASSESSMENT = canonical_assessment()

#: The consent query the consent-port contract case issues.
CANONICAL_CONSENT_QUERY = ConsentQuery(
    tenant=TENANT_ID,
    subject_id=VULNERABLE_SUBJECT,
    purpose="marketing",
    channel="sms",
)

#: The narration brief the narration-port contract case issues.
CANONICAL_BRIEF = narration_brief(CANONICAL_ASSESSMENT)
