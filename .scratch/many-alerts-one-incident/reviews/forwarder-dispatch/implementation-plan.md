# Atomic dispatch gate, write fence and receipt-gated one-request exchange (unit 13a, revision 2)

2026-09-22. This is the thirteenth separately authorized local application unit under the [approval record](../native-runtime-source-implementation-approval.json). It is split in two:
- **13a**, this plan, is fully specified.
- **13b** adds the real upstream TLS connector and is sketched under "Deferred".

Revision 1 synthesized three competing designs and two judge panels. Its base is the judged winner, `atomic-first`, with the judges' grafts applied; "Judge findings resolved" maps those findings. Revision 2 resolves all 20 critic issues and rejects none. "Critic issues resolved (revision 2)" maps each issue to the section that changed. Every source fact cited below was re-read against the working tree on 2026-09-22.

**Baseline.** The baseline is the reviewed local commit of unit 12: `forwarder_json.py`, `forwarder_routes.py` and their four test files. 13a does not start before that commit exists. It consumes these unit-12 names exactly as routes plan revision 2 defines them:
- `ScopeManifest` (`.service`, `.run_id`, `.attempt_id`, `.digest`, `.canonical_bytes()`);
- `require_manifest_binding` and `RouteConfigError`;
- `RoutePolicy.parser_options`, `.route` and `.check_response`;
- `RoutedRequest` (`route_id`, `service`, `scope_digest`, `policy_digest`, `request_digest`, `requires_permit`);
- `RoutePolicyError` (`code`, `route_id`, `receipt_reason`, `request_digest`);
- `UNMATCHED_ROUTE_ID`, `denied_request_digest`, and `ROUTE_CATALOG` (`RouteStatus.state`).

If the committed unit-12 code differs from any of these, root reconciles this plan before implementation starts.

Root reconciliation, 2026-09-23: the unit-12 commit exports every name above with the listed fields and attributes (`RoutePolicyError.code/route_id/receipt_reason/request_digest`, `RoutedRequest` fields, `UNMATCHED_ROUTE_ID = "unmatched"`), and its golden digests equal the values this plan cites.

**Protected state.**
- Preserve the four protected dirty files: issue 19, `planning-frontier-2026-09-18.md`, and the two ticket-19 `c2-ingestion-*` files.
- Ticket 19 C2 is out of scope.

**Out of bounds.**
- No push or deployment.
- No provider, native or tenant call.
- No real credential, tenant origin or CA.
- No DNS lookup and no paid experiment.
- Neither new module opens a socket. The only upstream is an injected trusted connector, and source ships none.

**Rules.**
- Existing modules and their tests stay unchanged, except the two additive seams listed under "Existing-module changes".
- Neither new module has a `raise` statement inside an `except` block; this is AST-checked. The unit-12 error discipline applies unchanged:
  - handlers only record a fixed code;
  - a fresh error is raised after the `try` statement, with `from None`;
  - nothing is re-raised;
  - when raised outside a caller's handler, every error has `__cause__ is None`, `__context__ is None` and `args == (code,)`.
- Both new modules have exact-name import allowlists, listed below and AST-checked.
- Run the full suite before the one local commit.
- Root saves this plan as `.scratch/many-alerts-one-incident/reviews/forwarder-dispatch/implementation-plan.md`.

## Why this unit

Unit 12 documents the lease and receipt seam but does not compose it (routes plan L611-636). Its Deferred item 1 is assigned to this unit:
- the sentinel store;
- the atomic final lease check coordinated with revocation;
- the ledger transitions;
- an inbound byte count.

The specification and docs require these properties:
- revocation atomically prevents new dispatch, but may leave an already transmitted request `DISPATCHED_UNKNOWN` (spec L155-157);
- the permit is consumed atomically with the final lease check before the first possible upstream write (L231-233);
- `check` does not authorize a later network write (docs/forwarder-control.md L39-41);
- a closeout failure is `UNKNOWN` and holds dispatch (L162-163);
- lease records are byte-accounted (L158-159);
- phase limits are 5/10/20 s, and the absolute handler limit is 40 s clipped to the lease (L175-178);
- nothing is replayed (L212-217);
- capacity failure rejects before bytes are sent (L424-425).

`LeaseRegistry.check` is an instantaneous observation taken under the registry's private lock. Every retirement is serialized under that same lock: revoke, control EOF, Receiver replacement, hold, expiry and heartbeat loss. 13a turns two moments into linearizable steps without changing the registry:
- **dispatch initiation**: `admit` (L1);
- **first possible upstream write**: the `begin_write` fence (L2).

For each step, one gate lock `G` is held across the authorizing `check` and the ledger transition it justifies. Nothing runs in between except the three monotonic clocks: no I/O and no other injected code. Every observer that must see in-flight work also takes `G`.

13a also composes the receipt-gated one-request exchange over an already accepted inbound TLS socket.

## Module 1: `grafana_jsm_sandbox/forwarder_dispatch.py`

This module is the dispatch authority for one Forwarder generation bundle: exactly one `LeaseRegistry` and one `ReceiptLedger` with equal `generation`. Each registry and each ledger belongs to at most one gate.
- It performs no I/O. It never holds its lock while calling injected code, except the clocks (see "Clock contract").
- Flights never retain a `RoutedRequest`, request, response or body.
- Target: 850 lines or fewer, raised from 750 to cover overdue tracking, authority claims, byte accounting and record verification. Exceeding it is a review finding.

**Imports** (AST-checked by exact name).
- **stdlib:** `__future__` (`annotations`), `collections.abc` (`Callable`), `dataclasses` (`dataclass`, `field`), `hashlib`, `hmac`, `math`, `secrets`, `threading`, `time`.
- **relative:**
  - `.forwarder_leases` (`LeaseError`, `LeaseGrant`, `LeaseRegistry`);
  - `.forwarder_receipts` (`MAX_HANDLER_SECONDS`, `ForwarderReceipt`, `ReceiptError`, `ReceiptLedger`, `ReceiptReservation`);
  - `.forwarder_routes` (`ROUTE_CATALOG`, `RouteConfigError`, `RoutedRequest`, `ScopeManifest`, `require_manifest_binding`);
  - `.forwarder_http_response` (`ParsedResponse`);
  - `.forwarder_services` (`SERVICE_PROFILES`).
- **Forbidden anywhere in the module:** `socket`, `ssl`, `select`, `os`, `subprocess`, `importlib` and `__import__`.

### Constants

| Name | Value | Source |
| --- | --- | --- |
| `MAX_SCOPE_ENTRIES` | `1024` | equals `forwarder_leases.MAX_RECORDS`; spec L158-159 |
| `MAX_SCOPE_BYTES` | `2 * 1024 * 1024` | local byte budget for the store (spec L158-159 "byte-accounted"); the same figure as `MAX_LEDGER_BYTES` |
| `SCOPE_ENTRY_OVERHEAD_BYTES` | `1024` | local fixed charge per entry for IDs, digests, times and the 32-byte index, added to `len(manifest.canonical_bytes())` |
| `STORE_RETENTION_SECONDS` | `310.0` | spec L161-162 |
| `MAX_OPEN_DISPATCHES` | `32` | local bound on reserved, admitted, writing and overdue flights. It is read from the module global at call time, so a test can monkeypatch it. |
| `CONNECT_SECONDS` | `5.0` | spec L175 |
| `WRITE_SECONDS` | `10.0` | spec L175 |
| `READ_INACTIVITY_SECONDS` | `20.0` | spec L175-176. Documentary: the connector enforces it, and a test asserts it equals `forwarder_response_receive._INACTIVITY_LIMIT`. |
| `RESPONSE_MARGIN_SECONDS` | `1.0` | local: time reserved after the upstream exchange so that `finish` and `send_response` complete before the ledger sweep |
| `MIN_ADMISSION_SECONDS` | `1.0` | local: the minimum upstream exchange budget at admission |
| `MIN_WRITE_SECONDS` | `0.5` | local: the minimum write budget at the fence. It is at most `MIN_ADMISSION_SECONDS`, so an immediate fence after admission always passes this check. |
| `MAX_HANDLER_SECONDS` | `40.0` | re-exported from `forwarder_receipts`; spec L177 |

`ROUTE_CATALOG` is also read from the module global at call time, so a test can mark a route unavailable.

### Closed codes

- `DENIAL_REASONS = frozenset({"request_rejected", "lease_denied", "route_denied", "permit_denied", "deadline"})`. These are the `NOT_DISPATCHED` reasons a caller may record. `abandoned` is recorded only by the sweep.
- `ADMISSION_CODES = ("admitted", "lease_denied", "sentinel_mismatch", "permit_unavailable", "insufficient_time", "gate_closed", "gate_held")`. Receipt reasons:
  - `insufficient_time` gives `deadline` (504);
  - `permit_unavailable` gives `permit_denied` (403);
  - every other denial gives `lease_denied` (403).
- `WRITE_FENCE_CODES = ("write_admitted", "lease_denied", "sentinel_mismatch", "permit_unavailable", "insufficient_time", "gate_closed", "gate_held")`.
  - Every denial gives `FAILED`/`connect_failed` (502 `forwarder_upstream_failed`).
  - No application byte was written, and the receipts module stays unchanged; see "Judge findings resolved", A1.
  - `permit_unavailable` is the fence's fail-closed permit slot; it is unreachable in 13a.
- `GATE_STATES = ("ready", "closed", "held")`. `HOLD_CODES = ("clock_fault", "clock_domain_mismatch")`.
- `FLIGHT_PHASES = ("reserved", "admitted", "writing")`. A separate `overdue` flag marks a flight whose deadline has passed.
- `CLOSEOUT_STATES = ("open", "draining", "overdue", "quiescent", "unknown")`.
- `LEASE_STATES = ("registered", "active", "revoked", "expired", "pruned", "unknown")`.
- `DISPATCH_ERROR_CODES` is a frozenset of 23 codes:
  - `clock_fault`, `gate_held`, `gate_closed`, `generation_mismatch`, `authority_claimed`;
  - `manifest_binding_mismatch`, `grant_expired`, `lease_unverified`, `scope_conflict`, `scope_capacity`, `scope_unknown`;
  - `binding_mismatch`, `route_unavailable`, `deadline_exceeds_lease`, `dispatch_capacity`, `receipt_unavailable`, `invalid_reason`;
  - `handle_unknown`, `handle_consumed`, `deadline_expired`, `admission_unknown`, `write_claimed`, `invalid_outcome`.

`DispatchError(ValueError)`:
- `.code` is in `DISPATCH_ERROR_CODES`;
- `args == (code,)` and `str(e) == code`;
- it has no other attribute.

These are programming errors, not responses to caller content:
- `TypeError` for wrong exact argument types;
- `ValueError("unknown service")` for a service outside `SERVICE_PROFILES`.

### Types

All types are frozen dataclasses. Types marked `eq=False` are authenticated by object identity against the instance the gate issued, so a `dataclasses.replace` or `copy` of one is unknown to the gate.

- **`ScopeEntry(lease_id, run_id, attempt_id, service, generation, scope_digest, expires_at: float, installed_at: float, manifest: ScopeManifest = field(repr=False))`**, `eq=False`. Every field except `installed_at` and `manifest` is copied from the registry record, never from the caller's grant. `scope_digest == manifest.digest`.
- **`DispatchHandle(receipt_id, lease_id, service, route_id, deadline: float)`**, `eq=False`.
- **`Admission(receipt_id, lease_id, service, route_id, admitted_at: float, deadline: float, exchange_deadline: float, connect_deadline: float)`**, `eq=False`.
- **`AdmissionOutcome(code: str, admission: Admission | None, denial: ForwarderReceipt | None)`**. Exactly one of `admission` and `denial` is non-`None`.
- **`WriteOutcome(code: str, write_deadline: float | None, denial: ForwarderReceipt | None)`**. `write_deadline` is set if and only if `code == "write_admitted"`; otherwise `denial` is a `FAILED`/`connect_failed` receipt.
- **`Closeout(lease_id, lease_state, closeout_state, pending: int, in_flight: int, overdue: int, drain_deadline: float | None, uncertain: int, observed_at: float)`**.
- **`ShutdownReport(in_flight: int, overdue: int, aborted: int, abort_failures: int)`**.

### `DispatchGate(*, registry: LeaseRegistry, ledger: ReceiptLedger, clock: Callable[[], float] = time.monotonic)`

