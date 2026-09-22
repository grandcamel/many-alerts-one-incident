# Venue lifecycle and protected teardown specification

Type: task
Status: open
Blocked by: 30, 37, 38, 39, 41

## Question

Produce an implementation-ready specification for [ADR 0016](../../../docs/adr/0016-venue-lifetime-is-bounded-with-protected-teardown.md), not runtime changes or infrastructure actions. Define operator lifecycle states and the authoritative cluster-creation age source, restart/clock-skew/missing-age behavior, age-30 session-start gate, 30-minute presentation window, age-85 Run-launch cutoff and age-90 hold/recovery boundary. A timer is not deletion authority. Hold ordinary dispatch without dropping bounded pending Notifications or uncertain work; preserve ADR 0012's deadline and containment precedence.

Specify five-minute baseline readiness, observations at most 60 seconds old, verified LGTM/load-generator limit and working-set queries, below-80-percent admission, at least 25 percent node memory available and pressure/eviction checks. Define authoritative timestamps, sample coverage and denominator semantics; never infer health from missing data. Map expected Fault symptoms versus unrelated venue conditions without muting C4 cluster-wide coverage or rewriting an infrastructure Alert's identity. Integrate OPS candidate eligibility, mandatory route readiness, Change state, private capture and budget gates.

Define $10 weekly cloud accounting with $2 reserved before each creation attempt, operator-only control, an off-cluster durable ledger and attribution/reconciliation of all relevant resources and delayed charges. Combine interfaces with ticket 38 without mixing the $150 model and $10 venue envelopes or double-counting reservations as spend. Verify current provider pricing/limits only in separately authorized preflight; these policy dollars are not a provider charge guarantee.

Specify the off-cluster recovery manifest, artifact inventory, safe export permissions, record versions, checksums/read-back and explicit named acceptance of unresolved Receiver/Change/external-effect obligations. Preserve audit artifacts and existing retention limits, model/cloud weekly reservations and external OPS/Confluence history. Enforce handoff before source destruction, except an explicit exceptional human decision on evidence loss. Define safe partial-export recovery, missing evidence, emergency undo, operator disposition and restart from retained state. A completed handoff must not mark uncertain writes complete or let a new rehearsal evade eligibility/spend gates.

Specify provider-inventory cleanup verification, residual resource ownership, ambiguous deletion and ongoing-cost escalation. No automatic recreation or resource-tier increase; no invented proof of zero future billing from empty inventory alone. Preserve charge reconciliation after infrastructure is gone.

Offline fixtures must use real lifecycle/admission/clock/health/ledger/export boundaries: exact age edges, time jumps/restarts/missing age, late readiness, stale/absent health, expected Fault restarts, unrelated critical conditions, active/pending Runs at drain, concurrent reservations, failed setup, unknown charges, full/lost journals, interrupted export, digest mismatch, expired audit evidence, uncertain deletion and orphan resources. Keep offline proof distinct from provider/tenant and intended-venue acceptance.

Plan the separately authorized no-Fault 90-minute venue baseline and three candidate qualification lifecycles on fresh venues within existing budgets. Include actual settings, observations, overruns, failures, cost and cleanup receipts. Do not run these measurements, provision, delete, purchase or modify credentials under this specification ticket. A failed gate retains labelled replay and produces a bounded tuning/measurement follow-up.

Clarify exact `<85 minutes` Run admission and that queue wait, restarts and handoff never reset age or extend the 300-second Run deadline. Define restart-safe cluster age from verified creation evidence plus monotonic elapsed checks; unknown/skewed age cannot admit optimistically. Keep handoff operator-only, with no automatic import of prior-rehearsal Memory into Runs or promotion into authoritative OPS state. Explicitly define the permitted Memory-assisted qualification setup using same-rehearsal prior learning or approved reference material under ADR 0009, not an unreviewed recovery export. The no-Fault baseline is a separate venue gate, not a scored model sample.

## Source progress — 2026-09-22

The [venue specification](../reviews/ticket-42/venue-specification.md) defines
proposed lifecycle, creation-age and health observations, weekly/aggregate cost
admission, independent handoff verification and named acceptance, bounded cleanup
inventory, and future offline/venue acceptance. The
[integration review](../reviews/memory-venue-audience-integration.md) preserves
each store's retention, uncertain effects and accounting after reset or teardown.

This remains open for concrete provider timestamp/inventory/billing semantics,
resource and metric bindings, private vault permissions/read-back, and later
intended-venue evidence. No provisioning, deletion, pricing probe, credential
change or paid baseline was performed. Age 90 remains a hold, not deletion
authority; unknown historical and residual-resource charges remain liabilities.
