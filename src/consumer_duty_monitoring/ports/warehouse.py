"""WarehouseExportPort: the analytics seam, and the narrowest data the service ever emits.

A Consumer Duty programme is only useful when the whole book of products can be looked at: breach
rates by product, by theme, by quarter, on a board dashboard. That is a warehouse question, so
this port exists.

It takes :class:`~..domain.models.AssessmentRow`, the deliberately FLAT projection of an
assessment, and never a signal, never a subject id and never free text. Shipping signal detail
into an analytics table is how a monitoring programme becomes a data-protection incident: the
rows are joined, copied into notebooks and exported to spreadsheets by people who never saw the
retention policy. The evidence stays in the tenant-scoped assessment store, behind the 403.

The managed adapter streams to BigQuery in the residency region with a lazy import; the offline
adapter appends JSON Lines to a local path so the export is inspectable in the gate and the demo;
the on-premises adapter refuses, because the client's warehouse is the client's.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..domain.models import AssessmentRow


@runtime_checkable
class WarehouseExportPort(Protocol):
    def export(self, rows: Sequence[AssessmentRow]) -> int:
        """Append ``rows`` to the warehouse and return how many were accepted.

        A count rather than ``None`` so a caller can record what left the service; an export that
        silently accepted nothing is indistinguishable from one that worked.
        """
        ...
