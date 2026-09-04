"""API request/response schemas (Pydantic) mapped to/from the pure-domain models."""

from __future__ import annotations

from pydantic import BaseModel

from ..domain.models import OutcomeAssessment


class AssessRequest(BaseModel):
    #: The tenant to assess. Server-side identity supersedes this: the audited actor and the
    #: tenant boundary come from the verified principal, and a body field can only NARROW to the
    #: principal's own tenant, never widen to another.
    tenant: str = ""


class CitationModel(BaseModel):
    source_id: str
    title: str
    snippet: str = ""


class OutcomeTestModel(BaseModel):
    test_id: str
    family: str
    product_id: str
    observed: float
    threshold: float
    outcome: str
    severity: str
    requires_human_review: bool
    rationale: str
    signal_ids: list[str] = []
    citations: list[CitationModel] = []


class ThemeModel(BaseModel):
    theme_id: str
    family: str
    title: str
    breach_count: int
    product_ids: list[str] = []
    signal_ids: list[str] = []


class NarrationModel(BaseModel):
    headline: str
    body: str
    model: str = ""
    grounded: bool = True
    citations: list[CitationModel] = []


class AssessmentResponse(BaseModel):
    assessment_id: str
    tenant: str
    as_of: str
    pack_version: str
    engine_version: str
    overall: str
    severity: str
    requires_human_review: bool
    signal_count: int
    product_count: int
    breach_count: int
    gap_count: int
    #: Where the escalation WENT (rule R8): the human-review-console review id, or the local queue
    #: reference. Empty only when the assessment did not escalate.
    review_ref: str = ""
    results: list[OutcomeTestModel] = []
    themes: list[ThemeModel] = []
    narration: NarrationModel | None = None
    citations: list[CitationModel] = []

    @classmethod
    def from_domain(cls, assessment: OutcomeAssessment) -> AssessmentResponse:
        return cls(
            assessment_id=assessment.assessment_id,
            tenant=assessment.tenant,
            as_of=assessment.as_of.isoformat(),
            pack_version=assessment.pack_version,
            engine_version=assessment.engine_version,
            overall=assessment.overall.value,
            severity=assessment.severity.value,
            requires_human_review=assessment.requires_human_review,
            signal_count=assessment.signal_count,
            product_count=assessment.product_count,
            breach_count=assessment.breach_count,
            gap_count=assessment.gap_count,
            review_ref=assessment.review_ref,
            results=[
                OutcomeTestModel(
                    test_id=r.test_id,
                    family=r.family.value,
                    product_id=r.product_id,
                    observed=r.observed,
                    threshold=r.threshold,
                    outcome=r.outcome.value,
                    severity=r.severity.value,
                    requires_human_review=r.requires_human_review,
                    rationale=r.rationale,
                    signal_ids=list(r.signal_ids),
                    citations=[_c(c) for c in r.citations],
                )
                for r in assessment.results
            ],
            themes=[
                ThemeModel(
                    theme_id=t.theme_id,
                    family=t.family.value,
                    title=t.title,
                    breach_count=t.breach_count,
                    product_ids=list(t.product_ids),
                    signal_ids=list(t.signal_ids),
                )
                for t in assessment.themes
            ],
            narration=(
                NarrationModel(
                    headline=assessment.narration.headline,
                    body=assessment.narration.body,
                    model=assessment.narration.model,
                    grounded=assessment.narration.grounded,
                    citations=[_c(c) for c in assessment.narration.citations],
                )
                if assessment.narration is not None
                else None
            ),
            citations=[_c(c) for c in assessment.citations],
        )


def _c(citation: object) -> CitationModel:
    return CitationModel(
        source_id=getattr(citation, "source_id", ""),
        title=getattr(citation, "title", ""),
        snippet=getattr(citation, "snippet", ""),
    )


class HealthResponse(BaseModel):
    status: str
    profile: str
    region: str
    #: Provenance the UI banner states on every page: where the runtime sits and which model
    #: answers. Both are read off the service because the browser cannot know either.
    runtime: str = "local"  # "gcp" | "local"
    generator_model: str = "deterministic-offline-stub"
