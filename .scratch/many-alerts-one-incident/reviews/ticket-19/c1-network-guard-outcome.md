# Ticket 19 — C1 interface inspection and guard correction, 2026-09-19

Verdict: **the nine extra interfaces were inactive in a fresh network-none diagnostic; a state-based guard is source-tested and prepared**. The user said "proceed" after the proposal to inspect interface state before revising the guard. One bounded inspection container ran and was removed. No full C1 measurement, sentinel admission, MCP client, model or paid call followed.

## Observed state

The diagnostic used the existing Run base `sha256:5abb2fb0c6bebe246ee31e56e4634edc92fe8b3be75bc5dcd12cf00f0592abe9` on the pinned `desktop-linux` endpoint, Docker 29.8.0, Linux/amd64. Container `maoi-c1-interface-inspection-20260919` was created only after name/label collision checks. Its exact ID is recorded in the private ledger. Read-back confirmed UID/GID 1000, network-none, read-only root, no mounts or published ports, no capabilities, no-new-privileges, 2 CPUs, 2 GiB and 256 PIDs. The sole process received a read-only Python diagnostic over stdin. No image build, pull, network/volume creation, credential provision or package install occurred.

Five completed rtnetlink dumps captured links, IPv4/IPv6 addresses and IPv4/IPv6 routes across tables. Raw replies and decoded state were retained. Sysfs flags/type/index/operstate and the three proc network files were captured separately.

| Interface | Kernel kind | Device type | Flags | Operational state |
| --- | --- | --- | --- | --- |
| `lo` | none | 772 | 65609 | UNKNOWN; UP/RUNNING/LOWER_UP flags set |
| `tunl0` | ipip | 768 | 128 | DOWN |
| `gre0` | gre | 778 | 128 | DOWN |
| `gretap0` | gretap | 1 | 4098 | DOWN |
| `erspan0` | erspan | 1 | 4098 | DOWN |
| `ip_vti0` | vti | 768 | 128 | DOWN |
| `ip6_vti0` | vti6 | 769 | 128 | DOWN |
| `sit0` | sit | 776 | 128 | DOWN |
| `ip6tnl0` | ip6tnl | 769 | 128 | DOWN |
| `ip6gre0` | ip6gre | 823 | 128 | DOWN |

All nine non-loopback links lacked UP, RUNNING and LOWER_UP flags. They had **zero IPv4/IPv6 address assignments and zero route entries**. Only `lo` held `127.0.0.1/8` and `::1/128`. The routing dumps returned four routes in local table 255: IPv4 local `127.0.0.0/8`, local `127.0.0.1/32`, broadcast `127.255.255.255/32`, and IPv6 local `::1/128`, all through `lo`. No other route table entries were returned. The earlier empty `/proc/net/route` reading therefore did not describe all IPv4 routes; it omitted these local-table entries.

The tunnel links reported netlink carrier=1 while sysfs carrier reads returned EINVAL. Carrier alone is unsuitable for this guard. The [kernel's operational-state documentation](https://www.kernel.org/doc/Documentation/networking/operstates.txt) distinguishes administrative flags from operational state; [rtnetlink documentation](https://man7.org/linux/man-pages/man7/rtnetlink.7.html) describes the link, address and routing-table messages used here. The classification is based on the captured flags, addresses and routes, not names or carrier alone. This was a fresh diagnostic namespace, not retrospective proof about attempt 2's namespace or proof of lasting isolation.

## Prepared source correction

Local prototype commit: `7741d2060aceb9bb475a42c2f9f3adc5f3c1db7e`. Four changed files: `prototype/local_acceptance/run_probe.py`, its README, `tests/test_c1_network_inventory.py`, and `tests/fixtures/c1_network_none_netlink.json`. No Dockerfile, Compose topology, frozen Stage A/B or production source changed.

The existing Run probe now captures five completed rtnetlink dumps within an eight-second absolute deadline, two-second maximum receive wait and 512 KiB raw reply quota. It raises on truncated, malformed, interrupted, wrongly sequenced or non-kernel replies, unexpected message types, failed/missing completion, timeout and excess output. `snapshot` includes both decoded/raw inventory and a predicate result; the operator must recompute `network_state_allowed` from the committed source before accepting it.

The predicate requires the exact measured loopback flags/address/route profile. It permits any subset of the nine named inactive profiles only when name, kernel kind, device type, flags and DOWN operational state match. Unknown/duplicate links or indices, active flags, any non-loopback address, changed local routes or additional routes fail. Gateway, multipath, nexthop ID, via and encapsulation route attributes fail. Route destinations must remain the four specific loopback routes in table 255; merely naming `lo` is insufficient. This is deliberately specific to the measured inputs; a different legitimate kernel profile requires new evidence, not an automatic allowance.

The separate Docker network-none/capability/identity checks and exact experiment-IP/private-socket connection denials remain mandatory. This correction changes interpretation of inventory; it adds no network attachment or authority. The [prepared execution-card amendment](c1-execution-card.md#prepared-network-guard-amendment--not-yet-executed) specifies operator integration and remaining execution gate.

Validation before the local commit: **409 passed, 36 skipped**, 445 collected, 21.07 seconds. All **44 new tests** passed. They replay the actual Linux kernel replies and reject activation, unknown types/names, IPv4/IPv6 address additions, route/table changes, gateway/multipath/encapsulation/nexthop attributes, duplicate/incomplete data and capture failures. Ruff and whitespace checks passed. These are host replay/source tests; the revised committed probe has **not** yet run in the four-service topology.

## Cleanup and evidence

The diagnostic completed in **1.923 seconds**, including cleanup. Exact-ID deletion, absence by both ID and name, and preservation of the original base image were checked. A later independent container listing also verified the ID absent. No derived image, custom network or volume was created. No transient authority was generated or injected.

Private diagnostic directory: `/Users/jasonkrueger/maoi-stage-b-evidence/c1/interface-inspection-20260919`. Its index verifies **8 files / 115,908 indexed bytes**, excluding the index itself; directory mode 700 and indexed file modes 600 were read back. Created 2026-09-19T23:30:02.943170Z; retention expiry 2026-10-19T23:30:02.943170Z.

| Artifact | SHA-256 |
| --- | --- |
| `network-state.json` | `76634e77d319ee48a93234feafcf272539f434a610f167d09cc8f28e30095c0d` |
| `ledger.json` | `198ff044a2312a3a8a2b75bce0a82dd289ac44dd55dcda7982ce16e8e3b0bfcb` |
| `artifact-index.json` | `1eade6d436d62c0fba4ae0ba7273dd7b2640f415f63db77302610d52a01fbf6c` |
| committed `run_probe.py` | `03801ad63e9de783697d0c7a11344e977c7cd4496d0c0d6b546ceee527317c3c` |

Source hashes, full-suite log/hash and independent cleanup verification are retained at `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/network-guard-20260919/verification.json`, SHA-256 `1217126183210ae59ef3a4cccf3c1cb8b25998891ef67135ee8826f0e097e230`.

## Remaining boundary

The next executable step is one fresh C1 attempt using the amended inventory checks and newly frozen Run source/image output. It retains the existing five positive sessions, one negative session, exact-target direct probes, resource/time/capture limits and stop/cleanup rules. That full build/start/admission was not included in this diagnostic step and has not run. Exact-address denial, native MCP responses/correlation/containment and later C1 drills remain unmeasured; C2, real Grafana, model behavior and intended-cluster acceptance remain separate. Ticket 19 stays claimed, ticket 12 blocked, all $12 reservations retained and provider actuals unknown. Everything remains local.
