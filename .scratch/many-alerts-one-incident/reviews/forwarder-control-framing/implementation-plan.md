# Scope manifest delivery and lease closeout over authenticated Forwarder control (unit 14)

2026-09-23, revision 2. **Baseline:** `c1869a2` (unit 13a). This is the fourteenth separately authorized local application unit under the [approval record](../native-runtime-source-implementation-approval.json).

**Scope.** Source and synthetic tests only. Tests use local socketpairs and pathname Unix sockets, synthetic 32-byte secrets and fake clocks. Out of bounds: push, provider/native/tenant calls, real credentials, C2 retries, paid experiments and deployment. Run the full suite before committing. Every existing test file stays byte-identical.

**Protected state.** Seven dirty paths exist at baseline (re-checked 2026-09-23 with `git status --porcelain`):
- the issue 19 file;
- `planning-frontier-2026-09-18.md`;
- the 13b plan, `forwarder-upstream/implementation-plan.md`;
- the two untracked ticket-19 `c2-ingestion-*` files;
- the two untracked, in-progress 13b files, `grafana_jsm_sandbox/forwarder_upstream.py` and `tests/test_forwarder_upstream.py`.

None of them is edited, staged or committed. Ticket 19 C2 is out of scope.

**Sequencing with 13b.** 13b is in progress as the two untracked files above. They import `forwarder_dispatch`, `forwarder_exchange`, `forwarder_http_response`, `forwarder_json`, `forwarder_response_receive` and `forwarder_routes`. This unit changes none of those, and 13b imports neither control module. Both units append to `docs/forwarder-control.md` and its focused pytest command. Whichever commits second rebases those two documentation edits. No source reconciliation is needed. The full-suite run will collect the untracked 13b test; "Ownership and validation" says how that result is recorded.

**Root reconciliation, 2026-09-23, against the 13b commit `74b10e8`.** 13b committed first. The plan's source line references re-read unchanged, because no module under `grafana_jsm_sandbox/` other than the new `forwarder_upstream.py` changed after `c1869a2`. Four items supersede the text above and "Ownership and validation":
- **Protected state.** It is back to the four original dirty paths: issue 19, `planning-frontier-2026-09-18.md` and the two ticket-19 `c2-ingestion-*` files. The 13b plan and files are committed and are no longer protected.
- **Documentation.** The docs line references in "Documentation" still hold (L61, L68-73, L494-497, L514-515, L533-535, L561-562). The next-units sentence and the focused command now sit at the end of the new "Synthetic fixed-origin upstream connector" section (docs L566 onward), and the focused command already lists the three 13b files.
- **Validation.** There is one plain `pytest -q` run. The baseline at `74b10e8` is 3358 passed, 36 skipped, so the `--ignore` run and the observed-but-not-owned 13b hashes are dropped. `git status --porcelain -- tests/` must show only this unit's new test files.
- **Test files.** Implementer C's cases are split across three disjoint files, so testers can work in parallel. `tests/test_forwarder_control_gate.py` holds the fixtures and cases 1, 4, 5, 6, 25, 26 and the case-24 AST check. `tests/test_forwarder_control_gate_closeout.py` holds cases 2, 3, 7-13, 17 and 18. `tests/test_forwarder_control_gate_races.py` holds cases 14-16, 19-23, the case-24 thread-ownership checks, 27 and 28. The focused command lists all five new files.

**How this plan was made.** The base is `extend-control`, which both judge panels chose, with grafts from `receiver-side` and `adapter-layer`. "Judge findings resolved" maps every judge error to its resolution. Revision 2 resolves all thirteen critic issues; see "Critic issues resolved (revision 2)".

These facts were re-read against the working tree on 2026-09-23:
- **Closeout order.** `DispatchGate._closeout_locked` reports `open` for a registered or active lease *before* it looks at overdue flights, so a live lease with an overdue flight reports `open` with `overdue > 0` (forwarder_dispatch.py L928-940). `overdue` counts gate flights, and `in_flight` counts ledger entries. `pruned` means the registry record is gone while the gate's scope entry remains (L901-906).
- **`install_scope`:**
  - raises `TypeError` for arguments of the wrong exact type, and `DispatchError` otherwise;
  - accepts a `registered` lease (check reason `lease_registered`);
  - re-compares the full registry record, including `receiver_boot_id` (L396-489).
- **The install race window.** Inside `install_scope`, with `G` held, `registry.check` (L424) and `registry.snapshot()` (L438) each take `R` separately. A replacement's `_disconnect` takes `C` then `R`, never `G`. A retirement can therefore land after the check or the snapshot and before the entry is inserted.
- **Abort callbacks.** `install_scope` and `closeout` drain abort callbacks in `finally`, outside `G` (L368-381).
- **Clocks and snapshots.**
  - `gate.closeout` reads the registry and ledger snapshots before its own clock tick.
  - `registry.snapshot()` runs `_now()`, which can expire records, revoke every live lease for heartbeat lateness, prune records and set `_control_stale` (forwarder_leases.py L330-349).
  - The ledger snapshot sweeps abandoned entries.
  - A held registry still returns a snapshot, with `registry_state == "held"`.
  - `admit` holds the gate on `clock_domain_mismatch` only for the registry-vs-gate clocks (L676-681). Ledger clock divergence is detected only partially (docs L563-564).
- **After a hold.** `registry.handshake` fails with `registry_held`, so no new control session can authenticate on a held generation. The committed `_disconnect` then fails too, so `ControlOutcome.closeout` is `unknown`.
- **Heartbeat window.** `HEARTBEAT_SECONDS = 15.0`. `register` requires a fresh session, and `_now()` revokes every live lease once 15 s pass without a heartbeat (L345-348). Spec L145 expects a heartbeat every 5 s.
- **Supervisor.** `ControlService` accepts any `isinstance(control, ForwarderControl)` whose `_closed` is `False` (forwarder_supervisor.py L56-63).
- **No AST coverage of control.** No AST or import test covers `forwarder_control.py` or `forwarder_control_protocol.py`. The only AST tests are in the dispatch, exchange, json and routes adversarial files.
- **Existing registrations are Jira only.** Every registration through `ForwarderControl` in the existing tests uses `service="jira"`: control L83/232/330, listener_control L68 and supervisor_integration L59. `test_forwarder_dispatch_races.py` L151 and the Grafana registration in `test_forwarder_exchange_integration.py` call `LeaseRegistry` directly. No existing test expects `invalid_service` from control.
- **Codec internals:**
  - `_socket_timeout` raises `socket_failure`;
  - `_recv_exact` checks its deadline after the final read;
  - `recv_frame` rejects any array inside a root object with `arrays_not_allowed`. A canonical manifest has a top-level `routes` array.
- **Manifest size.** `forwarder_routes.MAX_MANIFEST_BYTES = 16_384`. `ScopeManifest` accepts only `service == "jira"`. With 256 search labels a canonical manifest can exceed 8,192 bytes. `SERVICE_PROFILES` is `anthropic`, `confluence`, `grafana`, `jira`, `kubernetes`.

## Why this unit

The 13a gate can install a Receiver scope manifest and compute a lease closeout, but:
- `install_scope` has no production caller;
- closeout "is not yet a control reply" (docs L514-515, L533-535);
- a remote Receiver cannot tell `draining` from `quiescent` (dispatch plan, residual risk "Closeout visibility").

Dispatch plan Deferred 2 and routes plan Deferred 2 name the missing pieces:
- manifest delivery over control, in frames above 8 KiB, with the digest checked against the grant;
- a Revoke reply `{revoked_at, closeout_state}` or a closeout command, including how `overdue` and `pruned` are presented;
- refusal of Register for any service that has no scope type.

This unit delivers all three, the third in both controller modes. AuthorizeDispatch permits (Deferred 2, fourth bullet) stay deferred until the ticket-37 durable intent journal exists.

**Shape of the change.** Everything goes over the **existing** authenticated control connection (spec L221-222). There is no second channel.
- **Refusal of unscoped services in both modes.** `register` for `confluence`, `grafana`, `kubernetes` or `anthropic` fails with `scope_type_unavailable` before any registry call. This applies with or without a gate.
- **One new gated command, `register_scoped`.** It is one JSON header plus one attachment, and one reply. The Forwarder validates the manifest before any registry mutation. It registers under the committed owner fence, installs the scope, and re-checks the owner fence. Only then does it send the sentinel. There is no pending-grant state and no registered-but-unscoped window.
- **Revoke.** In gated mode, a Revoke reply is `ok:true` only when the closeout is `draining` or `quiescent`. Every uncertain closeout holds the registry and fails the Revoke.
- **Closeout command.** A `closeout` command polls without spending authority. It holds on the same uncertain observations.
- **Lock order.** The gate is always called with the control lock released.

## Module 1: additive attachment codec in `grafana_jsm_sandbox/forwarder_control_protocol.py`

The committed `MAX_FRAME_BYTES = 8192`, `recv_frame`, `send_frame` and the JSON validator do not change.

**Additions:**
- `MAX_ATTACHMENT_BYTES = 16_384`. This equals `forwarder_routes.MAX_MANIFEST_BYTES` and spec L238's proposed control frame size of at most 16 KiB. A test asserts the equality; the codec does not import routes.
- The module docstring gains one sentence: exactly one opaque attachment kind, a Receiver scope manifest, may follow a schema-valid gated registration header, and its length is declared twice and must match.

**`send_attachment(sock, data: bytes, *, timeout=FRAME_TIMEOUT_SECONDS) -> None`**
1. If `type(data) is not bytes` or `data` is empty, raise `invalid_payload`. If `len(data) > MAX_ATTACHMENT_BYTES`, raise `oversize_frame`. Both checks run before `_deadline` and before any write.
2. `deadline = _deadline(timeout)`, then `previous = _socket_timeout(sock)`.
3. `_send_exact(sock, struct.pack("!I", len(data)) + data, deadline)`, then `_check_deadline(deadline)`.
4. In `finally`, `_restore_timeout(sock, previous)`.

The Forwarder never sends an attachment. This function exists for tests and the deferred Receiver client.

