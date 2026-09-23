# Unit 13a dispatch gate and one-request exchange outcome

2026-09-23. PASS for the thirteenth separately authorized local application
unit (13a), baseline `edd3ad5`. [validation.json](validation.json) records the
final verdict and evidence. The work is local only: nothing was pushed and no
planning ticket was closed.

## What the unit adds

`forwarder_dispatch.DispatchGate` permanently claims one lease registry and one receipt ledger of the same generation. It never mutates the registry.

**Two linearization points.** Each runs under the gate lock, with no I/O between the lease check and the ledger step it authorizes:
- `admit` runs the lease check and then `begin_connect`.
- The `begin_write` fence runs the final lease check and then `begin_dispatch`, immediately before the first possible upstream write.

After a revocation, EOF, replacement, hold, expiry, heartbeat loss or gate shutdown is ordered, no later admission or fence succeeds. A request stopped at the fence ends `FAILED` with zero application bytes. A request whose fence came first may complete and be delivered.

**Scope entries.** Scope entries install only after manifest binding and exact registry-record verification, and are indexed by a keyed HMAC. They are count- and byte-bounded and age out after 310 seconds.

**Deadlines.** Deadlines share one clock domain:
- 40 s handler, clipped to the lease;
- a 1 s response margin before the ledger sweep;
- 5 s connect, 10 s write;
- minimum budgets of 2 s at admission and 0.5 s at the fence.

**Overdue flights and closeout.** Overdue flights keep their slot and fire their abort once, outside the lock. `closeout` reports `open`, `draining`, `overdue`, `quiescent` or `unknown` from in-process observations.

**Permit rule.** The consume-at-admit, re-verify-at-fence rule for future permits is decided but not implemented; permit routes are denied at both slots.

`forwarder_exchange.serve_request` serves one inbound TLS request, in order:
1. sized receipt, sentinel resolution and lease precheck;
2. route policy, then a connector-prepared digest (never the v1 route digest);
3. reservation, admission, connect and fence;
4. send and receive;
5. response policy, finalization and receipt-gated delivery.

No response byte is sent without a recorded receipt. `serve_one` binds the receipt's service to the listener and closes the connection. No upstream connector ships in source.

Two existing modules gained additive seams: `receive_request_sized` (exact inbound byte count) and `FixedTLSListener.service`.

## Review

- A design panel of three designs, two judges and a critic produced the plan. Root reconciled it against unit 12.
- Sonnet workers implemented two modules, two seams and seven test files.
- Opus lens reviewers, Sonnet refuters and an Opus fixer confirmed 32 findings over three rounds. The workflow fixed 22; root fixed three low-severity source items; a test agent pinned the rest.
- A fresh reviewer bound the final hashes: PASS, 35 of 38 mutants killed.
- The reviewer found one test gap (the sentinel-to-lease binding in `install_scope`) and documentation precision issues. Root fixed them, mutation-checked the new test, and the same reviewer re-verified them ([review](review.md)).

## Validation

- Unit tests: **292 passed**, repeated runs.
- [Focused Forwarder suite](focused-tests.txt): **2043 passed** before the final added test.
- [Full suite](full-suite.txt): **2919 passed, 36 skipped in 149.58s**, exit 0.
- Ruff (including line length), compile and `git diff --check` pass. Every existing test file is byte-identical.

## Not qualified

- a real upstream connection, the connector contract, a credential or the v2 digest;
- AuthorizeDispatch permits;
- manifest delivery or `install_scope` over control, and control-level closeout;
- a worker supervisor or readiness wiring;
- PARTIAL, the durable journal, SSE, non-Jira routes, native clients and deployment;
- hard real-time deadlines, and a connector that ignores both deadline and abort.

## Not performed and next

No provider, tenant or native call was made. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

Next is unit 13b, the synthetic fixed-origin upstream connector from the [upstream plan](../forwarder-upstream/implementation-plan.md), after reconciliation against this commit. Planning ticket 36 remains open.
