# Ticket 23 — source preparation, 2026-09-21

Status: source-only design. No executor implementation or model measurement is supplied.
The [execution card](execution-card.md) is **CLOSED**. Ticket 23 remains open.

This records the initial design phase. The subsequent
[offline implementation outcome](implementation-outcome.md) describes the replay core
and its tests; native bindings and paid execution remain closed.

## Scope and evidence

Prepare a new diagnostic series for the unfinished Fable timing arm and the fixed
command-length experiment. Preserve historical results; do not revive their commands,
credit explanation or universal-threshold claim. This work is independent of ticket
19's rejected C2 correction/review packet and does not resubmit it.

Historical source is pinned at `79a14c8904f3a125d1f03b192d10797d30979c86`
(`prototype/run-timing` at inspection). Paths and line numbers below are relative to
that commit, under `prototype/run-timing/`, not main. Inspect with `git show`;
[source-manifest.json](source-manifest.json) records the source digests. Main baseline:
`027f7c197e6bff2eb34e95217a6924e0aa76da68`. Unrelated C2 work is preserved.

| Historical evidence | Gap | Replacement requirement |
| --- | --- | --- |
| `measure.py:49–66,76–82` | Direct CLI plus inherited host environment and PATH; tool preapproval does not isolate credentials or execution. | Minimal environment, sealed fixture mounts, mediated API sentinel, fixed executables and verified direct-route prevention. |
| `measure.py:69–73` | Reusing an arm deletes prior evidence. | Unique attempt ID; exclusive creation, refuse existing output directory, retain unsettled evidence. |
| `measure.py:87–111,209–210`; `arms.sh:5–8` | 900-second guard; immediate SIGKILL then unbounded wait; wrapper returns zero after child failure. | Monotonic 270/20/10 lifecycle and verified descendant containment within 300 seconds. Derived outcome must govern exit/reporting. |
| `measure.py:125–150,154–168` | Malformed events silently skipped, last terminal wins, initial model treated as identity, text matching counts denials. | Versioned native-event adapter, strict terminal validation, actual model/fallback evidence and correlated dispatch observations. |
| `bin/jira-as:18–19,40–42,66–68,146–155` | A logged dispatch can exit nonzero because OPS-1 is absent. Log paths are caller-controlled. | Supervisor-owned dispatch receipt independent of stub exit; no live Jira routes or credentials. |
| `bin/jira-as:130–144` | Historical update adds labels; this is a fixture behavior, not evidence about current jira-as. | Label behavior must be explicitly frozen as synthetic or separately redesigned; never infer installed/live semantics from this stub. |
| `probe/PROBE.md:1–30` | Binary ran/denied and unconditional continuation conflate permission denial, provider refusal and missing evidence. | Fixed cases with separate exact-command, dispatch, tool-result and Run outcomes; provider refusal stops this experiment. |
| `score.py:29–46,64–84`; `fixtures/ground-truth.md` | Regex mentions and historical flag-name scoring cannot establish supported Mechanism diagnosis. | Separate human Mechanism/evidence grades and claim-to-returned-evidence audit under ADR 0014. |

