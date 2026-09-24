# Evaluation-only accounting policy

`grafana_jsm_sandbox.accounting_policy` is unit 18a: an unconnected, pure
calculation over explicit hypothetical inputs. No application entrypoint calls
it. A `HypotheticalProposal` is neither a durable reservation nor permission to
launch a Run. The journaled front door remains admission-only.

The fixed policy uses USD microdollars: $3 reservation, up to $150 model spend
per New York week, $30 per lifecycle and diagnostics, and ten attempts per
applicable bucket. Retries consume both their lifecycle and diagnostics but
are charged once in weekly and experiment totals. Those ceilings come from
[ADR 0013](adr/0013-demo-spend-is-metered-reserved-and-qualified.md).

Ticket 38 proposes the signed-64-bit microdollar representation, defensible
upper liability U (at least $3 for a model attempt), and lifetime experiment
liability strictly below $50. This module adopts those proposed choices;
they are not additional accepted ADR text. Support, review and venue exposure
enters the experiment total, never a model allocation. Zero or lower settled
actuals never remove attempt counts.

## Public seams

- `validate_usd_micros(amount, currency="USD")` checks exact signed integers and
  USD. Booleans, floats, subclasses and overflow are refused. Negative values
  are valid representations; this evaluation subset refuses negative exposures.
- `week_for(instant)` takes an explicit UTC datetime in years 2000–9998. It
  computes Monday midnight through the next Monday in America/New_York and
  returns stored UTC boundaries. It may read installed timezone data; it never
  reads the current clock. DST weeks can contain 167 or 169 hours.
- `check_limits(Totals(...))` checks independent arithmetic predicates. `None`
  means those numbers meet the fixed ceilings only. It does not establish
  internally consistent history, available funds, or execution authority.
- `evaluate_reservation(snapshot, candidate, at=instant)` returns a frozen
  `HypotheticalProposal` or `Refusal(code)`. It derives totals and counters
  from individual rows and changes no input.

Every record is a frozen dataclass with slots. Constructors do not validate:
validation occurs at these public seams. Exact nested types and tuples are
required; identifiers are canonical lowercase UUID pseudonyms, not account
names or credential material. New attempt/reservation/Run/lease and cost IDs
must be disjoint from one another and from configured experiment, lifecycle,
model/auth/venue IDs; references to shared context may repeat. `journal_generation` is an exact integer in
1..2**31-1; this correlation alone is not a full journal identity check.

A `Snapshot` contains experiment/generation, `as_of`, explicit population
status, configured `Profile` values, `Lifecycle` registrations, prior `Attempt`
rows, `NonModelCost` rows and holds. `as_of` must exactly equal the evaluation
instant. Only `hypothetical_complete` population with no holds can produce a
proposal. This label asserts a test assumption, not authenticated completeness.
No supplied aggregate totals or caller-supplied budget ceilings are accepted.

A `Candidate` carries matching experiment/generation, four fresh identities
(attempt, reservation, Run, lease), a configured profile, kind and lifecycle,
optional retry predecessor, explicit reconciliation assumption, and exposure.
The output retains the candidate, computed week, fixed $3 reservation, U and
prospective totals. IDs and assumptions are supplied, never minted or verified
against a real Receiver, provider or account here.

## History and liability

`Exposure` is `bounded`, `settled`, `unknown` or `conflicted`. Bounded exposure
uses U and an explicit validity deadline strictly after evaluation; actual
must be absent. Settled exposure uses a nonnegative actual no greater than U
and has no validity deadline. Settled means hypothetical complete-coverage
input: this module does not reconcile provider charges. Unknown, conflicted,
missing, stale and above-U amounts refuse. Estimates, process exits and partial
provider observations have no input field that could release liability.

Model rows always require U >= $3. Non-model U can be zero. One exposure enters
each applicable total once; actual replaces U rather than adding to it.
Historical over-cap buckets hold even if the candidate uses a different bucket.
All experiment weeks contribute to lifetime liability. Old reservations retain
their original week, and rollover clears neither liability nor holds.

Stored weeks undergo structural validation without recalculating historical
timezones: canonical Monday date, 04:00/05:00 UTC endpoints on that date and
seven days later, zero sub-hour fields, and 167/168/169-hour duration. Same-key
values must agree; different weeks cannot overlap. Current stored boundaries
must match newly calculated boundaries. Historical timezone provenance remains
a future adapter obligation.

This deliberately narrow subset permits one lifecycle in each fixed weekly
slot (`rehearsal_1` through `rehearsal_3`, `presentation`) and configured
profiles only. History timestamps must strictly increase and precede the
candidate. A retry requires the latest prior attempt in its lifecycle, the
same model/auth/venue profile, and an explicit reconciliation assumption.
After a declared retry, later work in that lifecycle must continue the retry
chain. Cross-week retries and ordinary continuation after a retry are refused
pending fuller lifecycle/rollover design; these are subset restrictions, not
ADR policy. Without terminal/effect evidence, this evaluator cannot detect
failed work relabeled as ordinary before the first retry. A trusted future
adapter must prevent that semantic relabeling.

Input bounds are 16 profiles, 512 lifecycles, 512 attempts, 512 non-model
costs and 32 holds. These are calculation limits, not durable-store capacity
acceptance. Complete history that exceeds them refuses; nothing is discarded.
Credits/refunds, settlement/import, apply/replay, configuration registries,
archives, durable capacity, and storage choice remain separate work.

## Validation boundary

Tests exercise known arithmetic answers, strict scalar and input validation,
week/DST boundaries, retained history, dual attribution, and fixed count caps.
A future trusted adapter must establish real coverage/configuration/U, preserve
full accounting identity and history, re-evaluate under serialization, commit
a reservation durably, and satisfy lease/readiness/launch requirements.

No filesystem durability, concurrent reservation, provider billing, native
client, tenant, venue, model quality, paid Run or human Report adjudication
acceptance follows from this unit. The ticket-38 durable reservation seam
remains unmet. Nothing here clears the operational unknown-exposure gate.
