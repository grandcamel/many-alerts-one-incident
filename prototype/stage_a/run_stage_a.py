#!/usr/bin/env python3
"""Model-free native MCP transport experiment; synthetic loopback services only."""
import hashlib
import http.client
import json
from pathlib import Path
import queue
import signal
import ssl
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

from boundary import FixtureBoundary

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts'
BIN = Path('/tmp/maoi-mcp-client/mcp-grafana')
PIN = 'd8cdb94e5e3154e1cf7b3ea850c83fd9309c222d96d99784187a57b76545334c'
TRACE = '0123456789abcdef0123456789abcdef'
START = '2026-01-01T00:00:00Z'
END = '2026-01-01T00:01:00Z'


def content(message):
    return '\n'.join(x.get('text', '') for x in message.get('result', {}).get('content', []))


def failed(message):
    return bool(message.get('error') or message.get('result', {}).get('isError'))


class Native:
    """One real stdio client, sequenced handshake, bounded reads and owned cleanup."""
    def __init__(self, fixture, token='default'):
        self.f = fixture
        self.td = tempfile.TemporaryDirectory(prefix='stage-a-client-')
        self.env = {'PATH': '/usr/bin:/bin', 'HOME': self.td.name,
                    'GRAFANA_URL': fixture.url, 'GRAFANA_USAGE_STATS': 'disabled',
                    'NO_PROXY': '*'}
        if token is not None:
            self.env['GRAFANA_SERVICE_ACCOUNT_TOKEN'] = fixture.token if token == 'default' else token
        self.args = [str(BIN), '--transport=stdio', '--enabled-tools=prometheus,loki,tempo,datasource',
                     '--disable-write', '--disable-api', '--usage-stats=disabled',
                     '--grafana-timeout=1s', '--tls-ca-file=' + str(fixture.ca)]
        self.started = time.monotonic()
        self.p = subprocess.Popen(self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=self.env)
        self.q = queue.Queue()
        self.errors = []
        self.transcript = []
        self.ident = 0
        self.closed = False
        self.threads = [threading.Thread(target=self._read, daemon=True),
                        threading.Thread(target=self._stderr, daemon=True)]
        for t in self.threads:
            t.start()
        try:
            self.initialize = self.rpc('initialize', {'protocolVersion': '2024-11-05',
              'capabilities': {}, 'clientInfo': {'name': 'stage-a-fixture-driver', 'version': '1'}})
            self.initialize_ms = round((time.monotonic() - self.started) * 1000, 3)
            self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}})
            self.tools = self.rpc('tools/list', {})
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.p.stdout:
                try:
                    self.q.put(json.loads(line))
                except ValueError:
                    self.q.put({'protocol_error': line[:1000]})
        finally:
            self.q.put({'eof': True})

    def _stderr(self):
        for line in self.p.stderr:
            self.errors.append(line)

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj) + '\n')
        self.p.stdin.flush()

    def rpc(self, method, params):
        self.ident += 1
        ident = self.ident
        start = time.monotonic()
        request = {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params}
        self.send(request)
        deadline = start + 5
        while True:
            message = self.q.get(timeout=max(0.001, deadline - time.monotonic()))
            if message.get('eof') or message.get('protocol_error'):
                raise RuntimeError('MCP stream ended or malformed before response')
            if message.get('id') == ident:
                self.transcript.append({'request': request, 'response': message,
                                        'elapsed_ms': round((time.monotonic() - start) * 1000, 3)})
                return message
            if time.monotonic() >= deadline:
                raise TimeoutError(method)

    def call(self, name, args):
        return self.rpc('tools/call', {'name': name, 'arguments': args})

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.p.stdin and not self.p.stdin.closed:
                self.p.stdin.close()
            try:
                self.p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.p.terminate()
                try:
                    self.p.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.p.kill()
                    self.p.wait(timeout=1)
            for t in self.threads:
                t.join(timeout=1)
            assert not any(t.is_alive() for t in self.threads), 'reader thread did not stop'
            self.p.stdout.close()
            self.p.stderr.close()
        finally:
            self.td.cleanup()

    def receipt(self):
        return {'initialize_ms': self.initialize_ms,
                'argv': [s if not s.startswith('--tls-ca-file=') else '--tls-ca-file=<ephemeral CA>' for s in self.args],
                'environment_keys': sorted(self.env), 'transcript': self.transcript,
                'stderr': ''.join(self.errors), 'exit': self.p.returncode,
                'process_reaped': self.p.poll() is not None}


