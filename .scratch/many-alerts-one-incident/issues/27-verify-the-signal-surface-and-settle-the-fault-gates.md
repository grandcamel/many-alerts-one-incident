# Verify the signal surface and settle the Fault gates

Type: prototype
Status: resolved
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

## Answer

Resolved 2026-09-17 by a prototype run on one `s-8vcpu-16gb` DOKS node — **81
minutes, $0.19, destroyed in the same session**, with no cluster, load balancer
or volume left behind. Harness and 61 raw artifacts on branch
`prototype/signal-surface`; the full write-up is
`prototype/signal-surface/results/SUMMARY.md`.

**The headline: the signal surface is real and the three Faults survive.** Every
query ticket 10 wrote is now either verified or corrected against a file. Both
gates that could have killed a Fault came back clean, and **the Kubernetes signal
class is not refuted a fourth time.**

### The two gates, first, because they could have changed the menu

**Item 8 — the Float gate does NOT fire. `emailMemoryLeak` survives.** The flag
JSON holds integers and the Ruby service leaks exactly as designed: no
`TypeError`, no 500s, **zero** email log lines matching `error|exception|memory`
across a twenty-minute window. Baseline RSS is **51.7 Mi against a 100 Mi limit**
— the number that had never been measured and that dominates every OOM estimate —
so the climb crosses 48.3 Mi, not 100. **Five OOMKills** in 1181 s.

**Item 11 — cart's bad-path connect duration is 5.58 s at p99, not 150.5 s.**
The theoretical ceiling (`ConnectTimeout 5000 × ConnectRetry 30` behind a lock
around a synchronous `Connect()`) does not materialise — about **27× under the
bound** — almost certainly because the hostname fails DNS resolution rather than
exhausting thirty connect timeouts, the same mechanism Fault 1 shows. **Fault 3
is a silent Fault; the demo-destabilising risk is refuted.** cart and checkout
both stayed healthy throughout.

### Items 1 to 6 — the venue-wide sweep

1. **Application logs DO reach this venue's Loki.** 17 `service_name` values, 14
   of them ticket 10's services, with real lines retrieved. The whole logs column
   of ticket 10's signal table is real rather than source-derived. Still absent:
   **`flagd`**, `frontend`, `image-provider`.
2. **The `service_namespace` trap holds, and is sharper than written.**
   `otel-demo` selects only the collector's own logs; applications carry
   `opentelemetry-demo`. **But `cart`, `quote` and `accounting` carry no
   `service_namespace` stream label at all**, so for cart — the service carrying
   Fault 3 — even the *correct* value returns zero streams.
3. **All five claimed metric names CONFIRMED**, including
   `traces_span_metrics_calls_total`. 585 names enumerated to a file.
4. **Tempo answers**, `event:name` is supported as an intrinsic, and event-scoped
   attributes are queryable as `event.<key>`. Four tag scopes: intrinsic 20,
   resource 44, span 155, event 16.
5. **Baseline captured, and steady state is genuinely clean** — every service
   reads 0.0000/s error rate, so the error series simply does not exist until a
   Fault fires.
6. **`span_kind` is carried, five values, and the distortion is worse than
   written**: checkout has 131 CLIENT spans to 13 SERVER — a **10×** denominator
   inflation, not the ~6× implied.

### Item 13 — a real symptom was confirmed before every clock

For each Fault, flagd was shown to hold the new variant *and* a real symptom was
observed in the telemetry before any timing was trusted. **No provider wedged.**
The check earned its place immediately: this harness's own first "symptom" fired
**7 seconds** after injection and was a false positive — see the absence trap.

### Items 7, 9, 10 and 12

- **Item 7 — the leak rate.** OOM cycle **124–373 s, mean 264 s (~4.4 min)**,
  **inside ticket 10's budgeted 3–9 minutes**. Reading the rate off the *first*
  cycle alone gave "~100 s" and was wrong; four later kills refute it.
- **Item 9 — the restart evidence, in full.** `lastState.terminated` gives
  `OOMKilled`, `exitCode: 137`, with timestamps, via read-only `kubectl`. **There
  is no OOMKilled Kubernetes Event** — eight Events name the pod, all `Normal`.
  **Ticket 10's central correction is confirmed at this venue.** The restart
  lifecycle *does* reach Loki (`Created`/`Started` with `count=2`) under
  **both** this ticket's proposed selector and the bare form.
  `k8s_container_restarts` behaves as a gauge; `changes(…[10m])` reads 1.0.
  The caller's WARN is real and diagnostic — `…Post "http://email:8080/send_order_confirmation": EOF`
  — where the `EOF` **is** the kill landing mid-request.
- **Item 10 — the checkout ceiling did not bite.** Over a full 12-minute
  `paymentUnreachable` window checkout went **17 → 18 Mi against its 20 Mi limit,
  restarts=0**. The leaked connection per failed order did not move the working
  set measurably. Ticket 10's "keep the window under ~15 minutes" is not
  disproved — only 12 were tested — but the hazard is far less acute than the
  18-of-20-Mi framing implies.
