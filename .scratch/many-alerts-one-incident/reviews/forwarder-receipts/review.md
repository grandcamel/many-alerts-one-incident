# Sanitized receipts and receipt-gated send: independent review

## Review history

Two orchestrated review workflows ran against the unit files. Each round used
four independent lens reviewers (contract, concurrency/time, fail-closed or
security, test adequacy), merged duplicates, and verified every finding with an
adversarial refuter before a fixer changed only the six unit files.

| Workflow | Round | Raw findings | Confirmed | Outcome |
| --- | --- | --- | --- | --- |
| Initial implementation | 1 | 45 | 24 | fixed |
| Initial implementation | 2 | 30 | 13 | fixed |
| Initial implementation | 3 | 22 | 10 | fixed |
| Initial implementation | 4 | 14 | 8 | open; superseded by the root redesign |
| Root redesign | 1 | 8 | 3 | fixed |
| Root redesign | 2 | 7 | 6 | fixed |
| Root redesign | 3 | 7 | 4 | test gaps; closed by root |

The first workflow's fixes hardened the code but left caller-supplied claim
tokens, precedence flags and a check-then-claim race: the send module compared
the wire digest with fields of the caller's receipt instance outside the ledger
lock. The root moved the digest comparison into `ReceiptLedger.claim_delivery`
against a ledger-private record copy, returned an identity-authenticated
`DeliveryClaim`, and made failure precedence structural (fixed-code raises follow
the `try/finally`). The second workflow adapted all tests, then confirmed and
fixed nine findings. Its round-3 residue was test adequacy only: lock
acquisition for some operations, socket consumption before every validation,
and record-before-restore order. The root added deterministic tests for these.
Five targeted mutants (lock removed from `begin_connect` and from `contains`,
record/restore swapped, socket claimed after validation, and the digest compared
with the caller receipt instead of the private record) each failed the focused
tests. The source was then restored byte-for-byte.

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. Verified SHA-256:

```
bfc2c5a3c3ecc2e8259b0ff62fb6ae83903d40639f7983cbda595b9c4b8b3a34  grafana_jsm_sandbox/forwarder_receipts.py
0b5eb8b4127223a8d5112128e864404aad5a1a14e5255e53b091e14ac8c71391  grafana_jsm_sandbox/forwarder_response_send.py
d05cf7fda8f566ee7a3b875747cbc5a05dcd99003056cbcc3a044eb74c81250d  tests/test_forwarder_receipts.py
9a54b629cccad0f4402327860942952040c557b6c111abfbb4bf527afc330959  tests/test_forwarder_receipts_adversarial.py
d3f8ba9227829a842fe61e3f6faaf149b7f290c490105335914e946f8cd6b25f  tests/test_forwarder_response_send.py
1b49add52579cde34fd048b62db3e85a4b46799c22c85eb80d666c3d79142908  tests/test_forwarder_response_send_integration.py
```

Verdict: **PASS (source and test review)**. No defects found.

- No path writes client bytes before `claim_delivery` succeeds. The claim checks
  receipt identity, then compares the wire digest with the private record in
  constant time. The written bytes are slices of that same immutable buffer.
  Delivery is one-use per receipt and per socket. A mismatch leaves the entry
  `pending` and sends nothing.
- Transition, reason and local-response tables match the plan. `FAILED` is
  reachable only from `connecting` and `NOT_DISPATCHED` only from `reserved`. A
  rejected finalize leaves the entry unchanged.
- Count and byte capacity are checked at `reserve` without eviction. The
  worst-case charge covers the 23-field snapshot record. Independent probes with
  maximal float representations, 128-character IDs, a 1 MiB body and status 599
  kept every real record within its charge (largest charge 1,443 bytes).
  Abandonment is stamped at the deadline, retention prunes at 310 seconds, and
  clock faults hold permanently while snapshots stay readable.
- The send path claims the socket before validation and writes timed chunks of
  at most 16 KiB. It records the outcome, then restores the timeout. Primary
  failures and interruptions take precedence. It never closes, shuts down,
  unwraps or retries.
- The documentation section matches the code and claims no upstream, lease,
  route, permit, journal, native or deployment qualification.
- The reviewer ran all 631 unit tests, then the real-TLS file 13 more times,
  including 5 runs under 2x CPU load. All passed.

## Residual limitations (accepted; consistent with the plan)

- Retention is lazy: an idle ledger keeps expired entries in memory until the
  next call, although snapshots never show them.
- `send_response` validates its deadline independently of the reservation. A
  caller that sends more than about 270 seconds after finalization can see its
  entry pruned mid-send, which is reported as `delivery_unrecorded` or hidden
  behind a primary failure. Callers derive the send deadline from the original
  handler deadline.
- An asynchronous interruption inside or immediately after `claim_delivery`, or
  in the `finally` before recording, leaves the delivery `sending`. An
  interruption during recording or restore replaces an earlier send failure.
- `not_sent` still consumes the receipt's one delivery; the caller closes.
- `sent` means the local TLS layer accepted every byte, not client receipt.
- Identity authentication protects against buggy callers, not hostile code in
  the same process.
- The stalled-reader real-TLS test depends on small socket buffers producing
  backpressure. It was stable on this Darwin host under load; other kernels are
  unverified.
