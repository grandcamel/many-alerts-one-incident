# Ticket 41 Change coordinator and retrieval specification

Status: source-only implementation plan. This bounded contract changes no
Kubernetes, collector, Loki, Eyes, Forwarder, flagd, Skill, Run, tenant, or Fault;
no live actuation, provider call, cluster probe, model run, or C2 qualification occurred.

## Authority and boundaries

ADR 0015 and ticket 25 require one operator-controlled in-cluster coordinator, one globally serialized active
action, immutable request identity, direct action records, intent before mutation, fresh value/version
preconditions, linked undo, and restart reconciliation. A Change records what an action and its stages
establish; it does not establish diagnosis, causality, Alert/Incident recovery, or repository adjudication.
Runs remain read-only for Kubernetes and receive no coordinator control, mutation token, or emergency
credential.

Accepted policy is distinguished from proposed implementation choices below:

| Kind | Contract |
|---|---|
| Accepted | One active action globally; no queued injection; stable Change ID; same-ID same-payload replay is idempotent; conflicting reuse is rejected. |
| Accepted | Private journal and sanitized dedicated Change stream are separate from Receiver recovery, Memory, and ADR 0010's 24-hour best-effort Run feed; current-rehearsal Change retrieval is Run-readable only through approved Eyes/Forwarder scope. |
| Accepted | 100 MiB journal, 10 MiB recovery/undo reserve, seven-day journal/Change retention, 180-second actuation threshold, 30-second queryability threshold, and at most three telemetry sends per stage per authorized delivery attempt. |
| Accepted | Undo is a distinct linked Change, has priority only after reconciling in-flight injection, and uses recorded prior value plus fresh resource-version/value checks. |
| Proposed | Physical journal/database, coordinator framework, exact Kubernetes subject names, API endpoint paths, serialization format, and operator authentication mechanism. These require source and intended-venue review. |

## Stable identities and sanitized body

Every request has a `change_id`, `request_id`, immutable canonical payload digest, operator alias, private
principal reference if available, source namespace, request sequence, and creation time. Each action stage has
a stable `stage_id`, `stage_seq`, `intent_id`, `dispatch_id`, and evidence references. Undo has its own Change
and request IDs plus `undo_of_change_id`; it never reuses the injection IDs. A delivery attempt has
`delivery_id` and `delivery_attempt` (1..3).

The private journal's canonical request is bounded and contains only:

* one coordinator-selected Fault recipe identifier;
* one fixed target/resource identity from the allowlist;
* requested flag key and variant/value from the allowlist;
* explicit action kind (`inject`, `undo`, `reconcile`, or `emergency_undo`);
* expected prior value and resource version when required by the recipe;
* operator alias, private principal reference, and request sequence; and
* the payload digest and schema version.

Reject unknown fields, caller-selected namespaces/resources, arbitrary JSON patches, shell/exec strings,
credentials, tokens, headers, raw prompts/tool bodies, personal identity, Ground truth, Mechanism prose,
scoring feedback, and unbounded application text. Shared Change records retain only a bounded operator alias,
resource identities, values, versions, timestamps, digests, result codes/classes, and evidence links. The
private journal may retain a principal reference for audit; that reference is never projected to the shared
stream. An alias never attests a natural person's identity.

## Kubernetes authority and allowed operations

The coordinator runs under a dedicated operator identity and separately mounted configuration from Runs. Its
Kubernetes permissions are scoped to the named demo ConfigMap, the named Fault-specific Deployments/Pods, and
read-only resources needed for rollout, served-value, and evaluation read-back. The allowlist binds namespace,
resource kind, resource name, permitted verbs, allowed fields, and preconditions. The coordinator rejects a
target or verb absent from that allowlist even if the service account could technically perform it.

The logical operation vocabulary is fixed:

| Operation | Allowed purpose | Required evidence/precondition |
|---|---|---|
| `config_read` | Read the named `ConfigMap` and the JSON document in `data[<pinned_document_key>]` | Resource identity and read digest. |
| `config_write` | Parse that JSON document and change only `flags[<recipe>].defaultVariant` | Current `resourceVersion` and prior value match; record accepted write response/version. |
| `rollout_restart` | Restart only the named `flagd` Deployment or recipe-named service Deployment | Fixed target and supported Kubernetes action; record accepted request and observed rollout. |
| `pod_delete` | Delete only the owner-verified `email` Pod for the accepted email undo recipe | Coordinator-selected Pod UID/resourceVersion and explicit undo stage; record response and replacement observation. |
| `resource_read` | Read rollout, Pod status, readiness, and versions | Read-only fixed target; unknown remains unknown. |
| `served_read` | Use a pinned supported flagd served-value surface when the recipe profile requires it | Capability profile must identify endpoint/resource and its version; no fallback by guess. |
| `evaluation_read` | Retrieve application evaluation evidence through approved Eyes/Forwarder when profiled | Fixed collector/source query and Change correlation; absence is unavailable, not false. |
| `stream_send/query` | Write/query dedicated Change records | Collector-owned producer identity and bounded query. |
| `annotation_create` | Optional derived audience annotation | Same Change/stage ID; failure cannot change authoritative state. |

