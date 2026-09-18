# Memory

Type: grilling
Status: resolved
Blocked by: 06

## Question

What lives in each of Memory's three stores, the Incidents in OPS, the Confluence space reached through `confluence-as`, and the Memory directory? What a Run reads before it judges a Match, what it writes after it reports, what seeds the Confluence space (a service catalog, runbooks, past postmortems), and whether a Run writes a postmortem page there. How the Memory directory persists through the container boundary, as the one exception to "nothing survives a restart" (ADR 0005). Produces an ADR.

## Work history

Claimed as the next eligible planning ticket after tickets 14 and 31 were committed. Scope is offline evidence and a human decision round for Memory; no live Confluence/Jira writes, cluster, demo or runtime implementation.

## Comments

Offline discovery and the first proposed decision round are recorded in [facts](../reviews/ticket-13/facts.md), [CLI output](../reviews/ticket-13/cli.txt), and [round 1](../reviews/ticket-13/round-1.md). The installed CLI exposes native draft creation, but live tenant acceptance is unverified. Current Run authority and tmpfs-only storage do not implement persistent Memory. At that stage, store responsibility, seed contents, Run-authored drafts, persistence lifetime, and write authority awaited human decisions.

The human accepted all five [round-1 decisions](../reviews/ticket-13/round-1.md): store roles, seed contents, reviewed postmortem drafts, rehearsal persistence, and narrow structured append authority. The human subsequently accepted [round 2](../reviews/ticket-13/round-2.md) on ordering, unavailable stores, provenance/corrections, draft lifecycle, and rehearsal isolation.

## Answer

The human accepted both five-question rounds: [round 1](../reviews/ticket-13/round-1.md) and [round 2](../reviews/ticket-13/round-2.md). [ADR 0009](../../../docs/adr/0009-memory-has-one-incident-authority-and-reviewed-learning.md) records the resulting contract. OPS owns Incident/member state; Confluence holds reviewed reference knowledge; the persistent Memory directory holds cited observations and retrieval hints. Reads precede Match and cannot override ticket 14. Learning follows confirmed OPS writes; one reviewable postmortem draft follows confirmed normal completion. Human review gates reuse, corrections preserve history, and unavailable secondary stores do not undo confirmed OPS results.

The operator resets the directory for a fresh rehearsal; it survives Runs and container/pod restarts within that rehearsal. Prior-rehearsal observations require explicit approval as reference material. A narrow structured append interface extends the planned authority and persistence boundaries without granting broad Write. Ground truth remains excluded under ADR 0008.

Remaining work is explicit: [storage and offline acceptance](32-memory-storage-and-offline-acceptance.md), [Confluence scope and permissions](33-confluence-space-and-permissions.md), and [audience view](34-what-the-audience-sees-of-memory.md). Report form remains ticket 16, forwarding ticket 17, failure/retry mechanics ticket 21. [Evidence](../reviews/ticket-13/facts.md) is offline source/CLI only; no Skill/runtime implementation, live tenant acceptance, cluster or demo was performed.

## Accepted integration decision

Round 2 excludes previous rehearsal observations unless approved, but [ticket 14](14-many-to-one-under-a-cascade.md#answer) requires candidate lookup for eligible open OPS Incidents created within thirty minutes. A fresh rehearsal begun sooner can encounter one. The human agreed: block fresh-rehearsal admission until such prior Incidents age out or a human explicitly disposes of them; never silently filter or automatically close them. The two accepted rounds remain accepted. This settles the final boundary: ADR 0009 is accepted and this planning ticket is resolved. No runtime implementation or commit is implied.
