"""ProductGovernancePort: the product packs, target-market definitions and fee / value inputs.

The outcome-test engine compares each product's signals against its APPROVED target market and
its fee against the value it delivers. Those facts (the product pack, the target-market
definition, the fees and the benefit score) come from the firm's product governance records, and
this port is the hexagon boundary to wherever they live.

The offline family reads obviously-synthetic product fixtures; the managed family reads
Document AI extractions and BigQuery with a lazy import; the on-premises family refuses. The
engine never learns a product name or a fee as a constant: it reads them here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import ProductGovernanceFrame


@runtime_checkable
class ProductGovernancePort(Protocol):
    def load(self, tenant: str) -> ProductGovernanceFrame:
        """Return ``tenant``'s product governance frame (target markets, fees, benefit scores)."""
        ...
