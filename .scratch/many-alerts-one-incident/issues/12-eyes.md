# Eyes

Type: grilling
Status: open
Blocked by: 03, 09, 17, 19

## Question

Which tools may a Run execute to read telemetry, and what does the allow list say? How does the sentinel pattern extend to a Grafana service account? The Forwarder's shape itself (one or one per site, and what it speaks on loopback) is decided in "The Forwarder's growth"; this ticket takes that answer as given. Is read-only `kubectl` an Eye when the cluster is real, and how is its credential held so the Run never sees it? What changes in Grafana: anonymous access off, a Viewer service account minted at startup, Loki, Tempo and Prometheus bound to loopback so that Grafana is the only door (the research found all three answer the demo container with no credential today). Whether the tool is `mcp-grafana` or a standard-library `eyes` CLI, decided on what the prototype "mcp-grafana behind the sentinel" showed and what the allow list and the Skill can say plainly. Produces an ADR extending ADRs 0002 and 0003.
