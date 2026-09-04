"""Shared conversion from an escalated assessment to an ``review-kit`` Review payload.

Lives in the adapter layer, not the pure domain, because it depends on the kit. The subject, summary
and every citation snippet are redacted BEFORE they leave the process (the same redact-before-
anything rule the audit write obeys), using the shared ``pii-kit``, so no raw identifier reaches
human-review-console over the wire; human-review-console redacts again before its own audit write
(defence in depth). ``maker`` and ``tenant`` are asserted here and trusted by human-review-console
because the caller is an authenticated S2S service; per-hop on-behalf-of token exchange is the
deferred next layer.
"""

from __future__ import annotations

import re

from pii_kit import NATIONAL_ID_PATTERNS, UNIVERSAL_PATTERNS, national_patterns_for
from pii_kit import redact as pii_redact
from review_kit import Citation as KitCitation
from review_kit import Review

from ..domain.kernel import Severity
from ..domain.models import OutcomeAssessment

#: The repository name prefixes every source_key: it is the dedup key the
#: human-review-console stores, so it names the producer.
_REPOSITORY = "consumer-duty-monitoring"

#: Cap the citations carried on the wire: enough for a reviewer to trace the decision without
#: copying the whole evidence set into the console.
_MAX_CITATIONS = 8

#: The console is a SHARED sink, so the payload is scrubbed against every jurisdiction's rows plus
#: the universal email / phone rows, whatever this deployment's own ``domain.pii`` selects.
_ALL_PATTERNS = (
    *national_patterns_for(tuple(NATIONAL_ID_PATTERNS.keys())),
    *UNIVERSAL_PATTERNS,
)

#: Bands that demand dual control (two approvals) rather than a single checker.
_DUAL_CONTROL = (Severity.CRITICAL,)


def _redact(text: str) -> str:
    """Mask every jurisdiction's identifiers plus email / phone, and normalise whitespace."""
    return re.sub(r"\s+", " ", pii_redact(text, _ALL_PATTERNS)).strip()


def _kit_citations(assessment: OutcomeAssessment) -> tuple[KitCitation, ...]:
    seen: set[str] = set()
    out: list[KitCitation] = []
    for citation in assessment.citations:
        if citation.source_id in seen:
            continue
        seen.add(citation.source_id)
        out.append(
            KitCitation(
                source_id=citation.source_id,
                title=citation.title,
                snippet=_redact(citation.snippet),
            )
        )
        if len(out) >= _MAX_CITATIONS:
            break
    return tuple(out)


def _summary(assessment: OutcomeAssessment) -> str:
    families = ", ".join(sorted({r.family.value for r in assessment.breaches})) or "none"
    return (
        f"Consumer Duty assessment {assessment.assessment_id}: {assessment.breach_count} "
        f"breach(es), {assessment.gap_count} gap(s) across {assessment.product_count} product(s); "
        f"families: {families}."
    )


def result_to_review(assessment: OutcomeAssessment, *, maker: str, tenant: str = "") -> Review:
    """Build the review a producer submits to human-review-console when an assessment escalates
    (rule R8).
    """
    return Review(
        action="consumer_duty_monitoring:assess",
        subject=assessment.assessment_id,
        maker=maker,
        tenant=tenant or assessment.tenant,
        summary=_redact(_summary(assessment)),
        severity=assessment.severity.value,
        required_approvals=2 if assessment.severity in _DUAL_CONTROL else 1,
        sod_group="consumer_duty_monitoring-maker-checker",
        case_ref=assessment.assessment_id,
        # Producer-owned, tenant-scoped key so a retried delivery is idempotent at the console.
        source_key=f"{_REPOSITORY}:{tenant or assessment.tenant}:{assessment.assessment_id}",
        citations=_kit_citations(assessment),
    )
