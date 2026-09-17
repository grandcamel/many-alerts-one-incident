#!/usr/bin/env python3
"""Ticket 27, item 13 — confirm ONE REAL SYMPTOM before starting any clock.

Ticket 10's trap list: "Verifying flagd is not verifying the caller. Only the
Java provider's reconnect after a flagd rollout has ever been confirmed. A
wedged channel falls back to the code default and the Fault silently never
fires." So this polls the signals a Run would actually read, across all four
classes, and records the first moment each one turns — which is also the
injection -> first symptom half of the timing budget.

    python3 lib/symptom.py <fault> <t0_epoch> [max_seconds] [poll_seconds]
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graf  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(HERE, "capture")
NS = os.environ.get("NS", "otel-demo")
SPAN = os.environ.get("SPAN_METRIC", "traces_span_metrics_calls_total")


# --- probes a Run could actually run ----------------------------------------

def prom_sum(q):
    rows = graf.prom_scalars(q)
    return sum(v for _, v in rows if v is not None) if rows else 0.0


def span_rate(svc, error=False, window="5m"):
    sel = 'service_name="%s"' % svc
    if error:
        sel += ',status_code="STATUS_CODE_ERROR"'
    # MEASURED, not assumed: the collector pushes these metrics every 60 s, so a
    # rate() over [30s] or [1m] has fewer than two samples and returns NO SERIES.
    # `or vector(0)` then turns that emptiness into a confident 0 — which is
    # indistinguishable from the Fault, and is why this harness's own first
    # "payment traffic to zero" fired 7 s after injection, before the Fault could
    # possibly have acted. [2m] is the minimum that produces a value; ticket 10
    # wrote [5m] and [5m] is correct.
    return prom_sum("sum(rate(%s{%s}[%s])) or vector(0)" % (SPAN, sel, window))


def loki_hits(logql, minutes=5):
    return len(graf.loki_lines(logql, minutes=minutes, limit=5))


def tempo_hits(q, minutes=5):
    r = graf.tempo_search(q, minutes=minutes)
    return len((r.get("json", {}) or {}).get("traces", []) or [])


def top_pod(prefix):
    """(pod_name, cpu_millicores, memory_mi) for the first pod matching prefix."""
    try:
        out = subprocess.run(["kubectl", "top", "pod", "-n", NS, "--no-headers"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return (None, None, None)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].startswith(prefix):
            cpu = parts[1].rstrip("m")
            mem = parts[2].rstrip("Mi")
            try:
                return (parts[0], float(cpu), float(mem))
            except ValueError:
                return (parts[0], None, None)
    return (None, None, None)


def pod_status(prefix):
    """restartCount and lastState.terminated for the first pod matching prefix."""
    try:
        out = subprocess.run(["kubectl", "get", "pods", "-n", NS, "-o", "json"],
                             capture_output=True, text=True, timeout=30).stdout
        d = json.loads(out)
    except Exception:  # noqa: BLE001
        return {}
    for p in d.get("items", []):
        if not p["metadata"]["name"].startswith(prefix):
            continue
        for cs in p.get("status", {}).get("containerStatuses") or []:
            term = (cs.get("lastState") or {}).get("terminated") or {}
            return {"pod": p["metadata"]["name"], "container": cs["name"],
                    "restarts": cs.get("restartCount", 0),
                    "ready": cs.get("ready"),
                    "last_terminated_reason": term.get("reason"),
                    "last_exit_code": term.get("exitCode"),
                    "last_finished_at": term.get("finishedAt")}
    return {}


# --- per-Fault symptom sets -------------------------------------------------
# Each check: (name, signal_class, callable -> (fired: bool, detail))

def checks_payment():
    return [
        ("checkout error span-metric", "metrics",
         lambda: (lambda v: (v > 0, "%.4f/s" % v))(span_rate("checkout", error=True))),
        ("payment traffic to zero", "metrics",
         lambda: (lambda v: (v < 0.001, "%.4f/s" % v))(span_rate("payment"))),
        ("errored checkout trace", "traces",
         lambda: (lambda n: (n > 0, "%d traces" % n))(
             tempo_hits('{resource.service.name="checkout" && status=error}'))),
        ("checkout log line (expected ZERO: ticket 10 read all 34 logger calls)", "logs",
         lambda: (lambda n: (n > 0, "%d lines" % n))(
             loki_hits('{service_name="checkout"} |= "charge"'))),
    ]


def checks_email():
    def mem():
        _, _, m = top_pod("email")
        return (m is not None and m > float(os.environ.get("EMAIL_BASELINE_MI", "0")) + 20,
                "%s Mi" % m)

    def restarts():
        s = pod_status("email")
        return (s.get("restarts", 0) > 0,
                "restarts=%s last=%s" % (s.get("restarts"), s.get("last_terminated_reason")))

    return [
        ("email RSS climbing", "kubernetes",
         mem),
        ("email restarted", "kubernetes", restarts),
        ("checkout WARN on confirmation", "logs",
         lambda: (lambda n: (n > 0, "%d lines" % n))(
             loki_hits('{service_name="checkout"} |= "failed to send order confirmation"'))),
        ("email error span-metric (the FLOAT GATE tell: a TypeError 500s instead of leaking)",
         "metrics",
         lambda: (lambda v: (v > 0, "%.4f/s" % v))(span_rate("email", error=True))),
        ("email error log (Float gate raises, look for TypeError)", "logs",
         lambda: (lambda n: (n > 0, "%d lines" % n))(
             loki_hits('{service_name="email"} |~ "(?i)error|typeerror|exception"'))),
    ]


def checks_cart():
    return [
        ("cart redis-connect error log", "logs",
         lambda: (lambda n: (n > 0, "%d lines" % n))(
             loki_hits('{service_name="cart"} |= "Wasn\'t able to connect to redis"'))),
        ("cart any error log", "logs",
         lambda: (lambda n: (n > 0, "%d lines" % n))(
             loki_hits('{service_name="cart"} |~ "(?i)error|exception"'))),
        ("errored cart trace", "traces",
         lambda: (lambda n: (n > 0, "%d traces" % n))(
             tempo_hits('{resource.service.name="cart" && status=error}'))),
        ("cart error span-metric", "metrics",
         lambda: (lambda v: (v > 0, "%.4f/s" % v))(span_rate("cart", error=True))),
    ]


SETS = {
    "paymentUnreachable": checks_payment,
    "emailMemoryLeak": checks_email,
    "cartFailure": checks_cart,
}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    fault = argv[0]
    t0 = int(argv[1]) if len(argv) > 1 else int(time.time())
    max_s = int(argv[2]) if len(argv) > 2 else 600
    poll = int(argv[3]) if len(argv) > 3 else 15
    if fault not in SETS:
        print("no symptom set for %s; have: %s" % (fault, ", ".join(SETS)), file=sys.stderr)
        return 2
    checks = SETS[fault]()
    first = {}
    os.makedirs(CAP, exist_ok=True)
    print("# item 13 — symptom watch for %s" % fault)
    print("# t0 = %s (injection start)" % time.strftime("%FT%TZ", time.gmtime(t0)))
    print("# polling every %ss for up to %ss, across all four signal classes\n" % (poll, max_s))
    print("%6s  %-12s %-64s %s" % ("t+s", "class", "check", "value"))
    deadline = time.time() + max_s
    while time.time() < deadline:
        elapsed = int(time.time() - t0)
        for name, cls, fn in checks:
            try:
                fired, detail = fn()
            except Exception as e:  # noqa: BLE001 - a probe failing is itself data
                fired, detail = False, "probe error: %r" % e
            mark = ""
            if fired and name not in first:
                first[name] = {"t_plus_seconds": elapsed, "detail": detail,
                               "signal_class": cls,
                               "utc": time.strftime("%FT%TZ", time.gmtime())}
                mark = "   <-- FIRST"
            print("%6d  %-12s %-64s %s%s" % (elapsed, cls, name[:64], detail, mark))
        print("")
        sys.stdout.flush()
        if len(first) >= len([c for c in checks if "expected ZERO" not in c[0]]):
            print("# every symptom has fired")
            break
        time.sleep(poll)

    out = {"fault": fault, "t0_epoch": t0,
           "t0_utc": time.strftime("%FT%TZ", time.gmtime(t0)),
           "watched_seconds": int(time.time() - t0),
           "first_symptoms": first,
           "never_fired": [n for n, _, _ in checks if n not in first]}
    with open(os.path.join(CAP, "symptom-%s.json" % fault), "w") as f:
        json.dump(out, f, indent=2)
    print("\n# first symptom per check:")
    for n, v in sorted(first.items(), key=lambda kv: kv[1]["t_plus_seconds"]):
        print("   t+%-5ss  %-12s %s  (%s)" % (v["t_plus_seconds"], v["signal_class"], n, v["detail"]))
    if out["never_fired"]:
        print("\n# NEVER FIRED within the window:")
        for n in out["never_fired"]:
            print("   %s" % n)
    print("\n# artifact: capture/symptom-%s.json" % fault)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
