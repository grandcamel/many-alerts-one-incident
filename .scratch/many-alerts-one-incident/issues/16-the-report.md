# The Report

Type: grilling
Status: open
Blocked by: 12, 14

## Question

The sections were settled while charting: summary; blast radius, the services and Alerts involved; timeline; evidence; Suggested root cause with a stated confidence; suggested remediation; the Fingerprints explained. This ticket settles what an evidence citation is for each signal (a trace id, a Loki query and time range, a dashboard link, a Kubernetes Event), how confidence is worded, the Jira ADF shape given chapter one's one-line lesson, and what a later Run appends versus rewrites. The citation rule holds: an uncited cause is the failure mode this demo exists to disprove.

## Constraint measured on 2026-09-15

The timing prototype ("Does a high-effort Run fit the slot") found a hard ceiling this
ticket has to design around: under `dontAsk` with `Bash(jira-as *)` allowed, a
`jira-as issue create` carrying the Report as one line of ADF is **denied on length
alone**. Largest accepted 9,417 characters, smallest denied 11,313, across nine creates
in four arms; it is not content — a denied command with every shell metacharacter removed
was denied again at the same length.

So the Report cannot simply be "as long as it needs to be". Either it fits under the
ceiling, or it arrives in pieces — a short Description on create and the sections appended
as comments, which also suits "what a later Run appends versus rewrites". Decide which here.

The budget is tighter than the ceiling suggests, because ADF markup is most of the command.
Measured on the three accepted creates:

| Report | Command | ADF JSON | Actual prose | Markup |
| ---: | ---: | ---: | ---: | ---: |
| 445 words | 7,444 | 7,073 | 3,876 | 45% |
| 731 words | 9,411 | 8,950 | 5,393 | 40% |
| 899 words | 9,331 | 8,852 | 6,183 | 30% |

So a single create carries roughly **5,400 to 6,200 characters of Report prose** — about
800 to 900 words — and the 899-word one only just fitted. Markup overhead falls as
paragraphs get longer, so the shape of the ADF is itself part of the budget: many short
bullets cost far more per word than a few long paragraphs.

This also collides with a second limit. Both arms that stalled in the timing prototype blew
the 64,000-token per-message output cap while serializing their ADF, and neither the cap nor
this ceiling is negotiable at Run time. Report size is the one lever over both.

## Accepted scoring input from ticket 24

ADR 0014 requires claim-to-retrieval linkage and clear observed/inferred language, explicit uncertainty and auditable revisions. A supported inference can score correctly without a retrieved Trigger. Preserve corrections and earlier defects; a citation link or tool name alone does not prove returned evidence supported the claim.
