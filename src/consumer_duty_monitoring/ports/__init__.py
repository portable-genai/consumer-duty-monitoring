"""The hexagon's boundaries, re-exported once so there is a single import site.

Every port is a ``@runtime_checkable`` Protocol and every port has a binding in every profile
(``config.DEFAULT_BINDINGS``); ``tests/contract/test_port_parity.py`` asserts both, plus set
equality in the reverse direction so a port added here without a binding fails the build.

``IdentityPort`` is not redeclared: it comes from the shared ``hex-service-kit`` commons and is
re-exported here so consumers still have one import site for the boundary set. What an identity
adapter DECLARES about the authentication it provides is this service's own vocabulary, not the
commons', and lives in :mod:`.identity` next to the re-export.
"""

from __future__ import annotations

from hex_service_kit.identity import IdentityPort

from .assessment_store import AssessmentStorePort
from .audit import AuditSinkPort
from .consent import ConsentLookupPort
from .identity import (
    CLIENT_ASSERTED,
    END_USER_AUTH_ATTR,
    END_USER_AUTH_KINDS,
    UNIMPLEMENTED,
    VERIFIED,
    EndUserAuthUnavailableError,
    declared_end_user_auth,
)
from .narration import NarrationBrief, NarrationPort
from .observability import (
    EvaluationGatePort,
    ObservabilityTracerPort,
    TokenUsage,
)
from .outcome_signals import SignalSourcePort
from .product_governance import ProductGovernancePort
from .review_router import ReviewRouterPort
from .warehouse import WarehouseExportPort

#: port name (the key in the settings ``adapters:`` block) -> the Protocol it must satisfy.
PORT_PROTOCOLS: dict[str, type] = {
    "assessment_store": AssessmentStorePort,
    "audit": AuditSinkPort,
    "consent": ConsentLookupPort,
    "identity": IdentityPort,
    "narration": NarrationPort,
    "product_governance": ProductGovernancePort,
    "review_router": ReviewRouterPort,
    "signal_source": SignalSourcePort,
    "warehouse": WarehouseExportPort,
    "tracer": ObservabilityTracerPort,
    "evaluation": EvaluationGatePort,
}

__all__ = [
    "TokenUsage",
    "ObservabilityTracerPort",
    "EvaluationGatePort",
    "CLIENT_ASSERTED",
    "END_USER_AUTH_ATTR",
    "END_USER_AUTH_KINDS",
    "PORT_PROTOCOLS",
    "UNIMPLEMENTED",
    "VERIFIED",
    "AssessmentStorePort",
    "AuditSinkPort",
    "ConsentLookupPort",
    "EndUserAuthUnavailableError",
    "IdentityPort",
    "NarrationBrief",
    "NarrationPort",
    "ProductGovernancePort",
    "ReviewRouterPort",
    "SignalSourcePort",
    "WarehouseExportPort",
    "declared_end_user_auth",
]
