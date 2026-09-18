# Ticket 19 facts — offline experiment preparation (2026-09-18)

Ticket 19 is a measurement prototype and remains NOT RUN: its question explicitly
requires a copied image, read-only `mcp-grafana`, Forwarder Bearer swapping,
anonymous-off Grafana, and a print-mode Run
(`.scratch/many-alerts-one-incident/issues/19-mcp-grafana-behind-the-sentinel.md:1-17`).

## Historical auth naming: two layers, not established compatibility

The committed research states that `mcp-grafana` itself reads `GRAFANA_URL` and
`GRAFANA_SERVICE_ACCOUNT_TOKEN` and sends that token as Bearer
(`git show 9dc705f:docs/research/eyes-into-grafana-2026-09.md:327-347`). Its
example MCP configuration maps that native variable from `${GRAFANA_TOKEN}`
(:374-378). Elsewhere the same research calls `GRAFANA_TOKEN` the proposed
Run-facing sentinel and the Forwarder-swapped header (:399-408). Therefore:
`GRAFANA_TOKEN` is historical proposal naming for the Run/Forwarder boundary;
`GRAFANA_SERVICE_ACCOUNT_TOKEN` is the historical MCP-native input; the example
bridges them through config. It is not proof that either variable name or the
Bearer swap works with ADR 0011's HTTPS sidecar.

## What was actually verified versus documentation-only

The research ran a throwaway `otel-lgtm` container, disabled anonymous access,
minted a Viewer service account/token, and called endpoints with it using curl,
Python, or Node; no CLI was downloaded or executed
(`git show 9dc705f:...:10-19`). Its observed results include anonymous 401 and
Viewer reads/writes boundaries (:149-152,193-203). Those are historical
Grafana-12.3.1/container evidence, not current or planned-venue acceptance.

`mcp-grafana` was never executed; neither were the alternative CLIs
(:435-441). Accordingly its stdio default, `--disable-write`, enabled-tool
categories, default 10-line Loki behavior, tool-output threshold, and the
30-second Claude MCP-startup claim are documentation/source-derived only
(:327-372,425-428). The cited research provides no measured evidence for its startup time, its actual
tool output on a Run, container-hardening compatibility, `dontAsk` behavior, or
Forwarder Bearer behavior.

## Current prerequisite gap after ADR 0011

ADR 0011 requires a separate loopback HTTPS Grafana endpoint with its own
sentinel/upstream credential, validated operations/scope, blocked direct backend
access, and non-anonymous Grafana (`docs/adr/0011-one-forwarder-sidecar-with-scoped-tls-endpoints.md:5-25`).
Current compose instead uses `grafana/otel-lgtm:latest`, enables anonymous Admin,
disables the login form, and publishes Grafana (`docker-compose.yml:23-42`);
it has no MCP binary/config, service-account minting, backend isolation, or
Forwarder sidecar/TLS route. Current Run command permits only Jira Bash and Read
(`grafana_jsm_sandbox/run_command.py:30-34,62-80`), and current Forwarder has one
Jira Basic credential/listener (`grafana_jsm_sandbox/forwarder.py:67-125,203-207`).
These are experiment prerequisites, not grounds to run them now.

No fresh Claude CLI/MCP flags or model claims are made: the required
`claude-api` skill remains absent from the bounded skill locations. No model,
container, cluster, network, or live credential operation ran.
