# Scoring a Report against Ground truth

Type: grilling
Status: resolved
Blocked by: none

## Question

Graduated from the map's fog once the timing prototype rehearsed it for real and the
scorer it wrote got things wrong.

Every Fault has a documented Ground truth and a Report is judged by whether its Suggested
root cause names it — that is a standing rule. This ticket settles **how that judgment is
actually made during rehearsal**: what a mechanical pre-check may decide, what a human
must read, and how the verdict is recorded so a rehearsal week produces a trend rather
than five opinions.

There is prior art to argue from, not a blank page: `prototype/run-timing/score.py` on
branch `prototype/run-timing`, run against five arms with
`prototype/run-timing/fixtures/ground-truth.md`. One rehearsal produced three distinct
failure classes, and a script caught only the first:

1. **Keyword presence, which a script does well.** Did the Report name the flag, cite the
   trace ids, state a confidence? Cheap, mechanical, reliable.
2. **Mention versus attribution, which the script got wrong.** It graded an arm as having
   swallowed the red-herring deploy because the words "payment v1" appeared — when the
   Report had ruled that deploy out explicitly, in words, which is the correct behaviour.
   A regex cannot tell endorsement from dismissal.
3. **Fabricated evidence, which the script missed entirely and which matters most.** The
   Haiku arm's Report claimed "Checked healthy: payment service, ad service" after making
   four Eyes calls, none of them against either service. It passed every keyword check.
   Catching this needs the Report cross-checked against *what the Run actually retrieved* —
   the Transcript's tool calls — not against the Ground truth alone.

So the decisions are: does the citation rule get enforced by machine, by comparing each
Evidence bullet against the Run's own tool calls? Does a Report that names the right cause
with a fabricated control pass, fail, or get its own grade? Who reads what, and when? And
is the record a file per rehearsal, a table, or something the demo itself can show?

A fourth, smaller class is worth deciding too: the best-graded arm wrote "54 minutes" for a
52-minute interval. Arithmetic on screen will be read closely, and no keyword check sees it.

## Related, added 2026-09-16

[The Change: making a Fault's cause citable](25-the-change-making-a-faults-cause-citable.md)
asks whether a Run can retrieve a Fault's cause at all —
[Can the laptop hold it](08-can-the-laptop-hold-it.md) measured that today it
cannot, for flag-injected Faults. Not a blocking edge: the scoring method can be
decided in shape either way. But the two answers have to agree on how much a
Report must *cite* versus *infer* before either is final, so whichever is taken
second should read the first.

## What ticket 10 settled, 2026-09-17

**ADR 0008 changes what this ticket scores.** A Ground truth is now two layers — the
**Mechanism**, what breaks in system terms, and the **Trigger**, the flag and variant —
and a Suggested root cause is judged **against the Mechanism alone**. Naming the flag is
not a diagnosis.

Two consequences this ticket inherits:

- **Scoring is no longer a string match.** The three Mechanisms are written as prose
  paragraphs in [Faults and their Cascades](10-faults-and-their-cascades.md), deliberately
  naming no flag. Judging a Report against one takes a judgment, which is this ticket's
  problem now.
- **Memory is untrusted.** The Ground truth lives only in this repository — never in the
  cluster, Grafana, an OPS Incident, the Confluence space, or the Memory directory. The
  live leak risk is a Run writing a Ground truth into Memory for a later Run to read,
  which would contaminate every later score with no visible symptom.

Sample size: three Faults are written in full and nine are named without Ground truths.
If scoring wants more samples, it graduates its own ticket to write them.

## Work in progress

Claimed after ticket 22 was committed as d9b3e6f. Ticket 23 remains unexecuted because paid measurements are not authorized. Offline scoring-evidence review and human policy decisions only; no model or demo run.

[Offline facts](../reviews/ticket-24/facts.md) verify the source's earlier mention/attribution error was already corrected into a pre-check, and distinguish historical audit findings from a fresh response-level citation audit: raw Transcripts are not committed. The old flag-name pass mark is superseded by ADR 0008. [Round 1](../reviews/ticket-24/round-1.md) records accepted adjudicator, rubric, audit evidence, record granularity and arithmetic policy. The human accepted all five recommendations. [Round 2](../reviews/ticket-24/round-2.md) records the accepted review, rollup, retention and qualification details. All five second-round recommendations were accepted.

## Answer

Both rounds are accepted in [ADR 0014](../../../docs/adr/0014-report-scoring-requires-supported-claims-and-human-review.md). Deterministic prechecks support named human adjudication; Mechanism correctness and evidence support are separate, and missing audit evidence is unverifiable rather than proof of fabrication. A supported inference may pass, while a lucky cause with invented controls cannot. Per-Report revision records roll into a lifecycle verdict without hiding earlier failures or arithmetic defects behind a corrected final Report.

Private operator audit evidence stays outside Runs, Memory, shared telemetry and Git, bounded to 100 MiB per Run, 2 GiB total and 30 days. Capture failure cannot block required OPS work, but prevents an auditable qualifying pass where evidence is missing. Human disputes require a second review; records preserve both rationales and rubric history. Three qualification samples cover two primary and one fallback lifecycle, including cold-start and Memory-assisted conditions, within existing budgets and only after the relevant reviewed Ground truths exist.

[Ticket 39](39-report-audit-and-scoring-specification.md) owns capture/schema/checker and offline acceptance specification. No scorer or Skill implementation, live audit or model qualification is claimed. The historical regex precheck and flag-name grades remain historical evidence.

[Ticket 40](40-fallback-fault-ground-truth.md) supplies the missing reviewed fallback Mechanism/Trigger definition before qualification. Ticket 29 already measured adFailure at the intended venue; that historical measurement does not substitute for a Ground-truth definition or model qualification.
