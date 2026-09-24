"""Adversarial tests for the recovery journal (ticket 37, unit 15b; Tester F,
cases F1-F9). Real SQLite and real syncs where store images are opened; at
most 300 real syncs (Tester F's budget).

This file is self-contained: it builds its own deterministic golden records
and journal images rather than depending on ``tests/data/recovery_journal_v1_
golden.jsonl`` (Tester E's concurrently-written golden file) or importing
helpers from the other, still-evolving journal test files. Golden values and
expected rejections are worked out from the source modules' own documented
rules, never trusted from the module under test.
"""

from __future__ import annotations

import ast
import copy
import errno
import hashlib
import json
import pathlib
import random
import re
import shutil
import sqlite3

import pytest

from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_source as js
from grafana_jsm_sandbox import journal_store
from grafana_jsm_sandbox import recovery_journal as rj
from grafana_jsm_sandbox.forwarder_json import JSONPolicyError, canonical_json

pytestmark = pytest.mark.skipif(
    not journal_store.no_ckpt_supported(),
    reason="needs sqlite3.Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE (Python >= 3.12)",
)

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent

CG1_KEY = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
CG1 = js.source_group_digest(CG1_KEY)

PF = "5e8d72dc87b1ff35"
PC = "6cd7e206a0716d2d"

MARKER = "advmarkerZZ9F"
MARKER_INVALID = MARKER + " \x00invalid"


# === Shared helpers (self-contained; mirrors D/B's fixture style) ===========


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


class ReplayIds:
    """Returns each of ``override`` in order, then falls back to ``base``."""

    def __init__(self, base, override) -> None:
        self._base = base
        self._override = list(override)

    def __call__(self) -> str:
        if self._override:
            return self._override.pop(0)
        return self._base()


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


def copy_image(base_dir: pathlib.Path, tmp_path: pathlib.Path, name: str = "journal") -> pathlib.Path:
    target = tmp_path / name
    shutil.copytree(base_dir, target)
    return target


def _restore_bytes(path: pathlib.Path, data: bytes) -> None:
    """Write ``data`` to ``path`` and force mode 0600: ``Path.write_bytes`` on
    a path that does not yet exist (as after a copy that dropped the file)
    creates it with the process umask, which the store's own ownership
    checks then correctly refuse as ``journal_permissions``."""
    path.write_bytes(data)
    path.chmod(0o600)


def _file_bytes(directory: pathlib.Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(directory.iterdir())
        if path.name != journal_store.LOCK_FILENAME
    }


def _envelope(record: jr.Record) -> dict:
    return {
        "schema_version": jr.SCHEMA_VERSION,
        "journal_generation": record.position.journal_generation,
        "event_id": record.event_id, "event_seq": record.position.event_seq,
        "commit_seq": record.position.commit_seq, "commit_index": record.position.commit_index,
        "commit_size": record.position.commit_size, "event_type": record.event_type,
        "actor": record.actor, "boot_id": record.stamp.boot_id, "wall_time": record.stamp.wall_time,
        "mono_us": record.stamp.mono_us, "ids": jr.thaw(record.ids), "data": jr.thaw(record.data),
        "prev_record_digest": record.position.prev_record_digest,
    }


def _reseal(envelope: dict, prev_digest: str | None = None) -> jr.Record:
    """Rebuild+re-sign a record from a (possibly mutated) envelope: digests and
    the chain stay internally valid, but the content need not be."""
    if prev_digest is not None:
        envelope = dict(envelope, prev_record_digest=prev_digest)
    draft = jr.Draft(
        event_id=envelope["event_id"], event_type=envelope["event_type"], actor=envelope["actor"],
        ids=envelope["ids"], data=envelope["data"],
    )
    position = jr.Position(
        journal_generation=envelope["journal_generation"], event_seq=envelope["event_seq"],
        commit_seq=envelope["commit_seq"], commit_index=envelope["commit_index"],
        commit_size=envelope["commit_size"], prev_record_digest=envelope["prev_record_digest"],
    )
    stamp = jr.Stamp(
        boot_id=envelope["boot_id"], wall_time=envelope["wall_time"], mono_us=envelope["mono_us"],
    )
    return jr.seal(draft, position, stamp)


@pytest.fixture(scope="module", autouse=True)
def _sync_budget():
    import time as _time

    counts = {"n": 0}
    original = journal_store._full_sync

    def counting_full_sync(fd: int) -> None:
        counts["n"] += 1
        return original(fd)

    journal_store._full_sync = counting_full_sync
    start = _time.perf_counter()
    yield counts
    elapsed = _time.perf_counter() - start
    journal_store._full_sync = original
    print(f"\n[test_recovery_journal_adversarial] real syncs={counts['n']} wall={elapsed:.2f}s")


# =============================================================================
# F1: pure mutation matrix
# =============================================================================

_SIBLING_KEY = "zz_adversarial_sibling"
_SUBSTITUTES = (None, True, 0, -1, 2**53, "x" * 300, [], {})


def _iter_dict_paths(node, path=()):
    """Yield every path to a dict key found anywhere under ``node``, recursing
    into dict values and list elements (so nested list-of-dict fields, like
    ``superseded`` or ``alerts``, are reached too)."""
    if type(node) is dict:
        for key, value in node.items():
            yield path + (key,)
            yield from _iter_dict_paths(value, path + (key,))
    elif type(node) is list:
        for index, value in enumerate(node):
            yield from _iter_dict_paths(value, path + (index,))


def _get(root, path):
    node = root
    for step in path:
        node = node[step]
    return node


