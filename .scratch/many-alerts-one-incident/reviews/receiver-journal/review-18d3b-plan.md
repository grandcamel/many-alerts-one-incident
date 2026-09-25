# 18d3b design and plan review

Status: **ACCEPT_LOCAL_NEGATIVE_SCAN_PLAN**, 2026-09-25. Fixed point:
`bf3c141`. Independent read-only Standards and Spec reviewers checked the
design and file-by-file plan against the 18d1 comparator, 18d3a views,
accepted ADR 0013 and open tickets 37/38. They made no edits or test runs.

Both first reviews identified that the scanner introduced new reasons while
calling them the 18d1 vocabulary, and that the ledger view has no format
discriminator. The revised design defines its own frozen, closed all-hold
result and limits `ledger_unsupported` to an observable changed view shape;
any future same-shaped store format needs paired scanner review. It maps
`BridgeError` and unexpected comparator output to fixed holds, and maps a
journal claim's `ledger_event_id` to the bridge confirmation's `event_id`
while dropping the distinct journal confirmation ID and commit metadata.
The Standards reviewer also caught one sentence that incorrectly counted
`scan_invariant` as a comparator reason; it was corrected. The reviewers
found no remaining plan blocker after these changes.

This is a documentation-only checkpoint. Source, focused and full tests are
**NOT RUN** for this commit. Positive durable reservation, production
reserve, dispatch permit, native/provider/tenant/venue/paid execution,
power-loss durability and human adjudication remain **NOT RUN**.
