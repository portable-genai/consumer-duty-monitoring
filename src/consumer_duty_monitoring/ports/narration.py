"""NarrationPort: the model boundary, and the narrowest surface in this service.

A narrator receives a :class:`NarrationBrief` that has ALREADY been decided: every outcome-test
verdict, every count and the overall severity are settled facts by the time this port is called.
The model's only job is to restate them in a paragraph a board can read.

Three constraints, each enforced elsewhere rather than trusted here:

* **It may only restate.** The brief carries the closed set of figures the engine published and
  the closed set of instruments it cited, and ``domain/narration.py`` validates the returned draft
  against both. A draft that mentions a figure the engine did not publish, or cites an instrument
  it did not emit, is DISCARDED and the deterministic narration stands.
* **It sees an already-decided, already-redacted brief.** No raw identifier and no signal detail
  reaches a model; the brief carries counts, verdicts and instrument ids only.
* **It is optional.** Returning ``None`` is a first-class answer, and so is RAISING. The domain
  turns any failure into the deterministic fallback, so an assessment is never blocked on a model
  being reachable and a broken managed binding is never invisible.

The adapters are the usual three: an offline deterministic drafter with no SDK, the managed Gemini
adapter with a lazy import, and the on-premises placeholder that refuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..domain.models import Narration


@dataclass(frozen=True, slots=True)
class NarrationBrief:
    """Everything a narrator is allowed to see. Already decided, already redacted.

    ``allowed_figures`` is the closed set of numeric strings the draft may contain, and
    ``allowed_source_ids`` the closed set of instrument ids it may cite. They are carried in the
    brief rather than inferred afterwards so the prompt and the validator agree by construction.
    """

    assessment_id: str
    tenant: str
    overall: str
    severity: str
    breach_count: int
    gap_count: int
    product_count: int
    signal_count: int
    theme_titles: tuple[str, ...] = ()
    allowed_figures: frozenset[str] = field(default_factory=frozenset)
    allowed_source_ids: frozenset[str] = field(default_factory=frozenset)


@runtime_checkable
class NarrationPort(Protocol):
    def narrate(self, brief: NarrationBrief) -> Narration | None:
        """Return a restatement of ``brief``, or ``None``. Never a number or verdict of its own."""
        ...
