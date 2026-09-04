"""Theme synthesis: deterministic counting owns every figure; a model may only restate them.

An assessment across many products produces many individual verdicts. A board reads themes, not
a hundred rows, so this module groups the breaching and gapped results into one theme per outcome
family, counting deterministically: the breach count, the products implicated and the signal ids
behind them are all computed here, in pure stdlib.

The merge rule mirrors complaints-review's categorization service: the deterministic themes are
AUTHORITATIVE. A model narrator (``domain/narration.py``) may phrase them and add cited colour, but
it cannot remove a theme the counting produced or change a count. Embedding-based clustering, when a
managed profile provides it, is advisory only and never edits these figures.
"""

from __future__ import annotations

from .kernel import Citation
from .models import (
    OutcomeTestFamily,
    OutcomeTestResult,
    TestOutcome,
    Theme,
)

_FAMILY_TITLES: dict[OutcomeTestFamily, str] = {
    OutcomeTestFamily.FORESEEABLE_HARM: "Foreseeable harm indicators",
    OutcomeTestFamily.TARGET_MARKET_DRIFT: "Target-market drift",
    OutcomeTestFamily.PRICE_VS_VALUE: "Price and fair value",
    OutcomeTestFamily.VULNERABLE_CUSTOMER: "Vulnerable-customer treatment",
}


def synthesize_themes(results: tuple[OutcomeTestResult, ...]) -> tuple[Theme, ...]:
    """One theme per family with a breaching or gapped result. Counting is deterministic."""
    by_family: dict[OutcomeTestFamily, list[OutcomeTestResult]] = {}
    for result in results:
        if result.breaching:
            by_family.setdefault(result.family, []).append(result)

    themes: list[Theme] = []
    for family in sorted(by_family, key=lambda f: f.value):
        family_results = by_family[family]
        breach_count = sum(1 for r in family_results if r.outcome is TestOutcome.BREACH)
        gap_count = sum(1 for r in family_results if r.outcome is TestOutcome.GAP)
        products = tuple(sorted({r.product_id for r in family_results}))
        signal_ids = tuple(sorted({sid for r in family_results for sid in r.signal_ids}))
        citations = _dedupe_citations(family_results)
        title = _FAMILY_TITLES[family]
        if gap_count:
            title = f"{title} (with {gap_count} unconfigured gap(s))"
        themes.append(
            Theme(
                theme_id=f"theme:{family.value}",
                family=family,
                title=title,
                breach_count=breach_count + gap_count,
                product_ids=products,
                signal_ids=signal_ids,
                citations=citations,
            )
        )
    return tuple(themes)


def _dedupe_citations(results: list[OutcomeTestResult]) -> tuple[Citation, ...]:
    seen: set[str] = set()
    out: list[Citation] = []
    for result in results:
        for citation in result.citations:
            if citation.source_id not in seen:
                seen.add(citation.source_id)
                out.append(citation)
    return tuple(out)