Local read-only inspection found Claude Code **2.1.278**. Its help advertises
`--safe-mode`, `--tools`, `--allowedTools`, `--effort`, `--max-budget-usd`, and
`--fallback-model`. This establishes option spelling only. Actual model availability,
effective policy, auth, streaming, routing, cancellation and costs remain NOT RUN.
Tool selection and tool preapproval are distinct; safe mode does not establish OS
isolation. See the [official CLI reference](https://code.claude.com/docs/en/cli-reference).
Freeze installed help/version again at implementation and execution preflight.

## Revised probe and fixture contract

Two independently admitted attempts are proposed, not authorized: one Fable synthetic
timing Run, then one Haiku length Run. Never launch them as an unconditional batch.
Each would reserve $3 and consume one diagnostic attempt; an authorized retry is a
new attempt. Five tool cases within the length Run are not five model Runs. Reconcile
the first attempt before admitting another. Neither series qualifies a model or venue.

**Timing arm.** Preserve the seven-Alert synthetic cascade and canned telemetry from
the pinned source for a reproducible diagnostic. Freeze revised Skill/prompt, tools,
fixture hashes, rubric and explicit effort before launch. Requested historical model
is `claude-fable-5-1`, effort `high`; availability and actual identity require fresh
evidence. No substitution. The historical draft Skill and scorer are inputs to review,
not approved current implementations. Only a local synthetic Incident may be created
as part of the diagnostic task; no real Incident or permission-test mutation is allowed.
Retain every Report revision and the exact returned evidence used to audit it.

**Length arm.** [fixtures/length-cases.json](fixtures/length-cases.json) contains the
five historical commands as inert JSON strings. Each is ASCII; command bytes exclude
the single file-terminating LF. Source-file hashes include that LF. Only padding length
varies. Keep case order 9500, 11000, 12000, 13000, 14000; no adaptive expansion, alternate
spelling, wrappers or shortening. Requested family is historical Haiku 4.5; exact model
identifier and supported explicit effort remain unset execution gates. This isolates a
single command shape, not all CLI requests. Do not materialize shell scripts or execute
these strings during source preparation.

Before a future length Run, a reviewed isolated adapter must resolve `jira-as` solely
to an inert receipt stub with no network or Incident state. The legacy comment spelling
and OPS-1 are test data, not permission to reach OPS. The adapter observes exact command
bytes at the Bash boundary and records an authenticated supervisor-owned receipt for
stub entry/argv, then returns a fixed synthetic response. A separate offline test must
prove receipt authenticity, no host executable substitution and no live route. Read-only
case files are the only input; audit/rubric/ground-truth files stay outside Run mounts.

For each case preserve: case ID, expected and observed command digest/byte count,
tool-use ID, structured permission decision with native evidence reference, dispatch
receipt, stub exit/result, timestamps and evidence completeness. Classify separately:

- Exact command and trusted receipt: `dispatched`, even if the stub exits nonzero.
- Proven native permission denial before dispatch with complete observation coverage:
  `permission_denied_no_dispatch`. A missing receipt alone does not prove this.
- Edited command: `invalid_case`; never count it as a length observation.
- Missing, conflicting or incomplete dispatch evidence: `dispatch_unknown`; stop and
  inspect. Never turn absence of a log into proof that a command did not run.
- Provider refusal/safeguard, unavailable model or fallback: stop the attempt, preserve
  evidence and hold further dispatch; do not reword, reroute or switch models.

Fallback detected during a Run enters interruption/revocation and cleanup; an observed
cancellation overrides a successful terminal result. If fallback is discovered only
after otherwise completed execution, retain that execution outcome but invalidate the
model comparison and hold further dispatch. Do not invent a retrospective cancellation.

Continue to the next fixed case only after a classified ordinary permission outcome
or completed stub dispatch, while the original work deadline permits it. No retry of
a denied case. Cases not reached are `not_attempted`; a provider refusal is not a data
point about command length. Report a version/policy/auth/shape-specific observed bracket
only when the comparable exact cases support monotonic separation. Otherwise report
all accepted/all denied/nonmonotonic/inconclusive as appropriate. Five samples cannot
pin an exact threshold or establish a universal limit or causation by length alone.

## Lifecycle, evidence and admission

The supervisor starts a monotonic deadline at process launch: startup/work through
270 seconds, revoke sentinels and SIGINT by then, up to 20 seconds for local flush,
then up to 10 for force-kill/reap. Cancellation starts cleanup sooner; it cannot extend
the original 300-second bound. No new upstream calls during cleanup. Track descendants
and held pipes after parent exit. Unconfirmed containment by 300 seconds is a failure
and dispatch hold, not an extended wait. Upstream requests already dispatched can still
finish and bill; revocation is not rollback. Queue wait is separate.

Execution, effects, model identity, audit completeness and spend are separate fields.
Observed spawn/timeout/cancel/containment failures override a clean terminal result.
Only one recognized well-formed successful terminal result, exit zero and no override
supports completed execution. Result errors/nonzero exit prevent success; missing or
malformed required evidence and duplicate/conflicting terminal results are incomplete.
Retain all reasons rather than choosing a last event. Missing usage/actuals remain null
with an explicit unknown status. [fixtures/outcome-cases.json](fixtures/outcome-cases.json)
is an acceptance-case specification, not an implemented parser or passed runtime test.

Reserve durably before launch against current weekly and diagnostic allocations under
ADR 0013. Verify current rates, limits, provider billing visibility/lag and outstanding
exposure; do not compute remaining money from transcript estimates. Previous ticket 19
telemetry-only exceptions do not apply here. Client dollar guards are secondary, not a
hard billing ceiling. Unknown exposure retains reservations and can hold new admission.
No new ledger or calendar week erases existing obligations.

The Run receives only its sentinel and minimum fixture access; the upstream key and
host auth/config remain outside. Verify fixed Forwarder endpoint, TLS/trust, streaming,
credential substitution, revocation, native-client behavior and direct-route prevention
under ticket 36's contract. Missing mediation is a closed gate, not a direct-key fallback.
Observe every actual assistant model identifier and native fallback event; initial
configuration alone is insufficient. Missing identity evidence makes comparison invalid.

Private correlated capture is operator-owned outside Git and Run mounts, credential
sanitized, at most 100 MiB per Run / 2 GiB total / 30 days per ADR 0014. Capacity/capture
failure must remain visible and bounded; it cannot silently lose evidence or authorize
new writes. Report affected claims as unverifiable. Keep compact metadata/digests local.
Named human review assigns Mechanism and evidence grades separately, checks arithmetic,
and reviews every Report revision; automated regex checks cannot award semantic passes.

This is a new series: changed budget/auth/policy/rubric preclude a controlled comparison
with the historical 900-second arms. Preserve old results verbatim. Eventual new results
must report failures and unattempted cases alongside successes, with estimates distinct
from billed actuals. Three representative lifecycle samples, intended venue/auth and
all other ADR 0013/0014 gates remain necessary for qualification.

## Implementation acceptance still required

1. Build and independently review the supervisor, minimal sandbox/fixture bundle,
   inert receipt adapter, strict native-event adapter and bounded audit capture.
2. Offline tests: deadline/cancel boundaries; descendants holding pipes; spawn and
   terminal errors; missing/duplicate/malformed events; fallback/identity loss;
   receipt spoofing/loss and nonzero stub exit; output collision; capture exhaustion;
   sentinel revoke/direct-route denial; missing ledger/unknown spend and attempt caps.
3. Verify mediated native client compatibility and current budget/billing preflight
   under separately scoped authority. Freeze all executable hashes and measurements.
4. Complete a concrete one-attempt card and obtain separate execution authorization.

Accepted sources: [ADR 0012](../../../../docs/adr/0012-run-outcomes-and-recovery-are-explicit.md),
[ADR 0013](../../../../docs/adr/0013-demo-spend-is-metered-reserved-and-qualified.md),
[ADR 0014](../../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md).
