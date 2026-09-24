"""Shell tests for the recovery journal's front-door extensions in
``recovery_journal`` (ticket 37, unit 17a; Tester T1, cases K1-K14).

Exercises Implementer A's front-door additions to ``journal_records``/
``journal_reducer``/``recovery_journal``: ``record_refusal``,
``admission_precheck``, resume at open (``ResumeRequest``/``ResumeReceipt``),
and verify-only ``inspect_recovery_journal`` (``Inspection``).

Real SQLite and real syncs throughout, mirroring ``test_recovery_journal.py``/
``test_recovery_journal_crash.py``/``test_recovery_journal_adversarial.py``:
private 0700 ``tmp_path`` directories, injected clocks and ID factories, no
fixed ports, no sleeps. ``SeqIds``, ``SeqClock``, ``SimulatedCrash`` and the
image-building helpers are reused by read-only import from those three files
rather than redefined.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import shutil
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from grafana_jsm_sandbox import journal_ingress as ji
from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import recovery_journal as rj
from grafana_jsm_sandbox.forwarder_json import canonical_json
from tests.test_recovery_journal import (
    CG1_KEY,
    PC,
    PF,
    SeqClock,
    SeqIds,
    make,
    new_dir,
    reopen,
    source,
)
from tests.test_recovery_journal_crash import (
    SimulatedCrash,
    _checkpoint,
    _crash_on_call,
    _e2_image,
    _n_admissions,
    anchor_path_of,
    commit_groups,
    db_path_of,
    flip_byte_in_group,
    open_held,
    open_ready,
    snapshot,
    trim_last_frame,
    wal_frames,
    wal_path_of,
)

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE "
    "(Python >= 3.12)",
)

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"
FRONT_DOOR_GOLDEN_PATH = DATA_DIR / "recovery_journal_v1_front_door_golden.jsonl"

# A group key distinct from the admission fixtures' CG1_KEY/CG2_KEY, used only
# for raw refusal-body JSON (never fed through the ``source()`` helper).
_REFUSAL_GROUP_KEY = '{}:{alertname="disk full", grafana_folder="ops"}'


@pytest.fixture(scope="module", autouse=True)
def _sync_budget():
    counts = {"n": 0}
    original = journal_store._full_sync

    def counting_full_sync(fd: int) -> None:
        counts["n"] += 1
        return original(fd)

    journal_store._full_sync = counting_full_sync
    start = time.perf_counter()
    yield counts
    elapsed = time.perf_counter() - start
    journal_store._full_sync = original
    print(f"\n[test_recovery_journal_front_door] real syncs={counts['n']} wall={elapsed:.2f}s")


# === Shared helpers (front-door specific) ====================================


def _json_invalid_summary(body: bytes = b"not json") -> dict:
    outcome = ji.sanitize_notification(body)
    assert outcome.refusal is not None
    return ji.refusal_to_json(outcome.refusal)


def _many_alerts_body(
    group_key: str, total: int, resolved: int, *, extra: dict | None = None,
) -> bytes:
    """A raw Grafana-shaped webhook body with ``total`` alerts, the first
    ``resolved`` of them Resolved and the rest Firing."""
    alerts = [
        {"fingerprint": f"alert-{i:03d}", "status": "resolved" if i < resolved else "firing"}
        for i in range(total)
    ]
    payload = {"groupKey": group_key, "alerts": alerts}
    if extra:
        payload.update(extra)
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _many_alerts_summary(total: int, resolved: int, *, extra: dict | None = None) -> dict:
    body = _many_alerts_body(_REFUSAL_GROUP_KEY, total, resolved, extra=extra)
    outcome = ji.sanitize_notification(body)
    assert outcome.refusal is not None
    return ji.refusal_to_json(outcome.refusal)


def _oversize_summary(declared_length: int = 300_000) -> dict:
    return ji.refusal_to_json(ji.oversize_refusal(declared_length))


def _resume_token(directory) -> str:
    inspection = rj.inspect_recovery_journal(directory)
    return inspection.report["resume"]["token"]


def _file_snapshot(directory: pathlib.Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir()) if path.is_file()}


def _crash_after_nth_call(monkeypatch, target, name: str, n: int, directory, image):
    """Patch ``target.name`` so its n-th call runs for real (durable) and
    THEN snapshots and crashes -- unlike ``_crash_on_call``, which skips the
    real call entirely. Every other call runs normally."""
    real_fn = getattr(target, name)
    state = {"n": 0}

    def wrapper(*args, **kwargs):
        state["n"] += 1
        result = real_fn(*args, **kwargs)
        if state["n"] == n:
            snapshot(directory, image)
            raise SimulatedCrash
        return result

    monkeypatch.setattr(target, name, wrapper)
    return state


# === K1: record_refusal outcomes, latching and snapshot() parity ============


def test_k1_record_refusal_outcomes_and_latching(tmp_path):
    _directory, _clock, _ids, journal = make(tmp_path, "k1")
    try:
        summary = _json_invalid_summary()
        assert journal.record_refusal(summary) == "recorded"
        # A byte-identical re-render (same code, same no-group key): coalesced.
        assert journal.record_refusal(_json_invalid_summary(b"still not json")) == "coalesced"

        # A malformed summary: refusal_invalid, latches nothing.
        with pytest.raises(rj.JournalError) as info:
            journal.record_refusal({"code": "ingress_json_invalid"})
        assert info.value.args == ("refusal_invalid",)
        assert journal.state == "ready"

        snap = journal.snapshot()
        assert set(snap.keys()) == {
            "state", "hold", "journal_uuid", "generation", "boot_id", "head", "anchor",
            "wal_found", "dispatch_holds", "counts", "bytes", "bounds", "refusals_this_boot",
            "verified_state_digest", "pending_digest", "state_digest",
        }
        assert len(snap.keys()) == 16
        # D11: refusals_this_boot stays capacity-only even with refusals present.
        assert set(snap["refusals_this_boot"]) <= set(jr.CAPACITY_CODES)

        # Per-boot outcome counters, keyed by code: one recorded, one coalesced;
        # the refusal_invalid attempt never reached a code to bucket under.
        status = journal.front_door_status()
        assert status["refusals"]["this_boot"] == {
            "ingress_json_invalid": {"recorded": 1, "coalesced": 1},
        }
        assert status["refusals"]["recorded"] == 1
        assert status["refusals"]["limit"] == jrd.MAX_REFUSAL_RECORDS
        assert status["refusals"]["reserve"] == jrd.REFUSAL_RESOLVED_RESERVE
        assert status["resume"] == {"this_boot": "not_requested"}
    finally:
        journal.close()

    # A clock fault latches journal_clock_invalid.
    _directory2, _clock2, _ids2, journal2 = make(tmp_path, "k1-clock")
    journal2._wall_clock = lambda: (_ for _ in ()).throw(RuntimeError("no canary"))
    with pytest.raises(rj.JournalError) as info:
        journal2.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_clock_invalid",)
    assert journal2.hold == ("journal_clock_invalid", "process")
    journal2.close()

    # Held: journal_held, without touching the summary at all.
    directory3, _receipts = _n_admissions(tmp_path, "k1-held", 2)
    _tear_last_commit(directory3)
    held = open_held(directory3)
    try:
        with pytest.raises(rj.JournalError) as info:
            held.record_refusal(_json_invalid_summary())
        assert info.value.args == ("journal_held",)
    finally:
        held.close()


def test_k1_admission_precheck_is_advisory_and_exact_in_one_direction(tmp_path):
    bounds = jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    _directory, _clock, _ids, journal = make(tmp_path, "k1-precheck", bounds=bounds)
    assert journal.admission_precheck() is None
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    # At the bound, but not yet refused: it deliberately does not fire early.
    assert journal.admission_precheck() is None
    with pytest.raises(rj.JournalError) as info:
        journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    assert info.value.args == ("capacity_admissions",)
    # The durable capacity_admissions hold now exists: every later admit would
    # refuse with the same code, so the precheck fires.
    assert journal.admission_precheck() == "capacity_admissions"
    # Latched after the hold (a clock fault): no longer ready, so no answer.
    journal._wall_clock = lambda: (_ for _ in ()).throw(RuntimeError("clock fault"))
    with pytest.raises(rj.JournalError) as info:
        journal.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_clock_invalid",)
    assert "capacity_admissions" in journal._projection.dispatch_holds  # still there, unseen
    assert journal.admission_precheck() is None
    journal.close()
    assert journal.admission_precheck() is None  # closed: no lock, no answer either way


def test_k1_admission_precheck_never_fires_for_pending_bytes_or_a_held_open(tmp_path):
    bounds = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    _directory, _clock, _ids, journal = make(tmp_path, "k1-precheck-pending", bounds=bounds)
    try:
        firing = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
        journal.admit(firing)
        with pytest.raises(rj.JournalError) as info:
            journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert info.value.args == ("capacity_pending",)
        assert journal.dispatch_holds == ("capacity_pending",)
        # A repeat can still be admitted, so the precheck must not refuse it.
        assert journal.admission_precheck() is None
        assert journal.admit(firing).result == "suppressed"
    finally:
        journal.close()

    bounds = dataclasses.replace(bounds, max_pending_fingerprints=1_024, ordinary_bytes=1)
    _directory, _clock, _ids, journal = make(tmp_path, "k1-precheck-bytes", bounds=bounds)
    try:
        with pytest.raises(rj.JournalError) as info:
            journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.args == ("capacity_bytes",)
        assert journal.dispatch_holds == ("capacity_bytes",)
        assert journal.admission_precheck() is None
    finally:
        journal.close()

    directory, _receipts = _n_admissions(tmp_path, "k1-precheck-held", 2)
    _tear_last_commit(directory)
    held = open_held(directory)
    try:
        assert held.admission_precheck() is None
    finally:
        held.close()


def test_k1_record_refusal_refuses_bools_posing_as_ints(tmp_path):
    _directory, _clock, _ids, journal = make(tmp_path, "k1-bools")
    try:
        summary = _many_alerts_summary(33, 1)
        assert summary["members_omitted"] == 1
        assert journal.record_refusal(summary) == "recorded"
        # Equal by value to what refusal_to_json emits, but a JSON boolean
        # would give each its own key and spend the budget twice.
        forgeries = (
            dict(summary, members_omitted=True),
            dict(_json_invalid_summary(), members_omitted=False),
        )
        for forged in forgeries:
            with pytest.raises(rj.JournalError) as info:
                journal.record_refusal(forged)
            assert info.value.args == ("refusal_invalid",)
        assert journal.state == "ready"
        assert journal.front_door_status()["refusals"]["recorded"] == 1
    finally:
        journal.close()


def test_k1_record_refusal_no_room_writes_nothing_and_is_counted(tmp_path):
    bounds = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=1,
        total_bytes=128 * 2**20,
    )
    directory, _clock, _ids, journal = make(tmp_path, "k1-no-room", bounds=bounds)
    try:
        head = journal.snapshot()["head"]
        before = _file_snapshot(directory)
        assert journal.record_refusal(_json_invalid_summary()) == "no_room"
        assert journal.record_refusal(_many_alerts_summary(33, 1)) == "no_room"
        assert journal.state == "ready"
        assert journal.snapshot()["head"] == head
        assert _file_snapshot(directory) == before
        refusals = journal.front_door_status()["refusals"]
        assert refusals["recorded"] == 0
        assert refusals["this_boot"] == {
            "ingress_json_invalid": {"no_room": 1}, "ingress_too_many_alerts": {"no_room": 1},
        }
    finally:
        journal.close()


def _group_summary(index: int, resolved: int) -> dict:
    group_key = f'{{}}:{{alertname="k1-limit-{index}", grafana_folder="ops"}}'
    outcome = ji.sanitize_notification(_many_alerts_body(group_key, 33, resolved))
    return ji.refusal_to_json(outcome.refusal)


def test_k1_record_refusal_limit_writes_nothing_and_is_counted(tmp_path, monkeypatch):
    # 256 real commits would cost 256 real syncs: lower the reducer's limit to
    # 2 records, 1 of them reserved for a summary carrying a Resolved member.
    monkeypatch.setattr(jrd, "MAX_REFUSAL_RECORDS", 2)
    monkeypatch.setattr(jrd, "REFUSAL_RESOLVED_RESERVE", 1)
    directory, _clock, _ids, journal = make(tmp_path, "k1-limit")
    try:
        assert journal.record_refusal(_group_summary(0, 0)) == "recorded"
        before = _file_snapshot(directory)
        assert journal.record_refusal(_group_summary(1, 0)) == "limit"  # past the unreserved 1
        assert _file_snapshot(directory) == before
        assert journal.record_refusal(_group_summary(2, 1)) == "recorded"  # the reserve
        before = _file_snapshot(directory)
        assert journal.record_refusal(_group_summary(3, 1)) == "limit"  # past the limit of 2
        assert journal.record_refusal(_group_summary(0, 0)) == "coalesced"  # known, at the limit
        assert _file_snapshot(directory) == before
        refusals = journal.front_door_status()["refusals"]
        assert refusals["recorded"] == 2
        assert refusals["this_boot"] == {
            "ingress_too_many_alerts": {"recorded": 2, "limit": 2, "coalesced": 1},
        }
    finally:
        journal.close()


def test_k1_record_refusal_id_fault_latches_journal_divergence(tmp_path):
    _directory, _clock, _ids, journal = make(tmp_path, "k1-ids")
    journal._id_factory = lambda: "not an id"
    try:
        with pytest.raises(rj.JournalError) as info:
            journal.record_refusal(_json_invalid_summary())
        assert info.value.args == ("journal_divergence",)
        assert journal.hold == ("journal_divergence", "process")
    finally:
        journal.close()


def test_k1_record_refusal_mono_regression_latches_journal_clock_invalid(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k1-mono")
    try:
        before = _file_snapshot(directory)
        journal._mono_clock = lambda: 1_000  # below the genesis stamp: the clock went back
        with pytest.raises(rj.JournalError) as info:
            journal.record_refusal(_json_invalid_summary())
        assert info.value.args == ("journal_clock_invalid",)
        assert journal.hold == ("journal_clock_invalid", "process")
        assert _file_snapshot(directory) == before
    finally:
        journal.close()


def _raise_injected_fault(*_args):
    raise OSError("injected fault")


@pytest.mark.parametrize("seam,lag,recorded", [
    ("_write_slot", 1, 1),  # the row committed, its anchor did not
    ("_commit_sql", 0, 0),  # nothing durable
])
def test_k1_record_refusal_write_fault_latches_and_never_retries(
    tmp_path, monkeypatch, seam, lag, recorded,
):
    directory, _clock, _ids, journal = make(tmp_path, f"k1-fault{seam}")
    monkeypatch.setattr(journal_store.JournalStore, seam, _raise_injected_fault)
    try:
        with pytest.raises(rj.JournalError) as info:
            journal.record_refusal(_json_invalid_summary())
        assert info.value.args == ("journal_write_failed",)
        assert journal.hold == ("journal_write_failed", "process")
        with pytest.raises(rj.JournalError) as info:
            journal.record_refusal(_many_alerts_summary(33, 1))
        assert info.value.args == ("journal_held",)
        with pytest.raises(rj.JournalError) as info:
            journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.args == ("journal_held",)
    finally:
        journal.close()
    monkeypatch.undo()
    report = rj.inspect_recovery_journal(directory).report
    assert (report["anchor"]["lag"], report["refusals"]["recorded"]) == (lag, recorded)


def test_k1_record_refusal_refuses_a_non_pair_member_and_an_out_of_set_code(tmp_path):
    _directory, _clock, _ids, journal = make(tmp_path, "k1-forged")
    try:
        summary = _many_alerts_summary(33, 1)
        fingerprint, status = summary["members"][0]
        rest = summary["members"][1:]
        forgeries = (
            dict(summary, members=[[fingerprint, status, "junk"], *rest]),
            dict(summary, members=[[fingerprint], *rest]),
            # Member-less with one group: only the closed code set refuses it.
            dict(_json_invalid_summary(), code="ingress_future_code", source_group="a" * 64),
        )
        for forged in forgeries:
            with pytest.raises(rj.JournalError) as info:
                journal.record_refusal(forged)
            assert info.value.args == ("refusal_invalid",)
        assert journal.state == "ready"
        assert journal.front_door_status()["refusals"]["recorded"] == 0
        assert journal.record_refusal(summary) == "recorded"  # the unforged control
    finally:
        journal.close()


# === Gap-agent additions (unit 17a mutation survivors) ======================


def test_j01_record_refusal_checks_closed_before_held(tmp_path):
    # J01: record_refusal's check order mirrors admit's (closed, then held).
    # On a held handle that is then closed, the closed check must still win.
    directory, _receipts = _n_admissions(tmp_path, "j01-held-closed", 2)
    _tear_last_commit(directory)
    held = open_held(directory)
    held.close()
    with pytest.raises(rj.JournalError) as info:
        held.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    assert info.value.args == ("journal_closed",)
    with pytest.raises(rj.JournalError) as info:
        held.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_closed",)

    # Repeat on a ready handle latched by a clock fault, then closed.
    _directory2, _clock2, _ids2, journal2 = make(tmp_path, "j01-latched-closed")
    journal2._wall_clock = lambda: (_ for _ in ()).throw(RuntimeError("clock fault"))
    with pytest.raises(rj.JournalError) as info:
        journal2.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_clock_invalid",)
    assert journal2.hold == ("journal_clock_invalid", "process")
    journal2.close()
    with pytest.raises(rj.JournalError) as info:
        journal2.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_closed",)


def test_j03_record_refusal_normalizes_the_summary_before_reading_the_clock(tmp_path):
    # J03: a malformed summary is refusal_invalid and latches nothing, even
    # when the clock would fault -- normalization must run first.
    _directory, _clock, _ids, journal = make(tmp_path, "j03-wall")
    journal._wall_clock = lambda: (_ for _ in ()).throw(RuntimeError("no canary"))
    with pytest.raises(rj.JournalError) as info:
        journal.record_refusal({"code": "ingress_json_invalid"})
    assert info.value.args == ("refusal_invalid",)
    assert journal.hold is None
    assert journal.state == "ready"
    # A well-formed summary still hits the (still-failing) clock.
    with pytest.raises(rj.JournalError) as info:
        journal.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_clock_invalid",)
    assert journal.hold == ("journal_clock_invalid", "process")
    journal.close()

    _directory2, _clock2, _ids2, journal2 = make(tmp_path, "j03-mono")
    journal2._mono_clock = lambda: 1_000  # below the genesis stamp: a clock fault
    with pytest.raises(rj.JournalError) as info:
        journal2.record_refusal({"code": "ingress_json_invalid"})
    assert info.value.args == ("refusal_invalid",)
    assert journal2.hold is None
    assert journal2.state == "ready"
    with pytest.raises(rj.JournalError) as info:
        journal2.record_refusal(_json_invalid_summary())
    assert info.value.args == ("journal_clock_invalid",)
    journal2.close()


def test_j05_record_refusal_bumps_recorded_only_after_a_successful_commit(tmp_path, monkeypatch):
    # J05: the per-boot "recorded" counter must reflect only a committed
    # refusal, never one a write fault refused.
    directory, _clock, _ids, journal = make(tmp_path, "j05-write-fault")
    monkeypatch.setattr(journal_store.JournalStore, "_commit_sql", _raise_injected_fault)
    try:
        with pytest.raises(rj.JournalError) as info:
            journal.record_refusal(_json_invalid_summary())
        assert info.value.args == ("journal_write_failed",)
        assert journal.hold == ("journal_write_failed", "process")
        assert journal.front_door_status()["refusals"]["this_boot"] == {}
    finally:
        journal.close()
    monkeypatch.undo()
    report = rj.inspect_recovery_journal(directory).report
    assert report["refusals"]["recorded"] == 0


def test_j08_front_door_status_recorded_is_null_while_held(tmp_path):
    # J08: D9's null rule -- front_door_status must read the visible
    # (None-while-held) projection, not the handle's raw projection.
    _directory, _clock, _ids, journal = make(tmp_path, "j08-null-while-held")
    assert journal.record_refusal(_json_invalid_summary()) == "recorded"
    assert journal.front_door_status()["refusals"]["recorded"] == 1
    journal._wall_clock = lambda: (_ for _ in ()).throw(RuntimeError("clock fault"))
    with pytest.raises(rj.JournalError) as info:
        journal.record_refusal(_many_alerts_summary(33, 1))
    assert info.value.args == ("journal_clock_invalid",)
    assert journal.state == "held"
    status = journal.front_door_status()
    assert status["refusals"]["recorded"] is None
    # The per-boot counters are unaffected by the null rule: they still show
    # the refusal recorded before the latch.
    assert status["refusals"]["this_boot"]["ingress_json_invalid"] == {"recorded": 1}
    journal.close()


def test_j11_admission_precheck_checks_closed_even_when_never_held(tmp_path):
    # J11: the precheck must return None once closed, even when the handle
    # was never latched (a clean close, only a projection-level capacity
    # hold). The existing precheck test closes a handle already latched by a
    # clock fault, which masks this guard.
    bounds = jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    _directory, _clock, _ids, journal = make(tmp_path, "j11-precheck-closed", bounds=bounds)
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    with pytest.raises(rj.JournalError) as info:
        journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    assert info.value.args == ("capacity_admissions",)
    assert journal.admission_precheck() == "capacity_admissions"
    journal.close()  # a clean close: never latched
    assert journal.hold is None
    assert journal.state == "closed"
    assert journal.admission_precheck() is None


# === K2: resume at open ======================================================


def test_k2_resume_at_open_clears_the_hold(tmp_path):
    directory, clock, ids, journal = make(tmp_path, "k2")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()

    reopened = reopen(directory, clock, ids)  # boot 2: restart_recovery, held
    assert "restart_recovery" in reopened.dispatch_holds
    reopened.close()

    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="k2-operator", reason="restart-inspected")
    resumed = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    try:
        assert resumed.state == "ready"
        assert "restart_recovery" not in resumed.dispatch_holds
        receipt = resumed.resumed_this_boot
        assert isinstance(receipt, rj.ResumeReceipt)
        assert receipt.operator == "k2-operator"
        assert receipt.reason == "restart-inspected"
        assert receipt.hold == "restart_recovery"

        # Read through the handle's own already-open store (a second
        # JournalStore.open() here would contend for the flock this handle
        # still holds); checked before the next admit appends more rows.
        rows = list(resumed._store.rows())
        assert [r.event_type for r in rows[-2:]] == ["restart_recovery", "operator_action"]

        # The receipt matches what the committed operator_action record itself
        # carries.
        operator_record = rows[-1]
        assert receipt.commit_seq == operator_record.position.commit_seq
        assert receipt.since_commit_seq == operator_record.data["since_commit_seq"]
        assert receipt.pending_digest == operator_record.data["pending_digest"]
        inspected = operator_record.data["inspected"]
        assert receipt.inspected.commit_seq == inspected["commit_seq"]
        assert receipt.inspected.event_seq == inspected["event_seq"]
        assert receipt.inspected.record_digest == inspected["record_digest"]

        assert resumed.front_door_status()["resume"] == {"this_boot": "resumed"}
        next_admission = resumed.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert next_admission.decision == "admitted"
    finally:
        resumed.close()


def test_k2_resume_clears_only_restart_recovery_and_keeps_a_capacity_hold(tmp_path):
    bounds = jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    directory, clock, ids, journal = make(tmp_path, "k2-capacity", bounds=bounds)
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    with pytest.raises(rj.JournalError) as info:
        journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    assert info.value.args == ("capacity_admissions",)
    journal.close()

    resume = rj.ResumeRequest(token=_resume_token(directory), operator="k2-operator")
    resumed = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    try:
        assert resumed.resumed_this_boot is not None
        assert resumed.dispatch_holds == ("capacity_admissions",)
        assert resumed.admission_precheck() == "capacity_admissions"
    finally:
        resumed.close()


def test_k2_resume_at_open_on_a_lag_1_image_takes_the_inspected_token(tmp_path, monkeypatch):
    image, _a, _prior = _e2_image(tmp_path, monkeypatch, "k2-lag1")
    report = rj.inspect_recovery_journal(image).report
    assert report["anchor"]["lag"] == 1
    token = report["resume"]["token"]

    resumed = rj.open_recovery_journal(image, resume=rj.ResumeRequest(token=token, operator="op"))
    try:
        assert resumed.state == "ready"
        receipt = resumed.resumed_this_boot
        assert receipt is not None and receipt.inspected.record_digest == token
        assert "restart_recovery" not in resumed.dispatch_holds
        rows = list(resumed._store.rows())
        assert [r.event_type for r in rows[-2:]] == ["restart_recovery", "operator_action"]
        assert rows[-2].data["anchor_lag"] == 1
    finally:
        resumed.close()


# === K3: a stale or malformed resume writes nothing (WAL-present image) =====


def test_k3_stale_token_raises_resume_stale_and_writes_nothing(tmp_path):
    directory, clock, ids, journal = make(tmp_path, "k3-stale")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    before = _file_snapshot(directory)

    stale = rj.ResumeRequest(token="0" * 64, operator="op", reason="restart-inspected")
    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=stale,
        )
    assert info.value.args == ("resume_stale",)
    assert _file_snapshot(directory) == before


def test_j18_stale_token_is_refused_before_finish_open_is_called(tmp_path, monkeypatch):
    # J18 (V10 check order): the stale-token check must run before
    # finish_open, so a refused resume calls it zero times.
    directory, clock, ids, journal = make(tmp_path, "j18-finish-open-spy")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    before = _file_snapshot(directory)

    calls = {"n": 0}
    real_finish_open = journal_store.JournalStore.finish_open

    def spy(self):
        calls["n"] += 1
        return real_finish_open(self)

    monkeypatch.setattr(journal_store.JournalStore, "finish_open", spy)
    stale = rj.ResumeRequest(token="0" * 64, operator="op", reason="restart-inspected")
    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=stale,
        )
    assert info.value.args == ("resume_stale",)
    assert calls["n"] == 0
    assert _file_snapshot(directory) == before


class _ResumeRequestSubclass(rj.ResumeRequest):
    """Not exactly a ``ResumeRequest``, though every field is well formed."""


class _PosingStr(str):
    """A str subclass posing as an exact str, and equal to anything."""

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = str.__hash__


_MALFORMED_RESUME_REQUESTS = (
    rj.ResumeRequest(token="not-hex" * 8, operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 63, operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 65, operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 128, operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token=_PosingStr("a" * 64), operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 64, operator=_PosingStr("op"), reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 64, operator="op", reason=_PosingStr("restart-inspected")),
    rj.ResumeRequest(token="A" * 64, operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token=7, operator="op", reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 64, operator="has space", reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 64, operator="a" * 129, reason="restart-inspected"),
    rj.ResumeRequest(token="a" * 64, operator="op", reason="has space"),
    {"token": "a" * 64, "operator": "op", "reason": "restart-inspected"},
    SimpleNamespace(token="a" * 64, operator="op", reason="restart-inspected"),
    _ResumeRequestSubclass(token="a" * 64, operator="op"),
)


def test_k3_malformed_resume_request_raises_resume_invalid_before_the_store_opens(
    tmp_path, monkeypatch,
):
    directory, clock, ids, journal = make(tmp_path, "k3-malformed")
    journal.close()
    # Opening the store would create an absent lock, so its absence shows the
    # store was never opened; the patched open makes the same point directly.
    lock_path = directory / journal_store.LOCK_FILENAME
    lock_path.unlink()
    before = _file_snapshot(directory)

    def store_open_forbidden(cls, directory):
        raise AssertionError("the store was opened for a malformed resume request")

    monkeypatch.setattr(journal_store.JournalStore, "open", classmethod(store_open_forbidden))
    for bad in _MALFORMED_RESUME_REQUESTS:
        with pytest.raises(rj.JournalError) as info:
            rj.open_recovery_journal(
                directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=bad,
            )
        assert info.value.args == ("resume_invalid",)
        assert info.value.__context__ is None
        assert _file_snapshot(directory) == before
        assert not lock_path.exists()


def test_k3_malformed_resume_request_on_a_wal_absent_image_creates_no_wal(tmp_path):
    directory, clock, ids, journal = make(tmp_path, "k3-malformed-no-wal")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    _checkpoint(directory)
    assert not wal_path_of(directory).exists()
    before = _file_snapshot(directory)

    bad = rj.ResumeRequest(token="A" * 64, operator="op", reason="restart-inspected")
    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=bad,
        )
    assert info.value.args == ("resume_invalid",)
    assert _file_snapshot(directory) == before
    assert not wal_path_of(directory).exists()


def test_k3_stale_token_on_a_lag_1_image_writes_nothing(tmp_path, monkeypatch):
    # The stale check runs before finish_open, so before the re-anchor too.
    image, _a, _prior = _e2_image(tmp_path, monkeypatch, "k3-lag1")
    assert rj.inspect_recovery_journal(image).report["anchor"]["lag"] == 1
    before = _file_snapshot(image)

    stale = rj.ResumeRequest(token="0" * 64, operator="op", reason="restart-inspected")
    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(image, resume=stale)
    assert info.value.args == ("resume_stale",)
    assert _file_snapshot(image) == before


# === K3b: a stale token on a WAL-absent image creates only an empty WAL =====


def test_k3b_stale_token_on_wal_absent_image_creates_only_an_empty_wal(tmp_path):
    directory, clock, ids, journal = make(tmp_path, "k3b")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    # A raw-connection TRUNCATE checkpoint, closing as the sole connection,
    # already leaves the WAL absent (SQLite's own close-time cleanup): no
    # separate unlink is needed, or possible.
    _checkpoint(directory)
    assert not wal_path_of(directory).exists()
    db_before = db_path_of(directory).read_bytes()
    anchor_before = anchor_path_of(directory).read_bytes()

    stale = rj.ResumeRequest(token="0" * 64, operator="op", reason="restart-inspected")
    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=stale,
        )
    assert info.value.args == ("resume_stale",)
    assert db_path_of(directory).read_bytes() == db_before
    assert anchor_path_of(directory).read_bytes() == anchor_before
    # The connect step creates an empty WAL before the token can be checked.
    assert wal_path_of(directory).exists()
    assert wal_path_of(directory).stat().st_size == 0

    reopened = open_ready(directory)
    try:
        wal_found = reopened.snapshot()["wal_found"]
        assert wal_found == {"size": 0, "digest": wal_found["digest"]}
    finally:
        reopened.close()


# === K4: resume against a held image is silently not applied ================


def test_k4_resume_against_a_held_image_is_not_applied(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "k4", 2)
    wal_bytes = wal_path_of(directory).read_bytes()
    wal_path_of(directory).write_bytes(trim_last_frame(wal_bytes, wal_frames(wal_bytes)))

    resume = rj.ResumeRequest(token="0" * 64, operator="op", reason="restart-inspected")
    journal = rj.open_recovery_journal(directory, resume=resume)
    try:
        assert journal.state == "held"
        assert journal.hold == ("journal_truncated", "recovery")
        assert journal.resumed_this_boot is None
        assert journal.front_door_status()["resume"] == {"this_boot": "not_applied"}
        # The recovery verdict is persisted as any held open would persist it,
        # independent of the (never-applied) resume request.
        assert journal.snapshot()["hold"]["persisted"] is True
    finally:
        journal.close()

    store = journal_store.JournalStore.open(directory)
    try:
        event_types = {r.event_type for r in store.rows()}
    finally:
        store.close()
    assert "operator_action" not in event_types


# === K5: a clock fault during the restart latches; no resume is attempted ===


def test_k5_clock_fault_during_restart_skips_resume(tmp_path):
    directory, clock, ids, journal = make(tmp_path, "k5")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="op", reason="restart-inspected")

    def failing_wall() -> int:
        raise RuntimeError("clock fault")

    reopened = rj.open_recovery_journal(
        directory, wall_clock=failing_wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    try:
        assert reopened.hold == ("journal_clock_invalid", "process")
        assert reopened.resumed_this_boot is None
    finally:
        reopened.close()


def test_j26_resume_at_open_is_never_called_once_the_restart_has_latched(tmp_path, monkeypatch):
    # J26: _resume_at_open must only run when the restart committed cleanly
    # (journal._hold_detail is None). A spy on the method itself, rather than
    # on its durable effects, is what the plan's probe measures: the mutant
    # calls it (and mints an id, reads the clock) even though it then returns
    # at once via _resume_at_open's own dispatch-hold guard.
    directory, clock, ids, journal = make(tmp_path, "j26")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="op", reason="restart-inspected")

    def failing_wall() -> int:
        raise RuntimeError("clock fault")

    calls = {"n": 0}
    real_resume_at_open = rj.RecoveryJournal._resume_at_open

    def spy(self, resume_request):
        calls["n"] += 1
        return real_resume_at_open(self, resume_request)

    monkeypatch.setattr(rj.RecoveryJournal, "_resume_at_open", spy)
    reopened = rj.open_recovery_journal(
        directory, wall_clock=failing_wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    try:
        assert reopened.hold == ("journal_clock_invalid", "process")
        assert reopened.resumed_this_boot is None
        assert calls["n"] == 0
    finally:
        reopened.close()


# --- K5: faults at the resume step itself latch exactly as for restart -------


class _FailingOnCall:
    """Passes calls through to ``fn``, except that call number ``n`` raises."""

    def __init__(self, fn, n: int) -> None:
        self._fn, self._n, self.calls = fn, n, 0

    def __call__(self):
        self.calls += 1
        if self.calls == self._n:
            raise RuntimeError("injected fault")
        return self._fn()


def _resume_ready_image(tmp_path, name: str, bounds=None):
    directory, clock, ids, journal = make(tmp_path, name, bounds=bounds)
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    return directory, clock, ids, _resume_token(directory)


def _event_types(directory) -> list[str]:
    store = journal_store.JournalStore.open(directory)
    try:
        return [record.event_type for record in store.rows()]
    finally:
        store.close()


def _assert_restarted_but_not_resumed(journal, directory, hold) -> None:
    try:
        assert journal.hold == hold
        assert journal.resumed_this_boot is None
        assert journal.front_door_status()["resume"] == {"this_boot": "not_applied"}
    finally:
        journal.close()
    assert _event_types(directory)[-1] == "restart_recovery"


def test_k5_an_id_fault_at_the_resume_step_latches_journal_divergence(tmp_path):
    directory, clock, ids, token = _resume_ready_image(tmp_path, "k5-resume-id")
    # Open mints the candidate boot ID, then the restart's boot and event IDs;
    # the fourth call is the resume's own event ID.
    faulty_ids = _FailingOnCall(ids, 4)
    journal = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=faulty_ids,
        resume=rj.ResumeRequest(token=token, operator="op"),
    )
    assert faulty_ids.calls == 4
    _assert_restarted_but_not_resumed(journal, directory, ("journal_divergence", "process"))


def test_k5_a_clock_fault_at_the_resume_step_latches_journal_clock_invalid(tmp_path):
    directory, clock, ids, token = _resume_ready_image(tmp_path, "k5-resume-clock")
    faulty_wall = _FailingOnCall(clock.wall, 2)  # the restart reads it first
    journal = rj.open_recovery_journal(
        directory, wall_clock=faulty_wall, mono_clock=clock.mono, id_factory=ids,
        resume=rj.ResumeRequest(token=token, operator="op"),
    )
    assert faulty_wall.calls == 2
    _assert_restarted_but_not_resumed(journal, directory, ("journal_clock_invalid", "process"))


def test_k5_a_mono_regression_at_the_resume_step_latches_journal_clock_invalid(tmp_path):
    directory, clock, ids, token = _resume_ready_image(tmp_path, "k5-resume-mono")
    calls = {"n": 0}

    def regressing_mono() -> int:
        calls["n"] += 1
        # The restart reads it first; the resume's read, in the same boot, goes back.
        return 1_000 if calls["n"] == 2 else clock.mono()

    journal = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=regressing_mono, id_factory=ids,
        resume=rj.ResumeRequest(token=token, operator="op"),
    )
    assert calls["n"] == 2
    _assert_restarted_but_not_resumed(journal, directory, ("journal_clock_invalid", "process"))


def test_k5_an_anchor_write_fault_at_the_resume_step_latches_journal_write_failed(
    tmp_path, monkeypatch,
):
    directory, clock, ids, token = _resume_ready_image(tmp_path, "k5-resume-write")
    real_write_slot = journal_store.JournalStore._write_slot
    calls = {"n": 0}

    def write_slot(store, body):
        calls["n"] += 1
        if calls["n"] == 2:  # the restart's anchor is the first
            raise OSError("injected fault")
        return real_write_slot(store, body)

    monkeypatch.setattr(journal_store.JournalStore, "_write_slot", write_slot)
    journal = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
        resume=rj.ResumeRequest(token=token, operator="op"),
    )
    try:
        assert journal.hold == ("journal_write_failed", "process")
        assert journal.resumed_this_boot is None
        assert journal.front_door_status()["resume"] == {"this_boot": "not_applied"}
    finally:
        journal.close()
    monkeypatch.undo()
    # The operator_action row is committed; its anchor is not (lag 1).
    report = rj.inspect_recovery_journal(directory).report
    assert (report["anchor"]["lag"], report["resumes"]["count"]) == (1, 1)


def test_k5_a_resume_over_the_total_region_latches_journal_capacity_recovery(tmp_path):
    probe_directory, clock, ids, token = _resume_ready_image(tmp_path, "k5-total-probe")
    probe = rj.open_recovery_journal(
        probe_directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
        resume=rj.ResumeRequest(token=token, operator="op"),
    )
    try:
        assert probe.resumed_this_boot is not None
        logical_bytes = probe.snapshot()["bytes"]["logical"]
        resume_charge = len(list(probe._store.rows())[-1].body) + jrd.RECORD_OVERHEAD_BYTES
    finally:
        probe.close()

    # The restart fits; the resume overflows the total region by about half
    # its own charge (a margin far above genesis's few digit-dependent bytes).
    total_bytes = logical_bytes - resume_charge // 2
    bounds = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=total_bytes,
        total_bytes=total_bytes,
    )
    directory, clock, ids, token = _resume_ready_image(tmp_path, "k5-total", bounds=bounds)
    journal = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
        resume=rj.ResumeRequest(token=token, operator="op"),
    )
    _assert_restarted_but_not_resumed(
        journal, directory, ("journal_capacity_recovery", "process"),
    )


# === K6: inspect over eleven images ==========================================


def _k6_image_ready_lag0(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-lag0", 1)
    return directory


def _k6_image_lag1(tmp_path, monkeypatch):
    image, _a, _prior = _e2_image(tmp_path, monkeypatch, "k6-lag1")
    return image


def _tear_last_commit(directory):
    wal_bytes = wal_path_of(directory).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path_of(directory).write_bytes(flip_byte_in_group(wal_bytes, groups[-1]))


def _k6_image_recovery_finding_unpersisted(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-unpersisted", 2)
    _tear_last_commit(directory)
    return directory  # never opened since the tear: the anchor carries no hold yet


def _k6_image_persisted_hold(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-persisted", 2)
    _tear_last_commit(directory)
    open_held(directory).close()  # persists journal_truncated into the anchor
    return directory


def _k6_image_process_finding(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-process", 1)
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        # Without this, closing this raw connection -- the sole connection,
        # since the journal's own handle already closed -- triggers SQLite's
        # default checkpoint-and-remove-the-WAL behavior on last close, which
        # would turn this into a WAL-absent image instead of the intended
        # WAL-present process finding.
        raw.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        raw.execute("PRAGMA user_version=2")
        raw.commit()
    finally:
        raw.close()
    return directory


def _k6_image_lock_absent(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-nolock", 1)
    lock_path = directory / journal_store.LOCK_FILENAME
    if lock_path.exists():
        lock_path.unlink()
    return directory


def _k6_image_wal_absent_checkpointed(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-checkpointed", 2)
    # A raw-connection TRUNCATE checkpoint, closing as the sole connection,
    # already leaves the WAL absent: no separate unlink is needed.
    _checkpoint(directory)
    assert not wal_path_of(directory).exists()
    return directory


def _k6_image_wal_removed_anchor_ahead(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-anchor-ahead", 2)
    wal_path_of(directory).unlink()  # no checkpoint: the last commit(s) are lost
    return directory


def _k6_image_persisted_hold_no_wal(tmp_path, monkeypatch):
    directory = _k6_image_persisted_hold(tmp_path, monkeypatch)
    wal_path_of(directory).unlink()
    return directory


def _k6_image_db_unlinked_no_wal(tmp_path, monkeypatch):
    directory, _clock, _ids, journal = make(tmp_path, "k6-dbgone")
    journal.close()
    wal_path_of(directory).unlink(missing_ok=True)
    db_path_of(directory).unlink()
    return directory


def _k6_image_torn_wal_tail(tmp_path, monkeypatch):
    directory, _receipts = _n_admissions(tmp_path, "k6-torn-tail", 2)
    wal_bytes = wal_path_of(directory).read_bytes()
    frames = wal_frames(wal_bytes)
    cut = frames[-1]["data_start"] + 10  # mid-frame, well short of the checksum
    wal_path_of(directory).write_bytes(wal_bytes[:cut])
    return directory


_K6_IMAGES = (
    ("ready_lag0", _k6_image_ready_lag0),
    ("lag1", _k6_image_lag1),
    ("recovery_finding_unpersisted", _k6_image_recovery_finding_unpersisted),
    ("persisted_hold", _k6_image_persisted_hold),
    ("process_finding", _k6_image_process_finding),
    ("lock_absent", _k6_image_lock_absent),
    ("wal_absent_checkpointed", _k6_image_wal_absent_checkpointed),
    ("wal_removed_anchor_ahead", _k6_image_wal_removed_anchor_ahead),
    ("persisted_hold_no_wal", _k6_image_persisted_hold_no_wal),
    ("db_unlinked_no_wal", _k6_image_db_unlinked_no_wal),
    ("torn_wal_tail", _k6_image_torn_wal_tail),
)

_K6_UNVERIFIED = {
    "wal_absent_checkpointed", "wal_removed_anchor_ahead", "persisted_hold_no_wal",
}


@pytest.mark.parametrize("name,builder", _K6_IMAGES, ids=[n for n, _b in _K6_IMAGES])
def test_k6_inspect_over_eleven_images(tmp_path, monkeypatch, name, builder):
    directory = builder(tmp_path, monkeypatch)
    twin = _copy_image(directory, tmp_path / f"{name}-twin")
    before = _file_snapshot(directory)

    inspection = rj.inspect_recovery_journal(directory)
    report = inspection.report
    assert report["mode"] == "verify_only"

    # Whatever the unchanged unit-15 open of a twin gives is the verdict
    # (for the torn tail this is the only verdict asserted).
    if name not in _K6_UNVERIFIED:
        opened = rj.open_recovery_journal(twin)
        try:
            if opened.state == "ready":
                assert report["verdict"] == "ready"
            else:
                assert report["verdict"] == "held"
                assert (report["finding"]["code"], report["finding"]["scope"]) == opened.hold
        finally:
            opened.close()

    if name in _K6_UNVERIFIED:
        assert report["verdict"] == "unverified"
        assert report["reason"] == "wal_absent"
        assert report["next_open"] == ["unknown"]
        for key in ("journal", "pending", "refusals", "resumes", "resume"):
            assert report[key] is None
        assert inspection.references == frozenset()
    elif name == "db_unlinked_no_wal":
        assert report["verdict"] == "held"
        assert report["finding"]["code"] == "journal_truncated"
        assert report["next_open"] == ["persist_hold"]  # a recovery finding, not yet in the anchor
        assert not wal_path_of(directory).exists()
    elif name == "process_finding":
        assert report["verdict"] == "held"
        assert report["finding"]["code"] == "journal_schema_unsupported"
        assert report["next_open"] == ["hold"]  # a process finding: the next open writes nothing
    elif name == "recovery_finding_unpersisted":
        assert report["verdict"] == "held"
        assert report["finding"]["code"] == "journal_truncated"
        assert report["finding"]["in_anchor"] is False
        assert report["next_open"] == ["persist_hold"]
        assert report["created"] in ([], ["lock"])
    elif name == "persisted_hold":
        assert report["verdict"] == "held"
        assert report["finding"]["code"] == "journal_truncated"
        assert report["finding"]["in_anchor"] is True
        assert report["next_open"] == ["persist_hold"]
    elif name == "lag1":
        assert report["verdict"] == "ready"
        assert report["anchor"]["lag"] == 1
        assert report["next_open"] == ["reanchor", "restart_recovery"]
    elif name == "lock_absent":
        assert report["verdict"] == "ready"
        assert report["created"] == ["lock"]
    elif name == "ready_lag0":
        assert report["verdict"] == "ready"
        assert report["anchor"]["lag"] == 0
        assert report["next_open"] == ["restart_recovery"]
    # torn_wal_tail: whatever the unchanged unit-15 open gives (K7 checks
    # inspect did not change it); no fixed code is asserted here.

    # V11: inspect never writes anything but an absent ``lock``.
    after = _file_snapshot(directory)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed <= {journal_store.LOCK_FILENAME}


def test_k6_persisted_hold_without_wal_opens_held_and_inspect_stays_unverified(
    tmp_path, monkeypatch,
):
    # Why the runbook takes the hold code on /health as the verdict: an open
    # of this image returns before connecting, so no later inspect can verify it.
    directory = _k6_image_persisted_hold_no_wal(tmp_path, monkeypatch)
    assert rj.inspect_recovery_journal(directory).report["verdict"] == "unverified"
    opened = rj.open_recovery_journal(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
        assert opened.snapshot()["hold"]["persisted"] is True
    finally:
        opened.close()
    assert not wal_path_of(directory).exists()
    again = rj.inspect_recovery_journal(directory).report
    assert (again["verdict"], again["reason"]) == ("unverified", "wal_absent")


def test_i16_unverified_report_created_is_empty_even_when_the_lock_is_absent(tmp_path, monkeypatch):
    # I16: the unverified path never opens the store, so it must report
    # created == [] regardless of the lock's own state beforehand -- no K6
    # image is both WAL-absent (full-size DB) and lock-absent at once.
    directory = _k6_image_wal_absent_checkpointed(tmp_path, monkeypatch)
    lock_path = directory / journal_store.LOCK_FILENAME
    if lock_path.exists():
        lock_path.unlink()
    assert not lock_path.exists()
    before = _file_snapshot(directory)

    report = rj.inspect_recovery_journal(directory).report
    assert report["verdict"] == "unverified"
    assert report["created"] == []
    assert not lock_path.exists()
    assert _file_snapshot(directory) == before


# === K7: inspect is neutral: twin A (inspected) == twin B (never inspected) =


def _copy_image(base: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    shutil.copytree(base, target)
    return target


def _anchor_slot_bodies(directory: pathlib.Path) -> list:
    return journal_store._slot_bodies(anchor_path_of(directory).read_bytes())


def _stored_records(directory: pathlib.Path) -> list:
    store = journal_store.JournalStore.open(directory)
    try:
        return list(store.rows())
    finally:
        store.close()


def _assert_next_open_happened(report: dict, snapshot: dict, records: list) -> None:
    """The open after an inspect did what that inspect's ``next_open`` said."""
    next_open = report["next_open"]
    if next_open[-1] == "restart_recovery":
        assert snapshot["state"] == "ready"
        assert records[-1].event_type == "restart_recovery"
        assert records[-1].data["anchor_lag"] == (1 if next_open[0] == "reanchor" else 0)
    elif next_open != ["unknown"]:
        finding = report["finding"]
        scope = "recovery" if next_open == ["persist_hold"] else "process"
        assert (finding["scope"], snapshot["state"]) == (scope, "held")
        assert (snapshot["hold"]["code"], snapshot["hold"]["scope"]) == (finding["code"], scope)
        assert snapshot["hold"]["persisted"] is (scope == "recovery")


