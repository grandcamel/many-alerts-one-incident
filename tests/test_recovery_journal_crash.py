"""Crash and power-loss recovery tests for the recovery-journal shell
(ticket 37, unit 15b, module 4; Tester E, cases E1-E18).

Crash images: a fixture patches one named seam (``_commit_sql``,
``_write_slot``, ``_full_sync``, ``persist_hold`` or ``write_anchor``) to
``shutil.copytree`` the live directory into an image and raise
``SimulatedCrash`` -- a ``BaseException``, never caught by any
``except Exception``/``except (sqlite3.Error, OSError, StoreError)`` clause
in the source, matching what a real process crash looks like to the shell.
The image is the kernel-visible state at that instant: writes that already
happened are visible even though nothing was closed or synced. Power-loss
variants edit that image afterwards (a slot kept, reverted or torn; the WAL
trimmed to its pre-transaction size or garbage-appended); WAL frames are
located by parsing frame headers (the "db size after commit" field marks a
commit frame -- critic q6), never by a fixed index, and named by the commit
they belong to.

Real SQLite and real syncs throughout; at most 500 (Tester E's budget). The
count and wall time are recorded at teardown and never asserted, matching
test_journal_store.py/test_recovery_journal.py.
"""

from __future__ import annotations

import dataclasses
import errno
import fcntl
import os
import select
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import recovery_journal as rj
from tests.test_recovery_journal import (
    CG1_KEY,
    PC,
    PF,
    PX,
    SeqClock,
    SeqIds,
    make,
    new_dir,
    reopen,
    source,
)

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE "
    "(Python >= 3.12)",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"
GOLDEN_PATH = DATA_DIR / "recovery_journal_v1_golden.jsonl"


class SimulatedCrash(BaseException):
    """Raised by a patched seam right after it snapshots the live directory.

    A ``BaseException``, not an ``Exception``: it must fall through every
    ``except Exception``/``except (sqlite3.Error, OSError, StoreError)``
    clause in the source exactly like a real process crash would, and only
    the source's own ``except BaseException`` re-raise (recovery_journal's
    ``_commit``) or bare ``finally`` (journal_store's ``_guarded_write`` /
    ``_locked``) may observe it.
    """


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
    print(f"\n[test_recovery_journal_crash] real syncs={counts['n']} wall={elapsed:.2f}s")


# === Crash-image helpers ======================================================


def snapshot(directory: Path, image: Path) -> Path:
    shutil.copytree(directory, image)
    return image


def file_bytes(directory: Path, names: tuple[str, ...]) -> dict[str, bytes | None]:
    result: dict[str, bytes | None] = {}
    for name in names:
        path = directory / name
        result[name] = path.read_bytes() if path.exists() else None
    return result


def wal_path_of(directory: Path) -> Path:
    return directory / journal_store.WAL_FILENAME


def db_path_of(directory: Path) -> Path:
    return directory / journal_store.DB_FILENAME


def anchor_path_of(directory: Path) -> Path:
    return directory / journal_store.ANCHOR_FILENAME


def _crash_on_call(monkeypatch, target, name: str, n: int, directory: Path, image: Path):
    """Patch ``target.name`` so its n-th call snapshots ``directory`` into
    ``image`` and raises ``SimulatedCrash``; earlier calls run for real."""
    real_fn = getattr(target, name)
    state = {"n": 0}

    def wrapper(*args, **kwargs):
        state["n"] += 1
        if state["n"] == n:
            snapshot(directory, image)
            raise SimulatedCrash
        return real_fn(*args, **kwargs)

    monkeypatch.setattr(target, name, wrapper)
    return state


def _crashing_commit_sql_before_commit(directory: Path, image: Path):
    """A ``_commit_sql`` that runs BEGIN and every INSERT for real (so the WAL
    carries frames with no valid commit frame), then crashes before COMMIT."""

    def wrapper(self, records):
        cursor = self._connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        for record in records:
            cursor.execute(journal_store._INSERT_SQL, journal_store._row_params(record))
        snapshot(directory, image)
        raise SimulatedCrash

    return wrapper


def _torn_pwrite(monkeypatch, directory: Path, image: Path, torn_bytes: int = 16):
    """Patch ``os.pwrite`` (as ``journal_store`` calls it) so its NEXT call
    writes only the first ``torn_bytes`` of the slot -- magic and length, well
    short of the checksum regardless of payload size, so the slot can never
    look intact by accident -- snapshots, then crashes. A genuinely torn
    physical write, not merely an interrupted one. (A naive "first half of
    1024 bytes" cut can accidentally still include a small payload's full
    magic+length+payload+checksum, since the untouched tail is already zero
    from the anchor's initial ftruncate -- that looked like a clean write.)"""
    real_pwrite = journal_store.os.pwrite

    def wrapper(fd, data, offset):
        real_pwrite(fd, data[:torn_bytes], offset)
        snapshot(directory, image)
        raise SimulatedCrash

    monkeypatch.setattr(journal_store.os, "pwrite", wrapper)


def open_ready(directory: Path):
    # A real (uuid4-based) id_factory: a fresh SeqIds() would restart at
    # "000...01" and collide with ids already stored under this directory's
    # own (also SeqIds-seeded) history, wrongly latching journal_divergence.
    journal = rj.open_recovery_journal(directory)
    assert journal.state == "ready", journal.snapshot()
    return journal


def open_held(directory: Path):
    journal = rj.open_recovery_journal(directory)
    assert journal.state == "held", journal.snapshot()
    return journal


# === WAL frame parsing (critic q6): located by header, named by commit ======

_WAL_HEADER_SIZE = 32
_FRAME_HEADER_SIZE = 24
_WAL_MAGIC_BIG = 0x377F0683
_WAL_MAGIC_LITTLE = 0x377F0682


def _wal_layout(wal_bytes: bytes) -> int:
    # Every WAL header/frame integer is big-endian on disk regardless of host
    # byte order; the magic number's low bit only selects the checksum
    # algorithm (native vs. byte-swapped), not the field byte order.
    magic = struct.unpack(">I", wal_bytes[0:4])[0]
    if magic not in (_WAL_MAGIC_BIG, _WAL_MAGIC_LITTLE):
        raise AssertionError(f"unrecognized WAL magic {magic:#x}")
    return struct.unpack(">I", wal_bytes[8:12])[0]


def wal_frames(wal_bytes: bytes) -> list[dict]:
    """Frame descriptors in file order. ``is_commit`` is the "db size after
    commit" field -- nonzero only on the last frame of a transaction, the
    commit marker -- never a fixed frame index."""
    if len(wal_bytes) < _WAL_HEADER_SIZE:
        return []
    page_size = _wal_layout(wal_bytes)
    frame_size = _FRAME_HEADER_SIZE + page_size
    frames = []
    offset = _WAL_HEADER_SIZE
    while offset + frame_size <= len(wal_bytes):
        header = wal_bytes[offset:offset + _FRAME_HEADER_SIZE]
        db_size_after_commit = struct.unpack(">I", header[4:8])[0]
        frames.append({
            "start": offset, "data_start": offset + _FRAME_HEADER_SIZE,
            "end": offset + frame_size, "is_commit": db_size_after_commit != 0,
        })
        offset += frame_size
    return frames


