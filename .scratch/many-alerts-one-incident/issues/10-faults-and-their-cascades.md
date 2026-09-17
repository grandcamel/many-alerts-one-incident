# Faults and their Cascades

Type: grilling
Status: resolved
Blocked by: 09, 26

## Question

Which Faults can the simulation inject, including the one Kubernetes-native Fault the story needs? For each: its Ground truth, the Cascade of Alerts it should raise, the signals that show it (which logs, metrics, traces, Kubernetes Events and Changes), and its timing inside the slot from injection to the last Alert. Which Fault the live demo uses, and which are rehearsal-only. Every Fault added here writes its Ground truth, per the map's standing rule.

Start from the Demo's fifteen fault flags (two need the Kafka layer or Kubernetes). Decide here how each Fault's injection becomes a Change: the research found a flip emits nothing collectable, so a small watcher on flagd's event stream posting a Grafana annotation and an OTLP log record is the candidate, with the flag file as the source of truth. Ticket 05's finding that a Fault presents as a restart loop with a pod-status signal rather than a reliable Kubernetes Event was about **OOMKill**, not about `failedReadinessProbe`; ticket 01 found that flag wants the chart's `kubernetesEvents` preset, which points the other way. What it actually produces is [ticket 26](26-can-one-doks-node-hold-the-chart.md)'s to measure, and this ticket's Cascade waits on that answer rather than assuming a restart count.

## What ticket 09 settled, 2026-09-16

The venue is one DigitalOcean node running the Helm chart, not the Compose core
layer (ADR 0007). That changes this ticket's starting menu:

- **All 13 fault flags are usable**, not 11. `kafka` stays enabled, so
  `kafkaQueueProblems` is in; the cluster is real, so `failedReadinessProbe` is
  the Kubernetes-native Fault the story wanted rather than a synthesized one.
- **The load generator stays on**, so a Fault produces symptoms the moment it is
  flipped and `traffic.sh` is retired. Timing "from injection to the last Alert"
  is measurable rather than dependent on a stopgap driving traffic.
- **The flip is a ConfigMap write**, not a file edit. How that becomes a Change
  is [ticket 25](25-the-change-making-a-faults-cause-citable.md)'s to decide, but
  the presenter's action for each Fault is shaped by it.
- This ticket now also waits on
  [Can one DOKS node hold the chart](26-can-one-doks-node-hold-the-chart.md), so
  the menu is not written against a deployment that has not stood up.

## Correction from ticket 26, 2026-09-16

Measured on the real venue. Three things this ticket carries as settled are
wrong, and two of them would have shaped the Fault menu around signals that do
not exist.

**`failedReadinessProbe` is not the Kubernetes-native Fault.** A real cluster was
never sufficient: chart 0.41.2 templates **no readinessProbe on cart**, the
service the flag names. `readinessProbe` appears twice in the entire render,
both on the collector — 2 containers of 26. With the flag genuinely on, cart held
`ready=true` and `restartCount=0`, its EndpointSlice never changed, and no
`Unhealthy` Event fired. So the adjudication this ticket was waiting for has **no
winner**: ticket 05's restart loop and ticket 01's Event are both wrong. Pick a
different Kubernetes-native Fault, or accept that the Kubernetes signal class
comes from elsewhere. **13 flags enabled, 12 usable.**

**"Start from the Demo's fifteen fault flags" counts two knobs as faults.**
Chart 0.41.2 ships 15 flags, but `loadGeneratorTraffic` and `loadGeneratorVUs`
are load knobs. The menu starts from **13**, and one of those is inert, so **12**.

**A Fault can be invisible in logs.** `adFailure`, genuinely firing, produced
clean `Targeted ad request received` lines and nothing else in the ad service's
log. It was visible only in metrics and span metrics — gRPC status 14 at
0.0167/s, and `STATUS_CODE_ERROR` on **five services at once**: ad,
frontend-proxy, flagd, fraud-detection, payment. **An Alert rule written on log
volume would never fire for this Fault.** Per-Fault, this ticket has to name
which signal class actually carries it rather than assuming logs do.

That five-service spread is also the many-to-one shape **already present** with
no Grafana grouping change, which is an input to ticket 14.

**Flipping a flag requires a pod restart.** flagd reads an `emptyDir` populated
once by an init container, not the ConfigMap. The presenter's one action is the
ConfigMap edit **plus `kubectl rollout restart deploy/flagd`**, which adds a
rollout delay between the action and the first symptom — size the Cascade window
accordingly.

