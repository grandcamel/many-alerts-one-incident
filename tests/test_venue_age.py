"""Arithmetic-only venue age bounds; no provider or cluster is contacted."""

from dataclasses import FrozenInstanceError, replace

import pytest

from grafana_jsm_sandbox.venue_age import (
    MAX_EPSILON_NS,
    MAX_NS,
    AgeAnchor,
    ClaimedProviderTime,
    VenueAgeError,
    derive_claimed_age,
)

SECOND = 1_000_000_000
MINUTE = 60 * SECOND
DIGEST = "a" * 64


def observation(age: int, **changes) -> ClaimedProviderTime:
    values = {
        "provider_created_at_ns": 1_000_000_000_000,
        "provider_now_ns": 1_000_000_000_000 + age,
        "epsilon_ns": 0,
        "request_started_ns": 1_000,
        "response_received_ns": 1_000,
        "observer_boot_id": "boot-1",
        "resource_digest": DIGEST,
    }
    values.update(changes)
    return ClaimedProviderTime(**values)


@pytest.mark.parametrize("age", [30 * MINUTE - 1, 30 * MINUTE,
                                   85 * MINUTE - 1, 85 * MINUTE,
                                   90 * MINUTE - 1, 90 * MINUTE])
def test_exact_policy_edges_are_represented_without_permit(age):
    result = derive_claimed_age(None, observation(age))
    assert result.lower_ns == age
    assert result.upper_ns == age
    assert not hasattr(result, "may_launch")
    assert not hasattr(result, "ready")


def test_epsilon_and_full_round_trip_widen_fresh_bounds():
    result = derive_claimed_age(None, observation(
        85 * MINUTE, epsilon_ns=5 * SECOND,
        request_started_ns=100, response_received_ns=100 + 2 * SECOND,
    ))
    assert result.lower_ns == 85 * MINUTE - 5 * SECOND
    assert result.upper_ns == 85 * MINUTE + 7 * SECOND


def test_same_boot_advances_prior_before_max_and_preserves_identity():
    prior = AgeAnchor(60 * SECOND, 62 * SECOND, 100, "boot-1", DIGEST)
    fresh = observation(65 * SECOND, request_started_ns=105,
                        response_received_ns=100 + 10 * SECOND,
                        provider_created_at_ns=1_000_000_000_000,
                        provider_now_ns=1_000_000_000_000 + 65 * SECOND)
    # Fresh lower is 65s; the advanced prior lower is 70s and must survive.
    result = derive_claimed_age(prior, fresh)
    assert result.lower_ns == 70 * SECOND
    assert result.upper_ns == 75 * SECOND - 5
    assert result.monotonic_anchor_ns == fresh.response_received_ns
    assert result.boot_id == "boot-1"


def test_new_boot_carries_prior_without_cross_boot_subtraction():
    prior = AgeAnchor(70 * SECOND, 72 * SECOND, 999_999, "old-boot", DIGEST)
    result = derive_claimed_age(prior, observation(
        72 * SECOND, observer_boot_id="new-boot", epsilon_ns=5 * SECOND,
        request_started_ns=0, response_received_ns=0,
    ))
    # Fresh lower is 67s; the persisted 70s lower survives the new boot.
    assert (result.lower_ns, result.upper_ns) == (70 * SECOND, 77 * SECOND)
    assert result.monotonic_anchor_ns == 0


def test_raw_fresh_upper_below_advanced_prior_is_rollback():
    prior = AgeAnchor(70 * SECOND, 72 * SECOND, 100, "boot-1", DIGEST)
    with pytest.raises(VenueAgeError, match="^age_rollback$"):
        derive_claimed_age(prior, observation(
            71 * SECOND, request_started_ns=100,
            response_received_ns=100 + 2 * SECOND,
        ))
    with pytest.raises(VenueAgeError, match="^age_rollback$"):
        derive_claimed_age(replace(prior, boot_id="old-boot"), observation(71 * SECOND))


@pytest.mark.parametrize(("change", "code"), [
    ({"provider_created_at_ns": True}, "age_time_invalid"),
    ({"provider_now_ns": 1}, "age_time_invalid"),
    ({"epsilon_ns": MAX_EPSILON_NS + 1}, "age_time_invalid"),
    ({"request_started_ns": 2_000}, "age_time_invalid"),
    ({"observer_boot_id": "bad boot"}, "age_identity_invalid"),
    ({"resource_digest": "A" * 64}, "age_identity_invalid"),
    ({"provider_created_at_ns": 0, "provider_now_ns": MAX_NS,
      "epsilon_ns": 1}, "age_overflow"),
])
def test_invalid_fresh_claims_fail_by_fixed_code(change, code):
    with pytest.raises(VenueAgeError) as error:
        derive_claimed_age(None, observation(0, **change))
    assert error.value.code == code
    assert str(error.value) == code


def test_prior_anchor_and_identity_are_checked():
    good = AgeAnchor(1, 2, 10, "boot-1", DIGEST)
    with pytest.raises(VenueAgeError, match="^age_anchor_invalid$"):
        derive_claimed_age(replace(good, lower_ns=3), observation(2))
    with pytest.raises(VenueAgeError, match="^age_identity_changed$"):
        derive_claimed_age(replace(good, resource_digest="b" * 64), observation(2))
    with pytest.raises(VenueAgeError, match="^age_anchor_lost$"):
        derive_claimed_age(replace(good, monotonic_anchor_ns=2_000), observation(2))


def test_overflow_and_immutable_result():
    with pytest.raises(VenueAgeError, match="^age_overflow$"):
        derive_claimed_age(None, observation(
            0, provider_created_at_ns=0, provider_now_ns=MAX_NS,
            epsilon_ns=1,
        ))
    result = derive_claimed_age(None, observation(1))
    with pytest.raises(FrozenInstanceError):
        result.upper_ns = 0
