# Ticket 12 Eyes and read-only Kubernetes proposal

Status: source-only planning proposal, 2026-09-22. This document does not select
`mcp-grafana` or a standard-library `eyes` client, change a Skill, call a cluster,
use credentials, run a model, or accept a venue. It defines the smallest
interface that ticket 36 can enforce. Any native request form whose source or
intended-venue behavior is not pinned below remains unavailable until verified.

## Settled boundary

ADR 0011 gives each service a separate loopback HTTPS Forwarder listener, a fixed
upstream origin, a per-Run service sentinel, Receiver-only control, and managed
credentials outside the Run. Runs have no direct Grafana, Loki, Tempo, Prometheus,
or Kubernetes route. The Forwarder strips caller credentials and proxy headers,
rejects redirects and caller-selected origins, bounds requests/responses/timeouts,
and never retries an uncertain read as a mutation.

ADR 0010 separates sanitized Run telemetry from system telemetry and the dedicated
Change feed. Shared telemetry is best effort and diagnostic; it does not prove a
Fault, terminal success, or an external effect. Ticket 35 owns the sanitized Run
feed and its five-query self-observation bound. Ticket 41 owns the Change journal
and producer identity. Ticket 43 owns Confluence and supplies no Kubernetes or
telemetry authority. Ticket 19 remains a measurement prototype: Stage A supports
an exact pinned `mcp-grafana` transport subset, but does not select the client or
prove the intended venue; Stage B and C2 do not change that boundary.

## Authority and admission

The Receiver creates a lease containing `run_id`, `rehearsal_id`, service scope,
registered resource/template scope, maximum admission sequence, expiry, and a
distinct service sentinel. A Run may submit only a typed operation name and
bounded arguments. Caller-supplied namespace, resource, datasource, stream label,
PromQL, LogQL, TraceQL, selector prefix, or Grafana dashboard filter is rejected
unless it is a typed value matched by a server-owned template; none is authority.

The Forwarder accepts only registered operations and fixed native paths. A generic
Grafana user-query or dashboard endpoint is prohibited: a dashboard filter cannot
enforce rehearsal scope, source identity, or returned-record scope. Each operation
must build a bounded query from a server-owned template and trusted lease fields,
then validate every returned record against the same scope. A query that cannot
prove its scope is denied or returns an explicit unavailable/unknown result.

Registered scopes are fixed namespace/resource names and datasource identities.
There is no namespace enumeration, Secret read, ConfigMap write, `exec`, `attach`,
`portforward`, proxy, log-subresource, arbitrary discovery, or watch. Collection
reads may use at most two server-controlled pages with a server-issued continuation;
overflow becomes incomplete/unknown and never silently truncates. No operation
causes a follow-up query automatically; each operation is bounded to 30 seconds,
10,000 records, and 1 MiB, with at most 32 Eyes operations per Run, including
Ticket 35's separate five-query self-observation limit. Query time must be within
the current rehearsal and no more than 24 hours old; future time is rejected.
Query text is at most 8 KiB, parser depth 8, strings 2 KiB, arrays 256 items,
and each operation has a 30-second upstream timeout. Range steps are 1 second to
5 minutes and produce at most 3,600 samples per series; instant results are at
most 1,000 series; logs/events are at most 10,000 projected rows. These are
proposal bounds and remain ticket-36 acceptance inputs.

## Logical operation allowlist

These are semantic Eyes operations, not a public arbitrary HTTP proxy. All have a
fixed service, path, method, query-key set, response schema, byte/row/time bound,
and scope predicate. The exact native forms are source-backed where cited; the
adapter and intended venue still require acceptance.

