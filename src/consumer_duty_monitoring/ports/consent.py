"""ConsentLookupPort: read-only channel-preference context for the vulnerable-customer test.

The vulnerable-customer outcome test needs to know whether a vulnerable subject who was contacted
had actually granted a preference to be contacted on that channel. That is a legal position about
a person, owned by the catalog's consent and preference store, so this service reads it rather
than re-deriving it: the port wraps the shared ``consent-preference-kit`` client and its wire
types, and it is READ-ONLY. This service never records a send and never writes consent.

Fail closed, exactly as the kit does: a decision that cannot be obtained is a REFUSAL, not a
silent allow. A subject the store refuses (or a store that is unreachable) is treated as
"contacted against preference" if a contact was in fact made, because reading an unknown or
unreachable consent state as permission is the precise error a Consumer Duty monitor must not
make.

The offline family returns deterministic decisions from an obviously-synthetic preference
fixture; the managed family constructs the real S2S client with a lazy import; the on-premises
family refuses.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from consent_preference_kit import ConsentDecision, ConsentQuery


@runtime_checkable
class ConsentLookupPort(Protocol):
    def decide(self, query: ConsentQuery) -> ConsentDecision:
        """Return the store's cited consent decision for ``query`` (read-only, fail-closed)."""
        ...
