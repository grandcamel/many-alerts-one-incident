# Unit 18b: pure accounting event transition and replay

Status: accepted for local pure/synthetic 18b implementation after independent
critique, 2026-09-24.
Baseline: `11834600c712cf3f9851a989ed4c8e82fd4d806c`.
Decision: [next-accounting-transition-design.md](next-accounting-transition-design.md).
Local application source/test/review/commit authority applies. No external call,
credential read, paid execution, deployment, publication or ticket-19 C2 work.

## Size and file ownership

Add `grafana_jsm_sandbox/accounting_events.py` for the canonical v1 envelope,
`grafana_jsm_sandbox/accounting_transition.py` for pure transition/replay,
`tests/test_accounting_events.py`, `tests/test_accounting_transition.py`,
and `docs/accounting-transition.md`. Do not edit existing code/tests, either
journal golden, journal DDL, CLI or application entry point. Target <=800 new
production lines combined; pause and redesign if it exceeds 900. Keep codec
and policy transition separate interfaces. No filesystem, SQLite, current
clock, environment, network, process or random source in these modules.

## Closed event interface

`AccountingEvent` is immutable and contains canonical encoded bytes and its
SHA-256 tagged digest. `encode_event(...)` validates and seals an exact v1
envelope; `decode_event(bytes, *, expected_digest) -> AccountingEvent` rejects
noncanonical JSON, unknown kinds/version, extra/missing fields, unsupported
scalars, oversized body and a digest mismatch. The expected digest is an
independent input from the event carrier; hashing bytes alone does not prove
that an event was not removed or replaced. All errors are fixed codes with no
caller content.
The envelope carries `schema_version=1`, ledger UUID/generation,
experiment UUID, contiguous `sequence`, `previous_digest`, event UUID,
RFC3339 UTC timestamp, actor kind and one exact typed body. The encoded top
level has exactly `schema_version`, `ledger_uuid`, `ledger_generation`,
`experiment_id`, `sequence`, `previous_digest`, `event_id`,
`recorded_at_utc`, `actor_kind`, `event_type`, `data`. The digest is external
to these bytes and covers the
whole envelope with a distinct accounting domain tag. Maximum event body is
16,384 bytes, sequence is 1..2**53-1, and all IDs are canonical lowercase
UUIDs. Every digest is exactly 64 lowercase hexadecimal characters, and
timestamps are exactly `YYYY-MM-DDTHH:MM:SS.ffffffZ`, parsed as UTC without
leap seconds. Signed int64 money is exact `int` (never bool) with explicit
`currency: "USD"`; reservation values are nonnegative. `Week` is exactly
`{key, start_utc, end_utc, timezone}`, with 18a's fixed New York structural
validation. A profile triple is exactly `{model_id, auth_id, venue_id}`.
Nullable fields are present with JSON null, never omitted. The only actor in
this source subset is `receiver` or `fixture`;
`fixture` can never be elevated to evidence provenance. The codec imposes no
physical durability or storage identity proof.

Closed kinds and exact `data` keys (no extra or missing keys):

1. `genesis`: `policy_revision` fixed `accounting-v1`, `population` one of
   `unknown|synthetic_complete`. Ledger UUID/generation and experiment ID live
   in the envelope. Sequence
   1, zero previous digest. `synthetic_complete` requires the `fixture` actor
   and is test-only. `receiver` genesis must say `unknown`. This closed v1
   format has no trusted history-attestation transition. Before 18c can use
   it to reserve, a separately reviewed compatible version/transition and
   verifier must bind an external authoritative opening manifest, provider
   coverage and cost population to the ledger head. Until then, even a
   durable store of these v1 events cannot admit a production attempt.
2. `journal_bound`: `journal_uuid` UUID, `journal_generation` int in
   1..2**31-1. Each new binding becomes
   the active origin for later reservations. A binding previously seen in
   this experiment is idempotent only as an exact event replay; a new event
   reusing it or stepping back to it refuses. Historical bindings and their
   rows remain in the projection.
3. `profile_configured`: `profile` triple, unique as a triple.
4. `lifecycle_registered`: `lifecycle_id` UUID, `slot` one of
   `rehearsal_1|rehearsal_2|rehearsal_3|presentation`, `week` Week,
   `profile` triple, `journal_uuid` UUID, `journal_generation` int.
   Its origin must equal the active binding when registered. Preserve the
   stored Week bytes, including DST endpoints. A later binding does not
   transfer the lifecycle to that origin; a reservation under a new binding
   cannot use an older-origin lifecycle. Register a fresh lifecycle in an
   unused week/slot, or hold until a future reviewed continuity transition.
