# Ticket 23 native-launch evidence contract

**Status:** preparation contract, 2026-09-22. **Native launch remains CLOSED.**

This contract turns the accepted boundaries in [ADRs 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md), [0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md), [0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md), and [0014](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md) into a future evidence checklist. It does not authorize a command, credential, provider account, model request, tenant operation, C2 activity, or environment mutation.

“Required” below means a predicate must be demonstrated before the named state can be claimed. “Proposed” references a specification that still needs implementation and acceptance. A source file, synthetic fixture, or planned schema is not execution evidence.

## States and non-implications

| State | Meaning | It does not establish |
| --- | --- | --- |
| `launch_ready` | All pre-launch predicates for one exact scoped execution card are retained and verified. | A spawned process, provider request, client compatibility, effect, charge, Report grade, or qualification. |
| `attempted` | A named launcher recorded a bounded attempt with immutable source/card bindings. | Successful execution, delivered request, provider actual, effect, or qualification. |
| `executed` | The derived outcome has clean containment and the retained terminal/evidence predicates required by ADR 0012. | A confirmed Incident effect, settled cost, Report grade, or model qualification. |
| `qualified` | Ticket 38 accounting, Ticket 39 audit/adjudication, effect, venue, and all lifecycle predicates pass. | A global cheapest-model conclusion, production readiness, or permission expansion. |

The existing documented-stream normalizer is an official-source-derived *offline subset*; the supervised stream is a fixed local TLS child/parent rehearsal. Neither admits native launch or establishes model qualification. They demonstrate neither installed-client compatibility, provider event origin, real authentication/routing, provider billing, model behavior, tenant effects, nor venue qualification.

## Fixed identity and card

The Receiver allocates every future attempt before launch. It must retain immutable references, not mutable names alone:

| Binding | Required pre-launch value | Post-attempt linkage predicate | Owner |
| --- | --- | --- | --- |
| Execution card | Card revision digest; intended candidate/model label, API auth mode, service scopes, venue, Fault/lifecycle purpose, approved Report/rubric references | Attempt, audit bundle, accounting, journal and human review cite the same card digest or explicitly record a revision conflict | Receiver/operator |
| Source | Exact repository revision and source packet/worker/adapter/Skill/prompt digests; fixed scenario/Fault identity | Launcher snapshot digest and retained process artifact match the card | Receiver/launcher |
| Attempt | `journal_generation`, `admission_id`, `run_id`, `attempt_id`, `reservation_id`, `lease_id`; only relevant `operation_id`/`intent_id` | Recovery journal, Forwarder receipt, accounting events, audit references and outcome share their applicable immutable IDs | Receiver |
| Route | Fixed Anthropic listener/origin, hostname, CA/certificate generation, service sentinel scope and expiry | Listener/control/route evidence records the generation and proves no caller-selected origin or direct credential route was accepted | Forwarder/Receiver |
| Time | Monotonic launch timestamp and one 300-second deadline | Every observed phase is joined to that launch clock; queue/setup/closeout gaps are visible | Launcher/Receiver |

The trusted operator freezes the executable, arguments, environment allowlist, candidate and route/scope in the card. An untrusted Run may not select or override those bindings, the provider origin, credentials, Fault or mutation scope. A card revision, source digest mismatch, expired grant, unknown generation, or missing binding holds launch.

## Bootstrap without circular proof

Installed-client compatibility is currently absent. A local fixture cannot prove it. **Native compatibility observation** is distinct from **model qualification**: the former can establish only client protocol behavior; the latter remains the representative lifecycle and human-review process in ADRs 0013/0014. Requiring a successful provider/model response before an isolated compatibility observation would make the gate circular. The bootstrap is therefore a **two-stage, non-qualifying compatibility gate**:

1. **Static launch readiness:** retain the exact installed client/version/help or source evidence, supported endpoint/TLS/credential configuration, fixed card and route profile. Unknown fields remain unknown; they are not guessed from documented SDK types or wrapper events.
2. **Proposed provider-disabled compatibility observation:** its design may be prepared locally now; it may execute only after acceptance proves an independently enforced no-provider-route/no-upstream-credential boundary for the exact native client process. A loopback endpoint variable, fixture route, or omitted credential does not prove zero provider access. Its card-scoped observations may decide protocol compatibility only. Failure, malformed events, containment loss, or an uncertain route holds and does not trigger a broader fallback, direct credential restore, automatic retry, or model-qualification claim.

This ordering permits a future bounded test of an otherwise-unverified seam without treating a model-success response as authorization. It approves neither such a probe nor paid work. Current fixture/macOS child isolation does not establish the needed native safe boundary, so all native probes remain `CLOSED`; any later paid attempt needs Ticket 38 admission first.

