"""OutcomeTestEngine: the deterministic Consumer Duty outcome tests. Pure, replayable, cited.

The consequential core of this service. Given the normalised signals, the product governance
frame and the set of vulnerable subjects contacted against preference, it produces one
:class:`OutcomeTestResult` per (family, product): the observed metric, the threshold it was
compared against, the verdict, the severity and whether it must be reviewed. It owns every number
and every verdict; the model that narrates the assessment reads these results and may only
restate them.

Four tests, each a small pure kernel:

* **foreseeable harm** : a weighted count of complaint, conduct-flag and QA-failure signals per
  product, compared to the pack's harm threshold.
* **target-market drift** : the fraction of a product's signals whose cohort is outside the
  product's approved target market.
* **price vs value** : the product's fee-per-unit-of-value, expressed as a robust z-score
  (median / MAD, resistant to the outliers in the very set it screens, the same maths Mkt4's
  anomaly service uses) across the product set, so an expensive-for-what-it-delivers product
  stands out from its peers rather than from an absolute number nobody agreed.
* **vulnerable customer** : the count of vulnerable subjects who were contacted against a
  recorded preference (the consent context, resolved read-only through the consent kit).

Determinism: same inputs and same ``as_of`` produce byte-identical results. No clock read inside
a method, no randomness, no I/O, no model. Fail-closed: a family the pack does not configure is a
GAP, not a pass (``domain/policy.py``), because a test that measured nothing must never read as
an outcome that was checked and found good.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel import Citation, Severity
from .models import (
    AssessmentRequest,
    OutcomeSignal,
    OutcomeTestFamily,
    OutcomeTestResult,
    ProductProfile,
    SignalKind,
    TestOutcome,
)
from .policy import OutcomePolicy, OutcomeThreshold

#: 0.6745 = the 0.75 quantile of the standard normal; scales MAD to a normal-consistent sigma.
_MAD_SCALE = 0.6745

#: How much each signal kind contributes to the foreseeable-harm score. Conduct flags weigh more
#: than a single complaint because they are a supervisor's judgement that something is wrong, not
#: a customer's report that something felt wrong. These are ENGINE weights (how to combine
#: evidence), not POLICY thresholds (how much is too much); the latter live in the pack.
_HARM_WEIGHTS: dict[SignalKind, float] = {
    SignalKind.COMPLAINT: 1.0,
    SignalKind.CONDUCT_FLAG: 2.0,
    SignalKind.QA_FAILURE: 1.0,
}

ENGINE_VERSION = "outcome-tests/1"


@dataclass(frozen=True, slots=True)
class OutcomeTestEngine:
    """Pure, deterministic Consumer Duty outcome testing over one tenant's signals and products."""

    def assess(
        self, request: AssessmentRequest, policy: OutcomePolicy
    ) -> tuple[OutcomeTestResult, ...]:
        """Run every family against every product, in a stable order."""
        results: list[OutcomeTestResult] = []
        by_product = self._signals_by_product(request.signals)
        for product in sorted(request.frame.products, key=lambda p: p.product_id):
            signals = by_product.get(product.product_id, ())
            results.append(self._foreseeable_harm(product, signals, policy))
            results.append(self._target_market_drift(product, signals, policy))
            results.append(self._price_vs_value(product, request.frame.products, signals, policy))
            results.append(
                self._vulnerable_customer(product, signals, request.consent_denied_subjects, policy)
            )
        results.sort(key=lambda r: (r.product_id, r.family.value))
        return tuple(results)

    # ------------------------------------------------------------------ #
    # Grouping
    # ------------------------------------------------------------------ #
    @staticmethod
    def _signals_by_product(
        signals: tuple[OutcomeSignal, ...],
    ) -> dict[str, tuple[OutcomeSignal, ...]]:
        grouped: dict[str, list[OutcomeSignal]] = {}
        for signal in signals:
            grouped.setdefault(signal.product_id, []).append(signal)
        return {pid: tuple(items) for pid, items in grouped.items()}

    # ------------------------------------------------------------------ #
    # Test 1: foreseeable harm
    # ------------------------------------------------------------------ #
    def _foreseeable_harm(
        self,
        product: ProductProfile,
        signals: tuple[OutcomeSignal, ...],
        policy: OutcomePolicy,
    ) -> OutcomeTestResult:
        family = OutcomeTestFamily.FORESEEABLE_HARM
        threshold = policy.for_family(family)
        contributing = tuple(s for s in signals if s.kind in _HARM_WEIGHTS)
        observed = round(sum(_HARM_WEIGHTS[s.kind] * s.value for s in contributing), 6)
        rationale = (
            f"Weighted harm score {observed:g} from {len(contributing)} complaint / conduct / "
            f"QA signals for product {product.product_id}."
        )
        return self._verdict(family, product, observed, threshold, contributing, rationale)

    # ------------------------------------------------------------------ #
    # Test 2: target-market drift
    # ------------------------------------------------------------------ #
    def _target_market_drift(
        self,
        product: ProductProfile,
        signals: tuple[OutcomeSignal, ...],
        policy: OutcomePolicy,
    ) -> OutcomeTestResult:
        family = OutcomeTestFamily.TARGET_MARKET_DRIFT
        threshold = policy.for_family(family)
        total = len(signals)
        off_target = tuple(s for s in signals if s.cohort not in product.target_cohorts)
        observed = round(len(off_target) / total, 6) if total else 0.0
        rationale = (
            f"{len(off_target)} of {total} signals for product {product.product_id} came from "
            f"cohorts outside its target market {tuple(product.target_cohorts)}; drift "
            f"{observed:.2%}."
        )
        return self._verdict(family, product, observed, threshold, off_target, rationale)

    # ------------------------------------------------------------------ #
    # Test 3: price vs value (robust z across the product set)
    # ------------------------------------------------------------------ #
    def _price_vs_value(
        self,
        product: ProductProfile,
        products: tuple[ProductProfile, ...],
        signals: tuple[OutcomeSignal, ...],
        policy: OutcomePolicy,
    ) -> OutcomeTestResult:
        family = OutcomeTestFamily.PRICE_VS_VALUE
        threshold = policy.for_family(family)
        ratios = [p.price_value_ratio for p in products]
        median = self._median(ratios)
        mad = self._mad(ratios, median)
        observed = round(self._robust_z(product.price_value_ratio, median, mad), 6)
        rationale = (
            f"Product {product.product_id} price-to-value ratio {product.price_value_ratio:.3f} "
            f"is robust z {observed:g} against the product-set median {median:.3f}."
        )
        return self._verdict(family, product, observed, threshold, signals[:0], rationale)

    # ------------------------------------------------------------------ #
    # Test 4: vulnerable-customer mishandling
    # ------------------------------------------------------------------ #
    def _vulnerable_customer(
        self,
        product: ProductProfile,
        signals: tuple[OutcomeSignal, ...],
        consent_denied_subjects: frozenset[str],
        policy: OutcomePolicy,
    ) -> OutcomeTestResult:
        family = OutcomeTestFamily.VULNERABLE_CUSTOMER
        threshold = policy.for_family(family)
        vulnerable = {
            s.subject_id for s in signals if s.kind is SignalKind.VULNERABILITY_CUE and s.subject_id
        }
        contacted = {
            s.subject_id for s in signals if s.kind is SignalKind.CONTACT_OUTCOME and s.subject_id
        }
        mishandled_subjects = sorted(vulnerable & contacted & consent_denied_subjects)
        observed = float(len(mishandled_subjects))
        contributing = tuple(
            s
            for s in signals
            if s.subject_id in mishandled_subjects
            and s.kind in (SignalKind.VULNERABILITY_CUE, SignalKind.CONTACT_OUTCOME)
        )
        rationale = (
            f"{len(mishandled_subjects)} vulnerable subject(s) on product {product.product_id} "
            "were contacted against a recorded preference (consent not granted)."
        )
        return self._verdict(family, product, observed, threshold, contributing, rationale)

    # ------------------------------------------------------------------ #
    # Shared verdict shaping (the ONE place fail-closed lives)
    # ------------------------------------------------------------------ #
    def _verdict(
        self,
        family: OutcomeTestFamily,
        product: ProductProfile,
        observed: float,
        threshold: OutcomeThreshold | None,
        contributing: tuple[OutcomeSignal, ...],
        rationale: str,
    ) -> OutcomeTestResult:
        signal_ids = tuple(s.signal_id for s in contributing)
        signal_citations = tuple(s.citation for s in contributing if s.citation is not None)
        if threshold is None:
            # Fail closed: an unconfigured test is a GAP, never a pass.
            return OutcomeTestResult(
                test_id=f"{family.value}:{product.product_id}",
                family=family,
                product_id=product.product_id,
                cohort="all",
                observed=observed,
                threshold=float("nan"),
                outcome=TestOutcome.GAP,
                severity=Severity.HIGH,
                requires_human_review=True,
                rationale=(
                    f"{family.value} is not configured in the active pack, so it is a GAP for "
                    f"product {product.product_id}: a test that measured nothing is never a pass."
                ),
                signal_ids=signal_ids,
                citations=signal_citations,
            )
        breach = threshold.breached(observed)
        outcome = TestOutcome.BREACH if breach else TestOutcome.PASS
        citations: tuple[Citation, ...] = (threshold.citation, *signal_citations)
        return OutcomeTestResult(
            test_id=f"{family.value}:{product.product_id}",
            family=family,
            product_id=product.product_id,
            cohort="all",
            observed=observed,
            threshold=threshold.threshold,
            outcome=outcome,
            severity=threshold.severity if breach else Severity.LOW,
            requires_human_review=breach,
            rationale=rationale,
            signal_ids=signal_ids,
            citations=citations if breach else (threshold.citation,),
        )

    # ------------------------------------------------------------------ #
    # Robust statistics (stdlib only), mirroring Mkt4's anomaly service
    # ------------------------------------------------------------------ #
    @staticmethod
    def _median(values: list[float]) -> float:
        s = sorted(values)
        n = len(s)
        if n == 0:
            return 0.0
        mid = n // 2
        if n % 2 == 1:
            return s[mid]
        return (s[mid - 1] + s[mid]) / 2.0

    def _mad(self, values: list[float], median: float) -> float:
        return self._median([abs(v - median) for v in values])

    def _robust_z(self, value: float, median: float, mad: float) -> float:
        if mad <= 0:
            # Degenerate set (no spread): only an exact match is non-anomalous.
            if value == median:
                return 0.0
            return 999.0 if value > median else -999.0
        return _MAD_SCALE * (value - median) / mad


def overall_verdict(results: tuple[OutcomeTestResult, ...]) -> tuple[Severity, bool]:
    """The aggregate severity and review flag: worst breaching severity, review if any breached."""
    rank = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
    breaching = [r for r in results if r.breaching]
    if not breaching:
        return Severity.LOW, False
    worst = max(breaching, key=lambda r: rank[r.severity])
    return worst.severity, True
