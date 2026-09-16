# How a Run could see telemetry

Type: research
Status: resolved
Resolved: 2026-09-15, by a research subagent
Blocked by: none

## Question

Which read-only, shell-executable tools could a Run use to query Grafana, Loki, Tempo and Mimir, and what would each need to authenticate? Compare, with a one-line example invocation for each (the allow list denies a command split across lines, see `skill/incident-sync/SKILL.md`):

- The Grafana HTTP API and its datasource query endpoints, with a service account token, from a container that has no `curl` (ADR 0005) but has Python and Node.
- `logcli` for Loki, `tempo-cli` or the Tempo HTTP API for traces, `promtool` or `mimirtool` or the Prometheus HTTP API for metrics.
- Grafana's own `mcp-grafana`: its tool list, its auth, whether it runs as a stdio MCP server inside a container, and what an allow list would say about a Run that talks to it.

Also: whether anonymous access can be turned off in the `grafana/otel-lgtm` image and a service account with a token provisioned at startup; what Grafana's Viewer role can and cannot query; and whether datasource proxy queries need more than Viewer.

Primary sources: grafana.com docs for the HTTP API, service accounts and roles, Loki, Tempo and Mimir CLIs, the `grafana/mcp-grafana` repository, and the `grafana/docker-otel-lgtm` README.

## Answer

Findings: `docs/research/eyes-into-grafana-2026-09.md` on branch `research/eyes-into-grafana` (commit 9dc705f), cited to Grafana, Loki, Tempo, Prometheus, mcp-grafana and Claude Code documentation, with the auth and role claims verified on a throwaway `otel-lgtm` container (Grafana 12.3.1) that was removed afterwards. The running demo stack was not touched.

- **A correction**: the `otel-lgtm` image runs Prometheus, not Mimir. `mimirtool` does not apply and has no query command anyway.
- **Anonymous can go, and Viewer is the role.** With `GF_AUTH_ANONYMOUS_ENABLED=false` the image answers 401. Service accounts cannot be file-provisioned; the Receiver mints one at startup through the API with the admin's basic auth, which the standard library can do. A Viewer token got 200 on `/api/ds/query` for Prometheus and Loki, on every datasource proxy route, on annotations, alert rules and alert state, provisioning reads and dashboard search, and 403 on every write tried. `GF_AUTH_DISABLE_LOGIN_FORM` must be dropped, so the presenter logs in.
- **Today the backends need no credential at all.** Loki, Tempo, Prometheus and anonymous-Admin Grafana all answer the demo container directly. For a sentinel to mean anything, Loki, Tempo and Prometheus must bind to loopback inside the LGTM container (mounted configs and a `run-prometheus.sh`), so that Grafana is the only door.
- **Two candidates survive.** `mcp-grafana`, one static binary in a 17.6 MB tarball, stdio by default, Grafana-only, Bearer auth from `GRAFANA_SERVICE_ACCOUNT_TOKEN`, with `--disable-write --enabled-tools` cutting its 106 tools to read-only categories; its allow-list form is a tool name such as `mcp__grafana__query_loki_logs`, and the log formatter already renders MCP calls. Or a standard-library `eyes` CLI in the image, allow-listed as `Bash(eyes *)`, whose stdout is the evidence a Report cites. `python3 -c` and `node -e` reach everything but their allow-list form is arbitrary code. `logcli` (37 MB), `promtool` (in a 107 MB tarball) and `tempo-cli` (in a 70 MB tarball) bring three auth styles, no view of annotations or alert state, and one of them cannot address a path under Grafana; not worth it.
- **The research's recommendation**: prototype `mcp-grafana` first. Open questions only a prototype answers: whether its tool names read well on screen, whether the 25,000-token output cap and the ten-line Loki default fit a five-minute Run, and what the thirty-second MCP startup wait does to the slot. `eyes` is the fallback and needs no third party.
- **The Forwarder's shape**: one Forwarder, two routes: the Atlassian site with a basic-auth swap, Grafana with a Bearer swap. Confluence is a third basic-auth route on the same site, not a third Forwarder.
- **The sentinel for Grafana**: `GRAFANA_URL` at the Forwarder and the sentinel in `GRAFANA_TOKEN`; the Forwarder swaps the `Authorization` header. The `ls /usr/local/bin` line of ADR 0005 grows by one name, whichever tool wins.

What this settles for the map: the standing preference for a command-line tool behind the Forwarder now has a named rival that the allow list can express just as plainly, and the choice is a decision for "Eyes" with a prototype in front of it; see "mcp-grafana behind the sentinel". "The Forwarder's growth" has a proposed shape. The backends binding to loopback is a boundary requirement the simulation spec must carry.

Could not verify: none of the CLIs was run (path shapes were tested with curl); unpacked binary sizes; the Tempo `/api/ds/query` body; why a Viewer can list datasources; the tests ran on Grafana 12.3.1 where `otel-lgtm` `main` carries 13.2.1.
