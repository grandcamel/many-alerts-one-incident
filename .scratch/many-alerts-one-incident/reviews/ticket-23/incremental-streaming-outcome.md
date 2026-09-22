# Incremental synthetic TLS fixture outcome

2026-09-22. Local implementation, test and internal review evidence. No provider,
native model client, tenant, cluster, credential change, paid experiment or
provider-blocked C2 retry occurred.

## Delivered behavior

The [incremental harness](../../../../prototype/mediated_client/streaming.py)
adds a separate synthetic stream mode to the existing two-hop TLS fixture. A real
test client decodes the first complete frame before the controller releases the
final frame. The split-UTF-8 case forces byte-sized mediator reads, so successful
assembly does not depend on separate upstream writes remaining separate packets.
The buffered harness remains unchanged.

The terminal is withheld until the declared body, strict event sequence and true
connection EOF are verified. Truncation, duplicate or conflicting terminals and
bytes beyond Content-Length close a partial stream without a fabricated terminal
or second HTTP response. A partial upstream send counts as a possible dispatch
and holds its lease. Revocation between frames prevents later frame dispatch;
it does not undo bytes already written.

Limits cover frame/stream bytes, event count, nesting, numbers, request history,
TLS handshake, blocking operations and absolute connection lifetime. Only finite
built-in scripts are accepted. Synthetic upstream identity headers and one-use
nonce/sequence correlation are checked. Receipts contain metadata and digests,
never credentials or bodies. A completed local write is distinct from the test
client's own decode acknowledgement.

Controller release and first-frame signals are one-way per-harness latches;
they do not grant per-Run authority. A partial-stream failure aborts that harness
and blocks later upstream dispatch even with a fresh grant. The history test
verifies the independent 128-request cap across successful requests.

## Validation and review

- Full repository suite: **835 passed, 36 skipped**. The
  [retained log](incremental-streaming-pytest.txt) records the final run.
- Focused streaming and buffered suites: **91 passed**, including 41 new
  streaming cases and all 50 existing buffered cases.
- Ruff checks and source whitespace checks passed.
- Terra implemented the fixture. Two Luna reviewers independently checked parser,
  transport, lifecycle, identity, evidence and test boundaries, with root review.
  Final source reviews passed; these are internal reviews, not provider approval.

The [validation receipt](incremental-streaming-validation.json) pins source and
test hashes, the full-suite log and review scope. Review corrections include
incremental first-frame reads, true-EOF verification, partial-write phase flags,
conservative upstream dispatch accounting, strict frame ordering and Unicode
handling, fresh checks under the lease lock, fixed upstream header enforcement,
and abort admission. Test import ordering and explicit expected exception classes
received final lint cleanup; the full suite was rerun afterward.

## Remaining boundary and next work

This proves only the fixed Python fixture's local transport behavior. It does not
qualify an installed client, production SSE protocol, OS credential/direct-route
isolation, provider cancellation or billing, tenant mutations, private-audit
deployment, human Report adjudication or the intended venue. Existing unknown
historical charges remain unknown; no paid attempt is admitted by these results.

The next local unit is the
[supervised streaming integration](supervised-streaming-integration-plan.md):
bind an actual fixed child's decode evidence to the existing process supervisor
and transport receipts, preserving separate stream, process and evidence outcomes.
