"""Pure venue-age arithmetic over unverified provider-time claims.

This module cannot authenticate a creation receipt, timestamp placement or
resource identity. Its result is not a Run/session/Fault or teardown permit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_NS = 2**63 - 1
MAX_EPSILON_NS = 5_000_000_000
_BOOT = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class VenueAgeError(ValueError):
    """A fixed rejection code with no receipt content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AgeAnchor:
    lower_ns: int
    upper_ns: int
    monotonic_anchor_ns: int
    boot_id: str
    resource_digest: str


@dataclass(frozen=True, slots=True)
class ClaimedProviderTime:
    provider_created_at_ns: int
    provider_now_ns: int
    epsilon_ns: int
    request_started_ns: int
    response_received_ns: int
    observer_boot_id: str
    resource_digest: str


def _valid_ns(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_NS


def _valid_boot(value: object) -> bool:
    return type(value) is str and _BOOT.fullmatch(value) is not None


def _valid_digest(value: object) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _checked_sum(*values: int) -> int:
    total = sum(values)
    if total > MAX_NS:
        raise VenueAgeError("age_overflow") from None
    return total


def derive_claimed_age(
    prior: AgeAnchor | None, fresh: ClaimedProviderTime,
) -> AgeAnchor:
    """Apply ticket 42's rollback-aware lower/upper formula to claims only.

    A future trusted adapter must verify provider origin and that its time was
    generated during the measured request before using these bounds in a gate.
    """
    if type(fresh) is not ClaimedProviderTime:
        raise VenueAgeError("age_argument") from None
    if not all(_valid_ns(value) for value in (
        fresh.provider_created_at_ns, fresh.provider_now_ns, fresh.epsilon_ns,
        fresh.request_started_ns, fresh.response_received_ns,
    )):
        raise VenueAgeError("age_time_invalid") from None
    if (not _valid_boot(fresh.observer_boot_id) or
            not _valid_digest(fresh.resource_digest)):
        raise VenueAgeError("age_identity_invalid") from None
    if (fresh.provider_now_ns < fresh.provider_created_at_ns or
            fresh.response_received_ns < fresh.request_started_ns or
            fresh.epsilon_ns > MAX_EPSILON_NS):
        raise VenueAgeError("age_time_invalid") from None

    if prior is not None:
        if type(prior) is not AgeAnchor or not all(_valid_ns(value) for value in (
            prior.lower_ns, prior.upper_ns, prior.monotonic_anchor_ns,
        )) or prior.lower_ns > prior.upper_ns:
            raise VenueAgeError("age_anchor_invalid") from None
        if not _valid_boot(prior.boot_id) or not _valid_digest(prior.resource_digest):
            raise VenueAgeError("age_anchor_invalid") from None
        if prior.resource_digest != fresh.resource_digest:
            raise VenueAgeError("age_identity_changed") from None

    delta = fresh.provider_now_ns - fresh.provider_created_at_ns
    rtt = fresh.response_received_ns - fresh.request_started_ns
    fresh_lower = max(0, delta - fresh.epsilon_ns)
    fresh_upper = _checked_sum(delta, fresh.epsilon_ns, rtt)
    if prior is None:
        prior_lower = prior_upper = 0
    elif prior.boot_id == fresh.observer_boot_id:
        if fresh.request_started_ns < prior.monotonic_anchor_ns:
            raise VenueAgeError("age_anchor_lost") from None
        elapsed = fresh.response_received_ns - prior.monotonic_anchor_ns
        prior_lower = _checked_sum(prior.lower_ns, elapsed)
        prior_upper = _checked_sum(prior.upper_ns, elapsed)
    else:
        prior_lower, prior_upper = prior.lower_ns, prior.upper_ns
    if fresh_upper < prior_upper:
        raise VenueAgeError("age_rollback") from None
    return AgeAnchor(
        lower_ns=max(prior_lower, fresh_lower),
        upper_ns=max(prior_upper, fresh_upper),
        monotonic_anchor_ns=fresh.response_received_ns,
        boot_id=fresh.observer_boot_id,
        resource_digest=fresh.resource_digest,
    )


__all__ = [
    "MAX_EPSILON_NS", "MAX_NS", "AgeAnchor", "ClaimedProviderTime",
    "VenueAgeError", "derive_claimed_age",
]