There is no generic shell, `kubectl exec`, caller-supplied patch, arbitrary rollout target, direct upstream,
flagd-ui mutation, or OFREP assumption in the contract. `flagd` v0.16.0 is distroless in the accepted recipe
notes; an exec path is not generally supported. The coordinator may use a served-value path only after its
pinned venue capability profile proves that path for this flag. The historical note permits `flagd-ui`
container file read or OFREP `:8016` after rollout status, but neither is declared universal here. Unsupported
read-back records `unknown`; it holds qualification only when the recipe's profile marks served read-back as
required.

The Run identity, mounts, service account, network policy, and emergency credentials are disjoint from the
coordinator. A boundary acceptance must prove that a Run can neither invoke these operations nor read their
private mounts. flagd-ui editing is disabled or restricted during a managed demonstration. Direct
administrator intervention is an explicit emergency/out-of-band path, recorded as untracked when it cannot
enter the journal, not a hidden coordinator route.

RBAC alone is not field-level policy. The adapter must verify fixed owner/name, namespace, UID, and current
resourceVersion for every Pod/Deployment action and reject caller targets; it exposes no `exec`, arbitrary
patch, or dynamic Pod selection. Intended verbs are `GET`/guarded `PATCH` ConfigMap, `GET` plus the fixed
restart operation per named Deployment, and `GET`/guarded `DELETE` for the owner-verified email Pod. A restart
is the fixed `PATCH /apis/apps/v1/namespaces/{pinned_ns}/deployments/{pinned_name}` changing only
`spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"]` under UID/resourceVersion
preconditions; track its generated timestamp, never a raw command. Rendered names/selectors remain manifest
pins.

The ConfigMap mutation is a bounded parse/patch, not string replacement. Read the pinned JSON document,
require `flags[recipe].defaultVariant` and the requested variant in `variants`, preserve `$schema`, state,
description, every other flag, and unrelated data, and record canonicalization differences in a bounded
digest. Unknown key, malformed JSON, missing recipe, type/value mismatch, or unexpected nested field holds the
write. Check expected pre-value and `resourceVersion` in the same guarded update; send no partial patch.

The historical pinned recipe identifies ConfigMap `flagd-config`, data key `demo.flagd.json`, serialized path
`flags[recipe].defaultVariant`, and served path `/app/data/demo.flagd.json`. This pins the proposed adapter
shape, not current manifest binding; read the rendered name/key from the intended-venue manifest.

## Fault recipes

Recipes are exact allowlist entries, not a generic flag editor. The accepted recipes below preserve the source
action and undo ordering:

| Recipe | Injection | Undo ordering |
|---|---|---|
| `paymentUnreachable` | Set `paymentUnreachable` to `on`; restart `flagd` and observe rollout before timing. | Set `off`; restart `flagd`; restart `checkout` to clear leaked connections. |
| `emailMemoryLeak` | Set `emailMemoryLeak` to `1000x`; restart `flagd` and observe rollout. | Set `off`; restart `flagd`; delete the `email` Pod; observe replacement/backoff. |
| `cartFailure` | Set `cartFailure` to the historically captured `100%` variant; restart `flagd` and observe rollout. | Set `off`; restart `flagd`; restart `cart` to clear retrying multiplexers. |
| `adFailure` fallback | Set `adFailure` to `on`/boolean true; restart `flagd` and observe rollout. | Set `off`; restart `flagd`; restart `ad`. |

Each recipe has one injection Change and one linked undo Change. No two flags are changed together. A
recipe-specific restart is part of undo, not evidence that the Fault symptoms or Incident recovered. The
coordinator records the requested, accepted, observed, served, and evaluated stages independently.

