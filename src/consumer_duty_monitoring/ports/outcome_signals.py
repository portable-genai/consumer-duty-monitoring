"""SignalSourcePort: the feed-agnostic intake of complaint / conversation / recommendation signals.

consumer-duty-monitoring's intake is deliberately feed-agnostic. It consumes complaint
categorisations and conduct flags from built complaints-review, conversation-QA scorecards from E3,
and next-best-action outcomes from next-best-action, and it will consume the F2 complaints-intake
feed when that is built in a later wave. Every source maps into ONE normalised
:class:`~..domain.models.OutcomeSignal` shape, so the engine reads one vocabulary rather than three
feed schemas, and registering a new feed (F2) is a new adapter behind this unchanged port, not an
engine change.

The offline family reads obviously-synthetic fixtures for all three built sources plus a declared
F2 fixture. The managed family reads BigQuery / the sibling services with a lazy import. The
on-premises family refuses, because the client's systems of record are the client's.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import OutcomeSignal


@runtime_checkable
class SignalSourcePort(Protocol):
    def load(self, tenant: str) -> tuple[OutcomeSignal, ...]:
        """Return every normalised outcome signal held for ``tenant`` (store-side tenant filter).

        The tenant comes from the VERIFIED principal, never from a client-supplied field, and the
        adapter filters on it so a load can never span tenants.
        """
        ...
