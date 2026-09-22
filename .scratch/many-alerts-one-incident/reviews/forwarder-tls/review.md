# TLS boundary independent source review

Supersedes the earlier source-only verdict. Reviewed
`grafana_jsm_sandbox/forwarder_tls.py` at SHA-256
`a4b4b7d94253c9eab986846593e128bc9e8e2fc32bff22f482771ca236314a1a`.

Verdict: **PASS (source review)**.

The boundary selects only immutable service profiles and makes a single
AF_INET/loopback connection with the profile port and exact SNI.  The context
is fresh, uses only `cadata`, requires certificate verification, disables CN
fallback, and rejects CA bundles whose loaded store contains any non-CA entry.
The post-handshake policy requires the exact two SAN entries and enforces the
specified UTC validity, current-time, remaining-lifetime, and maximum-lifetime
conditions.

The implementation captures one monotonic deadline before TCP work, spends its
remaining budget on connect and explicit handshake, checks it after certificate
policy evaluation, and turns nonfinite/regressing clock observations into fixed
errors.  Timeout and CA inputs are bounded, exact-typed, and do not expose
caller material in diagnostics. Failure ownership is retained through the
raw-to-wrapped handoff. The correction removes the unsafe `fileno()` fallback:
cleanup calls `socket.close(fd)` only after `detach()` transfers ownership,
avoiding a double-close of a recycled descriptor if both `close()` and
`detach()` fail. If transfer cannot be established, the original setup failure
is retained rather than risking an unrelated descriptor.

Static checks run by this reviewer: `python -m py_compile`, `ruff check`, and
`git diff --check` for the module and inspected TLS tests all passed. Final
targeted and full-suite execution remains root-owned and is not reported here.
No runtime, native, provider, credential, C2, commit, or push validation was
run here.

Final inspected test hashes are
`519f6fd254e8b23b4e161e0593b5d0af1493b508689dcc2d42e5f43682810db8`
for `tests/test_forwarder_tls.py` and
`2d363b2662e507677f1db6270e40cf4d03e269fb39d282d1930655bf3d9cf73f`
for `tests/test_forwarder_tls_integration.py`. The unit tests cover the exact
600-second remaining and 86400-second lifetime inclusions plus one-second
rejections, and the ownership-transfer regression. The integration success
path completes TLS close-notify with `unwrap()` before close, avoiding a TLS
1.3 ticket-related reset in the fixture.

Remaining acceptance is owned by the root integration lane: real certificate
and handshake coverage, including all profiles and negative CA/SAN/lifetime
cases, is required before any broader claim.