def _leaf_mutations(envelope):
    """Every (path, op, value) mutation: one delete and one add-sibling per
    distinct parent dict, plus every substitution that actually changes the
    current value."""
    mutations = []
    seen_parents = set()
    for path in _iter_dict_paths(envelope):
        current = _get(envelope, path)
        mutations.append((path, "delete", None))
        parent_path = path[:-1]
        if parent_path not in seen_parents:
            seen_parents.add(parent_path)
            mutations.append((parent_path, "add_sibling", None))
        for value in _SUBSTITUTES:
            if type(value) is type(current) and value == current:
                continue
            mutations.append((path, "substitute", value))
    return mutations


def _apply_mutation(envelope, path, op, value):
    mutated = copy.deepcopy(envelope)
    if op == "add_sibling":
        target = _get(mutated, path)
        target[_SIBLING_KEY] = "adversarial-sibling"
        return mutated
    parent = _get(mutated, path[:-1])
    key = path[-1]
    if op == "delete":
        del parent[key]
    else:
        parent[key] = copy.deepcopy(value)
    return mutated


def _short(value) -> str:
    return repr(value)


def _mutate_and_check(kind, envelope, projection_before, *, pair_role=None, companion=None):
    """Every leaf mutation of ``envelope`` must be rejected, either by
    ``open_record`` (a typed ``RecordError``/``SourceError``) or by
    ``verify_commit`` against a fresh copy of the pre-commit projection (a
    ``ReplayError``). Returns the mutations that were *not* rejected, for the
    caller to check against an explicit allow-list.
    """
    unexpected = []
    for path, op, value in _leaf_mutations(envelope):
        mutated_envelope = _apply_mutation(envelope, path, op, value)
        try:
            mutated_body = canonical_json(mutated_envelope, ascii_only=True)
        except JSONPolicyError:
            continue  # the encoder itself is the rejection layer here
        rejected = False
        mutated_record = None
        try:
            mutated_record = jr.open_record(mutated_body)
        except (jr.RecordError, js.SourceError):
            rejected = True
        if not rejected:
            if pair_role is None:
                commit = (mutated_record,)
            elif pair_role == "admission":
                companion_env = _envelope(companion)
                rechained = _reseal(companion_env, prev_digest=mutated_record.record_digest)
                commit = (mutated_record, rechained)
            else:
                commit = (companion, mutated_record)
            try:
                jrd.verify_commit(copy.deepcopy(projection_before), commit)
            except jrd.ReplayError:
                rejected = True
        if not rejected:
            unexpected.append((kind, path, op, _short(value)))
    return unexpected


_F1_JOURNAL_UUID = "33333333-3333-3333-3333-333333333333"
_F1_BOOT_A = "44444444-4444-4444-4444-444444444444"
_F1_BOOT_B = "55555555-5555-5555-5555-555555555555"
_F1_BOUNDS = jrd.JournalBounds(
    max_admissions=2, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
    total_bytes=128 * 2**20,
)


def _f1_stamp(boot_id, minute, second=0):
    return jr.Stamp(
        boot_id=boot_id, wall_time=f"2026-09-23T00:{minute:02d}:{second:02d}.000000Z", mono_us=minute + 1,
    )


def _f1_commit(p, plan):
    delta = jrd.verify_commit(p, plan.records)
    jrd.apply_delta(p, delta)


def _build_f1_golden():
    """A real (pure, no I/O) chain: genesis -> restart -> two admissions in
    the same group (so the second's dedupe_decision has a non-None
    ``baseline_before`` and a non-empty ``superseded``) -> a capacity_hold.
    """
    p = jrd.new_projection()

    genesis_plan = jrd.plan_genesis(
        journal_uuid=_F1_JOURNAL_UUID, bounds=_F1_BOUNDS, event_id="f1-genesis",
        stamp=_f1_stamp(_F1_BOOT_A, 0),
    )
    p_before_genesis = copy.deepcopy(p)
    _f1_commit(p, genesis_plan)
    genesis_record = genesis_plan.records[0]

    restart_plan = jrd.plan_restart(
        p, event_id="f1-restart", stamp=_f1_stamp(_F1_BOOT_B, 1),
        anchor_lag=0, wal_found=jr.WalFound(size=4_096, digest="a" * 64),
    )
    assert isinstance(restart_plan, jrd.Plan)
    p_before_restart = copy.deepcopy(p)
    _f1_commit(p, restart_plan)
    restart_record = restart_plan.records[0]

    first_source = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    first_plan = jrd.plan_admission(
        p, first_source, admission_id="f1-adm1", dedupe_event_id="f1-ded1",
        stamp=_f1_stamp(_F1_BOOT_B, 2),
    )
    assert isinstance(first_plan, jrd.Plan)
    _f1_commit(p, first_plan)

    second_source = source(CG1_KEY, (PF, "firing", (("A", "2"),)))
    second_plan = jrd.plan_admission(
        p, second_source, admission_id="f1-adm2", dedupe_event_id="f1-ded2",
        stamp=_f1_stamp(_F1_BOOT_B, 3),
    )
    assert isinstance(second_plan, jrd.Plan)
    p_before_pair = copy.deepcopy(p)
    _f1_commit(p, second_plan)
    admission_record, dedupe_record = second_plan.records

    refusal = jrd.CapacityRefusal(
        "capacity_admissions", p.bounds.max_admissions, p.admission_count, 1,
    )
    capacity_plan = jrd.plan_capacity_hold(
        p, refusal, event_id="f1-cap", stamp=_f1_stamp(_F1_BOOT_B, 4),
        refused_source_digest=js.source_digest(second_source),
    )
    assert isinstance(capacity_plan, jrd.Plan)
    p_before_capacity = copy.deepcopy(p)
    _f1_commit(p, capacity_plan)
    capacity_record = capacity_plan.records[0]

    return {
        "journal_genesis": (genesis_record, p_before_genesis),
        "restart_recovery": (restart_record, p_before_restart),
        "admission_pair": (admission_record, dedupe_record, p_before_pair),
        "capacity_hold": (capacity_record, p_before_capacity),
    }


