# Unit 15a recovery journal records, source and store outcome

2026-09-23. PASS for the first part (15a) of the fifteenth separately authorized
local application unit, baseline `6a3ecc2`. [validation-15a.json](validation-15a.json)
records the final verdict and evidence. The work is local only: nothing was
pushed and no planning ticket was closed.

## What the unit adds

The lower layers of the ticket-37 Receiver-owned recovery journal ([docs](../../../../docs/recovery-journal.md)). They are not wired into the Receiver.

**`journal_source`.** The sanitized source record holds only digests, Fingerprints, statuses, canonical numeric values sorted by refId, `starts_at`, `truncated_alerts` and fixed provenance, all within closed grammars. The dedupe key compares numbers by value.

**`journal_records`.** The 15-key canonical record envelope covers five record types. `record_digest` is taken over the exact body bytes and chains each record to its predecessor, and `content_digest` supports exact-retry detection. Stored bytes are verified raw-byte digest first, then a strict parse, the chain link and the columns, and only then canonical re-encoding and typed validation. Every failure has a fixed code with no chained context.

**`journal_store`:**
- **File layout.** One SQLite database in WAL mode with `synchronous=FULL` and `fullfsync`, append-only triggers and an exact, compared DDL. An 8 KiB two-slot anchor file sits outside SQLite. Files are 0600 in a 0700 directory, owned by the effective uid, and refused if symlinked or hard-linked.
- **Single writer and runtime gates.** The store holds an exclusive lock. It refuses URI-reserved characters in the directory path, and requires Python 3.12 or newer and SQLite 3.37 or newer.
- **Append.** An append commits, then writes and fully syncs the anchor, with no fallback. Any write or sync failure latches the store.
- **No evidence destroyed.** No connection checkpoints on close, and a database file shorter than one page is reported without connecting, so opening a damaged journal destroys no evidence.
- **Hold classification.** Verified physical failures are recovery findings that the anchor can store durably; the writer then refuses any hold-free slot. Transient and newer-format failures are process findings that are never persisted.

Commit framing, replay and the admission transaction are unit 15b.

## Review

- A design panel of three designs, two judges, a synthesizer and a critic (15 issues) produced the plan. The unit was split per the plan's own size rule.
- Four Opus lens reviewers confirmed 20 items (3 high), each reproduced with probes. An Opus fixer fixed all 20 and verified each new test against the pre-fix sources.
- Root fixed two residual SQLite-error escapes. A gap agent closed 8 test gaps and killed 15 mutants.
- A fresh reviewer bound the hashes. It returned FAIL on one blocking test gap: no test read back the durability pragmas. It found no source defect. Root applied four small source hardenings and five doc corrections. A second gap agent added the settings read-back and nine other isolating tests, and killed 20 mutants. The same reviewer then re-verified and passed the result. Root closed its remaining nits ([review](review-15a.md)).

## Validation

- Unit tests: **299 passed, 2 skipped** in the three 15a files, over repeated runs. The two skips are the Linux sync-primitive variants, which are skipped on darwin.
- [Focused suite](focused-tests-15a.txt): **476 passed, 2 skipped**. It covers the three journal files, `forwarder_json`, the receiver and the replay.
- [Full suite](full-suite-15a.txt): **3799 passed, 38 skipped in 202.25s**, exit 0 (the baseline was 3500 passed, 36 skipped). The run is `pytest -q` with `--ignore` for the four untracked, in-progress 15b test files (`test_journal_reducer.py`, `test_recovery_journal.py`, `test_recovery_journal_crash.py`, `test_recovery_journal_adversarial.py`), whose modules are not part of this commit.
- Ruff (including line length), compile and `git diff --check` pass. No existing module, test, document or `pyproject.toml` changed.

## Not qualified

- the reducer, admission transaction, replay, restart recovery and snapshot (15b);
- Receiver integration, raw Notification ingress, Run, effect, accounting, operator actions, reset, retention and reconstruction;
- device flush honesty, venue durability, Linux behavior (the local suite runs on macOS; the Linux sync primitive is only selected, not exercised), and isolation of the journal from Runs;
- detection of a consistent rollback of all journal files, or of a same-uid process writing a valid anchor;
- ratification of the proposed limits, field names and semantics that freeze into v1 records.

## Not performed and next

No provider, tenant or native call was made. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

Next is unit 15b: the pure reducer, the journal shell with the admission transaction, and the crash-image and adversarial suites. Ticket 37 remains open.
