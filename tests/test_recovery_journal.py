"""Shell tests for ``recovery_journal`` (unit 15, module 4; ticket 37 cases
D1-D14). Real SQLite and real syncs throughout, at most 450 (Implementer D's
budget); the count and wall time are recorded at teardown and never
asserted.

Scenario data mirrors ``test_journal_reducer.py``'s B1/B2 fixture matrix
(short synthetic ``groupKey`` strings, not the captured ones -- A9's golden
values are Implementer A's job, not this module's) but drives it through the
real shell: ``create_recovery_journal``/``open_recovery_journal``/``admit``.
"""

from __future__ import annotations

import ast
import errno
import json
import pathlib
import sqlite3
import threading
import time
import uuid

import pytest

from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import recovery_journal as rj
from tests.test_journal_reducer import reference_model

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE (Python >= 3.12)",
)

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent

CG1_KEY = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
CG2_KEY = '{}:{alertname="Service error rate is elevated", grafana_folder="demo2"}'
CG1 = js.source_group_digest(CG1_KEY)
CG2 = js.source_group_digest(CG2_KEY)

PF = "5e8d72dc87b1ff35"
PC = "6cd7e206a0716d2d"
PX = "8e2d9556f6c757b5"
PA = "f09facf2b8f5b694"
PB = "4396dcd5ddc23476"
PD = "4bde20aac01f95a2"
PE = "b3587dd72657d226"


# === Shared helpers ===========================================================


class SeqIds:
    """A deterministic ``id_factory``: canonical-uuid-shaped, strictly increasing."""

    def __init__(self, start: int = 1) -> None:
        self._n = start

    def __call__(self) -> str:
        value = f"{self._n:032x}"
        self._n += 1
        return f"{value[0:8]}-{value[8:12]}-{value[12:16]}-{value[16:20]}-{value[20:32]}"


class SeqClock:
    """Deterministic wall/mono clocks: each call advances by a fixed step."""

    def __init__(self) -> None:
        self._wall = 1_700_000_000_000_000_000
        self._mono = 1_000_000_000

    def wall(self) -> int:
        self._wall += 1_000_000_000
        return self._wall

    def mono(self) -> int:
        self._mono += 1_000_000
        return self._mono


def alerts(*members: tuple[str, str, tuple | None]) -> tuple[js.SourceAlert, ...]:
    return tuple(
        js.SourceAlert(fingerprint=fp, status=status, values=values, starts_at=None)
        for fp, status, values in members
    )


def source(group_key: str, *members, truncated: int | None = 0) -> js.SourceRecord:
    return js.SourceRecord(
        source_group=js.source_group_digest(group_key), alerts=alerts(*members),
        truncated_alerts=truncated, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )


def new_dir(tmp_path: pathlib.Path, name: str = "journal") -> pathlib.Path:
    directory = tmp_path / name
    directory.mkdir(mode=0o700)
    return directory


def make(tmp_path, name="journal", **kwargs):
    directory = new_dir(tmp_path, name)
    clock = SeqClock()
    ids = SeqIds()
    bounds = kwargs.pop("bounds", None)
    journal = rj.create_recovery_journal(
        directory, bounds=bounds or jrd.DEFAULT_BOUNDS, wall_clock=clock.wall,
        mono_clock=clock.mono, id_factory=ids, **kwargs,
    )
    return directory, clock, ids, journal


def reopen(directory, clock, ids):
    return rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )


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
    print(f"\n[test_recovery_journal] real syncs={counts['n']} wall={elapsed:.2f}s")


# === D1: create ==============================================================


def test_d1_create_is_ready_generation_1_no_dispatch_holds(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        assert j.state == "ready"
        snap = j.snapshot()
        assert snap["generation"] == 1
        assert snap["dispatch_holds"] == []
        a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
        receipt = j.admit(a)
        assert receipt.decision == "admitted"
        assert receipt.result == "admitted"
        # Every minted ID (journal_uuid, boot_id, event ids, admission_id) came
        # from the SeqIds factory: they are strictly increasing canonical uuids.
        assert receipt.admission_id
        uuid.UUID(receipt.admission_id)
        uuid.UUID(snap["journal_uuid"])
        uuid.UUID(snap["boot_id"])
    finally:
        j.close()


def _raise_runtime():
    raise RuntimeError("caller text that must not leak")


@pytest.mark.parametrize(
    "fault", ["id_factory_raises", "id_factory_invalid", "clock_raises", "genesis_refused"],
)
def test_d1_create_refused_before_any_write_is_journal_argument_and_leaves_no_file(
    tmp_path, monkeypatch, fault,
):
    # Genesis is built and verified before JournalStore.create, so a refusal
    # leaves nothing for an operator to remove: journal_argument, not
    # journal_create_failed.
    directory = new_dir(tmp_path)
    clock, ids = SeqClock(), SeqIds()
    kwargs = {"wall_clock": clock.wall, "mono_clock": clock.mono, "id_factory": ids}
    if fault == "id_factory_raises":
        kwargs["id_factory"] = _raise_runtime
    elif fault == "id_factory_invalid":
        kwargs["id_factory"] = lambda: "bad id with spaces"
    elif fault == "clock_raises":
        kwargs["wall_clock"] = _raise_runtime
    else:
        def refuse(_projection, _records):
            raise jrd.ReplayError("replay_mismatch")

        monkeypatch.setattr(rj, "verify_commit", refuse)
    with pytest.raises(rj.JournalError) as info:
        rj.create_recovery_journal(directory, **kwargs)
    error = info.value
    assert error.args == ("journal_argument",)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert list(directory.iterdir()) == []
    monkeypatch.undo()

    clock = SeqClock()
    rj.create_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=SeqIds(),
    ).close()


# === D2: fixtures through admit ==============================================