# Mutations that are valid by type -- structurally well-formed and,
# independently, not something either ``verify_commit`` or ``decode_record``
# has any basis to reject -- explicitly allow-listed, one entry per finding,
# each with the reason it is not a gap:
#
# * genesis/restart ``mono_us`` -> 0: both shapes return before the general
#   ``mono_us >= p.last_mono_us`` check in ``verify_commit`` (there is no
#   prior boot to compare genesis against, and a restart begins a *new* boot,
#   so its own mono_us has nothing of this boot's to be non-decreasing from
#   yet); 0 is within the field's own 0..MAX_SEQ bound (spec: "mono_us ...
#   never compared across boots").
# * restart ``wal_found`` (and its ``size``) -> None / 0: the schema and spec
#   both say ``wal_found`` is ``null`` (unknown) or a ``{size, digest}``
#   observation -- it is an "observed fact ... only type-checked" (Record
#   schema table), never independently re-derived by ``_verify_restart``; a
#   zero-byte WAL is a perfectly legitimate observation.
_F1_ALLOWED = {
    ("journal_genesis", ("mono_us",), "substitute", repr(0)),
    ("restart_recovery", ("mono_us",), "substitute", repr(0)),
    ("restart_recovery", ("data", "wal_found"), "substitute", repr(None)),
    ("restart_recovery", ("data", "wal_found", "size"), "substitute", repr(0)),
}


def test_f1_pure_mutation_matrix_rejects_every_leaf_mutation():
    golden = _build_f1_golden()
    unexpected = []

    genesis_record, p_before_genesis = golden["journal_genesis"]
    unexpected += _mutate_and_check(
        "journal_genesis", _envelope(genesis_record), p_before_genesis,
    )

    restart_record, p_before_restart = golden["restart_recovery"]
    unexpected += _mutate_and_check(
        "restart_recovery", _envelope(restart_record), p_before_restart,
    )

    admission_record, dedupe_record, p_before_pair = golden["admission_pair"]
    unexpected += _mutate_and_check(
        "admission", _envelope(admission_record), p_before_pair,
        pair_role="admission", companion=dedupe_record,
    )
    unexpected += _mutate_and_check(
        "dedupe_decision", _envelope(dedupe_record), p_before_pair,
        pair_role="dedupe", companion=admission_record,
    )

    capacity_record, p_before_capacity = golden["capacity_hold"]
    unexpected += _mutate_and_check(
        "capacity_hold", _envelope(capacity_record), p_before_capacity,
    )

    truly_unexpected = [tuple(u) for u in unexpected if tuple(u) not in _F1_ALLOWED]
    assert truly_unexpected == [], (
        f"{len(truly_unexpected)} mutation(s) were accepted when they should have been "
        f"rejected -- (record_type, path, op, value): {truly_unexpected[:15]}"
    )


def test_f1_type_valid_allowlist_entries_are_really_accepted():
    """The allow-list only earns its keep if every entry really is accepted by
    both layers (never rejected) -- otherwise it would be silently hiding a
    mutation that current source code actually does catch.
    """
    golden = _build_f1_golden()
    accepted_kinds = {kind for kind, _p, _op, _v in _F1_ALLOWED}
    checks = {
        "journal_genesis": (lambda: golden["journal_genesis"]),
        "restart_recovery": (lambda: golden["restart_recovery"]),
    }
    seen = set()
    for kind in accepted_kinds:
        record, p_before = checks[kind]()
        unexpected = _mutate_and_check(kind, _envelope(record), p_before)
        seen |= {tuple(u) for u in unexpected}
    assert _F1_ALLOWED <= seen, sorted(_F1_ALLOWED - seen)


# =============================================================================
# Shared checkpointed base image (F2, F8, F9)
# =============================================================================


@pytest.fixture(scope="module")
def checkpointed_base(tmp_path_factory):
    """genesis + one admission pair, checkpointed into the main db file and
    closed (never reopened), for tests that tamper with the on-disk bytes."""
    base_dir = tmp_path_factory.mktemp("adv-base") / "journal"
    base_dir.mkdir(mode=0o700)
    clock, ids = SeqClock(), SeqIds()
    journal = rj.create_recovery_journal(
        base_dir, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    verified_digest = journal.snapshot()["state_digest"]
    journal.close()

    raw = sqlite3.connect(str(base_dir / journal_store.DB_FILENAME))
    try:
        raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        raw.close()
    shm_path = base_dir / "journal.sqlite3-shm"
    if shm_path.exists():
        shm_path.unlink()

    return base_dir, verified_digest


# =============================================================================
# F2: 40 seeded single-bit flips of a checkpointed DB image
# =============================================================================


def test_f2_forty_seeded_bit_flips_never_open_ready_with_different_state(
    checkpointed_base, tmp_path,
):
    base_dir, original_digest = checkpointed_base
    original_size = (base_dir / journal_store.DB_FILENAME).stat().st_size
    outcomes = {"held": 0, "ready": 0}

    for seed in range(40):
        rng = random.Random(seed)
        directory = copy_image(base_dir, tmp_path, name=f"f2-{seed}")
        db_path = directory / journal_store.DB_FILENAME
        data = bytearray(db_path.read_bytes())
        byte_index = rng.randrange(original_size)
        bit_index = rng.randrange(8)
        data[byte_index] ^= 1 << bit_index
        db_path.write_bytes(bytes(data))

        # A fresh, non-colliding id sequence (T1): SeqIds() restarting at 1
        # would mint the exact same event ids the base image's own
        # genesis/admission already used, so a clean flip's restart-on-open
        # commit would always find a duplicate event_id with different
        # content (store_event_conflict -> journal_divergence), masking
        # every "ready" outcome as a process "held" one below.
        clock, ids = SeqClock(), SeqIds(start=1_000)
        journal = rj.open_recovery_journal(
            directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
        )
        try:
            if journal.state == "held":
                outcomes["held"] += 1
                assert journal.hold[1] in ("recovery", "process")
            else:
                outcomes["ready"] += 1
                assert journal.state == "ready"
                assert journal.snapshot()["verified_state_digest"] == original_digest
        finally:
            journal.close()

    # The seeded flips actually exercised both outcomes: some genuinely
    # verify clean and open ready with the identical verified state digest
    # (the per-iteration assert above is what would catch a silent
    # divergence), and some are genuinely caught as corrupt.
    assert outcomes["held"] + outcomes["ready"] == 40
    assert outcomes["held"] > 0
    assert outcomes["ready"] > 0
    print(f"\n[F2] outcomes={outcomes}")


# =============================================================================
# F3: free-text audit over every stored string leaf (I17)
# =============================================================================

_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_ID_CHARSET_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")
_WALL_TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")
_STARTS_AT_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z",
)

