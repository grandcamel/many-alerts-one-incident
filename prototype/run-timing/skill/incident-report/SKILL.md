---
name: incident-report
description: Turn one Grafana Notification carrying a Cascade into one Jira OPS Incident with a cited Report.
---

# Many Alerts, one Incident

PROTOTYPE DRAFT. Chapter two's skill, written far enough to time a Run against.

Read `notification.json` in your working directory. It carries several Alerts. They are
almost certainly **one Fault seen from several angles** — that is the point of this work.
Your job is to find the Fault, file **one** Incident for it, and write a Report whose
Suggested root cause is **cited to evidence you retrieved**.

An uncited root cause is the failure this demo exists to disprove. Never state a cause
you have not shown.

## Your tools

`eyes` reads the telemetry. `jira-as` writes to Jira. `Read` reads files. Nothing else —
no `curl`, no `date`, no writing files. Every invocation below is one you can run as
written.

**Write each invocation on a single line, in plain single quotes.** The permission
boundary denies a command split across lines with `\`, one carrying a newline inside an
argument, or one using `$'...'`. Nothing you need has a newline in it.

You have no clock. Every time you state comes from the data or from Jira's `serverTime`.

## Step 1 — read the Cascade

Read `notification.json`. For every Alert note its `alertname`, `service`, `severity`,
`startsAt`, `fingerprint` and `values.A`. Order them by `startsAt`: the earliest Alerts
are nearest the Fault, the later ones are usually downstream of it.

## Step 2 — investigate with Eyes

Run `eyes` (no arguments) once to see what it offers. Then look at **all four signals**
before you conclude anything. At minimum:

```bash
eyes changes list --since 2026-09-15T12:00:00Z
eyes metrics query recommendation --since 2026-09-15T13:55:00Z
eyes logs query --service <service> --since 2026-09-15T13:55:00Z --limit 40
eyes traces list --min-duration-ms 500
eyes traces get <traceId>
```

Three habits decide whether the Report is right:

- **Compare before and after.** A trace, a series or a log line from before the first
  Alert is what turns a number into a change.
- **Check the quiet services too.** A service whose metrics are flat is evidence — it
  bounds the blast radius and rules out shared causes.
- **Distrust the loudest Alert.** Whole-host or edge-level Alerts are usually
  consequences. So is a change that landed long before the symptoms started; check the
  timing of every Change against the first Alert before you blame it.

Stop investigating when you can name a cause and point at the evidence for it. You are
on a clock the audience can see.

## Step 3 — judge the Match

An Incident stands for one Fault's whole lifetime and carries the Fingerprint label of
every Alert it explains. Look for one that already covers this Fault:

```bash
jira-as search jql 'project = OPS AND issuetype = Incident AND statusCategory != Done'
```

The Match is a **judgment**, not a lookup: an open Incident is the Match when its Fault
is the one you just found, whether or not these Fingerprints are on it yet.

| Match | What you do |
| --- | --- |
| none | [Create](#step-4a--create-the-incident) one Incident for the whole Cascade |
| one | [Update](#step-4b--update-the-incident) it: add the new Fingerprints, append to the Report |

Never open a second Incident for a Fault that already has one.

## Step 4a — create the Incident

- **Summary** — the Fault in a responder's words, not an alertname. Name the service you
  believe is the cause.
- **Severity** `customfield_10085` — the highest severity among the Alerts: `critical` →
  `Sev-1`, `warning` → `Sev-2`, else `Sev-3`. Never `Sev-0`.
- **Urgency** `customfield_10079` — follows Severity: `Critical`, `High`, `Medium`.
- **Source** `customfield_10096` — always `Monitoring systems`.
- **Labels** — `fp-<fingerprint>` for **every** Alert in the Notification, comma-separated.
- **Description** — the Report, as ADF. See [the Report](#the-report).

```bash
jira-as issue create -p OPS -t Incident -s '<summary>' --labels 'fp-<one>,fp-<two>' --custom-fields '{"customfield_10085": {"value": "Sev-1"}, "customfield_10079": {"value": "Critical"}, "customfield_10096": {"value": "Monitoring systems"}, "description": <adf>}'
```

Then record what it opened with, so a later Run can tell what changed:

```bash
jira-as collaborate comment add <key> -b 'Opened from a Cascade of <n> Alerts. Suggested cause: <one line>. Confidence: <level>.'
```

## Step 4b — update the Incident

Add the Fingerprints that are not on it yet, then append what this Cascade added:

```bash
jira-as issue update <key> --labels 'fp-<new>'
jira-as collaborate comment add <key> -b '<n> further Alerts, <names>. What this adds: <one line>. Confidence now: <level>.'
```

A later Run **appends**; it does not rewrite an earlier Run's Report.

## The Report

Seven sections, in this order, as the Incident's Description. It is one line of ADF JSON,
because a command may not contain a newline.

1. **Summary** — two sentences: what is broken and what you believe caused it.
2. **Blast radius** — the services affected, and the services checked and found healthy.
3. **Timeline** — the Change or first symptom, then each Alert at its `startsAt`.
4. **Evidence** — one bullet per piece, each naming where it came from: a trace id, an
   `eyes logs query` you ran, a metric name and window, a Change id.
5. **Suggested root cause** — the cause, then **Confidence: high | medium | low**, then
   why that confidence. Every claim here points back at a bullet in Evidence.
6. **Suggested remediation** — what a human might do. You never do it yourself; this
   Run never touches the system.
7. **Fingerprints explained** — one line per Alert: its name, and whether this cause
   explains it directly, as a downstream effect, or not at all.

Build it from these node types, all on one line:

```json
{"type":"doc","version":1,"content":[{"type":"heading","attrs":{"level":3},"content":[{"type":"text","text":"Summary"}]},{"type":"paragraph","content":[{"type":"text","text":"..."}]},{"type":"bulletList","content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"..."}]}]}]}]}
```

Confidence is a claim about evidence, not a feeling: **high** means you found the cause
in the data and a before-and-after comparison confirms it; **medium** means the evidence
is consistent with the cause but you could not rule out an alternative; **low** means you
are naming the most likely of several.

## Finish

End with these lines and nothing after them:

- One line naming the Incident key and whether you created or updated it.
- One line naming the Suggested root cause and the confidence.
- One line per Alert: its `alertname` and `explained`, `downstream`, or `unexplained`.