def commit_groups(frames: list[dict]) -> list[list[dict]]:
    """Complete frame groups, each named by its position (1st, 2nd, ...) in
    the file -- never by a fixed frame index -- and each ending in exactly
    one commit frame. A trailing incomplete group is dropped, matching what
    SQLite's own WAL recovery ignores."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    for frame in frames:
        current.append(frame)
        if frame["is_commit"]:
            groups.append(current)
            current = []
    return groups


def flip_byte_in_group(wal_bytes: bytes, group: list[dict], frame_index: int = 0) -> bytes:
    data = bytearray(wal_bytes)
    pos = group[frame_index]["data_start"] + 8
    data[pos] ^= 0xFF
    return bytes(data)


def trim_last_frame(wal_bytes: bytes, frames: list[dict]) -> bytes:
    return wal_bytes[: frames[-1]["start"]]


# === Shared scenario builders ==================================================


def _primed(tmp_path: Path, name: str):
    """genesis + one fully-acknowledged admission, ready for one more."""
    directory, clock, ids, j = make(tmp_path, name=name)
    prior = source(CG1_KEY, (PC, "firing", (("A", "1"),)))
    first = j.admit(prior)
    return directory, clock, ids, j, first


def _n_admissions(tmp_path: Path, name: str, n: int):
    directory, _clock, _ids, j = make(tmp_path, name=name)
    fps = [PF, PC, PX, "fp-4", "fp-5", "fp-6", "fp-7"]
    receipts = [j.admit(source(CG1_KEY, (fps[i], "firing", (("A", "1"),)))) for i in range(n)]
    j.close()
    return directory, receipts


# === E1 (C2): crash in _commit_sql before COMMIT =============================


def test_e1_crash_before_commit_admission_absent_repeat_admitted(tmp_path, monkeypatch):
    directory, _clock, _ids, j = make(tmp_path, name="e1-live")
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    image = tmp_path / "e1-image"

    monkeypatch.setattr(
        journal_store.JournalStore, "_commit_sql",
        _crashing_commit_sql_before_commit(directory, image),
    )
    with pytest.raises(SimulatedCrash):
        j.admit(a)
    monkeypatch.undo()
    j.close()

    opened = open_ready(image)
    try:
        assert opened.snapshot()["counts"]["admissions"] == 0
        assert opened.pending() == ()
        repeat = opened.admit(a)
        assert repeat.result == "admitted"
    finally:
        opened.close()


# === E2 (C3): crash after COMMIT, before pwrite ===============================


def _e2_image(tmp_path, monkeypatch, name: str):
    directory, _clock, _ids, j, prior = _primed(tmp_path, name)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    image = tmp_path / f"{name}-image"

    _crash_on_call(monkeypatch, journal_store.JournalStore, "_write_slot", 1, directory, image)
    with pytest.raises(SimulatedCrash):
        j.admit(a)
    monkeypatch.undo()
    j.close()
    return image, a, prior


def test_e2_crash_after_commit_before_pwrite_ready_lag1_repeat_suppressed(tmp_path, monkeypatch):
    image, a, prior = _e2_image(tmp_path, monkeypatch, "e2")
    opened = open_ready(image)
    try:
        snap = opened.snapshot()
        assert snap["anchor"]["lag_at_open"] == 1
        assert snap["counts"]["admissions"] == 2  # committed, though never ACKed
        assert any(entry.admission_id == prior.admission_id for entry in opened.pending())
        assert any(entry.fingerprint == PF for entry in opened.pending())
        repeat = opened.admit(a)
        assert repeat.result == "suppressed"
    finally:
        opened.close()


# === E3 (C4): anchor slot torn / reverted / kept (crash before its sync) =====


def _e3_image(tmp_path, monkeypatch, name: str, corruption: str):
    directory, _clock, _ids, j, _prior = _primed(tmp_path, name)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    image = tmp_path / f"{name}-image"

    anchor_before = anchor_path_of(directory).read_bytes()
    next_counter = j._store.anchor.counter + 1
    offset = journal_store.ANCHOR_SLOT_OFFSETS[next_counter % 2]
    pre_write_slot = anchor_before[offset:offset + journal_store.ANCHOR_SLOT_BYTES]

    _crash_on_call(monkeypatch, journal_store, "_full_sync", 1, directory, image)
    with pytest.raises(SimulatedCrash):
        j.admit(a)
    monkeypatch.undo()
    j.close()

    anchor_bytes = bytearray(anchor_path_of(image).read_bytes())
    if corruption == "reverted":
        anchor_bytes[offset:offset + journal_store.ANCHOR_SLOT_BYTES] = pre_write_slot
    elif corruption == "torn":
        anchor_bytes[offset + 20] ^= 0xFF
    elif corruption != "kept":
        raise AssertionError(corruption)
    anchor_path_of(image).write_bytes(bytes(anchor_bytes))
    return image, a


@pytest.mark.parametrize("corruption,expected_lag", [("torn", 1), ("reverted", 1), ("kept", 0)])
def test_e3_anchor_slot_torn_reverted_or_kept(tmp_path, monkeypatch, corruption, expected_lag):
    image, a = _e3_image(tmp_path, monkeypatch, f"e3-{corruption}", corruption)
    opened = open_ready(image)
    try:
        assert opened.snapshot()["anchor"]["lag_at_open"] == expected_lag
        repeat = opened.admit(a)
        assert repeat.result == "suppressed"
    finally:
        opened.close()


# === E4 (C5): image taken after admit() returns ===============================


def test_e4_image_after_admit_returns_ready_lag0_repeat_suppressed(tmp_path):
    directory, _clock, _ids, j, _prior = _primed(tmp_path, "e4")
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    image = tmp_path / "e4-image"
    snapshot(directory, image)
    j.close()

    opened = open_ready(image)
    try:
        assert opened.snapshot()["anchor"]["lag_at_open"] == 0
        repeat = opened.admit(a)
        assert repeat.result == "suppressed"
    finally:
        opened.close()


# === E5 (C10): crash in create ================================================


def test_e5_crash_before_anchor_gives_anchor_missing_then_exists(tmp_path, monkeypatch):
    directory = new_dir(tmp_path, "e5a")
    image = tmp_path / "e5a-image"
    _crash_on_call(monkeypatch, journal_store, "_full_sync", 1, directory, image)
    with pytest.raises(SimulatedCrash):
        rj.create_recovery_journal(
            directory, id_factory=SeqIds(), wall_clock=SeqClock().wall, mono_clock=SeqClock().mono,
        )
    monkeypatch.undo()

    assert not anchor_path_of(image).exists()
    assert db_path_of(image).exists()
    opened = open_held(image)
    try:
        assert opened.hold == ("journal_anchor_missing", "recovery")
    finally:
        opened.close()

    with pytest.raises(rj.JournalError) as info:
        rj.create_recovery_journal(
            image, id_factory=SeqIds(), wall_clock=SeqClock().wall, mono_clock=SeqClock().mono,
        )
    assert info.value.code == "journal_exists"


def test_e5_torn_anchor_at_create_gives_anchor_invalid(tmp_path, monkeypatch):
    directory = new_dir(tmp_path, "e5b")
    image = tmp_path / "e5b-image"
    _torn_pwrite(monkeypatch, directory, image)
    with pytest.raises(SimulatedCrash):
        rj.create_recovery_journal(
            directory, id_factory=SeqIds(), wall_clock=SeqClock().wall, mono_clock=SeqClock().mono,
        )
    monkeypatch.undo()

    opened = open_held(image)
    try:
        assert opened.hold == ("journal_anchor_invalid", "recovery")
    finally:
        opened.close()


# === E6: two-crash cases on the E2 image ======================================


def _e6_base_image(tmp_path, name: str, monkeypatch):
    image, _a, prior = _e2_image(tmp_path, monkeypatch, name)
    return image, prior


def _second_crash_and_reopen(base_image: Path, second_image: Path, prior, monkeypatch, patch):
    """Open ``base_image`` with ``patch`` applied (crashing, snapshotting
    into ``second_image``); then a plain final reopen of ``second_image``
    must succeed ready, with the prior admission still present."""
    patch()
    with pytest.raises(SimulatedCrash):
        rj.open_recovery_journal(base_image)
    monkeypatch.undo()

    final = open_ready(second_image)
    try:
        snap = final.snapshot()
        assert snap["anchor"]["lag_at_open"] <= 1
        assert any(entry.admission_id == prior.admission_id for entry in final.pending())
    finally:
        final.close()


def test_e6_two_crash_after_reanchor_before_restart_commit(tmp_path, monkeypatch):
    base_image, prior = _e6_base_image(tmp_path, "e6i", monkeypatch)
    second_image = tmp_path / "e6i-second"

    def patch():
        _crash_on_call(
            monkeypatch, journal_store.JournalStore, "_commit_sql", 1, base_image, second_image,
        )

    _second_crash_and_reopen(base_image, second_image, prior, monkeypatch, patch)


def test_e6_two_crash_after_restart_commit_before_directory_sync(tmp_path, monkeypatch):
    base_image, prior = _e6_base_image(tmp_path, "e6ii", monkeypatch)
    second_image = tmp_path / "e6ii-second"

    def patch():
        # call 1 = the re-anchor's own _full_sync (must run for real);
        # call 2 = the restart commit's directory sync.
        _crash_on_call(monkeypatch, journal_store, "_full_sync", 2, base_image, second_image)

    _second_crash_and_reopen(base_image, second_image, prior, monkeypatch, patch)


def test_e6_two_crash_after_directory_sync_before_its_anchor(tmp_path, monkeypatch):
    base_image, prior = _e6_base_image(tmp_path, "e6iii", monkeypatch)
    second_image = tmp_path / "e6iii-second"

    def patch():
        # call 1 = re-anchor's _write_slot (real); call 2 = restart's own anchor write (crash).
        _crash_on_call(
            monkeypatch, journal_store.JournalStore, "_write_slot", 2, base_image, second_image,
        )

    _second_crash_and_reopen(base_image, second_image, prior, monkeypatch, patch)


def test_e6_two_crash_mid_reanchor_pwrite(tmp_path, monkeypatch):
    base_image, prior = _e6_base_image(tmp_path, "e6iv", monkeypatch)
    second_image = tmp_path / "e6iv-second"

    def patch():
        _torn_pwrite(monkeypatch, base_image, second_image)

    _second_crash_and_reopen(base_image, second_image, prior, monkeypatch, patch)


# === E7: two-crash during hold persistence ====================================


def _e8a_image(tmp_path, name: str):
    """A fresh ``journal_truncated`` image (defined in full in the E8
    section below): the last anchored admission commit's WAL frame is
    flipped. Reproduced as a minimal local builder so E7 does not depend on
    E8's test ordering."""
    directory, _receipts = _n_admissions(tmp_path, name, 3)
    wal_bytes = wal_path_of(directory).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path_of(directory).write_bytes(flip_byte_in_group(wal_bytes, groups[-1]))
    return directory