_F3_KNOWN_LITERALS = (
    set(jr.EVENT_TYPES) | set(jr.ACTORS) | set(jr.DEDUPE_RESULTS) | set(jr.ADMISSION_DECISIONS)
    | set(jr.CAPACITY_CODES) | set(jr.DISPATCH_HOLD_CODES) | set(js.ALERT_STATUSES)
    | set(js.PROVENANCE_KINDS) | {jr.DEDUPE_RULE, "rj.journal.v1", "invalid", "set", "/notification"}
)


def _is_allowed_leaf_string(value: str) -> bool:
    if _HEX64_RE.fullmatch(value):
        return True
    if value in _F3_KNOWN_LITERALS:
        return True
    if _WALL_TIME_RE.fullmatch(value) or _STARTS_AT_RE.fullmatch(value):
        return True
    if js.is_canonical_number(value):
        return True
    return bool(_ID_CHARSET_RE.fullmatch(value))  # restricted-charset ID, fingerprint or refId


def _walk_string_values(node):
    if type(node) is dict:
        for value in node.values():
            yield from _walk_string_values(value)
    elif type(node) is list:
        for item in node:
            yield from _walk_string_values(item)
    elif type(node) is str:
        yield node


def _build_f3_journal(tmp_path):
    directory = new_dir(tmp_path, "f3")
    clock, ids = SeqClock(), SeqIds()
    bounds = jrd.JournalBounds(
        max_admissions=3, max_pending_fingerprints=1_024, ordinary_bytes=112 * 2**20,
        total_bytes=128 * 2**20,
    )
    journal = rj.create_recovery_journal(
        directory, bounds=bounds, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
    )
    a1 = js.SourceRecord(
        source_group=js.source_group_digest(CG1_KEY),
        alerts=(
            js.SourceAlert(
                fingerprint=PF, status="firing", values=(("A", "0.1144"), ("B", "1")),
                starts_at="2026-09-17T21:56:20Z",
            ),
        ),
        truncated_alerts=0, body_digest="a" * 64, provenance=js.HTTP_PROVENANCE,
    )
    journal.admit(a1)
    a2 = js.SourceRecord(
        source_group=js.source_group_digest(CG1_KEY),
        alerts=(js.SourceAlert(fingerprint=PC, status="resolved", values=None, starts_at=None),),
        truncated_alerts=0, body_digest="b" * 64, provenance=js.HTTP_PROVENANCE,
    )
    journal.admit(a2)
    journal.close()

    reopened = reopen(directory, clock, ids)  # appends a restart_recovery record
    reopened.admit(a1)  # third admission: exactly at max_admissions=3
    with pytest.raises(rj.JournalError) as info:
        reopened.admit(a2)  # fourth: writes a capacity_hold record
    assert info.value.code == "capacity_admissions"
    reopened.close()
    return directory


def test_f3_every_stored_string_leaf_matches_a_closed_grammar(tmp_path):
    directory = _build_f3_journal(tmp_path)
    store = journal_store.JournalStore.open(directory)
    try:
        seen_types = set()
        bad = []
        for record in store.rows():
            seen_types.add(record.event_type)
            envelope = json.loads(record.body)
            for value in _walk_string_values(envelope):
                if not _is_allowed_leaf_string(value):
                    bad.append((record.event_type, value))
        assert bad == []
        # Sanity: the audit really covered every in-scope record type.
        assert seen_types == set(jr.EVENT_TYPES)
    finally:
        store.close()


# =============================================================================
# F4: custody -- clean errors, no marker leakage
# =============================================================================


def _assert_clean_error(error, code):
    assert error.args == (code,)
    assert error.__cause__ is None
    assert MARKER not in repr(error)
    assert MARKER not in str(error)


def test_f4_journal_source_marker_input_gives_a_clean_error():
    with pytest.raises(js.SourceError) as info:
        js.source_group_digest(MARKER_INVALID)
    error = info.value
    assert error.code == "source_group"
    _assert_clean_error(error, "source_group")
    assert error.__context__ is None


def test_f4_journal_records_marker_input_gives_a_clean_error():
    with pytest.raises(jr.RecordError) as info:
        jr.validate_id(MARKER_INVALID)
    error = info.value
    assert error.code == "record_id"
    _assert_clean_error(error, "record_id")
    assert error.__context__ is None


