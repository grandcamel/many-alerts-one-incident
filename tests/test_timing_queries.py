import builtins
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from prototype.run_timing import timing_queries
from prototype.run_timing.executor import Lifecycle
from prototype.run_timing.timing_queries import FixtureDataUnavailable, QueryRejected, TimingQueries

DATA = Path(timing_queries.__file__).with_name('timing_data')
REPO_ROOT = Path(__file__).resolve().parents[1]
METRIC = 'container_memory_usage_bytes{service="recommendation"}'


@pytest.fixture
def adapter():
    return TimingQueries('fixture-one', Lifecycle())


def test_corpus_matches_historical_manifest_and_excludes_ground_truth():
    manifest = json.loads((REPO_ROOT / '.scratch/many-alerts-one-incident/reviews/ticket-23/source-manifest.json').read_text())
    old = {Path(item['path']).name: item for item in manifest['files']}
    assert {p.name for p in DATA.iterdir()} == set(timing_queries.PINNED_INPUTS)
    for name, digest in timing_queries.PINNED_INPUTS.items():
        original = old['notification-cascade.json' if name == 'notification.json' else name]
        raw = (DATA / name).read_bytes()
        assert digest == original['sha256'] == hashlib.sha256(raw).hexdigest()
        assert len(raw) == original['bytes']


