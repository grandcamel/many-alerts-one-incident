# Ticket 42 venue lifecycle and protected teardown specification
Status: proposed implementation contract, source-only, 2026-09-22. This document
implements no cloud action, cluster, deletion, credential, model run, or paid
operation. “Accepted” below repeats ADR 0016 and ticket 30. “Proposed” selects
interfaces and bounds that require future review and intended-venue acceptance.

## Authority and non-claims
A venue is one fresh cluster for one full rehearsal or presentation lifecycle.
Its lifetime starts at provider creation, includes provisioning, and never resets
because a Pod, Receiver, Forwarder, coordinator, or process restarts. A failed
setup, missed gate, or age threshold does not authorize automatic recreation,
resource-tier increase, spending, Fault injection, or deletion. The fallback is
labelled replay or an explicitly approved later creation after protected state is
preserved.
The Receiver owns Notification admission, Run deadlines and recovery under
ticket 37. Ticket 38 owns model and aggregate experiment accounting; ticket 39
owns private audit retention; ticket 41 owns Change and undo. The venue controller
is operator-only. A Run can read only its mediated scope; it cannot create,
destroy, extend, hand off, export, or reclassify a venue.

## Stable identity, clocks, and lifecycle states
`venue_id` is a generated UUIDv4; it is distinct from a provider resource ID,
rehearsal ID, lifecycle ID, Fault ID, or billing account. The durable off-cluster
venue ledger has append-only, canonical UTF-8 JSON records with schema version,
record UUID, wall timestamp, monotonic timestamp/boot ID, actor class, predecessor
digest, payload digest, and encoded byte count. IDs are ASCII <=128 bytes;
records are <=16 KiB except the bounded handoff manifest below. Duplicate
record ID/digest is idempotent; a changed duplicate or unknown schema holds all
ordinary admission.
A proposed state machine is:
`PLANNED -> CREATION_RESERVED -> CREATING -> CREATED -> PREFLIGHT -> BASELINING
-> READY -> LIVE -> DRAINING -> HANDOFF_PENDING -> HANDOFF_VERIFIED ->
TEARDOWN_REQUESTED -> CLEANUP_UNKNOWN|CLEANED`.
`HELD`, `AGE_UNKNOWN`, `HEALTH_UNKNOWN`, `EXPORT_INCOMPLETE`, `COST_UNKNOWN`,
and `CONTAMINATED` are sticky gates that may coexist with a lifecycle state.
`CLEANED` means only verified provider inventory absence, not zero future billing
or no external effect. Every transition is operator-recorded or comes from the
named trusted adapter; a timer cannot transition directly to destruction.

### Authoritative age
The provider creation adapter returns a typed `creation_receipt`:
```json
{
  "schema_version": 1,
  "venue_id": "uuid",
  "provider_account_pseudonym": "opaque",
  "provider_resource_ids": ["opaque"],
  "region": "bounded-token",
  "provider_created_at_utc": "RFC3339",
  "provider_now_utc": "RFC3339",
  "receipt_digest": "sha256",
  "observed_monotonic_ns": 0,
  "observer_boot_id": "opaque"
}
```

`provider_created_at_utc` plus authenticated provider `now` in the same read is
the authority, not Kubernetes creation time, pod time, local wall time, or a
billing event. At every boot/restart, the controller reads a fresh receipt and
persists `age_lower`, `age_upper`, boot ID, and monotonic anchor. Given the
provider timestamp uncertainty `epsilon` (proposed maximum five seconds), require
the authenticated timestamp to have been generated during the measured request.
At response receipt use the full measured round trip for the upper bound;
timestamp placement is not assumed to be the midpoint. Before applying any
`max`, calculate fresh raw bounds and validate the prior anchor:

```
fresh_lower = max(0, provider_now - provider_created_at - epsilon)
fresh_upper = provider_now - provider_created_at + epsilon + rtt
same boot: prior = persisted_bounds + elapsed_monotonic_since_anchor
new boot:  prior = persisted_bounds  # no cross-boot monotonic subtraction
require fresh_upper >= prior.upper
age_lower = max(prior.lower, fresh_lower)
age_upper = max(prior.upper, fresh_upper)
```

