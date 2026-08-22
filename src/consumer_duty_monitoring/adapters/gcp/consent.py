"""Managed ConsentLookupPort: the real read-only ``consent-preference-kit`` S2S client.

Constructs the shared consent client against the catalog's consent and preference store and asks
it, read-only, whether a subject may be contacted. No cloud SDK is involved: the kit is pure
stdlib ``urllib`` with S2S headers wire-compatible with ``hex-service-kit``'s verifier, so this
module imports cleanly with no GCP SDK present. It is bound in the managed profile because it makes
a real network call to a sibling service.

Fail closed: an unconfigured ``consent_url`` REFUSES rather than defaulting to an allow. The kit
itself synthesises a DENIED decision when the store is unreachable, so a monitor never reads an
unavailable consent state as permission.
"""

from __future__ import annotations

from consent_preference_kit import ConsentClient, ConsentDecision, ConsentQuery

from ...config import Settings


class ConsentStoreLookup:
    """Ask the consent and preference store, read-only, through the shared S2S client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def decide(self, query: ConsentQuery) -> ConsentDecision:
        base_url = (self._settings.consent_url or "").strip()
        if not base_url:
            raise RuntimeError(
                "consent_url is not configured, so the vulnerable-customer test cannot resolve "
                "channel preference. Set CONSUMERDUTY_CONSENT_URL (config/settings.yaml "
                "consent_url) to the consent and preference store; refusing rather than reading "
                "an unknown preference as consent."
            )
        client = ConsentClient(base_url)
        return client.decide(query)
