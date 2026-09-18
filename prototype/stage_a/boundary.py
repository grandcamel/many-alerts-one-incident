"""Exact-fixture allowlist; deliberately not a production query authorization engine."""
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

PROM = '/api/datasources/proxy/uid/prom'
LOKI = '/api/datasources/proxy/uid/loki'
TEMPO = '/api/datasources/proxy/uid/tempo'
TRACE = '0123456789abcdef0123456789abcdef'
PROM_QUERIES = {'stage_a_current', 'stage_a_system', 'stage_a_empty', 'stage_a_error',
                'stage_a_redirect', 'stage_a_timeout'}
LOG_QUERIES = {'{stream="application"}':'application',
               '{stream="run",rehearsal="current"}':'run',
               '{stream="change",rehearsal="current"}':'change', '{stream="empty"}':'empty'}
DATASOURCES = [{ 'id': i, 'uid': uid, 'name': uid, 'type': typ, 'access':'proxy',
                 'url':'http://synthetic.invalid'}
               for i, (uid,typ) in enumerate([('prom','prometheus'),('loki','loki'),('tempo','tempo')],1)]


def params(value):
    data = parse_qs(value, keep_blank_values=True, strict_parsing=True)
    if any(len(v)!=1 for v in data.values()):
        raise ValueError('duplicate parameter')
    return {k:v[0] for k,v in data.items()}