**`recv_attachment(sock, *, length: int, timeout=FRAME_TIMEOUT_SECONDS) -> bytes`**
1. If `type(length) is not int` or `not 1 <= length <= MAX_ATTACHMENT_BYTES`, raise `invalid_attachment_length`. This runs before `_deadline` or any socket call. The control path pre-validates `length`, so this code never reaches the wire.
2. `deadline = _deadline(timeout)`, then `previous = _socket_timeout(sock)`.
3. `header = _recv_exact(sock, 4, deadline, allow_clean_eof=False)`. EOF here means an incomplete command and gives `truncated_frame`.
4. Check the declared length:
   - `0` gives `invalid_length`;
   - more than `MAX_ATTACHMENT_BYTES` gives `oversize_frame`;
   - any value other than `length` gives `attachment_mismatch`.
   None of these three reads a body byte.
5. `body = _recv_exact(sock, length, deadline, allow_clean_eof=False)`, then `_check_deadline(deadline)`. Return the raw bytes; they are never decoded.
6. In `finally`, `_restore_timeout(sock, previous)`.

It reuses the private `_deadline`, `_socket_timeout`, `_recv_exact`, `_send_exact`, `_check_deadline` and `_restore_timeout`. There is one absolute deadline per attachment. The controller passes a clipped timeout (Module 3, item 4).

## Module 2: `grafana_jsm_sandbox/forwarder_control_scope.py` (new, pure)

This is the scoped control policy. It does no I/O, reads no clock, takes no lock and keeps no state after returning. It never retains a grant, sentinel, manifest or raw bytes.

**Module-1 error discipline.** An `except` block only records a fixed code. A fresh `ControlProtocolError(code)` is raised after the `try` statement, `from None`. Nothing is re-raised.

**No registry calls.** It never calls a registry method. Registry mutation and `hold()` stay inside `ForwarderControl`, and an AST test enforces this. Every refusal from `observe_closeout` is a hold decision that `ForwarderControl` carries out.

**Imports (AST-checked, exact):**
- `from __future__ import annotations`
- `import math`
- `.forwarder_control_protocol`: `ControlProtocolError`
- `.forwarder_dispatch`: `CLOSEOUT_STATES`, `LEASE_STATES`, `Closeout`, `DispatchError`, `DispatchGate`, `ScopeEntry`
- `.forwarder_leases`: `LeaseGrant`, `LeaseRegistry`
- `.forwarder_routes`: `MAX_MANIFEST_BYTES`, `RouteConfigError`, `ScopeManifest`, `parse_scope_manifest`, `require_manifest_binding`
- `.forwarder_services`: `SERVICE_PROFILES`

### Constants

- `SCOPED_SERVICES = frozenset({"jira"})`. This is a subset of `SERVICE_PROFILES`: exactly the services for which `ScopeManifest(service=s)` constructs. A parity test pins it. It grows only with a reviewed new manifest type.
- `ATTACHMENT_SECONDS = 2.0`. This is the attachment's budget, measured from when the header has been validated. A 16 KiB write on a local Unix socket, sent back-to-back with the header, needs far less. It is read at call time, so a test can monkeypatch it.
- `REGISTER_SCOPED_PARAMETERS = frozenset({"run_id", "attempt_id", "service", "scope_digest", "expires_at", "manifest_bytes"})`
- `CLOSEOUT_PARAMETERS = frozenset({"lease_id"})`
- `CLOSEOUT_FIELDS = ("generation", "lease_id", "lease_state", "closeout_state", "pending", "in_flight", "overdue", "uncertain", "drain_deadline", "observed_at")`
- `CLOSEOUT_COUNT_FIELDS = ("pending", "in_flight", "overdue", "uncertain")`, with `MAX_CLOSEOUT_COUNT = 2**31 - 1`.
- `REVOKED_LEASE_STATES = ("revoked", "pruned")`. These are the only lease states coherent after a successful gated Revoke (see `observe_closeout`).
- `SCOPED_GRANT_EXTRA_FIELDS = ("installed_at",)`
- `REVOKE_EXTRA_FIELDS = ("revoked_at", "closeout_state", "closeout")`
- `INSTALL_ERROR_CODES`, mapping a `DispatchError` code to a control code:

| `DispatchError` code | Control code |
| --- | --- |
| `gate_closed` | `scope_gate_closed` |
| `gate_held`, `clock_fault` | `scope_gate_held` |
| `lease_unverified`, `grant_expired`, `generation_mismatch` | `scope_lease_unverified` |
| `manifest_binding_mismatch` | `manifest_binding_mismatch` |
| `scope_capacity` | `scope_capacity` |
| `scope_conflict` | `scope_conflict` |
| any other code | `scope_install_failed` |

- `SCOPE_CONTROL_CODES` is every code the committed controller never emits and this unit can put on the wire, apart from the attachment codec's `attachment_mismatch`: `scope_required`, `scope_type_unavailable`, `invalid_manifest_length`, `manifest_too_large`, `manifest_invalid`, `manifest_binding_mismatch`, `scope_gate_closed`, `scope_gate_held`, `scope_lease_unverified`, `scope_capacity`, `scope_conflict`, `scope_install_failed`, `closeout_unknown`, `closeout_inconsistent`, `closeout_overdue`. The gated path also emits committed codes, such as `invalid_service` (reused by `manifest_length`), `invalid_identity`, `session_replaced` and `control_closed`. Those are not listed as new.
- `invalid_gate` is raised only by the constructor.

### Functions

**`require_gate(gate, registry) -> DispatchGate`.** Raises `invalid_gate` unless all three hold:
- `type(gate) is DispatchGate`;
- `type(registry) is LeaseRegistry`;
- `gate.generation == registry.generation`.

The gate's own constructor already enforces that the ledger and registry generations are equal. Pairing is proven only by equality of the 192-bit random generation. `DispatchGate` has no public registry accessor, and this unit leaves `forwarder_dispatch.py` unchanged. Exclusive ownership stays a trusted-caller precondition, as the committed docs L78-79 already require for the registry.

**`refuse_unscoped(service) -> None`.** Raises `scope_type_unavailable` only when `type(service) is str`, `service in SERVICE_PROFILES` and `service not in SCOPED_SERVICES`. For any other value it returns, leaving unknown and non-`str` services to the committed registry `invalid_service` path.

**`manifest_length(params) -> int`.** Checks run in this order, and no socket is touched:
1. **Service.** Not a `str`, or not in `SERVICE_PROFILES`, gives `invalid_service`. Otherwise `refuse_unscoped(service)`.
2. **`manifest_bytes`.** It must be an exact `int` (not `bool`) and at least 1, otherwise `invalid_manifest_length`. A value above `MAX_MANIFEST_BYTES` gives `manifest_too_large`.

**`bound_manifest(data: bytes, params) -> ScopeManifest`.**
1. `parse_scope_manifest(data)` accepts canonical bytes only. A `RouteConfigError` keeps its code: `manifest_invalid` or `manifest_too_large`.
2. If any of `service`, `run_id`, `attempt_id` or `scope_digest` is not a `str`, raise `manifest_binding_mismatch`.
3. `require_manifest_binding(manifest, service=, run_id=, attempt_id=, scope_digest=)`. A `RouteConfigError` gives `manifest_binding_mismatch`.

**`registry_parameters(params) -> dict`.** Returns exactly `run_id`, `attempt_id`, `service`, `scope_digest` and `expires_at`.

**`install(gate, grant: LeaseGrant, manifest: ScopeManifest) -> float`.**
1. Call `gate.install_scope(grant=grant, manifest=manifest)`.
2. A `DispatchError` maps through `INSTALL_ERROR_CODES`; a `TypeError` gives `scope_install_failed`. Any other exception propagates to the committed `internal_failure` path.
3. **Post-install identity check (graft).** The result must satisfy all of:
   - `type(entry) is ScopeEntry`;
   - `entry.lease_id == grant.lease_id`;
   - `entry.scope_digest == grant.scope_digest == manifest.digest`;
   - `entry.generation == grant.generation`.

   Otherwise raise `scope_install_failed`.
4. Return `entry.installed_at`.

**`observe_closeout(gate, lease_id: str, *, after_revoke: bool) -> dict`.** Every refusal it raises means "hold the registry". It returns a projection only when no hold is needed.
1. **Call.** Call `gate.closeout(lease_id)`. Any exception, or a result whose type is not exactly `Closeout`, gives `closeout_unknown`.
2. **Types and ranges** (`closeout_inconsistent` on any failure):
   - `lease_id` is a `str` equal to the argument;
   - `lease_state` is in `LEASE_STATES` and `closeout_state` is in `CLOSEOUT_STATES`;
   - each of `CLOSEOUT_COUNT_FIELDS` is an exact `int` (not `bool`) in `0..MAX_CLOSEOUT_COUNT`;
   - `observed_at` is an `int` or `float` (not `bool`), finite and at least 0;
   - `drain_deadline` is `None`, or a finite `int`/`float` (not `bool`) of at least 0.
3. **Coherence**, mirroring the gate's decision order (`closeout_inconsistent` on any failure):
   - `open` requires `lease_state` in (`registered`, `active`). `registered` or `active` requires `closeout_state` in (`open`, `unknown`).
   - `lease_state == "unknown"` requires `closeout_state == "unknown"`.
   - `overdue` requires `overdue >= 1`.
   - `draining` requires `in_flight >= 1` and `overdue == 0`.
   - `quiescent` requires `in_flight == 0` and `overdue == 0`.
   - `drain_deadline is None` exactly when `in_flight == 0`.
   - **After a revoke (graft):** `lease_state` must be in `REVOKED_LEASE_STATES`. `registry.revoke` has just retired the record, a revoked record never becomes `expired`, and the lease's scope entry outlives its record. So `registered`, `active`, `expired` or `unknown` here is inconsistent.
4. **Hold decisions:**
   - `overdue > 0` gives `closeout_overdue`. This covers `closeout_state == "overdue"` and also an `open` lease with an overdue flight.
   - `closeout_state == "unknown"` gives `closeout_unknown` if `after_revoke`, or if `lease_state != "unknown"` (a lease the Forwarder still knows, observed through a held gate, registry or ledger).
