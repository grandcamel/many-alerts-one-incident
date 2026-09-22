# Ticket 23 retained timing snapshot plan

Baseline: 3e535c2. Preserve the existing trusted in-process query and Incident records in a
bounded operator-only local snapshot. This is not a native audit store, recovery journal,
semantic Report validator or production retention implementation.

1. Add detached operator snapshots to TimingQueries and TimingIncidents. Include every retained
   response, dispatch, effect and committed Report revision, current state and correlation IDs.
   Shared single-threaded state makes capture coherent within this trusted process. Do not
   issue queries/writes, complete pending work or clear holds while capturing.
2. Validate record digests and bounded counts/sizes, query/store identity, notification linkage,
   dispatch/effect/revision links and every Report reference. Preserve pending and unknown
   outcomes, including an applied revision whose effect remains unknown. Do not infer success
   from integrity, absence, or operator-visible state; do not re-run queries or grade claims.
3. Publish a <=16 MiB canonical JSON snapshot and small digest manifest in a newly created
   private directory. Refuse existing destinations; use exclusive files, fsync and final
   hard-link publication. Read back bounded ordinary files and verify digests/linkage. Retain
   partial files on errors. Directory ancestry/interpreter are trusted; no adversarial isolation.
4. Document scope gaps: rejected requests, candidate-read observations and unapplied proposal
   bodies were never retained. No native provenance, auth, human grade, model/billing proof,
   automatic recovery/replay, production quota/retention or closeout time guarantee is added.
5. Test full Report-to-response round trip after original objects are gone; detached captures;
   revoked/held/pending/failed/unknown states; malformed/damaged/missing/colliding/oversized or
   nonregular files; broken references/IDs. Run full suite and independent reviews before a
   local-only commit, preserving unrelated C2 files and prior packet evidence.
