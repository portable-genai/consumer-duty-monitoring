"""Local ConsentLookupPort: SDK-free, read-only channel-preference decisions from a fixture.

The offline stand-in for the managed consent client (the S2S ``consent-preference-kit`` client
against the catalog's consent and preference store). It returns real ``ConsentDecision`` objects
built from the shared synthetic preference fixture, using the KIT's own types so the wire shape is
identical to the managed path.

Fail closed exactly as the kit does: a subject the fixture does not list is UNKNOWN, and an unknown
consent state is a refusal, not an allow. Reading an unknown preference as permission to contact a
vulnerable customer is the precise error this whole test exists to catch.
"""

from __future__ import annotations

from consent_preference_kit import ConsentDecision, ConsentQuery

from ...config import Settings
from ._seed import CONSENT_FIXTURE


class LocalConsentLookup:
    """Answer consent queries from the offline synthetic preference fixture, fail-closed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def decide(self, query: ConsentQuery) -> ConsentDecision:
        outcome, reasons = CONSENT_FIXTURE.get(query.subject_id, ("denied", ("consent_unknown",)))
        return ConsentDecision(
            id=f"consent-local:{query.subject_id}:{query.channel}",
            tenant=query.tenant,
            subject_id=query.subject_id,
            purpose=query.purpose,
            channel=query.channel,
            outcome=outcome,
            reasons=reasons,
            market=query.market,
            vertical=query.vertical,
            as_of=query.as_of,
            explanation="offline synthetic preference fixture",
        )
