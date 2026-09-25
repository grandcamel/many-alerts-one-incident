# Unit 19i2 no-writer v3 confirmation outcome

Status: **PASS_LOCAL_NO_WRITER**, 2026-09-25. Fixed point: `abe75ba`.

The private v3 `reservation_confirmation` record links one v3 initial
intent to a claimed ledger event and retains exact IDs/digests in replay.
It uses recovery capacity and shares the aggregate 256-confirmation cap
with v2. Both v2 and v3 planners reject reuse of a claimed ledger event ID
or ledger UUID/generation/sequence in either version order. V2-only
record bytes and digest, and the v3 initial-intent digest, remain unchanged.
A journal confirmation is unverified until an independently verified
ledger counterpart matches; no such positive counterpart is supplied here.

Snapshot, verify-only inspection and the stopped claim view expose v3
confirmation count/digest as outstanding unverified evidence. The stopped
negative scanner returns a hold-only `v3_unsupported` for a verified target
v3 claim instead of falsely reporting a missing intent. It checks the
journal and ledger images first and retains existing unverified/unsupported
precedence. The [implementation plan](implementation-plan-19i2-confirmation.md)
and independent Standards/Spec source reviews pass. Focused journal and
scanner tests: **86 passed**; changed-file Ruff passes. The full local suite:
**5,480 passed, 39 skipped** in 390.52s. A real SQLite/WAL reopen test
checks the v3 claim and a simulated older decoder's process hold.

Cross-version duplicate tests use synthetic pure projections because current
valid history cannot contain both v2 and v3 intents before a later reviewed
disposition transition. There is no v3 application writer, authenticated
ledger match, positive reservation, Run, grant, process or permit. The v1
Receiver ledger still has `population=unknown` and rejects reservations;
the scanner cannot promote v3 claims. Provider, native, tenant, paid,
venue, deployment, power-loss and human adjudication are **NOT RUN**.
Tickets 37 and 38 remain open.
