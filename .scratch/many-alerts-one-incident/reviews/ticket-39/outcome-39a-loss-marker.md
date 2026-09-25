# 39a outcome: content-free local audit loss marker

Status: reviewed local source and synthetic verification, 2026-09-25.
The [design](design-39a-loss-marker.md) pins a strict `audit_loss` v1
payload for a local request, response or Report capture gap. The pure codec
requires lowercase UUIDv4 identities, a closed side/state/code matrix,
exact UTC timestamp syntax or null, and fixed `unqualified_local` source.
It emits canonical UTF-8 bytes with external byte count and SHA-256 under a
1,024-byte record cap. No source body, native provenance, grade or clean
qualification field is accepted. A complete `empty` response remains a
separate future exchange state and cannot become `missing` here.

Independent Standards and Spec source reviews pass. The Spec review found a
mutable state/code registry; it was frozen and a regression test added.
The focused 39a suite passed **21 tests**; Ruff and `git diff --check`
passed. The full local suite passed **5,665 tests, 39 skipped in 437.54s**.

This is a format, not a durable marker. It has no capture adapter, redactor,
private store, append/read-back, manifest chain, quota reservation, expiry,
operator access or human review. Native, provider, paid, tenant, venue,
protected export and human acceptance are **NOT RUN**. Ticket 39 remains
open.
