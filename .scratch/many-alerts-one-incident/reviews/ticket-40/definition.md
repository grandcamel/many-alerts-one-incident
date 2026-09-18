# Fallback Fault Ground truth — approved

Status: approved by the human on 2026-09-18 with “Approved.” Repository-only adjudication material; never seed it into Run-readable Memory, OPS, Confluence or telemetry.

## Trigger

`adFailure` → `on` (boolean true), using the accepted ConfigMap edit plus flagd rollout/read-back path. The recorded undo returns it to `off`, rolls flagd and restarts ad. This records the existing recipe, not proof that every provider/client always requires that restart.

## Ground truth (Mechanism)

The advertising service intermittently aborts advertisement-retrieval requests after preparing the ads but before sending a successful response, returning gRPC UNAVAILABLE. The failure path selects requests with a nominal one-in-ten probability, so this is a partial request failure rather than a total service outage. The frontend's advertisement-data RPC gateway rejects these errors and the API handler propagates them instead of supplying a successful replacement ad response; its server instrumentation records the exception and marks the span as an error.

## Diagnostic and scoring boundaries

A supported Suggested root cause should identify intermittent server-side advertisement retrieval failures and their propagation to the frontend ad-data path. Naming the flag, merely naming ad, or calling all checkout/payment traffic broken is not equivalent. Exact probability is a source fact, not a mandatory measured 10-percent ratio in the Report: a finite sample can differ, and per-request probability is not an absolute span-error rate. Apply ADR 0014's human semantic and citation review; source truth in this file is not evidence the Run retrieved.

The browser may show no ad content when the query supplies no data; do not require or claim that UI symptom universally. Do not infer a final HTTP status/body, retry count, sustained total outage, or checkout impact without retrieved evidence. Source contains a warning log, but the historical venue query returned zero matches. Future diagnostic acceptance must retrieve actual trace/response/log evidence where available and honestly disclose missing channels.

## Evidence and qualification gates

[Source verification](source-verification.md) cites original line numbers from immutable upstream commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f` and retained source receipts. [Venue evidence](venue-evidence.md) separately records historical observed symptoms and original-threshold behavior. Source-to-deployed-image correspondence still requires verification; no current system was inspected.

The historical `>0.1/s` rule did not fire before undo. Recorded samples cross `>0.03/s` for frontend and frontend-proxy, but that is not live corrected-rule acceptance or a guaranteed two-Alert Cascade. Human approval closes only ticket 40's definition gate. ADRs 0013–0017's model, citation, budget, mediated access, venue and Change gates still apply. No model/cluster/demo was run.
