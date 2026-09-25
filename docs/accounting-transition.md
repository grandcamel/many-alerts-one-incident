# Accounting transition (local synthetic subset)

`accounting_events` encodes a closed version-1 accounting event with canonical
JSON and an external tagged SHA-256 digest. `accounting_transition` replays a
presented stream from genesis and applies one event against an expected head.
It checks sequence, digest chain, identity, configuration, original New York
week, conservative liability and reservation eligibility using the 18a
accounting policy. Replaying the same event bytes yields the same projection.
An exact individual event retry at the current head leaves state unchanged;
the same event duplicated inside a stream refuses.

The seven event kinds are genesis, journal binding, profile configuration,
lifecycle registration, non-model commitment, reservation creation and sticky
hold setting. A reservation retains U as liability and counts as an attempted
Run in this synthetic history. It can refer to an admitted Notification, but
this module cannot check the journal, intent digest, effect reconciliation or
provider evidence. A new journal binding preserves earlier experiment
liabilities and cannot reuse an older-origin lifecycle.

`receiver` genesis has unknown population and cannot evaluate a reservation.
The `fixture` synthetic-complete marker is solely an offline test assumption;
it never establishes provider coverage, a bounded live U, account identity or
an opening balance. There is no trusted-completeness transition in version 1.
The future durable adapter needs a separately reviewed history-attestation
format and verifier, a current verified storage head, exclusive serialized
re-evaluation, capacity reserved for control and billing repair, and a durable
read-back receipt. The recovery-journal bridge then needs committed intent,
idempotent ledger reservation, committed confirmation and a no-launch scan of
both stores after restart.

The projection is pure memory state. The caller supplies every event, digest,
ID and time. No storage, lock, filesystem sync, provider import, actual cost
settlement, hold clearing, archive, lease or launch operation exists here.
A separate [non-reserving durable ledger](accounting-ledger.md) now stores only
receiver-origin v1 events; it does not change this module's synthetic proof.
A presented valid prefix cannot prove it is the latest durable head. The
8,192-event cap bounds replay input only. The 18a 512-attempt guard counts
full history, but the strict lifetime $50 cap limits this no-settlement subset
first because each model U is at least $3. These are not the ticket-38 active
store capacity or 52-week archive contracts.

Local tests exercise synthetic event integrity and transition rules. Power
loss, concurrent writers, native/client/provider billing, tenant/venue
readiness, paid execution, human Report adjudication and dispatch remain
unverified. Ticket 38's durable reservation seam and Run lifecycle are open.
