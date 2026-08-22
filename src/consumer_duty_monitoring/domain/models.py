"""Vertical artifact models: the Consumer Duty outcome-monitoring types.

The artifacts THIS vertical reasons over and produces, as opposed to the vertical-neutral
machinery in ``kernel.py``. The service's own name is deliberately kept out of these docstrings:
a rendered line whose length depends on ``friendly_name`` fails the repo's own format check for
no reason but the length of its name.

Everything here is a frozen, slotted, pure-stdlib value object. The consequential numbers (every
observed metric, every threshold comparison, every outcome and severity) are produced by
``domain/outcome_tests.py`` and only recorded here; a model may narrate an assessment but never
computes one. A fork building a different vertical rewrites this module and keeps ``kernel.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from hex_service_kit.enums import LenientStrEnum

from .kernel import Citation, Decision, Severity


class SignalSource(LenientStrEnum):
    """Where a normalised outcome signal came from. Feed-agnostic by design.

    Rgc15 is a named consumer of built Doc6 complaint categorisations and conduct flags, of E3
    conversation-QA scorecards, and of Mkt5 next-best-action outcomes. ``INTAKE`` is the F2
    complaints-intake feed, declared here but not yet built: its adapter registers on arrival as
    configuration only, and until then the F2 slice reads from a declared fixture.
    """

    COMPLAINTS = "complaints"
    CONVERSATION_QA = "conversation_qa"
    NEXT_BEST_ACTION = "next_best_action"
    INTAKE = "intake"


class SignalKind(LenientStrEnum):
    """What one signal asserts. The engine weights these; it never reads free text."""

    COMPLAINT = "complaint"
    CONDUCT_FLAG = "conduct_flag"
    QA_FAILURE = "qa_failure"
    VULNERABILITY_CUE = "vulnerability_cue"
    CONTACT_OUTCOME = "contact_outcome"


class OutcomeTestFamily(LenientStrEnum):
    """The four Consumer Duty outcome tests this service runs, each its own deterministic kernel."""

    FORESEEABLE_HARM = "foreseeable_harm"
    TARGET_MARKET_DRIFT = "target_market_drift"
    PRICE_VS_VALUE = "price_vs_value"
    VULNERABLE_CUSTOMER = "vulnerable_customer"


class TestOutcome(LenientStrEnum):
    """One outcome-test verdict. ``GAP`` is the fail-closed state: an unconfigured test is never
    a ``PASS``, because a test the pack does not configure has measured nothing."""

    #: Not a pytest test class. The name begins with ``Test`` (an outcome-TEST verdict), so pytest
    #: tries to collect it and warns that it cannot; this dunder is a class attribute, never an
    #: enum member (enum ignores dunders), and tells the collector to leave the type alone.
    __test__ = False

    PASS = "pass"
    BREACH = "breach"
    GAP = "gap"


@dataclass(frozen=True, slots=True)
class OutcomeSignal:
    """One normalised complaint / conversation / recommendation signal.

    The single shape every source adapter maps into, so the engine reads one vocabulary rather
    than three feed schemas. ``value`` is a normalised magnitude (``1.0`` for a discrete event,
    a score otherwise); ``subject_id`` is present only where a downstream consent lookup needs it
    (the vulnerable-customer test), and is a synthetic pseudonymous id, never a raw identifier.
    """

    signal_id: str
    source: SignalSource
    kind: SignalKind
    tenant: str
    product_id: str
    cohort: str
    value: float = 1.0
    subject_id: str = ""
    channel: str = ""
    observed_date: str = ""
    citation: Citation | None = None


@dataclass(frozen=True, slots=True)
class ProductProfile:
    """A product's governance frame: its defined target market and its price / value inputs.

    ``target_cohorts`` is the target market the product was approved for; a signal from any other
    cohort is target-market drift. ``annual_fee`` and ``benefit_score`` (0..100) are the two
    inputs the price-vs-value test compares across the product set. Both come from the product
    pack, never from the engine.
    """

    product_id: str
    name: str
    target_cohorts: tuple[str, ...]
    annual_fee: float
    benefit_score: float
    citation: Citation

    @property
    def price_value_ratio(self) -> float:
        """Fee per unit of delivered value. Higher is worse value for the customer."""
        return self.annual_fee / max(self.benefit_score, 1e-9)


@dataclass(frozen=True, slots=True)
class ProductGovernanceFrame:
    """The product set an assessment runs against, for one tenant."""

    tenant: str
    products: tuple[ProductProfile, ...]

    def by_id(self, product_id: str) -> ProductProfile | None:
        return next((p for p in self.products if p.product_id == product_id), None)


@dataclass(frozen=True, slots=True)
class OutcomeTestResult:
    """One outcome test's verdict for one product. Every number here is engine-owned."""

    test_id: str
    family: OutcomeTestFamily
    product_id: str
    cohort: str
    observed: float
    threshold: float
    outcome: TestOutcome
    severity: Severity
    requires_human_review: bool
    rationale: str
    signal_ids: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()

    @property
    def breaching(self) -> bool:
        return self.outcome in (TestOutcome.BREACH, TestOutcome.GAP)