@pytest.mark.parametrize("name,builder", _K6_IMAGES, ids=[n for n, _b in _K6_IMAGES])
def test_k7_inspect_neutrality(tmp_path, monkeypatch, name, builder):
    base_root = tmp_path / "base"
    base_root.mkdir()
    base = builder(base_root, monkeypatch)
    twin_a = _copy_image(base, tmp_path / "twin-a")
    twin_b = _copy_image(base, tmp_path / "twin-b")

    report = rj.inspect_recovery_journal(twin_a).report

    ids_a, ids_b = SeqIds(start=5_000), SeqIds(start=5_000)
    clock_a, clock_b = SeqClock(), SeqClock()
    opened_a = rj.open_recovery_journal(
        twin_a, wall_clock=clock_a.wall, mono_clock=clock_a.mono, id_factory=ids_a,
    )
    opened_b = rj.open_recovery_journal(
        twin_b, wall_clock=clock_b.wall, mono_clock=clock_b.mono, id_factory=ids_b,
    )
    try:
        assert opened_a.state == opened_b.state
        assert opened_a.hold == opened_b.hold
        assert opened_a.dispatch_holds == opened_b.dispatch_holds
        snapshot_a = opened_a.snapshot()
    finally:
        opened_a.close()
        opened_b.close()

    records_a = _stored_records(twin_a)
    assert [r.body for r in records_a] == [r.body for r in _stored_records(twin_b)]
    assert _anchor_slot_bodies(twin_a) == _anchor_slot_bodies(twin_b)
    if snapshot_a["state"] == "held":
        # rows() yields nothing once the store has a finding, so compare the
        # files themselves: a held open writes neither the DB nor the WAL.
        assert _db_and_wal_bytes(twin_a) == _db_and_wal_bytes(twin_b)
    _assert_next_open_happened(report, snapshot_a, records_a)