5. **Return** a dict with exactly `CLOSEOUT_FIELDS`:
   - `generation` is `gate.generation`, so a restarted Receiver can bind the observation to a generation;
   - all other values are copied verbatim.

   The dict can then be only one of four observations:
   - `open` with `overdue == 0` (closeout command only);
   - `draining`;
   - `quiescent`;
   - `unknown`/`unknown` for a lease ID the Forwarder has no record of (closeout command only).

   Every value is a scalar or `None` and passed step 2, so the dict is always a valid control frame value.

Wire states are the gate's own vocabulary. There is no `disposition` or `settled` vocabulary.

## Module 3: opt-in gate and unscoped refusal in `grafana_jsm_sandbox/forwarder_control.py`

This is an explicit, bounded delta of about 55 lines. These parts are unchanged:
- the handshake and proofs;
- `peer_uid`, `authenticate_receiver`, `MAX_CONNECTIONS` and the sequence rule;
- the owner fence and the `except`/`finally` paths;
- `_release_owner`, `_disconnect` and `shutdown`;
- `ControlOutcome` and `AuthenticatedControl`.

The delta:

1. **Imports.** Import `recv_attachment` from the protocol module, and add `from . import forwarder_control_scope as scope`.
2. **Gated command table.** Add a module table `_GATED_PARAMETERS`. `_PARAMETERS` stays unchanged and keeps its identity.
   ```python
   _GATED_PARAMETERS = {
       "register": _PARAMETERS["register"],        # refused with scope_required
       "register_scoped": set(scope.REGISTER_SCOPED_PARAMETERS),
       "activate": _PARAMETERS["activate"],
       "revoke": _PARAMETERS["revoke"],
       "heartbeat": set(),
       "closeout": set(scope.CLOSEOUT_PARAMETERS),
   }
   ```
3. **Constructor.** The signature becomes `__init__(self, registry, *, receiver_uid, control_secret, timeout=10.0, gate=None)`. After the existing checks:
   - `self._gate = None if gate is None else scope.require_gate(gate, registry)`
   - `self._commands = _PARAMETERS if self._gate is None else _GATED_PARAMETERS`

   The mode test is always `is None`; it never relies on truthiness.
4. **Command loop (committed L271-298).**
   - The unknown-operation test and `_keys(params, ...)` read `self._commands` instead of `_PARAMETERS`.
   - After the sequence check, and before `_keys`, `if self._gate is not None and operation == "register": raise ControlProtocolError("scope_required")`.
   - Then, after `_keys` and before taking the control lock:
     ```python
     registry_operation, registry_params, manifest = operation, params, None
     if operation == "register":                  # reached only in gateless mode
         scope.refuse_unscoped(params["service"])  # scope_type_unavailable, before any registry call
     elif operation == "register_scoped":
         length = scope.manifest_length(params)
         data = recv_attachment(sock, length=length,
                                timeout=min(self._timeout, scope.ATTACHMENT_SECONDS))
         manifest = scope.bound_manifest(data, params)
         registry_operation, registry_params = "register", scope.registry_parameters(params)
     elif operation == "closeout":
         _id(params["lease_id"])                  # invalid_identity
         registry_operation = None
     ```
5. **Under `self._lock`.** The fence (`control_closed`, `session_replaced`) and `commands += 1` are unchanged.
   - If `registry_operation is None`, the projection is `{}`.
   - Otherwise the committed `getattr(self._registry, registry_operation)(receiver_boot_id=boot, generation=generation, **registry_params)` runs.
   - The committed selector on L293 changes explicitly to `fields = _GRANT_FIELDS if registry_operation == "register" else _RECEIPT_FIELDS`. Without this change, `register_scoped` would be projected with receipt fields.
6. **After releasing `self._lock` (gated follow-ups).** No lock is held on entry.
   ```python
   if manifest is not None:
       installed_at = scope.install(self._gate, result, manifest)
       with self._lock:                          # post-install owner fence; no gate call inside
           if self._closed:
               raise ControlProtocolError("control_closed")
           if self._owner is not owner:
               raise ControlProtocolError("session_replaced")
       projection["installed_at"] = installed_at
   elif self._gate is not None and operation in ("revoke", "closeout"):
       try:
           observed = scope.observe_closeout(self._gate, params["lease_id"],
                                             after_revoke=operation == "revoke")
       except Exception:
           self._registry.hold()                 # every refusal is an uncertain closeout
           raise
       if operation == "revoke":
           projection.update(revoked_at=result.observed_at,
                             closeout_state=observed["closeout_state"], closeout=observed)
       else:
           projection = observed
   ```
   The hold-then-raise form is the one `forwarder_control.py` already uses at L257-261 and L337-343. A `ControlProtocolError` continues to the committed `except`, and anything else becomes the committed `internal_failure`; the registry is held first either way. Every raise stays inside the committed `try`, so `_release_owner` runs before any error frame.
7. **Docstrings.**
   - `serve_connection`: `commands` counts schema-valid commands admitted past the owner fence, including a rejected registry operation or scope install. A gated `closeout` also counts, although it makes no registry call. A Register refused with `scope_required` or `scope_type_unavailable` does not count. Otherwise the gateless meaning is the committed one.
   - The class and module docstrings name the optional gate, the unscoped-service refusal, and that only the Register or `register_scoped` reply carries a sentinel.

**Legacy identity.** With `gate=None`, the command table object, schemas, replies, codes and `ControlOutcome` semantics equal the committed ones, with one exception. `register` for a service in `SERVICE_PROFILES` but outside `SCOPED_SERVICES` (`confluence`, `grafana`, `kubernetes`, `anthropic`) now fails with `scope_type_unavailable` before the owner fence and before any registry call, so `commands` is not incremented. Jira registration, and `invalid_service` from the registry for unknown or non-`str` services, are unchanged. `register_scoped` and `closeout` give `unknown_operation`.

## Existing-module changes and test impact

| File | Change | Test impact |
| --- | --- | --- |
| `forwarder_control_protocol.py` | Additive: one constant, two functions, one docstring sentence | `test_forwarder_control_protocol.py` unchanged and green |
| `forwarder_control.py` | Opt-in `gate=`, gated table, unscoped-service refusal in both modes, the L293 selector, the post-install fence, docstrings | Every existing registration through control is Jira, so every existing test keeps committed behavior: control, listener_control, supervisor, supervisor_integration, dispatch_races |
| `docs/forwarder-control.md` | New section plus the edits listed under "Documentation" | none |

**No change** to:
- `forwarder_dispatch.py`, whose exact AST import allowlist stays green;
- `forwarder_routes.py`, `forwarder_leases.py`, `forwarder_listener.py`, `forwarder_supervisor.py`;
- any existing test file.

`ControlService` already accepts a fresh gated `ForwarderControl`.

**Import coupling.** `forwarder_control`, and through it `forwarder_supervisor`, now imports `forwarder_dispatch` and its dependency stack. There is no cycle: nothing in that stack imports control or the supervisor.

## Protocol

**Handshake.** Unchanged: peer UID, then `challenge`, `hello` and the `hello` reply with role-separated proofs. Every new command and the attachment exist only inside the post-handshake command loop.

**Command table.**
- `gate=None`: exactly the committed `register`, `activate`, `revoke` and `heartbeat`. `register` refuses unscoped services.
- `gate=DispatchGate`: `register` (always refused), `register_scoped`, `activate`, `revoke`, `heartbeat` and `closeout`.

### `register` (gateless)

After op/seq and schema validation, a `str` service in `SERVICE_PROFILES` but outside `SCOPED_SERVICES` gives `scope_type_unavailable` before the owner fence. The committed path releases the owner, which revokes the session's leases, and writes the error frame. Jira is unchanged, and so is every other code.

### `register` (gated)

Always refused with `scope_required`, right after op/seq validation and before the parameter schema. `commands` is not incremented. The committed path then releases the owner, revoking that session's leases, and writes `{"op":"register","seq":n,"ok":false,"error":"scope_required"}`.

### `register_scoped`

**Header frame** (JSON, at most 8 KiB):

```
{"op":"register_scoped","seq":n,"params":{"run_id":str,"attempt_id":str,"service":"jira",
 "scope_digest":hex64,"expires_at":number,"manifest_bytes":int}}
```

**Attachment.** It follows immediately on the same stream: `u32be(manifest_bytes) || ScopeManifest.canonical_bytes()`.
- Its length is 1..16,384 bytes.
- It consumes no sequence number and travels only from Receiver to Forwarder.
- It carries IDs and labels only, with no body or credential (spec L238-240).
- It must arrive within `min(timeout, ATTACHMENT_SECONDS)`, at most 2 s after the header is validated.

**Processing order.** The first failure raises its fixed code and ends the session through the committed path.

1. **Operation and sequence** (committed): `unknown_operation`, `invalid_sequence`.
2. **Schema.** The exact 6-key parameter set, else `invalid_schema`.
3. **Service** (`scope.manifest_length`): `invalid_service` or `scope_type_unavailable`. No attachment byte has been read yet.
4. **`manifest_bytes`:** `invalid_manifest_length` or `manifest_too_large`, still before any read.
5. **`recv_attachment`**, with its own deadline of at most 2 s.
   - Rejected before the body is read: `invalid_length`, `oversize_frame`, `attachment_mismatch`.
   - Also possible: `truncated_frame`, `timeout`, `read_failure`, `socket_failure`.
6. **`scope.bound_manifest`.**
   - Canonical parse: `manifest_invalid` or `manifest_too_large`.
   - Binding against `service`, `run_id`, `attempt_id` and `scope_digest`: `manifest_binding_mismatch`.
   - The raw bytes are dropped here.
   - **Steps 1-6 make no registry or gate mutation.**
7. **Registration, under `C`.**
   - Fence: `control_closed`, `session_replaced`.
   - `commands += 1`.
   - `registry.register` with the session's boot and generation. Committed `LeaseError` codes apply: `invalid_expiry`, `heartbeat_late`, `capacity_live`, `capacity_total`, `capacity_metadata`, `binding_conflict`, `replay_not_live`, `registry_held`, and so on.
