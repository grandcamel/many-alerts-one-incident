# Ticket 19 — prototype protocol (local Stage A measured)

**Current status, 2026-09-19:** the original preparation and authorization statements below are historical. Local Stage A and four subsequently authorized Stage B attempts are recorded, most recently [attempt 4](stage-b-attempt-4-outcome.md). C0 of the [remaining local acceptance plan](local-container-acceptance-plan.md) is now implemented: [offline capture outcome](c0-capture-outcome.md), seven synthetic cases supported and 334 tests passed / 36 skipped. Linux-container C1 and disposable-Grafana C2 remain unexecuted and separately gated; ticket 19 remains claimed and ticket 12 blocked. No further paid attempt is authorized.

**Subsequent preparation:** [C1 source/pins](c1-preparation-outcome.md) are prepared at prototype `3a16de9`, with 363 passed / 36 skipped. The [first C1 execution card](c1-execution-card.md) defines the next bounded build/start/measurement step and its unmeasured rows. Read-only Docker inspection/rendering and host synthetic tests do not change the unexecuted C1/C2 status above.

## Question and boundary

Determine whether mcp-grafana is a usable Eyes tool through ADR 0011's Grafana HTTPS endpoint and service-scoped sentinel, and whether its actual tool output/startup behavior fits the selected Run budget. An eyes CLI is the fallback, not a presumed winner. The user authorized the local, model-free Stage A implementation and execution on 2026-09-18. This authorization excludes Stage B, real tenants, containers and cloud venues; results are recorded separately. Ticket 19 remains unresolved and cannot unblock ticket 12.

The prototype skill is a general throwaway logic/UI workflow. This ticket instead asks for transport/client measurements; a simulated HTML interaction would not answer it. Keep future prototype code and captures on the ticket's named throwaway branch, `prototype/mcp-grafana-eyes`, with exact commits and a main-branch verdict pointer. Do not publish or push from this session.

## Prerequisites before execution

1. Pin the actual mcp-grafana artifact, version, checksum, license and image/base commit. Inspect its own help and primary source for current auth names, TLS trust, tool allowlisting and stdio behavior; historical ticket-03 examples are not an executable command contract.
2. **Stage B only:** obtain the required claude-api skill before asserting/configuring Claude model or CLI flags. ADR 0012 now fixes 300 seconds total per model Run (270 work, 20 interrupt/flush, 10 kill/reap); freeze the actual model/effort and output limits only after current self-documentation/skill verification. Policy duration is not measured client/model compliance. Paid/model and container execution remain outside the current planning session.
3. Build a throwaway subset of the accepted Forwarder boundary sufficient for the Grafana experiment: TLS with verified local CA, Grafana-only sentinel, fixed upstream, authenticated admission/revocation, redirect rejection and request-aware read/rehearsal scope. Do not claim the current HTTP Jira Forwarder provides this. Ticket 36 owns the complete five-service specification (ADR 0013 adds mediated Anthropic); ticket 19 can use a clearly isolated prototype subset without depending on ticket 36's completion (which waits on Eyes).
4. Use an isolated local/test Grafana venue with anonymous access disabled, a least-privilege read credential and deterministic telemetry fixtures; any actual venue run requires separate authorized execution. Keep real credentials outside the Run and out of captures. No mutation probes against the user's shared services.
5. Record the approved tool set, query fixtures and expected source results before comparing candidates; record the Run budget for Stage B only. Keep system telemetry and Run telemetry distinct; include current- and previous-rehearsal fixtures to test access scope. Kubernetes is a separate required Eye and is not evidence of mcp-grafana coverage.

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

## Reconciled inputs after tickets 22–40

The later accepted ADRs constrain execution. The subsequent explicit user authorization covers only the local, model-free Stage A subset; other stages remain NOT RUN.

