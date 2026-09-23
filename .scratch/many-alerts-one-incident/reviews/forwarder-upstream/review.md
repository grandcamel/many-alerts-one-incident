# Unit 13b synthetic fixed-origin upstream connector: independent review

## Design and review history

A read-only design panel produced three competing designs: contract-first,
wire-first and trust-first. Both judge panels picked contract-first. A
synthesizer grafted in the judges' required fixes, and a completeness critic
raised 15 issues, all resolved in [plan revision 2](implementation-plan.md).
Root reconciled the plan against the 13a commit `c1869a2` before
implementation started; every consumed 13a name, flag, constant and signature
matched.

The implementation workflow (56 agents) used Sonnet implementers and testers,
Opus lens reviewers (contract, wire and concurrency, fail-closed and custody,
test adequacy), Sonnet refuters and an Opus fixer.

| Round | Raw findings | Confirmed | Outcome |
| --- | --- | --- | --- |
| 1 | 23 | 16 | fixed, including F1-1 (high): a test sent real packets to the documentation address 192.0.2.10 |
| 2 | 11 | 9 | fixed |
| 3 | 11 | 8 | root fixed the one source defect (F3-3); a test agent covered all eight |

**Root source fix (F3-3).** `UpstreamDescriptor.__post_init__` now requires
`method == DISPATCHABLE_SHAPES[route_id].method`. Before the fix, a
CRLF-injected method built a descriptor silently, a request-splitting risk.

**Test gaps.** One Sonnet test agent added 23 tests covering F3-1 through F3-8
and killed all eight targeted mutants, on scratch copies only. It found no
source defects.

**Tester deviations** recorded for this review:
- race iteration counts are reduced;
- case 2b uses a 2 MiB body with a 4 KiB client `SO_SNDBUF`, because macOS does
  not propagate a listener's `SO_RCVBUF` to accepted sockets;
- the `synthetic_upstream` fixture takes keyword flags instead of the plan's
  `script=`.

**Size.** The module is 1,373 lines against a target of about 950. The recorded
reason was that the module is barred from importing `json`, so it hand-rolls the
endpoint's canonical JSON. The final reviewer corrected this (below).

## Final hash-bound source and test review

Reviewer: fresh independent agent, read-only. It verified these SHA-256 values
at HEAD `c1869a2`; the final hashes are listed after the addendum.

```
5b39d6bb20c20fb108bf7249d03555340d151237dd1895a3f8b310382b885aa5  grafana_jsm_sandbox/forwarder_upstream.py
b9022577df2ba3f92cbe1517117b466ec5b01b6390f3b71c8287e9cfdbc26b71  tests/test_forwarder_upstream.py
eec5739d4a490dacdf3dfdc49f404c02f536348f178742f4ad3490786ed3297a  tests/test_forwarder_upstream_integration.py
4d994f2bddda8a025cfe86e8d275375c8002a1a5eb68836f1d42646360b802ec  tests/test_forwarder_upstream_adversarial.py
b9f44e8259496f694d58a0bb758b6806c5fc11e75497afdcb3cdc767c82534db  docs/forwarder-control.md
fe3322c5a4eb094a04a937e6222eefab4072b3354d32fcad5598b180bb901827  .scratch/many-alerts-one-incident/reviews/forwarder-upstream/implementation-plan.md
```

Verdict: **PASS (source and test review)**. No blocking defects.

- **Production unavailable.** The origin gate, denied networks and address-class checks hold. There is no loader. The no-caller walk and the unchanged route catalog and readiness facts are asserted.
- **No ambient authority.** The source makes no environment, OS, file, resolver or `getattr` use. The only connect target is a canonical IPv4 literal, which takes CPython's numeric `inet_pton` path.
- **TLS.** `cadata` is the only trust source. The read-back covers protocol, verify mode, hostname settings, versions, flags, options (including bit 18), keylog, post-handshake authentication, store counts and sorted DER digests. A fresh context is built per connect, before the socket.
- **Credential custody.** Redaction, copy and pickle refusal, subclass refusal, service binding and a locked single claim hold. The request is assembled into an exact-length `bytearray`, zeroed in `finally`, and every channel path drops the credential reference.
- **Digest v2.** The reviewer recomputed every golden independently with `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)`: both endpoint digests, all three v2 digests, the v1 digests, the Authorization value and all six full and redacted wire hashes match.
- **Wire.** The header set and order match the plan. The method is bound to the route shape. No CR, LF or SP can reach any header field.
- **Connect.** Every refusal (types, the one-connect set, bindings, recomputed digest, parts, deadline cap) and the context build precede the socket. The limit is `min(deadline, t0 + 5)`, and connect never writes.
- **Channel, abort and close.** Sockets are captured under the phase lock; chunks are at most 16 KiB with per-chunk abort, clock and stall checks. The receive mapping matches 13a's `_upstream_reason`. `_shutdown_fd` uses the base-class shutdown, which the reviewer checked against the local CPython 3.13.7 `ssl.py` plaintext-fallback behavior. The reviewer found no check-then-use race, and double close is guarded.
- **Mutation probes.** On a scratch copy, 40 of 42 mutants were killed, each by an assertion about the mutated behavior. The two survivors exposed test gaps T1 and T2.
- **Size.** The extra lines are design content, not bloat: 793 AST statements at 1.43 lines per statement (routes 1.55, dispatch 1.34), with no essay comments. The hand-rolled encoder is only about 30 lines; the excess comes from the surface the plan mandates. About 55 lines could be folded: a shared refusal-dunder mixin across three classes, a clock re-check helper in `connect`, and step-5 checks in `request_descriptor` that `__post_init__` repeats. Root left these as they are, because they are behavior-neutral and would reopen a reviewed surface.
- **Deviations.** All three are acceptable:
  - Only the concurrent fd-reuse test drops from 200 to 40 iterations; the deterministic mutants carry that proof.
  - Case 2b asserts that the writer is really blocked before it aborts, and the evidence is macOS-only.
  - The keyword flags are equally expressive, though conflicting flags follow a silent precedence order.

  The reviewer also found an undeclared relaxation: the abort time bounds were widened from the plan's 0.05 s to 0.5 s and 0.2 s, as a margin against flakes. This is recorded here.

