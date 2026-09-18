# When a Run is refused or never runs

Type: grilling
Status: resolved
Blocked by: none

## Question

The timing prototype found three ways a Run fails that the demo currently cannot tell
apart from success, and none of them is the Run reasoning badly.

- **Hands refuses.** A `jira-as` command over roughly 9,400 characters is denied by the
  allow list on length alone, with the ordinary don't-ask message and no reason
  ("Does a high-effort Run fit the slot"). All three arms that hit it handled it badly:
  one shortened and retried twice, one **created a junk Incident to test the boundary**
  before filing the real one, and one spent its whole remaining slot probing and filed
  nothing. What does the Skill tell a Run to do the first time Hands refuses? A Run must
  never write a probe into a live OPS project, and it must prefer a short filed Report
  over a long denied one.
- **The Run never ran.** A rate-limited Run's result line says `"subtype": "success"`
  with zero cost and one turn, **and the process exits 0** — but the same line also carries
  `"is_error": true`, `terminal_reason: "api_error"` and a plain-English `result`. So the
  question is not "is there an honest field" — there is, and it is `is_error`. It is which
  fields the Receiver branches on, in what order, and what the audience sees when a Run did
  not happen. Note also that only some models are refused: Fable 5.1 was out of usage
  credits while Opus 5 and Haiku 4.5 ran, so "the API is down" and "this model is not
  available to us" are different states and the demo should tell them apart.
- **The Run stalls.** The worst arm in the timing prototype did not loop or probe: it fell
  silent at +246.6 s and emitted nothing for 466 s until a synthetic `Output token limit
  hit` message, having blown the 64,000-token per-message output cap while serializing the
  Report. A Run can be alive, billing, and producing nothing, and the Receiver cannot see
  the difference from a Run that is thinking. What, if anything, detects that?
- **The Run was killed.** A Run killed on the Receiver's timeout writes no result line,
  so its cost and usage are lost, and chapter one's `RUN_TIMEOUT` is 300 s against an
  Opus 5 Run measured at 370 s. Is the guard SIGINT, which yields a result line, rather
  than the current SIGKILL? What is the timeout now that a Cascade has been timed?

Produces an ADR or extends ADR 0003, and hands the Skill a "what to do when refused"
section. This is the decision the prototype's worst outcome argues for: a Run that
investigates perfectly and produces nothing is worse on a stage than a thin Report.

## Work history

Claimed after ticket 20 was committed. Offline fact checking and human decisions only; no runtime/Skill changes, model Run, live mutation, container or cluster. Historical failure evidence is not treated as current model/CLI behavior.

The human accepted the first [decision round](../reviews/ticket-21/round-1.md), covering separate execution/effect outcomes, bounded refusal recovery, a total deadline with reserved cleanup time, honest silence/progress reporting, and explicit recovery before new dispatch. These are accepted planning decisions, not implemented behavior.

[Offline facts](../reviews/ticket-21/facts.md) confirm current exit-only handling and identify the committed historical false-success measurement; its raw Transcript was not committed. SIGINT result flushing remains documentation-derived, not a measured guarantee. The current timeout guard also needs acceptance for a parent that exits while descendants retain stdout.

The human accepted the second [decision round](../reviews/ticket-21/round-2.md), covering the total time budget, an explicit Receiver recovery-journal persistence exception, failed/pending merge, terminal-evidence rules and operator controls. Both rounds are accepted.

## Answer

[ADR 0012](../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md) records the ten accepted decisions. Execution and external effects are separate; result errors and Receiver timeout/cancel/containment observations override apparent success. Missing/conflicting terminal evidence is incomplete, missing usage unknown, and required effects need trusted evidence or justified no-ops. One shorter Report attempt is permitted only after proven pre-dispatch denial; never probe live permissions or blindly retry uncertain writes.

The five-minute total is 270s startup/work, 20s interruption/local flush and 10s kill/reap. Silence is not a stall verdict and output cannot extend the deadline. Revoke authority at cancellation/work deadline; interruption does not guarantee a result. Unconfirmed containment holds dispatch.

A Receiver-owned durable Recovery journal explicitly extends ADR 0005, separately from Run-written Memory. Durable admission precedes acknowledgement; mutation intent precedes dispatch. Preserve pending/failed work, latest-admitted dedupe state and effect evidence across rehearsal restarts, with dispatch held and sentinels invalid. Reconcile before a fresh operator-authorized retry, merging newest admitted Alert state without replaying confirmed operations. Unknown external effects cannot be erased by abandonment/reset. Optional Memory/export failures alone do not justify repeating OPS work.

Operator controls are cancel, inspect/reconcile, retry and resume. [Future Skill guidance](../reviews/ticket-21/refusal-recovery-contract.md) remains a planning artifact; [ticket 37](37-run-recovery-and-admission-specification.md) owns concrete recovery/admission specifications and fixture extensions. No Skill/runtime implementation, model/signal experiment, live mutation, cluster or demo acceptance was performed.
