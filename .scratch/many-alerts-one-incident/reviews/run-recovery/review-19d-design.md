# 19d worker supervision design review

Status: independent Standards and Spec reviews PASS, 2026-09-25.
Baseline: `e376ec1`. Reviewed file: `design-19d-worker-supervision.md`.

Standards review found that an already-running `Popen` child could act before
post-spawn group attestation and that a numeric PGID could be recycled after
the root was reaped. The design now requires an inherited startup barrier
before child release and an independently verifiable stable containment
identity; absent that identity, group absence is unknown and dispatch held.
The reviewer confirmed both findings resolved.

Spec review found that clean early exit could leave an active lease and that
revocation acknowledgment did not prove Forwarder quiescence. The design now
retires installed leases on every exit path and records gated Forwarder
closeout state, counts and errors separately, including post-EOF/replacement
polling. The reviewer confirmed both findings resolved.

This is documentation-only. Source and full tests are NOT RUN for unit 19d.
The startup barrier, stable venue containment identity, actual supervision,
durable observations and guarded launch remain implementation/acceptance
gates; native/provider, tenant and intended venue evidence are NOT RUN.
