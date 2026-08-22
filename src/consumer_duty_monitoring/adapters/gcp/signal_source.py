"""Managed SignalSourcePort: BigQuery plus the sibling services (SDK imports stay lazy).

Reads normalised outcome signals from the residency-region warehouse the sibling systems land
their outputs in (Doc6 complaint categorisations and conduct flags, E3 scorecards, Mkt5
next-best-action outcomes, and F2 intake once built). The ``google.cloud`` import is lazy, so the
offline profiles import this module with no cloud SDK present; offline it refuses at call time
rather than pretending, because a monitor that silently read no signals would report a clean book.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import OutcomeSignal


class BigQuerySignalSource:
    """Load tenant-scoped normalised signals from the managed warehouse."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self, tenant: str) -> tuple[OutcomeSignal, ...]:
        # Lazy import: absent in the offline profiles and in CI.
        from google.cloud import bigquery  # pragma: no cover - needs live GCP

        client = bigquery.Client()  # pragma: no cover - needs live GCP
        raise NotImplementedError(  # pragma: no cover - needs live GCP
            f"managed signal intake for {tenant} requires the residency-region warehouse; "
            f"bind the query for {client}. See docs/onprem-migration.md."
        )
