# grafana-jsm-sandbox

**Current status (2026-09-25): the chapter-one live launcher is disabled.**
`python3 -m grafana_jsm_sandbox`, its standalone Forwarder command and the
default Compose entrypoint refuse before loading credentials or starting a
Run. The walkthrough below is historical; do not use it as a current demo
runbook. The [journaled Receiver](docs/recovery-journal.md) supports local
admission-only replay and starts no Run. Guarded launch, accounting and
Forwarder acceptance remain open under tickets 36–38.

**This repository is chapter two, and it opens with chapter one's code.** Everything below
describes `grafana-jsm-sandbox`, a finished demo in which one Grafana alert becomes one Jira
Service Management Incident through a Run that holds no Jira credential. That repository is
[where chapter one lives](https://github.com/grandcamel/grafana-jsm-sandbox); it stays as it
is and nothing in this effort touches it, so this repository is the one that moves from here.
Chapter two asks the harder question it is named for: when one Fault in a simulated distributed
system raises a Cascade of Alerts, how do many Notifications become one Incident whose Suggested
root cause cites the evidence a Run retrieved? It is being charted before it is built, and the
charting is in the open. The map is
[.scratch/many-alerts-one-incident/map.md](.scratch/many-alerts-one-incident/map.md), the
vocabulary is in [CONTEXT.md](CONTEXT.md), the decisions are in [docs/adr](docs/adr), and the
research they rest on is on the `research/*` branches. Nothing in the sections below has
changed yet.

A Grafana alert opens, updates and resolves a Jira Service Management Incident through a
headless Claude Code Run that holds no Jira credential. One `docker compose up` brings up a
Grafana LGTM stack with one alert rule, the small app that rule watches, the synthetic traffic
whose absence fires it, and one hardened container whose main process receives the alert's
Notification and starts a Run for it: Claude Code in print mode, allowed exactly two tools,
following one Skill, reaching Jira through a localhost Forwarder that swaps a per-Run sentinel
for the real token. Stop the traffic and an Incident appears in the queue; start it again and
the Incident is Completed, with the trend commented in between. It was built as a demo of what a
sandboxed boundary looks like when the audience may ask what else the Run can reach, and
[the runbook](docs/demo-runbook.md) is the presenter's script.

## What you need

- **Docker** with Compose v2. The demo is `docker compose up`: the images are pulled from Docker
  Hub or built here, and nothing is installed on the laptop. Compose applies `pids_limit` from
  2.2 and `cpus` from 2.17; an older one silently leaves them off, and the runbook says how to
  tell and what to do meanwhile.
- **A Jira Cloud site with a Jira Service Management project created from the ITSM template.**
  The Skill and the tests call it `OPS` and use its Incident issue type, and an API token for
  an account on that site is what the Forwarder holds. ADR 0004 records the project template key
  that created ours.
- **A Claude Code OAuth token**, from `claude setup-token` on a machine where Claude Code is
  logged in. It is the one credential a Run really holds.
- **`jira-as` in your own shell**, the Jira Assistant CLI 2.x, with the same Jira credential in
  its environment. The image carries its own copy for Runs; yours is for the reset between takes
  and the opt-in end-to-end check.

**The OPS field ids in the Skill are one site's.** Custom field ids differ on every Jira site,
so the Severity, Urgency and Source ids in [`skill/incident-sync/SKILL.md`](skill/incident-sync/SKILL.md),
and the Major incident id it says never to touch, must be re-read from your own project and
edited in before a Run creates anything. From the repo root, with the credential in the shell:

```bash
jira-as -o json api call getFields
```

lists every field on the site; the ITSM template's Severity, Urgency, Source and Major incident
are among them under your own `customfield_` numbers. The Incidents queue id the runbook names
is read the same way, off the address bar. Transition ids need no such step: a Run reads them
off each Incident as it goes.

Domain vocabulary is in [CONTEXT.md](CONTEXT.md); decisions are in [docs/adr](docs/adr);
the spec and tickets are under [.scratch/alert-to-incident-sync](.scratch/alert-to-incident-sync)
and, for the hardened image, [.scratch/hardened-demo-image](.scratch/hardened-demo-image).

## What exists today

The **Receiver** — the HTTP endpoint that accepts Notifications and starts Runs, one at a time.

- `POST /notification` — a Grafana webhook contact point body. A valid Notification is
  acknowledged with `202` and queued; the Run starts afterwards, so Grafana never waits on it.
  A body that is not JSON, has no `alerts` array, or has an Alert without a `fingerprint` and a
  `status`, gets a `400` and starts nothing.
- `GET /health` — `200` while the Receiver is up.

Each Notification becomes one Run with its own working directory under the Receiver's runs
directory, containing the Notification exactly as Grafana sent it as `notification.json`. Runs
execute one at a time in arrival order, so two Firings of the same Alert cannot race into
duplicate Incidents. The Receiver logs each Run's start, end, exit status and duration; a Run that
blows up is logged and the next one still starts.

The process that actually spawns a Run is injected into the `Receiver` at construction, so it
stays a seam a test can substitute; the real spawner is `RunSpawner`, below.

The **log formatter** — what turns a Run's Transcript into the log window the audience watches.

`format_event` is a pure function: one Run event in, zero or more display lines out. It renders
the Run's own text, every tool call with its command in full, tool results trimmed to a few lines,
and permission denials on a `[DENIED]` line — the audience-visible proof that a Run cannot do
anything except talk to Jira (ADR 0003). An event it does not understand costs one diagnostic
line, never a crash. Every line is redacted on the way out, so no Authorization header and nothing
token-shaped can reach a screen.

Render a saved Transcript to see what the log window will look like:

```bash
python3 -m grafana_jsm_sandbox.log_formatter fixtures/run-transcript.jsonl
```

```
[run]    model=claude-fable-5-1 permission-mode=dontAsk tools=Bash,Read
[claude] I'll run the two bash commands in order and report which worked.
[tool]   Bash: seq 1 40
[out]    1
[out]    2
[out]    3
[out]    4
[out]    5
[out]    + 35 more lines
[tool]   Bash: ls /etc
[DENIED] Bash: Permission to use Bash has been denied because Claude Code is running in don't ask mode.
[claude] The first command (`seq 1 40`) worked and printed 1 through 40; the second (`ls /etc`) was denied by the permission mode and did not run.
[DENIED] Bash: ls /etc
[result] success in 10.0s, 3 turns, $0.4527
```

The Receiver pipes every live Run through it, one line at a time, as the Run produces it.

The **skill** a Run follows, and the command line that starts one.

[`skill/incident-sync/SKILL.md`](skill/incident-sync/SKILL.md) is the whole of what a Run knows
about OPS: the Fingerprint label format, the match JQL, the field mapping, the lifecycle rule, and
every operation written as a `jira-as` invocation, because nothing else will execute. It is short
on purpose — it is meant to be read off a screen during the demo.

`build_run_command` is the command line that starts one Run: print mode, `dontAsk`, an allow list
of `Bash(jira-as *)` and `Read`, stream-json with `--verbose`, and the skill directory added so the
Run can read it (ADR 0003). Print it to start a Run by hand:

```bash
python3 -m grafana_jsm_sandbox.run_command skill
```

Two things the permission boundary decides for the skill, both found by running it:

- A `jira-as` command that is split across lines, carries a newline inside an argument, or uses
  `$'...'` does not match the allow list and is denied whole. Every invocation in the skill is one
  line of plain single quotes; the Description gets its paragraphs from one line of ADF instead.
- A Run has no clock of its own — `date` is not on the allow list — so every duration it reports is
  Jira's `serverTime` minus the Incident's `created`. Grafana's clock is never used for a duration,
  which is also what keeps a replayed fixture from reporting a negative one.

The **Forwarder** — the localhost process that holds the real Jira credential so a Run never does.

A Run's environment points jira-as at the Forwarder over plain http, with a per-Run **sentinel**
in place of the API token. The Forwarder swaps that sentinel for the real email and token and
forwards the request to the configured Atlassian site (ADR 0002). It binds to loopback only, takes
its upstream from configuration and never from the request, hands a redirect back rather than
following it somewhere else, and refuses a request whose sentinel is missing, wrong, or left over
from a Run that has ended. Neither the token nor an Authorization header reaches any log line.

Run it on its own to point a jira-as on this machine at the real site through a sentinel:

```bash
python3 -m grafana_jsm_sandbox.forwarder
```

```
forwarding to https://example.atlassian.net as ops@example.com
point jira-as at the Forwarder with a sentinel in place of the token:

    export JIRA_SITE_URL=http://127.0.0.1:61545
    export JIRA_API_TOKEN=<a fresh 32-character sentinel>

forwarded GET /rest/api/3/search/jql?jql=project+%3D+OPS, upstream said 200
refused a GET /rest/api/3/myself with no valid sentinel
```

It reads `JIRA_SITE_URL`, `JIRA_EMAIL` and `JIRA_API_TOKEN` from its own environment and fails at
startup, naming every variable that is missing, rather than no-opping during the demo. The
Receiver owns it, and the spawner below registers each Run's sentinel around that Run.

The **Run spawner** — what the Receiver starts for each Notification, for real.

`RunSpawner` builds the Run's environment from scratch rather than inheriting one: the Anthropic
OAuth token, the Jira email, `JIRA_SITE_URL` pointing at the Forwarder over plain http,
`JIRA_API_TOKEN` set to that Run's sentinel, `JIRA_ALLOW_SITE_OPERATIONS` so the Run can ask Jira
what time it is, and `PATH`. Nothing else — not the real Jira token, not whatever else the
Receiver happened to be started with. The sentinel is registered with the
Forwarder before the process starts and cleared the moment it ends, so a sentinel that turns up in
a Transcript afterwards is worth nothing.

The Run's stdout is its Transcript, rendered into the log by the formatter as it arrives. Its
stderr is captured and logged only if it exits non-zero, redacted like every other line. A Run
that outlives its timeout is killed and logged, and the queue behind it keeps moving.

## Historical laptop demo walkthrough (disabled)

The Receiver, the Forwarder and real Runs are one process — the demo container's main process,
and this on a laptop:

```bash
python3 -m grafana_jsm_sandbox
```

This command now exits with `legacy_launch_disabled` before reading the
historical credentials listed below. The table documents the retired format.

| Variable | What it is |
| --- | --- |
| `JIRA_SITE_URL` | The real Atlassian site. Only the Forwarder ever sees it |
| `JIRA_EMAIL` | The account the Forwarder acts as |
| `JIRA_API_TOKEN` | The real token. It never reaches a Run |
| `CLAUDE_CODE_OAUTH_TOKEN` | What a Run authenticates with. The one real credential it holds |
| `RECEIVER_HOST` / `RECEIVER_PORT` | Where the Receiver listens. `0.0.0.0` and `8080` |
| `RUNS_DIRECTORY` | Where each Run's working directory goes. `runs` |
| `SKILL_DIRECTORY` | The skill a Run reads. This repo's `skill` |
| `RUN_TIMEOUT` | Seconds before a stuck Run is killed. `300` |

Then drive it with the canned Notification sequence — a Firing, a repeat Firing, a Resolved —
which is also the demo's fallback if Grafana is uncooperative:

```bash
python3 -m grafana_jsm_sandbox.replay --receiver http://localhost:8080 --pause 30
```

## Historical container demo walkthrough (disabled)

`docker compose up` is the whole demo: the LGTM stack the Alert fires from, one demo container
whose main process is the Receiver, the rolldice app the Alert is about, and the synthetic
traffic whose absence fires it — on one network so that Grafana's contact point can name `demo`
by service name.

```bash
git clone https://github.com/grandcamel/grafana-jsm-sandbox.git
cd grafana-jsm-sandbox
cp .env.example .env     # then fill in the four credentials
docker compose up -d --build
docker compose logs -f demo
```

The image carries only what a Run needs (ADR 0005). It is built from the slim official Node
image at a pinned tag, plus the distribution's Python 3 and TLS roots, and installs exactly Claude
Code and `jira-as` at pinned versions, this package and the skill. It runs as `demo`, a non-root
user the Dockerfile creates; the base image's own account and package managers are removed. There
is no `sudo`, no `docker` CLI or group, no `gh`, `git`, `curl` or `jq` — `ls /usr/local/bin` inside
the container is `claude`, `jira-as`, `node`, `nodejs`, `npm` and `npx`, and that is the answer to "what else can a
Run reach for". The entrypoint pre-accepts Claude Code's onboarding with Python's standard library
and the healthcheck asks the health endpoint the same way, because nothing else is there to do it
with. It mounts no Docker socket and holds no credential — those arrive at `docker compose up`
from `.env`, which git ignores and the build context refuses. The image is 539 MB; the developer
image it replaced was 4.35 GB.

The container runs the way Anthropic's secure-deployment guide describes a headless agent, and
the compose file is the whole list: every Linux capability dropped, `no-new-privileges`, a
read-only root filesystem, a process limit, and memory and CPU limits sized for three Runs in a
row on a laptop. The three directories a Run writes are tmpfs, and nothing else is writable:
`/tmp`, the runs directory, and the Run user's home, where the entrypoint writes the onboarding
flag and Claude Code its configuration and Transcripts. They are exactly what `docker diff`
lists after three Runs, and none survives a restart. The default test run reads each control
off the compose file; the opt-in stack checks read them back from the running container's
kernel, a write refused on the read-only root and accepted on each tmpfs among them, and say so
when a Compose too old to apply a limit has left it off (`pids_limit` needs Compose 2.2, `cpus`
2.17). Which controls are the guide's and which are this repo's is in the runbook's spoken
points.

On a laptop behind an intercepting proxy, one variable names the corporate root CA as a PEM
file under `certs/`, a directory git takes nothing from but the empty placeholder the build
defaults to. Both images install it into their system trust store before any `npm` or `pip`
install, and the demo image points Python, `requests`, pip and Claude Code at that store
through the standard trust-store variables, which each Run inherits alongside its sentinel and
nothing else new. The runbook has the presenter's steps.

```bash
EXTRA_CA_CERT=certs/corporate-root.crt docker compose up -d --build
```

The Receiver answers on the compose network at `http://demo:8080`, which is what Grafana will
post to, and on the laptop at `http://localhost:8080`, which is where the replay script posts:

```bash
curl -fsS http://localhost:8080/health
python3 -m grafana_jsm_sandbox.replay --receiver http://localhost:8080 --pause 30
```

Grafana is on the laptop at <http://localhost:3000>, anonymous admin, no login form.

### Firing the Alert for real

Grafana's contact point, notification policy and alert rule are provisioned from
[`grafana/provisioning/alerting`](grafana/provisioning/alerting), mounted read-only into the LGTM
container. Nothing inside the published image is edited; these three files are the whole of the
alerting configuration. Grafana reads the
directory once, at startup, so a change to any of the three files is `docker compose restart lgtm`.

| File | What it provisions |
| --- | --- |
| `contact-point.yaml` | `demo-receiver`, a webhook at `http://demo:8080/notification` |
| `notification-policy.yaml` | One route, everything to `demo-receiver`: group wait 10s, repeat interval **1m** |
| `alert-rule.yaml` | `rolldice request rate is zero`: evaluated every 10s, Firing after 30s at zero |

The rule watches `http_server_duration_milliseconds_count{service_name="rolldice"}`, which is
what the Python auto-instrumentation in the rolldice image actually exports to Prometheus — asked
of Prometheus with rolldice under traffic, not guessed. The rolldice app keeps exporting the
counter after its traffic stops, so the rate reads zero rather than going missing, and no-data is
deliberately Normal so that a rolldice that has not yet served a request starts no Run.

**The repeat interval override is the one thing not to lose.** Grafana's default is four hours,
which means the Alert fires once and the repeat Firings that add trend comments never arrive
during a demo. `repeat_interval: 1m` in `notification-policy.yaml` is the override, with the group
wait and group interval at 10s for the same reason.

The `traffic` service sends rolldice one request a second. The presenter's one action, and its
undo:

```bash
docker compose stop traffic
```

```bash
docker compose start traffic
```

Measured on this laptop, from the container log: the Firing Notification arrives 70s after the
stop, the first repeat 70s after that, and the Resolved 20s after traffic is started again. The
whole lifecycle — Incident created, moved to Work in progress with a trend comment, Completed
with a resolution — took 3m30s, three Runs, $0.47.

The canned fixtures under `fixtures/` are the three Notifications Grafana posted during that
rehearsal, so the replay script drives the same Alert, Fingerprint included. That is deliberate:
if the live Alert has already opened an Incident when the fallback is needed, the replayed Firing
comments on it rather than opening a second one, which is the demo working. It also means the
replay and the live Alert must not be run at the same time.

Everything a Run does arrives in `docker compose logs -f demo` through the formatter — its own
text, every `jira-as` command in full, and every denial. To look around inside, the entrypoint
honours a command:

```bash
docker compose run --rm demo sh
```

### Presenting it

[`docs/demo-runbook.md`](docs/demo-runbook.md) is the runbook: the three-window screen layout,
the pre-demo checks, every presenter action with what the audience sees and how long each wait
is, the five spoken points, the replay fallback, and the reset. Its numbers come from a timed
rehearsal recorded in ticket 08.

Rehearsals leave Incidents behind, and the Incidents queue must start empty. The reset takes
every open Incident a Run made — the ones with an `fp-` label — out of the queue the only clean
way this workflow has, `Resolve` with a resolution and then `Close` (ADR 0004), and starts the
traffic so the rule goes back to Normal:

```bash
python3 -m grafana_jsm_sandbox.reset
```

It runs on the laptop with the `jira-as` credential in the shell, prints what it did per key,
and exits non-zero if anything a human has to finish is still open. It never cancels and never
deletes.

## Layout

| Path | What it holds |
| --- | --- |
| `grafana_jsm_sandbox/receiver.py` | The Receiver, its Run queue and the `Run` record |
| `grafana_jsm_sandbox/notification.py` | Validation of an incoming Notification |
| `grafana_jsm_sandbox/log_formatter.py` | Rendering a Run's Transcript, and the redaction rules |
| `grafana_jsm_sandbox/forwarder.py` | The Forwarder, the sentinel check and the Jira credential |
| `grafana_jsm_sandbox/run_command.py` | The command line that starts one Run, and its allow list |
| `grafana_jsm_sandbox/run_spawner.py` | Starting one Run for real: its scrubbed environment, its sentinel |
| `grafana_jsm_sandbox/replay.py` | Posting the canned Notification sequence at a Receiver |
| `grafana_jsm_sandbox/reset.py` | Emptying the Incidents queue of a rehearsal's Incidents and restarting the traffic |
| `docs/demo-runbook.md` | The presenter's runbook: screen, checks, actions, spoken points, fallback, reset |
| `grafana_jsm_sandbox/__main__.py` | The whole process: configuration, the Forwarder, the Receiver |
| `skill/incident-sync/SKILL.md` | The skill a Run follows to turn a Notification into Incidents |
| `Dockerfile` | The demo image: slim Node plus Python, Claude Code, `jira-as`, the package and the skill, one non-root user |
| `docker/entrypoint.sh` | What the container starts: onboarding pre-accepted, then the Receiver |
| `docker-compose.yml` | The LGTM stack, the demo container, rolldice and its traffic, on one network |
| `docker/rolldice/` | The rolldice example app, copied from the `grafana/docker-otel-lgtm` examples under Apache-2.0, auto-instrumented |
| `certs/` | Where a corporate root CA goes for a build behind a proxy; only the empty placeholder is committed |
| `grafana/provisioning/alerting/` | The contact point, the notification policy and the alert rule Grafana loads |
| `.env.example` | Every variable the container needs, with placeholders |
| `LICENSE`, `NOTICE` | MIT for this repository; the Apache-2.0 attribution for the copied rolldice files |
| `fixtures/notification-*.json` | The canned Notification sequence as Grafana really posted it: firing, repeat, resolved |
| `fixtures/run-transcript.jsonl` | A recorded Run Transcript, including a real denial |
| `fixtures/run-transcript-repeat-firing.jsonl` | A recorded Run that commented a trend on a real Incident |
| `tests/` | pytest, driving a real Receiver and Forwarder over real HTTP on ephemeral ports |

## Running the tests

Python 3.11 or newer. The runtime is standard library only; the dev dependencies are pytest
and PyYAML, which the container checks use to read `docker-compose.yml`.

```bash
python3 -m pytest
```

The default run is offline: no Jira, no model, nothing but real HTTP on ephemeral ports and real
child processes. The one test that touches OPS is opt-in, and asserts by JQL that the canned
sequence drove one Incident to `Completed` with its trend comments. It needs a Receiver already
running and a `jira-as` credential in the shell, and it resolves and closes the Incident it
watched on the way out:

```bash
DEMO_END_TO_END=1 python3 -m pytest tests/test_end_to_end.py
```

The checks that need the container are opt-in the same way, and need nothing but `docker compose
up -d` first. They ask the questions compose cannot answer on its own: whether the health
endpoint answers the laptop and the `lgtm` container, whether the Receiver is really running
as a user who is not root with the two executables a Run is allowed on its PATH, and whether
`sudo`, `docker`, `gh`, `git`, `curl` and `jq` are really absent from it, along with any `docker`
group, on a Node new enough to read the operating system trust store. When the shell's
`EXTRA_CA_CERT` names a certificate, they also find its fingerprint in the container's bundle and
confirm Python's default SSL context loads it; when it names none, that nothing was added.

```bash
DEMO_CONTAINER=1 python3 -m pytest tests/test_container.py
```

The same flag runs the Grafana checks, which ask the running Grafana what it was provisioned with
rather than reading the files back — a typo in a provisioning file makes Grafana skip it and say
so only in its own log. They check the contact point aims at the Receiver on the compose network,
the policy repeats every minute, the rule evaluates every ten seconds and fires after thirty, the
rule's own query matches a series rolldice really exports, the rule is Normal while traffic flows,
and the canned fixtures describe the Alert Grafana is provisioned to send:

```bash
DEMO_CONTAINER=1 python3 -m pytest tests/test_grafana.py
```

Everything else in `tests/test_container.py` runs by default and builds nothing: it reads the
committed `Dockerfile`, `docker-compose.yml` and `.env.example` and drives them against the code
they configure — the example is fed to the real configuration reader, its values through the real
redaction, the ignore rules through real `git check-ignore`, and the entrypoint is run under `sh`
on a PATH holding only what the slim image carries. It holds the Dockerfile to ADR 0005: the base
is the slim Node image at a pinned tag, Claude Code and `jira-as` are pinned, the distribution
adds nothing but TLS roots and a Python, no line installs an escalation tool, and the last `USER`
is one the Dockerfile created. It holds both Dockerfiles to the certificate mechanism: the
corporate CA is installed before anything reaches npm or PyPI, the trust-store variables point at
the system bundle, compose hands the same argument to both builds, and git ignores everything in
`certs/` but the placeholder. It also holds compose to the three things the live Alert depends
on: every service on the one network, this repo's provisioning directory mounted where Grafana
reads it, and a stopped `traffic` staying stopped.

## License

MIT, in [LICENSE](LICENSE). The three files under `docker/rolldice/` are copied from
[grafana/docker-otel-lgtm](https://github.com/grafana/docker-otel-lgtm) and stay under the
Apache License 2.0; [NOTICE](NOTICE) says which, and what was changed.
