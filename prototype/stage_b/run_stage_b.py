#!/usr/bin/env python3
"""Stage B attempt runner (throwaway, ticket 19) — budget/revoke/reap/evidence.

Executes ONE bounded model attempt per the experiment card: mediated endpoint
with per-attempt sentinel, monotonic 270/20/10 budget, SIGINT + revocation at
the work deadline, SIGTERM then SIGKILL/reap, operator-only evidence with
sanitizer. `--self-test` runs the full machinery against a mock upstream with
synthetic keys (no spend): one completing attempt, one forced-containment
attempt. Execution mode takes the real key from DEMO_UPSTREAM_KEY in the
operator's environment; the key is never written to artifacts.
"""

import argparse
import http.client
import json
import os
import secrets
import shutil
import signal
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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "anthropic_endpoint"))

import certificates
import endpoint
import run_self_test as st  # SlowOrFastUpstream dribble machinery
from http.server import ThreadingHTTPServer

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
PROMPT = "Reply with the single word: pong"


class AlwaysSlowUpstream(st.SlowOrFastUpstream):
    """Every Messages request dribbles SSE (containment testing)."""

    def _handle(self):
        if self.path.startswith("/v1/messages") and "slow=true" not in self.path:
            self.path += ("&" if "?" in self.path else "?") + "slow=true"
        super()._handle()

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle


def start_slow_upstream():
    server = ThreadingHTTPServer(("127.0.0.1", 0), AlwaysSlowUpstream)
    server.daemon_threads = False
    t = threading.Thread(target=server.serve_forever,
                         kwargs={"poll_interval": 0.02})
    t.start()
    return server, t


class Budget:
    def __init__(self, work_s=270, flush_s=20, kill_s=10):
        self.work_s, self.flush_s, self.kill_s = work_s, flush_s, kill_s


def _control(port, token, path, payload):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", path, body=json.dumps(payload),
                 headers={"Content-Type": "application/json",
                          "x-operator-token": token})
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return resp.status