8. **Install, after `C` is released.** `scope.install(gate, grant, manifest)`.
   - The gate re-runs the binding and generation checks, `registry.check` (the lease must be registered or active) and the exact record comparison under `G`, then `R`.
   - Codes: `scope_gate_closed`, `scope_gate_held`, `scope_lease_unverified`, `scope_capacity`, `scope_conflict`, `manifest_binding_mismatch`, `scope_install_failed`.
9. **Post-install owner fence, under `C` alone.** `control_closed` or `session_replaced`. This catches a replacement or shutdown that landed inside `install_scope` after its check (see I6).
10. **Reply**, sent only now:

```
{"op":"register_scoped","seq":n,"ok":true,"result":{"generation","lease_id","run_id","attempt_id",
 "receiver_boot_id","service","scope_digest","expires_at","sentinel","installed_at"}}
```

**Failure after registration.** A failure at step 7, 8 or 9 reaches the committed `except`. When this session still owns control, `_release_owner`'s disconnect revokes every session lease, including the new one, before the error frame is written. When it was replaced, the replacement has already revoked them. An entry that install left behind for a revoked lease is inert, because every `check` and `precheck` denies it.

**Timing and the heartbeat window.** The header read waits up to the controller timeout (at most 10 s), and the attachment up to 2 s more, so `registry.register` runs at most about 12 s after the previous reply. **Receiver obligation:** keep the spec L145 five-second heartbeat cadence, or send a heartbeat as the command just before each `register_scoped`, and write the attachment immediately after the header. A Receiver that lets 15 s pass without a heartbeat gets `heartbeat_late` from `register`, and the registry has already revoked every live lease of the session (case 23).

**Replay.** An exact replay in the same session, with the same parameters and bytes, returns the same grant through the registry replay path and the same `installed_at` through `install_scope`'s same-index, same-digest path. A changed tuple conflicts in the registry.

### `activate`, `heartbeat`

Unchanged. In gated mode every live lease created through this controller already has its scope installed, so a successful activate implies installation.

### `revoke` (gated)

**Request.** Unchanged: `{"lease_id","reason"}`.

**Processing:**
1. Under `C`: the committed fence, `commands += 1` and `registry.revoke`. Revoking an already expired or revoked lease stays a session-ending `LeaseError`, as committed. There is no observation and no hold in that case.
2. After `C` is released: `observe_closeout(after_revoke=True)`. On any refusal, the registry is held first. The command then fails with `closeout_unknown`, `closeout_inconsistent` or `closeout_overdue`. The committed path releases the owner; the disconnect fails on the held registry, so `ControlOutcome.closeout` is `unknown`. It then writes `{"op":"revoke","seq":n,"ok":false,"error":code}`.
3. Otherwise, the reply is sent with `ok:true`.

**Wire rule.** An `ok:true` Revoke reply means two things: the lease is retired, and `closeout_state` is `draining` (REVOKING) or `quiescent` (REVOKED), with `overdue == 0`. It never carries `open`, `overdue` or `unknown`. Every uncertain closeout has exactly one representation: `ok:false` with a `closeout_*` code, written after the hold. That matches spec L162-163, which says a closeout failure "is UNKNOWN, not a successful revoke, and holds new dispatch". The registry retirement did happen. The Receiver must still record such a Revoke as UNKNOWN, never as successful. Revision 1's claim that L162-163 supports `ok:true` for `unknown` is withdrawn.

**Reply result.** The 8 committed receipt fields `{operation, generation, lease_id, service, state, reason, authorized, observed_at}`, plus:
- `revoked_at`, which equals `observed_at`, the registry retirement time;
- `closeout_state`, which is `draining` or `quiescent`;
- `closeout`, a nested object with the 10 `CLOSEOUT_FIELDS`.

That is depth 3 of 4, and under 2 KiB encoded. It matches spec L122's `Revoke -> {revoked_at, closeout_state}` literally and keeps the committed receipt.

### `closeout` (gated, spends no authority)

**Request:** `{"op":"closeout","seq":n,"params":{"lease_id":str}}`. A malformed ID gives `invalid_identity`.

**Processing.** The command passes the owner fence and counts as a command. It makes no registry call through control and needs no heartbeat freshness. It then calls `observe_closeout(after_revoke=False)`. A refusal holds the registry and fails the command, exactly as for Revoke.

**Side effects.** `gate.closeout` reads `registry.snapshot()` and ticks the gate clock. That can perform time-based retirement (expiry, heartbeat-late revocation, record and scope pruning, `_control_stale`). It can also mark flights overdue and run their abort callbacks on this handler thread before the reply. All of these only reduce authority. 13a requires abort callables to be non-blocking, so a slow abort only delays the reply.

**Reply result.** Exactly the 10 `CLOSEOUT_FIELDS`.

**Which leases.** Any lease ID of this generation is allowed, including leases of a prior Receiver boot, which supports reconciliation after EOF or replacement.

### Holds (I8)

The same rule applies to Revoke and `closeout`:

| Observation | Forwarder action | Wire |
| --- | --- | --- |
| `gate.closeout` raises, or returns something other than an exact `Closeout` | hold | `closeout_unknown` |
| a wrong type, non-finite or out-of-range value, incoherent states, or after a revoke a `lease_state` other than `revoked`/`pruned` | hold | `closeout_inconsistent` |
| `overdue > 0`: the `overdue` state, or an `open` lease with an overdue flight | hold | `closeout_overdue` |
| `unknown` after a revoke, or `unknown` for a lease the Forwarder still knows (`lease_state != "unknown"`) | hold | `closeout_unknown` |
| `closeout` only: `unknown` with `lease_state == "unknown"`, meaning no Forwarder record | none | `ok:true`, `unknown`/`unknown` |
| `open` (closeout only), `draining` or `quiescent`, with `overdue == 0` | none | `ok:true` |

**Why hold on `overdue`.** 13a left "hold dispatch on `overdue`" to the Receiver (dispatch plan L290). This unit enforces it on the Forwarder whenever control observes it. A deadline-ignoring connector may still be writing upstream. Spec L162-163 requires an UNKNOWN closeout to hold new dispatch, and the committed hold is the only Forwarder-side mechanism that does so. The hold only removes authority. It is terminal for the generation: afterwards handshakes fail with `registry_held`.

**Cross-owner effect.** These holds run with `C` released and do not re-check ownership. A session replaced after its fence passed can therefore still hold the generation the new owner uses. This is the only permitted cross-owner effect. It never grants authority, and spec L162-163 requires it whichever session observed the uncertainty, because the uncertainty is about Forwarder state, not about the session (case 22).

### Presentation of closeout states

| Observation | Meaning for the Receiver |
| --- | --- |
| `open` | The lease is registered or active, and no flight of it is overdue. |
| `draining` | Some admitted or writing flight of the lease is unfinished, and none is overdue. The remaining drain budget is `drain_deadline - observed_at` from the same reply. Never compare `drain_deadline` with the Receiver's own clock. The difference is valid only while the gate and ledger share one clock domain, which 13a requires but checks only for the registry and gate clocks. Poll `closeout` until `quiescent`. If a flight outlives its deadline, the next observation holds the registry and fails with `closeout_overdue`. |
| `quiescent` | No admitted or writing flight of the lease is unfinished, and none is overdue. `pending` may be nonzero, but reserved entries can no longer be admitted after the retirement and can only become `NOT_DISPATCHED`. If `uncertain > 0`, those dispatches were `DISPATCHED_UNKNOWN` or `PARTIAL` and must be recorded as such, never as settled. |
| `unknown` (`ok:true`, closeout only) | The Forwarder has no record of this ID: it was never registered in this generation, or its retention ended. Treat as UNKNOWN and reconcile from the Receiver's durable journal (ticket 37). |
| `lease_state = "pruned"` | The registry record aged out (`created_at + 310` s) while the scope entry is kept until `installed_at + 310` s. Counts come from the retained ledger only. |
| error `closeout_overdue` | A flight passed its deadline without returning. The registry is held. Record the lease's in-flight work as UNKNOWN. |
| error `closeout_unknown`, `closeout_inconsistent` | The registry is held. Record the lease, and a Revoke that failed this way, as UNKNOWN. |

**After any hold.** The generation refuses new sessions with `registry_held`. The Receiver records every unreconciled lease of that generation as UNKNOWN and waits for a fresh Forwarder generation.

**After EOF or replacement.** On the Forwarder, `ControlOutcome.closeout == "revoked"` means only that the registry retired the session's leases. It does not mean their flights drained. Before treating any lease as quiescent, the Receiver must open a new session and poll `closeout` for it. If that session is refused with `registry_held`, every lease is UNKNOWN.

After a scope entry's retention ends, the answer is `unknown` (spec L158-162). Mapping to spec lease states is documentation guidance, not enforcement:
- `revoked` with `draining` is REVOKING;
- `revoked` with `quiescent` is REVOKED;
- `expired` with `quiescent` is EXPIRED.

### Misframing fails closed

- **Omitted attachment.** If the Receiver sends the next JSON frame instead, its length prefix is read as the attachment header and fails with `attachment_mismatch`. If the lengths coincide, the body fails with `manifest_invalid`.
- **Unexpected attachment.** Read as a JSON frame, it fails with `oversize_frame` (above 8 KiB) or `arrays_not_allowed` (a canonical manifest has a top-level `routes` array).

Every one of these ends the session and revokes its leases.

## Frame limits

| Frame | Limit | When legal | Deadline |
| --- | --- | --- | --- |
| JSON (all, including pre-authentication) | 8,192 bytes, depth 4, 64-byte ASCII keys, 512-byte strings, no arrays (committed) | always | one absolute deadline, at most the timeout (at most 10 s) |
| Attachment | 1..16,384 bytes, declared twice with an exact match | only immediately after an authenticated, sequence-valid, schema-valid `register_scoped` header with a scoped service and a valid `manifest_bytes` | its own absolute deadline, `min(timeout, ATTACHMENT_SECONDS)`, at most 2 s |