The table's `off` values are the historical recipe values. At actuation, record the actual pre-injection
baseline and restore that value when it is still valid; an optional off preflight may be required by the
venue. The undo precondition is the expected post-injection value and version, never equality with the old
value: if current state differs from the recorded post-injection state, hold for drift reconciliation before
restoring the recorded baseline.

## State machine and ordering

Change state is one of `RECEIVED`, `ACCEPTED`, `HELD`, `IN_FLIGHT`, `PARTIAL`, `COMPLETE`, `INCOMPLETE`,
`UNKNOWN`, `REJECTED`, or `UNTRACKED`. Stage state is one of `PENDING`, `INTENT_RECORDED`, `DISPATCHED`,
`SUCCEEDED`, `FAILED`, `UNKNOWN`, `SKIPPED`, or `UNAVAILABLE`. `COMPLETE` requires every required stage to be
`SUCCEEDED`; each stage declares `required`, `optional`, or `unsupported` in its recipe capability profile. A
successful write never promotes rollout, served, or evaluation. Unknown/unavailable/partial required stages or
drift hold new injections. An optional evaluation that is unavailable remains visible and prevents an
evaluation claim, but does not by itself block ordinary action or a supported causal inference under ADR 0014.

The coordinator performs this sequence under one global action lock:

1. Authenticate operator, validate alias/private principal, recipe, target,
   payload digest, sequence, and preconditions.
2. Reject conflicting reuse or return the recorded progress for an exact
   duplicate. Reject a second injection while any action is unresolved.
3. Append and durably commit the request, immutable payload, and `ACCEPTED` or
   `HELD` decision before acknowledging acceptance.
4. Append and commit a stage intent before each Kubernetes or telemetry dispatch.
5. Dispatch only the allowlisted operation with a fresh value/version check;
   append response receipt, observed state, and evidence references separately.
6. Advance to the next stage only after the prior stage's required observation
   succeeds. `UNKNOWN`/`UNAVAILABLE` permits only read-only reconciliation,
   query, export, or inspection; it cannot start another mutation stage.
7. Release the lock only after completion, hold, rejection, or operator
   reconciliation. An undo cannot begin until unresolved injection dispatch is
   reconciled.

Sequence numbers establish causal order. Wall-clock, ingestion, Kubernetes resource-version, and observation
timestamps are stored separately and never substitute for a stage sequence. An accepted write with a lost
response is `UNKNOWN` until read-back; timeout is not cancellation of the upstream action.

## Undo, drift, and emergency path

Undo reads current state and requires the recorded post-injection value plus a fresh resource-version
precondition to match. If current state differs from the post-injection state, it enters `HELD`/`UNKNOWN` and
requires explicit operator reconcile; there is no blind overwrite. When valid, restore the recorded
pre-injection baseline, then follow the recipe restart/delete ordering and record every stage. Unrelated
ConfigMap fields are preserved.

If telemetry or journal storage is unavailable, the coordinator attempts local durable recovery recording. If
recovery recording itself is unavailable, an operator may perform the fixed emergency undo directly through
the separately authorized emergency path. The result is an explicit `UNTRACKED` audit gap; the system
prioritizes restoration, disqualifies the sample, and never pretends the Change is complete. Emergency reserve
cannot be consumed by ordinary injection records.

## Journal, stream, and retention

The operator journal is durable across coordinator and pod restart within a rehearsal, separate from Receiver
recovery and Run Memory. It has a hard 100 MiB limit, with 10 MiB reserved exclusively for recovery, undo,
handoff, and capacity/error records. Every private record includes bounded schema version, record ID,
Change/stage identity, stage sequence, event type, actor alias/private principal reference, resource identity,
monotonic and wall times, outcome, evidence digest, and predecessor/digest fields. `record_digest` is computed
over the canonical record with only its own digest and encoded-length fields excluded; `predecessor_digest`
remains in the hash chain. Record size is charged as encoded bytes, including framing and indexes. Proposed
bounds are 16 KiB per row, 8 KiB per canonical request, 128-byte IDs, 64-byte aliases, 100 query results, 1
MiB query response, and 5 seconds per query. Reject or hold before crossing a bound; never evict unresolved
records. Reserve exhaustion is a visible hold, not a reason to block fixed emergency undo.

