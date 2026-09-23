# Sanitized receipts and receipt-gated client response send

2026-09-22. Baseline `b7285cb`. Eleventh separately authorized local application
unit under the [approval record](../native-runtime-source-implementation-approval.json).
Preserve the four protected dirty files. No push, provider/native/tenant call,
actual credential, C2 retry, paid experiment or deployment. Full suite before
commit. Existing modules and their tests stay unchanged.

## Why this unit

The [Forwarder specification](../ticket-36/forwarder-specification.md) requires
that every response returned to a client is preceded by a sanitized
`ForwarderReceipt`, that capacity failure rejects new dispatch before bytes are
sent, and that dispatch states distinguish `NOT_DISPATCHED`, `FAILED`,
`DISPATCHED_UNKNOWN`, `PARTIAL` and `TRANSPORT_CONFIRMED`. Earlier units parse,
collect and serialize bytes but never send to a client. This unit makes receipt
ordering explicit and enforceable: a client response is written only when its
exact canonical bytes are named by a receipt already recorded in a bounded ledger.

It deliberately does **not** open an upstream connection, select routes, check
leases, consume dispatch permits or write a durable journal. Those remain the
next units (request-aware route policy, then atomic lease/permit/dispatch and
durable Receiver/recovery/accounting). The ledger's explicit transition calls are
the seam those units will call.

## Module 1: `grafana_jsm_sandbox/forwarder_receipts.py`

Constants: `MAX_RECEIPTS = 2048`, `MAX_RECEIPT_BYTES = 8192` (one record's
canonical JSON), `MAX_LEDGER_BYTES = 2 * 1024 * 1024`, `RETENTION_SECONDS = 310.0`,
`MAX_HANDLER_SECONDS = 40.0`, `MAX_REQUEST_BYTES = 2048 + 16384 + 262144`.

`DISPATCH_STATES = ("NOT_DISPATCHED", "FAILED", "DISPATCHED_UNKNOWN", "PARTIAL",
"TRANSPORT_CONFIRMED")`. `DELIVERY_OUTCOMES = ("pending", "sending", "sent",
"not_sent", "send_unknown")`.

`ReceiptError(ValueError)` carries one fixed `code`; messages never contain
caller values, digests of secrets, bodies or IDs.

### Transition protocol (the dispatch seam)

A handler follows exactly this order:

1. `reserve(...)` **before opening any upstream connection**. Capacity and input
   validation happen here; failure means no upstream open and no client response
   (the owner closes the connection without response bytes; there is no
   receipt-less send path).
2. `begin_connect(reservation)` immediately before opening the upstream
   connection (the point where a future dispatch permit is consumed).
3. `begin_dispatch(reservation)` immediately before the first possible upstream
   request write.
4. `finalize(reservation, ...)` once the outcome is known, before any client send.
5. `forwarder_response_send.send_response(...)` writes the receipt-named bytes.

Internal entry states: `reserved -> connecting -> dispatched -> finalized`.
Legal finalizations:

| From | Allowed `dispatch_state` |
| --- | --- |
| reserved | `NOT_DISPATCHED` only |
| connecting | `FAILED` or `DISPATCHED_UNKNOWN` (never `NOT_DISPATCHED`) |
| dispatched | `DISPATCHED_UNKNOWN`, `PARTIAL` or `TRANSPORT_CONFIRMED` |

`FAILED` therefore means the upstream connection attempt began (permit consumed)
but failed before the first request write. It is distinct from `NOT_DISPATCHED`
because the specification reserves the shorter Report path for proven
non-dispatch. A connecting-state caller that cannot prove no write occurred uses
`DISPATCHED_UNKNOWN`.

Closed reason codes, each with one fixed local client-response kind:

