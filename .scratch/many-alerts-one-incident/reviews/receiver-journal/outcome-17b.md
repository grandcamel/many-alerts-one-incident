# Unit 17b journaled front door: outcome

2026-09-24. **PASS_LOCAL_JOURNALED_ADMISSION_FRONT_DOOR**, baseline `c3e4f3a`.
[Validation](validation-17b.json), [review](review-17b.md) and
[operator documentation](../../../../docs/recovery-journal.md#front-door-journaled-admission-only)
record the local boundary. Ticket 37 remains open. Nothing is pushed.

The opt-in `journaled_receiver` retains each exact Notification body in a
private content-addressed spool, syncs file and directory before journal
admission, then sends a seven-key 202 receipt with `run: not_dispatched`.
It deduplicates and records bounded refusal summaries and exposes code/count
health. The operator CLI explicitly creates state and performs verify-only
inspect with a spool survey; resume is bound to the inspected head at startup.
No Run starts and no Incident is created in journaled mode. The legacy command,
all its modules/tests and both journal goldens remain unchanged.

Independent contract, durability/custody, HTTP, identity and test reviews found
and repaired short-write/close/FIFO failures, persistence and path-custody
errors, missing diagnostic/startup behavior, and test gaps. A fresh final
reviewer bound hashes and reverified its five findings. Mutation evidence
covers source rules and repaired test gaps; the first broad run's four crash
failures were a buffered-output test-reader defect, subsequently repaired.

- Focused: **1645 passed, 30 skipped**, guarded;
  [log](focused-tests-17b.txt).
- Full: **4939 passed, 39 skipped** in 372.18 s;
  [log](full-suite-17b.txt). Skips are baseline 38 plus the declared spool Linux
  sync branch on Darwin.
- Ruff, source line length, whitespace, identity diffs and protected hashes pass.
- Source size 1,436 lines, accepted by independent review after the 17a/17b split.

**Not qualified:** device power loss/flush honesty, Linux no-read delivery,
real Grafana status/retry behavior, deployed storage, same-uid isolation,
authenticated operator identity, Run lifecycle, effects, accounting, reset,
retention, reconstruction, online operator control, native client/provider/
tenant execution, paid experiments and human Report adjudication. Source
choices remain proposals under the existing ratification boundary.

Next is the accounting reservation prerequisite for Run lifecycle. The queue's
reservation gate is not satisfied by this unit; no no-reservation dispatch
profile is inferred. Four protected dirty files and panel working material
remain outside the commit.
