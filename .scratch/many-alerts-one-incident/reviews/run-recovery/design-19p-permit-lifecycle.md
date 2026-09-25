# 19p: isolated identity-owned permit lifecycle, with no authorization path

Status: proposed local source design, 2026-09-25. Fixed point: `fdd0f95`.
Authority: accepted ADRs 0011–0013, tickets 36–38, reviewed 19h/19k
contracts and current `forwarder_dispatch` L1/L2/receipt source.

## Present boundary

The active route matcher selects only `jira.issue.get` and `jira.search`,
which are read-only even though search uses POST. Every specified mutation
and `anthropic.messages` route remains unavailable. Both Forwarder permit
fences deny a permit-required route, and the Receiver has no authenticated
authorization endpoint, positive reservation or effect-intent writer.
This unit must not change those facts or install a token in a live gate.

## Mechanical lifecycle contract

Add an isolated in-memory owner that validates a proposed permit's **shape
and use order** after a future authenticated Receiver reply. It does not
authenticate that reply, persist authority or authorize dispatch. Any caller
can stage a binding in this local component, so a positive result is never
dispatch authority. No production route, gate or exchange imports it in
this unit.

A frozen binding includes bounded opaque permit/boot/generation/Run/attempt/
operation/effect-intent/grant/flight IDs; exact service and route ID; canonical
prepared-request and sanitized target digests; and an absolute monotonic
expiry in microseconds. No body, target string, credential or account
identity is carried. Route service must match the fixed catalog. The future
adapter must prove same-clock-domain conversion and a deadline no later than
the effective grant/work/control deadline; this model checks only the
integer relation supplied to it.

One `PermitBook` owns exact `eq=False` handle instances and a finite map of
their private phase. It stages at most 32 simultaneously open bindings and
at most 2,048 total bindings over that book's lifetime, including closed
tombstones. It rejects duplicate permit and logical-operation IDs even
after close; tombstones are not pruned. At 32 open handles, staging is
refused until an owned handle closes and frees an open slot. Exhausting the
2,048 lifetime cap refuses all further staging until a newly qualified
generation; it never silently evicts tombstones.
The book returns an opaque handle. A copied,
reconstructed or foreign handle is unknown even if its fields match. The
book's phases are `offered`, `consumed_l1`, `write_admitted` and `closed`.
All transitions are serialized by the book's own lock, with no callback or
I/O while locked; a future integration must review its order with gate `G`.
The book snapshots a staged binding before storing it and separately snapshots
the expected binding before either fence acquires the lock. It validates exact
scalar types on those private copies. Mutation of a caller-owned dataclass,
including a forced mutation of frozen fields, cannot retag an owned entry or
change a comparison while the lock is held.

L1 receives the exact owned handle, current expected flight binding, boot,
generation and monotonic time. It moves `offered` to `consumed_l1` only for
an exact, unexpired match. Any attempted mismatch, stale generation,
expiry or repeated L1 closes a known handle. L2 accepts only that same
owned, consumed handle while current and unexpired, then marks
`write_admitted` once; it never restores an offered permit or asks Receiver
again. An attempted mismatch or expiry at L2 closes it. A second L2 cannot
pass. The owner can explicitly close a known handle after an independently
handled receipt or on revocation; close merely retires local permit use and
does not claim an external outcome. A `closed` state is absorbing. A newly constructed book cannot
recognize a handle from a prior book, even when its binding values match;
the live Forwarder must discard the whole book on restart. Staging a
logically identical claim in a new book is still possible and must be
prevented by Receiver journal/effect reconciliation before authenticated
installation. The local book does not prove that reconciliation.

The book returns only `l1_pass`, `l1_denied`, `l2_pass` or `l2_denied` with
its current phase. It does **not** classify a trusted Forwarder receipt, prove
zero bytes, create an effect-intent record, or qualify ADR 0012's shorter
Report path. L1 and L2 receipt semantics remain the reviewed 19k contract:
pre-L1 `NOT_DISPATCHED` and post-L1 `FAILED` need separate trusted ledger
finalization, while uncertain connect/first-byte position holds.

## Local acceptance and later integration

Tests cover exact pass, copied/forged/foreign handles, replay within one
book, wrong boot/generation, route, grant, operation, flight, request or
target digest, expiry at both fences, duplicate stage both before and after
close, 32-open and 2,048-total capacity, second L1/L2 and absorbing
closure. They assert no import from the live
Forwarder gate/exchange and no route availability change. Fixed error codes
contain no caller content. This is a source/synthetic transition test only.

Later integration must use an authenticated Receiver-owned endpoint,
current journal and independently verified ledger qualification, durable
effect intent/exposure read-back, reviewed lock ordering and exact receipt
evidence. This isolated book cannot stand in for any of these. Native
client, provider, tenant,
venue, paid and human acceptance remain NOT RUN.