The dedicated Loki Change stream carries a sanitized projection of the bounded records through the collector
with the planned stable stream identity `service_namespace=maoi-change`, `service_name=change-coordinator`,
and `feed=change`. The collector, rather than caller fields, derives the trusted producer identity. Untrusted
Run headers/body fields cannot forge it. Change and stage IDs belong in structured metadata or bounded fields,
not high-cardinality index labels; it excludes the private principal reference. Loki's seven-day policy is
separate from the journal's seven-day retention and ADR 0010's 24-hour Run feed. The Grafana documentation
says retention is applied by the Compactor, stream selectors use labels, and chunk deletion is asynchronous
after marker/sweeper delay; therefore seven-day config is not proof of exact physical byte expiry. Acceptance
must verify query age guards and current-rehearsal readiness at Eyes, while physical expiry remains an
intended-venue gate. See <https://grafana.com/docs/loki/latest/operations/storage/retention/>.

Before seven-day expiry, reset, pod destruction, or venue teardown, unresolved records require reconciliation
or a private handoff containing identities, stages, unknown effects, evidence references, reservation/audit
digests, and operator acceptance. Read back the handoff digest before destroying the only copy. A corrupt,
unavailable, or disk-full journal holds new injection and marks the Change incomplete; it cannot discard an
acknowledged request. C2 remains a separate bounded evidence lane and cannot promote this plan to live or
tenant acceptance.

## Retrieval contract

The coordinator emits a diagnostic readiness record for the current rehearsal before accepting the first
injection. It proves only that the configured collector-to-Loki write and approved Eyes/Forwarder query can
round-trip a synthetic Change record with its producer identity, Change ID, stage ID, and source namespace. A
transport send receipt alone is insufficient.

The collector query reference is bounded and explicit: `ChangeQuery(rehearsal_id, source_namespace,
change_id?, stage_id?, from, to, limit) -> ChangeRecord[]`. Its Loki selector uses only the fixed stream
labels above; IDs and UUIDs are filters/structured metadata, not index labels. The query is fixed to the
Change source namespace and current rehearsal identity. The response must preserve source, Change/stage IDs,
sequence, event type, actor alias, target, timestamps, outcome, and evidence digest, with bounded result
count/bytes and no raw secrets. Duplicate records deduplicate by immutable record ID/digest for display while
retaining delivery provenance. Conflicting same-ID records remain visible and hold the Change.

Historically proven evaluated retrieval is Tempo evaluation evidence for `paymentUnreachable` and
`cartFailure`, including flag key/value, reason, and provider; `emailMemoryLeak` had zero evaluation traces in
the measured window. Those are source facts, not universal support. The capability profile must name the
supported native served/evaluated surface for each recipe. Missing served or evaluation evidence is
`UNKNOWN`/`UNAVAILABLE`, never a negative evaluation or proof that every application saw the value. Stored
ConfigMap, flagd-served, rollout health, application evaluation, symptoms, and diagnosis are separate claims.
No query may read or emit Ground truth or scoring feedback.

Optional Grafana annotation creation derives from the same Change/stage IDs and is never an authoritative
receipt, a required Run surface, or a gate for undo. Collector outage, query timeout, no Loki visibility,
failed annotation, and stored/served mismatch each produce explicit stage outcomes and preserve local records
for later delivery.

## Deadlines and delivery

The monotonic actuation budget is 180 seconds from accepted dispatch through config write, recipe
restart/rollout, and bounded read-back. Each queued stage has 30 seconds to become queryable through Eyes. At
a threshold, stop starting new stages, record `UNKNOWN` or `INCOMPLETE`, and hold injection; do not imply that
a timed-out Kubernetes or upstream operation stopped. An operator may reconcile observed state, then resume
only with a fresh authorized decision.

Telemetry delivery may retry a journaled stage with bounded backoff and no more than three sends for one
authorized delivery attempt. Proposed waits are 1s, 5s, and 15s with a 30-second total delivery ceiling; retry
does not redispatch Kubernetes mutation. Proposed pending delivery is capped at 1,024 rows and export
concurrency at one. Exhaustion leaves pending delivery for `inspect`/`resume`. Controls are operator-only:
`inspect`, `reconcile`, `resume`, `undo`, `abandon`, `handoff`, and `reset`; each requires a private principal
reference and writes an operator action record. Reset cannot erase unresolved state or change a seven-day
record into a success.

## Crash and drift recovery

