# Unit 17a journal extensions for the front door: independent review

## Design and review history

Unit 17 is the Receiver integration of the recovery journal, together with
operator resume. The user chose an opt-in journal: the legacy demo path and
every existing test stay unchanged.

**Design panel.** Three Opus designs were judged by two Opus judges.
- **Admission-only** won both judges (49 and 48 of 60) and is the base. The front door records admissions and refusals and starts no Run.
- Operator-first scored 42 and 43; minimal-dispatch scored 31 and 30.

An Opus synthesizer wrote the [plan](implementation-plan.md). An Opus critic
raised 16 issues, 0 of them high and 7 medium, and all were resolved in
revision 2. The panel's designs, judgments and probes are in `panel/`, which is
not committed.

**Split.** Earlier units' size estimates ran about 2x low, so root split the
unit up front (plan, "Root reconciliation"):
- **17a** (this record): the journal-level pieces in `journal_records.py`, `journal_reducer.py` and `recovery_journal.py`, with plan cases A1-A12 and K1-K14 and a second golden journal.
- **17b**: the body spool, the journaled HTTP front door and the operator CLI.

The implementer's diff added 931 source lines against the plan's 625-line
trigger, which confirmed the split. 17a is committed on its own, with a full
suite that contains no 17b file.

**Orchestration.** This unit ran as two Workflows:
- `wf_bf03fcc5-d45`: 75 agents, about 6.3 hours;
- `wf_987bd275-b44`: 2 agents.

| Step | Result |
| --- | --- |
| Implementer A (Sonnet) | the three module changes and A1-A12; 1,187 focused tests passed; no bugs reported |
| T1 drafter and finalizer (Sonnet) | K1-K14 with K3b and K11b, written from the plan's signatures, then reconciled with the source. The draft's 12 failures were all test-construction errors, so no source bug. The finalizer built the golden and pinned its digests |
| Round 1: five Opus lenses (contract, v1 compatibility, durability, fail-closed, test adequacy) | 44 raw findings, 21 merged, 20 confirmed by Sonnet verifiers |
| Fix round 1 (Opus) | 20 applied: four source fixes, the rest tests |
| Round 2: the same lenses | 20 raw, 14 merged, 14 confirmed |
| Fix round 2 (Opus) | 14 applied: two source fixes, the rest tests |
| Round 3: the same lenses | 18 raw, 15 merged, 15 confirmed, all test gaps with no source defect; left to the residue step |
| Mutation sweep (Opus) | 117 mutants: 94 killed, 23 survived, 22 of them important |
| Gap agent (Sonnet) | all 22 important survivors killed, each proven against its mutant |
| Residue gap agent and independent checker (Sonnet) | the 9 round-3 items the gap tests did not already cover, plus one root item (the golden comparator), closed. Each was re-proven in a separate scratch copy |

**Source fixes from review:**
- **F1-1.** The strict refusal-summary checker accepted a bool `members_omitted`, which `refusal_to_json` refuses. It now requires an exact int.
- **F1-2.** Inspect's report was not JSON-serializable once a refusal existed, because it held the record's frozen mapping. Summaries are now plain dicts in `refusal_to_json`'s shape.
- **F1-5.** Inspect's pre-check let a raw `OSError` escape with the path. Inspect now applies the store's own directory custody rule first (a private import of `journal_store._check_directory`), and maps any other stat failure to `journal_path_invalid`. Inspect and open now refuse the same bad directories with the same codes.
- **F1-18.** Two validator codes now follow the plan's check-order text: every summary violation is `record_field`, and `operator` and `reason` violations are `record_field` rather than `record_id`.
- **F2-1.** Replay now re-checks that a resume's `hold` is `restart_recovery`, so a forged resume cannot clear a capacity hold even if it gets past the validator.
- **F2-7.** A monotonic-clock regression at the resume step now latches `journal_clock_invalid`, as it does in `admit`, instead of `journal_divergence`.

None of them changes any record's bytes, so neither golden was rebuilt.

**Root checks:**
- An independent replay of the new golden gives 14 records in 11 commits, as tabulated in the plan, and reproduces all four pinned digests.
- The docs give the refusal byte coupling with measured numbers. The largest summary the tests could build is 2,718 bytes, and 256 such records charge 936,192 bytes. The 4 KiB check caps the coupling at about 1.3 MiB.

## Final hash-bound source and test review

Reviewer: a fresh independent agent, read-only. At the start it verified these SHA-256 values; the final hashes follow the addendum.

```
5c1d7e7b9a29cd15b84a33242af92824b80027ee49bac82f5c4807afbfb86eb6  grafana_jsm_sandbox/journal_records.py
d10416874e0026ed478bed6719512e8e440a1387e0da0f03210f3a419ff5ae28  grafana_jsm_sandbox/journal_reducer.py
49d841c6b8f5d31fadf39be6157e4f72e45b7f84716e9df5f8174e827e052b87  grafana_jsm_sandbox/recovery_journal.py
729cd9c0e5fb2f3f5012c15dafbf5559777c83cef406ca7cd793bfa436acec32  tests/test_journal_front_door_records.py
3194d2b33f3c52d416d468aa8c1b0832f9e2557551653259a31e4a8c58f87a00  tests/test_recovery_journal_front_door.py
1a193ed4bdd9586677c9f08106b72a5137f895fc34034b69162c9d33015447d1  tests/data/recovery_journal_v1_front_door_golden.jsonl
7b57a8518f3bc977dc0d33d480fd14e3dc97c144bf1328c9d70f9934ed1a5b3c  docs/recovery-journal.md
```

