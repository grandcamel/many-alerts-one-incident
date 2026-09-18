# Run telemetry as a signal

Type: grilling
Status: resolved
Blocked by: 02

## Question

Which of the harness's exports and which Transcript Run events go into the LGTM stack, and how are they labelled so they can be told apart from the system's own telemetry? May a Run read its own telemetry, or an earlier Run's? What does the audience see of a Run observing itself, and is that a dashboard, a log window, or both?

Historical research reported the following mechanics (the source/venue limits are corrected in the Answer below): the export is enabled per Run from the Receiver's environment, `session_id` is the join key across Transcript, export and Incident, cumulative temporality is required for the stack's Prometheus, and identity attributes (`user.email`, `organization.id`, account id) ride on every record unless a collector processor drops them. This ticket decides: whether the Transcript is shipped by the Receiver as OTLP log records or by a shipper; whether identity is dropped or a demo account accepted; whether beta traces are in the demo; and what the audience sees.

## Work history

Claimed for offline planning after ticket 13 was resolved. Verify historical research against committed source before the human decision round. No model Run, cluster, demo, or live telemetry export is authorized.

The human accepted all six recommendations in the first [decision round](../reviews/ticket-15/round-1.md). Historical research is retained with [provenance](../reviews/ticket-15/provenance.md); fresh exporter/model compatibility is not asserted.

[Offline fact check](../reviews/ticket-15/facts.md): current source renders a lossy, redacted Transcript projection into container logs; shared session correlation and Transcript export are not implemented. The old Compose temporality probe is not planned-venue acceptance (map line 63). No new model/exporter capability is asserted.

The human accepted the second [decision round](../reviews/ticket-15/round-2.md), covering correlation authority, telemetry separation/access, sanitized event contents, retention/overload behavior, and honest delivery/usage presentation. Both policy rounds are accepted.

## Answer

[ADR 0010](../../../docs/adr/0010-run-telemetry-is-sanitized-correlated-and-best-effort.md) records the eleven accepted choices. Operational metrics/events and a Receiver-shipped sanitized structured Transcript projection are required; beta traces are outside the required demo path. Receiver Run ID is canonical, with explicit native session mapping and zero/one/many Notification/Incident associations. Dedicated namespace/feed origin separates Run telemetry; individual identities stay in log metadata, not per-Run metric dimensions or index labels.

Runs may inspect execution telemetry from their current rehearsal for tool/transport problems, but their statements are not independent system evidence. Identity, credentials, raw prompts and unfiltered content are excluded before ingestion. The audience gets a compact per-Run dashboard and sanitized event timeline with provenance and omissions.

Delivery is bounded best effort: in-memory queue, drop oldest on overload, visible loss, no persistent spool, unknown unconfirmed delivery after restart. Run telemetry has 24-hour retention with current-rehearsal read scope. Stable projected-event identities deduplicate retries; late arrivals/gaps remain visible; overlapping export/Transcript usage is not summed. Missing final usage/outcome is unknown. Ticket 21 owns terminal success/failure classification.

Current source does not implement Transcript export or shared Receiver/session correlation. The earlier Compose Prometheus temporality result is not acceptance for the intended venue; [facts](../reviews/ticket-15/facts.md) and [provenance](../reviews/ticket-15/provenance.md) preserve that distinction. The referenced claude-api skill was not found in the searched roots, so no fresh model/flag/exporter compatibility claim is made.

[Ticket 35](35-run-telemetry-integration-and-acceptance.md) carries the integration specification and acceptance work. Tickets 12/17 own access enforcement and ticket 24 owns full citation-audit evidence. No runtime/Skill implementation, new model Run, cluster, demo or live export was performed.
