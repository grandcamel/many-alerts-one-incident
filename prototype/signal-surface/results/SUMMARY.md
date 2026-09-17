# Ticket 27 — measured results

One `s-8vcpu-16gb` DOKS node, nyc3, 1.36.3-do.5, chart 0.41.2, LGTM 0.11.4,
collector at `mode: deployment`. Cluster created 2026-09-17 17:05 UTC.

Every number below has a file in `capture/`. Where a claim has no file, it says so.

---

## Items 1 to 6 — the venue-wide sweep

Run with every fault flag `off`, ~20 minutes of load generator at `loadGeneratorVUs=5`.
Raw log: `capture/items-1-6.log`. Structured: `capture/ITEMS-1-6.json`.

### Item 1 — application logs DO reach this venue's Loki. Confirmed.

17 `service_name` values, 14 of them ticket 10's services:

    accounting, ad, cart, checkout, currency, email, fraud-detection,
    frontend-proxy, kafka, load-generator, otelcol-contrib, payment,
    product-catalog, quote, recommendation, shipping, unknown_service

Real lines retrieved from `{service_name="checkout"}`, e.g. `order confirmation
email sent`, `sending to postProcessor`. **The whole logs column of ticket 10's
signal table is real**, not source-derived.

**Absent, and this matters**: `flagd`, `frontend`, `image-provider`. flagd's
stdout reaching Loki is the one thing ticket 08 said was missing and it is still
missing — `{service_name="flagd"}`, `{k8s_deployment_name="flagd"}` and
`{k8s_container_name="flagd"}` all return **0 streams**.

The 8 stream labels the map lists are confirmed exactly:
`k8s_container_name`, `k8s_deployment_name`, `k8s_namespace_name`,
`k8s_pod_name`, `k8s_replicaset_name`, `service_instance_id`, `service_name`,
`service_namespace`. Everything else a query result shows — `detected_level`,
`scope_name`, `trace_id`, `severity_text`, `service_version` — is **structured
metadata**, merged into the stream object on read but not selectable.

### Item 2 — the `service_namespace` trap is real, and sharper than written.

Values present: `opentelemetry-demo`, `otel-demo`, `kube-system`.

- `{service_namespace="otel-demo"}` → **only `otelcol-contrib`**, the collector's
  own logs. Confirms the trap: it is not an application value.
- `{service_namespace="opentelemetry-demo"}` → applications.
- **But three services carry no `service_namespace` stream label at all**:
  **`cart`, `quote`, `accounting`**. For them, *both* values return zero:
  `{service_name="cart", service_namespace="opentelemetry-demo"}` → **0 streams**,
  and so does the `otel-demo` form. Verified per service; `ad`, `checkout`,
  `email`, `payment` all carry `opentelemetry-demo`.

  Ticket 10's rule "use a bare `{service_name="…"}`" is right, and cart — the
  service carrying **Fault 3** — is exactly the case where the *correct* value
  still returns nothing.

- **Correction to ticket 26**: Kubernetes Events *do* have an isolating stream
  selector. `{service_name="unknown_service", service_namespace="otel-demo"}`
  returns **45 streams** of demo-namespace Events, cleanly separated from the 17
  `kube-system` ones. `service_namespace` on an Event stream is the namespace of
  the *object the Event is about*. Ticket 26's "no isolating stream selector"
  was measured before the namespace split was visible.

### Item 3 — all five claimed metric names CONFIRMED, plus a new trap.

585 metric names (Compose had 240; ticket 26 counted 578 here). Full list:
`capture/03-prom-metric-names.txt`.

| claimed by ticket 10 | verdict |
|---|---|
| `traces_span_metrics_calls_total` | **CONFIRMED** |
| `traces_span_metrics_duration_milliseconds_bucket` | **CONFIRMED** |
| `container_memory_working_set_bytes` | **CONFIRMED** |
| `k8s_container_restarts` | **CONFIRMED** |
| `rpc_server_call_duration_seconds_*` | **CONFIRMED** |

**New trap — there are TWO span-metrics families.** The collector's
`span_metrics` connector emits `traces_span_metrics_*`; the LGTM image's own
Tempo metrics-generator emits `traces_spanmetrics_*` (no underscore). They are
not interchangeable: `traces_spanmetrics_calls_total` carries **no
`service_name` label** and **never emits `STATUS_CODE_ERROR`** — only
`STATUS_CODE_OK` and `STATUS_CODE_UNSET`. A rule written on the wrong one
silently returns nothing usable. `capture/08-duplicate-spanmetrics.json`.