**Kubernetes Events are available but awkward.** They reach Loki only at
`mode: deployment`, watch-only with **no backfill**, and with **no isolating
stream selector**: `{event_domain="k8s"}` and `{k8s_resource_name="events"}`
both return zero streams, because those are structured metadata. The only
selector that finds them is `{service_name="unknown_service"}`.

## Answer

Resolved 2026-09-17 by a grilling session, against eight candidate flags mapped and
then adversarially refuted. **The refutation changed the outcome three times**: it
rehabilitated a Fault this ticket had written off, it killed the premise on which the
Kubernetes-native Fault had been chosen, and it revealed that the whole logs-and-traces
column rests on something nobody has ever measured at this venue.

### The rules, before the menu

1. **A Fault is exactly one flag.** Compound Faults — two flags at once, decoys — are
   out of scope. They would reopen ADR 0006's counting rule and the Ground truth rule
   together, and `adFailure` alone already spreads across five services, so width is
   not a reason to reach for them.
2. **A Ground truth is two layers** — the **Mechanism**, what breaks in system terms,
   and the **Trigger**, the flag and variant — and a Report is scored against the
   Mechanism alone. The Ground truth lives only in this repository and never enters
   the Run's world. **ADR 0008** records this; the Memory directory is the live leak
   risk, not Jira or Confluence.
3. **This ticket names alertable conditions, not Alert rules.** It owns what is true
   of the system when a Fault fires; thresholds, `for` durations, labels and grouping
   belong to [Alert rules for a Cascade](28-alert-rules-for-a-cascade.md).
4. **The traffic level is venue, not Fault.** `make up` pins `loadGeneratorVUs` once
   and every timing budget is written against that level. A Fault is a flag flip and
   nothing else.
5. **Timing is budgeted here and measured later.** "Injection to last Alert" is not a
   property of a Fault — it is a property of a Fault *and* a rule, and the rules do
   not exist yet.
6. **Each Fault defines its own undo, and "one presenter action" means one command,
   not one API call.** `make fault NAME=x` and `make clear`. All three chosen Faults
   need a service restart in their undo, so a script was always required.

### The menu

Chart 0.41.2 ships **15 flags**. Two are load knobs (`loadGeneratorTraffic`,
`loadGeneratorVUs`), leaving **13 Faults**. `failedReadinessProbe` is inert — no probe
is templated on cart — so **12 are usable**. `productCatalogFailure` is usable only via
a targeting edit: its rule returns `"off"` on **both** branches, so `defaultVariant` is
never consulted and a plain flip does nothing. It is the only flag in the set carrying
a `targeting` key.

**Three are written in full. The rest are named only and carry no Ground truth:**
`adHighCpu`, `adManualGc`, `imageSlowLoad`, `intlShippingSlowdown`, `kafkaQueueProblems`,
`paymentFailure`, `productCatalogFailure`, `recommendationCacheFailure`, and
`failedReadinessProbe` (inert, recorded so nobody nominates it a fourth time).

`adFailure` is the **designated fallback for the live slot** — not one of the nine.
It is the only Fault ever actually injected at this venue, and if rehearsal kills the
live Fault we should not be choosing a replacement under time pressure.

---

### Fault 1 — Checkout-to-payment connection (LIVE)

**Trigger**: `paymentUnreachable` → `on`.

**Ground truth (Mechanism)**: Every checkout attempt abandons the healthy connection it
holds to the payment service and instead dials a hostname that does not exist in cluster
DNS, so the charge call fails name resolution and returns gRPC UNAVAILABLE; checkout
converts that into gRPC INTERNAL for its caller, so every order fails at the payment step
while the payment service itself stays perfectly healthy and simply stops receiving any
traffic at all. Everything sequenced after the charge — shipping dispatch, cart clearing,
the confirmation email, and the order stream that feeds accounting and fraud detection —
is never reached, while the browse and add-to-cart path ahead of the charge keeps working
normally. Each failed attempt also leaves behind an undisposed connection that keeps
retrying the unresolvable name in the background.

**Signals**: metrics ✅, traces ✅, **logs a proven zero** (all 34 `logger.*` calls read;
the failure branch is `status.Errorf` with no logging), Kubernetes ❌.

**Alertable conditions** (2, instantiating to 6–9 Alerts):