def test_f4_journal_reducer_marker_input_gives_a_clean_error():
    # A dedupe record whose own ``ids.admission_id`` disagrees with its
    # admission's -- valid by shape (decode_record never cross-checks the two
    # records), so this trips ``_verify_admission_pair``'s own direct
    # ``_fail_replay("replay_shape")``, not a decode-time rejection.
    p = jrd.new_projection()
    genesis_plan = jrd.plan_genesis(
        journal_uuid=_F1_JOURNAL_UUID, bounds=jrd.DEFAULT_BOUNDS, event_id="f4-genesis",
        stamp=_f1_stamp(_F1_BOOT_A, 0),
    )
    _f1_commit(p, genesis_plan)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        p, a, admission_id="adm-real", dedupe_event_id="ded-real", stamp=_f1_stamp(_F1_BOOT_A, 1),
    )
    assert isinstance(plan, jrd.Plan)
    admission_record, dedupe_record = plan.records
    envelope = _envelope(dedupe_record)
    envelope["ids"] = {"admission_id": "adm-" + MARKER}
    tampered = _reseal(envelope)
    with pytest.raises(jrd.ReplayError) as info:
        jrd.verify_commit(p, (admission_record, tampered))
    error = info.value
    assert error.code == "replay_shape"
    _assert_clean_error(error, "replay_shape")
    assert error.__context__ is None


def test_f4_journal_store_marker_input_gives_a_clean_error(tmp_path):
    directory = tmp_path / f"missing-{MARKER}"
    with pytest.raises(journal_store.StoreError) as info:
        journal_store.JournalStore.open(directory)
    error = info.value
    assert error.code == "journal_path_invalid"
    _assert_clean_error(error, "journal_path_invalid")
    assert error.__context__ is None


def test_f4_recovery_journal_marker_input_gives_a_clean_error(tmp_path):
    """The wrapped ``SourceError`` must not survive in ``__context__``: a raise
    inside an ``except`` block keeps it there even with ``from None``, so the
    shell raises after the ``try`` statement, like every other journal module.
    """
    _directory, _clock, _ids, journal = make(tmp_path, "f4-rj")
    try:
        bad_source = js.SourceRecord(
            source_group=js.source_group_digest(CG1_KEY),
            alerts=(
                js.SourceAlert(fingerprint=MARKER_INVALID, status="firing", values=None, starts_at=None),
            ),
            truncated_alerts=0, body_digest="a" * 64, provenance=js.HTTP_PROVENANCE,
        )
        with pytest.raises(rj.JournalError) as info:
            journal.admit(bad_source)
        error = info.value
        assert error.args == ("source_invalid",)
        assert error.__cause__ is None
        assert MARKER not in repr(error)
        assert MARKER not in str(error)
        assert error.__context__ is None
    finally:
        journal.close()


def test_f4_marker_absent_from_snapshot_and_anchor_and_db_bytes(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "f4-snap")
    try:
        bad = js.SourceRecord(
            source_group=js.source_group_digest(CG1_KEY),
            alerts=(
                js.SourceAlert(fingerprint=MARKER_INVALID, status="firing", values=None, starts_at=None),
            ),
            truncated_alerts=0, body_digest="a" * 64, provenance=js.HTTP_PROVENANCE,
        )
        with pytest.raises(rj.JournalError) as info:
            journal.admit(bad)
        assert info.value.args == ("source_invalid",)
        snapshot_blob = json.dumps(journal.snapshot())
        assert MARKER not in snapshot_blob
        anchor_bytes = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
        assert MARKER.encode("ascii") not in anchor_bytes
        db_bytes = (directory / journal_store.DB_FILENAME).read_bytes()
        assert MARKER.encode("ascii") not in db_bytes
    finally:
        journal.close()


# =============================================================================
# F5: AST rules over all five journal modules
# =============================================================================

_MODULE_NAMES = (
    "journal_source", "journal_records", "journal_reducer", "journal_store", "recovery_journal",
)

_IMPORT_ALLOWLISTS = {
    "journal_source": frozenset({"__future__", "dataclasses", "math", "re"}),
    "journal_records": frozenset(
        {"__future__", "dataclasses", "hashlib", "re", "collections", "types", "datetime"},
    ),
    "journal_reducer": frozenset({"__future__", "dataclasses", "hashlib", "collections", "types"}),
    "journal_store": frozenset({
        "__future__", "dataclasses", "errno", "fcntl", "hashlib", "os", "sqlite3", "stat",
        "struct", "sys", "collections", "pathlib",
    }),
    "recovery_journal": frozenset(
        {"__future__", "dataclasses", "threading", "time", "uuid", "collections", "pathlib", "types"},
    ),
}

_BANNED_MODULES = frozenset({"socket", "subprocess", "http", "logging"})


def _module_path(name: str) -> pathlib.Path:
    return REPOSITORY / "grafana_jsm_sandbox" / f"{name}.py"


def _module_ast(name: str) -> ast.Module:
    text = _module_path(name).read_text(encoding="utf-8")
    return ast.parse(text, filename=str(_module_path(name)))


@pytest.mark.parametrize("name", _MODULE_NAMES)
def test_f5_import_allowlist_is_exact(name):
    tree = _module_ast(name)
    top_level: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                top_level.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            target = node.func
            is_dunder_import = isinstance(target, ast.Name) and target.id == "__import__"
            is_importlib = isinstance(target, ast.Attribute) and target.attr == "import_module"
            assert not is_dunder_import and not is_importlib, (name, "dynamic import call found")
    assert top_level == _IMPORT_ALLOWLISTS[name], name


