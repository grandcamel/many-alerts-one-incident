# 19p local outcome: isolated permit lifecycle

Date: 2026-09-25. Fixed point: `fdd0f95`.

The proposed design and implementation plan were reviewed before the source
change. The resulting `forwarder_permit_model.PermitBook` owns exact handle
identities and privately copied bindings for one-use L1/L2 transitions. It
retains duplicate-ID tombstones, limits simultaneous open handles to 32 and
lifetime handles to 2,048, and closes a known handle on any failed attempt.
Tests cover copied and foreign handles, replay, mismatch, expiry, concurrency,
capacity, restart separation, hostile equality and forced caller mutation at
the staging and validation boundaries. Denials contain fixed codes.

Independent Standards and Spec source reviews pass after the identity-owned,
bounded-tombstone and private-snapshot corrections. Focused permit, dispatch
and exchange tests: **207 passed**. Changed-file Ruff and `git diff --check`
pass. The full local suite: **5,558 passed, 39 skipped in 392.54s**.

This is an isolated source/synthetic mechanics model. Any caller can stage an
untrusted binding; a positive model result is **not** dispatch authority. No
runtime route, gate or exchange imports the module. Permit-required routes
remain unavailable. There is no authenticated Receiver reply, independently
qualified reservation, durable effect intent, trusted receipt or production
Run/worker/launcher path. Provider, native, tenant, paid, venue and human
acceptance are **NOT RUN**. Tickets 36 and 37 remain open.
