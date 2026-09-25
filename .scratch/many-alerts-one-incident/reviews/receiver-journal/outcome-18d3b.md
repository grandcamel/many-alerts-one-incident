# Unit 18d3b verified negative reservation scan

Status: **PASS_LOCAL_NEGATIVE_SCAN**, 2026-09-25. Fixed point: `972332c`.

The new `reservation_scan.scan_reservation` shell reads the 18d3a journal
claim and v1 accounting views for one target intent. It accepts no
caller-supplied projection, ledger receipt or `read_back` assertion, and
returns a frozen all-hold result with a closed reason set. Real stopped
SQLite images cover no claim, intent-only and journal-confirmed histories;
the current Receiver/`unknown` ledger has no reservation row, so each is
held. The scanner checks the journal claim's `ledger_event_id` as a claimed
comparison field, never as an authenticated accounting receipt. It has no
writer, application caller, permit or launch token.

The [design](design-18d3b-no-launch-scan.md),
[plan](implementation-plan-18d3b.md), [plan review](review-18d3b-plan.md),
[source review](review-18d3b-source.md) and
[validation record](validation-18d3b.json) bind this local checkpoint.
Independent Standards and Spec source re-reviews pass after a documentation
precision edit, a persisted held-ledger regression and an exact reason-set
assertion. The final focused block passed **350**, skipped **2**; changed-file
Ruff and whitespace checks passed. The full local suite passed **5274**,
skipped **39**, in 374.14 seconds with demo flags unset.

The two store inspections are sequential, not an atomic snapshot. This
scanner cannot observe a positive durable reservation in the current v1
ledger, and cannot qualify spend or dispatch. Production reservation still
requires authoritative opening history, provider line identity/coverage/lag,
defensible U, continuity witness and archive/repair policy. Native,
provider, tenant, venue, paid, power-loss and human Report adjudication are
**NOT RUN**. Tickets 37 and 38 stay open. No push, publication, C2 retry or
provider/model call occurred.