def test_e7_two_crash_during_hold_persistence(tmp_path, monkeypatch):
    """E7 (C13). A crash between ``persist_hold``'s two slot writes leaves the
    hold in the newest slot only. Every later open must call ``persist_hold``
    again (the store writes only the still-missing slot, or returns False
    once both carry it), so a half-written hold is completed rather than
    taken as fully persisted; see test_journal_store.py's
    ``test_c13_crash_between_hold_slots_is_completed_by_the_next_persist``.

    This drives the plan's own two-crash method (E8a image; crash after the
    first hold slot, then again, torn, on the still-missing second slot),
    then a clean open that completes it.
    """
    directory = _e8a_image(tmp_path, "e7")
    image1 = tmp_path / "e7-image1"

    _crash_on_call(monkeypatch, journal_store.JournalStore, "_write_slot", 2, directory, image1)
    with pytest.raises(SimulatedCrash):
        rj.open_recovery_journal(directory)
    monkeypatch.undo()

    bodies = journal_store._slot_bodies(anchor_path_of(image1).read_bytes())
    held_slots = [body for body in bodies if body is not None and body.get("hold") is not None]
    assert len(held_slots) == 1, "setup assumption: exactly one hold slot after the first crash"
    code = held_slots[0]["hold"]["code"]

    image2 = tmp_path / "e7-image2"
    _torn_pwrite(monkeypatch, image1, image2)
    with pytest.raises(SimulatedCrash):
        # Expected (plan): the shell retries persist_hold, which starts
        # writing the still-missing second slot and is torn mid-write.
        rj.open_recovery_journal(image1)
    monkeypatch.undo()

    final = open_held(image2)
    try:
        assert final.hold == (code, "recovery")
    finally:
        final.close()
    final_bodies = journal_store._slot_bodies(anchor_path_of(image2).read_bytes())
    held = [body for body in final_bodies if body is not None and body.get("hold") is not None]
    assert len(held) == 2, "the half-written hold was never completed by a later open"


# === E8: torn WAL, by commit (critic 5) =======================================


