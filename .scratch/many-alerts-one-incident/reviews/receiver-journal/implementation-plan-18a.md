# Unit 18a: evaluation-only accounting policy

Status: approved for pure implementation after independent critique, 2026-09-24.
Baseline: `1d04b7dc1174924de52a8927059f9eb6cbaca3a3` (17b `b053387`).
Authority: the existing local application source/test/review/local-commit approval.
The reviewed next-accounting-unit-design.md selects this boundary. No live,
provider, paid, credential, deployment, publication or ticket-19 C2 work.

## Scope and files

New `grafana_jsm_sandbox/accounting_policy.py` and
`tests/test_accounting_policy.py` only for executable work. New
`docs/accounting-policy.md` documents use and limits. Records live alongside
this plan. Preserve all existing source/tests/goldens, 17b hash-bound artifacts,
protected dirty files and panel directory. A standalone outcome points from
this unit to the existing queue; do not rewrite hashed 17b backlog artifacts.

One module, target at most 600 lines. If the implementation exceeds this, stop
and review a split before coding further. Use only dataclasses, datetime,
uuid, zoneinfo. ZoneInfo may load installed timezone data: no network, current
clock, environment, process, persistence, CLI, imports of legacy/journal code,
or application integration. No apply/replay, settlement, provider-line import,
credits/refunds, configuration registry, capacity reservation or history archive.

The proposed ticket-38 phrase “before step 2 has no admission” means no attempt
reservation. Notification admission remains durable independently of refusal.
This unit creates neither kind of admission and clears no holds.

## Data and scalar seam

All records are frozen dataclasses with slots. Their constructors are simple
containers; public evaluation validates exact types, including nested records
and tuples. Invalid dataclass fields cannot bypass validation. No coercion,
subclass acceptance, caller text in errors, input mutation or returned mutable
containers. Strict UUIDs are canonical lowercase strings. Strings used for
kinds/states are from the closed sets below. Every referenced ID must exist.

`validate_usd_micros(amount, currency="USD") -> int` accepts exactly int in
signed 64-bit range and exactly str USD; rejects bool, float, Decimal, integer
subclasses, foreign currency and overflow with `PolicyInputError` carrying a
fixed code `invalid_money` or `currency_unsupported`. Arithmetic uses Python
integers, then explicitly refuses signed-64 overflow; no wrap or float.
Negative scalar values are valid representations, but all exposures in this
first subset must be nonnegative. Credits/refunds require a later contract.

`week_for(instant) -> Week`: exact datetime with timezone.utc, years 2000..9998.
Explicit instant only; no clock read. Uses America/New_York, Monday midnight
inclusive to next Monday exclusive. Week fields: `key` (local Monday date),
`start_utc`, `end_utc`, `timezone` fixed America/New_York. Return UTC instants.
Invalid input raises PolicyInputError("invalid_time").
Historical Week values are stored inputs, never recomputed using current tzdata.
Validate exact class/fields, Monday key, canonical UTC bounds, positive duration
167/168/169 hours, UTC endpoints exactly 04:00 or 05:00 with zero minutes,
seconds and microseconds, start UTC date equal to key and end date key+7.
These are conservative stored shapes, not historical timezone authentication.
Same key must have identical
bounds throughout snapshot. Different keys cannot overlap. A reserved_at value
must lie inside its stored week; no history may be later than the evaluation.
Fresh week_for output must agree with any same-key stored current week.

## Frozen input records

`Profile(model_id, auth_id, venue_id)`: three UUID pseudonyms; no model name,
account, token, billing material, raw prompt or other content.
`Lifecycle(lifecycle_id, slot, week, profile)`: slots rehearsal_1, rehearsal_2,
rehearsal_3, presentation. At most one lifecycle per (week key, slot); lifecycle
IDs unique. This fixes accepted allocations without caller-supplied ceilings.
All profiles must occur in the explicitly supplied configured profiles tuple.
No registry or claim that the configuration is authenticated is implemented.

`Exposure(state, upper_bound, valid_until, actual)`: state bounded, settled,
unknown or conflicted. Bounded requires nonnegative upper_bound, UTC valid_until
strictly later than evaluation and actual=None. Settled requires nonnegative
upper_bound and actual <= upper_bound, valid_until=None. Unknown/conflicted
refuse regardless of fields; missing/stale U is indeterminate. Model rows and
candidate require U >= 3,000,000 even if settled actual is lower. Nonmodel U may
be zero. Above-U actual refuses, not silently clamped. Settled rows are explicit
hypothetical complete-coverage input, not provider settlement performed here.
Partial/estimated/process-result fields are intentionally absent: those facts
cannot reduce exposure. Amounts/currency are validated at this seam in USD.

