"""Local SignalSourcePort: SDK-free intake of obviously-synthetic outcome signals.

The offline stand-in for the managed intake (BigQuery plus the sibling services complaints-review,
E3 and next-best-action). It serves the shared synthetic dataset (``_seed.py``), already normalised
into the one ``OutcomeSignal`` shape every source maps to, and filters on tenant so a load can never
span tenants. The F2 intake source is present in the dataset as a DECLARED fixture, so the feed-
agnostic intake is exercised end to end before F2 itself is built.
"""

from __future__ import annotations

from ...config import Settings
from ...domain.models import OutcomeSignal
from ._seed import seed_signals


class LocalSignalSource:
    """Serve tenant-scoped normalised signals from the offline synthetic dataset."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self, tenant: str) -> tuple[OutcomeSignal, ...]:
        if not tenant:
            return ()
        return seed_signals(tenant)
