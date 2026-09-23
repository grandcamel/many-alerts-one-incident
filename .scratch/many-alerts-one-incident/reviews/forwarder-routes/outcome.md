# Strict JSON and read-only Jira route policy outcome

2026-09-23. PASS for the twelfth separately authorized local application unit,
baseline `31dfee4`. [validation.json](validation.json) records the final verdict and
evidence. The work is local only: nothing was pushed and no planning ticket was
closed.

## What the unit adds

`forwarder_json` parses strict UTF-8 RFC 8259 JSON:
- depth at most 16, arrays at most 256 items, keys and strings at most 16 KiB each;
- duplicate keys rejected after unescaping, as are U+0000, lone surrogates and non-finite numbers;
- request integers must fit within 2^53-1; fractional upstream lexemes are kept as `JSONDecimal` text and never become floats;
- an escape-aware linear prescan bounds depth before decoding.

It also provides a sorted RFC 8785-subset encoder and domain-separated SHA-256 digests. Error handlers only record fixed codes and raise fresh errors outside the handler.

`forwarder_routes` validates an operator `JiraVenuePolicy` and a Receiver `ScopeManifest`. The manifest digest equals the lease `scope_digest`, and `require_manifest_binding` checks a manifest against a grant.

`RoutePolicy.route` turns a parsed request into a `RoutedRequest` or a closed `RoutePolicyError`, which maps to a receipt reason:
- Two routes are matchable, both `partial`: `jira.issue.get` for manifest-registered issues, and the first page of `jira.search`.
- The other 23 catalog routes are unavailable, each with named missing inputs.
- Caller values only select within the manifest.
- The upstream request is rebuilt from manifest, policy and template values plus the caller's capped `maxResults`.
- The version-1 request digest binds service, route, policy, scope, method, target and body. It binds no origin and may never satisfy a permit.

`check_response` validates identity, scope, count, label and open status for status-200 responses only. Everything else becomes `response_policy_rejected` with a fixed 502.

## Review

- Sonnet workers implemented the modules and wrote the deterministic and adversarial tests.
- Opus lens reviewers and Sonnet refuters confirmed 29 findings; the fix rounds resolved 28.
- The remaining size deviation is recorded here: `forwarder_routes.py` has 1,044 lines against a 750-line target, and `forwarder_json.py` has 321 against 300. The mandated catalog, validators and digests account for it.
- The round-3 residue was 25 test gaps for correct but unpinned guards. A dedicated agent closed them, with six mutation confirmations.
- A fresh reviewer then recomputed every golden vector independently, fuzzed 50,000 requests and killed 82 of 84 mutants (both survivors explained). Bound to the final hashes, the verdict is PASS; see the [review](review.md).

## Validation

- Unit tests: **564 passed** in repeated runs.
- [Focused Forwarder suite](focused-tests.txt): **1753 passed**.
- [Full suite](full-suite.txt): **2627 passed, 36 skipped in 134.19s**, exit 0.
- Ruff (including line length), compilation and `git diff --check` pass.
- A stray coverage data file created by a worker was removed; no coverage artifact is committed.

## Not qualified, not performed, next

**Not qualified:** lease resolution or the sentinel store, dispatch permits, upstream serialization or origin binding, credentials, real Jira response compatibility (including content-type parameters), tenant IDs or templates, readiness wiring, mutation, projection, continuation, SSE, any non-Jira route, native clients and deployment.

**Not performed:** no provider, tenant or native call; no actual credential, C2 retry, paid experiment, deployment or human Report adjudication. The four protected dirty artifacts are unchanged and unstaged.

**Next:** unit 13a, the atomic dispatch gate, write fence and one-request exchange from the reviewed [dispatch plan](../forwarder-dispatch/implementation-plan.md). Then 13b, the fixed-origin upstream connector and version-2 serializer. Planning ticket 36 remains open.
