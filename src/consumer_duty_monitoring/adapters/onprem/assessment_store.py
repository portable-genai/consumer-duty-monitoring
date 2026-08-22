"""On-prem AssessmentStorePort: fail-fast portability placeholder (the exit proof, P-12)."""

from __future__ import annotations

from ...config import Settings
from ...domain.models import OutcomeAssessment


class OnPremAssessmentStore:
    """Satisfies AssessmentStorePort but refuses: the client's store is the client's."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_for_product(self, tenant: str, product_id: str) -> tuple[OutcomeAssessment, ...]:
        raise NotImplementedError(
            "on-prem assessment store is a portability placeholder: bind the client's own store "
            "(see docs/onprem-migration.md)."
        )

    def get(self, assessment_id: str) -> OutcomeAssessment | None:
        raise NotImplementedError(
            "on-prem assessment store is a portability placeholder: bind the client's own store "
            "(see docs/onprem-migration.md)."
        )

    def put(self, assessment: OutcomeAssessment) -> str:
        raise NotImplementedError(
            "on-prem assessment store is a portability placeholder: bind the client's own store "
            "(see docs/onprem-migration.md)."
        )
