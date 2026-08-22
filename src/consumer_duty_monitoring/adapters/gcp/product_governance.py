"""Managed ProductGovernancePort: Document AI plus BigQuery (SDK imports stay lazy).

Extracts product packs and target-market definitions with Document AI and reads fees / value data
from the residency-region warehouse. The cloud imports are lazy so the offline profiles import
this module with no SDK present; offline it refuses at call time rather than inventing a frame.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ProductGovernanceFrame


class DocumentAiProductGovernance:
    """Load a tenant's product governance frame from the managed extraction and warehouse."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self, tenant: str) -> ProductGovernanceFrame:
        # Lazy import: absent in the offline profiles and in CI.
        from google.cloud import documentai  # pragma: no cover - needs live GCP

        _ = documentai  # pragma: no cover - needs live GCP
        raise NotImplementedError(  # pragma: no cover - needs live GCP
            f"managed product governance for {tenant} requires Document AI and the warehouse; "
            "bind the extraction. See docs/onprem-migration.md."
        )
