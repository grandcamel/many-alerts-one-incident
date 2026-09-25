# Local work program after 18c storage

Status: active local plan, 2026-09-24. Authority: local specifications, source,
tests, reviews, truthful issue updates and commits. This plan does not amend an
accepted ADR or authorize any external execution.

## Current baseline and preservation

- `main` at `380287c` has the reviewed 18c storage gate. The existing journal
  front door is opt-in admission only. Neither can reserve or launch a model.
- Preserve the two pre-existing dirty ticket-19/planning files, the untracked
  panel directory and the two untracked ticket-19 drafts as distinct prior
  work. Record and compare
  their hashes before any local commit. Do not stage, reset, rewrite, discard,
  or report these files as accepted from this program.
- Ticket 19 stays claimed. Its C2 correction has a provider-safeguard stop and
  incomplete adversarial review. Do not retry, reword, reroute, or execute that
  path. Ticket 12 remains blocked on the missing Eyes evidence.
- All other non-resolved tickets stay open until their own acceptance criteria
  are met. A local implementation checkpoint is not tenant, provider, native,
  intended-venue, human-review, or publication acceptance.

## Ordered slices

| Slice | Feasible local deliverable | Gate retained |
| --- | --- | --- |
| A. Accounting continuity and reservation design | Reconcile ticket 38's proposed one-store schema with the selected separate ledger. Specify exact trusted opening/coverage evidence, v2 transition, archive/index, rollback witness and finite repair capacity. Review the plan before code. Implement only independently verifiable fail-closed parts. | No production reserve or launch until authoritative opening population, provider charge identity/coverage/lag, defensible U, and continuity witness are evidenced. |
| B. Recovery journal and effects | Versioned journal record/replay contract for Run attempts, operation intent, trusted response/read-back, unknown effect, held work, cancellation and operator disposition. Add pure reducers and offline storage/crash tests in bounded units. | No mutation dispatch or replay of an unknown effect; external OPS identity and Forwarder receipt remain unverified. |
| C. Cross-store and dispatch | Review an exact 18d intent/reservation/confirmation handshake, then implement its no-launch recovery scanner and conjunction gate. Add lease and permit identity checks after the journal and ledger interfaces are stable. | A historical event receipt alone never permits launch. Missing or conflicting counterpart holds. |
| D. Worker and launcher | Implement bounded process-group supervision, outcome precedence, deadline/reap evidence, and a guarded launcher that requires a fresh committed permit. Drive local deterministic processes and real local seams. | No model/provider invocation or claim of intended-venue containment. |
| E. Independent contracts | Advance local schemas and offline acceptance for tickets 32, 35, 36, 39, 41, 42, 43 and 44; continue ticket 16/23 source-only work where it does not require Eyes or paid measurement. | Keep each external, human, tenant and provider gate open. Do not work around ticket 19. |

Each multi-file source slice gets an exact plan and focused test seam first,
then source changes file by file, an independent source/spec review, focused
validation and the full repository suite before its local commit. Stage only
the named slice. Document test counts, hashes, read-back, unrun gates and any
changed ticket status. Stop one lane at a missing authority input and continue
another locally feasible lane.

## Immediate next decisions

1. Produce `receiver-journal/accounting-reservation-gates.md` with the exact
   evidence that is currently missing. Do not infer a trusted zero-spend
   population from a new directory, a synthetic marker, telemetry or an
   operator assertion.
2. Draft a reviewed Run/effect journal version plan for a source-only,
   no-dispatch first unit. The existing v1 journal has an exact schema and
   closed event registry, so extension requires explicit versioning; do not
   append an unregistered event to v1.
3. Keep the independent tickets' proposed contracts in view, updating local
   issue prose only when an actual source or review result changes their
   evidence state. Do not mark a ticket resolved from a plan or synthetic test.

## Completion rule

The persistent goal completes only after every feasible local slice has a
reviewed implementation and full-suite verification, and every remaining
external or safety gate is represented by an accurately open ticket with the
exact evidence and decision needed. No local result is a substitute for those
gates.
