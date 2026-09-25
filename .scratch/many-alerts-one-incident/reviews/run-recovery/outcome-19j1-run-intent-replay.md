# Unit 19j1 no-writer Run-intent replay outcome

Status: **PASS_LOCAL_NO_WRITER**, 2026-09-25. Fixed point: `9ea0a4b`.

The private `(run_intent, 3)` record binds one v3 initial intent and
confirmation, the current original-admission member set, a claimed ledger
event/head and exact service lease claims. Anthropic, Jira, Grafana and
Kubernetes are mandatory; Confluence is the only optional fifth service.
Service names and lease claim UUIDs are distinct. A superseded original
member refuses the plan. The record is ordinary-class, and a single
outstanding claim has a separately tagged projection digest; v1 state and
older record formats retain their formulas. A bounded maximal five-service
shape measures **2,822 bytes** inside the new type-specific 4,096-byte
ceiling. Earlier private record types remain capped at 2,048 bytes.

Replay re-derives every field. Live snapshot and stopped verify-only inspect
label the claim `outstanding_unqualified`; a real SQLite/WAL mixed history
reopens, while an older decoder holds it as `journal_schema_unsupported`.
The [implementation plan](implementation-plan-19j1-run-intent-replay.md)
and independent Standards/Spec source reviews pass after a duplicate-service
finding was fixed with planner, codec and replay regressions. The final
focused set reports **267 passed**; changed-file Ruff and diff checks pass.
The full local suite passes: **5,496 passed, 39 skipped** in 388.72s.

The ledger head in this record is a structural, caller-supplied claim. No
ledger reservation was created, authenticated or read back, and no
application writer, Forwarder grant, launch, effect or permit exists for
this record. The current Receiver ledger has `population=unknown` and no
reservation events. Provider opening and charge identity, coverage,
liability U, independent continuity, archive registration and intended
venue durability remain external decisions. Native, provider, tenant, paid,
venue, deployment, power-loss and human adjudication are **NOT RUN**.
Tickets 36–38 remain open.
