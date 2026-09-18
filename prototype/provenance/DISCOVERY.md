# Pinned client discovery — Stage A

Release v1.5.1 (published 2026-09-17), source `2a33c72f211560e4ffb39d6b99cad3c3dc2a3f6e`. Downloaded Darwin x86_64 archive matched its published SHA-256. The binary reports `1.5.1`. See `manifest.json`, captured help, checksum list and Apache-2.0 LICENSE. Matching the publisher checksum is integrity evidence, not independent supply-chain attestation. No container image was used.

Captured source references (paths below are relative to `prototype/provenance/source/`):

- `mcpgrafana.go:42` names `GRAFANA_SERVICE_ACCOUNT_TOKEN`; `mcpgrafana.go:709` constructs its Bearer header. Fixture sentinel substitution must be measured through this native path.
- `cmd/mcp-grafana/main.go:311` exposes `--tls-ca-file`. `mcpgrafana.go:476`–505 constructs TLS settings and loads the supplied CA pool; skip verification defaults false and is not enabled by this experiment.
- `cmd/mcp-grafana/main.go:1142` exposes `--usage-stats`; this experiment explicitly disables reporting and supplies a minimal subprocess environment. This is configuration evidence, not packet-capture proof of network isolation.
- `tools/http_redirect.go:26`–44 allows method-preserving redirects. The helper name does not imply unconditional rejection. The prototype Forwarder must reject upstream 3xx itself.
- `tools/loki.go:24` defaults to ten log lines. `tools/loki.go:543`–562 enforces the configurable maximum. `tools/loki.go:899`–919 constructs line count and truncation metadata. Native output measurements determine what the exercised fixture actually receives.

This discovery does not establish transport acceptance, general query authorization, real Grafana compatibility, model usability, container confinement or intended-venue readiness. Those claims require their own evidence.

To reproduce the pinned binary download, run `python3 prototype/provenance/fetch_client.py`. It verifies both captured SHA-256 values before writing the binary to `/tmp/maoi-mcp-client/mcp-grafana`. The runner must separately verify that binary before execution. The public download requires network; the fixture run uses local endpoints only.
