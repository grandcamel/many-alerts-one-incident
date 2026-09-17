# Many Alerts to One Incident

A demo in which the Alerts one Fault raises across a simulated distributed system each trigger a headless Claude run inside a container, and those runs reduce the Alerts to one Incident in the Jira OPS project, with a suggested root cause a responder can check.

## Language

### Simulation side

**Fault**:
One injected failure in the simulated system, with a documented Ground truth.
_Avoid_: scenario, chaos experiment, failure mode, incident, outage

**Ground truth**:
The documented true cause of a Fault, written when the Fault is, in two layers: the **Mechanism**, what actually breaks stated in system terms, and the **Trigger**, the switch that injected it. A Report's Suggested root cause is judged against the Mechanism alone, so naming the Trigger is not a diagnosis.
_Avoid_: root cause, answer key, expected result

**Cascade**:
The set of Alerts one Fault fires.
_Avoid_: alert storm, flood, correlated alerts, alert group

**Event**:
A timestamped, named, structured record that something happened, as distinct from a log line. The only sense the word has here; an Alert and a Notification are not Events. Three kinds: Kubernetes Event, Change and Run event.
_Avoid_: structured event, log event, occurrence

**Kubernetes Event**:
An Event the cluster itself records about a pod, node or rollout, such as OOMKilled, BackOff or FailedScheduling.
_Avoid_: k8s event, cluster event, pod event

**Change**:
An Event recording something someone did to the system: a deploy, a config edit, a feature-flag flip.
_Avoid_: deployment event, annotation, change event, release

### Alerting side

**Alertable condition**:
One distinct thing that is true of the system while a Fault is firing, named against a signal that exists. The unit a Cascade is designed in, before any threshold turns it into an Alert.
_Avoid_: alert rule, condition, symptom, trigger

**Alert**:
One Grafana alert rule instance, identified by its Fingerprint. It is either Firing or Resolved.
_Avoid_: alarm, event, rule

**Fingerprint**:
Grafana's stable hash of an Alert's label set. The identity of an Alert across every Notification.
_Avoid_: alert id, hash, key

**Notification**:
One webhook POST from Grafana, carrying one or more Alerts.
_Avoid_: webhook, payload, message, event

**Firing**:
The Alert state meaning the condition currently holds. A Notification may report the same Firing Alert repeatedly.
_Avoid_: active, triggered, alerting

**Resolved**:
The Alert state meaning the condition no longer holds.
_Avoid_: cleared, ok, recovered

### Sync side

**Receiver**:
The HTTP endpoint inside the container that accepts Notifications and starts Runs, one at a time.
_Avoid_: harness, server, listener, webhook handler

**Run**:
One headless Claude invocation, started by the Receiver for exactly one Notification.
_Avoid_: harness, agent, session, job

**Skill**:
The one file in this repo, copied into the image, that tells a Run the OPS facts and how to
act on an Alert. A Run reads it and nothing else instructs it.
_Avoid_: prompt, playbook, instructions, runbook

**Forwarder**:
The localhost process, owned by the Receiver, that holds the real Jira credential and forwards a Run's Jira requests with that credential attached. A Run only ever holds a sentinel.
_Avoid_: proxy, sidecar, hand, vault

**Sentinel**:
The random token generated for one Run and registered with the Forwarder for that Run's lifetime. It stands where the Jira API token would be in a Run's environment, and is worth nothing anywhere else or once the Run has ended.
_Avoid_: fake token, dummy credential, placeholder, api key

**Transcript**:
The stream-json output of one Run, one Run event per line. The Receiver renders it into the container log as it arrives, and a recorded Transcript is committed as a fixture.
_Avoid_: log, output, stream, session log

**Run event**:
One line of a Transcript: one thing the Run did — assistant text, a tool call, a tool result, a denial, or the final result. Never shortened to "event" on its own: an Event is the wider term, and an Alert and a Notification are not Events.
_Avoid_: event, message, chunk

**Eyes**:
The read-only tools a Run may execute to look at telemetry: queries against logs, metrics, traces and Events, and whatever read-only view of the cluster the map grants.
_Avoid_: query tools, observability tools, read tools, sensors

**Hands**:
The tools a Run may execute that change something outside itself: the Jira and Confluence operations. Never the cluster or the system; a Run reports and does not remediate.
_Avoid_: write tools, actions, actuators, effectors

**Memory**:
What a Run can consult that an earlier Run left behind: the Incidents in OPS, the pages in the Confluence space, and the Memory directory.
_Avoid_: state, history, cache, context, knowledge base

**Memory directory**:
The one directory that persists across Runs, where a Run writes what it learned about the system for the next Run to read.
_Avoid_: notes, scratch, memory file, cache

### Jira side

**Incident**:
An OPS issue of type Incident that represents one Fault's lifetime as the Run understands it, carrying the Fingerprint of every Alert it explains.
_Avoid_: ticket, issue, case, request

**Match**:
The open Incident a Run judges an Alert to belong to. A judgment, not a label lookup; an Alert has at most one Match.
_Avoid_: duplicate, existing incident, correlation

**Report**:
The body a Run writes into an Incident: what happened, to what, in what order, on what evidence, with a Suggested root cause and a suggested remediation.
_Avoid_: description, summary, postmortem, RCA, write-up

**Suggested root cause**:
The cause a Report names, with the evidence it cites and the confidence it states. The Run's claim, never shortened to "root cause", which would blur it with the Ground truth.
_Avoid_: root cause, diagnosis, finding, conclusion

**Problem**:
An OPS issue of type Problem that groups Incidents that recur. Reserved; not built in this effort.
_Avoid_: parent, root cause ticket
