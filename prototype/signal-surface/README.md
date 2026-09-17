# PROTOTYPE — the signal surface and the Fault gates (ticket 27)

Throwaway. Answers one question: **are the queries ticket 10 wrote actually
runnable at this venue, and do the three chosen Faults behave the way their
Ground truths say?**

Nothing here graduates to `main` except the numbers it produced, which live on
the ticket.

## Why this exists

[Faults and their Cascades](../../.scratch/many-alerts-one-incident/issues/10-faults-and-their-cascades.md)
chose three Faults and wrote every query they rest on. **Almost none of those
queries had ever been run.** No application service's logs had been retrieved
from this venue's Loki, Tempo had never been queried here at all, and the 578
Prometheus metric names were counted but never enumerated — so
`traces_span_metrics_calls_total` was a probable name backed by prose in a
summary, not by an artifact.

That is the same failure mode that has cost this project three decisions: a
plausible claim nobody ran. Every probe here writes its raw answer to
`capture/`, so each finding has a file behind it.

## What it inherits from ticket 26

Built on `prototype/doks-chart-capacity`, carrying its three corrections:

- **flagd does not read the ConfigMap.** The chart copies it once into an
  `emptyDir` via an init container and there is no `checksum/config`, so a
  ConfigMap write alone is inert. `flag.sh` does the write **plus
  `kubectl rollout restart deploy/flagd`**, then reads flagd's own in-pod copy
  back to prove the variant landed.
- **DOKS ships no metrics-server**, and the upstream manifest needs
  `--kubelet-insecure-tls`. `run.sh metrics-server` does both. Without it
  `kubectl top` is dead and items 7 and 10 cannot be measured at all.
- **`helm --wait` exited 0 over a crashlooping pod.** `run.sh ready` is the
  harness's own gate.

`values-demo.yaml` already carries `mode: deployment`, without which the
`kubernetesEvents` preset renders nothing.

## This costs money

One `s-8vcpu-16gb` node is **$0.142860/hour**. Create only with `--ha=false`,
`--size` and `--count` — omitting `--ha` defaults the HA control plane **on** at
$40/month, prorated and irreversible, and `doctl` otherwise defaults to three
`s-1vcpu-2gb-intel` nodes. `run.sh cluster-create` enforces all three.
**Destroy in the same session.** LGTM climbs ~14 Mi/min against a 4 GiB limit,
so bring the cluster up inside the working window, not the morning of.

## Run it

    ./run.sh cluster-create        # COSTS MONEY
    ./run.sh repo
    ./run.sh install-demo
    ./run.sh install-lgtm
    ./run.sh metrics-server
    ./run.sh ready                 # helm's exit code is not proof of health
    ./run.sh pf                    # Grafana on localhost:3000, the only door

    python3 lib/venue.py | tee capture/items-1-6.log    # items 1-6, flags OFF

    ./fault.sh inject paymentUnreachable on   12 checkout payment
    ./fault.sh undo   paymentUnreachable checkout

    ./fault.sh inject emailMemoryLeak    1000x 20 email checkout
    ./fault.sh undo   emailMemoryLeak    email

    ./fault.sh inject cartFailure        on    12 cart checkout
    ./fault.sh undo   cartFailure        cart

    ./run.sh cluster-delete        # ALWAYS

## The order matters

Items 1 to 6 are venue-wide and **gate everything else** — if
`traces_span_metrics_calls_total` is not the real name, every alertable
condition in ticket 10 is written against a series that does not exist, and
there is no point measuring a Fault against it.

Then one Fault at a time, never two. The flagd rollout briefly zeroes *every*
flag as providers fall back to code defaults, and it emits identical Kubernetes
Events for injection and for remediation.

Inside a window, `fault.sh` flips, proves flagd holds the variant, and only then
runs **item 13** — a real symptom in the telemetry — before trusting any clock.
Verifying flagd is not verifying the caller.

## Files

- `run.sh` — cluster lifecycle, installs, readiness gate, port-forward.
- `flag.sh` — the whole flip: ConfigMap write + flagd rollout + in-pod proof,
  with every step timestamped into `capture/timing-*.json`.
- `fault.sh` — one Fault window end to end: baseline, inject, symptom watch,
  probes, undo.
- `lib/graf.py` — the query client. Everything goes through Grafana's datasource
  proxy, because that is the only door a Run has.
- `lib/venue.py` — items 1 to 6.
- `lib/symptom.py` — item 13, and injection → first symptom.
- `lib/faultprobe.py` — items 9 to 12: ticket 10's queries, verbatim, live.
- `lib/podwatch.py` — items 7, 9, 10: memory, restarts, `lastState.terminated`.
- `capture/` — one artifact per probe. The point of the ticket.

## What this prototype does NOT do

The **first-Alert-to-last-Alert** half of the timing budget. That is a property
of a Fault *and a rule*, and the rules do not exist until
[Alert rules for a Cascade](../../.scratch/many-alerts-one-incident/issues/28-alert-rules-for-a-cascade.md)
picks thresholds off the baselines captured here. Injection → flagd ready →
first symptom needs no rules and is measured.
