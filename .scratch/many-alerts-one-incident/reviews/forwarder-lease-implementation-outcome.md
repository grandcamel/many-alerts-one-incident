# Forwarder service and lease implementation outcome

2026-09-22. **PASS — first local application source unit.** This is separately
authorized implementation, not runtime acceptance for planning ticket 36.

## Delivered behavior

`grafana_jsm_sandbox/forwarder_services.py` pins the five loopback service profiles
and distinguishes mandatory-route failure from optional Confluence degradation.
`grafana_jsm_sandbox/forwarder_leases.py` adds the trusted-controller lease registry:
immutable Run/attempt/service/Receiver-boot bindings, explicit activation, exact
live replay, expiry, revocation, heartbeat/EOF invalidation and generation checks.
Invalid clocks hold authority. Late renewal cannot revive retired leases.

Nonsecret metadata has count, age and canonical encoded-byte bounds. Admission
reserves future state growth and diagnostic history; it never evicts recent lease
records to admit another Run. `check()` is an instantaneous observation. An
authenticated transport must coordinate its final authority check with dispatch.

See the [file-level plan](forwarder-lease-implementation-plan.md),
[source/test review](forwarder-lease-review.md), and
[application documentation](../../../docs/forwarder-control.md).

## Validation

- Focused service and lease tests: **50 passed in 52.68 seconds**.
- Full repository command `pytest -q`: **924 passed, 36 skipped in 157.19 seconds**;
  [complete output](forwarder-lease-full-suite.txt).
- Ruff passed for both source modules and both test modules.
- Independent final source review and test review passed at the hashes recorded
  in the review and [validation manifest](forwarder-lease-validation.json).
- Root checked the actual approved proposal hash and final source hashes. The
  four unrelated C2/planning-frontier dirty files were preserved and excluded
  from this commit.

The new tests cover replay conflicts, lease state transitions, service/generation
denials, inclusive expiry, timely and late heartbeats, boot replacement, stale
registration/activation, clock faults, strict inputs, bounded secret-free
diagnostics, concurrent duplicate registration and count/byte/age limits. Capacity
tests isolate record counts from byte limits, then exercise mass activation and
heartbeat retirement near the default byte-admission boundary.

## Remaining work

The legacy HTTP/OAuth launcher is unchanged and is not wired to these modules.
Next implement authenticated Receiver control, fixed TLS listeners and
request-aware policies, then durable Receiver admission/recovery/accounting and
guarded launcher integration. These local source/test follow-ups are already
authorized; automatic continuation is active.

NOT RUN or qualified here: native model client execution, real provider or tenant
requests, authenticated socket-peer/mount/kernel isolation, deployment, credential
operations, paid experiments or human Report adjudication. The 36 skipped tests
remain skipped. Source and local test success do not clear those separate gates.
No C2 implementation retry, push or publication occurred in this unit.