def _db_and_wal_bytes(directory) -> tuple:
    return tuple(
        path.read_bytes() if path.exists() else None
        for path in (db_path_of(directory), wal_path_of(directory))
    )


# === K8: inspect while a handle is open =====================================


def test_k8_inspect_while_open_gives_journal_locked_with_a_clean_error(tmp_path):
    marker = "k8markerZZ"
    directory, _clock, _ids, journal = make(tmp_path, f"k8-{marker}")
    try:
        with pytest.raises(rj.JournalError) as info:
            rj.inspect_recovery_journal(directory)
        error = info.value
        assert error.args == ("journal_locked",)
        assert error.__cause__ is None
        assert error.__context__ is None
        assert marker not in repr(error)
        assert marker not in str(error)
    finally:
        journal.close()


_K8_CANARY = "k8canaryQQ"
_REPORT_KEYS = {
    "mode", "verdict", "reason", "created", "finding", "anchor", "wal_found", "next_open",
    "journal", "pending", "refusals", "resumes", "resume",
}
_SUMMARY_KEYS = {
    "alerts", "body_bytes", "body_digest", "code", "members", "members_omitted",
    "refused_group", "resolved", "source_group",
}


def _assert_json_round_trips_without_canary(report: dict) -> None:
    encoded = json.dumps(report)
    assert json.loads(encoded) == report
    assert _K8_CANARY not in encoded


