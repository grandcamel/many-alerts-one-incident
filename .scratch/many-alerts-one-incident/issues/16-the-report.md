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

So the Report cannot simply be "as long as it needs to be". Either it fits in roughly
9,000 characters of ADF, or it arrives in pieces — a short Description on create and the
sections appended as comments, which also suits "what a later Run appends versus
rewrites". Decide which here. For scale: the arms' Reports ran 445 to 899 words, and the
899-word one serialized to 9,337 characters and only just fitted.
