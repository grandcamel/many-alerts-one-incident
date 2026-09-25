# Ticket 35 sanitized Run telemetry specification

**Status:** proposed planning contract, 2026-09-22. This document specifies the
ADR 0010 integration and offline acceptance boundaries. It changes no Receiver,
spawner, collector, Loki, Claude Code, dashboard, venue, or retention system;
it authorizes no model Run, credential use, cluster export, tenant operation, or
publication. A field name below is a proposed interface until implemented and
verified at the stated boundary.

Settled policy is carried from ADR 0010/0018 and ticket 15. Ticket 24/39 owns
the private citation-audit bundle; shared telemetry is a bounded diagnostic
projection and never a complete Transcript or semantic grade. Ticket 21 owns
execution terminal classification and retry mechanics. Ticket 37 owns durable
admission/effect recovery; this feed may reference its IDs but cannot replace
its journal or prove an external effect.

## Capability and authority boundary

The current official Claude Code documentation describes opt-in OpenTelemetry
metrics and logs/events, with optional beta traces, and documents OTLP exporters,
resource attributes, event fields, and content gates. It does not establish the
installed CLI version, the planned venue's exporter behavior, a stable internal
Transcript schema, or a Receiver Run-ID join. The documentation says transcript
joins are version-specific and may break between releases. Historical Compose
probes are retained as historical evidence only.

Native export is **disabled by default** until a pinned Claude Code version,
collector configuration, privacy test, and intended-venue delivery/temporality
acceptance are all approved. The native path may be enabled only through an
allowlisting collector boundary. Unsupported or unknown native fields are
omitted with a visible loss marker; they are never passed through unfiltered.
If the collector cannot prove this, the affected native feed stays disabled.

The Receiver projection is the canonical Run telemetry source. Its current
journaled front door commits a **Notification** admission only: its receipt has
an admission ID, but no Run ID, rehearsal ID or telemetry generation. A separate
trusted handoff must bind that admission to a validated rehearsal and either a
Receiver-owned Run ID or an explicit unassigned state before a shared record is
staged. Journal generation is not telemetry generation, and the legacy
one-notification/one-Run launcher is not that handoff. Once the handoff exists,
the projection allocates its own `projection_generation`; each process then
uses an in-memory monotonic `projection_seq` and `projected_event_id` before
enqueueing. A rehearsal-unbound receipt remains durable journal evidence, not
a Run telemetry event or an exportable record. A rehearsal-bound Notification
with no Run can retain `run_id=null` only under a separately specified
operator-only read scope; it is excluded from every Run read and must not be
silently assigned to a Run.
No per-event disk write or persistent telemetry spool is required. A restart
allocates a new generation and emits an explicit gap before another event. A native
`session.id` is mapped to the Receiver `run_id` only by an explicit mapping
record; equality is never assumed. One Run may have zero, one, or several native
session IDs (for example after a documented session reset). Native identity is
the pair `(producer_instance_id, native_session_id)` so a supervised restart
cannot collide with a prior process, and a native session may never silently map
to two Runs. Conflicts become `mapping_conflict` and hold
the affected native projection.

## Feed, namespace, and identity

Every projected record has this envelope:

```json
{
  "schema_version": 1,
  "feed": "run_events|run_metrics|run_gaps|session_map",
  "projected_event_id": "sha256-or-opaque-stable-id",
  "run_id": "receiver-run-id-or-null",
  "rehearsal_id": "rehearsal-id",
  "producer_instance_id": "supervisor-instance-id-or-null",
  "native_session_id": "opaque-or-null",
  "projection_generation": "admission-generation",
  "projection_seq": 0,
  "event_kind": "allowlisted-kind",
  "source": {"class": "receiver|native_otel|metric_derivative", "version": "..."},
  "observed_at": "UTC-or-null",
  "ingested_at": "UTC",
  "associations": null,
  "payload": {},
  "loss": []
}
```

The example is schematic. Strict v1 parsing rejects unknown versions, unknown
fields/enums, duplicate JSON keys, conflicting duplicate identities, non-finite numbers, invalid UTF-8 or
timestamps, nesting deeper than 8, records over 64 KiB, strings over 2 KiB,
arrays over 256 items, or metadata over 16 KiB. `run_id`, `rehearsal_id`, native
IDs, Notification IDs, Incident keys, and source references are opaque bounded
identifiers; none is a credential or account identity.

