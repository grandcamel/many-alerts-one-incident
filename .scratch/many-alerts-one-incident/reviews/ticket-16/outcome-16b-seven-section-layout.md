# 16b outcome: seven-section local ADF layout

Status: reviewed local source and synthetic verification, 2026-09-25.
The [design](design-16b-seven-section-layout.md) adds a pure builder for
exactly seven caller-supplied Report section texts in the ticket-16 order.
It produces fixed heading/paragraph ADF through the reviewed 16a preflight,
which returns canonical UTF-8 bytes, byte count and SHA-256 under the 8,192
byte document cap. Missing, extra, blank and nontext sections fail closed.
Citation IDs and URLs remain inert text; the output carries no support,
completeness or grade claim.

Independent Standards and Spec source reviews pass. The focused layout and
ADF suites passed **26 tests**; Ruff and `git diff --check` passed. The full
local suite passed **5,695 tests, 39 skipped in 454.68s**.

The builder accepts only already-sanitized caller text as a local fixture.
Claim-to-returned-response support, source-specific citation checks,
immutable revision custody, ticket-39 private capture, bounded native Jira
transport, tenant permission/effect read-back and human adjudication remain
open. Native, provider, paid, tenant, venue and human acceptance are **NOT
RUN**. Ticket 16 remains open.
