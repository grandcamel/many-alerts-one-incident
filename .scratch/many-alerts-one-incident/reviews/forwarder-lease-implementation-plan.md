# First local application unit: service profiles and scoped leases

2026-09-22. The user's `continue` response to the pending implementation-scope
decision authorizes the reviewed local source/test proposal. This is its first
bounded unit, not native/deployment acceptance or a change to the planning tickets.

## File ownership and sequence

1. Root adds `grafana_jsm_sandbox/forwarder_services.py` and
   `tests/test_forwarder_services.py`: immutable five-service constants, exact
   mandatory/optional readiness classification and no caller-selected route.
2. Terra adds `grafana_jsm_sandbox/forwarder_leases.py`: internal trusted-controller
   lease registry with generated generation/lease/sentinel IDs, immutable binding,
   activation, exact replay, expiry, revocation, Receiver heartbeat/EOF and bounded
   metadata history. Luna independently owns `tests/test_forwarder_leases.py`.
3. Root and an independent reviewer inspect the integration and negative cases.
   Run focused checks, then the full suite before a local commit. Update evidence
   and the backlog with the implemented versus still-missing boundary.

## Fixed contract

Service keys are `jira`, `confluence`, `grafana`, `kubernetes`, `anthropic`;
ports are 17441 through 17445 respectively. Confluence alone is optional for
mandatory route readiness. Service profiles contain only nonsecret constants;
an operator-owned future transport supplies the fixed actual upstream origin.
Readiness here classifies supplied route facts, not authentication or launch.

The lease module is in-process application source. Only a future authenticated
Receiver control adapter may call it. It does not accept or verify socket peer
UIDs, control secrets, OS attestations, provider credentials or native clients.
No existing HTTP/OAuth launcher is wired to it in this unit.

`LeaseRegistry(clock=time.monotonic)` generates its own `generation`. Trusted
control methods are `handshake(receiver_boot_id, generation)`,
`heartbeat(receiver_boot_id, generation)`, `disconnect(receiver_boot_id, generation)`,
`register(run_id, attempt_id, receiver_boot_id, service, scope_digest, expires_at,
generation)`, `activate(lease_id, receiver_boot_id, generation, launch_at)`,
`revoke(lease_id, receiver_boot_id, generation, reason)`, and
`check(service, sentinel, generation, scope_digest)`. `snapshot()` returns bounded
nonsecret metadata for diagnosis. Invalid inputs raise a typed error with a fixed
reason code, never secret values. Methods use keyword arguments except snapshot.

Registration returns a frozen grant containing its sentinel with `repr=False`;
receipts and snapshots never include the sentinel. IDs are bounded opaque ASCII;
scope digests are lowercase SHA-256 hex. One `(run_id, attempt_id, service)` has
one immutable boot/generation/scope/expiry binding during retained history.
Exact replay returns the same live grant; changed binding, replay of a revoked
grant, or unknown/wrong service/generation is refused. Activation is explicit;
pre-activation checks fail. A lease cannot outlive its supplied expiry or 270
seconds from registration/launch. No replay, heartbeat or activation extends it.

A new Receiver boot or observed control EOF revokes affected leases immediately.
At 15 seconds without a heartbeat, existing leases expire before a later heartbeat
can refresh connection health. Invalid or regressing clocks hold the registry;
no reconstructed monotonic time may revive authority. One registry clock and
lock serialize decisions; supplied trusted-controller launch time cannot be in
the future. Cancellation/revocation prevents later successful checks, but `check`
returns only an instantaneous authorization snapshot. It is not a dispatch token:
future transport must combine final authority checks with dispatch initiation.
This unit makes no race-free network dispatch or rollback claim.

Keep at most 256 live leases and 1,024 total live/retired record slots, reserving
retirement capacity by refusing registration before overflow. This is a tighter
implementation bound than separate 256/1,024 maxima. Bound and byte-account
retained metadata; prune records at 310 seconds from creation, never sooner to
make room. These are representation bounds, not Python heap measurements.
Cross-restart and post-retention duplicate suppression belong to the durable
Receiver journal; the in-memory registry cannot claim them.

## Validation boundaries

Tests must cover exact replay versus changed scope/expiry, wrong service/token/
generation, pre-activation, expiry equality, heartbeat threshold and late renewal,
EOF, boot replacement, revocation replay, capacity without eviction, retention,
strict types, clock rollback/nonfinite values, secret-free receipts/repr and
concurrent registration. Readiness tests distinguish mandatory failure from
optional Confluence degradation. No test contacts a real upstream or invokes a
native model client. All provider, OS isolation, authenticated control transport,
request policy, durable admission and native integration gates remain unqualified.
