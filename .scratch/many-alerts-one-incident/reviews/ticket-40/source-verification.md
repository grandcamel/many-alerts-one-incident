# Ticket 40 — pinned upstream source verification

After the committed offline gap record, the human requested “Commit and proceed.” A read-only bare fetch of upstream tag `3.0.0` resolved to commit `1755859a9de82c2e5e225be68abc401a5ebf2b4f` on 2026-09-18. No source was built/executed. [Receipt](upstream/receipt.json) records original paths, Git blob IDs and SHA-256 digests of retained text copies; original notices and the Apache-2.0 license are retained. These source artifacts stay repository-only, outside the Run's world.

## What the source establishes

- [AdService.java](upstream/AdService.java.txt):237-240 evaluates the enabled failure branch and uses `random.nextInt(10) == 0` to throw `StatusRuntimeException(Status.UNAVAILABLE)`. It is nominally one in ten eligible requests, not every request and not a guaranteed exact fraction in a finite window. Success sends the prepared advertisement response at :248-250.
- The catch at :251-256 adds an Error span event carrying the exception message, marks the span ERROR, logs a WARN message and calls `responseObserver.onError(e)`. Thus the source is not log-silent. Historical zero matching log lines remain a bounded query/window result, with collection/query/version differences unestablished; do not erase that observation or claim WARN was actually retrieved then.
- [Frontend RPC gateway](upstream/src__frontend__gateways__rpc__Ad.gateway.ts.txt):11-17 rejects its Promise on RPC error. [Ad-data handler](upstream/src__frontend__pages__api__data.ts.txt):11-18 awaits it and emits 200 with ads only after success; these paths supply no successful substitute ad response on rejection.
- [Instrumentation](upstream/src__frontend__utils__telemetry__InstrumentationMiddleware.ts.txt):16-23 records exception/error and a local HTTP-status attribute of 500, then rethrows. This does not by itself establish the final framework response body/status on the wire.
- [Ad provider](upstream/src__frontend__providers__Ad.provider.tsx.txt):28-40 defaults absent query data to an empty list. [Ad component](upstream/src__frontend__components__Ad__Ad.tsx.txt):8-18 renders empty fields for no ads. This supports a conditional empty-ad display, not a universal observed blank page, browser retry behavior, checkout failure or site outage.
- [Flag configuration](upstream/demo.flagd.json.txt):4-12 declares `adFailure`, enabled, with default off and off=false/on=true. The historical venue capture independently records the on/off actuation recipe.

## Version and acceptance limits

The immutable commit establishes behavior of the fetched upstream 3.0.0 source. The tag mapping at fetch time and historical chart appVersion do not attest the exact historical deployed image digest or guarantee that the intended future image was built from these bytes. Verify image/source correspondence during qualification. The source-level Mechanism was approved by the human on 2026-09-18; corrected-rule live acceptance, full diagnostic retrieval and model qualification remain outstanding. No original primary Fault definition is reopened.
