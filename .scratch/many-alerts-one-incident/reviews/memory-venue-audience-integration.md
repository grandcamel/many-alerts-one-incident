# Memory, venue and audience integration

2026-09-22. Planning/source review for tickets 32, 42 and 44. The proposals
consume accepted ADRs; they do not change runtime, UI, permissions, infrastructure,
Report grades, or the provider-blocked C2 lane.

## Authority across reset and teardown

| Record or action | Owner | A reset, handoff or view must preserve |
| --- | --- | --- |
| Incident/member state | Fresh OPS records and accepted ticket-14 handling | Membership labels, current member states, correction holds and uncertain external effects |
| Directory learning | Narrow structured Memory service | Immutable provenance/corrections and current rehearsal scope; no second Incident database |
| Draft/reference state | Ticket-43 mapping and curator manifest | One Incident-to-draft identity, exact approved version/digest, immediate revocation and uncertain-create obligations |
| Recovery/accounting | Receiver and off-cluster operator ledgers | Failed work, unsettled liabilities and original week/attempt identity, even after cluster deletion |
| Private evidence | Ticket-39 capture/review store | Original retention deadlines, completeness and human-review history; no raw-body export through the audience |
| Audience selection | Operator-only read projection | Historical context plus current correction/revocation overlays; no write or approval authority |

Fresh rehearsal preflight must examine prior OPS Incidents still eligible under
ticket 14's Jira-clock thirty-minute window. A rehearsal label cannot silently
exclude them. Wait for age-out or explicit human disposition; no automatic
closure, membership deletion or alternate Match predicate. Unknown provenance or
incomplete candidate retrieval cannot become a clean preflight. Changing a
rehearsal ID does not reset a cluster's creation age, a Run deadline or a budget.

Memory may carry observations and hypotheses from retrieved evidence, including
legitimate Change references. Repository adjudication Ground truth remains
excluded. A supported-looking Memory entry is context, not independent causal
confirmation. Available records and records actually retrieved by a Run require
separate evidence; a count proves neither learning quality nor use.

## Storage and transfer boundaries

The small recovery manifest is an inventory of separately bounded stores, not a
container that forces every artifact into one new arbitrary cap. Receiver state,
Memory, Change state, model/cloud accounting, Confluence history and private
citation evidence retain their owning storage limits and access rules.

Ticket 39 already specifies off-cluster private audit storage. Teardown validates
that required retained artifacts and their manifests are readable there; it does
not duplicate them without quota accounting or reset their thirty-day capture
expiry. An expired artifact is recorded as expired/missing, never reconstructed
from a later query. A digest alone cannot establish support after the body is gone.

Before source destruction, compare artifact identity, original generation,
byte count, content digest, retention deadline and completeness with the target
read-back. Interrupted transfer is a recoverable incomplete handoff. It grants
neither source deletion nor automatic import into new Run context. A named
operator acceptance transfers responsibility for unresolved work; it does not
mark that work or its external effect complete.

A deliberate exceptional human decision concerning evidence loss is distinct
from ordinary local-work or experiment-cost authority. Prepare exact missing
artifacts, unresolved obligations and cost consequences before that decision is
needed. No such exception or destructive action is requested by this batch.

## Time and health are separate observations

Venue creation age comes from verified creation evidence and restart-safe elapsed
checks. UI refresh time, metric evaluation time, source sample time and Run
elapsed time cannot replace it. A cache refresh is not a new health sample or
new source verification. Unknown/skewed time closes admission conservatively;
a clock adjustment or container restart cannot extend the session.

The baseline must finish before the age-30 gate; the venue proposal permits
session start at age 30 only if baseline completion was earlier. The live
presentation lasts thirty minutes; model launch must
occur strictly before cluster age 85 minutes; age 90 holds ordinary work while
bounded operator recovery remains available. No age transition is deletion
permission or proof that a provider stopped charging.

Health ratios require verified quantities with compatible units and scope.
LGTM/load-generator working-set bytes divided by their configured memory-limit
bytes must be strictly below 0.80; node-available memory divided by its verified
total-memory denominator must be at least 0.25. Do not substitute node capacity,
allocatable memory or a stale declared limit without a verified definition.
Missing samples, coverage gaps, unexpected restart/UID changes, pressure and
unrelated critical conditions remain visible. A narrowly specified expected
Fault symptom cannot mute C4 or make unrelated infrastructure healthy.

