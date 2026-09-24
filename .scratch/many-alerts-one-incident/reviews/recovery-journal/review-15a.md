# Unit 15a recovery journal records, source and store: independent review

## Design and review history

A read-only design panel produced three competing designs for the first
ticket-37 journal unit:
- **SQLite-transactional:** one WAL database plus a separately synced anchor file.
- **Hand-rolled framed log:** a length-prefixed log with a high-water mark.
- **Domain-first reducer:** a pure fold over one backend.

Probes by the designers and judges showed two things about SQLite. First, it silently drops committed transactions when the WAL is truncated or a middle frame is damaged, while `integrity_check` still reports `ok`. Second, closing a connection on a damaged journal can delete the WAL. Both findings shaped the plan.

Both judge panels picked the SQLite design: 47 against 46 and 43 (durability and fidelity), and 43 against 42 and 40 (boundedness and fit). A synthesizer grafted in:
- the domain design's pure reducer and property tests;
- the log design's crash enumeration and single-in-flight tail rule;
- the split between verified, persisted integrity holds and transient, in-process holds.

A completeness critic then raised 15 issues (2 high), all resolved in
[plan revision 2](implementation-plan.md). The two high issues:
- `SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE` is now mandatory, so no open can destroy evidence. It needs Python 3.12 or newer and fails closed on 3.11.
- Digest and chain verification now run before typed validation, and a typed failure on a verified row is never persisted.

**Split.** Implementation crossed the plan's own size thresholds. Following Module 1's split point, the source-record section moved to `journal_source.py`. Following the plan's size rule, the unit is committed as:
- **15a:** records, source and store, with their tests and the store-level documentation;
- **15b:** the reducer, the journal shell, and the crash and adversarial suites.

The split is recorded in the plan's root note.

Implementation used individual agents: Sonnet implementers with disjoint file ownership, four Opus lens reviewers, an Opus fixer, a Sonnet gap agent and root fixes.

| Step | Result |
| --- | --- |
| Implementer A: records, then the planned `journal_source` split | 121 tests |
| Implementer C: SQLite store and anchor | 64 store tests; 74 real syncs |
| Round-1 review: contract, durability, fail-closed and test-adequacy lenses | 20 distinct confirmed items (3 high), each reproduced by probes; 13 of 33 mutants survived |
| Opus fixer | all 20 fixed; each new test fails on the saved pre-fix sources (57 store and 7 records/source tests) |
| Root | `find_duplicate` and `finish_open` map `sqlite3.Error` to `store_write_failed` and latch the store |
| Gap agent | 8 gaps closed; 15 mutants killed by assertions |

**Round-1 confirmed items:**
- **High:**
  - The anchor vocabulary lacked `journal_tail_unverified` and `journal_replay_mismatch`.
  - A directory name containing `?`, `#` or `%` sent SQLite's database outside the checked 0700 directory, as a 0644 file.
  - `open()` and `rows()` let raw exceptions escape and leaked the lock.
- **Medium:**
  - A transient `lstat` error was persisted as `journal_truncated`.
  - A hold-free anchor write could erase a persisted verdict.
  - A zero-byte database let SQLite delete the WAL.
  - The SQLite version gate was never checked.
  - The anchor codec accepted semantically invalid slots.
  - `find_duplicate` matched partial or mixed commits.
  - Raises inside `except` blocks kept caller paths as context.
  - Unsorted values were accepted.
  - `superseded` fingerprints could carry free text.
- **Low:**
  - Non-ASCII digits were accepted.
  - `thaw` could recurse without bound.
  - Sync failures in anchor writes did not latch the store.
  - A mistyped predecessor digest was persisted as `journal_chain_broken`.
  - A crash between the two hold-slot writes left the second slot never written.
  - `append` accepted records it had not checked.
  - `verified_head` advanced before its commit group was verified.
  - Two pragmas were set but never read back.