Ticket 10's cross-language trap is corroborated: **both**
`rpc_server_call_duration_seconds_*` (Go) and `rpc_server_duration_milliseconds_*`
(Java, old semconv) exist side by side.

`kube_*` is **zero** metrics — the `k8s_*` family (`k8s_container_restarts`,
`k8s_container_memory_limit_bytes`, `k8s_container_ready`) is what exists.

### Item 4 — Tempo answers, and TraceQL is richer than assumed.

`/api/v2/search/tags` → HTTP 200. Four scopes: **intrinsic 20 tags, resource 44,
span 155, event 16**.

- `{resource.service.name="checkout"}` → 14 traces.
- **`event:name` IS supported** — it is an intrinsic, and `{event:name!=""}`
  returns traces. Event-scoped attributes are queryable as `event.<key>`.
- The value filter genuinely discriminates: `{event.feature_flag.key="thisFlagDoesNotExist"}`
  → **0 traces**, while real keys return traces. This was checked precisely
  because a filter that matches everything would look identical to one that works.

### Item 5 — the flags-off baseline. `capture/05-baseline-authoritative.json`.

**Steady state is genuinely clean: every service reads 0.0000/s error rate**,
on both the all-spans and SERVER-only series. The error series does not exist at
steady state, which makes ticket 10's "empty vector ≠ 0" trap the governing
decision for every rule — see the trap below, which is worse than ticket 10 knew.

Call rates, `sum by (service_name) (rate(traces_span_metrics_calls_total[5m]))`:

| service | all/s | SERVER/s | | service | all/s | SERVER/s |
|---|---|---|---|---|---|---|
| frontend | 13.32 | 7.30 | | ad | 0.479 | 0.263 |
| frontend-proxy | 12.65 | 6.54 | | currency | 0.408 | 0.446 |
| flagd | 9.98 | 6.49 | | quote | 0.325 | 0.108 |
| product-catalog | 5.30 | 2.76 | | shipping | 0.279 | 0.175 |
| frontend-web | 4.56 | 0.00 | | email | 0.250 | 0.067 |
| cart | 2.66 | 1.00 | | accounting | 0.175 | 0.00 |
| load-generator | 2.10 | 0.00 | | fraud-detection | 0.125 | 0.00 |
| image-provider | 1.35 | 1.30 | | **payment** | **0.117** | **0.067** |
| recommendation | 1.06 | 0.37 | | | | |
| **checkout** | **0.850** | **0.067** | | | | |

Memory, the numbers item 7 and item 10 turn on:

- **email: 51.7 Mi working set against a 100 Mi limit.** Never measured before.
  The leak has **48.3 Mi** of headroom to cross, not 100. Ticket 10's
  re-thresholded `> 70Mi` sits 18.3 Mi above baseline — viable.
- **checkout: 17.8 Mi against a 20 Mi limit.** Ticket 10's "18 Mi of 20"
  confirmed at this venue. **2.2 Mi of headroom.**

cart's HTTP routes at baseline: `GetCart` 0.692/s, `AddItem` 0.242/s,
**`EmptyCart` 0.067/s**. cart p95 HTTP duration **7.3 ms**.

### Item 6 — span metrics DO carry `span_kind`, and the distortion is worse than written.

Five values: `SPAN_KIND_CLIENT`, `CONSUMER`, `INTERNAL`, `PRODUCER`, `SERVER`.

checkout span totals by kind: **CLIENT 131, SERVER 13, PRODUCER 13, INTERNAL 13.**
That is a **10×** denominator inflation, not the ~6× implied by ticket 10's "reads
~3% instead of 18%". Every ratio rule needs `span_kind="SPAN_KIND_SERVER"`.

Dimensions on `traces_span_metrics_calls_total`: `service_name` 18,
`span_name` 116, `status_code` 3, `span_kind` 5, **`collector_instance_id` 1**
(the cardinality bomb on collector restart — confirmed present),
`service_namespace` 1, **`http_route` 0 values**.

`http_route` is **not** a span-metrics dimension, but it **is** a label on
`http_server_request_duration_seconds_count` — which settles half of item 12
before the Fault is even injected.

---

## The absence-rule trap — new, and it governs ticket 28

