"""Real-store no-launch writer for a replayed restart recovery hold."""

import pytest

from grafana_jsm_sandbox import journal_reducer as reducer
from grafana_jsm_sandbox import journaled_receiver
from grafana_jsm_sandbox.journal_store import StoreError
from grafana_jsm_sandbox.recovery_journal import (
    JournalError,
    ResumeRequest,
    inspect_recovery_journal,
    open_recovery_journal,
)
from tests.test_recovery_journal import (
    CG1_KEY,
    CG2_KEY,
    PC,
    PF,
    make,
    reopen,
    source,
)

JOB = 'job-restart-1'


def _pending_journal(tmp_path, *, bounds=None, name='journal'):
    options = {} if bounds is None else {'bounds': bounds}
    directory, clock, ids, journal = make(tmp_path, name=name, **options)
    admission = journal.admit(source(CG1_KEY, (PF, 'firing', (('A', '1'),))))
    return directory, clock, ids, journal, admission


def test_fresh_journal_cannot_invent_restart_reason(tmp_path):
    _directory, _clock, _ids, journal, admission = _pending_journal(tmp_path)
    with journal:
        before = journal.snapshot()['head']
        with pytest.raises(JournalError, match='run_hold_not_required'):
            journal.record_restart_run_hold(JOB, admission.admission_id)
        assert journal.snapshot()['head'] == before
        assert journal.state == 'ready'


def test_restart_hold_commits_once_and_survives_reopen_and_later_admission(tmp_path):
    directory, clock, ids, journal, admission = _pending_journal(tmp_path)
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        assert restarted.dispatch_holds == ('restart_recovery',)
        before = restarted.snapshot()['head']['commit_seq']
        receipt = restarted.record_restart_run_hold(JOB, admission.admission_id)
        assert (receipt.job_id, receipt.admission_id, receipt.reason, receipt.state) == (
            JOB, admission.admission_id, 'restart_recovery', 'recorded')
        assert receipt.since_commit_seq == before + 1
        assert restarted.snapshot()['run_holds']['count'] == 1
        head = restarted.snapshot()['head']
        retry = restarted.record_restart_run_hold(JOB, admission.admission_id)
        assert retry.state == 'already_recorded'
        assert retry.member_digest == receipt.member_digest
        assert restarted.snapshot()['head'] == head
        restarted.admit(source(CG2_KEY, (PC, 'firing', (('B', '2'),))))
        assert restarted.snapshot()['run_holds']['count'] == 1
    inspected = inspect_recovery_journal(directory)
    assert inspected.report['verdict'] == 'ready'
    assert inspected.report['journal']['run_holds']['count'] == 1
    with reopen(directory, clock, ids) as again:
        retry = again.record_restart_run_hold(JOB, admission.admission_id)
        assert retry.state == 'already_recorded'
        assert retry.since_commit_seq == receipt.since_commit_seq
        assert again.snapshot()['run_holds']['count'] == 1
    assert journaled_receiver.MODE == 'journaled-admission-only'


def test_run_hold_blocks_v1_resume_but_exact_retry_survives(tmp_path):
    directory, clock, ids, journal, admission = _pending_journal(tmp_path)
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        receipt = restarted.record_restart_run_hold(JOB, admission.admission_id)
    token = inspect_recovery_journal(directory).report['journal']['head']['record_digest']
    with open_recovery_journal(
        directory, wall_clock=clock.wall, mono_clock=clock.mono, id_factory=ids,
        resume=ResumeRequest(token=token, operator='local-operator'),
    ) as resumed:
        assert resumed.dispatch_holds == ('restart_recovery',)
        assert resumed.resumed_this_boot is None
        assert [row.event_type for row in resumed._store.rows()][-1] == 'restart_recovery'
        before = resumed.snapshot()['head']
        retry = resumed.record_restart_run_hold(JOB, admission.admission_id)
        assert retry.state == 'already_recorded'
        assert retry.since_commit_seq == receipt.since_commit_seq
        assert resumed.snapshot()['head'] == before
        another = resumed.admit(source(CG2_KEY, (PC, 'firing', (('B', '2'),))))
        assert another.decision == 'held'
        assert resumed.dispatch_holds == ('restart_recovery',)
        assert resumed.state == 'ready'
        with pytest.raises(JournalError, match='journal_divergence'):
            resumed.record_restart_run_hold('job-restart-2', admission.admission_id)
        assert resumed.hold == ('journal_divergence', 'process')


