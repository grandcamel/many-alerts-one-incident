# Stage A: pinned native client against synthetic loopback services

This throwaway implements ticket 19's authorized local, model-free experiment. It does not implement the production Skill or Forwarder, select Eyes, resolve ticket 19, or unblock ticket 12.

## Reproduce

On Darwin x86_64 with Python 3.11+ and OpenSSL at `/usr/local/bin/openssl`:

```sh
python3 prototype/provenance/fetch_client.py
python3 prototype/stage_a/run_stage_a.py
env -u DEMO_END_TO_END -u DEMO_CONTAINER python3 -m pytest
```

The download is the only step requiring public network. The runner checks the pinned binary hash before execution. Source provenance, actual help, license and release checksum are in `../provenance/`. The fixture uses no real token or tenant. A minimal explicit environment replaces inherited credentials/proxies; usage statistics are disabled. This configuration is not OS-enforced network confinement or packet-capture evidence.

## Fixture contract declared by the harness

- Native MCP `initialize`, initialized notification, `tools/list`, then sequenced `tools/call`. Tool categories: Prometheus, Loki, Tempo and datasource; write and raw API tools disabled. Direct boundary mutation probes independently test the Forwarder policy.
- Separate loopback TLS Forwarder and HTTP synthetic backend. Random per-fixture sentinel, upstream token and operator-control token. Authenticated one-time admission, expiry and revocation. Control is a separate local HTTP endpoint with a distinct credential outside the native process environment; this does not prove container isolation. Fixed upstream, no redirect following, exact fixture query allowlist, duplicate/unlisted parameters denied. Time parameters accept numeric fixture values; this is no general query-language authorization parser.
- `stage_a_current`: vector `{source: current}`, timestamp 1767225660, value `1`. `stage_a_system`: matrix `{source: system}`, samples `[1767225600,1]` and `[1767225630,2]`. POST read requests are expected and allowed. Prior/unlisted queries are denied.
- Application logs: twelve deterministic records containing trace ID `0123456789abcdef0123456789abcdef`, a real newline, 5,000 `L` characters and numbered suffix. Native default ten requests eleven upstream to detect truncation. A requested limit of 1,000 is capped to 100; upstream receives 101 and the fixture returns its complete twelve records.
- Current Run and Change streams have distinct exact LogQL selectors and synthetic diagnostic records. The Change was pre-existing fixture data; no change injection ran. Prior-rehearsal selectors are denied; a separate allowed datasource metadata lookup can precede that denial. Empty logs return an empty data array, not an error. Tempo returns the exact synthetic trace reference.
- Backend failure=500, redirect=307 to a local recording sink (Forwarder converts to 502), backend delay=.6s (Forwarder timeout=.3s, output504). MCP request deadline5s; native Grafana configuration1s. Native cleanup: close stdin/wait2s, terminate/wait1s, kill/reap1s. Server request sockets2s, server loops20ms; all owned listener and request threads are joined. SIGINT probe waits until the delayed backend query is actually dispatched, reaps the process and explicitly revokes authority. It is not a completed model Run or automated production recovery proof.

## Evidence and limits

`artifacts/stage-a.json` preserves native requests/responses, tool schemas, exact synthetic read-backs, timings, distinct boundary/backend receipts and redirect-sink counts. Receipts intentionally contain fixture query strings/bodies: do not reuse this recorder with real input. Runtime secrets are checked against the serialized report before persistence; keys/certificates are temporary and deleted. Sanitizer success is limited to these known runtime secrets. Values temporarily remain in process memory until its short-lived exit; this is not secure memory erasure.

The report's assertion count covers only exercised cases. `criterion_gaps` and `not_run` preserve the broader inconclusive criteria: model usability and budget, large-response caps/general pagination, real Grafana grants, Kubernetes, intended venue, container filesystem and OS network confinement. Prometheus tool errors retain numeric status but omit diagnostic response bodies; the synthetic boundary receipts retain the cause. The client is supported only for the exercised transport scope.

Full repository suite output is saved in `artifacts/pytest.txt`. Its skipped integration/container tests remain unexecuted. No model, paid API, cloud resource, real tenant, image/container, production Skill edit or publication was performed.