- **Worst case per command read:** 4 + 8,192 + 4 + 16,384 bytes within about 12 s.
- **Memory:** at most 4 connections times 16 KiB of attachment buffer.
- **Pre-authentication exposure:** unchanged.

## Codes

| Code | Raised by | Where |
| --- | --- | --- |
| `invalid_gate` | `require_gate` | constructor only; never on the wire |
| `scope_required` | `ForwarderControl` | gated `register`, before the schema check |
| `scope_type_unavailable` | `refuse_unscoped` (directly, or through `manifest_length`) | both modes, before any registry call or attachment read |
| `invalid_service` (committed code) | `manifest_length` | before any attachment read |
| `invalid_manifest_length`, `manifest_too_large` | `manifest_length`, `bound_manifest` | before the read, or at parse |
| `invalid_length`, `oversize_frame`, `attachment_mismatch` | `recv_attachment` | header rejected; body unread |
| `truncated_frame`, `timeout`, `read_failure`, `socket_failure` | `recv_attachment` | committed codec meanings |
| `invalid_attachment_length`, `invalid_payload` | codec argument checks | caller bugs; unreachable from the control path |
| `manifest_invalid`, `manifest_binding_mismatch` | `bound_manifest` (and the gate re-check) | before mutation |
| `scope_gate_closed`, `scope_gate_held`, `scope_lease_unverified`, `scope_capacity`, `scope_conflict`, `scope_install_failed` | `install` | after registration; the session's leases are revoked |
| `control_closed`, `session_replaced` (committed codes) | post-install owner fence | after install; no sentinel is written |
| `closeout_unknown`, `closeout_inconsistent`, `closeout_overdue` | `observe_closeout` | revoke or closeout; the registry is held first |

Error frames keep the committed shape `{op, seq, ok:false, error}` and are written only after `_release_owner`. No error frame is written for `eof` or `internal_failure`.

## Lock order

- **`C` (`control._lock`) to `R`.** Unchanged, and used for registry calls only. The post-install fence takes `C` alone and calls nothing.
- **`C` is never held across a `DispatchGate` call.** `install_scope` and `closeout` run on the handler thread with no control lock held. Inside the gate, `G` then `R` and `G` then `L` are as committed.
- **Abort callbacks** drained in the gate's `finally` run outside `G`, and therefore with no lock held.
- **`registry.hold()`** calls added by this unit run with `C` released and take only `R`. The committed hold calls under `C` (`shutdown`, `_disconnect`, handshake failure) are unchanged.
- **No new lock edge.** The documented total order (`C` < `G` < `R`, with `G` < `L`; docs L494-497, dispatch plan L535-541) stays valid, and this unit uses a strict subset of it. The gate never calls control.
- **Fencing without holding `C` across the gate call.** A replacement's `_disconnect`, or a shutdown's `hold()`, retires or holds under `R`. It is linearized with `install_scope`'s `registry.check` and `registry.snapshot()`, each taken separately. A retirement that lands after those reads is caught by the post-install fence (I6).
- **Structural check.** An AST test asserts that, in `forwarder_control.py`, no `scope.*` call, no `self._gate` attribute call and no `recv_attachment` call appears lexically inside a `with self._lock:` body.

## Invariants

Each invariant has a test.

- **I1. Authentication is unchanged** (spec L113-117). The peer UID check and the role-separated HMAC handshake precede every command. The attachment exists only after the handshake.
- **I2. Bounded framing** (spec L238-240; docs L61-66).
  - The committed 8 KiB JSON codec is unchanged.
  - There is one attachment kind. Its length is validated before the read, and its header is checked against that length before any body byte is read.
  - One absolute deadline per frame. The attachment's deadline is at most 2 s.
  - An absent attachment ends in `timeout` or `truncated_frame`.
- **I3. No mutation before validity** (spec L138-142; routes plan Deferred 2). The scope-type check, the length check, the canonical parse and `require_manifest_binding` all finish before `registry.register`. A refused `register_scoped`, or a refused gateless unscoped `register`, leaves `retained_records`, `history` and the gate's `scope_entries` unchanged, apart from pruning.
- **I4. Scope-type refusal** (routes plan Deferred 2; dispatch plan Deferred 2, bullet 3).
  - In both modes, `register` for any service outside `SCOPED_SERVICES` that is in `SERVICE_PROFILES` gives `scope_type_unavailable` before any registry call.
  - With a gate wired, `register` always gives `scope_required`, and `register_scoped` for an unscoped service gives `scope_type_unavailable` before any attachment read.
  - `SCOPED_SERVICES` equals the set of services that have a `ScopeManifest` type, which is only `jira`.
- **I5. No sentinel for an unscoped lease.** In gated mode, a sentinel reaches the wire only in a `register_scoped` reply. That reply is sent only after `scope.install` returned an identity-checked entry and the post-install owner fence passed. In gateless mode only Jira leases get sentinels, and none has an installed scope.
- **I6. Replacement fencing** (spec L143-149; docs L68-73).
  - Every registry mutation stays under `C`, behind the owner/closed fence.
  - `install_scope` receives only the grant returned by this session's own fenced register.
  - A replacement or shutdown between register and install has one of two effects. If the retirement precedes `install_scope`'s `registry.check`, install fails with `scope_lease_unverified`. If it lands after the check or the snapshot, install inserts an entry for an already-retired lease, which every check denies.
  - Either way, the post-install fence raises `session_replaced` or `control_closed`, so no session known to be replaced or closed writes a sentinel. A replacement that lands after the fence can still let the reply, carrying an inert sentinel, reach the replaced peer before the new owner closes that socket. The committed Register reply has the same window.
  - The finalizer of the old handler reports `not_owner` after a replacement, and `unknown` after a shutdown hold.
  - No old session can mutate the registry for the new owner. The one permitted cross-owner effect is the conservative hold of I8.
- **I7. Closeout before error** (docs L70-72). Every new failure is a `ControlProtocolError` or `LeaseError` raised inside the committed `try`, so `_release_owner` precedes every error frame. Unexpected exceptions still become `internal_failure`: no frame, and release in `finally`. A closeout observation holds before either path.
- **I8. Hold on uncertain closeout** (spec L162-163). The registry is held in these cases:
  - a failed disconnect (committed);
  - every refusal in the "Holds" table, on Revoke or `closeout`. That includes `overdue > 0`, and `unknown` for a lease the Forwarder still knows. The hold is taken before the error frame, and the command fails.

  An `ok:true` reply never carries `overdue` or a known-lease `unknown`. The only unheld `unknown` is a `closeout` answer for an ID the Forwarder has no record of.
- **I9. Revocation visibility** (spec L155-157; 13a I3, I4 and I8). A Revoke observation starts after `registry.revoke` returned. At that observation:
  - every admitted or writing flight of the lease that is unfinished counts in `in_flight` (`draining`) or `overdue`, so it is never `quiescent`;
  - uncertain finished outcomes count in `uncertain`;
  - reserved entries (`pending`) can no longer be admitted and can only become `NOT_DISPATCHED`.

  An admitted flight that is denied at the fence, or completes, between the retirement and the observation is finalized (`FAILED`, or complete) and correctly allows `quiescent`. After a successful revoke, `open` is impossible and is treated as inconsistent.
- **I10. Sentinel custody** (spec L126-128, L141-142; docs L55-59).
  - A sentinel appears only in `register` and `register_scoped` replies to the authenticated peer.
  - The grant lives only in the handler's local scope; the gate keeps only its HMAC index.
  - Error frames, `ControlOutcome`, exceptions (args and chains), registry and gate snapshots, the closeout projection and the Revoke reply carry no sentinel and no manifest bytes.
- **I11. Lock order.** As stated above. Tests use an instrumented lock that records its owning thread, and an AST test covers the structure.
- **I12. No new authority.** The unit adds no permit and no dispatch path. `closeout` spends no authority: its side effects (time-based retirement, overdue marking, abort callbacks, holds) only reduce it. `install_scope` re-verifies the lease itself. Dispatch still requires the L1 and L2 registry checks.
- **I13. Legacy identity for Jira.** With `gate=None`, the command table, schemas, replies, codes and `commands` semantics equal the committed ones for every command except `register` of the four unscoped profiled services. Every existing test passes unmodified.
- **I14. Retention** (spec L158-163, L423-429). Closeout reflects in-process state only. After `installed_at + 310` s it answers `unknown`. Durable evidence belongs to ticket 37.

## Documentation (`docs/forwarder-control.md`, root)

- **L61, "Commands are limited to...".** Add two sentences:
  - every controller refuses registration for services without a scope type (only Jira has one);
  - a gated controller replaces registration with scoped registration (one attachment of at most 16 KiB, within 2 s) and adds a closeout command.
- **L68-73 (fencing).** Add: a post-install fence stops a replaced or closed session from writing a scoped grant; an uncertain closeout observed by any session holds the registry.
- **L494-497 (lock order).** Add: the control lock is never held across a `DispatchGate` call, and `registry.hold()` is also called with the control lock released, taking only `R`.
- **L514-515 and L533-535.** Replace "no production caller until manifest delivery over control exists" and "not yet a control reply" with pointers to the new section.
- **L561-562 and L566-567 (non-claims and next units).** Remove manifest delivery and control closeout from the non-qualified list, and update the next-unit sentence.
- **New section "Scope delivery and control closeout".** It covers:
  - the command shapes;
  - attachment framing and limits;
  - refusal order;
  - the Revoke wire rule: `ok:true` only for `draining`/`quiescent`, and every uncertain closeout is `ok:false` after a hold;
  - the Revoke mapping to spec L122, and the presentation table;
  - the holds table, including `overdue`, and the cross-owner effect;
  - lock order;
  - Receiver obligations:
    - keep the 5 s heartbeat cadence, and send the attachment immediately after the header;
    - compute the drain budget as `drain_deadline - observed_at` from the same reply;
    - poll `closeout` on a new session after EOF or replacement before treating any lease as quiescent;
    - read closeout within 310 s;
    - treat every `closeout_*` error and `unknown` as UNKNOWN;
    - use `closeout`, not Revoke, for leases it believes are already retired;
    - keep scope-store use within the capacity bound under "Residual risks";
  - non-claims: no permits, no Ready, no Receiver client, no deployment. Gateless mode still registers Jira without a scope, so it can never create a dispatchable lease over control.
