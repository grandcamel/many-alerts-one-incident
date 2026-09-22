# Operator-only diagnostic rubric draft

Version: `ticket23-timing-rubric-v1-draft`. Status: **PENDING HUMAN FREEZE**.
Keep this document, Ground truth, adjudications and scoring feedback outside Run access,
Memory and shared telemetry. This rubric is a diagnostic application of ADRs 0008/0014;
it does not complete ticket 39 or qualify a model, billing path or venue.

## Establish review identity and evidence

Before grading, name the human reviewer, review time, rubric version, diagnostic series,
Fault/Run/synthetic Incident identities, requested and observed model/effort, auth/venue/
Memory condition and every exact Report revision/digest. Link retained request/returned-
response records and explicit capture gaps. Empty responses, failed queries and missing
records are distinct. A later re-query cannot replace what this Run actually retrieved.

The proposed source Mechanism for the pinned canned scenario is:

> Unbounded cache growth during misses in the recommendation service increases memory,
> garbage-collection and CPU pressure, slowing request handling and propagating latency
> and deadline failures to its callers.

This is an **unapproved synthetic review target**, derived from the pinned historical
fixture description, not a fresh source/image or live-system qualification. A named human
must approve a flag-free Mechanism baseline and its correspondence to the frozen fixture
responses before the rubric is frozen. Record Trigger separately for operator provenance;
Trigger naming earns no Mechanism credit. No grade is assigned by this draft.

The historical `ground-truth.md` is an input to this review, not current scoring authority:
its flag-name pass/near table conflicts with ADR 0008 and must not be reused. Historical
measurement grades remain historical. This new text/rubric starts a new series and cannot
establish a controlled comparison to the earlier 900-second/direct-auth arms.

## Review every Report revision

| Axis | Allowed judgment | Evidence needed |
| --- | --- | --- |
| Mechanism | correct / partial / wrong / undetermined | Human causal reading against the approved Mechanism baseline; naming a flag/service/Change alone is insufficient |
| Evidence | supported / unsupported / unverifiable | Every observational/causal claim mapped to what the Run retrieved, with service/time/query scope and observed/inferred distinction |
| Arithmetic | correct / incorrect / unverifiable / not_applicable | Reproduce displayed calculations using returned inputs, units and window, accepting stated rounding; not_applicable needs a reason |
| Human review | pending / reviewed / disputed | Named dated rationale; disagreement keeps the sample excluded until a second named human review and reconciliation |

Record each claim's Report location, assertion kind, returned-response/item reference,
query/service/time scope, support judgment and rationale. Supported inference may establish
Mechanism correctness without a directly observed Trigger. Memory or earlier assertions
alone cannot independently confirm a claim; legitimate earlier returned evidence needs
its original provenance and scope.

An invented observation/control or unsupported causal assertion is unsupported even if
the proposed Mechanism happens to be right. Missing, truncated, redacted, tampered or expired
evidence is unverifiable when it prevents checking the claim; missingness alone is not
proof of fabrication. Capture loss cannot become supported via a digest or later query.
A Change supports only its recorded stage, not application evaluation, recovery or causation.

Early partial/undetermined Mechanism Reports are allowed, but their asserted claims still
need support. Preserve confidently wrong assertions, arithmetic defects and fabricated
controls as distinct defects. Review every revision; a corrected Report can receive a
better revision grade while its original defect still prevents a clean lifecycle sample.
A reviewer-error correction is a separate dated superseding adjudication, not a Report fix.

## Roll up without hiding defects

A clean diagnostic lifecycle requires the correct supported final Mechanism, supported
claims throughout, no invented control/observation or confidently wrong causal assertion,
correct final arithmetic, complete necessary audit and finished human review of every
revision. Preserve earlier arithmetic/unsupported/fabrication defects; they cannot be erased
by a corrected revision to create a clean qualification sample. Missing final Report,
pending/disputed review or unverifiable necessary evidence prevents a pass. Never average
axis grades to hide failure. Record rationale and prior-review links append-only.

Keep diagnostic judgment separate from execution/effects, actual identity, containment,
300-second timing, audit completeness and spend. A clean diagnostic judgment is not a
model qualification result. Qualification still needs the accepted two-primary/one-fallback
representative lifecycle set with cold/Memory conditions, existing allocation limits and
all auth/billing/Change/venue gates under tickets 38/39. This single canned timing attempt
cannot supply those samples. Failed/replaced samples remain visible and consume allocation.

## Review cases before freezing

Walk through mention-versus-attribution, flag-only answer, supported inference without a
Trigger, an unqueried healthy control, failed query claimed as evidence, wrong service/time
scope, empty versus missing response, prior retrieved evidence versus copied assertion,
truncation/redaction/expiry, wrong units/rounding, corrected Report, reviewer-error correction,
and disputed adjudication. Determine the appropriate axis separately for each; this checklist
does not itself adjudicate any case or constitute a passed behavioral test.

Raw audit remains operator-owned outside Git/Run mounts, sanitized before persistence,
100 MiB/Run and 2 GiB total, at most 30 days. Compact references/digests may remain local;
after expiry label verdicts historical and no longer independently re-auditable. Capture
failure makes affected claims unverifiable and must not block required OPS handling in the
future production system. This diagnostic draft adds no capture implementation or OPS route.
