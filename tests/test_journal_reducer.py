"""Tests for ``journal_reducer`` (unit 15, module 2; ticket 37 cases B1-B12,
plus the cross-module half of A5). Built directly against ``journal_records``
and ``journal_source`` signatures, never trusting the reducer's own plan
output as ground truth: expected results are computed by hand or by the
independent ``reference_model`` below.

Scenario data for B1 comes from the ticket-31 fixture matrix (F01, F02, F04,
F05, F06, F07) and the cross-group reclaim sequence (q7), read against
``.scratch/.../reviews/ticket-31/fixture-spec.md`` and ``source-checks.md``.
Source groups use short synthetic ``groupKey`` strings rather than the
captured ones: A9's golden values are Implementer A's job, not this module's.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import pathlib
import time

import pytest

from grafana_jsm_sandbox import journal_records as jr
from grafana_jsm_sandbox import journal_reducer as jrd
from grafana_jsm_sandbox import journal_source as js

REPOSITORY = pathlib.Path(__file__).resolve().parent.parent

BOOT_A = "11111111-1111-1111-1111-111111111111"
BOOT_B = "66666666-6666-6666-6666-666666666666"
BOOT_C = "77777777-7777-7777-7777-777777777777"
JOURNAL_UUID = "22222222-2222-2222-2222-222222222222"
WALL_A = "2026-09-23T00:00:00.000000Z"
WALL_B = "2026-09-23T00:01:00.000000Z"
WALL_C = "2026-09-23T00:02:00.000000Z"

PF = "5e8d72dc87b1ff35"
PC = "6cd7e206a0716d2d"
PX = "8e2d9556f6c757b5"
PA = "f09facf2b8f5b694"
PB = "4396dcd5ddc23476"
PD = "4bde20aac01f95a2"
PE = "b3587dd72657d226"

CG1_KEY = '{}:{alertname="Service error rate is elevated", grafana_folder="demo"}'
CG2_KEY = '{}:{alertname="Service error rate is elevated", grafana_folder="demo2"}'
CG3_KEY = '{}:{alertname="third"}'
CG1 = js.source_group_digest(CG1_KEY)
CG2 = js.source_group_digest(CG2_KEY)


# === Shared helpers ==========================================================


def stamp(*, boot_id: str = BOOT_A, wall_time: str = WALL_A, mono_us: int = 0) -> jr.Stamp:
    return jr.Stamp(boot_id=boot_id, wall_time=wall_time, mono_us=mono_us)


def expect_replay(code, fn, *args, **kwargs):
    with pytest.raises(jrd.ReplayError) as info:
        fn(*args, **kwargs)
    error = info.value
    assert error.code == code
    assert error.args == (code,)
    assert error.__cause__ is None
    assert error.__context__ is None
    return error


_Values = tuple[tuple[str, str], ...] | None
_Member = tuple[str, str, _Values]


def alerts(*members: _Member) -> tuple[js.SourceAlert, ...]:
    """``members`` are ``(fingerprint, status, values)`` triples, already in
    fingerprint order (as a real caller must supply them).
    """
    return tuple(
        js.SourceAlert(fingerprint=fp, status=status, values=values, starts_at=None)
        for fp, status, values in members
    )


def source(
    group_key: str, *members: _Member, truncated: int | None = 0,
) -> js.SourceRecord:
    return js.SourceRecord(
        source_group=js.source_group_digest(group_key), alerts=alerts(*members),
        truncated_alerts=truncated, body_digest="0" * 64, provenance=js.HTTP_PROVENANCE,
    )


class Journal:
    """A tiny live-path harness: mints sequential admission ids, keeps the
    flat record history, and always runs the live path's own
    ``verify_commit``/``apply_delta`` pair before mutating the projection --
    exactly what the (later) shell does before it ever writes anything.
    """

    def __init__(self, bounds: jrd.JournalBounds | None = None, *, boot_id: str = BOOT_A) -> None:
        self.projection = jrd.new_projection()
        self.history: list[jr.Record] = []
        self._boot_id = boot_id
        self._wall = WALL_A
        self._mono = 0
        self._counter = 0
        genesis = jrd.plan_genesis(
            journal_uuid=JOURNAL_UUID, bounds=bounds or jrd.DEFAULT_BOUNDS,
            event_id=self._next_id("genesis"), stamp=self._stamp(),
        )
        self._commit(genesis)

    def _next_id(self, label: str) -> str:
        self._counter += 1
        return f"{label}-{self._counter:04d}"

    def _stamp(self) -> jr.Stamp:
        self._mono += 1
        return stamp(boot_id=self._boot_id, wall_time=self._wall, mono_us=self._mono)

    def _commit(self, plan: jrd.Plan) -> dict:
        delta = jrd.verify_commit(self.projection, plan.records)
        jrd.apply_delta(self.projection, delta)
        self.history.extend(plan.records)
        return dict(plan.outcome)

    def admit(self, src: js.SourceRecord) -> dict:
        admission_id = self._next_id("adm")
        plan = jrd.plan_admission(
            self.projection, src, admission_id=admission_id,
            dedupe_event_id=self._next_id("ded"), stamp=self._stamp(),
        )
        if isinstance(plan, jrd.CapacityRefusal):
            return {"refusal": plan}
        outcome = self._commit(plan)
        outcome["admission_id"] = admission_id
        return outcome

    def restart(self, *, boot_id: str, wall_time: str) -> dict:
        self._boot_id = boot_id
        self._wall = wall_time
        self._mono = 0
        plan = jrd.plan_restart(
            self.projection, event_id=self._next_id("restart"), stamp=self._stamp(),
            anchor_lag=0, wal_found=None,
        )
        assert isinstance(plan, jrd.Plan)
        return self._commit(plan)

    def pending_map(self) -> dict[str, jrd.PendingEntry]:
        return dict(self.projection.pending)


# === B1: scenario tables (F01, F02, F04, F05, F06, F07, cross-group, q7) ====


def test_b1_f01_identity_repeat_is_suppressed():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    first = j.admit(a)
    assert first["result"] == "admitted"
    second = j.admit(a)
    assert second["result"] == "suppressed"
    assert second["superseded"] == ()
    assert j.pending_map()[PF].admission_id == first["admission_id"]


def test_b1_f02_changed_value_both_admit():
    j = Journal()
    line1 = source(CG1_KEY, (PF, "firing", (("A", "0.1144"), ("B", "1"))))
    line2 = source(CG1_KEY, (PF, "firing", (("A", "0.1957"), ("B", "1"))))
    first = j.admit(line1)
    assert first["result"] == "admitted"
    second = j.admit(line2)
    assert second["result"] == "pending_reduced"
    assert second["superseded"] == ((PF, first["admission_id"]),)


def test_b1_f04_resolved_then_firing_reduces_to_latest_firing():
    j = Journal()
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
    assert step16["result"] == "admitted"
    step18 = j.admit(line18)
    assert step18["result"] == "pending_reduced"
    assert step18["superseded"] == ((PF, step16["admission_id"]),)
    step20 = j.admit(line20)
    assert step20["result"] == "pending_reduced"
    assert step20["superseded"] == (
        (PF, step18["admission_id"]), (PC, step16["admission_id"]), (PX, step16["admission_id"]),
    )
    pending = j.pending_map()
    for fp in (PC, PF, PX):
        assert pending[fp].admission_id == step20["admission_id"]
        assert pending[fp].status == "firing"


def test_b1_f05_firing_then_resolved():
    j = Journal()
    firing = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    resolved = source(CG1_KEY, (PF, "resolved", (("A", "0"), ("B", "0"))))
    first = j.admit(firing)
    assert first["result"] == "admitted"
    repeat = j.admit(firing)
    assert repeat["result"] == "suppressed"
    final = j.admit(resolved)
    assert final["result"] == "pending_reduced"
    assert j.pending_map()[PF].status == "resolved"


def test_b1_f06_omission_is_never_resolved():
    j = Journal()
    seed = source(
        CG1_KEY, (PF, "firing", (("A", "1"),)), (PC, "firing", (("A", "1"),)),
        (PX, "firing", (("A", "1"),)),
    )
    step_seed = j.admit(seed)
    assert step_seed["result"] == "admitted"
    repeat = j.admit(seed)
    assert repeat["result"] == "suppressed"
    pf_only = source(CG1_KEY, (PF, "firing", (("A", "2"),)))
    step_pf = j.admit(pf_only)
    assert step_pf["result"] == "pending_reduced"
    assert step_pf["superseded"] == ((PF, step_seed["admission_id"]),)
    pending = j.pending_map()
    assert pending[PC].admission_id == step_seed["admission_id"]
    assert pending[PC].status == "firing"
    assert pending[PX].admission_id == step_seed["admission_id"]
    assert pending[PF].admission_id == step_pf["admission_id"]


def test_b1_f07_mixed_groups_keep_separate_baselines():
    j = Journal()
    cg1 = source(
        CG1_KEY, (PF, "firing", (("A", "1"),)), (PC, "firing", (("A", "1"),)),
        (PX, "firing", (("A", "1"),)),
    )
    cg2 = source(
        CG2_KEY, (PB, "resolved", (("A", "0"),)), (PD, "resolved", (("A", "0"),)),
        (PE, "resolved", (("A", "0"),)), (PA, "resolved", (("A", "0"),)),
    )
    step1 = j.admit(cg1)
    assert step1["result"] == "admitted"
    step2 = j.admit(cg2)
    # Different groups: an equal/disjoint tuple in another group is never
    # suppressed, and nothing is superseded since none of PA/PB/PD/PE existed.
    assert step2["result"] == "admitted"
    pending = j.pending_map()
    assert set(pending) == {PC, PF, PX, PA, PB, PD, PE}
    assert pending[PC].source_group == CG1
    assert pending[PA].source_group == CG2


def test_b1_cross_group_equal_tuple_is_admitted_not_suppressed():
    j = Journal()
    cg1_a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    cg2_a = source(CG2_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    first = j.admit(cg1_a)
    assert first["result"] == "admitted"
    second = j.admit(cg2_a)
    # An equal tuple in another group is never suppressed. PF is already
    # pending (globally, from CG1), so this supersedes it -- pending_reduced,
    # not suppressed -- and CG2 gets its own fresh baseline.
    assert second["result"] == "pending_reduced"
    assert second["superseded"] == ((PF, first["admission_id"]),)
    assert j.projection.baselines[CG2].admission_id == second["admission_id"]
    assert j.projection.baselines[CG1].admission_id == first["admission_id"]


def test_b1_q7_cross_group_reclaim():
    """The cross-group reclaim sequence: a suppressed arrival keeps its own
    group's baseline and reclaims only entries another group currently
    holds, never creating a new pending entry.
    """
    j = Journal()
    cg1_resolved = source(CG1_KEY, (PF, "resolved", (("A", "0"), ("B", "0"))))
    cg2_firing = source(CG2_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))

    step1 = j.admit(cg1_resolved)
    assert step1["result"] == "admitted"
    assert j.pending_map()[PF].source_group == CG1

    step2 = j.admit(cg2_firing)
    assert step2["result"] == "pending_reduced"
    assert step2["superseded"] == ((PF, step1["admission_id"]),)
    assert j.pending_map()[PF].source_group == CG2

    step3 = j.admit(cg1_resolved)
    assert step3["result"] == "suppressed"  # CG1's baseline (step1) is unchanged and matches
    assert step3["superseded"] == ((PF, step2["admission_id"]),)  # reclaimed from CG2
    pending = j.pending_map()
    assert pending[PF].admission_id == step3["admission_id"]
    assert pending[PF].source_group == CG1
    assert len(pending) == 1  # never created a second entry


# === B2: the worked A/B/A/A example, plus restart then A (held) ============


def test_b2_worked_a_b_a_a_then_restart_a():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    b = source(CG1_KEY, (PF, "firing", (("A", "2"), ("B", "1"))))

    step1 = j.admit(a)  # adm1
    assert step1["result"] == "admitted"
    step2 = j.admit(b)  # adm2, superseded PF <- adm1
    assert step2["result"] == "pending_reduced"
    assert step2["superseded"] == ((PF, step1["admission_id"]),)
    step3 = j.admit(a)  # adm3, superseded PF <- adm2 (latest-admitted, not latest-completed)
    assert step3["result"] == "pending_reduced"
    assert step3["superseded"] == ((PF, step2["admission_id"]),)
    step4 = j.admit(a)  # adm4, suppressed against adm3's baseline
    assert step4["result"] == "suppressed"
    assert step4["decision"] == "admitted"  # no dispatch hold active yet
    assert j.pending_map()[PF].admission_id == step3["admission_id"]  # unchanged by step4

    j.restart(boot_id=BOOT_B, wall_time=WALL_B)
    assert jrd.dispatch_holds(j.projection) == ("restart_recovery",)
    step5 = j.admit(a)  # adm5, still suppressed, now held
    assert step5["result"] == "suppressed"
    assert step5["decision"] == "held"
    assert step5["dispatch_holds"] == ("restart_recovery",)


def test_b2_variant_on_a_constructed_projection():
    """The plan's variant: a projection with an existing baseline (adm1) and
    empty pending, run only against the pure reducer -- not through a full
    admit sequence, since consumption is a later unit's concern.
    """
    p = jrd.new_projection()
    p.journal_uuid = JOURNAL_UUID
    p.generation = 1
    p.bounds = jrd.DEFAULT_BOUNDS
    p.boot_id = BOOT_A
    p.seen_boot_ids = {BOOT_A}
    p.head = jr.Head(generation=1, commit_seq=1, event_seq=1, record_digest="a" * 64)

    a = source(CG1_KEY, (PF, "firing", (("A", "1"), ("B", "1"))))
    b = source(CG1_KEY, (PF, "firing", (("A", "2"), ("B", "1"))))
    key_a = js.dedupe_key(a)
    p.baselines[CG1] = jrd.Baseline("adm1", key_a, True)

    decision_b = jrd._decide(p, b, "adm2")
    assert decision_b.result == "admitted"  # nothing pending yet
    p.pending[PF] = jrd.PendingEntry(PF, "adm2", 1, CG1, "firing", (("A", "2"), ("B", "1")))
    p.baselines[CG1] = decision_b.baseline_after

    decision_a = jrd._decide(p, a, "adm3")
    assert decision_a.result == "pending_reduced"
    assert decision_a.superseded == ((PF, "adm2"),)
    p.pending[PF] = jrd.PendingEntry(PF, "adm3", 2, CG1, "firing", (("A", "1"), ("B", "1")))
    p.baselines[CG1] = decision_a.baseline_after

    decision_a2 = jrd._decide(p, a, "adm4")
    assert decision_a2.result == "suppressed"


# === B3: suppressed neutrality ===============================================


def test_b3_suppressed_neutrality_no_cross_group():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    before = dict(j.projection.pending)
    before_baselines = dict(j.projection.baselines)
    j.admit(a)  # suppressed repeat, no cross-group entries to reclaim
    assert j.projection.pending == before
    assert j.projection.baselines == before_baselines


def test_b3_suppressed_reclaims_only_cross_group_entries():
    j = Journal()
    cg1 = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    cg2 = source(CG2_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(cg1)
    j.admit(cg2)  # PF now held by CG2
    step = j.admit(cg1)  # suppressed against CG1's own unchanged baseline; reclaims PF
    assert step["result"] == "suppressed"
    assert j.pending_map()[PF].source_group == CG1


def test_b3_suppressed_repeat_after_pending_clear_creates_nothing():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    j.projection.pending.clear()  # test-only: simulate a later unit's consumption
    step = j.admit(a)
    assert step["result"] == "suppressed"
    assert step["superseded"] == ()
    assert j.pending_map() == {}


# === B4: capacity with small bounds =========================================


def _small_bounds(**overrides) -> jrd.JournalBounds:
    base = {
        "max_admissions": 2, "max_pending_fingerprints": 2,
        "ordinary_bytes": 112 * 2**20, "total_bytes": 128 * 2**20,
    }
    base.update(overrides)
    return jrd.JournalBounds(**base)


def test_b4_admissions_capacity_counts_suppressed_arrivals():
    j = Journal(bounds=_small_bounds(max_admissions=2))
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    j.admit(a)  # suppressed, still counts
    refused = j.admit(a)["refusal"]
    assert refused.code == "capacity_admissions"
    assert refused.limit == 2
    assert refused.observed == 2
    assert refused.requested == 1


def test_b4_pending_capacity_refuses_only_new_fingerprints():
    j = Journal(bounds=_small_bounds(max_admissions=100, max_pending_fingerprints=2))
    first = source(CG1_KEY, (PF, "firing", (("A", "1"),)), (PC, "firing", (("A", "1"),)))
    j.admit(first)  # exactly at the pending limit (2)
    # A reclaim/overlap never trips it: re-admitting an overlapping-but-changed
    # arrival supersedes existing entries, adding zero new fingerprints.
    changed = source(CG1_KEY, (PF, "firing", (("A", "2"),)), (PC, "firing", (("A", "2"),)))
    repeat = j.admit(changed)
    assert repeat["result"] == "pending_reduced"
    assert len(repeat["superseded"]) == 2
    # A genuinely new fingerprint is refused.
    new_fp = source(CG1_KEY, (PX, "firing", (("A", "1"),)))
    refused = j.admit(new_fp)["refusal"]
    assert refused.code == "capacity_pending"
    assert refused.limit == 2
    assert refused.observed == 2
    assert refused.requested == 1


def test_b4_bytes_refusal_while_recovery_records_still_fit():
    # ordinary_bytes tiny; total_bytes has headroom, so capacity_hold and
    # restart_recovery (recovery-class, checked against total_bytes) still fit.
    bounds = _small_bounds(max_admissions=1000, max_pending_fingerprints=1000, ordinary_bytes=1)
    j = Journal(bounds=bounds)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    refused = j.admit(a)["refusal"]
    assert refused.code == "capacity_bytes"
    hold_plan = jrd.plan_capacity_hold(
        j.projection, refused, event_id="hold-1", stamp=stamp(mono_us=999),
        refused_source_digest=js.source_digest(a),
    )
    assert isinstance(hold_plan, jrd.Plan)  # fits in the reserve
    restart_stamp = stamp(boot_id=BOOT_B, wall_time=WALL_B, mono_us=1)
    restart_plan = jrd.plan_restart(
        j.projection, event_id="restart-1", stamp=restart_stamp, anchor_lag=0, wal_found=None,
    )
    assert isinstance(restart_plan, jrd.Plan)


def test_b4_at_most_one_capacity_hold_per_code():
    j = Journal(bounds=_small_bounds(max_admissions=1))
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    refused_1 = j.admit(a)["refusal"]
    plan_1 = jrd.plan_capacity_hold(
        j.projection, refused_1, event_id="hold-1", stamp=stamp(mono_us=100),
        refused_source_digest=js.source_digest(a),
    )
    delta = jrd.verify_commit(j.projection, plan_1.records)
    jrd.apply_delta(j.projection, delta)
    refused_2 = j.admit(a)["refusal"]
    plan_2 = jrd.plan_capacity_hold(
        j.projection, refused_2, event_id="hold-2", stamp=stamp(mono_us=101),
        refused_source_digest=js.source_digest(a),
    )
    assert plan_2 is None


def test_b4_replay_uses_bounds_recorded_in_genesis():
    j = Journal(bounds=_small_bounds(max_admissions=1))
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    replayed = jrd.replay(j.history)
    assert replayed.bounds == _small_bounds(max_admissions=1)
    refused = jrd.plan_admission(
        replayed, a, admission_id="adm-x", dedupe_event_id="ded-x", stamp=stamp(mono_us=500),
    )
    assert isinstance(refused, jrd.CapacityRefusal)


# === B5: property test against an independent reference model ==============


def _reference_step(
    baselines: dict[str, tuple[str, str, bool]], pending: dict[str, tuple[str, str, str, object]],
    admission_id: str, src: js.SourceRecord,
) -> None:
    """One incremental step of the I12/I13 reference model (mutates
    ``baselines``/``pending`` in place). Factored out of ``reference_model``
    so a property test can apply it once per admitted arrival -- O(1) amortized
    per step -- instead of rescanning the whole arrival history on every step.
    """
    group = src.source_group
    key = js.dedupe_key(src)
    complete = src.truncated_alerts == 0
    prior = baselines.get(group)
    suppressed = complete and prior is not None and prior[2] and prior[1] == key
    if suppressed:
        for alert in src.alerts:
            held = pending.get(alert.fingerprint)
            if held is not None and held[1] != group:
                pending[alert.fingerprint] = (admission_id, group, alert.status, alert.values)
        return
    baselines[group] = (admission_id, key, complete)
    for alert in src.alerts:
        pending[alert.fingerprint] = (admission_id, group, alert.status, alert.values)


def reference_model(
    arrivals: list[tuple[str, js.SourceRecord]],
) -> tuple[dict[str, tuple[str, str, bool]], dict[str, tuple[str, str, str, object]]]:
    """Independent scan-the-history model of I12 (the dedupe baseline) and
    I13 (pending is the latest arrival per fingerprint). Written without
    calling any reducer plan/verify/apply function, so a bug shared between
    this and the reducer's own logic is unlikely.

    ``arrivals`` is the ordered sequence of ``(admission_id, source)`` pairs
    that were actually admitted (never one a capacity refusal blocked).
    Returns ``(baselines, pending)``:
      * ``baselines[group] = (admission_id, dedupe_key, complete)``
      * ``pending[fingerprint] = (admission_id, source_group, status, values)``
    """
    baselines: dict[str, tuple[str, str, bool]] = {}
    pending: dict[str, tuple[str, str, str, object]] = {}
    for admission_id, src in arrivals:
        _reference_step(baselines, pending, admission_id, src)
    return baselines, pending


def _reference_from_projection(p: jrd.Projection) -> tuple[dict, dict]:
    baselines = {
        group: (baseline.admission_id, baseline.dedupe_key, baseline.complete)
        for group, baseline in p.baselines.items()
    }
    pending = {
        fp: (entry.admission_id, entry.source_group, entry.status, entry.values)
        for fp, entry in p.pending.items()
    }
    return baselines, pending


_VALUE_POOL = ("0", "1", "0.1", "2", None)


def _random_source(rng, groups: tuple[str, ...], fingerprints: tuple[str, ...]) -> js.SourceRecord:
    group_key = rng.choice(groups)
    statuses = ("firing", "resolved")
    count = rng.randint(1, len(fingerprints))
    chosen = sorted(rng.sample(fingerprints, count))
    members = []
    for fp in chosen:
        status = rng.choice(statuses)
        if rng.random() < 0.2:
            values = None
        else:
            values = (("A", rng.choice(_VALUE_POOL)),)
        members.append((fp, status, values))
    truncated = rng.choice((0, 0, 0, 2, None))
    return source(group_key, *members, truncated=truncated)


def _b5_pool() -> tuple[js.SourceRecord, ...]:
    """~8 prebuilt sources, built once (never per-step): fingerprint PF is
    shared across CG1 and CG2 (cross-group reclaim), CG1 also holds a
    same-fingerprint different-value arrival (moves CG1's own baseline) and a
    truncated twin of the CG1/PF arrival (never suppressible -- B12/G2), a
    values=None / resolved arrival covers the remaining shape, a multi-alert
    arrival covers a source with more than one member, and an
    ``truncated_alerts=None`` (unknown truncation) arrival covers the other
    never-suppressible shape (B12/G2's sibling: "unknown" is as incomplete as
    "some truncated").
    """
    return (
        source(CG1_KEY, (PF, "firing", (("A", "1"),))),
        source(CG2_KEY, (PF, "firing", (("A", "1"),))),
        source(CG1_KEY, (PF, "firing", (("A", "2"),))),
        source(CG3_KEY, (PC, "resolved", None)),
        source(CG1_KEY, (PF, "firing", (("A", "1"),)), truncated=2),
        source(CG2_KEY, (PA, "firing", (("A", "1"),))),
        source(CG1_KEY, (PF, "firing", (("A", "1"),)), (PX, "resolved", None)),
        source(CG2_KEY, (PC, "firing", (("A", "1"),)), truncated=None),
    )


def test_b5_property_against_reference_model(record_property):
    import random

    bounds = dataclasses.replace(jrd.DEFAULT_BOUNDS, max_admissions=30, max_pending_fingerprints=3)
    pool = _b5_pool()
    seeds, steps = 60, 60
    totals = {
        "admitted": 0, "pending_reduced": 0, "suppressed": 0, "reclaim": 0, "capacity_refusal": 0,
    }
    started = time.monotonic()
    for seed in range(seeds):
        rng = random.Random(seed)
        j = Journal(bounds=bounds)
        ref_baselines: dict[str, tuple[str, str, bool]] = {}
        ref_pending: dict[str, tuple[str, str, str, object]] = {}
        for step in range(steps):
            if rng.random() < 0.1:
                j.restart(boot_id=f"b5-boot-{seed}-{step}", wall_time=WALL_B)
                continue
            src = rng.choice(pool)
            outcome = j.admit(src)
            if "refusal" in outcome:
                totals["capacity_refusal"] += 1
                continue
            totals[outcome["result"]] += 1
            if outcome["result"] == "suppressed" and outcome["superseded"]:
                totals["reclaim"] += 1
            _reference_step(ref_baselines, ref_pending, outcome["admission_id"], src)
            live_baselines, live_pending = _reference_from_projection(j.projection)
            assert live_baselines == ref_baselines, (seed, step)
            assert live_pending == ref_pending, (seed, step)
        # B6 already covers every prefix; one full-history replay per seed
        # (not every 10th step) is enough to catch a live/replay divergence.
        replayed = jrd.replay(j.history)
        assert jrd.state_digest(replayed) == jrd.state_digest(j.projection)
    elapsed = time.monotonic() - started
    record_property("b5_wall_time_seconds", elapsed)
    for key, value in totals.items():
        assert value > 0, (key, totals)


@pytest.fixture
def record_property(record_testsuite_property):
    return record_testsuite_property


# === B6: prefix property =====================================================


def test_b6_commit_boundary_prefix_replays_to_live_state():
    import random

    for seed in range(5):
        rng = random.Random(1000 + seed)
        j = Journal()
        boundaries = [len(j.history)]
        for step in range(20):
            action = rng.random()
            if action < 0.15:
                j.restart(boot_id=f"pfx-boot-{seed}-{step}", wall_time=WALL_B)
            else:
                src = _random_source(rng, (CG1_KEY, CG2_KEY), (PF, PC, PX))
                j.admit(src)
            boundaries.append(len(j.history))
        live_projections = []
        p = jrd.new_projection()
        for group in jrd.group_commits(j.history):
            jrd.apply_delta(p, jrd.verify_commit(p, group))
            live_projections.append(jrd.state_digest(p))
        # Every commit-boundary cut must replay to exactly that step's state.
        # `boundaries[0]` is the length right after genesis, which is also
        # `live_projections[0]`'s state, so the two line up index-for-index.
        for cut, digest in zip(boundaries, live_projections, strict=True):
            replayed = jrd.replay(j.history[:cut])
            assert jrd.state_digest(replayed) == digest
        # A cut inside a group (mid-commit) is a tail-incomplete stream.
        if len(j.history) > 1:
            mid_cut = boundaries[1] - 1 if boundaries[1] > 1 else None
            if mid_cut and mid_cut > 0:
                expect_replay("replay_tail_incomplete", jrd.replay, j.history[:mid_cut])


# === B7: chain and framing edits =============================================


def _two_admissions(bounds=None):
    j = Journal(bounds=bounds)
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    b = source(CG1_KEY, (PC, "firing", (("A", "1"),)))
    j.admit(b)
    return j


def test_b7_delete_a_commit_breaks_framing():
    j = _two_admissions()
    # Drop the middle commit (the first admission pair): commit_seq jumps.
    genesis = j.history[0:1]
    second_pair = j.history[3:5]
    tampered = genesis + second_pair
    expect_replay("replay_framing", jrd.replay, tampered)


def test_b7_duplicate_a_commit_breaks_framing():
    j = _two_admissions()
    tampered = j.history[0:3] + j.history[1:3]  # replay the same commit twice
    expect_replay("replay_framing", jrd.replay, tampered)


def test_b7_swapped_records_break_the_chain():
    j = _two_admissions()
    # Swap the two single-record capacity/admission-pair boundaries so a
    # later record's prev_record_digest no longer matches its predecessor,
    # while event_seq/commit_seq stay superficially in range.
    tampered = list(j.history)
    tampered[3], tampered[1] = tampered[1], tampered[3]
    with pytest.raises(jrd.ReplayError) as info:
        jrd.replay(tampered)
    assert info.value.code in ("replay_chain", "replay_framing")


def test_b7_generation_change_without_reset():
    j = _two_admissions()
    p = jrd.new_projection()
    apply_prefix(p, j.history[:3])
    restart_plan = jrd.plan_restart(
        p, event_id="restart-gen", stamp=stamp(boot_id=BOOT_B, wall_time=WALL_B, mono_us=1),
        anchor_lag=0, wal_found=None,
    )
    (restart_record,) = restart_plan.records
    envelope = _envelope(restart_record)
    envelope["journal_generation"] = 2
    tampered = _reseal(envelope)
    expect_replay("replay_generation", jrd.verify_commit, p, (tampered,))


def test_b7_genesis_outside_generation_1_breaks_generation():
    genesis_plan = jrd.plan_genesis(
        journal_uuid=JOURNAL_UUID, bounds=jrd.DEFAULT_BOUNDS, event_id="genesis-g7", stamp=stamp(),
    )
    (genesis,) = genesis_plan.records
    envelope = _envelope(genesis)
    envelope["journal_generation"] = 7
    tampered = _reseal(envelope)
    expect_replay("replay_generation", jrd.verify_commit, jrd.new_projection(), (tampered,))
    expect_replay("replay_generation", jrd.replay, [tampered])


def test_b7_boot_reuse_on_restart():
    j = _two_admissions()
    p = jrd.new_projection()
    apply_prefix(p, j.history[:3])
    restart_plan = jrd.plan_restart(
        p, event_id="restart-x", stamp=stamp(boot_id=BOOT_A, wall_time=WALL_B, mono_us=999),
        anchor_lag=0, wal_found=None,
    )
    assert isinstance(restart_plan, jrd.Plan)
    expect_replay("replay_boot", jrd.verify_commit, p, restart_plan.records)


def test_b7_mono_us_regression_within_a_boot():
    j = _two_admissions()
    p = jrd.new_projection()
    apply_prefix(p, j.history[:3])
    a = source(CG1_KEY, (PX, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        p, a, admission_id="adm-regress", dedupe_event_id="ded-regress",
        stamp=stamp(boot_id=BOOT_A, wall_time=WALL_A, mono_us=0),
    )
    assert isinstance(plan, jrd.Plan)
    expect_replay("replay_clock", jrd.verify_commit, p, plan.records)


def test_b7_boot_change_outside_restart_recovery():
    j = _two_admissions()
    p = jrd.new_projection()
    apply_prefix(p, j.history[:3])
    a = source(CG1_KEY, (PX, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        p, a, admission_id="adm-newboot", dedupe_event_id="ded-newboot",
        stamp=stamp(boot_id=BOOT_B, wall_time=WALL_B, mono_us=1),
    )
    assert isinstance(plan, jrd.Plan)
    expect_replay("replay_boot", jrd.verify_commit, p, plan.records)


def apply_prefix(p: jrd.Projection, records: list[jr.Record]) -> None:
    for group in jrd.group_commits(records):
        jrd.apply_delta(p, jrd.verify_commit(p, group))


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
    """Rebuild+re-sign a record from a (possibly mutated) envelope, exactly
    the "tampered but re-signed" threat model: digests and the chain stay
    internally valid, but the content is not what the live path produced.
    """
    if prev_digest is not None:
        envelope["prev_record_digest"] = prev_digest
    draft = jr.Draft(
        event_id=envelope["event_id"], event_type=envelope["event_type"], actor=envelope["actor"],
        ids=envelope["ids"], data=envelope["data"],
    )
    position = jr.Position(
        journal_generation=envelope["journal_generation"], event_seq=envelope["event_seq"],
        commit_seq=envelope["commit_seq"], commit_index=envelope["commit_index"],
        commit_size=envelope["commit_size"], prev_record_digest=envelope["prev_record_digest"],
    )
    record_stamp = stamp(
        boot_id=envelope["boot_id"], wall_time=envelope["wall_time"], mono_us=envelope["mono_us"],
    )
    return jr.seal(draft, position, record_stamp)


# === B8: commit shapes give replay_shape ====================================


def test_b8_admission_alone_gives_replay_shape():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="solo-adm", dedupe_event_id="solo-ded",
        stamp=stamp(mono_us=99),
    )
    admission_record, _dedupe_record = plan.records
    original_position = admission_record.position
    solo_position = jr.Position(
        journal_generation=original_position.journal_generation,
        event_seq=original_position.event_seq, commit_seq=original_position.commit_seq,
        commit_index=0, commit_size=1, prev_record_digest=original_position.prev_record_digest,
    )
    solo = jr.seal(
        jr.Draft(
            event_id="solo-adm", event_type="admission", actor="receiver",
            ids={"admission_id": "solo-adm"},
            data=jr.thaw(admission_record.data),
        ),
        solo_position, stamp(mono_us=99),
    )
    expect_replay("replay_shape", jrd.verify_commit, j.projection, (solo,))


def test_b8_mismatched_admission_id_gives_replay_shape():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="adm-real", dedupe_event_id="ded-real",
        stamp=stamp(mono_us=1),
    )
    admission_record, dedupe_record = plan.records
    envelope = _envelope(dedupe_record)
    envelope["ids"] = {"admission_id": "adm-other"}
    tampered = _reseal(envelope)
    expect_replay("replay_shape", jrd.verify_commit, j.projection, (admission_record, tampered))


def test_b8_reversed_order_gives_replay_shape():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="adm-rev", dedupe_event_id="ded-rev", stamp=stamp(mono_us=1),
    )
    admission_record, dedupe_record = plan.records
    admission_env, dedupe_env = _envelope(admission_record), _envelope(dedupe_record)
    admission_index, dedupe_index = admission_env["commit_index"], dedupe_env["commit_index"]
    admission_env["commit_index"], dedupe_env["commit_index"] = dedupe_index, admission_index
    admission_seq, dedupe_seq = admission_env["event_seq"], dedupe_env["event_seq"]
    admission_env["event_seq"], dedupe_env["event_seq"] = dedupe_seq, admission_seq
    reversed_dedupe = _reseal(dedupe_env, prev_digest=j.projection.head.record_digest)
    reversed_admission = _reseal(admission_env, prev_digest=reversed_dedupe.record_digest)
    reversed_pair = (reversed_dedupe, reversed_admission)
    expect_replay("replay_shape", jrd.verify_commit, j.projection, reversed_pair)


def test_b8_three_record_group_gives_replay_shape():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    prev = j.projection.head.record_digest
    seq = j.projection.head.event_seq
    commit_seq = j.projection.head.commit_seq + 1
    records = []
    shared_stamp = stamp(mono_us=1)
    for index in range(3):
        position = jr.Position(
            journal_generation=1, event_seq=seq + index + 1, commit_seq=commit_seq,
            commit_index=index, commit_size=3, prev_record_digest=prev,
        )
        record = jr.seal(
            jr.Draft(
                event_id=f"triple-{index}", event_type="capacity_hold", actor="receiver", ids={},
                data={
                    "code": "capacity_admissions", "limit": 1, "observed": 1, "requested": 1,
                    "refused_source_digest": js.source_digest(a), "action": "set",
                },
            ),
            position, shared_stamp,
        )
        records.append(record)
        prev = record.record_digest
    expect_replay("replay_shape", jrd.verify_commit, j.projection, tuple(records))


def test_b8_unknown_shape_gives_replay_shape():
    j = Journal()
    dedupe_alone_position = jr.Position(
        journal_generation=1, event_seq=j.projection.head.event_seq + 1,
        commit_seq=j.projection.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=j.projection.head.record_digest,
    )
    dedupe_alone = jr.seal(
        jr.Draft(
            event_id="lone-dedupe", event_type="dedupe_decision", actor="receiver",
            ids={"admission_id": "adm-nope"},
            data={
                "rule": "latest-admitted-v1", "result": "admitted", "source_group": CG1,
                "dedupe_key": "0" * 64, "baseline_before": None,
                "baseline_after": {
                    "admission_id": "adm-nope", "complete": True, "dedupe_key": "0" * 64,
                },
                "superseded": (), "pending_count_after": 1,
            },
        ),
        dedupe_alone_position, stamp(mono_us=1),
    )
    expect_replay("replay_shape", jrd.verify_commit, j.projection, (dedupe_alone,))


def test_b8_non_record_inputs_give_replay_shape_before_any_field_is_read():
    genesis = Journal().history[0]
    p = jrd.new_projection()
    expect_replay("replay_shape", jrd.verify_commit, p, [None])
    expect_replay("replay_shape", jrd.verify_commit, p, [object()])
    expect_replay("replay_shape", jrd.verify_commit, p, (genesis, None))


# === B9: re-signed semantic divergence gives replay_mismatch ================


def _seeded_pending_reduced_plan(j: Journal) -> jrd.Plan:
    """Admit PF once, then build (never commit) a second admission that
    supersedes it -- pending_reduced, with a non-empty ``superseded`` -- so
    every dedupe field below has a real value to diverge from.
    """
    seed = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(seed)
    a = source(CG1_KEY, (PF, "firing", (("A", "2"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="adm-mut", dedupe_event_id="ded-mut", stamp=stamp(mono_us=99),
    )
    assert isinstance(plan, jrd.Plan)
    return plan


def _mutate_dedupe_field(j: Journal, field: str, value: object):
    plan = _seeded_pending_reduced_plan(j)
    admission_record, dedupe_record = plan.records
    envelope = _envelope(dedupe_record)
    envelope["data"][field] = value
    tampered = _reseal(envelope)
    return j.projection, (admission_record, tampered)


@pytest.mark.parametrize("field,value", [
    ("result", "admitted"),
    ("superseded", ()),
    ("pending_count_after", 999),
    ("dedupe_key", "f" * 64),
    ("source_group", CG2),
    ("baseline_before", None),
])
def test_b9_dedupe_field_divergence(field, value):
    j = Journal()
    p, records = _mutate_dedupe_field(j, field, value)
    expect_replay("replay_mismatch", jrd.verify_commit, p, records)


def test_b9_admission_arrival_seq_divergence():
    j = Journal()
    plan = _seeded_pending_reduced_plan(j)
    admission_record, dedupe_record = plan.records
    envelope = _envelope(admission_record)
    envelope["data"]["arrival_seq"] = 999
    tampered_admission = _reseal(envelope)
    # Re-chain the dedupe record onto the tampered admission's new digest,
    # without touching its own (still correct) content.
    dedupe_envelope = _envelope(dedupe_record)
    tampered_dedupe = _reseal(dedupe_envelope, prev_digest=tampered_admission.record_digest)
    expect_replay(
        "replay_mismatch", jrd.verify_commit, j.projection, (tampered_admission, tampered_dedupe),
    )


def test_b9_baseline_after_complete_flag_divergence():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="adm-c", dedupe_event_id="ded-c", stamp=stamp(mono_us=5),
    )
    admission_record, dedupe_record = plan.records
    envelope = _envelope(dedupe_record)
    baseline_after = dict(envelope["data"]["baseline_after"])
    baseline_after["complete"] = False
    envelope["data"]["baseline_after"] = baseline_after
    tampered = _reseal(envelope)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (admission_record, tampered))


def _rechain_dedupe_onto(dedupe_record: jr.Record, new_prev_digest: str) -> jr.Record:
    """Re-seal ``dedupe_record`` unchanged except its predecessor link, so it
    follows a just-tampered (and therefore re-digested) admission record.
    """
    envelope = _envelope(dedupe_record)
    return _reseal(envelope, prev_digest=new_prev_digest)


def test_b9_admission_decision_divergence():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="adm-d", dedupe_event_id="ded-d", stamp=stamp(mono_us=5),
    )
    admission_record, dedupe_record = plan.records
    envelope = _envelope(admission_record)
    envelope["data"]["decision"] = "held"
    tampered = _reseal(envelope)
    rechained_dedupe = _rechain_dedupe_onto(dedupe_record, tampered.record_digest)
    expect_replay(
        "replay_mismatch", jrd.verify_commit, j.projection, (tampered, rechained_dedupe),
    )


def test_b9_source_digest_divergence():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    other = source(CG1_KEY, (PC, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        j.projection, a, admission_id="adm-e", dedupe_event_id="ded-e", stamp=stamp(mono_us=5),
    )
    admission_record, dedupe_record = plan.records
    envelope = _envelope(admission_record)
    envelope["data"]["source"] = js.source_to_json(other)
    tampered = _reseal(envelope)
    rechained_dedupe = _rechain_dedupe_onto(dedupe_record, tampered.record_digest)
    expect_replay(
        "replay_mismatch", jrd.verify_commit, j.projection, (tampered, rechained_dedupe),
    )


def test_b9_capacity_observation_divergence():
    j = Journal(bounds=_small_bounds(max_admissions=1))
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    refusal = jrd.CapacityRefusal("capacity_admissions", 1, 1, 1)
    plan = jrd.plan_capacity_hold(
        j.projection, refusal, event_id="hold-e", stamp=stamp(mono_us=50),
        refused_source_digest=js.source_digest(a),
    )
    (hold_record,) = plan.records
    envelope = _envelope(hold_record)
    envelope["data"]["observed"] = 0
    tampered = _reseal(envelope)
    expect_replay("replay_mismatch", jrd.verify_commit, j.projection, (tampered,))


def test_b9_restart_recovered_head_divergence():
    j = _two_admissions()
    p = jrd.new_projection()
    apply_prefix(p, j.history[:3])
    plan = jrd.plan_restart(
        p, event_id="restart-e", stamp=stamp(boot_id=BOOT_B, wall_time=WALL_B, mono_us=1),
        anchor_lag=0, wal_found=None,
    )
    (restart_record,) = plan.records
    envelope = _envelope(restart_record)
    recovered = dict(envelope["data"]["recovered"])
    recovered["event_seq"] = recovered["event_seq"] + 1
    envelope["data"]["recovered"] = recovered
    tampered = _reseal(envelope)
    expect_replay("replay_mismatch", jrd.verify_commit, p, (tampered,))


# === T2: replay-side re-checks for forged histories (six capacity/budget
# checks with no test of their own) =========================================


def test_b9_capacity_hold_forged_while_genuinely_below_capacity_gives_replay_mismatch():
    """``plan_capacity_hold`` never itself checks that a refusal was genuine
    (only the live shell ever hands it a real ``CapacityRefusal``); a forged
    hold naming the CURRENT true limit/observed but a ``requested`` that does
    not actually overflow it must still be caught at replay by
    ``_verify_capacity_hold``'s own "was this genuinely over capacity" check.
    """
    j = Journal(bounds=_small_bounds(max_admissions=5))
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    p = j.projection
    fake_refusal = jrd.CapacityRefusal(
        "capacity_admissions", p.bounds.max_admissions, p.admission_count, 1,
    )
    plan = jrd.plan_capacity_hold(
        p, fake_refusal, event_id="hold-below", stamp=stamp(mono_us=50),
        refused_source_digest="a" * 64,
    )
    assert isinstance(plan, jrd.Plan)  # not None: the code has no active hold yet
    expect_replay("replay_mismatch", jrd.verify_commit, p, plan.records)


def test_b9_capacity_hold_forged_for_an_already_active_code_gives_replay_mismatch():
    """``plan_capacity_hold`` refuses (returns ``None``) a second hold for a
    code already active -- the live shell never even builds one. A forged
    record for that already-active code, otherwise perfectly genuine (real
    limit/observed, and a real overflow), must still be caught by
    ``_verify_capacity_hold``'s own "not already active" check.
    """
    j = Journal(bounds=_small_bounds(max_admissions=1))
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    refused = j.admit(a)["refusal"]
    hold_plan = jrd.plan_capacity_hold(
        j.projection, refused, event_id="hold-1", stamp=stamp(mono_us=50),
        refused_source_digest=js.source_digest(a),
    )
    delta = jrd.verify_commit(j.projection, hold_plan.records)
    jrd.apply_delta(j.projection, delta)
    p = j.projection
    assert "capacity_admissions" in p.dispatch_holds

    # A hand-sealed second hold for the same code, chained onto the real head:
    # plan_capacity_hold itself would refuse to build this (it returns None),
    # so this reproduces exactly what it would have produced minus that gate.
    position = jr.Position(
        journal_generation=p.generation, event_seq=p.head.event_seq + 1,
        commit_seq=p.head.commit_seq + 1, commit_index=0, commit_size=1,
        prev_record_digest=p.head.record_digest,
    )
    forged = jr.seal(
        jr.Draft(
            event_id="hold-2-forged", event_type="capacity_hold", actor="receiver", ids={},
            data={
                "code": "capacity_admissions", "limit": p.bounds.max_admissions,
                "observed": p.admission_count, "requested": 1,
                "refused_source_digest": js.source_digest(a), "action": "set",
            },
        ),
        position, stamp(mono_us=60),
    )
    expect_replay("replay_mismatch", jrd.verify_commit, p, (forged,))


def test_b9_restart_forged_over_the_total_bytes_budget_gives_replay_mismatch():
    """``plan_restart`` and ``_verify_restart`` share one formula for the
    total-bytes gate; the only way to test the verify-side copy on its own is
    a genuinely-built restart record replayed against a projection whose
    (tampered-genesis-style) bounds are smaller than what built it.
    """
    j = Journal()  # default, generous bounds
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    p = j.projection
    plan = jrd.plan_restart(
        p, event_id="restart-budget", stamp=stamp(boot_id=BOOT_B, wall_time=WALL_B, mono_us=1),
        anchor_lag=0, wal_found=None,
    )
    assert isinstance(plan, jrd.Plan)
    (restart_record,) = plan.records
    charge = len(restart_record.body) + jrd.RECORD_OVERHEAD_BYTES
    p2 = copy.copy(p)
    p2.bounds = dataclasses.replace(p2.bounds, total_bytes=p2.logical_bytes + charge - 1)
    expect_replay("replay_mismatch", jrd.verify_commit, p2, plan.records)


def test_b9_admission_pair_forged_over_the_admission_limit_gives_replay_mismatch():
    j = Journal()
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    p = j.projection
    a = source(CG1_KEY, (PC, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        p, a, admission_id="adm-limit", dedupe_event_id="ded-limit", stamp=stamp(mono_us=100),
    )
    assert isinstance(plan, jrd.Plan)
    p2 = copy.copy(p)
    p2.bounds = dataclasses.replace(p2.bounds, max_admissions=p2.admission_count)
    expect_replay("replay_mismatch", jrd.verify_commit, p2, plan.records)


def test_b9_admission_pair_forged_over_the_pending_limit_gives_replay_mismatch():
    j = Journal()
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    p = j.projection
    a = source(CG3_KEY, (PC, "firing", (("A", "1"),)))  # a genuinely new fingerprint
    plan = jrd.plan_admission(
        p, a, admission_id="adm-pending", dedupe_event_id="ded-pending", stamp=stamp(mono_us=100),
    )
    assert isinstance(plan, jrd.Plan)
    p2 = copy.copy(p)
    p2.bounds = dataclasses.replace(p2.bounds, max_pending_fingerprints=len(p2.pending))
    expect_replay("replay_mismatch", jrd.verify_commit, p2, plan.records)


def test_b9_admission_pair_forged_over_the_ordinary_bytes_limit_gives_replay_mismatch():
    j = Journal()
    j.admit(source(CG1_KEY, (PF, "firing", (("A", "1"),))))
    p = j.projection
    a = source(CG1_KEY, (PC, "firing", (("A", "1"),)))
    plan = jrd.plan_admission(
        p, a, admission_id="adm-bytes", dedupe_event_id="ded-bytes", stamp=stamp(mono_us=100),
    )
    assert isinstance(plan, jrd.Plan)
    admission_record, dedupe_record = plan.records
    charge = len(admission_record.body) + len(dedupe_record.body) + 2 * jrd.RECORD_OVERHEAD_BYTES
    p2 = copy.copy(p)
    p2.bounds = dataclasses.replace(p2.bounds, ordinary_bytes=p2.logical_bytes + charge - 1)
    expect_replay("replay_mismatch", jrd.verify_commit, p2, plan.records)


# === B10: pending_digest/state_digest ========================================


def test_b10_digests_equal_for_equal_histories_and_order_independent():
    j1 = Journal()
    j2 = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    b = source(CG2_KEY, (PC, "firing", (("A", "1"),)))
    j1.admit(a)
    j1.admit(b)
    j2.admit(a)
    j2.admit(b)
    assert jrd.pending_digest(j1.projection) == jrd.pending_digest(j2.projection)
    assert jrd.state_digest(j1.projection) == jrd.state_digest(j2.projection)

    # Rebuild j2's pending dict with reversed insertion order -- must not matter.
    reordered = dict(reversed(list(j2.projection.pending.items())))
    j2.projection.pending = reordered
    assert jrd.pending_digest(j1.projection) == jrd.pending_digest(j2.projection)


@pytest.mark.parametrize("field,new_value", [
    ("arrival_seq", 999), ("admission_id", "other-admission"), ("source_group", CG2),
    ("status", "resolved"), ("values", (("A", "9"),)),
])
def test_b10_digest_changes_on_any_single_pending_field(field, new_value):
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    baseline_pending_digest = jrd.pending_digest(j.projection)
    baseline_state_digest = jrd.state_digest(j.projection)
    original = j.projection.pending[PF]
    j.projection.pending[PF] = dataclasses.replace(original, **{field: new_value})
    assert jrd.pending_digest(j.projection) != baseline_pending_digest
    assert jrd.state_digest(j.projection) != baseline_state_digest


def test_b10_digest_changes_on_a_baseline_field():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)))
    j.admit(a)
    baseline_digest = jrd.state_digest(j.projection)
    original = j.projection.baselines[CG1]
    j.projection.baselines[CG1] = dataclasses.replace(original, complete=False)
    assert jrd.state_digest(j.projection) != baseline_digest


def test_b10_pending_digest_at_1024_entries():
    p = jrd.new_projection()
    for i in range(1024):
        fp = f"fp-{i:05d}"
        p.pending[fp] = jrd.PendingEntry(fp, f"adm-{i}", i, CG1, "firing", (("A", "1"),))
    digest = jrd.pending_digest(p)
    assert isinstance(digest, str)
    assert len(digest) == 64


# === B11 (AST): the purity import allowlist =================================

MODULE_PATH = REPOSITORY / "grafana_jsm_sandbox" / "journal_reducer.py"
ALLOWED_TOP_LEVEL_IMPORTS = frozenset({
    "__future__", "dataclasses", "hashlib", "collections", "types",
})


def _module_ast() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))


def test_b11_imports_match_the_exact_allowlist():
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
    assert (0, "collections.abc", ("Iterable", "Iterator", "Sequence")) in from_imports
    assert (0, "types", ("MappingProxyType",)) in from_imports
    assert (1, "forwarder_json", ("canonical_json", "tagged_digest")) in from_imports
    # Exactly these six `from` imports: __future__, collections.abc, types,
    # forwarder_json, journal_records and journal_source.
    assert len(from_imports) == 6


def test_b11_no_clock_random_os_filesystem_sqlite_or_threading():
    tree = _module_ast()
    banned_modules = {
        "time", "random", "os", "pathlib", "sqlite3", "threading", "socket", "subprocess",
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", None) or ""
            names = [alias.name for alias in node.names]
            assert module.split(".")[0] not in banned_modules
            assert not banned_modules.intersection(names)


def test_b11_except_bodies_are_only_assign_annassign_or_pass():
    tree = _module_ast()
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    for handler in handlers:
        for statement in handler.body:
            assert isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Pass))


# === Cross-module half of A5: genesis bounds are checked against the frozen
# V1_BOUND_CEILINGS, never against the reducer's own mutable DEFAULT_BOUNDS. ==


def test_a5_genesis_bounds_unaffected_by_monkeypatched_default_bounds(monkeypatch):
    tiny_default = jrd.JournalBounds(
        max_admissions=1, max_pending_fingerprints=1, ordinary_bytes=1, total_bytes=1,
    )
    monkeypatch.setattr(jrd, "DEFAULT_BOUNDS", tiny_default)
    max_bounds = jrd.JournalBounds(
        max_admissions=jr.V1_BOUND_CEILINGS["max_admissions"],
        max_pending_fingerprints=jr.V1_BOUND_CEILINGS["max_pending_fingerprints"],
        ordinary_bytes=jr.V1_BOUND_CEILINGS["ordinary_bytes"],
        total_bytes=jr.V1_BOUND_CEILINGS["total_bytes"],
    )
    # plan_genesis takes its bounds explicitly, not from DEFAULT_BOUNDS at all;
    # the patched (tiny) module-level default must not leak into it.
    plan = jrd.plan_genesis(
        journal_uuid=JOURNAL_UUID, bounds=max_bounds, event_id=BOOT_A, stamp=stamp(),
    )
    assert plan.outcome["bounds"] == max_bounds
    # verify_commit re-derives genesis bounds against V1_BOUND_CEILINGS itself
    # (an import, not DEFAULT_BOUNDS), so the ceiling values are still accepted.
    p = jrd.new_projection()
    delta = jrd.verify_commit(p, plan.records)
    jrd.apply_delta(p, delta)
    assert p.bounds == max_bounds


# === B12: truncation ==========================================================


def test_b12_truncated_repeat_is_never_suppressed():
    j = Journal()
    a = source(CG1_KEY, (PF, "firing", (("A", "1"),)), truncated=0)
    first = j.admit(a)
    assert first["result"] == "admitted"

    truncated_repeat = source(CG1_KEY, (PF, "firing", (("A", "1"),)), truncated=2)
    step_truncated = j.admit(truncated_repeat)
    assert step_truncated["result"] == "pending_reduced"  # never suppressed
    assert j.projection.baselines[CG1].complete is False

    null_repeat = source(CG1_KEY, (PF, "firing", (("A", "1"),)), truncated=None)
    step_null = j.admit(null_repeat)
    assert step_null["result"] == "pending_reduced"
    assert j.projection.baselines[CG1].complete is False

    # A later identical *complete* repeat is not suppressed against the
    # incomplete baseline...
    complete_repeat = source(CG1_KEY, (PF, "firing", (("A", "1"),)), truncated=0)
    step_complete = j.admit(complete_repeat)
    assert step_complete["result"] == "pending_reduced"
    assert j.projection.baselines[CG1].complete is True

    # ...but a second complete repeat now is, since the baseline is complete.
    step_second_complete = j.admit(complete_repeat)
    assert step_second_complete["result"] == "suppressed"
