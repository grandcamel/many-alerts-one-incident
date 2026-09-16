# What the harness tells us about a Run

Type: research
Status: resolved
Resolved: 2026-09-15, by a research subagent
Blocked by: none

## Question

What telemetry does Claude Code export about a headless Run, and how would it reach the LGTM stack as a signal beside the system's own? Facts:

- The OpenTelemetry export Claude Code supports: the environment variables that enable it, the metrics it emits, the log events it emits, whether it emits traces, the exporters and protocols it supports, and what identifies one session in that data.
- Whether the export works in print mode with the `dontAsk` permission mode, and whether anything in it would carry a credential or a prompt the audience should not see.
- The stream-json Transcript's Run event shapes, from `fixtures/run-transcript.jsonl` and `fixtures/run-transcript-repeat-firing.jsonl` in this repo, and how each kind of Run event would map onto Loki (logs), Prometheus (metrics) or Tempo (traces).
- Any documented dashboard or reference setup for Claude Code telemetry in Grafana.

Primary sources: the Claude Code documentation on monitoring and OpenTelemetry at code.claude.com, its CLI reference, and this repo's fixtures. Load the `claude-api` skill before stating any model or flag fact.

## Answer

Findings: `docs/research/claude-code-run-telemetry-2026-09.md` on branch `research/claude-code-run-telemetry` (commit 285d85e), cited to the Claude Code monitoring and CLI documentation and verified with live probes: one real one-turn session in print mode under `dontAsk` (about $0.77 of the subscription) and six free replays into the running demo stack's Loki and Prometheus.

- **Enabling the export**: `CLAUDE_CODE_ENABLE_TELEMETRY=1` with `OTEL_METRICS_EXPORTER=otlp` and `OTEL_LOGS_EXPORTER=otlp`; traces need `OTEL_TRACES_EXPORTER=otlp` plus `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` and are beta. Endpoint and protocol through the standard `OTEL_EXPORTER_OTLP_*` variables; protocols are OTLP over gRPC, `http/protobuf` and `http/json`, plus a Prometheus scrape exporter and a console exporter that is a silent no-op under `-p`.
- **What arrives**: eight metrics (session count, lines of code, pull requests, commits, cost, tokens, code-edit decisions, active time) and twenty-six log events (`user_prompt`, `assistant_response`, `tool_decision`, `tool_result`, `api_request`, `api_error`, `api_refusal`, and hook, plugin, auth, compaction and subagent lifecycle events). Traces nest `llm_request` and `tool` spans under a `claude_code.interaction` span, parent to an inbound `TRACEPARENT`, and stamp the trace id on log records.
- **Print mode and `dontAsk` are covered**, verified live: payloads arrive, `session.id` in the export equals `session_id` in the Transcript, `app.entrypoint` is `sdk-cli`, and a session of about a second flushes at exit on default intervals. `--session-id <uuid>` lets the Receiver choose the id, so the Run directory, the Transcript, the export and the Jira comment can share one key.
- **What the audience must not see is identity, not secrets.** Prompts, responses, tool arguments and file contents are redacted by default, and no captured record carried the OAuth token or the sentinel. But `user.email`, `organization.id` and `user.account_id` are on every record when the Run signs in with an OAuth token, and `api_error.error` is verbatim. The formatter's redaction does not touch the export; the fix is an attributes processor in a mounted collector config, or a demo account.
- **The stack drops the metrics as it stands.** The LGTM image's Prometheus 3.9.1 discards Claude Code's default delta counters, verified by replay; set `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative` or enable Prometheus's delta-to-cumulative feature. Loki keeps only `service_name` as an index label and the rest as structured metadata, which is enough to tell `claude-code` from the system's services.
- **The Transcript still has to be shipped.** The export never carries the command line, the tool output, the denial text, the final cost or the turn count; the formatter's lines do, and today they go only to the container log. The Receiver posting one OTLP log record per Run event, body the formatter line, is the candidate that keeps redaction and the join key in one place; a log shipper is the alternative.
- **Side findings**: `--bare` refuses an OAuth token and needs an API key. The public Claude Code dashboards (Grafana.com 25255 and 25052, Anthropic's monitoring guide, a community `otel-lgtm` compose) are fleet-level; none is per-Run.

What this settles for the map: "Run telemetry as a signal" is unblocked and knows its variables, its join key, its two privacy fixes and the temporality trap. The Notes' fourth signal is confirmed as two feeds with one key: the harness's export and the shipped Transcript.

Could not verify: flush on SIGKILL; tool spans from a successful Run; end-to-end delivery to Tempo; whether `OTEL_RESOURCE_ATTRIBUTES` can override `service.name`; exporter behaviour when the collector is down.