- **Focused pytest command.** Add the three new test files.

## Ownership and validation

**Implementer A** owns Module 1 and `tests/test_forwarder_control_attachment.py`, using real socketpairs, plus fake sockets and a monkeypatched `time.monotonic` as in the committed codec tests.
- A1: a round trip at 1, 8,193 and 16,384 bytes returns exact opaque bytes (including non-UTF-8) and restores the prior timeout, both after success and after failure.
- A2: 1-byte drip reassembly. An attachment coalesced with the next JSON frame is consumed exactly, and `recv_frame` then reads that frame.
- A3: header 0 gives `invalid_length` and 16,385 gives `oversize_frame`; header not equal to `length` gives `attachment_mismatch`. In all three, the peer's body marker stays unread (verified on the peer socket).
- A4: `length` values 0, -1, `True`, 1.0 and 16,385 give `invalid_attachment_length` without any socket call.
- A5: EOF before or inside the header, or mid-body, gives `truncated_frame`.
- A6: a drip past one absolute deadline gives `timeout`. The deadline is also checked after the final read and after the final write.
- A7: `send_attachment` rejects `bytearray`, `str`, `memoryview` and `b""` with `invalid_payload`, and 16,385 bytes with `oversize_frame`. Nothing is written.
- A8: error args never echo body markers.
- A9: `MAX_ATTACHMENT_BYTES == forwarder_routes.MAX_MANIFEST_BYTES > MAX_FRAME_BYTES == 8192`.

**Implementer B** owns Module 2 and `tests/test_forwarder_control_scope.py`. It reuses `tests.test_forwarder_routes.golden_manifest` and `POLICY_DIGEST`, and `tests.test_forwarder_dispatch.new_system`/`register`/`FakeClock`/`make_routed`/`reserve_and_admit`.
- B1: `SCOPED_SERVICES == {"jira"}`, a subset of `SERVICE_PROFILES`. For every other service `s`, `ScopeManifest(service=s, ...)` raises `manifest_invalid`. `ATTACHMENT_SECONDS == 2.0`.
- B2: refusal and length tables.
  - `refuse_unscoped`: `scope_type_unavailable` for each unscoped profiled service; it returns for `"jira"`, `"ghost"`, 7, `None` and `{}`.
  - `manifest_length`: `scope_type_unavailable` for each unscoped service; `invalid_service` for `"ghost"`, 7, `None` and `{}`; `invalid_manifest_length` for `True`, 0, -1, 1.5 and `"10"`; `manifest_too_large` for 16,385. 16,384 is accepted, and service is checked before length.
- B3: `bound_manifest`.
  - Golden bytes give `digest == scope_digest`.
  - Reordered keys, extra whitespace, a trailing newline or non-ASCII give `manifest_invalid`.
  - A mismatched `run_id`, `attempt_id`, `service` or `scope_digest`, or a non-`str` value, gives `manifest_binding_mismatch`.
- B4: `install` against a real gate in each state:
  - closed gives `scope_gate_closed`;
  - a faulting gate clock gives `scope_gate_held`, on the first call and on later calls;
  - a revoked lease, or a grant from another generation, gives `scope_lease_unverified`;
  - a monkeypatched `fd.MAX_SCOPE_ENTRIES = 0` gives `scope_capacity`;
  - a reinstall returns the same `installed_at`;
  - an instance-attribute `install_scope` that returns another lease's entry gives `scope_install_failed` (post-install identity check).
- B5: `observe_closeout`, against real gate states and stubbed `Closeout` values.
  - A raising or wrong-type `gate.closeout` gives `closeout_unknown`.
  - Types and ranges give `closeout_inconsistent`: a wrong `lease_id` echo; an out-of-vocabulary state; `True`, -1, 1.5 or `2**31` as a count; `nan`, `inf` or -1 as `observed_at`; `nan` or `"x"` as `drain_deadline`.
  - Coherence gives `closeout_inconsistent`: `open` with `revoked`; `active` with `quiescent`; `unknown` lease state with `quiescent`; `draining` with `in_flight == 0`; `draining` or `quiescent` with `overdue == 1`; `quiescent` with `in_flight == 1`; a `drain_deadline` present with `in_flight == 0`, or missing with `in_flight == 1`.
  - With `after_revoke=True`: `registered`, `active`, `expired` or `unknown` lease states give `closeout_inconsistent`. `revoked` and `pruned` are accepted, and a return is always `draining` or `quiescent`.
  - Holds: `overdue` state, and `open` with `overdue == 1`, give `closeout_overdue`. `unknown` after a revoke, or `unknown` with a known lease state, gives `closeout_unknown`. `unknown`/`unknown` with `after_revoke=False` is returned.
  - The projection has exactly `CLOSEOUT_FIELDS` with `generation == gate.generation`, and `send_frame` accepts it over a socketpair.
- B6: `require_gate` gives `invalid_gate` for a non-gate object, for a gate over another registry, and for a registry of the wrong type.
- B7: every raised error has `args == (code,)`, and `__cause__` and `__context__` are `None`.
- B8 (AST):
  - no `raise` inside an `except` handler;
  - the exact import allowlist;
  - no `socket`, `os`, `ssl`, `time`, `threading`, `subprocess`, `open` or `print`;
  - no attribute call named `register`, `activate`, `revoke`, `heartbeat`, `handshake`, `disconnect`, `hold` or `check`.

**Implementer C** owns Module 3 and `tests/test_forwarder_control_gate.py`. C starts after A and B are green.

Fixture:
- one `FakeClock` shared by the registry and the ledger;
- the gate runs on `GateClock(clock)`: a wrapper that returns the same values, so the admit clock-domain guard sees one domain, and raises when its `fault` flag is set;
- `ForwarderControl(registry, receiver_uid=os.geteuid(), control_secret=SECRET, timeout=2.0, gate=gate)`;
- `OwnedLock`: a test lock installed as `control._lock` after construction. It supports `with`, `acquire`, `release` and `locked`, and records the owning thread. `held_by_current_thread()` is the lock-order predicate;
- the committed `authenticate_receiver`, plus raw frames through `send_frame`/`recv_frame`/`send_attachment`;
- helper `scoped(client, seq, manifest, **overrides)`.

Cases:
1. **Happy path.**
   - The reply keys equal `set(_GRANT_FIELDS) | {"installed_at"}`.
   - `gate.resolve("jira", sentinel).manifest.digest` equals the scope digest, and `installed_at` matches the reply.
   - `precheck` is `False` until activate over control, then `True`.
   - `ControlOutcome` and both snapshots contain no sentinel.
2. **Large manifests.** A manifest whose canonical bytes exceed 8,192 (256 labels, `jira.search` only) installs. So does one of more than 15,000 and at most 16,384 bytes. The header frame stays at 8 KiB or less.
3. **Exact replay** on seq 2 returns the same lease, sentinel and `installed_at`, with one scope entry.
4. **Gated `register`.**
   - (a) As the first command: `scope_required`, `retained_records` 0, `commands` 0, outcome closeout `revoked` (the owner is released with no leases).
   - (b) After a successful `register_scoped`: `scope_required`, that lease is revoked (reason `receiver_disconnected`), `commands` 1.
5. **Unscoped services, gated** (parametrized over `confluence`, `grafana`, `kubernetes`, `anthropic`) give `scope_type_unavailable` with only the header sent, well before the timeout; `retained_records` 0. Unknown and non-`str` services give `invalid_service`.
6. **Bad `manifest_bytes`.** 16,385 gives `manifest_too_large`; 0, `True`, 1.5 and `"12"` give `invalid_manifest_length`. No attachment is sent.
7. **Framing errors.** None of them mutates anything.
   - A prefix mismatch gives `attachment_mismatch`.
   - A missing attachment gives `timeout` (controller timeout 0.3 s).
   - Closing mid-body gives `truncated_frame`.
   - **Budget clip:** controller timeout 2.0, a monkeypatched `scope.ATTACHMENT_SECONDS = 0.2` and a withheld attachment give `timeout`, observed in under 1.0 s.
8. **Manifest errors.**
   - Non-canonical bytes give `manifest_invalid`, and the error frame has no marker.
   - Another attempt's manifest, or a digest mismatch, gives `manifest_binding_mismatch`.
   - `retained_records` and `scope_entries` are unchanged.
9. **Install failure after register.** Parametrized over `gate.shutdown()` (`scope_gate_closed`) and `MAX_SCOPE_ENTRIES = 0` (`scope_capacity`).
   - The new lease and an earlier lease of the session are revoked.
   - A wrapped `registry.disconnect` records that release happened before the error frame arrived.
   - The frame has no sentinel.
   - `commands` counts the command.
10. **Revoke reply.**
    - Keys equal `set(_RECEIPT_FIELDS) | {"revoked_at", "closeout_state", "closeout"}`, and the closeout keys equal `CLOSEOUT_FIELDS`.
    - `revoked_at == observed_at`; `closeout_state == closeout.closeout_state == "quiescent"`; lease state `revoked`; zero counts; `generation` matches.
    - The encoded reply is under 2 KiB, and `precheck` becomes `False`.
11. **Draining.** An admitted flight (`make_routed` plus `reserve_and_admit` with the reply sentinel) makes the revoke reply `ok:true`/`draining`, with `in_flight` 1 and `drain_deadline` equal to the flight deadline. `begin_write` then gives `lease_denied`, and a `closeout` command reports `quiescent` with `uncertain` 0.
    - Variant with the fence passed before the revoke: `finish(DISPATCHED_UNKNOWN, write_failed)`, then `quiescent` with `uncertain` 1.
    - Heartbeats go over control during clock advances.