`capture/10-absence-rule-trap.json`.

This harness's own symptom watch reported "payment traffic to zero" **7 seconds
after injection**, before the Fault could possibly have acted. Chasing that false
positive produced the finding:

**The collector pushes these metrics every 60 s.** A `rate()` needs two samples
inside its window, so:

| window | bare | with `or vector(0)` |
|---|---|---|
| `[30s]` | **EMPTY** | **0.0** |
| `[1m]` | **EMPTY** | **0.0** |
| `[2m]` | 0.0333 | 0.0333 |
| `[5m]` | 0.1333 | 0.1333 |

Ticket 10 prescribes `or vector(0)` as the fix for the NoData trap. For an
**error-ratio** rule that is right. For an **absence** rule it is actively
dangerous: it converts "no samples in the window" into a confident zero that is
**indistinguishable from the Fault**, so the rule fires permanently at steady
state. `[2m]` is the minimum window that produces a value at all; ticket 10 wrote
`[5m]` and `[5m]` is correct.

---

## Query latency, with an artifact this time

`capture/09-query-latency.json`. Ticket 26's correction flagged its own Loki and
Tempo latencies as unreproduced — `check-grafana.sh` issues no Loki request at
all. Measured here through the Grafana proxy, 5 attempts each, median:

| path | median | max | ticket 26 claimed |
|---|---|---|---|
| grafana `/api/health` | 148 ms | 173 ms | 146 ms ✓ |
| prometheus `query_range` | 171 ms | 190 ms | 145–191 ms ✓ |
| prometheus instant | 176 ms | 207 ms | — |
| loki label values | 172 ms | 191 ms | — |
| **loki `query_range`** | **251 ms** | 308 ms | 148–180 ms ✗ **too low** |
| **tempo search** | **324 ms** | 362 ms | 190 ms ✗ **too low** |
| tempo tags | 718 ms | 809 ms | — |

All still far inside a Run's patience.

---

## A Fault's cause IS citable here — correcting a map-level standing fact

`capture/07-cause-citability.json`.

The map records, from ticket 08 at the **Compose** venue: "a Fault's cause is
invisible in the telemetry — 240 metric names in Prometheus, none `feature_flag*`,
and flagd's stdout never reaches Loki — so the Change watcher is load-bearing for
the Citation rule, not optional."

At **this** venue, one third of that holds and two thirds do not.

- **Traces: the cause is fully citable.** Services emit a
  **`feature_flag.evaluation` span event** carrying `feature_flag.key`,
  **`feature_flag.result.variant`**, `feature_flag.result.value`,
  `feature_flag.result.reason` and `feature_flag.provider.name`. Observed on
  **checkout** (`paymentUnreachable`, `kafkaQueueProblems`), **cart**
  (`cartFailure`) and **product-catalog** (`productCatalogFailure`).
  `{event.feature_flag.key="paymentUnreachable"}` returns traces;
  `{event.feature_flag.key="thisFlagDoesNotExist"}` returns none.
- **Metrics: not citable.** Four `feature_flag_evaluation_*` metrics **do** exist
  here (the map says none) — but they carry **no `key` label** and come from
  **`service_name="cart"` only**, so they identify no flag.
- **Logs: not citable.** flagd's stdout still never reaches Loki. Unchanged.

**`emailMemoryLeak` has no `feature_flag.evaluation` event in Tempo** — 0 traces.
So the three chosen Faults are **asymmetric**: Faults 1 and 3 have a citable
trigger in traces, Fault 2 does not.

This does not collide with ADR 0008 — a Report is scored on the **Mechanism**, and
naming the Trigger is not a diagnosis — but it raises the stakes on that scoring
rule, because a Run can now name the Trigger cheaply and must not be credited for it.

---

## Timing, the half that needs no Alert rules

`capture/timing-*.json`.

- **`paymentUnreachable`: injection → flagd ready = 5 s** (ConfigMap write 1 s +
  flagd rollout 4 s), against ticket 10's budgeted **20–45 s**.
- **injection → first errored checkout trace searchable in Tempo = 39 s**,
  against ticket 10's budgeted **~90 s**.

The first-Alert and last-Alert halves need thresholds and are
[Alert rules for a Cascade](../../.scratch/many-alerts-one-incident/issues/28-alert-rules-for-a-cascade.md)'s
to measure once it has them.

---

## Fault 1 — `paymentUnreachable` (LIVE). Measured 2026-09-17 17:20–17:37 UTC.

