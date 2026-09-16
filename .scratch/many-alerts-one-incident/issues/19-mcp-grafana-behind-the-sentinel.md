# mcp-grafana behind the sentinel

Type: prototype
Status: open
Blocked by: none

## Question

Run `mcp-grafana` as a stdio MCP server inside a copy of the chapter-one image, read-only (`--disable-write --enabled-tools ...`), pointed at the Forwarder with a sentinel as its token, against an `otel-lgtm` with anonymous access off and a Viewer service account, and drive a print-mode Run against it with the allow list naming its tools. Answer what only running it can: do its tool names read well in the log window; do the output cap and the Loki line default fit a five-minute Run; what does the MCP startup wait cost; does the Forwarder's Bearer swap work unchanged; and what does `docker diff` and the denial line show. Compare against a stub of the `eyes` CLI on the same questions if time allows. The throwaway lives on a `prototype/mcp-grafana-eyes` branch.
