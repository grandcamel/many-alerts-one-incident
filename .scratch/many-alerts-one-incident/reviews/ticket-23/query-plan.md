# Ticket 23 pinned read-only query adapter plan

Baseline: `44ed5f5`. Implement only in-process retrieval from the five pinned synthetic
Notification/telemetry files. No historical executable, query language interpreter,
shell, network, Jira mutation, native model adapter or new execution authorization.

1. Copy exact bytes for Notification, metrics, logs, traces and Changes from historical
   commit 79a14c8904f3a125d1f03b192d10797d30979c86 after checking existing source-manifest
   digests. Exclude Ground truth/scoring files. Load only fixed names under a trusted
   operator root; bounded regular-file reads and compiled-in hashes fail on drift.
2. Define fixed Python operation names and strict argument contracts: Notification,
   metric catalogue/exact-series query, exact-service logs, trace summaries/exact detail,
   and Changes. Canonical UTC second timestamps use inclusive bounds; no fuzzy service
   or trace prefix matching. Sort event-time selections stably and expose truncation.
3. Return versioned correlation envelopes with caller request ID, adapter response ID,
   virtual observation time, effective query filters, pinned source digest, source item
   pointer/projection, explicit status/counts/truncation and response digest. Empty matches
   are successful queries; unknown exact metric/trace selectors are not_found. Invalid,
   revoked, duplicate-ID or capacity-exhausted calls raise, never synthesize empty success.
4. Retain bounded serialized responses for read-back within the adapter; never expose
   mutable internal records. Enforce lifecycle work admission for new queries. This is
   trusted single-threaded fixture code; returned IDs/digests are not authentication,
   durable audit, native dispatch proof or a private mount boundary.
5. Test pinned parity, filtering, missing-versus-empty, projection, truncation, stable
   correlation/read-back, malformed input, revocation/capacity and no path/URL operation.
   Run full suite and independent Standards/Spec plus bounded fresh Fable review.

The fixture query protocol is not a native capability manifest. Synthetic Incident writes,
transport/mount controls, full timing, human rubric freeze and paid execution stay closed.
