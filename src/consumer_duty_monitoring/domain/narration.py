"""The narration grounding gate: a model may restate an assessment, never compute one.

By the time a narrator is called, the assessment is settled: every outcome-test verdict, every
count and the overall severity are engine-owned facts. The narrator's only job is to phrase them
for a board reader. This module builds the brief the narrator sees, composes the deterministic
fallback, and enforces the two rules a draft must obey or be discarded:

* it may mention only figures the engine PUBLISHED (``brief.allowed_figures``), so a draft that
  invents "97% of customers" is rejected because 97 is not in the closed set; and
* it may cite only instruments the assessment EMITTED (``brief.allowed_source_ids``).

A draft that breaks either rule is dropped and the deterministic narration stands, so a broken or
adversarial model can never move a number in front of a board. ``grounded_or_fallback`` is the
one place that decision is made, and the eval scores it against adversarial drafts built
independently, proving the gate can actually reject.
"""

from __future__ import annotations

import re

from ..ports.narration import NarrationBrief
from .kernel import Citation
from .models import Narration, OutcomeAssessment

_MODEL_FALLBACK = "offline-deterministic"

#: Number-like tokens: integers, decimals and percentages. Every one found in a draft body must
#: appear in the brief's closed set of allowed figures, or the draft is discarded.
_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")


def _figures_for(assessment: OutcomeAssessment) -> frozenset[str]:
    """The closed set of numeric strings a narration may contain."""
    figures: set[str] = {
        str(assessment.breach_count),
        str(assessment.gap_count),
        str(assessment.product_count),
        str(assessment.signal_count),
        str(len(assessment.results)),
    }
    for result in assessment.results:
        figures.add(_fmt(result.observed))
        figures.add(_fmt(result.threshold))
    for theme in assessment.themes:
        figures.add(str(theme.breach_count))
        figures.add(str(len(theme.product_ids)))
        figures.add(str(len(theme.signal_ids)))
    return frozenset(figures)


def _fmt(value: float) -> str:
    if value != value:  # NaN
        return "nan"
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def narration_brief(assessment: OutcomeAssessment) -> NarrationBrief:
    """Everything a narrator may see: the settled verdicts and the closed figure / citation sets."""
    return NarrationBrief(
        assessment_id=assessment.assessment_id,
        tenant=assessment.tenant,
        overall=assessment.overall.value,
        severity=assessment.severity.value,
        breach_count=assessment.breach_count,
        gap_count=assessment.gap_count,
        product_count=assessment.product_count,
        signal_count=assessment.signal_count,
        theme_titles=tuple(theme.title for theme in assessment.themes),
        allowed_figures=_figures_for(assessment),
        allowed_source_ids=frozenset(c.source_id for c in assessment.citations),
    )


def deterministic_narration(assessment: OutcomeAssessment) -> Narration:
    """Compose a grounded board narrative from the assessment, with no model and no network."""
    verdict = assessment.overall.value.replace("_", " ")
    sentences = [
        f"Consumer Duty assessment for {assessment.tenant} is {verdict} at severity "
        f"{assessment.severity.value} across {assessment.product_count} product(s) and "
        f"{assessment.signal_count} signal(s).",
    ]
    if assessment.themes:
        listed = "; ".join(
            f"{theme.title} ({theme.breach_count} finding(s))" for theme in assessment.themes
        )
        sentences.append(f"Themes: {listed}.")
    else:
        sentences.append("No outcome test breached or gapped.")
    sentences.append(
        f"{assessment.breach_count} breach(es) and {assessment.gap_count} unconfigured gap(s)."
    )
    return Narration(
        headline=f"{verdict}: {assessment.tenant}",
        body=" ".join(sentences),
        citations=tuple(assessment.citations[:8]),
        model=_MODEL_FALLBACK,
        grounded=True,
    )


def is_grounded(draft: Narration, brief: NarrationBrief) -> bool:
    """True when the draft mentions only allowed figures and cites only emitted instruments."""
    for token in _NUMBER.findall(draft.body):
        if token not in brief.allowed_figures:
            return False
    return all(c.source_id in brief.allowed_source_ids for c in draft.citations)


def grounded_or_fallback(
    draft: Narration | None, brief: NarrationBrief, assessment: OutcomeAssessment
) -> Narration:
    """Keep the draft only if it is grounded; otherwise the deterministic narration stands."""
    fallback = deterministic_narration(assessment)
    if draft is None:
        return fallback
    if not is_grounded(draft, brief):
        return fallback
    kept_citations: tuple[Citation, ...] = tuple(
        c for c in draft.citations if c.source_id in brief.allowed_source_ids
    )
    return Narration(
        headline=draft.headline or fallback.headline,
        body=draft.body,
        citations=kept_citations or fallback.citations,
        model=draft.model or "model",
        grounded=True,
    )