| Operation | Fixed native form and purpose | Scope/result rule |
| --- | --- | --- |
| `pod_list` | `GET /api/v1/namespaces/{fixed_ns}/pods?labelSelector={fixed_workload_selector}&limit={server_limit}` | Only for a registered workload selector and verified owner UID. Return bounded Pod handles for subsequent `pod_status`; overflow or owner mismatch is incomplete/unknown. |
| `pod_status` | `GET /api/v1/namespaces/{fixed_ns}/pods/{fixed_name}` | Return only the bounded status projection for the registered Pod. Pod status is required for `OOMKilled`, restart count, conditions, UID, and container termination state; an Event absence cannot replace it. |
| `pod_events` | `GET /api/v1/namespaces/{fixed_ns}/events?fieldSelector=involvedObject.uid={registered_uid}&limit={server_limit}` | Read only events for the registered object UID and namespace. Event note/message is categorized or omitted; arbitrary text is never passed through. Query form and field-selector support require pinned Kubernetes-version verification. |
| `service_endpoints` | `GET /apis/discovery.k8s.io/v1/namespaces/{fixed_ns}/endpointslices?labelSelector=kubernetes.io/service-name={fixed_service}&limit={server_limit}` | Join at most the bounded page set, return readiness/port counts and safe target references, and mark incomplete on overflow. EndpointSlice is preferred; deprecated Endpoints is not a silent fallback. |
| `metrics_instant` | `GET /api/v1/query?query={server_template}&time={bounded_time}&timeout={bounded_timeout}&limit={server_limit}` | PromQL comes from fixed templates for application latency, application errors, request volume, or registered resource pressure. Returned series must satisfy trusted source scope; unknown labels or unbounded cardinality hold. |
| `metrics_range` | `GET /api/v1/query_range?query={server_template}&start={bounded_start}&end={bounded_end}&step={bounded_step}&timeout={bounded_timeout}` | Same template and returned-series checks; duration, step, samples, and response bytes are bounded. |
| `logs_range` | `GET /loki/api/v1/query_range?query={server_template}&start={bounded_start}&end={bounded_end}&limit={server_limit}&direction={forward\|backward}` | LogQL is server-generated. Validate fixed stream labels, source class, rehearsal, and record fields after the response; a dashboard filter is not authorization. |
| `traces_search` | `GET /api/search?q={server_traceql}&start={bounded_start}&end={bounded_end}&limit={server_limit}&spss={server_limit}` | Optional beta capability. TraceQL/tags are template-generated; returned trace/service attributes are allowlisted and scope-checked. Missing or ambiguous scope is unknown, not no evidence. |
| `trace_get` | `GET /api/traces/{admitted_trace_id}` or the pinned v2 equivalent | Only an ID returned by an admitted search may be fetched. Validate service identity and time scope; if the trace spans outside the query window, report that wider trace scope rather than silently rewriting it. Search alone is not citation evidence. |
| `grafana_health` | Fixed `GET` health/readiness route at the registered Grafana origin | Receiver/Forwarder readiness only. It does not grant datasource enumeration or Run query authority. Exact Grafana path and response schema remain a ticket-36 source/intended-venue gate. |

The Prometheus, Loki, Tempo, and EndpointSlice forms above follow their published
HTTP/API shapes as upstream forms. A deployment may put them behind Grafana's
datasource proxy at the proposed fixed prefix
`/api/datasources/proxy/uid/{pinned_uid}/{native_path}`. Runs never receive a
direct backend route. The pinned datasource UID, path mapping, response shape,
and native-client compatibility must be verified before the operation becomes
READY. No undocumented client fallback may broaden the route.

## Feed and scope separation

The adapter recognizes three source classes and never merges them by query result:

1. **System telemetry:** fixed Pod/status, Events, EndpointSlice, Prometheus
   application/resource templates, and optionally bounded Loki/Tempo service
   templates. Scope is the trusted namespace, workload/service, owner UID, and
   rehearsal time window; system series are not required to contain a
   `rehearsal_id`. Missing trusted scope is denied. This is never a generic
   cluster feed; direct access to an unscoped system-telemetry feed is denied.
2. **Run telemetry:** Ticket 35's trusted labels are exactly
   `service_namespace=maoi-run`, `service_name=receiver-projection`, and
   `feed=run`. A Run may read its own Run and earlier Runs in the same current
   rehearsal only, through the trusted lease, with at most five self-observation
   queries and the Ticket 35 age/row/byte/time bounds.
3. **Change telemetry:** Ticket 41's dedicated stream is exactly
   `service_namespace=maoi-change`, `service_name=change-coordinator`, and
   `feed=change`. It is read-only, current-rehearsal scoped, and requires trusted
   coordinator producer identity. It exposes bounded stage/evidence references,
   never coordinator control, private principal references, or journal bodies.

Run and Change identifiers are structured fields, not high-cardinality labels.
The Kubernetes Event stream's historical `service_name="unknown_service"` selector
is collision-prone; it may be used only by a fixed Event operation with required
object-UID/namespace fields and post-response validation. If those fields cannot
be proven, the result is unavailable rather than attributed to Kubernetes.

## Response sanitization

All responses are parsed strictly before projection: valid UTF-8 and JSON only,
no duplicate keys, finite numbers, unknown-shape rejection, depth/row/string/byte
limits, and explicit omission/loss records. No raw response is returned to a Run.

* **Pod:** retain UID, namespace/name references, phase, conditions, restart counts,
  bounded container state/reason/exit code, and observed timestamps. Drop `spec`
  by default; if a capability profile needs a safe field, allowlist it explicitly.
  Never retain `env`, `envFrom`, Secret references, tokens, mounted credentials,
  command arguments, or unbounded annotations.
