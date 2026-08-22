"""Managed AssessmentStorePort: Firestore in the residency region (SDK imports stay lazy).

Persists assessments to Firestore in the deployment's residency region. The tenant partition is a
document field filtered in :meth:`list_for_product`; :meth:`get` is deliberately unfiltered and the
domain authorizes the tenant. The ``google.cloud`` import is lazy, so the offline profiles import
this module with no SDK present; offline every method refuses at call time.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import OutcomeAssessment


class FirestoreAssessmentStore:
    """Serve tenant-scoped assessments from Firestore."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _client(self) -> object:
        # Lazy import: absent in the offline profiles and in CI.
        from google.cloud import firestore  # pragma: no cover - needs live GCP

        return firestore.Client()  # pragma: no cover - needs live GCP

    def list_for_product(self, tenant: str, product_id: str) -> tuple[OutcomeAssessment, ...]:
        self._client()  # pragma: no cover - needs live GCP
        raise NotImplementedError(  # pragma: no cover - needs live GCP
            "managed assessment store requires Firestore; see docs/onprem-migration.md."
        )

    def get(self, assessment_id: str) -> OutcomeAssessment | None:
        self._client()  # pragma: no cover - needs live GCP
        raise NotImplementedError(  # pragma: no cover - needs live GCP
            "managed assessment store requires Firestore; see docs/onprem-migration.md."
        )

    def put(self, assessment: OutcomeAssessment) -> str:
        self._client()  # pragma: no cover - needs live GCP
        raise NotImplementedError(  # pragma: no cover - needs live GCP
            "managed assessment store requires Firestore; see docs/onprem-migration.md."
        )