**Gap agent.** It closed the row-verification pipeline (chain, digest, duplicate `event_id`, column mismatch, end-to-end re-signed update), the `find_duplicate` content check, WAL preservation on ready and held reopen, write ordering including `pwrite`, the anchor checksum, lone-slot parity and anchor-read errors, the exact DDL golden and the contiguity trigger, and both root fixes. It also made the subprocess lock test independent of the working directory.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. It verified these SHA-256 values
at HEAD `6a3ecc2`; the final hashes are listed after the addendum.

```
8cd5749dfc8bd947bfc6dae040e0db43f13117a36f6fa0cf183e0350a0a07f39  grafana_jsm_sandbox/journal_source.py
f54334570b5382137624f3bc17f6162166e9bf5b929971c4e224dc43b3d81690  grafana_jsm_sandbox/journal_records.py
04c0288697f5241e24ce800cb428845196285d7bc2be65817be816ced23921ee  grafana_jsm_sandbox/journal_store.py
1a5c648b122f2d75578bb9dee21e07fadfc4a48c6765bd6e8f735a71ba3e37ed  tests/test_journal_source.py
d379eeac9cbd3e6bebe77b125c22e59298cdf1f0f40ad165ccbbccce9040ad7a  tests/test_journal_records.py
6ccbfefa71855d53801650408f43b1bee804933b6b43fc3d2ccffe89b16182c0  tests/test_journal_store.py
9ab8a48c2b8ae1fe09c0e8d1a3d2931a7e29777d123883d57355b79be089f0a4  docs/recovery-journal.md
dcee1545977aee2dfe3bb685150f64bbb0d0f6a96119e7efb465cafe7779b67c  .scratch/many-alerts-one-incident/reviews/recovery-journal/implementation-plan.md
```

Verdict: **FAIL**, on one blocking test gap. The reviewer found no blocking
source defect.

- **Record and source layer: PASS.** The digest is checked before parsing, and exact types and closed codes hold (an AST sweep found every raised code inside its closed set). The I17 grammars hold. It recomputed five goldens and eight `canonical_number` lexemes independently, and all match.
- **Store durability: PASS.**
  - The append order is COMMIT, then the optional directory sync, then `pwrite`, then the full sync. There is no fallback, and a failed write latches the store.
  - `NO_CKPT_ON_CLOSE` is set at the only connect site.
  - Probes: a mid-WAL flip, then open and close, left the database, WAL and anchor byte-identical. A zero-byte database gives `journal_truncated` with all bytes unchanged. The reviewer also confirmed that raw SQLite deletes the WAL of a zero-byte database even with `NO_CKPT` set, so the short-database guard is necessary.
  - A transient EIO gives the process hold `journal_open_failed` and writes nothing. The lock is released on every failure path.
- **Round-1 and root fixes: PASS.** All 22 are present and correct, with no regression.
- **Custody: PASS.** No `raise` in any `except` or `finally` block.
- **Mutation probes.** Of 28, 11 were killed and 2 were equivalent. Fifteen survived:
  - **M01-M05, blocking.** No test read back the durability pragmas, so `synchronous=NORMAL` or dropping `fullfsync`, `checkpoint_fullfsync`, `trusted_schema` or `cell_size_check` passed all 280 tests.
  - **The other ten**: an anchor head behind the previous one, different anchor UUIDs, an `event_seq` column mismatch, `observed_commit_seq`, an `integrity_check` failure, the `ordinary_bytes`/`total_bytes` relation, the actor set, the `admission_id` binding, a non-fixed provenance path, and duplicate `superseded` fingerprints.
- **Size.** About 1,547 of the 2,110 lines are code, 1.75 times the 880-line target. Most of the store's growth is design content from the round-1 fixes. About 60-90 lines could be folded (predicates duplicated across modules, `_genesis_uuid_conflicts`, one-use helpers). This is not a blocker.

