"""On-prem NarrationPort: fail-fast portability placeholder (the exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import Narration
from ...ports.narration import NarrationBrief


class OnPremNarrator:
    """Satisfies NarrationPort but refuses: the client binds its own model gateway."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def narrate(self, brief: NarrationBrief) -> Narration | None:
        raise NotImplementedError(
            "on-prem narration is a portability placeholder: bind the client's own model gateway "
            "(see docs/onprem-migration.md). The narration is optional and the assessment stands "
            "on its deterministic verdict regardless."
        )
