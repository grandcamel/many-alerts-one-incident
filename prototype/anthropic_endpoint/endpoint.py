#!/usr/bin/env python3
"""Throwaway mediated Anthropic endpoint subset (ticket 19 Stage B preparation).

Loopback TLS listener under the Stage A ephemeral CA. Admits per-attempt
sentinels via a separate operator-control listener, substitutes the real
upstream key (held here, outside the client Run), forwards only
POST /v1/messages* to a fixed upstream, streams responses (SSE-compatible)
back, and supports mid-session revocation. Receipts record paths, sizes,
timings and statuses only — never credential values or request bodies.

This is NOT ticket 36's five-service specification; it is the isolated
two-service experiment subset the ticket-19 card allows.
"""

import http.client
import json
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

BODY_CAP = 10 * 1024 * 1024
ALLOWED_PATH_PREFIX = "/v1/messages"
# Response headers passed through; everything else from upstream is dropped.
RESP_HEADER_ALLOW = {"content-type", "cache-control", "request-id",
                     "anthropic-ratelimit-requests-remaining",
                     "anthropic-ratelimit-tokens-remaining"}
# Client request headers forwarded; x-api-key is REPLACED, never forwarded.
REQ_HEADER_ALLOW = {"content-type", "accept", "anthropic-version",
                    "anthropic-beta", "anthropic-dangerous-direct-browser-access",
                    "user-agent", "x-app", "x-claude-code-session-id"}
REQ_HEADER_ALLOW_PREFIX = ("x-stainless-",)


class _UpstreamError(Exception):
    pass


