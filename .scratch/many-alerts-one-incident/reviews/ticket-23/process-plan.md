# Ticket 23 fixed-process harness plan — 2026-09-21

Continue with a real POSIX-process binding restricted to reviewed local Python fixture
scenarios. No arbitrary command/model launcher, container, credential read or network
operation is authorized by this step. Preserve production and rejected C2 source.

1. Implement a supervisor and fixed fixture worker under `prototype/run_timing`. Start
   a fresh process group with a minimal environment, explicit work/flush/reap bounds,
   nonblocking capped stdout/stderr, and exclusive attempt-directory creation.
2. Use real local fixture processes to test success/failure, silence, cancellation,
   ignored SIGINT, held pipes/descendants, oversized output and output collisions.
   Test budgets may be shorter than 270/20/10, never longer.
3. Run targeted and full tests, then independent Standards/Spec and one fresh bounded
   Fable review of this new source batch. Do not retry the prior timed-out review.
4. Record real observations and remaining gates. Process-group evidence covers only
   these cooperative fixed fixtures; it does not establish confinement against escaping
   descendants, model-client compatibility, Forwarder mediation or venue qualification.

The output parent is a trusted operator-owned test directory. This is not the private
production audit store or a general filesystem security boundary. Native model launch
remains CLOSED regardless of the fixture result.
