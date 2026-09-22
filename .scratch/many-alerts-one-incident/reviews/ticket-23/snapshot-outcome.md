# Ticket 23 — retained timing snapshots

2026-09-21. **TRUSTED SYNTHETIC SNAPSHOT / NATIVE LAUNCH CLOSED.**
Baseline: local commit `3e535c2`.

The [snapshot adapter](../../../../prototype/run_timing/timing_snapshot.py) preserves the
exact retained query responses, dispatch/effect receipts, every committed Report revision,
current Incident and virtual Lifecycle observation in one bounded operator-only bundle.
References resolve after the original adapters are gone; read-back does not rerun queries
or restore a writable adapter. Capture neither admits work nor completes pending effects.

The [contract](../../../../prototype/run_timing/TIMING_SNAPSHOT.md) limits the snapshot to
16 MiB and manifest to 4 KiB. Publication uses a new private directory, exclusive files,
fsync and a final hard-link manifest; collisions are refused and failures preserve partial
files. Read-back checks byte digests, record identities/counts, query provenance metadata,
reference targets, revision history, effect links, current revision and hold/pending state.
Directory ancestry and interpreter are trusted. Hashes establish comparisons, not authenticity.

Pending and unknown outcomes remain pending/unknown, including an unknown-after-apply revision
visible to the operator. Missing rejected requests, candidate-read observations and unapplied
proposal bodies are explicit gaps. Audit completeness always remains NOT_ASSESSED. Claim
support, semantic correctness, native provenance, billing and human grading are not inferred.

## Validation

Final focused snapshot suite: **60 passed in 0.52s**. Final full suite: **635 passed,
36 skipped in 29.11s**. Ruff and diff whitespace checks passed. The initial integrated
snapshot/query/Incident check passed 142 tests, before the seven review regressions.
Tests cover round-trip retention, detached copies, empty/pending/revoked/held/unknown states,
malformed records and checked links, collisions, failed publication, nonregular/symlink/FIFO
or oversized files, and read-back without query execution or adapter reconstruction.

The retained example bundle holds two responses and one committed revision after an
unknown-after-apply effect. Read-back preserves `unknown`, the hold and NOT_ASSESSED audit
completeness. It is a synthetic storage example without a diagnostic claim or human grade.

## Standards

Initial review found one malformed-input exception defect: `10**400` as a lifecycle time
escaped as OverflowError. The validation boundary now normalizes it to EvidenceUnavailable;
regressions cover direct validation and persisted read-back. Final correction read-back found no remaining Standards blocker.

## Spec

Initial review found the same timestamp defect and a missing current-revision check: an
Incident with revision zero and no retained revision could pass. The Incident-present branch
now requires a nonempty revision inventory; a rehashed malformed-snapshot regression rejects
it. Final correction read-back found no remaining Spec blocker.

The fresh bounded Fable review returned **PASS** on the frozen initial source, with three
optional findings. Its zero-revision Incident finding duplicated the Spec finding; the other
link suggestion led to a third fix: revisions must follow increasing dispatch order. A regression
keeps individual links consistent while reversing order and confirms rejection. The pending
proposal-body omission is now explicit, and additional invalid-time cases have controlled
errors. Standards and Spec read back all final corrections; Fable was not rerun.

The reviewer reported `claude-fable-5-1`, a $2.033722 session estimate and no provider actuals.
This source review is separate from any timing/length model experiment. Raw results and
correction adjudication are retained; the verdict does not supersede the internal defects.

[Validation receipt](snapshot-validation.json) records source hashes, review dispositions,
test evidence and unrun boundaries. Raw reviews and example files are outside Git under
`/Users/jasonkrueger/maoi-ticket23-evidence/20260921-timing-snapshot/`.
The preceding manifest and **69 indexed files** were read from `3e535c2`, verified against
its byte counts/digests and archived at that root's `prior-phase-snapshot/`. The new packet
manifest supersedes that inventory without rewriting historical validation receipts.

Native tool transport/authentication, adversarial isolation, production custody/sanitization/
expiry/quotas, full durable-closeout deadline, writable recovery, human grading and provider
billing remain unimplemented or NOT RUN. Paid timing/length execution and model/tenant/venue
qualification remain CLOSED. Ticket 23 stays open; tickets 38/39 are not completed by this work.