`capture/window-paymentUnreachable-on.log`, `capture/faultprobe-paymentUnreachable-*.json`,
`capture/symptom-paymentUnreachable.json`, `capture/12-blast-radius.json`.

### The Mechanism is confirmed verbatim, and a Run can reach it from one string

The `exception` span event carries:

> `13 INTERNAL: failed to charge card: could not charge the card: rpc error:`
> `code = Unavailable desc = name resolver error: produced zero addresses`

**"produced zero addresses" is DNS name resolution returning nothing** — exactly
ticket 10's Ground truth Mechanism, in the telemetry, without naming the Trigger.

**Correction to the diagnostic path**: ticket 10 places the `exception` event "on
the PlaceOrder span". It is not there — it is on the **frontend's**
`executing api route (pages) /api/checkout` span, in the same trace. The TraceQL
search `{resource.service.name="checkout" && span.rpc.method="oteldemo.PaymentService/Charge" && status=error}`
does return 20 traces, so the *search* is right; the *evidence* is one hop up.

### The error-ratio condition

| query | measured | ticket 10 said |
|---|---|---|
| checkout ratio, all span kinds | **0.2079** | 20–28% ✓ |
| checkout ratio, `SPAN_KIND_SERVER` only | **1.0000** | "~18%" ✗ |

Every checkout SERVER span errors. A 5% threshold clears by **20×**, not 4–5×.
Absolute error rate: checkout **0.175/s** at `[5m]` (and **EMPTY** at `[1m]` —
see the absence trap).

### The absence condition — 4 services, not 6

| service | baseline | under Fault | verdict |
|---|---|---|---|
| email | 0.250/s | **0.0000/s** | GONE |
| accounting | 0.175/s | **0.0000/s** | GONE |
| fraud-detection | 0.125/s | **0.0042/s** | GONE |
| payment | 0.117/s | **0.0042/s** | GONE |
| **shipping** | 0.279/s | **0.267/s** | **UNCHANGED** |
| **cart** | 2.658/s | **2.800/s** | **UNCHANGED** |

**Two corrections to the Ground truth.** It says shipping dispatch and cart
clearing are "never reached". At the *service* level both are untouched:

- shipping still serves `POST /get-quote` at 0.133/s because the quote is fetched
  **before** the charge. Only **`POST /ship-order` goes to 0.0000/s**.
- cart's GetCart/AddItem traffic dominates, so cart clearing failing is invisible
  in the service total.

So a service-level absence rule on shipping or cart **never fires**. They need a
`span_name` rule or they drop out of the Cascade.

**"Payment traffic goes to *exactly* zero" is also wrong** — it is **0.0042/s**,
about one call every four minutes. A `< 0.01` threshold still works; the word
"exactly" does not.

### Cascade breadth — the target is reachable and now measured

- error-ratio condition instantiates over **3** services with meaningful rates:
  frontend 0.350/s, frontend-proxy 0.183/s, checkout 0.175/s
- absence condition instantiates over **4**: email, accounting, fraud-detection, payment

**7 Alerts from 2 conditions**, inside ticket 10's six-to-nine target, with no
rule-count inflation.

### Logs — ticket 10's "proven zero" holds

`{service_name="checkout"}` returned 3 lines in the window, all `[PlaceOrder]`,
and **0** lines matching charge/payment/unavailable/rpc error. `{service_name="payment"}`
returned **0 lines at all**. The failure path logs nothing, as the source read said.

### Item 10 — the stage hazard did NOT materialise

checkout over the full 12-minute window: **17 → 18 Mi peak against its 20 Mi
limit, restarts=0, ready throughout.** The leaked `grpc.ClientConn` per failed
order did not move the container's working set measurably in 12 minutes. payment
drifted 80 → 83 Mi. **Ticket 10's "keep the window under ~15 minutes" is not
disproved — only 12 minutes were tested — but the hazard is far less acute than
the 18-of-20-Mi framing implies.**

### Timing (needs no Alert rules)

| step | measured | ticket 10 budgeted |
|---|---|---|
| ConfigMap write | 1 s | — |
| flagd rollout | 4 s | 20–45 s |
| **injection → flagd ready** | **5 s** | 20–45 s |
| **injection → first errored trace in Tempo** | **39 s** | ~90 s |
| injection → error series present at `[5m]` | ~2–5 min | 3–5 min ✓ |

