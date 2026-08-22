"""Local ProductGovernancePort: SDK-free product packs, target markets and fee / value inputs.

The offline stand-in for the managed extraction (Document AI plus BigQuery). It serves the shared
synthetic product frame (``_seed.py``): the products, their approved target markets, their fees and
their benefit scores, all obviously fictional. The engine reads these rather than carrying any
product name or fee as a constant.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ProductGovernanceFrame
from ._seed import seed_frame


class LocalProductGovernance:
    """Serve a tenant's product governance frame from the offline synthetic dataset."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self, tenant: str) -> ProductGovernanceFrame:
        return seed_frame(tenant)
