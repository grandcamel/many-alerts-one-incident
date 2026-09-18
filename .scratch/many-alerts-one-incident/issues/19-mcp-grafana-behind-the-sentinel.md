# mcp-grafana behind the sentinel

Type: prototype
Status: claimed
Blocked by: none

## Question

Run `mcp-grafana` as a stdio MCP server inside a copy of the chapter-one image, read-only (`--disable-write --enabled-tools ...`), pointed at the Forwarder with a sentinel as its token, against an `otel-lgtm` with anonymous access off and a Viewer service account, and drive a print-mode Run against it with the allow list naming its tools. Answer what only running it can: do its tool names read well in the log window; do the output cap and the Loki line default fit a five-minute Run; what does the MCP startup wait cost; does the Forwarder's Bearer swap work unchanged; and what does `docker diff` and the denial line show. Compare against a stub of the `eyes` CLI on the same questions if time allows. The throwaway lives on a `prototype/mcp-grafana-eyes` branch.

## Input from ticket 17

[ADR 0011](../../../docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md) settles loopback HTTPS with trusted deployment-local CA, a Grafana-specific sentinel, fixed upstream destination and request-aware read/rehearsal scope. The prototype must test client trust and these boundaries rather than assume the old HTTP Basic-auth Forwarder works unchanged. This planning update does not authorize running the prototype.

## Work in progress

Claimed for offline experiment preparation after ticket 17 was resolved. The current session does not execute the model/container prototype. Preserve an explicit NOT RUN result; preparation cannot resolve this measurement ticket or unblock Eyes.

An [experiment protocol](../reviews/ticket-19/experiment-plan.md) now separates real-client transport checks from a later bounded model experiment and defines evidence/decision rules. All execution remains NOT RUN. It requires only an isolated ADR 0011 Grafana subset, not completion of ticket 36, avoiding a dependency cycle through Eyes.

The [offline fact sheet](../reviews/ticket-19/facts.md) resolves historical token-variable naming as a configuration bridge and confirms that the referenced research did not execute mcp-grafana. It therefore provides no measured startup, tool-output or TLS/sentinel compatibility verdict. Ticket 19 stays claimed and unresolved; ticket 12 stays blocked on the actual prototype.
