# Finish the Fable arm and pin the denial threshold

Type: task
Status: open
Blocked by: none

## Historical question — execution claims superseded below

Two measurements from the timing prototype are unfinished. They are **not equally
blocked**, which an earlier version of this ticket got wrong:

- The **length probe is runnable now**. It is driven by Haiku 4.5, and Haiku 4.5 and
  Opus 5 were both confirmed working right after the arms.
- The **Fable arm is blocked on usage credits**, not on a weekly window. `claude-fable-5-1`
  is refused with "You're out of usage credits"; the remedy is topping the balance up at
  claude.ai/settings/usage, a human-in-the-loop step, and then it can run immediately.

On branch `prototype/run-timing`:

1. **The Fable 5.1 arm.** `python3 measure.py run fable51-high --model claude-fable-5-1
   --budget 3 --wait 900`, then `python3 measure.py report` and `python3 score.py
   fable51-high`. It is the one comparison the ticket asked for that has no number.
   Chapter one's recorded Transcript ran on Fable 5.1, so this is also the "what chapter
   one would have done" arm.
2. **The denial threshold.** `probe/` holds five ready command files at 9,500, 11,000,
   12,000, 13,000 and 14,000 characters and a `PROBE.md` telling a Run to run each
   verbatim and report ran-or-denied. Drive it with Haiku 4.5 to keep it cheap. The
   natural experiment bounds the threshold between 9,417 accepted and 11,313 denied;
   this pins it.

This ticket does work; it decides nothing and produces no ADR. It is here so the frontier
carries it rather than a reviewer's memory. The answer records the Fable numbers, its
grade against the Ground truth, and the threshold, and appends all three to
`prototype/run-timing/results/measurements-2026-09.md`.

## Current execution boundary after ticket 22

The commands and model availability above are historical, not runnable-now evidence or authorization. Ticket 22 refutes independent per-model balances as an established fact; a top-up is not an accepted remedy. ADR 0013 requires metered API billing, mediated credentials, budget preflight and separately authorized execution. Redesign these probes against that contract and ADR 0012's 300-second total bound before any future run; the historical 900-second command is not an approved current Run budget. The user has since granted standing cost authorization strictly below $50 aggregate; see [the authorization receipt](../reviews/ticket-23/experiment-authorization.json). Native execution remains technically closed pending the mediated route, accounting and client evidence. No credential change is established by that approval.

## Source preparation, 2026-09-21

The [redesign packet](../reviews/ticket-23/source-redesign.md) records the pinned historical
harness gaps, revised timing/length contracts, inert fixtures and implementation
acceptance gates. The [measurement card](../reviews/ticket-23/execution-card.md) remains
**CLOSED**. Source preparation can proceed independently of ticket 19's C2 provider
block; paid execution still requires reviewed implementation, mediated-client and
budget readiness, then a concrete one-attempt card under the standing aggregate authorization. No new measurement or
qualification result is claimed; this ticket remains open.

## Offline implementation continuation

The [offline implementation outcome](../reviews/ticket-23/implementation-outcome.md)
records the new replay core, adversarial regressions and remaining native integrations.
No paid timing/length probe ran. The measurement card stays closed and this ticket stays
open; offline receipts, ledger snapshots and containment observations do not establish
the corresponding host/provider boundaries.

The next [fixed-process harness outcome](../reviews/ticket-23/process-outcome.md) adds real
host fixture evidence for scheduling, cancellation, process-group cleanup, pipe EOF,
bounded output and attempt collisions. It does not admit a native model client or prove
adversarial isolation. Ticket 23 remains open; paid execution remains closed.

The [synthetic diagnostic ledger outcome](../reviews/ticket-23/ledger-outcome.md) adds
durable reservation/launch claims, exact receipt reconciliation and concurrent/crash
tests around fixed local fixtures. Inputs and allocation amounts are synthetic; no real
accounting ledger or paid probe is admitted. This diagnostic slice does not complete
ticket 38's lifecycle/Receiver integration. Ticket 23 remains open; native launch remains
closed.

The [fixture closeout outcome](../reviews/ticket-23/closeout-outcome.md) adds bounded
retained output, exclusive publication and digest/linkage read-back. Byte integrity does
not establish semantic acceptance, production audit custody or a launch-to-durable-closeout
deadline. Closeout failures preserve unresolved ledger claims. Paid execution remains closed.

The [inert length-record outcome](../reviews/ticket-23/length-record-outcome.md) adds
five-case snapshots with command digests, virtual times and separate issued/supplied
receipt observations. Synthetic permission labels and opaque references do not establish
native permission or authenticated dispatch. Ticket 23 remains open.

The [timing text outcome](../reviews/ticket-23/timing-text-outcome.md) adds reviewed source
drafts for the prompt, diagnostic Skill and operator-only human rubric. Historical inputs
are pinned; legacy flag-name grading is excluded. The pinned Mechanism/rubric freeze is now human-approved in the
[approval receipt](../reviews/ticket-23/timing-draft/operator/rubric-approval.json);
the native adapter/executable binding remains pending. No Skill was installed and no probe ran.

The [pinned query outcome](../reviews/ticket-23/query-outcome.md) adds a read-only in-process
fixture API with exact input hashes, bounded queries, explicit truncation and correlated
response read-back. Native transport, authenticated receipts and synthetic Incident writes
remain unimplemented; the timing measurement card remains closed.

The [synthetic Incident outcome](../reviews/ticket-23/incident-outcome.md) adds an in-process
empty candidate store, additive membership, immutable Report revisions, retained query
references and separate simulated dispatch/effect receipts. Failed or uncertain writes
hold further work. Native binding, authenticated receipts, durable recovery and human
grading remain unimplemented or NOT RUN; the measurement card remains closed.

The [retained snapshot outcome](../reviews/ticket-23/snapshot-outcome.md) adds a bounded
operator-only bundle preserving query responses, Incident revisions and effect receipts
with byte/link read-back. Pending and unknown states stay explicit; no human audit grade,
native provenance, writable recovery or paid execution is established. Ticket 23 stays open.

The [documented stream outcome](../reviews/ticket-23/documented-stream-outcome.md)
adds a bounded offline normalizer against pinned official SDK source, conservative
process/stream correlation and metadata-only fixtures. Installed-client/native
qualification, mediated routing and real spend reconciliation remain pending. The
[standing experiment authorization](../reviews/ticket-23/experiment-authorization.json)
and [rubric approval](../reviews/ticket-23/timing-draft/operator/rubric-approval.json)
are granted; no repeat cost permission is required within the aggregate cap.

The [local mediated-client outcome](../reviews/ticket-23/mediated-client-outcome.md)
adds real two-hop Python TLS fixtures with scoped leases, deadline enforcement,
credential-header replacement and unknown/no-retry failure handling. Native client
streaming, real request policies, OS isolation and billing remain separate gates.

The [supervised streaming outcome](../reviews/ticket-23/supervised-streaming-outcome.md)
joins an actual fixed child's decoded frames to parent transport receipts and
process evidence. Cancellation, capture loss, nonzero exit and incomplete evidence
remain held; synthetic ledger claims are not automatically settled. This remains
fixture evidence, with native qualification and the measurement card closed.

The [native-launch evidence outcome](../reviews/ticket-23/native-launch-evidence-outcome.md)
adds a phase-specific contract, 14-area readiness record and reverified source pins.
The historical fixture inputs match their pinned Git commit; no current native
behavior, spending or Report grade is inferred. Application implementation is the
next proposed scope, separate from planning tickets and still excluding deployment.