## Audience freshness and approval

The five-second refresh target is best effort. More than thirty seconds without
a successful section refresh marks that section stale. Separately display source
observation and verification ages so a successful fetch of old cached data does
not look newly observed. Replay keeps recorded time and mode visible; replay
playback cannot update the live source's freshness clock.

Pinned snapshots preserve what was available/retrieved historically. Current
revocation/correction information overlays the pin, without editing the historical
record or granting current approval. If the overlay source is unavailable, show
current approval as unknown/stale; never rely on the pin to infer approval.
The audience has no approve, publish, retry, reset, teardown or mutation endpoint.

Human review is sourced from the operator-only sanitized review projection,
separate from Run telemetry and execution outcomes. Review pending, disputed,
corrected and historically reviewed with expired audit support remain distinct.
No dashboard calculation or model review creates a semantic grade.

## Required cross-contract acceptance

Exercise real caller/parser/storage/projection seams with deterministic doubles
at the external boundary, not constructed passing summaries:

1. Reset with a still-eligible prior Incident, missing candidate page, unknown
   membership provenance or unresolved write: hold without hidden filtering.
2. Confirmed OPS effect followed by failed learning/draft write: preserve OPS,
   expose the secondary gap, and do not replay confirmed work.
3. Directory corruption/restart/capacity, stale source and superseded entry:
   preserve history, disclose unknowns and prevent unsupported source promotion.
4. Exact age edges, time jump/restart, stale health and denominator mismatch:
   deny optimistic admission; retain bounded pending obligations.
5. Partial export, wrong digest, missing acceptance and expired private evidence:
   refuse ordinary source destruction, preserve original retention and named duties.
6. Unknown deletion, residual resources and delayed charges: hold accounting,
   report ongoing exposure, and do not infer zero cost from empty inventory.
7. Before/after pin plus revocation, unavailable overlay, rehearsal switch and
   replay: retain explicit mode/time and current approval uncertainty.
8. Forged source/reviewer identity, raw-body/credential/private-path/URL fields,
   keyboard-only navigation and UI failure: reveal no prohibited data and issue
   no mutation or Incident-work blocking call.

## Review corrections and retained outcome

The [Memory](ticket-32/memory-specification.md),
[venue](ticket-42/venue-specification.md), and
[audience](ticket-44/audience-specification.md) proposals were drafted by bounded
Terra/Luna workers and reviewed by other internal workers plus root. This is
internal source review, not an external headless panel, human Report adjudication
or runtime acceptance.

Review tightened these material contracts:

- Preserve unknown member state for unmarked/imported OPS records; require
  native conditional-write and read-back evidence before Memory can confirm a
  delta. A transport receipt alone cannot confirm an external effect.
- Bind append attribution to authenticated admission, define finite parser and
  retrieval limits, and cap all retained Memory generations and archives.
- Measure venue age conservatively with full request RTT and separate boot-local
  monotonic clocks from restart recovery using fresh provider evidence.
- Require per-container health checks, unchanged workload identities, complete
  fresh samples and visible unrelated critical conditions.
- Bound creation exposure through verified cleanup and settlement, including
  failed deletion and residual resources. Expected operator response is not a
  hard spending bound.
- Separate write-only export from independent target verification. Record named
  acceptance after final manifest read-back, invalidate it on source changes,
  and require a complete bounded inventory before declaring resources absent.
- Keep source-specific effect, draft and human-review states distinct in the
  audience. Pins preserve history while current overlays, missing receipts,
  expiry and truncation remain visible.

The [validation receipt](memory-venue-audience-validation.json) records final
artifact hashes and source checks. These documents change no code; no code suite
was rerun. The prior code baseline remains `17037db` with 794 passed and 36
skipped; that result does not validate these new contracts. No paid experiment,
provider/tenant action, cluster operation or human Report adjudication occurred.
Historical provider charges remain unknown, and standing aggregate experiment
authority remains strictly below $50 with technical readiness gates intact.

Tickets 32, 42 and 44 remain open for unresolved exact interface choices and
later acceptance evidence. The initial specification sequence is retained. Next
is the [incremental synthetic TLS fixture](ticket-23/incremental-streaming-fixture-plan.md),
which has a bounded implementation/test plan and requires no new user input.
