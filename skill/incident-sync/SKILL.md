---
name: incident-sync
description: Turn one Grafana Notification into Incident activity in the Jira {{PROJECT_KEY}} project.
---

# One Notification, one Incident lifecycle

Read `notification.json` in your working directory. Handle **every Alert in it
independently**: an Alert is `firing` or `resolved`, and its `fingerprint` is its
identity across every Notification it ever appears in.

You can run `jira-as` and read files. Nothing else — no writing files, no `curl`,
no `date`, no other command. Every invocation below is one you can run as written.

**Write each `jira-as` invocation on a single line, in plain single quotes.** The
permission boundary denies a whole command that is split across lines with `\`,
that carries a newline inside an argument, or that uses `$'...'` — it will not
match the allow list however harmless it looks. Nothing you need has a newline in
it: the one field that wants paragraphs is the Description, and it gets them from
the ADF form below instead.

## The project

| Fact | Value |
| --- | --- |
| Project | `{{PROJECT_KEY}}` |
| Issue type | `Incident` |
| Fingerprint label | `fp-<fingerprint>` — nothing else identifies an Incident |
| Severity field | {{SEVERITY_FIELD}} |
| Urgency field | {{URGENCY_FIELD}} |
| Source field | {{SOURCE_FIELD}} |

Never set `Sev-0`. Never touch {{MAJOR_INCIDENT}}. Never use the
statuses `Pending`, `Closed` or `Canceled` — a human owns those.

## Step 1 — find the Match

The Match is the one open Incident carrying this Alert's Fingerprint label:

```bash
jira-as search jql 'project = {{PROJECT_KEY}} AND issuetype = Incident AND labels = "fp-<fingerprint>" AND statusCategory != Done'
```

`Found 0 issue(s)` means there is no Match. Otherwise the table's `Key` column is
the Match and its `Status` is what the next step branches on. A Completed Incident
is deliberately not a Match: a re-fire gets its own Incident.

Then act on what you found:

| Alert | Match | What you do |
| --- | --- | --- |
| `firing` | none | [Create](#step-2a--create-the-incident) it |
| `firing` | `Open` | [Comment](#step-2b--comment-the-trend) the trend, then move it to `Work in progress` |
| `firing` | `Work in progress` | [Comment](#step-2b--comment-the-trend) the trend and nothing else |
| `resolved` | any | [Close](#step-2c--close-the-incident) it |
| `resolved` | none | Do nothing. Say you skipped it and why |

## Step 2a — create the Incident

Map the Alert onto the fields:

- **Summary** — the `alertname` label, then ` on `, then the `instance` label.
- **Description** — the `summary` annotation, then the `description` annotation,
  then the Alert's `generatorURL`, `dashboardURL` and `panelURL`, one per line.
  Written as ADF, because that is the only way to get separate lines out of a
  command that cannot contain one. See [the template](#the-description) below.
- **Severity** — `critical` → `Sev-1`, `warning` → `Sev-2`, anything else → `Sev-3`,
  read from the `severity` label.
- **Urgency** — follows Severity: `Sev-1` → `Critical`, `Sev-2` → `High`,
  `Sev-3` → `Medium`.
- **Component** — the `service` label, but only if a component of that exact name
  already exists on {{PROJECT_KEY}}. Check with
  `jira-as -o json api call getProjectComponents --projectIdOrKey {{PROJECT_KEY}}`. If it is
  not there, leave the component off entirely. An unknown service must not fail
  the create.
- **Label** — `fp-<fingerprint>`, and no other label.

```bash
jira-as issue create -p {{PROJECT_KEY}} -t Incident -s '<summary>' --labels 'fp-<fingerprint>' --custom-fields '{{CUSTOM_FIELDS}}'
```

That sets exactly the fields [the project](#the-project) gives an id for. A field
it says this project lacks stays off: never look for its id, never guess one.

Add `--components '<service>'` only when that component exists. The Incident is
created in `Open`; do not transition it on the first Firing.

Then record the value it opened at, so the next Firing has something to compare
against and the closing comment can count the Firings:

```bash
jira-as collaborate comment add <key> -b 'Opened from a firing Alert. value=<current>.'
```

`<current>` is the Alert's `values.A`.

### The description

The Description goes in under `--custom-fields` with the other fields, as one
line of ADF JSON — `issue create` has no `--description` that understands
paragraphs, and a command may not contain a newline. Fill in the five
placeholders, change nothing else, and paste it in place of `<description>`
above, unquoted, as a JSON value among the others:

```json
{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"<summary annotation>"}]},{"type":"paragraph","content":[{"type":"text","text":"<description annotation>"}]},{"type":"bulletList","content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"Generator: <generatorURL>"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"Dashboard: <dashboardURL>"}]}]},{"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"Panel: <panelURL>"}]}]}]}]}
```

## Step 2b — comment the trend

Read what the last Run said, so this comment can report a change:

```bash
jira-as collaborate comment list <key>
```

The previous value is the most recent `value=` in that list that is **not** a
`previous value=` — every trend comment carries both, and reading the wrong one
freezes the trend at whatever it said last time. Then post one comment and no
more than one, in exactly this shape, so the next Run can read it too:

```bash
jira-as collaborate comment add <key> -b 'Still firing. value=<current> (previous value=<previous>, <up|down|unchanged>). Open for <duration>.'
```

`<duration>` is how long the Incident has been open: the Jira clock now, minus
the Incident's own `created`. Read both off Jira, never off the Alert — Grafana's
clock and Jira's are not the same clock, and a Notification replayed from a
fixture can carry a `startsAt` that has not happened yet:

```bash
jira-as -o json api call getServerInfo
jira-as issue get <key> -o json
```

`serverTime` from the first, `created` from the second. Write the difference like
`4m30s`. That is the only clock you can reach, so use it for every duration.

If the Match is in `Open`, move it on after commenting — see
[transitions](#moving-an-incident). If it is already in `Work in progress`, stop
here: a repeat is idempotent apart from its comment.

## Step 2c — close the Incident

Count the Firings: one per comment on the Incident, the opening one included —
comments, not occurrences of `value=`, because a trend comment carries two. The
duration is the Jira clock now minus the Incident's `created`, read the same way
as in [step 2b](#step-2b--comment-the-trend).

```bash
jira-as collaborate comment add <key> -b 'Resolved after <duration>, <n> Firings. value=<current>. Completed automatically from the Grafana Alert.'
```

Then move it to `Completed` **with a resolution**:

```bash
jira-as lifecycle transition <key> --id <id> --resolution Done
```

Without the resolution the Incident stays in the Incidents queue forever, because
that queue is `resolution = Unresolved`. This is the one place a resolution is set.

## Moving an Incident

Transition names are not status names on this workflow: `Investigate` leads to
`Work in progress` and `Resolve` leads to `Completed`. So never pass `--to`. Read
the transitions off the issue itself and use the id of the one whose `to.name` is
the status you want:

```bash
jira-as lifecycle transitions <key> -o json
jira-as lifecycle transition <key> --id <id>
```

Read them every time. An id that was right last week is not a fact about this issue.

## Finish

End with one line per Alert, naming the Fingerprint, the Incident key and what
changed — `created`, `commented`, `commented and moved to Work in progress`,
`completed`, or `skipped` and why. Nothing else after those lines.