12. **Overdue holds.** Heartbeats go over control during clock advances.
    - (a) Revoke with an admitted flight gives `draining`. Advance past the flight deadline. The `closeout` command then gives `ok:false`/`closeout_overdue`. The registry is `held` when the frame is read, and the outcome closeout is `unknown`. A reconnect is refused with `registry_held`. After `gate.release(admission)`, a direct `gate.closeout` shows `overdue` 0 and `uncertain` 1.
    - (b) A revoke of a lease whose flight is already overdue gives `ok:false`/`closeout_overdue`, and the registry is held. The history still shows the revoke receipt.
    - (c) A live lease with an overdue flight (`open`, `overdue` 1): the `closeout` command gives `closeout_overdue`, and the registry is held.
    - (d) Expiry variant: advance past `expires_at` with heartbeats. `closeout` then gives `closeout_overdue`, where the direct gate view shows lease state `expired`.
13. **Closeout command basics.** A live lease with no flights reports `open`. An unknown well-formed ID reports `ok:true` `unknown`/`unknown` without a hold, and a following heartbeat succeeds. `"bad id!"` gives `invalid_identity`.
14. **Pruned.**
    - An instance-attribute wrapper on `gate.install_scope` advances the clock 10 s before delegating. Then revoke.
    - Advance past `created_at + 310` but before `installed_at + 310`: `closeout` gives lease state `pruned` and `quiescent`, with counts from the ledger.
    - Past `installed_at + 310`: `ok:true` `unknown`/`unknown`, with no hold.
15. **Gate-only clock fault.** Set `GateClock.fault` before a revoke.
    - The revoke fails with `ok:false`/`closeout_unknown`.
    - The registry is already `held` when the error frame is read, the outcome closeout is `unknown`, and a reconnect is refused with `registry_held`.
    - The registry history shows the revoke receipt: the retirement happened but is not reported as a successful revoke.
16. **Observation failures and incoherence.** Each of these holds the registry:
    - `gate.closeout` raising `RuntimeError`, on revoke and on a `closeout` command, gives `closeout_unknown`.
    - A `Closeout` with `lease_state` `active` after a revoke gives `closeout_inconsistent`.
    - A `Closeout` with `observed_at = nan`, or with a `bool` count, gives `closeout_inconsistent`, never the codec's `nonfinite_number` or a frame without a hold.
17. **Registry held by the test, one session.** First, `closeout` on an unknown ID answers `ok:true` `unknown`/`unknown`. Then `closeout` on a known lease gives `closeout_unknown`.
18. **Prior-boot leases.** After a boot-B replacement, closeout from B on a boot-A lease reports `revoked`/`quiescent`.
19. **Replacement race before the check.** A barrier in an instance-attribute `gate.install_scope`, before it delegates, lets session B replace A between register and install.
    - A's outcome is `scope_lease_unverified` with closeout `not_owner`.
    - `resolve(A's sentinel)` is `None`, and B registers and installs normally.
20. **Replacement race after the snapshot.** An instance-attribute `registry.snapshot` wrapper fires once, on A's handler thread during install. It returns the real snapshot and then blocks. B replaces A, and the barrier is released.
    - Install inserts an entry for A's revoked lease.
    - A's post-install fence raises `session_replaced`, and A's outcome closeout is `not_owner`.
    - A's client reads EOF or a `session_replaced` error frame, never a frame containing A's sentinel.
    - `precheck(entry, sentinel=A's)` is `False`, and any `resolve` hit is that inert entry. B registers and installs normally.
21. **Shutdown race.**
    - With `control.shutdown()` during a block before the check: `scope_lease_unverified`, a held registry and no scope entry.
    - With the block after the snapshot: `control_closed` from the post-install fence, a held registry and only an inert entry.
    - Both: outcome closeout `unknown`, and no sentinel on the wire.
22. **Cross-owner hold.** A revokes a lease. A wrapped `gate.closeout` blocks until B has replaced A, then raises.
    - The registry is held, and A's outcome closeout is `not_owner`.
    - B's next heartbeat gets `registry_held`, and B's outcome closeout is `unknown`.
23. **Heartbeat gap across the attachment.** After an earlier successful `register_scoped`, send a header, advance the shared `FakeClock` by 15 s, then send the attachment.
    - The command gets `heartbeat_late`.
    - The earlier lease is revoked with reason `heartbeat_late`, and no new record exists.
24. **Lock order.**
    - Wrapped `install_scope` and `closeout` assert `not control._lock.held_by_current_thread()`.
    - An abort attached to a flight that becomes overdue, and is drained by a control `closeout`, observes the same (the command then fails with `closeout_overdue`).
    - An AST test finds no `scope.*` call, `self._gate` attribute call or `recv_attachment` call inside any `with self._lock:` body of `forwarder_control.py`.
25. **Gateless identity (`gate=None`).**
    - `register_scoped` and `closeout` give `unknown_operation`.
    - `register` for each of `confluence`, `grafana`, `kubernetes` and `anthropic` gives `scope_type_unavailable`, with `commands` 0 and `retained_records` 0. An earlier Jira lease of the session is revoked.
    - `"ghost"` and 7 still give the committed `invalid_service`, with `commands` 1.
    - The Jira register and revoke reply keys equal `_GRANT_FIELDS` and `_RECEIPT_FIELDS`.
    - A Jira lease registered over the gateless controller is inert at a separately constructed gate: `resolve` is `None` and there is no scope entry.
26. **Constructor.** A non-gate object, or a gate over another registry, gives `invalid_gate`.
27. **Custody scan** after failed paths (install failure, both replacement races, binding mismatch, a `closeout_*` hold).
    - A planted sentinel and a manifest-label marker are absent from raw error frames, `repr(ControlOutcome)`, the controller `__dict__` (excluding the injected `_registry`/`_gate`), and the registry and gate snapshots.
    - Every emitted code is within the closed union of committed codes, `SCOPE_CONTROL_CODES` and the codec codes.
28. **Pathname integration.** One `ControlService` with a `PrivateControlListener` under a mode-0710 parent in `/tmp`, following the committed supervisor-integration fixture:
    - `register_scoped` (over 8 KiB), `closeout`, `revoke`, then `stop`;
    - `ServiceCloseout.state == "stopped"`, then `gate.shutdown()` in the documented order.

**Root** owns:
- the documentation;
- the focused command: the three new files, plus `test_forwarder_control`, `_control_protocol`, `_listener_control`, `_supervisor`, `_supervisor_integration`, `_dispatch`, `_dispatch_seams`, `_dispatch_races`, `_dispatch_adversarial`, `_exchange`, `_exchange_integration` and `_exchange_adversarial`;
- the baseline skip count, measured before any edit with `pytest -q --ignore=tests/test_forwarder_upstream.py`;
- the full suite, run twice on the working tree as found:
  - `pytest -q --ignore=tests/test_forwarder_upstream.py` must show 0 failures and the baseline skip count;
  - plain `pytest -q` also collects the untracked 13b test. Its result is recorded. A failure confined to that file is not fixed here: the 13b files are never edited, and the root reports it for a decision before committing;
- `ruff check` on the changed and new files, and `git diff --check`;
- `git diff --stat -- tests/` empty, and `git status --porcelain -- tests/` showing only the three new files plus the pre-existing untracked 13b test;
- `validation.json`, with SHA-256 hashes of:
  - the source, tests and documentation;
  - both full-suite logs;
  - the two untracked 13b files, as observed but not owned.

An independent reviewer binds the final hashes before the local commit. There is no push.

## Critic issues resolved (revision 2)

| Critic issue | Resolution |
| --- | --- |
| 1. Register refusal only in gated mode, with a wrong rationale | Option (a): `refuse_unscoped` runs in both modes before any registry call. Revision 1's claim that the rule "would refuse every registration, including Jira" is withdrawn. I13 is restated as legacy identity for Jira, which covers every existing control registration. Gateless test: case 25. |
| 2. No hold on `overdue` contradicts spec L162-163 | Option (1): any control-observed `overdue > 0` (Revoke or `closeout`, including an `open` lease with an overdue flight) holds the registry before the error frame, and the command fails with `closeout_overdue`. Tests: cases 12a-d and 24. The remaining gap, an overdue flight that no control observation sees, is a residual risk and a deferred gate-side hold. |
| 3. `ok:true` Revoke with `closeout_state: "unknown"` | One representation: every uncertain Revoke is `ok:false` with `closeout_unknown`, `closeout_inconsistent` or `closeout_overdue`, after the hold. `ok:true` implies `draining` or `quiescent`. The L162-163 claim is withdrawn. Tests: cases 12b, 15 and 16. |
| 4. I6 overstated: install can succeed for an already-retired lease | I6 is restated. A post-install owner fence under `C` alone raises `session_replaced`/`control_closed` before any reply. Tests: case 20 (block after the snapshot) and case 21 (both windows). |
| 5. Holds after `C` release can hold the new owner's generation | Stated as the single permitted cross-owner effect, which spec L162-163 requires and which never grants authority ("Holds", I6, I8). Test: case 22. |
| 6. `observe_closeout` lacks type, range and coherence checks | Exact types, ranges, finiteness, coherence rules mirroring the gate's decision order, and `revoked`/`pruned` only after a revoke, all raising `closeout_inconsistent` so the hold runs. `unknown` after a revoke is treated as inconsistent rather than accepted; the reason is in Module 2. Tests: B5 and case 16. |
| 7. I9 and the `quiescent` row overclaim | I9 and the `quiescent` row are restated: unfinished admitted or writing flights count, finished uncertain ones count in `uncertain`, and `pending` can only become `NOT_DISPATCHED`. A flight finalized between the retirement and the observation correctly allows `quiescent`. |
| 8. `register_scoped` can outlast the heartbeat window | The attachment deadline is clipped to `min(timeout, ATTACHMENT_SECONDS = 2.0)`, so `register` runs at most about 12 s after the previous reply. The Receiver heartbeat obligation is documented. Tests: case 7 (clip) and case 23 (15 s fake-clock gap gives `heartbeat_late`, with session leases revoked). |
| 9. Case 4 contradicts itself | Split into 4a (first command) and 4b (after a successful `register_scoped`). |
| 10. `invalid_service` listed as new; `closeout` called read-only | `SCOPE_CONTROL_CODES` is redefined as codes the committed controller never emits, so `invalid_service` is dropped and `closeout_overdue` added. I12 now says `closeout` "spends no authority", with its retirement, abort-callback and reply-delay side effects stated. |
| 11. `_lock.locked()` assertion is racy; no structural check | The `OwnedLock` fixture asserts on the current thread only. An AST test covers `with self._lock:` bodies (case 24). |
| 12. Scope-capacity risk omits retired leases | Restated under "Residual risks" with the 310 s window, retired leases included, and the Receiver-side bound, tied to Deferred 7. |
| 13. `drain_deadline` and session-end guidance ambiguous | The presentation table uses `drain_deadline - observed_at` from the same reply, valid only in one clock domain. After EOF or replacement, the Receiver polls `closeout` on a new session before treating any lease as quiescent. Documentation lists both. |

