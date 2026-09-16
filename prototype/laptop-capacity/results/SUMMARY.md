# Can the laptop hold it — measured 2026-09-16

Docker Desktop 4.91.0, Engine 29.8.0, Apple Virtualization Framework.
Allocation: **8 CPUs, 12288 MiB (11.68 GiB to containers), disk raised 60 G -> 102 G**.
Demo pinned at **DEMO_VERSION=3.0.0** (not just the 3.0.0 git tag — see blockers).

## Memory, stage by stage

| Stage | Containers | VM MemAvailable | Stage cost | Containers (docker stats) |
|---|---|---|---|---|
| 0. Docker idle | 0 | 11.03 GiB | — (Docker itself ~0.65 GiB) | 0 MiB |
| 1. + kind cluster | 0 visible | 10.31 GiB | **~735 MiB** | — (system containers hidden) |
| 2. + LGTM | 1 | 9.78 GiB | ~543 MiB | 429 MiB |
| 3. + demo core layer | 20 | 8.56 GiB | ~1.22 GiB | 1,637 MiB |
| 4. + Claude container (2g cap, idle) | 21 | 8.57 GiB | ~0 | 1,608 MiB |
| 5. under load, fault on | 21 | **8.39 GiB** | ~180 MiB | 1,827 MiB |

**Verdict: it fits, with room to spare.** 8.39 GiB free with everything running
under load. The whole stack costs ~2.6 GiB of the 11.68 GiB; a Claude container
could take its full 2 GiB and still leave ~6.4 GiB unused.

Declared limits overstate reality: the 20 running containers declare 2,655 MB
of limits and actually use 1,827 MiB under load.

## CPU is looser than memory in the VM, tighter on the host

- Containers total **215.8% of 800%** available. No VM CPU pressure.
- But host load average hit **8.84 / 25.97 / 27.83** on 8 threads. The VM has
  headroom; the *laptop* does not have much. Screen sharing and a browser during
  a live demo compete with this.

## Containers nearest their caps (candidates to raise)

flagd-ui 86.9% of 200M · flagd 83.2% of 75M · ad 73.0% of 300M ·
checkout 70.3% of 20M · astronomy-db 60.9% of 80M

## Is Grafana usable? Yes, comfortably

- `/api/health`: 4 ms idle.
- `/api/search`: 130–210 ms idle; **37–46 ms under load** (warm cache).
- A real Run-shaped PromQL range query over 10 minutes: **75 ms**.
- Four datasources live: Loki, Prometheus, Tempo, Pyroscope. Span metrics flowing.

## Does a fault flag fire and show? Symptom yes, cause NO

`adFailure` flipped on: **12 errors in 140 requests** (baseline was 0 in 92).

Visible to a Run:
- Loki: `GetAds Failed with status Status{code=UNAVAILABLE, ...}` on service_name="ad".

NOT visible to a Run — see blockers §4:
- No `feature_flag*` metric of any kind. 240 metric names in Prometheus, zero match.
- flagd's stdout never reaches Loki (0 streams).
- No log anywhere matches the flag file, `configuration_change`, or `adFailure`.