@pytest.mark.parametrize("name", _MODULE_NAMES)
def test_f5_except_bodies_match_the_module_discipline(name):
    # Every journal module, the shell included: "assign a code, raise fresh
    # after the try". journal_reducer has no try/except at all (it only ever
    # rejects already decoded, already-typed data with direct `_fail_replay`
    # calls), so its empty handler list passes vacuously.
    tree = _module_ast(name)
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass)), (
                name, handler.lineno, type(statement).__name__,
            )
        for inner in ast.walk(handler):
            assert not isinstance(inner, ast.Raise), (name, inner.lineno)


def _raise_ids_inside_except(tree: ast.Module) -> set[int]:
    """Every ``ast.Raise`` node reachable from inside some ``except`` body --
    a raise outside any handler has no active exception to suppress, so
    ``from None`` is not "applicable" to it (plenty of direct, unconditional
    raises in these modules correctly omit it).
    """
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Raise):
                    inside.add(id(inner))
    return inside


@pytest.mark.parametrize("name", _MODULE_NAMES)
def test_f5_every_raise_inside_except_uses_from_none(name):
    tree = _module_ast(name)
    inside = _raise_ids_inside_except(tree)
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or id(node) not in inside:
            continue
        if node.exc is None:
            continue  # a bare `raise` re-raises the active exception unchanged
        if isinstance(node.exc, ast.Name):
            continue  # `raise error` (re-raising a caught exception object, unchanged)
        cause_is_none = isinstance(node.cause, ast.Constant) and node.cause.value is None
        if not cause_is_none:
            offenders.append(node.lineno)
    assert offenders == [], (name, offenders)


@pytest.mark.parametrize("name", _MODULE_NAMES)
def test_f5_no_print_logging_subprocess_socket_or_http(name):
    tree = _module_ast(name)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = (getattr(node, "module", None) or "")
            names = {alias.name for alias in node.names}
            assert module.split(".")[0] not in _BANNED_MODULES, name
            assert _BANNED_MODULES.isdisjoint(names), name
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "print", (name, node.lineno)


def test_f5_no_update_or_delete_dml_outside_the_schema_ddl():
    text = _module_path("journal_store").read_text(encoding="utf-8")
    start = text.index("SCHEMA_SQL = (")
    end = text.index("\n)\n", start) + len("\n)\n")
    outside_ddl = text[:start] + text[end:]
    offenders = list(re.finditer(r"\bUPDATE\b|\bDELETE\b", outside_ddl))
    assert offenders == []


