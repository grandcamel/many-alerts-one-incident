# Memory storage and offline acceptance

Type: task
Status: open
Blocked by: 13, 16, 17, 21, 33

## Question

Produce an implementation-ready specification, not runtime code, for ADR 0009. Define the OPS representation of current member state; narrow structured append/read interface, provenance and correction schema, atomicity and bounded retrieval; dedicated persistent path and restart/reset wiring; rehearsal isolation that preserves ticket 14's membership labels and eligibility; and draft identity/version/reconciliation across partial failures. Specify fresh-rehearsal preflight that waits for prior eligible OPS Incidents to age out or receive explicit human disposition, with no silent filtering or automatic closure. Carry Confluence scope from ticket 33 and refusal/retry mechanics from ticket 21.

Specify offline acceptance through real caller boundaries for source verification, stale/superseded learning, missing stores, confirmed OPS plus failed secondary writes, uncertain draft creation, directory loss, restart persistence, fresh-rehearsal isolation and Ground-truth exclusion. Keep CLI/source, offline fixture, model/Skill and live tenant/volume acceptance distinct. Ticket 31's Cascade fixtures remain valid and must be extended or referenced, not replaced by stubs presented as model proof.

## Inputs

[Ticket 13](13-memory.md#answer), [ADR 0009](../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md), and [offline facts](../reviews/ticket-13/facts.md). No cluster, live write or implementation is authorized by this planning ticket.

## Accepted venue input from ticket 30

ADR 0016 uses a fresh venue for each presentation/full rehearsal and requires protected state handoff before destruction. Keep Memory reset distinct from unresolved work, weekly spend and private audit retention. No cluster deletion may silently alter external OPS/Confluence history or evade fresh-rehearsal candidate eligibility.

## Accepted Confluence input from ticket 33

ADR 0017 adds operator-owned exact reference version/digest manifests and durable tenant/Incident-to-draft mappings. Preserve mapping/approval history across handoff without exposing prior-rehearsal drafts to new Runs. Reference freeze never overrides immediate revocation; changed bodies and unresolved draft conflicts disclose degraded Memory. Ticket 43 specifies the concrete interface.

## Accepted audience input from ticket 34

ADR 0018 needs sanitized confirmed-record projections with provenance, source time/version and incomplete/corrected states, scoped to selected rehearsal/Run/Incident. Availability and actual retrieval are distinct. Ticket 44 consumes these read-only interfaces; no raw Memory payload, prior-rehearsal context or scoring material may leak through presentation.

## Source progress — 2026-09-22

The [Memory specification](../reviews/ticket-32/memory-specification.md) defines
the proposed OPS adapter projection, narrow structured append/read service,
immutable source/correction records, persistence and bounded reset/handoff,
rehearsal admission, and reuse of ticket 43's draft mapping. The
[integration review](../reviews/memory-venue-audience-integration.md) joins it to
venue teardown and the operator audience without turning Memory into an Incident
authority or hiding still-eligible prior OPS Incidents.

This remains open: native current-member representation/migration, conditional
updates and read-back, volume/identity/durability choices, and exact source and
Confluence bindings need evidence. Offline acceptance cases are specified, not
executed. No runtime, model, tenant, paid experiment or deployment was performed.
