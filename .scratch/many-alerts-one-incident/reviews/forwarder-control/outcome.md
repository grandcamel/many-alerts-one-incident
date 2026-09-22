# Authenticated Forwarder control implementation outcome

2026-09-22. **PASS — local application source and Unix-socket tests.** The
existing implementation approval covers this separate follow-up to planning
ticket 36. The ticket remains open for its other acceptance requirements.

## Delivered behavior

The new control adapter authenticates OS peer identity and role-separated
shared-secret challenge proofs before accepting Receiver authority. Four-byte
length-prefixed JSON frames have size, nesting, scalar and whole-frame deadline
bounds. Only register, activate, revoke and heartbeat commands are exposed, with
exact schemas and increasing sequence numbers; boot/generation are session-owned.

At most four connections execute, with one authenticated owner. Replacement
revokes old leases, including for the same Receiver boot. A delayed old command
or finalizer cannot change replacement authority. Failed frames, commands and
response writes release authority before diagnostic output. An uncertain
disconnect permanently holds the registry, even when clock-based cleanup cannot
be trusted. Only authenticated registration replies carry lease sentinels.

See the [implementation plan](implementation-plan.md), [independent review](review.md),
and [module documentation](../../../../docs/forwarder-control.md).

## Validation

- Final focused command: `pytest -q tests/test_forwarder_control.py tests/test_forwarder_control_protocol.py`;
  **53 passed in 0.63 seconds**.
- Full repository command: `pytest -q`; **977 passed, 36 skipped in 126.26 seconds**.
  [Full output](full-suite.txt).
- Ruff passed for both new source/test modules and the updated lease module.
- Independent Sol source and lifecycle review passed; Terra implemented the
  codec and independently authored its tests. Root integrated and reviewed the
  session implementation. [Validation hashes](validation.json) pin final files.
- The initial full-suite timing failure is retained in a separate log and
  explained in the review. A deterministic delayed-finalizer barrier replaced a
  timing assumption; no production change was required for that failure.
- All four unrelated C2/planning-frontier dirty files remain unchanged and are
  excluded from this unit's local commit.

The tests cover bad UID/proof, reflected or replayed proof, malformed schemas and
sequences, failed closeout, response failure, slot exhaustion/release, EOF,
timeout and old-owner cleanup after replacement. Codec cases include fragmented
and coalesced frames, invalid/oversize encodings, enormous integer literals and
absolute read/decode/write deadlines. Actual local Darwin socket peer checks
were exercised with synthetic secrets; this is not cross-UID deployment proof.

## Next work and boundaries

Next implement private listener provisioning and fixed service TLS/request
policies, then durable Receiver admission/recovery/accounting and guarded launcher
integration. Local implementation authority and automatic continuation remain
active. The legacy HTTP/OAuth launcher is still unchanged and not wired here.

NOT RUN or accepted here: Linux SO_PEERCRED behavior, deployed socket ownership,
secret loading/custody, private mount or kernel isolation, native model clients,
provider/tenant operations, deployment, paid experiments or human Report
adjudication. Unauthenticated peers can occupy the four connection slots until
their frame deadlines; future listener access restriction is required. No C2
retry, real credential operation, push or publication occurred.
