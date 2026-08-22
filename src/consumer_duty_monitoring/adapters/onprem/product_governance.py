"""On-prem ProductGovernancePort: fail-fast portability placeholder (the exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import ProductGovernanceFrame


class OnPremProductGovernance:
    """Satisfies ProductGovernancePort but refuses: the client's product data is the client's."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self, tenant: str) -> ProductGovernanceFrame:
        raise NotImplementedError(
            "on-prem product governance is a portability placeholder: bind the client's own "
            "product packs and target-market records (see docs/onprem-migration.md)."
        )