- *Checkout error ratio* — `sum(rate(traces_span_metrics_calls_total{service_name="checkout",status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_span_metrics_calls_total{service_name="checkout"}[5m]))`, real ratio 20–28%, clearing a 5% threshold by 4–5×. Instantiates across checkout, frontend-proxy and the edge.
- *Service traffic absent* — `sum(rate(traces_span_metrics_calls_total{service_name="payment"}[5m])) < 0.01`. Payment's traffic goes to **exactly zero**, so this is unambiguous rather than a dip inside Poisson noise. Instantiates across payment, email, accounting, fraud-detection, shipping and cart clearing.

**Diagnostic path**: `{resource.service.name="checkout" && span.rpc.method="oteldemo.PaymentService/Charge" && status=error}`, then the `exception` event on the PlaceOrder span carrying `could not charge the card: rpc error: code = Unavailable`. The orphaned client span with no server-side child is the structural signature of dialling a destination that is not there — a Run reaches the Mechanism without ever naming the Trigger.

**Timing budget**: flagd rollout 20–45 s + mean 18 s to the next checkout + ~5 s trace lag → a failing trace searchable at **~90 s**; first metric-backed Alert at **3–5 min**; absence Alerts landing by **9–12 min**. Fits a thirty-minute slot with room for a visible recovery.

**Undo**: flip off → `rollout restart deploy/flagd` → **`rollout restart deploy/checkout`** (the leaked connections do not clear otherwise).

**⚠️ Stage hazard**: checkout is the tightest container in the demo — **18 Mi against a
20 Mi limit with `GOMEMLIMIT=16MiB`** — and this Fault leaks a `grpc.ClientConn` per
failed order and never closes it, in a file where every startup connection gets
`defer c.Close()`. A long window can OOM checkout on stage and **replace the Fault with a
different one**. Keep the fault window under ~15 minutes.

---

### Fault 2 — Email confirmation service (REHEARSAL, carries the Kubernetes signal class)

**Trigger**: `emailMemoryLeak` → `1000x`.

**Ground truth (Mechanism)**: The email service keeps every order-confirmation message it
"sends" in an in-process test mailbox that is emptied only on a branch the running
configuration no longer takes, and each message body is padded to roughly a thousand times
its natural size, so the container's resident memory climbs until it crosses its
hundred-mebibyte limit and the kernel kills it. The kill lands mid-request, so its one
caller's in-flight confirmation POST is reset at least once per cycle. With no liveness or
readiness probe on that container, exhausting the limit is the only thing that ends the
pod; Kubernetes restarts it with an empty mailbox and the climb repeats. The caller treats
the confirmation as fire-and-forget — it logs the failure and completes the order anyway —
so no customer ever sees an error and no order is lost.

**Signals**: Kubernetes ⚠️ (**pod status, not Events**), metrics ⚠️, logs ⚠️ caller-only,
traces ⚠️ thin.

**The correction that matters**: **`OOMKilled` emits no Kubernetes Event.** It is a
`containerStatuses[].lastState.terminated.reason`, carried by neither Loki nor Prometheus.
The Event evidence is the restart lifecycle (`Created`/`Started`, `BackOff` after repeats),
which has never been observed here. **The strongest citable evidence is pod status via
read-only `kubectl`** — already granted through `kubectl proxy` behind the Forwarder by
[Which system, and where it runs](09-which-system-and-where-it-runs.md). This makes
[Eyes](12-eyes.md) a hard dependency for this Fault rather than a parallel concern.

**Alertable conditions**: container memory approaching limit —
`max by (k8s_pod_name)(container_memory_working_set_bytes{k8s_container_name="email"}) > 70Mi`
(re-thresholded from 90%/`for:1m`, which is **unreachable**: 90→100 MiB takes 56 s);
restart count rising — note `k8s.container.restarts` is a **gauge**, so `changes()` or
`max_over_time − min_over_time`, never `increase()`; and the caller's WARN,
`{service_name="checkout"} |= "failed to send order confirmation"`.

**Timing budget**: at `1000x`, an OOM cycle in roughly **3–9 min**, repeating. At `100x`
it is 28–83 min and does not fit. There is no variant landing cleanly mid-slot, so
`1000x` is the choice and the repeat is the demo.

**Undo**: flip off → `rollout restart deploy/flagd` → **delete the email pod**. Beware a
restart backoff of up to 300 s, during which a flip-off does nothing at all, because the
process must be running to execute the clear.