def run_attempt(*, proxy, control_port, operator_token, ca_pem, budget,
                upstream_key_label, slow_upstream=False):
    """One bounded attempt. Returns the evidence dict for the attempt."""
    t0 = time.monotonic()
    sentinel = "sb-attempt-sentinel-" + secrets.token_hex(16)
    _control(control_port, operator_token, "/admit",
             {"sentinel": sentinel, "ttl_s": budget.work_s + budget.flush_s + budget.kill_s + 30})

    home = tempfile.mkdtemp(prefix="sb-home-")
    cwd = tempfile.mkdtemp(prefix="sb-cwd-")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home,
           "LANG": "en_US.UTF-8", "TERM": "dumb",
           "ANTHROPIC_BASE_URL": f"https://localhost:{proxy.server_address[1]}",
           "ANTHROPIC_API_KEY": sentinel,
           "NODE_EXTRA_CA_CERTS": str(ca_pem)}
    cmd = ["claude", "--bare", "-p", "--output-format", "json",
           "--max-budget-usd", "3", PROMPT]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, cwd=cwd,
                            start_new_session=True)

    timeline = []
    stage = "work"
    revoked = False
    while True:
        elapsed = time.monotonic() - t0
        rc = proc.poll()
        if rc is not None:
            timeline.append({"t": round(elapsed, 3), "event": f"exit-{rc}"})
            break
        if stage == "work" and elapsed >= budget.work_s:
            _control(control_port, operator_token, "/revoke",
                     {"sentinel": sentinel})
            revoked = True
            os.killpg(proc.pid, signal.SIGINT)
            timeline.append({"t": round(elapsed, 3),
                             "event": "work-deadline: revoked+SIGINT"})
            stage = "flush"
        elif stage == "flush" and elapsed >= budget.work_s + budget.flush_s:
            os.killpg(proc.pid, signal.SIGTERM)
            timeline.append({"t": round(elapsed, 3),
                             "event": "flush-deadline: SIGTERM"})
            stage = "kill"
        elif stage == "kill" and elapsed >= budget.work_s + budget.flush_s + budget.kill_s:
            os.killpg(proc.pid, signal.SIGKILL)
            timeline.append({"t": round(elapsed, 3),
                             "event": "kill-deadline: SIGKILL"})
            stage = "reap"
        time.sleep(0.05)

    try:
        stdout, stderr = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        stdout, stderr = "", "communicate-timeout"
    reaped = proc.poll() is not None
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(cwd, ignore_errors=True)

    result_json = None
    if stdout and stdout.strip().startswith("{"):
        try:
            result_json = json.loads(stdout)
        except json.JSONDecodeError:
            result_json = None

    containment = ("completed" if stage == "work"
                   else "contained-after-interrupt" if reaped
                   else "CONTAINMENT-FAILURE")
    return {
        "upstream_key_label": upstream_key_label,
        "slow_upstream": slow_upstream,
        "timeline": timeline,
        "final_stage": stage,
        "exit_code": proc.poll(),
        "reaped": reaped,
        "containment": containment,
        "sentinel_revoked_at_deadline": revoked,
        "duration_s": round(time.monotonic() - t0, 3),
        "client_result": {k: result_json.get(k) for k in
                          ("terminal_reason", "is_error", "subtype",
                           "total_cost_usd", "num_turns")}
        if result_json else None,
        "client_result_text": (result_json.get("result") or "")[:120]
        if result_json else None,
        "stderr_tail": (stderr or "")[-500:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true",
                    help="mock upstream, synthetic keys, scaled-down budget")
    args = ap.parse_args()
    if not args.self_test:
        print("Execution mode requires the authorized card; not run.",
              file=sys.stderr)
        sys.exit(2)

    started = time.monotonic()
    ARTIFACTS.mkdir(exist_ok=True)
    inherited = {k: v for k, v in os.environ.items()
                 if k.upper().startswith(("ANTHROPIC", "CLAUDE")) and v}

    certs_dir = tempfile.mkdtemp(prefix="sb-certs-")
    server_key, server_pem, ca_pem = certificates.generate(certs_dir, "valid")
    tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_ctx.load_cert_chain(server_pem, server_key)

    upstream, upstream_t = start_slow_upstream()
    upstream_port = upstream.server_address[1]
    operator_token = "sb-operator-" + secrets.token_hex(16)
    fixture_key = "sb-fixture-upstream-key-" + secrets.token_hex(16)

    proxy, control_srv = endpoint.make_servers(
        upstream_host=f"127.0.0.1:{upstream_port}",
        upstream_conn_factory=lambda: http.client.HTTPConnection(
            "127.0.0.1", upstream_port, timeout=290),
        upstream_key=fixture_key,
        operator_token=operator_token,
        ssl_context=tls_ctx)
    control_port = control_srv.server_address[1]
    threads = [threading.Thread(target=s.serve_forever,
                                kwargs={"poll_interval": 0.02})
               for s in (proxy, control_srv)]
    for t in threads:
        t.start()

    attempts = []
    # A: completes well inside budget (mock answers instantly).
    attempts.append(run_attempt(
        proxy=proxy, control_port=control_port,
        operator_token=operator_token, ca_pem=ca_pem,
        budget=Budget(work_s=60, flush_s=5, kill_s=2),
        upstream_key_label="fixture", slow_upstream=False))
    # B: same dribbling upstream; tiny budget forces the containment path:
    # the work deadline fires mid-stream while the client still runs.
    attempts.append(run_attempt(
        proxy=proxy, control_port=control_port,
        operator_token=operator_token, ca_pem=ca_pem,
        budget=Budget(work_s=4, flush_s=3, kill_s=2),
        upstream_key_label="fixture", slow_upstream=True))

    for s in (proxy, control_srv, upstream):
        s.shutdown()
    for t in threads + [upstream_t]:
        t.join(timeout=5)
    for s in (proxy, control_srv, upstream):
        s.server_close()
    shutil.rmtree(certs_dir, ignore_errors=True)

    a, b = attempts
    checks = {
        "A_completed": a["containment"] == "completed",
        "A_client_success": (a["client_result"] or {}).get("is_error") is False,
        "A_client_under_client_guard": (a["client_result"] or {}).get(
            "total_cost_usd", 9) <= 3,
        "B_reaped": b["reaped"],
        "B_revoked_at_deadline": b["sentinel_revoked_at_deadline"],
        "B_interrupted_not_completed": b["final_stage"] != "work",
        "B_contained": b["containment"] != "CONTAINMENT-FAILURE",
    }
    report = {
        "probe": "Stage B runner self-test (mock upstream, synthetic keys)",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "verdict": "supported" if all(checks.values()) else "refuted-or-incomplete",
        "checks": checks,
        "attempts": attempts,
        "endpoint_receipts": proxy.receipts,
        "not_run": ["real model/upstream", "mcp-grafana wiring (Stage A-proven "
                    "transport; assembled at execution)", "fixture scoring",
                    "billing reconciliation"],
    }
    serialized = json.dumps(report, indent=1)
    leaks = [k for k, v in inherited.items() if len(v) >= 8 and v in serialized]
    report["sanitizer"] = {
        "inherited_anthropic_claude_vars_present": sorted(inherited),
        "leaked_into_report": sorted(leaks),
        "min_scanned_value_length": 8,
        "note": "All keys synthetic; sentinels random per attempt; "
                "throwaway HOMEs and CA deleted.",
    }
    if leaks:
        print("REFUSING TO PERSIST: inherited value leaked:", leaks,
              file=sys.stderr)
        sys.exit(2)
    out = ARTIFACTS / "runner-self-test.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"verdict={report['verdict']} -> {out}")
    print(json.dumps(checks, indent=1))
    for i, a_ in enumerate(attempts):
        print(f"attempt {chr(65+i)}: containment={a_['containment']} "
              f"stage={a_['final_stage']} dur={a_['duration_s']}s "
              f"timeline={json.dumps(a_['timeline'])}")


if __name__ == "__main__":
    main()
