# 18d2 implementation plan: no-writer journal reservation claims

Status: accepted local source plan, 2026-09-25. Baseline: `d871a63`.
Design: `design-18d2-journal-claims.md`. This is a multi-file refactor with
verification between record validation, reducer replay and inspection steps.
No existing application caller, ledger writer, reservation or launch path is
added.

1. Add tests first for the exact two v2 pairs, default v1 byte parity,
   canonical UUID/digest/sequence/type rejection, body limit and fixed error
   codes. Verify non-UUID v1 admission/job histories still replay but new
   intents for non-UUID admissions are held. Test collisions among journal
   origin, admission, job and every new ID, including the fresh journal
   confirmation event ID and claimed ledger event ID. Pin the public v1
   registry and unknown-future-pair process hold.
2. Extend `journal_records.py` through its private v2 registry. Define exact
   ID/data key sets and validators. Keep the existing v1 tables and tags
   unchanged. Bound each new v2 body to 2048 bytes on seal and decode.
   Run focused codec tests and Ruff before editing the reducer.
3. Extend `journal_reducer.py` with immutable intent/confirmation projection
   entries, pure planners, replay verification and a separately tagged claims
   digest. Verify committed `run_hold`/pending membership, prior head,
   canonical new IDs, exact eight-way distinctness, digest recomputation,
   duplicate and cross-intent reuse of attempt identities, claimed ledger
   event IDs and `(ledger_uuid, ledger_generation, sequence)`, confirmation
   order, the exact sorted claims-digest object, 256-record caps and
   total-byte accounting. A planning
   cap refusal writes nothing. Intent and confirmation leave `run_hold`
   unchanged and never make a job dispatch-eligible. Keep v1 and run-hold
   state calculations exact.
   Run focused replay and mixed-history tests before editing inspection.
4. Extend `recovery_journal.py` only for verified replay and a bounded
   count/digest in handle and verify-only inspection. Expose no append
   method. Update `docs/recovery-journal.md` with the claim-only semantics.
   Test whole-history reopen, restart, forged recomputed chain/claim digest,
   crash images at intent/confirmation boundaries, a superseded held job that
   remains unresolved, orphan-ledger handling reserved for the scanner, and
   old-binary handling.
5. Review Standards and Spec independently against this design and the
   accounting gate ledger. Run guarded focused tests, Ruff, line/whitespace
   checks and the full repository suite with demo flags unset before a local
   code commit. Record artifact hashes, protected dirty read-back, and all
   `NOT RUN` boundaries. Update tickets 37 and 38 while leaving them open.

If the tests expose a v1 registry or replay compatibility conflict, fix the
versioned approach before committing source. A journal confirmation remains
a claim until 18d3 reads a verified current ledger event. Synthetic
confirmation, fixture population or a fresh directory cannot qualify it.
