# Ticket 15 — Run telemetry facts (offline, 2026-09-18)

## Scope and evidence boundary

Ticket 15 is a planning question about which harness export and Transcript
events reach LGTM, their labels, Run self-observation, and audience view
(`.scratch/many-alerts-one-incident/issues/15-run-telemetry-as-a-signal.md:1-15`).
Ticket 02 records historical research at commit `285d85e`: documentation fetches,
one paid Run, and replays against a laptop stack on 2026-09-15
(`.scratch/many-alerts-one-incident/reviews/ticket-15/historical-research.md:7-17`).
It is not proof of the current source configuration or planned DOKS venue.

The required `claude-api` skill was not found by `rg --files --hidden` in the
specified cache roots, nor in bounded likely skill paths under `~/.claude`,
`~/.codex`, and `~/.agents`. This sheet therefore makes no new Claude flags,
model, or exporter-behaviour claim; where needed it labels ticket-02 research
as historical.

## Current Transcript path

`RunSpawner` starts the configured command with stdout piped, sends each line to
`format_stream`, and logs each formatted line (`grafana_jsm_sandbox/run_spawner.py:121-160`).
It does not write stdout to a Transcript file or send it to OTLP. Receiver writes
only each Notification to its Run working directory
(`grafana_jsm_sandbox/receiver.py:94-100`).

`format_stream` parses newline-delimited JSON and calls `format_event`
(`grafana_jsm_sandbox/log_formatter.py:100-135`). It renders init metadata,
assistant text/tool calls, tool results, permission denials, and result
duration/turn/cost; it deliberately drops other system chatter and
`rate_limit_event` (`log_formatter.py:138-232`). The formatter test binds this
to the two recorded fixture shapes and verifies the final result display
(`tests/test_log_formatter.py:334-342,394-409`). Fixtures themselves contain
raw `session_id`, `request_id`, tool inputs/results, usage and result fields
(`fixtures/run-transcript.jsonl:1-12`; `fixtures/run-transcript-repeat-firing.jsonl:1-39`).

Every display line is passed through `redact` (`log_formatter.py:8-14,93-119`).
Its patterns cover Authorization/basic/bearer forms, credential-named flags and
assignments, recognizable prefixes, and long opaque strings
(:48-90). Tests exercise commands, outputs, and denied commands so credentials
do not reach rendered lines (`tests/test_log_formatter.py:241-310`). This
protects the container log presentation; there is no current Transcript-to-LGTM
shipping implementation to inherit that protection.

## Join key: historical capability versus current code

The fixtures show a `session_id` on both init and subsequent events
(`fixtures/run-transcript.jsonl:1-12`). Ticket-02 research reported it matched
the OTLP `session.id` and proposed Receiver-selected `--session-id` as the
shared key (`.scratch/many-alerts-one-incident/reviews/ticket-15/historical-research.md:21-31,390-404`). Current `build_run_command`
does not include `--session-id` (`grafana_jsm_sandbox/run_command.py:54-81`),
and formatted log lines contain no `session_id` (`log_formatter.py:138-216`).
The Receiver has a distinct generated `run_id` for its working directory
(`receiver.py:94-100`). Thus current source has no configured, emitted join from
Receiver Run ID to Transcript/OTLP session ID; the historical equality is not a
current implementation.

## Export-versus-Transcript gap

Historical research says the Claude export omits command line, tool output,
denial text, final cost, and turn count, which the formatter can present, and
that the Transcript needs a separate shipment decision
(`.scratch/many-alerts-one-incident/reviews/ticket-15/historical-research.md:48-53,421-427`). Present source confirms the second half:
there is no OTLP client/configuration in `RunSpawner`’s freshly built child
environment, which contains only trust-store values, OAuth token, Jira
Forwarder settings, site-operation permission, and PATH
(`grafana_jsm_sandbox/run_spawner.py:162-180`). The current compose points only
`rolldice` telemetry at LGTM (`docker-compose.yml:117-120`); it sets no Run
telemetry environment. A Transcript shipper versus Receiver OTLP records is
therefore a planning choice, not existing behaviour.

## LGTM: historical correction versus current state

The historical research measured a running laptop `otel-lgtm` stack as
Prometheus 3.9.1, not Mimir, and observed delta counters dropped unless
temporality was changed (`.scratch/many-alerts-one-incident/reviews/ticket-15/historical-research.md:39-47,306-320,405-406`). Current
Compose uses unpinned `grafana/otel-lgtm:latest` (`docker-compose.yml:23-42`),
so neither that exact version nor the delta/cumulative behaviour is current
source evidence. ADR 0007 names the future deployment venue but does not pin an
LGTM image/config (`docs/adr/0007-one-digitalocean-node-with-everything-in-the-cluster.md:7,16-19`).
The map already records the planned venue as `otel-lgtm:0.11.4` with Prometheus 3.4.1 and explicitly rejects transferring the retired Compose temporality result (`.scratch/many-alerts-one-incident/map.md:63`). That is recorded venue evidence, not a fresh exporter acceptance run. Do not replace it with the old 3.9.1 claim or interpret unpinned Compose as the planned venue.

## Unverified boundaries

No model invocation, collector connection, cluster, demo, or network operation
ran for this sheet. Unverified now: exporter delivery on clean exit/SIGKILL,
actual current LGTM signal/temporality handling, run/export session correlation,
OTLP attributes and identity redaction, trace delivery, retention, and any
audience dashboard/log window. Ticket-02 itself listed clean-SIGKILL flush,
successful tool spans, Tempo delivery, service-name override, and collector-down
behaviour as unverified (`.scratch/many-alerts-one-incident/reviews/ticket-15/historical-research.md:441-464`).
