"""AssessmentStorePort: the tenant-scoped store of produced outcome assessments.

A Consumer Duty assessment is tenant-owned data with a regulator's interest attached, so the two
read methods differ DELIBERATELY, exactly as Mkt6's evidence store and E3's scorecard store do:

* :meth:`list_for_product` takes the tenant and MUST filter on it in the store, so a query can
  never span tenants even when a caller passes another tenant's product id, and
* :meth:`get` is a raw fetch by id that does NOT filter: the caller (the domain's assessment
  service) compares the record's tenant to the VERIFIED principal's tenant and denies with
  ``TenantAccessDeniedError``, which every surface maps to HTTP 403.

Keeping the comparison in the DOMAIN, not the adapter, is what makes it true on every surface at
once: the API, the CLI and the agent tools all go through the same service, and an adapter cannot
become the only place the boundary is enforced. 403 rather than 404, deliberately: the record
EXISTS and this caller may not have it, and answering 404 makes the store probeable with an id
generator.

Never pass a client-supplied tenant into either method: the tenant comes from the ``Principal``
the identity adapter verified.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import OutcomeAssessment


@runtime_checkable
class AssessmentStorePort(Protocol):
    def list_for_product(self, tenant: str, product_id: str) -> tuple[OutcomeAssessment, ...]:
        """Assessments ``tenant`` holds mentioning ``product_id`` (store-side tenant filter)."""
        ...

    def get(self, assessment_id: str) -> OutcomeAssessment | None:
        """Return one assessment by id, or ``None``; the DOMAIN authorizes the tenant."""
        ...

    def put(self, assessment: OutcomeAssessment) -> str:
        """Upsert one assessment (the id is deterministic, so a re-run updates in place)."""
        ...
