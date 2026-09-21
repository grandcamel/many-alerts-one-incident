# C2 attempt 1 outcome — 2026-09-21

The explicitly approved first compatibility attempt **stopped before startup** at the Grafana post-create identity/command inspection guard. One internal network and one Grafana container were created; both received durable full-ID receipts and were removed. Independent read-back confirms their absence, deletion of the temporary bootstrap password, preservation of the pinned base image, and no changes to the preexisting container, network, image-list or volume-name inventories. No Loki, Prometheus or Tempo container was created. No backend started, and no health request, ingestion, account/token operation, native MCP session or qualification model run occurred.

The [execution card](c2-attempt-1-card.md) and [preparation plan](c2-approved-compatibility-plan.md) define the approved scope. Run ID: `cd54f95f5c48acc6bbba2141c8d90e21`. Consumed runtime root: `/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-1-20260921`; never reuse it. The single attempt completed with process exit1 and `FAILED_OR_INCOMPLETE`. Host timestamps span 4.068 seconds from the launch-readiness record to the outcome file; this is not a harness monotonic timing measurement.

## Failure and evidence limit

The error was `CompatibilityError: container identity/command inspection mismatch`. Independent comparison of the retained selected inspection confirms matching container ID, image configuration ID, name, labels, UID:GID, binary path and argument list. The guard also checks `Config.Image` and `Config.Healthcheck`, but those two fields were omitted from the retained view. The exact failing subpredicate therefore cannot be resolved from this evidence. Image-reference normalization or inherited healthcheck fields are possible explanations, not confirmed causes. The failed inspection occurred before any start operation; it does not establish that Grafana or the compiled backend configuration is incompatible.

The first post-run verifier also produced a false base-image warning because the expected image configuration ID did not appear in its `docker image ls` inventory. A separate read-only inspection of the exact pinned repository digest confirmed the original image configuration ID and repository digest remain present. The original verifier report is retained; the supplemental read-back corrects that warning without changing the failed compatibility result. Future verification must use exact pinned-reference inspection for this identity check.

## Cleanup and retained evidence

- Network receipt: `43affbabf44d19804dde62e8802289c706796660484066fb9d60ff588114eb31` — absent.
- Grafana receipt: `d1d8fb58cdf3e29d758eddef420e3fed7231fb60cd4a46a1fd5af672a10210ff` — absent.
- No unresolved create intent or acknowledged-but-unpersisted ID; bootstrap authority directory empty.
- Baseline, final and fresh read-back inventories match: 15 containers, 6 networks, 70 listed image IDs and 14 volume names. No new volume or unrelated-resource deletion was observed.
- Exact pinned image preserved: `docker.io/grafana/otel-lgtm@sha256:35da4355c58162b6f27ccbd43c6214d565bc29fc9b18baaf43b59202c354577b`, image configuration ID `sha256:44a7f733cea9b946b061774e5cbc690cb303e4a2de1719279ae212f01c4ff28f`.
- All 42 retained command-payload hashes verified. The final artifact index verifies 48 retained files totaling 159,574 bytes, including the supplemental cleanup and field audit. Retention expires 2026-10-21T18:45:40.215528Z; no automatic deletion was scheduled.

Primary private records: [runtime outcome](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-1-20260921/evidence/outcome.json), [independent cleanup correction](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-1-20260921/independent-cleanup-readback.json), [field audit](/Users/jasonkrueger/maoi-stage-b-evidence/c2/attempt-1-20260921/identity-field-audit.json).

## Source and reviews

Prototype source was committed locally as `8797b164b73f7d83eb4183e3d58f00399a10282b`. The new durable resource ledger records intent before engine calls, persists exact IDs before subsequent side effects, and refuses resumption or adoption by name. Fault tests cover receipt persistence, abrupt child exit and recovery. Full prototype suite: **592 passed, 36 skipped**; Ruff passed. The executed private harness and read-only verifier passed **30 tests**, including real subprocess deadline/failure cases and an injected receipt/evidence-write failure proving that the manual-audit ID survives without authorizing cleanup.

Terra performed bounded implementation; the parent integrated and corrected the work. Sol passed the ledger and final executor source reviews. A fresh one-shot Fable review of the new executor and ledger completed with a usable **FINDINGS** verdict after 463.398 seconds; the parent corrected its two Medium and six Low findings, and Sol independently verified the corrections. Fable reviewed the original frozen packet; Sol reviewed the final corrected bytes. The earlier provider-rejected configuration packet was not retried or rerouted. Native transcript `87f11336-55f7-4eba-92d0-3aab2ff58dde` confirms `claude-fable-5-1`; native-reported session API-equivalent cost was $3.21457, not a daily billing total.

Sol also audited this outcome and independently verified all 48 indexed runtime artifacts. Final outcome verdict: **PASS_WITH_FINDINGS** for the faithfully reported runtime evidence limits; the packaging finding was closed. Outcome review SHA256: `d79eb6249f0448a1bc8359ca643bf2c3d08ec91cf82758d767ccfa5617db5538`.

Executed harness SHA256: `2af099b174a37ca7e97e60d4040b21dcf09b0b126e3e3b00f20b066e60098e4f`. Source manifest SHA256: `bbfdaf225742196a056f316c345e40158b7499e72bc2d4ffa1f45fa2a33a38a3`. Final Sol source report SHA256: `583bd70050064c3355d62b21940e16f1fadbeb42f6e86b0453ed18224259ab91`. Private preparation/review artifacts: `/Users/jasonkrueger/maoi-stage-b-evidence/dispatch/20260921-c2-approved-compatibility`.

## Next work and remaining boundaries

Prepare individually named inspection predicates and retain every compared nonsecret field before evaluating the guard; correct the base-image verifier to inspect the pinned reference directly. Review any normalization rule against actual engine/API evidence rather than silently weakening identity checks. A subsequent compatibility run requires a fresh root, run ID and reviewed card; this failed run did not authorize an automatic retry. No second C2 attempt occurred.

C2 backend startup/health, strict HTTP framing, seeds/oracles, Grafana account/token lifecycle, native policy and full acceptance remain unverified or incomplete. C1's prior named gaps remain unchanged. Ticket 19 stays claimed, ticket 12 stays blocked, and qualification and spend-reservation boundaries remain unchanged. All changes and commits remain local.
