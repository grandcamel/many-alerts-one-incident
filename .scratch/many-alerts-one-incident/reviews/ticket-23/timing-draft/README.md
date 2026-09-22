# Timing diagnostic source drafts

Status: **REVIEWABLE SOURCE / NOT DEPLOYED / NATIVE EXECUTION CLOSED**.
Draft version: `ticket23-timing-text-v1`. Baseline: local commit `9ab04ab`.

These texts replace the historical answer-leading prompt and flag-name scoring for a
future single synthetic timing attempt. They contain no launch command, tool signatures,
permission allowlist, auth configuration or approved model binding. They are not installed
as an active Skill. Ticket 23 remains open and the measurement card remains closed.

The source work in this batch is:

1. Draft a short system/task prompt and diagnostic Skill with checkable completion rules,
   explicit evidence gaps and preserved Report revisions.
2. Separate Run-visible text from operator-only rubric, adjudication and assembly controls.
   Keep historical commands, Ground truth and legacy scores outside the Run bundle.
3. Pin historical inputs by read-back/hash without executing their generator or stubs.
   Map unresolved native binding and human-review fields explicitly rather than invent them.
4. Review both instruction quality and spec fidelity; verify JSON, pointers, file allowlists
   and pinned digests. Keep runtime/model-quality/human grading acceptance NOT RUN.

## Proposed delivery map

| Material | Future access | Current readiness |
| --- | --- | --- |
| `run/system-prompt.md`, `run/task-prompt.md`, `run/incident-report/SKILL.md` | Run instruction inputs only | Source drafts, exact digests in draft-manifest.json |
| Pinned `notification-cascade.json` as `notification.json` | Read-only Run input | Historical source digest verified, no mount prepared |
| Binding manifest | Run-visible capability syntax, fixture identities, response correlation and stop interface | UNSET; reviewed implementation required |
| Pinned canned telemetry | Supervisor-owned inert query adapter; exact returned responses recorded | Pinned in-process read-only query API implemented/tested; native isolated adapter remains unimplemented |
| Synthetic Incident store and mutation receipts | Supervisor-owned; capabilities only, no live route | UNSET; fresh empty baseline and mutation semantics must be proven |
| Operator directory, draft manifest, this README, historical Ground truth and scoring material | Operator/reviewer only, outside Run mounts and Memory | Planning artifacts; no access boundary implemented |

The delivery map is an allowlist proposal, not a mount or security proof. A future launcher
must assemble files individually; mounting this parent directory would expose operator
material. No directory glob or historical runner is an approved assembler. Draft manifests
hold provenance and status only; reading one cannot grant execution authority.

## Remaining freeze gates

[Operator preflight](operator/preflight.md) lists the exact unresolved bindings and
human-review inputs. Prompt/Skill digests identify this draft, not a frozen executable
comparison set. The operator must approve the final Mechanism baseline, rubric and full
input/executable manifest before a separately authorized attempt. Changing these inputs
starts a new diagnostic series unless retained evidence is explicitly re-adjudicated.

The [rubric](operator/rubric.md) is for named human adjudication, not an automated judge.
The [template](operator/adjudication-template.json) is an unfilled compact example, not
implemented validation or an accepted review record. Ticket 39 retains ownership of the
complete audit/scoring specification and ticket 38 of qualification/accounting integration.
