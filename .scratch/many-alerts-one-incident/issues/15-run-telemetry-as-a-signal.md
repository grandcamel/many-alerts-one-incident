# Run telemetry as a signal

Type: grilling
Status: open
Blocked by: 02

## Question

Which of the harness's exports and which Transcript Run events go into the LGTM stack, and how are they labelled so they can be told apart from the system's own telemetry? May a Run read its own telemetry, or an earlier Run's? What does the audience see of a Run observing itself, and is that a dashboard, a log window, or both?

The research settled the mechanics: the export is enabled per Run from the Receiver's environment, `session_id` is the join key across Transcript, export and Incident, cumulative temporality is required for the stack's Prometheus, and identity attributes (`user.email`, `organization.id`, account id) ride on every record unless a collector processor drops them. This ticket decides: whether the Transcript is shipped by the Receiver as OTLP log records or by a shipper; whether identity is dropped or a demo account accepted; whether beta traces are in the demo; and what the audience sees.
