"""Isolated permit mechanics; these claims never authorize a live route."""

from __future__ import annotations

import copy
import dataclasses
import threading

import pytest

from grafana_jsm_sandbox import forwarder_permit_model as model
from grafana_jsm_sandbox.forwarder_permit_model import (
    MAX_LIFETIME_PERMITS,
    MAX_OPEN_PERMITS,
    PermitBinding,
    PermitBook,
    PermitHandle,
    PermitModelError,
)


def binding(index: int = 0, **changes: object) -> PermitBinding:
    fields = {
        "permit_id": f"permit-{index}", "receiver_boot_id": "boot-1",
        "forwarder_generation": "generation-1", "run_id": "run-1",
        "attempt_id": "attempt-1", "operation_id": f"operation-{index}",
        "effect_intent_id": "intent-1", "grant_id": "grant-1",
        "flight_id": "flight-1", "service": "jira",
        "route_id": "jira.issue.create", "request_digest": "a" * 64,
        "target_digest": "b" * 64, "expires_us": 100,
    }
    fields.update(changes)
    return PermitBinding(**fields)


def book() -> PermitBook:
    return PermitBook(receiver_boot_id="boot-1", forwarder_generation="generation-1")


def l1(owner: PermitBook, handle: PermitHandle, claim: PermitBinding, **changes: object):
    arguments = {"receiver_boot_id": "boot-1", "forwarder_generation": "generation-1",
                 "now_us": 10}
    arguments.update(changes)
    return owner.attempt_l1(handle, claim, **arguments)


def l2(owner: PermitBook, handle: PermitHandle, claim: PermitBinding, **changes: object):
    arguments = {"receiver_boot_id": "boot-1", "forwarder_generation": "generation-1",
                 "now_us": 11}
    arguments.update(changes)
    return owner.attempt_l2(handle, claim, **arguments)


def fail(code: str, call) -> None:
    with pytest.raises(PermitModelError) as error:
        call()
    assert error.value.code == code
    assert str(error.value) == code


def test_exact_l1_consumes_once_and_l2_marks_one_write_transition():
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    assert l1(owner, handle, claim).code == "l1_pass"
    assert owner.phase(handle) == "consumed_l1"
    assert l2(owner, handle, claim).code == "l2_pass"
    assert owner.phase(handle) == "write_admitted"
    assert l2(owner, handle, claim).code == "l2_denied"
    assert owner.phase(handle) == "closed"
    assert l1(owner, handle, claim).code == "l1_denied"


def test_copy_and_forged_handle_cannot_use_or_close_owned_state():
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    for foreign in (copy.copy(handle), dataclasses.replace(handle), PermitHandle(handle.permit_id)):
        assert l1(owner, foreign, claim).reason == "unknown_handle"
        fail("permit_unknown", lambda foreign=foreign: owner.close(foreign))
    assert owner.phase(handle) == "offered"
    assert l1(owner, handle, claim).code == "l1_pass"


def test_staged_binding_is_a_private_snapshot_even_after_forced_caller_mutation():
    owner, claim = book(), binding()
    saved = dataclasses.replace(claim)
    handle = owner.stage(claim, now_us=0)
    object.__setattr__(claim, "target_digest", "c" * 64)
    assert l1(owner, handle, claim).reason == "binding_mismatch"
    assert owner.phase(handle) == "closed"
    other = owner.stage(binding(1), now_us=0)
    assert l1(owner, other, binding(1)).code == "l1_pass"
    assert saved.target_digest == "b" * 64


def test_expected_snapshot_is_fixed_before_lock_even_if_caller_changes_it(monkeypatch):
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    expected = dataclasses.replace(claim)
    original = model._snapshot_binding

    def mutate_after_snapshot(value, boot_id, generation):
        snapshot = original(value, boot_id, generation)
        if value is expected:
            object.__setattr__(expected, "target_digest", "c" * 64)
        return snapshot

    monkeypatch.setattr(model, "_snapshot_binding", mutate_after_snapshot)
    assert l1(owner, handle, expected).code == "l1_pass"
    assert expected.target_digest == "c" * 64


@pytest.mark.parametrize("change", [
    {"route_id": "jira.issue.update"}, {"grant_id": "grant-2"},
    {"operation_id": "operation-2"}, {"flight_id": "flight-2"},
    {"request_digest": "c" * 64}, {"target_digest": "d" * 64},
    {"effect_intent_id": "intent-2"}, {"attempt_id": "attempt-2"},
])
def test_l1_mismatch_closes_without_consumption(change):
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    assert l1(owner, handle, dataclasses.replace(claim, **change)).reason == "binding_mismatch"
    assert owner.phase(handle) == "closed"
    assert l1(owner, handle, claim).code == "l1_denied"