The trusted Run feed labels are exactly `service_namespace=maoi-run`,
`service_name=receiver-projection`, and `feed=run`; native and gap records stay
within that feed and use structured `source_class`/`event_kind` fields. No
deployment or identity label is added by default; `run_id`, `rehearsal_id`, native session IDs, Notification IDs,
Incident keys, prompt IDs, and request IDs are structured metadata or event body
fields, never labels or metric dimensions. User, account, personal-identity,
and repository values are dropped entirely, never retained as metadata or body
fields.
The collector/Loki configuration must explicitly drop default high-cardinality
resource labels such as `service.instance.id` and `k8s.pod.name`.

## Event and metric allowlists

`run_events` accepts only these projected event kinds:

| Kind | Required payload | Source authority |
| --- | --- | --- |
| `run_started` / `run_finished` | lifecycle state, monotonic elapsed ms, terminal classification or unknown | Receiver / ticket 21 |
| `api_request` | model label, request outcome, duration, retry count, usage state, usage reference | Native event or Receiver terminal, never both for one displayed measure |
| `api_error` / `api_refusal` | bounded error category, HTTP status when present, retry state | Native event, sanitized category only |
| `tool_result` | bounded tool category, success state, duration, tool-call reference | Receiver/native allowlist |
| `notification_admitted` | admission ID, source-group reference, admission state and explicit Run/unassigned binding | Receiver / ticket 37 after trusted rehearsal binding; unassigned is operator-only |
| `incident_touched` | Incident key, observed operation/effect state | Receiver / ticket 37; not candidate-read evidence |
| `usage_observed` | measure ID, scope, coverage, units, value or `unknown`, source reference | One selected usage source |

`telemetry_omitted` and `telemetry_gap` use the envelope's `run_gaps` feed,
not `run_events`; they retain the same trusted shared-stream label `feed=run`
at the collector boundary. The [35a local grammar](design-35a-receiver-gap-codec.md)
pins only a Receiver-origin synthetic subset. Native, queue and transport
gap emitters remain separate unimplemented profiles.

| Gap kind (`run_gaps`) | Required payload | Source authority |
| --- | --- | --- |
| `telemetry_omitted` / `telemetry_gap` | loss code, count, first/last time, affected sequence range | Projection/transport |

The payload never contains prompt text, assistant text, commands, arguments,
tool output, raw API bodies, credentials, sentinels, account/personal identity,
repository URLs, private paths, Ground truth, adjudication rationale, or raw
errors. A safe diagnostic summary is a fixed category token plus bounded counts;
free text is not accepted in v1. Unknown native event shapes create an omission
record with constant `unknown_native_shape` category, validated source version,
sequence range and a digest of the normalized shape/schema only; it never echoes
an arbitrary event name, key, or unknown value.

`run_metrics` is an aggregate diagnostic feed, not per-Run accounting. Its
metric-name enum is exactly `session_count`, `api_request_count`,
`tool_result_count`, `cost_usage_usd_micros`, `token_input`, `token_output`,
`token_cache_read`, `token_cache_creation`, or `active_time_ms`; its unit enum
is `count`, `usd_micros`, `tokens`, or `milliseconds`. It accepts numeric value,
start/end timestamps, temporality, source version, and only these dimensions:
`model_class`, `outcome_class`, `query_source_class`, `usage_type`, and
`tool_class`. It must preserve OTLP
delta/cumulative temporality and start time; after restart, reset or a gap it
emits `metric_gap` rather than adding values across an unknown boundary. Native
cost/token metrics and `api_request` usage are never summed together.

The per-Run dashboard chooses one source for every displayed measure. A measure
has `scope=api_request|full_run` and `coverage=complete|partial|unknown`.
Receiver terminal usage/outcome wins only when it is complete; otherwise a
correlated native API event may supply an `api_request` measure. A `full_run`
measure is complete only from a complete terminal record or complete correlated
coverage of every request in the Run. One request cannot stand in for full-Run
usage. Aggregate metrics cannot fill a per-Run measure. The selected source
reference, selection reason, completeness and loss state are displayed. `0` is
valid only when the selected source explicitly reports zero; absent, omitted,
dropped, partial, or conflicting usage remains unknown/incomplete.

