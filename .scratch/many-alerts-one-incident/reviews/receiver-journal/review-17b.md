# Unit 17b journaled front door: independent review

2026-09-24. Baseline `c3e4f3a`; legacy identity baseline `b931610`. Local
source, filesystem/socket and synthetic failure evidence only. This continues
the Claude implementation handed off during review; it is not a new provider
or native-client execution attempt.

## Inherited implementation and first review

The existing unit-17 design panel chose an opt-in admission-only front door,
with 17a committed first. 17b supplied three new modules and five new test
files. Its inherited focused result was 119 passed, 1 failed, 1 skipped;
the failure was an exact import-set test contradicting the plan's allowlist.
The first identity lens had five further gaps, all closed here.

Root used diagnosis/TDD for reproduced findings and the code-review skill's
independent Standards and Spec passes. The reviewers read the plan, current
source and tests; mutations ran in physical scratch copies outside the repo.
Every new production finding received a failing regression before repair.

| Finding | Resolution and evidence |
| --- | --- |
| Allowlist required unused imports | Subset checks; no unused imports added |
| Environment and function-local import gaps | Aliased from-imports and package-member imports checked; nine old-test survivors fail the new checks |
| OS process creation not pinned | Admission-only tests reject OS fork/exec/spawn paths and aliases |
| Refused-start port check was conditional and vacuous | In-process failed startup proves the captured bound socket is closed; CLI asserts no listening line |
| Missing no-Run startup notice | Explicit flushed admission-only and restart-hold lines; regression first failed |
| Short writes returned success | Partial/zero write latches, retains temp, and performs no sync/rename/retry |
| Close errors escaped unlatching | One close attempt, fixed-code translation and sticky write-failure latch |
| FIFO entry blocked before custody check | Nonblocking open, then regular-file validation; store and survey refuse without external writer |
| No-deletion scan omitted two modules | All three modules and imported aliases checked; four deletion mutations killed |
| Unread wrong-route body poisoned next request | Close without draining on wrong-route POST or GET with body framing |
| Response overrode Connection: close | Preserve stdlib persistence decision in all response paths |
| Exception type was lost outside except | Capture only type name inside except, log after slot release |
| Serving CLI resolved away symlink custody | Original path reaches constructor custody check; printed paths remain resolved |
| O8 lacked serving/create-hint test | Inspect missing journal exits 4; serving uninitialized journal exits 1 with setup hint |

The separate Standards sweep tried seven mutations. Existing relevant tests
killed three (health ignoring spool latch, premature 202, inconsistent spool
exit 0). Four survived and gained proved regressions: one deadline per
connection rather than request, leaked connection slot after thread-start
failure, leaked in-flight semaphore after an exception, and syncing S before
its children exist. Each regression passes current source and fails its mutant.

## Contract reconciliation

The plan's appended 17b reconciliation records every deviation: three explicit
journal full-sync calls plus SQLite's own synchronization; command-specific
JSON refusal keys; spool existing-path code; Python 3.13's ignored no-colon
header; flushed output; front-door unrecorded counters; safe HTTP persistence;
and reviewed size. The 17a modules and all pre-existing tests/goldens are
unchanged. No implicit create, deletion, Run dispatch, retention, online
operator channel or credential path was added.

## Fresh final hash-bound review

A fresh read-only reviewer hashed all three sources, all five tests, docs and
plan before reading them line by line. It ran its own scratch mutations and
checked documentation against source. Its initial findings were:

1. Operator create resolved an existing dangling symlink and created its
   target. Preserve the original path; the new CLI regression first failed.
2. Crash tests combined select with buffered readline and missed startup
   lines already buffered in userspace. A two-line pipe probe reproduced it;
   four cases failed in root's first broad run. Crash and operator tests now
   share the bounded unbuffered reader.
3. Removing unrecorded-refusal counting survived 48 HTTP tests. New 400/422/413
   cases assert class/body, count, fixed logged code and unchanged journal/spool.
4. H7 lacked its specified Darwin full-body 503 case. Added; H18 now separates
   portable headers-only and Darwin full-body cases with Retry-After checks.
5. H17 retried before observing the original admission. It now drops the reply
   at the post-commit receipt seam and gates the retry on that observation.

The final reviewer initially killed three of four own mutants (digest
verification, mismatched-orphan exit, spool-latched health). The fourth was
unrecorded counting; it is rechecked after the added tests in the addendum.
All five findings are repaired. This includes an actual test-harness failure,
not a claim that the initial broad run passed. The first full suite passed
4,938 tests with 39 skips, but collected before the final extra case existed.
Final collection listed 4,978 cases, so root reran the entire full suite on
the frozen hash-bound tree rather than using that earlier green result.

## Final reviewer addendum

# Unit 17b final review addendum