def test_notification_catalog_and_response_digest(adapter):
    response = adapter.query('one', 'notification.get', {})
    assert len(response['items'][0]['value']['alerts']) == 7
    assert response['status'] == 'ok' and not response['truncated']
    assert response['scope'] == 'OFFLINE_PINNED_QUERIES_ONLY' and response['native_launch'] == 'CLOSED'
    expected_digest = response.pop('response_sha256')
    canonical = json.dumps(response, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected_digest
    catalog = adapter.query('two', 'metrics.list', {})
    assert len(catalog['items']) == 13
    assert all('series' not in item['value'] and item['projection'] == 'metric_metadata'
               for item in catalog['items'])
    assert METRIC in [item['value']['name'] for item in catalog['items']]


def test_metrics_exact_selector_inclusive_window_and_source_pointer(adapter):
    response = adapter.query('one', 'metrics.query', {'metric': METRIC,
        'since': '2026-09-15T14:01:00Z', 'until': '2026-09-15T14:02:00Z'})
    assert response['matched_count'] == response['returned_count'] == 2
    for item in response['items']:
        assert item['value']['value'] == 188000000 and item['value']['unit'] == 'bytes'
        assert item['projection'] == 'metric_point'
    assert response['items'][0]['source_pointer'] == '/' + METRIC + '/series/11'
    assert adapter.query('two', 'metrics.query', {'metric': 'recommendation'})['status'] == 'not_found'
    empty = adapter.query('three', 'metrics.query', {'metric': METRIC, 'since': '2027-01-01T00:00:00Z'})
    assert empty['status'] == 'ok' and empty['items'] == [] and not empty['truncated']


def test_logs_exact_service_literal_body_and_visible_truncation(adapter):
    response = adapter.query('one', 'logs.query', {'service': 'recommendation',
                                                'contains': 'cache', 'limit': 1})
    assert response['matched_count'] > 1 and response['returned_count'] == 1
    assert response['truncated'] and response['items'][0]['value']['service'] == 'recommendation'
    for i, args in enumerate([{'service': 'recomm'}, {'service': 'Recommendation'},
                              {'contains': '.*'}, {'contains': '$(no-command)'}]):
        empty = adapter.query(f'empty-{i}', 'logs.query', args)
        assert empty['status'] == 'ok' and empty['matched_count'] == 0 and empty['items'] == []


def test_metric_truncation_and_until_only_log_window(adapter):
    points = adapter.query('one', 'metrics.query', {'metric': METRIC, 'limit': 2})
    assert points['matched_count'] == 21 and points['returned_count'] == 2 and points['truncated']
    assert [item['value']['timestamp'] for item in points['items']] == [
        '2026-09-15T13:50:00Z', '2026-09-15T13:51:00Z']
    logs = adapter.query('two', 'logs.query', {'until': '2026-09-15T13:50:00Z'})
    assert logs['status'] == 'ok' and logs['matched_count'] == 1
    assert logs['items'][0]['value']['timestamp'] == '2026-09-15T13:50:00Z'


@pytest.mark.parametrize('key', ['since', 'until'])
@pytest.mark.parametrize('year', ['２０２６', '٢٠٢٦', '2０26'])
def test_unicode_timestamp_digits_cannot_become_empty_success(adapter, key, year):
    with pytest.raises(QueryRejected, match='canonical'):
        adapter.query('one', 'logs.query', {key: year + '-09-15T14:00:00Z'})
    valid = adapter.query('one', 'logs.query', {'since': '2026-09-15T14:00:00Z'})
    assert valid['matched_count'] == 37 and valid['response_id'].endswith('/0001')


def test_trace_summary_does_not_supply_span_attributes_and_detail_is_exact(adapter):
    listed = adapter.query('one', 'traces.list', {'service': 'recommendation'})
    assert listed['matched_count'] == 3
    assert all(item['projection'] == 'trace_summary' and 'spans' not in item['value']
               for item in listed['items'])
    ids = [item['value']['traceId'] for item in listed['items']]
    detail = adapter.query('two', 'traces.get', {'trace_id': ids[0]})
    assert detail['items'][0]['value']['spans'] and detail['items'][0]['projection'] == 'full'
    assert adapter.query('three', 'traces.get', {'trace_id': ids[0][:8]})['status'] == 'not_found'
    assert adapter.query('four', 'traces.list', {'service': 'recommend'})['items'] == []


def test_changes_sort_by_event_time_and_keep_original_source_indexes(adapter):
    response = adapter.query('one', 'changes.list', {})
    assert [item['value']['id'] for item in response['items']] == [413, 411, 412]
    assert [item['source_pointer'] for item in response['items']] == ['/2', '/0', '/1']
    instant = adapter.query('two', 'changes.list', {'since': '2026-09-15T14:02:00Z',
                                                  'until': '2026-09-15T14:02:00Z'})
    assert instant['matched_count'] == 1 and instant['items'][0]['value']['id'] == 412


def test_correlation_and_readback_are_independent_and_not_reused(adapter):
    adapter.lifecycle.advance(12)
    args = {'service': 'recommendation'}
    response = adapter.query('one', 'logs.query', args)
    original = json.loads(json.dumps(response))
    assert response['observed_at_virtual_seconds'] == 12
    args['service'] = 'altered'
    response['items'][0]['value']['body'] = 'forged'
    response['arguments']['service'] = 'forged'
    assert adapter.read_response(response['response_id']) == original
    with pytest.raises(QueryRejected, match='already'):
        adapter.query('one', 'notification.get', {})
    another = TimingQueries('fixture-one', Lifecycle()).query('one', 'logs.query', {})
    assert another['response_id'] != response['response_id']
    with pytest.raises(QueryRejected, match='unknown'):
        adapter.read_response(another['response_id'])


@pytest.mark.parametrize('operation,args', [
    ('shell', {}), ('https://example.invalid', {}), ('logs.query', {'path': '/tmp/other'}),
    ('metrics.query', {}), ('traces.get', {}), ('notification.get', {'service': 'x'}),
    ('logs.query', {'limit': True}), ('logs.query', {'limit': 0}), ('logs.query', {'limit': 101}),
    ('logs.query', {'since': '2026-02-30T00:00:00Z'}),
    ('logs.query', {'since': '2026-09-15T14:00:00+00:00'}),
    ('logs.query', {'since': '2026-09-15T14:00:00Z', 'until': '2026-09-15T13:00:00Z'}),
    ('logs.query', {'contains': 'x' * 257}), ('logs.query', {'service': None}),
    ('logs.query', []),
])
def test_invalid_query_cannot_issue_an_empty_response_or_consume_identity(adapter, operation, args):
    with pytest.raises(QueryRejected):
        adapter.query('one', operation, args)
    result = adapter.query('one', 'changes.list', {})
    assert result['response_id'].endswith('/0001') and result['matched_count'] == 3


@pytest.mark.parametrize('bad', ['../path', 'Uppercase', '', 'x' * 65, None])
def test_invalid_request_identity_is_rejected(adapter, bad):
    with pytest.raises(QueryRejected):
        adapter.query(bad, 'notification.get', {})


def test_revocation_stops_new_queries_but_keeps_returned_evidence(adapter):
    response = adapter.query('one', 'changes.list', {})
    adapter.lifecycle.advance(270)
    with pytest.raises(QueryRejected, match='revoked'):
        adapter.query('two', 'notification.get', {})
    assert adapter.read_response(response['response_id']) == response


def test_count_and_byte_capacity_fail_without_losing_prior_response(adapter, monkeypatch):
    monkeypatch.setattr(timing_queries, 'MAX_RESPONSES', 1)
    one = adapter.query('one', 'changes.list', {})
    with pytest.raises(QueryRejected, match='capacity'):
        adapter.query('two', 'changes.list', {})
    assert adapter.read_response(one['response_id']) == one
    other = TimingQueries('other', Lifecycle())
    monkeypatch.setattr(timing_queries, 'MAX_RESPONSE_BYTES', 1)
    with pytest.raises(QueryRejected, match='capacity'):
        other.query('one', 'notification.get', {})
    monkeypatch.setattr(timing_queries, 'MAX_RESPONSE_BYTES', 65536)
    assert other.query('one', 'changes.list', {})['response_id'].endswith('/0001')


@pytest.mark.parametrize('failure', ['missing', 'changed', 'oversized', 'symlink', 'fifo'])
def test_unavailable_or_unpinned_data_cannot_make_a_ready_adapter(tmp_path, failure):
    corpus = tmp_path / 'data'
    shutil.copytree(DATA, corpus)
    path = corpus / 'logs.jsonl'
    raw = path.read_bytes()
    path.unlink()
    if failure == 'changed':
        path.write_bytes(raw + b' ')
    elif failure == 'oversized':
        path.write_bytes(b'x' * 65537)
    elif failure == 'symlink':
        path.symlink_to(DATA / 'logs.jsonl')
    elif failure == 'fifo':
        os.mkfifo(path)
    with pytest.raises(FixtureDataUnavailable):
        TimingQueries('bad-data', Lifecycle(), fixture_root=corpus)


def test_queries_use_loaded_snapshot_without_files_processes_or_sockets(adapter, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('query crossed in-process fixture boundary')
    monkeypatch.setattr(os, 'open', forbidden)
    monkeypatch.setattr(builtins, 'open', forbidden)
    monkeypatch.setattr(io, 'open', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    for i, op in enumerate(timing_queries.OPERATIONS):
        args = {'metric': METRIC} if op == 'metrics.query' else (
            {'trace_id': 'unknown'} if op == 'traces.get' else {})
        assert adapter.query(f'q-{i}', op, args)['native_launch'] == 'CLOSED'


def test_describe_is_detached_and_discloses_contract(adapter):
    info = adapter.describe()
    assert info['operations']['metrics.query']['required'] == ['metric']
    info['operations']['logs.query']['arguments'].append('path')
    assert 'path' not in adapter.describe()['operations']['logs.query']['arguments']