def prom(expr='stage_a_current', range_query=False):
    args = {'datasourceUid': 'prom', 'expr': expr, 'endTime': END,
            'queryType': 'range' if range_query else 'instant'}
    if range_query:
        args.update(startTime=START, stepSeconds=30)
    return args


def loki(query='{stream="application"}', limit=None):
    args = {'datasourceUid': 'loki', 'logql': query, 'startRfc3339': START, 'endRfc3339': END}
    if limit is not None:
        args['limit'] = limit
    return args


def direct(f, target, method='GET', body=None, token='default'):
    parts = urlsplit(f.url)
    conn = http.client.HTTPSConnection(parts.hostname, parts.port,
                                      context=ssl.create_default_context(cafile=str(f.ca)), timeout=2)
    headers = {}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + (f.token if token == 'default' else token)
    if body is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        conn.request(method, target, body=body, headers=headers)
        response = conn.getresponse()
        return {'status': response.status, 'body': response.read().decode()}
    finally:
        conn.close()


def main():
    if hashlib.sha256(BIN.read_bytes()).hexdigest() != PIN:
        raise SystemExit('Pinned binary hash mismatch')
    OUT.mkdir(exist_ok=True)
    report = {'binary_sha256': PIN, 'cases': [], 'sessions': [], 'fixtures': [],
              'limits': ['Synthetic HTTP backend, host processes, no real Grafana or tenant grants.',
                         'No model, container, cloud, paid API or production Skill execution.',
                         'Exact fixture query allowlist is not a general PromQL/LogQL security parser.',
                         'No OS network isolation proof; explicit local URLs, no inherited proxy/auth, usage stats disabled.',
                         'Timings are individual local samples, not venue or model timing guarantees.']}
    started = time.monotonic()
    def record(name, ok, evidence, origin='native MCP'):
        report['cases'].append({'name': name, 'origin': origin,
                                'verdict': 'supported' if ok else 'refuted', 'evidence': evidence})
    def save_fixture(f):
        report['fixtures'].append({'boundary': f.boundary_receipts, 'backend': f.backend_receipts,
                                   'redirect_sink': f.sink_receipts})
    def close_session(n):
        n.close()
        report['sessions'].append(n.receipt())

    with FixtureBoundary() as f:
        n = Native(f)
        try:
            names = [x['name'] for x in n.tools['result']['tools']]
            record('native initialization and tool schemas', all(x in names for x in
                   ['query_prometheus', 'query_loki_logs', 'get_tempo_trace']), {'tool_names': names})
            r = n.call('query_prometheus', prom())
            record('valid TLS Bearer swap and POST current read', not failed(r) and
                   json.loads(content(r)) == {'data':[{'metric':{'source':'current'},'value':[1767225660,'1']}]} and any(x['method']=='POST' for x in f.backend_receipts) and
                   all(x['token_matched'] for x in f.backend_receipts), r)
            r = n.call('query_prometheus', prom('stage_a_system', True))
            data = json.loads(content(r)) if not failed(r) else {}
            record('system metric range', not failed(r) and data == {'data':[{'metric':{'source':'system'},'values':[[1767225600,'1'],[1767225630,'2']]}]}, r)
            r = n.call('query_loki_logs', loki())
            data = json.loads(content(r)) if not failed(r) else {}
            lines = data.get('data', [])
            record('Loki default ten and truncation flag', len(lines) == 10 and
                   data.get('metadata', {}).get('resultsTruncated') is True, r)
            record('long multiline log preserved', bool(lines) and all(x.get('line') == 'synthetic application trace_id='+TRACE+'\n'+'L'*5000+' record='+str(i) for i,x in enumerate(lines)), {'line_lengths': [len(x.get('line','')) for x in lines]})
            r = n.call('query_loki_logs', loki(limit=1000))
            data = json.loads(content(r)) if not failed(r) else {}
            record('Loki configured maximum and complete fixture', len(data.get('data', [])) == 12 and
                   data.get('metadata',{}).get('maxLinesAllowed') == 100 and
                   data.get('metadata',{}).get('resultsTruncated') is False, r)
            for label, query in [('Run', '{stream="run",rehearsal="current"}'),
                                 ('Change', '{stream="change",rehearsal="current"}')]:
                r = n.call('query_loki_logs', loki(query))
                record(label + ' current-rehearsal readback', not failed(r) and
                       json.loads(content(r)).get('data',[{}])[0].get('line') ==
                       ('synthetic Run id=run-stage-a rehearsal=current record=0' if label=='Run' else
                        'synthetic Change id=change-stage-a diagnostic=ready rehearsal=current record=0'), r)
            before = len(f.backend_receipts)
            r = n.call('query_loki_logs', loki('{stream="run",rehearsal="previous"}'))
            record('prior rehearsal telemetry query denied before backend', failed(r) and
                   all(x['path']=='/api/datasources/uid/loki' for x in f.backend_receipts[before:]),
                   {'response':r,'new_backend_requests':f.backend_receipts[before:],
                    'note':'Native datasource metadata lookup is separately allowed; denied telemetry query did not reach backend.'})
            r = n.call('query_loki_logs', loki('{stream="empty"}'))
            data = json.loads(content(r)) if not failed(r) else {}
            record('empty logs distinct from error', not failed(r) and data.get('data') == [], r)
            r = n.call('get_tempo_trace', {'datasourceUid':'tempo', 'trace_id':TRACE})
            record('trace reference readback', not failed(r) and json.loads(content(r)) == {'traceID':TRACE,'synthetic':True,'resourceSpans':[]}, r)
            for expr,label in [('stage_a_error','upstream failure visible'),
                               ('stage_a_redirect','upstream redirect rejected'),
                               ('stage_a_timeout','upstream timeout visible')]:
                before = len(f.backend_receipts)
                r = n.call('query_prometheus', prom(expr))
                expected = {'stage_a_error':'server error: 500','stage_a_redirect':'server error: 502','stage_a_timeout':'server error: 504'}[expr]
                record(label, failed(r) and expected in content(r) and not f.sink_receipts and
                       any('query='+expr in x['body'] for x in f.backend_receipts[before:]), r)
            target = '/api/datasources/proxy/uid/prom/api/v1/query'
            for label, path, method, body in [
                ('write', '/api/admin/users', 'POST', '{}'),
                ('absolute target', 'http://127.0.0.1:1/escape', 'GET', None),
                ('unsafe path', '/api/../admin/users', 'GET', None),
                ('encoded unsafe path', '/api/%2e%2e/admin/users', 'GET', None),
                ('unlisted query', target, 'POST', 'query=stage_a_previous'),
                ('duplicate query', target, 'POST', 'query=stage_a_current&query=stage_a_previous'),
                ('unknown parameter', target, 'POST', 'query=stage_a_current&unsafe=yes')]:
                before = len(f.backend_receipts)
                r = direct(f,path,method,body)
                record(label + ' denied before backend', r['status'] in (400,403) and
                       len(f.backend_receipts)==before, r, 'direct boundary probe, write-disable independent')
            # Control credential is never placed in the native process environment.
            result = f.control('revoke', token='wrong-control')
            r = n.call('query_prometheus', prom())
            record('unauthorized control cannot revoke', result == 401 and not failed(r), {'control_result': result, 'readback': r}, 'control probe + native MCP')
            f.control('revoke')
            before = len(f.backend_receipts)
            r = n.call('query_prometheus', prom())
            record('mid-session revocation enforced', failed(r) and len(f.backend_receipts)==before, r)
            r = n.call('query_prometheus', prom())
            record('revocation not silently restored', failed(r) and len(f.backend_receipts)==before, r)
        finally:
            close_session(n)
            save_fixture(f)

    for kind in ['untrusted', 'wronghost', 'expired']:
        with FixtureBoundary(kind=kind) as f:
            n = Native(f)
            try:
                r = n.call('query_prometheus', prom())
                text = content(r).lower()
                marker = {'untrusted':'unknown authority','wronghost':'certificate is valid for','expired':'expired'}[kind]
                record('native TLS ' + kind, failed(r) and marker in text and not f.backend_receipts, r)
            finally:
                close_session(n)
                save_fixture(f)

    for kind in ['absent', 'wrong-service', 'expired']:
        with FixtureBoundary() as f:
            if kind == 'expired':
                f.control('expire')
            n = Native(f, token=None if kind=='absent' else ('jira-only-fixture-token' if kind=='wrong-service' else 'default'))
            try:
                r = n.call('query_prometheus', prom())
                record('native sentinel ' + kind, failed(r) and not f.backend_receipts, r)
            finally:
                close_session(n)
                save_fixture(f)

    with FixtureBoundary() as f:
        n = Native(f)
        try:
            # Start a delayed actual query, observe dispatch, then interrupt the stdio process.
            n.call('query_prometheus', prom())
            before = len(f.backend_receipts)
            n.send({'jsonrpc':'2.0','id':999,'method':'tools/call',
                    'params':{'name':'query_prometheus','arguments':prom('stage_a_timeout')}})
            deadline = time.monotonic() + 2
            while not any('query=stage_a_timeout' in x['body'] for x in f.backend_receipts[before:]) and time.monotonic()<deadline:
                time.sleep(.01)
            dispatched = any('query=stage_a_timeout' in x['body'] for x in f.backend_receipts[before:])
            n.p.send_signal(signal.SIGINT)
            n.close()
            f.control('revoke')
            before = len(f.backend_receipts)
            denied = direct(f, '/api/datasources')
            record('interrupted stdio reaped and authority revoked', dispatched and
                   n.p.poll() is not None and denied['status']==401 and len(f.backend_receipts)==before,
                   {'dispatched':dispatched,'exit':n.p.returncode,'post_revoke_status':denied['status']})
        finally:
            close_session(n)
            save_fixture(f)

    report['elapsed_seconds'] = round(time.monotonic()-started,3)
    report['summary'] = {v: sum(c['verdict']==v for c in report['cases']) for v in ['supported','refuted','inconclusive']}
    report['not_run'] = ['model tool selection/usability, model budget and mediated Anthropic',
      'real Grafana grants, Kubernetes Eyes, intended venue, container filesystem/network boundary',
      'general query parser and arbitrary query pagination; only default/capped fixture output observed']
    report['criterion_gaps'] = {'tool_usability_under_model':'inconclusive: Stage B NOT RUN',
      'runtime_budget':'inconclusive: local process timings only',
      'filesystem_credential_boundary':'inconclusive: host-process fixture only, no container or packet capture',
      'general_output_completeness':'inconclusive: fixed outputs only, no general pagination or 10MiB response-cap exercise'}
    report['observations'] = ['Prometheus error tool output preserves HTTP 500/502/504 status but drops synthetic diagnostic response bodies; inspect sanitized boundary receipts for the cause.']
    report['source_hashes'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')}
    # Runtime authority values are checked before saving; they are not report fields.
    serialized = json.dumps(report, indent=2, sort_keys=True)
    for secret in FixtureBoundary.all_secrets:
        if secret and secret in serialized:
            raise AssertionError('Runtime secret found in report; refusing persistence')
    report['sanitizer'] = {'runtime_secret_matches':0,'secrets_checked':len(FixtureBoundary.all_secrets)}
    FixtureBoundary.all_secrets.clear()
    (OUT/'stage-a.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report['summary']))
    if report['summary']['refuted']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
