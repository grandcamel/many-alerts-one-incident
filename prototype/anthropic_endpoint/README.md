# Mediated Anthropic endpoint subset (throwaway, ticket 19 Stage B preparation)

Implements the card's "Mediated endpoint" component: loopback TLS under the
Stage A ephemeral CA, per-attempt sentinel admission via a separate
operator-control listener, upstream key substitution held outside the client
Run, fixed upstream destination, `POST /v1/messages*` only, SSE-compatible
chunked streaming, mid-session revocation, and receipts limited to paths,
sizes, timings and statuses (no credential values or bodies).

For a real attempt, `upstream_conn_factory` becomes
`http.client.HTTPSConnection("api.anthropic.com", context=ssl.create_default_context())`
and `upstream_key` is supplied by the operator at launch from outside the Run;
neither appears in artifacts. This is the isolated two-service subset the
ticket-19 card allows — not ticket 36's five-service specification.

## Self-test evidence

`run_self_test.py` drives a mock loopback upstream with fixture keys. Measured
2026-09-18 (`artifacts/self-test.json`, verdict `supported`):

- Proxying substitutes the fixture upstream key; the client sentinel never
  reaches upstream.
- All six SSE event types pass through; non-streaming JSON passes through.
- Absent and wrong sentinels: 401 with zero upstream requests.
- Unlisted path: 404. Revocation: 200 before, 401 after, zero upstream
  requests after revoke (revocation drill).
- Mid-stream revocation: with a dribbling SSE upstream, revocation at ~1 s
  truncates the client stream (4 of 7 events received) and the endpoint
  records `revoked-mid-stream`. The proxy reads upstream with `read1`, because
  `read(amt)` on a chunked response blocks until amt bytes or end-of-stream
  and would defeat per-chunk revocation.
- Receipts hygiene: serialized endpoint receipts contain no sentinel,
  operator-token or upstream-key material (query strings are never logged).
- Content-Length abuse: negative → 413, malformed → 400; 10 MiB body cap.
- Full dress rehearsal: `claude --bare -p` completes a turn through the TLS
  endpoint (`NODE_EXTRA_CA_CERTS` trust per P4) with no real credential and
  no paid contact.

## Independent review record

A headless Pro review of the first implementation found six defects, all
verified against the code and fixed before this evidence was produced:
mid-stream revocation not enforced in the stream loop, negative
`Content-Length` bypassing the body cap, client disconnects dropping
receipts (now `try/finally`), missing socket timeouts (30 s client I/O bound
via `setup()`), malformed `Content-Length` crashing the handler, and query
strings written into receipts. The review also identified the two missing
self-test cases (mid-stream revocation, receipts-hygiene), now present.

Not covered (explicit `not_run`): real upstream with a valid key, upstream
error-body passthrough content, sentinel TTL-expiry case, concurrent Runs,
billing visibility. Upstream-side read timeouts are set by the connection
factory, not the endpoint; for a real attempt the factory must choose a value
compatible with the 300-second Run budget (e.g. 290 s total, generous per-read
to tolerate long model thinking between SSE events).
