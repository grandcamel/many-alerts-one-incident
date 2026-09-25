# 19e pure worker-supervision reducer plan

Status: local source plan, 2026-09-25. Baseline: `2faddfe`.
Authority: ADR 0012, ticket 37, the reviewed 19d design and 19c deadline
policy. This unit is a deterministic decision reducer over caller-supplied
observations. It creates no process, lease, Run, permit or Forwarder action.

1. Add a frozen state and observation vocabulary with exact scalar/enum/boot
   validation. An observation separates root exit/reap, stable group identity
   and presence/absence, actual pipe EOF, capture completeness, lease
   revocation acknowledgment and Forwarder closeout. Unknown is never absence.
2. Use `assess_supervision` as the only clock schedule. Return at most one due
   action per step: revoke first at stop/work deadline or early completion,
   then SIGINT when the revocation attempt is recorded, then SIGKILL at the
   flush boundary for a still-present verified group. Never repeat an attempted
   action or emit a new action at/after the hard deadline. Failed revocation
   cannot be interpreted as a dispatch fence, but signaling may still proceed
   to contain the worker. An early parent exit with possible descendants must
   return an observed stop timestamp and reject the next step if that timestamp
   is not retained. No caller-selected command or process group enters the policy.
3. Classify a closeout only when the root is reaped, independently verified
   stable group absence, actual stdout/stderr EOF, complete capture, acknowledged
   revocation and closed Forwarder closeout are all present. Return descriptive
   fixed gaps otherwise. This assessment does not durably release a Run hold.
4. Exercise silent and successful synthetic observations, early exit/failed
   start with an installed lease, stop and 270/290/300-second edges, ignored
   SIGINT, parent exit with descendants/pipes, revocation failure,
   draining/overdue/unknown closeout, group/pipe/capture gaps, boot mismatch,
   malformed inputs and action idempotency. Update ticket 37 and docs.
5. Run focused tests and Ruff, independent Standards and Spec reviews,
   protected dirty-file read-back and the full suite before a local commit.
   Stage only named 19e files.

Physical startup barrier, stable containment identity, bounded callbacks,
nonblocking capture, actual Forwarder closeout and durable journal handoff
remain later local integration work. Native/provider/tenant/venue evidence is
outside this unit and remains NOT RUN.
