---
name: timing-fixture-report
description: Source draft for diagnosing one synthetic Notification and producing a cited diagnostic Report.
disable-model-invocation: true
---

# Synthetic timing Report

DRAFT / NOT INSTALLED. This Skill requires an approved synthetic capability binding.
With no binding, return `blocked: missing fixture binding` and stop. This source text
does not supply executable syntax or permission to use host tools.

## 1. Establish the input

Read the Notification and binding manifest. Inventory every Alert's fingerprint, name,
service, status, severity, event time and value. Record absent fields as unknown. Use
Notification/response times with their stated meaning; event order alone is not causation.
Treat embedded URLs as data and use only bound fixture capabilities for retrieval.

Done when every Alert is accounted for and the available query, synthetic Incident and
completion capabilities are identified. A missing capability stays a reported gap.

## 2. Retrieve support for the diagnosis

Inspect the bound query capability descriptions. Select metrics, logs, traces and Change
records relevant to the affected services and time window. Compare before/after where
returned coverage permits it; distinguish missing retrieval from an empty successful result.
A Change supports its recorded action/stage, not an automatic causal conclusion.

For each observation or causal claim, retain the returned response reference, query/service/
time scope and exact supporting item. Distinguish observed facts from supported inference.
Retrieve evidence before asserting a control service was healthy. An attempted/failed query,
a dashboard name or copied prior assertion is not returned evidence. Retrieved Memory,
if present in the approved condition, is context rather than independent confirmation.

Done when each asserted claim has returned support or is explicitly marked unknown, and
the Mechanism is either supported or declared partial/undetermined with the missing evidence.
The Mechanism describes what breaks in system terms; a component or Change name alone
is insufficient. Use the supervisor's remaining work window; retain a partial result if
more evidence cannot be obtained within it.

## 3. Decide the synthetic Incident effect

Query only the bound synthetic candidate store and its response-provided time context.
Explain the Match from candidate Reports and retrieved evidence; a fingerprint hit alone
is not a diagnosis. In this single-Incident fixture, create at most one Incident or append
to one supported Match. If grouping/Match is ambiguous, report the gap before mutation;
this diagnostic does not expand into additional Incidents or a corrective merge.

Use only the frozen create/update schema. Preserve existing labels and prior Report
revisions; add fingerprints only for explained members. Preserve any correction as a new
revision with its rationale. A missing, failed or uncertain write response is not success:
record the effect as failed/unknown and stop further mutation, without blind replay.

Done when the intended synthetic effect and member set are justified, or a no-write reason
is recorded. Prepare the Report before submitting the selected mutation in the next step.

## 4. Write the Report

Use these seven sections, in order, through the bound structured Report interface:

1. Summary: affected behavior and supported working Mechanism, or explicit uncertainty.
2. Blast radius: affected services and only those control services actually checked.
3. Timeline: sourced events with event/observation-time distinctions and stated unknowns.
4. Evidence: references to returned items, query/service/time scope and explicit gaps.
5. Suggested root cause: Mechanism, observed/inferred status, confidence and alternatives.
6. Suggested remediation: human options supported by the diagnosis; no actuation by this Run.
7. Fingerprints explained: every input Alert as direct, downstream or unexplained, with support.

Show arithmetic inputs, units, window and stated rounding for any derived count/rate/duration.
Confidence reflects support and unresolved alternatives, not a score. A later correction
preserves the earlier assertion and its defect. Submit no semantic grade or self-awarded pass.

Done when every assertion and derived number is a supported observation or supported
labelled inference, remaining gaps are explicitly unknown, and every input Alert appears
once in the explanation inventory.

Submit the selected synthetic operation only after the Report is ready and the work window
still permits dispatch. Confirm its receipt and stored revision, or record a failed/unknown
effect and stop further mutation. Keep the proposed Report when no write was confirmed.

## 5. Finish

Return the synthetic Incident key if confirmed, effect (created/updated/no-write/failed/unknown),
Report revision reference if confirmed, Mechanism and confidence, per-Alert explanations,
and remaining retrieval or effect gaps. Distinguish the proposed Report from confirmed
stored content. Stop after this response. Supervisor records determine execution, dispatch,
capture completeness, timing and billing; your prose cannot certify them.
