# Unit 13a dispatch gate and one-request exchange: independent review

## Design and review history

A read-only design panel produced three competing designs: atomic-first,
upstream-first and handler-first. Two judges picked atomic-first (41 against 38
and 32/33). A synthesizer grafted in the fixes the judges required: a pre-write
fence, a response margin before the ledger sweep, fresh-clock phase deadlines
and prepared, non-v1 digests. A completeness critic then raised 20 issues,
resolved in [plan revision 2](implementation-plan.md): overdue flights instead
of deletion, record-verified scope installation, the permit rule, and exclusive
gate authority. Root reconciled the plan against the unit-12 commit before
implementation started.

The implementation workflow used Sonnet workers and testers, Opus lens reviewers
(contract, atomicity, fail-closed, test adequacy), Sonnet refuters and an Opus
fixer.

| Round | Raw findings | Confirmed | Outcome |
| --- | --- | --- | --- |
| 1 | 26 | 15 | fixed: shutdown lifting a hold, `closeout` reporting quiescent while writing, a raising channel attribute, clock faults outside tick handling, and others |
| 2 | 11 | 7 | fixed: held-gate `closeout` counts, connector exception chaining, delivery deadlines, and others |
| 3 | 12 | 10 | three low-severity source fixes by root; seven test gaps closed by a test agent |

The root's three source fixes:
- **Forged tokens.** A forged token whose `receipt_id` is unhashable is now simply unknown; it no longer raises a raw `TypeError`.
- **Permit slots.** They deny unless `requires_permit` is exactly `False`, so a falsy value fails closed.
- **Shutdown aborts.** Shutdown runs its own abort callables directly, so another thread's drain cannot misreport its failure count.

The test agent pinned all ten items and confirmed 11 of 12 mutants. The remaining mutant is also caught by a deterministic sibling test.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. It verified 11 SHA-256 values; the
final test hash is listed after the addendum.

```
d74de44ee934e92658f6115cf7610e873ee04a903ca172abd7e981f97320b6c2  grafana_jsm_sandbox/forwarder_dispatch.py
7461484cc0b1afc88eebdbd941095eb0ed3fe25758c1427f817f4588ea5f810a  grafana_jsm_sandbox/forwarder_exchange.py
80a9dada1bc2f36fb01d2e9c0f5edb80dbf0f6297bead2745ff92137cf8cf806  grafana_jsm_sandbox/forwarder_http_receive.py
ebe58ace2489d38759b1ffe4b852e02ec69749c51368f315c1ca513abcdade7e  grafana_jsm_sandbox/forwarder_server_tls.py
9c9e6cde1a3ca381c6f36efef75806c2552735ce00a71fb0177a3aab7d49fbfe  tests/test_forwarder_dispatch_seams.py
6c8db23af3d13f577854e88d9f9f9e36107971b6202ff4ea32d70919ca2d0ea8  tests/test_forwarder_exchange.py
1b5fb6ffecbb662ed7adda792aa8713dda58fcd0f3eb9e2c4889ee4ae3d4ffb1  tests/test_forwarder_exchange_integration.py
763231362bdcfd6133e1cfdbd44b49fe126aa926511b4c67717718f842d42ad4  tests/test_forwarder_dispatch_races.py
9efd998dda5fb8fc209004bf2980a25063e4747e1b89ff9213c085f44e711987  tests/test_forwarder_dispatch_adversarial.py
aa47575fb557b3981e805a6580daa72dc80f84d8ece78fdcd2c63d506d870556  tests/test_forwarder_exchange_adversarial.py
```

Verdict: **PASS (source and test review)**. No source defects were found.

- **Seams.** Both seams are purely additive. `receive_request` returns the verbatim body's result through `_receive(...)[0]`. Every existing test file is byte-identical, and the 93 existing receive and server-TLS tests pass.
- **Lock order.** The gate lock precedes the registry and ledger locks. Only the three clocks, gate code and unit-12 code run under the gate lock; connectors, aborts, receive and send never do.
- **L1 and L2.** Each lease check runs with the stored generation. The closed-gate check runs in the same critical section as its ledger step (`begin_connect` for admission, `begin_dispatch` for the write fence). The clock-domain guard holds the gate on divergence.
- **Wire order.** Connect happens only after `admitted`, send only after `write_admitted`. `FAILED` appears only before the fence, and `NOT_DISPATCHED` only before `begin_connect`.
- **Overdue flights.** Overdue flights are marked, never deleted by another thread. Each abort is queued once and runs outside the gate lock, and the flight keeps its slot.
- **Closeout.** `closeout` ticks after the ledger snapshot and applies its precedence order.
- **Shutdown.** It never touches the registry and runs only its own aborts.
- **Scope installation.** `install_scope` requires exact equality with the registry record.
- **Deadlines and digests.** Deadlines match the plan's table. The digest rule holds: no v1 route digest reaches a reservation.
- **Race tests.** The race tests are sound. R1 starts its `closeout` before the retirement but observes after it, which still demonstrates in-flight visibility.
- **Mutation probes.** 35 of 38 in-memory mutants were killed. Two survivors are equivalent to the original code. The third exposed a test gap: the sentinel-to-lease binding check in `install_scope`.
- **Size.** Of `forwarder_dispatch.py`'s lines, about 854 are statements, against an 850-line target; `forwarder_exchange.py` has about 391 statements against 450. There is no dead code; the reviewer judged this design content, not bloat.

**Non-blocking findings, applied before commit:**
- Root appended a parametrized test in which a grant carries another lease's sentinel. Deleting the `lease_id` comparison now fails its registered-lease case; the active case is independently denied by the scope check.
- Root corrected the documentation's receipt-backed overclaim. It also added the lazy overdue abort, the shutdown behavior for a connect in progress, the lock and supervisor order, and the missing non-claims.

## Addendum re-verification

The same reviewer then re-checked the final test file:
- **Final hash:** `c8088861eb409feeda4d23bcf0ee26cde95ce72ff4768c1f7c7d9fb7a2767740  tests/test_forwarder_dispatch.py`.
- **Pure append:** hashing its first 1,847 lines reproduces the reviewed file, and the other ten hashes are unchanged.
- **Mutation reproduced:** deleting the `lease_id` comparison in memory fails the registered-lease case while the other 291 tests pass.
- **Documentation:** the corrections are accurate. Two remaining wording nits were fixed before commit: overdue marking happens on a gate tick, and a deadline after reservation leaves a swept `abandoned` receipt.

Addendum verdict: **PASS**.

## Residual limitations (accepted)

- **Connector trust.** `FAILED` is truthful only if `connect` writes no application bytes; the connector contract is qualified in 13b.
- **Stuck connectors.** A connector that ignores its deadlines is bounded only by the lazy overdue abort and the ledger sweep. One that ignores both deadline and abort holds a slot until it returns.
- **Abort threads.** Aborts run on whichever request thread ticks first. A `BaseException` from another flight's abort escapes that unrelated request, which then ends `DISPATCHED_UNKNOWN/abandoned`.
- **Clock divergence.** Ledger clock divergence is detected only partially.
- **Closeout scope.** `closeout` is in-process only and forgets a lease after 310 seconds. Under capacity pressure the reconcile step can drop a pruned lease's entry early, and `closeout` then reports `unknown`.
- **Lock hold time.** `install_scope` and `closeout` hold the gate lock while reading full snapshots.