Missing/negative RTT, uncertainty above `epsilon`, stale/unavailable provider time,
a raw `fresh_upper` below the appropriate prior upper bound, malformed/changed
resource identity, or a lost same-boot monotonic anchor is `AGE_UNKNOWN` and holds ordinary
admission **before** any max can conceal elapsed time. At restart the fresh
provider receipt must cover downtime and establish a new boot-local anchor;
persisted age alone cannot recover missing time. Without a fresh authenticated
receipt with the required timestamp semantics, restart stays held. Local wall
time is audit-only. A restart therefore cannot lower age.
Accepted edges use the conservative upper bound: a model Run may start only when
`age_upper < 85 minutes`; equality is denied. Queue wait, restart, cancellation,
handoff, and reaping do not reset the bound or extend ticket 37's 300-second Run
deadline. At `age_lower >= 90 minutes`, or whenever `age_upper >= 90 minutes`,
ordinary Fault injection and model dispatch are held. The operator may continue
bounded reconciliation, undo, export, and teardown. Age 90 is not deletion
permission. The accepted requirement is baseline completion **before** age 30;
this proposed equality choice permits session start only when `age_upper <=30
minutes` after a baseline that completed with `age_upper <30 minutes`. Fixtures
must exercise `<30`, exactly `30`, and `>30` separately; this is not an accepted
claim that equality is universally safe.

## Admission, baseline, and live window
The accepted baseline is five continuous healthy minutes. Proposed implementation
requires at least six successful `health_snapshot-v1` samples spanning >=300
seconds, with adjacent samples <=60 seconds apart and each input observation <=60
seconds old at snapshot creation. Every input records both source `observed_at`
and adapter `fetched_at`; a refreshed cache whose observed timestamp is stale,
missing, future, recycled from an earlier baseline interval, or inconsistent with
the query receipt fails the snapshot. A missing, stale, malformed, conflicting,
or out-of-scope input resets the baseline and sets `HEALTH_UNKNOWN`; absence is
never healthy. Snapshot IDs link query receipt digests, exact times, VenueProfile
digest, and all denominators.
`VenueProfile` is operator-pinned before creation and contains the exact intended
workloads, Fault baseline values, mandatory Forwarder routes, service boundaries,
node set selector, resource limits, C4 rule identity, and expected-Fault profile.
It is <=64 KiB and may not be modified during a lifecycle. Current manifest,
pricing, and actual settings are acceptance inputs, not inferred from history.
A healthy snapshot requires all of the following:

| Check | Required observation and denominator | Predicate |
| --- | --- | --- |
| Fault baseline | ticket-41 Change/served observations for every declared Fault key/value | all equal Profile baseline; unknown holds |
| Workload stability | Deployment desired/available/updated replicas, Pod UID set, and restart counts for every Profile workload | equal desired/available/updated; no Pod UID/restart change since prior snapshot |
| Mandatory routes | ticket-36 per-route readiness and strict TLS/control generation | Jira, Grafana/Eyes, Kubernetes, Anthropic READY; Confluence visibly optional |
| LGTM working set | each named Profile LGTM container's working set / its verified actual positive `limits.memory` bytes, plus the corresponding aggregate ratio | every per-container and aggregate ratio `< 0.80`; absent/zero/mismatched limit holds |
| Load-generator working set | same per-container and aggregate calculation for named Profile load-generator containers using actual `limits.memory` bytes | every per-container and aggregate ratio `< 0.80`; absent/zero/mismatched limit holds |
| Node memory | for every node currently hosting a Profile workload: `MemAvailableBytes / MemTotalBytes` from one typed node metric family | minimum ratio `>= 0.25`; no missing node |
| Node/pod health | node MemoryPressure/DiskPressure/PIDPressure all false; no eviction/OOM condition outside approved profile; no active unexpected critical infrastructure Alert | all clear |
| System evidence | ticket-12 source-scoped Pod/status/Event/EndpointSlice/metrics reads | current-rehearsal time scope and sanitization validate |
| Recovery and policy | ticket-37 durable health/no recovery hold; ticket-38 availability; ticket-39 capture preflight; OPS eligibility | every mandatory gate passes |

The numerator counts a container once by `(pod UID, container name)`; the
denominator includes only its matching verified actual container `limits.memory`
bytes, never a quota, node allocatable/capacity, request, historical default, or
unrelated container. Node availability is the minimum across the exact live
hosting-node set; its proposed metric/path and `MemTotal` semantics must be
pinned and verified in the intended venue, never substituted with allocatable or
a cluster aggregate. A Profile change or a new host resets baseline. Historical
726--1640 MiB and single headroom/OOM observations do not satisfy any row or
prove 30/90-minute safety.
`LIVE` begins at recorded session start after `READY` and lasts 30 minutes. At
window end, hold every ordinary new Fault injection and model launch and switch
audience presentation to labelled replay; only already-admitted Incident/recovery
work may continue under its original deadlines and holds. It never extends
authority or makes an on-stage completion claim.

