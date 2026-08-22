"""Reload a stored assessment from plain JSON, refusing an unknown verdict rather than defaulting.

The store keeps each assessment as plain JSON (``hex_service_kit.serialization.to_jsonable`` on
the way in) so an auditor can open the column in a text editor and a migration off this platform
is a file copy. This module reads it back into the typed value objects, and it refuses an unknown
enum member instead of coercing it to a default: a record must never silently reload with a
different outcome or severity than it was written with.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .kernel import Citation, Decision, Severity
from .models import (
    Narration,
    OutcomeAssessment,
    OutcomeTestFamily,
    OutcomeTestResult,
    TestOutcome,
    Theme,
)


def _citations(raw: Any) -> tuple[Citation, ...]:
    return tuple(
        Citation(
            source_id=str(c.get("source_id", "")),
            title=str(c.get("title", "")),
            snippet=str(c.get("snippet", "")),
        )
        for c in (raw or ())
        if isinstance(c, dict)
    )


def _result(raw: dict[str, Any]) -> OutcomeTestResult:
    return OutcomeTestResult(
        test_id=str(raw["test_id"]),
        family=OutcomeTestFamily(str(raw["family"])),
        product_id=str(raw["product_id"]),
        cohort=str(raw.get("cohort", "")),
        observed=float(raw["observed"]),
        threshold=float(raw["threshold"]),
        outcome=TestOutcome(str(raw["outcome"])),
        severity=Severity(str(raw["severity"])),
        requires_human_review=bool(raw["requires_human_review"]),
        rationale=str(raw.get("rationale", "")),
        signal_ids=tuple(str(s) for s in raw.get("signal_ids", ())),
        citations=_citations(raw.get("citations")),
    )


def _theme(raw: dict[str, Any]) -> Theme:
    return Theme(
        theme_id=str(raw["theme_id"]),
        family=OutcomeTestFamily(str(raw["family"])),
        title=str(raw["title"]),
        breach_count=int(raw["breach_count"]),
        product_ids=tuple(str(p) for p in raw.get("product_ids", ())),
        signal_ids=tuple(str(s) for s in raw.get("signal_ids", ())),
        citations=_citations(raw.get("citations")),
    )


def _narration(raw: Any) -> Narration | None:
    if not isinstance(raw, dict):
        return None
    return Narration(
        headline=str(raw.get("headline", "")),
        body=str(raw.get("body", "")),
        citations=_citations(raw.get("citations")),
        model=str(raw.get("model", "")),
        grounded=bool(raw.get("grounded", True)),
    )


def assessment_from_jsonable(raw: dict[str, Any]) -> OutcomeAssessment:
    """Reconstruct an :class:`OutcomeAssessment`, raising on any unknown enum member."""
    return OutcomeAssessment(
        assessment_id=str(raw["assessment_id"]),
        tenant=str(raw["tenant"]),
        as_of=datetime.fromisoformat(str(raw["as_of"])),
        pack_version=str(raw.get("pack_version", "")),
        engine_version=str(raw.get("engine_version", "")),
        results=tuple(_result(r) for r in raw.get("results", ())),
        themes=tuple(_theme(t) for t in raw.get("themes", ())),
        overall=Decision(str(raw["overall"])),
        severity=Severity(str(raw["severity"])),
        requires_human_review=bool(raw["requires_human_review"]),
        signal_count=int(raw.get("signal_count", 0)),
        product_count=int(raw.get("product_count", 0)),
        citations=_citations(raw.get("citations")),
        narration=_narration(raw.get("narration")),
        review_ref=str(raw.get("review_ref", "")),
    )


def assessment_to_row(assessment: OutcomeAssessment) -> Any:
    """Project an assessment to its flat warehouse row (kept here so both directions share it)."""
    from .models import AssessmentRow

    return AssessmentRow(
        assessment_id=assessment.assessment_id,
        tenant=assessment.tenant,
        as_of=assessment.as_of.isoformat(),
        pack_version=assessment.pack_version,
        overall=assessment.overall.value,
        severity=assessment.severity.value,
        breach_count=assessment.breach_count,
        gap_count=assessment.gap_count,
        product_count=assessment.product_count,
        signal_count=assessment.signal_count,
        breaching_families=tuple(sorted({r.family.value for r in assessment.breaches})),
        requires_human_review=assessment.requires_human_review,
        review_ref=assessment.review_ref,
    )
