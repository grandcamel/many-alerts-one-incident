# 35a outcome: synthetic Receiver gap bytes

Status: reviewed local source and synthetic verification, 2026-09-25.
The [design](design-35a-receiver-gap-codec.md) and corrected
[proposed telemetry specification](telemetry-specification.md) put
`telemetry_omitted` and `telemetry_gap` records in the `run_gaps` envelope.
The pure codec pins a closed Receiver-origin subset with canonical UTF-8
bytes, a stable event ID, external byte count and SHA-256, and exact
kind/code/count/range validation under a 2,048-byte marker cap. It does not
mint trusted Receiver identity, enqueue, coalesce, deliver, or attest a gap.

Independent Standards and Spec source reviews pass. The Spec review found an
identity-tuple mismatch and a known count larger than its affected sequence
range; both were corrected with focused tests. The 35a suite passed **20
tests**; Ruff and `git diff --check` passed. The full local suite passed
**5,685 tests, 39 skipped in 454.95s**.

Actual Receiver/transport callers, queue capacity and retry enforcement,
native/exporter fields, sanitized query access, shared 24-hour retention,
current venue behavior and audience rendering remain open. Native, provider,
paid, tenant, venue and human acceptance are **NOT RUN**. Ticket 35 remains
open.
