# Unit 17a journal extensions for the front door: outcome

2026-09-24. PASS for the first half of the seventeenth separately authorized
local application unit, baseline `b931610`.
[validation-17a.json](validation-17a.json) records the final verdict and
evidence. The work is local only: nothing was pushed and no planning ticket was
closed.

## What the unit adds

Unit 17 integrates the recovery journal with the Receiver, together with
operator resume. The user chose an opt-in journal: the legacy demo path and
every existing test stay unchanged. The [plan](implementation-plan.md) splits
the unit in two. 17a adds the journal-level pieces to `journal_records.py`,
`journal_reducer.py` and `recovery_journal.py`
([docs](../../../../docs/recovery-journal.md#refusal-records)). 17b will add the
body spool, the journaled admission-only HTTP front door and the operator CLI.

- **Refusal records.** `record_refusal(summary)` stores one `ingress_refusal` for each refusal membership.
  - **Summary.** It is the nine-key output of `refusal_to_json`, checked strictly.
  - **Key.** The key leaves out the body digest, so Grafana's re-renders coalesce, while a member turning Resolved gets its own record.
  - **Limits.** A generation holds at most 256 records. 64 of them are reserved for summaries that carry a Resolved member, and every record is charged to the ordinary byte budget.
  - **Outcomes.** `recorded`, `coalesced`, `limit` or `no_room`, counted per boot. A malformed summary latches nothing.
- **Resume at open.** `open_recovery_journal(..., resume=ResumeRequest(token, operator, reason))`.
  - **Checks.** The request is checked before any file is touched. The token, the head digest that inspect verified, is checked before anything is written. A stale token writes nothing to a journal whose WAL exists.
  - **Commits.** A clean open commits its `restart_recovery`, then one `operator_action`. Replay binds that record to the immediately preceding restart, the inspected head and the pending set.
  - **Effect.** It clears only `restart_recovery`. Capacity and durable recovery holds stay, and the next open re-adds `restart_recovery`.
- **Verify-only inspect.** `inspect_recovery_journal(directory)` runs open's verification and replay, but writes nothing except an absent `lock`.
  - **WAL rule.** A WAL-absent journal with a full-size database is reported `unverified` without opening SQLite, because opening could create a WAL.
  - **Report.** It is closed-shape JSON: the verdict, `next_open`, the head, holds, digests, pending entries, recent refusals, the last resume and the resume token. For any verdict other than `ready`, the journal-derived fields are null.
- **Compatibility.**
  - Records are registered by `(event_type, schema_version)`, and each pair has one permitted actor. For the five unit-15 types, the envelope checks accept and reject exactly as before.
  - An older binary meets the new types as the process hold `journal_schema_unsupported`, which is never persisted. This binary treats a `schema_version: 2` record the same way.
  - `state_digest` is unchanged, and a separate `front_door_digest` covers the new state.
- **Golden.** A second golden journal, `tests/data/recovery_journal_v1_front_door_golden.jsonl`, holds 14 records in 11 commits: refusals, two restarts, a resume and admissions before and after. Later units must keep replaying it.

## Review

- **Design.** A panel of three designs, two judges and a synthesizer produced the plan. A critic raised 16 issues, all resolved in revision 2. The admission-only design won both judges.
- **Implementation (Workflow `wf_bf03fcc5-d45`, 75 agents):**
  - A Sonnet implementer and a two-phase Sonnet tester did the implementation.
  - Five Opus lenses covered contract, v1 compatibility, durability, fail-closed behaviour and test adequacy, in three rounds with two Opus fix rounds.
  - There were six source fixes; none changes record bytes.
  - An Opus mutation sweep killed 94 of 117 mutants, and a gap agent killed the 22 important survivors.
- **Residue (`wf_987bd275-b44`).** A residue step closed 10 more test items, each re-proven by an independent checker.
- **Final review.** A fresh reviewer bound the hashes and gave PASS with no functional defect ([review](review-17a.md)).
  - Its differential probe over 60,075 envelopes found no change for any unit-15 type.
  - Root applied its docstring, test, docs and plan items.
  - The same reviewer then re-verified the result in an addendum.
- **Size.** The unit adds 938 source lines against the 625-line split trigger, so 17a is committed on its own. `recovery_journal.py` is now 1,098 lines. The reviewer accepted it; the seam for a later split is inspect.

## Validation

- **New tests:** **343 passed** in the two new files.
- **[Focused suite](focused-tests-17a.txt):** **1492 passed, 29 skipped**. It covers the new files, every journal, ingress and store suite, the `parse_json` string-cap and upstream scans, the receiver, the replay and the container.
- **[Full suite](full-suite-17a.txt):** **4786 passed, 38 skipped in 359.84s**, exit 0. The baseline was 4443 passed, 38 skipped, and no 17b file exists.
- **Static checks:** ruff (including line length) and `git diff --check` pass. The legacy-identity diff against `b931610` is empty: `journal_store.py`, `journal_source.py`, `journal_ingress.py`, the Receiver, replay, spawner, Forwarder, container and project files, and every existing test file are byte-identical.

## Not qualified

- the journaled front door, the body spool and the operator CLI (unit 17b), and any Receiver integration;
- dispatch, Runs, effects, accounting, reset, retention and reconstruction;
- operator actions other than resume at open, and any online operator channel. The token and the `operator` label are not authentication;
- Grafana's handling of refusals, and its resend behaviour;
- ratification of the new record types, rules, limits and codes (U17-P3 to U17-P6, P8 and P16).

## Not performed and next

No provider, tenant or native call was made. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

Next is 17b: the body spool, the journaled admission-only front door and the operator CLI. Ticket 37 remains open.