Verdict: **PASS (source and test review)**. It found no functional defect, and no missing test for a core plan rule.

- **v1 compatibility.** A differential probe compared the three modules at `b931610` with the working tree over 60,075 envelopes:
  - both goldens;
  - the full grid of event type × actor × `schema_version`, including bools, strings, floats and `None`;
  - unhashable event types;
  - 40,500 random leaf mutations.

  Across `_validate_envelope`, `open_record`, `decode_record`, `verify_body` and `seal`, there was **no difference for any unit-15 type**. Every difference involved a new type, where the old code answers `record_unsupported`, as intended.
- **Replay and state.** The unit-15 golden replays to the same `state_digest`, `pending_digest` and projection fields under both reducers. Twin journals driven by the old and new shells gave identical snapshots, receipts, errors and rows. The only difference is the restart row's WAL salt.
- **Parity, resume, inspect and custody.** Live/replay parity, the check orders, resume at open, inspect's never-write rules and the null rule all match the plan. Every new error has a fixed code, and no `raise` sits inside an `except` body.
- **Tests.** A1-A12 and K1-K14 exist and assert what the plan says. The golden comparator checks records before c6 whole and masks exactly five leaves after. The only vacuous pattern found was K7's empty row lists for held images.
- **Mutants.** Of 41 reviewer mutants, 37 were killed. The four survivors each got a proposed test.
- **Size.** Accepted, and not blocking. If a split is wanted, the seam is inspect, moved into a `journal_inspect.py` once 17b's operator command calls it.

**Applied before the addendum:**
- **Source (docstrings and comments only):**
  - the `front_door_digest` docstring no longer claims that a refusal or a resume never changes `state_digest`;
  - the `Inspection` docstring states the null rule exactly;
  - the comment above `REFUSAL_OUTCOMES` is corrected;
  - the `_held_journal`, `inspect_recovery_journal` and module docstrings are updated;
  - two constants are now imported from `journal_records` directly.

  No executable line changed.
- **Tests:**
  - a held report's `anchor` and `wal_found` are pinned to the image (kills the reviewer's S18 and S19);
  - a dangling WAL symlink is refused by inspect as by open (S14);
  - `record_refusal` checks held before the summary (S6);
  - the F3-6 test builds the true largest summary, 2,866 bytes, and asserts that 256 such records stay under 1 MiB;
  - K7 compares the DB and WAL bytes of the twins when the open is held;
  - A11's resume round trip also compares `front_door_digest`, the resume fields and the boot fields.
- **Docs:**
  - the byte coupling is restated with the true maximum;
  - the backpressure sentence now excludes the three new codes;
  - two crash-window cells now say "dispatch hold" instead of "held";
  - "touches" is now "writes to";
  - the golden holds two restarts, not one.
- **Plan:** a "17a as built" note records the size, the private `_check_directory` import, the `record_refusal` check order (closed, held, then the summary, as in `admit`), the validator-code and replay fixes, the exports and the byte coupling.

## Addendum re-verification

The same reviewer re-checked the tree after the edits:
- **Hashes.** All eight match the root's list. `journal_store.py` is still identical to `b931610`, and the protected hashes are unchanged.
- **Edits.** Compared with its pre-review copies, the source changes are docstrings, one comment and one import move; no code logic changed. The three new tests are its proposed tests. The F3-6 rewrite asserts exactly 2,866 bytes, which matches the reviewer's own calculation.
- **Docs.** The "under 1 MiB" coupling holds even for 128-byte IDs at maximal positions: 1,035,520 bytes.
- **Mutants.** The four survivors (S6, S14, S18, S19) are now killed, and all 41 reviewer mutants are killed on the final tree.
- **Final gates.**
  - ruff, E501 and `git diff --check` pass, and the legacy-identity diff is empty.
  - The final tree adds 938 source lines: 244, 222 and 472.
  - Focused: 1492 passed, 29 skipped. Full suite: **4786 passed, 38 skipped**.
  - No `.coverage` file.
- **Its focused 14-file run:** 1420 passed, 2 skipped.

Addendum verdict: **PASS**, with nothing left open.

Final hashes of the source, tests and golden:

```
5c1d7e7b9a29cd15b84a33242af92824b80027ee49bac82f5c4807afbfb86eb6  grafana_jsm_sandbox/journal_records.py
3ccd4f661ecbbb95e8d542443bb7274be7b1337c3415764907b2ec2c60b080bc  grafana_jsm_sandbox/journal_reducer.py
9608c5887d4bf32bccec175db7ac62d030632f0054ce1c00a5f76e4591057bff  grafana_jsm_sandbox/recovery_journal.py
856deca4c3ef93a03d32d7e7214212da721d4a8e57c35dff205e99b4320fd79e  tests/test_journal_front_door_records.py
044b9f42e0bfd0cb3e2aec9e984ec2d59adc0f48caff0cd40c677d68294bef1a  tests/test_recovery_journal_front_door.py
1a193ed4bdd9586677c9f08106b72a5137f895fc34034b69162c9d33015447d1  tests/data/recovery_journal_v1_front_door_golden.jsonl
```

## Residual limitations (accepted)

- **Size.** `recovery_journal.py` is 1,098 lines. The split seam, inspect, is left for 17b.
- **Private import.** `recovery_journal.py` imports `journal_store._check_directory`, which keeps `journal_store.py` byte-identical.
- **No front door yet.** No caller exists outside the tests: the spool, the front door and the operator CLI are 17b.
- **Unratified.** The new record types, rules, limits and codes all await ratification.
