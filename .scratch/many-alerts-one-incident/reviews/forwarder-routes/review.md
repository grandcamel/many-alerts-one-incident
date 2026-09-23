# Strict JSON and read-only Jira route policy: independent review

## Design and review history

A read-only design panel produced three competing designs: engine-first,
Jira-complete and risk-first. Two judges scored them; engine-first and
risk-first finished close together, and Jira-complete was rejected for enabling
mutations, a code-owned JQL template, loose response limits and scope widening
from learned IDs. A synthesizer merged the winners, and a completeness critic
raised 16 issues, all resolved in [plan revision 2](implementation-plan.md).

The implementation workflow used Sonnet workers and adversarial testers. Opus
lens reviewers (contract, authority, JSON strictness, test adequacy) and Sonnet
refuters then reviewed it.

| Round | Raw findings | Confirmed | Outcome |
| --- | --- | --- | --- |
| 1 | 25 | 17 | fixed (including explicit `fields: null` acceptance and several type-confusion paths) |
| 2 | 21 | 12 | 11 fixed; the size-target deviation is recorded in the outcome |
| 3 | 23 | 25 | all test gaps for correct but unpinned guards; closed by a dedicated test agent |

The round-2 fix for the JQL matcher hardened the source structurally. The
upstream JQL is rendered from the matched operator template and manifest label,
never from a caller substring. The round-3 gap agent added regression tests for
all 25 guards and confirmed six high-priority mutants against scratch copies:
exact selector match, the JiraScope tuple guard, the `check_response` dict guard,
the template-render path, the POST-only search match and the body cap. The root
fixed one over-length line afterwards.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. Verified SHA-256:

```
134c774a6ec4abd82c09631a294c745a79e3c68505cba5bb70fcfaaee5d8e9a3  grafana_jsm_sandbox/forwarder_json.py
5105668d7b747dcfc7b8d371ddae60e163a2368ce606e5bf69b2e78499cdc83a  grafana_jsm_sandbox/forwarder_routes.py
4032711c3d3a4698dfb4d6daacb29bb8e211c3ea2cdce28df15999c6bc41c184  tests/test_forwarder_json.py
981618f7da9cabad08f0c504ce753332f08425a965ef50c8878c356c198c7d92  tests/test_forwarder_json_adversarial.py
368e7095c55e6dddef5a4867ad0bc4c1bc38154f669d128bf37254f3d1e58eb6  tests/test_forwarder_routes.py
48c5db6f50a52eef7d285c5fa230e7cace3391adab244b2bb5feb26b3c0df78c  tests/test_forwarder_routes_adversarial.py
```

Verdict: **PASS (source and test review)**. No defects found.

- **Golden vectors.** The reviewer recomputed every vector from the plan text with an independent encoder that does not use the `json` module: the 72-byte known answer, the tagged-digest vector, the policy and scope digests, the issue request digest, both search bodies and digests, and all seven denial digests. All matched byte for byte, and the module produces the same bytes.
- **JSON grammar and error discipline.** Duplicate keys, number modes, the escape-aware depth prescan, UTF-8, surrogates, U+0000, `ascii_only`, canonical escapes and UTF-16 key order all behave as the plan specifies. No `raise` appears inside an `except` handler, errors are fresh, and the import allowlists match.
- **`route()`.** Checks run in the plan's order and matching is exact. Manifest and policy agreement is enforced, selectors are grammar-checked and looked up exactly, and template matching reports zero, one or an ambiguous result. The upstream request is built only from the manifest entry, policy fields, the rendered template and the matched label, plus the caller's capped `maxResults`.
- **Fuzzing.** 50,000 generated requests raised only closed `RoutePolicyError` codes with empty exception chains and correct denial digests. Every success fell within a finite trusted set of targets and bodies.
- **`check_response`.** It checks issuance identity, allows only status 200, parses in finite mode, applies the plan's shape and value validators, and maps outcomes to the committed receipt reasons.
- **Catalog.** 25 entries, two `partial`, and every readiness fact false.
- **Mutation testing.** 82 of 84 in-memory mutants were killed. One survivor re-raised inside a handler; the on-disk AST test catches that. The other only affects readiness while no route is enabled, so no test can distinguish it today.
- **Size.** The routes module has 1,044 lines against a 750-line target, and the JSON module has 321 against 300. The reviewer found this is spec-mandated catalog, validation and digest content, not dead code.

The reviewer's two documentation precision notes were applied before commit: the
caller's capped `maxResults` does reach the upstream body, and an exception already
active in the caller's own handler still attaches as context.

## Residual limitations (stated non-claims)

- Traceback frame locals may hold input.
- The version-1 request digest binds no upstream origin, so it must never satisfy a dispatch permit.
- Passing responses keep upstream `self`, avatar and icon URLs.
- Only the operator template enforces the 30-minute window.
- Search completeness is not proven.
- Every non-200 upstream status becomes a fixed 502.
- Cascade labels outside the lowercase grammar are rejected.
- Readiness is not wired, and no tenant value is qualified.
