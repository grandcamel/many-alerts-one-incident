# 19r: no-writer supervision action claims

Status: proposed local source design, 2026-09-25. Fixed point: `f8682ad`.
Authority: ADR 0012, ticket 37, reviewed 19c/19d/19h/19n contracts and
current v3 Run/launch/spawn/release claim replay. This unit starts no child,
calls no Forwarder, sends no signal and grants no dispatch authority.

## Boundary and purpose

The pure supervision reducer returns proposed actions over caller-supplied
facts. The journal now replays a claimed release but has no durable evidence
that a revoke or signal was attempted. A future writer must append a distinct
pre-action intent before each callback and a distinct result after it. A
crash between those records leaves the action unknown; replay must never
repeat it automatically. These records are **claims** until independently
bound to a guarded child, current Forwarder control session and verified
callback result. They cannot establish stable group identity, Forwarder
quiescence, process absence or a clean Run.

## Closed action family

Introduce private v3 `supervision_action_intent` and
`supervision_action_result`, both one-record recovery commits with exact
keys, canonical values, fixed body ceilings and 384-byte overhead. Each
intent has a fresh UUID event ID and action ID, action kind, target, current
journal head, journal/Run/attempt/boot/generation identity, launch claim
event/digest, same-boot monotonic observation and tagged self-digest. Its
target is one replayed service/grant for `revoke_grant`, or the exact
attestation event/digest and its opaque witness locator/identity digest for
`signal_interrupt`/`signal_kill`. These fields are not a process-group ID
or authenticated handle. A revoke may use `pre_attestation` after launch;
all later phases are also valid for revocation. A future writer must resolve and reverify the live
stable group through its protected registry before any signal. A signal also
binds every earlier grant-revoke intent ID and one exact claimed phase:
`blocked_pre_release` after attestation, `release_unknown` after release
intent but before observation, or `released_observed` after release
observation. The phase binds the latest existing phase event/digest; neither
missing observation nor a claimed phase proves whether the release byte
crossed. No raw command, caller-selected PID, endpoint, output, credential,
signal argument or arbitrary reason is stored.

At most one revoke intent per launch grant, one interrupt and one kill
intent may exist for the single claimed Run. Signal intent requires a prior
revoke intent for every claimed grant; an intent without a result still
counts as attempted for ordering, but never as successful revocation.
Signal claims require a preceding attestation and may occur in any of the
three phases above. Pre-release failure may record grant-revoke and signal
claims, but blocked-child containment cannot be inferred from them. An
interrupt is optional before kill; replay checks only claimed ordering. A
dispatch hold bars new positive authority but never bars cleanup intent or
result journaling. Same-boot ordinary supervision does not initiate a new
signal at or after the hard deadline; later orphan cleanup needs a separate
recovery contract. If a pre-action append fails, a future writer still
attempts bounded best-effort revocation/containment and holds every clean
inference. One result per action ID binds exact intent event/digest, current
head, same boot and bounded fixed outcome code. A result may append after
hold or deadline to preserve history. `requested`/`acknowledged` are
syntactic outcome claims, not trusted callback evidence; signal syscall
success does not prove group absence. Duplicate/conflicting results hold.

There is no durable early-stop request or trigger in the current v3 journal.
Replay can check same-boot monotonic order and the absolute launch hard
deadline, but cannot establish that a revoke, interrupt or kill was due
under 19c after an early stop. No-writer inspection must label trigger and
due-time legitimacy unqualified. A future guarded writer needs an exact
durable stop/trigger transition and must recheck the reducer against that
evidence before asserting policy adherence.

The first cleanup intent is an absorbing stop for positive launch/effect
progression. Replay must reject a later `release_intent` or new
`effect_intent` after any cleanup intent for this launch. A historical
`release_observation` may still append against its prior release intent to
record an acknowledgment already observed, but grants no new authority. A
claimed successful cleanup result never removes the stop. Cleanup results
and further ordered cleanup intents can still append. A production writer
must also close its live barrier and Forwarder gates before invoking
cleanup, and any uncertain append holds.

The action family has a fixed maximum derived from the launch grant count
plus two signal actions, at most seven intents and seven results. Intent
bodies are capped at 4,096 bytes and result bodies at 2,048 bytes. With the
current 384-byte overhead, the family worst-case charge is
`7*(4096+384)+7*(2048+384)=48,384` recovery bytes. A source preflight must
show that this family plus all effect receipts, release observations,
terminal/containment/reconciliation records and other specified recovery
obligations fit the current 16 MiB recovery reserve before any writer. This
no-writer unit charges actual body plus overhead to recovery capacity and
rejects an eighth impossible/duplicate action as a replay mismatch; it
creates no escrow. The codec
and replay must reject forged recomputed predecessors, cross-Run/grant
targets, impossible order, duplicate IDs, malformed outcomes and oversized
bodies. Stopped/live inspection exposes only counts, digests, unmatched
actions and `supervision_actions_unqualified`; it cannot relax a Run hold.

## Follow-on and acceptance

Before a production writer, verify the real Forwarder per-grant revoke
reply and current closeout through the authenticated client; record callback
start/result, stable containment observations, root reap, real pipe EOF and
capture separately. A writer needs current-head read-back and capacity
preflight, a bounded callback, and restart reconciliation for an intent
without a result. It must not issue the same signal or revoke blindly on
restart. A synthetic fixed child can exercise process ordering separately,
but cannot attest intended-venue containment.

Local source acceptance should cover every crash prefix, one grant and all
grant cap, missing/late results, hold/deadline, SIGINT/SIGKILL order,
forged records, capacity, mixed-version reopen, stopped read-back and
old-binary refusal. Native, provider, paid, tenant, venue, power-loss and
human acceptance are **NOT RUN**.