### C4 and contamination
C4 remains cluster-wide exactly as the pinned rule/configuration reports it;
its original service/resource identity, namespace, labels, timestamps, and
severity are preserved. The controller never suppresses, relabels, or forces an
infrastructure Alert into the injected Fault's Incident.
The operator-pinned `expected_fault_profile` is narrow: it names one Fault,
its Change ID/stage window, exact expected service/resource identities, allowed
restart/condition categories, and a maximum time window. A symptom is expected
only when all fields match that profile and its trusted Change observation. Node
pressure, eviction, a mandatory backend exhaustion, an unprofiled C4 source,
or a critical condition outside the profile is `UNRELATED_CRITICAL`, holds new
injection, preserves its source identity, and sets `CONTAMINATED`. No expected
profile can override node pressure, eviction, exhausted mandatory backends, or
an unrelated critical C4 condition, and it never changes C4 label allocation.
Expected symptoms do not prove diagnosis, recovery, or clean qualification.
Material contamination excludes a clean candidate sample; later scope changes
need a new decision and acceptance.

## Cloud and aggregate accounting
Cloud accounting is an off-cluster, Receiver/operator-owned append-only ledger
with separate access purpose from the model ledger. It may share ticket 38's
transactional store only if cloud and model tables/access controls remain
separate and both changes commit atomically; otherwise use a durable
`creation_intent -> creation_reserved|creation_unknown` handshake and recovery
scan. Never assume two stores commit atomically.
The accepted venue envelope is $10 (`10_000_000` USD microdollars) per
Monday--Sunday week in `America/New_York`. Before each creation attempt, including
failed setup or replacement, atomically reserve `R_cloud=2_000_000`. Reservation
is an allocation, not a maximum charge. The creation admission also needs a
current authorized preflight-derived whole-creation liability `U_cloud`: the
maximum defensible total for all named resources through **verified cleanup and
provider settlement coverage**, including failed deletion, retry delay, residual
resources, nodes, control plane, volumes, snapshots, network, IPs and other
attachments. A timer or expected human response is not a hard bound. `U_cloud`
must be positive, exact integer microdollars, and at least `R_cloud`;
missing/indeterminate U holds creation.
Creation admits only when all are true:

```
weekly_cloud_liability + U_cloud <= 10_000_000
experiment_liability + U_cloud < 50_000_000
no cloud/accounting/history/recovery hold
```

`experiment_liability` is ticket 38's aggregate, combining each completed actual
once and each incomplete model/cloud/support/review/venue liability once. It
never adds an R already represented by U. The strict `< 50_000_000` retains the
standing total experiment cap below $50. The $10 cloud and $150 model weekly
envelopes are separate; a cloud charge never consumes model lifecycle or
diagnostic allocation, while both affect the aggregate experiment cap.
`venue_cost_event-v1` records creation ID, venue/provider resource IDs,
week/experiment key, R, U, cost class, provider-line identity, occurrence time,
amount/currency, evidence digest, coverage state, and reconciliation state. A
unique provider line is idempotent on `(provider_account_pseudonym, line_id)`;
a changed replay is a conflict hold. Final known actuals replace U only after
coverage-complete evidence covers the full creation-to-verified-cleanup and
settlement interval. Multiple lines may settle one creation. Unknown historical/late charges, missing archive,
missing coverage, resource without attribution, or provider-line conflict are
not zero and set `COST_UNKNOWN`, holding new creation/model dispatch where ticket
38's aggregate cannot be defended. Teardown cannot erase a reservation, old-week
liability, or later reconciliation obligation.
Venue records consume ticket 38's existing accounting capacity and archive
handoff: 8,192 active accounting events, 512 unsettled attempts/creations, and
65,536 or 16 MiB idempotency tombstones, whichever bound is reached first. A
separate physical cloud ledger must enforce those same count/byte bounds and
atomically register its archive/index digest with the shared aggregate; it cannot
create a second unbounded cost history. Capacity/archive failure holds creation
and preserves existing records rather than evicting a charge, reservation, or
unknown liability.
No automatic top-up, new cluster, higher resource tier, or budget extension is
allowed. Current pricing, limits, account status, billing semantics, and coverage
lag require separately authorized provider preflight; none was read here.

