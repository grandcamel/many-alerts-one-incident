# Unit 18c-storage source review

Status: independent read-only Standards and Spec reviews of the local
18c-storage diff, 2026-09-24. Fixed point: `221dab94c8828b101bb1f3a35bbe131e0b1d23bd`.
Reviewers did not edit files or run tests. Parent validation is recorded
separately in `validation-18c.json`.

## Standards axis

Initial findings were a leaked writer lock if SQLite close raised and an
unused retained event index. Recheck also found cleanup leaks in failed open
and inspect and an unchecked SQLite error during duplicate lookup. The source
now releases SQLite and lock handles independently, returns fixed cleanup
codes, removes the unused index, and latches the store on duplicate-lookup
I/O failure. The final Standards verdict found no concrete remaining source
blocker.

## Spec axis

Initial findings were missing-anchor misclassification and malformed v1
anchor fields treated as a newer format. Both are corrected: absent anchor
rederives `ledger_anchor_missing` without repair, malformed v1 fields derive
`ledger_anchor_invalid`, and explicit future format remains a process hold.
The reviewer then identified missing cases in the exact storage-only test
matrix. Focused tests now cover schema and custody variants, both anchor
slots, crash ordering and SIGKILL, malformed and repeated-identity events,
sanitized failures, and the actual 8192-row boundary. The final Spec verdict
found no concrete remaining blocker in the source/test diff, conditional on
the parent-run test gate and evidence record.

## Authority boundary

This review addresses only the Receiver-owned 18c-storage module and local
tests. It does not review or accept production reservation, trusted opening
history or provider coverage, the 18d journal/ledger bridge, power-loss
durability, native/tenant/venue behavior, paid execution, or Run launch.