class FixtureBoundary:
    all_secrets = []

    def __init__(self, kind='valid'):
        self.kind = kind
        self.backend_receipts, self.boundary_receipts, self.sink_receipts = [], [], []
        self.token, self.control_token, self._upstream = (secrets.token_urlsafe(24) for _ in range(3))
        self.all_secrets.extend([self.token, self.control_token, self._upstream])
        self._revoked = False
        self._admitted = False
        self._expires = time.monotonic()+60
        self._servers = []
        self._lock = threading.Lock()

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='maoi-boundary-')
        try:
            key, cert, self.ca = generate(Path(self._tmp.name), self.kind)
            outer = self
            def handler(callback):
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self,*_): pass
                    def handle_request(self):
                        self.connection.settimeout(2)
                        length = int(self.headers.get('Content-Length','0'))
                        if length>16384 or length<0 or self.headers.get('Transfer-Encoding'):
                            return outer._reply(self,400,{'error':'unsupported body framing'})
                        callback(self, self.rfile.read(length) if length else b'')
                    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = handle_request
                return Handler
            self._backend_server = self._serve(handler(self._backend))
            self._sink_server = self._serve(handler(self._sink))
            self._control_server = self._serve(handler(self._control))
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(str(cert),str(key))
            self._forward_server = self._serve(handler(self._forward),ctx)
            self.url = 'https://localhost:%d' % self._forward_server.server_address[1]
            assert self.control('admit',token='unauthorized') == 401
            assert not self._admitted
            assert self.control('admit') == 200
            return self
        except BaseException:
            self.__exit__()
            raise

    def _serve(self, handler, tls=None):
        server = ThreadingHTTPServer(('127.0.0.1',0),handler)
        server.daemon_threads = False  # server_close joins all bounded request handlers
        if tls:
            server.socket = tls.wrap_socket(server.socket,server_side=True)
        thread = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True)
        self._servers.append((server,thread))
        thread.start()
        return server

    def __exit__(self,*_):
        for server,thread in reversed(self._servers):
            server.shutdown()
            server.server_close()
            thread.join(2)
            assert not thread.is_alive(), 'server failed to stop'
        self._tmp.cleanup()

    def _reply(self,h,status,body):
        raw = json.dumps(body,separators=(',',':')).encode()
        try:
            h.send_response(status)
            h.send_header('Content-Type','application/json')
            h.send_header('Content-Length',str(len(raw)))
            h.end_headers()
            h.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError,ssl.SSLError):
            pass  # a deliberately timed-out/interrupted caller cannot receive a response

    def _control(self,h,body):
        if h.command!='POST' or h.headers.get('Authorization')!='Bearer '+self.control_token:
            return self._reply(h,401,{'error':'control denied'})
        with self._lock:
            if h.path=='/control/admit':
                if self._admitted or self._revoked:
                    return self._reply(h,409,{'error':'cannot reuse admission'})
                self._admitted=True
            elif h.path=='/control/revoke':
                self._revoked=True
            elif h.path=='/control/expire':
                self._expires=time.monotonic()-1
            else:
                return self._reply(h,404,{'error':'unknown action'})
        self._reply(h,200,{'applied':True})

    def control(self,action,token=None):
        c=http.client.HTTPConnection('127.0.0.1',self._control_server.server_address[1],timeout=1)
        try:
            c.request('POST','/control/'+action,headers={'Authorization':'Bearer '+(self.control_token if token is None else token)})
            r=c.getresponse(); r.read(); return r.status
        finally:
            c.close()

    def _allowed(self,h,p,body):
        if p.scheme or p.netloc or p.fragment or '%' in p.path or '..' in p.path or '\\' in p.path:
            return False
        try:
            q=params(p.query)
            if h.command=='GET' and p.path in ['/api/frontend/settings','/api/datasources']+[
                    '/api/datasources/uid/'+d['uid'] for d in DATASOURCES]+[TEMPO+'/api/v2/traces/'+TRACE]:
                return not q and not body
            if h.command=='POST' and p.path in [PROM+'/api/v1/query',PROM+'/api/v1/query_range']:
                if q or h.headers.get_content_type()!='application/x-www-form-urlencoded':
                    return False
                data=params(body.decode())
                allowed={'query','time','timeout'} if p.path.endswith('/query') else {'query','start','end','step','timeout'}
                return set(data)<=allowed and data.get('query') in PROM_QUERIES and all(
                    k=='query' or self._valid_time(v) for k,v in data.items())
            if h.command=='GET' and p.path==LOKI+'/loki/api/v1/query_range':
                return not body and set(q)<={'query','start','end','limit','direction','step'} and q.get('query') in LOG_QUERIES and all(
                    k=='query' or (k=='direction' and v in {'forward','backward'}) or
                    (k=='limit' and v.isdigit() and 1<=int(v)<=101) or
                    (k in {'start','end','step'} and self._valid_time(v)) for k,v in q.items())
        except (ValueError,UnicodeError):
            pass
        return False

    @staticmethod
    def _valid_time(value):
        # Fixed experiment numeric timestamps/durations only. No query-language parsing.
        import re
        return bool(re.fullmatch(r'[0-9]+(?:\.[0-9]+)?s?',value))

    def _forward(self,h,body):
        p=urlsplit(h.path)
        with self._lock:
            valid=self._admitted and h.headers.get('Authorization')=='Bearer '+self.token and not self._revoked and time.monotonic()<self._expires
        allowed=valid and self._allowed(h,p,body)
        receipt={'method':h.command,'path':p.path,'query':p.query,'body':body.decode(errors='replace'),
                 'status':401 if not valid else 403,'reason':'authority denied' if not valid else 'scope denied'}
        self.boundary_receipts.append(receipt)
        if not allowed:
            return self._reply(h,receipt['status'],{'error':receipt['reason']})
        c=http.client.HTTPConnection('127.0.0.1',self._backend_server.server_address[1],timeout=.3)
        try:
            c.request(h.command,h.path,body=body,headers={'Authorization':'Bearer '+self._upstream,
                      'Content-Type':h.headers.get('Content-Type','application/json')})
            r=c.getresponse(); data=r.read()
            if 300<=r.status<400:
                receipt.update(status=502,reason='upstream redirect rejected')
                return self._reply(h,502,{'error':'upstream redirect rejected'})
            receipt.update(status=r.status,reason='forwarded')
            self._reply(h,r.status,json.loads(data))
        except (TimeoutError,OSError):
            receipt.update(status=504,reason='upstream timeout')
            self._reply(h,504,{'error':'upstream timeout'})
        finally:
            c.close()

    def _sink(self,h,body):
        self.sink_receipts.append({'method':h.command,'path':h.path})
        self._reply(h,200,{'unexpected':'redirect reached sink'})

    def _backend(self,h,body):
        p=urlsplit(h.path)
        token_ok=h.headers.get('Authorization')=='Bearer '+self._upstream
        self.backend_receipts.append({'method':h.command,'path':p.path,'query':p.query,
                                      'body':body.decode(),'token_matched':token_ok})
        if not token_ok:
            return self._reply(h,401,{'error':'backend denied'})
        if p.path=='/api/frontend/settings':
            return self._reply(h,200,{'datasources':{d['name']:d for d in DATASOURCES},'defaultDatasource':'prom'})
        if p.path=='/api/datasources':
            return self._reply(h,200,DATASOURCES)
        if p.path in ['/api/datasources/uid/'+d['uid'] for d in DATASOURCES]:
            return self._reply(h,200,next(d for d in DATASOURCES if p.path.endswith('/'+d['uid'])))
        if p.path in [PROM+'/api/v1/query',PROM+'/api/v1/query_range']:
            q=params(body.decode())['query']
            if q=='stage_a_timeout':
                time.sleep(.6)
            if q=='stage_a_redirect':
                h.send_response(307)
                h.send_header('Location','http://127.0.0.1:%d/sink'%self._sink_server.server_address[1])
                h.send_header('Content-Length','0'); h.end_headers(); return
            if q=='stage_a_error':
                return self._reply(h,500,{'status':'error','errorType':'internal','error':'synthetic failure'})
            ranged=p.path.endswith('query_range')
            datum={'metric':{'source':'system' if q=='stage_a_system' else 'current'}}
            datum.update({'values':[[1767225600,'1'],[1767225630,'2']]} if ranged else {'value':[1767225660,'1']})
            return self._reply(h,200,{'status':'success','data':{'resultType':'matrix' if ranged else 'vector',
                                     'result':[] if q=='stage_a_empty' else [datum]}})
        if p.path==LOKI+'/loki/api/v1/query_range':
            q=params(p.query); stream=LOG_QUERIES[q['query']]
            message={'application':'synthetic application trace_id='+TRACE+'\n'+'L'*5000,
                     'run':'synthetic Run id=run-stage-a rehearsal=current',
                     'change':'synthetic Change id=change-stage-a diagnostic=ready rehearsal=current',
                     'empty':''}[stream]
            values=[[str(1767225600000000000+i),message+' record='+str(i)] for i in range(12)]
            values=values[:int(q.get('limit','10'))]
            return self._reply(h,200,{'status':'success','data':{'resultType':'streams','result':[] if stream=='empty' else [
                {'stream':{'stream':stream,'rehearsal':'current'},'values':values}]}})
        if p.path==TEMPO+'/api/v2/traces/'+TRACE:
            return self._reply(h,200,{'traceID':TRACE,'synthetic':True,'resourceSpans':[]})
        return self._reply(h,404,{'error':'unknown synthetic endpoint'})