## Protected drain, export, and handoff
`DRAINING` starts for age/readiness/cost/contamination/export hold or an operator
request. It stops ordinary Fault injection and model launch but retains bounded
Notification admission/coalescing, existing ticket-37 containment/recovery,
operator undo, and reconciliation. It cannot silently discard a pending source,
unknown effect, reservation, audit gap, or Change stage.
Before source destruction, the operator must request a `handoff-v1` from a
trusted exporter with read-only access to the listed journals and a write-only
private off-cluster vault. The exporter has no provider delete credential, no
Run mount, no upstream service credential, and no ability to mutate source
records. A distinct trusted verifier has read-only target access and no source
mutation/delete authority; it reads the completed target bytes and validates
object ID, encoded bytes, digest, and record count against the exporter’s
source-snapshot digests. Vault ACL/encryption and this independent verification
path are acceptance gates.

```json
{
  "schema_version": 1,
  "handoff_id": "uuid",
  "venue_id": "uuid",
  "rehearsal_id": "opaque",
  "creation_receipt_digest": "sha256",
  "venue_profile_digest": "sha256",
  "age_bounds_ns": {"lower": 0, "upper": 0},
  "source_snapshots": ["typed owner/digest/ref"],
  "notifications": ["admission_id/state"],
  "runs_attempts_leases": ["run_id/attempt_id/lease/state"],
  "effects": ["effect_id/operation_id/intent_id/state/readback"],
  "changes": ["change_id/stage/state/evidence"],
  "accounting": ["reservation/cost/coverage/hold refs"],
  "audit": ["audit_bundle_id/digest/expiry/status"],
  "ops_confluence": ["external identity/disposition only"],
  "unresolved": ["typed obligation/reason/owner"],
  "content_sha256": "sha256",
  "canonical_bytes": 0
}
```

For digest calculation, serialize the validated manifest as canonical UTF-8 JSON
with sorted keys, omitting only the `content_sha256` and `canonical_bytes`
envelope fields. Both fields describe those exact remaining bytes. The final
object also has an independent full-object digest in its verifier attestation;
acceptance names that object digest and revision, avoiding self-reference.
The handoff manifest is <=1 MiB, <=8,192 typed records and <=65,536 artifact
references; artifact-reference metadata is <=16 MiB. It is an index, not a new
unbounded artifact store. Ticket 37 recovery export remains <=128 MiB including
its 16 MiB reserve; ticket 41 Change export remains within its 100 MiB journal
and 10 MiB recovery/undo reserve; ticket 38 records retain their own 8,192-event
and archive limits. Audit artifacts already reside in ticket 39's separate
private off-cluster store: handoff validates retained object IDs, bytes, digests,
status, and expiry by read-back and records references only. It does not copy
audit bodies into the manifest, force them into the 16 MiB metadata cap, create a
second 2 GiB store, or extend ticket 39's absolute 100 MiB-per-Run, 2 GiB
aggregate, and 30-day expiry. The handoff records only references/digests for
external OPS/Confluence history, never copies credentials or assumes external
history can be deleted.
For each source snapshot the exporter writes canonical bytes, byte count, record
count, owner/schema/retention state, and expected SHA-256; the independent verifier
writes the target object/byte count/SHA-256 read-back attestation. A source digest
mismatch, incomplete byte count, failed copy, lost exporter,
unknown artifact, full vault, verifier failure, or unreadable target sets
`EXPORT_INCOMPLETE`, preserves the source, and blocks destructive cleanup.
Only after independent verification writes `handoff_attestation-v1` may a named
operator append `handoff_acceptance-v1` containing the final manifest revision,
object ID/digest, verified snapshot-digest set, exact unresolved obligations,
operator alias/private-principal reference, and timestamp. Any source change,
export retry, manifest revision, or snapshot change invalidates prior acceptance
and needs a fresh verification/acceptance. Retrying export creates a new snapshot
attempt linked to the failed attempt; it does not overwrite or call missing data
complete. A verified handoff preserves obligations but does not settle an external
write, unblock a held model launch, expose prior-rehearsal Memory to Runs, or
promote a recovery record into OPS authority.
Emergency undo/restoration takes priority. If destruction is truly necessary
while export is incomplete, only a named human operator may record an
`exceptional_loss_decision` with reason, affected owner IDs/digests, known loss,
remaining obligations, timestamp, and private principal reference. It marks the
venue/lifecycle incomplete and disqualified; it cannot be automated, delegated
to a Run, or converted into cleanup success.

