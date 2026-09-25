# Memory audience projection and acceptance

Type: task
Status: open
Blocked by: 32, 34, 35, 39, 43

## Question

Produce an implementation-ready specification for [ADR 0018](../../../docs/adr/0018-audience-memory-view-preserves-source-and-review-state.md), not a dashboard or public sharing change. Define the operator-only read-only view with OPS Incident state, directory observations/hypotheses, postmortem drafts and approved references, plus links to the complementary sanitized Grafana timeline. Keep human review distinct from execution outcome and reference publication.

Define bounded per-source projection schemas, field allowlists, source revision/observation/verification time, canonical rehearsal/Run/Incident links and safe provenance inspection. Scope to current selected context, distinguish available versus retrieved material, count confirmed records with visible gaps, and avoid quality claims from record counts. Define source authorization and isolation so the view cannot become a new authority, write channel or Run-readable scoring feed. No credentials, identity, raw errors, Ground truth or private audit bodies in rendered cards, URLs or shared telemetry.

Specify presenter selection and pinned before/after snapshots, explicit rehearsal reset, historical availability and current correction/revocation overlays. Pinning never restores approval or serves revoked context to Runs. Define how missing/expired provenance and unapproved/withdrawn versions render; retain source identity without inventing absent detail. Mark cold/Memory conditions without causal improvement claims. Read human-review summaries from an operator-side sanitized projection, not Run-readable logs, and retain pending/disputed/corrected states and qualified rationale.

Define five-second best-effort refresh and the after-30-seconds stale rule using controlled clocks; a refreshed cache is not freshly observed evidence. Show per-section last verified time and failures independently, preserving OPS success when Memory fails. Distinguish unavailable, unknown, revoked, write pending/failed and correction required. UI load/failure cannot block Incident work or reveal raw payloads. Specify live versus replay timing, persistent mode/sample labels, and no approve/publish/retry/reset controls.

Offline acceptance should exercise actual projection/rendering boundaries for mixed authorities, source/review version changes, successful refresh with stale source data, threshold edges, partial outages, missing/unknown counts, confirmed OPS plus failed draft, revocation after pinning, correction history, rehearsal switching, absent retrieval receipts, private-field/URL redaction, disputed human verdicts, historical replay and selection without mutations. Include keyboard-readable status text so color alone never carries authority or failure. Keep fixture success separate from real source integration, access isolation and presenter acceptance. No tenant access changes, dashboard build, live refresh/load test or model Run is authorized here.

## Source progress — 2026-09-22

The [audience specification](../reviews/ticket-44/audience-specification.md)
defines the proposed four-section operator projection, source and retrieval
states, separate human review, bounded safe inspection, pinning with current
correction/revocation overlays, replay/freshness, retention and accessibility.
The [integration review](../reviews/memory-venue-audience-integration.md) keeps
confirmed OPS handling visible despite secondary Memory failures and preserves
the separate authority of human review and reference publication.

This remains open for exact source joins, operator authentication and projection
storage choices and later presenter acceptance. No UI, dashboard, tenant access
change, live refresh test, model Run or automated Report grade was created.

## Local status-policy progress, 2026-09-25: unit 44a

The [44a plan](../reviews/ticket-44/implementation-plan-status-policy.md)
adds pure freshness, count-qualification and pinned-reference overlay decisions
over caller-supplied safe claims. It cannot authenticate source evidence, redact
arbitrary content, isolate operator access, render the view or serve a reference
to a Run. Actual projection/parser, source joins, snapshot storage, UI and
presenter acceptance remain open. This ticket remains open.

## Local structural card candidates, 2026-09-25: unit 44b

The [44b outcome](../reviews/ticket-44/outcome-44b-safe-card-envelope.md)
adds a strict structural parser for one untrusted candidate card in each primary
section. Every result is `unqualified`; caller-provided source, availability
and retrieval states are preserved as claims, never promoted to operator
display authority. Source joins, operator isolation, other projection classes,
current overlays, ID/text sanitization, UI and presenter acceptance remain open.
Independent Standards/Spec reviews and the full local suite (**5,805 passed,
39 skipped**) passed. Native, provider, paid, tenant, venue and human acceptance
are **NOT RUN**; the ticket stays open.
