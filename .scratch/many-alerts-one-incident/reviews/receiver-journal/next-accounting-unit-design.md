# Next unit after 17b: accounting prerequisite design decision

2026-09-24. Design only; tests and implementation NOT RUN. Reconciled against
17b commit `b0533879666d5bee6e8c6c186f7f7ca045cb2dd5`. The designers inspected
17a `c3e4f3a` plus the reviewed 17b candidate; the committed 17b source bytes
match that reviewed candidate. Standing local source/test/review/commit
authority applies. Paid/provider/native/tenant/deployment/publication
and ticket-19 C2 remain outside scope.

## Designs and judgment

Two independent designers read the ticket-37 and ticket-38 specifications,
ADRs 0012/0013 and the implemented journal contracts. They considered:

| Candidate | Correctness / containment / bounded scope (5 each) | Ruling |
| --- | --- | --- |
| Lifecycle first with injected or nullable reservation receipt | 1 / 1 / 3 | Reject: no durable reservation gate; no-reservation profile is not authorized |
| Add accounting tables to the existing journal immediately | 3 / 3 / 1 | Defer: exact DDL validation, generation, lifetime accounting and migration need their own design |
| Separate durable accounting ledger plus journal handshake immediately | 4 / 4 / 2 | Defer physical choice: valid if intent/confirmation/unknown and recovery scan are proved; two-store rollback is substantial |
| Pure reservation policy with no executable authority | 5 / 5 / 5 | Select next, before choosing storage or changing any journal format |

Scores are root engineering judgments, not experimental measurements. Design A
prefers separate storage later; Design B prefers versioned one-store storage
later. Neither has the migration/rollback evidence to settle that choice now.
Both agree on the pure prerequisite. Preserve that disagreement explicitly;
the selected next unit does not choose physical accounting persistence.

## Selected boundary: unit 18a

Unit 18a is evaluation-only: implement exact money validation, stored
week-boundary values and reservation eligibility arithmetic. Apply/replay,
event envelopes, configuration registries, genesis and chain formats require
a separate unit after this policy boundary is reviewed.
Outputs are proposals/refusals, never durable receipts, launch permits or a
`ready` production gate. No existing module calls the new component. Preserve
all admission-only pins, legacy modules, recovery journal modules and goldens.

Use new modules and tests only. No CLI, environment reads, SQLite, current-clock
reads, HTTP, provider adapter, lease registration, process spawning, pending
consumption, reset or paid experiment. A later implementation plan must list
its exact module/API/value/error shapes, then reconcile against the latest
commit before editing source. Prefer one module for pure policy. Target <=600 source lines; if even the
evaluation-only scope exceeds that estimate, split exact-value validation
from eligibility under an explicit reviewed module boundary before coding. No journal event or DB version
change merely to exercise a hypothetical future format.

Public seams to specify/test:
- Exact USD microdollar validation and immutable bounded inputs.
- Week boundary calculation from an explicit UTC instant; original reservation
  boundary values remain stored and unchanged across rollover.
- Pure evaluation of an explicit accounting snapshot and candidate into a
  proposal or closed refusal, with no mutation on refusal.
- No apply/replay seam in 18a; a later pure transition unit can reuse these
  predicates before either physical-storage design is selected.

A snapshot without complete population/history and defensible current liability
is indeterminate. A synthetic completeness declaration is test input, never
provider evidence. No public boolean is presented as authenticated coverage.
The later trusted durable adapter must establish provenance and re-evaluate
under serialization against its current head; proposals cannot be reused as
launch authority.

## Accepted policy versus proposed choices

Accepted ADR policy is a $3 reservation, Monday–Sunday New York weeks,
a $150 weekly model envelope, $30 lifecycle and diagnostic ceilings and
10 attempts per relevant bucket. The named liability U, U>=R and signed
integer USD microdollars are ticket-38 proposed implementation choices,
conservatively adopted for this pure unit; they are not additional ADR text. Retry contributes once to the weekly total
and to both lifecycle and diagnostics spend/count limits. No model switch or
conversion of a retry into initial work. No unknown cost treated as zero.

The ticket-38 proposed lifetime experiment guard remains strictly below $50,
including applicable model/support/review/venue liabilities across weeks.
Non-model cost never consumes model allocations. An unknown earlier amount or
population blocks new proposals. R is not the maximum charge: use defensible U
for unsettled attempts, and defer final provider-line coverage/settlement to a
later unit. No release or counter decrement exists in the initial subset.