## Judge findings resolved

| Finding | Resolution |
| --- | --- |
| extend-control test 14 expects `overdue` on a live lease | Case 12 retires the lease first (revoke, or the expiry variant). The live-lease case (12c) now asserts `open` with `overdue` 1 and a `closeout_overdue` hold. The "Closeout order" fact records why. |
| Codec reuse list omits `_socket_timeout` | Named in Module 1, steps 2 and 5. |
| The committed L293 selector would project `register_scoped` with receipt fields | Module 3, item 5 changes it explicitly to `registry_operation == "register"`. |
| `require_gate` pairs the gate and registry by generation only | Kept, and stated as a trusted-caller precondition in Module 2, Residual risks and Not qualified. It adds an exact `LeaseRegistry` type check. |
| test 16 cannot run on one shared clock | The gate-only `GateClock` wrapper (case 15). The registry and ledger stay healthy, so `registry.revoke` succeeds first. |
| Register refusal only in gated mode (routes plan Deferred 2 partly met) | Superseded in revision 2: the refusal now applies in both modes (critic issue 1). |
| `pruned` presentation unspecified | Presentation table and case 14. |
| Spec L122 keys only by mapping | Top-level `revoked_at` and `closeout_state` in the Revoke result, plus the nested closeout. |
| receiver-side: `gate if gate` truthiness | Module 3 uses `is None` only. |
| receiver-side: wrong stray-attachment codes | "Misframing fails closed" gives `oversize_frame` or `arrays_not_allowed`. |
| receiver-side: `unknown` Revoke closeout does not hold | This plan holds and fails the Revoke (I8). |
| receiver-side: changes ungated behavior and `commands` semantics | Not adopted beyond the explicit unscoped-service refusal. Jira legacy identity holds (I13). |
| receiver-side: client drain validator assumes one clock domain | Not adopted. There is no client and no timing validator. The docs state the single-domain condition for the drain budget. |
| receiver-side: full client library and invented runtime policy (`REVOKE_EXPIRY_GUARD_SECONDS`, `forwarder_time_hint`) | Deferred 4. |
| adapter-layer: second endpoint, invented handshake, changes to `forwarder_leases.py` and `forwarder_supervisor.py` | Not adopted. There is one existing connection (spec L221-222), and those modules are unchanged. |
| adapter-layer: sentinel sent from Receiver to Forwarder | Not adopted. The sentinel appears only in the Register reply (I10). |
| adapter-layer: lock `S` held across gate calls and abort drains | Not adopted. No control lock is held across a gate call (I11). |
| adapter-layer: registered-but-unscoped window and Activate before install | Not adopted. Install and the post-install fence happen before the sentinel leaves (I5). |
| adapter-layer: non-atomic Revoke closeout across two sockets | Not adopted. There is a single reply, observed after the retirement. |
| adapter-layer: `disposition`/`settled` vocabulary (`settled` even with `uncertain > 0`) | Not adopted. States are verbatim, and `uncertain > 0` must be recorded. |
| adapter-layer: `SCOPE_ERROR_CODES` listed committed codes as new | `SCOPE_CONTROL_CODES` lists only codes the committed controller never emits. |

Grafts applied:
- the post-install identity check;
- the after-revoke consistency hold;
- the literal L122 keys and `generation` in the closeout projection;
- the AST ban on registry calls;
- the custody scan;
- the fence-passed-before-revoke variant;
- reply-key parity tests;
- the `SCOPED_SERVICES` parity test.

## Residual risks the reviewers must accept

- **Session blast radius.** An install failure after a successful register ends the session under the committed rule that a rejected command terminates the session, and every lease of that session is revoked.
- **Scope capacity, retired leases included.** Retired leases keep their scope charge until their registry record is pruned (`created_at + 310` s; reconciliation drops only entries whose record is gone) or their entry ages out (`installed_at + 310` s). The gate budget is 2 MiB and 1,024 entries at 16 KiB plus 1 KiB overhead per maximum-size manifest. That allows about 120 maximum-size manifests **within any 310 s window, retired leases included**, before the 256-live-lease limit. Hitting it gives `scope_capacity` after registration, which ends the session and revokes all its live leases. **Receiver-side bound:** the sum of `canonical_bytes + 1,024` over every lease registered in the trailing 310 s stays at most 2 MiB, and the count at most 1,024. Deferred 7 aligns the constants.
- **Holds are terminal and coarse.** A control-observed `overdue` or known-lease `unknown` holds the whole generation, and new sessions are refused with `registry_held`. The Receiver cannot tell a held gate, registry or ledger apart. A single deadline-ignoring connector ends the generation once observed.
- **Overdue needs an observation.** The gate does not hold itself when a flight becomes overdue. An overdue flight is held only when a Revoke or `closeout` observes it. A Receiver that stops polling a draining lease, or never polls a live one, leaves new dispatch open until an observation occurs. A gate-side hold is Deferred 11.
- **Cross-owner hold.** A replaced session's uncertain observation holds the new owner's generation (case 22). It removes authority only.
- **Reply to a replaced peer.** After the post-install fence, a replacement can still let a `register_scoped` reply with an inert sentinel reach the replaced peer before its socket is closed, as with the committed Register reply.
- **Revoke of a retired lease stays fatal.** Revoking an already expired or revoked lease is a session-ending `LeaseError`. The Receiver uses `closeout` instead.
- **Closeout is readable for any lease of the generation.** It is fenced only at admission, so any lease ID of the generation can be read, including prior boots. The data is nonsecret metadata, and a replaced session's reply write simply fails.
- **Closeout side effects.** A poll can trigger time-based retirement and abort callbacks; a slow abort delays the reply.
- **Gate and registry pairing** rests on generation equality plus trusted exclusive ownership.
- **Slow commands.** A `register_scoped` can take about 12 s to receive. Staying inside the 15 s heartbeat window depends on the Receiver's heartbeat cadence.
- **Revoke latency.** Every gated Revoke takes `G` and reads the full registry and ledger snapshots, as in 13a.
- **Import coupling.** Import cost grows for the control and supervisor modules.
- **Gateless mode.** It still registers Jira without installing a scope. The launcher unit must require `gate=`.
- **Attachment budget.** The 16 KiB budget follows spec L238. AuthorizeDispatch framing may need its own budget.
- **Closeout memory is in-process only** and lasts 310 s.

## Deferred

1. AuthorizeDispatch permits, after the ticket-37 durable intent journal:
   - consume at admit step 5, atomically with L1, and re-verify at fence step 6, atomically with L2 (13a rule);
   - control framing: one outstanding authorization per service and a 5 s deadline clipped to the lease (spec L221-243);
   - whether permits reuse the attachment kind is undecided.
2. `Ready(service) -> {generation, route_id, tls_not_after, policy_digest}`, `route_id` in the Register reply (spec L121-123), and admission use of `policy_readiness_facts`.
3. The service worker supervisor and production composition:
   - stop order: `ControlService.stop`, then `DispatchGate.shutdown`, then listener close;
   - `gate=` made mandatory, with gateless construction refused in that composition.
4. A Receiver control client:
   - builds canonical manifest bytes and sends `register_scoped`;
   - schedules heartbeats around slow commands;
   - maps `revoked_at`/`closeout_state` and `closeout_*` errors, and polls `closeout`;
   - enforces the scope-capacity bound;
   - follows a dead-session rule and tracks unrevoked leases.
5. Non-fatal handling of revoke on retired leases and of install capacity refusals. Each would amend the committed rule that a rejected command terminates the session.
6. Scope types for Grafana/Eyes, Kubernetes, Confluence and Anthropic. `SCOPED_SERVICES` grows only with a reviewed manifest type and parser.
7. Aligning the gate's `MAX_SCOPE_BYTES`/`MAX_SCOPE_ENTRIES` with `MAX_LIVE_LEASES`, the maximum manifest size and retired-lease retention.
8. Durable closeout evidence beyond 310 s, restart reconciliation (ticket 37) and the ticket-38 `report_dispatch` hand-off.
9. 13b (a separate unit), the receipts amendment (`FAILED`/`lease_revoked`) and `PARTIAL` classification.
10. Linux `SO_PEERCRED` validation; deployed UID, mount and ACL isolation; control-secret custody and rotation; native clients.
11. A gate-side hold when a flight becomes overdue, independent of any control observation. This would amend 13a.

## Not qualified by this unit

- Any Receiver runtime behavior: client, heartbeat scheduling during a slow `register_scoped`, polling policy, or the scope-capacity bound.
- Proof of gate and registry pairing beyond generation equality. Exclusive ownership stays a trusted-caller precondition.
- AuthorizeDispatch, Ready, or any non-Jira scope type.
- Detection of an overdue flight that no control observation sees.
- Any real upstream connection (13b), credential, tenant or provider operation, native client or deployment.
- Linux peer credentials, and deployed UID, mount, kernel or secret isolation. Local Darwin same-UID sockets are not deployment evidence.
- Hard real-time drain or closeout bounds, and ledger clock divergence (the drain budget assumes one clock domain).
- Closeout answers after `installed_at + 310` s, and any durable record.
- The sizing of the 16 KiB attachment for future permit frames.
- Any external effect or human Report adjudication.
