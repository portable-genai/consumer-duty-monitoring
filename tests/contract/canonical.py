"""ONE canonical request per port, shared by the structural and behavioural contract suites.

Parity means the same request through every implementation, so the request needs a single home.
Retyping it per suite is how two "parity" tests end up asserting different things.

Each :class:`PortCase` answers three questions about one port:

* ``invoke``   : what a single canonical call to this port looks like;
* ``answered`` : what it means for the OFFLINE family to have actually answered (a port that
  returns ``None`` and records nothing has not answered, it has merely not raised);
* ``managed_refusal`` : what the MANAGED family must do when called with no cloud reachable.
  Never a silent success: either it refuses because it is unconfigured, or its lazy SDK import
  fails. Both are honest; returning as if the work happened is not.

Adding a port means adding a case here. ``test_port_parity.py`` fails the build if this table and
the port map ever disagree, so the touch list in ``CONTRIBUTING.md`` is enforced rather than
merely written down.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_eval_kit import EvalReport
from consent_preference_kit import ConsentDecision
from hex_service_kit.identity import IdentityError, Principal, RequestContext
from hex_service_kit.observability import TokenUsage

from consumer_duty_monitoring.domain.kernel import (
    AuditEvent,
    Citation,
    Decision,
    Severity,
)
from consumer_duty_monitoring.domain.models import (
    Narration,
    OutcomeAssessment,
)
from consumer_duty_monitoring.domain.serialization import assessment_to_row

from tests.fixtures import sample_cases

#: The audit record every audit-port implementation is handed. Already redacted, as the port
#: requires: a raw identifier must never reach a WORM record.
CANONICAL_EVENT = AuditEvent(
    action="assess",
    actor=sample_cases.ACTOR,
    decision=Decision.ESCALATED,
    severity=Severity.CRITICAL,
    redacted_summary="cda-fixture escalated sev critical: 4 breach(es)",
    citations=(Citation(source_id="fca_prin2a", title="FCA PRIN 2A", snippet="good outcomes"),),
)

#: The escalated assessment every review-router and store implementation is handed (R8 payload).
CANONICAL_RESULT: OutcomeAssessment = sample_cases.CANONICAL_ASSESSMENT

#: The inbound transport context every identity implementation is handed.
CANONICAL_CONTEXT = RequestContext(headers={"x-dev-persona": "auditor"})


@dataclass(frozen=True, slots=True)
class PortCase:
    """One port's canonical call plus the two verdicts the parity suites need."""

    invoke: Callable[[Any], Any]
    answered: Callable[[Any, Any], bool]
    managed_refusal: tuple[type[BaseException], ...]
    detail: str


def _audit_invoke(adapter: Any) -> Any:
    return adapter.record(CANONICAL_EVENT)


def _audit_answered(adapter: Any, _result: Any) -> bool:
    stored = adapter.log.read_all()
    return bool(stored) and stored[-1]["actor"] == sample_cases.ACTOR and adapter.verify().ok


def _identity_invoke(adapter: Any) -> Any:
    return adapter.resolve(CANONICAL_CONTEXT)


def _identity_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, Principal) and bool(result.actor)


def _review_invoke(adapter: Any) -> Any:
    return adapter.route(CANONICAL_RESULT, maker=sample_cases.ACTOR, tenant=sample_cases.TENANT)


def _review_answered(adapter: Any, result: Any) -> bool:
    return bool(result) and len(adapter.outbox.pending()) == 1


def _signals_invoke(adapter: Any) -> Any:
    return adapter.load(sample_cases.TENANT)


def _signals_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, tuple) and len(result) > 0


def _products_invoke(adapter: Any) -> Any:
    return adapter.load(sample_cases.TENANT)


def _products_answered(_adapter: Any, result: Any) -> bool:
    return bool(getattr(result, "products", ()))


def _consent_invoke(adapter: Any) -> Any:
    return adapter.decide(sample_cases.CANONICAL_CONSENT_QUERY)


def _consent_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, ConsentDecision) and bool(result.id)


def _narration_invoke(adapter: Any) -> Any:
    return adapter.narrate(sample_cases.CANONICAL_BRIEF)


