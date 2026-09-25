# 19n: guarded spawn, release and containment evidence

Status: proposed local source contract, 2026-09-25. Fixed point: `9b57f0e`.
Authority: accepted ADRs 0012, 0013, 0016 and 0017, ticket 37, reviewed
19d/19h/19m contracts, and the 19l closed synthetic barrier. This document
starts no Run and grants no dispatch, lease or accounting authority.

## Present boundary

The journal has a replayable `(launch_claim, 3)` and no application writer.
It is an unqualified claim: no grant read-back, child, stable containment
identity or release is established. The Receiver ledger still has
`population=unknown` and no authenticated reservation. The 19l fixture
proves only that its fixed inert child obeys its test pipe protocol. It does
not prove an intended-venue child cannot escape, that a recycled numeric
PID/group is stable, or that parent loss implies no prior release. A
`spawn_attestation` record must not be interpreted as process absence or
effect absence.

## Future writer order

1. Under the reviewed ownership order, qualify the exact current journal
   and independently verified ledger heads, admission, reservation, Run
   intent, launch claim, same-boot clock, intended venue, approved reference
   manifest/page-version scope and revocation state, Forwarder owner
   session/generation and every dormant service grant. The 19m claim must
   already be durably read back. An uncertain read-back holds.
2. Before any child creation, allocate and durably read back a protected
   containment anchor keyed uniquely by the exact launch-claim, Run and
   attempt IDs. Its opaque locator must be recoverable by that key after
   Receiver death, even before child identity is filled in. Refuse a
   collision, uncertain registration or an anchor that cannot bind every
   descendant. Create one child only inside that anchor and behind a
   fail-closed inherited barrier. This ordering and containment need
   intended-venue proof; the 19l fixture does not supply it. The child's
   first code path must block before client code and any external route. Capture a
   one-use blocked acknowledgment tied to the private barrier token; a
   parent-side timeout, EOF, malformed reply or changed child identity
   closes the barrier and begins containment. The token itself never enters
   the journal.
3. Verify a **stable containment witness** for the exact child and all
   descendants that may retain work or pipes. The witness must distinguish
   the original group from a recycled numeric identifier after root reap,
   remain queryable through the hard deadline and recovery inspection, and
   support a bounded absence result. A PID, PGID, SID, `killpg(..., 0)` or
   successful signal alone is insufficient. The concrete witness format and
   intended-venue custody remain an explicit gate; no local synthetic test
   establishes them. The witness needs a durable, bounded opaque locator
   whose separately protected registry can recover the exact original
   object after Receiver death. The registry also needs an exact
   launch-claim/Run/attempt lookup when attestation was never appended. A
   locator match also requires the recorded
   identity digest and verifier version to match that registry entry; a
   reused locator or missing registry holds, never selects a new group.
4. Append/read back `spawn_attestation` with the immutable launch-claim
   event/digest, Run/attempt, same boot and monotonic observation, blocked
   acknowledgment digest, bounded witness kind, opaque recoverable locator,
   identity digest, and verifier version. The writer must read back the
   separately durable witness registry entry before this append. It records
   **identity observed while blocked**, not
   release, confinement, child absence or readiness. The writer must hold
   if its observation is stale or if any current head, owner session, grant,
   deadline, approved reference scope/version, revocation, cancellation or
   venue predicate changes before release. Revocation observed while the
   child is blocked closes the barrier and holds immediately, even before a
   durable cancellation observation can be appended.
5. Activate only the intended grants on the same continuous Forwarder
   owner session and read back each state. Any replacement/disconnect
   revokes/holds. Before sending the release byte, append/read back a
   distinct one-use `release_intent` bound to the attestation, exact grant
   activation read-backs and remaining same-boot deadline. Because this
   append advances the journal head, freshly qualify that new committed
   head and the current independent ledger relation under the same
   ownership order; also recheck approved reference manifest/page-version
   scope and immediate revocation, venue, grants, deadlines and the
   barrier/child identity. Send exactly one
   release byte, then append a `release_observation` only on a trusted
   barrier acknowledgment. An acknowledgment proves only that the child
   crossed the barrier; it does not prove an effect or output. If the byte
   or observation may have occurred but its durable result is missing,
   state is release-unknown. Neither an intent nor a missing observation
   proves the child stayed blocked.
6. On failure at any point, close the barrier, durably mark each revocation
   or signal action **before** invoking it, and append its result afterward.
   Verify child/group absence and actual pipe EOF independently, along with
   current Forwarder closeout. If a pre-action append fails, attempt
   bounded best-effort containment and revocation while latching journal
   uncertainty. Never turn a best-effort action into a clean durable result.

## Replay and crash classifications

Replay binds every proposed record to the exact prior event, boot and
monotonic order. It rejects duplicate/conflicting attestation or release
transitions, reused action IDs, unknown witness versions, stale head and
changed service mapping. Inspection keeps separately tagged states:

| Durable prefix | Required recovery interpretation |
| --- | --- |
| Launch claim only | Child creation/absence unknown; inspect barrier, orphan and grants. |
| Attestation only | Identity was observed blocked at that instant; release/absence unknown. |
| Release intent only | Byte may or may not have crossed; execution unknown. |
| Release observation | Child crossed barrier; effects still require exact intents, receipts and OPS reconciliation. |
| Action intent without result | Action may have run; do not silently repeat it. |
| Action result without verified absence, EOF and Forwarder closeout | Containment remains unconfirmed. |

On every restart, old grants and permits are invalid and dispatch holds
before inspection. If only a launch claim is durable, query the protected
anchor registry by exact launch-claim/Run/attempt keys; a missing or
incomplete entry does not prove no child was created. Resolve a recorded
opaque witness locator through its
separately durable protected registry, verify its recorded identity digest
and version, then obtain a fresh stable-identity/absence observation and
current Forwarder closeout. Missing or mismatched registry custody holds
until independent operator reconciliation; a missing local
handle, expired barrier token, root exit, signal success or stale control
response cannot clear the hold. An operator's reconciliation is an
append-only transition with exact evidence, not deletion of an earlier
record. The outstanding Run slot remains during normal execution; it is not
itself a global dispatch hold. Restart, failed containment, uncertain append
or other ambiguous evidence latches a global dispatch hold until separately
reviewed terminal, effect, accounting and containment predicates pass. A
per-job Run hold, if needed, requires its own durable transition;
first-attempt launch does not imply one already exists.

## Record and capacity boundary

These are proposed semantic records, **not yet registered journal types**.
The future source plan must settle a versioned schema, exact maximum body
sizes, ordinary versus recovery charges, a finite per-Run action/observation
count and reserved worst-case room for terminal/effect/reconciliation
evidence. No new ordinary launch may consume the recovery reserve. Each
record contains bounded IDs, fixed codes, counters and digests only: no raw
token, command, environment, stream, client body, credential, account
identity, prompt, scoring data or Ground truth. Preserve v1 records/digest
and older-binary `journal_schema_unsupported` refusal. Test forged
recomputed records, mixed-version reopen, exact duplicate/conflict, capacity
edges, all crash prefixes above and a stopped real-store read-back.

Before adding an application writer or a production launcher, resolve the
stable witness and barrier semantics in the intended venue, including
parent death and root-reap/descendant survival, and independently verify
accounting/grants/clock-domain/readiness. Local source can still implement
strict no-writer replay and a pure state reducer, explicitly labelled
unqualified, after the schema and capacity plan receive independent review.
Native, provider, tenant, paid, deployment, venue and human adjudication
remain NOT RUN.
