# Ticket 17 consolidation review

A sequential read-only review found no policy conflict requiring another human choice. Mandatory Jira/Grafana/Kubernetes readiness gates starting new Runs; it does not replace ticket 21's mid-Run outcome/recovery contract. Confluence remains optional with visible missing Memory under ADR 0009, while telemetry export stays best effort under ADR 0010. Read/rehearsal scope is an enforced access boundary, not an availability guarantee.

ADR 0011 preserves ticket 12's exact Eyes tool/operation choice, ticket 19's client prototype, ticket 21's failure classification and ticket 33's Confluence grants. Concrete control/OS isolation, trust wiring, leases, query policies and deployment checks belong to ticket 36; none is claimed implemented or live-verified. ADR 0007's inaccurate pod/container wording is corrected explicitly.