5. `non_model_committed`: `cost_id` UUID, `kind` one of
   `support|review|venue`, `upper_bound_usd_micros` int64,
   `valid_until_utc` timestamp, `currency` fixed `USD`. It remains U in this
   unit; no settlement path.
6. `reservation_created`: `journal_uuid` UUID, `journal_generation` int,
   `admission_id` UUID, `intent_id` UUID, `intent_digest` hex64,
   `attempt_id` UUID, `reservation_id` UUID, `run_id` UUID, `lease_id` UUID,
   `kind` one of `initial|retry|diagnostic`, `lifecycle_id` nullable UUID,
   `predecessor_id` nullable UUID, `effects_reconciled` exact bool,
   `profile` triple, `week` Week, `reservation_usd_micros` exactly 3,000,000,
   `liability_usd_micros` int64 at least R, `currency` fixed `USD`,
   `valid_until_utc` timestamp and `policy_revision` fixed `accounting-v1`.
   The envelope previous digest is the sole expected
   predecessor head. No receipt field. The future bridge must independently
   verify that the admission and intent committed at that journal origin and
   digest; pure replay cannot do so.
7. `hold_set`: `hold_id` UUID, `code` one closed 18a hold code. Holds accumulate
   with no clear event in 18b.

This is a conservative subset. No provider charge line, actual coverage,
refund, credit, hold clear, archive, lease, launch or terminal event. Unknown
future event kinds refuse replay. `non_model_committed` is an assertion in a
synthetic history, not a verified cloud/venue charge.

## Projection and transition interface

`replay_accounting(events: tuple[AccountingEvent, ...]) -> Projection` starts
only at one genesis; an empty tuple refuses `history_unavailable`. It verifies
codec/digest, single identity, strictly contiguous sequence, exact previous
digest and nondecreasing UTC event times before applying semantics. A new
reservation timestamp must strictly exceed the preceding reservation's
timestamp, as 18a requires. If a future writer observes a backward clock, it
must hold and obtain a later valid instant; it cannot silently bump the time
or reorder recorded events. Receipt occurrence time is separate and deferred.
`Projection` is frozen and contains ledger/experiment identity, current
head sequence/digest, population status, journal bindings, profiles,
lifecycles, costs, attempts with their full journal origins and admission/
intent references, sticky holds, and all seen event/identity digests. No
mutable caller collection escapes. If input ends at any valid prefix, the
projection says only what that prefix proves; it cannot assert that a later
event did not exist in durable storage. The future adapter compares a verified
physical anchor before treating the prefix as current.
`replay_accounting` refuses duplicate sequence/event IDs even for identical
bytes; idempotency below applies to an individual `apply_event` call, not a
duplicated row in a complete event stream.

`apply_event(projection, event, *, expected_head) -> Projection` first checks
that expected_head exactly matches the current head, then validates the event
and recomputes the transition. Its only idempotent duplicate case is a call
with the *current* head and an already seen event ID plus exactly identical
encoded bytes; it returns the same projection without advancing. Changed
bytes under that ID refuse `event_conflict`. A repeated configuration with a
new event ID is a configuration conflict. Gaps, forks,
identity reuse across roles, changed journal bindings/configurations, or
unbound admission references refuse. A repeated reservation/intent identity
with any changed content refuses; exact replay does not count again. Multiple
new events at one head require sequential application; no caller-supplied
aggregate or cached proposal is accepted as state.

For `reservation_created`, require its origin to equal the active journal
binding, its referenced lifecycle (if any) to originate in that binding,
and the admission/intent pair to be fresh in that binding.
The `effects_reconciled` value is only a synthetic assertion; the later bridge
must prove it from the verified journal. Build the 18a `Snapshot` from *all*
projected rows at the event timestamp, with that active journal generation. Preserve
and validate all older origins in Projection before building 18a's single-
generation view. Recompute `Candidate` and call `evaluate_reservation` at
that timestamp. Require a `HypotheticalProposal`, then compare its Week,
R/U and candidate facts to the event exactly. The policy's 512 lifetime
attempt limit is enforced on full history; the 513th attempt refuses even if
settled rows would later be archived. Events do not store or trust Totals.
For a synthetic-complete genesis, reservation is possible only after a bound
journal and configured profile/lifecycle; an unknown population refuses.
Each reservation requires a distinct admission/intent pair and ID set.
Run IDs remain unused for launch.

