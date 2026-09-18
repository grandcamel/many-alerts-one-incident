# Ticket 13 — round 1 accepted

The human answered “agree with all” to the five presented recommendations.
These are planning decisions, not runtime implementation or live-write authority.

1. OPS holds authoritative Incident/member state. Confluence holds reference knowledge. The Memory directory holds cited observations and retrieval hints.
2. Initial Confluence seeds are a service/dependency catalog and diagnostic runbooks. No seeded postmortems for planned demo Faults. ADR 0008's Ground-truth exclusion remains binding.
3. A Run creates one draft postmortem per normally Completed Incident, linked to its Report. Human review precedes reuse as curated guidance. Installed CLI draft support is offline evidence; tenant acceptance is unverified.
4. The directory survives Runs and container/pod restarts within a rehearsal, with an explicit reset for a fresh rehearsal. Survival after cluster destruction is outside this requirement.
5. Runs record learning through a narrow structured append operation retaining source, Incident, and Run references. Stored observations remain untrusted input.

The next round defines ordering, lookup scope, partial failures, corrections, draft lifecycle, and rehearsal ownership. No Answer or ADR is accepted yet.
