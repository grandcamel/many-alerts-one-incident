# Local reservation relation check

`reservation_bridge.assess_bridge` compares sanitized journal intent, ledger
reservation and journal confirmation facts for one intent ID. It requires
canonical UUIDs and digests, exact scalar types, one-to-one attempt and ledger
event identities, a ledger read-back observation, and exact counterpart
correlation. Exact duplicates are idempotent; conflicting duplicates hold.

Every assessment has `hold=True`. An exact triple returns
`matching_unqualified`: it is a structural relation among caller-supplied
facts, not proof that either store was verified or that money can be spent.
Missing, unverified, orphaned and conflicting counterparts have separate
closed reasons. Malformed inputs raise only `bridge_invalid` without echoing
the input.

No application caller uses this module. A later Receiver adapter must derive
facts from independently verified durable journal and ledger histories, append
versioned intent and confirmation records, and test crash ordering. The
Receiver-facing ledger still refuses `reservation_created` while its opening
population is unknown. Provider charge identity and coverage, liability U,
continuity witness, retention, venue/reference readiness and every launch
permit remain outside this relation check.
