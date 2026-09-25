# Unit 19a: pure Run execution outcome

Status: proposed local design, 2026-09-24. Source: accepted ADR 0012 and
ticket 37's proposed execution/effect contract. This is a no-dispatch slice
after the 18c reservation gate stopped on external evidence.

## Seam and authority

Add one pure module between a future sanitized Receiver observation stream
and a future versioned recovery-journal writer. It receives already bounded,
non-secret process and terminal facts and returns a descriptive execution
assessment. It does not parse a native client's raw Transcript, authenticate
Forwarder receipts, decide OPS effects, reserve funds, create a Run, retry,
issue a permit or clear a dispatch hold. No existing caller imports it.

The interface accepts one `ProcessFacts` and a tuple of zero, one or more
`TerminalFacts`. `ProcessFacts` records the Receiver's trusted spawn state,
observed process exit, timeout/cancellation and containment. `TerminalFacts`
contains only subtype, exact boolean error indicator, bounded reason,
usage-state category and a digest reference. Invalid/missing terminal fields
become incomplete evidence; raw inputs never appear in errors or results.
The returned frozen `ExecutionAssessment` carries a closed execution state,
closed reasons, observed usage state (`known` or `unknown`), and whether a
trusted no-process observation exists. It carries no financial amount, effect
confirmation or launch authorization.

## Policy mapping

Use ADR 0012's precedence. Unconfirmed containment of a possibly started
process takes priority. Receiver timeout/cancellation overrides terminal
success. Trusted spawn failure, error terminal or nonzero exit prevents
success. Missing/malformed/duplicate terminal or missing exit is incomplete
unless an earlier override applies. Only exactly one valid success terminal,
clean observed exit and confirmed containment can be `succeeded`. A nonempty
reason on a claimed success is conflicting evidence and makes it incomplete;
this module does not infer meaning from arbitrary reason text. Missing or
malformed usage is `unknown`, never zero. A trusted spawn failure before
process creation is separately marked `never_started`; an unknown spawn gap
is not. Execution success leaves all external effects unverified.

An untrusted caller may construct facts in a unit test; the assessment is
descriptive only. The later journal unit must bind those facts to Receiver
observations and digest-linked event records. The eventual effect module must
verify Forwarder correlation and OPS read-back before any `CONFIRMED` effect.

## Deferred

Versioned journal events/replay, effect intent/receipt/reconciliation, real
native event inventory, process supervision, lease revocation, deadline
enforcement and guarded launch each require their own reviewed plan and
real-seam local tests. Ticket 37 remains open. No provider, tenant, native,
venue, paid or model test is claimed.
