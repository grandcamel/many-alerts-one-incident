#!/usr/bin/env bash
# PROTOTYPE — throwaway. Ticket 08, "Can the laptop hold it".
# Is Grafana usable while the stack runs, and did telemetry actually land?
set -u
G=http://localhost:3000
say() { printf '\n== %s ==\n' "$1"; }

say "grafana health (and how long it took)"
curl -s -o /dev/null -w '  http=%{http_code}  total=%{time_total}s\n' "$G/api/health"
curl -s "$G/api/health" | head -c 300; echo

say "datasources"
curl -s "$G/api/datasources" | yq -p json -o json e '.[] | .name + " (" + .type + ") uid=" + .uid' 2>/dev/null \
  || curl -s "$G/api/datasources" | head -c 500

say "prometheus: demo services reporting"
curl -s -G "$G/api/datasources/proxy/uid/prometheus/api/v1/query" \
  --data-urlencode 'query=count by (job) ({__name__=~".+"})' 2>/dev/null | head -c 600; echo

say "prometheus: span metrics (proves the collector->LGTM chain)"
curl -s -G "$G/api/datasources/proxy/uid/prometheus/api/v1/query" \
  --data-urlencode 'query=count(traces_span_metrics_calls_total)' 2>/dev/null | head -c 400; echo

say "dashboard render timing (usability under load)"
for i in 1 2 3; do
  curl -s -o /dev/null -w "  attempt $i: http=%{http_code} total=%{time_total}s\n" "$G/api/search?limit=20"
done
