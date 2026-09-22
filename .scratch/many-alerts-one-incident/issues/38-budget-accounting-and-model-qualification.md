# Budget accounting and model qualification

Type: task
Status: open
Blocked by: 22, 24, 36, 37

## Question

Produce an implementation-ready specification for [ADR 0013](../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md), not runtime changes or paid measurements.

Define the durable Receiver-only budget ledger, atomic reservation-before-launch, lifecycle/diagnostic/weekly attribution, every-attempt counting, actual/estimate/reservation reconciliation without double-counting, billing lag and unknown-exposure holds. Preserve weekly accounting across rehearsal resets, Receiver/pod restarts and calendar boundaries; after lost storage, hold admission until authoritative reconstruction. Specify retention, capacity, time-zone boundaries, operator reallocation and audit controls. Ensure retries consume diagnostic allocation and remain in their lifecycle ceiling, with each actual charge counted once in the weekly sum. Map budget hold to ticket 37's pending-work and uncertain-effect recovery without dropping Notifications or replaying confirmed writes.

Specify offline acceptance through real Receiver/Forwarder seams for simultaneous reservation attempts, crash windows, duplicate/delayed receipts, unknown and above-reservation costs, billing reconciliation, exhausted allocations, restart/reset/rollover and unavailable billing evidence. A mocked bill does not establish provider enforcement. Keep secrets, raw prompts and Ground truth out of the ledger and sanitize cost reporting consistently with ADR 0010.

Define the separately authorized live preflight for current rates, account limits/lag, client budget behavior and the mediated Anthropic path. Do not invent supported flags or prices: inspect current self-documentation and the required Claude API skill before model/CLI claims. Where unavailable, record the evidence gate as blocked. Do not perform a model probe, change auth, create keys, purchase credits or provision infrastructure to write this specification.

Specify a comparable candidate qualification matrix covering initial Report, match/update, resolution, the intended presentation Fault and separately labelled fallback coverage; three complete representative lifecycle samples per candidate, citation review, all failures/retries, per-Run 300s bound, per-lifecycle ceilings and provider actual/unknown accounting. Allocate samples to the accepted rehearsal envelope, guard checks/retries to diagnostics, and avoid hidden extra spend or declaring an unmeasured candidate cheapest. Separate offline fixture, model-quality, provider-billing, tenant and intended-venue acceptance. Preserve labelled replay until all required live gates pass.

## Accepted scoring input from ticket 24

ADR 0014 fixes three samples as two primary-Fault and one designated-fallback lifecycle, including cold-start and Memory-assisted conditions. Each needs reviewed Ground truth and human adjudication under a frozen rubric. Failed/unverifiable samples cannot qualify; replacement samples consume existing allocations or later weeks. Ticket 39 supplies evidence completeness and grade/rollup contracts; missing/expired evidence and corrected revisions must not become new clean samples.

Ticket 40 supplies the missing reviewed fallback Ground truth. A corrected Report revision does not erase an earlier arithmetic, unsupported-claim or fabrication defect from its qualification lifecycle. Require ticket 39's private audit completeness and review record; sanitized shared telemetry cannot supply that gate. Expired evidence retains a labelled historical verdict but cannot support a new independent re-adjudication.

## Accepted Change input from ticket 25

ADR 0015 additionally excludes lifecycles with unresolved Change stages, untracked interventions or material Change-record gaps from clean qualification. Include verified actuation/retrieval and emergency-recovery behavior in future venue preflight; repaired records cannot erase original sample failures. Ticket 41 specifies that contract, not paid acceptance.

## Accepted venue input from ticket 30

ADR 0016 adds a separate $10 weekly venue envelope, $2 reserved per creation attempt and authoritative weekly state preserved off-cluster, with failed setup, replacement and residual/late charges accounted. Keep cloud and model envelopes distinct. Its future no-Fault 90-minute baseline requires no model Runs but consumes venue allocation. Qualification also requires the age/readiness gates and protected cleanup evidence; no provisioning is authorized.

## Approved fallback definition from ticket 40

The human approved [adFailure's Mechanism/Trigger definition](../reviews/ticket-40/definition.md), pinned to upstream commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f`. The missing-definition prerequisite is satisfied. Keep it operator/repository-only, not reference material for Runs. It describes nominal one-in-ten ad RPC rejection with frontend error propagation, not total outage; an exact observed 10-percent ratio is not required for a correct diagnosis. Source/image correspondence, retrieved claim support and corrected-rule live acceptance remain qualification gates. Historical zero matching logs do not refute the warning emitted by source.

## Specification progress, 2026-09-22

The [proposed implementation contract](../reviews/ticket-38/accounting-specification.md)
now records the concrete state, persistence, integration and acceptance requirements.
Accepted ADR policy remains distinct from proposed implementation choices. See the
[cross-ticket review](../reviews/recovery-accounting-audit-integration.md).
This planning artifact is not runtime, model, billing, tenant or venue acceptance;
the ticket remains open for its unresolved inputs and final integration.
