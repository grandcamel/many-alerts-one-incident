# Ticket 19 — local Stage A verdict, 2026-09-18

**Supported for the exercised native-client transport scope. Ticket 19 remains claimed; ticket 12 remains blocked.** There is no measured incompatibility requiring an eyes-CLI fallback in this subset. This does not select Eyes or authorize Stage B.

The user explicitly authorized the local, model-free prototype after the protocol review. It ran on Darwin x86_64 with the real mcp-grafana v1.5.1 stdio binary, fresh TLS listeners and separate synthetic backend. No real Grafana tenant, model, container, cloud resource, paid API, production Skill change or publication was involved.

## Frozen evidence

Prototype branch `prototype/mcp-grafana-eyes`, commit **`5f90bfbb20a5a63edecaa118d9a214c0e08389e4`**, based on `3e17793`. Checkout: `/Users/jasonkrueger/projects/maoi-mcp-grafana-prototype`. All `prototype/` references below are at that commit; use `git show 5f90bfb:<path>` to recover the frozen evidence. The full bundle has a SHA-256 inventory at `prototype/bundle-sha256.json:1`.

Pinned upstream source `2a33c72f211560e4ffb39d6b99cad3c3dc2a3f6e`. Published archive SHA-256 matched; binary SHA-256 `d8cdb94e5e3154e1cf7b3ea850c83fd9309c222d96d99784187a57b76545334c` was checked immediately before execution (`prototype/provenance/manifest.json:1`, `prototype/stage_a/run_stage_a.py:172`). Actual help, license, source captures and reproducible pinned download are retained. No image/base-image acceptance is claimed.

## Observations

| Criterion | Verdict and evidence |
| --- | --- |
| Native transport and Bearer replacement | Supported: actual initialize/tools-list and query calls; allowed POST Prometheus read reaches a separate backend with the fixture upstream credential, not the client sentinel. Exact vector/range read-backs match. `prototype/stage_a/artifacts/stage-a.json:31`, `:48`, `:65`; assertions `prototype/stage_a/run_stage_a.py:197`. |
| TLS and authority negatives | Supported: native client rejects untrusted root, wrong hostname and expired certificate without backend execution. Absent, wrong-service and expired sentinels are denied; mid-session revocation persists. `prototype/stage_a/artifacts/stage-a.json:411`, `:429`, `:447`, `:465`, `:483`, `:501`; runner `:254` onward. |
| Redirects, paths and writes | Supported for the exact probes: upstream 307 becomes 502, recording redirect sink stays empty; direct mutation, absolute/unsafe/encoded paths and unlisted/duplicate/unknown query parameters never execute at backend. Direct probes are explicitly distinct from native MCP and independent of write-disable. `prototype/stage_a/artifacts/stage-a.json:256`; `prototype/stage_a/run_stage_a.py:241`; `prototype/stage_a/boundary.py:164`. |
| Rehearsal and source scope | Supported for exact allowed fixture selectors: separate application, current Run and pre-existing synthetic Change streams; system metric range. Previous-rehearsal telemetry query denied. Native client first performs an independently allowed datasource metadata lookup; this is recorded, not misrepresented as zero requests. `prototype/stage_a/artifacts/stage-a.json:152`, `:182`; `prototype/stage_a/run_stage_a.py:218`. |
| Output behavior | Supported for fixed fixtures: default 10 logs, truncation flag true and upstream limit 11; request 1000 capped 100, upstream 101 returns all 12 fixture records with truncation false. Real newline and 5,000-character payload survive exact comparison. Empty logs, exact metric samples and trace reference are distinct. `prototype/stage_a/artifacts/stage-a.json:82`, `:101`, `:118`; runner `:207`–238. General pagination and large-response cap behavior remain inconclusive. |
| Errors and interruption | Visible 500/502/504 failures; however the Prometheus tool omits diagnostic response bodies and retains numeric status only. Boundary receipts preserve the synthetic cause. A dispatched delayed query was interrupted, native process reaped and authority explicitly revoked. `prototype/stage_a/artifacts/stage-a.json:238`, `:256`, `:274`, `:511`, `:1257`. This is not full production recovery acceptance. |
| Runtime and isolation | Local harness completed in 4.486 s; eight startup-to-initialize samples ranged 63.866–245.847 ms. These are individual host samples, not model or venue latency guarantees. No container filesystem, OS egress confinement, real grants or model usability proof. `prototype/stage_a/artifacts/stage-a.json:522`, `:1285` and subsequent session `initialize_ms` values; `:516` preserves criterion gaps. |

Thirty-one exercised assertions are supported and zero are refuted (`prototype/stage_a/artifacts/stage-a.json:10813`). This count excludes unexercised criteria; it is not a complete ticket pass. The recorder contains only fixed synthetic request bodies, queries and outputs. It scanned against all 24 random runtime authority values before persistence, found zero matches, and cleared the scan list; ephemeral certificates/keys were removed. This is known-secret checking, not a universal privacy proof (`prototype/stage_a/artifacts/stage-a.json:1260`; `prototype/stage_a/run_stage_a.py:329`).

The complete repository suite passed: **241 passed, 36 skipped**, 9.33 s (`prototype/stage_a/artifacts/pytest.txt:25`). Container/integration skips remain NOT RUN. Captured upstream help retains its original space/tab formatting; source whitespace checks excluded only that raw capture rather than modifying the evidence.

## Small consequences for the next experiment

1. Keep explicit CA trust, service sentinel substitution and independent Forwarder policy. The client transport supports these exercised paths. Its own redirect helper permits method-preserving redirects; the boundary must enforce the stronger rule (`prototype/provenance/source/tools/http_redirect.go:26`, `prototype/stage_a/boundary.py:179`).
2. Carry the current Loki default/cap/truncation observations into the later tool-selection prompt and output-budget measurement. Do not reuse the historical “ten lines” claim without its truncation metadata and higher-limit option.
3. Preserve source-separated metadata and telemetry permissions. Do not treat every metadata lookup preceding a denied telemetry query as an authorization failure.
4. Plan visible operator denial diagnostics because native Prometheus errors can omit response bodies. Test model interpretation and audience usefulness only in separately authorized Stage B.

The next unresolved gate remains the bounded model/venue experiment. Before any paid execution, verify the required client/model skill and mediated Anthropic path, diagnostic reservation and private capture contract. No blocker edge changes here; Stage A alone cannot resolve 19 or unblock 12.