`Attempt(attempt_id, reservation_id, run_id, lease_id, reserved_at, week,
profile, kind, lifecycle_id, predecessor_id, effects_reconciled, exposure)`:
kind initial, retry, diagnostic. Every row represents a conservative committed
reservation, not observed launch. All four identities are required hypothetical
facts, globally unique across attempts/candidate and identity roles; no id is
created here. Initial requires lifecycle, no predecessor, effects_reconciled=False.
Diagnostic requires no lifecycle/predecessor and effects_reconciled=False.
Retry requires a lifecycle, effects_reconciled exactly True, and earlier
predecessor that is the latest chronological attempt in the same lifecycle,
with the same profile (model/auth/venue) and same original week. Predecessor may itself be a retry. Only one successor per predecessor;
no later initial in a lifecycle after a retry. Multiple ordinary initial Runs
within a lifecycle are valid. Structural declared-lineage check: after a retry,
additional work must be a retry linked to the current chain tip. Full effect
reconciliation authority remains outside this hypothetical evaluator. Without
terminal/effect evidence this cannot detect a failed initial misdeclared as
ordinary work before the first retry; a future trusted adapter must prevent
that semantic relabeling. No complete no-relabel enforcement is claimed.
History tuple is strictly ascending by reserved_at for deterministic lineage;
equal instants refused (conservative subset). Original-week attribution stays
fixed. Cross-week retry is refused in this subset pending explicit allocation
rollover design; settled old rows still affect lifetime cap.

`NonModelCost(cost_id, kind, exposure)`: kind support, review, venue. IDs unique
and disjoint from attempt/other identities. Count once in experiment exposure,
never model week/lifecycle/diagnostic totals. No known population means no zero.

`Snapshot(experiment_id, journal_generation, as_of, population, profiles,
lifecycles, attempts, non_model_costs, holds)`: exact tuples; max 16 unique
profiles, 512 lifecycles, 512 attempts, 512 nonmodel costs, 32 hold codes.
Population hypothetical_complete, unknown, conflicted. Only first evaluates;
it is explicitly not evidence of authenticated completeness. Requires at least
one profile. holds is a tuple of closed reasons from ticket-38 plus
execution_recovery and effect_recovery; any hold refuses. Unknown hold rejects
input. No caller aggregate totals, counts, or boolean readiness are accepted.
512 is a local evaluation input bound, not acceptance of durable capacity.

`Candidate(experiment_id, journal_generation, attempt_id, reservation_id,
run_id, lease_id, profile, kind, lifecycle_id, predecessor_id,
effects_reconciled, exposure)`: same rules as new Attempt, using evaluation
instant and freshly calculated week. Exposure must be bounded. Experiment and
journal generation must equal snapshot. Generation is exactly int in
1..2**31-1 (not bool); experiment ID is a canonical UUID. It is a hypothetical
correlation value, not full journal identity/readiness evidence. IDs must be
fresh. No counters mutate.

## Evaluation and output seam

`evaluate_reservation(snapshot, candidate, *, at) -> HypotheticalProposal | Refusal`.
Exact UTC at must equal snapshot.as_of; different time is `stale_snapshot`.
Validate bounds/types first as visited; then population/holds, configuration,
identities, historical weeks/lineage/exposure and candidate. Missing, conflicted,
stale or unknown facts return a closed refusal. Multiple bad inputs need not
have a specified winning error beyond always refusing without echoing input.
Unexpected programming errors are not caught by a blanket exception handler.

Derive totals from individual history rows, never supplied aggregate claims:
- each model exposure once in lifetime experiment and its original model week;
- initial in its lifecycle spend/count; retry in lifecycle AND diagnostics;
- diagnostic in diagnostics only; settled actual replaces U, never adds to it;
- nonmodel exposure in lifetime experiment only; all rows retain their counts.
All current-week allocations (including allocations unrelated to the candidate)
are checked for historical breaches, as are old-week allocations; over-cap
history refuses even if the current candidate would use another bucket.
Each lifecycle's model profile/week must match all its attempts.

`Totals(week_model, experiment, lifecycle, diagnostic, lifecycle_attempts,
diagnostic_attempts)` contains nonnegative checked integers after adding the
candidate. Lifecycle is zero for a diagnostic candidate. HypotheticalProposal
fields: `candidate`, `week`, `reservation_usd_micros` fixed 3,000,000,
`liability_usd_micros`, `totals`. It is a proposal only; no receipt, ready flag,
launch authority, apply method or durable state. Refusal fields: `code` only.

