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

## Local storage progress, 2026-09-24

The separate Receiver-owned [18c storage gate](../reviews/receiver-journal/outcome-18c.md)
passes local tests and independent source/spec review. It starts with unknown
population, stores receiver-origin v1 events, and exposes no production reserve
or launch method. Its [next-gate record](../reviews/receiver-journal/accounting-reservation-gates.md)
names the missing authoritative opening history, provider line identity and
coverage/lag, defensible U, continuity witness, archive/repair design and
cross-store handshake. No synthetic marker or new directory satisfies these
inputs. The ticket remains open; provider, native, tenant, paid, power-loss and
dispatch acceptance are NOT RUN.

## Local cross-store relation progress, 2026-09-25

The [18d1 pure relation](../reviews/receiver-journal/design-18d1-no-launch-bridge.md)
compares caller-supplied journal intent, ledger reservation and journal
confirmation facts. Its exact-match result remains a hold, so this source
slice supplies no authenticated store join, production reserve or launch
permit. The [source review](../reviews/receiver-journal/review-18d1-source.md)
found no local blocker. Verified history adapters, versioned writers and crash
ordering are still local work; authoritative opening/billing evidence and the
other gates in the 18c record remain unresolved. This ticket stays open.

## Local journal claim progress, 2026-09-25

The [18d2 journal claims](../reviews/receiver-journal/design-18d2-journal-claims.md)
make versioned intent and confirmation records replayable without a writer.
They preserve a held job and expose only count/digest inspection. A journal
confirmation remains unauthenticated until a separate read-only adapter
compares independently verified current journal and ledger histories; orphan
ledger events and rollback can still create liability. The Receiver ledger
continues to reject `reservation_created` while opening population is
unknown. Production reserve, provider billing evidence, continuity witness,
archive policy and dispatch gates remain open. This ticket stays open.

## Local verified-view progress, 2026-09-25

Unit [18d3a](../reviews/receiver-journal/outcome-18d3a.md) adds an
independently verified, query-only v1 ledger view. It releases an anchored
Receiver/`unknown` identity and an empty reservation tuple, and no facts on
held or unverified images. A fixture genesis or crafted reservation row is
rejected by replay. The companion journal view releases its claims only
from an exact anchored head. This is negative evidence for the current store
format, not a production reservation or a positive cross-store join.
Independent source reviews and the full local suite pass. Opening history,
provider identity/coverage/lag, liability U, continuity witness and
archive/repair policy remain unresolved. The ticket stays open.

## Local negative scan progress, 2026-09-25

Unit [18d3b](../reviews/receiver-journal/outcome-18d3b.md) consumes the
independently verified 18d3a views and reports only closed hold reasons.
Real stopped images with no journal claim, an intent, and a confirmation
remain held against the v1 Receiver/`unknown` ledger's empty reservation
set. A journal confirmation cannot authenticate spend. The scanner has no
reservation writer, positive durable triple, permit or Run caller.
Independent source reviews and the full local suite pass. Authoritative
opening/billing evidence, liability U, continuity witness and archive/repair
policy remain unresolved; provider, paid and venue acceptance are not run.
The ticket stays open.

## Local evidence/archive contract progress, 2026-09-25

The [18e candidate and archive contract](../reviews/receiver-journal/design-18e-accounting-evidence-archive.md)
separates untrusted source claims from later source-profile and accounting
verification. It specifies failure codes and a read-back, witness and active
index handoff that preserves duplicate uncertainty and holds on missing
history. This is documentation only: no source profile, importer, archive,
continuity witness or production reserve exists. The exact authoritative
source, account scope, line identity, adjustment and lag semantics, opening
history, liability U, archive registration, independent witness and intended
venue durability evidence remain decisions. Provider, paid, native, tenant,
venue and power-loss acceptance are NOT RUN. This ticket stays open.

## Local candidate syntax progress, 2026-09-25: unit 18f

Unit 18f parses the reviewed 18e private candidate envelope as canonical,
bounded metadata and detects exact replay versus changed bytes under one
candidate ID. Source kind, account scope, coverage and payload digest remain
unverified claims. There is no source profile, payload verification, billing
importer, opening reconstruction, archive, witness or reserve method. This
local source slice cannot clear a budget hold. The external evidence and
continuity decisions listed above remain open; this ticket stays open.

## Local archive-format progress, 2026-09-25: unit 18g

The [18g proposed format](../reviews/receiver-journal/design-18g-archive-format.md)
pins future contiguous event segments, a derived cumulative duplicate index
and fail-closed read-back, witness and registration ordering. The current v1
ledger cannot register or compact an archive, and no writer, importer,
off-cluster destination or independent witness was built or selected. Opening
history, provider source/account scope, charge-line and adjustment identity,
coverage/lag/finality, liability U, archive registration, witness and venue
durability remain decisions. Provider, paid, native, tenant, venue and
power-loss acceptance are NOT RUN. This ticket stays open.

## Local segment-codec progress, 2026-09-25: unit 18g1

The [18g1 local outcome](../reviews/receiver-journal/outcome-18g1-segment-codec.md)
records a pure, same-generation segment codec and replay check for the proposed
18g format. Independent source/spec review, focused tests and the full local
suite pass. This does not create a registered archive, duplicate index,
independent witness, reservation or dispatch authority. The external evidence
and durability decisions above remain open; provider, native, tenant, paid,
venue and power-loss acceptance are NOT RUN. This ticket stays open.