---

### Fault 3 — Cart clearing (REHEARSAL, carries the logs signal class)

**Trigger**: `cartFailure` → a percentage variant.

**Ground truth (Mechanism)**: Every request to empty a shopper's cart is routed to a
second, misconfigured cart-store client pointed at a hostname that does not resolve, so
those calls fail with gRPC FAILED_PRECONDITION after a failed connection attempt, and each
failure leaves behind another connection object that keeps retrying that hostname forever.
Checkout calls empty-cart at the very end of every order and discards the error, so the
order still completes — payment, shipping and the confirmation email all succeed and the
shopper sees nothing wrong — and the only symptoms are errored cart and checkout spans plus
cart error logs, while every shopper's cart is silently never cleared.

**Signals**: logs ✅, traces ✅, metrics ⚠️, Kubernetes ❌.

**Why this one over `adFailure`**: it is the only candidate giving an Error-level log line
**on the fault path** whose OTLP bridge is compiled into `Program.cs` rather than depending
on an env var, plus a ratio discriminator computable entirely inside Loki (Error lines ÷
`EmptyCartAsync called with` lines = the failure percentage). And it is a **different
shape** — a silent data-integrity failure behind green checkouts, which is the failure
alerting is worst at. The three Faults then span resource exhaustion, hard dependency
failure, and silent partial failure, rather than three variations of "errors reach the edge".

**Alertable conditions**: `{service_name="cart"} |= "Wasn't able to connect to redis"`
(**no `service_namespace` matcher** — see the traps); and an absolute error rate against a
measured baseline, **not** a ratio, because the ~5.2% ratio straddles a 0.05 threshold.

**Diagnostic path**: `{resource.service.name="cart" && status=error}` — the cause appears
twice, as an `exception` span event carrying
`Can't access cart storage. System.ApplicationException: Wasn't able to connect to redis`
with the `ValkeyCartStore.EnsureRedisConnected` frame, and as the OpenFeature evaluation event.

**Undo**: flip off → `rollout restart deploy/flagd` → **restart `cart`** (undisposed
multiplexers retry `badhost:1234` forever).

**Unmeasured and decisive**: the bad-path connect duration. The upper bound is exactly
**150.5 s** (`ConnectTimeout 5000 × ConnectRetry 30`), and `EnsureRedisConnected` holds a
lock around a *synchronous* `Connect()`, so concurrent failures serialise. This single
number decides whether this is a silent two-service Fault or a demo-destabilising stall.

---

### Cascade breadth: the target is reachable honestly

The map wants five to ten Alerts from one Fault. Post-refutation the live Fault yields
**two independent facts**, and inflating that to ten rules would manufacture the very
alert fatigue the demo argues against. The glossary dissolves it: an **Alert** is one
rule *instance* identified by its Fingerprint, so one rule with `by (service_name)` gives
one Alert per series. **Two to four alertable conditions, instantiated per affected
service, give six to nine Alerts** — breadth coming from the blast radius, which is
exactly the demo's claim.

### What is not measured, and it is more than expected

**No application service's logs have ever been retrieved from this venue's Loki, and
Tempo has never been queried at this venue for anything.** Every ✅ in the logs and traces
columns above is source-derived. The 578 Prometheus metric names were counted, never
enumerated, so `traces_span_metrics_calls_total` is a *probable* name backed only by prose.
Until [Verify the signal surface and settle the Fault gates](27-verify-the-signal-surface-and-settle-the-fault-gates.md)
runs, every query above is **proposed, not verified**, and the spec must say so.

### Traps the spec must carry

- **`service_namespace="otel-demo"` on an application selector returns zero streams
  forever.** All 22 demo pod templates carry
  `resource.opentelemetry.io/service.namespace: opentelemetry-demo`, and the collector's
  `k8s_attributes` runs with `otel_annotations: true`, which overwrites the
  namespace-derived value. `"otel-demo"` is correct **only** for Kubernetes Event streams,
  which come from the collector pod — the one pod with no such annotation. Use a bare
  `{service_name="…"}`.
- **Empty vector ≠ 0.** Every `> 0` rule here is written on an error-only series that does
  not exist at steady state. Grafana puts those in **NoData**, not Normal, so NoData
  handling decides whether the Cascade misses entirely or fires before injection. Wrap in
  `or vector(0)`.
