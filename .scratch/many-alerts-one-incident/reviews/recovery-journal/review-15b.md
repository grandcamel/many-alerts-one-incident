# Unit 15b recovery journal reducer and shell: independent review

## History

Unit 15b is the second part of the fifteenth unit. Its design history is shared
with 15a; see [review-15a](review-15a.md) and the plan's root notes. It adds the
pure reducer (`journal_reducer.py`) and the journal shell (`recovery_journal.py`),
built on the committed 15a layers at `f68c9aa`.

| Step | Result |
| --- | --- |
| Implementer B: pure reducer | 54 tests, including a property test against an independent reference model |
| Implementer D: shell | 37 tests (D1-D14); 275 real syncs |
| Tester E: crash images | 41 tests over E1-E18; 268 real syncs; confirmed one source bug |
| Tester F: adversarial | 45 tests over F1-F9; 67 real syncs; found one source bug |
| Round-1 review: contract, durability/concurrency, fail-closed and test-adequacy lenses | shell error-handling defects, reproduced by probes; 28 of 39 mutants killed |
| Opus fixer | all eight source findings fixed; 25 new or tightened tests fail on the pre-fix sources |
| Gap agent | eight test gaps closed; 13 mutants killed |

**Tester findings.** Both were pinned by failing tests before the fix:
- After a crash between the two hold-slot writes, the next open saw a hold on the anchor and skipped `persist_hold`, so a half-written hold was never completed.
- `JournalError` was raised inside `except` blocks, so `__context__` kept the wrapped exception, contrary to the module's own custody rule.

**Round-1 findings:**
- **Medium; three lenses independently.** Open had no close-on-failure guard. An emptied events table crashed open with `AttributeError`. Failures in `finish_open`, in `id_factory` at open or during restart, or a `BaseException` in the restart append escaped raw and leaked the store's lock, so later opens in the process got `journal_locked`.
- **Low:**
  - `id_factory` exceptions escaped `admit` and `create` raw.
  - `verify_commit` accepted a genesis at any generation, and read positions before its type check.
  - The snapshot could not be JSON-encoded, showed projection fields while held, and misreported `lag_at_open` on held opens.
  - `create` verified genesis only after writing it.

The concurrency lens confirmed that the crash windows C3, C11, C12 and an interrupt during the admission's anchor write all behave as planned. Open adopts only lag 0 or 1, re-anchors before `restart_recovery`, and syncs the directory before the restart anchor.

**Fixer.** Every exit after the store opens now closes it. An emptied table is a persisted `journal_truncated`, and a `finish_open` failure returns a held handle (`journal_open_failed`). `persist_hold` is called for every recovery finding. No `except` block raises. `id_factory` faults latch `journal_divergence`. `create` refuses with `journal_argument` before any write and verifies genesis before the store writes it. Genesis must be at generation 1, and `verify_commit` checks types first. The snapshot is JSON-encodable, with null projection fields whenever the journal is held.

**Gap agent.** It added:
- `journal_anchor_conflict` from forked journals sharing one UUID;
- a pool-based B5 property test with small bounds, all outcome counters above zero, and a run time of about 3 s instead of 20-28 s;
- the restart record's `anchor_lag` and `wal_found` at lag 0 and lag 1;
- the `capacity_hold` source digest and a single hold per code;
- a check that the projection is unchanged after a failed append;
- B9 cases for `dedupe_key`, `source_group` and `baseline_before`;
- the same-pair duplicate ID;
- a bounded read in the SIGKILL loop.

Root removed a stale docstring reference and recorded the contract refinements in the plan and the documentation.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. It verified these SHA-256 values
at HEAD `f68c9aa`. It also confirmed that the 15a sources and tests still match
their committed hashes. The final hashes are listed after the addendum.

```
5dd861447478c7cd737ddaeef71da397ef2f234f84afefc32310e47d5ab3c459  grafana_jsm_sandbox/journal_reducer.py
4800013b6674ee5b54880b02194367a8e0f67b2aa9b645dc5e368121e30f6ee0  grafana_jsm_sandbox/recovery_journal.py
be2d0d84ee27dd1a70fcec1235817cd65965f7ac6f0ebfeed43da7f0fa251c9c  tests/test_journal_reducer.py
59f01df1f4dc739f616aa839d9db1bd5c17062a01401da700b6ae3741d0ba9ae  tests/test_recovery_journal.py
b031354c2bfaea29a63e33fdd3abd2cfeaf2343ccfa933c345827cd9bc381d6b  tests/test_recovery_journal_crash.py
8100844741ca9bfcc19f790d8a93ca4596697fea03c61ac58b2e4522b15f83f5  tests/test_recovery_journal_adversarial.py
b49d72ed086c51c2b68b94e602f5f7d805b34694693422a6fa75bb521a5d619c  tests/data/recovery_journal_v1_golden.jsonl
458bc2eb8b5511dd3146da9a7db6f4e7435243b4896515aad3bf057659092fbe  docs/recovery-journal.md
1f1b756c2505503f4574e05404014ded85fe45cb84fe67672dc5727e6001d458  .scratch/many-alerts-one-incident/reviews/recovery-journal/implementation-plan.md
```

Verdict: **PASS (source and test review)**. Nothing blocks the commit.

- **Reducer.**
  - Ticket-31 dedupe holds: the baseline is per group, and only a non-suppressed arrival moves it. A `truncated_alerts` other than 0, including null, is never suppressed.
  - Pending entries carry every superseded identity. A suppressed repeat reclaims only an entry that another group holds, and never creates one.
  - Capacity is checked before crossing, in order: admissions, then pending (suppressed arrivals exempt), then bytes. There is no eviction path, and each code gets one hold, in both plan and verify.
  - Replay uses the same `verify_commit` and `apply_delta` as the live path, and all eight replay codes are closed and mapped. Types are checked first, genesis is pinned to generation 1, and the module is pure.
