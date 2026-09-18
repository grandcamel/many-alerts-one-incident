# Run telemetry integration and acceptance

Type: task
Status: open
Blocked by: 12, 15, 17, 21

## Question

Produce an implementation-ready specification for [ADR 0010](../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md), not runtime changes or a live rollout. Specify the sanitized event schema, Receiver Run/native session mapping, Notification/Incident associations, stable projected-event identities, source attribution and one source per displayed usage measure. Choose precise namespace/feed fields, structured metadata and bounded metric dimensions.

Define per-feed field allowlists and identity/content removal before ingestion, source-reference handling, unknown-shape omission markers and current-rehearsal access enforcement. Native export must meet the same privacy policy as the Receiver projection; unsupported fields are omitted or the affected feed disabled, never passed through unfiltered. Verify version-specific capabilities using the required claude-api skill and primary documentation; the historical Compose exporter probes do not prove the planned venue. Verify cumulative temporality/metric compatibility on that venue rather than treating the old loss result as current.

Set queue byte/event limits and send budgets, drop-oldest/loss visibility, retry deduplication, restart/unknown-delivery behavior, and enforcement of the accepted 24-hour Run-telemetry retention without deleting system telemetry. Derive the per-Run dashboard and linked sanitized timeline from explicit source attribution; show unknown/missing usage and outcomes, applying ticket 21's classification.

Specify offline tests at actual Receiver/projection/transport/query boundaries for redaction, omitted shapes, cross-rehearsal access, identity mapping, zero/multiple Incident links, overload, collector outage, duplicates, delayed arrival and restart. Compare metrics and events without double-counting. Separately list required model/exporter, intended-venue, retention and audience acceptance. Ticket 24 owns full citation-audit evidence; a sanitized timeline must not be presented as a complete Transcript.

## Inputs

[Ticket 15](15-run-telemetry-as-a-signal.md#answer), [accepted rounds and facts](../reviews/ticket-15/facts.md), and tickets 12, 17, 21 and 24. No model Run, cluster, demo or live export is authorized by this specification ticket.
