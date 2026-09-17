# Verify the signal surface and settle the Fault gates

Type: prototype
Status: open
Blocked by: 10

## Question

[Faults and their Cascades](10-faults-and-their-cascades.md) chose three Faults and wrote
every query they rest on. **Almost none of those queries have been run at this venue.**
No application service's logs have ever been retrieved from this venue's Loki, Tempo has
never been queried here for anything, and the 578 Prometheus metric names were counted but
never enumerated — so `traces_span_metrics_calls_total` is a probable name backed by prose
in a summary, not by an artifact.

That is the same failure mode that has now cost this project three decisions: a plausible
claim that nobody ran. Run them.

This ticket also owns the two gates that
[Faults and their Cascades](10-faults-and-their-cascades.md) left open on the Fault menu,
because they need the same cluster-hour, and the timing budgets that ticket wrote as
estimates rather than measurements.

**If the Float gate below kills `emailMemoryLeak`, this ticket reopens the Kubernetes
signal class**, which would be its fourth refutation — say so loudly rather than quietly
substituting another Fault.

### Items 1 to 6 are venue-wide and gate everything else

1. **Does any application log reach this venue's Loki?**
   `curl -G "$LOKI/loki/api/v1/label/service_name/values"` — one call settles the whole
   logs column.
2. **Which `service_namespace` do application streams actually carry?**
   `curl -G "$LOKI/loki/api/v1/label/service_namespace/values"`. Only the *collector's*
   value has ever been measured. The expectation is `opentelemetry-demo` for apps and
   `otel-demo` only for Kubernetes Events.
3. **Enumerate the metric names.** `curl -G ".../api/v1/label/__name__/values"`.
   `check-grafana.sh` already calls this endpoint and prints only a count; the fix is one
   `print()`. Confirm or refute `traces_span_metrics_calls_total`,
   `traces_span_metrics_duration_milliseconds_bucket`, `container_memory_working_set_bytes`,
   `k8s_container_restarts` and `rpc_server_call_duration_seconds_*`.
4. **Query Tempo once**, at all:
   `GET /api/datasources/proxy/uid/tempo/api/search?q={resource.service.name="checkout"}`.
   Confirm TraceQL shape and whether `event:name` is supported on this Tempo.
5. **Capture a flags-off baseline.** `sum by (service_name) (rate(traces_span_metrics_calls_total[5m]))`
   and the same filtered to `status_code="STATUS_CODE_ERROR"`. Four proposed thresholds
   depend on numbers that have never been sampled. Commit the capture.
6. **Do span metrics carry `span_kind`?**
   `sum by (span_kind) (traces_span_metrics_calls_total{service_name="checkout"})`. This is
   the fix for every inflated ratio denominator.

### Items 7 to 12 are the three chosen Faults

7. **email, the leak rate.** Flip to `1000x`, watch
   `kubectl -n otel-demo get pod -l ...email -w` plus `kubectl top pod` every 20 s. The
   container's **baseline RSS has never been measured and dominates every OOM estimate**.
8. **email, the Float gate.** `fetch_number_value` may return a Float, and Ruby's
   `String#*` requires an Integer — a Float raises `TypeError` and produces a 500 rather
   than a leak. Smoke-test before relying on the mechanism.
9. **email, the restart evidence.** After the first OOMKill, confirm what a read-only Run
   can actually retrieve: `containerStatuses[].lastState.terminated.reason` via `kubectl`,
   and whether restart-lifecycle Events appear under
   `{service_name="unknown_service", service_namespace="otel-demo"} |= "email-"` with a
   real `object.reason` body. **No OOMKill has ever happened at this venue.**
10. **payment, the checkout ceiling.** `kubectl top pod` on checkout every 60 s through a
    full 15-minute fault window. It sits at 18 Mi of a 20 Mi limit with `GOMEMLIMIT=16MiB`
    and the Fault leaks a connection per failed order.
11. **cart, the bad-path connect duration.** Upper bound is exactly 150.5 s
    (`ConnectTimeout 5000 × ConnectRetry 30`) with a lock around a synchronous `Connect()`.
    This one number decides whether the Fault is silent or destabilising:
    `histogram_quantile(0.95, sum by (le)(rate(http_server_request_duration_seconds_bucket{service_name="cart"}[5m])))`.
12. **cart, the metric shape.** Whether `http_route` is a label, and whether the ~5.2%
    error ratio sits above or below 0.05.

### Item 13 is a trap, not a measurement

13. **Do the .NET and Go flagd providers reconnect after a flagd rollout?** Only the Java
    provider has ever been verified. A wedged channel falls back to the code default and
    the Fault silently never fires. The check is not to verify flagd — it is to **confirm
    one real symptom before starting the clock**, for each of the three Faults.

### Then the timing budgets

[Faults and their Cascades](10-faults-and-their-cascades.md) budgeted injection → rollout →
first symptom → first Alert → last Alert, as estimates. Measure them once
[Alert rules for a Cascade](28-alert-rules-for-a-cascade.md) has thresholds to measure
against, and correct that ticket's numbers in place.

**This ticket spends money.** Same discipline as
[Can one DOKS node hold the chart](26-can-one-doks-node-hold-the-chart.md): ask before
creating, never without `--ha=false`, `--size` and `--count`, and destroy in the same
session. Items 1 to 6 are six `curl` calls and want minutes, not hours. Bring the cluster
up inside the working window, not the morning of — LGTM climbs ~14 Mi/min against a 4 GiB
limit.