`check_limits(totals) -> Refusal | None` is a public arithmetic-only predicate
for exact boundary testing independently of reachable combined eligibility.
Reject invalid totals/overflow; enforce model week <=150m, experiment <50m,
lifecycle/diagnostic <=30m, counts <=10. Fixed codes: weekly_limit,
experiment_limit, lifecycle_limit, diagnostic_limit, lifecycle_attempt_limit,
diagnostic_attempt_limit. None means only these supplied arithmetic predicates
pass, never snapshot or executable authority. Historical checks use each week's
same limits, plus lifetime experiment limit, before prospective evaluation.

Additional refusal codes: invalid_input, invalid_money, currency_unsupported,
invalid_time, invalid_week, stale_snapshot, population_unknown, held,
identity_conflict, configuration_conflict, lineage_conflict, exposure_unknown,
exposure_stale, above_liability, arithmetic_overflow, history_limit.
PolicyInputError carries only a fixed code. evaluate/check_limits translate it
to Refusal. No logs, exceptions with input repr, or other output channel.

## Implementation slices and verification

1. Money/week scalar seam. Red/green exact known answers for valid integers,
   rejected scalar kinds/ranges/currencies; New York UTC Monday and both DST
   transitions (167/169 hours); frozen containers and invalid times.
2. Fixed limit predicate. Independently worked 49,999,999 vs 50,000,000,
   150m vs 150m+1, 30m vs 30m+1, 10 vs 11; overflow and strict type checks.
   Weekly predicate pass is not combined eligibility at lifetime $50.
3. Evaluate empty hypothetical snapshot -> $3 proposal, unchanged inputs;
   membership/generation/freshness/holds/population/shape refusal, exact bounds.
4. Derive history and model/nonmodel U/actual arithmetic. Strict-cap worked
   prior 46,999,999 +3m accepted, 47m +3m refused; U>R used; stale/unknown
   earlier weeks hold, settled low/zero actual retains counters, no credits.
5. Lifecycle/retry/diagnostic lineage and independent coherent count fixtures;
   ten settled low actuals leave spend headroom, attempt eleven refuses. Retry
   is charged once weekly/lifetime but twice across buckets. Unrelated old
   over-cap buckets hold. No resets on week rollover, no model switch.
6. Static identity/import/no-callers checks and bounded malformed-input cases.
   Keep public tests at these agreed seams; no private helper mocks.

Independent Spec and Standards reviews after implementation, with scratch-copy
mutations for strict <, U->R, double weekly retry, missing diagnostic attribution,
unknown->zero and counter deletion; add red/green cases for surviving mutants.
Fresh final hash-bound read-only review; full suite with DEMO_END_TO_END and
DEMO_CONTAINER unset, no cacheprovider, must pass before local code commit.
Focused suite via existing loopback guard must show NON_LOOPBACK_ATTEMPTS [].
Ruff, E501, diff check, baseline tracked source/test identity, protected hashes
before and after commit. Explicit staging only. Docs and validation must state
pure/synthetic evidence only and preserve untested durable/live/paid gates.

## Root reconciliation before implementation

Critic required stored-week precision, generation type, and unambiguous retry
lineage. Applied endpoint/date shape checks; pinned generation to the existing
journal integer range; retry predecessor must be the latest attempt in its
lifecycle. Narrowed the no-relabel claim to declared structural lineage because
this subset has no terminal/effect evidence. A trusted future adapter must
reject failed work relabeled as initial, establish population and configuration
authority, and re-evaluate under serialization. No implementation was started
before these corrections. Baseline source/test and protected hashes verified.

Exact-shape clarification: Week.key is exactly str in YYYY-MM-DD canonical
calendar form (not a date/datetime/subclass). Boundary instants may extend into
1999 for a week containing early 2000; the supplied week_for instant stays in
2000..9998. Candidate at must be strictly later than every historical reserved_at.
The no-initial-after-retry rule is a conservative subset restriction, not ADR
policy.

## Implementation review reconciliation

The independent plan critic approved the pre-implementation plan hash
`fc0b61a1a6836a9ab77cc5b4c2c8ac594ae7eef3ddfcc7873cdd725bce1ddca8`.
This status update and implementation reconciliation follow that approval.
Spec review found record identity collisions with configured context. Reserve
the union of experiment, lifecycle and profile model/auth/venue UUIDs before
checking attempt/reservation/Run/lease and cost identities. Context references
may repeat legitimately; new records must be disjoint from that union and
each other. Fifteen red/green regressions pin all five context roles across
cost, historical Run and candidate reservation IDs. No existing source or tests
changed. The implementation remains within the one-module 600-line bound.
