# Bounded TLS response collection outcome

2026-09-22. PASS for the tenth separately authorized local application unit, baseline
`1220f4c`. Final verdict and validation are recorded in
[validation.json](validation.json). Local only; no push or planning-ticket closure.

The response parser now shares a pure complete-head validator with the new
`receive_response` collector. Declared length is validated without allocating a
dummy body. The collector reads one non-streaming response over a caller-owned
established client TLS socket, independently bounds status/header/body bytes and
rejects malformed heads before further body reads. Coalesced prefixes and opaque
bodies are preserved. Captured excess fails; exact completion does not await EOF.

One permanent socket claim prevents repeat/concurrent collection. Each read is
clipped to twenty seconds and the original lease-clipped handler deadline, with
clock checks before/after reads and timeout restoration. Late completed reads
cannot succeed after the inactivity interval. Restoration failure cannot create
success or replace a primary failure/interruption. The collector sends nothing
and leaves socket closure to its owner.

Terra workers implemented the source and deterministic tests; another Terra
worker independently reviewed the final source/test hashes. Root added real TLS
and adversarial tests, corrected generic test exception expectations and reviewed
fragmented headerless 204 detection plus completed-read inactivity enforcement.
The [review](review.md) records its verdict against the frozen files.

[Focused validation](focused-tests.txt): **137 passed in 2.18s**, exit 0,
comprising 83 unchanged response-codec tests, 39 deterministic head/transport/
adversarial tests and 15 real local TLS tests. The new tests cover trust-state
rejection before reads, region caps, slow fragments, restore-clock failures,
no-body response termination, captured excess, stalled peers and truncated EOF.
The final [full suite](full-suite.txt) reports **1432 passed, 36 skipped in
167.44s**, exit 0. Artifact hashes accompany the validation manifest. Independent
review, Ruff, compilation and whitespace checks pass.

Current socket TLS/configuration checks are not proof of original connection
trust or fixed-origin identity; the trusted connection owner retains that duty.
Local fixtures use synthetic certificates and ephemeral TLS ports through the
existing fixed-service adapter. They establish no real upstream, native-client,
deployed credential or namespace qualification. Body semantics, service scopes
and successful effects still require route-specific validation/read-back.

The complete exchange owner must close the socket after this one response;
later bytes or another unread TLS record cannot become a second response. A
collector error alone cannot classify an external effect as NOT_DISPATCHED;
that decision requires dispatch context and may retain UNKNOWN/PARTIAL state.
No response send, sanitized receipt, provider/tenant/native call, actual
credential, C2 retry, paid experiment, deployment or human Report adjudication
occurred. Four protected dirty artifacts remain unchanged and unstaged.

Next: response forwarding coordinated with receipt-before-send and request-aware
route policy, then atomic lease/revocation/dispatch and durable Receiver/recovery/
accounting integration. Existing local source authority covers that work without
another user scope decision. Planning ticket 36 remains open.