| State | Reason -> local response kind |
| --- | --- |
| NOT_DISPATCHED | `request_rejected`->`invalid_request`; `lease_denied`, `route_denied`, `permit_denied`->`denied`; `deadline`->`deadline`; `abandoned`->`unavailable` |
| FAILED | `connect_failed`, `upstream_tls_failed`->`upstream_failed` |
| DISPATCHED_UNKNOWN | `write_failed`, `receive_failed`, `malformed_response`, `abandoned`->`upstream_unknown`; `deadline`->`deadline` |
| PARTIAL | `response_incomplete`, `response_overflow`->`upstream_unknown` |
| TRANSPORT_CONFIRMED | `ok`-> the complete upstream response itself; `response_policy_rejected`->`response_rejected` |

A reason not listed for its state is rejected. Fixed local responses (public
`LOCAL_RESPONSES` mapping of kind -> `ParsedResponse`, and
`local_response(reason_or_kind)` helper as specified below), all
`application/json` with fixed small bodies containing no caller data:
`invalid_request` 400 `{"error":"forwarder_invalid_request"}`, `denied` 403
`{"error":"forwarder_denied"}`, `unavailable` 503 `{"error":"forwarder_unavailable"}`,
`upstream_failed` 502 `{"error":"forwarder_upstream_failed"}`, `upstream_unknown`
502 `{"error":"forwarder_dispatch_unknown"}`, `deadline` 504
`{"error":"forwarder_deadline"}`, `response_rejected` 502
`{"error":"forwarder_response_rejected"}`.

Provide `local_response_for(receipt: ForwarderReceipt) -> ParsedResponse` that
returns the fixed local response for a non-`ok` receipt and raises
`ReceiptError("upstream_response_required")` for a `TRANSPORT_CONFIRMED`/`ok`
receipt (whose client response is the upstream response the caller holds).

### Types

`ReceiptReservation`: frozen, `receipt_id: str` only. The ledger authenticates a
reservation by **object identity** with the instance it issued; an equal-valued
forged or copied instance is rejected (`reservation_unknown`).

`ForwarderReceipt` (frozen; every field nonsecret):
`receipt_id, generation, lease_id, attempt_id, operation_id (str|None), service,
route_id, request_digest, dispatch_state, reason, http_status_class (str|None),
response_digest (str|None), client_response_digest, request_bytes,
upstream_body_bytes (int|None), client_response_bytes, started_monotonic,
completed_monotonic`.

- `http_status_class` is `"2xx"`, `"4xx"` or `"5xx"`, present only for
  `TRANSPORT_CONFIRMED` (derived from the upstream `ParsedResponse.status`).
- `response_digest` and `upstream_body_bytes` are present only for
  `TRANSPORT_CONFIRMED` and derived from the complete upstream response.
- `client_response_digest`/`client_response_bytes` always describe the exact
  canonical bytes approved for client return: `serialize_response(upstream)` for
  `ok`, otherwise the fixed local response for the reason.
- Digests are lowercase SHA-256 hex. Public `response_digest(response:
  ParsedResponse) -> str` returns SHA-256 of `serialize_response(response)`;
  invalid responses raise `ReceiptError("invalid_response")`.
- Receipts exclude URLs/paths/queries, headers, sentinels, credentials and bodies.
  They are dispatch correlation only: not external-effect confirmation, not
  billing evidence and not a durable journal record.

### `ReceiptLedger(*, generation: str, clock=time.monotonic)`

One lock serializes all state. `generation` is a safe opaque ID (same grammar as
`forwarder_leases`: 1-128 chars of `[A-Za-z0-9._-]`). `clock` must be callable.