def test_e8a_torn_last_anchored_commit_gives_truncated(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e8a", 2)
    wal_bytes = wal_path_of(directory).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path_of(directory).write_bytes(flip_byte_in_group(wal_bytes, groups[-1]))

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
    finally:
        opened.close()


def test_e8b_torn_genesis_frame_gives_truncated_from_empty_presentation(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e8b", 1)
    wal_bytes = wal_path_of(directory).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path_of(directory).write_bytes(flip_byte_in_group(wal_bytes, groups[0]))

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
    finally:
        opened.close()


def test_e8c_torn_unanchored_lag1_commit_gives_ready_lag0(tmp_path, monkeypatch):
    image, a, _prior = _e2_image(tmp_path, monkeypatch, "e8c")
    wal_bytes = wal_path_of(image).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    damaged = flip_byte_in_group(wal_bytes, groups[-1])  # the unanchored (lag-1) commit
    wal_path_of(image).write_bytes(damaged)
    expected_digest = journal_store._wal_found(wal_path_of(image)).digest

    opened = open_ready(image)
    try:
        snap = opened.snapshot()
        assert snap["anchor"]["lag_at_open"] == 0
        assert snap["wal_found"]["digest"] == expected_digest
        # The damaged, unanchored admission is gone: a repeat is freshly admitted.
        repeat = opened.admit(a)
        assert repeat.result == "admitted"
    finally:
        opened.close()


def test_e8d_trim_wal_by_one_frame_gives_truncated(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e8d", 2)
    wal_bytes = wal_path_of(directory).read_bytes()
    frames = wal_frames(wal_bytes)
    wal_path_of(directory).write_bytes(trim_last_frame(wal_bytes, frames))

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
    finally:
        opened.close()


def test_e8e_garbage_appended_gives_ready_wal_found_records_it(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e8e", 1)
    wal_bytes = wal_path_of(directory).read_bytes()
    garbled = wal_bytes + b"\xde\xad\xbe\xef" * 32
    wal_path_of(directory).write_bytes(garbled)
    expected = journal_store._wal_found(wal_path_of(directory))

    opened = open_ready(directory)
    try:
        snap = opened.snapshot()
        assert snap["wal_found"] == {"size": expected.size, "digest": expected.digest}
    finally:
        opened.close()


def test_e8f_deleted_wal_before_autocheckpoint_gives_truncated(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e8f", 1)
    wal_path_of(directory).unlink()

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
    finally:
        opened.close()


# === E9: stale restore =========================================================


def test_e9_stale_restore_gives_truncated_then_sticky(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e9")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    stale = tmp_path / "e9-stale"
    snapshot(directory, stale)  # DB + WAL at k (its anchor is unused below)

    j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    j.admit(source(CG1_KEY, (PX, "firing", (("A", "1"),))))
    j.close()
    good_db = db_path_of(directory).read_bytes()
    good_wal = wal_path_of(directory).read_bytes()

    # Restore the stale DB+WAL (from k), keeping the newer (k+m) anchor.
    db_path_of(directory).write_bytes(db_path_of(stale).read_bytes())
    wal_path_of(directory).write_bytes(wal_path_of(stale).read_bytes())

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
        assert opened.snapshot()["anchor"]["lag_at_open"] == -2  # head two commits below
    finally:
        opened.close()

    # Restoring the good files afterwards stays held: the anchor is sticky.
    db_path_of(directory).write_bytes(good_db)
    wal_path_of(directory).write_bytes(good_wal)
    reopened = open_held(directory)
    try:
        assert reopened.hold == ("journal_truncated", "recovery")
        assert reopened.snapshot()["anchor"]["lag_at_open"] is None  # SQLite never opened
    finally:
        reopened.close()


# === E10: anchor mismatch variants =============================================


def test_e10_older_anchor_newer_db_gives_tail_unverified(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e10a")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    old_anchor = anchor_path_of(directory).read_bytes()
    j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    j.admit(source(CG1_KEY, (PX, "firing", (("A", "1"),))))  # >= 2 commits ahead of old_anchor
    j.close()
    anchor_path_of(directory).write_bytes(old_anchor)

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_tail_unverified", "recovery")
        assert opened.snapshot()["anchor"]["lag_at_open"] == 2
    finally:
        opened.close()


def test_e10_foreign_anchor_gives_identity_mismatch(tmp_path):
    directory_a, _clock_a, _ids_a, j_a = make(tmp_path, name="e10b-a")
    j_a.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j_a.close()
    # A real (uuid4-based) id_factory for B: make()'s own SeqIds() always
    # restarts at "000...01", which would give A and B the SAME journal_uuid.
    directory_b = new_dir(tmp_path, "e10b-b")
    j_b = rj.create_recovery_journal(directory_b)
    j_b.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j_b.close()

    anchor_path_of(directory_a).write_bytes(anchor_path_of(directory_b).read_bytes())

    opened = open_held(directory_a)
    try:
        assert opened.hold == ("journal_identity_mismatch", "recovery")
    finally:
        opened.close()


def test_e10_deleted_anchor_gives_anchor_missing(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e10c")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    anchor_path_of(directory).unlink()

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_anchor_missing", "recovery")
    finally:
        opened.close()


def test_e10_forked_same_uuid_anchor_gives_anchor_conflict(tmp_path):
    """Fork A and B from a common genesis (same journal_uuid), then diverge
    them identically in shape but not content: each reopens once (its own
    restart_recovery) and admits one different source. A's and B's heads then
    sit at the same (commit_seq, event_seq, generation) but with different
    record_digest. Overwriting B's anchor with A's makes step 11's "record at
    anchor.event_seq" check find B's real record at that position -- it
    exists, so this is not journal_truncated/_tail_unverified -- but with the
    wrong digest: journal_anchor_conflict (critic 14), not a silent ready
    open.
    """
    directory_a, clock_a, ids_a, j_a = make(tmp_path, name="e10g1-a")
    j_a.close()
    directory_b = tmp_path / "e10g1-b"
    snapshot(directory_a, directory_b)  # B starts as a byte-identical fork of A

    reopened_a = reopen(directory_a, clock_a, ids_a)
    reopened_a.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    reopened_a.close()

    # A different deterministic id sequence for B, so every minted id (and
    # therefore every record's content and digest) differs from A's.
    clock_b, ids_b = SeqClock(), SeqIds(start=1_000)
    reopened_b = reopen(directory_b, clock_b, ids_b)
    reopened_b.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    reopened_b.close()

    anchor_path_of(directory_b).write_bytes(anchor_path_of(directory_a).read_bytes())

    opened = open_held(directory_b)
    try:
        assert opened.hold == ("journal_anchor_conflict", "recovery")
    finally:
        opened.close()


# === T3: the other three anchor-agreement checks at open =======================
#
# ``_replay_finding``'s ``anchor_record_ok`` compares four fields of the real
# record found at ``anchor.event_seq`` against the anchor itself: commit_seq,
# "is the last record of its commit" (commit_index == commit_size - 1),
# record_digest (already covered by the forked-uuid case above) and
# generation. Each test below forges exactly one of the other three via a
# hand-built anchor slot (mirroring the ``_encode_slot`` technique the E16/E18
# golden-guard tests already use), leaving the rest naming the real record
# exactly -- so only the one comparison under test can fail.


def _write_forged_anchor_slot(
    directory: Path, *, journal_uuid: str, event_seq: int, commit_seq: int, generation: int,
    record_digest: str,
) -> None:
    """Overwrite the newest anchor slot (offset 0 -- the same "counter: 2,
    slot 0" trick E16/E18 use) with a hand-built body naming the given head
    fields, structurally valid but not required to match any real record.
    """
    body = {
        "counter": 2, "format": journal_store.ANCHOR_FORMAT, "journal_uuid": journal_uuid,
        "head": {
            "commit_seq": commit_seq, "event_seq": event_seq,
            "generation": generation, "record_digest": record_digest,
        },
        "hold": None,
    }
    slot = journal_store._encode_slot(body)
    with open(anchor_path_of(directory), "r+b") as handle:
        handle.seek(journal_store.ANCHOR_SLOT_OFFSETS[0])
        handle.write(slot)


def test_e10_anchor_names_the_right_event_seq_but_a_different_generation(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e10h-generation")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    dedupe = list(j._store.rows())[-1]  # the true head: last record of its commit
    journal_uuid = j._projection.journal_uuid
    j.close()

    _write_forged_anchor_slot(
        directory, journal_uuid=journal_uuid, event_seq=dedupe.position.event_seq,
        commit_seq=dedupe.position.commit_seq, generation=dedupe.position.journal_generation + 1,
        record_digest=dedupe.record_digest,
    )
    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_anchor_conflict", "recovery")
    finally:
        opened.close()


def test_e10_anchor_names_an_event_seq_that_is_not_the_last_of_its_commit(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e10h-not-last")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    rows = list(j._store.rows())
    admission = next(r for r in rows if r.event_type == "admission")
    journal_uuid = j._projection.journal_uuid
    j.close()

    # The admission record's own commit_seq/generation/digest are all real
    # and correct -- only its event_seq is not the LAST of its (2-record)
    # commit, which is exactly what this anchor claims it is.
    _write_forged_anchor_slot(
        directory, journal_uuid=journal_uuid, event_seq=admission.position.event_seq,
        commit_seq=admission.position.commit_seq,
        generation=admission.position.journal_generation, record_digest=admission.record_digest,
    )
    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_anchor_conflict", "recovery")
    finally:
        opened.close()


def test_e10_anchor_names_a_commit_seq_that_disagrees_with_its_record(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e10h-commit-seq")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    dedupe = list(j._store.rows())[-1]  # the true head
    journal_uuid = j._projection.journal_uuid
    j.close()

    # event_seq, generation and digest all name the real head record exactly;
    # only commit_seq is off by one (kept a step ahead of the true head's own
    # commit_seq is refused earlier as journal_truncated/tail_unverified --
    # one step BEHIND keeps lag == 1, so this reaches anchor_record_ok).
    _write_forged_anchor_slot(
        directory, journal_uuid=journal_uuid, event_seq=dedupe.position.event_seq,
        commit_seq=dedupe.position.commit_seq - 1,
        generation=dedupe.position.journal_generation, record_digest=dedupe.record_digest,
    )
    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_anchor_conflict", "recovery")
    finally:
        opened.close()


# === E11: body damage in the main file (post-checkpoint) ======================


def _checkpoint(directory: Path) -> None:
    """Checkpoint the WAL into the main file with a RAW connection: the
    journal itself never checkpoints on close (no-checkpoint-on-close)."""
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        raw.close()


def test_e11_unresigned_flip_in_decision_admitted_gives_record_invalid(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e11a")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    _checkpoint(directory)

    data = bytearray(db_path_of(directory).read_bytes())
    needle = b'"decision":"admitted"'
    offset = data.index(needle)
    data[offset + 1] ^= 0xFF  # inside the literal text; the digest column is untouched
    db_path_of(directory).write_bytes(bytes(data))

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_record_invalid", "recovery")
        assert opened._store.anchor.hold.code == "journal_record_invalid"
    finally:
        opened.close()


def test_e11_damaged_page_header_gives_corrupt(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e11b", 2)
    _checkpoint(directory)

    data = bytearray(db_path_of(directory).read_bytes())
    data[journal_store.PAGE_SIZE] ^= 0xFF  # the b-tree page-type byte of page 2
    db_path_of(directory).write_bytes(bytes(data))

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_corrupt", "recovery")
    finally:
        opened.close()


# === E12: forged/re-signed rows on trigger-dropped images =====================


def _drop_and_recreate_triggers(directory: Path, mutate) -> None:
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        raw.execute("DROP TRIGGER journal_events_no_update")
        raw.execute("DROP TRIGGER journal_events_no_delete")
        mutate(raw)
        raw.execute(
            "CREATE TRIGGER journal_events_no_update BEFORE UPDATE ON journal_events\n"
            "  BEGIN SELECT RAISE(ABORT, 'append_only'); END"
        )
        raw.execute(
            "CREATE TRIGGER journal_events_no_delete BEFORE DELETE ON journal_events\n"
            "  BEGIN SELECT RAISE(ABORT, 'append_only'); END"
        )
        raw.commit()
    finally:
        raw.close()


def _stored_rows(directory: Path) -> list[tuple]:
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        return raw.execute(
            "SELECT event_seq, event_id, event_type, body, record_digest "
            "FROM journal_events ORDER BY event_seq"
        ).fetchall()
    finally:
        raw.close()


def test_e12_forged_wrong_predecessor_gives_chain_broken(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e12a", 2)

    rows = _stored_rows(directory)
    target = rows[3]  # the second admission's admission record
    record = jr.open_record(bytes(target[3]))
    forged_position = dataclasses.replace(record.position, prev_record_digest="f" * 64)
    forged = jr.seal(
        jr.Draft(
            event_id=record.event_id, event_type=record.event_type, actor=record.actor,
            ids=record.ids, data=record.data,
        ),
        forged_position, record.stamp,
    )

    def mutate(raw):
        raw.execute(
            "UPDATE journal_events SET body=?, record_digest=? WHERE event_seq=?",
            (forged.body, forged.record_digest, target[0]),
        )

    _drop_and_recreate_triggers(directory, mutate)

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_chain_broken", "recovery")
    finally:
        opened.close()


def test_e12_swapped_bodies_gives_chain_broken(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e12b")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()

    rows = _stored_rows(directory)
    admission_row, dedupe_row = rows[1], rows[2]

    def mutate(raw):
        # record_digest is UNIQUE: swap through a temporary placeholder so
        # neither intermediate UPDATE collides with the other row's digest.
        raw.execute(
            "UPDATE journal_events SET record_digest=? WHERE event_seq=?",
            ("z" * 64, admission_row[0]),
        )
        raw.execute(
            "UPDATE journal_events SET body=?, record_digest=? WHERE event_seq=?",
            (admission_row[3], admission_row[4], dedupe_row[0]),
        )
        raw.execute(
            "UPDATE journal_events SET body=?, record_digest=? WHERE event_seq=?",
            (dedupe_row[3], dedupe_row[4], admission_row[0]),
        )

    _drop_and_recreate_triggers(directory, mutate)

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_chain_broken", "recovery")
    finally:
        opened.close()


def test_e12_resigned_dedupe_result_gives_replay_mismatch(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e12c")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))  # first-ever: real result is "admitted"
    j.close()

    rows = _stored_rows(directory)
    dedupe_row = rows[2]
    record = jr.open_record(bytes(dedupe_row[3]))
    forged_data = dict(record.data)
    forged_data["result"] = "suppressed"
    forged = jr.seal(
        jr.Draft(
            event_id=record.event_id, event_type=record.event_type, actor=record.actor,
            ids=record.ids, data=forged_data,
        ),
        record.position, record.stamp,  # the tail record: no downstream chain to rebuild
    )

    def mutate(raw):
        raw.execute(
            "UPDATE journal_events SET body=?, record_digest=? WHERE event_seq=?",
            (forged.body, forged.record_digest, dedupe_row[0]),
        )

    _drop_and_recreate_triggers(directory, mutate)

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_replay_mismatch", "recovery")
    finally:
        opened.close()


def test_e12_emptied_table_gives_persisted_truncated_and_releases_the_lock(tmp_path):
    # Every row deleted, the schema otherwise intact: the presentation and
    # format checks pass and the row scan yields nothing, so replay never
    # reaches a head to compare with the anchor.
    directory, _receipts = _n_admissions(tmp_path, "e12d", 2)
    _drop_and_recreate_triggers(directory, lambda raw: raw.execute("DELETE FROM journal_events"))

    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_truncated", "recovery")
        assert opened.snapshot()["hold"]["persisted"] is True
    finally:
        opened.close()
    reopened = open_held(directory)  # a leaked lock would make this journal_locked
    try:
        assert reopened.hold == ("journal_truncated", "recovery")
    finally:
        reopened.close()


# === E13: transient open failure ==============================================


def test_e13_read_anchor_transient_failure_gives_open_failed(tmp_path, monkeypatch):
    directory, _clock, _ids, j = make(tmp_path, name="e13a")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    names = (journal_store.DB_FILENAME, journal_store.WAL_FILENAME, journal_store.ANCHOR_FILENAME)
    before = file_bytes(directory, names)

    def failing_read_anchor(self):
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(journal_store.JournalStore, "_read_anchor", failing_read_anchor)
    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_open_failed", "process")
    finally:
        opened.close()
    monkeypatch.undo()

    assert file_bytes(directory, names) == before
    open_ready(directory).close()


def test_e13_connect_sqlite_error_gives_open_failed(tmp_path, monkeypatch):
    directory, _clock, _ids, j = make(tmp_path, name="e13b")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()

    def failing_connect(self):
        error = sqlite3.OperationalError("synthetic short read")
        error.sqlite_errorcode = 522
        error.sqlite_errorname = "SQLITE_IOERR_SHORT_READ"
        raise error

    monkeypatch.setattr(journal_store.JournalStore, "_connect", failing_connect)
    opened = open_held(directory)
    try:
        assert opened.hold == ("journal_open_failed", "process")
    finally:
        opened.close()
    monkeypatch.undo()
    open_ready(directory).close()


# === E14: end-to-end fsync failure =============================================


@pytest.mark.skipif(sys.platform != "darwin", reason="F_FULLFSYNC is darwin-only")
def test_e14_end_to_end_fsync_failure_gives_write_failed_reopen_lag1(tmp_path, monkeypatch):
    directory, _clock, _ids, j = make(tmp_path, name="e14")
    anchor_before = anchor_path_of(directory).read_bytes()
    next_counter = j._store.anchor.counter + 1
    offset = journal_store.ANCHOR_SLOT_OFFSETS[next_counter % 2]
    pre_write_slot = anchor_before[offset:offset + journal_store.ANCHOR_SLOT_BYTES]

    real_fcntl = fcntl.fcntl
    real_open = os.open
    anchor_fd_holder: list[int] = []

    def recording_open(path, flags, *args):
        fd = real_open(path, flags, *args)
        if str(path).endswith(journal_store.ANCHOR_FILENAME):
            anchor_fd_holder.append(fd)
        return fd

    def failing_fcntl(fd, request, *args):
        if request == fcntl.F_FULLFSYNC and fd in anchor_fd_holder:
            raise OSError(errno.ENOTSUP, "Operation not supported")
        return real_fcntl(fd, request, *args)

    monkeypatch.setattr(os, "open", recording_open)
    monkeypatch.setattr(fcntl, "fcntl", failing_fcntl)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    with pytest.raises(rj.JournalError) as info:
        j.admit(a)
    assert info.value.code == "journal_write_failed"
    monkeypatch.undo()
    j.close()

    # A same-process re-read would still see the pwritten-but-unsynced bytes
    # (a real power loss is exactly what the failed F_FULLFSYNC is meant to
    # guard against): revert them to model an actual loss, the same way E3
    # edits an image for this crash window (C4).
    anchor_bytes = bytearray(anchor_path_of(directory).read_bytes())
    anchor_bytes[offset:offset + journal_store.ANCHOR_SLOT_BYTES] = pre_write_slot
    anchor_path_of(directory).write_bytes(bytes(anchor_bytes))

    reopened = open_ready(directory)
    try:
        assert reopened.snapshot()["anchor"]["lag_at_open"] == 1
        repeat = reopened.admit(a)
        assert repeat.result == "suppressed"
    finally:
        reopened.close()


# === E15: SIGKILL loop, 5 iterations ===========================================

_CHILD_SCRIPT = """
import sys
sys.path.insert(0, {repo_root!r})
from pathlib import Path
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox import recovery_journal as rj

directory = Path({directory!r})
try:
    journal = rj.open_recovery_journal(directory)
except rj.JournalError:
    journal = rj.create_recovery_journal(directory)

group = js.source_group_digest("e15-group")
i = 0
while True:
    src = js.SourceRecord(
        source_group=group,
        alerts=(js.SourceAlert(
            fingerprint="fp-" + str(i), status="firing", values=None, starts_at=None,
        ),),
        truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )
    receipt = journal.admit(src)
    print(receipt.admission_id, flush=True)
    i += 1
"""


def _run_child(directory: Path) -> subprocess.Popen:
    script = _CHILD_SCRIPT.format(repo_root=str(REPO_ROOT), directory=str(directory))
    return subprocess.Popen(
        [sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def _readline_before(stream, deadline: float) -> str | None:
    """One line from ``stream``, never blocking past ``deadline``.

    A plain ``stream.readline()`` blocks forever if the child goes quiet
    without closing its stdout (a hang, not a crash), which would hang this
    test -- and the whole suite run -- past any timeout. ``select`` bounds
    the wait; a timeout or EOF both read as ``None`` so the caller stops.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    ready, _write, _err = select.select([stream], [], [], remaining)
    if not ready:
        return None
    line = stream.readline()
    return line or None


def test_e15_sigkill_loop_five_iterations(tmp_path):
    for iteration in range(5):
        directory = new_dir(tmp_path, f"e15-{iteration}")
        proc = _run_child(directory)
        printed_ids: list[str] = []
        target = 2 + iteration * 2
        try:
            deadline = time.monotonic() + 15
            while len(printed_ids) < target:
                line = _readline_before(proc.stdout, deadline)
                if line is None:
                    break
                printed_ids.append(line.strip())
        finally:
            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=10)

        assert printed_ids, f"iteration {iteration}: child never printed a receipt"

        opened = rj.open_recovery_journal(directory)
        try:
            assert opened.state == "ready"
            stored_ids = {entry.admission_id for entry in opened.pending()}
            assert set(printed_ids) <= stored_ids
            assert opened.snapshot()["anchor"]["lag_at_open"] <= 1
        finally:
            opened.close()


# === E16: golden guard ==========================================================


def _build_golden_records(directory: Path) -> list[jr.Record]:
    """Deterministic scenario: genesis (max_admissions=5); A, B, A, A;
    restart_recovery; A; the 6th arrival's capacity_hold -- 13 records. A
    seeded id_factory (canonical-uuid-shaped, strictly increasing, covering
    journal_uuid/boot_id/every event_id) and fixed-step clocks make every
    byte reproducible."""
    ids = SeqIds()
    clock = SeqClock()
    bounds = jrd.JournalBounds(
        max_admissions=5, max_pending_fingerprints=1_024,
        ordinary_bytes=112 * 2**20, total_bytes=128 * 2**20,
    )
    journal = rj.create_recovery_journal(
        directory, bounds=bounds, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )
    a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    b = source(CG1_KEY, (PF, "firing", (("A", "2"), ("B", "1"))))
    journal.admit(a)
    journal.admit(b)
    journal.admit(a)
    journal.admit(a)  # suppressed; still the 4th admission
    journal.close()

    journal = rj.open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )
    journal.admit(a)  # the 5th admission: at the cap, held (restart_recovery active)
    sixth = source(CG1_KEY, (PC, "firing", (("A", "1"),)))
    with pytest.raises(rj.JournalError) as info:
        journal.admit(sixth)
    assert info.value.code == "capacity_admissions"
    journal.close()

    store = journal_store.JournalStore.open(directory)
    try:
        records = list(store.rows())
    finally:
        store.close()
    return records


# Pinned once, at golden-file generation time: a one-off run of
# ``_build_golden_records`` against a fresh tmp_path, then
# ``journal_reducer.state_digest``/``.head.record_digest``/``pending_digest``
# of ``journal_reducer.replay`` over the resulting records (the same values
# this test recomputes from the committed JSONL below and must still match).
_E16_STATE_DIGEST = "7e72b935089ad98f3470ac83252d1693392fbb8ded56698bdb913c7aa1a3ab35"
_E16_HEAD_DIGEST = "13555d5723c8db2c828ad6ee3ada1d51e1c7297fe419182ff2bdb7ce40e58015"
_E16_PENDING_DIGEST = "ff7dbdc7d3554cae3d61cc47d6cea27df31b448a63513cc8a89a3b30b3683538"


def test_e16_golden_guard(tmp_path):
    lines = GOLDEN_PATH.read_text(encoding="ascii").splitlines()
    assert len(lines) == 13
    records = [jr.open_record(line.encode("ascii")) for line in lines]

    replayed = jrd.replay(records)
    assert jrd.state_digest(replayed) == _E16_STATE_DIGEST
    assert replayed.head.record_digest == _E16_HEAD_DIGEST

    directory = new_dir(tmp_path, "e16-loaded")
    genesis = records[0]
    journal_uuid = genesis.data["journal_uuid"]
    store = journal_store.JournalStore.create(directory, genesis, journal_uuid=journal_uuid)
    store.close()

    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        for record in records[1:]:
            raw.execute(
                "INSERT INTO journal_events (event_seq, event_id, event_type, body, record_digest) "
                "VALUES (?, ?, ?, ?, ?)",
                (record.position.event_seq, record.event_id, record.event_type, record.body,
                 record.record_digest),
            )
        raw.commit()
    finally:
        raw.close()

    last = records[-1]
    body = {
        "counter": 2, "format": journal_store.ANCHOR_FORMAT, "journal_uuid": journal_uuid,
        "head": {
            "commit_seq": last.position.commit_seq, "event_seq": last.position.event_seq,
            "generation": last.position.journal_generation, "record_digest": last.record_digest,
        },
        "hold": None,
    }
    slot = journal_store._encode_slot(body)
    with open(anchor_path_of(directory), "r+b") as handle:
        handle.seek(journal_store.ANCHOR_SLOT_OFFSETS[0])
        handle.write(slot)

    # Real (uuid4-based) id_factory: a fresh SeqIds() would restart at
    # "000...01" and collide with the golden records' own SeqIds-seeded ids.
    opened = rj.open_recovery_journal(directory)
    try:
        assert opened.state == "ready"
        assert opened._verified_state_digest == _E16_STATE_DIGEST
        assert jrd.pending_digest(opened._projection) == _E16_PENDING_DIGEST
    finally:
        opened.close()


def test_e16_build_golden_records_reproduces_the_committed_golden_file(tmp_path):
    """``_build_golden_records`` itself was never exercised by any test --
    only the committed JSONL it once produced was. Call it directly and
    confirm it reproduces that file record-for-record, except for the one
    field that cannot be reproduced deterministically: the WAL's own random
    per-file salt bytes baked into ``restart_recovery``'s observed
    ``wal_found.digest`` (a real per-run SQLite artifact, not a fixture
    value) -- which then legitimately changes every later record's
    ``prev_record_digest`` (and so its own ``record_digest``) purely as a
    chain consequence. Every other field, on every record, must match
    exactly.
    """
    lines = GOLDEN_PATH.read_text(encoding="ascii").splitlines()
    golden = [jr.open_record(line.encode("ascii")) for line in lines]

    directory = new_dir(tmp_path, "e16-rebuild")
    regenerated = _build_golden_records(directory)

    assert len(regenerated) == len(golden) == 13
    assert [r.event_type for r in regenerated] == [g.event_type for g in golden]

    restart_index = next(i for i, g in enumerate(golden) if g.event_type == "restart_recovery")
    for index, (g, r) in enumerate(zip(golden, regenerated)):
        if index < restart_index:
            assert r == g, index
            continue
        if index == restart_index:
            assert r.position == g.position
            assert r.stamp == g.stamp
            assert r.event_id == g.event_id
            assert r.ids == g.ids
            assert set(r.data.keys()) == set(g.data.keys()) == {
                "previous_boot_id", "recovered", "anchor_lag", "wal_found", "dispatch_hold",
                "prior_leases",
            }
            unaffected_keys = (
                "previous_boot_id", "recovered", "anchor_lag", "dispatch_hold", "prior_leases",
            )
            for key in unaffected_keys:
                assert r.data[key] == g.data[key], key
            assert r.data["wal_found"]["size"] == g.data["wal_found"]["size"]
            for wal_found in (r.data["wal_found"], g.data["wal_found"]):
                digest = wal_found["digest"]
                assert isinstance(digest, str) and len(digest) == 64
            continue
        # After the restart record, only the chained prev_record_digest (and
        # therefore this record's own record_digest) may legitimately differ.
        assert r.event_id == g.event_id
        assert r.event_type == g.event_type
        assert r.actor == g.actor
        assert r.ids == g.ids
        assert r.stamp == g.stamp
        assert r.data == g.data
        assert dataclasses.replace(r.position, prev_record_digest="") == dataclasses.replace(
            g.position, prev_record_digest="",
        )


# === E17: no evidence destroyed (critic 1) =====================================

_DB_WAL = (journal_store.DB_FILENAME, journal_store.WAL_FILENAME)


def test_e17_db_and_wal_byte_identical_after_held_open_e8a(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e17-e8a", 2)
    wal_bytes = wal_path_of(directory).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path_of(directory).write_bytes(flip_byte_in_group(wal_bytes, groups[-1]))
    before = file_bytes(directory, _DB_WAL)

    opened = open_held(directory)
    opened.close()
    assert file_bytes(directory, _DB_WAL) == before


def test_e17_db_and_wal_byte_identical_after_held_open_e8b(tmp_path):
    directory, _receipts = _n_admissions(tmp_path, "e17-e8b", 1)
    wal_bytes = wal_path_of(directory).read_bytes()
    groups = commit_groups(wal_frames(wal_bytes))
    wal_path_of(directory).write_bytes(flip_byte_in_group(wal_bytes, groups[0]))
    before = file_bytes(directory, _DB_WAL)

    opened = open_held(directory)
    opened.close()
    assert file_bytes(directory, _DB_WAL) == before


def test_e17_db_and_wal_byte_identical_after_held_open_e9(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e17-e9")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    stale = tmp_path / "e17-e9-stale"
    snapshot(directory, stale)
    j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    j.admit(source(CG1_KEY, (PX, "firing", (("A", "1"),))))
    j.close()
    db_path_of(directory).write_bytes(db_path_of(stale).read_bytes())
    wal_path_of(directory).write_bytes(wal_path_of(stale).read_bytes())
    before = file_bytes(directory, _DB_WAL)

    opened = open_held(directory)
    opened.close()
    assert file_bytes(directory, _DB_WAL) == before


def test_e17_db_and_wal_byte_identical_after_held_open_e10(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e17-e10")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    old_anchor = anchor_path_of(directory).read_bytes()
    j.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
    j.admit(source(CG1_KEY, (PX, "firing", (("A", "1"),))))
    j.close()
    anchor_path_of(directory).write_bytes(old_anchor)
    before = file_bytes(directory, _DB_WAL)

    opened = open_held(directory)
    opened.close()
    assert file_bytes(directory, _DB_WAL) == before


def test_e17_anchor_stays_absent_after_held_open(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e17-missing")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    anchor_path_of(directory).unlink()

    opened = open_held(directory)
    opened.close()
    assert not anchor_path_of(directory).exists()


def test_e17_anchor_byte_identical_after_held_open_when_invalid(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e17-invalid")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    anchor_path_of(directory).write_bytes(b"\x00" * journal_store.ANCHOR_BYTES)
    before = anchor_path_of(directory).read_bytes()

    opened = open_held(directory)
    opened.close()
    assert anchor_path_of(directory).read_bytes() == before


def test_e17_ready_open_and_close_keeps_the_wal_inode(tmp_path):
    directory, _clock, _ids, j = make(tmp_path, name="e17-inode")
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    j.close()
    inode_before = wal_path_of(directory).stat().st_ino

    opened = open_ready(directory)
    opened.close()
    assert wal_path_of(directory).stat().st_ino == inode_before


# === E18: open-time measurement (critic 15; recorded, never asserted) ========


def _build_large_image(directory: Path, pairs: int) -> str:
    """``pairs`` admission pairs built purely via the reducer's plan
    functions (no shell, no per-admission real syncs), inserted in one raw
    transaction, with the anchor written via ``_encode_slot`` -- the golden
    loader path (E16/E18 share this construction style)."""
    journal_uuid = str(uuid.uuid4())
    boot_id = str(uuid.uuid4())
    max_pending = jr.V1_BOUND_CEILINGS["max_pending_fingerprints"]
    bounds = jrd.JournalBounds(
        max_admissions=pairs + 10, max_pending_fingerprints=max_pending,
        ordinary_bytes=112 * 2**20, total_bytes=128 * 2**20,
    )
    wall_time = "2026-09-23T00:00:00.000000Z"
    # Cycle a bounded pool of fingerprints so pending never approaches the
    # 1,024 v1 ceiling, while still minting `pairs` distinct admissions.
    fingerprint_pool = 200

    projection = jrd.new_projection()
    genesis_stamp = jr.Stamp(boot_id=boot_id, wall_time=wall_time, mono_us=1)
    genesis_plan = jrd.plan_genesis(
        journal_uuid=journal_uuid, bounds=bounds, event_id=str(uuid.uuid4()), stamp=genesis_stamp,
    )
    jrd.apply_delta(projection, jrd.verify_commit(projection, genesis_plan.records))
    records = list(genesis_plan.records)

    for i in range(pairs):
        stamp_i = jr.Stamp(boot_id=boot_id, wall_time=wall_time, mono_us=2 + i)
        src = js.SourceRecord(
            source_group=js.source_group_digest("e18-group"),
            alerts=(js.SourceAlert(
                fingerprint=f"fp-{i % fingerprint_pool:06d}", status="firing",
                values=(("A", "1"),), starts_at=None,
            ),),
            truncated_alerts=0, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
        )
        plan = jrd.plan_admission(
            projection, src, admission_id=str(uuid.uuid4()), dedupe_event_id=str(uuid.uuid4()),
            stamp=stamp_i,
        )
        assert type(plan) is jrd.Plan, plan
        jrd.apply_delta(projection, jrd.verify_commit(projection, plan.records))
        records.extend(plan.records)

    store = journal_store.JournalStore.create(directory, records[0], journal_uuid=journal_uuid)
    store.close()
    raw = sqlite3.connect(str(db_path_of(directory)))
    try:
        for record in records[1:]:
            raw.execute(
                "INSERT INTO journal_events (event_seq, event_id, event_type, body, record_digest) "
                "VALUES (?, ?, ?, ?, ?)",
                (record.position.event_seq, record.event_id, record.event_type, record.body,
                 record.record_digest),
            )
        raw.commit()
    finally:
        raw.close()

    last = records[-1]
    body = {
        "counter": 2, "format": journal_store.ANCHOR_FORMAT, "journal_uuid": journal_uuid,
        "head": {
            "commit_seq": last.position.commit_seq, "event_seq": last.position.event_seq,
            "generation": last.position.journal_generation, "record_digest": last.record_digest,
        },
        "hold": None,
    }
    slot = journal_store._encode_slot(body)
    with open(anchor_path_of(directory), "r+b") as handle:
        handle.seek(journal_store.ANCHOR_SLOT_OFFSETS[0])
        handle.write(slot)
    return journal_uuid


def test_e18_open_time_measurement_2000_pairs(tmp_path):
    directory = new_dir(tmp_path, "e18")
    _build_large_image(directory, 2_000)

    started = time.perf_counter()
    opened = rj.open_recovery_journal(directory)
    elapsed = time.perf_counter() - started
    try:
        assert opened.state == "ready"
    finally:
        opened.close()
    extrapolated = elapsed * 5  # 2,000 -> 10,000 pairs, ~linear in row count
    print(
        f"\n[test_recovery_journal_crash] e18 open(2000 pairs)={elapsed:.2f}s "
        f"extrapolated(10000)={extrapolated:.2f}s"
    )