The event envelope's head and data are deterministic replay inputs. Pure
`apply_event` does not mint IDs, authenticate the source of an event, serialize
writers or commit data. A future ledger adapter must establish current head,
opening history/configuration/U provenance through a separately reviewed
format extension and verifier, exclusive writer lock, event capacity and
repair headroom, re-evaluate before committing, then read back. The 8,192-event
and 512-active proposals in ticket 38 are not claimed by this pure subset.
Pure replay limits input to 8,192 events solely to bound calculation, never
to certify storage capacity. In 18c, admission must budget independently for unbounded-in-
principle billing/control/repair needs or hold at a reviewed safe threshold;
four reserved future event slots alone are insufficient.

## Required tests and acceptance

- Independent exact-byte codec fixtures: canonical round trip, version/kind/
  actor/ID/money/time bounds, missing/extra fields, altered digest, body cap.
- Deterministic replay of the same bytes; gap, fork, duplicate event/intent/
  attempt IDs, changed duplicate payload, stale expected head and altered
  reservation R/U/Week all refuse. A valid prefix never claims physical
  completeness or launch authority.
- Synthetic-complete genesis plus registrations and one reservation produces
  independently known $3/U/weekly/lifetime amounts through 18a. Unknown
  genesis, missing binding/profile/lifecycle, stale U and sticky holds refuse.
- Old-week and old-generation reservations stay in lifetime liability; new
  journal binding cannot reset it. Lifecycle registration against an inactive
  binding and use of an older-origin lifecycle after rebinding both refuse.
  Retry same-profile/original-week dual attribution and cross-week refusal.
  Independent attempt-count limit proof through 18b replay is unreachable
  without settlement: ten U>=$3 attempts already exhaust the $30 lifecycle
  spend ceiling, and another attempt refuses spend first. The 18a settled-
  history tests retain count-limit coverage; a future reviewed settlement
  transition must prove these limits again through replay.
- Nonmodel U contributes to lifetime cap only. A zero process-cost assertion,
  estimate or terminal signal has no event and cannot reduce exposure.
- 8,193 replay inputs refuse without dropping earlier entries. The 512
  lifetime-attempt guard is retained from 18a but unreachable in this
  no-settlement subset because U >= $3 and the strict $50 cap blocks earlier.
  Its end-to-end transition test is deferred until a reviewed settlement
  transition can construct coherent low-actual history; this unit does not
  claim that test or 512-active durable capacity.
- Static checks: no application imports or changed legacy/journal source;
  no receipt/permit/launch method. Focused tests and full suite with opt-in
  end-to-end/container flags unset; full suite before a code commit. Ruff,
  E501, whitespace, prior artifact/protected hashes and fresh independent
  review. Local pure/synthetic scope only; durable, live, provider, tenant,
  paid and human qualification NOT RUN.

## Reconciliation gate

An independent critic found seven blocking ambiguities in the first draft.
The current text defines external expected-digest checking, matching-head
idempotency order, active journal origin, synthetic effect/provenance claims,
pure input bounds, and the missing production attestation transition as an
explicit 18c prerequisite. Before implementation, recheck HEAD, existing
source identity and protected hashes. Make red/green regressions for confirmed
findings. The 18c/18d bridge contract in the design decision remains mandatory
before any Run lifecycle work.

The critic's second pass found a lifecycle-origin gap. Registration now
requires the active binding, and a later binding cannot reuse that lifecycle;
both refusals are explicit acceptance cases. The critic's final verdict is
ACCEPT for this pure/synthetic plan only. No 18b tests or source have run at
this plan checkpoint.

## Implementation review reconciliation

The first local red/green pass exposed test setup and identity gaps. Independent
review then found that public Projection fields could be forged against the
event history, current event IDs could collide with body IDs, malformed dates
could retain caller text in exception context, and valid histories outside
18a's year range leaked a different exception class. Public apply now rebuilds
from its event chain, checks the expected head first, and returns only closed
transition errors. Role-aware profile identities and admission origin checks
preserve repeat use only in the same role and journal origin. Immutable
projection indexes avoid reparsing every prior event for each new event.

The accepted 18b subset remains deliberately without settlement, so 512
lifetime attempts and attempt-count ceilings cannot be reached with coherent
U>=$3 history before spend caps. Their end-to-end replay proofs are deferred
to the settlement unit; this does not relax either policy check. All other
required codec/replay, old-week/generation, retry attribution, stale U,
missing configuration, and input-bound cases are now represented in the
focused tests. Final full-suite and hash-bound verdict are recorded in the
separate outcome/validation artifacts after they complete.