- `reserve(*, lease_id, attempt_id, service, route_id, request_digest,
  request_bytes, deadline, operation_id=None) -> ReceiptReservation`. IDs use the
  safe-ID grammar; `service` must be in `SERVICE_PROFILES`; `route_id` safe ID;
  `request_digest` exactly 64 lowercase hex; `request_bytes` exact `int` (not
  bool) in `0..MAX_REQUEST_BYTES`; `deadline` exact int/float (not bool), finite,
  `now < deadline <= now + MAX_HANDLER_SECONDS`. `started_monotonic = now`.
  Capacity: reject `capacity_records` when retained entries (reserved or
  finalized) `>= MAX_RECEIPTS`; reject `capacity_bytes` when the sum of
  per-entry charged bytes plus this entry's charge exceeds `MAX_LEDGER_BYTES`.
  Each entry's charge is computed at reservation as the canonical JSON size of
  its **worst-case finalized record** (maximum-length placeholders for every
  not-yet-known field, including delivery outcome and byte counts), so later
  finalization/delivery can never exceed the charge. Assert the charge is
  `<= MAX_RECEIPT_BYTES`. Never evict a retained entry to admit another.
- `begin_connect(reservation)`, `begin_dispatch(reservation)`: exact next-state
  transitions only; refused at/after the reservation deadline
  (`deadline_expired`) and for unknown/finalized reservations.
- `finalize(reservation, *, dispatch_state, reason, upstream_response=None) ->
  ForwarderReceipt`. Enforce the transition and reason tables.
  `TRANSPORT_CONFIRMED` requires an exact `ParsedResponse` (revalidated through
  `serialize_response`); every other state requires `upstream_response is None`.
  Refused at/after the reservation deadline. Stores the receipt; returns it.
