# Ticket 31 — offline Cascade replay fixture specification

## Scope and roots

This is a future offline-harness contract for ticket 14. It does not implement the
Receiver or Skill, create a command, call Jira, run a model, or predict a changed
Grafana scheduler. Every `reviews/...` reference is relative to
`.scratch/many-alerts-one-incident/`; those captures are byte-identical
`prototype/cascade-timing` extracts (`reviews/ticket-14/jira/provenance.txt:1-4`).

Keep the existing replay separate. It posts a fixed three-file HTTP sequence and
exposes only `--receiver` and `--pause` (`grafana_jsm_sandbox/replay.py:25-29,48-58,77-86`);
tests require three 202s and three one-Notification Runs (`tests/test_replay.py:24-33`).
It remains a legacy regression seam; this specification adds no scenario selector.

## Future public contract and reset

The future library interface is
`replay_cascade_fixture(fixture, receiver_adapter, run_adapter, jira_adapter, match_stub) -> trace`.
This is not an existing CLI. It honours gates without sleeping and returns ordered
caller-visible events: `notification_admitted|suppressed|pending`,
`run_started|held|released`, reduced Run input (Fingerprint/current status/value/source
group), Match request/result, Jira write/read-back, appended Report entry,
`auto_complete|blocked`, and forced-completion audit entry. The Match stub returns
only its fixture verdict/confidence; it tests orchestration, never diagnosis, model
reasoning, telemetry, or live Jira.

Each case resets all adapters and sets `jira_now: 2030-01-01T12:00:00Z`. Aliases are symbolic notation only: expand them to full Fingerprints in every Notification, label and assertion:

| Alias | Fingerprint | Member |
| --- | --- | --- |
| PF | 5e8d72dc87b1ff35 | frontend C1 |
| PC | 6cd7e206a0716d2d | checkout C1 |
| PX | 8e2d9556f6c757b5 | frontend-proxy C1 |
| PA | f09facf2b8f5b694 | accounting C2 |
| PB | 4396dcd5ddc23476 | email C2 |
| PD | 4bde20aac01f95a2 | fraud-detection C2 |
| PE | b3587dd72657d226 | payment C2 |
| EM | 391dc40ca1dfd1a3 | email memory |
| ER | 3253da2ba16cb0cb | email restarting |
| EC | 90ec22b91f46a6ce | checkout confirmations |

These are read from `reviews/ticket-14/jira/capture-analysis.txt:1-18`. `CG1` and `CG2` are the exact `groupKey` values carried by payment lines 1 and 4; source grouping includes Grafana folder. Labels such as `fp-PF` below mean `fp-5e8d72dc87b1ff35`, never the alias text.

Unless replaced by a case, reset seeds this adapter Incident:

```yaml
OPS-100:
  status: Open
  created: 2030-01-01T11:50:00Z
  labels: [cascade-otel-demo, fp-PF]
  accepted_members: {PF: Firing}
  severity: Sev-1
  urgency: Critical
  report: ["opening evidence E0"]
  correction_pending: false
```

`accepted_members` and `correction_pending` are adapter controls, not a required
Jira storage representation. Every seed adds the `fp-` label for each accepted member and retains `cascade-otel-demo`; all seeds use the default clock/created/status/Report unless expressly overridden. Unless gated, finish one Run before delivering the next input. Baselines and pending state start empty unless explicitly seeded. New issue keys are allocated in fixture order from OPS-200. Default unmatched Firing judgment accepts the sole eligible OPS-100 with confidence `fixture-supported`; explicit overrides below replace it. No stub is called to bypass a missing eligibility check. Mutations default to success with read-back of the requested result and preserved unrelated fields; F13 overrides this. A case passes only when its read-back assertions match. No fixture chooses retry, compensation, timeout, or refusal behavior;
ticket 21 owns failure recovery.

Exact duplicate detection is **per source group**, against the latest **admitted**
sorted `(fingerprint,status,values)` record. This baseline is human-accepted.
Pending reduction is a separate global-per-Fingerprint scope: while any Run is
held/in flight it retains the latest local arrival and that arrival’s source group.
Thus cross-group dedupe stays per source group while pending merge is global per
Fingerprint.

### Fixture document

Use versioned YAML case documents in the future `fixtures/cascade/` collection; no such runnable collection is implemented here. Required case-local fields must be fully expanded before execution.