`projected_event_id` is stable across retry: for Receiver records it derives from
`(run_id, projection_generation, projection_seq, event_kind, source_record_id)`; for native records it
derives from the producer instance, source version/session/sequence plus canonical allowlisted
payload. A retry with the same identity/digest is idempotent; a conflicting
digest is a visible conflict. `event.sequence`, `message.uuid`, `request_id`,
`tool_use_id`, and `client_request_id` are retained only as version-qualified
source references and never treated as universal identity.

## Correlation and associations

The `session_map` record contains `run_id`, `rehearsal_id`, producer instance,
native session ID, mapping status (`explicit`, `unknown`, `conflict`, `expired`), source/version,
observed/ingested times, and a bounded evidence reference. Missing native IDs
are explicit unknown. A resumed or reset native process does not cause a new
Receiver Run join without Receiver evidence.

Receiver lifecycle/association records carry `associations` with
`notifications` and `incidents`, each `{state: known|none|unknown, ids: [],
overflow_count}`. IDs are capped at 256; overflow sets a nonzero count and
`state=unknown` (or retains `known` only when the complete set is proven), so
truncation is never silent. Native-only records may set associations to null and
must link through the Receiver mapping before appearing in a Run view. Empty
known arrays mean observed zero; unknown means the association query was
unavailable or incomplete. The durable Receiver journal records every admitted
Notification. Its telemetry projection may represent each one only after a
trusted rehearsal binding, with the Run association explicitly known or
unassigned; until then it remains unexported. The projection also records every
touched Incident once its effect owner supplies the verified association,
including many-to-one and one-to-many relationships. A
candidate read or asserted Match is not an Incident association.

Ticket-37 `attempt_id`, `operation_id`, `intent_id`, `effect_id`, and recovery
state may appear as opaque references. Telemetry never stores mutation payloads,
claims effect confirmation, or substitutes for Forwarder receipt/read-back.
Ticket 39 `audit_bundle_id`/`evidence_id` may appear only as sanitized gap or
provenance references; no audit body, Ground truth, or adjudication enters this
feed.

## Sanitization, transport, and native exporter gate

The Receiver sanitizer runs before the collector enqueue boundary. It accepts
only the envelope and allowlisted payload; it deletes identity/content fields
and fails closed on malformed or unsupported shapes. Collector transforms apply
the same allowlist to native OTLP resource, scope, log, metric and body fields.
No downstream Loki/Grafana filter is the privacy boundary.

Native configuration must keep prompt/assistant/tool-detail/tool-content/raw-API
body gates disabled, disable account/repository metric attributes, and reject
arbitrary resource attributes. The official docs state that account/email/org
attributes may be present and that raw API-body and tool-content flags can emit
sensitive data; their defaults are not treated as a privacy proof. Native
subprocess environment inheritance is not verified here. The launcher must
explicitly remove exporter destinations, authorization headers and other
monitoring configuration from child environments unless separately approved
and tested; it must not rely on an assumed native stripping behavior.
Subprocess telemetry is a separate, disabled-by-default source.

Use OTLP logs through an approved collector; metrics use the configured metrics
path and are not converted into event bodies. No persistent telemetry spool is
introduced by this specification. Authentication material belongs in the
collector/forwarder configuration and is excluded from records and diagnostics.

Proposed queue bounds are 4,096 records / 32 MiB globally and 512 records / 4 MiB
per Run, with one reserved loss-marker slot per scope. A send batch is at most
256 records / 1 MiB; each batch gets one initial attempt and at most two retries,
with a 5-second per-attempt deadline. Backoff is bounded and never blocks
Notification admission or Incident recovery. On saturation, drop oldest queued
records, increment a coalesced loss marker, and preserve its count, time range,
sequence range and reason. When the loss-marker budget saturates, emit one
terminal `loss_overflow` marker and mark the feed incomplete; never silently
claim delivery. No persistent spool means restart or process kill makes
unconfirmed records `delivery_unknown`, not delivered or absent.
These bounds apply only after the trusted rehearsal/Run handoff. A queue over
the current unbound admission receipts could be an internal best-effort staging
experiment, but cannot issue a Run event or the 35a per-Run gap record; that
codec requires a validated Run and rehearsal ID. No such queue is installed by
this specification.