- `claim_delivery(receipt, *, client_response_digest) -> DeliveryClaim`: requires
  the **identical** receipt object recorded by this ledger (not an equal copy),
  compares the caller's wire digest in constant time with the ledger's
  **private record** (never with the caller's instance), requires delivery
  `pending`, then sets `sending` and returns a fresh identity-authenticated
  `DeliveryClaim`. Codes: `receipt_unknown`, `receipt_mismatch`,
  `delivery_claimed`; a rejection leaves the entry unchanged.
- `complete_delivery(claim, *, outcome, bytes_sent)`: only the exact issued
  claim (`claim_unknown`), only from `sending` (`delivery_completed`); outcome
  in `sent`/`not_sent`/`send_unknown`; `bytes_sent` exact int in
  `0..client_response_bytes`, equal to it for `sent`, `0` for `not_sent`.
- The ledger hands the caller a `ForwarderReceipt` used only for identity and
  keeps an equal private copy; retention, snapshots and delivery checks read
  only the private copy, so in-place mutation of the caller's frozen instance
  cannot alter ledger state or the bytes a claim authorizes.
- `contains(receipt) -> bool`: identity check against the recorded instance.
- `snapshot() -> dict`: fresh nonsecret projection: generation, ledger state
  (`ready`/`held`), counts by entry state, charged bytes, and a tuple of per-entry
  metadata (receipt fields or reservation metadata plus entry state and delivery
  outcome). No bodies, headers or sentinels exist to leak.

Abandonment sweep (run under the lock at the start of every public operation,
after reading the clock): any unfinalized entry whose deadline has passed is
finalized conservatively with reason `abandoned`: `reserved` ->
`NOT_DISPATCHED`; `connecting`/`dispatched` -> `DISPATCHED_UNKNOWN`. Such a
receipt is recorded like any other; the late handler's subsequent calls fail.

Retention: finalized entries are pruned once `now - completed_monotonic >=
RETENTION_SECONDS`, freeing count and charge. Unfinalized entries cannot outlive
their (<=40 s) deadline because the sweep finalizes them first.

Clock: exact finite non-negative int/float, non-regressing. A clock exception,
invalid value or regression permanently holds the ledger (`ledger_held` for
every later mutating call, including finalize and delivery calls). `snapshot()`
remains readable when held without advancing the clock.

## Module 2: `grafana_jsm_sandbox/forwarder_response_send.py`

`ResponseSendError(ValueError)` with fixed `code`. `DeliveryResult` frozen:
`receipt_id: str, outcome: str, bytes_sent: int`.

`send_response(connection, ledger, receipt, response, *, deadline) -> DeliveryResult`:

1. Claim the connection permanently under a module lock using marker
   `_maoi_forwarder_response_send_claimed` **before** any validation (a failed
   attempt still consumes the socket), after checking `type(connection) is
   ssl.SSLSocket`. Then require `fileno() >= 0`, `server_side is True`,
   `context.protocol == ssl.PROTOCOL_TLS_SERVER`, `version()` in TLS 1.2/1.3.
   Failure -> `invalid_connection` / `connection_claimed`.
2. `ledger` must be exactly a `ReceiptLedger`; `receipt` exactly a
   `ForwarderReceipt`; `deadline` finite, future, `<= now + 40`.
3. `wire = serialize_response(response)` (`invalid_response` on failure).
4. `claim = ledger.claim_delivery(receipt, client_response_digest=sha256(wire))`;
   the ledger's locked comparison with its private record replaces any check
   against the caller's receipt fields. Map `ReceiptError` codes to
   `receipt_unknown` / `receipt_mismatch` / `delivery_claimed`, and every other
   ledger rejection to `ledger_held`.
5. Save the prior socket timeout. Write `wire` in chunks of at most 16384 bytes
   via `connection.send`; before each send compute remaining time (clock check,
   fail `deadline_expired`), set timeout `min(10.0, remaining)`; after each send
   check the clock again and reject a send that took `>= 10.0` s. Accept a
   partial count (continue with the unsent remainder); reject a non-int, zero,
   negative or oversized count. No retry after an exception; no close, shutdown
   or unwrap.
6. Delivery outcome: all bytes written -> `sent`; failure before the first
   `send` call begins -> `not_sent`; any failure after the first `send` call
   began -> `send_unknown` (TLS may have emitted bytes), with the accepted byte
   count. Offer it to `ledger.complete_delivery(claim, ...)` in every path after
   the claim, including after an interruption (`BaseException`), then restore
   the prior timeout even if recording was interrupted.
7. A primary failure or interruption always propagates unchanged. Only after an
   otherwise complete send does an unrecorded outcome raise
   `delivery_unrecorded`, then a failed restore raise `timeout_restore_failed`
   (delivery remains recorded as `sent`). An asynchronous interruption between
   the ledger's claim and its return leaves that delivery `sending` (unknown)
   until retention prunes it.

Root revision after four review rounds: the delivery claim moved into the ledger
(digest compared with the private record, identity-authenticated
`DeliveryClaim`) and outcome precedence is structural (fixed-code raises follow
the `try/finally`), replacing caller-supplied claim tokens and precedence flags.

`sent` means the local TLS layer accepted every byte; it is not proof the client
read them. The caller owns the socket and must close it after this one response.
The caller also binds `receipt.service` to its listener; this function cannot
attest service identity from the socket.

## Ownership and validation

- Implementer A owns `forwarder_receipts.py` and `tests/test_forwarder_receipts.py`.
- Implementer B owns `forwarder_response_send.py` and
  `tests/test_forwarder_response_send.py` (deterministic fake-socket tests).
- Tester C owns `tests/test_forwarder_response_send_integration.py` (real local
  TLS through the existing `FixedTLSListener`/`connect_service_tls` fixtures:
  request collection, NOT_DISPATCHED 403, TRANSPORT_CONFIRMED synthetic upstream
  `ParsedResponse` forwarded byte-exact and collected by `receive_response`, 1 MiB
  chunked body, digest mismatch sends nothing, stalled reader with small buffers
  reaches `send_unknown` within the deadline) and
  `tests/test_forwarder_receipts_adversarial.py` (spec-derived attempts to break
  the ledger: forged reservations/receipts, transition/reason matrix, capacity
  before dispatch, abandonment, retention, clock faults, concurrency).
- Independent reviewers bind final hashes before commit. Root owns docs,
  evidence, focused and full-suite execution, Ruff and `git diff --check`.

Not qualified by this unit: upstream connection/permit/lease coupling, route
policy, durable journal/accounting, SSE, native clients, real upstreams,
deployment or any external effect.
