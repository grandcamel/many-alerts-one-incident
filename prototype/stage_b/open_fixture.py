"""Permissive-read fixture stack for Stage B attempt 2 (user direction 2026-09-18).

Same authority model as the Stage A boundary (admission, per-fixture sentinel,
revocation, ephemeral CA), but READ operations are unrestricted per the user's
ruling: no SI/PII exists in this synthetic scenario. Discovery endpoints
(labels, values, health, stats, search) answer from fixture metadata so a
discovery-driven client can learn the real selectors. Unknown metrics/selectors
return empty results, not denials. Mutation/admin paths, path escapes and
non-fixture upstream tokens remain denied; upstream redirects still 502.
Stage A's `boundary.py` and its frozen evidence are untouched.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import ssl
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

from certificates import generate

TRACE = '0123456789abcdef0123456789abcdef'
METRICS = {'stage_a_current', 'stage_a_system', 'stage_a_empty'}
STREAMS = {'{stream="application"}': 'application',
           '{stream="run",rehearsal="current"}': 'run',
           '{stream="change",rehearsal="current"}': 'change',
           '{stream="empty"}': 'empty'}
DATASOURCES = [{'id': i, 'uid': uid, 'name': uid, 'type': typ, 'access': 'proxy',
                'url': 'http://synthetic.invalid'}
               for i, (uid, typ) in enumerate(
                   [('prom', 'prometheus'), ('loki', 'loki'), ('tempo', 'tempo')], 1)]
MESSAGES = {'application': 'synthetic application trace_id=' + TRACE + '\n' + 'L' * 5000,
            'run': 'synthetic Run id=run-stage-a rehearsal=current',
            'change': 'synthetic Change id=change-stage-a diagnostic=ready rehearsal=current',
            'empty': ''}


def params(value):
    data = parse_qs(value, keep_blank_values=True, strict_parsing=True)
    if any(len(v) != 1 for v in data.values()):
        raise ValueError('duplicate parameter')
    return {k: v[0] for k, v in data.items()}


class OpenFixture:
    """Context-managed stack: TLS Forwarder (permissive-read policy) + backend."""

    def __init__(self, kind='valid'):
        self.kind = kind
        self.backend_receipts, self.boundary_receipts, self.sink_receipts = [], [], []
        self.token, self.control_token, self._upstream = (secrets.token_urlsafe(24)
                                                          for _ in range(3))
        self._revoked = False
        self._admitted = False
        self._expires = time.monotonic() + 300
        self._servers = []
        self._lock = threading.Lock()

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='maoi-openfix-')
        key, cert, self.ca = generate(Path(self._tmp.name), self.kind)
        outer = self

        def handler(callback):
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def handle_request(self):
                    self.connection.settimeout(5)
                    length = int(self.headers.get('Content-Length', '0'))
                    if length > 1048576 or length < 0 or self.headers.get('Transfer-Encoding'):
                        return outer._reply(self, 400, {'error': 'unsupported body framing'})
                    callback(self, self.rfile.read(length) if length else b'')

                do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = handle_request
            return Handler

        self._backend_server = self._serve(handler(self._backend))
        self._sink_server = self._serve(handler(self._sink))
        self._control_server = self._serve(handler(self._control))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert), str(key))
        self._forward_server = self._serve(handler(self._forward), ctx)
        self.url = 'https://localhost:%d' % self._forward_server.server_address[1]
        assert self.control('admit', token='unauthorized') == 401
        assert self.control('admit') == 200
        return self

    def _serve(self, handler, tls=None):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        server.daemon_threads = False
        if tls:
            server.socket = tls.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={'poll_interval': .02}, daemon=True)
        self._servers.append((server, thread))
        thread.start()
        return server

    def __exit__(self, *_):
        for server, thread in reversed(self._servers):
            server.shutdown()
            server.server_close()
            thread.join(2)
            assert not thread.is_alive(), 'server failed to stop'
        self._tmp.cleanup()

    def _reply(self, h, status, body):
        raw = json.dumps(body, separators=(',', ':')).encode()
        try:
            h.send_response(status)
            h.send_header('Content-Type', 'application/json')
            h.send_header('Content-Length', str(len(raw)))
            h.end_headers()
            h.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass

    def _control(self, h, body):
        if h.command != 'POST' or h.headers.get('Authorization') != 'Bearer ' + self.control_token:
            return self._reply(h, 401, {'error': 'control denied'})
        with self._lock:
            if h.path == '/control/admit':
                if self._admitted or self._revoked:
                    return self._reply(h, 409, {'error': 'cannot reuse admission'})
                self._admitted = True
            elif h.path == '/control/revoke':
                self._revoked = True
            elif h.path == '/control/expire':
                self._expires = time.monotonic() - 1
            else:
                return self._reply(h, 404, {'error': 'unknown action'})
        self._reply(h, 200, {'applied': True})

    def control(self, action, token=None):
        c = http.client.HTTPConnection('127.0.0.1',
                                       self._control_server.server_address[1], timeout=2)
        try:
            c.request('POST', '/control/' + action,
                      headers={'Authorization': 'Bearer ' + (
                          self.control_token if token is None else token)})
            r = c.getresponse()
            r.read()
            return r.status
        finally:
            c.close()

    # ---- policy: authority + read-permissive scope ----

    def _read_allowed(self, h, p, body):
        if p.scheme or p.netloc or p.fragment or '%' in p.path or '..' in p.path or '\\' in p.path:
            return False
        if h.command not in ('GET', 'POST'):
            return False
        if p.path in ('/api/frontend/settings', '/api/datasources'):
            return h.command == 'GET'
        for d in DATASOURCES:
            uid = d['uid']
            if p.path in (f'/api/datasources/uid/{uid}',
                          f'/api/datasources/uid/{uid}/health'):
                return h.command == 'GET'
            if p.path.startswith(f'/api/datasources/proxy/uid/{uid}/'):
                return True
            if p.path.startswith(f'/api/datasources/uid/{uid}/resources/'):
                return True
        return False

    def _forward(self, h, body):
        p = urlsplit(h.path)
        with self._lock:
            valid = (self._admitted
                     and h.headers.get('Authorization') == 'Bearer ' + self.token
                     and not self._revoked and time.monotonic() < self._expires)
        allowed = valid and self._read_allowed(h, p, body)
        receipt = {'method': h.command, 'path': p.path, 'query': p.query,
                   'body': body.decode(errors='replace'),
                   'status': 401 if not valid else 403,
                   'reason': 'authority denied' if not valid else 'not a read operation'}
        self.boundary_receipts.append(receipt)
        if not allowed:
            return self._reply(h, receipt['status'], {'error': receipt['reason']})
        c = http.client.HTTPConnection('127.0.0.1',
                                       self._backend_server.server_address[1], timeout=2)
        try:
            c.request(h.command, h.path, body=body,
                      headers={'Authorization': 'Bearer ' + self._upstream,
                               'Content-Type': h.headers.get('Content-Type', 'application/json')})
            r = c.getresponse()
            data = r.read()
            if 300 <= r.status < 400:
                receipt.update(status=502, reason='upstream redirect rejected')
                return self._reply(h, 502, {'error': 'upstream redirect rejected'})
            receipt.update(status=r.status, reason='forwarded')
            self._reply(h, r.status, json.loads(data))
        except (TimeoutError, OSError):
            receipt.update(status=504, reason='upstream timeout')
            self._reply(h, 504, {'error': 'upstream timeout'})
        finally:
            c.close()

    def _sink(self, h, body):
        self.sink_receipts.append({'method': h.command, 'path': h.path})
        self._reply(h, 200, {'unexpected': 'redirect reached sink'})

    # ---- backend: fixture data + discovery ----

    def _backend(self, h, body):
        p = urlsplit(h.path)
        token_ok = h.headers.get('Authorization') == 'Bearer ' + self._upstream
        self.backend_receipts.append({'method': h.command, 'path': p.path,
                                      'query': p.query, 'body': body.decode(errors='replace'),
                                      'token_matched': token_ok})
        if not token_ok:
            return self._reply(h, 401, {'error': 'backend denied'})
        # Normalize the two read path families to one route.
        path = p.path
        for d in DATASOURCES:
            for prefix in (f'/api/datasources/proxy/uid/{d["uid"]}',
                           f'/api/datasources/uid/{d["uid"]}/resources'):
                if path.startswith(prefix + '/'):
                    return self._datasource_api(h, d, path[len(prefix):], p, body)
        if path == '/api/frontend/settings':
            return self._reply(h, 200, {'datasources': {d['name']: d for d in DATASOURCES},
                                        'defaultDatasource': 'prom'})
        if path == '/api/datasources':
            return self._reply(h, 200, DATASOURCES)
        for d in DATASOURCES:
            if path == f'/api/datasources/uid/{d["uid"]}':
                return self._reply(h, 200, d)
            if path == f'/api/datasources/uid/{d["uid"]}/health':
                return self._reply(h, 200, {'status': 'OK',
                                            'message': 'synthetic datasource healthy'})
        return self._reply(h, 404, {'error': 'unknown synthetic endpoint'})

    def _datasource_api(self, h, d, sub, p, body):
        uid = d['uid']
        if uid == 'prom':
            return self._prom(h, sub, p, body)
        if uid == 'loki':
            return self._loki(h, sub, p, body)
        return self._tempo(h, sub, p, body)

    def _prom(self, h, sub, p, body):
        if sub in ('/api/v1/query', '/api/v1/query_range') and h.command == 'POST':
            q = params(body.decode()).get('query', '')
            ranged = sub.endswith('query_range')
            if q == 'stage_a_timeout':
                time.sleep(.6)
            if q == 'stage_a_redirect':
                h.send_response(307)
                h.send_header('Location', 'http://127.0.0.1:%d/sink'
                              % self._sink_server.server_address[1])
                h.send_header('Content-Length', '0')
                h.end_headers()
                return
            if q == 'stage_a_error':
                return self._reply(h, 500, {'status': 'error', 'errorType': 'internal',
                                            'error': 'synthetic failure'})
            result = []
            if q in METRICS - {'stage_a_empty'}:
                datum = {'metric': {'source': 'system' if q == 'stage_a_system' else 'current'}}
                datum.update({'values': [[1767225600, '1'], [1767225630, '2']]}
                             if ranged else {'value': [1767225660, '1']})
                result = [datum]
            # Unknown metric names: truthful empty result, never a denial.
            return self._reply(h, 200, {'status': 'success',
                                        'data': {'resultType': 'matrix' if ranged else 'vector',
                                                 'result': result}})
        if sub == '/api/v1/labels':
            return self._reply(h, 200, {'status': 'success',
                                        'data': ['__name__', 'source']})
        if sub.startswith('/api/v1/label/') and sub.endswith('/values'):
            return self._reply(h, 200, {'status': 'success',
                                        'data': sorted(METRICS) if '__name__' in sub
                                        else ['current', 'system']})
        if sub == '/api/v1/metadata':
            return self._reply(h, 200, {'status': 'success',
                                        'data': {m: [{'type': 'gauge',
                                                      'help': 'synthetic fixture metric'}]
                                                 for m in sorted(METRICS)}})
        return self._reply(h, 404, {'error': 'unknown synthetic prometheus endpoint'})

    def _loki(self, h, sub, p, body):
        if sub == '/loki/api/v1/query_range':
            q = params(p.query)
            stream = STREAMS.get(q.get('query', ''))
            if stream is None:
                return self._reply(h, 200, {'status': 'success',
                                            'data': {'resultType': 'streams', 'result': []}})
            limit = int(q.get('limit', '10'))
            values = [[str(1767225600000000000 + i), MESSAGES[stream] + ' record=' + str(i)]
                      for i in range(12)][:limit]
            result = [] if stream == 'empty' else [
                {'stream': {'stream': stream, 'rehearsal': 'current'}, 'values': values}]
            return self._reply(h, 200, {'status': 'success',
                                        'data': {'resultType': 'streams', 'result': result}})
        if sub == '/loki/api/v1/labels':
            return self._reply(h, 200, {'status': 'success',
                                        'data': ['rehearsal', 'stream']})
        if sub.startswith('/loki/api/v1/label/') and sub.endswith('/values'):
            data = (['application', 'change', 'empty', 'run'] if 'stream' in sub
                    else ['current'])
            return self._reply(h, 200, {'status': 'success', 'data': data})
        if sub == '/loki/api/v1/index/stats':
            return self._reply(h, 200, {'streams': 4, 'chunks': 4, 'entries': 48,
                                        'bytes': 24000})
        return self._reply(h, 404, {'error': 'unknown synthetic loki endpoint'})

    def _tempo(self, h, sub, p, body):
        if sub == '/api/v2/traces/' + TRACE:
            return self._reply(h, 200, {'traceID': TRACE, 'synthetic': True,
                                        'resourceSpans': []})
        if sub == '/api/search':
            return self._reply(h, 200, {'traces': [{'traceID': TRACE,
                                                    'rootServiceName': 'synthetic'}]})
        if sub in ('/api/v2/search/tags', '/api/search/tags'):
            return self._reply(h, 200, {'tags': ['service.name']})
        return self._reply(h, 404, {'error': 'unknown synthetic tempo endpoint'})