- **Metric families do not transfer across languages.** Java emits
  `rpc_server_duration_milliseconds_*` (old semconv); Go emits
  `rpc_server_call_duration_seconds_*` with a string status; Python recommendation emits no
  rpc server metrics at all; .NET cart never adds the `Grpc.AspNetCore.Server` meter.
  Copying one service's rule onto another returns an empty series forever — **this is the
  exact class of error that already cost this project a decision.**
- **Span-metrics ratios count client and internal spans.** Without
  `span_kind="SPAN_KIND_SERVER"` the checkout ratio reads ~3% instead of 18%.
- `collector_instance_id` has been a default span-metrics dimension since v0.136.0 and its
  UUID changes on every collector restart. Always `sum by (service_name)`.
- **`transform/sanitize_spans` is defined in chart 0.41.2 and wired into no pipeline**, so
  `http.route` is never backfilled and any rule on a normalised frontend span name targets
  a value that does not exist.
- **flagd v0.16.0 is distroless**: `kubectl exec deploy/flagd -- cat` fails. Use
  `-c flagd-ui -- cat /app/data/demo.flagd.json`, or OFREP on `:8016` *after*
  `rollout status` returns.
- **Verifying flagd is not verifying the caller.** Only the Java provider's reconnect after
  a flagd rollout has ever been confirmed. Confirm one real symptom before starting the clock.
- **The flagd rollout contaminates evidence in both directions** — identical Events for
  injection and remediation, and it briefly zeroes *every* flag as providers fall back to
  code defaults. Flip one Fault at a time.
- **Nothing is idempotent across flips**, which is why every undo above restarts a service.

### Corrections this ticket made to the record

- [Can one DOKS node hold the chart](26-can-one-doks-node-hold-the-chart.md): "`adFailure`
  is invisible in logs" **was never measured** — no Loki query for ad logs exists in that
  prototype and no Loki access occurred while the flag was on, while
  [Can the laptop hold it](08-can-the-laptop-hold-it.md) *did* retrieve the WARN line from
  Loki on the same image. Two further numbers there have no artifact: the Loki query
  latency and the `traces_span_metrics_*` names.
- [Eyes](12-eyes.md): had escalated that claim to "produced no error lines at all" and was
  designing against it. The conclusion survives on better examples —
  `paymentUnreachable` and `productCatalogFailure` are genuinely log-silent at source.

## Correction from ticket 27, 2026-09-17

Measured on the real venue. **Every query this ticket wrote has now been run.**
The three Faults survive and most of this ticket's reasoning is confirmed —
including the two claims it flagged as unmeasured and decisive. Seven things move.

**Both gates came back clean.** The **Float gate does not fire** —
`emailMemoryLeak` leaks as designed, so the Kubernetes signal class is not
refuted a fourth time. And **cart's bad-path connect costs 5.58 s at p99, not
150.5 s**, about 27× under the theoretical ceiling, so **Fault 3 is silent, not
demo-destabilising**. Both were this ticket's own open questions and both resolve
in its favour.

**1. Two of Fault 1's six absence services do not go absent.** `shipping` runs
0.279 → **0.267/s**, essentially unchanged, because the quote is fetched *before*
the charge — only `POST /ship-order` goes to zero. `cart` stays at **2.8/s**
because GetCart/AddItem dominate the service total. **A service-level absence
rule on either never fires.** The absence condition instantiates over **4**
services, not 6: email, accounting, fraud-detection, payment. With the 3
error-ratio services that is **7 Alerts**, still inside this ticket's six-to-nine
target.

**2. "Payment traffic goes to *exactly* zero" is wrong.** It is **0.0042/s**,
about one call every four minutes. A `< 0.01` threshold still works.

**3. The `span_kind` correction understates itself.** checkout carries **131
CLIENT spans to 13 SERVER** — a **10×** denominator inflation. The verbatim ratio
measured **0.2079**, matching this ticket's predicted 20–28% almost exactly; the
SERVER-only ratio is **1.0000**, not "~18%". Every checkout SERVER span errors, so
a 5% threshold clears by 20×.

**4. Fault 3's diagnostic path cannot be reached by a LogQL line filter.**
cart's .NET log bodies are message **templates** —
`Error status code '{StatusCode}' with detail '{Detail}' raised.` — with the
values in **structured metadata**. `|= "EnsureRedisConnected"` and
`|= "ApplicationException"` both return **0 lines**;
`| Detail =~ ".*EnsureRedisConnected.*"` returns 5. The full frame with file and
line numbers is there, in `Detail`. Separately, these lines carry
**`severity_text: "Information"`**, so a severity-based rule misses the Fault.

