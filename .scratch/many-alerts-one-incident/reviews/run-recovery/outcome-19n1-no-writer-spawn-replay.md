# 19n1 outcome: unqualified spawn/release claim replay

Date: 2026-09-25. Fixed point: `fd4e046`.

The reviewed [design](design-19n1-no-writer-spawn-replay.md) and
[implementation plan](implementation-plan-19n1-no-writer-spawn-replay.md)
add private v3 `spawn_attestation`, `release_intent` and
`release_observation` codecs, pure planning/replay and stopped/live
inspection. The source binds each phase to the current head and exact prior
claim, same boot and ordered monotonic evidence. Pre-release phases reject
new holds and elapsed work deadlines. A historical release observation may
append after a hold or hard deadline but never clears either. Record charges
use ordinary, ordinary and recovery capacity respectively. Inspection shows
the latest claimed phase and a separate digest under
`outstanding_unqualified_launch_claim`.

Independent Standards and Spec document reviews and source reviews pass
after corrections to timing, capacity escrow, activation order and explicit
inspection phase. Focused journal regressions: **317 passed, 2 skipped**;
15 direct 19n1 tests pass. Changed-file Ruff and `git diff --check` pass.
The full local suite: **5,573 passed, 39 skipped in 392.31s**. Tests include
forged recomputed records, each crash prefix, held/late observation,
capacity edges, real-store read-back and older-decoder refusal.

These are replayable **claims**, not a writer, stable containment witness,
protected anchor, capacity escrow, child, release byte, grant activation,
effect, permit or Run acceptance. A future writer still must reserve the
8,960 ordinary and 2,432 recovery bytes for these records plus separately
specified action/terminal/reconciliation space before child creation. The
ledger remains `population=unknown`; current mutation routes remain
unavailable. Native, provider, tenant, paid, venue and human acceptance are
**NOT RUN**. Ticket 37 stays open.