def test_k8_ready_report_is_json_with_its_closed_shape_and_no_canary(tmp_path):
    bounds = jrd.JournalBounds(
        max_admissions=2, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    directory, clock, ids, journal = make(tmp_path, f"k8-{_K8_CANARY}", bounds=bounds)
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    with pytest.raises(rj.JournalError):
        journal.admit(source(CG1_KEY, ("k8-third", "firing", (("A", "1"),))))  # capacity_hold
    canary_extra = {"message": _K8_CANARY, "commonAnnotations": {"summary": _K8_CANARY}}
    recorded = [
        _many_alerts_summary(33, 1, extra=canary_extra),
        _json_invalid_summary(b"not json " + _K8_CANARY.encode("ascii")),
    ]
    for summary in recorded:
        assert journal.record_refusal(summary) == "recorded"
    with pytest.raises(rj.JournalError):
        journal.record_refusal({"code": _K8_CANARY})
    journal.close()
    reopen(directory, clock, ids).close()
    resume = rj.ResumeRequest(token=_resume_token(directory), operator="k8-operator")
    journal = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    recorded.append(_oversize_summary())
    assert journal.record_refusal(recorded[-1]) == "recorded"
    journal.close()

    report = rj.inspect_recovery_journal(directory).report
    _assert_json_round_trips_without_canary(report)
    assert set(report) == _REPORT_KEYS
    assert report["verdict"] == "ready"
    assert set(report["anchor"]) == {"counter", "commit_seq", "event_seq", "lag"}
    assert set(report["wal_found"]) == {"size", "digest"}
    journal_json = report["journal"]
    assert set(journal_json) == {
        "journal_uuid", "generation", "head", "dispatch_holds", "counts", "bytes", "bounds",
        "pending_digest", "state_digest", "front_door_digest",
    }
    assert set(journal_json["head"]) == {"commit_seq", "event_seq", "record_digest"}
    assert [set(hold) for hold in journal_json["dispatch_holds"]] == [
        {"code", "since_commit_seq"},
    ]
    assert set(journal_json["counts"]) == {
        "records", "admissions", "pending_fingerprints", "source_groups",
    }
    assert set(journal_json["bytes"]) == {"logical", "ordinary_limit", "total_limit"}
    assert set(journal_json["bounds"]) == set(jr.V1_BOUND_CEILINGS)
    assert len(report["pending"]) == 2
    for entry in report["pending"]:
        assert set(entry) == {
            "fingerprint", "status", "values", "admission_id", "arrival_seq", "source_group",
        }
    assert set(report["refusals"]) == {
        "recorded", "limit", "reserve", "unreserved_recorded", "recent",
    }
    recent = report["refusals"]["recent"]
    assert all(set(entry) == {"commit_seq", "summary"} for entry in recent)
    assert all(set(entry["summary"]) == _SUMMARY_KEYS for entry in recent)
    # Each summary reads back exactly as refusal_to_json produced it.
    assert [entry["summary"] for entry in recent] == recorded
    assert set(report["resumes"]) == {"count", "last"}
    assert set(report["resumes"]["last"]) == {
        "commit_seq", "operator", "reason", "inspected_commit_seq",
    }
    assert set(report["resume"]) == {"token", "head_commit_seq"}


def test_k8_held_report_is_json_with_nulls_and_no_canary(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, f"k8-held-{_K8_CANARY}", 2)
    _tear_last_commit(directory)
    report = rj.inspect_recovery_journal(directory).report
    _assert_json_round_trips_without_canary(report)
    assert set(report) == _REPORT_KEYS
    assert set(report["finding"]) == {"code", "scope", "in_anchor"}


def test_k8_held_report_fills_anchor_and_wal_found_from_the_image(tmp_path):
    # The null rule nulls only the journal-derived fields; finding, anchor,
    # wal_found and next_open describe the image and stay filled when known.
    directory, _receipts = _n_admissions(tmp_path, "k8-held-filled", 2)
    _tear_last_commit(directory)
    store = journal_store.JournalStore.open(directory)
    try:
        anchor, wal_found = store.anchor, store.wal_found
    finally:
        store.close()
    assert anchor is not None and wal_found is not None
    report = rj.inspect_recovery_journal(directory).report
    assert report["verdict"] == "held"
    assert report["wal_found"] == {"size": wal_found.size, "digest": wal_found.digest}
    assert report["anchor"] == {
        "counter": anchor.counter, "commit_seq": anchor.head.commit_seq,
        "event_seq": anchor.head.event_seq, "lag": -1,
    }


def test_k8_a_symlinked_wal_is_refused_by_inspect_as_by_open(tmp_path):
    # The pre-check uses lstat: a dangling WAL symlink is not "absent", so
    # inspect refuses it exactly as open does rather than reporting unverified.
    directory, _clock, _ids, journal = make(tmp_path, "k8-wal-symlink")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    _checkpoint(directory)
    assert not wal_path_of(directory).exists()
    wal_path_of(directory).symlink_to(tmp_path / "nowhere")
    for entry_point in (rj.inspect_recovery_journal, rj.open_recovery_journal):
        with pytest.raises(rj.JournalError) as info:
            entry_point(directory)
        assert info.value.args == ("journal_path_invalid",), entry_point.__name__


def test_k1_record_refusal_checks_held_before_the_summary(tmp_path):
    # The same order as admit: closed, then held, then the argument.
    directory, _receipts = _n_admissions(tmp_path, "k1-held-first", 2)
    _tear_last_commit(directory)
    held = rj.open_recovery_journal(directory)
    try:
        assert held.state == "held"
        with pytest.raises(rj.JournalError) as info:
            held.record_refusal({"code": "ingress_json_invalid"})
        assert info.value.args == ("journal_held",)
    finally:
        held.close()


_BAD_DIRECTORY_CASES = (
    ("regular_file", "journal_path_invalid"),
    ("str_path", "journal_argument"),
    ("symlink", "journal_path_invalid"),
    ("group_readable", "journal_permissions"),
    ("overlong_name", "journal_path_invalid"),
    ("unsearchable", "journal_path_invalid"),
)


@pytest.mark.parametrize(
    "case,code", _BAD_DIRECTORY_CASES, ids=[case for case, _code in _BAD_DIRECTORY_CASES],
)
def test_k8_inspect_refuses_a_bad_directory_with_open_s_own_fixed_code(tmp_path, case, code):
    if case == "unsearchable" and os.geteuid() == 0:
        pytest.skip("root searches a mode-0000 directory")
    marker = "k8dirQQ"
    directory, _clock, _ids, journal = make(tmp_path, f"k8-{case}-{marker}")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    # WAL absent with a full-size DB: the pre-check's own "unverified" branch,
    # which must still refuse whatever open refuses.
    _checkpoint(directory)
    target = directory
    if case == "regular_file":
        target = tmp_path / f"file-{marker}"
        target.write_bytes(b"x")
    elif case == "str_path":
        target = str(directory)
    elif case == "symlink":
        target = tmp_path / f"link-{marker}"
        target.symlink_to(directory, target_is_directory=True)
    elif case == "group_readable":
        directory.chmod(0o750)
    elif case == "overlong_name":
        target = tmp_path / ("x" * 300 + marker)
    else:
        directory.chmod(0o000)
    try:
        for entry_point in (rj.inspect_recovery_journal, rj.open_recovery_journal):
            with pytest.raises(rj.JournalError) as info:
                entry_point(target)
            error = info.value
            assert error.args == (code,), entry_point.__name__
            assert error.__cause__ is None and error.__context__ is None
            assert marker not in str(error) and marker not in repr(error)
    finally:
        directory.chmod(0o700)
    assert not wal_path_of(directory).exists()


# === K9: observe sees each verified group exactly once ======================


def test_k9_observe_sees_each_group_exactly_once(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k9")
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    journal.admit(a)
    journal.record_refusal(_json_invalid_summary())
    journal.close()

    store = journal_store.JournalStore.open(directory)
    try:
        candidate = jrd.new_projection()
        seen = []
        rj._replay_finding(store, candidate, observe=seen.append)
    finally:
        store.close()
    # Exactly the three commits: genesis, the admission pair, the refusal.
    assert len(seen) == 3
    assert [len(group) for group in seen] == [1, 2, 1]
    assert [group[0].event_type for group in seen] == [
        "journal_genesis", "admission", "ingress_refusal",
    ]


def test_k9_inspect_references_equal_the_admitted_digest_set(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k9-references")
    # The shared ``source()`` fixture hardcodes body_digest="0"*64; give each
    # source its own digest so the admitted set has two distinct members.
    a = dataclasses.replace(source(CG1_KEY, (PF, "firing", (("A", "1"),))), body_digest="1" * 64)
    b = dataclasses.replace(source(CG1_KEY, (PC, "firing", (("A", "1"),))), body_digest="2" * 64)
    journal.admit(a)
    journal.admit(b)
    journal.record_refusal(_json_invalid_summary())  # never a reference
    journal.close()

    inspection = rj.inspect_recovery_journal(directory)
    assert inspection.references == {a.body_digest, b.body_digest}


def test_k9_resumes_last_is_the_newer_of_two_resumes(tmp_path):
    directory, clock, ids, journal = make(tmp_path, "k9-two-resumes")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    resume_rows = []
    for operator, reason in (("op-1", "first-look"), ("op-2", "second-look")):
        resume = rj.ResumeRequest(token=_resume_token(directory), operator=operator, reason=reason)
        resumed = rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
            resume=resume,
        )
        try:
            assert resumed.resumed_this_boot is not None
            resume_rows.append(list(resumed._store.rows())[-1])
        finally:
            resumed.close()
    first, second = resume_rows
    assert first.data["inspected"]["commit_seq"] != second.data["inspected"]["commit_seq"]

    resumes = rj.inspect_recovery_journal(directory).report["resumes"]
    assert resumes["count"] == 2
    assert resumes["last"] == {
        "commit_seq": second.position.commit_seq, "operator": "op-2", "reason": "second-look",
        "inspected_commit_seq": second.data["inspected"]["commit_seq"],
    }


def test_k9_recent_refusals_capped_at_32_newest_last(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k9-recent")
    keys_seen = []
    for i in range(33):
        group_key = f'{{}}:{{alertname="k9-recent-{i:02d}", grafana_folder="ops"}}'
        body = _many_alerts_body(group_key, 33, 0)
        outcome = ji.sanitize_notification(body)
        assert outcome.refusal is not None
        summary = ji.refusal_to_json(outcome.refusal)
        assert journal.record_refusal(summary) == "recorded"
        keys_seen.append(jrd.refusal_key(summary))
    assert len(set(keys_seen)) == 33  # every one is a distinct membership key
    journal.close()

    inspection = rj.inspect_recovery_journal(directory)
    recent = inspection.report["refusals"]["recent"]
    assert len(recent) == 32
    # "recent" holds the 32 newest, oldest first excluded, newest last.
    assert [entry["commit_seq"] for entry in recent] == sorted(
        entry["commit_seq"] for entry in recent
    )
    seen_source_groups = [entry["summary"]["source_group"] for entry in recent]
    first_summary = ji.refusal_to_json(
        ji.sanitize_notification(
            _many_alerts_body(
                '{}:{alertname="k9-recent-00", grafana_folder="ops"}', 33, 0,
            )
        ).refusal
    )
    assert first_summary["source_group"] not in seen_source_groups
    last_summary = ji.refusal_to_json(
        ji.sanitize_notification(
            _many_alerts_body(
                '{}:{alertname="k9-recent-32", grafana_folder="ops"}', 33, 0,
            )
        ).refusal
    )
    assert seen_source_groups[-1] == last_summary["source_group"]


def test_k9_observe_raises_propagates_and_the_lock_releases(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k9-raise")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()

    store = journal_store.JournalStore.open(directory)

    class _Marker(Exception):
        pass

    def _raising_observe(_group):
        raise _Marker

    try:
        with pytest.raises(_Marker):
            rj._replay_finding(store, jrd.new_projection(), observe=_raising_observe)
    finally:
        store.close()

    # The lock can be taken again at once: the store was closed on the way out.
    reopened = open_ready(directory)
    reopened.close()


@pytest.mark.parametrize("seam", ["observe", "ready_report"])
def test_k9_an_exception_inside_inspect_propagates_and_the_store_is_closed(
    tmp_path, monkeypatch, seam,
):
    directory, _clock, _ids, journal = make(tmp_path, f"k9-inspect-{seam}")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()

    class _Marker(Exception):
        pass

    def raise_marker(*_args, **_kwargs):
        raise _Marker

    if seam == "observe":
        real_replay_finding = rj._replay_finding

        def replay_with_a_raising_observe(store, candidate, *, observe=None):
            return real_replay_finding(store, candidate, observe=raise_marker)

        monkeypatch.setattr(rj, "_replay_finding", replay_with_a_raising_observe)
    else:
        monkeypatch.setattr(rj, "_ready_report", raise_marker)
    with pytest.raises(_Marker):
        rj.inspect_recovery_journal(directory)
    monkeypatch.undo()

    # The lock can be taken again at once: inspect's own finally closed the store.
    store = journal_store.JournalStore.open(directory)
    store.close()


def test_k9_a_torn_tail_after_a_verified_admission_still_leaves_references_empty(tmp_path):
    # The first admission is in the verified prefix observe saw; the null rule
    # still discards it, because the image as a whole did not verify.
    directory, _receipts = _n_admissions(tmp_path, "k9-prefix", 2)
    _tear_last_commit(directory)
    inspection = rj.inspect_recovery_journal(directory)
    assert inspection.report["verdict"] == "held"
    for key in ("journal", "pending", "refusals", "resumes", "resume"):
        assert inspection.report[key] is None
    assert inspection.references == frozenset()


def _append_raw_row(directory: pathlib.Path, record) -> None:
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        # Keep the WAL, so the image stays WAL-present as the journal leaves it.
        raw.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        raw.execute(journal_store._INSERT_SQL, journal_store._row_params(record))
        raw.commit()
    finally:
        raw.close()


def test_k9_a_forged_row_that_fails_replay_leaves_references_empty(tmp_path):
    directory, clock, _ids, journal = make(tmp_path, "k9-forged-row")
    admitted = dataclasses.replace(
        source(CG1_KEY, (PF, "firing", (("A", "1"),))), body_digest="1" * 64,
    )
    journal.admit(admitted)
    p = journal._projection
    summary = jr.refusal_summary_data(_json_invalid_summary())
    # Digest- and chain-valid, and valid by every record rule; only replay's
    # key recomputation can tell it from a real refusal.
    forged = jr.seal(
        jr.Draft(
            event_id="k9-forged-refusal", event_type="ingress_refusal", actor="receiver", ids={},
            data={
                "rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": "0" * 64,
                "refusal_seq": 1,
            },
        ),
        jr.Position(
            journal_generation=p.generation, event_seq=p.head.event_seq + 1,
            commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
            prev_record_digest=p.head.record_digest,
        ),
        jr.Stamp(
            boot_id=p.boot_id, wall_time=jr.format_wall_time(clock.wall()),
            mono_us=p.last_mono_us + 1,
        ),
    )
    journal.close()
    _append_raw_row(directory, forged)

    inspection = rj.inspect_recovery_journal(directory)
    assert inspection.report["verdict"] == "held"
    assert inspection.report["finding"]["code"] == "journal_replay_mismatch"
    for key in ("journal", "pending", "refusals", "resumes", "resume"):
        assert inspection.report[key] is None
    assert inspection.references == frozenset()


def test_i12_replay_finding_observes_only_groups_verified_before_the_finding(tmp_path):
    # I12: observe(group) must run only after that group's own verify_commit/
    # apply_delta succeeded, so a group that fails replay is never observed.
    directory, clock, _ids, journal = make(tmp_path, "i12-observe-order")
    admitted = dataclasses.replace(
        source(CG1_KEY, (PF, "firing", (("A", "1"),))), body_digest="1" * 64,
    )
    journal.admit(admitted)
    p = journal._projection
    summary = jr.refusal_summary_data(_json_invalid_summary())
    # Digest- and chain-valid, and valid by every record rule; only replay's
    # key recomputation can tell it from a real refusal (as K9's forged-row
    # case does).
    forged = jr.seal(
        jr.Draft(
            event_id="i12-forged-refusal", event_type="ingress_refusal", actor="receiver", ids={},
            data={
                "rule": jr.REFUSAL_RULE, "summary": summary, "refusal_key": "0" * 64,
                "refusal_seq": 1,
            },
        ),
        jr.Position(
            journal_generation=p.generation, event_seq=p.head.event_seq + 1,
            commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
            prev_record_digest=p.head.record_digest,
        ),
        jr.Stamp(
            boot_id=p.boot_id, wall_time=jr.format_wall_time(clock.wall()),
            mono_us=p.last_mono_us + 1,
        ),
    )
    journal.close()
    _append_raw_row(directory, forged)

    seen: list = []
    store = journal_store.JournalStore.open(directory)
    try:
        finding, _lag = rj._replay_finding(store, jrd.new_projection(), observe=seen.append)
    finally:
        store.close()
    assert finding is not None
    assert finding.code == "journal_replay_mismatch"
    assert [group[0].event_type for group in seen] == ["journal_genesis", "admission"]


def test_k9_inspect_on_unreplayable_tail_has_null_journal_and_empty_references(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k9-forged")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    _tear_last_commit(directory)

    inspection = rj.inspect_recovery_journal(directory)
    report = inspection.report
    for key in ("journal", "pending", "refusals", "resumes", "resume"):
        assert report[key] is None
    assert inspection.references == frozenset()


# === F3: residue-gap closures (Tester T1) ====================================


def test_f3_1_ready_report_values_match_an_independent_replay(tmp_path):
    """No existing test checks the VALUES in ``inspect_recovery_journal``'s
    ready report, only its keys (K8 pins the shape). Every value below is
    checked against an independent replay of the stored rows -- read
    straight from the store, never through ``inspect_recovery_journal``'s
    own internals -- so a bug in how the report is assembled (a stale field,
    a swapped key, an off-by-one lag) is caught even though it would still
    produce a syntactically valid report.
    """
    directory, clock, ids, journal = make(tmp_path, "f3-1")
    admitted = journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    assert admitted.decision == "admitted"
    refusal_summary = _json_invalid_summary()
    assert journal.record_refusal(refusal_summary) == "recorded"
    journal.close()

    held = reopen(directory, clock, ids)  # a restart, unresumed: dispatch_holds gains restart_recovery
    assert "restart_recovery" in held.dispatch_holds
    held.close()

    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="f3-1-operator", reason="restart-inspected")
    resumed = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    resumed.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    resumed.close()

    inspection = rj.inspect_recovery_journal(directory)
    report = inspection.report

    # --- An independent source of truth: the raw rows, replayed fresh. -----
    store = journal_store.JournalStore.open(directory)
    try:
        rows = list(store.rows())
        wal_found, anchor = store.wal_found, store.anchor
    finally:
        store.close()
    replayed = jrd.replay(rows)
    refusal_rows = [r for r in rows if r.event_type == "ingress_refusal"]
    resume_rows = [r for r in rows if r.event_type == "operator_action"]
    assert len(refusal_rows) == 1
    assert len(resume_rows) == 1

    assert report["mode"] == "verify_only"
    assert report["verdict"] == "ready"
    assert report["reason"] is None
    assert report["created"] == []  # the lock already existed from `make`
    assert report["finding"] is None

    assert report["wal_found"] == (
        None if wal_found is None else {"size": wal_found.size, "digest": wal_found.digest}
    )
    assert anchor is not None
    expected_lag = replayed.head.commit_seq - anchor.head.commit_seq
    assert expected_lag == 0  # every close above was clean
    assert report["anchor"] == {
        "counter": anchor.counter, "commit_seq": anchor.head.commit_seq,
        "event_seq": anchor.head.event_seq, "lag": expected_lag,
    }
    assert report["next_open"] == ["restart_recovery"]

    journal_json = report["journal"]
    assert journal_json["journal_uuid"] == replayed.journal_uuid
    assert journal_json["generation"] == replayed.generation
    assert journal_json["head"] == {
        "commit_seq": replayed.head.commit_seq, "event_seq": replayed.head.event_seq,
        "record_digest": replayed.head.record_digest,
    }
    assert journal_json["dispatch_holds"] == [
        {"code": code, "since_commit_seq": seq}
        for code, seq in sorted(replayed.dispatch_holds.items())
    ]
    assert journal_json["dispatch_holds"] == []  # the resume cleared restart_recovery
    assert journal_json["counts"] == {
        "records": replayed.head.event_seq, "admissions": replayed.admission_count,
        "pending_fingerprints": len(replayed.pending), "source_groups": len(replayed.baselines),
    }
    assert journal_json["bytes"] == {
        "logical": replayed.logical_bytes, "ordinary_limit": replayed.bounds.ordinary_bytes,
        "total_limit": replayed.bounds.total_bytes,
    }
    assert journal_json["bounds"] == {
        "max_admissions": replayed.bounds.max_admissions,
        "max_pending_fingerprints": replayed.bounds.max_pending_fingerprints,
        "ordinary_bytes": replayed.bounds.ordinary_bytes, "total_bytes": replayed.bounds.total_bytes,
    }
    assert journal_json["pending_digest"] == jrd.pending_digest(replayed)
    assert journal_json["state_digest"] == jrd.state_digest(replayed)
    assert journal_json["front_door_digest"] == jrd.front_door_digest(replayed)

    expected_pending = [
        {
            "fingerprint": e.fingerprint, "status": e.status,
            "values": None if e.values is None else dict(e.values),
            "admission_id": e.admission_id, "arrival_seq": e.arrival_seq,
            "source_group": e.source_group,
        }
        for e in jrd.pending_entries(replayed)
    ]
    assert report["pending"] == expected_pending

    assert report["refusals"]["recorded"] == replayed.refusal_count == 1
    assert report["refusals"]["limit"] == jrd.MAX_REFUSAL_RECORDS
    assert report["refusals"]["reserve"] == jrd.REFUSAL_RESOLVED_RESERVE
    assert report["refusals"]["unreserved_recorded"] == replayed.refusal_unreserved_count
    refusal_row = refusal_rows[0]
    expected_summary = dict(jr.thaw(refusal_row.data["summary"]))
    expected_summary["members"] = [list(m) for m in refusal_row.data["summary"]["members"]]
    assert report["refusals"]["recent"] == [
        {"commit_seq": refusal_row.position.commit_seq, "summary": expected_summary},
    ]

    assert report["resumes"]["count"] == replayed.resume_count == 1
    resume_row = resume_rows[0]
    assert report["resumes"]["last"] == {
        "commit_seq": resume_row.position.commit_seq, "operator": resume_row.data["operator"],
        "reason": resume_row.data["reason"],
        "inspected_commit_seq": resume_row.data["inspected"]["commit_seq"],
    }
    assert report["resume"] == {
        "token": replayed.head.record_digest, "head_commit_seq": replayed.head.commit_seq,
    }


def test_f3_4_references_include_held_and_suppressed_admissions_not_refusals(tmp_path):
    """``Inspection.references`` was only ever exercised for freshly admitted
    bodies (K9). A held admission (accepted while a dispatch hold is in
    effect, after a restart without resume) and a suppressed one (a
    duplicate) still had their bodies durably spooled, so both must still be
    referenced; a refused body was never admitted at all, so it must not.
    """
    directory, clock, ids, journal = make(tmp_path, "f3-4")
    a = dataclasses.replace(source(CG1_KEY, (PF, "firing", (("A", "1"),))), body_digest="1" * 64)
    admitted = journal.admit(a)
    assert (admitted.decision, admitted.result) == ("admitted", "admitted")

    refusal_summary = _json_invalid_summary()
    assert journal.record_refusal(refusal_summary) == "recorded"
    journal.close()

    held = reopen(directory, clock, ids)  # a restart without resume: dispatch_holds stays held
    assert "restart_recovery" in held.dispatch_holds
    repeat = dataclasses.replace(source(CG1_KEY, (PF, "firing", (("A", "1"),))), body_digest="2" * 64)
    receipt = held.admit(repeat)
    assert (receipt.decision, receipt.result) == ("held", "suppressed")
    held.close()

    inspection = rj.inspect_recovery_journal(directory)
    assert inspection.references == {a.body_digest, repeat.body_digest}
    assert refusal_summary["body_digest"] not in inspection.references


_JOURNAL_ERROR_CODE_PATTERN = re.compile(r'info\.value\.args == \("([a-z_]+)",\)')


def test_f3_7_error_codes_and_refusal_outcomes_are_pinned():
    assert {"refusal_invalid", "resume_invalid", "resume_stale"} <= rj.JOURNAL_ERROR_CODES
    assert rj.REFUSAL_OUTCOMES == ("recorded", "coalesced", "limit", "no_room")

    # Every JournalError code this file's own K-series tests observe from
    # record_refusal or open_recovery_journal(resume=...) is a member of the
    # closed set -- a scan of this file's own source, not a hand-maintained
    # list, so a future test can't silently name a code outside it.
    source_text = pathlib.Path(__file__).read_text(encoding="utf-8")
    observed = set(_JOURNAL_ERROR_CODE_PATTERN.findall(source_text))
    assert {
        "refusal_invalid", "resume_invalid", "resume_stale", "journal_held", "journal_closed",
        "journal_clock_invalid", "journal_divergence", "journal_write_failed",
        "capacity_admissions",
    } <= observed
    assert observed <= rj.JOURNAL_ERROR_CODES


def test_f3_8_inspect_never_calls_a_write_path(tmp_path, monkeypatch):
    """K6/K7 pin this rule only by content hashes staying unchanged. Here
    every write path inspect must never call is patched to explode, and
    inspect is run over three image shapes (ready, lag 1, an unpersisted
    recovery finding): none of them is ever reached.
    """
    # Build every image with the real methods first -- these write paths are
    # legitimately exercised while building fixtures -- then patch them to
    # explode only for the inspect calls below.
    ready = _k6_image_ready_lag0(tmp_path, monkeypatch)
    lag1 = _k6_image_lag1(tmp_path, monkeypatch)
    finding = _k6_image_recovery_finding_unpersisted(tmp_path, monkeypatch)

    def _boom(*args, **kwargs):
        raise AssertionError("inspect must never call this")

    monkeypatch.setattr(journal_store.JournalStore, "finish_open", _boom)
    monkeypatch.setattr(journal_store.JournalStore, "write_anchor", _boom)
    monkeypatch.setattr(journal_store.JournalStore, "persist_hold", _boom)
    monkeypatch.setattr(journal_store.JournalStore, "append", _boom)
    # recovery_journal imports plan_restart by name at module load, so the
    # bound copy in its own namespace is what must be patched to take effect.
    monkeypatch.setattr(rj, "plan_restart", _boom)

    ready_report = rj.inspect_recovery_journal(ready).report
    assert ready_report["verdict"] == "ready"
    lag1_report = rj.inspect_recovery_journal(lag1).report
    assert lag1_report["verdict"] == "ready"
    assert lag1_report["anchor"]["lag"] == 1
    finding_report = rj.inspect_recovery_journal(finding).report
    assert finding_report["verdict"] == "held"


def test_f3_8_a_wal_absent_full_size_image_gains_no_directory_entry(tmp_path, monkeypatch):
    directory = _k6_image_wal_absent_checkpointed(tmp_path, monkeypatch)
    before = set(os.listdir(directory))
    inspection = rj.inspect_recovery_journal(directory)
    assert inspection.report["verdict"] == "unverified"
    assert set(os.listdir(directory)) == before


def test_f3_9_wal_absent_db_shorter_than_page_size_opens_and_holds(tmp_path):
    """The WAL pre-check's other branch: WAL absent, but the DB is PRESENT
    and merely shorter than PAGE_SIZE (not absent, unlike K6's
    ``db_unlinked_no_wal``). ``_verify_open`` finds this before it ever
    connects, so the store opens (unlike the ``unverified`` wal_absent
    case), and no WAL is created.
    """
    directory, _clock, _ids, journal = make(tmp_path, "f3-9-short-db")
    journal.close()
    wal_path_of(directory).unlink(missing_ok=True)
    db_path = db_path_of(directory)
    assert db_path.stat().st_size >= journal_store.PAGE_SIZE
    with open(db_path, "r+b") as fh:
        fh.truncate(journal_store.PAGE_SIZE - 1)
    assert db_path.exists()
    assert db_path.stat().st_size < journal_store.PAGE_SIZE
    assert not wal_path_of(directory).exists()

    inspection = rj.inspect_recovery_journal(directory)
    report = inspection.report
    assert report["verdict"] == "held"
    assert report["finding"] == {"code": "journal_truncated", "scope": "recovery", "in_anchor": False}
    assert report["next_open"] == ["persist_hold"]
    assert not wal_path_of(directory).exists()  # opening never created a WAL


# === K10: front-door golden ===================================================


def _build_front_door_golden_records(directory) -> list:
    """14 records in 11 commits, exactly as tabulated under "Replay
    compatibility and goldens" in the plan. Built entirely through the live
    RecoveryJournal API, mirroring E16's ``_build_golden_records``."""
    ids = SeqIds()
    clock = SeqClock()
    bounds = jrd.JournalBounds(
        max_admissions=64, max_pending_fingerprints=1_024,
        ordinary_bytes=112 * 2**20, total_bytes=128 * 2**20,
    )
    journal = rj.create_recovery_journal(  # c1: genesis
        directory, bounds=bounds, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )
    firing = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    journal.admit(firing)  # c2: pair, admitted

    # c3: a no-group key (JSON parse failure).
    assert journal.record_refusal(_json_invalid_summary()) == "recorded"
    assert journal.record_refusal(_json_invalid_summary(b"still not json")) == "coalesced"

    # c4: 33 alerts, 1 Resolved.
    summary_c4 = _many_alerts_summary(33, 1)
    assert journal.record_refusal(summary_c4) == "recorded"
    # A re-render (a different body, same group/code/members): coalesced.
    resend = _many_alerts_summary(33, 1, extra={"commonAnnotations": {"summary": "resend"}})
    assert journal.record_refusal(resend) == "coalesced"

    # c5: the same group, 2 Resolved -- a membership change, a new key.
    summary_c5 = _many_alerts_summary(33, 2)
    assert journal.record_refusal(summary_c5) == "recorded"
    journal.close()

    journal = reopen(directory, clock, ids)  # c6: restart_recovery (boot 2)
    repeat = journal.admit(firing)  # c7: pair, suppressed, held
    assert repeat.result == "suppressed"
    journal.close()

    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="k10-operator", reason="restart-inspected")
    journal = rj.open_recovery_journal(  # c8: restart_recovery (boot 3); c9: operator_action
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    resolved = source(CG1_KEY, (PF, "resolved", (("A", "1"),)))
    reduced = journal.admit(resolved)  # c10: pair, pending_reduced, decision admitted
    assert reduced.result == "pending_reduced"
    assert reduced.decision == "admitted"

    # c11: the oversize key.
    assert journal.record_refusal(_oversize_summary(300_000)) == "recorded"
    journal.close()

    store = journal_store.JournalStore.open(directory)
    try:
        records = list(store.rows())
    finally:
        store.close()
    return records


# Pinned once, at golden-file generation time, by the finalizer: journal_
# reducer.state_digest/.head.record_digest/pending_digest/front_door_digest
# of journal_reducer.replay over the committed JSONL below. state_digest and
# head.record_digest are NOT reproducible from a fresh build (the restart
# records' wal_found.digest is a genuine per-run SQLite salt that then
# chains into every later record_digest); pending_digest and
# front_door_digest are, since neither depends on any record_digest.
_K10_STATE_DIGEST = "d582afc458233c80333f9d85d1ca8da49f5de206985f6bdded609a363a174d28"
_K10_HEAD_DIGEST = "62337c4c304b711c0c5341cdfcd91fe1a07f868e5e98db46b9a53b8c58bb264f"
_K10_PENDING_DIGEST = "c46d5a754d5ab9664e73e9db913e73c772e69c8ae2d0fd808f51886cadf6aae5"
_K10_FRONT_DOOR_DIGEST = "b1c826acaa092029b5418cf08990957d8787c497dcf8be8df7122f7d49f48452"

# The five leaves the rebuild comparator masks (critic 8e): the WAL's random
# salt in c6/c8's ``wal_found.digest``; the chain consequence on every
# record's ``prev_record_digest``/``record_digest``; c8's re-derived
# ``recovered.record_digest``; c9's re-derived ``inspected.record_digest``.
_RESTART_C6_INDEX = 6
_RESTART_C8_INDEX = 9
_OPERATOR_ACTION_C9_INDEX = 10


def _masked_envelope(record, index: int) -> dict:
    # ROOT-1: masking applies only from c6 on (see ``_assert_records_match_masked``);
    # records at indices 0-5 (commits c1-c5) are compared whole instead, so
    # ``prev_record_digest`` is left in place here rather than blanked
    # unconditionally.
    envelope = {
        "schema_version": jr.SCHEMA_VERSION,
        "journal_generation": record.position.journal_generation,
        "event_id": record.event_id, "event_seq": record.position.event_seq,
        "commit_seq": record.position.commit_seq, "commit_index": record.position.commit_index,
        "commit_size": record.position.commit_size, "event_type": record.event_type,
        "actor": record.actor, "boot_id": record.stamp.boot_id, "wall_time": record.stamp.wall_time,
        "mono_us": record.stamp.mono_us, "ids": jr.thaw(record.ids),
        "data": dict(jr.thaw(record.data)),
        "prev_record_digest": None,  # masked only for index >= _RESTART_C6_INDEX (below)
    }
    if index >= _RESTART_C6_INDEX:
        envelope["prev_record_digest"] = None
    else:
        envelope["prev_record_digest"] = record.position.prev_record_digest
    if index in (_RESTART_C6_INDEX, _RESTART_C8_INDEX):
        envelope["data"] = dict(envelope["data"])
        envelope["data"]["wal_found"] = dict(envelope["data"]["wal_found"] or {})
        if envelope["data"]["wal_found"]:
            envelope["data"]["wal_found"]["digest"] = None
    if index == _RESTART_C8_INDEX:
        envelope["data"]["recovered"] = dict(envelope["data"]["recovered"])
        envelope["data"]["recovered"]["record_digest"] = None
    if index == _OPERATOR_ACTION_C9_INDEX:
        envelope["data"]["inspected"] = dict(envelope["data"]["inspected"])
        envelope["data"]["inspected"]["record_digest"] = None
    return envelope


def _assert_records_match_masked(rebuilt: list, golden: list) -> None:
    # ROOT-1 (test-harness strengthening): records before c6 (indices 0-5,
    # commits c1-c5) are fully deterministic -- no WAL salt has entered the
    # chain yet -- so they are compared whole, including ``record_digest``
    # and ``prev_record_digest`` (via ``record.body``, which is what both are
    # derived from), not just through the masked envelope the chained
    # records (index >= 6) still need.
    assert len(rebuilt) == len(golden) == 14
    for index, (r, g) in enumerate(zip(rebuilt, golden)):
        if index < _RESTART_C6_INDEX:
            assert r.record_digest == g.record_digest, index
            assert r.body == g.body, index
        else:
            assert _masked_envelope(r, index) == _masked_envelope(g, index), index


def test_k10_front_door_golden_guard(tmp_path):
    lines = FRONT_DOOR_GOLDEN_PATH.read_text(encoding="ascii").splitlines()
    assert len(lines) == 14
    records = [jr.open_record(line.encode("ascii")) for line in lines]

    replayed = jrd.replay(records)
    assert jrd.state_digest(replayed) == _K10_STATE_DIGEST
    assert replayed.head.record_digest == _K10_HEAD_DIGEST
    assert jrd.pending_digest(replayed) == _K10_PENDING_DIGEST
    assert jrd.front_door_digest(replayed) == _K10_FRONT_DOOR_DIGEST


def test_k10_build_front_door_golden_records_reproduces_the_committed_golden_file(tmp_path):
    lines = FRONT_DOOR_GOLDEN_PATH.read_text(encoding="ascii").splitlines()
    golden = [jr.open_record(line.encode("ascii")) for line in lines]

    directory = new_dir(tmp_path, "k10-rebuild")
    rebuilt = _build_front_door_golden_records(directory)
    _assert_records_match_masked(rebuilt, golden)


def test_root1_rebuild_comparator_catches_pre_restart_corruption(tmp_path):
    """ROOT-1 (test-harness strengthening). Before the fix above,
    ``prev_record_digest`` was masked on every one of the 14 records, so a
    corruption of that field on a pre-c6 record (index 0-5, fully
    deterministic -- no WAL salt has entered the chain yet) would slip past
    the rebuild comparator silently. This flips one hex character of commit
    c2's first record (index 1) in a SCRATCH COPY of the golden's lines held
    only in this test -- the committed golden file on disk is never touched
    -- and shows the (fixed) comparator now catches it.
    """
    lines = FRONT_DOOR_GOLDEN_PATH.read_text(encoding="ascii").splitlines()
    assert len(lines) == 14

    def _flip_last_hex(match: re.Match) -> str:
        prefix, last = match.group(1), match.group(2)
        return f'"prev_record_digest":"{prefix}{"0" if last != "0" else "1"}"'

    corrupted_line = re.sub(
        r'"prev_record_digest":"([0-9a-f]{63})([0-9a-f])"', _flip_last_hex, lines[1], count=1,
    )
    assert corrupted_line != lines[1]
    corrupted_lines = list(lines)
    corrupted_lines[1] = corrupted_line

    # Still syntactically valid, canonical, non-zero hex64 -- it parses and
    # decodes cleanly through open_record; only the chain VALUE is wrong,
    # exactly what an index-0-5 whole-record comparison must now catch.
    corrupted_golden = [jr.open_record(line.encode("ascii")) for line in corrupted_lines]
    assert corrupted_golden[1].position.prev_record_digest != corrupted_golden[0].record_digest

    directory = new_dir(tmp_path, "root1-rebuild")
    rebuilt = _build_front_door_golden_records(directory)
    with pytest.raises(AssertionError):
        _assert_records_match_masked(rebuilt, corrupted_golden)


# === K11: rollback (an older binary meets a new type) ========================


def test_k11_older_binary_meets_a_front_door_type_as_process_hold(tmp_path, monkeypatch):
    directory, _clock, _ids, journal = make(tmp_path, "k11")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.record_refusal(_json_invalid_summary())
    journal.close()
    before = _file_snapshot(directory)

    old_validators = {k: v for k, v in jr._TYPE_VALIDATORS.items() if k[0] in jr.EVENT_TYPES}
    old_actors = {k: v for k, v in jr.TYPE_ACTORS.items() if k[0] in jr.EVENT_TYPES}
    assert set(old_validators) == {(t, 1) for t in jr.EVENT_TYPES}
    monkeypatch.setattr(jr, "_TYPE_VALIDATORS", old_validators)
    monkeypatch.setattr(jr, "TYPE_ACTORS", old_actors)

    opened = rj.open_recovery_journal(directory)
    try:
        assert opened.state == "held"
        assert opened.hold == ("journal_schema_unsupported", "process")
        assert opened.snapshot()["hold"]["persisted"] is False
    finally:
        opened.close()
    monkeypatch.undo()
    assert _file_snapshot(directory) == before

    # Restoring the real registry opens ready again.
    reopened = open_ready(directory)
    reopened.close()


def test_k11_older_binary_meets_a_resume_record_as_process_hold(tmp_path, monkeypatch):
    directory, clock, ids, journal = make(tmp_path, "k11-resume")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    reopen(directory, clock, ids).close()
    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="op", reason="restart-inspected")
    rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    ).close()

    before = _file_snapshot(directory)
    old_validators = {k: v for k, v in jr._TYPE_VALIDATORS.items() if k[0] in jr.EVENT_TYPES}
    old_actors = {k: v for k, v in jr.TYPE_ACTORS.items() if k[0] in jr.EVENT_TYPES}
    monkeypatch.setattr(jr, "_TYPE_VALIDATORS", old_validators)
    monkeypatch.setattr(jr, "TYPE_ACTORS", old_actors)

    opened = rj.open_recovery_journal(directory)
    try:
        assert opened.hold == ("journal_schema_unsupported", "process")
        assert opened.snapshot()["hold"]["persisted"] is False
    finally:
        opened.close()
    monkeypatch.undo()
    assert _file_snapshot(directory) == before


# === K11b: this binary meets a future schema_version =========================


def _replace_last_row(
    directory, event_seq: int, event_id: str, event_type: str, body: bytes, digest: str,
):
    # journal_events carries append-only triggers (see test_recovery_journal_
    # crash.py's E12 series): drop them for this one hand-signed UPDATE and
    # recreate them from their own stored SQL. Unlike that series' helper,
    # this keeps the WAL, so the image stays WAL-present as a real one is.
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        raw.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        triggers = raw.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name"
        ).fetchall()
        for name, _sql in triggers:
            raw.execute(f"DROP TRIGGER {name}")
        raw.execute(
            "UPDATE journal_events SET event_id=?, event_type=?, body=?, record_digest=? "
            "WHERE event_seq=?",
            (event_id, event_type, body, digest, event_seq),
        )
        for _name, sql in triggers:
            raw.execute(sql)
        raw.commit()
    finally:
        raw.close()


def _point_anchor_at(directory, record_digest: str) -> None:
    """Rewrite the newest anchor slot's head digest, as the future binary that
    wrote the replaced row would have anchored it."""
    path = anchor_path_of(directory)
    raw = path.read_bytes()
    bodies = journal_store._slot_bodies(raw)
    index = max(
        (i for i, body in enumerate(bodies) if body is not None),
        key=lambda i: bodies[i]["counter"],
    )
    body = dict(bodies[index], head=dict(bodies[index]["head"], record_digest=record_digest))
    slot = journal_store._encode_slot(body)
    offset = journal_store.ANCHOR_SLOT_OFFSETS[index]
    path.write_bytes(raw[:offset] + slot + raw[offset + len(slot):])


def _hand_build_schema_version_2(record) -> tuple[bytes, str]:
    """The last stored record, re-encoded with ``schema_version: 2`` and a
    freshly digested (but not otherwise re-signed) chain-tail."""
    envelope = {
        "schema_version": 2,
        "journal_generation": record.position.journal_generation,
        "event_id": record.event_id, "event_seq": record.position.event_seq,
        "commit_seq": record.position.commit_seq, "commit_index": record.position.commit_index,
        "commit_size": record.position.commit_size, "event_type": record.event_type,
        "actor": record.actor, "boot_id": record.stamp.boot_id, "wall_time": record.stamp.wall_time,
        "mono_us": record.stamp.mono_us, "ids": jr.thaw(record.ids), "data": jr.thaw(record.data),
        "prev_record_digest": record.position.prev_record_digest,
    }
    body = canonical_json(envelope, ascii_only=True)
    digest = jr._record_digest(body)
    return body, digest


@pytest.mark.parametrize(
    "build", ["restart_recovery", "capacity_hold", "ingress_refusal", "operator_action"],
)
def test_k11b_this_binary_meets_a_future_schema_version(tmp_path, build):
    if build == "capacity_hold":
        bounds = jrd.JournalBounds(
            max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
            total_bytes=128 * 2**20,
        )
        directory, _clock, _ids, journal = make(tmp_path, f"k11b-{build}", bounds=bounds)
        journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        with pytest.raises(rj.JournalError):
            journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        journal.close()
    elif build == "ingress_refusal":
        directory, _clock, _ids, journal = make(tmp_path, f"k11b-{build}")
        journal.record_refusal(_json_invalid_summary())
        journal.close()
    elif build == "restart_recovery":
        directory, clock, ids, journal = make(tmp_path, f"k11b-{build}")
        journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        journal.close()
        reopen(directory, clock, ids).close()
    else:  # operator_action
        directory, clock, ids, journal = make(tmp_path, f"k11b-{build}")
        journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        journal.close()
        reopen(directory, clock, ids).close()
        token = _resume_token(directory)
        resume = rj.ResumeRequest(token=token, operator="op", reason="restart-inspected")
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
        ).close()

    store = journal_store.JournalStore.open(directory)
    try:
        rows = list(store.rows())
    finally:
        store.close()
    last = rows[-1]
    body, digest = _hand_build_schema_version_2(last)
    _replace_last_row(
        directory, last.position.event_seq, last.event_id, last.event_type, body, digest,
    )
    _point_anchor_at(directory, digest)
    assert wal_path_of(directory).exists()
    before = _file_snapshot(directory)

    opened = rj.open_recovery_journal(directory)
    try:
        assert opened.state == "held"
        assert opened.hold == ("journal_schema_unsupported", "process")
        assert opened.snapshot()["hold"]["persisted"] is False
    finally:
        opened.close()
    assert _file_snapshot(directory) == before

    inspection = rj.inspect_recovery_journal(directory)
    assert inspection.report["verdict"] == "held"
    assert inspection.report["next_open"] == ["hold"]
    assert _file_snapshot(directory) == before


