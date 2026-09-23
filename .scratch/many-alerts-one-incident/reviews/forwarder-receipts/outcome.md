# Sanitized receipts and receipt-gated send outcome

2026-09-22. PASS for the eleventh separately authorized local application unit,
baseline `b7285cb`. [validation.json](validation.json) records the final verdict and
validation evidence. The work is local only: nothing was pushed and no planning
ticket was closed.

`forwarder_receipts.ReceiptLedger` records one sanitized `ForwarderReceipt` per
handled request before any client response bytes. Its explicit transitions,
`reserve`, `begin_connect`, `begin_dispatch` and `finalize`, are the seam for
the later lease, permit and upstream units.

**Dispatch states and reasons**
- A reservation that never began connecting can only become `NOT_DISPATCHED`.
- After `begin_connect` it can only become `FAILED` or `DISPATCHED_UNKNOWN`. `FAILED` keeps the specification's shorter Report path, which needs proven non-dispatch, distinct from a consumed permit.
- After `begin_dispatch` it becomes `DISPATCHED_UNKNOWN`, `PARTIAL` or `TRANSPORT_CONFIRMED`.
- Closed reason codes select fixed local JSON responses, except `ok`, which returns the complete upstream response.

**Receipt contents.** Receipts contain correlation IDs, route, request digest, state, reason, optional status class, upstream digest and length, and the digest and length of the exact client bytes. They exclude URLs, headers, sentinels, credentials and bodies.

**Ledger bounds**
- At most 2,048 entries and 2 MiB. Each reservation is charged the size of its worst-case snapshot record, at most 8 KiB.
- Capacity failure happens at `reserve`, before any upstream connection. There is no receipt-less send path.
- Nothing is evicted to make room.
- An unfinalized entry past its deadline becomes `abandoned` (`NOT_DISPATCHED` or `DISPATCHED_UNKNOWN`), stamped at the deadline.
- Retention is 310 seconds.
- Clock faults hold the ledger permanently.
- Reservations, receipts and delivery claims are authenticated by identity. A private record copy is authoritative.

**Sending.** `forwarder_response_send.send_response` claims a server-side TLS socket permanently, then serializes the response. The ledger compares the digest with its private record and claims delivery in one locked step. Writes go in timed chunks of at most 16 KiB without retry. The outcome is recorded (`sent`, `not_sent` or `send_unknown` with accepted bytes) and then the timeout is restored. Primary failures and interruptions take precedence over `delivery_unrecorded` and `timeout_restore_failed`. The owner closes the socket.

**Review and redesign**
- Sonnet workers implemented the modules and tests. Opus lens reviewers and Sonnet adversarial verifiers ran four rounds; 55 findings were confirmed, and the first 47 were fixed.
- The root then redesigned the delivery seam. The ledger-private digest comparison and structural precedence replaced caller claim tokens and closed a check-then-claim race.
- A second workflow adapted every test and fixed 9 more confirmed findings.
- The root closed the remaining test gaps with deterministic lock-probe, consumption and ordering tests. Each was proven by a targeted mutant.
- A fresh reviewer then bound the final hashes with verdict PASS. See [review](review.md).

**Validation**
- Unit tests: **631 passed**, three consecutive runs.
- [Focused Forwarder suite](focused-tests.txt): **1189 passed**.
- [Full suite](full-suite.txt): **2063 passed, 36 skipped in 131.68s**, exit 0.
- Ruff, compile and `git diff --check` pass.

**Residual limitations** (accepted, listed in the review):
- retention is lazy;
- the send deadline is independent of the reservation;
- asynchronous interruption windows leave a delivery `sending`;
- `not_sent` consumes the receipt;
- `sent` means local TLS acceptance only;
- the stalled-reader test relies on small socket buffers.

**Not qualified:** upstream connection, lease check, route policy, dispatch permit, durable journal or accounting, SSE, native clients, real upstreams and deployment.

**Not performed:** no provider, tenant or native call; no actual credential, C2 retry, paid experiment, deployment or human Report adjudication. The four protected dirty artifacts are unchanged and unstaged.

**Next:** request-aware route policy (unit 12), then lease, permit and upstream coupling with durable Receiver, recovery and accounting. The reviewed route plan is in [../forwarder-routes/implementation-plan.md](../forwarder-routes/implementation-plan.md). Planning ticket 36 remains open.
