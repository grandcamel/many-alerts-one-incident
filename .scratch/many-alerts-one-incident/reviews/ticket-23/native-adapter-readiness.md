# Ticket 23 native-adapter readiness

**Purpose:** source-only preparation for a future native-client adapter.  It does
not authorize a client launch, model call, credential use, or a change to the
closed Ticket 23 execution card.  The supplied metadata-only scout is
`/Users/jasonkrueger/maoi-ticket23-evidence/20260921-integrated-rehearsal/native-event-preparation.md`.

## Evidence boundary

The scout inventoried a preserved *wrapper* JSONL stream: 200 JSON objects and
134,302 bytes.  It observed wrapper-labelled `system/init`,
`system/thinking_tokens`, `assistant`, `rate_limit_event`, a usage-only object,
and one successful `result`; the wrapper's init and assistant model strings
agree.  The result carried elapsed fields, usage-shaped fields,
`modelUsage`, `permission_denials`, and `total_cost_usd`.

Those are metadata observations only.  They do **not** establish an exact native
CLI/client schema, client version, stream provenance, authenticated provider or
model identity, provider billing, permission semantics, tool registration, or
any API support.  `total_cost_usd` and `modelUsage` remain wrapper-emitted
estimate-style data until provider reconciliation.  The scout found no observed
tool-use/result, permission request/decision, cancellation, fallback/model
transition, provider-error, or error-terminal example.  Absence in this sample
is an unobserved case, never evidence that the client lacks or handles it.

The current parser must retain that distinction: it is a bounded synthetic
Claude-shaped parser, and the inventory's wrapper-only kinds and 68,903-byte
line make its existing diagnostic incomplete rather than native-compatible.
See [the timing core](../../../../prototype/run_timing/README.md).  The supplied
scout remains an external metadata artifact at the path above; this draft does
not reproduce transcript content.

The [installed-client evidence register](client-evidence-register.md) now freezes
local version/help and a wrapper command preview. This establishes syntax evidence
only; runtime compatibility remains unqualified. A separate
[documented subset](documented-stream-sources.md) pins official SDK fields for
[offline normalization](../../../../prototype/run_timing/DOCUMENTED_STREAM.md).
It is not an observed-and-qualified installed-client schema.

A separate [local TLS harness](../../../../prototype/mediated_client/README.md)
provides real Python loopback transport checks with synthetic leases/credentials.
Its [incremental extension](incremental-streaming-outcome.md) now verifies
first-frame delivery before final release, true-EOF terminal checks and partial
failure/revocation through the same two loopback TLS hops. Its fixed Python
fixture vocabulary is not an installed-client or provider stream schema.
The [configuration source map](client-configuration-sources.md) records current
client documentation. Neither supplies installed-client streaming, OS isolation
or billing acceptance. The
[supervised streaming join](supervised-streaming-outcome.md) now binds a fixed
child's decoded frames to parent transport receipts and process evidence. It
retains cancellation, partial delivery, cleanup timing and read-back failures
separately; the installed-client gate remains NOT RUN.

## What Ticket 23 can carry forward

| Existing contract | Reusable offline property | It does not prove |
| --- | --- | --- |
| [Timing binding](../../../../prototype/run_timing/TIMING_BINDING.md) | Canonical bounded fixture requests, explicit structured rejections, finite call history, controller-only completion | Native tool schema, registration, authorization, or client identity |
| [Integrated rehearsal](../../../../prototype/run_timing/TIMING_REHEARSAL.md) | Child-generated artifact linkage, separate stdout/stderr retention, supervisor result retained on evidence failure, held unknown/pending fixture effects | Stream origin, native cancellation/revocation, authenticated receipt, provider operation |
| [Outcome/recovery ADR](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md) | Derived execution remains separate from reported terminal and external effects | The actual client terminal vocabulary or error schema |
| [Synthetic parser boundary](../../../../prototype/run_timing/README.md) | Bounded decoding and fail-closed malformed/duplicate-terminal handling | Compatibility with the observed wrapper or any native stream |

## Next offline work units

Perform these in order, with synthetic/redacted fixtures only.  Each output is
a reviewed source artifact; none is a model probe.

1. **Exact-client evidence register.** Record the selected executable/build,
   documented stream mode, launch arguments, environment contract, and local
   self-documentation capture.  Record each field's source, type, optionality,
   ordering rule, and version.  A missing item is `UNKNOWN`; do not fill it
   from wrapper names or an assumed SDK schema.
2. **Versioned normalizer contract.** After that register exists, define only
   the observed-and-qualified event families and the minimum common envelope:
   stream sequence, receiver monotonic receive time, client session/request
   correlation where supplied, stream/source identity, raw-byte digest, and
   explicit `UNKNOWN` fields.  Preserve raw bytes or a bounded digest under the
   audit policy; reject unknown/ambiguous input with a durable reason.  Do not
   adopt the scout's illustrative family names as a native schema.