**Constructor.** Steps, in order:
1. Check types: `type(registry) is LeaseRegistry`, `type(ledger) is ReceiptLedger` and `callable(clock)`, else `TypeError`.
2. Check generations: `ledger.generation == registry.generation`, else `DispatchError("generation_mismatch")`.
3. **Exclusive authority.** Under a module-level `threading.Lock` `_AUTHORITY_LOCK`, read the private marker attribute `_maoi_dispatch_gate_claimed` on both objects. This follows the style of the existing socket markers.
   - If either object already carries the marker, raise `authority_claimed` and claim neither.
   - Otherwise set the marker on both objects. A claim is permanent for the object's lifetime.
   - A copied object carries the copied marker and is refused (fail-closed).
4. Create one `threading.RLock` `G` and a per-gate `secrets.token_bytes(32)` index key. The key is never exposed.

The gate is the only caller of the registry's `check` and `snapshot` besides `ForwarderControl`, and it never calls a mutating registry method. The only writers of the ledger are the gate (`reserve`, `begin_connect`, `begin_dispatch`, `finalize`) and `send_response` (`claim_delivery`, `complete_delivery`). The docs section records both rules.

**Properties.**
- `generation`.
- `ledger`, read-only; `send_response` needs it.
- `system_clock`: `True` if and only if the constructor received the `time.monotonic` function object captured at import (`_SYSTEM_CLOCK = time.monotonic`).

**State under `G`.**
- **Scope store:** `index -> ScopeEntry`, `lease_id -> ScopeEntry`, and a per-entry byte charge summed into `scope_bytes`.
  - `index = hmac.new(key, service.encode("ascii") + b"\x00" + sentinel.encode("ascii"), hashlib.sha256).digest()`.
  - The raw sentinel is never retained.
- **Flights:** `receipt_id -> _Flight`. A flight holds:
  - the handle, the admission and the private `ReceiptReservation`;
  - `lease_id`, `service`, `route_id`, `generation` (from the record), `scope_digest`, the store index and `requires_permit`;
  - `deadline` and `exchange_deadline`;
  - `phase` (`reserved`, `admitted` or `writing`) and `overdue` (bool);
  - an optional `abort` callable and `abort_fired`.
- **Gate state and time:** the gate state, its hold code and `last_now`.
- **Abort bookkeeping:** a queue of abort callables awaiting invocation outside `G`, and an `abort_failures` counter.

**Clock contract.** `G` calls no injected code except three monotonic clocks: the gate's own, the registry's (called under `R` while `G` is held) and the ledger's (under `L` while `G` is held).
- All three must be non-blocking, must not re-enter the gate, and must share one monotonic domain.
- Tests R1 and R1b deliberately block inside the ledger clock to widen a race window. That is legal only in tests.
- The docs section records this contract.

**Gate tick** (private; called under `G` by every method that reads the gate clock).
- If the gate is held, it raises `gate_held` without reading the clock.
- Any clock exception, a value that is not finite and non-negative, or a regression below `last_now` permanently holds the gate with hold code `clock_fault` and raises `clock_fault`.
- On success it:
  - marks every flight with `now >= deadline` as `overdue`, keeping the flight;
  - moves each such flight's attached, unfired abort callable to the abort queue and sets `abort_fired`;
  - prunes store entries with `now - installed_at >= 310` and releases their byte charge.
- Every public method that ticks drains the abort queue after releasing `G`. It calls each callable once and counts exceptions in `abort_failures`, briefly re-taking `G` to update the counter.

**Methods.** Every public method takes `G`. `G` is never held while calling a connector, channel or abort callable, `receive_request_sized` or `send_response`.

- **`now() -> float`.** Runs a tick under `G`, drains the abort queue and returns the reading. Reading and comparing the clock under `G` means concurrent callers can never observe a false regression.

- **`install_scope(*, grant: LeaseGrant, manifest: ScopeManifest) -> ScopeEntry`.** Steps, in order; the first failure raises:
  1. Check exact types. The gate must be ready, else `gate_closed` or `gate_held`. Tick.
  2. Run `require_manifest_binding(manifest, service=grant.service, run_id=grant.run_id, attempt_id=grant.attempt_id, scope_digest=grant.scope_digest)`. A `RouteConfigError` gives `manifest_binding_mismatch`. Every manifest has service `jira` (`ScopeManifest.__post_init__`), so a grafana, kubernetes, confluence or anthropic grant can never install.
  3. `grant.generation == registry.generation`, else `generation_mismatch`.
  4. Run `registry.check(service=grant.service, sentinel=grant.sentinel, generation=grant.generation, scope_digest=grant.scope_digest)`.
     - It must return `lease_id == grant.lease_id` (compared with `compare_digest`), and either `authorized is True` or reason `lease_registered`.
     - A `LeaseError` or any other result gives `lease_unverified`.
     - For a registered lease, `check` returns before it compares `scope_digest` (leases L305-307), so this step proves only the sentinel-to-lease mapping.
  5. **Record verification.** Take one `registry.snapshot()`, and reuse it in step 8.
     - Find the record whose `lease_id` equals `grant.lease_id`.
     - Require exact equality of `service`, `run_id`, `attempt_id`, `receiver_boot_id`, `scope_digest`, `expires_at` and `generation` with the grant.
     - Require record state `registered` or `active`.
     - Otherwise raise `lease_unverified`. A `replace()`d or stale grant can therefore never install a later `expires_at` or a foreign digest.
  6. `now < record.expires_at`, else `grant_expired`.
  7. The same lease with the same index and manifest digest returns the existing entry object, so reinstalling is idempotent. Any other index or lease collision gives `scope_conflict`.
  8. **Capacity.** The charge is `len(manifest.canonical_bytes()) + SCOPE_ENTRY_OVERHEAD_BYTES`.
     - If the store is at `MAX_SCOPE_ENTRIES`, or `scope_bytes + charge > MAX_SCOPE_BYTES`, first prune by retention. Then reconcile against the step-5 snapshot, dropping entries whose `lease_id` has no registry record.
     - If either limit would still be exceeded, raise `scope_capacity`.
     - An entry whose lease record still exists is never evicted.
  9. Install the entry, built from the record's values, with `installed_at = now`, and add its charge.

  `install_scope` has no production caller; see Deferred item 2. Tests call it with unit-12 golden synthetic grants and manifests.

  A retired lease's entry keeps its manifest until the retention prune. The alternative of dropping manifests at retirement was rejected: a replacement `ScopeEntry` would break the identity that in-flight denials rely on, and the byte budget already bounds the footprint.

- **`resolve(*, service: str, sentinel: str) -> ScopeEntry | None`.**
  - An unknown service raises `ValueError`.
  - It returns `None` for a sentinel that is not an exact 43-character base64url string, for an unknown index, or for an entry past retention.
  - It does not tick. It resolves in every gate state. `serve_request` reaches it only when the gate is ready or closed; see "Hold and shutdown semantics".

- **`precheck(entry: ScopeEntry, *, sentinel: str) -> bool`.** This is routes seam step 3, an observation only. It returns `True` only when all of these hold:
  - the gate is ready;
  - `entry` is the stored instance for its `lease_id`;
  - `registry.check(service=entry.service, sentinel=sentinel, generation=entry.generation, scope_digest=entry.scope_digest)` returns `authorized is True` and a `compare_digest`-equal `lease_id`.

  A `LeaseError` gives `False`.

- **`deny(entry, *, route_id: str, request_digest: str, reason: str, request_bytes: int, deadline: float) -> ForwarderReceipt`.** It atomically runs `ledger.reserve`, then `ledger.finalize(dispatch_state="NOT_DISPATCHED", reason=reason)`. Codes:
  - `invalid_reason`: reason not in `DENIAL_REASONS`;
  - `scope_unknown`: foreign entry;
  - `deadline_expired`: the ledger's `invalid_deadline`, meaning the deadline has passed;
  - `receipt_unavailable`: any other `ReceiptError`.

  It does not read the gate clock. It works in every gate state and never counts toward `MAX_OPEN_DISPATCHES`.

- **`reserve(entry, routed: RoutedRequest, *, request_digest: str, request_bytes: int, deadline: float) -> DispatchHandle`.** Steps, in order:
  1. `gate_closed` or `gate_held`.
  2. Tick. Newly overdue flights are marked, and their aborts queued, before the capacity check. A fault gives `gate_held`.
  3. `scope_unknown`.
  4. `binding_mismatch`, unless `routed.service == entry.service` and `compare_digest(routed.scope_digest, entry.scope_digest)`.
  5. `route_unavailable`, unless `ROUTE_CATALOG[routed.route_id].state` is `"enabled"` or `"partial"`.
  6. `deadline_exceeds_lease`, if `deadline > entry.expires_at`.
  7. `dispatch_capacity`, at `MAX_OPEN_DISPATCHES` flights. Overdue flights still count.
  8. `ledger.reserve`. The ledger's `invalid_deadline` gives `deadline_expired`. Any other `ReceiptError`, including capacity and a held ledger, gives `receipt_unavailable`.

  On success the flight is `reserved`, with `exchange_deadline = deadline - RESPONSE_MARGIN_SECONDS`.

- **`admit(handle, *, sentinel: str) -> AdmissionOutcome`.** The critical section is described under "Atomicity". It raises `handle_unknown`, `handle_consumed` (the flight is past `reserved`), `deadline_expired` (the flight is overdue or swept) or `receipt_unavailable`.

- **`attach_abort(admission, abort: Callable[[], None]) -> bool`.**
  - A non-callable `abort` raises `TypeError`. An unknown admission raises `admission_unknown`.
  - It returns `False` if the gate is not ready or the flight is overdue; the caller must then abort the channel itself.
  - Otherwise it records the callable (one per flight) and returns `True`.
  - It does not tick and never removes the flight.

- **`begin_write(admission, *, sentinel: str) -> WriteOutcome`.** The write fence; see "Atomicity". It raises `admission_unknown`, `write_claimed` (already writing), `deadline_expired` (overdue or swept) or `receipt_unavailable`.

- **`finish(admission, *, dispatch_state: str, reason: str, upstream_response: ParsedResponse | None = None) -> ForwarderReceipt`.** Calls `ledger.finalize` and removes the flight.
  - An overdue flight raises `deadline_expired` and is removed without a ledger call.
  - A ledger `invalid_transition`, `invalid_reason`, `invalid_dispatch_state`, `invalid_upstream_response` or `invalid_response` gives `invalid_outcome`. The flight is kept, so a legal retry can follow.
  - A swept entry gives `deadline_expired`. Any other `ReceiptError` (held, clock fault) gives `receipt_unavailable`. Both remove the flight.
  - `finish` does not read the gate clock, so it works after shutdown and while the gate is held.

- **`release(token: DispatchHandle | Admission) -> bool`.** This is the owner's backstop.
  - It removes the token's flight if it is still present, and returns whether it did.
  - It never touches the ledger: an unfinalized entry is swept at its deadline.
  - It works in every gate state and is idempotent. A wrong type raises `TypeError`; an unknown or foreign token returns `False`.
  - Only the thread that reserved the handle may call it, and only after its channel (if any) is closed. `serve_request` calls it in a `finally`, so a `BaseException` can never leave a flight holding a slot.

- **`is_admitted(admission) -> bool`.** `True` while the flight's phase is `admitted` or `writing` and it is not overdue.

- **`closeout(lease_id: str) -> Closeout`.** Runs under `G` (G then R, G then L). It ticks unless the gate is held.
  - `registry.snapshot()` gives `lease_state` from the record. With no record, `lease_state` is:
    - `pruned` if the gate's store still holds an entry for `lease_id`: the record aged out at `created_at + 310`, which is at least 40 s after `expires_at`;
    - `unknown` otherwise.
  - `ledger.snapshot()`, filtered by `lease_id`, gives:
    - `pending`: entries in `reserved`;
    - `in_flight`: entries in `connecting` or `dispatched`;
    - `drain_deadline`: the maximum in-flight deadline;
    - `uncertain`: retained finalized entries that are `DISPATCHED_UNKNOWN` or `PARTIAL`.
  - `overdue` counts gate flights for `lease_id` with the overdue flag set: a serving thread has not yet returned from a deadline-ignoring connector.
  - `closeout_state` is decided in this order:
    - `unknown` if the registry is `held`, the ledger is `held`, the gate is held, `lease_state` is `unknown`, or `lease_id` is not a safe ID;
    - otherwise `open` for `registered` or `active`;
    - otherwise `overdue` if `overdue > 0`. A Receiver treats this state as UNKNOWN: it holds dispatch (spec L162-163);
    - otherwise `draining` if `in_flight > 0`;
    - otherwise `quiescent`. This covers `pruned`, which cannot have in-flight ledger entries because every flight deadline is at most `expires_at`.