* **Events:** retain type, reason, action/category, object UID, namespace, bounded
  timestamps/counts, and safe source identifiers. Drop free-form notes/messages or
  reduce them to fixed diagnostic categories.
* **EndpointSlice:** retain object UID, service identity, bounded port names/numbers,
  and endpoint readiness/serving/terminating counts. Do not expose addresses,
  topology, or arbitrary endpoint metadata unless a later profile proves need.
* **Prometheus/Loki/Tempo:** retain only registered metric names, dimensions,
  timestamps, numeric samples, fixed event fields, trace IDs, and bounded safe
  attributes. A registered application-log template may retain a bounded,
  redacted message/category, and a registered span template may retain status or
  event text, only after credential, account/personal identity, repository/private
  path, prompt, assistant/tool body, and raw API body removal. Redaction failure
  drops the content and emits a visible support gap; it never returns the raw
  value. `trace_get` additionally requires bounded span IDs, start/end times,
  service identity, status, and allowlisted event attributes; a search result
  alone is not citation evidence. Unknown fields remain omitted.

Sanitization occurs at the Receiver/Forwarder boundary. Grafana filters, Loki
selectors, RBAC role names, and dashboard configuration are not privacy or scope
boundaries. Failure to sanitize or validate holds the affected operation.

## Readiness, effects, and failure

Each service route is `UNAVAILABLE`, `PREFLIGHTED`, `READY`, `REVOKING`, or
`REVOKED`. Mandatory Grafana/Kubernetes/Forwarder/control/TLS routes must be READY
before new Runs; a telemetry export or optional trace capability remains best
effort and cannot discard Notifications or block safe OPS recovery. Revocation at
exit, cancellation, deadline, or restart denies new dispatch immediately; an
in-flight read remains explicitly unknown until reconciled. No query timeout,
truncation, backend error, or missing record is presented as zero, success, or
absence of a Fault.

Eyes query failure does not undo confirmed OPS work, reopen an Incident, or trigger
an automatic model retry. A Change journal/stream failure preserves its private
record and marks retrieval unavailable. A system read failure marks the affected
observation unknown. Ticket 21/37 owns terminal classification, effect receipts,
and recovery; Eyes cannot create or settle external effects.

## Acceptance and evidence boundary

Offline acceptance must drive the real selected client or standard-library adapter,
Forwarder request builder, parser, sanitizer, lease checks, and bounded synthetic
backends. It must cover forged/wrong/revoked sentinels, direct backend access,
caller-selected origin/path, arbitrary PromQL/LogQL/TraceQL, dashboard-filter scope
bypass, cross-namespace/resource/rehearsal reads, Pod `env` leakage, Event collision,
EndpointSlice overflow, query bounds, malformed/oversized responses, restart/expiry,
unknown backend results, and Change/Run/system feed confusion.

Ticket 19 Stage A's 31 supported synthetic assertions remain transport evidence only;
its native client is not a client-selection decision. Stage B/C2 and historical
Compose probes do not prove native venue, tenant RBAC, Grafana datasource policy,
Kubernetes grants, Tempo capability, client model behavior, or production privacy.
The later venue gate must verify the chosen client, Forwarder TLS and sentinels,
Grafana anonymous-off/service-account custody, fixed datasource routes, Kubernetes
read grants, native response shapes, and actual scope enforcement. Until then each
unverified operation stays unavailable.

## Sources and unresolved choices

* [Ticket 12](../../issues/12-eyes.md), [ADR 0010](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md),
  [ADR 0011](../../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md),
  [ADR 0015](../../../../docs/adr/0015-changes-record-operator-actions-and-observed-stages.md).
* [Ticket 19 facts](../ticket-19/facts.md), [Stage A verdict](../ticket-19/stage-a-verdict.md),
  and [Stage B readiness](../ticket-19/stage-b-readiness.md): source/synthetic boundaries only.
* [Ticket 35](../ticket-35/telemetry-specification.md), [Ticket 41](../ticket-41/change-specification.md),
  [Ticket 43](../ticket-43/confluence-specification.md), and [Ticket 36](../ticket-36/contract-draft.md).
* [Kubernetes API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/),
  [EndpointSlice API](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/),
  [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/),
  [Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/), and
  [Tempo HTTP API](https://grafana.com/docs/tempo/latest/api_docs/).

The exact Grafana health/datasource proxy path, Kubernetes Event field-selector
support in the pinned cluster version, selected client, operation-template registry,
resource names, response schemas, and intended-venue grants remain gates. This
proposal makes no runtime, native, tenant, model, paid, or publication claim.
