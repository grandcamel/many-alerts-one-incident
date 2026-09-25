# 41a: unqualified Change request screen

Status: reviewed design-only deferral, 2026-09-25. Ticket 41 remains open.
Authority: accepted ADR 0015 and the proposed Change coordinator
specification. This record states the limits of an offline negative screen. It
does not create a Change, accept an action, serialize the global coordinator,
authorize undo or write a stage intent.

## Input and identity

A future source-only checker might receive canonical request bytes under the
proposed 8 KiB request cap, a caller-supplied bounded snapshot of prior `(change_id, request_id,
request_digest)` identities, a caller-supplied active/unknown action identity,
and an explicit snapshot-completeness flag. It must compute the request digest
from the supplied bytes, never accept a caller-supplied digest as proof of
payload equality. Before a checker is implemented, the exact fixed-field
candidate grammar, per-field bounds, identity-count/byte caps and snapshot
ownership must be pinned and reviewed. Canonical JSON alone cannot establish
that a payload contains no secrets. The request body must be closed and free of credentials,
personal identity, Ground truth, arbitrary patches or dynamic targets. The
current target/resource/variant allowlist cannot be declared valid by this
screen without an independently reviewed current manifest and coordinator
principal. Any local schema is a synthetic candidate grammar, not the native
coordinator request contract. **No checker implementation is approved by this
draft.**

The screen can report only fixed findings: malformed candidate, conflicting
reuse, exact replay unqualified, active/unknown hold, incomplete snapshot
hold, or new candidate unqualified. Every finding carries `hold=true` and no
`ACCEPTED`, `DISPATCHED`, `COMPLETE`, available slot, validated target or
confirmed undo meaning. A duplicate response is merely a comparison to the
supplied snapshot; it is not durable progress. An empty snapshot cannot prove
that no action exists unless a trusted, complete journal owns and verifies it.
Exact replay requires the same `(change_id, request_id, computed_digest)`
tuple. Reusing either ID with a different paired ID is a conflict even when
the digest matches; reusing the pair with a different digest also conflicts.
Undo remains held while an injection dispatch is unresolved, regardless of
its apparent priority. A timeout or lost response is still unknown, not a
negative effect.

## Positive integration gate

ADR 0015 requires one global action lock, immutable request and stage IDs,
durable request/decision and pre-dispatch intent, fresh resource value/version
checks, linked undo, restart reconciliation and separate write, rollout,
served-value and application-evaluation observations. An in-memory slot or
caller-supplied identity list does not provide those guarantees. Before any
positive coordinator implementation, pin and review the physical journal,
100 MiB/10 MiB recovery reserve and retention, current rendered target and
variant allowlist, authenticated operator principal and endpoint, exact
Kubernetes UID/version/field preconditions, producer/query identity and
intended-venue durability. Human/operator emergency undo and qualification
remain separate. The protected #19 provider path is not a substitute.

## Offline decision examples for a later checker

| Supplied prefix | Only safe local finding |
| --- | --- |
| Same Change/request ID pair and identical computed canonical digest | `exact_replay_unqualified`, held. |
| Reused Change or request ID with a different paired ID or digest | `identity_conflict`, held. |
| Any active or unknown action, including a proposed linked undo | `active_unknown_hold`, held. |
| Snapshot incomplete/truncated or not verified by its owner | `snapshot_unqualified`, held. |
| No collision in a supplied empty or complete-looking snapshot | `new_candidate_unqualified`, held; no global vacancy claim. |

This design-only unit makes no checker or synthetic code run, native/tenant mutation,
provider/model call, paid attempt, deployment, protected export or human
decision. All such acceptance is **NOT RUN**.
