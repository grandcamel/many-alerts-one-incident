# Local mediated-client transport outcome

2026-09-22. Baseline 36a89c5. **SYNTHETIC LOCAL TLS / NATIVE CLIENT NOT RUN.**
[Plan](mediated-client-plan.md), [validation](mediated-client-validation.json), and
[client configuration sources](client-configuration-sources.md).

The isolated prototype now runs real TLS on both local hops: Python test client
to mediator, then mediator to its fixed synthetic upstream. It verifies CA trust,
hostname/IP and certificate expiry, and admits only one exact request/path/body.
The mediator rebuilds upstream credential/framing headers, rejects caller-selected
routes and ambiguous framing, and enforces finite scoped fixture leases. Registered,
wrong-service, expired and revoked tokens cannot send an upstream request. New
harness instances have no inherited admissions.

Responses are bounded and buffered. Only the exact complete synthetic response
passes; redirects, truncation, timeout, TLS failures and mismatches stay unknown.
There is no retry, and upstream uncertainty revokes the affected fixture lease.
Metadata-only receipts use one-time internal dispatch correlation; forged direct
upstream requests cannot create receipts. This is fixture integrity, not an OS
control-plane or real-provider authorization claim.

## Review and validation

Terra implemented the harness. Luna independently authored actual socket/TLS tests,
and a separate Luna reviewer checked the contract and implementation. Root supplied
temporary OpenSSL certificate generation and reviewed integration and deadlines.
No production Forwarder, Receiver, Run environment or system trust was changed.

Review corrected handshake timeouts that were applied after TLS accept, slow-drip
requests that could extend per-read timeouts, outbound work that could otherwise
start a fresh time allowance after a late request body, non-ASCII token and huge
Content-Length failure handling, constructor cleanup and forged receipt correlation.
Both server shutdowns start together, with a five-second join limit and visible
failure. Revocation synchronizes with the bounded request; it does not undo work
already dispatched. Native cancellation and the production 300-second lifecycle
remain separate acceptance work.

The final full suite passed **794 tests, 36 skipped in 47.00s**, including
**50** independent local transport cases. Ruff and diff checks passed. Independent
final Standards review passed at the recorded source hash. The validation receipt
records exact reviewed hashes and retained examples. Sixteen independent examples cover the successful exchange,
lease denials, wrong CA/hostname/expiry, upstream failures and response caps. Their
server threads stopped; temporary example keys were removed. Only public certificate
hashes and nonsecret receipt metadata are retained outside Git at
`/Users/jasonkrueger/maoi-ticket23-evidence/20260922-mediated-client/`.
The previous 103-file packet is archived and byte-verified.

## Remaining work

This covers local Python transport only. Buffered SSE-shaped fixture bytes do not
establish incremental streaming, real Messages request policy or Claude 2.1.278
compatibility. Five-service schemas, authenticated Receiver-only control, OS and
sidecar separation, direct-route denial from a Run, production certificate lifecycle,
provider ledger reconciliation and audit/venue acceptance remain open. Ticket 36
remains a specification task; no runtime adoption or ticket closure is claimed.

The next step is bounded streaming and client-shaped request/response fixtures,
followed by technically admitted native-client testing under the existing standing
cost approval. No paid experiment, external headless review, credential change,
push or publication occurred in this batch.
