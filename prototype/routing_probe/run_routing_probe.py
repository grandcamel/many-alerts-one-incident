#!/usr/bin/env python3
"""P1 routing probe: does the installed `claude` CLI honor ANTHROPIC_BASE_URL?

Local, model-free-in-billing fixture: a loopback mock terminates all requests
with a synthetic sentinel key. See README.md for the declared contract.
Writes artifacts/routing-probe.json beside this script.
"""

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
BODY_CAP = 64 * 1024
CHILD_TIMEOUT_S = 120
WALL_CLOCK_S = 170

receipts = []
receipts_lock = threading.Lock()


def _record(entry):
    with receipts_lock:
        receipts.append(entry)


def _message_payload(model, text):
    return {
        "id": "msg_p1probe" + secrets.token_hex(6),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


class MockAnthropic(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence default stderr logging
        pass

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        truncated = len(body) > BODY_CAP
        kept = body[:BODY_CAP]
        entry = {
            "method": self.command,
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "body_utf8": kept.decode("utf-8", "replace"),
            "body_bytes": len(body),
            "body_truncated": truncated,
            "ts": time.time(),
        }
        _record(entry)

        model = "claude-opus-5"
        stream = False
        try:
            payload = json.loads(body) if body else {}
            model = payload.get("model") or model
            stream = bool(payload.get("stream"))
        except json.JSONDecodeError:
            entry["body_json_error"] = True
            payload = {}

        clean_path = urlsplit(self.path).path
        if self.command == "POST" and clean_path.rstrip("/").endswith("/v1/messages"):
            entry["mock_response"] = "stream" if stream else "message"
            if stream:
                self._send_sse(model)
            else:
                self._send_json(200, _message_payload(model, "pong"))
        else:
            entry["mock_response"] = "404"
            self._send_json(404, {
                "type": "error",
                "error": {"type": "not_found_error",
                          "message": "p1 mock: unhandled path " + self.path},
            })

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle

    def _send_json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_sse(self, model):
        # Exact event sequence per claude-api skill curl/examples.md (SSE).
        msg = _message_payload(model, "")
        events = [
            ("message_start", {"type": "message_start", "message": msg}),
            ("content_block_start", {"type": "content_block_start", "index": 0,
                                     "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                     "delta": {"type": "text_delta", "text": "pong"}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta",
                               "delta": {"stop_reason": "end_turn"},
                               "usage": {"output_tokens": 1}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        payload = b"".join(
            b"event: " + name.encode() + b"\ndata: " + json.dumps(data).encode() + b"\n\n"
            for name, data in events
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    started = time.monotonic()
    ARTIFACTS.mkdir(exist_ok=True)
    sentinel = "p1-probe-sentinel-" + secrets.token_hex(16)

    # Inherited sensitive values to strip from the child and scan against.
    inherited = {k: v for k, v in os.environ.items()
                 if k.upper().startswith(("ANTHROPIC", "CLAUDE")) and v}

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockAnthropic)
    server.daemon_threads = False
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()

    home = tempfile.mkdtemp(prefix="p1-home-")
    cwd = tempfile.mkdtemp(prefix="p1-cwd-")
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True,
                             timeout=30).stdout.strip()

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_API_KEY": sentinel,
    }
    cmd = ["claude", "--bare", "-p", "--output-format", "json",
           "Reply with the single word: pong"]
    child = {"cmd": cmd, "cwd": cwd, "env_keys_sorted": sorted(env)}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S,
                              env=env, cwd=cwd)
        child.update(exit_code=proc.returncode, stdout=proc.stdout[-20000:],
                     stderr=proc.stderr[-20000:], timed_out=False)
    except subprocess.TimeoutExpired as exc:
        child.update(exit_code=None, stdout=(exc.stdout or "")[-20000:]
                     if isinstance(exc.stdout, str) else None,
                     stderr=(exc.stderr or "")[-20000:]
                     if isinstance(exc.stderr, str) else None,
                     timed_out=True)

    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(cwd, ignore_errors=True)

    with receipts_lock:
        seen = list(receipts)
    sentinel_hits = [
        {"path": r["path"], "via": name}
        for r in seen
        for name, value in r["headers"].items()
        if sentinel in value and name.lower() in ("x-api-key", "authorization")
    ]
    out_text = (child.get("stdout") or "") + (child.get("stderr") or "")
    real_api_markers = [m for m in ("api.anthropic.com", "request-id", "request_id",
                                    "invalid x-api-key", "authentication_error")
                        if m in out_text]

    if sentinel_hits:
        verdict = "supported-routing"
    elif not seen and real_api_markers:
        verdict = "refuted-direct-route-suspected"
    else:
        verdict = "inconclusive"

    report = {
        "probe": "P1 claude CLI base-URL routing",
        "started_monotonic": started,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "client_version": version,
        "mock_base_url": base_url,
        "sentinel_shape": "p1-probe-sentinel-<32 hex>",
        "child": child,
        "requests_received": len(seen),
        "request_paths": [r["method"] + " " + r["path"] for r in seen],
        "sentinel_arrivals": sentinel_hits,
        "real_api_markers_in_client_output": real_api_markers,
        "verdict": verdict,
        "receipts": seen,
        "not_run": [
            "TLS fifth-endpoint Forwarder (ADR 0011 pattern)",
            "billing visibility / rates preflight (ADR 0013)",
            "model usability, streaming acceptance beyond mock SSE shape",
            "container, tenant, venue",
        ],
    }

    serialized = json.dumps(report, indent=1)
    # Only credential-shaped values (length >= 8) are meaningful leak signals;
    # short literals like "1" match unrelated JSON content.
    leaks = [k for k, v in inherited.items() if len(v) >= 8 and v in serialized]
    report["sanitizer"] = {
        "inherited_anthropic_claude_vars_present": sorted(inherited),
        "leaked_into_report": sorted(leaks),
        "min_scanned_value_length": 8,
        "note": "Sentinel is synthetic and expected in receipts; throwaway HOME deleted.",
    }
    if leaks:
        print("REFUSING TO PERSIST: inherited value leaked into report:", leaks,
              file=sys.stderr)
        sys.exit(2)

    out = ARTIFACTS / "routing-probe.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"verdict={verdict} requests={len(seen)} sentinel_hits={len(sentinel_hits)} "
          f"exit={child.get('exit_code')} -> {out}")


if __name__ == "__main__":
    t0 = time.monotonic()
    main()
    assert time.monotonic() - t0 < WALL_CLOCK_S, "wall-clock bound exceeded"
