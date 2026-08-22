"""On-prem SignalSourcePort: fail-fast portability placeholder (the exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import OutcomeSignal


class OnPremSignalSource:
    """Satisfies SignalSourcePort but refuses: the client's systems of record are the client's."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self, tenant: str) -> tuple[OutcomeSignal, ...]:
        raise NotImplementedError(
            "on-prem signal intake is a portability placeholder: bind the client's own complaint, "
            "conversation and recommendation feeds (see docs/onprem-migration.md). Returning no "
            "signals would look exactly like a clean book."
        )