def _narration_answered(_adapter: Any, result: Any) -> bool:
    return isinstance(result, Narration) and bool(result.body)


def _store_invoke(adapter: Any) -> Any:
    return adapter.put(CANONICAL_RESULT)


def _store_answered(adapter: Any, result: Any) -> bool:
    stored = adapter.get(str(result))
    return stored is not None and stored.assessment_id == CANONICAL_RESULT.assessment_id


def _warehouse_invoke(adapter: Any) -> Any:
    return adapter.export((assessment_to_row(CANONICAL_RESULT),))


def _warehouse_answered(adapter: Any, result: Any) -> bool:
    return result == 1 and len(adapter.rows) == 1


def _tracer_invoke(adapter: Any) -> Any:
    with adapter.span("canonical.unit", action="canonical"):
        adapter.record_token_usage(TokenUsage(input_tokens=7, output_tokens=2), "canonical-model")
    return True


def _tracer_answered(adapter: Any, result: Any) -> bool:
    return bool(result)


def _evaluation_invoke(adapter: Any) -> Any:
    return adapter.evaluate("eval/datasets/canonical.jsonl")


def _evaluation_answered(adapter: Any, result: Any) -> bool:
    return isinstance(result, EvalReport) and result.dataset.endswith("canonical.jsonl")


CANONICAL_CALLS: dict[str, PortCase] = {
    "assessment_store": PortCase(
        invoke=_store_invoke,
        answered=_store_answered,
        # The lazy `google.cloud` import is the first thing the managed store does.
        managed_refusal=(ImportError,),
        detail="persist and read back one assessment",
    ),
    "audit": PortCase(
        invoke=_audit_invoke,
        answered=_audit_answered,
        managed_refusal=(ImportError,),
        detail="write one already-redacted WORM record",
    ),
    "consent": PortCase(
        invoke=_consent_invoke,
        answered=_consent_answered,
        # No consent_url offline, so the managed lookup refuses before any network call.
        managed_refusal=(RuntimeError,),
        detail="return a cited consent decision, fail-closed",
    ),
    "identity": PortCase(
        invoke=_identity_invoke,
        answered=_identity_answered,
        managed_refusal=(IdentityError,),
        detail="resolve a verified principal from transport context",
    ),
    "narration": PortCase(
        invoke=_narration_invoke,
        answered=_narration_answered,
        # The lazy Vertex import is the first thing the managed narrator does.
        managed_refusal=(ImportError,),
        detail="restate a settled assessment, grounded",
    ),
    "product_governance": PortCase(
        invoke=_products_invoke,
        answered=_products_answered,
        managed_refusal=(ImportError,),
        detail="load a product governance frame",
    ),
    "review_router": PortCase(
        invoke=_review_invoke,
        answered=_review_answered,
        # Rule R8: with no console configured the managed router must refuse, not swallow.
        managed_refusal=(RuntimeError,),
        detail="route one escalated assessment to human review",
    ),
    "signal_source": PortCase(
        invoke=_signals_invoke,
        answered=_signals_answered,
        managed_refusal=(ImportError,),
        detail="load normalised outcome signals",
    ),
    "warehouse": PortCase(
        invoke=_warehouse_invoke,
        answered=_warehouse_answered,
        # No warehouse_table offline, so the managed export refuses before importing.
        managed_refusal=(RuntimeError,),
        detail="export one flat assessment row",
    ),
    "tracer": PortCase(
        invoke=_tracer_invoke,
        answered=_tracer_answered,
        # NOTHING. Tracing is not essential to correctness, so the managed adapter must not refuse
        # offline either: with no SDK it degrades to a no-op and the traced body still runs. An
        # adapter that raised here would take a request down over a diagnostic.
        managed_refusal=(),
        detail="open one span and report the cost of a model call",
    ),
    "evaluation": PortCase(
        invoke=_evaluation_invoke,
        answered=_evaluation_answered,
        # The managed gate reaches model-quality-gate over HTTP, which is unreachable offline.
        managed_refusal=(Exception,),
        detail="score one golden dataset through the promotion authority",
    ),
}