**5. `or vector(0)` is the right fix for a ratio rule and the wrong one for an
absence rule.** The collector pushes every 60 s, so `rate()` over `[30s]` or
`[1m]` returns **no series**, and `or vector(0)` turns that into a confident 0
indistinguishable from the Fault — firing the rule permanently at steady state.
`[2m]` is the floor; this ticket's `[5m]` is correct.

**6. Fault 2 raises almost no Cascade.** email's error span-metric is an **empty
series**, `{resource.service.name="email" && status=error}` returns **0 traces**,
and the blast radius is noise-level — about **2–3 Alerts**, on one service. The
signal is pod status and the caller's WARN, exactly as written. This *confirms*
the Ground truth ("no customer ever sees an error and no order is lost") and
means [Alert rules for a Cascade](28-alert-rules-for-a-cascade.md) should not
size rules expecting breadth here.

**7. Timing: the flagd rollout is 4–5 s, not 20–45 s**, and the first errored
trace is searchable at **39 s**, not ~90 s. The OOM cycle is **124–373 s, mean
264 s** — **inside** the budgeted 3–9 minutes, though the *first* cycle at 119 s
is an outlier that would mislead anyone reading the rate off one kill.

**Confirmed as written**, with files behind them: all five metric names; the
`service_namespace` trap (and sharpened — cart, quote and accounting carry **no**
such label, so even the correct value returns zero); Fault 1's logs being a proven
zero; cart's `Wasn't able to connect to redis` line; the `EmptyCartAsync` ratio
denominator; `k8s_container_restarts` as a gauge; **no OOMKilled Kubernetes
Event**; `http_route` as a cart label; and the ~5.2% ratio straddling 0.05 —
measured **0.05337** at the `100%` variant, so lower variants sit below it.

**One risk downgraded**: over a full 12-minute window the checkout container went
**17 → 18 Mi against its 20 Mi limit with restarts=0**. The stage hazard did not
materialise. Untested beyond 12 minutes.

## Correction from ticket 28, 2026-09-17

Three things this ticket carries are wrong, and one of them would have made the
live Fault's own Cascade collapse to a single Alert.

**The checkout error ratio is refuted, twice over.** Ticket 27 measured the
verbatim ratio at 0.2079 and that number is right, but the *rule* built on it is
not. Run as a by-service query it yields **one** Alert, not three:
`capture/faultprobe-paymentUnreachable-on.json` gives frontend `0.01594` and
frontend-proxy `0.00705`, 3.1× and 7.1× below a 5% threshold. Worse, **the ratio
inverts** — frontend-proxy's fault-time `0.00705` is *lower* than the `0.00808`
measured with every flag off (`capture/05-baseline-span-metrics.json`) — and it
returns `NaN` for accounting, fraud-detection and payment, whose denominators
collapse, which are three of the four services the absence condition already
owns. The `span_kind` fix does not rescue it: SERVER-only saturates checkout at
`1.0000`, freezing every trend comment at "unchanged". **The condition is an
absolute error rate**, not a ratio.

**The email memory condition as written mints five Incidents from one Fault.**
`> 70Mi` instantaneous goes Firing→Resolved→Firing **five times in 1181 s**: the
container falls to 47 Mi after each kill and sits below 70 Mi for 67, 119, 118
and 243 s (`capture/podwatch-emailMemoryLeak-window.jsonl`). Under ADR 0004 each
of those is a new Incident. It needs a `max_over_time([5m])` latch.

**`adFailure`, the designated fallback, has never been measured at this venue.**
Every number about it in the record — 12 errors in 140 requests, the five-service
`STATUS_CODE_ERROR` spread — is from ticket 08 on the **Compose** venue, which
the map itself marks as Compose-only. Nothing proves it raises a Cascade here.
Ticket 28's system-shaped rules mean it *should* light up without a rule set of
its own, but "should" is the word this project has lost three decisions to.

Also: **this ticket's own trap list is half right about cart's log severity.**
`Wasn't able to connect to redis` carries `severity_text: "Error"`; only the
separate `Grpc.AspNetCore.Server.ServerCallHandler` template line carries
`"Information"`. The conclusion holds for a different reason — `severity_text` is
structured metadata and is **not selectable as a stream label at all**.