# === K12: closed-grammar audit over all seven types ==========================

_HEX = frozenset("0123456789abcdef")


def _hex64_ok(value: str) -> bool:
    return len(value) == 64 and all(c in _HEX for c in value)


def _k12_known_literals() -> frozenset:
    return (
        frozenset(jr.REGISTERED_EVENT_TYPES) | frozenset(jr.ACTORS) | frozenset(jr.DEDUPE_RESULTS)
        | frozenset(jr.ADMISSION_DECISIONS) | frozenset(jr.CAPACITY_CODES)
        | frozenset(jr.DISPATCH_HOLD_CODES) | frozenset(js.ALERT_STATUSES)
        | frozenset(js.PROVENANCE_KINDS) | frozenset(jr.INGRESS_REFUSAL_CODES_V1)
        | frozenset(jr.OPERATOR_ACTIONS) | frozenset(jr.RESUMABLE_HOLDS)
        | {
            jr.DEDUPE_RULE, jr.REFUSAL_RULE, jr.RESUME_RULE, "rj.journal.v1", "invalid", "set",
            "/notification",
        }
    )


def _walk_strings(node):
    if type(node) is dict:
        for value in node.values():
            yield from _walk_strings(value)
    elif type(node) is list:
        for item in node:
            yield from _walk_strings(item)
    elif type(node) is str:
        yield node