@pytest.mark.parametrize('job,admission_override', [
    (JOB, 'other-admission'),
    ('job-restart-2', None),
])
def test_conflicting_retry_latches_process_hold(tmp_path, job, admission_override):
    directory, clock, ids, journal, admission = _pending_journal(tmp_path)
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        restarted.record_restart_run_hold(JOB, admission.admission_id)
        target = admission.admission_id if admission_override is None else admission_override
        with pytest.raises(JournalError, match='journal_divergence'):
            restarted.record_restart_run_hold(job, target)
        assert restarted.state == 'held'
        assert restarted.hold == ('journal_divergence', 'process')


def test_noncurrent_admission_latches_without_a_run_hold(tmp_path):
    directory, clock, ids, journal, _admission = _pending_journal(tmp_path)
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        with pytest.raises(JournalError, match='journal_divergence'):
            restarted.record_restart_run_hold(JOB, 'missing-admission')
        assert restarted.state == 'held'


def test_clock_and_id_faults_latch_without_claiming_a_hold(tmp_path):
    directory, clock, ids, journal, admission = _pending_journal(tmp_path)
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        restarted._mono_clock = lambda: -1
        with pytest.raises(JournalError, match='journal_clock_invalid'):
            restarted.record_restart_run_hold(JOB, admission.admission_id)
        assert restarted.hold == ('journal_clock_invalid', 'process')
    with reopen(directory, clock, ids) as restarted:
        restarted._id_factory = lambda: 'bad id!'
        with pytest.raises(JournalError, match='journal_divergence'):
            restarted.record_restart_run_hold(JOB, admission.admission_id)
        assert restarted.hold == ('journal_divergence', 'process')


def test_append_failure_latches_and_reopen_has_no_fabricated_hold(tmp_path, monkeypatch):
    directory, clock, ids, journal, admission = _pending_journal(tmp_path)
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        before = restarted.snapshot()['head']

        def fail_append(*_args, **_kwargs):
            raise StoreError('injected')

        monkeypatch.setattr(restarted._store, 'append', fail_append)
        with pytest.raises(JournalError, match='journal_write_failed'):
            restarted.record_restart_run_hold(JOB, admission.admission_id)
        assert restarted.hold == ('journal_write_failed', 'process')
        assert restarted.snapshot()['counts'] is None  # held hides projection
    with reopen(directory, clock, ids) as again:
        assert 'run_holds' not in again.snapshot()
        assert again.snapshot()['head']['commit_seq'] > before['commit_seq']


def test_recovery_capacity_refusal_latches_no_write(tmp_path):
    # First use identical deterministic inputs to measure the exact headroom
    # after restart; a second image has no room for the Run hold record.
    probe_dir, probe_clock, probe_ids, probe, _admission = _pending_journal(
        tmp_path, name='probe')
    probe.close()
    with reopen(probe_dir, probe_clock, probe_ids) as opened:
        limit = opened.snapshot()['bytes']['logical']
    bounds = reducer.JournalBounds(ordinary_bytes=limit, total_bytes=limit)
    directory, clock, ids, journal, admission = _pending_journal(
        tmp_path, bounds=bounds, name='tight')
    journal.close()
    with reopen(directory, clock, ids) as restarted:
        before = restarted.snapshot()['head']
        with pytest.raises(JournalError, match='journal_capacity_recovery'):
            restarted.record_restart_run_hold(JOB, admission.admission_id)
        assert restarted.hold == ('journal_capacity_recovery', 'process')
        assert restarted.snapshot()['head'] is None
    inspected = inspect_recovery_journal(directory)
    assert inspected.report['verdict'] == 'ready'
    assert inspected.report['journal']['head'] == before
    assert 'run_holds' not in inspected.report['journal']