class Admission:
    def __init__(self):
        self._lock = threading.Lock()
        self._sentinels = {}

    def admit(self, sentinel, ttl_s):
        with self._lock:
            self._sentinels[sentinel] = {"expires": time.time() + ttl_s,
                                         "revoked": False}

    def revoke(self, sentinel):
        with self._lock:
            if sentinel in self._sentinels:
                self._sentinels[sentinel]["revoked"] = True
                return True
            return False

    def check(self, sentinel):
        with self._lock:
            entry = self._sentinels.get(sentinel)
            if not entry:
                return "absent"
            if entry["revoked"]:
                return "revoked"
            if time.time() > entry["expires"]:
                return "expired"
            return "ok"


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        # Bound every client read/write so a stalled client cannot hold a
        # handler thread past the Run budget. Upstream-side read timeouts are
        # set by the connection factory.
        self.request.settimeout(30)

    def log_message(self, *args):
        pass

    def do_POST(self):
        started = time.monotonic()
        receipts = self.server.receipts
        clean_path = urlsplit(self.path).path  # never log the query string
        if not clean_path.startswith(ALLOWED_PATH_PREFIX):
            self._deny(404, "not_found_error", "endpoint: unlisted path")
            receipts.append({"ts": time.time(), "path": clean_path,
                             "outcome": "denied-path"})
            return
        sentinel = self.headers.get("x-api-key", "")
        state = self.server.admission.check(sentinel)
        if state != "ok":
            self._deny(401, "authentication_error",
                       f"endpoint: sentinel {state}")
            receipts.append({"ts": time.time(), "path": clean_path,
                             "outcome": f"denied-sentinel-{state}"})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._deny(400, "invalid_request_error",
                       "endpoint: malformed Content-Length")
            receipts.append({"ts": time.time(), "path": clean_path,
                             "outcome": "denied-malformed-length"})
            return
        if length < 0 or length > BODY_CAP:
            self._deny(413, "request_too_large", "endpoint: body cap")
            receipts.append({"ts": time.time(), "path": clean_path,
                             "outcome": "denied-body-cap"})
            return
        body = self.rfile.read(length) if length else b""

        headers = {}
        for k, v in self.headers.items():
            lk = k.lower()
            if lk in REQ_HEADER_ALLOW or lk.startswith(REQ_HEADER_ALLOW_PREFIX):
                headers[k] = v
        headers["x-api-key"] = self.server.upstream_key  # substitution
        headers["host"] = self.server.upstream_host

        conn = self.server.upstream_conn_factory()
        outcome = "proxied"
        error = None
        upstream_status = None
        forwarded = 0
        try:
            try:
                conn.request("POST", self.path, body=body, headers=headers)
                resp = conn.getresponse()
            except OSError as exc:
                self._deny(502, "api_error", "endpoint: upstream unreachable")
                outcome = "upstream-error"
                error = str(exc)[:200]
                raise _UpstreamError

            upstream_status = resp.status
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in RESP_HEADER_ALLOW:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                # Mid-stream revocation: stop serving; an already-dispatched
                # upstream request may finish, but the endpoint stops
                # forwarding for a revoked sentinel (ADR 0012 precedence).
                if self.server.admission.check(sentinel) != "ok":
                    outcome = "revoked-mid-stream"
                    break
                # read1 (not read): read(amt) on a chunked response blocks
                # until amt bytes or end-of-stream, which would defeat the
                # per-chunk revocation check above.
                chunk = resp.read1(65536)
                if not chunk:
                    break
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                self.wfile.flush()
                forwarded += len(chunk)
            if outcome == "revoked-mid-stream":
                # Terminate the chunked body so the client sees a well-formed
                # (if truncated) end rather than a hung socket.
                try:
                    self.wfile.write(b"0\r\n\r\n")
                except OSError:
                    pass
            else:
                self.wfile.write(b"0\r\n\r\n")
        except _UpstreamError:
            pass
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError) as exc:
            # Client vanished mid-stream; the receipt must still record the
            # proxied upstream work (billable-attempt evidence).
            outcome = "client-disconnect"
            error = str(exc)[:200]
        finally:
            conn.close()
            receipt = {"ts": time.time(), "path": clean_path,
                       "outcome": outcome,
                       "request_bytes": length,
                       "response_bytes": forwarded,
                       "upstream_status": upstream_status,
                       "duration_s": round(time.monotonic() - started, 3)}
            if error:
                receipt["error"] = error
            receipts.append(receipt)

    def _deny(self, status, kind, message):
        payload = json.dumps({"type": "error",
                              "error": {"type": kind, "message": message}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_PUT = do_DELETE = lambda self: self._deny(
        404, "not_found_error", "endpoint: unlisted operation")


class ControlHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _auth_ok(self):
        return self.headers.get("x-operator-token", "") == self.server.operator_token

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(length, 65536)) if length else b"{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        if not self._auth_ok():
            self._reply(403, {"ok": False})
            return
        if self.path == "/admit":
            self.server.admission.admit(payload["sentinel"],
                                        float(payload.get("ttl_s", 300)))
            self._reply(200, {"ok": True})
        elif self.path == "/revoke":
            self._reply(200, {"ok": self.server.admission.revoke(
                payload.get("sentinel", ""))})
        else:
            self._reply(404, {"ok": False})

    def do_GET(self):
        if self.path == "/receipts" and self._auth_ok():
            self._reply(200, self.server.receipts)
        else:
            self._reply(403, {"ok": False})

    def _reply(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class QuietServer(ThreadingHTTPServer):
    daemon_threads = False

    def handle_error(self, request, client_address):
        # Clients closing TLS without close_notify surface as SSLEOFError
        # noise; expected in fixtures, not a failure signal.
        pass


def make_servers(proxy_port=0, control_port=0, *, upstream_host,
                 upstream_conn_factory, upstream_key, operator_token,
                 ssl_context=None):
    proxy = QuietServer(("127.0.0.1", proxy_port), ProxyHandler)
    proxy.admission = Admission()
    proxy.receipts = []
    proxy.upstream_host = upstream_host
    proxy.upstream_conn_factory = upstream_conn_factory
    proxy.upstream_key = upstream_key
    if ssl_context is not None:
        proxy.socket = ssl_context.wrap_socket(proxy.socket, server_side=True)

    control = QuietServer(("127.0.0.1", control_port), ControlHandler)
    control.admission = proxy.admission
    control.receipts = proxy.receipts
    control.operator_token = operator_token
    return proxy, control
