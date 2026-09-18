# Ticket 19 — prototype protocol (NOT RUN)

## Question and boundary

Determine whether mcp-grafana is a usable Eyes tool through ADR 0011's Grafana HTTPS endpoint and service-scoped sentinel, and whether its actual tool output/startup behavior fits the selected Run budget. An eyes CLI is the fallback, not a presumed winner. This file prepares the experiment; no prototype code, image, model invocation, cluster, credential use or live measurement was produced. Ticket 19 remains unresolved and cannot unblock ticket 12.

The prototype skill is a general throwaway logic/UI workflow. This ticket instead asks for transport/client measurements; a simulated HTML interaction would not answer it. Keep future prototype code and captures on the ticket's named throwaway branch, `prototype/mcp-grafana-eyes`, with exact commits and a main-branch verdict pointer. Do not publish or push from this session.

## Prerequisites before execution

1. Pin the actual mcp-grafana artifact, version, checksum, license and image/base commit. Inspect its own help and primary source for current auth names, TLS trust, tool allowlisting and stdio behavior; historical ticket-03 examples are not an executable command contract.
2. Obtain the required claude-api skill before asserting/configuring Claude model or CLI flags. Freeze the actual model/effort, timeout and output budget from the relevant decisions and record any still-unsettled assumption. Do not silently assume a five-minute budget or output limit is verified. Paid/model and container execution remain outside the current planning session.
3. Build a throwaway subset of the accepted Forwarder boundary sufficient for the Grafana experiment: TLS with verified local CA, Grafana-only sentinel, fixed upstream, authenticated admission/revocation, redirect rejection and request-aware read/rehearsal scope. Do not claim the current HTTP Jira Forwarder provides this. Ticket 36 owns the complete four-service specification; ticket 19 can use a clearly isolated prototype subset without depending on ticket 36's completion (which waits on Eyes).
4. Use an isolated local/test Grafana venue with anonymous access disabled, a least-privilege read credential and deterministic telemetry fixtures; any actual venue run requires separate authorized execution. Keep real credentials outside the Run and out of captures. No mutation probes against the user's shared services.
5. Record the approved tool set, query fixtures, expected source results and Run budget before comparing candidates. Keep system telemetry and Run telemetry distinct; include current- and previous-rehearsal fixtures to test access scope. Kubernetes is a separate required Eye and is not evidence of mcp-grafana coverage.

## Stage A — client/transport without a model

Use the actual pinned binary via its stdio protocol, not a hand-written HTTP substitute presented as client proof. Capture sanitized requests at the local boundary and exact fixture read-backs. The fixture backend records whether denied requests reached it without retaining auth secrets.

| Case | Required observation |
| --- | --- |
| Valid TLS and scoped admission | Real client completes a permitted query through the intended listener, with correct upstream request and expected fixture output. |
| TLS negative cases | Untrusted CA, wrong hostname/IP and expired certificate fail; there is no insecure retry. |
| Invalid authority | Wrong-service, absent, revoked and expired sentinels fail before upstream execution. |
| Redirect/target escape | Upstream redirects, absolute targets and unsafe paths cannot redirect credential-bearing requests. |
| Allowed reads and denied writes | Permit approved read query shapes, including approved POST queries; deny mutation/unlisted operations in an isolated fixture, independently of client write-disable settings. |
| Rehearsal scope | Current-rehearsal execution telemetry is readable; prior-rehearsal scope expansion is denied. System telemetry remains available under its separately approved policy. |
| Output completeness | Loki multiline/long records, metric ranges, trace references, empty results and explicit errors remain distinguishable; observe actual defaults, truncation and available pagination. |
| Failure and revocation | Timeout, interrupted stdio, upstream failure and mid-session revocation yield visible failures with no bypass or silent authority restoration. |

A pass here proves only the exercised client/transport contract. It does not prove the model can select tools, understand outputs, obey permissions or finish in time. Record skips and unsupported cases explicitly, never as passes.

## Stage B — bounded model experiment (NOT RUN)

After the transport gate passes and execution is authorized, use a single controlled read-only prompt and pinned fixtures with source-grounded expected results. Capture startup-to-initialization, initialization-to-first-useful-result, individual query durations and total Run duration using a monotonic clock; distinguish process/MCP startup from model thinking. A single sample proves only that sample, not a latency percentile or dependable stage timing.

Exercise representative logs, metrics and traces, an intentional forbidden operation against the isolated fixture, and current-rehearsal self-observation. Record actual tool names and whether the audience can follow them, observed output sizes/truncation, retrieved evidence references, permission-denial presentation, and outcome fields under ticket 21's contract. Raw model assertions are not proof of a successful tool call. Missing measurements or result data remain unknown.

Record container file changes and mounts before/after with a disposable image/container and a sanitized environment-key inventory. Check for unintended writable paths or persistence; do not disclose environment values or infer security from an empty filesystem diff alone. Verify revoked sentinels fail after the Run and that captured artifacts contain no upstream credential or reusable sentinel.

If mcp-grafana fails a requirement, implement only a throwaway eyes CLI subset needed for the same fixture and repeat the comparable cases under the same conditions. Do not spend model budget on a fallback merely to fill a comparison table if the first candidate answers the question. Identify unmatched coverage rather than calling unlike cases equivalent.

## Decision rule and evidence bundle

The outcome is `supported for exercised scope`, `refuted by named failure`, or `inconclusive` per criterion: TLS/auth, read/rehearsal enforcement, tool usability, evidence completeness, runtime budget, filesystem/credential boundary. Hard boundary failure prevents selection until corrected and re-tested; incomplete coverage stays a limitation. Ticket 12 makes the final tool/allowlist decision from measured results. Neither static discovery nor this protocol selects a winner.

Retain a manifest with source/image/binary commits and hashes, client help/source references, fixture and configuration hashes, declared budgets, sanitized transcripts/request logs/read-backs, timings, filesystem diffs, per-case verdicts and explicit NOT RUN boundaries. Keep probe identity and origin so native client, model, simulated backend and real venue evidence cannot be confused. Capture any exact command only after validating installed syntax; this document intentionally supplies no guessed invocation.

## Relationship to other tickets

Ticket 17/ADR 0011 provides the accepted boundary, ticket 12 owns the eventual Eyes selection, ticket 21 owns timeout/refusal/outcome semantics, and ticket 35 owns telemetry integration/acceptance. Ticket 36 may consume prototype findings after Eyes settles. Keep this ordering acyclic: a complete ticket-36 implementation is not a prerequisite for the limited ticket-19 experiment.
