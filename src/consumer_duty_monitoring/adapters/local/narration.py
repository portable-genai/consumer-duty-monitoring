"""Local NarrationPort: the SDK-free narrator. Deterministic, and deliberately unimpressive.

The offline profile has no model, so this composes the same grounded sentences the domain's
fallback would, from the brief and nothing else. It exists so the narration SEAM is exercised in
the gate, the demo and the eval rather than being a code path nobody runs until production: the
grounding validator, the fallback and the "identical with the model stubbed out" check all run
against a real bound adapter here.

Everything it writes is drawn from ``brief.allowed_figures`` and ``brief.theme_titles``, so it
passes the grounding gate by construction, which makes this adapter a standing proof that the gate
is not so strict it rejects a correct narration.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import Narration
from ...ports.narration import NarrationBrief

_MODEL = "offline-deterministic"


class LocalNarrator:
    """Compose a grounded board narrative offline, with no model and no network."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def narrate(self, brief: NarrationBrief) -> Narration | None:
        verdict = brief.overall.replace("_", " ")
        sentences = [
            f"Consumer Duty assessment for {brief.tenant} is {verdict} at severity "
            f"{brief.severity} across {brief.product_count} product(s) and "
            f"{brief.signal_count} signal(s).",
        ]
        if brief.theme_titles:
            sentences.append("Themes: " + "; ".join(brief.theme_titles) + ".")
        else:
            sentences.append("No outcome test breached or gapped.")
        sentences.append(
            f"{brief.breach_count} breach(es) and {brief.gap_count} unconfigured gap(s)."
        )
        return Narration(
            headline=f"{verdict}: {brief.tenant}",
            body=" ".join(sentences),
            citations=(),
            model=_MODEL,
            grounded=True,
        )
