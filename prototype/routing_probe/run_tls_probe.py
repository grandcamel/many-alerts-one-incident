#!/usr/bin/env python3
"""P4 TLS-trust probe: does the installed `claude` CLI trust a deployment-local
CA via NODE_EXTRA_CA_CERTS, and reject the same endpoint without it?

Local, model-free-in-billing: TLS mock on loopback terminates all requests with
a synthetic sentinel key; no real credential or upstream contact. Evidence:
artifacts/tls-probe.json. See README.md (P1) for the shared contract.
"""

import json
import os
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stage_a"))

import run_routing_probe as p1  # reuses MockAnthropic handler + receipts
import certificates

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
CHILD_TIMEOUT_S = 120

tls_events = []
tls_lock = threading.Lock()


class TlsMock(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, addr, handler, context):
        self._ctx = context
        super().__init__(addr, handler)

    def get_request(self):
        sock, addr = self.socket.accept()
        try:
            return self._ctx.wrap_socket(sock, server_side=True), addr
        except ssl.SSLError as exc:
            with tls_lock:
                tls_events.append({"event": "handshake_failure",
                                   "reason": str(exc), "ts": time.time()})
            sock.close()
            raise

    def handle_error(self, request, client_address):
        # Clients that reject our certificate reset the connection during or
        # right after the handshake; record, don't traceback-spam.
        exc = sys.exc_info()[1]
        with tls_lock:
            tls_events.append({"event": "connection_reset",
                               "reason": str(exc), "ts": time.time()})


def run_child(base_url, sentinel, home, cwd, ca_pem=None):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_API_KEY": sentinel,
    }
    if ca_pem:
        env["NODE_EXTRA_CA_CERTS"] = str(ca_pem)
    cmd = ["claude", "--bare", "-p", "--output-format", "json",
           "Reply with the single word: pong"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=CHILD_TIMEOUT_S, env=env, cwd=cwd)
        return {"exit_code": proc.returncode, "stdout": proc.stdout[-20000:],
                "stderr": proc.stderr[-20000:], "timed_out": False,
                "env_extra": sorted(set(env) - {"PATH", "HOME", "LANG", "TERM"})}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "stdout": None, "stderr": None,
                "timed_out": True, "env_extra": sorted(env)}


def main():
    started = time.monotonic()
    ARTIFACTS.mkdir(exist_ok=True)
    inherited = {k: v for k, v in os.environ.items()
                 if k.upper().startswith(("ANTHROPIC", "CLAUDE")) and v}
    version = subprocess.run(["claude", "--version"], capture_output=True,
                             text=True, timeout=30).stdout.strip()

    certs_dir = tempfile.mkdtemp(prefix="p4-certs-")
    server_key, server_pem, ca_pem = certificates.generate(certs_dir, "valid")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(server_pem, server_key)
    server = TlsMock(("127.0.0.1", 0), p1.MockAnthropic, ctx)
    port = server.server_address[1]
    base_url = f"https://localhost:{port}"
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.02})
    thread.start()

    cases = {}
    for name, ca in (("untrusted", None), ("trusted", ca_pem)):
        with p1.receipts_lock:
            del p1.receipts[:]
        with tls_lock:
            del tls_events[:]
        sentinel = "p4-probe-sentinel-" + secrets.token_hex(16)
        home = tempfile.mkdtemp(prefix="p4-home-")
        cwd = tempfile.mkdtemp(prefix="p4-cwd-")
        child = run_child(base_url, sentinel, home, cwd, ca_pem=ca)
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(cwd, ignore_errors=True)
        with p1.receipts_lock:
            seen = list(p1.receipts)
        with tls_lock:
            events = list(tls_events)
        hits = [r["path"] for r in seen
                if any(sentinel in v for k, v in r["headers"].items()
                       if k.lower() in ("x-api-key", "authorization"))]
        out_text = (child.get("stdout") or "") + (child.get("stderr") or "")
        cases[name] = {
            "child": child,
            "http_requests": len(seen),
            "sentinel_arrivals": hits,
            "tls_events_seen_by_mock": events,
            "tls_markers_in_client_output": [
                m for m in ("self-signed", "certificate", "CERT_",
                            "unable to verify", "UNABLE_TO_VERIFY",
                            "ERR_TLS", "fetch failed")
                if m.lower() in out_text.lower()],
        }

    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    server.server_close()
    shutil.rmtree(certs_dir, ignore_errors=True)

    un, tr = cases["untrusted"], cases["trusted"]
    negative_ok = un["http_requests"] == 0 and not un["sentinel_arrivals"]
    if tr["sentinel_arrivals"] and negative_ok:
        verdict = "supported-tls-trust"
    elif not tr["sentinel_arrivals"]:
        verdict = "refuted-no-workable-trust-mechanism"
    else:
        verdict = "inconclusive"

    report = {
        "probe": "P4 claude CLI deployment-local CA trust",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "client_version": version,
        "trust_mechanism": "NODE_EXTRA_CA_CERTS (binary strings evidence: "
                           "process.env.NODE_EXTRA_CA_CERTS check present in 2.1.272)",
        "mock_base_url": base_url,
        "sentinel_shape": "p4-probe-sentinel-<32 hex>",
        "server_cert": "ephemeral RSA-2048, CN=localhost, SAN DNS:localhost, "
                       "Stage A certificates.py; keys deleted after run",
        "cases": cases,
        "verdict": verdict,
        "not_run": [
            "real upstream passthrough with a valid key",
            "endpoint policy enforcement, revocation drill",
            "billing preflight, model usability",
        ],
    }
    serialized = json.dumps(report, indent=1)
    leaks = [k for k, v in inherited.items() if len(v) >= 8 and v in serialized]
    report["sanitizer"] = {
        "inherited_anthropic_claude_vars_present": sorted(inherited),
        "leaked_into_report": sorted(leaks),
        "min_scanned_value_length": 8,
        "note": "Sentinels synthetic; ephemeral CA and keys deleted; "
                "throwaway HOMEs deleted.",
    }
    if leaks:
        print("REFUSING TO PERSIST: inherited value leaked:", leaks,
              file=sys.stderr)
        sys.exit(2)
    out = ARTIFACTS / "tls-probe.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"verdict={verdict} trusted_reqs={tr['http_requests']} "
          f"untrusted_reqs={un['http_requests']} -> {out}")


if __name__ == "__main__":
    main()
