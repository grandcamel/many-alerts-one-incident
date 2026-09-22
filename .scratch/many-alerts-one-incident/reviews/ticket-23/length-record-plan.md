# Ticket 23 inert length-case records — 2026-09-21

Baseline: `def767b`. Add a deterministic export of the existing in-memory length probe;
no subprocess, native adapter, paid probe, authentication, shell or Jira operation.

1. Preserve all five fixed cases in order, including not-attempted and pending cases.
   Record expected/requested/observed command counts and digests, tool-use identity,
   virtual request/dispatch/observation times, synthetic permission observation/reference,
   coverage, issued stub receipt and supplied-receipt trust status, exit and classification.
2. Keep current classification, ordering, one-dispatch and cancellation behavior. Missing
   receipt must not become denial. Export only bounded synthetic metadata, never command
   bodies; snapshots must not permit callers to mutate probe state. Bound newly retained
   decision/reference fields and stub-exit integers; invalid inputs hold without advancing.
3. Label reports OFFLINE_LENGTH_RECORDS_ONLY / native launch CLOSED. Include the observed
   bracket, hold/work/cleanup state and explicit virtual-clock/in-memory-receipt limitations.
   A pending request is not not-attempted; an unrecognized supplied receipt is not trusted.
4. Test read-back serialization, edited commands, missing/forged/conflicting receipts,
   refusal/early stop, pending/cleanup states, untouched cases and snapshot independence.
   Run the full suite and independent Standards/Spec review. This bounded record export
   does not need another external model experiment or native access.

Reports are trusted fixture metadata, not production audit records or semantic grades.
Synthetic decision references are opaque labels, never verified native evidence locators.
No change to the closed measurement card or C2 provider boundary is authorized by them.