```yaml
version: 1
id: string
origin: captured | synthetic
policy: {group_wait_s: 10, group_interval_s: 10, repeat_interval_s: 600}
jira_now: ISO-8601
initial_incidents: [explicit adapter state]
notifications: [{arrival, source_group, capture: {path, line} | post}]
gates: [{after_arrival, hold_run: G0} | {release_run: G0}]
match_stub: [{request, candidates, verdict: accept|reject|ambiguous, selected_key, confidence}]
jira_stub: [{operation, result: success|failure, readback}]
human_authorization: null | {forced_complete: {incident, unresolved_members}}
expect: {trace, run_inputs, incident_readbacks, prohibited_effects}
```

Synthetic CG1 record A means PF/Firing with `values: {A: 1, B: 1}`; B means the same full record with `values.A: 2`. Use the Grafana body shape from payment line 1 with these explicitly recorded edits. Synthetic Resolved variants set the chosen member's status to resolved and values to `{A: 0, B: 0}`; recompute top-level status consistently with members. A synthetic multi-member post records its full labels and member list, never just aliases. E0/E1/C1 below are literal fixture Report entries; C1 is an evidence correction, not a membership-reassignment instruction.

## Deterministic matrix

| ID | Input/setup | Required caller-visible outcome |
| --- | --- | --- |
| F01 identity | Synthetic `CG1` record A twice, identical including values. | First A admits/starts one Run; second is `suppressed`; no second Run or Jira write. |
| F02 changed value | Captured payment lines 1 then 2: `PF/Firing`, A `0.1144→0.1957` (`reviews/ticket-14/jira/notifications-paymentUnreachable.jsonl:1-2`). | Both admit and reach Match/Run routing; second cannot be suppressed on Fingerprint/status alone. |
| F03 A→B→A | Complete an initial synthetic CG1 A Run; then hold unrelated G0 and deliver B (changed values), A. Last-completed CG1 remains A while B/A arrive. | Initial A and both later inputs admit. There is one pending input with final A, then one CG1 Run after release. A comparison against last-completed A would wrongly suppress final A. |
| F04 resolved→firing | Seed PF/PC/PX Firing; hold separate `G0` before delivering payment lines 16, 18, 20. | All enter pending; PC/PX reduce to line-20 Firing, not line-16 Resolved. On release reduce first, then apply normal Firing-before-Resolved order. (`reviews/ticket-14/jira/notifications-paymentUnreachable.jsonl:16,18,20`) |
| F05 firing→resolved | Seed PF Firing; hold `G0`; send synthetic PF Firing then explicit PF Resolved. | Released aggregate carries Resolved and can update only that explicit member. |
| F06 omission | Seed PF/PC/PX Firing; hold `G0`; synthetic post has PF/PC/PX Firing, then PF-only Firing. | PC/PX remain Firing. Omission is never Resolved. Synthetic data is required because captured payment 23→24 omits already-Resolved members. |
| F07 mixed groups | Hold `G0`; send payment line 20 (`CG1`, three Firing) and 21 (`CG2`, all Resolved); initial OPS-100 accepts PF/PC/PX/PA/PB/PD/PE, all Firing. | Reduced input carries both groups; C2’s resolution produces no `auto_complete` while accepted C1 is Firing. (`reviews/ticket-14/jira/notifications-paymentUnreachable.jsonl:20-21`) |
| F08 additive ratchet | Replace default seed with OPS-101 holding synthetic warning W1 (fingerprint fixture-w1), Sev-2/High; send synthetic critical C1 (fixture-c1), then warning W2 (fixture-w2); both judgments accept OPS-101. | Each success read-back preserves cascade, `fp-fixture-w1`, `fp-fixture-c1`, `fp-fixture-w2`; requests use `update.labels: [{"add":...}]`, never `labels[0]`; read-back becomes `Sev-1/Critical` after C1 and stays so after W2. (`reviews/ticket-14/jira/cli-request-construction.txt:2-6`) |
| F09 rejected candidate | Existing OPS-100 accepts only PF; a new synthetic critical fixture-rejected member in the same cascade gets stub reject with rationale. | Create a separate Incident with rejection rationale. Existing membership, labels, Severity and Urgency stay unchanged. |
| F10 age/multiple candidates | Parameterize a single candidate at each age 1799/1800/1801 seconds for both exact-fp and cascade lookup. Separately seed OPS-100 and OPS-101 as two eligible cascade candidates for a new synthetic Fingerprint; test a judgment selecting OPS-101 and an ambiguous judgment. | **F-AGE-01 fixture boundary:** age `<=1800s` is eligible; 1801 is stale/human-owned. Stub receives both candidate Reports/members/times. `accept` mutates only selected Incident; `ambiguous` creates separate ambiguity Incident; no merge. |
| F11a wrong-Match correction | Seed OPS-100 with PF Resolved and correction_pending=true; deliver a PF Resolved Notification with linked wrong-Match evidence. | Append linked correction/evidence without member move or Severity lowering; otherwise-resolved state is `auto_complete_blocked`. |
| F11b duplicate correction | Seed OPS-100 and OPS-101 as duplicates, each with its explicit member set fully Resolved and correction_pending=true; supply a human-review correction proposal linking the keys. | Append linked correction/evidence to both; prohibit automatic merge, membership move, or Severity lowering; both automatic completions remain blocked. |
| F12 normal/forced completion | Normal variant: seed OPS-100 with EM/ER/EC all Firing and consume email lines 57, 62, 63, draining each Run. Forced variants: reset with PF Resolved and PC Firing, deliver PF Resolved; test without authorization and with explicit OPS-100 forced-complete authorization naming PC. | Normal completion only after every accepted member is explicitly Resolved. Without authorization forced variant remains open; with authorization it completes and audit read-back names exactly the actual unresolved Fingerprint PC (expanded), rather than trusting an incomplete supplied list. (`reviews/ticket-14/jira/notifications-emailMemoryLeak.jsonl:57,62-63`) |
| F13 edit failure | Seed OPS-100 with PF Firing; accept new synthetic critical fixture-failed but return label-update failure and unchanged incident read-back. | Trace exposes failure; no completed membership, ratchet, or completion claim. No retry assertion. |
| F14 append provenance | Existing Report `[E0]`; accepted evidence E1 then correction C1. | Read-back Report is `[E0,E1,C1]` in order, with E0 byte-identical. This is semantic provenance, not ticket-16 ADF rendering. |

