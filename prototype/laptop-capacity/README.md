# PROTOTYPE — laptop capacity (ticket 08)

Throwaway. Answers one question: **can this laptop hold the OpenTelemetry Demo's
core layer, the LGTM stack, a kind cluster and one Claude container at once?**

Not production. Nothing here graduates to `main` except the numbers it produced,
which live on the ticket.

## Shape

The `/prototype` skill offers two branches — "does this state model feel right"
(a logic HTML file) and "what should this look like" (UI variations). Neither
fits a capacity measurement, so this follows the skill's *shared* rules instead:
throwaway and marked as such, one command to run, no polish, surface the state
after every step, captured to a branch with the answer on the issue.

## Run it

The demo itself is NOT vendored — it is cloned to the scratchpad at tag 3.0.0,
so nothing third-party is published here (see ticket 20).

    git clone --depth 1 --branch 3.0.0 \
      https://github.com/open-telemetry/opentelemetry-demo.git <somewhere>
    export DEMO=<somewhere>

    ./run.sh pull                 # ~14 GB of images
    ./run.sh up                   # the 17-service core layer + LGTM
    ./measure.sh <stage-label>    # numbers into results/
    ./check-grafana.sh            # is Grafana usable, did telemetry land
    ./run.sh flag adFailure on    # flip a fault
    ./run.sh down

## Files

- `services.txt` — the core layer: `compose.yaml`'s 20 services minus
  `load-generator`, `flagd-ui` and `telemetry-docs`, plus `lgtm`.
- `compose.lgtm.yaml` — adds the LGTM stack on the demo's own network, loaded
  last as the documented extras seam.
- `otelcol-config-extras.yml` — chains the demo's own collector into LGTM.
  Copied over the demo's stub by `run.sh`. Every pipeline repeats the upstream
  exporter names because the collector merges config but REPLACES arrays.
- `compose.claude.yaml` — stage 4, one Claude container at this repo's own 2g cap.
- `measure.sh` / `check-grafana.sh` / `run.sh` — the harness.
- `results/` — one file per stage, plus `00-blockers-found.txt`.