def test_l2_mismatch_is_post_l1_denial_and_cannot_restore_offer():
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    assert l1(owner, handle, claim).code == "l1_pass"
    result = l2(owner, handle, dataclasses.replace(claim, target_digest="c" * 64))
    assert (result.code, result.reason, result.phase) == (
        "l2_denied", "binding_mismatch", "closed",
    )
    assert l2(owner, handle, claim).code == "l2_denied"


@pytest.mark.parametrize("fence", ["l1", "l2"])
@pytest.mark.parametrize("changed", [
    {"now_us": True}, {"receiver_boot_id": "bad boot"},
    {"forwarder_generation": None},
])
def test_malformed_attempt_closes_known_handle(fence, changed):
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    if fence == "l2":
        assert l1(owner, handle, claim).code == "l1_pass"
    result = (l1 if fence == "l1" else l2)(owner, handle, claim, **changed)
    assert (result.code, result.reason, result.phase) == (
        fence + "_denied", "invalid_argument", "closed",
    )
    assert (l1 if fence == "l1" else l2)(owner, handle, claim).code == fence + "_denied"


@pytest.mark.parametrize("fence", ["l1", "l2"])
def test_context_change_or_expiry_closes_at_each_fence(fence):
    for changed in ({"receiver_boot_id": "boot-2"},
                    {"forwarder_generation": "generation-2"}, {"now_us": 100}):
        owner, claim = book(), binding()
        handle = owner.stage(claim, now_us=0)
        if fence == "l2":
            assert l1(owner, handle, claim).code == "l1_pass"
        result = (l1 if fence == "l1" else l2)(owner, handle, claim, **changed)
        assert result.code == fence + "_denied"
        assert result.phase == "closed"


def test_duplicate_l1_attempt_latches_the_known_handle_closed():
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    assert l1(owner, handle, claim).code == "l1_pass"
    assert l1(owner, handle, claim).reason == "phase"
    assert l2(owner, handle, claim).code == "l2_denied"


def test_close_frees_open_slot_but_keeps_duplicate_tombstones():
    owner = book()
    handles = [owner.stage(binding(index), now_us=0) for index in range(MAX_OPEN_PERMITS)]
    fail("permit_capacity", lambda: owner.stage(binding(MAX_OPEN_PERMITS), now_us=0))
    owner.close(handles[0])
    owner.close(handles[0])
    assert owner.phase(handles[0]) == "closed"
    fail("permit_duplicate", lambda: owner.stage(binding(0), now_us=0))
    fail("permit_duplicate", lambda: owner.stage(binding(99, operation_id="operation-0"), now_us=0))
    owner.stage(binding(MAX_OPEN_PERMITS), now_us=0)


def test_lifetime_tombstone_capacity_fails_closed_after_2048_stages():
    owner = book()
    for index in range(MAX_LIFETIME_PERMITS):
        handle = owner.stage(binding(index), now_us=0)
        owner.close(handle)
    fail("permit_capacity", lambda: owner.stage(binding(MAX_LIFETIME_PERMITS), now_us=0))
    fail("permit_duplicate", lambda: owner.stage(binding(0), now_us=0))


def test_new_book_rejects_old_handle_but_can_stage_same_claim_without_reconciliation():
    first, claim = book(), binding()
    old = first.stage(claim, now_us=0)
    second = book()
    assert l1(second, old, claim).reason == "unknown_handle"
    new = second.stage(claim, now_us=0)
    assert l1(second, new, claim).code == "l1_pass"
    # The model has no durable knowledge that the original operation existed.


def test_invalid_route_shape_and_time_fail_before_staging():
    owner = book()
    for claim in (
        binding(route_id="jira.unknown"), binding(service="grafana"),
        binding(permit_id="secret value"), binding(request_digest="Z" * 64),
    ):
        fail("permit_argument", lambda claim=claim: owner.stage(claim, now_us=0))
    fail("permit_expired", lambda: owner.stage(binding(), now_us=100))
    fail("permit_argument", lambda: owner.stage(binding(), now_us=True))


def test_caller_defined_equality_never_runs_inside_book_lock():
    class Trap:
        def __eq__(self, _other):
            raise AssertionError("caller equality ran")

    owner, claim = book(), binding()
    malformed = dataclasses.replace(claim, service=Trap())
    fail("permit_argument", lambda: owner.stage(malformed, now_us=0))
    handle = owner.stage(claim, now_us=0)
    result = l1(owner, handle, malformed)
    assert (result.code, result.reason, result.phase) == (
        "l1_denied", "invalid_argument", "closed",
    )


def test_concurrent_l1_calls_cannot_both_pass():
    owner, claim = book(), binding()
    handle = owner.stage(claim, now_us=0)
    barrier = threading.Barrier(3)
    results: list[str] = []

    def attempt() -> None:
        barrier.wait(timeout=3)
        results.append(l1(owner, handle, claim).code)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=3)
    for thread in threads:
        thread.join(timeout=3)
    assert sorted(results) == ["l1_denied", "l1_pass"]
    assert owner.phase(handle) == "closed"
