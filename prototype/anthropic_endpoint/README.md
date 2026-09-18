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
- Full dress rehearsal: `claude --bare -p` completes a turn through the TLS
  endpoint (`NODE_EXTRA_CA_CERTS` trust per P4) with no real credential and
  no paid contact.

Not covered (explicit `not_run`): real upstream with a valid key, sentinel
TTL-expiry case, concurrent Runs, billing visibility.
