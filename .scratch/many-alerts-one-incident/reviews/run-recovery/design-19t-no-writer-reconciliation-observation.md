# 19t: no-writer effect reconciliation observation replay

Status: proposed local source design, 2026-09-25. Fixed point: 19s pending.
Authority: accepted ADR 0012, ticket 37's proposed recovery specification and
reviewed 19h ordering. This is a bounded append-only observation claim. It
does not perform an OPS read, authenticate a read-back, settle an external
effect, authorize a retry, dispose of held work or clear a dispatch hold.

## Evidence gap and proposed record

The v3 journal stores effect intent and a claimed Forwarder receipt, but has
no independently replayable reconciliation observation. A process exit,
terminal success, absent receipt or lack of response cannot establish that
an OPS write was absent. A future Receiver-owned writer must make a fresh
OPS read under real route/grant/tenant identity and bind the exact target,
version, source and read-back custody. This unit has no such writer.

Add a private v3 recovery record `reconciliation_observation`, actor
`receiver`, bound to the current journal/Run/attempt and one existing
`effect_intent` operation/event/digest. Eligibility is closed to Jira OPS
mutation routes `jira.issue.create`, `jira.issue.update`, `jira.transition`
and `jira.comment.add`; model calls, read-only routes, Grafana/Kubernetes,
and Confluence intents cannot acquire an OPS reconciliation claim. The
source kind is `jira_issue_readback` for the first three and
`jira_comment_readback` for comment addition. This categorizes the claimed
source only; it does not assert the available API proves absence. Bind the current predecessor head,
launch event/digest, original Receiver boot, and monotonic observation.
The record has a closed reported state `confirmed`, `absent`, `conflict`, or
`unavailable`; route-specific source kind; source-evidence digest; target
digest equal to the effect intent; nullable version digest (required only
for `confirmed` or `conflict`); and a tagged self-digest. No raw OPS body,
URL, account identity, credential, prompt, tool body or provider identity
enters the record. A digest alone never authenticates a source or proves
absence. The journal reports every state as `reconciliation_unqualified`.

Allow at most four observations per existing operation to preserve an initial
unavailable read, a later result and a possible disagreement without an
unbounded log. Distinct event IDs and exact predecessor linkage retain
order; no last-write-wins projection resolves conflicts. The claim may
append after a hold, process closeout, effect receipt or outer deadline,
but only in the original launch boot. Restart needs a separately designed
recovery observation bound to new boot and renewed source authority.
At the 64-operation effect cap and a 2,048-byte body plus 384-byte
overhead, the family reserves at most 622,592 recovery bytes. A future
writer must preflight this obligation alongside 19n/q/r/s before ordinary
admission. When capacity is unavailable, preserve the outstanding effect
and hold; never infer absence or discard an obligation.

## Disposition boundary

Do not add `operator_disposition` or a positive `reconciled` state in this
unit. A separate operator-authenticated writer needs a verified current OPS
source, conflict handling, independently verified account relation and a
human choice before a fresh operation is authorized. A source-only schema
for such a positive decision would be misleading without those inputs.
The existing v1 `operator_action=resume` remains limited to its own
restart hold and cannot clear effect or Run holds.

## Acceptance

Keep the v1 state digest stable; use a separate tagged claim projection.
Live and stopped inspection show observation counts/digest, per-operation
reported state sequence and unqualified label without declaring an effect
confirmed. Test exact codec, replay/forgery, cap and recovery-byte refusal,
multiple/conflicting states, same-boot late append, restart refusal,
mixed-version reopen and old-decoder `journal_schema_unsupported`. Native,
provider, tenant, venue, paid, power-loss and human acceptance are NOT RUN.
