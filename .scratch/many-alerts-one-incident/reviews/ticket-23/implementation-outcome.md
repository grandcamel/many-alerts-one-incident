# Ticket 23 offline implementation outcome — 2026-09-21

Scope: the offline execution core in `prototype/run_timing`, two new test files and
ticket 23 documentation. Existing production code, historical timing source and the
rejected C2 packet were not changed. All changes remain local and uncommitted.

## Implemented and verified

- Bounded synthetic transcript parsing: duplicate keys/terminals, malformed or missing
  evidence, result/exit errors, explicit actual assistant identity, unknown estimates
  and receiver-observed failure precedence.
- Virtual 270/20/10 lifecycle, scheduled transitions during silence, early cancellation,
  retained concurrent failure reasons and separate descendant/pipe observations.
- Fixed-case inert dispatch with pending tool requests, process-local receipt identity,
  order/reuse checks, explicit Boolean evidence, late receipt/denial collection during
  cleanup, refusal/fallback cancellation and conservative observed-bracket reporting.
- Diagnostic admission predicates for $3 reservations, $30/10-attempt diagnostic and
  $150 weekly ceilings, New York week boundaries and unresolved older exposure.
- Bounded in-memory synthetic capture with visible exhaustion; replay output always
  says `OFFLINE_REPLAY_ONLY` and native launch `CLOSED`.

Targeted suite: **99 passed**. Full repository suite: **340 passed, 36 skipped in
10.38 seconds**. Targeted Ruff and diff whitespace checks passed. No skip was promoted
to a pass. Test receipts and source hashes are recorded in implementation-validation.json.

## Standards review

Fresh independent Codex reviewer: one initial P2 finding, zero remaining after read-back
and 99-test rerun. String values such as `"false"` were accepted through truthiness as
containment/coverage evidence. Public observation boundaries now require exact Booleans
before mutation, with string/integer/null regressions.

## Spec review

Fresh independent Codex reviewer: three initial P2 findings, zero remaining after
read-back and focused verification. The Boolean finding overlapped Standards. The
other corrections separate collecting a pending request's evidence from starting work,
and propagate fallback/refusal cancellation into the linked lifecycle with visible
cleanup actions. Simultaneous timeout/cancel reasons are also retained.

Standards: 1 initial / 0 remaining, worst initial P2. Spec: 3 initial / 0 remaining,
worst initial P2. These reviews approve only the offline scope.

## External review

A fresh bounded read-only Fable review was dispatched through `headless` against a
self-contained frozen source packet. It **timed out after 300 seconds (exit 124)**.
Native output contains requested/init model and progress events, but no final review,
assistant-model identity or terminal usage/cost. Actual identity and cost remain unknown;
this is not a Fable pass. No retry or substitute external invocation was made. The two
usable independent Codex opinions satisfy the available panel; the requested external
opinion remains unavailable. This was not a timing/length probe or qualification sample.
No prior C2 reviewer conversation or rejection packet was resumed. Raw local evidence
and digests are referenced from implementation-validation.json.

## Remaining implementation and acceptance gates

| Boundary | Current evidence | Still required |
| --- | --- | --- |
| Host deadline/containment | Virtual observations and emitted actions only | Native isolation/process binding, real scheduling, descendant membership/reaping, held-pipe and output-collision acceptance. |
| Tool/receipt trust | Inert same-process stub; exact command comparison | Protected fixture mounts/fixed executable, authenticated outside-Run receipt transport, native Bash/permission correlation. |
| Client stream/model | Small synthetic Claude-shaped schema | Exact-version native adapter, full event-shape/actual identity/fallback evidence and effective policy. |
| Credentials/network | No network or credential API in this package | Forwarder mediation, TLS/trust/streaming, sentinel custody/revocation and direct-route prevention. |
| Budget | Pure diagnostic predicate over supplied synthetic snapshots | Atomic durable reservation, authoritative attribution/reconciliation, current billing/limits/lag; lifecycle allocations remain ticket 38 work. |
| Capture/audit | In-memory synthetic cap, no real secrets | Private durable bounded store, sanitization, retention, access controls, exclusive attempt directories and named human report adjudication. |
| Timing arm | Historical inputs remain frozen | Revised reviewed Skill/prompt/rubric and executable fixture bundle. |
| Paid execution | None | Concrete one-attempt card, readiness proof and separate authorization. |

The 26 planning outcome cases are a specification, not 26 passed native tests. Their
execution/dispatch/admission predicates are exercised here; real reservation release,
semantic claim grading and qualification are not implemented by this package. A future
native binding must enforce actions on time without waiting for model output. No real
containment, tenant effects, current billing readiness or venue qualification is claimed.

The [measurement card](execution-card.md) stays **CLOSED**. Ticket 23 remains open.
