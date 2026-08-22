"""The outcome-test policy value objects: adopter-owned thresholds, as pure domain values.

Which harm rate is tolerable, how far a product may drift from its target market, how expensive
a product may be relative to the value it delivers, and how many vulnerable-customer mishandlings
trigger a breach are POLICY, not algorithm. They are the adopting firm's Consumer Duty risk
appetite, set per product review schedule, and each cites the regulator instrument it derives
from. So they live in a pack file a compliance officer can read and diff (``outcome_pack.py``
loads it), and arrive in the engine as this frozen value object. The engine carries no threshold
of its own.

Fail-closed by construction: :meth:`OutcomePolicy.for_family` returns ``None`` for a family the
pack does not configure, and the engine turns that into a GAP verdict, never a pass. An
unconfigured test has measured nothing, and reading nothing as a pass is the exact failure a
Consumer Duty monitor must not have.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .kernel import Citation, Severity
from .models import OutcomeTestFamily


@dataclass(frozen=True, slots=True)
class OutcomeThreshold:
    """One family's breach threshold, the severity a breach carries, and its cited instrument.

    ``comparison`` names how ``observed`` is tested against ``threshold``: ``ge`` means a breach
    when the observed value is at or above the threshold (the harm, drift, price-vs-value and
    mishandling tests all read this way, because more is worse).
    """

    family: OutcomeTestFamily
    threshold: float
    severity: Severity
    citation: Citation
    comparison: str = "ge"

    def breached(self, observed: float) -> bool:
        if self.comparison == "ge":
            return observed >= self.threshold
        raise ValueError(f"unknown comparison {self.comparison!r} for {self.family.value}")


@dataclass(frozen=True, slots=True)
class OutcomePolicy:
    """The whole configured policy: one threshold per configured family, plus its version."""

    version: str
    thresholds: Mapping[OutcomeTestFamily, OutcomeThreshold]

    def for_family(self, family: OutcomeTestFamily) -> OutcomeThreshold | None:
        """The threshold for ``family``, or ``None`` when the pack does not configure it (a GAP)."""
        return self.thresholds.get(family)
