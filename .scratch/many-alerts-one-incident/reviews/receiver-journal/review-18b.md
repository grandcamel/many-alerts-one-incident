# Unit 18b independent review

Status: local pure/synthetic review, 2026-09-24. Final full-suite gate and
hash read-back are recorded in `validation-18b.json` and `outcome-18b.md`.

The independent design critic first blocked the exact plan on completeness
provenance, digest verification, idempotency order, active journal origin,
exact event fields, capacity/test reachability, lifecycle origin and time
behavior. Those points were reconciled in `implementation-plan-18b.md`
before source editing. The critic then accepted implementation of the pure
synthetic subset; it did not accept a durable ledger or launch gate.

The independent source reviewer inspected both new modules, tests, docs and
plan. Confirmed findings and red/green repairs:

| Finding | Repair and regression |
| --- | --- |
| Empty history reported `history_limit` | Returns `history_unavailable`; exact-code test. |
| Profile/genesis IDs could cross roles | Genesis distinctness, role-aware profile reuse and cross-role refusal tests. |
| Public Projection fields could be forged against event bytes | Public `apply_event` replays and compares the presented projection; forged-projection test failed before the fix. |
| Malformed time retained caller text in exception context | Raise the closed error outside the `except` block; context test failed before the fix. |
| Current event ID could equal a newly introduced body ID | Explicit collision check; journal-binding collision test failed before the fix. |
| Same admission ID could shift journal origins | Reject cross-origin reuse while permitting another intent in the same origin; both tests. |
| Year outside 18a's policy range leaked `PolicyInputError` | Closed transition `invalid_time`; year-boundary test. |
| Public apply could exceed 8,192 events and checked projected state before a stale head | Limit new events; check expected head before rebuilding. |
| Replay reparsed every prior event for fresh-event identity checks | Immutable claimed/event-ID indexes. Reviewer benchmark on 129/257 synthetic bindings improved from 4.39/16.05 s to 0.093/0.179 s. This is local performance evidence only. |

The first review found missing plan cases. Focused tests now include canonical
bytes and external digest, malformed schemas and money, changed duplicates,
forged state, source identity, incomplete/unknown history, stale U, old-week
and old-generation lifetime liability, retry diagnostics and cross-week
refusal, sticky holds and the replay input cap. The no-settlement subset cannot
reach independent count ceilings or 512 lifetime attempts with coherent U>=R
history before spend caps; those replay proofs are explicitly deferred to a
future settlement transition. Existing 18a tests continue to exercise the
pure count predicates with coherent settled-history fixtures.

The fresh reviewer found no remaining P0/P1 source defect in the local
pure/synthetic scope. After the full gate, it read back all 12 artifact,
four tested-input and four protected-file hashes; verdict:
**ACCEPT_LOCAL_PURE**. The full log shows 5,100 passed and 39 skipped;
the guarded focused log shows 161 passed with no non-loopback attempts.
This review accepts only the local pure/synthetic result;
provider, tenant, paid, native, filesystem durability, concurrent writer,
cross-store recovery, dispatch and human adjudication remain NOT RUN.
