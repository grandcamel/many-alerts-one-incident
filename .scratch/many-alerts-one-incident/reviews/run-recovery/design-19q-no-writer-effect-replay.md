# 19q: no-writer effect-intent and receipt-claim replay

Status: proposed local source design, 2026-09-25. Fixed point: `4900467`.
Authority: accepted ADRs 0011–0013, reviewed 19h/19k effect and permit
contracts, ticket 37, and the current journal/Forwarder route and receipt
catalogs. This unit supplies no authorization endpoint, effect writer,
permit, provider call, OPS write or Report classification.

## Present boundary

The journal now replays launch and spawn/release **claims** only. There is no
application writer, protected stable witness, verified release, current
reservation, authenticated grant or logical-operation adapter. The Forwarder
permits no mutation route; `PermitBook` is isolated and accepts untrusted
bindings. A no-writer effect record must remain unqualified even if its
canonical bytes and journal chain verify. It cannot show L1 consumption,
L2 passage, zero bytes, a trusted Forwarder receipt or OPS read-back.

## Proposed private record family

Register `(effect_intent, 3)` as ordinary and `(effect_receipt, 3)` as
recovery. Both have actor `receiver`, one-record commits, exact keys and
canonical bounded values. Their per-type body ceilings are 4,096 and 2,048
bytes, respectively; each adds the current 384-byte record overhead. The
current single-Run projection admits at most 64 distinct logical operations
and one receipt claim per intent. This is a local bound for source/replay,
not an accepted Run call allowance. Exhaustion refuses new ordinary intent
with a fixed `capacity_effect_claims` result and without dropping prior
obligations; replay still rejects a stored 65th claim. The source does not escrow capacity for
the future writer: a writer would need 2,432 recovery bytes reserved per
outstanding intent plus separate terminal, containment and accounting
reconciliation room before any effect authorization.

`effect_intent` binds one Receiver-resolved UUID operation ID and one UUID
event ID to the exact journal/run/attempt/reservation identities and
`release_observation` event/digest; Receiver boot and Forwarder generation;
one current claimed service grant; fixed catalog service and route ID;
bounded flight and Forwarder receipt IDs; canonical prepared-request digest,
sanitized target digest and grant scope digest; same-boot monotonic observation
and deadline no later than work/grant expiry; immediate journal head; and a
tagged self-digest. It carries no body, target string, account identity,
credential, prompt or raw endpoint. Route/catalog matching checks only
identity and service, never route readiness. The operation ID is a
caller-supplied **claim** in this unit, not proof that the Receiver resolved
it from admitted state. A second intent with the same operation ID is
rejected, including a changed request, grant or target. A no-op is a
separate future adjudicated record, not an absent effect intent.
The pure reducer keeps a pinned v3 route-ID/service snapshot rather than
importing the Forwarder route module; a parity test checks it against the
current catalog. Future catalog changes need a separately versioned replay
rule. Catalog parity is identity checking, not route-readiness evidence.

`effect_receipt` binds the exact operation/intent event and digest, Run,
attempt, grant, flight, Forwarder receipt ID, current head, same-boot
observation, a bounded digest of a claimed finalized Forwarder receipt and
the closed claimed dispatch state/reason vocabulary. It does not embed the
Forwarder snapshot or classify the receipt as trusted. The source validates
only syntax, state/reason compatibility and predecessor identity. In
particular, a claimed `NOT_DISPATCHED` is not proof of pre-L1 no-connect, a
claimed `FAILED` is not proof of post-L1 zero bytes, and a claimed
`TRANSPORT_CONFIRMED` is not OPS confirmation. A future reader must compare
an independently authenticated, finalized Forwarder receipt plus L1/L2 and
first-byte evidence before using those distinctions. A duplicate receipt
claim conflicts; a missing receipt leaves an unmatched intent. No state
promotes either prefix to a successful external effect.

## Replay and capacity

Pure planning requires an exact current journal head, same original Run
members, no new dispatch/Run hold, same boot, a preceding claimed release
observation and a still-open work/grant deadline before an intent. This is
only a replay consistency gate. The receipt claim may append after a new
hold or elapsed deadline to preserve historical evidence, provided it binds
one existing intent and the same boot; it never removes the hold or permits
another operation. A restart invalidates both pre-dispatch eligibility and
same-boot receipt append until a separate recovery observation/adjudication
contract is reviewed. Replay replans each record and compares exact
canonical body, digest, IDs, head, phase and charge. A forged recomputed
record, duplicate operation/receipt, changed flight/request/target or
cross-Run service grant fails closed.

Stopped and live inspection report a separately tagged count/digest of
claimed intents and receipts plus an unmatched-intent count, always with
`effects_unqualified`. The present v1 state digest formula and existing
record ceilings remain unchanged. Future writer capacity preflight must
account for the entire 64-operation ordinary ceiling and all possible
recovery receipts along with other recovery obligations; the no-writer
source cannot turn free bytes into a durable reserve. Test maximal legal
body shapes, 64/65 operations, ordinary/recovery edges, duplicate and
unmatched receipts, hostile recomputed records, all crash prefixes,
real-store mixed reopen and older-decoder refusal.

Production effect intent, permit and receipt handling remain gated by an
independently verified accounting reservation, protected worker/release
evidence, current route-specific grants, authenticated Receiver-owned
authorization endpoint, native logical-operation binding, trusted
Forwarder receipt/zero-byte evidence, OPS read-back, venue and tenant
qualification. Native, provider, paid, tenant, venue and human acceptance
are NOT RUN.
