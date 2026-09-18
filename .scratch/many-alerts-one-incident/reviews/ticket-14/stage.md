# Ticket 14 — stage-lens verification

Scope is the six stage objections only. D1–D6 remain agreed planning inputs. No
counterfactual scheduler, demo, live system, or Run was executed. The D1 result below is
the bounded captured-POST filter, not an assertion about a changed Grafana policy.

1. **Lifecycle/timeout — PARTLY HOLDS.** `RUN_TIMEOUT` is 300 s and kills the process
group with SIGKILL (`grafana_jsm_sandbox/run_spawner.py:36-38,202-217`); the sole high-
effort measurement took 370.3 s against canned telemetry and stubbed Hands
(`.scratch/many-alerts-one-incident/issues/11-does-a-high-effort-run-fit-the-slot.md:20-29`).
The matched-Run speed D3(d) depends on is unmeasured (same file:108-114), so schedule
fitness is conditional, not established. The claimed 29-minute/four-Run schedule depends
on a synthetic 0.03/s dispatch simulation and cannot prove stage behavior. Timeout policy
belongs to ticket 21 (`.scratch/many-alerts-one-incident/issues/21-when-a-run-is-refused-or-never-runs.md:33-36`);
Report-create ordering/form belongs to ticket 16 (`.scratch/many-alerts-one-incident/issues/16-the-report.md:13-22`).
**Correction:** measure a matched append path and hand timeout handling to ticket 21; do
not specify first-write ordering here.

2. **D1 is fully subsumed/stale — PARTLY HOLDS; Run/time savings UNVERIFIED.** The captured trace uses the old threshold, so extrapolation to the planned 0.03/s threshold is not justified. The selected delivery filter returns different historical selections: payment is 26/10/8 and email 63/16/12 at 60/300/600 seconds
(`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/results.txt:1-8`). It does not establish future Run count once
D3(b/c) exists, so “buys zero seconds” is unproven. Nor is 0.03/s committed: the current
C1 threshold remains 0.1 (`git show rules/cascade:rules/cascade/alerting/cascade-rules.yaml:113-119`),
while 0.03 is ticket 29’s recommended blocking edit
(`.scratch/many-alerts-one-incident/issues/29-measure-the-cascade-against-real-rules.md:301-307`).
The D1 rationale about trend comments does need correction because the two 300→600
payment removals are repeat lines (`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/replay/report.md:41-45`), but that does
not justify dropping D1. **Correction:** retain 10m as agreed; replace its count/rationale
with the pinned filter boundary and define D3(b) equality/value treatment.

3. **D6 escape closes 237 s early — PARTLY HOLDS.** The capture fact is sound: payment
line 21 is C2 all-resolved at +662.603 seconds from the first POST while C1 is firing on lines 20 and 22 and resolves
only on line 26 at +900.084 seconds from the first POST (`prototype/cascade-timing/capture/notifications-paymentUnreachable.jsonl:20-22,26`).
The claimed premature completion requires those C1/C2 members to have been accepted into
one Incident and the future merged-input implementation to invoke the escape; D4 makes
the cascade result only a candidate subject to judgment
(`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:109-111`).
It is therefore a real safety gap, not inevitable tape behavior. **Proposed correction for human round 2:** the
escape must not automatically override any known-Firing accepted member, and D3(c) must retain source
group identity. Do not silently remove the human-agreed exception.

4. **D4 multiple candidates and stale exact fingerprint — HOLDS as a decision gap.**
D4 defines only exactly-one candidate (`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:109-111`).
C4 is generic/critical (`git show rules/cascade:rules/cascade/alerting/cascade-rules.yaml:315-345,371-373`), and cart’s
capture contains its critical load-generator Alert (source
`prototype/cascade-timing/capture/notifications-cartFailure.jsonl:6`). If a correct judge
rejects it into another Incident, later `n>1` behavior is unspecified. It does not
automatically make every future Alert a new Incident: exact step 1 can still match. Also,
Fingerprint reuse is measured, but misfiling requires the old Incident still be open
(`.scratch/many-alerts-one-incident/issues/29-measure-the-cascade-against-real-rules.md:195-199`).
**Correction:** specify zero/multiple-candidate and insufficient-evidence outcomes, and
time-bound exact-open admission. Jira label storage remains an implementation delta, not
an impossibility (`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/jira/report.md:15-29`).

5. **D5 contamination ratchet — PARTLY HOLDS.** Cart’s own rule is warning
(`git show rules/cascade:rules/cascade/alerting/cascade-rules.yaml:520-523`) while its
captured load-generator C4 is critical (`prototype/cascade-timing/capture/notifications-cartFailure.jsonl:6`); an incorrectly accepted C4 can
permanently raise D5’s historical maximum (`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:112-113`). D4 judgment means this is
conditional, and the 0.03 live-Fault visual claim is simulation-derived. **Correction:**
only accepted members feed D5; update mapped Urgency with Severity and retain a correction
rule for mistaken admission.

6. **D2 rationale is measured backwards — UNVERIFIED.** C3’s latch and C4’s 10-minute
window are committed (`git show rules/cascade:rules/cascade/alerting/cascade-rules.yaml:234-240,327-345`),
and ticket 29 reports zero C3 flaps (`.scratch/many-alerts-one-incident/issues/29-measure-the-cascade-against-real-rules.md:255-264`).
But the claimed alternate-group scheduler counts are not a committed reproducible artifact;
the D1 delivery filter cannot answer them. D2’s decision itself gives a design rationale,
not 6→39 (`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:101-104`).
**Correction:** retain D2 and record a separately specified scheduler measurement before
asserting either numeric sign.

Completeness check: no additional material clause is missing from
`/Users/jasonkrueger/projects/many-alerts-one-incident/.scratch/many-alerts-one-incident/reviews/ticket-14/completeness.md`; its existing multiple-candidate, stale-exact, wrong-
match correction, source-group identity, and report-mutability items cover the stage
findings.

Boss review: changed objection 2 from FAILS to PARTLY HOLDS. Different historical delivery selections cannot refute a claim about equal future Run counts; the old-threshold caveat is valid. Corrected objection 3 timestamps to the exact first-POST origin used in the independently checked capture analysis. Numerical scheduler and stage claims remain unverified.