- **Stage A is model-free and local.** The next bounded implementation would use the real pinned stdio client, a disposable TLS/Forwarder Grafana subset and deterministic synthetic backend fixtures. Store upstream credentials as fixture-only values outside the client boundary. No full demo/cluster, tenant token or paid API call is needed. Fetch/pin artifacts and dependencies with receipts, but do not treat downloaded code as executed acceptance. Mock backend results prove only exercised client/transport behavior; real Grafana/tenant grants and intended-venue behavior remain separate gates. Stage A can run without a complete ticket-36 implementation or Anthropic endpoint, because it launches no model. It does not decide tool usability under a model.
- **Stage B uses the accepted API posture.** ADR 0013 supersedes the direct Anthropic credential exception: an actual model experiment requires the verified mediated Anthropic path and per-Run sentinel in addition to the Grafana subset. Keep its real API key outside the Run; no direct-key/OAuth shortcut. Prove current client compatibility and billing visibility before paid execution. A complete five-service implementation is still not required for the isolated two-service experiment; that experiment cannot stand in for normal demo admission readiness.
- **Time and effects:** apply ADR 0012's 270/20/10-second budget and terminal/containment precedence. No apparent tool or process success overrides timeout/containment failure. An already-dispatched API request can still incur cost. No automatic model fallback or blind retry; every separate model attempt requires reservation and recorded outcome.
- **Spend:** use ADR 0013's diagnostic reserve, count retries, reserve $3 per model attempt and remain inside the $30/ten-attempt diagnostic and $150 weekly envelopes. Record provider actuals, estimates and unknown charges separately; no automatic top-up. A model-usefulness probe does not become one of the three full Fault qualification samples. No paid attempt is authorized by this protocol. A future cloud venue would additionally require ADR 0016's separate budget and lifecycle gates; local synthetic Stage A needs no cloud.
- **Evidence/privacy:** Stage B's private operator-only evidence capture follows ADR 0014's 100 MiB/Run, 2 GiB total and 30-day limits. Keep secrets out, record truncation/gaps and preserve exact source identities; the sanitized shared timeline is not a complete citation audit. Hypotheses, human review and source provenance follow ADRs 0014/0018; do not put scoring material into Run-readable feeds.
- **Read scope:** include distinct application, current-rehearsal Run and Change fixture streams, permitted source/query references and prior-rehearsal negative cases. ADR 0015 requires Change retrieval through the approved read path; synthetic Change fixtures are not proof of the coordinator's real actuation or seven-day retention. Record whether the candidate can enforce the required selection without choosing Eyes prematurely.

## Stage A deliverable for execution review

The proposed bounded work is an isolated throwaway checkout on the named prototype branch, a pinned real client, a local test TLS server/Forwarder subset and synthetic backend, plus a runner covering the Stage A matrix above. Record actual fixture operations, limits and expected results before execution; deny all unlisted targets and never use real tenant credentials. Produce a per-case verdict report, artifact hashes, sanitizer/read-back checks and explicit untouched Stage B/tenant/venue gates. No production Skill/package implementation, full demo, model invocation, cloud provisioning or publication is included. This protocol edit implements none of it.

Stage A is not a model Run: the 300-second model deadline and $3 model reservation do not apply to it. Its runner still needs explicit local process/request timeouts and cleanup bounds. Keep Confluence and other non-Grafana integrations out of this subset. Include a pre-existing clearly marked synthetic Change diagnostic record/read-back without actuation. Sanitized fixture outputs can establish fixture read-back, not a complete real-world citation audit or an implemented audience timeline.

## Execution authorization — 2026-09-18

The user’s “Proceed” authorizes the bounded local Stage A deliverable above. Work is isolated in `/Users/jasonkrueger/projects/maoi-mcp-grafana-prototype` on `prototype/mcp-grafana-eyes`, starting from `3e17793`. Production Skill/package files remain outside this experiment. Ticket 19 remains claimed and ticket 12 remains blocked pending the unexercised acceptance gates.

## Measured local subset

The [Stage A verdict](stage-a-verdict.md) records prototype commit `5f90bfb`, per-case evidence and remaining criterion gaps. Stage B and real tenant/container/venue gates remain NOT RUN. The original protocol is retained to distinguish the measured synthetic subset from the full ticket.
