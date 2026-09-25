# 18d3b implementation plan: verified negative scan

Status: proposed local source plan, 2026-09-25. Baseline: `bf3c141`.
Design: `design-18d3b-no-launch-scan.md`.

1. Add real stopped-image tests in `tests/test_reservation_claim_journal.py`
   for no-claim, intent-only and confirmed-claim journal histories paired
   with a v1 Receiver/`unknown` ledger. All outcomes hold. Add journal
   one-commit lag, WAL absence, corrupt anchor, ledger WAL absence and
   held/corrupt ledger cases. Test malformed target before file access,
   an invalid bridge conversion, and synthetic altered-view shape as closed
   holds. Assert the complete scanner reason set, no permit fields and
   verify-only file read-back. Keep pure synthetic bridge tests separate.
2. Implement a small `grafana_jsm_sandbox/reservation_scan.py` I/O shell.
   Validate the target ID before file access, call the two view APIs in
   order, require the observable `unknown`/empty negative ledger shape,
   and convert only verified replayed journal claims into 18d1 dataclasses.
   Map `ledger_event_id` to the bridge confirmation's `event_id`; drop claim
   fields that are not part of the bridge. Return a frozen all-hold
   `ScanAssessment`, mapping `BridgeError` and unexpected comparator output
   to closed hold reasons; do not change the pure comparator, stores,
   reducers, or application callers. Run focused tests and Ruff.
3. Document the shell and its stopped-image/non-atomic boundary in
   `docs/accounting-ledger.md` and `docs/recovery-journal.md`. Record
   independent Standards and Spec source reviews; fix concrete findings.
   Run the guarded local store/journal/bridge block, static checks and the
   full suite with demo flags unset before a local commit. Update tickets
   37/38 as open and record hashes and protected dirty read-back.

If real v1 SQLite can unexpectedly yield a positive reservation, or if a
view leaks facts from an unverified image, stop this scanner unit and
re-review the underlying store format before any further source work.
