"""Domain errors that carry an HTTP-mappable meaning without importing a web framework.

The domain stays pure; these are plain exceptions the surfaces map to status codes.
"""

from __future__ import annotations


class TenantAccessDeniedError(PermissionError):
    """A verified principal asked for a record belonging to another tenant.

    Mapped to HTTP 403 by every surface. 403 rather than 404 is deliberate: the record EXISTS and
    this caller may not have it, and 404 would make the store probeable with an id generator.
    """


class OutcomePackError(ValueError):
    """The outcome-test pack is missing, malformed, or omits a required citation.

    The monitor must not start on a silently empty or partly-parsed pack: a pack with a family
    dropped would wave that outcome through as unmeasured-but-fine, so loading fails closed.
    """
