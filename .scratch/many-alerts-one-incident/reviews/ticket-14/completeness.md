# Ticket 14 — boss completeness check (stage and replay reviewed)

Authority: .scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:9, decisions :101-117; docs/adr/0006-one-incident-per-fault-and-match-is-a-judgment.md:9-11. Planning only. The human subsequently accepted all seven round-2 recommendations; ticket 14’s Answer resolves the remaining choices listed in this historical checklist.

| Question clause | Coverage | Remaining decision |
| --- | --- | --- |
| Grafana grouping brings Cascade together | D2 retains folder+alertname; D1 selects 10m repeats | Confirm group_wait and group_interval (committed rules/cascade policy :19-20 has 10s each); reconcile count claim, not direction |
| One-at-a-time under multiple Notifications | D3 one in-flight plus one pending coalesced input | Exact equality key; whether changed values deserve a Run; duplicate-fingerprint ordering; retain source group identity |
| Rule for Match | D4 exact fingerprint then cascade+time candidate and Report judgment | Define time window; zero/multiple candidate and insufficient-evidence paths; stale exact-match admission |
| What Run reads | D4 candidate Report; ADR0006 persistent membership | State minimum evidence/time/member read contract; ticket16 owns ADF/storage shape |
| Alert filed under wrong Incident | Not answered | Human versus automatic correction, membership ownership, audit trail, impact on monotonic Severity |
| Second Incident for same Fault | Not answered | Whether/how duplicate is reconciled and who authorizes it |
| What later Run may change in Report | D3 says append evidence | Append-only versus mutable current summary; correction must preserve provenance; ticket16 handoff |
| Extending ADR0006 | D4-D6 supply new mechanics | Record only after human round2; no resolution yet |

Additional D5/D6 implementation contracts from Jira review: additive fp labels and cascade label, durable current per-fingerprint state (re-fire clears resolved marker), paired Severity/Urgency ratchet only after accepted membership. CLI edit support exists; live OPS editability NOT RUN.

D6 exception is a human decision: a wholly resolved source group can coexist with known-Firing members elsewhere. Do not silently delete agreed escape hatch. Proposed restriction for round2: no automatic exceptional closure overriding known-Firing accepted members.

Glossary handoff: CONTEXT.md:47-49 defines Notification as one POST; :65-67 defines Run as exactly one Notification. D3 changes the second definition; name aggregate input without redefining a POST. This is a documentation consequence, not a reopening of D3.

Acceptance boundaries: delivery-filter replay is not a counterfactual Grafana scheduler; source/CLI evidence is not live OPS acceptance; matched Run timing remains unmeasured. Timeout ownership stays ticket21; Report form stays ticket16; no cluster or demo run.