@dataclass(frozen=True, slots=True)
class Theme:
    """A deterministically counted cross-product theme. The counting owns the figures; a model
    may only restate them and cite the signal ids listed here."""

    theme_id: str
    family: OutcomeTestFamily
    title: str
    breach_count: int
    product_ids: tuple[str, ...]
    signal_ids: tuple[str, ...]
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class Narration:
    """A model (or offline) restatement of an already-decided assessment. Never consequential.

    ``grounded`` records whether the draft passed the grounding gate; a draft that mentioned a
    figure the engine never published, or cited an instrument it never emitted, is discarded and
    the deterministic fallback stands (``domain/narration.py``).
    """

    headline: str
    body: str
    citations: tuple[Citation, ...] = ()
    model: str = ""
    grounded: bool = True


@dataclass(frozen=True, slots=True)
class OutcomeAssessment:
    """The board-facing artifact: every outcome-test verdict, the themes, and a cited narrative.

    ``overall`` and ``severity`` are the engine's aggregate verdict; ``requires_human_review`` is
    True whenever any test breached or is a gap, because a Consumer Duty assessment is
    consequential and never auto-executes. ``review_ref`` records where the escalation actually
    WENT (rule R8), so a flag that stopped here is distinguishable from a routed one.
    """

    assessment_id: str
    tenant: str
    as_of: datetime
    pack_version: str
    engine_version: str
    results: tuple[OutcomeTestResult, ...]
    themes: tuple[Theme, ...]
    overall: Decision
    severity: Severity
    requires_human_review: bool
    signal_count: int
    product_count: int
    citations: tuple[Citation, ...] = ()
    narration: Narration | None = None
    review_ref: str = ""

    @property
    def breaches(self) -> tuple[OutcomeTestResult, ...]:
        """Every breaching or gapped test, worst severity first (stable)."""
        rank = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        return tuple(
            sorted(
                (r for r in self.results if r.breaching),
                key=lambda r: (rank[r.severity], r.family.value, r.product_id),
            )
        )

    @property
    def breach_count(self) -> int:
        from .models import TestOutcome as _Outcome

        return sum(1 for r in self.results if r.outcome is _Outcome.BREACH)

    @property
    def gap_count(self) -> int:
        from .models import TestOutcome as _Outcome

        return sum(1 for r in self.results if r.outcome is _Outcome.GAP)


@dataclass(frozen=True, slots=True)
class AssessmentRow:
    """The flat, warehouse-shaped projection of an assessment (one row per assessment).

    Deliberately flat and free of any subject identifier or free text: a warehouse export is an
    analytics artifact, and shipping signal detail into an analytics table is how a monitoring
    programme becomes a data-protection incident. The evidence stays in the tenant-scoped
    assessment store, behind the 403.
    """

    assessment_id: str
    tenant: str
    as_of: str
    pack_version: str
    overall: str
    severity: str
    breach_count: int
    gap_count: int
    product_count: int
    signal_count: int
    breaching_families: tuple[str, ...] = ()
    requires_human_review: bool = False
    review_ref: str = ""


@dataclass(frozen=True, slots=True)
class AssessmentRequest:
    """Everything one assessment run needs, gathered so the engine call stays a pure function."""

    tenant: str
    as_of: datetime
    signals: tuple[OutcomeSignal, ...]
    frame: ProductGovernanceFrame
    consent_denied_subjects: frozenset[str] = field(default_factory=frozenset)
