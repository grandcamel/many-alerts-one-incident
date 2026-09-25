# 19r implementation plan: no-writer supervision-action replay

Fixed point: `f8682ad`. Follow the reviewed
[design](design-19r-no-writer-supervision-actions.md). This is a multi-file
source change; keep all production callbacks and action writers absent.

1. Add private v3 record validators and fixed size/class assignments in
   `journal_records.py`. Preserve v1/v2 codecs and existing state digests.
   Enforce exact keys, kinds, phases, IDs, same-boot monotonic times and
   claimed result codes. Do not infer early-stop trigger or action due time.
   Verify the maximal canonical bodies fit the proposed 4,096/2,048 caps.
2. Add immutable action claims, projection maps, pure planners, replay
   verification and tagged inspection digests in `journal_reducer.py`.
   Limit one revoke per replayed grant and one of each signal; match the
   attestation witness locator/digest instead of accepting a caller PID.
   Permit cleanup despite a dispatch hold. Bind the three release phases,
   allow late result claims, and make the first action intent permanently
   reject later release-intent and effect-intent claims. Preserve historical
   release-observation append against a prior release intent.
3. Expose only `supervision_actions_unqualified` count/digest/unmatched
   inspection in `recovery_journal.py`; add no public writer or callback.
4. Add focused tests for syntactically ordered grants/signals, release-unknown and
   pre-release cleanup, post-hold/late results, absorbing stop, 7/8 count
   edge, maximal body, forged recomputed predecessor, mixed-version real
   store reopen, stopped inspection and old-decoder refusal. Assert that an
   early action claim never proves 19c due-time compliance. Test no
   production method appears. Update the recovery-journal documentation,
   ticket 37 and a truthful local outcome.
5. Run focused tests and changed-file Ruff, obtain independent Standards
   and Spec source reviews, then run the full test suite. Fix failures and
   rerun the full suite after any code change. Verify protected dirty-file
   hashes and panel manifest, stage named 19r paths only, check staged diff
   and commit locally. No push, provider/native run or tenant operation.

Stop source implementation if the current record/projection machinery
cannot preserve the absorbing stop and historical observation together, or
if recovery-capacity arithmetic cannot be bounded without a writer. In
that case record the exact source gap and leave ticket 37 open.
