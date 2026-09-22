# Next offline unit: incremental synthetic TLS streaming

2026-09-22. Proposed bounded implementation plan under the standing local-work
authorization. This extends ticket 23's existing Python loopback transport
fixture. It does not implement a planning-only ticket, select a native model
client, retry ticket-19 C2, or make a provider request.

## Problem and intended result

The [current harness](../../../../prototype/mediated_client/README.md) buffers
one exact SSE-shaped response before returning it. It therefore cannot show
incremental delivery, partial-stream failure, or revocation between frames.
Add a separate fixed synthetic streaming mode with a finite event script and
two verified TLS loopback hops. An independent client must observe the first
complete frame before the trusted controller releases the final frame.
The client must decode and acknowledge that exact complete validated frame;
a mediator write, readable socket or internal queue event is insufficient.
Retained test evidence orders client acknowledgement, controller final release,
terminal observation and transport close without treating these synthetic events
as a production client acknowledgement protocol.

Keep the existing buffered fixture and its stated claims intact. The added
mode has no arbitrary upstream, native SDK schema, credential, tool invocation,
provider identity, or production control endpoint. Its events are deliberately
fixture-specific and cannot qualify an installed client's stream format.

## Implementation sequence

1. Freeze a small fixture protocol and terminal rules. Set explicit limits for
   total bytes, frame bytes, event count, nesting, concurrent requests, history,
   per-operation timeout and absolute connection lifetime. Keep the existing
   connection lifetime bound unless a reviewed change is necessary. Use exact
   finite Content-Length framing initially; HTTP chunked transfer is out of this
   unit's scope. Unknown framing or event vocabulary is rejected.
2. Implement an incremental strict decoder and bounded transport path in
   `prototype/mediated_client`, with trusted test-controller barriers that have
   deadlines and cleanup. Validate every complete frame before forwarding it.
   Do not retain a whole stream merely to make the test appear incremental.
3. Record metadata-only delivery evidence: attempt/sequence, validated frame and
   byte counts, digests, whether any bytes may have crossed the client boundary,
   terminal observation and transport completion. A synthetic terminal does not
   override truncation, extra bytes, disconnect, revocation or timeout.
4. Serialize lease checking with each bounded downstream frame send. Do not hold
   the revocation lock while waiting for the next upstream event. After revoke
   returns, no later frame may begin dispatch; an already-dispatched frame may
   have arrived. Closing a socket never proves rollback or stopped billing.
   Distinguish frame read, validated, dispatch-started, write-complete and client
   acknowledgement. Discard validated-but-not-dispatched frames after revocation.
   On detected downstream failure, close the upstream path and wake any controller
   barrier; undetected peer closure remains bounded by the absolute deadline.
5. Test through real loopback TLS client/mediator/upstream boundaries. Use
   bounded synchronization to prove the first-frame-before-final-release order,
   avoiding assertions that depend only on a narrow elapsed-time race. Add
   meaningful parser edge tests alongside transport fault tests, then obtain
   an independent review and run the full repository suite before committing.

Review between protocol, transport and integration steps. Delegate a bounded
implementation to Terra and independent testing/review to Luna where practical;
avoid overlapping file ownership. Fix review findings before local retention.

## Required failures and assertions

Cover malformed or split UTF-8, duplicate JSON keys, unknown fields/kinds,
non-finite numbers, oversized/deep frames, total-byte and event-count limits,
missing/duplicate/conflicting terminal, trailing bytes after terminal, truncated
frame/body, upstream disconnect/timeout, downstream disconnect, lease expiry,
revocation before dispatch and between frames, and cleanup of stalled barriers.
Verify one upstream attempt, no automatic retry, and no secrets or bodies in
receipts. Preserve nonce/sequence correlation and existing malformed-header,
fixed-route, TLS trust and lease denial coverage.

Before a downstream response begins, a failure can use the existing bounded
local gateway response. After headers or bytes begin, close the failed stream
and record partial/unknown delivery; do not send a second status response or
manufacture a successful terminal. Client completion requires the exact terminal,
valid framing and full transport completion within the deadline.
Hold the terminal frame until the remainder and transport ending are verified,
so a duplicate terminal or malformed trailing frame cannot follow downstream
success. A claimed Content-Length alone does not establish the absence of
additional bytes in this fixed connection-close fixture.

## Acceptance boundary

Retain reviewed source, focused and full-suite results, bounded fixture receipts,
and updated README claims. This is synthetic incremental transport evidence
only. Native client configuration/schema, OS credential and route isolation,
provider cancellation and billing, accounting reconciliation, audit deployment,
tenant behavior, human Report review and venue qualification remain untested.
No paid experiment is admitted by this plan; historical charges remain unknown.
