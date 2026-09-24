# Unit 16 raw Notification ingress sanitizer outcome

2026-09-24. PASS for the sixteenth separately authorized local application unit,
baseline `1a62de7`. [validation.json](validation.json) records the final verdict
and evidence. The work is local only: nothing was pushed and no planning ticket
was closed.

## What the unit adds

`journal_ingress.sanitize_notification(body)` turns one raw Grafana Notification body into either an admissible `SourceRecord` for the recovery journal or a closed-code refusal ([docs](../../../../docs/recovery-journal.md#ingress)). It is pure and not yet called by the Receiver.

- **Read set.** It reads only `groupKey`, `truncatedAlerts` and, per alert, `fingerprint`, `status`, `values` and `startsAt`. Every other field, including Grafana's templated `message`, is parsed under the house parser's rules and dropped.
- **Mapping.**
  - Absent fields become null.
  - Numbers are canonical and compared by value.
  - Values are sorted by refId.
  - A bad `startsAt` is dropped, and only its Fingerprint is noted.
  - `body_digest` covers the exact raw bytes.
- **Checks.** Every 400-class check runs before any 422-class check, so a 422 means that Grafana could have sent the body and v1 cannot represent it. Each such refusal names up to 32 members, Resolved first, with counts. `refused_group` stays stable across resends.
- **Refusal summary.** `refusal_to_json` validates a nine-key summary that carries no HTTP status. `oversize_refusal` refuses from a `Content-Length` header alone.
- **Parser keyword.** `forwarder_json.parse_json` gains an additive `max_string_bytes` keyword with an unchanged default. Only the sanitizer raises it, which lifts the alert ceiling from 19 to 28 two-value alerts.

All 115 captured bodies and the three fixtures are admitted. The goldens match the recovery-journal plan.

## Review

- Two designs, a judge-synthesizer and a critic (14 issues, all accepted) produced the plan.
- The implementer and tester found no source bugs.
- The contract lens fuzzed 29,000 inputs with no mismatch and found one low validation gap. Root fixed it.
- The test-adequacy lens found seven gaps. A gap agent closed them, killing 19 mutants.
- A fresh reviewer bound the hashes: PASS with no source bug, after 46,000 more oracle-checked inputs. Root added an exact-type check and corrected overclaiming docs and a docstring. A second gap agent closed six more test items, killing 13 mutants. The same reviewer re-verified the result ([review](review.md)). The module is 509 lines against a 500-line split trigger; the split is deferred on the reviewer's advice.

## Validation

- Unit tests: **431 passed** in the four new files, over repeated runs.
- [Focused suite](focused-tests.txt): **1571 passed**. It covers the ingress files, every `parse_json`-dependent suite (`forwarder_json`, routes, exchange, upstream), the journal suites, the receiver and the replay.
- [Full suite](full-suite.txt): **4443 passed, 38 skipped in 270.90s**, exit 0; the baseline was 4012 passed, 38 skipped.
- Ruff (including line length), compile and `git diff --check` pass. Among existing modules only `forwarder_json.py` changed, additively, and every existing test file is byte-identical.

## Not qualified

- Receiver integration: the HTTP handler and status mapping, admission before the 202, the body spool, persisting refusal summaries, and the flood policy;
- the `capture` provenance kind;
- Grafana's real wire bytes (the captures store re-encoded bodies), and its retry and resend behaviour after a refusal;
- groups above the v1 limits, which are refused, never split or truncated;
- ratification of the proposed mappings, bounds and codes.

## Not performed and next

No provider, tenant or native call was made. No actual credential, C2 retry, paid experiment, deployment or human Report adjudication took place. The four protected dirty artifacts are unchanged and unstaged.

Next is the Receiver integration of the journal together with operator resume, then Run and effect records and ticket-38 accounting. Ticket 37 remains open.
