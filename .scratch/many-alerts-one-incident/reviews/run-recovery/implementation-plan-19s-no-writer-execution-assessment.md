# 19s implementation plan: unqualified execution claims

Fixed point `af2bb62`; design review pending final reason-code reconciliation.
This is a multi-file local source change with no runtime writer or positive
launch/effect/accounting authority.

1. Extend the private v3 record codec for one process observation, one terminal
   summary and one assessment. Use closed fields, exact types, tagged digests,
   4,096/4,096/2,048-byte ceilings and recovery class only. Verify old schema
   rejection and canonical round trip before proceeding.
2. Add a pure `journal_execution_adapter.py` for classifier calls and fixed
   exception conversion; update the reducer's exact import contract to admit
   that module while retaining the six-import `journal_records` contract and
   its no-`try` reducer invariant. Add pure planners and replay claims in `journal_reducer.py`. Bind the launch,
   same boot, exact predecessor and observation order; reject a no-process
   assertion after spawn attestation; call the existing pure classifier for
   validation and derivation. Keep results unqualified and never clear holds.
   Run focused replay/forgery tests before proceeding.
3. Add read-only live/stopped inspection summaries in `recovery_journal.py`
   with claim digests and unqualified labels. No writer method. Check output
   compatibility with existing inspection tests.
4. Add focused process/terminal/assessment, missing/duplicate/invalid,
   precedence, capacity, late history, restart, and old-decoder tests; update
   local outcome documentation. Seek independent Standards and Spec source
   review, run Ruff, `git diff --check`, then the full suite. Commit only named
   19s files after verifying the protected preexisting dirty paths and panel
   manifest are unchanged.

Native/provider, tenant, venue, paid, power-loss and human acceptance remain
NOT RUN. The ticket and positive guarded launcher remain externally gated.