def test_d2_f01_identity_repeat_is_suppressed(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    try:
        a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
        first = j.admit(a)
        assert first.result == "admitted"
        second = j.admit(a)
        assert second.result == "suppressed"
        assert second.superseded == ()
        assert j.pending()[0].admission_id == first.admission_id
        assert j.snapshot()["counts"]["admissions"] == 2
    finally:
        j.close()
    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.pending()[0].admission_id == first.admission_id
    finally:
        reopened.close()


def test_d2_f02_changed_value_both_admit(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        line1 = source(CG1_KEY, (PF, "firing", (("A", "0.1144"), ("B", "1"))))
        line2 = source(CG1_KEY, (PF, "firing", (("A", "0.1957"), ("B", "1"))))
        first = j.admit(line1)
        assert first.result == "admitted"
        second = j.admit(line2)
        assert second.result == "pending_reduced"
        assert second.superseded == ((PF, first.admission_id),)
    finally:
        j.close()


def test_d2_f04_resolved_then_firing_reduces_to_latest_firing(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        line16 = source(
            CG1_KEY, (PF, "firing", (("A", "0.2"),)), (PC, "resolved", (("A", "0.1"),)),
            (PX, "resolved", (("A", "0.1"),)),
        )
        line18 = source(CG1_KEY, (PF, "firing", (("A", "0.18"),)))
        line20 = source(
            CG1_KEY, (PF, "firing", (("A", "0.27"),)), (PC, "firing", (("A", "0.13"),)),
            (PX, "firing", (("A", "0.14"),)),
        )
        step16 = j.admit(line16)
        assert step16.result == "admitted"
        step18 = j.admit(line18)
        assert step18.superseded == ((PF, step16.admission_id),)
        step20 = j.admit(line20)
        assert step20.superseded == (
            (PF, step18.admission_id), (PC, step16.admission_id), (PX, step16.admission_id),
        )
        pending = {entry.fingerprint: entry for entry in j.pending()}
        for fp in (PC, PF, PX):
            assert pending[fp].admission_id == step20.admission_id
            assert pending[fp].status == "firing"
    finally:
        j.close()


def test_d2_f06_omission_is_never_resolved(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        seed = source(
            CG1_KEY, (PF, "firing", (("A", "1"),)), (PC, "firing", (("A", "1"),)),
            (PX, "firing", (("A", "1"),)),
        )
        step_seed = j.admit(seed)
        j.admit(seed)  # suppressed repeat
        pf_only = source(CG1_KEY, (PF, "firing", (("A", "2"),)))
        step_pf = j.admit(pf_only)
        assert step_pf.superseded == ((PF, step_seed.admission_id),)
        pending = {entry.fingerprint: entry for entry in j.pending()}
        assert pending[PC].admission_id == step_seed.admission_id
        assert pending[PX].admission_id == step_seed.admission_id
        assert pending[PF].admission_id == step_pf.admission_id
    finally:
        j.close()


def test_d2_f07_mixed_groups_keep_separate_baselines(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        cg1 = source(
            CG1_KEY, (PF, "firing", (("A", "1"),)), (PC, "firing", (("A", "1"),)),
            (PX, "firing", (("A", "1"),)),
        )
        cg2 = source(
            CG2_KEY, (PB, "resolved", (("A", "0"),)), (PD, "resolved", (("A", "0"),)),
            (PE, "resolved", (("A", "0"),)), (PA, "resolved", (("A", "0"),)),
        )
        j.admit(cg1)
        step2 = j.admit(cg2)
        assert step2.result == "admitted"
        pending = {entry.fingerprint: entry for entry in j.pending()}
        assert set(pending) == {PC, PF, PX, PA, PB, PD, PE}
        assert pending[PC].source_group == CG1
        assert pending[PA].source_group == CG2
    finally:
        j.close()


def test_d2_cross_group_equal_tuple_is_admitted_not_suppressed(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        cg1_a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
        cg2_a = source(CG2_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
        first = j.admit(cg1_a)
        second = j.admit(cg2_a)
        assert second.result == "pending_reduced"
        assert second.superseded == ((PF, first.admission_id),)
        assert second.dedupe_key != first.dedupe_key or second.source_group != first.source_group
    finally:
        j.close()


def test_d2_q7_cross_group_reclaim(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        cg1_resolved = source(CG1_KEY, (PF, "resolved", (("A", "0"), ("B", "0"))))
        cg2_firing = source(CG2_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
        step1 = j.admit(cg1_resolved)
        step2 = j.admit(cg2_firing)
        assert step2.superseded == ((PF, step1.admission_id),)
        step3 = j.admit(cg1_resolved)
        assert step3.result == "suppressed"
        assert step3.superseded == ((PF, step2.admission_id),)
        pending = j.pending()
        assert len(pending) == 1
        assert pending[0].source_group == CG1
    finally:
        j.close()


# === D3: A/B/A/A, close, reopen, then A ======================================


def test_d3_worked_example_then_restart_then_a_is_suppressed_and_held(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    b = source(CG1_KEY, (PF, "firing", (("A", "2"), ("B", "1"))))
    step1 = j.admit(a)
    step2 = j.admit(b)
    assert step2.superseded == ((PF, step1.admission_id),)
    step3 = j.admit(a)
    assert step3.superseded == ((PF, step2.admission_id),)
    step4 = j.admit(a)
    assert step4.result == "suppressed"
    assert step4.decision == "admitted"
    j.close()

    reopened = reopen(directory, clock, ids)
    assert reopened.dispatch_holds == ("restart_recovery",)
    step5 = reopened.admit(a)
    assert step5.result == "suppressed"
    assert step5.decision == "held"
    assert step5.dispatch_holds == ("restart_recovery",)
    reopened.close()


# === D4: restart replay ======================================================


def test_d4_restart_replay_is_consistent_and_verified(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    b = source(CG2_KEY, (PC, "firing", (("A", "1"),)))
    j.admit(b)
    pre_close_snap = j.snapshot()
    pre_close_state_digest = pre_close_snap["state_digest"]
    pre_pending_digest = pre_close_snap["pending_digest"]
    pre_baselines = pre_close_snap["counts"]["source_groups"]
    pre_counts = pre_close_snap["counts"]
    j.close()

    reopened = reopen(directory, clock, ids)
    try:
        snap = reopened.snapshot()
        assert snap["verified_state_digest"] == pre_close_state_digest
        assert snap["pending_digest"] == pre_pending_digest
        assert snap["counts"]["source_groups"] == pre_baselines
        assert snap["counts"]["admissions"] == pre_counts["admissions"]
        assert snap["dispatch_holds"] == [{"code": "restart_recovery", "since_commit_seq": 4}]
        assert snap["anchor"]["lag_at_open"] == 0
    finally:
        reopened.close()


def test_d4_restart_records_recovered_head_lag_and_wal_found(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    pre_head = j.snapshot()["head"]
    old_boot = j.snapshot()["boot_id"]
    j.close()

    reopened = reopen(directory, clock, ids)
    try:
        new_boot = reopened.snapshot()["boot_id"]
        assert new_boot != old_boot
        # Exactly one restart_recovery record was appended: the head advanced
        # by exactly one commit and two events (position, generation) beyond
        # what was verified before the restart.
        snap = reopened.snapshot()
        assert snap["head"]["commit_seq"] == pre_head["commit_seq"] + 1
        assert snap["head"]["event_seq"] == pre_head["event_seq"] + 1
        # A real WAL-mode write (never checkpointed on close) leaves a
        # non-empty WAL file behind for this scenario -- an observed fact,
        # not a tautology.
        assert snap["wal_found"] is not None
        assert snap["wal_found"]["size"] > 0

        # The stored restart_recovery record itself must carry the real
        # anchor_lag/wal_found the shell observed, not just the snapshot's
        # own (independently derived) view of them.
        last_record = list(reopened._store.rows())[-1]
        assert last_record.event_type == "restart_recovery"
        assert last_record.data["anchor_lag"] == snap["anchor"]["lag_at_open"]
        if snap["wal_found"] is None:
            assert last_record.data["wal_found"] is None
        else:
            assert last_record.data["wal_found"] is not None
            assert dict(last_record.data["wal_found"]) == snap["wal_found"]
    finally:
        reopened.close()


def test_d4_restart_commit_order_is_commit_then_directory_then_anchor(tmp_path, monkeypatch):
    directory, clock, ids, j = make(tmp_path)
    j.close()

    order: list[str] = []
    real_commit_sql = journal_store.JournalStore._commit_sql
    real_sync_path = journal_store._sync_path
    real_write_slot = journal_store.JournalStore._write_slot

    def recording_commit_sql(self, records):
        order.append("commit")
        return real_commit_sql(self, records)

    def recording_sync_path(path):
        order.append("directory")
        return real_sync_path(path)

    def recording_write_slot(self, body):
        order.append("anchor")
        return real_write_slot(self, body)

    monkeypatch.setattr(journal_store.JournalStore, "_commit_sql", recording_commit_sql)
    monkeypatch.setattr(journal_store, "_sync_path", recording_sync_path)
    monkeypatch.setattr(journal_store.JournalStore, "_write_slot", recording_write_slot)

    reopened = reopen(directory, clock, ids)
    try:
        assert order == ["commit", "directory", "anchor"]
        assert reopened.state == "ready"
    finally:
        monkeypatch.undo()
        reopened.close()


def test_d4_restart_dispatch_hold_since_commit_seq_pins_to_the_first_restart(tmp_path):
    """``dispatch_holds`` never overwrites an already-active code (T4a): a
    second restart on a later reopen must not move ``restart_recovery``'s
    ``since_commit_seq`` forward to its own, later commit.
    """
    directory, clock, ids, j = make(tmp_path, "d4-pin")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()

    reopened_once = reopen(directory, clock, ids)
    first_holds = {
        h["code"]: h["since_commit_seq"] for h in reopened_once.snapshot()["dispatch_holds"]
    }
    first_commit_seq = first_holds["restart_recovery"]
    reopened_once.close()

    reopened_twice = reopen(directory, clock, ids)
    try:
        snap = reopened_twice.snapshot()
        holds = {h["code"]: h["since_commit_seq"] for h in snap["dispatch_holds"]}
        # The second restart really did write a later commit than the first.
        assert snap["head"]["commit_seq"] > first_commit_seq
        assert holds["restart_recovery"] == first_commit_seq
    finally:
        reopened_twice.close()


# === D5: capacity through small bounds =======================================


def _small_bounds(**overrides) -> jrd.JournalBounds:
    base = {
        "max_admissions": 3, "max_pending_fingerprints": 1_024,
        "ordinary_bytes": 112 * 2**20, "total_bytes": 128 * 2**20,
    }
    base.update(overrides)
    return jrd.JournalBounds(**base)


def test_d5_capacity_admissions_writes_one_hold_and_counts_refusals(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path, bounds=_small_bounds(max_admissions=3))
    try:
        for fp in (PF, PC, PX):
            receipt = j.admit(source(CG1_KEY, (fp, "firing", (("A", "1"),))))
            assert receipt.result == "admitted"
        extra = source(CG1_KEY, (PA, "firing", (("A", "1"),)))
        with pytest.raises(rj.JournalError) as info:
            j.admit(extra)
        assert info.value.code == "capacity_admissions"
        assert j.dispatch_holds == ("capacity_admissions",)
        refusals = j.snapshot()["refusals_this_boot"]
        assert refusals["capacity_admissions"]["count"] == 1
        first_head = j.snapshot()["head"]
        last_record = list(j._store.rows())[-1]
        assert last_record.event_type == "capacity_hold"
        assert last_record.data["refused_source_digest"] == js.source_digest(extra)

        with pytest.raises(rj.JournalError) as info2:
            j.admit(extra)
        assert info2.value.code == "capacity_admissions"
        # A second hold for the same code is never written.
        assert j.snapshot()["refusals_this_boot"]["capacity_admissions"]["count"] == 2
        assert j.dispatch_holds == ("capacity_admissions",)
        assert j.snapshot()["head"] == first_head
    finally:
        j.close()


def test_d5_suppressed_arrivals_count_against_admissions(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path, bounds=_small_bounds(max_admissions=2))
    try:
        a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
        j.admit(a)
        second = j.admit(a)
        assert second.result == "suppressed"
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert info.value.code == "capacity_admissions"
    finally:
        j.close()


def test_d5_pending_full_still_accepts_suppressed_and_existing_fingerprints(tmp_path):
    bounds = _small_bounds(max_admissions=1_000, max_pending_fingerprints=2)
    _directory, _clock, _ids, j = make(tmp_path, bounds=bounds)
    try:
        first = source(CG1_KEY, (PF, "firing", (("A", "1"),)), (PC, "firing", (("A", "1"),)))
        j.admit(first)  # exactly at the pending limit (2)
        changed = source(CG1_KEY, (PF, "firing", (("A", "2"),)), (PC, "firing", (("A", "2"),)))
        repeat = j.admit(changed)  # existing fingerprints only: never trips the pending cap
        assert repeat.result == "pending_reduced"
        assert len(repeat.superseded) == 2
        new_fp = source(CG1_KEY, (PX, "firing", (("A", "1"),)))
        with pytest.raises(rj.JournalError) as info:
            j.admit(new_fp)
        assert info.value.code == "capacity_pending"
    finally:
        j.close()


def test_d5_bytes_refusal(tmp_path):
    bounds = _small_bounds(max_admissions=1_000, max_pending_fingerprints=1_000, ordinary_bytes=1)
    _directory, _clock, _ids, j = make(tmp_path, bounds=bounds)
    try:
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "capacity_bytes"
        assert j.dispatch_holds == ("capacity_bytes",)
    finally:
        j.close()


def test_d5_reserve_too_small_for_capacity_hold_gives_journal_capacity_recovery(tmp_path):
    # Sized so genesis plus one admission pair (~3,600 B) fits under both
    # ordinary_bytes and total_bytes, but the capacity_hold record the
    # refusal would also write (~974 B more) overflows total_bytes.
    bounds = jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1_000, ordinary_bytes=4_000, total_bytes=4_500,
    )
    _directory, _clock, _ids, j = make(tmp_path, bounds=bounds)
    try:
        first = j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert first.result == "admitted"
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert info.value.code == "journal_capacity_recovery"
        assert j.state == "held"
        assert j.hold == ("journal_capacity_recovery", "process")
        with pytest.raises(rj.JournalError) as info2:
            j.admit(source(CG1_KEY, (PX, "firing", (("A", "1"),))))
        assert info2.value.code == "journal_held"
    finally:
        j.close()


def test_d5_reserve_too_small_for_restart_recovery_holds_at_open(tmp_path):
    # total_bytes barely fits genesis (949 B) but not a restart_recovery record.
    bounds = jrd.JournalBounds(
        max_admissions=10_000, max_pending_fingerprints=1_024, ordinary_bytes=100, total_bytes=1_000,
    )
    directory, clock, ids, j = make(tmp_path, bounds=bounds)
    j.close()
    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "held"
        assert reopened.hold == ("journal_capacity_recovery", "process")
        snap = reopened.snapshot()
        assert snap["hold"]["persisted"] is False  # process holds are never persisted
        with pytest.raises(rj.JournalError) as info:
            reopened.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_held"
    finally:
        reopened.close()


# === D6: latches ==============================================================


def _epoch_ns(year: int) -> int:
    import datetime

    stamp = datetime.datetime(year, 1, 1, tzinfo=datetime.UTC)
    return int(stamp.timestamp() * 1_000_000_000)


class ReplayIds:
    """Returns each of ``override`` in order, then falls back to ``base``."""

    def __init__(self, base, override):
        self._base = base
        self._override = list(override)

    def __call__(self) -> str:
        if self._override:
            return self._override.pop(0)
        return self._base()


@pytest.mark.parametrize("bad_clock", ["raises", "non_int", "negative"])
def test_d6_bad_wall_clock_latches_clock_invalid_nothing_written(tmp_path, bad_clock):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        pre = j.snapshot()
        if bad_clock == "raises":
            j._wall_clock = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        elif bad_clock == "non_int":
            j._wall_clock = lambda: "not-an-int"
        else:
            j._wall_clock = lambda: -1
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_clock_invalid"
        assert j.state == "held"
        assert j.hold == ("journal_clock_invalid", "process")
        post = j.snapshot()
        assert post["head"] is None  # held: projection fields are hidden
        assert j._projection.head.record_digest == pre["head"]["record_digest"]
        assert post["anchor"] == pre["anchor"]
    finally:
        j.close()


def test_d6_wall_clock_year_1999_latches_clock_invalid(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        j._wall_clock = lambda: _epoch_ns(1999)
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_clock_invalid"
        assert j.hold == ("journal_clock_invalid", "process")
    finally:
        j.close()


def test_d6_mono_clock_regression_latches_clock_invalid(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        j._mono_clock = lambda: 1
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert info.value.code == "journal_clock_invalid"
    finally:
        j.close()


def test_d6_mono_clock_beyond_max_seq_latches_clock_invalid_nothing_written(tmp_path):
    """(N1) ``_read_clock`` rejects ``mono_ns // 1_000 > MAX_SEQ``: exactly one
    microsecond past the bound reads as no clock reading at all, latching
    ``journal_clock_invalid`` with nothing written -- not a divergence from a
    record that later fails its own field bound at ``seal()`` time.
    """
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        pre = j.snapshot()
        j._mono_clock = lambda: (2**53) * 1_000  # mono_us == MAX_SEQ + 1
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_clock_invalid"
        assert j.hold == ("journal_clock_invalid", "process")
        post = j.snapshot()
        assert post["head"] is None  # held: projection fields are hidden
        assert j._projection.head.record_digest == pre["head"]["record_digest"]
        assert post["anchor"] == pre["anchor"]
    finally:
        j.close()


class _FlatAfterSecondClock:
    """Wall time advances every call; mono time advances for the first two
    calls (genesis, then the first admission) and then holds flat, so a
    second admission's ``mono_us`` reads exactly equal to the projection's
    current ``last_mono_us`` -- never greater.
    """

    def __init__(self) -> None:
        self._wall = 1_700_000_000_000_000_000
        self._mono = 1_000_000_000
        self._calls = 0

    def wall(self) -> int:
        self._wall += 1_000_000_000
        return self._wall

    def mono(self) -> int:
        self._calls += 1
        if self._calls <= 2:
            self._mono += 1_000_000
        return self._mono


def test_d6_equal_mono_us_within_a_boot_is_accepted(tmp_path):
    """(T4c) The admit-time clock gate is a strict ``<`` in both
    ``_read_admit_stamp`` and ``verify_commit``: an equal reading is current,
    documented semantics, not a rejection.
    """
    clock = _FlatAfterSecondClock()
    directory = new_dir(tmp_path, "d6-flat-mono")
    ids = SeqIds()
    j = rj.create_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )
    try:
        j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        first_mono = j._projection.last_mono_us
        second = j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert j._projection.last_mono_us == first_mono  # the clock never advanced
        assert second.result == "admitted"
        assert j.state == "ready"
    finally:
        j.close()


def test_d6_id_factory_invalid_id_gives_journal_divergence(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        j._id_factory = lambda: "bad id with spaces"
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_divergence"
        assert j.hold == ("journal_divergence", "process")
    finally:
        j.close()


def test_d6_id_factory_raising_gives_a_clean_journal_divergence(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        j._id_factory = _raise_runtime
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        error = info.value
        assert error.args == ("journal_divergence",)
        assert error.__cause__ is None
        assert error.__context__ is None
        assert j.hold == ("journal_divergence", "process")
    finally:
        j.close()


def test_d6_id_factory_reuses_existing_event_id_gives_process_divergence(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    first = j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    pre = j.snapshot()
    fresh_id = ids()
    j._id_factory = ReplayIds(ids, [first.admission_id, fresh_id])
    with pytest.raises(rj.JournalError) as info:
        j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    assert info.value.code == "journal_divergence"
    post = j.snapshot()
    assert post["head"] is None  # held: projection fields are hidden
    assert j._projection.head.record_digest == pre["head"]["record_digest"]
    assert post["anchor"] == pre["anchor"]
    j.close()

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "ready"
        assert reopened.snapshot()["counts"]["admissions"] == 1
    finally:
        reopened.close()


def test_d6_id_factory_returns_same_id_twice_gives_process_divergence(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        pre_head = j._projection.head
        fixed = str(uuid.uuid4())
        j._id_factory = lambda: fixed  # admission_id and dedupe_event_id mint equal
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_divergence"
        assert j.hold == ("journal_divergence", "process")
        assert j._projection.head == pre_head
    finally:
        j.close()


# === D7: commit failures ======================================================


def test_d7_authorizer_denial_gives_write_failed_then_reopen_ready_repeat_admitted(tmp_path):
    directory, clock, ids, j = make(tmp_path)

    def deny_insert(action, arg1, _arg2, _arg3, _arg4):
        if action == sqlite3.SQLITE_INSERT and arg1 == "journal_events":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    pre_head = j._projection.head
    pre_state_digest = jrd.state_digest(j._projection)
    j._store._connection.set_authorizer(deny_insert)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    with pytest.raises(rj.JournalError) as info:
        j.admit(a)
    assert info.value.code == "journal_write_failed"
    assert j.state == "held"
    assert j.hold == ("journal_write_failed", "process")
    # I2: a failed append must leave the projection exactly as it was.
    assert j._projection.head == pre_head
    assert jrd.state_digest(j._projection) == pre_state_digest
    j.close()

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "ready"
        receipt = reopened.admit(a)
        assert receipt.result == "admitted"
    finally:
        reopened.close()


def test_d7_commit_sql_raising_after_commit_latches_reopen_retains_repeat_suppressed(
    tmp_path, monkeypatch,
):
    directory, clock, ids, j = make(tmp_path)
    real_commit_sql = journal_store.JournalStore._commit_sql

    def crashing_commit_sql(self, records):
        real_commit_sql(self, records)
        raise RuntimeError("crash after commit, before the anchor write")

    monkeypatch.setattr(journal_store.JournalStore, "_commit_sql", crashing_commit_sql)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    with pytest.raises(rj.JournalError) as info:
        j.admit(a)
    assert info.value.code == "journal_write_failed"
    monkeypatch.undo()
    j.close()

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "ready"
        assert reopened.snapshot()["counts"]["admissions"] == 1
        assert reopened.snapshot()["anchor"]["lag_at_open"] == 1
        repeat = reopened.admit(a)
        assert repeat.result == "suppressed"
    finally:
        reopened.close()


def test_d7_find_duplicate_non_conflict_store_error_latches_write_failed(tmp_path, monkeypatch):
    """(T4b) ``_commit`` maps a ``find_duplicate`` ``StoreError`` by its own
    code: only ``store_event_conflict`` reads as ``journal_divergence``; any
    other ``StoreError`` (e.g. the underlying SELECT itself failing) is
    ``journal_write_failed``.
    """
    _directory, _clock, _ids, j = make(tmp_path, "d7-find-duplicate")
    try:
        def failing_find_duplicate(self, records):
            raise journal_store.StoreError("store_write_failed")

        monkeypatch.setattr(journal_store.JournalStore, "find_duplicate", failing_find_duplicate)
        with pytest.raises(rj.JournalError) as info:
            j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_write_failed"
        assert j.hold == ("journal_write_failed", "process")
    finally:
        monkeypatch.undo()
        j.close()


# === D8: anchor-sync failure ==================================================


def test_d8_anchor_sync_failure_gives_write_failed_reopen_lag1_suppresses_repeat(
    tmp_path, monkeypatch,
):
    # A same-process test cannot observe a torn-but-visible pwrite the way a
    # real crash would (the OS still shows the bytes on a same-process
    # re-read), so the write itself -- not just its sync -- is what fails
    # here; C8/E14 (store- and crash-level) cover the sync-specific path.
    directory, clock, ids, j = make(tmp_path)
    real_pwrite = journal_store.os.pwrite
    calls = {"n": 0}

    def failing_pwrite(fd, data, offset):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(errno.EIO, "simulated anchor write failure")
        return real_pwrite(fd, data, offset)

    monkeypatch.setattr(journal_store.os, "pwrite", failing_pwrite)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    with pytest.raises(rj.JournalError) as info:
        j.admit(a)
    assert info.value.code == "journal_write_failed"
    monkeypatch.undo()
    j.close()

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "ready"
        snap = reopened.snapshot()
        assert snap["anchor"]["lag_at_open"] == 1
        assert snap["counts"]["admissions"] == 1
        last_record = list(reopened._store.rows())[-1]
        assert last_record.event_type == "restart_recovery"
        assert last_record.data["anchor_lag"] == 1
        assert last_record.data["anchor_lag"] == snap["anchor"]["lag_at_open"]
        if snap["wal_found"] is None:
            assert last_record.data["wal_found"] is None
        else:
            assert last_record.data["wal_found"] is not None
            assert dict(last_record.data["wal_found"]) == snap["wal_found"]
        repeat = reopened.admit(a)
        assert repeat.result == "suppressed"
    finally:
        reopened.close()


# === D9: held handles =========================================================

_PROJECTION_KEYS = (
    "journal_uuid", "generation", "boot_id", "head", "dispatch_holds", "counts",
    "bytes", "bounds", "verified_state_digest", "pending_digest", "state_digest",
)


def test_d9_recovery_hold_gives_held_recovery_readable_snapshot_null_fields(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    (directory / journal_store.DB_FILENAME).unlink()  # DB absent, anchor still valid

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "held"
        assert reopened.hold == ("journal_truncated", "recovery")
        snap = reopened.snapshot()
        assert snap["hold"] == {
            "code": "journal_truncated", "scope": "recovery", "persisted": True,
            "sqlite_error": None,
        }
        for key in _PROJECTION_KEYS:
            assert snap[key] is None, key
        json.dumps(snap)
        assert reopened.pending() == ()
        with pytest.raises(rj.JournalError) as info:
            reopened.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert info.value.code == "journal_held"
    finally:
        reopened.close()


def test_d9_process_hold_gives_held_process(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    j.close()
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA user_version=2")
        raw.commit()
    finally:
        raw.close()

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "held"
        assert reopened.hold == ("journal_schema_unsupported", "process")
        assert reopened.snapshot()["hold"]["persisted"] is False
        with pytest.raises(rj.JournalError) as info:
            reopened.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_held"
    finally:
        reopened.close()


def test_d9_hold_latched_after_a_ready_open_hides_every_projection_field(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "ready"
        assert reopened.dispatch_holds == ("restart_recovery",)
        assert reopened.pending() != ()
        reopened._wall_clock = lambda: -1
        with pytest.raises(rj.JournalError):
            reopened.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert reopened.hold == ("journal_clock_invalid", "process")
        snap = reopened.snapshot()
        for key in _PROJECTION_KEYS:
            assert snap[key] is None, key
        assert snap["anchor"]["lag_at_open"] == 0
        json.dumps(snap)
        assert reopened.pending() == ()
        assert reopened.dispatch_holds == ()
    finally:
        reopened.close()


# === D10: concurrent admits ===================================================


def test_d10_concurrent_admits_are_serialized_and_contiguous(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    results_lock = threading.Lock()
    receipts: list = []
    errors: list = []

    def worker(n: int) -> None:
        for i in range(5):
            src = source(CG1_KEY, (f"fp-{n}-{i}", "firing", (("A", "1"),)))
            try:
                receipt = j.admit(src)
            except Exception as error:  # noqa: BLE001 - captured for the assertion below.
                with results_lock:
                    errors.append(error)
                continue
            with results_lock:
                receipts.append(receipt)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    j.close()

    assert errors == []
    assert len(receipts) == 40
    assert sorted(r.arrival_seq for r in receipts) == list(range(1, 41))
    assert sorted(r.commit_seq for r in receipts) == list(range(2, 42))
    all_event_seqs = sorted(seq for r in receipts for seq in r.event_seqs)
    assert all_event_seqs == list(range(2, 82))

    reopened = reopen(directory, clock, ids)
    try:
        assert reopened.state == "ready"
        assert reopened.snapshot()["counts"]["admissions"] == 40
    finally:
        reopened.close()


# === N2: state/hold/dispatch_holds take the journal lock ======================


@pytest.mark.parametrize("attr,expected", [
    ("state", "ready"), ("hold", None), ("dispatch_holds", ()),
])
def test_n2_state_hold_and_dispatch_holds_block_while_the_lock_is_held(tmp_path, attr, expected):
    """(N2) The snapshot's own lock-taking is already covered elsewhere;
    ``state``/``hold``/``dispatch_holds`` are the three read-only properties
    that now take ``self._lock`` too (previously only ``snapshot`` did),
    fixed alongside ``_state()`` becoming an internal, already-locked helper.
    """
    _directory, _clock, _ids, j = make(tmp_path, f"n2-{attr}")
    try:
        holder_acquired = threading.Event()
        release_holder = threading.Event()

        def hold_the_lock() -> None:
            with j._lock:
                holder_acquired.set()
                release_holder.wait(5)

        holder = threading.Thread(target=hold_the_lock)
        holder.start()
        assert holder_acquired.wait(5)

        reader_done = threading.Event()
        result: dict[str, object] = {}

        def read_attr() -> None:
            result["value"] = getattr(j, attr)
            reader_done.set()

        reader = threading.Thread(target=read_attr)
        reader.start()
        try:
            # Bounded, deterministic: while the lock is held the read must
            # not have completed yet -- it must be blocked on the lock, not
            # racing ahead of it.
            assert not reader_done.wait(0.2)
        finally:
            release_holder.set()
        holder.join(5)

        assert reader_done.wait(5)
        reader.join(5)
        assert result["value"] == expected
    finally:
        j.close()


# === D11: snapshot key set and content discipline ============================


_SNAPSHOT_KEYS = frozenset({
    "state", "hold", "journal_uuid", "generation", "boot_id", "head", "anchor", "wal_found",
    "dispatch_holds", "counts", "bytes", "bounds", "refusals_this_boot",
    "verified_state_digest", "pending_digest", "state_digest",
})


def test_d11_snapshot_has_exactly_its_key_set_and_no_source_content(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        distinctive_fp = "distinctivefingerprint12345"
        j.admit(source(CG1_KEY, (distinctive_fp, "firing", (("A", "1"),))))
        snap = j.snapshot()
        assert set(snap.keys()) == _SNAPSHOT_KEYS
        assert snap["state"] in ("ready", "held", "closed")
        assert snap["hold"] is None
        for entry in snap["dispatch_holds"]:
            assert set(entry.keys()) == {"code", "since_commit_seq"}
        blob = json.dumps(snap)  # plain JSON types only: no default= fallback
        assert distinctive_fp not in blob
        assert CG1_KEY not in blob
    finally:
        j.close()


def test_d11_every_code_in_snapshot_comes_from_a_closed_set(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path, bounds=_small_bounds(max_admissions=1))
    try:
        j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        with pytest.raises(rj.JournalError):
            j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        snap = j.snapshot()
        assert snap["hold"] is None  # capacity refusals never latch a journal hold
        for entry in snap["dispatch_holds"]:
            in_recovery = entry["code"] in journal_store.RECOVERY_HOLD_CODES
            in_dispatch = entry["code"] == "restart_recovery" or entry["code"] in jr.CAPACITY_CODES
            assert in_recovery or in_dispatch
        for code in snap["refusals_this_boot"]:
            assert code in jr.CAPACITY_CODES
    finally:
        j.close()


# === D13: AST checks (import allowlist) ======================================

MODULE_PATH = REPOSITORY / "grafana_jsm_sandbox" / "recovery_journal.py"
ALLOWED_TOP_LEVEL_IMPORTS = frozenset({
    "__future__", "dataclasses", "threading", "time", "uuid", "collections", "pathlib", "types",
})


def _module_ast() -> ast.Module:
    text = MODULE_PATH.read_text(encoding="utf-8")
    return ast.parse(text, filename=str(MODULE_PATH))


def test_d13_imports_match_the_exact_allowlist():
    tree = _module_ast()
    top_level_names: set[str] = set()
    from_imports: set[tuple[int, str, tuple[str, ...]]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = tuple(sorted(alias.name for alias in node.names))
            from_imports.add((node.level, module, names))
            if node.level == 0:
                top_level_names.add((module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            target = node.func
            is_dunder_import = isinstance(target, ast.Name) and target.id == "__import__"
            is_importlib = isinstance(target, ast.Attribute) and target.attr == "import_module"
            assert not is_dunder_import and not is_importlib, "dynamic import call found"

    assert top_level_names == ALLOWED_TOP_LEVEL_IMPORTS
    assert (0, "__future__", ("annotations",)) in from_imports
    assert (0, "collections.abc", ("Callable",)) in from_imports
    assert (0, "pathlib", ("Path",)) in from_imports
    assert (0, "types", ("MappingProxyType",)) in from_imports
    banned = {"sqlite3", "os", "fcntl", "socket", "subprocess", "http"}
    assert banned.isdisjoint(top_level_names)
    for level, module, _names in from_imports:
        assert level in (0, 1)
        if level == 1:
            assert module in ("journal_records", "journal_reducer", "journal_source", "journal_store")


def test_d13_except_bodies_only_assign_or_pass_and_never_raise():
    # The module's discipline: an except body only records what happened, and
    # the fresh error is raised after the try, so no JournalError carries a
    # wrapped exception in __context__. A BaseException is never caught.
    tree = _module_ast()
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) >= 5
    for handler in handlers:
        assert handler.type is not None, f"bare except at line {handler.lineno}"
        caught = ast.unparse(handler.type)
        assert "BaseException" not in caught, f"BaseException caught at line {handler.lineno}"
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                f"except body has a {type(statement).__name__} at line {statement.lineno}"
            )
        for inner in ast.walk(handler):
            assert not isinstance(inner, ast.Raise), f"raise inside except at line {inner.lineno}"


# === D14: duplicate at the shell seam (critic 9) =============================


def test_d14_commit_with_resealed_duplicate_plan_returns_stored_event_seqs(tmp_path):
    _directory, _clock, _ids, j = make(tmp_path)
    try:
        a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
        j.admit(a)
        pre_head = j.snapshot()["head"]
        pre_state_digest = j.snapshot()["state_digest"]
        pre_counter = j.snapshot()["anchor"]["counter"]

        stored = list(j._store.rows())
        admission_row = next(r for r in stored if r.event_type == "admission")
        dedupe_row = next(r for r in stored if r.event_type == "dedupe_decision")

        head = j._projection.head
        admission_position = jr.Position(
            journal_generation=1, event_seq=head.event_seq + 1, commit_seq=head.commit_seq + 1,
            commit_index=0, commit_size=2, prev_record_digest=head.record_digest,
        )
        stamp = j._read_admit_stamp()
        resealed_admission = jr.seal(
            jr.Draft(
                event_id=admission_row.event_id, event_type=admission_row.event_type,
                actor=admission_row.actor, ids=admission_row.ids, data=admission_row.data,
            ),
            admission_position, stamp,
        )
        dedupe_position = jr.Position(
            journal_generation=1, event_seq=admission_position.event_seq + 1,
            commit_seq=admission_position.commit_seq, commit_index=1, commit_size=2,
            prev_record_digest=resealed_admission.record_digest,
        )
        resealed_dedupe = jr.seal(
            jr.Draft(
                event_id=dedupe_row.event_id, event_type=dedupe_row.event_type,
                actor=dedupe_row.actor, ids=dedupe_row.ids, data=dedupe_row.data,
            ),
            dedupe_position, stamp,
        )

        plan = jrd.Plan(records=(resealed_admission, resealed_dedupe), charge=0, outcome={})
        event_seqs = j._commit(plan, sync_directory=False)
        assert event_seqs == (
            admission_row.position.event_seq, dedupe_row.position.event_seq,
        )
        post = j.snapshot()
        assert post["head"] == pre_head
        assert post["state_digest"] == pre_state_digest
        assert post["anchor"]["counter"] == pre_counter

        followup = j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert followup.result != "suppressed"
    finally:
        j.close()


# === D12: shell-level property against B's reference model ==================

_D12_GROUPS = (CG1_KEY, CG2_KEY, '{}:{alertname="third"}')
_D12_FINGERPRINTS = (PF, PC, PX, PA)
_D12_VALUE_POOL = ("0", "1", "0.1", "2", None)


def _random_source(rng, groups, fingerprints):
    group_key = rng.choice(groups)
    count = rng.randint(1, len(fingerprints))
    chosen = sorted(rng.sample(fingerprints, count))
    members = []
    for fp in chosen:
        status = rng.choice(("firing", "resolved"))
        values = None if rng.random() < 0.2 else (("A", rng.choice(_D12_VALUE_POOL)),)
        members.append((fp, status, values))
    truncated = rng.choice((0, 0, 0, 2, None))
    return source(group_key, *members, truncated=truncated)


def _live_state(j):
    baselines = {
        group: (b.admission_id, b.dedupe_key, b.complete)
        for group, b in j._projection.baselines.items()
    }
    pending = {
        fp: (e.admission_id, e.source_group, e.status, e.values)
        for fp, e in j._projection.pending.items()
    }
    return baselines, pending


def test_d12_shell_level_property_against_reference_model(tmp_path):
    import random

    started = time.monotonic()
    for seed in range(3):
        rng = random.Random(seed)
        directory, clock, ids, j = make(tmp_path, name=f"journal-d12-{seed}")
        arrivals: list = []
        reopen_at = set(rng.sample(range(15), 2))
        for step in range(15):
            if step in reopen_at:
                j.close()
                j = reopen(directory, clock, ids)
                continue
            src = _random_source(rng, _D12_GROUPS, _D12_FINGERPRINTS)
            try:
                receipt = j.admit(src)
            except rj.JournalError:
                continue
            arrivals.append((receipt.admission_id, src))
            live_baselines, live_pending = _live_state(j)
            ref_baselines, ref_pending = reference_model(arrivals)
            assert live_baselines == ref_baselines, (seed, step)
            assert live_pending == ref_pending, (seed, step)

        # A fresh replay of the raw stored history, computed independently of
        # the live shell, must land on the same digests (no reopen needed).
        replayed = jrd.replay(j._store.rows())
        assert jrd.state_digest(replayed) == j.snapshot()["state_digest"]
        assert jrd.pending_digest(replayed) == j.snapshot()["pending_digest"]
        j.close()
    elapsed = time.monotonic() - started
    print(f"\n[test_recovery_journal] d12 wall={elapsed:.2f}s")


# === D15: open never leaves the store (and its lock) behind ===================


class _Crash(BaseException):
    """A stand-in for a process crash: no ``except Exception`` clause catches it."""


def _assert_unlocked_and_ready(directory):
    # A store left open by a failed open still holds the flock, so this open
    # would raise journal_locked. A uuid4 factory never collides with SeqIds.
    opened = rj.open_recovery_journal(directory)
    try:
        assert opened.state == "ready"
    finally:
        opened.close()


def test_d15_finish_open_failure_gives_held_process_open_failed(tmp_path, monkeypatch):
    directory, clock, ids, j = make(tmp_path)
    j.close()

    def failing_finish_open(self):
        raise journal_store.StoreError("store_write_failed")

    monkeypatch.setattr(journal_store.JournalStore, "finish_open", failing_finish_open)
    held = reopen(directory, clock, ids)
    monkeypatch.undo()
    try:
        assert held.hold == ("journal_open_failed", "process")
        assert held.snapshot()["hold"]["persisted"] is False
        _assert_unlocked_and_ready(directory)  # the held handle already released it
    finally:
        held.close()


def test_d15_id_factory_raising_for_the_open_boot_id_gives_held_divergence(tmp_path):
    directory, clock, _ids, j = make(tmp_path)
    j.close()
    held = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=_raise_runtime,
    )
    try:
        assert held.hold == ("journal_divergence", "process")
        assert held.snapshot()["hold"]["persisted"] is False
        _assert_unlocked_and_ready(directory)
    finally:
        held.close()


def test_d15_a_store_finding_outranks_a_failed_boot_id_mint(tmp_path):
    """(T4d) Per ``_open_verified``'s own docstring: a store or replay
    finding outranks a failed boot-id mint, which ALONE is only ever a
    process ``journal_divergence``. Force both at once (anchor missing, and
    the id_factory also raising) and confirm the store's real recovery
    finding is what gets reported.
    """
    directory, clock, _ids, j = make(tmp_path, "d15-precedence")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    (directory / journal_store.ANCHOR_FILENAME).unlink()

    held = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=_raise_runtime,
    )
    try:
        assert held.hold == ("journal_anchor_missing", "recovery")
    finally:
        held.close()


def test_d15_id_factory_raising_in_restart_recovery_latches_divergence(tmp_path):
    directory, clock, ids, j = make(tmp_path)
    j.close()
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] == 2:  # the restart_recovery boot id
            _raise_runtime()
        return ids()

    held = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=factory,
    )
    try:
        assert held.hold == ("journal_divergence", "process")
    finally:
        held.close()
    _assert_unlocked_and_ready(directory)


def test_d15_base_exception_in_the_restart_append_propagates_and_releases_the_lock(
    tmp_path, monkeypatch,
):
    directory, clock, ids, j = make(tmp_path)
    j.close()

    def crashing_append(self, records, *, sync_directory=False):
        raise _Crash

    monkeypatch.setattr(journal_store.JournalStore, "append", crashing_append)
    with pytest.raises(_Crash):
        reopen(directory, clock, ids)
    monkeypatch.undo()
    _assert_unlocked_and_ready(directory)
