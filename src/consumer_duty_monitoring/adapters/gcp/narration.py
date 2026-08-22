"""Managed NarrationPort: Gemini restates the assessment (SDK imports stay lazy).

Drafts the board narrative from the already-decided brief. It produces no number and no verdict:
the brief carries the closed figure and citation sets, and ``domain/narration.py`` discards a draft
that steps outside them. The Vertex import is lazy, so the offline profiles import this module with
no SDK present; offline it refuses at call time.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import Narration
from ...ports.narration import NarrationBrief


class GeminiNarrator:
    """Restate an assessment with the managed reasoning model."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def narrate(self, brief: NarrationBrief) -> Narration | None:
        # Lazy import: absent in the offline profiles and in CI, where the ImportError IS the
        # documented managed refusal.
        from google import genai  # pragma: no cover - needs live GCP

        _ = genai  # pragma: no cover - needs live GCP
        raise NotImplementedError(  # pragma: no cover - needs live GCP
            f"managed narration for {brief.assessment_id} requires the model gateway; bind the "
            f"model {self._settings.narration_model}. The narration is optional and grounded."
        )