F08 is wholly synthetic: never relabel a captured critical PC as warning while calling it an unmodified capture. Synthetic Fingerprints are explicit strings accepted by Notification validation; they are not represented as Grafana-generated hashes. Shapes may be derived from cart lines 1/6 only if every edit is recorded.

For gated cases, G0 is a separate synthetic source-group Run whose spawner is held before any case-specific Jira operation; its input does not seed the groups under test. Each fixture records G0 separately so total Run counts cannot accidentally include/exclude it. The existing controllable spawner seam is `tests/conftest.py:95-98,109-119`.

F-AGE-01 selects inclusive age 1800 seconds as the deterministic interpretation of the approved thirty-minute window; no separate user preference or measurement is claimed. Future-created Incidents are not included by these boundary cases. Captured-body cases use each JSONL row's `body`, not the sink envelope; preserve Alert timestamps unchanged, and control Jira's clock independently. The recorded source POST time is provenance, not the fixture's arrival schedule. Each instantiated fixture must contain full initial members, judgments, gate actions and expected events, resolving the matrix shorthand before execution.

## Boundaries

The suite asserts Receiver/Run/Jira orchestration only. It excludes Report ADF form
(ticket 16), timeout/refusal/retry (ticket 21), live OPS editability, model quality,
matched-Run speed, cluster state, and Grafana’s counterfactual 10-minute scheduler.
The historical filter’s 8/12 result is not a Run-count oracle
(`reviews/ticket-14/replay/report.md:1-5,36-45`). Physical correction-pending storage
is intentionally unspecified: adapters seed and verify its semantic completion hold.


## Acceptance layers

Receiver acceptance must drive the real HTTP `/notification` boundary and observe the injected spawner's inputs/gates, following `tests/conftest.py:129-139`; substituting a fake Receiver does not satisfy it. Mutation-contract checks must capture actual proposed Jira commands, pass them through the installed self-documenting v2 CLI into a stateful offline Jira adapter, and assert request construction plus read-back. The existing `tests/conftest.py:3-6` documents the real Forwarder/fake-upstream seam. An adapter seeded with expected results alone cannot prove a mutation occurred.

Because the Skill is presently prose executed by a model, a scripted Run can prove orchestration and CLI mutation contracts only. It cannot be counted as proof that the future Skill follows the decisions. Report Skill conformance/model-quality acceptance separately; no live model invocation is required or claimed by this fixture specification. The source checks are in [source-checks.md](source-checks.md).