Exact retry duplicates with the same `projected_event_id` and digest are accepted
idempotently by a bounded transport/query dedup layer; conflicting duplicates
are rejected and visible. The query layer must deduplicate by ID within each
bounded result and expose late arrival, duplicate conflict, rejected payload,
and dropped records. It cannot assume Loki or another backend deduplicates.
A source sequence gap is retained even if a later event arrives. Delivery
success does not change Ticket 21 terminal classification or Ticket 37 effect state.

## Read scope, retention, and presentation

Eyes/Forwarder enforces query authorization: a Run may read only its own Run and
earlier Runs in the same current `rehearsal_id`, through bounded read APIs. A
trusted lease binds the caller to its admitted Run, rehearsal and maximum
admission sequence; caller-supplied IDs are selectors, not authority. Cross-rehearsal,
system-telemetry, raw-audit, Ground-truth, and audience-review paths are denied
at the boundary. Proposed query bounds are 10,000 records, 1 MiB, 30 seconds,
one continuation token, and at most **five self-observation queries per Run**.
There is no automatic recursive query triggered by telemetry output; further
queries require a new bounded admitted operation.

The accepted shared Run-telemetry retention is 24 hours. Enforce query age and
rehearsal scope immediately in the access layer. Physical Loki deletion is a
separate backend acceptance: it requires pinned version/configuration, 24-hour
index compatibility, enabled compactor/delete processing, and read-back that
proves policy behavior. Asynchronous compaction/sweeper delay means a 24-hour
policy does not prove bytes disappeared at exactly 24 hours. This feed's cleanup
must not delete system telemetry, OPS history, Confluence history, or ticket-39
private evidence.

The audience projection shows a compact per-Run activity, elapsed time, selected
usage, terminal classification, and linked sanitized timeline. It displays
source class, event/observation time, mapping state, late/dropped/unknown gaps,
and zero/one/many Notification/Incident links. It never shows raw content,
credentials, account identity, Ground truth, scoring feedback, or a claim that
telemetry proves diagnosis. Refresh/stale states follow ADR 0018 and do not alter
backend timestamps or retention.

## Offline acceptance matrix and later gates

Tests must drive the actual Receiver projection, sanitizer, transport adapter,
collector boundary, and query authorization seams with bounded synthetic data.
They must assert exact records, omissions, identities and states; they do not
qualify a model, venue, tenant, or human diagnosis.

| Family | Required cases and expected result |
| --- | --- |
| Schema/privacy | valid allowlisted records; unknown version/shape; wrong types; duplicate/conflicting IDs; oversized/deep/nonfinite input; every prohibited field; raw-body/content flags; fail closed with omission/loss marker |
| Mapping/correlation | explicit mapping; missing/reset/multiple native sessions; conflict; Receiver Run canonical; stable retry ID; sequence gaps; timestamp ties; zero/one/many Notifications and Incidents; candidate read not association |
| Usage | Receiver and native usage; selected-source precedence; zero vs missing vs unknown; event/metric overlap; delta/cumulative reset and restart; conflicting values never summed |
| Queue/transport | per-Run/global byte and event caps; batch send/retry budget; drop-oldest; reserved loss marker; collector outage/rejection; duplicate retry; late delivery; restart/SIGKILL unknown delivery; OPS continues |
| Access/retention | current-rehearsal self/earlier read; cross-rehearsal/system/audit denial; query bounds; 24-hour age denial; backend deletion/read-back separately; system telemetry unaffected |
| Presentation | per-Run and linked timeline; source attribution; stale/unknown/incomplete terminal state; many associations; no raw or semantic-success promotion |

Separate acceptance is required for pinned Claude Code exporter/version/privacy
capabilities, intended OTLP/Loki venue, cumulative temporality and backend
retention, native-to-Receiver mapping, and ADR 0018 audience behavior. No current
installed-client proof, native exporter proof, model-quality evidence, live
tenant/RBAC evidence, billing evidence, or publication is claimed here.

## Sources and unresolved choices

Primary public sources and their bounded claims are listed in
`telemetry-sources.md`. Proposed choices still needing implementation pinning
include exact record limits, collector processor syntax, backend tenant/ACL
configuration, loss-code registry, and native field inventory for the selected
Claude Code version. They cannot weaken the settled privacy, correlation,
best-effort, access, 24-hour, or source-attribution rules.