3. **Fail-closed fixture matrix.** Add redacted, generated fixtures for every
   qualified family and for malformed JSON/UTF-8, duplicate keys, non-finite
   numbers, unknown kind, missing required correlation, oversize record,
   event-limit overflow, missing/duplicate/conflicting terminal, and out-of-
   order records.  Assert the exact normalized result or hold reason.  Keep a
   wrapper-inventory fixture explicitly incompatible unless a later qualified
   contract says otherwise.
4. **Process/stream correlator.** Specify a Receiver-observed attempt ID,
   launch identity, stdout/stderr byte capture, process exit, timeout/cancel
   action, descendant reaping, and containment fields separately from parsed
   events.  Terminal success cannot override nonzero exit, timeout,
   cancellation, malformed evidence, duplicate terminal, missing reaping, or
   absent stream provenance.  This extends the fixed supervisor contract; it
   does not turn fixture evidence into native containment proof.
5. **Identity and cost partitions.** Give requested model, wrapper-reported
   model, client-qualified actual model, fallback transition, usage estimate,
   reservation, provider actual, and unknown exposure distinct fields and
   evidence categories.  Never derive one from another.  A client fallback,
   refusal, or cancellation must remain a separately evidenced state, rather
   than an inferred result of a terminal string.

## Exact evidence still required

| Area | Required future exact-client evidence | Offline acceptance predicate |
| --- | --- | --- |
| Tools | Registration/listing mechanism, invocation and result records, IDs, ordering, malformed/partial behavior | A redacted fixture proves only the captured version's parser mapping and pairing rules |
| Permissions | Request, decision/denial, effective scope, and whether any dispatch occurred | Denial is represented separately from a no-op or uncertain effect; no permission is inferred from `permission_denials` |
| Cancellation | Operator action, client acknowledgement if any, stream/terminal behavior, exit and reaping observations | Timeout/cancel always overrides apparent terminal success; independently verify cleanup and preserve any confirmed/uncertain effects |
| Fallback | Trigger, requested and actual identity, transition ordering, and effect on budget/admission | Missing transition evidence stays `UNKNOWN`; it cannot become primary-model success |
| Errors | Provider/client/process error fields, retryability, terminal relation, and post-dispatch effect status | Error fixtures preserve reported and derived outcomes; uncertain effects hold reconciliation |

## Dependency gates

| Owner | Adapter dependency | Gate before a qualified native attempt |
| --- | --- | --- |
| [Ticket 36](../../issues/36-forwarder-integration-and-acceptance.md) | Fixed mediated route, per-Run sentinels, exact client endpoint/trust setup, TLS, revocation, direct-route prevention | The register identifies the exact mediated launch path and its receipt/correlation boundary; no direct credential fallback |
| [Ticket 38](../../issues/38-budget-accounting-and-model-qualification.md) | Receiver-owned atomic reservation and provider-actual reconciliation | Reservation precedes launch; usage/estimate does not settle spend; billing lag or unknown exposure holds admission |
| [Ticket 39](../../issues/39-report-audit-and-scoring-specification.md) | Private bounded capture and human-reviewable evidence identity | Redacted stream/process evidence has immutable attempt/revision linkage, visible truncation/loss, retention bounds, and no raw prompt/Ground-truth leak |

ADR 0013 makes the mediated Anthropic route mandatory for model admission and
keeps provider billing authoritative; [ADR 0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md)
does not establish client compatibility or rates.  ADR 0014 keeps audit evidence
and human adjudication separate from execution and spend; [ADR 0014](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md)
does not qualify this adapter.

## Acceptance ladder and current state

| Gate | Evidence required | Current state |
| --- | --- | --- |
| A — source readiness | This boundary, exact-client evidence register template, and unresolved-field list reviewed without schemas invented | CLI/version/help captured and official SDK source subset pinned; installed-client schema and launch contract remain incomplete |
| B — offline normalization | Version-pinned, redacted fixtures cover every qualified family and negative matrix; bounded parser preserves raw/digest provenance and holds invalid input | Documented-subset implementation and fixtures prepared; installed-client qualification remains NOT RUN |
| C — supervised client contract | Exact-client stream plus independent process/stream identity, cancel/timeout/reap evidence, and authenticated receipt correlation | NOT RUN |
| D — mediated and accounted admission | Ticket 36 route/revocation evidence and Ticket 38 durable reservation/provider reconciliation | NOT RUN |
| E — audit and qualification | Ticket 39 private evidence/review plus ADR 0013/0014 model, billing, human, tenant, and venue gates | NOT RUN |

The rehearsal's scripted child, structural hashes, fixture model label, normal
completion, and held unknown/wait cases support only their fixed synthetic
claims.  They do not advance any native-client, authentication, provider,
billing, tenant, or venue gate.
