# Unit 13b synthetic fixed-origin upstream connector outcome

2026-09-23. PASS for the second half (13b) of the thirteenth separately
authorized local application unit, baseline `c1869a2`.
[validation.json](validation.json) records the final verdict and evidence. The
work is local only: nothing was pushed and no planning ticket was closed.

## What the unit adds

`forwarder_upstream.JiraUpstreamConnector` is the trusted connector for
`jira.issue.get` and `jira.search`. It has no production caller.

**Production stays unavailable.** Four locks each have a test:
- no Python file outside `tests/` imports or names the connector, endpoint or credential types, and no launch or configuration file names the module;
- the `synthetic-only.v1` endpoint policy accepts only an RFC 6761 `.invalid` host on an RFC 5737 documentation address;
- there is no configuration or credential loader;
- `ROUTE_CATALOG` keeps both Jira routes `partial`, and `policy_readiness_facts()` stays all `False`.

**No ambient authority.** The module performs no DNS, proxy, environment, file or mount read. An AST test enforces the forbidden-name list, including resolvers and TLS-weakening calls.

**TLS.** Each connect builds a fresh context with explicit `cadata` as the only trust source, reads its options, flags and trust digests back before use, and checks the negotiated session after the handshake.

**Credential custody.** `BasicCredential` is redacted, unpicklable, uncopyable, final, cannot be re-initialized, and claimable by one connector. Within Python, the encoded header lives only in a send buffer that is zeroed after the write.

**Request digest v2.** `prepare` is pure. It re-verifies the route shape and the unit-12 v1 digest, and returns a v2 digest bound to the endpoint (including trust digests) and the Host authority. It never returns v1. The descriptor binds the method to the route shape, so an injected method cannot split the request.

**Transport.** `connect` refuses a wrong digest, a second connect or a late deadline before any socket exists, then completes TCP and TLS within five seconds and writes no application bytes. The channel sends the canonical request once, after the 13a write fence, reads one response through `receive_response`, and maps failures to 13a's closed upstream codes. `abort` shuts the socket down beneath its TLS object, so a later write cannot fall back to plaintext. Nothing is retried.

## Review

- A design panel of three designs, two judges and a critic (15 issues) produced the plan. Root reconciled it against 13a.
- A 56-agent implementation workflow confirmed 33 findings over three rounds. The workflow fixed 25. Of the eight round-3 findings, root fixed the one source defect, F3-3 (method binding), and a test agent added 23 tests covering all eight and killed eight targeted mutants.
- A fresh reviewer bound the hashes: PASS, 40 of 42 mutants killed, all goldens recomputed independently.
- Before commit, root applied the reviewer's two non-blocking source hardenings (credential re-initialization refusal, an encoder guard) and six doc wording corrections. A test agent closed five test gaps and proved each new test with a mutant, and the same reviewer re-verified the result ([review](review.md)).

## Validation

- Unit tests (three files): **439 passed** under the loopback guard in repeated runs, each with `NON_LOOPBACK_ATTEMPTS []`.
- [Focused Forwarder suite](focused-tests.txt): **2484 passed**.
- [Full suite](full-suite.txt): **3358 passed, 36 skipped in 172.84s**, exit 0.
- Ruff (including line length), compile and `git diff --check` pass. Every existing test file is byte-identical, and no existing module changed.

## Not qualified

- real Jira compatibility or any tenant or provider call (the committed codec rejects `application/json;charset=UTF-8` and chunked responses);
- the real origin, address stability, IPv6, CA issuer, rotation and revocation;
- credential custody on disk, by UID or mount, or in Python memory; a credential loader;
- process-level OpenSSL configuration beyond the runtime read-back;
- supervisor wiring, readiness, permits, PARTIAL, SSE and non-Jira connectors;
- native clients and deployment.

## Not performed and next

No provider, tenant or native call was made, and no test connected anywhere but loopback. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

Next is unit 14, control framing, from the [control-framing plan](../forwarder-control-framing/implementation-plan.md), after reconciliation against this commit. Planning ticket 36 remains open.