---

## Fault 2 — `emailMemoryLeak` at `1000x` (REHEARSAL). Measured 17:41–18:04 UTC.

`capture/13-oomkill-evidence.json`, `capture/14-email-signal-classes.log`,
`capture/podwatch-emailMemoryLeak-window.jsonl`, `capture/symptom-emailMemoryLeak.json`.

### Item 8 — THE FLOAT GATE DOES NOT FIRE. The Fault survives.

The flag JSON holds integers (`{"1000x": 1000, "100x": 100, …}`), flagd serves
them, and **the Ruby service leaks as designed**. No `TypeError`, no 500s: email
logged **zero** lines matching `error|exception|memory` across the window.

**The Kubernetes signal class is NOT refuted a fourth time.** `emailMemoryLeak`
stays the Fault that carries it.

### Item 7 — the leak rate, and the baseline nobody had measured

**Baseline RSS 51.7 Mi against a 100 Mi limit** — so the climb crosses 48.3 Mi,
not 100.

Cycle, from `podwatch`:

    t+0    52 Mi
    t+41   59 Mi
    t+62   75 Mi
    t+103  OOMKilled, restart #1      (finishedAt 17:42:35Z)
    t+124  47 Mi   (fresh process)
    t+165  75 Mi
    t+186  84 Mi

**Five OOMKills in a 1181-second window**, peak working set 98 Mi against the
100 Mi limit:

| kill | t+ | finishedAt | period since previous |
|---|---|---|---|
| #1 | 103 s | 17:42:35Z | — |
| #2 | 227 s | 17:44:29Z | 124 s |
| #3 | 476 s | 17:48:18Z | 249 s |
| #4 | 849 s | 17:54:10Z | 373 s |
| #5 | 1160 s | 17:58:53Z | 311 s |

**Cycle period 124–373 s, mean 264 s (~4.4 min) — inside ticket 10's budgeted
3–9 minutes. The budget is CONFIRMED.** A thirty-minute slot sees roughly **7
cycles**.

The *first* cycle is the outlier at 103 s; reading the rate off it alone would
have said "~100 s, 2–5× faster than budget", which the next four kills refute.
Cycles also lengthen as the window goes on (124 → 373 s), so the period is a
range, not a constant.

**Threshold consequence**: 70 Mi is crossed at roughly **t+40 s** of each cycle,
leaving **~60 s** before the kill. Ticket 10 moved off `90%`/`for:1m` because
90→100 MiB takes 56 s. `>70Mi` with `for: 1m` is *also* marginal here — it fires
approximately when the container dies.

### Item 9 — the restart evidence, answered in full

| evidence | available? | detail |
|---|---|---|
| `lastState.terminated.reason` via `kubectl` | **YES** | `OOMKilled`, `exitCode: 137`, with `startedAt`/`finishedAt` |
| an `OOMKilled` **Kubernetes Event** | **NO** | 8 Events name the pod, all `Normal`, none mention OOM |
| restart-lifecycle Events in Loki | **YES** | `Created`/`Started` arrive with `count=2` |
| `k8s_container_restarts` metric | **YES** | reads `1.0`; `changes(…[10m])` reads `1.0` |
| the caller's WARN | **YES** | see below |

**Ticket 10's central correction is confirmed at this venue**: OOMKill emits no
Kubernetes Event, and pod status via read-only `kubectl` is the strongest citable
evidence. Both Loki selectors work —
`{service_name="unknown_service", service_namespace="otel-demo"} |= "email-"`
and the bare form.

The caller's WARN, retrieved:

> `failed to send order confirmation: failed POST to email service:`
> `Post "http://email:8080/send_order_confirmation": EOF`

**The `EOF` is the kill landing mid-request** — the Ground truth's claim, in one
log line a Run can cite.

**New**: the pod reports **`ready: True` with `restartCount: 1`**. There is no
readiness or liveness probe on the container, so a readiness-based rule never fires.

### The signal table, verified — and Fault 2 raises almost no Cascade

| class | ticket 10 | measured |
|---|---|---|
| Kubernetes | ⚠️ pod status, not Events | **confirmed exactly** |
| logs | ⚠️ caller-only | **confirmed** — email logs only `Order confirmation email sent`, 0 error lines |
| traces | ⚠️ thin | **weaker than that** — `{resource.service.name="email" && status=error}` → **0 traces** |
| metrics | ⚠️ | **email error span-metric is an EMPTY SERIES** |

