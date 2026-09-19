# Ticket 19 — C1 source/pin preparation outcome, 2026-09-19

This is the historical preparation record. The later [authorized C1 attempt 1](c1-attempt-1-outcome.md) stopped at Forwarder provisioning after builds/service creation; cleanup is verified and no native measurement ran.

Status: **preparation complete for the first C1 execution card; container execution NOT RUN**. The user's "proceed" accepted the proposed next step after C0: implement Unix adapters/probes, resolve Linux/image inputs and prepare a concrete card. Source is committed locally at prototype `3a16de9d4195edd480a914d5211a08f2c3f9cab3`, branch `prototype/mcp-grafana-eyes`. The [C1 execution card](c1-execution-card.md) now records the bounded first measurement, exact inputs/resources, commands, evidence checks and teardown. Its build/start remains separately gated by the [accepted local plan](local-container-acceptance-plan.md).

## Source and exercised behavior

New modules in `/Users/jasonkrueger/projects/maoi-mcp-grafana-prototype/prototype/local_acceptance/` provide bounded HTTP/Unix transport, authenticated one-use admission and revocation, fixed numeric backend routing, synthetic native-tool fixtures, service startup/provisioning, an explicitly gated native driver, receipt correlation, and fixed Linux Run probes. The container definitions now use a holding Run process, private service tmpfs and a private data volume. The operator reaches control with exact-container Docker exec; the design no longer depends on macOS-to-VM Unix-socket bind behavior or host-owned secret-file readability under container UID 2000.

Forwarder requests receive internally generated IDs; gateway/backend receipts retain matching request/response hashes. Overlapping cases, missing admission, quota failures, redirects, unsupported HTTP framing and unknown targets cannot become successful fixture results. Revocation withholds a late response but does not claim to undo a read already dispatched. The native driver stores full MCP responses and requires exact container/image/project identity. Its host-process cleanup is labeled separately from mandatory in-container read-back. C0's recorder gained an explicit distinct C1 origin; its offline CLI remains unchanged.

The fixture policy is deliberately exact and synthetic. Seven positive native-case mappings and seven byte-cap/error/scope mappings are prepared. The new Run probes cover identity, mounts/tmpfs, capabilities, routes, private-file openability, allowed/denied writes, fixed direct-connect targets and direct TLS/authority/write denial. They were host-tested where portable; their Linux identity and confinement results are **NOT RUN**. Stage A, Stage B, the root Docker/Compose files and production package source remain unchanged from `3375fdb`.

## Validation

- Full suite before commit: `env -u DEMO_END_TO_END -u DEMO_CONTAINER python3 -m pytest` — **363 passed, 36 skipped**, 399 collected, 21.28 seconds. This includes all **29 new C1 preparation tests** and the 39 C0 tests.
- Ruff format/check and `git diff --check`: passed.
- Host integration tests exercise real local TLS and Unix sockets, correlation/hash joins and tamper rejection, secret-free receipts, exact 10 MiB minus-one/equal/plus-one HTTP fixture bodies, scope denial before backend dispatch, redirect/error/timeout handling, revocation during a read, restart default-denial state, socket ownership/modes/cleanup, malformed/framing limits, provisioning exclusivity and receipt quota failure. Direct Run-probe logic was exercised against the synthetic host TLS chain. No Linux native MCP process ran.
- Initial host-test failures identified macOS's Unix path-length limit and a socketpair sender-buffer assumption in the tests. Tests now use short private socket directories and an explicit send buffer. The superseded blocked test process was terminated; the final counts above belong to the corrected source.
- Installed Docker/Compose/Buildx help and read-only inspection established the local engine, builder and image IDs. Compose rendered and passed checks for all four declared services, users, read-only roots, capability drops, no-new-privileges, no public ports, network-none Run and internal backend network. The preparation render deliberately used existing base IDs as syntax placeholders, not built derivative images. No image build/pull, container create/start, credential provisioning, model call or cloud action ran.

## Pins and private read-back

The [upstream v1.5.1 release](https://github.com/grafana/mcp-grafana/releases/tag/v1.5.1) metadata and downloaded publisher checksum file agree on the Linux x86-64 archive hash. The archive was downloaded into private storage; the single named executable was read from the tar without extracting arbitrary paths. Its ELF header confirms 64-bit little-endian x86-64. It remains mode 600 and was **not executed**. Base images were inspected locally without pulling; the chapter-one base has an exact local image ID and no registry RepoDigest. Derived image IDs remain build outputs, not missing input pins.

| Private artifact | SHA-256 |
| --- | --- |
| `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/mcp-grafana_Linux_x86_64.tar.gz` | `3ef1c7a66aab3ba149de53681d72ea58244baa41331eb3aed9cdd2f68acc0db7` |
| `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/mcp-grafana-linux` | `208b71a4f1cf707834734671c6d784a8db4ffcf414a182ddc38d21384de8e125` |
| `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/mcp-grafana_1.5.1_checksums.txt` | `058aab9249a0beeecf861c82a0ce927930fcce17d6b527ce28b052c2a0e19ff5` |
| `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/compose-rendered-preparation.json` | `873832b971ec4364eff4e0e4ff6ffb48e4ee7eff0f81421e6e98f420d88a62e8` |
| `/Users/jasonkrueger/maoi-stage-b-evidence/c1-prep/preparation-verification.json` | `40efea5cc1ede43c3138edeedc40ee10cab1d9c27c9ed5d0cebe1d6f9c3092b0` |

The preparation directory contains 75,354,760 bytes at read-back, outside Git. Its verification manifest records hashes for 19 source/test/document files and the private input artifacts, plus test/ELF/render scope. Directory mode is 700; files are 600. No credential values were used in the preparation render; its sentinel is a non-admitted synthetic placeholder. The complete input/engine/image record is `prototype/local_acceptance/containers/inputs.json`. Docker's [Compose service reference](https://docs.docker.com/reference/compose-file/services/) was checked, while installed CLI help and the actual render supplied syntax verification.

## Next bounded action and remaining limits

The first execution card proposes five positive native sessions, one byte-cap/error/scope session, Run-side direct probes, receipt export/join and exact-resource cleanup. Actual volume/tmpfs ownership, public-CA readability, image source-file parity, namespace isolation, lifecycle cleanup and native response behavior must be read back before acceptance. The card explicitly does not yet measure native-client negative certificate variants, in-container mid-query interruption/revocation or restart persistence; host tests cannot stand in for those rows. Any first-run failure stops the card without automatic retry or scope expansion.

Nothing here repairs attempt 4's missing model-client response audit, establishes real Grafana grants, intended-cluster enforcement or Eyes selection. C2 provisioning remains unimplemented and separately gated. Ticket 19 remains claimed, ticket 12 remains blocked, all $12 reservations remain retained and provider actuals remain unknown. No code or evidence was pushed or published.
