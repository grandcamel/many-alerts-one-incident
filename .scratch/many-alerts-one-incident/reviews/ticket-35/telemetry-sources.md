# Ticket 35 source map

This is source/planning evidence only. No model, credential, account, cluster,
native exporter, or provider call was made. Historical Compose probes in ticket
15 remain historical and are not venue acceptance.

## Official Claude Code documentation

- [Claude Code monitoring](https://code.claude.com/docs/en/monitoring-usage) documents opt-in OTel metrics and logs/events, optional beta traces, OTLP exporter configuration, standard/resource attributes, event correlation fields, metric temporality, content gates, and service metadata. It documents `session.id`, `prompt.id`, `event.sequence`, `message.uuid`, `request_id`, `tool_use_id`, and `client_request_id` as version-qualified fields; it does not promise that these form a permanent internal Transcript API. It states that Transcript joins are version-specific and may break between releases.
- Native subprocess inheritance of exporter configuration has not been verified. The monitoring page's script-requirements section concerns the dynamic header helper; it does not support a blanket claim that all `OTEL_*` variables are stripped. The proposed launcher must enforce child-environment isolation explicitly and verify it at the installed-client boundary.
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars) documents `CLAUDE_CODE_ENABLE_TELEMETRY`, standard OTEL variables, exporter endpoints/protocols/headers, and the startup-only behavior of monitoring settings. It documents `ANTHROPIC_BASE_URL` separately from telemetry routing; it is not evidence of a Receiver Run join.
- [Claude Code corporate proxy](https://docs.anthropic.com/en/docs/claude-code/corporate-proxy) documents proxy and certificate configuration, including `NODE_EXTRA_CA_CERTS`; it does not establish this repository's collector trust or native telemetry acceptance.

Relevant documented privacy facts: user/account/org attributes can be exported;
prompt, assistant, tool-detail, tool-content, and raw API-body flags exist and
can reveal sensitive content. The specification therefore requires explicit
allowlisting and collector sanitization. Defaults are not treated as a privacy
boundary. The docs do not document a lossless sanitized Transcript exporter, a
stable version-independent event schema, a Notification/Incident association,
or a physical 24-hour deletion guarantee.

## OTLP and Loki references

- The repository's cross-ticket findings and trusted Run/Change label boundary are recorded in [telemetry-change-reference-integration.md](../telemetry-change-reference-integration.md). It links the same primary Grafana sources and must be kept aligned with this contract.
- [Grafana Loki OTLP ingestion](https://grafana.com/docs/loki/latest/send-data/otel/) is the primary source for structured metadata, default label mapping, cardinality, and attribute-drop controls.
- [Grafana Loki retention](https://grafana.com/docs/loki/latest/operations/storage/retention/) is the primary source for Compactor/index requirements, asynchronous deletion, and non-retroactive policy changes. Query-age enforcement and physical deletion/read-back remain separate gates.
- [OpenTelemetry metrics data model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/) documents delta/cumulative temporality, start timestamps, reset/gap interpretation, and why overlapping streams must not be summed without a valid temporality boundary.

## Repository source boundaries

- [ADR 0010](../../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md) settles the Receiver Run identity, explicit native mapping, dedicated namespace, zero/one/many associations, sanitized allowlist, bounded best-effort delivery, visible gaps, 24-hour shared retention, and separation from ticket-24 citation audit.
- [ADR 0018](../../../../docs/adr/0018-audience-memory-view-preserves-source-and-review-state.md) settles sanitized operator projection, provenance, stale/unknown/unavailable distinction, and no raw telemetry/audit exposure.
- [Ticket 15 facts](../ticket-15/facts.md), [round 1](../ticket-15/round-1.md), and [round 2](../ticket-15/round-2.md) establish current-source absence of an implemented shared exporter and preserve historical exporter probes as non-acceptance evidence.
- [Ticket 37 recovery specification](../ticket-37/recovery-specification.md) owns execution/effect state and recovery IDs; [ticket 39 audit specification](../ticket-39/audit-specification.md) owns private citation evidence. This feed may reference their identities and gaps only.
