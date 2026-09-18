# Ticket 40: pinned 3.0.0 frontend caller facts

Source inspected offline: bare clone `/tmp/maoi-ticket40-source.zq3W4N/repo.git`,
tag `3.0.0` object `1755859a9de82c2e5e225be68abc401a5ebf2b4f`.

* The frontend RPC gateway calls `AdServiceClient.getAds(contextKeys)` and
  resolves only when gRPC supplies a response; a gRPC error rejects the Promise.
  It contains no catch, retry, or synthetic/default ads
  (`1755859a:src/frontend/gateways/rpc/Ad.gateway.ts:7-17`).
* `GET /api/data` awaits that gateway and sends HTTP 200 with `response.ads`
  only after success (`1755859a:src/frontend/pages/api/data.ts:11-18`). Its
  instrumentation wrapper catches a rejected handler, marks the span Error,
  assigns its local `httpStatus` variable 500, then rethrows
  (`1755859a:src/frontend/utils/telemetry/InstrumentationMiddleware.ts:8-23`).
  This is source evidence of an uncaught server handler error and Error span;
  it is not a source-level proof of the final Next.js HTTP body/status emitted
  by the framework.
* Browser-side `listAds` fetches `/api/data` (`1755859a:src/frontend/gateways/Api.gateway.ts:86-92`). The request helper does not inspect `response.ok`; it
  reads/parses any nonempty body (`1755859a:src/frontend/utils/Request.ts:20-32`).
  The React query caller retains no `error` value and defaults absent `data` to
  `[]` (`1755859a:src/frontend/providers/Ad.provider.tsx:28-40`). The Ad
  component then renders empty text/link fields when the list is empty
  (`1755859a:src/frontend/components/Ad/Ad.tsx:8-18`). This is UI fallback for
  no ad data, not a catch around the gRPC call and not an HTTP success fallback.

Candidate consequence supported by source: a selected `adFailure` error can
propagate from the RPC gateway through `/api/data`, mark the frontend server
span Error, and leave the browser ad view blank if the query supplies no data.
Do not claim every request fails, a particular HTTP response body, retry
behavior, or an alternate ad result from these files. No source was executed.

Read-only fetched source copies and hashes are retained under `upstream/receipt.json`; original source line numbers are preserved in the corresponding `.txt` files.
