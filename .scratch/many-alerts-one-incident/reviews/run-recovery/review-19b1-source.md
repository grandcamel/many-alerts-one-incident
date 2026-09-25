# Unit 19b1 source review

Status: independent read-only Standards and Spec reviews of the local 19b1
diff, 2026-09-25. Fixed point: `e464555`.
Reviewers did not edit files or run tests. Parent validation is recorded
separately.

## Standards axis

No concrete correctness, compatibility, security or maintainability blocker
was found in the bounded v2 pair, replay derivation, mixed-history inspection
and tests. An initial full-suite run exposed the legacy front-door tests'
exact v1 registry pins. The new pair was moved into separate private v2
tables, leaving the public v1 registry and `SCHEMA_VERSIONS` exact. The
formerly failing block then passed 353 tests. The Standards reviewer
rechecked the correction and found no new blocker.

## Spec axis

No false-success, replay, identity, capacity or v1 compatibility defect was
found in this no-dispatch unit. The reviewer identified a test gap against
the written matrix: direct checks for content-digest versioning, a forged
membership digest and decoded-body size. Those assertions were added and
the reviewer rechecked them as resolved, with no new concrete blocker.
The Spec reviewer also rechecked the registry correction: only `(run_hold, 2)`
is accepted through the new table, while unsupported pairs retain the
non-persisted schema process hold.

## Authority boundary

The v2 `run_hold` projection is descriptive and per job. It is separate from
the global `dispatch_holds` projection and has no application writer. A future
writer and permit gate must bind and check both; a failed hold append must
latch dispatch and surface capacity. This review does not accept a Run launch,
reservation, cross-store handshake, effect receipt, Forwarder request,
native/provider/tenant/venue behavior, paid execution or human adjudication.
