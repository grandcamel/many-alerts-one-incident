# Routing probe P1: does the installed `claude` CLI honor a base-URL override?

This throwaway implements the P1 experiment proposed in the main repo's
`.scratch/many-alerts-one-incident/reviews/ticket-19/stage-b-readiness.md`.
It is local and model-free in the billing sense: a mock loopback listener
terminates every request, the API key is a random synthetic sentinel, and no
real credential, tenant, container, cloud resource or publication is involved.
It does not run Stage B, select Eyes, resolve ticket 19 or unblock ticket 12.

## Question

ADR 0013 requires the Anthropic API to be reached through a mediated Forwarder
endpoint with a per-Run sentinel, and states "Actual compatibility is
unverified; do not silently restore direct credentials if mediation fails."
The installed client (Claude Code 2.1.272) does not document an endpoint
override in `--help`. The official `claude-api` skill
(`anthropics/skills@claude-api`, installed at `~/.agents/skills/claude-api`)
documents `ANTHROPIC_BASE_URL` / `base_url` for the Anthropic SDKs and the
`ant` CLI (`shared/anthropic-cli.md:31`, `SKILL.md:465`). This probe measures
whether the installed `claude` CLI routes its Messages API traffic to a
loopback mock when `ANTHROPIC_BASE_URL` points there.

## Fixture contract declared by the harness

- Plain-HTTP mock on `127.0.0.1`, ephemeral port. Every request line, header
  set and a bounded body (64 KiB) is recorded. Bodies are synthetic by
  construction; do not reuse this recorder with real input.
- The child runs `claude --bare -p --output-format json` from a throwaway HOME
  and cwd, with a minimal explicit environment: `ANTHROPIC_BASE_URL` at the
  mock, a random per-run sentinel `ANTHROPIC_API_KEY`, stripped proxies and
  stripped inherited Anthropic/Claude variables. `--bare` (per installed help)
  restricts auth to `ANTHROPIC_API_KEY` and never reads OAuth/keychain.
- Mock responses use the exact non-streaming and SSE shapes from the skill's
  curl reference (`curl/examples.md`): a minimal valid `message` ("pong"),
  echoing the requested model id. Unhandled paths receive a JSON 404 and are
  recorded.
- Verdicts: `supported-routing` (a request carrying the sentinel reached the
  mock), `refuted-direct-route-suspected` (no arrival and client output shows
  a real-API response), otherwise `inconclusive` with quoted client output.
  Routing support here is not endpoint-policy, TLS-trust or billing
  acceptance; a fifth-endpoint Forwarder still needs the ADR 0011 TLS/sentinel
  pattern and ADR 0013 preflight checks.
- Known-secret scanning before persistence: the serialized report is checked
  against any inherited Anthropic/Claude environment values; the synthetic
  sentinel is expected in receipts by design. Throwaway HOME is deleted.

## Reproduce

```sh
python3 prototype/routing_probe/run_routing_probe.py   # P1: HTTP routing
python3 prototype/routing_probe/run_tls_probe.py       # P4: deployment-local CA trust
```

## P4 addition (2026-09-18)

`run_tls_probe.py` reuses the mock over HTTPS with an ephemeral Stage A CA
certificate (SAN `DNS:localhost`). Two cases run in sequence: `untrusted` (no
trust configuration) and `trusted` (`NODE_EXTRA_CA_CERTS` pointing at the
ephemeral CA — a mechanism evidenced by strings inside the installed 2.1.272
binary, not assumed). Verdict `supported-tls-trust` requires the trusted case
to deliver the sentinel over TLS **and** the untrusted case to produce zero
HTTP requests (client-side rejection). Measured: untrusted exit 1 with
"SSL certificate verification" error and three connection resets, no request
dispatched; trusted completed the turn. Ephemeral keys are deleted after the
run. This settles client CA trust for the fifth-endpoint design; it is not
endpoint-policy, revocation or billing acceptance.

Requires the installed `claude` CLI on PATH. No download, no public network
intended; if the client ignores the override its request carries an invalid
key and cannot be billed, and the client's own output is preserved as
evidence.