| Crash/failure point | Required state and next action |
|---|---|
| Before request commit | No acceptance was acknowledged; a repeat validates anew. |
| After request commit before response | Return durable progress; do not duplicate the request. |
| After intent commit before dispatch | On restart hold and reconcile intent; no automatic mutation retry. |
| After dispatch before response | Mark dispatch `UNKNOWN`; read fresh resource state before any undo/retry. |
| After accepted ConfigMap write before rollout | Record accepted write; hold at rollout until current state/version is reconciled. |
| Rollout still running at 180 seconds | Mark rollout incomplete/unknown and hold; timeout does not cancel Kubernetes. |
| After stage receipt before journal commit | Reconcile receipt/digest; conflicting or missing commit is a durable hold. |
| Restart during query/export | Preserve local stage; dedupe late delivery and retry only telemetry. |
| Resource value/version drift | Hold ordinary action and require explicit operator reconciliation. |
| Out-of-band mutation detected | Mark `UNTRACKED`/unknown, stop injection, retain evidence and disqualify sample. |

No automatic mutation replay occurs after restart, lost response, timeout, duplicate, or late delivery.
Confirmed stage receipts are never replayed; an unknown stage is reconciled against current identity/version
before any fresh operation. Undo priority does not override an unresolved injection dispatch.

## Offline acceptance and future live gates

Offline fixtures must use the real coordinator, journal, collector transport, and query interfaces, with
deterministic endpoint doubles only at transport boundaries. Required cases are:

1. duplicate same-ID/same-payload replay and conflicting same-ID rejection;
2. simultaneous injection/undo serialization and no queued injection;
3. intent before each dispatch, lost write response, running rollout timeout,
   restart between intent/effect/receipt, and no automatic mutation replay;
4. stored-versus-served mismatch, unavailable evaluation, duplicate/late
   delivery, collector outage, no Loki visibility, failed annotation, and
   bounded three-send telemetry retry;
5. version/value drift, partial action, recipe-specific undo ordering, emergency
   undo without recording, private alias/principal redaction, and forbidden
   Ground truth/raw-secret fields;
6. 100 MiB cap, 10 MiB reserve, byte accounting, expiry, handoff/read-back,
   corruption, disk-full, reset, and retention-age guard;
7. Run identity cannot mutate/read coordinator resources; inaccessible mutation
   authority fails closed; and unsupported served/evaluated capability stays
   unknown; and
8. every Fault recipe's fixed target/value allowlist and exact undo sequence.

Offline success proves the contract and boundary fixtures only. Intended-venue gates remain separately
authorized: coordinator identity and Kubernetes grants, collector/Loki producer trust and seven-day policy,
Eyes/Forwarder native query support, served/evaluation capability per flag, actual rollout/read-back, operator
emergency authority, venue age/readiness/teardown, cloud/model budget, and C2 evidence qualification. None are
run or promoted here.

## Sources and gaps

Read sources:

* [issue 41](../../issues/41-change-coordinator-and-retrieval-specification.md);
* [ADR 0015](../../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md) and
  [ADR 0016](../../../../docs/adr/0016-venue-lifetime-is-bounded-with-protected-teardown.md);
* [ticket-25 facts](../ticket-25/facts.md), [round 1](../ticket-25/round-1.md),
  and [round 2](../ticket-25/round-2.md);
* [issue 10](../../issues/10-faults-and-their-cascades.md) and
  [issue 27](../../issues/27-verify-the-signal-surface-and-settle-the-fault-gates.md);
* [issue 26](../../issues/26-can-one-doks-node-hold-the-chart.md) and
  [ticket-40 venue evidence](../ticket-40/venue-evidence.md) for the ConfigMap/rollout/read-back
  correction;
* [ticket-40 source facts](../ticket-40/source-facts.md), [definition](../ticket-40/definition.md), and
  [source verification](../ticket-40/source-verification.md), including the pinned
  [demo.flagd.json receipt](../ticket-40/upstream/demo.flagd.json.txt) and
  historical `prototype/cascade-timing` ref `557153bf531222dec1751f4bb5ac31adefcfa323`; and
* the coordinator-side [recipe source check](recipe-source-check.md) from the
  root review; and
* [telemetry integration](../telemetry-change-reference-integration.md); and
* Grafana Loki retention documentation cited above.

The sources do not settle the physical journal technology, exact Kubernetes subject names, coordinator
endpoint schema, private-principal representation, collector trust configuration, Eyes/Forwarder query API,
per-flag served-value capability, or application evaluation correlation implementation. Those remain proposed
and require a source-pinned design review. Historical recipe evidence does not prove current image/source
correspondence or live grants. Physical Loki expiry requires intended-venue verification because compaction
and sweeping are asynchronous. Real coordinator, Kubernetes, collector, Loki, Eyes, Forwarder, operator,
tenant, C2, model, budget, and teardown acceptance are NOT RUN.
