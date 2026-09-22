# Recovery, accounting and audit integration

2026-09-22. Planning review of tickets 37, 38 and 39. This record does not
implement the contracts or claim live acceptance.

## Shared boundaries

| Boundary | Required ordering and authority | Failure result |
| --- | --- | --- |
| Notification admission | Receiver durably records bounded source identity and dedupe/pending state before acknowledging | No successful acknowledgement when durable admission fails |
| Model launch | Recoverable journal/ledger admission and reservation precede a one-time launch claim | A crash in the launch gap holds the attempt; no inferred free retry |
| Mutation | Durable operation intent precedes dispatch; trusted Forwarder receipt/read-back supplies effect evidence | Missing response or local confirmation means uncertainty, not permission to replay |
| Cancellation | Revoke new dispatch and retain the original monotonic deadline | Already-dispatched effects and charges remain accountable |
| Private audit | Capture request/returned-response/revision provenance after removing forbidden secrets/identity | Loss is visible and disqualifies unsupported review; required OPS handling continues |
| Report review | Named human reviews immutable revision and evidence under a frozen rubric | Missing, disputed or expired evidence cannot become a new clean qualifying sample |
| Reset/destruction | Preserve unresolved effects, spend and private evidence with verified off-cluster handoff before destroying the only source | Reset does not zero spend, settle writes or extend raw-evidence retention |

The shared join is the Receiver-assigned attempt identity, with Run, rehearsal,
lifecycle and per-operation identities recorded only where applicable. An audit
artifact reference is neither a billing receipt nor confirmation of an OPS write.
Reported execution success, effect confirmation, billed spend, human diagnostic
review and overall qualification remain separate fields.

Ticket 37 and ticket 38 must either share a Receiver-owned transaction for launch
admission or define the recoverable handshake between separate stores. Separate
purposes do not imply atomic writes across separate databases. Audit storage has
a separate operator access boundary; its capture failures cannot wedge required
OPS handling. Sharing identifiers does not authorize shared raw content.

## Review checklist

Before retaining the specification batch, check each author against the other
two and the accepted ADRs:

- Same meaning for attempt, reservation, launch claim, operation and receipt;
  idempotent duplicate versus conflicting identity has an explicit outcome.
- Confirmed writes are never replayed; unknown writes reconcile before retry;
  optional Memory failure cannot repeat successful OPS work.
- Failed work survives newer pending work and repeated dedupe. Omission is not
  an Alert resolution. OPS remains authoritative after an Incident ages out.
- Retries count against diagnostics and their lifecycle while each provider
  charge appears once in weekly and aggregate totals.
- Estimates do not settle actuals, reservations do not cap exposure, and week
  rollover/restart cannot erase unsettled charges.
- Proposed concrete storage/capacity choices are labelled; all stores have
  explicit full/unavailable behavior rather than unbounded fallback.
- Raw audit retention, compact private verdict retention, recovery-journal
  retention and weekly accounting have separate purposes and expiry rules.
- A Report correction preserves original defects; a reviewer correction has a
  different provenance. Human review and qualification are not model judgments.
- Offline acceptance names actual integration boundaries and does not borrow
  proof from the isolated timing/transport fixtures.

External paid review is not part of this batch: experiment exposure remains
unreconciled. Internal peer review must be recorded as internal peer review.

## Review outcome

The three separately authored proposed contracts are retained together:
[recovery](ticket-37/recovery-specification.md),
[accounting](ticket-38/accounting-specification.md), and
[audit](ticket-39/audit-specification.md). Root reviewed all three against the
accepted ADRs. Terra independently reviewed the recovery/audit integration;
Luna authored recovery and audit and reviewed accounting separately from its
Terra author. These are internal reviews, not external provider opinions or
human Report adjudication.

Material corrections made during review:

- Keep one active Run and held Notification work distinct from a failed attempt;
  an ambiguous spawn crash never proves that no process started.
- Treat journal corruption as a reconstruction hold, retain boot/clock identity,
  and bound early cancellation without extending the original deadline.
- Distinguish the $3 reservation R from defensible total liability U. Reconcile
  multiple charge lines only with complete provider coverage; include applicable
  experiment support and venue exposure under the strict aggregate $50 ceiling.
- Attribute a retry's spend to both its lifecycle and diagnostics while counting
  it once in weekly and aggregate totals.
- Keep held admission out of launch-intent creation and carry the same R/U,
  coverage and hold references through recovery and audit.
- Cover every Run's audit bundle and every initial/update/resolution revision;
  no favorable revision replaces the complete history.
- Exclude hash/length envelope fields from their own canonical digest, require
  an independently trusted integrity anchor, and expire each artifact from its
  capture time. Later bundle activity cannot renew raw retention.

Validation covers local links, JSON illustration syntax, whitespace, scope and
source hashes. The examples are schematic, not a validated machine-readable
schema. No code changed, so the full suite was not repeated; the last code
baseline remains 794 passed and 36 skipped at `17037db`. No paid experiment,
runtime deployment, human Report grade or ticket closure is claimed.

Remaining work includes pinned concrete storage/ACL engines, complete executable
schemas and loss-code registries, enforced Receiver/Forwarder/capture boundaries,
and separate billing/native-client/tenant/venue acceptance. These are explicit
integration inputs, not a reason to stop the next independent specification
batch (tickets 35, 41 and 43).