## Required pre-launch evidence

The table applies to a **metered diagnostic**. A provider-disabled compatibility
card instead needs the static/source, process isolation, exclusively local route,
clock, capture and exact probe-card predicates; it must independently prove no
provider route or upstream credential can be used. It supplies no provider billing
or model sample. A **model-qualification** card additionally needs the intended
venue, Fault matrix and audit capacity before launch; actual Reports and human
verdicts belong after execution. No generic checklist row can turn an unknown
native observation into a pre-existing pass. The companion
[native-launch readiness record](native-launch-readiness.json) records applicability,
phase and current missing evidence explicitly; it is data, not an admission controller.


| Area | Required predicate before launch | Artifact/read-back | Missing current field or evidence |
| --- | --- | --- | --- |
| Client compatibility | Exact installed client executable/version and supported print-stream/event, endpoint, CA and auth configuration are captured for the card; unsupported or conflicting field is refused. | Version/help/source receipt, configuration digest, card digest, redacted schema map. | No installed-client compatibility or native event-schema observation. |
| Isolation and route | Ticket 36’s mandatory Jira, Grafana/Eyes, Kubernetes and Anthropic routes are ready for a Run; Confluence is optional and failures remain visible Memory degradation; Anthropic is a fixed TLS route, sentinel only is Run-visible, upstream credential is absent from Run, direct egress/bypass resistance is accepted for the exact process boundary. | Receiver registration + heartbeat/generation receipt; route/TLS/certificate identity; denied-bypass acceptance record. | Current loopback harness is not the Forwarder, OS isolation, real TLS trust wiring, or direct-route proof. |
| Authority | Receiver journal admission, reservation, and lease registration commit before launch; scope, expiry and revocation bind the Run/card/generation. Restart invalidates prior leases. | Ticket 37 journal transaction and Forwarder control receipt. | Proposed recovery/Forwarder interfaces are not implemented acceptance evidence. |
| Budget | Ticket 38 has reconciled applicable historical actuals, liabilities and unknown exposure. It can prove the aggregate experiment liability plus new defensible exposure is **strictly less than USD 50**, without adding a reservation and final actual twice. | Receiver-owned accounting snapshot, coverage/lag evidence, `R`, `U`, allocations, hold status, and admission event. | Current estimates/fixture reservations are not provider actuals; prior applicable spend/exposure is not established as zero. |
| Human materials | For a diagnostic producing Reports, the exact rubric and Ground truth are frozen and kept operator-only; runtime capture must enforce that boundary. | Revision/digest and access-purpose receipt. | Pinned synthetic rubric approval exists; it neither proves runtime access control nor adjudicates future Reports. |
| Venue/effects | The card declares its actual venue and permitted effect surface. A fixture diagnostic cannot silently mutate a tenant. Representative model qualification additionally requires Ticket 42 intended-venue and Ticket 41 lifecycle acceptance. | Current accepted/pinned readiness references. | No venue or tenant/Incident acceptance. |
| Time/containment | Launcher can observe launch through closeout on a monotonic clock and enforce the original 270/20/10 schedule. | Preflight and adversarial acceptance record. | Current fixtures measure a process interval; they do **not** measure launch-to-durable-closeout. |

Audit preflight for qualification must verify private capture, read-back, sanitization and capacity under ADR 0014: 100 MiB per Run, 2 GiB total and at most 30 days. Capture loss mid-Run makes the sample unverifiable but cannot block required OPS handling, silently evict unreviewed evidence or expand storage.

No preflight result may erase an already durable Notification admission or unsettled external effect. A financial or readiness denial records a hold; it does not imply no provider use by an earlier attempt.

## Attempt protocol and evidence

1. Receiver validates the immutable card and all pre-launch predicates.
2. In the Ticket 37/38 transaction, it preserves source/admission, computes liability, creates the reservation and hold-free launch claim, and records the lease/card/generation. Any uncertainty rejects launch while retaining the admission.
3. The launcher records `launch_monotonic`, snapshots the exact card/source bindings, starts only the fixed client under the accepted isolation, and starts the original 300-second clock. Queue wait and independent preflight before process launch are separately visible. Run startup uses the launch clock; it cannot restart that clock. Capture the interval through durable closeout explicitly: the current fixture excludes transport cleanup and publication from its process duration, so that duration cannot establish complete native acceptance.
4. Operator cancellation, loss of mandatory route authority, or applicable reference revocation triggers sentinel revocation and interruption immediately; none waits for the work deadline. Independently, reaching `launch + 270s` triggers the same cleanup. Cancellation at `c` gives local-flush cutoff `min(c+20s, launch+290s)` and kill/reap cutoff `min(c+30s, launch+300s)`; it never receives a new full deadline. A venue admission hold alone does not extend or erase an already-active Run's deadline. Malformed required execution evidence holds the result. Audit capture failure alone follows the separate OPS-preserving rule above. Revocation cannot undo an already-dispatched request.
5. The outcome is derived under ADR 0012: clean exit/prose never overrides spawn failure, nonzero/error terminal, timeout, cancellation, malformed/capture-lost evidence, or unconfirmed containment. Required operation effects are separately confirmed, partial, unknown, absent, or justified no-op.
6. Ticket 38 records every distinct charge line, coverage period and final coverage completeness. Usage or an estimate is informational. Unknown/partial billing remains `U` or indeterminate; it cannot become zero through exit, cancellation, retry, week rollover, or rehearsal reset.
7. Ticket 39 retains private sanitized evidence and records a named human Report adjudication. A human decides supported causal/mechanism claims; no automatic blanket grade follows terminal success or telemetry.