def test_f5_open_and_os_open_only_in_journal_store():
    for name in _MODULE_NAMES:
        if name == "journal_store":
            continue
        tree = _module_ast(name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                if isinstance(target, ast.Name) and target.id == "open":
                    pytest.fail(f"{name}:{node.lineno} calls builtin open(")
                if (
                    isinstance(target, ast.Attribute) and target.attr == "open"
                    and isinstance(target.value, ast.Name) and target.value.id == "os"
                ):
                    pytest.fail(f"{name}:{node.lineno} calls os.open(")


# =============================================================================
# F6: hold stickiness after a persisted journal_truncated
# =============================================================================


@pytest.fixture(scope="module")
def f6_held_image(tmp_path_factory):
    base = tmp_path_factory.mktemp("f6") / "journal"
    base.mkdir(mode=0o700)
    clock, ids = SeqClock(), SeqIds()
    journal = rj.create_recovery_journal(base, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    journal.close()

    pristine_db = (base / journal_store.DB_FILENAME).read_bytes()
    wal_path = base / journal_store.WAL_FILENAME
    pristine_wal = wal_path.read_bytes() if wal_path.exists() else None
    pre_hold_anchor = (base / journal_store.ANCHOR_FILENAME).read_bytes()

    (base / journal_store.DB_FILENAME).unlink()  # DB absent, anchor still valid -> journal_truncated
    clock2, ids2 = SeqClock(), SeqIds()
    held = rj.open_recovery_journal(base, wall_clock=clock2.wall, mono_clock=clock2.mono, id_factory=ids2)
    assert held.hold == ("journal_truncated", "recovery")
    assert held.snapshot()["hold"]["persisted"] is True
    held.close()

    return {
        "directory": base, "pristine_db": pristine_db, "pristine_wal": pristine_wal,
        "pre_hold_anchor": pre_hold_anchor,
    }


def test_f6a_restoring_pristine_db_and_wal_leaves_it_held(f6_held_image, tmp_path):
    info = f6_held_image
    directory = copy_image(info["directory"], tmp_path, "f6a")
    _restore_bytes(directory / journal_store.DB_FILENAME, info["pristine_db"])
    if info["pristine_wal"] is not None:
        _restore_bytes(directory / journal_store.WAL_FILENAME, info["pristine_wal"])
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_truncated", "recovery")
    finally:
        journal.close()


def test_f6b_zeroing_the_newest_hold_slot_leaves_it_held(f6_held_image, tmp_path):
    info = f6_held_image
    directory = copy_image(info["directory"], tmp_path, "f6b")
    store = journal_store.JournalStore.open(directory)
    counter = store.anchor.counter
    store.close()
    newest_offset = journal_store.ANCHOR_SLOT_OFFSETS[counter % 2]
    anchor_path = directory / journal_store.ANCHOR_FILENAME
    raw = bytearray(anchor_path.read_bytes())
    raw[newest_offset:newest_offset + journal_store.ANCHOR_SLOT_BYTES] = (
        b"\x00" * journal_store.ANCHOR_SLOT_BYTES
    )
    anchor_path.write_bytes(bytes(raw))

    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_truncated", "recovery")
    finally:
        journal.close()


def test_f6c_zeroing_both_slots_gives_anchor_invalid(f6_held_image, tmp_path):
    info = f6_held_image
    directory = copy_image(info["directory"], tmp_path, "f6c")
    anchor_path = directory / journal_store.ANCHOR_FILENAME
    anchor_path.write_bytes(b"\x00" * journal_store.ANCHOR_BYTES)

    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_anchor_invalid", "recovery")
        assert journal.snapshot()["hold"]["persisted"] is False
    finally:
        journal.close()


def test_f6d_consistent_rollback_of_anchor_and_db_clears_the_hold_silently(f6_held_image, tmp_path):
    """The documented non-claim: restoring the anchor AND the db to an
    earlier mutually-consistent state is undetectable and opens ready."""
    info = f6_held_image
    directory = copy_image(info["directory"], tmp_path, "f6d")
    _restore_bytes(directory / journal_store.ANCHOR_FILENAME, info["pre_hold_anchor"])
    _restore_bytes(directory / journal_store.DB_FILENAME, info["pristine_db"])
    if info["pristine_wal"] is not None:
        _restore_bytes(directory / journal_store.WAL_FILENAME, info["pristine_wal"])

    # A fresh, high-offset id sequence: this open goes all the way to ready
    # and mints a real restart_recovery (unlike a/b/c, which return held
    # before ever minting more than a throwaway boot id), so its ids must
    # not collide with the ones the fixture already spent on this same
    # journal_uuid's genesis/admission (an id_factory only promises fresh
    # IDs across one live process, never across two independent low-start
    # counters run against the same on-disk history).
    clock, ids = SeqClock(), SeqIds(start=1_000)
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.state == "ready"
    finally:
        journal.close()


# =============================================================================
# F7: process holds leave anchor/DB/WAL bytes unchanged
# =============================================================================


@pytest.fixture(scope="module")
def f7_base_image(tmp_path_factory):
    base = tmp_path_factory.mktemp("f7") / "journal"
    base.mkdir(mode=0o700)
    clock, ids = SeqClock(), SeqIds()
    journal = rj.create_recovery_journal(base, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    journal.close()
    return base


def test_f7_clock_fault_leaves_files_unchanged(tmp_path):
    directory, _clock, _ids, journal = make(tmp_path, "f7-clock")
    try:
        before = _file_bytes(directory)
        journal._wall_clock = lambda: -1
        with pytest.raises(rj.JournalError) as info:
            journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        assert info.value.code == "journal_clock_invalid"
        assert journal.hold == ("journal_clock_invalid", "process")
        assert _file_bytes(directory) == before
    finally:
        journal.close()


def test_f7_open_io_failure_leaves_files_unchanged(tmp_path, f7_base_image, monkeypatch):
    directory = copy_image(f7_base_image, tmp_path, "f7-io")
    before = _file_bytes(directory)

    def failing_connect(self):
        raise OSError(errno.EIO, "simulated")

    monkeypatch.setattr(journal_store.JournalStore, "_connect", failing_connect)
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_open_failed", "process")
        assert journal.snapshot()["hold"]["persisted"] is False
    finally:
        monkeypatch.undo()
        journal.close()
    assert _file_bytes(directory) == before


def test_f7_append_time_id_overlap_leaves_files_unchanged(tmp_path):
    directory, _clock, ids, journal = make(tmp_path, "f7-overlap")
    try:
        first = journal.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
        before = _file_bytes(directory)
        fresh_id = ids()
        journal._id_factory = ReplayIds(ids, [first.admission_id, fresh_id])
        with pytest.raises(rj.JournalError) as info:
            journal.admit(source(CG1_KEY, (PC, "firing", (("A", "1"),))))
        assert info.value.code == "journal_divergence"
        assert journal.hold == ("journal_divergence", "process")
        assert _file_bytes(directory) == before
    finally:
        journal.close()


# =============================================================================
# F8: classification by verification order
# =============================================================================


def _replace_row(directory, event_seq, event_id, event_type, body, digest):
    """Overwrite one stored row's columns in place: the only way to build a
    tampered-but-consistent image, since the append-only triggers forbid a
    plain UPDATE. The trigger is dropped and then recreated byte-for-byte, so
    the schema still matches ``_reference_schema_rows()`` exactly afterward.
    """
    raw = sqlite3.connect(str(directory / journal_store.DB_FILENAME))
    try:
        raw.execute("DROP TRIGGER journal_events_no_update")
        raw.execute(
            "UPDATE journal_events SET event_id=?, event_type=?, body=?, record_digest=? "
            "WHERE event_seq=?",
            (event_id, event_type, body, digest, event_seq),
        )
        raw.execute(journal_store.SCHEMA_SQL[1])  # journal_events_no_update, verbatim
        raw.commit()
    finally:
        raw.close()


def _digest_of(body: bytes) -> str:
    return hashlib.sha256(b"rj.record.v1\x00" + body).hexdigest()


def _admission_row(directory):
    store = journal_store.JournalStore.open(directory)
    try:
        record = next(r for r in store.rows() if r.event_type == "admission")
    finally:
        store.close()
    return record


def _admission_and_dedupe_rows(directory):
    store = journal_store.JournalStore.open(directory)
    try:
        rows = list(store.rows())
    finally:
        store.close()
    admission = next(r for r in rows if r.event_type == "admission")
    dedupe = next(
        (r for r in rows if r.position.event_seq == admission.position.event_seq + 1), None,
    )
    return admission, dedupe


def test_f8a_un_resigned_flip_gives_recovery_record_invalid_persisted(checkpointed_base, tmp_path):
    directory = copy_image(checkpointed_base[0], tmp_path, "f8a")
    record = _admission_row(directory)
    flipped = bytearray(record.body)
    flipped[10] ^= 0xFF
    _replace_row(
        directory, record.position.event_seq, record.event_id, record.event_type,
        bytes(flipped), record.record_digest,  # digest NOT recomputed: un-re-signed
    )
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_record_invalid", "recovery")
        assert journal.snapshot()["hold"]["persisted"] is True
    finally:
        journal.close()


def _f8_resigned_mutation(directory, mutate, *, rechain_next=False):
    """Mutate the stored admission row and re-sign it. When ``rechain_next``
    is set, the following (dedupe) row's ``prev_record_digest`` is also
    updated to the admission's new digest and re-signed: needed whenever the
    admission mutation is NOT itself a structural rejection (so the row
    pipeline reaches the following row), or its stale prev-digest would stop
    the scan one row early with ``journal_chain_broken`` instead of reaching
    the deeper check this test means to exercise. Both rows are read from the
    store *before* any write, since a fresh read after mutating admission
    would already be broken by the very staleness this rechains away.
    """
    admission, dedupe = _admission_and_dedupe_rows(directory)
    envelope = json.loads(admission.body)
    mutate(envelope)
    body = canonical_json(envelope, ascii_only=True)
    digest = _digest_of(body)
    _replace_row(
        directory, admission.position.event_seq, envelope["event_id"], envelope["event_type"],
        body, digest,
    )
    if rechain_next and dedupe is not None:
        dedupe_env = json.loads(dedupe.body)
        dedupe_env["prev_record_digest"] = digest
        dedupe_body = canonical_json(dedupe_env, ascii_only=True)
        dedupe_digest = _digest_of(dedupe_body)
        _replace_row(
            directory, dedupe.position.event_seq, dedupe_env["event_id"], dedupe_env["event_type"],
            dedupe_body, dedupe_digest,
        )


def test_f8b_resigned_commit_size_9_gives_process_schema_unsupported(checkpointed_base, tmp_path):
    directory = copy_image(checkpointed_base[0], tmp_path, "f8b")
    _f8_resigned_mutation(directory, lambda env: env.__setitem__("commit_size", 9))
    # Captured after the tamper (a raw connection's own checkpoint-on-close
    # can materialize or drop the -wal file as a pure side effect of opening
    # any WAL-mode connection at all -- irrelevant test-harness noise, not
    # evidence either way). The anchor is what the plan claims stays
    # untouched for a never-persisted process hold, so that is what is
    # compared byte-for-byte.
    before_anchor = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_schema_unsupported", "process")
        assert journal.snapshot()["hold"]["persisted"] is False
    finally:
        journal.close()
    after_anchor = (directory / journal_store.ANCHOR_FILENAME).read_bytes()
    assert after_anchor == before_anchor


def test_f8c_resigned_schema_version_2_gives_process_schema_unsupported(checkpointed_base, tmp_path):
    directory = copy_image(checkpointed_base[0], tmp_path, "f8c")
    _f8_resigned_mutation(directory, lambda env: env.__setitem__("schema_version", 2))
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_schema_unsupported", "process")
        assert journal.snapshot()["hold"]["persisted"] is False
    finally:
        journal.close()


def test_f8d_resigned_unknown_enum_gives_process_schema_unsupported(checkpointed_base, tmp_path):
    directory = copy_image(checkpointed_base[0], tmp_path, "f8d")

    def mutate(env):
        env["data"]["decision"] = "not-a-real-decision"

    _f8_resigned_mutation(directory, mutate)
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_schema_unsupported", "process")
        assert journal.snapshot()["hold"]["persisted"] is False
    finally:
        journal.close()


def test_f8e_resigned_semantic_change_gives_recovery_replay_mismatch(checkpointed_base, tmp_path):
    directory = copy_image(checkpointed_base[0], tmp_path, "f8e")

    def mutate(env):
        env["data"]["decision"] = "held"  # the base image has no active dispatch hold

    _f8_resigned_mutation(directory, mutate, rechain_next=True)
    clock, ids = SeqClock(), SeqIds()
    journal = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    try:
        assert journal.hold == ("journal_replay_mismatch", "recovery")
        assert journal.snapshot()["hold"]["persisted"] is True
    finally:
        journal.close()


# =============================================================================
# F9: rollback cannot brick (R2)
# =============================================================================


def test_f9_restoring_the_pre_mutation_record_after_a_process_hold_opens_ready(
    checkpointed_base, tmp_path,
):
    directory = copy_image(checkpointed_base[0], tmp_path, "f9")
    record = _admission_row(directory)
    original_body, original_digest = record.body, record.record_digest

    mutated_env = json.loads(original_body)
    mutated_env["commit_size"] = 9
    mutated_body = canonical_json(mutated_env, ascii_only=True)
    mutated_digest = _digest_of(mutated_body)
    _replace_row(
        directory, record.position.event_seq, record.event_id, record.event_type,
        mutated_body, mutated_digest,
    )

    clock, ids = SeqClock(), SeqIds()
    held = rj.open_recovery_journal(directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids)
    assert held.hold == ("journal_schema_unsupported", "process")
    held.close()

    # "Roll forward": the record is restored exactly as it was (the plan's
    # metaphor for a rolled-forward binary meeting bytes it understands).
    _replace_row(
        directory, record.position.event_seq, record.event_id, record.event_type,
        original_body, original_digest,
    )
    # High-offset ids: this second open goes all the way to ready and mints a
    # real restart_recovery, so its ids must not collide with the base
    # image's own genesis/admission ids (see the identical note on F6d).
    clock2, ids2 = SeqClock(), SeqIds(start=1_000)
    reopened = rj.open_recovery_journal(
        directory, wall_clock=clock2.wall, mono_clock=clock2.mono, id_factory=ids2,
    )
    try:
        assert reopened.state == "ready"
        assert reopened.snapshot()["counts"]["admissions"] == 1
    finally:
        reopened.close()
