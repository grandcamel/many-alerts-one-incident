# Ticket 13 — Memory fact sheet (offline, 2026-09-17)

## Scope and vocabulary

Ticket 13 asks for the contents of three Memory stores (OPS Incidents, a
Confluence space, and a Memory directory), what a Run reads before Match and
writes after Report, Confluence seeding/postmortems, and the directory's one
restart-persistence exception (`.scratch/many-alerts-one-incident/issues/13-memory.md:7-13`).
The current glossary defines Memory as those three stores, and the directory as
the one cross-Run place where a Run writes system learning
(`CONTEXT.md:98-104`). An Incident carries every Alert Fingerprint it explains
(`CONTEXT.md:106-110`); a Report is its body, including evidence, Suggested
root cause, and remediation (`CONTEXT.md:116-122`).

## Accepted upstream constraints, not new policy

Ticket 14’s accepted Answer says Match reads candidate Report, member set, and
relevant times, accepts only uniquely supported evidence, and records
confidence (`.scratch/many-alerts-one-incident/issues/14-many-to-one-under-a-cascade.md:236-244`).
It requires durable current state for accepted Fingerprints; membership labels
alone are insufficient, but deliberately leaves the store representation open
(:254-260). Later Runs append evidence/correction entries and never silently
rewrite earlier claims; human correction owns membership moves, merges, and
Severity correction (:262-267). These facts constrain a Memory design; they do
not choose its store split.

Ground truth is repository-only: never cluster, Grafana, OPS, Confluence, or
Memory directory (`docs/adr/0008-ground-truth-is-two-layers-and-never-enters-the-runs-world.md:1-5`).
The ADR calls the directory the live contamination risk and says Ticket 13 must
constrain what a Run can record there (:13-18).

## Current Run and persistence boundary

ADR 0003 gives a Run `dontAsk` with exactly `Bash(jira-as *)` and `Read`; calls
outside it are denied (`docs/adr/0003-runs-use-dontask-with-jira-as-allowlist.md:1-7`).
The implemented argv matches that allowlist
(`grafana_jsm_sandbox/run_command.py:30-34,62-80`). It therefore has neither a
general shell-write authority nor `confluence-as` authority today.

Current Receiver source creates a unique working directory below
`RUNS_DIRECTORY` and writes only the Notification there
(`grafana_jsm_sandbox/receiver.py:94-100`). Compose makes `/tmp`, `/app/runs`,
and `/home/demo` tmpfs under a read-only root (`docker-compose.yml:74-78`);
the container test asserts these are exactly the writable scratch directories,
with no volumes, so restart starts clean
(`tests/test_container.py:769-774`). This is current source, not a persistent
directory implementation. A narrow persistent writer therefore needs an
explicit new writable mount/path and command/tool authority.

ADR 0005 is the current architectural boundary: minimal image plus runtime
read-only root and tmpfs for temp, runs, and home
(`docs/adr/0005-container-is-the-boundary-minimal-image.md:1-5`). ADR 0002
puts the Jira credential in Receiver-owned localhost Forwarder and gives a Run
only a per-Run sentinel (`docs/adr/0002-jira-token-behind-localhost-forwarder.md:1-8`).
The planned DOKS venue puts Receiver and each Run in the cluster, with secrets
created at `make up`, not committed (`docs/adr/0007-one-digitalocean-node-with-everything-in-the-cluster.md:16-19`).
It does not define Memory storage.

## Installed confluence-as 1.1.1: offline discovery

The installed executable reports version 1.1.1 (`.scratch/many-alerts-one-incident/reviews/ticket-13/cli.txt:158`),
has no `help` subcommand (only `--help`), and has no `api` namespace
(`.scratch/many-alerts-one-incident/reviews/ticket-13/cli.txt:1-40,88-91,160-164`). Its top-level help lists page, search,
and comment commands (:24-40). Leaf help supports page get/body format
(:92-101), CQL/text search (:127-147), page create/update (:102-126), and
comment add (:148-155).

`page create` has native `--status [current|draft]`
(`.scratch/many-alerts-one-incident/reviews/ticket-13/cli.txt:102-114`). Source POSTs that selected status verbatim
to `/api/v2/pages` (`/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/cli/commands/page_cmds.py:160-224`), so it is a native-draft capability, not a title/label convention. `page update` likewise accepts status and PUTs a versioned update (:253-329). Neither was exercised against a live tenant, so native tenant acceptance/read-back remains unverified.

The client obtains `CONFLUENCE_SITE_URL`, `CONFLUENCE_EMAIL`, and
`CONFLUENCE_API_TOKEN`, then enforces HTTPS
(`/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/config_manager.py:52-88`; `/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/assistant_skills_lib/validators.py:262-266`). It builds API requests beneath `<base>/wiki/`
(`/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/confluence_client.py:165-185`). Thus current source cannot use ADR 0002’s plain-HTTP localhost Forwarder unchanged; no TLS-forwarder or patched-client decision is made here.

Historical ticket-06 evidence also found no CLI space-write guard and treated
dedicated-space permissions as the control, but it is an earlier offline
research conclusion, not a current tenant read (`.scratch/many-alerts-one-incident/issues/06-confluence-as-as-the-peer-of-jira-as.md:21-32`). Search CQL writes query history under home in current source
(`/Users/jasonkrueger/.as-plugins-venv/lib/python3.13/site-packages/confluence_as/cli/commands/search_cmds.py:152-194`), which today is tmpfs, not persistent Memory.

## Decision blockers / unverified facts

No live Confluence calls occurred. Unverified: target-space identity and grants;
Confluence draft creation/read-back on the target tenant; Confluence passage
through a Forwarder; whether a future persistent volume is appropriate in the
DOKS deployment; concurrency, retention, schema, and a Ground-truth exclusion
enforcement mechanism. These require product/design and later acceptance work,
not inference from current source.