Blast radius under this Fault: checkout 0.0078/s, everything else ≤0.0042/s —
noise level. checkout's SERVER error ratio is **0.0000**, because the order
completes anyway.

**This confirms the Ground truth** ("no customer ever sees an error and no order
is lost") **and means Fault 2 cannot produce a six-to-nine Alert Cascade.** It has
two alertable conditions — container memory and restart count — instantiating on
**one** service, plus the caller's WARN. Roughly **2–3 Alerts**. That is fine for
a rehearsal Fault, but ticket 28 should not size its rules expecting breadth here.

### Timing

| step | measured | ticket 10 budgeted |
|---|---|---|
| injection → flagd ready | **4 s** | — |
| injection → email RSS above baseline+20 Mi | **54 s** | — |
| **injection → first OOMKill** | **119 s** | 3–9 min (this is the *first* cycle) |
| steady-state OOM cycle period | **124–373 s, mean 264 s** | 3–9 min ✓ |
| injection → caller's WARN in Loki | **119 s** | — |

---

## Fault 3 — `cartFailure` at `100%` (REHEARSAL). Measured 18:02–18:17 UTC.

`capture/faultprobe-cartFailure-*.json`, `capture/15-cart-log-templates.log`,
`capture/window-cartFailure-100%.log`. Run at **`100%`** — the worst case, so the
connect-duration question gets its maximum signal and the ratio its upper bound.

### Item 11 — THE DECISIVE NUMBER. The Fault is silent, not destabilising.

Ticket 10: "The upper bound is exactly **150.5 s** (`ConnectTimeout 5000 ×
ConnectRetry 30`) with a lock around a *synchronous* `Connect()`, so concurrent
failures serialise. This single number decides whether this is a silent
two-service Fault or a demo-destabilising stall."

Measured, with every empty-cart call on the bad path:

| | measured | theoretical ceiling |
|---|---|---|
| cart p95 HTTP server duration | **0.0625 s** | 150.5 s |
| cart p99 HTTP server duration | **5.58 s** | 150.5 s |
| cart p95 span duration | 7.39 ms | — |
| checkout p95 span duration | 305 ms | — |

**The 150.5 s ceiling does not materialise — the bad path costs ~5.6 s at p99,
about 27× under the bound.** Almost certainly the same mechanism Fault 1 showed:
the hostname does not resolve, so the connection fails at DNS rather than
exhausting 30 × 5 s of connect timeouts.

**Fault 3 is a silent Fault. The demo-destabilising risk is refuted, and cart and
checkout both stay healthy** (cart `restarts=0`, `ready=True`, 0 Kubernetes Events).

### Item 12 — the metric shape, and ticket 10's ratio warning confirmed exactly

- **`http_route` IS a label** on `http_server_request_duration_seconds_count` for
  cart — 3 routes: `EmptyCart` 0.046/s, `GetCart` 0.667/s, `AddItem` 0.213/s.
  (It is **not** a span-metrics dimension — see item 6.)
- **cart SERVER-only error ratio: 0.05337.** Ticket 10 predicted "~5.2%
  straddles a 0.05 threshold". Measured **5.34% at the `100%` variant** — above
  0.05 by **0.34 percentage points**, at the Fault's maximum strength.
  **Any lower variant sits decisively below 0.05.** The ratio rule is unusable;
  ticket 10's call to use an absolute rate instead is confirmed.
- all-span-kind ratio: 0.0207 — the same denominator inflation as everywhere.
- **cart absolute error rate: 0.0496/s against a measured baseline of 0.0000/s.**
  A clean, unambiguous rule.

### Logs — the alertable condition works, the diagnostic path does not

`{service_name="cart"} |= "Wasn't able to connect to redis"` → **6 lines.
Confirmed.** `{service_name="cart", service_namespace="otel-demo"}` → **0 lines**,
confirming the trap. `EmptyCartAsync called with` → 4 lines, so the ratio
denominator exists in Loki as ticket 10 said.

**New trap, and it is sharp: the .NET log body is the message TEMPLATE, and the
values live in structured metadata.** The body arrives literally as:

    Error status code '{StatusCode}' with detail '{Detail}' raised.
    EmptyCartAsync called with userId={userId}

The rendered values are structured metadata fields (`StatusCode`, `Detail`,
`userId`). Consequences, measured:

| query | lines |
|---|---|
| `{service_name="cart"} \|= "EnsureRedisConnected"` | **0** |
| `{service_name="cart"} \|= "ApplicationException"` | **0** |
| `{service_name="cart"} \| Detail =~ ".*EnsureRedisConnected.*"` | **5** |
| `{service_name="cart"} \| StatusCode = "FailedPrecondition"` | **5** |
| `{service_name="cart"} \|= "badhost"` | **0** |

**Ticket 10's diagnostic path expects the `ValkeyCartStore.EnsureRedisConnected`
frame and the `System.ApplicationException` text. Neither is reachable by a LogQL
line filter** — both live in the `Detail` structured-metadata field and need
`| Detail =~ "…"`. The full frame *is* there, with file and line numbers:

> `Can't access cart storage. System.ApplicationException: Wasn't able to connect to redis`
> `   at cart.cartstore.ValkeyCartStore.EnsureRedisConnected() in /usr/src/app/src/cartstore/ValkeyCartStore.cs:line 98`
> `   at cart.cartstore.ValkeyCartStore.EmptyCartAsync(String userId) in …:line 182`

**`badhost` appears in no log line at all** — the bad hostname, the actual cause,
is not in the logs. It is only in the flag config and the `feature_flag.evaluation`
span event.

Also worth noting for Eyes: these error lines carry `severity_text: "Information"`,
not Error — `detected_level` is `Information` too. **A severity-based log rule
would miss this Fault entirely.**

---

## The recovery edge — a direct answer to ticket 28's resolution question

`capture/16-recovery-edge.log`. Measured after `cartFailure` was undone
(flip off → flagd rollout → `rollout restart deploy/cart`), sampled every minute:

| after undo | cart error rate, bare | with `or vector(0)` | SERVER ratio | redis log lines |
|---|---|---|---|---|
| +1 min | 0.03750 | 0.03750 | 0.03194 | 0 |
| +2 min | 0.02500 | 0.02500 | 0.01945 | 0 |
| +3 min | 0.00833 | 0.00833 | 0.00451 | 0 |
| +4 min | **0.00000** | **0.00000** | **0.00000** | 0 |
| +5 min | 0.00000 | 0.00000 | 0.00000 | 0 |
| +6 min | 0.00000 | 0.00000 | 0.00000 | 0 |

Ticket 28 asks: "does a rule that goes NoData on recovery ever send a Resolved at
all?" **It does not go NoData on recovery.** The bare query and the
`or vector(0)` query return the *same* value at every step, which means the
series still **exists** and reads a genuine **0** — Prometheus keeps the counter
once it has been created, so `rate()` over an unchanging counter is 0, not empty.

The asymmetry that matters:

- **before injection** — the error series has never existed → **NoData**
- **during** — series present, > 0 → **Alerting**
- **after recovery** — series present, = 0 → **Normal**, so **Resolved does fire**

**Recovery takes ~4 minutes**, which is the `[5m]` window draining, not the
system healing — the log condition stopped inside the first minute.

---

## Cost and disposal

Cluster `maoi-signal` created **17:05:36Z**, destroyed **18:26:47Z** — **81 min**,
**1.353 h × $0.142860 = $0.19**. `--ha=false`, `--size s-8vcpu-16gb`, `--count 1`,
as the runbook rule requires.

Post-delete sweep: **no clusters, no load balancers.** One 100 GiB volume is
listed, `8bbfce67-4b5f-11ea-…`, attached to droplet `154910143` — its UUID
timestamp is 2020 and it predates this account's work on this effort. **It is not
ours and was not created by this run.**

---

## What this prototype did NOT measure

- **First Alert and last Alert.** No Grafana Alert rules existed, by design —
  those thresholds are [Alert rules for a Cascade](../../.scratch/many-alerts-one-incident/issues/28-alert-rules-for-a-cascade.md)'s
  to pick from the baselines above. Injection → flagd ready → first symptom is
  measured; the rest is not.
- **`cartFailure` at variants below `100%`.** Only the worst case was run. The
  ratio finding is an upper bound, which is the direction that matters.
- **`paymentUnreachable` beyond 12 minutes.** checkout did not OOM in that window;
  ticket 10's "keep it under ~15 minutes" is neither confirmed nor refuted.
- **Whether LGTM's memory climb is a leak or cache warm-up.** Still open, still
  costs cluster time.
