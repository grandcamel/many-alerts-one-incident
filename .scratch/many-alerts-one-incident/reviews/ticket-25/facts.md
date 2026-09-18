# Ticket 25 facts (offline, 2026-09-18)

## Current main implementation

- No DOKS presenter/fault-injection or Change-recording script is present in this checkout: the only
  committed presenter action is Compose `docker compose stop traffic`, with `start traffic` as undo
  (`main:docker-compose.yml:1-16`). A source search finds no ConfigMap/flagd/rollout implementation
  outside planning/history. Therefore main currently records neither desired edit, rollout, served or
  evaluated flag, actor/time, nor injection-versus-undo Change data for the planned venue.

## Historical venue evidence

- A ConfigMap edit alone changed `resourceVersion` but flagd reads a one-shot init-container copy in
  `emptyDir`, so services still saw every flag off. The measured working action was ConfigMap edit
  **plus** `kubectl rollout restart deploy/flagd`; that performs an additional API mutation
  (`main:.scratch/many-alerts-one-incident/issues/26-can-one-doks-node-hold-the-chart.md:102-111`).
  Ticket 27 later reports that, for each tested Fault, flagd was shown holding the new variant and a
  real symptom was observed before timing
  (`main:.scratch/many-alerts-one-incident/issues/27-verify-the-signal-surface-and-settle-the-fault-gates.md:149-154`).
- The historical timing splits ConfigMap write (1–2s), rollout (2–4s), and injection-to-ready (4–5s)
  (`main:.scratch/many-alerts-one-incident/issues/27-verify-the-signal-surface-and-settle-the-fault-gates.md:240-251`). These are measured
  prototype timings, not a durable actor/time Change record or future bound.
- Kubernetes Events reached Loki in the deployment-mode test, but the receiver watches rather than
  lists (no backfill) and event fields are structured metadata, not selectors
  (`main:.scratch/many-alerts-one-incident/issues/26-can-one-doks-node-hold-the-chart.md:138-148`). The planning record also says rollout
  Events are identical for injection and remediation, so they cannot distinguish undo
  (`main:.scratch/many-alerts-one-incident/issues/25-the-change-making-a-faults-cause-citable.md:119-127`).

## Supported retrieval and gaps

- Tempo is the proven Trigger retrieval path for `paymentUnreachable` and `cartFailure`: service
  traces carried `feature_flag.evaluation` with key, variant/value, reason and provider, and the
  TraceQL key filter discriminated a nonexistent key
  (`main:.scratch/many-alerts-one-incident/issues/25-the-change-making-a-faults-cause-citable.md:131-151`).
  Metrics lack a flag key and flagd stdout remains absent from Loki
  (`main:.scratch/many-alerts-one-incident/issues/25-the-change-making-a-faults-cause-citable.md:146-151`).
- `emailMemoryLeak` produced zero evaluation traces, so it has no equivalent currently proven Trigger
  retrieval
  (`main:.scratch/many-alerts-one-incident/issues/25-the-change-making-a-faults-cause-citable.md:153-160`). Email has separate
  symptom/restart evidence, not a Change record.
- No historical evidence cited here establishes a stored actor identity, canonical Change timestamp,
  desired-versus-served/evaluated correlation ID, or implemented Grafana annotation. Alert-rule annotation templates must not be confused with Grafana dashboard annotations.

Source inventory command: `git ls-files` over Python, shell, YAML and Makefile paths; current main contains the Compose stack and Receiver/Forwarder package, not the planned DOKS action coordinator. Planning statements about unavailable evaluation traces describe the measured sample, not impossibility under all future instrumentation.
