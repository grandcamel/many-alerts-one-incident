#!/usr/bin/env python3
"""Ticket 27, items 1 to 6 — the venue-wide sweep that gates everything else.

Runs with every fault flag OFF. Writes a human-readable report to stdout and
every raw answer to capture/ as an artifact, because the thing this ticket
exists to fix is claims backed by prose rather than by a file.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graf  # noqa: E402

CAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "capture")

# The five names ticket 10's queries rest on. Prose, until this run.
CLAIMED = [
    "traces_span_metrics_calls_total",
    "traces_span_metrics_duration_milliseconds_bucket",
    "container_memory_working_set_bytes",
    "k8s_container_restarts",
    "rpc_server_call_duration_seconds_count",
]

# Application services ticket 10 names, to check against Loki's real label set.
APPS = ["checkout", "cart", "email", "payment", "ad", "frontend", "frontend-proxy",
        "shipping", "currency", "product-catalog", "recommendation", "quote",
        "accounting", "fraud-detection", "flagd", "image-provider", "load-generator"]


def save(name, obj):
    path = os.path.join(CAP, name)
    with open(path, "w") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, indent=2, default=str)
    return path


def head(n, title):
    print("\n" + "=" * 72)
    print("ITEM %s — %s" % (n, title))
    print("=" * 72)


def main():
    os.makedirs(CAP, exist_ok=True)
    print("# ticket 27, items 1-6, venue-wide sweep")
    print("# utc: %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ds = graf.datasources()
    print("# datasources: %s" % json.dumps(ds))
    save("00-datasources.json", ds)
    report = {}

    # ---- item 1 -----------------------------------------------------------
    head(1, "does any application log reach this venue's Loki?")
    svc = graf.loki_label("service_name")
    save("01-loki-service_name-values.json", svc)
    print("%d service_name values in Loki:" % len(svc))
    for v in sorted(svc):
        print("   ", v)
    found = sorted(set(svc) & set(APPS))
    missing = sorted(set(APPS) - set(svc))
    print("\nticket 10's services PRESENT (%d): %s" % (len(found), ", ".join(found) or "none"))
    print("ticket 10's services ABSENT  (%d): %s" % (len(missing), ", ".join(missing) or "none"))
    report["item1_service_name_values"] = sorted(svc)
    report["item1_apps_present"] = found
    report["item1_apps_absent"] = missing

    all_labels = graf.loki_labels()
    save("01-loki-stream-labels.json", all_labels)
    print("\nall Loki stream labels (%d): %s" % (len(all_labels), ", ".join(sorted(all_labels))))
    report["item1_stream_labels"] = sorted(all_labels)

    # A real line from a real application service settles it beyond the label.
    for cand in ["checkout", "cart", "ad", "frontend", "payment", "email"]:
        if cand in svc:
            lines = graf.loki_lines('{service_name="%s"}' % cand, minutes=15, limit=3)
            print("\nsample lines from {service_name=\"%s\"}: %d" % (cand, len(lines)))
            for ns, line, stream in lines:
                print("   ", ns, line[:200].replace("\n", " "))
            if lines:
                save("01-loki-sample-%s.json" % cand,
                     [{"ts": n, "line": l, "stream": s} for n, l, s in lines])
                report["item1_proof_service"] = cand
                report["item1_proof_lines"] = len(lines)
                break

    # ---- item 2 -----------------------------------------------------------
    head(2, "which service_namespace do application streams carry?")
    nsv = graf.loki_label("service_namespace")
    save("02-loki-service_namespace-values.json", nsv)
    print("service_namespace values: %s" % (", ".join(sorted(nsv)) or "NONE"))
    report["item2_service_namespace_values"] = sorted(nsv)
    for expect in ["opentelemetry-demo", "otel-demo"]:
        r = graf.loki_query('{service_namespace="%s"}' % expect, minutes=15, limit=5)
        n = len(r.get("json", {}).get("data", {}).get("result", []) or [])
        print('  {service_namespace="%s"} -> %d streams' % (expect, n))
        report["item2_streams_%s" % expect] = n
    # And the pairing that actually matters: which namespace does an app carry?
    if report.get("item1_proof_service"):
        lines = graf.loki_lines('{service_name="%s"}' % report["item1_proof_service"],
                                minutes=15, limit=1)
        if lines:
            print("  %s stream labels: %s" % (report["item1_proof_service"],
                                              json.dumps(lines[0][2])))
            report["item2_app_stream_labels"] = lines[0][2]

    # ---- item 3 -----------------------------------------------------------
    head(3, "enumerate the metric names")
    names = graf.prom_names()
    save("03-prom-metric-names.txt", "\n".join(sorted(names)))
    print("%d metric names (full list: capture/03-prom-metric-names.txt)" % len(names))
    report["item3_metric_count"] = len(names)
    print("\nthe five ticket 10 rests on:")
    for c in CLAIMED:
        hit = c in names
        near = [n for n in names if n.startswith(c.rsplit("_", 1)[0][:28])][:6]
        print("  %-52s %s" % (c, "CONFIRMED" if hit else "ABSENT"))
        if not hit and near:
            print("      nearest: %s" % ", ".join(near))
        report.setdefault("item3_claimed", {})[c] = {"present": hit, "nearest": near}
    for pfx in ["traces_span", "rpc_server", "container_memory", "k8s_container",
                "http_server", "kube_"]:
        got = sorted(n for n in names if n.startswith(pfx))
        print("\n  %s* (%d): %s" % (pfx, len(got), ", ".join(got[:12])))
        report.setdefault("item3_families", {})[pfx] = got

    # ---- item 4 -----------------------------------------------------------
    head(4, "query Tempo once, at all")
    tags = graf.tempo_tags()
    save("04-tempo-tags.json", tags.get("json", tags))
    print("tags endpoint: HTTP %s in %.0f ms" % (tags.get("code"), tags.get("ms", 0)))
    scopes = tags.get("json", {}).get("scopes", []) or []
    for s in scopes:
        print("  scope %-12s %d tags: %s" % (s.get("name"), len(s.get("tags", []) or []),
                                             ", ".join((s.get("tags") or [])[:10])))
    report["item4_tempo_scopes"] = {s.get("name"): (s.get("tags") or []) for s in scopes}

    for q in ['{resource.service.name="checkout"}',
              '{resource.service.name="checkout" && status=error}',
              '{event:name!=""}',
              '{span.rpc.method!=""}']:
        r = graf.tempo_search(q, minutes=15)
        traces = r.get("json", {}).get("traces", []) or []
        err = r.get("json", {}).get("error") or r.get("text", "")[:200]
        print("\n  %-56s HTTP %s  %d traces  %.0f ms" % (q, r.get("code"), len(traces), r.get("ms", 0)))
        if err and not traces:
            print("      %s" % err.replace("\n", " ")[:200])
        report.setdefault("item4_queries", {})[q] = {
            "code": r.get("code"), "traces": len(traces), "ms": round(r.get("ms", 0)),
            "error": err if not traces else None}
        save("04-tempo-%s.json" % (
            q.replace(" ", "").replace("{", "").replace("}", "")
             .replace('"', "").replace("=", "-").replace("!", "not")
             .replace("&", "_").replace(".", "_").replace(":", "-")[:48]),
             r.get("json", r))

    # ---- item 5 -----------------------------------------------------------
    head(5, "flags-off baseline")
    metric = "traces_span_metrics_calls_total"
    if metric not in names:
        cands = [n for n in names if "calls" in n and "span" in n]
        if cands:
            metric = cands[0]
            print("!! %s absent; using the real name: %s" % (CLAIMED[0], metric))
    base = {}
    for label, q in [
        ("all", 'sum by (service_name) (rate(%s[5m]))' % metric),
        ("error", 'sum by (service_name) (rate(%s{status_code="STATUS_CODE_ERROR"}[5m]))' % metric),
        ("server_all", 'sum by (service_name) (rate(%s{span_kind="SPAN_KIND_SERVER"}[5m]))' % metric),
        ("server_error", 'sum by (service_name) (rate(%s{span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}[5m]))' % metric),
    ]:
        rows = graf.prom_scalars(q)
        base[label] = {m.get("service_name", "?"): v for m, v in rows}
        print("\n  %s — %d series" % (label, len(rows)))
        for svc_name, v in sorted(base[label].items(), key=lambda kv: -(kv[1] or 0)):
            print("     %-22s %.4f/s" % (svc_name, v or 0))
    save("05-baseline-span-metrics.json", {"metric": metric, "series": base,
                                           "utc": time.strftime("%FT%TZ", time.gmtime())})
    report["item5_metric_used"] = metric
    report["item5_baseline"] = base
    ratios = {}
    for svc_name, tot in base.get("server_all", {}).items():
        errs = base.get("server_error", {}).get(svc_name, 0.0) or 0.0
        if tot:
            ratios[svc_name] = errs / tot
    print("\n  steady-state SERVER error ratio per service:")
    for svc_name, r_ in sorted(ratios.items(), key=lambda kv: -kv[1]):
        print("     %-22s %.4f" % (svc_name, r_))
    report["item5_server_error_ratio"] = ratios

    # cart's own http server metrics, the ticket-12 question, sampled at baseline
    for q in ['sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))',
              'sum by (http_route) (rate(http_server_request_duration_seconds_count{service_name="cart"}[5m]))']:
        rows = graf.prom_scalars(q)
        print("\n  %s -> %d series" % (q, len(rows)))
        for m, v in rows[:10]:
            print("     %-40s %.4f" % (json.dumps(m), v or 0))
        report.setdefault("item5_http_server", {})[q] = [
            {"labels": m, "value": v} for m, v in rows]

    # ---- item 6 -----------------------------------------------------------
    head(6, "do span metrics carry span_kind?")
    kinds = graf.prom_label("span_kind", metric)
    print("span_kind label values on %s: %s" % (metric, ", ".join(kinds) or "NONE"))
    report["item6_span_kind_values"] = kinds
    rows = graf.prom_scalars('sum by (span_kind) (%s{service_name="checkout"})' % metric)
    print("\n  checkout totals by span_kind:")
    for m, v in rows:
        print("     %-28s %.1f" % (m.get("span_kind", "(none)"), v or 0))
    report["item6_checkout_by_kind"] = {m.get("span_kind", "(none)"): v for m, v in rows}
    dims = {}
    for lbl in ["service_name", "status_code", "span_kind", "span_name",
                "collector_instance_id", "service_namespace", "http_route"]:
        vals = graf.prom_label(lbl, metric)
        dims[lbl] = len(vals)
        print("  dimension %-24s %d values%s" % (
            lbl, len(vals), "  " + ", ".join(vals[:4]) if 0 < len(vals) <= 6 else ""))
    report["item6_dimension_cardinality"] = dims
    save("06-span-metrics-dimensions.json", {"span_kind": kinds, "dims": dims,
                                             "checkout_by_kind": report["item6_checkout_by_kind"]})

    save("ITEMS-1-6.json", report)
    print("\n\n# items 1-6 complete; raw artifacts in capture/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
