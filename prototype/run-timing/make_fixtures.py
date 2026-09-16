"""PROTOTYPE — throwaway. Generates the canned Cascade and the canned telemetry.

One Fault, seven Alerts, four signals. The numbers are made up but internally
consistent, so a Run that reads them carefully can reach the Ground truth and a
Run that skims cannot. Two red herrings are planted on purpose: a host CPU alert
that is a consequence, and an unrelated payment deploy fifty-two minutes before
the symptoms, which is the plausible wrong answer.

    python3 make_fixtures.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
FLIP = datetime(2026, 9, 15, 14, 2, 0, tzinfo=timezone.utc)
NOTIFIED = datetime(2026, 9, 15, 14, 7, 45, tzinfo=timezone.utc)
START = FLIP - timedelta(minutes=12)
POINTS = 21  # one a minute, 13:50 to 14:10


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def ramp(baseline: float, peak: float, begins: datetime, minutes: float = 6.0) -> list[list]:
    """A series that sits at `baseline`, then climbs to `peak` over `minutes` from `begins`."""
    series = []
    for index in range(POINTS):
        moment = START + timedelta(minutes=index)
        if moment < begins:
            value = baseline
        else:
            share = min(1.0, (moment - begins).total_seconds() / 60.0 / minutes)
            value = baseline + (peak - baseline) * share
        series.append([stamp(moment), round(value, 3)])
    return series


def flat(value: float, jitter: float = 0.0) -> list[list]:
    series = []
    for index in range(POINTS):
        moment = START + timedelta(minutes=index)
        wobble = jitter * ((index % 3) - 1)
        series.append([stamp(moment), round(value + wobble, 3)])
    return series


METRICS = {
    "container_memory_usage_bytes{service=\"recommendation\"}": {
        "unit": "bytes",
        "help": "resident memory of the recommendation container",
        "series": ramp(188_000_000, 947_000_000, FLIP, minutes=6.0),
    },
    "container_cpu_utilization{service=\"recommendation\"}": {
        "unit": "ratio",
        "help": "CPU utilization of the recommendation container, 1.0 is one core",
        "series": ramp(0.11, 0.94, FLIP, minutes=5.0),
    },
    "traces_span_metrics_duration_p99{service=\"recommendation\"}": {
        "unit": "ms",
        "help": "p99 of ListRecommendations, from the span_metrics connector",
        "series": ramp(42, 2380, FLIP + timedelta(seconds=30), minutes=5.0),
    },
    "traces_span_metrics_duration_p95{service=\"frontend\"}": {
        "unit": "ms",
        "help": "p95 of the frontend's HTTP handler",
        "series": ramp(118, 1910, FLIP + timedelta(minutes=1), minutes=5.0),
    },
    "envoy_http_downstream_rq_5xx{service=\"frontend-proxy\"}": {
        "unit": "per second",
        "help": "5xx responses leaving the edge proxy",
        "series": ramp(0.0, 4.2, FLIP + timedelta(minutes=2), minutes=4.0),
    },
    "traces_span_metrics_duration_p95{service=\"product-catalog\"}": {
        "unit": "ms",
        "help": "p95 of ListProducts and GetProduct",
        "series": ramp(17, 305, FLIP + timedelta(minutes=2), minutes=4.0),
    },
    "postgresql_backends{service=\"product-catalog\"}": {
        "unit": "connections",
        "help": "open PostgreSQL backends behind product-catalog",
        "series": ramp(6, 19, FLIP + timedelta(minutes=2), minutes=4.0),
    },
    "host_cpu_utilization{host=\"otel-demo-1\"}": {
        "unit": "ratio",
        "help": "CPU utilization of the whole host, all services together",
        "series": ramp(0.31, 0.88, FLIP + timedelta(minutes=2), minutes=5.0),
    },
    "traces_span_metrics_duration_p95{service=\"cart\"}": {
        "unit": "ms", "help": "p95 of the cart service", "series": flat(22, 1.5),
    },
    "traces_span_metrics_duration_p95{service=\"payment\"}": {
        "unit": "ms", "help": "p95 of the payment service", "series": flat(31, 2.0),
    },
    "traces_span_metrics_duration_p95{service=\"shipping\"}": {
        "unit": "ms", "help": "p95 of the shipping service", "series": flat(44, 3.0),
    },
    "container_memory_usage_bytes{service=\"payment\"}": {
        "unit": "bytes", "help": "resident memory of the payment container",
        "series": flat(96_000_000, 2_000_000),
    },
    "python_gc_pause_ms{service=\"recommendation\"}": {
        "unit": "ms",
        "help": "time spent in garbage collection per minute",
        "series": ramp(3, 181, FLIP + timedelta(seconds=30), minutes=6.0),
    },
}

CACHE_SIZES = [1043, 1310, 1638, 2048, 2560, 3200, 4001, 5002, 6252, 7816, 9770]


def logs() -> list[dict]:
    records: list[dict] = []
    # Before the flip: recommendation is quiet and the cache is serving.
    for index in range(4):
        moment = START + timedelta(minutes=index * 2)
        records.append({
            "timestamp": stamp(moment), "service": "recommendation", "severity": "INFO",
            "body": "ListRecommendations served 5 products in 38ms (cache_hit=true)",
        })
    records.append({
        "timestamp": stamp(FLIP), "service": "flagd", "severity": "INFO",
        "body": "configuration_change received: 1 flag changed",
    })
    # After the flip: the cache stops serving and starts growing.
    for index, size in enumerate(CACHE_SIZES):
        moment = FLIP + timedelta(seconds=20 + index * 30)
        records.append({
            "timestamp": stamp(moment), "service": "recommendation", "severity": "WARN",
            "body": f"cache miss: recommendation cache size now {size} entries",
        })
    for index, pause in enumerate((12, 41, 88, 140, 181)):
        moment = FLIP + timedelta(minutes=1 + index)
        records.append({
            "timestamp": stamp(moment), "service": "recommendation", "severity": "WARN",
            "body": f"gc: collected generation 2 in {pause}ms, heap still growing",
        })
    for index in range(6):
        moment = FLIP + timedelta(minutes=1, seconds=index * 45)
        records.append({
            "timestamp": stamp(moment), "service": "frontend", "severity": "ERROR",
            "body": "upstream deadline exceeded calling recommendation:1010 ListRecommendations",
        })
    for index in range(5):
        moment = FLIP + timedelta(minutes=2, seconds=index * 50)
        records.append({
            "timestamp": stamp(moment), "service": "frontend-proxy", "severity": "ERROR",
            "body": 'GET /api/recommendations HTTP/1.1" 504 UT 0 1 15001 - "envoy" upstream_reset_before_response_started',
        })
    for index in range(3):
        moment = FLIP + timedelta(minutes=3, seconds=index * 60)
        records.append({
            "timestamp": stamp(moment), "service": "product-catalog", "severity": "WARN",
            "body": "ListProducts took 288ms, 19 backends open, called 41x in the last minute",
        })
    # Controls: services that are fine, so a Run can rule them out.
    for index in range(3):
        moment = FLIP + timedelta(minutes=index)
        records.append({
            "timestamp": stamp(moment), "service": "payment", "severity": "INFO",
            "body": "Charge request completed, transaction approved",
        })
        records.append({
            "timestamp": stamp(moment), "service": "cart", "severity": "INFO",
            "body": "GetCart completed in 21ms",
        })
    records.sort(key=lambda record: record["timestamp"])
    return records


TRACES = [
    {
        "traceId": "3f5c1a90b7d4e2118a6c0f3e9d215b47",
        "startTime": stamp(FLIP + timedelta(minutes=4, seconds=12)),
        "durationMs": 2412,
        "rootService": "frontend",
        "rootName": "GET /api/recommendations",
        "status": "ERROR",
        "spans": [
            {"service": "frontend", "name": "GET /api/recommendations", "durationMs": 2412,
             "status": "ERROR", "attributes": {"http.status_code": 504}},
            {"service": "recommendation", "name": "ListRecommendations", "durationMs": 2380,
             "status": "OK",
             "attributes": {
                 "demo.recommendation.cache_hit": False,
                 "demo.feature_flag.recommendation_cache": True,
                 "app.recommendation.cache_size": 7816,
                 "app.filtered_products.count": 5,
             }},
            {"service": "product-catalog", "name": "ListProducts", "durationMs": 291,
             "status": "OK", "attributes": {"db.system": "postgresql", "app.products.count": 10}},
        ],
    },
    {
        "traceId": "bb70c4e2119d3a5f8e61c0742a9f3d16",
        "startTime": stamp(FLIP - timedelta(minutes=6)),
        "durationMs": 131,
        "rootService": "frontend",
        "rootName": "GET /api/recommendations",
        "status": "OK",
        "spans": [
            {"service": "frontend", "name": "GET /api/recommendations", "durationMs": 131,
             "status": "OK", "attributes": {"http.status_code": 200}},
            {"service": "recommendation", "name": "ListRecommendations", "durationMs": 39,
             "status": "OK",
             "attributes": {
                 "demo.recommendation.cache_hit": True,
                 "demo.feature_flag.recommendation_cache": False,
                 "app.recommendation.cache_size": 1043,
                 "app.filtered_products.count": 5,
             }},
            {"service": "product-catalog", "name": "ListProducts", "durationMs": 16,
             "status": "OK", "attributes": {"db.system": "postgresql", "app.products.count": 10}},
        ],
    },
    {
        "traceId": "9a1e4d77c3b05f2648de1a9b0c573e82",
        "startTime": stamp(FLIP + timedelta(minutes=5, seconds=40)),
        "durationMs": 1974,
        "rootService": "frontend",
        "rootName": "GET /",
        "status": "OK",
        "spans": [
            {"service": "frontend", "name": "GET /", "durationMs": 1974, "status": "OK",
             "attributes": {"http.status_code": 200}},
            {"service": "recommendation", "name": "ListRecommendations", "durationMs": 1902,
             "status": "OK",
             "attributes": {
                 "demo.recommendation.cache_hit": False,
                 "demo.feature_flag.recommendation_cache": True,
                 "app.recommendation.cache_size": 6252,
             }},
            {"service": "ad", "name": "GetAds", "durationMs": 31, "status": "OK", "attributes": {}},
        ],
    },
    {
        "traceId": "c20b8f6134ae95d7021f4c8a6b3d9e05",
        "startTime": stamp(FLIP + timedelta(minutes=3)),
        "durationMs": 212,
        "rootService": "frontend",
        "rootName": "POST /api/checkout",
        "status": "OK",
        "spans": [
            {"service": "frontend", "name": "POST /api/checkout", "durationMs": 212, "status": "OK",
             "attributes": {"http.status_code": 200}},
            {"service": "checkout", "name": "PlaceOrder", "durationMs": 188, "status": "OK",
             "attributes": {}},
            {"service": "payment", "name": "Charge", "durationMs": 30, "status": "OK",
             "attributes": {"app.payment.charged": True}},
            {"service": "shipping", "name": "ShipOrder", "durationMs": 43, "status": "OK",
             "attributes": {}},
        ],
    },
]

CHANGES = [
    {
        "id": 411,
        "time": stamp(FLIP - timedelta(minutes=52)),
        "source": "ci",
        "tags": ["deploy", "payment"],
        "text": "deploy: payment v1.8.3 rolled out to otel-demo (2 replicas)",
    },
    {
        "id": 412,
        "time": stamp(FLIP),
        "source": "flagd-watcher",
        "tags": ["feature-flag", "recommendation"],
        "text": "feature flag recommendationCache set to on (variant: on, previously off)",
    },
    {
        "id": 413,
        "time": stamp(FLIP - timedelta(hours=6)),
        "source": "ci",
        "tags": ["deploy", "frontend"],
        "text": "deploy: frontend v2.1.0 rolled out to otel-demo (3 replicas)",
    },
]

ALERTS = [
    ("RecommendationLatencyP99High", "recommendation", "recommendation:1010", "critical",
     "recommendation ListRecommendations p99 is above 1s",
     "p99 of ListRecommendations has been above the 1000ms threshold for two minutes.",
     "f1a2b3c4d5e60718", 2380.0, timedelta(minutes=2, seconds=30)),
    ("RecommendationMemoryClimbing", "recommendation", "recommendation:1010", "warning",
     "recommendation resident memory is climbing",
     "Container memory for recommendation has grown by more than 300MB in five minutes.",
     "a9b8c7d6e5f40312", 812_000_000.0, timedelta(minutes=3)),
    ("RecommendationCpuSaturated", "recommendation", "recommendation:1010", "warning",
     "recommendation is using nearly a whole core",
     "CPU utilization for recommendation has been above 0.85 for one minute.",
     "0c1d2e3f4a5b6970", 0.91, timedelta(minutes=3, seconds=30)),
    ("FrontendLatencyP95High", "frontend", "frontend:8080", "critical",
     "frontend p95 latency is above 1s",
     "p95 of the frontend HTTP handler has been above the 1000ms threshold for one minute.",
     "7e6d5c4b3a291807", 1910.0, timedelta(minutes=4)),
    ("FrontendProxyErrorRate", "frontend-proxy", "frontend-proxy:8080", "warning",
     "the edge proxy is returning 5xx",
     "Envoy is returning more than 1 5xx per second at the edge.",
     "2b3c4d5e6f708192", 4.2, timedelta(minutes=4, seconds=30)),
    ("ProductCatalogLatencyP95High", "product-catalog", "product-catalog:3550", "warning",
     "product-catalog p95 latency is above 200ms",
     "p95 of ListProducts and GetProduct has been above 200ms for one minute.",
     "8f9e0d1c2b3a4556", 305.0, timedelta(minutes=5)),
    ("HostCpuHigh", "host", "otel-demo-1", "warning",
     "host CPU is above 85 percent",
     "Whole-host CPU utilization has been above 0.85 for one minute.",
     "4d5e6f708192a3b4", 0.88, timedelta(minutes=5, seconds=30)),
]


def alert(name, service, instance, severity, summary, description, fingerprint, value, offset):
    starts = FLIP + offset
    return {
        "status": "firing",
        "labels": {
            "alertname": name,
            "grafana_folder": "otel-demo",
            "instance": instance,
            "service": service,
            "severity": severity,
        },
        "annotations": {"description": description, "summary": summary},
        "startsAt": stamp(starts),
        "endsAt": "0001-01-01T00:00:00Z",
        "generatorURL": f"http://localhost:3000/alerting/grafana/{name.lower()}/view?orgId=1",
        "fingerprint": fingerprint,
        "silenceURL": f"http://localhost:3000/alerting/silence/new?alertmanager=grafana&matcher=alertname%3D{name}",
        "dashboardURL": "http://localhost:3000/d/otel-demo-services/services?orgId=1",
        "panelURL": f"http://localhost:3000/d/otel-demo-services/services?orgId=1&viewPanel={abs(hash(name)) % 40 + 1}",
        "values": {"A": value},
        "valueString": f"[ var='A' labels={{service={service}}} value={value} ]",
        "orgId": 1,
    }


def notification() -> dict:
    alerts = [alert(*row) for row in ALERTS]
    return {
        "receiver": "demo-receiver",
        "status": "firing",
        "alerts": alerts,
        "groupLabels": {"grafana_folder": "otel-demo"},
        "commonLabels": {"grafana_folder": "otel-demo"},
        "commonAnnotations": {},
        "externalURL": "http://localhost:3000/",
        "version": "1",
        "groupKey": '{}:{grafana_folder="otel-demo"}',
        "truncatedAlerts": 0,
        "orgId": 1,
        "title": "[FIRING:7] otel-demo",
        "state": "alerting",
        "message": "**Firing**\n\n" + "\n".join(
            f"- {one['labels']['alertname']} ({one['labels']['service']}, {one['labels']['severity']})"
            for one in alerts
        ),
        "notifiedAt": stamp(NOTIFIED),
    }


def write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {path.relative_to(HERE)}")


def main() -> None:
    write(HERE / "fixtures" / "notification-cascade.json", notification())
    write(HERE / "telemetry" / "metrics.json", METRICS)
    write(HERE / "telemetry" / "traces.json", TRACES)
    write(HERE / "telemetry" / "changes.json", CHANGES)
    log_path = HERE / "telemetry" / "logs.jsonl"
    log_path.write_text("".join(json.dumps(record) + "\n" for record in logs()))
    print(f"wrote {log_path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