**Non-blocking findings, applied before commit:**
- **S1 (source).** Calling `BasicCredential.__init__` again on a claimed credential reset the claim and swapped the secret; it needs deliberate in-process code. Root added a probe of the `_claimed` slot, so re-initialization now fails with the same immutability refusal that `__setattr__` uses.
- **S2 (source).** `_encode_json_string` escaped only backslash and quote. No input could reach it: 50 adversarial field values were all refused earlier. Root added a printable-ASCII guard that fails closed with `endpoint_invalid`.
- **T1-T5 (tests).**
  - T1: the AST check did not see attribute chains. Mutant M28, `ssl.os.environ`, survived.
  - T2: the trust-store count was never tested alone. Mutant M05 survived.
  - T3: the planned case "50 concurrent abort/close pairs" was missing.
  - T4: one assertion was vacuous.
  - T5: the seeded digest property was narrower than the plan asked for.

  One test agent closed all five and added tests for S1 and S2; the addendum records its mutation proofs.
- **D1-D6 (docs).** Root applied the reviewer's exact wordings:
  - `endpoint_unqualified` applies only after the shape checks;
  - "CA issuer" replaces "CA custody";
  - buffer zeroing is scoped to Python memory;
  - the prepare-time wire bounds are named;
  - the channel sends at most once, when 13a calls `send`;
  - the post-handshake check is only that a peer certificate was presented.

## Addendum re-verification

The same reviewer then re-checked the post-review tree:
- **Source diff:** exactly S1 and S2 against its pristine copy. No `except` handler holds anything but an assignment, `pass` or `return`, and no new identifier is forbidden. All golden digest and wire tests still pass, and valid inputs encode as before.
- **Test diffs:** additive, except T4, where the tautology became `assert results == {expected}` with `expected` from `request_descriptor`, a stricter check. No existing assertion was weakened.
- **T5:** it routes every variant through the real `RoutePolicy` with manifests of 1 to 256 entries, and asserts inequality with all seven unit-12 denial digests.
- **T3:** it asserts `fileno() == -1` for all 50 pairs. Its `ResourceWarning` capture was checked separately to be live.
- **Mutants:** on a fresh copy, all seven were killed by assertions: M05, M28, both guard deletions (S1 and S2), T3's never-closing `close()`, and T5 with `target` or `endpoint_digest` dropped from the v2 document.
- **Runs:** two guard runs gave 439 passed with `NON_LOOPBACK_ATTEMPTS []`.
- **Docs:** D1-D6 are applied word for word, and the credential sentence is accurate.

Addendum verdict: **PASS**.

Two cosmetic nits were fixed before commit. A raw U+2028 inside a test string literal is now the escape `" "`, which is the same string value, and the three rewrapped documentation lines now fit the surrounding width. The three test files then gave 439 passed again under the guard. The full-suite log predates that one-literal change, which leaves every test's behavior the same.

Final hashes:

```
fa0d834fc3c0f1f92ebb28635e97f0ead91176c436b3ef68848bf9e68702c7ab  grafana_jsm_sandbox/forwarder_upstream.py
c2bd5c6f7669f6c4623037654e8eededd9b590442cf571bd1354561039c64e75  tests/test_forwarder_upstream.py
ebb1ae496d1a680c623a688fac183229c560a3da04b9547b09df65d88156064c  tests/test_forwarder_upstream_integration.py
640f739a9f4a24e128869fb77add5553eb3119b7c8d4692f0d00c27131150ca8  tests/test_forwarder_upstream_adversarial.py
```

## Residual limitations (accepted)

- **In-process code.** It can still read the credential's slot. Lock 1 does not catch deliberately computed module names.
- **CPython internals.** The second plaintext barrier depends on `SSLSocket.shutdown` clearing `_sslobj`; a control test pins this behavior.
- **Platform evidence.** The `shutdown(2)` wake of a blocked reader or writer is shown on macOS only. `_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION` is a hard-coded OpenSSL bit (18).
- **Trust breadth.** Wildcard and long-lived upstream leaves are accepted. Process-level OpenSSL configuration and C-level resolver behavior are not attested.
- **Conservative receipts.** A send refused before its first byte is still recorded as `DISPATCHED_UNKNOWN`.
- **Timing.** The integration tests depend on real timing. In T3, the last pair's socket is still referenced during `gc.collect()`, so for that iteration only the `fileno()` assertion covers a leak.
