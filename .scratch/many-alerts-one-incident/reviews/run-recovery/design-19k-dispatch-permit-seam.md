# 19k: one-use dispatch permit at the Forwarder fences

Status: proposed local contract, 2026-09-25. Fixed point: `43b5a03`.
Authority: accepted ADRs 0012–0013, tickets 36–38, reviewed 19h/19i/19j
designs and current Forwarder L1/L2 and receipt source. This document issues
no permit, creates no effect, and changes no route availability.

## Current boundary

The Receiver ledger has `population=unknown`, no authenticated reservation
event and no positive reservation writer. The replayed journal confirmation
and Run intent are claims, not accounting authority. There is no effect
intent/receipt writer, Receiver authorization handler, operation binding or
permit store. Current `requires_permit` routes deny `permit_unavailable` at
both fences; `forwarder_exchange` denies them before upstream handling.
No caller-supplied token, Boolean or replayed claim may open that route.
The present control connection is Receiver-command/Forwarder-reply only; it
has no reverse request reader or demultiplexer. Authorization requires a
separate Receiver-owned, authenticated Unix endpoint with peer and
boot/generation checks before implementation. It may not inject unsolicited
frames into the current control session or expose that endpoint to a Run.

## Exchange and identity

After pure route and connector preparation, and before L1 admission or any
upstream connect, the Forwarder presents its authenticated route-specific
grant and generation, attempt, route, canonical prepared-request digest,
sanitized target/plan and bounded control deadline to Receiver
`AuthorizeDispatch`. The Receiver resolves the *logical operation ID* from
its own admitted state and approved adapter binding. The Run cannot assert
it. The target and digest must describe the exact prepared request that L2
would write; a changed request needs a new authorization decision, never a
retagged permit. Neither side transmits a raw body, secret or credential in
the control frame.

The Receiver must recheck the current journal and separately verified ledger
reservation heads, authorized Run/attempt, committed launch claim and grant
mapping, active route-specific grant, target and scope, work deadline,
venue/reference readiness, and absence of global dispatch hold. The future
Receiver writer uses one coordinator ownership order, `C -> journal J ->
ledger L`, never the reverse, and performs no Forwarder RPC while holding
these locks. It rechecks both heads after acquiring ownership and before its
first append. It durably appends and reads
back the exact `effect_intent` and applicable accounting exposure. Each
append invalidates the preceding exact-head qualification. Before replying,
it must freshly qualify the new committed journal head, the matching intent
and current independently verified reservation/exposure at the current
ledger head under that ownership order. This proposed order must be verified
against the actual store lock APIs before a writer is exposed. Any changed head, missing relation,
uncertain append or uncertain read-back issues no permit and latches dispatch.
Only then may it return an opaque one-use permit bound to operation,
attempt, grant, boot/generation, route, request digest, target, intent event
and monotonic expiry. There is no cross-store/upstream atomicity claim. These
positive checks depend on the externally gated accounting and native-client
identity evidence; the present product cannot satisfy them.

For a duplicate `(operation, request digest)` request, Receiver returns only
the recorded disposition and reconciliation reference, never a second live
permit. A conflicting digest or target for the same operation holds. A new
operation after an uncertain effect requires explicit reconciliation and a
fresh admitted attempt. Authorization is bounded by the five-second control
deadline clipped to the work lease; timeout/late reply has no permit effect.
The proposed separate endpoint uses frames at most 8,192 bytes, matching the
current control frame ceiling, and one outstanding authorization per service;
measure the actual encoded frame before implementation and hold if it cannot
fit. Give the endpoint its own bounded connection, descriptor, buffer and
pending-request allocation; exhaustion denies and holds. Its reader, reply
correlation and concurrent ownership are separate
from the existing command session.

## L1, L2 and recovery state

At L1, under Forwarder dispatch gate lock `G`, consume the permit once with
the final route-specific lease check and receipt `begin_connect`. The token
must be an identity-owned, generation-scoped object installed only from an
authenticated Receiver reply, bound to this flight and prepared digest.
Consumption is permanent even when a later fence denies; it must not be
recoverable from a copied value, restart or retry. L1 denial is
`NOT_DISPATCHED`/`permit_denied` only after trusted receipt finalization and
proof that no upstream connect began. A failed finalization or swept receipt
is unknown and holds. A trusted NOT_DISPATCHED denial can qualify for ADR
0012's sole shorter Report path only when its other evidence predicates hold.

At L2 immediately before the first possible upstream byte, recheck that the
*same consumed* permit still belongs to this flight, route, grant, digest,
target, boot/generation and unexpired deadline, together with the current
lease and gate state. Do not consume again and do not reauthorize in the
write path. A denial after L1 but before L2 is a zero-application-byte
`FAILED`/`connect_failed` receipt under the current vocabulary only when its
finalization and zero-byte evidence are trusted. The current deadline sweep
can instead yield `DISPATCHED_UNKNOWN`, and receipt failure has no reliable
final state; both hold. No post-L1 denial can be called `NOT_DISPATCHED`,
revive the permit or qualify for the shorter Report path. If a connection was
attempted but zero-byte evidence cannot be trusted, or L2/first-byte position
is unknown, hold as dispatch-unknown instead. After L2, any interruption or lost response
requires correlated receipt and required OPS read-back; no automatic reissue.

The gate must never call the Receiver while holding `G`. Reserve a bounded
flight first, obtain an authorization decision outside `G`, and install the
exact result only after rechecking that the same flight, grant, generation,
digest and deadline remain current. A late approval for a consumed, closed,
revoked or expired flight is discarded. On restart, old permits and grants
are invalid, dispatch is held, and outstanding intents are reconciled from
journal/Forwarder evidence. A Receiver-side authorization snapshot alone
does not prove L1 consumption, L2 passage or zero bytes.

## Local acceptance sequence

1. Keep permit routes closed while specifying a typed, bounded permit
   identity and pure binding/transition model. Synthetic tests may exercise
   forged/copy/replay/late/wrong-grant/wrong-digest/restart cases without
   supplying a production positive authorization path.
2. Add no-writer `effect_intent` and receipt codecs/replay only with measured
   ordinary/recovery capacity, mixed-version reopen, forged recomputed
   record and old-binary refusal coverage. The effect family must bind exact
   Run, service grant, operation, request and target identity; replay is not
   itself a permit.
3. Implement Receiver authorization and Forwarder L1/L2 wiring only when a
   current independently verified reservation relation, durable effect
   writer, authenticated control reply, registered grant mapping, native
   logical-operation binding and required route/venue evidence exist. Review
   Standards and Spec and run the full local suite before code commits.

Provider opening and charge identity, coverage/lag/finality, liability U,
continuity witness and archive registration, native tool compatibility,
intended venue, tenant/OPS read-back and human adjudication remain separate
unrun gates. A passing local synthetic test does not clear them.
