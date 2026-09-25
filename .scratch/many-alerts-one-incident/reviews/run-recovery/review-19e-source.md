# Unit 19e worker-supervision reducer source review

Status: independent Standards and Spec reviews PASS, 2026-09-25.
Baseline: `2faddfe`. Reviewed source, tests, docs, ticket and plan.

Both reviewers found that the first reducer could revoke after an early parent
exit but then wait until the ordinary 270-second boundary to interrupt live
descendants if the caller omitted an early stop timestamp. The decision now
returns the observed timestamp for retention alongside the revocation attempt;
the next step rejects a missing retained timestamp and uses the pinned time
through the sole 19c schedule. Regression: exit at 5 seconds, interrupt at 6,
kill at 25 and hard boundary at 35. Both reviewers read back the correction
and confirmed PASS. Focused tests: 24 passed. Ruff: passed.

The review covers pure decisions over supplied observations. It does not
establish actual startup containment, stable group identity, bounded callbacks,
Forwarder closeout, authenticated/durable timestamps, native-client behavior,
Run execution or external effects.
