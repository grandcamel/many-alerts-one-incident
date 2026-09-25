# 18d3b: verified negative reservation scan

Status: proposed local design, 2026-09-25. Fixed point: `bf3c141`.
Authority: ADR 0013, tickets 37/38, 18d1 pure hold comparator, 18d2
journal claims and 18d3a verified read-only views. This unit does not
reserve, append, confirm, permit, dispatch or launch.

## Purpose and result

A new `reservation_scan` shell accepts only journal and ledger directory
paths plus a target intent ID. It invokes both 18d3a views itself, then
passes replayed journal claims to 18d1's pure comparator. It returns a
frozen `ScanAssessment(hold=True, reason=...)`; no caller can
provide a projection, ledger receipt, `read_back` flag or synthetic fact to
this shell. The scanner never returns a token or amount. It is an observation
of two stopped local images, not an atomic cross-store snapshot or a lease.

The current v1 ledger view can prove only Receiver/`unknown` and an empty
reservation tuple. The scanner requires that observable shape; a different
population or nonempty tuple holds as `ledger_unsupported`. The view has no
format discriminator, so a future same-shaped store/view change requires a
paired scanner review rather than a claim of automatic detection. Thus
`missing_ledger` is the only counterpart outcome for a
verified journal intent. A journal confirmation without a ledger event is
also held; the journal's claim cannot authenticate spend. There is no
positive SQLite triple, matching-unqualified scanner result, production
reserve or permit in this unit. 18d1's pure synthetic positive comparator
retains its explicit synthetic label.

## Fail-closed order

Validate the target ID with 18d1's closed validator before opening either
store by calling `assess_bridge(target_id, (), (), ())`. Map its fixed
`BridgeError` to the `bridge_invalid` hold. Inspect the journal first. Any
held or unverified journal view returns `journal_unverified` and exposes no
facts. Inspect the ledger next. Any held or unverified ledger view returns
`ledger_unverified`; a ready result with a different population or nonempty
reservations returns `ledger_unsupported`. Only two ready views reach the
comparator. Map each journal intent's origin, admission/intent, attempt,
reservation, Run, lease and intent digest fields into `JournalIntent`; drop
the job and commit metadata. Map each confirmation's `ledger_event_id` to
`JournalConfirmation.event_id`, retaining its intent and ledger identity,
sequence and digest; drop its separate journal `confirmation_event_id`,
intent digest and commit metadata. Do not infer a ledger reservation from a
journal confirmation. Map any comparator `BridgeError` to `bridge_invalid`.

The scanner's closed reason set is `bridge_invalid`, `journal_unverified`,
`ledger_unverified`, `ledger_unsupported`, `missing_intent`,
`missing_ledger`, `identity_conflict` and `scan_invariant`. The comparator
reasons on the current verified v1 input shape are `missing_intent`,
`missing_ledger` and `identity_conflict`. An unexpected comparator result
becomes scanner-generated `scan_invariant`, still held.

The views may create an absent `lock` file under their existing rules and
otherwise verify without writes. The scanner itself performs no file I/O
outside invoking those views. A concurrent image change cannot make a
permit because every outcome remains a hold; the scanner does not claim
simultaneous snapshots. It may report a conservative unverified result or a
bounded observation that is stale immediately afterward.

## Deferred boundaries

A production reservation path needs authenticated complete opening history,
provider line identity/coverage/lag, defensible U, continuity witness and
archive/repair policy. A future compatible ledger format needs a separate
source design, migration and verified positive view before the scanner could
even describe a matching durable triple. No such path is authorized here.