def _is_allowed_k12_string(value: str, known: frozenset) -> bool:
    if _hex64_ok(value):
        return True
    if value in known:
        return True
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value))


def test_k12_closed_grammar_audit_over_all_seven_types(tmp_path):
    bounds = jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    directory, clock, ids, journal = make(tmp_path, "k12", bounds=bounds)
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    with pytest.raises(rj.JournalError) as info:
        journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    assert info.value.args == ("capacity_admissions",)  # writes a capacity_hold record
    journal.record_refusal(_json_invalid_summary())
    journal.close()

    reopen(directory, clock, ids).close()  # boot 2: restart_recovery
    token = _resume_token(directory)
    resume = rj.ResumeRequest(token=token, operator="k12-op", reason="restart-inspected")
    journal = rj.open_recovery_journal(  # boot 3: restart_recovery, operator_action
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
    )
    journal.close()

    known = _k12_known_literals()
    store = journal_store.JournalStore.open(directory)
    try:
        seen_types = set()
        bad = []
        for record in store.rows():
            seen_types.add(record.event_type)
            envelope = json.loads(record.body)
            for value in _walk_strings(envelope):
                if not _is_allowed_k12_string(value, known):
                    bad.append((record.event_type, value))
        assert bad == []
        assert seen_types == set(jr.REGISTERED_EVENT_TYPES)
    finally:
        store.close()