**Applied before the addendum:**
- **Source hardenings (root):**
  - S1: `_write_slot` refuses a head behind the current anchor, and any body the reader would not classify as v1, before writing.
  - S2: `persist_hold` refuses to replace a different persisted verdict.
  - S3: genesis-bounds validation iterates in sorted order, so the error code no longer depends on the hash seed.
  - S4: `canonical_number` rejects a `JSONDecimal` whose text is not a string.
- **Docs (root):** D1-D5 applied. The verification order is corrected; the latch is scoped to the store object; the anchor changes only when a verdict is persisted; a missing or invalid anchor is re-derived, not persisted; the digest descriptions are precise. The plan's root note now gives the current line counts.
- **Tests (gap agent):** the blocking settings read-back on create and open, the ten other surviving mutants, the `errno.ENOTSUP` label, and tests for S1-S4, each proven against a mutant.

## Addendum re-verification

The same reviewer re-checked the post-review tree:
- **Source diff:** exactly S1-S4, with no regression.
- **Mutants:** on a fresh copy, 20 of 21 are now killed by assertions or `DID NOT RAISE`. That covers M01-M05, M08, M17-M20, M23-M27 and the reverts of S1-S4.
- **Docs:** D1-D5 are accurate against the source. It re-probed the short-database sentence and it holds.
- **Runs:** two runs gave 297 passed, 2 skipped.

Addendum verdict: **PASS**.

It left three non-blocking nits, all addressed before commit:
- **S1 check order.** A `Head` with a string or `None` sequence field reached the "behind" comparison before `_slot_kind` and escaped as a raw `TypeError`, though nothing was written. The one surviving mutant also showed that the `event_seq` half of that comparison had no test. Root now runs `_slot_kind` first and added `test_write_anchor_refuses_an_event_seq_behind_or_a_mistyped_head`, one fresh store per case. On a scratch copy, dropping the `event_seq` half fails it with `DID NOT RAISE`, and the old order fails it with the raw `TypeError`.
- **Stale tracker counts.** They were already updated to the current gate result.
- **Documentation wrap.** Three reflowed lines were rewrapped.

Final hashes:

```
a5e9b9516e441b1cb7b14d8fc7f2fac59814c14dafc56bf188358e77a497c2d1  grafana_jsm_sandbox/journal_source.py
a7320dc1238f3406958d49ab980a3bdbc8a49ab90a5a5c43fd22c3629ef63994  grafana_jsm_sandbox/journal_records.py
fc5e79bec3d1ccddda403b986e708ff80a0a10d7ac696f8c4153b788ae09c627  grafana_jsm_sandbox/journal_store.py
8abf9de168fb459111c24228b926a5c0ad8d1aa1f5794590f0dba1132ccf8da3  tests/test_journal_source.py
de7ed910158e857e7d40dfde6798e5da2766b9c920f2858e1f0ee0a4fd1c8d17  tests/test_journal_records.py
746dee72f847a53783ac411a0b41d2f13954e1eb988cf76e575161d48ffd2155  tests/test_journal_store.py
```

## Residual limitations (accepted)

- **Trust in the shell.** The store trusts 15b's `verify_commit` for chain and head monotonicity on append; the anchor side now refuses backward heads. `finish_open` does not require that `rows()` has been fully drained, and that ordering belongs to the 15b shell.
- **Undetectable tampering.** A consistent rollback of all files, or a same-uid process writing a valid anchor, cannot be detected; the digests are unkeyed. Both are stated non-claims.
- **Platform evidence.** Linux behaviour is covered only by choosing the sync primitive. Python 3.11 is refused through the capability check, but no real 3.11 run exists. SQLite's silent `F_FULLFSYNC` fallback comes from source reading and was not probed.
- **Durability of the venue.** Device flush honesty, venue durability and isolation of the journal from same-uid Runs are not qualified.
- **Size.** About 60-90 lines could be folded: predicates duplicated across modules, `_genesis_uuid_conflicts`, and one-use helpers.
