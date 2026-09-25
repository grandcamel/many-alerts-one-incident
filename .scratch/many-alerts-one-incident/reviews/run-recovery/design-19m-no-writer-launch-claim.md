# 19m: no-writer launch claim and service-grant map

Status: proposed local source design, 2026-09-25. Fixed point: `984f50c`.
Authority: accepted ADRs 0011–0013, tickets 36–38, reviewed 19h/19i/19j
designs, `(run_intent, 3)` replay, Forwarder lease source and 19l's closed
synthetic barrier. This is a replay contract, not a launcher or grant writer.

## Entry and authority boundary

The current Receiver ledger remains `population=unknown` and has no verified
`reservation_created` event. The journal's v3 confirmation and Run intent are
unqualified claims. No source in this unit registers or activates a Forwarder
grant, creates a process, releases a barrier, or calls a native client. The
future launch writer requires the separate current reservation qualification
from 19j, a post-`run_intent` exact-head recheck, current venue/readiness and
Forwarder evidence. Pure planning/replay cannot authenticate those facts.

Add `(launch_claim, schema_version=3)` only as a private Receiver-authored
record with no application writer. It follows exactly one outstanding v3 Run
intent in the current boot and is committed and read back *before* any child
creation. Replay labels it `outstanding_unqualified_launch_claim` and holds
launch/recovery; it never means that a child existed or is absent. A later
`spawn_attestation` and release observation must be separate records. A
duplicate launch claim or a launch claim after a restart is refused until an
explicit reviewed reconciliation transition exists.

## Exact claim shape

The event ID is a fresh canonical UUID. `ids` repeats the Run intent's
journal, admission, job, intent, attempt, reservation, Run and model lease
UUIDs. Data binds the current journal head `(commit_seq, record_digest)`, the
exact Run-intent event ID/digest/commit sequence, the current journal/Receiver
boot ID, one Forwarder generation ID, a fresh digest of a private startup
barrier token, and a monotonic origin sampled at or before process creation.
The origin is exactly the record stamp's `mono_us`; queue wait ends there.
Store the absolute work, flush and hard deadlines as checked additions of
270/290/300 million microseconds, with the same boot and no extension.

Store an exact sorted array for every service in Run intent (four mandatory,
optional Confluence). Each row repeats that service's journal lease claim UUID
and scope digest, and binds one actual Forwarder `LeaseGrant.lease_id` and its
conservatively rounded-down monotonic expiry in microseconds. Every actual
grant ID is distinct; the model-service row maps the accounting-linked UUID
claim but does not replace it with the opaque `lease_...` grant ID. Every
actual grant must match the expected Run, attempt, service, scope, current
Receiver boot and Forwarder generation. A future writer must first prove that
the journal stamp and Forwarder registry clock share the same monotonic
epoch/rate; the registry permits an injected independent clock, so integer
comparison alone cannot establish this. With that current same-domain proof,
the effective service deadline is `min(grant_expiry_us, work_deadline_us)`,
and a grant already expired at the origin is refused. Pure replay checks only
claimed arithmetic and cannot prove clock-domain identity. This record stores
no sentinel, raw token, command,
request/response body, credential, account identity or scoring data.

Forwarder grant IDs and generation are bounded opaque safe IDs, not UUIDs.
Only a future writer can establish that they were returned by the live
registry, are still `registered`, and have the exact read-back expiry. A
caller-supplied `LeaseGrant`, registry snapshot or matching record body is not
proof. That writer registers dormant grants first and performs a fresh
read-back on the **same continuous authenticated owner session**, then claims
and reads back the journal record under a specified store/control order.
Replacing the current owner session revokes its grants; any replacement,
disconnect, changed boot/generation or uncertain continuity before activation
revokes/holds rather than reusing the old mapping. Failed registration, changed scope,
uncertain read-back or journal append revokes every known grant and holds;
registered grants with no committed claim still require recovery revocation.
After the claim, the writer again qualifies current journal and ledger heads
before creating a blocked child. It attests stable containment identity and
commits `spawn_attestation`, activates intended grants, rechecks deadlines and
releases the barrier. If any step fails, contain and durably observe it; a
missing attestation alone never proves no child existed.

## Replay, capacity and compatibility

The pure planner validates the current boot, one Run-intent slot, exact
current-head basis, identical Run/service claim map, canonical and distinct
IDs, fixed service order, exact arithmetic and unexpired claimed grant
deadlines. It also rejects a new global dispatch hold or unresolved Run hold
and re-derives the original admission's current member count/digest against
the Run intent and v3 initial claim. A superseded original member holds
launch even when unrelated newer pending work exists. Replay re-derives every
field from the current projection and
record stamp and compares canonical bytes/digest. It cannot verify current
grant state, accounting, endpoint ownership, process absence or venue.

The claim occupies one ordinary-class slot. Use a separate tagged projection
and digest; preserve `rj.state.v1` and older reservation/Run-intent digests.
Before implementation, measure a five-service maximal record including
128-byte actual grant and generation IDs and maximum legal counters. Prefer
a 6,144-byte type-specific ceiling, reducing fields if needed; do not widen
older 2,048/4,096-byte private record limits. Its exact charge must fit
`ordinary_bytes`, preserving the configured recovery reserve for spawn,
effect and containment observations. Older binaries must fail closed with
`journal_schema_unsupported` on the new event; mixed-version reopen and
stopped inspection remain hold-only.

Acceptance includes forged recomputed records, superseded original members,
new dispatch and Run holds, wrong grant/service/claim,
duplicate grant, stale journal basis, wrong boot/generation, expired or
shortened grant, maximal size and ordinary-capacity edge, restart before and
after claim, and older-binary refusal. Independent Standards and Spec review,
focused tests, Ruff and the full local suite precede any source commit.
Native, provider, tenant, venue and paid acceptance remain NOT RUN.