# === K13: in-process crash images ============================================


def test_k13_crash_after_refusal_append_w10_resend_coalesced(tmp_path, monkeypatch):
    directory, _clock, _ids, journal = make(tmp_path, "k13-w10")
    image = tmp_path / "k13-w10-image"
    _crash_after_nth_call(monkeypatch, journal_store.JournalStore, "append", 1, directory, image)
    summary = _json_invalid_summary()
    with pytest.raises(SimulatedCrash):
        journal.record_refusal(summary)
    # The crash latched the live handle on its way out.
    assert journal.hold == ("journal_write_failed", "process")
    monkeypatch.undo()
    journal.close()

    opened = open_ready(image)
    try:
        assert opened.snapshot()["counts"]["admissions"] == 0
        assert opened.front_door_status()["refusals"]["recorded"] == 1  # exactly one record
        resend = opened.record_refusal(_json_invalid_summary(b"still not json"))
        assert resend == "coalesced"
    finally:
        opened.close()


def test_k13_crash_after_restart_commit_w11_old_token_stale(tmp_path, monkeypatch):
    directory, clock, ids, journal = make(tmp_path, "k13-w11")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    token = _resume_token(directory)

    image = tmp_path / "k13-w11-image"
    _crash_after_nth_call(monkeypatch, journal_store.JournalStore, "append", 1, directory, image)
    with pytest.raises(SimulatedCrash):
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
        )
    monkeypatch.undo()

    resume = rj.ResumeRequest(token=token, operator="op", reason="restart-inspected")
    with pytest.raises(rj.JournalError) as info:
        rj.open_recovery_journal(image, resume=resume)
    assert info.value.args == ("resume_stale",)


