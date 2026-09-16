# Upgrade Docker Desktop

Type: task
Status: resolved
Resolved: 2026-09-16
Blocked by: none

## Question

Docker Desktop on this laptop is 4.0.0 from 2021, on Engine 20.10.8 and HyperKit (see "Where a real Kubernetes could run"). The kind provisioner appears by 4.43.0 and became the default at 4.65.0; the Kubernetes view in the Dashboard is 4.51 and later; the current release is 4.91.0. Upgrade it, then read two facts off the Resources pane that the docs do not give: the highest memory the slider allows on this 16 GB machine, and whether the built-in Kubernetes offers the kind provisioner. Human in the loop: installing an application and changing its resource settings is the user's to do. The answer records the version installed, the memory ceiling, the allocation set, and the Kubernetes options shown.

## Answer

Upgraded by the user on 2026-09-16, from 4.0.0 (2021) to **4.91.0 (239619)**. Everything
below was read off the machine after a restart, except the memory ceiling, which is the
one fact that is genuinely GUI-only.

**Versions.** Docker Desktop 4.91.0 (239619); Engine and CLI **29.8.0** (from 20.10.8);
containerd v2.3.4; runc 1.4.3; Compose **v5.5.1**; Buildx v0.37.0; bundled Kubernetes
**v1.36.1**; `kubectl` client v1.36.1. Two "could not verify" items from earlier research
fall out of this: the local Compose was never v2, it is v5.5.1, and the engine is far past
anything the OTel Demo needs.

**The VM moved.** `UseVirtualizationFramework` is now **true** with `VirtioFSing` enabled —
off HyperKit onto Apple's Virtualization Framework. The map's HyperKit fact is retired.
Bind mounts go through VirtioFS, which matters for mounting the skill directory into a Run.

**Resources.**

| | Before | After |
| --- | --- | --- |
| CPUs | 4 | **8** (every logical thread of the 4-physical-core host) |
| Memory | 8 GiB (7.751 GiB to containers) | **12 GiB / 12288 MiB** (11.68 GiB to containers) |
| Swap | 1024 MiB | 1024 MiB |
| Disk image | 61035 MiB (~60 GB) | unchanged; 138 GiB free on `/` |

**The memory ceiling is 16 GiB** — the slider allows the *entire* host RAM and reserves
nothing for macOS. So 12 GiB was a choice with headroom above it, not the maximum, and the
maximum is a setting nobody should use. The 12 GiB floor that "Where a real Kubernetes
could run" identified is now met with 4 GiB left for the host.

**Kubernetes: the kind provisioner is there, and it is the default.** It ships disabled.
`docker desktop kubernetes status` reports `State: disabled`, `Mode: kind`, `Node Count: 1`,
`Version: 1.36.1`. Both provisioners are offered — `docker desktop kubernetes images` lists
a `Mode` column carrying `kind` (4 images: `desktop-containerd-registry-mirror` v0.0.4,
`desktop-cloud-provider-kind` v0.7.0, `envoyproxy/envoy` v1.36.7, `kindest/node`) and
`kubeadm` (10 images, the full control plane). kind is the leaner of the two as well as
the selected one.

**A method worth keeping:** the provisioner question does not need the GUI. `docker desktop
kubernetes status` and `docker desktop kubernetes images` answer it from the CLI, and the
`docker desktop` plugin also does `start`, `stop`, `restart`, `reset-cluster` and
`diagnose` — which means a future session can bring a laptop cluster up and down without a
human at the Dashboard. Only the memory *ceiling* required a person to look.

`kind`, `k3d`, `minikube` and `helm` are still not installed standalone, and on this
evidence they do not need to be: Docker Desktop provisions kind itself. Helm is a separate
question if the Demo is deployed by chart rather than Compose.

What this settles for the map: **"Can the laptop hold it" is unblocked** and its premise is
better than it was written — 8 CPUs rather than 4, 11.68 GiB rather than 7.8, a faster VM,
and a kind cluster available without installing anything. The laptop may be a real venue
rather than a rehearsal one, which is the question "Which system, and where it runs" turns on.

Could not verify: how much of the 11.68 GiB a kind cluster actually leaves for workloads,
which is exactly what "Can the laptop hold it" measures; whether the Dashboard offers any
provisioner beyond the two the CLI lists; and whether the 16 GiB ceiling is enforced softly
(swap) or hard.
