# Unit 19i3 stopped negative scanner outcome

Status: **PASS_LOCAL_HOLD_ONLY**, 2026-09-25. Fixed point: `b17c5a4`.

The stopped scanner now carries verified v2 and v3 initial intent and
confirmation claims into the same structural bridge assessment. It first
verifies both independent SQLite/WAL images and requires the Receiver ledger's
current `population=unknown` and empty reservation view. A verified v3 claim
without a ledger counterpart, whether or not it has a journal confirmation,
now returns `missing_ledger` with `hold=True`. The earlier `v3_unsupported`
result in the 19i2 outcome describes that unit's fixed point; this unit
supersedes its current scanner behavior. The reason remains in the closed
vocabulary for older callers.

The [implementation plan](implementation-plan-19i3-negative-scan.md),
independent Standards/Spec source reviews, **77 focused tests**, changed-file
Ruff and diff checks pass. The full local suite passes: **5,481 passed,
39 skipped** in 387.65s. The new
real-store tests cover intent-only and confirmed v3 histories and compare all
journal and ledger file bytes before and after scanning. Existing v2,
unverified and unsupported-image gates remain covered.

This read-only observation is not an atomic cross-store snapshot and cannot
authenticate a ledger reservation, create one, admit Run or issue a dispatch
permit. Opening history, charge-line identity, coverage/lag/finality,
liability U, independent continuity and intended-venue durability remain
external gates. Provider, native, tenant, paid, venue, deployment,
power-loss and human adjudication are **NOT RUN**. Tickets 37 and 38 remain
open.