## Cleanup and post-teardown reconciliation
`TEARDOWN_REQUESTED` requires verified handoff or exceptional loss decision,
ordinary admissions held, active Runs contained/reconciled under their original
300-second deadline, and Fault state undone or explicitly handed off. The trusted
operator then issues a provider deletion request. Its exit code is only a request
receipt, never inventory absence.
The provider inventory adapter re-reads every creation-receipt resource and its
dependencies: cluster/control plane, node pools/nodes, volumes/snapshots, load
balancers, public/reserved IPs, firewalls, network resources, DNS entries, and
other separately billed attachments identified by current preflight. Each row
has resource ID/type, owner/tag, observed state/time, query receipt digest, and
cost-attribution status. Inventory is server-paginated with <=1,000 rows/page,
<=10 pages, <=30 seconds/page, and <=5 minutes from first to final source
observation; every receipt must be <=60 seconds old at the decision. Missing
continuation, duplicate/out-of-order page, timeout, partial page, stale read,
or empty response without a complete terminal page is `DELETE_UNKNOWN`. A
requested resource that is absent is `DELETED`; a remaining resource matching
both expected ID and venue ownership tag is `ORPHANED`; ownership ambiguity is
`DELETE_UNKNOWN` and never authorizes deletion of an unrelated resource. The
latter two retain liability, set `CLEANUP_UNKNOWN`, and escalate an operator
task. Empty known inventory does not prove zero future billing, credit/refund
completion, or no delayed charge.
`CLEANED` requires a complete bounded inventory traversal, every expected resource
`DELETED`, no orphan/unknown row, and post-destruction accounting reconciliation still active. It does not close OPS
Incidents, retry an uncertain operation, or clear historical holds. A subsequent
creation is a new venue and must pass fresh age, profile, accounting, Forwarder,
health, audit, and OPS gates.

## Offline acceptance and future venue gate
Offline fixtures must drive the actual planned lifecycle/clock/health/ledger/
export interfaces with deterministic adapters. They must cover creation receipt
identity changes; exact `<30`, `<85`, and `>=90` edges; boot restart; monotonic
and wall jumps; stale/missing/provider-skewed age; six-snapshot baseline gaps;
missing limits; 80%/25% boundaries; expected profile versus unrelated C4 source;
active/pending Runs at drain; concurrent R/U reservations; failed setup; late or
unknown cost; full journal/audit/vault; interrupted export; digest mismatch;
expired audit body; unknown delete; orphan resource; emergency loss; and no
automatic recreate/tier increase. Fixture success proves only these boundaries.
Separately authorized intended-venue qualification consists of one **no-Fault
90-minute baseline** on a fresh venue, without model Runs, then three candidate
qualification lifecycles on fresh venues within existing budgets. The baseline is
charged to cloud accounting but is not a scored model sample. Each venue records
actual settings/profile, age/health observations, session overrun, failures,
cost/liability/coverage, handoff, and cleanup inventory. Fresh venue
qualification may use only same-rehearsal prior learning or approved ADR 0009
reference material; never an unreviewed recovery export. A failed gate retains
labelled replay and creates a bounded tuning/measurement follow-up; it does not
prove a leak, justify a higher limit, or authorize a replacement.

## Sources and open gates

Read: [issue 42](../../issues/42-venue-lifecycle-and-protected-teardown-specification.md),
[ADR 0016](../../../../docs/adr/0016-venue-lifetime-is-bounded-with-protected-teardown.md),
[ticket 30 facts](../ticket-30/facts.md), [round 1](../ticket-30/round-1.md),
and [round 2](../ticket-30/round-2.md); [ticket 37](../ticket-37/recovery-specification.md),
[ticket 38](../ticket-38/accounting-specification.md), [ticket 39](../ticket-39/audit-specification.md),
[ticket 41](../ticket-41/change-specification.md), and
[ticket 36](../ticket-36/forwarder-specification.md), and
[ticket 32](../ticket-32/memory-specification.md).
Open gates: provider creation/inventory/time/billing APIs and their authenticated
receipt semantics; current prices/limits/coverage lag; actual profile resource
names and metric semantics; C4 rule/profile acceptance; off-cluster vault access
and read-back; chosen clock uncertainty; current Kubernetes/Forwarder grants;
and every intended-venue, tenant, native-client, model, paid, and cleanup proof.
No such call or acceptance occurred here.
