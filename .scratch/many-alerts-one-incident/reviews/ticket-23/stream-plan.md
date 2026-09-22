# Exact-client register and stream-evidence plan

Baseline b0e1f8b, 2026-09-22. Cost authorization is standing below $50 aggregate;
this batch uses local fixtures and self-documentation, with no paid model probe.

1. Inventory the exact installed Claude executable/version/help and headless wrapper
   help using no inference/auth mutation. Retain bounded command output and digests
   outside Git; distinguish CLI switches from actual stream schema qualification.
2. Extend fixed-process evidence with separate stdout/stderr bytes and digest/count
   fields. Preserve the existing aggregate capture cap across both streams. Capture
   accepted chunks only; loss/overflow must remain incomplete, never parsed as full.
   Existing merged capture stays diagnostic; per-stream ordering is retained but no
   cross-stream emission-order or authenticated native provenance claim is made.
3. Add version-2 closeout for the additional files/links, retain explicit version-1
   historical read support with unknown stream provenance, reject partial/downgraded
   stream metadata. Exclusive bounded publication/read-back keeps failure evidence.
4. Make integrated rehearsal require version-2 retained stdout, parse receipts only
   there, and reject nonempty stderr for its closed scripted worker. Add fixed
   stderr-noise/JSON fixture scenarios and tests for channel confusion, independent
   stream tampering, combined caps, interrupted/failed captures and legacy read-back.
5. Terra owns implementation, Luna owns independent tests and client evidence scout.
   Verify between implementation/reader changes; independent Standards/Spec review,
   full suite after final code edits, then local commit with exact evidence inventory.

This is fixed-fixture stream attribution, not a native model adapter, sanitized
production audit, authenticated source identity, live TLS/credential proof or billing.
Preserve unrelated ticket19 edits. No inferred native event schema or launcher is added.
