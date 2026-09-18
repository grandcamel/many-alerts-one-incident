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
