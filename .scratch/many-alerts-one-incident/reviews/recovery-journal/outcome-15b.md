# Unit 15b recovery journal reducer and shell outcome

2026-09-23. PASS for the second part (15b) of the fifteenth separately authorized
local application unit, baseline `f68c9aa` (unit 15a).
[validation-15b.json](validation-15b.json) records the final verdict and
evidence. The work is local only: nothing was pushed and no planning ticket was
closed.

## What the unit adds

The ticket-37 recovery journal is now usable as a component ([docs](../../../../docs/recovery-journal.md)). It is still not wired into the Receiver.

**`journal_reducer`.** A pure fold makes every decision:
- ticket-31 dedupe: the latest admitted key per source group, and truncated arrivals never suppressed;
- pending reduction per Fingerprint, keeping every superseded identity, with cross-group reclaim that never creates an entry;
- capacity checks before crossing, never evicting, with one hold per code;
- restart recovery.

`verify_commit` re-derives every planned or stored commit, so live decisions and replay are identical, and a re-signed semantic change is caught with a fixed replay code.

**`recovery_journal`:**
- **`create`** refuses before writing anything invalid.
- **`open`** verifies the whole chain and replays it before applying anything. It adopts at most one unanchored commit (re-anchoring before `restart_recovery`) and persists every verified integrity failure. It returns a held, readable handle for every other finding, and closes the store on any failed exit.
- **`admit`** runs under one lock. It returns an `AdmissionReceipt` only after the COMMIT and the anchor sync, and applies the result to memory only afterwards. Clock, ID, capacity and write failures latch fixed process holds.
- **The snapshot** has a fixed shape, contains nothing secret, and is JSON-encodable. Its projection fields are null while held.

## Review

- Testers E and F found two source bugs and pinned both with failing tests.
- Four Opus lens reviewers found the shell's unguarded open exits and six lower-severity items.
- An Opus fixer fixed all eight, and every new test fails against the pre-fix sources. A gap agent closed eight test gaps, killing 13 mutants, and cut the property test from 20-28 s to about 3 s.
- A fresh reviewer bound the hashes: PASS, with no blocking finding. Root fixed two small source items (a monotonic-clock bound, and locked state properties) and the documentation overclaims. A second gap agent closed the review's test items and killed 17 mutants, including a fix to the bit-flip test's ready branch, which had checked nothing. The same reviewer re-verified the result ([review](review-15b.md)).

## Validation

- Unit tests: **213 passed** in the four 15b files, over repeated runs.
- [Focused suite](focused-tests-15b.txt): **689 passed, 2 skipped**. It covers all seven journal files, `forwarder_json`, the receiver and the replay.
- [Full suite](full-suite-15b.txt): **4012 passed, 38 skipped in 237.36s**, exit 0. This is plain `pytest -q` with nothing excluded; 15a's full suite was 3799 passed, 38 skipped.
- Ruff (including line length on the sources), compile and `git diff --check` pass. No committed module or test changed; only the plan's root notes and `docs/recovery-journal.md` changed among tracked files.

## Not qualified

- Receiver integration and raw Notification ingress; the HTTP status mapping (the ingress unit's decision);
- Run, spawn, effect and terminal records; ticket-38 reservations; operator actions (cancel, resume, reset); retention, compaction and reconstruction;
- consumption of pending work and clearing of dispatch holds;
- device flush honesty, venue durability, Linux behavior and isolation of the journal from Runs;
- detection of a consistent rollback of every file or of a same-uid anchor forger;
- ratification of the proposed v1 limits, fields and semantics (the plan's "Proposals requiring ratification").

## Not performed and next

No provider, tenant or native call was made. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

Next is Receiver integration of the journal (ingress sanitization, admission before the 202, and the replay-fixture consequence), then Run and effect records and ticket-38 accounting. Ticket 37 remains open.
