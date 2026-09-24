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
from .ports.review_router import ReviewRouterPort


def build_service(
    container: Container, *, review_router: ReviewRouterPort | None = None
) -> AssessmentService:
    """Wire every port the assessment path needs. No surface may build a narrower one.

    ``review_router`` is the per-call recording wrapper a surface passes so its answer can say
    what happened to the hand-off (the fleet's runtime-control contract); it wraps
    ``container.review_router`` and never replaces it with a different router.
    """
    return AssessmentService(
        audit=container.audit,
        signals=container.signal_source,
        products=container.product_governance,
        consent=container.consent,
        store=container.assessment_store,
        review_router=review_router if review_router is not None else container.review_router,
        narrator=container.narration,
        warehouse=container.warehouse,
        tracer=container.tracer,
    )


def policy_for(container: Container) -> OutcomePolicy:
    """The active outcome-test policy for this deployment (adopter override, else the reference)."""
    return pack_for(container.settings)
