# Privacy review of unpushed commits — 2026-09-18

Scope: all unpushed commits in both checkouts — 22 on `main` (`origin/main..HEAD`, base `8ca7520`) and the prototype-only commits on `prototype/mcp-grafana-eyes`. Method: orchestrator mechanical scan (credential/token/key/email/high-entropy patterns) plus one independent headless Pro review (`gemini-3.1-pro-high`, read-only, staged diffs) — terminal classification `usable`.

## Outcome

One blocker, fixed and verified:

- **P1 synthetic sentinel shape** (`prototype/routing_probe/artifacts/routing-probe.json`): the probe key used the real Anthropic `sk-ant-` prefix. Although random, synthetic and never valid, its shape would trip platform secret scanning/push protection on a public remote. Fixed by reshaping to `p1-probe-sentinel-<32 hex>`, re-running the probe (verdict `supported-routing` reproduced, $0), and — with user approval — rewriting the never-pushed prototype history so the old-shaped value exists in no commit. P1 evidence is now prototype commit **`1973f90`**.

Verified non-findings: Stage A runtime sentinels persisted nowhere (`runtime_secret_matches: 0` in `stage-a.json`); no real credentials, OAuth tokens, private keys or personal emails in either diff; `admin/admin` is a documented Grafana default in a research doc; `username/password` hits are upstream mcp-grafana source captures; hex strings in `bundle-sha256.json`/`provenance/` are integrity hashes; `sk-ant` in `grafana_jsm_sandbox/log_formatter.py:81` is the project's own redaction regex, already on `origin/main`. Provenance LICENSE is Apache-2.0.

Post-fix state: **no known push blockers.** Both repos remain local; no push performed or authorized.
