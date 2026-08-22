"""On-prem ConsentLookupPort: fail-fast portability placeholder (the exit proof, P-12)."""

from __future__ import annotations

from consent_preference_kit import ConsentDecision, ConsentQuery

from ...config import Settings


class OnPremConsentLookup:
    """Satisfies ConsentLookupPort but refuses: the client's consent store is the client's."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def decide(self, query: ConsentQuery) -> ConsentDecision:
        raise NotImplementedError(
            "on-prem consent lookup is a portability placeholder: bind the client's own consent "
            "and preference store (see docs/onprem-migration.md). Fail-closed still applies: an "
            "unresolved preference is a refusal, never an allow."
        )