- **`shutdown() -> ShutdownReport`.** Idempotent. It does **not** call `registry.hold()`: `ForwarderControl` keeps exclusive control of mutating registry calls (docs L79). The closed gate alone denies every precheck, reserve, admit and fence.
  - Under `G`: mark the gate `closed`. Then take every attached, unfired abort callable of admitted, writing or overdue flights, and set `abort_fired`.
  - After releasing `G`: call each callable once, counting exceptions as `abort_failures`.
  - A later call aborts nothing new.
  - A connect already in progress is not interrupted. It is bounded by its `connect_deadline`; `attach_abort` then returns `False` and the fence denies with `gate_closed`.
  - The documented supervisor order is: `ControlService.stop` (whose `ForwarderControl.shutdown` holds the registry), then `DispatchGate.shutdown`, then listener close. The gate's invariants do not depend on that order.

- **`snapshot() -> dict`.** It does not tick and is readable in every state. Keys:
  - `generation`, `gate_state`, `hold_code`, `open_dispatches`, `scope_bytes`, `abort_failures`;
  - `scope_entries`: a tuple of `(lease_id, service, scope_digest, expires_at, installed_at)`;
  - `flights`: a tuple of `(receipt_id, lease_id, service, route_id, phase, overdue, deadline, abort_attached, abort_fired)`.

  It contains no sentinel, index or key.

### Overdue flights

A flight is never deleted by another thread's clock read. At its deadline, the next tick by any caller does four things:
- marks the flight overdue;
- queues its attached abort, which then runs once outside `G`;
- keeps it counted toward `MAX_OPEN_DISPATCHES` (bounded and fail-closed);
- makes `closeout` report `overdue` for its lease until the owner returns.

The owner's next call behaves consistently, whichever thread ticked first:
- `admit`, `begin_write` or `finish` raises `deadline_expired` and removes the flight;
- `attach_abort` returns `False`;
- `release` removes the flight.

Handle and admission identity is therefore stable for the owner's whole lifetime, so `handle_unknown` and `admission_unknown` mean only forgery or a bug.

### Transition rules

| Gate call | Flight | Ledger | Receipt returned |
| --- | --- | --- | --- |
| `deny` | none | `reserve`, then finalize `NOT_DISPATCHED` | the denial |
| `reserve` | becomes `reserved` | `reserve`, entry `reserved` | none |
| `admit`, admitted | `reserved` to `admitted` | `begin_connect`, entry `connecting` | none |
| `admit`, denied | removed | finalize `NOT_DISPATCHED`, inside the same critical section | the denial |
| `begin_write`, admitted | `admitted` to `writing` | `begin_dispatch`, entry `dispatched` | none |
| `begin_write`, denied | removed | finalize `FAILED`/`connect_failed`, inside the same critical section | the denial |
| `finish` | removed (kept on `invalid_outcome`) | finalize the given state and reason | the receipt |
| deadline passes | marked `overdue` at the next tick; abort queued; still counted | swept: `NOT_DISPATCHED`/`abandoned` from `reserved`, else `DISPATCHED_UNKNOWN`/`abandoned` | none |
| owner call on an overdue flight | removed by `admit`, `begin_write` or `finish` (`deadline_expired`); `attach_abort` returns `False` | untouched | none |
| `release` | removed if present | untouched | none |

### Deadlines (one clock domain)

| Name | Value | Used for |
| --- | --- | --- |
| `handler_deadline` | `started + 40` | inbound receive; the reserve and send deadline of the E5 precheck denial only |
| `dispatch_deadline` | `min(handler_deadline, entry.expires_at)` | the deadline of every other receipt: E6 and E7 denials, the `reserve` sweep point, and every reserved receipt's send deadline |
| `exchange_deadline` | `dispatch_deadline - RESPONSE_MARGIN_SECONDS` | the end of all upstream work; also the receive deadline |
| `connect_deadline` | `min(admitted_at + CONNECT_SECONDS, exchange_deadline)` | computed inside `admit` from its own clock read |
| `write_deadline` | `min(fence_observed_at + WRITE_SECONDS, exchange_deadline)` | computed inside `begin_write` from its own clock read; the fence requires `fence_observed_at + MIN_WRITE_SECONDS <= exchange_deadline` |

**Deliberate deviation (E5).** The precheck denial uses the unclipped `handler_deadline`. The lease may already be expired, and that is often why the precheck failed; a lease-clipped deadline would make the denial unrepresentable. This does not conflict with spec L177-178: the receipt is `NOT_DISPATCHED`/`lease_denied`, and the deadline governs only local receipt bookkeeping and delivery, never upstream authority. Every later receipt is clipped to the lease, as the routes-plan "Reserve inputs" rule requires.

**Why `expires_at` is the effective lease limit.** `register` requires `expires_at <= created_at + 270` (leases L190), and `activate` requires `launch_at >= created_at` (L238). So both `created_at + 270` and `launch_at + 270` are at least `expires_at`, and the registry's limit `min(...)` (L390-394) equals `expires_at`. The routes-plan term `launch_at + LEASE_SECONDS` is therefore redundant, and the Forwarder needs no `launch_at` input. `ScopeEntry.expires_at` comes from the registry record (install step 5), so the clip cannot be widened by a forged grant.

Phase deadlines are computed at the two linearization points, from fresh clock reads under `G`. There is no stale `now`. Admission requires `observed_at + RESPONSE_MARGIN_SECONDS + MIN_ADMISSION_SECONDS <= deadline`, which is at least 2.0 s total.

## Module 2: `grafana_jsm_sandbox/forwarder_exchange.py`

This module serves exactly one request on an already-handshaken inbound TLS socket.
- `serve_request` never closes the socket, never retries, and never sends bytes that are not named by a ledger receipt.
- It performs no upstream network I/O of its own.
- Target: 450 lines or fewer.

**Imports** (AST-checked by exact name).
- **stdlib:** `__future__` (`annotations`), `collections.abc` (`Callable`), `dataclasses` (`dataclass`), `hmac`, `math` and `typing` (`Protocol` only).
- **relative:**
  - `.forwarder_dispatch` (`Admission`, `DispatchError`, `DispatchGate`, `MAX_HANDLER_SECONDS`, `MIN_ADMISSION_SECONDS`, `RESPONSE_MARGIN_SECONDS`);
  - `.forwarder_http_receive` (`HTTPReceiveError`, `receive_request_sized`);
  - `.forwarder_http_response` (`ParsedResponse`);
  - `.forwarder_receipts` (`ForwarderReceipt`, `ReceiptError`, `local_response_for`, `response_digest`);
  - `.forwarder_response_send` (`ResponseSendError`, `send_response`);
  - `.forwarder_routes` (`RoutePolicy`, `RoutePolicyError`, `RoutedRequest`, `UNMATCHED_ROUTE_ID`, `denied_request_digest`);
  - `.forwarder_server_tls` (`FixedTLSListener`, `TLSListenerError`);
  - `.forwarder_services` (`SERVICE_PROFILES`).
- **Forbidden:** `socket`, `ssl`, `select`, `os` and `subprocess`, including under `TYPE_CHECKING`.
  - The inbound connection is annotated `object`.
  - `receive_request_sized` and `send_response` each claim the socket and require an exact `ssl.SSLSocket`.
  - Both are called through module globals, so the deterministic tests can monkeypatch them.

**Constants.**
- `UPSTREAM_ERROR_CODES = frozenset({"connect_failed", "upstream_tls_failed", "write_failed", "receive_failed", "deadline"})`.
- `SERVE_RESULTS = ("responded", "closed_without_response", "delivery_failed")`.
- `CLOSE_REASONS = frozenset({"accept_failed", "request_unreadable", "sentinel_unknown", "receipt_unavailable", "dispatch_capacity", "deadline_expired", "gate_failure", "internal_failure"})`.

**`UpstreamError(ValueError)`.** `.code` is in `UPSTREAM_ERROR_CODES`, and `args == (code,)`.

**`UpstreamConnector(Protocol)`.** The 13b trusted connector implements it. Source ships no implementation.
- `prepare(self, routed: RoutedRequest) -> str`
  - Pure, with no I/O.
  - Returns the 64-lowercase-hex request digest that binds this exact request to the connector's origin and service configuration. In 13b this is rule v2.
  - It is the only digest a dispatch-capable reservation ever carries. It must differ from `routed.request_digest` (v1), and E7c enforces that.
- `connect(self, admission: Admission, routed: RoutedRequest, *, request_digest: str, deadline: float) -> UpstreamChannel`
  - Opens and verifies the upstream transport.
  - **Writes no application bytes.**
  - Refuses a digest it did not prepare for `routed`.

**`UpstreamChannel(Protocol)`.**
- `send(self, *, deadline)` writes the complete canonical request exactly once.
- `receive(self, *, deadline) -> ParsedResponse` collects one bounded response with a 20 s per-read inactivity limit.
- `abort(self)` is idempotent, thread-safe and non-blocking. It must be safe before, during, after and concurrently with `close`, because `shutdown` and the overdue path call it outside `G` while E10's `finally` may be closing the channel.
- `close(self)` is idempotent.

Runtime check: `upstream` must be `None` or expose callable `prepare` and `connect`, else `TypeError`. A returned channel lacking any of the four callables counts as a connect failure. If it exposes a callable `close`, that is called exactly once and its exceptions are recorded only.

**`ServeOutcome(result, reason, receipt_id, dispatch_state, delivery)`** (frozen).
- For `responded`, `reason` is the receipt reason and `delivery` is `"sent"`.
- For `closed_without_response`, `reason` is in `CLOSE_REASONS`.
- For `delivery_failed`, `reason` is a `ResponseSendError` code or `internal_failure`.
- It never contains exception text.

### `serve_request(connection: object, *, service: str, gate: DispatchGate, policy: RoutePolicy, upstream: UpstreamConnector | None, started: float) -> ServeOutcome`

Steps run in order. "Close" means return `closed_without_response` with no bytes. "Deny" is the single procedure below; every denial site uses it.