def test_k13_crash_after_resume_commit_w12_held_again(tmp_path, monkeypatch):
    directory, clock, ids, journal = make(tmp_path, "k13-w12")
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()
    reopen(directory, clock, ids).close()  # boot 2's restart, uneventful
    token = _resume_token(directory)

    image = tmp_path / "k13-w12-image"
    # On this lag-0 image the open's first anchor write is its restart's; the
    # crash pre-empts the second, the resume's: operator_action is committed
    # and its anchor never written.
    _crash_on_call(monkeypatch, journal_store.JournalStore, "_write_slot", 2, directory, image)
    resume = rj.ResumeRequest(token=token, operator="op", reason="restart-inspected")
    with pytest.raises(SimulatedCrash):
        rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids, resume=resume,
        )
    monkeypatch.undo()

    report = rj.inspect_recovery_journal(image).report
    assert report["verdict"] == "ready"
    assert report["anchor"]["lag"] == 1
    assert report["next_open"] == ["reanchor", "restart_recovery"]
    assert report["resumes"]["count"] == 1

    # The next open adopts it, re-anchors, then appends its own new
    # restart_recovery: held again.
    reopened = open_ready(image)
    try:
        assert "restart_recovery" in reopened.dispatch_holds
        assert reopened.resumed_this_boot is None
        rows = list(reopened._store.rows())
        assert [r.event_type for r in rows[-2:]] == ["operator_action", "restart_recovery"]
        assert rows[-1].data["anchor_lag"] == 1
    finally:
        reopened.close()


# === K14: concurrent admit and record_refusal serialize ======================


def test_k14_concurrent_admit_and_record_refusal_serialize(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "k14")
    n_admits = 8
    errors: list[BaseException] = []
    outcomes: list[str] = []
    lock = threading.Lock()
    # A distinct group per thread, so every refusal is a real commit that races.
    summaries = [
        ji.refusal_to_json(ji.sanitize_notification(_many_alerts_body(
            f'{{}}:{{alertname="k14-{i}", grafana_folder="ops"}}', 33, 0,
        )).refusal)
        for i in range(n_admits)
    ]
    assert len({jrd.refusal_key(summary) for summary in summaries}) == n_admits

    def admit_worker(i: int) -> None:
        try:
            journal.admit(source(CG1_KEY, (f"fp-{i:03d}", "firing", (("A", "1"),))))
        except BaseException as error:  # noqa: BLE001 - collected, never silently dropped
            with lock:
                errors.append(error)

    def refuse_worker(i: int) -> None:
        try:
            outcome = journal.record_refusal(summaries[i])
            with lock:
                outcomes.append(outcome)
        except BaseException as error:  # noqa: BLE001 - collected, never silently dropped
            with lock:
                errors.append(error)

    threads = [threading.Thread(target=admit_worker, args=(i,)) for i in range(n_admits)]
    threads += [threading.Thread(target=refuse_worker, args=(i,)) for i in range(n_admits)]
    for t in threads:
        t.start()
    # F3-15: a generous bound (30s) that only catches a hang -- a
    # lock-ordering regression between the journal lock and the spool/admit
    # path must not wedge the suite forever. Every thread's liveness is then
    # checked explicitly, so a straggler is a reported failure, not a quiet
    # join() that returns having waited nothing.
    for t in threads:
        t.join(timeout=30)
    still_alive = [t for t in threads if t.is_alive()]
    assert still_alive == []
    status = journal.front_door_status()
    journal.close()

    assert errors == []
    assert outcomes == ["recorded"] * n_admits
    assert status["refusals"]["recorded"] == n_admits
    assert status["refusals"]["this_boot"] == {"ingress_too_many_alerts": {"recorded": n_admits}}
    store = journal_store.JournalStore.open(directory)
    try:
        rows = list(store.rows())
    finally:
        store.close()
    arrival_seqs = sorted(
        record.data["arrival_seq"] for record in rows if record.event_type == "admission"
    )
    refusal_seqs = sorted(
        record.data["refusal_seq"] for record in rows if record.event_type == "ingress_refusal"
    )
    assert arrival_seqs == list(range(1, n_admits + 1))
    assert refusal_seqs == list(range(1, n_admits + 1))
    assert [record.position.event_seq for record in rows] == list(range(1, len(rows) + 1))
