"""Assembly: build the domain service from the container, in one place.

The domain must not import ``config`` (it is pure and knows nothing about profiles or YAML), and
``config`` must not import the domain service (it binds ports and stops there). This module is the
seam between them, so every surface (API, CLI, agent, demo, eval) constructs the service
identically instead of each wiring its own subset of ports and quietly omitting one.

Omitting one is not hypothetical: a surface that forgot the review router would still produce
correct assessments and would silently stop honouring rule R8.
"""

from __future__ import annotations

from .config import Container
from .domain.assessment_service import AssessmentService
from .domain.policy import OutcomePolicy
from .outcome_pack import pack_for


def build_service(container: Container) -> AssessmentService:
    """Wire every port the assessment path needs. No surface may build a narrower one."""
    return AssessmentService(
        audit=container.audit,
        signals=container.signal_source,
        products=container.product_governance,
        consent=container.consent,
        store=container.assessment_store,
        review_router=container.review_router,
        narrator=container.narration,
        warehouse=container.warehouse,
        tracer=container.tracer,
    )


def policy_for(container: Container) -> OutcomePolicy:
    """The active outcome-test policy for this deployment (adopter override, else the reference)."""
    return pack_for(container.settings)