- **Open.**
  - Nothing is installed before the full replay and the four-field anchor check. An emptied table is `journal_truncated`.
  - Lag is 0 or 1 only, with the re-anchor before `restart_recovery` and the restart commit syncing the directory.
  - `persist_hold` runs for every recovery finding and completes a half-written hold. Every non-clean exit closes the store.
- **Admit.** Everything runs under the lock, and the receipt and `apply_delta` come only after `append`. Every failure latches its fixed code, and a `BaseException` latches on its way out.
- **Custody.** No `raise` inside `except`. The snapshot has a fixed 16-key shape, is JSON-only, and hides projection fields while held.
- **Mutation probes.** Of 32, 16 were killed (5 of them by an error rather than an assertion), 1 was equivalent, and 15 survived. The survivors were forged-history re-checks in verify (T2), three of the four anchor-agreement fields (T3), several low-value cases (T4), and projection hiding for two latched codes. The hiding check is code-agnostic, and the source rejects every probed forgery.
- **Size.** Reducer: 767 lines, 372 statements, against a 350-line target. Shell: 629 lines, 343 statements, against 270. About 70-90 reducer lines and 50-60 shell lines could be folded, which is well below the earlier estimate. The refactor can wait: the golden guard and the live `verify_commit` catch drift.
- **Runs.** The four 15b suites passed twice with 195 tests in about 45 s. Real syncs: D 319, E 287, F 68.

**Applied before the addendum:**
- **Source (root):**
  - N1: `_read_clock` bounds the monotonic reading to `MAX_SEQ`, so an overlarge clock is `journal_clock_invalid`, not `journal_divergence`.
  - N2: the `state`, `hold` and `dispatch_holds` properties take the journal lock. The snapshot uses an unlocked helper, which avoids a self-deadlock.
- **Docs (root):**
  - D1: open raises for a missing, locked, misplaced or unsupported journal and returns a handle only once the store is open.
  - D2: a suppressed repeat changes pending only by reclaiming another group's entry.
  - D3: removed the stale "next unit's" snapshot reference.
  - Nits: the crash-window table row; the crash-image coverage wording; `pending_reduced` in the worked example.
- **Tests (gap agent):**
  - T1: F2's ready branch now reopens with non-colliding IDs and asserts both outcomes.
  - T2: the six forged-history re-checks.
  - T3: the three untested anchor-agreement fields.
  - T4: the low-value cases.
  - Tests for N1 and N2, the D4 tautology, a golden-regeneration test, and a wider B5 pool.

## Addendum re-verification

The same reviewer re-checked the post-review tree:
- **Source diff:** exactly N1 and N2. Negative monotonic readings are still refused.
- **Deadlock:** there is no path. Nothing in the module calls the three locked properties, `_run_restart_recovery` runs before the handle is returned, and no other module uses the handle.
- **Docs:** D1-D3 and the nits read correctly.
- **Golden regeneration test:** only the WAL-salt digest in the restart record, and the digests that follow from it, are exempt. Every earlier record must be fully equal, and later records must match in every field except their predecessor digest.
- **Mutants:** on a fresh copy, all 13 earlier survivors plus the N1 revert and the three N2 reverts are killed. That includes S17-S19, S21-S23, S25-S27, S36 and S39-S41.
- **Runs:** the four suites gave 213 passed twice, and F2 exercised both branches (held 12, ready 28).

Addendum verdict: **PASS**.

Its two nits:
- The open-refusal list in the documentation omitted the permissions and argument refusals. Root added them.
- The N2 lock test waits 0.2 s, so a reverted lock could occasionally pass on a slow machine, but it can never fail on correct code. This is accepted.

Final hashes:

```
5dd861447478c7cd737ddaeef71da397ef2f234f84afefc32310e47d5ab3c459  grafana_jsm_sandbox/journal_reducer.py
d01980d00e7943bfb836671e3a610f48f8ac03fca18b54159339331bb11166f5  grafana_jsm_sandbox/recovery_journal.py
f8a860e6c4e228ad34901cc5398d81da04c466203ae462c0fc3b53f0a52406ab  tests/test_journal_reducer.py
90120ac3c5e45f9e3ed86bc95d6d3fd6bf2623e5d641091987357a65c9541cd0  tests/test_recovery_journal.py
867b09a91ce0fdee883627e2b93b16470318819ee476d42034278525706a653b  tests/test_recovery_journal_crash.py
9d4f2cbc43ae6d37439347e9e5e58cb1d9977d5b7a885bfd77f4e7c7acbafb6f  tests/test_recovery_journal_adversarial.py
b49d72ed086c51c2b68b94e602f5f7d805b34694693422a6fa75bb521a5d619c  tests/data/recovery_journal_v1_golden.jsonl
```

## Residual limitations (accepted)

- **Forgery and the lock.** Same-uid forgery of a self-consistent history, or a consistent rollback of every file, cannot be detected; both are stated non-claims. The lock stays held after a restart-time latch until `close()`, which is consistent with admit-time latches.
- **Test coverage.** Crash tests model process crashes, and power loss only by editing images. Open time is extrapolated from 2,000 pairs (about 3.2 s). The suites run on macOS only.
- **Size.** About 70-90 reducer lines and 50-60 shell lines could be folded. The refactor is deferred, because the golden guard and the live `verify_commit` catch drift.
- **Integration.** The journal is not wired into the Receiver. Pending is never consumed, and dispatch holds are never cleared.
