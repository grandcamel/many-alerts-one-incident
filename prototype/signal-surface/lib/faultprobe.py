#!/usr/bin/env python3
"""Run ticket 10's proposed queries against a live Fault — items 9 to 12.

Every alertable condition, diagnostic path and discriminator ticket 10 wrote is
run here verbatim against the venue, with the real number recorded. A query that
returns an empty series is a finding, not an error: ticket 10's own trap list
says metric families do not transfer across languages and that copying a rule
onto the wrong service returns an empty series forever.

    python3 lib/faultprobe.py <fault> [label]
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

RESULT = {}


def prom(title, q, note=""):
    rows = graf.prom_scalars(q)
    print("\n  %s" % title)
    print("    %s" % q)
    if not rows:
        print("    -> EMPTY SERIES%s" % ("  (%s)" % note if note else ""))
    for m, v in sorted(rows, key=lambda kv: -(kv[1] or 0))[:12]:
        lbl = m.get("service_name") or m.get("k8s_pod_name") or json.dumps(m)[:60]
        print("    -> %-34s %.5f" % (lbl, v if v is not None else float("nan")))
    RESULT.setdefault("prom", {})[title] = {
        "query": q, "series": len(rows),
        "values": [{"labels": m, "value": v} for m, v in rows]}
    return rows


def loki(title, logql, minutes=10, limit=5):
    lines = graf.loki_lines(logql, minutes=minutes, limit=limit)
    print("\n  %s" % title)
    print("    %s" % logql)
    print("    -> %d line(s)%s" % (len(lines), "" if lines else "   EMPTY"))
    for ns, line, stream in lines[:limit]:
        print("       %s" % line[:300].replace("\n", " "))
    if lines:
        print("       stream labels: %s" % json.dumps(lines[0][2]))
    RESULT.setdefault("loki", {})[title] = {
        "query": logql, "lines": len(lines),
        "sample": [{"ts": n, "line": l, "stream": s} for n, l, s in lines[:limit]]}
    return lines


def tempo(title, q, minutes=15, fetch_first=False):
    r = graf.tempo_search(q, minutes=minutes)
    traces = (r.get("json", {}) or {}).get("traces", []) or []
    print("\n  %s" % title)
    print("    %s" % q)
    print("    -> HTTP %s  %d trace(s)  %.0f ms" % (r.get("code"), len(traces), r.get("ms", 0)))
    if not traces and (r.get("text") or (r.get("json", {}) or {}).get("error")):
        print("       %s" % str(r.get("text") or r["json"]["error"])[:220].replace("\n", " "))
    detail = None
    if traces and fetch_first:
        tid = traces[0].get("traceID")
        t = graf.tempo_trace(tid)
        detail = extract_events(t.get("json", {}))
        print("       trace %s: %d span event(s) captured" % (tid, len(detail)))
        for e in detail[:6]:
            print("         [%s] %s  %s" % (e.get("span"), e.get("name"),
                                            str(e.get("attrs"))[:200]))
    RESULT.setdefault("tempo", {})[title] = {
        "query": q, "code": r.get("code"), "traces": len(traces),
        "ms": round(r.get("ms", 0)), "first_trace_events": detail,
        "trace_ids": [t.get("traceID") for t in traces[:5]]}
    return traces


def extract_events(trace_json):
    """Span events (the `exception` event ticket 10's diagnostic path relies on)."""
    out = []
    for b in trace_json.get("batches", []) or []:
        for ss in b.get("scopeSpans", []) or []:
            for sp in ss.get("spans", []) or []:
                for ev in sp.get("events", []) or []:
                    out.append({
                        "span": sp.get("name"),
                        "name": ev.get("name"),
                        "attrs": {a["key"]: list((a.get("value") or {}).values())[0]
                                  for a in ev.get("attributes", []) or []},
                    })
    return out


def kube_events(prefix):
    """Item 9 — what a read-only kubectl can retrieve, and what Loki carries."""
    print("\n  Kubernetes-side evidence for %s" % prefix)
    try:
        out = subprocess.run(
            ["kubectl", "get", "pods", "-n", NS, "-o", "json"],
            capture_output=True, text=True, timeout=45).stdout
        d = json.loads(out)
    except Exception as e:  # noqa: BLE001
        print("    kubectl failed: %r" % e)
        return
    found = []
    for p in d.get("items", []):
        if not p["metadata"]["name"].startswith(prefix):
            continue
        for cs in p.get("status", {}).get("containerStatuses") or []:
            term = (cs.get("lastState") or {}).get("terminated") or {}
            rec = {"pod": p["metadata"]["name"], "container": cs["name"],
                   "restarts": cs.get("restartCount"), "ready": cs.get("ready"),
                   "lastState_terminated": term or None}
            found.append(rec)
            print("    %s/%s restarts=%s ready=%s lastState.terminated=%s"
                  % (rec["pod"], rec["container"], rec["restarts"], rec["ready"],
                     json.dumps(term) if term else "(none)"))
    RESULT.setdefault("kubectl", {})[prefix] = found
    try:
        ev = subprocess.run(
            ["kubectl", "get", "events", "-n", NS, "--sort-by=.lastTimestamp",
             "-o", "json"], capture_output=True, text=True, timeout=45).stdout
        evd = json.loads(ev)
        rel = [e for e in evd.get("items", [])
               if prefix in (e.get("involvedObject", {}).get("name") or "")]
        print("    %d Kubernetes Event(s) naming %s*:" % (len(rel), prefix))
        for e in rel[-10:]:
            print("      %-10s %-22s %s" % (e.get("type"), e.get("reason"),
                                            (e.get("message") or "")[:110]))
        RESULT.setdefault("k8s_events", {})[prefix] = [
            {"type": e.get("type"), "reason": e.get("reason"),
             "message": e.get("message"), "count": e.get("count"),
             "lastTimestamp": e.get("lastTimestamp")} for e in rel]
    except Exception as e:  # noqa: BLE001
        print("    kubectl get events failed: %r" % e)


# --- per-Fault probe sets ---------------------------------------------------

def probe_payment():
    print("\n### alertable condition 1 — checkout error ratio")
    prom("checkout error ratio, ticket 10 verbatim (no span_kind)",
         'sum(rate(%s{service_name="checkout",status_code="STATUS_CODE_ERROR"}[5m]))'
         ' / sum(rate(%s{service_name="checkout"}[5m]))' % (SPAN, SPAN))
    prom("checkout error ratio, SERVER spans only (the span_kind fix)",
         'sum(rate(%s{service_name="checkout",span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}[5m]))'
         ' / sum(rate(%s{service_name="checkout",span_kind="SPAN_KIND_SERVER"}[5m]))' % (SPAN, SPAN))
    prom("error ratio by service, the instantiation that makes the Cascade",
         'sum by (service_name) (rate(%s{status_code="STATUS_CODE_ERROR"}[5m]))'
         ' / sum by (service_name) (rate(%s[5m]))' % (SPAN, SPAN))
    print("\n### alertable condition 2 — service traffic absent")
    prom("payment traffic (ticket 10 says EXACTLY zero)",
         'sum by (service_name) (rate(%s{service_name=~"payment|email|accounting|fraud-detection|shipping"}[5m]))' % SPAN)
    prom("every service's call rate, to see the blast radius",
         'sum by (service_name) (rate(%s[5m]))' % SPAN)
    print("\n### diagnostic path")
    tempo("checkout Charge spans, errored",
          '{resource.service.name="checkout" && span.rpc.method="oteldemo.PaymentService/Charge" && status=error}',
          fetch_first=True)
    tempo("checkout errored spans, any method",
          '{resource.service.name="checkout" && status=error}', fetch_first=True)
    print("\n### the logs column ticket 10 calls a proven zero")
    loki("checkout logs at all", '{service_name="checkout"}', minutes=10, limit=3)
    loki("checkout logs mentioning the failure",
         '{service_name="checkout"} |~ "(?i)charge|payment|unavailable|rpc error"')
    loki("payment logs at all", '{service_name="payment"}', minutes=10, limit=3)
    print("\n### stage hazard — checkout's own memory")
    kube_events("checkout")


def probe_email():
    print("\n### alertable condition — container memory approaching limit")
    prom("email working set, ticket 10's metric",
         'max by (k8s_pod_name) (container_memory_working_set_bytes{k8s_container_name="email"})')
    prom("email working set, whatever the real metric family is",
         'max by (k8s_pod_name) ({__name__=~"k8s_container_memory.*|container_memory.*",'
         'k8s_container_name="email"})')
    print("\n### alertable condition — restart count (a GAUGE, per ticket 10)")
    prom("k8s_container_restarts on email",
         'max by (k8s_pod_name) (k8s_container_restarts{k8s_container_name="email"})')
    prom("any restart-shaped metric on email",
         'max by (__name__, k8s_pod_name) ({__name__=~".*restart.*",k8s_container_name="email"})')
    print("\n### alertable condition — the caller's WARN")
    loki("checkout's confirmation WARN",
         '{service_name="checkout"} |= "failed to send order confirmation"')
    loki("checkout logs mentioning email",
         '{service_name="checkout"} |~ "(?i)email|confirmation"')
    loki("email's own logs", '{service_name="email"}', minutes=15, limit=6)
    loki("email logs carrying an error or a Ruby TypeError (THE FLOAT GATE)",
         '{service_name="email"} |~ "(?i)error|typeerror|exception|no implicit conversion"',
         minutes=20, limit=8)
    print("\n### item 9 — the restart evidence a read-only Run can retrieve")
    kube_events("email")
    loki("Kubernetes Events in Loki naming the email pod (ticket 26's only selector)",
         '{service_name="unknown_service"} |= "email-"', minutes=30, limit=8)
    loki("Kubernetes Events in Loki, ticket 27's proposed selector",
         '{service_name="unknown_service", service_namespace="otel-demo"} |= "email-"',
         minutes=30, limit=8)
    print("\n### traces")
    tempo("email spans", '{resource.service.name="email"}')
    tempo("email errored spans", '{resource.service.name="email" && status=error}',
          fetch_first=True)


def probe_cart():
    print("\n### alertable condition — the error log line")
    loki("cart's redis-connect line, ticket 10 verbatim",
         '{service_name="cart"} |= "Wasn\'t able to connect to redis"', minutes=15, limit=6)
    loki("cart logs with service_namespace (ticket 10 says this returns ZERO forever)",
         '{service_name="cart", service_namespace="otel-demo"} |= "redis"', minutes=15)
    loki("cart, any error", '{service_name="cart"} |~ "(?i)error|exception"',
         minutes=15, limit=6)
    loki("cart's EmptyCartAsync line, the ratio denominator",
         '{service_name="cart"} |= "EmptyCartAsync called with"', minutes=15, limit=4)
    print("\n### item 12 — the metric shape")
    prom("cart http server metric exists at all",
         'sum by (service_name) (rate(http_server_request_duration_seconds_count{service_name="cart"}[5m]))')
    prom("http_route as a label on cart",
         'sum by (http_route) (rate(http_server_request_duration_seconds_count{service_name="cart"}[5m]))')
    prom("cart error ratio on span metrics (ticket 10: ~5.2%, straddles 0.05)",
         'sum(rate(%s{service_name="cart",status_code="STATUS_CODE_ERROR"}[5m]))'
         ' / sum(rate(%s{service_name="cart"}[5m]))' % (SPAN, SPAN))
    prom("cart SERVER-only error ratio",
         'sum(rate(%s{service_name="cart",span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}[5m]))'
         ' / sum(rate(%s{service_name="cart",span_kind="SPAN_KIND_SERVER"}[5m]))' % (SPAN, SPAN))
    prom("cart ABSOLUTE error rate (ticket 10 wants this instead of a ratio)",
         'sum(rate(%s{service_name="cart",status_code="STATUS_CODE_ERROR"}[5m])) or vector(0)' % SPAN)
    print("\n### item 11 — the bad-path connect duration, the decisive number")
    prom("cart p95 http server duration, ticket 10 verbatim",
         'histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="cart"}[5m])))')
    prom("cart p99 http server duration",
         'histogram_quantile(0.99, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="cart"}[5m])))')
    prom("cart p95 SPAN duration, whatever the span-metrics histogram is called",
         'histogram_quantile(0.95, sum by (le) (rate({__name__=~"traces_span_metrics_duration.*bucket",service_name="cart"}[5m])))')
    prom("checkout p95 span duration — does cart's stall propagate?",
         'histogram_quantile(0.95, sum by (le) (rate({__name__=~"traces_span_metrics_duration.*bucket",service_name="checkout"}[5m])))')
    print("\n### diagnostic path")
    tempo("cart errored spans", '{resource.service.name="cart" && status=error}',
          fetch_first=True)
    kube_events("cart")


SETS = {"paymentUnreachable": probe_payment,
        "emailMemoryLeak": probe_email,
        "cartFailure": probe_cart}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    fault = argv[0]
    label = argv[1] if len(argv) > 1 else "on"
    if fault not in SETS:
        print("no probe set for %s" % fault, file=sys.stderr)
        return 2
    os.makedirs(CAP, exist_ok=True)
    print("=" * 72)
    print("FAULT PROBE — %s (%s)" % (fault, label))
    print("utc: %s   span metric: %s" % (time.strftime("%FT%TZ", time.gmtime()), SPAN))
    print("=" * 72)
    SETS[fault]()
    RESULT["_meta"] = {"fault": fault, "label": label, "span_metric": SPAN,
                       "utc": time.strftime("%FT%TZ", time.gmtime())}
    path = os.path.join(CAP, "faultprobe-%s-%s.json" % (fault, label))
    with open(path, "w") as f:
        json.dump(RESULT, f, indent=2, default=str)
    print("\n# artifact: capture/faultprobe-%s-%s.json" % (fault, label))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