- **Item 12 — the metric shape.** **`http_route` IS a label** on
  `http_server_request_duration_seconds_count` (3 cart routes) and is **not** a
  span-metrics dimension. **cart's SERVER-only error ratio is 0.05337** — ticket
  10 predicted "~5.2%, straddles 0.05" and that is almost exactly right, *at the
  `100%` variant*, so **any lower variant sits decisively below the threshold**.
  The ratio rule is unusable and ticket 10's call for an absolute rate against a
  measured baseline is confirmed: **0.0496/s against a 0.0000/s baseline.**

### Four new traps, each with an artifact

1. **Two span-metrics families exist.** The collector's `span_metrics` connector
   emits `traces_span_metrics_*`; the LGTM image's own Tempo metrics-generator
   emits `traces_spanmetrics_*`. The latter carries **no `service_name` label**
   and **never emits `STATUS_CODE_ERROR`**. A rule on the wrong family silently
   returns nothing usable.
2. **`or vector(0)` is dangerous on an absence rule.** The collector pushes every
   60 s, so `rate()` over `[30s]` or `[1m]` has fewer than two samples and
   returns **no series**; `or vector(0)` converts that emptiness into a confident
   **0**, indistinguishable from the Fault, and the rule fires permanently at
   steady state. `[2m]` is the minimum that produces a value; ticket 10's `[5m]`
   is correct. Ticket 10 prescribes `or vector(0)` as the NoData fix — right for
   ratio rules, wrong for absence rules.
3. **.NET log bodies are message TEMPLATES.** cart's lines arrive literally as
   `Error status code '{StatusCode}' with detail '{Detail}' raised.`, with the
   values in **structured metadata**. So `|= "EnsureRedisConnected"` and
   `|= "ApplicationException"` return **0 lines**, while
   `| Detail =~ ".*EnsureRedisConnected.*"` returns 5. **Ticket 10's diagnostic
   path for Fault 3 is written against a line filter that cannot work.** The full
   stack frame with file and line numbers *is* there — in `Detail`.
4. **cart's error lines carry `severity_text: "Information"`, not Error.** A
   severity-based log rule would miss Fault 3 entirely.

### The Cascade is reachable honestly — measured

Under `paymentUnreachable`, the error-ratio condition instantiates over **3**
services with meaningful rates (frontend 0.350/s, frontend-proxy 0.183/s,
checkout 0.175/s) and the absence condition over **4** (email, accounting,
fraud-detection, payment). **7 Alerts from 2 conditions**, inside ticket 10's
six-to-nine target with no rule-count inflation.

But **two of ticket 10's six absence services do not go absent**: **shipping**
runs 0.279 → 0.267/s because the quote is fetched *before* the charge (only
`POST /ship-order` goes to zero), and **cart** stays at 2.8/s because
GetCart/AddItem dominate. A service-level absence rule on either **never fires**.
And payment's traffic is **0.0042/s, not "exactly zero"** — a `< 0.01` threshold
still works, the word does not.

**Fault 2 raises almost no Cascade**: email's own error span-metric is an empty
series, `{resource.service.name="email" && status=error}` returns **0 traces**,
and the blast radius is noise-level. Two conditions on one service — about 2–3
Alerts. Correct for a rehearsal Fault, and ticket 28 should not size rules
expecting breadth there. It also **confirms the Ground truth**: no customer sees
an error and no order is lost.

### The recovery edge — answering ticket 28 early

A rule **does not go NoData on recovery**. The bare and `or vector(0)` forms
return the same value at every step after the undo, so the series still exists
and reads a genuine **0**: Prometheus keeps the counter, and `rate()` over an
unchanging counter is 0, not empty. The asymmetry is **NoData before injection,
Alerting during, Normal after** — so **Resolved does fire**. Recovery takes
**~4 minutes**, which is the `[5m]` window draining, not the system healing; the
log condition stopped inside the first minute.

### Timing — the half that needs no Alert rules

| step | measured | ticket 10 budgeted |
|---|---|---|
| ConfigMap write | 1–2 s | — |
| flagd rollout | 2–4 s | 20–45 s |
| **injection → flagd ready** | **4–5 s** | 20–45 s |
| **`paymentUnreachable` → first errored trace** | **39 s** | ~90 s |
| `paymentUnreachable` → error series at `[5m]` | ~2–5 min | 3–5 min ✓ |
| **`emailMemoryLeak` → first OOMKill** | **119 s** | 3–9 min |
| `emailMemoryLeak` steady cycle | 124–373 s, mean 264 s | 3–9 min ✓ |
| recovery to a clean 0 | ~4 min | — |

The **first-Alert and last-Alert halves are not measured** and are
[Alert rules for a Cascade](28-alert-rules-for-a-cascade.md)'s to take, since
they are a property of a Fault *and a rule*. That work is now
[Measure the Cascade against real rules](29-measure-the-cascade-against-real-rules.md).

### Query latency, with an artifact this time

Grafana health 148 ms, Prometheus `query_range` 171 ms, Loki label values 172 ms,
**Loki `query_range` 251 ms**, **Tempo search 324 ms**, Tempo tags 718 ms
(medians of 5). Ticket 26 flagged its own Loki and Tempo figures as unreproduced;
both were **too low**.

### What this run did not measure

- First Alert and last Alert — no rules existed, by design.
- `cartFailure` below `100%`; only the worst case ran, which bounds the ratio in
  the direction that matters.
- `paymentUnreachable` past 12 minutes, so the checkout OOM hazard is untested
  beyond that.
- Whether LGTM's memory climb is a leak or cache warm-up. Still open.
