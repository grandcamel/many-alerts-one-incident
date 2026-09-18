#!/usr/bin/env python3
"""Self-test for the throwaway mediated Anthropic endpoint.

Mock upstream (plain loopback) stands in for api.anthropic.com; all keys are
synthetic fixtures. Raw TLS-client cases exercise policy; one `claude --bare
-p` case dresses-rehearses the full client -> endpoint -> upstream path with
no real credential and no paid contact. Evidence: artifacts/self-test.json.
"""

import http.client
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "stage_a"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "routing_probe"))

import certificates
import endpoint
import run_routing_probe as p1
from http.server import ThreadingHTTPServer

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
FIXTURE_UPSTREAM_KEY = "fixture-upstream-key-" + secrets.token_hex(16)


def start_mock_upstream():
    server = ThreadingHTTPServer(("127.0.0.1", 0), p1.MockAnthropic)
    server.daemon_threads = False
    t = threading.Thread(target=server.serve_forever,
                         kwargs={"poll_interval": 0.02})
    t.start()
    return server, t


def raw_post(port, path, sentinel, payload, ca_pem, stream=False):
    ctx = ssl.create_default_context(cafile=str(ca_pem))
    conn = http.client.HTTPSConnection("localhost", port, context=ctx,
                                       timeout=30)
    headers = {"Content-Type": "application/json", "x-api-key": sentinel,
               "anthropic-version": "2023-06-01"}
    conn.request("POST", path, body=json.dumps(payload), headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


def control(port, token, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", path, body=json.dumps(payload),
                 headers={"Content-Type": "application/json",
                          "x-operator-token": token})
    resp = conn.getresponse()
    resp.read()
    ok = resp.status
    conn.close()
    return ok


def main():
    started = time.monotonic()
    ARTIFACTS.mkdir(exist_ok=True)
    inherited = {k: v for k, v in os.environ.items()
                 if k.upper().startswith(("ANTHROPIC", "CLAUDE")) and v}

    certs_dir = tempfile.mkdtemp(prefix="ep-certs-")
    server_key, server_pem, ca_pem = certificates.generate(certs_dir, "valid")
    tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_ctx.load_cert_chain(server_pem, server_key)

    upstream, upstream_t = start_mock_upstream()
    upstream_port = upstream.server_address[1]
    operator_token = "fixture-operator-" + secrets.token_hex(16)

    proxy, control_srv = endpoint.make_servers(
        upstream_host=f"127.0.0.1:{upstream_port}",
        upstream_conn_factory=lambda: http.client.HTTPConnection(
            "127.0.0.1", upstream_port, timeout=30),
        upstream_key=FIXTURE_UPSTREAM_KEY,
        operator_token=operator_token,
        ssl_context=tls_ctx)
    proxy_port = proxy.server_address[1]
    control_port = control_srv.server_address[1]
    threads = [threading.Thread(target=s.serve_forever,
                                kwargs={"poll_interval": 0.02})
               for s in (proxy, control_srv)]
    for t in threads:
        t.start()

    msg = {"model": "claude-opus-5", "max_tokens": 64,
           "messages": [{"role": "user", "content": "ping"}]}
    cases = {}

    def fresh_sentinel():
        return "ep-test-sentinel-" + secrets.token_hex(16)

    # 1. proxied substitution
    with p1.receipts_lock:
        del p1.receipts[:]
    s1 = fresh_sentinel()
    control(control_port, operator_token, "/admit",
            {"sentinel": s1, "ttl_s": 60})
    status, body = raw_post(proxy_port, "/v1/messages?beta=true", s1, msg,
                            ca_pem)
    with p1.receipts_lock:
        up_seen = list(p1.receipts)
    up_keys = [r["headers"].get("x-api-key") for r in up_seen]
    cases["proxied-substitution"] = {
        "client_status": status,
        "upstream_requests": len(up_seen),
        "upstream_got_fixture_key": up_keys == [FIXTURE_UPSTREAM_KEY],
        "sentinel_reached_upstream": any(s1 in json.dumps(r) for r in up_seen),
        "response_is_message": b'"pong"' in body,
    }

    # 2. SSE passthrough
    s2 = fresh_sentinel()
    control(control_port, operator_token, "/admit",
            {"sentinel": s2, "ttl_s": 60})
    status, body = raw_post(proxy_port, "/v1/messages?beta=true", s2,
                            {**msg, "stream": True}, ca_pem)
    cases["sse-passthrough"] = {
        "client_status": status,
        "has_all_events": all(e in body for e in (
            b"message_start", b"content_block_start", b"content_block_delta",
            b"content_block_stop", b"message_delta", b"message_stop")),
        "has_pong": b"pong" in body,
    }

    # 3/4. absent and wrong sentinel
    with p1.receipts_lock:
        del p1.receipts[:]
    st_absent, _ = raw_post(proxy_port, "/v1/messages", fresh_sentinel(), msg,
                            ca_pem)
    st_wrong, _ = raw_post(proxy_port, "/v1/messages", fresh_sentinel(), msg,
                           ca_pem)
    with p1.receipts_lock:
        up_after = len(p1.receipts)
    cases["absent-and-wrong-sentinel"] = {
        "absent_status": st_absent, "wrong_status": st_wrong,
        "upstream_untouched": up_after == 0,
    }

    # 5. unlisted path
    st_path, _ = raw_post(proxy_port, "/v1/models", s2, msg, ca_pem)
    cases["unlisted-path"] = {"status": st_path}

    # 6. revocation
    s6 = fresh_sentinel()
    control(control_port, operator_token, "/admit",
            {"sentinel": s6, "ttl_s": 60})
    st_before, _ = raw_post(proxy_port, "/v1/messages", s6, msg, ca_pem)
    control(control_port, operator_token, "/revoke", {"sentinel": s6})
    with p1.receipts_lock:
        del p1.receipts[:]
    st_after, _ = raw_post(proxy_port, "/v1/messages", s6, msg, ca_pem)
    with p1.receipts_lock:
        up_revoked = len(p1.receipts)
    cases["revocation"] = {"before_status": st_before,
                           "after_status": st_after,
                           "upstream_after_revoke": up_revoked}

    # 7. CLI end-to-end through the endpoint
    s7 = fresh_sentinel()
    control(control_port, operator_token, "/admit",
            {"sentinel": s7, "ttl_s": 120})
    home = tempfile.mkdtemp(prefix="ep-home-")
    cwd = tempfile.mkdtemp(prefix="ep-cwd-")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home,
           "LANG": "en_US.UTF-8", "TERM": "dumb",
           "ANTHROPIC_BASE_URL": f"https://localhost:{proxy_port}",
           "ANTHROPIC_API_KEY": s7,
           "NODE_EXTRA_CA_CERTS": str(ca_pem)}
    try:
        proc = subprocess.run(
            ["claude", "--bare", "-p", "--output-format", "json",
             "Reply with the single word: pong"],
            capture_output=True, text=True, timeout=120, env=env, cwd=cwd)
        out = {}
        if proc.stdout.strip().startswith("{"):
            out = json.loads(proc.stdout)
        cases["cli-end-to-end"] = {
            "exit_code": proc.returncode,
            "terminal_reason": out.get("terminal_reason"),
            "is_error": out.get("is_error"),
            "result": (out.get("result") or "")[:80],
            "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        cases["cli-end-to-end"] = {"timed_out": True}
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(cwd, ignore_errors=True)

    for s in (proxy, control_srv, upstream):
        s.shutdown()
    for t in threads + [upstream_t]:
        t.join(timeout=5)
    for s in (proxy, control_srv, upstream):
        s.server_close()
    shutil.rmtree(certs_dir, ignore_errors=True)

    passed = (
        cases["proxied-substitution"]["client_status"] == 200
        and cases["proxied-substitution"]["upstream_got_fixture_key"]
        and not cases["proxied-substitution"]["sentinel_reached_upstream"]
        and cases["proxied-substitution"]["response_is_message"]
        and cases["sse-passthrough"]["client_status"] == 200
        and cases["sse-passthrough"]["has_all_events"]
        and cases["absent-and-wrong-sentinel"]["absent_status"] == 401
        and cases["absent-and-wrong-sentinel"]["wrong_status"] == 401
        and cases["absent-and-wrong-sentinel"]["upstream_untouched"]
        and cases["unlisted-path"]["status"] == 404
        and cases["revocation"]["before_status"] == 200
        and cases["revocation"]["after_status"] == 401
        and cases["revocation"]["upstream_after_revoke"] == 0
        and cases["cli-end-to-end"].get("is_error") is False
    )
    report = {
        "probe": "mediated endpoint self-test (mock upstream, fixture keys)",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "verdict": "supported" if passed else "refuted-or-incomplete",
        "cases": cases,
        "endpoint_receipts": proxy.receipts,
        "not_run": ["real api.anthropic.com upstream with a valid key",
                    "expiry (TTL) case", "concurrent Runs",
                    "billing visibility"],
    }
    serialized = json.dumps(report, indent=1)
    leaks = [k for k, v in inherited.items() if len(v) >= 8 and v in serialized]
    report["sanitizer"] = {
        "inherited_anthropic_claude_vars_present": sorted(inherited),
        "leaked_into_report": sorted(leaks),
        "min_scanned_value_length": 8,
        "note": "All keys synthetic fixtures; ephemeral CA deleted; "
                "receipts hold no credential values by design.",
    }
    if leaks:
        print("REFUSING TO PERSIST: inherited value leaked:", leaks,
              file=sys.stderr)
        sys.exit(2)
    out = ARTIFACTS / "self-test.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"verdict={report['verdict']} -> {out}")
    for name, c in cases.items():
        print(f"  {name}: {json.dumps(c)[:160]}")


if __name__ == "__main__":
    main()