Currency, amount bounds, strict caps and attempt attribution need exact
independent known answers, not tests that repeat implementation arithmetic.
This source unit does not establish real provider coverage, enforceability of
U, available balance or authority to execute a paid Run.

## Rulings and deferred contracts

1. Ticket-38's sentence “before step 2 has no admission” means no *attempt
   reservation*. The implemented durable Notification admission already exists
   and survives an accounting refusal. Record that clarification when the
   implementation plan is written; do not edit history or reject Notifications.
2. The proposed four future event slots are insufficient to establish arbitrary
   billing/repair capacity. The pure plan may conservatively budget the specified
   slots as a reservation precheck, but must not claim full future reconciliation
   capacity. The durable unit must design separate control/repair headroom.
3. Counters count conservatively committed reservations once durable storage
   exists; observed starts are separate. A pure plan/proposal is not a committed
   attempted Run. Failed evaluation increments nothing.
4. Provider actual import, refunds, complete-coverage verification, hold clearing,
   archives, tombstones and qualification/human grading remain separate work.
5. Separate storage, if selected later, requires committed journal intent,
   idempotent ledger reserve, committed confirmation, and a no-launch recovery
   scan. A missing confirmation is unknown, not proof of zero liability.
   One-store storage, if selected, requires explicit format and identity/lifetime
   migration rather than extra version-1 tables.
6. Freeze old registered journal types. New types may use version 1; a version-2
   type requires explicit writer-side version propagation and old golden parity.
7. Immutable reservation evidence will not suffice to dispatch later: the
   lifecycle unit still needs current holds, both identities/readiness, lease,
   launch claim, containment and staleness rules, all before any spawn.

## Acceptance direction

Test strict scalar/overflow rules; resulting experiment liabilities of
49,999,999 and 50,000,000 microdollars ($49.999999 and $50), starting from
46,999,999 and 47,000,000 with U=3,000,000 and all other predicates passing;
inclusive model ceilings; R/U distinction; diagnostic/retry dual attribution;
10-attempt ceilings; missing/stale/conflicted history; week/DST boundaries;
unchanged older-week liabilities; no release on process failure/zero estimate;
identity conflicts and snapshot consistency. Mutation review
must kill `<` to `<=`, U to R, duplicate weekly retry charge, missing diagnostic
attribution and unknown-to-zero changes. Full suite precedes a code commit.

The ticket-38 reservation seam remains unmet after this pure unit. This is a
bounded prerequisite, not completion of Run lifecycle or ticket 38. The next
artifact is the exact implementation plan and its critic reconciliation.

## Critic reconciliation

The independent critic approved the direction after two factual corrections:
U/microdollars are explicitly proposed choices, and cap tests now specify
prospective microdollar sums rather than million-fold dollar amounts. Unit
18a is expressly evaluation-only; transition/replay design is deferred.

The exact implementation plan must derive or cross-check totals, identities,
original-week attribution, counters and holds from coherent bounded snapshot
facts, and reject contradictory/unknown population. Label any assumed
completeness as hypothetical; no production caller consumes it.

Independent count-limit tests need coherent settled-history fixtures with
low actuals, since ten unsettled U>=$3 reservations already exhaust a $30
bucket. Weekly-$150 predicates need separate policy tests because the strict
lifetime-$50 guard cannot admit a prospective $150 combined state. This is
explicit predicate testing, not a claim that combined eligibility passes.
Retry tests must pin predecessor/candidate linkage, fresh identities,
reconciliation preconditions and configured attribution; reject unapproved
ceiling expansion. These are prerequisites to implementation-plan acceptance.

## Review provenance and commit reconciliation

Two independent Codex designers supplied alternatives; a separate critic
reviewed the root decision and accepted the corrected design. The critic
approval applies only to this design decision. Its implementation-plan
obligations above remain open.

Original local review input hashes (SHA-256):

- `design-a.md`: `e80606e39fe089536f82181d48399381c87e38e39ac74d3aeb59f6b5817fa8bd`
- `design-b.md`: `3cda9e8938ff70af989ecc27c76a6f67e29a74756b57235601c2d90e853eaec1`
- `critic.md`: `72981453a6f0503c6558ce06dd3994e782d1a72d069234049b1772163cd9544f`

The 17b validation record was read back and every artifact hash verified
before saving this decision. No 17b source, tests, plan or validation artifact
changed for this design-only commit. The exact 18a implementation plan and
its critic reconciliation must precede source changes; the ticket-38 durable
reservation seam remains unmet. No paid or provider execution is authorized.
