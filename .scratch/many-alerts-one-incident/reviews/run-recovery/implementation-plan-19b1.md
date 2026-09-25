# Unit 19b1 exact plan: no-dispatch Run hold records

Status: proposed for source review, 2026-09-24. Baseline: `0cb62e8`.
Design: `design-19b-v2.md`. This unit adds replayable Run hold evidence to
the Receiver journal. It does not add a production caller, attempt,
reservation, lease, process, Forwarder request or permit. The legacy
admission-only front door remains the only integrated Receiver path.

## Contract and capacity

Register exactly one new pair, `(run_hold, 2)`, with `receiver` actor. Existing
version 1 pairs, validators, JSON bytes, digests and goldens stay unchanged.
`seal` gets an explicit version argument defaulting to 1; decoded `Record`
retains its actual version, and `content_digest` uses that version. A v2
record is still framed and chained in the current store. Older binaries must
stop at `journal_schema_unsupported` without persisting a corruption hold.

The v2 record has `ids={job_id, admission_id}`. Its data has exactly:

- `rule: "run-hold-v2"`;
- `reason`: one of `accounting_unavailable`, `restart_recovery`,
  `venue_unready`, `reference_revoked`, `operator_review`,
  `required_effect_unknown`;
- `based_on_commit_seq`: the prior committed head;
- `pending_digest`: the current v1 pending digest;
- `member_count`: one to 32 current pending Fingerprints for the named
  admission;
- `member_digest`: tagged digest `rj.run-hold-members.v2` of those
  Fingerprints sorted as an array.

The planner can select only an admission still present in the pending
projection. It accepts one hold per admission and never reuses a job ID. The
record declares a hold; it cannot clear one or authorize dispatch. Later
admission/pending reduction must not erase the held job. This unit has no
effect record, so `required_effect_unknown` is a conservative reason only;
it does not claim a particular effect was dispatched.

At most 1024 `run_hold` records may be committed in a generation. Each body
is at most 2048 bytes, charged as recovery-class under the existing `total_bytes`
limit. The worst body-plus-overhead charge is 2,490,368 bytes across the
family, leaving more than 13 MiB of the current 16 MiB recovery reserve for
other recovery evidence when ordinary bytes are full. A limit or byte refusal
is a closed no-write result; the absent record is never treated as a completed
hold. Future writers must latch dispatch and surface capacity/backpressure.

The v1 `rj.state.v1` digest formula remains unchanged. A separately tagged
`rj.run-holds.v2` digest commits the sorted job/admission/reason/sequence
projection. The projection is visible to tests and verify-only inspection;
it cannot be used as a launch gate. A future writer must bind the hold reason
to the relevant ledger, venue, reference or effect evidence before admitting
any operation that depends on it.

## File-by-file execution

1. Add tests first for v2 exact type validation, default-v1 byte parity,
   content digest version, future unknown pair, and sanitized rejections.
   Add mixed v1/v2 replay tests: head/chain/framing, duplicate job and
   admission rejection, forged `pending_digest`, non-current admission,
   membership digest, capacity boundary, admission after hold, restart,
   full-history reopen and unknown future pair as a process hold.
2. Extend `journal_records.py` with the pair and explicit versioned sealing.
   Do not change any version 1 validator or tag. Bound the v2 body to 2048
   bytes after canonical encoding and reject larger decoded bodies.
3. Extend `journal_reducer.py` with a pure planner and verifier, an additive
   hold projection and independent v2 digest. Admission and front-door
   transitions leave the hold projection unchanged. The verifier re-derives
   prior commit, pending membership/digest, IDs, uniqueness and capacity.
4. Extend `recovery_journal.py` only enough to replay and inspect a mixed
   history. Do not add a public append method. Verify-only inspect reports
   held job count and v2 digest without serializing raw source or prompt data.
5. Update `docs/recovery-journal.md`. Run focused tests, Ruff and source
   checks, two-axis independent review, then the full repository suite with
   demo flags unset before the local code commit. Record hashes, preserved
   uncommitted read-back, test counts and `NOT RUN` boundaries.

If review finds that one new pair cannot be replayed with v1 admissions and
the current store without changing frozen v1 semantics, stop this source
unit, record the precise conflict, and revise the design before coding.