**Deny(route_id, request_digest, reason, deadline).**
1. `now = gate.now()`. A `DispatchError` closes with `gate_failure`.
2. If `deadline <= now`, close with `deadline_expired`.
3. `receipt = gate.deny(entry, route_id=..., request_digest=..., reason=..., request_bytes=request_bytes, deadline=deadline)`. A `DispatchError` closes:
   - `receipt_unavailable` (ledger full or held) with `receipt_unavailable`;
   - `deadline_expired` (the ledger's deadline race) with `deadline_expired`;
   - `scope_unknown`, `invalid_reason` or any other code with `internal_failure`.
4. Deliver it (E18) with `deadline` as the delivery deadline.

**Digest rule, stated once.**
- A receipt created before a successful E7c carries `denied_request_digest(service, route_id)` for its route:
  - E5 uses `unmatched`;
  - E6 uses `e.request_digest`, which is that same unit-12 denial digest;
  - E7a, E7b and E7c use `denied_request_digest(service, routed.route_id)`.
- Every receipt created after a successful E7c carries the prepared `digest`: E7d, every E8 denial (including `route_unavailable`), every admit and fence denial, and every `finish`.
- No receipt ever carries `routed.request_digest`.

**Steps.**

- **E1. Arguments.**
  - Exact types for `gate` and `policy`; `started` must be an exact finite int or float. Otherwise `TypeError`.
  - `service` must be in `SERVICE_PROFILES` (`TypeError` or `ValueError`).
  - `upstream` shape is checked as above.
  - `gate.system_clock` must be `True`, else `ValueError("clock_domain_mismatch")`, because the receive and send helpers read `time.monotonic`.
- **E2. Clock.** `now = gate.now()`. A `DispatchError` closes with `gate_failure`; this includes every held gate (see "Hold and shutdown semantics"). Require `now - 40 < started <= now`, else close with `deadline_expired`. Set `handler_deadline = started + 40`.
- **E3. Receive.** `opts = policy.parser_options(service)`, then `request, request_bytes = receive_request_sized(connection, service, deadline=handler_deadline, allowed_query_keys=opts.allowed_query_keys, accept=opts.accept)`. `HTTPReceiveError` closes with `request_unreadable`: no lease is known, so no receipt can exist (routes seam step 1).
- **E4. Resolve.** `entry = gate.resolve(service=service, sentinel=request.sentinel)`. `None` closes with `sentinel_unknown` (seam step 2). This covers a wrong listener, a non-Jira service and an empty store.
- **E5. Precheck.** If `gate.precheck(entry, sentinel=...)` fails, Deny(`UNMATCHED_ROUTE_ID`, `denied_request_digest(service, UNMATCHED_ROUTE_ID)`, `lease_denied`, `handler_deadline`). Result: 403. The unclipped deadline is the deliberate deviation stated under "Deadlines". Then set `dispatch_deadline = min(handler_deadline, entry.expires_at)`.
- **E6. Route.** `routed = policy.route(request, entry.manifest)`.
  - `RoutePolicyError e`: record `(e.route_id, e.request_digest, e.receipt_reason)`, then, outside the handler, Deny with those and `dispatch_deadline`. Result: 400 or 403.
  - `TypeError` or `ValueError`: close with `internal_failure`.
- **E7. Pre-reserve denials**, in order. Each uses `d = denied_request_digest(service, routed.route_id)` and `dispatch_deadline` unless stated:
  - a. `routed.requires_permit is not False`: Deny `permit_denied` (unreachable in 13a).
  - b. `upstream is None`: Deny `route_denied`, 403. This is the capability staying explicitly unavailable.
  - c. `digest = upstream.prepare(routed)`. Deny `route_denied` if any of these holds:
    - `prepare` raises any `Exception`;
    - the result is not an exact 64-lowercase-hex `str`;
    - `hmac.compare_digest(digest, routed.request_digest)` is true. No v1 digest may ever be a dispatch digest (routes rule v2).
  - d. `now = gate.now()`; a `DispatchError` closes with `gate_failure`. If `dispatch_deadline - now < RESPONSE_MARGIN_SECONDS + MIN_ADMISSION_SECONDS`, Deny(`routed.route_id`, `digest`, `deadline`, `dispatch_deadline`). Result: 504, or `deadline_expired` if the lease end has already passed.
- **E8. Reserve.** `handle = gate.reserve(entry, routed, request_digest=digest, request_bytes=request_bytes, deadline=dispatch_deadline)`. On `DispatchError`:
  - `gate_closed`: Deny `lease_denied` with `digest`;
  - `gate_held`: close with `gate_failure`;
  - `route_unavailable`: Deny `route_denied` with `digest`;
  - `dispatch_capacity` or `receipt_unavailable`: close with that code (capacity before bytes);
  - `deadline_expired`: close with `deadline_expired`;
  - any other code: close with `internal_failure`.

  From here on, E9-E18 run inside `try/finally`, and the `finally` calls `gate.release(handle)` (E19).
- **E9. Admit.** `outcome = gate.admit(handle, sentinel=request.sentinel)`. A denial is delivered with `deadline=dispatch_deadline`. On `DispatchError`, close with `deadline_expired` or `receipt_unavailable`, or with `internal_failure` for the `handle_*` codes.
- **E10. Connect.** `channel = upstream.connect(admission, routed, request_digest=digest, deadline=admission.connect_deadline)`.
  - Any `Exception` gives `finish(FAILED, reason)`, where reason is `upstream_tls_failed` when `type(e) is UpstreamError and e.code == "upstream_tls_failed"`, else `connect_failed`. A connect-phase `UpstreamError("deadline")` is also `FAILED`/`connect_failed`: nothing was written.
  - A malformed channel gives `FAILED`/`connect_failed`, after its callable `close`, if any, is called once.
  - Steps E11-E15 run inside `try/finally`. The `finally` calls `channel.close()` exactly once and only records its exceptions.
- **E11. Attach.** If `gate.attach_abort(admission, channel.abort)` returns `False`, call `channel.abort()` (recorded) and continue. The fence then necessarily denies with `gate_closed` or `gate_held`, or raises `deadline_expired`.
- **E12. Fence.** `fence = gate.begin_write(admission, sentinel=request.sentinel)`.
  - Any code other than `write_admitted`: call `channel.abort()` and deliver `fence.denial` (`FAILED`/`connect_failed`, 502).
  - `DispatchError`: call `channel.abort()` and close with `deadline_expired` or `receipt_unavailable`, or with `internal_failure` for the `admission_*` and `write_claimed` codes.
- **E13. Send.** `channel.send(deadline=fence.write_deadline)`. This is the first possible upstream write, and nothing but the return from `begin_write` separates it from the fence. On `Exception`: `UpstreamError("deadline")` gives `DISPATCHED_UNKNOWN`/`deadline`; anything else gives `DISPATCHED_UNKNOWN`/`write_failed`.
- **E14. Receive.** `response = channel.receive(deadline=admission.exchange_deadline)`.
  - `UpstreamError("deadline")` gives `DISPATCHED_UNKNOWN`/`deadline`.
  - Any other `Exception`, or `type(response) is not ParsedResponse`, gives `DISPATCHED_UNKNOWN`/`receive_failed`.
  - Then `response_digest(response)` must succeed. A `ReceiptError` gives `DISPATCHED_UNKNOWN`/`malformed_response`, a reason the committed table already has (502). This catches a connector-built `ParsedResponse` that the canonical serializer refuses, such as status 302, an empty 200 body, or a body over 1 MiB.
  - A stalled real read reports `receive_failed`: unit 10 maps a recv timeout to `receive_failed` (response_receive L94-98).
- **E15. Response policy.** `verdict = policy.check_response(routed, response)`, then `finish(TRANSPORT_CONFIRMED, verdict.receipt_reason, upstream_response=response)`.
- **E16. Unmapped exception after admission.** Any `Exception` inside E11-E15 not mapped above is finalized by fence state:
  - `FAILED`/`connect_failed` if the fence was not passed: `send` never began, so this is truthful;
  - otherwise `DISPATCHED_UNKNOWN`/`abandoned`.

  Result: 502.
- **E17. Finish failure.** A `DispatchError` from `finish`:
  - `deadline_expired`: close with `deadline_expired`. The client sees EOF and the ledger shows `abandoned`.
  - `receipt_unavailable`: close with `receipt_unavailable`.
  - `invalid_outcome` (a bug: every mapped outcome is legal): make exactly one fallback `finish` with the E16 rule and deliver its receipt. If the fallback also fails, close with `internal_failure`.
  - Any other code: close with `internal_failure`.
- **E18. Deliver.** The body is the upstream `ParsedResponse` when the receipt is `TRANSPORT_CONFIRMED`/`ok`, else `local_response_for(receipt)`. Call `send_response(connection, gate.ledger, receipt, body, deadline=delivery_deadline)`. `delivery_deadline` is `handler_deadline` for the E5 receipt and `dispatch_deadline` for every other receipt.
  - A `DeliveryResult` returns `responded`.
  - A `ResponseSendError e` returns `delivery_failed` with `e.code`.
  - Any other `Exception` returns `delivery_failed` with `internal_failure`.
- **E19. Release.** The E8 `finally` calls `gate.release(handle)`. On every normal path the flight is already gone, so this returns `False`.

Per request there is at most one `prepare`, one `connect`, one `send`, one `receive` and one `close`. Nothing is retried after connect failure, 429/5xx, a timeout or a malformed reply (spec L212-217). 3xx never arrives from a real collector, because the unit-10 codec rejects it; a fake's 302 becomes `malformed_response`.

A `BaseException` propagates after the channel is closed and the flight is released. The ledger sweep then finalizes the entry as `abandoned`.

### `serve_one(listener: FixedTLSListener, *, gate, policy, upstream, accept_timeout: float = 1.0) -> ServeOutcome`

- `type(listener) is FixedTLSListener`, else `TypeError`. The other arguments are validated as in E1 before accept.
- `connection = listener.accept(timeout=accept_timeout)`. A `TLSListenerError` returns `closed_without_response`/`accept_failed`.
- `started = gate.now()`. A `DispatchError` closes the connection and returns `gate_failure`.
- It returns `serve_request(connection, service=listener.service, ...)`, and `connection.close()` runs in `finally` with its exceptions recorded only.

This binds the receipt's service to the listener that accepted the socket, a duty the receipts plan (L231-234) left to the caller. It also enforces one request per connection and close after the response (spec L167-168). There is no accept loop or worker pool; see Deferred item 4.

## Existing-module changes (additive only)

1. **`grafana_jsm_sandbox/forwarder_http_receive.py`.** This resolves routes-plan Deferred item 1's byte count.
   - Move the current body of `receive_request` verbatim into private `_receive(...) -> tuple[ParsedRequest, int]`. The `int` is `len(captured)` at the final parse: the exact request-line, header and body bytes consumed. Excess captured bytes are already rejected.
   - `receive_request` returns `_receive(...)[0]`.
   - Add public `receive_request_sized(connection, service, *, deadline, allowed_query_keys=frozenset(), accept="application/json") -> tuple[ParsedRequest, int]`.
   - The module-level names `ssl`, `time`, `_read`, `_collect_head`, `_clock`, `_remaining` and `_claim_and_validate` stay, because existing tests monkeypatch `forwarder_http_receive.ssl.SSLSocket` and `.time.monotonic`.
   - Codes, the socket marker and timeout restoration are unchanged. A sized call and a plain call on the same socket give `connection_claimed`.
   - The count never exceeds `forwarder_receipts.MAX_REQUEST_BYTES`.
2. **`grafana_jsm_sandbox/forwarder_server_tls.py`.** Add a read-only property `FixedTLSListener.service -> str` that returns `self._service`. There are no other changes.
3. **`docs/forwarder-control.md`** (root). Add a section "Dispatch admission, write fence and the one-request exchange" covering:
   - the lock hierarchy, the two linearization points, and the clock contract;
   - exclusive ownership: one gate per registry and per ledger; the ledger's only writers are the gate and `send_response`; the gate never mutates the registry;
   - the deadlines, the response margin, the minimum admission and write budgets, and the E5 deviation;
   - overdue flights and the `overdue` closeout state;
   - held versus closed behavior, and the shutdown order;
   - that closeout is in-process only, including `pruned`;
   - the permit rule this plan decides (consume at L1, re-verify at L2), which is not implemented;
   - that there is no upstream connector in source;
   - the non-claims below.

   Append the seven new test files to the focused pytest command.

Explicitly unchanged: `forwarder_leases.py`, `forwarder_control.py`, `forwarder_control_protocol.py`, `forwarder_receipts.py`, `forwarder_response_send.py`, `forwarder_response_receive.py`, `forwarder_tls.py`, `forwarder_http.py`, `forwarder_http_response.py`, `forwarder_services.py`, `forwarder_supervisor.py`, `forwarder_listener.py`, and the unit-12 modules.
- The receipt reason table already covers every outcome used, including `malformed_response`.
- No `LeaseRegistry` subclass, callback or retire hook is added.
- Every existing test file stays byte-identical and green.

## Atomicity: lock order, linearization and invariants

**Lock hierarchy** (a total order, never inverted): `ForwarderControl._lock` then `G` then `R` (`LeaseRegistry._lock`), and separately `G` then `L` (`ReceiptLedger._lock`). `_AUTHORITY_LOCK` is taken only in the gate constructor and never with any other lock.
- `R` and `L` never call outward, except their own clocks.
- `G` calls no injected code except the three clocks (see "Clock contract").
- `ForwarderControl` never calls the gate in 13a.
- A future control closeout command would take `control._lock`, then `G`, then `R`, which is consistent with this order.
- A retire hook running under `R` and taking `G` would invert the order. That is why the registry is not changed.

**Admission critical section (`admit`, L1).** Everything runs under `G`; nothing does I/O.
1. Look up the handle by identity: an unknown handle raises `handle_unknown`, and a flight past `reserved` raises `handle_consumed`. The lookup comes first, so a forged handle never reaches the clock.
2. Tick. If the gate is held, or the read faults (which holds it), deny `gate_held`. If this flight is overdue, remove it and raise `deadline_expired` after the `try`.
3. If the gate is closed, deny `gate_closed`.
4. Compare the HMAC index of `(handle.service, sentinel)` with the flight's index using `compare_digest`. A mismatch or malformed sentinel gives `sentinel_mismatch`.
5. **Permit consumption slot.** If `flight.requires_permit`, deny `permit_unavailable`: the capability is explicitly unavailable today. This is where a future AuthorizeDispatch permit is consumed, atomically with the step-6 check (receipts plan step 2 names `begin_connect` as the permit point). See "Permit rule".
6. **Lease check (L1).** `before = clock()`, then `r = registry.check(service, sentinel, generation=flight.generation, scope_digest=flight.scope_digest)`, then `after = clock()`.
   - The generation is the stored record generation, never `registry.generation`.
   - A `LeaseError`, `r.authorized is not True`, or a `lease_id` mismatch denies `lease_denied`.
   - If `before <= r.observed_at <= after` fails, hold the gate with `clock_domain_mismatch` and deny `gate_held`. This detects a registry on another clock.
7. If `r.observed_at + RESPONSE_MARGIN_SECONDS + MIN_ADMISSION_SECONDS > flight.deadline`, deny `insufficient_time`.
8. `ledger.begin_connect(reservation)`. A swept entry removes the flight and raises `deadline_expired`; any other `ReceiptError` removes it and raises `receipt_unavailable`.
9. Set the phase to `admitted` and return an `Admission` with `admitted_at = r.observed_at` and the deadlines from the table.

Denials in steps 2-7 finalize the still-reserved entry `NOT_DISPATCHED` inside the same critical section, and remove the flight. A `ReceiptError` from that finalize raises `deadline_expired` (swept) or `receipt_unavailable`.

**Write fence (`begin_write`, L2).** Everything runs under `G`.
1. Look up the admission by identity: an unknown admission raises `admission_unknown`, and a writing flight raises `write_claimed`.
2. Tick. A held gate or a fault denies `gate_held`. If the flight is overdue, remove it and raise `deadline_expired`.
3. If the gate is closed, deny `gate_closed`.
4. Check the sentinel index, as in admit.
5. **Final lease check (L2).** Repeat admit step 6 exactly, including the clock-domain guard. A denial gives `lease_denied`.
6. **Permit re-verification slot.** If `flight.requires_permit`, deny `permit_unavailable`. This is unreachable in 13a, because admit denies every permit route, so it only fails closed. A future permit unit re-verifies here, atomically with step 5, the consumed permit's monotonic expiry, request digest and lease, boot, generation and attempt binding.
7. If `observed_at + MIN_WRITE_SECONDS > exchange_deadline`, deny `insufficient_time`.
8. `ledger.begin_dispatch(reservation)`. A swept entry gives `deadline_expired`; any other error gives `receipt_unavailable`.
9. Set the phase to `writing` and return `write_admitted` with `write_deadline`.

Denials in steps 2-7 finalize `FAILED`/`connect_failed` inside the critical section (a legal transition from `connecting`) and remove the flight. The orchestrator then aborts the channel. That is truthful: `send` is never called before `write_admitted`, and `connect` writes no application bytes.

**Permit rule (decided here; not implemented).** Spec L231-233 requires the permit to be consumed atomically with the final lease check before the first possible upstream write. 13a has two checks, so it fixes the rule now:
- **Consume at L1.** Admit step 5 consumes the permit, atomically with the L1 check and `begin_connect`. This keeps the committed receipts meaning of `FAILED` ("the connection attempt began, permit consumed").
- **Re-verify at L2.** Fence step 6 re-verifies the consumed permit atomically with the final L2 check, under `G` and before any application byte. Expiry or binding failure is a fence denial: `FAILED`/`connect_failed`, zero bytes, and the permit is never revived (spec L234-235).
- **Late approval.** Missing or late control approval is decided at L1, before `begin_connect`, and gives `NOT_DISPATCHED`/`permit_denied`, as spec L233 requires.
- **Status.** This interpretation is recorded as an open question for the spec owner and as a non-claim.

**Linearization points.**
- A dispatch *initiation* is the authorizing `check` in admit step 6; `begin_connect` is its recorded consequence.
- A dispatch *write* is the authorizing `check` in fence step 5; `begin_dispatch` is its recorded consequence.
- `G` makes each pair indivisible for every observer that takes `G`: `closeout`, `shutdown`, `attach_abort`, `finish`, `release` and `snapshot`.
- The one-gate-per-registry-and-ledger claim ensures no second `G` exists for the same objects.

**Retirement causes.** All of them are serialized by `R` and ordered with every `check`:
- explicit Revoke;
- control EOF, timeout or a rejected command (`_release_owner` calls `disconnect`);
- owner replacement or a fresh boot (`receiver_replaced`);
- `hold()`, called only by `ForwarderControl`;
- lease expiry;
- heartbeat loss after 15 s.

The last two need no timer: `registry._now()` evaluates them inside every call, including the authorizing check itself (leases L330-349).

**Invariants.** Each has a test.
- **I1.** No `connect` without a successful L1: `connect` is called only with an `Admission`.
- **I2.** No upstream write without a successful L2 after `connect` returned: `send` is called only after `write_admitted`.
- **I3, revocation atomically prevents new dispatch (spec L155-157).** After a retirement of lease X returns, no L1 or L2 for X succeeds: every later check is ordered after it and is denied, or raises `registry_held`. After `DispatchGate.shutdown` linearizes under `G`, no L1 or L2 succeeds for any lease.
  - A request whose L2 preceded the retirement may still complete. Its receipt is `TRANSPORT_CONFIRMED` or `DISPATCHED_UNKNOWN` ("revocation is not rollback": ADR 0011 L17, ADR 0012 L17, accounting L222).
  - A request admitted but not yet writing ends `FAILED` with zero application bytes.
  - This also enforces docs L39-41: `check` never authorizes a later write by itself.
- **I4, in-flight observability.** `closeout` and `shutdown` hold `G`, so they never observe a passed check without its ledger consequence. Any L1 or L2 ordered before a retirement is visible to every closeout that starts after the retirement returns, even though Revoke itself holds only `R`.
- **I5, bounded drain for conforming connectors.** Every flight's deadline is `min(started + 40, expires_at)`, and the ledger sweeps at that deadline.
  - `drain_deadline` is at most retirement time + 40 s.
  - Admitted-but-not-writing flights end at their fence within `connect_deadline`, at most 5 s.
  - An expired lease is never `draining`. It is `quiescent`, unless a serving thread is overdue.
  - For a connector that ignores its deadlines, the flight becomes `overdue`: its abort fires once, it keeps its slot, and closeout reports `overdue` (treated as UNKNOWN), never `quiescent`, until the owner returns.
- **I6, no revival.** Consumed, copied or foreign handles and admissions are unknown. A new registry generation needs a new ledger and gate, and grants from another generation are refused at install and denied at check. A second gate over a claimed registry or ledger is refused.
- **I7, capacity before bytes.** Flight and ledger capacity fail at `reserve`, before any connect and before any client bytes. A deny that cannot reserve a receipt closes without bytes. Parse and sentinel failures produce no bytes (spec L423-426; receipts plan L43-47).
- **I8, stability.** Once closeout observes a retired lease:
  - pending flights can only become `NOT_DISPATCHED`, admitted flights only `FAILED`, and writing flights only finish, be swept, or become overdue;
  - `quiescent` never reverts to `open`, `draining` or `overdue`;
  - after the registry record is pruned, the gate reports `lease_state` `pruned` and stays `quiescent` while its store entry lasts (`installed_at + 310` s). After that, it reports `unknown`. A Receiver must read closeout within that retention, the same window the registry already bounds, and its durable evidence is ticket 37's (spec L161-162);
  - `draining` reaches `quiescent` by `drain_deadline` on a healthy clock with a conforming connector.

**Hold and shutdown semantics.**
- **Held registry.** Every check raises, so admits and fences deny. `closeout` reports `unknown`, and new dispatch stays held (spec L162-163).
- **Held gate** (`clock_fault` or `clock_domain_mismatch`).
  - Every admit and fence denies `gate_held`, and `reserve` and `install_scope` raise.
  - `serve_request` closes every new request without bytes (`gate_failure`), because E2's clock read raises. This is chosen over 403s: after either hold, no deadline derived from the gate's time can be trusted to match the registry's.
  - `resolve`, `precheck` (always `False`) and `deny` remain callable for direct callers.
  - `closeout` reports `unknown`.
- **Closed gate** (after `DispatchGate.shutdown`).
  - Requests still get receipt-backed 403s: `precheck` returns `False` and Deny succeeds.
  - An aborted writing flight becomes `DISPATCHED_UNKNOWN` (`write_failed` or `receive_failed`).
  - An aborted admitted flight becomes `FAILED`/`connect_failed` at its fence.
  - `attach_abort` returning `False` closes the race between connect returning and shutdown.
  - The registry is not held by the gate.

**Shared clock.** The registry, ledger and gate must share one monotonic clock.
- `serve_request` refuses a gate whose clock is not `time.monotonic`, because the receive and send helpers read `time.monotonic` directly.
- The admit and fence guards detect registry divergence.
- Ledger divergence is detected only partially, when `reserve` rejects the deadline as invalid; see the residual risks.

## Receipt-state mapping

| Phase | Ledger entry / flight | Receipt and client response |
| --- | --- | --- |
| Receive failure, unknown or wrong-listener sentinel, non-Jira listener | none | no receipt, no bytes (seam steps 1-2) |
| Held gate | none | no receipt, no bytes (`gate_failure`) |
| Deny impossible: ledger full or held, or the deny deadline has passed | none | no receipt, no bytes (`receipt_unavailable` or `deadline_expired`) |
| Precheck fails (revoked, expired, heartbeat-late, held registry, closed gate, stale generation) | none | `NOT_DISPATCHED`/`lease_denied`, route `unmatched`, jira denial digest `4d70175f...`, unclipped deadline; 403 |
| `RoutePolicyError` | none | `NOT_DISPATCHED`/`request_rejected` (400) or `route_denied` (403), with `e.request_digest` |
| Permit route; upstream unconfigured; `prepare` failure or v1 digest | none | `NOT_DISPATCHED`/`permit_denied` or `route_denied`, with the route denial digest (`d25b40c6...` for `jira.issue.get`, `e527abd1...` for `jira.search`); 403 |
| Less than 2.0 s of dispatch budget before reserve | none | `NOT_DISPATCHED`/`deadline`, with the prepared digest; 504 |
| Closed gate or catalog `unavailable` at reserve | none | `NOT_DISPATCHED`/`lease_denied` or `route_denied`, with the prepared digest; 403 |
| `reserve` | reserved / reserved | none yet (counts toward the 32 flights) |
| Flight or ledger capacity | none | no receipt, no bytes |
| `admit` denial | finalized / removed | `NOT_DISPATCHED`/`lease_denied`, `permit_denied` or `deadline`; 403 or 504 |
| `admit` success (L1) | connecting / admitted | none yet |
| Connect exception, including a connect deadline, or a malformed channel | finalized / removed | `FAILED`/`connect_failed` or `upstream_tls_failed`; 502 `forwarder_upstream_failed` |
| Fence denial (revoked after admit, shutdown, time, permit slot) | finalized / removed | `FAILED`/`connect_failed`; 502; zero application bytes |
| Fence success (L2) | dispatched / writing | none yet |
| Send failure | finalized | `DISPATCHED_UNKNOWN`/`write_failed` (502 `forwarder_dispatch_unknown`) or `deadline` (504) |
| Receive failure or stall | finalized | `DISPATCHED_UNKNOWN`/`receive_failed` (502) or `deadline` (504) |
| Connector returns a non-serializable `ParsedResponse` | finalized | `DISPATCHED_UNKNOWN`/`malformed_response`; 502 |
| Unmapped exception after admission | finalized | before the fence, `FAILED`/`connect_failed`; after it, `DISPATCHED_UNKNOWN`/`abandoned`; 502 |
| Response received | finalized | `TRANSPORT_CONFIRMED`/`ok` (byte-exact 200), or `response_policy_rejected` (fixed 502 `forwarder_response_rejected`, with `http_status_class` and `response_digest` recorded) |
| Deadline passes unfinalized (misbehaving connector) | swept / overdue until the owner returns | `NOT_DISPATCHED`/`abandoned` or `DISPATCHED_UNKNOWN`/`abandoned`; client EOF; closeout `overdue` |

`PARTIAL` is not produced; see Deferred item 5. Every receipt has these properties:
- `generation` equals the registry generation;
- `lease_id` and `attempt_id` come from the store entry, which was copied from the registry record;
- `request_bytes` is the exact inbound wire count;
- `request_digest` follows the digest rule in Module 2 and is never `routed.request_digest`.

**Lease states** (spec L417):

| Spec state | Registry state | Closeout state |
| --- | --- | --- |
| REGISTERED | `registered` | `open` |
| ACTIVE | `active` | `open` |
| REVOKING | `revoked` | `draining`, or `overdue` (the Receiver treats it as UNKNOWN) |
| REVOKED | `revoked` | `quiescent` |
| EXPIRED | `expired` | `quiescent`, or `overdue`; never `draining` |
| (record aged out) | none; gate `pruned` | `quiescent`, or `overdue` |

`unknown` means a held registry, ledger or gate; an invalid ID; or a lease that neither the registry nor the gate's store remembers.

**Tickets 37 and 38:**

| Receipt | Ticket 37 | Ticket 38 |
| --- | --- | --- |
| `NOT_DISPATCHED` | `NOT_DISPATCHED`, the only state eligible for the shorter Report path; includes missing or late permit approval | `failed_before_dispatch` |
| `FAILED` | nothing written. For a future permit route, the permit was consumed at L1 and is never revived. Not eligible for the shorter Report path. | `failed_before_dispatch`, kept distinct in the receipt |
| `DISPATCHED_UNKNOWN` | `DISPATCHED_UNKNOWN` | `dispatched_unknown` |
| `TRANSPORT_CONFIRMED` | never `CONFIRMED`: only ticket 37 plus read-back can confirm | transport receipt only |

Only reads exist, so no effect obligation is created.

## Upstream contract in 13a

The connector contract is trust-based in 13a, and 13b must prove it against a real synthetic TLS upstream:
- `prepare` is pure and never returns the v1 digest;
- `connect` writes no application bytes and is called at most once, only after an `Admission`, never under `G`;
- `abort` is idempotent, thread-safe and non-blocking, and safe before, during, after and concurrently with `close`;
- `send` is the first write and happens only after `write_admitted`;
- `receive` enforces 20 s inactivity and returns only codec-parsed responses;
- `close` always runs, including on a malformed channel that has a callable `close`.

13a tests use in-process fakes that record calls.
- A fake asserts `gate.is_admitted(admission)`.
- A fake asserts that `G` is free by having a helper thread call `gate.snapshot()` and return within 0.5 s.
- A fake's `prepare` returns `sha256(b"fake-v2|" + routed.request_digest.encode()).hexdigest()`. This proves that receipts carry the prepared digest and never `routed.request_digest`. For the unit-12 golden requests the values are computed in this revision; tests pin them as literals and recompute them independently:
  - `jira.issue.get` (`SYN-1`, default fields): `3bf1e11b2d062dd9d37a9b959c9ca290a0821153da52361cbc8cd74df7124acf`;
  - `jira.search` (default `maxResults`): `fd5f424e39922fd96b79a74c2261daf83aafd9323ebef92ddce88e60e2bbb804`.

## Ownership and validation

**Implementer A** owns `forwarder_dispatch.py` and `tests/test_forwarder_dispatch.py`. The tests are deterministic, with one `FakeClock` shared by the registry, ledger and gate, and use unit-12 golden inputs (policy-r1, scope-r1 manifest `849028ca...`):
- **Construction:**
  - exact types; `generation_mismatch`; `system_clock`;
  - a second gate over the same registry, the same ledger, or both gives `authority_claimed`, and a refused attempt claims neither object;
  - `copy.copy` of a claimed registry is refused.
- **`install_scope`:**
  - the golden binding succeeds, and the entry's fields equal the registry record's;
  - each single-field mismatch (run, attempt, digest, a grafana grant) gives `manifest_binding_mismatch`;
  - `replace(grant, expires_at=...)` gives `lease_unverified` on both a registered and an active lease;
  - `replace(grant, scope_digest=D2)` with a second manifest of digest `D2` gives `lease_unverified` on both lease states. On the registered lease, this proves that step 5, not `check`, catches it;
  - `replace(grant, receiver_boot_id=...)` gives `lease_unverified`;
  - a grant from another registry gives `generation_mismatch`;
  - an expired lease gives `grant_expired` or `lease_unverified`;
  - a revoked or unknown lease gives `lease_unverified`;
  - both registered and active leases are accepted;
  - reinstalling returns the identical object, and another manifest gives `scope_conflict`;
  - 1,024 entries fill the store, and the 1,025th gives `scope_capacity` unless reconcile frees slots for pruned records;
  - **byte cap:** manifests of a measured canonical size near `MAX_MANIFEST_BYTES` are installed until the next would exceed `MAX_SCOPE_BYTES`, which gives `scope_capacity` exactly at that boundary. 256 such installs are never all accepted, and `snapshot()["scope_bytes"]` equals the sum of the charges;
  - retention pruning at 310 s releases charge;
  - `gate_closed` and `gate_held`.
- **`resolve`:** hit; cross-service, malformed and retained-past sentinels give `None`; an unknown service gives `ValueError`.
- **`precheck`:** true only when authorized; false after revoke, expiry, heartbeat-late (+15 s), boot replacement, a registry hold, a gate hold, or shutdown.
- **`deny`:**
  - each `DENIAL_REASONS` value maps to its fixed local response;
  - `abandoned` gives `invalid_reason`;
  - a full ledger gives `receipt_unavailable`;
  - a passed deadline gives `deadline_expired`.
- **`reserve`:**
  - `binding_mismatch`;
  - `route_unavailable` via `replace(routed, route_id="jira.issue.create")` and via a monkeypatched `ROUTE_CATALOG`;
  - `deadline_exceeds_lease`;
  - the 33rd flight gives `dispatch_capacity`. The slot is freed by `finish`, by the owner observing `deadline_expired`, or by `release`. An overdue flight whose owner has not returned keeps its slot, and `reserve` marks it overdue before the capacity check;
  - `receipt_unavailable`, `deadline_expired`, `gate_closed` and `gate_held`.
- **`admit`:**
  - success: the ledger shows `connecting`, `admitted_at == check.observed_at`, and every deadline follows its formula;
  - each retirement cause gives `lease_denied`;
  - another lease's sentinel gives `sentinel_mismatch`;
  - `replace(routed, requires_permit=True)` gives `permit_denied`;
  - a remaining budget of 1.999 s gives the 504 `deadline` receipt, while exactly 2.0 s admits;
  - `handle_consumed`, a forged handle (`handle_unknown`), and `deadline_expired` after the deadline;
  - a forged handle with a faulting clock gives `handle_unknown` and leaves the gate ready, because the lookup precedes the clock read;
  - a registry on an offset `FakeClock` gives `clock_domain_mismatch`: the gate is held and later reserves fail with `gate_held`.
- **`begin_write`:**
  - success: the ledger shows `dispatched` and `write_deadline == min(observed + 10, exchange_deadline)`;
  - each retirement cause between admit and fence gives a `FAILED`/`connect_failed` receipt and a 502, and removes the flight;
  - sentinel mismatch;
  - `observed == exchange_deadline - 0.5` admits, and `exchange_deadline - 0.4999` gives `insufficient_time`;
  - a white-box flip of the private flight's `requires_permit` after admit gives `permit_unavailable` and `FAILED`;
  - `write_claimed`, `admission_unknown`, `deadline_expired`, and shutdown (`gate_closed`).
- **`finish`:**
  - the full legal matrix from admitted and from writing;
  - an illegal outcome, and a malformed `ParsedResponse(302, b"")` with `TRANSPORT_CONFIRMED` (ledger `invalid_response`), each give `invalid_outcome` and keep the flight, and a legal retry then succeeds;
  - an overdue or swept flight gives `deadline_expired`;
  - it works on a held gate.
- **Overdue:**
  - after the deadline, an unrelated `now()` marks the flight overdue and invokes its attached abort exactly once, with `G` free (the abort calls `snapshot()` from a joined worker);
  - the flight still counts;
  - `is_admitted` becomes `False`, and `attach_abort` returns `False`;
  - the owner's `finish`, `begin_write` or `admit` gives `deadline_expired` and removes it;
  - `release` is idempotent and returns `True` only once;
  - abort exceptions are counted in `abort_failures`.
- **`closeout`:**
  - `open`, `draining` (`drain_deadline` equal to the flight deadline), and `quiescent` with `uncertain == 1` after the clock passes the deadline and the owner finishes;
  - `overdue` while the owner has not returned;
  - pending entries are counted but never block `quiescent`;
  - an expired lease is never `draining`;
  - crossing the registry's 310 s record prune gives `lease_state == "pruned"` and `quiescent`; crossing the store entry's retention gives `unknown`;
  - a held registry, held ledger, held gate or unknown lease gives `unknown`.
- **`shutdown`:**
  - the registry's `registry_state` is unchanged (not held);
  - the gate is closed; aborts run with `G` free (the abort calls `gate.snapshot()` from a worker, which is joined);
  - `attach_abort` then returns `False`, and `precheck` returns `False`;
  - `finish` still records;
  - the second call aborts nothing;
  - abort exceptions are counted.
- **Other:** `now()` hold behavior; snapshot and repr contain no sentinel; `READ_INACTIVITY_SECONDS == forwarder_response_receive._INACTIVITY_LIMIT`; `MIN_WRITE_SECONDS <= MIN_ADMISSION_SECONDS`.

**Implementer B** owns:
- `forwarder_exchange.py`;
- both additive seams;
- `tests/test_forwarder_dispatch_seams.py`:
  - `receive_request_sized` counts equal `len(raw)` for fragmented, coalesced, zero-body and 256 KiB-body requests;
  - its error codes are identical to `receive_request`'s, and results and the shared marker are unchanged;
  - `FixedTLSListener.service` returns the service for all five listeners.
- `tests/test_forwarder_exchange.py`: deterministic, with fake connection objects. It monkeypatches `forwarder_exchange.receive_request_sized` and `forwarder_exchange.send_response`, uses the real monotonic clock shared by all three objects, and sleeps at most 0.1 s per case. Cases:
  - a full ledger during `reserve` gives EOF (`receipt_unavailable`), zero connects and no new ledger entry;
  - a full ledger during an E6 route denial gives EOF (`receipt_unavailable`) and no new ledger entry;
  - flight capacity gives `dispatch_capacity`;
  - `started <= now - 40` gives `deadline_expired` at E2;
  - `started` near `now - 40`, with a fake receive that sleeps past `handler_deadline`, gives `deadline_expired` from Deny, with no ledger entry;
  - a held gate gives `gate_failure`;
  - `send_response` raising `ResponseSendError("send_failed")` gives `delivery_failed`/`send_failed`, and a `RuntimeError` gives `delivery_failed`/`internal_failure`;
  - `serve_one` on an unopened `FixedTLSListener` gives `accept_failed`;
  - E16: `attach_abort` patched to raise gives `FAILED`/`connect_failed`, and `check_response` patched to raise gives `DISPATCHED_UNKNOWN`/`abandoned`;
  - E17: `finish` patched to raise `invalid_outcome` once gives the fallback receipt, delivered; `receipt_unavailable` closes;
  - E7c: a fake `prepare` returning `routed.request_digest` gives 403 `route_denied` with `d25b40c6...`;
  - E8: a monkeypatched catalog gives 403 `route_denied` with prepared digest `3bf1e11b...`;
  - a malformed channel with a callable `close` has `close` called once;
  - a `BaseException` subclass from a fake `send` propagates, the channel is closed, `release` removes the flight, and the ledger later shows `DISPATCHED_UNKNOWN`/`abandoned`;
  - digest-rule literal hex assertions for every denial site.
- `tests/test_forwarder_exchange_integration.py`, which uses real local TLS inbound through the asserting fixed-address adapter `ephemeral_listener` (`tests.test_forwarder_server_tls_integration`, imported as `tls_fixtures`, as existing integration tests do), `FixedTLSListener` and `connect_service_tls("jira")`, with `serve_request` or `serve_one` on a server thread. The client sends raw `Basic run:<grant.sentinel>`, Host `forwarder-jira.maoi.local:17441`, and `GET /rest/api/3/issue/SYN-1`. Upstreams are fake connectors only. Cases:
  1. **Success:** `jira.issue.get` and `jira.search` give 200 byte-exact.
     - The receipt is `TRANSPORT_CONFIRMED`/`ok`, and its digest equals the pinned prepared digest (`3bf1e11b...` or `fd5f424e...`), not `routed.request_digest`.
     - `request_bytes == len(raw)`, and its generation is the grant's.
     - Delivery is `sent`.
     - Each fake call happens exactly once.
  2. **Upstream 404:** 502 `forwarder_response_rejected` with class `4xx`.
  3. **Malformed upstream responses:** `ParsedResponse(302, b"")`, `ParsedResponse(200, b"")`, and a 200 with a body over 1 MiB each give 502 `DISPATCHED_UNKNOWN`/`malformed_response`, and the flight is removed.
  4. **No bytes** (client EOF, zero `prepare`/`connect`, no ledger entry): an unknown sentinel; a grafana listener with an uninstallable lease; a duplicate Host.
  5. **Denials with zero connects:**
     - revoked before the request: 403, `unmatched`, digest `4d70175f...`;
     - `SYN-2`: 403 `route_denied`;
     - a `fields` subset: 400;
     - `upstream=None`: 403 with digest `d25b40c6...`;
     - `prepare` raises: 403;
     - a lease with 1.5 s left: 504 `deadline` with the prepared digest, delivered before `expires_at`.
  6. **Upstream failures, each with exactly one connect:**
     - `UpstreamError("upstream_tls_failed")`: 502 `FAILED`/`upstream_tls_failed`;
     - `OSError` on connect: `FAILED`/`connect_failed`;
     - send raises: 502 `DISPATCHED_UNKNOWN`/`write_failed`;
     - a receive that blocks until its deadline and then raises `UpstreamError("receive_failed")` (mirroring unit 10), with a lease of now+4: 502 `DISPATCHED_UNKNOWN`/`receive_failed`, delivered before `dispatch_deadline`;
     - receive raises `UpstreamError("deadline")`: 504 `DISPATCHED_UNKNOWN`/`deadline`;
     - receive returns bytes: `receive_failed`.
  7. **Fence:** the fake `connect` revokes the lease before returning. Result: `FAILED`/`connect_failed` and 502; zero `send` calls; `abort` called; closeout `quiescent`.
  8. **Revocation after write:** the fake `send` revokes. Result: `TRANSPORT_CONFIRMED`/`ok` is delivered while the registry shows revoked (the L2 linearization).
  9. **Revocation while receive blocks:**
     - closeout reports `draining` with `in_flight == 1`;
     - a second connection with the same sentinel gets 403 with zero connects;
     - on release, the first client gets its 200 and closeout reports `quiescent`.
  10. **Shutdown:**
      - while receive blocks: the abort unblocks the fake, giving 502 `DISPATCHED_UNKNOWN`/`receive_failed`; later requests get 403; the registry is not held;
      - a `connect` that calls `gate.shutdown()`: attach refused, abort, fence `gate_closed`, `FAILED`.
  11. **Capacity:** with `MAX_OPEN_DISPATCHES` monkeypatched to 2 and two blocked flights, a third request gets EOF with zero connects.
  12. **Misbehaving connectors**, with a lease of now+3:
      - (a) a receive that ignores its deadline but honors `abort`: a main-thread `closeout` after the deadline reports `overdue` and fires the abort. The client gets EOF, the outcome is `closed_without_response`/`deadline_expired`, the ledger shows `DISPATCHED_UNKNOWN`/`abandoned`, and closeout then reports `quiescent`;
      - (b) a receive that ignores both deadline and abort: closeout stays `overdue`, and with `MAX_OPEN_DISPATCHES` at 1 a second request gets EOF (`dispatch_capacity`) until the test releases the fake.
  13. **Held gate:** after a registry on an offset clock triggers `clock_domain_mismatch` (that request gets its admit-denial 403), the next request gets EOF, `gate_failure`, and no new ledger entry.
  14. **`serve_one`:** it binds `listener.service`, and the client reads EOF after the one response.

**Tester C** owns three files.

*`tests/test_forwarder_dispatch_races.py`* (real threads, `Event`/`Barrier`, join timeouts). The ledger's clock is a wrapper over the shared base clock that can block in an armed thread; this is legal only in tests (see "Clock contract"). Tests advance the `FakeClock` between the authorizing check and the revoke, so that `admitted_at < revoke.observed_at` is meaningful.
- **R1.**
  - Thread A pauses inside `begin_connect` after its admit check.
  - B's direct `registry.revoke` returns while A is paused.
  - C's closeout, started after B, is still blocked 0.2 s later.
  - After A is released, C reports `draining` with `in_flight == 1`.
  - A's fence then denies, giving `FAILED`, zero sends, and closeout `quiescent`.
- **R1b.** A pauses inside `begin_dispatch` after its fence check, and B revokes. A's write proceeds and finishes `TRANSPORT_CONFIRMED`; closeout goes from `draining` to `quiescent`.
- **R2.** R1 with a real `ForwarderControl` Revoke over `socketpair`, using `authenticate_receiver` with `forwarder_uid=os.geteuid()`.
- **R3-R6.** The same scenario for control EOF, a fresh boot replacement, `ForwarderControl.shutdown` (hold), and heartbeat loss (+15 s, then any registry call).
- **R7.** A revoke that completes before admit gives a denial and zero connecting entries.
- **R8.** A strictly increasing thread-safe counter clock is shared by all three objects; 16 threads run 50 handles each against one revoker. Assertions:
  - every Admission and every `write_admitted` observation precedes `revoked_at`;
  - every later admit is denied and every later fence gives `FAILED`;
  - every non-`NOT_DISPATCHED` ledger entry matches exactly one Admission;
  - no false `clock_fault` occurs, which proves the tick reads under `G`.
- **R9.** Shutdown concurrent with admits and fences: no Admission or `write_admitted` is returned after shutdown linearizes.
- **R10.** A 2-second mixed load (control revoke/heartbeat, admit, fence, closeout, snapshot, shutdown, release) with a deadlock watchdog; no thread is left alive.
- **R11, overdue race.**
  - Flight A is writing with an attached abort.
  - The clock passes A's deadline, and thread B's `reserve` (its `now()`) runs before A's `finish`.
  - A's abort fires exactly once on B's thread, outside `G`.
  - B's capacity check still counts A.
  - A's `finish` gets `deadline_expired`, never `admission_unknown`, and only then is the slot freed.
  - Closeout reports `overdue` between the two events and `quiescent` after.

*`tests/test_forwarder_dispatch_adversarial.py`*:
- **AST, on both new modules:**
  - no `ast.Raise` inside any `ExceptHandler`;
  - exact import allowlists, with the named imports listed above and no `TYPE_CHECKING` exception;
  - no `socket`, `ssl`, `select`, `os`, `subprocess`, `importlib` or `__import__`.
- **Forgeries:** forged, `replace`d, copied and cross-gate `ScopeEntry`, `DispatchHandle` and `Admission` objects are refused, and `release` of a foreign token returns `False`. A second gate over claimed objects, or over copies of them, is refused.
- **Exception chains:** a walk for every `DispatchError` code with a planted marker; `__cause__` and `__context__` are `None` and the marker appears nowhere.
- **Secret walk:** gate state (excluding the registry and ledger references), snapshot, closeout and every repr contain neither the sentinel (as str or bytes) nor the index key.
- **Closed codes:** every raised code is in `DISPATCH_ERROR_CODES`, and admission and fence codes map only to legal reasons.

*`tests/test_forwarder_exchange_adversarial.py`* (real local TLS):
- argument types, and a gate with a non-monotonic clock gives `ValueError`;
- a manifest from another policy gives 403 `route_denied`;
- a Jira sentinel replayed on the Confluence listener gives EOF;
- connector exception text with a planted marker never appears in the `ServeOutcome`, receipts, or the ledger, gate or registry snapshots;
- ServeOutcome codes are closed;
- event-order proof: connect only after the ledger shows `connecting`, send only after it shows `dispatched`, and exactly one connect and one send;
- ledger capacity during reserve over real TLS gives EOF, zero connects and no new entry.

**Root** owns this plan file, the docs section, and validation:
1. `pytest -q` on the seven new files;
2. the existing focused forwarder command, unchanged and green;
3. full `pytest -q`;
4. `ruff check` on changed files;
5. `git diff --check`;
6. the four protected dirty-file hashes unchanged, and ticket-19 C2 untouched;
7. independent reviewers bind the final hashes, including a confirmation that `receive_request`'s behavior is identical;
8. explicit-path staging and one local commit, with no push.

## Judge findings resolved (revision 1)

| # | Finding | Resolution |
| --- | --- | --- |
| A1 | atomic-first: no pre-write lease check, so a first byte could follow a revocation (spec L156-157, docs L39-41) | Write fence `begin_write` (L2): under `G`, the stored-generation `check` plus `begin_dispatch`, with no I/O before `send`. A denial finalizes `FAILED`/`connect_failed` with zero bytes. No registry callback; the receipts module is unchanged. |
| A2 | atomic-first: upstream and send deadlines equal the reservation deadline, so the sweep wins and the 504 row is fake-only | `RESPONSE_MARGIN_SECONDS`: all upstream work ends at `exchange_deadline = dispatch_deadline - 1`, so `finish` and `send_response` precede the sweep. The 504 and receive-stall rows are exercised over real inbound TLS. |
| A3 | atomic-first: the `FAILED`/`DISPATCHED_UNKNOWN` split rests on an unverified connector contract | `send` only after the fence, so `FAILED` depends solely on "connect writes no application bytes". This is listed as not qualified; 13b proves it with a fixture that observes zero application bytes. |
| A4 | atomic-first: the AST test forbids `ssl` while exchange imports it under `TYPE_CHECKING` | Exchange imports no `ssl` at all; the connection is typed `object`; the allowlists are exact with no exception. |
| A5 | atomic-first: phase deadlines reuse the step-1 `now` | `connect_deadline` and `write_deadline` are computed inside `admit` and `begin_write` from fresh clock reads under `G`. |
| A6 | atomic-first: receipts carry the v1 digest, and the 13b sketch bumps the unit-12 tag | The reservation digest comes from `connector.prepare`, and E7c refuses a v1 digest. 13b puts rule v2 under a new tag in `forwarder_upstream`, and the unit-12 tag and golden vectors are untouched. |
| A7 | Race timestamps; unlocked clock reads cause a false hold | The tick reads and compares under `G`; FakeClock advances between check and revoke; the counter-clock test R8. |
| A8 | Machinery without a production caller | Kept bounded: closeout and shutdown are needed for spec L162-163 and bounded drain. Listed under "Not qualified". |
| U1 | upstream-first: the atomic final check is deferred | Both L1 and L2 are implemented here, with race tests. |
| U2, U3 | Dead deadline branches; a stalled recv is not `deadline` | The margin (A2). Tests expect `receive_failed` for a stall and `deadline` only for an explicit between-reads `UpstreamError("deadline")`. |
| U4 | `getaddrinfo`, a first-record policy, unbounded blocking | Not adopted. 13b takes an operator-supplied address shape with no resolution in source, and the real origin question stays open (Deferred item 1). |
| U5 | Invented base paths and bearer profiles; `launch_at` input | 13b is Jira-only with a Basic profile. `expires_at` is proven to be the effective limit, so there is no `launch_at` input. |
| H1 | handler-first: changes `forwarder_leases` and `forwarder_receipts` and moves the permit point | Neither is changed. The permit is consumed at admit (`begin_connect`, per receipts plan L47-48 and L63) and re-verified at the fence ("Permit rule"). |
| H2 | handler-first E2E 16: a stall expects 504 | A stall is `DISPATCHED_UNKNOWN`/`receive_failed`, 502. |
| H3 | handler-first P9: pre-socket errors over-reported as `DISPATCHED_UNKNOWN` | All connect-phase failures, including a connect deadline, are `FAILED`, and so are unmapped exceptions before the fence (E16). |
| H4 | handler-first: size | Two new modules plus two property-sized additive seams; upstream TLS moves to 13b. |
| H5 | handler-first: credential not bound to a service | 13b binds credential profiles per service (Jira Basic only). |
| H6 | handler-first: `functools` missing from the allowlist | Not applicable (no `partial`); the allowlists are exact. |
| G-graft | Listener service binding | `serve_one` uses the additive `FixedTLSListener.service`. |

## Critic issues resolved (revision 2)

| # | Severity | Issue | Resolution |
| --- | --- | --- | --- |
| 1 | high | `now()` deleted expired flights, so the codes depended on races; aborts were lost, slots freed early, and `quiescent` was reported while writing | "Overdue flights": ticks mark flights `overdue` and never delete them; the attached abort fires once outside `G`; the flight keeps its slot until the owner's `admit`, `begin_write` or `finish` returns `deadline_expired` or the owner calls `release`. Closeout has an `overdue` state (treated as UNKNOWN). `reserve` ticks before its capacity check. I5 and I8 are qualified for conforming connectors. Tests: race R11, the overdue unit cases, and integration case 12. |
| 2 | medium | A malformed `ParsedResponse` reaches an unmapped ledger `invalid_response` | E14 requires `response_digest(response)`; a failure gives `DISPATCHED_UNKNOWN`/`malformed_response`. `finish` maps `invalid_response` to `invalid_outcome` and keeps the flight, and E17 makes one fallback finish. Integration case 3 covers 302, an empty 200 and a body over 1 MiB. |
| 3 | medium | `install_scope` trusts grant fields; `check` skips the scope comparison for registered leases | Install step 5 verifies the registry record: exact equality of service, run, attempt, boot, scope digest, expiry and generation, plus a live state. The entry is built from the record. Tests use `replace(grant, expires_at=...)` and `replace(grant, scope_digest=...)` on both lease states. |
| 4 | medium | The permit slot at L1 contradicts "atomically with the final lease check" | "Permit rule": consume at L1 (the receipts meaning of `FAILED` is kept) and re-verify at L2, atomically with the final check. Expiry or binding failure is a fence denial, `FAILED` with zero bytes, and never revived. Late approval at L1 is `NOT_DISPATCHED`. The fence has a fail-closed `permit_unavailable` slot. The ticket-37 table, admit step 5, fence step 6 and Deferred item 2 are updated; there is a non-claim and an open question. |
| 5 | medium | No rule for a failed `gate.deny()` | One Deny procedure for every site: check the clock, then the deadline (`deadline_expired`), then map `receipt_unavailable` to `receipt_unavailable`, the ledger deadline race to `deadline_expired`, and anything else to `internal_failure`. Deterministic tests cover a full ledger during a route denial and `started` near now-40. |
| 6 | medium | A second gate over the same registry or ledger | Constructor claim under `_AUTHORITY_LOCK` with a private marker; `authority_claimed` is added (23 codes). The ledger's writers are documented as the gate and `send_response` only. Second-gate and copy tests. |
| 7 | medium | Store capped by count but not bytes | `MAX_SCOPE_BYTES` with a per-entry charge of canonical manifest bytes plus `SCOPE_ENTRY_OVERHEAD_BYTES`; refusal with `scope_capacity`; a byte-cap test with near-maximum manifests. Dropping manifests after retirement was considered and rejected, because it would break entry identity. |
| 8 | low | `quiescent` reverts to `unknown` after the record prune | A record that aged out while the store entry remains reads `lease_state` `pruned` and stays `quiescent`. I8 is qualified to the store entry's retention; a test crosses the 310 s prune. |
| 9 | low | The admit step order does not work | Admit looks up the handle first, then reads the clock; the fence already did. There is a test with a forged handle and a faulting clock. |
| 10 | low | Inconsistent digest rule | "Digest rule, stated once": before a successful E7c, the route denial digest; after it, the prepared digest. E8 `route_unavailable` names its digest. Literal-hex assertions at every site. |
| 11 | low | Nothing enforces "never the v1 digest" | E7c refuses `compare_digest(digest, routed.request_digest)` with `route_denied`; a deterministic test uses a v1-returning fake. |
| 12 | low | No minimum write budget at the fence | `MIN_WRITE_SECONDS = 0.5` (at most `MIN_ADMISSION_SECONDS`); fence step 7 denies `insufficient_time`, giving `FAILED` with zero bytes; both sides of the boundary are tested. |
| 13 | low | Gate shutdown mutates the registry through `hold()` | Removed. The closed gate alone denies; the supervisor order is documented; a test asserts the registry is not held. |
| 14 | low | "G never calls injected code" is false for clocks | "Clock contract": only the three non-blocking, non-reentrant monotonic clocks; test-only blocking is called out; the docs record it. |
| 15 | low | Deny deadlines unclipped | E6 and E7 denials use `dispatch_deadline`. E5 keeps `handler_deadline` as a stated deliberate deviation. |
| 16 | low | Channel contract gaps: close on a malformed channel; abort versus close | A malformed channel's callable `close` is called once. `abort` must be safe before, during, after and concurrently with `close`, and non-blocking; 13b tests the ordering. |
| 17 | low | Held and closed gates behave inconsistently | Decided: a held gate closes every request without bytes (`gate_failure`), and a closed gate returns 403s. The "every gate state" wording is narrowed. Integration case 13. |
| 18 | low | Untested `ServeOutcome` branches | New deterministic `tests/test_forwarder_exchange.py`, covering ledger capacity at reserve and deny, `delivery_failed`, `accept_failed`, `gate_failure`, E16 both sides, E17, E2 and Deny `deadline_expired`, and `BaseException` release. Plus a real-TLS ledger-capacity case. |
| 19 | low | The `.forwarder_dispatch` import names are unlisted | The exchange allowlist names every imported symbol, adding `hmac` for E7c and `response_digest`/`ReceiptError` for E14. The dispatch allowlist names its stdlib symbols. |
| 20 | low | 13b decides an unresolved origin input with a fixed IPv4 pin | Deferred item 1 is reframed: `(address, port)` is a synthetic-test and trusted-operator configuration shape only. A new 13b non-claim covers real origin resolution, address stability and IPv6, and the route stays unavailable (`upstream=None`) until the spec's origin decision (L441-448) is made. |

## Deferred

1. **13b: `forwarder_upstream.py`, the real `UpstreamConnector`.**
   - **Endpoint.** A trusted operator configuration object `UpstreamEndpoint(service, host, address, port, ca_pem, revision, credential_id)`, filled synthetically in tests. It is a configuration **shape**, not a decision about real origins.
     - `host`: lowercase LDH with a `.invalid` TLD in tests; never an IP, `localhost` or `*.maoi.local`.
     - `address`: a canonical IP address supplied by the operator. Source performs no DNS. Tests reject loopback, unspecified, link-local, multicast, reserved and broadcast addresses.
     - **Non-claim:** real service origin resolution, address stability, IPv6 and hosted-site address churn are unresolved choices (spec L441-448). No production endpoint is configured, and the route stays unavailable (`upstream=None`, 403) until that decision is reviewed.
   - **Trust.** A fresh strict context per connect:
     - `PROTOCOL_TLS_CLIENT`, TLS 1.2 or newer, `CERT_REQUIRED`, `check_hostname`, `hostname_checks_common_name=False`, `VERIFY_X509_STRICT`;
     - no compression or renegotiation, ALPN `http/1.1`;
     - `cadata` as the only trust source, with `cert_store_stats` `x509 == x509_ca ==` the bundle count;
     - an AST ban on default trust, `keylog`, `os`, `pathlib`, `open` and `environ`.
   - **Credential.** A redacted `BasicCredential`: `__slots__`, no `__dict__`, identity equality, pickling and copying refused. `CREDENTIAL_PROFILES = {"jira": "basic"}`; other services stay unavailable.
   - **Shapes and digest.** A `DISPATCHABLE_SHAPES` allowlist (`jira.issue.get`, `jira.search`). `prepare` computes rule v2 under the new tag `maoi.forwarder.request.v2` with an endpoint/service-config digest, binding Host.
   - **Transport.** Canonical serializer; writes in chunks of at most 16 KiB; `receive` through `receive_response`; thread-safe, non-blocking `abort` via `shutdown`, safe before, during and after `close`.
   - **Tests.**
     - A synthetic TLS upstream on an ephemeral port behind an asserting adapter that maps only the configured `(address, port)`.
     - Fixture-captured wire equals the bytes rebuilt from the descriptor (property test).
     - Zero application bytes on every connect failure.
     - SNI-callback revocation gives a fence denial, `FAILED` and zero application bytes.
     - Revocation after the upstream reads the request gives `TRANSPORT_CONFIRMED` delivered.
     - Abort and close ordering, including concurrent calls.
     - Golden vectors are recomputed independently.
2. **Control framing, as one unit:**
   - a control closeout command, or a Revoke reply `{revoked_at, closeout_state}` (control lock, then `G`, then `R`), including how `overdue` and `pruned` are presented;
   - manifest delivery and `install_scope` over control (frames above 8 KiB);
   - Register refusal for services without a scope type;
   - AuthorizeDispatch permits under the rule decided here: consume in admit step 5, atomically with the L1 check; re-verify expiry, digest and binding in fence step 6, atomically with the L2 check.
3. **Receipts amendment**, if wanted, as a separately reviewed step: `FAILED`/`lease_revoked` (403) for fence denials, and `FAILED`/`deadline`.
4. **Service worker supervisor:** an accept loop per `FixedTLSListener`, bounded handler threads, and a shared join deadline. The shutdown order is `ControlService.stop`, then `DispatchGate.shutdown`, then listener close. Plus `Ready(service)` readiness wiring.
5. **PARTIAL and codec-level malformed-framing classification,** which needs a collector that reports progress. 13a uses `malformed_response` only for a connector-built response that the serializer refuses.
6. **Durable ticket-37 journal and ticket-38 `report_dispatch` hand-off,** plus restart reconciliation.
7. **Remaining routes and services:** mutation routes, the Anthropic route and SSE, other services' scope types, continuation, projection, and codec charset tolerance.
8. **Post-revocation withholding** of completed read responses (not required by the spec).
9. **A receipt path for sentinels with no lease** (a receipts extension), if wanted.

## Not qualified by this unit

- Any real upstream connection, TLS trust, origin, address resolution, serializer or credential; the connector contract; the v2 digest.
- Native clients.
- Deployed listeners, UID or kernel isolation.
- A production caller of `install_scope`; manifest delivery; control-level closeout.
- A worker supervisor or accept loop; readiness.
- AuthorizeDispatch permits: the consume-at-L1, re-verify-at-L2 rule is decided but not implemented or tested against a real permit. Also mutation routes, ticket-37 intent and ticket-38 exposure.
- PARTIAL; the durable journal; SSE; any non-Jira route.
- Hard real-time deadlines: a connector that ignores its deadlines is bounded only by the ledger sweep and the overdue abort. The client then sees EOF.
- A connector that ignores both deadline and abort: it holds one flight slot and keeps closeout at `overdue` until it returns.
- Delivery of large `ok` bodies within the 1 s margin, which may end `send_unknown`.
- Ledger clock divergence.
- The sizing of `MAX_SCOPE_BYTES`, `SCOPE_ENTRY_OVERHEAD_BYTES` and `MIN_WRITE_SECONDS`, which are local choices.
- History-ring churn from three checks per request.
- Any external effect.

Residual risks the reviewers must accept:
- **Closeout visibility.** A remote Receiver cannot distinguish `draining` from `quiescent` until Deferred item 2 lands, so it must assume `draining` until revocation + 40 s, and treat `overdue` as UNKNOWN once visible.
- **Closeout memory.** After the store entry's retention (`installed_at + 310` s), the gate forgets the lease and reports `unknown`; the Receiver's durable evidence must cover later questions.
- **Reads delivered to a revoked Run.** Reads admitted and written before revocation are delivered to the revoked Run.
- **Coarse fence receipt.** A fence denial reports a coarse 502 rather than 403.
- **Lock hold time.** `closeout` and `install_scope` (at capacity) hold `G` while reading full registry and ledger snapshots (at most 1,024 plus 2,048 records).
- **Foreign-thread aborts.** An overdue flight's abort runs on whichever request thread ticks first, so a slow abort delays that unrelated request. The contract requires `abort` to be non-blocking.
- **Permanent claims.** The authority claim is never released, so a registry or ledger can serve only one gate for its lifetime. This is intended: a new generation needs new objects.