## Required post-attempt observations

| Observation | Completion predicate | Failure disposition |
| --- | --- | --- |
| Launch/containment | Launch and closeout timestamps, supervisor actions, root/descendant reaping, pipes/capture state, card/source/lease bindings and any gap are retained. | `incomplete`/containment hold; no success inference. |
| Native stream/client | Retained bounded raw/redacted event evidence matches the pinned installed-client profile; parser records unknown/duplicate/malformed/loss distinctly. | Compatibility remains unqualified; no schema allowlist expansion. |
| Route/authority | Forwarder records the matching generation/lease/scope, fixed route, request disposition and revocation state without exposing credentials/sentinels. | Dispatch may be `unknown`; reconcile before retry. |
| Effects | Trusted scoped response/read-back links applicable intent/operation to confirmed, partial, unknown, absent, or justified no-op. | Preserve recovery obligation; do not replay an uncertain mutation. |
| Money | Unique provider charge lines, account/date attribution, complete coverage and reconciled per-attempt sum are retained separately from R/U/estimate. | Sticky accounting hold; no new launch if headroom is not defensible. |
| Report review | Private bundle is complete/readable, Report revisions and named adjudication identify the exact rubric/ground truth and verdict. | `not_adjudicated`, disputed, or incomplete; no qualification. |

`execution` can be completed while effects, money, review, or qualification remain held. A confirmed effect does not settle a charge; a billing line does not prove causal quality; an adjudication does not prove route containment.

## Qualification gate

Only Ticket 38/39’s set-level process may write `qualified`. The comparison set requires three complete representative lifecycles: two primary-presentation Fault samples and one designated fallback, with at least one cold-start and one Memory-assisted condition. For each sample it needs: the exact card/source/route/auth/venue condition; 300-second launch-to-durable-closeout acceptance; complete journal/effect reconciliation; private audit and a named human adjudication; complete attributable provider coverage and reconciled actual sum; no applicable hold; and the prescribed initial Report, supported match/update, and final resolution. Failed, retried, corrected, stale, missing, unknown, or disputed samples remain visible and cannot be averaged into a pass.

A qualification result is specific to its retained model, auth mode, client/version profile, Forwarder generation/route, venue, Fault, rubric and allocation. Its evidence cannot be transferred silently across material binding/revision changes; it does not authorize a different client, direct provider route, tenant permission, model, or future spend.

## Current evidence and explicit gaps

| Current artifact | Supported fact | Does not support |
| --- | --- | --- |
| [execution card](execution-card.md) and [native-adapter readiness](native-adapter-readiness.md) | Required fields and staged readiness were identified. | A complete native execution card, route, installed client, or launch readiness. |
| [client evidence register](client-evidence-register.md) and [documented-stream outcome](documented-stream-outcome.md) | Official-source subset and unknown wrapper/native fields are documented. | Installed CLI compatibility, native stream origin, auth or cost. |
| [supervised-streaming outcome](supervised-streaming-outcome.md) | Bounded synthetic child/loopback TLS evidence, ACK/receipt joins and conservative holds. | Production/Forwarder isolation, provider request, client compatibility, actual billing, 300-second total acceptance, effects, or qualification. |
| [Ticket 36](../ticket-36/forwarder-specification.md), [37](../ticket-37/recovery-specification.md), [38](../ticket-38/accounting-specification.md), [39](../ticket-39/audit-specification.md) | Proposed implementation/acceptance contracts. | Implemented interfaces, real seams, current account/venue evidence, or an authorization to launch. |

The missing runtime facts cannot be supplied by inference: installed-client compatibility and configuration profile; accepted OS/process isolation and bypass proof; current provider billing/rates/coverage and defensible U; live venue/tenant and scoped effect acceptance; and a launch-to-durable-closeout measurement design. Until those are resolved through the named owners, `native_launch` stays `CLOSED`.
