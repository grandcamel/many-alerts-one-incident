# 18d3a implementation plan: verify-only store views

Status: accepted local source plan, 2026-09-25. Baseline: `92aace8`.
Design: `design-18d3a-verified-views.md`. This multi-file source change is
sequenced so each existing inspection contract is checked before the next
store changes. The public report schemas and Receiver reservation refusal
remain unchanged.

1. Add tests for journal claim view first. Compare its facts and digest to a
   fully replayed mixed v1/v2 projection. Exercise no-claim, intent-only,
   confirmed, one-commit anchor lag, WAL absence, corruption, held image,
   detectable `os.close` failure,
   and verify-only file/anchor read-back. Held/unverified views must have no
   facts; existing `inspect_recovery_journal` report remains exact.
2. Refactor `recovery_journal.py`'s private verify-only replay path just enough
   to share custody and replay between the old report and new view. Add a
   `journal_store.py` locked WAL-presence option for the new view, with a
   post-open WAL observation guard and a race-injection regression. Keep the
   current report shape, error classification, lock-file exception and
   closed-handle behavior. Translate detectable close failure only in the
   new view and drop every partial fact. Run focused journal tests and Ruff
   before ledger edits.
3. Add tests for the ledger reservation view using the current v1
   Receiver-origin SQLite image. A ready view must carry exact anchored
   identity/head, population=`unknown` and an empty reservation tuple.
   Verify fixture genesis and crafted reservation rows are rejected, along
   with WAL absence, tail lag, anchor/custody corruption, held state and
   checked close failure. Preserve the existing fixed-code held/unverified
   classification for corruption and custody. No ready positive fact is possible in
   this store format.
4. Refactor `accounting_store.py`'s private inspection path to share its
   query-only verification with the new immutable view. Preserve the existing
   `Inspection` result and all v1 store semantics. Run focused accounting
   tests and Ruff before updating `docs/accounting-ledger.md` and
   `docs/recovery-journal.md`.
5. Review Standards and Spec independently. Run guarded combined store tests,
   static checks, then the full suite with demo flags unset before a local
   code commit. Record source hashes, protected dirty read-back and NOT RUN
   boundaries. Tickets 37 and 38 stay open.

If a view cannot share the exact existing inspect custody semantics without
changing those reports or acknowledging storage, split that view into a
separate local unit and re-review the plan. Do not fill a failed view from an
unchecked raw row, a returned receipt or a synthetic marker.