2026-09-24. **ACCEPTED for this local source-and-synthetic unit, subject to the root-owned final gates. No remaining actionable finding from this review.** This supersedes the initial NOT YET ACCEPTED verdict. It does not qualify provider/tenant/native execution, Grafana retries, Linux no-read responses, device power loss, deployment, Run dispatch or publication.

All five findings are closed after read-back of the changes:

- F17b-1: operator CLI now preserves the supplied Path through creation. The new repository test and the independent reviewer probe both refuse a dangling symlink and leave its target absent.
- F17b-2: crash tests now reuse the operator tests' unbuffered deadline reader. The independent two-line pipe burst passes with that reader; all six real-process crash tests pass.
- F17b-3: new invalid-JSON, member-limit and oversize tests pin the original 400/422/413 response, unchanged journal head/spool and per-code unrecorded counter on a failed refusal write. Reapplying the exact surviving M4 mutant makes all three cases fail. `M4_repaired_killed.txt`: 3 failed in 4.07 s, NON_LOOPBACK_ATTEMPTS []. The mutant was restored and its source hash checked afterwards.
- F17b-4: Darwin-only H7 now sends the complete firing fixture and pins 503 journal_held plus Retry-After: 10. H18 separately covers headers-only and Darwin full-body opening refusals.
- F17b-5: H17 now shuts down the socket from the receipt seam after admission and uses an Event before the retry. It no longer depends on which of two handler threads wins admission.

Independent repaired baseline, outside the repository: all five new test files plus two reviewer probes passed, **155 passed, 1 skipped in 65.07 s**, ending NON_LOOPBACK_ATTEMPTS []. See `repaired-baseline.txt`. The repository's five files account for 153 passed, 1 skipped; the extra two passes are the independent symlink and buffered-reader reproductions. The skip is the Linux full-sync branch on Darwin.

The final reconciliation additions were read and accepted. `hashes-final.json` binds the exact current source, tests, documentation and plan. Source/tests/docs remained byte-identical throughout the repaired baseline and mutation recheck; the plan only gained the reviewed reconciliation text. `identity.json` independently confirms all four protected dirty hashes unchanged, the tracked legacy diff against b931610 empty, and the 17a modules/existing tests diff against c3e4f3a empty. Full-suite and broad focused gates are still root-owned, not claimed complete here.

The source totals 1,436 lines and the size deviation remains accepted for the reasons in the initial review. The documentation's relevant 17b sentences were checked against the final source and reconciled plan; no additional correction is required.

## Final SHA-256 identities

- `grafana_jsm_sandbox/journal_spool.py`: `aeb915736edeb3545b880c5d4bcde0db1b91946c5cd927c4f92c0168555e12ac`
- `grafana_jsm_sandbox/journaled_receiver.py`: `070209fdfa1bda30940f077e62d7a2de997c25feb25b76f0db54e9354a732699`
- `grafana_jsm_sandbox/journal_operator.py`: `c51a5116a961841c4d2a6010f6ae52e58789f1d6ef3c2ff6d819cfe5016c008f`
- `tests/test_journal_spool.py`: `9ddd1656664f1b9f0c3bfcfe056e15c892775407916d5a41bcc589ea106b5550`
- `tests/test_journaled_receiver.py`: `1a4e533473313c49264bb5c3f4b4d8cfe0717b0e2bdb6c41fcd6adfcfbd9b90d`
- `tests/test_journal_operator.py`: `5652fbe98e9fce1c644fba624c13b22b66e17d7629831b49f2f9a1e44dad2752`
- `tests/test_journaled_receiver_crash.py`: `68a1b21f4c10b44ee54dcbef45a7e0d3879da5cb134e23024d5b514ed090ef13`
- `tests/test_journaled_legacy_identity.py`: `0afb3ed884dc4bedf34c4a8780d2864bceae893dab778ef73dbf3ac75f18fce0`
- `docs/recovery-journal.md`: `f1a022103afa2ff48644360996b7565660cbaa9c36612763bf3c017ae5a9f00a`
- `.scratch/many-alerts-one-incident/reviews/receiver-journal/implementation-plan.md`: `6e29d944474dc1f72b59ec6d8061fde8064eff2e40f4e4be6293872873b1a809`


## Final root gates

- Focused: **1645 passed, 30 skipped**, 348.21 s;
  `NON_LOOPBACK_ATTEMPTS []`.
- Full suite: **4939 passed, 39 skipped**, 372.18 s, exit 0.
- Ruff, source E501, whitespace, frozen-source/test identity and protected
  hashes pass. No fixed-port literal or `.coverage` artifact.
- Source is 1,436 lines: spool 434, front door 835, operator 167. Both independent
  review passes accept the recorded deviation; the prior 17a/17b split remains.

The focused wrapper prevents non-loopback connects in its interpreter;
reviewers also inspected child scripts for explicit loopback-only listeners.
The full default suite disables live opt-in flags. Neither provides device
power-loss, Linux no-read, real Grafana retry, venue, provider or model evidence.
